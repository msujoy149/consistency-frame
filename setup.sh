#!/usr/bin/env bash
# Consistency Frame — one-command installer (v2.0)
#
# Installs the bundled components and the skills:
#   1. Fetches the bundled components (VoiceStudio for voice, OpenMontage
#      for long-form video) — by plain git clone, pinned to a tested
#      commit (VoiceStudio 2f2f5a9, OpenMontage fecb9a1). Their original
#      AGPL-3.0 licences stay intact inside each component.
#      (A plain clone is the reliable path: the GitHub push that
#      publishes this repo carries files only, so the tree has no
#      submodule gitlinks. setup.sh therefore clones any missing
#      component itself.)
#   2. Copies skills/ into .agents/skills/ so any platform that reads
#      skills from that directory picks them up automatically.
#   3. Walks you through downloading the OmniVoice voice model
#      (weights are NOT bundled; they come from Hugging Face and are
#      CC-BY-NC — noncommercial).
#
# Usage:
#   git clone https://github.com/msujoy149/consistency-frame.git
#   cd consistency-frame
#   bash setup.sh
#
# In Muse (Meta's personal app, which has no skill-install flow):
#   clone this repo into your workspace and run bash setup.sh here,
#   exactly like OpenMontage and VoiceStudio are installed.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

echo "== Consistency Frame 2.0 — setup =="

# 1. Bundled components --------------------------------------------------
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: not inside a git checkout. Clone the repo first:"
  echo "  git clone https://github.com/msujoy149/consistency-frame.git"
  exit 1
fi

# Disk space: the components need ~5 GB and the OmniVoice model ~3.3 GB.
# If free space cannot be determined, the check is skipped.
avail_kb=$(df -k "$REPO_ROOT" 2>/dev/null | tail -1 | awk '{print $4}')
if [ -n "$avail_kb" ] && [ "$avail_kb" -lt 9437184 ]; then
  echo "ERROR: less than 9 GB free disk space (components need ~5 GB, the OmniVoice model ~3.3 GB). Free space and run bash setup.sh again."
  exit 1
fi

# The published tree carries no submodule links, so the installs below
# are plain git clones — the only path that works in this repo.
echo "-- Installing bundled components (VoiceStudio + OpenMontage) --"

clone_component() {
  local name="$1" url="$2" dir="$3" pin="$4"
  if [ -d "$dir/.git" ]; then
    echo "-- $name already present --"
    return 0
  fi
  if [ -d "$dir" ] && [ -n "$(ls -A "$dir" 2>/dev/null)" ]; then
    echo "WARNING: $dir exists but is not a git checkout. Remove it and run bash setup.sh again to re-clone $name:"
    echo "  rm -rf $dir"
    return 1
  fi
  echo "-- Cloning $name (bundled component, pinned to ${pin:0:7}) --"
  mkdir -p "$(dirname "$dir")"
  if ! git clone --depth 1 "$url" "$dir"; then
    echo "WARNING: could not clone $name from $url (network?). Retry later:"
    echo "  git clone $url $dir"
    return 1
  fi
  # A --depth 1 clone only has the default branch tip, so fetch the
  # pinned commit explicitly, then check it out. The fetch needs the
  # FULL 40-character SHA: a short SHA is read as a ref name and fails
  # with "couldn't find remote ref".
  if (cd "$dir" && git fetch --depth 1 origin "$pin" && git checkout "$pin"); then
    echo "-- $name ready (pinned to ${pin:0:7}) --"
  else
    echo "WARNING: could not check out pinned commit $pin for $name. Removing the clone; run bash setup.sh again to retry."
    rm -rf "$dir"
    return 1
  fi
}

# Pinned commits (verified to exist upstream, 2026-11-13).
# Full 40-character SHAs — see the note in clone_component above.
# VoiceStudio 2f2f5a9b0e982c6147efc6baaeae62936f29b79b,
# OpenMontage fecb9a1e3cc23ef84de30b272059457a427f16f8.
clone_component "VoiceStudio" "https://github.com/debpalash/VoiceStudio" "components/voicestudio" "2f2f5a9b0e982c6147efc6baaeae62936f29b79b" || true
clone_component "OpenMontage" "https://github.com/OpenMontageInc/OpenMontage" "components/openmontage" "fecb9a1e3cc23ef84de30b272059457a427f16f8" || true

# 2. Skills -------------------------------------------------------------
echo "-- Installing skills into .agents/skills/ --"
# .agents/skills holds only copies of skills/, so clearing it first
# keeps a re-run exact (no stale skills left behind).
rm -rf .agents/skills
mkdir -p .agents/skills
cp -r skills/* .agents/skills/
echo "Installed skills: $(ls .agents/skills | tr '\n' ' ')"

# 3. VoiceStudio (voice) -------------------------------------------------
# A directory that is not a git checkout is not a usable install (see
# clone_component above) — skip it instead of running setup inside it.
if [ -d "components/voicestudio/.git" ]; then
  echo "-- VoiceStudio found. Setting up its API (needs bun + uv) --"
  if command -v bun >/dev/null 2>&1; then
    # `bun run setup:api` needs uv on PATH; it is often in ~/.local/bin.
    if ! command -v uv >/dev/null 2>&1 && [ -x "$HOME/.local/bin/uv" ]; then
      export PATH="$HOME/.local/bin:$PATH"
    fi
    voice_ok=1
    (cd components/voicestudio && bun install) || { echo "WARNING: bun install failed for VoiceStudio."; voice_ok=0; }
    if command -v uv >/dev/null 2>&1; then
      echo "-- Installing the VoiceStudio Python API (setup:api; downloads about 1 GB, takes a few minutes) --"
      (cd components/voicestudio && bun run setup:api) || { echo "WARNING: setup:api failed. Run it manually: cd components/voicestudio && bun run setup:api"; voice_ok=0; }
    else
      echo "uv is not installed, so the VoiceStudio Python API cannot be set up here."
      echo "Install uv (https://docs.astral.sh/uv/getting-started/installation/), then run:"
      echo "  cd components/voicestudio && bun run setup:api"
      voice_ok=0
    fi
    if [ "$voice_ok" = 1 ]; then
      echo "VoiceStudio dependencies installed. Model download is next:"
      echo "  Start the backend, then install the OmniVoice model:"
      echo "    cd components/voicestudio && bun run dev:api"
      echo "    curl -X POST http://127.0.0.1:3900/models/install \\"
      echo "      -H 'Content-Type: application/json' \\"
      echo "      -d '{\"repo_id\": \"k2-fsa/OmniVoice\"}'"
      echo "  NOTE: OmniVoice (k2-fsa/OmniVoice) is CC-BY-NC — noncommercial."
      echo "  Do not use that model for commercial work; use a commercial"
      echo "  voice provider instead."
    else
      echo "VoiceStudio is only partly set up (see the warnings above). Fix the failed step, then run bash setup.sh again."
    fi
  else
    echo "bun is not installed, so VoiceStudio cannot be set up here."
    echo "Install bun (https://bun.sh), then run this script again, or"
    echo "follow components/voicestudio README instructions manually."
  fi
else
  if [ -d "components/voicestudio" ]; then
    echo "VoiceStudio is not a valid checkout — remove components/voicestudio and run bash setup.sh again."
  else
    echo "VoiceStudio is not installed — run bash setup.sh again."
  fi
fi

# 4. OpenMontage (long-form video) ---------------------------------------
# As above: only a real checkout is a usable install.
if [ -d "components/openmontage/.git" ]; then
  echo "-- OpenMontage found. Running its own setup (make setup; downloads the Node + Python dependencies, takes a few minutes) --"
  echo "  (Needs Python 3.10+ — uv provides it if installed — plus Node and ffmpeg."
  echo "  No API keys are set by this script. Add provider keys to"
  echo "  components/openmontage/.env only when you need a paid provider.)"
  if command -v make >/dev/null 2>&1; then
    if (cd components/openmontage && make setup); then
      echo "OpenMontage set up."
    else
      echo "WARNING: OpenMontage 'make setup' failed. Run it manually to see the error:"
      echo "  cd components/openmontage && make setup"
    fi
  else
    echo "WARNING: 'make' is not installed, so OpenMontage cannot be set up here."
    echo "On macOS/Linux install it with your package manager; on Windows use WSL"
    echo "(Git Bash does not always ship make). Then run:"
    echo "  cd components/openmontage && make setup"
  fi
else
  if [ -d "components/openmontage" ]; then
    echo "OpenMontage is not a valid checkout — remove components/openmontage and run bash setup.sh again."
  else
    echo "OpenMontage is not installed — run bash setup.sh again."
  fi
fi

echo ""
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
