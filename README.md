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
and 86 numbered entries (75 distinct systems, each named and checkable)
covering identity, voice, performance,
sound, editing, grading, disclosure, and quality control. Nothing is left
to chance, and nothing is left vague — every rule is a rule an AI can
follow and a human can check.

## Install — one command

```bash
git clone https://github.com/msujoy149/consistency-frame.git
cd consistency-frame
./setup.sh
```

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
| Muse (Meta) | Clone into the workspace and run `./setup.sh` |
| Any other tool | `npx skills add msujoy149/consistency-frame` or `gh skill install msujoy149/consistency-frame` |

## Quick start

1. **Install** (above) and run `./setup.sh`.
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

## Features — 86 numbered entries (75 distinct systems)

The complete system is 86 numbered entries across the skills and
docs — 75 distinct systems. (The 11 professional systems are listed
twice: once in the production-systems skill and once in
docs/01-production-systems.md, so 11 + 18 + 3 + 7 + 36 = 75 distinct
systems, 86 listed entries.) They are grouped in four layers: a
character and voice foundation, humanized production, professional
production, and language, captions, and format. The skill files in
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
- **Fixed structure, variable clothing.** Eyes, nose, mouth, face, hands,
  and feet stay the same in every scene. Clothing and props change with
  the scene.
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

### Professional production — 11 + 18 + 7 systems

- **11 professional systems** (`docs/01-production-systems.md`): visual
  style bible, camera language and shot list, negative prompt library,
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

## Character registration

Registering a character takes all three of these, in one go:

1. **Reference image(s)** — 3–4 photos (front, 3/4, full body,
   expressions). Clear, well-lit, face to camera, neutral expression.
   A name written on the image is **not** mandatory: if you give photos
   and say in your message whose they are ("these are Serena's
   pictures"), that binds them. A name on the image is required only
   when several characters' images are uploaded together in one batch.
2. **Name + unique ID** in the message — e.g. `riya` with ID
   `char-riya-001`. A duplicate name with a different ID stops the
   registration and asks you first.
3. **Explicit authorisation** — e.g. "Register this character
   permanently." Uploading an image alone does not register a character.

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
| `production-systems` | The 11 professional + 18 extended + 7 additional systems, plus language, captions, and format rules |

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
