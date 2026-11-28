#!/usr/bin/env python3
"""Image-to-video (I2V) execution path (CF-WO-P1-006-R2).

A verified source keyframe becomes a genuine video clip only
through a real provider image-to-video execution — never by
animating a still locally. This module is the single place that
path lives:

* source-image validation (path + SHA-256 + size + geometry),
* character-reference permission validation (the keyframe and
  its references may be transmitted only under an explicit
  authorization record),
* provider-specific I2V request building (delegated to the
  provider contract — never a generic payload),
* an AUTHORIZATION GATE (no paid submission without an explicit
  authorization record),
* idempotency + uncertain-submission protection (never
  auto-resend when a submission's status is unknown),
* async polling + retrieval through the existing secure URL
  policy (the adapter does the download; this module verifies
  what came back),
* generated-clip verification (file type, size, duration,
  resolution, codec, video stream present),
* elements conditioning (one approved identity binding per
  recurring character — frontal + 1-3 angle references, the
  same references on every shot with that character, none on
  a shot without it; a missing or pending reference BLOCKS
  the plan), with the provider-specific GCS output policy
  (``storage.googleapis.com/falserverless/`` only, plus the
  fal CDN v3 origin where actually used) and the retention
  headers (``X-Fal-Store-IO: 0`` + the fal CDN v3
  lifecycle/ACL header; ZDR UNCONFIRMED, never claimed),
* post-generation character-drift review records (human
  review of real generated frames; no fake verdict),
* motion validation by frame sampling (static repeated frames
  and camera-only movement are REJECTED — a zoom or pan over a
  still is not image-to-video),
* text-overlay prohibition (all six overlay flags must be
  False; prompts carry a no-visible-text clause; on-screen text
  detection is human review only — no OCR claim is made),
* execution planning (a plan is BLOCKED, never silently
  degraded, when authorization or a keyframe is missing).

FFmpeg is used here only for probing, frame sampling, and the
technical conversions the assembly stage performs — never as
the I2V substitute. The still-zoompan fallback is disabled for
this project's required clips: the R2 driver fails closed
(BLOCKED, no fake MP4) when no authorized real execution
exists.

Standard library only, plus ffprobe/ffmpeg as external tools
(the same tools the rest of the runtime already requires).
No provider is called by importing this module; execution
happens only through :func:`execute_i2v_plan`, which refuses
to run a BLOCKED plan.
"""

import base64
import hashlib
import json
import math
import os
import re
import subprocess
import time
from datetime import datetime, timezone

from runtime import production_assets as pa
from runtime.provider_contracts import (
    FAL_ZDR_STATUS, fal_retention_truth_table, get_contract,
    validate_fal_video_elements)

PROVIDER_ID = "provider-fal-video"
MODEL_ID = "fal-ai/kling-video/v3/pro/image-to-video"
OPERATION = "image-to-video"

# ZDR status for this endpoint (fal.ai: ZDR is NOT enabled by
# default, requires sales-team confirmation, is NOT a single
# setting). This runtime never claims ZDR; see
# runtime.provider_contracts.fal_retention_truth_table().
ZDR_STATUS = FAL_ZDR_STATUS

# fal.ai Kling 3.0 Pro 1080p list prices, checked 2026-11-28
# (fal.ai learn pages — see RATE_SOURCE). Used ONLY for the
# cost estimate in the execution plan and the written
# authorization request — never billed, never charged here.
# Image-to-video WITH elements is a separate, HIGHER tier
# than without elements: $0.224/s audio off with elements,
# against $0.112/s audio off without elements. Voice control
# is recorded in the table but has no code path using it in
# this production (generate_audio is false, no voice control).
FAL_KLING_3_PRO_USD_PER_SECOND = {
    # Without elements: audio off / audio on / voice control.
    "without_elements": {
        "audio_off": 0.112,
        "audio_on": 0.168,
        "voice_control": 0.196,
    },
    # With elements: audio off / audio on / voice control.
    "with_elements": {
        "audio_off": 0.224,
        "audio_on": 0.336,
        "voice_control": 0.392,
    },
}
RATE_SOURCE = (
    "fal.ai list prices, checked 2026-11-28: "
    "https://fal.ai/learn/tools/kling-3-0-pro-vs-sora-2-pro "
    "(comparison table: with elements $0.224/s audio off, "
    "$0.336/s audio on; base without elements $0.112/s audio "
    "off, $0.168/s audio on, $0.196/s with voice control) and "
    "https://fal.ai/learn/tools/seedance-2-0-vs-kling-3-0 "
    "(image-to-video with elements $0.224/$0.336/$0.392 per "
    "second; without elements $0.112/$0.168/$0.196). The "
    "official API schema page (https://fal.ai/models/fal-ai/"
    "kling-video/v3/pro/image-to-video/api) lists no pricing.")


def kling_3_pro_rate_usd_per_second(*, generate_audio,
                                    with_elements,
                                    voice_control=False):
    """Kling 3.0 Pro per-second rate for one shot.

    ``with_elements`` selects the with-elements tier
    ($0.224/s audio off, $0.336/s audio on, $0.392/s voice
    control) over the base tier ($0.112/s audio off, $0.168/s
    audio on, $0.196/s voice control). Voice control is
    recorded here but has no caller in this production.
    """
    tier = FAL_KLING_3_PRO_USD_PER_SECOND[
        "with_elements" if with_elements else "without_elements"]
    if voice_control:
        return tier["voice_control"]
    return tier["audio_on" if generate_audio else "audio_off"]

# The six on-screen-text flags. Every one must be exactly False.
TEXT_OVERLAY_FLAGS = (
    "text_overlay_enabled",
    "subtitle_burn_in_enabled",
    "keyword_overlay_enabled",
    "subtext_overlay_enabled",
    "title_card_enabled",
    "watermark_enabled",
)
TEXT_OVERLAY_POLICY = {flag: False for flag in TEXT_OVERLAY_FLAGS}
TEXT_PROHIBITION_CLAUSE = (
    "No visible text, writing, signage, typography, subtitles, "
    "captions, watermarks, or logos.")

# Motion-prompt structure: every field is a separate movement
# specification. The composed provider prompt joins them in
# this order, then appends the text-prohibition clause.
MOTION_PROMPT_FIELDS = (
    "subject",
    "face",
    "body",
    "hand_prop",
    "hair_cloth",
    "environment",
    "camera",
)
MOTION_PROMPT_MAX_CHARS = 2500

# fal.ai Kling v3 Pro start-image limits (official OpenAPI
# schema, read 2026-11-28): <=50 MB, >=300x300 px, aspect
# 0.40-2.50. Codec names are ffprobe codec_name values.
START_IMAGE_MAX_BYTES = 50 * 1024 * 1024
START_IMAGE_MIN_PIXELS = 300
START_IMAGE_CODECS = {
    "png": "image/png",
    "mjpeg": "image/jpeg",
    "webp": "image/webp",
}

# Motion-detection thresholds. These are DETECTION thresholds
# on measured mean absolute pixel differences (0-255 scale over
# 64x36 grayscale frames) — not motion-quality scores, and no
# numeric motion or realism score is ever produced from them.
# A pair of sampled frames whose whole-frame difference is
# below STILL_THRESHOLD is treated as unchanged; a centre-region
# difference at or above SUBJECT_THRESHOLD is treated as
# subject-region change; a border-region difference at or above
# CAMERA_THRESHOLD with a still centre is treated as edge-only
# movement (the signature of a zoom over a still). A pure
# translation (pan) is detected separately: when some non-zero
# pixel shift explains the frame pair (residual below
# STILL_THRESHOLD), the change is a rigid camera move, not
# subject motion. The final gate is always human visual review
# of the actual clip — this analysis only rejects the failure
# modes named in the work order (repeated still, camera-only).
STILL_THRESHOLD = 1.0
SUBJECT_THRESHOLD = 3.0
CAMERA_THRESHOLD = 3.0
SAMPLE_WIDTH = 64
SAMPLE_HEIGHT = 36
SHIFT_SEARCH = 4


class ImageToVideoError(ValueError):
    """I2V failure carrying a failure-classification code."""

    def __init__(self, message, code="validation-failed"):
        super().__init__(message)
        self.code = code


def _fail(message, code="validation-failed"):
    raise ImageToVideoError(message, code=code)


# ------------------------------------------------------------------
# Text-overlay prohibition
# ------------------------------------------------------------------

def validate_text_overlay_policy(policy) -> list:
    """Text-overlay policy errors (empty list = valid).

    The policy must be an object carrying all six flags, each
    exactly False. A missing flag, a True flag, or a non-boolean
    value is an error naming the flag — nothing is silently
    treated as disabled.
    """
    errors: list[str] = []
    if not isinstance(policy, dict):
        return ["text overlay policy must be an object"]
    for flag in TEXT_OVERLAY_FLAGS:
        if flag not in policy:
            errors.append(
                f"text overlay policy is missing {flag!r}: every "
                "overlay flag must be explicitly False")
        elif policy[flag] is not False:
            errors.append(
                f"text overlay {flag!r} is not False: on-screen "
                "text is prohibited for this production")
    for key in policy:
        if key not in TEXT_OVERLAY_FLAGS:
            errors.append(
                f"text overlay policy carries unknown flag {key!r}")
    return errors


# ------------------------------------------------------------------
# Motion prompts
# ------------------------------------------------------------------

def validate_motion_prompt(motion) -> list:
    """Motion-prompt structure errors (empty list = valid).

    Every field must be a non-empty string. A prompt with only
    camera movement (all non-camera fields empty or missing) is
    rejected as camera-only: camera movement alone is never a
    subject motion.
    """
    errors: list[str] = []
    if not isinstance(motion, dict):
        return ["motion prompt must be an object with "
                + ", ".join(MOTION_PROMPT_FIELDS)]
    for field in MOTION_PROMPT_FIELDS:
        value = motion.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(
                f"motion prompt field {field!r} is missing or "
                "empty: subject, face, body, hand/prop, "
                "hair/cloth, environment and camera movement "
                "must each be specified")
    non_camera = [f for f in MOTION_PROMPT_FIELDS if f != "camera"]
    if not any(isinstance(motion.get(f), str)
               and motion.get(f).strip() for f in non_camera):
        errors.append(
            "motion prompt is camera-only: no subject, face, "
            "body, hand/prop, hair/cloth or environment movement "
            "is specified — camera movement alone is never "
            "image-to-video motion")
    return errors


def build_i2v_motion_prompt(motion) -> str:
    """Compose the provider motion prompt from its structure.

    Fields are joined in MOTION_PROMPT_FIELDS order, then the
    text-prohibition clause is appended. The result must fit
    the provider's 2500-character prompt limit.
    """
    errors = validate_motion_prompt(motion)
    if errors:
        raise ImageToVideoError(
            ["motion prompt:"] + errors, code="validation-failed")
    text = "; ".join(motion[field].strip()
                      for field in MOTION_PROMPT_FIELDS)
    text = f"{text}. {TEXT_PROHIBITION_CLAUSE}"
    if len(text) > MOTION_PROMPT_MAX_CHARS:
        _fail("motion prompt is "
              f"{len(text)} characters, over the provider limit "
              f"of {MOTION_PROMPT_MAX_CHARS}",
              code="validation-failed")
    return text


# ------------------------------------------------------------------
# Source images
# ------------------------------------------------------------------

def validate_source_image(path, *, expected_sha256=None,
                          max_bytes=START_IMAGE_MAX_BYTES,
                          ffprobe="ffprobe") -> dict:
    """Validate a verified source keyframe.

    The file must exist, fit the provider's start-image size
    limit, match the expected SHA-256 when one is given, and
    probe as an image of a supported codec at or above the
    provider's minimum pixels. Returns the measured record
    (path, sha256, bytes, codec, width, height, aspect ratio).
    """
    if not isinstance(path, str) or not path:
        _fail("source image path is missing",
              code="validation-failed")
    if not os.path.isfile(path):
        _fail(f"source image {path!r} does not exist",
              code="validation-failed")
    size = os.path.getsize(path)
    if size > max_bytes:
        _fail(f"source image {path!r} is {size} bytes, over the "
              f"provider start-image limit of {max_bytes}",
              code="validation-failed")
    with open(path, "rb") as handle:
        raw = handle.read()
    sha256 = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and sha256 != expected_sha256:
        _fail(f"source image {path!r} sha256 mismatch: expected "
              f"{expected_sha256[:16]}..., measured "
              f"{sha256[:16]}...",
              code="validation-failed")
    probe = pa.probe_media_file(path, ffprobe=ffprobe)
    codec = probe.get("video_codec")
    if codec not in START_IMAGE_CODECS:
        _fail(f"source image {path!r} probed as codec "
              f"{codec!r}: not a supported start-image codec "
              f"({', '.join(sorted(START_IMAGE_CODECS))})",
              code="validation-failed")
    width = probe.get("width")
    height = probe.get("height")
    if not isinstance(width, int) or not isinstance(height, int) \
            or width < START_IMAGE_MIN_PIXELS \
            or height < START_IMAGE_MIN_PIXELS:
        _fail(f"source image {path!r} is {width}x{height}: "
              "below the provider minimum of "
              f"{START_IMAGE_MIN_PIXELS}x{START_IMAGE_MIN_PIXELS}",
              code="validation-failed")
    aspect = width / height
    if aspect < 0.40 or aspect > 2.50:
        _fail(f"source image {path!r} aspect ratio "
              f"{aspect:.3f} is outside the provider range "
              "0.40-2.50",
              code="validation-failed")
    divisor = math.gcd(width, height)
    return {"path": path, "sha256": sha256, "bytes": size,
            "codec": codec, "mime": START_IMAGE_CODECS[codec],
            "width": width, "height": height,
            "aspect_ratio": f"{width // divisor}:"
                            f"{height // divisor}"}


def keyframe_data_uri(validated_image) -> str:
    """A validated keyframe as a base64 data URI (fal.ai input).

    Only a keyframe validated by :func:`validate_source_image`
    may be transmitted; the data URI is built from the file on
    disk, never from an unvalidated path.
    """
    if not isinstance(validated_image, dict) \
            or not validated_image.get("path"):
        _fail("keyframe data URI needs a validated image record",
              code="validation-failed")
    with open(validated_image["path"], "rb") as handle:
        encoded = base64.b64encode(handle.read()).decode("ascii")
    return (f"data:{validated_image['mime']};base64,{encoded}")


# ------------------------------------------------------------------
# Identity references and elements conditioning
# (CF-WO-P1-006-R2-PREFLIGHT)
#
# Roles, kept separate by design:
# - the keyframe (start_image_url) is the COMPOSITION / scene
#   context for one shot: where the character is, what the
#   scene looks like, the framing.
# - an elements entry is IDENTITY PRESERVATION for one
#   recurring character: the approved frontal view plus 1-3
#   additional angle references, the same references on every
#   shot containing that character. The prompt references them
#   as @Element1, @Element2, ... in prompt-reference order.
# A shot without the recurring character gets NO elements
# entry — never an unrelated reference. A missing or pending
# reference BLOCKS the plan; a different reference is never
# silently substituted. No identity preservation is claimed to
# be perfect: elements conditioning is a provider input, and
# whether the generated frames kept the identity is decided
# afterwards by human review (see record_character_drift_review).
# ------------------------------------------------------------------

# Reference-asset status values. Only "approved" may be
# transmitted; "pending-generation-after-script-approval" (and
# any other value) blocks the plan.
REFERENCE_STATUS_APPROVED = "approved"
REFERENCE_STATUS_PENDING = "pending-generation-after-script-approval"
ELEMENT_MIN_REFERENCES = 1
ELEMENT_MAX_REFERENCES = 3


def _reference_file_path(record, workspace_root):
    """Resolve a reference record's path (workspace-relative or
    absolute) to a real filesystem path, or None."""
    path = (record or {}).get("path")
    if not isinstance(path, str) or not path:
        return None
    if os.path.isabs(path):
        return path
    if workspace_root:
        return os.path.join(workspace_root, path)
    return path


def validate_reference_asset(record, *, workspace_root=None) -> list:
    """Reference-asset validation errors (empty list = valid).

    The record must name an asset id, point at a file that
    exists, fit the provider's image size limit, match its
    recorded SHA-256, decode as a supported image at or above
    the provider minimum with known dimensions, be approved at
    project level, and carry a recorded transmission permission.
    A missing file, a hash mismatch, an undecodable file, a
    pending approval, or a missing transmission permission is
    an error — never a silent substitution.
    """
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["identity reference must be an object"]
    asset_id = record.get("asset_id")
    if not isinstance(asset_id, str) or not asset_id:
        errors.append("identity reference has no asset_id")
    path = _reference_file_path(record, workspace_root)
    if path is None:
        errors.append(
            f"identity reference {asset_id!r} has no path")
        return errors
    if not os.path.isfile(path):
        errors.append(
            f"identity reference {asset_id!r} file {path!r} "
            "does not exist: a missing reference blocks "
            "submission — it is never silently substituted")
        return errors
    expected_sha256 = record.get("sha256")
    try:
        info = validate_source_image(
            path, expected_sha256=expected_sha256)
    except ImageToVideoError as exc:
        errors.append(
            f"identity reference {asset_id!r}: {exc}")
        return errors
    mime = record.get("mime")
    if mime is not None and mime != info["mime"]:
        errors.append(
            f"identity reference {asset_id!r} mime "
            f"{mime!r} does not match the decoded image mime "
            f"{info['mime']!r}")
    if record.get("status") != REFERENCE_STATUS_APPROVED:
        errors.append(
            f"identity reference {asset_id!r} is not approved "
            f"(status {record.get('status')!r}): a pending or "
            "missing reference is a BLOCKED plan, not a "
            "skipped element")
    if record.get("transmission_permitted") is not True:
        errors.append(
            f"identity reference {asset_id!r} has no recorded "
            "transmission permission: transmission permission "
            "must be recorded before the reference is sent")
    return errors


def validate_identity_binding(binding, *, workspace_root=None) -> list:
    """Identity-binding errors (empty list = valid).

    One binding is one character's elements entry: a frontal
    reference plus 1-3 additional angle references, all
    validated by :func:`validate_reference_asset`. A binding
    carrying a ``video_url`` or a ``voice_id`` is an error:
    this production uses image elements only, and no voice is
    bound to an element (generation runs with generate_audio
    false).
    """
    errors: list[str] = []
    if not isinstance(binding, dict):
        return ["identity binding must be an object"]
    character_id = binding.get("character_id")
    if not isinstance(character_id, str) or not character_id:
        errors.append("identity binding has no character_id")
    if binding.get("video_url") is not None:
        errors.append(
            "identity binding carries video_url: this "
            "production uses image elements only")
    if binding.get("voice_id") is not None:
        errors.append(
            "identity binding carries voice_id: no voice is "
            "bound to an element (generate_audio is false)")
    frontal = binding.get("frontal")
    if frontal is None:
        errors.append(
            "identity binding has no frontal reference: the "
            "main frontal view is required")
    else:
        errors += [f"frontal: {err}" for err in
                   validate_reference_asset(
                       frontal, workspace_root=workspace_root)]
    additional = binding.get("additional")
    if not isinstance(additional, list):
        errors.append(
            "identity binding needs 'additional': a list of "
            "1-3 additional angle references")
    else:
        if len(additional) < ELEMENT_MIN_REFERENCES:
            errors.append(
                "identity binding needs at least "
                f"{ELEMENT_MIN_REFERENCES} additional reference "
                "image: additional angles are required")
        if len(additional) > ELEMENT_MAX_REFERENCES:
            errors.append(
                "identity binding carries "
                f"{len(additional)} additional reference images: "
                f"at most {ELEMENT_MAX_REFERENCES} are supported")
        for position, ref in enumerate(additional, start=1):
            errors += [f"additional[{position}]: {err}" for err in
                       validate_reference_asset(
                           ref, workspace_root=workspace_root)]
    return errors


def build_elements_payload(bindings, *, workspace_root=None) -> list:
    """Build the provider ``elements`` array from identity bindings.

    ``bindings`` is a list of identity bindings, one per
    character, in prompt-reference order (element 1 is
    ``@Element1``). Every binding is validated first; an
    invalid, pending or missing reference raises instead of
    producing a partial array. Each element carries the frontal
    image URL and the 1-3 additional reference image URLs as
    base64 data URIs built from the validated local files (the
    same mechanism as the keyframe data URI). The keyframe /
    start image is NOT part of this array: it stays separate as
    ``start_image_url``.
    """
    if not isinstance(bindings, list) or not bindings:
        _fail("elements payload needs a non-empty list of "
              "identity bindings: one per character, in "
              "prompt-reference order",
              code="validation-failed")
    payload = []
    for binding in bindings:
        errors = validate_identity_binding(
            binding, workspace_root=workspace_root)
        if errors:
            raise ImageToVideoError(
                ["identity binding invalid:"] + errors,
                code="validation-failed")
        frontal = validate_source_image(
            _reference_file_path(binding["frontal"], workspace_root),
            expected_sha256=binding["frontal"].get("sha256"))
        frontal_url = keyframe_data_uri(frontal)
        reference_urls = []
        for ref in binding["additional"]:
            info = validate_source_image(
                _reference_file_path(ref, workspace_root),
                expected_sha256=ref.get("sha256"))
            reference_urls.append(keyframe_data_uri(info))
        payload.append(
            {"frontal_image_url": frontal_url,
             "reference_image_urls": reference_urls})
    return payload


def build_shot_elements(shot, identity_bindings, *,
                        workspace_root=None):
    """The ``elements`` array for one shot, or None.

    ``identity_bindings`` maps shot_id to a list of identity
    bindings for that shot (or None when the production carries
    no identity bindings at all — the legacy path, unchanged).
    A shot with no ``character_id`` gets NO elements entry. A
    shot with a character but no binding for it raises: a
    missing reference blocks submission, it is never silently
    substituted or skipped.
    """
    if identity_bindings is None:
        return None
    if not isinstance(shot, dict):
        _fail("shot elements need a shot object",
              code="validation-failed")
    if not shot.get("character_id"):
        return None
    shot_id = shot.get("shot_id") or "unknown-shot"
    bindings = identity_bindings.get(shot_id)
    if bindings is None:
        _fail(f"shot {shot_id}: character "
              f"{shot.get('character_id')!r} has no identity "
              "binding — a missing character reference blocks "
              "submission",
              code="validation-failed")
    return build_elements_payload(
        bindings, workspace_root=workspace_root)


def retention_truth_table() -> list:
    """The retention / ACL / ZDR truth table for this endpoint.

    Delegates to the provider contract (the single source of
    truth); see ``runtime.provider_contracts``.
    """
    return fal_retention_truth_table()


# ------------------------------------------------------------------
# Authorization gate
# ------------------------------------------------------------------

def validate_authorization(authorization, *, provider_id,
                           model, operation, required_generations,
                           scope_asset_ids) -> list:
    """Authorization-record errors (empty list = authorized).

    The record must name who authorized it, the exact provider /
    model / operation, a generation budget covering the required
    generations, and a scope containing every asset id that will
    be transmitted. An expired record is refused. A missing
    record is refused — there is no implicit authorization.
    """
    errors: list[str] = []
    if not isinstance(authorization, dict):
        return ["image-to-video authorization is missing: no paid "
                "submission without an explicit authorization "
                "record"]
    authorized_by = authorization.get("authorized_by")
    if not isinstance(authorized_by, str) or not authorized_by:
        errors.append("authorization record has no authorized_by")
    if authorization.get("provider_id") != provider_id:
        errors.append(
            "authorization provider "
            f"{authorization.get('provider_id')!r} does not match "
            f"the required provider {provider_id!r}")
    if authorization.get("model") != model:
        errors.append(
            f"authorization model {authorization.get('model')!r} "
            f"does not match the required model {model!r}")
    if authorization.get("operation") != operation:
        errors.append(
            "authorization operation "
            f"{authorization.get('operation')!r} does not match "
            f"the required operation {operation!r}")
    budget = authorization.get("max_generations")
    if not isinstance(budget, int) or isinstance(budget, bool) \
            or budget < required_generations:
        errors.append(
            "authorization generation budget "
            f"{budget!r} does not cover the required "
            f"{required_generations} generations")
    scope = authorization.get("scope")
    if not isinstance(scope, list):
        errors.append("authorization scope must be a list of "
                      "asset ids")
    else:
        missing = [asset for asset in (scope_asset_ids or [])
                   if asset not in scope]
        if missing:
            errors.append(
                "authorization scope does not cover transmitted "
                f"assets: {', '.join(sorted(missing))}")
    expires_at = authorization.get("expires_at")
    if expires_at is not None:
        try:
            text = str(expires_at)
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            expiry = datetime.fromisoformat(text)
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            if expiry <= datetime.now(timezone.utc):
                errors.append(
                    "authorization record expired at "
                    f"{authorization.get('expires_at')!r}")
        except ValueError:
            errors.append(
                "authorization expires_at "
                f"{expires_at!r} is not an ISO timestamp")
    return errors


def require_authorization(authorization, **kwargs):
    """Raise unless the authorization record is valid."""
    errors = validate_authorization(authorization, **kwargs)
    if errors:
        raise ImageToVideoError(
            ["image-to-video authorization denied:"] + errors,
            code="authorization-denied")


# ------------------------------------------------------------------
# Idempotency + uncertain-submission protection
# ------------------------------------------------------------------

def idempotency_key(project_id, shot_id, provider_id, model,
                    keyframe_sha256, prompt) -> str:
    """Deterministic idempotency key for one I2V generation.

    SHA-256 of the canonical job description: the same project,
    shot, provider, model, keyframe and prompt always produce
    the same key, so a retry never becomes a second paid
    submission.
    """
    canonical = json.dumps(
        {"project_id": project_id, "shot_id": shot_id,
         "provider_id": provider_id, "model": model,
         "keyframe_sha256": keyframe_sha256, "prompt": prompt},
        sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class SubmissionLedger:
    """Idempotency ledger for I2V submissions (in-memory, with
    an optional JSON store file).

    A key is recorded on submission; a later call with the same
    key returns the recorded job id instead of resubmitting. A
    submission whose outcome is unknown is recorded as
    ``uncertain`` and NEVER auto-resubmitted — the operator must
    resolve it against the provider first.
    """

    def __init__(self, store_path=None):
        self.store_path = store_path
        self._entries: dict = {}
        if store_path and os.path.isfile(store_path):
            with open(store_path, encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                self._entries = data

    def _save(self):
        if not self.store_path:
            return
        parent = os.path.dirname(self.store_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        tmp = f"{self.store_path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(self._entries, handle, indent=2,
                      sort_keys=True)
            handle.write("\n")
        os.replace(tmp, self.store_path)

    def lookup(self, key):
        """The ledger entry for a key, or None."""
        entry = self._entries.get(key)
        return dict(entry) if isinstance(entry, dict) else None

    def is_uncertain(self, key) -> bool:
        entry = self.lookup(key)
        return bool(entry and entry.get("status") == "uncertain")

    def record_submission(self, key, job_id, status):
        self._entries[key] = {"job_id": job_id, "status": status}
        self._save()
        return dict(self._entries[key])

    def record_uncertain(self, key, detail):
        self._entries[key] = {"job_id": None, "status": "uncertain",
                              "detail": str(detail)[:500]}
        self._save()
        return dict(self._entries[key])


# ------------------------------------------------------------------
# Request building + submission (through the provider contract)
# ------------------------------------------------------------------

def build_i2v_request(provider_id, model, *, prompt,
                      start_image_url, duration_seconds=6,
                      generate_audio=True, negative_prompt=None,
                      cfg_scale=None, elements=None,
                      lifecycle_expiration_seconds=None,
                      lifecycle_initial_acl=None) -> dict:
    """Build the provider I2V request via the provider contract.

    Preparation only: no submission, no charge. The packet
    carries the motion prompt as the canonical instruction; the
    contract validates every field for its own provider.
    ``elements`` (when given) is the validated provider
    ``elements`` array — one element per character, built by
    :func:`build_elements_payload`; the start image stays
    separate as ``start_image_url``. Retention overrides are
    passed through to the contract's retention headers.
    """
    contract = get_contract(provider_id)
    context = {"start_image_url": start_image_url,
               "duration": str(duration_seconds),
               "generate_audio": bool(generate_audio)}
    if negative_prompt is not None:
        context["negative_prompt"] = negative_prompt
    if cfg_scale is not None:
        context["cfg_scale"] = cfg_scale
    if elements is not None:
        context["elements"] = elements
    if lifecycle_expiration_seconds is not None:
        context["lifecycle_expiration_seconds"] = \
            lifecycle_expiration_seconds
    if lifecycle_initial_acl is not None:
        context["lifecycle_initial_acl"] = lifecycle_initial_acl
    return contract.build_request(
        {"canonical_instruction": prompt}, context, model)


def submit_i2v_generation(adapter, request, context, *,
                          ledger, key) -> dict:
    """Submit one I2V generation, or reuse the recorded job.

    A key already in the ledger returns the recorded job id
    without calling the adapter — a retry never becomes a second
    paid submission. An uncertain key refuses outright. A
    submission whose outcome is unknown (the adapter reports
    ``submission-uncertain``) is recorded as uncertain and the
    error propagates — the caller must resolve it against the
    provider, never resubmit.
    """
    existing = ledger.lookup(key) if ledger is not None else None
    if existing and existing.get("job_id") \
            and existing.get("status") in (
                "submitted", "running", "done"):
        return {"job_id": existing["job_id"], "reused": True,
                "completed": existing.get("status") == "done",
                "output": None, "failure": None}
    if ledger is not None and ledger.is_uncertain(key):
        _fail("I2V submission key is recorded uncertain: resolve "
              "it against the provider before any further "
              "submission — never auto-resend",
              code="submission-uncertain")
    try:
        result = adapter.submit(request, context)
    except Exception as exc:  # noqa: BLE001 - classify + record
        code = getattr(exc, "code", "") or ""
        if code == "submission-uncertain":
            if ledger is not None:
                ledger.record_uncertain(key, str(exc))
        raise
    job_id = (result or {}).get("provider_job_id")
    if not isinstance(job_id, str) or not job_id:
        if ledger is not None:
            ledger.record_uncertain(
                key, "adapter submit returned no provider job id")
        _fail("I2V submission returned no provider job id: "
              "recorded uncertain — resolve against the provider "
              "before any further submission",
              code="submission-uncertain")
    failure = (result or {}).get("failure")
    if failure is not None:
        if ledger is not None:
            ledger.record_submission(key, job_id, "failed")
        message = failure.get("message") if isinstance(
            failure, dict) else str(failure)
        _fail(f"I2V submission failed at the provider: {message}",
              code="provider-error")
    if ledger is not None:
        status = "done" if result.get("completed") else "submitted"
        ledger.record_submission(key, job_id, status)
    return {"job_id": job_id, "reused": False,
            "completed": bool(result.get("completed")),
            "output": result.get("output"), "failure": None}


def poll_i2v_generation(adapter, job_id, context, *,
                        max_polls=60, poll_interval_s=5) -> dict:
    """Poll one I2V job until it completes or fails.

    Returns the adapter's terminal result (with the verified
    output artifact when completed). A failed job raises with
    code ``provider-error``; running out of polls raises with
    code ``poll-timeout`` and never claims completion.
    """
    if not isinstance(job_id, str) or not job_id:
        _fail("I2V poll needs a provider job id",
              code="validation-failed")
    last = None
    for _ in range(max(1, int(max_polls))):
        last = adapter.poll(job_id, context)
        if (last or {}).get("completed"):
            failure = (last or {}).get("failure")
            if failure is not None:
                message = failure.get("message") if isinstance(
                    failure, dict) else str(failure)
                _fail(f"I2V job {job_id} failed at the provider: "
                      f"{message}",
                      code="provider-error")
            return last
        if poll_interval_s:
            time.sleep(poll_interval_s)
    _fail(f"I2V job {job_id} did not complete after "
          f"{max_polls} polls",
          code="poll-timeout")


# ------------------------------------------------------------------
# Generated-clip verification
# ------------------------------------------------------------------

def verify_generated_clip(path, *, expected_duration_seconds,
                          expected_width=None, expected_height=None,
                          duration_tolerance_s=1.0,
                          ffprobe="ffprobe") -> dict:
    """Verify a provider-returned clip against the plan.

    The file must be an MP4 with an H.264 video stream, a
    measured duration within tolerance of the requested
    duration, and — when an expected geometry is given — the
    expected width and height. The native resolution is always
    recorded separately from any later upscale: a clip that
    needed resizing is reported with its native geometry here.
    """
    if not isinstance(path, str) or not path:
        _fail("generated clip path is missing",
              code="validation-failed")
    if not os.path.isfile(path):
        _fail(f"generated clip {path!r} does not exist",
              code="validation-failed")
    probe = pa.probe_media_file(path, ffprobe=ffprobe)
    format_name = probe.get("format_name") or ""
    if "mp4" not in format_name:
        _fail(f"generated clip {path!r} format is "
              f"{format_name!r}: expected an MP4 container",
              code="validation-failed")
    codec = probe.get("video_codec")
    if codec is None:
        _fail(f"generated clip {path!r} has no video stream",
              code="validation-failed")
    if codec != "h264":
        _fail(f"generated clip {path!r} video codec is "
              f"{codec!r}: expected h264",
              code="validation-failed")
    duration = probe.get("duration_seconds")
    if duration is None:
        _fail(f"generated clip {path!r} has no measurable "
              "duration",
              code="validation-failed")
    if abs(duration - float(expected_duration_seconds)) \
            > float(duration_tolerance_s):
        _fail(f"generated clip {path!r} duration is "
              f"{duration:.3f}s, expected "
              f"{expected_duration_seconds}s "
              f"(tolerance {duration_tolerance_s}s)",
              code="validation-failed")
    width = probe.get("width")
    height = probe.get("height")
    if expected_width is not None and width != expected_width:
        _fail(f"generated clip {path!r} width is {width}, "
              f"expected {expected_width}",
              code="validation-failed")
    if expected_height is not None and height != expected_height:
        _fail(f"generated clip {path!r} height is {height}, "
              f"expected {expected_height}",
              code="validation-failed")
    with open(path, "rb") as handle:
        raw = handle.read()
    return {"path": path, "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw), "format_name": format_name,
            "video_codec": codec,
            "audio_codec": probe.get("audio_codec"),
            "width": width, "height": height,
            "duration_seconds": duration,
            "frame_rate_rational": probe.get(
                "frame_rate_rational")}


# ------------------------------------------------------------------
# Motion validation by frame sampling
# ------------------------------------------------------------------

def _run_ffmpeg(argv, *, timeout_s=120):
    try:
        proc = subprocess.run(argv, capture_output=True, text=True,
                              timeout=timeout_s)
    except (OSError, subprocess.TimeoutExpired) as exc:
        _fail(f"ffmpeg failed: {exc}", code="local-tool-error")
    if proc.returncode != 0:
        _fail("ffmpeg failed: "
              f"{(proc.stderr or proc.stdout or '').strip()[:400]}",
              code="local-tool-error")
    return proc


def sample_frames(video_path, *, num_frames=8, out_dir,
                  ffmpeg="ffmpeg", ffprobe="ffprobe") -> list:
    """Sample evenly spaced frames as small grayscale PGM files.

    Returns the frame paths in time order. FFmpeg is required:
    when it is absent the sampling fails instead of skipping —
    motion is never assumed.
    """
    if not os.path.isfile(video_path):
        _fail(f"motion sampling input {video_path!r} does not "
              "exist",
              code="validation-failed")
    probe = pa.probe_media_file(video_path, ffprobe=ffprobe)
    duration = probe.get("duration_seconds")
    if duration is None or duration <= 0:
        _fail(f"motion sampling input {video_path!r} has no "
              "measurable duration",
              code="validation-failed")
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for index in range(max(2, int(num_frames))):
        stamp = duration * (index + 0.5) / max(2, int(num_frames))
        target = os.path.join(out_dir, f"frame-{index:02d}.pgm")
        _run_ffmpeg([ffmpeg, "-y", "-v", "error", "-ss",
                     f"{stamp:.3f}", "-i", video_path,
                     "-frames:v", "1", "-vf",
                     f"scale={SAMPLE_WIDTH}:{SAMPLE_HEIGHT},"
                     "format=gray",
                     target])
        paths.append(target)
    return paths


def _read_pgm(path):
    """(width, height, pixel bytes) of a P5 grayscale PGM."""
    with open(path, "rb") as handle:
        data = handle.read()
    if not data.startswith(b"P5"):
        _fail(f"frame file {path!r} is not a P5 PGM",
              code="local-tool-error")
    tokens = []
    pos = 2
    while len(tokens) < 3:
        while pos < len(data) and data[pos:pos + 1].isspace():
            pos += 1
        if pos < len(data) and data[pos:pos + 1] == b"#":
            while pos < len(data) and data[pos:pos + 1] != b"\n":
                pos += 1
            continue
        start = pos
        while pos < len(data) \
                and not data[pos:pos + 1].isspace():
            pos += 1
        tokens.append(data[start:pos])
    width = int(tokens[0])
    height = int(tokens[1])
    maxval = int(tokens[2])
    if maxval != 255:
        _fail(f"frame file {path!r} has maxval {maxval}, "
              "expected 255",
              code="local-tool-error")
    pos += 1
    pixels = data[pos:pos + width * height]
    if len(pixels) != width * height:
        _fail(f"frame file {path!r} is truncated",
              code="local-tool-error")
    return width, height, pixels


def _mean_abs_diff(first, second, region=None):
    """Mean absolute pixel difference over a region.

    ``region`` is (x0, y0, x1, y1) in pixel coordinates, or None
    for the whole frame. ``first``/``second`` are
    (width, height, pixel bytes) tuples.
    """
    width, height, a = first
    _, _, b = second
    if region is None:
        x0, y0, x1, y1 = 0, 0, width, height
    else:
        x0, y0, x1, y1 = region
    total = 0
    count = 0
    for y in range(y0, y1):
        base = y * width
        for x in range(x0, x1):
            total += abs(a[base + x] - b[base + x])
            count += 1
    return total / count if count else 0.0


def _best_shift_residual(first, second):
    """Best rigid-translation explanation of a frame pair.

    Searches pixel shifts dx, dy in [-SHIFT_SEARCH,
    +SHIFT_SEARCH] on the downscaled frames and returns
    ((dx, dy), residual mean abs diff). A residual below the
    still threshold at a non-zero shift means the pair differs
    only by a camera pan — a rigid move over a still, not
    subject motion.
    """
    width, height, a = first
    _, _, b = second
    best_shift = (0, 0)
    best_residual = None
    for dy in range(-SHIFT_SEARCH, SHIFT_SEARCH + 1):
        for dx in range(-SHIFT_SEARCH, SHIFT_SEARCH + 1):
            total = 0
            count = 0
            for y in range(height):
                y2 = y + dy
                if y2 < 0 or y2 >= height:
                    continue
                for x in range(width):
                    x2 = x + dx
                    if x2 < 0 or x2 >= width:
                        continue
                    total += abs(a[y * width + x]
                                 - b[y2 * width + x2])
                    count += 1
            if not count:
                continue
            residual = total / count
            if best_residual is None or residual < best_residual:
                best_residual = residual
                best_shift = (dx, dy)
    return best_shift, best_residual


def _classify_frame_pair(first, second) -> dict:
    """Classify one consecutive sampled-frame pair.

    Returns the measured region differences, the best-shift
    result, and the pair classification: ``static``,
    ``camera-only``, ``subject-motion`` or ``mixed``.
    """
    width, height, _ = first
    cx0, cy0 = width // 4, height // 4
    cx1, cy1 = width * 3 // 4, height * 3 // 4
    centre = _mean_abs_diff(first, second, (cx0, cy0, cx1, cy1))
    whole = _mean_abs_diff(first, second)
    # Border = everything outside the centre region.
    border_total = whole * width * height \
        - centre * (cx1 - cx0) * (cy1 - cy0)
    border_count = width * height - (cx1 - cx0) * (cy1 - cy0)
    border = border_total / border_count if border_count else 0.0
    shift, residual = _best_shift_residual(first, second)
    if whole < STILL_THRESHOLD:
        classification = "static"
        reason = ("sampled frames are effectively unchanged "
                  "(whole-frame difference below the still "
                  "threshold)")
    elif shift != (0, 0) and residual < STILL_THRESHOLD:
        classification = "camera-only"
        reason = ("the frame pair differs only by a rigid "
                  f"translation {shift}: a camera pan over a "
                  "still, not subject motion")
    elif centre < SUBJECT_THRESHOLD \
            and border >= CAMERA_THRESHOLD:
        classification = "camera-only"
        reason = ("movement lives at the frame edges while the "
                  "centre subject region is unchanged: a zoom "
                  "over a still, not subject motion")
    elif centre >= SUBJECT_THRESHOLD \
            and border < CAMERA_THRESHOLD:
        classification = "subject-motion"
        reason = ("the centre subject region changes while the "
                  "background stays still")
    else:
        classification = "mixed"
        reason = ("both the subject region and the background "
                  "change")
    return {"classification": classification, "reason": reason,
            "whole_diff": round(whole, 3),
            "centre_diff": round(centre, 3),
            "border_diff": round(border, 3),
            "best_shift": list(shift),
            "shift_residual": round(residual, 3)
            if residual is not None else None}


def classify_motion(frame_paths) -> dict:
    """Classify sampled frames into one motion verdict.

    Overall classification is the strongest pair verdict
    present: subject-motion beats mixed beats camera-only
    beats static. ``passes`` is True only for subject-motion
    and mixed — a static clip or a camera-only clip never
    passes, however long it is.
    """
    if len(frame_paths) < 2:
        _fail("motion classification needs at least two sampled "
              "frames",
              code="validation-failed")
    frames = [_read_pgm(path) for path in frame_paths]
    pairs = [_classify_frame_pair(frames[i], frames[i + 1])
             for i in range(len(frames) - 1)]
    present = {pair["classification"] for pair in pairs}
    if "subject-motion" in present:
        overall = "subject-motion"
    elif "mixed" in present:
        overall = "mixed"
    elif "camera-only" in present:
        overall = "camera-only"
    else:
        overall = "static"
    passes = overall in ("subject-motion", "mixed")
    if overall == "static":
        reason = ("no sampled frame pair shows movement: the "
                  "clip is a repeated still")
    elif overall == "camera-only":
        reason = ("movement is camera-only (pan or zoom over a "
                  "still): no subject or environment motion was "
                  "measured")
    elif overall == "subject-motion":
        reason = "subject-region movement measured"
    else:
        reason = "subject and background movement measured"
    return {"classification": overall, "passes": passes,
            "reason": reason, "pairs": pairs}


def validate_clip_motion(video_path, *, num_frames=8, work_dir,
                         ffmpeg="ffmpeg",
                         ffprobe="ffprobe") -> dict:
    """Sample a clip and classify its motion.

    Returns the classification dict. A clip that fails
    (static or camera-only) is reported with ``passes: False``
    and a reason — the caller decides the consequence (the R2
    driver refuses to accept a failing clip).
    """
    frames_dir = os.path.join(work_dir, "motion-frames")
    paths = sample_frames(video_path, num_frames=num_frames,
                          out_dir=frames_dir, ffmpeg=ffmpeg,
                          ffprobe=ffprobe)
    result = classify_motion(paths)
    result["frames_sampled"] = len(paths)
    return result


# ------------------------------------------------------------------
# Human text review (no OCR claim)
# ------------------------------------------------------------------

def record_human_text_review(clip_path, *, reviewer, text_found,
                             notes="") -> dict:
    """One human reviewer's on-screen-text verdict for a clip.

    Text detection is human review only: this module performs no
    OCR and never claims an automated text check.
    """
    if not isinstance(reviewer, str) or not reviewer:
        _fail("human text review needs a reviewer name",
              code="validation-failed")
    if not isinstance(text_found, bool):
        _fail("human text review needs a boolean text_found",
              code="validation-failed")
    return {"clip": clip_path, "reviewer": reviewer,
            "text_found": text_found, "notes": notes,
            "reviewed_at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"),
            "method": "human-visual-review (no OCR)"}


def validate_human_text_reviews(reviews, clip_paths) -> list:
    """Human text-review errors (empty list = valid).

    Every clip needs a review, and no review may report text
    found. A missing review or a text-found review is an error
    naming the clip.
    """
    errors: list[str] = []
    if not isinstance(reviews, list):
        return ["human text reviews must be a list"]
    by_clip = {}
    for review in reviews:
        if isinstance(review, dict) and review.get("clip"):
            by_clip[review["clip"]] = review
    for clip in clip_paths or []:
        review = by_clip.get(clip)
        if review is None:
            errors.append(
                f"clip {clip!r} has no human text review: "
                "on-screen text must be checked by a human "
                "reviewer")
        elif review.get("text_found") is True:
            errors.append(
                f"clip {clip!r} has on-screen text reported by "
                f"reviewer {review.get('reviewer')!r}")
    return errors


# ------------------------------------------------------------------
# Post-generation character-drift review
# (CF-WO-P1-006-R2-PREFLIGHT)
#
# Elements conditioning is a provider input, not a guarantee:
# whether the generated frames actually kept the character's
# identity is decided AFTER generation, by a human reviewer
# looking at real frames. This record type carries those frame
# checks. It never carries a fake verdict: with no frame checks
# the overall verdict is None and the status is "incomplete";
# with checks it is "consistent" only when every check passed,
# "drift-found" when any check failed. No generated frames
# exist yet, so no review is completed.
# ------------------------------------------------------------------

DRIFT_REVIEW_VERDICTS = ("pass", "fail", "not-checked")


def record_character_drift_review(shot_id, clip_path, *,
                                  reviewer, frame_checks) -> dict:
    """One character-drift review record for a generated clip.

    ``frame_checks`` is a list of ``{"frame_time_seconds",
    "attribute", "verdict", "notes"}`` — one entry per frame
    the reviewer actually looked at. ``verdict`` is "pass",
    "fail" or "not-checked". The overall verdict is derived,
    never asserted: None ("incomplete") when there are no
    checks or any check is "not-checked", "drift-found" when
    any check failed, "consistent" only when every check
    passed.
    """
    if not isinstance(shot_id, str) or not shot_id:
        _fail("character drift review needs a shot_id",
              code="validation-failed")
    if not isinstance(clip_path, str) or not clip_path:
        _fail("character drift review needs a clip path",
              code="validation-failed")
    if not isinstance(reviewer, str) or not reviewer:
        _fail("character drift review needs a reviewer name",
              code="validation-failed")
    if not isinstance(frame_checks, list):
        _fail("character drift review needs a list of frame "
              "checks",
              code="validation-failed")
    checks = []
    for check_entry in frame_checks:
        if not isinstance(check_entry, dict):
            _fail("character drift frame check must be an object",
                  code="validation-failed")
        seconds = check_entry.get("frame_time_seconds")
        if isinstance(seconds, bool) \
                or not isinstance(seconds, (int, float)) \
                or seconds < 0:
            _fail("character drift frame check needs a "
                  "non-negative frame_time_seconds",
                  code="validation-failed")
        attribute = check_entry.get("attribute")
        if not isinstance(attribute, str) or not attribute:
            _fail("character drift frame check needs an "
                  "attribute name",
                  code="validation-failed")
        verdict = check_entry.get("verdict")
        if verdict not in DRIFT_REVIEW_VERDICTS:
            _fail("character drift frame check verdict must be "
                  "one of pass/fail/not-checked",
                  code="validation-failed")
        checks.append(
            {"frame_time_seconds": seconds, "attribute": attribute,
             "verdict": verdict,
             "notes": check_entry.get("notes") or ""})
    if not checks or any(c["verdict"] == "not-checked"
                         for c in checks):
        overall = None
        status = "incomplete"
    elif any(c["verdict"] == "fail" for c in checks):
        overall = "drift-found"
        status = "recorded"
    else:
        overall = "consistent"
        status = "recorded"
    return {"shot_id": shot_id, "clip": clip_path,
            "reviewer": reviewer, "frame_checks": checks,
            "overall_verdict": overall, "status": status,
            "reviewed_at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"),
            "method": "human-visual-review of generated frames"}


# ------------------------------------------------------------------
# Script-derived counts (never fixed numbers)
# ------------------------------------------------------------------

def derive_project_counts(project, shots, voice_lines) -> dict:
    """Counts calculated from the script + shot list.

    Scenes, shots, keyframes, clips and lines are all derived
    from the inputs — no count is fixed in advance. The total
    video runtime is the sum of the per-shot clip durations.
    """
    shots = shots or []
    scene_ids = sorted({shot.get("scene_id") for shot in shots
                        if isinstance(shot, dict)})
    clip_duration = None
    total_video_seconds = 0.0
    for shot in shots:
        duration = (shot.get("visual") or {}).get(
            "duration_seconds")
        if duration is not None:
            total_video_seconds += float(duration)
            clip_duration = float(duration)
    i2v = (project or {}).get("i2v") or {}
    return {"scenes": len(scene_ids),
            "scene_ids": scene_ids,
            "shots": len(shots),
            "shot_ids": [shot.get("shot_id") for shot in shots
                         if isinstance(shot, dict)],
            "keyframes": len(shots),
            "clips": len(shots),
            "lines": len(voice_lines or []),
            "clip_duration_seconds": clip_duration,
            "total_video_seconds": total_video_seconds,
            "provider_id": i2v.get("provider_id") or PROVIDER_ID,
            "model": i2v.get("provider_model") or MODEL_ID}


# ------------------------------------------------------------------
# Execution planning (pure: never submits, never charges)
# ------------------------------------------------------------------

def build_execution_plan(project, shots, *, authorization=None,
                         duration_seconds=6,
                         generate_audio=None,
                         identity_bindings=None,
                         workspace_root=None) -> dict:
    """Build the I2V execution plan for a project.

    The plan is READY only when the script is approved, every
    shot has a verified keyframe, every motion prompt is valid,
    and the authorization record covers the provider, model,
    operation, generation count and every transmitted asset.
    Otherwise the plan is BLOCKED with the exact reasons — and
    nothing is submitted, degraded, or substituted.

    ``identity_bindings`` (optional) maps shot_id to a list of
    identity bindings for that shot. When it is given, every
    shot containing the recurring character must carry a valid
    approved binding (its reference asset ids join the
    authorization scope), and the generation entries carry the
    built ``elements`` array; a shot without the character
    carries no elements entry. A missing or pending reference
    BLOCKS the plan. When it is None (legacy path) no elements
    are built and the plan is unchanged.

    ``generate_audio``: when None (the default) the plan takes
    the project's own audio setting from
    ``project["i2v"]["generate_audio"]`` (default True when the
    key is absent or not a boolean). An explicit argument always
    wins over the project setting. The resolved value drives
    both the per-shot ``generate_audio`` flag and the pricing
    rate. Pricing is per shot, by elements usage: a shot that
    uses elements (a character identity binding) is priced at
    the with-elements tier (audio off $0.224/s, audio on
    $0.336/s, voice control $0.392/s); a shot without elements
    is priced at the base tier (audio off $0.112/s, audio on
    $0.168/s, voice control $0.196/s). Every generation entry
    carries ``uses_elements``, ``rate_usd_per_second`` and
    ``estimated_cost_usd``; the plan total is the sum of the
    per-shot costs, rounded to 2 decimals. The plan-level
    ``rate_usd_per_second`` is the single rate only when all
    shots share one rate, otherwise None.
    """
    project = project or {}
    if generate_audio is None:
        # Take the project's own audio setting (project["i2v"]
        # ["generate_audio"]); default True when the key is absent
        # or not a boolean. An explicit argument always wins.
        # (Preflight: the R2 project sets it false; the earlier
        # default-True pricing ignored the project setting and
        # priced the plan audio-on.)
        _i2v = project.get("i2v") or {}
        generate_audio = _i2v.get("generate_audio", True)
        if not isinstance(generate_audio, bool):
            generate_audio = True
    shots = shots or []
    project_id = project.get("project_id") or "unknown-project"
    counts = derive_project_counts(
        project, shots, project.get("voice_lines") or [])
    blocked: list[str] = []
    script_status = project.get("script_status") or ""
    if isinstance(script_status, str) \
            and script_status.upper().startswith("DRAFT"):
        blocked.append(
            "script approval pending: the script + breakdown "
            "have not been approved by the user")
    text_errors = validate_text_overlay_policy(
        project.get("text_overlay_policy") or {})
    blocked += [f"text overlay policy: {err}"
                for err in text_errors]
    generations = []
    scope_asset_ids: set[str] = set()
    for shot in shots:
        if not isinstance(shot, dict):
            blocked.append("shot list carries a non-object shot")
            continue
        shot_id = shot.get("shot_id") or "unknown-shot"
        # Elements-aware pricing, computed here at the top of
        # the loop — before any continue — so every generation
        # entry, including blocked ones, carries its rate and
        # cost. A shot uses elements iff the plan carries
        # identity bindings AND this shot names a character AND
        # that shot has a non-empty binding list. Per-shot cost
        # is rounded to 3 decimals so the plan total (the sum,
        # rounded to 2) matches the exact arithmetic.
        shot_bindings = (identity_bindings.get(shot_id)
                         if identity_bindings is not None
                         else None)
        uses_elements = (
            identity_bindings is not None
            and bool(shot.get("character_id"))
            and isinstance(shot_bindings, list)
            and len(shot_bindings) > 0)
        shot_rate = kling_3_pro_rate_usd_per_second(
            generate_audio=bool(generate_audio),
            with_elements=uses_elements)
        shot_cost = round(float(duration_seconds) * shot_rate, 3)
        for ref_id in shot.get("reference_ids") or []:
            scope_asset_ids.add(str(ref_id))
        visual = shot.get("visual") or {}
        if visual.get("asset_id"):
            scope_asset_ids.add(str(visual["asset_id"]))
        keyframe = shot.get("keyframe") or {}
        if not keyframe.get("file") or not keyframe.get("sha256"):
            blocked.append(
                f"shot {shot_id} keyframe is pending generation "
                "after script approval")
            generations.append(
                {"shot_id": shot_id, "status": "blocked",
                 "reason": "keyframe pending",
                 "uses_elements": uses_elements,
                 "rate_usd_per_second": shot_rate,
                 "estimated_cost_usd": shot_cost})
            continue
        motion_errors = validate_motion_prompt(
            shot.get("motion_prompt"))
        if motion_errors:
            blocked.append(
                f"shot {shot_id} motion prompt: "
                + "; ".join(motion_errors))
            generations.append(
                {"shot_id": shot_id, "status": "blocked",
                 "reason": "motion prompt invalid",
                 "uses_elements": uses_elements,
                 "rate_usd_per_second": shot_rate,
                 "estimated_cost_usd": shot_cost})
            continue
        prompt = build_i2v_motion_prompt(shot["motion_prompt"])
        entry = {"shot_id": shot_id, "status": "ready",
                 "keyframe_file": keyframe["file"],
                 "keyframe_sha256": keyframe["sha256"],
                 "prompt": prompt,
                 "duration_seconds": duration_seconds,
                 "generate_audio": bool(generate_audio),
                 "uses_elements": uses_elements,
                 "rate_usd_per_second": shot_rate,
                 "estimated_cost_usd": shot_cost}
        if identity_bindings is not None:
            try:
                elements = build_shot_elements(
                    shot, identity_bindings,
                    workspace_root=workspace_root)
            except ImageToVideoError as exc:
                blocked.append(f"shot {shot_id} identity: {exc}")
                generations.append(
                    {"shot_id": shot_id, "status": "blocked",
                     "reason": "character reference missing or "
                               "pending",
                     "uses_elements": uses_elements,
                     "rate_usd_per_second": shot_rate,
                     "estimated_cost_usd": shot_cost})
                continue
            if elements is not None:
                try:
                    validate_fal_video_elements(elements, prompt)
                except Exception as exc:
                    blocked.append(
                        f"shot {shot_id} prompt/elements: {exc}")
                    generations.append(
                        {"shot_id": shot_id, "status": "blocked",
                         "reason": "prompt element references do "
                                   "not match the elements array",
                         "uses_elements": uses_elements,
                         "rate_usd_per_second": shot_rate,
                         "estimated_cost_usd": shot_cost})
                    continue
                entry["elements"] = elements
                for binding in identity_bindings.get(shot_id) or []:
                    if isinstance(binding, dict):
                        frontal = binding.get("frontal") or {}
                        if frontal.get("asset_id"):
                            scope_asset_ids.add(
                                str(frontal["asset_id"]))
                        for ref in binding.get("additional") or []:
                            if isinstance(ref, dict) \
                                    and ref.get("asset_id"):
                                scope_asset_ids.add(
                                    str(ref["asset_id"]))
        key = idempotency_key(
            project_id, shot_id, PROVIDER_ID, MODEL_ID,
            keyframe["sha256"], prompt)
        entry["idempotency_key"] = key
        generations.append(entry)
    auth_errors = validate_authorization(
        authorization, provider_id=PROVIDER_ID, model=MODEL_ID,
        operation=OPERATION,
        required_generations=len(shots),
        scope_asset_ids=sorted(scope_asset_ids))
    blocked += [f"authorization: {err}" for err in auth_errors]
    # Plan cost is the sum of the per-shot costs (each priced
    # by its own elements usage), rounded to 2 decimals. The
    # plan-level rate is the single rate only when all shots
    # share one rate, otherwise None (a mixed plan has no
    # single rate).
    total_seconds = len(shots) * float(duration_seconds)
    plan_rates = {gen.get("rate_usd_per_second")
                  for gen in generations}
    plan_rate = plan_rates.pop() if len(plan_rates) == 1 else None
    plan_cost = round(
        sum(gen.get("estimated_cost_usd", 0.0)
            for gen in generations), 2)
    plan = {"project_id": project_id,
            "provider_id": PROVIDER_ID, "model": MODEL_ID,
            "operation": OPERATION,
            "status": "BLOCKED" if blocked else "READY",
            "blocked_reasons": blocked,
            "counts": counts,
            "generations": generations,
            "total_seconds": total_seconds,
            "rate_usd_per_second": plan_rate,
            "rate_source": RATE_SOURCE,
            "estimated_cost_usd": plan_cost,
            # Retention truth for this endpoint: ZDR is
            # UNCONFIRMED and is never claimed; the request
            # carries X-Fal-Store-IO: 0 and the fal CDN v3
            # lifecycle/ACL headers (see retention_truth_table).
            "zdr_status": ZDR_STATUS}
    return plan


# ------------------------------------------------------------------
# Execution (authorized only — refuses a BLOCKED plan)
# ------------------------------------------------------------------

def execute_i2v_plan(plan, *, adapter, delivery_root, ledger,
                     output_dir, work_dir, registry=None,
                     poll_interval_s=5, max_polls=60,
                     ffprobe="ffprobe", ffmpeg="ffmpeg") -> dict:
    """Execute a READY plan through the provider adapter.

    Submits each generation (idempotent via the ledger), polls
    to completion, retrieves the clip through the adapter's
    secure URL policy, verifies the clip (type, duration,
    geometry, codec) and its motion, and registers it. A BLOCKED
    plan raises with code ``authorization-denied`` before any
    submission. A failed or motion-rejected clip raises and
    stops the run — no partial final video is ever assembled
    from a failed clip.
    """
    if not isinstance(plan, dict) or plan.get("status") != "READY":
        reasons = (plan or {}).get("blocked_reasons") or [
            "plan is not READY"]
        raise ImageToVideoError(
            ["image-to-video plan is BLOCKED:"] + list(reasons),
            code="authorization-denied")
    project_id = plan["project_id"]
    registry = dict(registry or {})
    executed = []
    for generation in plan.get("generations") or []:
        shot_id = generation["shot_id"]
        keyframe_path = os.path.join(
            delivery_root, generation["keyframe_file"])
        validated = validate_source_image(
            keyframe_path,
            expected_sha256=generation["keyframe_sha256"],
            ffprobe=ffprobe)
        start_image_url = keyframe_data_uri(validated)
        built = build_i2v_request(
            PROVIDER_ID, MODEL_ID, prompt=generation["prompt"],
            start_image_url=start_image_url,
            duration_seconds=generation["duration_seconds"],
            generate_audio=generation["generate_audio"],
            elements=generation.get("elements"))
        packet = {"model": MODEL_ID,
                  "canonical_instruction": generation["prompt"],
                  "task_id": f"{project_id}-{shot_id}",
                  # The adapter-served task type is
                  # "video-generation" (see HttpProviderAdapter
                  # capabilities); the operation
                  # "generate-video-from-image" is the authorized
                  # operation recorded on the plan and the
                  # authorization record, not the adapter task
                  # type.
                  "task_type": "video-generation"}
        # The adapter builds its request from packet + context
        # through the provider contract, so the context must
        # carry the I2V inputs — otherwise the adapter cannot
        # rebuild the contract-built request.
        context = {"execution_id": f"i2v-{project_id}-{shot_id}",
                   "idempotency_key":
                       generation["idempotency_key"],
                   "start_image_url": start_image_url,
                   "duration": str(generation["duration_seconds"]),
                   "generate_audio": generation["generate_audio"]}
        if generation.get("elements") is not None:
            # Elements travel in the context too, so the
            # adapter's contract rebuild matches the
            # contract-built request exactly.
            context["elements"] = generation["elements"]
        request = adapter.translate(packet, context)
        if request.get("contract_request") != built:
            _fail(f"shot {shot_id}: adapter translation does not "
                  "match the contract-built request",
                  code="local-tool-error")
        submitted = submit_i2v_generation(
            adapter, request, context, ledger=ledger,
            key=generation["idempotency_key"])
        job_id = submitted["job_id"]
        # The poll path needs the queue URLs from the submit
        # response (fal.ai has no poll template): carry them in
        # the poll context, never drop them.
        context = {**context,
                   "status_url": submitted.get("status_url"),
                   "response_url": submitted.get("response_url"),
                   "cancel_url": submitted.get("cancel_url")}
        result = poll_i2v_generation(
            adapter, job_id, context, max_polls=max_polls,
            poll_interval_s=poll_interval_s)
        artifact = (result or {}).get("output") or {}
        clip_rel = artifact.get("path")
        if not clip_rel:
            _fail(f"shot {shot_id}: provider job {job_id} "
                  "completed without an output artifact",
                  code="malformed-output")
        clip_path = clip_rel if os.path.isabs(clip_rel) \
            else os.path.join(delivery_root, clip_rel)
        if not os.path.isfile(clip_path):
            clip_path = os.path.join(output_dir,
                                     os.path.basename(clip_rel))
        verified = verify_generated_clip(
            clip_path,
            expected_duration_seconds=generation[
                "duration_seconds"],
            expected_width=1080, expected_height=1920,
            ffprobe=ffprobe)
        motion = validate_clip_motion(
            clip_path, work_dir=os.path.join(work_dir, shot_id),
            ffmpeg=ffmpeg, ffprobe=ffprobe)
        if not motion["passes"]:
            _fail(f"shot {shot_id}: generated clip failed motion "
                  f"validation ({motion['classification']}): "
                  f"{motion['reason']}",
                  code="motion-validation-failed")
        record = pa.new_asset_record(
            asset_id=f"i2v-{shot_id}", project_id=project_id,
            shot_id=shot_id, asset_type="video-clip",
            provider=PROVIDER_ID, provider_status="EXERCISED",
            path=os.path.basename(clip_path),
            mime_type="video/mp4",
            provenance="FROM_APPROVED_PROJECT_CANON",
            license_class="original")
        record["generation"] = {
            "method": "provider-generated image-to-video",
            "provider": PROVIDER_ID, "model": MODEL_ID,
            "provider_job_id": job_id,
            "keyframe_sha256": generation["keyframe_sha256"],
            "native_width": verified["width"],
            "native_height": verified["height"],
            "native_duration_seconds": verified[
                "duration_seconds"],
            "motion_classification": motion["classification"]}
        record = pa.verify_asset(record, os.path.dirname(clip_path))
        registry = pa.register_asset(registry, record)
        executed_entry = {
            "shot_id": shot_id, "provider_job_id": job_id,
            "clip_sha256": verified["sha256"],
            "clip_bytes": verified["bytes"],
            "native_width": verified["width"],
            "native_height": verified["height"],
            "duration_seconds": verified["duration_seconds"],
            "motion_classification": motion["classification"]}
        # The original provider result URL, recorded in redacted
        # form only (scheme://host/path — the query string is
        # never stored). The adapter records it during retrieve().
        result_url = getattr(adapter, "last_result_url_record",
                             None)
        if isinstance(result_url, dict):
            executed_entry["provider_result_url"] = result_url
        executed.append(executed_entry)
    return {"project_id": project_id, "status": "completed",
            "generations": executed, "registry": registry}
