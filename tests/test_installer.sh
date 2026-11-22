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

echo "test_installer: $([ "$FAILURES" = 0 ] && echo PASS || echo FAIL) ($FAILURES failure(s))"
exit "$([ "$FAILURES" = 0 ] && echo 0 || echo 1)"
