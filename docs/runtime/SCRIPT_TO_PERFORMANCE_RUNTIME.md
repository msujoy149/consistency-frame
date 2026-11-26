# Script-to-Performance runtime (CF-WO-P1-003)

The deterministic Script-to-Performance runtime — the third
production runtime component of Consistency Frame, built on the
P1-001 trusted local session and the P1-002 deterministic skill
router. It validates, binds and assembles a structured source
ScriptContract, an approved production profile and the AI layer's
analysis drafts into final schema-valid Scene, Shot and
Performance Plans plus the Script-to-Performance binding record,
under one exact active local session and one valid, ready P1-002
routing plan.

## What it is

- **A validator and assembler, not a creator.** It receives the
  AI layer's structured analysis drafts and guarantees contract
  integrity: every record validates against its canonical schema,
  every cross-reference resolves, the dialogue survives verbatim,
  and the assembly is deterministic. It never performs creative
  analysis, never invents a scene, beat, shot, line, character,
  location or asset, and never rewrites a word of dialogue unless
  the rewrite is explicitly authorised per line.
- **Standard-library only.** The runtime reads the six canonical
  schemas with `json` only and validates them with its own
  restricted JSON-Schema-subset validator (mirroring
  `scripts/validate-repo.py::validate_instance` semantics). No
  third-party JSON Schema dependency enters the installed runtime.
- **Deterministic.** The same validated script, profile, drafts,
  routing plan and session context always produce the same bundle.
  Bundles carry no timestamps and no random identifiers; the
  bundle hash is the SHA-256 of the canonical JSON of the bundle
  without the hash field itself.
- **Fail-closed.** Any invalid input — session, routing plan,
  script, profile, draft, or rewrite authorisation — raises
  `ScriptToPerformanceError` with a list of structured, actionable
  errors. A partially valid bundle is never returned as successful.

## Two layers, kept separate

Layer A (AI reasoning / script analysis) is done by the active AI
agent using the canonical skills: it reads the script, analyses
scene/beat/dialogue-line structure, and produces the structured
drafts this runtime consumes. Layer A is **not** implemented here.

Layer B (this deterministic runtime) receives the source
ScriptContract, the approved production profile and the structured
drafts, validates them, binds them, and assembles the final plans.
It must not pretend to understand arbitrary natural-language
scripts through deterministic Python heuristics: there is no LLM
API, no provider client, and no heuristic that guesses meaning
from prose. Where the runtime cannot decide something from the
supplied structured records, it fails closed or documents the
limitation instead of inventing an answer (see "Documented
limitations").

## Input and output contracts

`build_script_to_performance_bundle(session, routing_plan, script,
profile, draft, bundle_id, dialogue_rewrite_authorised=False)`
accepts:

1. An exact active P1-001 `LocalSession`.
2. A valid, ready P1-002 routing plan with
   `intent_mode == GENERATE_FROM_SCRIPT` and the plan's session ID
   equal to the exact active session.
3. A structured source ScriptContract
   (`schemas/script-contract.json`, v2.3).
4. A valid production profile
   (`schemas/production-profile.json`, v2.5).
5. A structured analysis draft: `scene_plan`, `shot_plan`,
   `performance_plan` (required), plus optional `audio_plan`,
   optional `editing_plan`, optional `character_voice_binding`,
   optional `character_voice_bindings`.
6. A caller-supplied valid bundle ID (lowercase letters, digits
   and hyphens, 3–64 characters).
7. An explicit dialogue-rewrite authorisation flag, defaulting to
   `False`. Only an actual boolean `True` is affirmative approval.

It returns an in-memory bundle:

```json
{
  "bundle_id": "s2p-test-001",
  "schema_version": "2.5",
  "session_id": "<exact active session ID>",
  "routing_plan_id": "plan-<task_id>",
  "script_contract": { "...": "validated source script" },
  "production_profile": { "...": "validated profile" },
  "script_to_performance": { "...": "final binding record" },
  "scene_plan": { "...": "final Scene Plan" },
  "shot_plan": { "...": "final Shot Plan" },
  "performance_plan": { "...": "final Performance Plan" },
  "bundle_hash": "<SHA-256 hex digest>"
}
```

The bundle carries the validated script and profile alongside the
plans so the hash is recomputable from the bundle alone and covers
the full validated input. Input objects are never modified in
place — the builder works on deep copies throughout, and the
returned bundle is self-checked with
`validate_script_to_performance_bundle()` before it is returned.

## Public API (`runtime/script_to_performance.py`)

- `build_script_to_performance_bundle(session, routing_plan,
  script, profile, draft, bundle_id,
  dialogue_rewrite_authorised=False)` — the main builder (above).
- `validate_script_contract(script)` — schema + P0 semantic
  rules for a ScriptContract.
- `validate_production_profile(profile)` — schema + the P1-002
  profile field rules for a production profile.
- `validate_scene_plan(plan)`, `validate_shot_plan(plan)`,
  `validate_performance_plan(plan)` — schema + P0 semantic rules
  for one plan each.
- `validate_script_plan_drafts(draft, script=None)` — the three
  plans, the optional audio/editing/binding fields, and the
  cross-references among the drafts (plus dialogue mapping and
  source-shot coverage when the script is supplied).
- `validate_script_to_performance_bundle(bundle)` — structure,
  every embedded record, the full cross-reference validation, and
  the bundle-hash recomputation.
- `script_to_performance_hash(bundle)` — the deterministic SHA-256
  of the canonical JSON of the bundle without `bundle_hash`.
- `ScriptToPerformanceError(ValueError)` — raised on any failure;
  carries the list of error strings in `.errors`.

## Session and routing binding

The builder requires an exact active `LocalSession` verified by
the P1-001 verifier (`is_active_session`); a missing, forged,
copied, expired or closed session fails closed and no bundle is
built. The routing plan is verified with the existing P1-002
validation (`validate_routing_plan` against the compiled catalog):
a blocked plan, an invalid plan, or a plan whose intent is not
`GENERATE_FROM_SCRIPT` is rejected, and the plan's session ID must
match the exact active session. The builder preserves the router's
selected skills and decisions — it records only the routing plan
ID and never selects or invents additional skills. No second
authorization policy is created; the P1-001 session is the only
identity source. A plan so malformed that the router validator
itself cannot run is rejected with a structured error rather than
leaking the validator's exception.

## Dialogue preservation

Default `dialogue_mode = VERBATIM_SCRIPT`: the user's original
dialogue is preserved exactly, character for character. The
runtime never rewrites, summarises, translates, auto-corrects
grammar, replaces original lines with performance descriptions,
reorders lines, or drops lines without a validation error. Every
source dialogue line maps to exactly one Performance Plan line,
by `line_id`, in order. Checked: missing line IDs, extra line IDs,
duplicate line IDs, reordered source dialogue, changed dialogue
text, and source-supplied dialogue metadata: when the source line
supplies a `character_id`, the Performance Plan line must carry
the SAME `character_id` (omitted, wrong type or different all fail
closed); when the source line supplies a `language`, the
Performance Plan line must carry the SAME language (omitted,
wrong type or different all fail closed). Nothing is invented and
nothing is translated — no replacement character ID is created
and no language is inferred (P1-003-R1, Task C). A source line
that supplies neither imposes no metadata requirement.

A non-verbal source line (empty text) must be performed
non-verbally: the performance line carries no spoken text (the
performance-plan schema gives `dialogue.text` minLength 1, so a
non-verbal line omits the text key rather than carrying an empty
string — the P0 bird-fixture pattern) and must carry at least one
`non_verbal_events` entry (P0 PERF-004).

## Rewrite authorisation

A plan-level `SCRIPT_EDIT_REQUESTED` value alone does **not**
authorise rewriting. A rewrite is only valid when all five hold:

1. the caller explicitly supplies
   `dialogue_rewrite_authorised: true` (an actual boolean `True`;
   a string, number or `None` is rejected, not silently treated as
   false);
2. the plan uses `SCRIPT_EDIT_REQUESTED`;
3. the exact line has `rewrite_permitted: true`;
4. the original source text remains preserved in the original
   `dialogue.text`;
5. any changed version is stored separately in `rewritten_text`.

A rewrite never overwrites the original text. Omission of
authorisation means false.

## Scene / Shot / Performance cross-reference rules

The four final records form one coherent production timeline.
The builder validates, explicitly:

- Script-to-Performance root IDs match the actual Scene / Shot /
  Performance Plan IDs, and its `id` matches the bundle ID.
- Project IDs agree wherever supplied (script, profile, scene,
  shot, performance, Script-to-Performance).
- Schema versions agree across the three plans; the binding
  record uses the agreed version. `dialogue_mode` agrees between
  the script and the performance plan.
- Scene IDs are unique; beat IDs are unique within their scene;
  shot IDs are unique; performance line IDs are unique.
- Every shot's `scene_id` resolves to a real Scene Plan scene;
  every supplied shot `beat_id` resolves inside its referenced
  scene.
- Source shot IDs, when supplied, are not silently omitted from
  the shot plan.
- Performance line IDs match source dialogue line IDs exactly
  (see Dialogue preservation).
- Character references resolve into the known set: script
  dialogue speakers, profile per-subject overrides, and the scene
  plan cast (scene plan character IDs and subjects are definitions
  that establish context; shot, performance-line and binding
  character references must resolve into that set).
- Voice bindings reference valid dialogue line IDs (in either ID
  namespace: the script's `line_id` or the performance line's
  `dialogue_line_id`); a `shot_id` when present must resolve to a
  shot-plan shot; a binding's `character_id` must resolve and must
  equal the performance line's character for that line. Singular
  and plural binding forms together are ambiguous only when two
  bindings for one line differ on any field — identical duplicates
  are allowed.
- Editing reaction holds reference valid dialogue line IDs
  (`after_line_id` in either ID namespace).
- Optional audio and editing records remain schema-valid.
- For repeated subject IDs across scene and shot plans and
  profile overrides, contradictory identity or production-medium
  information is detected: `subject_kind`, `representation`,
  `rendering_style`, `source_media`, `articulation_target`,
  `is_live_action_footage` and `species` must agree wherever
  supplied, and a scene/shot `motion_method` must agree across
  plans and be a member of the profile's `motion_methods` list for
  that subject when listed.

## Production dimensions and articulation

The independent production dimensions are respected, never
collapsed into one animation-type field: `representation`,
`rendering_style`, `source_media`, `motion_method`, `subject_kind`,
`articulation_target` and live-action provenance are separate
fields with their own vocabularies. Human mouth/lip articulation
is never applied to an animal or creature: the P0 articulation
map (`ARTICULATION_BY_SUBJECT_KIND`) plus the bird-species rule
("African grey parrot" maps to bird-beak, by substring) are
enforced. When the articulation is `human-mouth-lips` and the
subject kind cannot be established from the supplied context, the
check fails closed — but only in the cross-reference phase, after
kinds have been resolved from all sources (script, profile,
scene, shot, performance); single-record validators do not fail
closed on an unestablishable kind, because another record may
supply it. Anatomy, species and identity are never guessed.

## Validation and error model

All records validate against the existing canonical schemas
(Script Contract, Production Profile, Scene Plan, Shot Plan,
Performance Plan, Script-to-Performance) with the restricted
subset validator, plus the preserved P0 semantic checks:

- CF-P0-PERF-001 emotion-intensity bounds (0–10).
- CF-P0-PERF-002 strictly positive durations.
- CF-P0-PERF-003 canonical emotion taxonomy.
- CF-P0-PERF-004 non-verbal event requirements.
- CF-P0-PERF-005 line-level dialogue rewrite permission.

An optional field omitted from a record is not equivalent to a
present field containing null when the schema disallows null:
explicit nulls are rejected with a field-naming error (the
nullability-parity approach from P1-002-R1-R3, applied here to all
156 optional property paths across the six consumed schemas — see
the `CF-P1-003-NULL156` regression group). No P0 schema is changed
to make invalid runtime output pass.

Errors are structured strings naming the record, field and rule
(`performance_plan.lines[0].dialogue.text: ...`,
`subject char-001: contradictory subject_kind: ...`). The builder
raises at the first failing stage and never returns a partial
bundle.

Bundle shape validation (P1-003-R1, Task A): the bundle
validator checks every required field for BOTH presence AND
correct type — `bundle_id`, `schema_version`, `session_id`,
`routing_plan_id`, `bundle_hash` and all six embedded records
(`script_contract`, `production_profile`,
`script_to_performance`, `scene_plan`, `shot_plan`,
`performance_plan`). A required field containing `None`, or a
required record containing a list, scalar or other wrong type,
is invalid; validation is never skipped because a field is
`None` or is not a dictionary, so a malformed bundle is never
reported valid merely because its hash was recomputed.

Fail-closed input validation (P1-003-R1, Task B): public
validation functions never leak a raw Python implementation
exception on schema-invalid JSON-shaped input. Types are checked
before a value is used as a dictionary or set key, before a
string method is called on it, and before set membership is
tested with it — malformed identifiers, project IDs, schema
versions, subject dimensions, articulation/species values and
live-action provenance fields all return structured
field-specific errors. The builder converts invalid input into
`ScriptToPerformanceError`, never a raw `TypeError` or
`AttributeError`. Invalid values are never silently coerced into
valid ones.

## Deterministic hashing

`script_to_performance_hash(bundle)` canonicalises the bundle as
JSON with sorted keys, `", "`-free separators and Unicode kept
unescaped, then hashes with SHA-256 — the same canonicalisation
as the router's `plan_hash`. The hash covers the bundle minus
`bundle_hash` itself, so it is recomputable from the bundle alone
and any tampering (content or hash) fails
`validate_script_to_performance_bundle`. The hash lives only on
the bundle, outside the schema-governed records: no canonical
schema provides a field for it.

## Documented limitations

Two things the work order asks for are not machine-decidable
from the supplied structured records, and the runtime does not
pretend otherwise:

- **Beat-level non-verbal-event requirement.** Scene-plan beats
  carry no spoken-text marker, so the runtime cannot tell from
  the beat alone whether a non-verbal event is required there.
  P0 PERF-004 binds performance-plan lines only; a scene beat
  with a sad emotion and no non-verbal events is valid.
- **Motivated camera movement.** Only the camera-movement enum is
  validated; whether a movement is "motivated" by the dramatic
  intent is a judgement for the AI layer. Static camera is a valid
  deliberate choice, and the runtime never generates camera
  movement to fill optional fields.

One canonical-contract tension is recorded, not fixed: a script
with zero dialogue lines has no valid performance plan — the
performance-plan schema requires at least one line (minItems 1)
while the dialogue mapping forbids inventing one (an extra line
fails). The builder fails closed with a structured error for such
a script. See the corrections record, §5.

## What P1-003 does not do

No video generation, audio generation, lip-sync rendering,
provider execution, VoiceStudio invocation, OpenMontage
invocation, permanent character registration, permanent voice
registration, persistent project database, cloud database, API
server, web server, background worker, LLM API integration, new
authorization system, or graphical UI. The Brain creates and
validates instructions and plans — it does not become a
media-generation server. No permanent records are created in this
phase.
