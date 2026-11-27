"""Consistency Frame P1 — concrete media execution adapters
(CF-WO-P1-005).

One adapter per provider, all behind
:class:`runtime.media_execution.MediaAdapter`. Adapters translate a
compiled task packet into a real provider request, submit it, poll
async jobs, retrieve outputs and verify them. They never invent a
result: every method fails closed with
:class:`runtime.media_execution.MediaExecutionError`.

Local adapters (real tools in this repository):

- :class:`FFmpegAdapter` — ffprobe probing, safe-argv transcode /
  assembly / export, SHA-256 integrity. Technical operations only;
  no creative-editing judgement is claimed.
- :class:`VoiceStudioAdapter` — safe wrapper around the bundled
  VoiceStudio backend (``POST /generate``, ``GET /health``). The
  backend's internals are never modified. Preflight verifies the
  service, engine/model, language, voice-profile identity, consent
  and commercial eligibility before any task. The default
  OmniVoice weights are CC-BY-NC: commercial/monetized production
  is refused outright.
- :class:`OpenMontageAdapter` — thin wrapper around the bundled
  OpenMontage checkout. Preflight verifies the component checkout
  (origin + HEAD pin, the P0-014 pattern) and runs ``make
  preflight``; submit runs only the verified render entry
  (``render_demo.py`` for a named demo composition) and verifies
  the output files. Production assembly is NOT claimed EXERCISED
  until a real production output is generated and independently
  validated.
- :func:`probe_opentimelineio` — OpenTimelineIO is not installed
  in this environment, and the canonical timeline manifest already
  covers editorial interchange, so no OTIO adapter is built; the
  probe reports it unavailable and any use is refused fail-closed.

External adapters (WO §6): :class:`HttpProviderAdapter` is a
mockable HTTP lifecycle adapter driven by one declarative spec per
live provider (endpoint, auth, async pattern, cancellation,
retrieval, charge behaviour). Every outbound URL is validated by
the provider URL security policy
(:mod:`runtime.provider_url_policy`): explicit per-provider API
and output origin allowlists, no IP-literal or private/loopback
destination, every redirect hop validated, authorization headers
never forwarded across origins, and the default transport pins
the connection to a validated resolved address (DNS-rebinding
protection against this client; see the policy module for the
exact boundary). Specs come from the current official provider
documentation audited 2026-11-27 (see
``docs/runtime/PROVIDER_ADAPTERS.md`` and the provider registry);
Sora has no adapter — the service was shut down 2026-09-24 and
its registry record is FAILED, so it is never matched. No live
paid call is made in this round: tests use a mock transport, and
providers stay NOT_TESTED until real evidence exists.

Credentials: secrets are read only from an allow-listed
environment variable per provider
(:func:`resolve_provider_secret`); they never appear in Git,
logs, reports, packets or error messages. No paid external API
call is made without explicit user authorization.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import wave

from .media_execution import (
    FAILURE_CODES, MediaAdapter, MediaExecutionError)
from .provider_contracts import get_contract
from .provider_url_policy import (
    AUTH_HEADER_NAMES, MAX_DOWNLOAD_BYTES, MAX_RESPONSE_BYTES,
    ProviderURLPolicy, safe_url_for_message,
    validate_endpoint_segment, validate_model_id,
    validate_provider_job_id)

# Canonical component pins (setup.sh). The adapters verify the
# installed checkout against these; a mismatch fails closed.
VOICESTUDIO_ORIGIN = "https://github.com/debpalash/VoiceStudio"
VOICESTUDIO_PIN = "2f2f5a9b0e982c6147efc6baaeae62936f29b79b"
OPENMONTAGE_ORIGIN = "https://github.com/OpenMontageInc/OpenMontage"
OPENMONTAGE_PIN = "fecb9a1e3cc23ef84de30b272059457a427f16f8"

VOICESTUDIO_DEFAULT_BASE_URL = "http://127.0.0.1:3900"

# Languages the bundled OmniVoice engine demonstrably speaks in
# this account (demo runs 2026-11-12/13: Bengali, English, Hindi).
# A packet naming another language fails preflight instead of
# silently falling back to a wrong language.
OMNIVOICE_LANGUAGES = ("bn", "en", "hi")

# VoiceStudio /generate capability map (CF-WO-P1-005-R4, workstream
# D), verified against the BUNDLED backend in
# components/voicestudio (audit 2026-11-27; the adapter never
# modifies VoiceStudio internals). The backend's /generate
# endpoint accepts: text, language, ref_audio, ref_text,
# instruct, design_recipe, duration, num_step, guidance_scale,
# speed (float, default 1.0), t_shift, denoise,
# postprocess_output, layer_penalty_factor,
# position_temperature, class_temperature, emo_text, emo_vector,
# emotion (max 200 chars), profile_id, seed, effect_preset,
# wav_bits, engine, preset_voice, max_chunk_chars, crossfade_ms,
# pronounce, stream. It has NO pitch field and NO pauses field.
# For the adapter's engine (omnivoice): instruct_vocabulary is
# "tags" (fixed English tags only), supports_emotion is False so
# emotion control is "none" and apply_span_emotion IGNORES the
# emotion, and supports_voice_design applies only when no
# reference audio is used — this adapter always sends profile
# reference audio. So of the voice-binding controls, only
# instruct (from the execution context) and a numeric speaking
# pace (as speed) are genuinely forwarded; the rest are refused
# with a precise capability error instead of being silently
# dropped. The supported list is what the registry advertises
# (schemas/provider-capability.json: voice_controls).
VOICESTUDIO_SUPPORTED_VOICE_CONTROLS = ("instruct", "speed", "seed")
VOICESTUDIO_UNSUPPORTED_VOICE_CONTROLS = {
    "emotional_delivery":
        "the bundled OmniVoice engine has no emotion control "
        "(supports_emotion is False); the backend accepts an "
        "emotion field but it has no effect on this engine",
    "pitch_range":
        "the /generate endpoint has no pitch field",
    "pauses":
        "the /generate endpoint has no pauses field",
    "vocal_characteristics":
        "voice design applies only when no reference audio is "
        "used; this adapter always sends profile reference audio, "
        "so vocal characteristics cannot be forwarded",
    "pronunciation_preferences":
        "the backend pronounce flag applies a stored user "
        "pronunciation dictionary, not per-request free-text "
        "preferences",
}


def _voice_control_present(value) -> bool:
    """True when a voice control carries a value to forward."""
    return value is not None and value != "" and value != {}


def _parse_voice_speed(value):
    """Numeric speed for a speaking_pace value, or None.

    Accepts a finite positive number, or a string parsing to
    one. Descriptive labels ("natural", "slow") have no
    documented numeric mapping and return None — they are
    refused, never guessed.
    """
    import math
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError:
            return None
    else:
        return None
    if not math.isfinite(number) or number <= 0:
        return None
    return number


def _voice_control_errors(binding, context) -> list:
    """Capability errors for unsupported voice controls.

    Every control the binding asks for that the bundled
    OmniVoice engine cannot honour is an error here — the
    adapter refuses instead of silently dropping it. A
    descriptive speaking_pace with no numeric mapping is an
    error too, and a non-string instruct is one.
    """
    errors: list[str] = []
    binding = binding or {}
    context = context or {}
    for field, reason in \
            VOICESTUDIO_UNSUPPORTED_VOICE_CONTROLS.items():
        if _voice_control_present(binding.get(field)):
            errors.append(
                f"voice control {field!r} is not supported by the "
                f"bundled OmniVoice engine: {reason}")
    pace = binding.get("speaking_pace")
    if _voice_control_present(pace) and _parse_voice_speed(pace) is None:
        errors.append(
            "voice control 'speaking_pace' "
            f"{pace!r} cannot be mapped to a numeric speed: the "
            "bundled OmniVoice engine accepts a speed number only, "
            "and no documented mapping exists for descriptive "
            "pace labels")
    instruct = context.get("instruct")
    if instruct is not None and not isinstance(instruct, str):
        errors.append(
            "voice control 'instruct' must be a string of fixed "
            "backend tags, not "
            f"{type(instruct).__name__}")
    return errors

# Allow-listed credential environment variables, one per external
# provider. No other variable is ever read as a secret.
PROVIDER_SECRET_ENV = {
    "provider-openai-image": "OPENAI_API_KEY",
    "provider-gemini-image": "GEMINI_API_KEY",
    "provider-fal-image": "FAL_KEY",
    "provider-veo-video": "VERTEX_ACCESS_TOKEN",
    "provider-kling-video": "KLING_API_KEY",
    "provider-ltx-video": "LTX_API_KEY",
    "provider-elevenlabs-voice": "ELEVENLABS_API_KEY",
    "provider-lyria-music": "GEMINI_API_KEY",
}

_MAX_ERROR_TEXT = 2000
_DEFAULT_TIMEOUT_S = 120
_DEFAULT_MAX_OUTPUT_BYTES = 2 * 1024 * 1024 * 1024  # 2 GiB


def _redact(text: str, secrets=(), limit=_MAX_ERROR_TEXT) -> str:
    """Strip secrets, home and workspace paths from error text.

    ``limit`` caps the returned text (error messages stay short);
    pass ``None`` for full tool output, where truncation would
    corrupt structured data such as ffprobe JSON.
    """
    out = text or ""
    for secret in secrets:
        if secret:
            out = out.replace(secret, "[redacted]")
    home = os.path.expanduser("~")
    if home:
        out = out.replace(home, "~")
    if limit is None:
        return out
    return out[:limit]


def _sha256_file(path: str) -> tuple:
    """(sha256 hex, byte count) of a file."""
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _contained_path(root: str, path: str) -> str:
    """Resolve ``path`` under ``root``; refuse escapes and symlinks out."""
    if not isinstance(root, str) or not root:
        raise MediaExecutionError("workspace root is required")
    if not isinstance(path, str) or not path:
        raise MediaExecutionError("path must be a non-empty string")
    if os.path.isabs(path):
        candidate = os.path.realpath(path)
    else:
        candidate = os.path.realpath(os.path.join(root, path))
    root_real = os.path.realpath(root)
    if candidate != root_real and not candidate.startswith(
            root_real + os.sep):
        raise MediaExecutionError(
            f"path {path!r} escapes the workspace root")
    return candidate


_REFERENCE_MIME_BY_EXT = {
    ".png": "image/png", ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg", ".webp": "image/webp",
    ".wav": "audio/wav", ".mp3": "audio/mpeg",
}


def _normalize_reference(root: str, value, field: str) -> dict:
    """Normalize one context reference to ``{"mime", "base64"}``.

    Accepts the already-loaded form or ``{"path"}`` (a
    workspace-contained file, read here — references never travel
    as bytes inside a task packet). Anything else fails closed.
    """
    import base64

    if not isinstance(value, dict):
        raise MediaExecutionError(
            f"{field} must be an object with mime/base64 or path")
    if isinstance(value.get("base64"), str) \
            and isinstance(value.get("mime"), str):
        return {"mime": value["mime"], "base64": value["base64"]}
    path = value.get("path")
    if not isinstance(path, str) or not path:
        raise MediaExecutionError(
            f"{field} needs mime/base64 or a workspace path")
    real = _contained_path(root, path)
    ext = os.path.splitext(real)[1].lower()
    mime = _REFERENCE_MIME_BY_EXT.get(ext)
    if mime is None:
        raise MediaExecutionError(
            f"{field} file type {ext!r} is not a supported "
            "reference type")
    with open(real, "rb") as handle:
        raw = handle.read()
    return {"mime": mime,
            "base64": base64.b64encode(raw).decode("ascii")}


def _normalize_references(root: str, context) -> dict:
    """Return a copy of ``context`` with reference entries loaded.

    ``reference_images`` (a list), ``first_frame``,
    ``last_frame`` and ``reference_audio`` (single entries) are
    normalized; every other context key passes through
    unchanged. The provider contract then validates counts,
    mimes and sizes for its own provider.
    """
    context = dict(context or {})
    refs = context.get("reference_images")
    if refs is not None:
        if not isinstance(refs, list):
            raise MediaExecutionError(
                "reference_images must be a list")
        context["reference_images"] = [
            _normalize_reference(root, ref, "reference_images")
            for ref in refs]
    for key in ("first_frame", "last_frame", "reference_audio"):
        if context.get(key) is not None:
            context[key] = _normalize_reference(
                root, context[key], key)
    return context


def _run_argv(argv, *, timeout_s, secrets=(), cwd=None) -> tuple:
    """Run a safe argument array (never an interpolated shell string).

    Returns ``(returncode, stdout, stderr)``. A timeout or a
    spawn failure raises MediaExecutionError with code
    ``local-tool-error`` and redacted text.
    """
    if not argv or not isinstance(argv[0], str):
        raise MediaExecutionError("cannot run an empty command")
    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout_s,
            errors="replace", cwd=cwd)
    except subprocess.TimeoutExpired:
        raise MediaExecutionError(
            f"command timed out after {timeout_s}s: "
            f"{argv[0]} (arguments withheld)",
            code="local-tool-error")
    except OSError as exc:
        raise MediaExecutionError(
            f"cannot run {argv[0]}: {_redact(str(exc), secrets)}",
            code="local-tool-error")
    # Full stdout/stderr: truncation here would corrupt structured
    # tool output (ffprobe JSON). Callers redact + truncate again
    # when they embed output in an error message.
    return (proc.returncode,
            _redact(proc.stdout or "", secrets, limit=None),
            _redact(proc.stderr or "", secrets, limit=None))


def resolve_provider_secret(provider_id: str) -> str:
    """Read a provider credential from its allow-listed env var.

    Raises MediaExecutionError with code ``credential-missing``
    when the variable is absent or empty. The value is returned
    only to the caller that sends it; it is never logged.
    """
    env_var = PROVIDER_SECRET_ENV.get(provider_id)
    if env_var is None:
        raise MediaExecutionError(
            f"provider {provider_id!r} has no allow-listed "
            "credential variable",
            code="credential-missing")
    value = os.environ.get(env_var)
    if not value:
        raise MediaExecutionError(
            f"credential for {provider_id!r} is missing: set "
            f"{env_var} (never commit it)",
            code="credential-missing")
    return value


def probe_opentimelineio() -> dict:
    """Report whether OpenTimelineIO is available in this environment.

    It is not installed here, and the canonical timeline manifest
    already covers editorial interchange, so no OTIO adapter is
    built and OTIO is never a mandatory dependency.
    """
    try:
        import opentimelineio  # noqa: F401
    except Exception as exc:  # noqa: BLE001 - availability probe
        return {"installed": False,
                "reason": f"import opentimelineio failed: {exc}"}
    import opentimelineio as otio
    return {"installed": True,
            "version": getattr(otio, "__version__", "unknown")}


class FFmpegAdapter(MediaAdapter):
    """Local FFmpeg / ffprobe adapter (provider-ffmpeg).

    Technical media operations only: probe, transcode, assembly
    (concat), export. The adapter never claims creative editing
    judgement. All commands run as safe argument arrays with a
    timeout and an output size limit; inputs and outputs must stay
    inside the authorized workspace root.
    """

    adapter_id = "adapter-ffmpeg"
    provider_id = "provider-ffmpeg"
    adapter_version = "8.1.2"

    def __init__(self, *, workspace_root, ffmpeg="ffmpeg",
                 ffprobe="ffprobe", timeout_s=_DEFAULT_TIMEOUT_S,
                 max_output_bytes=_DEFAULT_MAX_OUTPUT_BYTES):
        self.workspace_root = workspace_root
        self.ffmpeg = ffmpeg
        self.ffprobe = ffprobe
        self.timeout_s = timeout_s
        self.max_output_bytes = max_output_bytes
        self._version = None

    def capabilities(self) -> dict:
        return {
            "operations": ["probe-media", "transcode-media",
                           "assemble-timeline"],
            "task_types": ["media-technical"],
        }

    def binary_version(self) -> str:
        """Recorded ffmpeg binary version (first line of -version)."""
        if self._version is None:
            if shutil.which(self.ffmpeg) is None:
                raise MediaExecutionError(
                    f"ffmpeg binary {self.ffmpeg!r} not found",
                    code="local-tool-error")
            code, out, _err = _run_argv(
                [self.ffmpeg, "-version"], timeout_s=30)
            if code != 0 or not out:
                raise MediaExecutionError(
                    "ffmpeg -version failed",
                    code="local-tool-error")
            self._version = out.splitlines()[0].strip()
        return self._version

    def preflight(self, packet, context) -> list:
        errors = super().preflight(packet, context)
        if shutil.which(self.ffmpeg) is None:
            errors.append(f"ffmpeg binary {self.ffmpeg!r} not found")
        if shutil.which(self.ffprobe) is None:
            errors.append(f"ffprobe binary {self.ffprobe!r} not found")
        if not os.path.isdir(self.workspace_root):
            errors.append("ffmpeg workspace root "
                          f"{self.workspace_root!r} is not a directory")
        operation = (context or {}).get("ffmpeg_operation") or {}
        if operation.get("operation") not in (
                "probe", "transcode", "assemble"):
            errors.append("ffmpeg context needs ffmpeg_operation "
                          "one of probe/transcode/assemble")
        return errors

    def probe(self, path: str) -> dict:
        """ffprobe metadata for one media file (JSON)."""
        real = _contained_path(self.workspace_root, path)
        if not os.path.isfile(real):
            raise MediaExecutionError(
                f"probe input {path!r} does not exist",
                code="local-tool-error")
        if shutil.which(self.ffprobe) is None:
            raise MediaExecutionError(
                f"ffprobe binary {self.ffprobe!r} not found",
                code="local-tool-error")
        code, out, err = _run_argv(
            [self.ffprobe, "-v", "error", "-show_format",
             "-show_streams", "-of", "json", real],
            timeout_s=self.timeout_s)
        if code != 0:
            raise MediaExecutionError(
                f"ffprobe failed for {path!r}: {_redact(err or out)}",
                code="local-tool-error")
        try:
            data = json.loads(out)
        except ValueError:
            raise MediaExecutionError(
                f"ffprobe returned unparseable output for {path!r}",
                code="malformed-output")
        metadata = {"format_name": (data.get("format") or {}).get(
            "format_name", "unknown"),
                    "duration_seconds": None,
                    "width": None, "height": None,
                    "frame_rate": None, "audio_streams": []}
        fmt = data.get("format") or {}
        try:
            metadata["duration_seconds"] = float(
                fmt["duration"]) if fmt.get("duration") else None
        except (TypeError, ValueError):
            metadata["duration_seconds"] = None
        for stream in data.get("streams") or []:
            if stream.get("codec_type") == "video":
                metadata["width"] = stream.get("width")
                metadata["height"] = stream.get("height")
                rate = stream.get("avg_frame_rate") or ""
                if "/" in str(rate):
                    num, den = str(rate).split("/", 1)
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
        return metadata

    def translate(self, packet, context) -> dict:
        request = super().translate(packet, context)
        operation = (context or {}).get("ffmpeg_operation") or {}
        request["ffmpeg_operation"] = operation.get("operation")
        request["inputs"] = operation.get("inputs") or []
        request["output"] = operation.get("output")
        request["options"] = operation.get("options") or {}
        return request

    def _transcode_argv(self, request) -> list:
        operation = request.get("ffmpeg_operation")
        inputs = request.get("inputs") or []
        output = request.get("output")
        options = request.get("options") or {}
        if not output:
            raise MediaExecutionError(
                "ffmpeg transcode/assemble needs an output path",
                code="local-tool-error")
        out_real = _contained_path(self.workspace_root, output)
        if operation == "transcode":
            if len(inputs) != 1:
                raise MediaExecutionError(
                    "ffmpeg transcode needs exactly one input",
                    code="local-tool-error")
            in_real = _contained_path(self.workspace_root, inputs[0])
            argv = [self.ffmpeg, "-y", "-v", "error", "-i", in_real]
            for key in ("video_codec", "audio_codec", "crf",
                        "preset", "pix_fmt"):
                value = options.get(key)
                if value is not None:
                    flag = {"video_codec": "-c:v",
                            "audio_codec": "-c:a", "crf": "-crf",
                            "preset": "-preset",
                            "pix_fmt": "-pix_fmt"}[key]
                    argv += [flag, str(value)]
            size = options.get("size")
            if size:
                # A size is exactly WxH; anything else is refused
                # before it can reach the ffmpeg command line.
                if not isinstance(size, str) \
                        or not re.fullmatch(r"[0-9]+x[0-9]+", size):
                    raise MediaExecutionError(
                        f"ffmpeg size option {size!r} is not WxH",
                        code="local-tool-error")
            fps = options.get("fps")
            if fps is not None:
                if isinstance(fps, bool) \
                        or not isinstance(fps, (int, float)) \
                        or fps <= 0 or fps > 240:
                    raise MediaExecutionError(
                        "ffmpeg fps option must be a positive "
                        "number no greater than 240",
                        code="local-tool-error")
            if size and fps is not None:
                argv += ["-vf", f"scale={size},fps={fps},setsar=1"]
            elif size:
                argv += ["-s", str(size)]
            elif fps is not None:
                argv += ["-vf", f"fps={fps}"]
            argv.append(out_real)
            return argv, out_real
        if operation == "assemble":
            if len(inputs) < 2:
                raise MediaExecutionError(
                    "ffmpeg assemble needs at least two inputs",
                    code="local-tool-error")
            list_path = os.path.join(
                self.workspace_root, ".cf-concat-list.txt")
            lines = []
            for item in inputs:
                real = _contained_path(self.workspace_root, item)
                if not os.path.isfile(real):
                    raise MediaExecutionError(
                        f"assemble input {item!r} does not exist",
                        code="local-tool-error")
                lines.append(f"file '{real}'")
            with open(list_path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(lines) + "\n")
            return [self.ffmpeg, "-y", "-v", "error", "-f", "concat",
                    "-safe", "0", "-i", list_path, "-c", "copy",
                    out_real], out_real
        raise MediaExecutionError(
            f"unknown ffmpeg operation {operation!r}",
            code="local-tool-error")

    def submit(self, request, context) -> dict:
        operation = request.get("ffmpeg_operation")
        if operation == "probe":
            inputs = request.get("inputs") or []
            if len(inputs) != 1:
                raise MediaExecutionError(
                    "ffmpeg probe needs exactly one input",
                    code="local-tool-error")
            metadata = self.probe(inputs[0])
            artifact = self.verify_output(inputs[0], None, context)
            artifact.update(metadata)
            artifact["provider_model"] = self.binary_version()
            return {"provider_job_id": None, "completed": True,
                    "output": artifact, "failure": None}
        if operation in ("transcode", "assemble"):
            argv, out_real = self._transcode_argv(request)
            code, _out, err = _run_argv(argv, timeout_s=self.timeout_s)
            if code != 0:
                raise MediaExecutionError(
                    f"ffmpeg {operation} failed: {_redact(err)}",
                    code="local-tool-error")
            if not os.path.isfile(out_real):
                raise MediaExecutionError(
                    f"ffmpeg {operation} produced no output file",
                    code="malformed-output")
            if os.path.getsize(out_real) > self.max_output_bytes:
                raise MediaExecutionError(
                    f"ffmpeg output exceeds the size limit "
                    f"({self.max_output_bytes} bytes)",
                    code="local-tool-error")
            output = request.get("output")
            artifact = self.verify_output(output, None, context)
            artifact.update(self.probe(output))
            artifact["provider_model"] = self.binary_version()
            return {"provider_job_id": None, "completed": True,
                    "output": artifact, "failure": None}
        raise MediaExecutionError(
            f"unknown ffmpeg operation {operation!r}",
            code="local-tool-error")

    def verify_output(self, path, packet, context) -> dict:
        artifact = super().verify_output(
            _contained_path(self.workspace_root, path), packet, context)
        artifact["path"] = path  # keep the workspace-relative path
        if artifact["bytes"] > self.max_output_bytes:
            raise MediaExecutionError(
                f"output exceeds the size limit "
                f"({self.max_output_bytes} bytes)",
                code="local-tool-error")
        return artifact


class VoiceStudioAdapter(MediaAdapter):
    """Safe wrapper around the bundled VoiceStudio backend.

    Backend interface (verified in components/voicestudio):
    ``GET /health`` (``{"status": "ok", "device", "engine",
    "version"}`` or 503 while starting) and ``POST /generate``
    (multipart form: ``text``, ``language``, ``ref_audio``,
    ``ref_text``, ``profile_id``, ``seed``, ``engine``; classic
    flow returns the WAV bytes with an ``X-Audio-Id`` header).
    The adapter never starts the backend itself and never modifies
    VoiceStudio internals: when the service is down it reports
    BLOCKED with the exact start command, and the operator starts
    it. The default OmniVoice weights are CC-BY-NC — commercial /
    monetized production is refused in preflight.

    Voice controls (R4-D, verified against the bundled backend
    2026-11-27): ``instruct`` (fixed English tags only, from the
    execution context) and a numeric ``speaking_pace`` (as the
    backend's ``speed``) are forwarded; ``seed`` is forwarded.
    ``emotional_delivery``, ``pitch_range``, ``pauses``,
    ``vocal_characteristics`` and ``pronunciation_preferences``
    have no backend field on this engine and are refused with a
    precise capability error in preflight and in translate —
    never silently dropped. See
    ``VOICESTUDIO_UNSUPPORTED_VOICE_CONTROLS``.
    """

    adapter_id = "adapter-voicestudio"
    provider_id = "provider-voicestudio-omnivoice"
    adapter_version = "0.5.8"
    # The engine this adapter serves. Submit pins it explicitly: on
    # a cold backend /health reports engine null until an engine is
    # selected or used, and the adapter must not depend on another
    # caller having warmed it.
    engine = "omnivoice"

    def __init__(self, *, workspace_root,
                 base_url=VOICESTUDIO_DEFAULT_BASE_URL,
                 timeout_s=300, http_client=None):
        self.workspace_root = workspace_root
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.http_client = http_client  # injectable transport (tests)

    def capabilities(self) -> dict:
        return {
            "operations": ["generate-speech"],
            "task_types": ["voice-generation"],
        }

    def _http(self, method, url, *, data=None, headers=None,
              files=None):
        """One HTTP call; returns (status, headers dict, body bytes).

        ``http_client`` (tests) is a callable with the same
        signature. The default transport is urllib, loopback only.
        """
        if self.http_client is not None:
            return self.http_client(method, url, data=data,
                                    headers=headers, files=files)
        if not self.base_url.startswith(
                ("http://127.0.0.1", "http://localhost",
                 "http://[::1]")):
            raise MediaExecutionError(
                "VoiceStudio base URL must be loopback",
                code="local-tool-error")
        request = urllib.request.Request(url, data=data, method=method)
        for key, value in (headers or {}).items():
            request.add_header(key, value)
        try:
            with urllib.request.urlopen(
                    request, timeout=self.timeout_s) as response:
                return (response.status,
                        {k.lower(): v for k, v in
                         response.headers.items()},
                        response.read())
        except urllib.error.HTTPError as exc:
            return (exc.code,
                    {k.lower(): v for k, v in exc.headers.items()},
                    exc.read())
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise MediaExecutionError(
                f"VoiceStudio service unreachable: "
                f"{_redact(str(exc))}",
                code="service-unavailable")

    def health(self) -> dict:
        """GET /health; raises service-unavailable when down."""
        status, _headers, body = self._http(
            "GET", self.base_url + "/health")
        if status == 503:
            raise MediaExecutionError(
                "VoiceStudio is starting (HTTP 503); retry shortly",
                code="service-unavailable")
        if status != 200:
            raise MediaExecutionError(
                f"VoiceStudio /health returned HTTP {status}",
                code="service-unavailable")
        try:
            data = json.loads(body.decode("utf-8"))
        except ValueError:
            raise MediaExecutionError(
                "VoiceStudio /health returned unparseable JSON",
                code="malformed-output")
        if data.get("status") != "ok":
            raise MediaExecutionError(
                "VoiceStudio /health did not report ok",
                code="service-unavailable")
        return data

    def preflight(self, packet, context) -> list:
        errors = super().preflight(packet, context)
        context = context or {}
        if context.get("commercial_use"):
            errors.append(
                "commercial/monetized production cannot use "
                "OmniVoice: the default weights are CC-BY-NC "
                "(non-commercial only)")
        if not context.get("voice_consent"):
            errors.append(
                "voice generation needs recorded voice consent "
                "(voice_consent must be true)")
        binding = (packet or {}).get("voice_binding") or {}
        language = binding.get("language")
        if not language:
            errors.append("voice packet carries no language")
        elif language not in OMNIVOICE_LANGUAGES:
            errors.append(
                f"language {language!r} is not evidenced for the "
                f"bundled OmniVoice engine (evidenced: "
                f"{', '.join(OMNIVOICE_LANGUAGES)})")
        # R4-D: unsupported voice controls fail preflight with a
        # precise capability error instead of being silently
        # dropped at submit time.
        errors.extend(_voice_control_errors(binding, context))
        profile_id = binding.get("voice_profile_id")
        expected = context.get("voice_profile_id")
        if expected is not None and profile_id != expected:
            errors.append(
                "voice packet names a different voice profile than "
                "the authorized one")
        if not binding.get("dialogue_line_id"):
            errors.append("voice packet carries no dialogue line id")
        try:
            health = self.health()
        except MediaExecutionError as exc:
            errors.append("; ".join(exc.errors))
            return errors
        engine = health.get("engine")
        if engine is not None and engine != self.engine:
            errors.append(
                f"VoiceStudio /health names engine {engine!r}, not "
                f"{self.engine!r}")
        return errors

    def translate(self, packet, context) -> dict:
        request = super().translate(packet, context)
        binding = (packet or {}).get("voice_binding") or {}
        dialogue = (packet or {}).get("canonical_instruction", "")
        text = binding.get("dialogue_text") or dialogue
        # R4-D: refuse unsupported controls here too, so a direct
        # translate call can never silently drop them.
        control_errors = _voice_control_errors(binding, context)
        if control_errors:
            raise MediaExecutionError(control_errors,
                                     code="validation-failed")
        voice_request = {
            "text": text,
            "language": binding.get("language"),
            "profile_id": binding.get("voice_profile_id"),
            "seed": binding.get("seed"),
            "dialogue_line_id": binding.get("dialogue_line_id"),
        }
        instruct = (context or {}).get("instruct")
        if isinstance(instruct, str) and instruct != "":
            voice_request["instruct"] = instruct
        pace = binding.get("speaking_pace")
        if _voice_control_present(pace):
            voice_request["speed"] = _parse_voice_speed(pace)
        request["voice_request"] = voice_request
        return request

    def _multipart(self, fields, file_field=None, file_bytes=None,
                   file_name="ref.wav"):
        """Build a multipart/form-data body (stdlib only)."""
        boundary = "----cf-voicestudio-boundary"
        parts = []
        for key, value in fields.items():
            if value is None:
                continue
            parts.append(
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'
                f"{value}\r\n".encode("utf-8"))
        if file_field is not None and file_bytes is not None:
            parts.append(
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{file_field}"; '
                f'filename="{file_name}"\r\n'
                "Content-Type: audio/wav\r\n\r\n".encode("utf-8"))
            parts.append(file_bytes)
            parts.append(b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode("utf-8"))
        body = b"".join(parts)
        return body, {"Content-Type":
                      f"multipart/form-data; boundary={boundary}"}

    def submit(self, request, context) -> dict:
        voice = request.get("voice_request") or {}
        text = voice.get("text")
        if not text:
            raise MediaExecutionError(
                "voice request carries no dialogue text",
                code="local-tool-error")
        fields = {
            "text": text,
            "language": voice.get("language"),
            "profile_id": voice.get("profile_id"),
            "seed": (str(voice["seed"])
                     if voice.get("seed") is not None else None),
            # R4-D: instruct (fixed backend tags) and speed (from
            # a numeric speaking_pace) are the only voice
            # controls this engine forwards. _multipart skips
            # None values, so absent controls send nothing.
            "instruct": voice.get("instruct"),
            "speed": (str(voice["speed"])
                      if voice.get("speed") is not None else None),
            "engine": self.engine,
        }
        file_bytes = None
        ref_audio = (context or {}).get("reference_audio_bytes")
        if ref_audio is not None:
            file_bytes = ref_audio
        try:
            body, headers = self._multipart(
                fields, file_field="ref_audio" if file_bytes else None,
                file_bytes=file_bytes)
            status, resp_headers, resp_body = self._http(
                "POST", self.base_url + "/generate", data=body,
                headers=headers)
        except MediaExecutionError as exc:
            if exc.code == "service-unavailable":
                raise
            raise MediaExecutionError(exc.errors,
                                      code="submission-uncertain")
        if status != 200:
            detail = _redact(resp_body.decode("utf-8", "replace"))
            raise MediaExecutionError(
                f"VoiceStudio /generate returned HTTP {status}: "
                f"{detail}",
                code="provider-error")
        if not resp_body:
            raise MediaExecutionError(
                "VoiceStudio /generate returned no audio bytes",
                code="malformed-output")
        execution_id = (context or {}).get("execution_id") or "voice"
        out_rel = os.path.join("outputs", f"{execution_id}.wav")
        out_real = _contained_path(self.workspace_root, out_rel)
        os.makedirs(os.path.dirname(out_real), exist_ok=True)
        with open(out_real, "wb") as handle:
            handle.write(resp_body)
        artifact = self.verify_output(out_rel, None, context)
        artifact["provider_model"] = "omnivoice"
        audio_id = resp_headers.get("x-audio-id")
        if audio_id:
            artifact["provider_audio_id"] = audio_id
        return {"provider_job_id": audio_id, "completed": True,
                "output": artifact, "failure": None}

    def verify_output(self, path, packet, context) -> dict:
        real = _contained_path(self.workspace_root, path)
        artifact = super().verify_output(real, packet, context)
        artifact["path"] = path
        try:
            with wave.open(real, "rb") as wav:
                frames = wav.getnframes()
                rate = wav.getframerate()
                artifact["duration_seconds"] = (
                    frames / rate if rate else None)
                artifact["audio_streams"] = [{
                    "codec": "pcm",
                    "sample_rate": str(rate),
                    "channels": wav.getnchannels()}]
        except (wave.Error, EOFError, OSError):
            artifact["duration_seconds"] = None
            artifact["audio_streams"] = []
        return artifact


class OpenMontageAdapter(MediaAdapter):
    """Thin wrapper around the bundled OpenMontage checkout.

    Verified interface only: component-checkout verification
    (origin + HEAD pin, the P0-014 pattern), ``make preflight``
    (tool-registry discovery in the component venv), pipeline-request
    preparation from validated artifacts, and output verification
    via ffprobe. ``submit`` runs only the verified render entry —
    ``render_demo.py`` for a named demo composition. A production
    pipeline request is prepared as a pipeline definition, but
    submitting an arbitrary production render has no verified entry
    in this checkout, so it fails closed with a clear message
    instead of pretending to render. Production assembly stays
    NOT_TESTED until a real production output is generated and
    independently validated.
    """

    adapter_id = "adapter-openmontage"
    provider_id = "provider-openmontage-assembly"
    adapter_version = "0.5.8"

    def __init__(self, *, component_root, workspace_root,
                 timeout_s=600):
        self.component_root = component_root
        self.workspace_root = workspace_root
        self.timeout_s = timeout_s

    def capabilities(self) -> dict:
        return {
            "operations": ["assemble-timeline"],
            "task_types": ["media-technical"],
        }

    def verify_checkout(self) -> dict:
        """Verify the OpenMontage checkout (origin + HEAD pin)."""
        root = self.component_root
        if not os.path.isdir(os.path.join(root, ".git")):
            raise MediaExecutionError(
                "OpenMontage component has no .git checkout",
                code="local-tool-error")
        code, out, _err = _run_argv(
            ["git", "-C", root, "rev-parse", "HEAD"], timeout_s=30)
        if code != 0:
            raise MediaExecutionError(
                "cannot read the OpenMontage checkout HEAD",
                code="local-tool-error")
        head = out.strip()
        if head != OPENMONTAGE_PIN:
            raise MediaExecutionError(
                "OpenMontage checkout HEAD does not match the pinned "
                "commit (expected the P0-014 pin)",
                code="local-tool-error")
        code, out, _err = _run_argv(
            ["git", "-C", root, "config", "--get", "remote.origin.url"],
            timeout_s=30)
        if code != 0 or OPENMONTAGE_ORIGIN not in out:
            raise MediaExecutionError(
                "OpenMontage checkout origin is not the canonical "
                "upstream",
                code="local-tool-error")
        return {"head": head, "origin": OPENMONTAGE_ORIGIN}

    def run_preflight(self) -> dict:
        """Run ``make preflight`` in the component checkout."""
        self.verify_checkout()
        code, out, err = _run_argv(
            ["make", "-C", self.component_root, "preflight"],
            timeout_s=self.timeout_s)
        if code != 0:
            raise MediaExecutionError(
                f"OpenMontage preflight failed: {_redact(err or out)}",
                code="local-tool-error")
        return {"preflight": "ok", "detail": out[:500]}

    def preflight(self, packet, context) -> list:
        errors = super().preflight(packet, context)
        try:
            self.verify_checkout()
        except MediaExecutionError as exc:
            errors.extend(exc.errors)
        return errors

    def translate(self, packet, context) -> dict:
        request = super().translate(packet, context)
        request["pipeline"] = {
            "composition": (context or {}).get("composition"),
            "clips": (context or {}).get("clips") or [],
            "output": (context or {}).get("output"),
        }
        return request

    def submit(self, request, context) -> dict:
        pipeline = request.get("pipeline") or {}
        composition = pipeline.get("composition")
        if not composition:
            raise MediaExecutionError(
                "OpenMontage submit needs a named demo composition "
                "in the pipeline request (production renders have "
                "no verified entry in this checkout)",
                code="local-tool-error")
        renders_dir = os.path.join(
            self.component_root, "projects", "demos", "renders")
        before = self._render_snapshot(renders_dir)
        code, out, err = _run_argv(
            [sys.executable, "render_demo.py", composition],
            timeout_s=self.timeout_s, cwd=self.component_root)
        if code != 0:
            raise MediaExecutionError(
                f"OpenMontage render failed: {_redact(err or out)}",
                code="local-tool-error")
        after = self._render_snapshot(renders_dir)
        new_files = sorted(
            name for name, stamp in after.items()
            if before.get(name) != stamp)
        if not new_files:
            raise MediaExecutionError(
                "OpenMontage render produced no new output file",
                code="malformed-output")
        rendered = os.path.join(renders_dir, new_files[-1])
        execution_id = (context or {}).get("execution_id") or "render"
        out_rel = os.path.join(
            "outputs",
            f"{execution_id}{os.path.splitext(rendered)[1]}")
        out_real = _contained_path(self.workspace_root, out_rel)
        os.makedirs(os.path.dirname(out_real), exist_ok=True)
        shutil.copyfile(rendered, out_real)
        artifact = self.verify_output(out_rel, None, context)
        return {"provider_job_id": None, "completed": True,
                "output": artifact, "failure": None}

    @staticmethod
    def _render_snapshot(renders_dir):
        """{filename: (mtime_ns, size)} — a re-render of the same
        demo overwrites the same filename, so a name-only diff
        would miss it; mtime + size catch the overwrite."""
        snapshot = {}
        if not os.path.isdir(renders_dir):
            return snapshot
        for name in os.listdir(renders_dir):
            path = os.path.join(renders_dir, name)
            try:
                stat = os.stat(path)
            except OSError:
                continue
            snapshot[name] = (stat.st_mtime_ns, stat.st_size)
        return snapshot

    def verify_output(self, path, packet, context) -> dict:
        real = _contained_path(self.workspace_root, path)
        artifact = super().verify_output(real, packet, context)
        artifact["path"] = path
        return artifact


# ---------------------------------------------------------------------
# External HTTP providers (WO §6)
# ---------------------------------------------------------------------

#: Declarative specs, one per live external provider. Facts come
#: from the current official documentation audited 2026-11-27; see
#: docs/runtime/PROVIDER_ADAPTERS.md. ``documentation_status`` is
#: "official" when the official page was read directly,
#: "secondary-quoting-official" when the official page could not be
#: fetched here and the fact is quoted from a source citing it.
#: Sora has no spec: the service was shut down 2026-09-24.
PROVIDER_SPECS = {
    "provider-openai-image": {
        "adapter_id": "adapter-openai-image",
        "api_version": "Images API (2026)",
        "models": ["gpt-image-1-mini", "gpt-image-1.5", "gpt-image-2",
                   "gpt-image-2-2026-04-21",
                   "gpt-image-2.5-sunburst",
                   "gpt-image-2.5-sunburst-2026-09-08",
                   "gpt-image-2.5-flare",
                   "gpt-image-2.5-flare-2026-09-08",
                   "gpt-image-2.6-sunburst", "gpt-image-2.6-flare",
                   "chatgpt-image-latest"],
        "documentation_url":
            "https://developers.openai.com/api/reference/ruby/"
            "resources/images/methods/generate",
        "documentation_status": "official",
        "submit": {"method": "POST",
                   "url": "https://api.openai.com/v1/images/generations"},
        # R4-A: explicit origin allowlists. Output is base64 in the
        # response body, so no output origin exists.
        "api_origins": ["api.openai.com"],
        "output_origins": [],
        "auth": {"env_var": "OPENAI_API_KEY", "header": "Authorization",
                 "scheme": "Bearer"},
        "async": False, "cancel": None, "retrieval": "base64-body",
        "charge_behaviour": "per token/request; current per-model "
                            "pricing UNCONFIRMED (not re-read "
                            "2026-11-27)",
        "reference_images": "up to 16 on edits",
        "async_behaviour": "synchronous",
        "cancellation_support": "none — synchronous",
        "output_retrieval": "base64 b64_json in the response",
        "character_reference_limits": "up to 16 reference images on edits",
        "aspect_ratios": ["1024x1024", "1536x1024", "1024x1536",
                          "auto"],
        "audio_support": False,
    },
    "provider-gemini-image": {
        "adapter_id": "adapter-gemini-image",
        "api_version": "Interactions API (Api-Revision 2026-05-20)",
        "models": ["gemini-nano-banana-2.1",
                   "gemini-3.1-flash-lite-image",
                   "gemini-3-pro-image",
                   # Deprecated 2026-10-06, no shutdown date
                   # announced; still works.
                   "gemini-3.1-flash-image"],
        "documentation_url":
            "https://aistudio.google.com/docs/image-generation",
        "documentation_status": "official",
        "submit": {"method": "POST",
                   "url": "https://generativelanguage.googleapis.com/"
                          "v1beta/interactions"},
        # R4-A: output is base64 in the response body.
        "api_origins": ["generativelanguage.googleapis.com"],
        "output_origins": [],
        "auth": {"env_var": "GEMINI_API_KEY", "header": "x-goog-api-key",
                 "scheme": "key"},
        "async": False, "cancel": None, "retrieval": "base64-body",
        "charge_behaviour": "per image/token; Nano Banana 2.1 "
                            "≈ $0.0336 (1K) / $0.0504 (2K) / $0.113 "
                            "(4K) per image (secondary-quoted)",
        "reference_images": "up to 14 (2.1/3.1-flash-image: 10 "
                            "objects + 4 characters; Pro: 6 objects "
                            "+ 5 characters + 3 style)",
        "async_behaviour": "synchronous",
        "cancellation_support": "none — synchronous",
        "output_retrieval": "base64 in the response",
        "character_reference_limits":
            "up to 14 reference images (2.1/3.1-flash-image: 10 "
            "objects + 4 characters; Pro: 6 objects + 5 "
            "characters + 3 style)",
        "aspect_ratios": ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5",
                          "5:4", "9:16", "16:9", "21:9"],
        "audio_support": False,
    },
    "provider-fal-image": {
        "adapter_id": "adapter-fal-image",
        "api_version": "fal Model APIs (queue + direct)",
        "models": ["fal-ai/nano-banana-2", "google/nano-banana-2.1",
                   "fal-ai/flux-2-pro", "fal-ai/flux/dev"],
        "documentation_url": "https://fal.ai/llms-full.txt",
        "documentation_status": "official",
        "submit": {"method": "POST",
                   "url": "https://queue.fal.run/{endpoint}"},
        # R4-A: output is a signed URL on the fal.media CDN.
        # Poll/cancel URLs come from the submit response and are
        # validated against api_origins before use (the fal queue
        # API returns status_url / cancel_url on submit).
        "api_origins": ["queue.fal.run"],
        "output_origins": ["fal.media"],
        "auth": {"env_var": "FAL_KEY", "header": "Authorization",
                 "scheme": "Key"},
        "async": True,
        "cancel": {"method": "PUT", "url_from_submit": "cancel_url"},
        "retrieval": "cdn-url",
        "charge_behaviour": "per output from prepaid credits; "
                            "server errors (HTTP 500+) never charged; "
                            "queue-wait time never charged; a 422 may "
                            "be charged if GPU time was spent; "
                            "nano-banana-2 $0.08/image (2K 1.5x, 4K "
                            "2x, 0.5K 0.75x)",
        "reference_images": "not supported by the contract "
                            "(reference-part serialization "
                            "UNCONFIRMED; no upload flow)",
        "async_behaviour": "asynchronous queue with polling "
                           "(direct endpoints synchronous)",
        "cancellation_support": "PUT cancel_url — cancellation "
                                "supported",
        "output_retrieval": "fal.media CDN URL, available 7 days "
                            "or more",
        "character_reference_limits":
            "not supported by the contract (see reference_images)",
        "aspect_ratios": ["per-model"],
        "audio_support": False,
    },
    "provider-veo-video": {
        "adapter_id": "adapter-veo-video",
        "api_version": "Veo 3.1 (Vertex AI / Gemini Enterprise Agent Platform; -001 IDs)",
        "models": ["veo-3.1-generate-001",
                   "veo-3.1-fast-generate-001",
                   "veo-3.1-lite-generate-001"],
        "documentation_url":
            "https://docs.cloud.google.com/gemini-enterprise-"
            "agent-platform/models/video/generate-videos-from-text",
        "documentation_status": "official",
        "submit": {"method": "POST",
                   "url": "https://us-central1-aiplatform.googleapis.com/"
                          "v1/projects/{project_id}/locations/us-central1/"
                          "publishers/google/models/{model}:"
                          "predictLongRunning"},
        # R4 follow-up: the Gemini API Veo preview IDs
        # (veo-3.1-generate-preview and siblings) were shut down
        # 2026-10-22. The live route is Vertex AI, authenticated
        # with an OAuth Bearer token (VERTEX_ACCESS_TOKEN), never
        # an API key. The poll is a POST to the model's
        # :fetchPredictOperation with the full operation name in
        # the body; completion carries inline video bytes (no
        # storageUri) or a GCS URI. A GCS URI cannot be
        # downloaded: no GCS download origin is documented in
        # the audit, so output_origins stays empty and the
        # contract refuses GCS output explicitly.
        "api_origins": ["us-central1-aiplatform.googleapis.com"],
        "output_origins": [],
        "poll_template": "https://us-central1-aiplatform.googleapis.com/"
                         "v1/projects/{project_id}/locations/us-central1/"
                         "publishers/google/models/{model}:"
                         "fetchPredictOperation",
        "auth": {"env_var": "VERTEX_ACCESS_TOKEN",
                 "header": "Authorization", "scheme": "Bearer"},
        "async": True, "cancel": None, "retrieval": "inline-bytes",
        "charge_behaviour": "per 1 count (official unit; the "
                            "pricing page does not define 1 count); "
                            "per-second pricing is SECONDARY-only "
                            "and is NOT encoded",
        "reference_images": "up to 3 (Standard/Fast; Lite image "
                            "input UNCONFIRMED — Vertex docs "
                            "conflict: model page says not "
                            "supported, capabilities row says "
                            "supported)",
        "async_behaviour": "asynchronous long-running operation "
                           "with polling (fetchPredictOperation)",
        "cancellation_support": "none — no cancel operation is "
                                "documented for Vertex Veo",
        "output_retrieval": "inline video bytes in the "
                            "fetchPredictOperation response when no "
                            "storageUri is set; a GCS URI output "
                            "cannot be downloaded (download origin "
                            "UNCONFIRMED)",
        "character_reference_limits":
            "up to 3 reference images (Standard/Fast; Lite image "
            "input UNCONFIRMED)",
        "aspect_ratios": ["16:9", "9:16"],
        "audio_support": True,
        "duration_limits": {"min_seconds": 4, "max_seconds": 8},
    },
    "provider-kling-video": {
        "adapter_id": "adapter-kling-video",
        "api_version": "Kling AI Open Platform (legacy /v1 design)",
        "models": ["kling-v1", "kling-v1-6", "kling-v2-master",
                   "kling-v2-1-master", "kling-v2-5-turbo",
                   "kling-v2-6"],
        "documentation_url":
            "https://app.klingai.com/global/dev/document-api",
        "documentation_status": "secondary-quoting-official",
        "submit": {"method": "POST",
                   "url": "https://api-singapore.klingai.com/v1/videos/"
                          "text2video"},
        # R4-A: poll is the legacy per-task URL for the submit
        # design this spec uses (secondary-quoting-official).
        # R4-B: the result URL host is UNCONFIRMED — output_origins
        # stays empty, so a download fails closed until confirmed.
        # The newer path-based design (Kling 4.0 etc.) is NOT
        # implemented: its prompt field was UNCONFIRMED at audit
        # time.
        "api_origins": ["api-singapore.klingai.com"],
        "output_origins": [],
        "poll_template": "https://api-singapore.klingai.com/v1/videos/"
                         "text2video/{job_id}",
        "auth": {"env_var": "KLING_API_KEY", "header": "Authorization",
                 "scheme": "Bearer"},
        "async": True, "cancel": None, "retrieval": "url",
        "charge_behaviour": "prepaid resource packages (units); "
                            "failed-task charging UNCONFIRMED",
        "reference_images": "image-to-video first/last frame "
                            "(base64, <= 10 MB)",
        "async_behaviour": "asynchronous task_id with polling and "
                           "callback_url",
        "cancellation_support": "none — no cancel endpoint is "
                                "documented (secondary-quoting-"
                                "official)",
        "output_retrieval": "result URL, 30 days",
        "character_reference_limits":
            "image-to-video first/last frame",
        "aspect_ratios": ["16:9", "9:16", "1:1"],
        "audio_support": True,
        "duration_limits": {"min_seconds": 5, "max_seconds": 10},
    },
    "provider-ltx-video": {
        "adapter_id": "adapter-ltx-video",
        "api_version": "LTX API v2 (async; V1 retired 2026-10-26)",
        "models": ["ltx-2-5-fast", "ltx-2-5-pro", "ltx-2-3-fast",
                   "ltx-2-3-pro"],
        "documentation_url": "https://docs.ltx.io/welcome",
        "documentation_status": "secondary-quoting-official",
        "submit": {"method": "POST",
                   "url": "https://api.ltx.io/v2/{endpoint}"},
        # R4-A: poll is GET /v2/{endpoint}/{id} (official docs).
        # The video_url host is UNCONFIRMED — output_origins stays
        # empty, so a download fails closed until confirmed.
        "api_origins": ["api.ltx.io"],
        "output_origins": [],
        "poll_template": "https://api.ltx.io/v2/{endpoint}/{job_id}",
        "auth": {"env_var": "LTX_API_KEY", "header": "Authorization",
                 "scheme": "Bearer"},
        "async": True, "cancel": None, "retrieval": "url",
        "charge_behaviour": "per second of output video (per second "
                            "of input audio for audio-to-video); "
                            "Fast $0.09/s (720p); prepaid credits are "
                            "reserved before generation and charged "
                            "only on success — a failed job releases "
                            "its reservation",
        "reference_images": "one first-frame image (data URI, "
                            "<= 7 MB)",
        "async_behaviour": "asynchronous only (V2) with job ID "
                           "polling",
        "cancellation_support": "none found in the official docs "
                                "(UNCONFIRMED)",
        "output_retrieval": "video_url, available under 24 hours "
                            "(signed URL expires 1 hour after it is "
                            "checked)",
        "character_reference_limits": "one first-frame image",
        "aspect_ratios": ["16:9", "9:16", "1:1"],
        "audio_support": True,
        "duration_limits": {"min_seconds": 6, "max_seconds": 20},
    },
    "provider-elevenlabs-voice": {
        "adapter_id": "adapter-elevenlabs-voice",
        "api_version": "ElevenLabs REST v1",
        "models": ["eleven_v4", "eleven_v4_turbo", "eleven_v3",
                   "eleven_multilingual_v2", "eleven_flash_v2_5"],
        "documentation_url":
            "https://elevenlabs.io/docs/api-reference",
        "documentation_status": "secondary-quoting-official",
        "submit": {"method": "POST",
                   "url": "https://api.elevenlabs.io/v1/text-to-speech/"
                          "{voice_id}"},
        # R4-A: output is raw audio bytes in the response.
        "api_origins": ["api.elevenlabs.io"],
        "output_origins": [],
        "auth": {"env_var": "ELEVENLABS_API_KEY", "header": "xi-api-key",
                 "scheme": "key"},
        "async": False, "cancel": None, "retrieval": "response-body",
        "charge_behaviour": "per character: $0.08/1,000 chars "
                            "(v4/v3/multilingual v2); $0.04/1,000 "
                            "chars (turbo/flash) (secondary-quoted); "
                            "free tier 10,000 credits/mo, "
                            "non-commercial only",
        "reference_images": "n/a (voice sample for cloning)",
        "async_behaviour": "synchronous",
        "cancellation_support": "none — synchronous",
        "output_retrieval": "response bytes (audio)",
        "character_reference_limits":
            "n/a (voice sample for cloning)",
        "aspect_ratios": [],
        "audio_support": True,
    },
    "provider-lyria-music": {
        "adapter_id": "adapter-lyria-music",
        "api_version": "Lyria 3.5 via Interactions API "
                       "(Api-Revision 2026-05-20)",
        "models": ["lyria-3.5", "lyria-3-clip-preview"],
        "documentation_url":
            "https://aistudio.google.com/docs/music-generation",
        "documentation_status": "official",
        "submit": {"method": "POST",
                   "url": "https://generativelanguage.googleapis.com/"
                          "v1beta/interactions"},
        # R4-A: output is base64 in the response body.
        "api_origins": ["generativelanguage.googleapis.com"],
        "output_origins": [],
        "auth": {"env_var": "GEMINI_API_KEY", "header": "x-goog-api-key",
                 "scheme": "key"},
        "async": False, "cancel": None, "retrieval": "base64-body",
        "charge_behaviour": "flat $0.08 per generated song, "
                            "including failed takes (secondary-quoted)",
        "reference_images": "images as inspiration only (up to 10)",
        "async_behaviour": "synchronous",
        "cancellation_support": "none — synchronous",
        "output_retrieval": "base64 MP3 in the response",
        "character_reference_limits":
            "images as inspiration only (up to 10)",
        "aspect_ratios": [],
        "audio_support": True,
        "duration_limits": {"max_seconds": 180},
    },
}


class HttpProviderAdapter(MediaAdapter):
    """Mockable HTTP lifecycle adapter for one external provider.

    Driven by a declarative spec from :data:`PROVIDER_SPECS`. The
    transport is injectable: tests pass a mock transport, and the
    default transport is the pinned HTTPS transport from
    :mod:`runtime.provider_url_policy` (DNS resolution validated
    once, connection pinned to a validated public address, TLS
    SNI/certificate validation against the hostname). No live paid
    call is made without explicit user authorization and a
    credential in the allow-listed environment variable; without a
    credential the adapter fails closed with
    ``credential-missing``.

    URL security (R4-A): every request URL — submit, poll,
    cancel, download — is validated against the spec's explicit
    origin allowlists before any byte is sent; every redirect hop
    is validated the same way; provider authorization headers are
    kept only on same-origin hops. For downloads they are sent
    only when the download URL's host is the provider's own API
    origin (no current provider has a documented API-origin
    download, so in practice no download receives them; the
    rule stays for any future provider that does); a signed
    CDN download URL never receives them. A forbidden destination
    is refused before the transport is ever called for that hop.

    Provider contracts (R4-B): the request body, the submit
    response parsing, the poll/cancel/response parsing and the
    error classification come from the provider's contract in
    :mod:`runtime.provider_contracts` — one exact contract per
    provider, audited against the official docs 2026-11-27. No
    generic ``{model, prompt}`` payload is ever built; a request
    that was not built by a contract is refused. Reference
    assets arrive through the execution context (``{"mime",
    "base64"}`` or a workspace ``{"path"}``) and are normalized
    here before the contract validates them for its provider.
    """

    def __init__(self, spec, *, workspace_root, timeout_s=120,
                 max_download_bytes=MAX_DOWNLOAD_BYTES,
                 max_response_bytes=MAX_RESPONSE_BYTES,
                 transport=None, url_policy=None, resolver=None):
        self.spec = spec
        self.provider_id = spec.get("provider_id", "")
        self.adapter_id = spec.get("adapter_id", "")
        self.adapter_version = spec.get("api_version", "")
        self.workspace_root = workspace_root
        self.timeout_s = timeout_s
        self.max_download_bytes = max_download_bytes
        self.max_response_bytes = max_response_bytes
        self.transport = transport
        self.url_policy = url_policy or ProviderURLPolicy(
            api_origins=spec.get("api_origins") or (),
            output_origins=spec.get("output_origins") or (),
            resolver=resolver, timeout_s=timeout_s,
            max_response_bytes=max_response_bytes)

    def capabilities(self) -> dict:
        operations = []
        if "image" in self.provider_id:
            operations = ["generate-image"]
        elif "video" in self.provider_id:
            operations = ["generate-video"]
        elif "voice" in self.provider_id:
            operations = ["generate-speech"]
        elif "music" in self.provider_id:
            operations = ["generate-sound"]
        task_types = {
            "generate-image": ["image-generation", "reference-sheet",
                               "environment-reference", "prop-reference"],
            "generate-video": ["video-generation"],
            "generate-speech": ["voice-generation"],
            "generate-sound": ["sound-generation"],
        }.get(operations[0], []) if operations else []
        return {"operations": operations, "task_types": task_types}

    def preflight(self, packet, context) -> list:
        errors = super().preflight(packet, context)
        if self.spec.get("documentation_status") != "official":
            errors.append(
                f"provider {self.provider_id} spec is documented "
                "from secondary sources quoting official docs — "
                "verify the official documentation before a live call")
        try:
            resolve_provider_secret(self.provider_id)
        except MediaExecutionError as exc:
            errors.extend(exc.errors)
        return errors

    def _single_hop(self, method, url, *, headers=None, body=None,
                    purpose="api", stream_to=None):
        """One HTTP hop, no redirects.

        Returns ``(status, headers, body)`` where ``body`` is bytes
        — except when ``stream_to`` is a file handle, where the
        body is a live ``http.client.HTTPResponse`` (real
        transport) or bytes (mock transport) and the caller must
        stream-or-discard it and close it before deciding the hop
        is final. A transport failure after the request was sent
        is submission-uncertain. A response larger than the cap is
        refused before it is returned or written.
        """
        if self.transport is not None:
            try:
                status, resp_headers, resp_body = self.transport(
                    method, url, headers=headers, body=body)
            except MediaExecutionError:
                raise
            except Exception as exc:  # noqa: BLE001 - transport guard
                raise MediaExecutionError(
                    f"provider request failed: {_redact(str(exc))}",
                    code="submission-uncertain")
            resp_body = resp_body or b""
            if len(resp_body) > self.max_response_bytes \
                    and stream_to is None:
                raise MediaExecutionError(
                    "provider response exceeds the size limit",
                    code="validation-failed")
            return (status,
                    {k.lower(): v for k, v
                     in (resp_headers or {}).items()},
                    resp_body)
        return self.url_policy.pinned_request(
            method, url, purpose=purpose, headers=headers, body=body,
            raw_response=(stream_to is not None))

    @staticmethod
    def _close_body(body) -> None:
        """Close a live HTTPResponse body, if that is what it is."""
        close = getattr(body, "close", None)
        if callable(close):
            try:
                close()
            except Exception:  # noqa: BLE001 - close is best-effort
                pass

    def _stream_body(self, body, stream_to) -> None:
        """Write one final-hop body to the download file, capped."""
        written = 0
        if hasattr(body, "read"):
            while True:
                chunk = body.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > self.max_download_bytes:
                    raise MediaExecutionError(
                        "download exceeds the size limit",
                        code="local-tool-error")
                stream_to.write(chunk)
        else:
            body = body or b""
            for offset in range(0, len(body), 1024 * 1024):
                chunk = body[offset:offset + 1024 * 1024]
                written += len(chunk)
                if written > self.max_download_bytes:
                    raise MediaExecutionError(
                        "download exceeds the size limit",
                        code="local-tool-error")
                stream_to.write(chunk)

    def _request(self, method, url, *, headers=None, body=None,
                 purpose="api", stream_to=None):
        """One HTTP request with a validated redirect loop.

        The starting URL and EVERY redirect hop are validated
        against the policy for ``purpose`` before the transport is
        called for that hop, so a forbidden destination is never
        requested. Authorization headers are kept only while the
        hop stays on the origin the request started from; they are
        stripped on any cross-origin hop. For ``"output"``
        downloads they are kept only when the download URL's host
        is one of the provider's own API origins (no current
        provider has a documented API-origin download, so in
        practice no download receives them); a signed CDN download
        URL never receives them. A
        303 turns the request into a GET with no body; 307/308
        keep method and body. At most ``MAX_REDIRECTS`` redirects
        are followed. When ``stream_to`` is given, a hop's body is
        written to the file only once the hop is known to be final
        — a redirect hop's body is discarded, never written.
        """
        current_url = url
        current_method = method
        current_headers = dict(headers or {})
        current_body = body
        if purpose == "output":
            parsed_start = self.url_policy.validate_url(
                current_url, purpose)
            if parsed_start["host"] not in \
                    self.url_policy.api_origins:
                current_headers = {
                    key: value for key, value in current_headers.items()
                    if key.lower() not in AUTH_HEADER_NAMES}
        origin = None
        for hop in range(self.url_policy.max_redirects + 1):
            parsed = self.url_policy.validate_url(current_url, purpose)
            hop_origin = (parsed["host"], parsed["port"])
            if origin is None:
                origin = hop_origin
            elif hop_origin != origin:
                current_headers = {
                    key: value
                    for key, value in current_headers.items()
                    if key.lower() not in AUTH_HEADER_NAMES}
            status, resp_headers, resp_body = self._single_hop(
                current_method, current_url, headers=current_headers,
                body=current_body, purpose=purpose,
                stream_to=stream_to)
            if status not in (301, 302, 303, 307, 308):
                if stream_to is not None:
                    try:
                        self._stream_body(resp_body, stream_to)
                    finally:
                        self._close_body(resp_body)
                    return status, resp_headers, b""
                return status, resp_headers, resp_body
            location = (resp_headers or {}).get("location")
            # A redirect hop's body is never download content.
            self._close_body(resp_body)
            if not location:
                if stream_to is not None:
                    return status, resp_headers, b""
                return status, resp_headers, resp_body
            if hop >= self.url_policy.max_redirects:
                raise MediaExecutionError(
                    "provider request exceeded the redirect limit",
                    code="validation-failed")
            # Validate the next hop BEFORE following it: a
            # redirect to a forbidden destination is refused
            # here, and the transport is never called for it.
            next_url = urllib.parse.urljoin(current_url, location)
            self.url_policy.validate_url(next_url, purpose)
            if status == 303:
                current_method = "GET"
                current_body = None
            current_url = next_url
        raise MediaExecutionError(
            "provider request exceeded the redirect limit",
            code="validation-failed")

    def _auth_headers(self) -> dict:
        spec_auth = self.spec.get("auth") or {}
        secret = resolve_provider_secret(self.provider_id)
        header = spec_auth.get("header", "Authorization")
        scheme = spec_auth.get("scheme", "Bearer")
        if scheme == "key":
            return {header: secret}
        return {header: f"{scheme} {secret}"}

    def translate(self, packet, context) -> dict:
        """Build the provider request from the packet + context.

        The request is built by the provider's contract
        (:mod:`runtime.provider_contracts`) — never a generic
        ``{model, prompt}`` payload. Reference assets in the
        context are normalized here (``{"path"}`` entries are
        read from the workspace) and validated by the contract
        for its own provider. The built request — including the
        contract's ``context_updates`` — is stored in the
        translated packet under ``contract_request``; submit
        refuses a packet that was not built by a contract.
        """
        request = super().translate(packet, context)
        model = packet.get("model") or (context or {}).get("model") \
            or (self.spec.get("models") or [None])[0]
        if model is None:
            raise MediaExecutionError(
                f"{self.provider_id}: packet has no model")
        context = _normalize_references(self.workspace_root,
                                        context or {})
        contract = get_contract(self.provider_id)
        built = contract.build_request(packet, context, model)
        request["contract_request"] = built
        request["context"] = {**context, **built["context_updates"]}
        request["request"] = {
            "model": built["model"], "body": built["body"],
            "content_type": built["content_type"],
            "headers": built["headers"],
            "url_values": built["url_values"],
            "query": built["query"]}
        return request

    def _submit_url(self, built) -> str:
        """The submit URL: the contract's URL, or the spec template
        with the contract's validated URL values substituted.

        Template values travel inside the submit URL: each one is
        validated as a safe path token before substitution, so a
        hostile model/endpoint/voice id cannot smuggle a path
        traversal or a second host into the request.
        """
        url = built.get("url")
        if url is not None:
            return url
        url = (self.spec.get("submit") or {}).get("url", "")
        values = built.get("url_values") or {}
        for var, value in values.items():
            placeholder = "{" + var + "}"
            if placeholder not in url:
                continue
            if var == "model":
                token = validate_model_id(value)
            elif var == "endpoint":
                token = validate_endpoint_segment(value)
            else:
                token = validate_provider_job_id(value)
            url = url.replace(placeholder, token)
        if "{" in url or "}" in url:
            raise MediaExecutionError(
                f"provider {self.provider_id} submit URL has an "
                "unfilled template placeholder",
                code="validation-failed")
        query = built.get("query") or {}
        if query:
            separator = "&" if "?" in url else "?"
            url = url + separator + urllib.parse.urlencode(query)
        return url

    def _classify_provider_error(self, status, raw_body):
        """(code, message) for a provider HTTP error response."""
        contract = get_contract(self.provider_id)
        kind, detail, _retryable = contract.parse_error_response(
            status, raw_body)
        code = kind if kind in FAILURE_CODES else "provider-error"
        return code, f"{self.provider_id} request failed ({kind}): " \
                     f"{detail}"

    def submit(self, request, context) -> dict:
        """Submit; parse the provider's submit response by contract."""
        contract = get_contract(self.provider_id)
        built = (request or {}).get("contract_request")
        if not isinstance(built, dict) \
                or not isinstance(built.get("body"), (dict, bytes)):
            raise MediaExecutionError(
                f"{self.provider_id}: submit refused — the packet "
                "was not translated by its provider contract "
                "(no contract_request)")
        shown = (request or {}).get("request") or {}
        if shown.get("body") != built["body"]:
            raise MediaExecutionError(
                f"{self.provider_id}: submit refused — the request "
                "body does not match the contract-built request")
        context = _normalize_references(self.workspace_root,
                                        context or {})
        ctx = dict((request or {}).get("context") or {})
        ctx.update(context)
        ctx.update(built.get("context_updates") or {})
        url = self._submit_url(built)
        self.url_policy.validate_url(url, "api")
        headers = dict(self._auth_headers())
        headers.update(built.get("headers") or {})
        content_type = built.get("content_type")
        body = built["body"]
        if content_type == "application/json":
            body = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif isinstance(content_type, str) and content_type.startswith(
                "multipart/form-data"):
            # The contract already encoded the multipart body
            # (OpenAI edits); the boundary travels in the content
            # type. The body must be bytes, never rebuilt here.
            if not isinstance(body, (bytes, bytearray)):
                raise MediaExecutionError(
                    f"{self.provider_id}: contract returned a "
                    "multipart body that is not bytes",
                    code="local-tool-error")
            headers["Content-Type"] = content_type
        else:
            raise MediaExecutionError(
                f"{self.provider_id}: unsupported contract content "
                f"type {content_type!r}")
        method = (self.spec.get("submit") or {}).get("method", "POST")
        try:
            status, resp_headers, resp_body = self._request(
                method, url, headers=headers, body=body,
                purpose="api")
        except MediaExecutionError:
            raise
        if status >= 400:
            code, message = self._classify_provider_error(
                status, resp_body)
            raise MediaExecutionError(message, code=code)
        if not contract.is_async:
            return self._finish_sync(contract, resp_body,
                                     resp_headers, ctx)
        try:
            data = json.loads(resp_body.decode("utf-8"))
        except ValueError:
            raise MediaExecutionError(
                f"provider {self.provider_id} returned unparseable "
                "async submit response",
                code="malformed-output")
        if not isinstance(data, dict):
            raise MediaExecutionError(
                f"provider {self.provider_id} returned a "
                "non-object async submit response",
                code="malformed-output")
        result = contract.parse_submit_response(data, status, ctx)
        output = result.get("output")
        if output is not None:
            # Synchronous completion delivered through the submit
            # path (a contract whose submit response is JSON
            # carrying the output).
            out_rel = self._save_output_bytes(
                output["raw"], output["ext"], ctx)
            artifact = self.verify_output(out_rel, None, ctx)
            return {"provider_job_id": result.get("job_id"),
                    "completed": True, "output": artifact,
                    "failure": None}
        return {"provider_job_id": result.get("job_id"),
                "completed": False, "output": None, "failure": None}

    def _save_output_bytes(self, raw, ext, ctx) -> str:
        """Write verified output bytes under outputs/; return the
        workspace-relative path."""
        if not raw:
            raise MediaExecutionError(
                f"{self.provider_id} returned no output bytes",
                code="malformed-output")
        execution_id = (ctx or {}).get("execution_id") or "output"
        out_rel = os.path.join("outputs", f"{execution_id}{ext}")
        out_real = _contained_path(self.workspace_root, out_rel)
        os.makedirs(os.path.dirname(out_real), exist_ok=True)
        with open(out_real, "wb") as handle:
            handle.write(raw)
        return out_rel

    def _finish_sync(self, contract, resp_body, headers, ctx) -> dict:
        """Save a synchronous response's output bytes (verified).

        The contract decodes the provider's bytes (JSON-wrapped
        base64 for OpenAI/Gemini/Lyria, raw bytes for
        ElevenLabs); the file is verified by the size and hash
        checks in :meth:`verify_output`.
        """
        raw, ext = contract.extract_sync_output(resp_body, headers)
        out_rel = self._save_output_bytes(raw, ext, ctx)
        artifact = self.verify_output(out_rel, None, ctx)
        return {"provider_job_id": None, "completed": True,
                "output": artifact, "failure": None}

    def _poll_request(self, provider_job_id, context):
        """(method, url, body) for one poll of an async job.

        The contract rebuilds it from the documented endpoint
        template + the validated job id (Veo's full Vertex
        operation name → a POST to :fetchPredictOperation with
        the operation name in the body, Kling's per-task URL,
        LTX's per-endpoint URL). Where the provider has no
        rebuildable template (fal), a ``status_url`` returned by
        the provider on submit is accepted ONLY after the policy
        validates it against this provider's API origins; it is
        never used unvalidated. No status/cancellation endpoint
        is invented. A job id the contract cannot use fails
        closed here, before any request — the transport is never
        called for it.
        """
        if not isinstance(provider_job_id, str) \
                or not provider_job_id:
            raise MediaExecutionError(
                "provider job id is required",
                code="validation-failed")
        contract = get_contract(self.provider_id)
        request = contract.build_poll_request(provider_job_id,
                                              context)
        if request is not None:
            method, url, body = request
            self.url_policy.validate_url(url, "api")
            return method, url, body
        validate_provider_job_id(provider_job_id)
        status_url = (context or {}).get("status_url")
        if not status_url:
            raise MediaExecutionError(
                "async poll needs a rebuildable poll URL from the "
                "provider contract or a status_url in the context",
                code="local-tool-error")
        self.url_policy.validate_url(status_url, "api")
        return "GET", status_url, None

    def _cancel_url(self, provider_job_id, context) -> str:
        """Build the cancel URL, or refuse when none is documented.

        The contract rebuilds it where the provider has a
        template; otherwise a submit-returned ``cancel_url``
        validated against the provider's API origins. Providers
        without documented cancellation stay explicitly
        non-cancellable.
        """
        contract = get_contract(self.provider_id)
        if not contract.supports_cancel:
            raise MediaExecutionError(
                f"provider {self.provider_id} offers no documented "
                "cancellation",
                code="local-tool-error")
        if not isinstance(provider_job_id, str) \
                or not provider_job_id:
            raise MediaExecutionError(
                "provider job id is required",
                code="validation-failed")
        url = contract.build_cancel_url(provider_job_id, context)
        if url is not None:
            self.url_policy.validate_url(url, "api")
            return url
        validate_provider_job_id(provider_job_id)
        cancel_url = (context or {}).get("cancel_url")
        if not cancel_url:
            raise MediaExecutionError(
                "cancellation needs a cancel URL in the context",
                code="local-tool-error")
        self.url_policy.validate_url(cancel_url, "api")
        return cancel_url

    def poll(self, provider_job_id, context) -> dict:
        contract = get_contract(self.provider_id)
        if not contract.is_async:
            raise MediaExecutionError(
                f"adapter {self.adapter_id} serves a synchronous "
                "provider and does not implement poll")
        method, status_url, poll_body = self._poll_request(
            provider_job_id, context)
        headers = self._auth_headers()
        body = None
        if poll_body is not None:
            body = json.dumps(poll_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        status, _headers, resp_body = self._request(
            method, status_url, headers=headers, body=body,
            purpose="api")
        if status >= 400:
            code, message = self._classify_provider_error(
                status, resp_body)
            raise MediaExecutionError(message, code=code)
        try:
            data = json.loads(resp_body.decode("utf-8"))
        except ValueError:
            raise MediaExecutionError(
                f"provider {self.provider_id} poll returned "
                "unparseable JSON",
                code="malformed-output")
        if not isinstance(data, dict):
            raise MediaExecutionError(
                f"provider {self.provider_id} poll returned a "
                "non-object response",
                code="malformed-output")
        parsed = contract.parse_poll_response(data)
        state = parsed["state"]
        if state == "running":
            return {"provider_job_id": provider_job_id,
                    "completed": False, "output": None,
                    "failure": None}
        if state == "cancelled":
            return {"provider_job_id": provider_job_id,
                    "completed": True, "output": None,
                    "failure": {
                        "code": "cancelled-by-provider",
                        "message": parsed.get("error")
                        or "provider reported the job cancelled",
                        "retryable": False}}
        if state == "failed":
            return {"provider_job_id": provider_job_id,
                    "completed": True, "output": None,
                    "failure": {
                        "code": "provider-error",
                        "message": parsed.get("error")
                        or "provider reported the job failed",
                        "retryable": False}}
        inline = parsed.get("output")
        if inline is not None:
            # Inline-bytes completion (Veo): the poll response
            # carried the output bytes; no download happens.
            out_rel = self._save_output_bytes(
                inline["raw"], inline["ext"], context)
            artifact = self.verify_output(out_rel, None, context)
            return {"provider_job_id": provider_job_id,
                    "completed": True, "output": artifact,
                    "failure": None}
        output_url = parsed.get("output_url")
        response_url = parsed.get("response_url") \
            or (context or {}).get("response_url")
        if response_url is not None:
            # Two-step result (fal): fetch the result document
            # from the provider's response URL, then read its
            # output URL. The URL is validated like any API URL.
            result_data = self._get_json(response_url)
            result_parsed = contract.parse_result_response(
                result_data)
            if result_parsed.get("error"):
                return {"provider_job_id": provider_job_id,
                        "completed": True, "output": None,
                        "failure": {
                            "code": "provider-error",
                            "message": result_parsed["error"],
                            "retryable": False}}
            output_url = result_parsed.get("output_url")
        if not output_url:
            raise MediaExecutionError(
                f"provider {self.provider_id} completed without "
                "an output URL",
                code="malformed-output")
        local_path = self.retrieve(provider_job_id, output_url,
                                   context)
        artifact = self.verify_output(local_path, None, context)
        return {"provider_job_id": provider_job_id,
                "completed": True, "output": artifact,
                "failure": None}

    def _get_json(self, url) -> dict:
        """GET a provider JSON document (fal result fetch)."""
        self.url_policy.validate_url(url, "api")
        status, _headers, resp_body = self._request(
            "GET", url,
            headers=self._auth_headers(), purpose="api")
        if status >= 400:
            code, message = self._classify_provider_error(
                status, resp_body)
            raise MediaExecutionError(message, code=code)
        try:
            data = json.loads(resp_body.decode("utf-8"))
        except ValueError:
            raise MediaExecutionError(
                f"provider {self.provider_id} returned unparseable "
                "JSON",
                code="malformed-output")
        if not isinstance(data, dict):
            raise MediaExecutionError(
                f"provider {self.provider_id} returned a "
                "non-object response",
                code="malformed-output")
        return data

    def cancel(self, provider_job_id, context) -> bool:
        contract = get_contract(self.provider_id)
        if not contract.supports_cancel:
            raise MediaExecutionError(
                f"provider {self.provider_id} offers no documented "
                "cancellation",
                code="local-tool-error")
        cancel_url = self._cancel_url(provider_job_id, context)
        headers = self._auth_headers()
        method = (self.spec.get("cancel") or {}).get("method", "PUT")
        status, _headers, resp_body = self._request(
            method, cancel_url, headers=headers, purpose="api")
        if status >= 400:
            code, message = self._classify_provider_error(
                status, resp_body)
            raise MediaExecutionError(message, code=code)
        if resp_body:
            try:
                data = json.loads(resp_body.decode("utf-8"))
            except ValueError:
                raise MediaExecutionError(
                    f"provider {self.provider_id} cancel returned "
                    "unparseable JSON",
                    code="malformed-output")
            if not isinstance(data, dict):
                raise MediaExecutionError(
                    f"provider {self.provider_id} cancel returned "
                    "a non-object response",
                    code="malformed-output")
        else:
            data = {}
        parsed = contract.parse_cancel_response(status, data)
        return parsed.get("cancelled") is True

    def retrieve(self, provider_job_id, output_ref, context) -> str:
        """Retrieve provider output to a local path; returns the path.

        URL outputs are downloads through the URL security policy
        (purpose ``"output"``): the URL is validated against the
        provider's permitted output/CDN origins BEFORE any request
        is made, authorization headers are sent only when the
        download URL's host is the provider's own API origin
        (no current provider has a documented API-origin
        download, so in practice no download receives them — a
        signed CDN download URL never receives them), every
        redirect hop is validated, and the
        body is streamed to disk under ``max_download_bytes``. A
        failed or over-limit download leaves no partial file
        behind. Non-URL references are workspace-contained local
        paths, as before.
        """
        if not isinstance(output_ref, str) or not output_ref:
            raise MediaExecutionError(
                "retrieve needs a non-empty output reference",
                code="local-tool-error")
        if output_ref.startswith(("http://", "https://")):
            # Validate before any request — and before opening the
            # destination file — so a malicious output URL can
            # neither trigger a request nor create a file.
            self.url_policy.validate_url(output_ref, "output")
            execution_id = (context or {}).get("execution_id") \
                or "output"
            out_rel = os.path.join("outputs", execution_id)
            out_real = _contained_path(self.workspace_root, out_rel)
            os.makedirs(os.path.dirname(out_real), exist_ok=True)
            try:
                with open(out_real, "wb") as handle:
                    status, _headers, _body = self._request(
                        "GET", output_ref,
                        headers=self._auth_headers(),
                        purpose="output", stream_to=handle)
            except MediaExecutionError:
                try:
                    os.unlink(out_real)
                except OSError:
                    pass
                raise
            except Exception as exc:  # noqa: BLE001 - download guard
                try:
                    os.unlink(out_real)
                except OSError:
                    pass
                raise MediaExecutionError(
                    f"output download failed: {_redact(str(exc))}",
                    code="provider-error")
            if status >= 400:
                try:
                    os.unlink(out_real)
                except OSError:
                    pass
                raise MediaExecutionError(
                    "output download returned HTTP "
                    f"{status} for "
                    f"{safe_url_for_message(output_ref)}",
                    code="provider-error")
            return out_rel
        return _contained_path(self.workspace_root, output_ref)

    def verify_output(self, path, packet, context) -> dict:
        real = _contained_path(self.workspace_root, path)
        artifact = super().verify_output(real, packet, context)
        artifact["path"] = path
        return artifact


def get_adapter(provider_id: str, **kwargs):
    """Build the adapter for one provider id.

    Local providers return their concrete adapter; external live
    providers return an :class:`HttpProviderAdapter` over their
    spec. Sora raises: the service is shut down and has no adapter.
    """
    if provider_id == "provider-ffmpeg":
        return FFmpegAdapter(**kwargs)
    if provider_id == "provider-voicestudio-omnivoice":
        return VoiceStudioAdapter(**kwargs)
    if provider_id == "provider-openmontage-assembly":
        return OpenMontageAdapter(**kwargs)
    if provider_id == "provider-sora-video":
        raise MediaExecutionError(
            "provider-sora-video has no adapter: the Sora service "
            "was shut down 2026-09-24",
            code="provider-error")
    spec = PROVIDER_SPECS.get(provider_id)
    if spec is None:
        raise MediaExecutionError(
            f"no adapter is registered for provider "
            f"{provider_id!r}")
    full_spec = dict(spec)
    full_spec["provider_id"] = provider_id
    return HttpProviderAdapter(full_spec, **kwargs)


__all__ = [
    "MediaExecutionError",
    "VOICESTUDIO_ORIGIN",
    "VOICESTUDIO_PIN",
    "OPENMONTAGE_ORIGIN",
    "OPENMONTAGE_PIN",
    "VOICESTUDIO_DEFAULT_BASE_URL",
    "OMNIVOICE_LANGUAGES",
    "VOICESTUDIO_SUPPORTED_VOICE_CONTROLS",
    "VOICESTUDIO_UNSUPPORTED_VOICE_CONTROLS",
    "PROVIDER_SECRET_ENV",
    "resolve_provider_secret",
    "probe_opentimelineio",
    "FFmpegAdapter",
    "VoiceStudioAdapter",
    "OpenMontageAdapter",
    "PROVIDER_SPECS",
    "HttpProviderAdapter",
    "get_adapter",
]
