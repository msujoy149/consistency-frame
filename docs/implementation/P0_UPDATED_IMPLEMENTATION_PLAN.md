# P0 Updated Implementation Plan — v2.4 Brain Architecture Amendment

**Work order:** CF-WO-P0-001 (revised) · **Architecture:** v2.4 (amendment
of 2026-11-22, user voice call — supersedes the v2.3 server-management
interpretation) · **Branch:** `feat/cf-p0-safe-foundations` ·
**Base:** `main` / `e1571db68ed87fb973c45960a4a3e27e09ba0d06`

**Governing rule:** Consistency Frame is the CENTRAL BRAIN /
Orchestrator of a general-purpose Professional AI Video Production &
Editing Ecosystem — NOT a standalone video-generation server,
audio-generation server, API backend, cloud database, hosting
platform, or replacement for the companion repos. WITHDRAWN: Central
Server Manager + own-API implementation. No standalone server, API
backend or central database in P0. The v2.3 P0 (Safe Foundations) is
preserved in full; this revision adds the v2.4 records on top of it.
Consistency Frame is animation-first and style-agnostic (§9, P0-006):
it directs consistent, expressive, physically believable animated
videos across 2D, 3D, stylized, semi-realistic, and photorealistic
styles, for humans, digital humans, animals, creatures,
multi-character interactions, image-to-video, video-to-video, and
hybrid live-action/VFX work — not a cartoon-only toolkit.

## 1. What the v2.3 P0 already delivered (preserved, not redone)

Non-destructive installer (`scripts/sync-skills.sh`, core-only
`setup.sh`); canonical registries (`registry/*.json` — 15 skills, 165
features, 13 workflows, 12 adapters, none supported); 20 versioned JSON
Schemas; asset-mode policy (`scripts/asset_policy.py`); named audio
delivery profiles (`docs/19`); skill-first loop split (§9A task-local
draft / §9B permanent mutation on explicit authorisation); scoped
quality claims + human-review gate; tests (17 checks) + GitHub Actions
CI; living architecture report. Full evidence:
`docs/implementation/BUILD_REPORT_P0.md` (v2.3 sections) and
`docs/implementation/CF-WO-P0-001-plan.md` (historical record — not
rewritten).

## 2. Revised P0 — three parts

### P0-A — Existing Skill + Architecture Audit (DONE)

Deliverable: `docs/implementation/BRAIN_ARCHITECTURE_AUDIT.md`.

- Grepped the whole repo for server / API-backend / cloud-database /
  central-manager claims: **zero** such claims in normative text.
  The v2.3 P0 built no server, so there was nothing to withdraw in code.
- Every related hit recorded with file:line and verdict (F-01…F-08):
  "Character Database" is the private overlay registry (KEEP);
  "VoiceStudio Python API" is the companion's own local API (KEEP);
  Premiere UXP API is an external editor API (KEEP); "provider
  orchestration" in out-of-scope lists is a deferred-scope label,
  reframed as brain direction, no server (KEEP).
- One documentation fix: a "v2.4 Brain Architecture Amendment" section
  added to `AGENTS.md`. No skill file was modified, deleted or rewritten.
- 15-skill inventory verified against `registry/skills.json` and the
  filesystem (all DOCUMENTED, none TESTED/PRODUCTION_VERIFIED as
  creative content — recorded honestly).
- v2.4 mode mapping documented (audit §4): ONE-OFF =
  `UPLOAD_ONLY`, `TEMPORARY_ASSET_USE`, `GENERATE_FROM_SCRIPT`,
  `EDIT_EXISTING_MEDIA`, `REFERENCE_REVIEW`, `VIDEO_QC`,
  `REMAKE_OR_TRANSFORM` (no permanent record); RECURRING =
  `PROJECT_CONSISTENCY` (resolve by stable ID, no silent create) +
  `REGISTER_CHARACTER` / `REGISTER_VOICE_PROFILE` /
  `REGISTER_SOUND_ASSET` (permanent only on explicit authorisation) +
  `REFERENCE_LEARN_AND_UPDATE` (canonical learning only via reviewable
  patch) + `REPORT_UPDATE_ONLY`. No code change was needed —
  `scripts/asset_policy.py` already enforces it.

### P0-B — Canonical Skill Registry, Skill Routing Matrix, Workflow Graph, Script-to-Performance Schemas (DONE)

| Deliverable | Path | Content |
|---|---|---|
| Skill Routing Matrix | `architecture/SKILL_ROUTING_MATRIX.yaml` | One entry per skill (all 15, ids `skill-<slug>`): stable ID, activation trigger, non-trigger, required inputs, expected outputs, dependencies, precedence (unique 1–15; command-authority = 1, the router), conflicts (symmetric), applicable production modes, quality gate, approval conditions. Every value grounded in the skill text or `registry/skills.json`; where a skill does not state something the value is `not_stated_in_skill`. |
| Workflow Graph | `architecture/WORKFLOW_GRAPH.yaml` | 15 nodes, 42 edges (14 router edges from command-authority + 28 dependency edges), 3 parallel groups, 1 conditional parallel group (already-registered characters only), exclusive groups (video-type skills, at most one per video), 9 sequential chains. Acyclic — topological order is the precedence order. |
| Script-to-Performance Schema (headline: `SCRIPT_TO_PERFORMANCE_SCHEMA.json`) | `schemas/script-to-performance.json` | Combined contract binding Scene + Shot + Performance Plans with audio (music/ambience/SFX) and editing (rhythm + reaction holds) plans. Dialogue VERBATIM unless a rewrite was explicitly requested. |
| Scene Plan | `schemas/scene-plan.json` | Scenes, beats, dramatic intent, primary/secondary emotion, intensity (0–10), transitions. |
| Shot Plan | `schemas/shot-plan.json` | Shots: framing, camera angle/movement, lighting, duration, beat link. |
| Performance Plan | `schemas/performance-plan.json` | Per dialogue line: facial + micro-expressions, eye movement/gaze, posture, gesture, breathing, physical behaviour, voice (emotion, pitch, pace, pauses), speaker identity, lip-sync required. |

All four schemas use only the restricted subset
`scripts/validate-repo.py` checks (no `$ref`/`allOf`/`oneOf`,
nested objects inline, `additionalProperties: false`) and carry
`schema_version: "2.4"`. The validator was extended to accept
`"2.3"` or `"2.4"`. Valid fixtures:
`tests/fixtures/{scene,shot,performance-plan,script-to-performance}-valid.json`.

### P0-C — Companion Capability Registry, Agent Compatibility Matrix, validation tests, living documentation (DONE)

| Deliverable | Path | Content |
|---|---|---|
| Companion Capability Registry | `architecture/COMPANION_CAPABILITY_REGISTRY.yaml` | VoiceStudio v0.5.8 (AGPL-3.0, pinned `2f2f5a9…`) + OpenMontage (AGPL-3.0, pinned `fecb9a1…`). Every capability carries on-disk evidence (file path) and an honest status: `VERIFIED_ON_DISK` (code present), `VERIFIED_BY_RUN` (recorded local run), `NOT_VERIFIED` (documented but never exercised — e.g. VoiceStudio's "646 languages" headline, all OpenMontage paid provider routes). The Brain directs the companions; it never modifies their internal code. |
| Agent Compatibility Matrix | `architecture/AGENT_COMPATIBILITY_MATRIX.yaml` | 10 agents (Muse, ChatGPT, Codex, Claude, Claude Code, Gemini CLI, Antigravity, OpenCode, Cursor, GitHub Copilot): native skill install, knowledge-pack path, verified vs untested. Only Muse is VERIFIED (knowledge-pack path used in this account). Every other agent is NOT_TESTED. OpenRouter is listed as a model-routing layer, not an agent host; Colab needs an appropriate Notebook/Agent Runtime. |
| Tests | `tests/test_routing.py` (+ `tests/run-tests.sh` registration) | CF-P0-ROUTING-001 (matrix completeness), -002 (graph acyclic + edges match dependencies), -003 (companion + agent matrices), plus v2.4 schema fixture/negative tests. |
| Validator | `scripts/validate-repo.py` (check 8) | Validates all five canonical YAML files (structure, 15-skill match, unique precedence, acyclicity, honest statuses, only Muse verified). PyYAML, guarded import with a clear skip message when missing. |
| CI | `.github/workflows/p0-ci.yml` | Added `pip install pyyaml` step before the test run (same pinned action SHAs). |
| Living report | `docs/architecture/living-architecture-report-v2.4-p0.md` | Regenerated by `scripts/generate-report.py` from canonical records (v2.3 report file retained as the baseline record). |
| Build report + manifest | `docs/implementation/BUILD_REPORT_P0.md` §11, `docs/implementation/build-report.json`, `release-manifest.json` (version `2.4-p0`) | Regenerated by `scripts/generate-build-report.py`. |

## 3. Chosen file paths (summary)

```
docs/implementation/BRAIN_ARCHITECTURE_AUDIT.md
docs/implementation/P0_UPDATED_IMPLEMENTATION_PLAN.md   (this file)
architecture/SKILL_ROUTING_MATRIX.yaml
architecture/WORKFLOW_GRAPH.yaml
architecture/COMPANION_CAPABILITY_REGISTRY.yaml
architecture/AGENT_COMPATIBILITY_MATRIX.yaml
schemas/script-to-performance.json        (SCRIPT_TO_PERFORMANCE_SCHEMA.json)
schemas/scene-plan.json
schemas/shot-plan.json
schemas/performance-plan.json
tests/test_routing.py
tests/fixtures/scene-plan-valid.json
tests/fixtures/shot-plan-valid.json
tests/fixtures/performance-plan-valid.json
tests/fixtures/script-to-performance-valid.json
docs/architecture/living-architecture-report-v2.4-p0.md
```

## 4. Acceptance gates (new, v2.4)

| Gate | Result | Evidence |
|---|---|---|
| CF-P0-ROUTING-001 routing matrix covers all 15 skills, required fields, triggers non-empty, precedence unique 1–15, router is precedence 1 | PASS | `tests/test_routing.py` |
| CF-P0-ROUTING-002 workflow graph acyclic, all nodes known skills, edges match routing-matrix dependencies (+ router edges only) | PASS | `tests/test_routing.py` |
| CF-P0-ROUTING-003 companion registry honest statuses, agent matrix only Muse verified, OpenRouter/Colab correctly classified | PASS | `tests/test_routing.py` |
| P0-SCHEMA (v2.4 part) new schemas validate fixtures + reject invalid instances | PASS | `tests/test_routing.py` + `scripts/validate-repo.py` |
| CF-P0-PERF-001 emotion intensity is 0–10 in performance-plan lines and scene-plan beats; 11 and −1 rejected, 0 and 10 accepted | PASS | `tests/test_performance_semantics.py` |
| CF-P0-PERF-002 all durations strictly positive (`exclusiveMinimum: 0`): shot `duration_seconds`, reaction-hold `hold_seconds`, non-verbal-event `duration_seconds`; 0 rejected | PASS | `tests/test_performance_semantics.py` + `scripts/validate-repo.py` (validator extended with `maximum` + `exclusiveMinimum`) |
| CF-P0-PERF-003 canonical emotion enum is the seven canonical + neutral set in both plans; the longer list moved to open `nuanced_emotion` (extensible, no schema change for new values) | PASS | `tests/test_performance_semantics.py` |
| CF-P0-PERF-004 explicit `non_verbal_events` on performance-plan lines and scene-plan beats; unknown type or intensity 11 rejected; a line with no spoken text and no event is invalid | PASS | `tests/test_performance_semantics.py` |
| CF-P0-PERF-005 dialogue is a `dialogue` object; `rewritten_text` requires per-line `rewrite_permitted: true` — plan-level `SCRIPT_EDIT_REQUESTED` alone never permits a rewrite | PASS | `tests/test_performance_semantics.py` (`validate_dialogue_rewrite` in `scripts/validate-repo.py`) |
| CF-P0-LEARN-001 propose/apply split: propose needs `REFERENCE_LEARN_AND_UPDATE` + explicit instruction; apply needs a full authorisation (granted_by + scope + branch + explicit_authorisation); intake never reports apply True | PASS | `tests/test_modes.py` + `tests/test_schemas.py` |
| All v2.3 gates still pass | PASS | `bash tests/run-tests.sh` (full run) |

## 5. What was deferred to P1 (not P0)

- **Runtime skill-routing engine:** the routing matrix and workflow
  graph are canonical data; a runtime that executes them (intake →
  route → run → QC) is P1 work. Until then the matrix is the
  human/agent-readable routing contract.
- **Script-to-performance runtime:** the schemas are contracts; the
  runtime that produces Scene/Shot/Performance Plans from a script
  is P1 work.
- **Adapter conformance tests:** all adapters remain NOT_TESTED; no
  "supported" claim until a real conformance test passes.
- **Registry count reconciliation:** 165 derived features vs the
  historical 109/120 claim (different counting units) — unchanged.
- **Private-overlay runtime adapter:** deferred to P2 (unchanged).
- **OpenMontage paid provider routes:** none validated live; recorded
  NOT_VERIFIED. A live paid call is never made without the user's
  explicit approval and keys.
- **Research-register reconciliation:** unchanged.
- **Media intelligence, reference-learning runtime, benchmarks, repair
  loop:** out of scope for P0 by design (P1–P4).

## 6. Judgement calls recorded (not hidden)

- `resource-management`'s applicable modes are inferred from its phase
  table (§3), not stated in the skill; it is excluded from
  `UPLOAD_ONLY`, `REGISTER_SOUND_ASSET` and `REPORT_UPDATE_ONLY` on
  that basis (see audit + routing NOTES in the work log).
- `production-systems` lists no dependencies: the skill says an AI
  "following this skill alone can apply them". Cross-references are not
  builds-on.
- `humanized-production` dependencies are "defers-to" (the full rules
  live in voice-consistency and production-systems), not "builds on".
- `video-regeneration` does not list `GENERATE_FROM_SCRIPT`: it is
  driven by the uploaded reference video, not a user script; its
  governing mode is `REMAKE_OR_TRANSFORM` with `REFERENCE_REVIEW` for
  the §1 analysis.
- `agency-advertising` lists no production-systems/humanized dependency:
  plainly needed in practice, never stated in the skill, so not invented.
- `language-authenticity` → `production-systems` dependency is thin
  (grounded only in §7 citing B15 for caption tracks); the
  voice-consistency dependency is the strong one.
- Precedence 11–14 (video-type skills) is tie-breaking only — those
  skills never run together. **Superseded by P0-006 (§9):** the
  one-video-type-per-video mutual exclusion is withdrawn and replaced
  by composable routing (primary pathway + style profiles + subject
  capabilities + compatible layers, true conflicts only). The
  `WORKFLOW_GRAPH.yaml` exclusive-groups change that implements this
  is owned by the P0-006 architecture part; until it lands, no
  routing claim in that file that contradicts the canonical
  animation-scope document is to be relied on.
- The `existing-character-prep` parallel group (character + voice) is
  valid ONLY for already-registered characters; for a new character,
  voice follows registration. It lives in
  `conditional_parallel_groups`, not `parallel_groups`, for exactly
  that reason.
- No skill owns `REGISTER_SOUND_ASSET`, `REPORT_UPDATE_ONLY` or
  `UPLOAD_ONLY` as its purpose; only command-authority (which routes
  everything) lists them.

## 7. Security & privacy (unchanged from v2.3)

Secret scan PASS; private-data check PASS; licences intact (own work
Apache-2.0; VoiceStudio + OpenMontage AGPL-3.0; OmniVoice weights
CC-BY-NC, never downloaded by `setup.sh`); no skill content changed;
no Master Prompt file touched; no server/API/database code exists or
was added; no push, no merge, no PR in this work (delivery is the
parent agent's step).

## 8. Propose/apply split for canonical skill learning (§5 correction, CF-WO-P0-002)

Proposing a skill patch and applying one are two different
permissions — the old single gate conflated them.

- **Propose** (`may_propose_skill_patch` in `scripts/asset_policy.py`):
  allowed only in mode `REFERENCE_LEARN_AND_UPDATE` with an explicit
  user instruction. A proposal is a reviewable patch file under
  `.consistency-frame/proposals/`; it never touches a canonical skill.
- **Apply** (`may_apply_skill_patch` / `validate_skill_patch_application`):
  allowed only with a full, explicit authorisation —
  `granted_by` + `scope` + `branch` + `explicit_authorisation: true`.
  Anything missing → rejected, with the missing fields listed.
- **Legacy gate** (`may_mutate_canonical_skills`): now returns True
  only when BOTH halves are present (propose permission + full apply
  authorisation). Propose alone never mutates a canonical skill.
- **Intake** (`intake_result`): reports both `may_propose_skill_patch`
  and `may_apply_skill_patch`; apply is always False from intake alone
  — intake never carries an apply authorisation.
- **Reference review** (`schemas/reference-review.json`): a review may
  only propose (`proposal_only`, default true, documented in the
  description). `apply_skill_patch: true` requires the `authorization`
  object; the conditional rule is enforced semantically in
  `tests/test_schemas.py` (the restricted schema subset cannot express
  conditional-required). `mutates_canonical_skills` stays `enum: [false]`.

## 9. P0-006 — Animation-first, style-agnostic production architecture (complete)

Work order CF-WO-P0-006 + Mandatory Addendum C (received 2026-11-22).
Part A (evidence correction) is done and committed (local head
`2235438`); Parts B–L are complete on this branch (local head
`f7fd0d5`, 9 commits), integrated by the coordinator.
The authoritative reference is the new canonical document
`docs/architecture/ANIMATION_SCOPE_AND_PRODUCTION_MODES.md`; the
full corrections record is
`docs/implementation/CF-WO-P0-006-corrections.md`.

### 9.1 What changes

- **Product identity becomes animation-first and style-agnostic
  everywhere** (README, AGENTS.md, this plan): animation is NOT
  cartoon-only — 2D, anime, stylized 3D, semi-realistic,
  photorealistic CGI, digital humans, animals, creatures,
  image-to-video, video-to-video, and hybrid live-action/VFX.
  The README's "Realism, not animation" wording is withdrawn: a
  photorealistic digital-human video IS animation (a generated
  digital human, not live-action footage). The flat 2D explainer is
  one optional profile, not the product's animation model.
- **Multi-dimensional model, not one enum.** Visual style,
  production medium, source-media type, and motion-generation
  method are independent dimensions with fixed vocabularies, plus
  subject kind, interaction pattern, and articulation target. No
  giant `animation_type` enum is created.
- **Composable routing replaces mutual exclusion.** Primary pathway
  + style profiles + subject capabilities + compatible layers, with
  true conflicts only. The §6 judgement that precedence 11–14
  video-type skills "never run together" is superseded (see the
  note in §6). The `WORKFLOW_GRAPH.yaml` exclusive-groups change
  and the routing-matrix update are owned by the P0-006
  architecture part.
- **Realistic-person skill contradiction fixed (by the skills part,
  not here):** the skill no longer says a realistic-person video is
  "not animation"; it now covers photorealistic digital-human
  animation including lip-sync, expressions, and body movement,
  while keeping the consent / likeness / voice-permission rules and
  the distinction from real live-action footage.
- **Schema evolution, additive, v2.5.** New production-profile
  contract (`schemas/production-profile.json`) and character
  registration contract (`schemas/character-registration.json`);
  character, voice-profile, shot-plan, and performance-plan
  contracts extended with subject kind / species / anatomy /
  consent, per-subject articulation targets, and the
  cinematography fields — all additive; v2.4 records stay valid.
  (Schema files are owned by the P0-006 schema part; this plan
  records the intent, not the delivery.)
- **Addendum C.** Reference video is OPTIONAL (Path A
  reference-video-assisted vs Path B script-and-image-driven; never
  invent a reference video); first-run Character Registration
  invitation (register now / skip + temporary use / register later;
  skipping never prevents a video; never silently convert an upload
  into a permanent registration); character registration data model
  (name + unique ID required, ID-generation with uniqueness
  validation); character–image binding and reference management
  (resolve by ID/unambiguous name, record IDs in the manifest);
  private per-character voice registration (user-recorded + AI-
  generated paths); strict voice isolation + privacy
  (owner/workspace-scoped, no private media in public GitHub,
  disclosed provider transmission, no unsupported "never leaves the
  device" promise); character–voice binding in every production;
  performance direction with subject-specific articulation (no human
  lips on birds); multi-character interaction + dialogue blocking
  (speaker/listener/eyelines/180-degree rule); intelligent
  cinematography (motivated movement only, focus/depth, continuity);
  one shared audio-visual timeline (stable dialogue + shot IDs for
  VoiceStudio/OpenMontage handoffs); QC (identity, voice,
  performance, cinematography, audio-visual, with the
  provider-limitation honesty rule).
- **D6 — no new skill.** P0-006 adds no new skill. The animation
  scope is a routing/profile layer over the existing 15 skills,
  which already cover the techniques involved; a new skill would
  duplicate them. Counts stay 109 distinct systems / 120 numbered
  entries. A permanent canonical skill change still needs explicit
  user authorisation through the propose/apply split (§8).

### 9.2 What P0-006 does not do

- No server, API backend, database, or rendering engine; no
  VoiceStudio/OpenMontage internal changes; no Master Prompt change;
  no skill file rewritten by the docs part (skill text changes are
  the skills part's work and are extensions/clarifications, not
  deletions or weakenings).
- No P1 work is started: routing-engine runtime,
  script-to-performance runtime, provider execution, and adapter
  conformance tests remain P1 (§5). No capability is marked
  exercised or production-verified without actual evidence.
- `docs/06-installation.md` is unchanged by the docs part: it does
  not describe the product as cartoon-only (it lists the explainer
  as one skill among 15), so no correction was needed there.

## 10. P0-007 — Final autonomous completion (in progress)

Work order CF-WO-P0-007 (received 2026-11-22). A contract +
validation correction round on the same branch; it completes the
P0-006 architecture rather than starting new work. The full record
is `docs/implementation/CF-WO-P0-007-corrections.md`.

- **A — Timeline contract.** `schemas/timeline-manifest.json`
  upgraded to v2.5 (additive): project/timeline identity, video-clip
  + shot bindings, audio-clip + dialogue bindings, synchronization
  groups, and real cross-reference validation. Valid v2.3 timelines
  still pass; invalid v2.5 relationships fail.
- **B — Private character and voice ownership.** Structured
  `ownership` (`owner_id`, `workspace_id`, `visibility`,
  `sharing`) in character registration and voice profiles; the
  production resolver requires BOTH the Character ID + Voice
  Profile binding AND matching ownership.
- **C — Conditional v2.5 voice validation.** JSON Schema and the
  Python validators must agree; the v2.5 rules differ by source
  (user-recorded vs AI-generated) and approval state, enforced by
  `scripts/asset_policy.py` because the restricted schema subset
  cannot express conditional requirements. v2.3 profiles remain
  valid under the legacy contract.
- **D — Real animal vs CGI animal.** Speaking-bird fixtures
  corrected to `cgi-animal`; a genuine captured animal is never
  automatically given fictional dialogue or a speaking voice.
- **E — Companion licensing.** OmniVoice model weights are CC-BY-NC
  (non-commercial): technically capable but NOT approved for
  commercial production. No verified commercial voice provider
  exists; the commercial voice adapter stays unsupported.
- **F — Documentation reconciled** (README, AGENTS.md, docs/07,
  docs/19, the canonical animation-scope document, the P0-006
  corrections record, BUILD_REPORT_P0, this plan, schemas/README,
  and the relevant skills/architecture files). The first-run
  registration UI is NOT claimed to exist — P0-007 is principally
  a contract + validation correction round.
- **G/H — Tests, validation, regression, reports, manifest,
  provenance** per the work order (§9–§10): the full suite must be
  green, registries regenerated if canonical data changed, and
  reports/manifest/checksums regenerated with the live GitHub head.
- P0-007 does not start P1, does not merge, and does not change the
  PR Draft state; the parent handles delivery after verifying CI.

## 11. P0-008 — Fail-closed private voice security (2026-11-22)

Work order CF-WO-P0-008. A security / production-correctness round
on the same branch; it hardens the P0-007 ownership contract
rather than starting new work. The full record is
`docs/implementation/CF-WO-P0-008-corrections.md`. Production
Corrections A–E were implemented and committed locally
(`f3e0c2b`, `6224bba`); Corrections F–G (tests + docs) are the
uncommitted change set this section records.

- **A — Mandatory requester identity.** The production voice
  resolver requires requester owner + workspace identity for a
  private v2.5 voice; a missing requester fails closed. Legacy
  v2.3 records keep their historical contract.
- **B — Owner-bound export.** A private voice export requires a
  `TrustedAuthorizationContext` issued by
  `issue_trusted_authorization_context` (the local application
  authorization boundary). A caller-created dictionary — including
  a forged `granted_by` — never authorizes anything. Provider
  transmission is a separate permission from export; export is
  owner-only even under `shared` + `workspace`.
- **C — Production timeline validation.** The validator moved from
  the test file into `scripts/timeline_policy.py`, with a strict
  v2.5 mode that fails closed on missing registry data, missing
  requester identity, missing ownership, unauthorized access, and
  unapproved voices. Narration/music/ambience/SFX timelines stay
  valid without a requester; v2.3 timelines still pass under the
  structural contract.
- **D — Duplicate test-only logic removed.** Tests import the
  production functions (`check_voice_binding`, `resolve_for_user`,
  `validate_timeline_cross_references`); a spy test proves the
  character-registration resolver calls the production resolver.
- **E — Centralized authorization.** One choke point,
  `authorize_action`, with explicit action scopes
  (`use_in_project`, `use_in_production`,
  `export_private_asset`, `transmit_to_provider`,
  `share_with_workspace`). Permission for one action never implies
  permission for another.
- **F — Security regression suite.**
  `tests/test_private_voice_security.py` (`CF-P0-008-SEC`, 74
  checks, all PASS locally), added to `tests/run-tests.sh`. It
  reproduces all three pre-fix failures (resolver without
  requester, forged/plain-dict export, timeline without
  requester) and pins the fixed behaviour.
- **G — Documentation reconciled** (schemas/README, docs/07, the
  canonical animation-scope document, BUILD_REPORT_P0, this plan,
  CHANGELOG, AGENTS.md, and the P0-008 corrections record).
- P0-008 does not start P1, does not merge, and does not change the
  PR Draft state. What stays P1: the registration UI, provider
  execution, the app/session runtime that supplies the actor
  identity at the trusted boundary (the trusted context is a
  structural type boundary, not cryptographic proof of identity),
  lip-sync/articulation generation, and the script-to-finished-
  video runtime.
