#!/usr/bin/env python3
"""Character-consistency tests (CF-WO-P1-006-R1).

Covers the character bible, reference asset integrity,
project-local identity isolation, cross-scene binding,
consistency evaluation and drift detection, scene provenance
and image-generation status honesty, the voice commercial
restriction, dialogue mapping, the six-scene timeline, missing
scene and asset-tampering rejection, the audio-mix regression
(multi-clip dialogue with ducking: every line must survive in
the mix), the review package and the human approval gate, and
one end-to-end fixture render through the R1 driver.

FFmpeg/ffprobe are REQUIRED: when they are absent the suite
fails (exit 1) instead of skipping. All generated media lives
in tempfile dirs. No test here calls a paid provider and no
test generates a real character image: fixture stills are
solid-colour frames made with FFmpeg, and the real Mara stills
are verified by the delivery evidence, not by CI.
"""

import copy
import hashlib
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import wave

ROOT = os.path.join(os.path.dirname(__file__), "..")
ROOT_ABS = os.path.abspath(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
from runtime import character_consistency as cc  # noqa: E402
from runtime import production_assets as pa  # noqa: E402
from runtime import production_audio as aud  # noqa: E402
from runtime import production_delivery as pdel  # noqa: E402
from runtime import production_qc as qc  # noqa: E402
from runtime import production_timeline as tl  # noqa: E402
from runtime import vertical_production as vp  # noqa: E402

EXAMPLE = os.path.join(ROOT_ABS, "examples",
                       "p1006-r1-character-consistency")
PROJECT_ID = "p1006-r1-character-consistency"

failures = []
_checks = [0]


def check(name, cond, detail=""):
    _checks[0] += 1
    if cond:
        print(f"PASS {name}")
    else:
        print(f"FAIL {name} {detail}")
        failures.append(name)


def expect_error(label, fn, kinds=(Exception,)):
    try:
        fn()
    except kinds:
        check(label, True)
        return None
    except Exception as exc:  # noqa: BLE001 - any other error fails
        check(label, False, f"raised {type(exc).__name__}: {exc}")
        return None
    check(label, False, "operation succeeded instead of refusing")
    return None


def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, payload):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def write_text(path, text):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def run_ffmpeg(argv, label):
    proc = subprocess.run(argv, capture_output=True, text=True,
                          timeout=300)
    if proc.returncode != 0:
        raise AssertionError(
            f"{label} failed: {(proc.stderr or '').strip()[:400]}")


def make_png(path, color="0x0F6B6B", width=108, height=192):
    """Detail-rich fixture still (NOT a character image).

    A Mandelbrot frame, not a solid colour or smooth gradient:
    the frozen-segment QC flags a video whose frames never
    change, and a smooth still stays pixel-identical under a
    slow zoompan. The colour value only picks a different
    fractal window so fixture stills differ from each other.
    """
    seed = int(color, 16) % 97
    dx = (seed % 10) * 0.05
    dy = (seed // 10) * 0.05
    run_ffmpeg(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                "-i", f"mandelbrot=s={width}x{height}:"
                     f"start_x={-0.74 + dx:.2f}:"
                     f"start_y={-0.13 + dy:.2f}",
                "-frames:v", "1", path],
               f"fixture still {path}")


def make_tone_wav(path, seconds=1.0, freq=440.0, rate=48000,
                  amplitude=0.5, channels=1):
    count = int(round(seconds * rate))
    frames = bytearray()
    for n in range(count):
        value = int(round(
            amplitude * 32767
            * math.sin(2 * math.pi * freq * n / rate)))
        for _ in range(channels):
            frames += struct.pack("<h", value)
    with wave.open(path, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(bytes(frames))
    return path


def rms_in_window(path, start, end):
    """RMS amplitude of a WAV slice (wave module, no ffmpeg)."""
    with wave.open(path, "rb") as wav:
        rate = wav.getframerate()
        channels = wav.getnchannels()
        width = wav.getsampwidth()
        frames = wav.readframes(wav.getnframes())
    total = len(frames) // (width * channels)
    first = max(0, int(start * rate))
    last = min(total, int(end * rate))
    if last <= first:
        return 0.0
    fmt = "<%dh" % ((last - first) * channels)
    values = struct.unpack(
        fmt, frames[first * width * channels:last * width * channels])
    if not values:
        return 0.0
    return math.sqrt(sum(v * v for v in values) / len(values)) / 32768.0


def parse_script_lines(script_path):
    lines = []
    pattern = re.compile(r"^- \*\*(l[0-9]+)\*\* \(shot (s[0-9]+)\): (.*)$")
    with open(script_path, encoding="utf-8") as handle:
        for raw in handle:
            match = pattern.match(raw.strip())
            if match:
                lines.append({"line_id": match.group(1),
                              "shot_id": match.group(2),
                              "text": match.group(3).strip()})
    return lines


def real_bible():
    return load_json(os.path.join(EXAMPLE, "character-bible.json"))


def real_shots():
    return load_json(os.path.join(EXAMPLE, "shot-list.json"))["shots"]


def all_pass_evaluations(shots):
    return [{
        "scene_id": s.get("scene_id"), "shot_id": s["shot_id"],
        "inspector": "r1-test-fixture",
        "checks": {a: "pass" for a in cc.CONSISTENCY_ATTRIBUTES},
        "notes": "fixture evaluation",
    } for s in shots]


def run_checks():
    bible = real_bible()
    shots = real_shots()

    # --- character bible validation ---
    check("CF-P1-006-R1-BIBLE-valid",
          cc.validate_character_bible(bible) == [],
          str(cc.validate_character_bible(bible)))
    check("CF-P1-006-R1-BIBLE-character-is-adult",
          25 <= bible["age_range"]["min_years"]
          and bible["age_range"]["max_years"] <= 30
          and bible["age_range"]["canonical_age"] == 28,
          str(bible.get("age_range")))
    check("CF-P1-006-R1-BIBLE-project-local-only",
          bible.get("is_canonical_user_character") is False
          and bible.get("is_registered_in_global_registry") is False
          and bible.get("identity_kind")
          == "project-local-demonstration",
          str({k: bible.get(k) for k in (
              "is_canonical_user_character",
              "is_registered_in_global_registry", "identity_kind")}))
    check("CF-P1-006-R1-BIBLE-signature-color-defined-once",
          bible["signature_color"]["hex"] == "0F6B6B"
          and bible["signature_color"]["defined_once"] is True,
          str(bible.get("signature_color")))
    check("CF-P1-006-R1-BIBLE-five-reference-views",
          set(bible["references"]) == {
              "front", "three_quarter", "side", "full_body",
              "expressions"},
          str(sorted(bible.get("references") or {})))
    check("CF-P1-006-R1-BIBLE-confirmed-vs-inferred",
          bible["provenance"]["design"] == "CONFIRMED"
          and isinstance(bible["provenance"].get("inferences"), list)
          and len(bible["provenance"]["inferences"]) >= 1,
          str(bible.get("provenance")))
    broken = copy.deepcopy(bible)
    del broken["outfit"]
    check("CF-P1-006-R1-BIBLE-missing-field-fails",
          any("outfit" in e
              for e in cc.validate_character_bible(broken)),
          str(cc.validate_character_bible(broken)))
    broken = copy.deepcopy(bible)
    broken["age_range"]["min_years"] = 12
    check("CF-P1-006-R1-BIBLE-under-18-fails",
          any("18" in e
              for e in cc.validate_character_bible(broken)),
          str(cc.validate_character_bible(broken)))
    broken = copy.deepcopy(bible)
    broken["is_canonical_user_character"] = True
    check("CF-P1-006-R1-BIBLE-canonical-flag-fails",
          any("canonical" in e
              for e in cc.validate_character_bible(broken)),
          str(cc.validate_character_bible(broken)))
    broken = copy.deepcopy(bible)
    broken["signature_color"]["defined_once"] = False
    check("CF-P1-006-R1-BIBLE-color-not-once-fails",
          any("defined once" in e
              for e in cc.validate_character_bible(broken)),
          str(cc.validate_character_bible(broken)))
    broken = copy.deepcopy(bible)
    del broken["references"]["side"]
    check("CF-P1-006-R1-BIBLE-missing-reference-fails",
          any("side" in e
              for e in cc.validate_character_bible(broken)),
          str(cc.validate_character_bible(broken)))
    broken = copy.deepcopy(bible)
    broken["provenance"]["design"] = "INFERRED"
    broken["provenance"]["inferences"] = []
    check("CF-P1-006-R1-BIBLE-inferred-without-record-fails",
          any("inference" in e.lower()
              for e in cc.validate_character_bible(broken)),
          str(cc.validate_character_bible(broken)))

    # --- project-local identity isolation ---
    check("CF-P1-006-R1-ISOLATION-demo-id-isolated",
          cc.check_project_local_isolation("DEMO-CHAR-001") == [],
          str(cc.check_project_local_isolation("DEMO-CHAR-001")))
    tmpdir = tempfile.mkdtemp(prefix="cf-p1006-r1-")
    try:
        # A registry that DID contain the id must fail. The record
        # is a valid v2.5 character-registration (lowercase id,
        # the schema's pattern); the file name must be one the
        # loader reads (character-registration.json). The demo id
        # itself is uppercase, so it can never be a valid registry
        # id — the collision branch is exercised with the valid
        # lowercase form.
        from runtime.identity_resolution import (  # noqa: E402
            load_authorized_character_registry)
        overlay = os.path.join(tmpdir, "overlay")
        record_dir = os.path.join(overlay, "characters",
                                  "demo-char-001")
        os.makedirs(record_dir, exist_ok=True)
        record = {
            "schema_version": "2.5",
            "character_id": "demo-char-001",
            "display_name": "Mara",
            "character_type": "Human",
            "canonical_reference_images": [{
                "asset_id": "ref-mara-front", "role": "front",
                "path": "refs/mara-front.png"}],
            "consent_permissions": {"granted": True,
                                    "source": "user"},
            "version": 1,
            "status": "approved",
            "ownership": {"owner_id": "owner-1",
                          "workspace_id": "ws-1",
                          "visibility": "private",
                          "sharing": "none"},
        }
        write_json(os.path.join(
            record_dir, "character-registration.json"), record)
        loaded = load_authorized_character_registry(overlay)
        check("CF-P1-006-R1-ISOLATION-fixture-registry-loads",
              "demo-char-001" in loaded,
              f"fixture registry did not load: {sorted(loaded)}")
        check("CF-P1-006-R1-ISOLATION-collision-fails",
              any("demo-char-001" in e for e in
                  cc.check_project_local_isolation(
                      "demo-char-001", overlay_root=overlay)),
              "collision with the global registry was not detected")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # --- cross-scene character binding ---
    binding_errors = []
    for shot in shots:
        binding_errors += cc.validate_scene_binding(bible, shot)
    check("CF-P1-006-R1-BINDING-six-shots-bind",
          binding_errors == [], str(binding_errors))
    bad = copy.deepcopy(shots[0])
    bad["character_id"] = "CHAR-999"
    check("CF-P1-006-R1-BINDING-wrong-character-fails",
          any("CHAR-999" in e
              for e in cc.validate_scene_binding(bible, bad)),
          str(cc.validate_scene_binding(bible, bad)))
    bad = copy.deepcopy(shots[0])
    bad["reference_ids"] = ["ref-no-such-view"]
    check("CF-P1-006-R1-BINDING-unknown-reference-fails",
          any("ref-no-such-view" in e
              for e in cc.validate_scene_binding(bible, bad)),
          str(cc.validate_scene_binding(bible, bad)))
    bad = copy.deepcopy(shots[0])
    bad["expression"] = "furious"
    check("CF-P1-006-R1-BINDING-unknown-expression-fails",
          any("furious" in e
              for e in cc.validate_scene_binding(bible, bad)),
          str(cc.validate_scene_binding(bible, bad)))
    bad = copy.deepcopy(shots[0])
    bad["visual"] = dict(bad.get("visual") or {})
    bad["visual"]["motion"] = "spin"
    check("CF-P1-006-R1-BINDING-unknown-motion-fails",
          any("spin" in e
              for e in cc.validate_scene_binding(bible, bad)),
          str(cc.validate_scene_binding(bible, bad)))

    # --- consistency evaluation and drift detection ---
    result = cc.evaluate_consistency(
        bible, all_pass_evaluations(shots))
    check("CF-P1-006-R1-EVAL-all-pass-consistent",
          result["overall_verdict"] == "consistent"
          and len(result["scenes"]) == 6
          and result["human_approval"] is None,
          str(result.get("overall_verdict")))
    failing = all_pass_evaluations(shots)
    failing[2]["checks"]["hair"] = "fail"
    check("CF-P1-006-R1-EVAL-one-fail-is-drift",
          cc.evaluate_consistency(bible, failing)[
              "overall_verdict"] == "drift-found",
          "a failed attribute did not produce drift-found")
    reviewing = all_pass_evaluations(shots)
    reviewing[4]["checks"]["accessories"] = "review"
    check("CF-P1-006-R1-EVAL-one-review-needs-human",
          cc.evaluate_consistency(bible, reviewing)[
              "overall_verdict"] == "needs-human-review",
          "a review finding did not produce needs-human-review")
    changed = all_pass_evaluations(shots)
    changed[0]["unexplained_changes"] = ["hair length changed"]
    check("CF-P1-006-R1-EVAL-unexplained-change-is-drift",
          cc.evaluate_consistency(bible, changed)[
              "overall_verdict"] == "drift-found",
          "an unexplained change did not produce drift-found")
    expect_error("CF-P1-006-R1-EVAL-empty-evaluations-fail",
                 lambda: cc.evaluate_consistency(bible, []),
                 kinds=(cc.CharacterConsistencyError,))
    bad_eval = all_pass_evaluations(shots)
    bad_eval[0]["checks"]["eyes"] = "maybe"
    expect_error("CF-P1-006-R1-EVAL-bad-finding-fails",
                 lambda: cc.evaluate_consistency(bible, bad_eval),
                 kinds=(cc.CharacterConsistencyError,))

    # --- reference asset integrity (fixture files) ---
    tmpdir = tempfile.mkdtemp(prefix="cf-p1006-r1-refs-")
    try:
        refs_root = os.path.join(tmpdir, "work", "references")
        os.makedirs(refs_root, exist_ok=True)
        fixture_bible = copy.deepcopy(bible)
        for view, entry in fixture_bible["references"].items():
            rel = entry["file"]
            target = os.path.join(tmpdir, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            if view == "expressions":
                make_png(target, width=192, height=128)
            else:
                make_png(target)
        report = cc.verify_reference_assets(fixture_bible, tmpdir)
        check("CF-P1-006-R1-REFS-all-five-verified",
              report["errors"] == []
              and len(report["references"]) == 5
              and all(r["status"] == "VERIFIED"
                      for r in report["references"]),
              str(report.get("errors")))
        recorded = {r["asset_id"]: r["sha256"]
                    for r in report["references"]}
        # Tamper with one reference: its SHA must change.
        front = os.path.join(refs_root, "mara-front-ref.png")
        with open(front, "ab") as handle:
            handle.write(b"tampered")
        report2 = cc.verify_reference_assets(fixture_bible, tmpdir)
        changed_sha = {r["asset_id"]: r["sha256"]
                       for r in report2["references"]}
        check("CF-P1-006-R1-REFS-tamper-changes-sha",
              changed_sha.get("ref-mara-front")
              != recorded.get("ref-mara-front"),
              "a tampered reference kept its recorded SHA")
        os.remove(front)
        report3 = cc.verify_reference_assets(fixture_bible, tmpdir)
        check("CF-P1-006-R1-REFS-missing-file-errors",
              any("ref-mara-front" in e
                  for e in report3["errors"]),
              str(report3.get("errors")))
        escaping = copy.deepcopy(fixture_bible)
        escaping["references"]["front"]["file"] = "../escape.png"
        report4 = cc.verify_reference_assets(escaping, tmpdir)
        check("CF-P1-006-R1-REFS-path-escape-refused",
              any("escapes" in e for e in report4["errors"]),
              str(report4.get("errors")))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # --- scene provenance and image-generation honesty ---
    check("CF-P1-006-R1-PROVENANCE-six-distinct-stills",
          len(shots) == 6
          and len({(s.get("visual") or {}).get("still_file")
                   for s in shots}) == 6,
          str([(s.get("visual") or {}).get("still_file")
               for s in shots]))
    check("CF-P1-006-R1-PROVENANCE-every-shot-is-ai-still",
          all((s.get("visual") or {}).get("kind") == "ai-still"
              for s in shots)
          and all((s.get("visual") or {}).get("motion")
                  in pa.STILL_MOTIONS for s in shots),
          str([(s.get("visual") or {}).get("kind") for s in shots]))
    check("CF-P1-006-R1-PROVENANCE-no-ai-video-claim",
          "ai-generated video" not in json.dumps(shots)
          and "AI-generated video" not in json.dumps(
              load_json(os.path.join(EXAMPLE, "project.json"))),
          "a project file claims AI-generated video")
    check("CF-P1-006-R1-PROVENANCE-still-provider-recorded",
          bible["asset_provenance"]["status"]
          == "EXERCISED for stills; image-to-video NOT_TESTED"
          and bible["asset_provenance"]["scene_stills"].startswith(
              "platform-builtin-image"),
          str(bible.get("asset_provenance")))
    check("CF-P1-006-R1-PROVENANCE-six-scenes-five-environments",
          len({s.get("environment_id") for s in shots}) == 5
          and [s.get("environment_id") for s in shots].count(
              "env-forest-path") == 2,
          str([s.get("environment_id") for s in shots])
          + " (s2 walks the forest path; s3 is a close-up in the "
          "same forest — one shared environment by design)")

    # --- voice commercial restriction + dialogue mapping ---
    voice_config = load_json(os.path.join(EXAMPLE, "voice-config.json"))
    check("CF-P1-006-R1-VOICE-non-commercial-only",
          voice_config.get("commercial_use") == "non-commercial-only"
          and voice_config.get("engine") == "omnivoice"
          and voice_config.get("provider")
          == "provider-voicestudio-omnivoice"
          and voice_config.get("seed") == 42,
          str({k: voice_config.get(k) for k in (
              "commercial_use", "engine", "provider", "seed")}))
    script_lines = parse_script_lines(
        os.path.join(EXAMPLE, "script.md"))
    check("CF-P1-006-R1-VOICE-dialogue-mapping-verbatim",
          [(ln.get("line_id"), ln.get("text"))
           for ln in voice_config.get("lines") or []]
          == [(ln.get("line_id"), ln.get("text"))
              for ln in script_lines]
          and len(script_lines) == 6,
          f"{len(script_lines)} script lines vs "
          f"{len(voice_config.get('lines') or [])} voice lines")

    # --- six-scene timeline ---
    voice_durations = {
        ln["line_id"]: float(ln["planned_duration_seconds"])
        for ln in voice_config.get("lines") or []}
    schedule = tl.compute_shot_schedule(
        voice_durations,
        [{"shot_id": s["shot_id"], "line_id": s["line_id"]}
         for s in shots],
        {s["shot_id"]: float(s.get("min_duration_seconds") or 0)
         for s in shots})
    check("CF-P1-006-R1-TIMELINE-six-scenes-30-to-60s",
          len(schedule["shots"]) == 6
          and 30.0 <= schedule["total_seconds"] <= 60.0,
          str(schedule.get("total_seconds")))
    check("CF-P1-006-R1-TIMELINE-scene-order-preserved",
          [s["shot_id"] for s in schedule["shots"]]
          == [s["shot_id"] for s in shots],
          str([s["shot_id"] for s in schedule["shots"]]))
    # Dialogue coverage: a missing scene is an error, never a
    # silent omission.
    check("CF-P1-006-R1-TIMELINE-coverage-full",
          tl.validate_dialogue_coverage(
              voice_config.get("lines") or [], shots) == [],
          str(tl.validate_dialogue_coverage(
              voice_config.get("lines") or [], shots)))
    check("CF-P1-006-R1-TIMELINE-coverage-missing-shot",
          any("l6" in e for e in tl.validate_dialogue_coverage(
              voice_config.get("lines") or [], shots[:5])),
          "a voice line without a shot was not flagged")
    orphan = copy.deepcopy(shots)
    orphan.append({"shot_id": "s7", "scene_id": "SC7"})
    check("CF-P1-006-R1-TIMELINE-coverage-orphan-shot",
          any("s7" in e for e in tl.validate_dialogue_coverage(
              voice_config.get("lines") or [], orphan)),
          "a shot without a voice line was not flagged")
    doubled = copy.deepcopy(shots)
    doubled[1]["line_id"] = "l1"
    check("CF-P1-006-R1-TIMELINE-coverage-double-mapped",
          any("l1" in e for e in tl.validate_dialogue_coverage(
              voice_config.get("lines") or [], doubled)),
          "a line mapped to two shots was not flagged")

    # --- still-clip generation: SHA gate and motion gate ---
    tmpdir = tempfile.mkdtemp(prefix="cf-p1006-r1-still-")
    try:
        still = os.path.join(tmpdir, "still.png")
        make_png(still)
        raw = open(still, "rb").read()
        sha = hashlib.sha256(raw).hexdigest()
        clip = os.path.join(tmpdir, "clip.mp4")
        record = pa.generate_still_clip(
            still_path=still, expected_sha256=sha,
            motion="zoom-in", motion_rate=0.02,
            duration_seconds=2.0, output_path=clip,
            asset_id="vis-s1", project_id=PROJECT_ID, shot_id="s1")
        check("CF-P1-006-R1-STILL-clip-verified",
              record["status"] == "VERIFIED"
              and record["generation"]["method"]
              == "ai-generated-still, locally animated"
              and record["generation"]["still_provider"]
              == "platform-builtin-image",
              str(record.get("generation")))
        probe = pa.probe_media_file(clip)
        check("CF-P1-006-R1-STILL-clip-geometry",
              probe["width"] == 1080 and probe["height"] == 1920
              and abs(probe["frame_rate"] - 30.0) < 0.01
              and abs(probe["duration_seconds"] - 2.0) < 0.15,
              str({k: probe.get(k) for k in (
                  "width", "height", "frame_rate",
                  "duration_seconds")}))
        expect_error("CF-P1-006-R1-STILL-wrong-sha-refused",
                     lambda: pa.generate_still_clip(
                         still_path=still,
                         expected_sha256="0" * 64,
                         motion="zoom-in", motion_rate=0.02,
                         duration_seconds=2.0,
                         output_path=os.path.join(
                             tmpdir, "bad.mp4"),
                         asset_id="vis-s1", project_id=PROJECT_ID,
                         shot_id="s1"),
                     kinds=(pa.AssetError,))
        expect_error("CF-P1-006-R1-STILL-bad-motion-refused",
                     lambda: pa.generate_still_clip(
                         still_path=still, expected_sha256=sha,
                         motion="spin", motion_rate=0.02,
                         duration_seconds=2.0,
                         output_path=os.path.join(
                             tmpdir, "bad2.mp4"),
                         asset_id="vis-s1", project_id=PROJECT_ID,
                         shot_id="s1"),
                     kinds=(pa.AssetError,))
        expect_error("CF-P1-006-R1-STILL-missing-file-refused",
                     lambda: pa.generate_still_clip(
                         still_path=os.path.join(tmpdir, "nope.png"),
                         expected_sha256=sha,
                         motion="zoom-in", motion_rate=0.02,
                         duration_seconds=2.0,
                         output_path=os.path.join(
                             tmpdir, "bad3.mp4"),
                         asset_id="vis-s1", project_id=PROJECT_ID,
                         shot_id="s1"),
                     kinds=(pa.AssetError,))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # --- audio-mix regression: every dialogue line survives ---
    # (CF-WO-P1-006-R1: the ducking sidechain used to starve the
    # final mix after the first voice clip.)
    tmpdir = tempfile.mkdtemp(prefix="cf-p1006-r1-mix-")
    try:
        audio_profile = {
            "id": "test-audio-profile",
            "target_loudness_lufs": -16.0,
            "target_true_peak_dbfs": -1.0,
            "voice_priority": True,
            "music_duck_db": -12.0,
            "fade_in_seconds": 0.5,
            "fade_out_seconds": 1.0,
        }
        voice_paths = {}
        freqs = {"voice-l1": 440.0, "voice-l2": 554.0,
                 "voice-l3": 659.0}
        starts = {"voice-l1": 1.0, "voice-l2": 4.0,
                  "voice-l3": 7.0}
        for asset_id, freq in freqs.items():
            path = os.path.join(tmpdir, f"{asset_id}.wav")
            make_tone_wav(path, seconds=2.0, freq=freq)
            voice_paths[asset_id] = path
        music = os.path.join(tmpdir, "music-bed.wav")
        aud.synthesize_music_bed(10.0, music)
        room = os.path.join(tmpdir, "room-tone.wav")
        aud.synthesize_room_tone(10.0, room)
        mix_timeline = {
            "schema_version": "2.5", "id": "timeline-r1-mix",
            "project_id": PROJECT_ID,
            "format": "editor_neutral_v1",
            "output_profile": {}, "duration_seconds": 10.0,
            "video_tracks": [], "transitions": [],
            "intentional_silences": [],
            "provenance": {},
            "audio_tracks": [
                {"track_id": "voice", "kind": "dialogue", "clips": [
                    {"clip_id": f"clip-{a}", "asset_id": a,
                     "line_id": a[-2:], "shot_id": a[-2:],
                     "timeline_start_seconds": starts[a],
                     "duration_seconds": 2.0}
                    for a in ("voice-l1", "voice-l2", "voice-l3")]},
                {"track_id": "music", "kind": "music", "clips": [
                    {"clip_id": "music-bed", "asset_id": "music-bed",
                     "timeline_start_seconds": 0.0,
                     "duration_seconds": 10.0}]},
                {"track_id": "room-tone", "kind": "room-tone",
                 "clips": [
                    {"clip_id": "room-tone", "asset_id": "room-tone",
                     "timeline_start_seconds": 0.0,
                     "duration_seconds": 10.0}]},
            ],
        }
        asset_paths = dict(voice_paths)
        asset_paths["music-bed"] = music
        asset_paths["room-tone"] = room
        mix_out = os.path.join(tmpdir, "mix.wav")
        record = aud.mix_audio(mix_timeline, asset_paths,
                               audio_profile, mix_out)
        check("CF-P1-006-R1-MIX-record-ok",
              record["duration_seconds"] is not None
              and abs(record["duration_seconds"] - 10.0) < 0.15,
              str(record.get("duration_seconds")))
        for asset_id, start in starts.items():
            rms = rms_in_window(mix_out, start + 0.3, start + 1.7)
            check(f"CF-P1-006-R1-MIX-{asset_id}-audible",
                  rms > 0.05,
                  f"{asset_id} rms {rms:.4f} in its window")
        check("CF-P1-006-R1-MIX-ducking-still-recorded",
              any("sidechaincompress" in op
                  for op in record["operations"]),
              str(record["operations"]))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # --- human approval gate ---
    technical_pass = {"verdict": "pass", "checks": []}
    audio_clean = {"findings": []}
    check("CF-P1-006-R1-GATE-no-approval-blocks",
          qc.qc_decision(technical_pass, audio_clean)[
              "decision"] == "BLOCKED",
          str(qc.qc_decision(technical_pass, audio_clean)))
    check("CF-P1-006-R1-GATE-automated-is-not-approval",
          qc.qc_decision(technical_pass, audio_clean,
                         editorial_approval="automated")[
              "decision"] == "BLOCKED",
          "the string 'automated' was accepted as approval")
    check("CF-P1-006-R1-GATE-named-human-approves",
          qc.qc_decision(technical_pass, audio_clean,
                         editorial_approval="Test Reviewer")[
              "decision"] == "DELIVERY_READY",
          "a named human approval did not open delivery")
    check("CF-P1-006-R1-GATE-failed-technical-blocks",
          qc.qc_decision({"verdict": "fail", "checks": [
              {"check_id": "x", "status": "fail"}]}, audio_clean,
              editorial_approval="Test Reviewer")[
              "decision"] == "BLOCKED",
          "failed technical QC did not block delivery")

    # --- end-to-end fixture render through the R1 driver ---
    tmpdir = tempfile.mkdtemp(prefix="cf-p1006-r1-e2e-")
    try:
        fixture = build_r1_fixture(tmpdir)
        driver = os.path.join(ROOT_ABS, "scripts",
                              "run-p1006-r1-character-render.py")
        proc = subprocess.run(
            [sys.executable, driver,
             "--project-dir", fixture["project_dir"],
             "--work-dir", fixture["work_dir"],
             "--dist-dir", fixture["dist_dir"]],
            capture_output=True, text=True, timeout=900)
        check("CF-P1-006-R1-E2E-driver-exits-zero",
              proc.returncode == 0,
              (proc.stdout or "")[-1500:] + (proc.stderr or "")[-500:])
        if proc.returncode == 0:
            summary = load_json(os.path.join(
                fixture["work_dir"], "render-summary.json"))
            check("CF-P1-006-R1-E2E-final-mp4-facts",
                  summary["width"] == 1080
                  and summary["height"] == 1920
                  and summary["aspect_ratio"] == "9:16"
                  and summary["video_codec"] == "h264"
                  and summary["audio_codec"] == "aac"
                  and 10.0 <= summary["duration_seconds"] <= 60.0
                  and summary["voice_source"] == "synthesized-tone",
                  str({k: summary.get(k) for k in (
                      "width", "height", "duration_seconds",
                      "voice_source")}))
            check("CF-P1-006-R1-E2E-review-package-blocked",
                  summary["qc_status"] == "BLOCKED"
                  and summary["consistency_verdict"] == "consistent",
                  str({k: summary.get(k) for k in (
                      "qc_status", "consistency_verdict")}))
            check("CF-P1-006-R1-E2E-delivery-verifies",
                  pdel.verify_delivery_package(
                      fixture["dist_dir"]) == [],
                  str(pdel.verify_delivery_package(
                      fixture["dist_dir"])))
            dist_files = os.listdir(fixture["dist_dir"])
            for needed in ("final.mp4", "character-reference-sheet.png",
                           "identity-comparison-sheet.png",
                           "contact-sheet.png", "consistency-report.json",
                           "delivery-manifest.json", "SHA256SUMS"):
                check(f"CF-P1-006-R1-E2E-dist-has-{needed}",
                      needed in dist_files, str(dist_files))
            probe = pa.probe_media_file(os.path.join(
                fixture["dist_dir"], "final.mp4"))
            check("CF-P1-006-R1-E2E-final-decodes",
                  probe["duration_seconds"] is not None
                  and probe["width"] == 1080
                  and probe["height"] == 1920,
                  str({k: probe.get(k) for k in (
                      "duration_seconds", "width", "height")}))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    print(f"--- CF-P1-006-R1: {_checks[0]} checks, "
          f"{len(failures)} failures ---")
    if failures:
        print("FAILURES: " + ", ".join(failures))
        return 1
    return 0


def build_r1_fixture(root):
    """Two-shot cut of the R1 project, self-contained.

    Copies the real project files, cuts the script / voice
    config / shot list to two shots (a valid shorter cut: the
    output profile allows 10-60 s), and generates solid-colour
    fixture stills + references with FFmpeg. The bible and the
    stills manifest carry the real SHAs of the fixture files.
    Tone narration (CI mode): no VoiceStudio in CI.
    """
    example = EXAMPLE
    project_dir = os.path.join(root, "project")
    os.makedirs(project_dir, exist_ok=True)
    for name in ("project.json", "sound-plan.json",
                 "assembly-config.json", "character-bible.json"):
        shutil.copy(os.path.join(example, name),
                    os.path.join(project_dir, name))
    # Two-shot cut: s1 + s2 only. The analysis is rewritten
    # minimally (as in the P1-006 e2e cut): the full analysis
    # lists six scenes.
    write_json(os.path.join(project_dir, "production-analysis.json"),
               {"schema_version": "2.5",
                "id": "analysis-p1006-r1-e2e-test",
                "project_id": PROJECT_ID,
                "open_questions": [],
                "character_resolutions": [],
                "notes": "Two-shot end-to-end test cut of the R1 "
                         "project; narrator-only, one fictional "
                         "project-local character."})
    full_shots = load_json(os.path.join(example, "shot-list.json"))
    cut_shots = [s for s in full_shots["shots"]
                 if s["shot_id"] in ("s1", "s2")]
    write_json(os.path.join(project_dir, "shot-list.json"),
               {"shots": cut_shots})
    full_voice = load_json(os.path.join(example, "voice-config.json"))
    cut_voice = copy.deepcopy(full_voice)
    cut_voice["lines"] = [ln for ln in full_voice["lines"]
                          if ln["line_id"] in ("l1", "l2")]
    write_json(os.path.join(project_dir, "voice-config.json"),
               cut_voice)
    sound_plan = load_json(os.path.join(project_dir, "sound-plan.json"))
    sound_plan["cues"] = [c for c in sound_plan.get("cues") or []
                          if c.get("shot_id") == "s2"]
    write_json(os.path.join(project_dir, "sound-plan.json"),
               sound_plan)
    script = ("# Mara and the Compass Garden (test cut)\n\n"
              "Two-shot end-to-end test cut of the R1 project.\n\n"
              "## Narration lines\n\n")
    for line in cut_voice["lines"]:
        script += (f"- **{line['line_id']}** "
                   f"(shot {line['shot_id']}): {line['text']}\n")
    script += ("\n## Timing\n\n- One short pause (0.5 s) follows "
               "each line except the last.\n- 1.0 s of music lead-in "
               "before l1; 1.5 s of music tail-out after l2.\n")
    write_text(os.path.join(project_dir, "script.md"), script)
    # Output profile: the two-shot cut is ~17 s; allow 10-60 s.
    project = load_json(os.path.join(project_dir, "project.json"))
    project["output_profile"]["duration_min_seconds"] = 10
    write_json(os.path.join(project_dir, "project.json"), project)

    work_dir = os.path.join(root, "work")
    refs_dir = os.path.join(work_dir, "references")
    stills_dir = os.path.join(work_dir, "stills")
    os.makedirs(refs_dir, exist_ok=True)
    os.makedirs(stills_dir, exist_ok=True)
    colors = {"front": "0x0F6B6B", "three_quarter": "0x1A7A6B",
              "side": "0x2A8A7B", "full_body": "0x3A9A8B"}
    bible = load_json(os.path.join(project_dir, "character-bible.json"))
    for view, color in colors.items():
        rel = bible["references"][view]["file"]
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        make_png(path, color=color)
        raw = open(path, "rb").read()
        bible["references"][view]["status"] = "generated"
        bible["references"][view]["sha256"] = hashlib.sha256(
            raw).hexdigest()
        bible["references"][view]["size_bytes"] = len(raw)
    expr_rel = bible["references"]["expressions"]["file"]
    expr_path = os.path.join(root, expr_rel)
    make_png(expr_path, color="0x4AAAA0", width=192, height=128)
    raw = open(expr_path, "rb").read()
    bible["references"]["expressions"]["status"] = "generated"
    bible["references"]["expressions"]["sha256"] = hashlib.sha256(
        raw).hexdigest()
    bible["references"]["expressions"]["size_bytes"] = len(raw)
    write_json(os.path.join(project_dir, "character-bible.json"),
               bible)
    manifest = {"project_id": PROJECT_ID, "stills": []}
    for index, shot in enumerate(cut_shots):
        still_file = (shot.get("visual") or {}).get("still_file")
        path = os.path.join(stills_dir, still_file)
        make_png(path, color=f"0x{index + 5}05A6B")
        raw = open(path, "rb").read()
        manifest["stills"].append({
            "shot_id": shot["shot_id"],
            "scene_id": shot.get("scene_id"),
            "file": f"work/stills/{still_file}",
            "size_bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "width": 108, "height": 192,
            "method": "ai-generated-still, locally animated",
            "still_provider": "platform-builtin-image",
            "motion": (shot.get("visual") or {}).get("motion"),
            "motion_rate": (shot.get("visual") or {}).get(
                "motion_rate"),
        })
    write_json(os.path.join(stills_dir, "scene-stills.json"), manifest)
    evaluations = [{
        "scene_id": s.get("scene_id"), "shot_id": s["shot_id"],
        "inspector": "r1-e2e-fixture",
        "checks": {a: "pass" for a in cc.CONSISTENCY_ATTRIBUTES},
        "notes": "fixture evaluation",
    } for s in cut_shots]
    write_json(os.path.join(work_dir, "consistency-evaluation.json"),
               {"character_id": "DEMO-CHAR-001",
                "inspector": "r1-e2e-fixture",
                "method": "fixture evaluation",
                "scene_evaluations": evaluations,
                "prop_continuity_observations": []})
    return {"project_dir": project_dir, "work_dir": work_dir,
            "dist_dir": os.path.join(root, "dist", PROJECT_ID)}


def main():
    return run_checks()


if __name__ == "__main__":
    sys.exit(main())
