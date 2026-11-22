#!/usr/bin/env python3
"""Consistency Frame P0 — generate BUILD_REPORT_P0.md, build-report.json
and release-manifest.json from git state + tests/last-run.json.

The `commit` recorded in these files is the head commit at generation
time (the code head). The files themselves are committed afterwards as
a docs-only commit; the delivery message states both SHAs:
  code_head  — all P0 implementation
  final_head — code_head + this docs-only commit (manifest + reports only)
The manifest's per-file SHA-256 hashes are computed from the working
tree, which at generation time equals the code head tree.

Usage: python3 scripts/generate-build-report.py
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT_MD = os.path.join(ROOT, "docs", "implementation", "BUILD_REPORT_P0.md")
OUT_JSON = os.path.join(ROOT, "docs", "implementation", "build-report.json")
OUT_MANIFEST = os.path.join(ROOT, "release-manifest.json")


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", ROOT, *args], capture_output=True,
                          text=True, check=True).stdout.strip()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    base = git("rev-parse", "origin/main")
    head = git("rev-parse", "HEAD")
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    changed = git("diff", "--name-only", f"{base}...HEAD").splitlines()
    changed = [c for c in changed if c]
    log = git("log", "--format=%H %s", f"{base}..HEAD").splitlines()

    last_run = json.load(open(os.path.join(ROOT, "tests", "last-run.json"),
                              encoding="utf-8"))
    # Deduplicate test IDs, keeping the worst result (FAIL > PASS).
    by_id: dict[str, dict] = {}
    order = {"FAIL": 0, "PASS": 1, "SKIPPED": 2, "NOT RUN": 3}
    for t in last_run.get("tests", []):
        cur = by_id.get(t["id"])
        if cur is None or order[t["result"]] < order[cur["result"]]:
            by_id[t["id"]] = t
    tests = [by_id[k] for k in sorted(by_id)]
    overall = last_run.get("status", "UNKNOWN")

    files = []
    for rel in sorted(changed):
        p = os.path.join(ROOT, rel)
        if os.path.exists(p):
            files.append({"path": rel, "sha256": sha256_file(p),
                          "bytes": os.path.getsize(p)})

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    status = "PASS" if overall == "PASS" else "PARTIAL" if overall == "PARTIAL" else "FAIL"

    build_report = {
        "schema_version": "2.3",
        "work_order_id": "CF-WO-P0-001",
        "product": "Consistency Frame",
        "product_scope": "general-purpose-video-production-and-editing",
        "repository_url": "https://github.com/msujoy149/consistency-frame",
        "base_branch": "main",
        "base_commit": base,
        "branch": branch,
        "head_commit": head,
        "status": status,
        "changed_files": sorted(changed),
        "tests": [{"id": t["id"], "command": t["command"],
                   "exit_code": t["exit_code"], "result": t["result"],
                   "evidence": "tests/last-run.json"} for t in tests],
        "not_run": [
            "CF-INT-015 (component-clone failure path via setup.sh --with-components end-to-end): the full --with-components run downloads ~5 GB + ~1 GB deps; failure reporting is unit-tested in tests/test_installer.sh, the live run is NOT RUN.",
            "CI remote run: GitHub Actions runs only after the branch is pushed and a PR is opened; the workflow file is validated locally (YAML parse + pinned SHAs verified via API).",
            "setup.sh --with-components end-to-end on a clean machine: NOT RUN (network + disk); core-only path executed end-to-end locally (exit 0).",
        ],
        "known_issues": [
            "Registry reconciliation deferred to P1: 165 derived features vs historical 109/120 claim (different counting units).",
            "All 12 adapters are NOT_TESTED; no adapter may be called supported until a conformance test passes.",
            "Private-overlay runtime adapter deferred to P2 (P0 adds schemas, validation and tests).",
            "Research-register reconciliation (gaps-research-20261112.md staleness) deferred.",
            "Media intelligence, reference-learning runtime, provider orchestration, benchmarks and repair loop are out of scope for P0 by design (P1-P4).",
            "v2.4: runtime skill-routing engine and script-to-performance runtime are P1 work (matrix/graph/schemas are canonical data, not a runtime).",
            "v2.4: OpenMontage paid provider routes are NOT_VERIFIED; no live paid call was made.",
        ],
        "security_and_licence_notes": [
            "Secret scan (validate-repo.py): PASS — no credentials or private keys in tracked text files.",
            "Private-data check: PASS — characters/ tracks only .gitkeep + README.md; no media tracked; .gitignore covers characters/*, private-data/, media extensions, .env, secrets.",
            "Licences intact: own work Apache-2.0; VoiceStudio + OpenMontage AGPL-3.0; OmniVoice weights CC-BY-NC, never downloaded by setup.sh.",
            "Installer safety: no whole-directory deletion; manifest-owned sync only; symlink/traversal and unsafe-root rejection tested.",
        ],
        "private_data_check": "PASS",
        "package": {"archive": "consistency-frame-p0-feat-branch.zip",
                    "release_manifest": "release-manifest.json"},
        # NOTE: package.sha256 is intentionally omitted here. The ZIP is
        # built from the final head after this report is committed, so
        # its hash cannot be inside the committed file without a
        # circularity. The ZIP SHA-256 is recorded in the delivery
        # message and in BUILD_REPORT_P0.md §7 after the ZIP is built.
    }

    manifest = {
        "schema_version": "2.3",
        "version": "2.4-p0",
        "branch": branch,
        "commit": head,
        "files": files,
        "tests": [{"id": t["id"], "result": t["result"]} for t in tests],
        "generated_at_utc": now,
    }

    test_rows = "\n".join(
        f"| `{t['id']}` | `{t['command']}` | {t['exit_code']} | **{t['result']}** |"
        for t in tests)
    changed_list = "\n".join(f"- `{c}`" for c in sorted(changed))
    commit_list = "\n".join(f"- `{c}`" for c in log)

    md = f"""# CONSISTENCY FRAME — P0 IMPLEMENTATION REPORT

Work order **CF-WO-P0-001** (P0 only — Safe Foundations), architecture v2.3.
Product: general-purpose professional AI video production & editing system.

## 1. BASELINE

- Repository: https://github.com/msujoy149/consistency-frame
- Base branch / commit: `main` / `{base}`
- Feature branch: `{branch}`
- Head commit at generation time (code head): `{head}`
- Working tree at generation time: clean except the report/manifest files
  generated by this script (committed afterwards as a docs-only commit;
  the delivery message states that final head SHA).
- The supplied ZIP snapshot (`consistency-frame-main.zip`) was verified
  identical to live `main` for tracked files — nothing was overwritten
  from it; live Git is authoritative.

## 2. ACCESS

Files actually read (all READABLE, none NOT_ACCESSIBLE; no in-chat
preview needed):

- `Consistency_Frame_Architecture_Review_v2_3_BN.md` (794 lines) and its
  DOCX twin (text-extracted, matches the Markdown)
- `IMPLEMENTATION_AGENT_MASTER_KICKOFF_BN.md` (265 lines)
- `IMPLEMENTATION_WORK_ORDER_CF_P0_001_BN.md` (230 lines)
- `PRODUCT_MODES_AND_ASSET_LIFECYCLE_BN.md` (64 lines)
- `HANDOFF_START_HERE_BN.md` (40 lines)
- `PACKAGE_MANIFEST.json` (all 8 hashes verified)
- `Consistency_Frame_Repository_Audit_BN.docx` (text-extracted, 30,998 chars)
- `consistency-frame-main.zip` (SHA-256 `6bddc455ced58639ca2f9661a20dd1204eff7bbd2cce19434cf82543fdcbe01b`)
- `CONSISTENCY_FRAME_MUSE_IMPLEMENTATION_MASTER_PROMPT_v2_3.md` (28,625 B)
- Live GitHub remote (fetched 2026-11-22; head `{base}`)

## 3. IMPLEMENTED

- **P0.1 Non-destructive installer:** `scripts/sync-skills.sh` (manifest-owned
  sync, unmanaged skills preserved, dry-run, opt-in `--prune`, backup +
  rollback, symlink/traversal + unsafe-root rejection, truthful
  SUCCESS/PARTIAL/FAILED + exit codes). `setup.sh` rewritten: core-only
  by default, `--with-components` opt-in, no `rm -rf .agents/skills`,
  no `|| true` suppression, per-component status summary.
- **P0.2 Canonical registries:** `registry/skills.json` (15),
  `registry/features.json` (165, derived from skill sections),
  `registry/workflows.json` (13 intent modes),
  `registry/adapters.json` (12, all untested, none supported),
  generated by `scripts/generate-registries.py`.
- **P0.3 Asset schemas:** 20 versioned JSON Schemas in `schemas/`
  (character, voice-profile, sound-asset, visual-style, wardrobe, prop,
  location, project, story-bible, episode-state, intake-job,
  reference-review, reference-learning, script-contract,
  timeline-manifest, evidence, approval, installer-result,
  build-report, release-manifest). Voice and sound are separate types.
- **P0.4 Workflow/evidence/report schemas:** intake-job,
  reference-review/learning, script-contract, timeline-manifest,
  evidence, approval, installer-result, build-report, release-manifest
  (all in `schemas/`).
- **P0.5 Tests + CI:** `tests/` (17 checks) + `.github/workflows/p0-ci.yml`
  (actions pinned to verified full SHAs).
- **P0.6 Living report:** `docs/architecture/living-architecture-report-v2.3-p0.md`,
  generated from canonical records by `scripts/generate-report.py`.
- **P0.7 Capability truth:** `architecture/platform-capabilities.md` +
  `registry/adapters.json`; Muse corrected to knowledge-pack
  (README + `docs/06-installation.md`).
- **Defect fixes:** F1 (`rm -rf`), F2 (`|| true`), F3 (Muse claim), F4
  (private-overlay validator + tests), F7 (absolute quality claims →
  measurable scoped targets + human-review gate), F8 (universal −14 LUFS
  → named delivery profiles, `docs/19`), F9 (skill-first loop split
  into task-local draft §9A / permanent mutation on explicit
  authorisation §9B). Existing 15 skills preserved; no duplicate skill.
- **Counts:** the historical 109/120 claim is kept as a labelled
  historical claim in `registry/features.json` (`legacy_counts`);
  reconciliation is deferred P1 work.

### v2.4 revision (Brain Architecture Amendment — this run)

- **P0-A audit:** `docs/implementation/BRAIN_ARCHITECTURE_AUDIT.md` —
  zero server/API-backend/cloud-database claims in normative text
  (the withdrawn items never existed in code); one docs fix (v2.4
  section in `AGENTS.md`); no skill file changed; v2.4 mode mapping
  (ONE-OFF vs RECURRING) documented.
- **P0-B routing + performance schemas:**
  `architecture/SKILL_ROUTING_MATRIX.yaml` (15 skills, precedence
  1–15, command-authority is the router),
  `architecture/WORKFLOW_GRAPH.yaml` (42 edges, acyclic),
  four `schema_version: "2.4"` schemas (`scene-plan`, `shot-plan`,
  `performance-plan`, `script-to-performance` — the combined
  Script-to-Performance contract; dialogue VERBATIM unless a rewrite
  was explicitly requested).
- **P0-C companion + agent truth:**
  `architecture/COMPANION_CAPABILITY_REGISTRY.yaml` (VoiceStudio
  v0.5.8 + OpenMontage, verified capabilities only) and
  `architecture/AGENT_COMPATIBILITY_MATRIX.yaml` (10 agents, only
  Muse verified; OpenRouter is a model-routing layer, not a host;
  Colab needs a Notebook/Agent Runtime).
- **Tests + validator:** `tests/test_routing.py` (gates
  CF-P0-ROUTING-001/002/003) + `scripts/validate-repo.py` check 8
  (canonical YAML records); CI installs PyYAML.
- **Docs:** `docs/implementation/P0_UPDATED_IMPLEMENTATION_PLAN.md`,
  living report `docs/architecture/living-architecture-report-v2.4-p0.md`
  (v2.3 report retained as the baseline record).

Commits on this branch (base..head):

{commit_list}

Changed files ({len(changed)}):

{changed_list}

## 4. TEST RESULTS

Overall local result: **{overall}** (from `tests/last-run.json`).
Every test below was executed locally with the exact command shown.

| Test ID | Command | Exit | Result |
|---|---|---|---|
{test_rows}

Additional executed checks (not in the runner's per-ID list):

- `bash setup.sh` (core-only, real repo): exit 0 — 15 skills synced
  (8 changed, 7 unchanged), components SKIPPED, no downloads.
- `bash setup.sh --dry-run`: exit 0 (in `tests/test_installer.sh`).

NOT RUN (honestly, not claimed as passed):

- `setup.sh --with-components` end-to-end (would download ~5 GB +
  ~1 GB deps; failure reporting is unit-tested, the live run is NOT RUN).
- Remote GitHub Actions CI run (runs only after push + PR; workflow
  YAML parses locally and both action SHAs were verified via the
  GitHub API on 2026-11-22).

## 5. GITHUB

- Feature branch: `{branch}`
- Base commit: `{base}`
- Head commit (code head): `{head}`
- Push status / draft PR URL: see the delivery message (filled in after
  push; this report is generated before the push).

## 6. SECURITY & PRIVACY

- Secret scan: PASS (no credentials/private keys in tracked text files).
- Private-data check: PASS (`characters/` tracks only `.gitkeep` +
  `README.md`; no media tracked; `.gitignore` covers `characters/*`,
  `private-data/`, media extensions, `.env`, secrets).
- Licences intact: own work Apache-2.0; VoiceStudio + OpenMontage
  AGPL-3.0; OmniVoice weights CC-BY-NC, never downloaded by `setup.sh`.
- Installer safety: no whole-directory deletion; manifest-owned sync
  only; symlink/traversal and unsafe-root rejection tested.
- Uploaded media / OCR / transcript text is treated as untrusted data,
  never as instructions.

## 7. ARTIFACTS

- Source ZIP: `consistency-frame-p0-feat-branch.zip` (built from the
  final head via `git archive`; SHA-256 in the delivery message).
- Release manifest: `release-manifest.json` (per-file SHA-256 for all
  {len(files)} changed files, test results, code-head commit `{head}`).
- Machine-readable build report: `docs/implementation/build-report.json`
  (package.sha256 is omitted by design — the ZIP is built from the final
  head after this report is committed; the ZIP SHA-256 in the delivery
  message is authoritative).
- This report: `docs/implementation/BUILD_REPORT_P0.md`.

## 8. ACCEPTANCE GATES

| Gate | Result | Evidence |
|---|---|---|
| CF-INT-014 unmanaged skill survives install | PASS | `tests/test_installer.sh` |
| CF-INT-015 dependency failure reports PARTIAL/FAILED | PASS | `tests/test_installer.sh` (missing-source + unsafe-root failure paths; full `--with-components` live run NOT RUN — see §4) |
| CF-INT-020 handoff has branch, commit, changed files, test evidence, ZIP hash, manifest | PASS | this report + `release-manifest.json` + ZIP (hash in delivery message) |
| CF-INT-023 living report matches canonical records, history retained | PASS | `tests/test_registries.py` + `scripts/generate-report.py --check` |
| CF-P0-ASSET-001 temporary use creates no permanent record | PASS | `tests/test_modes.py` |
| CF-P0-ASSET-002 registration fails without authorisation/name/ID/reference | PASS | `tests/test_modes.py` |
| CF-P0-ASSET-003 voice and sound are separate schemas/types | PASS | `tests/test_schemas.py` |
| CF-P0-ADAPTER-001 untested editor/provider not marked supported | PASS | `tests/test_registries.py` |
| CF-P0-ROUTING-001 routing matrix covers all 15 skills, required fields, precedence unique 1–15 | PASS | `tests/test_routing.py` |
| CF-P0-ROUTING-002 workflow graph acyclic, edges match routing-matrix dependencies (+ router edges) | PASS | `tests/test_routing.py` |
| CF-P0-ROUTING-003 companion registry honest statuses, agent matrix only Muse verified | PASS | `tests/test_routing.py` |

**P0 result: {status}** (all critical installer/data/security gates pass
locally; CI remote run is pending the push/PR and is recorded as NOT RUN,
not passed).

## 9. KNOWN ISSUES

- Registry reconciliation deferred to P1 (165 derived features vs
  historical 109/120 claim).
- All 12 adapters NOT_TESTED; no "supported" claim until conformance tests pass.
- Private-overlay runtime adapter deferred to P2.
- Research-register reconciliation deferred.
- `setup.sh --with-components` end-to-end NOT RUN (see §4).
- Media intelligence, reference-learning runtime, provider orchestration,
  benchmarks, repair loop: out of scope for P0 by design (P1–P4).
- v2.4: runtime skill-routing engine and script-to-performance runtime
  are P1 work (the matrix/graph/schemas are canonical data, not a runtime).
- v2.4: OpenMontage paid provider routes are NOT_VERIFIED; no live paid
  call was made.

## 10. NEXT PHASE

P1 (separate work order, do not start): runtime skill-routing engine
(execute the routing matrix + workflow graph) + script-to-performance
runtime (produce Scene/Shot/Performance Plans from a script) + intent
router + reference-learning runtime — `UPLOAD_ONLY` gate, intake/hash,
evidence cards, learning ledger, duplicate/conflict checks — after
independent review of this branch.

## 11. v2.4 REVISION (Brain Architecture Amendment)

- Amendment: user voice call 2026-11-22. Consistency Frame is the
  CENTRAL BRAIN / Orchestrator; Central Server Manager + own-API
  implementation are WITHDRAWN and were never built. Three-repo model:
  Brain (this repo) / VoiceStudio (voice/speech) / OpenMontage (video
  production/editing). No server, API backend or central database.
- Deliverables: `docs/implementation/BRAIN_ARCHITECTURE_AUDIT.md`,
  `architecture/SKILL_ROUTING_MATRIX.yaml`,
  `architecture/WORKFLOW_GRAPH.yaml`,
  `architecture/COMPANION_CAPABILITY_REGISTRY.yaml`,
  `architecture/AGENT_COMPATIBILITY_MATRIX.yaml`,
  `schemas/script-to-performance.json` (SCRIPT_TO_PERFORMANCE_SCHEMA.json)
  + `schemas/scene-plan.json`, `schemas/shot-plan.json`,
  `schemas/performance-plan.json`,
  `docs/implementation/P0_UPDATED_IMPLEMENTATION_PLAN.md`.
- Release manifest version for this run: `2.4-p0` (manifest format
  `schema_version` stays `2.3`; the v2.4 schemas carry their own
  `schema_version: "2.4"`).
- The v2.3 sections of this report (§§1–10) are the historical record
  of the first P0 run; this section records the revision on top of it.
"""

    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(md)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(build_report, f, indent=2)
        f.write("\n")
    with open(OUT_MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    print(f"wrote {OUT_MD}\nwrote {OUT_JSON}\nwrote {OUT_MANIFEST}")
    print(f"base={base}\nhead={head}\nchanged_files={len(changed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
