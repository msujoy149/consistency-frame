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
- `skills/production-systems/` — the 11 professional + 18 extended + 7
  additional systems, plus language, captions, and format rules.

Character identity and voice are fixed once registered. The user's
explicit instructions and script outrank everything else. Character
data is private by default and never committed to this public repo
(see `characters/README.md`). Run the QC checklist before delivering.
