# Authorization request — CF-WO-P1-006-R2 image-to-video execution

**This is a written request for approval, NOT an executed call.
No paid request has been made. No paid request will be made
until the user explicitly approves this document (and the
script + breakdown it depends on).**

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
  this endpoint, read 2026-11-28; queue lifecycle, pricing, and
  Commercial-use badge confirmed from fal.ai's own pages. Full
  audit record:
  `docs/implementation/CF-WO-P1-006-R2-corrections.md` §3.

## Exact scope of the requested generations

| Item | Value |
| --- | --- |
| Number of I2V generations | **8** (one per shot: s1, s2, s3a, s3b, s4, s5, s6a, s6b) |
| Duration per clip | **6 seconds** |
| Total video runtime | **48 seconds** |
| Resolution | **1080×1920 (9:16)**, up to 1080p as the provider returns it |
| Frame rate | 30 fps (final assembly) |
| Native audio | **Yes** (provider native audio generation) |
| Start image per clip | The shot's verified photorealistic keyframe (generated after script approval, chained from the approved front reference) |
| End image | Not used |
| Motion instruction per clip | The shot's structured motion prompt (subject / face / body / hand-prop / hair-cloth / environment / camera) plus the text-prohibition clause |
| On-screen text | **None** — all six text-overlay flags are False; prompts prohibit visible text |

The count (8) is script-derived, not fixed: the complete
script and its scene/shot breakdown determine it (6 scenes, 8
shots, 8 keyframes, 8 clips, 8 narration lines). No story
event was omitted to reduce clips; no shot was invented to
inflate the count. If the user changes the script, the count
and the cost change with it, and this request must be
re-approved.

## Estimated cost

- Rate: **$0.168 per second with audio, 1080p** (fal.ai list
  prices, read 2026-11-28:
  https://fal.ai/learn/devs/kling-4-0-vs-kling-3-0)
- Calculation: 8 clips × 6 s × $0.168/s = **$8.06**
- Without audio the same 48 s would be 48 × $0.112 = $5.38;
  audio is requested, so the $8.06 figure applies.
- Charging rules (provider-documented): server errors (HTTP
  500+) are never charged; queue-wait time is never charged; a
  422 may be charged if GPU time was spent. A failed
  generation after GPU time may therefore cost up to its clip
  price ($1.01 per 6 s clip) even when it produces no usable
  video.
- Payment: from the user's prepaid fal.ai credits, charged by
  the provider at generation time. No credential is stored in
  this repo; the call uses the allow-listed `FAL_KEY`
  environment variable only, supplied at run time.

## Input reference images being transmitted

Each generation transmits exactly one image: the shot's
verified keyframe, as a base64 data URI (`start_image_url`).
The keyframes are generated after script approval from the
approved front reference of a fictional adult character
(Nadia, DEMO-CHAR-002); no real person's face, no canonical
user character, and no registered character reference is
transmitted. No other reference image is transmitted: the
provider's `elements` mechanism (extra reference images) is
refused by the contract and is NOT part of this request. The
motion prompt text for each shot is also transmitted (it is
the generation instruction).

## Data retention and privacy implications

- The transmitted keyframe and prompt are sent to fal.ai's
  queue API (`queue.fal.run`) over HTTPS, authenticated with
  the `FAL_KEY` key.
- Generated videos are returned as URLs on the fal.media CDN
  and are kept at least 7 days; fal.ai queue outputs are public
  by default (anyone with the URL can fetch them during that
  window).
- The keyframes depict a fictional adult digital human, not a
  real person and not a private individual; no personal data,
  voice sample, or private character data is transmitted in
  this request. Voice narration for this production is
  generated separately and locally (VoiceStudio/OmniVoice,
  non-commercial) and is NOT part of this paid request.
- The provider job ids, output URLs, and SHA-256 hashes of the
  returned clips are recorded in the production evidence (the
  delivery folder and the repo's provider-generation
  provenance fields). The returned clips are downloaded,
  verified, and stored in the delivery folder only — never
  committed to the public repo.

## Commercial-use restrictions

- The provider carries a Commercial-use badge for this model
  (confirmed on fal.ai's model page). The generated clips may
  be used commercially under fal.ai's terms.
- The narration voice is a separate matter: the
  VoiceStudio/OmniVoice test voice is CC-BY-NC
  (non-commercial). A production that pairs these clips with
  that voice stays a non-commercial demonstration unless a
  commercially cleared voice is substituted. The clips
  themselves carry no such restriction from the video provider.

## What happens after approval

1. The user approves the script + breakdown (separate gate).
2. The user approves this request (this gate).
3. Reference images and keyframes are generated from the
   approved front reference and verified against the bible.
4. Real narration WAVs are generated locally
   (VoiceStudio/OmniVoice, seed 42, non-commercial).
5. The 8 authorized I2V generations run through
   `runtime/image_to_video.py::execute_i2v_plan` under the
   authorization record recorded from this approval (exact
   provider, model, operation, 8 generations, scope = the
   transmitted asset ids). Each clip is verified (MP4, H.264,
   6 s ± 1.0 s, 1080×1920) and motion-validated; a failed or
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
  keyframes (no `elements`, no extra references).
- Any use of the `FAL_KEY` credential beyond this run, and no
  storage of the credential in the repo, reports, or packets.
- A merge of PR #5, any push, or any change to the script
  after approval without a new approval.

## Decision

- [ ] APPROVED — run the 8 generations as specified above
  (estimated $8.06).
- [ ] APPROVED WITHOUT AUDIO — run the 8 generations with
  native audio off (estimated $5.38).
- [ ] NOT APPROVED — do not run any paid generation.
