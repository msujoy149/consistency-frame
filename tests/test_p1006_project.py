#!/usr/bin/env python3
"""P1-006 project tests (CF-WO-P1-006, Phases A + F).

Project validation, provenance, script preservation, identity
consistency, missing user decisions, invalid output profiles,
and the production execution state machine with checkpoints
and persistence. Pure-Python tests (no FFmpeg needed except the
adapter-availability check, which is exercised with
require_adapters=False where the tools are irrelevant).
"""

import copy
import json
import os
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(__file__), "..")
ROOT_ABS = os.path.abspath(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
from runtime import local_session  # noqa: E402
from runtime.local_session import (  # noqa: E402
    close_session, load_or_create_profile, start_session)
from runtime import production_store  # noqa: E402
from runtime import vertical_production as vp  # noqa: E402

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


def expect_error(label, fn, code=None):
    try:
        fn()
    except vp.VerticalProductionError as exc:
        if code is not None and exc.code != code:
            check(label, False, f"wrong code {exc.code!r}, want {code!r}")
            return
        check(label, True)
        return
    except Exception as exc:  # noqa: BLE001 - any other error is a fail
        check(label, False, f"raised {type(exc).__name__}: {exc}")
        return
    check(label, False, "operation succeeded instead of refusing")


def fresh_session():
    root = tempfile.mkdtemp(prefix="cf-p1006-project-")
    profile = load_or_create_profile(root)
    session = start_session(profile, profile.workspace_id)
    _sessions.append(session)
    return session


def load_example():
    base = os.path.join(ROOT_ABS,
                        "examples", "p1006-vertical-explainer")
    with open(os.path.join(base, "project.json")) as handle:
        project_config = json.load(handle)
    with open(os.path.join(base, "production-analysis.json")) as handle:
        analysis = json.load(handle)
    with open(os.path.join(base, "shot-list.json")) as handle:
        shots = json.load(handle)["shots"]
    with open(os.path.join(base, "voice-config.json")) as handle:
        voice = json.load(handle)
    with open(os.path.join(base, "sound-plan.json")) as handle:
        sound = json.load(handle)
    with open(os.path.join(base, "assembly-config.json")) as handle:
        assembly = json.load(handle)
    lines = [{"line_id": line["line_id"], "shot_id": line["shot_id"],
              "text": line["text"]} for line in voice["lines"]]
    return project_config, lines, analysis, shots, voice, sound, assembly


def build_reference(session):
    project_config, lines, analysis, shots, voice, sound, assembly = \
        load_example()
    return vp.build_project(session, project_config, lines, analysis,
                            shots, voice, sound, assembly)


# --- output profile ---------------------------------------------

def test_output_profile():
    _, _, _, _, _, _, _ = load_example()
    base = {"format": "mp4", "aspect_ratio": "9:16", "width": 1080,
            "height": 1920, "frame_rate": 30, "video_codec": "h264",
            "audio_codec": "aac", "audio_channels": 2,
            "audio_sample_rate": 48000, "duration_min_seconds": 30,
            "duration_max_seconds": 60}
    check("profile-valid", vp.validate_output_profile(base) == [])
    for field, bad in (
            ("format", "mov"), ("aspect_ratio", "16:9"),
            ("width", 1920), ("height", 1080), ("frame_rate", 24),
            ("video_codec", "vp9"), ("audio_codec", "mp3"),
            ("audio_channels", 1), ("audio_sample_rate", 22050)):
        mutated = dict(base)
        mutated[field] = bad
        check(f"profile-bad-{field}",
              len(vp.validate_output_profile(mutated)) > 0)
    mutated = dict(base)
    mutated["duration_max_seconds"] = 10
    check("profile-bad-duration-window",
          len(vp.validate_output_profile(mutated)) > 0)
    check("profile-not-object",
          len(vp.validate_output_profile("nope")) > 0)


def test_audio_profile():
    base = {"id": "p1006-audio-profile", "target_loudness_lufs": -16.0,
            "target_true_peak_dbfs": -1.0, "voice_priority": True,
            "music_duck_db": -12.0, "fade_in_seconds": 0.5,
            "fade_out_seconds": 1.0}
    check("audio-profile-valid",
          vp.validate_audio_profile(base) == [])
    for field, bad in (
            ("target_loudness_lufs", 0.5),
            ("target_true_peak_dbfs", 1.0),
            ("music_duck_db", 3.0),
            ("voice_priority", False),
            ("fade_in_seconds", -1.0)):
        mutated = dict(base)
        mutated[field] = bad
        check(f"audio-profile-bad-{field}",
              len(vp.validate_audio_profile(mutated)) > 0)


# --- project build ----------------------------------------------

def test_build_reference():
    session = fresh_session()
    project = build_reference(session)
    check("build-state", project["state"] == "PROJECT_VALIDATED")
    check("build-job-id", project["job_id"]
          == "job-p1006-vertical-explainer")
    check("build-script-lines", len(project["script"]["lines"]) == 6)
    check("build-script-hash",
          len(project["script"]["hash"]) == 64)
    check("build-shots", len(project["shots"]) == 6)
    check("build-no-failure", project["failure"] is None)
    check("build-validate-clean",
          vp.validate_project(project, require_adapters=False) == [])


def test_script_preservation():
    session = fresh_session()
    project_config, lines, analysis, shots, voice, sound, assembly = \
        load_example()
    tampered = copy.deepcopy(lines)
    tampered[0]["text"] = "Different words entirely."
    expect_error("script-text-mismatch-refused",
                 lambda: vp.build_project(
                     session, project_config, tampered, analysis,
                     shots, voice, sound, assembly))
    duplicated = copy.deepcopy(lines)
    duplicated.append(copy.deepcopy(duplicated[0]))
    expect_error("script-duplicate-line-refused",
                 lambda: vp.build_project(
                     session, project_config, duplicated, analysis,
                     shots, voice, sound, assembly))
    missing = copy.deepcopy(lines)
    del missing[2]
    expect_error("script-missing-line-refused",
                 lambda: vp.build_project(
                     session, project_config, missing, analysis,
                     shots, voice, sound, assembly))
    missing_voice = copy.deepcopy(voice)
    del missing_voice["lines"][2]
    expect_error("voice-missing-line-refused",
                 lambda: vp.build_project(
                     session, project_config, lines, analysis,
                     shots, missing_voice, sound, assembly))
    bad_seed = copy.deepcopy(voice)
    bad_seed["seed"] = "forty-two"
    expect_error("voice-bad-seed-refused",
                 lambda: vp.build_project(
                     session, project_config, lines, analysis,
                     shots, bad_seed, sound, assembly))
    commercial = copy.deepcopy(voice)
    commercial["commercial_use"] = "commercial"
    expect_error("voice-commercial-refused",
                 lambda: vp.build_project(
                     session, project_config, lines, analysis,
                     shots, commercial, sound, assembly))


def test_identity_and_decisions():
    session = fresh_session()
    project_config, lines, analysis, shots, voice, sound, assembly = \
        load_example()
    with_resolutions = copy.deepcopy(analysis)
    with_resolutions["character_resolutions"] = [{
        "character_ref": "char-001", "resolution": "approved"}]
    expect_error("identity-without-policy-refused",
                 lambda: vp.build_project(
                     session, project_config, lines, with_resolutions,
                     shots, voice, sound, assembly))
    with_questions = copy.deepcopy(analysis)
    with_questions["open_questions"] = ["which voice?"]
    expect_error("open-questions-refused",
                 lambda: vp.build_project(
                     session, project_config, lines, with_questions,
                     shots, voice, sound, assembly))
    undecided = copy.deepcopy(project_config)
    undecided["provenance"] = dict(project_config["provenance"])
    undecided["provenance"]["sound_plan"] = "NEEDS_USER_DECISION"
    expect_error("unresolved-decision-refused",
                 lambda: vp.build_project(
                     session, undecided, lines, analysis,
                     shots, voice, sound, assembly))
    report = vp.validation_report({"project_id": "p1006-x"},
                                  ["provenance.sound_plan is "
                                   "NEEDS_USER_DECISION: a required "
                                   "user decision is unresolved"])
    check("report-decisions-listed",
          len(report["decisions_needed"]) == 1
          and report["valid"] is False)


def test_shots_and_assembly():
    session = fresh_session()
    project_config, lines, analysis, shots, voice, sound, assembly = \
        load_example()
    no_direction = copy.deepcopy(shots)
    del no_direction[0]["visual_direction"]
    expect_error("shot-no-direction-refused",
                 lambda: vp.build_project(
                     session, project_config, lines, analysis,
                     no_direction, voice, sound, assembly))
    bad_recipe = copy.deepcopy(shots)
    bad_recipe[0]["visual"] = {"kind": "neural-render",
                              "colors": ["000000", "ffffff"]}
    expect_error("shot-unknown-recipe-refused",
                 lambda: vp.build_project(
                     session, project_config, lines, analysis,
                     bad_recipe, voice, sound, assembly))
    bad_line = copy.deepcopy(shots)
    bad_line[0]["line_id"] = "l99"
    expect_error("shot-unresolved-line-refused",
                 lambda: vp.build_project(
                     session, project_config, lines, analysis,
                     bad_line, voice, sound, assembly))
    montage = copy.deepcopy(assembly)
    montage["render_path"] = "openmontage"
    expect_error("assembly-openmontage-refused",
                 lambda: vp.build_project(
                     session, project_config, lines, analysis,
                     shots, voice, sound, montage))
    bad_codec = copy.deepcopy(assembly)
    bad_codec["video_codec"] = "vp9"
    expect_error("assembly-codec-mismatch-refused",
                 lambda: vp.build_project(
                     session, project_config, lines, analysis,
                     shots, voice, sound, bad_codec))


# --- state machine (Phase F) ------------------------------------

def _failure():
    return {"code": "local-tool-error", "message": "ffmpeg exited 1",
            "recovery": "inspect the render log and re-run assembly"}


def test_state_machine():
    session = fresh_session()
    project = build_reference(session)
    moved = vp.transition_project(session, project, "ASSETS_PENDING",
                                  reason="start assets")
    check("state-forward", moved["state"] == "ASSETS_PENDING")
    check("state-input-unchanged",
          project["state"] == "PROJECT_VALIDATED")
    expect_error("state-skip-refused",
                 lambda: vp.transition_project(
                     session, moved, "DELIVERED", reason="skip"))
    expect_error("state-same-refused",
                 lambda: vp.transition_project(
                     session, moved, "ASSETS_PENDING", reason="again"))
    expect_error("state-unknown-refused",
                 lambda: vp.transition_project(
                     session, moved, "EDITING", reason="nope"))
    ready = vp.transition_project(session, moved, "ASSETS_READY",
                                  reason="assets done")
    rerun = vp.transition_project(session, ready, "ASSETS_PENDING",
                                  reason="regenerate one asset")
    check("state-idempotent-rerun",
          rerun["state"] == "ASSETS_PENDING")
    expect_error("state-failed-needs-record",
                 lambda: vp.transition_project(
                     session, rerun, "FAILED", reason="boom"))
    failed = vp.transition_project(session, rerun, "FAILED",
                                   reason="render failed",
                                   failure=_failure())
    check("state-failed", failed["state"] == "FAILED"
          and failed["failure"]["code"] == "local-tool-error")
    expect_error("state-terminal-refused",
                 lambda: vp.transition_project(
                     session, failed, "ASSETS_PENDING", reason="retry"))
    bad_code = dict(_failure())
    bad_code["code"] = "not-a-code"
    expect_error("state-bad-failure-code-refused",
                 lambda: vp.transition_project(
                     session, rerun, "FAILED", reason="boom",
                     failure=bad_code))
    no_recovery = dict(_failure())
    del no_recovery["recovery"]
    expect_error("state-failure-needs-recovery",
                 lambda: vp.transition_project(
                     session, rerun, "FAILED", reason="boom",
                     failure=no_recovery))


def test_blocked_and_decision():
    session = fresh_session()
    project = build_reference(session)
    pending = vp.transition_project(session, project, "ASSETS_PENDING",
                                    reason="start assets")
    blocked = vp.transition_project(session, pending, "BLOCKED",
                                    reason="disk full")
    check("state-blocked", blocked["state"] == "BLOCKED"
          and blocked["previous_state"] == "ASSETS_PENDING")
    expect_error("blocked-resume-wrong-state-refused",
                 lambda: vp.transition_project(
                     session, blocked, "VOICE_PENDING",
                     reason="wrong"))
    resumed = vp.transition_project(session, blocked, "ASSETS_PENDING",
                                    reason="disk freed")
    check("blocked-resume-ok", resumed["state"] == "ASSETS_PENDING")
    check("blocked-previous-cleared",
          resumed["previous_state"] is None)
    stuck = dict(blocked)
    stuck["blocked_gates"] = ["disk full"]
    expect_error("blocked-with-blockers-refused",
                 lambda: vp.transition_project(
                     session, stuck, "ASSETS_PENDING",
                     reason="still blocked"))
    expect_error("decision-needs-reason",
                 lambda: vp.transition_project(
                     session, pending, "NEEDS_USER_DECISION"))
    waiting = vp.transition_project(
        session, pending, "NEEDS_USER_DECISION",
        reason="which music bed?")
    check("state-decision", waiting["state"] == "NEEDS_USER_DECISION")
    expect_error("decision-resume-wrong-state-refused",
                 lambda: vp.transition_project(
                     session, waiting, "VOICE_PENDING",
                     reason="wrong"))
    back = vp.transition_project(session, waiting, "ASSETS_PENDING",
                                 reason="user chose the bed")
    check("decision-resume-ok", back["state"] == "ASSETS_PENDING")
    cancelled = vp.transition_project(session, waiting, "CANCELLED",
                                      reason="user cancelled")
    check("decision-cancel-ok", cancelled["state"] == "CANCELLED")


def test_checkpoints():
    session = fresh_session()
    project = build_reference(session)
    inputs = {"stage": "assets", "shots": 6}
    digest = vp.stage_input_hash(inputs)
    check("checkpoint-hash-stable",
          digest == vp.stage_input_hash(inputs))
    check("checkpoint-hash-length", len(digest) == 64)
    check("checkpoint-not-done",
          vp.stage_is_done(project, "assets", digest) is False)
    stamped = vp.stage_checkpoint(project, "assets", digest,
                                  {"assets": ["vis-s1"]})
    check("checkpoint-done",
          vp.stage_is_done(stamped, "assets", digest) is True)
    check("checkpoint-wrong-hash-not-done",
          vp.stage_is_done(stamped, "assets", "0" * 64) is False)
    check("checkpoint-wrong-stage-not-done",
          vp.stage_is_done(stamped, "voice", digest) is False)
    check("checkpoint-input-unchanged",
          project["checkpoints"] == [])


def test_persistence():
    session = fresh_session()
    project = build_reference(session)
    root = tempfile.mkdtemp(prefix="cf-p1006-store-")
    path = vp.save_project(session, root, project)
    check("store-saved", os.path.isfile(path))
    loaded = vp.load_project(root, project["job_id"],
                             project["project_id"])
    check("store-loaded", loaded["project_id"] == project["project_id"]
          and loaded["state"] == "PROJECT_VALIDATED")
    resumed = vp.resume_project(session, root, project["job_id"],
                                project["project_id"])
    check("store-resumed", resumed["project_id"]
          == project["project_id"])
    # A DELIVERED project cannot be resumed: build one by hand.
    done = copy.deepcopy(project)
    done["state"] = "DELIVERED"
    vp.save_project(session, root, done)
    expect_error("resume-delivered-refused",
                 lambda: vp.resume_project(
                     session, root, done["job_id"],
                     done["project_id"]))
    # Tampering with the stored record is caught by the store hash.
    record_path = os.path.join(root, "jobs",
                               project["job_id"] + ".json")
    with open(record_path) as handle:
        record = json.load(handle)
    record["job"]["state"] = "ASSETS_READY"
    with open(record_path, "w") as handle:
        json.dump(record, handle)
    try:
        production_store.load_production_job(
            root, project["job_id"], project["project_id"])
        check("store-tamper-caught", False,
              "tampered record loaded without error")
    except production_store.ProductionStoreError:
        check("store-tamper-caught", True)


def main():
    test_output_profile()
    test_audio_profile()
    test_build_reference()
    test_script_preservation()
    test_identity_and_decisions()
    test_shots_and_assembly()
    test_state_machine()
    test_blocked_and_decision()
    test_checkpoints()
    test_persistence()
    for session in _sessions:
        close_session(session)
    print(f"CF-P1-006-PROJECT: {_checks[0]} checks, "
          f"{len(failures)} failures")
    if failures:
        print("FAILURES:", failures)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
