# Consistency Frame — agent instructions

This repository is a portable system for making videos with consistent
characters and voices that feel human-made. The skills in `skills/` are
the source of truth. Read them and follow them; do not invent your own
versions of these rules.

## Command authority

This repo is the command master: for every video, read and use the
repo's skills first — a skill that exists in the repo is used, never
reinvented. If a needed skill is not in the repo, check the repo's
comments and notes about that topic first and follow them; only if the
repo gives no comment, generate the system yourself in the repo's skill
format, save it as a new skill, and tell the user plainly what was added
and why.

## Skills (source of truth)

- `skills/character-consistency/` — character registry, identity
  resolution, prompt builder, reference fidelity, character recall,
  multi-character scenes.
- `skills/voice-consistency/` — voice profiles, VoiceStudio/OmniVoice,
  single-pass dialogue, voice drift, code-switching.
- `skills/humanized-production/` — the 36 humanization systems
  (performance, micro-motion, sound, editing, film finish, backgrounds).
- `skills/production-systems/` — the 12 professional + 18 extended + 7
  additional systems, plus language, captions, and format rules.
- `skills/agency-advertising/` — brand kit, ad formats, campaign
  variants, client isolation, AI disclosure, product consistency,
  client approval.
- `skills/video-regeneration/` — reference analysis, new-not-duplicate
  remake, character/object continuity, physical interactions,
  cinematography, storyboard, audio, QC, output requirements.
- `skills/cinematic-power/` — style lock, animal and creature
  performance, music-beat editing and synchronized ensemble, trailer
  structure, scale and colour scripting.
- `skills/live-action-vfx/` — live-action human performance, VFX
  integration of CG creatures in live footage, water, wetness and
  underwater continuity, practical locations and set extension,
  live-action stunt and action choreography, real-animal performance.
- `skills/emotional-performance/` — musical performance and
  stagecraft, crowd as a living character, intimate drama and
  emotional arc, age performance, instrument performance sync, music
  as story and memory, cultural authenticity and object storytelling.
- `skills/resource-management/` — load only what the phase needs:
  voice plugin for voice work, video plugin for video assembly,
  working memory for the current phase; stop rules and the quality
  guard.
- `skills/language-authenticity/` — every language spoken the way its
  native speakers speak it (US English, Bengali, Hindi); the same video
  in every language asked for, separately on request; one voice across
  languages; lip-sync matched to the language's sounds.
- `skills/realistic-person/` — a real person's photo becomes a realistic
  moving, speaking person: the face never changes, movement and speech
  are natural, lip-sync follows the language's sounds.
- `skills/explainer-animation/` — 2D flat cartoon / stick-figure explainer
  that teaches one idea through simple scenes and visual metaphors: flat
  2D vector, thick black outlines, small palette, two character designs
  kept apart, one idea per scene, almost no on-screen text.
- `skills/command-authority/` — the repo is the command master: read and
  use the repo's skills first for every video; a missing system is
  generated only after checking the repo's notes, then saved as a new
  skill and reported to the user.
- `skills/kids-family-animation/` — professional kids & family animation:
  short-form videos for children and young audiences across 14 animation
  methods, one locked visual style, a full camera decision system, 3D and
  2D craft, ten story templates, short-form structure, animation QC, and
  a permanent reference library.

## Rules that always apply

- A character's identity (face, eyes, nose, mouth, hands, feet) is
  fixed across every scene. Clothing and props change with the scene.
- A character's voice (tags + seed + reference audio) is fixed across
  every episode.
- The user's explicit instructions and script outrank everything else.
- Character data is private by default. Never commit reference images,
  voice recordings, or personal data to this public repo. Character
  data lives in a separate private overlay (see
  `characters/README.md`).
- Never claim a check you did not perform. Run the QC checklist
  (`skills/production-systems/`) before delivering.

## Docs

Full system documentation lives in `docs/`. Install instructions are in
`docs/06-installation.md`. The character registry is documented in
`docs/07-character-registry.md`, and the advertising layer in
`docs/08-agency-advertising.md`, and video regeneration in
`docs/09-video-regeneration.md`, and cinematic power in
`docs/10-cinematic-power.md`, and live-action and VFX in
`docs/11-live-action-vfx.md`, and emotional performance in
`docs/12-emotional-performance.md`, and on-demand resources in
`docs/13-resource-management.md`, and language authenticity in
`docs/14-language-authenticity.md`, and realistic person video in
`docs/15-realistic-person.md`, and 2D explainer animation in
`docs/16-explainer-animation.md`, and command authority in
`docs/17-command-authority.md`, and kids & family animation in
`docs/18-kids-family-animation.md`.
