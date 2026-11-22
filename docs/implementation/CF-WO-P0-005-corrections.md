# CF-WO-P0-005 — Final Evidence & Failure-Diagnostic Corrections

## Objective

Work order CF-WO-P0-005 (2026-11-22). Two focused corrections to the
P0-004 implementation: (1) reconcile the generated reports with the
actual successful post-push GitHub CI evidence on final PR head
`8879123`; (2) correct the misleading recovery-backup message when
no files were changed and final metadata persistence fails. No
installer or architecture redesign; no new features.

Branch: `feat/cf-p0-safe-foundations`. PR #1 stays open and Draft;
no merge; no P1; no server/API/database; no skill changes.

## 1. Root cause — stale CI evidence

The generated reports (`docs/implementation/BUILD_REPORT_P0.md`,
§4/§5/§8/§12, and the living architecture report) still named the
P0-002-era CI record — head `fcf311e`, run
`https://github.com/msujoy149/consistency-frame/actions/runs/45046203236`
— as the current evidence, and said "the post-corrections CI run
will be checked by the parent after the push". That was true when the
P0-004 package was generated, but the run has since happened and
passed: on final PR head
`88791231caa03e8fb75a3499beeb21d1dd64a906`, push run #37
(`https://github.com/msujoy149/consistency-frame/actions/runs/45055643056`)
and PR run #38
(`https://github.com/msujoy149/consistency-frame/actions/runs/45055649820`),
both SUCCESS, 2/2 checks. The `p0-test-results` artifact (artifact
ID `14766603267`) holds 43 recorded test-run entries, 31 distinct
test IDs, 24 distinct command strings, all PASS, every listed
command exit 0; its `last-run.json` is byte-for-byte identical to
the P0-004 ZIP's `tests/last-run.json` (independently verified, per
the work order). The reports therefore understated the evidence
actually on file, and the "will be checked later" wording was stale.

The same staleness was in `docs/implementation/CF-WO-P0-004-corrections.md`
§7 (Validation), whose last bullet said "remote CI on the new head
(parent checks after push)" under NOT RUN — written before that CI
run existed.

## 2. Root cause — misleading recovery-backup message

`scripts/sync-skills.sh` creates a content backup only for replaced
or pruned files (the backup loop copies `$PLAN_CHANGED` +
`$APPLIED_PRUNE` from the destination into the run directory; new
files are never backed up — there is no previous content to save).
Three failure diagnostics nevertheless claimed a backup was
preserved/restored unconditionally:

1. **No-change final metadata failure** (previously the last lines
   of the script): `n_new + n_changed + pruned = 0`, so the run
   directory holds only the owner marker (`.run-owner.json`) and
   the lock (`.lock`) — no content backup exists — yet the message
   said "recovery backup preserved at $RUN_DIR (run $RUN_ID)" and
   the summary line ended "(backup preserved)". Exit code 1 was
   correct; the words were not.
2. **Earlier `failed=1` path** (file-operation failure): the message
   said "restoring from this run's backup $RUN_DIR" even when the
   run failed while installing only new files, or before any backup
   was made — in which case there is nothing to restore. Its nested
   error on a failed result write likewise said "recovery backup
   preserved at $RUN_DIR".
3. **New-only PARTIAL case** (same class, found while fixing 1–2):
   changes applied + metadata failure with only new files installed
   (`n_new > 0`, `n_changed = pruned = 0`) also creates no content
   backup, yet the PARTIAL diagnostic said "recovery backup
   preserved". The PARTIAL behaviour itself (exit 2, backup
   preserved when one exists) is unchanged — only the words are
   now conditional on a backup actually existing.

## 3. Exact fix

### 3.1 Reports — CI evidence (generator, not hand-typed)

`scripts/generate-build-report.py` and `scripts/generate-report.py`
(the living report) carried the stale record as hardcoded template
text; `tests/test_reports.py` asserted it. All three were updated
together so regeneration and CI stay consistent:

- New latest-evidence constants in `generate-build-report.py`:
  `CI_HEAD = 88791231caa03e8fb75a3499beeb21d1dd64a906`,
  push run #37 (`.../runs/45055643056`), PR run #38
  (`.../runs/45055649820`), artifact `p0-test-results`
  (artifact ID 14766603267). The old `fcf311e` record is kept as
  `CI_HIST_HEAD` / `CI_HIST_RUN_URL`, labelled historical.
- `BUILD_REPORT_P0.md` §4 now leads with the verified #37/#38
  evidence (43 / 31 / 24 from the artifact, byte-identical
  `last-run.json`) and lists `fcf311e` as the historical record.
  §5 "GitHub branch head" now uses the recorded `{github_head}`
  instead of the stale CI head constant (the old text also carried
  a stale "20 snapshot commits" count). §8's result line and §12's
  CI bullet cite #37/#38; §12 adds a historical-runs line
  (`fcf311e`, `59f562a` #29/#30, `b30d75e` #19/#20) and keeps the
  honest two-phase note: the CI run for the corrections in *this*
  package is a separate event checked by the parent after the push;
  it is NOT claimed here. A P0-005 bullet was added to §12.
- The P0-004 §12 bullet's counts were hardcoded to the verified
  P0-004 evidence (43 / 31 / 24): the bullet previously reused the
  computed variables, which would have rendered the *new* counts
  on this regeneration and misstated the historical package.
- `build-report.json`'s `ci` object now records head `8879123`,
  `run_url` = push run #37, and a note naming PR run #38, the
  artifact, and the two-phase rule (schema unchanged;
  `additionalProperties: false` still holds).
- The living report's CI sentence now cites #37/#38 + the artifact
  counts, with `fcf311e` retained as the historical record.
- `tests/test_reports.py` (CF-P0-REPORT-003) now expects the #37
  run URL in both reports and in `build-report.json`'s `ci` object;
  the obsolete-phrase list is unchanged and still passes.
- `CF-WO-P0-004-corrections.md` §7: the outdated "remote CI NOT
  RUN" bullet is replaced by an explicit local-vs-remote
  distinction — local checks completed before push, then remote
  GitHub CI completed after push (verified by the parent on
  2026-11-22, NOT claimed before it ran), with the #37/#38 links
  and the artifact evidence. No claim is made that Muse ran the
  remote CI before it was actually run.

### 3.2 Installer — accurate backup diagnostics

`scripts/sync-skills.sh`. One new helper, used by all three
diagnostic paths:

```bash
run_dir_has_content_backup() {
  [ -n "$(find "$RUN_DIR" -type f ! -name '.run-owner.json' ! -name '.lock' -print -quit 2>/dev/null)" ]
}
```

- **No-change path:** FAILED, exit 1 (unchanged). The message now
  reads "no files were changed, but the final metadata record
  could not be written; no content backup was created; run record
  retained at $RUN_DIR (run $RUN_ID)", and the summary line ends
  "(no files changed; run record retained)". The run directory is
  retained (removal happens only after a successful metadata
  write), and is now described accurately as a retained run
  record, not a backup.
- **Failed=1 path:** the "restoring from this run's backup" line
  is printed only when a content backup exists; otherwise the
  message says "no content backup was created for this run,
  nothing to restore". The nested result-write error is likewise
  conditional ("recovery backup preserved" vs "no content backup
  was created for this run; run record retained").
- **PARTIAL path:** "recovery backup preserved" is printed only
  when a content backup exists; otherwise the diagnostic says "no
  content backup was created for this run; run record retained".
  Exit 2 and the preservation itself are unchanged.
- Exit-code contract preserved: 0 = SUCCESS, 2 = PARTIAL,
  1 = FAILED. No error path prints a false SUCCESS.

## 4. Regression tests — SEC-METADATA-06 and SEC-METADATA-07

Extended `tests/test_installer_metadata_failure.sh` (mode argument:
`changed` | `no-change` | `failed-no-backup`; default `changed`),
with two new runner entries in `tests/run-tests.sh`
(`CF-P0-SEC-METADATA-06`, `CF-P0-SEC-METADATA-07`). The existing
changed-file SEC-METADATA-05 case is intact and still passes.

### SEC-METADATA-06 — no-change metadata failure (13 checks, all PASS)

Procedure: isolated source + destination; successful initial
install; same sync again with no source changes (no new, changed
or pruned files); `.consistency-frame-last-sync.json` replaced by
a directory; installer run with stdout/stderr/exit captured.
Assertions: exit exactly 1 (and not 0); no false `Skill sync
SUCCESS`; reports FAILED; diagnostic confirms no files were
changed; diagnostic says no content backup was created; diagnostic
says the run record is retained; diagnostic does NOT contain
"backup preserved" or "recovery backup"; the run metadata
directory named in the diagnostic is retained, its owner marker
is valid for this destination, and it holds no content backup
files (only `.run-owner.json` + `.lock`); no stale `.cf-atomic-*`
temps.

### SEC-METADATA-07 — failed=1 path with no content backup (8 checks, all PASS)

Procedure (covers the reviewed failed=1 path): separate isolated
fixtures; the destination holds `skill-a` as a regular file, so
the copy cannot create its directory (file-operation failure, no
content backup), and `.consistency-frame-last-sync.json` is a
directory (result-write failure). Assertions: exit exactly 1 (and
not 0); no false `Skill sync SUCCESS`; diagnostic says "no content
backup was created for this run, nothing to restore"; nested
diagnostic says "no content backup was created for this run; run
record retained"; diagnostic does NOT contain "restoring from this
run's backup" or "recovery backup"; no stale `.cf-atomic-*` temps.

### Discrimination proof

Both new tests were run against pre-fix code (the
`scripts/sync-skills.sh` fix stashed): SEC-METADATA-06 fails 7 of
its 13 checks (the exit-code checks pass — exit was already 1 —
but every backup-accuracy check fails); SEC-METADATA-07 fails 4
of its 8 checks. Both pass fully on the fixed code. SEC-METADATA-05
passes on both — expected: the changed-case behaviour and wording
were fixed in P0-004 and are unchanged by P0-005.

SEC-01..08, SEC-MANIFEST-01..04 and CF-P0-ATOMIC-001..006 are
untouched and passing.

## 5. Test evidence (generated, not hand-typed)

- `bash tests/run-tests.sh` → **45 recorded test-run entries,
  all PASS, exit 0** (33 distinct test IDs, 26 distinct command
  strings, every listed command exit 0). The count is 45, not 44
  or 43: the two new runner entries each add one recorded entry,
  one distinct ID and one distinct command string
  (`bash tests/test_installer_metadata_failure.sh no-change`,
  `bash tests/test_installer_metadata_failure.sh
  failed-no-backup`); the `bash -n` entry for the test file already
  existed, so no new syntax-check entry was needed.
- `build-report.json`'s `tests` list is the generator's documented
  dedup by test ID (33 entries), not an error.
- The CI artifact evidence (43 / 31 / 24) describes the CI run on
  head `8879123` (the P0-004 package), not this package's local
  suite — the two counts differ because the local suite has grown
  by the two new tests since that CI run. They are different
  measurements of different runs and are labelled as such wherever
  they appear together.

## 6. Validation

- `bash -n scripts/sync-skills.sh`, `bash -n setup.sh`,
  `bash -n tests/run-tests.sh`,
  `bash -n tests/test_installer_metadata_failure.sh` → all OK.
- `python3 scripts/validate-repo.py` → PASS (schemas,
  skill_frontmatter, registries, private_overlay, secret_scan,
  absolute_claims, yaml_records).
- `python3 scripts/generate-registries.py --check` → CHECK OK.
- `bash tests/run-tests.sh` → **45 recorded test-run entries,
  all PASS, exit 0** (33 distinct test IDs, 26 distinct command
  strings, every listed command exit 0). Full suite run time
  ~50 s; no timeout, no skipped or incomplete run.
- `bash setup.sh --dry-run` → exit 0, `Setup SUCCESS:
  skills=SUCCESS voicestudio=SKIPPED openmontage=SKIPPED`.
- `bash setup.sh` core-only → exit 0, same SUCCESS line, 15
  skills synced.
- `git diff --check` → clean.
- NOT RUN (honest): `setup.sh --with-components` end-to-end;
  remote CI on the new head (parent checks after push).
- CI artifact download: NOT performed by the coordinator. The
  GitHub MCP toolset exposes 46 tools and none of them downloads
  Actions artifacts (no artifact/workflow-run/download tool), and
  local git has no credentials — there is no supported route from
  this environment. The artifact evidence cited in §1 and in the
  generated reports rests on the work order's statement that it
  was independently verified byte-identical; the parent re-checks
  the artifact after the push (see the delivery steps).

## 7. Files changed

- `scripts/sync-skills.sh` — the fix (§3.2): `run_dir_has_content_backup()`
  helper; accurate diagnostics in the no-change FAILED path, the
  failed=1 path (including its nested result-write error), and the
  new-only PARTIAL case. Exit codes and preservation behaviour
  unchanged.
- `tests/test_installer_metadata_failure.sh` (extended) — mode
  argument + SEC-METADATA-06 (13 checks) + SEC-METADATA-07
  (8 checks); SEC-METADATA-05 intact.
- `tests/run-tests.sh` — two new `run_one` entries
  (`CF-P0-SEC-METADATA-06`, `CF-P0-SEC-METADATA-07`) so both run
  in GitHub Actions.
- `scripts/generate-build-report.py` — latest CI evidence
  constants (#37/#38, artifact 14766603267), historical `fcf311e`
  record retained; §4/§5/§8/§12 rewritten; `ci` JSON object
  updated; P0-004 §12 bullet counts hardcoded to the verified
  43 / 31 / 24 (they previously reused the computed variables,
  which would have rendered the new counts on regeneration);
  P0-005 bullet added.
- `scripts/generate-report.py` — living report CI sentence
  updated to #37/#38 + artifact counts, `fcf311e` retained as
  historical.
- `tests/test_reports.py` — CF-P0-REPORT-003 now expects the #37
  run URL in both reports and in `build-report.json`'s `ci`
  object.
- `docs/implementation/CF-WO-P0-004-corrections.md` — §7
  rewritten: local-vs-remote distinction, #37/#38 links and
  artifact evidence; "remote CI NOT RUN" wording removed.
- `docs/implementation/CF-WO-P0-005-corrections.md` (new) — this
  record.
- `CHANGELOG.md` — [Unreleased] P0-005 entry.
- Regenerated with `--github-head 8879123`:
  `BUILD_REPORT_P0.md`, `build-report.json`,
  `release-manifest.json`, `CHECKSUMS.txt`, living report,
  `tests/last-run.json`.

## 8. Provenance

- Regenerated with `--github-head
  88791231caa03e8fb75a3499beeb21d1dd64a906` (the current remote
  head, i.e. the P0-004 final PR head whose CI is recorded above).
  Code head: `19e1a13e7c805f74e15940f44c1bb8944ec2f019` (the fix
  commit; the docs commit head is in the delivery report).
- The manifest records the GitHub head of the code it describes;
  pushing the regenerated manifest advances the branch head by one
  docs-only commit, and the delivery message states the final head
  (two-head rule, `BUILD_REPORT_P0.md` §12). The manifest excludes
  itself and `docs/implementation/CHECKSUMS.txt` from its own file
  list, and all listed hashes verify against the working tree (see
  the delivery report for the count).
- The `ci` object in `build-report.json` records the verified CI
  run on head `8879123` (push run #37); the CI run for the P0-005
  corrections themselves is a separate event, checked by the
  parent after the push — it is NOT claimed here.
