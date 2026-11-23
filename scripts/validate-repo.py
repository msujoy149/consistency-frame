#!/usr/bin/env python3
"""Consistency Frame P0 — repository validator (Python stdlib only).

Checks, all deterministic and offline:
  1. Every schema in schemas/*.json is valid JSON and a well-formed
     JSON Schema (subset): type/properties/required/enum/pattern/
     minLength/minimum/maximum/exclusiveMinimum/minItems/items/
     additionalProperties.
     schema_version must be "2.3" (v2.3 P0), "2.4" (v2.4 Brain
     Architecture Amendment — the new script-to-performance schemas),
     or "2.5" (v2.5 P0-006 animation-first additive migration).
     Dual-version enums ["2.3", "2.5"] / ["2.4", "2.5"] are allowed:
     a schema may accept records written against its earlier version
     as well as 2.5; no existing required field was removed or
     retyped, so every valid v2.3/v2.4 record remains valid.
  2. Every skill in skills/*/SKILL.md has YAML frontmatter with
     `name` and `description`; name matches the directory name.
  3. Registry files (registry/*.json) exist, parse, have unique IDs
     across all registries, and the skills registry matches the
     filesystem (15 skills, same ids/paths/names).
  4. No adapter is marked supported while its conformance is untested
     (CF-P0-ADAPTER-001).
  5. Private-overlay rules: no private media tracked by git under
     characters/ (only .gitkeep + README.md), and .gitignore covers
     characters/*, voice/media extensions and secrets.
  6. Secret scan: no obvious credential (api key / token / password
     assignment, private-key block) in tracked text files, excluding
     .git/ and components/.
  7. No absolute quality claim remains in normative skill/doc text:
     the strings "100% identical", "100% reference fidelity",
     "100% realistic" and "99.9% as the floor" must not appear in
     skills/ or docs/ (historical CHANGELOG entries are exempt —
     history is never rewritten).
  8. Canonical YAML records in architecture/ parse and are
     structurally sound: intent-modes.yaml (13 modes), the v2.4
     skill routing matrix (15 skills, required fields, unique
     precedence), the workflow graph (15 nodes, known endpoints,
     acyclic), the companion capability registry (2 companions,
     evidence_level from the closed set on every capability and
     interface, a run reference on every exercised_recorded_run,
     pinned commits matching setup.sh, no production_verified
     claim without a production record) and the agent compatibility
     matrix (only Muse verified). Needs PyYAML; if PyYAML is missing
     the check is reported SKIPPED with a clear message (CI installs
     PyYAML, so it runs there).

Usage: python3 scripts/validate-repo.py [--root DIR] [--json]
Exit 0 when every check passes, 1 otherwise. With --json, prints a
machine-readable result object to stdout.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(sys.argv[sys.argv.index("--root") + 1]
                       if "--root" in sys.argv else
                       os.path.join(os.path.dirname(__file__), ".."))
JSON_OUT = "--json" in sys.argv

ALLOWED_SCHEMA_KEYS = {
    "$schema", "$id", "title", "description", "type", "properties",
    "required", "additionalProperties", "enum", "pattern", "minLength",
    "minimum", "maximum", "exclusiveMinimum", "minItems", "items", "format",
}
ALLOWED_TYPES = {"object", "string", "integer", "number", "boolean", "array"}
FORBIDDEN_ABSOLUTE_CLAIMS = [
    "100% identical", "100% reference fidelity",
    "100% realistic", "99.9% as the floor",
]
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|secret[_-]?key)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]"),
    re.compile(r"(?i)password\s*[:=]\s*['\"][^'\"]{4,}['\"]"),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)sk-[A-Za-z0-9]{20,}"),
]


def check_schema(schema: dict, path: str, errors: list[str]) -> None:
    if not isinstance(schema, dict):
        errors.append(f"{path}: schema is not an object")
        return
    for key in schema:
        if key not in ALLOWED_SCHEMA_KEYS:
            errors.append(f"{path}: unsupported schema keyword '{key}' "
                          "(validator subset — extend the validator first)")
    t = schema.get("type")
    if t not in ALLOWED_TYPES:
        errors.append(f"{path}: bad/missing type '{t}'")
    if t == "object":
        props = schema.get("properties")
        if not isinstance(props, dict) or not props:
            errors.append(f"{path}: object schema needs non-empty properties")
        else:
            for name, sub in props.items():
                check_schema(sub, f"{path}.{name}", errors)
        for req in schema.get("required", []):
            if req not in (props or {}):
                errors.append(f"{path}: required field '{req}' not in properties")
        if schema.get("additionalProperties") is not False:
            errors.append(f"{path}: additionalProperties must be false")
    if t == "array" and "items" in schema:
        check_schema(schema["items"], f"{path}[]", errors)
    if "enum" in schema and not isinstance(schema["enum"], list):
        errors.append(f"{path}: enum must be a list")
    if "pattern" in schema:
        try:
            re.compile(schema["pattern"])
        except re.error as e:
            errors.append(f"{path}: bad pattern: {e}")
    for bound in ("minimum", "maximum", "exclusiveMinimum"):
        if bound in schema and (not isinstance(schema[bound], (int, float))
                                or isinstance(schema[bound], bool)):
            errors.append(f"{path}: {bound} must be a number")


def validate_dialogue_rewrite(plan: dict) -> list[str]:
    """Cross-field dialogue-rewrite rule (cannot live in the restricted
    JSON-Schema subset, so it is enforced semantically).

    A line's `dialogue.rewritten_text` may be present only when that
    line's `dialogue.rewrite_permitted` is explicitly true. The
    plan-level `dialogue_mode` (even SCRIPT_EDIT_REQUESTED) never
    permits a rewrite by itself — the per-line flag governs.
    Returns a list of violations; empty list means the plan complies.
    """
    errors = []
    if not isinstance(plan, dict):
        return ["performance plan is not an object"]
    for i, line in enumerate(plan.get("lines") or []):
        if not isinstance(line, dict):
            continue
        dialogue = line.get("dialogue")
        if not isinstance(dialogue, dict):
            continue
        if "rewritten_text" in dialogue and dialogue.get("rewrite_permitted") is not True:
            errors.append(
                f"lines[{i}] ({line.get('line_id', '?')}): rewritten_text present "
                "but rewrite_permitted is not true for this line "
                "(plan-level dialogue_mode alone never permits a rewrite)")
    return errors


def validate_non_verbal_lines(plan: dict) -> list[str]:
    """A performance-plan line must speak or perform non-verbally.

    A line with no spoken dialogue text (dialogue absent, or text
    missing/empty) must carry at least one `non_verbal_events` entry.
    Returns a list of violations; empty list means the plan complies.
    """
    errors = []
    if not isinstance(plan, dict):
        return ["performance plan is not an object"]
    for i, line in enumerate(plan.get("lines") or []):
        if not isinstance(line, dict):
            continue
        dialogue = line.get("dialogue")
        text = dialogue.get("text") if isinstance(dialogue, dict) else None
        events = line.get("non_verbal_events") or []
        if not text and not events:
            errors.append(
                f"lines[{i}] ({line.get('line_id', '?')}): no spoken dialogue "
                "text and no non_verbal_events — a line must speak or "
                "perform non-verbally")
    return errors


def validate_instance(schema: dict, value, path: str, errors: list[str]) -> None:
    """Minimal instance validation against the supported subset."""
    t = schema.get("type")
    type_ok = {
        "object": isinstance(value, dict),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "array": isinstance(value, list),
    }
    if t and not type_ok.get(t, True):
        errors.append(f"{path}: expected {t}, got {type(value).__name__}")
        return
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in enum {schema['enum']}")
        return
    if t == "object":
        for req in schema.get("required", []):
            if req not in value:
                errors.append(f"{path}: missing required field '{req}'")
        for name, sub in schema.get("properties", {}).items():
            if name in value:
                validate_instance(sub, value[name], f"{path}.{name}", errors)
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in schema.get("properties", {}):
                    errors.append(f"{path}: unexpected field '{key}'")
    if t == "string":
        if "enum" in schema and value not in schema["enum"]:
            errors.append(f"{path}: '{value}' not in enum {schema['enum']}")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: '{value}' does not match pattern {schema['pattern']}")
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: shorter than minLength {schema['minLength']}")
    if t in ("integer", "number") and "minimum" in schema and value < schema["minimum"]:
        errors.append(f"{path}: {value} < minimum {schema['minimum']}")
    if t in ("integer", "number") and "maximum" in schema and value > schema["maximum"]:
        errors.append(f"{path}: {value} > maximum {schema['maximum']}")
    if t in ("integer", "number") and "exclusiveMinimum" in schema \
            and value <= schema["exclusiveMinimum"]:
        errors.append(f"{path}: {value} <= exclusiveMinimum {schema['exclusiveMinimum']}")
    if t == "array":
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: fewer than minItems {schema['minItems']}")
        for i, item in enumerate(value):
            validate_instance(schema["items"], item, f"{path}[{i}]", errors)


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    errors: list[str] = []
    checks: dict[str, str] = {}

    # 1. Schemas ---------------------------------------------------------
    schema_dir = os.path.join(ROOT, "schemas")
    schema_files = sorted(f for f in os.listdir(schema_dir) if f.endswith(".json"))
    if not schema_files:
        errors.append("schemas/: no schema files found")
    for name in schema_files:
        path = os.path.join(schema_dir, name)
        try:
            schema = load_json(path)
        except Exception as e:
            errors.append(f"schemas/{name}: invalid JSON: {e}")
            continue
        check_schema(schema, f"schemas/{name}", errors)
        if schema.get("properties", {}).get("schema_version", {}).get("enum") not in (
                ["2.3"], ["2.4"], ["2.5"], ["2.3", "2.5"], ["2.4", "2.5"]):
            errors.append(f"schemas/{name}: schema_version must be '2.3', '2.4' or '2.5' "
                          "(dual-version ['2.3', '2.5'] / ['2.4', '2.5'] allowed)")
    checks["schemas"] = "PASS" if not errors else "FAIL"

    # 2. Skill frontmatter ------------------------------------------------
    skills_dir = os.path.join(ROOT, "skills")
    skill_names = sorted(d for d in os.listdir(skills_dir)
                         if os.path.isdir(os.path.join(skills_dir, d)))
    fm_errors_before = len(errors)
    for skill in skill_names:
        p = os.path.join(skills_dir, skill, "SKILL.md")
        if not os.path.exists(p):
            errors.append(f"skills/{skill}: missing SKILL.md")
            continue
        text = open(p, encoding="utf-8").read()
        m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        if not m:
            errors.append(f"skills/{skill}: missing YAML frontmatter")
            continue
        fm = m.group(1)
        name_m = re.search(r"^name:\s*(\S+)\s*$", fm, re.M)
        desc_m = re.search(r"^description:\s*\S+", fm, re.M)
        if not name_m or not desc_m:
            errors.append(f"skills/{skill}: frontmatter needs name + description")
        elif name_m.group(1) != skill:
            errors.append(f"skills/{skill}: frontmatter name '{name_m.group(1)}' "
                          f"does not match directory '{skill}'")
    checks["skill_frontmatter"] = "PASS" if len(errors) == fm_errors_before else "FAIL"

    # 3. Registries --------------------------------------------------------
    reg_dir = os.path.join(ROOT, "registry")
    seen_ids: dict[str, str] = {}
    reg_errors_before = len(errors)
    for fname in ("skills.json", "features.json", "workflows.json", "adapters.json"):
        p = os.path.join(reg_dir, fname)
        if not os.path.exists(p):
            errors.append(f"registry/{fname}: missing (run scripts/generate-registries.py)")
            continue
        try:
            data = load_json(p)
        except Exception as e:
            errors.append(f"registry/{fname}: invalid JSON: {e}")
            continue
        records = data.get("records") or data.get("skills") or data.get("features") \
            or data.get("workflows") or data.get("adapters") or []
        id_field = {"skills.json": "skill_id", "features.json": "feature_id",
                    "workflows.json": "workflow_id", "adapters.json": "adapter_id"}[fname]
        for rec in records:
            rid = rec.get(id_field)
            if not rid:
                errors.append(f"registry/{fname}: record without {id_field}: {rec}")
                continue
            if rid in seen_ids:
                errors.append(f"duplicate id '{rid}' in registry/{fname} "
                              f"(first seen in {seen_ids[rid]})")
            seen_ids[rid] = f"registry/{fname}"
        # Skills registry must match the filesystem.
        if fname == "skills.json":
            fs_ids = {f"skill-{s}" for s in skill_names}
            reg_ids = {r.get("skill_id") for r in records}
            if fs_ids != reg_ids:
                errors.append(f"registry/skills.json does not match skills/: "
                              f"filesystem={sorted(fs_ids)} registry={sorted(reg_ids)}")
    # Adapters: untested must never be marked supported.
    adapters_path = os.path.join(reg_dir, "adapters.json")
    if os.path.exists(adapters_path):
        try:
            for rec in load_json(adapters_path).get("adapters", []):
                if rec.get("status") in ("supported", "implemented") and \
                        rec.get("conformance", {}).get("status") in ("NOT_TESTED", "NOT RUN", None):
                    errors.append(f"adapter {rec.get('adapter_id')}: marked "
                                  f"{rec.get('status')} but conformance is untested")
        except Exception:
            pass
    checks["registries"] = "PASS" if len(errors) == reg_errors_before else "FAIL"

    # 4. Private overlay ---------------------------------------------------
    priv_errors_before = len(errors)
    try:
        tracked = subprocess.run(
            ["git", "-C", ROOT, "ls-files"], capture_output=True, text=True,
            check=True).stdout.splitlines()
    except Exception:
        tracked = []
    for path in tracked:
        if path.startswith("characters/") and path not in (
                "characters/.gitkeep", "characters/README.md"):
            errors.append(f"private data tracked in git: {path}")
        if re.search(r"\.(mp3|mp4|wav|webm|mov|png|jpg|jpeg)$", path) and \
                not path.startswith("docs/"):
            errors.append(f"media file tracked in git: {path}")
    gitignore = os.path.join(ROOT, ".gitignore")
    gi = open(gitignore, encoding="utf-8").read() if os.path.exists(gitignore) else ""
    for needle in ("characters/*", "*.mp3", "*.mp4", ".env"):
        if needle not in gi:
            errors.append(f".gitignore is missing '{needle}'")
    checks["private_overlay"] = "PASS" if len(errors) == priv_errors_before else "FAIL"

    # 5. Secret scan --------------------------------------------------------
    sec_errors_before = len(errors)
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in (".git", "components", ".agents")]
        for fn in filenames:
            if not fn.endswith((".md", ".json", ".yaml", ".yml", ".sh", ".py")):
                continue
            p = os.path.join(dirpath, fn)
            try:
                text = open(p, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            for pat in SECRET_PATTERNS:
                if pat.search(text):
                    errors.append(f"possible secret in {os.path.relpath(p, ROOT)}: {pat.pattern[:40]}...")
                    break
    checks["secret_scan"] = "PASS" if len(errors) == sec_errors_before else "FAIL"

    # 6. Absolute quality claims (normative text only) ----------------------
    abs_errors_before = len(errors)
    for base in ("skills", "docs"):
        for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, base)):
            dirnames[:] = [d for d in dirnames if d != "research"]
            for fn in filenames:
                if not fn.endswith(".md"):
                    continue
                p = os.path.join(dirpath, fn)
                text = open(p, encoding="utf-8", errors="ignore").read()
                for claim in FORBIDDEN_ABSOLUTE_CLAIMS:
                    if claim in text:
                        errors.append(f"{os.path.relpath(p, ROOT)}: absolute claim "
                                      f"'{claim}' must be replaced by a measurable, "
                                      "scoped target (see schemas + docs/19)")
    checks["absolute_claims"] = "PASS" if len(errors) == abs_errors_before else "FAIL"

    # 7. Canonical YAML records (v2.4) ------------------------------------
    yaml_errors_before = len(errors)
    try:
        import yaml as _yaml
    except ImportError:
        _yaml = None
    if _yaml is None:
        checks["yaml_records"] = "SKIPPED (PyYAML not installed — pip install pyyaml)"
        print("SKIPPED: yaml_records (PyYAML not installed — pip install pyyaml)")
    else:
        def load_yaml(rel):
            p = os.path.join(ROOT, rel)
            if not os.path.exists(p):
                errors.append(f"{rel}: missing")
                return None
            try:
                with open(p, encoding="utf-8") as f:
                    return _yaml.safe_load(f)
            except Exception as e:
                errors.append(f"{rel}: invalid YAML: {e}")
                return None

        expected_modes = {"UPLOAD_ONLY", "TEMPORARY_ASSET_USE",
                          "PROJECT_CONSISTENCY", "REGISTER_CHARACTER",
                          "REGISTER_VOICE_PROFILE", "REGISTER_SOUND_ASSET",
                          "GENERATE_FROM_SCRIPT", "EDIT_EXISTING_MEDIA",
                          "REFERENCE_REVIEW", "REFERENCE_LEARN_AND_UPDATE",
                          "VIDEO_QC", "REMAKE_OR_TRANSFORM",
                          "REPORT_UPDATE_ONLY"}
        skill_slugs = {f"skill-{s}" for s in skill_names}
        slug_names = set(skill_names)

        # intent-modes.yaml: 13 modes, matching asset_policy MODES.
        modes_doc = load_yaml("architecture/intent-modes.yaml")
        if modes_doc is not None:
            if str(modes_doc.get("version")) != "2.3":
                errors.append("architecture/intent-modes.yaml: version must be '2.3'")
            if set((modes_doc.get("modes") or {}).keys()) != expected_modes:
                errors.append("architecture/intent-modes.yaml: modes must be exactly the 13 asset modes")

        # SKILL_ROUTING_MATRIX.yaml: 15 skills, required fields, unique precedence.
        routing = load_yaml("architecture/SKILL_ROUTING_MATRIX.yaml")
        if routing is not None:
            if str(routing.get("version")) != "2.4":
                errors.append("architecture/SKILL_ROUTING_MATRIX.yaml: version must be '2.4'")
            entries = routing.get("skills") or []
            if {e.get("skill_id") for e in entries} != skill_slugs:
                errors.append("architecture/SKILL_ROUTING_MATRIX.yaml: skill_id set must match the 15 registry skills")
            precs = []
            for e in entries:
                for field in ("skill_id", "skill", "activation_trigger",
                              "non_trigger", "required_inputs",
                              "expected_outputs", "dependencies", "precedence",
                              "conflicts", "applicable_modes", "quality_gate",
                              "approval_conditions"):
                    if field not in e:
                        errors.append(f"routing entry {e.get('skill_id')}: missing field '{field}'")
                if e.get("skill") not in slug_names:
                    errors.append(f"routing entry {e.get('skill_id')}: unknown skill '{e.get('skill')}'")
                if isinstance(e.get("precedence"), int):
                    precs.append(e["precedence"])
                if not isinstance(e.get("activation_trigger"), str) or not (e.get("activation_trigger") or "").strip():
                    errors.append(f"routing entry {e.get('skill_id')}: activation_trigger must be non-empty")
                for dep in e.get("dependencies") or []:
                    if dep not in slug_names:
                        errors.append(f"routing entry {e.get('skill_id')}: unknown dependency '{dep}'")
                for conf in e.get("conflicts") or []:
                    if conf not in slug_names:
                        errors.append(f"routing entry {e.get('skill_id')}: unknown conflict '{conf}'")
                for mode in e.get("applicable_modes") or []:
                    if mode not in expected_modes:
                        errors.append(f"routing entry {e.get('skill_id')}: unknown mode '{mode}'")
            if sorted(precs) != list(range(1, len(entries) + 1)):
                errors.append("architecture/SKILL_ROUTING_MATRIX.yaml: precedence values must be unique 1..15")

        # WORKFLOW_GRAPH.yaml: 15 nodes, known endpoints, acyclic.
        graph = load_yaml("architecture/WORKFLOW_GRAPH.yaml")
        if graph is not None:
            if str(graph.get("version")) != "2.4":
                errors.append("architecture/WORKFLOW_GRAPH.yaml: version must be '2.4'")
            nodes = {n.get("id") for n in (graph.get("nodes") or [])}
            if nodes != slug_names:
                errors.append("architecture/WORKFLOW_GRAPH.yaml: node ids must be exactly the 15 skill slugs")
            children: dict[str, set[str]] = {n: set() for n in nodes}
            for edge in graph.get("edges") or []:
                src, dst = edge.get("from"), edge.get("to")
                if src not in nodes or dst not in nodes:
                    errors.append(f"workflow graph edge {src} -> {dst}: unknown endpoint")
                elif src in children:
                    children[src].add(dst)
            # Kahn's algorithm: a cycle leaves nodes unvisited.
            indegree = {n: 0 for n in nodes}
            for src in children:
                for dst in children[src]:
                    indegree[dst] += 1
            queue = [n for n, d in indegree.items() if d == 0]
            visited = 0
            while queue:
                n = queue.pop()
                visited += 1
                for dst in children[n]:
                    indegree[dst] -= 1
                    if indegree[dst] == 0:
                        queue.append(dst)
            if visited != len(nodes):
                errors.append("architecture/WORKFLOW_GRAPH.yaml: graph has a cycle")

        # COMPANION_CAPABILITY_REGISTRY.yaml: 2 companions, closed
        # evidence_level on every capability and interface (P0-002 §6:
        # evidence_level REPLACED the old `status` field).
        EVIDENCE_LEVELS = ("upstream_inspected_pinned_commit",
                           "present_locally", "exercised_recorded_run",
                           "production_verified")
        EXPECTED_PINS = {
            "VoiceStudio": "2f2f5a9b0e982c6147efc6baaeae62936f29b79b",
            "OpenMontage": "fecb9a1e3cc23ef84de30b272059457a427f16f8",
        }
        companions = load_yaml("architecture/COMPANION_CAPABILITY_REGISTRY.yaml")
        if companions is not None:
            if str(companions.get("version")) != "2.4":
                errors.append("architecture/COMPANION_CAPABILITY_REGISTRY.yaml: version must be '2.4'")
            comps = companions.get("companions") or []
            if {c.get("name") for c in comps} != {"VoiceStudio", "OpenMontage"}:
                errors.append("architecture/COMPANION_CAPABILITY_REGISTRY.yaml: must list exactly VoiceStudio + OpenMontage")
            for c in comps:
                if c.get("pinned_commit") != EXPECTED_PINS.get(c.get("name")):
                    errors.append(f"companion {c.get('name')}: pinned_commit "
                                  f"{c.get('pinned_commit')!r} does not match "
                                  f"the setup.sh pin {EXPECTED_PINS.get(c.get('name'))!r}")
                for group in ("capabilities", "interfaces"):
                    for item in c.get(group) or []:
                        label = item.get("capability") or item.get("name")
                        level = item.get("evidence_level")
                        if level not in EVIDENCE_LEVELS:
                            errors.append(f"companion {c.get('name')}: {group[:-1]} '{label}' has unknown evidence_level {level!r} "
                                          f"(must be one of {list(EVIDENCE_LEVELS)})")
                        if "status" in item:
                            errors.append(f"companion {c.get('name')}: {group[:-1]} '{label}' still carries the retired 'status' field "
                                          "(P0-002 §6 replaced it with evidence_level)")
                        if not item.get("evidence"):
                            errors.append(f"companion {c.get('name')}: {group[:-1]} '{label}' has no evidence pointer")
                        if level == "exercised_recorded_run":
                            ref = item.get("run_reference")
                            if not isinstance(ref, str) or not ref.strip():
                                errors.append(f"companion {c.get('name')}: {group[:-1]} '{label}' is exercised_recorded_run "
                                              "but has no run_reference (date + what was run + where it is recorded)")
                        if level == "production_verified":
                            rec = item.get("production_record")
                            if not isinstance(rec, str) or not rec.strip():
                                errors.append(f"companion {c.get('name')}: {group[:-1]} '{label}' claims production_verified "
                                              "but has no production_record")

        # AGENT_COMPATIBILITY_MATRIX.yaml: only Muse verified.
        agents_doc = load_yaml("architecture/AGENT_COMPATIBILITY_MATRIX.yaml")
        if agents_doc is not None:
            if str(agents_doc.get("version")) != "2.4":
                errors.append("architecture/AGENT_COMPATIBILITY_MATRIX.yaml: version must be '2.4'")
            for a in agents_doc.get("agents") or []:
                if a.get("verified") and a.get("name") != "Muse":
                    errors.append(f"agent matrix: {a.get('name')} is marked verified — only Muse is verified in this account")
                if a.get("verification_status") not in ("VERIFIED", "NOT_TESTED"):
                    errors.append(f"agent matrix: {a.get('name')} has an unknown verification_status")
            non_hosts = {n.get("name") for n in (agents_doc.get("non_hosts") or [])}
            if not {"OpenRouter", "Google Colab"} <= non_hosts:
                errors.append("agent matrix: non_hosts must include OpenRouter and Google Colab")
            for n in agents_doc.get("non_hosts") or []:
                if n.get("is_agent_host") is not False:
                    errors.append(f"agent matrix: non-host {n.get('name')} must have is_agent_host: false")
        checks["yaml_records"] = "PASS" if len(errors) == yaml_errors_before else "FAIL"

    result = {"checks": checks, "errors": errors,
              "result": "PASS" if not errors else "FAIL"}
    if JSON_OUT:
        print(json.dumps(result, indent=2))
    else:
        for name, status in checks.items():
            print(f"{status}: {name}")
        for e in errors:
            print(f"  ERROR: {e}")
        print("VALIDATE-REPO: " + result["result"])
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
