#!/usr/bin/env bash
# P0 installer security tests (CF-WO-P0-002, §§1-3).
# Attack / misuse cases for scripts/sync-skills.sh: each test asserts the
# attack is REJECTED (non-zero exit and/or no write outside the intended
# destination), not merely that the happy path works.
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

# Shared fixture: a minimal valid source tree and a synced destination.
SRC="$TMP/src/skills"
DEST="$TMP/dest/skills"
mkdir -p "$SRC/skill-a"
printf -- '---\nname: skill-a\ndescription: Test skill A.\n---\n# Skill A\n' > "$SRC/skill-a/SKILL.md"
$SYNC --source-dir "$SRC" --dest-dir "$DEST" >/dev/null 2>&1
MANIFEST="$DEST/.consistency-frame-manifest.json"

# Helper: rewrite the manifest from a literal JSON file, run a sync, and
# require failure. $1 = test label, $2 = manifest file to install.
expect_manifest_rejected() {
  local label="$1" bad_manifest="$2"
  cp "$bad_manifest" "$MANIFEST"
  if $SYNC --source-dir "$SRC" --dest-dir "$DEST" >/dev/null 2>&1; then
    bad "$label"
  else
    ok "$label"
  fi
  # Restore a known-good manifest by re-syncing from a clean state.
  rm -f "$MANIFEST"
  $SYNC --source-dir "$SRC" --dest-dir "$DEST" >/dev/null 2>&1
}

SHA_A="$(sha256sum "$SRC/skill-a/SKILL.md" | awk '{print $1}')"

# SEC-01: destination-parent symlink attack — the destination's parent is
# a symlink into another tree, so the sync must be refused and nothing
# may be written into that other tree.
mkdir -p "$TMP/real"
ln -s "$TMP/real" "$TMP/link"
if $SYNC --source-dir "$SRC" --dest-dir "$TMP/link/skills" >/dev/null 2>&1; then
  bad "SEC-01: dest-parent symlink attack is refused"
else
  [ ! -e "$TMP/real/skills" ] \
    && ok "SEC-01: dest-parent symlink attack is refused" \
    || bad "SEC-01: dest-parent symlink attack is refused (wrote outside)"
fi

# SEC-01b: the destination path itself is a symlink into another tree.
ln -s "$TMP/real" "$TMP/dest-link"
if $SYNC --source-dir "$SRC" --dest-dir "$TMP/dest-link" >/dev/null 2>&1; then
  bad "SEC-01b: symlinked destination itself is refused"
else
  [ ! -e "$TMP/real/skill-a" ] \
    && ok "SEC-01b: symlinked destination itself is refused" \
    || bad "SEC-01b: symlinked destination itself is refused (wrote outside)"
fi

# SEC-02: manifest "../" traversal entry -> FAILED, nothing written.
printf '{"version": 1, "owned": {"../evil": "%s", "skill-a/SKILL.md": "%s"}}' \
  "$SHA_A" "$SHA_A" > "$TMP/bad-traversal.json"
cp "$TMP/bad-traversal.json" "$MANIFEST"
if $SYNC --source-dir "$SRC" --dest-dir "$DEST" >/dev/null 2>&1; then
  bad "SEC-02: manifest ../ traversal entry is rejected"
else
  [ ! -e "$TMP/dest/evil" ] && [ ! -e "$TMP/evil" ] \
    && ok "SEC-02: manifest ../ traversal entry is rejected" \
    || bad "SEC-02: manifest ../ traversal entry is rejected (wrote outside)"
fi
rm -f "$MANIFEST"
$SYNC --source-dir "$SRC" --dest-dir "$DEST" >/dev/null 2>&1

# SEC-03: absolute path entry in the manifest -> FAILED.
printf '{"version": 1, "owned": {"/tmp/evil-abs": "%s", "skill-a/SKILL.md": "%s"}}' \
  "$SHA_A" "$SHA_A" > "$TMP/bad-absolute.json"
expect_manifest_rejected "SEC-03: manifest absolute-path entry is rejected" "$TMP/bad-absolute.json"
[ ! -e "/tmp/evil-abs" ] && ok "SEC-03: nothing written outside" || bad "SEC-03: nothing written outside"

# SEC-04a: corrupted manifest — invalid JSON -> FAILED.
printf '{not json' > "$TMP/bad-json.json"
expect_manifest_rejected "SEC-04a: manifest invalid JSON is rejected" "$TMP/bad-json.json"

# SEC-04b: corrupted manifest — wrong types (owned as a list) -> FAILED.
printf '{"version": 1, "owned": ["skill-a/SKILL.md"]}' > "$TMP/bad-owned-list.json"
expect_manifest_rejected "SEC-04b: manifest owned-as-list is rejected" "$TMP/bad-owned-list.json"

# SEC-04c: corrupted manifest — wrong types (sha as a number) -> FAILED.
printf '{"version": 1, "owned": {"skill-a/SKILL.md": 12345}}' > "$TMP/bad-sha-number.json"
expect_manifest_rejected "SEC-04c: manifest numeric sha is rejected" "$TMP/bad-sha-number.json"

# SEC-04d: corrupted manifest — version != 1 -> FAILED.
printf '{"version": 2, "owned": {"skill-a/SKILL.md": "%s"}}' "$SHA_A" > "$TMP/bad-version.json"
expect_manifest_rejected "SEC-04d: manifest version != 1 is rejected" "$TMP/bad-version.json"

# SEC-05: duplicate manifest entries (same key twice in raw JSON) -> FAILED.
printf '{"version": 1, "owned": {"skill-a/SKILL.md": "%s", "skill-a/SKILL.md": "%s"}}' \
  "$SHA_A" "$SHA_A" > "$TMP/bad-duplicate.json"
expect_manifest_rejected "SEC-05: manifest duplicate entries are rejected" "$TMP/bad-duplicate.json"

# SEC-06a: a managed path inside the destination is a symlink pointing
# outside (to /etc) -> refused, and the target is untouched.
printf 'TARGET-CONTENT\n' > "$TMP/outside-target"
rm -f "$DEST/skill-a/SKILL.md"
ln -s "$TMP/outside-target" "$DEST/skill-a/SKILL.md"
printf -- '---\nname: skill-a\ndescription: Test skill A v2.\n---\n# Skill A v2\n' > "$SRC/skill-a/SKILL.md"
if $SYNC --source-dir "$SRC" --dest-dir "$DEST" >/dev/null 2>&1; then
  bad "SEC-06a: symlinked managed file is refused"
else
  grep -q "TARGET-CONTENT" "$TMP/outside-target" \
    && ok "SEC-06a: symlinked managed file is refused, target untouched" \
    || bad "SEC-06a: symlinked managed file is refused, target untouched"
fi
# Restore the destination file and source content for later tests.
rm -f "$DEST/skill-a/SKILL.md"
printf -- '---\nname: skill-a\ndescription: Test skill A.\n---\n# Skill A\n' > "$SRC/skill-a/SKILL.md"
$SYNC --source-dir "$SRC" --dest-dir "$DEST" >/dev/null 2>&1

# SEC-06b: a parent directory inside the destination is a symlink
# pointing outside -> refused, nothing written through it.
mkdir -p "$TMP/evil-tree"
rm -rf "$DEST/skill-a"
ln -s "$TMP/evil-tree" "$DEST/skill-a"
if $SYNC --source-dir "$SRC" --dest-dir "$DEST" >/dev/null 2>&1; then
  bad "SEC-06b: symlinked parent dir inside dest is refused"
else
  [ ! -e "$TMP/evil-tree/SKILL.md" ] \
    && ok "SEC-06b: symlinked parent dir inside dest is refused" \
    || bad "SEC-06b: symlinked parent dir inside dest is refused (wrote outside)"
fi
rm -f "$DEST/skill-a"
$SYNC --source-dir "$SRC" --dest-dir "$DEST" >/dev/null 2>&1

# SEC-07: prune attempting to delete an unmanaged file -> it survives.
mkdir -p "$DEST/my-custom"
printf 'MY CUSTOM SKILL — DO NOT DELETE\n' > "$DEST/my-custom/SKILL.md"
$SYNC --source-dir "$SRC" --dest-dir "$DEST" --prune >/dev/null 2>&1
grep -q "DO NOT DELETE" "$DEST/my-custom/SKILL.md" \
  && ok "SEC-07: prune never deletes an unmanaged file" \
  || bad "SEC-07: prune never deletes an unmanaged file"

# SEC-08a: backup-dir given as a symlink escaping to another tree ->
# refused, nothing written there.
mkdir -p "$TMP/elsewhere"
ln -s "$TMP/elsewhere" "$TMP/bk-link"
if $SYNC --source-dir "$SRC" --dest-dir "$DEST" --backup-dir "$TMP/bk-link" >/dev/null 2>&1; then
  bad "SEC-08a: escaping backup-dir symlink is refused"
else
  [ -z "$(ls -A "$TMP/elsewhere" 2>/dev/null)" ] \
    && ok "SEC-08a: escaping backup-dir symlink is refused" \
    || bad "SEC-08a: escaping backup-dir symlink is refused (wrote outside)"
fi

# SEC-08b: a crafted manifest trying to steer rollback -> refused.
# First make a real backup, then corrupt the manifest, then roll back.
printf -- '---\nname: skill-a\ndescription: Test skill A v2.\n---\n# Skill A v2\n' > "$SRC/skill-a/SKILL.md"
$SYNC --source-dir "$SRC" --dest-dir "$DEST" >/dev/null 2>&1
printf '{"version": 1, "owned": {"../evil": "%s"}}' "$SHA_A" > "$MANIFEST"
if $SYNC --dest-dir "$DEST" --rollback >/dev/null 2>&1; then
  bad "SEC-08b: crafted manifest steering rollback is refused"
else
  ok "SEC-08b: crafted manifest steering rollback is refused"
fi
rm -f "$MANIFEST"
$SYNC --source-dir "$SRC" --dest-dir "$DEST" >/dev/null 2>&1

echo "test_installer_security: $([ "$FAILURES" = 0 ] && echo PASS || echo FAIL) ($FAILURES failure(s))"
exit "$([ "$FAILURES" = 0 ] && echo 0 || echo 1)"
