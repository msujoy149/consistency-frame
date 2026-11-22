#!/usr/bin/env bash
# P0 installer tests (CF-INT-014, CF-INT-015-partial).
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
mkdir -p "$SRC/skill-a" "$SRC/skill-b"

cat > "$SRC/skill-a/SKILL.md" <<'EOF'
---
name: skill-a
description: Test skill A.
---
# Skill A
## First section
EOF
cat > "$SRC/skill-b/SKILL.md" <<'EOF'
---
name: skill-b
description: Test skill B.
---
# Skill B
## First section
EOF

# 1. Fresh sync succeeds and installs owned skills.
if $SYNC --source-dir "$SRC" --dest-dir "$DEST" >/dev/null 2>&1; then ok "fresh sync succeeds"; else bad "fresh sync succeeds"; fi
[ -f "$DEST/skill-a/SKILL.md" ] && [ -f "$DEST/skill-b/SKILL.md" ] \
  && ok "owned skills installed" || bad "owned skills installed"
[ -f "$DEST/.consistency-frame-manifest.json" ] \
  && ok "manifest written" || bad "manifest written"

# 2. CF-INT-014: unmanaged custom skill survives install/update.
mkdir -p "$DEST/my-custom"
printf 'MY CUSTOM SKILL — DO NOT DELETE\n' > "$DEST/my-custom/SKILL.md"
printf -- '---\nname: skill-a\ndescription: Test skill A v2.\n---\n# Skill A v2\n## First section\n' > "$SRC/skill-a/SKILL.md"
if $SYNC --source-dir "$SRC" --dest-dir "$DEST" >/dev/null 2>&1; then ok "update sync succeeds"; else bad "update sync succeeds"; fi
grep -q "DO NOT DELETE" "$DEST/my-custom/SKILL.md" \
  && ok "CF-INT-014: unmanaged skill survives update" || bad "CF-INT-014: unmanaged skill survives update"
grep -q "Skill A v2" "$DEST/skill-a/SKILL.md" \
  && ok "owned skill updates correctly" || bad "owned skill updates correctly"

# 3. Idempotency: a second run changes nothing.
OUT2="$($SYNC --source-dir "$SRC" --dest-dir "$DEST" 2>&1)"
echo "$OUT2" | grep -q "new=0 changed=0" \
  && ok "idempotent re-run (new=0 changed=0)" || bad "idempotent re-run (new=0 changed=0)"

# 4. No prune by default; dry-run prune lists only stale owned files.
rm -rf "$SRC/skill-b"
$SYNC --source-dir "$SRC" --dest-dir "$DEST" >/dev/null 2>&1
[ -f "$DEST/skill-b/SKILL.md" ] \
  && ok "no prune by default (stale owned file kept)" || bad "no prune by default (stale owned file kept)"
DRY="$($SYNC --source-dir "$SRC" --dest-dir "$DEST" --dry-run --prune 2>&1)"
echo "$DRY" | grep -q "skill-b/SKILL.md" \
  && ok "dry-run prune lists stale owned file" || bad "dry-run prune lists stale owned file"
[ -f "$DEST/skill-b/SKILL.md" ] \
  && ok "dry-run changes nothing" || bad "dry-run changes nothing"
$SYNC --source-dir "$SRC" --dest-dir "$DEST" --prune >/dev/null 2>&1
[ ! -f "$DEST/skill-b/SKILL.md" ] \
  && ok "explicit --prune removes stale owned file" || bad "explicit --prune removes stale owned file"
grep -q "DO NOT DELETE" "$DEST/my-custom/SKILL.md" \
  && ok "prune never touches unmanaged files" || bad "prune never touches unmanaged files"

# 5. Backup + rollback: update an owned file (backup keeps the old
# version), corrupt it, roll back to the backup.
printf -- '---\nname: skill-a\ndescription: Test skill A v3.\n---\n# Skill A v3\n## First section\n' > "$SRC/skill-a/SKILL.md"
$SYNC --source-dir "$SRC" --dest-dir "$DEST" >/dev/null 2>&1
grep -q "Skill A v3" "$DEST/skill-a/SKILL.md" \
  && ok "owned skill updates to v3" || bad "owned skill updates to v3"
printf 'CORRUPTED\n' > "$DEST/skill-a/SKILL.md"
if $SYNC --dest-dir "$DEST" --rollback >/dev/null 2>&1; then ok "rollback runs"; else bad "rollback runs"; fi
grep -q "Skill A v2" "$DEST/skill-a/SKILL.md" \
  && ok "rollback restores owned file from backup" || bad "rollback restores owned file from backup"

# 6. Symlink / traversal rejection: a source symlink escaping the tree fails.
ln -s /etc/passwd "$SRC/skill-a/evil-link"
if $SYNC --source-dir "$SRC" --dest-dir "$DEST" >/dev/null 2>&1; then bad "symlink escape is rejected"; else ok "symlink escape is rejected"; fi
rm -f "$SRC/skill-a/evil-link"

# 7. Failed dependency reports FAILED (missing source dir).
if $SYNC --source-dir "$TMP/does-not-exist" --dest-dir "$DEST" >/dev/null 2>&1; then bad "missing source reports FAILED"; else ok "missing source reports FAILED"; fi

# 8. Unsafe destination root is rejected.
if $SYNC --source-dir "$SRC" --dest-dir "/" >/dev/null 2>&1; then bad "unsafe destination root rejected"; else ok "unsafe destination root rejected"; fi

# 9. setup.sh dry-run (core-only) succeeds in the real repo without changes.
if bash setup.sh --dry-run >/dev/null 2>&1; then ok "setup.sh --dry-run succeeds"; else bad "setup.sh --dry-run succeeds"; fi

# 10. CF-WO-P0-002 §2: a user-modified managed file is preserved by
# default, and the conflict is recorded in the last-sync JSON.
$SYNC --source-dir "$SRC" --dest-dir "$DEST" >/dev/null 2>&1
printf 'USER EDIT — DO NOT OVERWRITE\n' > "$DEST/skill-a/SKILL.md"
if $SYNC --source-dir "$SRC" --dest-dir "$DEST" >/dev/null 2>&1; then ok "conflict sync still succeeds"; else bad "conflict sync still succeeds"; fi
grep -q "USER EDIT" "$DEST/skill-a/SKILL.md" \
  && ok "user-modified managed file preserved by default" || bad "user-modified managed file preserved by default"
if python3 - "$DEST/.consistency-frame-last-sync.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
assert d["conflict_policy"] == "keep", d
assert d["conflict_count"] == 1, d
c = d["conflicts"][0]
assert c["path"] == "skill-a/SKILL.md", c
assert c["current_sha256"] and c["source_sha256"] and c["manifest_sha256"], c
assert c["current_sha256"] != c["source_sha256"], c
PYEOF
then ok "conflict recorded in last-sync JSON"; else bad "conflict recorded in last-sync JSON"; fi

# 11. --conflict overwrite replaces the user-modified file.
if $SYNC --source-dir "$SRC" --dest-dir "$DEST" --conflict overwrite >/dev/null 2>&1; then ok "overwrite sync succeeds"; else bad "overwrite sync succeeds"; fi
grep -q "Skill A v3" "$DEST/skill-a/SKILL.md" \
  && ok "--conflict overwrite overwrites the file" || bad "--conflict overwrite overwrites the file"
if python3 - "$DEST/.consistency-frame-last-sync.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
assert d["conflict_policy"] == "overwrite", d
assert any(c["path"] == "skill-a/SKILL.md" for c in d["conflicts"]), d
PYEOF
then ok "overwrite run records policy + conflict"; else bad "overwrite run records policy + conflict"; fi

# 12. Prune refuses a user-modified stale file (and records it).
mkdir -p "$SRC/skill-c"
printf -- '---\nname: skill-c\ndescription: Test skill C.\n---\n# Skill C\n' > "$SRC/skill-c/SKILL.md"
$SYNC --source-dir "$SRC" --dest-dir "$DEST" >/dev/null 2>&1
rm -rf "$SRC/skill-c"
printf 'USER EDIT OF STALE SKILL C\n' > "$DEST/skill-c/SKILL.md"
$SYNC --source-dir "$SRC" --dest-dir "$DEST" --prune >/dev/null 2>&1
grep -q "USER EDIT OF STALE SKILL C" "$DEST/skill-c/SKILL.md" \
  && ok "prune refuses a user-modified stale file" || bad "prune refuses a user-modified stale file"
if python3 - "$DEST/.consistency-frame-last-sync.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
assert d["prune_refused_count"] == 1, d
assert d["prune_refused"][0]["path"] == "skill-c/SKILL.md", d
PYEOF
then ok "prune refusal recorded in last-sync JSON"; else bad "prune refusal recorded in last-sync JSON"; fi

# 13. Rollback restores v2 -> v3 -> v2, twice in a row.
printf -- '---\nname: skill-a\ndescription: Test skill A v2.\n---\n# Skill A v2\n' > "$SRC/skill-a/SKILL.md"
$SYNC --source-dir "$SRC" --dest-dir "$DEST" >/dev/null 2>&1
grep -q "Skill A v2" "$DEST/skill-a/SKILL.md" \
  && ok "rollback test: back to v2" || bad "rollback test: back to v2"
printf -- '---\nname: skill-a\ndescription: Test skill A v3.\n---\n# Skill A v3\n' > "$SRC/skill-a/SKILL.md"
$SYNC --source-dir "$SRC" --dest-dir "$DEST" >/dev/null 2>&1
printf 'CORRUPTED\n' > "$DEST/skill-a/SKILL.md"
$SYNC --dest-dir "$DEST" --rollback >/dev/null 2>&1
grep -q "Skill A v2" "$DEST/skill-a/SKILL.md" \
  && ok "rollback restores v2 after update to v3" || bad "rollback restores v2 after update to v3"
$SYNC --source-dir "$SRC" --dest-dir "$DEST" >/dev/null 2>&1
grep -q "Skill A v3" "$DEST/skill-a/SKILL.md" \
  && ok "rollback test: re-apply v3 succeeds" || bad "rollback test: re-apply v3 succeeds"
$SYNC --dest-dir "$DEST" --rollback >/dev/null 2>&1
grep -q "Skill A v2" "$DEST/skill-a/SKILL.md" \
  && ok "second rollback restores v2 again" || bad "second rollback restores v2 again"

# 14. Five rapid repeated installs all succeed with distinct backup
# dirs and no clobbering.
BACKUP_PARENT="$(dirname "$DEST")/skills-backup"
count_runs() { ls -d "$BACKUP_PARENT"/run-*/ 2>/dev/null | wc -l | tr -d ' '; }
BEFORE_RUNS="$(count_runs)"
RAPID_OK=1
for i in 1 2 3 4 5; do
  printf -- '---\nname: skill-a\ndescription: Test skill A rapid-%s.\n---\n# Skill A rapid-%s\n' "$i" "$i" > "$SRC/skill-a/SKILL.md"
  $SYNC --source-dir "$SRC" --dest-dir "$DEST" >/dev/null 2>&1 || RAPID_OK=0
done
[ "$RAPID_OK" = 1 ] && ok "five rapid installs all succeed" || bad "five rapid installs all succeed"
AFTER_RUNS="$(count_runs)"
[ "$((AFTER_RUNS - BEFORE_RUNS))" = 5 ] \
  && ok "five rapid installs create five distinct backup dirs" \
  || bad "five rapid installs create five distinct backup dirs (before=$BEFORE_RUNS after=$AFTER_RUNS)"
grep -q "Skill A rapid-5" "$DEST/skill-a/SKILL.md" \
  && ok "rapid installs end at the latest version" || bad "rapid installs end at the latest version"
# Every run dir created in the loop carries a valid owner marker.
MARKERS_OK=1
for d in "$BACKUP_PARENT"/run-*/; do
  [ -f "$d/.run-owner.json" ] || MARKERS_OK=0
done
[ "$MARKERS_OK" = 1 ] && ok "every run dir carries an owner marker" || bad "every run dir carries an owner marker"

# 15. Two interleaved run dirs cannot delete each other's backups:
# --prune-backups removes only this destination's old, unlocked runs.
OLD_UTC="$(date -u -d '30 days ago' +%Y-%m-%dT%H:%M:%SZ)"
NOW_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
mk_run_fixture() {  # $1 = dir name, $2 = dest_dir, $3 = created_utc, $4 = lock? (1/0)
  mkdir -p "$BACKUP_PARENT/$1"
  printf '{"created_utc": "%s", "dest_dir": "%s", "run_id": "%s"}' "$3" "$2" "$1" > "$BACKUP_PARENT/$1/.run-owner.json"
  [ "$4" = 1 ] && : > "$BACKUP_PARENT/$1/.lock"
}
mk_run_fixture "run-FIXOLD" "$DEST" "$OLD_UTC" 0
mk_run_fixture "run-FIXNEW" "$DEST" "$NOW_UTC" 0
mk_run_fixture "run-FIXFOREIGN" "/tmp/some-other-dest" "$OLD_UTC" 0
mk_run_fixture "run-FIXLOCKED" "$DEST" "$OLD_UTC" 1
if $SYNC --dest-dir "$DEST" --prune-backups 7 >/dev/null 2>&1; then ok "--prune-backups runs"; else bad "--prune-backups runs"; fi
[ ! -d "$BACKUP_PARENT/run-FIXOLD" ] \
  && ok "prune-backups removes this dest's old run dir" || bad "prune-backups removes this dest's old run dir"
[ -d "$BACKUP_PARENT/run-FIXNEW" ] \
  && ok "prune-backups keeps this dest's fresh run dir" || bad "prune-backups keeps this dest's fresh run dir"
[ -d "$BACKUP_PARENT/run-FIXFOREIGN" ] \
  && ok "prune-backups never touches a foreign run dir" || bad "prune-backups never touches a foreign run dir"
[ -d "$BACKUP_PARENT/run-FIXLOCKED" ] \
  && ok "prune-backups skips a locked run dir" || bad "prune-backups skips a locked run dir"

echo "test_installer: $([ "$FAILURES" = 0 ] && echo PASS || echo FAIL) ($FAILURES failure(s))"
exit "$([ "$FAILURES" = 0 ] && echo 0 || echo 1)"
