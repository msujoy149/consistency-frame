#!/usr/bin/env bash
# Consistency Frame — one-command installer (v2.0)
#
# Installs the bundled components and the skills:
#   1. Fetches the bundled components (VoiceStudio for voice, OpenMontage
#      for long-form video) — by plain git clone. Their original
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
#   ./setup.sh
#
# In Muse (Meta's personal app, which has no skill-install flow):
#   clone this repo into your workspace and run ./setup.sh here,
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

# The published tree carries no submodule links, so the installs below
# are plain git clones — the only path that works in this repo.
echo "-- Installing bundled components (VoiceStudio + OpenMontage) --"

clone_component() {
  local name="$1" url="$2" dir="$3"
  if [ -d "$dir/.git" ]; then
    echo "-- $name already present --"
    return 0
  fi
  if [ -d "$dir" ] && [ -n "$(ls -A "$dir" 2>/dev/null)" ]; then
    echo "WARNING: $dir exists but is not a git checkout. Remove it and run ./setup.sh again to re-clone $name:"
    echo "  rm -rf $dir"
    return 1
  fi
  echo "-- Cloning $name (bundled component) --"
  mkdir -p "$(dirname "$dir")"
  if git clone --depth 1 "$url" "$dir"; then
    echo "-- $name ready --"
  else
    echo "WARNING: could not clone $name from $url (network?). Retry later:"
    echo "  git clone $url $dir"
    return 1
  fi
}

clone_component "VoiceStudio" "https://github.com/debpalash/VoiceStudio" "components/voicestudio" || true
clone_component "OpenMontage" "https://github.com/OpenMontageInc/OpenMontage" "components/openmontage" || true

# 2. Skills -------------------------------------------------------------
echo "-- Installing skills into .agents/skills/ --"
# .agents/skills holds only copies of skills/, so clearing it first
# keeps a re-run exact (no stale skills left behind).
rm -rf .agents/skills
mkdir -p .agents/skills
cp -r skills/* .agents/skills/
echo "Installed skills: $(ls .agents/skills | tr '\n' ' ')"

# 3. VoiceStudio (voice) -------------------------------------------------
if [ -d "components/voicestudio" ]; then
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
      echo "VoiceStudio is only partly set up (see the warnings above). Fix the failed step, then run ./setup.sh again."
    fi
  else
    echo "bun is not installed, so VoiceStudio cannot be set up here."
    echo "Install bun (https://bun.sh), then run this script again, or"
    echo "follow components/voicestudio README instructions manually."
  fi
else
  echo "VoiceStudio is not installed — run ./setup.sh again, or clone it:"
  echo "  git clone https://github.com/debpalash/VoiceStudio components/voicestudio"
fi

# 4. OpenMontage (long-form video) ---------------------------------------
if [ -d "components/openmontage" ]; then
  echo "-- OpenMontage found. Run its own setup when you need it: --"
  echo "    cd components/openmontage && make setup"
  echo "  (Needs Python 3.12, Node, and ffmpeg; no API keys are set by"
  echo "  this script. Add provider keys to components/openmontage/.env"
  echo "  only when you need a paid image/video provider.)"
else
  echo "OpenMontage is not installed — run ./setup.sh again, or clone it:"
  echo "  git clone https://github.com/OpenMontageInc/OpenMontage components/openmontage"
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
