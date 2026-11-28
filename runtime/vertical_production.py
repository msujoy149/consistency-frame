"""Consistency Frame P1 — complete vertical-video production project (CF-WO-P1-006).

Phase A (complete production project model) and Phase F (production
execution state and recovery).

A P1-006 project connects, in one validated record:

    script -> production analysis -> identities (character /
    environment / prop, when the project has any) -> visual assets
    -> voice assets -> music / sound effects -> canonical timeline
    -> output profile -> execution state -> QC results -> delivery
    artifacts.

Every production decision carries provenance from the P1-004
vocabulary:

    EXPLICIT_FROM_USER, FROM_APPROVED_PROJECT_CANON,
    INFERRED_FOR_PRODUCTION, NEEDS_USER_DECISION.

An inferred choice is never approved canon: inferences are
recorded as inferences, and a project must not enter execution
while a required user decision is unresolved — ``build_project``
refuses the project and ``validation_report`` names every missing
decision. No character or voice identity is registered here:
registration stays the existing explicit-authorisation flow, and
this reference project is narrator-only, so no registry is needed
at all.

Execution state machine (WO §10). The states reuse the P1-004
job-state conventions where they overlap (a project that fails
validation never leaves INTAKE; DELIVERED is terminal), and add
the per-stage states the work order requires:

    INTAKE -> PROJECT_VALIDATED -> ASSETS_PENDING -> ASSETS_READY
    -> VOICE_PENDING -> VOICE_READY -> SOUND_PENDING -> SOUND_READY
    -> TIMELINE_READY -> ASSEMBLY_RUNNING -> ASSEMBLY_COMPLETED
    -> QC_RUNNING -> QC_PASSED -> DELIVERY_READY -> DELIVERED

    FAILED, CANCELLED and NEEDS_USER_DECISION are reachable from
    every non-terminal state. BLOCKED is reachable from every
    non-terminal state and resumes only to the state it came from.

FAILED always carries a failure classification (the P1-005
``FAILURE_CODES`` vocabulary) plus recovery instructions. A stage
is idempotent: ``stage_checkpoint`` records the stage, the
SHA-256 of its canonical inputs, and its outputs; ``stage_is_done``
lets a stage runner skip re-execution when the inputs are
unchanged and the outputs still verify. A resumed job never
re-submits an already verified, billable output: this reference
project has no billable outputs (all generation is local), and
resume re-validates the recorded checkpoints before continuing.

Persistence reuses :mod:`runtime.production_store` — the project
record rides on the production job envelope (``job_id`` +
``project_id``), with the same integrity hash. No second job
database exists. Resume loads the stored record and revalidates
it; it never trusts a stored state blindly.

This module never touches media files, never calls a provider,
and never generates anything: it owns validation, state,
identity and provenance only. Media work lives in
:mod:`runtime.production_assets`, :mod:`runtime.production_voice`,
:mod:`runtime.production_audio`,
:mod:`runtime.production_timeline`,
:mod:`runtime.production_qc` and
:mod:`runtime.production_delivery`.
"""

from __future__ import annotations

import copy
import hashlib
import re
import shutil

from . import local_session
from . import production_store
from .task_compiler import canonical_json, sha256_hex

VERTICAL_PROJECT_SCHEMA_VERSION = "2.5"

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")

# Line/shot references are internal cross-references, not registry
# ids: they use the same lowercase shape with a two-character
# minimum (``l1``, ``s1``), while project/job/asset ids keep the
# repo-wide three-character minimum above.
_REF_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")

PROVENANCE_VALUES = (
    "EXPLICIT_FROM_USER",
    "FROM_APPROVED_PROJECT_CANON",
    "INFERRED_FOR_PRODUCTION",
    "NEEDS_USER_DECISION",
)

# WO §10 state machine. INTAKE is the pre-validation state;
# PROJECT_VALIDATED is the first state a built project holds.
VERTICAL_PROJECT_STATES = (
    "INTAKE",
    "PROJECT_VALIDATED",
    "ASSETS_PENDING",
    "ASSETS_READY",
    "VOICE_PENDING",
    "VOICE_READY",
    "SOUND_PENDING",
    "SOUND_READY",
    "TIMELINE_READY",
    "ASSEMBLY_RUNNING",
    "ASSEMBLY_COMPLETED",
    "QC_RUNNING",
    "QC_PASSED",
    "DELIVERY_READY",
    "DELIVERED",
    "FAILED",
    "CANCELLED",
    "NEEDS_USER_DECISION",
    "BLOCKED",
)

_TERMINAL = ("DELIVERED", "FAILED", "CANCELLED")
_NON_TERMINAL = tuple(s for s in VERTICAL_PROJECT_STATES
                      if s not in _TERMINAL)

# The linear production order. A stage may be re-entered from its
# own READY state (idempotent re-run) and from NEEDS_USER_DECISION
# once the user resolves the blocker.
_LINEAR = (
    "INTAKE",
    "PROJECT_VALIDATED",
    "ASSETS_PENDING",
    "ASSETS_READY",
    "VOICE_PENDING",
    "VOICE_READY",
    "SOUND_PENDING",
    "SOUND_READY",
    "TIMELINE_READY",
    "ASSEMBLY_RUNNING",
    "ASSEMBLY_COMPLETED",
    "QC_RUNNING",
    "QC_PASSED",
    "DELIVERY_READY",
    "DELIVERED",
)

PROJECT_TRANSITIONS = {}
for _i, _state in enumerate(_LINEAR):
    _allowed = []
    if _i > 0:
        # Normal forward step from the previous state.
        _allowed.append(_LINEAR[_i - 1])
    if 0 < _i < len(_LINEAR) - 1:
        # Idempotent re-run: the next state may step back to this
        # one (for example ASSETS_READY -> ASSETS_PENDING to
        # regenerate one asset). INTAKE is never a target again,
        # and DELIVERED is terminal.
        _allowed.append(_LINEAR[_i + 1])
    PROJECT_TRANSITIONS[_state] = tuple(_allowed)
PROJECT_TRANSITIONS["INTAKE"] = ()
# NEEDS_USER_DECISION may resume to the state the project was in
# when the decision was requested (recorded in previous_state),
# and FAILED/CANCELLED/BLOCKED are handled in transition_project.
PROJECT_TRANSITIONS["NEEDS_USER_DECISION"] = _NON_TERMINAL
PROJECT_TRANSITIONS["BLOCKED"] = _NON_TERMINAL
PROJECT_TRANSITIONS["FAILED"] = _NON_TERMINAL
PROJECT_TRANSITIONS["CANCELLED"] = _NON_TERMINAL

# Failure classification vocabulary: the P1-005 codes, reused
# verbatim so a failure reason means the same thing in both
# runtimes. "retryable" is advisory only; nothing retries
# automatically.
from .media_execution import FAILURE_CODES  # noqa: E402

# Only these render paths exist in this round. "openmontage"
# production assembly is NOT_TESTED and is refused here — the
# single proven path is FFmpeg.
SUPPORTED_RENDER_PATHS = ("ffmpeg",)

# Visual recipe kinds the asset stage can generate (see
# runtime.production_assets.generate_visual_asset, and
# generate_still_clip for the "ai-still" kind — an AI-generated
# still image animated locally with FFmpeg zoompan; the clip is
# built by generate_still_clip, never by visual_argv).
#
# "i2v-clip" is a recipe kind the asset stage can NEVER
# generate locally: it is a real provider image-to-video
# generation from a verified keyframe (runtime.image_to_video),
# produced only under an explicit authorization record. The
# local asset stage refuses it (see visual_argv) and the R2
# driver fails closed instead of substituting a still animation.
VISUAL_RECIPE_KINDS = (
    "gradient-band",
    "gradient-split",
    "gradient-rings",
    "gradient-scan",
    "gradient-frames",
    "gradient-title",
    "ai-still",
    "i2v-clip",
)


class VerticalProductionError(ValueError):
    """Project error carrying a list of structured messages.

    ``code`` is an optional failure-classification code from
    :data:`FAILURE_CODES` (for example ``"validation-failed"``).
    ``None`` means unclassified.
    """

    def __init__(self, errors, code=None):
        if isinstance(errors, str):
            errors = [errors]
        self.errors = list(errors)
        self.code = code
        super().__init__("; ".join(self.errors))


def _require_session(session) -> None:
    if not local_session.is_active_session(session):
        raise VerticalProductionError(
            "a P1-006 project operation needs an exact active "
            "LocalSession", code="authorization-denied")


def _is_id(value) -> bool:
    return isinstance(value, str) and bool(_ID_RE.match(value))


def _is_ref_id(value) -> bool:
    return isinstance(value, str) and bool(_REF_ID_RE.match(value))


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


# ------------------------------------------------------------------
# Output profile / audio profile validation (Phase A)
# ------------------------------------------------------------------

def validate_output_profile(profile) -> list:
    """Output-profile errors (empty list = valid).

    The required vertical profile is explicit and validated here,
    never hardcoded in the renderer: 9:16, 1080x1920, 30 FPS,
    H.264/AAC, MP4, stereo.
    """
    errors: list[str] = []
    if not isinstance(profile, dict):
        return ["output_profile: expected an object, "
                f"got {type(profile).__name__}"]
    if profile.get("format") != "mp4":
        errors.append("output_profile.format must be 'mp4', got "
                      f"{profile.get('format')!r}")
    if profile.get("aspect_ratio") != "9:16":
        errors.append("output_profile.aspect_ratio must be '9:16', "
                      f"got {profile.get('aspect_ratio')!r}")
    if profile.get("width") != 1080:
        errors.append("output_profile.width must be 1080, got "
                      f"{profile.get('width')!r}")
    if profile.get("height") != 1920:
        errors.append("output_profile.height must be 1920, got "
                      f"{profile.get('height')!r}")
    fps = profile.get("frame_rate")
    if not _is_number(fps) or float(fps) != 30.0:
        errors.append("output_profile.frame_rate must be 30, got "
                      f"{fps!r}")
    if profile.get("video_codec") != "h264":
        errors.append("output_profile.video_codec must be 'h264', "
                      f"got {profile.get('video_codec')!r}")
    if profile.get("audio_codec") != "aac":
        errors.append("output_profile.audio_codec must be 'aac', "
                      f"got {profile.get('audio_codec')!r}")
    if profile.get("audio_channels") != 2:
        errors.append("output_profile.audio_channels must be 2 "
                      f"(stereo), got {profile.get('audio_channels')!r}")
    rate = profile.get("audio_sample_rate")
    if rate not in (44100, 48000):
        errors.append("output_profile.audio_sample_rate must be "
                      f"44100 or 48000, got {rate!r}")
    lo = profile.get("duration_min_seconds")
    hi = profile.get("duration_max_seconds")
    if not _is_number(lo) or float(lo) <= 0:
        errors.append("output_profile.duration_min_seconds must be "
                      f"a positive number, got {lo!r}")
    if not _is_number(hi) or float(hi) <= 0:
        errors.append("output_profile.duration_max_seconds must be "
                      f"a positive number, got {hi!r}")
    if _is_number(lo) and _is_number(hi) and float(hi) < float(lo):
        errors.append("output_profile.duration_max_seconds "
                      f"({hi!r}) is below duration_min_seconds "
                      f"({lo!r})")
    return errors


def validate_audio_profile(profile) -> list:
    """Audio-profile errors (empty list = valid).

    The loudness target lives in the project audio profile —
    there is no hidden universal target. The values are validated
    as sane ranges only; the QC stage reports the actual measured
    values against them.
    """
    errors: list[str] = []
    if not isinstance(profile, dict):
        return ["audio_profile: expected an object, "
                f"got {type(profile).__name__}"]
    if not isinstance(profile.get("id"), str) or not profile.get("id"):
        errors.append("audio_profile.id is missing or not a string")
    loudness = profile.get("target_loudness_lufs")
    if not _is_number(loudness) or not -70.0 <= float(loudness) <= 0.0:
        errors.append("audio_profile.target_loudness_lufs must be "
                      f"between -70 and 0, got {loudness!r}")
    peak = profile.get("target_true_peak_dbfs")
    if not _is_number(peak) or not -20.0 <= float(peak) <= 0.0:
        errors.append("audio_profile.target_true_peak_dbfs must be "
                      f"between -20 and 0, got {peak!r}")
    duck = profile.get("music_duck_db")
    if duck is not None and (not _is_number(duck) or float(duck) > 0):
        errors.append("audio_profile.music_duck_db must be 0 or "
                      f"negative, got {duck!r}")
    for field in ("fade_in_seconds", "fade_out_seconds"):
        value = profile.get(field)
        if value is not None and (not _is_number(value)
                                  or float(value) < 0):
            errors.append(f"audio_profile.{field} must be a "
                          f"non-negative number, got {value!r}")
    if profile.get("voice_priority") is not True:
        errors.append("audio_profile.voice_priority must be true: "
                      "the narrator leads the mix")
    return errors


# ------------------------------------------------------------------
# Project construction and validation (Phase A)
# ------------------------------------------------------------------

def _validate_script_lines(lines) -> list:
    errors: list[str] = []
    if not isinstance(lines, list) or not lines:
        return ["script.lines must be a non-empty list"]
    seen: set[str] = set()
    for index, line in enumerate(lines):
        where = f"script.lines[{index}]"
        if not isinstance(line, dict):
            errors.append(f"{where}: expected an object")
            continue
        line_id = line.get("line_id")
        if not _is_ref_id(line_id):
            errors.append(f"{where}.line_id {line_id!r} is not a "
                          "valid id")
        elif line_id in seen:
            errors.append(f"script line {line_id!r} appears twice")
        else:
            seen.add(line_id)
        if not isinstance(line.get("text"), str) or not line["text"]:
            errors.append(f"{where}.text is missing or empty")
        if not _is_ref_id(line.get("shot_id")):
            errors.append(f"{where}.shot_id {line.get('shot_id')!r} "
                          "is not a valid id")
    return errors


def _validate_shots(shots, line_ids) -> list:
    errors: list[str] = []
    if not isinstance(shots, list) or not shots:
        return ["shots must be a non-empty list"]
    seen: set[str] = set()
    for index, shot in enumerate(shots):
        where = f"shots[{index}]"
        if not isinstance(shot, dict):
            errors.append(f"{where}: expected an object")
            continue
        shot_id = shot.get("shot_id")
        if not _is_ref_id(shot_id):
            errors.append(f"{where}.shot_id {shot_id!r} is not a "
                          "valid id")
        elif shot_id in seen:
            errors.append(f"shot {shot_id!r} appears twice")
        else:
            seen.add(shot_id)
        if shot.get("line_id") not in line_ids:
            errors.append(f"{where}.line_id "
                          f"{shot.get('line_id')!r} does not resolve "
                          "to a script line")
        if not isinstance(shot.get("visual_direction"), str) \
                or not shot["visual_direction"]:
            errors.append(f"{where}.visual_direction is missing or "
                          "empty: every planned shot needs a valid "
                          "visual direction")
        visual = shot.get("visual") or {}
        if not isinstance(visual, dict):
            errors.append(f"{where}.visual: expected an object")
        elif visual.get("kind") not in VISUAL_RECIPE_KINDS:
            errors.append(f"{where}.visual.kind "
                          f"{visual.get('kind')!r} is not a known "
                          "visual recipe kind")
        minimum = shot.get("min_duration_seconds")
        if not _is_number(minimum) or float(minimum) <= 0:
            errors.append(f"{where}.min_duration_seconds must be a "
                          f"positive number, got {minimum!r}")
    return errors


def _validate_voice_config(voice, script_lines) -> list:
    errors: list[str] = []
    if not isinstance(voice, dict):
        return ["voice_config: expected an object, "
                f"got {type(voice).__name__}"]
    line_ids = {ln.get("line_id") for ln in script_lines or []
                if isinstance(ln, dict)}
    script_text = {ln.get("line_id"): ln.get("text")
                   for ln in script_lines or []
                   if isinstance(ln, dict)}
    if not isinstance(voice.get("voice_id"), str) or not voice["voice_id"]:
        errors.append("voice_config.voice_id is missing or not a string")
    if voice.get("language") not in ("en-US", "bn-BD", "hi-IN", "en-GB"):
        errors.append("voice_config.language "
                      f"{voice.get('language')!r} is not a supported "
                      "narrator language")
    if voice.get("engine") != "omnivoice":
        errors.append("voice_config.engine must be 'omnivoice', got "
                      f"{voice.get('engine')!r}")
    if voice.get("provider") != "provider-voicestudio-omnivoice":
        errors.append("voice_config.provider must be "
                      "'provider-voicestudio-omnivoice', got "
                      f"{voice.get('provider')!r}")
    if voice.get("commercial_use") != "non-commercial-only":
        errors.append("voice_config.commercial_use must be "
                      "'non-commercial-only' for the default "
                      "OmniVoice weights (CC-BY-NC), got "
                      f"{voice.get('commercial_use')!r}")
    seed = voice.get("seed")
    if not isinstance(seed, int) or isinstance(seed, bool):
        errors.append(f"voice_config.seed must be an integer, got "
                      f"{seed!r}")
    if not isinstance(voice.get("instruct"), str) \
            or not voice["instruct"]:
        errors.append("voice_config.instruct must be a non-empty "
                      "fixed English tag")
    lines = voice.get("lines")
    if not isinstance(lines, list) or not lines:
        errors.append("voice_config.lines must be a non-empty list")
        return errors
    seen: set[str] = set()
    for index, line in enumerate(lines):
        where = f"voice_config.lines[{index}]"
        if not isinstance(line, dict):
            errors.append(f"{where}: expected an object")
            continue
        line_id = line.get("line_id")
        if line_id in seen:
            errors.append(f"voice line {line_id!r} appears twice")
        seen.add(line_id)
        if line_id not in line_ids:
            errors.append(f"{where}.line_id {line_id!r} does not "
                          "resolve to a script line")
        if not isinstance(line.get("text"), str) or not line["text"]:
            errors.append(f"{where}.text is missing or empty")
        elif line.get("text") != script_text.get(line_id):
            errors.append(f"{where}.text does not match the script "
                          f"line {line_id!r} byte-for-byte: dialogue "
                          "is preserved verbatim unless a rewrite "
                          "was explicitly requested")
    missing = line_ids - seen
    if missing:
        errors.append("voice_config.lines is missing dialogue for "
                      f"script lines: {sorted(missing)}")
    return errors


def _validate_sound_plan(sound, shot_ids) -> list:
    errors: list[str] = []
    if not isinstance(sound, dict):
        return ["sound_plan: expected an object, "
                f"got {type(sound).__name__}"]
    tracks = sound.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        errors.append("sound_plan.tracks must be a non-empty list")
        return errors
    kinds = [t.get("kind") for t in tracks if isinstance(t, dict)]
    if "dialogue" not in kinds:
        errors.append("sound_plan.tracks must include a dialogue "
                      "track: the narrator leads the mix")
    for index, track in enumerate(tracks):
        where = f"sound_plan.tracks[{index}]"
        if not isinstance(track, dict):
            errors.append(f"{where}: expected an object")
            continue
        if not isinstance(track.get("track_id"), str) \
                or not track["track_id"]:
            errors.append(f"{where}.track_id is missing or not a "
                          "string")
        gain = track.get("gain_db")
        if not _is_number(gain):
            errors.append(f"{where}.gain_db must be a number, got "
                          f"{gain!r}")
        if track.get("source") not in ("voicestudio-omnivoice",
                                       "synthesized", "supplied",
                                       "licensed"):
            errors.append(f"{where}.source "
                          f"{track.get('source')!r} is not a known "
                          "sound source")
    for index, cue in enumerate(sound.get("cues") or []):
        where = f"sound_plan.cues[{index}]"
        if not isinstance(cue, dict):
            errors.append(f"{where}: expected an object")
            continue
        if cue.get("shot_id") not in shot_ids:
            errors.append(f"{where}.shot_id "
                          f"{cue.get('shot_id')!r} does not resolve "
                          "to a shot")
        if not isinstance(cue.get("duration_seconds"), (int, float)) \
                or float(cue.get("duration_seconds") or 0) <= 0:
            errors.append(f"{where}.duration_seconds must be a "
                          "positive number")
    for index, silence in enumerate(sound.get("silences") or []):
        where = f"sound_plan.silences[{index}]"
        if not isinstance(silence, dict):
            errors.append(f"{where}: expected an object")
            continue
        if silence.get("intentional") is not True:
            errors.append(f"{where}: silence must be recorded as "
                          "intentional with a reason, or it is a "
                          "defect — a silent sequence is never "
                          "silently accepted")
        if not isinstance(silence.get("reason"), str) \
                or not silence["reason"]:
            errors.append(f"{where}.reason is missing: intentional "
                          "silence needs a recorded reason")
    return errors


def _validate_assembly_config(assembly, output_profile) -> list:
    errors: list[str] = []
    if not isinstance(assembly, dict):
        return ["assembly_config: expected an object, "
                f"got {type(assembly).__name__}"]
    if assembly.get("render_path") not in SUPPORTED_RENDER_PATHS:
        errors.append("assembly_config.render_path "
                      f"{assembly.get('render_path')!r} is not a "
                      "supported render path in this round "
                      f"(supported: {SUPPORTED_RENDER_PATHS}); "
                      "OpenMontage production assembly is NOT_TESTED")
    if assembly.get("video_codec") != "libx264":
        errors.append("assembly_config.video_codec must be 'libx264' "
                      "to produce the h264 output profile, got "
                      f"{assembly.get('video_codec')!r}")
    if assembly.get("audio_codec") != "aac":
        errors.append("assembly_config.audio_codec must be 'aac', "
                      f"got {assembly.get('audio_codec')!r}")
    if output_profile.get("audio_sample_rate") != \
            assembly.get("audio_sample_rate"):
        errors.append("assembly_config.audio_sample_rate "
                      f"{assembly.get('audio_sample_rate')!r} does "
                      "not match output_profile.audio_sample_rate "
                      f"{output_profile.get('audio_sample_rate')!r}")
    transition = assembly.get("transition") or {}
    if transition.get("type") not in ("cut", "fadeblack"):
        errors.append("assembly_config.transition.type "
                      f"{transition.get('type')!r} is not supported "
                      "(supported: cut, fadeblack)")
    return errors


def _validate_provenance(provenance) -> list:
    errors: list[str] = []
    if not isinstance(provenance, dict):
        return ["provenance: expected an object"]
    for key, value in provenance.items():
        if value not in PROVENANCE_VALUES:
            errors.append(f"provenance.{key} {value!r} is not a "
                          "known provenance value")
        if value == "NEEDS_USER_DECISION":
            errors.append(f"provenance.{key} is NEEDS_USER_DECISION: "
                          "a required user decision is unresolved — "
                          "the project must not enter execution")
    return errors


def validate_project(project, *, require_adapters=True) -> list:
    """Project-record errors (empty list = valid).

    Pure validation: no session, no filesystem, no provider. Set
    ``require_adapters`` False only for structural checks in
    unit tests — the render path always requires the adapters.
    """
    errors: list[str] = []
    if not isinstance(project, dict):
        return ["project: expected an object, "
                f"got {type(project).__name__}"]
    if project.get("schema_version") != VERTICAL_PROJECT_SCHEMA_VERSION:
        errors.append("project.schema_version must be "
                      f"'{VERTICAL_PROJECT_SCHEMA_VERSION}', got "
                      f"{project.get('schema_version')!r}")
    if not _is_id(project.get("project_id")):
        errors.append(f"project.project_id {project.get('project_id')!r} "
                      "is not a valid id")
    if not _is_id(project.get("job_id")):
        errors.append(f"project.job_id {project.get('job_id')!r} is "
                      "not a valid id")
    if project.get("state") not in VERTICAL_PROJECT_STATES:
        errors.append(f"project.state {project.get('state')!r} is not "
                      "a known P1-006 project state")
    errors.extend(validate_output_profile(
        project.get("output_profile") or {}))
    errors.extend(validate_audio_profile(
        project.get("audio_profile") or {}))
    script = project.get("script") or {}
    lines = script.get("lines") if isinstance(script, dict) else None
    errors.extend(_validate_script_lines(lines))
    line_ids = {ln.get("line_id") for ln in lines
                if isinstance(ln, dict)
                and _is_ref_id(ln.get("line_id"))}
    errors.extend(_validate_shots(project.get("shots") or [], line_ids))
    shot_ids = {s.get("shot_id") for s in project.get("shots") or []
                if isinstance(s, dict)
                and _is_ref_id(s.get("shot_id"))}
    errors.extend(_validate_voice_config(
        project.get("voice") or {}, lines))
    errors.extend(_validate_sound_plan(
        project.get("sound") or {}, shot_ids))
    errors.extend(_validate_assembly_config(
        project.get("assembly") or {}, project.get("output_profile") or {}))
    errors.extend(_validate_provenance(project.get("provenance") or {}))
    analysis = project.get("analysis") or {}
    if not isinstance(analysis, dict) or not analysis.get("id"):
        errors.append("project.analysis is missing or carries no id")
    elif (analysis.get("open_questions") or []) != []:
        errors.append("project.analysis.open_questions is not empty: "
                      "open questions block execution — resolve them "
                      "or record an explicit user decision first")
    resolutions = (analysis.get("character_resolutions") or [])
    if not isinstance(resolutions, list):
        errors.append("project.analysis.character_resolutions must "
                      "be a list")
    elif resolutions:
        errors.append("project.analysis carries character resolutions "
                      "but this project model resolves identities "
                      "only through an explicit identity policy — "
                      "pass one to build_project")
    if require_adapters:
        if shutil.which("ffmpeg") is None:
            errors.append("required execution adapter 'ffmpeg' is "
                          "not available on PATH")
        if shutil.which("ffprobe") is None:
            errors.append("required execution adapter 'ffprobe' is "
                          "not available on PATH")
    return errors


def build_project(session, project_config, script_lines, analysis,
                  shot_list, voice_config, sound_plan, assembly_config,
                  *, identity_policy=None, character_registry=None,
                  voice_registry=None) -> dict:
    """Build and validate a complete P1-006 project.

    ``script_lines`` is the structured script
    (``[{line_id, shot_id, text}]``); the caller parses the source
    script file. Voice lines must match the script lines exactly —
    same ids, same text, same order — so dialogue is preserved
    verbatim. Identity resolution is narrator-only by default:
    any character resolution in the analysis without an explicit
    identity policy (and registries) is refused, and a policy is
    never invented. Raises :class:`VerticalProductionError` with
    every error found; nothing is built half-way.
    """
    _require_session(session)
    errors: list[str] = []
    if not isinstance(project_config, dict):
        raise VerticalProductionError(
            "project_config: expected an object, "
            f"got {type(project_config).__name__}",
            code="validation-failed")
    project_id = project_config.get("project_id")
    if not _is_id(project_id):
        errors.append(f"project_config.project_id {project_id!r} is "
                      "not a valid id")
    errors.extend(validate_output_profile(
        project_config.get("output_profile") or {}))
    errors.extend(validate_audio_profile(
        project_config.get("audio_profile") or {}))
    provenance = project_config.get("provenance") or {}
    errors.extend(_validate_provenance(provenance))
    if not isinstance(analysis, dict):
        errors.append("analysis: expected an object")
    else:
        if (analysis.get("open_questions") or []) != []:
            errors.append("analysis.open_questions is not empty: "
                          "open questions block execution")
        if (analysis.get("character_resolutions") or []) \
                and identity_policy is None:
            errors.append("analysis carries character resolutions "
                          "but no identity policy was supplied — "
                          "identity resolution needs an explicit "
                          "policy, it is never invented")
    if identity_policy is not None and character_registry is None \
            and voice_registry is None:
        errors.append("an identity policy was supplied without any "
                      "registry: the policy cannot resolve anything")
    project = {
        "schema_version": VERTICAL_PROJECT_SCHEMA_VERSION,
        "job_id": f"job-{project_id}" if _is_id(project_id) else None,
        "project_id": project_id,
        "title": project_config.get("title"),
        "state": "PROJECT_VALIDATED",
        "previous_state": None,
        "output_profile": copy.deepcopy(
            project_config.get("output_profile") or {}),
        "audio_profile": copy.deepcopy(
            project_config.get("audio_profile") or {}),
        "narrator": copy.deepcopy(project_config.get("narrator") or {}),
        "provenance": copy.deepcopy(provenance),
        "script": {"lines": copy.deepcopy(script_lines or []),
                   "hash": sha256_hex(canonical_json(
                       script_lines or []))},
        "analysis": copy.deepcopy(analysis or {}),
        "shots": copy.deepcopy(shot_list or []),
        "voice": copy.deepcopy(voice_config or {}),
        "sound": copy.deepcopy(sound_plan or {}),
        "assembly": copy.deepcopy(assembly_config or {}),
        "assets": [],
        "timeline": None,
        "qc": None,
        "delivery": None,
        "checkpoints": [],
        "history": [{"state": "PROJECT_VALIDATED",
                     "reason": "project built and validated"}],
        "failure": None,
    }
    errors.extend(validate_project(project, require_adapters=True))
    if errors:
        raise VerticalProductionError(errors, code="validation-failed")
    return project


def validation_report(project, errors=None) -> dict:
    """Actionable validation report for an incomplete project."""
    if errors is None:
        errors = validate_project(project, require_adapters=True)
    decisions = [e for e in errors if "NEEDS_USER_DECISION" in e
                 or "unresolved" in e or "open questions" in e]
    return {
        "project_id": (project or {}).get("project_id"),
        "valid": not errors,
        "errors": list(errors),
        "decisions_needed": decisions,
        "next_steps": (
            ["resolve every listed error, then rebuild the project"]
            if errors else
            ["project is valid; execution may proceed"]),
    }


# ------------------------------------------------------------------
# State machine (Phase F)
# ------------------------------------------------------------------

def transition_project(session, project, new_state, *, reason="",
                       failure=None) -> dict:
    """Move a project to a new state, enforcing the state machine.

    Returns a NEW project dict; the input is never mutated.
    FAILED requires ``failure`` (``{code, message, recovery}``);
    NEEDS_USER_DECISION requires a reason naming the decision;
    BLOCKED records the previous state and resumes only to it.
    Terminal states never transition.
    """
    _require_session(session)
    if not isinstance(project, dict):
        raise VerticalProductionError("project: expected an object",
                                     code="validation-failed")
    current = project.get("state")
    if new_state not in VERTICAL_PROJECT_STATES:
        raise VerticalProductionError(
            f"unknown target state {new_state!r}",
            code="validation-failed")
    if current in _TERMINAL:
        raise VerticalProductionError(
            f"project in terminal state {current!r} cannot transition "
            f"to {new_state!r}", code="validation-failed")
    if current == new_state:
        raise VerticalProductionError(
            f"project is already in state {current!r}",
            code="validation-failed")
    if new_state == "FAILED":
        if not isinstance(failure, dict) or not failure.get("code") \
                or not failure.get("message") \
                or not failure.get("recovery"):
            raise VerticalProductionError(
                "FAILED requires failure {code, message, recovery}",
                code="validation-failed")
        if failure["code"] not in FAILURE_CODES:
            raise VerticalProductionError(
                f"failure code {failure['code']!r} is not a known "
                "failure classification", code="validation-failed")
    elif failure is not None:
        raise VerticalProductionError(
            "failure details are only valid on a FAILED transition",
            code="validation-failed")
    if new_state == "NEEDS_USER_DECISION" and not reason:
        raise VerticalProductionError(
            "NEEDS_USER_DECISION requires a reason naming the "
            "decision", code="validation-failed")
    if new_state == "BLOCKED":
        allowed = True
    elif current == "BLOCKED":
        if new_state in ("FAILED", "CANCELLED"):
            allowed = True
        elif new_state != project.get("previous_state"):
            raise VerticalProductionError(
                "a BLOCKED project can only resume to the state it "
                f"came from ({project.get('previous_state')!r}), not "
                f"{new_state!r}", code="validation-failed")
        else:
            gates = project.get("blocked_gates") or []
            if gates:
                raise VerticalProductionError(
                    "cannot resume from BLOCKED while blockers "
                    "remain: " + "; ".join(gates),
                    code="validation-failed")
            allowed = True
    elif current == "NEEDS_USER_DECISION":
        if new_state in ("FAILED", "CANCELLED"):
            allowed = True
        elif new_state != project.get("previous_state"):
            raise VerticalProductionError(
                "a NEEDS_USER_DECISION project can only resume to "
                f"the state it came from "
                f"({project.get('previous_state')!r}), not "
                f"{new_state!r}", code="validation-failed")
        else:
            allowed = True
    else:
        allowed = current in PROJECT_TRANSITIONS.get(new_state, ())
    if not allowed:
        raise VerticalProductionError(
            f"invalid transition {current!r} -> {new_state!r}",
            code="validation-failed")
    updated = copy.deepcopy(project)
    if new_state in ("BLOCKED", "NEEDS_USER_DECISION"):
        updated["previous_state"] = current
    else:
        updated["previous_state"] = None
    updated["state"] = new_state
    updated["failure"] = copy.deepcopy(failure) if failure else None
    history = list(updated.get("history") or [])
    history.append({"state": new_state, "reason": reason or "",
                    "from": current})
    updated["history"] = history
    return updated


def stage_input_hash(stage_inputs) -> str:
    """Deterministic input hash for one stage (idempotency)."""
    return sha256_hex(canonical_json(stage_inputs))


def stage_checkpoint(project, stage, input_hash, outputs) -> dict:
    """Record a completed stage checkpoint on the project.

    Returns a NEW project dict. A checkpoint never overwrites an
    existing checkpoint for the same stage with different inputs —
    that is a new attempt, recorded separately.
    """
    updated = copy.deepcopy(project)
    checkpoints = list(updated.get("checkpoints") or [])
    checkpoints.append({
        "stage": stage,
        "input_hash": input_hash,
        "outputs": copy.deepcopy(outputs),
    })
    updated["checkpoints"] = checkpoints
    return updated


def stage_is_done(project, stage, input_hash) -> bool:
    """True when the stage already completed with these inputs."""
    for checkpoint in (project or {}).get("checkpoints") or []:
        if checkpoint.get("stage") == stage \
                and checkpoint.get("input_hash") == input_hash:
            return True
    return False


# ------------------------------------------------------------------
# Persistence (Phase F — reuses the production store)
# ------------------------------------------------------------------

def save_project(session, store_root, project) -> str:
    """Persist a P1-006 project through the production store."""
    _require_session(session)
    return production_store.save_production_job(
        session, store_root, project)


def load_project(store_root, job_id, project_id) -> dict:
    """Load a stored P1-006 project record (metadata read).

    Returns the stored project dict. The caller must revalidate
    it with :func:`validate_project` before continuing — a stored
    state is never trusted blindly.
    """
    record = production_store.load_production_job(
        store_root, job_id, project_id)
    return record["job"]


def save_project_checkpoint(session, store_root, project,
                            checkpoint_id=None) -> str:
    """Persist a checkpoint copy of a P1-006 project."""
    _require_session(session)
    return production_store.save_production_checkpoint(
        session, store_root, project, checkpoint_id=checkpoint_id)


def resume_project(session, store_root, job_id, project_id) -> dict:
    """Resume a stored project under a NEW active session.

    Loads the record, revalidates it structurally, and refuses
    DELIVERED projects (a delivered project is done, never
    re-entered) and FAILED projects without a recorded failure.
    The stored session id is provenance only — resume needs the
    new exact active session passed in, and never auto-resumes a
    paid/external task (this project has none: all generation is
    local, and the checkpoints record that).
    """
    _require_session(session)
    project = load_project(store_root, job_id, project_id)
    errors = validate_project(project, require_adapters=False)
    if errors:
        raise VerticalProductionError(
            ["stored project failed revalidation:"] + errors,
            code="validation-failed")
    state = project.get("state")
    if state == "DELIVERED":
        raise VerticalProductionError(
            "a DELIVERED project cannot be resumed",
            code="validation-failed")
    if state == "FAILED" and not project.get("failure"):
        raise VerticalProductionError(
            "a FAILED project without a recorded failure cannot be "
            "resumed", code="validation-failed")
    return project
