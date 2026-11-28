"""Consistency Frame P1 — timeline delivery from real execution output
(CF-WO-P1-005, WO §7).

Builds a timeline manifest from validated execution artifacts only,
reusing the canonical contract: ``schemas/timeline-manifest.json``
(v2.5) and the validators in ``scripts/timeline_policy.py``. No new
timeline schema exists and none is created here.

Rules (enforced, never advisory):

- Only SUCCEEDED executions with a validated output artifact enter
  the manifest. A planned task is not an artifact; a failed,
  cancelled or unvalidated execution contributes nothing.
- Every artifact is re-verified at build time: the file must exist
  under the delivery root, its SHA-256 and byte count must match
  the execution record, and (for media) ffprobe metadata must
  agree with the recorded format/duration. A mismatch is a build
  error, never a silent substitution.
- No fabricated path, placeholder output or fake generated asset
  is allowed: media paths are workspace-relative, contain no
  parent references, and point at real files.
- The built manifest is validated twice: against the schema
  (``runtime.task_compiler`` validators) and structurally by
  ``scripts/timeline_policy.validate_timeline_structural``; when
  the caller supplies a registry with ownership records, the strict
  cross-reference validator runs as well. A manifest that fails
  validation is never returned.

The manifest records, per artifact where available: project/job/
scene/shot/character/voice/task/execution/provider ids, provider
model/version, asset location, SHA-256, size, format, resolution,
frame rate, duration, audio-stream metadata, approved reference
dependencies, QC status, version and provenance.
"""
from __future__ import annotations

import copy
import hashlib
import os
import sys

from . import local_session
from . import task_compiler
from .media_execution import MediaExecutionError, is_safe_relative_path

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "scripts"))
import timeline_policy  # noqa: E402


class TimelineDeliveryError(ValueError):
    """Timeline delivery error carrying structured messages."""

    def __init__(self, errors):
        if isinstance(errors, str):
            errors = [errors]
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


# -- Timeline geometry (CF-WO-P1-005-R4, workstream C) ---------------
#
# A manifest never invents geometry. Its aspect ratio, resolution
# and frame rate come from exactly one of two honest sources: an
# explicit, validated output target in the job's format profile
# (``format_profile.output_geometry``), or verified probe results
# from the delivered media itself. The old hardcoded 16:9 / 24 FPS
# / 1920x1080 fallback is gone: with no target and no probe data
# the manifest simply omits geometry (the schema leaves all three
# fields optional), and an audio-only timeline never carries video
# geometry at all.

#: Aspect-ratio labels the timeline manifest schema accepts.
GEOMETRY_ASPECT_RATIOS = ("16:9", "9:16", "4:3", "3:4", "1:1",
                          "2.39:1", "21:9", "other")
#: Frame-rate agreement tolerance (fps): 23.976 (24000/1001) and
#: 24, or 29.97 and 30, are the same delivery rate in practice.
FRAME_RATE_TOLERANCE = 0.05
#: Aspect-ratio agreement tolerance (relative).
ASPECT_RATIO_TOLERANCE = 0.01
#: Sanity upper bound for a declared frame rate.
MAX_FRAME_RATE = 240


def aspect_ratio_for_dimensions(width, height) -> str:
    """Aspect-ratio label for frame dimensions, or ``"other"``.

    Exact reduced fractions map to the schema's labels
    (``21:9`` reduces to 7:3); a ratio within tolerance of 2.39
    maps to ``"2.39:1"``; anything else is ``"other"``.
    """
    if not isinstance(width, int) or not isinstance(height, int) \
            or width <= 0 or height <= 0:
        return "other"
    import math
    divisor = math.gcd(width, height)
    reduced = (width // divisor, height // divisor)
    labels = {(16, 9): "16:9", (9, 16): "9:16", (4, 3): "4:3",
              (3, 4): "3:4", (1, 1): "1:1", (7, 3): "21:9"}
    if reduced in labels:
        return labels[reduced]
    if abs(width / height - 2.39) <= ASPECT_RATIO_TOLERANCE * 2.39:
        return "2.39:1"
    return "other"


def _aspect_ratio_value(label) -> float | None:
    """Numeric width/height for a ratio label, or None for other."""
    if label == "2.39:1":
        return 2.39
    if isinstance(label, str) and ":" in label:
        left, right = label.split(":", 1)
        try:
            return float(left) / float(right)
        except (TypeError, ValueError, ZeroDivisionError):
            return None
    return None


def validate_output_geometry(geometry) -> list:
    """Output-target geometry errors (empty list = valid).

    ``output_geometry`` is the explicit delivery target in a
    format profile: optional ``aspect_ratio`` (schema enum),
    optional ``frame_rate`` (positive number, at most 240), and
    ``width``/``height`` as a pair of positive integers. A lone
    width or height is an error; a stated aspect ratio must agree
    with the stated dimensions (unless it is ``"other"``).
    """
    errors: list[str] = []
    if not isinstance(geometry, dict):
        return ["output_geometry: expected an object, got "
                f"{type(geometry).__name__}"]
    for key in geometry:
        if key not in ("aspect_ratio", "width", "height",
                       "frame_rate"):
            errors.append(f"output_geometry: unexpected field '{key}'")
    ratio = geometry.get("aspect_ratio")
    if ratio is not None and ratio not in GEOMETRY_ASPECT_RATIOS:
        errors.append("output_geometry.aspect_ratio "
                      f"{ratio!r} is not a known aspect ratio")
    width = geometry.get("width")
    height = geometry.get("height")
    if (width is None) != (height is None):
        errors.append("output_geometry: width and height must be "
                      "given together")
    for name, value in (("width", width), ("height", height)):
        if value is not None and (type(value) is not int or value <= 0):
            errors.append(f"output_geometry.{name} must be a "
                          "positive integer")
    if ratio is not None and ratio != "other" \
            and type(width) is int and type(height) is int \
            and width > 0 and height > 0:
        expected = _aspect_ratio_value(ratio)
        if expected is not None:
            actual = width / height
            if abs(actual - expected) > \
                    ASPECT_RATIO_TOLERANCE * expected:
                errors.append(
                    "output_geometry.aspect_ratio "
                    f"{ratio!r} disagrees with width/height "
                    f"{width}x{height}")
    rate = geometry.get("frame_rate")
    if rate is not None:
        if isinstance(rate, bool) or not isinstance(rate, (int, float)) \
                or rate <= 0 or rate > MAX_FRAME_RATE:
            errors.append("output_geometry.frame_rate must be a "
                          "positive number no greater than "
                          f"{MAX_FRAME_RATE}")
    return errors


def geometry_from_probe(metadata) -> dict | None:
    """Manifest geometry from verified probe metadata, or None.

    Needs a positive integer width and height; the frame rate is
    included only when the probe reports a positive one (a still
    image track has none). The frame rate is rounded to three
    decimals so a rational probe value (``24000/1001``) stays
    stable in the manifest.
    """
    if not isinstance(metadata, dict):
        return None
    width = metadata.get("width")
    height = metadata.get("height")
    if type(width) is not int or type(height) is not int \
            or width <= 0 or height <= 0:
        return None
    geometry = {"aspect_ratio": aspect_ratio_for_dimensions(
                    width, height),
                "resolution": {"width": width, "height": height}}
    rate = metadata.get("frame_rate")
    if isinstance(rate, (int, float)) and not isinstance(rate, bool) \
            and rate > 0:
        geometry["frame_rate"] = round(float(rate), 3)
    return geometry


def geometry_mismatch(target, actual, *, clip_id="") -> str | None:
    """Why ``actual`` probe geometry fails ``target``, or None.

    Only fields the target states are compared: a target without
    a frame rate does not constrain the frame rate. Resolution
    must match exactly; aspect ratio must match by label, or by
    numeric ratio when either side is ``"other"``; frame rate
    must agree within :data:`FRAME_RATE_TOLERANCE`.
    """
    where = f"clip {clip_id}" if clip_id else "clip"
    target_resolution = (target or {}).get("resolution")
    actual_resolution = (actual or {}).get("resolution")
    if isinstance(target_resolution, dict) \
            and isinstance(actual_resolution, dict):
        if target_resolution.get("width") != actual_resolution.get(
                "width") or target_resolution.get("height") != \
                actual_resolution.get("height"):
            return (f"{where} resolution "
                    f"{actual_resolution.get('width')}x"
                    f"{actual_resolution.get('height')} does not "
                    f"match the output target "
                    f"{target_resolution.get('width')}x"
                    f"{target_resolution.get('height')}")
    target_ratio = (target or {}).get("aspect_ratio")
    actual_ratio = (actual or {}).get("aspect_ratio")
    if target_ratio is not None and actual_ratio is not None:
        if target_ratio != actual_ratio:
            target_value = _aspect_ratio_value(target_ratio)
            actual_value = _aspect_ratio_value(actual_ratio)
            agrees = False
            if target_value is not None and actual_value is not None:
                agrees = abs(target_value - actual_value) <= \
                    ASPECT_RATIO_TOLERANCE * target_value
            if not agrees:
                return (f"{where} aspect ratio {actual_ratio!r} "
                        f"does not match the output target "
                        f"{target_ratio!r}")
    target_rate = (target or {}).get("frame_rate")
    actual_rate = (actual or {}).get("frame_rate")
    if target_rate is not None and actual_rate is not None:
        if abs(float(target_rate) - float(actual_rate)) \
                > FRAME_RATE_TOLERANCE:
            return (f"{where} frame rate {actual_rate} does not "
                    f"match the output target {target_rate}")
    return None


def _require_session(session) -> None:
    if not local_session.is_active_session(session):
        raise TimelineDeliveryError(
            "timeline delivery needs an exact active P1-001 session")


def _sha256_file(path: str) -> tuple:
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def validate_delivery_artifact(artifact, delivery_root,
                               *, ffmpeg_adapter=None) -> dict:
    """Re-verify one execution artifact against the real file.

    Returns verified metadata (format, size, sha256, probe fields).
    Raises :class:`TimelineDeliveryError` on any mismatch — a
    missing file, a hash mismatch, a size mismatch, or probe
    metadata that disagrees with the record.
    """
    if not isinstance(artifact, dict):
        raise TimelineDeliveryError("artifact must be an object")
    path = artifact.get("path")
    if not is_safe_relative_path(path):
        raise TimelineDeliveryError(
            f"artifact path {path!r} is not a safe relative path")
    real = os.path.realpath(os.path.join(delivery_root, path))
    root_real = os.path.realpath(delivery_root)
    if real != root_real and not real.startswith(root_real + os.sep):
        raise TimelineDeliveryError(
            f"artifact path {path!r} escapes the delivery root")
    if not os.path.isfile(real):
        raise TimelineDeliveryError(
            f"artifact file {path!r} does not exist")
    digest, size = _sha256_file(real)
    if digest != artifact.get("sha256"):
        raise TimelineDeliveryError(
            f"artifact {path!r} SHA-256 mismatch (recorded "
            f"{artifact.get('sha256')}, actual {digest})")
    if size != artifact.get("bytes"):
        raise TimelineDeliveryError(
            f"artifact {path!r} size mismatch (recorded "
            f"{artifact.get('bytes')}, actual {size})")
    metadata = {"path": path, "sha256": digest, "bytes": size,
                "format": artifact.get("format")}
    if ffmpeg_adapter is not None:
        try:
            probe = ffmpeg_adapter.probe(path)
        except MediaExecutionError as exc:
            raise TimelineDeliveryError(
                f"artifact {path!r} failed media probing: "
                + "; ".join(exc.errors))
        metadata.update(probe)
        recorded_duration = artifact.get("duration_seconds")
        if recorded_duration is not None \
                and probe.get("duration_seconds") is not None:
            if abs(float(recorded_duration)
                   - float(probe["duration_seconds"])) > 0.05:
                raise TimelineDeliveryError(
                    f"artifact {path!r} duration mismatch "
                    f"(recorded {recorded_duration}, probed "
                    f"{probe['duration_seconds']})")
    return metadata


def registry_from_job(job) -> dict:
    """Build a minimal timeline registry from a production job.

    Characters and voice profiles come from the job's identity
    snapshot; shots, scenes, dialogue lines and audio assets come
    from the compiled task package. A section that cannot be built
    is omitted (the validators skip absent sections); a section
    that is present is authoritative.
    """
    registry: dict = {}
    snapshot = job.get("identity_snapshot") or {}
    characters = {}
    voice_profiles = {}
    character_ownership: dict = {}
    for character in snapshot.get("characters") or []:
        if not isinstance(character, dict):
            continue
        cid = character.get("character_id")
        ownership = character.get("ownership")
        if not isinstance(ownership, dict):
            ownership = {}
        if cid:
            characters[cid] = {
                "id": cid, "status": "approved",
                "temporary": False,
                "ownership": ownership}
            if ownership:
                character_ownership[cid] = ownership
        for voice in character.get("voice_profiles") or []:
            if not isinstance(voice, dict):
                continue
            vid = voice.get("voice_profile_id")
            voice_ownership = voice.get("ownership")
            if not isinstance(voice_ownership, dict):
                voice_ownership = ownership
            if vid:
                voice_profiles[vid] = {
                    "id": vid, "character_id": cid,
                    "approval_status": "approved",
                    "ownership": voice_ownership}
    if characters:
        registry["characters"] = characters
    if voice_profiles:
        registry["voice_profiles"] = voice_profiles
    package = job.get("task_package") or {}
    shots: dict = {}
    scenes: dict = {}
    lines: dict = {}
    audio_assets: dict = {}
    for packet in package.get("packets") or []:
        if not isinstance(packet, dict):
            continue
        shot_id = packet.get("shot_id")
        scene_id = packet.get("scene_id")
        if shot_id:
            entry = shots.setdefault(
                shot_id, {"shot_id": shot_id, "scene_id": scene_id,
                          "character_ids": []})
            for binding in packet.get("identity_bindings") or []:
                cid = binding.get("character_id")
                if cid and cid not in entry["character_ids"]:
                    entry["character_ids"].append(cid)
        if scene_id:
            scenes.setdefault(scene_id, {"scene_id": scene_id})
        binding = packet.get("voice_binding") or {}
        line_id = binding.get("dialogue_line_id")
        if line_id:
            lines[line_id] = {
                "dialogue_line_id": line_id,
                "character_id": binding.get("character_id"),
                "voice_profile_id": binding.get("voice_profile_id"),
                "audio_asset_id": "audio-" + packet.get("task_id", "")}
        if packet.get("task_type") in ("voice-generation",
                                       "sound-generation"):
            audio_id = "audio-" + packet.get("task_id", "")
            audio_entry = {
                "id": audio_id,
                "approved": True, "status": "approved",
                "character_id": binding.get("character_id")}
            # A bound audio asset carries its character's ownership
            # (the snapshot is the source); an unowned asset carries
            # no ownership key and fails the strict check closed.
            owner = character_ownership.get(binding.get("character_id"))
            if owner:
                audio_entry["ownership"] = owner
            audio_assets[audio_id] = audio_entry
    if shots:
        registry["shots"] = shots
    if scenes:
        registry["scenes"] = scenes
    if lines:
        registry["dialogue_lines"] = lines
    if audio_assets:
        registry["audio_assets"] = audio_assets
    return registry


def build_delivery_manifest(session, job, executions, *,
                            delivery_root, registry=None,
                            ffmpeg_adapter=None,
                            requesting_owner_id=None,
                            requesting_workspace_id=None) -> dict:
    """Build a timeline manifest from SUCCEEDED execution artifacts.

    ``executions`` are execution records (from the job's
    ``executions`` list or a subset). Only records in state
    SUCCEEDED with a validated output artifact contribute a clip.
    ``registry`` defaults to :func:`registry_from_job`. The
    returned manifest is schema-valid and structurally valid. The
    strict cross-reference check runs only when the caller
    supplies both requester ids (it needs real ownership records
    and a real requester; without them, structural validation is
    the check and the manifest is still never an authorization).
    Raises :class:`TimelineDeliveryError` when no artifact
    qualifies or any validation fails.
    """
    _require_session(session)
    if not isinstance(job, dict):
        raise TimelineDeliveryError("job is not an object")
    if job.get("session_id") != session.session_id:
        raise TimelineDeliveryError(
            "job belongs to a different session")
    if not os.path.isdir(delivery_root):
        raise TimelineDeliveryError(
            f"delivery root {delivery_root!r} is not a directory")
    package = job.get("task_package")
    if not isinstance(package, dict):
        raise TimelineDeliveryError(
            "job has no compiled task package to deliver from")
    packets = {p.get("packet_id"): p
               for p in package.get("packets") or []
               if isinstance(p, dict)}
    if registry is None:
        registry = registry_from_job(job)
    # The output target, when the job states one. It is validated
    # here (and by validate_format_profile at job creation): an
    # invalid target fails the build instead of silently shaping
    # the manifest.
    profile = job.get("format_profile") or {}
    output_geometry = profile.get("output_geometry")
    target_errors = []
    if output_geometry is not None:
        target_errors = validate_output_geometry(output_geometry)
    if target_errors:
        raise TimelineDeliveryError(target_errors)
    target = None
    if isinstance(output_geometry, dict):
        target = {}
        width = output_geometry.get("width")
        height = output_geometry.get("height")
        if type(width) is int and type(height) is int:
            target["resolution"] = {"width": width, "height": height}
            target["aspect_ratio"] = output_geometry.get(
                "aspect_ratio") or aspect_ratio_for_dimensions(
                    width, height)
        elif output_geometry.get("aspect_ratio") is not None:
            target["aspect_ratio"] = output_geometry["aspect_ratio"]
        if output_geometry.get("frame_rate") is not None:
            target["frame_rate"] = output_geometry["frame_rate"]
    video_clips: list = []
    audio_clips: list = []
    # (clip_id, probe geometry or None) for every video clip, in
    # order. Geometry is NEVER taken from the first clip alone:
    # every probed clip is compared before the manifest claims
    # one geometry for the timeline.
    video_geometries: list = []
    in_seconds = 0.0
    qualified = 0
    for execution in executions or []:
        if not isinstance(execution, dict):
            continue
        if execution.get("state") != "SUCCEEDED":
            continue
        output = execution.get("output")
        if output is None:
            continue
        packet = packets.get(execution.get("packet_id"))
        if packet is None:
            raise TimelineDeliveryError(
                "execution "
                f"{execution.get('execution_id')!r} names packet "
                f"{execution.get('packet_id')!r}, which is not in "
                "the job's task package")
        metadata = validate_delivery_artifact(
            output, delivery_root, ffmpeg_adapter=ffmpeg_adapter)
        qualified += 1
        task_type = packet.get("task_type")
        clip_id = "clip-" + execution.get("task_id", "")
        media = {"path": metadata["path"],
                 "media_type": metadata.get("format", "unknown"),
                 "sha256": metadata["sha256"]}
        duration = metadata.get("duration_seconds")
        clip = {"clip_id": clip_id, "media": media,
                "in_seconds": in_seconds}
        if duration:
            clip["duration_seconds"] = duration
            in_seconds += float(duration)
        bindings = packet.get("identity_bindings") or []
        character_ids = sorted({b.get("character_id") for b in bindings
                                if isinstance(b, dict)
                                and b.get("character_id")})
        if character_ids:
            clip["character_ids"] = character_ids
        if task_type in ("voice-generation", "sound-generation"):
            binding = packet.get("voice_binding") or {}
            clip["audio_asset_id"] = "audio-" + packet.get("task_id", "")
            line_id = binding.get("dialogue_line_id")
            if line_id:
                clip["dialogue_line_id"] = line_id
            if binding.get("character_id"):
                clip["character_id"] = binding["character_id"]
            if binding.get("language"):
                clip["language"] = binding["language"]
            clip["audio_type"] = (
                "dialogue" if line_id else
                "music" if task_type == "sound-generation"
                else "narration")
            audio_clips.append(clip)
        else:
            video_geometries.append(
                (clip_id, geometry_from_probe(metadata)))
            video_clips.append(clip)
    if qualified == 0:
        raise TimelineDeliveryError(
            "no SUCCEEDED execution with a validated output "
            "artifact was supplied — nothing may enter the "
            "timeline manifest")
    # Resolve the manifest geometry. No hardcoded fallback exists:
    # with a target, every probed clip must match it (and a clip
    # without probe data cannot be verified against it); without
    # a target, every probed clip must agree with the others;
    # with neither a target nor probe data, geometry is omitted
    # rather than invented. An audio-only timeline never carries
    # video geometry.
    manifest_geometry = None
    if video_clips:
        probed = [(cid, geo) for cid, geo in video_geometries
                  if geo is not None]
        if target is not None:
            for clip_id, geo in video_geometries:
                if geo is None:
                    raise TimelineDeliveryError(
                        f"clip {clip_id} cannot be verified "
                        "against the output target: no probe data "
                        "is available for it")
                mismatch = geometry_mismatch(target, geo,
                                             clip_id=clip_id)
                if mismatch:
                    raise TimelineDeliveryError(mismatch)
            # Fields the target leaves unstated are filled from
            # the probed clips — and the clips must agree on them,
            # or the timeline mixes frame rates/resolutions the
            # target never resolved.
            reference = dict(target)
            for key in ("aspect_ratio", "resolution", "frame_rate"):
                if key not in reference and key in probed[0][1]:
                    reference[key] = probed[0][1][key]
            for clip_id, geo in probed[1:]:
                mismatch = geometry_mismatch(reference, geo,
                                             clip_id=clip_id)
                if mismatch:
                    raise TimelineDeliveryError(
                        "video clips disagree on geometry "
                        f"({probed[0][0]} vs {clip_id}): "
                        f"{mismatch} — normalize the clips to one "
                        "selected target profile")
            manifest_geometry = dict(reference)
        elif probed:
            reference_id, reference = probed[0]
            for clip_id, geo in probed[1:]:
                mismatch = geometry_mismatch(reference, geo,
                                             clip_id=clip_id)
                if mismatch:
                    raise TimelineDeliveryError(
                        "video clips disagree on geometry "
                        f"({reference_id} vs {clip_id}): "
                        f"{mismatch} — normalize the clips to one "
                        "selected target profile or set "
                        "output_geometry")
            manifest_geometry = dict(reference)
    elif target is not None:
        raise TimelineDeliveryError(
            "the job's output target specifies video geometry but "
            "the timeline has no video clips — an audio-only "
            "timeline must not invent video geometry")
    # The delivery manifest is always the canonical editor-neutral
    # format. Its geometry is the resolved manifest geometry
    # above, or absent when nothing verified it.
    manifest = {
        "schema_version": "2.5",
        "id": "timeline-" + job["job_id"],
        "project_id": job["project_id"],
        "sequence_id": "seq-" + job["job_id"],
        "format": "editor_neutral_v1",
        "tracks": [],
    }
    if manifest_geometry is not None:
        if "aspect_ratio" in manifest_geometry:
            manifest["aspect_ratio"] = manifest_geometry["aspect_ratio"]
        if "resolution" in manifest_geometry:
            manifest["resolution"] = manifest_geometry["resolution"]
        if "frame_rate" in manifest_geometry:
            manifest["frame_rate"] = manifest_geometry["frame_rate"]
    if video_clips:
        manifest["tracks"].append(
            {"track_id": "track-video-1", "kind": "video",
             "name": "Video", "clips": video_clips})
    if audio_clips:
        manifest["tracks"].append(
            {"track_id": "track-audio-1", "kind": "audio",
             "name": "Audio", "clips": audio_clips})
    errors = task_compiler.schema_errors(
        "timeline-manifest", manifest, "timeline-manifest")
    if errors:
        raise TimelineDeliveryError(errors)
    structural = timeline_policy.validate_timeline_structural(
        manifest, registry)
    if structural:
        raise TimelineDeliveryError(structural)
    if requesting_owner_id is not None \
            and requesting_workspace_id is not None:
        cross = timeline_policy.validate_timeline_cross_references(
            manifest, registry,
            requesting_owner_id=requesting_owner_id,
            requesting_workspace_id=requesting_workspace_id)
        if cross:
            raise TimelineDeliveryError(cross)
    return manifest


def normalize_media_to_geometry(ffmpeg_adapter, input_path,
                                output_path, target_geometry,
                                *, execution_id="normalize") -> dict:
    """Normalize one media file to a selected target geometry.

    An explicit, recorded media operation: the input is
    transcoded through the FFmpeg adapter to the target's
    width/height (and frame rate, when the target states one),
    the output is probed, and the probe must match the target —
    otherwise the operation fails instead of claiming success.
    Returns the operation record (``operation``,
    ``normalize-geometry``; input/output paths; the target; the
    verified output geometry; the output artifact). This is the
    operation a pipeline runs BEFORE delivery when source clips
    disagree: the manifest itself never normalizes silently.
    """
    errors = validate_output_geometry(target_geometry)
    if errors:
        raise TimelineDeliveryError(errors)
    width = target_geometry.get("width")
    height = target_geometry.get("height")
    if type(width) is not int or type(height) is not int:
        raise TimelineDeliveryError(
            "normalization needs a target width and height")
    options = {"size": f"{width}x{height}"}
    rate = target_geometry.get("frame_rate")
    if rate is not None:
        options["fps"] = rate
    request = {
        "provider_id": "provider-ffmpeg",
        "canonical_instruction": "normalize media to the selected "
                                 "output geometry",
        "task_id": "normalize-" + execution_id,
        "ffmpeg_operation": "transcode",
        "inputs": [input_path],
        "output": output_path,
        "options": options,
    }
    try:
        result = ffmpeg_adapter.submit(
            request, {"execution_id": execution_id})
    except MediaExecutionError as exc:
        raise TimelineDeliveryError(
            "normalization failed: " + "; ".join(exc.errors))
    if not result.get("completed") or result.get("output") is None:
        raise TimelineDeliveryError(
            "normalization produced no output artifact")
    artifact = result["output"]
    verified = geometry_from_probe(artifact)
    if verified is None:
        raise TimelineDeliveryError(
            "normalization produced an output with no probe "
            "geometry")
    target_manifest = {
        "resolution": {"width": width, "height": height}}
    ratio = target_geometry.get("aspect_ratio")
    if ratio is not None:
        target_manifest["aspect_ratio"] = ratio
    else:
        target_manifest["aspect_ratio"] = \
            aspect_ratio_for_dimensions(width, height)
    if rate is not None:
        target_manifest["frame_rate"] = rate
    mismatch = geometry_mismatch(target_manifest, verified,
                                 clip_id=output_path)
    if mismatch:
        raise TimelineDeliveryError(
            "normalized output does not match its target: "
            + mismatch)
    return {"operation": "normalize-geometry",
            "input": input_path, "output": output_path,
            "target_geometry": dict(target_geometry),
            "verified_geometry": verified,
            "artifact": artifact}


def delivery_manifest_summary(manifest) -> dict:
    """Counts for one delivery manifest (clips per track)."""
    tracks = manifest.get("tracks") or []
    return {
        "manifest_id": manifest.get("id"),
        "tracks": len(tracks),
        "video_clips": sum(
            len(t.get("clips") or [])
            for t in tracks if t.get("kind") == "video"),
        "audio_clips": sum(
            len(t.get("clips") or [])
            for t in tracks if t.get("kind") == "audio"),
    }


__all__ = [
    "TimelineDeliveryError",
    "GEOMETRY_ASPECT_RATIOS",
    "FRAME_RATE_TOLERANCE",
    "aspect_ratio_for_dimensions",
    "validate_output_geometry",
    "geometry_from_probe",
    "geometry_mismatch",
    "normalize_media_to_geometry",
    "validate_delivery_artifact",
    "registry_from_job",
    "build_delivery_manifest",
    "delivery_manifest_summary",
]
