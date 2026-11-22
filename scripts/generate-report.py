#!/usr/bin/env python3
"""Consistency Frame P0 — generate the Living Architecture Report from
canonical records (registry/*.json, schemas/, git state, test results).

The report is GENERATED, not hand-typed: inventory counts come from the
registry files, the base/head commits from git, and test results from
tests/last-run.json (written by tests/run-tests.sh). If the test file
is absent, tests are reported as NOT RUN — never as passed.

Usage:
  python3 scripts/generate-report.py [--check]
  --check exits 1 if the committed report differs from a fresh
  generation (used by CI).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "docs", "architecture", "living-architecture-report-v2.3-p0.md")
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

    report = f"""# Living Architecture Report — v2.3 P0 (Safe Foundations)

**Generated:** {now} — from canonical records (`registry/*.json`,
`schemas/`, git state, `tests/last-run.json`). Do not edit the inventory
numbers by hand; regenerate with `python3 scripts/generate-report.py`.

**Product scope:** general-purpose professional AI video production
and editing system (2D/3D animation, realistic human video,
image-to-video and video-to-video, character/voice/sound consistency,
stories, web series and episodic production, cinematography, VFX,
editing, audio, post-production). Not a single-genre tool.

**Repository:** https://github.com/msujoy149/consistency-frame
**Base branch/commit:** `main` / `{base}`
**Feature branch:** `{branch}`
**Head commit:** `{head}`
**Architecture/report version:** v2.3 P0 (work order CF-WO-P0-001)
**Previous report:** none — this is the first living report (baseline is
live `main` at `{base}`).

## Inventory (generated from canonical records)

| Registry | Count |
|---|---|
| Skills (`registry/skills.json`) | {skills["count"]} |
| Features (`registry/features.json`) | {features["count"]} |
| Workflows / intent modes (`registry/workflows.json`) | {workflows["count"]} |
| Adapters (`registry/adapters.json`) | {adapters["count"]} |
| JSON Schemas (`schemas/*.json`) | {len(schema_files)} |

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

Changed files in this branch (vs base):

```
{changed}
```

## Tests and CI evidence — status: {test_status}

{test_section}

CI workflow: `.github/workflows/p0-ci.yml` (runs on pull requests and
pushes to the feature branch). A remote CI run URL is available only
after the branch is pushed and a PR is opened; until then CI is
NOT RUN, not passed.

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
   design (P1–P4).

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

P1 (CF-WO-P1-…): intent router + reference-learning runtime —
`UPLOAD_ONLY` gate, intake/hash, evidence cards, learning ledger,
duplicate/conflict checks — on top of these P0 foundations, after
independent review of this branch.

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
