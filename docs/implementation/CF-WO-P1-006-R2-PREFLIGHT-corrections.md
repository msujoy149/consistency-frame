# CF-WO-P1-006-R2-PREFLIGHT corrections — Kling elements
conditioning, GCS output policy & retention truth

Work order CF-WO-P1-006-R2-PREFLIGHT, branch
`feat/cf-p1-004-universal-production-brain`, PR #5 (open, Draft,
unmerged). Worker 1 (code) round: starting HEAD efde823, local
HEAD b0d87e0, tree clean at round start. No push, no merge, no
commit by this worker — changes are left uncommitted for the
coordinator to integrate. No paid call was made, no credential
was read or used, and no real I2V execution exists.

This document records what was decided, what was built, what
was verified, and what is still blocked. It quotes no generated
value (no commit SHA, file hash, byte count, or manifest entry
count) — those live in the generated reports, which are
regenerated at integration.

## §1. Elements conditioning

### What was wrong

The R2 contract refused `elements` outright: the
character/object element mechanism would have transmitted
extra reference images, and no first production had been
authorized for it. That refusal is now wrong on two counts.
First, the official schema documents `elements`
(`KlingV3ComboElementInput`) as a first-class field of this
endpoint, and identity preservation across shots needs it:
without elements, every shot carries only its keyframe and
the recurring character's identity is re-derived per shot.
Second, the refusal message implied the provider lacked the
mechanism, which it does not.

### What the official schema says

Endpoint `fal-ai/kling-video/v3/pro/image-to-video`
(model page
https://fal.ai/models/fal-ai/kling-video/v3/pro/image-to-video/api):

- `elements`: list of `KlingV3ComboElementInput`, one element
  per character, in prompt-reference order. The prompt
  references them as `@Element1`, `@Element2`, and so on.
- `frontal_image_url`: string — the main frontal view of the
  character or object.
- `reference_image_urls`: list of strings — additional
  angles, 1–3 supported, at least one image required per
  element.
- `video_url`: string — only one element with a video per
  request.
- `voice_id`: string — voice control for the element (not
  used here: this production runs with `generate_audio`
  false, so no voice is bound to an element).

### What was implemented

- `runtime/provider_contracts.py::FalVideoContract` builds
  and validates the `elements` array
  (`validate_fal_video_elements`, also reused by the I2V
  runtime at plan time):
  - one element per character, in prompt-reference order;
  - `frontal_image_url` required per element;
  - `reference_image_urls` 1–3, at least one required;
  - an element with neither a frontal nor a reference image
    is refused;
  - `video_url` elements are refused — the provider allows
    only one element with a video per request, and this
    production uses image elements only;
  - `voice_id` is refused — voice control is unused;
  - the prompt must reference exactly `@Element1`..`@ElementN`
    — every element referenced, no reference beyond the array.
- `runtime/image_to_video.py` adds the binding layer:
  - `validate_reference_asset` — file exists, size within
    the provider limit, SHA-256 matches the asset manifest,
    decodes as a supported image with known dimensions,
    identity approved at project level, transmission
    permission recorded. A missing reference BLOCKS
    submission; a different reference is never silently
    substituted.
  - `validate_identity_binding` — one character's binding:
    frontal + 1–3 additional references, all validated;
    `video_url` / `voice_id` refused.
  - `build_elements_payload` — builds the provider array
    from approved bindings (data URIs from validated local
    files, the same mechanism as the keyframe data URI).
  - `build_shot_elements` — one shot's array, or None: a
    shot without the recurring character gets NO elements
    entry; a shot with the character but no binding raises.
  - `build_execution_plan(..., identity_bindings=...)` —
    when bindings are supplied, every character shot must
    carry a valid approved binding (its reference asset ids
    join the authorization scope), the generation entries
    carry the built `elements` array, and a prompt/elements
    mismatch blocks the plan at plan time instead of failing
    at submission. When no bindings are supplied the legacy
    path is unchanged. A pending or missing reference is a
    BLOCKED plan, not a skipped element — references are
    pending generation after script approval, and the
    implementation handles that fail-closed.
  - `build_i2v_request(..., elements=...)` and
    `execute_i2v_plan` pass elements through to the contract
    and the adapter context, so the adapter's contract
    rebuild still matches the contract-built request.
  - All runtime API changes are additive only: existing
    callers keep working; new parameters are optional with
    safe defaults.
- `runtime/media_adapters.py`: the fal-video spec records
  elements support and `generate_audio` false support.

### Start image vs element: role separation

- The keyframe (`start_image_url`) is the COMPOSITION and
  scene context for one shot: where the character is, what
  the scene looks like, the framing. It is shot-specific
  and stays separate from `elements`.
- An elements entry is IDENTITY PRESERVATION for one
  recurring character: the approved frontal view plus 1–3
  additional angle references, the SAME references on every
  shot containing that character.
- A shot without that character gets no elements entry —
  never an unrelated reference. Multiple characters use one
  element per character, in prompt-reference order.

### What is NOT claimed

No identity preservation is claimed to be perfect. Elements
conditioning is a provider input; whether the generated
frames actually kept the character's identity is decided
afterwards by human review of real frames. The record type
for that review is
`runtime/image_to_video.py::record_character_drift_review`
(frame checks with pass/fail/not-checked verdicts per
frame; the overall verdict is derived — `consistent` only
when every check passed, `drift-found` when any failed, and
no verdict at all when no frame has been checked). No
generated frames exist yet, so no review is completed.

### Schemas

New v2.5 schemas (additive; optional new fields, no breaking
change to any existing required field — the files are new,
so there is nothing earlier to break):

- `schemas/character-identity.json` — identity reference
  binding: frontal + 1–3 additional angle references,
  approval state, transmission permission.
- `schemas/image-to-video-job.json` — elements payload,
  `generate_audio` false, output origin, retention headers
  (`X-Fal-Store-IO` + `X-Fal-Object-Lifecycle-Preference`),
  ZDR status `UNCONFIRMED` (the schema refuses any other
  ZDR value).

## §2. GCS output policy

### Permitted origins and paths

For the fal-ai/kling-video/v3/pro/image-to-video result
contract, and bound to provider id `provider-fal-video` +
model `fal-ai/kling-video/v3/pro/image-to-video` only:

- `https://storage.googleapis.com/falserverless/...` — the
  fal serverless bucket, path prefix `/falserverless/` only.
- `https://v3b.fal.media/...` — the fal CDN v3 origin, only
  where actually used.
- `https://fal.media/...` — the legacy fal CDN host, kept
  for the existing mock-tested download path.

### Why

The model page's own output example is Google Cloud
Storage:
`https://storage.googleapis.com/falserverless/example_outputs/kling-v3/pro-i2v/out.mp4`
(model page
https://fal.ai/models/fal-ai/kling-video/v3/pro/image-to-video/api).
For this endpoint the model-specific page wins over the
general retention page (see the discrepancy below). The GCS
rule is implemented as a per-host path prefix
(`output_path_prefixes` in
`runtime/provider_url_policy.py::ProviderURLPolicy`): a host
listed there accepts only output URLs whose path starts
with one of its prefixes. The policy instance carrying the
GCS rule is built from the fal-video spec only, so no other
provider inherits it.

### What is still rejected

- Any other GCS path or bucket
  (`/other-bucket/...`, `/falserverless2/...` — the prefix
  is `/falserverless/` with the trailing slash — a bare
  host path, or any path that merely resembles the prefix).
- Any other host, including lookalike hosts
  (`storage.googleapis.com.evil.example.com`).
- No broad wildcard for Google or fal subdomains; no global
  allow of `storage.googleapis.com` for arbitrary downloads.
- Localhost, private IP, link-local, reserved, metadata and
  otherwise disallowed destinations, as before.
- Unvalidated redirects: every redirect hop is validated
  against the same policy before the transport is called
  for it, and DNS/connection pinning applies as implemented
  in the existing security policy.

### Download handling

- No credential or provider authorization header is sent to
  a result-download URL (the adapter strips authorization
  headers for output downloads whose host is not one of the
  provider's API origins — verified by test, with the mock
  transport recording the headers it received).
- The downloaded body is validated: the response content
  type must be `video/mp4` where the spec declares it, and
  the file must start with MP4 magic bytes (`ftyp`). An
  HTML error page returned in place of MP4 media — whether
  labelled `text/html` or mislabelled `video/mp4` — is
  refused and no partial file is left behind. File size is
  capped by the existing download limit, and the download
  goes to controlled local storage with an immediate SHA-256
  verification by the existing output verification.
- The original provider result URL is recorded in redacted
  form only (`scheme://host/path`, no query string) via
  `runtime/provider_url_policy.py::record_result_url`, so a
  signed download URL's query authorization is never
  stored, logged or reported.

### The fal-CDN-vs-GCS discrepancy

The retention page
(https://fal.ai/docs/documentation/model-apis/media-expiration,
updated 2026-11-17) says generated outputs go to the fal
CDN — but the Kling model page's own output example is
Google Cloud Storage
(`storage.googleapis.com/falserverless/...`). For THIS
endpoint the model-specific page wins: outputs land on GCS,
the fal CDN ACL does NOT protect a
`storage.googleapis.com` output URL, and GCS outputs are
public-by-link. Recorded in the code comments, in this
document, and in `docs/runtime/PROVIDER_ADAPTERS.md`. ZDR
is recorded as UNCONFIRMED for this endpoint.

## §3. Retention / ACL / ZDR truth table

Every fal-video request carries both headers (built by
`runtime/provider_contracts.py::fal_retention_headers`;
the table is `fal_retention_truth_table`, also exposed as
`runtime/image_to_video.py::retention_truth_table`).

| Item | Status | Scope |
| --- | --- | --- |
| `X-Fal-Store-IO: 0` | Sent on every fal-video request | Disables request-history payload storage (otherwise stored 90 days by default); does NOT equal ZDR |
| `X-Fal-Object-Lifecycle-Preference` (expiration + initial_acl) | Sent on every fal-video request (expiration 7 days, initial_acl default forbid, unless overridden per request) | fal CDN v3 outputs only (`https://v3b.fal.media/...`); does NOT protect `storage.googleapis.com` outputs |
| fal CDN v3 file ACL | Controlled per request by `initial_acl` (default forbid: 403 to anyone but the owner) | fal CDN v3 URLs only; input files uploaded before the call keep the account default ACL and are NOT covered by the request header |
| GCS output URL (`storage.googleapis.com/falserverless/...`) | Public-by-link; no ACL applies | The model page's own output example for this endpoint is GCS, so the fal CDN ACL does NOT protect it |
| ZDR (zero data retention) | UNCONFIRMED for this endpoint | Not enabled by default; requires sales-team confirmation of availability/coverage; is not a single setting; does not disable application logging or app-managed persistent storage |

Notes:

- The lifecycle header value is JSON:
  `{"expiration_duration_seconds": <seconds>, "initial_acl":
  {"default": "allow"|"forbid"|"hide", "rules": [...]}}`.
  The `initial_acl` is an OBJECT with a `default` decision
  plus optional per-user `rules` — not a bare string. (An
  early draft of this round assumed a string value; the live
  fal.ai platform-headers and file-access-controls pages
  show the object shape, and the implementation validates
  it.)
- The default expiration is 7 days, matching the documented
  fal CDN retention floor (at least 7 days). The default
  `initial_acl` is `{"default": "forbid"}`: anyone but the
  owner gets 403 on a fal CDN v3 output; the owner always
  retains access.
- The runtime never claims ZDR. The schema
  (`schemas/image-to-video-job.json`) refuses any ZDR value
  other than `UNCONFIRMED`.

Sources (checked 2026-11-28):

- https://fal.ai/docs/documentation/model-apis/common-parameters
  (platform headers)
- https://fal.ai/docs/documentation/model-apis/media-expiration
  (retention; updated 2026-11-17)
- https://fal.ai/docs/documentation/model-apis/file-access-controls
  (file access controls; updated 2026-11-17)
- https://fal.ai/models/fal-ai/kling-video/v3/pro/image-to-video/api
  (endpoint schema + GCS output example)
- https://fal.ai/docs/api-reference/inference-api/queue/submit
  (queue submit)

## §4. multi_prompt design restriction

The R2 contract refused `multi_prompt` with a message that
read as if the provider lacked the field. The provider
documents `multi_prompt` (a list of prompt elements, each
with its own duration) — the refusal was a production
choice, not a provider gap. It is now recorded as what it
is: an intentional DESIGN RESTRICTION. This production
builds one shot per generation with a single prompt, so
`multi_prompt` is intentionally unused, and a context
carrying it is refused with a message that says exactly
that ("this is an intentional design restriction — one
shot is one generation with a single prompt, so
multi_prompt is unused even though the provider documents
the field"). Nothing about the provider is implied.

## §5. Test-found defects

New suite `tests/test_p1006_r2_preflight.py`, registered in
`tests/run-tests.sh` as `CF-P1-006-R2-PREFLIGHT` (93 checks,
all passing locally). Coverage: elements payload exact
fields, frontal reference, additional references (1–3,
reject 0 and 4+), character binding on every applicable
shot, non-character shot receiving no unrelated references,
missing character reference blocking submission, start
image separate from elements, official GCS output URL
accepted, unapproved GCS path/bucket rejected, unapproved
origin rejected, no authorization header on output
download, redirect to a prohibited host rejected, redirect
to a permitted same-policy destination validated, file type
and MP4 validation (HTML error page rejected, fake-MP4
magic rejected), `X-Fal-Store-IO: 0` present, lifecycle +
ACL header handling, ACL scope (fal CDN v3 only — GCS
output not covered), ZDR not claimed, `generate_audio:
false` in every built request, text overlay disabled, paid
submission blocked without explicit authorization, zero
network calls on the preflight path (mock transport only),
mock execution with elements end to end, drift-review
record behaviour, and both new schemas validated
(including a fixture with a claimed ZDR value, refused).

Defects found by the new tests and fixed in this round:

1. **Plan accepted a prompt/elements mismatch.** The
   execution plan built the `elements` array but never
   checked the prompt's `@Element` references against it,
   so a plan could go READY and fail only at submission.
   The plan now validates prompt references against the
   built array (`validate_fal_video_elements`, reused from
   the contract) and blocks with the exact reason.
2. **Downloads accepted any body.** `retrieve()` checked
   the URL and the HTTP status but not the content type or
   the bytes, so an HTML error page returned in place of
   MP4 media would have been saved as a clip. Downloads
   now require the spec-declared content type (`video/mp4`
   for fal-video) and MP4 `ftyp` magic bytes, and leave no
   partial file behind on refusal.
3. **GCS origin allow was path-blind.** The first version
   of the policy change added `storage.googleapis.com` to
   the output origins with no path rule, so any GCS bucket
   would have been accepted. The policy now carries
   per-host output path prefixes, and the fal-video rule
   permits only `/falserverless/`.
4. **`initial_acl` shape.** An early draft treated the
   lifecycle ACL as a bare string; the live fal.ai docs
   show it is an object (`{"default": ..., "rules":
   [...]}`). The header builder validates the object
   shape, and the schema encodes it.
5. **Plan ignored the project's own audio setting
   (coordinator-found at integration).** `build_execution_plan`
   defaulted `generate_audio=True` and never read the
   project config, so a plan built from the R2 project —
   whose `i2v.generate_audio` is false — was still priced
   audio-on ($8.06), while the driver (which passes
   `generate_audio=False` explicitly) priced the same plan
   audio-off ($5.38). The builder now resolves the value
   from `project["i2v"]["generate_audio"]` when the caller
   passes nothing (default True when the key is absent or
   not a boolean); an explicit argument always wins. The
   R2 suite's two cost assertions were corrected to the
   superseded rate at the same time ($8.06 / 0.168 →
   $5.38 / 0.112) — the assertions still pin the exact
   figures, against the new correct values.

### Coordination note (not a defect in this round's code)

While this round ran, the parallel storyboard worker
changed the R2 driver in the shared tree to pass
`generate_audio=False` (and the example project files).
That change moves the R2 driver's estimated cost to the
audio-off rate, so the R2 suite's
`driver-summary-blocked` check — which expects the
audio-on cost — fails in the shared tree. The failure is
in the driver + example files this worker was told not to
touch, not in the runtime code: with the HEAD driver and
HEAD example files restored in a scratch copy, the R2
suite passes its full count with this round's runtime
changes applied. The coordinator reconciles the driver
change and the R2 cost expectation at integration; neither
the driver nor the R2 test was edited here.

**Resolution (coordinator, at integration).** The audio-off
rate is the preflight decision (WO §7/§9: `generate_audio:
false`, $0.112/s), so the two R2 cost assertions were
corrected to the superseded rate — `plan-cost` from
$8.06 / 0.168 to $5.38 / 0.112, and
`driver-summary-blocked` from $8.06 to $5.38. Both still
pin the exact figure (48 s × $0.112); this is a correction
to a superseded rate, not a weakening: the assertions are
as strict as before, against the new correct values. The
R2 suite passes its full count after the change.

## §6. What is still blocked / open limitations

- The script is a DRAFT awaiting user approval; no
  reference image, keyframe, or voice recording has been
  generated from it; no real I2V execution exists; I2V
  capability is BLOCKED pending the user's explicit
  authorization of the paid provider call (and script
  approval). No final MP4 was delivered in this round —
  there is none, and claiming one would be fabrication.
- Identity references are pending generation after script
  approval. The elements implementation handles that
  fail-closed (a pending reference is a BLOCKED plan), but
  no elements payload has been transmitted to any provider.
- No video provider is VERIFIED/EXERCISED by a live call;
  all external providers remain conformance NOT_TESTED. The
  fal adapter path is exercised over mock transports only.
- The R2 motion-classification limitation stands
  (pixel-diff classification cannot reliably distinguish
  every zoom from subject motion; the architectural guards
  carry that case), and the R1 audio defect disclosure
  stands.
- The manifest count changes with the new files in this
  round; the coordinator regenerates the manifest at
  integration. No report was regenerated here.

## §7. Elements-tier pricing correction (parent-found defect, 2026-11-28)

### What was wrong

The preflight cost plan priced every shot at $0.112/s
(audio off). That is the WITHOUT-elements rate. fal.ai
charges a separate, higher tier for image-to-video WITH
elements, and every shot in this production uses elements:
Nadia (DEMO-CHAR-002) appears in all 8 shots (s1, s2, s3a,
s3b, s4, s5, s6a, s6b — see
`examples/p1006-r2-photorealistic-image-to-video/character-appearance-map.json`),
each carrying the frontal @Element1 reference plus 1 angle
reference. The correct rate for our shots is $0.224/s
(audio off), not $0.112/s. The preflight $5.38 total and
the $0.672 per-shot figure were therefore both wrong by a
factor of two.

### What the official sources say

Checked 2026-11-28, two fal.ai learn pages. The official
API schema page
(https://fal.ai/models/fal-ai/kling-video/v3/pro/image-to-video/api)
lists no pricing — pricing comes from the learn pages, not
the schema:

- https://fal.ai/learn/tools/kling-3-0-pro-vs-sora-2-pro —
  comparison table: "Per-second price (with elements) |
  $0.224 audio off, $0.336 audio on"; body: "Per-second
  pricing runs $0.112 with audio off, $0.168 with audio
  on, and $0.196 when voice control is layered in" (base,
  without elements).
- https://fal.ai/learn/tools/seedance-2-0-vs-kling-3-0 —
  "Image-to-video with elements: $0.224/second with audio
  off, $0.336/second with audio on, $0.392/second with
  voice control." And "Text-to-video and image-to-video
  (without elements): $0.112/second with audio off,
  $0.168/second with audio on, $0.196/second with voice
  control."

Rate table (Kling 3.0 Pro, per second, 1080p): without
elements — $0.112 audio off, $0.168 audio on, $0.196 voice
control; with elements — $0.224 audio off, $0.336 audio
on, $0.392 voice control. The $0.112/s rate applies ONLY
WITHOUT elements.

### Corrected figures

- Per shot (6 s, elements, audio off): 6 x $0.224 =
  $1.344.
- Total generation (8 shots x 6 s = 48 s): 48 x $0.224 =
  $10.752, rounded $10.75.
- Keyframe generation: $0 billed (unchanged — platform
  built-in image generation, not a billed provider charge;
  recorded as $0 / not-applicable, not invented).
- Retry budget: one retry per failed shot at that shot's
  own cost ($1.344 per 6 s shot); maximum retry budget
  $10.752, rounded $10.75; worst-case total (generation +
  full retry) $10.752 + $10.752 = $21.504, rounded $21.50.
  No second retry without a new approval.
- For comparison: with elements and audio on, 48 x $0.336
  = $16.128 (rounded $16.13); without elements and audio
  on, 48 x $0.168 = $8.064 (rounded $8.06).

### Superseded figures

Both superseded, reason: the elements pricing tier was
missed.

- R2 $8.06 (audio on, no-elements rate $0.168/s).
- Preflight $5.38 (audio off, no-elements rate $0.112/s).

### What changed

- Cost plan
  (`examples/p1006-r2-photorealistic-image-to-video/cost-plan.json`
  + `cost-plan.md`): pricing block now the elements tier
  (rate_audio_off 0.224 with elements; without-elements
  0.112/0.168 and voice-control 0.196/0.392 recorded for
  completeness); every shot entry rate 0.224, cost 1.344,
  `uses_elements: true`; totals exact 10.752 / rounded
  10.75; retry max 10.752 / 10.75; worst case 21.504 /
  21.50; both superseded figures recorded.
- Gate A checklist and Gate B authorization sheet:
  corrected to $1.344/shot, $10.75 total, retry max
  $10.75, worst $21.50; Gate B carries the
  with/without-elements rate table and the corrected
  audio-on comparison (with elements 48 x $0.336 =
  $16.13; without elements 48 x $0.168 = $8.06);
  decision box now $10.75; charging-rules clip price now
  $1.344. The GCS public-by-link acceptance box is
  unchanged (already verified).
- Gate B element-conditioning row corrected: element
  conditioning IS wired into the provider contract
  (`runtime/provider_contracts.py::FalVideoContract`,
  `validate_fal_video_elements`) and the I2V runtime
  (`runtime/image_to_video.py::build_shot_elements`) —
  verified against the code in this round; the "not yet
  wired" wording was stale from before the preflight
  elements work.
- Example data: `project.json` audio note, `README.md`,
  `story-coverage-report.json` verdict, and the per-shot
  cost headers in `motion-prompts.md` corrected to the
  elements figures.
- R2 authorization request: only the top SUPERSEDED note
  updated (replacement figure now $10.75, elements tier,
  audio OFF); the full original text below it is
  unchanged.
- Runtime rate model for this round: per-shot by elements
  usage — a shot carrying an `elements` array is priced
  at the with-elements rate, a shot without elements at
  the without-elements rate — with the driver and the
  storyboard cost assertions following it. The runtime,
  scripts, tests, and driver changes are the parallel
  worker's scope in this round; this section records the
  docs + example-data side, and the coordinator confirms
  the runtime side at integration.
- The earlier sections of this document are unchanged:
  their $5.38 / $0.112 passages describe what preflight
  did at the time, and are history, not live figures.
