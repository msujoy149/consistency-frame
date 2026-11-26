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
CF-P1-002-MODES, CF-P1-002-PLAN, CF-P1-002-SECURITY,
CF-P1-002-R1-SCOPE, CF-P1-002-R1-SCHEMA, CF-P1-002-R1-HANDOFF,
CF-P1-002-R1-CATALOG.
"""
import copy
import fnmatch
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
    # CF-WO-P1-002-R1-R1: the catalog hashes raw file bytes, so every
    # catalog-hashed file must check out with LF on every platform.
    # A Windows checkout converting LF to CRLF changes the SHA-256
    # and fails the two checks above — PR run #237 proved it (both
    # windows-compat jobs failed exactly those two checks plus the
    # PyYAML-missing --check failure). The checkout contract lives
    # in .gitattributes; these checks prove every hashed file is
    # covered by an eol=lf rule, so the defect class cannot silently
    # return when a new hashed file is added. The count pin (5 YAML
    # sources + 15 SKILL.md files + the catalog itself = 21) forces
    # the contract to be revisited if the hashed set ever changes.
    def _gitattributes_eol_lf_patterns():
        path = os.path.join(ROOT, ".gitattributes")
        patterns = []
        if not os.path.exists(path):
            return patterns
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) >= 2 and "eol=lf" in parts[1:]:
                    patterns.append(parts[0])
        return patterns

    def _pattern_matches(pattern, rel):
        # Git attributes patterns, segment by segment: '*' matches
        # within one path segment, '**' across segments, '?' one
        # character. (No '**' is used in .gitattributes today.)
        pat_segs = pattern.strip("/").split("/")
        rel_segs = rel.strip("/").split("/")

        def match(p, r):
            if not p:
                return not r
            if p[0] == "**":
                return any(match(p[1:], r[i:])
                           for i in range(len(r) + 1))
            if not r:
                return False
            if not fnmatch.fnmatchcase(r[0], p[0]):
                return False
            return match(p[1:], r[1:])

        return match(pat_segs, rel_segs)

    hashed = sorted(
        list((CATALOG.get("sources") or {}).keys())
        + [e["path"] for e in CATALOG["skills"]]
        + ["registry/routing-catalog.json"])
    lf_patterns = _gitattributes_eol_lf_patterns()
    uncovered = [rel for rel in hashed
                 if not any(_pattern_matches(p, rel)
                            for p in lf_patterns)]
    check("CF-P1-002-R1-CATALOG: every catalog-hashed file is covered "
          "by an eol=lf rule in .gitattributes",
          not uncovered and len(hashed) == 21,
          f"hashed={len(hashed)} uncovered={uncovered}")
    check("CF-P1-002-R1-CATALOG: .gitattributes covers the catalog "
          "file itself",
          any(_pattern_matches(p, "registry/routing-catalog.json")
              for p in lf_patterns))
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
    # subject in the same shot as realistic-person. (R1: the scoped
    # shot is declared in the request's shots table, so the scope
    # reference resolves.)
    res = resolve_skills(request(
        "tc2-plus", "GENERATE_FROM_SCRIPT", PROFILES["s3"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "consent": True},
        shots=[{"shot_id": "shot-01"}],
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
    # (R1: both shots are declared, so the subject's shot reference
    # and the scope reference resolve.)
    res = resolve_skills(request(
        "tc2-minus", "GENERATE_FROM_SCRIPT", PROFILES["s3"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "consent": True},
        subjects=[{"subject_id": human_s3, "shots": ["shot-01"]}],
        shots=[{"shot_id": "shot-01"}, {"shot_id": "shot-02"}],
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
        shots=[{"shot_id": "shot-01"}],
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
        shots=[{"shot_id": "shot-01"}],
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
    # (R1: the line's shot is declared, so the shot reference
    # resolves.)
    res = resolve_skills(request(
        "tc10-plus", "GENERATE_FROM_SCRIPT", PROFILES["s4"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "consent": True},
        shots=[{"shot_id": "shot-01"}],
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
        shots=[{"shot_id": "shot-01"}],
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
        shots=[{"shot_id": "shot-01"}],
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
    # Handoff packets (R1: receipts for every earlier step, so the
    # realistic-person step is ready and its dependencies count as
    # satisfied only because they were receipted).
    receipts = [{"plan_id": plan["plan_id"], "step_id": step,
                 "status": "completed"}
                for step in ("command-authority", "character-consistency",
                             "voice-consistency", "production-systems",
                             "language-authenticity", "humanized-production")]
    packet = build_handoff_packet(session, plan, "realistic-person",
                                  receipts, CATALOG)
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
    check("CF-P1-002-PLAN: handoff packet is bound to the plan and the "
          "session and lists the receipted steps",
          packet["plan_id"] == plan["plan_id"]
          and packet["session_id"] == session.session_id
          and packet["completed_step_ids"] == [
              "command-authority", "character-consistency",
              "voice-consistency", "production-systems",
              "language-authenticity", "humanized-production"])
    try:
        build_handoff_packet(session, plan, "not-a-step", [], CATALOG)
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
        shots=[{"shot_id": "shot-01"}],
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

    # --- CF-P1-002-R1-SCOPE: referential scope integrity --------------
    # TC-8 reproduction with the digital-human profile: the real
    # subject char-aria-001 triggers the same-subject conflict.
    res = resolve_skills(request(
        "r1-tc8-real", "GENERATE_FROM_SCRIPT", PROFILES["s3"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "consent": True},
        requested_skills=[{"skill": "agency-advertising",
                           "source": "user-request",
                           "scope": {"subjects": [human_s3]}}]), CATALOG)
    item = blocked_item(res, "TC-8")
    check("CF-P1-002-R1-SCOPE: TC-8 fires for the real subject "
          "char-aria-001",
          item is not None and item["subject_id"] == "char-aria-001",
          f"blocked={res['blocked']}")
    # A phantom subject in a skill scope is rejected at validation.
    ghost_req = request(
        "r1-tc8-ghost", "GENERATE_FROM_SCRIPT", PROFILES["s3"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "consent": True},
        requested_skills=[{"skill": "agency-advertising",
                           "source": "user-request",
                           "scope": {"subjects": ["ghost-subject-999"]}}])
    check("CF-P1-002-R1-SCOPE: phantom subject ghost-subject-999 is "
          "rejected during request validation",
          any("ghost-subject-999" in e
              for e in validate_routing_request(ghost_req, CATALOG)),
          "; ".join(validate_routing_request(ghost_req, CATALOG)))
    try:
        resolve_skills(ghost_req, CATALOG)
        check("CF-P1-002-R1-SCOPE: phantom subject never reaches "
              "resolution", False, "resolved instead of refusing")
    except RoutingError:
        check("CF-P1-002-R1-SCOPE: phantom subject never reaches "
              "resolution", True)
    # A phantom shot in a skill scope is rejected the same way.
    ghost_shot_req = request(
        "r1-tc8-ghost-shot", "GENERATE_FROM_SCRIPT", PROFILES["s3"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "consent": True},
        shots=[{"shot_id": "shot-01"}],
        requested_skills=[{"skill": "live-action-vfx",
                           "source": "user-request",
                           "scope": {"shots": ["ghost-shot-999"],
                                     "subjects": [human_s3]}}])
    check("CF-P1-002-R1-SCOPE: phantom shot ghost-shot-999 is rejected "
          "during request validation",
          any("ghost-shot-999" in e
              for e in validate_routing_request(ghost_shot_req, CATALOG)))
    # Phantom references are rejected wherever a rule consumes scope
    # IDs: subject shot lists, shot subject lists, dialogue lines,
    # and per-shot override subject lists.
    for label, req in (
            ("subject shot list", request(
                "r1-ghost-subject-shots", "GENERATE_FROM_SCRIPT",
                PROFILES["s3"],
                {"dialogue": True, "consent": True},
                subjects=[{"subject_id": human_s3,
                           "shots": ["ghost-shot-999"]}])),
            ("shot subject list", request(
                "r1-ghost-shot-subjects", "GENERATE_FROM_SCRIPT",
                PROFILES["s3"],
                {"dialogue": True, "consent": True},
                shots=[{"shot_id": "shot-01",
                        "subject_ids": ["ghost-subject-999"]}])),
            ("dialogue line subject", request(
                "r1-ghost-line-subject", "GENERATE_FROM_SCRIPT",
                PROFILES["s4"],
                {"dialogue": True, "consent": True},
                shots=[{"shot_id": "shot-01"}],
                dialogue_lines=[{"line_id": "line-01",
                                 "subject_id": "ghost-subject-999",
                                 "shot_id": "shot-01",
                                 "articulation_target": "human-mouth-lips"}])),
            ("dialogue line shot", request(
                "r1-ghost-line-shot", "GENERATE_FROM_SCRIPT",
                PROFILES["s4"],
                {"dialogue": True, "consent": True},
                shots=[{"shot_id": "shot-01"}],
                dialogue_lines=[{"line_id": "line-01",
                                 "subject_id": bird_s4,
                                 "shot_id": "ghost-shot-999",
                                 "articulation_target": "bird-beak"}])),
    ):
        check(f"CF-P1-002-R1-SCOPE: phantom reference rejected — {label}",
              bool(validate_routing_request(req, CATALOG)),
              "; ".join(validate_routing_request(req, CATALOG)))
    ghost_override = clone(PROFILES["s1"])
    ghost_override["per_shot_overrides"] = [
        {"shot_id": "shot-01", "subjects": ["ghost-subject-999"]}]
    check("CF-P1-002-R1-SCOPE: per-shot override naming a phantom "
          "subject is rejected",
          bool(validate_routing_request(request(
              "r1-ghost-override", "GENERATE_FROM_SCRIPT", ghost_override,
              {"dialogue": True}), CATALOG)))
    # Duplicate IDs inside the profile override tables are ambiguous.
    dup_subject = clone(PROFILES["s3"])
    dup_subject["per_subject_overrides"].append(
        clone(dup_subject["per_subject_overrides"][0]))
    check("CF-P1-002-R1-SCOPE: duplicate character_id in "
          "per_subject_overrides is rejected",
          bool(validate_routing_request(request(
              "r1-dup-subject", "GENERATE_FROM_SCRIPT", dup_subject,
              {"dialogue": True, "consent": True}), CATALOG)))
    dup_shot = clone(PROFILES["s3"])
    dup_shot["per_shot_overrides"].append(
        clone(dup_shot["per_shot_overrides"][0]))
    check("CF-P1-002-R1-SCOPE: duplicate shot_id in per_shot_overrides "
          "is rejected",
          bool(validate_routing_request(request(
              "r1-dup-shot", "GENERATE_FROM_SCRIPT", dup_shot,
              {"dialogue": True, "consent": True}), CATALOG)))
    # Phantom scope references are rejected for every TC that consumes
    # scope IDs, not just TC-8.
    for rule, skill, scope in (
            ("TC-2", "live-action-vfx",
             {"shots": ["shot-01"], "subjects": ["ghost-subject-999"]}),
            ("TC-4", "explainer-animation",
             {"shots": ["shot-01"], "subjects": ["ghost-subject-999"]}),
            ("TC-6", "kids-family-animation",
             {"shots": ["shot-01"], "subjects": ["ghost-subject-999"]}),
            ("TC-8", "agency-advertising",
             {"subjects": ["ghost-subject-999"]}),
    ):
        req = request(
            f"r1-ghost-{rule.lower()}", "GENERATE_FROM_SCRIPT",
            PROFILES["s3"],
            {"dialogue": True, "languages": ["en"],
             "recurring_character": True, "consent": True},
            shots=[{"shot_id": "shot-01"}],
            requested_skills=[{"skill": skill, "source": "user-request",
                               "scope": scope}])
        check(f"CF-P1-002-R1-SCOPE: phantom scope rejected for {rule}",
              bool(validate_routing_request(req, CATALOG)))
    # A scope that names a profile shot resolves (the profile's
    # per-shot override shot sh-01 is a real shot).
    res = resolve_skills(request(
        "r1-profile-shot", "GENERATE_FROM_SCRIPT", PROFILES["s3"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "consent": True},
        requested_skills=[{"skill": "live-action-vfx",
                           "source": "user-request",
                           "scope": {"shots": ["sh-01"],
                                     "subjects": [human_s3]}}]), CATALOG)
    check("CF-P1-002-R1-SCOPE: a scope naming a profile shot resolves "
          "and TC-2 fires for it",
          blocked_item(res, "TC-2") is not None
          and blocked_item(res, "TC-2")["shot_id"] == "sh-01",
          f"blocked={res['blocked']}")
    # Valid cross-shot / cross-subject combinations stay allowed when
    # their actual IDs resolve and the conflict rule permits them.
    res = resolve_skills(request(
        "r1-cross-ok", "GENERATE_FROM_SCRIPT", PROFILES["s4"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "consent": True},
        requested_skills=[{"skill": "agency-advertising",
                           "source": "user-request",
                           "scope": {"subjects": [bird_s4]}}]), CATALOG)
    check("CF-P1-002-R1-SCOPE: agency-advertising on a different real "
          "subject stays allowed",
          "TC-8" not in blocked_rules(res), f"blocked={res['blocked']}")
    # An invalid scope never produces a ready plan: the planner
    # returns a blocked plan with an invalid-request diagnostic.
    bad_plan = build_workflow_plan(session, ghost_req, CATALOG)
    check("CF-P1-002-R1-SCOPE: an invalid scope produces a blocked plan, "
          "never a ready plan",
          bad_plan["status"] == "blocked"
          and bad_plan["blocked_diagnostics"]
          and bad_plan["blocked_diagnostics"][0]["code"] == "invalid-request"
          and not bad_plan["steps"],
          f"status={bad_plan['status']}")

    # --- CF-P1-002-R1-SCHEMA: schema parity / typed evidence --------
    # The supplied reproduction: a string "false" is never boolean
    # authorisation evidence.
    false_req = request(
        "r1-evidence-false", "REGISTER_CHARACTER",
        registration_evidence={"explicit_authorisation": "false",
                               "name": "Nila",
                               "unique_id": "char-nila-001",
                               "approved_reference": True})
    check("CF-P1-002-R1-SCHEMA: explicit_authorisation \"false\" is "
          "rejected by request validation",
          any("explicit_authorisation" in e and "boolean" in e
              for e in validate_routing_request(false_req, CATALOG)),
          "; ".join(validate_routing_request(false_req, CATALOG)))
    false_plan = build_workflow_plan(session, false_req, CATALOG)
    check("CF-P1-002-R1-SCHEMA: explicit_authorisation \"false\" never "
          "builds a ready registration plan",
          false_plan["status"] == "blocked",
          f"status={false_plan['status']}")
    # Every boolean authorisation field, every non-True value: only
    # the actual boolean True can satisfy an affirmative approval.
    for field in ("explicit_authorisation", "approved_reference",
                  "rights_consent", "reference_audio",
                  "explicit_instruction"):
        for bad in ("true", "yes", 1, 0, None, ""):
            req = request(
                f"r1-bool-{field[:6]}", "REGISTER_CHARACTER",
                registration_evidence={field: bad})
            errs = validate_routing_request(req, CATALOG)
            check(f"CF-P1-002-R1-SCHEMA: {field}={bad!r} is rejected",
                  any(field in e for e in errs), "; ".join(errs))
        req = request(
            f"r1-bool-{field[:6]}-true", "REGISTER_CHARACTER",
            registration_evidence={field: True})
        check(f"CF-P1-002-R1-SCHEMA: {field}=True is well-formed",
              not any("registration_evidence" in e
                      for e in validate_routing_request(req, CATALOG)),
              "; ".join(validate_routing_request(req, CATALOG)))
    # A well-formed False is a denial, not a type error: it validates
    # but does not satisfy the registration policy.
    denied_req = request(
        "r1-evidence-denied", "REGISTER_CHARACTER",
        registration_evidence={"explicit_authorisation": False,
                               "name": "Nila",
                               "unique_id": "char-nila-001",
                               "approved_reference": True})
    check("CF-P1-002-R1-SCHEMA: explicit_authorisation False validates "
          "(a well-formed denial)",
          not validate_routing_request(denied_req, CATALOG),
          "; ".join(validate_routing_request(denied_req, CATALOG)))
    denied_plan = build_workflow_plan(session, denied_req, CATALOG)
    check("CF-P1-002-R1-SCHEMA: explicit_authorisation False does not "
          "satisfy the registration policy",
          denied_plan["status"] == "blocked"
          and denied_plan["blocked_diagnostics"][0]["code"]
          == "missing-registration-evidence",
          f"diagnostics={denied_plan['blocked_diagnostics']}")
    # None and wrong types for every required profile field.
    profile_bad_cases = []
    for field in ("schema_version", "production_profile_id",
                  "production_medium", "visual_style",
                  "source_media_type", "motion_methods", "subject_types",
                  "interaction_pattern", "is_live_action_footage",
                  "version", "status"):
        # "not-a-value" is a valid production_profile_id per the ID
        # pattern, so that field gets a genuinely invalid string.
        bad_string = "BAD ID!" if field == "production_profile_id" \
            else "not-a-value"
        for bad in (None, 123, bad_string):
            profile_bad_cases.append((f"{field}={bad!r}", field, bad))
    profile_bad_cases.extend([
        ("version=True", "version", True),
        ("version=0", "version", 0),
        ("version='1'", "version", "1"),
        ("status='pending'", "status", "pending"),
        ("schema_version='2.4'", "schema_version", "2.4"),
        ("motion_methods=[]", "motion_methods", []),
        ("motion_methods='rig'", "motion_methods", "rig-2d-keyframe"),
        ("subject_types=[]", "subject_types", []),
        ("production_profile_id='BAD ID!'", "production_profile_id",
         "BAD ID!"),
    ])
    for label, field, bad in profile_bad_cases:
        prof = clone(PROFILES["s3"])
        prof[field] = bad
        req = request(f"r1-prof-{label[:12]}", "GENERATE_FROM_SCRIPT",
                      prof, {"dialogue": True, "consent": True})
        check(f"CF-P1-002-R1-SCHEMA: required profile field rejected — "
              f"{label}",
              bool(validate_routing_request(req, CATALOG)),
              "; ".join(validate_routing_request(req, CATALOG)))
    # Nested registration-evidence extra fields and invalid types.
    for label, evidence in (
            ("extra field", {"explicit_authorisation": True,
                             "name": "Nila", "unique_id": "char-nila-001",
                             "approved_reference": True, "note": "hi"}),
            ("name is a number", {"explicit_authorisation": True,
                                  "name": 123,
                                  "unique_id": "char-nila-001",
                                  "approved_reference": True}),
            ("unique_id is empty", {"explicit_authorisation": True,
                                    "name": "Nila", "unique_id": "",
                                    "approved_reference": True}),
            ("approved_reference is 1", {"explicit_authorisation": True,
                                         "name": "Nila",
                                         "unique_id": "char-nila-001",
                                         "approved_reference": 1}),
    ):
        req = request("r1-evidence-nested", "REGISTER_CHARACTER",
                      registration_evidence=evidence)
        check(f"CF-P1-002-R1-SCHEMA: nested evidence rejected — {label}",
              bool(validate_routing_request(req, CATALOG)),
              "; ".join(validate_routing_request(req, CATALOG)))
    # Schema parity: every deliberately schema-invalid request/profile
    # in this table is rejected by the schema AND by the production
    # runtime validator.
    parity_base = request(
        "r1-parity", "GENERATE_FROM_SCRIPT", PROFILES["s3"],
        {"dialogue": True, "languages": ["bn"],
         "recurring_character": True, "consent": True})

    parity_cases = [
        ("unknown top-level field",
         lambda r: r.update({"surprise": True})),
        ("unknown hints field",
         lambda r: r["hints"].update({"surprise": True})),
        ("unknown evidence field",
         lambda r: r.update({"registration_evidence": {"surprise": 1}})),
        ("evidence explicit_authorisation 'false'",
         lambda r: r.update({"registration_evidence": {
             "explicit_authorisation": "false"}})),
        ("evidence explicit_authorisation 1",
         lambda r: r.update({"registration_evidence": {
             "explicit_authorisation": 1}})),
        ("profile version None",
         lambda r: r["production_profile"].update({"version": None})),
        ("profile version '1'",
         lambda r: r["production_profile"].update({"version": "1"})),
        ("profile version True",
         lambda r: r["production_profile"].update({"version": True})),
        ("profile status None",
         lambda r: r["production_profile"].update({"status": None})),
        ("profile status 'pending'",
         lambda r: r["production_profile"].update({"status": "pending"})),
        ("profile is_live_action_footage None",
         lambda r: r["production_profile"].update(
             {"is_live_action_footage": None})),
        ("profile is_live_action_footage 'false'",
         lambda r: r["production_profile"].update(
             {"is_live_action_footage": "false"})),
        ("profile schema_version '2.4'",
         lambda r: r["production_profile"].update(
             {"schema_version": "2.4"})),
        ("profile unknown field",
         lambda r: r["production_profile"].update({"surprise": 1})),
        ("per-subject override unknown field",
         lambda r: r["production_profile"]["per_subject_overrides"][0]
         .update({"surprise": 1})),
        ("per-subject override character_id pattern",
         lambda r: r["production_profile"]["per_subject_overrides"][0]
         .update({"character_id": "BAD ID!"})),
        ("per-subject override species type",
         lambda r: r["production_profile"]["per_subject_overrides"][0]
         .update({"species": 123})),
        ("per-shot override unknown field",
         lambda r: r["production_profile"]["per_shot_overrides"][0]
         .update({"surprise": 1})),
        ("subjects item unknown field",
         lambda r: r.update({"subjects": [{"subject_id": human_s3,
                                           "surprise": 1}]})),
        ("shots item unknown field",
         lambda r: r.update({"shots": [{"shot_id": "shot-01",
                                        "surprise": 1}]})),
        ("dialogue line unknown field",
         lambda r: r.update({"dialogue_lines": [
             {"line_id": "line-01", "subject_id": human_s3,
              "articulation_target": "human-mouth-lips",
              "surprise": 1}]})),
        ("dialogue line missing articulation_target",
         lambda r: r.update({"dialogue_lines": [
             {"line_id": "line-01", "subject_id": human_s3}]})),
        ("dialogue line shot_id type",
         lambda r: r.update({"dialogue_lines": [
             {"line_id": "line-01", "subject_id": human_s3,
              "shot_id": 123,
              "articulation_target": "human-mouth-lips"}]})),
        ("requested_skills item unknown field",
         lambda r: r.update({"requested_skills": [
             {"skill": "cinematic-power", "source": "user-request",
              "surprise": 1}]})),
        ("requested_skills item missing source",
         lambda r: r.update({"requested_skills": [
             {"skill": "cinematic-power"}]})),
        ("hints.languages short code",
         lambda r: r["hints"].update({"languages": ["e"]})),
        ("hints.dialogue string",
         lambda r: r["hints"].update({"dialogue": "yes"})),
        ("task_id empty",
         lambda r: r.update({"task_id": ""})),
        ("schema_version '2.3'",
         lambda r: r.update({"schema_version": "2.3"})),
        ("motion_methods None",
         lambda r: r["production_profile"].update(
             {"motion_methods": None})),
        ("subject_types empty",
         lambda r: r["production_profile"].update({"subject_types": []})),
    ]
    for label, mutator in parity_cases:
        req = clone(parity_base)
        mutator(req)
        schema_errs = errors_for(req_schema, req)
        router_errs = validate_routing_request(req, CATALOG)
        check(f"CF-P1-002-R1-SCHEMA: schema parity — {label}",
              bool(schema_errs) and bool(router_errs),
              f"schema_errs={schema_errs} router_errs={router_errs}")
    # Positive tests: valid schema-conforming requests still work.
    check("CF-P1-002-R1-SCHEMA: a valid request still resolves",
          "realistic-person" in resolve_skills(parity_base, CATALOG)["skills"])
    valid_reg = request(
        "r1-reg-ok", "REGISTER_CHARACTER",
        registration_evidence={"explicit_authorisation": True,
                               "name": "Nila",
                               "unique_id": "char-nila-001",
                               "approved_reference": True})
    reg_plan = build_workflow_plan(session, valid_reg, CATALOG)
    check("CF-P1-002-R1-SCHEMA: a valid registration request still "
          "builds a plan-only plan",
          reg_plan["status"] == "ready" and reg_plan["plan_only"] is True,
          f"status={reg_plan['status']}")

    # --- CF-P1-002-R1-HANDOFF: dependency-safe handoff packets -------
    s1_session = fresh_session()
    s1_plan = build_workflow_plan(s1_session, request(
        "r1-handoff-s1", "GENERATE_FROM_SCRIPT", PROFILES["s1"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "explainer_structure": True}),
        CATALOG)
    check("CF-P1-002-R1-HANDOFF: the s1 reproduction plan is ready",
          s1_plan["status"] == "ready", f"status={s1_plan['status']}")

    def _receipt(step_id, plan_id=None, status="completed"):
        return {"plan_id": plan_id or s1_plan["plan_id"],
                "step_id": step_id, "status": status}

    def _handoff_fails(label, sess, plan, step, receipts):
        try:
            build_handoff_packet(sess, plan, step, receipts, CATALOG)
            check(label, False, "packet built instead of refusing")
        except RoutingError:
            check(label, True)

    # With zero completion receipts, the voice-consistency handoff
    # must fail (its dependency character-consistency is not done).
    _handoff_fails(
        "CF-P1-002-R1-HANDOFF: voice-consistency with zero receipts fails",
        s1_session, s1_plan, "voice-consistency", [])
    # Completing character-consistency with a valid receipt allows
    # the dependent step when every other dependency is ready (the
    # earlier batch also needs production-systems).
    voice_receipts = [_receipt("command-authority"),
                      _receipt("character-consistency"),
                      _receipt("production-systems")]
    voice_packet = build_handoff_packet(
        s1_session, s1_plan, "voice-consistency", voice_receipts, CATALOG)
    check("CF-P1-002-R1-HANDOFF: voice-consistency is handed off once "
          "its dependency is receipted",
          voice_packet["step_id"] == "voice-consistency"
          and voice_packet["satisfied_dependencies"]
          == ["character-consistency"],
          f"satisfied={voice_packet['satisfied_dependencies']}")
    check("CF-P1-002-R1-HANDOFF: a packet lists only dependencies "
          "actually present in validated receipts",
          voice_packet["satisfied_dependencies"]
          == ["character-consistency"]
          and voice_packet["completed_step_ids"]
          == ["command-authority", "character-consistency",
              "production-systems"],
          f"packet={voice_packet['satisfied_dependencies']}, "
          f"{voice_packet['completed_step_ids']}")
    # The first command-authority step is available with no deps.
    first_packet = build_handoff_packet(
        s1_session, s1_plan, "command-authority", [], CATALOG)
    check("CF-P1-002-R1-HANDOFF: the first command-authority step is "
          "available with no dependencies",
          first_packet["step_id"] == "command-authority"
          and first_packet["satisfied_dependencies"] == [])
    # A receipt for only character-consistency is not enough: the
    # earlier batch (command-authority, production-systems) is not
    # complete.
    _handoff_fails(
        "CF-P1-002-R1-HANDOFF: voice-consistency fails when the earlier "
        "batch is incomplete",
        s1_session, s1_plan, "voice-consistency",
        [_receipt("character-consistency")])
    # A forged receipt for an unknown or different plan ID fails.
    _handoff_fails(
        "CF-P1-002-R1-HANDOFF: a receipt for a different plan ID fails",
        s1_session, s1_plan, "voice-consistency",
        [_receipt("command-authority", plan_id="plan-someone-else"),
         _receipt("character-consistency"),
         _receipt("production-systems")])
    _handoff_fails(
        "CF-P1-002-R1-HANDOFF: a receipt for an unknown step fails",
        s1_session, s1_plan, "voice-consistency",
        [_receipt("command-authority"),
         _receipt("character-consistency"),
         _receipt("production-systems"),
         _receipt("not-a-step")])
    # Duplicate, malformed and non-completed receipts fail.
    _handoff_fails(
        "CF-P1-002-R1-HANDOFF: a duplicate receipt fails",
        s1_session, s1_plan, "voice-consistency",
        [_receipt("command-authority"),
         _receipt("command-authority"),
         _receipt("character-consistency"),
         _receipt("production-systems")])
    _handoff_fails(
        "CF-P1-002-R1-HANDOFF: a receipt with status 'complete' fails",
        s1_session, s1_plan, "voice-consistency",
        [_receipt("command-authority"),
         _receipt("character-consistency", status="complete"),
         _receipt("production-systems")])
    _handoff_fails(
        "CF-P1-002-R1-HANDOFF: a receipt with an unknown field fails",
        s1_session, s1_plan, "voice-consistency",
        [_receipt("command-authority"),
         {**_receipt("character-consistency"), "note": "done"},
         _receipt("production-systems")])
    _handoff_fails(
        "CF-P1-002-R1-HANDOFF: a receipt missing its status fails",
        s1_session, s1_plan, "voice-consistency",
        [_receipt("command-authority"),
         {"plan_id": s1_plan["plan_id"],
          "step_id": "character-consistency"},
         _receipt("production-systems")])
    _handoff_fails(
        "CF-P1-002-R1-HANDOFF: a non-object receipt fails",
        s1_session, s1_plan, "voice-consistency",
        [_receipt("command-authority"), "character-consistency"])
    _handoff_fails(
        "CF-P1-002-R1-HANDOFF: a non-list receipts value fails",
        s1_session, s1_plan, "voice-consistency",
        "character-consistency")
    # A handoff for an already-completed step fails.
    _handoff_fails(
        "CF-P1-002-R1-HANDOFF: a handoff for an already-completed step "
        "fails",
        s1_session, s1_plan, "command-authority",
        [_receipt("command-authority")])
    # A valid plan modified after hashing fails validation.
    tampered_plan = clone(s1_plan)
    tampered_plan["steps"][0]["skill"] = "voice-consistency"
    _handoff_fails(
        "CF-P1-002-R1-HANDOFF: a plan modified after hashing fails",
        s1_session, tampered_plan, "command-authority", [])
    # Copied, forged, expired, closed and wrong sessions fail.
    _handoff_fails(
        "CF-P1-002-R1-HANDOFF: a copied session fails",
        copy.copy(s1_session), s1_plan, "command-authority", [])
    _handoff_fails(
        "CF-P1-002-R1-HANDOFF: a forged session fails",
        SimpleNamespace(session_id=s1_session.session_id),
        s1_plan, "command-authority", [])
    wrong_session = fresh_session()
    _handoff_fails(
        "CF-P1-002-R1-HANDOFF: a different session fails (plan/session "
        "binding)",
        wrong_session, s1_plan, "command-authority", [])
    closing_session = fresh_session()
    closing_plan = build_workflow_plan(closing_session, request(
        "r1-handoff-closing", "GENERATE_FROM_SCRIPT", PROFILES["s1"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "explainer_structure": True}),
        CATALOG)
    close_session(closing_session)
    _handoff_fails(
        "CF-P1-002-R1-HANDOFF: a closed session fails",
        closing_session, closing_plan, "command-authority", [])
    short_session = fresh_session(lifetime_seconds=1)
    short_plan = build_workflow_plan(short_session, request(
        "r1-handoff-short", "GENERATE_FROM_SCRIPT", PROFILES["s1"],
        {"dialogue": True, "languages": ["en"],
         "recurring_character": True, "explainer_structure": True}),
        CATALOG)
    time.sleep(1.2)
    _handoff_fails(
        "CF-P1-002-R1-HANDOFF: an expired session fails",
        short_session, short_plan, "command-authority", [])
    _handoff_fails(
        "CF-P1-002-R1-HANDOFF: a missing session fails",
        None, s1_plan, "command-authority", [])

    # --- CF-P1-002-R1-CATALOG: catalog semantic integrity -----------
    from runtime.skill_router import catalog_fingerprint
    check("CF-P1-002-R1-CATALOG: the stored fingerprint equals the "
          "recomputed fingerprint",
          CATALOG.get("integrity", {}).get("fingerprint")
          == catalog_fingerprint(CATALOG)
          and CATALOG.get("integrity", {}).get("algorithm")
          == "sha256-canonical-json-v1")

    def _altered_loads(label, mutator):
        altered = clone(CATALOG)
        mutator(altered)
        with tempfile.NamedTemporaryFile("w", suffix=".json",
                                        delete=False) as f:
            json.dump(altered, f)
            path = f.name
        try:
            load_routing_catalog(path)
            check(label, False, "altered catalog loaded instead of "
                  "being refused")
        except RoutingError:
            check(label, True)
        finally:
            os.unlink(path)

    def _altered_loads_refingerprinted(label, mutator):
        # The same altered catalog with a CORRECTLY recomputed
        # fingerprint: the fingerprint check passes, so rejection must
        # come from the semantic validation itself. This proves the
        # semantic layer independently of the fingerprint backstop.
        altered = clone(CATALOG)
        mutator(altered)
        altered["integrity"] = {
            "algorithm": "sha256-canonical-json-v1",
            "fingerprint": catalog_fingerprint(altered),
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json",
                                        delete=False) as f:
            json.dump(altered, f)
            path = f.name
        try:
            load_routing_catalog(path)
            check(label, False, "altered catalog loaded instead of "
                  "being refused by semantic validation")
        except RoutingError:
            check(label, True)
        finally:
            os.unlink(path)

    _altered_loads(
        "CF-P1-002-R1-CATALOG: a catalog missing TC-8 is rejected",
        lambda c: c["graph"].update({"true_conflicts": [
            tc for tc in c["graph"]["true_conflicts"]
            if tc["id"] != "TC-8"]}))
    _altered_loads_refingerprinted(
        "CF-P1-002-R1-CATALOG: a catalog missing TC-8 is rejected by "
        "semantic validation",
        lambda c: c["graph"].update({"true_conflicts": [
            tc for tc in c["graph"]["true_conflicts"]
            if tc["id"] != "TC-8"]}))
    _altered_loads(
        "CF-P1-002-R1-CATALOG: altered applicable modes are rejected",
        lambda c: next(
            e for e in c["skills"]
            if e["skill"] == "realistic-person")
        ["applicable_modes"].remove("GENERATE_FROM_SCRIPT"))
    _altered_loads_refingerprinted(
        "CF-P1-002-R1-CATALOG: a skill with no applicable mode is "
        "rejected by semantic validation",
        lambda c: next(
            e for e in c["skills"]
            if e["skill"] == "realistic-person")
        .update({"applicable_modes": []}))
    _altered_loads_refingerprinted(
        "CF-P1-002-R1-CATALOG: a missing graph edge is rejected by "
        "semantic validation",
        lambda c: c["graph"].update({"edges": [
            e for e in c["graph"]["edges"]
            if not (e["from"] == "character-consistency"
                    and e["to"] == "voice-consistency")]}))
    _altered_loads_refingerprinted(
        "CF-P1-002-R1-CATALOG: a missing dependency is rejected by "
        "semantic validation",
        lambda c: next(
            e for e in c["skills"]
            if e["skill"] == "voice-consistency")
        ["dependencies"].remove("character-consistency"))
    _altered_loads_refingerprinted(
        "CF-P1-002-R1-CATALOG: an asymmetric conflict pair is rejected "
        "by semantic validation",
        lambda c: next(
            e for e in c["skills"]
            if e["skill"] == "realistic-person")
        ["conflicts"].remove("live-action-vfx"))
    _altered_loads_refingerprinted(
        "CF-P1-002-R1-CATALOG: an invalid parallel-group reference is "
        "rejected by semantic validation",
        lambda c: next(
            g for g in c["graph"]["parallel_groups"]
            if g["name"] == "foundation-planning")
        ["skills"].append("not-a-skill"))
    _altered_loads(
        "CF-P1-002-R1-CATALOG: an incorrect fingerprint is rejected",
        lambda c: c["integrity"].update({"fingerprint": "0" * 64}))
    _altered_loads(
        "CF-P1-002-R1-CATALOG: a missing integrity record is rejected",
        lambda c: c.pop("integrity"))
    _altered_loads_refingerprinted(
        "CF-P1-002-R1-CATALOG: a renamed parallel group is rejected by "
        "semantic validation",
        lambda c: next(
            g for g in c["graph"]["parallel_groups"]
            if g["name"] == "foundation-planning")
        .update({"name": "foundation-planning-renamed"}))
    _altered_loads_refingerprinted(
        "CF-P1-002-R1-CATALOG: a parallel group with an internal "
        "dependency is rejected by semantic validation",
        lambda c: next(
            g for g in c["graph"]["parallel_groups"]
            if g["name"] == "foundation-planning")
        ["skills"].__setitem__(1, "voice-consistency"))
    check("CF-P1-002-R1-CATALOG: the original generated catalog still "
          "loads successfully",
          load_routing_catalog()["catalog_version"] == "2.4")

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
