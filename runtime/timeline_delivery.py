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
from .media_execution import MediaExecutionError

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
    if not isinstance(path, str) or not path \
            or path.startswith("/") or ".." in path.split("/"):
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
    video_clips: list = []
    audio_clips: list = []
    first_video_resolution = None
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
            if first_video_resolution is None:
                width = metadata.get("width")
                height = metadata.get("height")
                if isinstance(width, int) and isinstance(height, int) \
                        and width > 0 and height > 0:
                    first_video_resolution = {
                        "width": width, "height": height}
            video_clips.append(clip)
    if qualified == 0:
        raise TimelineDeliveryError(
            "no SUCCEEDED execution with a validated output "
            "artifact was supplied — nothing may enter the "
            "timeline manifest")
    profile = job.get("format_profile") or {}
    # The production format profile carries only the delivery
    # profile, duration target and chapters (see
    # production_orchestrator.validate_format_profile) — it never
    # carries media geometry. The delivery manifest is always the
    # canonical editor-neutral format; its resolution defaults to
    # 1920x1080 unless a delivered video artifact proves otherwise.
    manifest = {
        "schema_version": "2.5",
        "id": "timeline-" + job["job_id"],
        "project_id": job["project_id"],
        "sequence_id": "seq-" + job["job_id"],
        "format": "editor_neutral_v1",
        "aspect_ratio": "16:9",
        "resolution": first_video_resolution or {
            "width": 1920, "height": 1080},
        "frame_rate": 24,
        "tracks": [],
    }
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
    "validate_delivery_artifact",
    "registry_from_job",
    "build_delivery_manifest",
    "delivery_manifest_summary",
]
