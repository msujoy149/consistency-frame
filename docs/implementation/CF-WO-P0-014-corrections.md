# CF-WO-P0-014 Corrections — Installer Status Propagation & Pinned Component Verification

**Work order:** CF-WO-P0-014
**Date:** 2026-11-23
**Branch:** `feat/cf-p0-safe-foundations`
**Base (P0-013, report-only — no repo change):** local head `95eb7ad`, remote head `6ff9dbd451d265d315b49f4513221b13ec66764d`
**Scope:** `setup.sh` behaviour fix + regression tests + documentation + provenance. No new skill, no server/API/database, no VoiceStudio/OpenMontage internals changed, no P1 work, no merge.

## 1. Defect A — core sync exit contract collapsed (setup.sh)

### What was wrong

`scripts/sync-skills.sh` has three exit codes, documented in its own header and in `setup.sh`'s header:

- `0` = SUCCESS
- `2` = PARTIAL (sync applied but a non-fatal step failed)
- `1` = FAILED

`setup.sh` (pre-fix, lines 76–84) collapsed every non-zero return to FAILED:

```bash
if bash scripts/sync-skills.sh "${SYNC_ARGS[@]}"; then
  STATUS_SKILLS="SUCCESS"
else
  sync_code=$?
  echo "ERROR: skill sync failed (exit $sync_code). ..." >&2
  STATUS_SKILLS="FAILED"
  echo ""
  echo "== Setup FAILED: skills=$STATUS_SKILLS voicestudio=$STATUS_VOICESTUDIO openmontage=$STATUS_OPENMONTAGE =="
  exit 1
fi
```

A PARTIAL sync (exit 2 — e.g. changes applied but the final metadata record could not be written) was therefore reported as FAILED with exit 1. The installer already promised the three-state contract in its own header comment ("Exit codes: 0 = SUCCESS … 2 = PARTIAL … 1 = FAILED") and in `docs/06-installation.md` ("exits 1 (FAILED) or 2 (PARTIAL)"), but the code did not implement it.

### Root cause

The `if/else` treated the sync as a boolean: success vs failure. The exit code was captured only for the error message, never used to select the status. There was no PARTIAL branch at all.

### Fix (setup.sh, core-sync block)

The sync is now run as a plain command and its exit code is captured explicitly (the script runs under `set -uo pipefail`, never `set -e`, so no error handling relies on `set -e`):

```bash
bash scripts/sync-skills.sh "${SYNC_ARGS[@]}"
sync_code=$?
case "$sync_code" in
  0) STATUS_SKILLS="SUCCESS" ;;
  2)
    STATUS_SKILLS="PARTIAL"
    echo "ERROR: skill sync PARTIAL (exit 2). ... Component installation is skipped." >&2
    echo ""
    echo "== Setup PARTIAL: skills=$STATUS_SKILLS voicestudio=$STATUS_VOICESTUDIO openmontage=$STATUS_OPENMONTAGE =="
    exit 2
    ;;
  *)
    STATUS_SKILLS="FAILED"
    echo "ERROR: skill sync failed (exit $sync_code). ..." >&2
    echo ""
    echo "== Setup FAILED: skills=$STATUS_SKILLS voicestudio=$STATUS_VOICESTUDIO openmontage=$STATUS_OPENMONTAGE =="
    exit 1
    ;;
esac
```

### Old vs new exit behaviour

| sync-skills.sh exit | Old setup.sh status / exit | New setup.sh status / exit |
|---|---|---|
| 0 | SUCCESS / 0 | SUCCESS / 0 |
| 2 | FAILED / 1 | PARTIAL / 2 |
| 1 | FAILED / 1 | FAILED / 1 |
| other (e.g. 3) | FAILED / 1 | FAILED / 1 |

A PARTIAL or FAILED core sync exits before the `--with-components` section, so component installation never begins. The final summary always prints the real status — SUCCESS is never reported after a partial or failed sync. `sync-skills.sh` stderr diagnostics pass through untouched (the installer adds its own line, it never suppresses the sync's output).

## 2. Defect B — existing component checkouts accepted unverified (setup.sh)

### What was wrong

`clone_component()` (pre-fix, lines 113–118) accepted any directory containing `.git` and returned success immediately:

```bash
clone_component() {
  local name="$1" url="$2" dir="$3" pin="$4"
  if [ -d "$dir/.git" ]; then
    echo "-- $name already present --"
    return 0
  fi
  ...
```

It verified nothing: not repository validity, not the remote origin, not the HEAD SHA, not working-tree cleanliness. A directory with an empty `.git` folder, a `.git` file full of garbage, a fork's origin, a checkout at another commit, or a tree full of uncommitted user edits was all reported as the pinned release — and the component setup steps then ran against it. That contradicts the pinned-component installation contract (`setup.sh` header: components are "pinned to a tested commit", VoiceStudio `2f2f5a9b0e982c6147efc6baaeae62936f29b79b`, OpenMontage `fecb9a1e3cc23ef84de30b272059457a427f16f8`) and the docs (`docs/06-installation.md` item 2). The fresh-clone path had the same gap in miniature: after `git fetch` + `git checkout "$pin"` it never verified that HEAD actually equals the pin.

### Root cause

The `.git` presence check was written as a shortcut ("already present") and never grew into a verification step when pinning was added. The pin was only used as a checkout target for fresh clones, never as a check for existing ones.

### Fix (setup.sh)

Two new helpers, plus a rewritten `clone_component()`:

**`canonical_github_repo()`** — extracts the `owner/repo` from a remote URL, accepting the standard forms `https://github.com/<owner>/<repo>` (optional `.git`, optional trailing `/`), `ssh://git@github.com/<owner>/<repo>`, and `git@github.com:<owner>/<repo>`. Anything else (another host, `http://`, an empty path) fails. An extra path segment extracts to a longer path, which never equals the expected `owner/repo`, so it is rejected at comparison.

**`verify_component_checkout()`** — `$1=name $2=expected owner/repo $3=dir $4=pin`. Returns 0 only when all of these hold, printing a clear ERROR (and what the user must do) on every failure path, without touching the directory:

1. **Validity:** `git -C "$dir" rev-parse --git-dir` succeeds and `git -C "$dir" rev-parse --is-inside-work-tree` prints `true`. Real git plumbing, not a `[ -d .git ]` test — so a `.git` *file* (worktree/submodule gitdir) works and an empty or garbage `.git` fails.
2. **Origin:** `remote.origin.url` must exist and its canonical form must equal the expected official repository (`debpalash/VoiceStudio` or `OpenMontageInc/OpenMontage`). A fork, a prefix look-alike (`VoiceStudio-evil`), an `http://` URL, or a missing origin is rejected.
3. **Exact commit:** `git -C "$dir" rev-parse HEAD` must equal the full 40-character pin. A missing/unborn HEAD fails.
4. **Clean tree:** `git -C "$dir" status --porcelain` must be empty — no staged, unstaged, or untracked changes. A `git status` failure is itself a rejection.

**`clone_component()`** — now:

- Derives the expected repo from its `$url` argument (the call sites pass the official URLs); an unrecognised URL is an internal error, return 1.
- If `$dir/.git` exists (file or directory), the directory is verified with `verify_component_checkout()` and reused only on success (`-- $name already present (verified: pinned to <short>, clean) --`). On failure it returns 1 — the directory is never reset, force-checked-out, deleted, or overwritten.
- A non-empty directory without git metadata is still an error, return 1, no deletion (unchanged).
- A fresh clone keeps the existing procedure (`git clone --depth 1`, `git fetch --depth 1 origin "$pin"`, `git checkout "$pin"`), then runs the same `verify_component_checkout()` before reporting success. If the checkout or the verification fails, the directory is removed with `rm -rf` and the function returns 1 — safe, because that directory was created by this run and holds no user data. (Only the fresh-clone path ever deletes; the existing-checkout path never does.)

The later setup steps (sections 3–4, `bun install` / `make setup`) are unchanged; they already run only when the component status is SUCCESS.

### Existing-component verification policy (summary)

| Existing checkout state | Result |
|---|---|
| Valid git tree, official origin, HEAD = pin, clean | Reused, no re-clone |
| HEAD differs from the pin | Rejected, clear error naming the pin; directory preserved |
| Origin missing / wrong / prefix look-alike / http | Rejected, clear error naming the origin; directory preserved |
| Uncommitted or untracked changes | Rejected, clear error; files left untouched |
| Invalid or incomplete git metadata (empty `.git`, garbage `.git` file, no HEAD) | Rejected, clear error; directory preserved |
| Non-empty directory, no git metadata | Rejected, clear error; directory preserved |
| Fresh clone, checkout or verification fails | Incomplete clone removed (created by this run); return 1 |

## 3. Regression tests — tests/test_installer_status.sh

New file, registered in `tests/run-tests.sh` as `CF-P0-014-INST` and `CF-P0-014-PIN` (plus a `bash -n` entry). 47 checks, all network-independent: every git fixture is created fresh in the test (`git init` + local commits under a `mktemp` directory); component clones are redirected to local fixture sources with git's `url.<base>.insteadOf` mechanism, so no real URL is ever fetched. Mocked tests are never presented as real component installation evidence — the real `setup.sh --with-components` run remains NOT RUN (see §6).

**Section 1 — status propagation (CF-P0-014-INST-01..08).** A copy of the real `setup.sh` runs in an isolated git fixture whose `scripts/sync-skills.sh` is a stub exiting with `$SYNC_EXIT`:

- INST-01: sync exit 0 → setup exit 0, `== Setup SUCCESS:`.
- INST-02: the stub's stderr diagnostics reach the user unchanged.
- INST-03: sync exit 2 → setup exit 2, `== Setup PARTIAL:`, `skills=PARTIAL`.
- INST-04: sync exit 2 + `--with-components` → exit 2, no `components/` directory, "Installing bundled components" never appears.
- INST-05: sync exit 1 → setup exit 1, `== Setup FAILED:`.
- INST-06: sync exit 1 + `--with-components` → exit 1, no `components/` directory.
- INST-07: unexpected sync exit 3 → setup exit 1, FAILED.
- INST-08: no `== Setup SUCCESS:` in any PARTIAL/FAILED output.

**Section 2 — component verification (CF-P0-014-PIN-01..16).** The real `verify_component_checkout()`, `canonical_github_repo()`, and `clone_component()` are extracted from `setup.sh` at test time (awk, by function name) and sourced, so the tests exercise the production code, not a copy:

- PIN-01 (static): the real call sites pass the exact pins and official URLs.
- PIN-02: all three helpers are present in `setup.sh` (if they are missing — e.g. on pre-fix code — the remaining PIN checks are reported failed by name instead of crashing).
- PIN-03: origin forms — HTTPS, HTTPS+`.git`, trailing slash, SSH `git@…`, `ssh://…` accepted; `http://`, another host rejected; an extra path segment extracts to a longer path that never equals the expected repo.
- PIN-04: valid existing checkout at the pin (HTTPS origin) is reused, reported as verified, HEAD unchanged.
- PIN-05: the same checkout with an SSH origin is accepted.
- PIN-06: one more commit (HEAD ≠ pin) → rejected, error names the pinned commit, directory preserved (fixture reset to the pin afterwards).
- PIN-07: wrong origin → rejected, error names the unexpected origin, directory preserved.
- PIN-08: origin prefix attack (`VoiceStudio-evil`) → rejected.
- PIN-09: `http://` origin → rejected.
- PIN-10: uncommitted modification → rejected, error says the tree is modified, user content preserved.
- PIN-11: untracked file → rejected, directory preserved.
- PIN-12: empty `.git` directory → rejected, directory preserved.
- PIN-13: `.git` regular file with garbage → rejected, directory preserved.
- PIN-14: fresh clone (both components, via the local redirect) → return 0, HEAD equals the pin, origin is the official URL, working tree clean.
- PIN-15: every rejected fixture directory still exists afterwards.
- PIN-16: no rejected checkout was ever reported as verified/success.

### Before / after

Against the pre-fix `setup.sh` (fix stashed, test unchanged): **exit 1, 13 PASS / 19 FAIL** — INST-03 (all three assertions: exit code was 1, not 2; no PARTIAL summary) and INST-04 (exit code) fail; PIN-02..PIN-16 fail as "helpers missing from setup.sh". INST-04's "no components directory" and "install not started" assertions pass even pre-fix (the old code also exited before the components) — the defect there was the exit code and status, which the failing assertions catch. PIN-01 passes pre-fix (the pins and URLs were already correct in the call sites).

Against the fixed `setup.sh`: **exit 0, 47 PASS / 0 FAIL** (`p0-014-test-installer-status-after.txt`).

One test-authoring correction during the round: PIN-03 first asserted that `canonical_github_repo` must *fail* on `…/VoiceStudio/tree/main`. That was the wrong expectation — the helper's contract is extraction (it returns the path after the host prefix); the extra segment is rejected by the equality comparison in `verify_component_checkout()`. The assertion was corrected to check the extracted path is not the expected repo; no production code changed for this.

### What the tests do not prove

- They do not run the real `setup.sh --with-components` against the real upstream repositories. The fresh-clone test proves the clone → fetch → checkout → verify sequence against local fixtures with the same function and the same pin/origin logic, not a network install.
- They do not test `bun install` / `make setup` (component setup steps) — unchanged by this round.

## 4. Documentation

- `docs/06-installation.md`: item 2 now states the existing-checkout verification rule (valid tree, official origin, exact pin, clean tree; rejection leaves the directory untouched, never reset or deleted) and that a fresh clone is verified the same way; the "Re-running" paragraph now says existing components are verified and reused only on match (not "skipped"), and that a PARTIAL skill sync stops the run before any component is installed.
- `README.md`: no change needed — it describes the core-only default and the opt-in component path at a high level and states no existing-checkout behaviour that the fix contradicts.
- `CHANGELOG.md`: [Unreleased] P0-014 entry (top of the Added list).
- `AGENTS.md`: not changed by this round (the work order's Task D lists the corrections record, CHANGELOG, and installation documentation; the existing "P0 safe foundations" bullet — components report SUCCESS/PARTIAL/FAILED honestly — is still accurate).

## 5. Exact files changed

| File | Change |
|---|---|
| `setup.sh` | Task A: core-sync exit propagation (case on the captured exit code). Task B: `canonical_github_repo()`, `verify_component_checkout()`, rewritten `clone_component()` with post-clone verification. No other behaviour changed. |
| `tests/test_installer_status.sh` | New: 47 checks (INST-01..08, PIN-01..16). |
| `tests/run-tests.sh` | Registered `bash -n tests/test_installer_status.sh` and two entries (`CF-P0-014-INST`, `CF-P0-014-PIN`) running the new file. |
| `docs/06-installation.md` | Existing-checkout verification policy + PARTIAL-sync stop rule. |
| `docs/implementation/CF-WO-P0-014-corrections.md` | This record. |
| `CHANGELOG.md` | [Unreleased] P0-014 entry. |
| `tests/last-run.json`, `docs/architecture/living-architecture-report-v2.4-p0.md`, `docs/implementation/BUILD_REPORT_P0.md`, `docs/implementation/build-report.json`, `docs/implementation/CHECKSUMS.txt`, `release-manifest.json` | Regenerated provenance (see §7). |

No skill, schema, registry, or component-internal file changed. `setup.sh --with-components` was never run.

## 6. Verification commands and exit codes

- `bash -n setup.sh` — exit 0.
- `bash tests/test_installer_status.sh` — exit 0, 47 PASS / 0 FAIL (before: exit 1, 13 PASS / 19 FAIL on pre-fix code).
- `bash tests/run-tests.sh` — run TWICE at final state, exit 0 both times (counts recalculated, see §7).
- `python3 scripts/validate-repo.py` — PASS.
- `python3 scripts/generate-registries.py --check` — CHECK OK.
- `python3 scripts/generate-report.py --check` — CHECK OK (same `--github-head` as generation).
- `python3 tests/test_reports.py` — PASS (0 failures).
- `git diff --check` — clean.
- `bash setup.sh --dry-run` — exit 0 (core-only).
- `bash setup.sh --with-components` — **NOT RUN** (full component installation has never been completed end-to-end in this environment and stays honestly labelled NOT RUN; the mocked fresh-clone tests are not real installation evidence).

## 7. Provenance

Generators run in the established order (`generate-report.py` first, `generate-build-report.py` last, both with `--github-head 6ff9dbd451d265d315b49f4513221b13ec66764d`, the current remote head — no push happens in the local phase); the manifest was regenerated AFTER the final suite run (the suite rewrites the living report) and the suite was not run again before committing. Local provenance: manifest **159 files, 0 hash mismatches** vs the working tree (the new test file and corrections record are untracked, so they join the manifest after the push, as in P0-012); manifest commit `95eb7ad`, github_branch_head `6ff9dbd4`; manifest SHA `fea19c1f942b2a69e43f322f81b49a66e935bc158061a8626eb585bbbab38c23`; build-report SHA `63c0fe615e1d93aa6efa689f8525dd99c38a4c2f14f1ded5896a83d98bac479a`; BUILD_REPORT_P0.md SHA `5461a6514edcf00625007cef7aabdcfb7fd77f7c53b00f3a8d7ee9f82638c9a1`; CHECKSUMS.txt 3/3 OK. The parent regenerates provenance after the push at the new head.

## 8. Remaining limitations

- **The real `--with-components` install is still untested end-to-end.** The new tests prove the verification logic against local fixtures; they do not prove `bun install` / `make setup` succeed, nor that the real upstream commits are fetchable from this network. Until a real run completes and is independently verified, the install stays labelled NOT RUN.
- **Origin matching is exact, not case-insensitive.** GitHub treats `owner/repo` case-insensitively, but the verifier requires the exact canonical casing. A checkout whose origin differs only in case is rejected with instructions — fail-closed by design.
- **Untracked files make a checkout non-reusable.** Any untracked file (even a harmless note) fails the cleanliness check. That is the conservative reading of the work order ("no uncommitted or untracked changes that would make it unsafe"); a user who wants reuse must move the file aside first. The error message says so.
- **Verification trusts the local git binary and the local filesystem.** It does not detect a maliciously crafted `.git` directory that git itself accepts, and it cannot protect against code running with the same OS-user privileges. Same standing limitation as the P0-008..P0-011 authorization contracts.
- **A checkout at the pinned commit with staged-but-uncommitted changes is rejected** (porcelain is non-empty) — correct per the policy, recorded here so the strictness is visible.
- **No Windows/macOS run.** All tests ran on this Linux VM; the shell code uses only POSIX-ish bash + git, but no Mac/Windows machine verified it.
