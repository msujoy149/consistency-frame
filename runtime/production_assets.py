"""Consistency Frame P1 — visual asset production and ingestion (CF-WO-P1-006, Phase B).

Asset records, registration, resolution, verification, and the
local visual-generation stage for the reference project.

Every asset carries a stable id, project/shot association, type,
source/provider, path, MIME type, size, SHA-256, resolution /
duration / frame rate where applicable, license/provenance, a
privacy/transmission classification, and a generation/execution
status. Nothing is registered silently: a missing reference is
an error, never a substitution, and a corrupted file or a wrong
hash fails verification instead of entering the timeline.

Visuals for the reference project are generated locally and
deterministically with FFmpeg (animated gradients, moving accent
shapes, keyword text). They are REAL locally generated media,
labelled ``ffmpeg-local`` in every record — NOT AI image or video
generation. No external image/video provider is used or claimed;
all eight P1-005 provider contracts stay NOT_TESTED.

Asset selection priority (WO §5): (1) locally available licensed
tools, (2) authorized provider adapters, (3) approved
user-supplied assets, (4) external providers only with explicit
authorization (none given in this round — external generation
stays NOT_TESTED).

Generated media is never committed to this repo: the
``.gitignore`` forbids generated media (``*.mp4 *.wav *.png``
...), and the asset policy in ``scripts/asset_policy.py`` keeps
private character/voice data in the private overlay. Generated
assets live in the delivery archive with hashes in the asset
manifest; the repo keeps only the recipes that regenerate them.

This module runs subprocesses (ffmpeg/ffprobe) for generation and
probing, but never calls a provider and never invents an asset.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess

from .media_execution import is_safe_relative_path

ASSET_SCHEMA_VERSION = "2.5"

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
# Shot references use the two-character minimum (``s1``), like the
# project model in runtime.vertical_production.
_REF_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")

ASSET_TYPES = (
    "video-clip",
    "audio-voice",
    "audio-music",
    "audio-sfx",
    "audio-ambience",
    "audio-room-tone",
    "image",
)

# Provider status vocabulary: EXERCISED means a real local run
# produced this asset; NOT_TESTED means the provider was never
# run for it; FAILED means the provider was tried and failed.
PROVIDER_STATUSES = ("EXERCISED", "NOT_TESTED", "FAILED")

LICENSE_CLASSES = (
    "original",
    "licensed",
    "cc-by-nc",
    "unknown",
)

PRIVACY_CLASSES = (
    "public",
    "internal",
    "private",
)

ASSET_STATUSES = (
    "REGISTERED",
    "GENERATED",
    "INGESTED",
    "VERIFIED",
    "FAILED",
)

# Extension -> MIME type for the media this round produces.
_MIME_BY_EXTENSION = {
    ".mp4": "video/mp4",
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".png": "image/png",
    ".jpg": "image/jpeg",
}

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


class AssetError(ValueError):
    """Asset error carrying a list of structured messages."""

    def __init__(self, errors):
        if isinstance(errors, str):
            errors = [errors]
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


def hash_file(path) -> tuple:
    """SHA-256 hex digest and byte size of a file."""
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _contained_path(root: str, rel: str) -> str:
    """Resolve a relative asset path inside a root, refusing escapes."""
    if not is_safe_relative_path(rel):
        raise AssetError(f"asset path {rel!r} is not a safe relative "
                         "path")
    root_real = os.path.realpath(root)
    real = os.path.realpath(os.path.join(root_real, rel))
    if os.path.commonpath([root_real, real]) != root_real:
        raise AssetError(f"asset path {rel!r} escapes the asset root")
    return real


def new_asset_record(*, asset_id, project_id, shot_id=None,
                     asset_type, provider, provider_status,
                     path, mime_type, license_class="original",
                     license_note="", privacy_class="internal",
                     transmit_to_provider=False, provenance,
                     generation=None) -> dict:
    """Build one asset record (status REGISTERED, no file read)."""
    return {
        "schema_version": ASSET_SCHEMA_VERSION,
        "asset_id": asset_id,
        "project_id": project_id,
        "shot_id": shot_id,
        "asset_type": asset_type,
        "source": {
            "provider": provider,
            "provider_status": provider_status,
        },
        "path": path,
        "mime_type": mime_type,
        "size_bytes": None,
        "sha256": None,
        "width": None,
        "height": None,
        "duration_seconds": None,
        "frame_rate": None,
        "sample_rate": None,
        "channels": None,
        "license": {
            "class": license_class,
            "note": license_note,
        },
        "privacy": {
            "classification": privacy_class,
            "transmit_to_provider": transmit_to_provider,
        },
        "status": "REGISTERED",
        "provenance": provenance,
        "generation": generation,
    }


def validate_asset_record(record) -> list:
    """Asset-record errors (empty list = valid). Pure validation."""
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["asset: expected an object, "
                f"got {type(record).__name__}"]
    if record.get("schema_version") != ASSET_SCHEMA_VERSION:
        errors.append("asset.schema_version must be "
                      f"'{ASSET_SCHEMA_VERSION}', got "
                      f"{record.get('schema_version')!r}")
    if not isinstance(record.get("asset_id"), str) \
            or not _ID_RE.match(record["asset_id"]):
        errors.append(f"asset.asset_id {record.get('asset_id')!r} is "
                      "not a valid id")
    if not isinstance(record.get("project_id"), str) \
            or not _ID_RE.match(record["project_id"]):
        errors.append(f"asset.project_id {record.get('project_id')!r} "
                      "is not a valid id")
    if record.get("shot_id") is not None \
            and (not isinstance(record["shot_id"], str)
                 or not _REF_ID_RE.match(record["shot_id"])):
        errors.append(f"asset.shot_id {record.get('shot_id')!r} is "
                      "not a valid id")
    if record.get("asset_type") not in ASSET_TYPES:
        errors.append(f"asset.asset_type {record.get('asset_type')!r} "
                      "is not a known asset type")
    source = record.get("source") or {}
    if not isinstance(source, dict):
        errors.append("asset.source: expected an object")
    else:
        if not isinstance(source.get("provider"), str) \
                or not source["provider"]:
            errors.append("asset.source.provider is missing or not "
                          "a string")
        if source.get("provider_status") not in PROVIDER_STATUSES:
            errors.append("asset.source.provider_status "
                          f"{source.get('provider_status')!r} is not "
                          "a known provider status")
    path = record.get("path")
    if not isinstance(path, str) or not path \
            or not is_safe_relative_path(path):
        errors.append(f"asset.path {path!r} is not a safe relative "
                      "path")
    mime = record.get("mime_type")
    if not isinstance(mime, str) or "/" not in (mime or ""):
        errors.append(f"asset.mime_type {mime!r} is not a MIME type")
    else:
        ext = os.path.splitext(path or "")[1].lower()
        expected = _MIME_BY_EXTENSION.get(ext)
        if expected is not None and mime != expected:
            errors.append(f"asset.mime_type {mime!r} does not match "
                          f"the file extension {ext!r} (expected "
                          f"{expected!r})")
    for field in ("size_bytes",):
        value = record.get(field)
        if value is not None and (not isinstance(value, int)
                                  or isinstance(value, bool)
                                  or value < 0):
            errors.append(f"asset.{field} must be a non-negative "
                          f"integer or null, got {value!r}")
    sha = record.get("sha256")
    if sha is not None and (not isinstance(sha, str)
                            or not _SHA_RE.match(sha)):
        errors.append("asset.sha256 must be a 64-hex digest or null")
    for field in ("width", "height", "sample_rate", "channels"):
        value = record.get(field)
        if value is not None and (not isinstance(value, int)
                                  or isinstance(value, bool)
                                  or value <= 0):
            errors.append(f"asset.{field} must be a positive integer "
                          f"or null, got {value!r}")
    for field in ("duration_seconds", "frame_rate"):
        value = record.get(field)
        if value is not None and (not isinstance(value, (int, float))
                                  or isinstance(value, bool)
                                  or float(value) <= 0):
            errors.append(f"asset.{field} must be a positive number "
                          f"or null, got {value!r}")
    license_ = record.get("license") or {}
    if license_.get("class") not in LICENSE_CLASSES:
        errors.append("asset.license.class "
                      f"{license_.get('class')!r} is not a known "
                      "license class")
    privacy = record.get("privacy") or {}
    if privacy.get("classification") not in PRIVACY_CLASSES:
        errors.append("asset.privacy.classification "
                      f"{privacy.get('classification')!r} is not a "
                      "known privacy class")
    if not isinstance(privacy.get("transmit_to_provider"), bool):
        errors.append("asset.privacy.transmit_to_provider must be a "
                      "boolean")
    if record.get("status") not in ASSET_STATUSES:
        errors.append(f"asset.status {record.get('status')!r} is not "
                      "a known asset status")
    if record.get("provenance") not in (
            "EXPLICIT_FROM_USER", "FROM_APPROVED_PROJECT_CANON",
            "INFERRED_FOR_PRODUCTION", "NEEDS_USER_DECISION"):
        errors.append(f"asset.provenance {record.get('provenance')!r} "
                      "is not a known provenance value")
    return errors


def register_asset(registry, record) -> dict:
    """Register one asset record. Returns a NEW registry dict.

    Refuses a duplicate asset id, and refuses a private asset
    marked for provider transmission without an explicit
    transmission authorization — private data never leaves the
    workspace on an implicit decision.
    """
    errors = validate_asset_record(record)
    if errors:
        raise AssetError(errors)
    if not isinstance(registry, dict):
        raise AssetError("asset registry: expected an object")
    asset_id = record["asset_id"]
    if asset_id in registry:
        raise AssetError(f"asset {asset_id!r} is already registered")
    privacy = record.get("privacy") or {}
    if privacy.get("classification") == "private" \
            and privacy.get("transmit_to_provider") is True \
            and not record.get("transmission_authorization"):
        raise AssetError(
            f"private asset {asset_id!r} is marked for provider "
            "transmission without an explicit transmission "
            "authorization — private data never leaves the "
            "workspace implicitly")
    updated = dict(registry)
    updated[asset_id] = record
    return updated


def resolve_asset(registry, asset_id) -> dict:
    """Resolve one asset id. A missing reference is an error,
    never a substitution."""
    if not isinstance(registry, dict):
        raise AssetError("asset registry: expected an object")
    if asset_id not in registry:
        raise AssetError(f"asset {asset_id!r} cannot be resolved: "
                         "no such registered asset")
    return registry[asset_id]


def check_commercial_delivery(record) -> list:
    """Commercial-delivery blockers for one asset (empty = allowed).

    An unknown license or a CC-BY-NC license blocks commercial
    delivery; the asset may still be used for a non-commercial
    reference production.
    """
    errors: list[str] = []
    license_class = (record.get("license") or {}).get("class")
    if license_class == "unknown":
        errors.append(f"asset {record.get('asset_id')!r} has an "
                      "unknown license: commercial delivery is "
                      "blocked until the license is known")
    if license_class == "cc-by-nc":
        errors.append(f"asset {record.get('asset_id')!r} is CC-BY-NC: "
                      "commercial delivery is blocked")
    return errors


# ------------------------------------------------------------------
# Media probing (shared with the QC stage)
# ------------------------------------------------------------------

def probe_media_file(path, *, ffprobe="ffprobe", timeout_s=120) -> dict:
    """ffprobe metadata for one media file (JSON, stdlib only).

    Returns format name, duration, video width/height/frame-rate
    (as the exact ``avg_frame_rate`` rational string plus the
    float), codec names, and audio stream details. Raises
    :class:`AssetError` when ffprobe is absent or fails.
    """
    if not os.path.isfile(path):
        raise AssetError(f"probe input {path!r} does not exist")
    try:
        proc = subprocess.run(
            [ffprobe, "-v", "error", "-show_format", "-show_streams",
             "-of", "json", path],
            capture_output=True, text=True, timeout=timeout_s)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AssetError(f"ffprobe failed for {path!r}: {exc}") from exc
    if proc.returncode != 0:
        raise AssetError(f"ffprobe failed for {path!r}: "
                         f"{(proc.stderr or proc.stdout or '').strip()[:500]}")
    try:
        data = json.loads(proc.stdout)
    except ValueError as exc:
        raise AssetError(f"ffprobe returned unparseable output for "
                         f"{path!r}") from exc
    metadata: dict = {
        "format_name": (data.get("format") or {}).get(
            "format_name", "unknown"),
        "duration_seconds": None,
        "video_codec": None,
        "audio_codec": None,
        "width": None,
        "height": None,
        "frame_rate": None,
        "frame_rate_rational": None,
        "sample_rate": None,
        "channels": None,
        "audio_streams": [],
    }
    fmt = data.get("format") or {}
    try:
        metadata["duration_seconds"] = float(fmt["duration"]) \
            if fmt.get("duration") else None
    except (TypeError, ValueError):
        metadata["duration_seconds"] = None
    for stream in data.get("streams") or []:
        if stream.get("codec_type") == "video" \
                and metadata["video_codec"] is None:
            metadata["video_codec"] = stream.get("codec_name")
            metadata["width"] = stream.get("width")
            metadata["height"] = stream.get("height")
            rate = str(stream.get("avg_frame_rate") or "")
            metadata["frame_rate_rational"] = rate or None
            if "/" in rate:
                num, den = rate.split("/", 1)
                try:
                    metadata["frame_rate"] = float(num) / float(den) \
                        if float(den) else None
                except (TypeError, ValueError, ZeroDivisionError):
                    metadata["frame_rate"] = None
        elif stream.get("codec_type") == "audio":
            metadata["audio_streams"].append({
                "codec": stream.get("codec_name"),
                "sample_rate": stream.get("sample_rate"),
                "channels": stream.get("channels")})
            if metadata["audio_codec"] is None:
                metadata["audio_codec"] = stream.get("codec_name")
                try:
                    metadata["sample_rate"] = int(
                        stream.get("sample_rate"))
                except (TypeError, ValueError):
                    metadata["sample_rate"] = None
                metadata["channels"] = stream.get("channels")
    return metadata


def verify_asset(record, root, *, ffprobe="ffprobe") -> dict:
    """Verify one asset record against the real file.

    Checks the path stays inside the root, the file exists, the
    byte size and SHA-256 match the record, and — for media — the
    probed width/height/duration/frame-rate/sample-rate/channels
    agree with the record where the record carries them. Returns
    a NEW record with status VERIFIED and the measured values
    filled in. A missing file, a wrong hash, or a probe
    disagreement is an error, never a silent substitution.
    """
    errors = validate_asset_record(record)
    if errors:
        raise AssetError(errors)
    real = _contained_path(root, record["path"])
    if not os.path.isfile(real):
        raise AssetError(f"asset {record['asset_id']!r}: file "
                         f"{record['path']!r} does not exist")
    sha, size = hash_file(real)
    if record.get("size_bytes") is not None \
            and record["size_bytes"] != size:
        raise AssetError(f"asset {record['asset_id']!r}: byte size "
                         f"mismatch (record {record['size_bytes']}, "
                         f"file {size})")
    if record.get("sha256") is not None and record["sha256"] != sha:
        raise AssetError(f"asset {record['asset_id']!r}: SHA-256 "
                         "mismatch — the file changed since it was "
                         "registered")
    verified = dict(record)
    verified["size_bytes"] = size
    verified["sha256"] = sha
    mime = record.get("mime_type") or ""
    if mime.startswith(("video/", "audio/")):
        probe = probe_media_file(real, ffprobe=ffprobe)
        if record.get("width") is not None \
                and probe["width"] != record["width"]:
            raise AssetError(f"asset {record['asset_id']!r}: width "
                             f"mismatch (record {record['width']}, "
                             f"probed {probe['width']})")
        if record.get("height") is not None \
                and probe["height"] != record["height"]:
            raise AssetError(f"asset {record['asset_id']!r}: height "
                             f"mismatch (record {record['height']}, "
                             f"probed {probe['height']})")
        if record.get("duration_seconds") is not None \
                and probe["duration_seconds"] is not None \
                and abs(probe["duration_seconds"]
                        - float(record["duration_seconds"])) > 0.05:
            raise AssetError(f"asset {record['asset_id']!r}: duration "
                             "mismatch (record "
                             f"{record['duration_seconds']}, probed "
                             f"{probe['duration_seconds']})")
        if record.get("frame_rate") is not None \
                and probe["frame_rate"] is not None \
                and abs(probe["frame_rate"]
                        - float(record["frame_rate"])) > 0.01:
            raise AssetError(f"asset {record['asset_id']!r}: frame "
                             "rate mismatch (record "
                             f"{record['frame_rate']}, probed "
                             f"{probe['frame_rate']})")
        verified["width"] = probe["width"]
        verified["height"] = probe["height"]
        verified["duration_seconds"] = probe["duration_seconds"]
        verified["frame_rate"] = probe["frame_rate"]
        verified["sample_rate"] = probe["sample_rate"]
        verified["channels"] = probe["channels"]
    verified["status"] = "VERIFIED"
    return verified


# ------------------------------------------------------------------
# Local visual generation (FFmpeg motion graphics)
# ------------------------------------------------------------------

def visual_argv(recipe, duration_seconds, output_path, *,
                width=1080, height=1920, frame_rate=30,
                crf=20, preset="veryfast") -> list:
    """FFmpeg argument array for one shot's visual recipe.

    Pure function — no subprocess runs. Every recipe kind is an
    animated gradient with a moving accent shape and centred
    keyword text (plus subtext). Durations are explicit: the
    gradients source and ``-t`` both carry the shot duration.
    """
    if not isinstance(recipe, dict):
        raise AssetError("visual recipe: expected an object")
    kind = recipe.get("kind")
    colors = recipe.get("colors") or []
    if len(colors) != 2:
        raise AssetError(f"visual recipe {kind!r} needs exactly two "
                         "gradient colors")
    if not _is_number(duration_seconds) \
            or float(duration_seconds) <= 0:
        raise AssetError("visual duration must be a positive number")
    duration = float(duration_seconds)
    keyword = recipe.get("keyword") or ""
    subtext = recipe.get("subtext") or ""
    text_color = recipe.get("text_color") or "ffffff"
    accent = recipe.get("accent_color") or "ffffff"
    fontsize = recipe.get("fontsize") or 96
    # The gradients source seeds its geometry randomly by default
    # (seed=-1), so two runs of the same recipe produced different
    # files. The seed is fixed (42 unless the recipe says
    # otherwise) so a visual is reproducible byte for byte.
    seed = recipe.get("seed")
    if seed is None:
        seed = 42
    source = (f"gradients=size={width}x{height}:c0={colors[0]}:"
              f"c1={colors[1]}:speed=0.08:seed={int(seed)}:"
              f"duration={duration}")
    filters = []
    if kind == "gradient-band":
        filters.append(
            "drawbox=x=0:y='mod(t*40,h)':w=iw:h=120:"
            f"color={accent}@0.12:t=fill")
    elif kind == "gradient-split":
        filters.append(
            f"drawbox=x='iw/2-3':y=0:w=6:h=ih:color={accent}@0.8:t=fill")
        filters.append(
            "drawbox=x=0:y='mod(t*60,h)':w='iw/2-6':h=100:"
            f"color={accent}@0.10:t=fill")
        filters.append(
            "drawbox=x='iw/2+6':y='h-mod(t*60,h)-100':w='iw/2-6':h=100:"
            f"color={accent}@0.10:t=fill")
    elif kind == "gradient-rings":
        filters.append(
            "drawbox=x='(w-(200+mod(60*t,600)))/2':"
            "y='(h-(200+mod(60*t,600)))/2':"
            "w='200+mod(60*t,600)':h='200+mod(60*t,600)':"
            f"color={accent}@0.25:t=4")
        filters.append(
            "drawbox=x='(w-(500+mod(60*t,600)))/2':"
            "y='(h-(500+mod(60*t,600)))/2':"
            "w='500+mod(60*t,600)':h='500+mod(60*t,600)':"
            f"color={accent}@0.12:t=4")
    elif kind == "gradient-scan":
        filters.append(
            f"drawbox=x=0:y='mod(t*300,h)':w=iw:h=8:color={accent}@0.9:"
            "t=fill")
        filters.append(
            f"drawbox=x=0:y='mod(t*300,h)':w=iw:h=60:color={accent}@0.15:"
            "t=fill")
    elif kind == "gradient-frames":
        for _i, _y in enumerate((500, 850, 1200)):
            filters.append(
                f"drawbox=x='(w-600)/2':y={_y}:w=600:h=280:"
                f"color={accent}@0.5:t=4")
        filters.append(
            "drawbox=x='(w-600)/2':y='500+350*floor(mod(t,3))':w=600:"
            f"h=280:color={accent}@0.10:t=fill")
    elif kind == "gradient-title":
        pass
    else:
        raise AssetError(f"visual recipe kind {kind!r} is not a "
                         "known visual recipe kind")
    if keyword:
        filters.append(
            f"drawtext=fontfile={FONT_PATH}:text='{keyword}':"
            f"fontsize={fontsize}:fontcolor={text_color}:borderw=3:"
            "bordercolor=black:x=(w-text_w)/2:y=(h-text_h)/2-40")
    if subtext:
        filters.append(
            f"drawtext=fontfile={FONT_PATH}:text='{subtext}':"
            f"fontsize=44:fontcolor={text_color}:borderw=2:"
            "bordercolor=black:x=(w-text_w)/2:y=(h-text_h)/2+90")
    filters.append("format=yuv420p")
    return ["ffmpeg", "-y", "-v", "error",
            "-f", "lavfi", "-i", source,
            "-vf", ",".join(filters),
            "-r", str(frame_rate),
            "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
            "-pix_fmt", "yuv420p",
            "-metadata", "creation_time=1970-01-01T00:00:00Z",
            "-t", str(duration), output_path]


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def generate_visual_asset(recipe, duration_seconds, output_path, *,
                          asset_id, project_id, shot_id,
                          ffmpeg="ffmpeg", ffprobe="ffprobe",
                          timeout_s=300) -> dict:
    """Generate one shot clip from a visual recipe and verify it.

    Runs FFmpeg, then probes the output: the clip must be exactly
    the requested geometry (1080x1920, 30 FPS) and duration, or
    the generation is a failure with diagnostics — never a silent
    wrong-geometry asset. Returns the verified asset record.
    """
    argv = visual_argv(recipe, duration_seconds, output_path)
    if argv[0] != ffmpeg:
        argv = [ffmpeg] + argv[1:]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True,
                              timeout=timeout_s)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AssetError(f"visual generation for shot {shot_id!r} "
                         f"failed: {exc}") from exc
    if proc.returncode != 0 or not os.path.isfile(output_path):
        raise AssetError(
            f"visual generation for shot {shot_id!r} failed: "
            f"{(proc.stderr or '').strip()[:500]}")
    probe = probe_media_file(output_path, ffprobe=ffprobe)
    if probe["width"] != 1080 or probe["height"] != 1920:
        raise AssetError(f"visual generation for shot {shot_id!r} "
                         "produced the wrong geometry "
                         f"({probe['width']}x{probe['height']}, "
                         "expected 1080x1920)")
    if probe["frame_rate"] is None \
            or abs(probe["frame_rate"] - 30.0) > 0.01:
        raise AssetError(f"visual generation for shot {shot_id!r} "
                         "produced the wrong frame rate "
                         f"({probe['frame_rate_rational']}, expected "
                         "30/1)")
    if probe["duration_seconds"] is None \
            or abs(probe["duration_seconds"]
                   - float(duration_seconds)) > 0.1:
        raise AssetError(f"visual generation for shot {shot_id!r} "
                         "produced the wrong duration "
                         f"({probe['duration_seconds']}, expected "
                         f"{duration_seconds})")
    try:
        version_proc = subprocess.run(
            [ffmpeg, "-version"], capture_output=True, text=True,
            timeout=30)
        tool_version = (version_proc.stdout.splitlines()[0].strip()
                        if version_proc.returncode == 0
                        and version_proc.stdout else ffmpeg)
    except OSError:
        tool_version = ffmpeg
    sha, size = hash_file(output_path)
    record = new_asset_record(
        asset_id=asset_id, project_id=project_id, shot_id=shot_id,
        asset_type="video-clip", provider="ffmpeg-local",
        provider_status="EXERCISED", path=os.path.basename(output_path),
        mime_type="video/mp4", license_class="original",
        license_note="Generated locally from the project recipe; "
                     "no third-party material.",
        privacy_class="internal", transmit_to_provider=False,
        provenance="INFERRED_FOR_PRODUCTION",
        generation={"tool": "ffmpeg", "tool_version": tool_version,
                    "recipe": recipe,
                    "argv": argv})
    record["size_bytes"] = size
    record["sha256"] = sha
    record["width"] = probe["width"]
    record["height"] = probe["height"]
    record["duration_seconds"] = probe["duration_seconds"]
    record["frame_rate"] = probe["frame_rate"]
    record["status"] = "VERIFIED"
    return record


# ------------------------------------------------------------------
# Still-image animation (CF-WO-P1-006-R1 "ai-still" recipe kind)
# ------------------------------------------------------------------

# Camera motions for animating one still image into a shot clip.
# The motion is a slow, controlled zoompan move — a locally
# animated still, NOT AI-generated video. ``motion_rate`` is the
# zoom change per second (a rate of 0.02 over a 6 s shot is a 12%
# total zoom). Motions are deterministic: same still, same
# parameters, same bytes.
STILL_MOTIONS = (
    "zoom-in",
    "zoom-out",
    "pan-left",
    "pan-right",
    "static",
)


def still_animation_argv(still_path, motion, duration_seconds,
                         output_path, *, motion_rate=0.02,
                         width=1080, height=1920, frame_rate=30,
                         crf=20, preset="veryfast") -> list:
    """FFmpeg argument array animating one still into a shot clip.

    Pure function — no subprocess runs. The still is scaled to
    cover the output geometry (centre-cropped), then a zoompan
    move runs for the whole shot at the output frame rate. The
    clip is exactly the requested geometry and duration.
    """
    if not isinstance(still_path, str) or not still_path:
        raise AssetError("still animation: still_path is missing")
    if motion not in STILL_MOTIONS:
        raise AssetError(
            f"still animation: motion {motion!r} is not a known "
            f"still motion (known: {', '.join(STILL_MOTIONS)})")
    if not _is_number(duration_seconds) \
            or float(duration_seconds) <= 0:
        raise AssetError("still animation: duration must be a "
                         "positive number")
    if not _is_number(motion_rate) or float(motion_rate) < 0:
        raise AssetError("still animation: motion_rate must be a "
                         "non-negative number")
    duration = float(duration_seconds)
    total_frames = max(1, int(round(duration * frame_rate)))
    zoom_span = float(motion_rate) * duration
    if motion == "zoom-in":
        zoom = f"1+{float(motion_rate)}*on/{frame_rate}"
        x_expr = "(iw-iw/zoom)/2"
        y_expr = "(ih-ih/zoom)/2"
    elif motion == "zoom-out":
        zoom = f"{1.0 + zoom_span}-{float(motion_rate)}*on/{frame_rate}"
        x_expr = "(iw-iw/zoom)/2"
        y_expr = "(ih-ih/zoom)/2"
    elif motion == "pan-right":
        zoom = f"{1.0 + zoom_span}"
        x_expr = f"(iw-iw/zoom)*on/{total_frames}"
        y_expr = "(ih-ih/zoom)/2"
    elif motion == "pan-left":
        zoom = f"{1.0 + zoom_span}"
        x_expr = f"(iw-iw/zoom)*(1-on/{total_frames})"
        y_expr = "(ih-ih/zoom)/2"
    else:  # static
        zoom = "1"
        x_expr = "0"
        y_expr = "0"
    filters = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        f"zoompan=z='{zoom}':x='{x_expr}':y='{y_expr}':d=1:"
        f"s={width}x{height}:fps={frame_rate},format=yuv420p")
    return ["ffmpeg", "-y", "-v", "error",
            "-loop", "1", "-framerate", str(frame_rate),
            "-t", str(duration), "-i", still_path,
            "-vf", filters,
            "-r", str(frame_rate),
            "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
            "-pix_fmt", "yuv420p",
            "-metadata", "creation_time=1970-01-01T00:00:00Z",
            "-t", str(duration), output_path]


def generate_still_clip(*, still_path, expected_sha256, motion,
                        motion_rate, duration_seconds, output_path,
                        asset_id, project_id, shot_id,
                        ffmpeg="ffmpeg", ffprobe="ffprobe",
                        timeout_s=300) -> dict:
    """Animate one verified still image into a shot clip and verify it.

    The still's SHA-256 must match ``expected_sha256`` — a still
    that changed since the bible recorded it is refused, never
    animated silently. The clip must be exactly the requested
    geometry (1080x1920, 30 FPS) and duration, or the generation
    is a failure with diagnostics. Returns the verified asset
    record. The record's generation method is honest:
    ``ai-generated-still, locally animated`` — the still came
    from the platform's built-in image generation, the motion is
    FFmpeg zoompan, and this is NOT AI-generated video.
    """
    if not os.path.isfile(still_path):
        raise AssetError(
            f"still animation for shot {shot_id!r}: still file "
            f"{still_path!r} does not exist")
    sha, _size = hash_file(still_path)
    if expected_sha256 is not None and sha != expected_sha256:
        raise AssetError(
            f"still animation for shot {shot_id!r}: still SHA-256 "
            "mismatch — the file changed since it was recorded")
    still_probe = probe_media_file(still_path, ffprobe=ffprobe)
    if still_probe["width"] is None or still_probe["height"] is None:
        raise AssetError(
            f"still animation for shot {shot_id!r}: still file "
            f"{still_path!r} is not a readable image")
    argv = still_animation_argv(
        still_path, motion, duration_seconds, output_path,
        motion_rate=motion_rate)
    if argv[0] != ffmpeg:
        argv = [ffmpeg] + argv[1:]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True,
                              timeout=timeout_s)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AssetError(f"still animation for shot {shot_id!r} "
                         f"failed: {exc}") from exc
    if proc.returncode != 0 or not os.path.isfile(output_path):
        raise AssetError(
            f"still animation for shot {shot_id!r} failed: "
            f"{(proc.stderr or '').strip()[:500]}")
    probe = probe_media_file(output_path, ffprobe=ffprobe)
    if probe["width"] != 1080 or probe["height"] != 1920:
        raise AssetError(f"still animation for shot {shot_id!r} "
                         "produced the wrong geometry "
                         f"({probe['width']}x{probe['height']}, "
                         "expected 1080x1920)")
    if probe["frame_rate"] is None \
            or abs(probe["frame_rate"] - 30.0) > 0.01:
        raise AssetError(f"still animation for shot {shot_id!r} "
                         "produced the wrong frame rate "
                         f"({probe['frame_rate_rational']}, expected "
                         "30/1)")
    if probe["duration_seconds"] is None \
            or abs(probe["duration_seconds"]
                   - float(duration_seconds)) > 0.1:
        raise AssetError(f"still animation for shot {shot_id!r} "
                         "produced the wrong duration "
                         f"({probe['duration_seconds']}, expected "
                         f"{duration_seconds})")
    try:
        version_proc = subprocess.run(
            [ffmpeg, "-version"], capture_output=True, text=True,
            timeout=30)
        tool_version = (version_proc.stdout.splitlines()[0].strip()
                        if version_proc.returncode == 0
                        and version_proc.stdout else ffmpeg)
    except OSError:
        tool_version = ffmpeg
    out_sha, out_size = hash_file(output_path)
    record = new_asset_record(
        asset_id=asset_id, project_id=project_id, shot_id=shot_id,
        asset_type="video-clip", provider="platform-builtin-image",
        provider_status="EXERCISED", path=os.path.basename(output_path),
        mime_type="video/mp4", license_class="original",
        license_note="Still image generated by the platform's "
                     "built-in image generation; motion is local "
                     "FFmpeg zoompan. No third-party material.",
        privacy_class="internal", transmit_to_provider=False,
        provenance="INFERRED_FOR_PRODUCTION",
        generation={"method": "ai-generated-still, locally animated",
                    "still_provider": "platform-builtin-image",
                    "still_sha256": sha,
                    "still_width": still_probe["width"],
                    "still_height": still_probe["height"],
                    "animation_tool": "ffmpeg",
                    "animation_tool_version": tool_version,
                    "motion": motion,
                    "motion_rate": motion_rate,
                    "argv": argv})
    record["size_bytes"] = out_size
    record["sha256"] = out_sha
    record["width"] = probe["width"]
    record["height"] = probe["height"]
    record["duration_seconds"] = probe["duration_seconds"]
    record["frame_rate"] = probe["frame_rate"]
    record["status"] = "VERIFIED"
    return record
