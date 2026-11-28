#!/usr/bin/env python3
"""P1-006 timeline tests (CF-WO-P1-006, Phase E).

Canonical timeline generation, shot-schedule arithmetic,
multi-clip / multi-track structure, transitions, trim points,
overlap and gap validation, the 9:16 profile, wrong-geometry
rejection, and assembly refusal on invalid input. The real
render tests live in tests/test_p1006_assembly.py.
"""

import copy
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
ROOT_ABS = os.path.abspath(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
from runtime import production_assets as pa  # noqa: E402
from runtime import production_timeline as tl  # noqa: E402

failures = []
_checks = [0]


def check(name, cond, detail=""):
    _checks[0] += 1
    if cond:
        print(f"PASS {name}")
    else:
        print(f"FAIL {name} {detail}")
        failures.append(name)


def expect_error(label, fn):
    try:
        fn()
    except tl.TimelineError:
        check(label, True)
        return
    except Exception as exc:  # noqa: BLE001 - any other error is a fail
        check(label, False, f"raised {type(exc).__name__}: {exc}")
        return
    check(label, False, "operation succeeded instead of refusing")


PROFILE = {"format": "mp4", "aspect_ratio": "9:16", "width": 1080,
           "height": 1920, "frame_rate": 30, "video_codec": "h264",
           "audio_codec": "aac", "audio_channels": 2,
           "audio_sample_rate": 48000, "duration_min_seconds": 30,
           "duration_max_seconds": 60}

VOICE_DURATIONS = {"l1": 4.2, "l2": 7.1, "l3": 5.4,
                   "l4": 6.0, "l5": 5.1, "l6": 4.6}

SHOTS = [{"shot_id": f"s{i}", "line_id": f"l{i}"} for i in range(1, 7)]
MIN_DURATIONS = {f"s{i}": 3.0 for i in range(1, 7)}


def verified_record(asset_id, asset_type="video-clip", **fields):
    record = pa.new_asset_record(
        asset_id=asset_id, project_id="p1006-vertical-explainer",
        shot_id=None, asset_type=asset_type,
        provider="ffmpeg-local", provider_status="EXERCISED",
        path=f"{asset_id}.mp4",
        mime_type="video/mp4" if asset_type == "video-clip"
        else "audio/wav",
        provenance="INFERRED_FOR_PRODUCTION")
    record["status"] = "VERIFIED"
    record["width"] = 1080
    record["height"] = 1920
    record["frame_rate"] = 30.0
    record.update(fields)
    return record


def fixture_registry():
    registry = {}
    schedule = tl.compute_shot_schedule(
        VOICE_DURATIONS, SHOTS, MIN_DURATIONS)
    for shot in schedule["shots"]:
        registry[f"vis-{shot['shot_id']}"] = verified_record(
            f"vis-{shot['shot_id']}",
            duration_seconds=shot["duration_seconds"])
    for line_id, duration in VOICE_DURATIONS.items():
        registry[f"voice-{line_id}"] = verified_record(
            f"voice-{line_id}", asset_type="audio-voice",
            duration_seconds=duration)
    registry["music-bed"] = verified_record(
        "music-bed", asset_type="audio-music",
        duration_seconds=schedule["total_seconds"])
    registry["room-tone"] = verified_record(
        "room-tone", asset_type="audio-room-tone",
        duration_seconds=schedule["total_seconds"])
    registry["sfx-whoosh"] = verified_record(
        "sfx-whoosh", asset_type="audio-sfx", duration_seconds=0.8)
    return registry, schedule


def fixture_project():
    return {
        "project_id": "p1006-vertical-explainer",
        "output_profile": dict(PROFILE),
        "audio_profile": {"id": "p1006-audio-profile"},
        "narrator": {"role": "NARRATOR_OR_VOICE_OVER",
                     "language": "en-US"},
        "provenance": {"script": "EXPLICIT_FROM_USER"},
        "shots": [{"shot_id": f"s{i}", "line_id": f"l{i}",
                   "min_duration_seconds": 3.0}
                  for i in range(1, 7)],
    }


# --- schedule arithmetic -----------------------------------------

def test_schedule():
    schedule = tl.compute_shot_schedule(
        VOICE_DURATIONS, SHOTS, MIN_DURATIONS)
    check("schedule-total",
          schedule["total_seconds"] == 37.4)
    shots = schedule["shots"]
    check("schedule-count", len(shots) == 6)
    check("schedule-first-start",
          shots[0]["timeline_start_seconds"] == 0.0)
    check("schedule-first-voice",
          shots[0]["voice_start_seconds"] == 1.0)
    for index in range(5):
        gap = shots[index + 1]["voice_start_seconds"] - (
            shots[index]["voice_start_seconds"]
            + shots[index]["voice_duration_seconds"])
        check(f"schedule-gap-s{index + 1}", round(gap, 3) == 0.5)
    tail = schedule["total_seconds"] - (
        shots[5]["voice_start_seconds"]
        + shots[5]["voice_duration_seconds"])
    check("schedule-tail", round(tail, 3) == 1.5)
    # The minimum-duration floor holds a shot open.
    long_min = dict(MIN_DURATIONS)
    long_min["s1"] = 9.0
    floored = tl.compute_shot_schedule(
        VOICE_DURATIONS, SHOTS, long_min)
    check("schedule-min-floor",
          floored["shots"][0]["duration_seconds"] == 9.0)
    check("schedule-min-total",
          floored["total_seconds"] == 37.4 + 4.0)
    expect_error("schedule-missing-duration-refused",
                 lambda: tl.compute_shot_schedule(
                     {"l1": 4.2}, SHOTS, MIN_DURATIONS))
    expect_error("schedule-zero-duration-refused",
                 lambda: tl.compute_shot_schedule(
                     dict(VOICE_DURATIONS, l1=0), SHOTS,
                     MIN_DURATIONS))
    expect_error("schedule-empty-refused",
                 lambda: tl.compute_shot_schedule({}, [], {}))


# --- canonical timeline ------------------------------------------

def test_build_timeline():
    registry, schedule = fixture_registry()
    timeline = tl.build_canonical_timeline(
        fixture_project(), registry, VOICE_DURATIONS)
    check("timeline-id",
          timeline["id"] == "timeline-p1006-vertical-explainer")
    check("timeline-format", timeline["format"] == "editor_neutral_v1")
    check("timeline-duration",
          timeline["duration_seconds"] == schedule["total_seconds"])
    check("timeline-profile-9-16",
          timeline["output_profile"]["aspect_ratio"] == "9:16"
          and timeline["output_profile"]["width"] == 1080
          and timeline["output_profile"]["height"] == 1920
          and timeline["output_profile"]["frame_rate"] == 30)
    check("timeline-video-clips",
          len(timeline["video_tracks"][0]["clips"]) == 6)
    check("timeline-voice-clips",
          len(timeline["audio_tracks"][0]["clips"]) == 6)
    check("timeline-sfx-clips",
          len(timeline["audio_tracks"][3]["clips"]) == 5)
    check("timeline-transitions",
          len(timeline["transitions"]) == 5
          and all(t["type"] == "fadeblack"
                  for t in timeline["transitions"]))
    check("timeline-intentional-silence",
          len(timeline["intentional_silences"]) == 1
          and timeline["intentional_silences"][0]["duration_seconds"]
          == 1.5)
    check("timeline-deterministic-hash",
          tl.timeline_hash(timeline) == tl.timeline_hash(timeline))
    check("timeline-validates",
          tl.validate_canonical_timeline(timeline, registry) == [])
    # Missing visual asset is a build error, never a substitution.
    missing = dict(registry)
    del missing["vis-s3"]
    expect_error("timeline-missing-visual-refused",
                 lambda: tl.build_canonical_timeline(
                     fixture_project(), missing, VOICE_DURATIONS))
    unverified = dict(registry)
    stale = dict(unverified["vis-s2"])
    stale["status"] = "GENERATED"
    unverified["vis-s2"] = stale
    expect_error("timeline-unverified-refused",
                 lambda: tl.build_canonical_timeline(
                     fixture_project(), unverified, VOICE_DURATIONS))
    short = dict(registry)
    clip = dict(short["vis-s1"])
    clip["duration_seconds"] = 1.0
    short["vis-s1"] = clip
    expect_error("timeline-short-clip-refused",
                 lambda: tl.build_canonical_timeline(
                     fixture_project(), short, VOICE_DURATIONS))


def test_filter_chain():
    timeline = {"video_tracks": [{"clips": [
        {"duration_seconds": 5.0}, {"duration_seconds": 8.0},
        {"duration_seconds": 6.0}]}],
        "transitions": [{"duration_seconds": 0.3},
                        {"duration_seconds": 0.3}]}
    chain = tl.video_filter_chain(timeline)
    check("chain-offsets",
          "offset=4.700" in chain and "offset=12.400" in chain)
    check("chain-fadeblack", "transition=fadeblack" in chain)
    check("chain-output", chain.endswith("[xv]format=yuv420p[vout]"))
    single = {"video_tracks": [{"clips": [{"duration_seconds": 5.0}]}],
              "transitions": []}
    check("chain-single",
          tl.video_filter_chain(single)
          == "[0:v]format=yuv420p[vout]")


# --- validation ---------------------------------------------------

def test_validate_timeline():
    registry, _ = fixture_registry()
    timeline = tl.build_canonical_timeline(
        fixture_project(), registry, VOICE_DURATIONS)
    check("validate-clean",
          tl.validate_canonical_timeline(timeline, registry) == [])
    # Video gap: move a clip start.
    gapped = copy.deepcopy(timeline)
    gapped["video_tracks"][0]["clips"][2]["timeline_start_seconds"] += 1.0
    check("validate-video-gap",
          len(tl.validate_canonical_timeline(gapped, registry)) > 0)
    # Audio overlap inside one track.
    overlapped = copy.deepcopy(timeline)
    overlapped["audio_tracks"][0]["clips"][1][
        "timeline_start_seconds"] = overlapped["audio_tracks"][0][
        "clips"][0]["timeline_start_seconds"] + 0.5
    check("validate-audio-overlap",
          len(tl.validate_canonical_timeline(overlapped, registry)) > 0)
    # Trim beyond the source.
    bad_trim = copy.deepcopy(timeline)
    bad_trim["video_tracks"][0]["clips"][0]["source_end_seconds"] = 99.0
    check("validate-trim-beyond-source",
          len(tl.validate_canonical_timeline(bad_trim, registry)) > 0)
    # Audio extending beyond the timeline.
    long_audio = copy.deepcopy(timeline)
    long_audio["audio_tracks"][0]["clips"][5]["duration_seconds"] = 99.0
    check("validate-audio-beyond-timeline",
          len(tl.validate_canonical_timeline(long_audio, registry)) > 0)
    # Wrong geometry on a video asset.
    wrong_geo = dict(registry)
    clip = dict(wrong_geo["vis-s1"])
    clip["width"] = 720
    clip["height"] = 1280
    wrong_geo["vis-s1"] = clip
    check("validate-wrong-geometry",
          len(tl.validate_canonical_timeline(timeline, wrong_geo)) > 0)
    # Unregistered clip.
    missing = dict(registry)
    del missing["voice-l3"]
    check("validate-unregistered-clip",
          len(tl.validate_canonical_timeline(timeline, missing)) > 0)
    # Bad transition type.
    bad_transition = copy.deepcopy(timeline)
    bad_transition["transitions"][0]["type"] = "wipe"
    check("validate-bad-transition",
          len(tl.validate_canonical_timeline(bad_transition,
                                            registry)) > 0)
    # Duration sum disagreement.
    bad_total = copy.deepcopy(timeline)
    bad_total["duration_seconds"] = 99.0
    check("validate-duration-sum",
          len(tl.validate_canonical_timeline(bad_total, registry)) > 0)
    check("validate-not-object",
          len(tl.validate_canonical_timeline("nope", registry)) > 0)


def test_assemble_refuses_invalid():
    import tempfile
    from runtime import local_session
    from runtime.local_session import (
        close_session, load_or_create_profile, start_session)
    root = tempfile.mkdtemp(prefix="cf-p1006-timeline-")
    profile = load_or_create_profile(root)
    session = start_session(profile, profile.workspace_id)
    try:
        registry, _ = fixture_registry()
        timeline = tl.build_canonical_timeline(
            fixture_project(), registry, VOICE_DURATIONS)
        broken = copy.deepcopy(timeline)
        broken["video_tracks"][0]["clips"][0][
            "timeline_start_seconds"] = 5.0
        expect_error("assemble-invalid-timeline-refused",
                     lambda: tl.assemble_timeline(
                         session, fixture_project(), broken, registry,
                         "/tmp", "/tmp", "/tmp/out.mp4"))
        expect_error("assemble-needs-session",
                     lambda: tl.assemble_timeline(
                         None, fixture_project(), timeline, registry,
                         "/tmp", "/tmp", "/tmp/out.mp4"))
    finally:
        close_session(session)


def main():
    test_schedule()
    test_build_timeline()
    test_filter_chain()
    test_validate_timeline()
    test_assemble_refuses_invalid()
    print(f"CF-P1-006-TIMELINE: {_checks[0]} checks, "
          f"{len(failures)} failures")
    if failures:
        print("FAILURES:", failures)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
