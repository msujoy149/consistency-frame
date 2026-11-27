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
retrieval, charge behaviour). Specs come from the current official
provider documentation audited 2026-11-27 (see
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
import urllib.request
import wave

from .media_execution import MediaAdapter, MediaExecutionError

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

# Allow-listed credential environment variables, one per external
# provider. No other variable is ever read as a secret.
PROVIDER_SECRET_ENV = {
    "provider-openai-image": "OPENAI_API_KEY",
    "provider-gemini-image": "GEMINI_API_KEY",
    "provider-fal-image": "FAL_KEY",
    "provider-veo-video": "GEMINI_API_KEY",
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
                argv += ["-s", str(size)]
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
        request["voice_request"] = {
            "text": text,
            "language": binding.get("language"),
            "profile_id": binding.get("voice_profile_id"),
            "seed": binding.get("seed"),
            "dialogue_line_id": binding.get("dialogue_line_id"),
        }
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
        "models": ["gpt-image-1.5", "gpt-image-2",
                   "gpt-image-2.5-sunburst", "gpt-image-2.5-flare",
                   "gpt-image-2.6-sunburst", "gpt-image-2.6-flare"],
        "documentation_url":
            "https://developers.openai.com/api/reference/ruby/"
            "resources/images/methods/generate",
        "documentation_status": "official",
        "submit": {"method": "POST",
                   "url": "https://api.openai.com/v1/images/generations"},
        "auth": {"env_var": "OPENAI_API_KEY", "header": "Authorization",
                 "scheme": "Bearer"},
        "async": False, "cancel": None, "retrieval": "base64-body",
        "charge_behaviour": "per token/request; current per-model "
                            "pricing UNCONFIRMED (only gpt-image-1 "
                            "rates were verified, and that model is "
                            "shut down)",
        "reference_images": "up to 10 on edits",
        "async_behaviour": "synchronous",
        "cancellation_support": "none — synchronous",
        "output_retrieval": "base64 b64_json in the response",
        "character_reference_limits": "up to 10 reference images on edits",
        "aspect_ratios": ["1024x1024", "1536x1024", "1024x1536",
                          "auto"],
        "audio_support": False,
    },
    "provider-gemini-image": {
        "adapter_id": "adapter-gemini-image",
        "api_version": "Interactions API (Api-Revision 2026-05-20)",
        "models": ["gemini-nano-banana-2.1",
                   "gemini-3.1-flash-lite-image",
                   "gemini-3-pro-image"],
        "documentation_url":
            "https://aistudio.google.com/docs/image-generation",
        "documentation_status": "official",
        "submit": {"method": "POST",
                   "url": "https://generativelanguage.googleapis.com/"
                          "v1beta/interactions"},
        "auth": {"env_var": "GEMINI_API_KEY", "header": "x-goog-api-key",
                 "scheme": "key"},
        "async": False, "cancel": None, "retrieval": "base64-body",
        "charge_behaviour": "per image/token; Nano Banana 2.1 "
                            "≈ $0.0336 (1K) / $0.0504 (2K) / $0.113 "
                            "(4K) per image (secondary-quoted)",
        "reference_images": "up to 14 (4 character max on 2.1)",
        "async_behaviour": "synchronous",
        "cancellation_support": "none — synchronous",
        "output_retrieval": "base64 in the response",
        "character_reference_limits":
            "up to 14 reference images (4 character max on 2.1)",
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
        "auth": {"env_var": "FAL_KEY", "header": "Authorization",
                 "scheme": "Key"},
        "async": True,
        "cancel": {"method": "PUT", "url_from_submit": "cancel_url"},
        "retrieval": "cdn-url",
        "charge_behaviour": "per output from prepaid credits; "
                            "server errors (HTTP 500+) never charged; "
                            "queue-wait time never charged",
        "reference_images": "per-endpoint (up to 10 on some)",
        "async_behaviour": "asynchronous queue with polling "
                           "(direct endpoints synchronous)",
        "cancellation_support": "PUT cancel_url — cancellation "
                                "supported",
        "output_retrieval": "fal.media CDN URL, available 7 days "
                            "or more",
        "character_reference_limits":
            "per-endpoint (up to 10 on some)",
        "aspect_ratios": ["per-model"],
        "audio_support": False,
    },
    "provider-veo-video": {
        "adapter_id": "adapter-veo-video",
        "api_version": "Veo 3.1 (Gemini API preview IDs; Vertex GA IDs)",
        "models": ["veo-3.1-generate-preview",
                   "veo-3.1-fast-generate-preview",
                   "veo-3.1-lite-generate-preview"],
        "documentation_url":
            "https://docs.cloud.google.com/gemini-enterprise-"
            "agent-platform/models/video/generate-videos-from-text",
        "documentation_status": "official",
        "submit": {"method": "POST",
                   "url": "https://generativelanguage.googleapis.com/"
                          "v1beta/models/{model}:predictLongRunning"},
        "auth": {"env_var": "GEMINI_API_KEY", "header": "x-goog-api-key",
                 "scheme": "key"},
        "async": True, "cancel": None, "retrieval": "download",
        "charge_behaviour": "per second of output, success only; "
                            "Lite $0.05/s (720p), Fast $0.10/s (720p), "
                            "Standard $0.40/s (720p) (secondary-quoted)",
        "reference_images": "up to 3 (Standard/Fast; Lite: none)",
        "async_behaviour": "asynchronous long-running operation "
                           "with polling",
        "cancellation_support": "UNCONFIRMED — no cancel operation "
                                "found in the official docs",
        "output_retrieval": "download URL / GCS URI on completion",
        "character_reference_limits":
            "up to 3 reference images (Standard/Fast; Lite: none)",
        "aspect_ratios": ["16:9", "9:16"],
        "audio_support": True,
        "duration_limits": {"min_seconds": 4, "max_seconds": 8},
    },
    "provider-kling-video": {
        "adapter_id": "adapter-kling-video",
        "api_version": "Kling AI Open Platform (legacy + model-in-path)",
        "models": ["kling-4.0", "kling-4.0-flash", "kling-3.0",
                   "kling-3.0-turbo"],
        "documentation_url":
            "https://app.klingai.com/global/dev/document-api",
        "documentation_status": "secondary-quoting-official",
        "submit": {"method": "POST",
                   "url": "https://api-singapore.klingai.com/v1/videos/"
                          "text2video"},
        "auth": {"env_var": "KLING_API_KEY", "header": "Authorization",
                 "scheme": "Bearer"},
        "async": True, "cancel": None, "retrieval": "url",
        "charge_behaviour": "prepaid resource packages (units); "
                            "failed tasks do not consume credits",
        "reference_images": "keyframes / multi-image / Omni",
        "async_behaviour": "asynchronous task_id with polling and "
                           "callback_url",
        "cancellation_support": "UNCONFIRMED — no cancel operation "
                                "found in the official docs",
        "output_retrieval": "result URL, 30 days",
        "character_reference_limits":
            "keyframes / multi-image / Omni",
        "aspect_ratios": ["16:9", "9:16", "1:1"],
        "audio_support": True,
        "duration_limits": {"min_seconds": 3, "max_seconds": 30},
    },
    "provider-ltx-video": {
        "adapter_id": "adapter-ltx-video",
        "api_version": "LTX API v2 (async; V1 retired 2026-10-26)",
        "models": ["ltx-2-5-fast", "ltx-2-5-pro"],
        "documentation_url": "https://docs.ltx.io/welcome",
        "documentation_status": "secondary-quoting-official",
        "submit": {"method": "POST",
                   "url": "https://api.ltx.io/v2/{endpoint}"},
        "auth": {"env_var": "LTX_API_KEY", "header": "Authorization",
                 "scheme": "Bearer"},
        "async": True, "cancel": None, "retrieval": "url",
        "charge_behaviour": "per second of output video (per second "
                            "of input audio for audio-to-video); "
                            "Fast $0.09/s (720p); failed-task charging "
                            "UNCONFIRMED",
        "reference_images": "one first-frame image",
        "async_behaviour": "asynchronous only (V2) with job ID "
                           "polling",
        "cancellation_support": "UNCONFIRMED — no cancel operation "
                                "found in the official docs",
        "output_retrieval": "video_url, available under 24 hours",
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
        "models": ["lyria-3.5"],
        "documentation_url":
            "https://aistudio.google.com/docs/music-generation",
        "documentation_status": "official",
        "submit": {"method": "POST",
                   "url": "https://generativelanguage.googleapis.com/"
                          "v1beta/interactions"},
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
    default transport is urllib with a timeout. No live paid call
    is made without explicit user authorization and a credential in
    the allow-listed environment variable; without a credential the
    adapter fails closed with ``credential-missing``.
    """

    def __init__(self, spec, *, workspace_root, timeout_s=120,
                 max_download_bytes=512 * 1024 * 1024,
                 transport=None):
        self.spec = spec
        self.provider_id = spec.get("provider_id", "")
        self.adapter_id = spec.get("adapter_id", "")
        self.adapter_version = spec.get("api_version", "")
        self.workspace_root = workspace_root
        self.timeout_s = timeout_s
        self.max_download_bytes = max_download_bytes
        self.transport = transport

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

    def _request(self, method, url, *, headers=None, body=None):
        """One HTTP call via the injected transport or urllib.

        Returns (status, headers dict, body bytes). A transport
        failure after the request was sent is submission-uncertain.
        """
        if self.transport is not None:
            try:
                return self.transport(method, url, headers=headers,
                                      body=body)
            except MediaExecutionError:
                raise
            except Exception as exc:  # noqa: BLE001 - transport guard
                raise MediaExecutionError(
                    f"provider request failed: {_redact(str(exc))}",
                    code="submission-uncertain")
        request = urllib.request.Request(url, data=body, method=method)
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
                f"provider request failed: {_redact(str(exc))}",
                code="submission-uncertain")

    def _auth_headers(self) -> dict:
        spec_auth = self.spec.get("auth") or {}
        secret = resolve_provider_secret(self.provider_id)
        header = spec_auth.get("header", "Authorization")
        scheme = spec_auth.get("scheme", "Bearer")
        if scheme == "key":
            return {header: secret}
        return {header: f"{scheme} {secret}"}

    def translate(self, packet, context) -> dict:
        request = super().translate(packet, context)
        request["provider_request"] = {
            "model": (context or {}).get("model")
                     or (self.spec.get("models") or [None])[0],
            "prompt": packet.get("canonical_instruction", ""),
        }
        return request

    def submit(self, request, context) -> dict:
        submit_spec = self.spec.get("submit") or {}
        url = submit_spec.get("url", "")
        url = url.replace("{model}",
                          (request.get("provider_request") or {})
                          .get("model", ""))
        url = url.replace("{endpoint}",
                          (context or {}).get("endpoint", ""))
        url = url.replace("{voice_id}",
                          (context or {}).get("voice_id", ""))
        headers = self._auth_headers()
        headers["Content-Type"] = "application/json"
        body = json.dumps(
            request.get("provider_request") or {}).encode("utf-8")
        try:
            status, _headers, resp_body = self._request(
                submit_spec.get("method", "POST"), url,
                headers=headers, body=body)
        except MediaExecutionError:
            raise
        if status >= 400:
            detail = _redact(resp_body.decode("utf-8", "replace"))
            raise MediaExecutionError(
                f"provider {self.provider_id} submit returned HTTP "
                f"{status}: {detail}",
                code="provider-error")
        if self.spec.get("async"):
            try:
                data = json.loads(resp_body.decode("utf-8"))
            except ValueError:
                raise MediaExecutionError(
                    f"provider {self.provider_id} returned "
                    "unparseable async submit response",
                    code="malformed-output")
            job_id = (data.get("request_id") or data.get("id")
                      or data.get("task_id")
                      or (data.get("name") or "").split("/")[-1])
            if not job_id:
                raise MediaExecutionError(
                    f"provider {self.provider_id} async submit "
                    "returned no job id",
                    code="malformed-output")
            return {"provider_job_id": str(job_id), "completed": False,
                    "output": None, "failure": None}
        return self._finish_sync(resp_body, context)

    def _finish_sync(self, resp_body, context) -> dict:
        """Save a synchronous response body as the output artifact."""
        retrieval = self.spec.get("retrieval")
        execution_id = (context or {}).get("execution_id") or "output"
        ext = {"base64-body": ".bin", "response-body": ".bin"}.get(
            retrieval, ".bin")
        if retrieval == "base64-body":
            try:
                data = json.loads(resp_body.decode("utf-8"))
            except ValueError:
                raise MediaExecutionError(
                    f"provider {self.provider_id} returned "
                    "unparseable response",
                    code="malformed-output")
            import base64
            blob = None
            for key in ("b64_json", "data", "audio"):
                value = data.get(key)
                if isinstance(value, str):
                    blob = value
                    break
                if isinstance(value, list) and value:
                    first = value[0]
                    if isinstance(first, dict):
                        blob = (first.get("b64_json")
                                or first.get("data"))
                    elif isinstance(first, str):
                        blob = first
                    if blob:
                        break
            if not blob:
                raise MediaExecutionError(
                    f"provider {self.provider_id} response carried "
                    "no base64 output",
                    code="malformed-output")
            try:
                raw = base64.b64decode(blob, validate=True)
            except Exception:
                raise MediaExecutionError(
                    f"provider {self.provider_id} response carried "
                    "invalid base64 output",
                    code="malformed-output")
        else:
            raw = resp_body
        if not raw:
            raise MediaExecutionError(
                f"provider {self.provider_id} returned no output "
                "bytes",
                code="malformed-output")
        out_rel = os.path.join("outputs", f"{execution_id}{ext}")
        out_real = _contained_path(self.workspace_root, out_rel)
        os.makedirs(os.path.dirname(out_real), exist_ok=True)
        with open(out_real, "wb") as handle:
            handle.write(raw)
        artifact = self.verify_output(out_rel, None, context)
        return {"provider_job_id": None, "completed": True,
                "output": artifact, "failure": None}

    def poll(self, provider_job_id, context) -> dict:
        if not self.spec.get("async"):
            raise MediaExecutionError(
                f"adapter {self.adapter_id} serves a synchronous "
                "provider and does not implement poll")
        status_url = (context or {}).get("status_url")
        if not status_url:
            raise MediaExecutionError(
                "async poll needs a status_url in the context",
                code="local-tool-error")
        headers = self._auth_headers()
        status, _headers, resp_body = self._request(
            "GET", status_url, headers=headers)
        if status >= 400:
            raise MediaExecutionError(
                f"provider {self.provider_id} poll returned HTTP "
                f"{status}",
                code="provider-error")
        try:
            data = json.loads(resp_body.decode("utf-8"))
        except ValueError:
            raise MediaExecutionError(
                f"provider {self.provider_id} poll returned "
                "unparseable JSON",
                code="malformed-output")
        state = str(data.get("status") or data.get("state") or "")
        done = state.upper() in ("COMPLETED", "SUCCEED", "SUCCEEDED",
                                 "SUCCESS")
        failed = state.upper() in ("FAILED", "FAILURE", "ERROR")
        cancelled = state.upper() in ("CANCELLED", "CANCELED")
        if done:
            output_url = None
            result = data.get("result") or data.get("output") or {}
            if isinstance(result, dict):
                videos = result.get("videos")
                if isinstance(videos, list) and videos \
                        and isinstance(videos[0], dict):
                    output_url = videos[0].get("url")
                output_url = (output_url or result.get("video_url")
                              or result.get("url"))
            if not output_url and isinstance(data.get("output"), str):
                output_url = data["output"]
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
        if failed:
            return {"provider_job_id": provider_job_id,
                    "completed": True, "output": None,
                    "failure": {"code": "provider-error",
                                "message": "provider reported the "
                                           "job failed",
                                "retryable": False}}
        if cancelled:
            return {"provider_job_id": provider_job_id,
                    "completed": True, "output": None,
                    "failure": {"code": "cancelled-by-provider",
                                "message": "provider reported the "
                                           "job cancelled",
                                "retryable": False}}
        return {"provider_job_id": provider_job_id, "completed": False,
                "output": None, "failure": None}

    def cancel(self, provider_job_id, context) -> bool:
        cancel_spec = self.spec.get("cancel")
        if not cancel_spec:
            raise MediaExecutionError(
                f"provider {self.provider_id} offers no documented "
                "cancellation",
                code="local-tool-error")
        cancel_url = (context or {}).get("cancel_url")
        if not cancel_url:
            raise MediaExecutionError(
                "cancellation needs a cancel_url in the context",
                code="local-tool-error")
        headers = self._auth_headers()
        status, _headers, _body = self._request(
            cancel_spec.get("method", "PUT"), cancel_url,
            headers=headers)
        if status >= 400:
            raise MediaExecutionError(
                f"provider {self.provider_id} cancel returned HTTP "
                f"{status}",
                code="provider-error")
        return True

    def retrieve(self, provider_job_id, output_ref, context) -> str:
        if not isinstance(output_ref, str) or not output_ref:
            raise MediaExecutionError(
                "retrieve needs a non-empty output reference",
                code="local-tool-error")
        if output_ref.startswith(("http://", "https://")):
            headers = {}
            execution_id = (context or {}).get("execution_id") \
                or "output"
            out_rel = os.path.join("outputs", execution_id)
            out_real = _contained_path(self.workspace_root, out_rel)
            os.makedirs(os.path.dirname(out_real), exist_ok=True)
            try:
                with urllib.request.urlopen(
                        output_ref,
                        timeout=self.timeout_s) as response:
                    size = 0
                    with open(out_real, "wb") as handle:
                        while True:
                            chunk = response.read(1024 * 1024)
                            if not chunk:
                                break
                            size += len(chunk)
                            if size > self.max_download_bytes:
                                raise MediaExecutionError(
                                    "download exceeds the size limit",
                                    code="local-tool-error")
                            handle.write(chunk)
            except MediaExecutionError:
                raise
            except Exception as exc:  # noqa: BLE001 - download guard
                raise MediaExecutionError(
                    f"output download failed: {_redact(str(exc))}",
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
