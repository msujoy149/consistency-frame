# Nadia and the River Light — P1-006-R2 reference project

Status: **DRAFT — script awaiting user approval.** See
`script-breakdown.md` for the complete script, the script analysis,
and the derived counts (6 scenes, 8 shots, 8 keyframes, 8 I2V
clips, 48 s total). No reference image, keyframe, voice recording,
or provider clip has been generated from this script yet.

## What this project is

One fictional, project-local adult character (Nadia,
DEMO-CHAR-002, age 27, photorealistic-digital-human) in a short
vertical cinematic story: one lantern's journey from dawn to dusk.
Each of the 8 shots starts from its own verified photorealistic
keyframe and becomes a genuine video clip only through an
authorized image-to-video provider execution (fal.ai Kling Video
v3 Pro, `fal-ai/kling-video/v3/pro/image-to-video`). The final
video target is 9:16, 1080x1920, 30 FPS, 30–60 s, H.264/AAC, MP4.

## What is BLOCKED and why

- **Script approval:** the script + breakdown are drafts awaiting
  the user's approval. Until he approves, no visual asset is
  generated.
- **Image-to-video execution:** no paid provider call is
  authorized. The written authorization request is
  `docs/implementation/CF-WO-P1-006-R2-authorization-request.md`
  (8 generations, 6 s each, 1080p, with native audio — estimated
  $8.06). Until the user explicitly approves it, I2V execution
  stays BLOCKED and the driver produces no final video.
- **Delivery:** `qc_status` is BLOCKED; the delivery manifest
  records that, and never claims a delivery.

## Files

- `script.md` — the 8 narration lines (verbatim dialogue).
- `script-breakdown.md` — script analysis + derived counts.
- `character-bible.json` — Nadia's design (references pending
  generation after script approval).
- `shot-list.json` — 8 shots with structured motion prompts
  (subject/face/body/hand/prop/hair/cloth/environment/camera),
  keyframe placeholders (pending), and empty provider-generation
  provenance fields.
- `project.json` — output profile + text-overlay policy (all
  false) + I2V plan (8 clips × 6 s = 48 s).
- `voice-config.json` — narrator voice (VoiceStudio/OmniVoice,
  seed 42, non-commercial-only); WAVs are generated only after
  script approval.
- `production-analysis.json`, `sound-plan.json`,
  `assembly-config.json` — analysis, sound, and assembly plans.

## Rules this project follows

- Photorealistic digital human only — no stylized cartoon,
  oversized eyes, plastic skin, anime, or illustration.
- Genuine image-to-video only — no FFmpeg zoompan, no still as
  MP4, no slideshow, no motion-graphics substitute.
- No on-screen text of any kind (see `text_overlay_policy`).
- Narration only — no lip-sync is claimed.
- Counts are derived from the script, never fixed in advance.
