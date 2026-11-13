# Changelog

All notable changes to Consistency Frame are recorded here. Releases use
semantic-style versioning: small updates bump the minor number (2.1,
2.2), big breaking changes bump the major number (3.0). Every release
lists what changed.

## [Unreleased]

### Added

- Local install on Mac, Windows, and Linux via the terminal: a "Local
  install" section in the README and a full per-OS guide in
  docs/06-installation.md — exact commands per OS (Mac: Homebrew +
  `brew install git bun uv node ffmpeg`; Linux: apt + NodeSource +
  official bun/uv installers; Windows: Git Bash path with winget +
  PowerShell installers, and a WSL path), prerequisites, what
  `setup.sh` does, the OmniVoice model download step, verification,
  and troubleshooting. The Linux path was verified end-to-end on a
  Linux machine; Mac/Windows commands were checked against official
  installer docs only — no Mac or Windows machine was available to run
  them on.
- `setup.sh` now pins the bundled components to tested commits
  (VoiceStudio `2f2f5a9`, OpenMontage `fecb9a1`, using their full
  40-character SHAs — a short SHA fails the fetch with "couldn't find
  remote ref") and runs OpenMontage's `make setup` instead of only
  printing the command; a missing `make` or a failed step is reported
  honestly, not claimed as success.
- Generic character-consistency system, documented as a reusable
  template in docs/07-character-registry.md, skills/
  character-consistency/SKILL.md, characters/README.md, and the
  README: registration (name + unique ID + reference image(s) +
  explicit authorization, all required; an image alone does not
  register), structure fixed / clothing and props variable per scene,
  turnaround + detail reference sheet (front/side/back views, face/
  hands/feet close-ups, stored as `model-sheet.jpg`) as the identity
  anchor for every scene, and identity anchoring (the same approved
  reference reused in every generation; structure 100% identical
  across scenes and episodes).
- Character Generator — two ways to create a character: a
  user-supplied picture used exactly as given, or an AI-generated
  character shown to the user first and registered only on explicit
  "done" approval, after which its structure is locked from the
  approved version. No generated character becomes permanent without
  that approval.
- Privacy scrub: all example character names in the repo replaced
  with generic placeholders (`<character-name>`, `char-001`); no
  character pictures or real character data in the repo.
- Outfit consistency — script-driven: the outfit the user selects
  stays exactly as-is until the user says to change it; a scene-driven
  change (for example, swimming) is allowed, and the new outfit then
  holds in that context. Outfits change only on the user's word or a
  clear scene need — never randomly. Documented in the
  character-consistency skill, docs/07, the wardrobe registry
  (docs/02, production-systems skill), and the README.
- Face-consistency correction method: one user-approved image as the
  definitive reference reused in every generation, front-facing for
  face-critical shots, an explicit no-change instruction in every
  prompt, fresh regeneration (never editing) when the face drifts, and
  verification against the reference before delivery.
- Reference matching is mandatory for every generation, angles and
  expressions follow the script explicitly, and verification is
  angle-matched: a shot is compared against the sheet's matching
  head-turn view (front, 3/4 left, left profile, back, right profile,
  3/4 right) and its matching expression panel (twelve expressions),
  instead of comparing every angle against the front view only. The
  turnaround sheet now carries those six head-turn views and twelve
  expression panels.
- Expression auto-generation and library: missing expressions are
  generated from the definitive reference (face and structure 100%
  identical), saved per character under
  `characters/<character-id>/expressions/<expression-name>`, and reused
  from then on — never regenerated twice. The library grows on demand
  as scripts need new expressions, and persists across sessions as
  part of the character record.
- Agency advertising layer — seven new systems for using a registered
  AI-generated model as an agency spokesperson across ads (skill:
  skills/agency-advertising/SKILL.md; doc:
  docs/08-agency-advertising.md): brand kit (model + logo + colours +
  tagline + fonts + voice tone, locked per brand), ad formats (9:16,
  1:1, 16:9, hook in the first 3 seconds, clear CTA, platform safe
  zones), campaign variants (6s / 15s / 30s cut-downs from one master,
  A/B variants changing one thing at a time, tracked per variant ID),
  client isolation (per-client workspaces; model, brand kit, and voice
  checked against the client's workspace before every generation), AI
  disclosure and likeness safety (platform disclosure on every ad,
  likeness check at registration and after drift, never remove
  watermarks or provenance), product/service consistency (product
  shots, wording, prices, and claims locked per campaign), and client
  approval workflow (draft → review → approved → publish; every
  revision a new version; approval recorded per version). The model
  itself is a registered character created through the Character
  Generator; this layer adds only the advertising rules on top. Counts
  updated everywhere: 82 distinct systems, 93 numbered entries.
- Script-driven automatic camera angles: the angle for every shot is
  decided automatically from the script beat — story function, emotion,
  character relationship, and what the viewer must notice — never by
  habit or rotation; full shot grammar (wide, medium, close-up, extreme
  close-up, over-the-shoulder, POV, low / high / bird's-eye / worm's-eye,
  Dutch tilt, two-shot, group wide), a beat-to-angle mapping (emotion
  always wins over the table), motivated movement only, lens language
  (35mm for place and togetherness, 50mm for honest human presence,
  85mm for intimacy), the 180-degree rule and eyeline/action continuity
  across cuts, human-camera imperfection (faint handheld sway, a breath
  of focus hunting, framing corrected mid-shot — subtle, never
  distracting), one angle logic per beat planned in the shot list before
  generation, and user override wins. It also covers no-script
mode: when the system generates the story itself, it first writes
the story as beats and then directs the angles from those beats, so
the angle decision is mandatory in both modes and the shot list with
angles is part of the generated script. Realism target: aim for 100%
  realistic, human-generated feeling; 99.9% is the floor. Documented as
  A12 in the production-systems skill, cross-referenced from docs/01 §2.
  Counts updated everywhere: 83 distinct systems, 94 numbered entries.

- Video regeneration — a new skill (`skills/video-regeneration/SKILL.md`)
  and doc (`docs/09-video-regeneration.md`): the user uploads a reference
  video and the system first analyses it in full (story, scenes in order,
  characters, objects, camera, light, sound), then creates a NEW original
  video preserving the reference's core story, emotional impact, narrative
  structure, and creative direction, with only minor or explicitly
  requested changes. Covers character and object continuity, physically
  correct handovers and interactions (no merging, passing through, or
  disappearing objects), cinematic realism, a storyboard before generation,
  original audio, a mandatory QC pass before delivery, and output
  requirements (aspect ratio, pacing, duration, clips when the model
  limit is shorter). The reference is the user's own uploaded video; the
  output is an alternative version, never a frame-for-frame copy.
  Counts updated everywhere: 84 distinct systems, 95 numbered entries.
- Cinematic power — five new systems for feature-trailer and music-video quality (skill: skills/cinematic-power/SKILL.md; doc: docs/10-cinematic-power.md): stylized animation style lock (2D anime, 3D stylized CG, or photorealistic, chosen first and held in every shot), animal and creature performance (animals registered like characters, movement follows the creature's real body, comic timing for sidekicks, menace in stillness for monsters, elemental forces as characters), music-beat editing and synchronized ensemble (cuts and movements land on the musical beat, one timing reference for the whole ensemble), trailer and teaser structure (wonder → stakes → characters → comedy beat → climax montage → title card → credits), and scale, spectacle, and colour scripting (scale contrast for wonder, palettes assigned per emotional beat with planned transitions). Counts updated everywhere: 89 distinct systems, 100 numbered entries.
- Live-action and VFX — six new systems for live-action and VFX hybrid quality (skill: skills/live-action-vfx/SKILL.md; doc: docs/11-live-action-vfx.md): live-action human performance (a real body performs — micro-expressions, breath, fatigue, weight; effort shows; the face in the close-up matches the body in the wide shot), VFX integration of CG creatures in live footage (the creature shares the live plate's light, casts shadows and reflections, gets wet when the scene is wet; the actor's eyeline hits the creature's eyes; scale is fixed; contact is real), water, wetness and underwater continuity (the wet state is tracked across cuts and changes only when the story changes it; underwater shots hold a fixed look with water-driven movement), practical locations and set extension (the real place is extended with CG and the seam never shows — one light, one haze, one water line), live-action stunt and action choreography (action planned beat by beat and shot to look unplanned; the camera hides the safety, never the impact; the character stays readable), and real-animal performance (the animal does what it does — many takes, cut around its real behaviour, comic timing made in the edit; CG touch-up only where the animal cannot perform). Counts updated everywhere: 95 distinct systems, 106 numbered entries.

### Fixed

- Audit fixes (deep review of the first release). The "86 systems"
  count is now explained everywhere it appears: 75 distinct systems,
  86 numbered entries, because the 11 professional systems are listed
  both in the production-systems skill and in docs/01.
- The Claude Code marketplace now points at the repository root (the
  plugin directory). Codex gains the missing
  `.agents/plugins/marketplace.json` (with the correct source shape —
  the plugin was not discoverable without it), a current-format
  `plugin.json` at the repository root, and `./`-prefixed paths in its
  plugin manifests.
- `setup.sh` now installs the VoiceStudio Python API (`bun run
  setup:api`), not only the JavaScript dependencies; it reports a
  failed install instead of claiming success, and it warns (instead of
  claiming "already present") when a component directory exists but is
  not a git checkout.
- Model-download wording corrected everywhere: `setup.sh` walks you
  through downloading the OmniVoice weights; it does not download them
  itself.
- "Submodule" wording corrected to bundled components cloned by
  `setup.sh` (the published tree carries no submodule links).
- Character-registry file names in docs/07 now match
  characters/README.md. The language section now lists the actual third
  rule (per-character language) and links docs/03; the Made-for-Kids
  rule is noted under the distribution package where it belongs.
- `.gitignore` now covers the install outputs `.agents/skills/` and
  `components/` (the Codex marketplace manifest
  `.agents/plugins/marketplace.json` stays tracked).

## [2.0] — 2026-11-12 — First release

The first public release. The complete system: **86 numbered entries (75 distinct systems)** for
consistent characters, consistent voices, and human-feeling video, in
any AI platform. The 11 professional systems are listed twice — once in the production-systems skill and once in docs/01 — so 11 + 18 + 3 + 7 + 36 = 75 distinct systems, 86 listed entries.

### Included

- **Character consistency** — character registry (per-character folder:
  `character.yaml`, 3–4 reference images, voice reference audio),
  registration rules (name + unique ID + reference image(s) + explicit
  authorization; name-on-image not mandatory, required only when several
  characters' images arrive in one batch), identity resolution (a name
  in a script resolves to that character's ID + reference image + voice
  + prompt block), prompt builder (fixed prompt block + fixed seed per
  character), 100% reference fidelity (face and height most important;
  one photo enough, several more reliable), character recall (show the
  character exactly as stored, on request), fixed identity structure
  with scene-variable clothing and props, multi-character scenes with no
  overlap, private character data separation with a private overlay.
- **Voice consistency** — fixed voice profiles (tags + seed + reference
  audio) per character, reused every episode; VoiceStudio/OmniVoice
  integration; single-pass multi-speaker dialogue; voice-drift
  measurement; voice ageing and state variants; code-switching and
  dialect rule with a separate listening test per language;
  distance-and-space in voice; dialogue-first mixing.
- **Professional production systems (11)** — visual style bible;
  camera language and shot list; negative prompt library; sound design
  system; music and theme; story bible; episode continuity tracker;
  dialogue writing rules; reference photo quality rules; lip-sync and
  dubbing workflow; episode QC checklist.
- **Extended production systems (18)** — subtitles/captions pipeline;
  thumbnail/poster generator; character turnaround/model sheets;
  wardrobe/prop/location registry; clip-boundary seam continuity;
  quantitative drift measurement; per-character LoRA training;
  character aging/time-jump variants; shot-level provenance log; cost &
  credit tracking; backup/versioning of character data;
  multi-project/multi-series namespaces; child-safety rules; audio
  mastering standard (−14 LUFS); localisation/dubbing pack;
  distribution package; rights/consent/provenance records; audience
  feedback loop.
- **Language, captions, and format rules (3)** — captions OPT-IN (ask
  first, default no baked-in captions, any language on request);
  per-character language in one video; format/aspect ratio on demand
  (16:9, 9:16, 1:1, 4:5, any ratio; short or long; any platform;
  compose for the ratio from the start, never crop afterwards).
- **Additional systems (7)** — private character data separation;
  multi-character scenes and no overlap; episode intake checklist;
  demo project (on-demand system, no demo content shipped); script
  template and automatic script enhancement; contribution guide;
  script-driven realism and colour grading by time of day and light
  source.
- **Humanization systems (36)** — performance-driven acting;
  single-pass multi-speaker dialogue; involuntary micro-motion;
  listener-reaction rule; room tone / never-silence + 4-layer sound;
  non-verbal voice layer; eye/gaze continuity; hands & physics
  avoidance + repair; anti-plastic skin; editing rhythm; film-finish
  pipeline; voice-drift measurement; temporal-artifact QC; camera
  imperfection; lighting-continuity lock; background life; cloth/hair
  physics; distance & space in voice; sound spotting sheet; AI
  disclosure & provenance pack; detector self-QC; audio description
  track; voice ageing/state variants; code-switching & dialect rule;
  model-version pinning + golden regression; re-anchor every ~8–16 s;
  reference-count strategy per model; human blind-test gate;
  mouth-interior QC in lip-sync; wardrobe wear & continuity detail;
  imperfection budget; music-ducking / dialogue-first mix; failure &
  fallback playbook; real-person safeguards; realism budget; cinematic
  backgrounds.
- **Portable install** — Agent Skills standard (`skills/` as the source
  of truth) with thin per-platform manifests for Claude Code, Codex,
  Gemini CLI, and Antigravity, plus a Muse path (clone + `./setup.sh`).
  VoiceStudio and OpenMontage bundled as components, fetched by
  setup.sh (the published tree carries no submodule links); OmniVoice
  weights downloaded by the user at install time from Hugging Face with
  the CC-BY-NC notice.
- **Docs** — full system documentation in `docs/`, including the two
  background research reports in `docs/research/`.
- **Licence** — this project's own work under Apache-2.0; VoiceStudio
  and OpenMontage under AGPL-3.0 (bundled components, licences intact);
  OmniVoice model under CC-BY-NC (noncommercial).
