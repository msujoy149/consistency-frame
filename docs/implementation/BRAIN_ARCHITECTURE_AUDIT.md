# Status addendum — 2026-11-26 (CF-WO-P1-004)

This addendum records what changed after the audit below was
written. It does not rewrite the audit's history: the original
text stands as written on 2026-11-22, and this section is the
only place that reports later status.

- **Runtime skill-routing engine — DONE (P1-002).**
  `runtime/skill_router.py` now executes the routing matrix and
  workflow graph as deterministic workflow plans. Record:
  `docs/implementation/CF-WO-P1-002-corrections.md`.
- **Script-to-performance runtime — DONE (P1-003).**
  `runtime/script_to_performance.py` now produces Scene, Shot and
  Performance Plans plus the binding record from a script. Record:
  `docs/implementation/CF-WO-P1-003-corrections.md`. The
  Addendum-01 stage gates (G1–G6) and P0–P3 complexity tiers were
  integrated as documentation in the same round.
- **Production orchestration runtime — DONE (P1-004).**
  `runtime/production_orchestrator.py` (job state machine,
  production-analysis validation, G1–G6 gate enforcement, QC
  correction tasks) and `runtime/task_compiler.py`
  (deterministic provider-neutral task packets, provider matching
  on evidenced capabilities) now sit on top of the P1-001/002/003
  runtimes. Five new schemas (v2.5): `production-analysis.json`,
  `character-design-proposal.json`, `task-packet.json`,
  `gate-state.json`, `provider-capability.json`. The provider
  registry (`registry/providers.json`) is compiled from the
  `providers:` section of
  `architecture/COMPANION_CAPABILITY_REGISTRY.yaml`. Record:
  `docs/implementation/CF-WO-P1-004-corrections.md`; runtime
  contract: `docs/runtime/PRODUCTION_ORCHESTRATOR_RUNTIME.md`.
- **Adapter conformance tests — STILL OPEN.** All adapters
  remain NOT_TESTED for formal conformance. One clarification:
  Muse's knowledge-pack path is USED DAILY in this account since
  2026-11-12 (usage-exercised), which is not the same as a formal
  conformance test — the formal test (`CF-P0-ADAPTER-001`) is
  still to be run. Native Muse custom-skill installation remains
  UNSUPPORTED, and Muse has no media execution capability (it
  directs providers and tools only). All other hosts remain
  NOT_TESTED. See the P1-004 corrections record §2.
- **Registry count reconciliation — UNCHANGED.** The derived
  feature count is now 173 (was 165 at audit time); the
  historical 109/120 claim is a different counting unit and is
  unchanged.
- **Private-overlay runtime adapter — STILL DEFERRED to P2.**
- **OpenMontage paid provider routes — STILL NOT VALIDATED
  LIVE.** Paid third-party routes are recorded as NOT_TESTED in
  the provider registry. No live paid call is made without the
  user's explicit approval and keys.
- **Timeline manifest — DONE (P0-007, contract) and consumed by
  P1-003/004 as a contract; no timeline manifest is produced by
  the P1-004 orchestrator.** The `wf-generate-from-script`
  workflow's stated outputs include a timeline plan, so all
  workflows remain `SCHEMA_DEFINED` until a runtime builds one.

---

# Brain Architecture Audit — v2.4 Amendment (P0-A)

**Date:** 2026-11-22 · **Branch:** `feat/cf-p0-safe-foundations` ·
**Base:** `main` / `e1571db68ed87fb973c45960a4a3e27e09ba0d06` ·
**Governing spec:** BRAIN ARCHITECTURE AMENDMENT v2.4 (user, 2026-11-22,
voice call — supersedes the v2.3 server-management interpretation).

**Scope:** all 15 skills in `skills/`, `architecture/`, `registry/`,
`schemas/`, `scripts/`, `docs/` (except `docs/research/`, which is
historical research and is never rewritten), `setup.sh`, `README.md`,
`AGENTS.md`. The companion plugin copies in `components/` were inspected
for the capability registry only; their internal code was NOT modified.

**Method:** exact-string greps over the repo (commands recorded below),
skill-by-skill inventory check against `registry/skills.json` and the
filesystem, and a mode-by-mode mapping against
`scripts/asset_policy.py` + `architecture/intent-modes.yaml`.

## 1. Headline verdict

The v2.3 P0 built **no server, no API backend and no central database**,
so there is nothing to withdraw in code. The amendment's WITHDRAWN items
(Central Server Manager, own-API implementation) do not exist anywhere
in the repo. The audit found **zero** claims of a Consistency Frame
server, API backend, cloud database or hosting platform in normative
text. The only related words are companion-internal or external-editor
APIs and the private "Character Database" concept (see §2) — all
verdict KEEP with a clarification note.

Grep evidence (run 2026-11-22, repo root, excluding `.git`,
`components/`, `.agents`, `docs/research/`):

```text
grep -rniE "central server|server manager|api backend|own api|api server|cloud database|central database|hosting platform|video-generation server|audio-generation server" \
  --include="*.md" --include="*.json" --include="*.yaml" --include="*.sh" --include="*.py" .
→ 0 matches

grep -rni "server" <same set> → 0 matches
grep -rni "database" <same set> → 1 match (see F-01)
grep -rniE "\bapi\b" <same set, excluding api-key / api. / GitHub API> → companion + editor only (see F-02…F-04)
grep -rniE "central|manager|orchestrat" <same set> → unrelated word senses only (see F-05…F-07)
```

## 2. Findings (every hit, with verdict)

| ID | Location | Text | Verdict | Reason |
|---|---|---|---|---|
| F-01 | `skills/character-consistency/SKILL.md:30` | "Save this character in my permanent Character Database" | **KEEP** | "Character Database" is the user's private character registry (private overlay, `characters/` — local, never committed, never a cloud service). It is a registry concept, not a Consistency Frame database server. Clarified in §4 mode mapping; no text change needed. |
| F-02 | `docs/06-installation.md:79,85,185,208,225,243–244`, `setup.sh:164,174–176,180,182,234`, `CHANGELOG.md:157–158` | VoiceStudio Python API (`bun run setup:api`, `dev:api`) | **KEEP** | This is the companion VoiceStudio's own local API, run on the user's machine. It is not a Consistency Frame API backend and is not presented as one. The Brain directs VoiceStudio; it does not own or re-implement its API. |
| F-03 | `architecture/platform-capabilities.md:51` | Premiere Pro UXP "needs a version-tested API" | **KEEP** | Refers to Adobe's external editor API, a conformance precondition. Not a Consistency Frame API. |
| F-04 | `architecture/platform-capabilities.md:58` | "Capability records expire when a model version, API, pricing, terms or feature support changes" | **KEEP** | Generic expiry rule for third-party capability records. Not a claim that the Brain exposes an API. |
| F-05 | `skills/video-regeneration/SKILL.md:20,41`, `skills/kids-family-animation/SKILL.md:173,181`, `docs/09-video-regeneration.md:41,58` | "central message", "central idea", "Central composition", "central safe area" | **KEEP** | Unrelated word sense (story centre / frame centre). Not "central server/manager". |
| F-06 | `docs/implementation/BUILD_REPORT_P0.md:248`, `docs/implementation/build-report.json:166`, `scripts/generate-build-report.py:90,98,296`, `scripts/generate-report.py:209`, `docs/architecture/living-architecture-report-v2.3-p0.md:245` | "provider orchestration" listed as out-of-scope P1–P4 work | **KEEP (reframed)** | A deferred-scope label, not a built component. Under v2.4 "orchestration" means the Brain directing companions by instruction — no server, no runtime. The v2.4 plan (`docs/implementation/P0_UPDATED_IMPLEMENTATION_PLAN.md`) records this reframing; no code change. |
| F-07 | `docs/implementation/CF-WO-P0-001-plan.md` | (no server/API/database mention) | **KEEP** | The v2.3 plan is a historical record. It is not rewritten; the v2.4 revision lives in `P0_UPDATED_IMPLEMENTATION_PLAN.md`. |
| F-08 | `AGENTS.md` § "P0 safe foundations (v2.3…)" | No server/API/database claim | **FIX (docs only)** | The section is accurate for v2.3 but does not state the v2.4 brain model. Added a "v2.4 Brain Architecture Amendment" section to `AGENTS.md` stating: Brain only, no server/API/database; three-repo model; routing matrix + workflow graph + script-to-performance schemas are the canonical records. No skill content touched. |

**Documentation claims contradicting v2.4: none found.** The single
documentation change made in this audit is F-08 (AGENTS.md v2.4
section). No skill file was modified, deleted or rewritten.

## 3. Skill inventory verification (15/15)

Filesystem (`skills/*/SKILL.md`), `registry/skills.json` and the
validator agree. Verified with `python3 scripts/validate-repo.py`
(checks `registries` + `skill_frontmatter`) and
`python3 tests/test_registries.py` — both PASS; see test evidence in
`docs/implementation/BUILD_REPORT_P0.md` §4 (v2.4 run).

| # | Skill | ID | Maturity | Frontmatter `name` == dir |
|---|---|---|---|---|
| 1 | agency-advertising | skill-agency-advertising | DOCUMENTED | yes |
| 2 | character-consistency | skill-character-consistency | DOCUMENTED | yes |
| 3 | cinematic-power | skill-cinematic-power | DOCUMENTED | yes |
| 4 | command-authority | skill-command-authority | DOCUMENTED | yes |
| 5 | emotional-performance | skill-emotional-performance | DOCUMENTED | yes |
| 6 | explainer-animation | skill-explainer-animation | DOCUMENTED | yes |
| 7 | humanized-production | skill-humanized-production | DOCUMENTED | yes |
| 8 | kids-family-animation | skill-kids-family-animation | DOCUMENTED | yes |
| 9 | language-authenticity | skill-language-authenticity | DOCUMENTED | yes |
| 10 | live-action-vfx | skill-live-action-vfx | DOCUMENTED | yes |
| 11 | production-systems | skill-production-systems | DOCUMENTED | yes |
| 12 | realistic-person | skill-realistic-person | DOCUMENTED | yes |
| 13 | resource-management | skill-resource-management | DOCUMENTED | yes |
| 14 | video-regeneration | skill-video-regeneration | DOCUMENTED | yes |
| 15 | voice-consistency | skill-voice-consistency | DOCUMENTED | yes |

All 15 are maturity `DOCUMENTED`. None is `TESTED` or
`PRODUCTION_VERIFIED` as creative content in P0 — P0 tests validate
frontmatter, registries, schemas and the installer, not the creative
content of each skill. That limitation is unchanged by v2.4 and is
recorded honestly here and in the living report.

**Architecture records audited:** `architecture/intent-modes.yaml`
(13 modes, matches `scripts/asset_policy.py` `MODES` and
`registry/workflows.json`), `architecture/audio-delivery-profiles.json`
(named delivery profiles — no universal loudness target),
`architecture/platform-capabilities.md` (capability truth; all
adapters NOT_TESTED, none supported). No contradictions with v2.4
found in any of them.

## 4. v2.4 mode mapping (ONE-OFF vs RECURRING)

The amendment defines two production modes. They map onto the existing
asset modes in `scripts/asset_policy.py` as follows. No code change
was needed: the policy already enforces the mapping; this table is the
canonical statement of it.

### ONE-OFF — supplied assets are temporary; no permanent registration

| Asset mode | Role in ONE-OFF | Permanent record? |
|---|---|---|
| `UPLOAD_ONLY` | Intake only: store in temporary intake, show available commands | No |
| `TEMPORARY_ASSET_USE` | Use supplied assets for the current job only | No |
| `GENERATE_FROM_SCRIPT` | Plan + produce from the script (dialogue VERBATIM by default) | No |
| `EDIT_EXISTING_MEDIA` | Edit via verified adapters only | No |
| `REFERENCE_REVIEW` | Analyse a reference, timecoded report only | No (never mutates skills) |
| `VIDEO_QC` | Inspect and report defects | No |
| `REMAKE_OR_TRANSFORM` | Transform only as expressly requested, with rights/provenance check | No |

### RECURRING PROJECT / SERIES — stable IDs across tools and episodes

| Asset mode | Role in RECURRING | Permanent record? |
|---|---|---|
| `PROJECT_CONSISTENCY` | Resolve approved Character IDs, reference images, Voice Profiles, recurring Sound Assets, Visual Style, Wardrobe, Props, Locations, Story Continuity by stable ID; load private project records; reuse by stable ID | No (loads existing records; silent create/overwrite/merge/global registration forbidden) |
| `REGISTER_CHARACTER` | Permanent character registration | Yes — only with explicit authorisation + name + unique ID + approved reference |
| `REGISTER_VOICE_PROFILE` | Permanent voice-profile registration | Yes — only with explicit authorisation + rights/consent + character link + reference audio |
| `REGISTER_SOUND_ASSET` | Permanent sound-asset registration | Yes — only with explicit instruction + source + licence/permission + owner + project scope |
| `REFERENCE_LEARN_AND_UPDATE` | Canonical learning: evidence-backed candidate as a reviewable patch | No direct write (permanent canonical change only on explicit user instruction, via reviewable branch — command-authority §9B) |
| `REPORT_UPDATE_ONLY` | Regenerate reports from canonical records | No (never changes production rules) |

**Rules that carry over unchanged:** a mode is never inferred from an
upload alone; voice and sound are separate record types linked by ID
only (a character record must not embed voice/sound data); the user's
original dialogue is preserved unless rewriting is explicitly
requested (`GENERATE_FROM_SCRIPT` dialogue mode default
`VERBATIM_SCRIPT`, `script-contract.json`); permanent registration and
canonical learning happen only on explicit authorisation.

## 5. Gaps found (v2.4 requirements with no prior record)

These are the gaps P0-B and P0-C close. Each is a new canonical
record, not a skill change.

| # | v2.4 requirement | Prior state | Closed by (v2.4 P0) |
|---|---|---|---|
| G-01 | Canonical Skill Routing Engine (per-skill trigger, non-trigger, inputs, outputs, dependencies, precedence, conflicts, modes, quality gate, approval conditions) | Missing — routing was implicit in command-authority prose | `architecture/SKILL_ROUTING_MATRIX.yaml` |
| G-02 | Execution graph: which skills run in which order; sequential on dependency, parallel only when safe | Missing | `architecture/WORKFLOW_GRAPH.yaml` (acyclic, tested) |
| G-03 | Script-to-Performance Intelligence: scene/beat/dialogue-line analysis contracts (emotion, expression, gaze, posture, breathing, voice, lip-sync, camera, music/SFX, editing rhythm) | Partial — `schemas/script-contract.json` had dialogue + shots + performance cues as plain strings | `schemas/script-to-performance.json` (combined contract) + `schemas/scene-plan.json`, `schemas/shot-plan.json`, `schemas/performance-plan.json` |
| G-04 | Companion Capability Registry (VoiceStudio + OpenMontage, verified capabilities only) | Partial — `registry/adapters.json` + `architecture/platform-capabilities.md` listed the companions as adapters, without per-capability evidence | `architecture/COMPANION_CAPABILITY_REGISTRY.yaml` (capabilities grounded in the local plugin copies on disk) |
| G-05 | Agent Compatibility Matrix (verified, not claimed) | Partial — `registry/adapters.json` (12 adapters, all NOT_TESTED) + `architecture/platform-capabilities.md` | `architecture/AGENT_COMPATIBILITY_MATRIX.yaml` (only Muse verified, via the knowledge-pack path used in this account; every other agent untested) |
| G-06 | Three-repo model stated explicitly (Brain / Voice / Video) | Implicit — `setup.sh` clones the two companions as plugins; `docs/06` describes them | This audit (§6) + `docs/implementation/P0_UPDATED_IMPLEMENTATION_PLAN.md` + `AGENTS.md` v2.4 section |

## 6. Three-repo architecture (as audited)

- **(A) Consistency Frame — Brain / Orchestrator.** Creative
  intelligence, script understanding, skill routing, character/project
  continuity, emotion/performance direction, cinematography/editing
  decisions, quality requirements, production coordination,
  documentation/learning governance. This repo. It holds generic
  reusable knowledge, skills, schemas, adapters, tests and docs only.
- **(B) VoiceStudio — Voice/Speech Specialist.** Voice references,
  cloning/design, narration, dubbing, speech processing. Local plugin
  copy at `components/voicestudio` (v0.5.8, AGPL-3.0). The Brain
  directs it; its internal code is never silently modified or
  replaced. Verified capabilities only — see
  `architecture/COMPANION_CAPABILITY_REGISTRY.yaml`.
- **(C) OpenMontage — Video Production/Editing Specialist.** Video
  production, image/video tools, composition, editing, rendering,
  audio, post-production. Local plugin copy at
  `components/openmontage` (AGPL-3.0). Same rule: directed, never
  silently modified. Verified capabilities only — see the registry.

Private character images, voice samples, user media, credentials and
personal project data are NEVER committed to the public Brain repo;
they live in the user-controlled private overlay. The Brain requires
no separate Consistency Frame cloud database or server.

## 7. What was NOT changed by this audit

- No skill file was modified, deleted or rewritten (command-authority
  §9B: canonical skill changes need explicit user authorisation).
- No server, API backend, database or hosting code exists or was added.
- No Master Prompt file was touched (`~/workspace/video-production/`
  is out of scope for this work).
- Historical records (`CHANGELOG.md` entries, `docs/research/`,
  `docs/implementation/CF-WO-P0-001-plan.md`) were not rewritten.

## 8. Deferred to P1 (not P0)

- **Runtime skill-routing engine:** the routing matrix and workflow
  graph are canonical data; a runtime that executes them (intake →
  route → run → QC) is P1 work. Until then the matrix is the
  human/agent-readable routing contract.
- **Adapter conformance tests:** all adapters remain NOT_TESTED; no
  "supported" claim until a real conformance test passes.
- **Registry count reconciliation:** 165 derived features vs the
  historical 109/120 claim (different counting units) — unchanged.
- **Private-overlay runtime adapter:** deferred to P2 (unchanged).
- **OpenMontage paid provider routes:** the companion's provider
  guide lists paid third-party routes (Kling, Veo, fal, OpenAI, …).
  None was validated live in this P0; they are recorded as
  NOT_VERIFIED in the companion registry. A live paid call is never
  made without the user's explicit approval and keys.
- **Script-to-performance runtime:** the schemas are contracts; the
  runtime that produces Scene/Shot/Performance Plans from a script
  is P1 work.
