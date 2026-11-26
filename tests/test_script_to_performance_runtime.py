#!/usr/bin/env python3
"""Script-to-Performance runtime tests (CF-WO-P1-003).

Covers: session and routing binding; script validation; plan
validation; verbatim dialogue preservation and rewrite
authorisation; cross-plan integrity; determinism and output
integrity; and the optional-field nullability parity matrix over
the six schemas this runtime consumes (script-contract,
script-to-performance, scene-plan, shot-plan, performance-plan,
production-profile). For every optional property path in those
schemas the matrix checks the baseline with the field present,
the baseline with the field omitted, and explicit null rejected
whenever the schema disallows null; a coverage assertion compares
the exercised paths against the optional paths discovered from
the schemas themselves, so a future optional schema field without
a matching runtime/nullability regression test fails the suite.

Conventions follow tests/test_skill_router.py: check(name, cond,
detail="") prints PASS/FAIL lines, failures are collected, and
the process exits 0 only when every check passes. No test here
weakens any P0 or P1 check.
"""

import copy
import importlib.util
import json
import os
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(__file__), "..")
ROOT_ABS = os.path.abspath(ROOT)
sys.path.insert(0, ROOT)
from runtime import local_session  # noqa: E402
from runtime.local_session import (  # noqa: E402
    close_session, is_active_session, load_or_create_profile,
    start_session)
from runtime.skill_router import (  # noqa: E402
    build_workflow_plan, load_routing_catalog, validate_routing_plan)
from runtime.script_to_performance import (  # noqa: E402
    ScriptToPerformanceError, build_script_to_performance_bundle,
    script_to_performance_hash, validate_performance_plan,
    validate_production_profile, validate_scene_plan,
    validate_script_contract, validate_script_plan_drafts,
    validate_script_to_performance_bundle, validate_shot_plan)

_spec = importlib.util.spec_from_file_location(
    "validate_repo", os.path.join(ROOT, "scripts", "validate-repo.py"))
_validate_repo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_validate_repo)
validate_instance = _validate_repo.validate_instance

failures = []
_sessions = []


def check(name, cond, detail=""):
    if cond:
        print(f"PASS {name}")
    else:
        print(f"FAIL {name} {detail}")
        failures.append(name)


def clone(value):
    return json.loads(json.dumps(value))


# ---------------------------------------------------------------------------
# Sessions and routing plans
# ---------------------------------------------------------------------------

def fresh_session():
    root = tempfile.mkdtemp(prefix="cf-p1-003-test-")
    profile = load_or_create_profile(root)
    session = start_session(profile, profile.workspace_id)
    _sessions.append(session)
    return session


def fresh_routing_plan(session, intent_mode="GENERATE_FROM_SCRIPT"):
    s3 = json.load(open(os.path.join(
        ROOT, "tests", "fixtures",
        "production-profile-valid-digital-human.json")))
    req = {"schema_version": "2.4",
           "task_id": "s2p-routing-001",
           "intent_mode": intent_mode,
           "production_profile": s3,
           "hints": {"dialogue": True, "languages": ["en"],
                     "recurring_character": True, "consent": True}}
    return build_workflow_plan(session, req, load_routing_catalog())


# ---------------------------------------------------------------------------
# Baseline fixtures
# ---------------------------------------------------------------------------

SUBJECT_HUMAN = {
    "character_id": "char-001", "subject_kind": "digital-human",
    "representation": "ai-digital-human", "source_media": "reference-image",
    "rendering_style": "photorealistic-digital-human",
    "articulation_target": "human-mouth-lips", "species": "human",
    "motion_method": "face-animation", "is_live_action_footage": False,
    "position": "foreground-left", "scale": "life-size",
    "contact": "none", "continuity": "same dress as the previous scene",
    "eyeline_target": "char-kiki-001",
}
SUBJECT_BIRD = {
    "character_id": "char-kiki-001", "subject_kind": "cgi-animal",
    "representation": "3d-cgi-rigged", "source_media": "reference-image",
    "rendering_style": "stylized-3d",
    "articulation_target": "bird-beak", "species": "African grey parrot",
    "motion_method": "creature-articulation",
    "is_live_action_footage": False,
    "position": "foreground-right, perched on branch",
    "scale": "life-size", "contact": "feet gripping the branch",
    "continuity": "same branch, same perch position",
    "eyeline_target": "char-001",
}


def script():
    return {
        "schema_version": "2.3", "id": "script-test-001",
        "project_id": "proj-test-001",
        "dialogue_mode": "VERBATIM_SCRIPT",
        "version": 1,
        "dialogue": [
            {"line_id": "l-01", "character_id": "char-001",
             "text": "I will help. Let us go together.", "language": "en"},
            {"line_id": "l-02", "character_id": "char-kiki-001",
             "text": "Hello, Mira! I heard you coming.", "language": "en"},
        ],
        "beats": ["b-01", "b-02"],
        "shots": [
            {"shot_id": "sh-01", "duration_seconds": 4.5,
             "framing": "medium-close-up", "camera": "eye-level",
             "character_ids": ["char-001"]},
            {"shot_id": "sh-02", "duration_seconds": 3.0,
             "framing": "medium", "camera": "low",
             "character_ids": ["char-001", "char-kiki-001"]},
        ],
        "performance_cues": ["steady breath before the decision"],
        "audio_plan": "morning birds, distant river",
    }


def profile():
    return {
        "schema_version": "2.5", "production_profile_id": "prod-test-001",
        "name": "Test digital-human and bird performance",
        "project_id": "proj-test-001",
        "production_medium": "ai-digital-human",
        "visual_style": "photorealistic-digital-human",
        "source_media_type": "reference-image",
        "motion_methods": ["ai-image-to-video", "face-animation",
                           "lip-sync-phoneme-viseme", "body-animation",
                           "creature-articulation"],
        "subject_types": ["digital-human", "cgi-animal"],
        "interaction_pattern": "human-animal",
        "is_live_action_footage": False,
        "version": 1, "status": "approved",
        "skill_profiles": ["skill-realistic-person",
                           "skill-voice-consistency"],
        "per_subject_overrides": [
            {"character_id": "char-001", "subject_kind": "digital-human",
             "representation": "ai-digital-human",
             "source_media": "reference-image",
             "rendering_style": "photorealistic-digital-human",
             "articulation_target": "human-mouth-lips", "species": "human",
             "motion_methods": ["face-animation",
                                "lip-sync-phoneme-viseme", "body-animation"],
             "is_live_action_footage": False},
            {"character_id": "char-kiki-001", "subject_kind": "cgi-animal",
             "representation": "3d-cgi-rigged",
             "source_media": "reference-image",
             "rendering_style": "stylized-3d",
             "articulation_target": "bird-beak",
             "species": "African grey parrot",
             "motion_methods": ["creature-articulation", "body-animation"],
             "is_live_action_footage": False},
        ],
        "per_shot_overrides": [
            {"shot_id": "sh-01", "camera_movement": "static",
             "depth_of_field": "shallow", "focus_target": "char-001",
             "lighting": "soft morning light",
             "transition_to_next_shot": "cut"},
            {"shot_id": "sh-02", "camera_movement": "push-in",
             "depth_of_field": "deep", "focus_target": "char-kiki-001",
             "lighting": "same soft morning light",
             "transition_to_next_shot": "cut"},
        ],
    }


def scene_plan():
    return {
        "schema_version": "2.4", "id": "scene-plan-test-001",
        "project_id": "proj-test-001",
        "scenes": [{
            "scene_id": "sc-01", "title": "The test scene",
            "dramatic_intent": "The protagonist decides to help, turning "
                               "curiosity into courage.",
            "location_id": "loc-test-001",
            "character_ids": ["char-001", "char-kiki-001"],
            "visual_style_profile_id": "style-test-001",
            "subjects": [clone(SUBJECT_HUMAN), clone(SUBJECT_BIRD)],
            "beats": [
                {"beat_id": "b-01",
                 "description": "She hears the call and hesitates.",
                 "dramatic_intent": "Show doubt before the decision.",
                 "primary_emotion": "fear",
                 "secondary_emotion": "anticipation",
                 "emotion_intensity": 5,
                 "emotion_transition": "worry -> determination across "
                                       "the beat",
                 "nuanced_emotion": "worry",
                 "non_verbal_events": [{"type": "silence",
                                        "duration_seconds": 1.5,
                                        "intensity": 4}]},
                {"beat_id": "b-02",
                 "description": "She steps forward and agrees.",
                 "dramatic_intent": "The decision lands.",
                 "primary_emotion": "trust",
                 "secondary_emotion": "anticipation",
                 "emotion_intensity": 8,
                 "emotion_transition": "determination holds into the "
                                       "next scene",
                 "nuanced_emotion": "determination"},
            ],
        }],
    }


def shot_plan():
    return {
        "schema_version": "2.4", "id": "shot-plan-test-001",
        "project_id": "proj-test-001",
        "scene_plan_id": "scene-plan-test-001",
        "shots": [
            {"shot_id": "sh-01", "scene_id": "sc-01", "beat_id": "b-01",
             "framing": "medium-close-up", "shot_size": "medium-close-up",
             "camera_angle": "eye-level", "angle": "eye-level",
             "camera_height": "eye-level", "camera_movement": "static",
             "focus_target": "char-001",
             "lens_intent": "long lens to compress the background and "
                            "isolate the speaker",
             "lighting": "soft morning light from the left, warm grade",
             "duration_seconds": 4.5,
             "action": "She turns toward the sound, eyes widening.",
             "character_ids": ["char-001"],
             "subjects": [clone(SUBJECT_HUMAN)],
             "transition_to_next_shot": "cut"},
            {"shot_id": "sh-02", "scene_id": "sc-01", "beat_id": "b-02",
             "framing": "medium", "shot_size": "medium",
             "camera_angle": "low", "angle": "low",
             "camera_height": "ground-level", "camera_movement": "dolly",
             "focus_target": "char-kiki-001",
             "lens_intent": "wide lens to hold both characters",
             "lighting": "same soft morning light, slightly brighter",
             "duration_seconds": 3.0,
             "action": "She steps forward into the light.",
             "character_ids": ["char-001", "char-kiki-001"],
             "subjects": [clone(SUBJECT_HUMAN), clone(SUBJECT_BIRD)],
             "transition_to_next_shot": "cut"},
        ],
    }


def performance_plan():
    return {
        "schema_version": "2.4", "id": "performance-plan-test-001",
        "project_id": "proj-test-001", "dialogue_mode": "VERBATIM_SCRIPT",
        "lines": [
            {"line_id": "l-01", "dialogue_line_id": "d-01",
             "character_id": "char-001",
             "speaker_identity": "char-001, young protagonist, warm and "
                                 "steady voice",
             "dialogue": {"text": "I will help. Let us go together.",
                          "rewrite_permitted": False},
             "lip_sync_required": True, "speaking_state": "speaking",
             "articulation_target": "human-mouth-lips",
             "subject_kind": "digital-human", "species": "human",
             "language": "en", "primary_emotion": "trust",
             "secondary_emotion": "anticipation",
             "nuanced_emotion": "determination",
             "emotion": "warm determination", "emotion_intensity": 8,
             "emotion_transition": "worry in the previous line resolves "
                                   "into determination here",
             "facial_expression": "jaw set, small brave smile",
             "micro_expressions": ["brief eyebrow lift"],
             "eye_movement": "glance toward the companion, then forward",
             "gaze": "other-character",
             "posture": "shoulders back, chin level",
             "gestures": ["one step forward",
                          "open hand toward the companion"],
             "breathing": "one steadying breath before the line, then "
                          "even breathing",
             "physical_behaviour": "weight shifts forward as she commits",
             "voice": {"emotion": "warm determination",
                       "pitch": "moderate", "pace": "natural",
                       "pauses": ["short pause after 'help'"]},
             "non_verbal_events": [{"type": "breathing",
                                    "duration_seconds": 1.0,
                                    "intensity": 3}]},
            {"line_id": "l-02", "dialogue_line_id": "d-02",
             "character_id": "char-kiki-001",
             "speaker_identity": "char-kiki-001, African grey parrot, "
                                 "bright and quick",
             "dialogue": {"text": "Hello, Mira! I heard you coming.",
                          "rewrite_permitted": False},
             "lip_sync_required": True, "speaking_state": "speaking",
             "articulation_target": "bird-beak",
             "subject_kind": "cgi-animal",
             "species": "African grey parrot", "language": "en",
             "primary_emotion": "joy", "secondary_emotion": "trust",
             "nuanced_emotion": "delight", "emotion": "cheerful",
             "emotion_intensity": 7,
             "facial_expression": "beak opens in short bursts, head tilts",
             "micro_expressions": ["quick head tilt"],
             "eye_movement": "quick glance around, then to the companion",
             "gaze": "other-character",
             "posture": "perched upright, tail still",
             "gestures": ["small wing flutter"],
             "breathing": "quick breaths, then steady",
             "physical_behaviour": "feet grip the branch tighter",
             "voice": {"emotion": "bright cheer", "pitch": "high",
                       "pace": "brisk", "pauses": []},
             "non_verbal_events": [{"type": "breathing",
                                    "duration_seconds": 0.5,
                                    "intensity": 2}]},
        ],
    }


def draft():
    return {
        "scene_plan": scene_plan(),
        "shot_plan": shot_plan(),
        "performance_plan": performance_plan(),
        "audio_plan": {
            "ambience": [{"cue": "morning birds, distant river",
                          "timing": "sc-01 throughout"}],
            "music": [{"cue": "gentle strings rise under the decision",
                       "timing": "sc-01, beat b-02"}],
            "sfx": [{"cue": "soft footstep on dry leaves",
                     "timing": "sh-02"}]},
        "editing_plan": {
            "rhythm": "slow hold on the hesitation, quicker cut on the "
                      "decision",
            "reaction_holds": [{"after_line_id": "l-01",
                                "hold_seconds": 1.5,
                                "purpose": "let the decision land before "
                                           "the next scene"}]},
        "character_voice_binding": {
            "character_id": "char-001", "dialogue_line_id": "d-01",
            "voice_profile_id": "voice-aria-001",
            "audio_asset_id": "audio-aria-l01",
            "reference_asset_ids": ["asset-aria-001"], "shot_id": "sh-01",
            "speaking_state": "speaking", "emotion": "warm determination",
            "delivery": "warm, unhurried",
            "articulation": "human-mouth-lips"},
        "character_voice_bindings": [
            {"character_id": "char-kiki-001", "dialogue_line_id": "d-02",
             "voice_profile_id": "voice-kiki-001",
             "audio_asset_id": "audio-kiki-l02",
             "reference_asset_ids": ["asset-kiki-001"],
             "shot_id": "sh-02", "speaking_state": "speaking",
             "emotion": "cheerful",
             "delivery": "bright, quick, with a small head tilt",
             "articulation": "bird-beak"},
        ],
    }


# --- Non-verbal baseline: source lines carry no spoken text, the
# performance lines carry empty dialogue text plus non-verbal events.
def non_verbal_script():
    value = script()
    for line in value["dialogue"]:
        line["text"] = ""
    return value


def non_verbal_performance_plan():
    value = performance_plan()
    for line in value["lines"]:
        # No "text" key: the performance-plan schema gives
        # dialogue.text minLength 1, so a non-verbal line omits the
        # text rather than carrying an empty string (the P0 bird
        # fixture pattern).
        line["dialogue"] = {"rewrite_permitted": False}
        line["lip_sync_required"] = False
        line["speaking_state"] = "listening"
        line.setdefault("non_verbal_events",
                        [{"type": "breathing", "duration_seconds": 1.0,
                          "intensity": 3}])
    return value


# --- Rewrite-authorised baseline: SCRIPT_EDIT_REQUESTED, per-line
# permission, original text kept in dialogue.text, the changed
# version only in rewritten_text.
def rewrite_script():
    value = script()
    value["dialogue_mode"] = "SCRIPT_EDIT_REQUESTED"
    return value


def rewrite_performance_plan():
    value = performance_plan()
    value["dialogue_mode"] = "SCRIPT_EDIT_REQUESTED"
    line = value["lines"][0]
    line["dialogue"] = {
        "text": "I will help. Let us go together.",
        "rewrite_permitted": True,
        "rewritten_text": "I will help — let us go together, now."}
    return value


# ---------------------------------------------------------------------------
# Build helpers
# ---------------------------------------------------------------------------

def build(session=None, plan=None, scr=None, prof=None, drf=None,
          bundle_id="s2p-test-001", authorised=False):
    session = session if session is not None else fresh_session()
    plan = plan if plan is not None else fresh_routing_plan(session)
    return build_script_to_performance_bundle(
        session, plan,
        scr if scr is not None else script(),
        prof if prof is not None else profile(),
        drf if drf is not None else draft(),
        bundle_id, authorised)


def build_fails(label, **kwargs):
    try:
        build(**kwargs)
    except ScriptToPerformanceError as exc:
        check(label, True)
        return exc.errors
    check(label, False, "bundle built instead of refusing")
    return []


# ---------------------------------------------------------------------------
# CF-P1-003-SESSION-ROUTING: session and routing binding
# ---------------------------------------------------------------------------

def _session_routing_group():
    session = fresh_session()
    plan = fresh_routing_plan(session)
    bundle = build(session=session, plan=plan)
    check("CF-P1-003-SESSION-ROUTING: exact active session builds a "
          "bundle", bundle["bundle_id"] == "s2p-test-001"
          and bundle["session_id"] == session.session_id
          and bundle["routing_plan_id"] == plan["plan_id"]
          and bundle["script_to_performance"]["id"] == "s2p-test-001",
          f"bundle_id={bundle.get('bundle_id')} "
          f"session={bundle.get('session_id')}")
    check("CF-P1-003-SESSION-ROUTING: the bundle carries the router "
          "plan's selected skills verbatim",
          bundle["routing_plan_id"] == plan["plan_id"]
          and [entry["skill"] for entry in plan["selected_skills"]] == [
              "command-authority", "character-consistency",
              "voice-consistency", "production-systems",
              "humanized-production", "realistic-person"],
          f"selected={[entry['skill'] for entry in plan['selected_skills']]}")
    check("CF-P1-003-SESSION-ROUTING: the builder does not invent "
          "skills (it returns the routing plan only by ID)",
          "selected_skills" not in bundle
          and "skills" not in bundle)

    # Missing / forged / copied / expired / closed sessions fail.
    try:
        build_script_to_performance_bundle(
            None, plan, script(), profile(), draft(), "s2p-test-001")
        check("CF-P1-003-SESSION-ROUTING: None session fails",
              False, "bundle built with no session")
    except ScriptToPerformanceError:
        check("CF-P1-003-SESSION-ROUTING: None session fails", True)
    try:
        build_script_to_performance_bundle(
            "not-a-session", plan, script(), profile(), draft(),
            "s2p-test-001")
        check("CF-P1-003-SESSION-ROUTING: forged string session fails",
              False, "bundle built with a string session")
    except ScriptToPerformanceError:
        check("CF-P1-003-SESSION-ROUTING: forged string session fails",
              True)
    forged = copy.deepcopy(session)
    try:
        build_script_to_performance_bundle(
            forged, plan, script(), profile(), draft(), "s2p-test-001")
        check("CF-P1-003-SESSION-ROUTING: copied session fails",
              False, "bundle built with a copied session")
    except ScriptToPerformanceError:
        check("CF-P1-003-SESSION-ROUTING: copied session fails", True)
    expired_session = fresh_session()
    expired_plan = fresh_routing_plan(expired_session)
    close_session(expired_session)
    try:
        build_script_to_performance_bundle(
            expired_session, expired_plan, script(), profile(), draft(),
            "s2p-test-001")
        check("CF-P1-003-SESSION-ROUTING: closed session fails",
              False, "bundle built with a closed session")
    except ScriptToPerformanceError:
        check("CF-P1-003-SESSION-ROUTING: closed session fails", True)

    # Wrong session binding: a plan built for another session.
    other_session = fresh_session()
    other_plan = fresh_routing_plan(other_session)
    try:
        build_script_to_performance_bundle(
            session, other_plan, script(), profile(), draft(),
            "s2p-test-001")
        check("CF-P1-003-SESSION-ROUTING: plan bound to another "
              "session fails", False, "bundle built with a mismatched plan")
    except ScriptToPerformanceError:
        check("CF-P1-003-SESSION-ROUTING: plan bound to another "
              "session fails", True)

    # Blocked routing plan fails.
    blocked_plan = clone(plan)
    blocked_plan["status"] = "blocked"
    blocked_plan["blocked_diagnostics"] = [
        {"rule_id": "TC-TEST", "message": "test block"}]
    try:
        build_script_to_performance_bundle(
            session, blocked_plan, script(), profile(), draft(),
            "s2p-test-001")
        check("CF-P1-003-SESSION-ROUTING: blocked routing plan fails",
              False, "bundle built from a blocked plan")
    except ScriptToPerformanceError:
        check("CF-P1-003-SESSION-ROUTING: blocked routing plan fails",
              True)

    # Invalid routing plan fails (tampered plan hash).
    tampered_plan = clone(plan)
    tampered_plan["selected_skills"] = ["command-authority"]
    try:
        build_script_to_performance_bundle(
            session, tampered_plan, script(), profile(), draft(),
            "s2p-test-001")
        check("CF-P1-003-SESSION-ROUTING: tampered routing plan fails",
              False, "bundle built from a tampered plan")
    except ScriptToPerformanceError:
        check("CF-P1-003-SESSION-ROUTING: tampered routing plan fails",
              True)
    hash_tampered = clone(plan)
    hash_tampered["selected_skills"] = \
        hash_tampered["selected_skills"][:5]
    try:
        build_script_to_performance_bundle(
            session, hash_tampered, script(), profile(), draft(),
            "s2p-test-001")
        check("CF-P1-003-SESSION-ROUTING: plan with a stale hash "
              "fails", False, "bundle built from a hash-tampered plan")
    except ScriptToPerformanceError:
        check("CF-P1-003-SESSION-ROUTING: plan with a stale hash "
              "fails", True)

    # Wrong intent mode fails.
    wrong_mode_plan = fresh_routing_plan(session, "UPLOAD_ONLY")
    try:
        build_script_to_performance_bundle(
            session, wrong_mode_plan, script(), profile(), draft(),
            "s2p-test-001")
        check("CF-P1-003-SESSION-ROUTING: wrong intent mode fails",
              False, "bundle built for UPLOAD_ONLY")
    except ScriptToPerformanceError:
        check("CF-P1-003-SESSION-ROUTING: wrong intent mode fails", True)

    # A non-dict routing plan fails.
    try:
        build_script_to_performance_bundle(
            session, ["not-a-plan"], script(), profile(), draft(),
            "s2p-test-001")
        check("CF-P1-003-SESSION-ROUTING: non-object routing plan fails",
              False, "bundle built from a list plan")
    except ScriptToPerformanceError:
        check("CF-P1-003-SESSION-ROUTING: non-object routing plan fails",
              True)

    # Invalid bundle IDs fail.
    for bad_id in ("", "S2P-Test-001", "s2", "s2p test 001", None, 42):
        try:
            build_script_to_performance_bundle(
                session, plan, script(), profile(), draft(), bad_id)
            check(f"CF-P1-003-SESSION-ROUTING: bundle_id {bad_id!r} fails",
                  False, "bundle built with an invalid ID")
        except ScriptToPerformanceError:
            check(f"CF-P1-003-SESSION-ROUTING: bundle_id {bad_id!r} "
                  "fails", True)

    # Non-boolean rewrite flag is rejected, not silently false.
    for bad_flag in ("true", 1, None):
        try:
            build_script_to_performance_bundle(
                session, plan, script(), profile(), draft(),
                "s2p-test-001", bad_flag)
            check(f"CF-P1-003-SESSION-ROUTING: rewrite flag {bad_flag!r} "
                  "fails", False, "bundle built with a non-boolean flag")
        except ScriptToPerformanceError:
            check(f"CF-P1-003-SESSION-ROUTING: rewrite flag {bad_flag!r} "
                  "fails", True)


# ---------------------------------------------------------------------------
# CF-P1-003-SCRIPT: script validation
# ---------------------------------------------------------------------------

def _script_group():
    session = fresh_session()
    plan = fresh_routing_plan(session)
    check("CF-P1-003-SCRIPT: valid source script builds",
          build(session=session, plan=plan)["script_contract"]["id"]
          == "script-test-001")
    check("CF-P1-003-SCRIPT: validate_script_contract accepts the "
          "valid script", validate_script_contract(script()) == [])

    bad = script()
    del bad["dialogue"]
    check("CF-P1-003-SCRIPT: missing dialogue fails",
          validate_script_contract(bad) != [])
    bad = script()
    bad["dialogue_mode"] = "FREE_TEXT"
    check("CF-P1-003-SCRIPT: invalid dialogue_mode fails",
          validate_script_contract(bad) != [])
    bad = script()
    bad["dialogue"][0]["text"] = 42
    check("CF-P1-003-SCRIPT: non-string dialogue text fails",
          validate_script_contract(bad) != [])
    bad = script()
    bad["dialogue"][1]["line_id"] = "l-01"
    check("CF-P1-003-SCRIPT: duplicate dialogue IDs fail",
          validate_script_contract(bad) != [])
    check("CF-P1-003-SCRIPT: duplicate dialogue IDs fail at build",
          len(build_fails(
              "CF-P1-003-SCRIPT: duplicate dialogue IDs fail at build",
              session=session, plan=plan,
              scr=bad)) > 0)

    # Empty dialogue: a script with no spoken lines validates as a
    # script, but no valid bundle exists for it — the canonical
    # performance-plan schema requires at least one line (minItems
    # 1) while the dialogue mapping forbids inventing one (an extra
    # line fails). The builder therefore fails closed with a
    # structured error rather than fabricating a performance line.
    # This schema tension is recorded in the corrections record
    # (CF-WO-P1-003 §5); the schema is not changed to make it pass.
    empty = script()
    empty["dialogue"] = []
    check("CF-P1-003-SCRIPT: empty dialogue validates as a script",
          validate_script_contract(empty) == [])
    empty_draft = draft()
    empty_draft["performance_plan"]["lines"] = []
    check("CF-P1-003-SCRIPT: empty dialogue with an empty "
          "performance plan fails closed (schema minItems 1)",
          len(build_fails(
              "CF-P1-003-SCRIPT: empty dialogue with an empty "
              "performance plan fails closed (schema minItems 1)",
              session=session, plan=plan, scr=empty,
              drf=empty_draft)) > 0)
    check("CF-P1-003-SCRIPT: empty dialogue with a fabricated "
          "performance line fails closed (extra line)",
          len(build_fails(
              "CF-P1-003-SCRIPT: empty dialogue with a fabricated "
              "performance line fails closed (extra line)",
              session=session, plan=plan, scr=empty,
              drf=draft())) > 0)

    # Non-verbal-only script: every line empty text, performed
    # non-verbally.
    nv_session = fresh_session()
    nv_plan = fresh_routing_plan(nv_session)
    nv_draft = draft()
    nv_draft["performance_plan"] = non_verbal_performance_plan()
    check("CF-P1-003-SCRIPT: non-verbal-only script builds",
          build(session=nv_session, plan=nv_plan,
                scr=non_verbal_script(),
                drf=nv_draft)["performance_plan"]["lines"][0]
          ["dialogue"].get("text") is None)

    # A non-verbal line without non-verbal events fails (P0 PERF-004).
    nv_bad = draft()
    nv_bad["performance_plan"] = non_verbal_performance_plan()
    del nv_bad["performance_plan"]["lines"][0]["non_verbal_events"]
    check("CF-P1-003-SCRIPT: non-verbal line without non-verbal "
          "events fails",
          len(build_fails(
              "CF-P1-003-SCRIPT: non-verbal line without non-verbal "
              "events fails", session=nv_session, plan=nv_plan,
              scr=non_verbal_script(), drf=nv_bad)) > 0)

    # Script shots must not be silently omitted from the shot plan.
    missing_shot = script()
    missing_shot["shots"].append(
        {"shot_id": "sh-99", "duration_seconds": 2.0,
         "framing": "wide", "camera": "eye-level"})
    check("CF-P1-003-SCRIPT: source shot missing from the shot plan "
          "fails",
          len(build_fails(
              "CF-P1-003-SCRIPT: source shot missing from the shot "
              "plan fails", session=session, plan=plan,
              scr=missing_shot)) > 0)


# ---------------------------------------------------------------------------
# CF-P1-003-PLANS: plan validation
# ---------------------------------------------------------------------------

def _plans_group():
    session = fresh_session()
    plan = fresh_routing_plan(session)
    check("CF-P1-003-PLANS: valid Scene/Shot/Performance Plans build",
          build(session=session, plan=plan)["scene_plan"]["id"]
          == "scene-plan-test-001")
    check("CF-P1-003-PLANS: validate_scene_plan accepts the valid plan",
          validate_scene_plan(scene_plan()) == [])
    check("CF-P1-003-PLANS: validate_shot_plan accepts the valid plan",
          validate_shot_plan(shot_plan()) == [])
    check("CF-P1-003-PLANS: validate_performance_plan accepts the "
          "valid plan", validate_performance_plan(performance_plan())
          == [])

    # Invalid enum / type / value.
    bad = scene_plan()
    bad["scenes"][0]["beats"][0]["primary_emotion"] = "ecstasy"
    check("CF-P1-003-PLANS: invalid emotion enum fails (P0 PERF-003)",
          validate_scene_plan(bad) != [])
    bad = scene_plan()
    bad["scenes"][0]["beats"][0]["emotion_intensity"] = 11
    check("CF-P1-003-PLANS: emotion intensity above 10 fails "
          "(P0 PERF-001)", validate_scene_plan(bad) != [])
    bad = performance_plan()
    bad["lines"][0]["emotion_intensity"] = -1
    check("CF-P1-003-PLANS: negative emotion intensity fails "
          "(P0 PERF-001)", validate_performance_plan(bad) != [])
    bad = shot_plan()
    bad["shots"][0]["camera_movement"] = "spiral"
    check("CF-P1-003-PLANS: invalid camera movement fails",
          validate_shot_plan(bad) != [])
    bad = shot_plan()
    bad["shots"][0]["duration_seconds"] = 0
    check("CF-P1-003-PLANS: zero shot duration fails (P0 PERF-002)",
          validate_shot_plan(bad) != [])
    bad = shot_plan()
    bad["shots"][0]["duration_seconds"] = -2.5
    check("CF-P1-003-PLANS: negative shot duration fails (P0 PERF-002)",
          validate_shot_plan(bad) != [])
    bad = performance_plan()
    bad["lines"][0]["gaze"] = "into-the-void"
    check("CF-P1-003-PLANS: invalid gaze enum fails",
          validate_performance_plan(bad) != [])

    # Invalid or duplicate identifiers.
    bad = scene_plan()
    bad["scenes"][0]["beats"][1]["beat_id"] = "b-01"
    check("CF-P1-003-PLANS: duplicate beat IDs fail",
          validate_scene_plan(bad) != [])
    bad = shot_plan()
    bad["shots"][1]["shot_id"] = "sh-01"
    check("CF-P1-003-PLANS: duplicate shot IDs fail",
          validate_shot_plan(bad) != [])
    bad = performance_plan()
    bad["lines"][1]["line_id"] = "l-01"
    check("CF-P1-003-PLANS: duplicate performance line IDs fail",
          validate_performance_plan(bad) != [])
    bad = scene_plan()
    bad["scenes"].append(clone(bad["scenes"][0]))
    check("CF-P1-003-PLANS: duplicate scene IDs fail",
          validate_scene_plan(bad) != [])

    # Missing required non-verbal events (P0 PERF-004).
    bad = performance_plan()
    bad["lines"][0]["dialogue"] = {}
    del bad["lines"][0]["non_verbal_events"]
    check("CF-P1-003-PLANS: non-verbal line without non-verbal "
          "events fails", validate_performance_plan(bad) != [])
    bad = scene_plan()
    bad["scenes"][0]["beats"][0]["primary_emotion"] = "sadness"
    bad["scenes"][0]["beats"][0]["non_verbal_events"] = []
    check("CF-P1-003-PLANS: a sad beat without non-verbal events "
          "passes (P0 PERF-004 binds performance lines only; no "
          "beat-level non-verbal requirement exists in the canonical "
          "rules)",
          validate_scene_plan(bad) == [])

    # Human lip articulation on an animal fails; bird-beak on a
    # bird passes.
    bad = performance_plan()
    bad["lines"][1]["articulation_target"] = "human-mouth-lips"
    check("CF-P1-003-PLANS: human lips on a bird fails",
          validate_performance_plan(bad) != [])
    bad = scene_plan()
    bad["scenes"][0]["subjects"][1]["articulation_target"] = \
        "human-mouth-lips"
    check("CF-P1-003-PLANS: human lips on a bird subject fails",
          validate_scene_plan(bad) != [])
    bad = performance_plan()
    bad["lines"][1]["articulation_target"] = "bird-beak"
    check("CF-P1-003-PLANS: bird-beak on a bird passes",
          validate_performance_plan(bad) == [])

    # Draft-level validation: missing plan, unexpected field.
    bad_draft = draft()
    del bad_draft["shot_plan"]
    check("CF-P1-003-PLANS: draft missing the shot plan fails",
          validate_script_plan_drafts(bad_draft, script()) != [])
    bad_draft = draft()
    bad_draft["surprise_plan"] = {}
    check("CF-P1-003-PLANS: draft with an unexpected field fails",
          validate_script_plan_drafts(bad_draft, script()) != [])
    check("CF-P1-003-PLANS: draft validates without a script "
          "(cross-refs only)",
          validate_script_plan_drafts(draft()) == [])


# ---------------------------------------------------------------------------
# CF-P1-003-DIALOGUE: verbatim dialogue preservation and rewrite
# authorisation (P0 PERF-005)
# ---------------------------------------------------------------------------

def _dialogue_group():
    session = fresh_session()
    plan = fresh_routing_plan(session)
    bundle = build(session=session, plan=plan)
    source_lines = script()["dialogue"]
    built_lines = bundle["performance_plan"]["lines"]
    check("CF-P1-003-DIALOGUE: verbatim text survives byte-for-byte "
          "(code-point-for-code-point)",
          all(built["dialogue"]["text"] == source["text"]
              for built, source in zip(built_lines, source_lines))
          and [line["dialogue"]["text"] for line in built_lines]
          == ["I will help. Let us go together.",
              "Hello, Mira! I heard you coming."])
    check("CF-P1-003-DIALOGUE: the S2P record defaults to "
          "VERBATIM_SCRIPT with rewrites unauthorised",
          bundle["script_to_performance"]["dialogue_mode"]
          == "VERBATIM_SCRIPT"
          and bundle["script_to_performance"]
          ["dialogue_rewrite_authorised"] is False)

    # Reordering lines fails.
    bad = draft()
    bad["performance_plan"]["lines"] = list(
        reversed(bad["performance_plan"]["lines"]))
    check("CF-P1-003-DIALOGUE: reordering performance lines fails",
          len(build_fails(
              "CF-P1-003-DIALOGUE: reordering performance lines fails",
              session=session, plan=plan, drf=bad)) > 0)

    # Missing / extra / duplicate lines fail.
    bad = draft()
    bad["performance_plan"]["lines"] = \
        bad["performance_plan"]["lines"][:1]
    check("CF-P1-003-DIALOGUE: missing performance line fails",
          len(build_fails(
              "CF-P1-003-DIALOGUE: missing performance line fails",
              session=session, plan=plan, drf=bad)) > 0)
    bad = draft()
    extra = clone(bad["performance_plan"]["lines"][0])
    extra["line_id"] = "l-03"
    extra["dialogue_line_id"] = "d-03"
    bad["performance_plan"]["lines"].append(extra)
    check("CF-P1-003-DIALOGUE: extra performance line fails",
          len(build_fails(
              "CF-P1-003-DIALOGUE: extra performance line fails",
              session=session, plan=plan, drf=bad)) > 0)
    bad = draft()
    bad["performance_plan"]["lines"][1]["line_id"] = "l-01"
    check("CF-P1-003-DIALOGUE: duplicate performance line ID fails",
          len(build_fails(
              "CF-P1-003-DIALOGUE: duplicate performance line ID fails",
              session=session, plan=plan, drf=bad)) > 0)

    # Changed dialogue text fails.
    bad = draft()
    bad["performance_plan"]["lines"][0]["dialogue"]["text"] = \
        "I will help! Let's go together."
    check("CF-P1-003-DIALOGUE: changed dialogue text fails",
          len(build_fails(
              "CF-P1-003-DIALOGUE: changed dialogue text fails",
              session=session, plan=plan, drf=bad)) > 0)

    # Mismatched character ID where the source supplies one fails.
    bad = draft()
    bad["performance_plan"]["lines"][0]["character_id"] = "char-kiki-001"
    check("CF-P1-003-DIALOGUE: mismatched character ID fails",
          len(build_fails(
              "CF-P1-003-DIALOGUE: mismatched character ID fails",
              session=session, plan=plan, drf=bad)) > 0)

    # Unauthorised rewrite fails (P0 PERF-005): rewritten_text with
    # no permission, and with the plan asking but the caller not.
    bad = draft()
    bad["performance_plan"]["lines"][0]["dialogue"]["rewritten_text"] = \
        "I will help — let us go together, now."
    check("CF-P1-003-DIALOGUE: rewritten text without permission "
          "fails",
          len(build_fails(
              "CF-P1-003-DIALOGUE: rewritten text without permission "
              "fails", session=session, plan=plan, drf=bad)) > 0)
    bad = draft()
    bad["performance_plan"]["dialogue_mode"] = "SCRIPT_EDIT_REQUESTED"
    bad["performance_plan"]["lines"][0]["dialogue"] = {
        "text": "I will help. Let us go together.",
        "rewrite_permitted": True,
        "rewritten_text": "I will help — let us go together, now."}
    check("CF-P1-003-DIALOGUE: plan-level rewrite request alone "
          "does not authorise a rewrite",
          len(build_fails(
              "CF-P1-003-DIALOGUE: plan-level rewrite request alone "
              "does not authorise a rewrite", session=session, plan=plan,
              drf=bad)) > 0)

    # Explicitly authorised per-line rewrite retains the original.
    rw_session = fresh_session()
    rw_plan = fresh_routing_plan(rw_session)
    rw_draft = draft()
    rw_draft["performance_plan"] = rewrite_performance_plan()
    rw_bundle = build(session=rw_session, plan=rw_plan,
                      scr=rewrite_script(), drf=rw_draft,
                      authorised=True)
    check("CF-P1-003-DIALOGUE: authorised per-line rewrite builds",
          rw_bundle["script_to_performance"]
          ["dialogue_rewrite_authorised"] is True)
    check("CF-P1-003-DIALOGUE: authorised rewrite keeps the original "
          "text in dialogue.text and the change only in "
          "rewritten_text",
          rw_bundle["performance_plan"]["lines"][0]["dialogue"]["text"]
          == "I will help. Let us go together."
          and rw_bundle["performance_plan"]["lines"][0]["dialogue"]
          ["rewritten_text"]
          == "I will help — let us go together, now.")
    check("CF-P1-003-DIALOGUE: authorised rewrite keeps the "
          "untouched line verbatim",
          rw_bundle["performance_plan"]["lines"][1]["dialogue"]["text"]
          == "Hello, Mira! I heard you coming."
          and "rewritten_text" not in
          rw_bundle["performance_plan"]["lines"][1]["dialogue"])

    # Caller authorisation without the plan's SCRIPT_EDIT_REQUESTED
    # still fails: the plan must ask, the line must permit, and the
    # caller must authorise — all three.
    bad = draft()
    bad["performance_plan"]["lines"][0]["dialogue"] = {
        "text": "I will help. Let us go together.",
        "rewrite_permitted": True,
        "rewritten_text": "I will help — let us go together, now."}
    check("CF-P1-003-DIALOGUE: caller authorisation without "
          "SCRIPT_EDIT_REQUESTED fails",
          len(build_fails(
              "CF-P1-003-DIALOGUE: caller authorisation without "
              "SCRIPT_EDIT_REQUESTED fails", session=session, plan=plan,
              drf=bad, authorised=True)) > 0)


# ---------------------------------------------------------------------------
# CF-P1-003-XREF: cross-plan integrity
# ---------------------------------------------------------------------------

def _xref_group():
    session = fresh_session()
    plan = fresh_routing_plan(session)

    def xref_fails(label, mutate):
        bad = draft()
        mutate(bad)
        return build_fails(label, session=session, plan=plan, drf=bad)

    # Wrong scene / beat / shot references.
    check("CF-P1-003-XREF: shot referencing a missing scene fails",
          len(xref_fails(
              "CF-P1-003-XREF: shot referencing a missing scene fails",
              lambda d: d["shot_plan"]["shots"][0]
              .__setitem__("scene_id", "sc-99"))) > 0)
    check("CF-P1-003-XREF: shot referencing a missing beat fails",
          len(xref_fails(
              "CF-P1-003-XREF: shot referencing a missing beat fails",
              lambda d: d["shot_plan"]["shots"][0]
              .__setitem__("beat_id", "b-99"))) > 0)
    check("CF-P1-003-XREF: shot_plan scene_plan_id mismatch fails",
          len(xref_fails(
              "CF-P1-003-XREF: shot_plan scene_plan_id mismatch fails",
              lambda d: d["shot_plan"]
              .__setitem__("scene_plan_id", "scene-plan-other"))) > 0)

    # Wrong dialogue / character / project references.
    check("CF-P1-003-XREF: voice binding to an unknown dialogue "
          "line fails",
          len(xref_fails(
              "CF-P1-003-XREF: voice binding to an unknown dialogue "
              "line fails",
              lambda d: d["character_voice_binding"]
              .__setitem__("dialogue_line_id", "d-99"))) > 0)
    check("CF-P1-003-XREF: voice binding to an unknown shot fails",
          len(xref_fails(
              "CF-P1-003-XREF: voice binding to an unknown shot fails",
              lambda d: d["character_voice_binding"]
              .__setitem__("shot_id", "sh-99"))) > 0)
    check("CF-P1-003-XREF: voice binding to an unknown character "
          "fails",
          len(xref_fails(
              "CF-P1-003-XREF: voice binding to an unknown character "
              "fails",
              lambda d: d["character_voice_binding"]
              .__setitem__("character_id", "char-unknown"))) > 0)
    check("CF-P1-003-XREF: voice binding for the wrong character "
          "on that line fails",
          len(xref_fails(
              "CF-P1-003-XREF: voice binding for the wrong character "
              "on that line fails",
              lambda d: d["character_voice_binding"]
              .__setitem__("character_id", "char-kiki-001"))) > 0)
    check("CF-P1-003-XREF: reaction hold after an unknown line "
          "fails",
          len(xref_fails(
              "CF-P1-003-XREF: reaction hold after an unknown line "
              "fails",
              lambda d: d["editing_plan"]["reaction_holds"][0]
              .__setitem__("after_line_id", "l-99"))) > 0)
    check("CF-P1-003-XREF: shot referencing an unknown character "
          "fails",
          len(xref_fails(
              "CF-P1-003-XREF: shot referencing an unknown character "
              "fails",
              lambda d: d["shot_plan"]["shots"][0]
              .__setitem__("character_ids", ["char-unknown"]))) > 0)
    check("CF-P1-003-XREF: performance line for an unknown "
          "character fails",
          len(xref_fails(
              "CF-P1-003-XREF: performance line for an unknown "
              "character fails",
              lambda d: d["performance_plan"]["lines"][0]
              .__setitem__("character_id", "char-unknown"))) > 0)

    # Wrong project ID fails.
    bad = draft()
    bad["scene_plan"]["project_id"] = "proj-other-001"
    check("CF-P1-003-XREF: scene plan with a different project ID "
          "fails",
          len(build_fails(
              "CF-P1-003-XREF: scene plan with a different project ID "
              "fails", session=session, plan=plan, drf=bad)) > 0)
    bad = profile()
    bad["project_id"] = "proj-other-001"
    check("CF-P1-003-XREF: profile with a different project ID "
          "fails",
          len(build_fails(
              "CF-P1-003-XREF: profile with a different project ID "
              "fails", session=session, plan=plan, prof=bad)) > 0)

    # Contradictory subject dimensions fail.
    check("CF-P1-003-XREF: contradictory subject kind across plans "
          "fails",
          len(xref_fails(
              "CF-P1-003-XREF: contradictory subject kind across "
              "plans fails",
              lambda d: d["shot_plan"]["shots"][0]["subjects"][0]
              .__setitem__("subject_kind", "cgi-animal"))) > 0)
    check("CF-P1-003-XREF: contradictory rendering style across "
          "plans fails",
          len(xref_fails(
              "CF-P1-003-XREF: contradictory rendering style across "
              "plans fails",
              lambda d: d["shot_plan"]["shots"][1]["subjects"][1]
              .__setitem__("rendering_style", "photorealistic"))) > 0)
    check("CF-P1-003-XREF: subject motion method outside the "
          "profile list fails",
          len(xref_fails(
              "CF-P1-003-XREF: subject motion method outside the "
              "profile list fails",
              lambda d: d["shot_plan"]["shots"][0]["subjects"][0]
              .__setitem__("motion_method", "creature-articulation")))
          > 0)

    # Ambiguous singular + plural bindings fail; identical
    # duplicates stay allowed.
    bad = draft()
    bad["character_voice_bindings"] = [clone(
        bad["character_voice_binding"])]
    bad["character_voice_bindings"][0]["delivery"] = "different"
    check("CF-P1-003-XREF: ambiguous singular + plural bindings "
          "fail",
          len(build_fails(
              "CF-P1-003-XREF: ambiguous singular + plural bindings "
              "fail", session=session, plan=plan, drf=bad)) > 0)
    ok = draft()
    ok["character_voice_bindings"] = [clone(
        ok["character_voice_binding"])]
    check("CF-P1-003-XREF: identical duplicate bindings stay "
          "allowed",
          build(session=session, plan=plan, drf=ok)
          ["script_to_performance"]["character_voice_bindings"][0]
          ["dialogue_line_id"] == "d-01")

    # The S2P root IDs must match the actual plan IDs: a tampered
    # bundle fails its own validation.
    bundle = build(session=session, plan=plan)
    tampered = clone(bundle)
    tampered["script_to_performance"]["shot_plan_id"] = "shot-plan-other"
    check("CF-P1-003-XREF: tampered S2P root ID fails bundle "
          "validation",
          validate_script_to_performance_bundle(tampered) != [])
    tampered = clone(bundle)
    tampered["script_to_performance"]["id"] = "s2p-other-001"
    check("CF-P1-003-XREF: S2P id differing from the bundle id "
          "fails bundle validation",
          validate_script_to_performance_bundle(tampered) != [])


# ---------------------------------------------------------------------------
# CF-P1-003-DETERMINISM: determinism and output integrity
# ---------------------------------------------------------------------------

def _determinism_group():
    session = fresh_session()
    plan = fresh_routing_plan(session)
    first = build(session=session, plan=plan)
    second = build(session=session, plan=plan)
    check("CF-P1-003-DETERMINISM: identical input produces identical "
          "bundle hash",
          first["bundle_hash"] == second["bundle_hash"],
          f"first={first['bundle_hash']} second={second['bundle_hash']}")
    check("CF-P1-003-DETERMINISM: identical input produces identical "
          "bundles",
          first == second)
    check("CF-P1-003-DETERMINISM: the stored hash recomputes from "
          "the bundle contents",
          script_to_performance_hash(first) == first["bundle_hash"])

    # Changed plan content changes the bundle hash.
    changed = draft()
    changed["scene_plan"]["scenes"][0]["beats"][0]["emotion_intensity"] = 6
    other = build(session=session, plan=plan, drf=changed)
    check("CF-P1-003-DETERMINISM: changed plan content changes the "
          "bundle hash",
          other["bundle_hash"] != first["bundle_hash"])
    changed = draft()
    changed["performance_plan"]["lines"][0]["gestures"] = [
        "one step forward"]
    other = build(session=session, plan=plan, drf=changed)
    check("CF-P1-003-DETERMINISM: changed gesture changes the bundle "
          "hash", other["bundle_hash"] != first["bundle_hash"])

    # Input objects remain unchanged after execution.
    scr, prof, drf = script(), profile(), draft()
    scr_before, prof_before, drf_before = clone(scr), clone(prof), \
        clone(drf)
    plan_before = clone(plan)
    build(session=session, plan=plan, scr=scr, prof=prof, drf=drf)
    check("CF-P1-003-DETERMINISM: input objects are never modified "
          "in place",
          scr == scr_before and prof == prof_before
          and drf == drf_before and plan == plan_before)

    # Output records all validate against their canonical schemas.
    for schema_name, record in (
            ("script-contract.json", first["script_contract"]),
            ("production-profile.json", first["production_profile"]),
            ("script-to-performance.json",
             first["script_to_performance"]),
            ("scene-plan.json", first["scene_plan"]),
            ("shot-plan.json", first["shot_plan"]),
            ("performance-plan.json", first["performance_plan"])):
        schema = json.load(open(os.path.join(
            ROOT, "schemas", schema_name)))
        errors = []
        validate_instance(schema, record, schema_name, errors)
        check(f"CF-P1-003-DETERMINISM: output {schema_name} validates "
              "against its canonical schema", errors == [],
              f"errors={errors}")
    check("CF-P1-003-DETERMINISM: the whole bundle validates",
          validate_script_to_performance_bundle(first) == [])

    # No partial bundle is returned on validation failure.
    bad = draft()
    bad["shot_plan"]["shots"][0]["duration_seconds"] = 0
    try:
        build(session=session, plan=plan, drf=bad)
        check("CF-P1-003-DETERMINISM: no partial bundle on failure",
              False, "bundle returned despite invalid duration")
    except ScriptToPerformanceError:
        check("CF-P1-003-DETERMINISM: no partial bundle on failure",
              True)

    # A tampered bundle hash fails validation.
    tampered = clone(first)
    tampered["bundle_hash"] = "0" * 64
    check("CF-P1-003-DETERMINISM: tampered bundle hash fails "
          "validation",
          validate_script_to_performance_bundle(tampered) != [])
    tampered = clone(first)
    tampered["scene_plan"]["scenes"][0]["beats"][0]["emotion_intensity"] = 9
    check("CF-P1-003-DETERMINISM: tampered bundle content fails "
          "validation (hash mismatch)",
          validate_script_to_performance_bundle(tampered) != [])


# ---------------------------------------------------------------------------
# CF-P1-003-NULL156: optional-field nullability parity over the six
# schemas this runtime consumes. Declared matrix (schema, path):
# every optional property path, exactly once. A future optional
# schema field without a matching test fails the coverage
# assertion below.
# ---------------------------------------------------------------------------

NULL156_CASES = [
    ("script-contract", "audio_plan"),
    ("script-contract", "beats"),
    ("script-contract", "dialogue[i].character_id"),
    ("script-contract", "dialogue[i].language"),
    ("script-contract", "performance_cues"),
    ("script-contract", "project_id"),
    ("script-contract", "shots"),
    ("script-contract", "shots[i].camera"),
    ("script-contract", "shots[i].character_ids"),
    ("script-contract", "shots[i].duration_seconds"),
    ("script-contract", "shots[i].framing"),
    ("script-contract", "version"),
    ("script-to-performance", "audio_plan"),
    ("script-to-performance", "audio_plan.ambience"),
    ("script-to-performance", "audio_plan.ambience[i].timing"),
    ("script-to-performance", "audio_plan.music"),
    ("script-to-performance", "audio_plan.music[i].timing"),
    ("script-to-performance", "audio_plan.sfx"),
    ("script-to-performance", "audio_plan.sfx[i].timing"),
    ("script-to-performance", "character_voice_binding"),
    ("script-to-performance", "character_voice_binding.articulation"),
    ("script-to-performance", "character_voice_binding.audio_asset_id"),
    ("script-to-performance", "character_voice_binding.delivery"),
    ("script-to-performance", "character_voice_binding.emotion"),
    ("script-to-performance",
     "character_voice_binding.reference_asset_ids"),
    ("script-to-performance", "character_voice_binding.shot_id"),
    ("script-to-performance", "character_voice_binding.speaking_state"),
    ("script-to-performance",
     "character_voice_binding.voice_profile_id"),
    ("script-to-performance", "character_voice_bindings"),
    ("script-to-performance",
     "character_voice_bindings[i].articulation"),
    ("script-to-performance",
     "character_voice_bindings[i].audio_asset_id"),
    ("script-to-performance", "character_voice_bindings[i].delivery"),
    ("script-to-performance", "character_voice_bindings[i].emotion"),
    ("script-to-performance",
     "character_voice_bindings[i].reference_asset_ids"),
    ("script-to-performance", "character_voice_bindings[i].shot_id"),
    ("script-to-performance",
     "character_voice_bindings[i].speaking_state"),
    ("script-to-performance",
     "character_voice_bindings[i].voice_profile_id"),
    ("script-to-performance", "editing_plan"),
    ("script-to-performance", "editing_plan.reaction_holds"),
    ("script-to-performance", "editing_plan.reaction_holds[i].purpose"),
    ("script-to-performance", "editing_plan.rhythm"),
    ("script-to-performance", "project_id"),
    ("scene-plan", "project_id"),
    ("scene-plan", "scenes[i].beats[i].description"),
    ("scene-plan", "scenes[i].beats[i].emotion_intensity"),
    ("scene-plan", "scenes[i].beats[i].emotion_transition"),
    ("scene-plan", "scenes[i].beats[i].non_verbal_events"),
    ("scene-plan", "scenes[i].beats[i].non_verbal_events[i].duration_seconds"),
    ("scene-plan", "scenes[i].beats[i].non_verbal_events[i].intensity"),
    ("scene-plan", "scenes[i].beats[i].non_verbal_events[i].onset"),
    ("scene-plan", "scenes[i].beats[i].nuanced_emotion"),
    ("scene-plan", "scenes[i].beats[i].secondary_emotion"),
    ("scene-plan", "scenes[i].character_ids"),
    ("scene-plan", "scenes[i].location_id"),
    ("scene-plan", "scenes[i].subjects"),
    ("scene-plan", "scenes[i].subjects[i].articulation_target"),
    ("scene-plan", "scenes[i].subjects[i].contact"),
    ("scene-plan", "scenes[i].subjects[i].continuity"),
    ("scene-plan", "scenes[i].subjects[i].eyeline_target"),
    ("scene-plan", "scenes[i].subjects[i].is_live_action_footage"),
    ("scene-plan", "scenes[i].subjects[i].motion_method"),
    ("scene-plan", "scenes[i].subjects[i].position"),
    ("scene-plan", "scenes[i].subjects[i].rendering_style"),
    ("scene-plan", "scenes[i].subjects[i].representation"),
    ("scene-plan", "scenes[i].subjects[i].scale"),
    ("scene-plan", "scenes[i].subjects[i].source_media"),
    ("scene-plan", "scenes[i].subjects[i].species"),
    ("scene-plan", "scenes[i].subjects[i].subject_kind"),
    ("scene-plan", "scenes[i].title"),
    ("scene-plan", "scenes[i].visual_style_profile_id"),
    ("shot-plan", "project_id"),
    ("shot-plan", "scene_plan_id"),
    ("shot-plan", "shots[i].action"),
    ("shot-plan", "shots[i].angle"),
    ("shot-plan", "shots[i].beat_id"),
    ("shot-plan", "shots[i].camera_angle"),
    ("shot-plan", "shots[i].camera_height"),
    ("shot-plan", "shots[i].camera_movement"),
    ("shot-plan", "shots[i].character_ids"),
    ("shot-plan", "shots[i].depth_of_field"),
    ("shot-plan", "shots[i].duration_seconds"),
    ("shot-plan", "shots[i].focus_target"),
    ("shot-plan", "shots[i].lens_intent"),
    ("shot-plan", "shots[i].lighting"),
    ("shot-plan", "shots[i].shot_size"),
    ("shot-plan", "shots[i].subjects"),
    ("shot-plan", "shots[i].subjects[i].articulation_target"),
    ("shot-plan", "shots[i].subjects[i].contact"),
    ("shot-plan", "shots[i].subjects[i].continuity"),
    ("shot-plan", "shots[i].subjects[i].eyeline_target"),
    ("shot-plan", "shots[i].subjects[i].is_live_action_footage"),
    ("shot-plan", "shots[i].subjects[i].motion_method"),
    ("shot-plan", "shots[i].subjects[i].position"),
    ("shot-plan", "shots[i].subjects[i].rendering_style"),
    ("shot-plan", "shots[i].subjects[i].representation"),
    ("shot-plan", "shots[i].subjects[i].scale"),
    ("shot-plan", "shots[i].subjects[i].source_media"),
    ("shot-plan", "shots[i].subjects[i].species"),
    ("shot-plan", "shots[i].subjects[i].subject_kind"),
    ("shot-plan", "shots[i].transition_to_next_shot"),
    ("performance-plan", "lines[i].articulation_target"),
    ("performance-plan", "lines[i].audio_asset_id"),
    ("performance-plan", "lines[i].breathing"),
    ("performance-plan", "lines[i].character_id"),
    ("performance-plan", "lines[i].delivery"),
    ("performance-plan", "lines[i].dialogue"),
    ("performance-plan", "lines[i].dialogue.rewrite_permitted"),
    ("performance-plan", "lines[i].dialogue.rewritten_text"),
    ("performance-plan", "lines[i].dialogue.text"),
    ("performance-plan", "lines[i].dialogue_line_id"),
    ("performance-plan", "lines[i].emotion"),
    ("performance-plan", "lines[i].emotion_intensity"),
    ("performance-plan", "lines[i].emotion_transition"),
    ("performance-plan", "lines[i].eye_movement"),
    ("performance-plan", "lines[i].facial_expression"),
    ("performance-plan", "lines[i].gaze"),
    ("performance-plan", "lines[i].gestures"),
    ("performance-plan", "lines[i].language"),
    ("performance-plan", "lines[i].listener_state"),
    ("performance-plan", "lines[i].micro_expressions"),
    ("performance-plan", "lines[i].non_verbal_events"),
    ("performance-plan",
     "lines[i].non_verbal_events[i].duration_seconds"),
    ("performance-plan", "lines[i].non_verbal_events[i].intensity"),
    ("performance-plan", "lines[i].non_verbal_events[i].onset"),
    ("performance-plan", "lines[i].nuanced_emotion"),
    ("performance-plan", "lines[i].physical_behaviour"),
    ("performance-plan", "lines[i].posture"),
    ("performance-plan", "lines[i].primary_emotion"),
    ("performance-plan", "lines[i].reference_asset_ids"),
    ("performance-plan", "lines[i].secondary_emotion"),
    ("performance-plan", "lines[i].speaker_identity"),
    ("performance-plan", "lines[i].speaking_state"),
    ("performance-plan", "lines[i].species"),
    ("performance-plan", "lines[i].subject_kind"),
    ("performance-plan", "lines[i].voice"),
    ("performance-plan", "lines[i].voice.pauses"),
    ("performance-plan", "lines[i].voice_profile_id"),
    ("performance-plan", "project_id"),
    ("production-profile", "name"),
    ("production-profile", "per_shot_overrides"),
    ("production-profile", "per_shot_overrides[i].camera_movement"),
    ("production-profile", "per_shot_overrides[i].depth_of_field"),
    ("production-profile", "per_shot_overrides[i].focus_target"),
    ("production-profile", "per_shot_overrides[i].lighting"),
    ("production-profile",
     "per_shot_overrides[i].transition_to_next_shot"),
    ("production-profile", "per_subject_overrides"),
    ("production-profile",
     "per_subject_overrides[i].articulation_target"),
    ("production-profile",
     "per_subject_overrides[i].is_live_action_footage"),
    ("production-profile", "per_subject_overrides[i].motion_methods"),
    ("production-profile", "per_subject_overrides[i].rendering_style"),
    ("production-profile", "per_subject_overrides[i].representation"),
    ("production-profile", "per_subject_overrides[i].source_media"),
    ("production-profile", "per_subject_overrides[i].species"),
    ("production-profile", "per_subject_overrides[i].subject_kind"),
    ("production-profile", "project_id"),
    ("production-profile", "skill_profiles"),
]

_NULL_BASELINES = {
    "script-contract": (script, validate_script_contract),
    "production-profile": (profile, validate_production_profile),
    "scene-plan": (scene_plan, validate_scene_plan),
    "shot-plan": (shot_plan, validate_shot_plan),
    "performance-plan": (performance_plan, validate_performance_plan),
}
# Per-check baseline variants. The standard baseline is the full
# valid record. The dialogue object and its text need two
# baselines: "present" and "null" use the standard spoken baseline
# (text present with a real value), while "omitted" uses the
# non-verbal baseline (source text "" and non-verbal events
# present, so omitting the object or the text stays valid —
# dialogue.text has minLength 1, so a non-verbal line omits it
# rather than carrying ""). rewritten_text uses the
# rewrite-authorised baseline for all three checks.
_NULL_SPECIAL_BASELINES = {
    ("performance-plan", "lines[i].dialogue"): {
        "omitted": non_verbal_performance_plan},
    ("performance-plan", "lines[i].dialogue.text"): {
        "omitted": non_verbal_performance_plan},
    ("performance-plan", "lines[i].dialogue.rewritten_text"): {
        "present": rewrite_performance_plan,
        "omitted": rewrite_performance_plan,
        "null": rewrite_performance_plan},
}
# Paths the standard baseline does not carry: the "present" check
# first sets this valid value.
_NULL_PRESENT_VALUES = {
    ("scene-plan", "scenes[i].beats[i].non_verbal_events[i].onset"):
        "before the line",
    ("performance-plan", "lines[i].non_verbal_events[i].onset"):
        "before the line",
    ("performance-plan", "lines[i].audio_asset_id"): "audio-aria-l01",
    ("performance-plan", "lines[i].delivery"): "warm, unhurried",
    ("performance-plan", "lines[i].reference_asset_ids"):
        ["asset-aria-001"],
    ("performance-plan", "lines[i].voice_profile_id"): "voice-aria-001",
    ("performance-plan", "lines[i].listener_state"): "attentive",
}


def _null_optional_schema_paths(schema):
    """Optional property paths of one schema, as dotted paths with
    [i] for array-item objects. A path is optional when its
    property is not in its parent's required list."""
    found = set()

    def walk(node, prefix, required):
        for name, sub in (node.get("properties") or {}).items():
            path = f"{prefix}.{name}" if prefix else name
            if name not in required:
                found.add(path)
            if sub.get("type") == "object":
                walk(sub, path, set(sub.get("required") or []))
            items = sub.get("items")
            if isinstance(items, dict) and items.get("type") == "object":
                walk(items, path + "[i]",
                     set(items.get("required") or []))
            for key in ("anyOf", "oneOf"):
                for branch in sub.get(key) or []:
                    if branch.get("type") == "object":
                        walk(branch, path,
                             set(branch.get("required") or []))

    walk(schema, "", set(schema.get("required") or []))
    return found


def _null_navigate(record, path):
    """Return (container, leaf key) for a dotted matrix path;
    '[i]' steps index the list at position 0."""
    cur = record
    parts = path.split(".")
    for part in parts[:-1]:
        if part.endswith("[i]"):
            cur = cur[part[:-3]][0]
        else:
            cur = cur[part]
    return cur, parts[-1]


def _null_group():
    def draft_validator(value):
        return validate_script_plan_drafts(value, script())

    exercised = []
    for schema_name, path in NULL156_CASES:
        label = f"CF-P1-003-NULL156: {schema_name} {path}"
        special = _NULL_SPECIAL_BASELINES.get((schema_name, path), {})
        if schema_name == "script-to-performance" \
                and path == "project_id":
            # Not draft-carried: tested on the assembled record
            # inside a built bundle, with the hash recomputed so
            # only the field under test can fail validation.
            bundle = build()
            factory = lambda: clone(bundle["script_to_performance"])

            def validator(record, _bundle=bundle):
                probe = clone(_bundle)
                probe["script_to_performance"] = record
                probe["bundle_hash"] = script_to_performance_hash(probe)
                return validate_script_to_performance_bundle(probe)
        elif schema_name == "script-to-performance":
            factory = draft
            validator = draft_validator
        else:
            factory, validator = _NULL_BASELINES[schema_name]
        present_factory = special.get("present", factory)
        omitted_factory = special.get("omitted", factory)
        null_factory = special.get("null", factory)

        def with_present_value(record):
            if (schema_name, path) in _NULL_PRESENT_VALUES:
                container, leaf = _null_navigate(record, path)
                container[leaf] = clone(_NULL_PRESENT_VALUES[
                    (schema_name, path)])
            return record

        base = with_present_value(present_factory())
        check(f"{label} present with a valid value passes",
              validator(clone(base)) == [],
              f"errors={validator(clone(base))}")
        omitted = with_present_value(omitted_factory())
        container, leaf = _null_navigate(omitted, path)
        if leaf in container:
            del container[leaf]
        check(f"{label} omitted passes",
              validator(omitted) == [],
              f"errors={validator(omitted)}")
        nulled = with_present_value(null_factory())
        container, leaf = _null_navigate(nulled, path)
        container[leaf] = None
        errors = validator(nulled)
        check(f"{label} explicit null is rejected",
              errors != [],
              "explicit null was accepted")
        exercised.append((schema_name, path))

    discovered = set()
    for schema_name in ("script-contract", "script-to-performance",
                        "scene-plan", "shot-plan", "performance-plan",
                        "production-profile"):
        schema = json.load(open(os.path.join(
            ROOT, "schemas", f"{schema_name}.json")))
        for path in _null_optional_schema_paths(schema):
            discovered.add((schema_name, path))
    check("CF-P1-003-NULL156: declared matrix covers exactly the "
          "optional schema paths",
          set(exercised) == discovered
          and len(NULL156_CASES) == 156 and len(exercised) == 156,
          f"declared={len(NULL156_CASES)} exercised={len(exercised)} "
          f"discovered={len(discovered)} "
          f"missing={sorted(discovered - set(exercised))} "
          f"extra={sorted(set(exercised) - discovered)}")


# ---------------------------------------------------------------------------
# CF-P1-003-R1-BUNDLE-SHAPE: strict bundle shape validation (Task A).
# Every required bundle field is validated for BOTH presence AND
# correct type. A required record replaced by None, a list or a
# scalar must fail even when the bundle hash is recomputed — the
# test proves structural validation, not hash mismatch, rejects
# the bundle.
# ---------------------------------------------------------------------------

def _bundle_shape_group():
    session = fresh_session()
    plan = fresh_routing_plan(session)
    bundle = build(session=session, plan=plan)
    check("CF-P1-003-R1-BUNDLE-SHAPE: the valid bundle validates",
          validate_script_to_performance_bundle(bundle) == [])

    def rehash(mutated):
        probe = clone(mutated)
        probe["bundle_hash"] = script_to_performance_hash(probe)
        return probe

    for field in ("script_contract", "production_profile",
                  "script_to_performance", "scene_plan", "shot_plan",
                  "performance_plan"):
        for bad in (None, ["not", "an", "object"]):
            probe = clone(bundle)
            probe[field] = bad
            probe = rehash(probe)
            check(f"CF-P1-003-R1-BUNDLE-SHAPE: {field}={bad!r} "
                  "fails even with a recomputed hash",
                  validate_script_to_performance_bundle(probe) != [])
    for field, bad in (
            ("script_contract", "scalar"),
            ("production_profile", 42),
            ("script_to_performance", "scalar"),
            ("scene_plan", 42),
            ("shot_plan", True),
            ("performance_plan", 3.5)):
        probe = clone(bundle)
        probe[field] = bad
        probe = rehash(probe)
        check(f"CF-P1-003-R1-BUNDLE-SHAPE: {field}={bad!r} "
              "fails even with a recomputed hash",
              validate_script_to_performance_bundle(probe) != [])

    # Scalar top-level IDs: present but null or incorrectly typed.
    for field, bad in (
            ("bundle_id", None), ("bundle_id", ["bad"]), ("bundle_id", 42),
            ("session_id", None), ("session_id", 42), ("session_id", ["x"]),
            ("routing_plan_id", None), ("routing_plan_id", 42),
            ("routing_plan_id", {"x": 1}),
            ("bundle_hash", None), ("bundle_hash", "not-a-hash"),
            ("bundle_hash", 42), ("bundle_hash", ["x"])):
        probe = clone(bundle)
        probe[field] = bad
        check(f"CF-P1-003-R1-BUNDLE-SHAPE: {field}={bad!r} fails",
              validate_script_to_performance_bundle(probe) != [])

    # Missing required fields still fail.
    probe = clone(bundle)
    del probe["bundle_hash"]
    check("CF-P1-003-R1-BUNDLE-SHAPE: missing bundle_hash fails",
          validate_script_to_performance_bundle(probe) != [])
    probe = clone(bundle)
    del probe["scene_plan"]
    check("CF-P1-003-R1-BUNDLE-SHAPE: missing scene_plan fails",
          validate_script_to_performance_bundle(probe) != [])
    probe = clone(bundle)
    del probe["bundle_id"]
    check("CF-P1-003-R1-BUNDLE-SHAPE: missing bundle_id fails",
          validate_script_to_performance_bundle(probe) != [])


# ---------------------------------------------------------------------------
# CF-P1-003-R1-FAIL-CLOSED: total fail-closed input validation
# (Task B). Schema-invalid JSON-shaped input must never leak a raw
# Python implementation exception from a public validation function;
# the builder must convert invalid input into
# ScriptToPerformanceError. Each invalid case must fail at the
# correct validation boundary.
# ---------------------------------------------------------------------------

def _no_crash_returns_errors(label, fn):
    """A public validator called with malformed input must return a
    non-empty structured error list — never raise."""
    try:
        errors = fn()
    except Exception as exc:  # noqa: BLE001 - the test asserts no raise
        check(label, False, f"raised {type(exc).__name__}: {exc}")
        return []
    check(label, isinstance(errors, list) and errors != [],
          "validator returned no errors")
    return errors


def _build_fails_structured(label, **kwargs):
    """Like build_fails, but a raw implementation exception leaking
    out of the builder fails the check instead of crashing the
    suite — the boundary under test."""
    try:
        build(**kwargs)
    except ScriptToPerformanceError as exc:
        check(label, True)
        return exc.errors
    except Exception as exc:  # noqa: BLE001 - the test asserts no raise
        check(label, False, f"raised {type(exc).__name__}: {exc}")
        return []
    check(label, False, "bundle built instead of refusing")
    return []


def _fail_closed_group():
    session = fresh_session()
    plan = fresh_routing_plan(session)

    # The two independently reproduced crashes.
    bad = script()
    bad["dialogue"][0]["line_id"] = []
    _no_crash_returns_errors(
        "CF-P1-003-R1-FAIL-CLOSED: dialogue line_id as a list does "
        "not crash validate_script_contract",
        lambda: validate_script_contract(bad))
    bad = scene_plan()
    bad["scenes"][0]["scene_id"] = {}
    _no_crash_returns_errors(
        "CF-P1-003-R1-FAIL-CLOSED: scene_id as a dict does not "
        "crash validate_scene_plan",
        lambda: validate_scene_plan(bad))
    bad = draft()
    bad["scene_plan"]["scenes"][0]["scene_id"] = []
    _build_fails_structured(
        "CF-P1-003-R1-FAIL-CLOSED: build with scene_id as a list "
        "raises ScriptToPerformanceError, not TypeError",
        session=session, plan=plan, drf=bad)

    # Malformed identifiers at every boundary.
    for label, fn in (
            ("script dialogue line_id as a dict",
             lambda: validate_script_contract(_mut(script(), (
                 ("dialogue", 0, "line_id", {}))))),
            ("script shot_id as a list",
             lambda: validate_script_contract(_mut(script(), (
                 ("shots", 0, "shot_id", []))))),
            ("scene beat_id as a dict",
             lambda: validate_scene_plan(_mut(scene_plan(), (
                 ("scenes", 0, "beats", 0, "beat_id", {}))))),
            ("shot shot_id as a list",
             lambda: validate_shot_plan(_mut(shot_plan(), (
                 ("shots", 0, "shot_id", []))))),
            ("performance line_id as a dict",
             lambda: validate_performance_plan(_mut(performance_plan(), (
                 ("lines", 0, "line_id", {}))))),
            ("performance dialogue_line_id as a list",
             lambda: validate_performance_plan(_mut(performance_plan(), (
                 ("lines", 0, "dialogue_line_id", []))))),
            ("scene subject character_id as a list",
             lambda: validate_scene_plan(_mut(scene_plan(), (
                 ("scenes", 0, "subjects", 0, "character_id", []))))),
            ("shot subject character_id as a dict",
             lambda: validate_shot_plan(_mut(shot_plan(), (
                 ("shots", 0, "subjects", 0, "character_id", {})))))):
        _no_crash_returns_errors(
            f"CF-P1-003-R1-FAIL-CLOSED: {label} returns structured "
            "errors, never a raw exception", fn)

    # Malformed project IDs (agreement + _agreed_project_id).
    for label, fn in (
            ("script project_id as a list",
             lambda: validate_script_contract(_mut(script(), (
                 ("project_id", []))))),
            ("profile project_id as a dict",
             lambda: validate_production_profile(_mut(profile(), (
                 ("project_id", {}))))),
            ("scene plan project_id as a list",
             lambda: validate_scene_plan(_mut(scene_plan(), (
                 ("project_id", []))))),
            ("shot plan project_id as a dict",
             lambda: validate_shot_plan(_mut(shot_plan(), (
                 ("project_id", {}))))),
            ("performance plan project_id as a list",
             lambda: validate_performance_plan(_mut(performance_plan(), (
                 ("project_id", [])))))):
        _no_crash_returns_errors(
            f"CF-P1-003-R1-FAIL-CLOSED: {label} returns structured "
            "errors, never a raw exception", fn)
    bad = profile()
    bad["project_id"] = []
    _build_fails_structured(
        "CF-P1-003-R1-FAIL-CLOSED: build with a list project_id "
        "raises ScriptToPerformanceError, not TypeError",
        session=session, plan=plan, prof=bad)

    # Malformed schema versions.
    for label, fn in (
            ("scene plan schema_version as a list",
             lambda: validate_scene_plan(_mut(scene_plan(), (
                 ("schema_version", []))))),
            ("shot plan schema_version as a dict",
             lambda: validate_shot_plan(_mut(shot_plan(), (
                 ("schema_version", {}))))),
            ("performance plan schema_version as a number",
             lambda: validate_performance_plan(_mut(performance_plan(), (
                 ("schema_version", 42))))),
            ("script schema_version as a list",
             lambda: validate_script_contract(_mut(script(), (
                 ("schema_version", [])))))):
        _no_crash_returns_errors(
            f"CF-P1-003-R1-FAIL-CLOSED: {label} returns structured "
            "errors, never a raw exception", fn)
    bad = draft()
    bad["scene_plan"]["schema_version"] = []
    _build_fails_structured(
        "CF-P1-003-R1-FAIL-CLOSED: build with a list schema_version "
        "raises ScriptToPerformanceError, not TypeError",
        session=session, plan=plan, drf=bad)

    # Malformed subject dimensions (contradiction detection must not
    # use an unhashable value as a dict key).
    for label, fn in (
            ("scene subject subject_kind as a list",
             lambda: validate_scene_plan(_mut(scene_plan(), (
                 ("scenes", 0, "subjects", 0, "subject_kind", []))))),
            ("shot subject representation as a dict",
             lambda: validate_shot_plan(_mut(shot_plan(), (
                 ("shots", 0, "subjects", 0, "representation", {}))))),
            ("profile per-subject subject_kind as a list",
             lambda: validate_production_profile(_mut(profile(), (
                 ("per_subject_overrides", 0, "subject_kind", []))))),
            ("profile per-subject representation as a dict",
             lambda: validate_production_profile(_mut(profile(), (
                 ("per_subject_overrides", 0, "representation", {})))))):
        _no_crash_returns_errors(
            f"CF-P1-003-R1-FAIL-CLOSED: {label} returns structured "
            "errors, never a raw exception", fn)
    bad = draft()
    bad["shot_plan"]["shots"][0]["subjects"][0]["subject_kind"] = []
    _build_fails_structured(
        "CF-P1-003-R1-FAIL-CLOSED: build with a list subject_kind "
        "in a shot subject raises ScriptToPerformanceError, not "
        "TypeError",
        session=session, plan=plan, drf=bad)

    # Malformed articulation values and species values.
    for label, fn in (
            ("performance articulation_target as a list",
             lambda: validate_performance_plan(_mut(performance_plan(), (
                 ("lines", 0, "articulation_target",
                  ["human-mouth-lips"]))))),
            ("scene subject articulation_target as a dict",
             lambda: validate_scene_plan(_mut(scene_plan(), (
                 ("scenes", 0, "subjects", 0, "articulation_target",
                  {}))))),
            ("performance species as a list",
             lambda: validate_performance_plan(_mut(performance_plan(), (
                 ("lines", 0, "species", ["parrot"]))))),
            ("scene subject species as a dict",
             lambda: validate_scene_plan(_mut(scene_plan(), (
                 ("scenes", 0, "subjects", 0, "species", {}))))),
            ("performance subject_kind as a list",
             lambda: validate_performance_plan(_mut(performance_plan(), (
                 ("lines", 0, "subject_kind", [])))))):
        _no_crash_returns_errors(
            f"CF-P1-003-R1-FAIL-CLOSED: {label} returns structured "
            "errors, never a raw exception", fn)
    bad = draft()
    bad["performance_plan"]["lines"][0]["articulation_target"] = \
        ["human-mouth-lips"]
    _build_fails_structured(
        "CF-P1-003-R1-FAIL-CLOSED: build with a list "
        "articulation_target raises ScriptToPerformanceError, not "
        "TypeError",
        session=session, plan=plan, drf=bad)

    # Malformed live-action provenance fields.
    for label, fn in (
            ("profile production_medium as a list with the flag true",
             lambda: validate_production_profile(_mut(profile(),
                 ("production_medium", ["ai-digital-human"]),
                 ("is_live_action_footage", True)))),
            ("profile visual_style as a dict with the flag true",
             lambda: validate_production_profile(_mut(profile(),
                 ("visual_style", {}),
                 ("is_live_action_footage", True)))),
            ("profile per-subject representation as a list with the "
             "flag true",
             lambda: validate_production_profile(_mut(profile(),
                 ("per_subject_overrides", 0, "representation", []),
                 ("per_subject_overrides", 0, "is_live_action_footage",
                  True)))),
            ("scene subject representation as a list with the flag "
             "true",
             lambda: validate_scene_plan(_mut(scene_plan(),
                 ("scenes", 0, "subjects", 0, "representation", []),
                 ("scenes", 0, "subjects", 0, "is_live_action_footage",
                  True)))),
            ("shot subject representation as a dict with the flag "
             "true",
             lambda: validate_shot_plan(_mut(shot_plan(),
                 ("shots", 0, "subjects", 0, "representation", {}),
                 ("shots", 0, "subjects", 0, "is_live_action_footage",
                  True))))):
        _no_crash_returns_errors(
            f"CF-P1-003-R1-FAIL-CLOSED: {label} returns structured "
            "errors, never a raw exception", fn)
    bad = profile()
    bad["production_medium"] = ["ai-digital-human"]
    bad["is_live_action_footage"] = True
    _build_fails_structured(
        "CF-P1-003-R1-FAIL-CLOSED: build with a list "
        "production_medium raises ScriptToPerformanceError, not "
        "TypeError",
        session=session, plan=plan, prof=bad)

    # Malformed voice-binding / reaction-hold references.
    bad = draft()
    bad["character_voice_binding"]["shot_id"] = ["sh-01"]
    _build_fails_structured(
        "CF-P1-003-R1-FAIL-CLOSED: build with a list binding "
        "shot_id raises ScriptToPerformanceError, not TypeError",
        session=session, plan=plan, drf=bad)
    bad = draft()
    bad["editing_plan"]["reaction_holds"][0]["after_line_id"] = {"x": 1}
    _build_fails_structured(
        "CF-P1-003-R1-FAIL-CLOSED: build with a dict reaction-hold "
        "after_line_id raises ScriptToPerformanceError, not "
        "TypeError",
        session=session, plan=plan, drf=bad)


def _mut(record, *steps):
    """Apply (path..., value) mutations to a cloned record. Each
    step is a tuple of path segments ending in the new value; a
    segment that is an int indexes a list, otherwise a dict key."""
    value = clone(record)
    for step in steps:
        *path, new = step
        cur = value
        for part in path[:-1]:
            cur = cur[part]
        cur[path[-1]] = new
    return value


# ---------------------------------------------------------------------------
# CF-P1-003-R1-DIALOGUE-META: source dialogue metadata preservation
# (Task C). When the source line supplies a character_id or a
# language, the Performance Plan line must carry the SAME value.
# Missing or mismatched supplied metadata fails closed; nothing is
# invented and nothing is translated.
# ---------------------------------------------------------------------------

def _dialogue_meta_group():
    session = fresh_session()
    plan = fresh_routing_plan(session)
    built = build(session=session, plan=plan)
    check("CF-P1-003-R1-DIALOGUE-META: correct character ID and "
          "language preserved builds",
          built["performance_plan"]["lines"][0]["character_id"]
          == "char-001"
          and built["performance_plan"]["lines"][0]["language"] == "en")

    bad = draft()
    del bad["performance_plan"]["lines"][0]["character_id"]
    build_fails("CF-P1-003-R1-DIALOGUE-META: character ID omitted "
                "from the Performance Plan fails",
                session=session, plan=plan, drf=bad)
    bad = draft()
    bad["performance_plan"]["lines"][0]["character_id"] = "char-kiki-001"
    build_fails("CF-P1-003-R1-DIALOGUE-META: character ID mismatch "
                "fails", session=session, plan=plan, drf=bad)
    bad = draft()
    bad["performance_plan"]["lines"][0]["character_id"] = ["char-001"]
    build_fails("CF-P1-003-R1-DIALOGUE-META: character ID as a "
                "list fails", session=session, plan=plan, drf=bad)
    bad = draft()
    del bad["performance_plan"]["lines"][0]["language"]
    build_fails("CF-P1-003-R1-DIALOGUE-META: source language "
                "omitted from the Performance Plan fails",
                session=session, plan=plan, drf=bad)
    bad = draft()
    bad["performance_plan"]["lines"][0]["language"] = "bn"
    build_fails("CF-P1-003-R1-DIALOGUE-META: source language "
                "mismatch fails (no implicit translation)",
                session=session, plan=plan, drf=bad)
    bad = draft()
    bad["performance_plan"]["lines"][0]["language"] = ["en"]
    build_fails("CF-P1-003-R1-DIALOGUE-META: language as a list "
                "fails", session=session, plan=plan, drf=bad)

    # No metadata supplied by the source means no metadata is
    # required: the rule only preserves what the source supplies,
    # it never invents a requirement.
    scr = script()
    del scr["dialogue"][0]["character_id"]
    del scr["dialogue"][0]["language"]
    drf = draft()
    del drf["performance_plan"]["lines"][0]["character_id"]
    del drf["performance_plan"]["lines"][0]["language"]
    check("CF-P1-003-R1-DIALOGUE-META: a source line without "
          "character_id or language builds without them",
          build(session=session, plan=plan, scr=scr,
                drf=drf)["performance_plan"]["lines"][0].get(
                    "character_id") is None)
    # The second line keeps its metadata, so the rule still binds
    # it.
    check("CF-P1-003-R1-DIALOGUE-META: the untouched second line "
          "still carries its metadata",
          build(session=session, plan=plan, scr=scr,
                drf=drf)["performance_plan"]["lines"][1]["language"]
          == "en")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main():
    _session_routing_group()
    _script_group()
    _plans_group()
    _dialogue_group()
    _xref_group()
    _determinism_group()
    _null_group()
    _bundle_shape_group()
    _fail_closed_group()
    _dialogue_meta_group()
    total = 0
    if failures:
        print(f"\n{len(failures)} FAILURES:")
        for name in failures:
            print(f"  FAIL {name}")
        return 1
    print("\nAll script-to-performance runtime checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
