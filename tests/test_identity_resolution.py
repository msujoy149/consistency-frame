#!/usr/bin/env python3
"""Identity resolution tests (CF-WO-P1-004-R1-ADDENDUM-IDENTITY, Task P).

Covers all 45 listed cases: name/ID resolution (P01–P08),
selection policy (P09–P15), image/video binding (P16–P23),
voice resolution (P24–P34), multi-character/continuity
(P35–P40), registration/privacy (P41–P45). Every case asserts
actual packet/snapshot contents, not only schema labels or
status flags. Valid AND invalid fixtures are both exercised.

Test identities are synthetic fixtures named by the work order
(Arif, Sarena, Mina, Rahim, Tania, a shopkeeper, a narrator).
They are test-only records with placeholder ownership and
have no relation to any real private registration.

Conventions follow tests/test_production_orchestrator.py:
check(name, cond, detail="") prints PASS/FAIL lines, failures
are collected, and the process exits 0 only when every check
passes. No test here weakens any P0, P1-001/002/003 or P1-004
check, and no test invents a provider capability (image/video
work has no verified provider and must compile as a handoff
with its identity bindings attached).
"""

import copy
import json
import os
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(__file__), "..")
ROOT_ABS = os.path.abspath(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import test_script_to_performance_runtime as T  # noqa: E402
from runtime import local_session  # noqa: E402
from runtime.local_session import (  # noqa: E402
    close_session, is_active_session, load_or_create_profile,
    start_session)
from runtime import identity_resolution as ir  # noqa: E402
from runtime import production_store as store  # noqa: E402
from runtime import task_compiler as tc  # noqa: E402
from runtime.production_orchestrator import (  # noqa: E402
    ProductionOrchestratorError, build_production_bundle,
    build_qc_correction_tasks, compile_provider_tasks,
    create_production_job, transition_job, validate_job)

failures = []
_checks = [0]
_sessions = []


def check(name, cond, detail=""):
    _checks[0] += 1
    if cond:
        print(f"PASS {name}")
    else:
        print(f"FAIL {name} {detail}")
        failures.append(name)


def clone(value):
    return json.loads(json.dumps(value))


def fresh_session():
    root = tempfile.mkdtemp(prefix="cf-p1-004-identity-test-")
    profile = load_or_create_profile(root)
    session = start_session(profile, profile.workspace_id)
    _sessions.append(session)
    return session


def fresh_profile_session():
    """(profile, session) for groups that need a second session
    from the same installation (for example store resume)."""
    root = tempfile.mkdtemp(prefix="cf-p1-004-identity-test-")
    profile = load_or_create_profile(root)
    session = start_session(profile, profile.workspace_id)
    _sessions.append(session)
    return profile, session


def load_fixture(name):
    with open(os.path.join(
            ROOT, "tests", "fixtures", name), encoding="utf-8") as f:
        return json.load(f)


def stamp_ownership(record, session):
    """Bind a fixture record's ownership to the test session's
    identity (the fixtures carry placeholder owner-a /
    workspace-a; the P0 voice rules need the requester to be
    the owning owner in the owning workspace)."""
    value = clone(record)
    value["ownership"] = {
        "owner_id": session.owner_id,
        "workspace_id": session.workspace_id,
        "visibility": "private",
        "sharing": "none",
    }
    return value


def registries(session):
    """(character_registry, voice_registry) stamped to the
    session's identity. Returns deep copies; the fixtures are
    never mutated."""
    characters = {}
    for record in load_fixture("identity-registry.json")["characters"]:
        stamped = stamp_ownership(record, session) \
            if "ownership" in record else clone(record)
        cid = stamped.get("character_id") or stamped.get("id")
        characters[cid] = stamped
    voices = {}
    for record in load_fixture("identity-voice-registry.json"):
        voices[record["voice_profile_id"]] = stamp_ownership(
            record, session)
    return characters, voices


def registry_subset(session, *character_ids):
    characters, voices = registries(session)
    return ({cid: characters[cid] for cid in character_ids},
            {vid: v for vid, v in voices.items()
             if v["character_id"] in character_ids})


def policy(policy_id="pol-mixed-001", mode="MIXED_REGISTERED_AND_NEW",
           selected=("char-001", "char-002", "char-003"), excluded=(),
           allow_new=True, is_default=False, override=False,
           approval="approved", project="proj-test-001"):
    return {
        "schema_version": "2.5",
        "policy_id": policy_id,
        "project_id": project,
        "mode": mode,
        "selected_character_ids": list(selected),
        "excluded_character_ids": list(excluded),
        "allow_new_task_local_characters": allow_new,
        "is_project_default": is_default,
        "per_job_override": override,
        "voice_selection_policy": {
            "selection_mode": "use-character-default",
        },
        "provenance": "EXPLICIT_FROM_USER",
        "registry_snapshot_version": "unversioned",
        "approval_status": approval,
        "version": 1,
    }


def shopkeeper_proposal(job_id="job-mixed-001"):
    return {
        "schema_version": "2.5",
        "proposal_id": "prop-shopkeeper-001",
        "character_ref": "shopkeeper",
        "project_id": "proj-test-001",
        "job_id": job_id,
        "role": "supporting",
        "status": "approved-for-job",
        "design_brief": "A cheerful shopkeeper in his fifties who "
                        "runs the riverside market stall. Warm, quick "
                        "with a joke, always wiping his hands on his "
                        "apron.",
        "appearance": {
            "face_structure": "broad friendly face, grey moustache",
            "hairstyle": "short grey hair under a flat cap",
            "body_proportions": "stocky, apron over a checked shirt",
            "distinctive_features": ["grey moustache",
                                     "a brass key on a cord"]},
        "clothing": ["a checked shirt", "a canvas apron"],
        "accessories": ["a brass key on a cord"],
        "personality": "Warm and quick with a joke.",
        "signature_colour": "market green",
        "visual_style": "stylized-3d",
        "expression_requirements": ["a broad smile",
                                    "a welcoming wave"],
        "reference_preparation": {
            "front_reference_required": True,
            "side_reference_required": True,
            "turnaround_required": True,
            "expression_sheet_required": True,
            "pose_references": ["weighing fish", "waving a customer in"]},
        "approved_reference_ids": ["ref-shopkeeper-front",
                                   "ref-shopkeeper-side"],
        "permanent_registration_requested": False,
        "provenance": "INFERRED_FOR_PRODUCTION",
    }


def narrator_proposal(job_id="job-mixed-001"):
    """A voice-only narrator: no visual references, no visual
    identity. The proposal carries no approved reference ids."""
    return {
        "schema_version": "2.5",
        "proposal_id": "prop-narrator-001",
        "character_ref": "narr-001",
        "project_id": "proj-test-001",
        "job_id": job_id,
        "role": "narrator",
        "status": "approved-for-job",
        "design_brief": "A warm off-screen narrator who opens and "
                        "closes the story. Voice only; never visible.",
        "appearance": {
            "face_structure": "not visible",
            "hairstyle": "not visible",
            "body_proportions": "not visible",
            "distinctive_features": []},
        "clothing": [],
        "accessories": [],
        "personality": "Warm, steady, unhurried.",
        "signature_colour": "not visible",
        "visual_style": "stylized-3d",
        "expression_requirements": [],
        "reference_preparation": {
            "front_reference_required": False,
            "side_reference_required": False,
            "turnaround_required": False,
            "expression_sheet_required": False,
            "pose_references": []},
        "approved_reference_ids": [],
        "permanent_registration_requested": False,
        "provenance": "INFERRED_FOR_PRODUCTION",
    }


def mixed_proposals(job_id="job-mixed-001"):
    return {"prop-shopkeeper-001": shopkeeper_proposal(job_id),
            "prop-narrator-001": narrator_proposal(job_id)}

# ---------------------------------------------------------------------------
# Mixed-cast S2P fixtures (Task K): Arif (char-001) + Sarena
# (char-002) registered, Mina (char-003) registered in scene 2,
# shopkeeper + narrator task-local. Two scenes, three shots, six
# dialogue lines (Arif speaks English and Bengali).
# ---------------------------------------------------------------------------

def _subject(character_id, eyeline=None):
    return {
        "character_id": character_id, "subject_kind": "digital-human",
        "representation": "ai-digital-human",
        "source_media": "reference-image",
        "rendering_style": "photorealistic-digital-human",
        "articulation_target": "human-mouth-lips", "species": "human",
        "motion_method": "face-animation",
        "is_live_action_footage": False,
        "position": "foreground", "scale": "life-size",
        "contact": "none",
        "continuity": "same outfit as the previous scene",
        **({"eyeline_target": eyeline} if eyeline else {}),
    }


def mixed_script():
    return {
        "schema_version": "2.3", "id": "script-test-001",
        "project_id": "proj-test-001",
        "dialogue_mode": "VERBATIM_SCRIPT",
        "version": 1,
        "dialogue": [
            {"line_id": "l-01", "character_id": "char-001",
             "text": "I will help. Let us go together.",
             "language": "en"},
            {"line_id": "l-02", "character_id": "char-002",
             "text": "আমি তোমার সঙ্গে যাব।", "language": "bn"},
            {"line_id": "l-03", "character_id": "shopkeeper",
             "text": "Fresh fish, straight from the river.",
             "language": "en"},
            {"line_id": "l-04", "character_id": "char-003",
             "text": "রাস্তা পরিষ্কার। আমরা যেতে পারি।",
             "language": "bn"},
            {"line_id": "l-05", "character_id": "narr-001",
             "text": "And so the journey began at dawn.",
             "language": "en"},
            {"line_id": "l-06", "character_id": "char-001",
             "text": "চলো, একসঙ্গে যাই।", "language": "bn"},
        ],
        "beats": ["b-01", "b-02", "b-03"],
        "shots": [
            {"shot_id": "sh-01", "duration_seconds": 4.5,
             "framing": "medium-close-up", "camera": "eye-level",
             "character_ids": ["char-001"]},
            {"shot_id": "sh-02", "duration_seconds": 5.0,
             "framing": "medium", "camera": "low",
             "character_ids": ["char-001", "char-002", "shopkeeper"]},
            {"shot_id": "sh-03", "duration_seconds": 4.0,
             "framing": "medium", "camera": "eye-level",
             "character_ids": ["char-001", "char-003"]},
        ],
        "performance_cues": ["steady breath before the decision"],
        "audio_plan": "morning birds, distant river, market sounds",
    }


def mixed_profile():
    overrides = []
    for cid in ("char-001", "char-002", "shopkeeper", "char-003"):
        overrides.append({
            "character_id": cid, "subject_kind": "digital-human",
            "representation": "ai-digital-human",
            "source_media": "reference-image",
            "rendering_style": "photorealistic-digital-human",
            "articulation_target": "human-mouth-lips", "species": "human",
            "motion_methods": ["face-animation",
                               "lip-sync-phoneme-viseme",
                               "body-animation"],
            "is_live_action_footage": False})
    return {
        "schema_version": "2.5", "production_profile_id": "prod-test-001",
        "name": "Test mixed registered and task-local cast",
        "project_id": "proj-test-001",
        "production_medium": "ai-digital-human",
        "visual_style": "photorealistic-digital-human",
        "source_media_type": "reference-image",
        "motion_methods": ["ai-image-to-video", "face-animation",
                           "lip-sync-phoneme-viseme", "body-animation"],
        "subject_types": ["digital-human"],
        "interaction_pattern": "multi-person-conversation",
        "is_live_action_footage": False,
        "version": 1, "status": "approved",
        "skill_profiles": ["skill-realistic-person",
                           "skill-voice-consistency"],
        "per_subject_overrides": overrides,
        "per_shot_overrides": [
            {"shot_id": "sh-01", "camera_movement": "static",
             "depth_of_field": "shallow", "focus_target": "char-001",
             "lighting": "soft morning light",
             "transition_to_next_shot": "cut"},
            {"shot_id": "sh-02", "camera_movement": "push-in",
             "depth_of_field": "deep", "focus_target": "char-002",
             "lighting": "same soft morning light",
             "transition_to_next_shot": "cut"},
            {"shot_id": "sh-03", "camera_movement": "static",
             "depth_of_field": "deep", "focus_target": "char-003",
             "lighting": "morning light on the road",
             "transition_to_next_shot": "cut"},
        ],
    }


def _perf_line(line_id, dialogue_line_id, character_id, text,
               language, emotion, lip_sync=True, speaking=True,
               primary=None):
    # primary_emotion is a fixed enum in the performance-plan
    # schema; the free-form delivery emotion lives in `emotion`.
    # The expression matcher reads `emotion` first.
    return {
        "line_id": line_id, "dialogue_line_id": dialogue_line_id,
        "character_id": character_id,
        "speaker_identity": f"{character_id}, test speaker",
        "dialogue": {"text": text, "rewrite_permitted": False},
        "lip_sync_required": lip_sync,
        "speaking_state": "speaking" if speaking else "listening",
        "articulation_target": "human-mouth-lips",
        "subject_kind": "digital-human", "species": "human",
        "language": language, "primary_emotion": primary or emotion,
        "secondary_emotion": "anticipation",
        "nuanced_emotion": emotion, "emotion": emotion,
        "emotion_intensity": 7,
        "facial_expression": "open, engaged",
        "micro_expressions": ["brief eyebrow lift"],
        "eye_movement": "glance toward the companion, then forward",
        "gaze": "other-character",
        "posture": "shoulders back, chin level",
        "gestures": ["one step forward"],
        "breathing": "one steadying breath before the line",
        "physical_behaviour": "weight shifts forward",
        "voice": {"emotion": emotion, "pitch": "moderate",
                  "pace": "natural", "pauses": []},
        "non_verbal_events": [{"type": "breathing",
                               "duration_seconds": 1.0, "intensity": 3}],
    }


def mixed_draft():
    scene_plan = {
        "schema_version": "2.4", "id": "scene-plan-test-001",
        "project_id": "proj-test-001",
        "scenes": [
            {"scene_id": "sc-01", "title": "The riverside market",
             "dramatic_intent": "Arif and Sarena meet the shopkeeper "
                                "and decide to go together.",
             "location_id": "loc-test-001",
             "character_ids": ["char-001", "char-002", "shopkeeper"],
             "visual_style_profile_id": "style-test-001",
             "subjects": [_subject("char-001", "char-002"),
                          _subject("char-002", "char-001"),
                          _subject("shopkeeper", "char-001")],
             "beats": [
                 {"beat_id": "b-01",
                  "description": "Arif hears the call and hesitates.",
                  "dramatic_intent": "Show doubt before the decision.",
                  "primary_emotion": "fear",
                  "secondary_emotion": "anticipation",
                  "emotion_intensity": 5,
                  "emotion_transition": "worry -> determination",
                  "nuanced_emotion": "worry",
                  "non_verbal_events": [{"type": "silence",
                                         "duration_seconds": 1.5,
                                         "intensity": 4}]},
                 {"beat_id": "b-02",
                  "description": "Sarena agrees and the shopkeeper "
                                 "wishes them well.",
                  "dramatic_intent": "The decision lands.",
                  "primary_emotion": "trust",
                  "secondary_emotion": "anticipation",
                  "emotion_intensity": 8,
                  "emotion_transition": "determination holds",
                  "nuanced_emotion": "determination"},
             ]},
            {"scene_id": "sc-02", "title": "The clear road",
             "dramatic_intent": "Mina joins them on the road; the "
                                "narrator opens the next chapter.",
             "location_id": "loc-test-002",
             "character_ids": ["char-001", "char-003"],
             "visual_style_profile_id": "style-test-001",
             "subjects": [_subject("char-001", "char-003"),
                          _subject("char-003", "char-001")],
             "beats": [
                 {"beat_id": "b-03",
                  "description": "Mina says the road is clear.",
                  "dramatic_intent": "The group sets off.",
                  "primary_emotion": "trust",
                  "secondary_emotion": "joy",
                  "emotion_intensity": 7,
                  "emotion_transition": "determination holds",
                  "nuanced_emotion": "determination"},
             ]},
        ],
    }
    shot_plan = {
        "schema_version": "2.4", "id": "shot-plan-test-001",
        "project_id": "proj-test-001",
        "scene_plan_id": "scene-plan-test-001",
        "shots": [
            {"shot_id": "sh-01", "scene_id": "sc-01", "beat_id": "b-01",
             "framing": "medium-close-up",
             "shot_size": "medium-close-up",
             "camera_angle": "eye-level", "angle": "eye-level",
             "camera_height": "eye-level", "camera_movement": "static",
             "focus_target": "char-001",
             "lens_intent": "long lens to isolate the speaker",
             "lighting": "soft morning light from the left",
             "duration_seconds": 4.5,
             "action": "Arif turns toward the sound.",
             "character_ids": ["char-001"],
             "subjects": [_subject("char-001")],
             "transition_to_next_shot": "cut"},
            {"shot_id": "sh-02", "scene_id": "sc-01", "beat_id": "b-02",
             "framing": "medium", "shot_size": "medium",
             "camera_angle": "low", "angle": "low",
             "camera_height": "ground-level",
             "camera_movement": "dolly", "focus_target": "char-002",
             "lens_intent": "wide lens to hold all three characters",
             "lighting": "same soft morning light, slightly brighter",
             "duration_seconds": 5.0,
             "action": "Sarena steps forward; the shopkeeper waves.",
             "character_ids": ["char-001", "char-002", "shopkeeper"],
             "subjects": [_subject("char-001", "char-002"),
                          _subject("char-002", "char-001"),
                          _subject("shopkeeper", "char-001")],
             "transition_to_next_shot": "cut"},
            {"shot_id": "sh-03", "scene_id": "sc-02", "beat_id": "b-03",
             "framing": "medium", "shot_size": "medium",
             "camera_angle": "eye-level", "angle": "eye-level",
             "camera_height": "eye-level", "camera_movement": "static",
             "focus_target": "char-003",
             "lens_intent": "wide lens to hold both characters",
             "lighting": "morning light on the road",
             "duration_seconds": 4.0,
             "action": "Mina points down the clear road.",
             "character_ids": ["char-001", "char-003"],
             "subjects": [_subject("char-001", "char-003"),
                          _subject("char-003", "char-001")],
             "transition_to_next_shot": "cut"},
        ],
    }
    performance_plan = {
        "schema_version": "2.4", "id": "performance-plan-test-001",
        "project_id": "proj-test-001", "dialogue_mode": "VERBATIM_SCRIPT",
        "lines": [
            _perf_line("l-01", "d-01", "char-001",
                       "I will help. Let us go together.", "en",
                       "trust"),
            _perf_line("l-02", "d-02", "char-002",
                       "আমি তোমার সঙ্গে যাব।", "bn", "trust"),
            _perf_line("l-03", "d-03", "shopkeeper",
                       "Fresh fish, straight from the river.", "en",
                       "joy"),
            _perf_line("l-04", "d-04", "char-003",
                       "রাস্তা পরিষ্কার। আমরা যেতে পারি।", "bn",
                       "trust"),
            _perf_line("l-05", "d-05", "narr-001",
                       "And so the journey began at dawn.", "en",
                       "calm", lip_sync=False, primary="neutral"),
            _perf_line("l-06", "d-06", "char-001",
                       "চলো, একসঙ্গে যাই।", "bn", "determination",
                       primary="trust"),
        ],
    }
    return {
        "scene_plan": scene_plan,
        "shot_plan": shot_plan,
        "performance_plan": performance_plan,
        "audio_plan": {
            "ambience": [{"cue": "morning birds, distant river",
                          "timing": "sc-01 throughout"},
                         {"cue": "market sounds",
                          "timing": "sc-01, shot sh-02"}],
            "music": [{"cue": "gentle strings rise under the decision",
                       "timing": "sc-01, beat b-02"}],
            "sfx": [{"cue": "soft footstep on dry leaves",
                     "timing": "sh-02"}]},
        "editing_plan": {
            "rhythm": "slow hold on the hesitation, quicker cut on the "
                      "decision",
            "reaction_holds": [{"after_line_id": "l-01",
                                "hold_seconds": 1.5,
                                "purpose": "let the decision land"}]},
        "character_voice_binding": {
            "character_id": "char-001", "dialogue_line_id": "d-01",
            "voice_profile_id": "voice-arif-en-001",
            "audio_asset_id": "audio-arif-l01",
            "reference_asset_ids": ["asset-arif-001"], "shot_id": "sh-01",
            "speaking_state": "speaking", "emotion": "warm determination",
            "delivery": "warm, unhurried",
            "articulation": "human-mouth-lips"},
        "character_voice_bindings": [
            {"character_id": "char-002", "dialogue_line_id": "d-02",
             "voice_profile_id": "voice-sarena-bn-001",
             "audio_asset_id": "audio-sarena-l02",
             "reference_asset_ids": ["asset-sarena-001"],
             "shot_id": "sh-02", "speaking_state": "speaking",
             "emotion": "warm", "delivery": "warm, unhurried",
             "articulation": "human-mouth-lips"},
            {"character_id": "shopkeeper", "dialogue_line_id": "d-03",
             "voice_profile_id": "voice-shopkeeper-001",
             "audio_asset_id": "audio-shopkeeper-l03",
             "reference_asset_ids": ["asset-shopkeeper-001"],
             "shot_id": "sh-02", "speaking_state": "speaking",
             "emotion": "cheerful", "delivery": "brisk, friendly",
             "articulation": "human-mouth-lips"},
            {"character_id": "char-003", "dialogue_line_id": "d-04",
             "voice_profile_id": "voice-mina-bn-001",
             "audio_asset_id": "audio-mina-l04",
             "reference_asset_ids": ["asset-mina-001"],
             "shot_id": "sh-03", "speaking_state": "speaking",
             "emotion": "calm", "delivery": "steady",
             "articulation": "human-mouth-lips"},
            {"character_id": "narr-001", "dialogue_line_id": "d-05",
             "voice_profile_id": "voice-narrator-001",
             "audio_asset_id": "audio-narrator-l05",
             "reference_asset_ids": ["asset-narrator-001"],
             "speaking_state": "speaking", "emotion": "calm",
             "delivery": "warm, steady, unhurried",
             "articulation": "human-mouth-lips"},
            {"character_id": "char-001", "dialogue_line_id": "d-06",
             "voice_profile_id": "voice-arif-bn-001",
             "audio_asset_id": "audio-arif-l06",
             "reference_asset_ids": ["asset-arif-001"],
             "shot_id": "sh-03", "speaking_state": "speaking",
             "emotion": "determination", "delivery": "firm",
             "articulation": "human-mouth-lips"},
        ],
    }


def mixed_analysis():
    return {
        "schema_version": "2.5", "id": "analysis-mixed-001",
        "project_id": "proj-test-001",
        "script_contract_id": "script-test-001",
        "premise": "Arif and Sarena meet the shopkeeper at the "
                   "riverside market, decide to go together, and set "
                   "off down the clear road with Mina.",
        "narrative_structure": "three-act",
        "format_profile": {"delivery_profile": "short-form-15-60s",
                           "duration_target_seconds": 120},
        "dialogue_preservation": {
            "source_dialogue_line_count": 6, "mapped_line_count": 6,
            "rewrite_requested": False,
            "notes": "All six source lines map one-to-one."},
        "character_resolutions": [
            {"character_ref": "char-001", "resolution": "approved",
             "registered_character_id": "char-001",
             "role": "protagonist",
             "provenance": "FROM_APPROVED_PROJECT_CANON",
             "cast_class": "VISIBLE_CHARACTER",
             "scene_ids": ["sc-01", "sc-02"]},
            {"character_ref": "char-002", "resolution": "approved",
             "registered_character_id": "char-002",
             "role": "supporting",
             "provenance": "FROM_APPROVED_PROJECT_CANON",
             "cast_class": "VISIBLE_CHARACTER",
             "scene_ids": ["sc-01"]},
            {"character_ref": "shopkeeper",
             "resolution": "task-local-proposal",
             "proposal_id": "prop-shopkeeper-001",
             "role": "supporting",
             "provenance": "INFERRED_FOR_PRODUCTION",
             "cast_class": "VISIBLE_CHARACTER",
             "scene_ids": ["sc-01"]},
            {"character_ref": "char-003", "resolution": "approved",
             "registered_character_id": "char-003",
             "role": "supporting",
             "provenance": "FROM_APPROVED_PROJECT_CANON",
             "cast_class": "VISIBLE_CHARACTER",
             "scene_ids": ["sc-02"]},
            {"character_ref": "narr-001",
             "resolution": "task-local-proposal",
             "proposal_id": "prop-narrator-001",
             "role": "narrator",
             "provenance": "INFERRED_FOR_PRODUCTION",
             "cast_class": "NARRATOR_OR_VOICE_OVER",
             "scene_ids": ["sc-02"]},
        ],
        "scenes": [
            {"scene_id": "sc-01",
             "character_refs": ["char-001", "char-002", "shopkeeper"],
             "location_brief": "A riverside market at soft morning "
                               "light.",
             "purpose": "Arif and Sarena decide to go together.",
             "time_of_day": "morning",
             "transition_to_next": "cut",
             "provenance": "EXPLICIT_FROM_USER",
             "beats": [
                 {"beat_id": "b-01",
                  "description": "Arif hears the call and hesitates.",
                  "provenance": "EXPLICIT_FROM_USER"},
                 {"beat_id": "b-02",
                  "description": "Sarena agrees; the shopkeeper "
                                 "wishes them well.",
                  "provenance": "EXPLICIT_FROM_USER"}]},
            {"scene_id": "sc-02",
             "character_refs": ["char-001", "char-003"],
             "location_brief": "A clear road out of the village.",
             "purpose": "Mina joins them; the narrator opens the "
                        "next chapter.",
             "time_of_day": "morning",
             "transition_to_next": "cut",
             "provenance": "EXPLICIT_FROM_USER",
             "beats": [
                 {"beat_id": "b-03",
                  "description": "Mina says the road is clear.",
                  "provenance": "EXPLICIT_FROM_USER"}]},
        ],
        "emotional_progression": [
            {"beat_id": "b-01", "emotion": "fear", "intensity": 5,
             "provenance": "EXPLICIT_FROM_USER"},
            {"beat_id": "b-02", "emotion": "trust", "intensity": 8,
             "provenance": "INFERRED_FOR_PRODUCTION"},
            {"beat_id": "b-03", "emotion": "trust", "intensity": 7,
             "provenance": "INFERRED_FOR_PRODUCTION"}],
        "pacing": {
            "opening": "A call from the riverbank; Arif hesitates.",
            "ending": "The group sets off down the clear road.",
            "provenance": "EXPLICIT_FROM_USER"},
        "shot_direction": [
            {"shot_id": "sh-01", "scene_id": "sc-01",
             "angle": "eye-level", "size": "medium-close-up",
             "movement": "static",
             "lighting_intent": "Soft morning light from the left.",
             "purpose": "Hold on Arif's hesitation.",
             "provenance": "INFERRED_FOR_PRODUCTION"},
            {"shot_id": "sh-02", "scene_id": "sc-01",
             "angle": "low", "size": "medium", "movement": "dolly",
             "lighting_intent": "Same soft morning light.",
             "purpose": "Three characters in one frame; the decision "
                        "lands.",
             "provenance": "INFERRED_FOR_PRODUCTION"},
            {"shot_id": "sh-03", "scene_id": "sc-02",
             "angle": "eye-level", "size": "medium",
             "movement": "static",
             "lighting_intent": "Morning light on the road.",
             "purpose": "Mina joins the group.",
             "provenance": "INFERRED_FOR_PRODUCTION"},
        ],
        "sound_direction": [
            {"cue_type": "ambience",
             "intent": "Morning birds and a distant river.",
             "provenance": "INFERRED_FOR_PRODUCTION",
             "scene_id": "sc-01"},
            {"cue_type": "music",
             "intent": "Gentle strings rise under the decision.",
             "provenance": "INFERRED_FOR_PRODUCTION",
             "scene_id": "sc-01"},
            {"cue_type": "intentional-silence",
             "intent": "A beat of silence after the decision.",
             "provenance": "INFERRED_FOR_PRODUCTION",
             "scene_id": "sc-01"},
        ],
        "open_questions": [],
        "notes": "Mixed-cast fixture: two registered leads, one "
                 "registered scene-2 character, one task-local "
                 "shopkeeper, one voice-only narrator.",
    }


def mixed_bundle(session):
    plan = T.fresh_routing_plan(session)
    return T.build_script_to_performance_bundle(
        session, plan, mixed_script(), mixed_profile(), mixed_draft(),
        "s2p-mixed-001", False)


def mixed_job(session, job_id="job-mixed-001", policy_value=None,
              bundle_id="bundle-mixed-001", **job_flags):
    """Full orchestrator path for the mixed cast: job in ANALYZING
    with the policy, bundle built with the stamped registries,
    snapshot stored on the job. Returns (bundle, job)."""
    characters, voices = registries(session)
    job = create_production_job(
        session, job_id, "proj-test-001",
        {"delivery_profile": "short-form-15-60s"},
        identity_policy=policy_value if policy_value is not None
        else policy(), **job_flags)
    job = transition_job(session, job, "ANALYZING")
    bundle, job = build_production_bundle(
        session, job, T.fresh_routing_plan(session),
        mixed_script(), mixed_profile(), mixed_draft(),
        mixed_analysis(), bundle_id,
        identity_policy=policy_value if policy_value is not None
        else policy(),
        character_registry=characters, voice_registry=voices,
        proposals=list(mixed_proposals(job_id).values()))
    return bundle, job

# ---------------------------------------------------------------------------
# P01–P08: name / ID resolution (Task D)
# ---------------------------------------------------------------------------

def _resolution_group():
    session = fresh_session()
    characters, _voices = registries(session)

    resolved = ir.resolve_character_reference(
        selector={"character_id": "char-001"}, registry=characters)
    check("CF-P1-004-R1-IDENTITY-P01: resolve by unique id",
          resolved["character_id"] == "char-001"
          and resolved["matched_by"] == "id"
          and resolved["record"]["display_name"] == "Arif",
          f"got {resolved}")

    resolved = ir.resolve_character_reference(
        selector={"name": "Mina"}, registry=characters)
    check("CF-P1-004-R1-IDENTITY-P02: resolve by unique name",
          resolved["character_id"] == "char-003"
          and resolved["matched_by"] == "name",
          f"got {resolved}")

    resolved = ir.resolve_character_reference(
        selector={"character_id": "char-002", "name": "Sarena"},
        registry=characters)
    check("CF-P1-004-R1-IDENTITY-P03: resolve by name and id together",
          resolved["character_id"] == "char-002"
          and resolved["matched_by"] == "id-and-name",
          f"got {resolved}")

    try:
        ir.resolve_character_reference(
            selector={"name": "Arif"}, registry=characters)
        check("CF-P1-004-R1-IDENTITY-P04: duplicate name needs the id",
              False, "ambiguous name resolved instead of refusing")
    except ir.IdentityResolutionError as exc:
        check("CF-P1-004-R1-IDENTITY-P04: duplicate name needs the id",
              "ambiguous" in " ".join(exc.errors).lower()
              and "char-001" not in " ".join(exc.errors)
              and "char-005" not in " ".join(exc.errors),
              f"errors={exc.errors}")

    try:
        ir.resolve_character_reference(
            selector={"character_id": "char-001", "name": "Sarena"},
            registry=characters)
        check("CF-P1-004-R1-IDENTITY-P05: name and id mismatch fails",
              False, "mismatched name+id resolved instead of refusing")
    except ir.IdentityResolutionError as exc:
        check("CF-P1-004-R1-IDENTITY-P05: name and id mismatch fails",
              len(exc.errors) > 0, f"errors={exc.errors}")

    try:
        ir.resolve_character_reference(
            selector={"character_id": "char-999"}, registry=characters)
        check("CF-P1-004-R1-IDENTITY-P06: unknown id fails closed",
              False, "unknown id resolved instead of refusing")
    except ir.IdentityResolutionError as exc:
        check("CF-P1-004-R1-IDENTITY-P06: unknown id fails closed",
              "char-999" in " ".join(exc.errors)
              and "Arif" not in " ".join(exc.errors),
              f"errors={exc.errors}")

    try:
        ir.resolve_character_reference(
            selector={"name": "Nobody"}, registry=characters)
        check("CF-P1-004-R1-IDENTITY-P07: unknown name fails closed",
              False, "unknown name resolved instead of refusing")
    except ir.IdentityResolutionError as exc:
        check("CF-P1-004-R1-IDENTITY-P07: unknown name fails closed",
              "Nobody" in " ".join(exc.errors),
              f"errors={exc.errors}")

    # P08: a record under another workspace is not resolvable
    # through this registry at all — the loader excludes it, so
    # the resolver never sees it.
    other = clone(characters["char-001"])
    other["ownership"] = {"owner_id": "owner-b",
                          "workspace_id": "workspace-b",
                          "visibility": "private", "sharing": "none"}
    scoped = {cid: rec for cid, rec in characters.items()
              if cid != "char-001"}
    scoped["char-001"] = other
    try:
        ir.resolve_character_reference(
            selector={"character_id": "char-001"}, registry={
                cid: rec for cid, rec in scoped.items()
                if (rec.get("ownership") or {}).get("workspace_id")
                == session.workspace_id})
        check("CF-P1-004-R1-IDENTITY-P08: cross-workspace record is "
              "not resolvable", False,
              "other-workspace record resolved instead of refusing")
    except ir.IdentityResolutionError as exc:
        check("CF-P1-004-R1-IDENTITY-P08: cross-workspace record is "
              "not resolvable",
              "char-001" in " ".join(exc.errors),
              f"errors={exc.errors}")


# ---------------------------------------------------------------------------
# P09–P15: identity-selection policy (Tasks B/C)
# ---------------------------------------------------------------------------

def _policy_group():
    session = fresh_session()
    characters, _voices = registries(session)

    resolved = ir.resolve_project_identity_policy(
        policy(mode="SELECTED_REGISTERED_ONLY",
               selected=("char-001", "char-002"), allow_new=False),
        registry=characters)
    check("CF-P1-004-R1-IDENTITY-P09: SELECTED_REGISTERED_ONLY "
          "selects exactly the selected ids",
          set(resolved["resolved"]) == {"char-001", "char-002"}
          and resolved["mode"] == "SELECTED_REGISTERED_ONLY",
          f"got {sorted(resolved['resolved'])}")

    resolved = ir.resolve_project_identity_policy(
        policy(mode="MIXED_REGISTERED_AND_NEW",
               selected=("char-001",), allow_new=True),
        registry=characters)
    check("CF-P1-004-R1-IDENTITY-P10: MIXED resolves registered and "
          "allows new",
          set(resolved["resolved"]) == {"char-001"}
          and resolved["allow_new_task_local_characters"] is True,
          f"got {resolved}")

    resolved = ir.resolve_project_identity_policy(
        policy(mode="NEW_ONLY", selected=(), allow_new=True),
        registry=characters)
    check("CF-P1-004-R1-IDENTITY-P11: NEW_ONLY resolves no "
          "registered character",
          resolved["resolved"] == {} and resolved["mode"] == "NEW_ONLY",
          f"got {resolved}")

    resolved = ir.resolve_project_identity_policy(
        policy(mode="AUTO_MATCH_APPROVED",
               selected=("char-002",), allow_new=False),
        registry=characters)
    check("CF-P1-004-R1-IDENTITY-P12: AUTO_MATCH_APPROVED resolves "
          "the selected ids",
          set(resolved["resolved"]) == {"char-002"},
          f"got {resolved}")
    # ... and an unselected character still auto-matches by its
    # unique name at cast-resolution time.
    auto = ir.resolve_character_reference(
        selector={"name": "Mina"}, registry=characters)
    check("CF-P1-004-R1-IDENTITY-P12: AUTO_MATCH_APPROVED auto-"
          "matches a unique unselected name",
          auto["character_id"] == "char-003",
          f"got {auto}")

    errors = ir.validate_identity_policy(
        policy(selected=("char-001",), excluded=("char-001",)))
    check("CF-P1-004-R1-IDENTITY-P13: a character cannot be both "
          "selected and excluded",
          any("both selected and excluded" in e for e in errors),
          f"errors={errors}")

    try:
        ir.resolve_project_identity_policy(
            policy(excluded=("char-999",)), registry=characters)
        check("CF-P1-004-R1-IDENTITY-P14: unknown excluded id is an "
              "error", False,
              "unknown excluded id accepted instead of refusing")
    except ir.IdentityResolutionError as exc:
        check("CF-P1-004-R1-IDENTITY-P14: unknown excluded id is an "
              "error",
              "char-999" in " ".join(exc.errors),
              f"errors={exc.errors}")

    try:
        ir.resolve_project_identity_policy(
            policy(approval="pending"), registry=characters)
        check("CF-P1-004-R1-IDENTITY-P15: unapproved policy must not "
              "drive production", False,
              "pending policy resolved instead of refusing")
    except ir.IdentityResolutionError as exc:
        check("CF-P1-004-R1-IDENTITY-P15: unapproved policy must not "
              "drive production",
              "not approved" in " ".join(exc.errors).lower(),
              f"errors={exc.errors}")
    errors = ir.validate_identity_policy(
        policy(mode="NEW_ONLY", selected=("char-001",)))
    check("CF-P1-004-R1-IDENTITY-P15: NEW_ONLY selecting a "
          "registered character is invalid",
          len(errors) > 0, f"errors={errors}")
    errors = ir.validate_identity_policy(
        policy(is_default=True, override=True))
    check("CF-P1-004-R1-IDENTITY-P15: a policy cannot be both "
          "project default and one-job override",
          len(errors) > 0, f"errors={errors}")

# ---------------------------------------------------------------------------
# P16–P23: image / video binding (Tasks F/G)
# ---------------------------------------------------------------------------

def _packets_by_shot(package, task_type):
    out = {}
    for packet in package["packets"]:
        if packet["task_type"] == task_type and packet.get("shot_id"):
            out[packet["shot_id"]] = packet
    return out


def _binding_group():
    session = fresh_session()
    bundle, job = mixed_job(session, stills_first=True)
    package, job = compile_provider_tasks(session, job, bundle,
                                          mixed_analysis(),
                                          list(mixed_proposals().values()))
    images = _packets_by_shot(package, "image-generation")
    videos = _packets_by_shot(package, "video-generation")

    sh01 = images.get("sh-01")
    check("CF-P1-004-R1-IDENTITY-P16: image packet carries the "
          "structured identity binding",
          sh01 is not None
          and len(sh01.get("identity_bindings") or []) == 1
          and sh01["identity_bindings"][0]["character_id"] == "char-001"
          and sh01["identity_bindings"][0]["primary_reference_id"]
          == "ref-arif-front"
          and sh01["identity_bindings"][0]["reference_sha256"]
          == "a1" * 32
          and sh01["identity_bindings"][0]["fixed_identity_reference"]
          .startswith("fixed-identity:"),
          f"got {sh01}")

    sh01v = videos.get("sh-01")
    check("CF-P1-004-R1-IDENTITY-P17: video packet carries the "
          "structured identity binding",
          sh01v is not None
          and len(sh01v.get("identity_bindings") or []) == 1
          and sh01v["identity_bindings"][0]["character_id"] == "char-001"
          and sh01v["identity_bindings"][0]["primary_reference_id"]
          == "ref-arif-front"
          and sh01v["identity_bindings"][0]["reference_sha256"]
          == "a1" * 32,
          f"got {sh01v}")
    check("CF-P1-004-R1-IDENTITY-P17: video binding names the "
          "model sheet only when the record carries one",
          sh01v is not None
          and "model_sheet_reference"
          not in sh01v["identity_bindings"][0],
          f"got {sh01v}")

    sh02 = videos.get("sh-02")
    bindings = sh02.get("identity_bindings") or [] if sh02 else []
    by_id = {b["character_id"]: b for b in bindings}
    check("CF-P1-004-R1-IDENTITY-P18: three-character shot gets "
          "three distinct bindings, one per character",
          len(bindings) == 3
          and set(by_id) == {"char-001", "char-002",
                             "prop-shopkeeper-001"},
          f"got {[b['character_id'] for b in bindings]}")
    check("CF-P1-004-R1-IDENTITY-P18: no reference cross-"
          "contamination between characters",
          by_id.get("char-001", {}).get("primary_reference_id")
          == "ref-arif-front"
          and by_id.get("char-002", {}).get("primary_reference_id")
          == "ref-sarena-front"
          and by_id.get("prop-shopkeeper-001", {}).get(
              "primary_reference_id") == "ref-shopkeeper-front"
          and by_id.get("char-001", {}).get("reference_sha256")
          != by_id.get("char-002", {}).get("reference_sha256"),
          f"got {by_id}")

    check("CF-P1-004-R1-IDENTITY-P19: close-up shot gets the "
          "front angle reference",
          sh01["identity_bindings"][0]["angle_matched_reference"]
          ["asset_id"] == "ref-arif-front",
          f"got {sh01['identity_bindings'][0]}")
    check("CF-P1-004-R1-IDENTITY-P19: medium shot gets the "
          "three-quarter angle reference",
          by_id["char-001"]["angle_matched_reference"]["asset_id"]
          == "ref-arif-three-quarter",
          f"got {by_id['char-001']}")
    sh03 = videos.get("sh-03")
    sh03_by_id = {b["character_id"]: b
                  for b in (sh03.get("identity_bindings") or [])} \
        if sh03 else {}
    check("CF-P1-004-R1-IDENTITY-P20: expression reference follows "
          "the line's emotion in its own shot",
          by_id["char-002"]["expression_reference"]["asset_id"]
          == "ref-sarena-trust"
          and sh03_by_id["char-001"]["expression_reference"]
          ["asset_id"] == "ref-arif-determination",
          f"got sh-02 {by_id} sh-03 {sh03_by_id}")
    check("CF-P1-004-R1-IDENTITY-P20: a character with no spoken "
          "line in the shot gets no expression reference",
          "expression_reference" not in by_id["char-001"],
          f"got {by_id['char-001']}")

    check("CF-P1-004-R1-IDENTITY-P21: no verified provider is "
          "matched to an identity-critical task",
          sh01v["provider_status"]
          == "unavailable-no-verified-provider"
          and sh01v.get("provider_translation") is None,
          f"got {sh01v['provider_status']}")
    misses = {m["task_id"]: m for m in package["unmatched_tasks"]}
    check("CF-P1-004-R1-IDENTITY-P21: the mismatch is recorded "
          "with the identity handoff note",
          sh01v["task_id"] in misses
          and "identity-critical" in misses[sh01v["task_id"]]["reason"]
          and "identity_bindings" in sh01v,
          f"got {misses.get(sh01v['task_id'])}")

    # P22: an excluded character in the cast fails closed at
    # bundle time (the mixed analysis already puts char-003 in
    # the cast; the policy excludes it).
    characters, _voices = registries(session)
    excluded_policy = policy(selected=("char-001", "char-002",
                                       "char-003"),
                             excluded=("char-003",))
    try:
        build_production_bundle(
            session, transition_job(
                session,
                create_production_job(
                    session, "job-excluded-001", "proj-test-001",
                    {"delivery_profile": "short-form-15-60s"},
                    identity_policy=excluded_policy),
                "ANALYZING"),
            T.fresh_routing_plan(session), mixed_script(),
            mixed_profile(), mixed_draft(), mixed_analysis(),
            "bundle-excluded-001",
            identity_policy=excluded_policy,
            character_registry=characters,
            voice_registry=_voices,
            proposals=list(mixed_proposals(
                "job-excluded-001").values()))
        check("CF-P1-004-R1-IDENTITY-P22: excluded character in "
              "the cast fails closed", False,
              "excluded character accepted instead of refusing")
    except ProductionOrchestratorError as exc:
        check("CF-P1-004-R1-IDENTITY-P22: excluded character in "
              "the cast fails closed",
              "char-003" in " ".join(exc.errors),
              f"errors={exc.errors}")

    # P23: a shot character with no snapshot entry fails closed
    # at compile time.
    snapshot = clone(job["identity_snapshot"])
    snapshot["resolved_characters"] = [
        e for e in snapshot["resolved_characters"]
        if e.get("character_id") != "char-002"]
    snapshot["snapshot_hash"] = ir.sha256_hex(ir.canonical_json(
        {k: v for k, v in snapshot.items() if k != "snapshot_hash"}))
    try:
        tc.compile_task_package(session, job, bundle["s2p_bundle"],
                                mixed_analysis(),
                                list(mixed_proposals().values()),
                                identity_snapshot=snapshot)
        check("CF-P1-004-R1-IDENTITY-P23: shot character with no "
              "snapshot entry fails closed", False,
              "unresolved shot character compiled instead of refusing")
    except tc.TaskCompilerError as exc:
        check("CF-P1-004-R1-IDENTITY-P23: shot character with no "
              "snapshot entry fails closed",
              "char-002" in " ".join(exc.errors),
              f"errors={exc.errors}")


# ---------------------------------------------------------------------------
# P24–P34: voice resolution (Tasks I/J)
# ---------------------------------------------------------------------------

def _voice_group():
    session = fresh_session()
    characters, voices = registries(session)

    voice, errors = ir.resolve_character_voice(
        character_id="char-001", voice_registry=voices,
        character_registry=characters,
        requesting_owner_id=session.owner_id,
        requesting_workspace_id=session.workspace_id)
    check("CF-P1-004-R1-IDENTITY-P24: the character default voice "
          "resolves",
          voice is not None
          and voice["voice_profile_id"] == "voice-arif-bn-001"
          and errors == [],
          f"voice={voice} errors={errors}")

    voice, errors = ir.resolve_character_voice(
        character_id="char-001", voice_registry=voices,
        character_registry=characters,
        requesting_owner_id=session.owner_id,
        requesting_workspace_id=session.workspace_id,
        language="en")
    check("CF-P1-004-R1-IDENTITY-P25: English line resolves the "
          "English profile",
          voice is not None
          and voice["voice_profile_id"] == "voice-arif-en-001",
          f"voice={voice} errors={errors}")
    voice, errors = ir.resolve_character_voice(
        character_id="char-002", voice_registry=voices,
        character_registry=characters,
        requesting_owner_id=session.owner_id,
        requesting_workspace_id=session.workspace_id,
        language="bn")
    check("CF-P1-004-R1-IDENTITY-P25: Bengali line resolves the "
          "Bengali profile",
          voice is not None
          and voice["voice_profile_id"] == "voice-sarena-bn-001",
          f"voice={voice} errors={errors}")

    voice, errors = ir.resolve_character_voice(
        character_id="char-001", voice_registry=voices,
        character_registry=characters,
        requesting_owner_id=session.owner_id,
        requesting_workspace_id=session.workspace_id,
        language="bn")
    check("CF-P1-004-R1-IDENTITY-P26: several eligible profiles "
          "resolve to the character default",
          voice is not None
          and voice["voice_profile_id"] == "voice-arif-bn-001",
          f"voice={voice} errors={errors}")

    voice, errors = ir.resolve_character_voice(
        character_id="char-004", voice_registry=voices,
        character_registry=characters,
        requesting_owner_id=session.owner_id,
        requesting_workspace_id=session.workspace_id,
        language="bn")
    check("CF-P1-004-R1-IDENTITY-P27: several eligible profiles "
          "with no default require one clear selection",
          voice is None and len(errors) > 0
          and "one clear selection" in " ".join(errors),
          f"voice={voice} errors={errors}")

    voice, errors = ir.resolve_character_voice(
        character_id="char-001", voice_registry=voices,
        character_registry=characters,
        requesting_owner_id=session.owner_id,
        requesting_workspace_id=session.workspace_id,
        preferred_voice_profile_id="voice-sarena-bn-001")
    check("CF-P1-004-R1-IDENTITY-P28: a preferred profile must "
          "belong to this character",
          voice is None and len(errors) > 0
          and "not bound to character" in " ".join(errors),
          f"voice={voice} errors={errors}")

    voice, errors = ir.resolve_character_voice(
        character_id="char-001", voice_registry=voices,
        character_registry=characters,
        requesting_owner_id=session.owner_id,
        requesting_workspace_id=session.workspace_id,
        preferred_voice_profile_id="voice-sarena-bn-001",
        language="bn")
    check("CF-P1-004-R1-IDENTITY-P29: another character's voice "
          "is never borrowed",
          voice is None and len(errors) > 0,
          f"voice={voice} errors={errors}")

    pending = clone(voices["voice-arif-bn-001"])
    pending["approval_status"] = "pending"
    pending["status"] = "approved"
    pending_voices = dict(voices)
    pending_voices["voice-arif-bn-001"] = pending
    voice, errors = ir.resolve_character_voice(
        character_id="char-001", voice_registry=pending_voices,
        character_registry=characters,
        requesting_owner_id=session.owner_id,
        requesting_workspace_id=session.workspace_id,
        preferred_voice_profile_id="voice-arif-bn-001")
    check("CF-P1-004-R1-IDENTITY-P30: an unapproved voice profile "
          "fails closed",
          voice is None and len(errors) > 0,
          f"voice={voice} errors={errors}")

    # P31: the compiled voice packet carries the exact binding.
    bundle, job = mixed_job(session)
    package, _job = compile_provider_tasks(
        session, job, bundle, mixed_analysis(),
        list(mixed_proposals().values()))
    voice_packets = [p for p in package["packets"]
                     if p["task_type"] == "voice-generation"]
    by_line = {p["voice_binding"]["dialogue_line_id"]: p
               for p in voice_packets if p.get("voice_binding")}
    line01 = by_line.get("l-01")
    check("CF-P1-004-R1-IDENTITY-P31: voice packet carries the "
          "exact voice binding",
          line01 is not None
          and line01["voice_binding"]["character_id"] == "char-001"
          and line01["voice_binding"]["voice_profile_id"]
          == "voice-arif-en-001"
          and line01["voice_binding"]["language"] == "en"
          and line01["voice_binding"]["reference_audio_asset_id"]
          == "voice-reference"
          and line01["voice_binding"]["reference_audio_sha256"]
          == "b2" * 32
          and "voice-arif-en-001" in
          line01["voice_binding"]["ownership_consent_ref"],
          f"got {line01}")
    line06 = by_line.get("l-06")
    check("CF-P1-004-R1-IDENTITY-P31: the Bengali line binds the "
          "Bengali profile, not the English one",
          line06 is not None
          and line06["voice_binding"]["voice_profile_id"]
          == "voice-arif-bn-001"
          and line06["voice_binding"]["language"] == "bn",
          f"got {line06}")

    # P32: commercial production against a provider that does not
    # approve commercial use fails closed.
    voice, errors = ir.resolve_character_voice(
        character_id="char-001", voice_registry=voices,
        character_registry=characters,
        requesting_owner_id=session.owner_id,
        requesting_workspace_id=session.workspace_id,
        language="bn", provider={"commercial_use_approved": False},
        commercial_use=True)
    check("CF-P1-004-R1-IDENTITY-P32: commercial production with "
          "a non-approved provider fails closed",
          voice is None and len(errors) > 0
          and "commercial" in " ".join(errors).lower(),
          f"voice={voice} errors={errors}")

    voice, errors = ir.resolve_character_voice(
        character_id="char-001", voice_registry=voices,
        character_registry=characters,
        requesting_owner_id=session.owner_id,
        requesting_workspace_id=session.workspace_id,
        language="bn", role="narration")
    check("CF-P1-004-R1-IDENTITY-P33: a narration role prefers "
          "the narration variant",
          voice is not None
          and voice["voice_profile_id"] == "voice-arif-narr-001",
          f"voice={voice} errors={errors}")

    legacy = clone(voices["voice-mina-bn-001"])
    legacy["language"] = ""
    legacy_voices = dict(voices)
    legacy_voices["voice-mina-bn-001"] = legacy
    voice, errors = ir.resolve_character_voice(
        character_id="char-003", voice_registry=legacy_voices,
        character_registry=characters,
        requesting_owner_id=session.owner_id,
        requesting_workspace_id=session.workspace_id,
        language="bn")
    check("CF-P1-004-R1-IDENTITY-P34: a language-agnostic legacy "
          "profile stays eligible only with no exact match",
          voice is not None
          and voice["voice_profile_id"] == "voice-mina-bn-001",
          f"voice={voice} errors={errors}")

    # A character.json record carries no ownership, so a v2.5
    # voice for it can never satisfy the P0 ownership match —
    # the resolver fails closed (existing P0 contract, recorded
    # here so the boundary is pinned).
    voice, errors = ir.resolve_character_voice(
        character_id="char-006", voice_registry=voices,
        character_registry=characters,
        requesting_owner_id=session.owner_id,
        requesting_workspace_id=session.workspace_id,
        language="bn")
    check("CF-P1-004-R1-IDENTITY-P34: a voice whose character "
          "record carries no ownership fails closed",
          voice is None and len(errors) > 0,
          f"voice={voice} errors={errors}")

# ---------------------------------------------------------------------------
# P35–P40: multi-character / continuity (Tasks K–N)
# ---------------------------------------------------------------------------

def _packets_of_type(package, task_type):
    return [p for p in package["packets"]
            if p["task_type"] == task_type]


def _mixed_compile(session, job_id="job-mixed-001", **job_flags):
    bundle, job = mixed_job(session, job_id=job_id, **job_flags)
    package, job = compile_provider_tasks(
        session, job, bundle, mixed_analysis(),
        list(mixed_proposals(job_id).values()))
    return bundle, job, package


def _e2e_group():
    profile, session = fresh_profile_session()
    characters, voices = registries(session)
    before = ir.record_hash(characters)
    bundle, job, package = _mixed_compile(session, stills_first=True)
    snapshot = job["identity_snapshot"]

    check("CF-P1-004-R1-IDENTITY-P35: mixed cast snapshot holds "
          "registered and task-local characters",
          snapshot is not None
          and snapshot["mode"] == "MIXED_REGISTERED_AND_NEW"
          and len(snapshot["resolved_characters"]) == 5
          and sorted(snapshot["task_local_proposal_ids"])
          == ["prop-narrator-001", "prop-shopkeeper-001"]
          and {e["resolution"] for e in
               snapshot["resolved_characters"]}
          == {"approved", "task-local-proposal"},
          f"got {snapshot}")
    check("CF-P1-004-R1-IDENTITY-P35: cast classes classify the "
          "narrator as voice-only",
          snapshot["cast_classes"] == [
              {"character_ref": "char-001",
               "cast_class": "VISIBLE_CHARACTER"},
              {"character_ref": "char-002",
               "cast_class": "VISIBLE_CHARACTER"},
              {"character_ref": "char-003",
               "cast_class": "VISIBLE_CHARACTER"},
              {"character_ref": "narr-001",
               "cast_class": "NARRATOR_OR_VOICE_OVER"},
              {"character_ref": "shopkeeper",
               "cast_class": "VISIBLE_CHARACTER"}],
          f"got {snapshot.get('cast_classes')}")
    check("CF-P1-004-R1-IDENTITY-P35: voice selections cover "
          "every registered speaking character, per language",
          sorted((s["character_id"], s["language"])
                 for s in snapshot["voice_selections"])
          == [("char-001", "bn"), ("char-001", "en"),
              ("char-002", "bn"), ("char-003", "bn")],
          f"got {snapshot['voice_selections']}")
    check("CF-P1-004-R1-IDENTITY-P35: old identities are unchanged "
          "by the build",
          ir.record_hash(characters) == before
          and snapshot["registry_snapshot_hash"]
          == ir.registry_snapshot_hash(characters),
          "registry changed during the build")
    entry = next(e for e in snapshot["resolved_characters"]
                 if e.get("character_id") == "char-001")
    check("CF-P1-004-R1-IDENTITY-P35: snapshot freezes the "
          "approved reference with its record hash",
          entry["registry_record_hash"]
          == ir.record_hash(characters["char-001"])
          and entry["primary_reference_id"] == "ref-arif-front"
          and entry["fixed_identity_reference"].startswith(
              "fixed-identity:"),
          f"got {entry}")

    videos = _packets_by_shot(package, "video-generation")
    check("CF-P1-004-R1-IDENTITY-P35: the three-character shot "
          "separates all three identities",
          len(videos["sh-02"].get("identity_bindings") or []) == 3
          and {b["character_id"] for b in
               videos["sh-02"]["identity_bindings"]}
          == {"char-001", "char-002", "prop-shopkeeper-001"},
          f"got {videos.get('sh-02')}")
    sheets = _packets_of_type(package, "reference-sheet")
    check("CF-P1-004-R1-IDENTITY-P35: only the visible task-local "
          "character gets a reference sheet",
          len(sheets) == 1
          and sheets[0].get("identity_bindings")
          and sheets[0]["identity_bindings"][0]["character_id"]
          == "prop-shopkeeper-001",
          f"got {len(sheets)} reference sheets")
    narrator_packets = [
        p for p in package["packets"]
        if any((b.get("character_id") in ("narr-001",
                                          "prop-narrator-001"))
               for b in p.get("identity_bindings") or [])]
    check("CF-P1-004-R1-IDENTITY-P35: the narrator receives no "
          "image or video binding",
          narrator_packets == [],
          f"got {narrator_packets}")
    narrator_voice = [p for p in package["packets"]
                      if p["task_type"] == "voice-generation"
                      and any(i.get("input_ref")
                              == "voice-narrator-001"
                              for i in p["required_inputs"])]
    check("CF-P1-004-R1-IDENTITY-P35: the narrator still gets a "
          "voice packet, from the bundle profile, without a "
          "registered voice binding",
          len(narrator_voice) == 1
          and "voice_binding" not in narrator_voice[0],
          f"got {narrator_voice}")

    check("CF-P1-004-R1-IDENTITY-P36: five-character scenario — "
          "every shot binds exactly its own characters",
          len(videos["sh-01"].get("identity_bindings") or []) == 1
          and len(videos["sh-03"].get("identity_bindings") or []) == 2
          and {b["character_id"] for b in
               videos["sh-03"]["identity_bindings"]}
          == {"char-001", "char-003"},
          f"got sh-01 {videos.get('sh-01')} sh-03 {videos.get('sh-03')}")
    check("CF-P1-004-R1-IDENTITY-P36: the snapshot hash covers "
          "all five characters",
          snapshot["registry_snapshot_hash"]
          == ir.registry_snapshot_hash(characters)
          and len(snapshot["resolved_characters"]) == 5,
          f"got {snapshot}")

    # P37: the same inputs reproduce the same snapshot; a later
    # registry change is detected, never silently absorbed.
    _bundle2, job2 = mixed_job(session, job_id="job-mixed-001",
                               bundle_id="bundle-mixed-002")
    check("CF-P1-004-R1-IDENTITY-P37: identical inputs reproduce "
          "the identical snapshot hash",
          job2["identity_snapshot"]["snapshot_hash"]
          == snapshot["snapshot_hash"],
          "snapshot hash differs for identical inputs")
    changed = clone(characters)
    changed["char-002"]["features"]["clothing"] = "blue cloak"
    errors = ir.validate_identity_snapshot(
        snapshot, registry=changed, voice_registry=voices)
    check("CF-P1-004-R1-IDENTITY-P37: a changed registry record "
          "is detected on revalidation",
          len(errors) > 0 and "char-002" in " ".join(errors),
          f"errors={errors}")
    tampered = clone(snapshot)
    tampered["resolved_characters"][0]["reference_asset_ids"][0][
        "sha256"] = "0" * 64
    errors = ir.validate_identity_snapshot(tampered)
    check("CF-P1-004-R1-IDENTITY-P37: a tampered snapshot hash "
          "is detected",
          len(errors) > 0, f"errors={errors}")

    # P38: resume validation against the stored snapshot.
    errors = ir.validate_resumed_identity(
        job, registry=characters, voice_registry=voices)
    check("CF-P1-004-R1-IDENTITY-P38: resume validates against "
          "unchanged registries",
          errors == [], f"errors={errors}")
    changed_voices = clone(voices)
    changed_voices["voice-arif-bn-001"]["reference_audio"]["sha256"] \
        = "0" * 64
    errors = ir.validate_resumed_identity(
        job, registry=characters, voice_registry=changed_voices)
    check("CF-P1-004-R1-IDENTITY-P38: a changed voice reference "
          "audio hash blocks resume",
          len(errors) > 0, f"errors={errors}")

    # Integration (parent): the same revalidation through the
    # production store's resume path — the snapshot rides in
    # the stored job, and resume with the current registries
    # rebinds the session; a changed voice hash stops it.
    root = tempfile.mkdtemp(prefix="cf-p1-004-identity-resume-")
    store.save_production_job(session, root, job)
    session2 = start_session(profile, profile.workspace_id)
    _sessions.append(session2)
    resumed = store.resume_production_job(
        session2, root, job["job_id"], job["project_id"],
        registry=characters, voice_registry=voices)
    check("CF-P1-004-R1-IDENTITY-P38: store resume with the "
          "current registries rebinds the session and keeps the "
          "frozen snapshot",
          resumed["session_id"] == session2.session_id
          and resumed["identity_snapshot"]["snapshot_hash"]
          == snapshot["snapshot_hash"],
          f"got {resumed.get('identity_snapshot')}")
    try:
        store.resume_production_job(
            session2, root, job["job_id"], job["project_id"],
            registry=characters, voice_registry=changed_voices)
        check("CF-P1-004-R1-IDENTITY-P38: a changed voice "
              "reference audio hash blocks store resume",
              False, "resume succeeded with a changed voice hash")
    except store.ProductionStoreError as exc:
        check("CF-P1-004-R1-IDENTITY-P38: a changed voice "
              "reference audio hash blocks store resume",
              "identity" in str(exc).lower(),
              f"error={exc}")

    # P40: project default vs one-job override; scene-specific
    # participation; the project config survives the override.
    default_policy = policy(
        policy_id="pol-default-001", mode="SELECTED_REGISTERED_ONLY",
        selected=("char-001", "char-002"), allow_new=False,
        is_default=True)
    default_before = clone(default_policy)
    override_policy = policy(
        policy_id="pol-override-001", mode="MIXED_REGISTERED_AND_NEW",
        selected=("char-001", "char-002", "char-003"),
        allow_new=True, override=True)
    _bundle3, job3 = mixed_job(session, job_id="job-override-001",
                               bundle_id="bundle-override-001",
                               policy_value=override_policy)
    check("CF-P1-004-R1-IDENTITY-P40: a one-job override drives "
          "its own job without touching the project default",
          job3["identity_snapshot"]["mode"]
          == "MIXED_REGISTERED_AND_NEW"
          and default_policy == default_before
          and job3["identity_policy"]["policy_id"]
          == "pol-override-001",
          f"got {job3['identity_policy']}")
    check("CF-P1-004-R1-IDENTITY-P40: scene-specific wardrobe "
          "travels on the binding",
          next(b for b in videos["sh-02"]["identity_bindings"]
               if b["character_id"] == "char-002")
          ["wardrobe_variation"] == "royal red cloak",
          f"got {videos['sh-02']['identity_bindings']}")
    try:
        ir.identity_bindings_for_shot(
            shot={"shot_id": "sh-99", "scene_id": "sc-02",
                  "framing": "medium",
                  "character_ids": ["char-002"]},
            snapshot=snapshot, analysis=mixed_analysis())
        check("CF-P1-004-R1-IDENTITY-P40: a character outside its "
              "scene list never appears in that scene's shot",
              False, "out-of-scene character bound instead of refusing")
    except ir.IdentityResolutionError as exc:
        check("CF-P1-004-R1-IDENTITY-P40: a character outside its "
              "scene list never appears in that scene's shot",
              "char-002" in " ".join(exc.errors),
              f"errors={exc.errors}")


def _new_only_inputs():
    """The mixed story rebuilt with only new characters: every
    registered id/voice is renamed to a task-local ref, and the
    analysis resolutions become task-local proposals."""
    script = clone(mixed_script())
    profile = clone(mixed_profile())
    draft = clone(mixed_draft())
    analysis = clone(mixed_analysis())
    renames = [
        ("char-001", "farmer"), ("char-002", "daughter"),
        ("char-003", "traveler"),
        ("voice-arif-en-001", "voice-farmer-001"),
        ("voice-arif-bn-001", "voice-farmer-bn-001"),
        ("voice-sarena-bn-001", "voice-daughter-001"),
        ("voice-mina-bn-001", "voice-traveler-001"),
    ]

    def renamed(value):
        text = json.dumps(value)
        for old, new in renames:
            text = text.replace(old, new)
        return json.loads(text)

    script, profile, draft = (renamed(v) for v in
                              (script, profile, draft))
    analysis = renamed(analysis)
    proposals = {}
    for ref in ("farmer", "daughter", "traveler"):
        record = shopkeeper_proposal("job-newonly-001")
        record["proposal_id"] = f"prop-{ref}-001"
        record["character_ref"] = ref
        record["design_brief"] = f"A new character, {ref}, designed " \
                                 "for this story only."
        record["approved_reference_ids"] = [f"ref-{ref}-front"]
        proposals[record["proposal_id"]] = record
    for resolution in analysis["character_resolutions"]:
        ref = resolution["character_ref"]
        resolution["resolution"] = "task-local-proposal"
        resolution["proposal_id"] = f"prop-{ref}-001" \
            if ref in ("farmer", "daughter", "traveler") \
            else resolution["proposal_id"]
        resolution["provenance"] = "INFERRED_FOR_PRODUCTION"
        resolution.pop("registered_character_id", None)
    proposals.update(mixed_proposals("job-newonly-001"))
    return script, profile, draft, analysis, proposals


def _new_only_group():
    session = fresh_session()
    characters, voices = registries(session)
    script, profile, draft, analysis, proposals = _new_only_inputs()
    new_policy = policy(policy_id="pol-newonly-001", mode="NEW_ONLY",
                        selected=(), allow_new=True)
    job = create_production_job(
        session, "job-newonly-001", "proj-test-001",
        {"delivery_profile": "short-form-15-60s"},
        identity_policy=new_policy)
    job = transition_job(session, job, "ANALYZING")
    bundle, job = build_production_bundle(
        session, job, T.fresh_routing_plan(session), script, profile,
        draft, analysis, "bundle-newonly-001",
        identity_policy=new_policy,
        character_registry=characters, voice_registry=voices,
        proposals=list(proposals.values()))
    package, _job = compile_provider_tasks(
        session, job, bundle, analysis, list(proposals.values()))
    snapshot = job["identity_snapshot"]
    check("CF-P1-004-R1-IDENTITY-P39: NEW_ONLY snapshot holds no "
          "registered character and no voice selection",
          snapshot is not None
          and snapshot["mode"] == "NEW_ONLY"
          and all(e["resolution"] == "task-local-proposal"
                  for e in snapshot["resolved_characters"])
          and snapshot["voice_selections"] == [],
          f"got {snapshot}")
    leaked = []
    forbidden = ("ref-arif", "ref-sarena", "ref-mina", "ref-rahim",
                 "voice-arif", "voice-sarena", "voice-mina",
                 "voice-rahim", "char-001", "char-002", "char-003",
                 "char-004", "char-005", "char-006")
    package_text = json.dumps(package)
    for token in forbidden:
        if token in package_text:
            leaked.append(token)
    check("CF-P1-004-R1-IDENTITY-P39: no registered reference, "
          "model sheet, fixed block, seed or voice leaks into any "
          "NEW_ONLY packet",
          leaked == [], f"leaked tokens: {leaked}")
    check("CF-P1-004-R1-IDENTITY-P39: NEW_ONLY voice packets carry "
          "no registered voice binding",
          all("voice_binding" not in p
              for p in package["packets"]
              if p["task_type"] == "voice-generation"),
          "a voice packet carries a voice_binding")
    check("CF-P1-004-R1-IDENTITY-P39: NEW_ONLY image packets bind "
          "only task-local references",
          all(b["character_id"].startswith("prop-")
              for p in package["packets"]
              for b in p.get("identity_bindings") or []),
          "a binding names a registered character")


# ---------------------------------------------------------------------------
# P41–P45: registration / privacy (Task O)
# ---------------------------------------------------------------------------

def _stamped_records(session, records):
    """Fixture records bound to the test session's identity
    (records without an ownership field keep none — the
    character.json shape carries no ownership)."""
    return [stamp_ownership(r, session) if "ownership" in r
            else clone(r) for r in records]


def _write_overlay(root, records):
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, "registry.json"),
              encoding="utf-8", mode="w") as handle:
        json.dump({"characters": records}, handle)


def _privacy_group():
    session = fresh_session()
    characters, voices = registries(session)
    records = load_fixture("identity-registry.json")["characters"]

    overlay = tempfile.mkdtemp(prefix="cf-identity-overlay-")
    _write_overlay(overlay, _stamped_records(session, records))
    loaded = ir.load_authorized_character_registry(
        overlay, owner_id=session.owner_id,
        workspace_id=session.workspace_id)
    check("CF-P1-004-R1-IDENTITY-P41: the authorized registry "
          "loads every record",
          set(loaded) == {"char-001", "char-002", "char-003",
                          "char-004", "char-005", "char-006"},
          f"got {sorted(loaded)}")

    dup_root = tempfile.mkdtemp(prefix="cf-identity-dup-")
    _write_overlay(dup_root, _stamped_records(session, records[:1]))
    os.makedirs(os.path.join(dup_root, "char-001"), exist_ok=True)
    with open(os.path.join(dup_root, "char-001", "character.json"),
              encoding="utf-8", mode="w") as handle:
        json.dump(stamp_ownership(records[0], session), handle)
    try:
        ir.load_authorized_character_registry(dup_root)
        check("CF-P1-004-R1-IDENTITY-P41: a duplicate character id "
              "across files is an error", False,
              "duplicate id loaded instead of refusing")
    except ir.IdentityResolutionError as exc:
        text = " ".join(exc.errors)
        check("CF-P1-004-R1-IDENTITY-P41: a duplicate character id "
              "across files is an error",
              "char-001" in text and "Arif" not in text,
              f"errors={exc.errors}")

    try:
        ir.load_authorized_character_registry("relative/path")
        check("CF-P1-004-R1-IDENTITY-P42: a non-absolute registry "
              "root is refused", False,
              "relative root accepted instead of refusing")
    except ir.IdentityResolutionError:
        check("CF-P1-004-R1-IDENTITY-P42: a non-absolute registry "
              "root is refused", True)
    try:
        ir.load_authorized_character_registry(
            os.path.join(overlay, "does-not-exist"))
        check("CF-P1-004-R1-IDENTITY-P42: a missing registry root "
              "fails closed", False,
              "missing root accepted instead of refusing")
    except ir.IdentityResolutionError:
        check("CF-P1-004-R1-IDENTITY-P42: a missing registry root "
              "fails closed", True)
    try:
        saved_env = os.environ.pop("CONSISTENCY_FRAME_CHARACTERS",
                                   None)
        try:
            ir.load_authorized_character_registry()
        finally:
            if saved_env is not None:
                os.environ["CONSISTENCY_FRAME_CHARACTERS"] = saved_env
        check("CF-P1-004-R1-IDENTITY-P42: no configured registry "
              "fails closed", False,
              "unconfigured registry accepted instead of refusing")
    except ir.IdentityResolutionError:
        check("CF-P1-004-R1-IDENTITY-P42: no configured registry "
              "fails closed", True)
    link_root = tempfile.mkdtemp(prefix="cf-identity-link-")
    target = os.path.join(link_root, "real.json")
    with open(target, encoding="utf-8", mode="w") as handle:
        json.dump(stamp_ownership(records[0], session), handle)
    link_path = os.path.join(link_root, "character.json")
    try:
        os.symlink(target, link_path)
        try:
            ir.load_authorized_character_registry(link_root)
            check("CF-P1-004-R1-IDENTITY-P42: a symlinked registry "
                  "record is refused", False,
                  "symlinked record read instead of refusing")
        except ir.IdentityResolutionError:
            check("CF-P1-004-R1-IDENTITY-P42: a symlinked registry "
                  "record is refused", True)
    except OSError:
        check("CF-P1-004-R1-IDENTITY-P42: a symlinked registry "
              "record is refused (symlinks unavailable)", True)

    mixed_owners = _stamped_records(session, records[:3])
    other_owner = clone(records[3])
    other_owner["ownership"] = {
        "owner_id": "owner-b", "workspace_id": "workspace-b",
        "visibility": "private", "sharing": "none"}
    mixed_owners.append(other_owner)
    scoped_root = tempfile.mkdtemp(prefix="cf-identity-scoped-")
    _write_overlay(scoped_root, mixed_owners)
    scoped = ir.load_authorized_character_registry(
        scoped_root, owner_id=session.owner_id,
        workspace_id=session.workspace_id)
    check("CF-P1-004-R1-IDENTITY-P43: records under another owner "
          "are silently excluded",
          set(scoped) == {"char-001", "char-002", "char-003"},
          f"got {sorted(scoped)}")
    unscoped = ir.load_authorized_character_registry(scoped_root)
    check("CF-P1-004-R1-IDENTITY-P43: without a requester scope "
          "every record loads",
          set(unscoped) == {"char-001", "char-002", "char-003",
                            "char-004"},
          f"got {sorted(unscoped)}")

    try:
        ir.resolve_character_reference(
            selector={"character_id": "char-999"},
            registry=characters)
        check("CF-P1-004-R1-IDENTITY-P44: errors never leak private "
              "registry contents", False,
              "unknown id resolved instead of refusing")
    except ir.IdentityResolutionError as exc:
        text = " ".join(exc.errors)
        check("CF-P1-004-R1-IDENTITY-P44: errors never leak private "
              "registry contents",
              "Arif" not in text and "Sarena" not in text
              and "reference-front.jpg" not in text
              and "voice-reference" not in text,
              f"errors={exc.errors}")

    before_files = sorted(os.listdir(overlay))
    before_hash = ir.record_hash(characters)
    _mixed_compile(session, job_id="job-privacy-001")
    check("CF-P1-004-R1-IDENTITY-P45: a task-local proposal is "
          "never auto-registered",
          sorted(os.listdir(overlay)) == before_files
          and ir.record_hash(characters) == before_hash,
          "registry files or records changed during production")
    public_dir = os.path.join(ROOT, "characters")
    public_files = [name for name in os.listdir(public_dir)
                    if not name.startswith(".")
                    and name != "README.md"]
    check("CF-P1-004-R1-IDENTITY-P45: the public characters "
          "directory stays empty",
          public_files == [], f"got {public_files}")


def main():
    _resolution_group()
    _policy_group()
    _binding_group()
    _voice_group()
    _e2e_group()
    _new_only_group()
    _privacy_group()
    for session in list(_sessions):
        try:
            if is_active_session(session):
                close_session(session)
        except Exception:  # noqa: BLE001 - best-effort cleanup
            pass
    if failures:
        print(f"\n{len(failures)} FAILURES:")
        for name in failures:
            print(f"  FAIL {name}")
        print(f"test_identity_resolution: FAIL ({_checks[0]} checks)")
        sys.exit(1)
    print(f"test_identity_resolution: PASS ({_checks[0]} checks)")


if __name__ == "__main__":
    main()
