# Cost plan — "Nadia and the River Light" (preflight, audio OFF)

Status: **DRAFT — script awaiting user approval. Estimate only, not a guaranteed final bill.** No paid call has been made. This plan supersedes the R2 draft estimate of **$8.06** (8 clips x 6 s x $0.168/s, audio ON, without elements) AND the preflight estimate of **$5.38** (8 clips x 6 s x $0.112/s, audio OFF, without elements). The counts are unchanged (8 shots, 48 s); the rate changed because every shot uses the Nadia character element, which fal.ai prices on a separate, higher tier. Reason for superseding both: the elements pricing tier was missed.

## Model and pricing tier

- **Provider:** fal.ai (`provider-fal-video`)
- **Model:** Kling Video v3 Pro (Image to Video) — `fal-ai/kling-video/v3/pro/image-to-video`
- **Endpoint:** `POST https://queue.fal.run/fal-ai/kling-video/v3/pro/image-to-video`
- **Resolution:** 1080p (9:16, 1080x1920 as the provider returns it)
- **Audio setting:** `generate_audio: false` for every shot (external narration handled separately by the existing voice pipeline)
- **Elements:** every shot carries the Nadia character element (`@Element1`, frontal `ref-nadia-front` + 1 angle reference per shot) — Nadia, DEMO-CHAR-002, appears in all 8 shots (see `character-appearance-map.json`). Every shot is therefore priced at the **with-elements** tier.
- **Rate:** **$0.224 per second, audio off, WITH elements, 1080p**
- **Formula:** per-shot cost = shot_duration_seconds x $0.224

## Rate table (fal.ai Kling 3.0 Pro, per second, 1080p)

| Tier | Audio off | Audio on | Voice control |
| --- | --- | --- | --- |
| Without elements | $0.112 | $0.168 | $0.196 |
| **With elements** | **$0.224** | $0.336 | $0.392 |

The base $0.112/s rate applies ONLY WITHOUT elements. Sources, re-verified live 2026-11-28:

- https://fal.ai/learn/tools/kling-3-0-pro-vs-sora-2-pro — comparison table: "Per-second price (with elements) | $0.224 audio off, $0.336 audio on"; body: "Per-second pricing runs $0.112 with audio off, $0.168 with audio on, and $0.196 when voice control is layered in" (base, without elements).
- https://fal.ai/learn/tools/seedance-2-0-vs-kling-3-0 — "Image-to-video with elements: $0.224/second with audio off, $0.336/second with audio on, $0.392/second with voice control." And "Text-to-video and image-to-video (without elements): $0.112/second with audio off, $0.168/second with audio on, $0.196/second with voice control."

The official API schema page https://fal.ai/models/fal-ai/kling-video/v3/pro/image-to-video/api lists no pricing — pricing comes from the two fal.ai learn pages above.

## Per-shot cost

| Shot | Scene | Duration | Rate | Cost |
| --- | --- | --- | --- | --- |
| s1 | SC1 | 6 s | $0.224/s | $1.344 |
| s2 | SC2 | 6 s | $0.224/s | $1.344 |
| s3a | SC3 | 6 s | $0.224/s | $1.344 |
| s3b | SC3 | 6 s | $0.224/s | $1.344 |
| s4 | SC4 | 6 s | $0.224/s | $1.344 |
| s5 | SC5 | 6 s | $0.224/s | $1.344 |
| s6a | SC6 | 6 s | $0.224/s | $1.344 |
| s6b | SC6 | 6 s | $0.224/s | $1.344 |

Every shot uses elements (`uses_elements: true` in `cost-plan.json`).

## Totals

- **Total shot count:** 8
- **Total generated seconds:** 48 s
- **Total generation cost:** $10.752 (rounded **$10.75**)

For comparison: with elements and audio ON the same 48 s would be 48 x $0.336 = $16.128 (rounded $16.13); without elements and audio ON it would be 48 x $0.168 = $8.064 (rounded $8.06) — the R2 figure; without elements and audio OFF it would be 48 x $0.112 = $5.376 (rounded $5.38) — the superseded preflight figure. Audio is OFF and elements are ON in this round, so the $10.75 figure applies.

## Keyframe generation cost (separate)

- **Billed cost: $0.** Keyframes (8) and character references (5 views) are generated with the platform built-in image generation, which is not a billed provider charge in this environment. Recorded as $0 billed / not-applicable rather than an invented number. None has been generated yet — all are pending script approval.

## Retry budget (separate)

- **Rule:** one retry per failed shot, at that shot's own cost ($1.344 per 6 s shot). A retry is a new paid generation; a failed generation may still be charged if GPU time was spent (provider-documented 422 behaviour). Server errors (HTTP 500+) are never charged.
- **Maximum retry budget:** $10.752 (rounded **$10.75**, all 8 shots retried once)
- **Worst-case total (generation + full retry budget):** $10.752 + $10.752 = $21.504 (rounded **$21.50**)
- No second retry is budgeted without a new approval.

## Other charges

- **Upload / storage:** no upload or storage charge is stated for this endpoint's pricing; outputs are downloaded to the delivery folder. UNCONFIRMED as a separate line item — none is listed on the pricing page read.
- **Taxes / fees:** UNCONFIRMED — no tax or fee is stated on the pricing page read.

## Charging rules (provider-documented)

- Server errors (HTTP 500+) are never charged; queue-wait time is never charged; a 422 may be charged if GPU time was spent. A failed generation after GPU time may therefore cost up to its clip price ($1.344 per 6 s clip) even when it produces no usable video.
- Payment: from the user's prepaid fal.ai credits, charged by the provider at generation time. No credential is stored in this repo.
