# CF-WO-P0-006 — Animation-First, Style-Agnostic Production Architecture: Corrections

**Work order:** CF-WO-P0-006 + Mandatory Addendum C ·
**Branch:** `feat/cf-p0-safe-foundations` ·
**Status:** Integrated by the coordinator (2026-11-22); all parts
landed, validated, and committed locally — see §12–§15.
Other P0-006 parts (architecture/routing, schemas, skills, tests)
own their files; this record describes the whole change so the
coordinator can verify the integrated result against it. Where this
draft names a file owned by another part, the final integrated state
of that file is to be confirmed by the coordinator at integration
time — this draft does not claim to have seen those parts' final
work.

**Related records:** `docs/architecture/ANIMATION_SCOPE_AND_PRODUCTION_MODES.md`
(the canonical reference created by this work order);
`docs/implementation/P0_UPDATED_IMPLEMENTATION_PLAN.md` §9;
`docs/implementation/CF-WO-P0-005-corrections.md` (previous order).
Part A (P0-005 evidence correction) is already committed separately
(local head `2235438`) and is not re-litigated here except where a
stale P0-005 reference had to be corrected in a P0-006 file.

## Objective

Make Consistency Frame animation-first and style-agnostic in
definition, routing, schemas, and product identity — without
inventing a new video type, without adding a new skill, without a
server/API/database, and without weakening any existing safety,
privacy, or authorisation rule. Before this order, the repo's
animation scope was contradictory: some documents described a broad
animation system while others described the product as cartoon-only
or said a realistic-person video was "not animation", and routing
treated video-type skills as mutually exclusive alternatives. This
order replaces those contradictions with one canonical model:
independent dimensions with fixed vocabularies, composable routing,
and contracts that carry the dimensions from intake to delivery.

## 1. What already existed

Before P0-006, the repo already contained a broad animation system
— the contradiction was in how it was described and routed, not in
a missing technique:

- **15 skills, 109 distinct systems / 120 numbered entries.**
  Character and voice consistency; humanized production (36
  systems); professional production (12 + 18 + 7); agency
  advertising; video regeneration; cinematic power (style lock,
  animal and creature performance, music-beat editing, scale and
  colour scripting); live-action & VFX (live-action performance,
  CG creatures in live footage, water/wetness, set extension,
  stunts, real-animal performance); emotional performance (stage,
  crowd, intimate drama, age, instrument sync, music as story,
  cultural authenticity); resource management; language
  authenticity; realistic person video; 2D explainer animation;
  command authority (skill-first loop, distilled common core);
  kids & family animation (14 methods, camera decision system,
  reference library R-01–R-19).
- **v2.4 Brain architecture (P0, CF-WO-P0-001 revised).**
  Consistency Frame as CENTRAL BRAIN / Orchestrator; no server,
  API backend, or cloud database; three-repo model (Brain,
  VoiceStudio, OpenMontage); intelligent skill routing as canonical
  data (`architecture/SKILL_ROUTING_MATRIX.yaml`, 15 skills,
  precedence 1–15, command-authority as router;
  `architecture/WORKFLOW_GRAPH.yaml`, 15 nodes, 42 edges, acyclic);
  script-to-performance schemas (`schemas/scene-plan.json`,
  `schemas/shot-plan.json`, `schemas/performance-plan.json`,
  `schemas/script-to-performance.json`, `schema_version: "2.4"`,
  dialogue VERBATIM unless a rewrite was explicitly requested);
  companion capability registry and agent compatibility matrix
  (only Muse verified); propose/apply split for canonical skill
  learning (§8 of the implementation plan); ONE-OFF vs RECURRING
  mode mapping (`scripts/asset_policy.py`).
- **Character and voice foundations.** Character registry (name +
  unique ID + reference images + explicit authorisation; a name on
  the image not mandatory; duplicate name with a different ID stops
  and asks); fixed structure / variable clothing; turnaround and
  detail reference sheet; expression library; fixed voice profiles
  (tags + seed + reference audio); single-pass multi-speaker
  dialogue; per-character language; voice drift measurement.
- **Private asset handling.** Character data private by default,
  never committed to the public repo, living in a separate private
  overlay (`characters/README.md`, `docs/07-character-registry.md`);
  client isolation in agency work; licences intact (own work
  Apache-2.0; VoiceStudio + OpenMontage AGPL-3.0; OmniVoice
  CC-BY-NC).
- **Honesty rules already in force.** Quality targets measurable
  and scoped, verified shot by shot with a human-review gate, never
  an absolute percentage; loudness a delivery profile, never one
  universal target; capabilities recorded with honest evidence
  levels, never marked production-verified without evidence.

## 2. What was contradictory

| # | Contradiction | Where it lived | Resolution (this order) |
| --- | --- | --- | --- |
| C-01 | "Realism, not animation" — a realistic-person video was defined as NOT 2D/3D animation, while the repo also claimed to direct realistic moving/speaking person video as a core production. | README § "Realistic person video" ("This is not 2D/3D animation and not live-action footage of a real shoot"); `skills/realistic-person/` wording ("not animation") | Withdrawn. A photorealistic digital-human video IS animation: a generated digital human, not footage of a real shoot. The kept distinction is digital-human vs live-action footage, and the kept rule is shot-by-shot verification against the approved reference with a human-review gate and no absolute percentage guaranteed. README reworded; skill fix owned by the skills part. Canonical doc §2, §7.1. |
| C-02 | The 2D explainer was presented in a way that read as the product's animation model (flat 2D cartoon described without noting it is one optional profile), while the repo also claimed 14 animation methods and stylized/photorealistic 3D. | README § "2D explainer animation"; AGENTS.md explainer line; `docs/16-explainer-animation.md` framing (unchanged — the skill text itself is profile rules, not a product claim) | The explainer is named as ONE optional profile (`VISUAL_STYLE: flat-2d-vector`, `PRODUCTION_MEDIUM: 2d-drawn-vector`) in README, AGENTS.md, and canonical doc §3.1. Profile rules stay profile-specific; registry, voice, performance, cinematography, and QC apply across profiles. |
| C-03 | Video-type skills were mutually exclusive: at most one per video (workflow-graph exclusive groups; implementation-plan §6 "precedence 11–14 … never run together"). This made lawful combinations indescribable — e.g. a stylized 3D short with a musical performance, a crowd, and a CG creature, or a live-action plate with a generated creature and a title card. | `architecture/WORKFLOW_GRAPH.yaml` (`exclusive_groups`); `architecture/SKILL_ROUTING_MATRIX.yaml` (precedence as exclusion); `docs/implementation/P0_UPDATED_IMPLEMENTATION_PLAN.md` §6 | Withdrawn and replaced by composable routing: primary pathway + style profiles + subject capabilities + compatible layers, true conflicts only (§10 of the canonical doc). Precedence is tie-breaking, not exclusion. Routing-data files owned by the architecture part; plan §6 carries a supersession note and §9 records the change. |
| C-04 | No shared vocabulary for describing a production: style, medium, source, and motion method were conflated in prose ("animation type", "video type"), so the same production could be described three different ways and routed three different ways. | Throughout `docs/`, README, AGENTS.md (prose, not a single file) | Fixed vocabularies defined in the canonical doc (VISUAL_STYLE, PRODUCTION_MEDIUM, SOURCE_MEDIA, MOTION_METHOD array, SUBJECT_KIND, INTERACTION_PATTERN, ARTICULATION_TARGET) and used exactly everywhere. No giant `animation_type` enum was created. |
| C-05 | Human / animal / creature handling was split across skills with no single distinction: a generated realistic person, a CGI human, live-action footage of a real person, a real animal, and a generated creature were easily confused, and articulation (lips vs beak vs muzzle vs jaw) had no per-subject rule. | `skills/realistic-person/`, `skills/live-action-vfx/`, `skills/cinematic-power/` §2 (each correct in its own scope, no shared distinction) | Canonical doc §6–§7: the five-way live-action/generated distinction, per-subject `SUBJECT_KIND` and `ARTICULATION_TARGET`, and real-animal handling rules (takes and editing, CG touch-up only where the animal cannot perform, generated double recorded as `cgi-animal` for that shot). |
| C-06 | Character registration and voice registration were described as a single "register a character" step, with no stated difference between temporary use and permanent registration — so an upload could be read as a permanent registration, and a user who did not want to register could be read as refusing a video. | README quick start step 2 ("Register a character"); `docs/07-character-registry.md` (registration rules, no first-run invitation, no temporary/permanent mode distinction in the product-identity text) | Addendum C (§C2–§C3 of the canonical doc): first-run invitation with three honest choices (register now / skip + temporary use / register later), the exact prompt "Would you like to register this character for consistent use in future projects?", Temporary Asset Use vs Permanent Character Registration as different modes, and the rule that skipping never prevents creating a video. README quick start now states registration is optional. |
| C-07 | Voice handling had no stated isolation rule in the product-identity documents: nothing said a voice belongs to one owner/workspace, never transfers between characters, or that provider transmission must be disclosed — while the repo also claimed local-first operation, which could be read as "never leaves the device". | README § "Voice"; AGENTS.md (voice line: fixed across episodes, no isolation/privacy statement) | Canonical doc §C5–§C6: private per-character voice registration (user-recorded + AI-generated paths, Voice Profile data fields, no perfect cross-provider reproduction claim, provider limitations recorded); strict voice isolation + privacy (owner/workspace-scoped, no cross-character inheritance, no cross-user leakage, no private media in public GitHub, no public shared library by default, export/sharing needs explicit user action, disclosed provider transmission, no unsupported "never leaves the device" promise, real-person voice cloning needs permission). |
| C-08 | No production-profile record existed: nothing carried the combination of style + medium + source + motion + subjects for a production, so routing, QC, and the manifest could not name what a production was. | (Absence — no `schemas/production-profile.json`; no character-registration schema) | New contracts defined in canonical doc §11 (production profile, character registration) and created/extended by the schema part (schema_version 2.5, additive — see §5 below). |
| C-09 | Performance direction and cinematography were spread across skills with no shared per-shot contract: face/mouth/body direction, subject-specific articulation, dialogue blocking (speaker/listener/eyelines/180-degree rule), motivated camera movement, and focus/depth had no single place that said what a shot plan must carry. | `skills/humanized-production/`, `skills/production-systems/`, `skills/cinematic-power/`, `skills/kids-family-animation/` (each covers part; no shared contract) | Canonical doc §C8–§C10 + §8–§9: performance direction (facial / speaking / body, with subject-specific articulation), multi-character interaction + dialogue blocking, intelligent cinematography (per-shot angle/size/framing/lens/height/movement/focus/DOF/lighting/transition; shallow/deep/rack focus; continuity). Shot/performance-plan extensions are additive schema changes owned by the schema part. |
| C-10 | Reference-video handling had no stated optionality: the video-regeneration system assumed a reference video, and nothing said a production without one is a normal path — inviting invented "reference video analysed" claims. | `skills/video-regeneration/`, README § "Video regeneration" (reference-first framing) | Addendum C §C1: reference video OPTIONAL — Path A (reference-video-assisted) vs Path B (script-and-image-driven); never invent a reference video or claim one was analysed when none was supplied; training clips are training clips, not trailers. |

## 3. What was missing

Beyond the contradictions in §2, the following did not exist in any
document before P0-006:

1. A canonical animation-scope reference (now
   `docs/architecture/ANIMATION_SCOPE_AND_PRODUCTION_MODES.md`).
2. Fixed vocabularies for the seven dimensions (§4 below).
3. A composable routing model (§10 of the canonical doc) to replace
   mutual exclusion.
4. A production-profile contract and a character-registration
   contract (canonical doc §11; schema files owned by the schema
   part).
5. A first-run Character Registration invitation (§C2).
6. A character–voice binding record per shot / dialogue segment
   (§C7) and a shared audio-visual timeline handoff contract with
   stable IDs (§C11, carried by `schemas/timeline-manifest.json`).
7. An explicit honest-limitations statement (§14 of the canonical
   doc): P1 runtime, provider execution, and rendering are not
   executable in P0, and nothing is marked exercised or
   production-verified without actual evidence.
8. A P0 vs P1 separation table for the animation scope (§15 of the
   canonical doc).
9. Product-identity consistency across README, AGENTS.md, and the
   implementation plan (this order's docs part).

## 4. What was changed (per Part B–L + Addendum C)

Parts are as named in CF-WO-P0-006. The docs part (Agent D) owns the
files listed under "Docs part" in each row; other rows are owned by
their part agents and are summarised here so the integrated change
can be checked as a whole. "Changed" means the design decision and
its record; the coordinator confirms each implementing file at
integration.

| Part | Change | Files |
| --- | --- | --- |
| Part B — canonical doc | New authoritative reference defining all 15 items (§1–§15 of the canonical doc) plus Addendum C (§C1–§C12). See §4.1 below for its structure. | **Docs part:** new `docs/architecture/ANIMATION_SCOPE_AND_PRODUCTION_MODES.md`. |
| Part C — realistic-person fix | The "not animation" contradiction is removed: the skill now covers photorealistic digital-human animation including lip-sync, expressions, and body movement; the generated-digital-human vs real-live-action-footage distinction is kept, and consent/likeness/voice-permission rules are preserved. | Skills part: `skills/realistic-person/SKILL.md` (and `docs/15-realistic-person.md` if the skills part updates it). Docs part: README realistic-person section reworded (see §4.2). |
| Part D — explainer clarification | The explainer is clarified as ONE optional profile; its skill text (flat 2D rules, metaphor system, structure) is unchanged as profile rules. | Skills part (if any skill text change is needed — none is required by the docs part). Docs part: README + AGENTS.md explainer lines annotated as one optional profile. |
| Part E — live-action/VFX clarification | Real footage vs generated human/creature/animal is clarified as the five-way distinction (canonical doc §7.1); live-action skill text is unchanged in substance. | Skills part: `skills/live-action-vfx/` (clarification only, if needed). Docs part: canonical doc §7, §9. |
| Part F — character-consistency clarification | Character consistency is stated as style-agnostic identity: the same registry, reference, and anchoring rules apply to humans, digital humans, animals, and creatures, each with its own subject kind, species/anatomy, and articulation target. | Skills part: `skills/character-consistency/` (clarification only). Docs part: canonical doc §6–§7, §C3–§C4. |
| Part G — performance/voice across subjects | Performance and voice skills are stated to apply across human, digital-human, and creature workflows, with subject-specific articulation (no human lips on birds) and per-character language preserved. | Skills part: `skills/voice-consistency/`, `skills/humanized-production/` (clarification only). Docs part: canonical doc §C5–§C8. |
| Part H — composable routing | Mutual exclusion is replaced by the composable model (primary pathway + style profiles + subject capabilities + compatible layers + true conflicts only; no global video-type mutual exclusion). Routing scenarios and their tests are the architecture part's deliverable. | Architecture part: `architecture/SKILL_ROUTING_MATRIX.yaml`, `architecture/WORKFLOW_GRAPH.yaml` (exclusive groups removed/replaced). Docs part: canonical doc §10; plan §6 supersession note + §9. |
| Part I — per-character / per-shot representation | Routing and records are per character and per shot, not per production only: subject kind, articulation target, interaction pattern, and motion method can differ between subjects and shots in one production. | Architecture + schema parts. Docs part: canonical doc §5–§8, §11. |
| Part J — schema evolution | Production profile + character-registration contracts added; character, voice-profile, shot-plan, and performance-plan contracts extended; schema_version 2.5, additive migration (see §5). | Schema part: `schemas/production-profile.json` (new), `schemas/character-registration.json` (new), extensions to `schemas/character.json`, `schemas/voice-profile.json`, `schemas/shot-plan.json`, `schemas/performance-plan.json`. Docs part: canonical doc §11. |
| Part K — canonical doc + product identity | Product identity made consistent everywhere (see §4.2). | **Docs part:** README.md, AGENTS.md (repo root), `docs/implementation/P0_UPDATED_IMPLEMENTATION_PLAN.md` (§9 added; §6 supersession note; governing-rule sentence). `docs/06-installation.md` checked and left unchanged — it does not describe the product as cartoon-only. |
| Part L — tests | Routing scenarios and schema/validator tests for the new model. | Tests part: `tests/` additions + `scripts/validate-repo.py` extensions as needed. Test results: see §13. |
| Addendum C | Reference-video optionality; first-run registration invitation; registration data model; character–image binding; private voice registration; voice isolation + privacy; character–voice binding; performance direction; multi-character blocking; intelligent cinematography; shared timeline; QC. | **Docs part:** canonical doc §C1–§C12. Schema/architecture parts: the contracts that carry them (§11). |

### 4.1 The canonical document's structure

`docs/architecture/ANIMATION_SCOPE_AND_PRODUCTION_MODES.md`
contains, in order: the fixed canonical vocabularies (all seven
dimensions, exact strings); §1 product purpose and animation-first
positioning; §2 what animation means (not cartoon-only, including
the withdrawn "Realism, not animation" wording); §3 visual style
versus production medium (separate dimensions, with a combinations
table; §3.1 the explainer as one optional profile); §4 source-media
types; §5 motion-generation methods (array); §6 character and
subject categories; §7 human/animal/creature distinctions (the
five-way live-action/generated distinction, articulation targets,
real-animal handling); §8 character interactions and conversations
(speaker/listener/eyelines/180-degree rule/blocking); §9 hybrid
live-action/VFX workflows; §10 skill routing and compatibility
(composable model, with an illustrative routing table); §11 schema
responsibilities (file names + what each contract carries);
§12 consent, rights, and private-reference handling; §13 quality
gates (identity, voice, performance, cinematography, audio-visual);
§14 honest capability limitations; §15 what P0 documents versus
what P1 will execute; Addendum C §C1–§C12 (reference-video
optionality; first-run invitation; registration data model;
character–image binding; private voice registration; voice
isolation + privacy; character–voice binding; performance
direction; multi-character blocking; intelligent cinematography;
shared audio-visual timeline; QC); and document control
(supersedes / does-not-change / related records).

### 4.2 The product-identity changes (docs part)

- **README.md.** (1) New animation-first, style-agnostic paragraph
  after the opening paragraph, with a link to the canonical doc and
  the explicit "not a cartoon-only toolkit" statement, plus the P1
  honesty note. (2) Quick start step 2 now says registration is
  optional (temporary use / register later; skipping never prevents
  a video). (3) Realistic-person section: the bullet "Realism, not
  animation. … This is not 2D/3D animation …" is replaced with
  "Photorealistic digital-human animation. … This is a generated
  digital human … not live-action footage of a real shoot, and not
  a still with a voiceover" — keeping the realism target,
  shot-by-shot verification, human-review gate, and no-absolute-
  percentage rule. (4) Explainer section: annotated as one optional
  profile, not the product's animation model.
- **AGENTS.md (repo root).** (1) New animation-first, style-agnostic
  paragraph at the top, naming the canonical doc as governing where
  older documents disagree. (2) New "P0-006 Animation-first,
  style-agnostic production architecture" section after the v2.4
  Brain Architecture Amendment section. (3) Realistic-person skill
  line reframed as photorealistic digital-human animation (IS
  animation). (4) Explainer skill line annotated as one optional
  profile. (5) Docs index now points to the canonical doc and to
  this corrections record.
- **`docs/implementation/P0_UPDATED_IMPLEMENTATION_PLAN.md`.**
  (1) Governing-rule paragraph gains the animation-first,
  style-agnostic sentence. (2) §6 judgement on precedence 11–14
  carries a supersession note (mutual exclusion withdrawn). (3) New
  §9 records P0-006 in the plan (what changes, what it does not do).
- **`docs/06-installation.md` — unchanged, deliberately.** Checked
  first: it lists the explainer as one skill among 15 and does not
  describe the product as cartoon-only, so no correction was needed
  and none was made.
- **Not touched by the docs part:** `skills/`, `architecture/`,
  `schemas/`, `tests/`, `registry/`, `run-tests.sh`, Master Prompt
  files, `main`, CHANGELOG.md (entry text is supplied in the
  delivery report for the coordinator to apply), VoiceStudio /
  OpenMontage internals. No commit, push, PR update, or ZIP was made
  by the docs part; changes are left uncommitted for the coordinator
  to integrate.

## 5. The D6 no-new-skill decision + justification

**Decision (D6): P0-006 adds no new skill.** The 15-skill inventory
is unchanged, and the counts stay 109 distinct systems / 120
numbered entries.

**Justification.** (1) The techniques P0-006 covers are already
covered: the 15 skills already contain 2D, 3D, stylized, and
photorealistic craft, animal and creature performance, live-action
and VFX, emotional performance, voice consistency, and the
command-authority routing model. A new "animation" skill would
duplicate them and create a second source of truth for the same
rules. (2) What was missing was not a technique but a layer above
the skills: a shared vocabulary for describing a production, a
composable routing model for combining skills, and contracts that
carry the description from intake to delivery. A layer is not a
skill; it is expressed as a canonical document (§B), routing data
(Part H), and schemas (Part J). (3) The skill-first loop already
governs new skills: a missing system is written and saved FIRST
only when a skill is genuinely missing, and a permanent canonical
skill change needs explicit user authorisation through the
propose/apply split. No part of P0-006 demonstrates a genuinely
missing skill — every gap found was a contradiction, a missing
contract, or a missing routing rule, not a missing technique.
(4) Keeping the count unchanged preserves the inventory's
auditability: the registry's 15 skills / 165 derived features and
the historical 109/120 claim keep their existing reconciliation
note, and no recount is needed.

**Consequence.** Where a skill's wording contradicted the new model
(C-01 in the realistic-person skill), the fix is a clarification /
extension inside the existing skill, not a new skill — and, per the
skill-first rule, a permanent canonical skill change still needs
explicit user authorisation and a reviewable process.

## 6. The multi-dimensional model

One production is described by choosing from each dimension
independently — never by picking one value from one giant enum:

- **VISUAL_STYLE** — `flat-2d-vector`, `hand-drawn-2d`,
  `illustrated-2d`, `anime`, `cartoon-2d`, `stylized-3d`,
  `semi-realistic-3d`, `photorealistic-3d-cgi`,
  `photorealistic-digital-human`,
  `photorealistic-digital-animal-creature`, `mixed`,
  `captured-live-action`.
- **PRODUCTION_MEDIUM** — `2d-drawn-vector`, `3d-cgi-rigged`,
  `ai-digital-human`, `ai-digital-creature`, `live-action-footage`,
  `hybrid-live-action-cgi`.
- **SOURCE_MEDIA** — `script-only`, `reference-image`,
  `reference-video`, `captured-footage`, `generated-image`,
  `generated-video`, `mixed`.
- **MOTION_METHOD** (array) — `rig-2d-keyframe`,
  `rig-3d-keyframe`, `ai-image-to-video`, `ai-video-to-video`,
  `motion-capture`, `performance-transfer`, `face-animation`,
  `body-animation`, `pose-gesture-transfer`,
  `lip-sync-phoneme-viseme`, `creature-articulation`,
  `rotoscoping-compositing`, `captured-motion`.
- **SUBJECT_KIND** — `human`, `digital-human`, `real-animal`,
  `cgi-animal`, `fictional-creature`, `anthropomorphic`, `mixed`,
  `non-character`.
- **INTERACTION_PATTERN** — `single-performance`,
  `two-person-conversation`, `multi-person-conversation`,
  `human-animal`, `human-creature`,
  `multiple-animals-creatures`, `group-scene`, `silent-reaction`,
  `physical-contact-object`.
- **ARTICULATION_TARGET** — `human-mouth-lips`, `bird-beak`,
  `animal-muzzle`, `creature-jaw-mandibles`, `other`.

Rules: use the strings exactly; `mixed` means a genuine combination
in different shots/subjects, never "not decided"; a value not listed
is not invented — the vocabulary is extended only by a reviewed
change recorded in the canonical doc; style is locked first per
project and held in every shot; medium and style never imply each
other; a combination is invalid only when the two values genuinely
contradict each other for the same shot.

Integration note: `captured-live-action` (VISUAL_STYLE) and
`captured-motion` (MOTION_METHOD) were added at integration, not by
any subagent: routing scenario S6 (unmanipulated captured
real-animal footage) could not otherwise be expressed as a valid
production profile — v2.5 offered no captured-reality visual style
and required at least one motion method. The extension is additive
(only enum values added, nothing removed or retyped), is recorded
in the canonical doc (§2, §3, §5) and in
`schemas/production-profile.json` /
`schemas/visual-style-profile.json`, and S6 now has a schema-valid
fixture (`tests/fixtures/routing-profile-s6-real-animal.json`)
instead of an inline-only profile.

## 7. Schema evolution + migration (v2.5, additive)

- **New contracts.** `schemas/production-profile.json` (one record
  per production: visual style, production medium, source media,
  motion methods, subject kinds, interaction patterns, primary
  pathway + layers) and `schemas/character-registration.json`
  (the registration act: data-model fields, mode, authorisation,
  ID-generation / uniqueness-validation result).
- **Extended contracts.** `schemas/character.json` (subject kind,
  species/anatomy, consent/rights, history); `schemas/voice-profile.json`
  (provider limitations recorded, owner/workspace scope);
  `schemas/visual-style-profile.json` (visual_style, production_medium,
  motion_methods added from the canonical vocabularies, incl. the
  captured-footage values);
  `schemas/scene-plan.json` and `schemas/shot-plan.json` (per-subject
  shot/scene details; shot-plan per-shot cinematography fields: lens,
  height, focus / depth of field, transition);
  `schemas/performance-plan.json` (subject-specific articulation
  targets, speaking/listening state, character/voice binding);
  `schemas/script-to-performance.json` (character–voice binding per
  line/shot, stable dialogue/shot IDs). All seven carry dual-version
  enums (`["2.3", "2.5"]` for character, voice-profile,
  visual-style-profile; `["2.4", "2.5"]` for scene-plan, shot-plan,
  performance-plan, script-to-performance).
- **Unchanged contracts.** `schemas/timeline-manifest.json`,
  `schemas/episode-state.json`, `schemas/project.json` —
  their v2.3/v2.4 definitions stand; the timeline manifest remains the
  shared audio-visual timeline handoff (media references + timing
  only, stable dialogue + shot IDs for VoiceStudio/OpenMontage).
  (Correction at integration: an earlier draft of this section listed
  `scene-plan.json`, `script-to-performance.json`, and
  `visual-style-profile.json` as unchanged — they were in fact
  extended by the schema part; see the extended list above.)
- **Migration rule (v2.5).** Additive only: a new version adds
  optional fields; it never renames, removes, or narrows an existing
  field. A v2.4 record stays valid under v2.5, and no existing
  record needs to be rewritten. Enum values come only from the
  canonical vocabularies (§6). No schema in the public repo carries
  image/audio binaries or personal data — pointers and hashes only;
  media lives in the private overlay.
- **Ownership note.** The schema files themselves are created and
  validated by the P0-006 schema part; this record states the
  contracts they must carry. The coordinator confirms the files
  exist, validate, and carry `schema_version: "2.5"` at integration.

## 8. Private asset storage + ownership model

- **Private by default, public repo never holds private media.**
  Character reference images, voice recordings, and personal data
  are never committed to this public repository; they live in a
  separate private overlay (`characters/README.md`,
  `docs/07-character-registry.md`). Schemas store pointers + hashes
  only.
- **Ownership is per owner / per workspace.** Characters, voices,
  and brand kits belong to one owner in one workspace (per-client
  workspaces in agency work). A voice never transfers between
  characters and never leaks between users; no public shared library
  exists by default; export/sharing needs an explicit user action
  naming what is shared and with whom.
- **Modes, not assumptions.** ONE-OFF (`UPLOAD_ONLY`,
  `TEMPORARY_ASSET_USE`, `GENERATE_FROM_SCRIPT`,
  `EDIT_EXISTING_MEDIA`, `REFERENCE_REVIEW`, `VIDEO_QC`,
  `REMAKE_OR_TRANSFORM`) creates no permanent record; RECURRING
  (`PROJECT_CONSISTENCY`, `REGISTER_CHARACTER`,
  `REGISTER_VOICE_PROFILE`, `REGISTER_SOUND_ASSET`,
  `REFERENCE_LEARN_AND_UPDATE`, `REPORT_UPDATE_ONLY`) creates a
  permanent record only on explicit authorisation. The mode is
  recorded per asset, per production.
- **Authorisation is explicit and recorded.** Registration needs the
  user's explicit words; real-person likeness and voice use need
  that person's permission, recorded (who, for what, when);
  uploading someone else's voice/photo is NOT proof of
  authorisation; public availability of an image is NOT consent.
  Permanent canonical skill learning still goes through the
  propose/apply split (§8 of the implementation plan).
- **Local-first, disclosed transmission.** No central server, API
  backend, or cloud database exists or is added. When a provider is
  used, what is sent to it is disclosed; no "never leaves the
  device" promise is made.

## 9. Production + companion handoff contracts

- **Production contract.** The production profile (§7) is the
  record that makes a production describable, routable, and
  checkable. The production manifest records, per shot, the
  Character ID + reference-asset IDs + Voice Profile ID + Dialogue
  Line ID + Audio Asset ID actually used, with speaking/listening
  state, emotion/delivery, and lip-sync/articulation.
- **Companion handoffs.** One shared audio-visual timeline
  (`schemas/timeline-manifest.json`): stable Dialogue Line IDs and
  Shot IDs across tools and episodes. VoiceStudio receives dialogue
  lines by ID (character, voice profile, emotion, delivery) and
  returns audio assets by ID. OpenMontage receives shots by ID
  (media, timing, transitions) and returns the assembled timeline.
  Neither companion renumbers, reorders, or re-interprets the IDs.
  The Brain directs the companions by instruction; it never silently
  modifies or replaces their internal code.
- **Failure honesty.** If a bound voice cannot be produced, or a
  reference cannot be passed to a provider, the limitation is
  reported (which line / shot, which character, why) and the user is
  asked what to do. A different voice is never silently substituted,
  and a failed gate is never delivered as finished work.

## 10. Performance + cinematography model

- **Performance direction (§C8).** Face (expressions,
  micro-expressions, gaze, blinking, breathing), mouth (lip-sync
  matched to the audio and the language actually spoken, with the
  subject's own articulation target — no human lips on birds),
  body (posture, gesture, walk, weight, effort, hands directed).
  Involuntary motion (blink cadence, eye movements, breathing, head
  micro-drift) is specified per shot. Reaction holds and non-verbal
  events are first-class plan entries; a line with no spoken text
  and no non-verbal event is invalid.
- **Dialogue blocking (§C9).** Who speaks, listens, looks, and
  reacts — per line, per character. Positions recorded; eyelines hit
  the other subject's eyes; shot types chosen from the emotional
  beats; 180-degree rule held unless a motivated, scripted crossing
  is planned and shown; turn timing from the dialogue, with real
  gaps and reaction holds.
- **Intelligent cinematography (§C10).** Motivated movement only.
  Per shot: angle, size, framing, lens, height, movement, focus /
  depth of field, lighting, transition. Focus planned as shallow,
  deep, or rack. Lighting locked per scene; colour follows the
  script's time/light and each emotional beat's palette, never
  randomly inside a scene. Continuity (outfits, injuries, objects,
  wetness, light direction, hero-prop state) tracked across cuts.
- **QC (§13 of the canonical doc, §C12).** Five gates — identity,
  voice, performance, cinematography, audio-visual — run shot by
  shot before delivery, measurable or human-reviewable, with no
  invented numeric fidelity guarantee and with the
  provider-limitation honesty rule. A drifted face is regenerated
  fresh from the definitive reference, never edited or inpainted
  into correctness.

## 11. P0 vs P1 separation

P0 (this work order) defines contracts, definitions, vocabularies,
routing data, consent rules, and QC gates. It builds no runtime: the
runtime skill-routing engine, the script-to-performance runtime,
provider execution, rendering, and adapter conformance tests are P1
work, and remain P1 after P0-006. P0 adds no server, API backend,
database, rendering engine, or companion-internal change, and starts
no P1 work. No capability is marked exercised, tested, or
production-verified in P0 without actual evidence (a run, a render,
a check, or a test, recorded with its result).

## 12. Remaining limitations + unresolved decisions

1. **Routing data files — CONFIRMED at integration.** The
   composable routing model (§10 of the canonical doc) is encoded
   in `architecture/SKILL_ROUTING_MATRIX.yaml` (composable model,
   matrix conflicts narrowed to the two production-level blockers)
   and `architecture/WORKFLOW_GRAPH.yaml` (`exclusive_groups`
   removed; true conflicts TC-1–TC-10 as scoped graph rules). The
   8 routing scenarios pass (`tests/test_routing.py`
   CF-P0-ROUTING-005/006); the old exclusive-groups text is gone.
2. **Schema files — CONFIRMED at integration.** The
   production-profile and character-registration schemas exist and
   validate; the seven extended schemas carry dual-version enums
   (`["2.3", "2.5"]` / `["2.4", "2.5"]`); `python3
   scripts/validate-repo.py` passes with the 2.5 gate (see §13).
3. **Skill-text fixes — CONFIRMED at integration, authorisation
   recorded.** The realistic-person "not animation" wording and the
   clarification wording in live-action/VFX,
   character-consistency, voice, humanized-production, and the
   other skills listed in §15 were made under this work order's
   explicit Part D direction, which is the authorisation for these
   corrections: Part D orders the fixes by name. The propose/apply
   split still governs future reference-learning skill changes
   (new skills learned from reference analysis), not
   work-order-directed corrections. `docs/15-realistic-person.md`
   was also corrected at integration (the skills part had left its
   "not animation" sentence in place).
4. **Routing scenarios — CONFIRMED at integration.** The eight
   routing scenarios and their tests are delivered in
   `tests/test_routing.py` (CF-P0-ROUTING-005/006, all passing);
   the canonical doc's routing examples remain illustrative only
   and are not cited as test evidence.
5. **Provider execution is unvalidated in P0.** No provider route is
   claimed working by this order. Paid provider routes are never
   called live without the user's explicit approval and keys.
6. **Counts.** 109 distinct systems / 120 numbered entries and the
   registry's 165 derived features keep their existing
   reconciliation note; count reconciliation remains deferred (P1,
   per the implementation plan §5).
7. **"Made for Kids" and child-safety rules** are unchanged by this
   order; the kids & family skill's reference library remains
   verified-records-only (R-01–R-19), and no trend becomes a
   permanent rule without verification.
8. **The referenced "End-to-End Script-to-Finished-Video Addendum"**
   was not found on disk when P0-006 began; this order proceeds
   with P0-006 + Addendum C as given. If that addendum appears, it
   is reconciled separately and may add unresolved decisions to
   this list.
9. **Follow-up in P0-007 (CF-WO-P0-007, 2026-11-22).** This
   record's open items were completed by the follow-up work order:
   the timeline manifest is v2.5 with clip/shot/audio bindings,
   synchronization groups, and cross-reference validation
   (Correction A); character/voice ownership is a structured
   record with a both-conditions resolver rule (Correction B);
   v2.5 voice profiles follow conditional validation rules that
   differ by source and approval state (Correction C); the
   speaking-bird fixtures are corrected to `cgi-animal`
   (Correction D); and the OmniVoice CC-BY-NC commercial-use
   limitation is recorded in the companion capability registry
   with no verified commercial voice provider, so the commercial
   voice adapter stays unsupported (Correction E). The full
   record is `docs/implementation/CF-WO-P0-007-corrections.md`.

## 13. Test results

Final integrated run (coordinator, 2026-11-22, branch
`feat/cf-p0-safe-foundations`, local head `2235438` before the
P0-006 commits; all commands run from the repo root):

- `bash tests/run-tests.sh` — **PASS: 47 recorded test-run entries,
  35 distinct test IDs, 28 distinct command strings, all exit 0**,
  status PASS; recorded in `tests/last-run.json`
  (SHA-256 `c923875cff6cfe5afb0676d63b2235b2a73915a8dd24b7d3f50ca2ccfa7ce51d`).
  P0-005 was 45/33/26; the +2 entries are the two new acceptance-test
  files (CF-P0-006-AC-REG, CF-P0-006-AC-DIR).
- `python3 scripts/validate-repo.py` — **PASS** (7 checks: schemas,
  skill_frontmatter, registries, private_overlay, secret_scan,
  absolute_claims, yaml_records). The 2.5 gate was the known
  integration blocker and is fixed (see §15).
- `python3 scripts/generate-registries.py --check` — **CHECK OK**
  (skills=15 features=165 workflows=13 adapters=12).
- `python3 tests/test_schemas.py` — **PASS, 65 checks, 0 failures**
  (19 pre-existing + 45 new v2.5 checks + 1 integration check for
  the S6 captured-footage fixture).
- `python3 tests/test_routing.py` — **PASS, 305 checks, 0 failures**
  (CF-P0-ROUTING-001–006: matrix/graph/companion/agent versions,
  acyclicity, the 8 routing scenarios s1–s8, no video-type exclusive
  group, true-conflict pairs recorded, no cartoon default,
  source-media ≠ rendering style, old fixtures still pass).
- `python3 tests/test_registries.py` — **PASS, 261 checks, 0 failures**.
- `python3 tests/test_performance_semantics.py` — **PASS, 32 checks,
  0 failures**.
- `python3 tests/test_character_registration.py` — **PASS, 72 checks,
  0 failures** (Addendum C acceptance cases AC-01–AC-12 + QC-01).
- `python3 tests/test_production_direction.py` — **PASS, 92 checks,
  0 failures** (acceptance cases AC-13–AC-20 + QC-02/03).
- `python3 tests/test_private_overlay.py` — **PASS, 12 checks, 0 failures**.
- `python3 tests/test_modes.py` — **PASS, 32 checks, 0 failures**.
- `python3 tests/test_reports.py` — **PASS, 37 checks, 0 failures**.
- `git diff --check` — **clean, exit 0**.
- `bash setup.sh --dry-run` — **exit 0, Setup SUCCESS**
  (skills=SUCCESS, voicestudio=SKIPPED, openmontage=SKIPPED).
- `bash setup.sh --core-only` — **Setup SUCCESS, 15/15 skills synced**
  into `.agents/skills/`.
- `python3 scripts/generate-report.py` (+ `--check`) — **CHECK OK**:
  living report matches canonical records.
- `python3 scripts/generate-build-report.py --github-head 24d2e62` —
  regenerated BUILD_REPORT_P0.md, build-report.json,
  release-manifest.json, CHECKSUMS.txt from the final tree (final
  manifest file count and hash-verification result are recorded in
  the delivery report, after the final commits).

Pre-integration failures, all resolved (not hidden): the routing
tests failed 7 checks before integration (3 blocked on the
architecture part's unfinished graph/matrix edits, 4 old checks
asserting schema version 2.4 against the 2.5 working tree); the
validator failed the 9 evolved schemas on the 2.3/2.4-only gate;
the production-direction tests failed 2 schema gates on the fixed
vocabulary before the captured-footage values were added. No test
was weakened to pass: the failing checks were fixed by completing
the work they were waiting on (routing data, validator gate,
captured-footage vocabulary).

## 14. Validation (integrated run)

- `python3 scripts/validate-repo.py` — **PASS** (7/7 checks; see §13).
- `git diff --check` — **clean, exit 0**.
- Report generators run by the coordinator at integration:
  `python3 scripts/generate-report.py` + `--check` (CHECK OK);
  `python3 scripts/generate-build-report.py --github-head 24d2e62`
  (BUILD_REPORT_P0.md, build-report.json, release-manifest.json,
  CHECKSUMS.txt regenerated from the final tree; final manifest
  file count and hash check are recorded in the delivery report).
- The docs part's own run result is superseded by the integrated
  run above; the docs part did not run the report generators.

## 15. Files changed

**Docs part (this draft's author):**

- New: `docs/architecture/ANIMATION_SCOPE_AND_PRODUCTION_MODES.md`
  (canonical reference, §§1–15 + Addendum C §C1–§C12).
- Modified: `README.md` (animation-first paragraph, optional
  registration, realistic-person rewording, explainer as one
  optional profile).
- Modified: `AGENTS.md` (repo root — animation-first paragraph,
  P0-006 section, realistic-person + explainer lines, docs index).
- Modified: `docs/implementation/P0_UPDATED_IMPLEMENTATION_PLAN.md`
  (governing-rule sentence, §6 supersession note, new §9).
- New (draft): `docs/implementation/CF-WO-P0-006-corrections.md`
  (this file).
- Checked, unchanged: `docs/06-installation.md` (not cartoon-only;
  no correction needed).

**Other parts (confirmed by the coordinator at integration):**

- Architecture part: `architecture/SKILL_ROUTING_MATRIX.yaml`
  (composable routing; matrix conflicts narrowed to TC-2/TC-4),
  `architecture/WORKFLOW_GRAPH.yaml` (exclusive groups removed;
  true conflicts TC-1–TC-10; per-character/per-shot
  representation), `architecture/intent-modes.yaml` (unchanged —
  no mode needs a new field), registries regenerated via
  `scripts/generate-registries.py` only.
- Schema part: `schemas/production-profile.json` (new),
  `schemas/character-registration.json` (new), extensions to
  `schemas/character.json`, `schemas/voice-profile.json`,
  `schemas/visual-style-profile.json`, `schemas/scene-plan.json`,
  `schemas/shot-plan.json`, `schemas/performance-plan.json`,
  `schemas/script-to-performance.json` (schema_version 2.5,
  additive, dual-version enums); `schemas/README.md` updated by
  the coordinator to record 2.5.
- Skills part: `skills/realistic-person/SKILL.md`,
  `skills/live-action-vfx/SKILL.md`,
  `skills/explainer-animation/SKILL.md`,
  `skills/character-consistency/SKILL.md`,
  `skills/voice-consistency/SKILL.md`,
  `skills/humanized-production/SKILL.md`,
  `skills/cinematic-power/SKILL.md`,
  `skills/emotional-performance/SKILL.md`,
  `skills/language-authenticity/SKILL.md`,
  `skills/production-systems/SKILL.md`,
  `skills/video-regeneration/SKILL.md`,
  `skills/command-authority/SKILL.md` (12 skills; no new skill).
- Tests part: `tests/test_schemas.py` (+45 v2.5 checks),
  `tests/test_routing.py` (CF-P0-ROUTING-005/006, 8 scenarios),
  new `tests/test_character_registration.py` (AC-01–AC-12 + QC-01)
  and `tests/test_production_direction.py` (AC-13–AC-20 +
  QC-02/03), 30+ new fixtures in `tests/fixtures/`.

**Coordinator integration changes (not owned by any part agent):**

- `scripts/validate-repo.py` — schema_version gate accepts 2.5
  and dual-version enums `["2.3", "2.5"]` / `["2.4", "2.5"]`.
- `schemas/production-profile.json`,
  `schemas/visual-style-profile.json`,
  `schemas/character-registration.json`, canonical doc §2/§3/§5,
  this record §6, `architecture/SKILL_ROUTING_MATRIX.yaml`,
  `skills/character-consistency/SKILL.md`,
  `skills/cinematic-power/SKILL.md`, `tests/test_routing.py`,
  `tests/test_character_registration.py`,
  `tests/test_production_direction.py` — captured-footage
  vocabulary `captured-live-action` / `captured-motion` added so
  routing scenario S6 is a schema-valid profile (see the
  integration note in §6).
- `tests/fixtures/routing-profile-s6-real-animal.json` (new) +
  S6 wired into `tests/test_routing.py` and `tests/test_schemas.py`.
- `docs/15-realistic-person.md` — the leftover "not animation"
  sentence corrected to photorealistic digital-human animation.
- `tests/run-tests.sh` — CF-P0-006-AC-REG / CF-P0-006-AC-DIR
  entries for the two new acceptance-test files.
- `CHANGELOG.md` — [Unreleased] P0-006 entry applied (the docs
  part's entry text was not recoverable from disk, so the
  coordinator wrote it in the established entry style, accurate
  to the integrated work; final test counts filled from the
  integrated run, §13).
- `tests/test_routing.py` — the four stale "schema is version
  2.4" checks now accept dual-version 2.4/2.5.

**Explicitly not changed by this order:** Master Prompt files,
`main`, VoiceStudio / OpenMontage internals, any server/API/database code (none exists, none added), P1 runtime work
(not started).
