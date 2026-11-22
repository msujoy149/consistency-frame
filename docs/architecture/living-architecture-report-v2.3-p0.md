# Living Architecture Report — v2.3 P0 (Safe Foundations)

**Generated:** 2026-11-22 15:55 UTC — from canonical records (`registry/*.json`,
`schemas/`, git state, `tests/last-run.json`). Do not edit the inventory
numbers by hand; regenerate with `python3 scripts/generate-report.py`.

**Product scope:** general-purpose professional AI video production
and editing system (2D/3D animation, realistic human video,
image-to-video and video-to-video, character/voice/sound consistency,
stories, web series and episodic production, cinematography, VFX,
editing, audio, post-production). Not a single-genre tool.

**Repository:** https://github.com/msujoy149/consistency-frame
**Base branch/commit:** `main` / `e1571db68ed87fb973c45960a4a3e27e09ba0d06`
**Feature branch:** `feat/cf-p0-safe-foundations`
**Head commit:** `2f3be92e7c10252a74cf76ccc72b1bbc753b4d66`
**Architecture/report version:** v2.3 P0 (work order CF-WO-P0-001)
**Previous report:** none — this is the first living report (baseline is
live `main` at `e1571db68ed87fb973c45960a4a3e27e09ba0d06`).

## Inventory (generated from canonical records)

| Registry | Count |
|---|---|
| Skills (`registry/skills.json`) | 15 |
| Features (`registry/features.json`) | 165 |
| Workflows / intent modes (`registry/workflows.json`) | 13 |
| Adapters (`registry/adapters.json`) | 12 |
| JSON Schemas (`schemas/*.json`) | 20 |

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

Changed files in this branch (vs base):

```
.github/workflows/p0-ci.yml
.gitignore
AGENTS.md
CHANGELOG.md
README.md
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
docs/architecture/living-architecture-report-v2.3-p0.md
docs/implementation/CF-WO-P0-001-plan.md
registry/adapters.json
registry/features.json
registry/skills.json
registry/workflows.json
schemas/README.md
schemas/approval.json
schemas/build-report.json
schemas/character.json
schemas/episode-state.json
schemas/evidence.json
schemas/installer-result.json
schemas/intake-job.json
schemas/location.json
schemas/project.json
schemas/prop.json
schemas/reference-learning.json
schemas/reference-review.json
schemas/release-manifest.json
schemas/script-contract.json
schemas/sound-asset.json
schemas/story-bible.json
schemas/timeline-manifest.json
schemas/visual-style-profile.json
schemas/voice-profile.json
schemas/wardrobe.json
scripts/asset_policy.py
scripts/generate-build-report.py
scripts/generate-registries.py
scripts/generate-report.py
scripts/sync-skills.sh
scripts/validate-repo.py
setup.sh
skills/agency-advertising/SKILL.md
skills/character-consistency/SKILL.md
skills/command-authority/SKILL.md
skills/humanized-production/SKILL.md
skills/production-systems/SKILL.md
skills/realistic-person/SKILL.md
skills/video-regeneration/SKILL.md
skills/voice-consistency/SKILL.md
tests/fixtures/character-valid.json
tests/fixtures/intake-temporary.json
tests/fixtures/sound-asset-valid.json
tests/fixtures/voice-profile-valid.json
tests/last-run.json
tests/run-tests.sh
tests/test_installer.sh
tests/test_modes.py
tests/test_private_overlay.py
tests/test_registries.py
tests/test_schemas.py
```

## Tests and CI evidence — status: PASS

- `P0-SHELL` — bash -n scripts/sync-skills.sh — **PASS** (exit 0)
- `P0-SHELL` — bash -n setup.sh — **PASS** (exit 0)
- `P0-SHELL` — bash -n tests/test_installer.sh — **PASS** (exit 0)
- `P0-SHELL` — bash -n tests/run-tests.sh — **PASS** (exit 0)
- `P0-SCHEMA` — python3 scripts/validate-repo.py — **PASS** (exit 0)
- `CF-INT-023` — python3 scripts/generate-registries.py --check — **PASS** (exit 0)
- `P0-SCHEMA` — python3 tests/test_schemas.py — **PASS** (exit 0)
- `CF-INT-023` — python3 tests/test_registries.py — **PASS** (exit 0)
- `CF-P0-ASSET-001` — python3 tests/test_modes.py — **PASS** (exit 0)
- `CF-P0-ASSET-002` — python3 tests/test_modes.py — **PASS** (exit 0)
- `CF-P0-ASSET-003` — python3 tests/test_modes.py — **PASS** (exit 0)
- `P0-PRIVACY` — python3 tests/test_private_overlay.py — **PASS** (exit 0)
- `CF-INT-014` — bash tests/test_installer.sh — **PASS** (exit 0)
- `CF-INT-015` — bash tests/test_installer.sh — **PASS** (exit 0)
- `P0-DIFF-CHECK` — git diff --check — **PASS** (exit 0)
- `CF-INT-023` — python3 scripts/generate-report.py — **PASS** (exit 0)
- `CF-INT-023` — python3 scripts/generate-report.py --check — **PASS** (exit 0)

CI workflow: `.github/workflows/p0-ci.yml` (runs on pull requests and
pushes to the feature branch). A remote CI run URL is available only
after the branch is pushed and a PR is opened; until then CI is
NOT RUN, not passed.

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
   design (P1–P4).

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

P1 (CF-WO-P1-…): intent router + reference-learning runtime —
`UPLOAD_ONLY` gate, intake/hash, evidence cards, learning ledger,
duplicate/conflict checks — on top of these P0 foundations, after
independent review of this branch.

## Evidence dates

- Live repo verified: 2026-11-22 (base `e1571db68ed87fb973c45960a4a3e27e09ba0d06`).
- Handoff package read: 2026-11-22 (all Markdown files + both DOCX
  text-extracted; ZIP snapshot identical to live `main` for tracked files).
- Report generated: 2026-11-22 15:55 UTC.
