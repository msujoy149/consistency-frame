#!/usr/bin/env python3
"""P1-006 reference render driver (CF-WO-P1-006).

Runs the complete vertical production for the example project
``examples/p1006-vertical-explainer`` end to end, locally:

  intake/validate -> visuals (FFmpeg motion graphics) -> voice
  (real VoiceStudio/OmniVoice WAVs from --voice-dir, or
  deterministic tone narration when no voice dir is given)
  -> sound beds (synthesized) -> canonical timeline -> assembly
  (FFmpeg) -> technical / visual / audio QC -> delivery package.

The delivery package is a REVIEW package by default: its
manifest records the true QC decision (BLOCKED while the human
editorial approval is still missing) and never claims
DELIVERY_READY. Pass --editorial-approval "<reviewer name>" with
the name of the human who reviewed the visual QC evidence to
build a final delivery package instead.

Voice source is recorded honestly: "voicestudio-omnivoice" when
--voice-dir supplies real narration, "synthesized-tone" for the
CI render (same pipeline, same geometry and QC, only the voice
source differs — CI has no VoiceStudio model).

Nothing here is mocked: every media file is generated or probed
for real, and any failure stops the run with diagnostics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO)
from runtime import production_assets as pa  # noqa: E402
from runtime import production_audio as aud  # noqa: E402
from runtime import production_delivery as pdel  # noqa: E402
from runtime import production_qc as qc  # noqa: E402
from runtime import production_timeline as tl  # noqa: E402
from runtime import production_voice as pv  # noqa: E402
from runtime import vertical_production as vp  # noqa: E402
from runtime.local_session import (  # noqa: E402
    close_session, load_or_create_profile, start_session)
from runtime.production_store import save_production_checkpoint  # noqa: E402

PROJECT_ID = "p1006-vertical-explainer"
DEFAULT_WORK = os.path.expanduser(
    "~/workspace/consistency-frame-p1-delivery/p1006/work")
DEFAULT_DIST = os.path.expanduser(
    "~/workspace/consistency-frame-p1-delivery/p1006/dist/"
    "p1006-vertical-explainer")
DEFAULT_VOICE_DIR = os.path.join(DEFAULT_WORK, "voice")


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
    pattern = re.compile(
        r"^- \*\*(l[0-9]+)\*\* \(shot (s[0-9]+)\): (.*)$")
    with open(script_path, encoding="utf-8") as handle:
        for raw in handle:
            match = pattern.match(raw.strip())
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
    """Deterministic sine-tone narration stand-in (CI only)."""
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


def register_record(root, asset_id, asset_type, path, mime_type,
                    *, provider="ffmpeg-local",
                    provider_status="EXERCISED", license_class="original",
                    generation=None, shot_id=None):
    """Build a full asset record and verify it against the file.

    ``generation`` is the generation-method record (a dict); the
    record's ``source`` stays the provider object
    ``new_asset_record`` builds — it is never overwritten with a
    plain string.
    """
    record = pa.new_asset_record(
        asset_id=asset_id, project_id=PROJECT_ID, shot_id=shot_id,
        asset_type=asset_type, provider=provider,
        provider_status=provider_status, path=os.path.basename(path),
        mime_type=mime_type, provenance="INFERRED_FOR_PRODUCTION",
        license_class=license_class, generation=generation)
    return pa.verify_asset(record, root)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="P1-006 reference vertical render")
    parser.add_argument("--project-dir", default=os.path.join(
        REPO, "examples", PROJECT_ID))
    parser.add_argument("--voice-dir", default=None,
                        help="directory with real VoiceStudio WAVs "
                        "(outputs/voice-<line_id>.wav); without it, "
                        "deterministic tone narration is synthesized "
                        "(CI render)")
    parser.add_argument("--work-dir", default=DEFAULT_WORK)
    parser.add_argument("--dist-dir", default=DEFAULT_DIST)
    parser.add_argument("--editorial-approval", default=None,
                        help="name of the human reviewer who "
                        "approved the visual QC evidence")
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
    script_lines = parse_script_lines(
        os.path.join(project_dir, "script.md"))

    # Dialogue is preserved verbatim: script.md must agree with
    # the voice config line for line.
    voice_lines = voice_config.get("lines") or []
    if [ (ln.get("line_id"), ln.get("text")) for ln in voice_lines] != [
            (ln.get("line_id"), ln.get("text")) for ln in script_lines]:
        raise vp.VerticalProductionError(
            "script.md lines do not match voice-config.json lines "
            "byte-for-byte: dialogue is preserved verbatim",
            code="validation-failed")

    profile_root = os.path.join(work_dir, "session")
    profile = load_or_create_profile(profile_root)
    session = start_session(profile, profile.workspace_id)
    try:
        project = vp.build_project(
            session, project_config, script_lines, analysis,
            shot_list.get("shots") or [], voice_config, sound_plan,
            assembly_config)
        print(f"project validated: {project['project_id']} "
              f"(state {project['state']})")

        # --- voice durations (intake measurement, read-only) -----
        # Shot durations come from the narration, so the voice
        # files are measured first (probe only — no stage runs
        # yet). The VOICE_PENDING / VOICE_READY stage itself runs
        # after the visuals, in the state machine's order.
        voice_source = ("voicestudio-omnivoice" if args.voice_dir
                        else "synthesized-tone")
        voice_paths = {}
        if args.voice_dir:
            for line in voice_lines:
                line_id = line["line_id"]
                wav = os.path.join(
                    args.voice_dir, "outputs", f"voice-{line_id}.wav")
                if not os.path.isfile(wav):
                    wav = os.path.join(
                        args.voice_dir, f"voice-{line_id}.wav")
                if not os.path.isfile(wav):
                    raise pv.VoiceError(
                        f"real narration line {line_id!r} not found "
                        f"under {args.voice_dir!r}: a missing line "
                        "is an error, never a substitution")
                voice_paths[line_id] = wav
        else:
            for line in voice_lines:
                line_id = line["line_id"]
                duration = float(line.get("planned_duration_seconds")
                                 or 4.0)
                target = os.path.join(
                    assets_dir, f"voice-{line_id}.wav")
                _tone_wav(target, duration)
                voice_paths[line_id] = target
                print(f"tone narration {line_id}: {duration:.3f}s")
        voice_durations = {}
        for line_id, wav in voice_paths.items():
            probe = pa.probe_media_file(wav)
            if probe["duration_seconds"] is None:
                raise pv.VoiceError(
                    f"voice line {line_id!r} has no measurable "
                    "duration")
            voice_durations[line_id] = float(
                probe["duration_seconds"])

        # --- visuals (ASSETS_PENDING -> ASSETS_READY) -------------
        shots = shot_list.get("shots") or []
        min_durations = {s["shot_id"]: float(s.get(
            "min_duration_seconds") or 0) for s in shots}
        schedule = tl.compute_shot_schedule(
            voice_durations,
            [{"shot_id": s["shot_id"], "line_id": s["line_id"]}
             for s in shots],
            min_durations)
        total_seconds = schedule["total_seconds"]
        print(f"schedule: {len(shots)} shots, "
              f"total {total_seconds:.3f}s")
        project = vp.transition_project(
            session, project, "ASSETS_PENDING",
            reason="visual generation starting")
        registry = {}
        for shot in schedule["shots"]:
            shot_id = shot["shot_id"]
            spec = next(s for s in shots
                        if s["shot_id"] == shot_id)
            path = os.path.join(assets_dir, f"vis-{shot_id}.mp4")
            # The keyword and subtext live at the shot level in
            # the shot list; the visual recipe is only the
            # gradient. They must be merged into the recipe here
            # — passing the visual object alone produced
            # textless visuals (no drawtext at all).
            recipe = dict(spec.get("visual") or {})
            recipe.setdefault("keyword", spec.get("keyword") or "")
            recipe.setdefault("subtext", spec.get("subtext") or "")
            record = pa.generate_visual_asset(
                recipe, shot["duration_seconds"],
                path, asset_id=f"vis-{shot_id}", project_id=PROJECT_ID,
                shot_id=shot_id)
            registry[f"vis-{shot_id}"] = record
            print(f"visual {shot_id}: "
                  f"{shot['duration_seconds']:.3f}s, "
                  f"sha {record['sha256'][:16]}...")
        project = vp.transition_project(
            session, project, "ASSETS_READY",
            reason="visual assets generated and verified")

        # --- voice verification (VOICE_PENDING -> VOICE_READY) ----
        project = vp.transition_project(
            session, project, "VOICE_PENDING",
            reason="voice verification starting")
        voice_records = []
        for line in voice_lines:
            line_id = line["line_id"]
            wav = voice_paths[line_id]
            target = os.path.join(assets_dir, f"voice-{line_id}.wav")
            if os.path.abspath(wav) != os.path.abspath(target):
                with open(wav, "rb") as src, \
                        open(target, "wb") as dst:
                    dst.write(src.read())
            if args.voice_dir:
                record = pa.new_asset_record(
                    asset_id=f"voice-{line_id}", project_id=PROJECT_ID,
                    shot_id=line.get("shot_id"), asset_type="audio-voice",
                    provider="provider-voicestudio-omnivoice",
                    provider_status="EXERCISED",
                    path=f"voice-{line_id}.wav", mime_type="audio/wav",
                    provenance="INFERRED_FOR_PRODUCTION",
                    license_class="cc-by-nc")
                record["generation"] = {
                    "method": "voicestudio-omnivoice",
                    "engine": "omnivoice",
                    "commercial_use": "non-commercial-only"}
            else:
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
        print(f"voice verified: {voice_report['lines_checked']} "
              "lines, "
              f"{voice_report['total_duration_seconds']:.2f}s total")
        for record in voice_records:
            registry[record["asset_id"]] = record
        project = vp.transition_project(
            session, project, "VOICE_READY",
            reason="voice assets verified")
        project = vp.stage_checkpoint(
            project, "voice",
            vp.stage_input_hash({"voice": sorted(voice_durations)}),
            {"voice_assets": sorted(voice_durations)})

        # --- sound beds (SOUND_PENDING -> SOUND_READY) ------------
        project = vp.transition_project(
            session, project, "SOUND_PENDING",
            reason="sound bed synthesis starting")
        music_path = os.path.join(assets_dir, "music-bed.wav")
        aud.synthesize_music_bed(total_seconds, music_path)
        registry["music-bed"] = register_record(
            assets_dir, "music-bed", "audio-music", music_path,
            "audio/wav", generation={"method": "synthesized", "tool": "ffmpeg"})
        room_path = os.path.join(assets_dir, "room-tone.wav")
        aud.synthesize_room_tone(total_seconds, room_path)
        registry["room-tone"] = register_record(
            assets_dir, "room-tone", "audio-room-tone", room_path,
            "audio/wav", generation={"method": "synthesized", "tool": "ffmpeg"})
        sfx_path = os.path.join(assets_dir, "sfx-whoosh.wav")
        aud.synthesize_whoosh(0.8, sfx_path)
        registry["sfx-whoosh"] = register_record(
            assets_dir, "sfx-whoosh", "audio-sfx", sfx_path,
            "audio/wav", generation={"method": "synthesized", "tool": "ffmpeg"})
        print("sound beds synthesized and verified")
        project = vp.transition_project(
            session, project, "SOUND_READY",
            reason="sound beds synthesized and verified")

        # --- timeline + assembly ----------------------------------
        timeline = tl.build_canonical_timeline(
            project, registry, voice_durations)
        mix_errors = aud.validate_mix_inputs(
            timeline, registry, project["audio_profile"])
        if mix_errors:
            raise aud.AssetError(["mix inputs:"] + mix_errors)
        project = vp.transition_project(
            session, project, "TIMELINE_READY",
            reason="canonical timeline built")
        project = vp.stage_checkpoint(
            project, "timeline", tl.timeline_hash(timeline),
            {"timeline_id": timeline["id"],
             "duration_seconds": timeline["duration_seconds"]})

        project = vp.transition_project(
            session, project, "ASSEMBLY_RUNNING",
            reason="FFmpeg render starting")
        output_path = os.path.join(work_dir, "final.mp4")
        execution = tl.assemble_timeline(
            session, project, timeline, registry, assets_dir,
            work_dir, output_path)
        print(f"assembled: {output_path} "
              f"({execution['size_bytes']} bytes, "
              f"sha {execution['sha256'][:16]}...)")
        project = vp.transition_project(
            session, project, "ASSEMBLY_COMPLETED",
            reason="FFmpeg render completed")
        project = vp.stage_checkpoint(
            project, "assembly", execution["sha256"],
            {"output_path": output_path,
             "sha256": execution["sha256"]})

        # --- QC ----------------------------------------------------
        project = vp.transition_project(
            session, project, "QC_RUNNING",
            reason="technical / visual / audio QC starting")
        intentional = timeline.get("intentional_silences") or []
        technical = qc.technical_qc(
            output_path, project["output_profile"],
            intentional_silences=intentional)
        visual_dir = os.path.join(work_dir, "qc-visual")
        visual = qc.visual_qc(output_path, timeline, visual_dir)
        audio = qc.audio_qc(
            output_path, timeline, voice_lines,
            project["audio_profile"], assets=list(registry.values()))
        decision = qc.qc_decision(
            technical, audio,
            editorial_approval=args.editorial_approval)
        print(f"QC: technical {technical['verdict']}, "
              f"audio findings "
              f"{len(audio.get('findings') or [])}, "
              f"decision {decision['decision']}")
        if technical["verdict"] != "pass":
            failed = [c.get("check_id") for c in
                      technical.get("checks") or []
                      if c.get("status") == "fail"]
            raise qc.QCError(
                f"technical QC failed: {', '.join(failed)}")
        critical_audio = [f for f in audio.get("findings") or []
                          if f.get("severity") == "critical"]
        if critical_audio:
            raise qc.QCError(
                "audio QC critical findings: "
                + ", ".join(f.get("check", "?")
                            for f in critical_audio))
        project = vp.transition_project(
            session, project, "QC_PASSED",
            reason="technical QC passed, no critical audio findings")

        # --- delivery package --------------------------------------
        render_timestamp = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        voice_mapping = pv.voice_mapping_report(
            [{**line,
              "voice_id": voice_config.get("voice_id"),
              "language": voice_config.get("language"),
              "seed": voice_config.get("seed"),
              "instruct": voice_config.get("instruct")}
             for line in voice_lines],
            voice_records)
        execution_summary = {
            "project_id": PROJECT_ID,
            "timeline_id": timeline["id"],
            "voice_source": voice_source,
            "render_timestamp": render_timestamp,
            "output": {"path": output_path,
                       "size_bytes": execution["size_bytes"],
                       "sha256": execution["sha256"],
                       "probe": execution["probe"]},
            "operations": execution["operations"],
            "steps": execution["steps"],
            "audio_mix": execution["audio_mix"],
            "qc_decision": decision,
            "states": [h.get("state") for h in
                       project.get("history") or []],
        }
        qc_reports = {"decision": decision, "technical": technical,
                      "visual": visual, "audio": audio}
        source_files = {
            "script.md": os.path.join(project_dir, "script.md"),
            "production-analysis.json": os.path.join(
                project_dir, "production-analysis.json"),
            "voice-config.json": os.path.join(
                project_dir, "voice-config.json"),
            "shot-list.json": os.path.join(
                project_dir, "shot-list.json"),
            "sound-plan.json": os.path.join(
                project_dir, "sound-plan.json"),
            "assembly-config.json": os.path.join(
                project_dir, "assembly-config.json"),
        }
        contact_sheet = visual.get("contact_sheet")
        if contact_sheet:
            source_files["contact-sheet.png"] = os.path.join(
                visual_dir, os.path.basename(contact_sheet))
        for keyframe in visual.get("keyframes") or []:
            name = keyframe.get("path")
            if name:
                source_files[name] = os.path.join(
                    visual_dir, os.path.basename(name))
        review_package = args.editorial_approval is None
        manifest = pdel.build_delivery_package(
            project=project, timeline=timeline,
            assets=list(registry.values()),
            voice_mapping=voice_mapping, sound_plan=sound_plan,
            execution_summary=execution_summary,
            qc_reports=qc_reports, source_files=source_files,
            dist_dir=args.dist_dir, final_mp4_path=output_path,
            render_timestamp=render_timestamp,
            voice_source=voice_source, review_package=review_package)
        verify_errors = pdel.verify_delivery_package(args.dist_dir)
        if verify_errors:
            raise pdel.DeliveryError(
                ["delivery verification failed:"] + verify_errors)
        project = vp.transition_project(
            session, project, "DELIVERY_READY",
            reason="review package built"
            if review_package else "delivery package built")
        save_production_checkpoint(
            session, store_root, project,
            checkpoint_id=f"p1006-{PROJECT_ID}")

        result = {
            "project_id": PROJECT_ID,
            "final_mp4": os.path.join(
                args.dist_dir, manifest["filename"]),
            "size_bytes": manifest["size_bytes"],
            "sha256": manifest["sha256"],
            "duration_seconds": manifest["duration_seconds"],
            "width": manifest["width"],
            "height": manifest["height"],
            "aspect_ratio": manifest["aspect_ratio"],
            "frame_rate_rational": manifest["frame_rate_rational"],
            "video_codec": manifest["video_codec"],
            "audio_codec": manifest["audio_codec"],
            "voice_source": voice_source,
            "qc_status": manifest["qc_status"],
            "qc_blocked_reasons": manifest.get("qc_blocked_reasons"),
            "package_purpose": manifest.get("package_purpose"),
            "dist_dir": args.dist_dir,
            "state": project["state"],
        }
        write_json(os.path.join(work_dir, "render-summary.json"),
                   result)
        print(json.dumps(result, indent=2))
        return 0
    finally:
        close_session(session)


if __name__ == "__main__":
    sys.exit(main())
