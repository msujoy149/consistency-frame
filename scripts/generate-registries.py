#!/usr/bin/env python3
"""Consistency Frame P0 — generate canonical registries from the live repo.

Reads skills/*/SKILL.md (frontmatter + headings) and writes:
  registry/skills.json, registry/features.json,
  registry/workflows.json, registry/adapters.json

Counts are DERIVED from the files, never typed by hand. The historical
claim of "109 distinct systems / 120 numbered entries" (README, docs/01)
is preserved verbatim in features.json metadata as a historical claim
with status "historical-claim-not-machine-derived" — it is NOT
recomputed here, and this registry does not pretend to equal it.
Reconciling the two counts is deferred P1 work (see the living report).

Usage:
  python3 scripts/generate-registries.py [--check]
  --check exits 1 if the committed registry files differ from what
  this script would generate (used by CI).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
REG = os.path.join(ROOT, "registry")
CHECK = "--check" in sys.argv

FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.S)
HEADING2 = re.compile(r"^##\s+(.+?)\s*$", re.M)


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-+", "-", s) or "section"


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_skill(skill: str) -> dict:
    path = os.path.join(ROOT, "skills", skill, "SKILL.md")
    text = open(path, encoding="utf-8").read()
    m = FRONTMATTER.match(text)
    fm = m.group(1) if m else ""
    name = re.search(r"^name:\s*(\S+)\s*$", fm, re.M)
    desc = re.search(r"^description:\s*\"?(.*?)\"?\s*$", fm, re.M)
    headings = HEADING2.findall(text)
    return {
        "skill_id": f"skill-{skill}",
        "name": name.group(1) if name else skill,
        "path": f"skills/{skill}/SKILL.md",
        "version": "2.0",
        "description": (desc.group(1) if desc else "").strip(),
        "purpose": (desc.group(1) if desc else "").strip(),
        "scope": "global",
        "status": "DOCUMENTED",
        "maturity": "DOCUMENTED",
        "evidence": f"skills/{skill}/SKILL.md",
        "sha256": sha256_file(path),
        "section_count": len(headings),
        "tests": ["P0-FRONTMATTER"],
    }


def build_skills() -> dict:
    skills_dir = os.path.join(ROOT, "skills")
    names = sorted(d for d in os.listdir(skills_dir)
                   if os.path.isdir(os.path.join(skills_dir, d)))
    records = [parse_skill(s) for s in names]
    return {"registry": "skills", "version": "2.3", "count": len(records),
            "records": records}


def build_features(skills_data: dict) -> dict:
    records = []
    for skill in skills_data["records"]:
        text = open(os.path.join(ROOT, skill["path"]), encoding="utf-8").read()
        for heading in HEADING2.findall(text):
            fid = f"feat-{skill['name']}-{slug(heading)}"
            records.append({
                "feature_id": fid,
                "name": heading.strip(),
                "owner_skill": skill["skill_id"],
                "owner_path": skill["path"],
                "scope": "global",
                "status": "DOCUMENTED",
                "maturity": "DOCUMENTED",
                "evidence": f"{skill['path']} (section: {heading.strip()})",
                "dependencies": [],
                "conflicts": [],
                "tests": [],
            })
    # De-duplicate by feature_id (two skills may share a heading).
    seen, unique = set(), []
    for r in records:
        if r["feature_id"] in seen:
            continue
        seen.add(r["feature_id"])
        unique.append(r)
    return {
        "registry": "features", "version": "2.3", "count": len(unique),
        "records": unique,
        "legacy_counts": {
            "distinct_systems_claimed": 109,
            "numbered_entries_claimed": 120,
            "source": "README.md and docs/01-production-systems.md (pre-P0, manually maintained)",
            "status": "historical-claim-not-machine-derived",
            "note": ("This registry counts one feature per '##' section of each "
                     "canonical skill file. It is a different counting unit "
                     "from the historical 109/120 claim and must not be "
                     "presented as equal to it. Reconciliation is deferred P1 work."),
        },
    }


WORKFLOWS = [
    ("UPLOAD_ONLY", "A file is uploaded without a task command.",
     ["uploaded file"], ["intake receipt"], "no_mutation",
     "none — no action is taken", "none"),
    ("TEMPORARY_ASSET_USE", "Use supplied media for the current job only.",
     ["uploaded media", "task"], ["job output"], "temporary_only",
     "none — no permanent record", "discard temporary copies per retention"),
    ("PROJECT_CONSISTENCY", "Maintain consistency across a named project/series.",
     ["project_id", "task"], ["job output", "episode state"], "project_scoped",
     "project must exist; missing records asked, not invented", "reload project records"),
    ("REGISTER_CHARACTER", "Permanently register a character identity.",
     ["name", "unique id", "approved reference(s)", "explicit authorisation"],
     ["character record"], "permanent_registration",
     "explicit authorisation + name + id + reference (all required)", "reject, do not register"),
    ("REGISTER_VOICE_PROFILE", "Permanently register a voice profile.",
     ["character_id", "reference audio", "explicit authorisation", "consent"],
     ["voice_profile record"], "permanent_registration",
     "explicit authorisation + rights/consent", "reject, do not register"),
    ("REGISTER_SOUND_ASSET", "Permanently register a recurring sound asset.",
     ["sound kind", "source", "licence", "explicit instruction"],
     ["sound_asset record"], "permanent_registration",
     "explicit instruction + licence/provenance", "reject, do not register"),
    ("GENERATE_FROM_SCRIPT", "Convert a script/brief into a production plan.",
     ["script", "project_id (if recurring)"], ["shot/performance/audio/timeline plan"],
     "plan_only_in_p0", "dialogue VERBATIM by default", "re-plan from script"),
    ("EDIT_EXISTING_MEDIA", "Edit supplied footage/assets.",
     ["media", "edit brief"], ["edited output", "timeline manifest"],
     "verified_adapters_only", "adapter must be conformance-tested", "report unsupported operation"),
    ("REFERENCE_REVIEW", "Analyse a reference and report findings.",
     ["reference media"], ["timecoded reference report"], "no_mutation",
     "none — report only", "none"),
    ("REFERENCE_LEARN_AND_UPDATE", "Analyse a reference and propose reusable learnings.",
     ["reference media", "explicit user instruction"], ["learning candidate patch"],
     "reviewable_patch_only", "explicit instruction required; patch reviewed before merge",
     "candidate stays CANDIDATE until validated"),
    ("VIDEO_QC", "Inspect an existing output and report defects.",
     ["output media", "brief"], ["QC report"], "no_regeneration",
     "regenerate only if repair is authorised", "report defects"),
    ("REMAKE_OR_TRANSFORM", "Transform/remake a reference as expressly requested.",
     ["reference media", "explicit request", "rights check"], ["new transformed work"],
     "rights_gated", "rights/provenance check required", "stop on rights failure"),
    ("REPORT_UPDATE_ONLY", "Regenerate reports from canonical records.",
     ["registry/schema records"], ["regenerated report"], "reports_only",
     "must not change production rules", "regenerate from records"),
]


def build_workflows() -> dict:
    records = []
    for mode, trigger, inputs, outputs, mutation, gate, recovery in WORKFLOWS:
        records.append({
            "workflow_id": f"wf-{slug(mode)}",
            "mode": mode,
            "trigger": trigger,
            "required_inputs": inputs,
            "outputs": outputs,
            "mutation_policy": mutation,
            "approval_gate": gate,
            "recovery": recovery,
            "skills_invoked": [],
            "tests": ["CF-P0-ASSET-001", "CF-P0-ASSET-002"] if mode.startswith("REGISTER") or mode in ("UPLOAD_ONLY", "TEMPORARY_ASSET_USE") else [],
            "status": "SCHEMA_DEFINED",
        })
    return {"registry": "workflows", "version": "2.3", "count": len(records),
            "records": records}


ADAPTERS = [
    # adapter_id, name, kind, integration, native_skill_install, conformance, limitations
    ("adapter-muse", "Muse (Meta)", "host",
     "PACKAGED", "UNSUPPORTED",
     "NOT_TESTED",
     "No documented native custom-SKILL.md install flow (Meta Help Centre). "
     "Use the versioned knowledge pack / uploaded workspace files instead. "
     "Knowledge-pack availability in a Muse workspace has not been conformance-tested here."),
    ("adapter-claude-code", "Claude Code", "host",
     "NATIVE", "NOT_TESTED",
     "NOT_TESTED",
     "Plugin marketplace files exist (.claude-plugin/marketplace.json). "
     "Loaded skill version, precedence and permissions have not been conformance-tested here."),
    ("adapter-codex", "Codex", "host",
     "NATIVE", "NOT_TESTED",
     "NOT_TESTED",
     "Plugin manifest exists (plugin.json, .codex-plugin/plugin.json). "
     "Loading behaviour has not been conformance-tested here."),
    ("adapter-gemini-cli", "Gemini CLI", "host",
     "NATIVE", "NOT_TESTED",
     "NOT_TESTED",
     "Extension manifest exists (gemini-extension.json). "
     "Workspace/user/extension precedence has not been conformance-tested here."),
    ("adapter-antigravity", "Antigravity", "host",
     "PACKAGED", "NOT_TESTED",
     "NOT_TESTED",
     "Skills in .agents/skills/, rules in AGENTS.md / GEMINI.md. "
     "Actual discovery in the installed Antigravity version has not been tested here."),
    ("adapter-chatgpt", "ChatGPT", "host",
     "PACKAGED", "NOT_TESTED",
     "NOT_TESTED",
     "Skills uploaded via the Skills tab (per docs/06). "
     "Upload/loading behaviour has not been conformance-tested here."),
    ("adapter-opencode", "OpenCode", "host",
     "NATIVE", "NOT_TESTED",
     "NOT_TESTED",
     "Documented .opencode/skills path exists in OpenCode docs; no manifest "
     "or conformance test exists in this repo. Planned, not tested."),
    ("adapter-voicestudio", "VoiceStudio (bundled component)", "provider",
     "HOST_RUNTIME", "NOT_TESTED",
     "NOT_TESTED",
     "Local voice engine (AGPL-3.0). OmniVoice weights are CC-BY-NC "
     "(noncommercial) and are never downloaded by setup.sh. Voice generation "
     "was exercised manually in Nov 2026, but no automated conformance test "
     "exists in P0."),
    ("adapter-openmontage", "OpenMontage (bundled component)", "provider",
     "HOST_RUNTIME", "NOT_TESTED",
     "NOT_TESTED",
     "Long-form video assembly component (AGPL-3.0). No automated "
     "conformance test exists in P0."),
    ("adapter-ffmpeg", "FFmpeg / ffprobe", "tool",
     "HOST_RUNTIME", "NOT_TESTED",
     "NOT_TESTED",
     "Deterministic media probing/transcoding. Binary presence on a machine "
     "is not a conformance test; no P0 test invokes it."),
    ("adapter-opentimelineio", "OpenTimelineIO", "tool",
     "LIMITED", "NOT_TESTED",
     "NOT_TESTED",
     "Candidate for editorial interchange only: clips, timing, tracks, "
     "transitions, markers, external media references. NOT a renderer or "
     "media container. Not installed or tested in P0 — planned."),
    ("adapter-premiere-uxp", "Adobe Premiere Pro (UXP)", "editor",
     "LIMITED", "NOT_TESTED",
     "NOT_TESTED",
     "Application-specific editing integration requires a version-tested "
     "API. No adapter code or test exists in P0 — planned."),
]


def build_adapters() -> dict:
    records = []
    for aid, name, kind, integration, native_install, conformance, limits in ADAPTERS:
        records.append({
            "adapter_id": aid,
            "name": name,
            "kind": kind,
            "integration": integration,
            "native_skill_install": native_install,
            "capabilities": [],
            "limitations": [limits],
            "authentication": "none (local files) — provider keys, where needed, are never set by setup.sh",
            "privacy": "private assets stay in the private overlay; never committed",
            "licence_notes": "component licences intact (see LICENSE and component licences)",
            "conformance": {"status": conformance, "test_id": "CF-P0-ADAPTER-001",
                            "last_verified": "2026-11-22", "evidence": "none in P0"},
            "status": "untested",
        })
    return {"registry": "adapters", "version": "2.3", "count": len(records),
            "records": records,
            "note": ("No adapter is marked 'supported' in P0: a capability is "
                     "supported only after a real conformance test passes. "
                     "All adapters here are 'untested' (conformance NOT_TESTED) "
                     "or 'planned'.")}


def write(name: str, data: dict) -> bool:
    path = os.path.join(REG, name)
    new = json.dumps(data, indent=2, sort_keys=True) + "\n"
    if os.path.exists(path):
        old = open(path, encoding="utf-8").read()
        if old == new:
            return False
    os.makedirs(REG, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new)
    return True


def main() -> int:
    skills = build_skills()
    features = build_features(skills)
    workflows = build_workflows()
    adapters = build_adapters()
    changed = []
    for name, data in (("skills.json", skills), ("features.json", features),
                       ("workflows.json", workflows), ("adapters.json", adapters)):
        if write(name, data):
            changed.append(name)
    if CHECK:
        if changed:
            print(f"CHECK FAILED: registries out of date: {changed} "
                  "(run scripts/generate-registries.py)")
            return 1
        print("CHECK OK: registries match the live repo")
        return 0
    print(f"skills={skills['count']} features={features['count']} "
          f"workflows={workflows['count']} adapters={adapters['count']} "
          f"changed={changed or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
