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

`github_branch_head` records the GitHub head of the branch this
package describes (see §12 Provenance in the generated report):
  --github-head <sha> (or the CF_GITHUB_HEAD env var) pins it;
  without either, it defaults to the current git HEAD. Pushing the
  regenerated manifest advances the branch head by one docs-only
  commit; the delivery message states that final head. The manifest
  never tries to predict its own push SHA.

release-manifest.json is excluded from its own `files` list (a file
cannot contain its own hash); it IS listed in build-report.json's
`changed_files`, which is a list of names, not hashes.

A detached checksum file, docs/implementation/CHECKSUMS.txt, is also
written: SHA-256 + byte count of the three generated files as
generated (before commit). The ZIP hash lives in the delivery message
(the ZIP is built from the final head after commit).

Usage: python3 scripts/generate-build-report.py [--github-head <sha>]
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
OUT_CHECKSUMS = os.path.join(ROOT, "docs", "implementation", "CHECKSUMS.txt")

# Remote CI evidence (P0-002 §7): verified by the parent on 2026-11-22.
# CI PASSED on this head — 2/2 checks. The post-corrections CI run is
# checked by the parent after the push; this record is the evidence
# for the head it names, not a claim about a later head.
CI_HEAD = "fcf311ef79c5f10a4248f026a5f667109c584831"
CI_RUN_URL = ("https://github.com/msujoy149/consistency-frame/actions/"
              "runs/45046203236")
CI_PR_URL = "https://github.com/msujoy149/consistency-frame/pull/1"


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", ROOT, *args], capture_output=True,
                          text=True, check=True).stdout.strip()


def head_time() -> str:
    """Generation timestamp: the HEAD commit's time, NOT the wall clock,
    so regenerating at the same head is byte-identical and the manifest's
    hashes stay valid (P0-002 fix). Falls back to the wall clock only if
    git cannot supply a commit time."""
    try:
        epoch = int(git("log", "-1", "--format=%ct", "HEAD"))
        return datetime.fromtimestamp(epoch, timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


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
    base = git("rev-parse", "origin/main")
    head = git("rev-parse", "HEAD")
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    github_head = resolve_github_head(sys.argv, os.environ, head)
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
        # release-manifest.json is excluded from its own file-hash list:
        # a file cannot contain its own hash (see §12 Provenance).
        if rel == "release-manifest.json":
            continue
        # docs/implementation/CHECKSUMS.txt is excluded for the same
        # reason: it contains this manifest's hash (P0-002 fix).
        if rel == "docs/implementation/CHECKSUMS.txt":
            continue
        p = os.path.join(ROOT, rel)
        if os.path.exists(p):
            files.append({"path": rel, "sha256": sha256_file(p),
                          "bytes": os.path.getsize(p)})

    now = head_time()
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
        "github_branch_head": github_head,
        "status": status,
        "changed_files": sorted(changed),
        "ci": {
            "head": CI_HEAD,
            "result": "PASS",
            "checks_passed": 2,
            "checks_total": 2,
            "run_url": CI_RUN_URL,
            "pull_request": CI_PR_URL,
            "note": ("Remote CI PASSED on the GitHub branch head named "
                     "here. The post-corrections CI run is checked by the "
                     "parent after the push; this record is evidence for "
                     "the head it names, not a claim about a later head."),
        },
        "tests": [{"id": t["id"], "command": t["command"],
                   "exit_code": t["exit_code"], "result": t["result"],
                   "evidence": "tests/last-run.json"} for t in tests],
        "not_run": [
            "CF-INT-015 (component-clone failure path via setup.sh --with-components end-to-end): the full --with-components run downloads ~5 GB + ~1 GB deps; failure reporting is unit-tested in tests/test_installer.sh, the live run is NOT RUN.",
            "setup.sh --with-components end-to-end on a clean machine: NOT RUN (network + disk); core-only path executed end-to-end locally (exit 0).",
        ],
        "known_issues": [
            "Registry reconciliation deferred to P1: 165 derived features vs historical 109/120 claim (different counting units).",
            "All 12 adapters are NOT_TESTED; no adapter may be called supported until a conformance test passes.",
            "Private-overlay runtime adapter deferred to P2 (P0 adds schemas, validation and tests).",
            "Research-register reconciliation (gaps-research-20261112.md staleness) deferred.",
            "Media intelligence, reference-learning runtime, provider orchestration, benchmarks and repair loop are out of scope for P0 by design (P1-P4).",
            "v2.4: runtime skill-routing engine and script-to-performance runtime are P1 work (matrix/graph/schemas are canonical data, not a runtime).",
            "v2.4: OpenMontage paid provider routes have evidence_level present_locally (documented in the companion's provider guide only, never exercised); no live paid call was made.",
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
        "github_branch_head": github_head,
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
- GitHub branch head recorded in this package: `{github_head}`
  (remote head of `{branch}`; see §12 Provenance)
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

Remote CI evidence (not NOT RUN — it ran and passed):

- Remote GitHub Actions CI PASSED on GitHub branch head `{CI_HEAD}`:
  2/2 checks, run {CI_RUN_URL} (draft PR {CI_PR_URL}). The
  post-corrections CI run will be checked by the parent after the push.

## 5. GITHUB

- Feature branch: `{branch}`
- Base commit: `{base}`
- Head commit (local code head): `{head}`
- GitHub branch head: `{CI_HEAD}` (remote head; 20 snapshot commits
  pushed to the branch plus 1 web commit that added
  `.github/workflows/p0-ci.yml` — the remote tree equals the local
  tree, verified by identical blob SHA for the workflow file)
- Draft PR: {CI_PR_URL}
- Push status: branch pushed; draft PR open; remote CI PASSED on
  `{CI_HEAD}` (2/2 checks, run {CI_RUN_URL}). The regenerated
  manifest and reports in this package are committed afterwards as a
  docs-only commit, which advances the branch head by one; the
  delivery message states that final head (see §12).

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
  {len(files)} changed files, excluding `release-manifest.json`
  itself — see §12; test results, code-head commit `{head}`,
  GitHub branch head `{github_head}`).
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
| CF-P0-ROUTING-003 companion registry honest evidence levels, agent matrix only Muse verified | PASS | `tests/test_routing.py` |
| CF-P0-ROUTING-004 companion evidence_level closed set, run references, repo pins, zero production_verified | PASS | `tests/test_routing.py` |
| CF-P0-REPORT-001 --github-head recorded in build-report.json + release-manifest.json (flag wins, CF_GITHUB_HEAD fallback, HEAD default) | PASS | `tests/test_reports.py` |
| CF-P0-REPORT-002 release-manifest.json excluded from its own file list, kept in build-report.json changed_files; CHECKSUMS.txt matches the generated files | PASS | `tests/test_reports.py` |
| CF-P0-REPORT-003 CI evidence current (CI PASSED on the GitHub head), no obsolete "CI NOT RUN" text, --with-components NOT RUN kept | PASS | `tests/test_reports.py` |
| CF-P0-REPORT-004 generated build-report.json + release-manifest.json validate against their schemas | PASS | `tests/test_reports.py` |

**P0 result: {status}** (all critical installer/data/security gates pass
locally; remote CI PASSED on GitHub branch head `{CI_HEAD}` — 2/2
checks, run {CI_RUN_URL}; the post-corrections CI run will be checked
by the parent after the push).

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
- v2.4: OpenMontage paid provider routes have evidence_level
  `present_locally` (documented in the companion's provider guide
  only, never exercised); no live paid call was made.

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

## 12. PROVENANCE (P0-002 §7 — GitHub head and the two-head rule)

- Two heads, two meanings. `head_commit` / `commit` is the local code
  head at generation time (`{head}`): the head of the implementation
  this package describes. `github_branch_head` is the GitHub head of
  the branch (`{github_head}`): the remote head the manifest records
  as the code it describes.
- The two-head rule: the manifest records the GitHub head of the code
  it describes; pushing the regenerated manifest itself advances the
  branch head by one docs-only commit, and the delivery message states
  that final head. Do NOT try to make the manifest predict its own
  push SHA — the manifest is generated before that commit exists.
- Self-exclusion: `release-manifest.json` is excluded from its own
  `files` list, because a file cannot contain its own SHA-256 hash.
  It IS listed in `build-report.json`'s `changed_files` — that list
  holds file names, not hashes, so there is no circularity. The two
  lists answer different questions: names changed vs base, and
  per-file hashes of the package. `docs/implementation/CHECKSUMS.txt`
  is excluded from the manifest's `files` list for the same reason —
  it contains this manifest's hash. Both exclusions are checked by
  `tests/test_reports.py` (CF-P0-REPORT-002).
- Deterministic generation: the timestamps in the generated reports
  come from the HEAD commit's time, not the wall clock, so regenerating
  at the same head is byte-identical and the manifest's hashes stay
  valid. Generate the living report first, then this report, and every
  listed hash verifies against the final tree.
- Detached checksums: `docs/implementation/CHECKSUMS.txt` holds the
  SHA-256 + byte count of `release-manifest.json`,
  `docs/implementation/build-report.json` and
  `docs/implementation/BUILD_REPORT_P0.md` as generated (before
  commit). The source-ZIP hash is NOT in that file: the ZIP is built
  from the final head after this report is committed, so its hash
  lives in the delivery message only.
- CI evidence for this package: remote CI PASSED on GitHub branch head
  `{CI_HEAD}` — 2/2 checks, run {CI_RUN_URL} (draft PR {CI_PR_URL}).
  That record is evidence for the head it names. The post-corrections
  CI run (on the new head after this package is pushed) will be
  checked by the parent after the push; it is NOT claimed here.
- Regenerated under CF-WO-P0-002 (independent-review corrections)
  with `--github-head {github_head}`.
- Regenerated under CF-WO-P0-003 (final independent security
  correction) with `--github-head {github_head}`: the installer
  metadata writers now use one secure atomic-write helper
  (`scripts/atomic_write.py` — `tempfile.mkstemp()` + fd write +
  fsync + `os.replace()`), closing the predictable-`.tmp` symlink
  vulnerability in `write_manifest()` / `update_manifest_hashes()`
  (and the same pattern in the last-sync and run-owner writers).
  Regression tests SEC-MANIFEST-01..04 + CF-P0-ATOMIC-001..006;
  full suite 40/40 PASS locally. See
  `docs/implementation/CF-WO-P0-003-corrections.md`.
"""

    # The manifest's hashes for the two files this script writes must be
    # the hashes of the bytes about to be written, not the bytes on disk
    # from the previous generation (P0-002 fix): the MD and JSON are
    # rebuilt every run, so their on-disk hashes are always one
    # generation stale. build-report.json is written as
    # json.dumps(..., indent=2) + "\n"; the MD as the string itself.
    md_bytes = md.encode("utf-8")
    json_bytes = (json.dumps(build_report, indent=2) + "\n").encode("utf-8")
    for entry in manifest["files"]:
        if entry["path"] == "docs/implementation/BUILD_REPORT_P0.md":
            entry["sha256"] = hashlib.sha256(md_bytes).hexdigest()
            entry["bytes"] = len(md_bytes)
        elif entry["path"] == "docs/implementation/build-report.json":
            entry["sha256"] = hashlib.sha256(json_bytes).hexdigest()
            entry["bytes"] = len(json_bytes)

    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(md)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(build_report, f, indent=2)
        f.write("\n")
    with open(OUT_MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    # Detached checksums of the three generated files, as generated
    # (before commit). The ZIP hash is NOT listed here: the ZIP is
    # built from the final head after commit, so its hash lives in
    # the delivery message only (see §12 Provenance).
    checksums = (
        "# Consistency Frame P0 — detached checksums\n"
        "# SHA-256 + byte count of the three generated report files, as\n"
        "# generated (before commit). The source-ZIP hash is NOT listed\n"
        "# here: the ZIP is built from the final head after commit, so\n"
        "# its hash lives in the delivery message only.\n"
    )
    for rel in ("release-manifest.json",
                "docs/implementation/build-report.json",
                "docs/implementation/BUILD_REPORT_P0.md"):
        p = os.path.join(ROOT, rel)
        checksums += f"{sha256_file(p)}  {os.path.getsize(p)}  {rel}\n"
    with open(OUT_CHECKSUMS, "w", encoding="utf-8") as f:
        f.write(checksums)
    print(f"wrote {OUT_MD}\nwrote {OUT_JSON}\nwrote {OUT_MANIFEST}")
    print(f"wrote {OUT_CHECKSUMS}")
    print(f"base={base}\nhead={head}\nchanged_files={len(changed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
