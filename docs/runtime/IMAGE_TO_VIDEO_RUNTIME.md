# Image-to-video runtime (CF-WO-P1-006-R2)

The image-to-video runtime (`runtime/image_to_video.py`) is the
tenth P1 runtime component. It turns a verified photorealistic
keyframe into a genuine video clip through a real provider
image-to-video execution — and it refuses to do anything else.
It sits on the P1-005 execution runtime
(`docs/runtime/PROVIDER_ADAPTERS.md`): the provider contract
builds the request, the HTTP adapter submits / polls /
retrieves, and this runtime adds the authorization gate, the
idempotency ledger, clip verification, and motion validation.
The R2 driver
(`scripts/run-p1006-r2-photorealistic-render.py`) runs the
validation and planning stages and fails closed while no
authorized execution exists.

## What it is for

One verified keyframe, one provider generation, one verified
clip — per shot, with the counts derived from the script. The
runtime answers five questions:

1. Is the source image the verified keyframe, byte for byte?
2. Is there an explicit authorization record covering this
   provider, model, operation, generation count, and every
   transmitted asset?
3. Did the provider accept exactly one submission for this
   shot (never a duplicate, never an auto-resend of an
   uncertain one)?
4. Is the returned clip the right container, codec, duration,
   and geometry — and does it actually move?
5. Is there any on-screen text in the plan or the clip?

It never answers a sixth question — "is this good enough to
ship?" — that is the named human reviewer's decision, and the
delivery manifest stays BLOCKED until one is supplied.

## The selected provider

fal.ai Kling Video v3 Pro (Image to Video), endpoint
`fal-ai/kling-video/v3/pro/image-to-video`, provider id
`provider-fal-video`. The contract
(`runtime/provider_contracts.py::FalVideoContract`) is the
authority for the request shape: `start_image_url` is the only
required field (public URL or base64 data URI, ≤ 50 MB,
≥ 300×300 px, aspect 0.40–2.50); `prompt` ≤ 2500 chars;
`duration` is a string enum "3"–"15"; `generate_audio`
defaults true (native audio); `end_image_url` optional;
`negative_prompt` ≤ 2500; `cfg_scale` 0–1;
`enable_safety_checker` defaults true. There is NO
aspect-ratio or resolution field: the output follows the start
image's aspect (a 9:16 keyframe yields a 9:16 clip) at up to
1080p. The `elements` mechanism is refused by the contract —
it would transmit extra reference images and bind voices, and
no production has authorized it.

The queue lifecycle: submit POST to
`https://queue.fal.run/<endpoint>`; the submit response carries
`request_id`, `status_url`, `response_url`, `cancel_url`; the
status endpoint returns IN_QUEUE / IN_PROGRESS / COMPLETED; a
completed job's result is a second GET on `response_url`
(`video: {url, content_type, file_size, file_name}`); cancel is
PUT on `cancel_url`. Output URLs live on `*.fal.media` for at
least 7 days. Server errors (HTTP 500+) are never charged; a
422 may be charged if GPU time was spent. A failed job reports
COMPLETED at the status endpoint with the error in the result
payload — a literal `FAILED` status value is not part of the
documented API and the contract refuses it as malformed.

Pricing (fal.ai list prices, read 2026-11-28): Kling 3.0 Pro
1080p $0.168/s with audio, $0.112/s without. The R2 plan (8
clips × 6 s, with audio) estimates $8.06.

## Source image validation

`validate_source_image(path, expected_sha256=None)`:

- The file must exist and be ≤ 50 MB (the provider limit).
- When an expected SHA-256 is given, the file's hash must match
  it exactly.
- ffprobe must report a codec of png, mjpeg, or webp; the image
  must be ≥ 300×300 px; the aspect must be within 0.40–2.50.

`keyframe_data_uri(validated)` builds the base64 data URI from
a validated image only — an unvalidated image never becomes a
transmitted URL.

## The authorization gate

`validate_authorization(authorization, provider_id, model,
operation, required_generations, scope_asset_ids)` returns the
list of errors (empty = authorized). The record must:

- name who authorized it (`authorized_by`, non-empty string);
- name the exact provider, model, and operation;
- carry a generation budget (`max_generations`, an integer, not
  a boolean) covering the required generations;
- carry a `scope` list containing every asset id that will be
  transmitted (reference ids and keyframe asset ids);
- not be expired (`expires_at`, when present, must be in the
  future).

A missing record is refused — there is no implicit
authorization. `require_authorization` raises
`ImageToVideoError` (code `authorization-denied`) on any error.
`execute_i2v_plan` refuses a BLOCKED plan with the same code
before any submission, and the R2 driver never holds an
authorization record at all.

## Idempotency and uncertain submissions

`idempotency_key(project_id, shot_id, provider_id, model,
keyframe_sha256, prompt)` is the SHA-256 of the canonical JSON
of those six fields — the same shot always produces the same
key, a different keyframe or prompt a different one.

`SubmissionLedger` (in-memory, with an optional JSON store
written atomically) records one entry per key: `submitted` /
`running` / `done` with the provider job id, or `uncertain`
with a detail. `submit_i2v_generation` reuses a recorded job
id without calling the adapter again; it refuses an uncertain
key outright; and a submission that returns no job id (or
raises `submission-uncertain`) is recorded uncertain and the
error propagates. An uncertain submission is NEVER
auto-resubmitted — a human resolves it against the provider
first.

## Request building and submission

`build_i2v_request(provider_id, model, prompt,
start_image_url, duration_seconds=6, generate_audio=True, ...)`
delegates to the provider contract. Preparation only: no
submission, no charge.

`submit_i2v_generation(adapter, request, context, ledger, key)`
submits through the adapter and returns the job id (with
`reused: True` when the ledger already held it).
`poll_i2v_generation(adapter, job_id, context, max_polls=60,
poll_interval_s=5)` polls to completion or failure; running
out of polls raises `poll-timeout` and never claims completion.

The adapter builds its own request from packet + context
through the same contract, so the execution context must carry
the I2V inputs (`start_image_url`, `duration`,
`generate_audio`) — otherwise the adapter cannot rebuild the
contract-built request, and execution refuses a translation
that does not match. The adapter-served task type is
`video-generation`; the operation `generate-video-from-image`
is the authorized operation recorded on the plan and the
authorization record, not the adapter task type. The poll
context must carry the queue URLs from the submit response
(`status_url`, `response_url`, `cancel_url`) — fal.ai has no
poll template, and the adapter's async submit return carries
them for exactly that reason.

## Clip verification

`verify_generated_clip(path, expected_duration_seconds,
expected_width=None, expected_height=None,
duration_tolerance_s=1.0)`:

- The file must exist and probe as an MP4 container.
- It must have a video stream, and the codec must be H.264.
- The measured duration must be within tolerance of the
  requested duration.
- When an expected geometry is given, width and height must
  match exactly.

The returned record carries the SHA-256, byte size, format,
codecs, native width/height, duration, and frame rate. The
native resolution is always recorded separately from any later
upscale: a clip that needed resizing is reported with its
native geometry here.

## Motion validation

`validate_clip_motion(video_path, num_frames=8, work_dir)`
samples evenly spaced frames via ffmpeg to 64×36 grayscale
PGM (parsed with the stdlib — no image library) and classifies
them with `classify_motion`.

Each consecutive pair is classified from measured mean absolute
pixel diffs (centre region = middle 50%, border = the rest)
plus a best-rigid-translation search (±4 px):

- **static** — whole-frame diff below the still threshold
  (1.0): the frames are effectively unchanged.
- **camera-only** — the pair differs only by a rigid
  translation whose residual is below the still threshold (a
  pan over a still), or movement lives at the edges while the
  centre subject region is unchanged (a zoom over a still).
- **subject-motion** — the centre subject region changes while
  the background stays still.
- **mixed** — both subject region and background change.

The overall classification is the strongest pair verdict
present (subject-motion beats mixed beats camera-only beats
static). `passes` is True only for subject-motion and mixed.
Thresholds are detection thresholds on measured diffs, NOT
quality scores — no numeric motion score is ever invented or
reported as a grade.

Verified behaviour: identical frames → static (rejected); a
rigidly shifted pair → camera-only (rejected); a centre-only
change → subject-motion (passes); a whole-frame change →
mixed (passes); a slow zoompan over a smooth photographic
still → static (rejected — the per-frame change is
sub-pixel). **Known limitation:** a zoom over a
high-frequency test pattern changes enough pixels to measure
as mixed; pixel-diff classification alone cannot reliably
distinguish every zoom from subject motion. The architectural
guards carry that case: the local asset stage refuses
`i2v-clip` outright, execution accepts only provider clips,
and human visual review is the final gate. The classifier is a
backstop, not the sole guard.

## Text-overlay prohibition

`TEXT_OVERLAY_POLICY` is all six flags False:
`text_overlay_enabled`, `subtitle_burn_in_enabled`,
`keyword_overlay_enabled`, `subtext_overlay_enabled`,
`title_card_enabled`, `watermark_enabled`.
`validate_text_overlay_policy` requires every flag present,
boolean, and False; a missing, True, non-boolean, or unknown
flag is an error naming the flag.

Every composed motion prompt ends with the prohibition clause:
"No visible text, writing, signage, typography, subtitles,
captions, watermarks, or logos."

Text detection is human review only:
`record_human_text_review(clip_path, reviewer, text_found,
notes)` records one reviewer's verdict (method recorded as
"human-visual-review (no OCR)"), and
`validate_human_text_reviews(reviews, clip_paths)` requires a
review for every clip and fails any clip where text was found.
This module performs no OCR and never claims an automated text
check.

## Motion prompts

`validate_motion_prompt(motion)` requires a dict with seven
non-empty fields, in order: `subject`, `face`, `body`,
`hand_prop`, `hair_cloth`, `environment`, `camera`. Camera
movement alone is never motion — every other field must also
be specified. `build_i2v_motion_prompt(motion)` joins the
fields with "; ", appends the text-prohibition clause, and
refuses a result over 2500 characters (the provider limit).

## Script-derived counts

`derive_project_counts(project, shots, voice_lines)` computes
every count from the inputs — scenes (distinct `scene_id`
values), shots, keyframes (= shots), clips (= shots), lines,
per-shot clip duration, and total video runtime (the sum of
the per-shot clip durations). No count is fixed in advance;
the R2 counts (6 scenes, 8 shots, 8 keyframes, 8 clips, 8
lines, 48 s) are what the script analysis produces, not what
any constant declares.

## Execution plan

`build_execution_plan(project, shots, authorization=None,
duration_seconds=6, generate_audio=True)` is pure: it never
submits and never charges. The plan is READY only when the
script is approved, every shot has a verified keyframe, every
motion prompt is valid, the text policy is valid, and the
authorization record covers the provider, model, operation,
generation count, and every transmitted asset. Otherwise the
plan is BLOCKED with the exact reasons, plus the per-shot
generation entries (idempotency key, composed prompt,
duration, audio flag), the derived counts, the documented
rate, and the estimated cost.

## Execution

`execute_i2v_plan(plan, adapter, delivery_root, ledger,
output_dir, work_dir, registry=None, ...)` executes a READY
plan only. Per generation: validate the keyframe → data URI →
build the request → submit via the ledger → poll → verify the
clip → motion-validate → register via
`production_assets.register_asset` (with provider/model/job
id/keyframe SHA/native geometry/motion classification in the
generation record). A failed or motion-rejected clip raises
and stops the run — no partial final video is ever assembled
from a failed clip.

## What this runtime does not do

- It never generates a still animation as a substitute for
  I2V. The local asset stage refuses `i2v-clip`
  (`runtime/production_assets.py::visual_argv`); FFmpeg stays
  for codec/resolution/framerate conversion, audio mixing,
  cutting, concatenation, transitions, and final encoding.
- It never calls a paid provider without an explicit
  authorization record.
- It never claims a real execution that did not happen. Tests
  use mock transports and a mock adapter, labelled mock.
- It never performs OCR or claims an automated text check.
- It never registers a character: Nadia (DEMO-CHAR-002) is
  project-local, and the R2 driver checks the isolation.
