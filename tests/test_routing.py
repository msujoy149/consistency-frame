#!/usr/bin/env python3
"""P0 v2.4 routing tests. Run via tests/run-tests.sh or directly:
  python3 tests/test_routing.py
Exit 0 = PASS, 1 = FAIL. Test IDs: P0-ROUTING, P0-SCHEMA (part),
CF-P0-ROUTING-001/002/003/004, CF-P0-ROUTING-005 (P0-006 composable
routing scenarios), CF-P0-ROUTING-006 (no video-type mutual exclusion).
"""
import importlib.util
import json
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
try:
    import yaml
except ImportError:
    print("SKIP test_routing: PyYAML not installed (pip install pyyaml)")
    sys.exit(0)

_spec = importlib.util.spec_from_file_location(
    "validate_repo", os.path.join(ROOT, "scripts", "validate-repo.py"))
_validate_repo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_validate_repo)
validate_instance = _validate_repo.validate_instance

failures = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def load_yaml(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_json(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


def errors_for(schema, value):
    errs = []
    validate_instance(schema, value, "$", errs)
    return errs


# --- Production routing (CF-WO-P1-002) --------------------------------
# P0 defined the composable routing model as a test-only helper; P1-002
# promoted it into production code (runtime/skill_router.py), reading
# only the compiled catalog (registry/routing-catalog.json). The
# duplicate test-only algorithm was removed: every scenario below
# runs through the production resolver, with the same expected skill
# sets, the same refusal cases and the same precedence invariant.
# The resolver takes a structured routing request (schemas/
# skill-routing-request.json): a task id, an intent mode, a validated
# v2.5 production profile and structured hints. Scenario 7 and the
# reference-video fixture are video-to-video remakes, so they run in
# REMAKE_OR_TRANSFORM mode (video-regeneration is not applicable in
# GENERATE_FROM_SCRIPT) with the mode's required evidence.
sys.path.insert(0, os.path.abspath(ROOT))
from runtime.skill_router import (  # noqa: E402
    RoutingError, load_routing_catalog, resolve_skills)

CATALOG = load_routing_catalog()


def route_request(prof, hints, mode="GENERATE_FROM_SCRIPT",
                  task_id="p0-routing", **extra):
    req = {"schema_version": "2.4", "task_id": task_id,
           "intent_mode": mode, "production_profile": prof,
           "hints": hints}
    req.update(extra)
    return resolve_skills(req, CATALOG)


REMAKE_EVIDENCE = {"explicit_request": True,
                   "rights_provenance_checked": True}


def main():
    skills_reg = load_json("registry/skills.json")
    fs_skills = sorted(d for d in os.listdir(os.path.join(ROOT, "skills"))
                       if os.path.isdir(os.path.join(ROOT, "skills", d)))
    reg_ids = {r["skill_id"] for r in skills_reg["records"]}

    # --- CF-P0-ROUTING-001: routing matrix completeness ------------------
    routing = load_yaml("architecture/SKILL_ROUTING_MATRIX.yaml")
    check("CF-P0-ROUTING-001: routing matrix version is 2.4",
          str(routing.get("version")) == "2.4")
    entries = routing.get("skills") or []
    check("CF-P0-ROUTING-001: routing matrix covers all 15 skills",
          {e.get("skill_id") for e in entries} == reg_ids
          and len(entries) == 15 == len(fs_skills),
          f"entries={len(entries)}")
    required_fields = ("skill_id", "skill", "activation_trigger",
                       "non_trigger", "required_inputs", "expected_outputs",
                       "dependencies", "precedence", "conflicts",
                       "applicable_modes", "quality_gate",
                       "approval_conditions")
    for e in entries:
        check(f"routing entry {e.get('skill_id')} has all required fields",
              all(f in e for f in required_fields))
        check(f"routing entry {e.get('skill_id')} trigger is non-empty",
              isinstance(e.get("activation_trigger"), str)
              and len(e["activation_trigger"].strip()) >= 20)
        check(f"routing entry {e.get('skill_id')} lists required inputs",
              isinstance(e.get("required_inputs"), list)
              and len(e["required_inputs"]) >= 1)
        check(f"routing entry {e.get('skill_id')} lists expected outputs",
              isinstance(e.get("expected_outputs"), list)
              and len(e["expected_outputs"]) >= 1)
        check(f"routing entry {e.get('skill_id')} lists applicable modes",
              isinstance(e.get("applicable_modes"), list)
              and len(e["applicable_modes"]) >= 1)
        check(f"routing entry {e.get('skill_id')} names a quality gate",
              isinstance(e.get("quality_gate"), str)
              and len(e["quality_gate"].strip()) >= 10)
    precs = sorted(e["precedence"] for e in entries)
    check("CF-P0-ROUTING-001: precedence values are unique 1..15",
          precs == list(range(1, 16)), f"precs={precs}")
    router = [e for e in entries if e["skill"] == "command-authority"]
    check("CF-P0-ROUTING-001: command-authority (the router) is precedence 1",
          len(router) == 1 and router[0]["precedence"] == 1)
    # Dependencies must point at earlier-precedence skills (a skill cannot
    # depend on a skill that runs after it).
    prec_by_skill = {e["skill"]: e["precedence"] for e in entries}
    for e in entries:
        for dep in e.get("dependencies") or []:
            check(f"routing entry {e['skill']} dependency {dep} runs earlier",
                  prec_by_skill.get(dep, 99) < e["precedence"],
                  f"{dep} precedence {prec_by_skill.get(dep)} vs {e['precedence']}")

    # --- CF-P0-ROUTING-002: workflow graph -------------------------------
    graph = load_yaml("architecture/WORKFLOW_GRAPH.yaml")
    check("CF-P0-ROUTING-002: workflow graph version is 2.4",
          str(graph.get("version")) == "2.4")
    nodes = graph.get("nodes") or []
    check("CF-P0-ROUTING-002: graph has all 15 skill nodes",
          {n.get("id") for n in nodes} == set(fs_skills) and len(nodes) == 15)
    edges = graph.get("edges") or []
    node_ids = {n.get("id") for n in nodes}
    check("CF-P0-ROUTING-002: every edge endpoint is a known skill",
          all(e.get("from") in node_ids and e.get("to") in node_ids
              for e in edges))
    check("CF-P0-ROUTING-002: every edge states a reason",
          all(isinstance(e.get("reason"), str) and e["reason"].strip()
              for e in edges))
    # Acyclicity (Kahn).
    children: dict[str, set[str]] = {n: set() for n in node_ids}
    indegree = {n: 0 for n in node_ids}
    for e in edges:
        if e["to"] not in children[e["from"]]:
            children[e["from"]].add(e["to"])
            indegree[e["to"]] += 1
    queue = [n for n, d in indegree.items() if d == 0]
    visited = 0
    while queue:
        n = queue.pop()
        visited += 1
        for dst in children[n]:
            indegree[dst] -= 1
            if indegree[dst] == 0:
                queue.append(dst)
    check("CF-P0-ROUTING-002: workflow graph is acyclic",
          visited == len(node_ids), f"visited {visited}/{len(node_ids)}")
    # Graph edges must agree with routing-matrix dependencies. The graph
    # also carries router edges (command-authority -> each skill), which
    # are NOT matrix dependencies: the router selects every skill.
    matrix_deps = {(d, e["skill"]) for e in entries
                   for d in (e.get("dependencies") or [])}
    graph_edges = {(e["from"], e["to"]) for e in edges}
    check("CF-P0-ROUTING-002: every routing-matrix dependency is a graph edge",
          matrix_deps <= graph_edges,
          f"missing={sorted(matrix_deps - graph_edges)}")
    non_dep_edges = graph_edges - matrix_deps
    check("CF-P0-ROUTING-002: non-dependency graph edges are router edges only",
          all(src == "command-authority" for src, _ in non_dep_edges),
          f"unexpected={sorted(non_dep_edges)}")
    # Parallel groups must not contain a dependent pair.
    for group in graph.get("parallel_groups") or []:
        members = set(group.get("skills") or [])
        check(f"parallel group '{group.get('name')}' has no internal dependency",
              not any((a, b) in graph_edges for a in members for b in members))
    # Conditional parallel groups must state their condition and name real skills.
    for group in graph.get("conditional_parallel_groups") or []:
        check(f"conditional group '{group.get('name')}' states a condition",
              isinstance(group.get("condition"), str)
              and len(group["condition"].strip()) >= 20)
        check(f"conditional group '{group.get('name')}' names known skills",
              set(group.get("skills") or []) <= node_ids
              and len(group.get("skills") or []) >= 2)

    # --- CF-P0-ROUTING-003: companion + agent matrices -------------------
    companions = load_yaml("architecture/COMPANION_CAPABILITY_REGISTRY.yaml")
    check("CF-P0-ROUTING-003: companion registry version is 2.4",
          str(companions.get("version")) == "2.4")
    comps = companions.get("companions") or []
    check("CF-P0-ROUTING-003: companion registry lists VoiceStudio + OpenMontage",
          {c.get("name") for c in comps} == {"VoiceStudio", "OpenMontage"})
    for c in comps:
        check(f"companion {c.get('name')} states a licence",
              isinstance(c.get("licence"), str) and c["licence"])
        for cap in c.get("capabilities") or []:
            check(f"companion {c.get('name')} capability evidence_level is honest",
                  cap.get("evidence_level") in (
                      "upstream_inspected_pinned_commit", "present_locally",
                      "exercised_recorded_run", "production_verified"))
    agents_doc = load_yaml("architecture/AGENT_COMPATIBILITY_MATRIX.yaml")
    check("CF-P0-ROUTING-003: agent matrix version is 2.4",
          str(agents_doc.get("version")) == "2.4")
    agents = agents_doc.get("agents") or []
    check("CF-P0-ROUTING-003: agent matrix covers the 10 named agents",
          {a.get("name") for a in agents} == {"Muse", "ChatGPT", "Codex",
                                              "Claude", "Claude Code",
                                              "Gemini CLI",
                                              "Antigravity", "OpenCode",
                                              "Cursor", "GitHub Copilot"})
    verified = [a for a in agents if a.get("verified")]
    check("CF-P0-ROUTING-003: only Muse is marked verified",
          len(verified) == 1 and verified[0]["name"] == "Muse",
          f"verified={[a['name'] for a in verified]}")
    non_hosts = {n.get("name"): n for n in (agents_doc.get("non_hosts") or [])}
    check("CF-P0-ROUTING-003: OpenRouter is a model-routing layer, not a host",
          non_hosts.get("OpenRouter", {}).get("is_agent_host") is False
          and "model-routing" in (non_hosts.get("OpenRouter", {}).get("kind") or ""))
    check("CF-P0-ROUTING-003: Colab needs a Notebook/Agent Runtime",
          non_hosts.get("Google Colab", {}).get("is_agent_host") is False)

    # --- CF-P0-ROUTING-004: companion evidence levels (P0-002 §6) --------
    # evidence_level REPLACED the old `status` field. The closed set is
    # upstream_inspected_pinned_commit / present_locally /
    # exercised_recorded_run / production_verified. Every exercised run
    # carries a run reference; pinned commits match setup.sh; zero
    # production_verified claims exist in this account.
    EVIDENCE_LEVELS = ("upstream_inspected_pinned_commit",
                       "present_locally", "exercised_recorded_run",
                       "production_verified")
    # Pins as recorded in setup.sh (full 40-char SHAs).
    setup_text = open(os.path.join(ROOT, "setup.sh"),
                      encoding="utf-8").read()
    setup_pins = set(re.findall(r"\b[0-9a-f]{40}\b", setup_text))
    expected_pins = {
        "VoiceStudio": "2f2f5a9b0e982c6147efc6baaeae62936f29b79b",
        "OpenMontage": "fecb9a1e3cc23ef84de30b272059457a427f16f8",
    }
    check("CF-P0-ROUTING-004: setup.sh pins the two companion commits",
          set(expected_pins.values()) <= setup_pins,
          f"pins in setup.sh={sorted(setup_pins)}")
    level_counts: dict[str, int] = {lvl: 0 for lvl in EVIDENCE_LEVELS}
    total_caps = 0
    for c in comps:
        check(f"CF-P0-ROUTING-004: companion {c.get('name')} pinned commit "
              "matches the repo pin",
              c.get("pinned_commit") == expected_pins.get(c.get("name")),
              f"pinned={c.get('pinned_commit')}")
        for group in ("capabilities", "interfaces"):
            for item in c.get(group) or []:
                label = item.get("capability") or item.get("name")
                level = item.get("evidence_level")
                check(f"companion {c.get('name')} {group[:-1]} '{label}' "
                      "evidence_level is from the closed set",
                      level in EVIDENCE_LEVELS, f"level={level!r}")
                check(f"companion {c.get('name')} {group[:-1]} '{label}' "
                      "carries no retired 'status' field",
                      "status" not in item)
                if level == "exercised_recorded_run":
                    ref = item.get("run_reference")
                    check(f"companion {c.get('name')} {group[:-1]} '{label}' "
                          "exercised_recorded_run has a run reference",
                          isinstance(ref, str) and len(ref.strip()) >= 20,
                          f"run_reference={ref!r}")
                if group == "capabilities":
                    total_caps += 1
                    if level in level_counts:
                        level_counts[level] += 1
    check("CF-P0-ROUTING-004: registry lists exactly 20 capabilities",
          total_caps == 20, f"total={total_caps}")
    check("CF-P0-ROUTING-004: capability counts by evidence level are "
          "3 exercised / 16 present_locally / 1 upstream-inspected / "
          "0 production_verified",
          level_counts == {"upstream_inspected_pinned_commit": 1,
                           "present_locally": 16,
                           "exercised_recorded_run": 3,
                           "production_verified": 0},
          f"counts={level_counts}")
    check("CF-P0-ROUTING-004: zero production_verified claims",
          level_counts["production_verified"] == 0,
          f"production_verified={level_counts['production_verified']}")
    # No production_verified anywhere (capabilities + interfaces) unless
    # it carries a production record.
    for c in comps:
        for group in ("capabilities", "interfaces"):
            for item in c.get(group) or []:
                label = item.get("capability") or item.get("name")
                if item.get("evidence_level") == "production_verified":
                    check(f"companion {c.get('name')} {group[:-1]} '{label}' "
                          "production_verified has a production record",
                          isinstance(item.get("production_record"), str)
                          and len(item["production_record"].strip()) >= 10)

    # --- P0-SCHEMA (part): v2.4 schemas, dual-version 2.4/2.5 since P0-006 --
    # P0-006 extended these four schemas additively (schema_version 2.5);
    # the enum ["2.4", "2.5"] keeps every valid v2.4 record valid.
    for fixture, schema_name in (
            ("scene-plan-valid.json", "scene-plan.json"),
            ("shot-plan-valid.json", "shot-plan.json"),
            ("performance-plan-valid.json", "performance-plan.json"),
            ("script-to-performance-valid.json", "script-to-performance.json")):
        with open(os.path.join(ROOT, "schemas", schema_name), encoding="utf-8") as f:
            schema = json.load(f)
        with open(os.path.join(ROOT, "tests", "fixtures", fixture), encoding="utf-8") as f:
            value = json.load(f)
        errs = errors_for(schema, value)
        check(f"valid fixture {fixture} validates", not errs, "; ".join(errs))
        check(f"schema {schema_name} is version 2.4 or dual-version 2.4/2.5",
              schema.get("properties", {}).get("schema_version", {}).get("enum") in (["2.4"], ["2.4", "2.5"]))

    # Dialogue preservation: VERBATIM contract rejects a rewrite claim.
    bad = load_json("tests/fixtures/script-to-performance-valid.json")
    bad["dialogue_mode"] = "SCRIPT_EDIT_REQUESTED"
    bad["dialogue_rewrite_authorised"] = False
    # The schema itself cannot express the cross-field rule; the policy is
    # documented in the schema description and enforced by the router.
    # What the schema CAN enforce: the two fields must be present and typed.
    with open(os.path.join(ROOT, "schemas", "script-to-performance.json"),
              encoding="utf-8") as f:
        s2p = json.load(f)
    check("script-to-performance requires dialogue_mode + dialogue_rewrite_authorised",
          bool(errors_for(s2p, {k: v for k, v in bad.items()
                                if k not in ("dialogue_mode",)})))
    check("script-to-performance rejects an unknown top-level field",
          bool(errors_for(s2p, {**load_json("tests/fixtures/script-to-performance-valid.json"),
                                "surprise_field": True})))

    # Performance plan: a line without lip_sync_required is rejected.
    with open(os.path.join(ROOT, "schemas", "performance-plan.json"),
              encoding="utf-8") as f:
        perf_schema = json.load(f)
    bad_perf = load_json("tests/fixtures/performance-plan-valid.json")
    del bad_perf["lines"][0]["lip_sync_required"]
    check("performance-plan line without lip_sync_required is rejected",
          bool(errors_for(perf_schema, bad_perf)))

    # Scene plan: a beat without dramatic_intent is rejected.
    with open(os.path.join(ROOT, "schemas", "scene-plan.json"),
              encoding="utf-8") as f:
        scene_schema = json.load(f)
    bad_scene = load_json("tests/fixtures/scene-plan-valid.json")
    del bad_scene["scenes"][0]["beats"][0]["dramatic_intent"]
    check("scene-plan beat without dramatic_intent is rejected",
          bool(errors_for(scene_schema, bad_scene)))

    # --- CF-P0-ROUTING-005: P0-006 composable routing scenarios ---------
    # Each scenario resolves skills through the production resolver
    # (runtime/skill_router.py) from a schema-valid production profile
    # + hints, and asserts the exact resolved set, that no matrix
    # conflict blocks the valid combination, and the scenario-specific
    # routing proofs. The matrix/graph are version-agnostic here on
    # purpose: R1 may bump them 2.4 -> 2.5.
    with open(os.path.join(ROOT, "schemas", "production-profile.json"),
              encoding="utf-8") as f:
        prof_schema = json.load(f)
    check("CF-P0-ROUTING-005: production-profile schema is version 2.5",
          prof_schema.get("properties", {}).get("schema_version", {}).get("enum") == ["2.5"])
    routing_profiles = {
        "s1": load_json("tests/fixtures/routing-profile-s1-explainer-2d.json"),
        "s2": load_json("tests/fixtures/routing-profile-s2-stylized-3d.json"),
        "s3": load_json("tests/fixtures/production-profile-valid-digital-human.json"),
        "s4": load_json("tests/fixtures/routing-profile-s4-human-bird.json"),
        "s5": load_json("tests/fixtures/routing-profile-s5-live-action-creature.json"),
        "s7": load_json("tests/fixtures/routing-profile-s7-video-to-video.json"),
        "s8": load_json("tests/fixtures/routing-profile-s8-photorealistic-explainer.json"),
        # S6 (real animal footage) is a schema-valid fixture since
        # integration added the captured-footage vocabulary
        # (visual_style captured-live-action, motion captured-motion).
        "s6": load_json("tests/fixtures/routing-profile-s6-real-animal.json"),
    }
    for key, prof in routing_profiles.items():
        errs = errors_for(prof_schema, prof)
        check(f"CF-P0-ROUTING-005: routing fixture {key} validates "
              "against production-profile v2.5", not errs, "; ".join(errs))
    # Old valid fixtures still pass as routing inputs.
    for fixture in ("production-profile-reference-video.json",
                    "production-profile-script-only.json"):
        errs = errors_for(prof_schema, load_json(f"tests/fixtures/{fixture}"))
        check(f"CF-P0-ROUTING-005: existing valid fixture {fixture} "
              "still validates", not errs, "; ".join(errs))
    # S6 (real animal footage) now has a schema-valid fixture (see the
    # routing_profiles dict above); it routes below like the others.
    base_layers = {"command-authority", "production-systems",
                   "humanized-production"}
    scenarios = {
        "s1": (routing_profiles["s1"],
               {"dialogue": True, "languages": ["en"],
                "recurring_character": True, "explainer_structure": True},
               base_layers | {"character-consistency", "voice-consistency",
                              "explainer-animation"}),
        "s2": (routing_profiles["s2"],
               {"dialogue": True, "languages": ["en"],
                "recurring_character": True},
               base_layers | {"character-consistency", "voice-consistency",
                              "cinematic-power"}),
        "s3": (routing_profiles["s3"],
               {"dialogue": True, "languages": ["bn"],
                "recurring_character": True, "consent": True},
               base_layers | {"character-consistency", "voice-consistency",
                              "language-authenticity", "realistic-person"}),
        "s4": (routing_profiles["s4"],
               {"dialogue": True, "languages": ["en"],
                "recurring_character": True, "consent": True},
               base_layers | {"character-consistency", "voice-consistency",
                              "cinematic-power", "realistic-person"}),
        "s5": (routing_profiles["s5"],
               {"dialogue": True, "languages": ["en"],
                "recurring_character": True},
               base_layers | {"character-consistency", "voice-consistency",
                              "cinematic-power", "live-action-vfx"}),
        "s6": (routing_profiles["s6"], {}, base_layers | {"live-action-vfx"}),
        "s7": (routing_profiles["s7"],
               {"dialogue": True, "languages": ["en"],
                "recurring_character": True},
               base_layers | {"character-consistency", "voice-consistency",
                              "cinematic-power", "video-regeneration"}),
        "s8": (routing_profiles["s8"],
               {"dialogue": True, "languages": ["en"],
                "recurring_character": True, "explainer_structure": True,
                "consent": True},
               base_layers | {"character-consistency", "voice-consistency",
                              "realistic-person"}),
    }
    resolved = {}
    for key, (prof, hints, expected) in scenarios.items():
        # Scenario 7 is a video-to-video remake: REMAKE_OR_TRANSFORM
        # mode with the mode's required evidence. The rest generate
        # from a script.
        if key == "s7":
            mode, extra = "REMAKE_OR_TRANSFORM", REMAKE_EVIDENCE
        else:
            mode, extra = "GENERATE_FROM_SCRIPT", {}
        try:
            res = route_request(prof, hints, mode=mode,
                                task_id=f"p0-routing-{key}", **extra)
        except RoutingError as exc:
            check(f"CF-P0-ROUTING-005: scenario {key} resolves", False,
                  str(exc))
            continue
        resolved[key] = res
        check(f"CF-P0-ROUTING-005: scenario {key} selects exactly the "
              "expected skills",
              res["skills"] == expected,
              f"got={sorted(res['skills'])} expected={sorted(expected)}")
        check(f"CF-P0-ROUTING-005: scenario {key} is not blocked by a "
              "matrix conflict", res["blocked"] == [],
              f"blocked={res['blocked']}")
    # (1) 2D cartoon explainer, 2 characters: explainer profile + common
    # layers; the two character designs stay apart (character-consistency).
    if "s1" in resolved:
        check("CF-P0-ROUTING-005: (1) explainer-animation selected, "
              "cinematic-power/realistic-person/live-action-vfx not selected",
              "explainer-animation" in resolved["s1"]["skills"]
              and not ({"cinematic-power", "realistic-person",
                        "live-action-vfx"} & resolved["s1"]["skills"]))
        check("CF-P0-ROUTING-005: (1) style is flat-2d-vector, not a "
              "default cartoon", resolved["s1"]["styles"] == {"flat-2d-vector"})
    # (2) Stylized 3D story: 3D style lock, stable identity, continuity.
    if "s2" in resolved:
        check("CF-P0-ROUTING-005: (2) cinematic-power style lock + "
              "character-consistency, explainer/realistic-person excluded",
              "cinematic-power" in resolved["s2"]["skills"]
              and "character-consistency" in resolved["s2"]["skills"]
              and not ({"explainer-animation", "realistic-person"}
                       & resolved["s2"]["skills"]))
        check("CF-P0-ROUTING-005: (2) style is stylized-3d",
              resolved["s2"]["styles"] == {"stylized-3d"})
    # (3) Photorealistic digital human, Bengali: image-to-video workflow,
    # NOT cartoon, NOT falsely labelled live-action.
    if "s3" in resolved:
        check("CF-P0-ROUTING-005: (3) realistic-person + language-"
              "authenticity (Bengali), live-action-vfx/explainer excluded",
              "realistic-person" in resolved["s3"]["skills"]
              and "language-authenticity" in resolved["s3"]["skills"]
              and not ({"live-action-vfx", "explainer-animation",
                        "kids-family-animation"} & resolved["s3"]["skills"]))
        check("CF-P0-ROUTING-005: (3) profile is not live-action footage "
              "and style is photorealistic-digital-human",
              routing_profiles["s3"]["is_live_action_footage"] is False
              and resolved["s3"]["styles"]
              == {"photorealistic-digital-human"})
        rp = next(e for e in entries if e["skill"] == "realistic-person")
        rp_out = " ".join(rp.get("expected_outputs") or [])
        check("CF-P0-ROUTING-005: (3) realistic-person outputs cover "
              "natural movement + language-matched lip-sync",
              "natural movement" in rp_out and "lip-sync" in rp_out)
    # (4) Human + talking bird: composable human + creature performance.
    if "s4" in resolved:
        check("CF-P0-ROUTING-005: (4) realistic-person AND cinematic-power "
              "run together (human + creature performance)",
              {"realistic-person", "cinematic-power"}
              <= resolved["s4"]["skills"])
        subs = {s["character_id"]: s for s in
                routing_profiles["s4"]["per_subject_overrides"]}
        check("CF-P0-ROUTING-005: (4) human uses human-mouth-lips, bird "
              "uses bird-beak — never human lips on a bird",
              subs["char-nadia-001"]["articulation_target"]
              == "human-mouth-lips"
              and subs["char-kiki-001"]["articulation_target"] == "bird-beak")
        cp = next(e for e in entries if e["skill"] == "cinematic-power")
        check("CF-P0-ROUTING-005: (4) cinematic-power outputs cover "
              "creature performance",
              "creature performance" in " ".join(cp.get("expected_outputs") or []))
    # (5) Live-action human + CGI creature: VFX compositing rules.
    if "s5" in resolved:
        check("CF-P0-ROUTING-005: (5) live-action-vfx + cinematic-power, "
              "realistic-person excluded (the human is real footage)",
              {"live-action-vfx", "cinematic-power"}
              <= resolved["s5"]["skills"]
              and "realistic-person" not in resolved["s5"]["skills"])
        lav = next(e for e in entries if e["skill"] == "live-action-vfx")
        lav_out = " ".join(lav.get("expected_outputs") or [])
        check("CF-P0-ROUTING-005: (5) live-action-vfx outputs cover light, "
              "shadow, reflections, eyelines, scale, contact",
              all(w in lav_out for w in
                  ("light", "shadow", "reflections", "eyelines", "scale",
                   "contact")))
        subs5 = {s["character_id"]: s for s in
                 routing_profiles["s5"]["per_subject_overrides"]}
        check("CF-P0-ROUTING-005: (5) per-subject provenance: human is "
              "live-action footage, creature is not",
              subs5["char-actor-001"]["is_live_action_footage"] is True
              and subs5["char-ember-001"]["is_live_action_footage"] is False)
    # (6) Real animal footage: real-animal handling, no CG rules forced.
    if "s6" in resolved:
        check("CF-P0-ROUTING-005: (6) live-action-vfx selected, no CG "
              "performance skill forced onto a real animal",
              "live-action-vfx" in resolved["s6"]["skills"]
              and not ({"cinematic-power", "realistic-person",
                        "explainer-animation"} & resolved["s6"]["skills"]))
        lav = next(e for e in entries if e["skill"] == "live-action-vfx")
        lav_out = " ".join(lav.get("expected_outputs") or [])
        check("CF-P0-ROUTING-005: (6) live-action-vfx outputs cover "
              "real-animal performance",
              "real-animal performance" in lav_out)
    # (7) Video-to-video: output style is the requested stylized style,
    # not the realistic source; identity + motion preserved.
    if "s7" in resolved:
        check("CF-P0-ROUTING-005: (7) video-regeneration selected, output "
              "style stylized-3d from a reference-video source",
              "video-regeneration" in resolved["s7"]["skills"]
              and resolved["s7"]["visual_style"] == "stylized-3d"
              and resolved["s7"]["source_media_type"] == "reference-video")
        check("CF-P0-ROUTING-005: (7) character-consistency selected "
              "(identity preserved across the transformation)",
              "character-consistency" in resolved["s7"]["skills"])
        old_refvid = route_request(
            load_json("tests/fixtures/production-profile-reference-video.json"),
            {"dialogue": True, "languages": ["en"],
             "recurring_character": True},
            mode="REMAKE_OR_TRANSFORM", task_id="p0-routing-refvid",
            **REMAKE_EVIDENCE)
        check("CF-P0-ROUTING-005: (7) existing reference-video fixture "
              "also routes to video-regeneration",
              "video-regeneration" in old_refvid["skills"])
    # (8) Photorealistic explainer: explainer structure, NOT flat 2D.
    if "s8" in resolved:
        check("CF-P0-ROUTING-005: (8) realistic-person selected and "
              "explainer-animation NOT selected for a photorealistic "
              "explainer",
              "realistic-person" in resolved["s8"]["skills"]
              and "explainer-animation" not in resolved["s8"]["skills"])
        check("CF-P0-ROUTING-005: (8) style is photorealistic-digital-human",
              resolved["s8"]["styles"] == {"photorealistic-digital-human"})
    # Style is never inferred as cartoon by default; source media is
    # never confused with rendering style.
    try:
        route_request({k: v for k, v in routing_profiles["s3"].items()
                       if k != "visual_style"}, {"dialogue": True},
                      task_id="p0-routing-nostyle")
        check("CF-P0-ROUTING-005: profile without visual_style is refused "
              "(no cartoon default)", False, "resolved without a style")
    except RoutingError:
        check("CF-P0-ROUTING-005: profile without visual_style is refused "
              "(no cartoon default)", True)
    refvid_cartoon = route_request(
        load_json("tests/fixtures/production-profile-reference-video.json"),
        {"dialogue": True, "recurring_character": True},
        mode="REMAKE_OR_TRANSFORM", task_id="p0-routing-refvid-cartoon",
        **REMAKE_EVIDENCE)
    check("CF-P0-ROUTING-005: same source-media (reference-video), "
          "different requested styles stay different",
          refvid_cartoon["styles"] == {"cartoon-2d"}
          and resolved.get("s7", {}).get("styles") == {"stylized-3d"})
    check("CF-P0-ROUTING-005: reference-image input does not make the "
          "style 'image' — S3 resolves photorealistic-digital-human",
          resolved.get("s3", {}).get("styles")
          == {"photorealistic-digital-human"})
    # Incompatible operations are still prevented (production resolver
    # refusals).
    for label, prof, hints in (
            ("single animation_type enum",
             load_json("tests/fixtures/production-profile-invalid-animation-type.json"),
             {"dialogue": True, "consent": True}),
            ("generated digital human labelled live-action",
             load_json("tests/fixtures/production-profile-invalid-digital-human-live-action.json"),
             {"dialogue": True, "consent": True}),
            ("realistic-person without a consent record",
             routing_profiles["s3"],
             {"dialogue": True, "languages": ["bn"],
              "recurring_character": True}),
            ("flat 2D vector + captured live-action in one shot",
             {**routing_profiles["s1"], "is_live_action_footage": True,
              "source_media_type": "captured-footage"},
             {"dialogue": True, "recurring_character": True,
              "explainer_structure": True}),
    ):
        try:
            route_request(prof, hints, task_id="p0-routing-refuse")
            check(f"CF-P0-ROUTING-005: incompatible operation refused — "
                  f"{label}", False, "resolved instead of refusing")
        except RoutingError:
            check(f"CF-P0-ROUTING-005: incompatible operation refused — "
                  f"{label}", True)
    bird_lips = json.loads(json.dumps(routing_profiles["s4"]))
    for sub in bird_lips["per_subject_overrides"]:
        if sub["character_id"] == "char-kiki-001":
            sub["articulation_target"] = "human-mouth-lips"
    try:
        route_request(bird_lips,
                      {"dialogue": True, "recurring_character": True,
                       "consent": True}, task_id="p0-routing-bird")
        check("CF-P0-ROUTING-005: incompatible operation refused — bird "
              "with human-mouth-lips articulation", False,
              "resolved instead of refusing")
    except RoutingError:
        check("CF-P0-ROUTING-005: incompatible operation refused — bird "
              "with human-mouth-lips articulation", True)
    # True conflicts stay recorded in the matrix: explainer-animation's
    # style lock forbids photorealism, and realistic-person is never
    # live-action footage — those pairs genuinely cannot both hold for
    # the same subject/shot.
    conflict_pairs = {(a, b) for e in entries for b in (e.get("conflicts") or [])
                      for a in (e["skill"],)}
    conflict_pairs |= {(b, a) for (a, b) in list(conflict_pairs)}
    check("CF-P0-ROUTING-005: true conflict explainer-animation / "
          "realistic-person stays recorded",
          ("explainer-animation", "realistic-person") in conflict_pairs)
    check("CF-P0-ROUTING-005: true conflict live-action-vfx / "
          "realistic-person stays recorded",
          ("live-action-vfx", "realistic-person") in conflict_pairs)
    # Precedence invariant across every scenario: a selected skill never
    # depends on a later-precedence skill (deps run earlier).
    prec_by_skill = {e["skill"]: e["precedence"] for e in entries}
    deps_by_skill = {e["skill"]: set(e.get("dependencies") or [])
                     for e in entries}
    prec_ok = all(
        prec_by_skill.get(d, 99) < prec_by_skill[s]
        for res in resolved.values() for s in res["skills"]
        for d in deps_by_skill.get(s, set()))
    check("CF-P0-ROUTING-005: every scenario respects matrix precedence "
          "(dependencies run earlier)", prec_ok)

    # --- CF-P0-ROUTING-006: no video-type mutual exclusion --------------
    # The old one-video-type-per-video model is withdrawn (§10): there is
    # no exclusive group left in the graph, and no blanket conflict
    # between the skills a valid scenario needs together. The acyclicity
    # test itself already exists above (CF-P0-ROUTING-002) and still runs.
    check("CF-P0-ROUTING-006: no video-type exclusive group remains in "
          "the workflow graph",
          not graph.get("exclusive_groups"),
          f"exclusive_groups={graph.get('exclusive_groups')}")
    check("CF-P0-ROUTING-006: cinematic-power / realistic-person is not "
          "a blanket matrix conflict (scenario 4 needs both)",
          ("cinematic-power", "realistic-person") not in conflict_pairs)

    print(f"test_routing: {'PASS' if not failures else 'FAIL'} "
          f"({len(failures)} failure(s))")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
