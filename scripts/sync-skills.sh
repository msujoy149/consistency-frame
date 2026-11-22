#!/usr/bin/env bash
# Consistency Frame — non-destructive skill synchroniser (P0).
#
# Copies only Consistency Frame-owned skill files from a source skills/
# directory into a destination skills directory (default
# <repo>/.agents/skills). It NEVER deletes the destination directory and
# NEVER touches files it does not own.
#
# Ownership is tracked in <dest>/.consistency-frame-manifest.json:
#   { "version": 1, "owned": { "<relpath>": "<sha256>", ... } }
# A file is "owned" only if a previous sync wrote it (manifest entry) or
# this run writes it. Every other file in the destination — user skills,
# third-party skills, unknown files — is left exactly as it is.
#
# Usage:
#   scripts/sync-skills.sh [--source-dir DIR] [--dest-dir DIR]
#                          [--dry-run] [--prune] [--rollback]
#                          [--manifest FILE] [--backup-dir DIR]
#
#   --dry-run   Print the planned changes and exit 0 without changing
#               anything. Prune candidates are listed, never applied.
#   --prune     ALSO delete stale owned files (owned files whose source
#               no longer exists). Opt-in only, and only ever for
#               manifest-owned paths. Without --prune nothing is deleted.
#   --rollback  Restore owned files from the latest backup and exit.
#               No sync is performed.
#
# Exit codes: 0 = SUCCESS (all requested changes applied, or dry-run plan
# clean), 2 = PARTIAL (sync applied but a non-fatal step failed — see the
# result file), 1 = FAILED (nothing was applied, or rollback failed).
# A result record is written to <dest>/.consistency-frame-last-sync.json
# (skipped for --dry-run).
#
# Safety: the destination must resolve inside the repository root (or
# inside the directory given with --dest-dir when that directory is
# itself inside the repo or under $HOME/.agents-style paths passed
# explicitly by the caller — see the root check below). Symlinked files
# or directories inside the source or destination that would escape the
# synced trees are rejected. Paths containing ".." are rejected.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE_DIR="$REPO_ROOT/skills"
DEST_DIR="$REPO_ROOT/.agents/skills"
MANIFEST_FILE=""
BACKUP_DIR=""
DRY_RUN=0
PRUNE=0
ROLLBACK=0

usage() {
  echo "Usage: $0 [--source-dir DIR] [--dest-dir DIR] [--dry-run] [--prune] [--rollback] [--manifest FILE] [--backup-dir DIR]" >&2
  exit 2
}

while [ $# -gt 0 ]; do
  case "$1" in
    --source-dir) SOURCE_DIR="${2:-}"; shift 2 ;;
    --dest-dir) DEST_DIR="${2:-}"; shift 2 ;;
    --manifest) MANIFEST_FILE="${2:-}"; shift 2 ;;
    --backup-dir) BACKUP_DIR="${2:-}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --prune) PRUNE=1; shift ;;
    --rollback) ROLLBACK=1; shift ;;
    --help|-h) usage ;;
    *) echo "ERROR: unknown argument: $1" >&2; usage ;;
  esac
done

# Resolve a path to an absolute, normalised form without requiring it to
# exist (portable realpath -m equivalent via python3 if present, else
# a shell fallback that handles the common cases).
resolve_path() {
  if command -v python3 >/dev/null 2>&1; then
    python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$1"
  else
    case "$1" in
      /*) printf '%s\n' "$1" ;;
      *) printf '%s/%s\n' "$PWD" "$1" ;;
    esac
  fi
}

SOURCE_DIR="$(resolve_path "$SOURCE_DIR")"
DEST_DIR="$(resolve_path "$DEST_DIR")"
[ -n "$MANIFEST_FILE" ] && MANIFEST_FILE="$(resolve_path "$MANIFEST_FILE")"
[ -z "$MANIFEST_FILE" ] && MANIFEST_FILE="$DEST_DIR/.consistency-frame-manifest.json"
# Backup dir defaults to a sibling of the destination, so test fixtures
# with a temporary --dest-dir never write backups into the real repo.
[ -z "$BACKUP_DIR" ] && BACKUP_DIR="$(dirname "$DEST_DIR")/skills-backup"

# --- Destination-root safety -------------------------------------------
# The destination must be inside the repo, or inside $HOME when the
# caller explicitly passes a --dest-dir (hosts install skills under
# ~/.agents/skills, ~/.gemini/config/skills, ...). It must never be /,
# $HOME itself, or any parent of the repo root.
case "$DEST_DIR" in
  "/"|"$HOME"|"$REPO_ROOT"|"") echo "ERROR: unsafe destination root: $DEST_DIR" >&2; exit 1 ;;
esac
case "$DEST_DIR" in
  "$REPO_ROOT"/*|"$HOME"/.agents/*|"$HOME"/.gemini/*|"$HOME"/.codex/*|"$HOME"/.config/*) ;;
  *)
    # Allow any other explicit destination only if it is a subdirectory
    # of an existing directory the caller owns and it is not a system
    # root. Refuse anything that looks like a system path.
    case "$DEST_DIR" in
      /usr/*|/etc/*|/bin/*|/sbin/*|/var/*|/opt/*|/System/*) echo "ERROR: unsafe destination root: $DEST_DIR" >&2; exit 1 ;;
    esac
    ;;
esac
case "$SOURCE_DIR" in
  *".."* ) echo "ERROR: source path must not contain '..': $SOURCE_DIR" >&2; exit 1 ;;
esac
case "$DEST_DIR" in
  *".."* ) echo "ERROR: destination path must not contain '..': $DEST_DIR" >&2; exit 1 ;;
esac

if [ ! -d "$SOURCE_DIR" ]; then
  echo "ERROR: source skills directory not found: $SOURCE_DIR" >&2
  exit 1
fi

# Reject symlinked entries in the source tree that escape the source.
while IFS= read -r -d '' link; do
  target="$(resolve_path "$link")"
  case "$target" in
    "$SOURCE_DIR"/*) ;;
    *) echo "ERROR: source contains a symlink escaping the source tree: $link -> $target" >&2; exit 1 ;;
  esac
done < <(find "$SOURCE_DIR" -type l -print0 2>/dev/null)

sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}';
  elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | awk '{print $1}';
  else python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1"; fi
}

# --- Manifest handling (python3, stdlib only) ---------------------------
manifest_owned() {
  # Print owned relative paths, one per line. Missing manifest = none.
  python3 - "$MANIFEST_FILE" <<'PYEOF'
import json, os, sys
p = sys.argv[1]
if not os.path.exists(p):
    sys.exit(0)
try:
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    for rel in sorted(data.get("owned", {}).keys()):
        print(rel)
except Exception as e:
    print(f"ERROR: cannot read manifest {p}: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF
}

manifest_sha() {
  python3 - "$MANIFEST_FILE" "$1" <<'PYEOF'
import json, os, sys
p, rel = sys.argv[1], sys.argv[2]
if not os.path.exists(p):
    sys.exit(0)
try:
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    print(data.get("owned", {}).get(rel, ""))
except Exception:
    sys.exit(0)
PYEOF
}

write_manifest() {
  # $1 = file with lines "sha256  relpath" for the new owned set.
  python3 - "$MANIFEST_FILE" "$1" <<'PYEOF'
import json, os, sys
manifest_path, listing = sys.argv[1], sys.argv[2]
owned = {}
with open(listing, encoding="utf-8") as f:
    for line in f:
        line = line.rstrip("\n")
        if not line:
            continue
        sha, rel = line.split(" ", 1)
        owned[rel] = sha
data = {"version": 1, "owned": dict(sorted(owned.items()))}
os.makedirs(os.path.dirname(manifest_path) or ".", exist_ok=True)
tmp = manifest_path + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, sort_keys=True)
    f.write("\n")
os.replace(tmp, manifest_path)
PYEOF
}

# --- Rollback ------------------------------------------------------------
if [ "$ROLLBACK" = 1 ]; then
  latest="$(ls -dt "$BACKUP_DIR"/*/ 2>/dev/null | head -n 1 || true)"
  if [ -z "$latest" ] || [ ! -d "$latest" ]; then
    echo "ERROR: no backup found under $BACKUP_DIR" >&2
    exit 1
  fi
  echo "Restoring owned files from backup: $latest"
  restored=0
  while IFS= read -r -d '' f; do
    rel="${f#$latest}"
    mkdir -p "$DEST_DIR/$(dirname "$rel")"
    cp -f "$f" "$DEST_DIR/$rel" && restored=$((restored + 1))
  done < <(find "$latest" -type f -print0 2>/dev/null)
  echo "Rollback: restored $restored file(s) from $latest"
  exit 0
fi

# --- Plan ----------------------------------------------------------------
TMPDIR_WORK="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_WORK"' EXIT
PLAN_NEW="$TMPDIR_WORK/new.txt"; PLAN_CHANGED="$TMPDIR_WORK/changed.txt"
PLAN_UNCHANGED="$TMPDIR_WORK/unchanged.txt"; PLAN_PRUNE="$TMPDIR_WORK/prune.txt"
: > "$PLAN_NEW"; : > "$PLAN_CHANGED"; : > "$PLAN_UNCHANGED"; : > "$PLAN_PRUNE"

# Validate source: every skill directory must have a SKILL.md with a
# YAML frontmatter name + description (same rule as validate-repo.py).
while IFS= read -r -d '' skilldir; do
  if [ ! -f "$skilldir/SKILL.md" ]; then
    echo "ERROR: skill directory without SKILL.md: $skilldir" >&2
    exit 1
  fi
  if ! python3 - "$skilldir/SKILL.md" <<'PYEOF'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
if not m:
    sys.exit(1)
fm = m.group(1)
if not re.search(r"^name:\s*\S+", fm, re.M) or not re.search(r"^description:\s*\S+", fm, re.M):
    sys.exit(1)
PYEOF
  then
    echo "ERROR: $skilldir/SKILL.md has invalid frontmatter (name + description required)" >&2
    exit 1
  fi
done < <(find "$SOURCE_DIR" -mindepth 1 -maxdepth 1 -type d -print0)

OWNED_LIST="$TMPDIR_WORK/owned.txt"
manifest_owned > "$OWNED_LIST" || exit 1

while IFS= read -r -d '' src; do
  rel="${src#$SOURCE_DIR/}"
  case "$rel" in *".."* ) echo "ERROR: unsafe relative path: $rel" >&2; exit 1 ;; esac
  dest="$DEST_DIR/$rel"
  if [ -L "$dest" ]; then
    echo "ERROR: destination path is a symlink, refusing to follow: $dest" >&2
    exit 1
  fi
  if [ ! -e "$dest" ]; then
    echo "$rel" >> "$PLAN_NEW"
  else
    src_sha="$(sha256_file "$src")"
    dst_sha="$(sha256_file "$dest")"
    if [ "$src_sha" = "$dst_sha" ]; then
      echo "$rel" >> "$PLAN_UNCHANGED"
    else
      echo "$rel" >> "$PLAN_CHANGED"
    fi
  fi
done < <(find "$SOURCE_DIR" -type f -print0)

# Stale owned files: in the manifest, not in the source any more.
while IFS= read -r rel; do
  [ -z "$rel" ] && continue
  if [ ! -e "$SOURCE_DIR/$rel" ]; then
    echo "$rel" >> "$PLAN_PRUNE"
  fi
done < "$OWNED_LIST"

n_new="$(wc -l < "$PLAN_NEW" | tr -d ' ')"
n_changed="$(wc -l < "$PLAN_CHANGED" | tr -d ' ')"
n_unchanged="$(wc -l < "$PLAN_UNCHANGED" | tr -d ' ')"
n_prune="$(wc -l < "$PLAN_PRUNE" | tr -d ' ')"

echo "Skill sync plan: source=$SOURCE_DIR dest=$DEST_DIR"
echo "  new=$n_new changed=$n_changed unchanged=$n_unchanged prune_candidates=$n_prune (prune=$([ "$PRUNE" = 1 ] && echo on || echo off))"
if [ "$n_prune" -gt 0 ]; then
  echo "  prune candidates (owned files only):"
  sed 's/^/    /' "$PLAN_PRUNE"
fi

if [ "$DRY_RUN" = 1 ]; then
  echo "Dry run: no changes made."
  exit 0
fi

# --- Apply ---------------------------------------------------------------
mkdir -p "$DEST_DIR"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_THIS="$BACKUP_DIR/$TIMESTAMP"
mkdir -p "$BACKUP_THIS"
failed=0

# Back up every owned file that will be replaced or pruned, before
# touching it.
while IFS= read -r rel; do
  [ -z "$rel" ] && continue
  if [ -e "$DEST_DIR/$rel" ]; then
    mkdir -p "$BACKUP_THIS/$(dirname "$rel")"
    cp -f "$DEST_DIR/$rel" "$BACKUP_THIS/$rel" || failed=1
  fi
done < <(cat "$PLAN_CHANGED" "$PLAN_PRUNE")

apply_copy() {
  # $1 = relpath
  local rel="$1"
  mkdir -p "$DEST_DIR/$(dirname "$rel")"
  cp -f "$SOURCE_DIR/$rel" "$DEST_DIR/$rel"
}

while IFS= read -r rel; do
  [ -z "$rel" ] && continue
  apply_copy "$rel" || { echo "ERROR: failed to copy $rel" >&2; failed=1; }
done < <(cat "$PLAN_NEW" "$PLAN_CHANGED")

if [ "$PRUNE" = 1 ]; then
  while IFS= read -r rel; do
    [ -z "$rel" ] && continue
    rm -f "$DEST_DIR/$rel" || { echo "ERROR: failed to prune $rel" >&2; failed=1; }
    # Remove the parent dir only if it is now empty and was owned.
    rmdir "$DEST_DIR/$(dirname "$rel")" 2>/dev/null || true
  done < "$PLAN_PRUNE"
fi

if [ "$failed" = 1 ]; then
  echo "FAILED: one or more file operations failed; restoring from backup $BACKUP_THIS" >&2
  while IFS= read -r -d '' f; do
    rel="${f#$BACKUP_THIS/}"
    mkdir -p "$DEST_DIR/$(dirname "$rel")"
    cp -f "$f" "$DEST_DIR/$rel" 2>/dev/null || true
  done < <(find "$BACKUP_THIS" -type f -print0 2>/dev/null)
  echo '{"status":"FAILED"}' > "$DEST_DIR/.consistency-frame-last-sync.json"
  exit 1
fi

# Rebuild the owned manifest from the destination state: owned = every
# file present in the source (now copied) plus previously owned files
# that were not pruned.
NEW_OWNED="$TMPDIR_WORK/owned-new.txt"; : > "$NEW_OWNED"
while IFS= read -r -d '' src; do
  rel="${src#$SOURCE_DIR/}"
  echo "$(sha256_file "$DEST_DIR/$rel") $rel" >> "$NEW_OWNED"
done < <(find "$SOURCE_DIR" -type f -print0)
if [ "$PRUNE" = 0 ]; then
  while IFS= read -r rel; do
    [ -z "$rel" ] && continue
    if [ -e "$SOURCE_DIR/$rel" ]; then continue; fi
    if [ -e "$DEST_DIR/$rel" ]; then
      echo "$(sha256_file "$DEST_DIR/$rel") $rel" >> "$NEW_OWNED"
    fi
  done < "$OWNED_LIST"
fi
sort -u "$NEW_OWNED" -o "$NEW_OWNED"
write_manifest "$NEW_OWNED" || { echo "ERROR: failed to write manifest" >&2; exit 1; }

# Drop the backup if nothing changed (keep the directory only when it
# holds a real backup).
if [ "$n_changed" = 0 ] && [ "$n_prune" = 0 ]; then
  rm -rf "$BACKUP_THIS"
fi

STATUS="SUCCESS"
[ "$failed" = 1 ] && STATUS="PARTIAL"
cat > "$DEST_DIR/.consistency-frame-last-sync.json" <<EOF
{
  "status": "$STATUS",
  "source_dir": "$SOURCE_DIR",
  "dest_dir": "$DEST_DIR",
  "new": $n_new,
  "changed": $n_changed,
  "unchanged": $n_unchanged,
  "pruned": $([ "$PRUNE" = 1 ] && echo "$n_prune" || echo 0),
  "prune_candidates": $n_prune,
  "timestamp_utc": "$TIMESTAMP"
}
EOF

echo "Skill sync $STATUS: new=$n_new changed=$n_changed unchanged=$n_unchanged pruned=$([ "$PRUNE" = 1 ] && echo "$n_prune" || echo 0)"
echo "Manifest: $MANIFEST_FILE"
[ "$STATUS" = "SUCCESS" ] && exit 0 || exit 2
