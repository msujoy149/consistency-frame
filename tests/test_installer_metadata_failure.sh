#!/usr/bin/env bash
# P0 installer final-metadata failure test (CF-WO-P0-004, §1 / P0-003-01).
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
# This is a true installer integration test: it executes
# scripts/sync-skills.sh and verifies its externally visible
# behaviour (stdout, stderr, exit code, files left behind).
# Uses isolated temporary fixtures only — never touches the real repo
# or the real .agents/skills directory.
# Exit 0 = PASS, 1 = FAIL.
set -uo pipefail

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

echo "test_installer_metadata_failure: $([ "$FAILURES" = 0 ] && echo PASS || echo FAIL) ($FAILURES failure(s))"
exit "$([ "$FAILURES" = 0 ] && echo 0 || echo 1)"
