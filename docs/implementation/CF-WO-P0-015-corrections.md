# CF-WO-P0-015 Corrections — Git Worktree Component Setup Gate Fix

Work order CF-WO-P0-015 (2026-11-23, branch `feat/cf-p0-safe-foundations`).
Parent head at start: local `5a034a2`, remote `212469b908d39d431cd767c4f2275bfa5d7642d1`
(116 snapshot commits). Base (main) `e1571db68ed87fb973c45960a4a3e27e09ba0d06`,
unchanged. PR #1 open, Draft, unmerged throughout. This is a narrow
follow-up to P0-014: one inconsistent gate in `setup.sh`, its regression
tests, and the usual documentation + provenance. No skill, schema,
registry, or component-internal change. No new skill. No P1 work.

## 1. Finding — verified worktrees passed verification, then skipped setup

`setup.sh` has two separate moments for each component:

1. **Clone/verify** (`clone_component()`, P0-014): an existing checkout is
   reused only after `verify_component_checkout()` proves it is the
   pinned release. That verifier already accepts valid `.git` files —
   it uses real git plumbing (`git -C "$dir" rev-parse --git-dir` and
   `--is-inside-work-tree`), and `clone_component()` enters the
   reuse path for `[ -d "$dir/.git" ] || [ -f "$dir/.git" ]`
   (`setup.sh:221`, unchanged by this round).
2. **Setup** (sections 3 and 4): the per-component setup commands
   (`bun install` + `bun run setup:api` for VoiceStudio; `make setup`
   for OpenMontage) ran only behind a directory-only gate:

   - `setup.sh:273` (pre-fix): `if [ "$STATUS_VOICESTUDIO" = "SUCCESS" ] && [ -d "components/voicestudio/.git" ]; then`
   - `setup.sh:307` (pre-fix): `if [ "$STATUS_OPENMONTAGE" = "SUCCESS" ] && [ -d "components/openmontage/.git" ]; then`

A valid linked git worktree — a `.git` *file* pointing at the shared
git directory, as produced by `git worktree add` (and the shape a
submodule checkout also takes) — therefore passed step 1 and was
reported as a verified pinned checkout, and then failed the step-2
gate. Both setup sections were skipped entirely, `STATUS_VOICESTUDIO`
and `STATUS_OPENMONTAGE` stayed `SUCCESS` (set by the clone step),
and the final summary printed
`== Setup SUCCESS: skills=SUCCESS voicestudio=SUCCESS openmontage=SUCCESS ==`
with exit 0 — while neither component had actually been set up.
That is a false SUCCESS: the user is told everything is ready when
`bun install`, the Python API install, and `make setup` never ran.

The finding was reproduced before the fix, on the pre-fix `setup.sh`
(`5a034a2`), in an isolated fixture: two component directories built
as git worktrees at the pinned commits with the official origins, a
stub sync (exit 0), and mocked `bun`/`uv`/`make` logging every
invocation. Evidence: `p0-015-false-success-before.txt` in the delivery
folder (SHA-256 `409c2ac6463daf37d3db1622d18bf2bca124bebd98b11c615049ccd4b696ea06`):
both worktrees print `already present (verified: pinned to …, clean)`,
the run exits 0 with the SUCCESS summary — and the mocked-command log
is empty. Nothing ran.

Root cause: the two setup gates were written before P0-014, when
"already present" only ever meant "a normal clone". P0-014 taught the
verifier to accept `.git` files but left the gates on the old
directory-only test, so verification and setup disagreed about what
counts as a checkout. No other `[ -d …/.git ]` gate exists in
`setup.sh` or in `scripts/` (checked by grep; the only other match is
the `clone_component()` entry check at line 221, which already accepts
both forms, and a `.git` pruning line in `scripts/validate-repo.py`
that only skips directories while walking the tree).

## 2. Fix — one plumbing helper, both gates replaced

`setup.sh` only; the change is deliberately small.

### New helper (after the P0-014 verification block, `setup.sh:141–148`)

```sh
# is_git_work_tree: exit 0 iff $1 is a valid git working tree — a
# normal clone (a `.git` directory) or a linked worktree / submodule
# (a `.git` file). Uses real git plumbing, never a `[ -d .git ]`
# test: a directory merely containing a `.git` entry proves nothing,
# and a `.git` directory test silently excludes valid worktrees.
is_git_work_tree() {
  [ "$(git -C "$1" rev-parse --is-inside-work-tree 2>/dev/null)" = "true" ]
}
```

The check is the strict one: the output must be exactly `true`
(a bare repository or a broken git directory answers `false` or
fails, so both are rejected). It is the same plumbing
`verify_component_checkout()` already relies on.

### Gate 1 — VoiceStudio setup (`setup.sh:281–317`, was line 273)

```sh
if [ "$STATUS_VOICESTUDIO" = "SUCCESS" ]; then
  if is_git_work_tree "components/voicestudio"; then
    echo "-- VoiceStudio found. Setting up its API (needs bun + uv) --"
    ... (setup body unchanged, re-indented one level) ...
    if [ "$VOICE_OK" = 0 ]; then
      STATUS_VOICESTUDIO="PARTIAL"
    fi
  else
    # The clone step verified this directory, so reaching here means it
    # stopped being a valid working tree in between (or git broke).
    # Never report SUCCESS for a component whose setup never ran.
    echo "ERROR: components/voicestudio passed verification but is no longer a valid git working tree; refusing to report SUCCESS." >&2
    echo "Remove it yourself or move it aside, then run bash setup.sh --with-components again." >&2
    STATUS_VOICESTUDIO="FAILED"
  fi
fi
```

### Gate 2 — OpenMontage setup (`setup.sh:320–348`, was line 307)

The same shape: `STATUS_OPENMONTAGE = SUCCESS` plus
`is_git_work_tree "components/openmontage"` guards the `make setup`
body (unchanged, re-indented); the `else` branch prints the
equivalent ERROR and sets `STATUS_OPENMONTAGE="FAILED"`.

### Behaviour, old vs new

| Checkout shape | Old gate | New gate |
|---|---|---|
| Normal clone (`.git` directory), verified at pin | setup runs | setup runs (unchanged) |
| Valid worktree (`.git` file), verified at pin | setup SKIPPED, SUCCESS reported (false) | setup runs |
| Invalid metadata (empty `.git` dir, garbage `.git` file) | skipped at clone, FAILED (unchanged) | skipped at clone, FAILED (unchanged) |
| STATUS SUCCESS but no longer a work tree when the gate runs (race / tampering between clone and setup) | skipped silently, SUCCESS reported | ERROR + status FAILED, run exits 1 |

The `else` branches are defence-in-depth: `verify_component_checkout()`
and the gate test the same property with the same plumbing, so they
cannot disagree inside one undisturbed run — the branches exist so a
directory that stops being a work tree between the two checks can
never keep a SUCCESS status. Nothing in the P0-014 protections
changed: origin, exact-pin, cleanliness, and user-data rules are
untouched, and no existing directory is ever reset, force-checked-out,
deleted, or overwritten by this round (the only deletion in
`clone_component()` remains the one P0-014 allows — a fresh clone
created by the run itself, on failure).

## 3. Regression tests — tests/test_installer_status.sh

Section 3, new group `CF-P0-015-WT-01..08`, 14 checks, all
network-independent. The helper is extracted from the real
`setup.sh` at test time (the Section-2 awk extraction now also
matches `is_git_work_tree`) and sourced, so the helper tests exercise
production code. End-to-end cases run a copy of the real `setup.sh`
in an isolated fixture with a stub sync and mocked `bun`/`uv`/`make`
on PATH that log every invocation — no real component command runs,
no real URL is fetched (both components are always pre-created, so no
run ever clones; `url.<base>.insteadOf` redirects to the local
fixture sources are set as a safety net).

- **WT-01** — helper accepts a normal `.git` directory.
- **WT-02** — helper accepts a valid worktree (`.git` file).
- **WT-03** — helper rejects invalid metadata (empty `.git`
  directory and a garbage `.git` file).
- **WT-04** — VoiceStudio setup runs for a valid worktree:
  `bun install` and `bun run setup:api` both logged, run exits 0
  with the SUCCESS summary.
- **WT-05** — OpenMontage setup runs for a valid worktree:
  `make setup` logged, summary names both components SUCCESS.
- **WT-06** — setup runs for valid normal clones (the ordinary path
  is not broken by the fix): both mocked commands logged, exit 0.
- **WT-07** — invalid metadata end-to-end: garbage `.git` file as
  the component directory → run exits 1, reports FAILED, never
  SUCCESS, directory preserved.
- **WT-08** — a successful worktree run leaves the worktree intact
  (still a `.git` file, HEAD readable, user content kept).

Two test-authoring notes, both recorded because they change what the
tests assume, not what the product does:

1. **Fixture location.** The end-to-end fixtures first lived under
   `$TMP` (`mktemp -d`), and every run failed before any component
   logic with `ERROR: less than 5 GB free disk space for the
   components` — `$TMP` is a 512 MB tmpfs, and `setup.sh` refuses
   `--with-components` under 5 GB free. The fixtures now live under
   `$WT_BASE`, a `mktemp -d` directory inside the repo (main disk,
   real free space), removed at the end of the section and by the
   EXIT trap. The disk-space gate itself is unchanged and untested
   here; the lesson is the same one recorded for `/tmp` before —
   fixtures that a script measures against the disk must live on a
   disk with room.
2. **The `else` (gate-rejects-after-SUCCESS) branches have no
   deterministic end-to-end test.** Inside one undisturbed run the
   verifier and the gate cannot disagree, so the branches are only
   reachable by a race or tampering between the two checks. They are
   covered by code inspection and by WT-03/WT-07 (rejection is
   FAILED, never SUCCESS); the WT-04/WT-05 assertions pin the
   reachable path — SUCCESS is reported only when the mocked setup
   commands actually ran.

**Before (new tests against pre-fix `setup.sh` `5a034a2`, test file
unchanged): exit 1, 8 failures** — all eight WT checks fail as
`(helper missing from setup.sh)`; all 47 P0-014 checks still pass.
Evidence: `p0-015-test-installer-status-before.txt` (SHA-256
`59ca615d973d514febb283d766b4b54735f13da4a72d471e843c38d69b477dc7`).
The helper-missing failures alone only prove the tests need the
helper; the real bug is proved separately by the false-SUCCESS
reproduction in §1 (`p0-015-false-success-before.txt`): old code,
valid worktrees, exit 0, SUCCESS summary, empty command log.

**After (fixed `setup.sh`): exit 0, 61 PASS / 0 FAIL** (47 P0-014 +
14 new WT). Evidence: `p0-015-test-installer-status-after.txt`
(SHA-256 `316dd54dbd12558298b0c0e313b3ac081711a809c10a422231176cb0c9e3f934`).

Registered in `tests/run-tests.sh` as one new entry,
`run_one "CF-P0-015-WT" bash tests/test_installer_status.sh`
(after the CF-P0-014-PIN line). No existing test or assertion was
touched or weakened.

## 4. Documentation

- This record: `docs/implementation/CF-WO-P0-015-corrections.md`.
- `CHANGELOG.md`: `[Unreleased]` P0-015 entry (top of the Added list).
- `docs/06-installation.md`, item 2: one sentence added — a linked
  git worktree (a `.git` file instead of a `.git` directory) is a
  valid working tree and is verified and set up the same way as a
  normal clone. The "Re-running" paragraph already said the
  component setups "run again"; with the old gates that was false
  for worktrees, and it is true now. `README.md` needed no change —
  it states no existing-checkout gate behaviour the fix contradicts.
- `AGENTS.md` deliberately not changed — the work order's Task D
  lists the corrections record, CHANGELOG, and installation
  documentation; the existing P0-014 note (components report
  SUCCESS/PARTIAL/FAILED honestly) is now more accurate, not less.

## 5. Exact files changed

This round (parent head `5a034a2` to the P0-015 commit): **12 files,
+634/−90** (11 tracked files at +328/−90, plus this record, new,
306 lines). Against the base `e1571db6`: **164 files, +34,780/−267**.

| File | Change |
|---|---|
| `setup.sh` | New `is_git_work_tree()` helper; both setup gates replaced with it; `else` branches mark FAILED with a clear ERROR. Setup bodies unchanged apart from re-indentation. |
| `tests/test_installer_status.sh` | Section 3 (CF-P0-015-WT-01..08, 14 checks); extraction extended to `is_git_work_tree`; header updated; trap also removes `$WT_BASE`. |
| `tests/run-tests.sh` | One new entry `CF-P0-015-WT`. |
| `docs/06-installation.md` | Worktree sentence in item 2. |
| `docs/implementation/CF-WO-P0-015-corrections.md` | This record (new). |
| `CHANGELOG.md` | `[Unreleased]` P0-015 entry. |
| `docs/implementation/BUILD_REPORT_P0.md`, `build-report.json`, `CHECKSUMS.txt`, `release-manifest.json`, `docs/architecture/living-architecture-report-v2.4-p0.md` | Provenance regenerated (see §7). |
| `tests/last-run.json` | New suite record (54 entries). |

No skill, schema, registry, or component-internal file changed.
`setup.sh --with-components` was not run.

## 6. Verification commands and exit codes

All at the final state unless noted:

- `bash -n setup.sh` — exit 0.
- `bash tests/test_installer_status.sh` — exit 0, 61 PASS / 0 FAIL
  (after fix; exit 1, 8 WT failures on pre-fix `setup.sh`).
- `bash tests/run-tests.sh` — twice, exit 0 both times:
  **54 recorded entries / 41 distinct test IDs / 32 distinct
  commands, 54 PASS, 0 FAIL, 0 SKIP** (was 53/40/32 — the new
  `CF-P0-015-WT` entry adds one entry and one ID; the command was
  already registered).
- Per-file PASS totals (single-run, 0 FAIL everywhere): 12 Python
  files total **1,304** (unchanged — `test_private_voice_security.py`
  still 158, all P0-011 protections intact; `test_reports.py` still
  47); `tests/test_installer_status.sh` **61** per run;
  `tests/test_installer.sh` 40, `tests/test_installer_security.sh`
  15, `tests/test_installer_manifest_security.sh` 24,
  `tests/test_installer_metadata_failure.sh` 13.
- `tests/last-run.json` SHA-256 (recalculated, not reused):
  recorded in the delivery report.
- `python3 scripts/validate-repo.py` — PASS.
- `python3 scripts/generate-registries.py --check` — CHECK OK.
- `python3 scripts/generate-report.py --check` — CHECK OK (same
  `--github-head 212469b9` as generation).
- `python3 tests/test_reports.py` — PASS (0 failures).
- `git diff --check` — clean.
- `bash setup.sh --dry-run` — exit 0 (core-only).
- `bash setup.sh --with-components` — **NOT RUN** (see §8).

Suite evidence: `p0-015-suite-run1.txt`,
`p0-015-suite-run2.txt` in the delivery folder.

## 7. Provenance

Correct order: `scripts/generate-report.py` first,
`scripts/generate-build-report.py` last, both with
`--github-head 212469b908d39d431cd767c4f2275bfa5d7642d1` (the current
remote head; no push happens in the local phase). The manifest is
regenerated AFTER the final suite run — the suite rewrites the living
report — and the suite is not run again before committing. Final
manifest numbers, hashes, and the post-push provenance are recorded
in the delivery report by the parent.

## 8. Remaining limitations

- The real `--with-components` install is still untested
  end-to-end (NOT RUN, honestly labelled). The new tests prove the
  gate logic against local fixtures with mocked component commands;
  they do not prove `bun install`, `bun run setup:api`, or `make
  setup` succeed against the real components, or that the real
  upstream commits are fetchable from this network. Mocked tests
  must never be presented as real installation evidence.
- The gate-rejects-after-SUCCESS `else` branches have no
  deterministic end-to-end test (see §3, note 2) — they are
  defence-in-depth for a race, covered by inspection and by the
  rejection tests.
- `is_git_work_tree()` trusts the local git binary: a `.git` file
  pointing at attacker-controlled git metadata that git itself
  accepts would still pass the gate — the same standing limitation
  as P0-014 (verification trusts local git and the filesystem; no
  protection against malicious same-process code).
- All tests ran on this Linux VM; no Mac/Windows run.
- P0-015 is not P0 final approval. After delivery, all
  implementation stops; the independent reviewer conducts the
  complete final P0 audit of the exact GitHub HEAD. P1 does not
  start unless P0 is independently accepted and the user explicitly
  agrees.
