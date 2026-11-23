# Changelog

All notable changes to Consistency Frame are recorded here. Releases use
semantic-style versioning: small updates bump the minor number (2.1,
2.2), big breaking changes bump the major number (3.0). Every release
lists what changed.

## [Unreleased]

### Added

- P0-008 fail-closed private voice security (2026-11-22, branch `feat/cf-p0-safe-foundations`; corrections record `docs/implementation/CF-WO-P0-008-corrections.md`; production head `6224bba`, local base `5574589`): (A) the production voice resolver now REQUIRES requester owner + workspace identity for a private v2.5 voice (a missing requester is never an authorized internal request; no silent fallback to the character's owner); legacy v2.3 records keep their historical contract. (B) A private voice export requires a `TrustedAuthorizationContext` issued by `issue_trusted_authorization_context` in `scripts/asset_policy.py` — a caller-created authorization dictionary (including a forged `granted_by`) never authorizes anything; the context is checked against the voice on every point (actor = owner in the voice workspace, issuer = owner, explicit `export_private_asset` action, non-empty scope, exact character + voice binding, not expired, not revoked); provider transmission is a separate permission from export and export is owner-only even under `shared` + `workspace`. (C) Timeline cross-reference validation moved from the test file into production (`scripts/timeline_policy.py`), with a strict v2.5 mode that fails closed on missing registry data, missing requester identity, missing ownership, unauthorized access, and unapproved voices, while narration/music/ambience/SFX timelines stay valid without a requester and v2.3 timelines still pass. (D) Duplicate test-only authorization logic removed — tests import the production functions. (E) All production access decisions centralized in `authorize_action` with explicit action scopes (`use_in_project`, `use_in_production`, `export_private_asset`, `transmit_to_provider`, `share_with_workspace`); permission for one action never implies another. (F) New regression suite `tests/test_private_voice_security.py` (`CF-P0-008-SEC`, 74 checks, all PASS locally), added to `tests/run-tests.sh`; the before/after reproduction (`p0-008-repro-before.txt` / `p0-008-repro-after.txt`) shows all three pre-fix failures fixed. (G) Documentation reconciled (schemas/README, docs/07, the canonical animation-scope document, BUILD_REPORT_P0, the implementation plan, AGENTS.md). The trusted context is a structural (type) boundary, not cryptographic proof of identity — the P1 app/session runtime must supply the actor identity at the boundary. P0 only — no P1 runtime started, no merge, PR #1 Ready for Review, NOT merged.
- P0-007 final autonomous completion (2026-11-22, branch `feat/cf-p0-safe-foundations`; corrections record `docs/implementation/CF-WO-P0-007-corrections.md`): (A) the audio-visual timeline contract is complete — `schemas/timeline-manifest.json` is v2.5 (additive: `schema_version: ["2.3", "2.5"]`, no existing required field removed or retyped; video-clip + shot bindings, audio-clip + dialogue bindings, synchronization groups, hierarchy, and real cross-reference validation in `tests/test_timeline_manifest.py`; valid v2.3 timelines still pass); (B) private character and voice ownership is a structured record (`ownership`: `owner_id`, `workspace_id`, `visibility`, `sharing` — opaque local IDs, private by default) in `schemas/character-registration.json` (required) and `schemas/voice-profile.json`, enforced by `scripts/asset_policy.py`; the production resolver requires BOTH the Character ID + Voice Profile binding AND matching ownership — same Character ID with a different owner or workspace is REJECTED; the old free-text `ownership_scope` is kept only as a deprecated legacy field; (C) conditional v2.5 voice-profile validation (user-recorded vs AI-generated rules, approval states, consent rules — `consent_status` governs, `approval_status` agrees with `status`, `not-required` legitimate only with `human_voice_donor: false`) enforced by the Python validators because the restricted schema subset cannot express conditional requirements, with schema and validators pinned to agree on every record; v2.3 profiles remain valid; (D) real animal vs CGI animal fixed — the speaking-parrot fixtures are `cgi-animal` (Kiki, `character_type: "CGI Animal"`), the S6 red fox is the only `real-animal` left in fixtures, species matching for articulation is by substring ("African grey parrot" → bird-beak), and a listening line needs no voice profile while a speaking line still does; (E) companion licensing recorded — OmniVoice model weights are CC-BY-NC (non-commercial), verified against the live Hugging Face model card and `model_licenses.json`; technically capable but NOT approved for commercial production, no verified commercial voice provider exists, the commercial voice adapter stays unsupported, and `production_verified` stays 0 (an internal VoiceStudio GGUF README claims Apache-2.0 for the weights, contradicting every other record — the restrictive record governs, and the conflict is flagged for an upstream check); (F) documentation reconciled (README, AGENTS.md, docs/07, the canonical animation-scope document, the P0-006 corrections record, the implementation plan, schemas/README — docs/19 needed no change); the first-run registration UI is NOT claimed to exist; (G) full suite green: 48 recorded test-run entries PASS (36 distinct test IDs, 29 distinct command strings), 0 failures, 0 skipped; (H) reports, living report, release manifest, and detached checksums regenerated with the live GitHub head. P0 only — no P1 runtime started, no merge, PR stays Draft.
- P0-006 animation-first, style-agnostic production architecture (2026-11-22, branch `feat/cf-p0-safe-foundations`; corrections record `docs/implementation/CF-WO-P0-006-corrections.md`, canonical reference `docs/architecture/ANIMATION_SCOPE_AND_PRODUCTION_MODES.md`): Consistency Frame is now explicitly an animation-first, style-agnostic AI video production Brain/orchestrator — animation is NOT cartoon-only (2D, anime, stylized 3D, semi-realistic, photorealistic CGI, digital humans, animals, creatures, image-to-video, video-to-video, hybrid live-action/VFX are all first-class), and it is NOT a server, API backend, cloud database, or VoiceStudio/OpenMontage replacement. (1) Multi-dimensional production model: visual style, production medium, source-media type, motion-generation method, subject type, and interaction pattern are separate composable dimensions with fixed vocabularies — never one giant `animation_type` enum; no cartoon default; the user's explicit style choice has priority; a photorealistic CGI human is not live-action footage and a photo animated into a moving photorealistic character is image-to-video/digital-human animation, not filmed performance. Captured footage is expressible: `visual_style: "captured-live-action"` + motion method `"captured-motion"` were added at integration so unmanipulated captured real-animal footage (routing scenario S6) is a valid production profile. (2) Skill fixes (no new skill — D6 decision, counts unchanged 109/120, 15 skills): `realistic-person` no longer says its output is "not animation" — it IS photorealistic digital-human animation, with consent/likeness/voice-permission rules preserved and generated-digital-human vs real-live-action-footage distinguished; `explainer-animation` is labelled ONE optional profile; `live-action-vfx` carries the 5-way distinction (real actor footage / AI digital human / CGI creature / real captured animal / CG animal); `character-consistency` is style-agnostic across human/animal/creature anatomy; performance/voice/cinematic skills operate across human/digital-human/creature workflows (never human lips on a bird). `docs/15-realistic-person.md` carries the same correction. (3) Composable routing: the global video-type mutual exclusion is withdrawn — `architecture/WORKFLOW_GRAPH.yaml` no longer declares `exclusive_groups`, `architecture/SKILL_ROUTING_MATRIX.yaml` narrows matrix conflicts to the two production-level blockers (live-action-vfx ↔ realistic-person, explainer-animation ↔ realistic-person) with ten scoped true-conflict rules TC-1–TC-10 in the graph (same subject/same shot only); per-character/per-shot representation is supported; 8 routing scenarios (2D explainer, stylized 3D story, photorealistic digital human in Bengali, human + talking bird, live-action human + CGI creature, real animal footage, video-to-video, photorealistic explainer) prove compatible skills run together and incompatible operations are still prevented. (4) Schemas v2.5 (additive migration — dual-version enums `["2.3", "2.5"]` / `["2.4", "2.5"]`, no existing required field removed or retyped, every valid v2.3/v2.4 record still validates): two new schemas (`schemas/production-profile.json`, `schemas/character-registration.json`) and seven extended (`character.json`, `voice-profile.json`, `visual-style-profile.json`, `scene-plan.json`, `shot-plan.json`, `performance-plan.json`, `script-to-performance.json`) — production profile contract, subject_kind/species/anatomy/articulation/consent, per-subject shot/scene details, character–voice binding per dialogue line/shot with stable IDs. `scripts/validate-repo.py` accepts 2.5 (validator gate extended by the coordinator) and `schemas/README.md` records 2.5. (5) Addendum C (mandatory): reference video is OPTIONAL (Path A reference-assisted, Path B script-and-image-driven; never invent a reference video); first-run Character Registration invitation (register now / skip + temporary use / register later; skipping never prevents a video; never silently convert an upload into a permanent registration); character registration data model (name + unique ID, type/species/style/refs/voice profiles/consent/history — not human-only); character–image binding + reference management (resolve by ID/unambiguous name, record IDs in the manifest); private per-character voice registration (user-recorded + AI-generated, Voice Profile data, provider limits disclosed); strict voice isolation + privacy (owner/workspace-scoped, no private media in the public repo, local-first serverless Brain, provider transmission disclosed, no unsupported "never leaves the device" promise); character–voice binding in every production; performance direction (face/mouth/body, subject-specific articulation); multi-character interaction + dialogue blocking (speaker/listener/eyelines/180-degree rule); intelligent cinematography (motivated movement only, focus/depth, continuity; static is a valid deliberate choice); one shared audio-visual timeline (stable dialogue/shot IDs for VoiceStudio/OpenMontage handoffs); QC (identity/voice/performance/cinematography/audio-visual — report unsupported behaviour, never claim it succeeded). P0 = contracts/schemas/validation/docs only; provider execution/runtime remains P1 and is NOT started. (6) Tests: `tests/test_routing.py` CF-P0-ROUTING-005/006 (8 scenarios), `tests/test_schemas.py` (+45 v2.5 checks incl. F5 migration), new `tests/test_character_registration.py` (Addendum C acceptance cases 1–12 + QC-01) and `tests/test_production_direction.py` (cases 13–20 + QC-02/03), new fixtures incl. a schema-valid S6 captured-footage profile; `tests/run-tests.sh` gains CF-P0-006-AC-REG / CF-P0-006-AC-DIR. Full suite: 47 recorded test-run entries PASS (35 distinct test IDs, 28 distinct command strings). (7) Part A of this order (separate commit `2235438`): stale P0-005 CI evidence corrected in-repo — final P0-005 heads (code `b24d934`, docs `69247d5`, remote PR head `24d2e62`) with CI push run #47 and PR run #48 (both SUCCESS, 2/2 checks; 45 recorded entries, 33 distinct test IDs, 26 distinct command strings) recorded in `BUILD_REPORT_P0.md` §12, `build-report.json`, the living report, and `CF-WO-P0-005-corrections.md` §8; the work order's cited head `c294c987` / runs #45/#46 were stale and are superseded.
- P0-005 final evidence & failure-diagnostic corrections (2026-11-22, branch `feat/cf-p0-safe-foundations`; corrections record `docs/implementation/CF-WO-P0-005-corrections.md`): (1) generated reports reconciled with the verified post-push CI evidence on final PR head `8879123` — push run #37 (`https://github.com/msujoy149/consistency-frame/actions/runs/45055643056`) and PR run #38 (`https://github.com/msujoy149/consistency-frame/actions/runs/45055649820`), both SUCCESS, 2/2 checks; `p0-test-results` artifact (ID 14766603267) holds 43 recorded test-run entries, 31 distinct test IDs, 24 distinct command strings, all PASS, its `last-run.json` byte-identical to the P0-004 ZIP's; the stale "post-corrections CI run will be checked later" wording is replaced in `BUILD_REPORT_P0.md` §4/§5/§8/§12, the living report, and `CF-WO-P0-004-corrections.md` §7 (now an explicit local-before-push vs remote-after-push distinction), with the `fcf311e` record retained as history. (2) the no-change final-metadata failure diagnostic no longer claims a recovery backup exists where none was created — `scripts/sync-skills.sh` now reports FAILED (exit 1) with "no content backup was created; run record retained"; the same accuracy fix covers the earlier failed=1 path and the new-only PARTIAL case (backups are created only for replaced or pruned files). New regression tests SEC-METADATA-06 (no-change, 13 checks) and SEC-METADATA-07 (failed=1 with no backup, 8 checks) in `tests/test_installer_metadata_failure.sh`; both fail on pre-fix code and pass on fixed code, SEC-METADATA-05 intact. Full suite: 45 recorded test-run entries PASS (33 distinct test IDs, 26 distinct command strings).
- P0-004 post-review corrections (2026-11-22, branch `feat/cf-p0-safe-foundations`; corrections record `docs/implementation/CF-WO-P0-004-corrections.md`): (P0-003-01) the installer called `write_result_json()` without checking its return code, so a failed final metadata write still printed `Skill sync SUCCESS` and exited `0` — independently reproduced (script runs under `set -uo pipefail`, not `set -e`; `IsADirectoryError` on a directory in place of `.consistency-frame-last-sync.json`). Fixed in `scripts/sync-skills.sh`: both result-write calls are now checked explicitly; changes applied + metadata failure reports PARTIAL (exit 2) with a diagnostic and the recovery backup preserved; no changes + metadata failure reports FAILED (exit 1); no backup run directory is removed before final status persistence has succeeded. New true installer integration test SEC-METADATA-05 (`tests/test_installer_metadata_failure.sh`, 13 checks; fails 7 checks on the old code, passes on the new). (P0-003-02) test-evidence reconciliation: the P0-003 docs said "40/40" while `last-run.json` held 41 entries — a hand-count error omitting the new `bash -n` entry, plus a stale `last-run.json` committed with the fix; corrected to 41 recorded entries / 30 distinct test IDs / 22 distinct command strings, and `scripts/generate-build-report.py` §12 now computes the counts from `last-run.json` instead of carrying a hand-typed total. Current suite: 43 recorded test-run entries PASS (31 distinct test IDs, 24 distinct command strings). (P0-003-03) stale provenance in the P0-003 corrections §6 corrected to the final regenerated release (`--github-head 43d4fd33`, code head `5e25545`, final PR head `59f562a`).
- P0-003 final independent security correction (2026-11-22, branch `feat/cf-p0-safe-foundations`; corrections record `docs/implementation/CF-WO-P0-003-corrections.md`): the installer wrote the ownership manifest to a predictable `<target>.tmp` with an ordinary `open()`, so a planted symlink there was followed and the outside target overwritten — independently reproduced against the P0-002 package. Fixed with one reusable helper, `scripts/atomic_write.py` (`tempfile.mkstemp()` exclusive unique temp in the target's directory, write through the returned fd, fsync, `os.replace()`; failures clean up and propagate), now used by all four installer metadata writers (`write_manifest()`, `update_manifest_hashes()`, `write_result_json()`, `write_run_owner()`); file modes preserved (existing target's mode, else `0o666 & ~umask`). Regression tests SEC-MANIFEST-01..04 (`tests/test_installer_manifest_security.sh`) + helper unit tests CF-P0-ATOMIC-001..006 (`tests/test_atomic_write.py`); negative control reproduced the vulnerability with the old pattern and confirmed the fix with the new helper. Full suite: 41 recorded test-run entries PASS (35 previous + 1 new `bash -n` + 4 SEC-MANIFEST + 1 ATOMIC); 30 distinct test IDs, 22 distinct command strings; `setup.sh --dry-run` exit 0. (Correction, CF-WO-P0-004: an earlier draft of this entry said "40/40" — a hand-count error; the true count is 41 recorded entries.)
- P0-002 independent-review corrections (2026-11-22, branch `feat/cf-p0-safe-foundations`, findings §§1–7; corrections record `docs/implementation/CF-WO-P0-002-corrections.md`): installer hardening (§§1–3 — `scripts/sync-skills.sh` path safety, ownership and atomic backups; managed-file conflict policy in `docs/06-installation.md`; security regression suite); human performance schemas (§4 — emotion intensity 0–10, positive durations, nuanced emotion taxonomy, non-verbal events, dialogue-rewrite semantics; gates CF-P0-PERF-001..005); learning authorization split (§5 — propose vs apply a skill patch, `may_propose_skill_patch` vs `may_apply_skill_patch`); companion capability accuracy (§6 — `evidence_level` replaces `status` in `architecture/COMPANION_CAPABILITY_REGISTRY.yaml`: 20 capabilities, 3 `exercised_recorded_run`, 16 `present_locally`, 1 `upstream_inspected_pinned_commit`, 0 `production_verified`; core-only install explicitly excludes VoiceStudio/OpenMontage; gate CF-P0-ROUTING-004); reports and release provenance (§7 — `--github-head` / `CF_GITHUB_HEAD` on both report generators, `github_branch_head` in `build-report.json` + `release-manifest.json`, `release-manifest.json` excluded from its own file list, detached `docs/implementation/CHECKSUMS.txt`, Provenance §12 in `BUILD_REPORT_P0.md`; remote CI PASSED on `fcf311e`, 2/2 checks — all obsolete "CI NOT RUN" statements removed; gates CF-P0-REPORT-001..004).
- P0 v2.4 Brain Architecture Amendment (2026-11-22, user voice call; branch `feat/cf-p0-safe-foundations`): Consistency Frame is the CENTRAL BRAIN / Orchestrator — Central Server Manager + own-API implementation are WITHDRAWN and were never built (audit: zero server/API-backend/cloud-database claims in normative text). P0-A audit (`docs/implementation/BRAIN_ARCHITECTURE_AUDIT.md`, incl. ONE-OFF vs RECURRING mode mapping); P0-B Intelligent Skill Routing (`architecture/SKILL_ROUTING_MATRIX.yaml` — 15 skills, precedence 1–15, command-authority is the router; `architecture/WORKFLOW_GRAPH.yaml` — 42 edges, acyclic, sequential on dependency, parallel only when safe) and Script-to-Performance Intelligence (four `schema_version: "2.4"` schemas: `scene-plan.json`, `shot-plan.json`, `performance-plan.json`, `script-to-performance.json` — the combined contract; dialogue VERBATIM unless a rewrite was explicitly requested); P0-C Companion Capability Registry (`architecture/COMPANION_CAPABILITY_REGISTRY.yaml` — VoiceStudio v0.5.8 + OpenMontage, verified capabilities only) and Agent Compatibility Matrix (`architecture/AGENT_COMPATIBILITY_MATRIX.yaml` — 10 agents, only Muse verified; OpenRouter is a model-routing layer, not a host; Colab needs a Notebook/Agent Runtime); tests (`tests/test_routing.py`, gates CF-P0-ROUTING-001/002/003) + validator check 8 for the canonical YAML records; CI installs PyYAML; updated plan (`docs/implementation/P0_UPDATED_IMPLEMENTATION_PLAN.md`) and living report (`docs/architecture/living-architecture-report-v2.4-p0.md`). No skill file changed; no server/API/database code exists or was added. Runtime routing engine and script-to-performance runtime are P1 work.
- P0 Safe Foundations (work order CF-WO-P0-001, branch `feat/cf-p0-safe-foundations`, architecture v2.3): non-destructive skill sync (`scripts/sync-skills.sh` — manifest-owned files only, unmanaged skills preserved, dry-run, opt-in prune, backup + rollback); `setup.sh` is core-only by default with opt-in `--with-components` and truthful per-component SUCCESS/PARTIAL/FAILED status; canonical registries (`registry/skills.json`, `features.json`, `workflows.json`, `adapters.json`, generated by `scripts/generate-registries.py` — 15 skills, 165 features, 13 workflows, 12 adapters, none marked supported); 20 versioned JSON Schemas (`schemas/`); asset-mode policy (`scripts/asset_policy.py`); audio delivery profiles (`architecture/audio-delivery-profiles.json`, `docs/19-audio-delivery-profiles.md`); tests (`tests/`, 17 checks, all passing locally) and GitHub Actions CI (`.github/workflows/p0-ci.yml`, actions pinned to verified SHAs); living architecture report (`docs/architecture/living-architecture-report-v2.3-p0.md`, generated from canonical records); P0 plan (`docs/implementation/CF-WO-P0-001-plan.md`) and build report (`docs/implementation/BUILD_REPORT_P0.md`).
- 3D stylized fantasy reference videos watched in full (2026-11-15): two user-uploaded videos — a 13.46 s dialogue scene excerpt (received twice, as two different encodes of the same clip) and a 32.02 s vertical video clip from the same world, using title cards and an end card. Two genuine gaps found and closed by extending existing skills (no new skill, counts unchanged 109/120): the `cinematic-power` skill §4 now covers title cards and end cards (character-intro, tagline, pedigree, and release-date cards, each carrying one idea, timed to the beat, title last), and §2 now covers character transformation as a story beat (face and voice stay fixed, new form registered, change shown never jump-cut); the `kids-family-animation` skill §3 now notes the flash-frame transition, and §17 gains two verified techniques (§17.11 title cards and end cards, §17.12 transformation). Library records R-18 and R-19 added in the 25-field format. Everything else in the videos was already covered (3D stylized CG style lock, expression range, lip-sync, costume consistency, colour scripting, camera decision system, the six-beat arc the clip uses, living-object and flock-as-mass devices). Correction (2026-11-16, user instruction): these uploads are training video clips, not trailers — the title-card and end-card rules are general video devices, and the records describe the videos as clips.
- Deep audit + "repo as brain" system (2026-11-13): the command-authority skill now carries the full brain model — skill commands first whenever they exist; a missing skill is generated from the repo's own generation command (generate / preserve / quality bar / verify / save); light details (emotion, tone, natural phrasing) are delegated with direction from the repo; a new task type starts from the distilled common core (human-like, no overlap, lip-sync, fixed identity, script decides, realism and continuity, QC, rights and consent) instead of hunting for a skill; and when the repo has no instruction at all it says "do it yourself" — never bare, always with the quality commands (correct, cinematic, human-generated, per the need and the script). Docs/17, AGENTS.md, and the README carry the same model. Main-flow refinement (2026-11-13): the "do it yourself" permission now also hands over the repo's main flow — read the script, lock what is fixed, plan shots from the beats, decide the voice/video order, generate shot by shot, keep continuity, add sound, run QC, deliver, save if it grows into a system — derived from the existing skills (command-authority §2, production-systems A1–A12/B5/B14/C2/C3/C7/D2/D3, character-consistency §14, voice-consistency §8, kids-family-animation §15), so the AI follows the repo's order and improvises only the details inside each step. Skill-first loop (2026-11-13): when a skill is missing, the new skill is written and saved FIRST and the video is then made by following it, so no video is ever improvised and every gap is closed permanently the first time it appears; this round adds the rule only — no new skill file, counts unchanged 109/120. Audit fixes in the same round: quoted YAML frontmatter descriptions in 4 skills (strict parsers rejected them), replaced unresolvable citations (to section numbers that do not exist in the repo) with repo references (production-systems C7/A12/B17), fixed wrong section/area numbers in the kids skill (§4.5 → §4.6, §17.5 area 3 → area 2), resolved the inpainting contradiction (a merged face is never inpainted — regenerate fresh, per character-consistency §14), all four plugin manifests now list all 15 skills (they listed 9), the README skills table and docs/06 now list all 15, the counting convention is now documented in docs/01, docs/16's counting note no longer double-counts itself, the resource-management skill no longer claims production scripts exist, and setup.sh now refuses to run component setup inside a non-checkout directory and checks for ~9 GB free disk. Final re-audit (2026-11-13): the AGENTS.md docs index now lists docs/01–05 as well (it previously listed only docs/06–18). Counts unchanged: 109 distinct systems, 120 numbered entries.
- Local install on Mac, Windows, and Linux via the terminal: a "Local
  install" section in the README and a full per-OS guide in
  docs/06-installation.md — exact commands per OS (Mac: Homebrew +
  `brew install git bun uv node ffmpeg`; Linux: apt + NodeSource +
  official bun/uv installers; Windows: Git Bash path with winget +
  PowerShell installers, and a WSL path), prerequisites, what
  `setup.sh` does, the OmniVoice model download step, verification,
  and troubleshooting. The Linux path was verified end-to-end on a
  Linux machine; Mac/Windows commands were checked against official
  installer docs only — no Mac or Windows machine was available to run
  them on.
- `setup.sh` now pins the bundled components to tested commits
  (VoiceStudio `2f2f5a9`, OpenMontage `fecb9a1`, using their full
  40-character SHAs — a short SHA fails the fetch with "couldn't find
  remote ref") and runs OpenMontage's `make setup` instead of only
  printing the command; a missing `make` or a failed step is reported
  honestly, not claimed as success.
- Generic character-consistency system, documented as a reusable
  template in docs/07-character-registry.md, skills/
  character-consistency/SKILL.md, characters/README.md, and the
  README: registration (name + unique ID + reference image(s) +
  explicit authorization, all required; an image alone does not
  register), structure fixed / clothing and props variable per scene,
  turnaround + detail reference sheet (front/side/back views, face/
  hands/feet close-ups, stored as `model-sheet.jpg`) as the identity
  anchor for every scene, and identity anchoring (the same approved
  reference reused in every generation; structure 100% identical
  across scenes and episodes).
- Character Generator — two ways to create a character: a
  user-supplied picture used exactly as given, or an AI-generated
  character shown to the user first and registered only on explicit
  "done" approval, after which its structure is locked from the
  approved version. No generated character becomes permanent without
  that approval.
- Privacy scrub: all example character names in the repo replaced
  with generic placeholders (`<character-name>`, `char-001`); no
  character pictures or real character data in the repo.
- Outfit consistency — script-driven: the outfit the user selects
  stays exactly as-is until the user says to change it; a scene-driven
  change (for example, swimming) is allowed, and the new outfit then
  holds in that context. Outfits change only on the user's word or a
  clear scene need — never randomly. Documented in the
  character-consistency skill, docs/07, the wardrobe registry
  (docs/02, production-systems skill), and the README.
- Face-consistency correction method: one user-approved image as the
  definitive reference reused in every generation, front-facing for
  face-critical shots, an explicit no-change instruction in every
  prompt, fresh regeneration (never editing) when the face drifts, and
  verification against the reference before delivery.
- Reference matching is mandatory for every generation, angles and
  expressions follow the script explicitly, and verification is
  angle-matched: a shot is compared against the sheet's matching
  head-turn view (front, 3/4 left, left profile, back, right profile,
  3/4 right) and its matching expression panel (twelve expressions),
  instead of comparing every angle against the front view only. The
  turnaround sheet now carries those six head-turn views and twelve
  expression panels.
- Expression auto-generation and library: missing expressions are
  generated from the definitive reference (face and structure 100%
  identical), saved per character under
  `characters/<character-id>/expressions/<expression-name>`, and reused
  from then on — never regenerated twice. The library grows on demand
  as scripts need new expressions, and persists across sessions as
  part of the character record.
- Agency advertising layer — seven new systems for using a registered
  AI-generated model as an agency spokesperson across ads (skill:
  skills/agency-advertising/SKILL.md; doc:
  docs/08-agency-advertising.md): brand kit (model + logo + colours +
  tagline + fonts + voice tone, locked per brand), ad formats (9:16,
  1:1, 16:9, hook in the first 3 seconds, clear CTA, platform safe
  zones), campaign variants (6s / 15s / 30s cut-downs from one master,
  A/B variants changing one thing at a time, tracked per variant ID),
  client isolation (per-client workspaces; model, brand kit, and voice
  checked against the client's workspace before every generation), AI
  disclosure and likeness safety (platform disclosure on every ad,
  likeness check at registration and after drift, never remove
  watermarks or provenance), product/service consistency (product
  shots, wording, prices, and claims locked per campaign), and client
  approval workflow (draft → review → approved → publish; every
  revision a new version; approval recorded per version). The model
  itself is a registered character created through the Character
  Generator; this layer adds only the advertising rules on top. Counts
  updated everywhere: 82 distinct systems, 93 numbered entries.
- Script-driven automatic camera angles: the angle for every shot is
  decided automatically from the script beat — story function, emotion,
  character relationship, and what the viewer must notice — never by
  habit or rotation; full shot grammar (wide, medium, close-up, extreme
  close-up, over-the-shoulder, POV, low / high / bird's-eye / worm's-eye,
  Dutch tilt, two-shot, group wide), a beat-to-angle mapping (emotion
  always wins over the table), motivated movement only, lens language
  (35mm for place and togetherness, 50mm for honest human presence,
  85mm for intimacy), the 180-degree rule and eyeline/action continuity
  across cuts, human-camera imperfection (faint handheld sway, a breath
  of focus hunting, framing corrected mid-shot — subtle, never
  distracting), one angle logic per beat planned in the shot list before
  generation, and user override wins. It also covers no-script
mode: when the system generates the story itself, it first writes
the story as beats and then directs the angles from those beats, so
the angle decision is mandatory in both modes and the shot list with
angles is part of the generated script. Realism target: aim for 100%
  realistic, human-generated feeling; 99.9% is the floor. Documented as
  A12 in the production-systems skill, cross-referenced from docs/01 §2.
  Counts updated everywhere: 83 distinct systems, 94 numbered entries.

- Video regeneration — a new skill (`skills/video-regeneration/SKILL.md`)
  and doc (`docs/09-video-regeneration.md`): the user uploads a reference
  video and the system first analyses it in full (story, scenes in order,
  characters, objects, camera, light, sound), then creates a NEW original
  video preserving the reference's core story, emotional impact, narrative
  structure, and creative direction, with only minor or explicitly
  requested changes. Covers character and object continuity, physically
  correct handovers and interactions (no merging, passing through, or
  disappearing objects), cinematic realism, a storyboard before generation,
  original audio, a mandatory QC pass before delivery, and output
  requirements (aspect ratio, pacing, duration, clips when the model
  limit is shorter). The reference is the user's own uploaded video; the
  output is an alternative version, never a frame-for-frame copy.
  Counts updated everywhere: 84 distinct systems, 95 numbered entries.
- Cinematic power — five new systems for feature-trailer and music-video quality (skill: skills/cinematic-power/SKILL.md; doc: docs/10-cinematic-power.md): stylized animation style lock (2D anime, 3D stylized CG, or photorealistic, chosen first and held in every shot), animal and creature performance (animals registered like characters, movement follows the creature's real body, comic timing for sidekicks, menace in stillness for monsters, elemental forces as characters), music-beat editing and synchronized ensemble (cuts and movements land on the musical beat, one timing reference for the whole ensemble), trailer and teaser structure (wonder → stakes → characters → comedy beat → climax montage → title card → credits), and scale, spectacle, and colour scripting (scale contrast for wonder, palettes assigned per emotional beat with planned transitions). Counts updated everywhere: 89 distinct systems, 100 numbered entries.
- Live-action and VFX — six new systems for live-action and VFX hybrid quality (skill: skills/live-action-vfx/SKILL.md; doc: docs/11-live-action-vfx.md): live-action human performance (a real body performs — micro-expressions, breath, fatigue, weight; effort shows; the face in the close-up matches the body in the wide shot), VFX integration of CG creatures in live footage (the creature shares the live plate's light, casts shadows and reflections, gets wet when the scene is wet; the actor's eyeline hits the creature's eyes; scale is fixed; contact is real), water, wetness and underwater continuity (the wet state is tracked across cuts and changes only when the story changes it; underwater shots hold a fixed look with water-driven movement), practical locations and set extension (the real place is extended with CG and the seam never shows — one light, one haze, one water line), live-action stunt and action choreography (action planned beat by beat and shot to look unplanned; the camera hides the safety, never the impact; the character stays readable), and real-animal performance (the animal does what it does — many takes, cut around its real behaviour, comic timing made in the edit; CG touch-up only where the animal cannot perform). Counts updated everywhere: 95 distinct systems, 106 numbered entries.
- Emotional performance — seven new systems for musical and intimate scenes (skill: skills/emotional-performance/SKILL.md; doc: docs/12-emotional-performance.md): musical performance and stagecraft (the song has an arc — nervous start, finding the groove, the crowd won over, triumph — and the lighting brightens, the performer's body loosens, and the crowd's energy rises along with it; the stage is a warm island in a cool night), crowd as a living character (hundreds of distinct people, never a copy-paste, reacting in waves; the crowd's mood is the scene's barometer, and reaction shots prove the performer's triumph), intimate drama and emotional arc (a long scene between two people held for minutes on their faces — no response, a flicker, recognition, tears, joy — built from micro-expressions, pauses, and silence, planned beat by beat; the camera stays close and still; touch is the emotional climax), age performance (age changes everything — movement slow, trembling, frail; voice slow, thin, frail; face with deep wrinkles, drooping lids, cloudy eyes; memory loss, then a flicker of recognition; the very old act mostly with their eyes and hands; the voice must match the age and stay the same for that character across episodes), instrument performance sync (the hands must play the music you hear — fingers on the frets match the notes, strumming matches the rhythm; hand close-ups are checked against the audio; the instrument is a hero prop, the same look every time), music as story and memory (the song IS the plot — it unlocks a memory, changes a mind, heals a family; it starts small and the room joins it emotionally, each face changing at a different moment), and cultural authenticity and object storytelling (one culture held in every shot — festival, flowers, banners, dress, family house, food — never generic; props carry history and plot, and an object's damage and reveal are planned beats whose state matches the story at every cut). Counts updated everywhere: 102 distinct systems, 113 numbered entries.
- User-supplied voice cloning — a user may supply a real person's voice, their own or someone else's, as a character's voice (skill: skills/voice-consistency/SKILL.md §13): record a clean sample, clone it with VoiceStudio Voice Cloning / OmniVoice zero-shot, verify it sounds like that person, and lock it as the character's voice forever; one recording per person per character; the voice parallel of the character generator's user-supplied picture rule. Counts updated everywhere: 103 distinct systems, 114 numbered entries.
- On-demand resources — load only what the work needs (skill: skills/resource-management/SKILL.md; doc: docs/13-resource-management.md): when a job runs, only the resources that job needs are loaded — the voice plugin runs only for voice work, the video plugin only for video assembly, and the assistant's working memory holds only the current phase; both plugins together only when a step genuinely needs both, otherwise the steps are sequenced; model weights load to generate and unload after; one character's voice at a time; nothing left running "just in case". The quality guard is non-negotiable: resource discipline never degrades quality — if a job needs both plugins, run both, and if the machine cannot hold both, sequence the work, never cut quality or skip checks. Counts updated everywhere: 104 distinct systems, 115 numbered entries.
- Language authenticity — every language spoken the way its native speakers speak it, multi-language delivery, and lip-sync matched to the language's sounds (skill: skills/language-authenticity/SKILL.md; doc: docs/14-language-authenticity.md): US English carries the American tone and everyday phrasing, Bengali the Bengali tone and idiom, Hindi the Hindi tone and idiom — never stiff textbook speech; the register follows the script, including colloquial and slang words the way natives actually use them, without inventing words the script does not call for; each character keeps their own language and the same voice profile across languages; the same video in N languages means N complete versions (dialogue, voice, lip-sync, on-screen text), delivered separately when asked separately; lip-sync follows the sounds of the language being spoken and every line's mouth movement is verified against its own audio track — a talking character with a still mouth is a defect, never a delivery; each language version passes a native-plausibility listening test and a per-line lip-sync check before delivery. Counts updated everywhere: 105 distinct systems, 116 numbered entries.
- Realistic person video — a real person's photo becomes a realistic moving, speaking person video (skill: skills/realistic-person/SKILL.md; doc: docs/15-realistic-person.md): the supplied photo is used exactly as given, the face, structure, hands, and feet never change, only movement and speech are added; natural movement and natural speech in the person's own language, lip-sync matched to the language's sounds — a talking person with a still mouth is a defect, never a delivery; real skin, hair, and cloth behaviour, natural light, no plastic skin, no cartoon look, realism target 100% with 99.9% as the floor; not 2D/3D animation and not live-action footage of a real shoot. Also clarified in skills/cinematic-power/SKILL.md: the trailer/teaser structure is the cinematic system used inside web-series/episode production, not a standalone video type; music video stays separate. Counts updated everywhere: 106 distinct systems, 117 numbered entries.
- 2D explainer animation — a short video that teaches one idea through simple scenes and visual metaphors (skill: skills/explainer-animation/SKILL.md; doc: docs/16-explainer-animation.md): flat 2D cartoon / stick-figure explainer, vertical short-form — not anime, not 3D CG, not live-action, not a music video, not a trailer; flat 2D vector, thick black outlines, flat colour fills, warm neutral backgrounds, a small palette; two character designs kept apart (a fuller cartoon figure for the real person, simple stick figures for abstract ideas); every abstract idea becomes a character or a place (internal conflict = two figures arguing inside the brain, an obstacle = a mountain with a face, the brain itself = a friendly thinking companion); one idea per scene, ~10 s per scene, 4–6 scenes for a short video; slow push-ins and pans, few hard cuts; expression carries the meaning; almost no on-screen text, labels only where one word says the whole idea. Counts updated everywhere: 107 distinct systems, 118 numbered entries.
- Command authority — the repo is the command master (skill: skills/command-authority/SKILL.md; doc: docs/17-command-authority.md): after install, every video is made by reading and using the repo's skills first — a skill that exists in the repo is used, never reinvented; if a needed skill is not in the repo, check the repo's comments and notes about that topic first and follow them; only if the repo gives no comment, generate the system in the repo's skill format, save it as a new skill, and tell the user plainly what was added and why. Applies to every skill, including future ones, and to every platform the repo is installed on. Counts updated everywhere: 108 distinct systems, 119 numbered entries.
- Kids & family animation — professional short-form animated videos for children and young audiences (skill: skills/kids-family-animation/SKILL.md; doc: docs/18-kids-family-animation.md; camera reference: docs/research/kids-animation-camera-language.md; analysis method: docs/research/kids-animation-reference-analysis.md; permanent library: docs/research/kids-animation-reference-library.md): fourteen animation methods with one locked visual style per project; 2D craft (line weight, shape language, smear frames, parallax, anime framing) and a 3D CGI pipeline (modelling, rigging, animation principles, lighting and rendering, environment) with an honest AI reproduction strategy that never pretends an AI model performs real 3D rigging; a full camera decision system (angles, shot sizes, movement, lens and perspective, composition, and an 8-question system for every scene); character performance rules; ten reusable story templates for original scripts; natural voice and dialogue; a shot-level sound plan; short-form structure with a first-second hook, escalation, payoff, and replay potential; continuity; a six-group animation QC checklist; a reference-analysis methodology (25-field record plus timestamped shot breakdown, never fabricate observations); a permanent reference library in ten knowledge areas, updated continuously from new links, where a trend becomes a permanent rule only after verification; and a script-only workflow (the user gives a script, the system does the fifteen steps). Integrated research (2026-11-13): the library now holds real records (R-01 to R-17) from videos watched in full — the 4-video watch, the Cocomelon nursery rhyme, and the videos actually watched in the 7-channel research — plus trend intelligence from TrendReport, Veedio, and YouTube search results, each dated. The skill gains §17 with the verified techniques (AI stills + slow movement, recurring hero + rescue-of-the-day, multi-part saga + Part 2 hooks, static-camera Shorts grammar, game-engine animation detail, nursery-rhyme structure, absurd-premise Shorts, multi-language dubbing, and the rights rule that credit alone is not a licence). Held out by the quality rule (only what we are sure about): CartoonWala and 6 popular-channel videos could not be played in the browser, so no technique is recorded for them — their records will be added only after the user supplies the video files and they are watched in full; Guardian Animals AI is unverified and has no record. Counts unchanged: 109 distinct systems, 120 numbered entries. Also fixed in the earlier framework round: docs/16-explainer-animation.md's counting note omitted the command authority system from its list while claiming 108 — the list now names all systems.

### Fixed

- Install command is now `bash setup.sh` everywhere (README, docs/06-installation.md): a fresh clone from GitHub does not carry `setup.sh`'s executable bit, so `./setup.sh` fails with "Permission denied". Verified by a fresh-clone install test (2026-11-13): `bash setup.sh` exits 0 and installs both bundled components at their pinned commits.
- Audit fixes (deep review of the first release). The "86 systems"
  count is now explained everywhere it appears: 75 distinct systems,
  86 numbered entries, because the 11 professional systems are listed
  both in the production-systems skill and in docs/01.
- The Claude Code marketplace now points at the repository root (the
  plugin directory). Codex gains the missing
  `.agents/plugins/marketplace.json` (with the correct source shape —
  the plugin was not discoverable without it), a current-format
  `plugin.json` at the repository root, and `./`-prefixed paths in its
  plugin manifests.
- `setup.sh` now installs the VoiceStudio Python API (`bun run
  setup:api`), not only the JavaScript dependencies; it reports a
  failed install instead of claiming success, and it warns (instead of
  claiming "already present") when a component directory exists but is
  not a git checkout.
- Model-download wording corrected everywhere: `setup.sh` walks you
  through downloading the OmniVoice weights; it does not download them
  itself.
- "Submodule" wording corrected to bundled components cloned by
  `setup.sh` (the published tree carries no submodule links).
- Character-registry file names in docs/07 now match
  characters/README.md. The language section now lists the actual third
  rule (per-character language) and links docs/03; the Made-for-Kids
  rule is noted under the distribution package where it belongs.
- `.gitignore` now covers the install outputs `.agents/skills/` and
  `components/` (the Codex marketplace manifest
  `.agents/plugins/marketplace.json` stays tracked).

## [2.0] — 2026-11-12 — First release

The first public release. The complete system: **86 numbered entries (75 distinct systems)** for
consistent characters, consistent voices, and human-feeling video, in
any AI platform. The 11 professional systems are listed twice — once in the production-systems skill and once in docs/01 — so 11 + 18 + 3 + 7 + 36 = 75 distinct systems, 86 listed entries.

### Included

- **Character consistency** — character registry (per-character folder:
  `character.yaml`, 3–4 reference images, voice reference audio),
  registration rules (name + unique ID + reference image(s) + explicit
  authorization; name-on-image not mandatory, required only when several
  characters' images arrive in one batch), identity resolution (a name
  in a script resolves to that character's ID + reference image + voice
  + prompt block), prompt builder (fixed prompt block + fixed seed per
  character), 100% reference fidelity (face and height most important;
  one photo enough, several more reliable), character recall (show the
  character exactly as stored, on request), fixed identity structure
  with scene-variable clothing and props, multi-character scenes with no
  overlap, private character data separation with a private overlay.
- **Voice consistency** — fixed voice profiles (tags + seed + reference
  audio) per character, reused every episode; VoiceStudio/OmniVoice
  integration; single-pass multi-speaker dialogue; voice-drift
  measurement; voice ageing and state variants; code-switching and
  dialect rule with a separate listening test per language;
  distance-and-space in voice; dialogue-first mixing.
- **Professional production systems (11)** — visual style bible;
  camera language and shot list; negative prompt library; sound design
  system; music and theme; story bible; episode continuity tracker;
  dialogue writing rules; reference photo quality rules; lip-sync and
  dubbing workflow; episode QC checklist.
- **Extended production systems (18)** — subtitles/captions pipeline;
  thumbnail/poster generator; character turnaround/model sheets;
  wardrobe/prop/location registry; clip-boundary seam continuity;
  quantitative drift measurement; per-character LoRA training;
  character aging/time-jump variants; shot-level provenance log; cost &
  credit tracking; backup/versioning of character data;
  multi-project/multi-series namespaces; child-safety rules; audio
  mastering standard (−14 LUFS); localisation/dubbing pack;
  distribution package; rights/consent/provenance records; audience
  feedback loop.
- **Language, captions, and format rules (3)** — captions OPT-IN (ask
  first, default no baked-in captions, any language on request);
  per-character language in one video; format/aspect ratio on demand
  (16:9, 9:16, 1:1, 4:5, any ratio; short or long; any platform;
  compose for the ratio from the start, never crop afterwards).
- **Additional systems (7)** — private character data separation;
  multi-character scenes and no overlap; episode intake checklist;
  demo project (on-demand system, no demo content shipped); script
  template and automatic script enhancement; contribution guide;
  script-driven realism and colour grading by time of day and light
  source.
- **Humanization systems (36)** — performance-driven acting;
  single-pass multi-speaker dialogue; involuntary micro-motion;
  listener-reaction rule; room tone / never-silence + 4-layer sound;
  non-verbal voice layer; eye/gaze continuity; hands & physics
  avoidance + repair; anti-plastic skin; editing rhythm; film-finish
  pipeline; voice-drift measurement; temporal-artifact QC; camera
  imperfection; lighting-continuity lock; background life; cloth/hair
  physics; distance & space in voice; sound spotting sheet; AI
  disclosure & provenance pack; detector self-QC; audio description
  track; voice ageing/state variants; code-switching & dialect rule;
  model-version pinning + golden regression; re-anchor every ~8–16 s;
  reference-count strategy per model; human blind-test gate;
  mouth-interior QC in lip-sync; wardrobe wear & continuity detail;
  imperfection budget; music-ducking / dialogue-first mix; failure &
  fallback playbook; real-person safeguards; realism budget; cinematic
  backgrounds.
- **Portable install** — Agent Skills standard (`skills/` as the source
  of truth) with thin per-platform manifests for Claude Code, Codex,
  Gemini CLI, and Antigravity, plus a Muse path (clone + `./setup.sh`).
  VoiceStudio and OpenMontage bundled as components, fetched by
  setup.sh (the published tree carries no submodule links); OmniVoice
  weights downloaded by the user at install time from Hugging Face with
  the CC-BY-NC notice.
- **Docs** — full system documentation in `docs/`, including the two
  background research reports in `docs/research/`.
- **Licence** — this project's own work under Apache-2.0; VoiceStudio
  and OpenMontage under AGPL-3.0 (bundled components, licences intact);
  OmniVoice model under CC-BY-NC (noncommercial).
