# GATE A — Story and Visual Plan Approval checklist

Work order CF-WO-P1-006-R2-PREFLIGHT, branch
`feat/cf-p1-004-universal-production-brain`, PR #5 (open, Draft,
unmerged). Production: "Nadia and the River Light"
(p1006-r2-photorealistic-image-to-video).

**This gate is the owner's review of the story and the visual
plan. Nothing in this checklist is approved.** Every item below
is an unchecked checkbox with its evidence path. The owner
checks an item only after reading the evidence. Until Gate A
passes, no reference image, no keyframe, no voice recording, and
no paid provider call is generated from this script.

Related gates: Gate B (paid provider generation authorization)
is a SEPARATE approval —
`docs/implementation/CF-WO-P1-006-R2-PREFLIGHT-gate-b-authorization.md`.
Gate A passing does NOT authorize any paid call. Both gates are
required before any paid generation runs, and neither may be
inferred from the other.

## Checklist

- [ ] **The complete script** — 8 narration lines, "Nadia and
  the River Light", narrator-only, en-US. Evidence:
  `examples/p1006-r2-photorealistic-image-to-video/script.md`.
  The script is a DRAFT; its story and narration lines are
  approved or changed here, not after generation starts.
- [ ] **The script breakdown** — line-by-line analysis:
  locations, environments, actions, physical events, props,
  emotional reactions, narrative developments. Evidence:
  `examples/p1006-r2-photorealistic-image-to-video/script-breakdown.md`.
- [ ] **Story coverage report** — every story beat mapped to its
  shot(s); considered-and-rejected candidates with reasons; no
  PROPOSED shot (no genuinely missing beat was found); the s2
  lantern-continuity correction recorded. Evidence:
  `examples/p1006-r2-photorealistic-image-to-video/story-coverage-report.json`.
- [ ] **Location coverage** — rooftop terrace, river (stone steps
  + water's edge), market street: establishing, wide environment,
  arrival, movement through, objects / spatial relationships,
  detail shots, reaction shots, closing / departure. Evidence:
  `examples/p1006-r2-photorealistic-image-to-video/location-coverage.json`.
- [ ] **Dynamic scene / shot count** — 6 scenes (SC1–SC6),
  8 shots (s1, s2, s3a, s3b, s4, s5, s6a, s6b), 8 keyframes,
  8 clips, 48 s total. Counts are derived from the story, not
  fixed in advance; no shot was added and none was removed vs
  the R2 draft. Evidence:
  `examples/p1006-r2-photorealistic-image-to-video/scene-breakdown.json`
  and `shot-duration-plan.json`.
- [ ] **Character Bible** — Nadia, DEMO-CHAR-002, fictional
  project-local adult, 27, photorealistic digital human; fixed
  structure (oval face, dark brown eyes of natural size, long
  straight black hair with centre part, warm medium-brown skin
  with natural texture), one fixed outfit (rust-orange linen
  shirt #B4552A, dark indigo jeans, brown leather sandals),
  brass bangle on the LEFT wrist, gold hoop earrings; three
  distinct lantern props, not one continuous prop. Evidence:
  `examples/p1006-r2-photorealistic-image-to-video/character-bible.json`.
- [ ] **Character-reference image plan** — 5 views, all pending
  generation after script approval: front (`ref-nadia-front`),
  three-quarter (`ref-nadia-three-quarter`), side
  (`ref-nadia-side`), full-body (`ref-nadia-full-body`),
  expression sheet (`ref-nadia-expressions`). The front reference
  is generated first; the rest are chained from it. Evidence:
  `examples/p1006-r2-photorealistic-image-to-video/character-bible.json`
  (`references`) and
  `examples/p1006-r2-photorealistic-image-to-video/character-appearance-map.json`.
- [ ] **Character appearance map** — Nadia's appearance in every
  shot: framing, expression, outfit state (including the damp
  state in s5), hair state, props held. Evidence:
  `examples/p1006-r2-photorealistic-image-to-video/character-appearance-map.json`.
- [ ] **Photorealistic style** — photorealistic digital human
  only: natural skin texture, realistic eyes and face, natural
  hair, plausible clothing and fabric, realistic proportions,
  natural light and shadows. Cartoon / anime / illustration /
  stylized 3D / plastic-smooth skin / oversized eyes are all
  rejected. Evidence: the style lock in every shot's
  `prompt_record` in
  `examples/p1006-r2-photorealistic-image-to-video/shot-list.json`
  and in
  `examples/p1006-r2-photorealistic-image-to-video/motion-prompts.md`.
- [ ] **Motion prompts** — one structured prompt record per shot:
  source script segment, scene keyframe reference, character
  element references (frontal @Element1 + angle references),
  environment, action, body / facial / hand-object / hair-cloth /
  environmental / camera movement, physical realism constraints,
  expected duration. Evidence:
  `examples/p1006-r2-photorealistic-image-to-video/motion-prompts.md`
  and the `prompt_record` in
  `examples/p1006-r2-photorealistic-image-to-video/shot-list.json`.
- [ ] **Negative prompts** — every shot prohibits cartoon, anime,
  illustration, stylized rendering, plastic skin, oversized eyes,
  distorted faces, extra fingers, morphing, outfit/hair changes,
  a second character, and all on-screen text. Evidence: the
  `negative_prompt` in every shot's `prompt_record` in
  `examples/p1006-r2-photorealistic-image-to-video/shot-list.json`.
- [ ] **No-text policy** — no on-screen text, captions,
  subtitles, keywords, labels, logos, watermarks, decorative
  typography, title cards, or end cards in any shot; all six
  text-overlay flags are false in the project policy and in
  every shot record; `generate_audio: false` for every shot.
  Evidence:
  `examples/p1006-r2-photorealistic-image-to-video/project.json`
  (`text_overlay_policy`) and
  `examples/p1006-r2-photorealistic-image-to-video/shot-list.json`.
- [ ] **Shot duration plan** — 6 s per shot (provider enum "6",
  range "3"–"15"), 48 s total, inside the 30–60 s target; every
  narration line fits inside its 6 s shot. Evidence:
  `examples/p1006-r2-photorealistic-image-to-video/shot-duration-plan.json`.
- [ ] **Cost plan (for awareness; approval of the spend is Gate
  B)** — 8 shots x 6 s x $0.224/s (audio OFF, WITH elements —
  every shot carries the Nadia character element) = $10.75
  (exact $10.752); keyframe
  generation $0 billed; retry budget one retry per failed shot,
  maximum $10.75; worst case $21.50; taxes/fees UNCONFIRMED.
  Evidence:
  `examples/p1006-r2-photorealistic-image-to-video/cost-plan.json`
  and `cost-plan.md`.
- [ ] **Retention / privacy assessment (for awareness; acceptance
  of the public-by-link limitation is Gate B)** — inputs are
  base64 data URIs to `queue.fal.run`; request-history payload
  storage disabled by header; outputs are public-by-link on GCS
  and cannot be restricted by fal ACL; ZDR UNCONFIRMED; the
  generation operation is BLOCKED until the owner accepts
  public-by-link outputs. Evidence:
  `docs/implementation/CF-WO-P1-006-R2-PREFLIGHT-retention-assessment.md`.

## Decision

- [ ] GATE A APPROVED — the script, breakdown, location coverage,
  scene/shot count, Character Bible, reference plan, style,
  motion prompts, negative prompts, and no-text policy are
  approved as written. Reference images, keyframes, and voice
  recordings may now be generated from the approved script.
- [ ] GATE A NOT APPROVED — changes required (list them; the
  script + breakdown must be re-approved after the change).
