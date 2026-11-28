#!/usr/bin/env python3
"""P1-006 assembly tests (CF-WO-P1-006, Phase E).

The assembler is exercised for real: a two-shot fixture project
is rendered to an actual MP4 with FFmpeg, and the output is
probed. Voice lines here are sine-tone test fixtures — the
assembler test proves the render path, not the voice; the real
VoiceStudio narration is exercised in the end-to-end test.

Resume is stage-level (the Phase F checkpoint keyed by input
hash): a completed assembly stage with unchanged inputs is done
and is not re-run. The assembler itself re-renders on each call;
a second render must produce a valid MP4 with identical probe
facts. Mid-render cancellation is NOT supported (the FFmpeg
subprocess runs to completion); a closed session refuses to
start assembly at all.
"""

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(__file__), "..")
ROOT_ABS = os.path.abspath(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
from runtime import production_assets as pa  # noqa: E402
from runtime import production_audio as aud  # noqa: E402
from runtime import production_timeline as tl  # noqa: E402
from runtime import vertical_production as vp  # noqa: E402
from runtime.local_session import (  # noqa: E402
    close_session, load_or_create_profile, start_session)

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
    except (tl.TimelineError, pa.AssetError):
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
AUDIO_PROFILE = {"id": "p1006-audio-profile",
                 "target_loudness_lufs": -16.0,
                 "target_true_peak_dbfs": -1.0,
                 "voice_priority": True, "music_duck_db": -12.0,
                 "fade_in_seconds": 0.5, "fade_out_seconds": 1.0}
VOICE_DURATIONS = {"l1": 2.0, "l2": 2.0}
SHOTS = [{"shot_id": "s1", "line_id": "l1"},
         {"shot_id": "s2", "line_id": "l2"}]
MIN_DURATIONS = {"s1": 3.0, "s2": 3.0}


def _run(argv, label):
    proc = subprocess.run(argv, capture_output=True, text=True,
                          timeout=300)
    if proc.returncode != 0:
        raise AssertionError(
            f"{label} failed: {(proc.stderr or '')[:400]}")


def _tone_wav(path, duration, freq=440.0):
    _run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
          f"sine=frequency={freq}:duration={duration}:sample_rate=48000",
          "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le",
          "-t", str(duration), path], "tone synthesis")


def _register(root, asset_id, asset_type, path, mime_type):
    record = pa.new_asset_record(
        asset_id=asset_id, project_id="p1006-assembly-test",
        shot_id=None, asset_type=asset_type,
        provider="ffmpeg-local", provider_status="EXERCISED",
        path=os.path.basename(path), mime_type=mime_type,
        provenance="INFERRED_FOR_PRODUCTION")
    return pa.verify_asset(record, root)


def build_fixture(root):
    """Two-shot fixture: real visuals, tone voice, synth beds."""
    schedule = tl.compute_shot_schedule(
        VOICE_DURATIONS, SHOTS, MIN_DURATIONS)
    total = schedule["total_seconds"]
    registry = {}
    for shot in schedule["shots"]:
        shot_id = shot["shot_id"]
        recipe = {"kind": "gradient-band" if shot_id == "s1"
                  else "gradient-split",
                  "colors": ["1a2b4c", "3d6e9e"] if shot_id == "s1"
                  else ["4c1a2b", "9e3d6e"],
                  "accent_color": "ffffff", "keyword": "TEST"}
        path = os.path.join(root, f"vis-{shot_id}.mp4")
        pa.generate_visual_asset(
            recipe, shot["duration_seconds"], path,
            asset_id=f"vis-{shot_id}",
            project_id="p1006-assembly-test", shot_id=shot_id)
        registry[f"vis-{shot_id}"] = _register(
            root, f"vis-{shot_id}", "video-clip", path, "video/mp4")
    for line_id, duration in VOICE_DURATIONS.items():
        path = os.path.join(root, f"voice-{line_id}.wav")
        _tone_wav(path, duration)
        registry[f"voice-{line_id}"] = _register(
            root, f"voice-{line_id}", "audio-voice", path,
            "audio/wav")
    music = os.path.join(root, "music-bed.wav")
    aud.synthesize_music_bed(total, music)
    registry["music-bed"] = _register(
        root, "music-bed", "audio-music", music, "audio/wav")
    room = os.path.join(root, "room-tone.wav")
    aud.synthesize_room_tone(total, room)
    registry["room-tone"] = _register(
        root, "room-tone", "audio-room-tone", room, "audio/wav")
    sfx = os.path.join(root, "sfx-whoosh.wav")
    aud.synthesize_whoosh(0.8, sfx)
    registry["sfx-whoosh"] = _register(
        root, "sfx-whoosh", "audio-sfx", sfx, "audio/wav")
    project = {
        "project_id": "p1006-assembly-test",
        "output_profile": dict(PROFILE),
        "audio_profile": dict(AUDIO_PROFILE),
        "narrator": {"role": "NARRATOR_OR_VOICE_OVER",
                     "language": "en-US"},
        "provenance": {"script": "EXPLICIT_FROM_USER"},
        "shots": [{"shot_id": s["shot_id"], "line_id": s["line_id"],
                   "min_duration_seconds": 3.0} for s in SHOTS],
    }
    timeline = tl.build_canonical_timeline(
        project, registry, VOICE_DURATIONS)
    return project, timeline, registry, schedule


def _probe(path):
    return pa.probe_media_file(path)


def test_successful_render(session):
    root = tempfile.mkdtemp(prefix="cf-p1006-assembly-")
    try:
        project, timeline, registry, schedule = build_fixture(root)
        out = os.path.join(root, "final.mp4")
        record = tl.assemble_timeline(
            session, project, timeline, registry, root, root, out)
        check("assemble-output-exists",
              os.path.isfile(out) and record["size_bytes"] > 0)
        probe = _probe(out)
        check("assemble-geometry",
              probe["width"] == 1080 and probe["height"] == 1920)
        check("assemble-fps",
              probe["frame_rate_rational"] == "30/1")
        check("assemble-codecs",
              probe["video_codec"] == "h264"
              and probe["audio_codec"] == "aac")
        check("assemble-duration",
              probe["duration_seconds"] is not None
              and abs(probe["duration_seconds"]
                      - schedule["total_seconds"]) <= 0.15,
              f"got {probe['duration_seconds']}, "
              f"expected {schedule['total_seconds']}")
        check("assemble-audio-stream",
              len(probe["audio_streams"]) == 1
              and probe["channels"] == 2
              and probe["sample_rate"] == 48000)
        check("assemble-sha-matches",
              record["sha256"] == hashlib.sha256(
                  open(out, "rb").read()).hexdigest())
        check("assemble-size-matches",
              record["size_bytes"] == os.path.getsize(out))
        check("assemble-steps",
              [s["step"] for s in record["steps"]]
              == ["validate-timeline", "verify-assets", "mix-audio",
                  "render-video", "mux"])
        check("assemble-audio-mix",
              record["audio_mix"]["duration_seconds"] is not None
              and abs(record["audio_mix"]["duration_seconds"]
                      - schedule["total_seconds"]) <= 0.15)
        return root, project, timeline, registry, out, record
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_invalid_source(session):
    root = tempfile.mkdtemp(prefix="cf-p1006-assembly-bad-")
    try:
        project, timeline, registry, _ = build_fixture(root)
        os.remove(os.path.join(root, "vis-s2.mp4"))
        expect_error("assemble-missing-source-refused",
                     lambda: tl.assemble_timeline(
                         session, project, timeline, registry, root,
                         root, os.path.join(root, "out.mp4")))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_failed_render(session):
    root = tempfile.mkdtemp(prefix="cf-p1006-assembly-fail-")
    try:
        project, timeline, registry, _ = build_fixture(root)
        # The render step must fail closed when FFmpeg cannot
        # create the output file: the output's parent directory
        # does not exist (the assembler creates only the work
        # dir), so the render fails and no delivery is recorded.
        # (A 10-bit/8-bit pixel-format mismatch was tried first:
        # FFmpeg auto-converts formats, so the render succeeds
        # and is not a failure case.)
        expect_error("assemble-unwritable-output-refused",
                     lambda: tl.assemble_timeline(
                         session, project, timeline, registry, root,
                         root,
                         os.path.join(root, "no-such-dir",
                                      "out.mp4")))
        check("assemble-failed-render-no-output",
              not os.path.exists(
                  os.path.join(root, "no-such-dir", "out.mp4")))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_resume_and_idempotency(session):
    root = tempfile.mkdtemp(prefix="cf-p1006-assembly-resume-")
    try:
        project, timeline, registry, _ = build_fixture(root)
        out = os.path.join(root, "final.mp4")
        first = tl.assemble_timeline(
            session, project, timeline, registry, root, root, out)
        # Stage-level resume: the checkpoint says this input is
        # done, so a driver must not re-run the stage.
        input_hash = vp.stage_input_hash(
            {"timeline": tl.timeline_hash(timeline),
             "assets": sorted(registry)})
        project = vp.stage_checkpoint(
            project, "assembly", input_hash,
            {"output_path": out, "sha256": first["sha256"]})
        check("assemble-checkpoint-done",
              vp.stage_is_done(project, "assembly", input_hash))
        check("assemble-checkpoint-other-inputs-not-done",
              not vp.stage_is_done(
                  project, "assembly",
                  vp.stage_input_hash({"timeline": "different"})))
        # A second render call re-renders but must produce a
        # valid MP4 with identical probe facts.
        second = tl.assemble_timeline(
            session, project, timeline, registry, root, root, out)
        probe = _probe(out)
        check("assemble-second-render-valid",
              probe["width"] == 1080 and probe["height"] == 1920
              and probe["frame_rate_rational"] == "30/1"
              and second["sha256"] == hashlib.sha256(
                  open(out, "rb").read()).hexdigest())
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_cancelled_session_refused():
    root = tempfile.mkdtemp(prefix="cf-p1006-assembly-cancel-")
    try:
        project, timeline, registry, _ = build_fixture(root)
        profile = load_or_create_profile(root)
        session = start_session(profile, profile.workspace_id)
        close_session(session)
        expect_error("assemble-closed-session-refused",
                     lambda: tl.assemble_timeline(
                         session, project, timeline, registry, root,
                         root, os.path.join(root, "out.mp4")))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main():
    root = tempfile.mkdtemp(prefix="cf-p1006-assembly-session-")
    profile = load_or_create_profile(root)
    session = start_session(profile, profile.workspace_id)
    try:
        test_successful_render(session)
        test_invalid_source(session)
        test_failed_render(session)
        test_resume_and_idempotency(session)
        test_cancelled_session_refused()
    finally:
        close_session(session)
        shutil.rmtree(root, ignore_errors=True)
    print(f"CF-P1-006-ASSEMBLY: {_checks[0]} checks, "
          f"{len(failures)} failures")
    if failures:
        print("FAILURES:", failures)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
