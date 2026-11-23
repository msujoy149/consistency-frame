# CF-WO-P0-009 Corrections — Immutable Authorization Context, Fail-Closed Character Resolution & Timeline Ownership Binding

**Work order:** CF-WO-P0-009 (independent-review follow-up to P0-008)
**Branch:** `feat/cf-p0-safe-foundations` — PR #1, NOT merged
**Base (P0-008 docs head):** `ad692d0`
**Code head (this round):** `ee29b51` (4 commits: `ae3b1e1`, `f0ea7be`, `133f5e9`, `ee29b51`)
**Remote head at order start (verified live):** `49aa01d70a0b4236e70e287e74b4a2f4f7c6af98`
**Date:** 2026-11-23

---

## 1. What existed (P0-008 state)

- `TrustedAuthorizationContext` (`scripts/asset_policy.py`, ~lines 744–794) used `__slots__` and described itself as immutable. Revocation was done by setting `ctx.revoked = True` — including inside the security test itself (`tests/test_private_voice_security.py`, line ~375).
- `resolve_voice_for_production()` (`scripts/asset_policy.py`, ~lines 635–705) skipped the Character-existence and Character/Voice ownership checks when `character_registry is None` (the `if character_registry is not None:` block was skipped; `validate_voice_profile(vp, character=None)` ran with `character=None`).
- `validate_timeline_cross_references()` (`scripts/timeline_policy.py`, ~lines 97–110) defaulted to `strict=False`: a caller omitting the keyword got structural-only validation.
- `_strict_v25_errors()` (`scripts/timeline_policy.py`, Voice Profile section ~lines 620–680) checked a Voice Profile's own permissions/authorization but did not verify that the Voice Profile's ownership matches the ownership of the Character it claims to represent (the Audio Asset path already had an equivalent relationship check).
- P0-008 provenance: the delivered Bengali final report (`P0-008-final-report-bn.md`, §8, inside `P0-008-report.zip`) recorded `tests/last-run.json` SHA-256 `03bcf746e8e0321a723cfa48e6ba40fef07257586b0b09faa6917283052b8309`; the PR #1 P0-008 section stated the CI artifact zip could not be downloaded from the run page.

## 2. What was contradictory / missing

1. **Immutability claim vs reality (Task A).** `__slots__` blocks *new* attributes but allows reassignment of every existing field. The class claimed immutability while `ctx.revoked = True` and `ctx.scope = "forged scope"` both succeeded. Revocation *was* mutation of the authorization object itself.
2. **Resolver fail-open (Task B).** A v2.5 private voice could be resolved with `character_registry=None` and correct requester identity — the Character/Voice ownership relationship was never checked on that path.
3. **Unsafe default (Task C).** The production-facing timeline validator's default was the weak mode; strict v2.5 checks were opt-in.
4. **Missing binding (Task D).** Two assets could each independently pass workspace authorization while being linked across different owners (Character owner A + Voice Profile owner B, both `shared`/`workspace` in the same workspace) — the timeline accepted the cross-owner link that the production voice resolver would reject.
5. **Stale evidence (Task E).** `03bcf746…` is the P0-007 last-run hash, not P0-008's. The correct P0-008 hash is `cdb30569…` (verified below, both sides). The PR statement about the artifact download was true when written but stale after the artifact was downloaded and byte-verified.

## 3. What changed

### TASK A — TrustedAuthorizationContext is genuinely immutable

`scripts/asset_policy.py`:

- `__init__` writes all fields via `object.__setattr__` and sets a `_frozen` slot flag last. `__setattr__` / `__delattr__` raise **`AttributeError`** on a frozen instance for *any* attribute (existing or new). There is no `__dict__` slot (`vars()` raises `TypeError`). `__copy__`, `__deepcopy__`, and `__setstate__` (pickle) all return frozen objects, so copying cannot manufacture a mutable context. `dataclasses.replace` raises `TypeError` (not a dataclass). Direct construction still raises `TypeError` — the factory boundary (`issue_trusted_authorization_context`) is unchanged; no new public mechanism to manufacture trusted contexts was added.
- New immutable per-issuance `authorization_id` (uuid4 hex minted by the factory).
- **Revocation separated from the context:** module-level registry `_REVOKED_AUTHORIZATION_IDS`, keyed by `authorization_id`. New functions `revoke_trusted_authorization_context(ctx)` / `is_trusted_authorization_revoked(ctx)` (both raise `TypeError` for non-contexts — a dict/SimpleNamespace fake can neither revoke nor be reported "not revoked"). Revoking never mutates the issued context — `revoked` stays `False`, all fields unchanged. `validate_private_voice_export` rejects when `ctx.revoked` is set (defence in depth) **or** the id is in the registry.
- Consumers audited (grep across `scripts/` + `tests/`): the only `.revoked` / context consumers are `validate_private_voice_export` and the two test files; no other production code touches the class.
- **Caveat (honest):** the revocation registry is process-local/in-memory; a restart clears it and contexts must be re-issued. Persistence is P1 runtime work. The context remains a structural (type) boundary, NOT cryptographic proof of identity.

### TASK B — v2.5 voice resolution fails closed without a Character Registry

`scripts/asset_policy.py`, `resolve_voice_for_production()`:

- For a v2.5 voice, a missing **or non-dict** Character Registry now returns `(None, […])` before any character/validation step. Missing Character → `unknown character_id '…'`; mismatched Character/Voice ownership → ownership-mismatch error; non-dict Character record → fail-closed error.
- Exact missing-registry error:
  `v2.5 private voice resolution requires a valid Character Registry — no Character Registry was provided, so the voice cannot be resolved (fail closed: a v2.5 private voice is never resolvable without its Character Registry)`
- Requester, workspace, permission, approval, and provider-transmission checks are unchanged and still run after the registry gate.
- Legacy v2.3 keeps its exact historical contract (registry consulted only when given; no-registry resolution with `require_approved=False` still works) — v2.5 never silently falls back to it; legacy exceptions are explicit and version-aware.
- Callers audited: `resolve_voice_for_production` is called directly only from the two test files (plus a comment mention in `timeline_policy.py`, which does not call it). Two existing call sites relied on the bypass and were updated to the new contract with assertions unchanged: AC-09 in `test_character_registration.py` now passes `character_registry=registry`, and the (d2) spy in the security suite now passes a Mina Character Registry.

### TASK C — Strict Timeline v2.5 validation is the safe default

`scripts/timeline_policy.py`:

- `validate_timeline_cross_references(manifest, registry, requesting_owner_id=None, requesting_workspace_id=None, *, strict=None)` is the production entry point. `strict` is a tri-state sentinel, not a plain boolean default:
  - `strict=None` (default, i.e. omitted): production default — full strict v2.5 checks run on every v2.5 manifest. Only a manifest whose `schema_version` is exactly `"2.3"` keeps its historical legacy structural contract; any other/missing version is validated strictly (fail closed). A plain `strict=True` default was rejected as a design because it would have broken the pinned case of a valid v2.3 legacy timeline passing with no `strict` argument (`test_private_voice_security.py` c16a) — the sentinel distinguishes "caller omitted it" from "caller forced strict".
  - `strict=True`: forces strict; a v2.3 manifest under it returns the version error (preserves prior c18 behaviour).
  - `strict=False` on a v2.5 manifest is **refused**: structural errors are still computed and a refusal error is appended, so the result is never `[]` for a v2.5 manifest.
- New explicitly named legacy entry point: `validate_timeline_structural(manifest, registry)` — structural contract only. The structural body was extracted once into internal `_structural_errors()`, shared by both entry points (no duplicated logic). Module + function docstrings state which entry point is production-suitable and that a structural `[]` is NOT authorization and must NEVER be used to authorize or export a v2.5 Timeline.
- Callers updated: in `tests/test_timeline_manifest.py`, `full_errors()` and the v2.5 multi-character fixture check now use `validate_timeline_structural()` (they are structural cases with no ownership/requester); a repo-wide grep found no other callers of the validator (`scripts/validate-repo.py` does not call it).

### TASK D — Voice Profile ownership is bound to its linked Character in Timeline validation

`scripts/timeline_policy.py`, `_strict_v25_errors()`:

- The Voice Profile loop now, for every referenced voice, resolves `rec["character_id"]` and enforces the same binding the production voice resolver enforces, reusing the existing `asset_policy.ownerships_match` helper (already imported; no duplicated comparison logic, no new helper depended on from the other worker).
- Enforced EVEN when both resources independently have valid shared-workspace permissions. Requester authorization, workspace access, sharing policy, and approval checks are untouched. No ownership data is repaired, replaced, or reassigned.
- Exact mismatch error (both IDs included):
  `strict v2.5: voice_profile_id 'vp-ana-001' ownership does not match character 'char-ana-001' ownership (owner/workspace must match) — a voice profile must not be linked to a character with different ownership, even when both are shared in the same workspace`
- Also rejects: voice with no `character_id` link; linked character that does not resolve to a registered record; linked character with missing/malformed ownership. Since `ownerships_match` requires equal `owner_id` AND `workspace_id`, owner-mismatch and workspace-mismatch both reject.

### Cross-cutting audit (test-only authorization logic)

- `tests/test_private_voice_security.py` / `tests/test_character_registration.py`: no production responsibility was found implemented only in a test. `check_voice_binding` and `resolve_for_user` already *are* the production functions (identity-pinned by (d3)/(d4)); `resolve_voice_for_character` is a thin wrapper delegating to the production resolver — pinned by the (d2) spy, and new (d5) pins it has **no fallback**: if the production resolver is replaced by one raising `RuntimeError("production resolver unavailable")`, the failure propagates instead of resolving. The remaining helpers (`validate_registration`, `validate_voice_profile`, `register`, `resolve_references`, `is_releasable`, `validate_invitation`) are fixture/contract validators for schema rules the JSON-Schema subset cannot express, not authorization logic — nothing moved.
- `tests/test_timeline_manifest.py`: no test-only validation logic to move — no ownership, authorization, voice-resolution, or requester-access code was duplicated there (P0-008 had already removed it). `full_errors()` is a thin combiner (schema + production validator). Added regression check (C11) asserting the test aliases `is` the production functions (`validate_timeline_cross_references` and `validate_timeline_structural`), so a bypass/unavailable production function fails the suite.
- **Production module responsible for each critical contract:** voice resolution + ownership + export authorization + authorization context = `scripts/asset_policy.py`; timeline cross-reference validation (structural + strict v2.5) = `scripts/timeline_policy.py` (imports `ownerships_match` / `authorize_action` / `validate_ownership` from `asset_policy.py`); schema-level structural rules = `schemas/*.json` + `scripts/validate-repo.py`.

### TASK E — P0-008 provenance and PR documentation corrected

**Verified (not taken on faith):**

- Local `tests/last-run.json` before this round's suite run: SHA-256 `cdb305693d7a29525181892ca1ff10d5ea65a4ddc607e4bd2658b08d832921e8` (49 entries, PASS).
- Downloaded P0-008 CI artifact (`p0-test-results`, run #120, file `browser-download-20261123T072049.244279216Z-1-p0-test-results.zip` in `~/workspace/browser_downloads/`): its `last-run.json` SHA-256 is independently `cdb305693d7a29525181892ca1ff10d5ea65a4ddc607e4bd2658b08d832921e8` (49 entries, PASS). The two agree byte-for-byte.
- `03bcf746e8e0321a723cfa48e6ba40fef07257586b0b09faa6917283052b8309` is the **P0-007** last-run hash. Its only correct appearances in the repo are in `docs/implementation/CF-WO-P0-007-corrections.md:629` (P0-007's own record) and inside the historical P0-007/P0-008 diff files (diffs are historical records — untouched). The correct P0-008 hash `cdb30569…` was already recorded in `docs/implementation/CF-WO-P0-008-corrections.md:563` and in `release-manifest.json` (the `tests/last-run.json` entry) — no repo file recorded the stale hash as a P0-008 result.
- The stale hash DID appear as a P0-008 result in exactly one delivered file: `~/workspace/consistency-frame-p0-delivery/P0-008-final-report-bn.md`, line 57 (§8). **Corrected in place:** line 57 now records `cdb305693d7a29525181892ca1ff10d5ea65a4ddc607e4bd2658b08d832921e8`, with a correction note added at line 59 explaining the old value was P0-007's hash. `P0-008-report.zip` was rebuilt from the corrected file (`unzip -t` clean). Old ZIP SHA-256 `480750188b08a4047b8814a85b2b2adfca89f85a638c497af379e33723dce43d`; new ZIP SHA-256 `9983fac03ad2b6036464fdf1bb62b1a19d2c153d51558d76103b1d51ae561ce3`. The corrected `.md` SHA-256 is `98e0d54fd080345b28ea79315245aaec4a38b20889d75681e3223690915b675b`. (The user already received/uploaded the old ZIP to ChatGPT; the parent decides whether to re-deliver the corrected ZIP — the correction is recorded here and in the P0-009 final report.)
- The PR #1 P0-008 section contains **no** last-run SHA at all (the single `03bcf746` occurrence in the whole PR body is at the P0-007 section, where it is correct). Its stale statement is the artifact-download sentence (see the prepared correction below).
- Source-code head vs documentation-only head is preserved: manifest `commit` = the code head, `github_branch_head` = the remote branch head at push time (two-head rule, as in P0-006–P0-008). No artifact hash is presented as a source commit hash anywhere.

**Prepared corrected PR-section text (for the parent to apply verbatim to PR #1 — the coordinator does NOT update the PR):**

Old text (P0-008 section, CI paragraph) — replace this sentence:

> (The artifact zip itself could not be downloaded from the run page, so no byte-level zip comparison was possible; content totals were verified from the job log and the committed file.)

New text:

> The artifact zip was subsequently downloaded from the run page and byte-verified: the downloaded `p0-test-results` (ID 14796650215, 819 bytes, SHA-256 `860c250448ed66c3e985bfa8085482f3b2e2f2884aac20b1025d69a8b047c314`) contains `last-run.json` with SHA-256 `cdb305693d7a29525181892ca1ff10d5ea65a4ddc607e4bd2658b08d832921e8`, byte-identical to the committed `tests/last-run.json` (49 recorded entries, 37 distinct test IDs, 30 distinct command strings, 49 PASS). (Correction, P0-009 TASK E: the earlier statement that the artifact could not be downloaded was true when first written; the download and byte-verification were completed afterwards. The P0-008 final report's §8 also previously recorded the stale P0-007 hash `03bcf746…` for this file; the correct P0-008 hash is `cdb30569…`, and the delivered report file has been corrected and its ZIP rebuilt — see `docs/implementation/CF-WO-P0-009-corrections.md` §3, TASK E.)

Also add the correct P0-008 last-run hash to the P0-008 PR section's test-evidence line if the parent edits that section (it currently records no last-run SHA for P0-008): `tests/last-run.json` SHA-256 `cdb305693d7a29525181892ca1ff10d5ea65a4ddc607e4bd2658b08d832921e8`.

**What was NOT claimed:** no release ZIP or 152-file set was independently verified in this round beyond the manifest-vs-tree and manifest-vs-ZIP checks recorded in §5 (the P0-009 ZIP is built by the parent at delivery, as before).

## 4. Negative-control evidence (reproduced, labelled)

All before/after runs were actually executed by the workers (scripts in `/tmp`, not committed):

- **Task A** (`/tmp/p009-neg-before.py` before fix, `/tmp/p009-neg-after.txt` after): before — `ctx.revoked = True` SUCCEEDED (mutable, `revoked=True`); `ctx.scope = "forged scope"` SUCCEEDED. After — both reassignments raise `AttributeError`. Fuller smoke (`/tmp/p009-smoke.py`): copy/deepcopy/pickle copies stay frozen; revocation leaves the context byte-identical while export then rejects; revoking one context does not revoke another; fake contexts cannot revoke or be reported "not revoked".
- **Task B** (same scripts): before — v2.5 resolution with `character_registry=None`, correct requester, approved voice → **resolved `voice-nila-001`, errors `[]`**. After — `voice=None` with the registry error quoted in §3, TASK B.
- **Task C** (`/tmp/p009-repro.py`): v2.5 private dialogue timeline, `validate_timeline_cross_references(manifest, owned_registry)` with no `strict` argument and no requester — BEFORE: `ACCEPTED (vulnerable)`; AFTER: `REJECTED` (`strict v2.5: requesting owner identity is required…; requesting workspace identity is required…`).
- **Task D** (same script): Character owner-a + Voice Profile owner-b, both `shared`/`workspace` in `workspace-a`, requester owner-a/workspace-a, `strict=True` — BEFORE: `ACCEPTED (vulnerable)`; AFTER: `REJECTED` with the exact mismatch error quoted in §3, TASK D. The regression tests pin that the requester is individually authorized to each asset (production `authorize_action == []` for both), so the rejection is proven to come from the VP↔Character binding, not from access denial.

## 5. Tests executed — exact counts

Coordinator full suite, `CF_GITHUB_HEAD=49aa01d70a0b4236e70e287e74b4a2f4f7c6af98 bash tests/run-tests.sh`, exit 0:

- **49 recorded entries, ALL PASS; 37 distinct test IDs; 30 distinct commands; 0 failures, 0 skipped.** (Same entry/ID/command counts as P0-008 — the new P0-009 checks live *inside* existing test files, so no new runner entry was added. The per-file check counts below are where the growth is visible. `tests/last-run.json` is byte-identical to the P0-008 file — SHA-256 `cdb30569…` — because the runner records per-file/per-command PASS/FAIL, not per-check counts; this is expected, not a stale file.)
- Per-file PASS-line counts (verified by the coordinator, 0 FAIL everywhere): `validate-repo.py` PASS; `generate-registries.py --check` OK (15/165/13/12); `test_schemas.py` 91; `test_routing.py` 305; `test_registries.py` 261; `test_performance_semantics.py` 32; `test_character_registration.py` 142 (0 skipped); `test_production_direction.py` 132; `test_private_overlay.py` 28; `test_timeline_manifest.py` **58** (was 34; +24: C1–C11 incl. C8b, D1a/D1b, D2a/D2b, D3, D4a–c, D5, D6, D7, D8); `test_private_voice_security.py` **114** (was 74; +40: (h) `CF-P0-009-SEC` immutability/revocation ~29 checks, (i) `CF-P0-009-SEC` registry fail-closed 9 checks, plus (b13)/(d2)/(d5) updates); `test_modes.py` 32; `test_reports.py` 37. Total per-file PASS lines: 1,232 (+ validate-repo + registries check).
- `bash -n` on `sync-skills.sh`, `setup.sh`, `run-tests.sh`: all OK. `git diff --check`: clean. `bash setup.sh --dry-run`: exit 0 (core-only; `--with-components` end-to-end NOT run, as before).
- New test IDs present in the run: `CF-P0-009-SEC` (security suite), `CF-P0-009-C*` / `CF-P0-009-D*` (timeline suite, e.g. `CF-P0-009-SEC(i8)`, `CF-P0-009-SEC(i9)`, `CF-P0-009-D7`, `CF-P0-009-D8` observed in output). No test reported PASS unless executed with the expected successful result; no skipped test counted as passed; no count invented.

## 6. Files changed

| File | Change |
|---|---|
| `scripts/asset_policy.py` | Tasks A + B: frozen `TrustedAuthorizationContext` (`_frozen` flag, `__setattr__`/`__delattr__` raise `AttributeError`, no `__dict__`, frozen copy/deepcopy/pickle); per-issuance immutable `authorization_id`; separate revocation registry `_REVOKED_AUTHORIZATION_IDS` + `revoke_trusted_authorization_context` / `is_trusted_authorization_revoked`; v2.5 resolver fails closed without a valid Character Registry (missing/non-dict/missing-character/mismatched-ownership) |
| `scripts/timeline_policy.py` | Tasks C + D: strict-by-default tri-state sentinel on `validate_timeline_cross_references`; new explicit `validate_timeline_structural()`; structural body extracted once into `_structural_errors()`; Voice Profile↔Character ownership binding in `_strict_v25_errors()` via `ownerships_match` |
| `tests/test_private_voice_security.py` | Tasks A + B regressions: (h) immutability/revocation, (i) registry fail-closed; (b13) updated (not deleted) to the new revocation path; (d2) spy updated to pass a registry; (d5) no-fallback pin |
| `tests/test_character_registration.py` | Task B: AC-09 now passes `character_registry=registry` (assertion unchanged) |
| `tests/test_timeline_manifest.py` | Tasks C + D regressions: C1–C11, D1a/D1b, D2a/D2b, D3, D4a–c, D5, D6, D7, D8; `full_errors()` + v2.5 fixture check moved to `validate_timeline_structural()` |
| `docs/implementation/CF-WO-P0-009-corrections.md` | This record |
| `~/workspace/consistency-frame-p0-delivery/P0-009-final-report-bn.md` (outside the repo, per the P0-008 precedent) | Final Bengali report (§9 of the work order) — the parent ZIPs it for delivery |
| `CHANGELOG.md` | [Unreleased] P0-009 entry |
| `docs/implementation/BUILD_REPORT_P0.md`, `docs/implementation/build-report.json`, `release-manifest.json`, `docs/implementation/CHECKSUMS.txt`, `docs/architecture/living-architecture-report-v2.4-p0.md` | Regenerated by the coordinator with the repo generators at the code head (see §7) |
| `~/workspace/consistency-frame-p0-delivery/P0-008-final-report-bn.md` + `P0-008-report.zip` (outside the repo) | TASK E correction (see §3) — corrected file, rebuilt ZIP |

Diff vs P0-008 head `ad692d0` (code only, before docs commit): 5 files, +1,069/−114.

## 7. Provenance

- Generators run with `--github-head 49aa01d70a0b4236e70e287e74b4a2f4f7c6af98` (the verified live remote head at order start; the parent re-runs provenance after pushing, per the two-head rule). Manifest `commit` = local code head; `github_branch_head` = remote head at generation time.
- Regen at the code head (before the docs commit), verified by the coordinator: manifest `commit ee29b51`, `github_branch_head 49aa01d7`, **155 files, 0 mismatches vs the working tree**; manifest SHA-256 `08a491e79acd2ae707867620e615d153c10b297375fe09b41a9c8192dd61867a`; build-report SHA-256 `0250041e793e5847865fc768ab998e2a5d42415fbfee2c8ec8d4665999911e50`; BUILD_REPORT_P0.md SHA-256 `f168815dda834c58bf62814235fe809b0f9e63042e5055bb3194705b4f6f2779`; CHECKSUMS.txt 3/3 OK. The manifest is regenerated again after the docs commit (which adds this corrections record itself — final count 156 files); the final manifest hashes live in `docs/implementation/BUILD_REPORT_P0.md` §12 and in the parent's delivery record.
- No circular/self-referential manifest hashing (manifest excludes itself and `CHECKSUMS.txt`).

## 8. Remaining limitations + unresolved decisions

1. **Revocation registry is process-local/in-memory** — a restart clears it; contexts must be re-issued. Persistence is P1 runtime work.
2. **The trusted context is a structural (type) boundary, not cryptographic proof of identity.** A local pure-Python function cannot prove who the human at the keyboard is; passing someone else's IDs to the factory is boundary misuse, not a validator bypass (the validator still checks the issued context against asset owner/workspace/character/voice). Actual trusted app/session identity establishment is P1.
3. **P0 contract ≠ OS-level security.** Nothing here prevents a malicious process running with the same local OS user privileges from manipulating files or code — that is out of scope for a P0 policy contract and is stated, not promised away.
4. **Count reconciliation (109/120 vs 165) still deferred to P1** (unchanged).
5. **VoiceStudio GGUF licence conflict (Apache-2.0 claim vs CC-BY-NC records) still open** — restrictive record governs; needs a VoiceStudio-upstream check (P0-007 item, unchanged).
6. **"646 languages" claim unverified; OpenMontage AGPL-3.0 commercial status `unverified`** (P0-007 items, unchanged).
7. **"End-to-End Script-to-Finished-Video Addendum" still not found on disk** (unchanged).
8. **No verified commercial voice provider exists** (unchanged).
9. The P0-008 PR section currently records no P0-008 last-run SHA — the parent may add `cdb30569…` when applying the TASK E correction.

## 9. P0 vs P1 separation (explicit)

P0-009 hardens architecture, schemas, contracts, authorization logic, validation APIs, tests, and provenance ONLY. Still P1 (not started, not claimed): an authenticated end-user application session / trusted app-session identity establishment; first-run registration UI; persistent registration workflow runtime; image upload/reference retrieval runtime; voice recording / AI voice creation-approval interfaces; reusable per-character voice generation; real image/video provider execution; image-to-video/video-to-video; lip-sync/beak-muzzle articulation generation; facial/body animation execution; camera-motion/focus generation; VoiceStudio/OpenMontage execution handoffs; complete automated script-to-finished-video runtime; revocation persistence across restarts. No server, API backend, cloud database, cloud identity service, or deployment was added. No P1 item was converted to P0 by a contract or mock.

## 10. ADRs (decisions taken this round)

1. **Frozen-object immutability over frozen dataclass:** a hand-rolled `_frozen` flag + `__setattr__`/`__delattr__` guards was chosen because the class already had custom `__init__`/factory semantics and copy/pickle behaviour to pin; a frozen dataclass would have changed construction semantics more broadly. Reassignment raises `AttributeError` (a natural Python immutability signal), not a custom exception, so ordinary callers get the standard error.
2. **Tri-state `strict=None` sentinel over a plain `strict=True` default:** preserves the pinned v2.3 legacy contract (a v2.3 manifest validated with no `strict` argument still passes structurally) while making omission fail closed for every v2.5 manifest. The sentinel distinguishes "caller omitted it" from "caller forced strict".
3. **Revocation as a separate registry, not a context field:** revocation state must never mutate the issued authorization data; the registry keys on the immutable per-issuance `authorization_id`.
4. **Reuse `ownerships_match` for the VP↔Character binding:** one comparison implementation for one rule (the resolver and the timeline validator must never drift apart).
5. **No new runner entry for P0-009:** the new checks live inside the existing security + timeline suites, so the recorded-entry count (49) is unchanged while per-file check counts grew (74→114, 34→58). This is reported explicitly, not hidden.

## 11. Not addressed / out of scope

- `setup.sh --with-components` end-to-end (not run, as in all prior rounds). No new skill added (counts unchanged 109/120, 15 skills). No schema added (no new schema was genuinely needed; the authorization-context contract is a Python class + factory, documented here and in `asset_policy.py`, not a JSON Schema — a schema would falsely suggest an authenticated runtime already exists). The S4/S5 routing wording note (P0-007 §4.4) is unchanged. No voice-call training conversation content is included in any report or repo file (user instruction).
