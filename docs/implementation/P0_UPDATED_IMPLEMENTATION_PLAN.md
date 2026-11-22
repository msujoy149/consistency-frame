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
| Scene Plan | `schemas/scene-plan.json` | Scenes, beats, dramatic intent, primary/secondary emotion, intensity (1–10), transitions. |
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
  skills never run together.
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
