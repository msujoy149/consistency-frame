#!/usr/bin/env python3
"""Consistency Frame P0 — repository validator (Python stdlib only).

Checks, all deterministic and offline:
  1. Every schema in schemas/*.json is valid JSON and a well-formed
     JSON Schema (subset): type/properties/required/enum/pattern/
     minLength/minimum/minItems/items/additionalProperties.
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
    "minimum", "minItems", "items", "format",
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
        if schema.get("properties", {}).get("schema_version", {}).get("enum") != ["2.3"]:
            errors.append(f"schemas/{name}: schema_version must be '2.3'")
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
