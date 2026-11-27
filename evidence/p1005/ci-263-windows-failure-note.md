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
