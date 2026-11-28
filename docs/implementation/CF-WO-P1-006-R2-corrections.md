# CF-WO-P1-006-R2 corrections — Mandatory Photorealistic
Image-to-Video Generation & Real Motion Production

Work order CF-WO-P1-006-R2, branch
`feat/cf-p1-004-universal-production-brain`, PR #5 (open, Draft,
unmerged). Starting HEAD: the R1 head (remote head at round
start; local tree identical, clean). Build on that tree; no
history rewrite.

This document records what was decided, what was built, what
was verified, and what is still blocked. It quotes no generated
value (no commit SHA, file hash, byte count, or manifest entry
count) — those live in the generated reports, which are
regenerated after the code.

## §1. The mandatory addendum: script-first, no fixed counts

The original brief ordered six scenes. The addendum (received
mid-round) supersedes that plan in full:

1. **No fixed count anywhere.** No fixed six scenes / shots /
   keyframes / clips — and no replacement fixed number. Counts
   are determined by the complete story and script.
2. **Script-driven breakdown first.** Before any visual asset:
   the complete script; every location, environment, character
   action, important object, physical event, emotional reaction
   and narrative development; the complete scene and shot
   breakdown; the required keyframes and genuine I2V generations
   for every required shot. No story event is omitted to reduce
   clips; no shot is invented to inflate the count. One scene may
   need multiple shots; one continuous action may need multiple
   clips when provider duration limits require segmentation. The
   production system calculates scene count, shot count,
   keyframe count, I2V clip count, location/environment assets,
   per-shot duration estimates and total runtime from the script
   analysis (`runtime/image_to_video.py::derive_project_counts`).
3. **The script is a draft awaiting approval.** No R2 script was
   supplied by the user. A complete script was drafted (see §7)
   and its breakdown derived from it. **No keyframe, reference
   image, or voice recording has been generated from it** — the
   script + breakdown must be presented to the user and approved
   by him before any visual asset is generated.
4. Everything that assumed six was updated: reference project,
   driver, tests (fixed-six assertions replaced with
   script-derived-count assertions), docs, and the authorization
   request (clip count and cost are the script-derived count).

## §2. Superseded draft images (deleted, record kept)

Under the original brief — which ordered keyframe generation —
four Nadia reference images and six scene keyframes were
generated with the platform built-in image tool, chained from
the front reference, and visually inspected (verdict: identity
consistent, photorealistic, no text in any frame; honest
observations: brass bangle on the RIGHT wrist in two scenes
vs canon left wrist; an unprompted folded rust cloth in one
scene; three distinct lantern props; sleeves rolled to the
elbow in one scene).

The addendum arrived after generation: the script had not been
approved, so those images cannot be production assets. All ten
image files plus their sidecars were DELETED from the delivery
staging folder. Prompts, file hashes/sizes, and inspection
verdicts are preserved in the delivery folder's
`work/superseded-draft-keyframes.md` so the same images can be
regenerated exactly after approval (regeneration is a new
generation, not reuse). The six old keyframes map to new shots
s1, s2, s3b, s4, s5, s6b; shots s3a and s6a were never
generated. No visual asset was generated after the addendum
arrived. Voice WAVs were never generated in this round.

## §3. Provider audit and selection

Two research passes plus the coordinator's own direct
verification of the official fal.ai OpenAPI schema for the
endpoint (read 2026-11-28). Standing audit facts from the
consolidated 2026-11-27 audit still hold: Sora shut down
2026-09-24; Veo Gemini preview IDs shut down 2026-10-22 (live
route is Vertex AI `-001` IDs); LTX API v2 charges only on
success but its result-URL host is UNCONFIRMED; Kling legacy
/v1 is SECONDARY-verified only; OpenAI gpt-image-1 shut down
2026-10-23.

**Selected: fal.ai Kling Video v3 Pro (Image to Video),
endpoint `fal-ai/kling-video/v3/pro/image-to-video`,
provider id `provider-fal-video`.** Justification: I2V
confirmed with the exact official schema (required field
`start_image_url` only, ≤ 50 MB, ≥ 300×300 px, aspect
0.40–2.50; `prompt` ≤ 2500 chars; `duration` string enum
"3"–"15"; `generate_audio` native audio; `end_image_url`
optional; `negative_prompt` ≤ 2500; `cfg_scale` 0–1;
`enable_safety_checker`; no aspect-ratio/resolution field —
output follows the start image's aspect, so a 9:16 keyframe
yields a 9:16 clip at up to 1080p); queue lifecycle confirmed
(submit to `https://queue.fal.run/<endpoint>`, statuses
IN_QUEUE / IN_PROGRESS / COMPLETED, status/response/cancel
URLs, cancel PUT, outputs on `*.fal.media` ≥ 7 days, public by
default, 500+ never charged, 422 may be charged);
Commercial-use badge confirmed; pricing confirmed (1080p
$0.168/s with audio, $0.112/s without — fal.ai list prices,
read 2026-11-28); API-callable today (fal.ai-hosted Kling 4.0 API access is "coming
soon" — not usable via fal.ai; Kling 4.0 direct exists via Kling's own API, but its result-URL host is UNCONFIRMED, so it was not selected). Runner-up: fal.ai Veo 3.1 Fast (not
selected). The fal-video record is the only candidate with a
CONFIRMED output origin already in the URL policy — direct
LTX/Kling result-URL hosts are UNCONFIRMED, so downloads
would fail closed.

Registry: `architecture/COMPANION_CAPABILITY_REGISTRY.yaml`
gained the `provider-fal-video` record (operations
`[generate-video-from-image]`, commercial use approved with
the badge reason, charge behaviour with the documented rates,
conformance NOT_TESTED, evidence citing the OpenAPI schema
read 2026-11-28); registries regenerated (providers count is
now 14). `runtime/provider_contracts.py` gained
`FalVideoContract` (async, cancel PUT; validates model, prompt
≤ 2500, start-image URL required, duration string "3"–"15",
generate_audio, end_image_url, negative_prompt ≤ 2500,
cfg_scale 0–1, enable_safety_checker; refuses `elements` and
`multi_prompt`; result parses `video.url`, not `images`; 422
content-policy handling). `runtime/media_adapters.py` gained
the `provider-fal-video` spec (api_origins `queue.fal.run`,
output_origins `fal.media`, auth FAL_KEY/Key, charge
behaviour, aspect follows the start image, native audio) and
the `PROVIDER_SECRET_ENV` entry `provider-fal-video: FAL_KEY`.

## §4. I2V runtime (`runtime/image_to_video.py`)

Stdlib-only plus ffprobe/ffmpeg. What it does:

- **Source image validation** (`validate_source_image`):
  exists, ≤ 50 MB, SHA-256 match when given, ffprobe codec in
  png/mjpeg/webp, ≥ 300×300 px, aspect 0.40–2.50; returns
  path/sha256/bytes/codec/mime/width/height/reduced aspect.
  `keyframe_data_uri` builds the base64 data URI from a
  validated image only.
- **Authorization gate** (`validate_authorization` /
  `require_authorization`): the record must name who authorized
  it, the exact provider/model/operation, a generation budget
  covering the required generations, a scope containing every
  transmitted asset id, and a non-expired expiry. A missing
  record is refused — there is no implicit authorization.
  `execute_i2v_plan` refuses a BLOCKED plan with code
  `authorization-denied` before any submission.
- **Idempotency + uncertain-submission protection**
  (`idempotency_key`, `SubmissionLedger`): the key is the
  SHA-256 of the canonical JSON (project/shot/provider/model/
  keyframe SHA/prompt). A recorded key returns the existing job
  id without resubmitting. An uncertain key is never
  auto-resubmitted; a submission with no job id is recorded
  uncertain and refused.
- **Request building** (`build_i2v_request`): delegates to the
  provider contract with the motion prompt as the canonical
  instruction; the adapter rebuilds the same request from
  packet + context (the context carries `start_image_url`,
  `duration`, `generate_audio`), and execution refuses a
  translation that does not match the contract-built request.
- **Clip verification** (`verify_generated_clip`): MP4
  container, H.264 video stream present, duration within ±1.0 s
  of expected, expected geometry when given; native resolution
  recorded separately from any later upscale.
- **Motion validation** (`sample_frames`, `classify_motion`,
  `validate_clip_motion`): frames sampled via ffmpeg to 64×36
  grayscale PGM and parsed with the stdlib. Region diffs
  (centre/border/whole) plus a best-rigid-translation search
  classify each pair as static / camera-only / subject-motion /
  mixed; the overall verdict is the strongest pair verdict.
  Only subject-motion and mixed pass. Thresholds are detection
  thresholds on measured mean absolute pixel diffs, NOT quality
  scores. A slow zoompan over a smooth photographic still
  measures as static (sub-pixel per-frame change) and is
  rejected — verified empirically. **Known limitation:** a zoom
  over a high-frequency test pattern changes enough pixels to
  measure as mixed; pixel-diff classification alone cannot
  reliably distinguish every zoom from subject motion. The
  architectural guards carry that case: the local asset stage
  refuses `i2v-clip` outright (§5), execution accepts only
  provider clips, and human visual review is the final gate
  for every clip. The classifier is a backstop, not the sole
  guard, and this limitation is stated here rather than hidden.
- **Text-overlay prohibition**: all six flags
  (`text_overlay_enabled`, `subtitle_burn_in_enabled`,
  `keyword_overlay_enabled`, `subtext_overlay_enabled`,
  `title_card_enabled`, `watermark_enabled`) must be explicitly
  False; missing/True/non-boolean/unknown is an error. Every
  composed motion prompt ends with the prohibition clause ("No
  visible text, writing, signage, typography, subtitles,
  captions, watermarks, or logos."). Text detection is human
  review only — this module performs no OCR and never claims an
  automated text check (`record_human_text_review`,
  `validate_human_text_reviews`).
- **Motion prompts** (`validate_motion_prompt`,
  `build_i2v_motion_prompt`): seven fields — subject, face,
  body, hand/prop, hair/cloth, environment, camera — each
  non-empty; camera movement alone is never motion. Composed
  prompt ≤ 2500 chars.
- **Execution plan** (`build_execution_plan`, pure — never
  submits, never charges): READY only when the script is
  approved, every shot has a verified keyframe, every motion
  prompt is valid, and the authorization record covers the
  provider, model, operation, generation count and every
  transmitted asset. Otherwise BLOCKED with the exact reasons,
  including the estimated cost from the documented rates.
- **Execution** (`execute_i2v_plan`, READY plans only):
  validate image → data URI → build request → submit via
  ledger → poll → verify clip → motion-validate → register via
  `production_assets.register_asset`. A failed or
  motion-rejected clip stops the run — no partial final video
  is ever assembled from a failed clip.

## §5. Extensions: `i2v-clip` kind and I2V scene binding

- `runtime/vertical_production.py`: `VISUAL_RECIPE_KINDS`
  gained `"i2v-clip"`. The kind is a recipe the asset stage
  can NEVER generate locally.
- `runtime/production_assets.py`: `visual_argv` refuses
  `i2v-clip` explicitly — an I2V clip must come from an
  authorized provider image-to-video execution; FFmpeg stays
  for conversion/assembly only, never as the I2V substitute.
- `runtime/character_consistency.py`:
  `validate_scene_binding` gained a `motion_kind="i2v"`
  parameter. With it, the shot's motion prompt must pass the
  canonical I2V validator (lazy import, no import cycle), its
  visual kind must be `"i2v-clip"`, and it must not carry a
  still motion. Default `motion_kind="still"` behaviour is
  unchanged.

## §6. Adapter fix found by this round (P1-005 gap)

`HttpProviderAdapter.submit` parsed the queue URLs
(`status_url`, `response_url`, `cancel_url`) from the submit
response and then dropped them from its return — so no caller
could ever poll a fal queue job (fal.ai has no poll template;
its status URL comes from the submit response, as the existing
adapter test already states). The async submit return now
carries all three URLs (None when the contract did not return
them). Additive only: no existing assertion constrains the
return keys. `execute_i2v_plan` carries them into the poll
context. Verified by the R2 suite through the real fal-video
adapter over a mock transport (submit → poll → retrieve).

## §7. Character and script (draft, awaiting approval)

- **Character: Nadia, DEMO-CHAR-002** — fictional, project-local
  adult, age 27 (range 25–30), photorealistic-digital-human.
  Signature colour rust orange (defined once). One outfit:
  rust-orange linen shirt, dark indigo jeans, brown leather
  sandals; brass bangle canon LEFT wrist, gold hoop earrings;
  long straight black hair, centre part; warm medium-brown
  skin, natural texture; dark brown eyes, natural size. Three
  distinct lantern props (round table, rectangular floating,
  cylindrical sky) — NOT one continuous prop. Not Mara, not
  Sarena, not any real person; never registered.
- **Script: "Nadia and the River Light"** — narrator-only,
  en-US, 8 lines, one per shot; no character speaks on screen,
  so no lip-sync is claimed; no text on screen. Status: DRAFT —
  awaiting user approval. Full text and breakdown in
  `examples/p1006-r2-photorealistic-image-to-video/script.md`
  and `script-breakdown.md`.
- **Script-derived counts:** 6 scenes (SC1 rooftop dawn; SC2
  river steps; SC3 river's edge golden hour — 2 shots; SC4
  market morning; SC5 market rain; SC6 rooftop dusk — 2
  shots); 8 shots (s1, s2, s3a, s3b, s4, s5, s6a, s6b); 8
  keyframes; 8 I2V clips; 8 narration lines (1:1 dialogue
  coverage); 4 reference images + 1 expression sheet (all
  pending); 3 locations; 6 environment states; 5 important
  objects. Per-shot duration 6 s; total video runtime 48 s
  (inside 30–60 s). Planned narration ~39.3 s + pauses +
  lead-in/tail-out ≈ 45.3 s audio timeline; the final schedule
  is computed from MEASURED narration durations at assembly
  time. Why 8 shots, not 6: SC3 needs two shots (hands setting
  the lantern afloat + face watching it drift — the camera
  cannot be on hands and face at once); SC6 needs two shots
  (lifting + release/rising — two different movements). No
  scene was cut to save clips; no shot was invented to inflate
  the count.
- The bible's reference inventory now carries all five views
  (front, three-quarter, side, full-body, expressions) with
  `file: null` and status
  `pending-generation-after-script-approval`. The R2 driver
  treats the missing reference files as an expected BLOCKED
  condition (recorded, not fatal); every other bible error
  still stops the run. The bible validator itself is unchanged.

## §8. Reference project and driver

`examples/p1006-r2-photorealistic-image-to-video/` (source
files only, no media): `script.md`, `script-breakdown.md`,
`voice-config.json` (8 lines, seed 42, instruct
`middle-aged, moderate pitch`, en-US, non-commercial-only),
`shot-list.json` (8 shots; structured motion prompt per shot;
keyframe `{file: null, sha256: null, status:
"pending-generation-after-script-approval"}`; visual
`{kind: "i2v-clip", duration_seconds: 6}`; provider
generation all BLOCKED), `project.json` (qc_status BLOCKED,
reason "script approval pending; no authorized real I2V
execution yet"; script_status DRAFT; text overlay policy all
six False), `production-analysis.json`,
`sound-plan.json`, `assembly-config.json` (FFmpeg only; 8×6 s
= 48 s; video-led schedule; no still-zoompan fallback),
`README.md`, `character-bible.json`.

`scripts/run-p1006-r2-photorealistic-render.py` validates the
script (verbatim vs voice config), dialogue coverage, text
policy, bible (design + isolation + I2V bindings), and the
project; synthesizes deterministic tone narration for the
pipeline check only (`voice_source: synthesized-tone`, same
pattern as the R1 CI render); builds the execution plan; then
FAILS CLOSED — the plan is BLOCKED, no provider call is made,
no still animation is substituted, no final MP4 is produced,
and the run exits 2 with `render-summary.json` recording
BLOCKED, the exact reasons, the derived counts, and
`final_mp4: null`. The shot-id pattern accepts s3a/s3b/s6a/s6b
(a fixed `s[0-9]` pattern would silently drop them). The
driver also writes the pending keyframes manifest
(`work/keyframes/scene-keyframes.json`, 8 entries, status
pending).

## §9. Voice

Real VoiceStudio/OmniVoice narration is NOT generated in this
round (script unapproved). The generation script
(`work/voice/generate-r2-voice.py`, adapted from R1's
`generate-r1-voice.py`: VoiceStudioAdapter +
`production_voice.generate_voice_line`, seed 42, backend
started only for generation then stopped) refuses to run while
the project script status starts with "DRAFT" — the refusal
was verified. The R1 audio-mix fix (explicit `asplit=2` in
`runtime/production_audio.py::_mix_argv`) is untouched and
preserved.

## §10. Tests

New suite `tests/test_p1006_r2_image_to_video.py`, registered
in `tests/run-tests.sh` as `CF-P1-006-R2-I2V` (90 checks, all
passing locally). Coverage: request building, image input
integrity, reference-transmission authorization, invalid image
rejection, submission, polling, retrieval, malicious
result-URL rejection, failed generation, duplicate submission
prevention, download integrity, invalid video rejection, wrong
duration, wrong geometry, missing video stream, wrong codec,
static repeated-frame rejection, camera-only movement
rejection (including the slow-zoompan-over-a-smooth-still
case), character drift detection, text-overlay prohibition,
subtitle/caption prohibition, script-derived counts,
dialogue coverage, execution plan (BLOCKED and READY),
mock-adapter execution (completes + registers; motion-failed
clip stops the run), local-generation refusal, I2V scene
binding, human text review, and the end-to-end BLOCKED path
through the R2 driver (exit 2, summary BLOCKED, no MP4). The
fal.ai adapter is exercised over an injected mock transport
only; the mock execution adapter is labelled mock in every
check name that uses it. No test calls a paid provider.

Test-found defects fixed in this round: (1) the adapter
dropped the fal queue URLs from the submit return (§6);
(2) `execute_i2v_plan` did not pass the I2V inputs
(`start_image_url`, `duration`, `generate_audio`) in the
adapter context, so the real adapter could not rebuild the
contract request; (3) the packet used task type
`generate-video-from-image`, which no adapter serves — the
adapter-served type is `video-generation` (the operation
stays on the plan/authorization); (4) `_read_pgm` read four
header tokens where PGM has three, corrupting frame parsing;
(5) the R2 bible lacked the `references.expressions` view the
validator requires (§7).

## §11. Authorization request

`docs/implementation/CF-WO-P1-006-R2-authorization-request.md`
(+ delivery copy): provider fal.ai, model Kling Video v3 Pro
image-to-video, operation image-to-video, **8 generations**,
6 s per clip, 1080p, native audio, estimated **$8.06**
(48 s × $0.168/s with audio; $5.38 without audio), input
reference images transmitted, data-retention and privacy
implications, commercial-use restrictions. This is the gate
document the user must explicitly approve before any paid
request runs. No paid call was made in this round.

## §12. What is still blocked / open limitations

- The script is a DRAFT awaiting user approval; no reference
  image, keyframe, or voice recording has been generated from
  it; no real I2V execution exists; I2V capability is BLOCKED
  pending the user's explicit authorization of the paid
  provider call (and script approval). No final MP4 was
  delivered in this round — there is none, and claiming one
  would be fabrication.
- No video provider is VERIFIED/EXERCISED by a live call; all
  external providers remain conformance NOT_TESTED. The fal
  adapter path is exercised over a mock transport only.
- Motion classification limitation, stated in §4: pixel-diff
  classification cannot reliably distinguish every zoom from
  subject motion; the architectural guards (local refusal,
  provider-only execution, human review) carry that case.
- A failed fal job reports COMPLETED at the status endpoint
  with the error in the result payload (the contract handles
  this); a literal `FAILED` status value is not part of the
  documented API and the contract refuses it as malformed.
- The R1 audio defect disclosure stands (P1-006 MP4 narration
  audible only for line 1); a re-render has not been decided.
  The R1 fix is preserved, not re-applied.
