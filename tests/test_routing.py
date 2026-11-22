#!/usr/bin/env python3
"""P0 v2.4 routing tests. Run via tests/run-tests.sh or directly:
  python3 tests/test_routing.py
Exit 0 = PASS, 1 = FAIL. Test IDs: P0-ROUTING, P0-SCHEMA (part),
CF-P0-ROUTING-001/002/003/004.
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

    # --- P0-SCHEMA (part): new v2.4 schemas ------------------------------
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
        check(f"schema {schema_name} is version 2.4",
              schema.get("properties", {}).get("schema_version", {}).get("enum") == ["2.4"])

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

    print(f"test_routing: {'PASS' if not failures else 'FAIL'} "
          f"({len(failures)} failure(s))")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
