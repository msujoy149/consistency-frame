# P1-006-R1 — Mara and the Compass Garden (character consistency)

Character-consistency demonstration for CF-WO-P1-006-R1: one
fictional, project-local adult character (Mara, DEMO-CHAR-001,
age 28) across six distinct scenes.

## What this project is

- **Character:** Mara — a fictional demonstration identity, defined
  in `character-bible.json`. She is NOT an existing canonical user
  character and is NOT registered in the global character registry.
  Her binding lives only here and in the p1006-r1 delivery folder.
- **Story:** Mara, a young mapmaker, follows her grandmother's
  brass compass to a hidden garden. Six scenes: attic studio,
  forest path, close-up wonder, stream, meadow run, hidden garden.
- **Visuals:** AI-generated still images (built-in image generation
  of this environment — no external provider, no paid call, no
  credentials), animated locally with deterministic FFmpeg zoompan.
  They are labelled **locally animated stills**, never AI-generated
  video. Reference images and scene stills live ONLY in the
  delivery folder (`~/workspace/consistency-frame-p1-delivery/
  p1006-r1/work/`), referenced here by path + SHA-256 + byte size;
  no image/video/audio binary is committed to this repo.
- **Voice:** real VoiceStudio/OmniVoice narration, non-commercial
  (CC-BY-NC), seed 42, instruct `middle-aged, moderate pitch`,
  en-US. One narrator for all six scenes.
- **Assembly:** FFmpeg only (the P1-006 pipeline). OpenMontage
  production assembly is NOT_TESTED.
- **Delivery:** review package only — `qc_status: BLOCKED` until a
  named human reviewer approves the visual QC evidence.

## Files

- `character-bible.json` — the character canon (confirmed design
  vs production inferences, visual + negative constraints,
  reference inventory, approval state).
- `project.json`, `script.md`, `production-analysis.json`,
  `shot-list.json`, `voice-config.json`, `sound-plan.json`,
  `assembly-config.json` — the production source, same shape as
  the P1-006 reference project.
- Driver: `scripts/run-p1006-r1-character-render.py`.
- Runtime: `runtime/character_consistency.py` (bible validation,
  scene binding, reference integrity, consistency evaluation and
  drift report) and the still-animation extension in
  `runtime/production_assets.py` (`ai-still` recipe kind).

## Honest labels used everywhere

- Scene visuals: `ai-generated-still, locally animated`
  (provider `platform-builtin-image`, EXERCISED).
- Voice: `voicestudio-omnivoice`, non-commercial-only (CC-BY-NC).
- Sound: `synthesized` locally.
- Image-to-video generation: NOT_TESTED (no such provider was
  used; the motion is FFmpeg zoompan on stills).
- OpenMontage production assembly: NOT_TESTED.
