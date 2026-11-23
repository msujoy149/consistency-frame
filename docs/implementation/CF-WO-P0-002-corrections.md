# CF-WO-P0-002 — Independent-Review Corrections

Hand-written record (not generated). Work order CF-WO-P0-002, branch
`feat/cf-p0-safe-foundations`, 2026-11-22. One section per independent-
review finding (§§1–7): what changed, files, test IDs/gates. The CI
evidence, the GitHub-head/provenance rule and the known remaining
limitations are at the end.

No skill file under `skills/*/SKILL.md` was modified. No push, no
merge, nothing committed by the correction workers — the coordinator
commits.

## §1 — Installer path safety (sync-skills.sh)

- What changed: lexical destination resolution + a canonical check —
  a symlinked destination or a symlinked parent escaping the requested
  tree is refused. Strict fail-closed manifest validation (bad JSON,
  wrong types, duplicate keys, non-64-hex SHA, unsafe relative paths).
  The same `safe_rel` guard on prune/backup/rollback paths; the backup
  directory is canonicalised and confined to the destination's parent;
  bare `rm -rf` of backup directories removed.
- Files: `scripts/sync-skills.sh`.
- Tests: `tests/test_installer_security.sh` (security regression suite,
  added in the same round).
- Commit: `338d0b0` (+ `4200d72` for the tests).

## §2 — Managed-file conflict policy

- What changed: managed files are hashed against the manifest + the
  source; a file differing from both is user-modified and preserved by
  default (`--conflict keep`, conflicts recorded in the last-sync
  JSON). Overwrite only with explicit `--conflict overwrite`. Prune
  never deletes a user-modified stale file.
- Files: `scripts/sync-skills.sh`, `docs/06-installation.md`
  (conflict + backup policy documented).
- Tests: `tests/test_installer.sh` (conflict cases), `tests/test_installer_security.sh`.
- Commits: `338d0b0`, `36999a7`.

## §3 — Atomic backups and ownership

- What changed: timestamp backup directories replaced by
  `mktemp -d run-XXXXXX` with a `.run-owner.json` marker + `.lock`.
  Rollback restores only from the latest valid run directory for this
  destination. `--prune-backups <days>` removes only this
  destination's old, unlocked run directories.
- Files: `scripts/sync-skills.sh`.
- Tests: `tests/test_installer_security.sh` (ownership/backup tests).
- Commits: `338d0b0`, `4200d72`.

## §4 — Human performance schemas

- What changed: emotion intensity bounded 0–10 in all schemas;
  `primary_emotion` closed to joy / sadness / anger / fear / surprise /
  disgust / trust / anticipation / neutral; an open `nuanced_emotion`
  (minLength 1, extensible, no schema change). `duration_seconds` /
  `hold_seconds` strictly positive (`exclusiveMinimum` 0);
  `validate-repo.py` gained `exclusiveMinimum` + `maximum`
  enforcement. `non_verbal_events` (crying, sobbing, laughter, gasp,
  sigh, silence, breathing, trembling, reaction) on performance lines
  and scene beats. Dialogue object `{text verbatim, rewrite_permitted
  default false, rewritten_text}` with the cross-field rule in
  `validate_dialogue_rewrite()`.
- Files: `schemas/performance-plan.json`, `schemas/scene-plan.json`,
  `schemas/script-to-performance.json`, `schemas/shot-plan.json`,
  `schemas/README.md`, `scripts/validate-repo.py`,
  `tests/fixtures/performance-plan-valid.json`,
  `tests/fixtures/scene-plan-valid.json`.
- Tests: `tests/test_performance_semantics.py`, gates
  CF-P0-PERF-001..005 (registered in `tests/run-tests.sh`).
- Commit: `5676cf6`.

## §5 — Learning authorization: propose vs apply

- What changed: `may_propose_skill_patch` (REFERENCE_LEARN_AND_UPDATE
  + explicit instruction; a proposal file under
  `.consistency-frame/proposals/`, never a canonical write) split from
  `may_apply_skill_patch` (full authorization contract: `granted_by` +
  scope + branch + explicit authorisation).
  `may_mutate_canonical_skills` now requires both propose permission
  and a full apply authorization; the intake result reports both
  permissions (apply is always false from intake alone).
  `reference-review.json`: `proposal_only` (default true),
  `apply_skill_patch`, authorization object;
  `mutates_canonical_skills` stays enum `[false]`.
- Files: `scripts/asset_policy.py`, `schemas/reference-review.json`,
  `docs/implementation/P0_UPDATED_IMPLEMENTATION_PLAN.md` (§8).
- Tests: CF-P0-LEARN-001 in `tests/test_modes.py` +
  `tests/test_schemas.py`.
- Commit: `ebd92d4`.

## §6 — Companion capability accuracy

- What changed: `architecture/COMPANION_CAPABILITY_REGISTRY.yaml`
  now records a closed `evidence_level` per capability AND per
  interface, replacing the old `status` field
  (`VERIFIED_ON_DISK` / `VERIFIED_BY_RUN` / `NOT_VERIFIED`), which
  conflated "present on disk" with "verified" and let a single
  "verified" total hide how little was actually exercised. The four
  levels: `upstream_inspected_pinned_commit` (claim inspected in the
  companion upstream at the pinned commit — the claim itself is NOT
  independently verified), `present_locally` (in `components/`, not
  exercised), `exercised_recorded_run` (must carry a `run_reference`:
  date + what was run + where it is recorded), `production_verified`
  (only with a `production_record` — expect zero; none exists).
- Reclassification (20 capabilities): 3 `exercised_recorded_run` —
  OmniVoice TTS generation (Bengali/English/Hindi, 2026-11-12/13,
  user verdict recorded), zero-shot voice cloning (three unnamed test
  voices, 2026-11-13 sound test, user verdict "Good"), OpenMontage
  `make setup` / `make preflight` (2026-11-12, not re-run); 16
  `present_locally`; 1 `upstream_inspected_pinned_commit` — the
  VoiceStudio "646 languages" README headline (inspected at the pinned
  commit `2f2f5a9b0e982c6147efc6baaeae62936f29b79b`; the count itself
  is unverified — only Bengali, English, Hindi were exercised by run);
  0 `production_verified`. The old single "verified" total is gone —
  the living report counts by evidence level (see §7). The same closed
  set applies to the 9 interfaces (1 exercised — the VoiceStudio HTTP
  API, used in the recorded 2026-11-12/13 runs — 8 present locally).
- Core-only install: the registry header and `docs/06-installation.md`
  (near the core-only text) now state explicitly that a core-only
  install (`bash setup.sh`, the default) does NOT include VoiceStudio
  or OpenMontage — they are installed only with the opt-in
  `bash setup.sh --with-components`.
- Pins (unchanged, now enforced in two places): VoiceStudio
  `2f2f5a9b0e982c6147efc6baaeae62936f29b79b`, OpenMontage
  `fecb9a1e3cc23ef84de30b272059457a427f16f8` — matching `setup.sh`.
- Files: `architecture/COMPANION_CAPABILITY_REGISTRY.yaml`,
  `scripts/validate-repo.py` (check 8), `scripts/generate-report.py`
  (companion counting), `tests/test_routing.py`,
  `docs/06-installation.md`.
- Tests: gate CF-P0-ROUTING-004 (evidence_level from the closed set;
  every `exercised_recorded_run` has a run reference; pinned commits
  match the repo pins; the 3/16/1/0 distribution; zero
  `production_verified`), plus the updated CF-P0-ROUTING-003 companion
  check. Validator check 8 enforces the same rules.

## §7 — Reports and release provenance

- What changed: `scripts/generate-build-report.py` and
  `scripts/generate-report.py` both accept `--github-head <sha>` with
  a `CF_GITHUB_HEAD` env-var fallback; without either they default to
  the current git HEAD ("the current recorded head"). Both record
  `github_branch_head: fcf311ef79c5f10a4248f026a5f667109c584831` in the
  regenerated `docs/implementation/build-report.json` and
  `release-manifest.json` (schemas updated to allow the new field;
  `build-report.json` also carries a `ci` object — see CI evidence
  below).
- All obsolete "CI missing / CI not run" statements removed: the CI
  entry is dropped from the build report's `not_run` list, §4 of the
  generated report now carries the real CI evidence, the living
  report's "CI workflow" paragraph is replaced, and the same wording
  is gone everywhere else it appeared. The `setup.sh
  --with-components` NOT RUN entries are kept — they are still true.
- GitHub section (§5 of the build report) now filled in: branch
  `feat/cf-p0-safe-foundations`, base `main` /
  `e1571db68ed87fb973c45960a4a3e27e09ba0d06`, local code head, GitHub
  head `fcf311e`, draft PR
  https://github.com/msujoy149/consistency-frame/pull/1, push status
  (20 snapshot commits + 1 web commit).
- `release-manifest.json` is excluded from its own `files` list (a
  file cannot contain its own hash). It is kept in
  `build-report.json`'s `changed_files`, which is a list of names, not
  hashes — the distinction is documented in the new Provenance §12.
- Detached checksums: `generate-build-report.py` also writes
  `docs/implementation/CHECKSUMS.txt` (SHA-256 + byte count of
  `release-manifest.json`, `build-report.json` and `BUILD_REPORT_P0.md`
  as generated, before commit; header states the ZIP hash lives in
  the delivery message).
- Provenance §12 (new, generated) in `BUILD_REPORT_P0.md` explains
  the two-head rule — see below.
- Files: `scripts/generate-build-report.py`,
  `scripts/generate-report.py`, `schemas/build-report.json`,
  `schemas/release-manifest.json`, `docs/implementation/BUILD_REPORT_P0.md`,
  `docs/implementation/build-report.json`, `release-manifest.json`,
  `docs/implementation/CHECKSUMS.txt` (new),
  `docs/architecture/living-architecture-report-v2.4-p0.md`,
  `tests/test_reports.py` (new), `tests/run-tests.sh`,
  `CHANGELOG.md` ([Unreleased] P0-002 entry).
- Tests: gates CF-P0-REPORT-001 (flag/env/default precedence for both
  generators; `github_branch_head` recorded in both JSONs),
  CF-P0-REPORT-002 (manifest self-exclusion; `changed_files` keeps the
  manifest name; CHECKSUMS.txt matches the generated files),
  CF-P0-REPORT-003 (CI evidence current, no obsolete CI text,
  `--with-components` NOT RUN kept, Provenance §12 present, living
  report counts companions by evidence level),
  CF-P0-REPORT-004 (both generated JSONs validate against their
  schemas). All four run `tests/test_reports.py` via
  `tests/run-tests.sh`.

## CI evidence

- Remote CI PASSED on GitHub branch head
  `fcf311ef79c5f10a4248f026a5f667109c584831` — 2/2 checks, run
  https://github.com/msujoy149/consistency-frame/actions/runs/45046203236
  (draft PR https://github.com/msujoy149/consistency-frame/pull/1).
- Every "CI missing / CI not run" statement in the repo was obsolete
  once that run passed and has been removed (see §7). The
  post-corrections CI run (on the new head after this package is
  pushed) is NOT claimed anywhere; the parent checks it after the push.

## GitHub-head / provenance rule

- The manifest records the GitHub head of the code it describes
  (`github_branch_head`). Pushing the regenerated manifest itself
  advances the branch head by one docs-only commit, and the delivery
  message states that final head. The manifest never tries to predict
  its own push SHA.
- Two heads, two meanings: `head_commit` / `commit` is the local code
  head at generation time; `github_branch_head` is the remote head
  recorded for the package. Both are in `build-report.json` and
  `release-manifest.json`.
- The ZIP hash cannot live inside the committed files: the ZIP is built
  from the final head after commit. It lives in the delivery message
  (and `CHECKSUMS.txt` says so in its header).

## Known remaining limitations

- `setup.sh --with-components` end-to-end: NOT RUN (would download
  ~5 GB + ~1 GB deps; failure reporting is unit-tested; the live run
  is still honest NOT RUN).
- Remote CI on the NEW head (after the P0-002 corrections are pushed):
  NOT RUN — the parent checks it after the push.
- No `production_verified` companion claim exists, and none may be
  added without a production record (validator + tests enforce this).
- The VoiceStudio "646 languages" headline count remains unverified
  (inspected at the pinned commit only); only Bengali, English, Hindi
  were exercised by run.
- Historical records keep the old vocabulary: the v2.3 living report
  (retained baseline), `docs/implementation/BRAIN_ARCHITECTURE_AUDIT.md`
  and `docs/implementation/P0_UPDATED_IMPLEMENTATION_PLAN.md` still
  say `NOT_VERIFIED` / `VERIFIED_ON_DISK` / `VERIFIED_BY_RUN` where
  they describe the registry as it was at v2.4 time. They are records
  of that revision, not the current canonical vocabulary — the
  registry, validator, tests and generated reports use
  `evidence_level` (see §6).
- Registry reconciliation (165 derived features vs the historical
  109/120 claim), adapter conformance, the private-overlay runtime
  adapter, research-register reconciliation, and the P1 runtimes
  (skill-routing engine, script-to-performance runtime) remain
  deferred as recorded in the build report §9.
