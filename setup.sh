#!/usr/bin/env bash
# Consistency Frame — one-command installer (v2.0)
#
# Installs the bundled components and the skills:
#   1. Fetches the bundled components (VoiceStudio for voice, OpenMontage
#      for long-form video) — by plain git clone, after attempting a
#      submodule update for checkouts that carry gitlinks. Their original
#      AGPL-3.0 licences stay intact inside each component.
#      (A plain clone is the reliable path: the GitHub push that
#      publishes this repo carries files only, so the tree has no
#      submodule gitlinks for `git submodule update` to act on.
#      setup.sh therefore clones any missing component itself.)
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

# A checkout that carries submodule gitlinks gets them from this step;
# a plain file-based checkout (the published repo) has none, so the
# direct clones below do the real work.
echo "-- Installing bundled components (VoiceStudio + OpenMontage) --"
git submodule update --init --recursive 2>/dev/null || true

clone_component() {
  local name="$1" url="$2" dir="$3"
  if [ -d "$dir/.git" ]; then
    echo "-- $name already present --"
    return 0
  fi
  if [ -d "$dir" ] && [ -n "$(ls -A "$dir" 2>/dev/null)" ]; then
    echo "-- $name already present --"
    return 0
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
mkdir -p .agents/skills
cp -r skills/* .agents/skills/
echo "Installed skills: $(ls .agents/skills | tr '\n' ' ')"

# 3. VoiceStudio (voice) -------------------------------------------------
if [ -d "components/voicestudio" ]; then
  echo "-- VoiceStudio found. Setting up its API (needs bun + uv) --"
  if command -v bun >/dev/null 2>&1; then
    (cd components/voicestudio && bun install >/dev/null 2>&1 || true)
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
