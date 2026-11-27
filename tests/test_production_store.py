#!/usr/bin/env python3
"""Local persistent production job store tests
(CF-WO-P1-004-R1, Task C).

Covers: save/load round trip; store integrity (record hash,
envelope versions, id agreement); path safety (absolute root
only, strict ids, symlink containment, symlinked records
refused); tampered-record rejection; list with invalid files
reported, never silently dropped; checkpoint save; resume
under a new authorized session (session rebind, gate
revalidation, DELIVERED refused, wrong owner/workspace/project
refused, no execution triggered); restrictive POSIX modes.

Conventions follow tests/test_script_to_performance_runtime.py:
check(name, cond, detail="") prints PASS/FAIL lines, failures
are collected, and the process exits 0 only when every check
passes. No test here weakens any P0 or P1 check.
"""

import copy
import json
import os
import stat
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
from runtime import production_store as store  # noqa: E402
from runtime.production_orchestrator import (  # noqa: E402
    build_production_bundle, compile_provider_tasks,
    create_production_job, job_hash, transition_job,
    validate_job)
from runtime.production_store import ProductionStoreError  # noqa: E402

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


def fresh_profile():
    root = tempfile.mkdtemp(prefix="cf-p1-004-r1-store-prof-")
    profile = load_or_create_profile(root)
    session = start_session(profile, profile.workspace_id)
    _sessions.append(session)
    return profile, session


def new_session(profile):
    session = start_session(profile, profile.workspace_id)
    _sessions.append(session)
    return session


def store_root():
    return tempfile.mkdtemp(prefix="cf-p1-004-r1-store-")


def load_fixture(name):
    with open(os.path.join(
            ROOT, "tests", "fixtures", name), encoding="utf-8") as f:
        return json.load(f)


def short_analysis():
    return load_fixture("production-analysis-short.json")


def format_profile():
    return {"delivery_profile": "short-form-15-60s"}


def new_job(session, job_id="job-store-001"):
    return create_production_job(session, job_id, "proj-test-001",
                                 format_profile())


def analyzing_job(session, job_id="job-store-001"):
    return transition_job(session, new_job(session, job_id),
                          "ANALYZING")


def planned_job(session, job_id="job-store-001"):
    """A PLAN_READY job with a compiled task package."""
    job = analyzing_job(session, job_id)
    plan = T.fresh_routing_plan(session)
    bundle, job = build_production_bundle(
        session, job, plan, T.script(), T.profile(), T.draft(),
        short_analysis(), "bundle-store-001")
    package, job = compile_provider_tasks(
        session, job, bundle, short_analysis())
    return job


def expect_error(label, fn):
    """fn must raise ProductionStoreError; anything else
    (including success) fails the check."""
    try:
        fn()
    except ProductionStoreError:
        check(label, True)
        return True
    except Exception as exc:  # noqa: BLE001 - the test asserts no raise
        check(label, False, f"raised {type(exc).__name__}: {exc}")
        return False
    check(label, False, "operation succeeded instead of refusing")
    return False


def _store_group():
    profile, session = fresh_profile()
    root = store_root()

    # Save / load round trip.
    job = analyzing_job(session, "job-store-001")
    path = store.save_production_job(session, root, job)
    check("CF-P1-004-R1-STORE: save returns the jobs path",
          path == os.path.join(root, "jobs", "job-store-001.json"),
          f"got {path!r}")
    record = store.load_production_job(
        root, "job-store-001", "proj-test-001")
    check("CF-P1-004-R1-STORE: the loaded record round-trips "
          "the job with its state and hash",
          record["job"] == job
          and record["schema_version"] == "2.5"
          and record["store_format_version"] == 1
          and record["record_kind"] == "production-job"
          and record["job_id"] == "job-store-001"
          and record["project_id"] == "proj-test-001"
          and record["owner_id"] == session.owner_id
          and record["workspace_id"] == session.workspace_id)
    check("CF-P1-004-R1-STORE: the loaded job still validates",
          validate_job(record["job"]) == [])

    # Restrictive POSIX modes.
    if os.name == "posix":
        mode = stat.S_IMODE(os.stat(path).st_mode)
        check("CF-P1-004-R1-STORE: the saved job file is 0o600",
              mode == 0o600, f"got {oct(mode)}")
        mode = stat.S_IMODE(os.stat(os.path.join(root, "jobs")).st_mode)
        check("CF-P1-004-R1-STORE: the jobs directory is 0o700",
              mode == 0o700, f"got {oct(mode)}")

    # List: one valid job, empty invalid list.
    listing = store.list_production_jobs(root)
    check("CF-P1-004-R1-STORE: list reports the saved job",
          len(listing["jobs"]) == 1
          and listing["jobs"][0]["job_id"] == "job-store-001"
          and listing["jobs"][0]["state"] == "ANALYZING"
          and listing["invalid_files"] == [],
          f"listing={listing}")
    check("CF-P1-004-R1-STORE: list on an empty store root is "
          "empty, not an error",
          store.list_production_jobs(store_root())
          == {"jobs": [], "invalid_files": []})

    # Checkpoint save (default id is the state slug).
    checkpoint = store.save_production_checkpoint(session, root, job)
    check("CF-P1-004-R1-STORE: the default checkpoint id is the "
          "job state",
          checkpoint == os.path.join(
              root, "checkpoints", "job-store-001", "analyzing.json"),
          f"got {checkpoint!r}")
    with open(checkpoint, encoding="utf-8") as handle:
        checkpoint_record = json.load(handle)
    check("CF-P1-004-R1-STORE: the checkpoint record carries "
          "the checkpoint kind and the same job",
          checkpoint_record["record_kind"] == "production-checkpoint"
          and checkpoint_record["job"] == job)
    named = store.save_production_checkpoint(
        session, root, job, checkpoint_id="before-g1")
    check("CF-P1-004-R1-STORE: an explicit checkpoint id is used",
          named.endswith("before-g1.json"))

    # Tampered records are refused, never silently accepted.
    tampered_job = analyzing_job(session, "job-store-002")
    tampered_path = store.save_production_job(
        session, root, tampered_job)
    with open(tampered_path, encoding="utf-8") as handle:
        record = json.load(handle)
    record["job"]["state"] = "DELIVERED"
    with open(tampered_path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, sort_keys=True)
    expect_error(
        "CF-P1-004-R1-STORE: a record whose hash no longer "
        "matches is refused on load",
        lambda: store.load_production_job(
            root, "job-store-002", "proj-test-001"))
    listing = store.list_production_jobs(root)
    check("CF-P1-004-R1-STORE: a tampered file is reported in "
          "invalid_files, never silently dropped",
          len(listing["jobs"]) == 1
          and len(listing["invalid_files"]) == 1
          and listing["invalid_files"][0]["path"]
          == "job-store-002.json",
          f"listing={listing}")

    # Path safety.
    expect_error(
        "CF-P1-004-R1-STORE: a relative store root is refused",
        lambda: store.save_production_job(
            session, "relative/store", job))
    expect_error(
        "CF-P1-004-R1-STORE: a job id with path traversal is "
        "refused",
        lambda: store.load_production_job(
            root, "../escape", "proj-test-001"))
    expect_error(
        "CF-P1-004-R1-STORE: a checkpoint id with a slash is "
        "refused",
        lambda: store.save_production_checkpoint(
            session, root, job, checkpoint_id="a/b"))
    expect_error(
        "CF-P1-004-R1-STORE: loading a missing job is refused",
        lambda: store.load_production_job(
            root, "job-missing-001", "proj-test-001"))
    expect_error(
        "CF-P1-004-R1-STORE: loading with the wrong project is "
        "refused",
        lambda: store.load_production_job(
            root, "job-store-001", "proj-other-001"))
    closed_profile, closed_session = fresh_profile()
    close_session(closed_session)
    expect_error(
        "CF-P1-004-R1-STORE: saving with a closed session is "
        "refused",
        lambda: store.save_production_job(
            closed_session, root, job))
    link_root = store_root()
    try:
        outside = tempfile.mkdtemp(prefix="cf-p1-004-r1-outside-")
        os.symlink(outside, os.path.join(link_root, "jobs"))
        symlink_supported = True
    except (OSError, NotImplementedError):
        symlink_supported = False
    if symlink_supported:
        expect_error(
            "CF-P1-004-R1-STORE: a symlinked jobs directory "
            "pointing outside the store is refused",
            lambda: store.save_production_job(
                session, link_root,
                analyzing_job(session, "job-store-003")))
        os.unlink(os.path.join(link_root, "jobs"))
        target = os.path.join(root, "jobs", "job-store-001.json")
        link = os.path.join(root, "jobs", "job-link-001.json")
        try:
            os.symlink(target, link)
            expect_error(
                "CF-P1-004-R1-STORE: a symlinked job file is "
                "refused on read",
                lambda: store.load_production_job(
                    root, "job-link-001", "proj-test-001"))
            listing = store.list_production_jobs(root)
            check("CF-P1-004-R1-STORE: a symlinked file is "
                  "reported in invalid_files, not read",
                  any(entry["path"] == "job-link-001.json"
                      for entry in listing["invalid_files"]))
        finally:
            os.unlink(link)


def _resume_group():
    profile, session = fresh_profile()
    root = store_root()
    job = planned_job(session, "job-store-010")
    store.save_production_job(session, root, job)
    close_session(session)

    # Resume under a NEW session from the same profile.
    session2 = new_session(profile)
    resumed = store.resume_production_job(
        session2, root, "job-store-010", "proj-test-001")
    check("CF-P1-004-R1-STORE: resume rebinds the job to the new "
          "session and keeps PLAN_READY",
          resumed["session_id"] == session2.session_id
          and resumed["state"] == "PLAN_READY"
          and resumed["job_hash"] == job_hash(resumed))
    check("CF-P1-004-R1-STORE: resume keeps the task package "
          "and triggers no execution",
          resumed["task_package"] is not None
          and all(p["provider_status"] != "executed"
                  for p in resumed["task_package"]["packets"]))
    check("CF-P1-004-R1-STORE: the resumed job still validates",
          validate_job(resumed) == [])

    # Resume refusals.
    foreign_profile, foreign_session = fresh_profile()
    expect_error(
        "CF-P1-004-R1-STORE: resume under a different owner is "
        "refused",
        lambda: store.resume_production_job(
            foreign_session, root, "job-store-010", "proj-test-001"))
    expect_error(
        "CF-P1-004-R1-STORE: resume with the wrong project is "
        "refused",
        lambda: store.resume_production_job(
            session2, root, "job-store-010", "proj-other-001"))
    delivered = clone(job)
    delivered["state"] = "DELIVERED"
    delivered["job_hash"] = job_hash(delivered)
    store.save_production_job(session2, root, delivered)
    expect_error(
        "CF-P1-004-R1-STORE: resume refuses a DELIVERED job",
        lambda: store.resume_production_job(
            session2, root, "job-store-010", "proj-test-001"))
    # Gate revalidation: a stored job with an invalid gate state
    # (WAIVED with no waiver_reason, envelope hash recomputed so
    # the tamper is a job-level defect, not an envelope defect)
    # fails resume.
    broken = planned_job(session2, "job-store-011")
    store.save_production_job(session2, root, broken)
    with open(os.path.join(root, "jobs", "job-store-011.json"),
              encoding="utf-8") as handle:
        record = json.load(handle)
    record["job"]["gate_state"]["gates"][0]["status"] = "WAIVED"
    record["job"]["gate_state"]["gates"][0].pop("waiver_reason", None)
    record["job"]["job_hash"] = job_hash(record["job"])
    record["record_hash"] = store._record_hash(record)
    with open(os.path.join(root, "jobs", "job-store-011.json"),
              "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, sort_keys=True)
    expect_error(
        "CF-P1-004-R1-STORE: resume refuses a stored job whose "
        "gate state is invalid",
        lambda: store.resume_production_job(
            session2, root, "job-store-011", "proj-test-001"))


def _windows_atomic_write_group():
    # CF-WO-P1-005-R1: Windows CI run #263 failed both windows-compat
    # jobs in the identity suite's e2e group at
    # store.save_production_job -> atomic_write_json -> atomic_write
    # -> os.fchmod, which does not exist on Windows Python 3.10-3.12
    # (AttributeError). P1-001-R2 fixed the same hole in
    # runtime/local_session.py but left scripts/atomic_write.py
    # untouched. The fix capability-checks os.fchmod in the helper;
    # these checks simulate the Windows absence by hiding the
    # attribute, the same pattern as tests/test_local_session_runtime.py.
    import contextlib

    @contextlib.contextmanager
    def _without_fchmod():
        had = hasattr(os, "fchmod")
        saved = getattr(os, "fchmod", None)
        if had:
            del os.fchmod
        try:
            yield had
        finally:
            if had:
                os.fchmod = saved

    profile, session = fresh_profile()
    root = store_root()
    job = planned_job(session, "job-store-win-001")
    with _without_fchmod():
        store.save_production_job(session, root, job)
    loaded = store.load_production_job(
        root, "job-store-win-001", "proj-test-001")
    check("CF-P1-005-R1-STORE: save_production_job succeeds with "
          "os.fchmod hidden (Windows simulation)",
          loaded["job"]["job_id"] == "job-store-win-001"
          and loaded["job"]["job_hash"] == job_hash(loaded["job"]))
    check("CF-P1-005-R1-STORE: the record written without fchmod "
          "validates",
          validate_job(loaded["job"]) == [])

    # Direct helper path, same simulation.
    helper = store._load_atomic_write()
    target = os.path.join(tempfile.mkdtemp(prefix="cf-p1-005-r1-aw-"),
                          "out.json")
    payload = {"alpha": [1, 2, 3], "beta": "x"}
    with _without_fchmod():
        helper.atomic_write_json(target, payload)
    with open(target, encoding="utf-8") as handle:
        written = handle.read()
    check("CF-P1-005-R1-STORE: atomic_write_json writes exact bytes "
          "with os.fchmod hidden",
          json.loads(written) == payload
          and written.endswith("\n"))

    # Failure cleanup still holds without fchmod: bad input raises,
    # the target is unchanged, and no temporary file is left behind.
    before = written
    with _without_fchmod():
        try:
            helper.atomic_write(target, "not-bytes")
            raised = False
        except TypeError:
            raised = True
    leftovers = [n for n in os.listdir(os.path.dirname(target))
                 if n.startswith(".cf-atomic-")]
    with open(target, encoding="utf-8") as handle:
        after = handle.read()
    check("CF-P1-005-R1-STORE: atomic_write failure without fchmod "
          "leaves the target unchanged and no temp file behind",
          raised and after == before and leftovers == [])

    # fchmod is restored after the simulation.
    check("CF-P1-005-R1-STORE: os.fchmod is restored after the "
          "Windows simulation",
          hasattr(os, "fchmod") == (os.name == "posix"))

    # POSIX only: with fchmod present the requested mode is applied.
    if os.name == "posix" and hasattr(os, "fchmod"):
        mode_target = os.path.join(
            tempfile.mkdtemp(prefix="cf-p1-005-r1-aw-"), "mode.bin")
        helper.atomic_write(mode_target, b"mode", mode=0o600)
        check("CF-P1-005-R1-STORE: atomic_write applies the requested "
              "mode when os.fchmod exists",
              stat.S_IMODE(os.stat(mode_target).st_mode) == 0o600)


def main():
    _store_group()
    _resume_group()
    _windows_atomic_write_group()
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
        print(f"test_production_store: FAIL ({total} checks)")
        sys.exit(1)
    print(f"test_production_store: PASS ({total} checks)")


if __name__ == "__main__":
    main()
