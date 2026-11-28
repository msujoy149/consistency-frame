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
  $8.06). **That request is SUPERSEDED** by the preflight Gate B
  authorization sheet
  (`docs/implementation/CF-WO-P1-006-R2-PREFLIGHT-gate-b-authorization.md`):
  same 8 generations and 48 s, but audio OFF — estimated **$10.75**
  (with elements: 48 s x $0.224/s; see `cost-plan.json`). The $10.75
  figure corrects the earlier preflight $5.38 figure, which priced
  every shot at the without-elements $0.112/s rate. The old 8-shot / $8.06 figures are
  superseded as a cost estimate, not as counts. Until the user
  explicitly approves the script (Gate A) and the Gate B sheet,
  I2V execution stays BLOCKED and the driver produces no final
  video.
- **Delivery:** `qc_status` is BLOCKED; the delivery manifest
  records that, and never claims a delivery.

## Files

- `script.md` — the 8 narration lines (verbatim dialogue).
- `script-breakdown.md` — script analysis + derived counts.
- `character-bible.json` — Nadia's design (references pending
  generation after script approval).
- `shot-list.json` — 8 shots with structured motion prompts
  (subject/face/body/hand/prop/hair/cloth/environment/camera),
  keyframe placeholders (pending), empty provider-generation
  provenance fields, and per-shot preflight prompt records
  (`prompt_record`: source script segment, character element
  references, negative prompt, physical realism constraints,
  `generate_audio: false`, text-overlay flags). Preflight
  correction: shot s2 now shows Nadia carrying the lit round
  lantern, as script line l2 requires (see
  `story-coverage-report.json`).
- `story-coverage-report.json`, `scene-breakdown.json`,
  `location-coverage.json`, `character-appearance-map.json`,
  `shot-duration-plan.json` — preflight storyboard outputs
  (CF-WO-P1-006-R2-PREFLIGHT). Line-by-line analysis confirms the
  counts: 6 scenes, 8 shots, 8 keyframes, 8 clips, 48 s — no shot
  added, none removed vs the R2 draft.
- `motion-prompts.md` — human-readable per-shot prompt records.
- `cost-plan.json` + `cost-plan.md` — dynamic cost plan, audio
  OFF, WITH elements: 8 shots x 6 s x $0.224/s = **$10.75**
  (exact $10.752; $1.344 per 6 s shot). Keyframe generation
  $0 billed (platform built-in image generation, not a billed
  provider charge). Retry budget: one retry per failed shot,
  maximum $10.75; worst case $21.50. Taxes/fees UNCONFIRMED.
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
