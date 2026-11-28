"""Consistency Frame P1 — production orchestration runtime
(CF-WO-P1-004, Task K).

The missing orchestration layer between the P1-002 skill router, the
P1-003 Script-to-Performance runtime and the P1-004 task compiler.
It owns the production job lifecycle: intake, analysis validation,
production-bundle assembly, provider-task compilation, G1–G6 gate
evaluation, execution-result recording, and QC correction tasks.

Architecture boundary (the whole point of this module): the Python
runtime must NOT pretend to perform creative reasoning. The AI
reasoning host performs the semantic reasoning and fills the
production-analysis draft; this runtime performs deterministic
validation, binding, planning, task compilation, authorization
(state: only an exact active P1-001 session may act) and state
management. No LLM API lives inside this runtime, and none is
needed to work with an AI host.

State machine (explicit, no invalid transitions, never past a
failed gate):

    INTAKE -> ANALYZING -> PLAN_READY -> AWAITING_G1_APPROVAL
    -> TEST_READY -> AWAITING_G2_APPROVAL -> BATCH_PRODUCTION
    -> EDITORIAL_REVIEW -> PICTURE_LOCK -> FINISHING -> FINAL_QC
    -> DELIVERED, with BLOCKED reachable from any state and a
    resume back to the state it came from.

Three transitions are operation-gated, not freely available:
ANALYZING -> PLAN_READY happens only inside
:func:`build_production_bundle`; AWAITING_G1_APPROVAL -> TEST_READY
and AWAITING_G2_APPROVAL -> BATCH_PRODUCTION happen only inside
:func:`evaluate_production_gate` when G1 / G2 passes. The one
exception is resuming from BLOCKED: it returns to the state the
job came from even when that state is operation-gated, because
the operation that put the job there already passed the gate.
Gate order is enforced: a gate cannot pass or be waived while an
earlier gate is unresolved. A waiver needs an explicit reason and
the user as authoriser, and is recorded, never silent.

Jobs are plain dicts, never persisted by this runtime, never
modified in place: every function works on a deep copy and returns
the updated job. ``job_hash`` is the SHA-256 of the canonical JSON
of the job without the job_hash field itself, recomputed on every
mutation (the S2P bundle-hash pattern). Durable persistence lives
in the companion module :mod:`runtime.production_store`, which
:func:`plan_script_to_production` uses when a store root is
given; this module itself never touches the filesystem.

Character-resolution coverage (R1 A2): an empty
``character_resolutions`` array is valid only when the source
genuinely has no visible character subjects. When the source has
speaking or visible identities, every distinct required identity
must be resolved exactly once — missing, duplicate and unknown
resolutions are all errors. A narrator / voice-over identity is
not a visible character: it is excluded when the analysis marks
it with a narrator role, or when it speaks but appears in no
scene and no shot. Cross-reference integrity (R1 A4):
``validate_analysis_bundle_references`` runs the scene / beat /
shot / sound-cue / character checks against the actual built
P1-003 bundle inside :func:`build_production_bundle`, and
:func:`plan_script_to_production` runs them once more
explicitly; unknown references are never silently ignored.
"""
from __future__ import annotations

import copy
import re

from . import identity_resolution
from . import local_session
from . import script_to_performance
from . import task_compiler
from .task_compiler import (
    canonical_json,
    compile_regeneration_packets,
    compile_task_package,
    schema_errors,
    sha256_hex,
)

ORCHESTRATOR_SCHEMA_VERSION = "2.5"

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")

STATES = (
    "INTAKE", "ANALYZING", "PLAN_READY", "AWAITING_G1_APPROVAL",
    "TEST_READY", "AWAITING_G2_APPROVAL", "BATCH_PRODUCTION",
    "EDITORIAL_REVIEW", "PICTURE_LOCK", "FINISHING", "FINAL_QC",
    "DELIVERED", "BLOCKED",
)

# Freely available transitions (target -> allowed sources). The three
# operation-gated targets (PLAN_READY, TEST_READY, BATCH_PRODUCTION)
# are deliberately absent: they happen only inside the operation
# that earns them.
ALLOWED_TRANSITIONS = {
    "ANALYZING": ("INTAKE",),
    "AWAITING_G1_APPROVAL": ("PLAN_READY",),
    "AWAITING_G2_APPROVAL": ("TEST_READY",),
    "EDITORIAL_REVIEW": ("BATCH_PRODUCTION",),
    "PICTURE_LOCK": ("EDITORIAL_REVIEW",),
    "FINISHING": ("PICTURE_LOCK",),
    "FINAL_QC": ("FINISHING",),
    "DELIVERED": ("FINAL_QC",),
    "BLOCKED": STATES,
}

# States from which provider tasks may be compiled.
COMPILE_STATES = (
    "PLAN_READY", "AWAITING_G1_APPROVAL", "TEST_READY",
    "AWAITING_G2_APPROVAL", "BATCH_PRODUCTION", "EDITORIAL_REVIEW",
    "PICTURE_LOCK", "FINISHING", "FINAL_QC",
)

# States in which a QC report may be filed and correction tasks built.
QC_STATES = (
    "BATCH_PRODUCTION", "EDITORIAL_REVIEW", "PICTURE_LOCK",
    "FINISHING", "FINAL_QC",
)

GATE_NAMES = {
    "G1": "Visual Planning",
    "G2": "Test Production",
    "G3": "Editorial Review",
    "G4": "Picture Lock",
    "G5": "Finishing",
    "G6": "Delivery",
}

GATE_ORDER = ("G1", "G2", "G3", "G4", "G5", "G6")

DELIVERY_PROFILES = (
    "short-form-15-60s", "short-explainer-1-3min", "story-5-15min",
    "documentary-20-60min", "long-form", "episodic",
)

PROVENANCE_VALUES = (
    "EXPLICIT_FROM_USER", "FROM_APPROVED_PROJECT_CANON",
    "INFERRED_FOR_PRODUCTION", "NEEDS_USER_DECISION",
)

# Which job state each gate guards. A gate may only be evaluated
# while the job is in (or past) its stage; evaluating G1 after
# delivery is a no-op error, not a silent pass.
GATE_STAGE = {
    "G1": ("PLAN_READY", "AWAITING_G1_APPROVAL", "TEST_READY",
           "AWAITING_G2_APPROVAL", "BATCH_PRODUCTION"),
    "G2": ("TEST_READY", "AWAITING_G2_APPROVAL", "BATCH_PRODUCTION"),
    "G3": ("BATCH_PRODUCTION", "EDITORIAL_REVIEW", "PICTURE_LOCK",
           "FINISHING", "FINAL_QC"),
    "G4": ("EDITORIAL_REVIEW", "PICTURE_LOCK", "FINISHING", "FINAL_QC"),
    "G5": ("PICTURE_LOCK", "FINISHING", "FINAL_QC"),
    "G6": ("FINISHING", "FINAL_QC"),
}


class ProductionOrchestratorError(ValueError):
    """Fail-closed error for the production orchestrator.

    Carries a list of human-readable reasons, like
    :class:`runtime.script_to_performance.ScriptToPerformanceError`.
    """

    def __init__(self, errors):
        if isinstance(errors, str):
            errors = [errors]
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


def _require_session(session) -> None:
    if not local_session.is_active_session(session):
        reasons = local_session.validate_session(session)
        raise ProductionOrchestratorError(
            "no active session for this production operation"
            + (f": {'; '.join(reasons)}" if reasons else ""))


def _require_bool(value, field: str) -> None:
    if type(value) is not bool:
        raise ProductionOrchestratorError(
            f"{field} must be an actual boolean, got "
            f"{type(value).__name__}")


def job_hash(job: dict) -> str:
    """Deterministic hash of a job (excluding job_hash)."""
    probe = {k: v for k, v in job.items() if k != "job_hash"}
    return sha256_hex(canonical_json(probe))


def validate_format_profile(profile) -> list[str]:
    """Format-profile errors (empty list = valid).

    Short-form and long-form share the same contracts and
    orchestration; only the profile differs. The user's aspect
    ratio, resolution, frame rate and platform stay authoritative
    and live in the production profile, not here.
    """
    errors: list[str] = []
    if not isinstance(profile, dict):
        return ["format_profile: expected an object, "
                f"got {type(profile).__name__}"]
    delivery = profile.get("delivery_profile")
    if delivery not in DELIVERY_PROFILES:
        errors.append("format_profile.delivery_profile "
                      f"{delivery!r} is not a known delivery profile")
    duration = profile.get("duration_target_seconds")
    if duration is not None:
        if type(duration) is not int or duration <= 0:
            errors.append("format_profile.duration_target_seconds "
                          "must be a positive integer")
    chapters = profile.get("chapters")
    if chapters is not None:
        if not isinstance(chapters, list):
            errors.append("format_profile.chapters: expected an array")
        else:
            seen: set[str] = set()
            for chapter in chapters:
                if not isinstance(chapter, dict):
                    errors.append("format_profile.chapters: every "
                                  "chapter must be an object")
                    continue
                chapter_id = chapter.get("chapter_id")
                if not isinstance(chapter_id, str) or not chapter_id:
                    errors.append("format_profile.chapters: every "
                                  "chapter needs a chapter_id")
                elif chapter_id in seen:
                    errors.append("format_profile.chapters: duplicate "
                                  f"chapter_id {chapter_id!r}")
                seen.add(chapter_id)
                if not isinstance(chapter.get("title"), str) \
                        or not chapter.get("title"):
                    errors.append("format_profile.chapters: every "
                                  "chapter needs a title")
    # R4-C: an explicit output geometry target (aspect ratio,
    # width/height, frame rate) is validated by the delivery
    # geometry rules; the lazy import keeps the orchestrator from
    # depending on the delivery module at import time.
    geometry = profile.get("output_geometry")
    if geometry is not None:
        from .timeline_delivery import validate_output_geometry
        errors.extend(validate_output_geometry(geometry))
    for key in profile:
        if key not in ("delivery_profile", "duration_target_seconds",
                       "chapters", "output_geometry"):
            errors.append(f"format_profile: unexpected field '{key}'")
    return errors


NARRATOR_ROLES = ("narrator", "voice-over")


def _narrator_refs(resolutions) -> set[str]:
    """Character refs the analysis marks as narrator / voice-over."""
    refs: set[str] = set()
    for resolution in resolutions or []:
        if isinstance(resolution, dict) \
                and resolution.get("role") in NARRATOR_ROLES:
            ref = resolution.get("character_ref")
            if isinstance(ref, str) and ref:
                refs.add(ref)
    return refs


def _required_character_refs(analysis, script=None) -> set[str]:
    """Visible character identities the analysis must resolve.

    Sources: speaking identities in the source script, visible
    identities in the script's shots, and characters the analysis
    itself declares in its scenes. A narrator / voice-over identity
    is never required as a visible character: it is excluded when
    the analysis marks it with a narrator role, or when it speaks
    but appears in no scene and no shot (a voice-over speaks from
    off-screen). The second rule is a documented heuristic with a
    known limit — a visible character a sloppy script leaves out
    of every shot list would also be treated as a voice-over — so
    the analysis's own scene declarations always win: any
    character declared in a scene is required.
    """
    speaking: set[str] = set()
    shot_visible: set[str] = set()
    if isinstance(script, dict):
        for line in script.get("dialogue") or []:
            if isinstance(line, dict) and line.get("character_id"):
                speaking.add(line["character_id"])
        for shot in script.get("shots") or []:
            if isinstance(shot, dict):
                for ref in shot.get("character_ids") or []:
                    if isinstance(ref, str) and ref:
                        shot_visible.add(ref)
    scene_refs: set[str] = set()
    resolutions = (analysis or {}).get("character_resolutions") or []
    for scene in (analysis or {}).get("scenes") or []:
        if isinstance(scene, dict):
            for ref in scene.get("character_refs") or []:
                if isinstance(ref, str) and ref:
                    scene_refs.add(ref)
    narrators = _narrator_refs(resolutions)
    visible = (speaking | shot_visible | scene_refs) - narrators
    # A speaking identity in no scene and no shot is a voice-over.
    for ref in speaking:
        if ref not in scene_refs and ref not in shot_visible \
                and ref not in narrators:
            visible.discard(ref)
    return visible


def validate_analysis_bundle_references(analysis, production_bundle) \
        -> list[str]:
    """Analysis-to-plan cross-reference errors (empty = valid).

    Runs against the actual built P1-003 bundle, not a standalone
    fixture: every referenced scene id must resolve to the validated
    Scene Plan, every beat id within its referenced scene, every
    shot-direction shot id to the validated Shot Plan with the
    scene agreeing, every sound cue's scene / shot / beat reference
    must resolve, and character resolutions must cover every
    identity the source and the approved plans require. Unknown
    references are errors, never silently ignored.
    """
    errors: list[str] = []
    if not isinstance(analysis, dict):
        return ["production_analysis: expected an object, "
                f"got {type(analysis).__name__}"]
    if not isinstance(production_bundle, dict):
        return ["production_bundle: expected an object, "
                f"got {type(production_bundle).__name__}"]
    s2p_bundle = production_bundle.get("s2p_bundle")
    if not isinstance(s2p_bundle, dict):
        return ["production_bundle: carries no s2p_bundle"]
    scene_plan = s2p_bundle.get("scene_plan") or {}
    shot_plan = s2p_bundle.get("shot_plan") or {}
    perf_plan = s2p_bundle.get("performance_plan") or {}
    plan_scenes: dict[str, dict] = {}
    for scene in scene_plan.get("scenes") or []:
        if isinstance(scene, dict) and scene.get("scene_id"):
            plan_scenes[scene["scene_id"]] = scene
    plan_shots: dict[str, dict] = {}
    for shot in shot_plan.get("shots") or []:
        if isinstance(shot, dict) and shot.get("shot_id"):
            plan_shots[shot["shot_id"]] = shot
    analysis_scenes: dict[str, dict] = {}
    for scene in analysis.get("scenes") or []:
        if isinstance(scene, dict) and scene.get("scene_id"):
            analysis_scenes[scene["scene_id"]] = scene
    for scene_id in analysis_scenes:
        if scene_id not in plan_scenes:
            errors.append("production_analysis.scenes: scene "
                          f"{scene_id!r} does not resolve to the "
                          "validated Scene Plan")
    for scene_id, scene in analysis_scenes.items():
        plan_scene = plan_scenes.get(scene_id)
        if plan_scene is None:
            continue
        plan_beats = {b.get("beat_id") for b in
                      plan_scene.get("beats") or []
                      if isinstance(b, dict)}
        for beat in scene.get("beats") or []:
            if isinstance(beat, dict) and beat.get("beat_id") \
                    and beat["beat_id"] not in plan_beats:
                errors.append("production_analysis.scenes: beat "
                              f"{beat['beat_id']!r} does not resolve "
                              f"within scene {scene_id!r} of the "
                              "validated Scene Plan")
    seen_shots: set[str] = set()
    for direction in analysis.get("shot_direction") or []:
        if not isinstance(direction, dict):
            continue
        shot_id = direction.get("shot_id")
        scene_id = direction.get("scene_id")
        if shot_id in seen_shots:
            errors.append("production_analysis.shot_direction: "
                          f"duplicate shot-direction entry for shot "
                          f"{shot_id!r}")
        seen_shots.add(shot_id)
        shot = plan_shots.get(shot_id)
        if shot is None:
            errors.append("production_analysis.shot_direction: shot "
                          f"{shot_id!r} does not resolve to the "
                          "validated Shot Plan")
        elif scene_id is not None \
                and shot.get("scene_id") != scene_id:
            errors.append("production_analysis.shot_direction: shot "
                          f"{shot_id!r} belongs to scene "
                          f"{shot.get('scene_id')!r} in the Shot Plan, "
                          f"not {scene_id!r}")
    for cue in analysis.get("sound_direction") or []:
        if not isinstance(cue, dict):
            continue
        cue_id = cue.get("cue_id") or cue.get("cue_type")
        scene_id = cue.get("scene_id")
        if scene_id is not None and scene_id not in plan_scenes:
            errors.append("production_analysis.sound_direction: cue "
                          f"{cue_id!r} references unknown scene "
                          f"{scene_id!r}")
        shot_id = cue.get("shot_id")
        if shot_id is not None:
            shot = plan_shots.get(shot_id)
            if shot is None:
                errors.append("production_analysis.sound_direction: "
                              f"cue {cue_id!r} references unknown shot "
                              f"{shot_id!r}")
            elif scene_id is not None \
                    and shot.get("scene_id") != scene_id:
                errors.append("production_analysis.sound_direction: "
                              f"cue {cue_id!r} references shot "
                              f"{shot_id!r} from scene "
                              f"{shot.get('scene_id')!r}, not "
                              f"{scene_id!r}")
        beat_id = cue.get("beat_id")
        if beat_id is not None and scene_id is not None:
            plan_scene = plan_scenes.get(scene_id)
            if plan_scene is not None:
                plan_beats = {b.get("beat_id") for b in
                              plan_scene.get("beats") or []
                              if isinstance(b, dict)}
                if beat_id not in plan_beats:
                    errors.append("production_analysis.sound_direction: "
                                  f"cue {cue_id!r} references unknown "
                                  f"beat {beat_id!r} in scene "
                                  f"{scene_id!r}")
    required = _required_character_refs_from_bundle(
        analysis, s2p_bundle)
    resolved: set[str] = set()
    for resolution in analysis.get("character_resolutions") or []:
        if isinstance(resolution, dict):
            # Any recorded resolution counts as covering the
            # identity here; a needs-decision entry is refused
            # earlier, at bundle build, never here.
            ref = resolution.get("character_ref")
            if isinstance(ref, str) and ref:
                resolved.add(ref)
    missing = sorted(required - resolved)
    if missing:
        errors.append("production_analysis.character_resolutions: "
                      "no resolution covers required identities "
                      + ", ".join(missing))
    return errors


def _required_character_refs_from_bundle(analysis, s2p_bundle) \
        -> set[str]:
    """Visible identities the bundle's plans require resolved.

    Union of performance-line characters, Scene Plan characters
    (character_ids + subjects) and Shot Plan characters, minus
    narrator / voice-over identities (marked by role in the
    analysis, or a non-character subject kind in the plans).
    """
    required: set[str] = set()
    non_characters: set[str] = set()
    scene_plan = s2p_bundle.get("scene_plan") or {}
    shot_plan = s2p_bundle.get("shot_plan") or {}
    perf_plan = s2p_bundle.get("performance_plan") or {}
    for scene in scene_plan.get("scenes") or []:
        if not isinstance(scene, dict):
            continue
        for ref in scene.get("character_ids") or []:
            if isinstance(ref, str) and ref:
                required.add(ref)
        for subject in scene.get("subjects") or []:
            if isinstance(subject, dict) \
                    and subject.get("character_id"):
                if subject.get("subject_kind") == "non-character":
                    non_characters.add(subject["character_id"])
                else:
                    required.add(subject["character_id"])
    for shot in shot_plan.get("shots") or []:
        if not isinstance(shot, dict):
            continue
        for ref in shot.get("character_ids") or []:
            if isinstance(ref, str) and ref:
                required.add(ref)
        for subject in shot.get("subjects") or []:
            if isinstance(subject, dict) \
                    and subject.get("character_id"):
                if subject.get("subject_kind") == "non-character":
                    non_characters.add(subject["character_id"])
                else:
                    required.add(subject["character_id"])
    for line in perf_plan.get("lines") or []:
        if not isinstance(line, dict):
            continue
        ref = line.get("character_id")
        if isinstance(ref, str) and ref:
            if line.get("subject_kind") == "non-character":
                non_characters.add(ref)
            else:
                required.add(ref)
    narrators = _narrator_refs(
        analysis.get("character_resolutions") or [])
    return (required - non_characters) - narrators


def validate_production_analysis(analysis, script=None) -> list[str]:
    """Analysis-contract errors (empty list = valid).

    Checks the schema, the provenance discipline (every open
    question is NEEDS_USER_DECISION, every decision carries a
    label), character-resolution completeness, scene/beat id
    uniqueness, and — when the source script is supplied — that
    the dialogue counts match the script exactly. A rewrite is
    never authorised here: that decision lives in
    :func:`build_production_bundle` and the S2P layer.
    """
    errors = schema_errors("production-analysis", analysis,
                           "production_analysis")
    if not isinstance(analysis, dict):
        return errors
    if analysis.get("schema_version") != ORCHESTRATOR_SCHEMA_VERSION:
        errors.append("production_analysis.schema_version must be "
                      f"'{ORCHESTRATOR_SCHEMA_VERSION}', got "
                      f"{analysis.get('schema_version')!r}")
    scene_ids: set[str] = set()
    for scene in analysis.get("scenes") or []:
        if not isinstance(scene, dict):
            continue
        scene_id = scene.get("scene_id")
        if scene_id in scene_ids:
            errors.append("production_analysis.scenes: duplicate "
                          f"scene_id {scene_id!r}")
        scene_ids.add(scene_id)
        beat_ids: set[str] = set()
        for beat in scene.get("beats") or []:
            if not isinstance(beat, dict):
                continue
            beat_id = beat.get("beat_id")
            if beat_id in beat_ids:
                errors.append("production_analysis.scenes: duplicate "
                              f"beat_id {beat_id!r} in scene "
                              f"{scene_id!r}")
            beat_ids.add(beat_id)
        if scene.get("provenance") not in PROVENANCE_VALUES:
            errors.append("production_analysis.scenes: scene "
                          f"{scene_id!r} has unknown provenance "
                          f"{scene.get('provenance')!r}")
    for resolution in analysis.get("character_resolutions") or []:
        if not isinstance(resolution, dict):
            continue
        mode = resolution.get("resolution")
        if mode == "approved" \
                and not resolution.get("registered_character_id"):
            errors.append("production_analysis.character_resolutions: "
                          f"character "
                          f"{resolution.get('character_ref')!r} is "
                          "approved but names no "
                          "registered_character_id")
        if mode == "task-local-proposal" \
                and not resolution.get("proposal_id"):
            errors.append("production_analysis.character_resolutions: "
                          f"character "
                          f"{resolution.get('character_ref')!r} is a "
                          "task-local proposal but names no proposal_id")
        if mode not in ("approved", "task-local-proposal",
                        "needs-decision"):
            errors.append("production_analysis.character_resolutions: "
                          f"character "
                          f"{resolution.get('character_ref')!r} has "
                          f"unknown resolution {mode!r}")
    seen_refs: set[str] = set()
    for resolution in analysis.get("character_resolutions") or []:
        if not isinstance(resolution, dict):
            continue
        ref = resolution.get("character_ref")
        if isinstance(ref, str) and ref:
            if ref in seen_refs:
                errors.append("production_analysis."
                              "character_resolutions: duplicate "
                              f"resolution for character {ref!r}; every "
                              "identity must be resolved exactly once")
            seen_refs.add(ref)
    if script is not None and isinstance(script, dict):
        # A2: every distinct required identity must be resolved
        # exactly once; missing, duplicate and unknown resolutions
        # are all errors. A needs-decision entry counts as a
        # resolution here (the identity is recorded, awaiting the
        # user) — the bundle build refuses undecided characters
        # later; the validator only checks the draft is complete.
        required = _required_character_refs(analysis, script)
        missing = sorted(required - seen_refs)
        if missing:
            errors.append("production_analysis.character_resolutions: "
                          "no resolution covers required identities "
                          + ", ".join(missing))
        known: set[str] = set()
        for line in script.get("dialogue") or []:
            if isinstance(line, dict) and line.get("character_id"):
                known.add(line["character_id"])
        for shot in script.get("shots") or []:
            if isinstance(shot, dict):
                for ref in shot.get("character_ids") or []:
                    if isinstance(ref, str) and ref:
                        known.add(ref)
        for scene in analysis.get("scenes") or []:
            if isinstance(scene, dict):
                for ref in scene.get("character_refs") or []:
                    if isinstance(ref, str) and ref:
                        known.add(ref)
        unknown = sorted(seen_refs - known)
        # F1: a resolution that declares cast_class
        # MENTIONED_ONLY is not an unknown-identity error — the
        # host explicitly records a character the story only
        # mentions, and the declaration claims no visibility, no
        # shot and no voice. The cast classifier independently
        # derives MENTIONED_ONLY for such a ref, and the snapshot
        # builder refuses any disagreement between the declared
        # class and the derived one, so a genuinely visible
        # character cannot hide behind the declaration.
        mentioned_only = {
            r.get("character_ref") for r in
            analysis.get("character_resolutions") or []
            if isinstance(r, dict)
            and r.get("cast_class") == "MENTIONED_ONLY"}
        unknown = [ref for ref in unknown
                   if ref not in mentioned_only]
        if unknown:
            errors.append("production_analysis.character_resolutions: "
                          "resolutions name unknown identities "
                          + ", ".join(unknown))
    # A4 (analysis level): shot-direction scene ids must resolve
    # to the analysis scenes, shot ids must not repeat, and sound
    # cue scene / beat references must resolve within the analysis.
    # Shot ids are checked against the Shot Plan in the bundle path
    # (the analysis carries no shot list of its own).
    analysis_scene_ids = {s.get("scene_id") for s in
                          analysis.get("scenes") or []
                          if isinstance(s, dict)}
    seen_direction_shots: set[str] = set()
    for direction in analysis.get("shot_direction") or []:
        if not isinstance(direction, dict):
            continue
        shot_id = direction.get("shot_id")
        if shot_id in seen_direction_shots:
            errors.append("production_analysis.shot_direction: "
                          f"duplicate shot-direction entry for shot "
                          f"{shot_id!r}")
        seen_direction_shots.add(shot_id)
        scene_id = direction.get("scene_id")
        if scene_id is not None \
                and scene_id not in analysis_scene_ids:
            errors.append("production_analysis.shot_direction: shot "
                          f"{shot_id!r} references unknown scene "
                          f"{scene_id!r}")
    for cue in analysis.get("sound_direction") or []:
        if not isinstance(cue, dict):
            continue
        cue_id = cue.get("cue_id") or cue.get("cue_type")
        scene_id = cue.get("scene_id")
        if scene_id is not None \
                and scene_id not in analysis_scene_ids:
            errors.append("production_analysis.sound_direction: cue "
                          f"{cue_id!r} references unknown scene "
                          f"{scene_id!r}")
        beat_id = cue.get("beat_id")
        if beat_id is not None and scene_id is not None:
            scene = next((s for s in analysis.get("scenes") or []
                          if isinstance(s, dict)
                          and s.get("scene_id") == scene_id), None)
            if scene is not None:
                beat_ids = {b.get("beat_id") for b in
                            scene.get("beats") or []
                            if isinstance(b, dict)}
                if beat_id not in beat_ids:
                    errors.append("production_analysis.sound_direction: "
                                  f"cue {cue_id!r} references unknown "
                                  f"beat {beat_id!r} in scene "
                                  f"{scene_id!r}")
    for question in analysis.get("open_questions") or []:
        if isinstance(question, dict) \
                and question.get("provenance") != "NEEDS_USER_DECISION":
            errors.append("production_analysis.open_questions: every "
                          "open question must carry provenance "
                          "NEEDS_USER_DECISION")
    if script is not None:
        if isinstance(script, dict):
            dialogue = script.get("dialogue")
            if isinstance(dialogue, list):
                preservation = analysis.get("dialogue_preservation") \
                    or {}
                if preservation.get("source_dialogue_line_count") \
                        != len(dialogue):
                    errors.append("production_analysis."
                                  "dialogue_preservation."
                                  "source_dialogue_line_count "
                                  f"{preservation.get('source_dialogue_line_count')!r} "
                                  "does not match the script's "
                                  f"{len(dialogue)} dialogue lines")
                if preservation.get("mapped_line_count") \
                        != len(dialogue):
                    errors.append("production_analysis."
                                  "dialogue_preservation."
                                  "mapped_line_count "
                                  f"{preservation.get('mapped_line_count')!r} "
                                  "does not match the script's "
                                  f"{len(dialogue)} dialogue lines")
    return errors


def validate_character_design_proposal(proposal) -> list[str]:
    """Proposal-contract errors (empty list = valid).

    A proposal is task-local by construction: this validator
    additionally refuses any proposal that claims a permanent
    registration already happened — proposals never register.
    """
    errors = schema_errors("character-design-proposal", proposal,
                           "character_design_proposal")
    if not isinstance(proposal, dict):
        return errors
    if proposal.get("schema_version") != ORCHESTRATOR_SCHEMA_VERSION:
        errors.append("character_design_proposal.schema_version must "
                      f"be '{ORCHESTRATOR_SCHEMA_VERSION}', got "
                      f"{proposal.get('schema_version')!r}")
    return errors


def validate_gate_state(gate_state) -> list[str]:
    """Gate-state errors (empty list = valid)."""
    errors = schema_errors("gate-state", gate_state, "gate_state")
    if not isinstance(gate_state, dict):
        return errors
    if gate_state.get("schema_version") != ORCHESTRATOR_SCHEMA_VERSION:
        errors.append("gate_state.schema_version must be "
                      f"'{ORCHESTRATOR_SCHEMA_VERSION}', got "
                      f"{gate_state.get('schema_version')!r}")
    gates = gate_state.get("gates") or []
    if [g.get("gate_id") for g in gates if isinstance(g, dict)] \
            != list(GATE_ORDER):
        errors.append("gate_state.gates must list exactly G1..G6 in "
                      "order, once each")
    for gate in gates:
        if not isinstance(gate, dict):
            continue
        if gate.get("status") == "WAIVED" \
                and not (isinstance(gate.get("waiver_reason"), str)
                         and gate["waiver_reason"].strip()):
            errors.append(f"gate_state: gate {gate.get('gate_id')} "
                          "is WAIVED without a waiver_reason")
        if gate.get("status") != "WAIVED" \
                and isinstance(gate.get("waiver_reason"), str) \
                and gate["waiver_reason"].strip():
            errors.append(f"gate_state: gate {gate.get('gate_id')} "
                          "carries a waiver_reason without being WAIVED")
        if gate.get("gate_name") != GATE_NAMES.get(gate.get("gate_id")):
            errors.append(f"gate_state: gate {gate.get('gate_id')} "
                          f"has wrong gate_name "
                          f"{gate.get('gate_name')!r}")
    return errors


def validate_job(job) -> list[str]:
    """Job-record errors (empty list = valid)."""
    errors: list[str] = []
    if not isinstance(job, dict):
        return ["job: expected an object, "
                f"got {type(job).__name__}"]
    if job.get("schema_version") != ORCHESTRATOR_SCHEMA_VERSION:
        errors.append("job.schema_version must be "
                      f"'{ORCHESTRATOR_SCHEMA_VERSION}', got "
                      f"{job.get('schema_version')!r}")
    if not isinstance(job.get("job_id"), str) \
            or not _ID_RE.match(job["job_id"]):
        errors.append(f"job.job_id {job.get('job_id')!r} is not a "
                      "valid id")
    if not isinstance(job.get("project_id"), str) \
            or not _ID_RE.match(job["project_id"]):
        errors.append(f"job.project_id {job.get('project_id')!r} is "
                      "not a valid id")
    if job.get("state") not in STATES:
        errors.append(f"job.state {job.get('state')!r} is not a known "
                      "state")
    # Identity policy + snapshot (CF-WO-P1-004-R1-ADDENDUM-
    # IDENTITY): validated structurally when present; the
    # snapshot hash is recomputed, never trusted blind.
    if job.get("identity_policy") is not None:
        errors.extend(identity_resolution.validate_identity_policy(
            job["identity_policy"]))
    if job.get("identity_snapshot") is not None:
        errors.extend(identity_resolution.validate_identity_snapshot(
            job["identity_snapshot"]))
    errors.extend(validate_format_profile(
        job.get("format_profile") or {}))
    errors.extend(validate_gate_state(job.get("gate_state") or {}))
    stored = job.get("job_hash")
    if isinstance(stored, str) and _SHA_RE.match(stored):
        if job_hash(job) != stored:
            errors.append("job.job_hash does not match the recomputed "
                          "job hash")
    return errors


def _fresh_gate_state(job_id: str, project_id: str) -> dict:
    return {
        "schema_version": ORCHESTRATOR_SCHEMA_VERSION,
        "job_id": job_id,
        "project_id": project_id,
        "gates": [
            {"gate_id": gate_id, "gate_name": GATE_NAMES[gate_id],
             "status": "NOT_STARTED"}
            for gate_id in GATE_ORDER
        ],
    }


def _with_hash(job: dict) -> dict:
    job["job_hash"] = job_hash(job)
    return job


__all__ = [
    "ProductionOrchestratorError",
    "STATES",
    "GATE_ORDER",
    "DELIVERY_PROFILES",
    "job_hash",
    "validate_format_profile",
    "validate_production_analysis",
    "validate_analysis_bundle_references",
    "validate_character_design_proposal",
    "validate_gate_state",
    "validate_job",
    "create_production_job",
    "transition_job",
    "resolve_character",
    "build_production_bundle",
    "compile_provider_tasks",
    "plan_script_to_production",
    "evaluate_production_gate",
    "record_execution_result",
    "build_qc_correction_tasks",
]


def create_production_job(session, job_id, project_id, format_profile,
                          *, commercial_use=False, stills_first=False,
                          script_contract_id=None,
                          identity_policy=None) -> dict:
    """Create a production job in state INTAKE.

    ``commercial_use`` marks monetised/commercial production: the
    task compiler will never match such a job to a provider whose
    commercial use is not approved. ``stills_first`` asks the
    compiler to build a starting still per shot before video tasks.
    Both flags must be actual booleans. ``identity_policy`` is an
    optional identity-selection policy record (see
    ``runtime.identity_resolution``): when supplied it is
    validated and stored on the job, and
    :func:`build_production_bundle` resolves it into an identity
    snapshot. The job starts with all six gates NOT_STARTED and no
    bundle, analysis or task package.
    """
    _require_session(session)
    _require_bool(commercial_use, "commercial_use")
    _require_bool(stills_first, "stills_first")
    if identity_policy is not None:
        policy_errors = identity_resolution.validate_identity_policy(
            identity_policy)
        if policy_errors:
            raise ProductionOrchestratorError(policy_errors)
    if not isinstance(job_id, str) or not _ID_RE.match(job_id):
        raise ProductionOrchestratorError(
            f"job_id {job_id!r} is not a valid id")
    if not isinstance(project_id, str) \
            or not _ID_RE.match(project_id):
        raise ProductionOrchestratorError(
            f"project_id {project_id!r} is not a valid id")
    errors = validate_format_profile(format_profile)
    if errors:
        raise ProductionOrchestratorError(errors)
    if script_contract_id is not None and (
            not isinstance(script_contract_id, str)
            or not _ID_RE.match(script_contract_id)):
        raise ProductionOrchestratorError(
            f"script_contract_id {script_contract_id!r} is not a "
            "valid id")
    job = {
        "schema_version": ORCHESTRATOR_SCHEMA_VERSION,
        "job_id": job_id,
        "project_id": project_id,
        "session_id": session.session_id,
        "format_profile": copy.deepcopy(format_profile),
        "commercial_use": commercial_use,
        "stills_first": stills_first,
        "script_contract_id": script_contract_id,
        "state": "INTAKE",
        "previous_state": None,
        "routing_plan_id": None,
        "s2p_bundle_id": None,
        "analysis_id": None,
        "analysis_hash": None,
        "gate_state": _fresh_gate_state(job_id, project_id),
        "identity_policy": copy.deepcopy(identity_policy)
        if identity_policy is not None else None,
        "identity_snapshot": None,
        "task_package": None,
        "execution_results": [],
        "qc_reports": [],
        "correction_round": 0,
    }
    errors = validate_job(job)
    if errors:
        raise ProductionOrchestratorError(errors)
    return _with_hash(job)


def transition_job(session, job, new_state) -> dict:
    """Move a job to a new state, enforcing the state machine.

    Raises ProductionOrchestratorError on any invalid transition.
    The three operation-gated targets (PLAN_READY, TEST_READY,
    BATCH_PRODUCTION) are never reachable here as forward
    transitions: PLAN_READY comes only from
    :func:`build_production_bundle`, TEST_READY and
    BATCH_PRODUCTION only from :func:`evaluate_production_gate`
    when G1 / G2 passes. Resuming from BLOCKED is the one
    exception — it returns to the state the job came from even
    when that state is operation-gated, because the operation
    that put the job there already passed the gate. Stage-gated
    transitions check their gate: PICTURE_LOCK needs G3 PASS (or
    WAIVED), FINISHING needs G4, FINAL_QC needs G5, DELIVERED
    needs G6. Resuming from BLOCKED returns to the state the job
    came from and is refused while any gate is still BLOCKED.
    """
    _require_session(session)
    if not isinstance(job, dict):
        raise ProductionOrchestratorError("job is not an object")
    if job.get("session_id") != session.session_id:
        raise ProductionOrchestratorError(
            "job belongs to a different session "
            f"({job.get('session_id')!r} != {session.session_id!r})")
    if new_state not in STATES:
        raise ProductionOrchestratorError(
            f"unknown target state {new_state!r}")
    current = job.get("state")
    if current == new_state:
        raise ProductionOrchestratorError(
            f"job is already in state {current}")
    if new_state == "BLOCKED":
        allowed = True
    elif current == "BLOCKED":
        if new_state != job.get("previous_state"):
            raise ProductionOrchestratorError(
                "a BLOCKED job can only resume to the state it came "
                f"from ({job.get('previous_state')!r}), not "
                f"{new_state!r}")
        gates = (job.get("gate_state") or {}).get("gates") or []
        blocked = [g.get("gate_id") for g in gates
                   if isinstance(g, dict)
                   and g.get("status") == "BLOCKED"]
        if blocked:
            raise ProductionOrchestratorError(
                "cannot resume from BLOCKED while gates are BLOCKED: "
                + ", ".join(blocked))
        allowed = True
    else:
        if new_state in ("PLAN_READY", "TEST_READY",
                         "BATCH_PRODUCTION"):
            raise ProductionOrchestratorError(
                f"state {new_state} is operation-gated and cannot be "
                "reached by a bare transition")
        allowed = current in ALLOWED_TRANSITIONS.get(new_state, ())
    if not allowed:
        raise ProductionOrchestratorError(
            f"invalid transition {current} -> {new_state}")
    gate_needed = {
        "PICTURE_LOCK": "G3",
        "FINISHING": "G4",
        "FINAL_QC": "G5",
        "DELIVERED": "G6",
    }.get(new_state)
    if gate_needed is not None:
        gates = {(g.get("gate_id")): g.get("status")
                 for g in (job.get("gate_state") or {}).get("gates")
                 or [] if isinstance(g, dict)}
        if gates.get(gate_needed) not in ("PASS", "WAIVED"):
            raise ProductionOrchestratorError(
                f"cannot enter {new_state}: gate {gate_needed} is "
                f"{gates.get(gate_needed)!r}, not PASS or WAIVED")
    job = copy.deepcopy(job)
    if new_state == "BLOCKED":
        job["previous_state"] = current
    elif current == "BLOCKED":
        job["previous_state"] = None
    job["state"] = new_state
    job = _with_hash(job)
    errors = validate_job(job)
    if errors:
        raise ProductionOrchestratorError(errors)
    return job


def resolve_character(session, job, resolution, *,
                      approved_registry=None, proposals=None) -> dict:
    """Resolve one character from an analysis resolution entry.

    Approved identities always win: an ``approved`` resolution
    binds the registered character id, and the registry must
    actually contain it. A ``task-local-proposal`` resolution binds
    the proposal id, and the proposal record must be supplied and
    must not be rejected. A ``needs-decision`` resolution fails
    closed — the user must decide before production can use this
    character. This function is pure: it never creates, edits or
    registers anything, and the supplied registry and proposals
    are returned untouched (callers may verify by hash).
    """
    _require_session(session)
    if not isinstance(job, dict):
        raise ProductionOrchestratorError("job is not an object")
    if not isinstance(resolution, dict):
        raise ProductionOrchestratorError("resolution is not an object")
    character_ref = resolution.get("character_ref")
    mode = resolution.get("resolution")
    if mode == "approved":
        character_id = resolution.get("registered_character_id")
        if not character_id:
            raise ProductionOrchestratorError(
                f"character {character_ref!r} is approved but names "
                "no registered_character_id")
        registry = approved_registry or {}
        if character_id not in registry:
            raise ProductionOrchestratorError(
                f"approved character {character_id!r} is not in the "
                "supplied approved registry")
        return {
            "character_ref": character_ref,
            "resolution": "approved",
            "character_id": character_id,
            "proposal_id": None,
            "role": resolution.get("role"),
            "provenance": resolution.get("provenance"),
        }
    if mode == "task-local-proposal":
        proposal_id = resolution.get("proposal_id")
        if not proposal_id:
            raise ProductionOrchestratorError(
                f"character {character_ref!r} is a task-local "
                "proposal but names no proposal_id")
        proposals = proposals or {}
        proposal = proposals.get(proposal_id)
        if proposal is None:
            raise ProductionOrchestratorError(
                f"task-local proposal {proposal_id!r} was not supplied")
        errors = validate_character_design_proposal(proposal)
        if errors:
            raise ProductionOrchestratorError(errors)
        if proposal.get("status") == "rejected":
            raise ProductionOrchestratorError(
                f"task-local proposal {proposal_id!r} is rejected")
        return {
            "character_ref": character_ref,
            "resolution": "task-local-proposal",
            "character_id": None,
            "proposal_id": proposal_id,
            "role": resolution.get("role"),
            "provenance": resolution.get("provenance"),
        }
    if mode == "needs-decision":
        raise ProductionOrchestratorError(
            f"character {character_ref!r} needs a user decision "
            "before it can be resolved")
    raise ProductionOrchestratorError(
        f"character {character_ref!r} has unknown resolution "
        f"{mode!r}")


def _build_identity_snapshot_for_bundle(
        session, job, policy, analysis, script, s2p_bundle,
        character_registry, voice_registry, proposals) -> dict:
    """Resolve one job's identity policy + cast + voices into a
    frozen identity snapshot (CF-WO-P1-004-R1-ADDENDUM-IDENTITY,
    Tasks B–E, I, N). Raises ProductionOrchestratorError on any
    unresolved identity, unapproved policy, ambiguous voice, or
    missing registry. Task-local speaking characters keep their
    bundle voice profiles (no registry voice exists for them);
    registered speaking characters must resolve — one profile
    per (character, language), since a character may speak
    Bengali in one line and English in another."""
    if not isinstance(character_registry, dict):
        raise ProductionOrchestratorError(
            "an identity policy needs an authorized character "
            "registry (character_registry must be an object)")
    # F1 Defect A step 3: an explicitly supplied registry never
    # sees more than the authorized overlay would have shown
    # this session — records under another owner or workspace
    # are invisible here, exactly as the loader excludes them
    # at load time.
    try:
        character_registry = identity_resolution \
            .scope_registry_to_session(
                character_registry, owner_id=session.owner_id,
                workspace_id=session.workspace_id)
        if isinstance(voice_registry, dict):
            voice_registry = identity_resolution \
                .scope_registry_to_session(
                    voice_registry, owner_id=session.owner_id,
                    workspace_id=session.workspace_id)
    except identity_resolution.IdentityResolutionError as exc:
        raise ProductionOrchestratorError(exc.errors) from exc
    # F1 Task D: NEW_ONLY hardening — no registered identity may
    # survive into a NEW_ONLY job, whatever the draft carries.
    if isinstance(policy, dict) and policy.get("mode") == "NEW_ONLY":
        new_only_errors = identity_resolution \
            .validate_new_only_inputs(
                analysis=analysis, bundle=s2p_bundle,
                character_registry=character_registry,
                voice_registry=voice_registry, proposals=proposals)
        if new_only_errors:
            raise ProductionOrchestratorError(new_only_errors)
    try:
        policy_resolution = identity_resolution \
            .resolve_project_identity_policy(
                policy, registry=character_registry)
    except identity_resolution.IdentityResolutionError as exc:
        raise ProductionOrchestratorError(exc.errors) from exc
    try:
        cast = identity_resolution.resolve_script_cast(
            script, analysis, bundle=s2p_bundle,
            policy_resolution=policy_resolution)
    except identity_resolution.IdentityResolutionError as exc:
        raise ProductionOrchestratorError(exc.errors) from exc
    # F1 Defect B: the declared cast class must agree with the
    # class derived from the script structure — a visible
    # character cannot hide behind a MENTIONED_ONLY declaration,
    # and a narrator cannot claim a visible binding.
    for resolution in analysis.get("character_resolutions") or []:
        if not isinstance(resolution, dict):
            continue
        declared = resolution.get("cast_class")
        ref = resolution.get("character_ref")
        if declared is None or ref is None:
            continue
        derived = cast["cast"].get(ref)
        if derived is not None and derived != declared:
            raise ProductionOrchestratorError(
                f"character {ref!r} declares cast class "
                f"{declared!r} but the script structure classifies "
                f"it as {derived!r}")
    # F1 Defect B: AUTO_MATCH_APPROVED completes the selection
    # from the script cast — unselected but needed characters
    # resolve by exact id or exact unique name.
    if policy_resolution.get("mode") == "AUTO_MATCH_APPROVED":
        try:
            additions = identity_resolution \
                .complete_auto_match_selection(
                    cast=cast["cast"],
                    policy_resolution=policy_resolution,
                    registry=character_registry, analysis=analysis)
        except identity_resolution.IdentityResolutionError as exc:
            raise ProductionOrchestratorError(exc.errors) from exc
        if additions:
            policy_resolution = copy.deepcopy(policy_resolution)
            policy_resolution["resolved"].update(additions)
    proposals_by_id: dict = {}
    if isinstance(proposals, dict):
        proposals_by_id = {k: v for k, v in proposals.items()
                           if isinstance(v, dict)}
    else:
        for record in proposals or []:
            if isinstance(record, dict) and record.get("proposal_id"):
                proposals_by_id[record["proposal_id"]] = record
    ref_to_id = {}
    for resolution in analysis.get("character_resolutions") or []:
        if isinstance(resolution, dict) \
                and resolution.get("character_ref") \
                and resolution.get("registered_character_id"):
            ref_to_id[resolution["character_ref"]] = resolution[
                "registered_character_id"]
    # The resolved selection also maps script refs to ids (the
    # auto-match path resolves names the analysis never named by
    # id). A ref the analysis and the resolution map to different
    # ids is a conflict, not a tie to break.
    for entry in policy_resolution.get("resolved", {}).values():
        if not isinstance(entry, dict):
            continue
        ref = (entry.get("resolution") or {}).get("character_ref")
        cid = entry.get("character_id")
        if ref and cid:
            if ref in ref_to_id and ref_to_id[ref] != cid:
                raise ProductionOrchestratorError(
                    f"character reference {ref!r} resolves to "
                    f"{ref_to_id[ref]!r} in the analysis but to "
                    f"{cid!r} in the identity policy — conflicting "
                    "identifiers")
            ref_to_id[ref] = cid
    resolved_ids = set(policy_resolution.get("resolved") or [])
    s2p = s2p_bundle.get("script_to_performance") or {}
    # Voice profile per dialogue line (the s2p bindings name one
    # per line): a character speaking two languages needs a
    # different profile per line, so the preference must come
    # from the line itself, never from another line's binding.
    voice_by_dialogue_line = {}
    all_bindings = list(s2p.get("character_voice_bindings") or [])
    if isinstance(s2p.get("character_voice_binding"), dict):
        all_bindings.append(s2p["character_voice_binding"])
    for binding in all_bindings:
        if isinstance(binding, dict) \
                and binding.get("dialogue_line_id") \
                and binding.get("voice_profile_id"):
            voice_by_dialogue_line[binding["dialogue_line_id"]] = \
                binding["voice_profile_id"]
    speakers: dict = {}
    perf_plan = s2p_bundle.get("performance_plan") or {}
    for line in perf_plan.get("lines") or []:
        if not isinstance(line, dict):
            continue
        if (line.get("speaking_state") or "speaking") == "listening":
            continue
        if not line.get("dialogue"):
            continue
        ref = line.get("character_id")
        character_id = ref_to_id.get(ref, ref)
        if character_id not in resolved_ids:
            continue  # task-local speaker: bundle voice stands
        language = line.get("language")
        key = (character_id, language)
        entry = speakers.setdefault(key, {
            "character_id": character_id,
            "language": language,
            "line_ids": [],
            "preferred": None,
            "role": None,
        })
        if line.get("line_id"):
            entry["line_ids"].append(line["line_id"])
        if entry["preferred"] is None:
            entry["preferred"] = line.get("voice_profile_id") \
                or voice_by_dialogue_line.get(
                    line.get("dialogue_line_id"))
        if cast["cast"].get(ref) == "NARRATOR_OR_VOICE_OVER":
            entry["role"] = "narration"
    voice_selections = []
    if speakers:
        if not isinstance(voice_registry, dict):
            raise ProductionOrchestratorError(
                "registered speaking characters need a voice "
                "registry (voice_registry must be an object)")
        for entry in sorted(speakers.values(),
                            key=lambda e: (e["character_id"],
                                           e["language"] or "")):
            voice, errors = identity_resolution \
                .resolve_character_voice(
                    character_id=entry["character_id"],
                    voice_registry=voice_registry,
                    character_registry=character_registry,
                    requesting_owner_id=session.owner_id,
                    requesting_workspace_id=session.workspace_id,
                    language=entry["language"],
                    role=entry["role"],
                    preferred_voice_profile_id=entry["preferred"],
                    commercial_use=job.get("commercial_use") is True)
            if errors:
                raise ProductionOrchestratorError(errors)
            voice_selections.append(
                identity_resolution.voice_selection_for_character(
                    character_id=entry["character_id"],
                    voice_record=voice,
                    dialogue_line_ids=entry["line_ids"],
                    language=entry["language"]))
    try:
        return identity_resolution.build_identity_snapshot(
            snapshot_id=f"snap-{job['job_id']}",
            job_id=job["job_id"],
            project_id=job["project_id"],
            policy_resolution=policy_resolution,
            voice_selections=voice_selections,
            task_local_proposals=proposals_by_id,
            cast_classes=cast["cast"],
            provenance=policy.get("provenance")
            or "EXPLICIT_FROM_USER")
    except identity_resolution.IdentityResolutionError as exc:
        raise ProductionOrchestratorError(exc.errors) from exc


def build_production_bundle(session, job, routing_plan, script, profile,
                            draft, analysis, bundle_id,
                            dialogue_rewrite_authorised=False,
                            identity_policy=None,
                            character_registry=None,
                            voice_registry=None,
                            proposals=None) -> tuple:
    """Validate the analysis, build the S2P bundle, bind the job.

    The job must be in ANALYZING. The analysis must validate
    against the source script, name no unresolved user decisions
    (empty open_questions, no needs-decision character), agree
    with the job on project and format profile, and agree with
    the caller on dialogue rewrite authorisation. The S2P bundle
    is built by the P1-003 runtime; its failures are reported as
    orchestrator errors. On success the job moves to PLAN_READY
    and the returned production bundle carries the analysis hash
    and the S2P bundle hash for traceability. Returns
    ``(production_bundle, updated_job)``.

    Identity (CF-WO-P1-004-R1-ADDENDUM-IDENTITY): when an
    identity policy is supplied here — or the job already
    carries one from :func:`create_production_job` — the policy
    is resolved against ``character_registry``, the script cast
    is classified, registered speaking characters get their
    voice profiles resolved against ``voice_registry``, and the
    frozen result is stored as ``job["identity_snapshot"]``.
    Task-local proposals come from ``proposals`` (a list of
    proposal records, or a mapping by proposal id). No policy:
    no snapshot, and the job compiles exactly as before.
    """
    _require_session(session)
    _require_bool(dialogue_rewrite_authorised,
                  "dialogue_rewrite_authorised")
    if not isinstance(job, dict):
        raise ProductionOrchestratorError("job is not an object")
    if job.get("session_id") != session.session_id:
        raise ProductionOrchestratorError(
            "job belongs to a different session")
    if job.get("state") != "ANALYZING":
        raise ProductionOrchestratorError(
            "production bundle can only be built while the job is "
            f"ANALYZING, not {job.get('state')!r}")
    if not isinstance(bundle_id, str) or not _ID_RE.match(bundle_id):
        raise ProductionOrchestratorError(
            f"bundle_id {bundle_id!r} is not a valid id")
    errors = validate_production_analysis(analysis, script)
    if errors:
        raise ProductionOrchestratorError(errors)
    if analysis.get("project_id") != job.get("project_id"):
        raise ProductionOrchestratorError(
            "analysis.project_id "
            f"{analysis.get('project_id')!r} does not match job "
            f"project {job.get('project_id')!r}")
    if isinstance(script, dict) \
            and analysis.get("script_contract_id") != script.get("id"):
        raise ProductionOrchestratorError(
            "analysis.script_contract_id "
            f"{analysis.get('script_contract_id')!r} does not match "
            f"script id {script.get('id')!r}")
    analysis_profile = analysis.get("format_profile")
    if isinstance(analysis_profile, dict):
        job_profile = job.get("format_profile") or {}
        if analysis_profile.get("delivery_profile") \
                != job_profile.get("delivery_profile"):
            raise ProductionOrchestratorError(
                "analysis format_profile delivery_profile "
                f"{analysis_profile.get('delivery_profile')!r} does "
                "not match the job's "
                f"{job_profile.get('delivery_profile')!r}")
    if analysis.get("open_questions"):
        raise ProductionOrchestratorError(
            "analysis has unresolved user decisions "
            f"({len(analysis['open_questions'])} open questions); "
            "resolve them before building the production bundle")
    undecided = [r.get("character_ref") for r in
                 analysis.get("character_resolutions") or []
                 if isinstance(r, dict)
                 and r.get("resolution") == "needs-decision"]
    if undecided:
        raise ProductionOrchestratorError(
            "characters need a user decision before the production "
            f"bundle can be built: {', '.join(undecided)}")
    preservation = analysis.get("dialogue_preservation") or {}
    if preservation.get("rewrite_requested") is not True \
            and dialogue_rewrite_authorised is True:
        raise ProductionOrchestratorError(
            "dialogue rewrite was authorised by the caller but the "
            "analysis does not request a rewrite")
    if preservation.get("rewrite_requested") is True \
            and dialogue_rewrite_authorised is not True:
        raise ProductionOrchestratorError(
            "the analysis requests a dialogue rewrite but the caller "
            "did not authorise one")
    try:
        s2p_bundle = script_to_performance \
            .build_script_to_performance_bundle(
                session, routing_plan, script, profile, draft,
                bundle_id, dialogue_rewrite_authorised)
    except script_to_performance.ScriptToPerformanceError as exc:
        raise ProductionOrchestratorError(
            ["script-to-performance build failed: " + err
             for err in exc.errors]) from exc
    production_bundle = {
        "schema_version": ORCHESTRATOR_SCHEMA_VERSION,
        "bundle_id": bundle_id,
        "job_id": job.get("job_id"),
        "project_id": job.get("project_id"),
        "session_id": session.session_id,
        "routing_plan_id": s2p_bundle.get("routing_plan_id"),
        "s2p_bundle_id": s2p_bundle.get("bundle_id"),
        "s2p_bundle": s2p_bundle,
        "analysis_id": analysis.get("id"),
        "analysis_hash": sha256_hex(canonical_json(analysis)),
        "format_profile": copy.deepcopy(job.get("format_profile")),
    }
    # A4: run the analysis-to-plan cross-reference checks against
    # the actual built bundle, not merely a standalone fixture.
    # Fail closed — no partial bundle and no state change.
    reference_errors = validate_analysis_bundle_references(
        analysis, production_bundle)
    if reference_errors:
        raise ProductionOrchestratorError(
            "production_analysis: analysis-to-plan references fail: "
            + "; ".join(reference_errors))
    production_bundle["bundle_hash"] = sha256_hex(canonical_json(
        {k: v for k, v in production_bundle.items()
         if k != "bundle_hash"}))
    # -- Identity snapshot (Tasks B–E, I, N): resolve the job's
    # identity policy into a frozen snapshot before the job
    # leaves ANALYZING. No policy: no snapshot.
    effective_policy = identity_policy \
        if identity_policy is not None \
        else job.get("identity_policy")
    identity_snapshot = None
    if effective_policy is not None:
        identity_snapshot = _build_identity_snapshot_for_bundle(
            session, job, effective_policy, analysis, script,
            s2p_bundle, character_registry, voice_registry,
            proposals)
    job = copy.deepcopy(job)
    job["state"] = "PLAN_READY"
    job["routing_plan_id"] = s2p_bundle.get("routing_plan_id")
    job["s2p_bundle_id"] = s2p_bundle.get("bundle_id")
    job["analysis_id"] = analysis.get("id")
    job["analysis_hash"] = production_bundle["analysis_hash"]
    if effective_policy is not None:
        job["identity_policy"] = copy.deepcopy(effective_policy)
    job["identity_snapshot"] = identity_snapshot
    job = _with_hash(job)
    errors = validate_job(job)
    if errors:
        raise ProductionOrchestratorError(errors)
    return production_bundle, job


def compile_provider_tasks(session, job, production_bundle, analysis=None,
                           proposals=None, providers=None, *,
                           voice_consent=False, voice_kinds=None,
                           providers_path=None, approved_props=None,
                           identity_snapshot=None) -> tuple:
    """Compile provider tasks for a production bundle.

    The job must be past planning (PLAN_READY or later, but not
    DELIVERED or BLOCKED). The production bundle must belong to
    this job. Delegates to the task compiler and stores the
    package on the job. Returns ``(task_package, updated_job)``.

    Identity (CF-WO-P1-004-R1-ADDENDUM-IDENTITY): the identity
    snapshot is the job's stored ``identity_snapshot`` unless
    one is supplied here; the compiler attaches its structured
    bindings to the image/video/voice packets.
    """
    _require_session(session)
    if not isinstance(job, dict):
        raise ProductionOrchestratorError("job is not an object")
    if job.get("session_id") != session.session_id:
        raise ProductionOrchestratorError(
            "job belongs to a different session")
    if job.get("state") not in COMPILE_STATES:
        raise ProductionOrchestratorError(
            "provider tasks can only be compiled once the job is "
            f"past planning, not in state {job.get('state')!r}")
    if not isinstance(production_bundle, dict):
        raise ProductionOrchestratorError(
            "production_bundle is not an object")
    if production_bundle.get("job_id") != job.get("job_id"):
        raise ProductionOrchestratorError(
            "production_bundle.job_id "
            f"{production_bundle.get('job_id')!r} does not match job "
            f"{job.get('job_id')!r}")
    s2p_bundle = production_bundle.get("s2p_bundle")
    if not isinstance(s2p_bundle, dict):
        raise ProductionOrchestratorError(
            "production bundle carries no s2p_bundle")
    # Proposals pass through as a list; the compiler normalizes
    # them by proposal_id itself (it also accepts a mapping, but
    # one canonical form is kept here).
    effective_snapshot = identity_snapshot \
        if identity_snapshot is not None \
        else job.get("identity_snapshot")
    try:
        package = compile_task_package(
            session, job, s2p_bundle, analysis, proposals, providers,
            voice_consent=voice_consent, voice_kinds=voice_kinds,
            providers_path=providers_path,
            approved_props=approved_props,
            identity_snapshot=effective_snapshot)
    except task_compiler.TaskCompilerError as exc:
        raise ProductionOrchestratorError(exc.errors) from exc
    job = copy.deepcopy(job)
    job["task_package"] = package
    job = _with_hash(job)
    errors = validate_job(job)
    if errors:
        raise ProductionOrchestratorError(errors)
    return package, job


def plan_script_to_production(session, job, script, profile, draft,
                              analysis, routing_plan, bundle_id,
                              proposals=None, approved_props=None,
                              providers=None, *,
                              voice_consent=False, voice_kinds=None,
                              dialogue_rewrite_authorised=False,
                              store_root=None, providers_path=None,
                              identity_policy=None,
                              character_registry=None,
                              voice_registry=None,
                              character_registry_root=None,
                              voice_registry_root=None) \
        -> dict:
    """One unified script-to-production planning entry point.

    Runs the whole planning pipeline for a job in ANALYZING, in
    order: validate the job and session, validate the analysis
    draft, build the P1-003 production bundle (which runs the
    analysis-to-plan cross-reference checks against the built
    bundle), validate the analysis-to-plan references once more
    explicitly (defence in depth), compile all task packets, and
    build the complete task package. When ``store_root`` is given,
    the planned job and a ``plan-<bundle_id>`` checkpoint are
    persisted through the production store; without it the result
    records ``persisted: False`` and nothing is written. Returns
    the production bundle, the updated job, the task package and
    the persistence information. No media is generated, no
    provider is executed, and no creative reasoning happens here:
    the AI reasoning host supplies the analysis draft and the
    proposals; this runtime only validates, binds and compiles.
    ``wf-generate-from-script`` is NOT promoted by this entry
    point — no timeline manifest is produced and no fake media
    path is invented.

    Identity (CF-WO-P1-004-R1-F1, Defect A): the identity
    parameters are all optional and compatible with the existing
    positional arguments. ``identity_policy`` is the approved
    identity-selection policy — an explicit parameter wins over
    a policy stored on the job. ``character_registry`` /
    ``voice_registry`` are explicitly supplied authorized
    registry mappings; ``character_registry_root`` /
    ``voice_registry_root`` are authorized private overlay roots
    the registries are loaded from. With no policy, behaviour is
    exactly the pre-F1 behaviour and no registry is accessed at
    all. With a policy, registries resolve in this order —
    explicit mapping, then root, then the authorized overlay
    environment variable — and the voice registry defaults to
    the character registry root; a loader failure fails the
    planning with ``ProductionOrchestratorError``. The resolved
    policy and registries are passed to
    :func:`build_production_bundle`, which freezes the identity
    snapshot on the job. With ``AUTO_MATCH_APPROVED`` the
    analysis is enriched first (name-only approved resolutions
    resolved by exact unique name) so it validates.
    """
    _require_session(session)
    _require_bool(dialogue_rewrite_authorised,
                  "dialogue_rewrite_authorised")
    if not isinstance(job, dict):
        raise ProductionOrchestratorError("job is not an object")
    if job.get("session_id") != session.session_id:
        raise ProductionOrchestratorError(
            "job belongs to a different session")
    if job.get("state") != "ANALYZING":
        raise ProductionOrchestratorError(
            "script-to-production planning can only start while the "
            f"job is ANALYZING, not {job.get('state')!r}")
    # F1 Defect A: the unified entry point is the single place
    # where an identity policy, its authorized registries and
    # the bundle meet. An explicit parameter wins over a policy
    # stored on the job; without any policy, nothing below
    # touches a registry.
    effective_policy = identity_policy \
        if identity_policy is not None \
        else job.get("identity_policy")
    resolved_character_registry = character_registry
    resolved_voice_registry = voice_registry
    if effective_policy is not None:
        if resolved_character_registry is None:
            try:
                resolved_character_registry = \
                    identity_resolution \
                    .load_authorized_character_registry(
                        character_registry_root,
                        owner_id=session.owner_id,
                        workspace_id=session.workspace_id)
            except identity_resolution.IdentityResolutionError \
                    as exc:
                raise ProductionOrchestratorError(
                    exc.errors) from exc
        if resolved_voice_registry is None:
            voice_root = voice_registry_root \
                if voice_registry_root is not None \
                else character_registry_root
            if voice_root is not None or \
                    identity_resolution.overlay_root_configured():
                try:
                    resolved_voice_registry = \
                        identity_resolution \
                        .load_authorized_voice_registry(
                            voice_root,
                            owner_id=session.owner_id,
                            workspace_id=session.workspace_id)
                except identity_resolution.IdentityResolutionError \
                        as exc:
                    raise ProductionOrchestratorError(
                        exc.errors) from exc
        # F1 Defect B: AUTO_MATCH_APPROVED resolves name-only
        # approved resolutions by exact unique name before the
        # analysis is validated (an approved resolution without
        # a registered id is otherwise a validation error).
        if isinstance(effective_policy, dict) \
                and effective_policy.get("mode") \
                == "AUTO_MATCH_APPROVED":
            try:
                analysis = identity_resolution \
                    .enrich_analysis_for_auto_match(
                        analysis,
                        registry=resolved_character_registry)
            except identity_resolution.IdentityResolutionError \
                    as exc:
                raise ProductionOrchestratorError(
                    exc.errors) from exc
    errors = validate_production_analysis(analysis, script)
    if errors:
        raise ProductionOrchestratorError(errors)
    production_bundle, job = build_production_bundle(
        session, job, routing_plan, script, profile, draft, analysis,
        bundle_id,
        dialogue_rewrite_authorised=dialogue_rewrite_authorised,
        identity_policy=effective_policy,
        character_registry=resolved_character_registry,
        voice_registry=resolved_voice_registry,
        proposals=proposals)
    reference_errors = validate_analysis_bundle_references(
        analysis, production_bundle)
    if reference_errors:
        raise ProductionOrchestratorError(
            "production_analysis: analysis-to-plan references fail: "
            + "; ".join(reference_errors))
    task_package, job = compile_provider_tasks(
        session, job, production_bundle, analysis=analysis,
        proposals=proposals, providers=providers,
        voice_consent=voice_consent, voice_kinds=voice_kinds,
        providers_path=providers_path, approved_props=approved_props)
    result = {
        "production_bundle": production_bundle,
        "job": job,
        "task_package": task_package,
        "identity_policy": effective_policy,
        "persisted": False,
        "job_path": None,
        "checkpoint_id": None,
        "checkpoint_path": None,
    }
    if store_root is not None:
        from .production_store import (  # lazy: the store imports
            save_production_checkpoint,  # the orchestrator lazily
            save_production_job)  # too; a top-level import would
        # be circular.
        job_path = save_production_job(session, store_root, job)
        checkpoint_id = f"plan-{bundle_id}"
        checkpoint_path = save_production_checkpoint(
            session, store_root, job, checkpoint_id=checkpoint_id)
        result["persisted"] = True
        result["job_path"] = job_path
        result["checkpoint_id"] = checkpoint_id
        result["checkpoint_path"] = checkpoint_path
    return result


def evaluate_production_gate(session, job, gate_id, decision, *,
                             note=None, waiver_reason=None,
                             authoriser=None) -> dict:
    """Evaluate one G1–G6 gate and, when it passes, advance the job.

    ``decision`` is IN_PROGRESS, PASS, BLOCKED or WAIVED. Gates
    are evaluated in order: G2 cannot pass or be waived while G1
    is unresolved, and so on. A WAIVED decision needs a non-empty
    waiver_reason and authoriser exactly ``"user"`` — only the
    user waives a gate. A BLOCKED decision moves the job to
    BLOCKED (remembering the state it came from). A PASS on G1
    while the job awaits G1 moves it to TEST_READY; a PASS on G2
    while it awaits G2 moves it to BATCH_PRODUCTION. Other gates
    record their result; the job advances past them through
    :func:`transition_job`, which checks them.
    """
    _require_session(session)
    if not isinstance(job, dict):
        raise ProductionOrchestratorError("job is not an object")
    if job.get("session_id") != session.session_id:
        raise ProductionOrchestratorError(
            "job belongs to a different session")
    if gate_id not in GATE_ORDER:
        raise ProductionOrchestratorError(
            f"unknown gate {gate_id!r}")
    if decision not in ("IN_PROGRESS", "PASS", "BLOCKED", "WAIVED"):
        raise ProductionOrchestratorError(
            f"unknown gate decision {decision!r}")
    if job.get("state") not in GATE_STAGE[gate_id] + ("BLOCKED",):
        raise ProductionOrchestratorError(
            f"gate {gate_id} cannot be evaluated while the job is in "
            f"state {job.get('state')!r}")
    if decision == "WAIVED":
        if not (isinstance(waiver_reason, str)
                and waiver_reason.strip()):
            raise ProductionOrchestratorError(
                f"gate {gate_id} cannot be WAIVED without a "
                "waiver_reason")
        if authoriser != "user":
            raise ProductionOrchestratorError(
                f"gate {gate_id} can only be waived by the user, not "
                f"by {authoriser!r}")
    if decision in ("PASS", "WAIVED"):
        index = GATE_ORDER.index(gate_id)
        gates = {(g.get("gate_id")): g.get("status")
                 for g in (job.get("gate_state") or {}).get("gates")
                 or [] if isinstance(g, dict)}
        for earlier in GATE_ORDER[:index]:
            if gates.get(earlier) not in ("PASS", "WAIVED"):
                raise ProductionOrchestratorError(
                    f"gate {gate_id} cannot be {decision} while gate "
                    f"{earlier} is {gates.get(earlier)!r}")
    job = copy.deepcopy(job)
    for gate in job["gate_state"]["gates"]:
        if gate.get("gate_id") != gate_id:
            continue
        gate["status"] = decision
        gate["decided_by"] = ("user" if decision == "WAIVED"
                              else f"session:{session.session_id}")
        if isinstance(note, str) and note:
            gate["decision_note"] = note
        if decision == "WAIVED":
            gate["waiver_reason"] = waiver_reason
        else:
            gate.pop("waiver_reason", None)
    if decision == "BLOCKED":
        job["previous_state"] = job["state"]
        job["state"] = "BLOCKED"
    elif decision in ("PASS", "WAIVED") and gate_id == "G1" \
            and job["state"] in ("AWAITING_G1_APPROVAL", "BLOCKED"):
        # Passing G1 after a block resumes the job past the gate
        # in one step: the wait is over, no second evaluation is
        # needed. (BLOCKED here means the job was awaiting G1.)
        if job["state"] == "BLOCKED":
            if job.get("previous_state") != "AWAITING_G1_APPROVAL":
                raise ProductionOrchestratorError(
                    "gate G1 decided while BLOCKED, but the job was "
                    "not awaiting G1; resume it explicitly first")
            job["previous_state"] = None
        job["state"] = "TEST_READY"
    elif decision in ("PASS", "WAIVED") and gate_id == "G2" \
            and job["state"] in ("AWAITING_G2_APPROVAL", "BLOCKED"):
        if job["state"] == "BLOCKED":
            if job.get("previous_state") != "AWAITING_G2_APPROVAL":
                raise ProductionOrchestratorError(
                    "gate G2 decided while BLOCKED, but the job was "
                    "not awaiting G2; resume it explicitly first")
            job["previous_state"] = None
        job["state"] = "BATCH_PRODUCTION"
    elif decision in ("PASS", "WAIVED") and job["state"] == "BLOCKED":
        # Any other gate passing while BLOCKED restores the state
        # the job came from; the job advances from there.
        blocked = [g.get("gate_id") for g in job["gate_state"]["gates"]
                   if isinstance(g, dict)
                   and g.get("status") == "BLOCKED"]
        if blocked:
            raise ProductionOrchestratorError(
                "cannot resume from BLOCKED while gates are BLOCKED: "
                + ", ".join(blocked))
        job["state"] = job.get("previous_state") or "INTAKE"
        job["previous_state"] = None
    job = _with_hash(job)
    errors = validate_job(job)
    if errors:
        raise ProductionOrchestratorError(errors)
    return job


def record_execution_result(session, job, task_id, result) -> dict:
    """Record an adapter's real execution result for one task.

    ``result`` is ``{provider_id?, outcome, output_ref?, notes?}``
    with outcome exactly ``succeeded``, ``failed`` or
    ``not-executed``. The task must exist in the job's compiled
    task package. A failed result does not auto-block the job:
    the QC loop decides what gets corrected. This function records
    facts; it never claims work happened that did not.
    """
    _require_session(session)
    if not isinstance(job, dict):
        raise ProductionOrchestratorError("job is not an object")
    if job.get("session_id") != session.session_id:
        raise ProductionOrchestratorError(
            "job belongs to a different session")
    package = job.get("task_package")
    if not isinstance(package, dict):
        raise ProductionOrchestratorError(
            "job has no compiled task package to record against")
    known = {p.get("task_id") for p in package.get("packets") or []
             if isinstance(p, dict)}
    if task_id not in known:
        raise ProductionOrchestratorError(
            f"task_id {task_id!r} is not in the job's task package")
    if not isinstance(result, dict):
        raise ProductionOrchestratorError("result is not an object")
    if result.get("outcome") not in ("succeeded", "failed",
                                     "not-executed"):
        raise ProductionOrchestratorError(
            f"result outcome {result.get('outcome')!r} is not one of "
            "succeeded, failed, not-executed")
    if result.get("provider_id") is not None \
            and not isinstance(result.get("provider_id"), str):
        raise ProductionOrchestratorError(
            "result provider_id must be a string when present")
    record = {
        "task_id": task_id,
        "provider_id": result.get("provider_id"),
        "outcome": result["outcome"],
    }
    if isinstance(result.get("output_ref"), str):
        record["output_ref"] = result["output_ref"]
    if isinstance(result.get("notes"), str):
        record["notes"] = result["notes"]
    job = copy.deepcopy(job)
    job["execution_results"].append(record)
    job = _with_hash(job)
    errors = validate_job(job)
    if errors:
        raise ProductionOrchestratorError(errors)
    return job


def build_qc_correction_tasks(session, job, qc_report, providers=None,
                              *, providers_path=None) -> tuple:
    """Build correction tasks for a QC report's failed shots.

    The job must be in a QC stage (batch production through final
    QC). The report must belong to this job and name real tasks or
    shots. Critical and Major defects always get correction
    packets; Minor only with repair authorisation; Polish never.
    Only the defective shots get packets — approved neighbours
    are preserved. Returns ``(correction_package, updated_job)``;
    the job records the report and advances its correction round.
    Correction packets reuse the original packets' identity
    bindings (same approved anchors); the snapshot is passed
    through from the job for integrity validation.
    """
    _require_session(session)
    if not isinstance(job, dict):
        raise ProductionOrchestratorError("job is not an object")
    if job.get("session_id") != session.session_id:
        raise ProductionOrchestratorError(
            "job belongs to a different session")
    if job.get("state") not in QC_STATES:
        raise ProductionOrchestratorError(
            "QC correction tasks can only be built in a QC stage "
            f"(one of {', '.join(QC_STATES)}), not in state "
            f"{job.get('state')!r}")
    if not isinstance(qc_report, dict):
        raise ProductionOrchestratorError("qc_report is not an object")
    if qc_report.get("job_id") != job.get("job_id"):
        raise ProductionOrchestratorError(
            "qc_report.job_id "
            f"{qc_report.get('job_id')!r} does not match job "
            f"{job.get('job_id')!r}")
    try:
        package = compile_regeneration_packets(
            session, job, qc_report, providers,
            providers_path=providers_path,
            identity_snapshot=job.get("identity_snapshot"))
    except task_compiler.TaskCompilerError as exc:
        raise ProductionOrchestratorError(exc.errors) from exc
    job = copy.deepcopy(job)
    job["qc_reports"].append(copy.deepcopy(qc_report))
    job["correction_round"] = int(job.get("correction_round") or 0) + 1
    job = _with_hash(job)
    errors = validate_job(job)
    if errors:
        raise ProductionOrchestratorError(errors)
    return package, job
