#!/usr/bin/env python3
"""Timeline delivery tests (CF-WO-P1-005, WO §7 + §11).

Covers: building a delivery manifest only from SUCCEEDED
executions with validated real output artifacts (video + voice
tracks, character/dialogue/language/audio-type bindings, schema +
structural validation, strict cross-reference check with a real
requester); rejection of unvalidated, fabricated, missing,
hash-mismatched and path-escaping artifacts; the minimal registry
built from a job; and the manifest summary.

Real media is generated at test time (ffmpeg lavfi for video, the
stdlib wave module for audio). No fabricated path ever enters a
manifest.

Conventions follow tests/test_production_store.py: check(name, cond,
detail="") prints PASS/FAIL lines, failures are collected, and the
process exits 0 only when every check passes. No test here weakens
any P0 or P1 check.
"""

import hashlib
import io
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


def expect_error(label, fn):
    try:
        fn()
    except TimelineDeliveryError:
        check(label, True)
        return
    except Exception as exc:  # noqa: BLE001 - any other error is a fail
        check(label, False, f"raised {type(exc).__name__}: {exc}")
        return
    check(label, False, "operation succeeded instead of refusing")


def fresh_session():
    root = tempfile.mkdtemp(prefix="cf-p1-005-test-")
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


def make_video(path):
    cmd = ["ffmpeg", "-y", "-v", "error",
           "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=24",
           "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
           "-c:v", "libx264", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-shortest", path]
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          timeout=120)
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


def make_job(session):
    job = po.create_production_job(
        session, "job-delivery-001", "proj-test-001",
        {"delivery_profile": "short-form-15-60s"})
    video_packet = make_packet(
        "task-vid-001", "video-generation",
        identity_bindings=[{"character_id": "char-001"}])
    voice_packet = make_packet(
        "task-voice-001", "voice-generation",
        voice_binding={"voice_profile_id": "vp-001",
                       "dialogue_line_id": "l-01",
                       "dialogue_text": "Hello.",
                       "language": "bn",
                       "character_id": "char-001"})
    job["task_package"] = {
        "schema_version": "2.5",
        "package_id": "pkg-job-delivery-001",
        "job_id": "job-delivery-001",
        "project_id": "proj-test-001",
        "packets": [video_packet, voice_packet],
    }
    job["identity_snapshot"] = {
        "schema_version": "2.5",
        "job_id": "job-delivery-001",
        "project_id": "proj-test-001",
        "characters": [{
            "character_id": "char-001",
            "ownership": {"owner_id": "owner-001",
                          "workspace_id": "ws-001",
                          "visibility": "private", "sharing": "none"},
            "voice_profiles": [{
                "voice_profile_id": "vp-001",
                "ownership": {"owner_id": "owner-001",
                              "workspace_id": "ws-001",
                              "visibility": "private",
                              "sharing": "none"}}],
        }],
    }
    return job


def run_checks():
    session = fresh_session()
    tmpdir = tempfile.mkdtemp(prefix="cf-p1-005-delivery-")
    delivery_root = os.path.join(tmpdir, "delivery")
    os.makedirs(delivery_root)
    has_ffmpeg = shutil.which("ffmpeg") is not None \
        and shutil.which("ffprobe") is not None
    video_rel = "shot-001.mp4"
    audio_rel = "voice-001.wav"
    try:
        if has_ffmpeg:
            make_video(os.path.join(delivery_root, video_rel))
        else:
            with open(os.path.join(delivery_root, video_rel),
                      "wb") as handle:
                handle.write(b"cf-test-video-bytes")
    except RuntimeError as exc:
        print(f"SKIP CF-P1-005-DELIVERY video: {exc}")
        has_ffmpeg = False
        with open(os.path.join(delivery_root, video_rel),
                  "wb") as handle:
            handle.write(b"cf-test-video-bytes")
    make_wav(os.path.join(delivery_root, audio_rel))

    job = make_job(session)
    video_artifact = artifact_for(delivery_root, video_rel, "mp4")
    audio_artifact = artifact_for(delivery_root, audio_rel, "wav")
    video_exec = succeeded_execution(
        "task-vid-001", "pkt-task-vid-001", "job-delivery-001",
        video_artifact)
    audio_exec = succeeded_execution(
        "task-voice-001", "pkt-task-voice-001", "job-delivery-001",
        audio_artifact)
    executions = [video_exec, audio_exec]
    ffmpeg_adapter = FFmpegAdapter(workspace_root=delivery_root) \
        if has_ffmpeg else None

    # Artifact re-verification (no adapter: existence + hash + size).
    verified = td.validate_delivery_artifact(
        video_artifact, delivery_root)
    check("CF-P1-005-DELIVERY-artifact-valid",
          verified["sha256"] == video_artifact["sha256"]
          and verified["bytes"] == video_artifact["bytes"])
    bad_hash = dict(video_artifact)
    bad_hash["sha256"] = "0" * 64
    expect_error("CF-P1-005-DELIVERY-artifact-hash-mismatch",
                 lambda: td.validate_delivery_artifact(
                     bad_hash, delivery_root))
    bad_size = dict(video_artifact)
    bad_size["bytes"] = video_artifact["bytes"] + 1
    expect_error("CF-P1-005-DELIVERY-artifact-size-mismatch",
                 lambda: td.validate_delivery_artifact(
                     bad_size, delivery_root))
    missing = dict(video_artifact)
    missing["path"] = "no-such-file.mp4"
    missing["sha256"] = "0" * 64
    expect_error("CF-P1-005-DELIVERY-artifact-missing",
                 lambda: td.validate_delivery_artifact(
                     missing, delivery_root))
    absolute = dict(video_artifact)
    absolute["path"] = os.path.join(delivery_root, video_rel)
    expect_error("CF-P1-005-DELIVERY-artifact-absolute-refused",
                 lambda: td.validate_delivery_artifact(
                     absolute, delivery_root))
    escape = dict(video_artifact)
    escape["path"] = "../escape.mp4"
    expect_error("CF-P1-005-DELIVERY-artifact-escape-refused",
                 lambda: td.validate_delivery_artifact(
                     escape, delivery_root))
    expect_error("CF-P1-005-DELIVERY-artifact-not-object",
                 lambda: td.validate_delivery_artifact(
                     "not-an-artifact", delivery_root))

    # The registry is built from the job's snapshot + package.
    registry = td.registry_from_job(job)
    check("CF-P1-005-DELIVERY-registry-characters",
          "char-001" in (registry.get("characters") or {}))
    check("CF-P1-005-DELIVERY-registry-voices",
          "vp-001" in (registry.get("voice_profiles") or {}))
    check("CF-P1-005-DELIVERY-registry-lines",
          "l-01" in (registry.get("dialogue_lines") or {}))
    check("CF-P1-005-DELIVERY-registry-audio",
          "audio-task-voice-001" in (registry.get("audio_assets") or {}))

    # Manifest from validated artifacts only.
    manifest = td.build_delivery_manifest(
        session, job, executions, delivery_root=delivery_root,
        ffmpeg_adapter=ffmpeg_adapter)
    check("CF-P1-005-DELIVERY-manifest-format",
          manifest.get("format") == "editor_neutral_v1")
    check("CF-P1-005-DELIVERY-manifest-id",
          manifest.get("id") == "timeline-job-delivery-001")
    kinds = [t["kind"] for t in manifest.get("tracks") or []]
    check("CF-P1-005-DELIVERY-manifest-tracks",
          kinds == ["video", "audio"], str(kinds))
    video_track = next(t for t in manifest["tracks"]
                       if t["kind"] == "video")
    audio_track = next(t for t in manifest["tracks"]
                       if t["kind"] == "audio")
    video_clip = video_track["clips"][0]
    audio_clip = audio_track["clips"][0]
    check("CF-P1-005-DELIVERY-video-clip",
          video_clip["clip_id"] == "clip-task-vid-001"
          and video_clip["media"]["path"] == video_rel
          and video_clip["media"]["sha256"]
          == video_artifact["sha256"]
          and video_clip.get("character_ids") == ["char-001"])
    check("CF-P1-005-DELIVERY-audio-clip",
          audio_clip["clip_id"] == "clip-task-voice-001"
          and audio_clip.get("audio_asset_id")
          == "audio-task-voice-001"
          and audio_clip.get("dialogue_line_id") == "l-01"
          and audio_clip.get("language") == "bn"
          and audio_clip.get("audio_type") == "dialogue"
          and audio_clip.get("character_id") == "char-001")
    if has_ffmpeg:
        check("CF-P1-005-DELIVERY-video-duration",
              video_clip.get("duration_seconds") is not None
              and abs(video_clip["duration_seconds"] - 2.0) < 0.15,
              str(video_clip.get("duration_seconds")))
        check("CF-P1-005-DELIVERY-manifest-resolution",
              manifest.get("resolution")
              == {"width": 320, "height": 240},
              str(manifest.get("resolution")))
    summary = td.delivery_manifest_summary(manifest)
    check("CF-P1-005-DELIVERY-summary",
          summary.get("video_clips") == 1
          and summary.get("audio_clips") == 1
          and summary.get("tracks") == 2,
          str(summary))

    # Strict cross-reference check with the real requester.
    manifest_strict = td.build_delivery_manifest(
        session, job, executions, delivery_root=delivery_root,
        ffmpeg_adapter=ffmpeg_adapter,
        requesting_owner_id="owner-001",
        requesting_workspace_id="ws-001")
    check("CF-P1-005-DELIVERY-strict-owner-ok",
          manifest_strict.get("id") == manifest.get("id"))
    expect_error("CF-P1-005-DELIVERY-strict-wrong-owner",
                 lambda: td.build_delivery_manifest(
                     session, job, executions,
                     delivery_root=delivery_root,
                     ffmpeg_adapter=ffmpeg_adapter,
                     requesting_owner_id="owner-other-001",
                     requesting_workspace_id="ws-001"))

    # A FAILED execution contributes no clip; nothing qualified
    # is an error, never an empty manifest.
    failed_exec = dict(video_exec)
    failed_exec["state"] = "FAILED"
    failed_exec["failure"] = {"code": "provider-error",
                              "message": "provider 500",
                              "retryable": False}
    manifest_one = td.build_delivery_manifest(
        session, job, [failed_exec, audio_exec],
        delivery_root=delivery_root, ffmpeg_adapter=ffmpeg_adapter)
    check("CF-P1-005-DELIVERY-failed-excluded",
          [t["kind"] for t in manifest_one["tracks"]] == ["audio"])
    expect_error("CF-P1-005-DELIVERY-nothing-qualified",
                 lambda: td.build_delivery_manifest(
                     session, job, [failed_exec],
                     delivery_root=delivery_root,
                     ffmpeg_adapter=ffmpeg_adapter))
    expect_error("CF-P1-005-DELIVERY-empty-executions",
                 lambda: td.build_delivery_manifest(
                     session, job, [],
                     delivery_root=delivery_root,
                     ffmpeg_adapter=ffmpeg_adapter))

    # A fabricated path never enters the manifest.
    fabricated = succeeded_execution(
        "task-vid-001", "pkt-task-vid-001", "job-delivery-001",
        {"path": "fabricated.mp4", "sha256": "0" * 64,
         "bytes": 1234, "format": "mp4"})
    expect_error("CF-P1-005-DELIVERY-fabricated-refused",
                 lambda: td.build_delivery_manifest(
                     session, job, [fabricated, audio_exec],
                     delivery_root=delivery_root,
                     ffmpeg_adapter=ffmpeg_adapter))

    # Duration disagreement between record and probe is refused.
    if has_ffmpeg:
        wrong_duration = dict(video_artifact)
        wrong_duration["duration_seconds"] = 99.0
        expect_error("CF-P1-005-DELIVERY-duration-mismatch",
                     lambda: td.validate_delivery_artifact(
                         wrong_duration, delivery_root,
                         ffmpeg_adapter=ffmpeg_adapter))

    print(f"--- CF-P1-005-DELIVERY: {_checks[0]} checks, "
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
