# Consistency Frame — agent instructions

This repository is a portable system for making videos with consistent
characters and voices that feel human-made. The skills in `skills/` are
the source of truth. Read them and follow them; do not invent your own
versions of these rules.

## Skills (source of truth)

- `skills/character-consistency/` — character registry, identity
  resolution, prompt builder, reference fidelity, character recall,
  multi-character scenes.
- `skills/voice-consistency/` — voice profiles, VoiceStudio/OmniVoice,
  single-pass dialogue, voice drift, code-switching.
- `skills/humanized-production/` — the 36 humanization systems
  (performance, micro-motion, sound, editing, film finish, backgrounds).
- `skills/production-systems/` — the 11 professional + 18 extended + 7
  additional systems, plus language, captions, and format rules.

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
`docs/07-character-registry.md`.
