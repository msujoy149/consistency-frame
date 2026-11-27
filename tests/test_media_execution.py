#!/usr/bin/env python3
"""Media execution state machine tests (CF-WO-P1-005, WO §3 + §8 + §11).

Covers: execution-record schema + record validation, deterministic
execution ids and idempotency keys, the PLANNED -> ... ->
SUCCEEDED/FAILED/CANCELLED/NEEDS_USER_ACTION/BLOCKED state machine
(including SUCCEEDED only from VALIDATING_OUTPUT with a validated
artifact, FAILED always carrying a failure classification, and
terminal records never transitioning), BLOCKED resume, retry as a
new attempt (old record linked via superseded_by, non-retryable
failures refused), submit/poll/verify through the execution
orchestrator with fake adapters (sync completion, async poll,
uncertain submission -> NEEDS_USER_ACTION and never an automatic
resubmit, hash mismatch -> FAILED), the authorization and identity
lock gates, the technical QC verdict rules, and the semantic QC
handoff (never auto-approved, never an automated reviewer).

Conventions follow tests/test_production_store.py: check(name, cond,
detail="") prints PASS/FAIL lines, failures are collected, and the
process exits 0 only when every check passes. No test here weakens
any P0 or P1 check.
"""

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(__file__), "..")
ROOT_ABS = os.path.abspath(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
from runtime import local_session  # noqa: E402
from runtime.local_session import (  # noqa: E402
    close_session, load_or_create_profile, start_session)
from runtime import media_execution as me  # noqa: E402
from runtime.media_execution import (  # noqa: E402
    MediaAdapter, MediaExecutionError, create_execution,
    execution_for_task, execution_id_for, execution_summary,
    resume_execution, retry_execution, transition_execution,
    validate_execution_artifact, validate_execution_failure,
    validate_execution_record)
from runtime import execution_orchestrator as eo  # noqa: E402
from runtime import production_orchestrator as po  # noqa: E402
from runtime import production_store as store  # noqa: E402
from runtime import task_compiler  # noqa: E402
from runtime.media_adapters import FFmpegAdapter  # noqa: E402

failures = []
_checks = [0]
_sessions = []


def check(name, cond, detail=""):
    _checks[0] += 1
    if cond:
        print(f"PASS {name}")
    else:
        print(f"FAIL {name} {detail}")
        failures.append(name)


def clone(value):
    return json.loads(json.dumps(value))


def fresh_session():
    root = tempfile.mkdtemp(prefix="cf-p1-005-test-")
    profile = load_or_create_profile(root)
    session = start_session(profile, profile.workspace_id)
    _sessions.append(session)
    return session


def packet_hash(packet):
    return hashlib.sha256(json.dumps(
        packet, sort_keys=True).encode("utf-8")).hexdigest()


def make_packet(task_id, task_type="media-technical"):
    packet = {
        "schema_version": "2.5",
        "packet_id": "pkt-" + task_id,
        "task_id": task_id,
        "task_type": task_type,
        "canonical_instruction": "probe the test media file",
        "provider_status": "handed-off",
    }
    packet["packet_hash"] = packet_hash(
        {k: v for k, v in packet.items() if k != "packet_hash"})
    return packet


def make_job(session, job_id="job-exec-001", packets=None,
             profile=None):
    job = po.create_production_job(
        session, job_id, "proj-test-001",
        profile or {"delivery_profile": "short-form-15-60s"})
    job["task_package"] = {
        "schema_version": "2.5",
        "package_id": "pkg-" + job_id,
        "job_id": job_id,
        "project_id": "proj-test-001",
        "packets": packets or [make_packet("task-exec-001")],
    }
    return job


def make_artifact(tmpdir, name="out.mp4", data=b"cf-test-media"):
    path = os.path.join(tmpdir, name)
    with open(path, "wb") as handle:
        handle.write(data)
    return {
        "path": name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "format": "mp4",
    }


def plan(session, job, packet, provider="provider-ffmpeg",
         adapter="adapter-ffmpeg"):
    record, job = create_execution(
        session, job, packet, provider, adapter,
        adapter_version="8.1.2")
    return record, job


def drive_ready(session, job, execution_id):
    record, job = transition_execution(
        session, job, execution_id, "WAITING_FOR_AUTHORIZATION",
        reason="planned")
    record, job = transition_execution(
        session, job, execution_id, "READY",
        reason="authorized")
    return record, job


class FakeSyncAdapter(MediaAdapter):
    """Fake adapter that completes synchronously with a fixed artifact."""

    adapter_id = "adapter-fake-sync"
    provider_id = "provider-fake-sync"
    adapter_version = "0.1"

    def __init__(self, artifact=None, failure=None):
        self.artifact = artifact
        self.failure = failure

    def capabilities(self):
        return {"operations": ["probe-media"],
                "task_types": ["media-technical"]}

    def submit(self, request, context):
        if self.failure is not None:
            return {"provider_job_id": None, "completed": False,
                    "output": None, "failure": self.failure}
        return {"provider_job_id": None, "completed": True,
                "output": copy.deepcopy(self.artifact),
                "failure": None}


class FakeAsyncAdapter(MediaAdapter):
    """Fake async adapter: accepts, then completes on the second poll."""

    adapter_id = "adapter-fake-async"
    provider_id = "provider-fake-async"
    adapter_version = "0.1"

    def __init__(self, artifact):
        self.artifact = artifact
        self.polls = 0

    def capabilities(self):
        return {"operations": ["generate-video"],
                "task_types": ["video-generation"]}

    def submit(self, request, context):
        return {"provider_job_id": "prov-job-001", "completed": False,
                "output": None, "failure": None}

    def poll(self, provider_job_id, context):
        self.polls += 1
        if self.polls < 2:
            return {"provider_job_id": provider_job_id,
                    "completed": False, "output": None,
                    "failure": None}
        return {"provider_job_id": provider_job_id, "completed": True,
                "output": copy.deepcopy(self.artifact),
                "failure": None}


class FakeUncertainAdapter(MediaAdapter):
    """Fake adapter whose submission result is unknown."""

    adapter_id = "adapter-fake-uncertain"
    provider_id = "provider-fake-uncertain"
    adapter_version = "0.1"
    submitted = 0

    def capabilities(self):
        return {"operations": ["generate-video"],
                "task_types": ["video-generation"]}

    def submit(self, request, context):
        FakeUncertainAdapter.submitted += 1
        raise MediaExecutionError(
            "network cut after the request was sent",
            code="submission-uncertain")


def expect_error(label, fn):
    try:
        fn()
    except (MediaExecutionError, eo.ExecutionOrchestratorError):
        check(label, True)
        return
    except Exception as exc:  # noqa: BLE001 - any other error is a fail
        check(label, False, f"raised {type(exc).__name__}: {exc}")
        return
    check(label, False, "operation succeeded instead of refusing")


def validation_group():
    """CF-P1-005-EXECUTION: record + failure + artifact validation."""
    valid = {
        "schema_version": "2.5",
        "execution_id": "exec-" + "a" * 24,
        "task_id": "task-exec-001",
        "packet_id": "pkt-task-exec-001",
        "job_id": "job-exec-001",
        "project_id": "proj-test-001",
        "provider_id": "provider-ffmpeg",
        "adapter_id": "adapter-ffmpeg",
        "adapter_version": "8.1.2",
        "state": "PLANNED",
        "attempt": 1,
        "idempotency_key": "b" * 64,
        "history": [{"state": "PLANNED", "reason": "planned"}],
    }
    check("CF-P1-005-EXECUTION-record-valid",
          validate_execution_record(valid) == [])
    bad = clone(valid)
    bad["state"] = "DONE"
    check("CF-P1-005-EXECUTION-record-bad-state",
          len(validate_execution_record(bad)) > 0)
    bad = clone(valid)
    bad["state"] = "SUCCEEDED"
    check("CF-P1-005-EXECUTION-succeeded-needs-output",
          len(validate_execution_record(bad)) > 0)
    bad = clone(valid)
    bad["state"] = "FAILED"
    check("CF-P1-005-EXECUTION-failed-needs-failure",
          len(validate_execution_record(bad)) > 0)
    bad = clone(valid)
    bad["idempotency_key"] = "not-hex"
    check("CF-P1-005-EXECUTION-bad-idempotency-key",
          len(validate_execution_record(bad)) > 0)
    bad = clone(valid)
    bad["execution_id"] = "job-exec-001"
    check("CF-P1-005-EXECUTION-bad-execution-id",
          len(validate_execution_record(bad)) > 0)
    bad = clone(valid)
    bad["history"] = []
    check("CF-P1-005-EXECUTION-empty-history",
          len(validate_execution_record(bad)) > 0)
    check("CF-P1-005-EXECUTION-failure-codes",
          all(validate_execution_failure(
              {"code": code, "message": "m", "retryable": True}) == []
              for code in me.FAILURE_CODES))
    check("CF-P1-005-EXECUTION-failure-unknown-code",
          len(validate_execution_failure(
              {"code": "no-such-code", "message": "m",
               "retryable": True})) > 0)
    check("CF-P1-005-EXECUTION-failure-missing-message",
          len(validate_execution_failure(
              {"code": "provider-error", "retryable": False})) > 0)
    check("CF-P1-005-EXECUTION-artifact-valid",
          validate_execution_artifact(
              {"path": "out.mp4", "sha256": "c" * 64, "bytes": 10,
               "format": "mp4"}) == [])
    check("CF-P1-005-EXECUTION-artifact-bad-sha",
          len(validate_execution_artifact(
              {"path": "out.mp4", "sha256": "zz", "bytes": 10,
               "format": "mp4"})) > 0)
    check("CF-P1-005-EXECUTION-artifact-absolute-path",
          len(validate_execution_artifact(
              {"path": "/tmp/out.mp4", "sha256": "c" * 64, "bytes": 10,
               "format": "mp4"})) > 0)
    # The new schema validates a real record.
    check("CF-P1-005-EXECUTION-schema-valid",
          task_compiler.schema_errors(
              "execution-record", valid, "execution-record") == [])
    bad_schema = clone(valid)
    bad_schema["state"] = "DONE"
    check("CF-P1-005-EXECUTION-schema-rejects-bad-state",
          len(task_compiler.schema_errors(
              "execution-record", bad_schema,
              "execution-record")) > 0)
    bad_schema = clone(valid)
    bad_schema["execution_id"] = "exec-short"
    check("CF-P1-005-EXECUTION-schema-rejects-short-id",
          len(task_compiler.schema_errors(
              "execution-record", bad_schema,
              "execution-record")) > 0)
    handoff = {
        "schema_version": "2.5",
        "handoff_id": "handoff-job-exec-001",
        "job_id": "job-exec-001",
        "project_id": "proj-test-001",
        "artifacts": [{"task_id": "task-exec-001",
                       "execution_id": "exec-" + "a" * 24,
                       "path": "out.mp4", "sha256": "c" * 64}],
        "checks_required": ["character continuity"],
        "reviewer": "human",
        "status": "awaiting-human-review",
    }
    check("CF-P1-005-EXECUTION-handoff-schema-valid",
          task_compiler.schema_errors(
              "human-review-handoff", handoff,
              "human-review-handoff") == [])


def state_machine_group():
    """CF-P1-005-EXECUTION: create, transitions, resume, retry."""
    session = fresh_session()
    tmpdir = tempfile.mkdtemp(prefix="cf-p1-005-exec-")
    artifact = make_artifact(tmpdir)
    packet = make_packet("task-exec-001")
    job = make_job(session, packets=[packet])

    record, job = plan(session, job, packet)
    check("CF-P1-005-EXECUTION-create-planned",
          record["state"] == "PLANNED")
    check("CF-P1-005-EXECUTION-id-deterministic",
          record["execution_id"] == execution_id_for(
              "job-exec-001", "task-exec-001", "provider-ffmpeg",
              packet["packet_hash"], 1))
    check("CF-P1-005-EXECUTION-key-length",
          len(record["idempotency_key"]) == 64)
    check("CF-P1-005-EXECUTION-attempt-2-differs",
          execution_id_for(
              "job-exec-001", "task-exec-001", "provider-ffmpeg",
              packet["packet_hash"], 2) != record["execution_id"])
    expect_error("CF-P1-005-EXECUTION-duplicate-attempt-refused",
                 lambda: create_execution(
                     session, job, packet, "provider-ffmpeg",
                     "adapter-ffmpeg", adapter_version="8.1.2"))
    expect_error("CF-P1-005-EXECUTION-unknown-packet-refused",
                 lambda: create_execution(
                     session, job, make_packet("task-nope-001"),
                     "provider-ffmpeg", "adapter-ffmpeg"))
    other = fresh_session()
    expect_error("CF-P1-005-EXECUTION-wrong-session-refused",
                 lambda: create_execution(
                     other, job, packet, "provider-ffmpeg",
                     "adapter-ffmpeg"))

    eid = record["execution_id"]
    expect_error("CF-P1-005-EXECUTION-planned-to-succeeded-refused",
                 lambda: transition_execution(
                     session, job, eid, "SUCCEEDED",
                     reason="skip", output=artifact))
    expect_error("CF-P1-005-EXECUTION-failed-needs-failure",
                 lambda: transition_execution(
                     session, job, eid, "FAILED",
                     reason="no failure given"))
    expect_error("CF-P1-005-EXECUTION-empty-reason-refused",
                 lambda: transition_execution(
                     session, job, eid, "WAITING_FOR_AUTHORIZATION",
                     reason=""))

    record, job = drive_ready(session, job, eid)
    check("CF-P1-005-EXECUTION-ready", record["state"] == "READY")
    record, job = transition_execution(
        session, job, eid, "BLOCKED", reason="operator paused")
    check("CF-P1-005-EXECUTION-blocked-remembers-previous",
          record["state"] == "BLOCKED"
          and record["previous_state"] == "READY")
    record, job = resume_execution(session, job, eid)
    check("CF-P1-005-EXECUTION-resume-returns-previous",
          record["state"] == "READY"
          and "previous_state" not in record)
    expect_error("CF-P1-005-EXECUTION-resume-non-blocked-refused",
                 lambda: resume_execution(session, job, eid))

    record, job = transition_execution(
        session, job, eid, "SUBMITTED", reason="submit")
    record, job = transition_execution(
        session, job, eid, "RUNNING", reason="running")
    record, job = transition_execution(
        session, job, eid, "RETRIEVING", reason="retrieving")
    record, job = transition_execution(
        session, job, eid, "VALIDATING_OUTPUT",
        reason="verifying", output=artifact)
    check("CF-P1-005-EXECUTION-validating-output",
          record["state"] == "VALIDATING_OUTPUT"
          and record["output"]["sha256"] == artifact["sha256"])
    expect_error("CF-P1-005-EXECUTION-validating-to-cancelled-refused",
                 lambda: transition_execution(
                     session, job, eid, "CANCELLED",
                     reason="too late"))
    record, job = transition_execution(
        session, job, eid, "SUCCEEDED",
        reason="verified", output=artifact)
    check("CF-P1-005-EXECUTION-succeeded",
          record["state"] == "SUCCEEDED")
    check("CF-P1-005-EXECUTION-history-order",
          [h["state"] for h in record["history"]] == [
              "PLANNED", "WAITING_FOR_AUTHORIZATION", "READY",
              "BLOCKED", "READY", "SUBMITTED", "RUNNING",
              "RETRIEVING", "VALIDATING_OUTPUT", "SUCCEEDED"])
    expect_error("CF-P1-005-EXECUTION-terminal-refused",
                 lambda: transition_execution(
                     session, job, eid, "FAILED",
                     reason="too late",
                     failure={"code": "provider-error", "message": "x",
                              "retryable": False}))

    # Failed execution: retryable retries as a new attempt.
    packet2 = make_packet("task-exec-002")
    job2 = make_job(session, job_id="job-exec-002", packets=[packet2])
    record2, job2 = plan(session, job2, packet2)
    eid2 = record2["execution_id"]
    record2, job2 = transition_execution(
        session, job2, eid2, "FAILED", reason="provider timed out",
        failure={"code": "provider-timeout", "message": "timed out",
                 "retryable": True})
    new_record, job2 = retry_execution(session, job2, eid2)
    check("CF-P1-005-EXECUTION-retry-new-attempt",
          new_record["attempt"] == 2
          and new_record["execution_id"] != eid2
          and new_record["state"] == "PLANNED")
    old = next(r for r in job2["executions"]
               if r["execution_id"] == eid2)
    check("CF-P1-005-EXECUTION-retry-links-old",
          old.get("superseded_by") == new_record["execution_id"])
    expect_error("CF-P1-005-EXECUTION-retry-planned-refused",
                 lambda: retry_execution(
                     session, job2, new_record["execution_id"]))
    # Non-retryable failure refuses a retry.
    packet3 = make_packet("task-exec-003")
    job3 = make_job(session, job_id="job-exec-003", packets=[packet3])
    record3, job3 = plan(session, job3, packet3)
    eid3 = record3["execution_id"]
    record3, job3 = transition_execution(
        session, job3, eid3, "FAILED", reason="denied",
        failure={"code": "authorization-denied", "message": "denied",
                 "retryable": False})
    expect_error("CF-P1-005-EXECUTION-retry-nonretryable-refused",
                 lambda: retry_execution(session, job3, eid3))
    # NEEDS_USER_ACTION retries after the blocker is resolved.
    packet4 = make_packet("task-exec-004")
    job4 = make_job(session, job_id="job-exec-004", packets=[packet4])
    record4, job4 = plan(session, job4, packet4)
    eid4 = record4["execution_id"]
    record4, job4 = transition_execution(
        session, job4, eid4, "NEEDS_USER_ACTION",
        reason="user must decide")
    new4, job4 = retry_execution(session, job4, eid4)
    check("CF-P1-005-EXECUTION-retry-needs-user-action",
          new4["attempt"] == 2)

    summary = execution_summary(job)
    check("CF-P1-005-EXECUTION-summary-counts",
          summary["SUCCEEDED"] == 1 and summary["PLANNED"] == 0)
    check("CF-P1-005-EXECUTION-for-task",
          len(execution_for_task(job, "task-exec-001")) == 1
          and execution_for_task(job, "task-nope-001") == [])


def orchestrator_group():
    """CF-P1-005-EXECUTION: submit/poll/verify, authz + identity lock."""
    session = fresh_session()
    tmpdir = tempfile.mkdtemp(prefix="cf-p1-005-orch-")
    artifact = make_artifact(tmpdir)
    packet = make_packet("task-exec-001")
    job = make_job(session, packets=[packet])
    record, job = plan(session, job, packet)
    eid = record["execution_id"]
    record, job = drive_ready(session, job, eid)

    # Sync adapter: READY -> ... -> VALIDATING_OUTPUT, then verify.
    adapter = FakeSyncAdapter(artifact=artifact)
    record, job = eo.submit_execution(
        session, job, eid, adapter,
        {"provider_id": "provider-fake-sync"}, context={})
    check("CF-P1-005-EXECUTION-sync-to-validating",
          record["state"] == "VALIDATING_OUTPUT")
    record, job = eo.verify_execution_output(
        session, job, eid, delivery_root=tmpdir)
    check("CF-P1-005-EXECUTION-verify-succeeds",
          record["state"] == "SUCCEEDED")
    compat = [r for r in job.get("execution_results") or []
              if r.get("task_id") == "task-exec-001"]
    # The compat mirror is written by the pipeline driver, not by
    # verify_execution_output itself.
    check("CF-P1-005-EXECUTION-verify-no-compat-yet", compat == [])

    # Hash mismatch -> FAILED with code hash-mismatch.
    packet2 = make_packet("task-exec-002")
    job2 = make_job(session, job_id="job-exec-002", packets=[packet2])
    record2, job2 = plan(session, job2, packet2)
    eid2 = record2["execution_id"]
    record2, job2 = drive_ready(session, job2, eid2)
    bad_artifact = dict(artifact)
    bad_artifact["sha256"] = "0" * 64
    record2, job2 = eo.submit_execution(
        session, job2, eid2, FakeSyncAdapter(artifact=bad_artifact),
        {"provider_id": "provider-fake-sync"}, context={})
    record2, job2 = eo.verify_execution_output(
        session, job2, eid2, delivery_root=tmpdir)
    check("CF-P1-005-EXECUTION-hash-mismatch-failed",
          record2["state"] == "FAILED"
          and record2["failure"]["code"] == "hash-mismatch"
          and record2["failure"]["retryable"] is True)

    # Async adapter: RUNNING, poll stays, poll completes.
    packet3 = make_packet("task-exec-003", task_type="video-generation")
    job3 = make_job(session, job_id="job-exec-003", packets=[packet3])
    record3, job3 = plan(session, job3, packet3,
                         provider="provider-fake-async",
                         adapter="adapter-fake-async")
    eid3 = record3["execution_id"]
    record3, job3 = drive_ready(session, job3, eid3)
    async_adapter = FakeAsyncAdapter(artifact)
    record3, job3 = eo.submit_execution(
        session, job3, eid3, async_adapter,
        {"provider_id": "provider-fake-async"}, context={})
    check("CF-P1-005-EXECUTION-async-running",
          record3["state"] == "RUNNING"
          and record3["provider_job_id"] == "prov-job-001")
    record3, job3 = eo.poll_execution(
        session, job3, eid3, async_adapter, context={})
    check("CF-P1-005-EXECUTION-async-still-running",
          record3["state"] == "RUNNING")
    record3, job3 = eo.poll_execution(
        session, job3, eid3, async_adapter, context={})
    check("CF-P1-005-EXECUTION-async-completes",
          record3["state"] == "VALIDATING_OUTPUT")
    record3, job3 = eo.verify_execution_output(
        session, job3, eid3, delivery_root=tmpdir)
    check("CF-P1-005-EXECUTION-async-succeeds",
          record3["state"] == "SUCCEEDED")

    # Uncertain submission -> NEEDS_USER_ACTION, never auto-resubmit.
    FakeUncertainAdapter.submitted = 0
    packet4 = make_packet("task-exec-004", task_type="video-generation")
    job4 = make_job(session, job_id="job-exec-004", packets=[packet4])
    record4, job4 = plan(session, job4, packet4,
                         provider="provider-fake-uncertain",
                         adapter="adapter-fake-uncertain")
    eid4 = record4["execution_id"]
    record4, job4 = drive_ready(session, job4, eid4)
    record4, job4 = eo.submit_execution(
        session, job4, eid4, FakeUncertainAdapter(),
        {"provider_id": "provider-fake-uncertain"}, context={})
    check("CF-P1-005-EXECUTION-uncertain-needs-user-action",
          record4["state"] == "NEEDS_USER_ACTION"
          and FakeUncertainAdapter.submitted == 1)

    # Adapter-reported failure -> FAILED with its classification.
    packet5 = make_packet("task-exec-005")
    job5 = make_job(session, job_id="job-exec-005", packets=[packet5])
    record5, job5 = plan(session, job5, packet5)
    eid5 = record5["execution_id"]
    record5, job5 = drive_ready(session, job5, eid5)
    record5, job5 = eo.submit_execution(
        session, job5, eid5,
        FakeSyncAdapter(failure={"code": "provider-error",
                                 "message": "provider 500",
                                 "retryable": False}),
        {"provider_id": "provider-fake-sync"}, context={})
    check("CF-P1-005-EXECUTION-adapter-failure-classified",
          record5["state"] == "FAILED"
          and record5["failure"]["code"] == "provider-error"
          and record5["failure"]["retryable"] is False)

    # Authorization: nothing is authorized implicitly.
    package = job["task_package"]
    packet_auth = clone(packet)
    packet_auth["authorization_required"] = {
        "required": True, "action": "execute"}
    package_auth = dict(package)
    package_auth["packets"] = [packet_auth]
    authz = eo.check_execution_authorizations(
        session, job, package_auth, {})
    check("CF-P1-005-EXECUTION-authz-required-blocks",
          authz["task-exec-001"]["authorized"] is False)
    authz = eo.check_execution_authorizations(
        session, job, package_auth, {"task-exec-001": True})
    check("CF-P1-005-EXECUTION-authz-explicit-allows",
          authz["task-exec-001"]["authorized"] is True)
    authz = eo.check_execution_authorizations(
        session, job, package, {})
    check("CF-P1-005-EXECUTION-authz-not-required-allows",
          authz["task-exec-001"]["authorized"] is True)

    # Identity lock: a packet binding an unknown character blocks.
    snapshot = {"characters": [
        {"character_id": "char-001", "voice_profiles": []}]}
    bad_packet = clone(packet)
    bad_packet["identity_bindings"] = [
        {"character_id": "char-unknown-001"}]
    check("CF-P1-005-EXECUTION-identity-lock-mismatch",
          len(eo.bindings_match_snapshot(bad_packet, snapshot)) > 0)
    good_packet = clone(packet)
    good_packet["identity_bindings"] = [
        {"character_id": "char-001"}]
    check("CF-P1-005-EXECUTION-identity-lock-match",
          eo.bindings_match_snapshot(good_packet, snapshot) == [])
    check("CF-P1-005-EXECUTION-identity-lock-no-snapshot",
          eo.bindings_match_snapshot(bad_packet, None) == [])


def pipeline_group():
    """CF-P1-005-EXECUTION: end-to-end pipeline (short/long/failed
    + persistent recovery). Real FFmpeg execution; skipped where
    ffmpeg/ffprobe are absent (no conformance claimed there)."""
    if shutil.which("ffmpeg") is None \
            or shutil.which("ffprobe") is None:
        print("SKIP CF-P1-005-EXECUTION-pipeline: ffmpeg/ffprobe not "
              "installed; no conformance claimed")
        return
    profile_root = tempfile.mkdtemp(prefix="cf-p1-005-pipe-profile-")
    profile = load_or_create_profile(profile_root)
    session = start_session(profile, profile.workspace_id)
    _sessions.append(session)
    tmpdir = tempfile.mkdtemp(prefix="cf-p1-005-pipe-")
    workspace = os.path.join(tmpdir, "workspace")
    os.makedirs(workspace)
    src = os.path.join(workspace, "src.mp4")
    proc = subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi", "-i",
         "testsrc=duration=2:size=320x240:rate=24",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-shortest", src],
        capture_output=True, text=True, timeout=120)
    check("CF-P1-005-EXECUTION-pipe-source-generated",
          proc.returncode == 0 and os.path.isfile(src))
    if proc.returncode != 0:
        return
    adapter = FFmpegAdapter(workspace_root=workspace)

    def transcode_op(task_id, out, size="160x120"):
        return {"ffmpeg_operations": {
            task_id: {"operation": "transcode", "inputs": ["src.mp4"],
                      "output": out, "options": {"size": size}}}}

    # Short form: one media-technical task, end to end.
    packet = make_packet("task-pipe-short-001")
    job = make_job(session, job_id="job-pipe-short-001",
                   packets=[packet])
    job["state"] = "TEST_READY"
    job, report = eo.run_execution_pipeline(
        session, job, adapters={"provider-ffmpeg": adapter},
        authorizations={}, context=transcode_op(
            "task-pipe-short-001", "out-short.mp4"),
        delivery_root=workspace, ffmpeg_adapter=adapter)
    check("CF-P1-005-EXECUTION-pipe-short-succeeded",
          report["outcomes"].get("task-pipe-short-001", {}).get(
              "outcome") == "succeeded",
          str(report["outcomes"]))
    check("CF-P1-005-EXECUTION-pipe-short-manifest",
          report.get("manifest") is not None
          and len((report["manifest"]["tracks"][0]["clips"])) == 1)
    check("CF-P1-005-EXECUTION-pipe-short-qc",
          report["qc_report"]["verdict"] == "pass")
    check("CF-P1-005-EXECUTION-pipe-short-handoff",
          report["semantic_qc_handoff"]["status"]
          == "awaiting-human-review"
          and len(report["semantic_qc_handoff"]["artifacts"]) == 1)
    check("CF-P1-005-EXECUTION-pipe-short-compat",
          [r for r in job.get("execution_results") or []
           if r.get("task_id") == "task-pipe-short-001"
           and r.get("outcome") == "succeeded"] != [])
    check("CF-P1-005-EXECUTION-pipe-short-summary",
          eo.execution_summary(job)["SUCCEEDED"] == 1)

    # Long form: three tasks in one pipeline run.
    packets = [make_packet(f"task-pipe-long-00{i}")
               for i in (1, 2, 3)]
    long_job = make_job(
        session, job_id="job-pipe-long-001", packets=packets,
        profile={"delivery_profile": "long-form"})
    long_job["state"] = "BATCH_PRODUCTION"
    ops = {"ffmpeg_operations": {
        f"task-pipe-long-00{i}": {
            "operation": "transcode", "inputs": ["src.mp4"],
            "output": f"out-long-00{i}.mp4",
            "options": {"size": "160x120"}}
        for i in (1, 2, 3)}}
    long_job, long_report = eo.run_execution_pipeline(
        session, long_job, adapters={"provider-ffmpeg": adapter},
        authorizations={}, context=ops,
        delivery_root=workspace, ffmpeg_adapter=adapter)
    check("CF-P1-005-EXECUTION-pipe-long-all-succeeded",
          all(long_report["outcomes"].get(
              f"task-pipe-long-00{i}", {}).get("outcome") == "succeeded"
              for i in (1, 2, 3)),
          str(long_report["outcomes"]))
    check("CF-P1-005-EXECUTION-pipe-long-manifest",
          long_report.get("manifest") is not None
          and len(long_report["manifest"]["tracks"][0]["clips"]) == 3)
    check("CF-P1-005-EXECUTION-pipe-long-qc",
          long_report["qc_report"]["verdict"] == "pass")

    # Failed execution: one bad input must not abort the other task.
    good = make_packet("task-pipe-mix-good-001")
    bad = make_packet("task-pipe-mix-bad-001")
    mix_job = make_job(session, job_id="job-pipe-mix-001",
                       packets=[good, bad])
    mix_job["state"] = "TEST_READY"
    mix_ops = {"ffmpeg_operations": {
        "task-pipe-mix-good-001": {
            "operation": "transcode", "inputs": ["src.mp4"],
            "output": "out-mix-good.mp4",
            "options": {"size": "160x120"}},
        "task-pipe-mix-bad-001": {
            "operation": "transcode", "inputs": ["no-such-file.mp4"],
            "output": "out-mix-bad.mp4", "options": {}}}}
    mix_job, mix_report = eo.run_execution_pipeline(
        session, mix_job, adapters={"provider-ffmpeg": adapter},
        authorizations={}, context=mix_ops,
        delivery_root=workspace, ffmpeg_adapter=adapter)
    check("CF-P1-005-EXECUTION-pipe-mix-good-succeeds",
          mix_report["outcomes"].get(
              "task-pipe-mix-good-001", {}).get("outcome")
          == "succeeded")
    check("CF-P1-005-EXECUTION-pipe-mix-bad-fails",
          mix_report["outcomes"].get(
              "task-pipe-mix-bad-001", {}).get("outcome") == "failed")
    check("CF-P1-005-EXECUTION-pipe-mix-manifest-partial",
          mix_report.get("manifest") is not None
          and len(mix_report["manifest"]["tracks"][0]["clips"]) == 1)
    failed_executions = [r for r in mix_job.get("executions") or []
                         if r.get("task_id") == "task-pipe-mix-bad-001"]
    check("CF-P1-005-EXECUTION-pipe-mix-failure-classified",
          len(failed_executions) == 1
          and failed_executions[0]["state"] == "FAILED"
          and failed_executions[0]["failure"]["code"]
          == "local-tool-error")

    # Persistent recovery: the executed job survives a store
    # round trip and resumes under a NEW session (same profile).
    store_root = os.path.join(tmpdir, "store")
    os.makedirs(store_root)
    store.save_production_job(session, store_root, job)
    session2 = start_session(
        load_or_create_profile(profile_root), profile.workspace_id)
    _sessions.append(session2)
    resumed = store.resume_production_job(
        session2, store_root, "job-pipe-short-001", "proj-test-001")
    check("CF-P1-005-EXECUTION-pipe-resume-rebinds",
          resumed.get("session_id") == session2.session_id
          and resumed.get("state") == "TEST_READY")
    check("CF-P1-005-EXECUTION-pipe-resume-executions",
          len(resumed.get("executions") or []) == 1
          and resumed["executions"][0]["state"] == "SUCCEEDED")
    check("CF-P1-005-EXECUTION-pipe-resume-results",
          len(resumed.get("execution_results") or []) == 1)


def qc_group():
    """CF-P1-005-EXECUTION: technical QC + semantic handoff + G6."""
    session = fresh_session()
    tmpdir = tempfile.mkdtemp(prefix="cf-p1-005-qc-")
    artifact = make_artifact(tmpdir)
    packet = make_packet("task-exec-001")
    job = make_job(session, packets=[packet])
    record, job = plan(session, job, packet)
    eid = record["execution_id"]
    record, job = drive_ready(session, job, eid)
    record, job = eo.submit_execution(
        session, job, eid, FakeSyncAdapter(artifact=artifact),
        {"provider_id": "provider-fake-sync"}, context={})
    record, job = eo.verify_execution_output(
        session, job, eid, delivery_root=tmpdir)
    executions = job.get("executions") or []

    qc = eo.run_technical_qc(session, job, executions,
                             delivery_root=tmpdir)
    check("CF-P1-005-EXECUTION-qc-pass-no-adapter",
          qc["verdict"] == "pass"
          and all(c["passed"] for c in qc["checks"]))
    # A SUCCEEDED record with no output path is a Critical defect.
    broken = clone(record)
    broken["output"] = {}
    qc2 = eo.run_technical_qc(session, job, [broken],
                              delivery_root=tmpdir)
    check("CF-P1-005-EXECUTION-qc-critical-no-path",
          qc2["verdict"] == "fail"
          and any(d["severity"] == "Critical"
                  for d in qc2["defects"]))

    handoff = eo.prepare_semantic_qc_handoff(session, job, executions)
    check("CF-P1-005-EXECUTION-handoff-awaiting-human",
          handoff["status"] == "awaiting-human-review"
          and handoff["reviewer"] == "human"
          and "decision" not in handoff
          and len(handoff["artifacts"]) == 1)
    expect_error("CF-P1-005-EXECUTION-handoff-automated-refused",
                 lambda: eo.resolve_semantic_qc_handoff(
                     handoff, decision="approved",
                     reviewer="automated"))
    resolved = eo.resolve_semantic_qc_handoff(
        handoff, decision="approved", reviewer="sujoy-mondal",
        note="face matches the reference")
    check("CF-P1-005-EXECUTION-handoff-human-approves",
          resolved["status"] == "approved"
          and resolved["reviewer"] == "sujoy-mondal")

    # G6 evidence: technical pass + approved handoff + manifest.
    manifest = {"schema_version": "2.5", "id": "timeline-job-exec-001",
                "project_id": "proj-test-001",
                "format": "editor_neutral_v1",
                "resolution": {"width": 1920, "height": 1080},
                "tracks": [{"track_id": "track-video-1", "kind": "video",
                            "clips": [{"clip_id": "clip-task-exec-001",
                                       "media": {
                                           "path": "out.mp4",
                                           "media_type": "mp4",
                                           "sha256": artifact["sha256"]}}]}]}
    errors = eo.evaluate_delivery_gate(
        session, job, manifest, qc, resolved)
    check("CF-P1-005-EXECUTION-g6-evidence-complete", errors == [])
    errors = eo.evaluate_delivery_gate(
        session, job, manifest, qc, handoff)
    check("CF-P1-005-EXECUTION-g6-unapproved-handoff-blocks",
          any("semantic QC" in e for e in errors))
    errors = eo.evaluate_delivery_gate(
        session, job, manifest, qc2, resolved)
    check("CF-P1-005-EXECUTION-g6-failed-qc-blocks",
          any("technical QC" in e for e in errors))
    errors = eo.evaluate_delivery_gate(
        session, job, None, qc, resolved)
    check("CF-P1-005-EXECUTION-g6-no-manifest-blocks",
          any("manifest" in e for e in errors))


def main():
    try:
        validation_group()
        state_machine_group()
        orchestrator_group()
        pipeline_group()
        qc_group()
    finally:
        for session in _sessions:
            try:
                close_session(session)
            except Exception:  # noqa: BLE001 - best-effort cleanup
                pass
    print(f"--- CF-P1-005-EXECUTION: {_checks[0]} checks, "
          f"{len(failures)} failures ---")
    if failures:
        print("FAILURES: " + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
