#!/usr/bin/env python3
"""Timeline geometry tests (CF-WO-P1-005-R4, workstream C).

Covers: the explicit output-geometry target in a format profile
(``output_geometry``: aspect ratio, width/height, frame rate);
deriving manifest geometry from verified probe results instead
of any hardcoded 16:9 / 24 FPS / 1920x1080 fallback; mixed
aspect ratios and mixed frame rates rejected (or normalized);
missing probe metadata; invalid output profiles; audio-only
timelines carrying no video geometry; explicit FFmpeg
normalization to a selected target; and failure when actual
output does not match its declared profile.

Real media is generated at test time (ffmpeg lavfi for video,
the stdlib wave module for audio). No fabricated geometry ever
enters a manifest. No test here weakens any P0, P1 or R4 check.
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
sys.path.insert(0, os.path.join(ROOT, "tests"))
from runtime import local_session  # noqa: E402
from runtime.local_session import (  # noqa: E402
    close_session, load_or_create_profile, start_session)
from runtime import production_orchestrator as po  # noqa: E402
from runtime import timeline_delivery as td  # noqa: E402
from runtime.media_adapters import FFmpegAdapter  # noqa: E402
from runtime.media_execution import MediaExecutionError  # noqa: E402
from runtime.production_orchestrator import (  # noqa: E402
    ProductionOrchestratorError, validate_format_profile)
from runtime.timeline_delivery import TimelineDeliveryError  # noqa: E402

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


def expect_error(label, fn, error_type=TimelineDeliveryError):
    try:
        fn()
    except error_type:
        check(label, True)
        return
    except Exception as exc:  # noqa: BLE001 - any other error is a fail
        check(label, False, f"raised {type(exc).__name__}: {exc}")
        return
    check(label, False, "operation succeeded instead of refusing")


def fresh_session():
    root = tempfile.mkdtemp(prefix="cf-p1-005-r4-geo-")
    profile = load_or_create_profile(root)
    session = start_session(profile, profile.workspace_id)
    _sessions.append(session)
    return session


def packet_hash(packet):
    return hashlib.sha256(json.dumps(
        packet, sort_keys=True).encode("utf-8")).hexdigest()


def make_packet(task_id, task_type, **extra):
    packet = {
        "schema_version": "2.5",
        "packet_id": "pkt-" + task_id,
        "task_id": task_id,
        "task_type": task_type,
        "canonical_instruction": "test packet",
        "provider_status": "handed-off",
    }
    packet.update(extra)
    packet["packet_hash"] = packet_hash(
        {k: v for k, v in packet.items() if k != "packet_hash"})
    return packet


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_wav(path, seconds=1, rate=8000):
    frames = b"\x00\x00" * (rate * seconds)
    with wave.open(path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(frames)


def make_video(path, size="320x240", rate=24):
    cmd = ["ffmpeg", "-y", "-v", "error",
           "-f", "lavfi", "-i",
           f"testsrc=duration=2:size={size}:rate={rate}",
           "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
           "-c:v", "libx264", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-shortest", path]
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          timeout=180)
    if proc.returncode != 0 or not os.path.isfile(path):
        raise RuntimeError(f"ffmpeg lavfi generation failed: {proc.stderr}")


def artifact_for(root, rel, fmt):
    path = os.path.join(root, rel)
    return {"path": rel, "sha256": sha256_file(path),
            "bytes": os.path.getsize(path), "format": fmt}


def succeeded_execution(task_id, packet_id, job_id, artifact):
    return {
        "schema_version": "2.5",
        "execution_id": "exec-" + hashlib.sha256(
            task_id.encode("utf-8")).hexdigest()[:24],
        "task_id": task_id,
        "packet_id": packet_id,
        "job_id": job_id,
        "project_id": "proj-test-001",
        "provider_id": "provider-ffmpeg",
        "adapter_id": "adapter-ffmpeg",
        "state": "SUCCEEDED",
        "attempt": 1,
        "idempotency_key": "a" * 64,
        "history": [{"state": "SUCCEEDED", "reason": "verified"}],
        "output": artifact,
    }


def make_job(session, job_id, profile, video_tasks=("task-vid-001",)):
    job = po.create_production_job(
        session, job_id, "proj-test-001", profile)
    packets = []
    for task_id in video_tasks:
        packets.append(make_packet(
            task_id, "video-generation",
            identity_bindings=[{"character_id": "char-001"}]))
    packets.append(make_packet(
        "task-voice-001", "voice-generation",
        voice_binding={"voice_profile_id": "vp-001",
                       "dialogue_line_id": "l-01",
                       "dialogue_text": "Hello.",
                       "language": "bn",
                       "character_id": "char-001"}))
    job["task_package"] = {
        "schema_version": "2.5",
        "package_id": "pkg-" + job_id,
        "job_id": job_id,
        "project_id": "proj-test-001",
        "packets": packets,
    }
    return job


def profile_with_geometry(geometry):
    profile = {"delivery_profile": "short-form-15-60s"}
    if geometry is not None:
        profile["output_geometry"] = geometry
    return profile


def profile_validation_group():
    valid = (
        {"aspect_ratio": "16:9", "width": 1920, "height": 1080,
         "frame_rate": 24},
        {"aspect_ratio": "9:16", "width": 1080, "height": 1920,
         "frame_rate": 30},
        {"aspect_ratio": "1:1", "width": 720, "height": 720},
        {"aspect_ratio": "4:3"},
        {"width": 640, "height": 480},
        {"frame_rate": 29.97},
        {"aspect_ratio": "other", "width": 100, "height": 99},
        {},
    )
    for geometry in valid:
        check("CF-P1-005-R4-GEOMETRY-profile-valid: "
              + json.dumps(geometry, sort_keys=True),
              td.validate_output_geometry(geometry) == [])
    invalid = (
        ("not-an-object", "not-an-object"),
        ({"surprise": True}, "unexpected field"),
        ({"aspect_ratio": "3:2"}, "unknown ratio"),
        ({"width": 640}, "lone width"),
        ({"height": 480}, "lone height"),
        ({"width": 640.5, "height": 480}, "non-int width"),
        ({"width": 0, "height": 480}, "zero width"),
        ({"width": -640, "height": 480}, "negative width"),
        ({"aspect_ratio": "16:9", "width": 640, "height": 480},
         "ratio disagrees with dimensions"),
        ({"aspect_ratio": "4:3", "width": 1920, "height": 1080},
         "ratio disagrees with dimensions"),
        ({"frame_rate": 0}, "zero frame rate"),
        ({"frame_rate": -24}, "negative frame rate"),
        ({"frame_rate": True}, "bool frame rate"),
        ({"frame_rate": "24"}, "string frame rate"),
        ({"frame_rate": 241}, "frame rate above the bound"),
    )
    for geometry, label in invalid:
        errors = td.validate_output_geometry(geometry)
        check("CF-P1-005-R4-GEOMETRY-profile-invalid: " + label,
              errors != [], str(errors))
    # The format-profile validator accepts a valid target and
    # refuses an invalid one; the "surprise" field still fails.
    check("CF-P1-005-R4-GEOMETRY-format-profile-accepts-target",
          validate_format_profile(profile_with_geometry(
              {"aspect_ratio": "16:9", "width": 1920,
               "height": 1080, "frame_rate": 24})) == [])
    check("CF-P1-005-R4-GEOMETRY-format-profile-rejects-target",
          validate_format_profile(profile_with_geometry(
              {"aspect_ratio": "16:9", "width": 640,
               "height": 480})) != [])
    check("CF-P1-005-R4-GEOMETRY-format-profile-rejects-unknown",
          validate_format_profile(
              {"delivery_profile": "short-form-15-60s",
               "surprise": True}) != [])
    session = fresh_session()
    job = po.create_production_job(
        session, "job-geo-profile-001", "proj-test-001",
        profile_with_geometry(
            {"aspect_ratio": "9:16", "width": 1080,
             "height": 1920, "frame_rate": 30}))
    check("CF-P1-005-R4-GEOMETRY-job-keeps-target",
          job["format_profile"]["output_geometry"]["aspect_ratio"]
          == "9:16")
    expect_error(
        "CF-P1-005-R4-GEOMETRY-job-rejects-bad-target",
        lambda: po.create_production_job(
            session, "job-geo-profile-002", "proj-test-001",
            profile_with_geometry(
                {"aspect_ratio": "16:9", "width": 640,
                 "height": 480})),
        error_type=ProductionOrchestratorError)


def unit_geometry_group():
    cases = ((1920, 1080, "16:9"), (1080, 1920, "9:16"),
             (720, 720, "1:1"), (640, 480, "4:3"),
             (480, 640, "3:4"), (2100, 900, "21:9"),
             (2560, 1080, "2.39:1"), (1920, 800, "2.39:1"),
             (0, 480, "other"), (640, 0, "other"))
    for width, height, expected in cases:
        check("CF-P1-005-R4-GEOMETRY-ratio: "
              f"{width}x{height} -> {expected}",
              td.aspect_ratio_for_dimensions(width, height)
              == expected)
    probe = {"width": 1920, "height": 1080,
             "frame_rate": 23.976023976, "duration_seconds": 2.0,
             "codec": "h264"}
    check("CF-P1-005-R4-GEOMETRY-probe-full",
          td.geometry_from_probe(probe)
          == {"aspect_ratio": "16:9",
              "resolution": {"width": 1920, "height": 1080},
              "frame_rate": 23.976},
          str(td.geometry_from_probe(probe)))
    check("CF-P1-005-R4-GEOMETRY-probe-no-frame-rate",
          td.geometry_from_probe(
              {"width": 640, "height": 480})
          == {"aspect_ratio": "4:3",
              "resolution": {"width": 640, "height": 480}})
    for missing in ({}, {"width": 640}, {"height": 480},
                    {"width": 0, "height": 480},
                    {"width": "640", "height": 480},
                    {"width": 640, "height": 480,
                     "frame_rate": 0}):
        check("CF-P1-005-R4-GEOMETRY-probe-missing: "
              + json.dumps(missing, sort_keys=True),
              td.geometry_from_probe(missing) is None
              or "frame_rate" not in
              (td.geometry_from_probe(missing) or {}))
    target = {"aspect_ratio": "16:9",
              "resolution": {"width": 1920, "height": 1080},
              "frame_rate": 24}
    same = {"aspect_ratio": "16:9",
            "resolution": {"width": 1920, "height": 1080},
            "frame_rate": 23.976}
    check("CF-P1-005-R4-GEOMETRY-mismatch-same",
          td.geometry_mismatch(target, same) is None)
    check("CF-P1-005-R4-GEOMETRY-mismatch-resolution",
          td.geometry_mismatch(
              target, {"aspect_ratio": "16:9",
                       "resolution": {"width": 1280,
                                      "height": 720},
                       "frame_rate": 24}) is not None)
    check("CF-P1-005-R4-GEOMETRY-mismatch-ratio",
          td.geometry_mismatch(
              target, {"aspect_ratio": "4:3",
                       "resolution": {"width": 1920,
                                      "height": 1080},
                       "frame_rate": 24}) is not None)
    check("CF-P1-005-R4-GEOMETRY-mismatch-rate",
          td.geometry_mismatch(
              target, {"aspect_ratio": "16:9",
                       "resolution": {"width": 1920,
                                      "height": 1080},
                       "frame_rate": 25}) is not None)
    check("CF-P1-005-R4-GEOMETRY-mismatch-rate-tolerance",
          td.geometry_mismatch(
              target, {"aspect_ratio": "16:9",
                       "resolution": {"width": 1920,
                                      "height": 1080},
                       "frame_rate": 29.97}) is not None)
    check("CF-P1-005-R4-GEOMETRY-mismatch-unstated-rate",
          td.geometry_mismatch(
              {"resolution": {"width": 1920, "height": 1080}},
              {"aspect_ratio": "16:9",
               "resolution": {"width": 1920, "height": 1080},
               "frame_rate": 30}) is None)


def manifest_geometry_group(session, delivery_root, adapter):
    def build(job, executions, ffmpeg_adapter):
        return td.build_delivery_manifest(
            session, job, executions,
            delivery_root=delivery_root,
            ffmpeg_adapter=ffmpeg_adapter)

    def video_exec(task_id, rel):
        return succeeded_execution(
            task_id, "pkt-" + task_id, "job-geo-001",
            artifact_for(delivery_root, rel, "mp4"))

    def audio_exec():
        return succeeded_execution(
            "task-voice-001", "pkt-task-voice-001", "job-geo-001",
            artifact_for(delivery_root, "voice-001.wav", "wav"))

    # One clip per geometry: the manifest must report exactly
    # what the probe measured — never 16:9 / 24 / 1920x1080.
    cases = (
        ("shot-916.mp4", "1080x1920", 30, "9:16",
         {"width": 1080, "height": 1920}, 30),
        ("shot-169-24.mp4", "1920x1080", 24, "16:9",
         {"width": 1920, "height": 1080}, 24),
        ("shot-169-30.mp4", "1920x1080", 30, "16:9",
         {"width": 1920, "height": 1080}, 30),
        ("shot-11.mp4", "720x720", 24, "1:1",
         {"width": 720, "height": 720}, 24),
        ("shot-43.mp4", "640x480", 25, "4:3",
         {"width": 640, "height": 480}, 25),
    )
    for rel, size, rate, ratio, resolution, expected_rate in cases:
        make_video(os.path.join(delivery_root, rel),
                   size=size, rate=rate)
        job = make_job(session, "job-geo-001",
                       profile_with_geometry(None))
        manifest = build(job, [video_exec("task-vid-001", rel),
                               audio_exec()], adapter)
        check(f"CF-P1-005-R4-GEOMETRY-manifest-{rel}",
              manifest.get("aspect_ratio") == ratio
              and manifest.get("resolution") == resolution
              and manifest.get("frame_rate") == expected_rate,
              str({k: manifest.get(k) for k in
                   ("aspect_ratio", "resolution", "frame_rate")}))

    # Mixed aspect ratios are rejected, never silently claimed.
    make_video(os.path.join(delivery_root, "mix-a.mp4"),
               size="320x240", rate=24)
    make_video(os.path.join(delivery_root, "mix-b.mp4"),
               size="320x180", rate=24)
    job = make_job(session, "job-geo-001",
                   profile_with_geometry(None),
                   video_tasks=("task-vid-001", "task-vid-002"))
    expect_error(
        "CF-P1-005-R4-GEOMETRY-mixed-aspect-rejected",
        lambda: build(job, [video_exec("task-vid-001", "mix-a.mp4"),
                            video_exec("task-vid-002", "mix-b.mp4"),
                            audio_exec()], adapter))

    # Mixed frame rates are rejected the same way.
    make_video(os.path.join(delivery_root, "mix-c.mp4"),
               size="320x240", rate=24)
    make_video(os.path.join(delivery_root, "mix-d.mp4"),
               size="320x240", rate=30)
    expect_error(
        "CF-P1-005-R4-GEOMETRY-mixed-rate-rejected",
        lambda: build(job, [video_exec("task-vid-001", "mix-c.mp4"),
                            video_exec("task-vid-002", "mix-d.mp4"),
                            audio_exec()], adapter))

    # Two agreeing clips deliver one geometry (not the first
    # clip's alone: the second clip is checked too).
    make_video(os.path.join(delivery_root, "agree-a.mp4"),
               size="320x240", rate=24)
    make_video(os.path.join(delivery_root, "agree-b.mp4"),
               size="320x240", rate=24)
    manifest = build(job, [video_exec("task-vid-001", "agree-a.mp4"),
                           video_exec("task-vid-002", "agree-b.mp4"),
                           audio_exec()], adapter)
    check("CF-P1-005-R4-GEOMETRY-two-agreeing-clips",
          manifest.get("aspect_ratio") == "4:3"
          and manifest.get("resolution")
          == {"width": 320, "height": 240}
          and manifest.get("frame_rate") == 24,
          str({k: manifest.get(k) for k in
               ("aspect_ratio", "resolution", "frame_rate")}))

    # An explicit target that matches delivers that geometry.
    job = make_job(
        session, "job-geo-001",
        profile_with_geometry(
            {"aspect_ratio": "4:3", "width": 320, "height": 240,
             "frame_rate": 24}))
    manifest = build(job, [video_exec("task-vid-001", "agree-a.mp4"),
                           audio_exec()], adapter)
    check("CF-P1-005-R4-GEOMETRY-target-match",
          manifest.get("aspect_ratio") == "4:3"
          and manifest.get("resolution")
          == {"width": 320, "height": 240}
          and manifest.get("frame_rate") == 24)

    # An explicit target the media does not meet fails.
    job = make_job(
        session, "job-geo-001",
        profile_with_geometry(
            {"aspect_ratio": "16:9", "width": 1920,
             "height": 1080, "frame_rate": 24}))
    expect_error(
        "CF-P1-005-R4-GEOMETRY-target-mismatch-rejected",
        lambda: build(job, [video_exec("task-vid-001", "agree-a.mp4"),
                            audio_exec()], adapter))

    # A target stating only the aspect ratio takes the rest
    # from the verified media.
    job = make_job(session, "job-geo-001",
                   profile_with_geometry({"aspect_ratio": "4:3"}))
    manifest = build(job, [video_exec("task-vid-001", "agree-a.mp4"),
                           audio_exec()], adapter)
    check("CF-P1-005-R4-GEOMETRY-target-aspect-only",
          manifest.get("aspect_ratio") == "4:3"
          and manifest.get("resolution")
          == {"width": 320, "height": 240}
          and manifest.get("frame_rate") == 24)

    # A resolution-only target does not forgive mixed rates.
    job2 = make_job(session, "job-geo-001",
                    profile_with_geometry({"width": 320,
                                           "height": 240}),
                    video_tasks=("task-vid-001", "task-vid-002"))
    expect_error(
        "CF-P1-005-R4-GEOMETRY-target-mixed-rate-rejected",
        lambda: build(job2, [video_exec("task-vid-001", "mix-c.mp4"),
                             video_exec("task-vid-002", "mix-d.mp4"),
                             audio_exec()], adapter))

    # No probe data and no target: geometry is omitted, never
    # invented. (The fake clip has no probe metadata.)
    fake_rel = "fake-clip.mp4"
    with open(os.path.join(delivery_root, fake_rel), "wb") as handle:
        handle.write(b"cf-test-video-bytes")
    job = make_job(session, "job-geo-001",
                   profile_with_geometry(None))
    manifest = build(job, [video_exec("task-vid-001", fake_rel),
                           audio_exec()], None)
    check("CF-P1-005-R4-GEOMETRY-no-probe-no-geometry",
          "aspect_ratio" not in manifest
          and "resolution" not in manifest
          and "frame_rate" not in manifest,
          str({k: manifest.get(k) for k in
               ("aspect_ratio", "resolution", "frame_rate")}))

    # No probe data and a target: cannot verify, so it fails.
    job = make_job(
        session, "job-geo-001",
        profile_with_geometry(
            {"aspect_ratio": "16:9", "width": 1920,
             "height": 1080, "frame_rate": 24}))
    expect_error(
        "CF-P1-005-R4-GEOMETRY-target-no-probe-rejected",
        lambda: build(job, [video_exec("task-vid-001", fake_rel),
                            audio_exec()], None))

    # Audio-only: no video geometry at all.
    job = make_job(session, "job-geo-001",
                   profile_with_geometry(None))
    manifest = build(job, [audio_exec()], adapter)
    check("CF-P1-005-R4-GEOMETRY-audio-only-no-geometry",
          "aspect_ratio" not in manifest
          and "resolution" not in manifest
          and "frame_rate" not in manifest
          and [t["kind"] for t in manifest["tracks"]] == ["audio"])

    # Audio-only with a video target: the target cannot hold.
    job = make_job(
        session, "job-geo-001",
        profile_with_geometry(
            {"aspect_ratio": "16:9", "width": 1920,
             "height": 1080}))
    expect_error(
        "CF-P1-005-R4-GEOMETRY-audio-only-target-rejected",
        lambda: build(job, [audio_exec()], adapter))

    # A bad target stored on a hand-built job fails the build
    # even when job creation was bypassed.
    job = make_job(session, "job-geo-001",
                   profile_with_geometry(None))
    job["format_profile"] = {"delivery_profile": "short-form-15-60s",
                             "output_geometry": {
                                 "aspect_ratio": "16:9",
                                 "width": 640, "height": 480}}
    expect_error(
        "CF-P1-005-R4-GEOMETRY-invalid-target-at-build",
        lambda: build(job, [video_exec("task-vid-001", "agree-a.mp4"),
                            audio_exec()], adapter))


def normalization_group(session, delivery_root, adapter):
    make_video(os.path.join(delivery_root, "norm-src.mp4"),
               size="320x240", rate=24)
    target = {"aspect_ratio": "16:9", "width": 640, "height": 360,
              "frame_rate": 30}
    record = td.normalize_media_to_geometry(
        adapter, "norm-src.mp4", "norm-out.mp4", target,
        execution_id="norm-001")
    check("CF-P1-005-R4-GEOMETRY-normalize-record",
          record.get("operation") == "normalize-geometry"
          and record.get("target_geometry") == target
          and record.get("verified_geometry", {}).get("resolution")
          == {"width": 640, "height": 360}
          and record.get("verified_geometry", {}).get("frame_rate")
          == 30,
          str(record))
    check("CF-P1-005-R4-GEOMETRY-normalize-artifact-probed",
          record.get("artifact", {}).get("width") == 640
          and record.get("artifact", {}).get("height") == 360
          and record.get("artifact", {}).get("frame_rate") == 30,
          str(record.get("artifact")))
    # The normalized clip now delivers against the same target.
    job = make_job(session, "job-geo-001",
                   profile_with_geometry(target))
    manifest = td.build_delivery_manifest(
        session, job,
        [succeeded_execution(
            "task-vid-001", "pkt-task-vid-001", "job-geo-001",
            artifact_for(delivery_root, "norm-out.mp4", "mp4")),
         succeeded_execution(
            "task-voice-001", "pkt-task-voice-001", "job-geo-001",
            artifact_for(delivery_root, "voice-001.wav", "wav"))],
        delivery_root=delivery_root, ffmpeg_adapter=adapter)
    check("CF-P1-005-R4-GEOMETRY-normalized-delivers",
          manifest.get("resolution")
          == {"width": 640, "height": 360}
          and manifest.get("frame_rate") == 30)
    # Normalization needs a full target and a valid one.
    expect_error(
        "CF-P1-005-R4-GEOMETRY-normalize-aspect-only-rejected",
        lambda: td.normalize_media_to_geometry(
            adapter, "norm-src.mp4", "norm-bad.mp4",
            {"aspect_ratio": "16:9"}, execution_id="norm-002"))
    expect_error(
        "CF-P1-005-R4-GEOMETRY-normalize-invalid-target-rejected",
        lambda: td.normalize_media_to_geometry(
            adapter, "norm-src.mp4", "norm-bad.mp4",
            {"width": 640}, execution_id="norm-003"))
    # The ffmpeg fps/size options are validated before any
    # command runs.
    for bad_fps in (0, -1, "30", True, 241):
        expect_error(
            "CF-P1-005-R4-GEOMETRY-ffmpeg-fps-rejected: "
            f"{bad_fps!r}",
            lambda bad_fps=bad_fps: adapter.submit(
                {"provider_id": "provider-ffmpeg",
                 "canonical_instruction": "bad fps",
                 "task_id": "bad-fps",
                 "ffmpeg_operation": "transcode",
                 "inputs": ["norm-src.mp4"],
                 "output": "bad-fps.mp4",
                 "options": {"fps": bad_fps}},
                {"execution_id": "bad-fps"}),
            error_type=MediaExecutionError)
    expect_error(
        "CF-P1-005-R4-GEOMETRY-ffmpeg-size-rejected",
        lambda: adapter.submit(
            {"provider_id": "provider-ffmpeg",
             "canonical_instruction": "bad size",
             "task_id": "bad-size",
             "ffmpeg_operation": "transcode",
             "inputs": ["norm-src.mp4"],
             "output": "bad-size.mp4",
             "options": {"size": "640x360; rm -rf /"}},
            {"execution_id": "bad-size"}),
        error_type=MediaExecutionError)


def run_checks():
    profile_validation_group()
    unit_geometry_group()
    session = fresh_session()
    tmpdir = tempfile.mkdtemp(prefix="cf-p1-005-r4-geo-")
    delivery_root = os.path.join(tmpdir, "delivery")
    os.makedirs(delivery_root)
    has_ffmpeg = shutil.which("ffmpeg") is not None \
        and shutil.which("ffprobe") is not None
    make_wav(os.path.join(delivery_root, "voice-001.wav"))
    adapter = None
    if has_ffmpeg:
        adapter = FFmpegAdapter(workspace_root=delivery_root)
        manifest_geometry_group(session, delivery_root, adapter)
        normalization_group(session, delivery_root, adapter)
    else:
        print("SKIP CF-P1-005-R4-GEOMETRY probe groups: "
              "ffmpeg/ffprobe not available")
    print(f"--- CF-P1-005-R4-GEOMETRY: {_checks[0]} checks, "
          f"{len(failures)} failures ---")
    if failures:
        print("FAILURES: " + ", ".join(failures))
        return 1
    return 0


def main():
    try:
        return run_checks()
    finally:
        for session in _sessions:
            try:
                close_session(session)
            except Exception:  # noqa: BLE001 - best-effort cleanup
                pass


if __name__ == "__main__":
    sys.exit(main())
