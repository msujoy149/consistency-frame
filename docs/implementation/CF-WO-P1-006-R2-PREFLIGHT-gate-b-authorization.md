# GATE B — Paid Provider Generation Authorization

Work order CF-WO-P1-006-R2-PREFLIGHT, branch
`feat/cf-p1-004-universal-production-brain`, PR #5 (open, Draft,
unmerged). Production: "Nadia and the River Light"
(p1006-r2-photorealistic-image-to-video).

**This is a written request for approval, NOT an executed call.
No paid request has been made. No paid request will be made
until the owner explicitly approves this sheet AND Gate A (the
story and visual plan) has passed. Gate A passing does NOT
authorize this sheet, and this sheet passing does NOT approve
the script — both gates are required, and neither may be
inferred from the other.**

This sheet SUPERSEDES
`docs/implementation/CF-WO-P1-006-R2-authorization-request.md`
(the R2 authorization request: 8 generations, 6 s each, 1080p,
native audio ON, estimated $8.06). The R2 request is kept in
full below a SUPERSEDED note; its history is not overwritten.
Reason for superseding: audio on -> audio off (external
narration is handled separately by the existing voice pipeline;
the provider must not generate unintended audio), and the
8-clip / $8.06 estimate is replaced by the dynamic storyboard
cost plan below. Date: 2026-11-28.

## What is being asked

Approval to run real image-to-video generations with a paid
provider for the P1-006-R2 demonstration production "Nadia and
the River Light" (fictional adult character Nadia,
DEMO-CHAR-002, project-local, never registered).

## Provider and model

- **Provider:** fal.ai (fal Model APIs, queue)
- **Provider id (repo):** `provider-fal-video`
- **Model:** Kling Video v3 Pro (Image to Video)
- **Model id:** `fal-ai/kling-video/v3/pro/image-to-video`
- **Endpoint:** `POST https://queue.fal.run/fal-ai/kling-video/v3/pro/image-to-video`
- **Operation:** image-to-video (`generate-video-from-image`)
- **Selection evidence:** official fal.ai OpenAPI schema for
  this endpoint, read 2026-11-28; queue lifecycle and
  Commercial-use badge confirmed from fal.ai's own pages;
  pricing re-verified live 2026-11-28 from the fal.ai learn
  pages
  https://fal.ai/learn/tools/kling-3-0-pro-vs-sora-2-pro
  and
  https://fal.ai/learn/tools/seedance-2-0-vs-kling-3-0
  (with-elements tier: $0.224/s audio off, $0.336/s audio
  on; without-elements base: $0.112/s audio off, $0.168/s
  audio on). The official API schema page
  (https://fal.ai/models/fal-ai/kling-video/v3/pro/image-to-video/api)
  lists no pricing. Full audit
  record:
  `docs/implementation/CF-WO-P1-006-R2-corrections.md` §3.

## Exact scope of the requested generations

| Item | Value |
| --- | --- |
| Number of I2V generations | **8** (one per shot: s1, s2, s3a, s3b, s4, s5, s6a, s6b) |
| Duration per clip | **6 seconds** (provider enum "6", range "3"–"15") |
| Total video runtime | **48 seconds** |
| Resolution | **1080x1920 (9:16)**, up to 1080p as the provider returns it |
| Frame rate | 30 fps (final assembly) |
| Native audio | **No — `generate_audio: false` for every shot** (external narration handled separately by the existing voice pipeline) |
| Start image per clip | The shot's verified photorealistic keyframe (generated after script approval, chained from the approved front reference), as a base64 data URI |
| Character element references | Frontal @Element1 (`ref-nadia-front`) + 1 angle reference per shot (`reference_image_urls`), as URLs once generated. Element conditioning IS wired into the provider contract (`runtime/provider_contracts.py::FalVideoContract`, `validate_fal_video_elements`) and the I2V runtime (`runtime/image_to_video.py::build_shot_elements`); a shot whose element references are missing or pending BLOCKS the plan. Every shot in this production carries an element, so every shot is priced at the with-elements tier ($0.224/s, audio off). |
| End image | Not used |
| Motion instruction per clip | The shot's structured motion prompt (subject / face / body / hand-prop / hair-cloth / environment / camera) plus the text-prohibition clause |
| On-screen text | **None** — all six text-overlay flags are False; prompts prohibit visible text |

The count (8) is script-derived, not fixed: the complete script
and its scene/shot breakdown determine it (6 scenes, 8 shots, 8
keyframes, 8 clips, 8 narration lines). No story event was
omitted to reduce clips; no shot was invented to inflate the
count. The preflight line-by-line analysis confirmed the counts
unchanged vs the R2 draft (see
`examples/p1006-r2-photorealistic-image-to-video/story-coverage-report.json`).
If the owner changes the script, the count and the cost change
with it, and this sheet must be re-approved.

## Expected cost

- Rate: **$0.224 per second, audio OFF, WITH elements,
  1080p** (fal.ai list prices, re-verified live 2026-11-28
  from
  https://fal.ai/learn/tools/kling-3-0-pro-vs-sora-2-pro
  and
  https://fal.ai/learn/tools/seedance-2-0-vs-kling-3-0).
  Every shot carries the Nadia character element
  (@Element1), so the with-elements tier applies to all 8
  shots. The base $0.112/s rate applies ONLY WITHOUT
  elements.
- Per-shot cost: 6 s x $0.224/s = **$1.344**
- Calculation: 8 clips x 6 s x $0.224/s = **$10.752, rounded $10.75**
- Rate table (Kling 3.0 Pro, per second, 1080p): without
  elements — $0.112 audio off, $0.168 audio on, $0.196
  voice control; with elements — $0.224 audio off,
  $0.336 audio on, $0.392 voice control. With elements
  and audio ON the same 48 s would be 48 x $0.336 =
  $16.128 (rounded $16.13); without elements and audio ON
  it would be 48 x $0.168 = $8.064 (rounded $8.06) — the
  R2 figure. Audio is OFF and elements are ON in this
  round, so the $10.75 figure applies.
- Keyframe generation cost: **$0 billed** — keyframes (8) and
  character references (5 views) are generated with the platform
  built-in image generation, which is not a billed provider
  charge in this environment. Recorded as $0 billed /
  not-applicable rather than an invented number.
- Retry budget: **one retry per failed shot** at that shot's own
  cost ($1.344); maximum retry budget **$10.75** (exact
  $10.752); worst-case total
  (generation + full retry budget) **$21.50** (exact
  $21.504). No second retry is
  budgeted without a new approval.
- Charging rules (provider-documented): server errors (HTTP 500+)
  are never charged; queue-wait time is never charged; a 422 may
  be charged if GPU time was spent. A failed generation after GPU
  time may therefore cost up to its clip price ($1.344 per 6 s
  clip) even when it produces no usable video.
- Taxes / fees: **UNCONFIRMED** — no tax or fee is stated on the
  pricing page read.
- Upload / storage charges: none stated for this endpoint;
  UNCONFIRMED as a separate line item.
- Payment: from the owner's prepaid fal.ai credits, charged by
  the provider at generation time. No credential is stored in
  this repo; the call uses the allow-listed key environment
  variable only, supplied at run time.
- This is an estimate, not a guaranteed final bill. Full cost
  sheet:
  `examples/p1006-r2-photorealistic-image-to-video/cost-plan.json`
  and `cost-plan.md`.

## Input reference images being transmitted

Each generation transmits its shot's verified keyframe as a
base64 data URI (`start_image_url`), plus the character
element references as URLs (frontal + 1 angle reference per
shot). The keyframes are
generated after script approval from the approved front
reference of a fictional adult character (Nadia, DEMO-CHAR-002);
no real person's face, no canonical user character, and no
registered character reference is transmitted. The motion prompt
text for each shot is also transmitted (it is the generation
instruction). Voice narration is generated separately and
locally and is NOT part of this paid request.

## Data transmission, retention, and access-control limitations

- The transmitted keyframe and prompt are sent to fal.ai's queue
  API (`queue.fal.run`) over HTTPS, authenticated with the
  allow-listed key. Inputs are sent as base64 data URIs in the
  request body — not uploaded to the CDN first.
- Every request carries `X-Fal-Store-IO: 0`, which disables
  request-history payload storage. Scope limit: it does NOT
  equal zero data retention and does NOT disable application
  logging. Request payloads are otherwise retained 90 days by
  default.
- **Generated clips are public-by-link on Google Cloud Storage.**
  For this endpoint the model page's own output example is
  `https://storage.googleapis.com/falserverless/...` — NOT the
  fal CDN. The fal CDN access control and lifecycle
  (`X-Fal-Object-Lifecycle-Preference`, expiration 7 days,
  `initial_acl`) apply ONLY to fal CDN v3 URLs
  (`https://v3b.fal.media/...`) and do NOT protect a GCS output
  URL. A GCS output cannot be restricted by any fal ACL setting.
  Anyone with a clip URL can fetch it. No GCS retention period
  for these outputs was confirmed: UNCONFIRMED.
- **Provider logs may retain content:** application logging is
  not disabled by the headers above.
- **Zero data retention (ZDR): UNCONFIRMED** — not enabled by
  default, requires sales-team confirmation, is NOT a single
  setting, and does NOT disable application logging.
- Full assessment:
  `docs/implementation/CF-WO-P1-006-R2-PREFLIGHT-retention-assessment.md`.
  The retention assessment marks the generation operation
  BLOCKED on privacy grounds until the owner accepts the
  public-by-link limitation in writing here.

## Commercial-use status

- The provider carries a Commercial-use badge for this model
  (confirmed on fal.ai's model page). The generated clips may
  be used commercially under fal.ai's terms.
- The narration voice is a separate matter: the
  VoiceStudio/OmniVoice test voice is CC-BY-NC
  (non-commercial). A production that pairs these clips with
  that voice stays a non-commercial demonstration unless a
  commercially cleared voice is substituted. The clips
  themselves carry no such restriction from the video provider.

## Expected outputs

- 8 verified I2V clips (MP4, H.264, 6 s +/- 1.0 s, 1080x1920),
  each motion-validated (real subject motion, not static and not
  camera-only) and human-reviewed for text. A failed or
  motion-rejected clip stops the run — no partial final video is
  ever assembled from a failed clip.
- The clips are assembled (FFmpeg only), QC'd, and delivered as
  a review package (BLOCKED pending a named human reviewer's
  editorial approval).
- The provider job ids, output URLs, and SHA-256 hashes of the
  returned clips are recorded in the production evidence (the
  delivery folder and the repo's provider-generation provenance
  fields). The returned clips are downloaded, verified, and
  stored in the delivery folder only — never committed to the
  public repo.

## What happens after approval

1. The owner approves the script + breakdown (Gate A).
2. The owner approves this sheet (Gate B), including explicit
   acceptance of public-by-link GCS outputs (see the decision
   box below).
3. Reference images and keyframes are generated from the
   approved front reference and verified against the bible.
4. Real narration WAVs are generated locally
   (VoiceStudio/OmniVoice, seed 42, non-commercial).
5. The 8 authorized I2V generations run through
   `runtime/image_to_video.py::execute_i2v_plan` under the
   authorization record recorded from this approval (exact
   provider, model, operation, 8 generations, audio off, scope =
   the transmitted asset ids). Each clip is verified (MP4, H.264,
   6 s +/- 1.0 s, 1080x1920) and motion-validated; a failed or
   motion-rejected clip stops the run.
6. The clips are assembled (FFmpeg only), QC'd, and delivered
   as a review package (BLOCKED pending a named human reviewer's
   editorial approval).

If any step fails, the run stops with diagnostics — no still
animation is substituted, and no fake final video is produced.

## What approval does NOT authorize

- More than 8 generations, or any generation for a different
  model, provider, or operation.
- Transmission of any reference image beyond the 8 shot
  keyframes and the per-shot element references named above.
- Any use of the provider key credential beyond this run, and no
  storage of the credential in the repo, reports, or packets.
- A merge of PR #5, any push, or any change to the script
  after approval without a new approval.

## Decision

- [ ] APPROVED — run the 8 generations as specified above
  (estimated $10.75, audio OFF, with elements), AND I accept that the generated
  clips will be public-by-link on Google Cloud Storage and
  cannot be restricted by the fal CDN access control.
- [ ] NOT APPROVED — do not run any paid generation.
