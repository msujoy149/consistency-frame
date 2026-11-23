# Consistency Frame — agent instructions

This repository is a portable system for making videos with consistent
characters and voices that feel human-made. The skills in `skills/` are
the source of truth. Read them and follow them; do not invent your own
versions of these rules.

Consistency Frame is **animation-first and style-agnostic**: it directs
consistent, expressive, physically believable animated videos across
2D, 3D, stylized, semi-realistic, and photorealistic styles — for
humans, digital humans, animals, creatures, multi-character
interactions, image-to-video, video-to-video, and hybrid
live-action/VFX work. Visual style, production medium, source-media
type, and motion-generation method are independent dimensions, chosen
per production. The authoritative reference is
`docs/architecture/ANIMATION_SCOPE_AND_PRODUCTION_MODES.md` — it
defines the fixed vocabularies and the composable routing model, and
it governs wherever an older document disagrees (for example, any
cartoon-only framing, or any claim that a realistic-person video is
"not animation"). It is not a cartoon-only toolkit, not a standalone
video-generation server, API backend, or cloud database, and not a
VoiceStudio/OpenMontage replacement.

## Command authority

This repo is the command master: for every video, read and use the
repo's skills first — a skill that exists in the repo is used, never
reinvented. If a needed skill is not in the repo, check the repo's
comments and notes about that topic first and follow them; only if the
repo gives no comment, generate the system yourself in the repo's skill
format, save it as a new skill, and tell the user plainly what was added
and why — and the skill is written and saved FIRST, before any video is
generated from it (the skill-first loop, command-authority §9), so no
video is ever improvised. For a new kind of task, the repo gives one distilled common core
instead of hunting for a skill (see the `command-authority` skill, §8);
when the repo has no instruction at all it says "do it yourself" — never
bare, always with the quality commands (correct, cinematic,
human-generated, per the need and the script) and the main flow (the
step-by-step order for every video, in §7).

## Skills (source of truth)

- `skills/character-consistency/` — character registry, identity
  resolution, prompt builder, reference fidelity, character recall,
  multi-character scenes.
- `skills/voice-consistency/` — voice profiles, VoiceStudio/OmniVoice,
  single-pass dialogue, voice drift, code-switching.
- `skills/humanized-production/` — the 36 humanization systems
  (performance, micro-motion, sound, editing, film finish, backgrounds).
- `skills/production-systems/` — the 12 professional + 18 extended + 7
  additional systems, plus language, captions, and format rules.
- `skills/agency-advertising/` — brand kit, ad formats, campaign
  variants, client isolation, AI disclosure, product consistency,
  client approval.
- `skills/video-regeneration/` — reference analysis, new-not-duplicate
  remake, character/object continuity, physical interactions,
  cinematography, storyboard, audio, QC, output requirements.
- `skills/cinematic-power/` — style lock, animal and creature
  performance, music-beat editing and synchronized ensemble, trailer
  structure, scale and colour scripting.
- `skills/live-action-vfx/` — live-action human performance, VFX
  integration of CG creatures in live footage, water, wetness and
  underwater continuity, practical locations and set extension,
  live-action stunt and action choreography, real-animal performance.
- `skills/emotional-performance/` — musical performance and
  stagecraft, crowd as a living character, intimate drama and
  emotional arc, age performance, instrument performance sync, music
  as story and memory, cultural authenticity and object storytelling.
- `skills/resource-management/` — load only what the phase needs:
  voice plugin for voice work, video plugin for video assembly,
  working memory for the current phase; stop rules and the quality
  guard.
- `skills/language-authenticity/` — every language spoken the way its
  native speakers speak it (US English, Bengali, Hindi); the same video
  in every language asked for, separately on request; one voice across
  languages; lip-sync matched to the language's sounds.
- `skills/realistic-person/` — a real person's photo becomes a
  photorealistic digital-human animation: a realistic moving,
  speaking person whose face never changes, whose movement and
  speech are natural, and whose lip-sync follows the language's
  sounds. This IS animation (a generated digital human, not
  live-action footage of a real shoot).
- `skills/explainer-animation/` — 2D flat cartoon / stick-figure explainer
  that teaches one idea through simple scenes and visual metaphors: flat
  2D vector, thick black outlines, small palette, two character designs
  kept apart, one idea per scene, almost no on-screen text. This is one
  optional profile of the system, not the product's animation model.
- `skills/command-authority/` — the repo is the command master: read and
  use the repo's skills first for every video; a missing system is
  generated only after checking the repo's notes, then saved as a new
  skill and reported to the user.
- `skills/kids-family-animation/` — professional kids & family animation:
  short-form videos for children and young audiences across 14 animation
  methods, one locked visual style, a full camera decision system, 3D and
  2D craft, ten story templates, short-form structure, animation QC, and
  a permanent reference library.

## P0 safe foundations (v2.3, branch `feat/cf-p0-safe-foundations`)

- Install is non-destructive: `scripts/sync-skills.sh` syncs only
  manifest-owned skill files; unmanaged skills are never deleted.
  `setup.sh` is core-only by default; components are opt-in
  (`--with-components`) and report SUCCESS/PARTIAL/FAILED honestly.
- Canonical records live in `registry/` (generated by
  `scripts/generate-registries.py`) and `schemas/`; counts are derived,
  not typed by hand. Validate with `python3 scripts/validate-repo.py`.
- Skill-first loop (§9): a missing system is drafted task-locally
  first; it becomes a permanent canonical skill only on the user's
  explicit authorisation.
- Loudness is a delivery profile (`architecture/audio-delivery-profiles.json`,
  `docs/19-audio-delivery-profiles.md`), never one universal target.
- Quality targets are measurable and scoped, verified shot by shot
  with a human-review gate — never an absolute percentage.

## v2.4 Brain Architecture Amendment (2026-11-22, user voice call)

- Consistency Frame is the CENTRAL BRAIN / Orchestrator of the video
  production ecosystem — creative intelligence, script understanding,
  skill routing, character/project continuity, emotion/performance
  direction, cinematography/editing decisions, quality requirements,
  production coordination, documentation/learning governance.
- It is NOT a standalone video-generation server, audio-generation
  server, API backend, cloud database, or hosting platform, and it is
  not a replacement for the companion repos. No such component exists
  in this repo and none is to be built (see
  `docs/implementation/BRAIN_ARCHITECTURE_AUDIT.md`).
- Three-repo model: (A) this repo = Brain; (B) VoiceStudio =
  Voice/Speech Specialist; (C) OpenMontage = Video Production/Editing
  Specialist. The Brain directs the companions by instruction; it never
  silently modifies or replaces their internal code. Verified
  capabilities only — see
  `architecture/COMPANION_CAPABILITY_REGISTRY.yaml`.
- Intelligent skill routing is canonical data, not improvisation:
  `architecture/SKILL_ROUTING_MATRIX.yaml` (per-skill trigger,
  non-trigger, inputs, outputs, dependencies, precedence, conflicts,
  modes, quality gate, approval conditions) and
  `architecture/WORKFLOW_GRAPH.yaml` (sequential on dependency,
  parallel only when safe, acyclic). Never arbitrarily select skills
  or ignore relevant ones.
- Script-to-Performance Intelligence: a script is analysed at
  scene/beat/dialogue-line level into machine-readable Scene, Shot and
  Performance Plans (`schemas/scene-plan.json`, `schemas/shot-plan.json`,
  `schemas/performance-plan.json`, combined in
  `schemas/script-to-performance.json`). The user's original dialogue is
  preserved verbatim unless rewriting was explicitly requested.
- Modes: ONE-OFF (supplied assets temporary, no permanent record) vs
  RECURRING PROJECT/SERIES (stable IDs across tools and episodes;
  permanent registration and canonical learning only on explicit
  authorisation). Mapping to the asset modes is in
  `docs/implementation/BRAIN_ARCHITECTURE_AUDIT.md` §4.
- Agent portability: one canonical Brain source; thin adapters plus a
  verified compatibility matrix
  (`architecture/AGENT_COMPATIBILITY_MATRIX.yaml`). Only Muse is
  verified (knowledge-pack path). OpenRouter is a model-routing layer,
  not an agent host. Colab needs an appropriate Notebook/Agent Runtime.

## P0-006 Animation-first, style-agnostic production architecture (2026-11-22, complete)

- Animation is NOT cartoon-only: 2D, anime, stylized 3D,
  semi-realistic, photorealistic CGI, digital humans, animals,
  creatures, image-to-video, video-to-video, and hybrid
  live-action/VFX are all first-class productions of the same system.
  A photorealistic digital-human video IS animation.
- Visual style, production medium, source-media type, and
  motion-generation method are independent, composable dimensions —
  never one giant `animation_type` enum. The fixed vocabularies and
  the full scope live in
  `docs/architecture/ANIMATION_SCOPE_AND_PRODUCTION_MODES.md`, which
  governs wherever an older document disagrees.
- Skill routing is composable: one primary pathway + style profiles +
  subject capabilities + compatible layers, with true conflicts only.
  The old one-video-type-per-video mutual exclusion is withdrawn.
  (The routing data files that encode this —
  `architecture/SKILL_ROUTING_MATRIX.yaml` and
  `architecture/WORKFLOW_GRAPH.yaml` — are updated by the P0-006
  architecture part; until then, no routing claim in them that
  contradicts the canonical document is to be relied on.)
- Reference video is OPTIONAL (Path A reference-video-assisted vs
  Path B script-and-image-driven); never invent a reference video or
  claim one was analysed when none was supplied.
- Character registration is optional and explicit: first-run
  invitation (register now / skip and use temporarily / register
  later); skipping never prevents creating a video; an upload is
  never silently converted into a permanent registration. Private
  character and voice data stays in the private overlay, never in
  this public repo; voice isolation is owner/workspace-scoped.
- P0 defines contracts (production profile, character registration,
  voice profile, scene/shot/performance, script-to-performance,
  timeline manifest — schema version 2.5, additive only). The
  runtimes that execute them — routing engine, script-to-performance
  runtime, provider execution, rendering — are P1 work. No
  capability is marked exercised or production-verified without
  actual evidence.
- No new skill is added in P0-006 (see the corrections record):
  the animation scope is a routing/profile layer over the existing
  15 skills, not a new technique skill.

## P0-007 Final autonomous completion (2026-11-22, complete)

- **Timeline contract completed.** `schemas/timeline-manifest.json`
  is v2.5 (additive): video-clip + shot bindings, audio-clip +
  dialogue bindings, synchronization groups, and real
  cross-reference validation (`validate_timeline_cross_references`
  in `tests/test_timeline_manifest.py`) — a shot, dialogue line,
  character, voice profile, or audio asset ID must resolve to the
  record it names. Valid v2.3 timelines still pass.
- **Structured ownership enforced.** Character registrations and
  voice profiles carry `ownership` (`owner_id`, `workspace_id`,
  `visibility`, `sharing`) — opaque local IDs, private by default.
  Resolving a voice profile requires BOTH the Character ID +
  Voice Profile binding AND matching ownership; same Character ID
  with a different owner or workspace is REJECTED. The old
  free-text `ownership_scope` is kept only as a deprecated legacy
  field.
- **Conditional v2.5 voice validation.** The repo validator cannot
  express conditional requirements, so the v2.5 voice rules
  (required fields, user-recorded vs AI-generated conditions,
  approval states, consent rules) are enforced by the Python
  validators in `scripts/asset_policy.py`; schema and validators
  must agree on every record. A v2.3 voice profile remains valid
  under the legacy contract.
- **Real animal vs CGI animal fixed.** A speaking bird (Kiki) is
  `cgi-animal`, not `real-animal`; a genuine captured animal is
  never automatically given fictional dialogue or a speaking voice.
  Species matching for articulation is by substring ("African grey
  parrot" maps to bird-beak). A listening line needs no voice
  profile; a speaking line still does.
- **Companion licensing recorded.** OmniVoice model weights are
  CC-BY-NC (non-commercial) — technically capable but NOT approved
  for commercial production; no verified commercial voice provider
  exists, so the commercial voice adapter stays unsupported
  (see `architecture/COMPANION_CAPABILITY_REGISTRY.yaml`).
- P0-007 is a contract + validation correction round: it does not
  build the first-run registration UI, provider execution, or any
  P1 runtime. No capability is marked exercised or
  production-verified without actual evidence.

## P0-008 Fail-closed private voice security (2026-11-22)

- **Requester identity is mandatory.** For a private v2.5 voice,
  `resolve_voice_for_production` (`scripts/asset_policy.py`)
  requires BOTH the requesting owner ID and the requesting
  workspace ID — a missing requester is never an authorized
  internal request, there is no silent fallback to the
  character's owner, and `None` is never an authorization
  bypass. Wrong owner, wrong workspace, cross-character
  assignment, and a voice owned by another owner or workspace
  are all rejected. Legacy v2.3 records keep their historical
  contract.
- **Export needs a trusted context.** A private voice export
  requires a `TrustedAuthorizationContext` issued by
  `issue_trusted_authorization_context` — the local application
  authorization boundary. A caller-created dictionary (including
  a forged `granted_by`) never authorizes anything. The context
  is checked against the voice on every point (actor = owner in
  the voice workspace, issuer = owner, explicit
  `export_private_asset` action, non-empty scope, exact
  character + voice binding, not expired, not revoked). Export
  is owner-only even under `shared` + `workspace`, and provider
  transmission is a separate permission from export. The trusted
  context is a structural (type) boundary, not cryptographic
  proof of identity — the P1 app/session runtime must supply the
  actor identity at the boundary.
- **Timeline validation is production code.** The validator moved
  from `tests/test_timeline_manifest.py` into
  `scripts/timeline_policy.py`, with a strict v2.5 mode
  (`strict=True`) that fails closed on missing registry data,
  missing requester identity, missing ownership, unauthorized
  access, and unapproved voices. Narration, music, ambience, SFX
  and foley timelines stay valid without a requester; valid v2.3
  timelines still pass.
- **One authorization choke point.** Every production access
  decision goes through `authorize_action` in
  `scripts/asset_policy.py`, with explicit action scopes
  (`use_in_project`, `use_in_production`,
  `export_private_asset`, `transmit_to_provider`,
  `share_with_workspace`). Permission for one action never
  implies permission for another, and the duplicate test-only
  authorization logic is gone (tests import the production
  functions).
- **Security regression suite.**
  `tests/test_private_voice_security.py` (`CF-P0-008-SEC`, 74
  checks, all PASS locally) reproduces all three pre-fix
  failures and pins the fixed behaviour. Full record:
  `docs/implementation/CF-WO-P0-008-corrections.md`.
- P0-008 is a policy / validation / tests / documentation round:
  it does not build the first-run registration UI, provider
  execution, the app/session runtime for the trusted boundary,
  lip-sync/articulation generation, or any P1 runtime.

## P0-009 Immutable authorization context & fail-closed resolution (2026-11-23)

- **The authorization context is genuinely immutable.**
  `TrustedAuthorizationContext` (`scripts/asset_policy.py`) freezes
  itself at issuance (`_frozen` flag; `__setattr__`/`__delattr__`
  raise `AttributeError`; no `__dict__`; copy/deepcopy/pickle return
  frozen objects). `__slots__` alone was not enough — the old
  `ctx.revoked = True` mutation no longer works. Revocation is a
  separate registry (`_REVOKED_AUTHORIZATION_IDS`, keyed by the
  immutable per-issuance `authorization_id`) and never mutates the
  issued context. The registry is process-local/in-memory;
  persistence is P1 work.
- **v2.5 voice resolution fails closed without a Character
  Registry.** `resolve_voice_for_production` returns no voice when
  the registry is missing, non-dict, lacks the Character, or the
  Character/Voice ownership does not match. Legacy v2.3 keeps its
  historical contract; v2.5 never silently falls back to it.
- **Timeline validation is strict by default.**
  `validate_timeline_cross_references` (`scripts/timeline_policy.py`)
  runs full strict v2.5 checks when the `strict` argument is omitted
  (only an exactly-`"2.3"` manifest keeps its legacy structural
  contract). Structural-only validation is the explicitly named
  `validate_timeline_structural()` and its result is never
  authorization for a v2.5 Timeline.
- **Voice Profile ownership is bound to its Character in timeline
  validation.** A voice linked to a Character with different
  ownership is rejected even when both assets are `shared` /
  `workspace` and individually authorized to the requester.
- **P0-008 provenance corrected.** The delivered P0-008 Bengali
  report's §8 had recorded the stale P0-007 hash; the correct
  P0-008 `tests/last-run.json` SHA-256 was verified from both the
  local file and the downloaded CI artifact, and the report file +
  its ZIP were corrected and rebuilt. Full record:
  `docs/implementation/CF-WO-P0-009-corrections.md`.
- P0-009 hardens contracts, authorization logic, validation APIs,
  tests, and provenance only. It does not build an authenticated
  end-user app session, provider execution, or any P1 runtime, and
  the P0 contract alone does not stop a malicious process running
  with the same local OS user privileges from manipulating files
  or code.

## Rules that always apply

- A character's identity (face, eyes, nose, mouth, hands, feet) is
  fixed across every scene. Clothing and props change with the scene.
- A character's voice (tags + seed + reference audio) is fixed across
  every episode.
- The user's explicit instructions and script outrank everything else.
- Character data is private by default. Never commit reference images,
  voice recordings, or personal data to this public repo. Character
  data lives in a separate private overlay (see
  `characters/README.md`).
- Never claim a check you did not perform. Run the QC checklist
  (`skills/production-systems/`) before delivering.

## Docs

Full system documentation lives in `docs/`. The core systems are in
`docs/01-production-systems.md`, `docs/02-extended-systems.md`,
`docs/03-language-captions-format.md`, `docs/04-additional-systems.md`,
and `docs/05-humanization-systems.md`. Install instructions are in
`docs/06-installation.md`. The character registry is documented in
`docs/07-character-registry.md`, and the advertising layer in
`docs/08-agency-advertising.md`, and video regeneration in
`docs/09-video-regeneration.md`, and cinematic power in
`docs/10-cinematic-power.md`, and live-action and VFX in
`docs/11-live-action-vfx.md`, and emotional performance in
`docs/12-emotional-performance.md`, and on-demand resources in
`docs/13-resource-management.md`, and language authenticity in
`docs/14-language-authenticity.md`, and realistic person video in
`docs/15-realistic-person.md`, and 2D explainer animation in
`docs/16-explainer-animation.md`, and command authority in
`docs/17-command-authority.md`, and kids & family animation in
`docs/18-kids-family-animation.md`, and audio delivery profiles in
`docs/19-audio-delivery-profiles.md`. The animation scope — what
animation means here, the fixed vocabularies, composable routing,
consent and QC rules, and Addendum C — is in
`docs/architecture/ANIMATION_SCOPE_AND_PRODUCTION_MODES.md`, and the
P0-006 corrections record is in
`docs/implementation/CF-WO-P0-006-corrections.md`.
