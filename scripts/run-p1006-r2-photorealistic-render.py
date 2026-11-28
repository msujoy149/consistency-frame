#!/usr/bin/env python3
"""P1-006-R2 photorealistic image-to-video render driver
(CF-WO-P1-006-R2).

Validates the reference project
``examples/p1006-r2-photorealistic-image-to-video`` — script,
character bible, scene bindings, text-overlay policy, voice
config — and builds the image-to-video execution plan for the
script-derived shots.

This driver FAILS CLOSED. The script is a DRAFT awaiting user
approval, no keyframe or reference image has been generated
from it, and no paid image-to-video authorization exists — so
the execution plan is BLOCKED, no provider call is made, no
still animation is substituted, and NO final MP4 is produced.
The run writes ``render-summary.json`` recording BLOCKED with
the exact reasons and exits 2. A final video can only exist
after the user approves the script + breakdown AND explicitly
authorizes the paid provider call; that execution runs through
``runtime.image_to_video.execute_i2v_plan``, never through a
local still-animation fallback.

Tone narration is synthesized only as a pipeline check (the
same pattern as the R1 CI render): deterministic sine tones at
the planned line durations, recorded as
``voice_source: synthesized-tone``. Real VoiceStudio/OmniVoice
narration is generated only after script approval, by the
separate voice script — never here, and never claimed as real
speech.

Honest labels, recorded everywhere they apply: image-to-video
is BLOCKED (no authorized real execution yet); the character
is Nadia (DEMO-CHAR-002), a fictional project-local adult
demonstration identity — never registered in the global
character registry, never a canonical user character; the
voice is a non-commercial VoiceStudio/OmniVoice test voice
(CC-BY-NC) when real narration is eventually generated.

Nothing here is mocked: every validation runs for real, and
any validation failure stops the run with diagnostics.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO)
from runtime import character_consistency as cc  # noqa: E402
from runtime import image_to_video as iv  # noqa: E402
from runtime import production_assets as pa  # noqa: E402
from runtime import production_timeline as tl  # noqa: E402
from runtime import production_voice as pv  # noqa: E402
from runtime import vertical_production as vp  # noqa: E402
from runtime.local_session import (  # noqa: E402
    close_session, load_or_create_profile, start_session)

PROJECT_ID = "p1006-r2-photorealistic-image-to-video"
DEFAULT_WORK = os.path.expanduser(
    "~/workspace/consistency-frame-p1-delivery/p1006-r2/work")
DEFAULT_DIST = os.path.expanduser(
    "~/workspace/consistency-frame-p1-delivery/p1006-r2/dist/"
    "p1006-r2-photorealistic-image-to-video")

# Shot ids are s1, s2, s3a, s3b, s4, s5, s6a, s6b — the trailing
# letter marks the second shot of a two-shot scene. The pattern
# must accept it; a fixed s[0-9] pattern would silently drop
# shots s3a, s3b, s6a and s6b.
SCRIPT_LINE_RE = re.compile(
    r"^- \*\*(l[0-9]+)\*\* \(shot (s[0-9]+[a-z]?)\): (.*)$")


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


def parse_script_lines(script_path):
    """[{line_id, shot_id, text}] from script.md's line list."""
    lines = []
    with open(script_path, encoding="utf-8") as handle:
        for raw in handle:
            match = SCRIPT_LINE_RE.match(raw.strip())
            if match:
                lines.append({"line_id": match.group(1),
                              "shot_id": match.group(2),
                              "text": match.group(3).strip()})
    if not lines:
        raise vp.VerticalProductionError(
            f"no narration lines parsed from {script_path!r}",
            code="validation-failed")
    return lines


def _tone_wav(path, duration, freq=440.0):
    """Deterministic sine-tone narration stand-in (pipeline
    check only — never claimed as real speech)."""
    proc = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
         f"sine=frequency={freq}:duration={duration}:"
         "sample_rate=48000",
         "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le",
         "-t", str(duration), path],
        capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        raise pa.AssetError(
            "tone narration synthesis failed: "
            f"{(proc.stderr or '').strip()[:400]}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="P1-006-R2 photorealistic image-to-video "
        "render (fail-closed: BLOCKED, no final MP4)")
    parser.add_argument("--project-dir", default=os.path.join(
        REPO, "examples", PROJECT_ID))
    parser.add_argument("--work-dir", default=DEFAULT_WORK)
    parser.add_argument("--dist-dir", default=DEFAULT_DIST)
    args = parser.parse_args(argv)

    project_dir = args.project_dir
    work_dir = args.work_dir
    assets_dir = os.path.join(work_dir, "assets")
    store_root = os.path.join(work_dir, "store")
    os.makedirs(assets_dir, exist_ok=True)
    os.makedirs(store_root, exist_ok=True)

    project_config = load_json(
        os.path.join(project_dir, "project.json"))
    analysis = load_json(
        os.path.join(project_dir, "production-analysis.json"))
    shot_list = load_json(os.path.join(project_dir, "shot-list.json"))
    voice_config = load_json(
        os.path.join(project_dir, "voice-config.json"))
    sound_plan = load_json(
        os.path.join(project_dir, "sound-plan.json"))
    assembly_config = load_json(
        os.path.join(project_dir, "assembly-config.json"))
    bible = load_json(
        os.path.join(project_dir, "character-bible.json"))
    appearance_map = load_json(os.path.join(
        project_dir, "character-appearance-map.json"))
    script_lines = parse_script_lines(
        os.path.join(project_dir, "script.md"))

    # Dialogue is preserved verbatim: script.md must agree with
    # the voice config line for line.
    voice_lines = voice_config.get("lines") or []
    if [(ln.get("line_id"), ln.get("text")) for ln in voice_lines] != [
            (ln.get("line_id"), ln.get("text")) for ln in script_lines]:
        raise vp.VerticalProductionError(
            "script.md lines do not match voice-config.json lines "
            "byte-for-byte: dialogue is preserved verbatim",
            code="validation-failed")

    # Dialogue coverage: every line needs exactly one shot and
    # every shot exactly one line. A missing shot is an error,
    # never a silent omission.
    shots = shot_list.get("shots") or []
    coverage_errors = tl.validate_dialogue_coverage(
        voice_lines, shots)
    if coverage_errors:
        raise vp.VerticalProductionError(
            coverage_errors, code="validation-failed")

    # --- text overlay policy: all six flags must be False ------
    policy_errors = iv.validate_text_overlay_policy(
        project_config.get("text_overlay_policy") or {})
    if policy_errors:
        raise iv.ImageToVideoError(
            ["text overlay policy:"] + policy_errors,
            code="validation-failed")

    # --- character bible: validation, isolation, I2V bindings --
    # The bible validator is strict and stays strict: a bible
    # whose reference files are missing is not fully valid. In
    # this round the files are missing because the script is
    # unapproved — that is an expected BLOCKED condition, not a
    # fatal error. Only the missing-file errors are treated as
    # pending; every other bible error still stops the run.
    bible_errors = cc.validate_character_bible(bible)
    pending_file_errors = [
        err for err in bible_errors if ".file is missing" in err]
    fatal_bible_errors = [
        err for err in bible_errors if ".file is missing" not in err]
    if fatal_bible_errors:
        raise cc.CharacterConsistencyError(fatal_bible_errors)
    if pending_file_errors:
        print("character bible: reference files pending "
              "(script approval not given):")
        for err in pending_file_errors:
            print(f"  blocked: {err}")
    character_id = bible["character_id"]
    isolation_errors = cc.check_project_local_isolation(character_id)
    if isolation_errors:
        raise cc.CharacterConsistencyError(isolation_errors)
    binding_errors = []
    for shot in shots:
        binding_errors += cc.validate_scene_binding(
            bible, shot, motion_kind="i2v")
    if binding_errors:
        raise cc.CharacterConsistencyError(binding_errors)
    print(f"character bible validated: {character_id} "
          "(project-local, never registered)")
    print(f"scene bindings validated: {len(shots)} shots, "
          "motion kind i2v")

    # References and keyframes are PENDING (script unapproved):
    # verify_reference_assets is not run — there is no real file
    # to verify yet. Their pending status is recorded in the
    # keyframes manifest and in the render summary instead.
    pending_references = [
        {"view": view, "asset_id": entry.get("asset_id"),
         "status": entry.get("status")}
        for view, entry in (bible.get("references") or {}).items()]
    pending_keyframes = [
        {"shot_id": shot.get("shot_id"),
         "scene_id": shot.get("scene_id"),
         "status": (shot.get("keyframe") or {}).get("status"),
         "width": (shot.get("keyframe") or {}).get("width"),
         "height": (shot.get("keyframe") or {}).get("height")}
        for shot in shots]
    keyframes_manifest = {
        "project_id": PROJECT_ID,
        "character_id": character_id,
        "status": "pending-generation-after-script-approval",
        "note": "No keyframe has been generated from the script: "
                "the script + breakdown await user approval.",
        "references": pending_references,
        "keyframes": pending_keyframes,
    }
    write_json(os.path.join(
        work_dir, "keyframes", "scene-keyframes.json"),
        keyframes_manifest)

    profile_root = os.path.join(work_dir, "session")
    profile = load_or_create_profile(profile_root)
    session = start_session(profile, profile.workspace_id)
    try:
        project = vp.build_project(
            session, project_config, script_lines, analysis,
            shots, voice_config, sound_plan, assembly_config)
        print(f"project validated: {project['project_id']} "
              f"(state {project['state']})")

        # --- tone narration: pipeline check only -----------------
        voice_source = "synthesized-tone"
        voice_durations = {}
        voice_records = []
        for line in voice_lines:
            line_id = line["line_id"]
            duration = float(line.get("planned_duration_seconds")
                             or 4.0)
            target = os.path.join(assets_dir, f"voice-{line_id}.wav")
            _tone_wav(target, duration)
            probe = pa.probe_media_file(target)
            if probe["duration_seconds"] is None:
                raise pv.VoiceError(
                    f"voice line {line_id!r} has no measurable "
                    "duration")
            voice_durations[line_id] = float(
                probe["duration_seconds"])
            record = pa.new_asset_record(
                asset_id=f"voice-{line_id}", project_id=PROJECT_ID,
                shot_id=line.get("shot_id"), asset_type="audio-voice",
                provider="ffmpeg-local",
                provider_status="EXERCISED",
                path=f"voice-{line_id}.wav", mime_type="audio/wav",
                provenance="INFERRED_FOR_PRODUCTION",
                license_class="original")
            record["generation"] = {
                "method": "synthesized-tone", "tool": "ffmpeg"}
            voice_records.append(pa.verify_asset(record, assets_dir))
        errors, voice_report = pv.verify_voice_assets(
            voice_lines, voice_records, assets_dir)
        if errors:
            raise pv.VoiceError(errors)
        print(f"voice pipeline check: "
              f"{voice_report['lines_checked']} tone lines, "
              f"{voice_report['total_duration_seconds']:.2f}s total "
              "(synthesized-tone, not real speech)")

        # --- image-to-video execution plan: FAIL CLOSED ----------
        # No authorization record exists in this round, the script
        # is a DRAFT, and every keyframe is pending — the plan is
        # BLOCKED. Nothing is submitted, nothing is substituted,
        # and no final MP4 is assembled.
        # PREFLIGHT (CF-WO-P1-006-R2-PREFLIGHT): this round sets
        # generate_audio=False for every shot — external narration
        # is handled separately by the existing voice pipeline, so
        # the provider must not generate unintended audio. Nadia
        # (DEMO-CHAR-002) appears in every shot, so every shot
        # uses elements and the plan cost uses the audio-off
        # WITH-ELEMENTS rate ($0.224/s): 48 s x $0.224/s =
        # $10.75, not the without-elements $0.112/s rate.
        # The references below are pending (no files exist), but
        # the shots are keyframe-pending so elements are never
        # built in this driver path — only elements-presence
        # drives the per-shot cost.
        characters = appearance_map.get("characters") or []
        nadia = characters[0] if characters else {}
        ref_plan = nadia.get("reference_plan") or {}
        frontal_id = (ref_plan.get("front") or {}).get(
            "asset_id") or "ref-nadia-front"
        angle_id = (ref_plan.get("three_quarter") or {}).get(
            "asset_id") or "ref-nadia-three-quarter"
        pending_status = ("pending-generation-after-"
                          "script-approval")
        identity_bindings = {}
        for appearance in appearance_map.get("appearances") or []:
            if not appearance.get("present"):
                continue
            identity_bindings[appearance.get("shot_id")] = [{
                "character_id": appearance.get("character_id")
                or nadia.get("character_id"),
                "frontal": {"asset_id": frontal_id,
                            "status": pending_status},
                "additional": [{"asset_id": angle_id,
                                "status": pending_status}],
            }]
        plan = iv.build_execution_plan(
            {**project_config,
             "voice_lines": voice_lines},
            shots, authorization=None, generate_audio=False,
            identity_bindings=identity_bindings)
        counts = iv.derive_project_counts(
            project_config, shots, voice_lines)
        print(f"execution plan: {plan['status']}")
        for reason in plan["blocked_reasons"]:
            print(f"  blocked: {reason}")

        result = {
            "project_id": PROJECT_ID,
            "character_id": character_id,
            "script_title": "Nadia and the River Light",
            "script_status": project_config.get("script_status"),
            "counts": counts,
            "provider_id": iv.PROVIDER_ID,
            "model": iv.MODEL_ID,
            "operation": iv.OPERATION,
            "generate_audio": False,
            "plan_status": plan["status"],
            "blocked_reasons": plan["blocked_reasons"],
            "estimated_cost_usd": plan["estimated_cost_usd"],
            "rate_usd_per_second": plan["rate_usd_per_second"],
            "rate_source": plan["rate_source"],
            "voice_source": voice_source,
            "voice_lines_checked": voice_report["lines_checked"],
            "voice_total_duration_seconds": round(
                voice_report["total_duration_seconds"], 3),
            "pending_references": pending_references,
            "pending_keyframes": pending_keyframes,
            "final_mp4": None,
            "qc_status": "BLOCKED",
            "qc_blocked_reasons": plan["blocked_reasons"],
            "package_purpose": "review",
            "dist_dir": args.dist_dir,
            "state": project["state"],
        }
        write_json(os.path.join(work_dir, "render-summary.json"),
                   result)
        print(json.dumps(result, indent=2))
        # BLOCKED is the honest outcome of this round: exit 2 so
        # no caller mistakes it for a completed render.
        return 2
    finally:
        close_session(session)


if __name__ == "__main__":
    sys.exit(main())
