#!/usr/bin/env python3
"""P1-006 end-to-end test (CF-WO-P1-006, Phase H).

One complete reproducible job, intake -> QC -> delivery,
through the real reference-render driver, producing an ACTUAL
playable video — no mocked media anywhere. The fixture is a
two-shot cut of the reference project (its own valid output
profile: 10–60 s, so the short cut passes QC honestly), run in
the CI tone-narration mode (no VoiceStudio in CI). The full
six-shot reference render with real narration is exercised by
the driver itself and the CI execution job.
"""

import json
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
from runtime import production_delivery as pdel  # noqa: E402

failures = []
_checks = [0]


def check(name, cond, detail=""):
    _checks[0] += 1
    if cond:
        print(f"PASS {name}")
    else:
        print(f"FAIL {name} {detail}")
        failures.append(name)


def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, payload):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def write_text(path, text):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def build_fixture(root):
    """Two-shot cut of the reference project (valid, self-contained)."""
    example = os.path.join(ROOT_ABS, "examples",
                           "p1006-vertical-explainer")
    fixture = os.path.join(root, "project")
    os.makedirs(fixture)
    project = load_json(os.path.join(example, "project.json"))
    project["project_id"] = "p1006-e2e-test"
    project["title"] = "P1-006 end-to-end test cut"
    project["output_profile"] = dict(project["output_profile"])
    project["output_profile"]["duration_min_seconds"] = 10
    write_json(os.path.join(fixture, "project.json"), project)
    write_json(os.path.join(fixture, "production-analysis.json"), {
        "schema_version": "2.5",
        "id": "analysis-p1006-e2e-test",
        "project_id": "p1006-e2e-test",
        "open_questions": [],
        "character_resolutions": [],
        "notes": "Two-shot end-to-end test cut of the reference "
                 "project; narrator-only, no characters.",
    })
    voice_config = load_json(os.path.join(example, "voice-config.json"))
    voice_config["project_id"] = "p1006-e2e-test"
    voice_config["lines"] = voice_config["lines"][:2]
    write_json(os.path.join(fixture, "voice-config.json"), voice_config)
    shot_list = load_json(os.path.join(example, "shot-list.json"))
    shot_list["project_id"] = "p1006-e2e-test"
    shot_list["shots"] = shot_list["shots"][:2]
    write_json(os.path.join(fixture, "shot-list.json"), shot_list)
    sound_plan = load_json(os.path.join(example, "sound-plan.json"))
    sound_plan["project_id"] = "p1006-e2e-test"
    sound_plan["cues"] = [c for c in sound_plan.get("cues") or []
                          if c.get("shot_id") == "s2"]
    write_json(os.path.join(fixture, "sound-plan.json"), sound_plan)
    shutil.copyfile(os.path.join(example, "assembly-config.json"),
                    os.path.join(fixture, "assembly-config.json"))
    lines = voice_config["lines"]
    script = ("# P1-006 end-to-end test cut\n\n"
              "Original explainer script for the P1-006 end-to-end "
              "test. Narrator-only.\n\n## Narration lines\n\n")
    for line in lines:
        script += (f"- **{line['line_id']}** "
                   f"(shot {line['shot_id']}): {line['text']}\n")
    script += ("\n## Timing\n\n- One short pause (0.5 s) follows "
               "each line except the last.\n- 1.0 s of music lead-in "
               "before l1; 1.5 s of music tail-out after l6.\n")
    write_text(os.path.join(fixture, "script.md"), script)
    return fixture


def main():
    root = tempfile.mkdtemp(prefix="cf-p1006-e2e-")
    try:
        fixture = build_fixture(root)
        work_dir = os.path.join(root, "work")
        dist_dir = os.path.join(root, "dist")
        driver = os.path.join(ROOT_ABS, "scripts",
                              "run-p1006-reference-render.py")
        proc = subprocess.run(
            [sys.executable, driver, "--project-dir", fixture,
             "--work-dir", work_dir, "--dist-dir", dist_dir],
            capture_output=True, text=True, timeout=900)
        check("e2e-driver-exit-0", proc.returncode == 0,
              f"exit {proc.returncode}: "
              f"{(proc.stderr or proc.stdout or '')[-800:]}")
        if proc.returncode != 0:
            print(f"CF-P1-006-E2E: {_checks[0]} checks, "
                  f"{len(failures)} failures")
            print("FAILURES:", failures)
            return 1
        summary = load_json(os.path.join(work_dir,
                                         "render-summary.json"))
        mp4 = summary["final_mp4"]
        check("e2e-mp4-exists",
              os.path.isfile(mp4) and summary["size_bytes"] > 0)
        probe = pa.probe_media_file(mp4)
        check("e2e-mp4-geometry",
              probe["width"] == 1080 and probe["height"] == 1920)
        check("e2e-mp4-fps",
              probe["frame_rate_rational"] == "30/1")
        check("e2e-mp4-codecs",
              probe["video_codec"] == "h264"
              and probe["audio_codec"] == "aac")
        check("e2e-mp4-duration",
              probe["duration_seconds"] is not None
              and 10.0 <= probe["duration_seconds"] <= 60.0,
              f"got {probe['duration_seconds']}")
        check("e2e-mp4-sha",
              summary["sha256"] == pa.hash_file(mp4)[0])
        # The shot-1 keyword must actually be visible in the
        # assembled video, not just in the visual unit test: the
        # driver once passed the shot's visual object (which has
        # no keyword) to the generator, so the whole render came
        # out textless while every unit test passed.
        timeline = load_json(os.path.join(
            dist_dir, "timeline-manifest.json"))
        video_track = (timeline.get("video_tracks") or [{}])[0]
        first_shot = (video_track.get("clips") or [{}])[0]
        start = float(first_shot.get("timeline_start_seconds") or 0)
        duration = float(first_shot.get("duration_seconds") or 0)
        mid = start + duration / 2.0
        proc = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", str(mid), "-i", mp4,
             "-vf", "crop=1080:300:0:810,format=gray",
             "-frames:v", "1", "-f", "rawvideo", "-"],
            capture_output=True, timeout=120)
        bright = max(proc.stdout) if proc.stdout else 0
        check("e2e-keyword-visible", bright >= 240,
              f"brightest centre-band pixel {bright} at {mid:.2f}s, "
              "expected >= 240")
        check("e2e-voice-source-tone",
              summary["voice_source"] == "synthesized-tone")
        manifest = load_json(os.path.join(
            dist_dir, "delivery-manifest.json"))
        check("e2e-manifest-review-package",
              manifest["qc_status"] == "BLOCKED"
              and manifest["package_purpose"] == "review"
              and any("editorial approval" in r for r in
                      manifest.get("qc_blocked_reasons") or []),
              str({k: manifest.get(k) for k in
                   ("qc_status", "package_purpose",
                    "qc_blocked_reasons")}))
        check("e2e-manifest-mp4",
              manifest["sha256"] == summary["sha256"]
              and manifest["size_bytes"] == summary["size_bytes"]
              and manifest["filename"] == os.path.basename(mp4))
        check("e2e-package-verifies",
              pdel.verify_delivery_package(dist_dir) == [],
              str(pdel.verify_delivery_package(dist_dir)))
        technical = load_json(os.path.join(
            dist_dir, "technical-qc-report.json"))
        check("e2e-technical-qc-pass",
              technical.get("verdict") == "pass",
              str(technical.get("verdict")))
        audio = load_json(os.path.join(
            dist_dir, "audio-qc-report.json"))
        check("e2e-audio-qc-no-critical",
              not any(f.get("severity") == "critical"
                      for f in audio.get("findings") or []),
              str(audio.get("findings")))
        check("e2e-state-delivery-ready",
              summary["state"] == "DELIVERY_READY")
        expected = {"project.json", "timeline-manifest.json",
                    "asset-manifest.json", "voice-mapping.json",
                    "sound-plan.json", "execution-summary.json",
                    "technical-qc-report.json", "visual-qc-report.json",
                    "audio-qc-report.json", "delivery-manifest.json",
                    "SHA256SUMS", "script.md",
                    "production-analysis.json", "voice-config.json",
                    "shot-list.json", "assembly-config.json",
                    "contact-sheet.png"}
        actual = {entry["path"] for entry in
                  pdel._collect_files(dist_dir)}
        check("e2e-package-file-set",
              expected <= actual,
              f"missing={expected - actual}")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print(f"CF-P1-006-E2E: {_checks[0]} checks, "
          f"{len(failures)} failures")
    if failures:
        print("FAILURES:", failures)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
