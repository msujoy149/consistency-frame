"""Consistency Frame P1 — local persistent production job store
(CF-WO-P1-004-R1, Task C).

Durable local storage for production jobs and checkpoints, as
plain JSON files under an explicitly configured local workspace
root. Standard library only. This store persists production
metadata ONLY — project/job ids, state, gate states,
analysis/bundle hashes, task package and statuses,
execution-result references, QC reports, correction rounds,
approved character/prop/voice ids, asset references with
provenance, and version information. It NEVER copies raw media,
voice recordings, personal photos, model weights, API keys,
passwords, tokens, raw private voice samples or private media
bytes; a job record that carries any of those is refused.

Layout::

    <store_root>/jobs/<job_id>.json
    <store_root>/checkpoints/<job_id>/<checkpoint_id>.json

Every record is an envelope::

    schema_version: "2.5"
    store_format_version: 1
    record_kind: "production-job" | "production-checkpoint"
    job_id, project_id, owner_id, workspace_id
    job: <the production job dict>
    record_hash: SHA-256 of the canonical JSON of the envelope
        without the record_hash field itself

Writes go through ``scripts/atomic_write.py`` (loaded by file
path, never by mutating ``sys.path``) so a record is replaced
atomically. Files are 0o600 and directories 0o700 on POSIX;
on Windows the store relies on the user-data-directory ACL
behaviour (the P1-001 R2 pattern) and claims no POSIX mode-bit
equivalence.

Path safety: the store root must be absolute; job and
checkpoint ids must match ``^[a-z0-9][a-z0-9-]{2,63}$``; paths
are built only from validated components; symlink containment
is checked with ``realpath`` — any component escaping the root
refuses the operation, and a symlinked job file itself is
refused on read. Malformed or tampered records are reported,
never silently dropped: ``list_production_jobs`` returns them
in ``invalid_files``, and single-record reads raise.

Authorization boundary: a stored session id is NEVER a
currently active authorization — it is provenance only.
Saving needs an exact active P1-001 session; resuming needs a
NEW exact active session plus a project/owner/workspace match,
stored-job validation and gate revalidation, and it rebinds
``job["session_id"]`` to the new session. Resume refuses
DELIVERED jobs and never triggers execution or auto-resumes
paid/external provider tasks — continuing a resumed job needs
a fresh authorized action.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import ntpath
import os
import re

from . import local_session

__all__ = [
    "ProductionStoreError",
    "STORE_FORMAT_VERSION",
    "save_production_job",
    "load_production_job",
    "list_production_jobs",
    "save_production_checkpoint",
    "resume_production_job",
]

STORE_FORMAT_VERSION = 1
_STORE_SCHEMA_VERSION = "2.5"
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
_RECORD_KINDS = ("production-job", "production-checkpoint")


class ProductionStoreError(ValueError):
    """A production-store operation failed (bad input, bad path,
    tampered record, or a failed authorization check)."""


# -- atomic-write helper (loaded by file path, never sys.path) --

_atomic_write = None


def _load_atomic_write():
    global _atomic_write
    if _atomic_write is None:
        helper_path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "scripts", "atomic_write.py")
        spec = importlib.util.spec_from_file_location(
            "consistency_frame_atomic_write", helper_path)
        if spec is None or spec.loader is None:
            raise ProductionStoreError(
                "cannot load scripts/atomic_write.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _atomic_write = module
    return _atomic_write


# -- validation helpers --


def _require_session(session):
    if not local_session.is_active_session(session):
        raise ProductionStoreError(
            "production store operations need an exact active "
            "P1-001 session")


def _validate_store_root(store_root):
    if not isinstance(store_root, str) or not store_root:
        raise ProductionStoreError(
            "store_root must be a non-empty string")
    if not os.path.isabs(store_root):
        raise ProductionStoreError(
            f"store_root {store_root!r} is not an absolute path")
    if os.name == "posix" and ntpath.splitdrive(store_root)[0]:
        raise ProductionStoreError(
            f"store_root {store_root!r} carries a Windows drive "
            "prefix and is not a valid POSIX absolute path")
    return store_root


def _validate_id(value, what):
    if not isinstance(value, str) or not _ID_RE.match(value):
        raise ProductionStoreError(
            f"{what} {value!r} is not a valid id")
    return value


def _ensure_private_dir(path):
    """Create ``path`` as a private directory (POSIX 0o700) or
    verify the existing directory. A symlink at the path is
    refused outright (the P1-001 pattern)."""
    if os.path.islink(path):
        raise ProductionStoreError(
            f"store directory {path!r} is a symlink — refusing to "
            "use a symlinked store directory")
    if not os.path.exists(path):
        os.makedirs(path, mode=0o700)
    elif not os.path.isdir(path):
        raise ProductionStoreError(
            f"store location {path!r} exists and is not a directory")
    if os.name == "posix":
        try:
            os.chmod(path, 0o700)
        except OSError:
            pass


def _contained_path(store_root, *parts):
    """Join validated components under the root and refuse any
    path whose realpath escapes the root (symlink containment)."""
    root_real = os.path.realpath(store_root)
    path = os.path.join(store_root, *parts)
    real = os.path.realpath(path)
    if real != root_real and not real.startswith(root_real + os.sep):
        raise ProductionStoreError(
            f"path {path!r} escapes the store root")
    return path


def _canonical_json(obj) -> bytes:
    return json.dumps(obj, indent=2, sort_keys=True,
                      ensure_ascii=False).encode("utf-8")


def _record_hash(record) -> str:
    without = {k: v for k, v in record.items() if k != "record_hash"}
    return hashlib.sha256(_canonical_json(without)).hexdigest()


def _file_mode():
    # POSIX only: restrictive 0o600 files. On Windows the helper's
    # default applies (user-data-directory ACL behaviour, the
    # P1-001 R2 pattern); no POSIX mode-bit equivalence is claimed.
    return 0o600 if os.name == "posix" else None


def _write_record(path, record):
    helper = _load_atomic_write()
    parent = os.path.dirname(path)
    _ensure_private_dir(parent)
    helper.atomic_write_json(path, record, mode=_file_mode())
    return path


# -- envelope --


def _envelope(record_kind, session, job):
    if not isinstance(job, dict):
        raise ProductionStoreError("job is not an object")
    job_id = _validate_id(job.get("job_id"), "job_id")
    project_id = _validate_id(job.get("project_id"), "project_id")
    record = {
        "schema_version": _STORE_SCHEMA_VERSION,
        "store_format_version": STORE_FORMAT_VERSION,
        "record_kind": record_kind,
        "job_id": job_id,
        "project_id": project_id,
        "owner_id": session.owner_id,
        "workspace_id": session.workspace_id,
        "job": copy.deepcopy(job),
    }
    record["record_hash"] = _record_hash(record)
    return record


def _verify_envelope(record, record_kind, project_id=None):
    """Envelope-integrity errors (empty = valid). Checks shape,
    versions, kind, id agreement and the record hash. This is
    integrity against accidental / unsupported mutation, not
    cryptographic protection against a malicious same-OS-user
    process."""
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["stored record is not an object"]
    if record.get("schema_version") != _STORE_SCHEMA_VERSION:
        errors.append("stored record schema_version "
                      f"{record.get('schema_version')!r} is not "
                      f"{_STORE_SCHEMA_VERSION!r}")
    if record.get("store_format_version") != STORE_FORMAT_VERSION:
        errors.append("stored record store_format_version "
                      f"{record.get('store_format_version')!r} is "
                      f"not {STORE_FORMAT_VERSION}")
    if record.get("record_kind") != record_kind:
        errors.append("stored record record_kind "
                      f"{record.get('record_kind')!r} is not "
                      f"{record_kind!r}")
    for field in ("job_id", "project_id", "owner_id", "workspace_id"):
        value = record.get(field)
        if not isinstance(value, str) or not value:
            errors.append(f"stored record {field} is missing or "
                          "not a string")
    job = record.get("job")
    if not isinstance(job, dict):
        errors.append("stored record job is not an object")
    else:
        if job.get("job_id") != record.get("job_id"):
            errors.append("stored record job.job_id does not match "
                          "the envelope job_id")
        if job.get("project_id") != record.get("project_id"):
            errors.append("stored record job.project_id does not "
                          "match the envelope project_id")
    if project_id is not None \
            and record.get("project_id") != project_id:
        errors.append("stored record project_id "
                      f"{record.get('project_id')!r} does not match "
                      f"the requested project {project_id!r}")
    stored_hash = record.get("record_hash")
    if not isinstance(stored_hash, str) or not stored_hash:
        errors.append("stored record carries no record_hash")
    elif stored_hash != _record_hash(record):
        errors.append("stored record record_hash does not match "
                      "the record content — the record was "
                      "modified or tampered with")
    return errors


def _read_record(path, record_kind, project_id=None):
    """Read and envelope-verify one record file. A symlinked
    file itself is refused on read."""
    if os.path.islink(path):
        raise ProductionStoreError(
            f"stored record {path!r} is a symlink — refusing to "
            "read a symlinked record")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            record = json.load(handle)
    except OSError as exc:
        raise ProductionStoreError(
            f"cannot read stored record {path!r}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ProductionStoreError(
            f"stored record {path!r} is not valid JSON: {exc}") \
            from exc
    errors = _verify_envelope(record, record_kind, project_id)
    if errors:
        raise ProductionStoreError(
            "stored record failed integrity checks: "
            + "; ".join(errors))
    return record


# -- operations --


def save_production_job(session, store_root, job) -> str:
    """Persist a production job. Returns the record path.

    Needs an exact active session. The envelope records the
    session's owner/workspace ids; the job's own stored
    session id is provenance only, never authorization.
    """
    _require_session(session)
    _validate_store_root(store_root)
    record = _envelope("production-job", session, job)
    path = _contained_path(store_root, "jobs",
                           record["job_id"] + ".json")
    return _write_record(path, record)


def load_production_job(store_root, job_id, project_id) -> dict:
    """Load a stored production job record (session-free metadata
    read). Returns the verified envelope record. Raises
    :class:`ProductionStoreError` when the record is missing,
    malformed or tampered with, or the project does not match.
    The returned record is data, not authorization — resuming
    the job needs :func:`resume_production_job` with a new
    active session.
    """
    _validate_store_root(store_root)
    _validate_id(job_id, "job_id")
    _validate_id(project_id, "project_id")
    path = _contained_path(store_root, "jobs", job_id + ".json")
    if not os.path.isfile(path):
        raise ProductionStoreError(
            f"no stored production job {job_id!r}")
    return _read_record(path, "production-job", project_id)


def list_production_jobs(store_root) -> dict:
    """List stored production jobs. Returns ``{"jobs": [...],
    "invalid_files": [...]}``. A valid record contributes a
    summary (job_id, project_id, state); a malformed or
    tampered file is reported in ``invalid_files`` with its
    error, never silently dropped.
    """
    _validate_store_root(store_root)
    jobs_dir = _contained_path(store_root, "jobs")
    summaries: list[dict] = []
    invalid: list[dict] = []
    if not os.path.isdir(jobs_dir):
        return {"jobs": summaries, "invalid_files": invalid}
    for name in sorted(os.listdir(jobs_dir)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(jobs_dir, name)
        if not os.path.isfile(path) or os.path.islink(path):
            invalid.append({"path": name,
                            "error": "not a regular record file"})
            continue
        try:
            record = _read_record(path, "production-job")
        except ProductionStoreError as exc:
            invalid.append({"path": name, "error": str(exc)})
            continue
        job = record["job"]
        summaries.append({
            "job_id": record["job_id"],
            "project_id": record["project_id"],
            "state": job.get("state"),
            "schema_version": record["schema_version"],
            "store_format_version": record["store_format_version"],
        })
    return {"jobs": summaries, "invalid_files": invalid}


def save_production_checkpoint(session, store_root, job,
                               checkpoint_id=None) -> str:
    """Persist a checkpoint copy of a production job. Returns
    the record path. ``checkpoint_id`` defaults to the job's
    current state (for example ``plan-ready``).
    """
    _require_session(session)
    _validate_store_root(store_root)
    if checkpoint_id is None:
        if not isinstance(job, dict) \
                or not isinstance(job.get("state"), str):
            raise ProductionStoreError(
                "cannot derive a checkpoint id: job carries no state")
        checkpoint_id = job["state"].lower().replace("_", "-")
    _validate_id(checkpoint_id, "checkpoint_id")
    record = _envelope("production-checkpoint", session, job)
    path = _contained_path(store_root, "checkpoints",
                           record["job_id"], checkpoint_id + ".json")
    return _write_record(path, record)


def resume_production_job(session, store_root, job_id,
                          project_id, *, registry=None,
                          voice_registry=None) -> dict:
    """Resume a stored production job under a NEW active session.

    The stored session id is provenance only: resume requires a
    new exact active P1-001 session whose owner/workspace ids
    match the stored envelope, plus stored-job validation and
    gate revalidation. The returned job has ``session_id``
    rebound to the new session and a recomputed job hash.
    DELIVERED jobs are refused. Resume never triggers
    execution and never auto-resumes paid/external provider
    tasks — continuing a resumed job needs a fresh authorized
    action.

    When ``registry`` is supplied, the job's identity snapshot
    (when present) is revalidated against the CURRENT
    registries before the session is rebound: a changed record,
    a missing asset or a hash mismatch stops the resume. Without
    registries the caller revalidates separately with
    ``runtime.identity_resolution.validate_resumed_identity``
    after resume returns the job.
    """
    _require_session(session)
    record = load_production_job(store_root, job_id, project_id)
    if record.get("owner_id") != session.owner_id:
        raise ProductionStoreError(
            "stored job belongs to a different owner")
    if record.get("workspace_id") != session.workspace_id:
        raise ProductionStoreError(
            "stored job belongs to a different workspace")
    job = copy.deepcopy(record["job"])
    if job.get("state") == "DELIVERED":
        raise ProductionStoreError(
            f"stored job {job_id!r} is DELIVERED and cannot be "
            "resumed")
    # Lazy import: the orchestrator lazily imports this store
    # inside plan_script_to_production; a top-level import here
    # would be circular.
    from .production_orchestrator import (
        job_hash,
        validate_gate_state,
        validate_job,
    )
    errors = validate_job(job)
    if errors:
        raise ProductionStoreError(
            "stored job failed validation: " + "; ".join(errors))
    gate_errors = validate_gate_state(job.get("gate_state"))
    if gate_errors:
        raise ProductionStoreError(
            "stored job gate state failed revalidation: "
            + "; ".join(gate_errors))
    if registry is not None:
        # Identity snapshot revalidation against the CURRENT
        # registries (integration: CF-WO-P1-004-R1-ADDENDUM-
        # IDENTITY Task N). Lazy import: identity_resolution
        # imports this store's caller chain, so a top-level
        # import would be circular.
        from .identity_resolution import validate_resumed_identity
        identity_errors = validate_resumed_identity(
            job, registry=registry, voice_registry=voice_registry)
        if identity_errors:
            raise ProductionStoreError(
                "stored job identity snapshot failed revalidation: "
                + "; ".join(identity_errors))
    job["session_id"] = session.session_id
    job["job_hash"] = job_hash(job)
    errors = validate_job(job)
    if errors:
        raise ProductionStoreError(
            "resumed job failed validation: " + "; ".join(errors))
    return job
