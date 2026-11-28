# Retention / privacy assessment — CF-WO-P1-006-R2-PREFLIGHT

Work order CF-WO-P1-006-R2-PREFLIGHT, branch
`feat/cf-p1-004-universal-production-brain`, PR #5 (open, Draft,
unmerged). Production: "Nadia and the River Light"
(p1006-r2-photorealistic-image-to-video). Provider: fal.ai, model
Kling Video v3 Pro image-to-video,
`fal-ai/kling-video/v3/pro/image-to-video`, endpoint
`POST https://queue.fal.run/fal-ai/kling-video/v3/pro/image-to-video`.

Sources: the revalidated official facts supplied with this work
order (verified from live fal.ai pages 2026-11-28) and the
provider record in `runtime/media_adapters.py`
(`provider-fal-video`). No paid call has been made; no credential
was read or used. Where a fact could not be confirmed from those
sources it is marked UNCONFIRMED, not filled in.

## Item-by-item assessment

- **What input image data is sent:** one keyframe per shot as a
  base64 data URI (`start_image_url`), 8 keyframes total — plus
  character element reference images as URLs once generated
  (frontal `ref-nadia-front` as `frontal_image_url` + 1–3 angle
  references as `reference_image_urls`, prompt reference
  `@Element1`/`@Element2`). No real person's face is sent: the
  character is Nadia (DEMO-CHAR-002), a fictional project-local
  adult; no registered character reference and no private user
  character data is transmitted. The motion prompt text for each
  shot is also transmitted (it is the generation instruction).
  No voice sample is transmitted in this request (narration is
  generated separately and locally).
- **Which host receives the input:** `https://queue.fal.run`
  (fal.ai Model APIs queue), over HTTPS, authenticated with the
  allow-listed key supplied at run time. No other host receives
  the input images.
- **Whether input uploads are public or restricted:** inputs are
  sent as base64 data URIs inside the request body — they are
  NOT uploaded to the CDN first, so there is no public upload
  URL for an input image. This is distinct from SDK-style
  uploads, where a file is first uploaded to fal storage and
  given a URL: this production does not do that. Restriction of
  the transmitted payload itself depends on the request-history
  and logging behaviour below, not on a public/private upload
  flag.
- **Whether request history is disabled:** every request carries
  `X-Fal-Store-IO: 0`, which disables request-history payload
  storage. Scope limit: that header disables the stored
  request-history payload only — it does NOT equal zero data
  retention, and it does NOT disable application logging (see
  below). Request payloads are otherwise retained 90 days by
  default.
- **How uploaded images are retained:** the transmitted keyframe
  (base64 data URI in the request body) falls under the request
  payload: retained 90 days by default, not stored when
  `X-Fal-Store-IO: 0` is sent. No separate uploaded-image
  retention applies because no input image is uploaded to
  storage first.
- **How generated clips are retained:** generated clips for THIS
  endpoint land on Google Cloud Storage — the model page's own
  output example is
  `https://storage.googleapis.com/falserverless/example_outputs/kling-v3/pro-i2v/out.mp4`
  — NOT on the fal CDN. The fal CDN lifecycle
  (`X-Fal-Object-Lifecycle-Preference`, expiration 7 days) does
  NOT apply to GCS outputs. No GCS retention period for these
  outputs was confirmed from the sources above: **UNCONFIRMED**.
  The older R2 record of "fal.media outputs kept at least 7
  days" describes fal CDN outputs, not this endpoint's GCS
  outputs, and must not be quoted as the retention for these
  clips.
- **Whether generated outputs are publicly accessible:** YES —
  plainly stated: GCS outputs are public-by-link. Anyone with
  the output URL can fetch the clip; there is no per-URL
  password, signed-URL expiry, or access list on it.
- **Whether the output host is covered by fal ACL:** NO. The fal
  CDN access control (`X-Fal-Object-Lifecycle-Preference`,
  `initial_acl`) applies ONLY to fal CDN v3 URLs
  (`https://v3b.fal.media/...`). It does NOT protect a GCS
  output URL. A GCS output cannot be restricted by any fal ACL
  setting.
- **Whether provider logs may retain content:** YES. Application
  logging is not disabled by the `X-Fal-Store-IO: 0` header or
  by the lifecycle/ACL headers. The provider's application logs
  may retain request content (including prompts and references
  to the transmitted images) under its own logging retention,
  which was not confirmed from the sources above.
- **Whether zero data retention (ZDR) is available and
  confirmed:** UNCONFIRMED. ZDR is NOT enabled by default for
  this endpoint, requires sales-team confirmation, is NOT a
  single setting, and does NOT disable application logging. No
  ZDR confirmation exists for this endpoint, and none is claimed
  here.

## Verdict: generation operation BLOCKED on privacy grounds

**BLOCKED.** The outputs of this endpoint are public-by-link on
GCS (`storage.googleapis.com/falserverless/...`) and cannot be
restricted by the fal CDN ACL, which covers fal CDN v3 URLs
only. That limitation cannot be fixed by a header, a setting, or
a different request shape in this round. The owner must
explicitly accept public-by-link outputs — i.e. accept that
anyone with a clip URL can fetch it — or the generation
operation stays BLOCKED. This is recorded here rather than
hidden: Gate B carries the same limitation, and no paid
generation may run until the owner accepts it in writing there.

The input side is less exposed (fictional character only, no
real face, base64 data-URI transmission, request-history payload
storage disabled by header), but the input-side measures do not
change the output-side verdict: the clips themselves would be
public by link.
