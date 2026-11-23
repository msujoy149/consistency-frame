#!/usr/bin/env bash
# P0 installer manifest-symlink tests (CF-WO-P0-003, §§1-2).
# Reproduces the critical temporary-manifest symlink vulnerability:
# the old code wrote the manifest to a predictable
# ".consistency-frame-manifest.json.tmp" with an ordinary open(), so a
# planted symlink there was followed and the outside target
# overwritten. The fix (scripts/atomic_write.py) creates the temp with
# tempfile.mkstemp() — exclusive, unique, never following a planted
# path — and replaces the target with os.replace().
# Each test asserts the outside canary is byte-for-byte unchanged, the
# final metadata file is a regular file (not a symlink), and no
# stale .cf-atomic-* temp files remain.
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
OUTSIDE="$TMP/outside"
mkdir -p "$SRC/skill-a" "$OUTSIDE"
printf -- '---\nname: skill-a\ndescription: Test skill A.\n---\n# Skill A v1\n' > "$SRC/skill-a/SKILL.md"
$SYNC --source-dir "$SRC" --dest-dir "$DEST" >/dev/null 2>&1
MANIFEST="$DEST/.consistency-frame-manifest.json"
LASTSYNC="$DEST/.consistency-frame-last-sync.json"

CANARY="$OUTSIDE/canary.txt"
printf 'CANARY-ORIGINAL-CONTENT\n' > "$CANARY"
CANARY_SHA="$(sha256sum "$CANARY" | awk '{print $1}')"

canary_unchanged() {  # $1 = label
  [ "$(sha256sum "$CANARY" | awk '{print $1}')" = "$CANARY_SHA" ] \
    && ok "$1: outside canary unchanged" \
    || bad "$1: outside canary unchanged"
}

no_stale_temps() {  # $1 = label
  [ -z "$(find "$TMP/dest" -name '.cf-atomic-*' -print -quit 2>/dev/null)" ] \
    && ok "$1: no stale .cf-atomic-* temp files" \
    || bad "$1: no stale .cf-atomic-* temp files"
}

regular_file() {  # $1 = path, $2 = label
  [ -f "$1" ] && [ ! -L "$1" ] \
    && ok "$2: final file is a regular file, not a symlink" \
    || bad "$2: final file is a regular file, not a symlink"
}

# --- SEC-MANIFEST-01: manifest temp symlink attack -----------------------
# Plant .consistency-frame-manifest.json.tmp -> canary, change the
# source skill, run the installer. The sync must succeed (the planted
# symlink is never touched), the canary must be untouched, and the
# final manifest must be a regular file with the new content.
ln -s "$CANARY" "$DEST/.consistency-frame-manifest.json.tmp"
printf -- '---\nname: skill-a\ndescription: Test skill A v2.\n---\n# Skill A v2\n' > "$SRC/skill-a/SKILL.md"
if $SYNC --source-dir "$SRC" --dest-dir "$DEST" >/tmp/m1.out 2>&1; then
  ok "SEC-MANIFEST-01: sync succeeds with planted manifest .tmp symlink"
else
  bad "SEC-MANIFEST-01: sync succeeds with planted manifest .tmp symlink"
fi
canary_unchanged "SEC-MANIFEST-01"
regular_file "$MANIFEST" "SEC-MANIFEST-01"
grep -q "skill-a/SKILL.md" "$MANIFEST" \
  && ok "SEC-MANIFEST-01: manifest content is correct" \
  || bad "SEC-MANIFEST-01: manifest content is correct"
grep -q '"status": "SUCCESS"' "$LASTSYNC" \
  && ok "SEC-MANIFEST-01: installer honestly reports SUCCESS" \
  || bad "SEC-MANIFEST-01: installer honestly reports SUCCESS"
[ -L "$DEST/.consistency-frame-manifest.json.tmp" ] \
  && ok "SEC-MANIFEST-01: planted symlink was never followed (still a link)" \
  || bad "SEC-MANIFEST-01: planted symlink was never followed (still a link)"
no_stale_temps "SEC-MANIFEST-01"

# --- SEC-MANIFEST-02: rollback temp symlink attack -----------------------
# A valid install + backup exist (v1 backed up by the v2 sync above).
# Plant the same temp symlink, roll back so update_manifest_hashes()
# runs; the canary must survive and the rollback must report honestly.
if $SYNC --dest-dir "$DEST" --rollback >/tmp/m2.out 2>&1; then
  ok "SEC-MANIFEST-02: rollback succeeds with planted manifest .tmp symlink"
else
  bad "SEC-MANIFEST-02: rollback succeeds with planted manifest .tmp symlink"
fi
grep -q "Rollback: restored 1 file(s)" /tmp/m2.out \
  && ok "SEC-MANIFEST-02: rollback reports an accurate result" \
  || bad "SEC-MANIFEST-02: rollback reports an accurate result"
canary_unchanged "SEC-MANIFEST-02"
regular_file "$MANIFEST" "SEC-MANIFEST-02"
grep -q "Skill A v1" "$DEST/skill-a/SKILL.md" \
  && ok "SEC-MANIFEST-02: rollback restored the v1 content" \
  || bad "SEC-MANIFEST-02: rollback restored the v1 content"
no_stale_temps "SEC-MANIFEST-02"

# --- SEC-MANIFEST-03: concurrent / repeated manifest writes -------------
# Repeated syncs (each rewrites the manifest) with the planted symlink
# still in place: independent temp files each time, canary untouched,
# no stale temps left behind — after success and after a failed run.
for i in 1 2 3; do
  printf -- '---\nname: skill-a\ndescription: Test skill A v%s.\n---\n# Skill A v%s\n' "$i" "$i" > "$SRC/skill-a/SKILL.md"
  $SYNC --source-dir "$SRC" --dest-dir "$DEST" >/dev/null 2>&1
done
canary_unchanged "SEC-MANIFEST-03"
regular_file "$MANIFEST" "SEC-MANIFEST-03"
no_stale_temps "SEC-MANIFEST-03"
# A failed run (corrupt manifest) must also leave no stale temps.
printf '{not json' > "$MANIFEST"
$SYNC --source-dir "$SRC" --dest-dir "$DEST" >/dev/null 2>&1 \
  && bad "SEC-MANIFEST-03: corrupt manifest still fails the sync" \
  || ok "SEC-MANIFEST-03: corrupt manifest still fails the sync"
no_stale_temps "SEC-MANIFEST-03 (after failed run)"
canary_unchanged "SEC-MANIFEST-03 (after failed run)"
rm -f "$MANIFEST"
$SYNC --source-dir "$SRC" --dest-dir "$DEST" >/dev/null 2>&1

# --- SEC-MANIFEST-04: last-sync metadata symlink -------------------------
# Plant a symlink AT .consistency-frame-last-sync.json pointing
# outside, run a normal sync. os.replace() must replace the symlink
# itself (never follow it): the outside target stays unchanged and
# the final metadata file is a regular file.
rm -f "$LASTSYNC"
ln -s "$CANARY" "$LASTSYNC"
printf -- '---\nname: skill-a\ndescription: Test skill A final.\n---\n# Skill A final\n' > "$SRC/skill-a/SKILL.md"
if $SYNC --source-dir "$SRC" --dest-dir "$DEST" >/dev/null 2>&1; then
  ok "SEC-MANIFEST-04: sync succeeds with planted last-sync symlink"
else
  bad "SEC-MANIFEST-04: sync succeeds with planted last-sync symlink"
fi
canary_unchanged "SEC-MANIFEST-04"
regular_file "$LASTSYNC" "SEC-MANIFEST-04"
grep -q '"status": "SUCCESS"' "$LASTSYNC" \
  && ok "SEC-MANIFEST-04: last-sync metadata written atomically, status SUCCESS" \
  || bad "SEC-MANIFEST-04: last-sync metadata written atomically, status SUCCESS"
no_stale_temps "SEC-MANIFEST-04"

echo "test_installer_manifest_security: $([ "$FAILURES" = 0 ] && echo PASS || echo FAIL) ($FAILURES failure(s))"
exit "$([ "$FAILURES" = 0 ] && echo 0 || echo 1)"
