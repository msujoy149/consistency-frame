#!/usr/bin/env python3
"""P0 §4 human-performance semantic tests. Run directly:
  python3 tests/test_performance_semantics.py
Exit 0 = PASS, 1 = FAIL.
Test IDs: CF-P0-PERF-001 (intensity bounds), CF-P0-PERF-002 (positive
durations / exclusiveMinimum), CF-P0-PERF-003 (emotion taxonomy),
CF-P0-PERF-004 (non-verbal events), CF-P0-PERF-005 (dialogue rewrite).

Covers the cross-field rules the restricted JSON-Schema subset cannot
express: the per-line dialogue-rewrite permission and the
"a line must speak or perform non-verbally" rule.
"""
import copy
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "validate_repo", os.path.join(ROOT, "scripts", "validate-repo.py"))
_validate_repo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_validate_repo)
validate_instance = _validate_repo.validate_instance
validate_dialogue_rewrite = _validate_repo.validate_dialogue_rewrite
validate_non_verbal_lines = _validate_repo.validate_non_verbal_lines

failures = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def load_schema(name):
    with open(os.path.join(ROOT, "schemas", name), encoding="utf-8") as f:
        return json.load(f)


def load_fixture(name):
    with open(os.path.join(ROOT, "tests", "fixtures", name), encoding="utf-8") as f:
        return json.load(f)


def schema_errors(schema, value):
    errs = []
    validate_instance(schema, value, "$", errs)
    return errs


def main():
    perf_schema = load_schema("performance-plan.json")
    scene_schema = load_schema("scene-plan.json")
    shot_schema = load_schema("shot-plan.json")
    s2p_schema = load_schema("script-to-performance.json")

    # Valid fixtures pass the schema AND the semantic checks.
    for fixture, schema in (
            ("performance-plan-valid.json", perf_schema),
            ("scene-plan-valid.json", scene_schema),
            ("shot-plan-valid.json", shot_schema),
            ("script-to-performance-valid.json", s2p_schema)):
        plan = load_fixture(fixture)
        errs = schema_errors(schema, plan)
        check(f"valid fixture {fixture} validates", not errs, "; ".join(errs))
    plan = load_fixture("performance-plan-valid.json")
    check("CF-P0-PERF-005: valid fixture passes dialogue-rewrite check",
          validate_dialogue_rewrite(plan) == [])
    check("CF-P0-PERF-004: valid fixture passes non-verbal-line check",
          validate_non_verbal_lines(plan) == [])

    # CF-P0-PERF-001: emotion intensity is 0..10 inclusive.
    for bad_intensity in (11, -1):
        bad = load_fixture("performance-plan-valid.json")
        bad["lines"][0]["emotion_intensity"] = bad_intensity
        check(f"CF-P0-PERF-001: performance intensity {bad_intensity} is rejected",
              bool(schema_errors(perf_schema, bad)))
        bad = load_fixture("scene-plan-valid.json")
        bad["scenes"][0]["beats"][0]["emotion_intensity"] = bad_intensity
        check(f"CF-P0-PERF-001: scene-beat intensity {bad_intensity} is rejected",
              bool(schema_errors(scene_schema, bad)))
    for ok_intensity in (0, 10):
        good = load_fixture("performance-plan-valid.json")
        good["lines"][0]["emotion_intensity"] = ok_intensity
        check(f"CF-P0-PERF-001: performance intensity {ok_intensity} is accepted",
              not schema_errors(perf_schema, good))

    # CF-P0-PERF-002: durations are strictly positive (exclusiveMinimum 0).
    bad = load_fixture("shot-plan-valid.json")
    bad["shots"][0]["duration_seconds"] = 0
    check("CF-P0-PERF-002: shot duration 0 is rejected",
          bool(schema_errors(shot_schema, bad)))
    bad = load_fixture("script-to-performance-valid.json")
    bad["editing_plan"]["reaction_holds"][0]["hold_seconds"] = 0
    check("CF-P0-PERF-002: reaction hold 0 is rejected",
          bool(schema_errors(s2p_schema, bad)))
    good = load_fixture("shot-plan-valid.json")
    good["shots"][0]["duration_seconds"] = 0.5
    check("CF-P0-PERF-002: shot duration 0.5 is accepted",
          not schema_errors(shot_schema, good))
    bad = load_fixture("performance-plan-valid.json")
    bad["lines"][0]["non_verbal_events"] = [
        {"type": "sigh", "duration_seconds": 0, "intensity": 3}]
    check("CF-P0-PERF-002: non-verbal event duration 0 is rejected",
          bool(schema_errors(perf_schema, bad)))

    # CF-P0-PERF-003: canonical emotion enum + open nuanced emotion.
    bad = load_fixture("performance-plan-valid.json")
    bad["lines"][0]["primary_emotion"] = "determination"
    check("CF-P0-PERF-003: primary_emotion 'determination' is rejected "
          "(moved to nuanced_emotion)",
          bool(schema_errors(perf_schema, bad)))
    bad = load_fixture("performance-plan-valid.json")
    bad["lines"][0]["primary_emotion"] = "bittersweet"
    check("CF-P0-PERF-003: unknown primary_emotion is rejected",
          bool(schema_errors(perf_schema, bad)))
    good = load_fixture("performance-plan-valid.json")
    good["lines"][0]["nuanced_emotion"] = "bittersweet"
    check("CF-P0-PERF-003: nuanced_emotion 'bittersweet' is accepted "
          "(open vocabulary)",
          not schema_errors(perf_schema, good))
    bad = load_fixture("scene-plan-valid.json")
    bad["scenes"][0]["beats"][0]["primary_emotion"] = "worry"
    check("CF-P0-PERF-003: scene-beat primary_emotion 'worry' is rejected",
          bool(schema_errors(scene_schema, bad)))
    good = load_fixture("scene-plan-valid.json")
    good["scenes"][0]["beats"][0]["secondary_emotion"] = "none"
    check("CF-P0-PERF-003: secondary_emotion 'none' is accepted",
          not schema_errors(scene_schema, good))

    # CF-P0-PERF-004: non-verbal events.
    bad = load_fixture("performance-plan-valid.json")
    bad["lines"][0]["non_verbal_events"] = [
        {"type": "screaming", "duration_seconds": 1.0, "intensity": 5}]
    check("CF-P0-PERF-004: non_verbal_events with unknown type is rejected",
          bool(schema_errors(perf_schema, bad)))
    bad = load_fixture("performance-plan-valid.json")
    bad["lines"][0]["non_verbal_events"] = [
        {"type": "crying", "duration_seconds": 2.0, "intensity": 11}]
    check("CF-P0-PERF-004: non_verbal_events intensity 11 is rejected",
          bool(schema_errors(perf_schema, bad)))
    good = load_fixture("performance-plan-valid.json")
    good["lines"][0]["non_verbal_events"] = [
        {"type": "silence", "duration_seconds": 2.0, "intensity": 0}]
    check("CF-P0-PERF-004: non_verbal_events intensity 0 is accepted",
          not schema_errors(perf_schema, good))
    # A line with no spoken text and no non-verbal events is invalid.
    bad = load_fixture("performance-plan-valid.json")
    bad["lines"][0]["dialogue"] = {"rewrite_permitted": False}
    bad["lines"][0].pop("non_verbal_events", None)
    check("CF-P0-PERF-004: line with no text and no non_verbal_events "
          "is rejected",
          bool(validate_non_verbal_lines(bad)))
    # ... but the same line with a non-verbal event is valid.
    good = copy.deepcopy(bad)
    good["lines"][0]["non_verbal_events"] = [
        {"type": "silence", "duration_seconds": 1.5, "intensity": 4}]
    check("CF-P0-PERF-004: non-verbal-only line with an event is accepted",
          validate_non_verbal_lines(good) == []
          and not schema_errors(perf_schema, good))

    # CF-P0-PERF-005: dialogue rewrite is per-line only.
    # (a) rewritten_text present + rewrite_permitted false -> invalid.
    bad = load_fixture("performance-plan-valid.json")
    bad["lines"][0]["dialogue"]["rewritten_text"] = "I will help. Come with me."
    check("CF-P0-PERF-005(a): rewritten_text with rewrite_permitted=false "
          "is rejected",
          bool(validate_dialogue_rewrite(bad)))
    # (a2) rewritten_text present + rewrite_permitted absent -> invalid.
    bad = load_fixture("performance-plan-valid.json")
    del bad["lines"][0]["dialogue"]["rewrite_permitted"]
    bad["lines"][0]["dialogue"]["rewritten_text"] = "I will help. Come with me."
    check("CF-P0-PERF-005(a): rewritten_text with rewrite_permitted absent "
          "is rejected",
          bool(validate_dialogue_rewrite(bad)))
    # (b) rewritten_text present + rewrite_permitted true -> valid.
    good = load_fixture("performance-plan-valid.json")
    good["lines"][0]["dialogue"]["rewrite_permitted"] = True
    good["lines"][0]["dialogue"]["rewritten_text"] = "I will help. Come with me."
    check("CF-P0-PERF-005(b): rewritten_text with rewrite_permitted=true "
          "is accepted",
          validate_dialogue_rewrite(good) == []
          and not schema_errors(perf_schema, good))
    # (c) rewrite_permitted true + no rewritten_text -> valid.
    good = load_fixture("performance-plan-valid.json")
    good["lines"][0]["dialogue"]["rewrite_permitted"] = True
    check("CF-P0-PERF-005(c): rewrite_permitted=true without rewritten_text "
          "is accepted",
          validate_dialogue_rewrite(good) == []
          and not schema_errors(perf_schema, good))
    # (d) rewritten_text equal to text -> valid.
    good = load_fixture("performance-plan-valid.json")
    good["lines"][0]["dialogue"]["rewrite_permitted"] = True
    good["lines"][0]["dialogue"]["rewritten_text"] = \
        good["lines"][0]["dialogue"]["text"]
    check("CF-P0-PERF-005(d): rewritten_text equal to text is accepted",
          validate_dialogue_rewrite(good) == [])
    # (e) plan-level SCRIPT_EDIT_REQUESTED does not permit a rewrite.
    bad = load_fixture("performance-plan-valid.json")
    bad["dialogue_mode"] = "SCRIPT_EDIT_REQUESTED"
    bad["lines"][0]["dialogue"]["rewritten_text"] = "I will help. Come with me."
    check("CF-P0-PERF-005(e): SCRIPT_EDIT_REQUESTED alone does not permit "
          "a rewrite",
          bool(validate_dialogue_rewrite(bad)))

    print(f"test_performance_semantics: {'PASS' if not failures else 'FAIL'} "
          f"({len(failures)} failure(s))")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
