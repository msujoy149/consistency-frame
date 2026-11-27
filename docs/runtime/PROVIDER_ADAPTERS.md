# Provider adapters (CF-WO-P1-005)

The provider adapters in `runtime/media_adapters.py` execute
compiled task packets through real providers. Every adapter follows
the canonical `MediaAdapter` interface
(`docs/runtime/MEDIA_EXECUTION_RUNTIME.md`): it declares what it
can do, validates inputs, prepares a request without submitting it,
submits, polls async jobs, cancels where the provider allows it,
retrieves outputs, and verifies them. Every method fails closed
and never invents a result.

Facts below come from the current official provider documentation
audited 2026-11-27. `documentation_status` is `official` when the
official page was read directly, `secondary-quoting-official` when
the official page could not be fetched here and the fact is quoted
from a source citing it. Where a fact is UNCONFIRMED, the adapter
says so instead of inventing it.

## Local providers

| Provider | Status | Commercial | Evidence |
| --- | --- | --- | --- |
| `provider-ffmpeg` (FFmpeg 8.1.2) | EXERCISED | approved (local tool) | `CF-P1-005-FFMPEG` (28 checks, real probe/transcode/assembly) |
| `provider-voicestudio-omnivoice` (VoiceStudio 0.5.8, OmniVoice) | EXERCISED | **never** — CC-BY-NC weights | Real generation 2026-11-27 (Bengali, 1.98 s, audio id `1faa2e3e`); Bengali/English/Hindi 2026-11-12/13 |
| `provider-openmontage-assembly` (OpenMontage, pin `fecb9a1`) | EXERCISED (demo-render entry only) | approved (local tool; output status depends on asset providers) | Demo `animated-reel-20s` rendered 2026-11-27, ffprobe-validated (21.056 s, 1920x1080); same render through `OpenMontageAdapter.submit`. Production assembly NOT exercised |
| `provider-opentimelineio` | NOT_TESTED | not approved (unverified) | Not installed; probe reports unavailable; no adapter — the canonical timeline manifest covers interchange |

## External providers — readiness matrix

All eight are conformance NOT_TESTED: no live paid call has been
made, and none is made without explicit user authorization for
that run. Adapter tests use mock transports only.

| Provider | API / models | Async | Cancel | Retrieval | Charge | Refs | Audio |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `provider-openai-image` | Images API (2026); gpt-image-1-mini, gpt-image-1.5, gpt-image-2 (+2026-04-21 snapshot), gpt-image-2.5-sunburst/flare (+2026-09-08 snapshots), gpt-image-2.6-sunburst/flare, chatgpt-image-latest (gpt-image-1 shut down 2026-10-23) | sync | none (sync) | base64 `b64_json` | per token/request; current per-model pricing UNCONFIRMED (not re-read 2026-11-27) | up to 16 on edits | no |
| `provider-gemini-image` | Interactions API (Api-Revision 2026-05-20); gemini-nano-banana-2.1, gemini-3.1-flash-lite-image, gemini-3-pro-image, gemini-3.1-flash-image (deprecated 2026-10-06, no shutdown date, still works) | sync | none (sync) | base64 | per image/token; Nano Banana 2.1 ≈ $0.0336 (1K) / $0.0504 (2K) / $0.113 (4K) (secondary-quoted) | up to 14 (2.1/3.1-flash-image: 10 objects + 4 characters; Pro: 6 objects + 5 characters + 3 style) | no |
| `provider-fal-image` | fal Model APIs (queue + direct); fal-ai/nano-banana-2, google/nano-banana-2.1, fal-ai/flux-2-pro, fal-ai/flux/dev | queue + polling (direct sync) | PUT `cancel_url` | fal.media CDN URL (≥ 7 days) | per output from prepaid credits; HTTP 500+ never charged; queue-wait never charged; a 422 may be charged if GPU time was spent; nano-banana-2 $0.08/image (2K 1.5x, 4K 2x, 0.5K 0.75x) | not supported by the contract (reference-part serialization UNCONFIRMED; no upload flow) | no |
| `provider-veo-video` | Veo 3.1 (Vertex AI / Gemini Enterprise Agent Platform); veo-3.1-generate-001 (GA 2025-11-17), veo-3.1-fast-generate-001 (GA), veo-3.1-lite-generate-001 (Preview 2026-04-02). The Gemini API preview IDs (veo-3.1-generate-preview / fast / lite) were SHUT DOWN 2026-10-22 and are refused by the contract | async long-running op + polling (`:fetchPredictOperation`, POST, `operationName` in body) | none — no cancel operation is documented for Vertex Veo | inline video bytes in the poll response (no `storageUri`); a GCS URI output cannot be downloaded (download origin UNCONFIRMED) | per 1 count (official unit; the pricing page does not define 1 count); per-second pricing is SECONDARY-only and is NOT encoded | up to 3 (Standard/Fast; Lite image input UNCONFIRMED — Vertex docs conflict) | yes (native) |
| `provider-kling-video` | Kling AI Open Platform (legacy /v1 design); kling-v1, kling-v1-6, kling-v2-master, kling-v2-1-master, kling-v2-5-turbo, kling-v2-6 | async `task_id` + polling, `callback_url` | none — no cancel endpoint is documented (secondary-quoting-official) | result URL, 30 days | prepaid units; failed-task charging UNCONFIRMED | image-to-video first/last frame (base64, ≤ 10 MB) | yes |
| `provider-ltx-video` | LTX API v2 (async; V1 retired 2026-10-26); ltx-2-5-fast / pro, ltx-2-3-fast / pro | async only, job ID polling | none found in the official docs (UNCONFIRMED) | `video_url`, < 24 h (signed URL expires 1 hour after it is checked) | per second of output video; Fast $0.09/s (720p); prepaid credits are reserved before generation and charged only on success — a failed job releases its reservation | one first-frame image (data URI, ≤ 7 MB) | yes (incl. audio-to-video lip-sync) |
| `provider-elevenlabs-voice` | ElevenLabs REST v1; eleven_v4 / v4_turbo / v3 / multilingual_v2 / flash_v2_5 | sync | none (sync) | response bytes | per character: $0.08/1,000 chars (v4/v3/multilingual v2); $0.04/1,000 (turbo/flash) (secondary-quoted); free tier 10,000 credits/mo, non-commercial only | n/a (voice sample for cloning) | yes |
| `provider-lyria-music` | Lyria 3.5 via Interactions API (Api-Revision 2026-05-20); lyria-3.5, lyria-3-clip-preview (30 s) | sync | none (sync) | base64 MP3 | flat $0.08 per song, including failed takes (secondary-quoted) | images as inspiration only (up to 10) | yes (music, SynthID watermark) |

**Sora** (`provider-sora-video`): FAILED. The Sora 2 models and
the Videos API were shut down 2026-09-24 (OpenAI docs: no longer
available, no one-to-one replacement API). No adapter exists and
none will be built. Source:
https://developers.openai.com/api/docs/models/sora-2-pro

## Credential handling

One allow-listed environment variable per provider, read only by
`resolve_provider_secret`:

- `OPENAI_API_KEY` — OpenAI image
- `GEMINI_API_KEY` — Gemini image, Lyria music
- `VERTEX_ACCESS_TOKEN` — Veo video (OAuth Bearer token; never an API key)
- `FAL_KEY` — fal.ai image
- `KLING_API_KEY` — Kling video
- `LTX_API_KEY` — LTX video
- `ELEVENLABS_API_KEY` — ElevenLabs voice

Without its variable the adapter fails closed with
`credential-missing`. A missing variable, an empty value, and an
unknown provider are all refusals, never silent fallbacks. Secrets
are never logged, never committed, never placed in Git, reports, or
task packets; error text is redacted. The VoiceStudio and
OpenMontage adapters need no key (local tools).

## Licensing and privacy

- **OmniVoice weights are CC-BY-NC (noncommercial).** The
  VoiceStudio adapter refuses commercial / monetized voice tasks
  outright. A different model is eligible only after its exact
  weights, tokenizer, model terms and dependencies are
  independently cleared. A licensed application does not imply
  every bundled model is commercially licensed.
- **ElevenLabs free tier is non-commercial** (10,000 credits/mo);
  paid tiers carry the commercial licence. The under-18 Prohibited
  Use clause is relevant to kids content and must be checked
  before any kids production uses it.
- **fal.ai training-use clause** is UNCONFIRMED — check the terms
  before sending any private reference image.
- **Transmission:** every external call sends the prompt (and, for
  image/video, reference images; for voice, the voice id or
  reference audio) to the provider. That transmission needs the
  same explicit authorization as the paid call. Local providers
  transmit nothing.
- **Sora shutdown note:** a provider can disappear (Sora, six
  months' notice, no replacement). Nothing in the runtime assumes
  a provider stays available; FAILED providers are never matched.

## How the HTTP adapter works

`HttpProviderAdapter` is driven by one declarative spec per
provider (`PROVIDER_SPECS` in `runtime/media_adapters.py`):
submit URL + method, auth header + scheme, async flag, cancel
spec, retrieval kind, and the documented behaviour fields — and
by one exact contract per provider
(`runtime/provider_contracts.py`), which builds the request
body, parses the submit/poll/result/cancel responses, and
classifies provider errors. The spec says *where* to call; the
contract says *what* to send and *how* to read the answer. No
generic `{model, prompt}` payload is ever built: `translate`
builds the request through the contract, and `submit` refuses
any packet that was not built by one (including a tampered body
or a request built for another provider). Reference assets
arrive through the execution context (`{"mime", "base64"}` or a
workspace `{"path"}`), are normalized inside the workspace
root, and are validated by the contract for its own provider —
fal.ai refuses them outright (reference-part serialization
UNCONFIRMED, no upload flow); OpenAI edits take up to 16
images as multipart; Gemini takes up to 14; Veo up to 3
(Standard/Fast; Lite image input UNCONFIRMED);
Kling image-to-video takes a first (and optional last) frame
as raw base64; LTX takes one first-frame image as a data URI.

The transport is injectable: tests pass a mock transport; the
default transport is the pinned HTTPS transport from
`runtime/provider_url_policy.py` (see "URL security" below). A
transport failure after the request was sent is
`submission-uncertain` — the caller moves the execution to
`NEEDS_USER_ACTION` and never resubmits automatically.
Synchronous providers return `completed: True` with the saved
output artifact; async providers return a provider job id and
are polled (still-running stays RUNNING; completed with an
output URL is retrieved with a size limit and verified, and
completed with inline bytes is saved and verified the same
way; provider failure and provider cancellation are
classified).
Retrieval kinds: `base64-body` (OpenAI/Gemini image, Lyria),
`response-body` (ElevenLabs), `cdn-url` (fal.ai),
`inline-bytes` (Veo), `url` (Kling, LTX). A sync adapter that
returns both a provider job id and a completed output is driven
to `VALIDATING_OUTPUT` with the job id recorded — the job id
never masks a completion. fal.ai completes in two steps: the
poll returns COMPLETED with a `response_url`, and the adapter
fetches the result document from it before downloading.

## URL security (R4-A)

Every outbound URL — submit, poll, cancel, download — is
validated by `runtime/provider_url_policy.py` before any byte
is sent, against explicit per-provider API and output/CDN
origin allowlists: scheme must be HTTPS, no userinfo, no
unapproved host or port, no IP-literal / loopback / private /
link-local / multicast / reserved / unspecified destination, no
cloud-metadata address (169.254.169.254), no alternate numeric
address representation, no encoded path/hostname trick, no
trailing-dot hostname. Every redirect hop is validated the
same way (at most five hops); authorization headers are kept
only on same-origin hops and are sent with a download only
when the download URL's host is the provider's own API origin
(no current provider has a documented API-origin download, so
in practice no download receives them) — a signed CDN
download URL never receives them. The default transport pins
the connection to a validated resolved address, so a hostname
cannot resolve to a prohibited destination between validation
and connection; that pinning protects this client against
DNS-rebinding *of its own requests* — it is not a claim about
the provider's infrastructure, and a one-time hostname check
alone is never presented as rebinding protection. A forbidden
destination is refused before the transport is called for that
hop, and no signed URL query string, credential, or
authorization header is ever logged. Provider-owned async URLs
are constructed from the documented endpoint template plus the
validated job id where possible (Veo's full Vertex operation
name,
Kling's per-task URL, LTX's per-endpoint URL); where a provider
returns a dynamic URL (fal.ai `status_url` / `cancel_url` /
`response_url`) it is validated against that provider's API
origins before use. No status or cancellation endpoint is
invented; providers without documented cancellation stay
explicitly non-cancellable.

## Provider contracts and official-doc audit (R4-B)

One contract class per provider in
`runtime/provider_contracts.py` (`CONTRACTS`, `get_contract`).
Each contract implements: request construction (exact method,
endpoint, headers, body fields), model/operation selection,
authentication (via the adapter's allow-listed credential),
input/reference serialization, submit-response parsing, sync
completion or async job identification, poll-URL construction
plus status parsing, cancellation (only where officially
supported), output-URL or response-byte extraction, and
provider error classification with retryability. Unsupported
operations are refused explicitly; fields the task requires
are never silently dropped; capabilities are never invented.
The contracts were re-audited against the official
documentation on 2026-11-27; the table below records what was
read, what it says, and what stays UNCONFIRMED.

| Provider | Official doc (audit 2026-11-27) | API version | Current model IDs | UNCONFIRMED / NOT_TESTED |
| --- | --- | --- | --- | --- |
| OpenAI image | https://developers.openai.com/api/reference/ruby/resources/images/methods/generate (official, read directly) | Images API (2026) | gpt-image-1-mini, gpt-image-1.5, gpt-image-2, gpt-image-2-2026-04-21, gpt-image-2.5-sunburst/flare (+2026-09-08 snapshots), gpt-image-2.6-sunburst/flare, chatgpt-image-latest | Per-model pricing |
| Gemini image | https://aistudio.google.com/docs/image-generation (official, read directly) | Interactions API, Api-Revision 2026-05-20 | gemini-nano-banana-2.1, gemini-3.1-flash-lite-image, gemini-3-pro-image, gemini-3.1-flash-image (deprecated 2026-10-06, still works) | Pricing is secondary-quoted ($0.0336/1K, $0.0504/2K, $0.1134/4K for 2.1) |
| fal image | https://fal.ai/llms-full.txt + per-model llms.txt (official, read directly) | fal Model APIs (queue + direct) | fal-ai/nano-banana-2, google/nano-banana-2.1, fal-ai/flux-2-pro, fal-ai/flux/dev | Reference-part serialization (refs refused); model-example output URLs use storage.googleapis.com while the platform doc says fal.media (allowlist stays fal.media) |
| Veo video | https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/generate-videos-from-text (official) | Veo 3.1 (Vertex AI / Gemini Enterprise Agent Platform) | veo-3.1-generate-001, veo-3.1-fast-generate-001, veo-3.1-lite-generate-001 | Gemini API preview IDs shut down 2026-10-22; GA-ID retirement wording UNCONFIRMED (model page says Nov 17, 2026 or later, versions page says no date announced); Fast 4K UNCONFIRMED (pricing lists it, model page does not); Lite image input UNCONFIRMED (model page says not supported, capabilities row says supported); GCS download origin UNCONFIRMED, so a GCS URI output is refused; pricing unit is per 1 count (undefined on the pricing page) |
| Kling video | https://app.klingai.com/global/dev/document-api (secondary-quoting-official — official docs are login/JS-gated and could not be read directly) | Kling AI Open Platform, legacy /v1 design | kling-v1, kling-v1-6, kling-v2-master, kling-v2-1-master, kling-v2-5-turbo, kling-v2-6 | Failed-task charging; the newer path-based design (4.0 etc.) is NOT implemented — its prompt field was UNCONFIRMED at audit time; result-URL host |
| LTX video | https://docs.ltx.io/welcome (secondary-quoting-official — direct read not completed here) | LTX API v2 | ltx-2-5-fast/pro, ltx-2-3-fast/pro | Cancellation (none found in the docs); licence and training-use terms; webhooks; result-URL host |
| ElevenLabs voice | https://elevenlabs.io/docs/api-reference (secondary-quoting-official — direct fetch blocked here) | ElevenLabs REST v1 | eleven_v4, eleven_v4_turbo, eleven_v3, eleven_multilingual_v2, eleven_flash_v2_5 | Per-request character limits except eleven_v4 (100,000, official); v4 voice-settings support (stability + similarity_boost only); under-18 clause for kids content |
| Lyria music | https://aistudio.google.com/docs/music-generation (official, read directly) | Lyria 3.5 via Interactions API, Api-Revision 2026-05-20 | lyria-3.5, lyria-3-clip-preview (30 s) | Pricing ($0.08/song incl. failed takes) is secondary-quoted; WAV output fields were not confirmed, so WAV is refused explicitly |

**Readiness discipline.** Mock contract tests
(`tests/test_provider_contracts.py`,
`CF-P1-005-R4-CONTRACTS`, 161 checks) prove the contracts
build the documented requests and parse the documented
responses — they never make a provider EXERCISED or VERIFIED.
EXERCISED needs a real authorized execution with recorded
evidence; VERIFIED needs documented conformance completed. No
live paid call is authorized in this round.

## Open items

To close before any live conformance run per provider (no live
run is authorized in this round):

- OpenAI image: current per-model pricing.
- Gemini image: direct re-read of the pricing page.
- Kling video: direct read of the official docs (login/JS-gated
  here); commercial terms; result-URL host confirmation (a
  completed job's download currently fails closed until the host
  is confirmed); failed-task charging.
- LTX video: licence, training-use terms, webhooks, cancellation
  support, result-URL host confirmation (same fail-closed state
  as Kling).
- ElevenLabs voice: direct read of the official docs (fetch
  blocked here); under-18 clause for kids content.
- fal.ai image: training-use clause; reference-part
  serialization (refs refused until confirmed).
- Veo video: Fast 4K; Lite image input; GA-ID retirement
  wording; GCS download origin (a GCS URI output currently
  fails closed until the host is confirmed); `gemini-omni-1.2-flash`
  (the Gemini API replacement for Veo) needs its own audit and is
  out of scope for this round.
- All providers: a live conformance run needs credentials in the
  allow-listed variables plus explicit user authorization for
  that run — neither exists in this round.

## Provider capability schema

`schemas/provider-capability.json` (v2.5, additive): the P1-005
optional fields are `documentation_url`,
`documentation_status` (`official` /
`secondary-quoting-official`), `api_version`, `async_behaviour`,
`cancellation_support`, `output_retrieval`, `charge_behaviour`,
`aspect_ratios`, `audio_support`,
`character_reference_limits`, plus the existing `duration_limits`
(`{min_seconds?, max_seconds?}`) and `resolution_limits`. R4
adds the optional `voice_controls` field (`supported` list plus
`unsupported` map of control to refusal reason) for the
VoiceStudio backend's genuine controls. All are optional, so
every valid v2.5 record remains valid. The generated registry
(`registry/providers.json`) is compiled from the `providers:`
section of `architecture/COMPANION_CAPABILITY_REGISTRY.yaml` by
`scripts/generate-registries.py`.
