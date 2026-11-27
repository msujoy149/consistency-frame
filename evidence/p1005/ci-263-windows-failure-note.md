# CI run #263 — Windows failure note (P1-005-R1)

Run: #263, ID 45994910588, workflow P0 CI, PR #5, head
`a6fa1e14664583dfe4217cf2e9910e13627c7201` (P1-005 final head).
Overall: Failure, 1m 52s.
- p0-validate (Linux): Success, 1m 49s.
- windows-compat (Python 3.10): Failed, 1m 12s.
- windows-compat (Python 3.12): Failed, 31s.

## Failing step (both Windows jobs, identical)

Step 11, "Run identity resolution suite", in the end-to-end group:

```
File "tests\test_identity_resolution.py", line 1471, in _e2e_group
    store.save_production_job(session, root, job)
File "runtime\production_store.py", line 315, in save_production_job
    return _write_record(path, record)
File "runtime\production_store.py", line 198, in _write_record
    helper.atomic_write_json(path, record, mode=_file_mode())
File "scripts\atomic_write.py", line 102, in atomic_write_json
    atomic_write(path, blob, mode=mode)
File "scripts\atomic_write.py", line 78, in atomic_write
    os.fchmod(fd, mode)
AttributeError: module 'os' has no attribute 'fchmod'.
```

The job stopped at step 11, so the production-store step and the four
P1-005 suite steps never ran on Windows.

## Root cause

`scripts/atomic_write.py` called `os.fchmod` unconditionally. P1-001-R2
fixed the identical hole in `runtime/local_session.py` but left this
helper untouched. The production store writes through this helper, and
the identity and store steps were added to `windows-compat` by P1-005,
so this was the first Windows run to exercise the path. A
repository-wide grep confirmed this helper was the only remaining
unconditional `os.fchmod` call outside the components.

## Fix

`atomic_write` applies the mode only when `os.fchmod` exists
(`hasattr` check, the R2 pattern); on Windows the file inherits the
parent directory's ACL behaviour. Regression group
`CF-P1-005-R1-STORE` (six checks) in `tests/test_production_store.py`
simulates the Windows absence by hiding `os.fchmod`. Verified to
reproduce the defect: with the fix stashed, the suite crashes with the
same `AttributeError`. Full record: corrections doc §9.

## Downloaded evidence

- Log archive `logs_124432527258.zip`, SHA-256
  `913cc8032a0f6c2fb32a31a9f03bd24f4292e0a6b938669cdfc1e1cbd85c4b33`
  (run-wide archive, suite endpoint `suites/124432527258/logs`).
- Artifact `p0-test-results.zip`, SHA-256
  `3f73d13f0e90f0fefc36bd80857a2b843a9b851ca8a2109612323a8d11733166`
  (artifact ID 15195990331; matches the digest shown on the run page).

Both files are kept in `ci-evidence-p1-005/` with the extracted logs
under `logs-extracted/` (per-step files; the Windows per-step files end
at step 11, then 32/33 post steps).

---

# CI run #266 — Windows failure note (P1-005-R2)

Run: #266, ID 45997891103, workflow P0 CI, PR #5, head
`b97f6718b4e1e259f1966608214255554f15c274` (P1-005-R1 final head).
Overall: Failure, 1m 38s.

- p0-validate (Linux): Success, 1m 36s.
- windows-compat (Python 3.10): Failed, 1m 12s.
- windows-compat (Python 3.12): Failed, 28s.

## Failing step (both Windows jobs, identical)

Step 16, "Run timeline delivery suite", with exactly one failure:

```
--- CF-P1-005-DELIVERY: 23 checks, 1 failures ---
FAILURES: CF-P1-005-DELIVERY-artifact-absolute-refused
```

The R1 fix had worked: steps 11 (identity) and 12 (production
store) now ran, as did steps 13–15 — media execution 68 checks,
FFmpeg skipped (no ffmpeg installed), media adapters 50 checks —
all passing. (The lower counts vs local — 85/56/26 — are the
ffmpeg-dependent groups and symlink cases skipping on Windows, by
design; no conformance is claimed for them there.)

## Root cause

`validate_delivery_artifact` rejected absolute paths with a
POSIX-only test (`path.startswith("/")` plus `".." in
path.split("/")`). The test builds its absolute case with
`os.path.join(delivery_root, video_rel)`: on Linux that is
`/tmp/...` (refused), on Windows it is `D:\...` (accepted — no
leading `/`, no `/`-separated `..`), so the file verified and the
operation succeeded instead of refusing. The same POSIX-only
pattern existed in `validate_execution_artifact`; its test used a
hardcoded `/tmp/out.mp4`, so it passed on Windows while the hole
stayed open.

## Fix

One shared host-independent predicate, `is_safe_relative_path`
in `runtime/media_execution.py`, used by both validators. It
refuses any drive letter (`ntpath.splitdrive`), any absolute form
on either platform (`ntpath.isabs`), and any `..` segment under
either separator. Regression: seven new execution checks and
twelve new delivery predicate checks; the execution cases fail
pre-fix on Linux. Full record: corrections doc §10.

## Downloaded evidence

- Log archive `logs_124440581509.zip`, SHA-256
  `386488e3a060bc55ce7e96a411242f7ba44ca88b597cba2afd9eb6a8b9a9c8a4`
  (run-wide archive, suite endpoint `suites/124440581509/logs`).
- Artifact `p0-test-results.zip`, SHA-256
  `611ea945c21c8a392dbbdcdbc5047f66974b96d0f9efe38fe54d58f19a0d0b0d`
  (artifact ID 15196582473; matches the digest shown on the run page).

Both files are kept in `ci-evidence-p1-005/` with the extracted logs
under `logs-extracted-266/` (per-step files; the Windows jobs ran
all 16 steps this time).
