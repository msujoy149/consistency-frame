# CF-WO-P0-004 — Post-Review Corrections

## Installer Failure Handling, Test Evidence & Release Provenance

Work order CF-WO-P0-004 (2026-11-22). Independent review of the
P0-003 package (`CONSISTENCY_FRAME_P0_003_INDEPENDENT_REVIEW_BN.md`)
found one reproducible release-blocking issue (P0-003-01) and two
documentation/provenance inconsistencies (P0-003-02, P0-003-03).
This record corrects all three. The review document matches the
work-order text exactly; no requirement beyond it was added.

Branch: `feat/cf-p0-safe-foundations`. PR #1 stays open and Draft;
no merge; no P1; no server/API/database; no skill changes.

## 1. Root cause — P0-003-01 (false SUCCESS)

`scripts/sync-skills.sh` called `write_result_json()` — the function
that persists the final sync status record
(`.consistency-frame-last-sync.json`) — without checking its return
code, at the final successful-sync path (previously line 880).

The atomic-write helper itself was correct: it propagates an
`os.replace()` failure. The shell caller ignored it. The script runs
under `set -uo pipefail`, **not** `set -e` — that is why the
unchecked call fell through instead of aborting. The installer then
printed `Skill sync SUCCESS` and exited `0`.

The reviewer reproduced it exactly: with
`.consistency-frame-last-sync.json` replaced by a directory, the
atomic write fails with `IsADirectoryError` on `os.replace()`;
the skill was installed and the manifest was written, but the
installer still reported `Skill sync SUCCESS` and exited `0`.

The same unchecked pattern existed at the FAILED path (previously
line 827), where the exit code happened to stay `1` by luck — the
`exit 1` after the call masked it — but the return code was never
checked there either.

A second ordering defect: the final backup cleanup removed an empty
run directory *before* final status persistence had succeeded. A
run holding a real backup was already kept (the emptiness check),
but the ordering was wrong in principle — a metadata failure must
never be able to discard a backup that may be required for recovery.

## 2. Exact fix

`scripts/sync-skills.sh`, final path (and FAILED path). No other
installer behaviour changed; the exit-code contract is preserved
(`0` = SUCCESS, `2` = PARTIAL, `1` = FAILED).

1. **Every `write_result_json()` call is now checked explicitly.**
   `set -e` is not relied on as the only solution — the return
   status is handled in an `if` in both places. Python exceptions
   are not suppressed and atomic-write errors are not hidden: the
   traceback still reaches stderr, followed by the diagnostic.
2. **Final path, success:** the metadata write succeeds, then the
   (possibly empty) run directory is dropped, then `Skill sync
   SUCCESS` is printed and the installer exits `0` (or `2` for the
   pre-existing PARTIAL path).
3. **Final path, failure, changes applied:** if files were already
   installed, changed or pruned (`new + changed + pruned > 0`) but
   the final status record cannot be persisted, the installer
   reports PARTIAL and exits `2`, with a clear diagnostic:
   `PARTIAL: sync changes were applied (new=… changed=… pruned=…)
   but the final metadata record could not be written; recovery
   backup preserved at <RUN_DIR> (run <RUN_ID>)`.
4. **Final path, failure, no changes:** if the failure occurs
   before any changes are applied, the installer preserves FAILED
   semantics and exits `1`, with the same style of diagnostic.
5. **No error path can print a false SUCCESS.** The `Skill sync
   SUCCESS` line is reachable only after the metadata write
   returned success.
6. **Backup preservation:** the decision whether a run directory
   may be dropped is now made *before* the metadata write, but the
   removal happens only *after* a successful metadata write. On
   metadata failure the run directory and its valid owner marker
   are preserved, and the result message refers to that preserved
   backup (`run_id=<RUN_ID> (backup preserved)`). Normal cleanup
   for successful operations is unchanged where safe.
7. **FAILED path:** the result write is checked explicitly; a
   failed record write adds a diagnostic only — the exit stays `1`
   and the restored backup is preserved.

Investigated and deliberately left out of scope: if
`write_manifest()` fails, the installer already exits `1` (honest
FAILED, no false SUCCESS) without writing a result record and
without rolling back — that path was not flagged by the review and
is not changed here. `setup.sh` maps any non-zero sync exit to a
setup FAILED (pre-existing, unchanged): a PARTIAL sync (exit 2)
makes setup report FAILED, never SUCCESS. The repo build tools'
plain `open()` writes and the helper's file-only (not directory)
fsync remain out of scope, as recorded for P0-003.

## 3. Regression test — SEC-METADATA-05

`tests/test_installer_metadata_failure.sh` (new), wired into
`tests/run-tests.sh` (new `P0-SHELL` syntax entry + `run_one
"CF-P0-SEC-METADATA-05"` entry) so it runs in the GitHub Actions
P0 CI workflow. It is a true installer integration test: it
executes `scripts/sync-skills.sh` and verifies externally visible
behaviour, not just the Python helper.

Procedure: isolated source skill + destination; initial successful
install of skill-a v1; modify the source to v2 so the next sync
must replace the installed file (and back the original up);
replace `.consistency-frame-last-sync.json` with a directory to
force the final metadata replacement to fail; run the installer
and capture stdout, stderr and exit code.

13 checks, all PASS:

- installer returns exit code `2` (PARTIAL, changes applied);
- installer does NOT return `0` on metadata failure;
- installer does NOT print a false `Skill sync SUCCESS`;
- installer reports PARTIAL;
- diagnostic explains the failed final metadata write;
- diagnostic says the recovery backup is preserved;
- diagnostic says the sync changes were applied;
- updated skill content (v2) is installed;
- previous content (v1) is recoverable from the preserved backup;
- backup run directory still exists;
- backup owner marker is valid for this destination (`dest_dir`
  matches, `run_id` matches the directory name, `created_utc`
  present);
- no stale `.cf-atomic-*` temp files remain after the failed
  operation;
- setup check: the initial install succeeds.

Discrimination proof: run against the pre-fix code (fix stashed),
the test FAILS with 7 failures — exit `0` and a false `Skill sync
SUCCESS`, exactly the reported bug — and passes 13/13 on the fixed
code. Existing regression tests are untouched and still passing:
SEC-01..SEC-08, SEC-MANIFEST-01..04, CF-P0-ATOMIC-001..006.

## 4. Test evidence reconciliation — P0-003-02

The P0-003 docs disagreed with the recorded evidence. Root cause,
found by reading `tests/run-tests.sh` and the generators (not
guessed):

- The P0-002 suite had 35 recorded entries. P0-003 added **6**
  runner entries: 1 new `bash -n
  tests/test_installer_manifest_security.sh`, 4 SEC-MANIFEST, 1
  ATOMIC — 35 + 1 + 4 + 1 = **41**.
- The P0-003 corrections doc §5 said "40/40 (35 previous + 4
  SEC-MANIFEST + 1 ATOMIC)": a hand-count error that omitted the
  new `bash -n` entry. `BUILD_REPORT_P0.md` §12 copied the same
  "40/40" text (it is a static template string in
  `scripts/generate-build-report.py`, not computed).
- The `tests/last-run.json` committed with the P0-003 fix was also
  stale — 35 entries — because it was recorded before the new
  runner entries were added; it was re-recorded with 41 entries in
  the docs commit. The GitHub Actions artifact for the same head
  independently records 41 rows, all PASS.
- `build-report.json`'s `tests` list holds 30 entries at P0-003:
  that is the generator's documented deduplication by test ID
  (30 distinct IDs), not an error — but the prose "40/40" matched
  neither the 41 entries, the 30 distinct IDs, nor the 22 distinct
  command strings.

Corrections made here:

- `docs/implementation/CF-WO-P0-003-corrections.md` §5 now states
  the true P0-003 counts with this explanation.
- `scripts/generate-build-report.py` §12 now computes the counts
  from `tests/last-run.json` at generation time (entries, distinct
  IDs, distinct commands) instead of carrying a hand-typed total;
  the P0-003 bullet keeps its verified historical numbers
  (41 entries / 30 distinct IDs / 22 distinct commands) and a
  P0-004 bullet states the current package's computed counts.
- `CHANGELOG.md`'s P0-003 entry is corrected the same way.
- The PR #1 description is updated by the parent with the final
  numbers (see the delivery report).

Precise wording used everywhere now: **recorded test-run entries**,
**distinct test IDs**, **distinct command strings**,
**individual assertions** (the checks inside a test script, e.g.
SEC-MANIFEST-01 has 7, the ATOMIC suite 18, SEC-METADATA-05 has
13). Test-run rows are never represented as unique commands or
individual assertions.

Current package (this correction), from the generated evidence:

- **43 recorded test-run entries, all PASS** (41 previous + 1 new
  `bash -n tests/test_installer_metadata_failure.sh` + 1
  SEC-METADATA-05). The count is 43, not 42 — the new test file
  adds a syntax-check entry as well as its run entry.
- **31 distinct test IDs, 24 distinct command strings**; each
  listed command returned exit `0`.
- The PR body already said 41/41 for P0-003 while the corrections
  doc and build report said 40/40 — the PR body was right; the
  docs were wrong. Both now agree.

## 5. Stale provenance — P0-003-03

`docs/implementation/CF-WO-P0-003-corrections.md` §6 named an
earlier intermediate head as the regenerated release. It now
states the final regenerated release: regenerated with
`--github-head 43d4fd33a59a19c57cabbb74b14492a2acaf9343`; the
release manifest records the code head it describes
(`5e25545a3d803b7611b8865d453f4c88f524b525`) and that GitHub head;
pushing the regenerated manifest advanced the branch head by one
docs-only commit, and the final PR head after that push was
`59f562afb0d9d7c5cab14cd6d878b49d85d89449`. The two heads have
different meanings (see `BUILD_REPORT_P0.md` §12, two-head rule).
No future SHA was invented, predicted or hardcoded.

For this correction the reports are regenerated with
`--github-head 59f562afb0d9d7c5cab14cd6d878b49d85d89449` (the
current remote head); the parent re-runs provenance after pushing
with the new head (two-phase, two-head rule).

## 6. Independent-review verification facts (P0-003 package)

Recorded from the review document, for the delivery report:

- Delivered P0-003 ZIP verified independently: SHA-256
  `3808a624a96e0473bde3d8e1e81839f4fa4e9063464bff3ef4ce01ca0fdb12f7`
  (matches ours), 468 KB, 168 entries, `unzip -t` PASS, no
  symlinks, largest file `registry/features.json` 90,024 B;
  manifest 96/96 hashes + bytes match; detached checksums 3/3
  match.
- CI on `59f562a`: push run #29, SUCCESS,
  https://github.com/msujoy149/consistency-frame/actions/runs/45052729856
  and PR run #30, SUCCESS,
  https://github.com/msujoy149/consistency-frame/actions/runs/45052735029.
  The `p0-test-results` artifact was downloaded and inspected: 41
  rows, all PASS, exit 0.
- What passed independently: `test_atomic_write.py` 18 assertions;
  SEC-MANIFEST-01/02/04 passed; SEC-MANIFEST-03 partially (their
  run timed out, the tested assertions passed); all core validation
  commands PASS individually. Their full local `run-tests.sh`
  TIMED OUT in their environment — not a failure, not counted as
  a pass. A timeout is never labelled PASS.
- Final decision: do not merge, keep Draft. Next work limited to
  the six points in the review §7 (which match this work order).

## 7. Validation

- `bash -n scripts/sync-skills.sh`, `bash -n setup.sh`,
  `bash -n tests/run-tests.sh`,
  `bash -n tests/test_installer_metadata_failure.sh` → all OK.
- `python3 scripts/validate-repo.py` → PASS (schemas,
  skill_frontmatter, registries, private_overlay, secret_scan,
  absolute_claims, yaml_records).
- `python3 scripts/generate-registries.py --check` → CHECK OK.
- `bash tests/run-tests.sh` → **43 recorded test-run entries,
  all PASS, exit 0** (31 distinct test IDs, 24 distinct command
  strings, every listed command exit 0). Full suite run time
  ~80 s; no timeout, no skipped or incomplete run.
- `bash setup.sh --dry-run` → exit 0, `Setup SUCCESS:
  skills=SUCCESS voicestudio=SKIPPED openmontage=SKIPPED`.
- `bash setup.sh` core-only → exit 0, same SUCCESS line, 15
  skills synced.
- `git diff --check` → clean.
- Local checks completed before push: everything above in this
  section (43 recorded test-run entries, all PASS; `setup.sh`
  core-only and `--dry-run` SUCCESS; `git diff --check` clean).
- Remote GitHub CI completed after push (verified by the parent on
  2026-11-22, NOT claimed before it ran): PASSED on final PR head
  `88791231caa03e8fb75a3499beeb21d1dd64a906` — 2/2 checks, push run
  #37 https://github.com/msujoy149/consistency-frame/actions/runs/45055643056
  and PR run #38 https://github.com/msujoy149/consistency-frame/actions/runs/45055649820.
  The `p0-test-results` artifact (artifact ID 14766603267) holds 43
  recorded test-run entries, 31 distinct test IDs, 24 distinct
  command strings, all PASS, every listed command exit 0; its
  `last-run.json` is byte-for-byte identical to the P0-004 ZIP's
  `tests/last-run.json`.
- NOT RUN (honest): `setup.sh --with-components` end-to-end.

## 8. Files changed

- `scripts/sync-skills.sh` — the fix (§2): explicit return-code
  checks on both `write_result_json()` calls; PARTIAL/FAILED
  branching on metadata failure; backup cleanup moved to after
  successful metadata persistence.
- `tests/test_installer_metadata_failure.sh` (new) — SEC-METADATA-05
  (§3), 13 checks.
- `tests/run-tests.sh` — `bash -n` entry for the new test file +
  `run_one "CF-P0-SEC-METADATA-05"` entry (CI runs it).
- `scripts/generate-build-report.py` — §12 test counts computed
  from `tests/last-run.json` (§4); P0-003 bullet corrected to the
  verified historical numbers; P0-004 bullet added.
- `docs/implementation/CF-WO-P0-003-corrections.md` — §5 counts
  corrected with the root-cause explanation (§4); §6 provenance
  rewritten to the final regenerated release (§5).
- `docs/implementation/CF-WO-P0-004-corrections.md` (new) — this
  record.
- `CHANGELOG.md` — [Unreleased] P0-004 entry; P0-003 entry's
  "40/40" corrected to 41 recorded entries.
- Regenerated with `--github-head 59f562a...`: `BUILD_REPORT_P0.md`,
  `build-report.json`, `release-manifest.json`, `CHECKSUMS.txt`,
  living report (see §9).

## 9. Provenance

Regenerated with `--github-head
59f562afb0d9d7c5cab14cd6d878b49d85d89449` (the GitHub branch head
before this correction). Code head: `17befa1af006ce0ce7ef8c0e1dc4534015ce5a33`
(the fix commit; the docs commit head is in the delivery report).
The manifest records the GitHub head of the code it describes;
pushing the regenerated manifest advances the branch head by one
docs-only commit, and the delivery message states the final head
(two-head rule, `BUILD_REPORT_P0.md` §12). The manifest excludes
itself and `docs/implementation/CHECKSUMS.txt` from its own file
list, and all listed hashes verify against the working tree (see
the delivery report for the count).
