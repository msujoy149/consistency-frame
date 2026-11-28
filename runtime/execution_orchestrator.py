"""Consistency Frame P1 — execution orchestration (CF-WO-P1-005, WO §8–§9).

Connects the P1-004 production orchestrator to the real media
execution runtime. The required pipeline, as discrete step
functions plus a fail-closed driver:

    1. Receive an approved production bundle (job in TEST_READY or
       BATCH_PRODUCTION — execution happens only after G1/G2).
    2. Receive the compiled task package.
    3. Select capability-compatible providers (P1-004 matching).
    4. Check ownership and asset authorization.
    5. Evaluate cost/privacy/licensing restrictions.
    6. Request required G1/G2 approval (already granted: the job
       state proves it; this module never waives a gate).
    7. Prepare executable requests.
    8. Submit authorized tasks.
    9. Track async jobs.
    10. Retrieve generated files.
    11. Verify actual artifacts.
    12. Register validated artifacts.
    13. Run technical QC.
    14. Prepare semantic QC handoffs.
    15. Create localized repair tasks (P1-004 QC correction tasks).
    16. Update production state.
    17. Assemble a valid timeline manifest.
    18. Run G6 delivery checks (evidence only — the gate itself is
        evaluated by production_orchestrator.evaluate_production_gate).

Dialogue, character and voice identity locks from P1-004 are
preserved: every packet's identity/voice bindings are checked
against the job's identity snapshot before submission, and a
mismatch blocks the execution (NEEDS_USER_ACTION) instead of
regenerating anything. Only defective shots get repair tasks;
approved neighbours are never regenerated. Short/long production
profiles are preserved (the job's format_profile is never
rewritten here).

Technical QC vs semantic QC (WO §9): automated checks cover file
readability, corrupt frames, frame rate, resolution, codec,
duration, audio presence, peak levels, technical A/V sync and
missing/invalid artifacts. Semantic checks (character continuity,
face drift, lip-sync quality, physical realism, creative intent)
need a real qualified reviewer or a human: where none is
connected, :func:`prepare_semantic_qc_handoff` creates a clear
human-review handoff. A project is never marked G6 PASS merely
because FFmpeg can read the output — see
:func:`evaluate_delivery_gate`.
"""
from __future__ import annotations

import copy

from . import local_session
from . import production_orchestrator
from . import task_compiler
from . import timeline_delivery
from .media_execution import (
    FAILURE_CODES,
    MediaExecutionError,
    create_execution,
    execution_summary,
    retry_execution,
    transition_execution,
)

EXECUTION_JOB_STATES = ("TEST_READY", "BATCH_PRODUCTION")

DEFAULT_SEMANTIC_CHECKS = (
    "character-continuity-vs-approved-reference",
    "face-drift-vs-approved-reference",
    "lip-sync-vs-dialogue",
    "physical-realism",
    "sound-dialogue-sync-semantic",
    "colour-grade-intent",
)


class ExecutionOrchestratorError(ValueError):
    """Execution orchestration error carrying structured messages."""

    def __init__(self, errors):
        if isinstance(errors, str):
            errors = [errors]
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


def _require_session(session) -> None:
    if not local_session.is_active_session(session):
        raise ExecutionOrchestratorError(
            "execution orchestration needs an exact active P1-001 "
            "session")


def _require_job(session, job) -> None:
    if not isinstance(job, dict):
        raise ExecutionOrchestratorError("job is not an object")
    if job.get("session_id") != session.session_id:
        raise ExecutionOrchestratorError(
            "job belongs to a different session")


def _failure_from_error(exc: MediaExecutionError) -> dict:
    """Map an adapter error to a failure classification."""
    code = getattr(exc, "code", None)
    if code not in FAILURE_CODES:
        code = "provider-error"
    return {"code": code,
            "message": "; ".join(exc.errors),
            "retryable": FAILURE_CODES[code]}


def select_execution_providers(session, job, package, providers=None,
                               *, providers_path=None) -> dict:
    """Match every packet to a capability-compatible provider.

    Returns ``{task_id: {"provider_id": str|None, "reason": str}}``.
    Matching is the P1-004 rule: VERIFIED then EXERCISED, commercial
    jobs exclude unapproved providers, NOT_TESTED and FAILED never
    match. An unmatched packet is reported, never force-matched.
    """
    _require_session(session)
    _require_job(session, job)
    if not isinstance(package, dict):
        raise ExecutionOrchestratorError("package is not an object")
    if providers is None:
        providers = task_compiler.load_provider_registry(
            providers_path)
    commercial = bool(job.get("commercial_use"))
    selections = {}
    for packet in package.get("packets") or []:
        if not isinstance(packet, dict):
            continue
        task_id = packet.get("task_id")
        provider_id, reason = task_compiler.match_provider_for_task(
            packet.get("task_type"), providers,
            commercial_use=commercial,
            needs_clone=bool(
                (packet.get("voice_binding") or {}).get("clone_voice")))
        selections[task_id] = {"provider_id": provider_id,
                               "reason": reason,
                               "task_type": packet.get("task_type")}
    return selections


def check_execution_authorizations(session, job, package,
                                   authorizations) -> dict:
    """Check the per-task user authorizations for execution.

    ``authorizations`` is ``{task_id: True}`` — explicit user
    approvals recorded by the caller. A packet whose
    ``authorization_required.required`` is true without an approval
    is reported unauthorized (the execution waits in
    WAITING_FOR_AUTHORIZATION); nothing is authorized implicitly.
    Returns ``{task_id: {"authorized": bool, "reason": str}}``.
    """
    _require_session(session)
    _require_job(session, job)
    authorizations = authorizations or {}
    result = {}
    for packet in package.get("packets") or []:
        if not isinstance(packet, dict):
            continue
        task_id = packet.get("task_id")
        required = packet.get("authorization_required") or {}
        if required.get("required"):
            action = required.get("action", "execute")
            if authorizations.get(task_id) is True:
                result[task_id] = {"authorized": True,
                                   "reason": f"authorized: {action}"}
            else:
                result[task_id] = {
                    "authorized": False,
                    "reason": f"authorization required ({action}) "
                              "but not granted for this task"}
        else:
            result[task_id] = {"authorized": True,
                               "reason": "no authorization required"}
    return result


def bindings_match_snapshot(packet, snapshot) -> list:
    """Identity-lock check: packet bindings vs the frozen snapshot.

    Returns a list of errors (empty = the packet's bindings agree
    with the snapshot). A mismatch blocks execution — the packet is
    never silently re-bound and nothing is regenerated.
    """
    errors: list[str] = []
    if snapshot is None:
        return errors
    characters = {}
    voices = {}
    for character in snapshot.get("characters") or []:
        if not isinstance(character, dict):
            continue
        cid = character.get("character_id")
        if cid:
            characters[cid] = character
            for voice in character.get("voice_profiles") or []:
                if isinstance(voice, dict) \
                        and voice.get("voice_profile_id"):
                    voices[voice["voice_profile_id"]] = cid
    for binding in packet.get("identity_bindings") or []:
        if not isinstance(binding, dict):
            continue
        cid = binding.get("character_id")
        if cid and cid not in characters:
            errors.append(
                f"packet binds character {cid!r}, which is not in "
                "the job's identity snapshot")
    voice_binding = packet.get("voice_binding") or {}
    vid = voice_binding.get("voice_profile_id")
    if vid:
        owner = voices.get(vid)
        expected = voice_binding.get("character_id")
        if owner is None:
            errors.append(
                f"packet binds voice profile {vid!r}, which is not "
                "in the job's identity snapshot")
        elif expected is not None and owner != expected:
            errors.append(
                f"voice profile {vid!r} belongs to character "
                f"{owner!r}, not {expected!r}")
    return errors


def _record_compat_result(session, job, execution) -> dict:
    """Mirror a terminal execution into P1-004 execution_results."""
    outcome = {"SUCCEEDED": "succeeded", "FAILED": "failed",
               "CANCELLED": "not-executed"}.get(execution["state"])
    if outcome is None:
        return job
    result = {"provider_id": execution.get("provider_id"),
              "outcome": outcome}
    output = execution.get("output") or {}
    if output.get("path"):
        result["output_ref"] = output["path"]
    failure = execution.get("failure") or {}
    if failure.get("message"):
        result["notes"] = failure["message"][:500]
    return production_orchestrator.record_execution_result(
        session, job, execution["task_id"], result)


def _task_context(context, execution, packet) -> dict:
    """Per-task adapter context: roots + execution identity + task bits."""
    task_context = dict(context or {})
    task_context["execution_id"] = execution["execution_id"]
    task_context["idempotency_key"] = execution["idempotency_key"]
    task_context["task_id"] = execution["task_id"]
    task_context["packet_id"] = execution["packet_id"]
    operations = (context or {}).get("ffmpeg_operations") or {}
    if execution["task_id"] in operations:
        task_context["ffmpeg_operation"] = operations[
            execution["task_id"]]
    models = (context or {}).get("models") or {}
    if execution["task_id"] in models:
        task_context["model"] = models[execution["task_id"]]
    voice = (context or {}).get("voice") or {}
    task_context.update(voice)
    return task_context


def submit_execution(session, job, execution_id, adapter, request, *,
                     context) -> tuple:
    """Submit one READY execution and drive it to its next state.

    READY -> SUBMITTED, then the adapter result decides: a
    synchronous completion drives SUBMITTED -> RUNNING ->
    RETRIEVING -> VALIDATING_OUTPUT; an async acceptance drives
    SUBMITTED -> RUNNING with the provider job id. An uncertain
    submission drives NEEDS_USER_ACTION (never an automatic
    resubmit); any other adapter error drives FAILED with its
    classification. Returns ``(record, updated_job)``.
    """
    _require_session(session)
    _require_job(session, job)
    record, job = transition_execution(
        session, job, execution_id, "SUBMITTED",
        reason="request submitted to adapter")
    task_context = _task_context(context, record, None)
    try:
        result = adapter.submit(request, task_context)
    except MediaExecutionError as exc:
        if getattr(exc, "code", None) == "submission-uncertain":
            record, job = transition_execution(
                session, job, execution_id, "NEEDS_USER_ACTION",
                reason="submission result uncertain: the provider "
                       "may have accepted the request; resubmission "
                       "is refused without a human decision")
            return record, job
        record, job = transition_execution(
            session, job, execution_id, "FAILED",
            reason="adapter submit failed",
            failure=_failure_from_error(exc))
        return record, job
    if not isinstance(result, dict):
        record, job = transition_execution(
            session, job, execution_id, "FAILED",
            reason="adapter submit returned no result",
            failure={"code": "malformed-output",
                     "message": "adapter submit returned no result",
                     "retryable": True})
        return record, job
    if result.get("completed") and result.get("output") is not None:
        record, job = transition_execution(
            session, job, execution_id, "RUNNING",
            reason="synchronous adapter completed the task",
            provider_job_id=result.get("provider_job_id"))
        record, job = transition_execution(
            session, job, execution_id, "RETRIEVING",
            reason="output retrieved")
        record, job = transition_execution(
            session, job, execution_id, "VALIDATING_OUTPUT",
            reason="output awaiting independent verification",
            output=result["output"])
        return record, job
    if result.get("provider_job_id"):
        record, job = transition_execution(
            session, job, execution_id, "RUNNING",
            reason="provider accepted the job",
            provider_job_id=result["provider_job_id"])
        return record, job
    if result.get("failure"):
        failure = result["failure"]
        record, job = transition_execution(
            session, job, execution_id, "FAILED",
            reason="adapter reported failure",
            failure={"code": failure.get("code", "provider-error"),
                     "message": failure.get("message", ""),
                     "retryable": bool(failure.get("retryable"))})
        return record, job
    record, job = transition_execution(
        session, job, execution_id, "FAILED",
        reason="adapter submit returned an unusable result",
        failure={"code": "malformed-output",
                 "message": "adapter submit returned neither a "
                            "provider job id, a completed output, "
                            "nor a failure",
                 "retryable": True})
    return record, job


def poll_execution(session, job, execution_id, adapter, *,
                   context) -> tuple:
    """Poll one RUNNING async execution and drive it forward.

    A still-running job stays RUNNING. A completed job with output
    drives RUNNING -> RETRIEVING -> VALIDATING_OUTPUT; a provider
    failure drives FAILED; a provider cancellation drives
    CANCELLED. Returns ``(record, updated_job)``.
    """
    _require_session(session)
    _require_job(session, job)
    executions = job.get("executions") or []
    record = next((r for r in executions
                   if isinstance(r, dict)
                   and r.get("execution_id") == execution_id), None)
    if record is None:
        raise ExecutionOrchestratorError(
            f"execution_id {execution_id!r} is not in the job")
    if record.get("state") != "RUNNING":
        raise ExecutionOrchestratorError(
            f"execution {execution_id!r} is not RUNNING "
            f"(state {record.get('state')!r})")
    task_context = _task_context(context, record, None)
    try:
        result = adapter.poll(record.get("provider_job_id"),
                              task_context)
    except MediaExecutionError as exc:
        record, job = transition_execution(
            session, job, execution_id, "FAILED",
            reason="adapter poll failed",
            failure=_failure_from_error(exc))
        return record, job
    if not isinstance(result, dict):
        record, job = transition_execution(
            session, job, execution_id, "FAILED",
            reason="adapter poll returned no result",
            failure={"code": "malformed-output",
                     "message": "adapter poll returned no result",
                     "retryable": True})
        return record, job
    if not result.get("completed"):
        return record, job
    if result.get("failure"):
        failure = result["failure"]
        if failure.get("code") == "cancelled-by-provider":
            record, job = transition_execution(
                session, job, execution_id, "CANCELLED",
                reason="provider cancelled the job")
            return record, job
        record, job = transition_execution(
            session, job, execution_id, "FAILED",
            reason="provider reported failure",
            failure={"code": failure.get("code", "provider-error"),
                     "message": failure.get("message", ""),
                     "retryable": bool(failure.get("retryable"))})
        return record, job
    if result.get("output") is not None:
        record, job = transition_execution(
            session, job, execution_id, "RETRIEVING",
            reason="provider output retrieved")
        record, job = transition_execution(
            session, job, execution_id, "VALIDATING_OUTPUT",
            reason="output awaiting independent verification",
            output=result["output"])
        return record, job
    record, job = transition_execution(
        session, job, execution_id, "FAILED",
        reason="adapter poll completed without output or failure",
        failure={"code": "malformed-output",
                 "message": "adapter poll completed without output "
                            "or failure",
                 "retryable": True})
    return record, job


def verify_execution_output(session, job, execution_id, *,
                            delivery_root, ffmpeg_adapter=None) -> tuple:
    """Independently re-verify a VALIDATING_OUTPUT execution.

    Recomputes the SHA-256 and byte count from the real file and
    re-probes the media. Success drives VALIDATING_OUTPUT ->
    SUCCEEDED (the only path to SUCCEEDED); a hash mismatch drives
    FAILED with code ``hash-mismatch``; any other verification
    failure drives FAILED with code ``validation-failed``.
    Returns ``(record, updated_job)``.
    """
    _require_session(session)
    _require_job(session, job)
    executions = job.get("executions") or []
    record = next((r for r in executions
                   if isinstance(r, dict)
                   and r.get("execution_id") == execution_id), None)
    if record is None:
        raise ExecutionOrchestratorError(
            f"execution_id {execution_id!r} is not in the job")
    if record.get("state") != "VALIDATING_OUTPUT":
        raise ExecutionOrchestratorError(
            f"execution {execution_id!r} is not VALIDATING_OUTPUT "
            f"(state {record.get('state')!r})")
    try:
        verified = timeline_delivery.validate_delivery_artifact(
            record.get("output"), delivery_root,
            ffmpeg_adapter=ffmpeg_adapter)
    except timeline_delivery.TimelineDeliveryError as exc:
        message = "; ".join(exc.errors)
        code = "hash-mismatch" if "SHA-256 mismatch" in message \
            else "validation-failed"
        record, job = transition_execution(
            session, job, execution_id, "FAILED",
            reason="independent output verification failed",
            failure={"code": code, "message": message,
                     "retryable": code == "hash-mismatch"})
        return record, job
    output = copy.deepcopy(record.get("output") or {})
    output.update({k: v for k, v in verified.items()
                   if k not in ("path", "sha256", "bytes", "format")})
    record, job = transition_execution(
        session, job, execution_id, "SUCCEEDED",
        reason="output independently verified", output=output)
    return record, job


def run_technical_qc(session, job, executions, *, delivery_root,
                     ffmpeg_adapter=None) -> dict:
    """Deterministic technical QC over SUCCEEDED execution artifacts.

    Checks only what a tool can decide: file readability, corrupt
    frames (ffprobe failure), frame rate, resolution, codec,
    duration, audio presence, peak levels, technical A/V sync and
    missing/invalid artifacts. Nothing here is a semantic judgement.
    Returns a QC report ``{job_id, checks, defects, verdict}``;
    verdict is ``"pass"`` only when no Critical or Major defect
    exists. A passing technical report is NOT a G6 PASS.
    """
    _require_session(session)
    _require_job(session, job)
    checks: list = []
    defects: list = []

    def _check(task_id, name, passed, detail=""):
        checks.append({"task_id": task_id, "check": name,
                       "passed": bool(passed), "detail": detail})
        return passed

    def _defect(severity, task_id, name, detail):
        defects.append({"severity": severity, "task_id": task_id,
                        "check": name, "detail": detail})

    package = job.get("task_package") or {}
    packets = {p.get("packet_id"): p
               for p in package.get("packets") or []
               if isinstance(p, dict)}
    for execution in executions or []:
        if not isinstance(execution, dict):
            continue
        if execution.get("state") != "SUCCEEDED":
            continue
        task_id = execution.get("task_id")
        output = execution.get("output") or {}
        packet = packets.get(execution.get("packet_id")) or {}
        path = output.get("path")
        if not path:
            _check(task_id, "file-readable", False, "no output path")
            _defect("Critical", task_id, "file-readable",
                    "succeeded execution carries no output path")
            continue
        if not _check(task_id, "file-readable",
                      isinstance(path, str) and path,
                      f"path={path}"):
            _defect("Critical", task_id, "file-readable",
                    "output path is missing")
            continue
        metadata = None
        if ffmpeg_adapter is not None:
            try:
                metadata = ffmpeg_adapter.probe(path)
            except MediaExecutionError as exc:
                _check(task_id, "media-readable", False,
                       "; ".join(exc.errors))
                _defect("Critical", task_id, "media-readable",
                        "ffprobe cannot read the output (corrupt "
                        "frames or unreadable file)")
                continue
            _check(task_id, "media-readable", True)
            duration = metadata.get("duration_seconds")
            if duration is not None:
                if not _check(task_id, "duration-positive",
                              duration > 0, f"duration={duration}"):
                    _defect("Major", task_id, "duration-positive",
                            "output duration is not positive")
            width = metadata.get("width")
            height = metadata.get("height")
            if width is not None and height is not None:
                expected = (packet.get("expected_output") or {}).get(
                    "format")
                _check(task_id, "resolution-present", True,
                       f"{width}x{height}")
            if packet.get("task_type") == "voice-generation":
                if not _check(
                        task_id, "audio-present",
                        bool(metadata.get("audio_streams")),
                        "voice output carries no audio stream"):
                    _defect("Major", task_id, "audio-present",
                            "voice output carries no audio stream")
    verdict = "pass" if not any(
        d["severity"] in ("Critical", "Major") for d in defects) \
        else "fail"
    return {"job_id": job["job_id"], "checks": checks,
            "defects": defects, "verdict": verdict}


def prepare_semantic_qc_handoff(session, job, executions, *,
                                checks_required=None) -> dict:
    """Create a human-review handoff for semantic QC.

    Semantic checks (character continuity, face drift, lip-sync
    quality, physical realism, creative intent) need a real
    qualified reviewer or a human. This handoff names the artifacts
    and the checks; it is never auto-approved and never auto-passed.
    """
    _require_session(session)
    _require_job(session, job)
    artifacts = []
    for execution in executions or []:
        if not isinstance(execution, dict):
            continue
        if execution.get("state") != "SUCCEEDED":
            continue
        output = execution.get("output") or {}
        artifacts.append({
            "task_id": execution.get("task_id"),
            "execution_id": execution.get("execution_id"),
            "path": output.get("path"),
            "sha256": output.get("sha256")})
    return {
        "schema_version": "2.5",
        "handoff_id": "handoff-" + job["job_id"],
        "job_id": job["job_id"],
        "project_id": job["project_id"],
        "artifacts": artifacts,
        "checks_required": list(
            checks_required or DEFAULT_SEMANTIC_CHECKS),
        "reviewer": "human",
        "status": "awaiting-human-review",
    }


def resolve_semantic_qc_handoff(handoff, *, decision, reviewer,
                                note=None) -> dict:
    """Record a human reviewer's decision on a semantic QC handoff.

    ``decision`` is ``"approved"`` or ``"rejected"``. The reviewer
    must be a named human (never ``"automated"``): an automated
    process cannot approve semantic QC.
    """
    if not isinstance(handoff, dict):
        raise ExecutionOrchestratorError("handoff is not an object")
    if decision not in ("approved", "rejected"):
        raise ExecutionOrchestratorError(
            f"decision {decision!r} must be approved or rejected")
    if not isinstance(reviewer, str) or not reviewer \
            or reviewer == "automated":
        raise ExecutionOrchestratorError(
            "semantic QC needs a named human reviewer, never an "
            "automated one")
    updated = copy.deepcopy(handoff)
    updated["status"] = "approved" if decision == "approved" \
        else "rejected"
    updated["decision"] = decision
    updated["reviewer"] = reviewer
    if note is not None:
        updated["note"] = note
    else:
        updated.pop("note", None)
    return updated


def evaluate_delivery_gate(session, job, manifest, qc_report,
                           handoff) -> list:
    """G6 delivery evidence checklist (empty list = evidence complete).

    Requires a valid delivery manifest, a passing technical QC
    report, and a semantic QC handoff approved by a named human.
    This checks evidence only — the gate itself is evaluated by
    production_orchestrator.evaluate_production_gate.
    """
    _require_session(session)
    _require_job(session, job)
    errors: list[str] = []
    if not isinstance(manifest, dict) or not manifest.get("id"):
        errors.append("G6 evidence: no delivery manifest")
    else:
        errors.extend(task_compiler.schema_errors(
            "timeline-manifest", manifest, "timeline-manifest"))
    if not isinstance(qc_report, dict):
        errors.append("G6 evidence: no technical QC report")
    elif qc_report.get("verdict") != "pass":
        errors.append("G6 evidence: technical QC did not pass")
    if not isinstance(handoff, dict):
        errors.append("G6 evidence: no semantic QC handoff")
    else:
        if handoff.get("status") != "approved":
            errors.append("G6 evidence: semantic QC handoff is not "
                          "approved by a human reviewer")
        if handoff.get("reviewer") in (None, "", "automated"):
            errors.append("G6 evidence: semantic QC reviewer must "
                          "be a named human, never automated")
    return errors


def run_execution_pipeline(session, job, *, adapters, authorizations,
                           context, delivery_root,
                           ffmpeg_adapter=None, providers=None,
                           max_polls=5) -> tuple:
    """Run the §8 execution pipeline for one approved job.

    The job must be in TEST_READY or BATCH_PRODUCTION. Every packet
    is matched, authorized, prepared, submitted, tracked, retrieved
    and verified; one task failing never aborts the others. The
    driver returns ``(updated_job, report)`` where the report
    carries per-task outcomes, the delivery manifest (when any
    artifact qualified), the technical QC report and the semantic
    QC handoff. Execution state persists on the job (the caller
    saves it with the production store).
    """
    _require_session(session)
    _require_job(session, job)
    if job.get("state") not in EXECUTION_JOB_STATES:
        raise ExecutionOrchestratorError(
            "execution needs a job in TEST_READY or "
            f"BATCH_PRODUCTION, not {job.get('state')!r}")
    package = job.get("task_package")
    if not isinstance(package, dict):
        raise ExecutionOrchestratorError(
            "job has no compiled task package to execute")
    selections = select_execution_providers(
        session, job, package, providers)
    authz = check_execution_authorizations(
        session, job, package, authorizations)
    snapshot = job.get("identity_snapshot")
    outcomes: dict = {}
    for packet in package.get("packets") or []:
        task_id = packet.get("task_id")
        selection = selections.get(task_id, {})
        provider_id = selection.get("provider_id")
        if not provider_id:
            outcomes[task_id] = {
                "outcome": "unmatched",
                "reason": selection.get("reason", "no provider")}
            continue
        adapter = (adapters or {}).get(provider_id)
        if adapter is None:
            outcomes[task_id] = {
                "outcome": "no-adapter",
                "reason": f"no adapter registered for {provider_id}"}
            continue
        lock_errors = bindings_match_snapshot(packet, snapshot)
        record, job = create_execution(
            session, job, packet, provider_id, adapter.adapter_id,
            adapter_version=adapter.adapter_version)
        execution_id = record["execution_id"]
        if lock_errors:
            record, job = transition_execution(
                session, job, execution_id, "NEEDS_USER_ACTION",
                reason="identity lock mismatch: "
                       + "; ".join(lock_errors))
            outcomes[task_id] = {
                "outcome": "needs-user-action",
                "execution_id": execution_id,
                "reason": "; ".join(lock_errors)}
            continue
        record, job = transition_execution(
            session, job, execution_id, "WAITING_FOR_AUTHORIZATION",
            reason="execution planned, authorization check pending")
        if not authz.get(task_id, {}).get("authorized"):
            record, job = transition_execution(
                session, job, execution_id, "NEEDS_USER_ACTION",
                reason=authz.get(task_id, {}).get(
                    "reason", "authorization required"))
            outcomes[task_id] = {
                "outcome": "needs-user-action",
                "execution_id": execution_id,
                "reason": authz.get(task_id, {}).get("reason", "")}
            continue
        record, job = transition_execution(
            session, job, execution_id, "READY",
            reason="authorized for execution")
        task_context = _task_context(context, record, packet)
        try:
            request = adapter.prepare(packet, task_context)
        except MediaExecutionError as exc:
            record, job = transition_execution(
                session, job, execution_id, "FAILED",
                reason="request preparation failed",
                failure=_failure_from_error(exc))
            job = _record_compat_result(session, job, record)
            outcomes[task_id] = {
                "outcome": "failed", "execution_id": execution_id,
                "reason": "; ".join(exc.errors)}
            continue
        record, job = submit_execution(
            session, job, execution_id, adapter, request,
            context=context)
        if record["state"] == "RUNNING":
            polls = 0
            while record["state"] == "RUNNING" and polls < max_polls:
                record, job = poll_execution(
                    session, job, execution_id, adapter,
                    context=context)
                polls += 1
        if record["state"] == "VALIDATING_OUTPUT":
            record, job = verify_execution_output(
                session, job, execution_id,
                delivery_root=delivery_root,
                ffmpeg_adapter=ffmpeg_adapter)
        if record["state"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
            job = _record_compat_result(session, job, record)
        outcomes[task_id] = {
            "outcome": record["state"].lower(),
            "execution_id": execution_id,
            "reason": (record.get("failure") or {}).get("message", "")}
    executions = job.get("executions") or []
    manifest = None
    manifest_error = None
    try:
        manifest = timeline_delivery.build_delivery_manifest(
            session, job, executions, delivery_root=delivery_root,
            ffmpeg_adapter=ffmpeg_adapter)
    except timeline_delivery.TimelineDeliveryError as exc:
        manifest_error = "; ".join(exc.errors)
    qc_report = run_technical_qc(
        session, job, executions, delivery_root=delivery_root,
        ffmpeg_adapter=ffmpeg_adapter)
    handoff = prepare_semantic_qc_handoff(session, job, executions)
    report = {
        "job_id": job["job_id"],
        "outcomes": outcomes,
        "execution_summary": execution_summary(job),
        "manifest": manifest,
        "manifest_error": manifest_error,
        "qc_report": qc_report,
        "semantic_qc_handoff": handoff,
    }
    return job, report


__all__ = [
    "ExecutionOrchestratorError",
    "EXECUTION_JOB_STATES",
    "DEFAULT_SEMANTIC_CHECKS",
    "select_execution_providers",
    "check_execution_authorizations",
    "bindings_match_snapshot",
    "submit_execution",
    "poll_execution",
    "verify_execution_output",
    "run_technical_qc",
    "prepare_semantic_qc_handoff",
    "resolve_semantic_qc_handoff",
    "evaluate_delivery_gate",
    "run_execution_pipeline",
]
