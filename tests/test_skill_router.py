#!/usr/bin/env python3
"""CF-WO-P1-002 — deterministic runtime skill router tests.

Tests the production code in runtime/skill_router.py against the
compiled catalog (registry/routing-catalog.json): catalog integrity,
request/plan schemas, the 8 P0 routing scenarios through production
code, TC-1..TC-10 scoped conflicts (positive + negative, per-shot /
per-subject enforcement and cross-shot / cross-subject allowance),
intent-mode policy, session security, deterministic planning,
handoff packets and tamper detection.

Run: python3 tests/test_skill_router.py
Exit 0 = PASS, 1 = FAIL. Test IDs: CF-P1-002-CATALOG,
CF-P1-002-SCHEMA, CF-P1-002-ROUTING, CF-P1-002-CONFLICTS,
CF-P1-002-MODES, CF-P1-002-PLAN, CF-P1-002-SECURITY.
"""
import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

ROOT = os.path.join(os.path.dirname(__file__), "..")
ROOT_ABS = os.path.abspath(ROOT)
sys.path.insert(0, ROOT)
from runtime import local_session  # noqa: E402
from runtime.local_session import (  # noqa: E402
    close_session, is_active_session, load_or_create_profile, start_session)
from runtime.skill_router import (  # noqa: E402
    RoutingError, build_handoff_packet, build_workflow_plan,
    get_ready_steps, load_routing_catalog, plan_hash, resolve_skills,
    validate_routing_plan, validate_routing_request)

_spec = importlib.util.spec_from_file_location(
    "validate_repo", os.path.join(ROOT, "scripts", "validate-repo.py"))
_validate_repo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_validate_repo)
validate_instance = _validate_repo.validate_instance
check_schema = _validate_repo.check_schema

failures = []
_sessions = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def load_json(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


def clone(value):
    return json.loads(json.dumps(value))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def errors_for(schema, value):
    errs = []
    validate_instance(schema, value, "$", errs)
    return errs


def fresh_session(lifetime_seconds=None):
    root = tempfile.mkdtemp(prefix="cf-p1-002-")
    profile = load_or_create_profile(root)
    kwargs = {}
    if lifetime_seconds is not None:
        kwargs["lifetime_seconds"] = lifetime_seconds
    session = start_session(profile, profile.workspace_id, **kwargs)
    _sessions.append(session)
    return session


def request(task_id, mode, profile=None, hints=None, **extra):
    req = {"schema_version": "2.4", "task_id": task_id,
           "intent_mode": mode}
    if profile is not None:
        req["production_profile"] = profile
    if hints is not None:
        req["hints"] = hints
    req.update(extra)
    return req


def subject_id(profile, index=0):
    return profile["per_subject_overrides"][index]["character_id"]


CATALOG = load_routing_catalog()
PROFILES = {
    "s1": load_json("tests/fixtures/routing-profile-s1-explainer-2d.json"),
    "s2": load_json("tests/fixtures/routing-profile-s2-stylized-3d.json"),
    "s3": load_json("tests/fixtures/production-profile-valid-digital-human.json"),
    "s4": load_json("tests/fixtures/routing-profile-s4-human-bird.json"),
    "s5": load_json("tests/fixtures/routing-profile-s5-live-action-creature.json"),
    "s6": load_json("tests/fixtures/routing-profile-s6-real-animal.json"),
    "s7": load_json("tests/fixtures/routing-profile-s7-video-to-video.json"),
    "s8": load_json("tests/fixtures/routing-profile-s8-photorealistic-explainer.json"),
}
BASE_LAYERS = {"command-authority", "production-systems",
               "humanized-production"}


def main():
    # --- CF-P1-002-CATALOG: the compiled catalog ----------------------
    check("CF-P1-002-CATALOG: catalog version is 2.4",
          CATALOG.get("catalog_version") == "2.4")
    check("CF-P1-002-CATALOG: catalog lists all 15 skills",
          len(CATALOG.get("skills") or []) == 15)
    check("CF-P1-002-CATALOG: precedence values are unique 1..15",
          sorted(e["precedence"] for e in CATALOG["skills"])
          == list(range(1, 16)))
    check("CF-P1-002-CATALOG: command-authority is precedence 1",
          next(e for e in CATALOG["skills"]
               if e["skill"] == "command-authority")["precedence"] == 1)
    sources_ok = True
    for rel, info in (CATALOG.get("sources") or {}).items():
        live = sha256_file(os.path.join(ROOT, rel))
        if live != info.get("sha256"):
            sources_ok = False
    check("CF-P1-002-CATALOG: source SHA-256 values match the live YAML files",
          sources_ok and len(CATALOG.get("sources") or {}) == 5,
          f"sources={sorted((CATALOG.get('sources') or {}).keys())}")
    fingerprints_ok = True
    for entry in CATALOG["skills"]:
        live = sha256_file(os.path.join(ROOT, entry["path"]))
        if live != entry.get("sha256"):
            fingerprints_ok = False
    check("CF-P1-002-CATALOG: skill fingerprints match the live SKILL.md files",
          fingerprints_ok)
    check("CF-P1-002-CATALOG: skill paths are skills/<slug>/SKILL.md",
          all(e["path"] == f"skills/{e['skill']}/SKILL.md"
              for e in CATALOG["skills"]))
    vocab = CATALOG.get("vocabularies") or {}
    check("CF-P1-002-CATALOG: visual_style vocabulary has 12 values",
          len(vocab.get("visual_style") or []) == 12)
    check("CF-P1-002-CATALOG: vocabularies cover all 7 dimensions",
          all(vocab.get(k) for k in (
              "visual_style", "production_medium", "source_media",
              "motion_method", "subject_kind", "interaction_pattern",
              "articulation_target")))
    check("CF-P1-002-CATALOG: cinematic styles are the 5 style-lock styles",
          sorted(vocab.get("cinematic_styles") or []) == [
              "anime", "cartoon-2d", "photorealistic-3d-cgi",
              "semi-realistic-3d", "stylized-3d"])
    graph = CATALOG.get("graph") or {}
    check("CF-P1-002-CATALOG: graph has 15 nodes and 42 edges",
          len(graph.get("nodes") or []) == 15
          and len(graph.get("edges") or []) == 42,
          f"nodes={len(graph.get('nodes') or [])} "
          f"edges={len(graph.get('edges') or [])}")
    check("CF-P1-002-CATALOG: graph has 4 parallel groups",
          len(graph.get("parallel_groups") or []) == 4)
    check("CF-P1-002-CATALOG: graph has the conditional existing-character-prep group",
          [g["name"] for g in
           (graph.get("conditional_parallel_groups") or [])]
          == ["existing-character-prep"])
    check("CF-P1-002-CATALOG: graph has TC-1..TC-10",
          [tc["id"] for tc in (graph.get("true_conflicts") or [])]
          == [f"TC-{i}" for i in range(1, 11)])
    check("CF-P1-002-CATALOG: catalog lists 13 intent modes",
          len(CATALOG.get("intent_modes") or {}) == 13)
    check("CF-P1-002-CATALOG: catalog lists 2 companions, 10 agents",
          len(CATALOG.get("companions") or []) == 2
          and len(CATALOG.get("agents") or []) == 10)
    # The compiler's --check must pass against the committed catalog.
    proc = subprocess.run(
        [sys.executable, "scripts/generate-routing-catalog.py", "--check"],
        cwd=ROOT_ABS, capture_output=True, text=True)
    check("CF-P1-002-CATALOG: generate-routing-catalog.py --check passes",
          proc.returncode == 0, proc.stdout.strip() + proc.stderr.strip())
    # A tampered catalog is refused at load.
    tampered = clone(CATALOG)
    tampered["catalog_version"] = "9.9"
    with tempfile.NamedTemporaryFile("w", suffix=".json",
                                    delete=False) as f:
        json.dump(tampered, f)
        bad_path = f.name
    try:
        load_routing_catalog(bad_path)
        check("CF-P1-002-CATALOG: wrong catalog version is refused",
              False, "loaded instead of refusing")
    except RoutingError:
        check("CF-P1-002-CATALOG: wrong catalog version is refused", True)
    finally:
        os.unlink(bad_path)
    tampered = clone(CATALOG)
    tampered["skills"][0]["precedence"] = 2
    with tempfile.NamedTemporaryFile("w", suffix=".json",
                                    delete=False) as f:
        json.dump(tampered, f)
        bad_path = f.name
    try:
        load_routing_catalog(bad_path)
        check("CF-P1-002-CATALOG: duplicate precedence is refused",
              False, "loaded instead of refusing")
    except RoutingError:
        check("CF-P1-002-CATALOG: duplicate precedence is refused", True)
    finally:
        os.unlink(bad_path)

    # --- CF-P1-002-SCHEMA: request + plan schemas ---------------------
    req_schema = load_json("schemas/skill-routing-request.json")
    plan_schema = load_json("schemas/skill-routing-plan.json")
    for name, schema in (("skill-routing-request.json", req_schema),
                         ("skill-routing-plan.json", plan_schema)):
        errs: list[str] = []
        check_schema(schema, f"schemas/{name}", errs)
        check(f"CF-P1-002-SCHEMA: {name} satisfies the validator subset",
              not errs, "; ".join(errs))
        check(f"CF-P1-002-SCHEMA: {name} is schema version 2.4",
              schema.get("properties", {}).get(
                  "schema_version", {}).get("enum") == ["2.4"])
    check("CF-P1-002-SCHEMA: request intent_mode enum is the 13 modes",
          sorted(req_schema["properties"]["intent_mode"]["enum"])
          == sorted(CATALOG["intent_modes"].keys()))
    check("CF-P1-002-SCHEMA: plan intent_mode enum is the 13 modes",
          sorted(plan_schema["properties"]["intent_mode"]["enum"])
          == sorted(CATALOG["intent_modes"].keys()))
    valid_req = request(
        "schema-valid-001", "GENERATE_FROM_SCRIPT", PROFILES["s3"],
        {"dialogue": True, "languages": ["bn"],
         "recurring_character": True, "consent": True})
    check("CF-P1-002-SCHEMA: a valid request validates against the schema",
          not errors_for(req_schema, valid_req),
          "; ".join(errors_for(req_schema, valid_req)))
    bad_req = clone(valid_req)
    bad_req["surprise_field"] = True
    check("CF-P1-002-SCHEMA: a request with an unknown field is rejected",
          bool(errors_for(req_schema, bad_req)))
    bad_req = clone(valid_req)
    bad_req["intent_mode"] = "DO_ANYTHING"
    check("CF-P1-002-SCHEMA: a request with an unknown mode is rejected",
          bool(errors_for(req_schema, bad_req)))
    bad_req = clone(valid_req)
    bad_req["task_id"] = ""
    check("CF-P1-002-SCHEMA: a request with an empty task_id is rejected",
          bool(errors_for(req_schema, bad_req)))
    bad_req = clone(valid_req)
    bad_req["production_profile"] = {
        k: v for k, v in PROFILES["s3"].items() if k != "visual_style"}
    check("CF-P1-002-SCHEMA: a profile without visual_style is rejected",
          bool(errors_for(req_schema, bad_req)))
    # The router's structural validation must agree with the schema
    # on structural cases (the router additionally enforces semantics
    # the schema cannot express).
    structural_cases = [
        ("valid request", valid_req, True),
        ("unknown top-level field", {**valid_req, "nope": 1}, False),
        ("unknown mode", {**valid_req, "intent_mode": "DO_ANYTHING"}, False),
        ("empty task_id", {**valid_req, "task_id": ""}, False),
        ("unknown skill in additional_layers",
         {**valid_req, "additional_layers": ["not-a-skill"]}, False),
    ]
    for label, req, should_pass in structural_cases:
        schema_errs = errors_for(req_schema, req)
        router_errs = validate_routing_request(req, CATALOG)
        agree = (not schema_errs) == (not router_errs) == should_pass
        check(f"CF-P1-002-SCHEMA: router and schema agree — {label}",
              agree,
              f"schema_errs={schema_errs} router_errs={router_errs}")
    # Semantic rejections live in the router only: the schema allows
    # any skill slug as a pathway, the router refuses the two that
    # cannot be one (the router is the router; resource-management is
    # cross-cutting, never a pathway).
    for label, pathway in (
            ("resource-management as primary pathway",
             "resource-management"),
            ("command-authority as primary pathway", "command-authority")):
        req = {**valid_req, "primary_pathway": pathway}
        check(f"CF-P1-002-SCHEMA: router refuses — {label}",
              bool(validate_routing_request(req, CATALOG)))

    # --- CF-P1-002-ROUTING: the 8 P0 scenarios, production code ------
    scenarios = {
        "s1": ({"dialogue": True, "languages": ["en"],
                "recurring_character": True, "explainer_structure": True},
               BASE_LAYERS | {"character-consistency", "voice-consistency",
                              "explainer-animation"},
               "GENERATE_FROM_SCRIPT", {}),
        "s2": ({"dialogue": True, "languages": ["en"],
                "recurring_character": True},
               BASE_LAYERS | {"character-consistency", "voice-consistency",
                              "cinematic-power"},
               "GENERATE_FROM_SCRIPT", {}),
        "s3": ({"dialogue": True, "languages": ["bn"],
                "recurring_character": True, "consent": True},
               BASE_LAYERS | {"character-consistency", "voice-consistency",
                              "language-authenticity", "realistic-person"},
               "GENERATE_FROM_SCRIPT", {}),
        "s4": ({"dialogue": True, "languages": ["en"],
                "recurring_character": True, "consent": True},
               BASE_LAYERS | {"character-consistency", "voice-consistency",
                              "cinematic-power", "realistic-person"},
               "GENERATE_FROM_SCRIPT", {}),
        "s5": ({"dialogue": True, "languages": ["en"],
                "recurring_character": True},
               BASE_LAYERS | {"character-consistency", "voice-consistency",
                              "cinematic-power", "live-action-vfx"},
               "GENERATE_FROM_SCRIPT", {}),
        "s6": ({},
               BASE_LAYERS | {"live-action-vfx"},
               "GENERATE_FROM_SCRIPT", {}),
        # S7 is a video-to-video remake, so its production mode is
        # REMAKE_OR_TRANSFORM (video-regeneration is not applicable in
        # GENERATE_FROM_SCRIPT) with the mode's required evidence.
        "s7": ({"dialogue": True, "languages": ["en"],
                "recurring_character": True},
               BASE_LAYERS | {"character-consistency", "voice-consistency",
                              "cinematic-power", "video-regeneration"},
               "REMAKE_OR_TRANSFORM",
               {"explicit_request": True,
                "rights_provenance_checked": True}),
        "s8": ({"dialogue": True, "languages": ["en"],
                "recurring_character": True, "explainer_structure": True,
                "consent": True},
               BASE_LAYERS | {"character-consistency", "voice-consistency",
                              "realistic-person"},
               "GENERATE_FROM_SCRIPT", {}),
    }
    resolved = {}
    for key, (hints, expected, mode, extra) in scenarios.items():
        req = request(f"routing-{key}", mode, PROFILES[key], hints, **extra)
        try:
            res = resolve_skills(req, CATALOG)
        except RoutingError as exc:
            check(f"CF-P1-002-ROUTING: scenario {key} resolves", False,
                  str(exc))
            continue
        resolved[key] = res
        check(f"CF-P1-002-ROUTING: scenario {key} selects exactly the "
              "expected skills",
              res["skills"] == expected,
              f"got={sorted(res['skills'])} expected={sorted(expected)}")
        check(f"CF-P1-002-ROUTING: scenario {key} is not blocked",
              res["blocked"] == [], f"blocked={res['blocked']}")
    # Scenario-specific proofs (the same proofs test_routing checks,
    # now through production code).
    if "s1" in resolved:
        check("CF-P1-002-ROUTING: (1) style is flat-2d-vector, not a "
              "default cartoon",
              resolved["s1"]["styles"] == {"flat-2d-vector"})
    if "s3" in resolved:
        check("CF-P1-002-ROUTING: (3) profile is not live-action footage "
              "and style is photorealistic-digital-human",
              PROFILES["s3"]["is_live_action_footage"] is False
              and resolved["s3"]["styles"]
              == {"photorealistic-digital-human"})
    if "s4" in resolved:
        check("CF-P1-002-ROUTING: (4) realistic-person AND cinematic-power "
              "run together (human + creature performance)",
              {"realistic-person", "cinematic-power"}
              <= resolved["s4"]["skills"])
    if "s5" in resolved:
        check("CF-P1-002-ROUTING: (5) realistic-person excluded (the "
              "human is real footage)",
              "realistic-person" not in resolved["s5"]["skills"])
    if "s6" in resolved:
        check("CF-P1-002-ROUTING: (6) no CG skill forced onto a real animal",
              not ({"cinematic-power", "realistic-person",
                    "explainer-animation"} & resolved["s6"]["skills"]))
    if "s7" in resolved:
        check("CF-P1-002-ROUTING: (7) output style stylized-3d from a "
              "reference-video source",
              resolved["s7"]["visual_style"] == "stylized-3d"
              and resolved["s7"]["source_media_type"] == "reference-video")
    if "s8" in resolved:
        check("CF-P1-002-ROUTING: (8) explainer-animation NOT selected for "
              "a photorealistic explainer",
              "explainer-animation" not in resolved["s8"]["skills"])
    # Incompatible operations are still refused (the P0 refusal cases).
    for label, prof, hints, mode, extra in (
            ("single animation_type enum",
             load_json("tests/fixtures/production-profile-invalid-animation-type.json"),
             {"dialogue": True, "consent": True}, "GENERATE_FROM_SCRIPT", {}),
            ("generated digital human labelled live-action",
             load_json("tests/fixtures/production-profile-invalid-digital-human-live-action.json"),
             {"dialogue": True, "consent": True}, "GENERATE_FROM_SCRIPT", {}),
            ("realistic-person without a consent record",
             PROFILES["s3"],
             {"dialogue": True, "languages": ["bn"],
              "recurring_character": True}, "GENERATE_FROM_SCRIPT", {}),
            ("flat 2D vector + captured live-action in one shot",
             {**PROFILES["s1"], "is_live_action_footage": True,
              "source_media_type": "captured-footage"},
             {"dialogue": True, "recurring_character": True,
              "explainer_structure": True}, "GENERATE_FROM_SCRIPT", {}),
    ):
        req = request(f"refuse-{label[:8]}", mode, prof, hints, **extra)
        try:
            resolve_skills(req, CATALOG)
            check(f"CF-P1-002-ROUTING: incompatible operation refused — "
                  f"{label}", False, "resolved instead of refusing")
        except RoutingError:
            check(f"CF-P1-002-ROUTING: incompatible operation refused — "
                  f"{label}", True)
    bird_lips = clone(PROFILES["s4"])
    for sub in bird_lips["per_subject_overrides"]:
        if sub["character_id"] == subject_id(PROFILES["s4"], 1):
            sub["articulation_target"] = "human-mouth-lips"
    try:
        resolve_skills(request(
            "refuse-bird", "GENERATE_FROM_SCRIPT", bird_lips,
            {"dialogue": True, "recurring_character": True,
             "consent": True}), CATALOG)
        check("CF-P1-002-ROUTING: incompatible operation refused — bird "
              "with human-mouth-lips articulation", False,
              "resolved instead of refusing")
    except RoutingError:
        check("CF-P1-002-ROUTING: incompatible operation refused — bird "
              "with human-mouth-lips articulation", True)
    try:
        resolve_skills(request(
            "refuse-nostyle", "GENERATE_FROM_SCRIPT",
            {k: v for k, v in PROFILES["s3"].items()
             if k != "visual_style"},
            {"dialogue": True}), CATALOG)
        check("CF-P1-002-ROUTING: profile without visual_style is refused "
              "(no cartoon default)", False, "resolved without a style")
    except RoutingError:
        check("CF-P1-002-ROUTING: profile without visual_style is refused "
              "(no cartoon default)", True)
    # Precedence invariant across every scenario: a selected skill
    # never depends on a later-precedence skill.
    prec_by_skill = {e["skill"]: e["precedence"] for e in CATALOG["skills"]}
    deps_by_skill = {e["skill"]: set(e.get("dependencies") or [])
                     for e in CATALOG["skills"]}
    prec_ok = all(
        prec_by_skill.get(d, 99) < prec_by_skill[s]
        for res in resolved.values() for s in res["skills"]
        for d in deps_by_skill.get(s, set()) if d in res["skills"])
    check("CF-P1-002-ROUTING: every scenario respects matrix precedence "
          "(dependencies run earlier)", prec_ok)
    # A request with dialogue but no recurring character selects voice
    # without forcing character-consistency: dependencies order, they
    # do not expand the selection.
    res = resolve_skills(request(
        "dialogue-only", "GENERATE_FROM_SCRIPT", PROFILES["s2"],
        {"dialogue": True, "languages": ["en"]}), CATALOG)
    check("CF-P1-002-ROUTING: dialogue without a recurring character "
          "selects voice-consistency without forcing character-consistency",
          "voice-consistency" in res["skills"]
          and "character-consistency" not in res["skills"],
          f"got={sorted(res['skills'])}")

    # --- CF-P1-002-CONFLICTS: TC-1..TC-10, positive + negative -------
    def blocked_rules(res):
        return {item["rule_id"] for item in res["blocked"]}

    def blocked_item(res, rule_id):
        for item in res["blocked"]:
            if item["rule_id"] == rule_id:
                return item
        return None

    human_s3 = subject_id(PROFILES["s3"], 0)
    human_s4 = subject_id(PROFILES["s4"], 0)
    bird_s4 = subject_id(PROFILES["s4"], 1)
    fox_s6 = subject_id(PROFILES["s6"], 0)
    # TC-2 positive: live-action-vfx forced onto the digital-human
    # subject in the same shot as realistic-person.
    res = resolve_skills(request(
        "tc2-plus", "GENERATE_FROM_SCRIPT", PROFILES["s3"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "consent": True},
        requested_skills=[{"skill": "live-action-vfx",
                           "source": "user-request",
                           "scope": {"shots": ["shot-01"],
                                     "subjects": [human_s3]}}]), CATALOG)
    item = blocked_item(res, "TC-2")
    check("CF-P1-002-CONFLICTS: TC-2 fires for live-action-vfx + "
          "realistic-person on one subject in one shot",
          item is not None and item["subject_id"] == human_s3
          and item["shot_id"] == "shot-01"
          and set(item["skills"]) == {"live-action-vfx", "realistic-person"}
          and item["required_input"],
          f"blocked={res['blocked']}")
    check("CF-P1-002-CONFLICTS: TC-2 never silently removes either skill",
          {"live-action-vfx", "realistic-person"} <= res["skills"])
    # TC-2 negative: the same two skills in different shots stay allowed.
    res = resolve_skills(request(
        "tc2-minus", "GENERATE_FROM_SCRIPT", PROFILES["s3"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "consent": True},
        subjects=[{"subject_id": human_s3, "shots": ["shot-01"]}],
        requested_skills=[{"skill": "live-action-vfx",
                           "source": "user-request",
                           "scope": {"shots": ["shot-02"]}}]), CATALOG)
    check("CF-P1-002-CONFLICTS: TC-2 allows the same two skills in "
          "different shots",
          "TC-2" not in blocked_rules(res), f"blocked={res['blocked']}")
    # TC-4 positive: explainer-animation forced onto the digital-human
    # subject in the same shot as realistic-person.
    res = resolve_skills(request(
        "tc4-plus", "GENERATE_FROM_SCRIPT", PROFILES["s3"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "consent": True},
        requested_skills=[{"skill": "explainer-animation",
                           "source": "user-request",
                           "scope": {"shots": ["shot-01"],
                                     "subjects": [human_s3]}}]), CATALOG)
    item = blocked_item(res, "TC-4")
    check("CF-P1-002-CONFLICTS: TC-4 fires for explainer-animation + "
          "realistic-person on one subject in one shot",
          item is not None and item["subject_id"] == human_s3
          and item["shot_id"] == "shot-01",
          f"blocked={res['blocked']}")
    # TC-4 negative: explainer on a different subject stays allowed.
    res = resolve_skills(request(
        "tc4-minus", "GENERATE_FROM_SCRIPT", PROFILES["s4"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "consent": True},
        requested_skills=[{"skill": "explainer-animation",
                           "source": "user-request",
                           "scope": {"subjects": [bird_s4]}}]), CATALOG)
    check("CF-P1-002-CONFLICTS: TC-4 allows explainer-animation on a "
          "different subject",
          "TC-4" not in blocked_rules(res), f"blocked={res['blocked']}")
    # TC-1 positive: a REAL animal directed to speak.
    res = resolve_skills(request(
        "tc1-plus", "GENERATE_FROM_SCRIPT", PROFILES["s6"],
        {"dialogue": True},
        subjects=[{"subject_id": fox_s6, "speaking": True}],
        requested_skills=[{"skill": "cinematic-power",
                           "source": "user-request",
                           "scope": {"subjects": [fox_s6]}}]), CATALOG)
    item = blocked_item(res, "TC-1")
    check("CF-P1-002-CONFLICTS: TC-1 fires for a real animal directed to "
          "speak (live-action-vfx + cinematic-power)",
          item is not None and item["subject_id"] == fox_s6,
          f"blocked={res['blocked']}")
    # TC-1 negative: the real animal is not directed to speak (s6),
    # and a CGI creature speaking (s5) is creature performance.
    check("CF-P1-002-CONFLICTS: TC-1 does not fire for non-speaking "
          "real-animal footage",
          "TC-1" not in blocked_rules(resolved["s6"]))
    check("CF-P1-002-CONFLICTS: TC-1 does not fire for a speaking CGI "
          "creature (s5)",
          "TC-1" not in blocked_rules(resolved["s5"]))
    # TC-3 positive: two style locks on one named shot.
    res = resolve_skills(request(
        "tc3-plus", "GENERATE_FROM_SCRIPT", PROFILES["s1"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "explainer_structure": True},
        shots=[{"shot_id": "shot-01", "visual_style": "flat-2d-vector"}],
        requested_skills=[{"skill": "cinematic-power",
                           "source": "user-request",
                           "scope": {"shots": ["shot-01"]}}]), CATALOG)
    item = blocked_item(res, "TC-3")
    check("CF-P1-002-CONFLICTS: TC-3 fires for flat-2D + cinematic style "
          "locks on one shot",
          item is not None and item["shot_id"] == "shot-01",
          f"blocked={res['blocked']}")
    # TC-3 negative: the two locks on different shots stay allowed.
    res = resolve_skills(request(
        "tc3-minus", "GENERATE_FROM_SCRIPT", PROFILES["s1"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "explainer_structure": True},
        shots=[{"shot_id": "shot-01", "visual_style": "flat-2d-vector"},
               {"shot_id": "shot-02", "visual_style": "stylized-3d"}],
        requested_skills=[{"skill": "cinematic-power",
                           "source": "user-request",
                           "scope": {"shots": ["shot-02"]}}]), CATALOG)
    check("CF-P1-002-CONFLICTS: TC-3 allows the two style locks on "
          "different shots",
          "TC-3" not in blocked_rules(res), f"blocked={res['blocked']}")
    # TC-5 positive / negative (explainer vs kids-family style locks).
    res = resolve_skills(request(
        "tc5-plus", "GENERATE_FROM_SCRIPT", PROFILES["s1"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "explainer_structure": True},
        shots=[{"shot_id": "shot-01", "visual_style": "flat-2d-vector"}],
        requested_skills=[{"skill": "kids-family-animation",
                           "source": "user-request",
                           "scope": {"shots": ["shot-01"]}}]), CATALOG)
    item = blocked_item(res, "TC-5")
    check("CF-P1-002-CONFLICTS: TC-5 fires for flat-2D explainer + kids "
          "style lock on one shot",
          item is not None and item["shot_id"] == "shot-01",
          f"blocked={res['blocked']}")
    res = resolve_skills(request(
        "tc5-minus", "GENERATE_FROM_SCRIPT", PROFILES["s1"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "explainer_structure": True},
        shots=[{"shot_id": "shot-01", "visual_style": "flat-2d-vector"},
               {"shot_id": "shot-02", "visual_style": "stylized-3d"}],
        requested_skills=[{"skill": "kids-family-animation",
                           "source": "user-request",
                           "scope": {"shots": ["shot-02"]}}]), CATALOG)
    check("CF-P1-002-CONFLICTS: TC-5 allows the two style locks on "
          "different shots",
          "TC-5" not in blocked_rules(res), f"blocked={res['blocked']}")
    # TC-6 positive / negative (kids vs realistic-person, same subject).
    res = resolve_skills(request(
        "tc6-plus", "GENERATE_FROM_SCRIPT", PROFILES["s3"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "consent": True},
        requested_skills=[{"skill": "kids-family-animation",
                           "source": "user-request",
                           "scope": {"shots": ["shot-01"],
                                     "subjects": [human_s3]}}]), CATALOG)
    check("CF-P1-002-CONFLICTS: TC-6 fires for kids-family-animation + "
          "realistic-person on one subject",
          blocked_item(res, "TC-6") is not None,
          f"blocked={res['blocked']}")
    res = resolve_skills(request(
        "tc6-minus", "GENERATE_FROM_SCRIPT", PROFILES["s4"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "consent": True},
        requested_skills=[{"skill": "kids-family-animation",
                           "source": "user-request",
                           "scope": {"subjects": [bird_s4]}}]), CATALOG)
    check("CF-P1-002-CONFLICTS: TC-6 allows kids-family-animation on a "
          "different subject",
          "TC-6" not in blocked_rules(res), f"blocked={res['blocked']}")
    # TC-7 positive: animation styling on a digital-human subject.
    s3_animated = clone(PROFILES["s3"])
    s3_animated["visual_style"] = "stylized-3d"
    s3_animated["per_subject_overrides"][0]["rendering_style"] = "stylized-3d"
    res = resolve_skills(request(
        "tc7-plus", "GENERATE_FROM_SCRIPT", s3_animated,
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "consent": True}), CATALOG)
    item = blocked_item(res, "TC-7")
    check("CF-P1-002-CONFLICTS: TC-7 fires for 2D/3D-animation styling on "
          "a photorealistic digital-human subject",
          item is not None and item["subject_id"] == human_s3,
          f"blocked={res['blocked']}")
    check("CF-P1-002-CONFLICTS: TC-7 does not fire for s4 (human "
          "photorealistic + bird creature performance)",
          "TC-7" not in blocked_rules(resolved["s4"]))
    # TC-8 positive / negative (synthetic spokesperson vs real person).
    res = resolve_skills(request(
        "tc8-plus", "GENERATE_FROM_SCRIPT", PROFILES["s3"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "consent": True},
        requested_skills=[{"skill": "agency-advertising",
                           "source": "user-request",
                           "scope": {"subjects": [human_s3]}}]), CATALOG)
    check("CF-P1-002-CONFLICTS: TC-8 fires for agency-advertising + "
          "realistic-person on one subject",
          blocked_item(res, "TC-8") is not None,
          f"blocked={res['blocked']}")
    res = resolve_skills(request(
        "tc8-minus", "GENERATE_FROM_SCRIPT", PROFILES["s4"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "consent": True},
        requested_skills=[{"skill": "agency-advertising",
                           "source": "user-request",
                           "scope": {"subjects": [bird_s4]}}]), CATALOG)
    check("CF-P1-002-CONFLICTS: TC-8 allows agency-advertising on a "
          "different subject",
          "TC-8" not in blocked_rules(res), f"blocked={res['blocked']}")
    # TC-9 positive / negative (flat-2D explainer vs live footage).
    s1_live_shot = clone(PROFILES["s1"])
    s1_live_shot["per_shot_overrides"] = [
        {"shot_id": "shot-01", "visual_style": "flat-2d-vector",
         "is_live_action_footage": True}]
    s1_live_shot["per_subject_overrides"].append(
        {"character_id": "char-plate-001", "subject_kind": "human",
         "representation": "live-action-footage",
         "source_media": "captured-footage",
         "is_live_action_footage": True})
    res = resolve_skills(request(
        "tc9-plus", "GENERATE_FROM_SCRIPT", s1_live_shot,
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "explainer_structure": True}),
        CATALOG)
    check("CF-P1-002-CONFLICTS: TC-9 fires for flat-2D explainer + live "
          "footage in one shot",
          blocked_item(res, "TC-9") is not None,
          f"blocked={res['blocked']}")
    s1_live_other = clone(PROFILES["s1"])
    s1_live_other["per_shot_overrides"] = [
        {"shot_id": "shot-01", "visual_style": "flat-2d-vector"},
        {"shot_id": "shot-02", "visual_style": "captured-live-action",
         "is_live_action_footage": True}]
    s1_live_other["per_subject_overrides"].append(
        {"character_id": "char-plate-001", "subject_kind": "human",
         "representation": "live-action-footage",
         "source_media": "captured-footage",
         "is_live_action_footage": True})
    res = resolve_skills(request(
        "tc9-minus", "GENERATE_FROM_SCRIPT", s1_live_other,
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "explainer_structure": True}),
        CATALOG)
    check("CF-P1-002-CONFLICTS: TC-9 allows flat-2D and live footage in "
          "different shots",
          "TC-9" not in blocked_rules(res), f"blocked={res['blocked']}")
    # TC-10 positive: a bird line with human lip movement.
    res = resolve_skills(request(
        "tc10-plus", "GENERATE_FROM_SCRIPT", PROFILES["s4"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "consent": True},
        dialogue_lines=[{"line_id": "line-01", "subject_id": bird_s4,
                         "shot_id": "shot-01",
                         "articulation_target": "human-mouth-lips"}]),
        CATALOG)
    item = blocked_item(res, "TC-10")
    check("CF-P1-002-CONFLICTS: TC-10 fires for human lips on a bird line",
          item is not None and item["subject_id"] == bird_s4
          and item["shot_id"] == "shot-01",
          f"blocked={res['blocked']}")
    # TC-10 negative: the same line with bird-beak, and s4 as-is.
    res = resolve_skills(request(
        "tc10-minus", "GENERATE_FROM_SCRIPT", PROFILES["s4"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "consent": True},
        dialogue_lines=[{"line_id": "line-01", "subject_id": bird_s4,
                         "shot_id": "shot-01",
                         "articulation_target": "bird-beak"},
                        {"line_id": "line-02", "subject_id": human_s4,
                         "shot_id": "shot-01",
                         "articulation_target": "human-mouth-lips"}]),
        CATALOG)
    check("CF-P1-002-CONFLICTS: TC-10 allows matching articulation per "
          "subject per line",
          "TC-10" not in blocked_rules(res), f"blocked={res['blocked']}")
    res = resolve_skills(request(
        "tc10-other", "GENERATE_FROM_SCRIPT", PROFILES["s4"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "consent": True},
        dialogue_lines=[{"line_id": "line-01", "subject_id": bird_s4,
                         "shot_id": "shot-01",
                         "articulation_target": "other"}]), CATALOG)
    check("CF-P1-002-CONFLICTS: TC-10 allows an explicitly non-anatomical "
          "'other' articulation",
          "TC-10" not in blocked_rules(res), f"blocked={res['blocked']}")
    # TC-10 fails closed: a speaking subject whose anatomy cannot be
    # established from the supplied information.
    res = resolve_skills(request(
        "tc10-unknown", "GENERATE_FROM_SCRIPT", PROFILES["s6"],
        {"dialogue": True},
        subjects=[{"subject_id": "char-mystery-001", "speaking": True}]),
        CATALOG)
    check("CF-P1-002-CONFLICTS: TC-10 fails closed when a speaking "
          "subject's anatomy cannot be established",
          blocked_item(res, "TC-10") is not None,
          f"blocked={res['blocked']}")

    # --- CF-P1-002-MODES: intent-mode policy --------------------------
    session = fresh_session()
    # UPLOAD_ONLY and REPORT_UPDATE_ONLY never route production.
    for mode in ("UPLOAD_ONLY", "REPORT_UPDATE_ONLY"):
        plan = build_workflow_plan(session, request(
            f"mode-{mode.lower()}", mode, PROFILES["s3"],
            {"dialogue": True}), CATALOG)
        check(f"CF-P1-002-MODES: {mode} never routes production",
              plan["status"] == "blocked" and not plan["steps"]
              and plan["blocked_diagnostics"]
              and plan["blocked_diagnostics"][0]["code"]
              == "mode-does-not-route-production",
              f"status={plan['status']}")
        check(f"CF-P1-002-MODES: {mode} blocked plan validates",
              not validate_routing_plan(plan, CATALOG))
    # TEMPORARY_ASSET_USE: voice-consistency is not applicable there.
    plan = build_workflow_plan(session, request(
        "mode-temp-voice", "TEMPORARY_ASSET_USE", PROFILES["s3"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "consent": True}), CATALOG)
    check("CF-P1-002-MODES: TEMPORARY_ASSET_USE with dialogue is blocked "
          "(voice-consistency is not applicable there)",
          plan["status"] == "blocked"
          and "voice-consistency" in
          plan["blocked_diagnostics"][0]["message"],
          f"diagnostics={plan['blocked_diagnostics']}")
    # TEMPORARY_ASSET_USE without dialogue: a silent digital human is
    # allowed, temporary-only, with the non-applicable dependencies
    # recorded per the mode's documented scope.
    plan = build_workflow_plan(session, request(
        "mode-temp-silent", "TEMPORARY_ASSET_USE", PROFILES["s3"],
        {"recurring_character": True, "consent": True}), CATALOG)
    check("CF-P1-002-MODES: TEMPORARY_ASSET_USE silent plan is ready and "
          "temporary-only",
          plan["status"] == "ready" and plan["temporary_only"] is True,
          f"status={plan['status']}")
    check("CF-P1-002-MODES: TEMPORARY_ASSET_USE records the "
          "non-applicable dependencies per mode scope",
          any("voice-consistency" in c and "not applicable in "
              "TEMPORARY_ASSET_USE" in c for c in plan["constraints"]),
          f"constraints={plan['constraints']}")
    # Registration modes are plan-only and need their evidence.
    for mode, evidence, chain in (
            ("REGISTER_CHARACTER",
             {"explicit_authorisation": True, "name": "Nila",
              "unique_id": "char-nila-001", "approved_reference": True},
             ["command-authority", "character-consistency"]),
            ("REGISTER_VOICE_PROFILE",
             {"explicit_authorisation": True, "rights_consent": True,
              "character_link": "char-nila-001", "reference_audio": True},
             ["command-authority", "voice-consistency"]),
            ("REGISTER_SOUND_ASSET",
             {"explicit_instruction": True, "source": "studio-recording",
              "licence_or_permission": "owned", "owner": "owner-001",
              "project_scope": "project-001"},
             ["command-authority"]),
    ):
        plan = build_workflow_plan(session, request(
            f"mode-{mode.lower()}-noevidence", mode), CATALOG)
        check(f"CF-P1-002-MODES: {mode} without evidence is blocked",
              plan["status"] == "blocked"
              and plan["blocked_diagnostics"][0]["code"]
              == "missing-registration-evidence",
              f"diagnostics={plan['blocked_diagnostics']}")
        plan = build_workflow_plan(session, request(
            f"mode-{mode.lower()}", mode,
            registration_evidence=evidence), CATALOG)
        check(f"CF-P1-002-MODES: {mode} with evidence is a plan-only plan",
              plan["status"] == "ready" and plan["plan_only"] is True
              and [s["step_id"] for s in plan["steps"]] == chain,
              f"steps={[s['step_id'] for s in plan['steps']]}")
        check(f"CF-P1-002-MODES: {mode} plan validates",
              not validate_routing_plan(plan, CATALOG))
    # REFERENCE_LEARN_AND_UPDATE is proposal-only and needs an explicit
    # user instruction.
    plan = build_workflow_plan(session, request(
        "mode-learn-noinstr", "REFERENCE_LEARN_AND_UPDATE",
        requested_skills=[{"skill": "kids-family-animation",
                           "source": "user-request"}]), CATALOG)
    check("CF-P1-002-MODES: REFERENCE_LEARN_AND_UPDATE without an "
          "explicit instruction is blocked",
          plan["status"] == "blocked"
          and plan["blocked_diagnostics"][0]["code"]
          == "missing-explicit-instruction")
    plan = build_workflow_plan(session, request(
        "mode-learn", "REFERENCE_LEARN_AND_UPDATE",
        explicit_user_instruction=True,
        requested_skills=[{"skill": "kids-family-animation",
                           "source": "user-request"}]), CATALOG)
    check("CF-P1-002-MODES: REFERENCE_LEARN_AND_UPDATE with instruction "
          "is a proposal-only plan",
          plan["status"] == "ready" and plan["proposal_only"] is True,
          f"status={plan['status']}")
    # REFERENCE_REVIEW analyses and reports only.
    plan = build_workflow_plan(session, request(
        "mode-review", "REFERENCE_REVIEW",
        requested_skills=[{"skill": "video-regeneration",
                           "source": "user-request"}]), CATALOG)
    check("CF-P1-002-MODES: REFERENCE_REVIEW plan is analysis-only",
          plan["status"] == "ready" and plan["analysis_only"] is True,
          f"status={plan['status']}")
    # VIDEO_QC never regenerates without repair authorisation.
    plan = build_workflow_plan(session, request(
        "mode-qc-norepair", "VIDEO_QC", PROFILES["s7"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True}), CATALOG)
    check("CF-P1-002-MODES: VIDEO_QC without repair authorisation never "
          "regenerates",
          plan["status"] == "blocked"
          and plan["blocked_diagnostics"][0]["code"]
          == "regeneration-without-repair-authorisation",
          f"diagnostics={plan['blocked_diagnostics']}")
    plan = build_workflow_plan(session, request(
        "mode-qc-repair", "VIDEO_QC", PROFILES["s7"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True},
        repair_authorised=True), CATALOG)
    check("CF-P1-002-MODES: VIDEO_QC with repair authorisation is ready",
          plan["status"] == "ready", f"status={plan['status']}")
    # REMAKE_OR_TRANSFORM needs an explicit request and a rights check.
    plan = build_workflow_plan(session, request(
        "mode-remake-noevidence", "REMAKE_OR_TRANSFORM", PROFILES["s7"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True}), CATALOG)
    check("CF-P1-002-MODES: REMAKE_OR_TRANSFORM without evidence is blocked",
          plan["status"] == "blocked"
          and plan["blocked_diagnostics"][0]["code"]
          == "missing-remake-evidence")
    # GENERATE_FROM_SCRIPT forbids a silent dialogue rewrite.
    plan = build_workflow_plan(session, request(
        "mode-rewrite", "GENERATE_FROM_SCRIPT", PROFILES["s3"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "consent": True},
        dialogue_rewrite_requested=True), CATALOG)
    check("CF-P1-002-MODES: GENERATE_FROM_SCRIPT forbids a silent "
          "dialogue rewrite",
          plan["status"] == "blocked"
          and plan["blocked_diagnostics"][0]["code"]
          == "dialogue-rewrite-forbidden")
    # A mode-incompatible skill is refused with a suggested mode.
    try:
        resolve_skills(request(
            "mode-incompat", "GENERATE_FROM_SCRIPT", PROFILES["s7"],
            {"dialogue": True, "languages": ["en"],
             "recurring_character": True},
            explicit_request=True, rights_provenance_checked=True),
            CATALOG)
        check("CF-P1-002-MODES: video-regeneration in GENERATE_FROM_SCRIPT "
              "is refused", False, "resolved instead of refusing")
    except RoutingError as exc:
        check("CF-P1-002-MODES: video-regeneration in GENERATE_FROM_SCRIPT "
              "is refused with a suggested mode",
              "video-regeneration" in str(exc)
              and "REMAKE_OR_TRANSFORM" in str(exc), str(exc))

    # --- CF-P1-002-PLAN: deterministic planning -----------------------
    plan = build_workflow_plan(session, request(
        "plan-s3", "GENERATE_FROM_SCRIPT", PROFILES["s3"],
        {"dialogue": True, "languages": ["bn"],
         "recurring_character": True, "consent": True}), CATALOG)
    check("CF-P1-002-PLAN: s3 plan is ready",
          plan["status"] == "ready", f"status={plan['status']}")
    check("CF-P1-002-PLAN: s3 plan steps are in precedence order",
          [s["step_id"] for s in plan["steps"]] == [
              "command-authority", "character-consistency",
              "voice-consistency", "production-systems",
              "language-authenticity", "humanized-production",
              "realistic-person"],
          f"steps={[s['step_id'] for s in plan['steps']]}")
    check("CF-P1-002-PLAN: s3 execution batches are deterministic",
          plan["execution_batches"] == [
              ["command-authority"],
              ["character-consistency", "production-systems"],
              ["voice-consistency"],
              ["language-authenticity", "humanized-production"],
              ["realistic-person"]],
          f"batches={plan['execution_batches']}")
    check("CF-P1-002-PLAN: s3 parallel groups are the two no-dependency "
          "groups",
          plan["parallel_groups"] == [
              {"name": "foundation-planning",
               "skills": ["character-consistency", "production-systems"],
               "scope": "no-dependency"},
              {"name": "language-and-humanization-prep",
               "skills": ["language-authenticity", "humanized-production"],
               "scope": "no-dependency"}],
          f"groups={plan['parallel_groups']}")
    check("CF-P1-002-PLAN: resource-management is never a step",
          "resource-management" not in
          [s["step_id"] for s in plan["steps"]]
          and "resource-management" not in
          [s["skill"] for s in plan["selected_skills"]])
    check("CF-P1-002-PLAN: resource-management is one instruction per "
          "phase boundary",
          len(plan["resource_management"])
          == len(plan["execution_batches"])
          and all(r["phase"].startswith("before-batch-")
                  for r in plan["resource_management"]))
    check("CF-P1-002-PLAN: plan records the session id only",
          plan["session"] == {"session_id": session.session_id})
    check("CF-P1-002-PLAN: plan carries the catalog version and sources",
          plan["catalog_version"] == "2.4"
          and plan["catalog_sources"] == CATALOG["sources"])
    check("CF-P1-002-PLAN: plan validates against the catalog",
          not validate_routing_plan(plan, CATALOG),
          "; ".join(validate_routing_plan(plan, CATALOG)))
    check("CF-P1-002-PLAN: plan validates against the plan schema",
          not errors_for(plan_schema, plan),
          "; ".join(errors_for(plan_schema, plan)))
    check("CF-P1-002-PLAN: plan hash is the recomputed hash",
          plan_hash(plan) == plan["plan_hash"])
    plan_again = build_workflow_plan(session, request(
        "plan-s3", "GENERATE_FROM_SCRIPT", PROFILES["s3"],
        {"dialogue": True, "languages": ["bn"],
         "recurring_character": True, "consent": True}), CATALOG)
    check("CF-P1-002-PLAN: rebuilding the same request gives the same plan",
          plan == plan_again and plan["plan_hash"] == plan_again["plan_hash"])
    check("CF-P1-002-PLAN: plans carry no timestamps",
          "timestamp" not in json.dumps(plan).lower()
          and "created_at" not in json.dumps(plan))
    # Ready steps walk the batches in order.
    check("CF-P1-002-PLAN: only the router is ready at the start",
          get_ready_steps(plan, []) == ["command-authority"])
    check("CF-P1-002-PLAN: foundation planning is ready after the router",
          get_ready_steps(plan, ["command-authority"])
          == ["character-consistency", "production-systems"])
    check("CF-P1-002-PLAN: voice is ready after foundation planning",
          get_ready_steps(plan, ["command-authority",
                                 "character-consistency",
                                 "production-systems"])
          == ["voice-consistency"])
    check("CF-P1-002-PLAN: a dependent is never ready before its "
          "prerequisites",
          get_ready_steps(plan, ["command-authority",
                                 "character-consistency"])
          == ["production-systems"])
    check("CF-P1-002-PLAN: nothing is ready when everything is complete",
          get_ready_steps(plan, [s["step_id"] for s in plan["steps"]]) == [])
    check("CF-P1-002-PLAN: a blocked plan has no ready steps",
          get_ready_steps(build_workflow_plan(session, request(
              "plan-blocked", "UPLOAD_ONLY", PROFILES["s3"],
              {"dialogue": True}), CATALOG), []) == [])
    # Conditional existing-character-prep group.
    plan_existing = build_workflow_plan(session, request(
        "plan-existing", "GENERATE_FROM_SCRIPT", PROFILES["s3"],
        {"dialogue": True, "languages": ["bn"],
         "recurring_character": True, "consent": True,
         "existing_character_registered": True}), CATALOG)
    check("CF-P1-002-PLAN: existing character runs character + voice in "
          "one batch",
          ["character-consistency", "voice-consistency"]
          in plan_existing["execution_batches"],
          f"batches={plan_existing['execution_batches']}")
    check("CF-P1-002-PLAN: existing character relaxes the voice "
          "dependency (independent registry reads)",
          next(s for s in plan_existing["steps"]
               if s["skill"] == "voice-consistency")["dependencies"] == [])
    check("CF-P1-002-PLAN: existing character records the conditional group",
          {"name": "existing-character-prep",
           "skills": ["character-consistency", "voice-consistency"],
           "scope": "existing-character-only"}
          in plan_existing["parallel_groups"])
    plan_new = build_workflow_plan(session, request(
        "plan-new", "GENERATE_FROM_SCRIPT", PROFILES["s3"],
        {"dialogue": True, "languages": ["bn"],
         "recurring_character": True, "consent": True,
         "existing_character_registered": False}), CATALOG)
    check("CF-P1-002-PLAN: new character runs voice after character "
          "registration",
          next(s for s in plan_new["steps"]
               if s["skill"] == "voice-consistency")["dependencies"]
          == ["character-consistency"])
    check("CF-P1-002-PLAN: new character does not record the conditional "
          "group",
          not any(g["name"] == "existing-character-prep"
                  for g in plan_new["parallel_groups"]))
    # Performance-layers group: only for different scenes.
    check("CF-P1-002-PLAN: performance layers without shot scope are not "
          "parallelised (different scenes unproven)",
          "performance-layers-different-scenes" not in
          [g["name"] for g in build_workflow_plan(session, request(
              "plan-perf", "GENERATE_FROM_SCRIPT", PROFILES["s5"],
              {"dialogue": True, "languages": ["en"],
               "recurring_character": True},
              additional_layers=["emotional-performance"]),
              CATALOG)["parallel_groups"]])
    # Handoff packets.
    packet = build_handoff_packet(plan, "realistic-person", CATALOG)
    record = next(e for e in CATALOG["skills"]
                  if e["skill"] == "realistic-person")
    plan_record = next(s for s in plan["selected_skills"]
                       if s["skill"] == "realistic-person")
    check("CF-P1-002-PLAN: handoff packet carries the exact skill path "
          "and SHA-256 fingerprint",
          packet["path"] == record["path"]
          and packet["sha256"] == record["sha256"])
    check("CF-P1-002-PLAN: handoff packet carries inputs, outputs, "
          "dependencies, quality gate and approvals",
          packet["inputs"] == plan_record["required_inputs"]
          and packet["expected_outputs"] == plan_record["expected_outputs"]
          and packet["satisfied_dependencies"]
          == ["character-consistency", "voice-consistency",
              "language-authenticity", "humanized-production"]
          and packet["quality_gate"] == record["quality_gate"]
          and packet["approval_requirements"]
          == plan_record["approval_conditions"])
    check("CF-P1-002-PLAN: plan text lists are uniform strings (matrix "
          "dict entries normalised to 'label: detail')",
          all(isinstance(x, str)
              for s in plan["selected_skills"]
              for key in ("required_inputs", "expected_outputs",
                          "approval_conditions")
              for x in s[key]))
    check("CF-P1-002-PLAN: handoff packet names the conflicting operations",
          any("TC-2" in c for c in packet["conflicting_operations"])
          and any("TC-4" in c for c in packet["conflicting_operations"]),
          f"conflicts={packet['conflicting_operations']}")
    check("CF-P1-002-PLAN: handoff packet names the prohibited operations",
          packet["prohibited_operations"]
          == ["mode GENERATE_FROM_SCRIPT: forbidden silent_dialogue_rewrite"])
    check("CF-P1-002-PLAN: handoff packet carries the selection basis",
          packet["selection_basis"] == "profile-dimension")
    try:
        build_handoff_packet(plan, "not-a-step", CATALOG)
        check("CF-P1-002-PLAN: handoff packet for an unknown step is refused",
              False, "built instead of refusing")
    except RoutingError:
        check("CF-P1-002-PLAN: handoff packet for an unknown step is refused",
              True)
    # Tamper detection.
    tampered = clone(plan)
    tampered["steps"][0]["skill"] = "voice-consistency"
    errs = validate_routing_plan(tampered, CATALOG)
    check("CF-P1-002-PLAN: a tampered step is detected",
          any("plan_hash" in e for e in errs), "; ".join(errs))
    tampered = clone(plan)
    tampered["plan_hash"] = "0" * 64
    errs = validate_routing_plan(tampered, CATALOG)
    check("CF-P1-002-PLAN: a forged plan hash is detected",
          any("plan_hash" in e for e in errs), "; ".join(errs))
    tampered = clone(plan)
    tampered["steps"] = tampered["steps"][:-1]
    errs = validate_routing_plan(tampered, CATALOG)
    check("CF-P1-002-PLAN: a dropped step is detected",
          bool(errs), "; ".join(errs))
    tampered = clone(plan)
    tampered["catalog_sources"] = {}
    errs = validate_routing_plan(tampered, CATALOG)
    check("CF-P1-002-PLAN: catalog sources that do not match are detected",
          any("catalog_sources" in e for e in errs), "; ".join(errs))
    # A blocked plan from a true conflict names the rule and the
    # decision required, and keeps both skills.
    blocked_plan = build_workflow_plan(session, request(
        "plan-tc2", "GENERATE_FROM_SCRIPT", PROFILES["s3"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "consent": True},
        requested_skills=[{"skill": "live-action-vfx",
                           "source": "user-request",
                           "scope": {"shots": ["shot-01"],
                                     "subjects": [human_s3]}}]), CATALOG)
    check("CF-P1-002-PLAN: a true conflict builds a blocked plan, not an "
          "exception",
          blocked_plan["status"] == "blocked"
          and blocked_plan["conflicts"]
          and blocked_plan["conflicts"][0]["rule_id"] == "TC-2"
          and blocked_plan["conflicts"][0]["subject_id"] == human_s3,
          f"conflicts={blocked_plan['conflicts']}")
    check("CF-P1-002-PLAN: the blocked plan validates",
          not validate_routing_plan(blocked_plan, CATALOG))

    # --- CF-P1-002-SECURITY: sessions and boundaries ------------------
    # No session at all.
    try:
        build_workflow_plan(None, request(
            "sec-none", "GENERATE_FROM_SCRIPT", PROFILES["s3"],
            {"dialogue": True}), CATALOG)
        check("CF-P1-002-SECURITY: a missing session is rejected",
              False, "planned without a session")
    except RoutingError:
        check("CF-P1-002-SECURITY: a missing session is rejected", True)
    # A forged session object (same id string, wrong type).
    forged = SimpleNamespace(session_id=session.session_id)
    try:
        build_workflow_plan(forged, request(
            "sec-forged", "GENERATE_FROM_SCRIPT", PROFILES["s3"],
            {"dialogue": True}), CATALOG)
        check("CF-P1-002-SECURITY: a forged session is rejected",
              False, "planned with a forged session")
    except RoutingError:
        check("CF-P1-002-SECURITY: a forged session is rejected", True)
    # A copied session (same data, different object identity).
    copied = copy.copy(session)
    check("CF-P1-002-SECURITY: a copied session is not active",
          not is_active_session(copied))
    try:
        build_workflow_plan(copied, request(
            "sec-copied", "GENERATE_FROM_SCRIPT", PROFILES["s3"],
            {"dialogue": True}), CATALOG)
        check("CF-P1-002-SECURITY: a copied session is rejected",
              False, "planned with a copied session")
    except RoutingError:
        check("CF-P1-002-SECURITY: a copied session is rejected", True)
    # An expired session.
    short_session = fresh_session(lifetime_seconds=1)
    time.sleep(1.2)
    check("CF-P1-002-SECURITY: an expired session is not active",
          not is_active_session(short_session))
    try:
        build_workflow_plan(short_session, request(
            "sec-expired", "GENERATE_FROM_SCRIPT", PROFILES["s3"],
            {"dialogue": True}), CATALOG)
        check("CF-P1-002-SECURITY: an expired session is rejected",
              False, "planned with an expired session")
    except RoutingError:
        check("CF-P1-002-SECURITY: an expired session is rejected", True)
    # A closed session.
    closing = fresh_session()
    close_session(closing)
    check("CF-P1-002-SECURITY: a closed session is not active",
          not is_active_session(closing))
    try:
        build_workflow_plan(closing, request(
            "sec-closed", "GENERATE_FROM_SCRIPT", PROFILES["s3"],
            {"dialogue": True}), CATALOG)
        check("CF-P1-002-SECURITY: a closed session is rejected",
              False, "planned with a closed session")
    except RoutingError:
        check("CF-P1-002-SECURITY: a closed session is rejected", True)
    # The router takes no caller-provided identity strings: the plan
    # API has no owner/workspace parameter, and the plan records only
    # the session id from the verified session object.
    check("CF-P1-002-SECURITY: the plan records only the verified "
          "session id",
          plan["session"] == {"session_id": session.session_id}
          and "owner_id" not in plan["session"]
          and "workspace_id" not in plan["session"])
    # The router never touches private assets: it never calls the P0
    # policy (no asset_policy / authorize_action reference in its own
    # source — it plans only; authorization stays with the P1-001
    # boundary) and carries no provider, companion, media generation,
    # YAML, network or persistence code. (asset_policy IS loaded
    # transitively: runtime/local_session imports it for its own
    # ownership checks — that is the P1-001 design, not a router call.)
    router_src = open(os.path.join(ROOT, "runtime", "skill_router.py"),
                      encoding="utf-8").read()
    check("CF-P1-002-SECURITY: the router never calls the asset policy",
          "asset_policy" not in router_src
          and "authorize_action" not in router_src)
    denied = [token for token in (
        "VoiceStudio", "OpenMontage", "import yaml", "import requests",
        "subprocess", "socket", "os.makedirs", "os.remove", "os.unlink",
        "http.client", "open(", )
        if token in router_src]
    # open( is used once: reading the catalog JSON. Everything else
    # on the denylist must be absent.
    check("CF-P1-002-SECURITY: the router carries no provider, companion, "
          "media-generation, network or persistence code",
          denied == ["open("], f"denied tokens present: {denied}")
    check("CF-P1-002-SECURITY: the router reads the catalog with the "
          "standard library only",
          "import yaml" not in router_src
          and "import json" in router_src)

    for s in _sessions:
        try:
            close_session(s)
        except Exception:
            pass
    print(f"test_skill_router: {'PASS' if not failures else 'FAIL'} "
          f"({len(failures)} failure(s))")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
