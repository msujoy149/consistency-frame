#!/usr/bin/env python3
"""P0-006 acceptance tests — production direction (Addendum C §14).

Run directly: python3 tests/test_production_direction.py
Exit 0 = PASS, 1 = FAIL.
Acceptance cases covered: AC-13..AC-20, plus QC-02 (voice-identity
QC) and QC-03 (audio-visual QC) from Addendum C §12.

Method: same as tests/test_character_registration.py — the acceptance
logic is tested by small in-test contract validators built on the FIXED
SCHEMA CONTRACTS (CF-WO-P0-006) and on the repo's own validator
(scripts/validate-repo.py validate_instance) wherever a schema exists.
The SCHEMA DEPENDENCY GATES in main() check that the real P0-006
schemas (v2.5, Agent C) exist and carry exactly the contract fields
and vocabularies; fixture-vs-schema validation runs only when the
gate for that schema passes, and is reported SKIP (blocked by the
gate) otherwise — never a pass against nothing.
"""
import copy
import importlib.util
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")

_spec = importlib.util.spec_from_file_location(
    "validate_repo", os.path.join(ROOT, "scripts", "validate-repo.py"))
_validate_repo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_validate_repo)
validate_instance = _validate_repo.validate_instance
check_schema = _validate_repo.check_schema

try:
    import yaml
except ImportError:
    yaml = None

failures = []
skipped = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def skip(name, reason):
    print(f"SKIP {name} — {reason}")
    skipped.append(name)


def load_json(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


def load_schema(name):
    path = os.path.join(ROOT, "schemas", name)
    if not os.path.exists(path):
        return None
    return load_json(os.path.join("schemas", name))


def load_fixture(name):
    return load_json(os.path.join("tests", "fixtures", name))


def errors_for(schema, value):
    errs = []
    validate_instance(schema, value, "$", errs)
    return errs


# --- Fixed vocabularies (CF-WO-P0-006; never a single animation_type) ---
VISUAL_STYLE = {"flat-2d-vector", "hand-drawn-2d", "illustrated-2d",
                "anime", "cartoon-2d", "stylized-3d", "semi-realistic-3d",
                "photorealistic-3d-cgi", "photorealistic-digital-human",
                "photorealistic-digital-animal-creature", "mixed",
                "captured-live-action"}
PRODUCTION_MEDIUM = {"2d-drawn-vector", "3d-cgi-rigged",
                     "ai-digital-human", "ai-digital-creature",
                     "live-action-footage", "hybrid-live-action-cgi"}
SOURCE_MEDIA = {"script-only", "reference-image", "reference-video",
                 "captured-footage", "generated-image", "generated-video",
                 "mixed"}
MOTION_METHOD = {"rig-2d-keyframe", "rig-3d-keyframe",
                 "ai-image-to-video", "ai-video-to-video",
                 "motion-capture", "performance-transfer",
                 "face-animation", "body-animation",
                 "pose-gesture-transfer", "lip-sync-phoneme-viseme",
                 "creature-articulation", "rotoscoping-compositing",
                 "captured-motion"}
SUBJECT_KIND = {"human", "digital-human", "real-animal", "cgi-animal",
                "fictional-creature", "anthropomorphic", "mixed",
                "non-character"}
INTERACTION_PATTERN = {"single-performance", "two-person-conversation",
                       "multi-person-conversation", "human-animal",
                       "human-creature", "multiple-animals-creatures",
                       "group-scene", "silent-reaction",
                       "physical-contact-object"}
ARTICULATION_TARGET = {"human-mouth-lips", "bird-beak", "animal-muzzle",
                       "creature-jaw-mandibles", "other"}
# Contract camera vocabulary (v2.5). The schema also keeps the legacy
# v2.4 values (dolly, crane, zoom, orbit, aerial-move) so existing
# records stay valid; the gate allows exactly contract + legacy.
CAMERA_MOVEMENT = {"static", "pan", "tilt", "tracking", "dolly-in",
                   "dolly-out", "push-in", "pull-back", "follow",
                   "handheld"}
CAMERA_MOVEMENT_LEGACY = {"dolly", "crane", "zoom", "orbit",
                          "aerial-move"}
DEPTH_OF_FIELD = {"shallow", "deep", "rack-focus"}
SPEAKING_STATE = {"speaking", "listening", "silent", "reacting"}
LISTENER_STATE = {"attentive", "reacting", "distracted", "absent"}
PRODUCTION_PROFILE_FIELDS = {
    "production_profile_id", "production_medium", "visual_style",
    "source_media_type", "motion_methods", "subject_types",
    "interaction_pattern", "skill_profiles", "per_subject_overrides",
    "per_shot_overrides", "schema_version"}
PERF_LINE_FIELDS = {"character_id", "dialogue_line_id",
                    "voice_profile_id", "reference_asset_ids",
                    "audio_asset_id", "speaking_state", "listener_state",
                    "articulation_target", "emotion", "delivery"}
SUBJECT_FIELDS = {"character_id", "representation", "source_media",
                  "rendering_style", "motion_method", "position",
                  "scale", "eyeline_target", "contact", "continuity"}
SHOT_CAMERA_FIELDS = {"angle", "shot_size", "framing", "lens_intent",
                      "camera_height", "camera_movement", "focus_target",
                      "depth_of_field", "lighting",
                      "transition_to_next_shot"}
BINDING_FIELDS = {"character_id", "reference_asset_ids",
                  "voice_profile_id", "dialogue_line_id",
                  "audio_asset_id", "speaking_state", "emotion",
                  "delivery", "articulation"}
ALLOWED_SCHEMA_VERSIONS = (["2.3"], ["2.4"], ["2.5"],
                           ["2.3", "2.5"], ["2.4", "2.5"])
SUCCESS_CLAIMS = {"success", "succeeded", "complete", "verified",
                  "done", "rendered"}


def schema_gate(name, contract_fields, required_fields=()):
    """One check per schema: exists, well-formed (repo's check_schema),
    carries the contract fields, sane schema_version. Returns the
    schema dict, or None when the gate fails."""
    schema = load_schema(name)
    check(f"SCHEMA-GATE: schemas/{name} exists", schema is not None,
          "schema file missing — Agent C dependency unmet")
    if schema is None:
        return None
    errs = []
    check_schema(schema, f"schemas/{name}", errs)
    check(f"SCHEMA-GATE: schemas/{name} is well-formed (repo subset)",
          not errs, "; ".join(errs))
    props = schema.get("properties", {})
    check(f"SCHEMA-GATE: schemas/{name} carries the contract fields",
          set(contract_fields) <= set(props),
          f"missing={sorted(set(contract_fields) - set(props))}")
    check(f"SCHEMA-GATE: schemas/{name} schema_version is 2.3/2.4/2.5",
          props.get("schema_version", {}).get("enum")
          in ALLOWED_SCHEMA_VERSIONS,
          f"enum={props.get('schema_version', {}).get('enum')}")
    if required_fields:
        check(f"SCHEMA-GATE: schemas/{name} requires "
              f"{sorted(required_fields)}",
              set(required_fields) <= set(schema.get("required", [])),
              f"required={schema.get('required')}")
    return schema


def validate_against_schema(schema, fixture_name, label):
    """validate_instance for one fixture; call only after its gate."""
    if schema is None:
        skip(label, "schema gate failed")
        return
    errs = errors_for(schema, load_fixture(fixture_name))
    check(label, not errs, "; ".join(errs))


def load_companion_registry():
    """(companion, capability, evidence_level) rows from the canonical
    companion capability registry."""
    if yaml is None:
        return None, "PyYAML not installed"
    with open(os.path.join(
            ROOT, "architecture",
            "COMPANION_CAPABILITY_REGISTRY.yaml"),
            encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    rows = []
    for comp in doc.get("companions", []):
        for group in ("capabilities", "interfaces"):
            for item in comp.get(group) or []:
                rows.append((comp.get("name"),
                             item.get("capability")
                             or item.get("name"),
                             item.get("evidence_level")))
    return rows, ""


# --- In-test contract validators (semantic / cross-record rules) -------
def articulation_fits_subject(kind, species, articulation):
    """Subject-specific articulation: never human lips on a bird,
    animal or creature. Returns an error string or ''."""
    if articulation == "other":
        return ""
    expected = None
    if kind in ("human", "digital-human"):
        expected = "human-mouth-lips"
    elif kind in ("real-animal", "cgi-animal"):
        if (species or "").lower() in ("parrot", "bird"):
            expected = "bird-beak"
        else:
            expected = "animal-muzzle"
    elif kind == "fictional-creature":
        expected = "creature-jaw-mandibles"
    if expected is not None and articulation != expected:
        return (f"articulation {articulation!r} does not fit "
                f"{kind}/{species} (expected {expected!r})")
    return ""


def validate_production_profile(pp):
    """Fixed production-profile contract (composable dimensions)."""
    errs = []
    if not isinstance(pp, dict):
        return ["production profile is not an object"]
    for field in PRODUCTION_PROFILE_FIELDS:
        if field not in pp:
            errs.append(f"missing field '{field}'")
    if pp.get("production_medium") not in PRODUCTION_MEDIUM:
        errs.append(f"production_medium {pp.get('production_medium')!r} "
                    "not in the fixed vocabulary")
    if pp.get("visual_style") not in VISUAL_STYLE:
        errs.append(f"visual_style {pp.get('visual_style')!r} not in "
                    "the fixed vocabulary")
    if pp.get("source_media_type") not in SOURCE_MEDIA:
        errs.append(f"source_media_type "
                    f"{pp.get('source_media_type')!r} not in the fixed "
                    "vocabulary")
    methods = pp.get("motion_methods")
    if not isinstance(methods, list) or not methods:
        errs.append("motion_methods must be a non-empty list")
    else:
        for m in methods:
            if m not in MOTION_METHOD:
                errs.append(f"motion_method {m!r} not in the fixed "
                            "vocabulary")
    subjects = pp.get("subject_types")
    if not isinstance(subjects, list) or not subjects:
        errs.append("subject_types must be a non-empty list")
    else:
        for s in subjects:
            if s not in SUBJECT_KIND:
                errs.append(f"subject_type {s!r} not in the fixed "
                            "vocabulary")
    if pp.get("interaction_pattern") not in INTERACTION_PATTERN:
        errs.append(f"interaction_pattern "
                    f"{pp.get('interaction_pattern')!r} not in the "
                    "fixed vocabulary")
    skills_dir = os.path.join(ROOT, "skills")
    for slug in pp.get("skill_profiles") or []:
        if not slug.startswith("skill-") or \
                slug[len("skill-"):] not in os.listdir(skills_dir):
            errs.append(f"skill_profiles entry {slug!r} is not a real "
                        "skill slug")
    for field in ("per_subject_overrides", "per_shot_overrides"):
        if not isinstance(pp.get(field), list):
            errs.append(f"{field} must be a list")
    if "animation_type" in pp:
        errs.append("a single animation_type enum is forbidden")
    return errs


def validate_subject(subj):
    """Per-subject scene/shot details (contract subjects array)."""
    errs = []
    if not isinstance(subj, dict):
        return ["subject is not an object"]
    for field in SUBJECT_FIELDS:
        if field not in subj or subj[field] in ("", None):
            errs.append(f"subject {subj.get('character_id')!r} missing "
                        f"'{field}'")
    if subj.get("representation") not in PRODUCTION_MEDIUM:
        errs.append(f"representation {subj.get('representation')!r} "
                    "not in the fixed vocabulary")
    if subj.get("source_media") not in SOURCE_MEDIA:
        errs.append(f"source_media {subj.get('source_media')!r} not in "
                    "the fixed vocabulary")
    if subj.get("rendering_style") not in VISUAL_STYLE:
        errs.append(f"rendering_style {subj.get('rendering_style')!r} "
                    "not in the fixed vocabulary")
    if subj.get("motion_method") not in MOTION_METHOD:
        errs.append(f"motion_method {subj.get('motion_method')!r} not "
                    "in the fixed vocabulary")
    if subj.get("subject_kind") not in SUBJECT_KIND:
        errs.append(f"subject_kind {subj.get('subject_kind')!r} not in "
                    "the fixed vocabulary")
    if subj.get("articulation_target") not in ARTICULATION_TARGET:
        errs.append(f"articulation_target "
                    f"{subj.get('articulation_target')!r} not in the "
                    "fixed vocabulary")
    else:
        fit = articulation_fits_subject(
            subj.get("subject_kind"), subj.get("species"),
            subj.get("articulation_target"))
        if fit:
            errs.append(f"subject {subj.get('character_id')!r}: {fit}")
    return [e for e in errs if e]


def validate_performance_line(line, voice_registry):
    """One performance-plan line: binding, articulation, sync fields."""
    errs = []
    if not isinstance(line, dict):
        return ["performance line is not an object"]
    for field in ("character_id", "dialogue_line_id", "voice_profile_id",
                  "reference_asset_ids", "speaking_state",
                  "articulation_target", "emotion", "delivery",
                  "lip_sync_required"):
        if field not in line:
            errs.append(f"line {line.get('line_id')!r} missing "
                        f"'{field}'")
    state = line.get("speaking_state")
    if state not in SPEAKING_STATE:
        errs.append(f"speaking_state {state!r} not in "
                    f"{sorted(SPEAKING_STATE)}")
    if line.get("articulation_target") not in ARTICULATION_TARGET:
        errs.append(f"articulation_target "
                    f"{line.get('articulation_target')!r} not in the "
                    "fixed vocabulary")
    else:
        fit = articulation_fits_subject(
            line.get("subject_kind"), line.get("species"),
            line.get("articulation_target"))
        if fit:
            errs.append(f"line {line.get('line_id')!r}: {fit}")
    vp = voice_registry.get(line.get("voice_profile_id"))
    if vp is None:
        errs.append(f"unknown voice_profile_id "
                    f"{line.get('voice_profile_id')!r}")
    elif vp.get("character_id") != line.get("character_id"):
        errs.append(f"voice_profile_id {line.get('voice_profile_id')!r} "
                    f"belongs to {vp.get('character_id')!r}, not "
                    f"{line.get('character_id')!r}")
    if not isinstance(line.get("lip_sync_required"), bool):
        errs.append(f"line {line.get('line_id')!r}: lip_sync_required "
                    "must be a boolean")
    dialogue = line.get("dialogue") or {}
    text = dialogue.get("text") if isinstance(dialogue, dict) else None
    if state == "speaking":
        if line.get("lip_sync_required") is not True:
            errs.append(f"line {line.get('line_id')!r}: a speaking line "
                        "needs lip_sync_required=true")
        if not text:
            errs.append(f"line {line.get('line_id')!r}: a speaking line "
                        "needs dialogue text")
        if not line.get("audio_asset_id"):
            errs.append(f"line {line.get('line_id')!r}: a speaking line "
                        "needs audio_asset_id")
    if state in ("listening", "silent") and not text:
        if not line.get("non_verbal_events"):
            errs.append(f"line {line.get('line_id')!r}: a non-speaking "
                        "line needs non_verbal_events")
        if line.get("listener_state") not in LISTENER_STATE:
            errs.append(f"line {line.get('line_id')!r}: listener_state "
                        f"{line.get('listener_state')!r} not in "
                        f"{sorted(LISTENER_STATE)}")
    return errs


def validate_shot(shot):
    """One shot: camera, framing and focus deliberately assigned."""
    errs = []
    if not isinstance(shot, dict):
        return ["shot is not an object"]
    for field in SHOT_CAMERA_FIELDS:
        if field not in shot or shot[field] in ("", None):
            errs.append(f"shot {shot.get('shot_id')!r} leaves "
                        f"'{field}' unset")
    if shot.get("camera_movement") not in CAMERA_MOVEMENT:
        errs.append(f"shot {shot.get('shot_id')!r}: camera_movement "
                    f"{shot.get('camera_movement')!r} not in the "
                    "contract vocabulary")
    if shot.get("depth_of_field") not in DEPTH_OF_FIELD:
        errs.append(f"shot {shot.get('shot_id')!r}: depth_of_field "
                    f"{shot.get('depth_of_field')!r} not in "
                    f"{sorted(DEPTH_OF_FIELD)}")
    for subj in shot.get("subjects") or []:
        errs.extend(validate_subject(subj))
    return errs


def validate_binding(binding, voice_registry):
    """One character-voice binding (script-to-performance)."""
    errs = []
    if not isinstance(binding, dict):
        return ["binding is not an object"]
    for field in BINDING_FIELDS:
        if field not in binding or binding[field] in ("", None):
            errs.append(f"binding {binding.get('dialogue_line_id')!r} "
                        f"missing '{field}'")
    if binding.get("speaking_state") not in SPEAKING_STATE:
        errs.append(f"speaking_state {binding.get('speaking_state')!r} "
                    "not in the fixed vocabulary")
    if binding.get("articulation") not in ARTICULATION_TARGET:
        errs.append(f"articulation {binding.get('articulation')!r} not "
                    "in the fixed vocabulary")
    vp = voice_registry.get(binding.get("voice_profile_id"))
    if vp is None:
        errs.append(f"unknown voice_profile_id "
                    f"{binding.get('voice_profile_id')!r}")
    elif vp.get("character_id") != binding.get("character_id"):
        errs.append(f"voice_profile_id {binding.get('voice_profile_id')!r} "
                    f"belongs to {vp.get('character_id')!r}, not "
                    f"{binding.get('character_id')!r}")
    return errs


def check_honest_limitation(plan, registry_rows):
    """AC-20 rule: a plan requesting a capability the companion
    registry marks untested/unsupported must carry an explicit
    limitation warning naming it, and must NOT claim success.
    Capabilities exercised_recorded_run / production_verified need
    no warning. Returns error strings."""
    errs = []
    if not isinstance(plan, dict):
        return ["plan is not an object"]
    if (plan.get("status_claim") or "").lower() in SUCCESS_CLAIMS:
        errs.append(f"plan claims {plan.get('status_claim')!r} while "
                    "requesting capabilities that are not verified — "
                    "false success")
    limits = {lim.get("capability"): lim
              for lim in plan.get("limitations") or []}
    for req in plan.get("requested_capabilities") or []:
        name = req.get("capability") or ""
        level = None
        for comp, cap, ev in registry_rows:
            if comp == req.get("companion") and cap and \
                    (name in cap or cap in name):
                level = ev
                break
        if level is None:
            errs.append(f"requested capability {name!r} is not in the "
                        "companion registry at all")
            continue
        if level in ("exercised_recorded_run", "production_verified"):
            continue
        lim = limits.get(name)
        if lim is None:
            errs.append(f"requested capability {name!r} is only "
                        f"{level} but the plan carries no limitation "
                        "warning for it")
        elif not (lim.get("warning") or "").strip():
            errs.append(f"limitation for {name!r} has no warning text")
        elif lim.get("evidence_level") != level:
            errs.append(f"limitation for {name!r} records "
                        f"evidence_level {lim.get('evidence_level')!r}, "
                        f"registry says {level!r}")
    return errs


def main():
    # --- SCHEMA DEPENDENCY GATES --------------------------------------
    prof_schema = schema_gate(
        "production-profile.json", PRODUCTION_PROFILE_FIELDS,
        required_fields=("production_profile_id", "production_medium",
                         "visual_style", "source_media_type",
                         "motion_methods", "subject_types",
                         "interaction_pattern"))
    if prof_schema is not None:
        props = prof_schema["properties"]
        for field, vocab in (
                ("visual_style", VISUAL_STYLE),
                ("production_medium", PRODUCTION_MEDIUM),
                ("source_media_type", SOURCE_MEDIA),
                ("interaction_pattern", INTERACTION_PATTERN)):
            check(f"SCHEMA-GATE: production-profile.json {field} enum "
                  "is exactly the fixed vocabulary",
                  set(props.get(field, {}).get("enum", [])) == vocab,
                  f"enum={props.get(field, {}).get('enum')}")
        check("SCHEMA-GATE: production-profile.json motion_methods "
              "enum is exactly the fixed vocabulary",
              set(props.get("motion_methods", {}).get("items", {}).get(
                  "enum", [])) == MOTION_METHOD)
        check("SCHEMA-GATE: production-profile.json subject_types "
              "enum is exactly the fixed vocabulary",
              set(props.get("subject_types", {}).get("items", {}).get(
                  "enum", [])) == SUBJECT_KIND)
        def _no_animation_type(node):
            if isinstance(node, dict):
                if "animation_type" in node:
                    return False
                return all(_no_animation_type(v)
                           for k, v in node.items()
                           if k != "description")
            if isinstance(node, list):
                return all(_no_animation_type(v) for v in node)
            return node != "animation_type"
        check("SCHEMA-GATE: production-profile.json defines no "
              "animation_type field or enum value (its description "
              "may name it only to forbid it)",
              _no_animation_type(props))
    perf_schema = schema_gate("performance-plan.json", set())
    if perf_schema is not None:
        line_props = perf_schema["properties"]["lines"]["items"][
            "properties"]
        check("SCHEMA-GATE: performance-plan.json lines carry the "
              "contract fields",
              PERF_LINE_FIELDS <= set(line_props),
              f"missing={sorted(PERF_LINE_FIELDS - set(line_props))}")
        check("SCHEMA-GATE: performance-plan.json speaking_state enum "
              "is exactly speaking/listening/silent/reacting",
              set(line_props.get("speaking_state", {}).get("enum", []))
              == SPEAKING_STATE)
        check("SCHEMA-GATE: performance-plan.json articulation_target "
              "enum is exactly the fixed vocabulary",
              set(line_props.get("articulation_target", {}).get(
                  "enum", [])) == ARTICULATION_TARGET)
    scene_schema = schema_gate("scene-plan.json", set())
    if scene_schema is not None:
        scene_props = scene_schema["properties"]["scenes"]["items"][
            "properties"]
        subj_props = set(scene_props.get("subjects", {}).get(
            "items", {}).get("properties", {}))
        check("SCHEMA-GATE: scene-plan.json scenes carry a subjects "
              "array with the contract fields",
              SUBJECT_FIELDS <= subj_props
              and {"articulation_target", "subject_kind", "species"}
              <= subj_props,
              f"subject fields={sorted(subj_props)}")
        check("SCHEMA-GATE: scene-plan.json subject articulation "
              "enum is exactly the fixed vocabulary",
              set(scene_props.get("subjects", {}).get("items", {}).get(
                  "properties", {}).get("articulation_target", {}).get(
                      "enum", [])) == ARTICULATION_TARGET)
    shot_schema = schema_gate("shot-plan.json", set())
    if shot_schema is not None:
        shot_props = shot_schema["properties"]["shots"]["items"][
            "properties"]
        check("SCHEMA-GATE: shot-plan.json shots carry the contract "
              "camera fields",
              SHOT_CAMERA_FIELDS <= set(shot_props),
              f"missing={sorted(SHOT_CAMERA_FIELDS - set(shot_props))}")
        cam_enum = set(shot_props.get("camera_movement", {}).get(
            "enum", []))
        check("SCHEMA-GATE: shot-plan.json camera_movement covers the "
              "contract vocabulary (legacy v2.4 values kept)",
              CAMERA_MOVEMENT <= cam_enum
              and cam_enum <= CAMERA_MOVEMENT | CAMERA_MOVEMENT_LEGACY,
              f"enum={sorted(cam_enum)}")
        check("SCHEMA-GATE: shot-plan.json depth_of_field enum is "
              "exactly shallow/deep/rack-focus",
              set(shot_props.get("depth_of_field", {}).get("enum", []))
              == DEPTH_OF_FIELD)
        subj_props = set(shot_props.get("subjects", {}).get(
            "items", {}).get("properties", {}))
        check("SCHEMA-GATE: shot-plan.json shots carry a subjects "
              "array with the contract fields",
              SUBJECT_FIELDS <= subj_props,
              f"subject fields={sorted(subj_props)}")
    s2p_schema = schema_gate("script-to-performance.json", set())
    if s2p_schema is not None:
        props = s2p_schema["properties"]
        check("SCHEMA-GATE: script-to-performance.json carries "
              "character_voice_binding + character_voice_bindings",
              "character_voice_binding" in props
              and "character_voice_bindings" in props)
        bind_props = set(props.get("character_voice_bindings", {}).get(
            "items", {}).get("properties", {}))
        check("SCHEMA-GATE: script-to-performance.json bindings carry "
              "the contract fields",
              BINDING_FIELDS <= bind_props,
              f"missing={sorted(BINDING_FIELDS - bind_props)}")
        bind_enums = props.get("character_voice_bindings", {}).get(
            "items", {}).get("properties", {})
        check("SCHEMA-GATE: script-to-performance.json binding "
              "articulation enum is exactly the fixed vocabulary",
              set(bind_enums.get("articulation", {}).get("enum", []))
              == ARTICULATION_TARGET)
        check("SCHEMA-GATE: script-to-performance.json binding "
              "speaking_state enum is exactly the fixed vocabulary",
              set(bind_enums.get("speaking_state", {}).get("enum", []))
              == SPEAKING_STATE)

    # Fixture-vs-schema validation (repo's validate_instance), only
    # where the gate passed.
    validate_against_schema(
        prof_schema, "production-profile-script-only.json",
        "valid fixture production-profile-script-only.json validates")
    validate_against_schema(
        prof_schema, "production-profile-reference-video.json",
        "valid fixture production-profile-reference-video.json "
        "validates")
    validate_against_schema(
        perf_schema, "performance-plan-human.json",
        "valid fixture performance-plan-human.json validates")
    validate_against_schema(
        perf_schema, "performance-plan-bird.json",
        "valid fixture performance-plan-bird.json validates")
    validate_against_schema(
        perf_schema, "performance-plan-two-person.json",
        "valid fixture performance-plan-two-person.json validates")
    validate_against_schema(
        scene_schema, "scene-plan-two-person.json",
        "valid fixture scene-plan-two-person.json validates")
    validate_against_schema(
        shot_schema, "shot-plan-directed.json",
        "valid fixture shot-plan-directed.json validates")
    validate_against_schema(
        s2p_schema, "script-to-performance-binding.json",
        "valid fixture script-to-performance-binding.json validates")
    # Regression: the pre-P0-006 fixtures still validate against the
    # additively extended schemas.
    validate_against_schema(
        perf_schema, "performance-plan-valid.json",
        "regression: performance-plan-valid.json still validates")
    validate_against_schema(
        scene_schema, "scene-plan-valid.json",
        "regression: scene-plan-valid.json still validates")
    validate_against_schema(
        shot_schema, "shot-plan-valid.json",
        "regression: shot-plan-valid.json still validates")
    validate_against_schema(
        s2p_schema, "script-to-performance-valid.json",
        "regression: script-to-performance-valid.json still validates")

    # No single animation_type enum anywhere in the new fixtures.
    for name in ("production-profile-script-only.json",
                 "production-profile-reference-video.json",
                 "performance-plan-human.json",
                 "performance-plan-bird.json",
                 "performance-plan-two-person.json",
                 "scene-plan-two-person.json",
                 "shot-plan-directed.json",
                 "script-to-performance-binding.json"):
        check(f"no animation_type in fixture {name}",
              "animation_type" not in json.dumps(load_fixture(name)))

    script_only = load_fixture("production-profile-script-only.json")
    ref_video = load_fixture(
        "production-profile-reference-video.json")
    human_plan = load_fixture("performance-plan-human.json")
    bird_plan = load_fixture("performance-plan-bird.json")
    two_person = load_fixture("performance-plan-two-person.json")
    scene = load_fixture("scene-plan-two-person.json")
    shots = load_fixture("shot-plan-directed.json")
    binding_doc = load_fixture("script-to-performance-binding.json")
    voice_registry = {
        load_fixture("voice-profile-user-recording.json")
        ["voice_profile_id"]:
        load_fixture("voice-profile-user-recording.json"),
        load_fixture("voice-profile-ai-generated.json")
        ["voice_profile_id"]:
        load_fixture("voice-profile-ai-generated.json")}

    # --- AC-13: script-only production, no reference video ------------
    errs = validate_production_profile(script_only)
    check("AC-13: script-only production profile validates (contract)",
          not errs, "; ".join(errs))
    text = json.dumps(script_only)
    check("AC-13: the plan claims no reference video was analysed",
          script_only["source_media_type"] == "script-only"
          and "reference_video" not in text
          and "reference-video" not in text
          and "analysed" not in text and "analyzed" not in text)

    # --- AC-14: supplied reference video, optional input --------------
    errs = validate_production_profile(ref_video)
    check("AC-14: reference-video production profile validates "
          "(contract)",
          not errs, "; ".join(errs))
    text = json.dumps(ref_video)
    check("AC-14: the reference video is recorded as optional input, "
          "never mandatory",
          ref_video["source_media_type"] == "reference-video"
          and "mandatory" not in text
          and "reference_video_required" not in text
          and "required\": true" not in text)

    # --- AC-15: human dialogue: lip-sync + gesture direction ----------
    human_line = human_plan["lines"][0]
    errs = validate_performance_line(human_line, voice_registry)
    check("AC-15: human performance line validates", not errs,
          "; ".join(errs))
    check("AC-15: human dialogue gets lip-sync + gesture direction",
          human_line["articulation_target"] == "human-mouth-lips"
          and human_line["lip_sync_required"] is True
          and len(human_line.get("gestures") or []) >= 1
          and "lip-sync-phoneme-viseme"
          in script_only["motion_methods"])

    # --- AC-16: speaking bird: beak + its own registered voice --------
    bird_line = bird_plan["lines"][0]
    errs = validate_performance_line(bird_line, voice_registry)
    check("AC-16: bird performance line validates", not errs,
          "; ".join(errs))
    check("AC-16: speaking bird gets beak articulation + its own "
          "registered voice",
          bird_line["articulation_target"] == "bird-beak"
          and bird_line["voice_profile_id"] == "voice-kiki-001"
          and voice_registry["voice-kiki-001"]["character_id"]
          == "char-002")
    bad_bird = copy.deepcopy(bird_line)
    bad_bird["articulation_target"] = "human-mouth-lips"
    check("AC-16: a bird with human-mouth-lips FAILS validation",
          bool(validate_performance_line(bad_bird, voice_registry)))
    bad_bird_voice = copy.deepcopy(bird_line)
    bad_bird_voice["voice_profile_id"] = "voice-mina-001"
    check("AC-16: a bird speaking with another character's voice "
          "FAILS validation",
          bool(validate_performance_line(bad_bird_voice,
                                         voice_registry)))

    # --- AC-17: multi-character conversation direction -----------------
    lines = two_person["lines"]
    errs = []
    for line in lines:
        errs.extend(validate_performance_line(line, voice_registry))
    check("AC-17: two-person performance plan validates", not errs,
          "; ".join(errs))
    by_line = {}
    for line in lines:
        by_line.setdefault(line["dialogue_line_id"], []).append(line)
    one_speaker = all(
        sum(1 for row in rows if row["speaking_state"] == "speaking")
        == 1 for rows in by_line.values())
    check("AC-17: no two characters speak simultaneously on one line",
          one_speaker)
    listeners = all(
        any(row.get("listener_state") == "attentive"
            for row in rows if row["speaking_state"] == "listening")
        for rows in by_line.values())
    check("AC-17: each line has a speaker and an attentive listener",
          listeners)
    speakers = {rows[0]["dialogue_line_id"]:
                [r["character_id"] for r in rows
                 if r["speaking_state"] == "speaking"][0]
                for rows in by_line.values()}
    check("AC-17: speakers alternate across the conversation",
          speakers == {"l-01": "char-001", "l-02": "char-002"},
          f"speakers={speakers}")
    scene_subjects = {s["character_id"]: s
                      for s in scene["scenes"][0]["subjects"]}
    check("AC-17: eyelines cross between the two characters",
          scene_subjects["char-001"]["eyeline_target"] == "char-002"
          and scene_subjects["char-002"]["eyeline_target"] == "char-001")
    check("AC-17: the conversation opens on a two-shot with camera "
          "direction",
          shots["shots"][0]["framing"] == "two-shot"
          and not validate_shot(shots["shots"][0]))

    # --- AC-18: camera movement, framing, focus deliberately assigned -
    shot_errs = []
    for shot in shots["shots"]:
        shot_errs.extend(validate_shot(shot))
    check("AC-18: every shot has explicit camera_movement + framing + "
          "focus_target",
          not shot_errs, "; ".join(shot_errs))
    missing_focus = copy.deepcopy(shots["shots"][0])
    del missing_focus["focus_target"]
    check("AC-18: a shot without focus_target FAILS validation",
          bool(validate_shot(missing_focus)))
    missing_move = copy.deepcopy(shots["shots"][0])
    del missing_move["camera_movement"]
    check("AC-18: a shot without camera_movement FAILS validation",
          bool(validate_shot(missing_move)))

    # --- AC-19: a static shot is allowed when it is the better choice --
    static_shot = [s for s in shots["shots"]
                   if s["camera_movement"] == "static"]
    check("AC-19: a static shot validates as a deliberate choice",
          len(static_shot) == 1
          and not validate_shot(static_shot[0])
          and static_shot[0]["shot_id"] == "sh-01")

    # --- AC-20: honest warnings for unsupported capabilities -----------
    registry_rows, reg_err = load_companion_registry()
    check("AC-20: companion capability registry is readable",
          registry_rows is not None, reg_err)
    if registry_rows is not None:
        paid = [(c, cap, ev) for c, cap, ev in registry_rows
                if cap and "Paid third-party provider routes" in cap]
        check("AC-20: the paid provider routes capability is "
              "present_locally (not exercised, not production-verified)",
              len(paid) == 1 and paid[0][2] == "present_locally",
              f"paid={paid}")
        check("AC-20: zero production_verified claims in the registry",
              not any(ev == "production_verified"
                      for _, _, ev in registry_rows))
        paid_name = paid[0][1] if paid else \
            "Paid third-party provider routes"
        good_plan = {
            "requested_capabilities": [
                {"companion": "OpenMontage",
                 "capability": paid_name}],
            "limitations": [
                {"capability": paid_name,
                 "evidence_level": "present_locally",
                 "warning": "Paid third-party provider routes are "
                            "documented only; no live paid call was made "
                            "in this account. Needs the user's explicit "
                            "approval and keys."}],
            "status_claim": "limited"}
        check("AC-20: a plan requesting an untested capability WITH "
              "an explicit limitation warning validates",
              not check_honest_limitation(good_plan, registry_rows),
              "; ".join(check_honest_limitation(good_plan,
                                                 registry_rows)))
        bad_plan = {
            "requested_capabilities": [
                {"companion": "OpenMontage",
                 "capability": paid_name}],
            "limitations": [],
            "status_claim": "success"}
        bad_errs = check_honest_limitation(bad_plan, registry_rows)
        check("AC-20: a plan claiming success with no limitation "
              "warning FAILS validation",
              len(bad_errs) >= 2, "; ".join(bad_errs))
        exercised_plan = {
            "requested_capabilities": [
                {"companion": "VoiceStudio",
                 "capability": "Text-to-speech generation (OmniVoice "
                                "engine)"}],
            "limitations": [],
            "status_claim": "limited"}
        check("AC-20: a plan requesting an exercised capability needs "
              "no limitation warning",
              not check_honest_limitation(exercised_plan, registry_rows))

    # --- QC-02: voice-identity QC (Addendum C §12) ----------------------
    check("QC-02: a binding to a wrong (unknown) Voice Profile ID is "
          "rejected",
          bool(validate_binding(
              {"character_id": "char-001",
               "reference_asset_ids": ["ref-mina-front"],
               "voice_profile_id": "voice-nope-001",
               "dialogue_line_id": "l-01",
               "audio_asset_id": "audio-mina-ref",
               "speaking_state": "speaking", "emotion": "determination",
               "delivery": "warm, steady",
               "articulation": "human-mouth-lips"}, voice_registry)))
    check("QC-02: cross-character voice leakage in a binding is "
          "rejected",
          bool(validate_binding(
              {"character_id": "char-002",
               "reference_asset_ids": ["ref-kiki-front"],
               "voice_profile_id": "voice-mina-001",
               "dialogue_line_id": "l-02",
               "audio_asset_id": "audio-kiki-ref",
               "speaking_state": "speaking", "emotion": "excitement",
               "delivery": "bright, brisk",
               "articulation": "bird-beak"}, voice_registry)))
    bind_errs = []
    for b in binding_doc["character_voice_bindings"]:
        bind_errs.extend(validate_binding(b, voice_registry))
    bind_errs.extend(validate_binding(
        binding_doc["character_voice_binding"], voice_registry))
    check("QC-02: the fixture's own character-voice bindings validate",
          not bind_errs, "; ".join(bind_errs))

    # --- QC-03: audio-visual QC (Addendum C §12) ------------------------
    av_errs = []
    for plan_name, plan in (("human", human_plan),
                            ("bird", bird_plan),
                            ("two-person", two_person)):
        for line in plan["lines"]:
            for field in ("dialogue_line_id", "audio_asset_id",
                          "articulation_target", "lip_sync_required"):
                if line.get("speaking_state") == "speaking" \
                        and field not in line:
                    av_errs.append(f"{plan_name} line "
                                   f"{line.get('line_id')!r} missing "
                                   f"sync field '{field}'")
            if line.get("speaking_state") == "speaking":
                if not line.get("audio_asset_id"):
                    av_errs.append(f"{plan_name} line "
                                   f"{line.get('line_id')!r} has no "
                                   "audio_asset_id")
    check("QC-03: dialogue/articulation sync fields are present on "
          "every speaking line",
          not av_errs, "; ".join(av_errs))
    perf_by_key = {}
    for line in two_person["lines"]:
        if line["speaking_state"] == "speaking":
            perf_by_key[(line["character_id"],
                         line["dialogue_line_id"])] = line
    mapping_errs = []
    for b in binding_doc["character_voice_bindings"]:
        key = (b["character_id"], b["dialogue_line_id"])
        line = perf_by_key.get(key)
        if line is None:
            mapping_errs.append(f"binding {key} has no performance "
                                "line")
            continue
        if line["voice_profile_id"] != b["voice_profile_id"]:
            mapping_errs.append(
                f"binding {key} voice {b['voice_profile_id']!r} != "
                f"performance line voice "
                f"{line['voice_profile_id']!r}")
        if line.get("audio_asset_id") != b["audio_asset_id"]:
            mapping_errs.append(
                f"binding {key} audio {b['audio_asset_id']!r} != "
                f"performance line audio "
                f"{line.get('audio_asset_id')!r}")
    check("QC-03: character-to-voice mapping is consistent between "
          "the performance plan and the script-to-performance bindings",
          not mapping_errs, "; ".join(mapping_errs))

    print(f"test_production_direction: "
          f"{'PASS' if not failures else 'FAIL'} "
          f"({len(failures)} failure(s), {len(skipped)} skipped)")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
