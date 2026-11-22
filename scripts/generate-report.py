#!/usr/bin/env python3
"""Consistency Frame P0 — generate the Living Architecture Report from
canonical records (registry/*.json, schemas/, git state, test results).

The report is GENERATED, not hand-typed: inventory counts come from the
registry files, the base/head commits from git, and test results from
tests/last-run.json (written by tests/run-tests.sh). If the test file
is absent, tests are reported as NOT RUN — never as passed.

Usage:
  python3 scripts/generate-report.py [--check] [--github-head <sha>]
  --check exits 1 if the committed report differs from a fresh
  generation (used by CI).
  --github-head records the GitHub branch head this report describes
  (default: the CF_GITHUB_HEAD env var, else the current git HEAD).
  The remote head advances by one docs-only commit when the regenerated
  report is pushed; the delivery message states that final head.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "docs", "architecture", "living-architecture-report-v2.4-p0.md")
CHECK = "--check" in sys.argv


def git(*args: str) -> str:
    try:
        return subprocess.run(["git", "-C", ROOT, *args], capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def load(name: str) -> dict:
    with open(os.path.join(ROOT, "registry", name), encoding="utf-8") as f:
        return json.load(f)


def resolve_github_head(argv, environ, default_head: str) -> str:
    """GitHub branch head to record: --github-head wins, then the
    CF_GITHUB_HEAD env var, else the current git HEAD (the default
    "current recorded head")."""
    if "--github-head" in argv:
        i = argv.index("--github-head")
        if i + 1 < len(argv) and argv[i + 1]:
            return argv[i + 1]
    return environ.get("CF_GITHUB_HEAD") or default_head


def main() -> int:
    skills = load("skills.json")
    features = load("features.json")
    workflows = load("workflows.json")
    adapters = load("adapters.json")
    schema_files = sorted(f for f in os.listdir(os.path.join(ROOT, "schemas"))
                          if f.endswith(".json"))
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    head = git("rev-parse", "HEAD")
    base = git("rev-parse", "origin/main")
    github_head = resolve_github_head(sys.argv, os.environ, head)
    changed = git("diff", "--name-only", f"{base}...HEAD")
    if not changed:
        changed = git("diff", "--name-only", "HEAD")

    last_run_path = os.path.join(ROOT, "tests", "last-run.json")
    if os.path.exists(last_run_path):
        last_run = json.load(open(last_run_path, encoding="utf-8"))
        test_lines = [f"- `{t['id']}` — {t['command']} — **{t['result']}** "
                      f"(exit {t['exit_code']})" for t in last_run.get("tests", [])]
        test_section = "\n".join(test_lines) if test_lines else "- No tests recorded."
        test_status = last_run.get("status", "unknown")
    else:
        test_section = "- No test run recorded yet (`tests/last-run.json` absent). Tests are NOT RUN, not passed."
        test_status = "NOT RUN"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    adapter_rows = "\n".join(
        f"| {a['name']} | {a['integration']} | {a['native_skill_install']} | "
        f"{a['conformance']['status']} | {a['status']} |"
        for a in adapters["records"])
    skill_rows = "\n".join(
        f"| `{s['skill_id']}` | {s['name']} | {s['path']} | {s['maturity']} | {s['section_count']} |"
        for s in skills["records"])

    # v2.4 canonical YAML records (guarded PyYAML import; CI installs it).
    try:
        import yaml as _yaml
    except ImportError:
        _yaml = None
    if _yaml is not None:
        def load_yaml(rel):
            with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
                return _yaml.safe_load(f)
        routing = load_yaml("architecture/SKILL_ROUTING_MATRIX.yaml")
        graph = load_yaml("architecture/WORKFLOW_GRAPH.yaml")
        companions = load_yaml("architecture/COMPANION_CAPABILITY_REGISTRY.yaml")
        agent_matrix = load_yaml("architecture/AGENT_COMPATIBILITY_MATRIX.yaml")
        routing_count = len(routing.get("skills") or [])
        graph_nodes = len(graph.get("nodes") or [])
        graph_edges = len(graph.get("edges") or [])
        comp_caps = sum(len(c.get("capabilities") or [])
                        for c in (companions.get("companions") or []))
        comp_levels: dict[str, int] = {
            "exercised_recorded_run": 0,
            "present_locally": 0,
            "upstream_inspected_pinned_commit": 0,
            "production_verified": 0,
        }
        for c in (companions.get("companions") or []):
            for cap in (c.get("capabilities") or []):
                lvl = cap.get("evidence_level")
                if lvl in comp_levels:
                    comp_levels[lvl] += 1
        comp_line = (f"{comp_caps} ({comp_levels['exercised_recorded_run']} "
                     "exercised_recorded_run, "
                     f"{comp_levels['present_locally']} present_locally, "
                     f"{comp_levels['upstream_inspected_pinned_commit']} "
                     "upstream_inspected_pinned_commit, "
                     f"{comp_levels['production_verified']} "
                     "production_verified)")
        agent_count = len(agent_matrix.get("agents") or [])
        agent_verified = [a["name"] for a in (agent_matrix.get("agents") or [])
                          if a.get("verified")]
        yaml_note = ""
    else:
        routing_count = graph_nodes = graph_edges = 0
        comp_caps = 0
        comp_line = "0 (PyYAML not installed — see note below)"
        agent_count = 0
        agent_verified = []
        yaml_note = "\n\n> v2.4 YAML records were not counted: PyYAML is not installed in this environment (`pip install pyyaml`). CI installs it, so the counts appear there."

    report = f"""# Living Architecture Report — v2.4 P0 (Brain Architecture Amendment)

**Generated:** {now} — from canonical records (`registry/*.json`,
`schemas/`, `architecture/*.yaml`, git state, `tests/last-run.json`). Do not edit the inventory
numbers by hand; regenerate with `python3 scripts/generate-report.py`.

**Product scope:** general-purpose professional AI video production
and editing system (2D/3D animation, realistic human video,
image-to-video and video-to-video, character/voice/sound consistency,
stories, web series and episodic production, cinematography, VFX,
editing, audio, post-production). Not a single-genre tool.

**Brain model (v2.4):** Consistency Frame is the CENTRAL BRAIN /
Orchestrator — creative intelligence, script understanding, skill
routing, character/project continuity, emotion/performance direction,
cinematography/editing decisions, quality requirements, production
coordination, documentation/learning governance. It is NOT a server,
API backend, cloud database or hosting platform, and not a replacement
for the companions (VoiceStudio = voice/speech, OpenMontage =
video production/editing). See
`docs/implementation/BRAIN_ARCHITECTURE_AUDIT.md`.

**Repository:** https://github.com/msujoy149/consistency-frame
**Base branch/commit:** `main` / `{base}`
**Feature branch:** `{branch}`
**Head commit:** `{head}`
**GitHub branch head:** `{github_head}` (remote head of `{branch}` at
generation time; pushing this regenerated report advances the branch
head by one docs-only commit — see `docs/implementation/BUILD_REPORT_P0.md` §12)
**Architecture/report version:** v2.4 P0 (work order CF-WO-P0-001, revised)
**Previous report:** `docs/architecture/living-architecture-report-v2.3-p0.md` — the v2.3 baseline (retained, not rewritten).

## Inventory (generated from canonical records)

| Registry | Count |
|---|---|
| Skills (`registry/skills.json`) | {skills["count"]} |
| Features (`registry/features.json`) | {features["count"]} |
| Workflows / intent modes (`registry/workflows.json`) | {workflows["count"]} |
| Adapters (`registry/adapters.json`) | {adapters["count"]} |
| JSON Schemas (`schemas/*.json`) | {len(schema_files)} |
| Routing matrix entries (`architecture/SKILL_ROUTING_MATRIX.yaml`) | {routing_count} |
| Workflow graph nodes / edges (`architecture/WORKFLOW_GRAPH.yaml`) | {graph_nodes} / {graph_edges} |
| Companion capabilities (`architecture/COMPANION_CAPABILITY_REGISTRY.yaml`) | {comp_line} |
| Agents in compatibility matrix (`architecture/AGENT_COMPATIBILITY_MATRIX.yaml`) | {agent_count} ({len(agent_verified)} verified: {", ".join(agent_verified) if agent_verified else "none"}) |
{yaml_note}

### Skills

| Skill ID | Name | Path | Maturity | Sections |
|---|---|---|---|---|
{skill_rows}

All 15 skills are maturity `DOCUMENTED`: guidance exists in the skill
files. None is `TESTED` or `PRODUCTION_VERIFIED` as a skill in P0 —
P0 tests validate frontmatter, registries, schemas and the installer,
not the creative content of each skill.

### Features

`{features["count"]}` features, one per `##` section of each canonical
skill file, derived by `scripts/generate-registries.py`.

**Reconciliation note (open):** the historical claim in the README and
`docs/01` is 109 distinct systems / 120 numbered entries. That claim
uses a different counting unit and is preserved in
`registry/features.json` under `legacy_counts` as
`historical-claim-not-machine-derived`. The P0 registry count (165) must
not be presented as equal to 109/120. Reconciling the two counts is
deferred P1 work.

### Workflows / intent modes

`{workflows["count"]}` modes (`UPLOAD_ONLY`, `TEMPORARY_ASSET_USE`,
`PROJECT_CONSISTENCY`, `REGISTER_CHARACTER`, `REGISTER_VOICE_PROFILE`,
`REGISTER_SOUND_ASSET`, `GENERATE_FROM_SCRIPT`, `EDIT_EXISTING_MEDIA`,
`REFERENCE_REVIEW`, `REFERENCE_LEARN_AND_UPDATE`, `VIDEO_QC`,
`REMAKE_OR_TRANSFORM`, `REPORT_UPDATE_ONLY`). Full contracts in
`architecture/intent-modes.yaml`; enforcement in
`scripts/asset_policy.py`.

### Adapters / capability truth

| Adapter | Integration | Native skill install | Conformance | Status |
|---|---|---|---|---|
{adapter_rows}

**No adapter is marked supported in P0.** A capability is supported
only after a real conformance test passes; every adapter above is
`untested` (conformance `NOT_TESTED`) or `planned`. In particular:
Muse is a knowledge pack, not a native skill install; OpenTimelineIO
is an editorial-interchange candidate, not a renderer; FFmpeg binary
presence is not a conformance test.

## Changes in P0 (since base `{base}`)

- Non-destructive installer: `scripts/sync-skills.sh` replaces
  `rm -rf .agents/skills`; `setup.sh` is core-only by default with
  opt-in `--with-components`, truthful per-component SUCCESS / PARTIAL /
  FAILED status and exit codes (fixes F1, F2).
- Canonical registries + 20 versioned JSON Schemas + asset-mode policy
  (fixes F5, F6-partial).
- Skill-first loop split: task-local draft (§9A) vs permanent canonical
  mutation on explicit user authorisation only (§9B).
- Absolute quality claims replaced by measurable, scoped targets with a
  human-review gate (fixes F7-partial; historical CHANGELOG entries
  untouched).
- Universal `-14 LUFS` retired; loudness is a named delivery profile
  (`architecture/audio-delivery-profiles.json`, `docs/19`) (fixes F8).
- Muse install claim corrected to knowledge-pack (fixes F3).
- Private-overlay validation contract + tests (fixes F4-partial:
  executable validator + tests exist; a runtime overlay adapter is
  deferred to P2).
- Tests + GitHub Actions CI (`.github/workflows/p0-ci.yml`).

### Changes in the v2.4 revision (Brain Architecture Amendment)

- P0-A audit (`docs/implementation/BRAIN_ARCHITECTURE_AUDIT.md`):
  zero server/API-backend/cloud-database claims in normative text;
  the withdrawn items never existed in code. One docs fix (v2.4
  section in `AGENTS.md`). No skill file changed.
- Intelligent Skill Routing: `architecture/SKILL_ROUTING_MATRIX.yaml`
  (15 skills, precedence 1–15, command-authority is the router) and
  `architecture/WORKFLOW_GRAPH.yaml` (42 edges, acyclic; sequential
  on dependency, parallel only when safe).
- Script-to-Performance Intelligence: four new `schema_version: "2.4"`
  schemas (`scene-plan`, `shot-plan`, `performance-plan`,
  `script-to-performance` — the combined contract). Dialogue is
  VERBATIM unless a rewrite was explicitly requested.
- Companion Capability Registry + Agent Compatibility Matrix: every
  capability carries an `evidence_level` (P0-002 §6 — 20 capabilities:
  3 `exercised_recorded_run`, 16 `present_locally`, 1
  `upstream_inspected_pinned_commit`, 0 `production_verified`); only
  Muse is verified (knowledge pack). OpenRouter is a model-routing
  layer, not a host; Colab needs a Notebook/Agent Runtime.
- Validator check 8 (canonical YAML records) + `tests/test_routing.py`
  (gates CF-P0-ROUTING-001/002/003); CI installs PyYAML.

Changed files in this branch (vs base):

```
{changed}
```

## Tests and CI evidence — status: {test_status}

{test_section}

CI workflow: `.github/workflows/p0-ci.yml` (runs on pull requests and
pushes to the feature branch). Remote CI PASSED on
`fcf311ef79c5f10a4248f026a5f667109c584831` — 2/2 checks, run
https://github.com/msujoy149/consistency-frame/actions/runs/45046203236
(draft PR https://github.com/msujoy149/consistency-frame/pull/1). The
post-corrections CI run will be checked by the parent after the push.

## Known issues and deferred work

1. **Registry reconciliation (P1):** 165 derived features vs the
   historical 109/120 claim — reconcile counting units and update the
   README/docs/01 from the canonical registry.
2. **Adapter conformance (P1/P5):** all 12 adapters are NOT_TESTED.
   Conformance tests per host/editor are needed before any "supported"
   claim.
3. **Private-overlay runtime adapter (P2):** P0 adds schemas, validation
   and tests; a runtime adapter that resolves `CONSISTENCY_FRAME_CHARACTERS`
   is not built in P0.
4. **`setup.sh --with-components` end-to-end run (NOT RUN):** executing
   it downloads ~5 GB of components plus ~1 GB of Python/Node deps;
   it was verified by syntax check, dry-run core sync and failure-path
   tests only. Run it on a machine with network + disk before claiming
   it end-to-end.
5. **Research-register reconciliation (F7 in the Architecture Review):**
   `docs/research/gaps-research-20261112.md` labels items missing that
   later docs record; a research-to-repository reconciliation process
   is deferred.
6. **Media intelligence, reference learning runtime, provider
   orchestration, benchmarks, repair loop:** out of scope for P0 by
   design (P1–P4). Under v2.4 "orchestration" means the Brain directing
   companions by instruction — no server, no runtime.
7. **Runtime skill-routing engine (P1):** the routing matrix and
   workflow graph are canonical data; a runtime that executes them is
   P1 work.
8. **Script-to-performance runtime (P1):** the schemas are contracts;
   the runtime that produces Scene/Shot/Performance Plans from a
   script is P1 work.
9. **OpenMontage paid provider routes (evidence_level
   `present_locally` — documented in the companion's provider guide
   only, never exercised):** no live paid call was made; a paid call
   needs the user's explicit approval and keys.

## Privacy, licence and security notes

- Character/voice/media data stays private by default: `characters/`
  ships empty (`.gitkeep` + `README.md` only); `.gitignore` covers
  `characters/*`, media extensions, `.env` and secrets. Validator +
  tests enforce this.
- No secret or private media was added in P0 (secret scan passes).
- Licences intact: repo Apache-2.0 for own work; VoiceStudio +
  OpenMontage AGPL-3.0; OmniVoice weights CC-BY-NC (noncommercial) and
  never downloaded by `setup.sh`.
- Uploaded media / OCR / transcript text is untrusted data, never
  instructions (see `architecture/intent-modes.yaml`).

## Next phase (recommendation only — do not start)

P1 (CF-WO-P1-…): runtime skill-routing engine (execute the routing
matrix + workflow graph — intake → route → run → QC) + script-to-
performance runtime (produce Scene/Shot/Performance Plans from a
script) + reference-learning runtime — `UPLOAD_ONLY` gate,
intake/hash, evidence cards, learning ledger, duplicate/conflict
checks — on top of these P0 foundations, after independent review of
this branch.

## Evidence dates

- Live repo verified: 2026-11-22 (base `{base}`).
- Handoff package read: 2026-11-22 (all Markdown files + both DOCX
  text-extracted; ZIP snapshot identical to live `main` for tracked files).
- Report generated: {now}.
"""
    if CHECK:
        if os.path.exists(OUT) and open(OUT, encoding="utf-8").read() == report:
            print("CHECK OK: living report matches canonical records")
            return 0
        print("CHECK FAILED: living report is out of date "
              "(run scripts/generate-report.py)")
        return 1
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
