# Installation (All Platforms)

Consistency Frame is a portable system built on the Agent Skills open
standard. The portable core is one folder per skill, containing a
`SKILL.md` file (with YAML frontmatter — `name` and `description`, both
required) plus optional `scripts/`, `references/`, and `assets/`
subfolders.

- Repository: https://github.com/msujoy149/consistency-frame
- Official website: https://consistencyframe.blogspot.com
- Current release: v2.0

The skills in this repository are:

- `character-consistency` — character registry, identity resolution,
  prompt builder, reference fidelity, character recall, multi-character
  scenes.
- `voice-consistency` — voice profiles, single-pass dialogue, voice
  drift, code-switching.
- `humanized-production` — the 36 humanization systems (performance,
  micro-motion, sound, editing, film finish, backgrounds).
- `production-systems` — the 12 professional systems, the 18 extended
  systems, the 7 additional systems, and the language, captions, and
  format rules.

Use the one-command install for your platform below. After installing,
the skills are available to the agent in that platform; character data is
never part of the install — it lives in the private overlay described in
"Character Registry".

---

## Local install (Mac, Windows, Linux)

This is the terminal install on your own computer. It is the same
one-command install as the README's "Local install" section — the
command blocks below are identical there, so copy from either place.

> Honest note: the Linux path was verified end-to-end on a Linux
> machine. The Mac and Windows commands were checked against the
> official installer docs (brew.sh, bun.sh, astral.sh/uv, git-scm.com,
> Microsoft Learn) — no Mac or Windows machine was available here to
> run them on.

### Prerequisites

| What | Why | Mac | Linux (Ubuntu/Debian) | Windows |
| --- | --- | --- | --- | --- |
| git | Clone the repo | `brew install git` | `sudo apt install -y git` | Git for Windows (`winget install --id Git.Git -e --source winget`) or WSL |
| bun | VoiceStudio's JavaScript runtime | `brew install bun` | official installer (below) | PowerShell installer (below) or WSL |
| uv | Python environments (VoiceStudio API, OpenMontage venv) | `brew install uv` | official installer (below) | PowerShell installer (below) or WSL |
| Node.js 22 LTS + npm | OpenMontage's Remotion composer | `brew install node` | NodeSource (below) | `winget install --id OpenJS.NodeJS.LTS -e --source winget` or WSL |
| ffmpeg | Video/audio work | `brew install ffmpeg` | `sudo apt install -y ffmpeg` | `winget install --id Gyan.FFmpeg -e --source winget` or WSL |
| make | Runs OpenMontage's `make setup` | Ships with Xcode Command Line Tools | `sudo apt install -y make` (usually preinstalled) | WSL (Git Bash does not always ship it) |

Python needs no separate install: uv provides Python 3.10 for the
OpenMontage virtual environment, and VoiceStudio's `setup:api` manages
its own Python environment through uv. Disk space: allow ~5 GB for the
components and their dependencies, plus ~3.27 GB more if you download
the OmniVoice voice model (see below).

### Mac

```bash
# Homebrew (skip if you already have it)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
# Prerequisites
brew install git bun uv node ffmpeg
# Consistency Frame
git clone https://github.com/msujoy149/consistency-frame.git
cd consistency-frame
bash setup.sh
```

Homebrew needs the Xcode Command Line Tools (`xcode-select --install`)
and will ask for your Mac login password once. After installing
Homebrew, run the `brew shellenv` lines the installer prints, or `brew`
will not be found in new shells.

### Linux (Ubuntu / Debian)

```bash
# Prerequisites
sudo apt update && sudo apt install -y git curl unzip ffmpeg
# Node.js 22 LTS (Ubuntu's own nodejs package is old — use NodeSource)
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
# bun and uv (official installers; open a new terminal afterwards so PATH picks them up)
curl -fsSL https://bun.com/install | bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# Consistency Frame
git clone https://github.com/msujoy149/consistency-frame.git
cd consistency-frame
bash setup.sh
```

`unzip` is required by the bun installer on Linux. On non-Debian
distributions, install the same tools with your package manager
(`dnf`, `pacman`, `zypper`) — the commands after that point are the
same.

### Windows — WSL (recommended)

```powershell
# PowerShell as Administrator: install WSL + Ubuntu, then restart
wsl --install
```

Then open Ubuntu and follow the Linux steps above. This is the
recommended Windows path: `setup.sh` is a bash script, and WSL gives it
a real Linux shell. Git Bash does not always ship `make`, which
OpenMontage's setup needs.

### Windows — Git Bash

```powershell
# PowerShell as Administrator: Git, Node.js LTS, FFmpeg
winget install --id Git.Git -e --source winget
winget install --id OpenJS.NodeJS.LTS -e --source winget
winget install --id Gyan.FFmpeg -e --source winget
# PowerShell: bun and uv
powershell -c "irm bun.sh/install.ps1 | iex"
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then in Git Bash:

```bash
git clone https://github.com/msujoy149/consistency-frame.git
cd consistency-frame
bash setup.sh
```

Notes: the `Git.Git` winget package is not maintained by the Git for
Windows project and may lag the latest official release — the installer
from git-scm.com is the alternative. If `make --version` reports nothing
in Git Bash, the OpenMontage step in `setup.sh` will say so; use WSL for
that step. Close and reopen the terminal after installing bun/uv so
their PATH changes take effect. Windows needs Windows 10 version 1809
or later for bun.

### What setup.sh does

1. **Clones the bundled components, pinned to tested commits** —
   VoiceStudio (`2f2f5a9`) for voice and OpenMontage (`fecb9a1`) for
   long-form video — into `components/`. Their AGPL-3.0 licences stay
   intact inside each component. Nothing is vendored into this repo;
   the components are fetched at install time.
2. **Copies `skills/` into `.agents/skills/`** (clearing it first, so a
   re-run is exact).
3. **Sets up VoiceStudio** — `bun install`, then the Python API
   (`bun run setup:api`, needs bun + uv; downloads about 1 GB).
4. **Runs OpenMontage's `make setup`** — creates its Python virtual
   environment and installs the Node dependencies. If `make` is missing
   or the step fails, `setup.sh` says so plainly instead of claiming
   success; run `cd components/openmontage && make setup` yourself to
   see the error.
5. **Walks you through the voice-model download** (next section) — it
   does not download the model itself.

Re-running `bash setup.sh` is safe: components already present are
skipped, skills are re-copied exactly, and the component setups run
again.

### The voice model (OmniVoice) — download step

The OmniVoice model weights (~3.27 GB) are **not** bundled in this
repo. After `setup.sh`, `setup.sh` prints the steps; run them:

```bash
cd components/voicestudio && bun run dev:api
curl -X POST http://127.0.0.1:3900/models/install \
  -H 'Content-Type: application/json' \
  -d '{"repo_id": "k2-fsa/OmniVoice"}'
```

The model downloads from the original Hugging Face source
(`k2-fsa/OmniVoice`). It is licensed **CC-BY-NC (noncommercial)** — do
not use that model for commercial work; use a commercial voice provider
instead. The notice is kept wherever the model is used.

### Verifying a local install

```bash
git --version; bun --version; uv --version; node --version; ffmpeg -version | head -1
ls components/voicestudio components/openmontage   # both present, with real content
ls .agents/skills                                  # character-consistency voice-consistency humanized-production production-systems
(cd components/voicestudio && .venv/bin/python -c "import torch; print(torch.__version__)")  # VoiceStudio Python API
(cd components/openmontage && ls .venv)            # OpenMontage virtual environment
```

Also run the checks in "Verifying the install" below (four skills
present, `SKILL.md` frontmatter, no character data installed).

### Troubleshooting

- **`bun: command not found` / `uv: command not found`** — close and
  reopen the terminal, or `source ~/.bashrc` (bash) / `source ~/.zshrc`
  (zsh on Mac). The installers add `~/.bun/bin` and `~/.local/bin` to
  PATH for new shells only.
- **`make: command not found`** — install make (macOS: Xcode Command
  Line Tools; Linux: `sudo apt install -y make`; Windows: use WSL).
- **Component clone fails** — check the network, then run `bash setup.sh`
  again. A failed pin checkout removes the partial clone, so a re-run
  starts clean.
- **VoiceStudio `setup:api` fails** — run it manually to see the error:
  `cd components/voicestudio && bun run setup:api`. It needs uv on
  PATH (`~/.local/bin/uv` is added automatically by `setup.sh` when
  present).
- **OpenMontage `make setup` fails** — run it manually:
  `cd components/openmontage && make setup`. Common cause: a missing
  prerequisite from the table above.
- **No API keys are needed for the install itself.** Provider keys go
  in `components/openmontage/.env` only when you use a paid
  image/video provider.

---

## Claude Code

Install the plugin from the marketplace. The marketplace name and the
plugin name are both `consistency-frame`:

```text
/plugin marketplace add msujoy149/consistency-frame
/plugin install consistency-frame@consistency-frame
```

The marketplace manifest is `.claude-plugin/marketplace.json`; the
plugin manifest is `.claude-plugin/plugin.json` at the repository root,
and the plugin's skills load from the plugin's own `skills/` folders.
Nothing needs to be copied into `.claude/skills/` by hand.

## Codex

Install the plugin from the marketplace. The marketplace manifest is
`.agents/plugins/marketplace.json`; the plugin manifest is `plugin.json`
at the repository root (`.codex-plugin/plugin.json` is the same plugin
in the older compatibility layout). The marketplace name and the plugin
name are both `consistency-frame`:

```bash
codex plugin marketplace add msujoy149/consistency-frame
```

Then, inside a Codex session, open `/plugins`, select the
`consistency-frame` marketplace, and install the plugin. The plugin's
skills then load from the plugin's own `skills/` folders. (Running
`bash setup.sh` additionally copies the skills into `.agents/skills/`.)

## ChatGPT

Use the same skill folders, uploaded via the Skills tab.

1. Download or clone the repository (see "Clone the repository" below).
2. In ChatGPT, open the Skills tab.
3. Upload the skill folders from `skills/` — one folder per skill, each
   containing its `SKILL.md`.

## Gemini CLI

Install as an extension with a `gemini-extension.json` manifest.

```bash
gemini extensions install https://github.com/msujoy149/consistency-frame
```

## Antigravity

Skills go in `.agents/skills/` (project) and
`~/.gemini/config/skills/` (global). Project rules live in `AGENTS.md`
and `GEMINI.md`.

1. Clone the repository (see "Clone the repository" below).
2. Copy the `skills/` folders into `.agents/skills/` in the project,
   and into `~/.gemini/config/skills/` for global availability.
3. Keep the rules in `AGENTS.md` / `GEMINI.md` alongside the skills.

## Muse (Meta's personal app)

Muse has no documented skill-install flow. Install by cloning the
repository into the workspace and running the bundled setup script,
which installs the bundled components (VoiceStudio for voice,
OpenMontage for video) and copies the skills into `.agents/skills/`.

```bash
git clone https://github.com/msujoy149/consistency-frame
cd consistency-frame
bash setup.sh
```

`setup.sh` installs the bundled components and copies `skills/` into
`.agents/skills/`. The two components (VoiceStudio for voice,
OpenMontage for video) are fetched automatically by `setup.sh` — no
separate install is needed. Character data is not installed by the setup
script — it is linked in separately from the private overlay (see
"Character Registry").

## Generic installers

For any platform that supports the generic skill installers:

```bash
npx skills add msujoy149/consistency-frame
```

```bash
gh skill install msujoy149/consistency-frame
```

## Clone the repository

For a manual install on any platform:

```bash
git clone https://github.com/msujoy149/consistency-frame
```

Then copy the `skills/` folders into the skill directory your platform
uses (see the platform sections above), and read the documentation in
`docs/` — start with "Character Registry" before registering any
character.

## Verifying the install

After installing, check that:

1. Each skill folder contains a `SKILL.md` with `name` and `description`
   in its YAML frontmatter.
2. The four skills listed at the top of this document are all present.
3. No character data (reference images, voice recordings, personal
   data) was installed — character data lives only in the private
   overlay, never in the public repository.
