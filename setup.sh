#!/usr/bin/env bash
# Consistency Frame — installer (v2.0, P0 safe foundations)
#
# Two install layers, kept separate on purpose:
#
#   CORE (default, `bash setup.sh`):
#     Non-destructive skill sync only — copies skills/ into
#     .agents/skills/ via scripts/sync-skills.sh. Unmanaged user and
#     third-party skills are never deleted; only Consistency
#     Frame-owned files are updated, tracked by a manifest.
#     No network download, no model weights, no paid service.
#
#   COMPONENTS (opt-in, `bash setup.sh --with-components`):
#     Fetches the bundled components (VoiceStudio for voice, OpenMontage
#     for long-form video) by plain git clone, pinned to a tested commit
#     (VoiceStudio 2f2f5a9, OpenMontage fecb9a1). Their original AGPL-3.0
#     licences stay intact inside each component. The voice model
#     (OmniVoice, CC-BY-NC) is NEVER downloaded by this script — it is
#     installed separately, on request, from Hugging Face.
#
# Usage:
#   bash setup.sh [--core-only] [--with-components] [--dry-run] [--prune]
#
#   --dry-run  Show what the skill sync would do; change nothing.
#   --prune    Opt-in stale-file pruning for manifest-owned skill files
#              only (dry-run first is recommended: --dry-run --prune).
#
# Exit codes: 0 = SUCCESS (every requested component succeeded),
# 2 = PARTIAL (a requested component failed — see the per-component
# status below; nothing is reported as done that did not succeed),
# 1 = FAILED (core skill sync failed, or the run could not start).
# The final summary always prints one status per component.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

WITH_COMPONENTS=0
DRY_RUN=0
PRUNE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --core-only) WITH_COMPONENTS=0; shift ;;
    --with-components) WITH_COMPONENTS=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --prune) PRUNE=1; shift ;;
    --help|-h)
      echo "Usage: bash setup.sh [--core-only] [--with-components] [--dry-run] [--prune]"
      echo "  Default is core-only: non-destructive skill sync, no downloads."
      exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; exit 2 ;;
  esac
done

echo "== Consistency Frame 2.0 — setup =="

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: not inside a git checkout. Clone the repo first:"
  echo "  git clone https://github.com/msujoy149/consistency-frame.git"
  exit 1
fi

# Per-component status, printed in the final summary. Values:
# SUCCESS | PARTIAL | FAILED | SKIPPED.
STATUS_SKILLS="FAILED"
STATUS_VOICESTUDIO="SKIPPED"
STATUS_OPENMONTAGE="SKIPPED"

# 1. Core: non-destructive skill sync ------------------------------------
echo "-- Syncing skills into .agents/skills/ (non-destructive) --"
SYNC_ARGS=()
[ "$DRY_RUN" = 1 ] && SYNC_ARGS+=(--dry-run)
[ "$PRUNE" = 1 ] && SYNC_ARGS+=(--prune)
if bash scripts/sync-skills.sh "${SYNC_ARGS[@]}"; then
  STATUS_SKILLS="SUCCESS"
else
  sync_code=$?
  echo "ERROR: skill sync failed (exit $sync_code). No unmanaged skill was deleted; see scripts/sync-skills.sh output above." >&2
  STATUS_SKILLS="FAILED"
  echo ""
  echo "== Setup FAILED: skills=$STATUS_SKILLS voicestudio=$STATUS_VOICESTUDIO openmontage=$STATUS_OPENMONTAGE =="
  exit 1
fi

if [ "$WITH_COMPONENTS" = 0 ]; then
  echo ""
  echo "Core install done. Components were NOT installed (default)."
  echo "To also install VoiceStudio + OpenMontage, run:"
  echo "  bash setup.sh --with-components"
  echo "The voice model (OmniVoice, CC-BY-NC) is never downloaded by"
  echo "setup.sh; install it separately when you need it — see"
  echo "docs/06-installation.md."
  echo ""
  echo "== Setup SUCCESS: skills=$STATUS_SKILLS voicestudio=$STATUS_VOICESTUDIO openmontage=$STATUS_OPENMONTAGE =="
  exit 0
fi

# 2. Components (opt-in only) -------------------------------------------
# Disk space: the components need ~5 GB. The voice model (~3.3 GB) is
# NOT downloaded here, so it is not counted in this check.
avail_kb=$(df -k "$REPO_ROOT" 2>/dev/null | tail -1 | awk '{print $4}')
if [ -n "$avail_kb" ] && [ "$avail_kb" -lt 5242880 ]; then
  echo "ERROR: less than 5 GB free disk space for the components. Free space and run bash setup.sh --with-components again." >&2
  echo ""
  echo "== Setup FAILED: skills=$STATUS_SKILLS voicestudio=$STATUS_VOICESTUDIO openmontage=$STATUS_OPENMONTAGE =="
  exit 1
fi

echo "-- Installing bundled components (VoiceStudio + OpenMontage) --"

clone_component() {
  local name="$1" url="$2" dir="$3" pin="$4"
  if [ -d "$dir/.git" ]; then
    echo "-- $name already present --"
    return 0
  fi
  if [ -d "$dir" ] && [ -n "$(ls -A "$dir" 2>/dev/null)" ]; then
    echo "ERROR: $dir exists but is not a git checkout. Remove it yourself and run bash setup.sh --with-components again to re-clone $name." >&2
    return 1
  fi
  echo "-- Cloning $name (bundled component, pinned to ${pin:0:7}) --"
  mkdir -p "$(dirname "$dir")"
  if ! git clone --depth 1 "$url" "$dir"; then
    echo "ERROR: could not clone $name from $url (network?). Retry later:" >&2
    echo "  git clone $url $dir" >&2
    return 1
  fi
  # A --depth 1 clone only has the default branch tip, so fetch the
  # pinned commit explicitly, then check it out. The fetch needs the
  # FULL 40-character SHA: a short SHA is read as a ref name and fails
  # with "couldn't find remote ref".
  if (cd "$dir" && git fetch --depth 1 origin "$pin" && git checkout "$pin"); then
    echo "-- $name ready (pinned to ${pin:0:7}) --"
    return 0
  else
    echo "ERROR: could not check out pinned commit $pin for $name. Removing the incomplete clone; run bash setup.sh --with-components again to retry." >&2
    rm -rf "$dir"
    return 1
  fi
}

# Pinned commits (verified to exist upstream, 2026-11-13).
# Full 40-character SHAs — see the note in clone_component above.
# VoiceStudio 2f2f5a9b0e982c6147efc6baaeae62936f29b79b,
# OpenMontage fecb9a1e3cc23ef84de30b272059457a427f16f8.
# NOTE: failures are NOT suppressed here. Each component reports its
# own status and the final exit code reflects it (P0 fix for F2).
if clone_component "VoiceStudio" "https://github.com/debpalash/VoiceStudio" "components/voicestudio" "2f2f5a9b0e982c6147efc6baaeae62936f29b79b"; then
  STATUS_VOICESTUDIO="SUCCESS"
else
  STATUS_VOICESTUDIO="FAILED"
fi
if clone_component "OpenMontage" "https://github.com/OpenMontageInc/OpenMontage" "components/openmontage" "fecb9a1e3cc23ef84de30b272059457a427f16f8"; then
  STATUS_OPENMONTAGE="SUCCESS"
else
  STATUS_OPENMONTAGE="FAILED"
fi

# 3. VoiceStudio setup (only if the clone succeeded) ----------------------
VOICE_OK=1
if [ "$STATUS_VOICESTUDIO" = "SUCCESS" ] && [ -d "components/voicestudio/.git" ]; then
  echo "-- VoiceStudio found. Setting up its API (needs bun + uv) --"
  if command -v bun >/dev/null 2>&1; then
    if ! command -v uv >/dev/null 2>&1 && [ -x "$HOME/.local/bin/uv" ]; then
      export PATH="$HOME/.local/bin:$PATH"
    fi
    if ! (cd components/voicestudio && bun install); then
      echo "WARNING: bun install failed for VoiceStudio." >&2
      VOICE_OK=0
    fi
    if command -v uv >/dev/null 2>&1; then
      echo "-- Installing the VoiceStudio Python API (setup:api; downloads about 1 GB, takes a few minutes) --"
      if ! (cd components/voicestudio && bun run setup:api); then
        echo "WARNING: setup:api failed. Run it manually: cd components/voicestudio && bun run setup:api" >&2
        VOICE_OK=0
      fi
    else
      echo "uv is not installed, so the VoiceStudio Python API cannot be set up here."
      echo "Install uv (https://docs.astral.sh/uv/getting-started/installation/), then run:"
      echo "  cd components/voicestudio && bun run setup:api"
      VOICE_OK=0
    fi
  else
    echo "bun is not installed, so VoiceStudio cannot be set up here."
    echo "Install bun (https://bun.sh), then run this script again, or"
    echo "follow components/voicestudio README instructions manually."
    VOICE_OK=0
  fi
  if [ "$VOICE_OK" = 0 ]; then
    STATUS_VOICESTUDIO="PARTIAL"
  fi
fi

# 4. OpenMontage setup (only if the clone succeeded) -----------------------
if [ "$STATUS_OPENMONTAGE" = "SUCCESS" ] && [ -d "components/openmontage/.git" ]; then
  echo "-- OpenMontage found. Running its own setup (make setup; downloads the Node + Python dependencies, takes a few minutes) --"
  echo "  (Needs Python 3.10+ — uv provides it if installed — plus Node and ffmpeg."
  echo "  No API keys are set by this script. Add provider keys to"
  echo "  components/openmontage/.env only when you need a paid provider.)"
  if command -v make >/dev/null 2>&1; then
    if (cd components/openmontage && make setup); then
      echo "OpenMontage set up."
    else
      echo "WARNING: OpenMontage 'make setup' failed. Run it manually to see the error:" >&2
      echo "  cd components/openmontage && make setup" >&2
      STATUS_OPENMONTAGE="PARTIAL"
    fi
  else
    echo "WARNING: 'make' is not installed, so OpenMontage cannot be set up here." >&2
    echo "On macOS/Linux install it with your package manager; on Windows use WSL"
    echo "(Git Bash does not always ship make). Then run:" >&2
    echo "  cd components/openmontage && make setup" >&2
    STATUS_OPENMONTAGE="PARTIAL"
  fi
fi

# 5. Final summary — the exit code must match the summary -----------------
echo ""
if [ "$STATUS_SKILLS" = "SUCCESS" ] && [ "$STATUS_VOICESTUDIO" = "SUCCESS" ] && [ "$STATUS_OPENMONTAGE" = "SUCCESS" ]; then
  echo "== Done. Next steps =="
  echo "  1. Register a character: give the assistant a name, a unique ID,"
  echo "     3-4 reference photos, and a voice reference."
  echo "  2. Name your series. The assistant records it in the project"
  echo "     register and reads it back before every episode."
  echo "  3. Give a script: scene, characters, dialogue per character,"
  echo "     camera, emotion per line."
  echo "  Docs: docs/06-installation.md (all platforms),"
  echo "        docs/07-character-registry.md (registration rules)."
  echo "  Website: https://consistencyframe.blogspot.com"
  echo "  NOTE: the voice model (OmniVoice, CC-BY-NC — noncommercial)"
  echo "  is NOT installed by setup.sh. Install it separately:"
  echo "    cd components/voicestudio && bun run dev:api"
  echo "    curl -X POST http://127.0.0.1:3900/models/install \\"
  echo "      -H 'Content-Type: application/json' \\"
  echo "      -d '{\"repo_id\": \"k2-fsa/OmniVoice\"}'"
  echo "  Do not use that model for commercial work; use a commercial"
  echo "  voice provider instead."
  echo ""
  echo "== Setup SUCCESS: skills=$STATUS_SKILLS voicestudio=$STATUS_VOICESTUDIO openmontage=$STATUS_OPENMONTAGE =="
  exit 0
elif [ "$STATUS_VOICESTUDIO" = "FAILED" ] || [ "$STATUS_OPENMONTAGE" = "FAILED" ]; then
  echo "== Setup FAILED: skills=$STATUS_SKILLS voicestudio=$STATUS_VOICESTUDIO openmontage=$STATUS_OPENMONTAGE =="
  echo "A component failed (see above). The skills sync itself succeeded;"
  echo "fix the failed component and run bash setup.sh --with-components again."
  exit 1
else
  echo "== Setup PARTIAL: skills=$STATUS_SKILLS voicestudio=$STATUS_VOICESTUDIO openmontage=$STATUS_OPENMONTAGE =="
  echo "Some optional setup steps did not complete (see the warnings above)."
  echo "The skills sync itself succeeded. Fix the failed step, then run"
  echo "bash setup.sh --with-components again."
  exit 2
fi
