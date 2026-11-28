#!/usr/bin/env python3
"""Production analysis tests (CF-WO-P1-004).

Covers: the production-analysis contract (short, long and
missing-character fixtures validate with 0 errors; invalid
analyses fail closed; dialogue-count agreement with the source
script; provenance discipline; character-resolution
completeness) and the optional-field nullability parity matrix
over schemas/production-analysis.json (every optional property
path: present-valid passes, omitted passes, explicit null is
rejected; a coverage assertion compares the exercised paths
against the optional paths discovered from the schema itself,
so a future optional schema field without a matching test fails
the suite).

Conventions follow tests/test_script_to_performance_runtime.py:
check(name, cond, detail="") prints PASS/FAIL lines, failures
are collected, and the process exits 0 only when every check
passes. No test here weakens any P0 or P1 check.
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
from runtime.production_orchestrator import (  # noqa: E402
    validate_character_design_proposal, validate_production_analysis)

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
    root = tempfile.mkdtemp(prefix="cf-p1-004-test-")
    profile = load_or_create_profile(root)
    session = start_session(profile, profile.workspace_id)
    _sessions.append(session)
    return session


def load_fixture(name):
    with open(os.path.join(
            ROOT, "tests", "fixtures", name), encoding="utf-8") as f:
        return json.load(f)


def short_analysis():
    return load_fixture("production-analysis-short.json")


def long_analysis():
    return load_fixture("production-analysis-long.json")


def missing_analysis():
    return load_fixture("production-analysis-missing-character.json")


# ---------------------------------------------------------------------------
# CF-P1-004-ANALYSIS: the production-analysis contract
# ---------------------------------------------------------------------------

def _analysis_group():
    short = short_analysis()
    long = long_analysis()
    missing = missing_analysis()
    check("CF-P1-004-ANALYSIS: short fixture validates with 0 errors",
          validate_production_analysis(short) == [],
          f"errors={validate_production_analysis(short)}")
    check("CF-P1-004-ANALYSIS: long fixture validates with 0 errors",
          validate_production_analysis(long) == [],
          f"errors={validate_production_analysis(long)}")
    check("CF-P1-004-ANALYSIS: missing-character fixture validates "
          "with 0 errors",
          validate_production_analysis(missing) == [],
          f"errors={validate_production_analysis(missing)}")

    # Fixture shape: what each fixture actually carries.
    check("CF-P1-004-ANALYSIS: short fixture has 2 approved "
          "characters, 1 scene, 2 dialogue lines",
          len(short["character_resolutions"]) == 2
          and all(r["resolution"] == "approved"
                  for r in short["character_resolutions"])
          and len(short["scenes"]) == 1
          and short["dialogue_preservation"]
          ["source_dialogue_line_count"] == 2
          and short["script_contract_id"] == "script-test-001")
    check("CF-P1-004-ANALYSIS: long fixture has 3 scenes, 3 "
          "characters including a task-local proposal",
          len(long["scenes"]) == 3
          and len(long["character_resolutions"]) == 3
          and [r["resolution"]
               for r in long["character_resolutions"]] == [
                   "approved", "approved", "task-local-proposal"]
          and long["character_resolutions"][2]["proposal_id"]
          == "prop-fisherman-001"
          and long["script_contract_id"] == "script-long-001")
    check("CF-P1-004-ANALYSIS: missing-character fixture has 1 "
          "proposal character",
          len(missing["character_resolutions"]) == 1
          and missing["character_resolutions"][0]["resolution"]
          == "task-local-proposal"
          and missing["character_resolutions"][0]["proposal_id"]
          == "prop-fisherman-001")

    # Dialogue counts agree with the source script.
    script = T.script()
    check("CF-P1-004-ANALYSIS: short analysis dialogue counts match "
          "the S2P script (2 lines)",
          validate_production_analysis(short, script) == [])
    check("CF-P1-004-ANALYSIS: long analysis dialogue counts do not "
          "match the short S2P script (4 vs 2)",
          validate_production_analysis(long, script) != [])
    check("CF-P1-004-ANALYSIS: missing-character analysis dialogue "
          "counts do not match the short S2P script (1 vs 2)",
          validate_production_analysis(missing, script) != [])
    bad = clone(short)
    bad["dialogue_preservation"]["source_dialogue_line_count"] = 3
    check("CF-P1-004-ANALYSIS: source dialogue count mismatch fails",
          validate_production_analysis(bad, script) != [])
    bad = clone(short)
    bad["dialogue_preservation"]["mapped_line_count"] = 1
    check("CF-P1-004-ANALYSIS: mapped dialogue count mismatch fails",
          validate_production_analysis(bad, script) != [])

    # Invalid analyses fail closed.
    bad = clone(short)
    bad["schema_version"] = "2.4"
    check("CF-P1-004-ANALYSIS: bad schema_version fails",
          validate_production_analysis(bad) != [])
    bad = clone(short)
    del bad["premise"]
    check("CF-P1-004-ANALYSIS: missing required field fails",
          validate_production_analysis(bad) != [])
    bad = clone(short)
    bad["scenes"].append(clone(bad["scenes"][0]))
    check("CF-P1-004-ANALYSIS: duplicate scene_id fails",
          validate_production_analysis(bad) != [])
    bad = clone(short)
    bad["scenes"][0]["beats"].append(clone(bad["scenes"][0]["beats"][0]))
    check("CF-P1-004-ANALYSIS: duplicate beat_id fails",
          validate_production_analysis(bad) != [])
    bad = clone(short)
    bad["open_questions"] = [{
        "question": "Which river?",
        "why_material": "The location changes the whole look.",
        "provenance": "INFERRED_FOR_PRODUCTION"}]
    check("CF-P1-004-ANALYSIS: open question with provenance other "
          "than NEEDS_USER_DECISION fails",
          validate_production_analysis(bad) != [])
    good_question = clone(short)
    good_question["open_questions"] = [{
        "question": "Which river?",
        "why_material": "The location changes the whole look.",
        "provenance": "NEEDS_USER_DECISION"}]
    check("CF-P1-004-ANALYSIS: open question with provenance "
          "NEEDS_USER_DECISION validates (it is refused later, at "
          "bundle build, not here)",
          validate_production_analysis(good_question) == [])
    bad = clone(short)
    del bad["character_resolutions"][0]["registered_character_id"]
    check("CF-P1-004-ANALYSIS: approved resolution without a "
          "registered_character_id fails",
          validate_production_analysis(bad) != [])
    bad = clone(missing)
    del bad["character_resolutions"][0]["proposal_id"]
    check("CF-P1-004-ANALYSIS: proposal resolution without a "
          "proposal_id fails",
          validate_production_analysis(bad) != [])
    bad = clone(short)
    bad["scenes"][0]["provenance"] = "MADE_UP"
    check("CF-P1-004-ANALYSIS: provenance label outside the "
          "4-value enum fails",
          validate_production_analysis(bad) != [])
    bad = clone(short)
    bad["character_resolutions"][0]["resolution"] = "maybe"
    check("CF-P1-004-ANALYSIS: unknown character resolution fails",
          validate_production_analysis(bad) != [])
    bad = clone(short)
    bad["character_resolutions"][0]["provenance"] = "GUESS"
    check("CF-P1-004-ANALYSIS: resolution provenance outside the "
          "4-value enum fails",
          validate_production_analysis(bad) != [])
    check("CF-P1-004-ANALYSIS: a non-object analysis fails",
          validate_production_analysis(None) != []
          and validate_production_analysis(["not", "an", "object"])
          != [])

    # Character-design proposals validate on their own contract.
    proposed = load_fixture(
        "character-design-proposal-fisherman.json")
    approved = load_fixture(
        "character-design-proposal-fisherman-approved.json")
    check("CF-P1-004-ANALYSIS: proposed fisherman proposal validates",
          validate_character_design_proposal(proposed) == [],
          f"errors={validate_character_design_proposal(proposed)}")
    check("CF-P1-004-ANALYSIS: approved-for-job fisherman proposal "
          "validates",
          validate_character_design_proposal(approved) == [],
          f"errors={validate_character_design_proposal(approved)}")
    check("CF-P1-004-ANALYSIS: approved-for-job proposal carries "
          "the two approved references",
          approved["status"] == "approved-for-job"
          and approved["approved_reference_ids"] == [
              "ref-fisherman-front", "ref-fisherman-side"]
          and proposed["status"] == "proposed"
          and proposed["approved_reference_ids"] == [])
    bad = clone(proposed)
    bad["schema_version"] = "2.4"
    check("CF-P1-004-ANALYSIS: proposal with a bad schema_version "
          "fails",
          validate_character_design_proposal(bad) != [])
    bad = clone(proposed)
    bad["status"] = "rejected"
    check("CF-P1-004-ANALYSIS: a rejected proposal is still "
          "schema-valid (rejection is refused at use, not here)",
          validate_character_design_proposal(bad) == [])
    check("CF-P1-004-ANALYSIS: a non-object proposal fails",
          validate_character_design_proposal(None) != [])


# ---------------------------------------------------------------------------
# CF-P1-004-ANALYSIS-NULL: optional-field nullability parity over
# schemas/production-analysis.json. Declared matrix: every optional
# property path, exactly once. A future optional schema field
# without a matching test fails the coverage assertion below.
# ---------------------------------------------------------------------------

NULL_CASES = [
    "character_resolutions[i].cast_class",
    "character_resolutions[i].proposal_id",
    "character_resolutions[i].provenance_note",
    "character_resolutions[i].registered_character_id",
    "character_resolutions[i].scene_ids",
    "dialogue_preservation.notes",
    "emotional_progression",
    "emotional_progression[i].progression_note",
    "format_profile",
    "format_profile.chapters",
    "format_profile.chapters[i].scene_ids",
    "format_profile.duration_target_seconds",
    "notes",
    "open_questions",
    "pacing",
    "pacing.pacing_note",
    "scenes[i].asset_references",
    "scenes[i].asset_references[i].reference_id",
    "scenes[i].atmosphere",
    "scenes[i].background_design",
    "scenes[i].background_requirements",
    "scenes[i].character_refs",
    "scenes[i].environment_continuity",
    "scenes[i].foreground_requirements",
    "scenes[i].important_props",
    "scenes[i].important_props[i].approved_prop_id",
    "scenes[i].important_props[i].approved_reference_ids",
    "scenes[i].important_props[i].continuity_restrictions",
    "scenes[i].important_props[i].design_brief",
    "scenes[i].important_props[i].physical_requirements",
    "scenes[i].important_props[i].provenance_note",
    "scenes[i].important_props[i].visual_requirements",
    "scenes[i].location_brief",
    "scenes[i].midground_requirements",
    "scenes[i].time_of_day",
    "scenes[i].transition_to_next",
    "scenes[i].weather",
    "shot_direction",
    "shot_direction[i].angle",
    "shot_direction[i].lighting_intent",
    "shot_direction[i].movement",
    "shot_direction[i].size",
    "sound_direction",
    "sound_direction[i].beat_id",
    "sound_direction[i].cue_id",
    "sound_direction[i].distance",
    "sound_direction[i].duration_seconds",
    "sound_direction[i].end_anchor",
    "sound_direction[i].intensity",
    "sound_direction[i].mixing_priority",
    "sound_direction[i].perspective",
    "sound_direction[i].shot_id",
    "sound_direction[i].start_anchor",
    "sound_direction[i].start_offset_seconds",
    "sound_direction[i].sync_target",
]

_VALID_CHAPTERS = [{"chapter_id": "ch-01", "scene_ids": ["sc-01"],
                    "title": "The Call"}]


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


def _valid_prop():
    """One valid important-prop entry (required fields only)."""
    return {"prop_id": "prop-boat-001", "name": "wooden boat",
            "provenance": "EXPLICIT_FROM_USER"}


def _ensure_prop(record):
    """Ensure scenes[0] carries one valid important-prop entry
    and return it."""
    scene = record["scenes"][0]
    if "important_props" not in scene:
        scene["important_props"] = [clone(_valid_prop())]
    return scene["important_props"][0]


def _ensure_asset_ref(record):
    """Ensure scenes[0] carries one valid asset reference and
    return it."""
    scene = record["scenes"][0]
    if "asset_references" not in scene:
        scene["asset_references"] = [{
            "asset_id": "asset-river-001",
            "kind": "reference-image",
            "provenance": "EXPLICIT_FROM_USER"}]
    return scene["asset_references"][0]


def _ensure_present(record, path):
    """Set a valid value for a path the short fixture does not
    carry, so the 'present' check has something to validate."""
    if path == "character_resolutions[i].cast_class":
        record["character_resolutions"][0]["cast_class"] = \
            "VISIBLE_CHARACTER"
    elif path == "character_resolutions[i].proposal_id":
        record["character_resolutions"][0]["proposal_id"] = \
            "prop-fisherman-001"
    elif path == "character_resolutions[i].registered_character_id":
        record["character_resolutions"][0]["registered_character_id"] = \
            "char-001"
    elif path == "character_resolutions[i].scene_ids":
        record["character_resolutions"][0]["scene_ids"] = ["sc-01"]
    elif path == "format_profile.chapters":
        record["format_profile"]["chapters"] = clone(_VALID_CHAPTERS)
    elif path == "format_profile.chapters[i].scene_ids":
        record["format_profile"]["chapters"] = clone(_VALID_CHAPTERS)
    elif path == "scenes[i].asset_references":
        _ensure_asset_ref(record)
    elif path == "scenes[i].asset_references[i].reference_id":
        _ensure_asset_ref(record)["reference_id"] = "ref-river-001"
    elif path == "scenes[i].atmosphere":
        record["scenes"][0]["atmosphere"] = "warm evening air"
    elif path == "scenes[i].background_design":
        record["scenes"][0]["background_design"] = \
            "riverbank with moored boats"
    elif path == "scenes[i].background_requirements":
        record["scenes"][0]["background_requirements"] = \
            "boats moored along the bank"
    elif path == "scenes[i].environment_continuity":
        record["scenes"][0]["environment_continuity"] = \
            "the river stays on the left in every shot"
    elif path == "scenes[i].foreground_requirements":
        record["scenes"][0]["foreground_requirements"] = \
            "reeds in the near foreground"
    elif path == "scenes[i].important_props":
        _ensure_prop(record)
    elif path == "scenes[i].important_props[i].approved_prop_id":
        _ensure_prop(record)["approved_prop_id"] = "prop-approved-001"
    elif path == "scenes[i].important_props[i].approved_reference_ids":
        _ensure_prop(record)["approved_reference_ids"] = ["ref-prop-01"]
    elif path == ("scenes[i].important_props[i]."
                  "continuity_restrictions"):
        _ensure_prop(record)["continuity_restrictions"] = \
            "the boat stays moored"
    elif path == "scenes[i].important_props[i].design_brief":
        _ensure_prop(record)["design_brief"] = \
            "a small wooden fishing boat"
    elif path == "scenes[i].important_props[i].physical_requirements":
        _ensure_prop(record)["physical_requirements"] = \
            "wooden, seats two"
    elif path == "scenes[i].important_props[i].provenance_note":
        _ensure_prop(record)["provenance_note"] = \
            "seen in the user's photo"
    elif path == "scenes[i].important_props[i].visual_requirements":
        _ensure_prop(record)["visual_requirements"] = \
            "weathered wood, red trim"
    elif path == "scenes[i].midground_requirements":
        record["scenes"][0]["midground_requirements"] = \
            "the river midground"
    elif path == "scenes[i].weather":
        record["scenes"][0]["weather"] = "clear evening"
    elif path == "sound_direction[i].beat_id":
        record["sound_direction"][0]["beat_id"] = "b-01"
    elif path == "sound_direction[i].cue_id":
        record["sound_direction"][0]["cue_id"] = "cue-sc01-amb-001"
    elif path == "sound_direction[i].distance":
        record["sound_direction"][0]["distance"] = "near"
    elif path == "sound_direction[i].duration_seconds":
        record["sound_direction"][0]["duration_seconds"] = 3.0
    elif path == "sound_direction[i].end_anchor":
        record["sound_direction"][0]["end_anchor"] = "BEAT_START"
    elif path == "sound_direction[i].intensity":
        record["sound_direction"][0]["intensity"] = 5
    elif path == "sound_direction[i].mixing_priority":
        record["sound_direction"][0]["mixing_priority"] = \
            "dialogue-first"
    elif path == "sound_direction[i].perspective":
        record["sound_direction"][0]["perspective"] = "on-screen"
    elif path == "sound_direction[i].shot_id":
        record["sound_direction"][0]["shot_id"] = "sh-01"
    elif path == "sound_direction[i].start_anchor":
        record["sound_direction"][0]["start_anchor"] = "SCENE_START"
    elif path == "sound_direction[i].start_offset_seconds":
        record["sound_direction"][0]["start_offset_seconds"] = 0.5
    elif path == "sound_direction[i].sync_target":
        record["sound_direction"][0]["sync_target"] = "the oar stroke"
    return record


def _null_base(path):
    """Baseline record for a nullability path. The short fixture
    is the default; registered_character_id is conditionally
    required for an 'approved' resolution, so it uses the
    missing-character fixture (a task-local proposal, where the
    field is genuinely optional)."""
    if path == "character_resolutions[i].registered_character_id":
        return missing_analysis()
    return short_analysis()


def _null_group():
    exercised = []
    for path in NULL_CASES:
        label = f"CF-P1-004-ANALYSIS-NULL: {path}"

        base = _ensure_present(clone(_null_base(path)), path)
        check(f"{label} present with a valid value passes",
              validate_production_analysis(clone(base)) == [],
              f"errors={validate_production_analysis(clone(base))}")
        omitted = _ensure_present(clone(_null_base(path)), path)
        container, leaf = _null_navigate(omitted, path)
        if leaf in container:
            del container[leaf]
        check(f"{label} omitted passes",
              validate_production_analysis(omitted) == [],
              f"errors={validate_production_analysis(omitted)}")
        nulled = _ensure_present(clone(_null_base(path)), path)
        container, leaf = _null_navigate(nulled, path)
        container[leaf] = None
        errors = validate_production_analysis(nulled)
        check(f"{label} explicit null is rejected",
              errors != [],
              "explicit null was accepted")
        exercised.append(path)

    schema = json.load(open(os.path.join(
        ROOT, "schemas", "production-analysis.json")))
    discovered = _null_optional_schema_paths(schema)
    check("CF-P1-004-ANALYSIS-NULL: declared matrix covers exactly "
          "the optional schema paths",
          set(exercised) == discovered
          and len(NULL_CASES) == 55 and len(exercised) == 55,
          f"declared={len(NULL_CASES)} exercised={len(exercised)} "
          f"discovered={len(discovered)} "
          f"missing={sorted(discovered - set(exercised))} "
          f"extra={sorted(set(exercised) - discovered)}")


# ---------------------------------------------------------------------------
# CF-P1-004-R1-A2-A4: character-resolution coverage and
# analysis-level cross-reference integrity (R1 Tasks A2/A4).
# ---------------------------------------------------------------------------

def _narrator_script():
    """The short S2P script plus a third dialogue line spoken by
    a narrator who appears in no scene and no shot."""
    script = T.script()
    script["dialogue"].append({
        "line_id": "l-03",
        "character_id": "char-narrator-001",
        "text": "Listen, and you will hear the river answer.",
        "language": "en"})
    return script


def _narrator_analysis(role=None):
    """The short analysis with 3/3 dialogue lines and a resolution
    for the narrator. ``role`` is "supporting" (presence heuristic
    only — the narrator speaks but appears in no scene and no
    shot) or "narrator" (explicit role)."""
    analysis = short_analysis()
    analysis["dialogue_preservation"][
        "source_dialogue_line_count"] = 3
    analysis["dialogue_preservation"]["mapped_line_count"] = 3
    resolution = {"character_ref": "char-narrator-001",
                  "resolution": "approved",
                  "registered_character_id": "char-narrator-001",
                  "role": role if role is not None else "supporting",
                  "provenance": "EXPLICIT_FROM_USER"}
    analysis["character_resolutions"].append(resolution)
    return analysis


def _coverage_group():
    script = T.script()

    # Empty resolutions are valid only with no visible subjects.
    empty = short_analysis()
    empty["character_resolutions"] = []
    empty["scenes"][0]["character_refs"] = []
    empty["dialogue_preservation"]["source_dialogue_line_count"] = 0
    empty["dialogue_preservation"]["mapped_line_count"] = 0
    silent_script = {"id": "script-test-001", "dialogue": [],
                     "shots": []}
    check("CF-P1-004-R1-A2: empty character_resolutions validates "
          "when the source has no visible character subjects",
          validate_production_analysis(empty, silent_script) == [],
          f"errors={validate_production_analysis(empty, silent_script)}")
    check("CF-P1-004-R1-A2: empty character_resolutions fails when "
          "the source has speaking characters",
          validate_production_analysis(empty, script) != [])

    # Missing / duplicate / unknown resolutions are rejected.
    missing_one = short_analysis()
    del missing_one["character_resolutions"][0]
    check("CF-P1-004-R1-A2: a missing resolution for a required "
          "identity fails",
          validate_production_analysis(missing_one, script) != [])
    duplicate = short_analysis()
    duplicate["character_resolutions"].append(
        clone(duplicate["character_resolutions"][0]))
    check("CF-P1-004-R1-A2: a duplicate resolution for one identity "
          "fails",
          validate_production_analysis(duplicate, script) != [])
    unknown = short_analysis()
    unknown["character_resolutions"].append({
        "character_ref": "char-ghost-001", "resolution": "approved",
        "registered_character_id": "char-ghost-001",
        "provenance": "EXPLICIT_FROM_USER"})
    check("CF-P1-004-R1-A2: a resolution for an unknown identity "
          "fails",
          validate_production_analysis(unknown, script) != [])
    scene_extra = short_analysis()
    scene_extra["scenes"][0]["character_refs"].append("char-extra-001")
    check("CF-P1-004-R1-A2: a character declared in a scene with "
          "no resolution fails",
          validate_production_analysis(scene_extra, script) != [])

    # Narrator / voice-over is not a visible character.
    narrator_script = _narrator_script()
    check("CF-P1-004-R1-A2: a narrator marked by role needs no "
          "visible-character resolution",
          validate_production_analysis(
              _narrator_analysis(role="narrator"),
              narrator_script) == [],
          f"errors={validate_production_analysis(_narrator_analysis(role='narrator'), narrator_script)}")
    check("CF-P1-004-R1-A2: a speaking identity in no scene and "
          "no shot is a voice-over, not a visible character",
          validate_production_analysis(
              _narrator_analysis(role=None),
              narrator_script) == [],
          f"errors={validate_production_analysis(_narrator_analysis(role=None), narrator_script)}")
    voice_over_only = short_analysis()
    voice_over_only["character_resolutions"].append({
        "character_ref": "char-narrator-001",
        "resolution": "approved",
        "registered_character_id": "char-narrator-001",
        "provenance": "EXPLICIT_FROM_USER"})
    check("CF-P1-004-R1-A2: the same narrator WITHOUT a speaking "
          "line is an unknown identity and fails",
          validate_production_analysis(voice_over_only, script) != [])

    # A needs-decision entry counts as a resolution at draft
    # level (the bundle build refuses undecided characters).
    undecided = short_analysis()
    undecided["character_resolutions"][0]["resolution"] = \
        "needs-decision"
    check("CF-P1-004-R1-A2: a needs-decision entry still covers "
          "its identity in the draft validator",
          validate_production_analysis(undecided, script) == [],
          f"errors={validate_production_analysis(undecided, script)}")

    # Analysis-level cross-references (A4).
    good_direction = short_analysis()
    good_direction["shot_direction"] = [{
        "shot_id": "sh-01", "scene_id": "sc-01",
        "purpose": "the decision lands",
        "size": "medium", "angle": "eye-level",
        "movement": "static",
        "lighting_intent": "soft morning light",
        "provenance": "EXPLICIT_FROM_USER"}]
    check("CF-P1-004-R1-A4: shot direction resolving to a known "
          "scene validates",
          validate_production_analysis(good_direction) == [],
          f"errors={validate_production_analysis(good_direction)}")
    bad_scene = short_analysis()
    bad_scene["shot_direction"] = [{
        "shot_id": "sh-01", "scene_id": "sc-99",
        "purpose": "the decision lands",
        "size": "medium", "angle": "eye-level",
        "movement": "static",
        "lighting_intent": "soft morning light",
        "provenance": "EXPLICIT_FROM_USER"}]
    check("CF-P1-004-R1-A4: shot direction naming an unknown "
          "scene fails",
          validate_production_analysis(bad_scene) != [])
    duplicate_direction = clone(good_direction)
    duplicate_direction["shot_direction"].append(
        clone(good_direction["shot_direction"][0]))
    check("CF-P1-004-R1-A4: duplicate shot-direction entries fail",
          validate_production_analysis(duplicate_direction) != [])
    good_cue = short_analysis()
    good_cue["sound_direction"][0]["beat_id"] = "b-01"
    check("CF-P1-004-R1-A4: a sound cue resolving to a known "
          "scene and beat validates",
          validate_production_analysis(good_cue) == [],
          f"errors={validate_production_analysis(good_cue)}")
    bad_cue_scene = short_analysis()
    bad_cue_scene["sound_direction"][0]["scene_id"] = "sc-99"
    check("CF-P1-004-R1-A4: a sound cue naming an unknown scene "
          "fails",
          validate_production_analysis(bad_cue_scene) != [])
    bad_cue_beat = short_analysis()
    bad_cue_beat["sound_direction"][0]["beat_id"] = "b-99"
    check("CF-P1-004-R1-A4: a sound cue naming an unknown beat "
          "in its scene fails",
          validate_production_analysis(bad_cue_beat) != [])


def main():
    _analysis_group()
    _coverage_group()
    _null_group()
    for session in list(_sessions):
        try:
            if is_active_session(session):
                close_session(session)
        except Exception:  # noqa: BLE001 - best-effort cleanup
            pass
    total = _checks[0]
    if failures:
        print(f"\n{len(failures)} FAILURES:")
        for name in failures:
            print(f"  FAIL {name}")
        print(f"test_production_analysis: FAIL ({total} checks)")
        return 1
    print(f"test_production_analysis: PASS ({total} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
