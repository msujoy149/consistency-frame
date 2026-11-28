"""Provider-specific request/response contracts (R4-B).

One contract class per external provider. A contract owns the
provider's exact request construction, model/operation selection,
input/reference serialization, submit/poll/cancel/response
parsing, output extraction and error classification. The shared
transport and the common execution lifecycle stay in
:mod:`runtime.media_adapters`; a single generic ``{model,
prompt}`` payload is never built — :func:`get_contract` fails
closed for any provider without a contract, and
:class:`HttpProviderAdapter` refuses a request that was not built
by a contract.

Audit basis (2026-11-27): every request/response shape below was
rechecked against the provider's official documentation (or, where
the official page could not be read directly, a secondary source
quoting it — those fields are marked in the code comments and in
``docs/runtime/PROVIDER_ADAPTERS.md``). Facts that could not be
confirmed are marked UNCONFIRMED there and are NOT encoded as
capabilities here: a provider that cannot support a supplied
reference, a requested format, or an operation raises a precise
validation error instead of silently dropping the field or
inventing the behaviour.

Readiness discipline: these contracts are tested with mock
transports only. Mock tests never make a provider EXERCISED or
VERIFIED — EXERCISED needs a real authorized execution with
recorded evidence; VERIFIED needs documented conformance. No live
paid call is authorized by this module.
"""

import base64
import binascii
import json
import re
import urllib.parse

from runtime.media_execution import MediaExecutionError

CONTRACT_AUDIT_DATE = "2026-11-27"

# The Gemini Interactions API revision the official REST examples
# send (Gemini image + Lyria music pages, 2026-11-27).
API_REVISION_GEMINI = "2026-05-20"

_MULTIPART_BOUNDARY = "----consistency-frame-provider-contract"

_MAX_BODY_BYTES_LTX = 32 * 1024 * 1024


def _fail(message, code="validation-failed"):
    raise MediaExecutionError(message, code=code)


def _require_text(value, field, max_len=None):
    if not isinstance(value, str) or not value.strip():
        _fail(f"{field} is required and must be a non-empty string")
    if max_len is not None and len(value) > max_len:
        _fail(f"{field} exceeds the {max_len} character limit")
    return value


def _optional_text(value, field, max_len=None):
    if value is None:
        return None
    return _require_text(value, field, max_len=max_len)


def _validate_enum(value, field, allowed):
    if value not in allowed:
        _fail(f"{field} must be one of {sorted(allowed)}; got "
              f"{value!r}")
    return value


def _validate_int(value, field, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(f"{field} must be an integer")
    if minimum is not None and value < minimum:
        _fail(f"{field} must be at least {minimum}")
    if maximum is not None and value > maximum:
        _fail(f"{field} must be at most {maximum}")
    return value


def _validate_number(value, field, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"{field} must be a number")
    if minimum is not None and value < minimum:
        _fail(f"{field} must be at least {minimum}")
    if maximum is not None and value > maximum:
        _fail(f"{field} must be at most {maximum}")
    return value


def _validate_bool(value, field):
    if not isinstance(value, bool):
        _fail(f"{field} must be a boolean")
    return value


def _parse_json_object(raw_body, provider_id):
    """Parse a provider JSON body; fail closed on anything else."""
    try:
        data = json.loads(raw_body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        _fail(f"provider {provider_id} returned unparseable JSON",
              code="malformed-output")
    if not isinstance(data, dict):
        _fail(f"provider {provider_id} returned a non-object JSON "
              "response", code="malformed-output")
    return data


def _strict_b64(value, field):
    if not isinstance(value, str) or not value:
        _fail(f"{field} is missing or not a base64 string",
              code="malformed-output")
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        _fail(f"{field} is not valid base64", code="malformed-output")


def _error_detail(data):
    """Best-effort provider error message from a parsed body."""
    if not isinstance(data, dict):
        return None
    error = data.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message:
            return message
    detail = data.get("detail")
    if isinstance(detail, str) and detail:
        return detail
    if isinstance(detail, dict):
        message = detail.get("message")
        if isinstance(message, str) and message:
            return message
    message = data.get("message")
    if isinstance(message, str) and message:
        return message
    return None


def _http_error(status, body, provider_id, detail=None):
    """Generic HTTP error classification.

    Returns ``(code, message, retryable)``. 400 is a caller error,
    401/403 an authorization error, 404 a non-retryable provider
    error, 408/429/5xx a retryable provider error. Providers
    override this only to add their own documented error detail
    or charge/retry rules; the classification itself stays shared.
    """
    message = detail or f"provider {provider_id} returned HTTP {status}"
    if status == 400:
        return ("validation-failed", message, False)
    if status in (401, 403):
        return ("authorization-denied", message, False)
    if status == 404:
        return ("provider-error", message, False)
    if status in (408, 429, 500, 502, 503, 504):
        return ("provider-error", message, True)
    return ("provider-error", message, False)


def _multipart_body(fields, files):
    """Build a multipart/form-data body with a fixed boundary.

    ``fields`` is a list of ``(name, value)`` text fields;
    ``files`` a list of ``(field, filename, bytes, mime)``.
    Returns ``(body_bytes, content_type)``.
    """
    boundary = _MULTIPART_BOUNDARY
    parts = []
    for name, value in fields:
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode("utf-8"))
    for field, filename, data, mime in files:
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{field}"; '
            f'filename="{filename}"\r\n'
            f"Content-Type: {mime}\r\n\r\n".encode("utf-8")
            + data + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return (b"".join(parts),
            f"multipart/form-data; boundary={boundary}")


def _reference_images(context, max_count):
    """Validated reference images from the execution context.

    The adapter normalizes each entry to ``{"mime", "base64"}``
    (resolving ``{"path"}`` entries against the workspace) before
    the contract runs; the contract validates count, mime and
    base64 here. Returns a list (possibly empty).
    """
    refs = (context or {}).get("reference_images") or []
    if not isinstance(refs, list):
        _fail("reference_images must be a list")
    if len(refs) > max_count:
        _fail(f"at most {max_count} reference images are supported")
    out = []
    for ref in refs:
        if not isinstance(ref, dict):
            _fail("each reference image must be an object with "
                  "mime and base64 fields")
        mime = ref.get("mime")
        if mime not in ("image/png", "image/jpeg", "image/webp"):
            _fail(f"unsupported reference image mime type: {mime!r}")
        blob = _strict_b64(ref.get("base64"), "reference image")
        out.append({"mime": mime, "base64": ref["base64"],
                    "bytes": blob})
    return out


def _single_reference(context, key):
    """One normalized reference (first/last frame, audio) or None."""
    ref = (context or {}).get(key)
    if ref is None:
        return None
    if not isinstance(ref, dict):
        _fail(f"{key} must be an object with mime and base64 fields")
    mime = ref.get("mime")
    blob = _strict_b64(ref.get("base64"), key)
    return {"mime": mime, "base64": ref["base64"], "bytes": blob}


def _data_uri(ref):
    return f"data:{ref['mime']};base64,{ref['base64']}"


def _interactions_output(data, kind):
    """Extract one base64 output block from an Interactions API
    response.

    The documented response is a ``steps`` array; a ``model_output``
    step carries a ``content`` list whose items have ``"type"`` of
    ``"image"`` or ``"audio"`` with ``data`` (base64) and
    ``mime_type`` — either flat on the item or nested under an
    ``"image"``/``"audio"`` object. Top-level ``output_image`` /
    ``output_audio`` convenience keys are accepted too. Returns
    ``(raw_bytes, mime_type, text_or_None)``; the text is the
    accompanying model text (lyrics for music) when present.
    """
    b64 = None
    mime = None
    text = None
    steps = data.get("steps")
    if isinstance(steps, list):
        for step in steps:
            if not isinstance(step, dict):
                continue
            content = step.get("content")
            if not isinstance(content, list):
                continue
            for item in content:
                if not isinstance(item, dict):
                    continue
                item_type = item.get("type")
                if item_type == "text" and isinstance(
                        item.get("text"), str):
                    text = item["text"]
                    continue
                if item_type != kind:
                    continue
                block = item.get(kind)
                if isinstance(block, dict):
                    candidate = block.get("data")
                    candidate_mime = block.get("mime_type")
                else:
                    candidate = item.get("data")
                    candidate_mime = item.get("mime_type")
                if isinstance(candidate, str) and candidate:
                    b64 = candidate
                    mime = candidate_mime
    if b64 is None:
        convenience = data.get("output_" + kind)
        if isinstance(convenience, dict):
            candidate = convenience.get("data")
            if isinstance(candidate, str) and candidate:
                b64 = candidate
                mime = convenience.get("mime_type")
    if b64 is None:
        _fail("Interactions API response carried no "
              f"{kind} output", code="malformed-output")
    raw = _strict_b64(b64, f"{kind} output")
    if not raw:
        _fail(f"Interactions API returned empty {kind} output",
              code="malformed-output")
    if text is None and isinstance(data.get("output_text"), str):
        text = data["output_text"]
    return raw, mime, text


class ProviderContract:
    """Base class: one provider's exact request/response contract."""

    provider_id = ""
    is_async = False
    supports_cancel = False
    cancel_method = "PUT"

    def build_request(self, packet, context, model):
        """Build the provider request.

        Returns a dict with ``model`` (resolved model id),
        ``body`` (a JSON dict or raw bytes), ``content_type``,
        ``url_values`` (template substitutions for the spec URL),
        ``query`` (query parameters), ``headers`` (extra headers),
        ``url`` (optional full submit-URL override) and
        ``context_updates`` (values the caller should carry into
        the poll/cancel context, e.g. the endpoint kind used).
        """
        raise NotImplementedError

    def parse_submit_response(self, data, status, context=None):
        """Parse a successful submit response.

        Returns ``{"job_id", "status_url", "cancel_url",
        "response_url", "output"}`` — ``output`` is
        ``{"raw": bytes, "ext": str, "detail": str|None}`` for a
        synchronous completion and ``None`` for an async
        acceptance; the URL keys are present only when the
        provider returns them (or the contract constructs them).
        ``context`` is the submit context (endpoint kind etc.).
        """
        raise NotImplementedError

    def parse_poll_response(self, data):
        """Parse an async poll response.

        Returns ``{"state": "running"|"done"|"failed"|
        "cancelled", "output_url": str|None, "response_url":
        str|None, "error": str|None}`` — plus, for a provider
        whose completion carries inline bytes instead of a URL
        (Veo), an optional ``"output": {"raw": bytes, "ext":
        str}``; the adapter saves those bytes instead of
        downloading.
        """
        _fail(f"provider {self.provider_id} does not support polling",
              code="local-tool-error")

    def parse_result_response(self, data):
        """Parse a two-step (fal-style) result response.

        Returns ``{"output_url": str|None, "error": str|None}``.
        """
        _fail(f"provider {self.provider_id} has no two-step result "
              "response", code="local-tool-error")

    def parse_cancel_response(self, status, data):
        """Parse a successful cancel response (2xx only)."""
        return {"cancelled": True}

    def parse_error_response(self, status, body):
        """Classify a provider HTTP error body.

        Returns ``(code, message, retryable)``.
        """
        detail = None
        try:
            data = json.loads(body.decode("utf-8"))
            detail = _error_detail(data)
        except (ValueError, UnicodeDecodeError):
            detail = None
        return _http_error(status, body, self.provider_id,
                           detail=detail)

    def extract_sync_output(self, raw_body, headers):
        """Extract synchronous output bytes from a response.

        Returns ``(raw_bytes, ext)``.
        """
        _fail(f"provider {self.provider_id} is not synchronous",
              code="local-tool-error")

    def build_poll_url(self, job_id, context):
        """Rebuild a poll URL from a job id alone, or None."""
        return None

    def build_poll_request(self, job_id, context):
        """(method, url, body) for one poll, or None.

        Default: a GET of :meth:`build_poll_url`. Contracts
        whose poll is a POST with a body (Veo's
        ``fetchPredictOperation``) override this; the body is a
        JSON object or None.
        """
        url = self.build_poll_url(job_id, context)
        if url is None:
            return None
        return ("GET", url, None)

    def build_cancel_url(self, job_id, context):
        """Rebuild a cancel URL from a job id alone, or None."""
        return None


def _prompt(packet):
    return _require_text(
        (packet or {}).get("canonical_instruction", ""), "prompt")


# ---------------------------------------------------------------------
# OpenAI Images API (official reference, 2026-11-27)
# ---------------------------------------------------------------------

_OPENAI_MODELS = (
    "gpt-image-1-mini", "gpt-image-1.5", "gpt-image-2",
    "gpt-image-2-2026-04-21",
    "gpt-image-2.5-sunburst", "gpt-image-2.5-sunburst-2026-09-08",
    "gpt-image-2.5-flare", "gpt-image-2.5-flare-2026-09-08",
    "gpt-image-2.6-sunburst", "gpt-image-2.6-flare",
    "chatgpt-image-latest",
)
_OPENAI_MAX_PROMPT = 32000
_OPENAI_EDIT_IMAGE_MAX_BYTES = 50 * 1024 * 1024


class OpenAIImageContract(ProviderContract):
    """OpenAI Images API: synchronous generations + edits.

    POST /v1/images/generations (JSON) and POST /v1/images/edits
    (multipart, up to 16 reference images). GPT image models
    always return base64 in ``data[0].b64_json``; the legacy
    ``response_format`` parameter is unsupported for them. Model
    ``gpt-image-1`` was shut down 2026-10-23; dall-e-2/3 were
    retired 2026-05-12 — neither is accepted. Pricing is
    UNCONFIRMED (not re-read 2026-11-27).
    """

    provider_id = "provider-openai-image"
    is_async = False

    def build_request(self, packet, context, model):
        model = _validate_enum(model, "model", _OPENAI_MODELS)
        prompt = _prompt(packet)
        if len(prompt) > _OPENAI_MAX_PROMPT:
            _fail("prompt exceeds the 32000 character limit")
        context = context or {}
        refs = _reference_images(context, 16)
        n = context.get("n", 1)
        _validate_int(n, "n", minimum=1)
        fields = {"model": model, "prompt": prompt, "n": n}
        size = context.get("size")
        if size is not None:
            if size != "auto":
                match = re.fullmatch(r"(\d+)x(\d+)", size)
                if not match:
                    _fail("size must be 'auto' or 'WIDTHxHEIGHT'")
                width, height = int(match.group(1)), int(match.group(2))
                if width <= 0 or height <= 0:
                    _fail("size dimensions must be positive")
                # Arbitrary resolutions are documented for the
                # gpt-image-2 family, with both dimensions
                # divisible by 16.
                if model.startswith("gpt-image-2") and (
                        width % 16 or height % 16):
                    _fail("size dimensions must be divisible by 16 "
                          "for this model")
            fields["size"] = size
        quality = context.get("quality")
        if quality is not None:
            _validate_enum(quality, "quality",
                           ("auto", "low", "medium", "high", "xhigh",
                            "max"))
            if quality in ("xhigh", "max") and not (
                    model.startswith("gpt-image-2.5")):
                _fail("quality 'xhigh'/'max' is supported only by "
                      "gpt-image-2.5 models")
            fields["quality"] = quality
        output_format = context.get("output_format")
        if output_format is not None:
            _validate_enum(output_format, "output_format",
                           ("png", "webp", "jpeg", "gif", "svg"))
            fields["output_format"] = output_format
        background = context.get("background")
        if background is not None:
            _validate_enum(background, "background",
                           ("transparent", "opaque", "auto"))
            fields["background"] = background
        moderation = context.get("moderation")
        if moderation is not None:
            _validate_enum(moderation, "moderation", ("low", "auto"))
            fields["moderation"] = moderation
        complexity = context.get("complexity")
        if complexity is not None:
            _validate_enum(complexity, "complexity",
                           ("low", "medium", "high"))
            fields["complexity"] = complexity
        compression = context.get("output_compression")
        if compression is not None:
            _validate_int(compression, "output_compression",
                          minimum=0, maximum=100)
            if output_format not in ("webp", "jpeg"):
                _fail("output_compression is supported only with "
                      "webp or jpeg output")
            fields["output_compression"] = compression
        frame_count = context.get("frame_count")
        frame_duration_ms = context.get("frame_duration_ms")
        if frame_count is not None or frame_duration_ms is not None:
            if output_format != "gif":
                _fail("frame_count/frame_duration_ms require "
                      "output_format 'gif'")
            if frame_count is not None:
                _validate_int(frame_count, "frame_count",
                              minimum=2, maximum=16)
                fields["frame_count"] = frame_count
            if frame_duration_ms is not None:
                _validate_int(frame_duration_ms,
                              "frame_duration_ms", minimum=20)
                fields["frame_duration_ms"] = frame_duration_ms
        if not refs:
            return {"model": model, "body": fields,
                    "content_type": "application/json",
                    "url_values": {}, "query": {}, "headers": {},
                    "url": None, "context_updates": {}}
        # Edits: multipart, one image part per reference.
        files = []
        for index, ref in enumerate(refs):
            if ref["mime"] not in ("image/png", "image/jpeg",
                                   "image/webp"):
                _fail("OpenAI edits accept png, webp or jpg "
                      "reference images")
            if len(ref["bytes"]) > _OPENAI_EDIT_IMAGE_MAX_BYTES:
                _fail("OpenAI edit reference images must be under "
                      "50 MB")
            ext = {"image/png": "png", "image/jpeg": "jpg",
                   "image/webp": "webp"}[ref["mime"]]
            files.append(("image", f"reference-{index + 1}.{ext}",
                          ref["bytes"], ref["mime"]))
        fidelity = context.get("input_fidelity")
        if fidelity is not None:
            _validate_enum(fidelity, "input_fidelity",
                           ("high", "low"))
            if model.startswith("gpt-image-2"):
                _fail("input_fidelity must be omitted for "
                      "gpt-image-2 models")
            if model == "gpt-image-1-mini" and fidelity == "high":
                _fail("gpt-image-1-mini supports only "
                      "input_fidelity 'low'")
            fields["input_fidelity"] = fidelity
        text_fields = [(key, str(value))
                       for key, value in fields.items()]
        body, content_type = _multipart_body(text_fields, files)
        return {"model": model, "body": body,
                "content_type": content_type,
                "url_values": {}, "query": {}, "headers": {},
                "url": "https://api.openai.com/v1/images/edits",
                "context_updates": {}}

    def parse_submit_response(self, data, status, context=None):
        return {"job_id": None, "status_url": None,
                "cancel_url": None, "response_url": None,
                "output": self._extract(data)}

    def _extract(self, data):
        items = data.get("data")
        if not isinstance(items, list) or not items:
            _fail("OpenAI response carried no image data",
                  code="malformed-output")
        first = items[0]
        if not isinstance(first, dict):
            _fail("OpenAI response carried malformed image data",
                  code="malformed-output")
        b64 = first.get("b64_json")
        if not isinstance(b64, str) or not b64:
            # GPT image models always return base64; a URL-only
            # item is not a usable output for this contract.
            _fail("OpenAI response carried no base64 image data",
                  code="malformed-output")
        raw = _strict_b64(b64, "b64_json")
        if not raw:
            _fail("OpenAI response carried empty image data",
                  code="malformed-output")
        output_format = data.get("output_format")
        ext = {None: ".png", "png": ".png", "webp": ".webp",
               "jpeg": ".jpg", "gif": ".gif",
               "svg": ".svg"}.get(output_format, ".png")
        return {"raw": raw, "ext": ext, "detail": None}

    def extract_sync_output(self, raw_body, headers):
        data = _parse_json_object(raw_body, self.provider_id)
        return (self._extract(data)["raw"],
                self._extract(data)["ext"])


# ---------------------------------------------------------------------
# Gemini image generation via the Interactions API (official docs,
# 2026-11-27)
# ---------------------------------------------------------------------

_GEMINI_IMAGE_MODELS = (
    "gemini-nano-banana-2.1",
    "gemini-3.1-flash-lite-image",
    "gemini-3-pro-image",
    # Deprecated 2026-10-06, no shutdown date announced; still works.
    "gemini-3.1-flash-image",
)
_GEMINI_ASPECT_STANDARD = (
    "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9",
    "21:9",
)
_GEMINI_ASPECT_EXTREME = ("1:4", "4:1", "1:8", "8:1")


class GeminiImageContract(ProviderContract):
    """Gemini image generation (Nano Banana) via Interactions API.

    POST /v1beta/interactions with header ``Api-Revision:
    2026-05-20`` and ``x-goog-api-key``. Request body
    ``{"model", "input": [{"type": "text", "text"}, {"type":
    "image", "data", "mime_type"}...], "response_format": {"type":
    "image", "aspect_ratio", "image_size", "mime_type"}}``. Up to
    14 reference images (2.1 / 3.1-flash-image: up to 10 objects +
    4 characters; Pro: up to 6 objects + 5 characters + 3 style
    references — the per-role caps are documented but not
    enforced per role by this contract, only the 14 total).
    Output is base64 in the response ``steps`` (``output_image``).
    """

    provider_id = "provider-gemini-image"
    is_async = False

    def build_request(self, packet, context, model):
        model = _validate_enum(model, "model", _GEMINI_IMAGE_MODELS)
        prompt = _prompt(packet)
        context = context or {}
        refs = _reference_images(context, 14)
        parts = [{"type": "text", "text": prompt}]
        for ref in refs:
            parts.append({"type": "image", "data": ref["base64"],
                          "mime_type": ref["mime"]})
        body = {"model": model, "input": parts}
        response_format = {"type": "image"}
        aspect_ratio = context.get("aspect_ratio")
        if aspect_ratio is not None:
            if model in ("gemini-3.1-flash-lite-image",
                         "gemini-3-pro-image"):
                allowed = _GEMINI_ASPECT_STANDARD
            else:
                allowed = (_GEMINI_ASPECT_STANDARD
                           + _GEMINI_ASPECT_EXTREME)
            _validate_enum(aspect_ratio, "aspect_ratio", allowed)
            response_format["aspect_ratio"] = aspect_ratio
        image_size = context.get("image_size")
        if image_size is not None:
            if model == "gemini-3.1-flash-lite-image":
                allowed_sizes = ("1K",)
            elif model == "gemini-3.1-flash-image":
                allowed_sizes = ("0.5K", "1K", "2K", "4K")
            else:
                allowed_sizes = ("1K", "2K", "4K")
            _validate_enum(image_size, "image_size", allowed_sizes)
            response_format["image_size"] = image_size
        output_format = context.get("output_format")
        if output_format is not None:
            mime = {"png": "image/png",
                    "jpeg": "image/jpeg"}.get(output_format)
            if mime is None:
                _fail("Gemini image output_format must be png or "
                      "jpeg")
            response_format["mime_type"] = mime
        body["response_format"] = response_format
        return {"model": model, "body": body,
                "content_type": "application/json",
                "url_values": {}, "query": {},
                "headers": {"Api-Revision": API_REVISION_GEMINI},
                "url": None, "context_updates": {}}

    def parse_submit_response(self, data, status, context=None):
        raw, mime, _text = _interactions_output(data, "image")
        ext = {None: ".png", "image/png": ".png",
               "image/jpeg": ".jpg"}.get(mime, ".png")
        return {"job_id": None, "status_url": None,
                "cancel_url": None, "response_url": None,
                "output": {"raw": raw, "ext": ext, "detail": None}}

    def extract_sync_output(self, raw_body, headers):
        data = _parse_json_object(raw_body, self.provider_id)
        output = self.parse_submit_response(data, 200)["output"]
        return output["raw"], output["ext"]

    def parse_error_response(self, status, body):
        # Gemini error envelope: {"error": {"code", "message",
        # "status"}} — _error_detail reads it.
        return super().parse_error_response(status, body)


# ---------------------------------------------------------------------
# fal.ai Model APIs, queue mode (official llms.txt, 2026-11-27)
# ---------------------------------------------------------------------

_FAL_MODELS = (
    "fal-ai/nano-banana-2",
    "google/nano-banana-2.1",
    "fal-ai/flux-2-pro",
    "fal-ai/flux/dev",
)
_FAL_ASPECT_RATIOS = (
    "auto", "21:9", "16:9", "3:2", "4:3", "5:4", "1:1", "4:5", "3:4",
    "2:3", "9:16", "4:1", "1:4", "8:1", "1:8",
)
_FAL_NANO_COMMON = {
    "num_images", "aspect_ratio", "output_format", "resolution",
    "seed", "safety_tolerance", "sync_mode", "system_prompt",
    "limit_generations",
}


class FalImageContract(ProviderContract):
    """fal.ai image models over the queue API.

    POST https://queue.fal.run/{endpoint} with ``Authorization:
    Key``. Submit returns ``{request_id, status_url,
    response_url, cancel_url}``; GET status_url returns
    ``IN_QUEUE`` / ``IN_PROGRESS`` / ``COMPLETED``; GET
    response_url returns the result (``images: [{url, ...}]``);
    PUT cancel_url cancels. Output CDN URLs live on fal.media
    and are kept at least 7 days. Server errors (HTTP 500+) are
    never charged; a 422 may be charged if GPU time was spent;
    ``content_policy_violation`` is a non-retryable 422.

    Reference images: the nano-banana endpoints take references
    through a ``context`` field whose exact part serialization is
    NOT confirmed in the model documentation read, and the
    flux endpoints take no reference input at all — so this
    contract REFUSES reference images with a precise error
    instead of guessing a serialization. The upload-first flow
    (fal storage) is not implemented.
    """

    provider_id = "provider-fal-image"
    is_async = True
    supports_cancel = True
    cancel_method = "PUT"

    def build_request(self, packet, context, model):
        model = _validate_enum(model, "model", _FAL_MODELS)
        prompt = _prompt(packet)
        context = context or {}
        refs = _reference_images(context, 14)
        if refs:
            _fail("fal contract does not support reference images: "
                  "the reference-part serialization is not "
                  "confirmed in the provider documentation and no "
                  "upload flow is implemented")
        body = {"prompt": prompt}
        if model == "fal-ai/nano-banana-2":
            self._nano_fields(body, context, extra={
                "thinking_level": ("minimal", "high"),
                "temperature": (0, 2),
                "top_p": (0, 1),
                "max_output_tokens": (1, 32768),
                "enable_web_search": "bool",
                "enable_image_search": "bool",
            })
            self._resolution(body, context,
                             ("0.5K", "1K", "2K", "4K"))
        elif model == "google/nano-banana-2.1":
            self._nano_fields(body, context, extra={
                "thinking_level": ("minimal", "medium", "high"),
            })
            self._resolution(body, context, ("1K", "2K", "4K"))
        elif model == "fal-ai/flux-2-pro":
            self._flux_fields(body, context, pro=True)
        else:  # fal-ai/flux/dev
            self._flux_fields(body, context, pro=False)
        return {"model": model, "body": body,
                "content_type": "application/json",
                "url_values": {"endpoint": model}, "query": {},
                "headers": {}, "url": None, "context_updates": {}}

    def _nano_fields(self, body, context, extra):
        num_images = context.get("num_images")
        if num_images is not None:
            body["num_images"] = _validate_int(
                num_images, "num_images", minimum=1, maximum=4)
        aspect_ratio = context.get("aspect_ratio")
        if aspect_ratio is not None:
            body["aspect_ratio"] = _validate_enum(
                aspect_ratio, "aspect_ratio", _FAL_ASPECT_RATIOS)
        output_format = context.get("output_format")
        if output_format is not None:
            body["output_format"] = _validate_enum(
                output_format, "output_format",
                ("jpeg", "png", "webp"))
        seed = context.get("seed")
        if seed is not None:
            body["seed"] = _validate_int(seed, "seed")
        tolerance = context.get("safety_tolerance")
        if tolerance is not None:
            body["safety_tolerance"] = _validate_enum(
                str(tolerance), "safety_tolerance",
                ("1", "2", "3", "4", "5", "6"))
        sync_mode = context.get("sync_mode")
        if sync_mode is not None:
            body["sync_mode"] = _validate_bool(sync_mode, "sync_mode")
        system_prompt = context.get("system_prompt")
        if system_prompt is not None:
            body["system_prompt"] = _require_text(
                system_prompt, "system_prompt")
        limit = context.get("limit_generations")
        if limit is not None:
            body["limit_generations"] = _validate_bool(
                limit, "limit_generations")
        for field, spec in extra.items():
            value = context.get(field)
            if value is None:
                continue
            if spec == "bool":
                body[field] = _validate_bool(value, field)
            elif isinstance(spec, tuple) and len(spec) == 2 and all(
                    isinstance(v, (int, float)) for v in spec):
                body[field] = _validate_number(
                    value, field, minimum=spec[0], maximum=spec[1])
            else:
                body[field] = _validate_enum(value, field, spec)

    def _resolution(self, body, context, allowed):
        resolution = context.get("resolution")
        if resolution is not None:
            body["resolution"] = _validate_enum(
                resolution, "resolution", allowed)

    def _flux_fields(self, body, context, pro):
        image_size = context.get("image_size")
        if image_size is not None:
            # The model docs name the field but do not enumerate
            # the ImageSize enum members — accept a non-empty
            # string, do not invent the enum.
            body["image_size"] = _require_text(image_size,
                                               "image_size")
        seed = context.get("seed")
        if seed is not None:
            body["seed"] = _validate_int(seed, "seed")
        tolerance = context.get("safety_tolerance")
        if tolerance is not None:
            allowed = ("1", "2", "3", "4", "5") if pro else (
                "1", "2", "3", "4", "5", "6")
            body["safety_tolerance"] = _validate_enum(
                str(tolerance), "safety_tolerance", allowed)
        checker = context.get("enable_safety_checker")
        if checker is not None:
            body["enable_safety_checker"] = _validate_bool(
                checker, "enable_safety_checker")
        output_format = context.get("output_format")
        if output_format is not None:
            body["output_format"] = _validate_enum(
                output_format, "output_format", ("jpeg", "png"))
        sync_mode = context.get("sync_mode")
        if sync_mode is not None:
            body["sync_mode"] = _validate_bool(sync_mode, "sync_mode")
        if not pro:
            steps = context.get("num_inference_steps")
            if steps is not None:
                body["num_inference_steps"] = _validate_int(
                    steps, "num_inference_steps", minimum=1,
                    maximum=50)
            guidance = context.get("guidance_scale")
            if guidance is not None:
                body["guidance_scale"] = _validate_number(
                    guidance, "guidance_scale", minimum=1,
                    maximum=20)
            num_images = context.get("num_images")
            if num_images is not None:
                body["num_images"] = _validate_int(
                    num_images, "num_images", minimum=1, maximum=4)
            acceleration = context.get("acceleration")
            if acceleration is not None:
                body["acceleration"] = _validate_enum(
                    acceleration, "acceleration",
                    ("none", "regular", "high"))

    def parse_submit_response(self, data, status, context=None):
        request_id = data.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            _fail("fal submit response carried no request_id",
                  code="malformed-output")
        for key in ("status_url", "response_url", "cancel_url"):
            value = data.get(key)
            if not isinstance(value, str) or not value:
                _fail(f"fal submit response carried no {key}",
                      code="malformed-output")
        return {"job_id": request_id,
                "status_url": data["status_url"],
                "cancel_url": data["cancel_url"],
                "response_url": data["response_url"],
                "output": None}

    def parse_poll_response(self, data):
        status = data.get("status")
        if status in ("IN_QUEUE", "IN_PROGRESS"):
            return {"state": "running", "output_url": None,
                    "response_url": None, "error": None}
        if status == "COMPLETED":
            # The result is a second GET on response_url (carried
            # by the status response; the adapter also accepts a
            # context-carried response_url as a fallback).
            return {"state": "done", "output_url": None,
                    "response_url": data.get("response_url"),
                    "error": None}
        # The documented status values are only the three above;
        # anything else is not a state this contract understands.
        _fail(f"fal poll returned unknown status {status!r}",
              code="malformed-output")

    def parse_result_response(self, data):
        detail = _error_detail(data)
        if detail is not None:
            return {"output_url": None, "error": detail}
        images = data.get("images")
        if not isinstance(images, list) or not images:
            _fail("fal result carried no images",
                  code="malformed-output")
        first = images[0]
        if not isinstance(first, dict):
            _fail("fal result carried a malformed image entry",
                  code="malformed-output")
        url = first.get("url")
        if not isinstance(url, str) or not url:
            _fail("fal result carried no output URL",
                  code="malformed-output")
        return {"output_url": url, "error": None}

    def parse_error_response(self, status, body):
        detail = None
        try:
            data = json.loads(body.decode("utf-8"))
            detail = _error_detail(data)
        except (ValueError, UnicodeDecodeError):
            detail = None
        text = body.decode("utf-8", "replace")
        if status == 422 and "content_policy_violation" in text:
            return ("validation-failed",
                    detail or "fal content policy violation", False)
        if status == 422:
            # A 422 may be charged if GPU time was spent.
            return ("provider-error",
                    detail or "fal rejected the request (HTTP 422)",
                    False)
        return _http_error(status, body, self.provider_id,
                           detail=detail)


# ---------------------------------------------------------------------
# fal.ai Kling Video v3 Pro — image-to-video (official fal.ai
# OpenAPI schema, read 2026-11-28)
# ---------------------------------------------------------------------

_FAL_VIDEO_MODELS = (
    "fal-ai/kling-video/v3/pro/image-to-video",
)
_FAL_VIDEO_DURATIONS = tuple(str(n) for n in range(3, 16))
_FAL_VIDEO_START_IMAGE_MAX_BYTES = 50 * 1024 * 1024

# fal.ai platform headers attached to every fal-video request
# (CF-WO-P1-006-R2-PREFLIGHT; fal.ai platform headers doc,
# https://fal.ai/docs/documentation/model-apis/common-parameters,
# and retention / file-access docs, updated 2026-11-17).
#
# - ``X-Fal-Store-IO: 0`` disables request-history payload
#   storage (request payloads are otherwise stored 90 days by
#   default). It does NOT equal ZDR: ZDR is NOT enabled by
#   default, requires sales-team confirmation of availability /
#   coverage, is NOT a single setting, and does NOT disable
#   application logging or app-managed persistent storage.
# - ``X-Fal-Object-Lifecycle-Preference`` is a JSON object
#   ``{"expiration_duration_seconds": <seconds>, "initial_acl":
#   {"default": "allow"|"forbid"|"hide", "rules": [...]}}``.
#   SCOPE: it applies ONLY to files produced on the fal CDN v3
#   (https://v3b.fal.media/...). It does NOT protect a
#   storage.googleapis.com output URL: for this endpoint the
#   model page's own output example is GCS
#   (https://storage.googleapis.com/falserverless/
#   example_outputs/kling-v3/pro-i2v/out.mp4), and GCS outputs
#   are public-by-link.
# - ZDR status for this endpoint: UNCONFIRMED. This runtime
#   never claims ZDR.
FAL_STORE_IO_HEADER = "X-Fal-Store-IO"
FAL_STORE_IO_DISABLED = "0"
FAL_LIFECYCLE_HEADER = "X-Fal-Object-Lifecycle-Preference"
# 7 days, matching the documented fal CDN retention floor
# (>= 7 days). Overridable per request via the context keys
# ``lifecycle_expiration_seconds`` / ``lifecycle_initial_acl``.
FAL_LIFECYCLE_DEFAULT_EXPIRATION_SECONDS = 604800
FAL_LIFECYCLE_DEFAULT_INITIAL_ACL = {"default": "forbid"}
FAL_LIFECYCLE_ACL_DECISIONS = ("allow", "forbid", "hide")
FAL_ZDR_STATUS = "UNCONFIRMED"
FAL_VIDEO_GCS_OUTPUT_EXAMPLE = (
    "https://storage.googleapis.com/falserverless/"
    "example_outputs/kling-v3/pro-i2v/out.mp4")


def fal_retention_headers(context=None):
    """The fal retention headers for one fal-video request.

    Returns ``{header: value}``: ``X-Fal-Store-IO: 0`` plus the
    JSON ``X-Fal-Object-Lifecycle-Preference`` (expiration +
    initial ACL). The caller may override the expiration
    (``lifecycle_expiration_seconds``, a positive integer) and
    the ACL (``lifecycle_initial_acl``, a dict with a
    ``default`` decision of allow/forbid/hide and optional
    ``rules`` of ``{"user", "decision"}``). The header values
    are validated here, never passed through unchecked.
    """
    context = context or {}
    expiration = context.get("lifecycle_expiration_seconds")
    if expiration is None:
        expiration = FAL_LIFECYCLE_DEFAULT_EXPIRATION_SECONDS
    expiration = _validate_int(
        expiration, "lifecycle_expiration_seconds", minimum=1)
    acl = context.get("lifecycle_initial_acl")
    if acl is None:
        acl = dict(FAL_LIFECYCLE_DEFAULT_INITIAL_ACL)
    if not isinstance(acl, dict):
        _fail("lifecycle_initial_acl must be an object with a "
              "'default' decision")
    default = acl.get("default")
    if default not in FAL_LIFECYCLE_ACL_DECISIONS:
        _fail("lifecycle_initial_acl.default must be one of "
              "allow/forbid/hide")
    for key in acl:
        if key not in ("default", "rules"):
            _fail(f"lifecycle_initial_acl carries unknown key "
                  f"{key!r}")
    rules = acl.get("rules")
    if rules is not None:
        if not isinstance(rules, list):
            _fail("lifecycle_initial_acl.rules must be a list")
        for rule in rules:
            if not isinstance(rule, dict) \
                    or not isinstance(rule.get("user"), str) \
                    or not rule.get("user") \
                    or rule.get("decision") \
                    not in FAL_LIFECYCLE_ACL_DECISIONS:
                _fail("lifecycle_initial_acl.rules entries must "
                      "be objects with a non-empty 'user' and a "
                      "'decision' of allow/forbid/hide")
    preference = {"expiration_duration_seconds": expiration,
                  "initial_acl": acl}
    return {FAL_STORE_IO_HEADER: FAL_STORE_IO_DISABLED,
            FAL_LIFECYCLE_HEADER: json.dumps(preference)}


def fal_retention_truth_table():
    """The retention / ACL / ZDR truth table for this endpoint.

    One dict per item: ``item``, ``status`` and ``scope``. The
    runtime never claims more than this table states.
    """
    return [
        {"item": "X-Fal-Store-IO: 0",
         "status": "sent on every fal-video request",
         "scope": "disables request-history payload storage "
                  "(otherwise stored 90 days by default); does "
                  "NOT equal ZDR"},
        {"item": "X-Fal-Object-Lifecycle-Preference "
                 "(expiration + initial_acl)",
         "status": "sent on every fal-video request "
                  "(expiration 7 days, initial_acl default "
                  "forbid, unless overridden per request)",
         "scope": "fal CDN v3 outputs only "
                  "(https://v3b.fal.media/...); does NOT "
                  "protect storage.googleapis.com outputs"},
        {"item": "fal CDN v3 file ACL",
         "status": "controlled per request by initial_acl "
                  "(default forbid: 403 to anyone but the owner)",
         "scope": "fal CDN v3 URLs only; input files uploaded "
                  "before the call keep the account default ACL "
                  "and are NOT covered by the request header"},
        {"item": "GCS output URL "
                 "(storage.googleapis.com/falserverless/...)",
         "status": "public-by-link; no ACL applies",
         "scope": "the model page's own output example for this "
                  "endpoint is GCS, so the fal CDN ACL does NOT "
                  "protect it"},
        {"item": "ZDR (zero data retention)",
         "status": "UNCONFIRMED for this endpoint",
         "scope": "not enabled by default; requires sales-team "
                  "confirmation; is not a single setting; does "
                  "not disable application logging or "
                  "app-managed persistent storage"},
    ]


# KlingV3ComboElementInput fields (official OpenAPI schema for
# this endpoint, read 2026-11-28). ``frontal_image_url`` is the
# main frontal view; ``reference_image_urls`` are additional
# angles (1-3 supported, at least one image required per
# element). ``video_url`` is allowed by the provider on only
# ONE element per request — this production uses image elements
# only, so it is refused here. ``voice_id`` is not used:
# generation runs with ``generate_audio`` false, so there is no
# voice control to bind.
_FAL_VIDEO_ELEMENT_FIELDS = (
    "frontal_image_url", "reference_image_urls", "video_url",
    "voice_id",
)
_FAL_VIDEO_ELEMENT_MAX_REFERENCES = 3
_FAL_VIDEO_ELEMENT_MIN_REFERENCES = 1
_ELEMENT_REF_RE = re.compile(r"@Element(\d+)")


def validate_fal_video_elements(elements, prompt):
    """Validate the ``elements`` array for one fal-video request.

    Returns the exact payload list (one dict per element, in
    prompt-reference order). Public: the I2V runtime reuses this
    validator at plan time so a prompt/elements mismatch blocks
    the plan instead of failing at submission. Every element needs its frontal
    image URL and 1-3 additional reference image URLs; an
    element with neither a frontal nor a reference image is
    refused; ``video_url`` elements and ``voice_id`` are
    refused. The prompt must reference exactly
    ``@Element1``..``@ElementN`` — every element referenced
    once, no reference beyond the array.
    """
    if not isinstance(elements, list) or not elements:
        _fail("fal video elements must be a non-empty list: one "
              "element per character, in prompt-reference order")
    validated = []
    for index, element in enumerate(elements, start=1):
        if not isinstance(element, dict):
            _fail(f"fal video element {index} must be an object")
        for key in element:
            if key not in _FAL_VIDEO_ELEMENT_FIELDS:
                _fail(f"fal video element {index} carries unknown "
                      f"field {key!r}")
        if element.get("video_url") is not None:
            _fail(f"fal video element {index} carries video_url: "
                  "this production uses image elements only — "
                  "the provider allows only one element with a "
                  "video per request, and no video element is "
                  "used here")
        if element.get("voice_id") is not None:
            _fail(f"fal video element {index} carries voice_id: "
                  "voice control is not used — generation runs "
                  "with generate_audio false, so no voice is "
                  "bound to an element")
        frontal = element.get("frontal_image_url")
        references = element.get("reference_image_urls")
        if (not isinstance(frontal, str) or not frontal) \
                and not (isinstance(references, list)
                         and references):
            _fail(f"fal video element {index} has neither a "
                  "frontal image nor a reference image: at least "
                  "one image is required per element")
        if not isinstance(frontal, str) or not frontal:
            _fail(f"fal video element {index} needs "
                  "frontal_image_url: the main frontal view of "
                  "the character")
        if not isinstance(references, list):
            _fail(f"fal video element {index} needs "
                  "reference_image_urls: a list of 1-3 additional "
                  "angle references")
        if len(references) < _FAL_VIDEO_ELEMENT_MIN_REFERENCES:
            _fail(f"fal video element {index} needs at least "
                  f"{_FAL_VIDEO_ELEMENT_MIN_REFERENCES} reference "
                  "image URL: additional angles are required")
        if len(references) > _FAL_VIDEO_ELEMENT_MAX_REFERENCES:
            _fail(f"fal video element {index} carries "
                  f"{len(references)} reference image URLs: at "
                  "most "
                  f"{_FAL_VIDEO_ELEMENT_MAX_REFERENCES} are "
                  "supported")
        for ref in references:
            if not isinstance(ref, str) or not ref:
                _fail(f"fal video element {index} carries an "
                      "empty reference image URL")
        validated.append(
            {"frontal_image_url": frontal,
             "reference_image_urls": list(references)})
    referenced = {int(match) for match in
                  _ELEMENT_REF_RE.findall(prompt or "")}
    expected = set(range(1, len(validated) + 1))
    if referenced != expected:
        missing = sorted(expected - referenced)
        extra = sorted(referenced - expected)
        detail = []
        if missing:
            detail.append("unreferenced elements: " + ", ".join(
                f"@Element{n}" for n in missing))
        if extra:
            detail.append("references beyond the elements array: "
                          + ", ".join(f"@Element{n}" for n in extra))
        _fail("fal video prompt element references do not match "
              "the elements array (" + "; ".join(detail) + "): "
              "the prompt must reference exactly @Element1.."
              f"@Element{len(validated)}")
    return validated


class FalVideoContract(ProviderContract):
    """fal.ai Kling Video v3 Pro image-to-video over the queue API.

    POST https://queue.fal.run/fal-ai/kling-video/v3/pro/
    image-to-video with ``Authorization: Key``. Submit returns
    ``{request_id, status_url, response_url, cancel_url}``; GET
    status_url returns ``IN_QUEUE`` / ``IN_PROGRESS`` /
    ``COMPLETED``; GET response_url returns the result
    (``video: {url, content_type, file_size, file_name}``); PUT
    cancel_url cancels. Output URLs for this endpoint land on
    Google Cloud Storage under ``/falserverless/`` (per the
    model page's own output example) — the fal CDN origin
    (``v3b.fal.media``) is also permitted where actually used;
    fal CDN files are kept at least 7 days. Server errors
    (HTTP 500+) are never charged; a 422 may be charged if GPU
    time was spent; ``content_policy_violation`` is a
    non-retryable 422.

    Request schema (fal.ai OpenAPI for this endpoint, read
    2026-11-28): ``start_image_url`` is the only required field
    (public URL or base64 data URI, <=50 MB, >=300x300 px,
    aspect 0.40-2.50); ``prompt`` <=2500 chars (either prompt or
    multi_prompt, never both); ``duration`` is a string enum
    "3"-"15" (default "5"); ``generate_audio`` defaults true
    (native audio; Chinese and English voice output — other
    languages are auto-translated to English); ``end_image_url``
    optional; ``elements`` is a list of KlingV3ComboElementInput
    (``frontal_image_url`` required, ``reference_image_urls``
    1-3 additional angles, at least one image per element; the
    prompt references them as ``@Element1``, ``@Element2``, ...;
    ``video_url`` only on one element per request — refused
    here, this production uses image elements only;
    ``voice_id`` unused — generation runs with
    ``generate_audio`` false); ``negative_prompt`` <=2500 chars
    (default "blur, distort, and low quality"); ``cfg_scale``
    0-1 (default 0.5); ``enable_safety_checker`` defaults
    true. There is NO aspect-ratio or resolution field: the
    output follows the start image's aspect (a 9:16 keyframe
    yields a 9:16 clip) at up to 1080p.

    ``multi_prompt`` is a DESIGN RESTRICTION, not a provider
    gap: the provider documents it, but this production builds
    one shot per generation with a single prompt, so
    ``multi_prompt`` is intentionally unused and a context
    carrying it is refused with that reason.

    Retention headers (every request): ``X-Fal-Store-IO: 0``
    and ``X-Fal-Object-Lifecycle-Preference`` — see
    :func:`fal_retention_headers` and
    :func:`fal_retention_truth_table`. ZDR is UNCONFIRMED for
    this endpoint and is never claimed.

    Output URLs for this endpoint land on Google Cloud Storage
    (``https://storage.googleapis.com/falserverless/...``, per
    the model page's own output example), NOT on the fal CDN —
    so the fal CDN ACL does not protect them and they are
    public-by-link. The URL policy permits that one GCS path
    prefix for this provider/model contract only.
    """

    provider_id = "provider-fal-video"
    is_async = True
    supports_cancel = True
    cancel_method = "PUT"

    def build_request(self, packet, context, model):
        model = _validate_enum(model, "model", _FAL_VIDEO_MODELS)
        prompt = _prompt(packet)
        if len(prompt) > 2500:
            _fail("fal video prompt must be at most 2500 "
                  "characters")
        context = context or {}
        elements = context.get("elements")
        if elements is not None:
            elements = validate_fal_video_elements(elements, prompt)
        if context.get("multi_prompt") is not None:
            _fail("fal video contract does not use multi_prompt: "
                  "this is an intentional design restriction — "
                  "one shot is one generation with a single "
                  "prompt, so multi_prompt is unused even though "
                  "the provider documents the field")
        start_image_url = context.get("start_image_url")
        if not isinstance(start_image_url, str) \
                or not start_image_url:
            _fail("fal video request needs start_image_url: the "
                  "verified keyframe as a public URL or a base64 "
                  "data URI")
        body = {"prompt": prompt,
                "start_image_url": start_image_url}
        duration = context.get("duration")
        if duration is not None:
            body["duration"] = _validate_enum(
                str(duration), "duration", _FAL_VIDEO_DURATIONS)
        audio = context.get("generate_audio")
        if audio is not None:
            body["generate_audio"] = _validate_bool(
                audio, "generate_audio")
        end_image_url = context.get("end_image_url")
        if end_image_url is not None:
            if not isinstance(end_image_url, str) \
                    or not end_image_url:
                _fail("fal video end_image_url must be a "
                      "non-empty string")
            body["end_image_url"] = end_image_url
        negative = context.get("negative_prompt")
        if negative is not None:
            negative = _require_text(negative, "negative_prompt",
                                     max_len=2500)
            body["negative_prompt"] = negative
        cfg = context.get("cfg_scale")
        if cfg is not None:
            body["cfg_scale"] = _validate_number(
                cfg, "cfg_scale", minimum=0, maximum=1)
        checker = context.get("enable_safety_checker")
        if checker is not None:
            body["enable_safety_checker"] = _validate_bool(
                checker, "enable_safety_checker")
        if elements is not None:
            body["elements"] = elements
        return {"model": model, "body": body,
                "content_type": "application/json",
                "url_values": {"endpoint": model}, "query": {},
                # Retention headers, every request (see the
                # module constants above for scope): Store-IO 0
                # disables request-history payload storage; the
                # lifecycle preference sets fal CDN v3 retention
                # + ACL. Neither is ZDR, and ZDR is UNCONFIRMED.
                "headers": fal_retention_headers(context),
                "url": None, "context_updates": {}}

    def parse_submit_response(self, data, status, context=None):
        request_id = data.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            _fail("fal video submit response carried no "
                  "request_id", code="malformed-output")
        for key in ("status_url", "response_url", "cancel_url"):
            value = data.get(key)
            if not isinstance(value, str) or not value:
                _fail(f"fal video submit response carried no {key}",
                      code="malformed-output")
        return {"job_id": request_id,
                "status_url": data["status_url"],
                "cancel_url": data["cancel_url"],
                "response_url": data["response_url"],
                "output": None}

    def parse_poll_response(self, data):
        status = data.get("status")
        if status in ("IN_QUEUE", "IN_PROGRESS"):
            return {"state": "running", "output_url": None,
                    "response_url": None, "error": None}
        if status == "COMPLETED":
            # The result is a second GET on response_url (carried
            # by the status response; the adapter also accepts a
            # context-carried response_url as a fallback).
            return {"state": "done", "output_url": None,
                    "response_url": data.get("response_url"),
                    "error": None}
        # The documented status values are only the three above;
        # anything else is not a state this contract understands.
        _fail(f"fal video poll returned unknown status {status!r}",
              code="malformed-output")

    def parse_result_response(self, data):
        detail = _error_detail(data)
        if detail is not None:
            return {"output_url": None, "error": detail}
        video = data.get("video")
        if not isinstance(video, dict):
            _fail("fal video result carried no video object",
                  code="malformed-output")
        url = video.get("url")
        if not isinstance(url, str) or not url:
            _fail("fal video result carried no output URL",
                  code="malformed-output")
        return {"output_url": url, "error": None}

    def parse_error_response(self, status, body):
        detail = None
        try:
            data = json.loads(body.decode("utf-8"))
            detail = _error_detail(data)
        except (ValueError, UnicodeDecodeError):
            detail = None
        text = body.decode("utf-8", "replace")
        if status == 422 and "content_policy_violation" in text:
            return ("validation-failed",
                    detail or "fal content policy violation", False)
        if status == 422:
            # A 422 may be charged if GPU time was spent.
            return ("provider-error",
                    detail or "fal rejected the request (HTTP 422)",
                    False)
        return _http_error(status, body, self.provider_id,
                           detail=detail)


# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# Veo 3.1 via Vertex AI / Gemini Enterprise Agent Platform
# (official Vertex docs, 2026-11-27 — see PROVIDER_ADAPTERS.md)
# ---------------------------------------------------------------------

_VEO_MODELS = (
    "veo-3.1-generate-001",
    "veo-3.1-fast-generate-001",
    "veo-3.1-lite-generate-001",
)
_VEO_API_HOST = "us-central1-aiplatform.googleapis.com"
_VEO_IMAGE_MAX_BYTES = 20 * 1024 * 1024
_VERTEX_PROJECT_RE = re.compile(
    r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_VEO_OPERATION_ID_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _validate_vertex_project_id(value):
    """A GCP project id (6-30 chars: lowercase letters, digits,
    hyphens; starts with a letter, never ends with a hyphen)."""
    if not isinstance(value, str) \
            or not _VERTEX_PROJECT_RE.match(value):
        _fail("vertex_project_id must be a GCP project id "
              "(6-30 characters: lowercase letters, digits, "
              "hyphens; starts with a letter, never ends with "
              "a hyphen)")
    return value


def _validate_veo_operation_name(name):
    """A Vertex Veo operation name, split into its parts.

    Returns ``(project, model, operation_id)``. The documented
    form is ``projects/<project>/locations/us-central1/
    publishers/google/models/<model>/operations/<id>`` — the
    FULL operation name is the job id.
    """
    if not isinstance(name, str) or not name:
        _fail("Veo operation name is required",
              code="malformed-output")
    parts = name.split("/")
    if len(parts) != 10 or parts[0] != "projects" \
            or parts[2] != "locations" \
            or parts[3] != "us-central1" \
            or parts[4] != "publishers" or parts[5] != "google" \
            or parts[6] != "models" or parts[8] != "operations":
        _fail("Veo operation name is not in the documented "
              "Vertex form 'projects/<project>/locations/"
              "us-central1/publishers/google/models/<model>/"
              "operations/<id>'", code="malformed-output")
    project = parts[1]
    if not _VERTEX_PROJECT_RE.match(project):
        _fail("Veo operation name carries an invalid project id",
              code="malformed-output")
    model = parts[7]
    if model not in _VEO_MODELS:
        _fail(f"Veo operation names a model this contract does "
              f"not serve: {model!r}", code="malformed-output")
    operation_id = parts[9]
    if not _VEO_OPERATION_ID_RE.match(operation_id):
        _fail("Veo operation id is not a safe URL path token",
              code="malformed-output")
    return project, model, operation_id


def _veo_fetch_url(project, model):
    return ("https://" + _VEO_API_HOST + "/v1/projects/" + project
            + "/locations/us-central1/publishers/google/models/"
            + model + ":fetchPredictOperation")


class VeoVideoContract(ProviderContract):
    """Veo 3.1 video generation via Vertex AI.

    POST ``/v1/projects/{project}/locations/us-central1/
    publishers/google/models/{model}:predictLongRunning`` with
    an OAuth Bearer token (``VERTEX_ACCESS_TOKEN`` — never an
    API key), then POST ``.../models/{model}:
    fetchPredictOperation`` with ``{"operationName": "<full
    operation name>"}`` in the body until ``done``. The submit
    response returns the full operation name
    (``projects/<project>/locations/us-central1/publishers/
    google/models/<model>/operations/<id>``) — that name is the
    job id, and the poll URL is rebuilt from it. Completion
    carries ``response.videos[0]``: inline video bytes
    (``bytesBase64Encoded``) when no ``storageUri`` was set, or
    a GCS URI (``gcsUri``) — a GCS URI output is refused
    explicitly because no GCS download origin is documented in
    the audit (UNCONFIRMED). No cancel operation is
    documented. The Gemini API Veo preview model IDs
    (``veo-3.1-generate-preview`` and siblings) were shut down
    2026-10-22 and are refused here. Constraints: us-central1
    only, 1-4 outputs, 4/6/8 s, 24 fps, at most 3 reference
    images (Standard/Fast only), image input at most 20 MB.
    Pricing is per "1 count" (the official unit; the pricing
    page does not define 1 count) — no per-second price is
    encoded. UNCONFIRMED: Fast 4K (pricing lists it, model
    page does not); Lite image input (model page "Not
    supported" vs capabilities row "Supported"); GA-ID
    retirement wording.
    """

    provider_id = "provider-veo-video"
    is_async = True
    supports_cancel = False

    def build_request(self, packet, context, model):
        model = _validate_enum(model, "model", _VEO_MODELS)
        prompt = _prompt(packet)
        context = context or {}
        project = _validate_vertex_project_id(
            context.get("vertex_project_id"))
        first = _single_reference(context, "first_frame")
        last = _single_reference(context, "last_frame")
        refs = _reference_images(context, 3)
        for ref in [first, last] + refs:
            if ref is not None \
                    and len(ref["bytes"]) > _VEO_IMAGE_MAX_BYTES:
                _fail("Veo reference image exceeds the 20 MB "
                      "input limit")
        if model == "veo-3.1-lite-generate-001" and refs:
            _fail("reference images on "
                  "veo-3.1-lite-generate-001 are UNCONFIRMED "
                  "(Vertex docs conflict: model page says not "
                  "supported, capabilities row says supported); "
                  "refused until confirmed")
        instance = {"prompt": prompt}
        if first is not None:
            instance["image"] = {
                "bytesBase64Encoded": first["base64"],
                "mimeType": first["mime"]}
        if last is not None:
            instance["lastFrame"] = {
                "bytesBase64Encoded": last["base64"],
                "mimeType": last["mime"]}
        if refs:
            instance["referenceImages"] = [
                {"image": {"bytesBase64Encoded": ref["base64"],
                           "mimeType": ref["mime"]},
                 "referenceType": "asset"}
                for ref in refs]
        aspect_ratio = context.get("aspect_ratio", "16:9")
        _validate_enum(aspect_ratio, "aspect_ratio", ("16:9", "9:16"))
        resolution = context.get("resolution", "720p")
        _validate_enum(resolution, "resolution",
                       ("720p", "1080p", "4k"))
        duration = context.get("duration_seconds", 8)
        if isinstance(duration, int) and not isinstance(duration,
                                                       bool):
            duration = str(duration)
        _validate_enum(duration, "duration_seconds", ("4", "6", "8"))
        if resolution in ("1080p", "4k") and duration != "8":
            _fail("1080p and 4K renders require 8 seconds")
        if resolution == "4k" and model == (
                "veo-3.1-lite-generate-001"):
            _fail("4K is not available on "
                  "veo-3.1-lite-generate-001")
        if resolution == "4k" and model == (
                "veo-3.1-fast-generate-001"):
            _fail("4K on veo-3.1-fast-generate-001 is "
                  "UNCONFIRMED (pricing lists it, model page "
                  "does not); refused until confirmed")
        if refs and duration != "8":
            _fail("reference images require an 8 second clip")
        parameters = {"aspectRatio": aspect_ratio,
                      "resolution": resolution,
                      "durationSeconds": duration,
                      "sampleCount": 1}
        num_videos = context.get("num_videos")
        if num_videos is not None:
            parameters["sampleCount"] = _validate_int(
                num_videos, "num_videos", minimum=1, maximum=4)
        negative = context.get("negative_prompt")
        if negative is not None:
            parameters["negativePrompt"] = _require_text(
                negative, "negative_prompt")
        seed = context.get("seed")
        if seed is not None:
            parameters["seed"] = _validate_int(seed, "seed")
        return {"model": model,
                "body": {"instances": [instance],
                         "parameters": parameters},
                "content_type": "application/json",
                "url_values": {"model": model,
                               "project_id": project},
                "query": {},
                "headers": {}, "url": None, "context_updates": {}}

    def parse_submit_response(self, data, status, context=None):
        name = data.get("name")
        _validate_veo_operation_name(name)
        return {"job_id": name,
                "status_url": None,
                "cancel_url": None, "response_url": None,
                "output": None}

    def build_poll_url(self, job_id, context):
        project, model, _op = _validate_veo_operation_name(job_id)
        return _veo_fetch_url(project, model)

    def build_poll_request(self, job_id, context):
        url = self.build_poll_url(job_id, context)
        return ("POST", url, {"operationName": job_id})

    def parse_poll_response(self, data):
        done = data.get("done")
        if done is not True and done is not False:
            _fail("Veo poll response carried no 'done' flag",
                  code="malformed-output")
        if not done:
            return {"state": "running", "output_url": None,
                    "response_url": None, "error": None,
                    "output": None}
        error = data.get("error")
        if isinstance(error, dict):
            message = error.get("message") or "Veo job failed"
            status_text = str(error.get("status") or "")
            code = error.get("code")
            if status_text.upper() == "CANCELLED" or code == 499:
                return {"state": "cancelled", "output_url": None,
                        "response_url": None, "error": str(message),
                        "output": None}
            return {"state": "failed", "output_url": None,
                    "response_url": None, "error": str(message),
                    "output": None}
        response = data.get("response") or {}
        videos = response.get("videos")
        if not isinstance(videos, list) or not videos:
            _fail("Veo operation completed without generated "
                  "videos", code="malformed-output")
        video = videos[0]
        if not isinstance(video, dict):
            _fail("Veo operation completed without a video "
                  "record", code="malformed-output")
        inline = video.get("bytesBase64Encoded")
        if isinstance(inline, str) and inline:
            raw = _strict_b64(inline, "Veo video bytes")
            return {"state": "done", "output_url": None,
                    "response_url": None, "error": None,
                    "output": {"raw": raw, "ext": ".mp4"}}
        uri = video.get("gcsUri")
        if isinstance(uri, str) and uri:
            _fail("Veo operation completed with a GCS URI "
                  "output; the GCS download origin is "
                  "UNCONFIRMED, so the output cannot be "
                  "retrieved — request inline bytes (no "
                  "storageUri) or confirm the download origin "
                  "first", code="validation-failed")
        _fail("Veo operation completed without a video output",
              code="malformed-output")


# Kling AI video, legacy /v1 design (secondary sources quoting the
# official docs, 2026-11-27)
# ---------------------------------------------------------------------

_KLING_T2V_MODELS = (
    "kling-v1", "kling-v1-6", "kling-v2-master",
    "kling-v2-1-master", "kling-v2-5-turbo", "kling-v2-6",
)
_KLING_I2V_MODELS = _KLING_T2V_MODELS + ("kling-v1-5", "kling-v2-1")
_KLING_MAX_PROMPT = 2500
_KLING_IMAGE_MAX_BYTES = 10 * 1024 * 1024


def _validate_camera_control(value):
    if not isinstance(value, dict):
        _fail("camera_control must be an object")
    control_type = value.get("type")
    presets = ("down_back", "forward_up", "right_turn_forward",
               "left_turn_forward")
    if control_type == "simple":
        config = value.get("config")
        if not isinstance(config, dict):
            _fail("camera_control 'simple' needs a config object")
        axes = ("horizontal", "vertical", "pan", "tilt", "roll",
                "zoom")
        non_zero = [axis for axis in axes
                    if config.get(axis) not in (None, 0)]
        if len(non_zero) != 1:
            _fail("camera_control config needs exactly one "
                  "non-zero axis")
        for axis in axes:
            axis_value = config.get(axis)
            if axis_value is not None:
                _validate_number(axis_value,
                                 f"camera_control.config.{axis}",
                                 minimum=-10, maximum=10)
        return {"type": "simple", "config": config}
    if control_type in presets:
        if value.get("config") is not None:
            _fail("camera_control preset type needs config null")
        return {"type": control_type, "config": None}
    _fail("camera_control type must be 'simple' or a documented "
          "preset")


class KlingVideoContract(ProviderContract):
    """Kling AI video generation, legacy /v1 design.

    POST https://api-singapore.klingai.com/v1/videos/text2video
    (or image2video with a reference image), then GET
    /v1/videos/{text2video|image2video}/{task_id}. Submit
    returns ``{code: 0, data: {task_id, task_status, ...}}``;
    poll statuses are submitted / processing / succeed / failed
    and the output is ``data.task_result.videos[0].url`` (result
    URLs are cleared 30 days after the task). No cancel endpoint
    is documented. Legacy auth is a short-lived HS256 JWT minted
    from the Access Key + Secret Key; this runtime does NOT mint
    it — the configured credential is sent as-is as the Bearer
    token. The newer path-based design (Kling 4.0 etc.) is NOT
    implemented: its prompt field was UNCONFIRMED at audit time.
    """

    provider_id = "provider-kling-video"
    is_async = True
    supports_cancel = False

    def build_request(self, packet, context, model):
        context = context or {}
        refs = _reference_images(context, 2)
        image_to_video = bool(refs)
        if image_to_video:
            model = _validate_enum(model, "model",
                                   _KLING_I2V_MODELS)
        else:
            model = _validate_enum(
                model or "kling-v1", "model", _KLING_T2V_MODELS)
        prompt = (packet or {}).get("canonical_instruction", "")
        if image_to_video:
            prompt = _optional_text(prompt, "prompt",
                                    max_len=_KLING_MAX_PROMPT)
        else:
            prompt = _require_text(prompt, "prompt",
                                   max_len=_KLING_MAX_PROMPT)
        body = {"model_name": model}
        if prompt:
            body["prompt"] = prompt
        negative = context.get("negative_prompt")
        if negative is not None:
            body["negative_prompt"] = _require_text(
                negative, "negative_prompt",
                max_len=_KLING_MAX_PROMPT)
        sound = context.get("sound")
        if sound is not None:
            _validate_enum(sound, "sound", ("on", "off"))
            if sound == "on" and model != "kling-v2-6":
                _fail("sound is supported only by kling-v2-6 and "
                      "later (secondary-quoted)")
            body["sound"] = sound
        cfg_scale = context.get("cfg_scale")
        if cfg_scale is not None:
            if model.startswith("kling-v2"):
                _fail("cfg_scale is not supported by kling-v2.x "
                      "models")
            body["cfg_scale"] = _validate_number(
                cfg_scale, "cfg_scale", minimum=0, maximum=1)
        mode = context.get("mode")
        if mode is not None:
            body["mode"] = _validate_enum(mode, "mode",
                                          ("std", "pro"))
        camera_control = context.get("camera_control")
        if camera_control is not None:
            if image_to_video:
                _fail("camera_control is mutually exclusive with "
                      "image-to-video inputs")
            body["camera_control"] = _validate_camera_control(
                camera_control)
        aspect_ratio = context.get("aspect_ratio")
        if aspect_ratio is not None:
            body["aspect_ratio"] = _validate_enum(
                aspect_ratio, "aspect_ratio",
                ("16:9", "9:16", "1:1"))
        duration = context.get("duration_seconds", 5)
        if isinstance(duration, int) and not isinstance(duration,
                                                       bool):
            duration = str(duration)
        _validate_enum(duration, "duration_seconds", ("5", "10"))
        body["duration"] = duration
        callback_url = context.get("callback_url")
        if callback_url is not None:
            body["callback_url"] = _require_text(callback_url,
                                                "callback_url")
        external_task_id = context.get("external_task_id")
        if external_task_id is not None:
            body["external_task_id"] = _require_text(
                external_task_id, "external_task_id")
        kind = "image2video" if image_to_video else "text2video"
        if image_to_video:
            first = refs[0]
            if len(first["bytes"]) > _KLING_IMAGE_MAX_BYTES:
                _fail("Kling reference images must be under 10 MB")
            # Legacy image-to-video takes base64 WITHOUT the
            # data: URI prefix, or an accessible URL.
            body["image"] = first["base64"]
            if len(refs) > 1:
                body["image_tail"] = refs[1]["base64"]
        url = ("https://api-singapore.klingai.com/v1/videos/"
               + kind)
        return {"model": model, "body": body,
                "content_type": "application/json",
                "url_values": {}, "query": {}, "headers": {},
                "url": url,
                "context_updates": {"endpoint": kind}}

    def parse_submit_response(self, data, status, context=None):
        code = data.get("code")
        if code != 0:
            message = data.get("message") or "Kling submit failed"
            _fail(f"Kling submit failed: {message}",
                  code="provider-error")
        inner = data.get("data")
        if not isinstance(inner, dict):
            _fail("Kling submit response carried no data",
                  code="malformed-output")
        task_id = inner.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            _fail("Kling submit response carried no task_id",
                  code="malformed-output")
        kind = (context or {}).get("endpoint") or "text2video"
        return {"job_id": task_id,
                "status_url": "https://api-singapore.klingai.com/"
                              "v1/videos/" + kind + "/" + task_id,
                "cancel_url": None, "response_url": None,
                "output": None}

    def build_poll_url(self, job_id, context):
        kind = (context or {}).get("endpoint") or "text2video"
        if kind not in ("text2video", "image2video"):
            _fail("Kling poll endpoint must be text2video or "
                  "image2video")
        return ("https://api-singapore.klingai.com/v1/videos/"
                + kind + "/" + job_id)

    def parse_poll_response(self, data):
        code = data.get("code")
        if code is not None and code != 0:
            message = data.get("message") or "Kling poll failed"
            return {"state": "failed", "output_url": None,
                    "response_url": None, "error": str(message)}
        inner = data.get("data")
        if not isinstance(inner, dict):
            _fail("Kling poll response carried no data",
                  code="malformed-output")
        task_status = inner.get("task_status")
        if task_status in ("submitted", "processing"):
            return {"state": "running", "output_url": None,
                    "response_url": None, "error": None}
        if task_status == "succeed":
            result = inner.get("task_result") or {}
            videos = result.get("videos")
            if not isinstance(videos, list) or not videos:
                _fail("Kling job succeeded without a video URL",
                      code="malformed-output")
            first = videos[0]
            if not isinstance(first, dict):
                _fail("Kling job succeeded with a malformed video "
                      "entry", code="malformed-output")
            url = first.get("url")
            if not isinstance(url, str) or not url:
                _fail("Kling job succeeded without a video URL",
                      code="malformed-output")
            return {"state": "done", "output_url": url,
                    "response_url": None, "error": None}
        if task_status == "failed":
            message = (inner.get("task_status_msg")
                       or "Kling job failed")
            return {"state": "failed", "output_url": None,
                    "response_url": None, "error": str(message)}
        _fail(f"Kling poll returned unknown task_status "
              f"{task_status!r}", code="malformed-output")


# ---------------------------------------------------------------------
# LTX API v2 (official docs, direct read 2026-11-27)
# ---------------------------------------------------------------------

_LTX_MODELS = (
    "ltx-2-5-fast", "ltx-2-5-pro", "ltx-2-3-fast", "ltx-2-3-pro",
)
_LTX_ENDPOINTS = ("text-to-video", "image-to-video",
                  "audio-to-video")
_LTX_IMAGE_MAX_BYTES = 7 * 1024 * 1024
_LTX_AUDIO_MAX_BYTES = 15 * 1024 * 1024


def _ltx_resolution_class(width, height):
    return "high" if height > 1080 else "low"


def _ltx_allowed_durations(model, width, height, fps):
    if model in ("ltx-2-5-pro", "ltx-2-3-pro"):
        return {6, 8, 10}
    if _ltx_resolution_class(width, height) == "high":
        return {6, 8, 10}
    if fps in (48, 50):
        return {6, 8, 10}
    return {6, 8, 10, 12, 14, 16, 18, 20}


def _ltx_aspect_ok(model, width, height):
    ratio = width / height
    targets = (16 / 9, 9 / 16, 1.0, 3 / 2, 2 / 3)
    if model.startswith("ltx-2-3"):
        targets = (16 / 9, 9 / 16)
    return any(abs(ratio - target) <= 0.01 for target in targets)


class LTXVideoContract(ProviderContract):
    """LTX API v2 (async only; V1 retired 2026-10-26).

    POST /v2/{text-to-video|image-to-video|audio-to-video}
    returns 202 ``{id, created_at}``; GET /v2/{endpoint}/{id}
    returns statuses pending / processing / completed / failed
    (completed carries ``result.video_url``; failed carries
    ``error: {type, message}``). The signed video_url expires 1
    hour after it is checked — re-check the job for a fresh URL;
    job status is available up to 24 h after the terminal state.
    Media inputs are ``ltx://`` upload URIs, public HTTPS URLs,
    or base64 data URIs (images <= 7 MB, video/audio <= 15 MB;
    whole JSON body <= 32 MB). Prepaid credits are reserved
    before generation and charged only on success; a failed job
    releases its reservation. No cancel endpoint was found in
    the official docs (UNCONFIRMED).
    """

    provider_id = "provider-ltx-video"
    is_async = True
    supports_cancel = False

    def build_request(self, packet, context, model):
        model = _validate_enum(model, "model", _LTX_MODELS)
        context = context or {}
        endpoint = context.get("endpoint", "text-to-video")
        _validate_enum(endpoint, "endpoint", _LTX_ENDPOINTS)
        prompt = (packet or {}).get("canonical_instruction", "")
        body = {"model": model}
        first = _single_reference(context, "first_frame")
        last = _single_reference(context, "last_frame")
        audio = _single_reference(context, "reference_audio")
        if endpoint == "text-to-video":
            body["prompt"] = _require_text(prompt, "prompt")
        elif endpoint == "image-to-video":
            if first is None:
                _fail("LTX image-to-video needs a first-frame "
                      "image (first_frame)")
            if len(first["bytes"]) > _LTX_IMAGE_MAX_BYTES:
                _fail("LTX reference images must be under 7 MB")
            body["image_uri"] = _data_uri(first)
            if prompt:
                body["prompt"] = _require_text(prompt, "prompt")
        else:  # audio-to-video
            if audio is None:
                _fail("LTX audio-to-video needs reference audio "
                      "(reference_audio)")
            if len(audio["bytes"]) > _LTX_AUDIO_MAX_BYTES:
                _fail("LTX audio inputs must be under 15 MB")
            body["audio_uri"] = _data_uri(audio)
            if first is None and not prompt:
                _fail("LTX audio-to-video needs a first-frame "
                      "image or a prompt")
            if first is not None:
                if len(first["bytes"]) > _LTX_IMAGE_MAX_BYTES:
                    _fail("LTX reference images must be under 7 MB")
                body["image_uri"] = _data_uri(first)
            if prompt:
                body["prompt"] = _require_text(prompt, "prompt")
        if last is not None:
            if first is None:
                _fail("LTX last_frame_uri requires a first-frame "
                      "image")
            body["last_frame_uri"] = _data_uri(last)
        resolution = context.get("resolution")
        if resolution is None:
            _fail("LTX resolution is required ('WIDTHxHEIGHT')")
        match = re.fullmatch(r"(\d+)x(\d+)", str(resolution))
        if not match:
            _fail("LTX resolution must be 'WIDTHxHEIGHT'")
        width, height = int(match.group(1)), int(match.group(2))
        if width <= 0 or height <= 0:
            _fail("LTX resolution dimensions must be positive")
        if not _ltx_aspect_ok(model, width, height):
            _fail("LTX resolution aspect ratio is not supported "
                  "by this model")
        body["resolution"] = f"{width}x{height}"
        fps = context.get("fps", 24)
        _validate_enum(fps, "fps", (24, 25, 48, 50))
        body["fps"] = fps
        if endpoint != "audio-to-video":
            # Absent and explicit null are different: absent is a
            # missing required field; null requests automatic
            # duration (ltx-2-5-fast/pro only).
            _missing = object()
            duration = context.get("duration", _missing)
            if duration is _missing:
                _fail("LTX duration is required (a number of "
                      "seconds, or null for automatic duration on "
                      "ltx-2-5-fast/pro only)")
            if duration is None:
                if model not in ("ltx-2-5-fast", "ltx-2-5-pro"):
                    _fail("automatic (null) duration is supported "
                          "only by ltx-2-5-fast/pro")
                body["duration"] = None
            else:
                _validate_number(duration, "duration")
                if int(duration) != duration:
                    _fail("LTX duration must be a whole number of "
                          "seconds")
                allowed = _ltx_allowed_durations(model, width,
                                                 height, fps)
                if int(duration) not in allowed:
                    _fail(f"LTX duration {int(duration)}s is not "
                          f"supported by {model} at "
                          f"{width}x{height} {fps}fps "
                          f"(allowed: {sorted(allowed)})")
                body["duration"] = int(duration)
        generate_audio = context.get("generate_audio")
        if generate_audio is not None:
            body["generate_audio"] = _validate_bool(
                generate_audio, "generate_audio")
        camera_motion = context.get("camera_motion")
        if camera_motion is not None:
            body["camera_motion"] = _require_text(
                camera_motion, "camera_motion")
        return {"model": model, "body": body,
                "content_type": "application/json",
                "url_values": {"endpoint": endpoint}, "query": {},
                "headers": {}, "url": None,
                "context_updates": {"endpoint": endpoint}}

    def parse_submit_response(self, data, status, context=None):
        job_id = data.get("id")
        if not isinstance(job_id, str) or not job_id:
            _fail("LTX submit response carried no job id",
                  code="malformed-output")
        endpoint = (context or {}).get("endpoint") or "text-to-video"
        return {"job_id": job_id,
                "status_url": "https://api.ltx.io/v2/" + endpoint
                              + "/" + job_id,
                "cancel_url": None, "response_url": None,
                "output": None}

    def build_poll_url(self, job_id, context):
        endpoint = (context or {}).get("endpoint") or "text-to-video"
        _validate_enum(endpoint, "endpoint", _LTX_ENDPOINTS)
        return ("https://api.ltx.io/v2/" + endpoint + "/" + job_id)

    def parse_poll_response(self, data):
        status = data.get("status")
        if status in ("pending", "processing"):
            return {"state": "running", "output_url": None,
                    "response_url": None, "error": None}
        if status == "completed":
            result = data.get("result") or {}
            url = result.get("video_url")
            if not isinstance(url, str) or not url:
                _fail("LTX job completed without a video_url",
                      code="malformed-output")
            return {"state": "done", "output_url": url,
                    "response_url": None, "error": None}
        if status == "failed":
            error = data.get("error") or {}
            message = (error.get("message")
                       or error.get("type")
                       or "LTX job failed")
            return {"state": "failed", "output_url": None,
                    "response_url": None, "error": str(message)}
        _fail(f"LTX poll returned unknown status {status!r}",
              code="malformed-output")

    def parse_error_response(self, status, body):
        # LTX error types (official docs): authentication_error,
        # content_filtered_error, insufficient_funds_error,
        # rate_limit_error, request_too_large_error.
        detail = None
        try:
            data = json.loads(body.decode("utf-8"))
            detail = _error_detail(data)
            error_type = (data.get("error") or {}).get("type") \
                if isinstance(data.get("error"), dict) else None
        except (ValueError, UnicodeDecodeError):
            error_type = None
        if error_type == "content_filtered_error":
            return ("validation-failed",
                    detail or "LTX content filter refused the "
                             "request", False)
        if error_type == "insufficient_funds_error":
            return ("authorization-denied",
                    detail or "LTX account has insufficient funds",
                    False)
        if error_type == "request_too_large_error":
            return ("validation-failed",
                    detail or "LTX request exceeds the size limit",
                    False)
        return super().parse_error_response(status, body)


# ---------------------------------------------------------------------
# ElevenLabs text-to-speech REST v1 (secondary sources quoting the
# official docs, 2026-11-27)
# ---------------------------------------------------------------------

_ELEVENLABS_MODELS = (
    "eleven_v4", "eleven_v4_turbo", "eleven_v3",
    "eleven_multilingual_v2", "eleven_flash_v2_5",
)
_ELEVENLABS_V4_MAX_CHARS = 100000


class ElevenLabsVoiceContract(ProviderContract):
    """ElevenLabs text-to-speech, synchronous.

    POST /v1/text-to-speech/{voice_id}?output_format=... with
    header ``xi-api-key``. Body: ``text`` (required),
    ``model_id``, ``voice_settings`` (stability,
    similarity_boost, style, speed, use_speaker_boost),
    ``language_code``, ``seed``, ``previous_text`` /
    ``next_text``, ``pronunciation_dictionary_locators``,
    ``apply_text_normalization``. Response is raw audio bytes
    (default MP3). No job, no polling, no documented cancel
    endpoint. eleven_v4 accepts up to 100,000 characters per
    request (official docs); the other models' per-request
    character limits are SECONDARY-quoted and are NOT enforced
    here. eleven_v4 supports only stability + similarity_boost
    in voice_settings (SECONDARY-quoted).
    """

    provider_id = "provider-elevenlabs-voice"
    is_async = False

    def build_request(self, packet, context, model):
        model = _validate_enum(model, "model", _ELEVENLABS_MODELS)
        text = _prompt(packet)
        if model == "eleven_v4" and len(text) > _ELEVENLABS_V4_MAX_CHARS:
            _fail("eleven_v4 accepts at most 100,000 characters "
                  "per request")
        context = context or {}
        voice_id = context.get("voice_id")
        if not isinstance(voice_id, str) or not voice_id:
            _fail("ElevenLabs needs a voice_id in the context")
        body = {"text": text, "model_id": model}
        settings = context.get("voice_settings")
        if settings is not None:
            if not isinstance(settings, dict):
                _fail("voice_settings must be an object")
            parsed = {}
            stability = settings.get("stability")
            if stability is not None:
                parsed["stability"] = _validate_number(
                    stability, "voice_settings.stability",
                    minimum=0, maximum=1)
            similarity = settings.get("similarity_boost")
            if similarity is not None:
                parsed["similarity_boost"] = _validate_number(
                    similarity, "voice_settings.similarity_boost",
                    minimum=0, maximum=1)
            style = settings.get("style")
            if style is not None:
                if model == "eleven_v4":
                    _fail("eleven_v4 does not support "
                          "voice_settings.style")
                parsed["style"] = _validate_number(
                    style, "voice_settings.style",
                    minimum=0, maximum=1)
            speed = settings.get("speed")
            if speed is not None:
                if model == "eleven_v4":
                    _fail("eleven_v4 does not support "
                          "voice_settings.speed")
                parsed["speed"] = _validate_number(
                    speed, "voice_settings.speed",
                    minimum=0.7, maximum=1.2)
            boost = settings.get("use_speaker_boost")
            if boost is not None:
                parsed["use_speaker_boost"] = _validate_bool(
                    boost, "voice_settings.use_speaker_boost")
            if parsed:
                body["voice_settings"] = parsed
        language_code = context.get("language_code")
        if language_code is not None:
            if not re.fullmatch(r"[a-z]{2}", str(language_code)):
                _fail("language_code must be an ISO 639-1 code")
            body["language_code"] = language_code
        seed = context.get("seed")
        if seed is not None:
            body["seed"] = _validate_int(seed, "seed", minimum=0,
                                         maximum=4294967295)
        for field in ("previous_text", "next_text"):
            value = context.get(field)
            if value is not None:
                body[field] = _require_text(value, field)
        locators = context.get("pronunciation_dictionary_locators")
        if locators is not None:
            if not isinstance(locators, list) or len(locators) > 3:
                _fail("pronunciation_dictionary_locators must be "
                      "a list of at most 3 entries")
            parsed_locators = []
            for entry in locators:
                if not isinstance(entry, dict) \
                        or not entry.get("id"):
                    _fail("each pronunciation dictionary locator "
                          "needs an id")
                parsed_locators.append(entry)
            body["pronunciation_dictionary_locators"] = parsed_locators
        normalization = context.get("apply_text_normalization")
        if normalization is not None:
            body["apply_text_normalization"] = _validate_enum(
                normalization, "apply_text_normalization",
                ("auto", "on", "off"))
        output_format = context.get("output_format", "mp3_44100_128")
        if not re.fullmatch(r"(mp3|pcm|ulaw|alaw|opus)_\d+(_\d+)?",
                            str(output_format)):
            _fail("output_format is not a documented ElevenLabs "
                  "format")
        return {"model": model, "body": body,
                "content_type": "application/json",
                "url_values": {"voice_id": voice_id},
                "query": {"output_format": output_format},
                "headers": {}, "url": None, "context_updates": {}}

    def parse_submit_response(self, data, status, context=None):
        # Synchronous: the adapter calls extract_sync_output with
        # the raw body instead; reaching here is a wiring error.
        _fail("ElevenLabs submit is synchronous and returns raw "
              "audio bytes, not JSON", code="local-tool-error")

    def extract_sync_output(self, raw_body, headers):
        if not raw_body:
            _fail("ElevenLabs returned no audio bytes",
                  code="malformed-output")
        content_type = (headers or {}).get("content-type", "")
        if content_type:
            main = content_type.split(";")[0].strip().lower()
            if not (main.startswith("audio/")
                    or main == "application/octet-stream"):
                _fail("ElevenLabs returned an unexpected content "
                      f"type: {main}", code="malformed-output")
        return raw_body, ".mp3"


# ---------------------------------------------------------------------
# Lyria music via the Interactions API (official docs, 2026-11-27)
# ---------------------------------------------------------------------

_LYRIA_MODELS = ("lyria-3.5", "lyria-3-clip-preview")


class LyriaMusicContract(ProviderContract):
    """Lyria music generation via the Interactions API.

    POST /v1beta/interactions with header ``Api-Revision:
    2026-05-20`` and ``x-goog-api-key``. Request body
    ``{"model", "input": "<prompt>"}`` (or a list of text +
    image parts for image inspiration, up to 10 images).
    ``lyria-3.5`` makes full-length songs (a couple of minutes,
    duration controllable in the prompt); ``lyria-3-clip-preview``
    always makes a 30-second clip. Output is base64 MP3
    (44.1 kHz stereo) in the response ``steps``
    (``output_audio``) plus generated lyrics/structure as
    ``output_text``. WAV output is NOT implemented: the exact
    ``response_format`` fields for WAV were not confirmed in the
    docs read, so a WAV request is refused explicitly.
    """

    provider_id = "provider-lyria-music"
    is_async = False

    def build_request(self, packet, context, model):
        model = _validate_enum(model, "model", _LYRIA_MODELS)
        prompt = _prompt(packet)
        context = context or {}
        refs = _reference_images(context, 10)
        output_format = context.get("output_format")
        if output_format is not None and output_format != "mp3":
            _fail("Lyria WAV output is not implemented: the exact "
                  "response_format fields were not confirmed in "
                  "the provider documentation")
        if refs:
            parts = [{"type": "text", "text": prompt}]
            for ref in refs:
                parts.append({"type": "image", "data": ref["base64"],
                              "mime_type": ref["mime"]})
            body = {"model": model, "input": parts}
        else:
            body = {"model": model, "input": prompt}
        return {"model": model, "body": body,
                "content_type": "application/json",
                "url_values": {}, "query": {},
                "headers": {"Api-Revision": API_REVISION_GEMINI},
                "url": None, "context_updates": {}}

    def parse_submit_response(self, data, status, context=None):
        raw, mime, text = _interactions_output(data, "audio")
        return {"job_id": None, "status_url": None,
                "cancel_url": None, "response_url": None,
                "output": {"raw": raw, "ext": ".mp3",
                           "detail": text}}

    def extract_sync_output(self, raw_body, headers):
        data = _parse_json_object(raw_body, self.provider_id)
        output = self.parse_submit_response(data, 200)["output"]
        return output["raw"], output["ext"]


# ---------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------

CONTRACTS = {
    "provider-openai-image": OpenAIImageContract(),
    "provider-gemini-image": GeminiImageContract(),
    "provider-fal-image": FalImageContract(),
    "provider-fal-video": FalVideoContract(),
    "provider-veo-video": VeoVideoContract(),
    "provider-kling-video": KlingVideoContract(),
    "provider-ltx-video": LTXVideoContract(),
    "provider-elevenlabs-voice": ElevenLabsVoiceContract(),
    "provider-lyria-music": LyriaMusicContract(),
}


def get_contract(provider_id):
    """Return the contract for a provider, or fail closed."""
    contract = CONTRACTS.get(provider_id)
    if contract is None:
        _fail(f"no provider contract is registered for "
              f"{provider_id!r} — refusing to build a generic "
              "request", code="local-tool-error")
    return contract


__all__ = [
    "CONTRACT_AUDIT_DATE",
    "API_REVISION_GEMINI",
    "FAL_STORE_IO_HEADER",
    "FAL_LIFECYCLE_HEADER",
    "FAL_ZDR_STATUS",
    "FAL_VIDEO_GCS_OUTPUT_EXAMPLE",
    "fal_retention_headers",
    "fal_retention_truth_table",
    "validate_fal_video_elements",
    "ProviderContract",
    "OpenAIImageContract",
    "GeminiImageContract",
    "FalImageContract",
    "FalVideoContract",
    "VeoVideoContract",
    "KlingVideoContract",
    "LTXVideoContract",
    "ElevenLabsVoiceContract",
    "LyriaMusicContract",
    "CONTRACTS",
    "get_contract",
]
