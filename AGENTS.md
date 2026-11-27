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

## P0-010 Factory-issued authorization contexts (2026-11-23)

- **Only the exact factory-issued object is trusted.**
  `TrustedAuthorizationContext` (`scripts/asset_policy.py`) is
  still genuinely immutable (P0-009), but immutability never
  proved issuance: the constructor sentinel could be imported,
  `__setstate__` could initialize a `__new__` object, and
  pickle/copy produced further objects that all passed the old
  `isinstance` check with zero factory calls. The trust anchor
  is now a process-local, identity-based issuance registry
  (`_ISSUED_AUTHORIZATION_CONTEXTS`, a `weakref.WeakSet`):
  registration happens only inside
  `issue_trusted_authorization_context()`, as its last step, and
  the single check `is_factory_issued_trusted_authorization_context()`
  is what every authorization boundary uses — export,
  provider-transmission approval, revocation, and revocation
  checks. Equality and hashing are explicitly identity-based
  (`__eq__` is `is`), so two contexts with identical fields are
  distinct entries. Serialization is refused outright
  (`__getstate__` / `__setstate__` / `__reduce__` /
  `__reduce_ex__` raise `TypeError`); copies are frozen but
  unregistered and have no authority. Full record:
  `docs/implementation/CF-WO-P0-010-corrections.md`.
  P0-011 replaced the WeakSet with an `id()`-keyed dict of weak
  references -- see the P0-011 section below -- because WeakSet
  membership invokes the candidate's `__eq__`/`__hash__` and a
  forged subclass could compare equal to a genuine context.
- **This is a process-level integrity contract, not identity
  proof.** It proves an object was issued by the factory in
  this process; it does not prove the owner/workspace IDs
  supplied to the factory belong to the real person operating
  the application, and it does not stop malicious code running
  with the same process privileges. Authenticated
  application-session identity remains P1 work.

## P0-011 Exact object identity for authorization issuance (2026-11-23)

- **Exact concrete type, not ancestry.** The verifier now
  requires `type(context) is TrustedAuthorizationContext` --
  a subclass instance is rejected before any registry lookup,
  however faithfully it mimics a genuine context.
  `TrustedAuthorizationContext.__init_subclass__` raises
  `TypeError`, so a subclass cannot even be defined -- but
  that prohibition is defence-in-depth only; the verifier
  enforces exact type independently, and a subclass built by
  low-level construction is still rejected.
- **Identity verification, no equality anywhere in the
  registry.** The P0-010 WeakSet was insufficient: set
  membership hashes the candidate and compares with `==`, so
  a forged subclass overriding `__eq__` (always True) and
  `__hash__` (the genuine object's hash) passed with zero
  factory calls -- and a raising `__eq__` made the verifier
  itself raise. The registry is now a plain `dict[int,
  weakref.ref]` keyed by `id()`, values are weak references,
  and the verifier checks `target is context` -- an int-keyed
  lookup plus one `is`, never `==`, never a hash of the
  candidate. An `id()` lookup alone is never proof; the
  stored weak reference must still point at the exact object.
- **Guarded cleanup.** Dead entries are removed by the
  weak-reference callback, and only when the stored value is
  still that exact dead ref -- so a newer registration that
  reuses the same `id()` is never removed. A stale dead entry
  met during verification is pruned and the check fails
  closed.
- **Hostile subclasses are irrelevant.** Always-True
  `__eq__`, raising `__eq__`, genuine-hash `__hash__`,
  constant hash, inconsistent eq/hash, and multiple equal
  subclasses are all rejected without granting authorization,
  mutating or revoking the genuine context, corrupting the
  registry, or raising an unhandled exception. Verification
  never invokes a candidate's `__eq__` or `__hash__`.
- **P0-009 + P0-010 preserved.** Immutability, separate
  revocation, serialization refusal, and copy non-registration
  all stand; revoking one identical-field context never revokes
  another; a forged subclass cannot revoke a genuine context
  or inspect its revocation status via a stolen
  `authorization_id`. Full record:
  `docs/implementation/CF-WO-P0-011-corrections.md`.

## P1-001 Trusted local application session (2026-11-23)

- **The P0 policy finally has an actor.** `runtime/` is the
  first P1 runtime component: first-run installation identity
  (stable opaque owner/workspace IDs in `profile.json` under the
  platform user data root — never in the repo; a corrupt profile
  fails closed and is never silently replaced), process-bound
  `LocalSession` objects (fresh ID per run; only the exact issued
  object is accepted, verified by exact type plus an `id()`-keyed
  weak-reference registry checked with `is`, the P0-011 pattern),
  and an authorization bridge that takes identity ONLY from a
  verified session and delegates every decision to the P0
  `authorize_action` — there is no caller-provided identity
  parameter. Full record:
  `docs/implementation/CF-WO-P1-001-corrections.md`, and the
  trust boundary in
  `docs/runtime/LOCAL_SESSION_AND_TRUST_BOUNDARY.md`.
- **Private voice export is issued, never asserted.** Export
  authorization goes through the P0 factory only, after explicit
  owner approval (a narrow callback — no graphical UI exists),
  bound to the exact Character/Voice IDs with a short finite
  expiry (5 minutes by default, at most 1 hour). Provider
  transmission is a separate permission with its own distinct
  approval. Closing a session revokes the contexts it issued.
- **The boundary is local-OS-user only.** It does not prove who
  operates the application and does not protect against another
  process already controlling the same OS account. No server,
  cloud identity, password, or credential vault exists here, and
  none is to be built as part of this runtime. P0 authorization
  behaviour is unchanged (`tests/test_private_voice_security.py`
  passes unmodified); the runtime adds a caller, not a second
  policy.
- P1-001 does not build a graphical UI, character registration
  UI, voice/video generation, provider calls, the skill routing
  engine, script-to-performance generation, or the
  script-to-finished-video pipeline.

## P1-002 Deterministic runtime skill router (2026-11-25)

- **The router plans; it never generates.** `runtime/skill_router.py`
  is the second P1 runtime component: it resolves skills and builds
  deterministic workflow plans from structured requests, reading
  only the compiled catalog `registry/routing-catalog.json` (built
  by `scripts/generate-routing-catalog.py` from the matrix, graph,
  and intent modes; standard-library only at runtime, PyYAML only
  in the build-time compiler). No provider calls, no companion
  invocation, no media generation, no persistence, no server, no
  LLM classifier, no script-to-performance generation.
- **Dependencies order, they never expand the selection.** A
  dependent is never ready before a prerequisite that is also
  selected, but selecting a skill never forces its dependencies
  into the plan. A dependency that is not selected and does not
  list the mode is recorded in the plan as resolved per mode scope
  — never silently dropped, never invented. Precedence is a
  tie-breaker only, never an exclusion.
- **Conflicts are scoped, never global.** TC-1..TC-10 fire only in
  their documented scope — same subject, same shot, same dialogue
  line. Cross-shot and cross-subject combinations stay allowed, and
  a blocked plan names the rule, the skills, the shot, the subject,
  and the decision required; neither skill is ever silently removed.
  TC-10 fails closed when a speaking subject's anatomy cannot be
  established.
- **Plans need an exact active session.** `build_workflow_plan`
  accepts only an exact `LocalSession` verified by the P1-001
  verifier; identity comes only from the session, and the plan
  records only the session ID. UPLOAD_ONLY and REPORT_UPDATE_ONLY
  never route production work. Full record:
  `docs/implementation/CF-WO-P1-002-corrections.md`, and the
  runtime contract in `docs/runtime/SKILL_ROUTING_RUNTIME.md`.
- **R1 hardening (2026-11-26, same branch and PR #3).** Every
  scope reference must resolve to a request/profile subject or shot
  (a phantom reference is a validation error, never a silently
  dropped scope). The request validator enforces the same relevant
  constraints as the request/profile schemas with exact JSON types,
  and boolean authorisation evidence must be the actual boolean
  `True` — a string such as `"false"` is never approval. Handoff
  packets take explicit completion receipts
  (`build_handoff_packet(session, plan, step_id,
  completed_receipts, catalog=None)`); a dependency counts as
  satisfied only when a validated receipt says so, and the packet
  is refused unless the session is the exact active session the
  plan belongs to, the plan hash validates, and the step is ready
  under those receipts. The compiled catalog carries a
  deterministic integrity fingerprint plus full semantic
  validation at load (exact TC-1..TC-10, edges vs dependencies,
  conflict symmetry, mode applicability, canonical groups) —
  integrity against accidental / unsupported mutation, not
  cryptographic protection against a malicious same-OS-user
  process. `tests/test_skill_router.py` also runs natively on
  Windows now (both `windows-compat` matrix versions). Record:
  corrections doc §12.
- **Checkout contract (R1-R1, 2026-11-26, same branch and PR #3).**
  `.gitattributes` pins `eol=lf` on every file the routing catalog
  hashes (the five canonical YAML sources, every
  `skills/*/SKILL.md`, and the catalog itself) — a Windows LF→CRLF
  checkout changes their raw-byte SHA-256 and fails the catalog
  checks (PR run #237); the router suite also needs PyYAML
  installed in `windows-compat`, mirroring `p0-validate`. Record:
  corrections doc §13.
- **Explicit nulls (R1-R2, 2026-11-26, same branch and PR #3).**
  An optional field that is present with an explicit `null` is a
  type error naming the field — never treated as if the field
  were absent — while an omitted field stays valid wherever the
  schema permits omission. Covers 22 cases (10 request-level, 5
  profile, 7 evidence strings); boolean approval evidence is
  unchanged (only the actual boolean `True` counts). Regression
  group CF-P1-002-R1-R2-NULL in `tests/test_skill_router.py`
  (22 cases × 4 checks + a summary check that fails if any
  declared case is dropped). Record: corrections doc §14.
- **Explicit nulls, complete parity (R1-R3, 2026-11-26, same
  branch and PR #3).** A schema-wide probe of all 67 unique
  optional property paths found 16 further explicit-null
  mismatches R1-R2 had not covered — request subject/shot tables
  (4) and profile per-subject (7) / per-shot (5) overrides —
  which `resolve_skills()` also accepted; all 16 are now rejected
  by both validators with a field-naming error. Regression group
  CF-P1-002-R1-R3-NULL67 in `tests/test_skill_router.py`
  (67 paths × 5 checks + a coverage assertion that compares the
  declared matrix against the optional paths discovered from the
  schema, so a new optional schema property without a test fails
  the suite). Record: corrections doc §15.

## P1-003 Script-to-Performance runtime (2026-11-26)

- **The runtime validates and assembles; it never creates.**
  `runtime/script_to_performance.py` is the third P1 runtime
  component: it validates, binds and assembles a structured source
  ScriptContract, an approved production profile and the AI layer's
  analysis drafts into final schema-valid Scene, Shot and
  Performance Plans plus the Script-to-Performance binding record,
  under one exact active P1-001 session and one valid, ready
  P1-002 routing plan (`intent_mode == GENERATE_FROM_SCRIPT`,
  plan session == exact active session). Standard-library only; it
  never generates media, never calls a provider, never persists
  anything, and never performs creative analysis — the AI reasoning
  layer supplies the drafts, this runtime guarantees contract
  integrity, verbatim dialogue preservation, cross-plan
  consistency and deterministic assembly. Full record:
  `docs/implementation/CF-WO-P1-003-corrections.md`, and the
  runtime contract in
  `docs/runtime/SCRIPT_TO_PERFORMANCE_RUNTIME.md`.
- **Dialogue is verbatim unless five conditions all hold.** Every
  source dialogue line maps to exactly one Performance Plan line,
  by `line_id`, in order, byte-for-byte. A rewrite is valid only
  when (1) the caller supplies an actual boolean `True`, (2) the
  plan uses `SCRIPT_EDIT_REQUESTED`, (3) the exact line has
  `rewrite_permitted: true`, (4) the original stays in
  `dialogue.text`, (5) the change lives only in `rewritten_text`.
  A plan-level request alone never authorises a rewrite.
- **Two layers, kept separate.** Layer A (AI reasoning / script
  analysis, canonical skills) is not implemented in the runtime;
  Layer B (this deterministic runtime) validates, binds and
  assembles. No LLM API, no heuristics pretending to understand
  natural language.
- **Cross-plan integrity is explicit.** Root IDs, project
  agreement, schema-version agreement, scene/beat/shot/line
  resolution, character resolution into the known set, voice
  bindings (either ID namespace), reaction holds, and contradictory
  subject dimensions across scene/shot/profile records are all
  checked; human lip articulation is never applied to an animal or
  creature, and an unestablishable kind fails closed only in the
  cross-reference phase, after kinds are resolved from all
  sources.
- **Determinism and output.** Canonical JSON + SHA-256 bundle hash
  (same pattern as the router's `plan_hash`); the hash lives only
  on the bundle and is recomputed by the bundle validator. Inputs
  are never modified in place; no partial bundle is ever returned.
  `tests/test_script_to_performance_runtime.py` (606 checks:
  session/routing, script, plans, dialogue, cross-refs,
  determinism, and the NULL156 nullability matrix over all 156
  optional paths in the six consumed schemas, with a coverage
  assertion). The `windows-compat` CI job runs the new suite on
  both matrix versions; the workflow file goes up via the GitHub
  website (API push 403s it), so no CI coverage is claimed until
  the actual run proves it.
- **Known canonical tension (recorded, not fixed).** A script with
  zero dialogue lines has no valid performance plan — the
  performance-plan schema requires at least one line (minItems 1)
  while the dialogue mapping forbids inventing one — so the
  builder fails closed. A non-verbal performance line omits
  `dialogue.text` (minLength 1); an explicit `""` is
  schema-invalid.
- **R1 hardening (2026-11-26, same branch and PR #4).** Bundle
  shape integrity (every required bundle field validated for
  presence AND type — a `None`, list or scalar record no longer
  passes with a recomputed hash), fail-closed input validation
  (malformed identifiers, project IDs, schema versions, subject
  dimensions, articulation/species values and live-action
  provenance fields return structured errors; the builder raises
  `ScriptToPerformanceError`, never a raw `TypeError` /
  `AttributeError`), and source dialogue metadata preservation
  (a source-supplied `character_id` or `language` must match
  exactly in the Performance Plan line — omitted or different
  fails closed; nothing invented, nothing translated). The two
  report generators take an explicit `--base <sha>` (default:
  the local `origin/main` ref) so the manifest base no longer
  depends on a ref any fetch can move. Regression groups
  `CF-P1-003-R1-BUNDLE-SHAPE` (35), `CF-P1-003-R1-FAIL-CLOSED`
  (41), `CF-P1-003-R1-DIALOGUE-META` (9) in
  `tests/test_script_to_performance_runtime.py` (691 checks
  total; baseline 606 intact). Record: corrections doc §11.
- **R2 hardening (2026-11-26, same branch and PR #4).** Manifest
  integrity (the R1 manifest carried one stale entry — the
  corrections document was edited after generation — so the
  document is now finalized before the manifest is generated and
  quotes no generated value; a new automated group
  `CF-P1-003-R2-MANIFEST` in `tests/test_reports.py` verifies
  all 182 entries entry-by-entry against the tree and rejects
  tampered copies) and adversarial nested JSON validation (eight
  table-driven groups over all eight boundaries — script,
  profile, scene, shot, performance, editing, bindings, bundle —
  with malformed types at every required object/array boundary
  and identifier field; 1,096 new checks, suite total 1,787,
  baseline 691 intact). Twenty production defects were
  reproduced pre-fix and fixed: a raw `TypeError` crash class
  from truthy non-iterable scalars where arrays are required
  (new `_as_list()` helper), a non-serialisable bundle hash,
  empty-string identifiers that silently passed, and dangling
  per-shot overrides that silently built. Record: corrections
  doc §12.
- **R2-F1 cross-platform manifest path safety (2026-11-26,
  same branch and PR #4).** The R2 validator accepted Windows
  absolute paths (`C:/Windows/win.ini`) because POSIX
  `os.path.isabs()` says False for them; the validator now uses
  host-independent `ntpath.splitdrive()` / `ntpath.isabs()`
  checks plus a realpath containment check, so drive-absolute,
  drive-relative and UNC paths, and symlinks escaping the
  repository root, are all rejected before any file is opened.
  Regression tests cover eight unsafe paths with explicit
  unsafe-path errors, the reviewer's decoy-file case, and a
  symlink-escape case (explicitly skipped where the platform
  cannot create symlinks). Only `tests/test_reports.py` and
  docs changed; the S2P runtime is untouched (1,787 checks).
  Record: corrections doc §12.7.
- **P1-003 Production Addendum 01 — professional filmmaking workflow (2026-11-26, same branch and PR #4).** Documentation-only integration of the genuinely missing professional filmmaking systems, derived from the work-order specification (the cited 28-page handbook PDF was not received in the workspace — see corrections doc §13.1; cross-check against the PDF is still open): six-stage stage-gate workflow G1–G6 with gate statuses (NOT STARTED / IN PROGRESS / PASS / BLOCKED / WAIVED) and explicit-authorisation waivers; P0–P3 production complexity tiers (a scope hierarchy, explicitly not a replacement for the Part E instruction-precedence hierarchy); director's breakdown, blocking, and selective 12-type coverage plus the 30-degree guideline and playable-action performance direction; Lighting Plan Template (20 fields) and 7 lighting scenarios; capability-aware camera technical profile; 6-step emotional beat progression; 8-step editorial workflow with picture lock and four added cut techniques; 9-step colour workflow with the no-invented-log-profile and no-LUT-hiding rules; 16-field Sound Spotting Template with the intentional-silence clarification; six missing animation principles in kids §4.3; shot-level VFX believability checklist; unified Master Shot Tracker (18 fields) with workspace template and naming convention; QC severity levels (Critical / Major / Minor / Polish) with delivery checklist and post-mortem; genre skill-selection matrix; command-authority integration (10-step operational sequence with G1–G6 gates). No new skill (15 stays 15), no new numbered entries (109/120 unchanged), no runtime or schema change, no new tracked file — the 182-file manifest scope is preserved. Record: corrections doc §13.

## P1-004 Universal AI Production Brain & script-to-production orchestration (2026-11-26)

- **The Brain is universal; the runtime is local.** `runtime/production_orchestrator.py` and `runtime/task_compiler.py` are the fourth and fifth P1 runtime components. The Brain separates five roles — Consistency Frame (Central Brain), AI Reasoning Host, Implementation Agent, Media Execution Providers, Production/Editing Tools — and contains no LLM, no rendering engine, no server, no API backend, and no cloud database. The orchestrator validates, binds, compiles and gates; the reasoning host does creative analysis and fills the production-analysis draft; providers execute media only on evidenced capabilities.
- **Production analysis is a contract, not a conversation.** `schemas/production-analysis.json` carries premise, narrative structure, scene breakdown, character resolutions, emotional progression, pacing, shot and sound direction, and open questions — every material decision labelled `EXPLICIT_FROM_USER`, `FROM_APPROVED_PROJECT_CANON`, `INFERRED_FOR_PRODUCTION`, or `NEEDS_USER_DECISION`. Story preservation is enforced: dialogue counts are checked against the source script, open questions and needs-decision characters block bundle building, and inferences are never presented as facts.
- **Character resolution is pure and task-local.** Approved identities always win (and must exist in the registry); a character with no approved identity gets a task-local design proposal (`schemas/character-design-proposal.json`) — design brief, fixed structure, reference preparation — that never registers anything permanently. Permanent registration still needs the existing explicit-authorisation flow.
- **Job state machine with operation-gated transitions.** `INTAKE → ANALYZING → PLAN_READY → AWAITING_G1_APPROVAL → TEST_READY → AWAITING_G2_APPROVAL → BATCH_PRODUCTION → EDITORIAL_REVIEW → PICTURE_LOCK → FINISHING → FINAL_QC → DELIVERED`, plus `BLOCKED` from any state (resume only to the previous state, only while no gate is BLOCKED). `PLAN_READY` is reachable only via `build_production_bundle`; `TEST_READY` and `BATCH_PRODUCTION` only via a G1/G2 PASS (or a user waiver with a recorded reason) in `evaluate_production_gate` — resuming from BLOCKED to a previous operation-gated state is the exception, because the operation that put the job there already passed the gate. Gates are enforced in order; a blocked gate blocks the job; only the user waives a gate.
- **Task compilation is deterministic and provider-neutral.** The compiler turns a validated bundle and analysis into task packets (character/reference prep, image, video, voice with exact dialogue text and consent, sound, editing/finishing, QC review) with deterministic hashes. Provider matching uses only evidenced capabilities from `registry/providers.json` (compiled from the `providers:` section of `architecture/COMPANION_CAPABILITY_REGISTRY.yaml`): VERIFIED, then EXERCISED; NOT_TESTED and FAILED never match; commercial jobs never match a provider whose commercial use is not approved (the default OmniVoice weights are CC-BY-NC). An unmatched task compiles as a complete provider-neutral handoff — never a pretended execution.
- **QC corrects locally.** `build_qc_correction_tasks` compiles regeneration packets only for defective shots (Critical/Major always, Minor only with repair authorisation, Polish never), re-matched as their original task type, preserving approved neighbours.
- **Muse compatibility is recorded in four dimensions.** Native installation support: UNSUPPORTED. Packaged knowledge-pack support: EXISTS (the repo itself). Actual host conformance: used daily in this account since 2026-11-12, but formal conformance NOT_TESTED (test `CF-P0-ADAPTER-001` still to be run). Media execution: none — Muse directs providers and tools only. All other hosts remain NOT_TESTED. Full record: `docs/implementation/CF-WO-P1-004-corrections.md`, runtime contract in `docs/runtime/PRODUCTION_ORCHESTRATOR_RUNTIME.md`.
- **Three numbering systems, never confused.** Production Complexity P0–P3 = video-quality scope classification. Engineering milestones P0/P1/P2/P3 = project phases. G1–G6 = production approval gates.
- **No new skill in P1-004** (15 stays 15); the audit found no gap that needs one. Five new schemas (all v2.5): `production-analysis.json`, `character-design-proposal.json`, `task-packet.json`, `gate-state.json`, `provider-capability.json`. New test suites `CF-P1-004-ANALYSIS`, `CF-P1-004-ORCHESTRATOR`, `CF-P1-004-COMPILER`. The manifest grows beyond 186 — expected for this round, genuinely new files only.

## P1-004-R1 Production contract fidelity, persistent project state & end-to-end planning (2026-11-26)

- **Production analysis is a complete contract.** Scenes carry structured environment intelligence (background design, weather, atmosphere, foreground/midground/background requirements, environment continuity) and `important_props` with design brief, visual/physical requirements, continuity restrictions and provenance; asset references bind scenes to approved assets by stable ids. Sound cues carry a stable cue id, scene/shot/beat ids, a start anchor from the seven-value vocabulary, optional end anchor/offset/duration, distance, perspective, intensity, sync target and mixing priority — relative timing only, never an invented global timecode, and planned timing is never claimed as rendered audio.
- **Character coverage is exact.** An empty `character_resolutions` array is valid only with genuinely no visible character subjects; otherwise every distinct required identity is resolved exactly once (missing, duplicate and unknown all rejected). A narrator / voice-over is not a visible character (narrator role, or a speaking identity in no scene and no shot). Cross-reference integrity runs against the actual built bundle (`validate_analysis_bundle_references`, called inside `build_production_bundle` and again in `plan_script_to_production`): scene/beat/shot/sound references must resolve, shot-direction entries must not repeat, and unknown references are never silently ignored.
- **The compiler splits technical from creative.** FFmpeg matches only technical media operations (`media-technical`: probe, assemble, transcode). `creative-editing` and `semantic-qc-review` have no verified provider and always compile as human handoffs. Environment packets carry every validated scene-environment detail plus approved asset ids; prop packets are one per distinct prop (approved props prepared, never redesigned; task-local proposals where no approved prop exists; nothing permanently registered). Sound packets preserve full structured cue timing with `timing_status: "planned"`; intentional silence generates no sound request.
- **Jobs persist locally, never as authorization.** `runtime/production_store.py` stores production metadata only (never raw media, voice samples or credentials) as JSON envelopes with integrity hashes under an explicit local root, atomic writes, strict path validation and symlink containment, `0o600` files / `0o700` dirs on POSIX. A stored session id is provenance only: resume needs a NEW exact active session, a project/owner/workspace match, stored-job validation and gate revalidation, rebinds the session id, refuses `DELIVERED` jobs, and never auto-resumes paid/external tasks.
- **One planning entry point.** `plan_script_to_production` runs validate → build bundle → cross-reference check → compile packets → persist (when a store root is given) → return the complete planning result. It does not promote `wf-generate-from-script`: no timeline manifest is produced and no fake media path is invented.
- **Muse formal conformance is now VERIFIED.** Test `CF-P0-ADAPTER-001` (`tests/test_muse_adapter_conformance.py`, 20 checks) ran in this environment on 2026-11-26 and passed: knowledge-pack access, router skill identification, canonical contract read, short-form fixture analysis, verbatim dialogue preservation, schema + runtime validation, unsupported media-provider operations identified, no native-install claim. The matrix entry (`architecture/AGENT_COMPATIBILITY_MATRIX.yaml`, duplicate keys cleaned) and the adapters registry (`registry/adapters.json`, regenerated from `scripts/generate-registries.py`) record `formal_conformance_status: VERIFIED` / conformance `VERIFIED`, evidence the test file, `last_verified: "2026-11-26"`, status `verified`. Native Muse install stays `UNSUPPORTED`. No claim is made about ChatGPT, Claude or Gemini conformance.
- **A test-found defect was fixed in this round.** `compile_provider_tasks` keyed proposals into a dict and passed the dict to `compile_task_package`, which iterated it as a list of records and dropped every key — so a task-local proposal passed through the orchestrator was silently lost and compilation failed with "no proposal record was supplied". Proposals now pass through as a list; the long-form end-to-end test (21 packets, fisherman task-local proposal) pins the fix. Record: `docs/implementation/CF-WO-P1-004-corrections.md` §10+.

## P1-004-R1-ADDENDUM-IDENTITY Persistent character & voice identity (2026-11-26)

- **Selection is explicit; identity is frozen.** `runtime/identity_resolution.py` is the sixth P1 runtime component. A job uses registered characters only through an approved identity-selection policy (`SELECTED_REGISTERED_ONLY`, `MIXED_REGISTERED_AND_NEW`, `NEW_ONLY`, `AUTO_MATCH_APPROVED`); the whole registry is never auto-added and `NEW_ONLY` disables registry reuse entirely. The resolved selection is frozen in an identity snapshot on the job (`job["identity_snapshot"]`) — reference asset ids and SHA-256s, model-sheet and fixed-identity references, expression references, wardrobe constraints, voice selections, cast classes, registry snapshot version and hash — and resume revalidates it against the current registries; a later registry change never silently mutates an approved snapshot.
- **Resolution is exact, never fuzzy.** Unique id is strongest; a unique name resolves only within the authorized owner/workspace scope; duplicate names require the id; name+id mismatch fails closed; no fuzzy matching, no cross-workspace resolution, and errors never leak private registry contents. The cast is classified per character — `VISIBLE_CHARACTER`, `OFF_SCREEN_SPEAKER`, `NARRATOR_OR_VOICE_OVER`, `MENTIONED_ONLY` — so a narrator gets no image task and a mentioned name gets no task at all unless the script requires it.
- **Packets carry structured bindings.** Image and video packets carry one `identity_bindings` entry per visible character (reference asset ids, primary reference, model sheet, angle-matched and expression references, fixed identity reference, reference SHA-256, wardrobe variation, ownership scope). Voice packets carry a `voice_binding` (voice profile id, dialogue line id, language, accent, vocal characteristics, pitch, pace, pronunciation, emotional delivery, pauses, reference-audio asset id and SHA-256, provider voice id, model/version, seed, ownership/consent reference). A voice profile belongs to exactly one character; several eligible profiles with no default require one clear selection — the first additional profile of a registration is not a default. All P0 voice checks are delegated to `scripts/asset_policy.py`, never reimplemented. Regeneration packets copy the original bindings verbatim.
- **Fixed prompt block and seed are machine-readable.** `schemas/character.json` and `schemas/character-registration.json` carry optional `fixed_prompt_block` and `generation_seed`; `schemas/project.json` (v2.5, alongside preserved v2.3) links its policy through optional `identity_policy_id`. No new skill; two new schemas (`identity-selection-policy.json`, `identity-snapshot.json`); new test suite `CF-P1-004-R1-IDENTITY-*` (see `docs/runtime/IDENTITY_RESOLUTION_RUNTIME.md`). The snapshot rides in the production job record, so the production store persists it with the job — no second job database.

## P1-004-R1-F1 Unified identity workflow (2026-11-26)

- **One entry point carries identity end to end.** `plan_script_to_production` takes optional keyword-only `identity_policy`, `character_registry`, `voice_registry`, `character_registry_root` and `voice_registry_root` (explicit mapping, then root, then the authorized overlay environment variable; the voice registry defaults to the character registry root). No policy means exactly the pre-F1 behaviour and no registry access. An explicitly supplied registry is scoped to the session inside the snapshot builder, so foreign owner/workspace records are invisible there as at load time.
- **Selectors are canonical and exact.** The policy's `selected_characters` selects by exact id, exact unique name, or both (both must name the same record); `selected_character_ids` stays valid, and the two lists must agree when both are supplied. `AUTO_MATCH_APPROVED` enriches the analysis first (name-only approved resolutions by exact unique name) and completes the selection from the script cast in the snapshot builder; duplicate names, unknown names and conflicting identifiers fail closed, no fuzzy matching. A resolution ref outside the known set is accepted only when it declares `MENTIONED_ONLY`, and a declared cast class must agree with the classifier's class.
- **NEW_ONLY is adversarially hardened.** `validate_new_only_inputs` fails closed on any approved registered resolution, any proposal reusing a registered reference asset, or any bundle voice binding naming a registered voice — naming only caller-supplied references. The adversarial test uses the original script/cast references against populated registries and scans the whole package, bundle and snapshot for registered content; old registry records are never modified.
- **Test-found defect (F5):** the voice binding copied the performance line's `pauses` list verbatim, but the task-packet schema types it as one string — the binding now joins a list with `"; "`. Full record: `docs/implementation/CF-WO-P1-004-corrections.md` §17; regression matrix F1–F6 in `tests/test_identity_resolution.py` (entries `CF-P1-004-R1-F1-*` in `tests/run-tests.sh`).

## P1-005 Real media execution runtime, provider adapters & timeline delivery (2026-11-27)

- **A compiled packet is never proof of execution.** The execution
  runtime (`runtime/media_execution.py`, `runtime/media_adapters.py`,
  `runtime/execution_orchestrator.py`, `runtime/timeline_delivery.py`)
  is the seventh P1 runtime component. Only a genuine adapter result
  moves an execution to SUCCEEDED, and only after independent
  re-verification (SHA-256, byte count, ffprobe duration agreement).
  Execution state rides on the production job (`job["executions"]`)
  and persists through the existing production store — no second job
  database.
- **The state machine is deterministic.** Twelve states
  (`PLANNED` → … → `SUCCEEDED` / `FAILED` / `CANCELLED` /
  `NEEDS_USER_ACTION` / `BLOCKED`); SUCCEEDED only from
  `VALIDATING_OUTPUT` with a validated artifact; FAILED always
  carries a failure classification; terminal records never
  transition; `BLOCKED` resumes to its previous state. Stable
  execution ids + idempotency keys
  (SHA-256 of `job_id|task_id|provider_id|packet_hash|attempt`); a
  retry is an explicit new attempt; an uncertain submission goes to
  `NEEDS_USER_ACTION` and is never auto-resubmitted.
- **Authorization and identity locks gate every submission.**
  Provider matching reuses the P1-004 rule (VERIFIED then EXERCISED;
  NOT_TESTED and FAILED never match); authorizations are explicit
  per-task approvals (`{task_id: True}`, nothing implicit); packet
  bindings are checked against the frozen identity snapshot before
  submitting. One task failing never aborts the others.
- **Technical QC is deterministic; semantic QC is human.**
  Technical checks (readability, corrupt frames, fps, resolution,
  codec, duration, audio presence, peak levels) carry Critical /
  Major / Minor / Polish and pass only with no Critical or Major —
  but a passing technical report is NOT a G6 PASS. Semantic checks
  need a named human reviewer through a handoff that is never
  auto-approved (`automated` is refused).
- **Only validated artifacts enter the timeline.** The delivery
  manifest is built from SUCCEEDED executions only, re-verifying
  every artifact against the real file; no fabricated path or
  placeholder output. Format is always `editor_neutral_v1`;
  resolution comes from the first delivered video artifact when
  probed, otherwise 1920x1080 (the production format profile
  carries no media geometry).
- **Local providers, exercised 2026-11-27.** FFmpeg 8.1.2
  (probe/transcode/assembly, `CF-P1-005-FFMPEG`); VoiceStudio /
  OmniVoice (one real Bengali generation, 1.98 s, audio id
  `1faa2e3e`; CC-BY-NC — commercial voice tasks are refused);
  OpenMontage (demo `animated-reel-20s` rendered and validated;
  production assembly NOT exercised). OpenTimelineIO is not
  installed and has no adapter — the canonical timeline manifest
  covers interchange.
- **External providers: eight live specs, all NOT_TESTED, Sora
  FAILED.** OpenAI / Gemini / fal.ai image, Veo / Kling / LTX
  video, ElevenLabs voice, Lyria music — spec-driven HTTP adapters
  over mock transports in tests; no live paid call without explicit
  user authorization. Sora was shut down 2026-09-24 (no
  replacement API). Credentials come only from allow-listed
  environment variables; never in Git, logs, reports or packets.
  Full matrix: `docs/runtime/PROVIDER_ADAPTERS.md`.
- **Test-found defects (P1-005):** `load_schema` called without
  `.json`; `validate_instance` called with the wrong arity;
  `VALIDATING_OUTPUT` dropped the output artifact; `SUCCEEDED`
  was unreachable (missing transition-table entry); a sync
  completion with a provider job id stalled in RUNNING; the
  delivery manifest used schema-invalid defaults; ffprobe JSON was
  truncated by error-text redaction; the HTTP adapter did not
  resolve output paths; `duration_limits` was a string where the
  schema wants an object; a re-render was invisible to the
  OpenMontage adapter; schemas used explicit nulls the repo
  validator rejects; `registry_from_job` built invalid ownership;
  the VoiceStudio adapter could never warm a cold backend. Full
  record: `docs/implementation/CF-WO-P1-005-corrections.md`;
  suites `CF-P1-005-EXECUTION` (85), `CF-P1-005-FFMPEG` (28),
  `CF-P1-005-ADAPTERS` (56), `CF-P1-005-DELIVERY` (26).
- **R1 Windows fix (2026-11-27):** the first CI run on the P1-005
  head failed both `windows-compat` jobs in the identity suite's
  e2e group — `scripts/atomic_write.py` called `os.fchmod`
  unconditionally, which does not exist on Windows Python
  3.10-3.12. P1-001-R2 had fixed the same hole in
  `runtime/local_session.py` but left this helper untouched. The
  helper now capability-checks `os.fchmod` (same pattern); the
  store suite pins it with a Windows simulation (hide the
  attribute, write through the store and the helper directly,
  verify the record validates and no temp file is left on
  failure). Full record: corrections doc §9.
- **R2 Windows path fix (2026-11-27):** the CI run on the R1 head
  failed both `windows-compat` jobs again, this time in the
  timeline delivery suite — one check,
  `artifact-absolute-refused`: the delivery validator rejected
  absolute paths with a POSIX-only `startswith("/")` test, which
  accepts `D:\...` on Windows. The same pattern existed in the
  execution-artifact validator (its test used `/tmp/...`, so it
  passed on Windows while the hole stayed open). Both validators
  now share one host-independent predicate,
  `is_safe_relative_path` (`ntpath.splitdrive` + `ntpath.isabs`
  + `..` under either separator), pinned by Windows-style path
  cases that fail pre-fix on Linux too. Full record: corrections
  doc §10.
- **R3 Python 3.13 `ntpath.isabs` fix (2026-11-27):** the CI run
  on the R2 head passed both `windows-compat` jobs but failed
  `p0-validate` on exactly three leading-slash cases — the R2
  predicate relied on `ntpath.isabs()`, which since Python 3.13
  (GH-44626) returns False for a path starting with exactly one
  (back)slash, and the CI runner uses Python 3.14.4 while local
  Python is 3.12.3. The predicate now refuses a leading `/` or
  `\` explicitly, before consulting `ntpath` at all, and the fix
  was verified locally under a simulated 3.13+ `ntpath.isabs`.
  Full record: corrections doc §11.

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

## P1-006 First complete vertical video production & delivery (2026-11-27)

- **One workflow, intake to delivery.** The vertical production
  runtime (`runtime/vertical_production.py`,
  `runtime/production_assets.py`, `runtime/production_voice.py`,
  `runtime/production_audio.py`, `runtime/production_timeline.py`,
  `runtime/production_qc.py`, `runtime/production_delivery.py`)
  is the eighth P1 runtime component. It connects project
  validation, visual assets, voice, sound design, canonical
  timeline, FFmpeg assembly, QC and delivery into one
  reproducible job, on the P1-001 session, P1-004 orchestrator /
  store / identity workflow, and P1-005 execution runtime. The
  reference driver is `scripts/run-p1006-reference-render.py`;
  the reference project is
  `examples/p1006-vertical-explainer/` (source only — no media
  binaries are committed; generated media lives in the delivery
  archive with hashes).
- **The state machine is strictly linear.** `INTAKE →
  PROJECT_VALIDATED → ASSETS_PENDING → ASSETS_READY →
  VOICE_PENDING → VOICE_READY → SOUND_PENDING → SOUND_READY →
  TIMELINE_READY → ASSEMBLY_RUNNING → ASSEMBLY_COMPLETED →
  QC_RUNNING → QC_PASSED → DELIVERY_READY → DELIVERED`, plus
  `FAILED` / `CANCELLED` / `NEEDS_USER_DECISION` / `BLOCKED`.
  Each state transitions only from its immediate predecessor.
  Stages are idempotent via input-hash checkpoints
  (`stage_checkpoint` / `stage_is_done`); mid-render
  cancellation is not supported (a closed session refuses to
  start assembly).
- **One rendering path: FFmpeg.** The canonical timeline
  (`editor_neutral_v1`) is assembled by FFmpeg only; OpenMontage
  production assembly stays NOT_TESTED and is refused. Geometry
  comes from the validated output profile, never hardcoded. The
  reference render is 9:16, 1080x1920, 30 FPS, H.264/AAC, MP4,
  30–60 s.
- **Voice is real VoiceStudio/OmniVoice, non-commercial.**
  Narration is generated locally, seed-fixed, line by line, each
  WAV verified; only `instruct` / `speed` / `seed` are forwarded.
  The valid instruct tag for the reference narrator is
  `middle-aged, moderate pitch` — `narrator` is not in
  OmniVoice's fixed vocabulary and the backend rejects it. The
  CI render synthesizes deterministic tone narration at the
  planned line durations (same pipeline, geometry and QC) and
  records `voice_source: synthesized-tone`.
- **QC blocks delivery; the review package is honest.** Technical
  QC (ffprobe, exact geometry, rational frame rate, full decode,
  black/freeze detection), visual QC (contact sheet, keyframes,
  human review always required) and audio QC (loudness, true
  peak, clipping, silence) must pass, and `DELIVERY_READY`
  needs a named human reviewer — `automated` is refused. A
  review package (`review_package=True`) is built while that
  approval is still missing; its manifest records the true
  decision (`BLOCKED`), the reasons, and `package_purpose:
  review`, and never claims `DELIVERY_READY`. Full record:
  `docs/implementation/CF-WO-P1-006-corrections.md`, runtime
  contract in `docs/runtime/VERTICAL_PRODUCTION_RUNTIME.md`.

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
