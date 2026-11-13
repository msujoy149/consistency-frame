# Consistency Frame

**An open-source, portable system for AI video production: the same characters and voices in every scene and episode, in any AI platform.**

Consistency Frame is a portable system for making videos whose characters
stay the same in every scene and whose voices stay the same in every
episode — and whose images, dialogue, and sound feel human-made, not
AI-made. Install the repository in any AI platform and the skills come
with it: you introduce your characters and your series once, and
afterwards you only give scripts and images.

- **Website:** https://consistencyframe.blogspot.com
- **Version:** 2.0 (first release)
- **Licence:** Apache-2.0 (see [Licence](#licence))

---

## The problem it solves

AI video tools forget. A character's face drifts from shot to shot. A
voice changes between episodes. Dialogue sounds clean, flat, and robotic.
Backgrounds are empty. Hands break. The result reads as AI the moment a
viewer looks at the eyes, hears a too-perfect voice, or notices two mouths
moving at once.

Consistency Frame fixes that with a system, not a hope: a character
registry, fixed prompt blocks and voice profiles, a production pipeline,
and 116 numbered entries (105 distinct systems, each named and checkable)
covering identity, voice, performance, camera direction,
sound, editing, grading, disclosure, and quality control. Nothing is left
to chance, and nothing is left vague — every rule is a rule an AI can
follow and a human can check.

## Install — one command

```bash
git clone https://github.com/msujoy149/consistency-frame.git
cd consistency-frame
bash setup.sh
```

> Run it with `bash` — a fresh clone from GitHub does not carry the executable bit, so `./setup.sh` fails with "Permission denied".

`setup.sh` fetches and installs the bundled components (VoiceStudio for
voice, OpenMontage for long-form video) automatically — no separate
install is needed — and copies the skills into `.agents/skills/`, so any
platform that reads skills from that directory picks them up
automatically. It also walks you through downloading the voice model
(see [Voice](#voice)).

Per-platform install details are in
[`docs/06-installation.md`](docs/06-installation.md). In short:

| Platform | How the skills load |
| --- | --- |
| Claude Code | Plugin marketplace: `.claude-plugin/marketplace.json` |
| Codex | Plugin marketplace: `.agents/plugins/marketplace.json` (plugin manifest: `plugin.json` at the root; `.codex-plugin/plugin.json` kept for compatibility) |
| ChatGPT | Upload the `skills/` folder via the Skills tab |
| Gemini CLI | Extension: `gemini-extension.json` |
| Antigravity | Skills in `.agents/skills/`, rules in `AGENTS.md` / `GEMINI.md` |
| Muse (Meta) | Clone into the workspace and run `bash setup.sh` |
| Any other tool | `npx skills add msujoy149/consistency-frame` or `gh skill install msujoy149/consistency-frame` |

## Local install — Mac, Windows, Linux

To install on your own computer (not only inside an AI platform), use a
terminal. The full per-OS guide — prerequisites, what `setup.sh` does,
the voice-model download, verification, and troubleshooting — is in
[`docs/06-installation.md`](docs/06-installation.md).

> Honest note: the Linux path below was verified end-to-end on a Linux
> machine. The Mac and Windows commands were checked against the
> official installer docs (brew.sh, bun.sh, astral.sh/uv, git-scm.com,
> Microsoft Learn) — no Mac or Windows machine was available here to
> run them on.

### Mac

```bash
# Homebrew (skip if you already have it)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
# Prerequisites (Python comes via uv — no separate Python install needed)
brew install git bun uv node ffmpeg
# Consistency Frame
git clone https://github.com/msujoy149/consistency-frame.git
cd consistency-frame
bash setup.sh
```

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
their PATH changes take effect.

## Quick start

1. **Install** (above) and run `bash setup.sh`.
2. **Register a character.** Give the installed assistant a name, a
   unique ID, 3–4 reference photos, and a voice reference. See
   [Character registration](#character-registration).
3. **Start a series.** Give the series a name. The assistant records it
   in the project register and reads it back before every episode.
4. **Give a script.** Scene, characters, dialogue per character, camera,
   emotion per line. The assistant asks every open question in one go
   (characters, language per character, captions, ratio, platform,
   short/long) and never asks the same question twice.
5. **Get the episode.** The assistant generates with the registered
   characters and voices, runs the QC checklist, and delivers.

## Features — 116 numbered entries (105 distinct systems)

The complete system is 116 numbered entries across the skills and
docs — 105 distinct systems. (Eleven of the 12 professional systems are listed
twice: once in the production-systems skill and once in
docs/01-production-systems.md — the script-driven automatic camera angles
system is numbered in the skill only, and the video regeneration, cinematic
power, live-action & VFX, emotional performance, user-supplied voice cloning, on-demand resource management, and language authenticity systems are numbered in their own skills only — so 12 + 18 + 3 + 7 + 36 + 7 + 1 + 5 + 6 + 7 + 1 + 1 + 1 = 105 distinct
systems, 116 listed entries.) They are grouped in eleven layers: a
character and voice foundation, humanized production, professional
production, language, captions, and format, agency advertising, video
regeneration, cinematic power, live-action & VFX, emotional performance, on-demand resources, and language authenticity. The skill files in
`skills/` are the source of truth; the `docs/` folder describes each
system in full.

### Character consistency — the foundation

- **Character registry.** Every character has one folder: a
  `character.yaml` (name, unique ID, age, gender, look, voice profile,
  seed), 3–4 reference images (front, 3/4, full body, expressions), and
  a voice reference audio. A name in a script resolves to that
  character's ID, reference image, voice, and prompt block — each
  character resolved separately, so faces never merge.
- **100% reference fidelity.** The character is built 100% from the
  reference image(s). Face and height matter most. One photo is enough;
  several are more reliable.
- **Character recall.** Ask any time and the system shows the character
  exactly as stored, so you can check face, height, and structure.
- **Turnaround and detail reference sheet.** Every character gets one
  sheet — front, side, and back views plus close-ups of face, hands,
  and feet — built from the reference images and stored as
  `model-sheet.jpg`. Every new scene is checked against it, so the
  face, height, and body stay the same from every angle.
- **Identity anchoring.** Every generation reuses the same approved
  reference — the same reference images, the same sheet, the same fixed
  prompt block, and the same seed. The identity is never rebuilt from a
  fresh interpretation; the structure stays 100% identical across
  scenes and episodes.
- **Expression library.** Expressions the user did not supply are
  generated from the definitive reference (face and structure
  unchanged), saved per character, and reused — never generated twice.
- **Fixed structure, variable clothing.** Eyes, nose, mouth, face, hands,
  and feet stay the same in every scene. Clothing and props change with
  the scene — but never randomly: the outfit the user selects stays
  exactly as-is until the user says to change it, or the script clearly
  needs a change (for example, swimming), and the new outfit then holds
  in that context.
- **Multi-character scenes, no overlap.** 3–5 characters together is
  fine. Natural contact is allowed — a hand on a shoulder, holding
  hands, touching hair — but one character or object must never go
  inside another. Bodies stay separate and solid.
- **Quantitative drift measurement.** Face-embedding similarity is
  measured per shot; below threshold, regenerate. Voices are measured
  the same way (see [Voice](#voice)).

### Voice — one voice per character, forever

- **Fixed voice profiles.** Tone, apparent age, language, fixed tags,
  fixed seed, reference audio — set once per character, reused every
  episode. Generate once, save the output, reuse it as the reference to
  lock the voice.
- **Realistic, script-driven emotion.** The voice performs like a human
  actor. Emotion comes from the script and matches each line. If
  dialogue sounds robotic, viewers will realise it is AI and lose
  interest.
- **Single-pass multi-speaker dialogue.** A whole conversation in one
  call, up to 10 voices, with real ~200 ms gaps — not stitched lines.
- **Non-verbal voice.** Sighs, laughs, whispers, breaths, hesitations.
  Real speech is messy; a clean, pause-free take is the audio uncanny
  valley.
- **Code-switching.** Bengali↔English mid-sentence, with a separate
  listening test per language. A multilingual model is not assumed
  equally good in every language.
- **Per-character language.** In one video each character may speak a
  different language; dialogue, voice, and lip-sync follow that
  character's language.
- **Voice drift, ageing, and distance.** Speaker-embedding similarity and
  a prosody fingerprint are measured per line and per episode. Voice
  variants cover age, illness, whisper/shout, tiredness, and cold.
  Level, reverb, and muffling change with camera distance and room.

### Humanized production — 36 systems

The largest layer, `skills/humanized-production/`, makes footage feel
filmed, not generated:

- **Performance first.** A real human performance (phone/webcam
  driving video) is the biggest leap — it drives the pixels. When no
  performance is available, script-driven emotion rules apply.
- **Involuntary motion.** Blink cadence, eye movements, breathing, head
  micro-drift. Dead eyes and a frozen face are defects.
- **Listener reactions.** When one character speaks, the other visibly
  listens — and never moves their mouth.
- **Never-silence sound.** Room tone in every interior, four sound
  layers (ambience, foley, dialogue, music), a sound spotting sheet per
  shot. Silence is a defect.
- **Anti-plastic skin.** Visible pores, fine lines, freckles, uneven
  tone. The words "flawless", "perfect", and "airbrushed" are banned
  from prompts.
- **Hands and physics.** Frame hands out, keep hand shots to 3–5 second
  segments, repair with masked inpainting. Never make pouring, grasping,
  or tying the hero action.
- **Editing rhythm.** J-cuts, L-cuts, cut on action, cut on the phrase.
  Stitched clips with simultaneous audio and video cuts feel stitched.
- **Film finish.** Correct, then LUT at reduced strength, then 35 mm
  grain (8–15%), then light blur. AI footage is too clean.
- **Camera and light.** Handheld breathing, focus pulls, 24 fps feel.
  Shadow direction, colour temperature, and light position are locked
  per scene.
- **Backgrounds.** The background is what the eye rests on most — every
  background is detailed, layered, with depth, atmosphere, and life.
  Never empty, flat, or generic.
- **Eye and gaze continuity, mouth-interior QC, wardrobe wear,
  imperfection budget, dialogue-first mixing, failure playbooks,
  real-person safeguards, realism budget, blind-test gates, model
  pinning, re-anchoring every ~8–16 seconds, and reference-count
  strategy per model.** All 36 are in
  [`docs/05-humanization-systems.md`](docs/05-humanization-systems.md).

### Professional production — 12 + 18 + 7 systems

- **12 professional systems** (`docs/01-production-systems.md` and the
  production-systems skill): visual
  style bible, camera language and shot list, script-driven automatic camera
  angles, negative prompt library,
  sound design system, music and theme, story bible, episode continuity
  tracker, dialogue writing rules, reference photo quality rules,
  lip-sync and dubbing workflow, episode QC checklist.
- **18 extended systems** (`docs/02-extended-systems.md`): captions
  pipeline, thumbnail/poster generator, character turnarounds, wardrobe
  registry, seam continuity, drift measurement, LoRA training, ageing
  variants, provenance log, cost tracking, backup/versioning,
  multi-series namespaces, child safety, audio mastering (−14 LUFS),
  localisation/dubbing, distribution package ("Made for Kids" is set
  only when the content is for children or the user asks for it),
  rights and consent, audience feedback loop.
- **7 additional systems** (`docs/04-additional-systems.md`): private
  character data separation, multi-character no-overlap, episode intake
  checklist, demo project (on demand), script template with automatic
  enhancement, contribution guide, and script-driven realism and colour
  grading — the grade follows the script's time of day and light source
  (full-moon night = cool blue moonlight, sunlight = warm daylight,
  evening = soft warm grade, morning = fresh morning light, dusk =
  orange-purple twilight, midnight = deep dark grade, torchlight at
  night = warm torch light with real shadows), and never changes
  randomly inside one scene.

### Language, captions, and format

- **Captions are opt-in.** The assistant asks at generation time; the
  default is no baked-in captions. If wanted, captions in any language
  the user requests.
- **Per-character language.** In one video each character may speak a
  different language; dialogue, voice, and lip-sync follow that
  character's language — never force all characters into one language.
- **Format on demand.** 16:9, 9:16, 1:1, 4:5, or any ratio; short or
  long video; any platform, not only YouTube. Composed for that ratio
  from the start, never cropped afterwards.

The system is content-agnostic: kids animation, adult animation, and
videos from real photos of adults all work the same way. Full rules:
[`docs/03-language-captions-format.md`](docs/03-language-captions-format.md).

### Agency advertising — 7 systems

- **Brand kit.** The model plus the brand's logo, colours, tagline,
  fonts, and voice tone profile, locked together in one kit per brand
  — the single source of truth for every ad.
- **Ad formats.** 9:16 Reels/Shorts/TikTok, 1:1 feed, 16:9 YouTube,
  composed for the ratio from the start; hook inside the first 3
  seconds, clear CTA at the end, safe zones kept clear of platform UI.
- **Campaign variants.** One master ad cut down to 6s / 15s / 30s,
  same model, voice, and brand kit; A/B variants change one thing at
  a time and are tracked per variant ID.
- **Client isolation.** Per-client workspaces; the model, brand kit,
  and voice are checked against the client's workspace before every
  generation — one client's assets never appear in another client's ad.
- **AI disclosure and likeness safety.** Every ad carries the
  platform's AI-generated disclosure; the model's face must not
  resemble any real person; watermarks and provenance are never
  removed.
- **Product/service consistency.** Product shots, wording, prices, and
  claims are locked per campaign and identical across all its ads.
- **Client approval workflow.** Draft → client review → approved →
  publish; every revision is a new version, approvals are recorded per
  version, and only the approved version is published.

The model is a registered character created through the Character
Generator; this layer adds only the advertising rules on top. Full
rules: [`docs/08-agency-advertising.md`](docs/08-agency-advertising.md).

### Video regeneration — 1 system

- **Video regeneration.** The user uploads a video and asks for it to be
  regenerated: the system first analyses the reference in full (story,
  scenes in order, characters, objects, camera, light, sound), then
  creates a NEW original video that preserves the reference's core story,
  emotional impact, narrative structure, and creative direction — with
  only minor or explicitly requested changes. Character and object
  continuity, physically correct handovers and interactions, cinematic
  realism, a storyboard before generation, original audio, and a mandatory
  QC pass before delivery. The reference is the user's own uploaded video;
  the output is an alternative version, never a frame-for-frame copy.

Full rules: [`docs/09-video-regeneration.md`](docs/09-video-regeneration.md).

### Cinematic power — 5 systems

- **Stylized animation style lock.** 2D anime, 3D stylized CG, or photorealistic — chosen first and held in every shot; line weight and cel colour for anime, proportions and squash-and-stretch for CG, realism rules for live-action.
- **Animal and creature performance.** Animals registered like characters, each distinct; movement follows the creature's real body; sidekicks have comic timing, monsters have menace in stillness, and elemental forces may act as characters.
- **Music-beat editing and synchronized ensemble.** Cuts and movements land on the musical beat; a synchronized jump or dance shares one timing reference for every character and animal, with no drift.
- **Trailer and teaser structure.** Wonder → stakes → characters → one comedy beat after tension → climax montage → title card → credits; never reveal the ending.
- **Scale, spectacle, and colour scripting.** Scale contrast for wonder, planned per beat; a colour palette assigned to each emotional beat with planned transitions — colour follows emotion, not only time of day.

Full rules: [`docs/10-cinematic-power.md`](docs/10-cinematic-power.md).

### Live-action & VFX — 6 systems

- **Live-action human performance.** A real body performs: micro-expressions, breath, fatigue, weight; effort shows where the action is hard; the face in the close-up matches the body in the wide shot.
- **VFX integration — CG creatures in live footage.** The creature shares the live plate's light, casts shadows and reflections, gets wet when the scene is wet; the actor's eyeline hits the creature's eyes; scale is fixed; contact is real.
- **Water, wetness, and underwater continuity.** The wet state (hair, skin, clothes, salt, sand) is tracked across cuts and changes only when the story changes it; underwater shots hold a fixed look with water-driven movement.
- **Practical locations and set extension.** The real place is extended with CG and the seam never shows — one light, one haze, one water line; the actor walks from the built set into the extension without the join ever being noticed.
- **Live-action stunt and action choreography.** Action is planned beat by beat and shot to look unplanned; the camera hides the safety, never the impact; the character stays readable through the fastest action.
- **Real-animal performance.** A real animal does what it does — many takes, cut around its real behaviour, comic timing made in the edit; CG touch-up only where the animal cannot perform, preserving its real body.

Full rules: [`docs/11-live-action-vfx.md`](docs/11-live-action-vfx.md).

### Emotional performance — 7 systems

- **Musical performance and stagecraft.** A live performance on stage: the song has an arc — nervous start, finding the groove, the crowd won over, triumph — and the staging follows it: the lighting brightens as the song builds, the performer's body loosens, the crowd's energy rises. The stage is a warm island in a cool night.
- **Crowd as a living character.** Hundreds of distinct people, never a copy-paste — each different in face, hat, clothes, age — reacting in waves: a gasp spreads, applause rises, the crowd leans in. The crowd's mood is the scene's barometer; reaction shots cut between the performer and individual crowd faces.
- **Intimate drama and emotional arc.** A long scene between two people, held for minutes on their faces. The emotional turn is slow — no response, a flicker, recognition, tears, joy — built from micro-expressions, pauses, and silence; the camera stays close and still and lets the faces do the work; the arc is planned beat by beat in the shot list.
- **Age performance.** Age changes everything: movement slow, trembling, frail; voice slow, thin, frail; face with deep wrinkles, drooping lids, cloudy eyes; mind with memory loss, then a flicker of recognition. The very old act mostly with their eyes and hands. Different ages perform differently in the same scene.
- **Instrument performance sync.** When a character plays an instrument, the hands must play the music you hear: fingers on the frets match the notes, strumming matches the rhythm. Hand close-ups are checked against the audio; the instrument is a hero prop, the same look every time it appears.
- **Music as story and memory.** The song IS the plot: it unlocks a memory, changes a mind, heals a family. It starts small — one voice, one instrument — and the room joins it emotionally, each face changing at a different moment. The music is never background; it is the scene's action.
- **Cultural authenticity and object storytelling.** One culture, held in every shot — festival, flowers, banners, dress, family house, food — never generic. Props carry history and plot: a torn photograph, a hero instrument, a drawer that hides the truth. An object's damage and reveal are planned beats, and its state matches the story's state at every cut.

Full rules: [`docs/12-emotional-performance.md`](docs/12-emotional-performance.md).

### On-demand resources — 1 system

- **Load only what the phase needs.** Planning and writing run on working memory only, with both plugins off. Voice generation runs the voice plugin only. Video assembly runs the video plugin only. Both plugins together only when a step genuinely needs both at the same time — otherwise the steps are sequenced.
- **Model weights load to generate, unload after.** The OmniVoice weights load only while voice is being generated; stopping the backend unloads them. One character's voice at a time; never preload all characters' voices.
- **Nothing runs "just in case".** The voice backend stops immediately after the voice work is done; assembly processes stop immediately after the render is done.
- **The quality guard is non-negotiable.** Resource discipline never degrades quality: if a job needs both plugins, run both; if the machine cannot hold both, sequence the work — never cut quality, skip checks, or degrade output.

Full rules: [`docs/13-resource-management.md`](docs/13-resource-management.md).

### Language authenticity — 1 system

- **Native patterns, never textbook speech.** Every language is spoken the way its native speakers speak it: US English carries the American tone and everyday phrasing, Bengali the Bengali tone and idiom, Hindi the Hindi tone and idiom. If a listener cannot tell which language's speakers the voice belongs to, the pattern is wrong.
- **Native register.** Casual scripts sound casual the way natives are casual — including colloquial and slang words the way native speakers actually use them. Authenticity changes how a line is spoken, never what it says.
- **Multi-language delivery.** The same video in N languages means N complete versions — dialogue, voice, lip-sync, and on-screen text all in that version's language. Asked separately, the videos are delivered separately.
- **One voice across languages.** The same character voice profile speaks each language; the voice stays recognizably the same character.
- **Lip-sync follows the language's sounds.** English, Bengali, and Hindi move the mouth differently. Every line's mouth movement is verified against its own audio track; a talking character with a still mouth is a defect, never a delivery.

Full rules: [`docs/14-language-authenticity.md`](docs/14-language-authenticity.md).

## Character registration

Registering a character takes all three of these, in one go:

1. **Reference image(s)** — 3–4 photos (front, 3/4, full body,
   expressions). Clear, well-lit, face to camera, neutral expression.
   A name written on the image is **not** mandatory: if you give photos
   and say in your message whose they are ("these are
   <character-name>'s pictures"), that binds them. A name on the image is required only
   when several characters' images are uploaded together in one batch.
2. **Name + unique ID** in the message — e.g. `<character-name>` with ID
   `char-001`. A duplicate name with a different ID stops the
   registration and asks you first.
3. **Explicit authorisation** — e.g. "Register this character
   permanently." Uploading an image alone does not register a character.

### Two ways to create a character

- **You supply the picture.** Give a picture and say "use this as my
  character" — that picture, exactly as given, is the character.
- **The AI generates it.** You do not have to supply all pictures:
  ask the AI to generate the character, it shows it to you first, and
  only when you say "done — use this one" does it become your
  registered character. From then on it keeps the same structure in
  every scene and episode — locked from the approved version, while
  clothing and props still vary per scene.

Everything about a character — images, voice, prompt block — lives in
that character's own folder. Character data is **private by default**
and is **never** committed to this public repository; it lives in a
separate private overlay (see
[`characters/README.md`](characters/README.md) and
[`docs/07-character-registry.md`](docs/07-character-registry.md)).

## Voice

Voice work runs through VoiceStudio, bundled as a component
(`components/voicestudio`, cloned by `setup.sh`), with the OmniVoice model for zero-shot voice
cloning across 600+ languages.

- The OmniVoice model weights (~3.2 GB) are **not** bundled in this
  repo. `setup.sh` walks you through downloading them from the original
  Hugging Face source (`k2-fsa/OmniVoice`) at install time — you run the
  download step yourself.
- The OmniVoice model is licensed **CC-BY-NC (noncommercial)**. Do not
  use that model for commercial work; use a commercial voice provider
  instead. The notice is kept intact wherever the model is used.
- Long-form video runs through OpenMontage, bundled as a component
  (`components/openmontage`, cloned by `setup.sh`), which stitches short clips into long
  episodes.

## Project and series register

Every project is recorded: series name, episode list, characters in use,
and continuity notes (events, outfits, injuries, objects, end states)
written after each episode and read before the next. Projects are
isolated unless you request a continuation, sequel, or reuse. One repo
serves many series — characters are introduced per project, after
install, and the same repo is reused for the next series.

## Demo project

The repo ships with an on-demand demo system: a sample character and a
sample episode, provided only when you ask for one — never forced. No
demo content is included in the repo. See
[`demo/README.md`](demo/README.md).

## How the skills work

The skills are the source of truth. Each folder in `skills/` holds one
`SKILL.md` (Agent Skills open standard: YAML frontmatter with `name`
and `description`, plus the full instructions):

| Skill | Covers |
| --- | --- |
| `character-consistency` | Registry, identity resolution, prompt builder, reference fidelity, recall, multi-character scenes |
| `voice-consistency` | Voice profiles, VoiceStudio/OmniVoice, single-pass dialogue, voice drift, code-switching |
| `humanized-production` | The 36 humanization systems |
| `production-systems` | The 12 professional + 18 extended + 7 additional systems, plus language, captions, and format rules |
| `agency-advertising` | Brand kit, ad formats, campaign variants, client isolation, AI disclosure and likeness safety, product/service consistency, client approval |
| `video-regeneration` | Reference analysis, new-not-duplicate remake, character/object continuity, physical interactions, cinematography, storyboard, audio, QC, output requirements |
| `cinematic-power` | Style lock, animal and creature performance, music-beat editing and synchronized ensemble, trailer structure, scale and colour scripting |
| `live-action-vfx` | Live-action human performance, VFX integration of CG creatures, water and wetness continuity, practical locations and set extension, stunt and action choreography, real-animal performance |
| `emotional-performance` | Musical performance and stagecraft, crowd as a living character, intimate drama and emotional arc, age performance, instrument performance sync, music as story and memory, cultural authenticity and object storytelling |
| `resource-management` | Load only what the phase needs: voice plugin for voice work, video plugin for video assembly, working memory for the current phase; stop rules and the quality guard |
| `language-authenticity` | Native patterns per language (US English, Bengali, Hindi), multi-language delivery, one voice across languages, lip-sync matched to the language's sounds |

`AGENTS.md`, `CLAUDE.md`, and `GEMINI.md` are thin pointers to
`skills/` — one source of truth, read by every platform.

## Contributing

Read [`CONTRIBUTING.md`](CONTRIBUTING.md). The short version: keep the
consistency and safety rules intact, describe every change, test before
submitting, keep licence and attribution. See
[`CHANGELOG.md`](CHANGELOG.md) for what changed in each release.

## Licence

This project's own work — the consistency system, skills, prompts, and
instructions — is licensed under the **Apache License 2.0** (see
`LICENSE`). Bundled components keep their own licences: VoiceStudio and
OpenMontage are **AGPL-3.0** (included as bundled components, cloned by
`setup.sh`, licences intact),
and the OmniVoice model is **CC-BY-NC (noncommercial)** (downloaded at
install, weights not bundled). Nothing is reverse-engineered or
re-licensed; attribution is stated plainly wherever someone else's work
is used.

## Acknowledgements

- [VoiceStudio](https://github.com/debpalash/VoiceStudio) (AGPL-3.0) —
  local voice studio and OmniVoice integration.
- [OpenMontage](https://github.com/OpenMontageInc/OpenMontage)
  (AGPL-3.0) — long-form video composition.
- [OmniVoice](https://huggingface.co/k2-fsa/OmniVoice) (CC-BY-NC) —
  zero-shot voice cloning model.
- [Agent Skills](https://agentskills.io) — the open standard this repo's
  skill format follows.
