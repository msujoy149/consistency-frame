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
# Path safety: the destination is canonicalised up front. The canonical
# destination must equal <canonical parent>/<requested basename>; if the
# destination path itself is a symlink, or any existing ancestor is a
# symlink that would redirect the sync outside the requested parent,
# the run FAILS before anything is written. The manifest is validated
# strictly (see below) before any file is copied, pruned or backed up,
# and every path used by prune/backup/rollback is validated as a safe
# relative path (no leading "/", no ".." segment, no empty segment, no
# backslash, no NUL, no trailing "/"). A symlinked file or parent
# directory inside the destination is never followed.
#
# Managed-file ownership: a managed file is user-modified when its
# current hash differs from BOTH the manifest hash and the source hash.
# Default policy is "keep": user-modified files are NOT overwritten and
# are recorded as conflicts in <dest>/.consistency-frame-last-sync.json
# (a "conflicts" array plus a "conflict_policy" field); the run still
# succeeds for the other files. Pass --conflict overwrite to replace
# user-modified files explicitly. Prune NEVER deletes a user-modified
# managed file; refused prunes are listed as "prune_refused".
#
# Backups and rollback: every run that changes or prunes a file keeps a
# backup in an atomically unique run directory created with mktemp -d
# ("$BACKUP_DIR/run-XXXXXX") carrying a .run-owner.json marker
# ({dest_dir, run_id, created_utc}). Rollback restores ONLY from the
# latest run directory with a valid owner marker for THIS destination,
# and only validated relative paths inside it. One run never deletes
# another run's backup: old backups are removed only with the explicit
# --prune-backups <days> option, which deletes only this destination's
# run directories older than <days> days with no live .lock file.
#
# Metadata writes are atomic and symlink-safe (P0-003): the manifest,
# the last-sync record and the run-owner marker are all written through
# one helper, scripts/atomic_write.py (tempfile.mkstemp + fd write +
# fsync + os.replace). No installer metadata writer uses a predictable
# temporary filename.
#
# Usage:
#   scripts/sync-skills.sh [--source-dir DIR] [--dest-dir DIR]
#                          [--dry-run] [--prune] [--rollback]
#                          [--manifest FILE] [--backup-dir DIR]
#                          [--conflict keep|overwrite]
#                          [--prune-backups DAYS]
#
#   --dry-run   Print the planned changes and exit 0 without changing
#               anything. Prune candidates are listed, never applied.
#   --prune     ALSO delete stale owned files (owned files whose source
#               no longer exists). Opt-in only, and only ever for
#               manifest-owned paths. Without --prune nothing is deleted.
#               A user-modified stale file is never pruned.
#   --rollback  Restore owned files from the latest backup for this
#               destination and exit. No sync is performed.
#   --conflict keep|overwrite
#               What to do with a user-modified managed file (default
#               keep). "keep" leaves the file alone and records a
#               conflict; "overwrite" replaces it with the source.
#   --prune-backups DAYS
#               Delete run backup directories for this destination
#               older than DAYS days (skips locked and foreign ones)
#               and exit. No sync is performed.
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
# Directory of the atomic-write helper (scripts/atomic_write.py) used by
# every installer metadata writer. The embedded Python heredocs import
# it from here and fail hard if it is unset, so a metadata write can
# never silently fall back to a predictable temporary file (P0-003).
export CF_ATOMIC_WRITE_LIB="$REPO_ROOT/scripts"
SOURCE_DIR="$REPO_ROOT/skills"
DEST_DIR="$REPO_ROOT/.agents/skills"
MANIFEST_FILE=""
BACKUP_DIR=""
DRY_RUN=0
PRUNE=0
ROLLBACK=0
CONFLICT_POLICY="keep"
PRUNE_BACKUPS=""

usage() {
  echo "Usage: $0 [--source-dir DIR] [--dest-dir DIR] [--dry-run] [--prune] [--rollback] [--manifest FILE] [--backup-dir DIR] [--conflict keep|overwrite] [--prune-backups DAYS]" >&2
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
    --conflict)
      CONFLICT_POLICY="${2:-}"
      case "$CONFLICT_POLICY" in keep|overwrite) ;; *) echo "ERROR: --conflict must be keep or overwrite" >&2; usage ;; esac
      shift 2 ;;
    --prune-backups)
      PRUNE_BACKUPS="${2:-}"
      case "$PRUNE_BACKUPS" in ''|*[!0-9]*) echo "ERROR: --prune-backups needs a non-negative integer number of days" >&2; usage ;; esac
      shift 2 ;;
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
# NOTE: DEST_DIR is resolved LEXICALLY here (no symlink resolution) so
# the canonical check below can see — and refuse — a symlinked
# destination or symlinked ancestor. resolve_path() would silently
# resolve those away first.
lexical_path() {
  if command -v python3 >/dev/null 2>&1; then
    python3 -c 'import os,sys; print(os.path.normpath(os.path.abspath(sys.argv[1])))' "$1"
  else
    case "$1" in
      /*) printf '%s\n' "$1" ;;
      *) printf '%s/%s\n' "$PWD" "$1" ;;
    esac
  fi
}
DEST_DIR="$(lexical_path "$DEST_DIR")"
[ -n "$MANIFEST_FILE" ] && MANIFEST_FILE="$(resolve_path "$MANIFEST_FILE")"

# --- Canonical destination check ---------------------------------------
# Fail closed if the destination itself is a symlink, or if any existing
# ancestor is a symlink: the canonical destination must equal
# <canonical parent>/<requested basename>. Never follow a symlinked
# parent into another tree.
DEST_DIR="$(python3 - "$DEST_DIR" <<'PYEOF'
import os, sys
req = os.path.normpath(os.path.abspath(sys.argv[1]))
cur = ""
for part in req.split(os.sep)[1:]:
    cur += os.sep + part
    if os.path.islink(cur):
        print(f"ERROR: destination path contains a symlink, refusing to follow: {cur}", file=sys.stderr)
        sys.exit(1)
parent = os.path.dirname(req)
canon = os.path.realpath(req)
canon_parent = os.path.realpath(parent)
if canon != os.path.join(canon_parent, os.path.basename(req)):
    print(f"ERROR: canonical destination {canon} does not equal {canon_parent}/{os.path.basename(req)}", file=sys.stderr)
    sys.exit(1)
print(canon)
PYEOF
)" || exit 1

[ -z "$MANIFEST_FILE" ] && MANIFEST_FILE="$DEST_DIR/.consistency-frame-manifest.json"
# Backup dir defaults to a sibling of the destination, so test fixtures
# with a temporary --dest-dir never write backups into the real repo.
[ -z "$BACKUP_DIR" ] && BACKUP_DIR="$(dirname "$DEST_DIR")/skills-backup"

# --- Backup-dir confinement --------------------------------------------
# The canonical backup dir must be a sibling of the destination (its
# parent must be the destination's parent) and must not be the
# destination itself. A backup-dir symlink that escapes is rejected.
BACKUP_DIR="$(python3 - "$BACKUP_DIR" "$DEST_DIR" <<'PYEOF'
import os, sys
backup = os.path.normpath(os.path.abspath(sys.argv[1]))
dest = sys.argv[2]
canon_backup = os.path.realpath(backup)
dest_parent = os.path.dirname(dest)
if os.path.dirname(canon_backup) != dest_parent:
    print(f"ERROR: backup dir {canon_backup} is not a sibling of the destination {dest}", file=sys.stderr)
    sys.exit(1)
if canon_backup == dest:
    print(f"ERROR: backup dir must not be the destination itself: {canon_backup}", file=sys.stderr)
    sys.exit(1)
print(canon_backup)
PYEOF
)" || exit 1

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

# --- Safe relative paths --------------------------------------------------
# A safe relative path has no leading "/", no ".." or "." segment, no
# empty segment, no backslash, no NUL, and no trailing "/".
safe_rel() {
  local p="$1" seg rest
  case "$p" in ""|/*|*/|*\\*) return 1 ;; esac
  rest="$p"
  while :; do
    case "$rest" in
      */*) seg="${rest%%/*}"; rest="${rest#*/}" ;;
      *) seg="$rest"; rest="" ;;
    esac
    case "$seg" in ""|"."|"..") return 1 ;; esac
    [ -z "$rest" ] && break
  done
  return 0
}

# Reject if any existing parent directory of $DEST_DIR/$1 is a symlink.
# Called for every managed path before it is read, written or deleted.
check_dest_parents() {
  local rel="$1" parent cur part rest
  parent="$(dirname "$rel")"
  [ "$parent" = "." ] && return 0
  cur="$DEST_DIR"
  rest="$parent"
  while :; do
    case "$rest" in
      */*) part="${rest%%/*}"; rest="${rest#*/}" ;;
      *) part="$rest"; rest="" ;;
    esac
    cur="$cur/$part"
    if [ -L "$cur" ]; then
      echo "ERROR: destination parent is a symlink, refusing to follow: $cur" >&2
      return 1
    fi
    [ -z "$rest" ] && break
  done
  return 0
}

# --- Working area + run lock ----------------------------------------------
TMPDIR_WORK="$(mktemp -d)"
RUN_DIR=""
RUN_LOCK=""
cleanup() {
  [ -n "$RUN_LOCK" ] && [ -f "$RUN_LOCK" ] && rm -f "$RUN_LOCK"
  [ -n "${TMPDIR_WORK:-}" ] && [ -d "$TMPDIR_WORK" ] && rm -rf "$TMPDIR_WORK"
}
trap cleanup EXIT

# --- Manifest handling (python3, stdlib only) ---------------------------
# Strict validation, run once up front, fail closed: invalid JSON,
# non-object top level, version != 1, "owned" not an object, any key or
# value with the wrong type, duplicate keys (detected via
# object_pairs_hook), a missing sha256, a sha256 that is not a 64-hex
# string, or a key that is not a safe relative path all fail the whole
# sync (exit 1) before any file is copied, pruned or backed up. A
# missing manifest file means "no owned files".
manifest_validate_and_dump() {
  # Print owned entries as "sha<TAB>rel" lines (sorted) to stdout.
  python3 - "$MANIFEST_FILE" <<'PYEOF'
import json, re, sys

SHA_RE = re.compile(r"[0-9a-fA-F]{64}\Z")

def fail(msg):
    print(f"ERROR: manifest validation failed: {msg}", file=sys.stderr)
    sys.exit(1)

def no_dupes(pairs):
    obj = {}
    for k, v in pairs:
        if k in obj:
            raise ValueError(f"duplicate key: {k!r}")
        obj[k] = v
    return obj

def safe_rel(p):
    if not isinstance(p, str) or p == "":
        return False
    if p.startswith("/") or p.endswith("/"):
        return False
    if "\\" in p or "\x00" in p:
        return False
    for seg in p.split("/"):
        if seg in ("", ".", ".."):
            return False
    return True

p = sys.argv[1]
try:
    with open(p, encoding="utf-8") as f:
        raw = f.read()
except FileNotFoundError:
    sys.exit(0)
except OSError as e:
    fail(f"cannot read {p}: {e}")
try:
    data = json.loads(raw, object_pairs_hook=no_dupes)
except ValueError as e:
    fail(f"invalid JSON in {p}: {e}")
if not isinstance(data, dict):
    fail("top level is not a JSON object")
version = data.get("version")
if type(version) is not int or version != 1:
    fail("version must be 1")
owned = data.get("owned")
if not isinstance(owned, dict):
    fail("'owned' must be an object")
for rel, sha in owned.items():
    if not safe_rel(rel):
        fail(f"unsafe owned path: {rel!r}")
    if type(sha) is not str:
        fail(f"sha256 for {rel!r} is not a string")
    if not SHA_RE.match(sha):
        fail(f"sha256 for {rel!r} is not a 64-hex string")
for rel in sorted(owned):
    print(f"{owned[rel]}\t{rel}")
PYEOF
}

MANIFEST_DUMP="$TMPDIR_WORK/manifest.tsv"
manifest_validate_and_dump > "$MANIFEST_DUMP" || exit 1

declare -A MANIFEST_SHA=()
while IFS=$'\t' read -r sha rel; do
  [ -n "$rel" ] && MANIFEST_SHA["$rel"]="$sha"
done < "$MANIFEST_DUMP"
OWNED_LIST="$TMPDIR_WORK/owned.txt"
cut -f2 "$MANIFEST_DUMP" > "$OWNED_LIST"

manifest_sha() {  # $1 = relpath; prints the manifest sha or empty
  printf '%s' "${MANIFEST_SHA["$1"]:-}"
}

write_manifest() {
  # $1 = file with lines "sha256  relpath" for the new owned set.
  python3 - "$MANIFEST_FILE" "$1" <<'PYEOF'
import json, os, sys
_lib = os.environ.get("CF_ATOMIC_WRITE_LIB")
if not _lib or not os.path.isdir(_lib):
    raise SystemExit("CF_ATOMIC_WRITE_LIB is not set to the scripts directory")
sys.path.insert(0, _lib)
from atomic_write import atomic_write_json
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
# Secure atomic write (P0-003): mkstemp-created temp, written through
# its fd, then os.replace(). Never a predictable "<target>.tmp".
atomic_write_json(manifest_path, data)
PYEOF
}

update_manifest_hashes() {
  # $1 = file with lines "sha256  relpath" whose entries replace (or
  # add) the manifest hashes for those paths (used by rollback so the
  # restored files are owned at their restored content).
  python3 - "$MANIFEST_FILE" "$1" <<'PYEOF'
import json, os, sys
_lib = os.environ.get("CF_ATOMIC_WRITE_LIB")
if not _lib or not os.path.isdir(_lib):
    raise SystemExit("CF_ATOMIC_WRITE_LIB is not set to the scripts directory")
sys.path.insert(0, _lib)
from atomic_write import atomic_write_json
manifest_path, listing = sys.argv[1], sys.argv[2]
owned = {}
if os.path.exists(manifest_path):
    with open(manifest_path, encoding="utf-8") as f:
        owned = dict(json.load(f).get("owned", {}))
with open(listing, encoding="utf-8") as f:
    for line in f:
        line = line.rstrip("\n")
        if not line:
            continue
        sha, rel = line.split(" ", 1)
        owned[rel] = sha
data = {"version": 1, "owned": dict(sorted(owned.items()))}
# Secure atomic write (P0-003): same helper as write_manifest().
atomic_write_json(manifest_path, data)
PYEOF
}

# --- Backup run-dir helpers ----------------------------------------------
marker_valid() {
  # $1 = run dir; exit 0 iff .run-owner.json is valid for THIS dest.
  python3 - "$1" "$DEST_DIR" <<'PYEOF'
import json, os, sys
d, dest = sys.argv[1], sys.argv[2]
try:
    with open(os.path.join(d, ".run-owner.json"), encoding="utf-8") as f:
        m = json.load(f)
    if not isinstance(m, dict):
        sys.exit(1)
    if m.get("dest_dir") != dest:
        sys.exit(1)
    if m.get("run_id") != os.path.basename(os.path.normpath(d)):
        sys.exit(1)
    if not isinstance(m.get("created_utc"), str):
        sys.exit(1)
except Exception:
    sys.exit(1)
sys.exit(0)
PYEOF
}

write_run_owner() {  # $1 = run dir, $2 = run id, $3 = created_utc
  python3 - "$1" "$2" "$3" "$DEST_DIR" <<'PYEOF'
import json, os, sys
_lib = os.environ.get("CF_ATOMIC_WRITE_LIB")
if not _lib or not os.path.isdir(_lib):
    raise SystemExit("CF_ATOMIC_WRITE_LIB is not set to the scripts directory")
sys.path.insert(0, _lib)
from atomic_write import atomic_write_json
d, run_id, created, dest = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
# Secure atomic write (P0-003): same helper as the manifest writers.
atomic_write_json(os.path.join(d, ".run-owner.json"),
                  {"dest_dir": dest, "run_id": run_id, "created_utc": created})
PYEOF
}

remove_run_dir() {
  # $1 = run dir. Delete ONLY a validated run dir of THIS destination:
  # it must be a real directory named run-* directly under the backup
  # dir, carrying a valid owner marker for this destination. Never
  # bulk-delete backup directories.
  local dir="$1"
  [ -d "$dir" ] || { echo "ERROR: not a directory: $dir" >&2; return 1; }
  [ -L "$dir" ] && { echo "ERROR: refusing to remove symlinked dir: $dir" >&2; return 1; }
  case "$(basename "$dir")" in run-*) ;; *) echo "ERROR: not a run dir: $dir" >&2; return 1 ;; esac
  [ "$(dirname "$dir")" = "$BACKUP_DIR" ] || { echo "ERROR: run dir not under backup dir: $dir" >&2; return 1; }
  marker_valid "$dir" || { echo "ERROR: run dir has no valid owner marker for this destination: $dir" >&2; return 1; }
  rm -rf -- "$dir"
}

latest_valid_run_dir() {
  # Print the newest run dir (by mtime) with a valid owner marker for
  # this destination, or fail.
  local d
  while IFS= read -r d; do
    [ -d "$d" ] || continue
    if marker_valid "$d"; then printf '%s' "${d%/}"; return 0; fi
  done < <(ls -dt "$BACKUP_DIR"/run-*/ 2>/dev/null)
  return 1
}

# --- Rollback ------------------------------------------------------------
if [ "$ROLLBACK" = 1 ]; then
  latest="$(latest_valid_run_dir)" || { echo "ERROR: no backup found under $BACKUP_DIR for destination $DEST_DIR" >&2; exit 1; }
  echo "Restoring owned files from backup: $latest"
  # Pre-validate every file to restore: safe relative path, regular
  # file, not a marker/metadata file, and the destination target must
  # not be a symlink (nor sit under a symlinked parent).
  RESTORE_LIST="$TMPDIR_WORK/restore.txt"; : > "$RESTORE_LIST"
  while IFS= read -r -d '' f; do
    rel="${f#$latest/}"
    case "$rel" in ".run-owner.json"|".lock"|".consistency-frame-manifest.json"|".consistency-frame-last-sync.json") continue ;; esac
    safe_rel "$rel" || { echo "ERROR: unsafe path in backup, refusing rollback: $rel" >&2; exit 1; }
    check_dest_parents "$rel" || exit 1
    [ -L "$DEST_DIR/$rel" ] && { echo "ERROR: destination path is a symlink, refusing to restore over it: $DEST_DIR/$rel" >&2; exit 1; }
    echo "$rel" >> "$RESTORE_LIST"
  done < <(find "$latest" -type f -print0 2>/dev/null)
  restored=0
  while IFS= read -r rel; do
    [ -z "$rel" ] && continue
    mkdir -p "$DEST_DIR/$(dirname "$rel")"
    cp -f "$latest/$rel" "$DEST_DIR/$rel" && restored=$((restored + 1))
  done < "$RESTORE_LIST"
  # Update the manifest so the restored files are owned at their
  # restored content; otherwise the next sync would see them as
  # user-modified and refuse to update them.
  if [ "$restored" -gt 0 ]; then
    RESTORE_HASHES="$TMPDIR_WORK/restore-hashes.txt"; : > "$RESTORE_HASHES"
    while IFS= read -r rel; do
      [ -z "$rel" ] && continue
      echo "$(sha256_file "$DEST_DIR/$rel") $rel" >> "$RESTORE_HASHES"
    done < "$RESTORE_LIST"
    update_manifest_hashes "$RESTORE_HASHES" || { echo "ERROR: failed to update manifest after rollback" >&2; exit 1; }
  fi
  echo "Rollback: restored $restored file(s) from $latest"
  exit 0
fi

# --- Prune old backups -----------------------------------------------------
if [ -n "$PRUNE_BACKUPS" ]; then
  now_epoch="$(date +%s)"
  threshold=$((PRUNE_BACKUPS * 86400))
  pruned_backups=0; skipped_backups=0
  for d in "$BACKUP_DIR"/run-*/; do
    [ -d "$d" ] || continue
    d="${d%/}"
    if [ -f "$d/.lock" ]; then echo "  skip (locked, run still active): $d"; skipped_backups=$((skipped_backups + 1)); continue; fi
    if ! marker_valid "$d"; then echo "  skip (no valid owner marker for this destination): $d"; skipped_backups=$((skipped_backups + 1)); continue; fi
    created_epoch="$(python3 - "$d" <<'PYEOF'
import datetime, json, os, sys
d = sys.argv[1]
try:
    with open(os.path.join(d, ".run-owner.json"), encoding="utf-8") as f:
        m = json.load(f)
    created = datetime.datetime.strptime(m["created_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    print(int(created.timestamp()))
except Exception:
    print(int(os.path.getmtime(d)))
PYEOF
)"
    age=$((now_epoch - created_epoch))
    if [ "$age" -gt "$threshold" ]; then
      if remove_run_dir "$d"; then
        echo "  pruned backup: $d"
        pruned_backups=$((pruned_backups + 1))
      else
        echo "  skip (could not validate for removal): $d" >&2
        skipped_backups=$((skipped_backups + 1))
      fi
    else
      echo "  skip (too new): $d"
      skipped_backups=$((skipped_backups + 1))
    fi
  done
  echo "Prune backups: pruned=$pruned_backups skipped=$skipped_backups"
  exit 0
fi

# --- Plan ----------------------------------------------------------------
PLAN_NEW="$TMPDIR_WORK/new.txt"; PLAN_CHANGED="$TMPDIR_WORK/changed.txt"
PLAN_CONFLICT="$TMPDIR_WORK/conflict.txt"
PLAN_UNCHANGED="$TMPDIR_WORK/unchanged.txt"; PLAN_PRUNE="$TMPDIR_WORK/prune.txt"
APPLIED_PRUNE="$TMPDIR_WORK/prune-apply.txt"
CONFLICTS_TSV="$TMPDIR_WORK/conflicts.tsv"; PRUNE_REFUSED_TSV="$TMPDIR_WORK/prune-refused.tsv"
: > "$PLAN_NEW"; : > "$PLAN_CHANGED"; : > "$PLAN_CONFLICT"
: > "$PLAN_UNCHANGED"; : > "$PLAN_PRUNE"; : > "$APPLIED_PRUNE"
: > "$CONFLICTS_TSV"; : > "$PRUNE_REFUSED_TSV"

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

while IFS= read -r -d '' src; do
  rel="${src#$SOURCE_DIR/}"
  safe_rel "$rel" || { echo "ERROR: unsafe relative path: $rel" >&2; exit 1; }
  check_dest_parents "$rel" || exit 1
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
      man_sha="$(manifest_sha "$rel")"
      if [ "$dst_sha" != "$man_sha" ]; then
        # User-modified: current content differs from BOTH the manifest
        # hash and the source hash (dst != src here by construction).
        printf '%s\t%s\t%s\t%s\n' "$rel" "$man_sha" "$src_sha" "$dst_sha" >> "$CONFLICTS_TSV"
        if [ "$CONFLICT_POLICY" = "keep" ]; then
          echo "$rel" >> "$PLAN_CONFLICT"
        else
          echo "$rel" >> "$PLAN_CHANGED"
        fi
      else
        echo "$rel" >> "$PLAN_CHANGED"
      fi
    fi
  fi
done < <(find "$SOURCE_DIR" -type f -print0)

# Stale owned files: in the manifest, not in the source any more.
# A user-modified stale file is NEVER pruned (recorded as refused).
while IFS= read -r rel; do
  [ -z "$rel" ] && continue
  if [ ! -e "$SOURCE_DIR/$rel" ]; then
    echo "$rel" >> "$PLAN_PRUNE"
    refused=0
    if [ -L "$DEST_DIR/$rel" ]; then
      printf '%s\t%s\t%s\t%s\n' "$rel" "$(manifest_sha "$rel")" "" "symlink" >> "$PRUNE_REFUSED_TSV"
      refused=1
    elif [ -e "$DEST_DIR/$rel" ]; then
      check_dest_parents "$rel" || exit 1
      cur_sha="$(sha256_file "$DEST_DIR/$rel")"
      man_sha="$(manifest_sha "$rel")"
      if [ "$cur_sha" != "$man_sha" ]; then
        printf '%s\t%s\t%s\t%s\n' "$rel" "$man_sha" "$cur_sha" "user-modified" >> "$PRUNE_REFUSED_TSV"
        refused=1
      fi
    fi
    [ "$refused" = 0 ] && echo "$rel" >> "$APPLIED_PRUNE"
  fi
done < "$OWNED_LIST"

n_new="$(wc -l < "$PLAN_NEW" | tr -d ' ')"
n_changed="$(wc -l < "$PLAN_CHANGED" | tr -d ' ')"
n_unchanged="$(wc -l < "$PLAN_UNCHANGED" | tr -d ' ')"
n_prune="$(wc -l < "$PLAN_PRUNE" | tr -d ' ')"
n_conflicts="$(wc -l < "$PLAN_CONFLICT" | tr -d ' ')"
[ "$CONFLICT_POLICY" = "overwrite" ] && n_conflicts="$(wc -l < "$CONFLICTS_TSV" | tr -d ' ')"
n_prune_refused="$(wc -l < "$PRUNE_REFUSED_TSV" | tr -d ' ')"

echo "Skill sync plan: source=$SOURCE_DIR dest=$DEST_DIR"
echo "  new=$n_new changed=$n_changed unchanged=$n_unchanged prune_candidates=$n_prune (prune=$([ "$PRUNE" = 1 ] && echo on || echo off)) conflicts=$n_conflicts prune_refused=$n_prune_refused"
if [ "$n_prune" -gt 0 ]; then
  echo "  prune candidates (owned files only):"
  sed 's/^/    /' "$PLAN_PRUNE"
fi
if [ "$n_conflicts" -gt 0 ]; then
  echo "  conflicts (user-modified managed files, policy=$CONFLICT_POLICY):"
  cut -f1 "$CONFLICTS_TSV" | sed 's/^/    /'
fi
if [ "$n_prune_refused" -gt 0 ]; then
  echo "  prune refused (user-modified stale files, kept):"
  cut -f1 "$PRUNE_REFUSED_TSV" | sed 's/^/    /'
fi

if [ "$DRY_RUN" = 1 ]; then
  echo "Dry run: no changes made."
  exit 0
fi

# --- Result record ---------------------------------------------------------
write_result_json() {
  # $1=status $2=run_id ("" = none) $3=new $4=changed $5=unchanged
  # $6=pruned $7=prune_candidates $8=timestamp_utc
  python3 - "$DEST_DIR/.consistency-frame-last-sync.json" "$CONFLICTS_TSV" "$PRUNE_REFUSED_TSV" "$CONFLICT_POLICY" "$1" "$2" "$3" "$4" "$5" "$6" "$7" "$8" "$SOURCE_DIR" "$DEST_DIR" <<'PYEOF'
import json, os, sys
_lib = os.environ.get("CF_ATOMIC_WRITE_LIB")
if not _lib or not os.path.isdir(_lib):
    raise SystemExit("CF_ATOMIC_WRITE_LIB is not set to the scripts directory")
sys.path.insert(0, _lib)
from atomic_write import atomic_write_json
out, conflicts_tsv, refused_tsv, policy, status, run_id, new, changed, unchanged, pruned, prune_candidates, ts, src, dest = sys.argv[1:15]

def load_tsv(path, fields):
    rows = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line:
                    continue
                rows.append(dict(zip(fields, line.split("\t"))))
    except FileNotFoundError:
        pass
    return rows

conflicts = load_tsv(conflicts_tsv, ["path", "manifest_sha256", "source_sha256", "current_sha256"])
for c in conflicts:
    if c.get("manifest_sha256") == "":
        c["manifest_sha256"] = None
refused = load_tsv(refused_tsv, ["path", "manifest_sha256", "current_sha256", "reason"])
for r in refused:
    if r.get("manifest_sha256") == "":
        r["manifest_sha256"] = None
    if r.get("current_sha256") == "":
        r["current_sha256"] = None
data = {
    "status": status,
    "source_dir": src,
    "dest_dir": dest,
    "run_id": run_id if run_id else None,
    "new": int(new),
    "changed": int(changed),
    "unchanged": int(unchanged),
    "pruned": int(pruned),
    "prune_candidates": int(prune_candidates),
    "conflicts": conflicts,
    "conflict_count": len(conflicts),
    "conflict_policy": policy,
    "prune_refused": refused,
    "prune_refused_count": len(refused),
    "timestamp_utc": ts,
}
# Secure atomic write (P0-003): os.replace() replaces a planted symlink
# at the result path itself instead of following it, so the symlink's
# outside target is untouched and the result ends up a regular file.
atomic_write_json(out, data)
PYEOF
}

# --- Apply ---------------------------------------------------------------
mkdir -p "$DEST_DIR"
mkdir -p "$BACKUP_DIR"
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
RUN_DIR="$(mktemp -d "$BACKUP_DIR/run-XXXXXX")" || { echo "ERROR: failed to create backup run dir under $BACKUP_DIR" >&2; exit 1; }
RUN_ID="$(basename "$RUN_DIR")"
RUN_LOCK="$RUN_DIR/.lock"
: > "$RUN_LOCK"
write_run_owner "$RUN_DIR" "$RUN_ID" "$TIMESTAMP" || { echo "ERROR: failed to write run owner marker" >&2; exit 1; }
failed=0

# Back up every owned file that will be replaced or pruned, before
# touching it. Only this run's own backup directory is used.
while IFS= read -r rel; do
  [ -z "$rel" ] && continue
  safe_rel "$rel" || { echo "ERROR: unsafe relative path: $rel" >&2; failed=1; continue; }
  if [ -e "$DEST_DIR/$rel" ]; then
    [ -L "$DEST_DIR/$rel" ] && { echo "ERROR: destination path is a symlink, refusing to back up: $DEST_DIR/$rel" >&2; failed=1; continue; }
    mkdir -p "$RUN_DIR/$(dirname "$rel")"
    cp -f "$DEST_DIR/$rel" "$RUN_DIR/$rel" || failed=1
  fi
done < <(cat "$PLAN_CHANGED" "$APPLIED_PRUNE")

# Whether this run's directory holds a real content backup: any file
# other than the owner marker and the lock. Backups are created only
# for replaced or pruned files, so a run that only installed new
# files, or changed nothing, has no content backup to recover. The
# failure diagnostics below use this so they never claim a backup
# exists when none was created (P0-005).
run_dir_has_content_backup() {
  [ -n "$(find "$RUN_DIR" -type f ! -name '.run-owner.json' ! -name '.lock' -print -quit 2>/dev/null)" ]
}

apply_copy() {
  # $1 = relpath
  local rel="$1"
  mkdir -p "$DEST_DIR/$(dirname "$rel")"
  cp -f "$SOURCE_DIR/$rel" "$DEST_DIR/$rel"
}

while IFS= read -r rel; do
  [ -z "$rel" ] && continue
  safe_rel "$rel" || { echo "ERROR: unsafe relative path: $rel" >&2; failed=1; continue; }
  apply_copy "$rel" || { echo "ERROR: failed to copy $rel" >&2; failed=1; }
done < <(cat "$PLAN_NEW" "$PLAN_CHANGED")

pruned=0
if [ "$PRUNE" = 1 ]; then
  while IFS= read -r rel; do
    [ -z "$rel" ] && continue
    safe_rel "$rel" || { echo "ERROR: unsafe relative path: $rel" >&2; failed=1; continue; }
    [ -L "$DEST_DIR/$rel" ] && { echo "ERROR: destination path is a symlink, refusing to prune: $DEST_DIR/$rel" >&2; failed=1; continue; }
    if [ -e "$DEST_DIR/$rel" ]; then
      if rm -f "$DEST_DIR/$rel"; then pruned=$((pruned + 1)); else echo "ERROR: failed to prune $rel" >&2; failed=1; fi
    fi
    # Remove the parent dir only if it is now empty and was owned.
    rmdir "$DEST_DIR/$(dirname "$rel")" 2>/dev/null || true
  done < "$APPLIED_PRUNE"
fi

if [ "$failed" = 1 ]; then
  # P0-005: describe the backup state accurately. A run that failed
  # while installing only new files, or before any backup was made,
  # has no content backup to restore from — say so instead of
  # claiming one.
  if run_dir_has_content_backup; then
    echo "FAILED: one or more file operations failed; restoring from this run's backup $RUN_DIR" >&2
  else
    echo "FAILED: one or more file operations failed; no content backup was created for this run, nothing to restore" >&2
  fi
  while IFS= read -r -d '' f; do
    rel="${f#$RUN_DIR/}"
    case "$rel" in ".run-owner.json"|".lock") continue ;; esac
    safe_rel "$rel" || continue
    mkdir -p "$DEST_DIR/$(dirname "$rel")"
    cp -f "$f" "$DEST_DIR/$rel" 2>/dev/null || true
  done < <(find "$RUN_DIR" -type f -print0 2>/dev/null)
  # P0-004: check the result write explicitly (the script runs under
  # `set -uo pipefail`, not `set -e`, so an unchecked failure would
  # pass silently). The sync is already FAILED; a failed record write
  # only adds a diagnostic and never changes the exit code.
  if ! write_result_json "FAILED" "$RUN_ID" "$n_new" "$n_changed" "$n_unchanged" "$pruned" "$n_prune" "$TIMESTAMP"; then
    if run_dir_has_content_backup; then
      echo "ERROR: failed to write final sync status record to $DEST_DIR/.consistency-frame-last-sync.json (sync already FAILED; recovery backup preserved at $RUN_DIR)" >&2
    else
      echo "ERROR: failed to write final sync status record to $DEST_DIR/.consistency-frame-last-sync.json (sync already FAILED; no content backup was created for this run; run record retained at $RUN_DIR)" >&2
    fi
  fi
  exit 1
fi

# Rebuild the owned manifest from the destination state: owned = every
# file present in the source (now copied) plus previously owned files
# that were not pruned. Conflict-kept files carry their previous
# manifest hash (this run did not write them); a conflict with no
# previous entry is not added, so it is reported again next run.
NEW_OWNED="$TMPDIR_WORK/owned-new.txt"; : > "$NEW_OWNED"
while IFS= read -r -d '' src; do
  rel="${src#$SOURCE_DIR/}"
  if grep -qxF "$rel" "$PLAN_CONFLICT" 2>/dev/null; then
    man_sha="$(manifest_sha "$rel")"
    [ -n "$man_sha" ] && echo "$man_sha $rel" >> "$NEW_OWNED"
  else
    echo "$(sha256_file "$SOURCE_DIR/$rel") $rel" >> "$NEW_OWNED"
  fi
done < <(find "$SOURCE_DIR" -type f -print0)
if [ "$PRUNE" = 0 ]; then
  while IFS= read -r rel; do
    [ -z "$rel" ] && continue
    if [ -e "$SOURCE_DIR/$rel" ]; then continue; fi
    if [ -e "$DEST_DIR/$rel" ]; then
      echo "$(manifest_sha "$rel") $rel" >> "$NEW_OWNED"
    fi
  done < "$OWNED_LIST"
else
  # Prune on: refused stale files stay owned at their old manifest hash.
  while IFS= read -r rel; do
    [ -z "$rel" ] && continue
    if [ -e "$DEST_DIR/$rel" ]; then
      echo "$(manifest_sha "$rel") $rel" >> "$NEW_OWNED"
    fi
  done < <(cut -f1 "$PRUNE_REFUSED_TSV")
fi
sort -u "$NEW_OWNED" -o "$NEW_OWNED"
write_manifest "$NEW_OWNED" || { echo "ERROR: failed to write manifest" >&2; exit 1; }

STATUS="SUCCESS"
[ "$failed" = 1 ] && STATUS="PARTIAL"

# Decide whether this run's backup directory may be dropped, but do NOT
# remove it yet (P0-004): no backup run directory is removed before the
# final status record has been persisted. An empty run dir (only the
# owner marker and lock, no real backup) is dropped after a successful
# metadata write; a run that holds a real backup is always kept.
RESULT_RUN_ID="$RUN_ID"
DROP_RUN_DIR=0
if [ -z "$(find "$RUN_DIR" -type f ! -name '.run-owner.json' ! -name '.lock' -print -quit 2>/dev/null)" ]; then
  DROP_RUN_DIR=1
  RESULT_RUN_ID=""
fi

# P0-004: check the result write explicitly. The script runs under
# `set -uo pipefail`, not `set -e`, so the old unchecked call let an
# atomic-write failure fall through to a false "Skill sync SUCCESS"
# with exit 0. That must never happen again.
if write_result_json "$STATUS" "$RESULT_RUN_ID" "$n_new" "$n_changed" "$n_unchanged" "$pruned" "$n_prune" "$TIMESTAMP"; then
  # Final metadata persisted: safe to drop the empty run dir now.
  if [ "$DROP_RUN_DIR" = 1 ]; then
    remove_run_dir "$RUN_DIR" || echo "WARNING: could not remove empty run dir $RUN_DIR" >&2
  fi
  echo "Skill sync $STATUS: new=$n_new changed=$n_changed unchanged=$n_unchanged pruned=$pruned conflicts=$n_conflicts prune_refused=$n_prune_refused run_id=${RESULT_RUN_ID:-none}"
  echo "Manifest: $MANIFEST_FILE"
  [ "$STATUS" = "SUCCESS" ] && exit 0 || exit 2
fi

# Final metadata persistence failed: never report SUCCESS. The run
# directory is preserved (with its valid owner marker); whether it
# holds a content backup depends on what the run did — the
# diagnostics below say so accurately (P0-005). A run that only
# installed new files, or changed nothing, created no content backup.
echo "ERROR: failed to write final sync status record to $DEST_DIR/.consistency-frame-last-sync.json" >&2
if [ $((n_new + n_changed + pruned)) -gt 0 ]; then
  if run_dir_has_content_backup; then
    echo "PARTIAL: sync changes were applied (new=$n_new changed=$n_changed pruned=$pruned) but the final metadata record could not be written; recovery backup preserved at $RUN_DIR (run $RUN_ID)" >&2
    echo "Skill sync PARTIAL: new=$n_new changed=$n_changed unchanged=$n_unchanged pruned=$pruned conflicts=$n_conflicts prune_refused=$n_prune_refused run_id=$RUN_ID (backup preserved)"
  else
    echo "PARTIAL: sync changes were applied (new=$n_new changed=$n_changed pruned=$pruned) but the final metadata record could not be written; no content backup was created for this run; run record retained at $RUN_DIR (run $RUN_ID)" >&2
    echo "Skill sync PARTIAL: new=$n_new changed=$n_changed unchanged=$n_unchanged pruned=$pruned conflicts=$n_conflicts prune_refused=$n_prune_refused run_id=$RUN_ID (no content backup; run record retained)"
  fi
  exit 2
fi
echo "FAILED: no files were changed, but the final metadata record could not be written; no content backup was created; run record retained at $RUN_DIR (run $RUN_ID)" >&2
echo "Skill sync FAILED: new=$n_new changed=$n_changed unchanged=$n_unchanged pruned=$pruned conflicts=$n_conflicts prune_refused=$n_prune_refused run_id=$RUN_ID (no files changed; run record retained)"
exit 1
