# Agency Advertising

This document describes the advertising layer of Consistency Frame: how a registered AI-generated model is used as an agency spokesperson across advertising campaigns. The full rules are in the `agency-advertising` skill (`skills/agency-advertising/SKILL.md`); this document explains each system in full.

The model is a synthetic person with no real existence. It is introduced once — registered as a character through the Character Generator (`docs/07-character-registry.md`, "Character Generator — Two Ways to Create a Character", option 2: AI-generated, shown first, permanent only on explicit "done" approval) — and then used across every ad for a business's services, with the same face, the same voice, and the same brand in each one.

Nothing in this layer replaces the character system. Registration, 100% reference fidelity, identity anchoring, face-consistency correction, angle-matched verification, and the expression library all still apply, unchanged, to every ad. The seven systems below add only the advertising layer on top.

Counting note: these 7 systems are part of the repo total. Together with the 11 professional, 18 extended, 3 language/captions/format, 7 additional, and 36 humanization systems, the repo holds 82 distinct systems, presented as 93 numbered entries.

## Folder layout

Advertising work lives in per-client workspaces, in the private overlay — never in the public repository:

```text
clients/
  <client-id>/
    models/
      <agency-model-id>/        # the registered character folder
                                # (see docs/07-character-registry.md)
    brands/
      <brand-kit-id>/
        brand-kit.yaml          # logo, colours, tagline, fonts,
                                # model ID, voice tone profile
        logo.png                # brand logo (private overlay only)
    campaigns/
      <campaign-id>/
        brief.md                # locked product shots, wording,
                                # prices, claims for the campaign
        master/                 # the master ad (all formats)
        variants/
          <ad-variant-id>/      # one variant: what changed, platform,
                                # master it came from
        approvals.md            # approval record per version
```

Character data and client data are private by default. No model images, brand logos, voice recordings, or client data are ever committed to the public repository.

## 1. Brand Kit — One Kit, One Brand

The model and the brand's assets are locked together in one brand kit. The kit is the single source of truth for every ad of that brand.

Each brand has one kit, recorded as `brand-kit.yaml`:

```yaml
brand_kit_id: <brand-kit-id>
client_id: <client-id>
model_id: <agency-model-id>     # the registered spokesperson character
logo: logo.png                  # brand logo file (private overlay)
colours:
  primary: "#000000"
  accent: "#000000"
tagline: "<brand-tagline>"       # exact wording
fonts:
  heading: "<font-name>"
  body: "<font-name>"
voice_tone: persuasive          # persuasive / energetic / warm / as directed
```

- Every ad generation reads the kit first. Logo, colours, tagline, and fonts come from the kit — never restyled, recoloured, or reworded per ad, and never improvised.
- One kit per brand. A model may serve more than one brand only with a separate kit per brand — and if two brands compete, flag the conflict to the user before generating anything.
- A change to the kit (new tagline, new colours) is a deliberate, recorded change: note what changed, when, and who asked. Old ads keep the old kit; new ads use the new one. Never silently update a published ad to match a changed kit.

The voice tone profile is performance direction for advertising. The model's base voice (tags + seed + reference audio) stays fixed, exactly as the voice-consistency skill requires; the tone profile says how that voice performs in ads.

## 2. Ad Formats — Built for the Platform, Not Cropped

Every ad is composed for its platform's format from the start — never cropped afterwards.

| Format | Platforms | Notes |
| --- | --- | --- |
| 9:16 | Reels / Shorts / TikTok | Vertical, full-screen |
| 1:1 | Feed posts | Square |
| 16:9 | YouTube and other wide placements | Wide |

Any other ratio the platform asks for is composed for that ratio from the start, the same way.

Each ad, in every format, has three parts:

1. **Hook in the first 3 seconds.** The model states the value, the offer, or the question immediately. No slow open, no logo-only cold start — a viewer who scrolls past in three seconds has still heard the point.
2. **The service, shown by the model.** The model presents the service or product (Section 6), in the brand kit's colours, with the model's face and voice consistent throughout.
3. **A clear call to action (CTA) at the end.** One action, in words and on screen — matching the campaign's CTA exactly (Section 3).

**Safe zones.** Keep the model's face, the logo, the tagline, and the CTA clear of each platform's UI overlays (top bar, bottom buttons, caption area, side icons). Check the safe zone per format before delivery — a CTA hidden behind a platform button is a failed ad.

## 3. Campaign Variants — One Master, Many Cut-Downs

A campaign is one master ad, cut down and varied — never a set of unrelated ads.

- **Cut-downs.** One master ad produces 6-second, 15-second, and 30-second versions. Every cut-down uses the same model, the same voice, the same brand kit, the same product shots, and the same claims as the master. A cut-down is a shorter telling of the same ad, not a different ad.
- **A/B variants.** Variants change ONE thing at a time — a different hook OR a different CTA, never both at once — so the result stays readable. If hook A beats hook B, the campaign knows why.
- **Tracking.** Every variant gets a variant ID (`<ad-variant-id>`) and a record of what changed, which platform it is for, and which master it came from. A 9:16 hook-A cut is never delivered as a 16:9 hook-B cut, and a variant is never published under another variant's ID.
- **Verification.** The master and all its cut-downs are verified against the same reference (docs/07, "Identity Anchoring" and "Reference Matching and Angle-Matched Verification") and the same brand kit (Section 1) before any of them is delivered.

## 4. Client Isolation — One Client, One Workspace

An agency serves many clients. Each client's work lives in that client's workspace only, and one client's assets must NEVER appear in another client's ad.

- **Check before every generation.** Before generating anything for a client, verify that the model ID, the brand kit ID, and the voice ID all belong to that client's workspace. If any asset belongs to another client, STOP — do not generate, do not substitute, ask the user.
- **No casual reuse.** Never reuse one client's model, brand kit, voice, or ad assets in another client's ad — even if the user asks casually. If reuse is genuinely wanted, the user must confirm it explicitly, and the reuse is recorded with the confirmation.
- **Separate records.** Campaign records, approval records, and variant tracking are per client. A search for a client's assets must never return another client's work.
- **Private by default.** Client workspaces live in the private overlay, like character data (docs/07, "Private Overlay Design"). Client models, brand kits, voices, and ad assets are never committed to the public repository.

## 5. AI Disclosure and Likeness Safety

The spokesperson is a synthetic person. That fact is disclosed, every time, everywhere it is required — and the model's face must never be a real person's face.

- **Platform disclosure.** Every ad carries the AI-generated disclosure each platform requires: YouTube's AI-content disclosure setting, Meta's AI-generated labelling, and any equivalent label on the platform where the ad runs. Set the disclosure at publish time. Never publish an ad without it.
- **Likeness check at registration.** When the model is created and approved (docs/07, "Character Generator"), check that the generated face does not resemble any real person. Re-check whenever the face drifts, is regenerated, or is revised. If a generated face starts to resemble a real person, stop and regenerate — do not use it.
- **Never remove the traces.** NEVER remove AI watermarks, provenance (SynthID / C2PA), or any other AI-origin trace to deceive a platform or a viewer. If a platform detects the ad as AI-made, that is the system working, not a defect to hide.
- **Tell the client.** The client is told, before approving (Section 7), that the spokesperson is AI-generated. Approval of an ad is approval with that knowledge.

## 6. Product and Service Consistency

Whatever the model presents — a service, a product, a price, an offer — stays visually and factually identical across every ad in a campaign.

- **Lock it per campaign.** Each campaign locks its product/service shots (the exact images or renders used), the exact wording, the prices, and the claims, in the campaign record (`campaigns/<campaign-id>/brief.md`). The lock is made once, before the first ad of the campaign is generated.
- **Same presentation, every ad.** The model presents the same service the same way in the master and in every cut-down and variant: same product shots, same wording, same prices, same claims. A price in the 6-second cut is the price in the 30-second master.
- **Changes make a new version.** A price change, a wording change, or a new claim creates a new campaign version — never a silent edit to a published ad, and never a different price in one variant than in another. The old version's ads are withdrawn or re-approved (Section 7) before the new version runs.
- **Verify before publishing.** Compare the product shot, wording, price, and claims in the finished ad against the campaign lock, word for word, before the ad goes to the client (Section 7).

## 7. Client Approval Workflow — Draft, Review, Approve, Publish

No ad is published before the client approves it. The workflow has four states, in order:

1. **Draft.** The ad is generated and checked internally (Sections 1–6). A draft is never published and never shown to the public.
2. **Client review.** The client reviews the actual ad — the video, the captions, and the disclosure — not a description of it. The client sees the AI-generated nature of the spokesperson (Section 5) as part of the review.
3. **Approved.** The client approves a specific version. The approval is recorded per version: who approved, when, and which version.
4. **Publish.** Only the approved version is published, with the platform disclosure set (Section 5).

Rules:

- **Every revision is a new draft version** (v1, v2, v3, …). A change after approval voids the approval — the ad goes back to client review and must be approved again.
- **An approval covers exactly one version.** Approving v2 does not approve v3.
- **Publish only the approved version.** Never publish a draft, never publish a superseded version, and never publish a version the client has not seen.

Approval record example (`campaigns/<campaign-id>/approvals.md`):

```text
<ad-variant-id> v1 — sent for review <date>
<ad-variant-id> v1 — APPROVED by <client-name> on <date>
<ad-variant-id> v2 — draft (CTA changed); v1 approval void
<ad-variant-id> v2 — APPROVED by <client-name> on <date>
<ad-variant-id> v2 — PUBLISHED on <platform> on <date>, disclosure set
```
