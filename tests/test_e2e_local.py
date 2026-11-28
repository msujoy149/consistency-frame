#!/usr/bin/env python3
"""Local end-to-end integration test (CF-WO-P1-005-R4, workstream E).

One reproducible local chain, all real, no paid provider, no
credentials, no network:

  validated production task packet (real planning pipeline:
  job -> bundle -> compiled task package)
  -> local media execution (real FFmpeg operations driven
     through the execution state machine)
  -> verified output artifact (SHA-256 + byte size recomputed
     from disk, ffprobe metadata)
  -> timeline manifest construction (geometry + frame rate
     from the verified probe, against the job's output target)
  -> delivery validation
  -> final evidence record (written and read back)

FFmpeg/ffprobe are REQUIRED: when they are absent the suite
fails (exit 1) instead of skipping — skipped FFmpeg tests
must never count as integration coverage.

Honest scope: no creative AI generation is performed here.
The video clip is a deterministic lavfi fixture transcoded
to the job's validated output geometry, and the audio clip
is a deterministic WAV fixture probed by ffprobe. The local
steps are technical media operations, not the packets'
creative fulfilment — the evidence record says so. The
preflight guard that refuses a creative packet to the FFmpeg
adapter is asserted intact; the test drives the technical
operation explicitly through translate + submit_execution,
never through prepare().
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
from runtime.execution_orchestrator import submit_execution  # noqa: E402
from runtime.media_adapters import FFmpegAdapter  # noqa: E402
from runtime.media_execution import (  # noqa: E402
    MediaExecutionError, create_execution, execution_id_for,
    transition_execution)
from runtime.task_compiler import task_packet_hash  # noqa: E402
import test_production_orchestrator as PO  # noqa: E402
import test_script_to_performance_runtime as T  # noqa: E402

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
    except MediaExecutionError:
        check(label, True)
        return
    except Exception as exc:  # noqa: BLE001 - any other error is a fail
        check(label, False, f"raised {type(exc).__name__}: {exc}")
        return
    check(label, False, "operation succeeded instead of refusing")


def fresh_session():
    root = tempfile.mkdtemp(prefix="cf-p1-005-r4-e2e-")
    profile = load_or_create_profile(root)
    session = start_session(profile, profile.workspace_id)
    _sessions.append(session)
    return session


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_video_fixture(path):
    """Deterministic 2 s, 320x240, 24 fps test clip + audio."""
    cmd = ["ffmpeg", "-y", "-v", "error",
           "-f", "lavfi", "-i",
           "testsrc=duration=2:size=320x240:rate=24",
           "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
           "-c:v", "libx264", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-shortest", path]
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          timeout=180)
    if proc.returncode != 0 or not os.path.isfile(path):
        raise RuntimeError(f"ffmpeg fixture generation failed: "
                           f"{proc.stderr}")


def make_wav_fixture(path, seconds=1, rate=8000):
    frames = b"\x00\x00" * (rate * seconds)
    with wave.open(path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(frames)


def binary_version(binary):
    proc = subprocess.run([binary, "-version"], capture_output=True,
                          text=True, timeout=30)
    if proc.returncode != 0 or not proc.stdout:
        raise RuntimeError(f"{binary} -version failed")
    return proc.stdout.splitlines()[0].strip()


def run_checks():
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        print("FAIL CF-P1-005-R4-E2E-ffmpeg-required: ffmpeg and "
              "ffprobe are required for the local end-to-end test; "
              "a skipped FFmpeg run is not integration coverage")
        return 1
    ffmpeg_version = binary_version("ffmpeg")
    ffprobe_version = binary_version("ffprobe")
    check("CF-P1-005-R4-E2E-ffmpeg-present",
          ffmpeg_version.startswith("ffmpeg version ")
          and ffprobe_version.startswith("ffprobe version "),
          f"{ffmpeg_version} / {ffprobe_version}")

    session = fresh_session()
    tmpdir = tempfile.mkdtemp(prefix="cf-p1-005-r4-e2e-")
    workspace = os.path.join(tmpdir, "workspace")
    os.makedirs(workspace)
    os.makedirs(os.path.join(workspace, "outputs"))
    make_video_fixture(os.path.join(workspace, "fixture-src.mp4"))
    make_wav_fixture(os.path.join(workspace, "fixture-voice.wav"))
    adapter = FFmpegAdapter(workspace_root=workspace)
    check("CF-P1-005-R4-E2E-adapter-version-recorded",
          adapter.binary_version() == ffmpeg_version)

    # 1. Validated production task packet, through the real
    # planning pipeline (job -> bundle -> compiled package).
    target = {"aspect_ratio": "16:9", "width": 640, "height": 360,
              "frame_rate": 30}
    job = po.create_production_job(
        session, "job-e2e-001", "proj-test-001",
        {"delivery_profile": "short-form-15-60s",
         "output_geometry": target})
    job = po.transition_job(session, job, "ANALYZING")
    bundle, job = PO.build_bundle(session, job,
                                  bundle_id="bundle-e2e-001")
    check("CF-P1-005-R4-E2E-job-plan-ready",
          job["state"] == "PLAN_READY")
    package, job = po.compile_provider_tasks(
        session, job, bundle, PO.short_analysis())
    check("CF-P1-005-R4-E2E-package-compiled",
          isinstance(package, dict)
          and len(package.get("packets") or []) > 0,
          str(len(package.get("packets") or [])))
    job["task_package"] = package
    video_packets = [p for p in package["packets"]
                     if p["task_type"] == "video-generation"]
    voice_packets = [p for p in package["packets"]
                     if p["task_type"] == "voice-generation"]
    check("CF-P1-005-R4-E2E-packets-present",
          len(video_packets) >= 1 and len(voice_packets) >= 1,
          "video=%d voice=%d"
          % (len(video_packets), len(voice_packets)))
    video_packet = video_packets[0]
    voice_packet = voice_packets[0]
    for packet in (video_packet, voice_packet):
        check("CF-P1-005-R4-E2E-packet-hash: "
              + packet["task_id"],
              isinstance(packet.get("packet_hash"), str)
              and packet["packet_hash"]
              == task_packet_hash(packet))

    def execute_local(packet, operation, output_rel):
        """One local technical execution through the machine.

        The preflight guard (FFmpeg serves media-technical
        tasks, not creative packets) is asserted intact; the
        technical operation is driven explicitly via translate
        + submit_execution and recorded as such.
        """
        record, updated_job = create_execution(
            session, job, packet, "provider-ffmpeg",
            "adapter-ffmpeg")
        execution_id = record["execution_id"]
        check("CF-P1-005-R4-E2E-execution-id-deterministic: "
              + packet["task_id"],
              execution_id == execution_id_for(
                  job["job_id"], packet["task_id"],
                  "provider-ffmpeg", packet["packet_hash"], 1))
        record, updated_job = transition_execution(
            session, updated_job, execution_id,
            "WAITING_FOR_AUTHORIZATION",
            reason="local technical operation planned")
        record, updated_job = transition_execution(
            session, updated_job, execution_id, "READY",
            reason="local technical operation ready")
        context = {"ffmpeg_operation": operation,
                   "execution_id": execution_id}
        guard = adapter.preflight(packet, context)
        check("CF-P1-005-R4-E2E-preflight-guard-intact: "
              + packet["task_id"],
              any("does not serve" in error for error in guard),
              str(guard))
        request = adapter.translate(packet, context)
        record, updated_job = submit_execution(
            session, updated_job, execution_id, adapter, request,
            context=context)
        check("CF-P1-005-R4-E2E-submitted-to-validating: "
              + packet["task_id"],
              record["state"] == "VALIDATING_OUTPUT"
              and record.get("output") is not None,
              str(record.get("state")))
        return record, updated_job, execution_id

    # 2. Local media execution: transcode the fixture to the
    # job's validated output geometry.
    video_record, job, video_eid = execute_local(
        video_packet,
        {"operation": "transcode", "inputs": ["fixture-src.mp4"],
         "output": "outputs/e2e-video.mp4",
         "options": {"size": "640x360", "fps": 30}},
        "outputs/e2e-video.mp4")
    # 3. Local media execution: probe the audio fixture.
    audio_record, job, audio_eid = execute_local(
        voice_packet,
        {"operation": "probe", "inputs": ["fixture-voice.wav"]},
        "fixture-voice.wav")

    # 4. Verified output artifacts: SHA-256 + byte size
    # recomputed from disk, then ffprobe metadata.
    verified = {}
    for record in (video_record, audio_record):
        artifact = record["output"]
        real = os.path.join(workspace, artifact["path"])
        digest = sha256_file(real)
        size = os.path.getsize(real)
        check("CF-P1-005-R4-E2E-artifact-verified: "
              + artifact["path"],
              artifact["sha256"] == digest
              and artifact["bytes"] == size,
              f"recorded {artifact['sha256'][:12]}.. vs disk "
              f"{digest[:12]}..")
        probe = adapter.probe(artifact["path"])
        verified[artifact["path"]] = probe
        record, job = transition_execution(
            session, job, record["execution_id"], "SUCCEEDED",
            reason="artifact verified", output=artifact)
        check("CF-P1-005-R4-E2E-execution-succeeded: "
              + record["task_id"],
              record["state"] == "SUCCEEDED")
    video_probe = verified["outputs/e2e-video.mp4"]
    check("CF-P1-005-R4-E2E-probe-geometry",
          video_probe.get("width") == 640
          and video_probe.get("height") == 360
          and video_probe.get("frame_rate") == 30
          and video_probe.get("duration_seconds") is not None
          and abs(video_probe["duration_seconds"] - 2.0) < 0.15,
          str({k: video_probe.get(k) for k in
               ("width", "height", "frame_rate",
                "duration_seconds", "codec")}))
    check("CF-P1-005-R4-E2E-probe-audio",
          len(verified["fixture-voice.wav"].get("audio_streams")
              or []) >= 1)

    # 5. Timeline manifest construction + delivery validation.
    # The SUCCEEDED records live on the job's execution list.
    succeeded = [r for r in job.get("executions") or []
                 if r.get("state") == "SUCCEEDED"]
    check("CF-P1-005-R4-E2E-two-succeeded-on-job",
          len(succeeded) == 2, str(len(succeeded)))
    manifest = td.build_delivery_manifest(
        session, job, succeeded, delivery_root=workspace,
        ffmpeg_adapter=adapter)
    check("CF-P1-005-R4-E2E-manifest-geometry",
          manifest.get("aspect_ratio") == "16:9"
          and manifest.get("resolution")
          == {"width": 640, "height": 360}
          and manifest.get("frame_rate") == 30,
          str({k: manifest.get(k) for k in
               ("aspect_ratio", "resolution", "frame_rate")}))
    check("CF-P1-005-R4-E2E-manifest-tracks",
          [t["kind"] for t in manifest.get("tracks") or []]
          == ["video", "audio"])
    check("CF-P1-005-R4-E2E-manifest-format",
          manifest.get("format") == "editor_neutral_v1"
          and manifest.get("id") == "timeline-job-e2e-001")
    for artifact in (video_record["output"], audio_record["output"]):
        checked = td.validate_delivery_artifact(
            artifact, workspace, ffmpeg_adapter=adapter)
        check("CF-P1-005-R4-E2E-delivery-validated: "
              + artifact["path"],
              checked["sha256"] == artifact["sha256"])
    summary = td.delivery_manifest_summary(manifest)
    check("CF-P1-005-R4-E2E-manifest-summary",
          summary.get("video_clips") == 1
          and summary.get("audio_clips") == 1
          and summary.get("tracks") == 2,
          str(summary))
    try:
        import jsonschema
        with open(os.path.join(ROOT_ABS, "schemas",
                               "timeline-manifest.json"),
                  encoding="utf-8") as handle:
            schema = json.load(handle)
        jsonschema.validate(manifest, schema)
        check("CF-P1-005-R4-E2E-manifest-schema-valid", True)
    except ImportError:
        print("SKIP CF-P1-005-R4-E2E-manifest-schema-valid: "
              "jsonschema not installed")
    except Exception as exc:  # noqa: BLE001 - validation failure
        check("CF-P1-005-R4-E2E-manifest-schema-valid", False,
              str(exc))

    # 6. Final evidence record: written and read back.
    evidence = {
        "test_id": "CF-P1-005-R4-E2E",
        "job_id": job["job_id"],
        "project_id": job["project_id"],
        "output_geometry": target,
        "packets": [{"packet_id": p["packet_id"],
                     "task_id": p["task_id"],
                     "task_type": p["task_type"],
                     "packet_hash": p["packet_hash"]}
                    for p in (video_packet, voice_packet)],
        "executions": [
            {"execution_id": video_eid,
             "task_id": video_packet["task_id"],
             "provider_id": "provider-ffmpeg",
             "state": "SUCCEEDED",
             "artifact": {
                 "path": video_record["output"]["path"],
                 "sha256": video_record["output"]["sha256"],
                 "bytes": video_record["output"]["bytes"]}},
            {"execution_id": audio_eid,
             "task_id": voice_packet["task_id"],
             "provider_id": "provider-ffmpeg",
             "state": "SUCCEEDED",
             "artifact": {
                 "path": audio_record["output"]["path"],
                 "sha256": audio_record["output"]["sha256"],
                 "bytes": audio_record["output"]["bytes"]}}],
        "probe": {"video": {
            "width": video_probe.get("width"),
            "height": video_probe.get("height"),
            "frame_rate": video_probe.get("frame_rate"),
            "duration_seconds": video_probe.get("duration_seconds"),
            "codec": video_probe.get("codec")}},
        "manifest": {
            "id": manifest["id"],
            "aspect_ratio": manifest.get("aspect_ratio"),
            "resolution": manifest.get("resolution"),
            "frame_rate": manifest.get("frame_rate")},
        "tools": {"ffmpeg": ffmpeg_version,
                  "ffprobe": ffprobe_version},
        "scope": ("local technical operations on deterministic "
                  "fixtures only; no creative AI generation was "
                  "performed and no paid provider was called"),
    }
    evidence_path = os.path.join(tmpdir, "e2e-evidence.json")
    with open(evidence_path, "w", encoding="utf-8") as handle:
        json.dump(evidence, handle, indent=2, sort_keys=True)
        handle.write("\n")
    with open(evidence_path, encoding="utf-8") as handle:
        read_back = json.load(handle)
    check("CF-P1-005-R4-E2E-evidence-roundtrip",
          read_back == evidence
          and read_back["manifest"]["resolution"]
          == {"width": 640, "height": 360}
          and read_back["probe"]["video"]["frame_rate"] == 30)

    print(f"--- CF-P1-005-R4-E2E: {_checks[0]} checks, "
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
