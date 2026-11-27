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
| `provider-openai-image` | Images API (2026); gpt-image-1.5/2/2.5/2.6 (gpt-image-1 shut down 2026-10-23) | sync | none (sync) | base64 `b64_json` | per token/request; current per-model pricing UNCONFIRMED | up to 10 on edits | no |
| `provider-gemini-image` | Interactions API (Api-Revision 2026-05-20); gemini-nano-banana-2.1, gemini-3.1-flash-lite-image, gemini-3-pro-image | sync | none (sync) | base64 | per image/token; Nano Banana 2.1 ≈ $0.0336 (1K) / $0.0504 (2K) / $0.113 (4K) (secondary-quoted) | up to 14 (4 character max on 2.1) | no |
| `provider-fal-image` | fal Model APIs (queue + direct); fal-ai/nano-banana-2, google/nano-banana-2.1, fal-ai/flux-2-pro, fal-ai/flux/dev | queue + polling (direct sync) | PUT `cancel_url` | fal.media CDN URL (≥ 7 days) | per output from prepaid credits; HTTP 500+ never charged; queue-wait never charged | per-endpoint (up to 10 on some) | no |
| `provider-veo-video` | Veo 3.1 (Gemini API preview IDs; Vertex GA IDs); veo-3.1-generate-preview / fast / lite | async long-running op + polling | UNCONFIRMED | download URL / GCS URI | per second, success only; Lite $0.05/s, Fast $0.10/s, Standard $0.40/s (720p) (secondary-quoted) | up to 3 (Standard/Fast; Lite: none) | yes (native) |
| `provider-kling-video` | Kling AI Open Platform; kling-4.0 / 4.0-flash / 3.0 / 3.0-turbo | async `task_id` + polling, `callback_url` | UNCONFIRMED | result URL, 30 days | prepaid units; failed tasks not charged | keyframes / multi-image / Omni | yes |
| `provider-ltx-video` | LTX API v2 (async; V1 retired 2026-10-26); ltx-2-5-fast / pro | async only, job ID polling | UNCONFIRMED | `video_url`, < 24 h | per second of output video; Fast $0.09/s (720p); failed-task charging UNCONFIRMED | one first-frame image | yes (incl. audio-to-video lip-sync) |
| `provider-elevenlabs-voice` | ElevenLabs REST v1; eleven_v4 / v4_turbo / v3 / multilingual_v2 / flash_v2_5 | sync | none (sync) | response bytes | per character: $0.08/1,000 chars (v4/v3/multilingual v2); $0.04/1,000 (turbo/flash) (secondary-quoted); free tier 10,000 credits/mo, non-commercial only | n/a (voice sample for cloning) | yes |
| `provider-lyria-music` | Lyria 3.5 via Interactions API (Api-Revision 2026-05-20); lyria-3.5 | sync | none (sync) | base64 MP3 | flat $0.08 per song, including failed takes (secondary-quoted) | images as inspiration only (up to 10) | yes (music, SynthID watermark) |

**Sora** (`provider-sora-video`): FAILED. The Sora 2 models and
the Videos API were shut down 2026-09-24 (OpenAI docs: no longer
available, no one-to-one replacement API). No adapter exists and
none will be built. Source:
https://developers.openai.com/api/docs/models/sora-2-pro

## Credential handling

One allow-listed environment variable per provider, read only by
`resolve_provider_secret`:

- `OPENAI_API_KEY` — OpenAI image
- `GEMINI_API_KEY` — Gemini image, Veo video, Lyria music
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
spec, retrieval kind, and the documented behaviour fields. The
transport is injectable: tests pass a mock transport; the default
transport is urllib with a timeout. A transport failure after the
request was sent is `submission-uncertain` — the caller moves the
execution to `NEEDS_USER_ACTION` and never resubmits
automatically. Synchronous providers return `completed: True`
with the saved output artifact; async providers return a provider
job id and are polled (still-running stays RUNNING; completed
with an output URL is retrieved with a size limit and verified;
provider failure and provider cancellation are classified).
Retrieval kinds: `base64-body` (OpenAI/Gemini image, Lyria),
`response-body` (ElevenLabs), `cdn-url` (fal.ai),
`download` (Veo), `url` (Kling, LTX). A sync adapter that returns
both a provider job id and a completed output is driven to
`VALIDATING_OUTPUT` with the job id recorded — the job id never
masks a completion.

## Open items

To close before any live conformance run per provider (no live
run is authorized in this round):

- OpenAI image: current per-model pricing.
- Gemini image: direct re-read of the pricing page.
- Kling video: direct read of the official docs (login/JS-gated
  here); commercial terms; cancellation support.
- LTX video: licence, training-use terms, failed-task charging,
  webhooks, cancellation support.
- ElevenLabs voice: direct read of the official docs (fetch
  blocked here); under-18 clause for kids content.
- fal.ai image: training-use clause.
- Veo video: preview-ID deprecation schedule; cancellation
  support.
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
(`{min_seconds?, max_seconds?}`) and `resolution_limits`. All are
optional, so every valid v2.5 record remains valid. The generated
registry (`registry/providers.json`) is compiled from the
`providers:` section of
`architecture/COMPANION_CAPABILITY_REGISTRY.yaml` by
`scripts/generate-registries.py`.
