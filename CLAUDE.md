# Consistency Frame — Claude instructions

This repository is a portable system for making videos with consistent
characters and voices that feel human-made. The skills in `skills/` are
the source of truth. Read them and follow them.

- `skills/character-consistency/` — character registry, identity
  resolution, prompt builder, reference fidelity, character recall,
  multi-character scenes.
- `skills/voice-consistency/` — voice profiles, VoiceStudio/OmniVoice,
  single-pass dialogue, voice drift, code-switching.
- `skills/humanized-production/` — the 36 humanization systems.
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

Character identity and voice are fixed once registered. The user's
explicit instructions and script outrank everything else. Character
data is private by default and never committed to this public repo
(see `characters/README.md`). Run the QC checklist before delivering.
