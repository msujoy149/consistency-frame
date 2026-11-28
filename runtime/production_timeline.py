"""Consistency Frame P1 — canonical timeline and assembly runtime (CF-WO-P1-006, Phase E).

One canonical timeline representation connects the production
task packets and the approved media artifacts. There is no second
source of truth: the timeline manifest IS the edit, and the
assembler renders exactly what it describes.

Timeline geometry (all explicit, all recorded — nothing is
stretched, cropped, rotated, or re-timed silently):

- Every shot clip is generated at the output geometry already
  (1080x1920, 30 FPS); a clip whose probe disagrees with the
  output profile is refused before assembly.
- Voice line ``i`` starts 1.0 s into its shot (``LEAD_IN_SECONDS``,
  the music lead-in). The gap between consecutive voice lines is
  ``PAUSE_AFTER_SECONDS`` (0.5 s). Each shot's duration is
  ``voice duration + pause + transition overlap``, so the voice
  timing and the visual timing agree by construction.
- Shot boundaries use a 0.3 s dip-to-black (``TRANSITION_SECONDS``)
  implemented as an FFmpeg ``xfade``; the overlap is subtracted
  from the total exactly once per boundary.
- The last shot holds ``TAIL_OUT_SECONDS`` (1.5 s) of music after
  the final voice line ends, under the end card.
- The music bed and room tone span the full timeline; SFX cues
  sit at the shot boundaries.

The single final rendering path is FFmpeg. OpenMontage
production assembly is NOT_TESTED and is not used here; the
earlier OpenMontage demo (a 20 s animated reel) proves nothing
about production assembly and is never cited as proof. The
assembler validates every source asset, resolves every path,
verifies every hash, validates durations and trims and the output
profile, rejects invalid overlaps, handles gaps and transitions,
synchronizes voice and SFX, assembles in deterministic order,
renders, and produces an execution record. A failed render is
recorded as failed with diagnostics — never marked delivered.
"""

from __future__ import annotations

import copy
import hashlib
import os
import subprocess

from . import production_assets as assets_mod
from .media_execution import is_safe_relative_path
from .task_compiler import canonical_json, sha256_hex
from .timeline_delivery import (
    aspect_ratio_for_dimensions,
    geometry_from_probe,
    validate_output_geometry,
)

TIMELINE_SCHEMA_VERSION = "2.5"

# Named timing constants for the reference edit. They are inputs
# to the schedule arithmetic, never hidden magic numbers.
LEAD_IN_SECONDS = 1.0
PAUSE_AFTER_SECONDS = 0.5
TAIL_OUT_SECONDS = 1.5
TRANSITION_SECONDS = 0.3


class TimelineError(ValueError):
    """Timeline error carrying a list of structured messages."""

    def __init__(self, errors):
        if isinstance(errors, str):
            errors = [errors]
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


def timeline_hash(timeline) -> str:
    """Deterministic hash of a canonical timeline."""
    return sha256_hex(canonical_json(timeline))


def validate_dialogue_coverage(voice_lines, shots) -> list:
    """Dialogue coverage errors (empty list = fully covered).

    Every voice line must map to exactly one shot, and every
    shot must carry exactly one voice line: a line with no shot
    would be narration without a scene, and a shot with no line
    would be a scene without narration. A missing scene is an
    error here, never a silent omission.
    """
    errors: list[str] = []
    line_ids = [ln.get("line_id") for ln in (voice_lines or [])
                if isinstance(ln, dict)]
    shot_lines: list[str] = []
    for shot in (shots or []):
        if not isinstance(shot, dict):
            errors.append("dialogue coverage: shot is not an object")
            continue
        line_id = shot.get("line_id")
        if not line_id:
            errors.append(
                f"dialogue coverage: shot {shot.get('shot_id')!r} "
                "carries no voice line")
        shot_lines.append(line_id)
    for line_id in line_ids:
        if line_id not in shot_lines:
            errors.append(
                f"dialogue coverage: voice line {line_id!r} has no "
                "shot")
    for line_id in set(shot_lines):
        if line_id is not None and shot_lines.count(line_id) > 1:
            errors.append(
                f"dialogue coverage: voice line {line_id!r} maps to "
                f"{shot_lines.count(line_id)} shots")
    return errors


def compute_shot_schedule(voice_durations, shots,
                          min_durations, *, pause_after=PAUSE_AFTER_SECONDS,
                          lead_in=LEAD_IN_SECONDS,
                          tail_out=TAIL_OUT_SECONDS,
                          transition=TRANSITION_SECONDS) -> dict:
    """Shot schedule arithmetic for the reference edit.

    ``voice_durations`` maps line ids to measured narration
    seconds; ``shots`` is the shot order as ``[{shot_id,
    line_id}]``; ``min_durations`` maps shot ids to minimum shot
    lengths. Returns ``{shots: [{shot_id, line_id,
    voice_duration_seconds, duration_seconds,
    timeline_start_seconds, voice_start_seconds}],
    total_seconds}``.

    Every shot (except the last) lasts ``voice + pause +
    transition``; the last lasts ``voice + lead_in + tail_out``.
    The voice for a shot starts ``lead_in`` seconds into the shot.
    Transitions overlap ``transition`` seconds, so the total is
    the sum of shot durations minus one overlap per boundary.
    """
    errors: list[str] = []
    if not isinstance(voice_durations, dict) or not voice_durations:
        errors.append("voice_durations must be a non-empty mapping")
    if not isinstance(shots, list) or not shots:
        errors.append("shots must be a non-empty list")
    if errors:
        raise TimelineError(errors)
    ordered = []
    for shot in shots:
        shot_id = shot.get("shot_id")
        line_id = shot.get("line_id")
        duration = voice_durations.get(line_id)
        if duration is None:
            raise TimelineError(
                f"no measured voice duration for shot {shot_id!r} "
                f"(line {line_id!r})")
        if not isinstance(duration, (int, float)) or float(duration) <= 0:
            raise TimelineError(
                f"voice duration for shot {shot_id!r} must be a "
                f"positive number, got {duration!r}")
        minimum = (min_durations or {}).get(shot_id) or 0.0
        if shot_id == shots[-1].get("shot_id"):
            shot_duration = float(duration) + lead_in + tail_out
        else:
            shot_duration = float(duration) + pause_after + transition
        shot_duration = max(shot_duration, float(minimum))
        ordered.append({"shot_id": shot_id, "line_id": line_id,
                        "voice_duration_seconds": float(duration),
                        "duration_seconds": shot_duration})
    total = sum(s["duration_seconds"] for s in ordered) \
        - transition * (len(ordered) - 1)
    start = 0.0
    for shot in ordered:
        shot["timeline_start_seconds"] = round(start, 3)
        shot["voice_start_seconds"] = round(start + lead_in, 3)
        shot["duration_seconds"] = round(shot["duration_seconds"], 3)
        start += shot["duration_seconds"] - transition
    return {"shots": ordered, "total_seconds": round(total, 3)}


def build_canonical_timeline(project, asset_registry,
                             voice_durations, *, timeline_id=None) -> dict:
    """Build the canonical timeline for a validated project.

    ``asset_registry`` maps asset ids to verified asset records
    (visual clips ``vis-<shot>``, voice ``voice-<line>``, music
    ``music-bed``, room tone ``room-tone``, SFX ``sfx-whoosh``).
    ``voice_durations`` maps line ids to measured seconds.
    The timeline carries the project profile, durations, frame
    rate, dimensions, video/audio tracks, shot/scene ids, clip
    references, in/out points, positions, transitions, gains,
    fades, layer order, asset ids, identity references (the
    narrator binding) and provenance. Raises
    :class:`TimelineError` on any inconsistency.
    """
    errors: list[str] = []
    if not isinstance(project, dict):
        raise TimelineError("project: expected an object")
    if not isinstance(asset_registry, dict):
        raise TimelineError("asset_registry: expected an object")
    profile = project.get("output_profile") or {}
    errors.extend(validate_output_geometry({
        "aspect_ratio": profile.get("aspect_ratio"),
        "width": profile.get("width"),
        "height": profile.get("height"),
        "frame_rate": profile.get("frame_rate")}))
    if errors:
        raise TimelineError(errors)
    shots = project.get("shots") or []
    shot_order = [{"shot_id": s.get("shot_id"),
                   "line_id": s.get("line_id")} for s in shots]
    min_durations = {s.get("shot_id"): s.get("min_duration_seconds")
                     for s in shots}
    schedule = compute_shot_schedule(
        voice_durations, shot_order, min_durations)
    # Every visual asset must exist and cover its shot.
    for shot in schedule["shots"]:
        asset_id = f"vis-{shot['shot_id']}"
        record = asset_registry.get(asset_id)
        if record is None:
            errors.append(f"timeline: visual asset {asset_id!r} for "
                          f"shot {shot['shot_id']!r} is not registered")
            continue
        if record.get("status") != "VERIFIED":
            errors.append(f"timeline: visual asset {asset_id!r} is "
                          f"not VERIFIED (status "
                          f"{record.get('status')!r})")
        duration = record.get("duration_seconds")
        if duration is not None \
                and duration + 0.05 < shot["duration_seconds"]:
            errors.append(f"timeline: visual asset {asset_id!r} "
                          f"({duration}s) is shorter than its shot "
                          f"({shot['duration_seconds']}s)")
        if record.get("width") != profile.get("width") \
                or record.get("height") != profile.get("height"):
            errors.append(f"timeline: visual asset {asset_id!r} "
                          "geometry does not match the output "
                          "profile")
    for line_id in voice_durations:
        asset_id = f"voice-{line_id}"
        record = asset_registry.get(asset_id)
        if record is None:
            errors.append(f"timeline: voice asset {asset_id!r} is "
                          "not registered")
        elif record.get("status") != "VERIFIED":
            errors.append(f"timeline: voice asset {asset_id!r} is "
                          "not VERIFIED")
    for asset_id in ("music-bed", "room-tone", "sfx-whoosh"):
        record = asset_registry.get(asset_id)
        if record is None:
            errors.append(f"timeline: audio asset {asset_id!r} is "
                          "not registered")
        elif record.get("status") != "VERIFIED":
            errors.append(f"timeline: audio asset {asset_id!r} is "
                          "not VERIFIED")
    if errors:
        raise TimelineError(errors)
    total = schedule["total_seconds"]
    video_clips = []
    for shot in schedule["shots"]:
        video_clips.append({
            "clip_id": f"clip-{shot['shot_id']}",
            "asset_id": f"vis-{shot['shot_id']}",
            "shot_id": shot["shot_id"],
            "source_start_seconds": 0.0,
            "source_end_seconds": shot["duration_seconds"],
            "timeline_start_seconds": shot["timeline_start_seconds"],
            "duration_seconds": shot["duration_seconds"],
            "operations": [{
                "op": "generated",
                "tool": "ffmpeg",
                "detail": "clip generated at the output geometry; "
                          "no scale, crop, or rotation applied"}],
        })
    voice_clips = []
    for shot in schedule["shots"]:
        voice_clips.append({
            "clip_id": f"clip-voice-{shot['line_id']}",
            "asset_id": f"voice-{shot['line_id']}",
            "line_id": shot["line_id"],
            "shot_id": shot["shot_id"],
            "timeline_start_seconds": shot["voice_start_seconds"],
            "duration_seconds": shot["voice_duration_seconds"],
        })
    sfx_clips = []
    for shot in schedule["shots"][1:]:
        sfx_clips.append({
            "clip_id": f"clip-sfx-{shot['shot_id']}",
            "asset_id": "sfx-whoosh",
            "cue_id": f"sfx-whoosh-{shot['shot_id']}",
            "shot_id": shot["shot_id"],
            "timeline_start_seconds": shot["timeline_start_seconds"],
            "duration_seconds": 0.8,
        })
    transitions = []
    for index in range(len(schedule["shots"]) - 1):
        transitions.append({
            "transition_id": f"tr-{schedule['shots'][index]['shot_id']}-"
                             f"{schedule['shots'][index + 1]['shot_id']}",
            "from_clip_id": f"clip-{schedule['shots'][index]['shot_id']}",
            "to_clip_id":
                f"clip-{schedule['shots'][index + 1]['shot_id']}",
            "type": "fadeblack",
            "duration_seconds": TRANSITION_SECONDS,
        })
    timeline = {
        "schema_version": TIMELINE_SCHEMA_VERSION,
        "id": timeline_id or f"timeline-{project.get('project_id')}",
        "project_id": project.get("project_id"),
        "format": "editor_neutral_v1",
        "output_profile": copy.deepcopy(profile),
        "duration_seconds": total,
        "video_tracks": [{"track_id": "v1", "clips": video_clips}],
        "audio_tracks": [
            {"track_id": "voice", "kind": "dialogue",
             "clips": voice_clips},
            {"track_id": "music", "kind": "music",
             "clips": [{"clip_id": "clip-music-bed",
                        "asset_id": "music-bed",
                        "timeline_start_seconds": 0.0,
                        "duration_seconds": total}]},
            {"track_id": "room-tone", "kind": "room-tone",
             "clips": [{"clip_id": "clip-room-tone",
                        "asset_id": "room-tone",
                        "timeline_start_seconds": 0.0,
                        "duration_seconds": total}]},
            {"track_id": "sfx", "kind": "sfx", "clips": sfx_clips},
        ],
        "transitions": transitions,
        "intentional_silences": [{
            "silence_id": "tail-out",
            "timeline_start_seconds": round(
                total - TAIL_OUT_SECONDS, 3),
            "duration_seconds": TAIL_OUT_SECONDS,
            "reason": "Music tail-out under the end card; not a "
                      "defect.",
        }],
        "provenance": copy.deepcopy(project.get("provenance") or {}),
        "narrator": copy.deepcopy(project.get("narrator") or {}),
    }
    return timeline


def validate_canonical_timeline(timeline, asset_registry,
                                project=None) -> list:
    """Canonical-timeline errors (empty list = valid).

    Every clip resolves to a registered, VERIFIED asset; trims
    are inside the source duration; video clips tile exactly
    with the declared transitions (no gaps, no undeclared
    overlaps); audio clips never overlap inside one track; every
    video asset matches the output geometry; the clip durations
    sum to the timeline duration. Pure validation — no I/O.
    """
    errors: list[str] = []
    if not isinstance(timeline, dict):
        return ["timeline: expected an object, "
                f"got {type(timeline).__name__}"]
    if timeline.get("schema_version") != TIMELINE_SCHEMA_VERSION:
        errors.append("timeline.schema_version must be "
                      f"'{TIMELINE_SCHEMA_VERSION}', got "
                      f"{timeline.get('schema_version')!r}")
    if timeline.get("format") != "editor_neutral_v1":
        errors.append("timeline.format must be 'editor_neutral_v1', "
                      f"got {timeline.get('format')!r}")
    profile = timeline.get("output_profile") or {}
    errors.extend(validate_output_geometry({
        "aspect_ratio": profile.get("aspect_ratio"),
        "width": profile.get("width"),
        "height": profile.get("height"),
        "frame_rate": profile.get("frame_rate")}))
    if not isinstance(asset_registry, dict):
        return errors + ["asset_registry: expected an object"]
    total = timeline.get("duration_seconds")
    if not isinstance(total, (int, float)) or float(total) <= 0:
        errors.append("timeline.duration_seconds must be a positive "
                      f"number, got {total!r}")
        return errors
    # Video track: tiling with transitions.
    video_tracks = timeline.get("video_tracks") or []
    if len(video_tracks) != 1:
        errors.append("timeline must carry exactly one video track "
                      "in this round")
    else:
        clips = (video_tracks[0] or {}).get("clips") or []
        if not clips:
            errors.append("video track carries no clips")
        cursor = 0.0
        transitions = {t.get("from_clip_id"): t
                       for t in timeline.get("transitions") or []}
        for index, clip in enumerate(clips):
            where = f"video clip {clip.get('clip_id')!r}"
            asset_id = clip.get("asset_id")
            try:
                record = assets_mod.resolve_asset(asset_registry,
                                                  asset_id)
            except assets_mod.AssetError as exc:
                errors.append(f"{where}: {exc.errors[0]}")
                continue
            if record.get("status") != "VERIFIED":
                errors.append(f"{where}: asset {asset_id!r} is not "
                              "VERIFIED")
            if record.get("width") != profile.get("width") \
                    or record.get("height") != profile.get("height"):
                errors.append(f"{where}: asset {asset_id!r} geometry "
                              "does not match the output profile")
            start = clip.get("timeline_start_seconds")
            duration = clip.get("duration_seconds")
            if not isinstance(start, (int, float)) \
                    or not isinstance(duration, (int, float)):
                errors.append(f"{where}: start/duration must be "
                              "numbers")
                continue
            if abs(float(start) - cursor) > 0.05:
                errors.append(f"{where}: starts at {start}s, expected "
                              f"{cursor:.3f}s — video clips must tile "
                              "exactly with the declared transitions")
            src_start = clip.get("source_start_seconds")
            src_end = clip.get("source_end_seconds")
            asset_duration = record.get("duration_seconds")
            if isinstance(src_start, (int, float)) \
                    and isinstance(src_end, (int, float)):
                if float(src_start) < 0 or float(src_end) <= float(src_start):
                    errors.append(f"{where}: invalid trim "
                                  f"[{src_start}, {src_end}]")
                if asset_duration is not None \
                        and float(src_end) > float(asset_duration) + 0.05:
                    errors.append(f"{where}: trim end {src_end}s "
                                  "exceeds the source duration "
                                  f"{asset_duration}s")
                if abs((float(src_end) - float(src_start))
                       - float(duration)) > 0.05:
                    errors.append(f"{where}: trim length does not "
                                  "match the timeline duration")
            overlap = 0.0
            transition = transitions.get(clip.get("clip_id"))
            if transition is not None:
                overlap = float(transition.get("duration_seconds") or 0)
                if transition.get("type") not in ("cut", "fadeblack"):
                    errors.append(f"{where}: transition type "
                                  f"{transition.get('type')!r} is not "
                                  "supported")
            cursor = float(start) + float(duration) - overlap
        if clips and abs(cursor - float(total)) > 0.05:
            errors.append("video track ends at "
                          f"{cursor:.3f}s but the timeline duration "
                          f"is {total}s")
    # Audio tracks: no overlap inside a track; clips resolve.
    for track in timeline.get("audio_tracks") or []:
        clips = (track or {}).get("clips") or []
        cursor = None
        for clip in clips:
            where = (f"audio clip {clip.get('clip_id')!r} on track "
                     f"{track.get('track_id')!r}")
            asset_id = clip.get("asset_id")
            try:
                record = assets_mod.resolve_asset(asset_registry,
                                                  asset_id)
            except assets_mod.AssetError as exc:
                errors.append(f"{where}: {exc.errors[0]}")
                continue
            if record.get("status") != "VERIFIED":
                errors.append(f"{where}: asset {asset_id!r} is not "
                              "VERIFIED")
            start = clip.get("timeline_start_seconds")
            duration = clip.get("duration_seconds")
            if not isinstance(start, (int, float)) \
                    or not isinstance(duration, (int, float)):
                errors.append(f"{where}: start/duration must be "
                              "numbers")
                continue
            if cursor is not None and float(start) < cursor - 0.05:
                errors.append(f"{where}: overlaps the previous clip "
                              f"on its track (starts {start}s, "
                              f"previous ends {cursor:.3f}s)")
            end = float(start) + float(duration)
            cursor = end if cursor is None else max(cursor, end)
            if end > float(total) + 0.05:
                errors.append(f"{where}: extends beyond the timeline "
                              f"({end:.3f}s > {total}s)")
    return errors


# ------------------------------------------------------------------
# Assembly (FFmpeg — the single proven render path)
# ------------------------------------------------------------------

def video_filter_chain(timeline) -> str:
    """The xfade filter chain for the video track (pure function).

    Each transition is a dip-to-black of TRANSITION_SECONDS; the
    offset of transition ``i`` is the cumulative clip duration
    minus one overlap per boundary so far.
    """
    clips = (timeline.get("video_tracks") or [{}])[0].get("clips") or []
    transitions = timeline.get("transitions") or []
    if len(clips) == 1:
        return "[0:v]format=yuv420p[vout]"
    chain = []
    current = "[0:v]"
    offset = 0.0
    for index, transition in enumerate(transitions):
        duration = float(
            clips[index].get("duration_seconds") or 0)
        offset += duration - float(
            transition.get("duration_seconds") or TRANSITION_SECONDS)
        nxt = f"[{index + 1}:v]"
        out = f"[x{index}]" if index < len(transitions) - 1 else "[xv]"
        chain.append(
            f"{current}{nxt}xfade=transition=fadeblack:"
            f"duration={transition.get('duration_seconds')}:"
            f"offset={offset:.3f}{out}")
        current = out
    chain.append("[xv]format=yuv420p[vout]")
    return ";".join(chain)


def assemble_timeline(session, project, timeline, asset_registry,
                      asset_root, work_dir, output_path, *,
                      ffmpeg="ffmpeg", ffprobe="ffprobe",
                      timeout_s=600) -> dict:
    """Assemble the canonical timeline into the final MP4.

    Steps: (1) validate the timeline and verify every asset
    against the real files; (2) mix the audio with the Phase D
    mixer (voice priority, ducked music, room tone, SFX);
    (3) render the video track through the xfade chain and mux
    with the mixed audio. Returns an execution record
    (output path, size, SHA-256, probe, operations, audio-mix
    record, step log). Raises :class:`TimelineError` with
    diagnostics on any failure — a failed render is never
    recorded as delivered.
    """
    from . import local_session
    if not local_session.is_active_session(session):
        raise TimelineError("assembly needs an exact active "
                            "LocalSession")
    errors = validate_canonical_timeline(timeline, asset_registry,
                                         project)
    if errors:
        raise TimelineError(errors)
    # Verify every referenced asset against its real file first.
    asset_paths: dict[str, str] = {}
    for track in (timeline.get("video_tracks") or []) \
            + (timeline.get("audio_tracks") or []):
        for clip in (track or {}).get("clips") or []:
            asset_id = clip.get("asset_id")
            if asset_id in asset_paths:
                continue
            record = assets_mod.resolve_asset(asset_registry, asset_id)
            try:
                verified = assets_mod.verify_asset(
                    record, asset_root, ffprobe=ffprobe)
            except assets_mod.AssetError as exc:
                raise TimelineError(
                    [f"assembly: asset {asset_id!r} failed "
                     "verification: " + "; ".join(exc.errors)])
            asset_registry = dict(asset_registry)
            asset_registry[asset_id] = verified
            path = verified["path"]
            if not is_safe_relative_path(path):
                raise TimelineError(
                    f"assembly: asset {asset_id!r} path {path!r} is "
                    "not a safe relative path")
            real = os.path.realpath(
                os.path.join(os.path.realpath(asset_root), path))
            if not os.path.isfile(real):
                raise TimelineError(
                    f"assembly: asset {asset_id!r} file {path!r} "
                    "does not exist")
            asset_paths[asset_id] = real
    os.makedirs(work_dir, exist_ok=True)
    mixed_audio_path = os.path.join(work_dir, "mixed-audio.wav")
    try:
        from . import production_audio as audio_mod
        mix = audio_mod.mix_audio(
            timeline, asset_paths,
            project.get("audio_profile") or {},
            mixed_audio_path, ffmpeg=ffmpeg, ffprobe=ffprobe)
    except Exception as exc:  # noqa: BLE001 - diagnostics recorded
        raise TimelineError(
            f"assembly: audio mix failed: {exc}") from exc
    # Video inputs in timeline order.
    video_clips = (timeline.get("video_tracks") or [{}])[0].get("clips") or []
    argv: list[str] = [ffmpeg, "-y", "-v", "error"]
    for clip in video_clips:
        argv += ["-i", asset_paths[clip["asset_id"]]]
    argv += ["-i", mixed_audio_path]
    filter_chain = video_filter_chain(timeline)
    profile = timeline.get("output_profile") or {}
    total = float(timeline.get("duration_seconds"))
    assembly = project.get("assembly") or {}
    argv += [
        "-filter_complex", filter_chain,
        "-map", "[vout]", "-map", f"{len(video_clips)}:a",
        "-c:v", assembly.get("video_codec", "libx264"),
        "-crf", str(assembly.get("crf", 20)),
        "-preset", assembly.get("preset", "medium"),
        "-pix_fmt", assembly.get("pix_fmt", "yuv420p"),
        "-c:a", assembly.get("audio_codec", "aac"),
        "-b:a", assembly.get("audio_bitrate", "192k"),
        "-ar", str(assembly.get("audio_sample_rate", 48000)),
        "-metadata", "creation_time=1970-01-01T00:00:00Z",
        "-t", f"{total:.3f}",
        output_path,
    ]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True,
                              timeout=timeout_s)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TimelineError(
            f"assembly: ffmpeg render failed: {exc}") from exc
    if proc.returncode != 0 or not os.path.isfile(output_path):
        raise TimelineError(
            "assembly: ffmpeg render failed: "
            f"{(proc.stderr or '').strip()[:800]}")
    probe = assets_mod.probe_media_file(output_path, ffprobe=ffprobe)
    geometry = geometry_from_probe(probe)
    if geometry is None:
        raise TimelineError("assembly: rendered output has no video "
                            "geometry")
    # geometry_from_probe nests the dimensions under "resolution".
    resolution = geometry.get("resolution") or {}
    width = resolution.get("width")
    height = resolution.get("height")
    aspect = geometry.get("aspect_ratio")
    if (width != profile.get("width")
            or height != profile.get("height")
            or aspect != profile.get("aspect_ratio")):
        raise TimelineError(
            "assembly: rendered output geometry "
            f"({width}x{height}, {aspect}) does not match the "
            "output profile")
    if probe["frame_rate"] is None \
            or abs(probe["frame_rate"] - float(profile.get("frame_rate"))) > 0.01:
        raise TimelineError(
            "assembly: rendered output frame rate "
            f"({probe['frame_rate_rational']}) does not match the "
            "output profile")
    if probe["duration_seconds"] is None \
            or abs(probe["duration_seconds"] - total) > 0.15:
        raise TimelineError(
            "assembly: rendered output duration "
            f"({probe['duration_seconds']}s) does not match the "
            f"timeline ({total}s)")
    sha, size = assets_mod.hash_file(output_path)
    operations = [{
        "op": "xfade",
        "tool": "ffmpeg",
        "detail": f"{len(video_clips)} clips joined with "
                  f"{len(timeline.get('transitions') or [])} "
                  "fadeblack transitions; no scale, crop, or "
                  "rotation applied",
    }, {
        "op": "audio-mix",
        "tool": "ffmpeg",
        "detail": "voice priority, music ducked beneath speech, "
                  "room tone, SFX at shot boundaries",
    }]
    return {
        "output_path": output_path,
        "size_bytes": size,
        "sha256": sha,
        "probe": probe,
        "operations": operations,
        "audio_mix": mix,
        "steps": [
            {"step": "validate-timeline", "status": "ok"},
            {"step": "verify-assets",
             "status": "ok", "assets": sorted(asset_paths)},
            {"step": "mix-audio", "status": "ok"},
            {"step": "render-video", "status": "ok"},
            {"step": "mux", "status": "ok"},
        ],
    }
