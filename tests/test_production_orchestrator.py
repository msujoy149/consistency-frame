#!/usr/bin/env python3
"""Production orchestrator tests (CF-WO-P1-004).

Covers: job creation; the full happy-path lifecycle
(INTAKE -> ... -> DELIVERED) with job validity at every step;
invalid transitions; gate order and waiver rules; BLOCKED and
resume; session enforcement; build_production_bundle
refusals; character resolution; execution-result recording;
provider-task compile guards; QC correction tasks;
determinism and input immutability; and the no-false-execution
rule (a compiled packet never claims execution).

Conventions follow tests/test_script_to_performance_runtime.py:
check(name, cond, detail="") prints PASS/FAIL lines, failures
are collected, and the process exits 0 only when every check
passes. No test here weakens any P0 or P1 check.
"""

import copy
import hashlib
import json
import os
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(__file__), "..")
ROOT_ABS = os.path.abspath(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import test_script_to_performance_runtime as T  # noqa: E402
from runtime import local_session  # noqa: E402
from runtime.local_session import (  # noqa: E402
    close_session, is_active_session, load_or_create_profile,
    start_session)
from runtime.production_orchestrator import (  # noqa: E402
    ProductionOrchestratorError, create_production_job,
    build_production_bundle, build_qc_correction_tasks,
    compile_provider_tasks, evaluate_production_gate, job_hash,
    record_execution_result, resolve_character, transition_job,
    validate_format_profile, validate_gate_state, validate_job)

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


def digest(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True).encode("utf-8")).hexdigest()


def fresh_session():
    root = tempfile.mkdtemp(prefix="cf-p1-004-test-")
    profile = load_or_create_profile(root)
    session = start_session(profile, profile.workspace_id)
    _sessions.append(session)
    return session


def load_fixture(name):
    with open(os.path.join(
            ROOT, "tests", "fixtures", name), encoding="utf-8") as f:
        return json.load(f)


def short_analysis():
    return load_fixture("production-analysis-short.json")


def expect_error(label, fn):
    """fn must raise ProductionOrchestratorError; anything else
    (including success) fails the check."""
    try:
        fn()
    except ProductionOrchestratorError as exc:
        check(label, True)
        return exc.errors
    except Exception as exc:  # noqa: BLE001 - the test asserts no raise
        check(label, False, f"raised {type(exc).__name__}: {exc}")
        return []
    check(label, False, "operation succeeded instead of refusing")
    return []


def format_profile():
    return {"delivery_profile": "short-form-15-60s"}


def new_job(session, job_id="job-short-001", profile=None, **kwargs):
    return create_production_job(
        session, job_id, "proj-test-001",
        profile if profile is not None else format_profile(), **kwargs)


def analyzing_job(session, job_id="job-short-001", **kwargs):
    job = new_job(session, job_id, **kwargs)
    return transition_job(session, job, "ANALYZING")


def build_bundle(session, job, analysis=None, bundle_id="bundle-short-001",
                 authorised=False):
    plan = T.fresh_routing_plan(session)
    return build_production_bundle(
        session, job, plan, T.script(), T.profile(), T.draft(),
        analysis if analysis is not None else short_analysis(),
        bundle_id, authorised)


def gate_status(job, gate_id):
    for gate in job["gate_state"]["gates"]:
        if gate["gate_id"] == gate_id:
            return gate["status"]
    return None


def valid_job(label, job):
    check(label, validate_job(job) == []
          and job_hash(job) == job["job_hash"],
          f"errors={validate_job(job)}")


# ---------------------------------------------------------------------------
# CF-P1-004-ORCHESTRATOR: job creation
# ---------------------------------------------------------------------------

def _creation_group():
    session = fresh_session()
    job = new_job(session)
    check("CF-P1-004-ORCHESTRATOR: valid job creation starts in "
          "INTAKE",
          job["state"] == "INTAKE"
          and job["job_id"] == "job-short-001"
          and job["project_id"] == "proj-test-001"
          and job["session_id"] == session.session_id
          and job["previous_state"] is None
          and job["commercial_use"] is False
          and job["stills_first"] is False
          and job["task_package"] is None
          and job["execution_results"] == []
          and job["qc_reports"] == []
          and job["correction_round"] == 0)
    check("CF-P1-004-ORCHESTRATOR: a new job has all six gates "
          "NOT_STARTED in order",
          [g["gate_id"] for g in job["gate_state"]["gates"]] == [
              "G1", "G2", "G3", "G4", "G5", "G6"]
          and all(g["status"] == "NOT_STARTED"
                  for g in job["gate_state"]["gates"]))
    valid_job("CF-P1-004-ORCHESTRATOR: a new job validates and its "
              "hash recomputes", job)
    check("CF-P1-004-ORCHESTRATOR: validate_gate_state accepts the "
          "fresh gate state",
          validate_gate_state(job["gate_state"]) == [])

    for bad_id in ("", "Bad_ID", "j", None, 42, "job with spaces"):
        expect_error(
            f"CF-P1-004-ORCHESTRATOR: bad job_id {bad_id!r} fails",
            lambda bad_id=bad_id: create_production_job(
                session, bad_id, "proj-test-001", format_profile()))
    expect_error(
        "CF-P1-004-ORCHESTRATOR: bad project_id fails",
        lambda: create_production_job(
            session, "job-bad-001", "Bad_Project", format_profile()))
    for bad_profile in (
            {"delivery_profile": "no-such-profile"},
            {"delivery_profile": "short-form-15-60s",
             "duration_target_seconds": 0},
            {"delivery_profile": "short-form-15-60s",
             "duration_target_seconds": -5},
            {"delivery_profile": "short-form-15-60s",
             "duration_target_seconds": "45"},
            {"delivery_profile": "short-form-15-60s",
             "surprise": True},
            {"delivery_profile": "short-form-15-60s",
             "chapters": [{"chapter_id": "ch-01", "title": "A"},
                          {"chapter_id": "ch-01", "title": "B"}]},
            "not-a-profile",
            None):
        expect_error(
            "CF-P1-004-ORCHESTRATOR: bad format_profile "
            f"{bad_profile!r} fails",
            lambda bad_profile=bad_profile: create_production_job(
                session, "job-bad-001", "proj-test-001", bad_profile))
    check("CF-P1-004-ORCHESTRATOR: validate_format_profile accepts "
          "a valid profile",
          validate_format_profile(format_profile()) == [])
    check("CF-P1-004-ORCHESTRATOR: validate_format_profile rejects "
          "an unknown delivery profile",
          validate_format_profile(
              {"delivery_profile": "nope"}) != [])
    for bad_flag in ("true", 1, None):
        expect_error(
            "CF-P1-004-ORCHESTRATOR: non-bool commercial_use "
            f"{bad_flag!r} fails",
            lambda bad_flag=bad_flag: create_production_job(
                session, "job-bad-001", "proj-test-001",
                format_profile(), commercial_use=bad_flag))
        expect_error(
            "CF-P1-004-ORCHESTRATOR: non-bool stills_first "
            f"{bad_flag!r} fails",
            lambda bad_flag=bad_flag: create_production_job(
                session, "job-bad-001", "proj-test-001",
                format_profile(), stills_first=bad_flag))
    commercial = new_job(session, "job-commercial-001",
                         commercial_use=True, stills_first=True)
    check("CF-P1-004-ORCHESTRATOR: commercial_use and stills_first "
          "flags are recorded when True",
          commercial["commercial_use"] is True
          and commercial["stills_first"] is True)


# ---------------------------------------------------------------------------
# CF-P1-004-ORCHESTRATOR: full happy-path lifecycle
# ---------------------------------------------------------------------------

def _lifecycle_group():
    session = fresh_session()
    job = analyzing_job(session)
    bundle, job = build_bundle(session, job)
    check("CF-P1-004-ORCHESTRATOR: build_production_bundle moves "
          "the job to PLAN_READY",
          job["state"] == "PLAN_READY"
          and job["s2p_bundle_id"] == "bundle-short-001"
          and job["analysis_id"] == "analysis-short-001"
          and job["analysis_hash"] == bundle["analysis_hash"])
    valid_job("CF-P1-004-ORCHESTRATOR: PLAN_READY job validates",
              job)
    check("CF-P1-004-ORCHESTRATOR: production bundle carries the "
          "analysis hash and a bundle hash",
          bundle["bundle_id"] == "bundle-short-001"
          and bundle["job_id"] == "job-short-001"
          and isinstance(bundle["bundle_hash"], str)
          and len(bundle["bundle_hash"]) == 64)

    job = transition_job(session, job, "AWAITING_G1_APPROVAL")
    check("CF-P1-004-ORCHESTRATOR: PLAN_READY -> "
          "AWAITING_G1_APPROVAL", job["state"] == "AWAITING_G1_APPROVAL")
    valid_job("CF-P1-004-ORCHESTRATOR: AWAITING_G1_APPROVAL job "
              "validates", job)
    job = evaluate_production_gate(session, job, "G1", "PASS",
                                   note="Visual plan approved.")
    check("CF-P1-004-ORCHESTRATOR: G1 PASS advances to TEST_READY",
          job["state"] == "TEST_READY"
          and gate_status(job, "G1") == "PASS")
    valid_job("CF-P1-004-ORCHESTRATOR: TEST_READY job validates", job)

    job = transition_job(session, job, "AWAITING_G2_APPROVAL")
    check("CF-P1-004-ORCHESTRATOR: TEST_READY -> "
          "AWAITING_G2_APPROVAL",
          job["state"] == "AWAITING_G2_APPROVAL")
    job = evaluate_production_gate(session, job, "G2", "PASS",
                                   note="Test shots approved.")
    check("CF-P1-004-ORCHESTRATOR: G2 PASS advances to "
          "BATCH_PRODUCTION",
          job["state"] == "BATCH_PRODUCTION"
          and gate_status(job, "G2") == "PASS")
    valid_job("CF-P1-004-ORCHESTRATOR: BATCH_PRODUCTION job "
              "validates", job)

    job = transition_job(session, job, "EDITORIAL_REVIEW")
    check("CF-P1-004-ORCHESTRATOR: BATCH_PRODUCTION -> "
          "EDITORIAL_REVIEW",
          job["state"] == "EDITORIAL_REVIEW")
    job = evaluate_production_gate(session, job, "G3", "PASS")
    check("CF-P1-004-ORCHESTRATOR: G3 PASS records without moving "
          "the job (transition advances it)",
          job["state"] == "EDITORIAL_REVIEW"
          and gate_status(job, "G3") == "PASS")
    job = transition_job(session, job, "PICTURE_LOCK")
    check("CF-P1-004-ORCHESTRATOR: EDITORIAL_REVIEW -> PICTURE_LOCK "
          "once G3 passes",
          job["state"] == "PICTURE_LOCK")
    valid_job("CF-P1-004-ORCHESTRATOR: PICTURE_LOCK job validates",
              job)

    job = evaluate_production_gate(session, job, "G4", "PASS")
    job = transition_job(session, job, "FINISHING")
    check("CF-P1-004-ORCHESTRATOR: PICTURE_LOCK -> FINISHING once "
          "G4 passes", job["state"] == "FINISHING")
    job = evaluate_production_gate(session, job, "G5", "PASS")
    job = transition_job(session, job, "FINAL_QC")
    check("CF-P1-004-ORCHESTRATOR: FINISHING -> FINAL_QC once G5 "
          "passes", job["state"] == "FINAL_QC")
    valid_job("CF-P1-004-ORCHESTRATOR: FINAL_QC job validates", job)

    job = evaluate_production_gate(session, job, "G6", "PASS")
    job = transition_job(session, job, "DELIVERED")
    check("CF-P1-004-ORCHESTRATOR: FINAL_QC -> DELIVERED once G6 "
          "passes",
          job["state"] == "DELIVERED"
          and all(gate_status(job, g) == "PASS"
                  for g in ("G1", "G2", "G3", "G4", "G5", "G6")))
    valid_job("CF-P1-004-ORCHESTRATOR: DELIVERED job validates", job)
    return session, job, bundle


# ---------------------------------------------------------------------------
# CF-P1-004-ORCHESTRATOR: invalid transitions
# ---------------------------------------------------------------------------

def _invalid_transitions_group(delivered):
    session, job, _bundle = delivered
    expect_error(
        "CF-P1-004-ORCHESTRATOR: DELIVERED -> INTAKE fails",
        lambda: transition_job(session, job, "INTAKE"))
    expect_error(
        "CF-P1-004-ORCHESTRATOR: DELIVERED -> FINAL_QC fails",
        lambda: transition_job(session, job, "FINAL_QC"))

    fresh = fresh_session()
    intake = new_job(fresh, "job-inv-001")
    expect_error(
        "CF-P1-004-ORCHESTRATOR: INTAKE -> PLAN_READY fails "
        "(PLAN_READY only via build_production_bundle)",
        lambda: transition_job(fresh, intake, "PLAN_READY"))
    expect_error(
        "CF-P1-004-ORCHESTRATOR: INTAKE -> DELIVERED fails",
        lambda: transition_job(fresh, intake, "DELIVERED"))
    expect_error(
        "CF-P1-004-ORCHESTRATOR: INTAKE -> INTAKE fails (already "
        "in state)",
        lambda: transition_job(fresh, intake, "INTAKE"))
    expect_error(
        "CF-P1-004-ORCHESTRATOR: unknown target state fails",
        lambda: transition_job(fresh, intake, "NOPE"))
    expect_error(
        "CF-P1-004-ORCHESTRATOR: non-string target state fails",
        lambda: transition_job(fresh, intake, 42))
    plan_ready = build_bundle(fresh, analyzing_job(fresh, "job-inv-002"))[1]
    expect_error(
        "CF-P1-004-ORCHESTRATOR: PLAN_READY -> TEST_READY by bare "
        "transition fails (TEST_READY only via G1)",
        lambda: transition_job(fresh, plan_ready, "TEST_READY"))
    expect_error(
        "CF-P1-004-ORCHESTRATOR: PLAN_READY -> BATCH_PRODUCTION by "
        "bare transition fails (only via G2)",
        lambda: transition_job(fresh, plan_ready, "BATCH_PRODUCTION"))
    expect_error(
        "CF-P1-004-ORCHESTRATOR: PLAN_READY -> PICTURE_LOCK fails "
        "without G3",
        lambda: transition_job(fresh, plan_ready, "PICTURE_LOCK"))
    expect_error(
        "CF-P1-004-ORCHESTRATOR: a non-object job fails",
        lambda: transition_job(fresh, ["not", "a", "job"], "ANALYZING"))


# ---------------------------------------------------------------------------
# CF-P1-004-ORCHESTRATOR: gate order and waivers
# ---------------------------------------------------------------------------

def _gate_order_group():
    session = fresh_session()
    job = build_bundle(session, analyzing_job(session, "job-gate-001"))[1]
    job = transition_job(session, job, "AWAITING_G1_APPROVAL")
    job = evaluate_production_gate(session, job, "G1", "IN_PROGRESS")
    check("CF-P1-004-ORCHESTRATOR: G1 IN_PROGRESS records without "
          "moving the job",
          job["state"] == "AWAITING_G1_APPROVAL"
          and gate_status(job, "G1") == "IN_PROGRESS")

    # G2 cannot pass or be waived while G1 is unresolved: block G1
    # so the job is BLOCKED (a state from which every gate may be
    # evaluated) and the order rule, not the stage rule, decides.
    job = evaluate_production_gate(session, job, "G1", "BLOCKED")
    check("CF-P1-004-ORCHESTRATOR: G1 BLOCKED moves the job to "
          "BLOCKED",
          job["state"] == "BLOCKED"
          and job["previous_state"] == "AWAITING_G1_APPROVAL"
          and gate_status(job, "G1") == "BLOCKED")
    expect_error(
        "CF-P1-004-ORCHESTRATOR: G2 PASS before G1 is refused",
        lambda: evaluate_production_gate(session, job, "G2", "PASS"))
    expect_error(
        "CF-P1-004-ORCHESTRATOR: G2 WAIVED before G1 is refused",
        lambda: evaluate_production_gate(
            session, job, "G2", "WAIVED", waiver_reason="skip",
            authoriser="user"))
    expect_error(
        "CF-P1-004-ORCHESTRATOR: unknown gate fails",
        lambda: evaluate_production_gate(session, job, "G7", "PASS"))
    expect_error(
        "CF-P1-004-ORCHESTRATOR: unknown gate decision fails",
        lambda: evaluate_production_gate(session, job, "G1", "MAYBE"))
    job = evaluate_production_gate(session, job, "G1", "PASS")
    check("CF-P1-004-ORCHESTRATOR: G1 PASS while BLOCKED (job was "
          "awaiting G1) advances to TEST_READY directly",
          job["state"] == "TEST_READY"
          and job["previous_state"] is None)
    job = transition_job(session, job, "AWAITING_G2_APPROVAL")
    job = evaluate_production_gate(session, job, "G2", "BLOCKED")
    check("CF-P1-004-ORCHESTRATOR: G2 BLOCKED moves the job to "
          "BLOCKED",
          job["state"] == "BLOCKED"
          and job["previous_state"] == "AWAITING_G2_APPROVAL")
    job = evaluate_production_gate(session, job, "G2", "PASS")
    check("CF-P1-004-ORCHESTRATOR: G2 PASS while BLOCKED (job was "
          "awaiting G2) advances to BATCH_PRODUCTION directly",
          job["state"] == "BATCH_PRODUCTION"
          and job["previous_state"] is None)


def _waiver_group():
    session = fresh_session()
    job = build_bundle(session, analyzing_job(session, "job-waive-001"))[1]
    job = transition_job(session, job, "AWAITING_G1_APPROVAL")
    expect_error(
        "CF-P1-004-ORCHESTRATOR: waiver without a reason fails",
        lambda: evaluate_production_gate(session, job, "G1", "WAIVED",
                                         authoriser="user"))
    expect_error(
        "CF-P1-004-ORCHESTRATOR: waiver with an empty reason fails",
        lambda: evaluate_production_gate(
            session, job, "G1", "WAIVED", waiver_reason="  ",
            authoriser="user"))
    expect_error(
        "CF-P1-004-ORCHESTRATOR: waiver by a non-user authoriser "
        "fails",
        lambda: evaluate_production_gate(
            session, job, "G1", "WAIVED",
            waiver_reason="reviewed offline", authoriser="agent"))
    expect_error(
        "CF-P1-004-ORCHESTRATOR: waiver without an authoriser fails",
        lambda: evaluate_production_gate(
            session, job, "G1", "WAIVED",
            waiver_reason="reviewed offline"))
    job = evaluate_production_gate(
        session, job, "G1", "WAIVED",
        waiver_reason="visual plan reviewed offline with the user",
        authoriser="user", note="Waived by the user.")
    check("CF-P1-004-ORCHESTRATOR: waiver by the user with a reason "
          "passes and advances past G1",
          job["state"] == "TEST_READY"
          and gate_status(job, "G1") == "WAIVED")
    waived = [g for g in job["gate_state"]["gates"]
              if g["gate_id"] == "G1"][0]
    check("CF-P1-004-ORCHESTRATOR: a waived gate records its reason "
          "and the user as decider",
          waived.get("waiver_reason")
          == "visual plan reviewed offline with the user"
          and waived.get("decided_by") == "user")
    valid_job("CF-P1-004-ORCHESTRATOR: waived-gate job validates",
              job)
    job = transition_job(session, job, "AWAITING_G2_APPROVAL")
    job = evaluate_production_gate(
        session, job, "G2", "WAIVED",
        waiver_reason="test shots reviewed offline with the user",
        authoriser="user")
    check("CF-P1-004-ORCHESTRATOR: G2 WAIVED after a G1 waiver "
          "advances to BATCH_PRODUCTION",
          job["state"] == "BATCH_PRODUCTION"
          and gate_status(job, "G2") == "WAIVED")


# ---------------------------------------------------------------------------
# CF-P1-004-ORCHESTRATOR: BLOCKED and resume
# ---------------------------------------------------------------------------

def _blocked_group():
    session = fresh_session()
    job = build_bundle(session, analyzing_job(session, "job-block-001"))[1]
    job = transition_job(session, job, "AWAITING_G1_APPROVAL")
    job = evaluate_production_gate(session, job, "G1", "PASS")
    job = transition_job(session, job, "AWAITING_G2_APPROVAL")
    job = evaluate_production_gate(session, job, "G2", "PASS")
    job = transition_job(session, job, "EDITORIAL_REVIEW")
    job = transition_job(session, job, "BLOCKED")
    check("CF-P1-004-ORCHESTRATOR: BLOCKED from a mid state "
          "records the previous state",
          job["state"] == "BLOCKED"
          and job["previous_state"] == "EDITORIAL_REVIEW")
    expect_error(
        "CF-P1-004-ORCHESTRATOR: resume from BLOCKED to a state "
        "other than the previous state fails",
        lambda: transition_job(session, job, "BATCH_PRODUCTION"))
    job = transition_job(session, job, "EDITORIAL_REVIEW")
    check("CF-P1-004-ORCHESTRATOR: resume from BLOCKED returns to "
          "the previous state and clears it",
          job["state"] == "EDITORIAL_REVIEW"
          and job["previous_state"] is None)
    valid_job("CF-P1-004-ORCHESTRATOR: resumed job validates", job)

    # Resume is refused while a gate is BLOCKED.
    job = evaluate_production_gate(session, job, "G3", "BLOCKED")
    check("CF-P1-004-ORCHESTRATOR: G3 BLOCKED moves the job to "
          "BLOCKED",
          job["state"] == "BLOCKED"
          and job["previous_state"] == "EDITORIAL_REVIEW"
          and gate_status(job, "G3") == "BLOCKED")
    expect_error(
        "CF-P1-004-ORCHESTRATOR: resume refused while a gate is "
        "BLOCKED",
        lambda: transition_job(session, job, "EDITORIAL_REVIEW"))
    job = evaluate_production_gate(session, job, "G3", "PASS")
    check("CF-P1-004-ORCHESTRATOR: G3 PASS while BLOCKED restores "
          "the state the job came from",
          job["state"] == "EDITORIAL_REVIEW"
          and job["previous_state"] is None
          and gate_status(job, "G3") == "PASS")

    # [SUSPECTED RUNTIME BUG — see final report] A job blocked
    # from an operation-gated state cannot resume to it: the
    # operation-gated check in transition_job fires before the
    # BLOCKED-resume branch, so the documented "resume BLOCKED ->
    # previous_state" rule fails for PLAN_READY, TEST_READY and
    # BATCH_PRODUCTION. The test asserts the documented behaviour.
    job = transition_job(session, job, "PICTURE_LOCK")
    job = evaluate_production_gate(session, job, "G4", "PASS")
    job = transition_job(session, job, "FINISHING")
    job = transition_job(session, job, "BLOCKED")
    check("CF-P1-004-ORCHESTRATOR: BLOCKED from FINISHING records "
          "FINISHING as the previous state",
          job["state"] == "BLOCKED"
          and job["previous_state"] == "FINISHING")
    job = transition_job(session, job, "FINISHING")
    check("CF-P1-004-ORCHESTRATOR: resume from BLOCKED to "
          "FINISHING works", job["state"] == "FINISHING")
    job = evaluate_production_gate(session, job, "G5", "PASS")
    job = transition_job(session, job, "FINAL_QC")
    check("CF-P1-004-ORCHESTRATOR: FINISHING -> FINAL_QC once G5 "
          "passes", job["state"] == "FINAL_QC")
    # Back to BATCH_PRODUCTION is not reachable by transition, so
    # use a fresh job blocked from BATCH_PRODUCTION itself.
    batch_session = fresh_session()
    batch_job = build_bundle(
        batch_session,
        analyzing_job(batch_session, "job-block-002"))[1]
    batch_job = transition_job(batch_session, batch_job,
                               "AWAITING_G1_APPROVAL")
    batch_job = evaluate_production_gate(batch_session, batch_job,
                                         "G1", "PASS")
    batch_job = transition_job(batch_session, batch_job,
                               "AWAITING_G2_APPROVAL")
    batch_job = evaluate_production_gate(batch_session, batch_job,
                                         "G2", "PASS")
    check("CF-P1-004-ORCHESTRATOR: setup job reaches "
          "BATCH_PRODUCTION",
          batch_job["state"] == "BATCH_PRODUCTION")
    batch_job = transition_job(batch_session, batch_job, "BLOCKED")
    check("CF-P1-004-ORCHESTRATOR: BLOCKED from BATCH_PRODUCTION "
          "records BATCH_PRODUCTION as the previous state",
          batch_job["state"] == "BLOCKED"
          and batch_job["previous_state"] == "BATCH_PRODUCTION")
    # The resume below raises in the current runtime (see the
    # comment above): catch it so the check fails cleanly and the
    # rest of the suite still runs.
    try:
        batch_job = transition_job(batch_session, batch_job,
                                   "BATCH_PRODUCTION")
        resumed = (batch_job["state"] == "BATCH_PRODUCTION"
                   and batch_job["previous_state"] is None)
        check("CF-P1-004-ORCHESTRATOR: [SUSPECTED RUNTIME BUG] "
              "resume from BLOCKED to operation-gated previous_state "
              "BATCH_PRODUCTION works", resumed)
    except ProductionOrchestratorError as exc:
        check("CF-P1-004-ORCHESTRATOR: [SUSPECTED RUNTIME BUG] "
              "resume from BLOCKED to operation-gated previous_state "
              "BATCH_PRODUCTION works", False,
              f"refused with: {exc.errors}")


# ---------------------------------------------------------------------------
# CF-P1-004-ORCHESTRATOR: session enforcement
# ---------------------------------------------------------------------------

def _session_group():
    session = fresh_session()
    other = fresh_session()
    job = analyzing_job(session, "job-sess-001")
    expect_error(
        "CF-P1-004-ORCHESTRATOR: a job built under one session "
        "cannot be transitioned under a different session",
        lambda: transition_job(other, job, "ANALYZING"))
    expect_error(
        "CF-P1-004-ORCHESTRATOR: a job cannot be created under a "
        "different session than the caller (cross-session build)",
        lambda: build_bundle(other, job))
    close_session(other)
    expect_error(
        "CF-P1-004-ORCHESTRATOR: a closed session cannot act",
        lambda: transition_job(other, job, "ANALYZING"))
    expect_error(
        "CF-P1-004-ORCHESTRATOR: a closed session cannot create a "
        "job",
        lambda: new_job(other, "job-sess-002"))
    expect_error(
        "CF-P1-004-ORCHESTRATOR: a closed session cannot resolve a "
        "character",
        lambda: resolve_character(
            other, job, short_analysis()["character_resolutions"][0],
            approved_registry={"char-001": {}}))
    still = new_job(session, "job-sess-003")
    check("CF-P1-004-ORCHESTRATOR: the original session still acts "
          "after the other session closes",
          transition_job(session, still, "ANALYZING")["state"]
          == "ANALYZING")


# ---------------------------------------------------------------------------
# CF-P1-004-ORCHESTRATOR: build_production_bundle refusals
# ---------------------------------------------------------------------------

def _build_group():
    session = fresh_session()
    intake = new_job(session, "job-build-001")
    expect_error(
        "CF-P1-004-ORCHESTRATOR: bundle build refused when the job "
        "is not ANALYZING",
        lambda: build_bundle(session, intake))

    def refused(label, analysis, authorised=False):
        job = analyzing_job(session, "job-build-002")
        expect_error(label, lambda: build_bundle(
            session, job, analysis, authorised=authorised))

    open_q = clone(short_analysis())
    open_q["open_questions"] = [{
        "question": "Which river?",
        "why_material": "The location changes the whole look.",
        "provenance": "NEEDS_USER_DECISION"}]
    refused("CF-P1-004-ORCHESTRATOR: analysis with open questions "
            "is refused", open_q)
    undecided = clone(short_analysis())
    undecided["character_resolutions"][0]["resolution"] = \
        "needs-decision"
    del undecided["character_resolutions"][0]["registered_character_id"]
    refused("CF-P1-004-ORCHESTRATOR: analysis with a needs-decision "
            "character is refused", undecided)
    wrong_project = clone(short_analysis())
    wrong_project["project_id"] = "proj-other-001"
    refused("CF-P1-004-ORCHESTRATOR: analysis project mismatch is "
            "refused", wrong_project)
    wrong_profile = clone(short_analysis())
    wrong_profile["format_profile"]["delivery_profile"] = "story-5-15min"
    refused("CF-P1-004-ORCHESTRATOR: analysis format_profile "
            "delivery_profile mismatch is refused", wrong_profile)
    wrong_script = clone(short_analysis())
    wrong_script["script_contract_id"] = "script-other-001"
    refused("CF-P1-004-ORCHESTRATOR: analysis script_contract_id "
            "mismatch is refused", wrong_script)
    rewrite_wanted = clone(short_analysis())
    rewrite_wanted["dialogue_preservation"]["rewrite_requested"] = True
    refused("CF-P1-004-ORCHESTRATOR: rewrite_requested True without "
            "authorisation is refused", rewrite_wanted)
    refused("CF-P1-004-ORCHESTRATOR: authorisation True without a "
            "rewrite request is refused", short_analysis(),
            authorised=True)
    bad_counts = clone(short_analysis())
    bad_counts["dialogue_preservation"]["source_dialogue_line_count"] = 3
    bad_counts["dialogue_preservation"]["mapped_line_count"] = 3
    refused("CF-P1-004-ORCHESTRATOR: analysis dialogue counts vs "
            "the script are refused", bad_counts)

    job = analyzing_job(session, "job-build-003")
    bundle, job = build_bundle(session, job)
    check("CF-P1-004-ORCHESTRATOR: a valid analysis builds the "
          "production bundle",
          job["state"] == "PLAN_READY"
          and bundle["s2p_bundle"]["bundle_id"] == "bundle-short-001")
    expect_error(
        "CF-P1-004-ORCHESTRATOR: a second bundle build is refused "
        "once the job left ANALYZING",
        lambda: build_bundle(session, job))


# ---------------------------------------------------------------------------
# CF-P1-004-ORCHESTRATOR: character resolution
# ---------------------------------------------------------------------------

def _resolve_group():
    session = fresh_session()
    job = analyzing_job(session, "job-resolve-001")
    registry = {"char-001": {"character_id": "char-001"},
                "char-kiki-001": {"character_id": "char-kiki-001"}}
    analysis = short_analysis()
    resolved = resolve_character(
        session, job, analysis["character_resolutions"][0],
        approved_registry=registry)
    check("CF-P1-004-ORCHESTRATOR: approved resolution binds the "
          "registered id",
          resolved["character_id"] == "char-001"
          and resolved["resolution"] == "approved"
          and resolved["proposal_id"] is None
          and resolved["role"] == "protagonist")
    resolved = resolve_character(
        session, job, analysis["character_resolutions"][1],
        approved_registry=registry)
    check("CF-P1-004-ORCHESTRATOR: second approved resolution binds",
          resolved["character_id"] == "char-kiki-001")
    expect_error(
        "CF-P1-004-ORCHESTRATOR: approved character missing from "
        "the registry is refused",
        lambda: resolve_character(
            session, job, analysis["character_resolutions"][0],
            approved_registry={}))
    expect_error(
        "CF-P1-004-ORCHESTRATOR: approved resolution without a "
        "registered id is refused",
        lambda: resolve_character(
            session, job,
            {"character_ref": "char-001", "resolution": "approved",
             "role": "protagonist",
             "provenance": "FROM_APPROVED_PROJECT_CANON"},
            approved_registry=registry))

    proposal = load_fixture(
        "character-design-proposal-fisherman.json")
    missing = load_fixture("production-analysis-missing-character.json")
    proposals = {"prop-fisherman-001": proposal}
    resolved = resolve_character(
        session, job, missing["character_resolutions"][0],
        proposals=proposals)
    check("CF-P1-004-ORCHESTRATOR: task-local-proposal resolution "
          "binds the proposal id",
          resolved["proposal_id"] == "prop-fisherman-001"
          and resolved["resolution"] == "task-local-proposal"
          and resolved["character_id"] is None)
    expect_error(
        "CF-P1-004-ORCHESTRATOR: proposal resolution with no "
        "proposal record supplied is refused",
        lambda: resolve_character(
            session, job, missing["character_resolutions"][0],
            proposals={}))
    rejected = clone(proposal)
    rejected["status"] = "rejected"
    expect_error(
        "CF-P1-004-ORCHESTRATOR: rejected proposal is refused",
        lambda: resolve_character(
            session, job, missing["character_resolutions"][0],
            proposals={"prop-fisherman-001": rejected}))
    expect_error(
        "CF-P1-004-ORCHESTRATOR: needs-decision resolution is "
        "refused",
        lambda: resolve_character(
            session, job,
            {"character_ref": "the old fisherman",
             "resolution": "needs-decision", "role": "supporting",
             "provenance": "NEEDS_USER_DECISION"}))
    expect_error(
        "CF-P1-004-ORCHESTRATOR: unknown resolution is refused",
        lambda: resolve_character(
            session, job,
            {"character_ref": "x", "resolution": "maybe",
             "role": "supporting",
             "provenance": "INFERRED_FOR_PRODUCTION"}))

    registry_before = digest(registry)
    proposals_before = digest(proposals)
    resolve_character(session, job,
                      analysis["character_resolutions"][0],
                      approved_registry=registry)
    resolve_character(session, job,
                      missing["character_resolutions"][0],
                      proposals=proposals)
    check("CF-P1-004-ORCHESTRATOR: resolve_character never mutates "
          "the supplied registry or proposals",
          digest(registry) == registry_before
          and digest(proposals) == proposals_before)


# ---------------------------------------------------------------------------
# CF-P1-004-ORCHESTRATOR: execution results and compile guards
# ---------------------------------------------------------------------------

def _execution_group():
    session = fresh_session()
    job = analyzing_job(session, "job-exec-001")
    expect_error(
        "CF-P1-004-ORCHESTRATOR: recording a result without a "
        "compiled task package is refused",
        lambda: record_execution_result(
            session, job, "t-video-generation-002",
            {"outcome": "succeeded"}))
    bundle, job = build_bundle(session, job)
    package, job = compile_provider_tasks(
        session, job, bundle, short_analysis())
    video_task = [p for p in package["packets"]
                  if p["task_type"] == "video-generation"][0]
    job = record_execution_result(
        session, job, video_task["task_id"],
        {"provider_id": "provider-ffmpeg", "outcome": "succeeded",
         "output_ref": "out/sh-01.mp4"})
    check("CF-P1-004-ORCHESTRATOR: a valid execution result is "
          "recorded on the job",
          len(job["execution_results"]) == 1
          and job["execution_results"][0]["task_id"]
          == video_task["task_id"]
          and job["execution_results"][0]["outcome"] == "succeeded"
          and job["execution_results"][0]["output_ref"]
          == "out/sh-01.mp4")
    valid_job("CF-P1-004-ORCHESTRATOR: job with a recorded result "
              "validates", job)
    expect_error(
        "CF-P1-004-ORCHESTRATOR: unknown task_id is refused",
        lambda: record_execution_result(
            session, job, "t-nope-999", {"outcome": "succeeded"}))
    for bad_outcome in ("done", "ok", None, 1):
        expect_error(
            "CF-P1-004-ORCHESTRATOR: bad outcome "
            f"{bad_outcome!r} is refused",
            lambda bad_outcome=bad_outcome: record_execution_result(
                session, job, video_task["task_id"],
                {"outcome": bad_outcome}))
    job = record_execution_result(
        session, job, video_task["task_id"],
        {"outcome": "failed", "notes": "face drift in the second half"})
    check("CF-P1-004-ORCHESTRATOR: a failed result is recorded "
          "without auto-blocking the job",
          len(job["execution_results"]) == 2
          and job["execution_results"][1]["outcome"] == "failed"
          and job["state"] == "PLAN_READY")


def _compile_guard_group(delivered):
    session, _job, _bundle = delivered
    expect_error(
        "CF-P1-004-ORCHESTRATOR: compile_provider_tasks refused "
        "once DELIVERED",
        lambda: compile_provider_tasks(session, _job, _bundle))

    fresh = fresh_session()
    intake = new_job(fresh, "job-guard-001")
    expect_error(
        "CF-P1-004-ORCHESTRATOR: compile_provider_tasks refused in "
        "INTAKE",
        lambda: compile_provider_tasks(
            fresh, intake,
            {"job_id": "job-guard-001", "s2p_bundle": {}}))
    job = analyzing_job(fresh, "job-guard-002")
    bundle, job = build_bundle(fresh, job)
    package, job = compile_provider_tasks(fresh, job, bundle,
                                          short_analysis())
    check("CF-P1-004-ORCHESTRATOR: compile_provider_tasks works in "
          "PLAN_READY and stores the package on the job",
          job["task_package"]["package_id"] == package["package_id"]
          and len(package["packets"]) == 10)
    valid_job("CF-P1-004-ORCHESTRATOR: job with a task package "
              "validates", job)
    expect_error(
        "CF-P1-004-ORCHESTRATOR: compile refuses a bundle from "
        "another job",
        lambda: compile_provider_tasks(
            fresh, job, {"job_id": "job-other-001",
                         "s2p_bundle": bundle["s2p_bundle"]}))


# ---------------------------------------------------------------------------
# CF-P1-004-ORCHESTRATOR: QC correction tasks
# ---------------------------------------------------------------------------

def _qc_group():
    session = fresh_session()
    job = analyzing_job(session, "job-short-001")
    bundle, job = build_bundle(session, job)
    qc = load_fixture("qc-report-test.json")
    expect_error(
        "CF-P1-004-ORCHESTRATOR: QC correction tasks refused in "
        "PLAN_READY (not a QC state)",
        lambda: build_qc_correction_tasks(session, job, qc))
    package, job = compile_provider_tasks(session, job, bundle,
                                          short_analysis())
    job = transition_job(session, job, "AWAITING_G1_APPROVAL")
    job = evaluate_production_gate(session, job, "G1", "PASS")
    expect_error(
        "CF-P1-004-ORCHESTRATOR: QC correction tasks refused in "
        "TEST_READY (not a QC state)",
        lambda: build_qc_correction_tasks(session, job, qc))
    job = transition_job(session, job, "AWAITING_G2_APPROVAL")
    job = evaluate_production_gate(session, job, "G2", "PASS")
    check("CF-P1-004-ORCHESTRATOR: setup job reaches "
          "BATCH_PRODUCTION for QC",
          job["state"] == "BATCH_PRODUCTION")

    correction, job = build_qc_correction_tasks(session, job, qc)
    check("CF-P1-004-ORCHESTRATOR: Critical defect gets exactly 1 "
          "correction packet, for sh-01 only",
          len(correction["packets"]) == 1
          and correction["packets"][0].get("shot_id") == "sh-01"
          and correction["packets"][0]["task_type"] == "regeneration")
    check("CF-P1-004-ORCHESTRATOR: neighbours are untouched (no "
          "packet for sh-02)",
          all(p.get("shot_id") != "sh-02"
              for p in correction["packets"]))
    skipped = {entry["defect_id"]: entry["reason"]
               for entry in correction["skipped_defects"]}
    check("CF-P1-004-ORCHESTRATOR: Minor without authorisation is "
          "skipped with a reason",
          "qc-002" in skipped
          and "authorisation" in skipped["qc-002"])
    check("CF-P1-004-ORCHESTRATOR: Polish is skipped with a reason",
          "qc-003" in skipped
          and "Polish" in skipped["qc-003"])
    check("CF-P1-004-ORCHESTRATOR: correction_round increments and "
          "the report is recorded",
          job["correction_round"] == 1
          and len(job["qc_reports"]) == 1
          and job["qc_reports"][0]["report_id"] == "qc-report-001")
    valid_job("CF-P1-004-ORCHESTRATOR: job after QC correction "
              "validates", job)

    correction2, job = build_qc_correction_tasks(session, job, qc)
    check("CF-P1-004-ORCHESTRATOR: a second correction round gets "
          "a distinct package id and round 2",
          correction2["package_id"] != correction["package_id"]
          and correction2["package_id"]
          == "pkg-job-short-001-regen-02"
          and job["correction_round"] == 2)

    bad_shot = clone(qc)
    bad_shot["defects"] = [{
        "defect_id": "qc-999", "severity": "Critical",
        "shot_id": "sh-99", "description": "No such shot."}]
    expect_error(
        "CF-P1-004-ORCHESTRATOR: defect with an unknown shot is "
        "refused",
        lambda: build_qc_correction_tasks(session, job, bad_shot))
    bad_severity = clone(qc)
    bad_severity["defects"] = [{
        "defect_id": "qc-998", "severity": "Trivial",
        "shot_id": "sh-01", "description": "No such severity."}]
    expect_error(
        "CF-P1-004-ORCHESTRATOR: defect with an unknown severity "
        "is refused",
        lambda: build_qc_correction_tasks(session, job, bad_severity))
    wrong_job = clone(qc)
    wrong_job["job_id"] = "job-other-001"
    expect_error(
        "CF-P1-004-ORCHESTRATOR: QC report for another job is "
        "refused",
        lambda: build_qc_correction_tasks(session, job, wrong_job))


# ---------------------------------------------------------------------------
# CF-P1-004-ORCHESTRATOR: determinism, immutability, no false claims
# ---------------------------------------------------------------------------

def _determinism_group():
    session = fresh_session()
    first = new_job(session, "job-det-001")
    second = new_job(session, "job-det-001")
    check("CF-P1-004-ORCHESTRATOR: identical job inputs produce "
          "identical job_hash values",
          first["job_hash"] == second["job_hash"]
          and first == second,
          f"first={first['job_hash']} second={second['job_hash']}")

    first = transition_job(session, first, "ANALYZING")
    second = transition_job(session, second, "ANALYZING")
    plan = T.fresh_routing_plan(session)
    script, profile, draft = T.script(), T.profile(), T.draft()
    analysis = short_analysis()
    snapshots = {
        "job": clone(first), "plan": clone(plan),
        "script": clone(script), "profile": clone(profile),
        "draft": clone(draft), "analysis": clone(analysis),
    }
    bundle_a, job_a = build_production_bundle(
        session, first, plan, script, profile, draft, analysis,
        "bundle-det-001")
    bundle_b, job_b = build_production_bundle(
        session, second, plan, script, profile, draft, analysis,
        "bundle-det-001")
    check("CF-P1-004-ORCHESTRATOR: identical bundle inputs produce "
          "identical bundle_hash values",
          bundle_a["bundle_hash"] == bundle_b["bundle_hash"]
          and bundle_a == bundle_b)
    check("CF-P1-004-ORCHESTRATOR: build_production_bundle never "
          "mutates its inputs",
          first == snapshots["job"] and plan == snapshots["plan"]
          and script == snapshots["script"]
          and profile == snapshots["profile"]
          and draft == snapshots["draft"]
          and analysis == snapshots["analysis"])
    snapshots["job_a"] = clone(job_a)
    snapshots["bundle_a"] = clone(bundle_a)
    job_a_in, bundle_a_in = job_a, bundle_a
    package_a, job_a = compile_provider_tasks(
        session, job_a, bundle_a, analysis)
    package_b, job_b = compile_provider_tasks(
        session, job_b, bundle_b, analysis)
    check("CF-P1-004-ORCHESTRATOR: identical compile inputs "
          "produce identical package_hash values",
          package_a["package_hash"] == package_b["package_hash"]
          and package_a == package_b)
    check("CF-P1-004-ORCHESTRATOR: compile_provider_tasks never "
          "mutates its inputs",
          job_a_in == snapshots["job_a"]
          and bundle_a_in == snapshots["bundle_a"]
          and analysis == snapshots["analysis"])

    allowed = {"not-executed", "handed-off",
               "unavailable-no-verified-provider"}
    check("CF-P1-004-ORCHESTRATOR: no compiled packet claims "
          "execution (provider_status is only not-executed, "
          "handed-off, or unavailable-no-verified-provider)",
          all(p["provider_status"] in allowed
              for p in package_a["packets"])
          and all(p["provider_status"] != "executed"
                  for p in package_a["packets"]))


def main():
    _creation_group()
    delivered = _lifecycle_group()
    _invalid_transitions_group(delivered)
    _gate_order_group()
    _waiver_group()
    _blocked_group()
    _session_group()
    _build_group()
    _resolve_group()
    _execution_group()
    _compile_guard_group(delivered)
    _qc_group()
    _determinism_group()
    for session in list(_sessions):
        try:
            if is_active_session(session):
                close_session(session)
        except Exception:  # noqa: BLE001 - best-effort cleanup
            pass
    total = _checks[0]
    if failures:
        print(f"\n{len(failures)} FAILURES:")
        for name in failures:
            print(f"  FAIL {name}")
        print(f"test_production_orchestrator: FAIL ({total} checks)")
        return 1
    print(f"test_production_orchestrator: PASS ({total} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
