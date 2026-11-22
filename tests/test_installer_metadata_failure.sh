#!/usr/bin/env bash
# P0 installer final-metadata failure tests (CF-WO-P0-004, §1 / P0-003-01;
# extended by CF-WO-P0-005 with the no-change and failed-no-backup cases).
# Reproduces the false-SUCCESS bug: the old code called
# write_result_json() without checking its return code, so when the
# final metadata replacement failed (here forced by making
# .consistency-frame-last-sync.json a directory, which makes the
# atomic write fail with IsADirectoryError), the installer still
# printed "Skill sync SUCCESS" and exited 0 — even though the sync
# status record was never persisted. The script runs under
# `set -uo pipefail`, not `set -e`, so the unchecked call fell through.
# The fix (scripts/sync-skills.sh) checks the return code explicitly:
# changes already applied + metadata failure => PARTIAL, exit 2, with
# a clear diagnostic and the recovery backup preserved; no changes
# applied + metadata failure => FAILED, exit 1. No error path may
# print a false SUCCESS, and no backup run directory is removed
# before final status persistence has succeeded.
# CF-WO-P0-005: the failure diagnostics must also describe the backup
# state accurately. Backups are created only for replaced or pruned
# files, so a run that only installed new files, or changed nothing,
# has no content backup to recover — the diagnostics say "no content
# backup was created" and describe the retained run directory as a
# run record (owner marker only), never as a recovery backup.
# This is a true installer integration test: it executes
# scripts/sync-skills.sh and verifies its externally visible
# behaviour (stdout, stderr, exit code, files left behind).
# Uses isolated temporary fixtures only — never touches the real repo
# or the real .agents/skills directory.
# Usage: bash tests/test_installer_metadata_failure.sh [changed|no-change|failed-no-backup]
#   changed (default): SEC-METADATA-05, metadata failure after changes.
#   no-change:         SEC-METADATA-06, metadata failure, no files changed.
#   failed-no-backup:  SEC-METADATA-07, file-operation failure with no
#                      content backup + metadata failure.
# Exit 0 = PASS, 1 = FAIL.
set -uo pipefail

MODE="${1:-changed}"
case "$MODE" in
  changed|no-change|failed-no-backup) ;;
  *) echo "unknown mode: $MODE (expected changed|no-change|failed-no-backup)" >&2; exit 2 ;;
esac

SYNC="bash $PWD/scripts/sync-skills.sh"
FAILURES=0
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

ok()   { echo "PASS $1"; }
bad()  { echo "FAIL $1"; FAILURES=$((FAILURES + 1)); }

SRC="$TMP/src/skills"
DEST="$TMP/dest/skills"
BACKUP="$(dirname "$DEST")/skills-backup"
mkdir -p "$SRC/skill-a"
LASTSYNC="$DEST/.consistency-frame-last-sync.json"

# --- Setup: initial successful install of skill-a v1 ---------------------
printf -- '---\nname: skill-a\ndescription: Test skill A.\n---\n# Skill A v1\n' > "$SRC/skill-a/SKILL.md"
if $SYNC --source-dir "$SRC" --dest-dir "$DEST" >/dev/null 2>&1; then
  ok "SEC-METADATA-05 setup: initial install succeeds"
else
  bad "SEC-METADATA-05 setup: initial install succeeds"
fi

if [ "$MODE" = "changed" ]; then
# --- SEC-METADATA-05: final metadata write fails after changes -----------
# Change the source skill so the next sync must replace the installed
# file (and therefore back the original up), then force the final
# metadata replacement to fail by making last-sync.json a directory.
printf -- '---\nname: skill-a\ndescription: Test skill A v2.\n---\n# Skill A v2\n' > "$SRC/skill-a/SKILL.md"
rm -f "$LASTSYNC"
mkdir "$LASTSYNC"
set +e
$SYNC --source-dir "$SRC" --dest-dir "$DEST" >"$TMP/sync.out" 2>&1
SYNC_CODE=$?
[ "$SYNC_CODE" = 2 ] \
  && ok "SEC-METADATA-05: installer returns exit code 2 (PARTIAL, changes applied)" \
  || bad "SEC-METADATA-05: installer returns exit code 2 (PARTIAL, changes applied) (got $SYNC_CODE)"
[ "$SYNC_CODE" = 0 ] \
  && bad "SEC-METADATA-05: installer must NOT return 0 on metadata failure" \
  || ok "SEC-METADATA-05: installer does not return 0 on metadata failure"
if grep -q "Skill sync SUCCESS" "$TMP/sync.out"; then
  bad "SEC-METADATA-05: installer does NOT print a false SUCCESS"
else
  ok "SEC-METADATA-05: installer does NOT print a false SUCCESS"
fi
grep -q "Skill sync PARTIAL" "$TMP/sync.out" \
  && ok "SEC-METADATA-05: installer reports PARTIAL" \
  || bad "SEC-METADATA-05: installer reports PARTIAL"
grep -q "final metadata record could not be written" "$TMP/sync.out" \
  && ok "SEC-METADATA-05: diagnostic explains the failed final metadata write" \
  || bad "SEC-METADATA-05: diagnostic explains the failed final metadata write"
grep -q "backup preserved" "$TMP/sync.out" \
  && ok "SEC-METADATA-05: diagnostic says the recovery backup is preserved" \
  || bad "SEC-METADATA-05: diagnostic says the recovery backup is preserved"
grep -q "sync changes were applied" "$TMP/sync.out" \
  && ok "SEC-METADATA-05: diagnostic says the sync changes were applied" \
  || bad "SEC-METADATA-05: diagnostic says the sync changes were applied"
# The updated skill content may be present (the file copy succeeded).
grep -q "Skill A v2" "$DEST/skill-a/SKILL.md" \
  && ok "SEC-METADATA-05: updated skill content is installed" \
  || bad "SEC-METADATA-05: updated skill content is installed"
# The previous content must remain recoverable from the preserved
# backup: find a run dir holding the v1 file.
BACKED_V1=""
for d in "$BACKUP"/run-*; do
  [ -d "$d" ] || continue
  if [ -f "$d/skill-a/SKILL.md" ] && grep -q "Skill A v1" "$d/skill-a/SKILL.md"; then
    BACKED_V1="$d"
  fi
done
[ -n "$BACKED_V1" ] \
  && ok "SEC-METADATA-05: previous content recoverable from preserved backup ($BACKED_V1)" \
  || bad "SEC-METADATA-05: previous content recoverable from preserved backup"
# The backup run directory and its valid owner marker must still exist.
[ -n "$BACKED_V1" ] && [ -d "$BACKED_V1" ] \
  && ok "SEC-METADATA-05: backup run directory still exists" \
  || bad "SEC-METADATA-05: backup run directory still exists"
if [ -n "$BACKED_V1" ]; then
  python3 - "$BACKED_V1" "$DEST" <<'PYEOF'
import json, os, sys
d, dest = sys.argv[1], sys.argv[2]
try:
    with open(os.path.join(d, ".run-owner.json"), encoding="utf-8") as f:
        m = json.load(f)
    assert isinstance(m, dict)
    assert m.get("dest_dir") == dest
    assert m.get("run_id") == os.path.basename(os.path.normpath(d))
    assert isinstance(m.get("created_utc"), str)
except Exception:
    sys.exit(1)
sys.exit(0)
PYEOF
  [ $? = 0 ] \
    && ok "SEC-METADATA-05: backup owner marker is valid for this destination" \
    || bad "SEC-METADATA-05: backup owner marker is valid for this destination"
else
  bad "SEC-METADATA-05: backup owner marker is valid for this destination"
fi
# No atomic-write temp files may remain after the failed operation.
[ -z "$(find "$TMP/dest" -name '.cf-atomic-*' -print -quit 2>/dev/null)" ] \
  && ok "SEC-METADATA-05: no stale .cf-atomic-* temp files" \
  || bad "SEC-METADATA-05: no stale .cf-atomic-* temp files"
fi # MODE = changed

if [ "$MODE" = "no-change" ]; then
# --- SEC-METADATA-06: final metadata write fails, no files changed -------
# P0-005: run the same sync again with no source changes, so there are
# no new, changed or pruned files, then force the final metadata
# replacement to fail by making last-sync.json a directory. The
# installer must report FAILED with exit 1, state clearly that no
# files were changed, and must NOT claim a content recovery backup
# exists — no backup was created, only the run record (owner marker)
# is retained.
rm -f "$LASTSYNC"
mkdir "$LASTSYNC"
set +e
$SYNC --source-dir "$SRC" --dest-dir "$DEST" >"$TMP/sync2.out" 2>&1
SYNC_CODE=$?
[ "$SYNC_CODE" = 1 ] \
  && ok "SEC-METADATA-06: installer returns exit code 1 (FAILED, no files changed)" \
  || bad "SEC-METADATA-06: installer returns exit code 1 (FAILED, no files changed) (got $SYNC_CODE)"
[ "$SYNC_CODE" = 0 ] \
  && bad "SEC-METADATA-06: installer must NOT return 0 on metadata failure" \
  || ok "SEC-METADATA-06: installer does not return 0 on metadata failure"
if grep -q "Skill sync SUCCESS" "$TMP/sync2.out"; then
  bad "SEC-METADATA-06: installer does NOT print a false SUCCESS"
else
  ok "SEC-METADATA-06: installer does NOT print a false SUCCESS"
fi
grep -q "Skill sync FAILED" "$TMP/sync2.out" \
  && ok "SEC-METADATA-06: installer reports FAILED" \
  || bad "SEC-METADATA-06: installer reports FAILED"
grep -q "no files were changed" "$TMP/sync2.out" \
  && ok "SEC-METADATA-06: diagnostic confirms no files were changed" \
  || bad "SEC-METADATA-06: diagnostic confirms no files were changed"
grep -q "no content backup was created" "$TMP/sync2.out" \
  && ok "SEC-METADATA-06: diagnostic says no content backup was created" \
  || bad "SEC-METADATA-06: diagnostic says no content backup was created"
grep -q "run record retained" "$TMP/sync2.out" \
  && ok "SEC-METADATA-06: diagnostic says the run record is retained" \
  || bad "SEC-METADATA-06: diagnostic says the run record is retained"
if grep -q "backup preserved" "$TMP/sync2.out"; then
  bad "SEC-METADATA-06: diagnostic does NOT claim a backup is preserved"
else
  ok "SEC-METADATA-06: diagnostic does NOT claim a backup is preserved"
fi
if grep -q "recovery backup" "$TMP/sync2.out"; then
  bad "SEC-METADATA-06: diagnostic does NOT claim a recovery backup exists"
else
  ok "SEC-METADATA-06: diagnostic does NOT claim a recovery backup exists"
fi
# The retained run directory is the one named in the diagnostic.
RUN_DIR2="$(grep -o "run record retained at [^ ]*" "$TMP/sync2.out" | awk '{print $NF}')"
[ -n "$RUN_DIR2" ] && [ -d "$RUN_DIR2" ] \
  && ok "SEC-METADATA-06: run metadata directory is retained ($RUN_DIR2)" \
  || bad "SEC-METADATA-06: run metadata directory is retained"
if [ -n "$RUN_DIR2" ] && [ -d "$RUN_DIR2" ]; then
  python3 - "$RUN_DIR2" "$DEST" <<'PYEOF'
import json, os, sys
d, dest = sys.argv[1], sys.argv[2]
try:
    with open(os.path.join(d, ".run-owner.json"), encoding="utf-8") as f:
        m = json.load(f)
    assert isinstance(m, dict)
    assert m.get("dest_dir") == dest
    assert m.get("run_id") == os.path.basename(os.path.normpath(d))
    assert isinstance(m.get("created_utc"), str)
except Exception:
    sys.exit(1)
sys.exit(0)
PYEOF
  [ $? = 0 ] \
    && ok "SEC-METADATA-06: run owner marker is valid for this destination" \
    || bad "SEC-METADATA-06: run owner marker is valid for this destination"
  # The retained run directory must hold no content backup files:
  # only the owner marker and the lock.
  [ -z "$(find "$RUN_DIR2" -type f ! -name '.run-owner.json' ! -name '.lock' -print -quit 2>/dev/null)" ] \
    && ok "SEC-METADATA-06: retained run directory holds no content backup files" \
    || bad "SEC-METADATA-06: retained run directory holds no content backup files"
else
  bad "SEC-METADATA-06: run owner marker is valid for this destination"
  bad "SEC-METADATA-06: retained run directory holds no content backup files"
fi
# No atomic-write temp files may remain after the failed operation.
[ -z "$(find "$TMP/dest" -name '.cf-atomic-*' -print -quit 2>/dev/null)" ] \
  && ok "SEC-METADATA-06: no stale .cf-atomic-* temp files" \
  || bad "SEC-METADATA-06: no stale .cf-atomic-* temp files"
fi # MODE = no-change

if [ "$MODE" = "failed-no-backup" ]; then
# --- SEC-METADATA-07: file-operation failure with no content backup ------
# P0-005: review of the earlier failed=1 path. Force a file-operation
# failure with no content backup (the destination holds skill-a as a
# regular file, so the copy cannot create its directory) AND force
# the final metadata write to fail (last-sync.json as a directory).
# The installer must report FAILED with exit 1 and must not claim a
# recovery backup exists anywhere in its diagnostics.
SRC2="$TMP/src2/skills"
DEST2="$TMP/dest2/skills"
BACKUP2="$(dirname "$DEST2")/skills-backup"
mkdir -p "$SRC2/skill-a" "$DEST2"
printf -- '---\nname: skill-a\ndescription: Test skill A.\n---\n# Skill A v1\n' > "$SRC2/skill-a/SKILL.md"
printf 'not a directory' > "$DEST2/skill-a"
mkdir "$DEST2/.consistency-frame-last-sync.json"
set +e
$SYNC --source-dir "$SRC2" --dest-dir "$DEST2" >"$TMP/sync3.out" 2>&1
SYNC_CODE=$?
[ "$SYNC_CODE" = 1 ] \
  && ok "SEC-METADATA-07: installer returns exit code 1 (FAILED)" \
  || bad "SEC-METADATA-07: installer returns exit code 1 (FAILED) (got $SYNC_CODE)"
[ "$SYNC_CODE" = 0 ] \
  && bad "SEC-METADATA-07: installer must NOT return 0 on failure" \
  || ok "SEC-METADATA-07: installer does not return 0 on failure"
if grep -q "Skill sync SUCCESS" "$TMP/sync3.out"; then
  bad "SEC-METADATA-07: installer does NOT print a false SUCCESS"
else
  ok "SEC-METADATA-07: installer does NOT print a false SUCCESS"
fi
grep -q "no content backup was created for this run, nothing to restore" "$TMP/sync3.out" \
  && ok "SEC-METADATA-07: diagnostic says no content backup was created, nothing to restore" \
  || bad "SEC-METADATA-07: diagnostic says no content backup was created, nothing to restore"
grep -q "no content backup was created for this run; run record retained" "$TMP/sync3.out" \
  && ok "SEC-METADATA-07: nested diagnostic says no content backup was created, run record retained" \
  || bad "SEC-METADATA-07: nested diagnostic says no content backup was created, run record retained"
if grep -q "restoring from this run's backup" "$TMP/sync3.out"; then
  bad "SEC-METADATA-07: diagnostic does NOT claim to restore from a backup"
else
  ok "SEC-METADATA-07: diagnostic does NOT claim to restore from a backup"
fi
if grep -q "recovery backup" "$TMP/sync3.out"; then
  bad "SEC-METADATA-07: diagnostic does NOT claim a recovery backup exists"
else
  ok "SEC-METADATA-07: diagnostic does NOT claim a recovery backup exists"
fi
# No atomic-write temp files may remain after the failed operation.
[ -z "$(find "$TMP/dest2" -name '.cf-atomic-*' -print -quit 2>/dev/null)" ] \
  && ok "SEC-METADATA-07: no stale .cf-atomic-* temp files" \
  || bad "SEC-METADATA-07: no stale .cf-atomic-* temp files"
fi # MODE = failed-no-backup

echo "test_installer_metadata_failure: $([ "$FAILURES" = 0 ] && echo PASS || echo FAIL) ($FAILURES failure(s))"
exit "$([ "$FAILURES" = 0 ] && echo 0 || echo 1)"
