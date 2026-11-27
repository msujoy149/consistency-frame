"""Consistency Frame P1 — real media execution runtime (CF-WO-P1-005).

The missing execution layer between the P1-004 task compiler and
real media tools/providers. The compiler produces validated,
provider-neutral task packets; this module makes them executable
through verified adapters and records real output evidence.

Separation of concerns (WO §3) — ten distinct stages, never
collapsed into one another:

    1. Task planning        (P1-004 compiler — not here)
    2. Provider matching    (P1-004 compiler — not here)
    3. User authorization   (P1-001 session + P0 authorize_action)
    4. Request preparation  (adapter.prepare — no submission)
    5. Actual submission    (adapter.submit — the only chargeable step)
    6. Execution result     (adapter.poll — provider truth only)
    7. Artifact retrieval   (adapter.retrieve)
    8. Technical validation (adapter.verify_output + technical QC)
    9. Semantic QC          (human-review handoff — never automated)
    10. Timeline registration (runtime.timeline_delivery)

A compiled task packet is never proof of execution: only a genuine
adapter result can move an execution to SUCCEEDED, and SUCCEEDED is
reachable only from VALIDATING_OUTPUT with a validated artifact.

State machine (explicit, no invalid transitions):

    PLANNED -> WAITING_FOR_AUTHORIZATION -> READY -> SUBMITTED
    -> RUNNING -> RETRIEVING -> VALIDATING_OUTPUT -> SUCCEEDED

    FAILED is reachable from every non-terminal state, but only with
    a failure classification (see FAILURE_CODES). CANCELLED is
    reachable from every non-terminal state except VALIDATING_OUTPUT.
    NEEDS_USER_ACTION is reachable from every non-terminal state when
    the runtime cannot proceed without a human decision — most
    importantly on an uncertain submission result: an uncertain
    submission is NEVER treated as permission to resubmit and incur
    another charge. BLOCKED is reachable from every non-terminal
    state; resume returns to the state it came from.

    From NEEDS_USER_ACTION the execution may go to READY (the user
    resolved the blocker), FAILED or CANCELLED. A retry is an
    explicit new attempt (new execution_id and idempotency key);
    nothing retries automatically.

Idempotency: every execution carries a deterministic idempotency
key — the SHA-256 of the canonical string
``job_id|task_id|provider_id|packet_hash|attempt``. Where a provider
supports idempotency keys the adapter sends it; a resubmission with
the same key returns the existing execution instead of creating a
second chargeable request. Retries use a new attempt number, hence
a new key — a retry is a deliberate new submission, never a silent
duplicate.

Persistence: execution records ride on the production job dict
(``job["executions"]``), exactly like the P1-004-R1 identity
snapshot. The existing production store
(:mod:`runtime.production_store`) persists the job; no second job
database exists. Records carry no wall-clock timestamps, so the
job hash stays deterministic. Resume never auto-resumes
paid/external provider tasks — continuing a resumed job needs a
fresh authorized action (the store's existing rule).

This module never touches the filesystem, never calls a provider,
and never generates media: adapters do that, behind the
:class:`MediaAdapter` interface. It owns validation, state,
identity and provenance only.
"""
from __future__ import annotations

import copy
import hashlib
import re

from . import local_session
from .task_compiler import canonical_json, sha256_hex

MEDIA_EXECUTION_SCHEMA_VERSION = "2.5"

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")

EXECUTION_STATES = (
    "PLANNED",
    "WAITING_FOR_AUTHORIZATION",
    "READY",
    "SUBMITTED",
    "RUNNING",
    "RETRIEVING",
    "VALIDATING_OUTPUT",
    "SUCCEEDED",
    "FAILED",
    "CANCELLED",
    "NEEDS_USER_ACTION",
    "BLOCKED",
)

TERMINAL_STATES = ("SUCCEEDED", "FAILED", "CANCELLED")

_NON_TERMINAL = tuple(s for s in EXECUTION_STATES
                      if s not in TERMINAL_STATES)

# Freely available transitions (target -> allowed sources).
# SUCCEEDED is deliberately absent from the free list: it happens
# only inside transition_execution with a validated artifact.
ALLOWED_TRANSITIONS = {
    "WAITING_FOR_AUTHORIZATION": ("PLANNED",),
    "READY": ("WAITING_FOR_AUTHORIZATION", "NEEDS_USER_ACTION"),
    "SUBMITTED": ("READY",),
    "RUNNING": ("SUBMITTED",),
    "RETRIEVING": ("RUNNING",),
    "VALIDATING_OUTPUT": ("RETRIEVING",),
    "SUCCEEDED": ("VALIDATING_OUTPUT",),
    "FAILED": _NON_TERMINAL,
    "CANCELLED": tuple(s for s in _NON_TERMINAL
                       if s != "VALIDATING_OUTPUT"),
    "NEEDS_USER_ACTION": _NON_TERMINAL,
    "BLOCKED": _NON_TERMINAL,
}

# Failure classification vocabulary (WO §3, §11). "retryable" is
# advisory only: nothing retries automatically; a retry is an
# explicit new attempt through retry_execution.
FAILURE_CODES = {
    # The provider did not answer in time. Retryable only where the
    # provider's documented semantics say a timeout never charged.
    "provider-timeout": True,
    # The submission result is unknown (network cut, ambiguous
    # response). NEVER auto-resubmit: the provider may have charged.
    "submission-uncertain": False,
    # The provider returned output that cannot be parsed/used.
    "malformed-output": True,
    # Retrieved bytes do not match the provider's declared hash.
    "hash-mismatch": True,
    "cancelled-by-user": False,
    "cancelled-by-provider": False,
    # Authorization (P0/P1-001) refused the action.
    "authorization-denied": False,
    # The provider returned an error (4xx/5xx or equivalent).
    "provider-error": False,
    # The output failed its acceptance checks.
    "validation-failed": False,
    # A local tool (ffmpeg, companion) failed.
    "local-tool-error": True,
    # No credential was available for the provider.
    "credential-missing": False,
    # A local companion service was not reachable.
    "service-unavailable": True,
}


class MediaExecutionError(ValueError):
    """Execution error carrying a list of structured messages.

    ``code`` is an optional failure-classification code from
    :data:`FAILURE_CODES` (for example ``"submission-uncertain"``);
    adapters set it so the caller can classify the failure without
    parsing message text. ``None`` means unclassified.
    """

    def __init__(self, errors, code=None):
        if isinstance(errors, str):
            errors = [errors]
        self.errors = list(errors)
        self.code = code
        super().__init__("; ".join(self.errors))


def _require_session(session) -> None:
    if not local_session.is_active_session(session):
        raise MediaExecutionError(
            "media execution needs an exact active P1-001 session")


def _idempotency_key(job_id: str, task_id: str, provider_id: str,
                     packet_hash: str, attempt: int) -> str:
    """Deterministic idempotency key for one execution attempt."""
    return sha256_hex(
        f"{job_id}|{task_id}|{provider_id}|{packet_hash}|{attempt}")


def execution_id_for(job_id: str, task_id: str, provider_id: str,
                     packet_hash: str, attempt: int) -> str:
    """Stable execution id for one execution attempt."""
    key = _idempotency_key(job_id, task_id, provider_id, packet_hash,
                           attempt)
    return "exec-" + key[:24]


def validate_execution_failure(failure) -> list[str]:
    """Failure-classification errors (empty list = valid)."""
    errors: list[str] = []
    if failure is None:
        return errors
    if not isinstance(failure, dict):
        return ["execution.failure must be an object"]
    code = failure.get("code")
    if code not in FAILURE_CODES:
        errors.append(
            f"execution.failure.code {code!r} is not a known "
            f"failure code (one of {', '.join(FAILURE_CODES)})")
    if not isinstance(failure.get("message"), str) \
            or not failure["message"]:
        errors.append("execution.failure.message must be a "
                      "non-empty string")
    if not isinstance(failure.get("retryable"), bool):
        errors.append("execution.failure.retryable must be a boolean")
    return errors


def validate_execution_artifact(artifact) -> list[str]:
    """Validated-output artifact errors (empty list = valid)."""
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["execution.output must be an object"]
    if not isinstance(artifact.get("path"), str) \
            or not artifact["path"]:
        errors.append("execution.output.path must be a non-empty "
                      "string")
    elif artifact["path"].startswith("/") or ".." in artifact["path"].split("/"):
        errors.append("execution.output.path must be a relative path "
                      "without parent references")
    if not isinstance(artifact.get("sha256"), str) \
            or not _SHA_RE.match(artifact["sha256"]):
        errors.append("execution.output.sha256 must be a 64-char "
                      "lowercase hex digest")
    if not isinstance(artifact.get("bytes"), int) \
            or artifact["bytes"] <= 0:
        errors.append("execution.output.bytes must be a positive "
                      "integer")
    if not isinstance(artifact.get("format"), str) \
            or not artifact["format"]:
        errors.append("execution.output.format must be a non-empty "
                      "string")
    return errors


def validate_execution_record(record) -> list[str]:
    """Execution-record errors (empty list = valid)."""
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["execution record: expected an object, got "
                f"{type(record).__name__}"]
    if record.get("schema_version") != MEDIA_EXECUTION_SCHEMA_VERSION:
        errors.append("execution.schema_version must be "
                      f"'{MEDIA_EXECUTION_SCHEMA_VERSION}', got "
                      f"{record.get('schema_version')!r}")
    for field in ("execution_id", "task_id", "packet_id", "job_id",
                  "project_id", "provider_id", "adapter_id"):
        value = record.get(field)
        if field == "execution_id":
            if not isinstance(value, str) or not value.startswith("exec-"):
                errors.append(
                    f"execution.{field} {value!r} is not a valid "
                    "execution id")
        elif not isinstance(value, str) or not _ID_RE.match(value):
            errors.append(f"execution.{field} {value!r} is not a "
                          "valid id")
    if record.get("state") not in EXECUTION_STATES:
        errors.append(f"execution.state {record.get('state')!r} is "
                      "not a known execution state")
    if not isinstance(record.get("attempt"), int) \
            or record["attempt"] < 1:
        errors.append("execution.attempt must be a positive integer")
    if not isinstance(record.get("idempotency_key"), str) \
            or not _SHA_RE.match(record["idempotency_key"]):
        errors.append("execution.idempotency_key must be a 64-char "
                      "lowercase hex digest")
    if record.get("provider_job_id") is not None \
            and not isinstance(record["provider_job_id"], str):
        errors.append("execution.provider_job_id must be a string "
                      "when present")
    if record.get("previous_state") is not None \
            and record["previous_state"] not in EXECUTION_STATES:
        errors.append("execution.previous_state "
                      f"{record['previous_state']!r} is not a known "
                      "execution state")
    history = record.get("history")
    if not isinstance(history, list) or not history:
        errors.append("execution.history must be a non-empty list")
    else:
        for entry in history:
            if not isinstance(entry, dict) \
                    or entry.get("state") not in EXECUTION_STATES \
                    or not isinstance(entry.get("reason"), str):
                errors.append("execution.history entries must be "
                              "{state, reason} objects with a known "
                              "state")
                break
    errors.extend(validate_execution_failure(record.get("failure")))
    if record.get("output") is not None:
        errors.extend(validate_execution_artifact(record["output"]))
    if record.get("state") == "SUCCEEDED" \
            and record.get("output") is None:
        errors.append("a SUCCEEDED execution must carry a validated "
                      "output artifact")
    if record.get("state") == "FAILED" \
            and record.get("failure") is None:
        errors.append("a FAILED execution must carry a failure "
                      "classification")
    return errors


def _job_executions(job: dict) -> list:
    executions = job.get("executions")
    if executions is None:
        return []
    if not isinstance(executions, list):
        raise MediaExecutionError(
            "job.executions must be a list when present")
    return executions


def _find_execution(job: dict, execution_id: str) -> dict:
    for record in _job_executions(job):
        if isinstance(record, dict) \
                and record.get("execution_id") == execution_id:
            return record
    raise MediaExecutionError(
        f"execution_id {execution_id!r} is not in the job's "
        "executions")


def _with_execution(job: dict, record: dict) -> dict:
    """Return a copy of the job with one execution record replaced."""
    job = copy.deepcopy(job)
    executions = list(job.get("executions") or [])
    for index, existing in enumerate(executions):
        if isinstance(existing, dict) and existing.get(
                "execution_id") == record.get("execution_id"):
            executions[index] = record
            break
    else:
        executions.append(record)
    job["executions"] = executions
    return job


def _history(record: dict, state: str, reason: str) -> list:
    history = list(record.get("history") or [])
    history.append({"state": state, "reason": reason})
    return history


def create_execution(session, job, packet, provider_id, adapter_id,
                     *, adapter_version="", attempt=1,
                     reason="execution planned") -> tuple:
    """Plan one execution for a compiled packet.

    The packet must belong to the job's compiled task package and
    the provider must be the one the adapter serves. The new record
    starts in PLANNED with a deterministic execution id and
    idempotency key. Returns ``(record, updated_job)``; the job is
    deep-copied, never modified in place.
    """
    _require_session(session)
    if not isinstance(job, dict):
        raise MediaExecutionError("job is not an object")
    if job.get("session_id") != session.session_id:
        raise MediaExecutionError(
            "job belongs to a different session")
    if not isinstance(packet, dict):
        raise MediaExecutionError("packet is not an object")
    package = job.get("task_package")
    if not isinstance(package, dict):
        raise MediaExecutionError(
            "job has no compiled task package to execute against")
    known = {p.get("packet_id"): p for p in package.get("packets") or []
             if isinstance(p, dict)}
    if packet.get("packet_id") not in known:
        raise MediaExecutionError(
            f"packet_id {packet.get('packet_id')!r} is not in the "
            "job's task package")
    if packet.get("task_id") != known[packet["packet_id"]].get("task_id"):
        raise MediaExecutionError(
            "packet task_id does not match the compiled package")
    if not isinstance(provider_id, str) or not _ID_RE.match(provider_id):
        raise MediaExecutionError(
            f"provider_id {provider_id!r} is not a valid id")
    if not isinstance(adapter_id, str) or not _ID_RE.match(adapter_id):
        raise MediaExecutionError(
            f"adapter_id {adapter_id!r} is not a valid id")
    if not isinstance(attempt, int) or attempt < 1:
        raise MediaExecutionError("attempt must be a positive integer")
    packet_hash = packet.get("packet_hash")
    if not isinstance(packet_hash, str) \
            or not _SHA_RE.match(packet_hash):
        raise MediaExecutionError(
            "packet.packet_hash must be a 64-char lowercase hex "
            "digest")
    execution_id = execution_id_for(
        job["job_id"], packet["task_id"], provider_id, packet_hash,
        attempt)
    for existing in _job_executions(job):
        if isinstance(existing, dict) and existing.get(
                "execution_id") == execution_id:
            raise MediaExecutionError(
                f"execution {execution_id!r} already exists — "
                "resubmitting the same attempt is refused; use "
                "retry_execution for a new attempt")
    record = {
        "schema_version": MEDIA_EXECUTION_SCHEMA_VERSION,
        "execution_id": execution_id,
        "task_id": packet["task_id"],
        "packet_id": packet["packet_id"],
        "job_id": job["job_id"],
        "project_id": job["project_id"],
        "provider_id": provider_id,
        "adapter_id": adapter_id,
        "adapter_version": adapter_version,
        "state": "PLANNED",
        "attempt": attempt,
        "idempotency_key": _idempotency_key(
            job["job_id"], packet["task_id"], provider_id,
            packet_hash, attempt),
        "history": [{"state": "PLANNED", "reason": reason}],
    }
    errors = validate_execution_record(record)
    if errors:
        raise MediaExecutionError(errors)
    updated = _with_execution(job, record)
    return record, updated


def transition_execution(session, job, execution_id, new_state, *,
                         reason, failure=None, output=None,
                         provider_job_id=None) -> tuple:
    """Move one execution to a new state (explicit transitions only).

    ``reason`` is required and recorded in the history. SUCCEEDED is
    reachable only from VALIDATING_OUTPUT and only with a validated
    output artifact. FAILED requires a failure classification.
    NEEDS_USER_ACTION requires a reason naming what the user must
    decide. Returns ``(record, updated_job)``.
    """
    _require_session(session)
    if not isinstance(job, dict):
        raise MediaExecutionError("job is not an object")
    if job.get("session_id") != session.session_id:
        raise MediaExecutionError(
            "job belongs to a different session")
    if new_state not in EXECUTION_STATES:
        raise MediaExecutionError(
            f"new_state {new_state!r} is not a known execution state")
    if not isinstance(reason, str) or not reason:
        raise MediaExecutionError(
            "transition reason must be a non-empty string")
    record = copy.deepcopy(_find_execution(job, execution_id))
    current = record["state"]
    if current in TERMINAL_STATES:
        raise MediaExecutionError(
            f"execution {execution_id!r} is terminal ({current}) "
            "and cannot transition")
    allowed = ALLOWED_TRANSITIONS.get(new_state, ())
    if current not in allowed:
        raise MediaExecutionError(
            f"execution cannot move {current} -> {new_state}")
    if new_state == "SUCCEEDED":
        if current != "VALIDATING_OUTPUT":
            raise MediaExecutionError(
                "SUCCEEDED is reachable only from VALIDATING_OUTPUT")
        if output is None:
            raise MediaExecutionError(
                "SUCCEEDED requires a validated output artifact")
        record.pop("failure", None)
    if output is not None:
        artifact_errors = validate_execution_artifact(output)
        if artifact_errors:
            raise MediaExecutionError(artifact_errors)
        record["output"] = copy.deepcopy(output)
    if new_state == "FAILED":
        if failure is None:
            raise MediaExecutionError(
                "FAILED requires a failure classification")
        failure_errors = validate_execution_failure(failure)
        if failure_errors:
            raise MediaExecutionError(failure_errors)
        record["failure"] = copy.deepcopy(failure)
    if new_state == "BLOCKED":
        record["previous_state"] = current
    else:
        record.pop("previous_state", None)
    if provider_job_id is not None:
        if not isinstance(provider_job_id, str):
            raise MediaExecutionError(
                "provider_job_id must be a string when present")
        record["provider_job_id"] = provider_job_id
    record["state"] = new_state
    record["history"] = _history(record, new_state, reason)
    errors = validate_execution_record(record)
    if errors:
        raise MediaExecutionError(errors)
    updated = _with_execution(job, record)
    return record, updated


def resume_execution(session, job, execution_id, *,
                     reason="execution resumed from BLOCKED") -> tuple:
    """Return a BLOCKED execution to the state it came from."""
    _require_session(session)
    record = _find_execution(job, execution_id)
    if record.get("state") != "BLOCKED":
        raise MediaExecutionError(
            f"execution {execution_id!r} is not BLOCKED "
            f"(state {record.get('state')!r})")
    previous = record.get("previous_state")
    if previous is None or previous not in EXECUTION_STATES:
        raise MediaExecutionError(
            f"execution {execution_id!r} has no resumable previous "
            "state")
    updated_record = copy.deepcopy(record)
    updated_record["state"] = previous
    updated_record.pop("previous_state", None)
    updated_record["history"] = _history(
        updated_record, previous, reason)
    errors = validate_execution_record(updated_record)
    if errors:
        raise MediaExecutionError(errors)
    return updated_record, _with_execution(job, updated_record)


def retry_execution(session, job, execution_id, *,
                    reason="explicit retry as a new attempt") -> tuple:
    """Start a new attempt for a failed or user-blocked execution.

    Only FAILED executions with a retryable failure, and
    NEEDS_USER_ACTION executions whose blocker the user resolved,
    may be retried. The new attempt gets a new execution id and
    idempotency key; the old record is linked via ``superseded_by``
    and keeps its state. Returns ``(new_record, updated_job)``.
    """
    _require_session(session)
    if not isinstance(job, dict):
        raise MediaExecutionError("job is not an object")
    if job.get("session_id") != session.session_id:
        raise MediaExecutionError(
            "job belongs to a different session")
    old = _find_execution(job, execution_id)
    state = old.get("state")
    if state == "FAILED":
        failure = old.get("failure") or {}
        if not failure.get("retryable"):
            raise MediaExecutionError(
                f"execution {execution_id!r} failed with "
                f"non-retryable code {failure.get('code')!r}; a "
                "retry needs a new packet, not a new attempt")
    elif state != "NEEDS_USER_ACTION":
        raise MediaExecutionError(
            f"only FAILED (retryable) or NEEDS_USER_ACTION "
            f"executions may be retried, not {state!r}")
    package = job.get("task_package") or {}
    packet = None
    for candidate in package.get("packets") or []:
        if isinstance(candidate, dict) and candidate.get(
                "packet_id") == old.get("packet_id"):
            packet = candidate
            break
    if packet is None:
        raise MediaExecutionError(
            "the execution's packet is no longer in the job's task "
            "package")
    attempt = int(old.get("attempt") or 1) + 1
    new_record, updated = create_execution(
        session, job, packet, old["provider_id"], old["adapter_id"],
        adapter_version=old.get("adapter_version", ""),
        attempt=attempt, reason=reason)
    old = copy.deepcopy(old)
    old["superseded_by"] = new_record["execution_id"]
    updated = _with_execution(updated, old)
    return new_record, updated


def execution_for_task(job, task_id) -> list:
    """All execution records for one task, in creation order."""
    return [r for r in _job_executions(job)
            if isinstance(r, dict) and r.get("task_id") == task_id]


def execution_summary(job) -> dict:
    """Counts of executions by state, plus failed task ids."""
    summary = {state: 0 for state in EXECUTION_STATES}
    failed_tasks: list[str] = []
    for record in _job_executions(job):
        if not isinstance(record, dict):
            continue
        state = record.get("state")
        if state in summary:
            summary[state] += 1
        if state == "FAILED" and record.get("task_id"):
            failed_tasks.append(record["task_id"])
    summary["failed_tasks"] = sorted(set(failed_tasks))
    summary["total"] = sum(summary[s] for s in EXECUTION_STATES)
    return summary


class MediaAdapter:
    """Canonical execution adapter interface (WO §3).

    One adapter serves one provider. An adapter declares what it
    can do, validates inputs, prepares a request without submitting
    it, submits, polls async jobs, cancels, retrieves outputs, and
    verifies them. Every method fails closed with
    :class:`MediaExecutionError` and never invents a result.

    Subclasses override the operations they support; an operation
    an adapter does not support raises MediaExecutionError naming
    the operation (never a silent no-op, never a fake success).
    """

    adapter_id = "adapter-base"
    provider_id = "provider-base"
    adapter_version = ""

    def capabilities(self) -> dict:
        """Declared capabilities: operations + task types served."""
        return {"operations": [], "task_types": []}

    def supports_task_type(self, task_type: str) -> bool:
        """Whether this adapter serves the packet's task type."""
        return task_type in self.capabilities().get("task_types", [])

    def preflight(self, packet, context) -> list:
        """Pre-submission checks; empty list means ready.

        The base implementation only checks the task type. Concrete
        adapters add service availability, model/language/voice
        verification, consent and commercial-eligibility checks.
        """
        if not isinstance(packet, dict):
            return ["packet is not an object"]
        if not self.supports_task_type(packet.get("task_type")):
            return [f"adapter {self.adapter_id} does not serve "
                    f"task type {packet.get('task_type')!r}"]
        return []

    def translate(self, packet, context) -> dict:
        """Translate a packet into a provider request (no submit)."""
        if not isinstance(packet, dict):
            raise MediaExecutionError("packet is not an object")
        return {
            "provider_id": self.provider_id,
            "canonical_instruction": packet.get(
                "canonical_instruction", ""),
            "task_id": packet.get("task_id"),
        }

    def prepare(self, packet, context) -> dict:
        """Build the submission request, including the idempotency key.

        Preparation never submits and never charges. The returned
        request carries ``idempotency_key`` where the provider
        supports one.
        """
        errors = self.preflight(packet, context)
        if errors:
            raise MediaExecutionError(errors)
        request = self.translate(packet, context)
        request["idempotency_key"] = context.get("idempotency_key")
        return request

    def submit(self, request, context) -> dict:
        """Submit a prepared request.

        Returns ``{"provider_job_id": str|None, "completed": bool,
        "output": artifact|None, "failure": failure|None}``.
        A synchronous adapter returns ``completed: True`` with the
        output; an async adapter returns ``completed: False`` with a
        provider job id. An uncertain submission (the provider may
        have accepted the request but the answer was lost) must
        raise MediaExecutionError with code ``submission-uncertain``
        — the caller moves the execution to NEEDS_USER_ACTION and
        never resubmits automatically.
        """
        raise MediaExecutionError(
            f"adapter {self.adapter_id} does not implement submit")

    def poll(self, provider_job_id, context) -> dict:
        """Poll an async provider job.

        Returns the same shape as :meth:`submit`. Synchronous
        adapters raise MediaExecutionError naming the operation.
        """
        raise MediaExecutionError(
            f"adapter {self.adapter_id} does not implement poll")

    def cancel(self, provider_job_id, context) -> bool:
        """Cancel an async provider job. True when cancelled.

        Raises MediaExecutionError when the provider offers no
        cancellation — the caller records the refusal, never
        pretends the job stopped.
        """
        raise MediaExecutionError(
            f"adapter {self.adapter_id} does not support "
            "cancellation")

    def retrieve(self, provider_job_id, output_ref, context) -> str:
        """Retrieve provider output to a local path; returns the path.

        For URL outputs the adapter downloads with a size limit and
        verifies the bytes; for local outputs it verifies path
        containment. The returned path is inside the workspace root
        from the context.
        """
        raise MediaExecutionError(
            f"adapter {self.adapter_id} does not implement retrieve")

    def verify_output(self, path, packet, context) -> dict:
        """Verify a retrieved output file; returns artifact metadata.

        The base implementation checks existence, positive size and
        SHA-256. Concrete adapters add format/probe metadata.
        """
        import os
        if not isinstance(path, str) or not path:
            raise MediaExecutionError(
                "verify_output needs a non-empty path")
        if not os.path.isfile(path):
            raise MediaExecutionError(
                f"output file {path!r} does not exist")
        size = os.path.getsize(path)
        if size <= 0:
            raise MediaExecutionError(
                f"output file {path!r} is empty")
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return {
            "path": path,
            "sha256": digest.hexdigest(),
            "bytes": size,
            "format": os.path.splitext(path)[1].lstrip(".").lower()
            or "unknown",
        }


__all__ = [
    "MediaExecutionError",
    "MEDIA_EXECUTION_SCHEMA_VERSION",
    "EXECUTION_STATES",
    "TERMINAL_STATES",
    "ALLOWED_TRANSITIONS",
    "FAILURE_CODES",
    "execution_id_for",
    "validate_execution_failure",
    "validate_execution_artifact",
    "validate_execution_record",
    "create_execution",
    "transition_execution",
    "resume_execution",
    "retry_execution",
    "execution_for_task",
    "execution_summary",
    "MediaAdapter",
]
