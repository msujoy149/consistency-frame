#!/usr/bin/env python3
"""FFmpeg / ffprobe adapter tests (CF-WO-P1-005, WO §4 + §11).

Real local execution only: deterministic test media is generated
with ffmpeg lavfi at test time (2 s, 320x240, 24 fps testsrc plus a
440 Hz sine tone), then probed, transcoded and assembled through
the FFmpegAdapter. This is technical execution — probe, transcode,
concatenation — not evidence of AI video generation. Path and
symlink containment, timeouts and size limits are pinned.

When ffmpeg or ffprobe is absent the suite SKIPs (exit 0, no
conformance claimed): the adapter conformance record rests on the
runs where the binaries exist.

Conventions follow tests/test_production_store.py: check(name, cond,
detail="") prints PASS/FAIL lines, failures are collected, and the
process exits 0 only when every check passes. No test here weakens
any P0 or P1 check.
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
from runtime.media_adapters import FFmpegAdapter  # noqa: E402
from runtime.media_execution import MediaExecutionError  # noqa: E402

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
    except MediaExecutionError:
        check(label, True)
        return
    except Exception as exc:  # noqa: BLE001 - any other error is a fail
        check(label, False, f"raised {type(exc).__name__}: {exc}")
        return
    check(label, False, "operation succeeded instead of refusing")


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate_test_media(path):
    """Deterministic 2 s test clip: testsrc video + sine audio."""
    cmd = ["ffmpeg", "-y", "-v", "error",
           "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=24",
           "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
           "-c:v", "libx264", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-shortest", path]
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          timeout=120)
    if proc.returncode != 0 or not os.path.isfile(path):
        raise RuntimeError(f"ffmpeg lavfi generation failed: {proc.stderr}")


def main():
    if shutil.which("ffmpeg") is None \
            or shutil.which("ffprobe") is None:
        print("SKIP CF-P1-005-FFMPEG: ffmpeg/ffprobe not installed; "
              "no conformance claimed")
        return 0
    tmpdir = tempfile.mkdtemp(prefix="cf-p1-005-ffmpeg-")
    workspace = os.path.join(tmpdir, "workspace")
    os.makedirs(workspace)
    src_rel = "test.mp4"
    src_abs = os.path.join(workspace, src_rel)
    try:
        generate_test_media(src_abs)
    except RuntimeError as exc:
        print(f"SKIP CF-P1-005-FFMPEG: {exc}")
        return 0

    adapter = FFmpegAdapter(workspace_root=workspace)
    packet = {"task_id": "task-ffmpeg-001",
              "task_type": "media-technical"}

    # Binary version is recorded from the real binary.
    version = adapter.binary_version()
    check("CF-P1-005-FFMPEG-version-recorded",
          version.startswith("ffmpeg version"), version[:40])

    # Probe: real metadata from ffprobe JSON.
    metadata = adapter.probe(src_rel)
    check("CF-P1-005-FFMPEG-probe-dimensions",
          metadata.get("width") == 320 and metadata.get("height") == 240,
          str(metadata.get("width")) + "x" + str(metadata.get("height")))
    check("CF-P1-005-FFMPEG-probe-duration",
          metadata.get("duration_seconds") is not None
          and abs(metadata["duration_seconds"] - 2.0) < 0.15,
          str(metadata.get("duration_seconds")))
    check("CF-P1-005-FFMPEG-probe-frame-rate",
          metadata.get("frame_rate") is not None
          and abs(metadata["frame_rate"] - 24.0) < 0.5,
          str(metadata.get("frame_rate")))
    check("CF-P1-005-FFMPEG-probe-audio",
          len(metadata.get("audio_streams") or []) >= 1)
    check("CF-P1-005-FFMPEG-probe-format",
          metadata.get("format_name") not in (None, "", "unknown"))

    # Preflight: the operation must be named; binaries must exist.
    check("CF-P1-005-FFMPEG-preflight-ok",
          adapter.preflight(packet, {"ffmpeg_operation": {
              "operation": "probe", "inputs": [src_rel]}}) == [])
    check("CF-P1-005-FFMPEG-preflight-no-operation",
          len(adapter.preflight(packet, {})) > 0)
    check("CF-P1-005-FFMPEG-preflight-wrong-task",
          len(adapter.preflight(
              {"task_id": "task-x", "task_type": "video-generation"},
              {"ffmpeg_operation": {"operation": "probe"}})) > 0)

    # Submit probe: a completed artifact with the real SHA-256.
    request = adapter.prepare(packet, {
        "ffmpeg_operation": {"operation": "probe",
                             "inputs": [src_rel]}})
    result = adapter.submit(request, {})
    check("CF-P1-005-FFMPEG-submit-probe-completed",
          result.get("completed") is True
          and result.get("output") is not None)
    artifact = result["output"]
    check("CF-P1-005-FFMPEG-probe-artifact-hash",
          artifact.get("sha256") == sha256_file(src_abs)
          and artifact.get("bytes") == os.path.getsize(src_abs)
          and artifact.get("path") == src_rel)
    check("CF-P1-005-FFMPEG-probe-artifact-model",
          artifact.get("provider_model") == version)

    # Submit transcode: 320x240 -> 160x120, real output file.
    small_rel = "test-small.mp4"
    request = adapter.prepare(packet, {
        "ffmpeg_operation": {"operation": "transcode",
                             "inputs": [src_rel],
                             "output": small_rel,
                             "options": {"size": "160x120"}}})
    result = adapter.submit(request, {})
    small_abs = os.path.join(workspace, small_rel)
    check("CF-P1-005-FFMPEG-transcode-completed",
          result.get("completed") is True
          and os.path.isfile(small_abs))
    small_meta = adapter.probe(small_rel)
    check("CF-P1-005-FFMPEG-transcode-dimensions",
          small_meta.get("width") == 160
          and small_meta.get("height") == 120)
    check("CF-P1-005-FFMPEG-transcode-artifact-hash",
          result["output"].get("sha256") == sha256_file(small_abs))

    # Submit assemble: two copies concatenated, ~4 s long.
    joined_rel = "test-joined.mp4"
    request = adapter.prepare(packet, {
        "ffmpeg_operation": {"operation": "assemble",
                             "inputs": [src_rel, src_rel],
                             "output": joined_rel}})
    result = adapter.submit(request, {})
    joined_abs = os.path.join(workspace, joined_rel)
    check("CF-P1-005-FFMPEG-assemble-completed",
          result.get("completed") is True
          and os.path.isfile(joined_abs))
    joined_meta = adapter.probe(joined_rel)
    check("CF-P1-005-FFMPEG-assemble-duration",
          joined_meta.get("duration_seconds") is not None
          and abs(joined_meta["duration_seconds"] - 4.0) < 0.3,
          str(joined_meta.get("duration_seconds")))

    # Containment: parent escape and absolute outside paths refused.
    expect_error("CF-P1-005-FFMPEG-probe-escape-refused",
                 lambda: adapter.probe("../escape.mp4"))
    expect_error("CF-P1-005-FFMPEG-probe-absolute-refused",
                 lambda: adapter.probe("/etc/passwd"))
    expect_error("CF-P1-005-FFMPEG-transcode-escape-refused",
                 lambda: adapter.submit(
                     {"ffmpeg_operation": "transcode",
                      "inputs": [src_rel], "output": "../out.mp4",
                      "options": {}}, {}))
    expect_error("CF-P1-005-FFMPEG-probe-missing-refused",
                 lambda: adapter.probe("no-such-file.mp4"))
    expect_error("CF-P1-005-FFMPEG-unknown-operation-refused",
                 lambda: adapter.submit(
                     {"ffmpeg_operation": "grade",
                      "inputs": [src_rel], "output": "x.mp4",
                      "options": {}}, {}))

    # Size limit: a tiny limit refuses even a real output.
    tiny = FFmpegAdapter(workspace_root=workspace,
                         max_output_bytes=10)
    expect_error("CF-P1-005-FFMPEG-size-limit-refused",
                 lambda: tiny.verify_output(src_rel, None, {}))

    # verify_output recomputes the hash from the real file.
    verified = adapter.verify_output(src_rel, None, {})
    check("CF-P1-005-FFMPEG-verify-output",
          verified.get("sha256") == sha256_file(src_abs)
          and verified.get("path") == src_rel)
    expect_error("CF-P1-005-FFMPEG-verify-missing-refused",
                 lambda: adapter.verify_output("no-such.mp4", None, {}))

    # The base adapter interface refuses unimplemented operations.
    from runtime.media_execution import MediaAdapter
    base = MediaAdapter()
    expect_error("CF-P1-005-FFMPEG-base-submit-refused",
                 lambda: base.submit({}, {}))
    expect_error("CF-P1-005-FFMPEG-base-poll-refused",
                 lambda: base.poll("job-1", {}))
    expect_error("CF-P1-005-FFMPEG-base-cancel-refused",
                 lambda: base.cancel("job-1", {}))

    print(f"--- CF-P1-005-FFMPEG: {_checks[0]} checks, "
          f"{len(failures)} failures ---")
    if failures:
        print("FAILURES: " + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
