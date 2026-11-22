# CF-WO-P0-003 — Final independent security correction

Work order CF-WO-P0-003 (independent review of the P0-002 package).
Branch `feat/cf-p0-safe-foundations`. No skill file changed; no
server/API/database added; no P1 started.

## 1. Root cause

`scripts/sync-skills.sh` wrote the ownership manifest to a
**predictable temporary filename**, `<target>.tmp`, with an ordinary
Python `open(tmp, "w")` followed by `os.replace(tmp, target)` — in
two places: `write_manifest()` and `update_manifest_hashes()`
(rollback). An attacker who can plant a symlink at
`.consistency-frame-manifest.json.tmp` pointing outside the
destination makes the write follow the symlink and overwrite the
external target. The vulnerability was independently reproduced
against the P0-002 package, and re-reproduced locally against the
old pattern before the fix (a canary file outside the destination
was overwritten with manifest JSON by the old code; see §4).

The same pattern existed in two more installer metadata writers:
`write_result_json()` (`.consistency-frame-last-sync.json` — it
unlinked a planted symlink first, which still left a TOCTOU window
between unlink and open) and `write_run_owner()`
(`.run-owner.json` — plain `open(..., "w")`).

## 2. Fix — one reusable secure atomic-write helper

New module `scripts/atomic_write.py` (`atomic_write(path, data)`,
`atomic_write_json(path, obj)`), used by all four writers:

- Temporary file created with `tempfile.mkstemp(dir=<target's
  parent>, prefix=".cf-atomic-", suffix=".tmp")` — exclusive
  creation (O_CREAT | O_EXCL), unique random name, never following a
  planted path. Renaming `.tmp` to another predictable name would
  not have fixed this.
- Written through the file descriptor returned by `mkstemp`
  (`os.fdopen(fd, "wb")`), flushed + `os.fsync`, closed, then
  `os.replace(tmp, target)`.
- `os.replace()` never follows a symlink at the target: a planted
  symlink at the target itself is replaced by the new regular file
  and its outside target is untouched.
- On any failure the temp file is removed (best effort) and the
  error propagates — the installer never reports SUCCESS after a
  failed write.
- Mode: the target's existing mode when it is a regular file, else
  `0o666 & ~umask` — matching what a plain `open()` produced, so
  installs do not change file permissions (installed files are
  0660 under this environment's umask 007).

The embedded Python heredocs import the helper from the scripts
directory via the `CF_ATOMIC_WRITE_LIB` environment variable set by
`sync-skills.sh`; they fail hard if it is unset, so a metadata
write can never silently fall back to a predictable temp file. The
helper is defined once and imported — not redefined per call site.

Out of scope (noted, not changed): the repo build tools
(`scripts/generate-build-report.py`, `generate-report.py`,
`generate-registries.py`) also write with plain `open(..., "w")`,
but they write generated reports inside the repo checkout the user
controls, not installer metadata into an arbitrary destination, so
they are not part of this installer vulnerability.

## 3. Files changed

| File | Change |
|---|---|
| `scripts/atomic_write.py` (new) | Secure atomic-write helper (`atomic_write`, `atomic_write_json`). |
| `scripts/sync-skills.sh` | All four metadata writers migrated to the helper; `CF_ATOMIC_WRITE_LIB` export; header note. |
| `tests/test_installer_manifest_security.sh` (new) | SEC-MANIFEST-01..04. |
| `tests/test_atomic_write.py` (new) | Helper unit tests CF-P0-ATOMIC-001..006. |
| `tests/run-tests.sh` | Registers the new suites (bash -n + 5 run_one entries). |
| `docs/06-installation.md` | Atomic/symlink-safe metadata-write note. |
| `docs/implementation/BUILD_REPORT_P0.md` | §12 extended with the P0-003 correction. |
| `docs/implementation/CF-WO-P0-003-corrections.md` | This file. |
| `CHANGELOG.md` | [Unreleased] P0-003 entry. |
| `docs/architecture/living-architecture-report-v2.4-p0.md`, `docs/implementation/build-report.json`, `release-manifest.json`, `docs/implementation/CHECKSUMS.txt`, `tests/last-run.json` | Regenerated at the P0-003 code head. |

## 4. Regression tests

All run via `bash tests/run-tests.sh` (see §5) and standalone.

- **SEC-MANIFEST-01** — manifest temp symlink attack: dest + skill
  installed; outside canary with known content; planted
  `.consistency-frame-manifest.json.tmp` symlink to the canary;
  source skill modified; installer run. Canary byte-for-byte
  unchanged, final manifest a regular file with the new content,
  last-sync honestly reports SUCCESS, planted symlink untouched,
  no stale `.cf-atomic-*` temps. 7 checks, PASS.
- **SEC-MANIFEST-02** — rollback temp symlink attack: valid install
  + backup; same planted symlink; rollback (invokes
  `update_manifest_hashes()`). Canary unchanged, manifest a regular
  file, v1 content restored, rollback reports "restored 1 file(s)".
  6 checks, PASS.
- **SEC-MANIFEST-03** — concurrent/repeated writes: three repeated
  syncs with the planted symlink in place; canary unchanged, no
  stale temps; a failed run (corrupt manifest) also leaves no stale
  temps and still fails the sync. 6 checks, PASS.
- **SEC-MANIFEST-04** — last-sync metadata: symlink planted AT
  `.consistency-frame-last-sync.json` pointing outside; normal sync.
  Outside target unchanged, final metadata a regular file with
  status SUCCESS. 5 checks, PASS.
- **CF-P0-ATOMIC-001..006** (`tests/test_atomic_write.py`) — helper
  unit tests: basic write; mode preservation (0o640 kept);
  planted sibling `.tmp` symlink ignored; planted symlink AT the
  target replaced, not followed; simulated `os.replace` failure
  propagates, target unchanged, no temp left; non-bytes input
  raises TypeError with no temp left; JSON round-trip. 18 checks,
  PASS.

Negative control (run before the fix was trusted): the OLD pattern
(`open(manifest + ".tmp", "w")` + `os.replace`) executed against a
planted symlink overwrote the outside canary with manifest JSON —
the vulnerability reproduced. The NEW helper against the same setup
left the canary byte-for-byte unchanged. The regression tests
therefore discriminate: they fail on the old code and pass on the
new code. Existing SEC-01..SEC-08 tests unchanged and still passing.

## 5. Validation

- `bash tests/run-tests.sh` → **41 recorded test-run entries PASS**
  (35 previous + 1 new `bash -n tests/test_installer_manifest_security.sh`
  + 4 SEC-MANIFEST + 1 ATOMIC), exit 0, verified independently.
  30 distinct test IDs, 22 distinct command strings; each listed
  command returned exit 0. (Correction, CF-WO-P0-004: this section
  originally said "40/40" — a hand-count error that omitted the new
  `bash -n` entry, 35 + 4 + 1 = 40 instead of 35 + 1 + 4 + 1 = 41.
  The `last-run.json` committed with the fix was also stale — 35
  entries — because it was recorded before the new runner entries
  were added; it was re-recorded with 41 entries in the docs commit.
  The GitHub Actions artifact for the same head independently
  records 41 rows, all PASS. Never represent test-run rows as unique
  commands or individual assertions: the 41 rows are recorded
  test-run entries, some commands run more than once under different
  test IDs.)
- `bash setup.sh --dry-run` → exit 0, `Setup SUCCESS:
  skills=SUCCESS voicestudio=SKIPPED openmontage=SKIPPED`.
- `bash setup.sh` core-only → exit 0, 15 skills synced.
- `git diff --check` → clean.
- NOT RUN (honest): `setup.sh --with-components` end-to-end;
  remote CI on the new head (parent checks after push).

## 6. Provenance

Regenerated with `--github-head
43d4fd33a59a19c57cabbb74b14492a2acaf9343` (the GitHub branch head of
the pushed correction commits). The release manifest records the
code head it describes (`5e25545a3d803b7611b8865d453f4c88f524b525`)
and that GitHub head (`43d4fd33...`); pushing the regenerated
manifest advanced the branch head by one docs-only commit, and the
final PR head after that push was
`59f562afb0d9d7c5cab14cd6d878b49d85d89449` — the two heads have
different meanings, see `BUILD_REPORT_P0.md` §12 (two-head rule).
(Correction, CF-WO-P0-004: this section originally named an earlier
intermediate head as the regenerated release; the final regenerated
release is the one above.) The manifest excludes itself and
`docs/implementation/CHECKSUMS.txt` from its own file list, and all
listed hashes verify against the working tree (see the delivery
report for the count).
