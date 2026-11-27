# Production orchestrator runtime (CF-WO-P1-004)

The deterministic production orchestration runtime — the fifth
production runtime component of Consistency Frame, built on the
P1-001 trusted local session, the P1-002 deterministic skill
router, the P1-003 Script-to-Performance runtime and the P1-004
task compiler. It owns the production job lifecycle: intake,
production-analysis validation, production-bundle assembly,
provider-task compilation, G1–G6 gate evaluation, execution-result
recording, and QC correction tasks — under one exact active local
session, with an explicit job state machine.

## What it is

- **An orchestrator, not a creator.** It receives the AI host's
  structured production-analysis draft, validates it against its
  contract and the source script, binds it to a validated
  Script-to-Performance bundle, compiles deterministic
  provider-neutral task packets, and enforces the G1–G6 gates in
  order. It never performs creative analysis, never invents a
  scene, beat, shot, line, character, location or asset, never
  rewrites dialogue, never registers a character or voice profile,
  and never claims a task executed.
- **Standard-library only.** The runtime reads its five canonical
  schemas with `json` only and validates them with the restricted
  JSON-Schema-subset validator shared with the task compiler
  (mirroring `scripts/validate-repo.py::check_schema` semantics).
  No third-party dependency enters the installed runtime, and no
  LLM API lives inside it.
- **Deterministic.** The same validated job, analysis, bundle and
  provider registry always produce the same packets. Jobs, packets
  and packages carry no timestamps and no random identifiers; each
  hash is the SHA-256 of the canonical JSON of the record without
  the hash field itself.
- **Fail-closed.** Any invalid input — session, job state, gate
  order, analysis, bundle, task id, QC report, voice consent, or
  commercial routing — raises `ProductionOrchestratorError` with a
  list of structured, actionable errors. A partially valid job or
  package is never returned as successful.

## Architecture boundary: five roles, kept separate

The Universal AI Production Brain separates five roles. This
runtime is the Brain's orchestration layer; it is none of the
other four.

- **Consistency Frame — Central Brain.** Owns production
  instructions, skill selection, script-to-production contracts,
  canonical plans, character and voice identity references,
  workflow authority, production task compilation, QC policies,
  and project continuity and provenance. This runtime is the
  Brain's executable orchestration half.
- **AI Reasoning Host.** The connected AI model (ChatGPT, Claude,
  Gemini, Muse, or another compatible host) performs creative and
  semantic reasoning: it reads the Brain's skills and contracts,
  analyses the script, proposes missing production details, and
  fills the production-analysis draft. The Brain validates and
  directs this work; the host's draft is never trusted until the
  runtime validates it.
- **Implementation Agent.** Muse or another coding agent modifies
  the repository only when explicitly assigned a Work Order. It is
  not a media-generation provider.
- **Media Execution Providers.** Image, video, voice, music,
  sound, lip-sync and editing providers generate the requested
  assets. The Brain matches tasks to providers only on evidenced
  capabilities (`registry/providers.json`); an unmatched task
  compiles as a complete provider-neutral handoff.
- **Production and Editing Tools.** VoiceStudio, OpenMontage,
  FFmpeg, OpenTimelineIO and compatible editors. The Brain directs
  them through verified interfaces and task instructions; it never
  modifies their internal code.

The repository contains no LLM and no rendering engine, and this
runtime must never pretend otherwise. No central web server, cloud
database or hosting platform is required or built.

## Job state machine

```
INTAKE -> ANALYZING -> PLAN_READY -> AWAITING_G1_APPROVAL
  -> TEST_READY -> AWAITING_G2_APPROVAL -> BATCH_PRODUCTION
  -> EDITORIAL_REVIEW -> PICTURE_LOCK -> FINISHING -> FINAL_QC
  -> DELIVERED
```

`BLOCKED` is reachable from any state; a blocked job resumes only
to the state it came from, and only while no gate is BLOCKED.
Three transitions are operation-gated and can never be reached by
a bare transition:

- `ANALYZING -> PLAN_READY` happens only inside
  `build_production_bundle` (the analysis validates and the S2P
  bundle builds).
- `AWAITING_G1_APPROVAL -> TEST_READY` and
  `AWAITING_G2_APPROVAL -> BATCH_PRODUCTION` happen only inside
  `evaluate_production_gate` when G1 / G2 passes (or is waived by
  the user with a recorded reason).

The one exception is resuming from BLOCKED: it returns to the
state the job came from even when that state is operation-gated,
because the operation that put the job there already passed the
gate.

Stage-gated transitions check their gate: `PICTURE_LOCK` needs G3,
`FINISHING` needs G4, `FINAL_QC` needs G5, `DELIVERED` needs G6 —
each PASS or WAIVED, never merely attempted.

## G1–G6 gates

The six Addendum-01 stage gates (G1 Visual Planning, G2 Test
Production, G3 Editorial Review, G4 Picture Lock, G5 Finishing,
G6 Delivery) are enforced in order: a gate cannot pass or be
waived while an earlier gate is unresolved. A `BLOCKED` decision
moves the job to `BLOCKED`. A `WAIVED` decision needs a non-empty
waiver reason and the user as authoriser — only the user waives a
gate — and is recorded on the gate, never silent. Passing G1
after a block advances the job past the gate in one step; other
gates restore the state the job came from.

## Production analysis (Layer A contract)

The analysis draft (`schemas/production-analysis.json`) is the
contract the reasoning host fills: premise, narrative structure,
scene-by-scene breakdown (purpose, beats, characters, location,
time of day, transitions), character resolutions, emotional
progression, pacing, shot direction, sound direction, and the
open questions that need a user decision.

- **Story preservation.** The user's story, events, meaning and
  dialogue are authoritative. The analysis must not invent events,
  change relationships or the ending, rewrite dialogue without
  explicit permission, add scenes or subplots, or remove important
  events. The runtime checks dialogue counts against the source
  script and refuses a bundle when they disagree.
- **Provenance.** Every material decision carries one of
  `EXPLICIT_FROM_USER`, `FROM_APPROVED_PROJECT_CANON`,
  `INFERRED_FOR_PRODUCTION`, `NEEDS_USER_DECISION`. An inference is
  never presented as fact. Ordinary missing creative details are
  inferred and labelled inferred; the user is asked only when a
  detail would materially change the story, identity, rights,
  privacy, safety, budget or production outcome.
- **Unresolved decisions block planning.** An analysis with open
  questions or needs-decision characters cannot build a production
  bundle. The host (or user) resolves them first.
- **Environment and asset requirements (R1 A1).** A scene may
  carry structured environment intelligence — background design,
  weather, atmosphere, foreground / midground / background
  requirements, environment continuity — and `important_props`
  with a design brief, visual and physical requirements,
  continuity restrictions and provenance. Asset references bind a
  scene to approved assets by stable ids. Approved assets always
  win; an inferred temporary prop is never permanently registered
  (approved permanent props reuse `schemas/prop.json` unchanged).
- **Sound timing (R1 A3).** A sound cue carries a stable cue id,
  scene / shot / beat ids, a start anchor (`SCENE_START`,
  `SHOT_START`, `BEAT_START`, `ACTION_ONSET`, `DIALOGUE_LINE`,
  `CONTINUOUS_SCENE`, `USER_SPECIFIED_TIME`), an optional end
  anchor, offset and duration, distance, perspective, intensity,
  sync target and mixing priority. Timing is relative — an exact
  global timecode is never invented. Planned timing (from the
  plan) and actual rendered timing (from an execution result) are
  distinguished; a plan never claims audio was already generated.
- **Cross-reference integrity (R1 A4).** Scene ids must resolve
  to the validated Scene Plan, beat ids within their scene,
  shot-direction shot ids to the Shot Plan with the scene
  agreeing, sound cue scene / shot / beat references must
  resolve, and character resolutions must cover every required
  identity. Duplicate shot-direction entries are rejected.
  Unknown references are never silently ignored. These checks run
  against the actual built P1-003 bundle inside
  `build_production_bundle` (and again explicitly in
  `plan_script_to_production`), through
  `validate_analysis_bundle_references`.

## Character resolution

Approved identities always win. A character the analysis resolves
as `approved` binds the registered character id, and the registry
must actually contain it. A character with no approved identity
gets a task-local design proposal
(`schemas/character-design-proposal.json`): a design brief, fixed
structure, reference-preparation requirements and a job-scoped
status. Proposals never register anything permanently — permanent
registration still requires the existing explicit-authorisation
flow — and the resolver is pure: it never creates, edits or
registers anything.

**Coverage (R1 A2).** An empty `character_resolutions` array is
valid only when the source genuinely has no visible character
subjects. When the source has speaking or visible identities,
every distinct required identity must be resolved exactly once —
missing, duplicate and unknown resolutions are all rejected. A
narrator / voice-over is not a visible character: an identity the
analysis marks with a narrator role needs no visible-character
resolution, and a speaking identity that appears in no scene and
no shot is treated as a voice-over. The P1-003 zero-dialogue
limitation stands: a script with no dialogue lines still has no
valid performance plan, and the runtime never invents dialogue
to satisfy it.

## Task compilation

`compile_provider_tasks` delegates to the task compiler
(`runtime/task_compiler.py`), which converts the validated bundle
and analysis into deterministic task packets: character/reference
preparation, environment and prop references, image generation,
video generation, voice generation (exact dialogue text,
character and voice profile ids, language, emotion, delivery,
pauses, timing, consent and provider eligibility), time-aware
sound generation (structured cue timing from the analysis or the
bundle audio plan, with `timing_status: "planned"`; intentional
silence is a creative decision, never a defect, and generates no
sound-generation request), technical media operations, creative
editing, and semantic QC review. Provider matching uses only
evidenced capabilities; commercial jobs never match a provider
whose commercial use is not approved (the default OmniVoice
weights are CC-BY-NC). Unmatched tasks compile as complete
provider-neutral handoffs.

**Technical vs creative (R1 B4).** FFmpeg matches only technical
media operations it genuinely evidences — probe, assemble,
transcode — as `media-technical` tasks. It does not match the
complete creative editing/finishing workflow or human semantic
QC: `creative-editing` (picture editing, creative colour review,
narrative pacing review) and `semantic-qc-review` (semantic
visual/audio review, character-continuity and physical-realism
assessment) have no verified provider in the registry and always
compile as handoffs for human work. A provider matches only what
its capability record proves; OpenMontage stays `NOT_TESTED`.

**Environment and prop packets (R1 B1/B2).** One
environment-reference packet per scene carries every validated
scene-environment detail plus approved asset ids as required
`approved-asset` inputs. One prop-reference packet per distinct
prop carries the design brief, visual and physical requirements,
continuity restrictions and approved reference ids; an approved
recurring prop never gets duplicate tasks, an approved prop is
prepared from its approved record (never redesigned), and a prop
with no approved record gets a task-local proposal. Nothing here
permanently registers a prop.

## QC and regeneration

`build_qc_correction_tasks` takes a QC report (defects with
severity Critical / Major / Minor / Polish, shot and task
references) and compiles correction packets only for the shots
that failed: Critical and Major always, Minor only with repair
authorisation, Polish never. Only the defective shots get
packets — approved neighbours are preserved — and each packet
re-matches as its original task type, so a failed video shot is
never silently re-typed. Execution results are recorded as facts
(`record_execution_result`); a failed result does not auto-block
the job — the QC loop decides what gets corrected.

## Persistent production job store (R1 Task C)

`runtime/production_store.py` persists production jobs and
checkpoints as local JSON under an explicitly configured local
workspace root — `<root>/jobs/<job_id>.json` and
`<root>/checkpoints/<job_id>/<checkpoint_id>.json` — standard
library only, atomic writes through `scripts/atomic_write.py`.
Every record is an envelope (`schema_version "2.5"`,
`store_format_version 1`, `record_kind`, `job_id`,
`project_id`, `owner_id`, `workspace_id`, `job`,
`record_hash` — SHA-256 of the canonical JSON without the hash
field). Only production metadata is persisted: ids, state, gate
states, analysis/bundle hashes, task package and statuses,
execution-result references, QC reports, correction rounds,
approved character/prop/voice ids, asset references with
provenance, version information. Raw media, voice recordings,
personal photos, model weights, API keys, passwords, tokens,
raw private voice samples and private media bytes are never
stored; a record carrying any of those is refused.

Path safety: the root must be absolute; job and checkpoint ids
must match `^[a-z0-9][a-z0-9-]{2,63}$`; paths are built only from
validated components; symlink containment is checked with
`realpath` and a symlinked record file is refused on read.
Malformed or tampered records are reported, never silently
dropped (`list_production_jobs` returns them in
`invalid_files`). Files are `0o600` and directories `0o700` on
POSIX; on Windows the store relies on the user-data-directory
ACL behaviour (the P1-001 R2 pattern).

A stored session id is provenance only, never authorization.
Saving needs an exact active P1-001 session; resuming needs a
NEW exact active session plus a project/owner/workspace match,
stored-job validation and gate revalidation, and it rebinds
`job["session_id"]` to the new session. Resume refuses
`DELIVERED` jobs and never triggers execution or auto-resumes
paid/external provider tasks — continuing a resumed job needs a
fresh authorized action. Recovery covers `ANALYZING`,
`PLAN_READY`, the G1/G2 waiting states, `BATCH_PRODUCTION`,
`EDITORIAL_REVIEW`, `PICTURE_LOCK`, `FINISHING`, `QC` and
`BLOCKED`.

## The unified entry point (R1 Task D)

`plan_script_to_production` is the one deterministic entry point
for script-to-production planning. Given an active session, a
job in `ANALYZING`, the source script, the production profile,
the P1-003 draft inputs, the AI host's production-analysis
draft, the routing plan, a bundle id, the required proposal
records, optional approved props and provider records, it runs
the whole pipeline in order: validate the job and session,
validate the analysis draft, build the P1-003 production bundle
(including the analysis-to-plan cross-reference checks),
validate the analysis-to-plan references once more explicitly,
compile all task packets, build the complete task package, and
— when a store root is given — persist the planned job and a
`plan-<bundle_id>` checkpoint through the production store.
It returns the production bundle, the updated job, the task
package and the persistence information. No media is generated,
no provider is executed, and no creative reasoning happens
inside it. `wf-generate-from-script` is NOT promoted by this
entry point: no timeline manifest is produced and no fake media
path is invented.

## Short-form and long-form

The same contracts and orchestration serve every delivery
profile (`short-form-15-60s`, `short-explainer-1-3min`,
`story-5-15min`, `documentary-20-60min`, `long-form`, `episodic`),
carried on the job as `format_profile`. Short-form prioritises an
immediate hook, clear visuals, efficient coverage, faster pacing
and compact sound; long-form uses chapters, narrative arcs,
slower development, breathing space, detailed continuity and
long-range character, voice and environment tracking. The user's
aspect ratio, resolution, frame rate and platform remain
authoritative and live in the production profile.

## Numbering systems (do not confuse them)

- **Production Complexity P0–P3** is a video-quality scope
  classification (Essential / Strongly Recommended / Advanced /
  Specialized) — how much production machinery a project uses.
- **Engineering milestones P0/P1/P2/P3** are separate project
  phases (P0 safe foundations, P1 runtimes, P2/P3 future work).
- **G1–G6** are production approval gates — the stage-gate
  workflow a job must pass through.
- The three numbering systems must never be confused.

## Public API

`runtime/production_orchestrator.py`:

- `create_production_job(session, job_id, project_id,
  format_profile, *, commercial_use=False, stills_first=False,
  script_contract_id=None)` — job in `INTAKE`.
- `transition_job(session, job, new_state)` — explicit state
  machine, operation-gated targets refused.
- `resolve_character(session, job, resolution, *,
  approved_registry=None, proposals=None)` — pure resolution.
- `build_production_bundle(session, job, routing_plan, script,
  profile, draft, analysis, bundle_id,
  dialogue_rewrite_authorised=False)` — `(production_bundle, job)`.
- `compile_provider_tasks(session, job, production_bundle,
  analysis=None, proposals=None, providers=None, *,
  voice_consent=False, voice_kinds=None, providers_path=None,
  approved_props=None)` — `(task_package, job)`.
- `plan_script_to_production(session, job, script, profile,
  draft, analysis, routing_plan, bundle_id, proposals=None,
  approved_props=None, providers=None, *, voice_consent=False,
  voice_kinds=None, dialogue_rewrite_authorised=False,
  store_root=None, providers_path=None)` — the unified
  script-to-production planning result (bundle, job, task
  package, persistence information).
- `evaluate_production_gate(session, job, gate_id, decision, *,
  note=None, waiver_reason=None, authoriser=None)` — job.
- `record_execution_result(session, job, task_id, result)` — job.
- `build_qc_correction_tasks(session, job, qc_report,
  providers=None, *, providers_path=None)` —
  `(correction_package, job)`.
- Validators: `validate_format_profile`,
  `validate_production_analysis`,
  `validate_analysis_bundle_references`,
  `validate_character_design_proposal`,
  `validate_gate_state`, `validate_job`, `job_hash`.

`runtime/production_store.py`:

- `save_production_job(session, store_root, job)` — record path.
- `load_production_job(store_root, job_id, project_id)` —
  verified envelope record (session-free metadata read).
- `list_production_jobs(store_root)` — `{"jobs": [...],
  "invalid_files": [...]}`.
- `save_production_checkpoint(session, store_root, job,
  checkpoint_id=None)` — record path.
- `resume_production_job(session, store_root, job_id,
  project_id)` — job rebound to the new session.

`runtime/task_compiler.py`:

- `compile_task_package(session, job, bundle, analysis=None,
  proposals=None, providers=None, *, voice_consent=False,
  voice_kinds=None, providers_path=None, approved_props=None)` —
  package.
- `compile_regeneration_packets(session, job, qc_report,
  providers=None, *, providers_path=None)` — package.
- `match_provider_for_task(task_type, providers, *,
  commercial_use=False, needs_clone=False)` —
  `(provider_id | None, reason)`.
- `load_provider_registry(providers_path=None)` — validated list.
- Validators: `validate_task_packet`, `validate_task_package`,
  `validate_provider_record`, `task_packet_hash`.

## What this runtime does not do

- No creative reasoning, no LLM API, no heuristic that guesses
  meaning from natural language.
- No media generation, no provider calls, no paid calls, no
  credentials in the repo.
- No permanent registration of characters, voice profiles, sound
  assets or canonical rules.
- No server, API backend, cloud database or hosting platform.
- No silent fallback: an unmatched provider, an unresolved user
  decision, a failed gate, or a missing voice profile is an
  explicit error or an explicit handoff, never a quiet substitute.
