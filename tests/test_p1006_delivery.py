#!/usr/bin/env python3
"""P1-006 Phase G + H tests: QC runtime and delivery runtime
(CF-WO-P1-006).

Covers runtime/production_qc.py (technical / visual / audio QC
plus the QC decision gate) and runtime/production_delivery.py
(delivery package, delivery manifest, SHA256SUMS, independent
verification).

FFmpeg/ffprobe are REQUIRED: when they are absent the suite
fails (exit 1) instead of skipping — a skipped media test is
not QC coverage. All media fixtures are generated locally with
FFmpeg lavfi sources (or the wave module) into tempfile dirs;
no media binary is committed and nothing is pushed anywhere.

Note on the 720x1280 geometry fixture: 720x1280 reduces to
exactly 9:16, so a correct aspect check PASSES it — only the
resolution check fails there. The aspect-fail path is covered
separately with a square 1080x1080 fixture.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import wave

ROOT = os.path.join(os.path.dirname(__file__), "..")
ROOT_ABS = os.path.abspath(ROOT)
sys.path.insert(0, ROOT)
from runtime import production_delivery as pd  # noqa: E402
from runtime import production_qc as qc  # noqa: E402
from runtime.production_assets import (  # noqa: E402
    hash_file, new_asset_record, probe_media_file)
from runtime.production_delivery import DeliveryError  # noqa: E402
from runtime.production_qc import QCError  # noqa: E402

failures = []
_checks = [0]

EXAMPLES = os.path.join(ROOT_ABS, "examples",
                        "p1006-vertical-explainer")


def check(name, cond, detail=""):
    _checks[0] += 1
    if cond:
        print(f"PASS {name}")
    else:
        print(f"FAIL {name} {detail}")
        failures.append(name)


def expect_error(label, error_types, fn):
    try:
        fn()
    except error_types:
        check(label, True)
        return
    except Exception as exc:  # noqa: BLE001 - any other error is a fail
        check(label, False, f"raised {type(exc).__name__}: {exc}")
        return
    check(label, False, "operation succeeded instead of refusing")


def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, payload):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def write_text(path, text):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def check_status(report, check_id):
    for entry in report.get("checks") or []:
        if entry.get("check_id") == check_id:
            return entry.get("status")
    return None


def run_ffmpeg(argv, timeout=300):
    proc = subprocess.run(argv, capture_output=True, text=True,
                          timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg failed: "
                           f"{(proc.stderr or '').strip()[:500]}")
    return proc


# ------------------------------------------------------------------
# Fixture builders (lavfi / wave only, tempfile dirs only)
# ------------------------------------------------------------------

def make_video(path, *, duration=5, width=1080, height=1920, fps=30,
               audio="sine", black=False, frozen=False):
    """One deterministic vertical clip.

    Video is scrolling SMPTE bars (cheap to encode, always
    moving, never black). ``audio="sine"`` adds a 440 Hz tone
    at -6 dB, ``"clipped"`` the same tone amplified into
    clipping, ``None`` adds no audio track. ``black`` blanks
    the frame 2–3 s with a scrolling 16 px colour strip inside
    the black (still >= 98% black pixels, but moving, so the
    freeze check stays silent). ``frozen`` covers the frame
    with a solid red box 2–4 s (identical frames: a real freeze).
    """
    inputs = ["-f", "lavfi", "-i",
              f"smptebars=size={width}x{height}:rate={fps}:"
              f"duration={duration}"]
    audio_index = None
    if black:
        inputs += ["-f", "lavfi", "-i",
                   f"smptebars=size={width}x16:rate={fps}:"
                   f"duration={duration}"]
        audio_index = 2
    elif audio is not None:
        audio_index = 1
    if audio is not None:
        inputs += ["-f", "lavfi", "-i",
                   f"sine=frequency=440:duration={duration}"]
    filters = [f"[0:v]scroll=v=0.005[v0]"]
    video_label = "v0"
    if black:
        filters.append(
            "[v0]drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:"
            "enable='between(t,2,3)'[base]")
        filters.append("[1:v]scroll=h=0.005[strip]")
        filters.append("[base][strip]overlay=0:100:"
                       "enable='between(t,2,3)'[v]")
        video_label = "v"
    elif frozen:
        filters.append(
            "[v0]drawbox=x=0:y=0:w=iw:h=ih:color=red:t=fill:"
            "enable='between(t,2,4)'[v]")
        video_label = "v"
    else:
        filters.append("[v0]null[v]")
        video_label = "v"
    argv = ["ffmpeg", "-y", "-v", "error", *inputs,
            "-filter_complex",
            ";".join(filters)
            + (f";[{audio_index}:a]"
               f"{'volume=0.5' if audio == 'sine' else 'volume=20dB'}[a]"
               if audio is not None else ""),
            "-map", f"[{video_label}]"]
    if audio is not None:
        argv += ["-map", "[a]", "-c:a", "aac"]
    argv += ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
             "-pix_fmt", "yuv420p", "-shortest", path]
    run_ffmpeg(argv)
    if not os.path.isfile(path):
        raise RuntimeError(f"fixture generation failed: {path}")


def make_silence_wav(path, *, seconds=5, rate=48000):
    """Stereo WAV: 1 s tone, 3 s digital silence, 1 s tone."""
    import math
    frames = bytearray()
    for index in range(rate * seconds):
        second = index / rate
        if 1.0 <= second < 4.0:
            sample = 0
        else:
            sample = int(12000 * math.sin(2 * math.pi * 440 * second))
        frames += sample.to_bytes(2, "little", signed=True) * 2
    with wave.open(path, "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(bytes(frames))


def make_timeline(*, duration=5.0, shots=None, voice_clips=None,
                  music=True, sfx=True, room_tone=True,
                  intentional_silences=None):
    """A timeline in the P1-006 contract shape."""
    if shots is None:
        shots = [("s1", 0.0, duration)]
    video_clips = [{
        "clip_id": f"clip-{shot_id}", "asset_id": f"clip-{shot_id}",
        "shot_id": shot_id, "source_start_seconds": 0.0,
        "source_end_seconds": shot_duration,
        "timeline_start_seconds": start,
        "duration_seconds": shot_duration, "operations": []}
        for shot_id, start, shot_duration in shots]
    audio_tracks = []
    if voice_clips is None:
        voice_clips = [{
            "clip_id": "clip-voice-l1", "asset_id": "voice-l1",
            "line_id": "l1", "shot_id": "s1",
            "timeline_start_seconds": 0.0,
            "duration_seconds": duration}]
    audio_tracks.append({"track_id": "voice", "kind": "dialogue",
                         "clips": voice_clips})
    if music:
        audio_tracks.append({"track_id": "music", "kind": "music",
                             "clips": [{
                                 "clip_id": "clip-music-bed",
                                 "asset_id": "music-bed",
                                 "timeline_start_seconds": 0.0,
                                 "duration_seconds": duration}]})
    if room_tone:
        audio_tracks.append({"track_id": "room-tone",
                             "kind": "room-tone",
                             "clips": [{
                                 "clip_id": "clip-room-tone",
                                 "asset_id": "room-tone",
                                 "timeline_start_seconds": 0.0,
                                 "duration_seconds": duration}]})
    if sfx:
        audio_tracks.append({"track_id": "sfx", "kind": "sfx",
                             "clips": [{
                                 "clip_id": "clip-sfx-whoosh",
                                 "asset_id": "sfx-whoosh",
                                 "cue_id": "sfx-whoosh-s2",
                                 "shot_id": "s1",
                                 "timeline_start_seconds": 2.0,
                                 "duration_seconds": 0.8}]})
    return {
        "schema_version": "2.5",
        "id": "timeline-p1006-test",
        "project_id": "p1006-vertical-explainer",
        "format": "editor_neutral_v1",
        "output_profile": load_json(
            os.path.join(EXAMPLES, "project.json"))["output_profile"],
        "duration_seconds": duration,
        "video_tracks": [{"track_id": "v1", "clips": video_clips}],
        "audio_tracks": audio_tracks,
        "transitions": [],
        "intentional_silences": intentional_silences or [],
        "provenance": {},
    }


def make_asset(asset_id, *, duration, sha, size, asset_type="audio-voice",
               license_class="original", path=None, mime_type="audio/wav"):
    """One asset record with measured values filled in."""
    record = new_asset_record(
        asset_id=asset_id, project_id="p1006-vertical-explainer",
        shot_id=None, asset_type=asset_type,
        provider="ffmpeg-local", provider_status="EXERCISED",
        path=path or f"{asset_id}.wav", mime_type=mime_type,
        license_class=license_class,
        license_note="Local test fixture.",
        privacy_class="internal", transmit_to_provider=False,
        provenance="INFERRED_FOR_PRODUCTION")
    record["duration_seconds"] = duration
    record["sha256"] = sha
    record["size_bytes"] = size
    record["status"] = "VERIFIED"
    return record


def run_checks():
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        print("FAIL CF-P1-006-QC-ffmpeg-required: ffmpeg and "
              "ffprobe are required for the QC/delivery tests; "
              "a skipped FFmpeg run is not coverage")
        return 1
    check("CF-P1-006-QC-ffmpeg-present",
          ffmpeg.startswith("/") and ffprobe.startswith("/"),
          f"{ffmpeg} / {ffprobe}")

    tmpdir = tempfile.mkdtemp(prefix="cf-p1006-delivery-")
    project_config = load_json(os.path.join(EXAMPLES, "project.json"))
    profile = project_config["output_profile"]
    audio_profile = project_config["audio_profile"]
    voice_lines = [{"line_id": "l1", "shot_id": "s1",
                    "text": "One character. Every scene."}]

    # ------------------------------------------------------------------
    # Technical QC
    # ------------------------------------------------------------------
    valid30 = os.path.join(tmpdir, "valid30.mp4")
    make_video(valid30, duration=30)
    report = qc.technical_qc(valid30, profile)
    check("CF-P1-006-QC-tech-valid-verdict",
          report["verdict"] == "pass",
          str([(c["check_id"], c["detail"]) for c in report["checks"]
               if c["status"] != "pass"]))
    check("CF-P1-006-QC-tech-valid-all-checks",
          all(c["status"] == "pass" for c in report["checks"])
          and len(report["checks"]) == 16,
          f"{len(report['checks'])} checks")
    measured = report["measured"]
    check("CF-P1-006-QC-tech-valid-measured",
          measured["width"] == 1080 and measured["height"] == 1920
          and measured["aspect_ratio"] == "9:16"
          and measured["frame_rate_rational"] == "30/1"
          and measured["frame_rate"] == 30
          and measured["video_codec"] == "h264"
          and measured["audio_codec"] == "aac"
          and measured["duration_seconds"] is not None
          and 30.0 <= measured["duration_seconds"] <= 60.0
          and measured["decode_errors"] == []
          and measured["size_bytes"] == os.path.getsize(valid30),
          str({k: measured.get(k) for k in
               ("width", "height", "aspect_ratio",
                "frame_rate_rational", "duration_seconds",
                "video_codec", "audio_codec")}))

    res720 = os.path.join(tmpdir, "res720.mp4")
    make_video(res720, duration=5, width=720, height=1280)
    report720 = qc.technical_qc(res720, profile)
    check("CF-P1-006-QC-tech-720-resolution-fails",
          check_status(report720, "resolution") == "fail"
          and report720["verdict"] == "fail",
          str(report720["verdict"]))
    check("CF-P1-006-QC-tech-720-aspect-is-9-16",
          check_status(report720, "aspect-ratio") == "pass",
          "720x1280 reduces to 9:16, so the aspect check "
          "correctly passes while resolution fails")
    square = os.path.join(tmpdir, "square.mp4")
    make_video(square, duration=5, width=1080, height=1080)
    report_square = qc.technical_qc(square, profile)
    check("CF-P1-006-QC-tech-square-aspect-fails",
          check_status(report_square, "aspect-ratio") == "fail"
          and check_status(report_square, "resolution") == "fail",
          str(report_square["verdict"]))

    fps24 = os.path.join(tmpdir, "fps24.mp4")
    make_video(fps24, duration=5, fps=24)
    report24 = qc.technical_qc(fps24, profile)
    check("CF-P1-006-QC-tech-24fps-fails",
          check_status(report24, "frame-rate") == "fail"
          and report24["measured"]["frame_rate_rational"] == "24/1",
          str(report24["measured"]["frame_rate_rational"]))

    dur10 = os.path.join(tmpdir, "dur10.mp4")
    make_video(dur10, duration=10)
    report10 = qc.technical_qc(dur10, profile)
    check("CF-P1-006-QC-tech-10s-duration-fails",
          check_status(report10, "duration") == "fail"
          and report10["verdict"] == "fail",
          str(report10["measured"]["duration_seconds"]))

    noaudio = os.path.join(tmpdir, "noaudio.mp4")
    make_video(noaudio, duration=5, audio=None)
    report_noaudio = qc.technical_qc(noaudio, profile)
    check("CF-P1-006-QC-tech-noaudio-fails",
          check_status(report_noaudio, "audio-stream") == "fail"
          and report_noaudio["verdict"] == "fail")

    black30 = os.path.join(tmpdir, "black30.mp4")
    make_video(black30, duration=30, black=True)
    report_black = qc.technical_qc(black30, profile)
    check("CF-P1-006-QC-tech-black-unrecorded-fails",
          check_status(report_black, "black-gaps") == "fail"
          and report_black["verdict"] == "fail",
          str([c["detail"] for c in report_black["checks"]
               if c["check_id"] == "black-gaps"]))
    report_black_ok = qc.technical_qc(
        black30, profile,
        intentional_silences=[{
            "silence_id": "black-gap",
            "timeline_start_seconds": 2.0, "duration_seconds": 1.0,
            "reason": "Recorded intentional black gap for the test."}])
    check("CF-P1-006-QC-tech-black-intentional-passes",
          check_status(report_black_ok, "black-gaps") == "pass"
          and report_black_ok["verdict"] == "pass",
          str([(c["check_id"], c["detail"]) for c in
               report_black_ok["checks"] if c["status"] != "pass"]))
    check("CF-P1-006-QC-tech-black-no-freeze",
          check_status(report_black_ok, "frozen-segments") == "pass",
          "the black segment moves, so it must not read as frozen")

    frozen5 = os.path.join(tmpdir, "frozen5.mp4")
    make_video(frozen5, duration=5, frozen=True)
    report_frozen = qc.technical_qc(frozen5, profile)
    check("CF-P1-006-QC-tech-frozen-fails",
          check_status(report_frozen, "frozen-segments") == "fail"
          and report_frozen["verdict"] == "fail",
          str([c["detail"] for c in report_frozen["checks"]
               if c["check_id"] == "frozen-segments"]))

    corrupt = os.path.join(tmpdir, "corrupt.mp4")
    with open(valid30, "rb") as handle:
        head = handle.read(2000)
    with open(corrupt, "wb") as handle:
        handle.write(head)
    report_corrupt = qc.technical_qc(corrupt, profile)
    check("CF-P1-006-QC-tech-corrupt-fails",
          report_corrupt["verdict"] == "fail"
          and check_status(report_corrupt, "mp4-container") == "fail",
          str(report_corrupt["verdict"]))
    report_missing = qc.technical_qc(
        os.path.join(tmpdir, "does-not-exist.mp4"), profile)
    check("CF-P1-006-QC-tech-missing-file-fails",
          report_missing["verdict"] == "fail"
          and check_status(report_missing, "file-exists") == "fail")

    expect_error("CF-P1-006-QC-tech-missing-tool-raises", (QCError,),
                 lambda: qc.technical_qc(
                     valid30, profile, ffmpeg="ffmpeg-no-such-binary"))
    expect_error("CF-P1-006-QC-tech-incomplete-profile-raises",
                 (QCError,),
                 lambda: qc.technical_qc(valid30, {"width": 1080}))

    # ------------------------------------------------------------------
    # Visual QC
    # ------------------------------------------------------------------
    visual6 = os.path.join(tmpdir, "visual6.mp4")
    make_video(visual6, duration=6)
    shots6 = [(f"s{i}", float(i - 1), 1.0) for i in range(1, 7)]
    timeline6 = make_timeline(duration=6.0, shots=shots6)
    out_dir = os.path.join(tmpdir, "visual-qc")
    visual_report = qc.visual_qc(visual6, timeline6, out_dir)
    check("CF-P1-006-QC-visual-keyframes",
          len(visual_report["keyframes"]) == 6
          and [k["shot_id"] for k in visual_report["keyframes"]]
          == [f"s{i}" for i in range(1, 7)]
          and all(os.path.isfile(
              os.path.join(out_dir, k["path"]))
              for k in visual_report["keyframes"]),
          str(visual_report["keyframes"]))
    check("CF-P1-006-QC-visual-keyframe-midpoints",
          [k["at_seconds"] for k in visual_report["keyframes"]]
          == [0.5, 1.5, 2.5, 3.5, 4.5, 5.5],
          str([k["at_seconds"] for k in visual_report["keyframes"]]))
    sheet_path = os.path.join(out_dir, visual_report["contact_sheet"])
    check("CF-P1-006-QC-visual-contact-sheet-exists",
          os.path.isfile(sheet_path),
          visual_report["contact_sheet"])
    sheet_probe = probe_media_file(sheet_path)
    check("CF-P1-006-QC-visual-contact-sheet-geometry",
          sheet_probe["width"] == 1080
          and sheet_probe["height"] == 2880,
          f"{sheet_probe['width']}x{sheet_probe['height']}")
    check("CF-P1-006-QC-visual-shot-summary",
          visual_report["shot_summary"]
          == [{"shot_id": f"s{i}", "timeline_start_seconds": float(i - 1),
               "duration_seconds": 1.0, "asset_id": f"clip-s{i}"}
              for i in range(1, 7)],
          str(visual_report["shot_summary"]))
    check("CF-P1-006-QC-visual-no-crop",
          visual_report["aspect_crop_report"]["cropped"] is False
          and visual_report["aspect_crop_report"]["width"] == 1080
          and visual_report["aspect_crop_report"]["height"] == 1920
          and visual_report["aspect_crop_report"]["aspect_ratio"]
          == "9:16",
          str(visual_report["aspect_crop_report"]))
    check("CF-P1-006-QC-visual-human-review",
          visual_report["human_review_required"] is True
          and visual_report["editorial_approval"] is None,
          str((visual_report["human_review_required"],
               visual_report["editorial_approval"])))
    check("CF-P1-006-QC-visual-black-report-clean",
          visual_report["black_frame_report"]["unexpected"] == []
          and visual_report["black_frame_report"]["segments"] == [],
          str(visual_report["black_frame_report"]))

    # ------------------------------------------------------------------
    # Audio QC
    # ------------------------------------------------------------------
    normal5 = os.path.join(tmpdir, "normal5.mp4")
    make_video(normal5, duration=5)
    timeline5 = make_timeline(duration=5.0)
    silence_wav = os.path.join(tmpdir, "silence.wav")
    make_silence_wav(silence_wav)
    silence_sha, silence_size = hash_file(silence_wav)
    voice_sha, voice_size = hash_file(normal5)
    audio_assets = [
        make_asset("voice-l1", duration=5.0, sha=voice_sha,
                   size=voice_size),
        make_asset("music-bed", duration=5.0, sha=silence_sha,
                   size=silence_size, asset_type="audio-music",
                   path="music-bed.wav"),
        make_asset("room-tone", duration=5.0, sha=silence_sha,
                   size=silence_size, asset_type="audio-room-tone",
                   path="room-tone.wav"),
        make_asset("sfx-whoosh", duration=0.8, sha=silence_sha,
                   size=silence_size, asset_type="audio-sfx",
                   path="sfx-whoosh.wav"),
    ]
    audio_report = qc.audio_qc(normal5, timeline5, voice_lines,
                               audio_profile, assets=audio_assets)
    check("CF-P1-006-QC-audio-normal-measured",
          audio_report["integrated_loudness_lufs"] is not None
          and audio_report["true_peak_dbfs"] is not None
          and audio_report["peak_dbfs"] is not None
          and audio_report["clipped"] is False,
          str({k: audio_report.get(k) for k in
               ("integrated_loudness_lufs", "true_peak_dbfs",
                "peak_dbfs", "clipped")}))
    check("CF-P1-006-QC-audio-normal-no-critical",
          not [f for f in audio_report["findings"]
               if f["severity"] == "critical"],
          str(audio_report["findings"]))
    check("CF-P1-006-QC-audio-dialogue-duration",
          audio_report["dialogue_duration_seconds"] == 5.0,
          str(audio_report["dialogue_duration_seconds"]))
    check("CF-P1-006-QC-audio-track-alignment",
          all(t["aligned"] for t in audio_report["track_alignment"])
          and {t["track_id"] for t in audio_report["track_alignment"]}
          == {"voice", "music", "room-tone", "sfx"},
          str(audio_report["track_alignment"]))
    check("CF-P1-006-QC-audio-asset-hashes",
          {h["asset_id"] for h in audio_report["asset_hashes"]}
          == {"voice-l1", "music-bed", "room-tone", "sfx-whoosh"},
          str(audio_report["asset_hashes"]))

    clipped5 = os.path.join(tmpdir, "clipped5.mp4")
    make_video(clipped5, duration=5, audio="clipped")
    clipped_report = qc.audio_qc(clipped5, timeline5, voice_lines,
                                 audio_profile, assets=audio_assets)
    check("CF-P1-006-QC-audio-clipped-flagged",
          clipped_report["clipped"] is True
          and clipped_report["peak_dbfs"] is not None
          and clipped_report["peak_dbfs"] >= -0.1,
          str(clipped_report["peak_dbfs"]))
    check("CF-P1-006-QC-audio-clipped-critical",
          any(f["severity"] == "critical"
              and f["code"] == "clipped-audio"
              for f in clipped_report["findings"]),
          str(clipped_report["findings"]))

    silence_video = os.path.join(tmpdir, "silence-video.mp4")
    make_video(silence_video, duration=5, audio=None)
    silence5 = os.path.join(tmpdir, "silence5.mp4")
    run_ffmpeg(["ffmpeg", "-y", "-v", "error", "-i", silence_video,
                "-i", silence_wav, "-c:v", "copy", "-c:a", "aac",
                "-shortest", silence5])
    silence_report = qc.audio_qc(silence5, timeline5, voice_lines,
                                 audio_profile, assets=audio_assets)
    long_silences = [s for s in silence_report["silence_report"]
                     if s["duration"] > 2.0]
    check("CF-P1-006-QC-audio-silence-detected",
          len(long_silences) == 1
          and long_silences[0]["intentional"] is False,
          str(silence_report["silence_report"]))
    check("CF-P1-006-QC-audio-silence-major",
          any(f["severity"] == "major"
              and f["code"] == "unexpected-long-silence"
              for f in silence_report["findings"]),
          str(silence_report["findings"]))
    timeline5_intentional = make_timeline(
        duration=5.0,
        intentional_silences=[{
            "silence_id": "mid-silence",
            "timeline_start_seconds": 1.0, "duration_seconds": 3.0,
            "reason": "Recorded intentional silence for the test."}])
    silence_ok = qc.audio_qc(silence5, timeline5_intentional,
                             voice_lines, audio_profile,
                             assets=audio_assets)
    check("CF-P1-006-QC-audio-silence-intentional-ok",
          all(s["intentional"]
              for s in silence_ok["silence_report"]
              if s["duration"] > 2.0)
          and not any(f["code"] == "unexpected-long-silence"
                      for f in silence_ok["findings"]),
          str(silence_ok["silence_report"]))

    timeline_no_voice = make_timeline(duration=5.0, voice_clips=[])
    no_dialogue = qc.audio_qc(normal5, timeline_no_voice, voice_lines,
                              audio_profile, assets=audio_assets)
    check("CF-P1-006-QC-audio-missing-dialogue",
          any(f["severity"] == "critical"
              and f["code"] == "missing-dialogue"
              for f in no_dialogue["findings"]),
          str(no_dialogue["findings"]))
    timeline_no_music = make_timeline(duration=5.0, music=False)
    no_music = qc.audio_qc(normal5, timeline_no_music, voice_lines,
                           audio_profile, assets=audio_assets)
    check("CF-P1-006-QC-audio-missing-music",
          any(f["severity"] == "critical"
              and f["code"] == "missing-music-asset"
              for f in no_music["findings"]),
          str(no_music["findings"]))
    expect_error("CF-P1-006-QC-audio-missing-tool-raises", (QCError,),
                 lambda: qc.audio_qc(
                     normal5, timeline5, voice_lines, audio_profile,
                     ffmpeg="ffmpeg-no-such-binary"))

    # ------------------------------------------------------------------
    # QC decision
    # ------------------------------------------------------------------
    decision_ok = qc.qc_decision(report, audio_report,
                                 editorial_approval="reviewer-name")
    check("CF-P1-006-QC-decision-ready",
          decision_ok["decision"] == "DELIVERY_READY"
          and decision_ok["reasons"] == [],
          str(decision_ok))
    decision_no_approval = qc.qc_decision(report, audio_report)
    check("CF-P1-006-QC-decision-no-approval-blocked",
          decision_no_approval["decision"] == "BLOCKED"
          and any("editorial approval" in r
                  for r in decision_no_approval["reasons"]),
          str(decision_no_approval))
    decision_auto = qc.qc_decision(report, audio_report,
                                   editorial_approval="automated")
    check("CF-P1-006-QC-decision-automated-refused",
          decision_auto["decision"] == "BLOCKED"
          and any("automated" in r
                  for r in decision_auto["reasons"]),
          str(decision_auto))
    decision_tech_fail = qc.qc_decision(report10, audio_report,
                                        editorial_approval="reviewer")
    check("CF-P1-006-QC-decision-tech-fail-blocked",
          decision_tech_fail["decision"] == "BLOCKED"
          and any("technical QC failed" in r
                  for r in decision_tech_fail["reasons"]),
          str(decision_tech_fail))
    decision_audio_critical = qc.qc_decision(
        report, clipped_report, editorial_approval="reviewer")
    check("CF-P1-006-QC-decision-audio-critical-blocked",
          decision_audio_critical["decision"] == "BLOCKED"
          and any("clipped-audio" in r
                  for r in decision_audio_critical["reasons"]),
          str(decision_audio_critical))

    # ------------------------------------------------------------------
    # Delivery package
    # ------------------------------------------------------------------
    project = {"project_id": "p1006-vertical-explainer",
               "title": "Consistency Frame — One Character, "
                        "Every Scene",
               "output_profile": profile,
               "audio_profile": audio_profile}
    delivery_assets = [
        make_asset("clip-s1", duration=5.0, sha=voice_sha,
                   size=voice_size, asset_type="video-clip",
                   path="clip-s1.mp4", mime_type="video/mp4"),
        make_asset("voice-l1", duration=5.0, sha=voice_sha,
                   size=voice_size),
    ]
    # Real QC reports from this run feed the delivery gate.
    qc_reports = {"decision": decision_ok,
                  "technical": report,
                  "visual": visual_report,
                  "audio": audio_report}
    script_path = os.path.join(tmpdir, "script.md")
    write_text(script_path, "# Script\n\nOne character. Every scene.\n")
    analysis_path = os.path.join(tmpdir, "production-analysis.json")
    write_json(analysis_path, {"id": "analysis-p1006",
                               "project_id":
                                   "p1006-vertical-explainer"})
    source_files = {
        "script.md": script_path,
        "production-analysis.json": analysis_path,
        "contact-sheet.png": sheet_path,
    }
    for keyframe in visual_report["keyframes"]:
        source_files[keyframe["path"]] = os.path.join(
            out_dir, keyframe["path"])
    dist_dir = os.path.join(tmpdir, "dist")
    manifest = pd.build_delivery_package(
        project=project, timeline=timeline5, assets=delivery_assets,
        voice_mapping={"voice_id": "p1006-narrator",
                       "lines": voice_lines},
        sound_plan=load_json(os.path.join(EXAMPLES, "sound-plan.json")),
        execution_summary={"total": 1, "succeeded": 1},
        qc_reports=qc_reports, source_files=source_files,
        dist_dir=dist_dir, final_mp4_path=normal5,
        render_timestamp="2026-11-27T12:00:00Z",
        voice_source="synthesized-tone")
    expected_files = {
        os.path.basename(normal5), "project.json", "script.md",
        "production-analysis.json", "timeline-manifest.json",
        "asset-manifest.json", "voice-mapping.json",
        "sound-plan.json", "execution-summary.json",
        "technical-qc-report.json", "visual-qc-report.json",
        "audio-qc-report.json", "contact-sheet.png",
        "SHA256SUMS", "delivery-manifest.json",
    } | {k["path"] for k in visual_report["keyframes"]}
    actual_files = {e["path"] for e in pd._collect_files(dist_dir)}
    check("CF-P1-006-DEL-full-file-set",
          expected_files == actual_files,
          f"missing={expected_files - actual_files} "
          f"extra={actual_files - expected_files}")
    check("CF-P1-006-DEL-original-not-moved",
          os.path.isfile(normal5),
          "the source MP4 must still exist after delivery")
    source_probe = probe_media_file(normal5)
    check("CF-P1-006-DEL-manifest-matches-probe",
          manifest["schema_version"] == "2.5"
          and manifest["project_id"] == "p1006-vertical-explainer"
          and manifest["timeline_id"] == "timeline-p1006-test"
          and manifest["filename"] == os.path.basename(normal5)
          and manifest["size_bytes"] == os.path.getsize(normal5)
          and manifest["sha256"] == hash_file(normal5)[0]
          and manifest["container"] == "mp4"
          and manifest["video_codec"] == "h264"
          and manifest["audio_codec"] == "aac"
          and manifest["width"] == 1080
          and manifest["height"] == 1920
          and manifest["aspect_ratio"] == "9:16"
          and manifest["frame_rate"] == 30
          and manifest["frame_rate_rational"] == "30/1"
          and abs(manifest["duration_seconds"]
                  - source_probe["duration_seconds"]) < 0.05
          and manifest["render_timestamp"] == "2026-11-27T12:00:00Z"
          and manifest["render_path"] == "ffmpeg"
          and manifest["voice_source"] == "synthesized-tone"
          and manifest["qc_status"] == "DELIVERY_READY"
          and manifest["qc_reports"]
          == ["audio-qc-report.json", "technical-qc-report.json",
              "visual-qc-report.json"]
          and {a["asset_id"] for a in manifest["source_assets"]}
          == {"clip-s1", "voice-l1"},
          str({k: manifest.get(k) for k in
               ("filename", "size_bytes", "width", "height",
                "frame_rate_rational", "duration_seconds",
                "qc_reports")}))
    dist_probe = probe_media_file(os.path.join(dist_dir, manifest["filename"]))
    check("CF-P1-006-DEL-dist-mp4-reprobes-identically",
          dist_probe["width"] == source_probe["width"]
          and dist_probe["height"] == source_probe["height"]
          and dist_probe["frame_rate_rational"]
          == source_probe["frame_rate_rational"]
          and abs(dist_probe["duration_seconds"]
                  - source_probe["duration_seconds"]) < 0.05
          and dist_probe["video_codec"] == source_probe["video_codec"]
          and dist_probe["audio_codec"] == source_probe["audio_codec"],
          str(dist_probe))
    check("CF-P1-006-DEL-verify-good-package",
          pd.verify_delivery_package(dist_dir) == [],
          str(pd.verify_delivery_package(dist_dir)))

    sums_path = os.path.join(dist_dir, "SHA256SUMS")
    check("CF-P1-006-DEL-checksums-file",
          os.path.isfile(sums_path)
          and "delivery-manifest.json" in open(
              sums_path, encoding="utf-8").read(),
          "SHA256SUMS must include the delivery manifest")
    check("CF-P1-006-DEL-write-checksums-returns-path",
          pd.write_checksums(dist_dir) == sums_path)

    deleted_dir = os.path.join(tmpdir, "dist-deleted")
    shutil.copytree(dist_dir, deleted_dir)
    os.remove(os.path.join(deleted_dir, "script.md"))
    check("CF-P1-006-DEL-verify-deleted-file-fails",
          len(pd.verify_delivery_package(deleted_dir)) > 0,
          "a deleted file must fail verification")

    tampered_dir = os.path.join(tmpdir, "dist-tampered")
    shutil.copytree(dist_dir, tampered_dir)
    with open(os.path.join(tampered_dir, "project.json"),
              "a", encoding="utf-8") as handle:
        handle.write(" ")
    check("CF-P1-006-DEL-verify-tampered-file-fails",
          any("SHA-256 mismatch" in e or "mismatch" in e
              for e in pd.verify_delivery_package(tampered_dir)),
          str(pd.verify_delivery_package(tampered_dir)))

    replaced_dir = os.path.join(tmpdir, "dist-replaced")
    shutil.copytree(dist_dir, replaced_dir)
    shutil.copyfile(res720, os.path.join(
        replaced_dir, manifest["filename"]))
    check("CF-P1-006-DEL-verify-replaced-mp4-fails",
          len(pd.verify_delivery_package(replaced_dir)) > 0,
          "a different-geometry MP4 must fail verification")

    blocked_reports = {"decision": decision_no_approval,
                       "technical": report, "audio": audio_report}
    expect_error("CF-P1-006-DEL-refuses-blocked-qc", (DeliveryError,),
                 lambda: pd.build_delivery_package(
                     project=project, timeline=timeline5,
                     assets=delivery_assets,
                     voice_mapping={"voice_id": "p1006-narrator"},
                     sound_plan={}, execution_summary={},
                     qc_reports=blocked_reports, source_files={},
                     dist_dir=os.path.join(tmpdir, "dist-blocked"),
                     final_mp4_path=normal5,
                     render_timestamp="2026-11-27T12:00:00Z",
                     voice_source="synthesized-tone"))
    # Review package: the same BLOCKED decision (editorial approval
    # missing, technical passed, audio clean) may be packaged for
    # a human reviewer — but its manifest must say BLOCKED, never
    # DELIVERY_READY. A technical failure or an audio critical
    # finding still refuses even as a review package.
    review_dir = os.path.join(tmpdir, "dist-review")
    review_manifest = pd.build_delivery_package(
        project=project, timeline=timeline5,
        assets=delivery_assets,
        voice_mapping={"voice_id": "p1006-narrator"},
        sound_plan={}, execution_summary={},
        qc_reports=blocked_reports, source_files=source_files,
        dist_dir=review_dir, final_mp4_path=normal5,
        render_timestamp="2026-11-27T12:00:00Z",
        voice_source="synthesized-tone", review_package=True)
    check("CF-P1-006-DEL-review-package-editorial-only",
          review_manifest["qc_status"] == "BLOCKED"
          and review_manifest["package_purpose"] == "review"
          and any("editorial approval" in r
                  for r in review_manifest["qc_blocked_reasons"])
          and review_manifest["sha256"] == hash_file(normal5)[0],
          str({k: review_manifest.get(k) for k in
               ("qc_status", "package_purpose",
                "qc_blocked_reasons")}))
    check("CF-P1-006-DEL-review-package-verifies",
          pd.verify_delivery_package(review_dir) == [],
          str(pd.verify_delivery_package(review_dir)))
    tech_fail_reports = {"decision": decision_tech_fail,
                         "technical": report10,
                         "audio": audio_report}
    expect_error("CF-P1-006-DEL-review-refuses-tech-fail",
                 (DeliveryError,),
                 lambda: pd.build_delivery_package(
                     project=project, timeline=timeline5,
                     assets=delivery_assets,
                     voice_mapping={"voice_id": "p1006-narrator"},
                     sound_plan={}, execution_summary={},
                     qc_reports=tech_fail_reports, source_files={},
                     dist_dir=os.path.join(tmpdir, "dist-review-tech"),
                     final_mp4_path=normal5,
                     render_timestamp="2026-11-27T12:00:00Z",
                     voice_source="synthesized-tone",
                     review_package=True))
    audio_critical_reports = {"decision": decision_audio_critical,
                              "technical": report,
                              "audio": clipped_report}
    expect_error("CF-P1-006-DEL-review-refuses-audio-critical",
                 (DeliveryError,),
                 lambda: pd.build_delivery_package(
                     project=project, timeline=timeline5,
                     assets=delivery_assets,
                     voice_mapping={"voice_id": "p1006-narrator"},
                     sound_plan={}, execution_summary={},
                     qc_reports=audio_critical_reports, source_files={},
                     dist_dir=os.path.join(tmpdir,
                                           "dist-review-audio"),
                     final_mp4_path=normal5,
                     render_timestamp="2026-11-27T12:00:00Z",
                     voice_source="synthesized-tone",
                     review_package=True))
    # Rebuild into the same directory: a stale manifest and
    # SHA256SUMS from the first build must never be listed with
    # stale hashes. The second package (different MP4, so a
    # different manifest) must verify cleanly.
    second_video = os.path.join(tmpdir, "second.mp4")
    make_video(second_video, duration=6)
    second_manifest = pd.build_delivery_package(
        project=project, timeline=timeline5,
        assets=delivery_assets,
        voice_mapping={"voice_id": "p1006-narrator"},
        sound_plan={}, execution_summary={},
        qc_reports=qc_reports, source_files=source_files,
        dist_dir=dist_dir, final_mp4_path=second_video,
        render_timestamp="2026-11-27T12:00:00Z",
        voice_source="synthesized-tone")
    check("CF-P1-006-DEL-rebuild-same-dir",
          second_manifest["sha256"] == hash_file(second_video)[0]
          and "delivery-manifest.json" not in
          {e["path"] for e in second_manifest["files"]}
          and "SHA256SUMS" not in
          {e["path"] for e in second_manifest["files"]},
          str({k: second_manifest.get(k) for k in ("sha256",)}))
    check("CF-P1-006-DEL-rebuild-verifies",
          pd.verify_delivery_package(dist_dir) == [],
          str(pd.verify_delivery_package(dist_dir)))
    missing_files = dict(source_files)
    missing_files["gone.md"] = os.path.join(tmpdir, "gone.md")
    expect_error("CF-P1-006-DEL-refuses-missing-source",
                 (DeliveryError,),
                 lambda: pd.build_delivery_package(
                     project=project, timeline=timeline5,
                     assets=delivery_assets,
                     voice_mapping={"voice_id": "p1006-narrator"},
                     sound_plan={}, execution_summary={},
                     qc_reports=qc_reports, source_files=missing_files,
                     dist_dir=os.path.join(tmpdir, "dist-missing"),
                     final_mp4_path=normal5,
                     render_timestamp="2026-11-27T12:00:00Z",
                     voice_source="synthesized-tone"))
    commercial_project = dict(project)
    commercial_project["commercial_delivery"] = True
    unknown_asset = make_asset(
        "clip-unknown", duration=5.0, sha=voice_sha, size=voice_size,
        asset_type="video-clip", license_class="unknown",
        path="clip-unknown.mp4")
    expect_error("CF-P1-006-DEL-refuses-commercial-blocker",
                 (DeliveryError,),
                 lambda: pd.build_delivery_package(
                     project=commercial_project, timeline=timeline5,
                     assets=[unknown_asset],
                     voice_mapping={"voice_id": "p1006-narrator"},
                     sound_plan={}, execution_summary={},
                     qc_reports=qc_reports, source_files={},
                     dist_dir=os.path.join(tmpdir, "dist-commercial"),
                     final_mp4_path=normal5,
                     render_timestamp="2026-11-27T12:00:00Z",
                     voice_source="synthesized-tone"))
    expect_error("CF-P1-006-DEL-refuses-invented-timestamp",
                 (DeliveryError,),
                 lambda: pd.build_delivery_package(
                     project=project, timeline=timeline5,
                     assets=delivery_assets,
                     voice_mapping={"voice_id": "p1006-narrator"},
                     sound_plan={}, execution_summary={},
                     qc_reports=qc_reports, source_files={},
                     dist_dir=os.path.join(tmpdir, "dist-notime"),
                     final_mp4_path=normal5,
                     voice_source="synthesized-tone"))

    print(f"--- CF-P1-006-QC-DEL: {_checks[0]} checks, "
          f"{len(failures)} failures ---")
    if failures:
        print("FAILURES: " + ", ".join(failures))
        return 1
    return 0


def main():
    return run_checks()


if __name__ == "__main__":
    sys.exit(main())
