#!/usr/bin/env python3
"""P1-006 asset tests (CF-WO-P1-006, Phase B).

Asset registration and resolution, missing assets, corrupted
media, incorrect hashes, invalid paths, the private-asset
policy, and the commercial-license restriction — plus the
FFmpeg visual-generation stage (all six recipe kinds produce
real 1080x1920, 30 FPS clips of the requested duration).

FFmpeg/ffprobe are REQUIRED: the suite fails (exit 1) when they
are absent, never skips — skipped media tests must never count
as asset coverage.
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
from runtime import production_assets as pa  # noqa: E402

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
    except pa.AssetError:
        check(label, True)
        return
    except Exception as exc:  # noqa: BLE001 - any other error is a fail
        check(label, False, f"raised {type(exc).__name__}: {exc}")
        return
    check(label, False, "operation succeeded instead of refusing")


def require_ffmpeg():
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        print("FAIL ffmpeg/ffprobe are required for the asset tests")
        sys.exit(1)


def make_record(**overrides):
    record = pa.new_asset_record(
        asset_id="vis-s1", project_id="p1006-vertical-explainer",
        shot_id="s1", asset_type="video-clip",
        provider="ffmpeg-local", provider_status="EXERCISED",
        path="vis-s1.mp4", mime_type="video/mp4",
        provenance="INFERRED_FOR_PRODUCTION")
    record.update(overrides)
    return record


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_wav(path, seconds=1, rate=48000):
    frames = int(rate * seconds)
    with wave.open(path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x10\x00" * frames)


def make_clip(path, seconds=2):
    cmd = ["ffmpeg", "-y", "-v", "error",
           "-f", "lavfi", "-i",
           f"testsrc=duration={seconds}:size=1080x1920:rate=30",
           "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
           "-c:v", "libx264", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-shortest", path]
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          timeout=180)
    if proc.returncode != 0 or not os.path.isfile(path):
        raise RuntimeError(f"ffmpeg fixture failed: {proc.stderr}")


# --- records ----------------------------------------------------

def test_record_validation():
    check("record-valid", pa.validate_asset_record(make_record()) == [])
    for field, bad in (
            ("asset_id", "Bad ID"), ("project_id", ""),
            ("shot_id", "S1"), ("asset_type", "hologram"),
            ("path", "/tmp/escape.mp4"), ("path", "../escape.mp4"),
            ("mime_type", "not-a-mime"),
            ("sha256", "deadbeef"), ("status", "DONE"),
            ("provenance", "MAYBE")):
        record = make_record(**{field: bad})
        check(f"record-bad-{field}",
              len(pa.validate_asset_record(record)) > 0)
    mime_mismatch = make_record(mime_type="audio/wav")
    check("record-mime-extension-mismatch",
          len(pa.validate_asset_record(mime_mismatch)) > 0)
    check("record-not-object",
          len(pa.validate_asset_record("nope")) > 0)


def test_registration_and_resolution():
    registry = pa.register_asset({}, make_record())
    check("register-one", "vis-s1" in registry)
    expect_error("register-duplicate-refused",
                 lambda: pa.register_asset(registry, make_record()))
    check("resolve-known",
          pa.resolve_asset(registry, "vis-s1")["asset_id"] == "vis-s1")
    expect_error("resolve-missing-refused",
                 lambda: pa.resolve_asset(registry, "vis-nope"))
    private = make_record(asset_id="priv-1")
    private["privacy"]["classification"] = "private"
    private["privacy"]["transmit_to_provider"] = True
    expect_error("private-transmit-refused",
                 lambda: pa.register_asset({}, private))
    private_ok = make_record(asset_id="priv-1")
    private_ok["privacy"]["classification"] = "private"
    private_ok["privacy"]["transmit_to_provider"] = False
    check("private-no-transmit-ok",
          "priv-1" in pa.register_asset({}, private_ok))
    bad = make_record(asset_id="bad!!")
    expect_error("register-invalid-refused",
                 lambda: pa.register_asset({}, bad))


def test_commercial_restriction():
    check("commercial-original-ok",
          pa.check_commercial_delivery(make_record()) == [])
    licensed = make_record()
    licensed["license"]["class"] = "licensed"
    check("commercial-licensed-ok",
          pa.check_commercial_delivery(licensed) == [])
    unknown = make_record()
    unknown["license"]["class"] = "unknown"
    check("commercial-unknown-blocked",
          len(pa.check_commercial_delivery(unknown)) > 0)
    cc_by_nc = make_record()
    cc_by_nc["license"]["class"] = "cc-by-nc"
    check("commercial-cc-by-nc-blocked",
          len(pa.check_commercial_delivery(cc_by_nc)) > 0)


# --- verification ------------------------------------------------

def test_verify_asset():
    root = tempfile.mkdtemp(prefix="cf-p1006-assets-")
    clip = os.path.join(root, "vis-s1.mp4")
    make_clip(clip, seconds=2)
    sha, size = pa.hash_file(clip)
    record = make_record(size_bytes=size, sha256=sha)
    record["status"] = "GENERATED"
    verified = pa.verify_asset(record, root)
    check("verify-ok", verified["status"] == "VERIFIED")
    check("verify-size", verified["size_bytes"] == size)
    check("verify-sha", verified["sha256"] == sha)
    check("verify-width", verified["width"] == 1080)
    check("verify-height", verified["height"] == 1920)
    check("verify-fps",
          verified["frame_rate"] is not None
          and abs(verified["frame_rate"] - 30.0) < 0.01)
    check("verify-duration",
          verified["duration_seconds"] is not None
          and abs(verified["duration_seconds"] - 2.0) < 0.1)
    wrong_size = make_record(size_bytes=size + 1, sha256=sha)
    expect_error("verify-wrong-size-refused",
                 lambda: pa.verify_asset(wrong_size, root))
    wrong_sha = make_record(size_bytes=size, sha256="0" * 64)
    expect_error("verify-wrong-sha-refused",
                 lambda: pa.verify_asset(wrong_sha, root))
    missing = make_record(path="vis-missing.mp4")
    expect_error("verify-missing-refused",
                 lambda: pa.verify_asset(missing, root))
    corrupted = make_record(path="vis-corrupt.mp4")
    with open(os.path.join(root, "vis-corrupt.mp4"), "wb") as handle:
        handle.write(b"this is not a video file at all")
    expect_error("verify-corrupt-refused",
                 lambda: pa.verify_asset(corrupted, root))
    # A corrupted file whose hash was recorded pre-corruption is
    # caught by the hash check before probing even runs.
    tampered_path = os.path.join(root, "vis-tampered.mp4")
    shutil.copyfile(clip, tampered_path)
    tampered = make_record(asset_id="vis-tampered",
                          path="vis-tampered.mp4",
                          size_bytes=size, sha256=sha)
    with open(tampered_path, "ab") as handle:
        handle.write(b"tamper")
    expect_error("verify-tampered-refused",
                 lambda: pa.verify_asset(tampered, root))
    # Width disagreement is caught by the probe check.
    wrong_width = make_record(size_bytes=size, sha256=sha, width=720)
    expect_error("verify-wrong-width-refused",
                 lambda: pa.verify_asset(wrong_width, root))


def test_probe():
    root = tempfile.mkdtemp(prefix="cf-p1006-probe-")
    clip = os.path.join(root, "clip.mp4")
    make_clip(clip, seconds=2)
    probe = pa.probe_media_file(clip)
    check("probe-format", "mp4" in probe["format_name"])
    check("probe-video-codec", probe["video_codec"] == "h264")
    check("probe-audio-codec", probe["audio_codec"] == "aac")
    check("probe-rational", probe["frame_rate_rational"] == "30/1")
    expect_error("probe-missing-refused",
                 lambda: pa.probe_media_file(
                     os.path.join(root, "nope.mp4")))


# --- visual generation -------------------------------------------

def test_visual_generation():
    root = tempfile.mkdtemp(prefix="cf-p1006-visual-")
    kinds = {
        "gradient-band": ["1a2b4c", "3d6e9e"],
        "gradient-split": ["0f3d3e", "2a7f7f"],
        "gradient-rings": ["241a4c", "5b3d9e"],
        "gradient-scan": ["1c2733", "4a6b8a"],
        "gradient-frames": ["123527", "2e7d4f"],
        "gradient-title": ["0b1220", "1e3a5f"],
    }
    for index, (kind, colors) in enumerate(kinds.items()):
        recipe = {"kind": kind, "colors": colors,
                  "accent_color": "ffffff", "text_color": "ffffff",
                  "keyword": f"SHOT {index + 1}",
                  "subtext": "test line",
                  "fontsize": 96}
        out = os.path.join(root, f"vis-{kind}.mp4")
        record = pa.generate_visual_asset(
            recipe, 3.0, out, asset_id=f"vis-{kind}",
            project_id="p1006-vertical-explainer",
            shot_id=f"s{index + 1}")
        check(f"visual-{kind}-verified",
              record["status"] == "VERIFIED")
        check(f"visual-{kind}-geometry",
              record["width"] == 1080 and record["height"] == 1920)
        check(f"visual-{kind}-fps",
              record["frame_rate"] is not None
              and abs(record["frame_rate"] - 30.0) < 0.01)
        check(f"visual-{kind}-duration",
              record["duration_seconds"] is not None
              and abs(record["duration_seconds"] - 3.0) < 0.1)
        check(f"visual-{kind}-provider",
              record["source"]["provider"] == "ffmpeg-local"
              and record["source"]["provider_status"] == "EXERCISED")
        check(f"visual-{kind}-hash",
              record["sha256"] == sha256_file(out))
        # The keyword text must actually be visible at the shot
        # midpoint: crop the centre band where the text sits and
        # require near-white pixels (the keyword is white). A
        # drawtext alpha expression once made every frame
        # text-free while the render still succeeded — this check
        # pins the fix.
        mid = record["duration_seconds"] / 2.0
        proc = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", str(mid), "-i", out,
             "-vf", "crop=1080:300:0:810,format=gray",
             "-frames:v", "1", "-f", "rawvideo", "-"],
            capture_output=True, timeout=120)
        bright = max(proc.stdout) if proc.stdout else 0
        check(f"visual-{kind}-keyword-visible", bright >= 240,
              f"brightest centre-band pixel {bright}, expected >= 240")
    expect_error("visual-unknown-kind-refused",
                 lambda: pa.generate_visual_asset(
                     {"kind": "neural-render",
                      "colors": ["000000", "ffffff"]},
                     2.0, os.path.join(root, "x.mp4"),
                     asset_id="vis-x",
                     project_id="p1006-vertical-explainer",
                     shot_id="s1"))
    expect_error("visual-bad-duration-refused",
                 lambda: pa.visual_argv(
                     {"kind": "gradient-band",
                      "colors": ["000000", "ffffff"]},
                     0, os.path.join(root, "x.mp4")))
    argv = pa.visual_argv(
        {"kind": "gradient-band", "colors": ["000000", "ffffff"],
         "keyword": "HI"}, 2.0, os.path.join(root, "x.mp4"))
    check("visual-argv-deterministic",
          argv == pa.visual_argv(
              {"kind": "gradient-band",
               "colors": ["000000", "ffffff"], "keyword": "HI"},
              2.0, os.path.join(root, "x.mp4")))
    # A recipe fontsize is honoured (the reference project's
    # longest keyword needs a smaller size or it overflows the
    # frame edges).
    small_argv = pa.visual_argv(
        {"kind": "gradient-band", "colors": ["000000", "ffffff"],
         "keyword": "A LONG KEYWORD HERE", "fontsize": 64},
        2.0, os.path.join(root, "x.mp4"))
    check("visual-argv-recipe-fontsize",
          "fontsize=64" in " ".join(small_argv)
          and "fontsize=96" not in " ".join(small_argv),
          " ".join(small_argv))
    # Byte-level determinism: the same recipe rendered twice must
    # produce identical files. The gradients source seeds its
    # geometry randomly by default, so two runs once produced
    # different SHAs for the same shot — the seed is now fixed.
    det_recipe = {"kind": "gradient-band",
                  "colors": ["1a2b4c", "3d6e9e"],
                  "accent_color": "ffffff", "text_color": "ffffff",
                  "keyword": "SAME FACE", "subtext": "test line"}
    det_paths = []
    for i in (1, 2):
        det_out = os.path.join(root, f"det-{i}.mp4")
        pa.generate_visual_asset(
            det_recipe, 2.0, det_out, asset_id=f"vis-det-{i}",
            project_id="p1006-vertical-explainer", shot_id="s1")
        det_paths.append(det_out)
    check("visual-byte-deterministic",
          sha256_file(det_paths[0]) == sha256_file(det_paths[1]),
          f"{sha256_file(det_paths[0])[:12]} vs "
          f"{sha256_file(det_paths[1])[:12]}")


def main():
    require_ffmpeg()
    test_record_validation()
    test_registration_and_resolution()
    test_commercial_restriction()
    test_verify_asset()
    test_probe()
    test_visual_generation()
    print(f"CF-P1-006-ASSETS: {_checks[0]} checks, "
          f"{len(failures)} failures")
    if failures:
        print("FAILURES:", failures)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
