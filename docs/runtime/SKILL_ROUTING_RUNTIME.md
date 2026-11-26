# Skill routing runtime (CF-WO-P1-002)

The deterministic runtime skill router and workflow plan builder —
the second production runtime component of Consistency Frame, built
on the P1-001 trusted local session. It promotes the P0 test-only
routing helper into production code (`runtime/skill_router.py`) and
resolves skills and builds workflow plans from structured requests,
using only the compiled routing catalog
(`registry/routing-catalog.json`) as its data source.

## What it is

- **A router, not a generator.** It decides *which skills* run, in
  *which order*, under *which intent mode* — and nothing else. It
  never generates media, never calls a provider, never reads a
  private project asset, never persists anything, and never runs a
  server, API, or cloud database. There is no LLM classifier and no
  script-to-performance generation here.
- **Standard-library only.** The runtime reads the catalog with
  `json` only. PyYAML is a build-time dependency of the catalog
  compiler (`scripts/generate-routing-catalog.py`) and never enters
  the installed runtime.
- **Deterministic.** The same request, catalog, and session always
  produce the same plan. Plans carry no timestamps; the plan hash is
  the SHA-256 of the canonical JSON of the plan without the hash
  field itself.

## The catalog

`registry/routing-catalog.json` (catalog version 2.4) is compiled
from the canonical routing records by
`scripts/generate-routing-catalog.py`:

- `architecture/SKILL_ROUTING_MATRIX.yaml` — the 15 skill records
  (precedence, dependencies, conflicts, applicable modes, quality
  gates, approval conditions, routing dimensions).
- `architecture/WORKFLOW_GRAPH.yaml` — nodes, edges, the 4 parallel
  groups, the conditional `existing-character-prep` group, and the
  scoped true conflicts TC-1..TC-10.
- `architecture/intent-modes.yaml` — the 13 intent modes.
- `architecture/COMPANION_CAPABILITY_REGISTRY.yaml` and
  `architecture/AGENT_COMPATIBILITY_MATRIX.yaml` — companions and
  agents, compiled in so the runtime can read them without YAML.
- A SHA-256 fingerprint of each skill's `skills/<slug>/SKILL.md`,
  so a handoff packet names the exact skill text it was built from.

The catalog records the SHA-256 and version of every source file.
The compiler enforces cross-source consistency and refuses to build
on a contradiction: matrix skills, graph nodes, and `skills/` on disk
must agree exactly; every matrix dependency must be a graph edge;
precedence must be unique 1..15; conflicts and modes must name known
skills and modes; the fixed vocabularies must equal the unions of
the matrix routing dimensions. The generated JSON is never edited by
hand; `generate-routing-catalog.py --check` fails CI when it is
stale (wired into `.github/workflows/p0-ci.yml` and
`tests/run-tests.sh`).

One documented absence, not a contradiction: the cross-cutting
`resource-management` skill states no `routing_dimensions` in the
matrix (it is consulted at every phase, never routed as a stage).
The compiler treats a missing `routing_dimensions` as "no
dimensions stated".

## Requests

`schemas/skill-routing-request.json` (schema version 2.4) defines a
routing request: a unique task/job ID, a valid intent mode, a
validated v2.5 production profile when the mode requires one,
structured routing hints, an explicit primary pathway when one
applies, explicit additional layers, per-shot / per-subject scope,
existing-character status, dialogue / language indicators, and a
clear source for every requested skill selection. Every skill
selection carries its source (`user-request`, `profile-dimension`,
`hint`, `canonical-dependency`, `mode-default`, `router-default`),
so the plan shows why each skill was selected.

What the router never does:

- Never infers style or production medium from one another, and
  never defaults to cartoon: a profile without `visual_style` is
  refused.
- Never infers consent or registration from an upload: animating a
  real person's photo needs an explicit consent hint, and
  registration modes need their documented evidence.
- Never parses `activation_trigger` prose as routing rules: the
  natural-language fields in the matrix are authoritative
  instructions for agents, not executable rules. Routing reads only
  the structured fields (dimensions, dependencies, conflicts,
  modes, graph edges, true conflicts).

## Resolution

`resolve_skills(request, catalog)` returns the selected skills, the
effective rendering styles, the structured blocked diagnostics, and
the per-skill selection records (basis + scope):

- **Base layers** for any production: `command-authority` (the
  router), `production-systems`, `humanized-production`.
- **Hints:** dialogue selects `voice-consistency`; a recurring
  character selects `character-consistency`; a non-English language
  selects `language-authenticity`; explainer structure at the
  flat-2D-vector style selects `explainer-animation` (explainer
  structure at any other style does NOT route through it).
- **Profile dimensions:** a cinematic style selects
  `cinematic-power` (style lock); CGI-animal / fictional-creature /
  anthropomorphic subjects with dialogue select `cinematic-power`
  (creature performance); a digital human from a reference image
  selects `realistic-person` (consent required); live-action footage
  selects `live-action-vfx`; reference-video plus
  `ai-video-to-video` selects `video-regeneration`. Real-animal
  subjects alone add no CG skill.
- **Exactly one primary pathway** where one applies; compatible
  layers alongside it. `resource-management` can never be a primary
  pathway or a standalone layer — it is cross-cutting.
- **Dependencies order, they do not expand the selection.** A
  dependent is never ready before a prerequisite that is also
  selected, but selecting a skill never forces its dependencies
  into the plan: a realistic-person video in English selects
  `realistic-person` without `language-authenticity`, and
  real-animal footage selects `live-action-vfx` without
  `cinematic-power` (the P0 scenarios prove both). A dependency
  that is not selected and does not list the mode is recorded in
  the plan as resolved per the mode's documented scope — never
  silently dropped, never invented.
- **Precedence is a tie-breaker only**, never an exclusion.
- **Mode compatibility:** every selected skill must list the
  request's intent mode. A skill that does not is refused with a
  diagnostic naming the skill, the mode, and a suggested mode
  (e.g. `video-regeneration` in `GENERATE_FROM_SCRIPT` suggests
  `REMAKE_OR_TRANSFORM`).

## True conflicts (TC-1..TC-10)

Conflicts apply only in their documented scope — same subject, same
shot, same dialogue line. Cross-shot and cross-subject combinations
stay allowed. A conflict is returned as a structured blocked
diagnostic naming the rule ID, the skill IDs, the shot ID, the
subject ID, and the decision and input required. Neither skill is
ever silently removed.

- **TC-1** live-action-vfx / cinematic-power: a REAL animal
  directed to speak. A CGI creature speaking is creature
  performance, not this conflict.
- **TC-2** live-action-vfx / realistic-person: captured footage vs
  generated digital human, same subject, same shot (matrix blocking
  pair).
- **TC-3** explainer-animation / cinematic-power: two style locks
  on one named shot (flat-2D vs anime / stylized-3D / photorealistic
  styling).
- **TC-4** explainer-animation / realistic-person: flat-2D explainer
  vs photorealistic digital human, same subject, same shot (matrix
  blocking pair).
- **TC-5** explainer-animation / kids-family-animation: flat-2D
  explainer vs an anime / 3D / photorealistic kids style on one
  named shot. A flat-2D kids style does not conflict.
- **TC-6** kids-family-animation / realistic-person: animated
  character vs photorealistic digital human, same subject, same shot.
- **TC-7** cinematic-power / realistic-person: 2D/3D-animation
  styling vs photorealistic digital human, same subject, same shot.
  A photorealistic digital human talking with a stylized creature
  does not conflict — the styling must be on the same subject.
- **TC-8** agency-advertising / realistic-person: synthetic
  spokesperson vs real-person digital human, same subject.
- **TC-9** explainer-animation / live-action-vfx: flat-2D explainer
  vs captured live-action footage in one shot (per-shot scope; the
  production-level case is already refused by profile validation).
- **TC-10** character-consistency / voice-consistency /
  language-authenticity: articulation must match the subject's own
  anatomy, per subject per dialogue line (human-mouth-lips for
  human / digital-human, bird-beak for birds, animal-muzzle for
  animals, creature-jaw-mandibles for creatures). An explicitly
  non-anatomical `other` articulation is allowed. Where the anatomy
  cannot be established from the supplied structured information,
  the router fails closed and requests resolution instead of
  guessing.

A production-wide claim never locks a shot on its own for TC-3 /
TC-5: a mixed production holds different styles on different
subjects, and without shot scope the router cannot prove they share
a shot. A conflict exists only when two rules genuinely cannot both
hold for the same subject in the same shot.

## Plans

`build_workflow_plan(session, request)` builds the plan under one
exact active `LocalSession`, verified with the P1-001 verifier
(`is_active_session`). Identity comes only from the session — there
is no caller-provided owner or workspace parameter, and the plan
records only the session ID. A missing, forged, expired, copied, or
closed session raises `RoutingError` and no plan is built at all.

Every request-side problem produces a structured **blocked plan**
instead of raising: invalid request, mode incompatibility, missing
evidence, or a true conflict. A blocked plan has status `blocked`,
no steps, and every reason in `blocked_diagnostics` (plus the TC
records in `conflicts`). The caller must resolve the diagnostics
and request a new plan.

A ready plan contains:

- `selected_skills`: every skill with its exact skill path and
  SHA-256 fingerprint, selection basis and scope, quality gate,
  approval conditions, required inputs and expected outputs. The
  matrix stores inputs/outputs as strings and single-key dicts
  (`{label: detail}`) and approval conditions as one string; the
  plan normalises them uniformly to string lists (`"label: detail"`)
  so they validate against the plan schema. The catalog keeps the
  verbatim matrix values.
- `steps` in precedence order, each with its dependencies (matrix
  dependencies restricted to the selected skills), stage, scope,
  quality gate and approval conditions.
- `execution_batches`: deterministic topological levels. A skill
  joins the earliest batch where all its dependencies are in
  earlier batches and it shares a parallel group (whose scope
  condition holds) with every skill already in that batch.
  Anything else gets its own batch — never parallelise merely on
  different names.
- `parallel_groups`: the canonical groups actually parallelised in
  the plan (members in the same batch, scope condition holding):
  `foundation-planning` and `language-and-humanization-prep` (no
  scope condition), `performance-layers-different-scenes` (only
  when the two skills apply to different shots — a production-wide
  claim proves nothing, so the group does not apply without scoped
  claims), `composable-pathways-different-shots` (only when the
  members' claims are pairwise disjoint), and the conditional
  `existing-character-prep` (only when the character is already
  registered — the two registry reads are independent then, so the
  character-consistency → voice-consistency edge is relaxed and the
  two may share a batch; for a new character the edge applies and
  registration runs first).
- `resource_management`: one instruction per phase boundary (one
  per execution batch), never a scheduled step.
- `constraints`: the mode's allowed / forbidden actions, the
  dialogue mode (`VERBATIM_SCRIPT` for `GENERATE_FROM_SCRIPT`),
  derived articulations (a speaking subject with no explicit
  articulation gets the one its anatomy allows, recorded here so
  the plan never guesses silently), and any non-applicable
  dependencies resolved per mode scope.
- `plan_hash`: the deterministic hash (see above).

`validate_routing_plan(plan, catalog)` returns the list of plan
errors (empty means valid): schema version, plan ID, catalog version
and sources, session ID, status, hash recomputation (tamper
detection), step order against dependencies, precedence, and batch
coverage. Structural schema conformance is additionally checked by
the test suite against `schemas/skill-routing-plan.json` with the
repo validator.

`get_ready_steps(plan, completed_step_ids)` is pure: it returns the
step IDs ready to run given the completed receipts — a step is ready
when every dependency is complete, the step itself is not complete,
and every step in every earlier execution batch is complete. No
sleeps, no workers, no external scheduler; the caller drives
execution and reports receipts back.

`build_handoff_packet(plan, step_id, catalog=None)` builds the
packet for one step: the exact skill path and SHA-256 fingerprint,
the selection basis and reason, the scope, the stage and precedence,
the inputs, the expected outputs, the satisfied dependencies (the
prerequisites the plan schedules before this step), the quality gate,
the approval requirements, and the conflicting and prohibited
operations (the skill's matrix conflicts and the true-conflict rules
that involve it, plus the mode's forbidden actions, when a catalog
is supplied).

## Intent modes

The router enforces the mode table from the catalog
(`architecture/intent-modes.yaml`):

- **UPLOAD_ONLY, REPORT_UPDATE_ONLY** never route production work:
  any request in these modes gets a blocked plan.
- **TEMPORARY_ASSET_USE** plans are temporary-only: no permanent
  record, no cross-project reuse. Skills that do not list the mode
  (e.g. `voice-consistency`) cannot be selected in it.
- **Registration modes** (`REGISTER_CHARACTER`,
  `REGISTER_VOICE_PROFILE`, `REGISTER_SOUND_ASSET`) are plan-only
  and need their documented evidence (explicit authorisation, name,
  unique ID, approved reference / rights consent, character link,
  reference audio / explicit instruction, source, licence or
  permission, owner, project scope). The plan carries the canonical
  registration chain as its default.
- **REFERENCE_REVIEW** plans are analysis-only (analyse and
  timecoded report; no skill mutation, no registry change).
- **REFERENCE_LEARN_AND_UPDATE** plans are proposal-only and need an
  explicit user instruction; they never write to canonical records.
- **VIDEO_QC** inspects and reports defects; regeneration needs
  repair authorisation.
- **REMAKE_OR_TRANSFORM** needs an explicit request and a rights
  provenance check.
- **GENERATE_FROM_SCRIPT** keeps dialogue verbatim
  (`VERBATIM_SCRIPT`); a silent dialogue rewrite is refused.
- **PROJECT_CONSISTENCY** reuses by stable ID only; no silent
  create, overwrite, merge, or global registration. The router
  never reads private project records — the constraint is recorded
  on the plan, not executed.
- **EDIT_EXISTING_MEDIA** edits via verified adapters only; the
  mode-compatibility check enforces which skills may run in it.

## What P1-002 does not do

No provider calls, no companion (VoiceStudio / OpenMontage)
invocation, no media generation, no persistence, no permanent
records, no server / API / cloud database, no LLM classifier, no
script-to-performance generation, no character registration UI, no
graphical UI. It does not change the P0 authorization policy
(`scripts/asset_policy.py` is untouched) and does not change the
P1-001 session runtime (`runtime/local_session.py` and
`runtime/authorization.py` are untouched). It plans only.
