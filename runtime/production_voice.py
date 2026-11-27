"""Consistency Frame P1 — voice stage (CF-WO-P1-006, Phase C).

Turns a validated voice config into verified per-line voice
assets through the VoiceStudio / OmniVoice adapter, and reports
the voice mapping for the delivery package.

Only the controls the bundled OmniVoice engine genuinely
forwards are ever sent: ``instruct``, ``speed`` and ``seed``
(:data:`VOICESTUDIO_SUPPORTED_CONTROLS`). Any other voice
control (emotional delivery, pitch range, pauses, vocal
characteristics, pronunciation preferences) is refused with an
error naming the control — the refusal comes from the adapter
itself in the generation path, never from a re-implementation
of the backend call here. Validation names the control too, so
a bad config fails before any provider is contacted.

Generation never substitutes fake audio: a failed line is
retried exactly once, the failure is recorded in the generation
diagnostics, and a second failure raises. A returned WAV is
verified against its asset record (hash, size, ffprobe probe)
and decoded with the standard-library ``wave`` module before
it is accepted — an empty or all-silent file is a defect, not
an asset.

This module never generates audio itself and never calls a
provider directly: the adapter owns the backend call. Standard
library plus the adapter only.
"""

from __future__ import annotations

import array
import os
import sys

from .media_execution import MediaExecutionError
from .production_assets import (
    AssetError, hash_file, new_asset_record, validate_asset_record,
    verify_asset)
from .vertical_production import _validate_voice_config

# The only voice controls the bundled OmniVoice engine forwards
# (see runtime.media_adapters.VOICESTUDIO_SUPPORTED_VOICE_CONTROLS).
VOICESTUDIO_SUPPORTED_CONTROLS = ("instruct", "speed", "seed")

# Controls the engine cannot honour. They are named precisely
# wherever they are refused, never silently dropped.
UNSUPPORTED_VOICE_CONTROLS = (
    "emotional_delivery",
    "pitch_range",
    "pauses",
    "vocal_characteristics",
    "pronunciation_preferences",
)

VOICE_PROVIDER = "provider-voicestudio-omnivoice"
VOICE_ENGINE = "omnivoice"
VOICE_LICENSE_NOTE = ("OmniVoice default weights CC-BY-NC — "
                      "non-commercial only")


class VoiceError(ValueError):
    """Voice-stage error carrying a list of structured messages.

    ``diagnostics`` (when present) is the generation record for a
    failed line: attempts made and the per-attempt failures, so a
    retry is auditable and a second failure never looks like a
    silent drop.
    """

    def __init__(self, errors, code=None, diagnostics=None):
        if isinstance(errors, str):
            errors = [errors]
        self.errors = list(errors)
        self.code = code
        self.diagnostics = diagnostics
        super().__init__("; ".join(self.errors))


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _control_present(value) -> bool:
    return value is not None and value != "" and value != {}


def _unsupported_control_errors(container, where) -> list:
    """Errors naming every unsupported voice control present."""
    errors: list[str] = []
    if not isinstance(container, dict):
        return errors
    for control in UNSUPPORTED_VOICE_CONTROLS:
        if _control_present(container.get(control)):
            errors.append(
                f"{where}: voice control {control!r} is not "
                "supported by the bundled OmniVoice engine — only "
                f"{', '.join(VOICESTUDIO_SUPPORTED_CONTROLS)} are "
                "forwarded; refusing instead of silently dropping it")
    return errors


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------

def validate_voice_config(config, script_lines) -> list:
    """Voice-config errors (empty list = valid).

    Reuses :func:`vertical_production._validate_voice_config`
    for the structural checks (voice id, language, engine,
    provider, commercial use, seed, instruct, line coverage)
    and the byte-for-byte verbatim text check against the
    script lines, then adds the Phase C rules: ``speed`` — when
    present — must be a number in [0.5, 2.0], and any
    unsupported voice control is refused with an error naming
    the control.
    """
    errors: list[str] = []
    if not isinstance(script_lines, list):
        return ["script_lines: expected a list, got "
                f"{type(script_lines).__name__}"]
    errors.extend(_validate_voice_config(config, script_lines))
    if not isinstance(config, dict):
        return errors
    errors.extend(_unsupported_control_errors(config, "voice_config"))
    speed = config.get("speed")
    if speed is not None and (not _is_number(speed)
                              or not 0.5 <= float(speed) <= 2.0):
        errors.append(f"voice_config.speed must be a number in "
                      f"[0.5, 2.0], got {speed!r}")
    for index, line in enumerate(config.get("lines") or []):
        where = f"voice_config.lines[{index}]"
        if not isinstance(line, dict):
            continue
        errors.extend(_unsupported_control_errors(line, where))
    return errors


# ------------------------------------------------------------------
# Line -> asset mapping
# ------------------------------------------------------------------

def voice_line_assets(config) -> list:
    """Per-line voice asset specs, in config order.

    Each entry carries the line id, shot id, asset id
    (``voice-<line_id>``), verbatim text, language, seed,
    instruct tag and pause-after value from the config, plus
    the ``voice_id`` and ``speed`` the generation step needs to
    build the adapter packet. Raises :class:`VoiceError` when
    the config has no usable lines list.
    """
    if not isinstance(config, dict):
        raise VoiceError("voice_config: expected an object, got "
                         f"{type(config).__name__}")
    lines = config.get("lines")
    if not isinstance(lines, list) or not lines:
        raise VoiceError("voice_config.lines must be a non-empty "
                         "list")
    pause_after = config.get("pause_after_seconds", 0.0)
    specs = []
    for line in lines:
        if not isinstance(line, dict):
            raise VoiceError("voice_config.lines entries must be "
                             "objects")
        line_id = line.get("line_id")
        specs.append({
            "line_id": line_id,
            "shot_id": line.get("shot_id"),
            "asset_id": f"voice-{line_id}",
            "text": line.get("text"),
            "language": config.get("language"),
            "seed": config.get("seed"),
            "instruct": config.get("instruct"),
            "pause_after_seconds": pause_after,
            "voice_id": config.get("voice_id"),
            "speed": config.get("speed", 1.0),
        })
    return specs


# ------------------------------------------------------------------
# Generation (Phase C, through the adapter only)
# ------------------------------------------------------------------

def _project_id_for(line, session):
    """Project id for a line: the line first, then the session."""
    project_id = None
    if isinstance(line, dict):
        project_id = line.get("project_id")
    if not project_id and isinstance(session, dict):
        project_id = session.get("project_id")
    if not project_id and session is not None:
        project_id = getattr(session, "project_id", None)
    return project_id


def _build_packet(line):
    """Adapter packet for one line, plus the adapter context.

    Unsupported controls present on the line are passed through
    into the binding on purpose: the adapter's translate refuses
    them with a precise error, and this module never decides on
    its own to drop a control the caller asked for.
    """
    binding = {
        "dialogue_text": line.get("text"),
        "language": line.get("language"),
        "voice_profile_id": line.get("voice_profile_id")
        or line.get("voice_id"),
        "seed": line.get("seed"),
        "dialogue_line_id": line.get("line_id"),
    }
    speed = line.get("speaking_pace", line.get("speed"))
    if speed is not None:
        binding["speaking_pace"] = speed
    for control in UNSUPPORTED_VOICE_CONTROLS:
        if _control_present(line.get(control)):
            binding[control] = line[control]
    packet = {
        "task_type": "voice-generation",
        "canonical_instruction": line.get("text") or "",
        "voice_binding": binding,
    }
    context = {}
    instruct = line.get("instruct")
    if isinstance(instruct, str) and instruct != "":
        context["instruct"] = instruct
    return packet, context


def generate_voice_line(adapter, session, line, *, workspace_root,
                        execution_id) -> dict:
    """Generate one dialogue line and return its verified record.

    Builds the adapter packet from ``line`` (see
    :func:`voice_line_assets`), calls ``adapter.translate`` then
    ``adapter.submit``, and verifies the returned WAV with
    :func:`production_assets.verify_asset` against a record
    built with :func:`production_assets.new_asset_record`
    (type ``audio-voice``, provider
    ``provider-voicestudio-omnivoice``, status EXERCISED, CC-BY-NC
    licence, internal privacy, ``INFERRED_FOR_PRODUCTION``
    provenance). The record's path is relative to
    ``workspace_root``.

    On a :class:`MediaExecutionError` the submission is retried
    exactly once; the first failure is recorded in the returned
    record's generation diagnostics. A second failure raises
    :class:`VoiceError` carrying the generation diagnostics
    (attempts and per-attempt failures) — no fake audio is ever
    substituted. An unsupported voice control is refused by the
    adapter's translate and raises the same way.
    """
    if not isinstance(line, dict):
        raise VoiceError("voice line: expected an object, got "
                         f"{type(line).__name__}")
    line_id = line.get("line_id")
    if not isinstance(line_id, str) or not line_id:
        raise VoiceError("voice line carries no line_id")
    if not isinstance(line.get("text"), str) or not line["text"]:
        raise VoiceError(f"voice line {line_id!r} carries no "
                         "dialogue text")
    voice_profile_id = line.get("voice_profile_id") or line.get(
        "voice_id")
    if not voice_profile_id:
        raise VoiceError(f"voice line {line_id!r} carries no voice "
                         "profile id (voice_id)")
    project_id = _project_id_for(line, session)
    if not project_id:
        raise VoiceError(f"voice line {line_id!r} carries no "
                         "project_id")
    asset_id = line.get("asset_id") or f"voice-{line_id}"
    packet, context = _build_packet(line)
    context["execution_id"] = execution_id
    failures: list[dict] = []
    result = None
    for attempt in (1, 2):
        try:
            request = adapter.translate(packet, context)
            result = adapter.submit(request, context)
            break
        except MediaExecutionError as exc:
            failures.append({
                "attempt": attempt,
                "code": exc.code,
                "errors": list(exc.errors),
            })
            if attempt == 2:
                diagnostics = {
                    "tool": "voicestudio-omnivoice",
                    "tool_version": getattr(
                        adapter, "adapter_version", "unknown"),
                    "seed": line.get("seed"),
                    "instruct": line.get("instruct"),
                    "attempts": 2,
                    "failures": failures,
                }
                raise VoiceError(
                    [f"voice line {line_id!r} failed twice: "
                     + "; ".join(exc.errors)],
                    code=exc.code, diagnostics=diagnostics) from exc
    if not isinstance(result, dict) or not result.get("completed"):
        raise VoiceError(
            f"voice line {line_id!r}: the adapter did not complete "
            "the generation synchronously — no audio was produced",
            diagnostics={"tool": "voicestudio-omnivoice",
                         "tool_version": getattr(
                             adapter, "adapter_version", "unknown"),
                         "seed": line.get("seed"),
                         "instruct": line.get("instruct"),
                         "attempts": len(failures) + 1,
                         "failures": failures})
    output = result.get("output") or {}
    rel_path = output.get("path")
    if not isinstance(rel_path, str) or not rel_path:
        raise VoiceError(f"voice line {line_id!r}: the adapter "
                         "returned no output path")
    provider_audio_id = output.get("provider_audio_id") \
        or result.get("provider_job_id")
    generation = {
        "tool": "voicestudio-omnivoice",
        "tool_version": getattr(adapter, "adapter_version",
                                "unknown"),
        "seed": line.get("seed"),
        "instruct": line.get("instruct"),
        "attempts": len(failures) + 1,
        "provider_audio_id": provider_audio_id,
    }
    if failures:
        generation["failures"] = failures
    record = new_asset_record(
        asset_id=asset_id, project_id=project_id,
        shot_id=line.get("shot_id"), asset_type="audio-voice",
        provider=VOICE_PROVIDER, provider_status="EXERCISED",
        path=rel_path, mime_type="audio/wav",
        license_class="cc-by-nc", license_note=VOICE_LICENSE_NOTE,
        privacy_class="internal", transmit_to_provider=False,
        provenance="INFERRED_FOR_PRODUCTION",
        generation=generation)
    return verify_asset(record, workspace_root)


# ------------------------------------------------------------------
# Verification
# ------------------------------------------------------------------

def _asset_line_id(record) -> str | None:
    """Dialogue line id for an asset record.

    The record may carry ``line_id`` directly; otherwise the
    asset id ``voice-<line_id>`` is the binding.
    """
    if not isinstance(record, dict):
        return None
    line_id = record.get("line_id")
    if isinstance(line_id, str) and line_id:
        return line_id
    asset_id = record.get("asset_id") or ""
    if asset_id.startswith("voice-") and len(asset_id) > 6:
        return asset_id[len("voice-"):]
    return None


def _wav_info(path) -> dict:
    """Decode a WAV with the standard library.

    Returns duration, sample rate, channels and the maximum
    absolute sample value. Raises ``ValueError`` when the file
    is not a decodable WAV, has no frames, or is all silence.
    """
    import wave

    with wave.open(path, "rb") as wav:
        channels = wav.getnchannels()
        rate = wav.getframerate()
        width = wav.getsampwidth()
        frames = wav.getnframes()
        if channels < 1:
            raise ValueError(f"{path!r} has no audio channels")
        if rate <= 0:
            raise ValueError(f"{path!r} has no sample rate")
        if frames <= 0:
            raise ValueError(f"{path!r} has 0 frames: empty audio")
        raw = wav.readframes(frames)
    if width == 1:
        peak = max((abs(byte - 128) for byte in raw), default=0)
        scale = 128.0
    elif width == 2:
        samples = array.array("h")
        samples.frombytes(raw)
        if sys.byteorder == "big":
            samples.byteswap()
        peak = max((abs(int(s)) for s in samples), default=0)
        scale = 32768.0
    elif width == 4:
        samples = array.array("i")
        samples.frombytes(raw)
        if sys.byteorder == "big":
            samples.byteswap()
        peak = max((abs(int(s)) for s in samples), default=0)
        scale = 2147483648.0
    elif width == 3:
        peak = 0
        for offset in range(0, len(raw) - 2, 3):
            value = int.from_bytes(raw[offset:offset + 3],
                                   "little", signed=True)
            peak = max(peak, abs(value))
        scale = 8388608.0
    else:
        raise ValueError(f"{path!r} has unsupported sample width "
                         f"{width}")
    if peak <= 0:
        raise ValueError(f"{path!r} is all silence (max absolute "
                         "sample is 0): empty audio")
    return {
        "duration_seconds": frames / rate,
        "sample_rate": rate,
        "channels": channels,
        "peak_normalized": peak / scale,
    }


def verify_voice_assets(lines, assets, root, *,
                        ffprobe="ffprobe") -> tuple:
    """Verify voice assets against their dialogue lines.

    Returns ``(errors, report)``. Every line must have exactly
    one asset — a missing line, a duplicate line asset, and an
    asset naming an unknown line are all errors. Each asset file
    must exist, be decodable as a WAV (channels >= 1, sample
    rate > 0, frames > 0), carry a known duration, and contain
    non-silent audio (max absolute sample > 0). Each record is
    also checked with :func:`production_assets.verify_asset`
    (hash / size / ffprobe probe where applicable), so a wrong
    hash fails here. No required dialogue may be missing and no
    accidental duplicate line is accepted.

    ``report`` is ``{lines_checked, total_duration_seconds,
    per_line: [{line_id, asset_id, duration_seconds,
    sample_rate, channels}]}``.
    """
    errors: list[str] = []
    per_line: list[dict] = []
    total = 0.0
    if not isinstance(lines, list):
        return (["voice lines: expected a list"], {
            "lines_checked": 0, "total_duration_seconds": 0.0,
            "per_line": []})
    if not isinstance(assets, list):
        return (["voice assets: expected a list"], {
            "lines_checked": len(lines),
            "total_duration_seconds": 0.0, "per_line": []})
    expected_ids = []
    for line in lines:
        if isinstance(line, dict) and line.get("line_id"):
            expected_ids.append(line["line_id"])
    by_line: dict[str, list] = {}
    for record in assets:
        line_id = _asset_line_id(record)
        if line_id is None:
            errors.append(
                f"voice asset {record.get('asset_id')!r} names no "
                "dialogue line (expected asset id "
                "'voice-<line_id>')")
            continue
        by_line.setdefault(line_id, []).append(record)
    for line_id in expected_ids:
        group = by_line.get(line_id, [])
        if not group:
            errors.append(f"voice line {line_id!r} has no voice "
                          "asset: required dialogue is missing")
            continue
        if len(group) > 1:
            errors.append(
                f"voice line {line_id!r} has {len(group)} voice "
                "assets: accidental duplicate line")
            continue
        record = group[0]
        asset_id = record.get("asset_id")
        entry = {"line_id": line_id, "asset_id": asset_id,
                 "duration_seconds": None, "sample_rate": None,
                 "channels": None}
        per_line.append(entry)
        record_errors = validate_asset_record(record)
        if record_errors:
            errors.extend(
                f"voice asset {asset_id!r}: {err}"
                for err in record_errors)
            continue
        real = os.path.join(root, record["path"])
        if not os.path.isfile(real):
            errors.append(f"voice asset {asset_id!r}: file "
                          f"{record['path']!r} does not exist")
            continue
        try:
            info = _wav_info(real)
        except (ValueError, EOFError, OSError) as exc:
            errors.append(f"voice asset {asset_id!r}: {exc}")
            continue
        entry["duration_seconds"] = round(
            info["duration_seconds"], 6)
        entry["sample_rate"] = info["sample_rate"]
        entry["channels"] = info["channels"]
        total += info["duration_seconds"]
        try:
            verify_asset(record, root, ffprobe=ffprobe)
        except AssetError as exc:
            errors.extend(
                f"voice asset {asset_id!r}: {err}"
                for err in exc.errors)
    for line_id in sorted(by_line):
        if line_id not in expected_ids:
            errors.append(
                f"voice asset for line {line_id!r} has no dialogue "
                "line in the voice config: unexpected asset")
    return (errors, {
        "lines_checked": len(expected_ids),
        "total_duration_seconds": round(total, 6),
        "per_line": per_line})


# ------------------------------------------------------------------
# Delivery mapping
# ------------------------------------------------------------------

def voice_mapping_report(lines, assets) -> dict:
    """Voice mapping for the delivery package.

    ``{voice_id, language, seed, instruct, lines: [{line_id,
    shot_id, asset_id, text, duration_seconds, sha256}]}``.
    Durations and hashes are taken from the verified asset
    records. Raises :class:`VoiceError` when there are no lines
    or when a line has no verified asset — a delivery package
    never silently omits a voice line.
    """
    if not isinstance(lines, list) or not lines:
        raise VoiceError("voice mapping needs at least one voice "
                         "line")
    if not isinstance(assets, list):
        raise VoiceError("voice mapping needs an asset list")
    by_asset_id = {}
    for record in assets:
        if isinstance(record, dict) and record.get("asset_id"):
            by_asset_id[record["asset_id"]] = record
    first = lines[0] if isinstance(lines[0], dict) else {}
    mapped = []
    for line in lines:
        if not isinstance(line, dict):
            raise VoiceError("voice mapping lines must be objects")
        line_id = line.get("line_id")
        asset_id = line.get("asset_id") or f"voice-{line_id}"
        record = by_asset_id.get(asset_id)
        if record is None:
            raise VoiceError(
                f"voice mapping: line {line_id!r} has no verified "
                f"asset {asset_id!r}")
        mapped.append({
            "line_id": line_id,
            "shot_id": line.get("shot_id"),
            "asset_id": asset_id,
            "text": line.get("text"),
            "duration_seconds": record.get("duration_seconds"),
            "sha256": record.get("sha256"),
        })
    return {
        "voice_id": first.get("voice_id")
        or first.get("voice_profile_id"),
        "language": first.get("language"),
        "seed": first.get("seed"),
        "instruct": first.get("instruct"),
        "lines": mapped,
    }


__all__ = [
    "VOICESTUDIO_SUPPORTED_CONTROLS",
    "UNSUPPORTED_VOICE_CONTROLS",
    "VoiceError",
    "validate_voice_config",
    "voice_line_assets",
    "generate_voice_line",
    "verify_voice_assets",
    "voice_mapping_report",
]
