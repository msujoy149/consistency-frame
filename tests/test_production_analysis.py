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
    "character_resolutions[i].proposal_id",
    "character_resolutions[i].provenance_note",
    "character_resolutions[i].registered_character_id",
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
    "scenes[i].character_refs",
    "scenes[i].location_brief",
    "scenes[i].time_of_day",
    "scenes[i].transition_to_next",
    "shot_direction",
    "shot_direction[i].angle",
    "shot_direction[i].lighting_intent",
    "shot_direction[i].movement",
    "shot_direction[i].size",
    "sound_direction",
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


def _ensure_present(record, path):
    """Set a valid value for a path the short fixture does not
    carry, so the 'present' check has something to validate."""
    if path == "character_resolutions[i].proposal_id":
        record["character_resolutions"][0]["proposal_id"] = \
            "prop-fisherman-001"
    elif path == "character_resolutions[i].registered_character_id":
        record["character_resolutions"][0]["registered_character_id"] = \
            "char-001"
    elif path == "format_profile.chapters":
        record["format_profile"]["chapters"] = clone(_VALID_CHAPTERS)
    elif path == "format_profile.chapters[i].scene_ids":
        record["format_profile"]["chapters"] = clone(_VALID_CHAPTERS)
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
          and len(NULL_CASES) == 24 and len(exercised) == 24,
          f"declared={len(NULL_CASES)} exercised={len(exercised)} "
          f"discovered={len(discovered)} "
          f"missing={sorted(discovered - set(exercised))} "
          f"extra={sorted(set(exercised) - discovered)}")


def main():
    _analysis_group()
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
