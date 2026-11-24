# Living Architecture Report — v2.4 P0 (Brain Architecture Amendment)

**Generated:** 2026-11-23 20:17 UTC — from canonical records (`registry/*.json`,
`schemas/`, `architecture/*.yaml`, git state, `tests/last-run.json`). Do not edit the inventory
numbers by hand; regenerate with `python3 scripts/generate-report.py`.

**Product scope:** general-purpose professional AI video production
and editing system (2D/3D animation, realistic human video,
image-to-video and video-to-video, character/voice/sound consistency,
stories, web series and episodic production, cinematography, VFX,
editing, audio, post-production). Not a single-genre tool.

**Brain model (v2.4):** Consistency Frame is the CENTRAL BRAIN /
Orchestrator — creative intelligence, script understanding, skill
routing, character/project continuity, emotion/performance direction,
cinematography/editing decisions, quality requirements, production
coordination, documentation/learning governance. It is NOT a server,
API backend, cloud database or hosting platform, and not a replacement
for the companions (VoiceStudio = voice/speech, OpenMontage =
video production/editing). See
`docs/implementation/BRAIN_ARCHITECTURE_AUDIT.md`.

**Repository:** https://github.com/msujoy149/consistency-frame
**Base branch/commit:** `main` / `e1571db68ed87fb973c45960a4a3e27e09ba0d06`
**Feature branch:** `feat/cf-p1-001-trusted-session`
**Head commit:** `1dcd00182581c9f0fe27406ead0bc9655af2724f`
**GitHub branch head:** `2f66bd21001c8d0d0dce7b571539555bf658c475` (remote head of `feat/cf-p1-001-trusted-session` at
generation time; pushing this regenerated report advances the branch
head by one docs-only commit — see `docs/implementation/BUILD_REPORT_P0.md` §12)
**Architecture/report version:** v2.4 P0 (work order CF-WO-P0-001, revised)
**Previous report:** `docs/architecture/living-architecture-report-v2.3-p0.md` — the v2.3 baseline (retained, not rewritten).

## Inventory (generated from canonical records)

| Registry | Count |
|---|---|
| Skills (`registry/skills.json`) | 15 |
| Features (`registry/features.json`) | 165 |
| Workflows / intent modes (`registry/workflows.json`) | 13 |
| Adapters (`registry/adapters.json`) | 12 |
| JSON Schemas (`schemas/*.json`) | 26 |
| Routing matrix entries (`architecture/SKILL_ROUTING_MATRIX.yaml`) | 15 |
| Workflow graph nodes / edges (`architecture/WORKFLOW_GRAPH.yaml`) | 15 / 42 |
| Companion capabilities (`architecture/COMPANION_CAPABILITY_REGISTRY.yaml`) | 20 (3 exercised_recorded_run, 16 present_locally, 1 upstream_inspected_pinned_commit, 0 production_verified) |
| Agents in compatibility matrix (`architecture/AGENT_COMPATIBILITY_MATRIX.yaml`) | 10 (1 verified: Muse) |


### Skills

| Skill ID | Name | Path | Maturity | Sections |
|---|---|---|---|---|
| `skill-agency-advertising` | agency-advertising | skills/agency-advertising/SKILL.md | DOCUMENTED | 7 |
| `skill-character-consistency` | character-consistency | skills/character-consistency/SKILL.md | DOCUMENTED | 16 |
| `skill-cinematic-power` | cinematic-power | skills/cinematic-power/SKILL.md | DOCUMENTED | 5 |
| `skill-command-authority` | command-authority | skills/command-authority/SKILL.md | DOCUMENTED | 9 |
| `skill-emotional-performance` | emotional-performance | skills/emotional-performance/SKILL.md | DOCUMENTED | 7 |
| `skill-explainer-animation` | explainer-animation | skills/explainer-animation/SKILL.md | DOCUMENTED | 8 |
| `skill-humanized-production` | humanized-production | skills/humanized-production/SKILL.md | DOCUMENTED | 37 |
| `skill-kids-family-animation` | kids-family-animation | skills/kids-family-animation/SKILL.md | DOCUMENTED | 17 |
| `skill-language-authenticity` | language-authenticity | skills/language-authenticity/SKILL.md | DOCUMENTED | 9 |
| `skill-live-action-vfx` | live-action-vfx | skills/live-action-vfx/SKILL.md | DOCUMENTED | 6 |
| `skill-production-systems` | production-systems | skills/production-systems/SKILL.md | DOCUMENTED | 5 |
| `skill-realistic-person` | realistic-person | skills/realistic-person/SKILL.md | DOCUMENTED | 8 |
| `skill-resource-management` | resource-management | skills/resource-management/SKILL.md | DOCUMENTED | 9 |
| `skill-video-regeneration` | video-regeneration | skills/video-regeneration/SKILL.md | DOCUMENTED | 9 |
| `skill-voice-consistency` | voice-consistency | skills/voice-consistency/SKILL.md | DOCUMENTED | 13 |

All 15 skills are maturity `DOCUMENTED`: guidance exists in the skill
files. None is `TESTED` or `PRODUCTION_VERIFIED` as a skill in P0 —
P0 tests validate frontmatter, registries, schemas and the installer,
not the creative content of each skill.

### Features

`165` features, one per `##` section of each canonical
skill file, derived by `scripts/generate-registries.py`.

**Reconciliation note (open):** the historical claim in the README and
`docs/01` is 109 distinct systems / 120 numbered entries. That claim
uses a different counting unit and is preserved in
`registry/features.json` under `legacy_counts` as
`historical-claim-not-machine-derived`. The P0 registry count (165) must
not be presented as equal to 109/120. Reconciling the two counts is
deferred P1 work.

### Workflows / intent modes

`13` modes (`UPLOAD_ONLY`, `TEMPORARY_ASSET_USE`,
`PROJECT_CONSISTENCY`, `REGISTER_CHARACTER`, `REGISTER_VOICE_PROFILE`,
`REGISTER_SOUND_ASSET`, `GENERATE_FROM_SCRIPT`, `EDIT_EXISTING_MEDIA`,
`REFERENCE_REVIEW`, `REFERENCE_LEARN_AND_UPDATE`, `VIDEO_QC`,
`REMAKE_OR_TRANSFORM`, `REPORT_UPDATE_ONLY`). Full contracts in
`architecture/intent-modes.yaml`; enforcement in
`scripts/asset_policy.py`.

### Adapters / capability truth

| Adapter | Integration | Native skill install | Conformance | Status |
|---|---|---|---|---|
| Muse (Meta) | PACKAGED | UNSUPPORTED | NOT_TESTED | untested |
| Claude Code | NATIVE | NOT_TESTED | NOT_TESTED | untested |
| Codex | NATIVE | NOT_TESTED | NOT_TESTED | untested |
| Gemini CLI | NATIVE | NOT_TESTED | NOT_TESTED | untested |
| Antigravity | PACKAGED | NOT_TESTED | NOT_TESTED | untested |
| ChatGPT | PACKAGED | NOT_TESTED | NOT_TESTED | untested |
| OpenCode | NATIVE | NOT_TESTED | NOT_TESTED | untested |
| VoiceStudio (bundled component) | HOST_RUNTIME | NOT_TESTED | NOT_TESTED | untested |
| OpenMontage (bundled component) | HOST_RUNTIME | NOT_TESTED | NOT_TESTED | untested |
| FFmpeg / ffprobe | HOST_RUNTIME | NOT_TESTED | NOT_TESTED | untested |
| OpenTimelineIO | LIMITED | NOT_TESTED | NOT_TESTED | untested |
| Adobe Premiere Pro (UXP) | LIMITED | NOT_TESTED | NOT_TESTED | untested |

**No adapter is marked supported in P0.** A capability is supported
only after a real conformance test passes; every adapter above is
`untested` (conformance `NOT_TESTED`) or `planned`. In particular:
Muse is a knowledge pack, not a native skill install; OpenTimelineIO
is an editorial-interchange candidate, not a renderer; FFmpeg binary
presence is not a conformance test.

## Changes in P0 (since base `e1571db68ed87fb973c45960a4a3e27e09ba0d06`)

- Non-destructive installer: `scripts/sync-skills.sh` replaces
  `rm -rf .agents/skills`; `setup.sh` is core-only by default with
  opt-in `--with-components`, truthful per-component SUCCESS / PARTIAL /
  FAILED status and exit codes (fixes F1, F2).
- Canonical registries + 20 versioned JSON Schemas + asset-mode policy
  (fixes F5, F6-partial).
- Skill-first loop split: task-local draft (§9A) vs permanent canonical
  mutation on explicit user authorisation only (§9B).
- Absolute quality claims replaced by measurable, scoped targets with a
  human-review gate (fixes F7-partial; historical CHANGELOG entries
  untouched).
- Universal `-14 LUFS` retired; loudness is a named delivery profile
  (`architecture/audio-delivery-profiles.json`, `docs/19`) (fixes F8).
- Muse install claim corrected to knowledge-pack (fixes F3).
- Private-overlay validation contract + tests (fixes F4-partial:
  executable validator + tests exist; a runtime overlay adapter is
  deferred to P2).
- Tests + GitHub Actions CI (`.github/workflows/p0-ci.yml`).

### Changes in the v2.4 revision (Brain Architecture Amendment)

- P0-A audit (`docs/implementation/BRAIN_ARCHITECTURE_AUDIT.md`):
  zero server/API-backend/cloud-database claims in normative text;
  the withdrawn items never existed in code. One docs fix (v2.4
  section in `AGENTS.md`). No skill file changed.
- Intelligent Skill Routing: `architecture/SKILL_ROUTING_MATRIX.yaml`
  (15 skills, precedence 1–15, command-authority is the router) and
  `architecture/WORKFLOW_GRAPH.yaml` (42 edges, acyclic; sequential
  on dependency, parallel only when safe).
- Script-to-Performance Intelligence: four new `schema_version: "2.4"`
  schemas (`scene-plan`, `shot-plan`, `performance-plan`,
  `script-to-performance` — the combined contract). Dialogue is
  VERBATIM unless a rewrite was explicitly requested.
- Companion Capability Registry + Agent Compatibility Matrix: every
  capability carries an `evidence_level` (P0-002 §6 — 20 capabilities:
  3 `exercised_recorded_run`, 16 `present_locally`, 1
  `upstream_inspected_pinned_commit`, 0 `production_verified`); only
  Muse is verified (knowledge pack). OpenRouter is a model-routing
  layer, not a host; Colab needs a Notebook/Agent Runtime.
- Validator check 8 (canonical YAML records) + `tests/test_routing.py`
  (gates CF-P0-ROUTING-001/002/003); CI installs PyYAML.

Changed files in this branch (vs base):

```
.github/workflows/p0-ci.yml
.gitignore
AGENTS.md
CHANGELOG.md
README.md
architecture/AGENT_COMPATIBILITY_MATRIX.yaml
architecture/COMPANION_CAPABILITY_REGISTRY.yaml
architecture/SKILL_ROUTING_MATRIX.yaml
architecture/WORKFLOW_GRAPH.yaml
architecture/audio-delivery-profiles.json
architecture/intent-modes.yaml
architecture/platform-capabilities.md
characters/README.md
docs/02-extended-systems.md
docs/06-installation.md
docs/07-character-registry.md
docs/08-agency-advertising.md
docs/09-video-regeneration.md
docs/15-realistic-person.md
docs/17-command-authority.md
docs/19-audio-delivery-profiles.md
docs/architecture/ANIMATION_SCOPE_AND_PRODUCTION_MODES.md
docs/architecture/living-architecture-report-v2.3-p0.md
docs/architecture/living-architecture-report-v2.4-p0.md
docs/implementation/BRAIN_ARCHITECTURE_AUDIT.md
docs/implementation/BUILD_REPORT_P0.md
docs/implementation/CF-WO-P0-001-plan.md
docs/implementation/CF-WO-P0-002-corrections.md
docs/implementation/CF-WO-P0-003-corrections.md
docs/implementation/CF-WO-P0-004-corrections.md
docs/implementation/CF-WO-P0-005-corrections.md
docs/implementation/CF-WO-P0-006-corrections.md
docs/implementation/CF-WO-P0-007-corrections.md
docs/implementation/CF-WO-P0-008-corrections.md
docs/implementation/CF-WO-P0-009-corrections.md
docs/implementation/CF-WO-P0-010-corrections.md
docs/implementation/CF-WO-P0-011-corrections.md
docs/implementation/CF-WO-P0-012-corrections.md
docs/implementation/CF-WO-P0-014-corrections.md
docs/implementation/CF-WO-P0-015-corrections.md
docs/implementation/CF-WO-P1-001-corrections.md
docs/implementation/CHECKSUMS.txt
docs/implementation/P0_UPDATED_IMPLEMENTATION_PLAN.md
docs/implementation/build-report.json
docs/runtime/LOCAL_SESSION_AND_TRUST_BOUNDARY.md
registry/adapters.json
registry/features.json
registry/skills.json
registry/workflows.json
release-manifest.json
runtime/__init__.py
runtime/authorization.py
runtime/local_session.py
schemas/README.md
schemas/approval.json
schemas/build-report.json
schemas/character-registration.json
schemas/character.json
schemas/episode-state.json
schemas/evidence.json
schemas/installer-result.json
schemas/intake-job.json
schemas/location.json
schemas/performance-plan.json
schemas/production-profile.json
schemas/project.json
schemas/prop.json
schemas/reference-learning.json
schemas/reference-review.json
schemas/release-manifest.json
schemas/scene-plan.json
schemas/script-contract.json
schemas/script-to-performance.json
schemas/shot-plan.json
schemas/sound-asset.json
schemas/story-bible.json
schemas/timeline-manifest.json
schemas/visual-style-profile.json
schemas/voice-profile.json
schemas/wardrobe.json
scripts/asset_policy.py
scripts/atomic_write.py
scripts/generate-build-report.py
scripts/generate-registries.py
scripts/generate-report.py
scripts/sync-skills.sh
scripts/timeline_policy.py
scripts/validate-repo.py
setup.sh
skills/agency-advertising/SKILL.md
skills/character-consistency/SKILL.md
skills/cinematic-power/SKILL.md
skills/command-authority/SKILL.md
skills/emotional-performance/SKILL.md
skills/explainer-animation/SKILL.md
skills/humanized-production/SKILL.md
skills/language-authenticity/SKILL.md
skills/live-action-vfx/SKILL.md
skills/production-systems/SKILL.md
skills/realistic-person/SKILL.md
skills/video-regeneration/SKILL.md
skills/voice-consistency/SKILL.md
tests/fixtures/character-extended-valid.json
tests/fixtures/character-registration-bird-valid.json
tests/fixtures/character-registration-invalid-duplicate-id.json
tests/fixtures/character-registration-invalid-missing-id.json
tests/fixtures/character-registration-valid-bird.json
tests/fixtures/character-registration-valid-human.json
tests/fixtures/character-registration-valid.json
tests/fixtures/character-valid-v25-animal.json
tests/fixtures/character-valid.json
tests/fixtures/intake-temporary.json
tests/fixtures/performance-plan-bird.json
tests/fixtures/performance-plan-human.json
tests/fixtures/performance-plan-invalid-bird-human-lips.json
tests/fixtures/performance-plan-two-person.json
tests/fixtures/performance-plan-valid-bird.json
tests/fixtures/performance-plan-valid.json
tests/fixtures/production-profile-invalid-animation-type.json
tests/fixtures/production-profile-invalid-digital-human-live-action.json
tests/fixtures/production-profile-reference-video.json
tests/fixtures/production-profile-script-only.json
tests/fixtures/production-profile-valid-digital-human.json
tests/fixtures/registration-invitation.json
tests/fixtures/routing-profile-s1-explainer-2d.json
tests/fixtures/routing-profile-s2-stylized-3d.json
tests/fixtures/routing-profile-s4-human-bird.json
tests/fixtures/routing-profile-s5-live-action-creature.json
tests/fixtures/routing-profile-s6-real-animal.json
tests/fixtures/routing-profile-s7-video-to-video.json
tests/fixtures/routing-profile-s8-photorealistic-explainer.json
tests/fixtures/scene-plan-two-person.json
tests/fixtures/scene-plan-valid-human-bird.json
tests/fixtures/scene-plan-valid.json
tests/fixtures/script-to-performance-binding.json
tests/fixtures/script-to-performance-valid-bindings.json
tests/fixtures/script-to-performance-valid.json
tests/fixtures/shot-plan-directed.json
tests/fixtures/shot-plan-valid-human-bird.json
tests/fixtures/shot-plan-valid.json
tests/fixtures/sound-asset-valid.json
tests/fixtures/temporary-asset-use.json
tests/fixtures/timeline-valid-v23.json
tests/fixtures/timeline-valid-v25-multicharacter.json
tests/fixtures/visual-style-profile-valid.json
tests/fixtures/voice-profile-ai-generated.json
tests/fixtures/voice-profile-user-recording.json
tests/fixtures/voice-profile-valid-ai-generated.json
tests/fixtures/voice-profile-valid-user-recorded.json
tests/fixtures/voice-profile-valid.json
tests/last-run.json
tests/run-tests.sh
tests/test_atomic_write.py
tests/test_character_registration.py
tests/test_installer.sh
tests/test_installer_manifest_security.sh
tests/test_installer_metadata_failure.sh
tests/test_installer_security.sh
tests/test_installer_status.sh
tests/test_local_session_runtime.py
tests/test_modes.py
tests/test_performance_semantics.py
tests/test_private_overlay.py
tests/test_private_voice_security.py
tests/test_production_direction.py
tests/test_registries.py
tests/test_reports.py
tests/test_routing.py
tests/test_schemas.py
tests/test_session_authorization.py
tests/test_timeline_manifest.py
```

## Tests and CI evidence — status: PASS

- `P0-SHELL` — bash -n scripts/sync-skills.sh — **PASS** (exit 0)
- `P0-SHELL` — bash -n setup.sh — **PASS** (exit 0)
- `P0-SHELL` — bash -n tests/test_installer.sh — **PASS** (exit 0)
- `P0-SHELL` — bash -n tests/test_installer_security.sh — **PASS** (exit 0)
- `P0-SHELL` — bash -n tests/test_installer_manifest_security.sh — **PASS** (exit 0)
- `P0-SHELL` — bash -n tests/test_installer_metadata_failure.sh — **PASS** (exit 0)
- `P0-SHELL` — bash -n tests/test_installer_status.sh — **PASS** (exit 0)
- `P0-SHELL` — bash -n tests/run-tests.sh — **PASS** (exit 0)
- `P0-SCHEMA` — python3 scripts/validate-repo.py — **PASS** (exit 0)
- `CF-INT-023` — python3 scripts/generate-registries.py --check — **PASS** (exit 0)
- `P0-SCHEMA` — python3 tests/test_schemas.py — **PASS** (exit 0)
- `P0-ROUTING` — python3 tests/test_routing.py — **PASS** (exit 0)
- `CF-P0-ROUTING-001` — python3 tests/test_routing.py — **PASS** (exit 0)
- `CF-P0-ROUTING-002` — python3 tests/test_routing.py — **PASS** (exit 0)
- `CF-P0-ROUTING-003` — python3 tests/test_routing.py — **PASS** (exit 0)
- `CF-INT-023` — python3 tests/test_registries.py — **PASS** (exit 0)
- `CF-P0-ASSET-001` — python3 tests/test_modes.py — **PASS** (exit 0)
- `CF-P0-ASSET-002` — python3 tests/test_modes.py — **PASS** (exit 0)
- `CF-P0-ASSET-003` — python3 tests/test_modes.py — **PASS** (exit 0)
- `CF-P0-LEARN-001` — python3 tests/test_modes.py — **PASS** (exit 0)
- `CF-P0-LEARN-001` — python3 tests/test_schemas.py — **PASS** (exit 0)
- `CF-P0-PERF-001` — python3 tests/test_performance_semantics.py — **PASS** (exit 0)
- `CF-P0-PERF-002` — python3 tests/test_performance_semantics.py — **PASS** (exit 0)
- `CF-P0-PERF-003` — python3 tests/test_performance_semantics.py — **PASS** (exit 0)
- `CF-P0-PERF-004` — python3 tests/test_performance_semantics.py — **PASS** (exit 0)
- `CF-P0-PERF-005` — python3 tests/test_performance_semantics.py — **PASS** (exit 0)
- `P0-PRIVACY` — python3 tests/test_private_overlay.py — **PASS** (exit 0)
- `CF-P0-006-AC-REG` — python3 tests/test_character_registration.py — **PASS** (exit 0)
- `CF-P0-006-AC-DIR` — python3 tests/test_production_direction.py — **PASS** (exit 0)
- `CF-P0-007-AC-TIMELINE` — python3 tests/test_timeline_manifest.py — **PASS** (exit 0)
- `CF-P0-008-SEC` — python3 tests/test_private_voice_security.py — **PASS** (exit 0)
- `CF-INT-014` — bash tests/test_installer.sh — **PASS** (exit 0)
- `CF-INT-015` — bash tests/test_installer.sh — **PASS** (exit 0)
- `CF-INT-015` — bash tests/test_installer_security.sh — **PASS** (exit 0)
- `CF-P0-SEC-MANIFEST-01` — bash tests/test_installer_manifest_security.sh — **PASS** (exit 0)
- `CF-P0-SEC-MANIFEST-02` — bash tests/test_installer_manifest_security.sh — **PASS** (exit 0)
- `CF-P0-SEC-MANIFEST-03` — bash tests/test_installer_manifest_security.sh — **PASS** (exit 0)
- `CF-P0-SEC-MANIFEST-04` — bash tests/test_installer_manifest_security.sh — **PASS** (exit 0)
- `CF-P0-SEC-METADATA-05` — bash tests/test_installer_metadata_failure.sh — **PASS** (exit 0)
- `CF-P0-SEC-METADATA-06` — bash tests/test_installer_metadata_failure.sh no-change — **PASS** (exit 0)
- `CF-P0-SEC-METADATA-07` — bash tests/test_installer_metadata_failure.sh failed-no-backup — **PASS** (exit 0)
- `CF-P0-014-INST` — bash tests/test_installer_status.sh — **PASS** (exit 0)
- `CF-P0-014-PIN` — bash tests/test_installer_status.sh — **PASS** (exit 0)
- `CF-P0-015-WT` — bash tests/test_installer_status.sh — **PASS** (exit 0)
- `CF-P1-001-SESSION` — python3 tests/test_local_session_runtime.py — **PASS** (exit 0)
- `CF-P1-001-AUTHZ` — python3 tests/test_session_authorization.py — **PASS** (exit 0)
- `CF-P0-ATOMIC-001` — python3 tests/test_atomic_write.py — **PASS** (exit 0)
- `P0-DIFF-CHECK` — git diff --check — **PASS** (exit 0)
- `CF-INT-023` — python3 scripts/generate-report.py — **PASS** (exit 0)
- `CF-INT-023` — python3 scripts/generate-report.py --check — **PASS** (exit 0)
- `CF-P0-ROUTING-004` — python3 tests/test_routing.py — **PASS** (exit 0)
- `CF-P0-REPORT-001` — python3 tests/test_reports.py — **PASS** (exit 0)
- `CF-P0-REPORT-002` — python3 tests/test_reports.py — **PASS** (exit 0)
- `CF-P0-REPORT-003` — python3 tests/test_reports.py — **PASS** (exit 0)
- `CF-P0-REPORT-004` — python3 tests/test_reports.py — **PASS** (exit 0)
- `CF-P0-REPORT-005` — python3 tests/test_reports.py — **PASS** (exit 0)

CI workflow: `.github/workflows/p0-ci.yml` (runs on pull requests and
pushes to the feature branch). Remote CI PASSED on
`33dc78b88bba9cc83ecfc35c7b28a3ef3de7f90b` — 2/2 checks, push run #83
https://github.com/msujoy149/consistency-frame/actions/runs/45063530337
and PR run #84
https://github.com/msujoy149/consistency-frame/actions/runs/45063535304
(draft PR https://github.com/msujoy149/consistency-frame/pull/1).
The `p0-test-results` artifact (784 bytes, ID 14770342860, digest
sha256:017c91538a628aeda58eaada9b0563f0bab43f62e4abf42a200d6011be73cb44)
holds 47 recorded test-run entries, 35 distinct test IDs, 28 distinct
command strings, all PASS; its `last-run.json` is byte-for-byte
identical to the P0-006 ZIP's `tests/last-run.json`. Historical
record (P0-005): remote CI PASSED on
`24d2e6274f1fe2ee42b86c20ecf083e0d4b3c4d4` — 2/2 checks, push run #47
https://github.com/msujoy149/consistency-frame/actions/runs/45059388184
and PR run #48
https://github.com/msujoy149/consistency-frame/actions/runs/45059393245.
Historical record (P0-002): remote CI PASSED on
`fcf311ef79c5f10a4248f026a5f667109c584831` — 2/2 checks, run
https://github.com/msujoy149/consistency-frame/actions/runs/45046203236.

## Known issues and deferred work

1. **Registry reconciliation (P1):** 165 derived features vs the
   historical 109/120 claim — reconcile counting units and update the
   README/docs/01 from the canonical registry.
2. **Adapter conformance (P1/P5):** all 12 adapters are NOT_TESTED.
   Conformance tests per host/editor are needed before any "supported"
   claim.
3. **Private-overlay runtime adapter (P2):** P0 adds schemas, validation
   and tests; a runtime adapter that resolves `CONSISTENCY_FRAME_CHARACTERS`
   is not built in P0.
4. **`setup.sh --with-components` end-to-end run (NOT RUN):** executing
   it downloads ~5 GB of components plus ~1 GB of Python/Node deps;
   it was verified by syntax check, dry-run core sync and failure-path
   tests only. Run it on a machine with network + disk before claiming
   it end-to-end.
5. **Research-register reconciliation (F7 in the Architecture Review):**
   `docs/research/gaps-research-20261112.md` labels items missing that
   later docs record; a research-to-repository reconciliation process
   is deferred.
6. **Media intelligence, reference learning runtime, provider
   orchestration, benchmarks, repair loop:** out of scope for P0 by
   design (P1–P4). Under v2.4 "orchestration" means the Brain directing
   companions by instruction — no server, no runtime.
7. **Runtime skill-routing engine (P1):** the routing matrix and
   workflow graph are canonical data; a runtime that executes them is
   P1 work.
8. **Script-to-performance runtime (P1):** the schemas are contracts;
   the runtime that produces Scene/Shot/Performance Plans from a
   script is P1 work.
9. **OpenMontage paid provider routes (evidence_level
   `present_locally` — documented in the companion's provider guide
   only, never exercised):** no live paid call was made; a paid call
   needs the user's explicit approval and keys.

## Privacy, licence and security notes

- Character/voice/media data stays private by default: `characters/`
  ships empty (`.gitkeep` + `README.md` only); `.gitignore` covers
  `characters/*`, media extensions, `.env` and secrets. Validator +
  tests enforce this.
- No secret or private media was added in P0 (secret scan passes).
- Licences intact: repo Apache-2.0 for own work; VoiceStudio +
  OpenMontage AGPL-3.0; OmniVoice weights CC-BY-NC (noncommercial) and
  never downloaded by `setup.sh`.
- Uploaded media / OCR / transcript text is untrusted data, never
  instructions (see `architecture/intent-modes.yaml`).

## Next phase (recommendation only — do not start)

P1 (CF-WO-P1-…): runtime skill-routing engine (execute the routing
matrix + workflow graph — intake → route → run → QC) + script-to-
performance runtime (produce Scene/Shot/Performance Plans from a
script) + reference-learning runtime — `UPLOAD_ONLY` gate,
intake/hash, evidence cards, learning ledger, duplicate/conflict
checks — on top of these P0 foundations, after independent review of
this branch.

## Evidence dates

- Live repo verified: 2026-11-22 (base `e1571db68ed87fb973c45960a4a3e27e09ba0d06`).
- Handoff package read: 2026-11-22 (all Markdown files + both DOCX
  text-extracted; ZIP snapshot identical to live `main` for tracked files).
- Report generated: 2026-11-23 20:17 UTC.
