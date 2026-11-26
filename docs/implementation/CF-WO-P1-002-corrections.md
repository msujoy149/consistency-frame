# CF-WO-P1-002 Corrections — Deterministic Runtime Skill Router & Workflow Plan Builder

## 1. What existed (P0 state)

P0 defined the routing model as contracts and validation only. The
composable routing helper `resolve_skills()` in `tests/test_routing.py`
was explicitly test-only: it resolved the 8 P0 composable-routing
scenarios (P0-006) from a schema-valid production profile + hints and
refused invalid/contradictory requests, but it was not a runtime
component — no production resolver, no plan builder, no session
requirement, no mode enforcement, no structured conflict diagnostics,
and no handoff packet. The canonical routing records existed as YAML
only (`architecture/SKILL_ROUTING_MATRIX.yaml` v2.4,
`architecture/WORKFLOW_GRAPH.yaml`, `architecture/intent-modes.yaml`
v2.3), readable by the validator and the tests but not by any
standard-library-only runtime (the runtime cannot depend on PyYAML).
P1-001 had delivered the trusted local session (`runtime/local_session.py`,
`runtime/authorization.py`) but no consumer of it beyond the
authorization bridge.

## 2. What was missing / the gap

- No production `resolve_skills()` — the P0 helper's logic existed
  only inside a test file, duplicated nowhere else, and would have
  diverged from any later runtime.
- No deterministic plan builder: nothing turned a resolved skill set
  into an ordered, parallelisable, session-bound workflow plan.
- No intent-mode enforcement at runtime: the 13 modes were documented
  in YAML; nothing refused a production request in UPLOAD_ONLY or
  REPORT_UPDATE_ONLY, and nothing enforced the registration modes'
  evidence requirements.
- No structured conflict diagnostics: the matrix recorded two
  blocking conflict pairs and the graph recorded TC-1..TC-10, but
  nothing produced a blocked result naming the rule, skills, shot,
  subject, and the decision required.
- No catalog: nothing compiled the canonical YAML records into a
  single stdlib-readable, fingerprint-verified, freshness-checked
  artifact.

## 3. What changed

### 3.1 New build-time compiler `scripts/generate-routing-catalog.py`

Build-time only; uses PyYAML, which is already available in this
environment and already required by `scripts/validate-repo.py`
(check 8) and `tests/test_routing.py`. The installed runtime never
imports it. It reads five canonical sources —
`architecture/SKILL_ROUTING_MATRIX.yaml`,
`architecture/WORKFLOW_GRAPH.yaml`,
`architecture/intent-modes.yaml`,
`architecture/COMPANION_CAPABILITY_REGISTRY.yaml`,
`architecture/AGENT_COMPATIBILITY_MATRIX.yaml` — plus the SHA-256
of each `skills/<slug>/SKILL.md`, and writes
`registry/routing-catalog.json` with `json.dumps(indent=2,
sort_keys=True) + "\n"` (the same pattern as
`scripts/generate-registries.py`). `--check` compares the freshly
compiled bytes with the committed file and exits 1 when stale.

The compiler enforces cross-source consistency and aborts with the
exact contradiction instead of silently reinterpreting it:

- matrix skills == graph nodes == `skills/` directories on disk;
- precedence unique 1..15;
- every matrix dependency names a known skill with earlier
  precedence;
- every matrix dependency is a graph edge (and non-dependency edges
  are router edges only);
- the graph is acyclic;
- parallel groups have no internal dependency;
- TC-1..TC-10 are exactly the graph's records, sorted numerically;
- companion pins match `setup.sh`;
- the derived vocabulary unions equal the canonical sets from the
  matrix header (`generated_media`, `generated_subjects`,
  `cinematic_styles`, `animation_styles`).

The catalog records the SHA-256 and version of every source file,
so a plan can name the exact catalog it was built from and a
handoff packet can name the exact skill text it refers to.

### 3.2 New schemas `schemas/skill-routing-request.json` + `schemas/skill-routing-plan.json`

Schema version 2.4, restricted JSON Schema subset accepted by
`scripts/validate-repo.py` (verified PASS). The request schema
mirrors the full v2.5 production profile (all fields, including
`name`, `production_profile_id`, `project_id`, `schema_version`
`["2.5"]`, `skill_profiles`, `status`, `version`, per-shot overrides
with camera fields plus the routing extensions `subjects`,
`visual_style`, `source_media`, `is_live_action_footage`), plus
`task_id` (pattern), the 13 intent modes, structured hints, an
explicit primary pathway, explicit additional layers, requested
skills each with a `source` enum, per-shot / per-subject scope
tables, dialogue / language indicators, existing-character status,
and the mode-evidence fields (`repair_authorised`,
`explicit_request`, `rights_provenance_checked`,
`dialogue_rewrite_requested`, `explicit_user_instruction`,
`registration_evidence` — whose fields match the modes' `requires`
lists exactly). The plan schema covers plan ID, catalog version +
sources (5 files with SHA-256), session (session ID only), status
`ready`/`blocked`, selected skills (skill, skill ID, path, SHA-256,
basis, scope, quality gate, approval conditions, required inputs,
expected outputs), steps, execution batches, parallel groups,
resource-management instructions, conflicts, blocked diagnostics,
constraints, the four plan-only flags, and the SHA-256 plan hash.

### 3.3 New production router `runtime/skill_router.py` (stdlib only)

API: `load_routing_catalog()`, `validate_routing_request(request,
catalog)`, `resolve_skills(request, catalog)`,
`build_workflow_plan(session, request, catalog=None)`,
`validate_routing_plan(plan, catalog)`,
`get_ready_steps(plan, completed_step_ids)`,
`build_handoff_packet(plan, step_id, catalog=None)`, `plan_hash(plan)`.
Exported from `runtime/__init__.py`.

### 3.4 Tests

- New suite `tests/test_skill_router.py` (see §5 for counts).
- `tests/test_routing.py` refactored: the test-only routing
  algorithm (helper block, vocabulary constants, `RoutingError`
  class) was removed; the file now imports the production resolver
  and runs all 8 P0 scenarios + the refusal cases through it with
  exact intended outcomes. Scenario 7 and the reference-video
  fixture cases run in REMAKE_OR_TRANSFORM mode with the mode's
  required evidence, because `video-regeneration` is not applicable
  in GENERATE_FROM_SCRIPT.
- `tests/run-tests.sh`: `generate-routing-catalog.py --check`
  (CF-P1-002-CATALOG) and the seven `test_skill_router.py` runs
  (CF-P1-002-CATALOG / -SCHEMA / -ROUTING / -CONFLICTS / -MODES /
  -PLAN / -SECURITY).

### 3.5 Documentation

- `docs/runtime/SKILL_ROUTING_RUNTIME.md` — the runtime contract.
- `AGENTS.md` — P1-002 section.
- `CHANGELOG.md` — [Unreleased] entry.
- This corrections record.

### 3.6 CI

- `.github/workflows/p0-ci.yml` (p0-validate job): new step "Check
  routing catalog is fresh" running
  `python3 scripts/generate-routing-catalog.py --check`, before the
  test suite. **Flag: the workflow file cannot be pushed via the
  GitHub API (403, established in P1-001-R2), so the parent uploads
  this file via the GitHub website.**
- Windows CI decision: no new Windows job. The router introduces no
  platform-sensitive filesystem or multiprocessing code (pure
  stdlib, no `os.fchmod`, no multiprocessing, no platform branches;
  paths are `__file__`-relative). The existing `windows-compat`
  job runs the three P1-001 suite files only — it does NOT run
  `tests/test_skill_router.py`. Recommended exact change, for the
  reviewer to approve: add one step to `windows-compat` after the
  private voice security suite step:

  ```yaml
        - name: Run skill router suite
          shell: bash
          run: python tests/test_skill_router.py
  ```

### 3.7 What did NOT change

- No P0 authorization policy change: `scripts/asset_policy.py`
  untouched (the router never calls it; the only `open(` in the
  router reads the catalog JSON).
- No P1-001 session change: `runtime/local_session.py` and
  `runtime/authorization.py` untouched; the router consumes
  `is_active_session` exactly as designed.
- No VoiceStudio / OpenMontage change.
- No change to the canonical YAML routing records, the 15 skills,
  or the matrix/graph/mode versions (catalog version 2.4).
- No provider, companion, media-generation, persistence, server,
  API, cloud-database, LLM-classifier, or script-to-performance
  code anywhere in the new files.

## 4. Findings (canonical-data issues found while building)

### 4.1 `resource-management` has no `routing_dimensions` in the matrix

The cross-cutting skill states no routing dimensions. This is a
documented absence, not a contradiction: the skill is consulted at
every phase boundary and is never a pipeline stage, so it has no
dimensions to route on. The compiler treats a missing
`routing_dimensions` as "no dimensions stated" (documented in the
compiler and in `docs/runtime/SKILL_ROUTING_RUNTIME.md`). No matrix
change was made.

### 4.2 Lexicographic sort put TC-10 before TC-2

The TC records' string sort placed `TC-10` before `TC-2`. The
compiler and the catalog sort TC records numerically (TC-1..TC-10).
Additive correction only; no source data changed.

### 4.3 Matrix text fields are not uniform

`required_inputs` / `expected_outputs` contain a mix of strings and
single-key dicts (`{label: detail}`), and `approval_conditions` is a
single string in all 15 entries. The router normalises these to
uniform string lists (`"label: detail"`) in plans so the plan
schema validates. The catalog keeps the verbatim matrix values.
This normalisation also fixed a real bug found during testing:
`list()` on the approval string would have split it into
characters in step records.

### 4.4 `get_ready_steps` must be batch-aware

The first implementation returned later-batch steps as ready at
start (their dependencies were satisfied but earlier batches were
incomplete). Fixed: a step is ready only when every dependency is
complete, the step itself is not complete, and every step in every
earlier execution batch is complete. Regression test added.

### 4.5 `parallel_groups` must list only co-located groups

The first implementation listed a parallel group as active even
when its members landed in different batches. Fixed: the plan lists
only groups whose members actually share one batch. Regression
test added.

## 5. Tests executed — exact counts

Final full-suite run (2026-11-25, after all code and docs were
final, before the provenance regeneration): `bash tests/run-tests.sh`
— **status PASS, 64 entries / 50 distinct IDs / 36 distinct
commands, 0 failures** (before P1-002: 56 entries / 43 IDs / 34
commands; the +8 entries are the catalog `--check` and the seven
`test_skill_router.py` runs). Individual suites, counted from their
own output (each run twice where the count was compared with the
P1-001 record):

- `tests/test_skill_router.py` — **166 checks, 0 failures** (new
  suite: catalog 19, schema 18, routing 31, conflicts 24, modes 24,
  plan 38, security 12).
- `tests/test_routing.py` — **305 checks, 0 failures** (all 8 P0
  scenarios + refusal cases, now through the production resolver).
- `tests/test_local_session_runtime.py` — **67 checks, 0 failures**
  (the P1-001 record says 65: the difference is the two POSIX-only
  checks, which run on Linux and are skipped on Windows — the file
  is untouched in this round and the count is stable across runs).
- `tests/test_session_authorization.py` — **47 checks, 0 failures**.
- `tests/test_private_voice_security.py` — **158 checks, 0 failures**
  (unmodified P0 suite).
- `scripts/validate-repo.py` — **PASS** (all 8 checks).
- `scripts/generate-registries.py --check` — **CHECK OK**.
- `scripts/generate-routing-catalog.py --check` — **CHECK OK**.
- `scripts/generate-report.py --check --github-head
  b2db48828b3e964eebca3fe585bff84bafb00dae` — **CHECK OK** (living
  report matches canonical records).
- `tests/test_reports.py` — **PASS** (0 failures).
- `git diff --check` — **clean**.

## 6. Files changed

20 files (12 modified, 8 new) — full `git diff --stat` against
`bfe60e5` is recorded in the delivery report. New: `runtime/skill_router.py`,
`scripts/generate-routing-catalog.py`, `registry/routing-catalog.json`,
`schemas/skill-routing-request.json`, `schemas/skill-routing-plan.json`,
`tests/test_skill_router.py`, `docs/runtime/SKILL_ROUTING_RUNTIME.md`,
`docs/implementation/CF-WO-P1-002-corrections.md`. Modified:
`runtime/__init__.py`, `tests/test_routing.py`, `tests/run-tests.sh`,
`tests/last-run.json`, `.github/workflows/p0-ci.yml`, `AGENTS.md`,
`CHANGELOG.md`, `docs/architecture/living-architecture-report-v2.4-p0.md`,
`docs/implementation/BUILD_REPORT_P0.md`,
`docs/implementation/build-report.json`,
`docs/implementation/CHECKSUMS.txt`, `release-manifest.json`.

## 7. Provenance

Provenance was regenerated after the final suite run, in order:
full suite → `scripts/generate-report.py` →
`scripts/generate-build-report.py` LAST, both with
`--github-head b2db48828b3e964eebca3fe585bff84bafb00dae` (the P1-001
base head; the parent re-regenerates after the push).

The manifest generator lists files from `git diff --name-only
<base>...HEAD`, so untracked files cannot appear in it. The
manifest was therefore regenerated AFTER the single P1-002 commit
and folded into the same commit with `--amend` (provenance-only
amend, no code change). The manifest's `commit` field consequently
names the pre-amend content head, and the final head is the amended
commit — the same pattern as the P1-001 F2-R2 round, where the
manifest named the content commit and the docs commit was
provenance-only. The manifest file count is **177** (169 at F2-R2 +
8 new files), verified entry-by-entry against the live tree: every
entry exists, every SHA-256 matches, no entry missing. CHECKSUMS.txt
verified manually (SHA-256 + byte counts recomputed, `#` comment
lines skipped): **3/3 OK**. The full SHA list (manifest,
build-report.json, BUILD_REPORT_P0.md, this document, CHECKSUMS.txt,
living-architecture report) is recorded in the delivery report, not
here — this document cannot quote the manifest SHA of the
generation that includes this document's own final text (manifest
hash-chain rule).

## 8. Remaining limitations + unresolved decisions

- The router plans only. There is no executor: no step runs a skill,
  no handoff packet is delivered to a skill, and no completed
  receipt is produced by any runtime component — the caller drives
  execution and reports receipts back to `get_ready_steps`.
- `PROJECT_CONSISTENCY` reuse-by-stable-ID is recorded as a plan
  constraint only; the router never reads private project records,
  so it cannot verify that a referenced ID exists.
- The living-architecture report
  (`docs/architecture/living-architecture-report-v2.4-p0.md`) was
  not hand-edited: it is generated from canonical records by
  `scripts/generate-report.py`, and the provenance regeneration
  picks up the new files. Its manifest section therefore reflects
  the new files only after regeneration.
- The Windows CI recommendation (§3.6) is not yet applied — it
  awaits reviewer approval, and the workflow file itself is
  uploaded via the website (see §3.6 flag).
- No end-to-end execution test exists (a plan driving real skill
  execution) — that belongs to the script-to-performance runtime,
  which is out of scope for P1-002.

## 9. ADRs (decisions taken this round)

- **ADR-P1-002-1 — Dependencies order, they never expand the
  selection.** The 8 P0 scenarios are decisive: s4 (human + talking
  bird) must not gain extra skills, s6 (real-animal footage) must
  select only `live-action-vfx` beyond the base, and s8
  (photorealistic explainer) must not gain `language-authenticity`
  or `explainer-animation`. `humanized-production` depends on
  `voice-consistency`, so transitive expansion would wrongly add
  `voice-consistency` + `character-consistency` to every production.
  Plan step dependencies = matrix dependencies ∩ selected skills.
- **ADR-P1-002-2 — Non-applicable dependencies are constraints, not
  silence.** A dependency that is not selected and does not list the
  mode is recorded in the plan as resolved per the mode's
  documented scope — never silently dropped, never invented.
- **ADR-P1-002-3 — Mode compatibility is enforced in the resolver,
  with a suggested mode.** A skill that does not list the request's
  mode raises `RoutingError` naming the skill, the mode, and a
  suggested mode. This is why s7 runs in REMAKE_OR_TRANSFORM.
- **ADR-P1-002-4 — Conflicts are claims over (subject, shot) pairs.**
  Per-skill claim sets (`None` = wildcard); a conflict fires only
  on intersecting claims in the rule's scope. A production-wide
  claim never locks a shot for TC-3 / TC-5. Blocked diagnostics are
  structured dicts returned by the resolver (not raised) so the
  planner can build a blocked plan keeping both skills.
- **ADR-P1-002-5 — TC-10 fails closed.** Articulation is validated
  against anatomy per subject per dialogue line; when the anatomy
  cannot be established from the supplied structured information,
  the router refuses and requests resolution instead of guessing.
  An explicitly non-anatomical `other` articulation is allowed.
- **ADR-P1-002-6 — Blocked plans, not exceptions, for request
  problems.** Every request-side problem (invalid request, mode
  incompatibility, missing evidence, true conflict) produces a
  blocked plan with structured diagnostics. Only a missing /
  forged / expired / copied / closed session raises, and then no
  plan is built at all.
- **ADR-P1-002-7 — The compiler is build-time only and uses PyYAML;
  the runtime stays stdlib-only.** PyYAML was already available
  and already required by the validator and the routing tests, so
  no minimal YAML reader was written. The catalog is JSON, and the
  runtime reads it with `json` only.
- **ADR-P1-002-8 — Registration default chains are injected by the
  resolver.** `REGISTER_CHARACTER` → `character-consistency`,
  `REGISTER_VOICE_PROFILE` → `voice-consistency`,
  `REGISTER_SOUND_ASSET` → `[]` (no skill selected; the mode's
  evidence is still enforced).
- **ADR-P1-002-9 — No new Windows CI job.** The router introduces
  no platform-sensitive filesystem or multiprocessing code. The
  exact step to add `test_skill_router.py` to the existing
  `windows-compat` job is recommended in §3.6 rather than applied
  unilaterally.

## 10. Not addressed / out of scope

- Script-to-performance runtime (P1-003 territory).
- Any executor or scheduler for plans.
- Any change to the P0 policy, the P1-001 session runtime, the
  canonical routing YAML, or the 15 skills.
- Any provider, companion, or media-generation integration.
- PR creation, push, or merge (the parent handles those after this
  report).

## 11. Post-push provenance addendum (parent)

- Content push: 19 files (all round files except
  `.github/workflows/p0-ci.yml`) pushed via the API to
  `feat/cf-p1-002-skill-routing-runtime`, GitHub head
  `997fd119bb6349bbab67860ca19b5687b4c95ccd`.
- The workflow file cannot be pushed via the API (403, established
  in P1-001-R2), so `.github/workflows/p0-ci.yml` was edited on the
  GitHub website: the "Check routing catalog is fresh" step, commit
  `14eb178c8586b58f5ca52114d950022098c151b1`. The remote file was
  verified byte-identical to the local file after the edit.
- Provenance was regenerated with `--github-head 14eb178…` after
  the workflow commit. The pre-push provenance recorded in §7
  (manifest generated against content head `0802045`, source
  snapshot `b2db4882`) is superseded by that regeneration, not
  rewritten. The tested implementation head remains the local
  content commit; the workflow commit changes no runtime, test, or
  policy file. The regenerated manifest and CHECKSUMS values live in
  the delivery report, not here (hash-chain rule §7).

## 12. CF-WO-P1-002-R1 — Referential Scope Integrity, Typed Evidence, Safe Handoffs & Catalog Integrity (2026-11-26)

Independent-review follow-up to P1-002. Four independently
reproduced defects, fixed without redesigning the router and
without changing the P1-001 session runtime. Same branch
(`feat/cf-p1-002-skill-routing-runtime`), same PR (#3, Draft,
unmerged). No canonical YAML or skill was rewritten; no protected
file was touched (`scripts/asset_policy.py`,
`scripts/timeline_policy.py`, `scripts/atomic_write.py`,
`runtime/local_session.py`, `runtime/authorization.py`,
VoiceStudio, OpenMontage — all 0 lines changed).

### 12.1 Reproductions (all four defects confirmed on pre-fix code)

The reproductions were run against the P1-002 tree (`f18de74`,
extracted with `git archive` into an isolated directory) and
again against the fixed code:

- **Task A — phantom scope resolves.** On pre-fix code a
  `requested_skills` scope naming `ghost-subject-999` passed
  `validate_routing_request()` with zero errors and resolved
  (TC-8 silently fired on nothing). On fixed code the same request
  fails validation with
  `requested_skills[0].scope.subjects entry 'ghost-subject-999'
  does not resolve to a request or profile subject`, and
  `resolve_skills()` raises.
- **Task B — string "false" authorises registration.** On pre-fix
  code `{"explicit_authorisation": "false"}` passed validation and
  `build_workflow_plan()` built a **ready** `REGISTER_CHARACTER`
  plan. On fixed code validation rejects it as a type error and
  the plan is blocked.
- **Task C — handoff labels dependencies satisfied with no
  receipts.** On pre-fix code `build_handoff_packet(plan,
  "voice-consistency")` returned
  `satisfied_dependencies: ["character-consistency"]` with zero
  completion evidence. On fixed code the same handoff (zero
  receipts) raises `RoutingError: step 'voice-consistency' is not
  ready for handoff: its dependencies are not complete:
  ['character-consistency']`.
- **Task D — altered catalog loads.** On pre-fix code a catalog
  with TC-8 deleted loaded successfully. On fixed code it is
  refused at load (integrity fingerprint mismatch).

### 12.2 What changed

**Task A — referential scope integrity
(`runtime/skill_router.py`).** New `_validate_referential_integrity()`,
called at the end of `validate_routing_request()`. Canonical
request-local reference sets are the union of the profile's
`per_subject_overrides` character IDs and `per_shot_overrides`
shot IDs with the request's own subject and shot tables. Checked:
every skill-scope subjects/shots entry; every subject's shot
references; every shot's `subject_ids`; every dialogue line's
`subject_id` and `shot_id`; every per-shot override's `subjects`
list. Duplicate IDs inside the profile override tables are
rejected as ambiguous (the request tables were already
duplicate-checked; a profile override and a request-table entry
sharing one ID is the documented merge). An invalid reference is a
validation error — the scope is never silently removed and the
request never produces a ready plan.

- **ADR-P1-002-R1-1 — TC tests now declare the shots they scope
  to.** The pre-existing TC-2/TC-4/TC-6/TC-10 and plan-tc2 tests
  scoped skills and dialogue lines to `shot-01`/`shot-02` without
  declaring those shots anywhere. Under Task A those scopes are
  invalid, so the tests now declare them in the request's shots
  table (`shots=[{"shot_id": "shot-01"}]`, both shots for the
  TC-2 cross-shot case). This is a test correction to the new
  rule, not a weakening: the conflict behaviour asserted is
  unchanged, and the R1-SCOPE section adds the phantom-reference
  negatives for the same rules.

**Task B — strict runtime/schema parity and boolean authorisation
evidence (`runtime/skill_router.py`).** One validation path, still
stdlib-only, still no `jsonschema` or PyYAML at runtime:

- New `_validate_registration_evidence()`: shape and type checks
  for `registration_evidence` — unknown fields rejected
  (`additionalProperties: false`), boolean fields must be actual
  bools, string fields must be non-empty strings. A string such as
  `"false"` is a type error here, so it can never reach the policy
  check where Python truthiness would treat it as approval.
- Required profile fields are now strict: `schema_version` must be
  exactly `"2.5"` (the old code let `None` through);
  `production_profile_id` must match the ID pattern (and `None` is
  an error); `version` must be an integer `>= 1` (a boolean is not
  an integer; `None` and strings are errors); `status` must be one
  of its enum; `is_live_action_footage` must be a boolean when
  present (missing is already the missing-required-field error);
  the dimension fields must be strings in the fixed vocabulary.
  `per_subject_overrides[].character_id` must match the ID pattern
  (the schema requires it); `species` must be a string.
- `additionalProperties: false` is now enforced inside items too:
  unknown fields in `requested_skills`, `subjects`, `shots` and
  `dialogue_lines` items; `dialogue_lines[].shot_id` must be a
  string; `shots[].subject_ids` must be a list of IDs;
  `subjects[].species` must be a string.
- Membership tests that could raise `TypeError` on unhashable
  input (a list where a string is expected) are now type-guarded,
  so `validate_routing_request()` never raises for a bad request —
  it returns errors.
- Policy points hardened to `value is True`: the
  `realistic-person` consent gate in `resolve_skills()` and the
  registration-evidence satisfaction check in
  `build_workflow_plan()` (new `_registration_field_satisfied()`:
  boolean fields need `is True`, string fields need a non-empty
  string). A well-formed `False` is a denial, not a type error: it
  validates and then fails the policy check. The other mode gates
  (`explicit_user_instruction`, `explicit_request`,
  `rights_provenance_checked`, `repair_authorised`,
  `dialogue_rewrite_requested`) already used `is True` and are
  unchanged. Registration and permanent-mutation modes stay
  plan-only; a valid plan never means registration was authorised
  or executed.

**Task C — dependency-safe handoff packets
(`runtime/skill_router.py`).** `build_handoff_packet()` changes
signature to `build_handoff_packet(session, plan, step_id,
completed_receipts=None, catalog=None)` (the old
`build_handoff_packet(plan, step_id, catalog=None)` form is gone;
its two call sites in `tests/test_skill_router.py` are updated).
Validation order: the exact active session first (P1-001 verifier
— a missing, forged, expired, copied or closed session raises and
nothing is built), then the plan structure and its deterministic
hash (`validate_routing_plan()` — a plan modified after hashing is
refused), then the plan/session binding (the plan's session ID must
equal the session's), then every receipt, then readiness. A receipt
is exactly `{"plan_id", "step_id", "status"}` — matching plan ID,
a known step ID, explicit `status == "completed"`, no duplicates,
no unknown fields, no missing fields. The requested step must be in
`get_ready_steps(plan, completed_step_ids)` or the packet is
refused (the error names the incomplete dependencies or the
incomplete earlier batch). `satisfied_dependencies` is populated
only from the validated receipts; the packet also carries
`plan_id`, `session_id` and `completed_step_ids` (precedence
order). Receipts are reported completion state, not cryptographic
proof that an external agent executed the work; no execution
engine, worker or scheduler was added.

- **ADR-P1-002-R1-2 — receipts are the only satisfaction source,
  the declared list stays descriptive.** `dependency_steps` still
  carries the plan's declared dependencies (it describes the plan
  structure); `satisfied_dependencies` carries only the receipted
  subset. For a ready step the two coincide, because readiness
  requires every dependency to be complete — but the code path
  that fills `satisfied_dependencies` reads only the receipts.

**Task D — compiled catalog integrity
(`runtime/skill_router.py`, `scripts/generate-routing-catalog.py`,
`tests/test_skill_router.py`,
`docs/runtime/SKILL_ROUTING_RUNTIME.md`).**

- The compiler now stamps `integrity: {algorithm:
  "sha256-canonical-json-v1", fingerprint}` on the catalog — the
  SHA-256 of the canonical JSON of the catalog without the
  integrity record itself. The runtime exposes the same
  computation as `catalog_fingerprint()` and the loader refuses
  any catalog whose stored fingerprint differs (missing record,
  wrong algorithm, or non-digest value are refused too). The
  fingerprint is recomputed deterministically on every build, so
  the update procedure is a rebuild, never a hand edit (documented
  in `docs/runtime/SKILL_ROUTING_RUNTIME.md`); `--check` compares
  the full regenerated bytes, so it covers fingerprint freshness.
- The loader now validates the catalog's complete runtime-relevant
  structure (`_validate_catalog_semantics()`): sources are exactly
  the five canonical files; intent modes are exactly the 13, each
  with its record shape (`allowed` non-empty list of strings,
  `creates_permanent_record` boolean, optional `forbidden` /
  `requires` / `dialogue_mode_default`); vocabularies are
  non-empty unique string lists with the derived sets inside their
  parent vocabulary; each skill's `skill_id` is `skill-<slug>`,
  its path is `skills/<slug>/SKILL.md`, its `applicable_modes` is
  a non-empty duplicate-free list of known modes, its
  dependencies and conflicts name known distinct skills (no
  self-references), dependencies run earlier by precedence, and
  its routing dimensions stay inside the vocabularies; conflicts
  are symmetric; graph nodes carry the skill's precedence and a
  stage; every matrix dependency is a graph edge and every
  non-router graph edge is a matrix dependency, with
  command-authority edging to every other skill exactly once;
  parallel groups are exactly the four canonical names and
  conditional groups exactly `existing-character-prep`, each with
  at least two distinct known members and (for plain parallel
  groups) no internal dependency edge; true conflicts are exactly
  TC-1..TC-10 in order with known skills and non-empty rule /
  scope / resolution; sequential chains and cross-cutting records
  have their canonical shapes.
- Two findings from building the semantic checks (no canonical
  data was changed): (1) TC pairs are NOT all matrix conflicts —
  only TC-2 and TC-4 are pairwise matrix conflicts — so no
  TC↔matrix agreement is enforced; (2) one router edge
  (`command-authority -> kids-family-animation`) is also a matrix
  dependency, so the router-edge check counts the full edge set
  (14), not the non-dependency remainder (13).
- The documentation claim is narrowed: this is integrity against
  accidental / unsupported mutation and malformed catalogs, not
  cryptographic protection against a malicious process with the
  same OS-user access to the repository and the runtime source.
- The altered-catalog tests prove the semantic layer
  independently of the fingerprint: each semantic case is loaded
  twice, once as-is (fingerprint mismatch) and once with a
  correctly recomputed fingerprint (so only the semantic check can
  reject it).

**Windows CI (`.github/workflows/p0-ci.yml`).** The
`windows-compat` job now runs `tests/test_skill_router.py` as its
own step on both matrix versions (Python 3.10 and 3.12), after the
private-voice-security step; the existing three P1-001 suites are
unchanged. The header comment now says four suites. (Per the
standing rule the workflow file cannot be pushed via the API; the
parent uploads it via the browser. ADR-P1-002-9's recommended step
is now applied in this round, as the work order asked.)

**Test registration (`tests/run-tests.sh`).** Four new entries for
the new categories (`CF-P1-002-R1-SCOPE`, `CF-P1-002-R1-SCHEMA`,
`CF-P1-002-R1-HANDOFF`, `CF-P1-002-R1-CATALOG`), each running
`tests/test_skill_router.py`.

### 12.3 Tests executed — exact counts

- `tests/test_skill_router.py` — **339 checks, 0 failures** (was
  166 in P1-002; +173: the R1 sections plus the updated handoff
  assertions and the shots-table declarations in the TC tests).
- Full suite `bash tests/run-tests.sh` — counts recalculated from
  the final run (see the delivery report; the suite gained the four
  R1 entries).
- The other suites were re-run unchanged as part of the full suite
  (`test_routing`, `test_local_session_runtime`,
  `test_session_authorization`, `test_private_voice_security`).
- Parent verification correction (2026-11-26): the R1 provenance
  was first generated with `--github-head 900a7e0b` (8 characters).
  `tests/test_reports.py` requires `github_branch_head` to be a
  full 40-character SHA (CF-P0-REPORT-001/004), so the full suite
  failed on the five CF-P0-REPORT entries until the provenance was
  regenerated with the full head
  `900a7e0ba8d55106e7b9131897d3ca07bd17c981` (generate-report.py,
  then generate-build-report.py last) and the full suite re-run.
  No code or test changed in this correction — provenance only.
- The new R1 checks fail on pre-fix code: the four reproductions
  in §12.1 were demonstrated against the P1-002 tree before the
  fix, and the fixed code refuses each of them.

### 12.4 Files changed

- `runtime/skill_router.py` — Tasks A–D (referential integrity,
  schema parity / typed evidence, receipt-based handoffs, catalog
  fingerprint + semantic validation).
- `scripts/generate-routing-catalog.py` — integrity fingerprint
  computation (build-time only).
- `registry/routing-catalog.json` — regenerated (integrity record
  added; all other content identical).
- `tests/test_skill_router.py` — four new R1 regression categories
  + updated handoff calls + shots declarations in TC tests.
- `tests/run-tests.sh` — four new R1 entries.
- `.github/workflows/p0-ci.yml` — router suite step in
  `windows-compat` (browser upload by the parent; not API-pushed).
- `docs/runtime/SKILL_ROUTING_RUNTIME.md` — R1 sections
  (referential integrity, schema parity / typed evidence,
  dependency-safe handoffs, catalog integrity + update procedure +
  narrowed claim).
- `docs/implementation/CF-WO-P1-002-corrections.md` — this §12.
- `CHANGELOG.md` — R1 entry under [Unreleased].
- `AGENTS.md` — R1 note in the P1-002 section.
- Regenerated provenance (manifest, living report, build report)
  in the repo's required order; the manifest and CHECKSUMS values
  live in the delivery report, not here (hash-chain rule §7).
  Post-push regen (parent): provenance regenerated with the full
  GitHub head `60d0a941c20e736dd6f6d32f997f82f66f32c8c7` (R1-R2
  content push); the new manifest SHA is recorded in the delivery
  report, not here.

### 12.5 Remaining limitations + unresolved decisions

- Receipts are reported completion state, not proof of execution:
  a caller that lies about completion gets a packet. That is the
  documented boundary; no execution engine or verification of
  external work is in scope.
- The fingerprint proves the catalog file is the compiler's
  output, not who ran the compiler; it does not stop a malicious
  same-OS-user process.
- The Windows CI evidence for the new router step exists only
  after the PR run; Windows success is not claimed before that run.
- Script-to-performance runtime remains P1-003 territory; no
  executor or scheduler for plans was added.

## 13. CF-WO-P1-002-R1-R1 — Windows CI follow-up fix: PyYAML install + LF checkout contract (2026-11-26)

The first R1 CI run failed on Windows only. This section records
the failure, the two proven causes with their evidence, and the
two fixes. Nothing here redesigns the router or changes the P1-001
session runtime. Same branch (`feat/cf-p1-002-skill-routing-runtime`),
same PR #3 (Draft, unmerged); no merge, no P1-003.

### 13.1 The failure — PR run #237

- Run: **#237**, run ID `45788632035`,
  https://github.com/msujoy149/consistency-frame/actions/runs/45788632035
- Head: `bcd24f3305639a541dd6f0032cf6829a3e9c0084` (exact; the R1
  docs push), event pull_request (PR #3).
- Overall: **Failure**.
- `p0-validate` (Linux): **Success, 1m 21s** — "Check routing
  catalog is fresh" step CHECK OK; full suite PASS, 68 entries /
  54 IDs / 36 commands. Its `p0-test-results` artifact (ID
  `15100973200`, 1017 B, digest
  `sha256:188647a23cd022914958be8a9910965b70cff1649d007b732ea78ae2d28c1a2c`)
  holds a `last-run.json` byte-identical to the committed one
  (SHA `a24736d6…`, 68 entries, status PASS).
- `windows-compat` (Python 3.10.11): **Failure**; `windows-compat`
  (Python 3.12.10): **Failure** — both only in the new "Run skill
  router suite" step. The other three suites PASS in both jobs
  (runtime 65, authorization 47, security 158 checks; 66/48/159
  "PASS " lines including the summary line).
- Exactly **3 failures** in the router step, identical in both
  jobs (raw logs, `evidence/p1002-r1/`):
  1. `FAIL CF-P1-002-CATALOG: source SHA-256 values match the live
     YAML files` — sources are the 5 canonical YAML files.
  2. `FAIL CF-P1-002-CATALOG: skill fingerprints match the live
     SKILL.md files`.
  3. `FAIL CF-P1-002-CATALOG: generate-routing-catalog.py --check
     passes — generate-routing-catalog: PyYAML is required
     (pip install pyyaml)`.
- Per-job logs: `windows-compat-3.10-run237.log` (859 lines,
  SHA-256 `8a06c5de0f3f2b68c2d414a9940d98f889015f8af0823fc8d24c34b286f5f34c`),
  `windows-compat-3.12-run237.log` (809 lines, SHA-256
  `7069b12f2d6501553386932fc80ada9ab012299149604c59b0aff3d5303a9e53`).
  Reconstructed by concatenating the run-level archive's per-step
  files for that job in step-number order (the P1-002 run #234
  method); the archive's `system.txt` files are not part of a job
  log and were excluded. Evidence staged in
  `ci-evidence-p1-002-r1/` (artifact + README) and
  `evidence/p1002-r1/` (both Windows logs). Run #237 is recorded
  as FAILED; it is not claimed as passed anywhere.

### 13.2 Cause 1 — windows-compat has no PyYAML install step

`p0-validate` installs PyYAML before running the suite; the
`windows-compat` job never did. The router suite runs
`scripts/generate-routing-catalog.py --check`, which imports
`yaml` at module load and exits with "PyYAML is required (pip
install pyyaml)" when it is absent. That is failure 3 above.
The other three Windows suites are stdlib-only, so only the
router step tripped over it.

Fix: a pip-install-PyYAML step in the `windows-compat` job, after
"Show versions" and before the suite steps (mirroring the
`p0-validate` install step's wording and purpose), using
`python -m pip install --quiet pyyaml` — `python`, not `python3`,
is the interpreter on the Windows runner. The workflow file
cannot be pushed via API; the parent uploads it via the browser.

### 13.3 Cause 2 — Windows checkout converts LF to CRLF

The catalog records raw-byte SHA-256 values of the 5 canonical
YAML sources and the 15 `SKILL.md` files; the compiler was run on
Linux, so the recorded hashes are LF hashes. A Windows checkout
converts LF to CRLF, which changes the bytes and therefore the
hashes — failures 1 and 2 above. Proven by simulation on Linux:
for `architecture/SKILL_ROUTING_MATRIX.yaml` and a sampled
`skills/character-consistency/SKILL.md`, the LF hash matches the
catalogued value and the CRLF-converted hash does not (all 5 YAML
files and the sampled SKILL.md behave the same way).

Fix: a new `.gitattributes` file forcing `eol=lf` for every file
the catalog hashes — the 5 `architecture/*.yaml` sources,
`skills/*/SKILL.md`, and `registry/routing-catalog.json` itself.
The fix is the checkout contract, not hash normalisation: the
fingerprint semantics are unchanged, the compiler still hashes
raw bytes, and no canonical YAML or skill was rewritten. The
`.gitattributes` rule is targeted to the hashed files only.

### 13.4 Regression test

Two new checks in `tests/test_skill_router.py`
(CF-P1-002-R1-CATALOG), placed in the catalog section next to the
`--check passes` check:

- Every catalog-hashed file is covered by an `eol=lf` rule in
  `.gitattributes` — the hashed set is taken from the live
  catalog (5 sources + 15 skill paths + the catalog itself = 21
  files, count pinned), and coverage is decided by a
  segment-aware gitattributes pattern matcher (`*` within one
  segment, `**` across segments). Uncovered files are named in
  the failure detail.
- `.gitattributes` covers the catalog file itself.

Demonstrated failing on pre-fix code: with `.gitattributes`
temporarily removed, both checks fail (all 21 files uncovered)
and the suite reports 2 failures; restored, the suite passes.
`tests/test_skill_router.py` is now **341 checks, 0 failures**
(was 339; +2).

### 13.5 Tests executed — exact counts

- `tests/test_skill_router.py` — **341 checks, 0 failures**.
- Full suite `bash tests/run-tests.sh` — counts recalculated from
  the final run (see the delivery report; the suite entries are
  unchanged — no new test file was added).
- The other suites were re-run unchanged as part of the full suite
  (`test_routing`, `test_local_session_runtime`,
  `test_session_authorization`, `test_private_voice_security`).
- The new checks fail on pre-fix code (see §13.4); the Windows
  re-run after the two fixes is a separate CI event, recorded
  after the PR run — Windows success is not claimed before it.

### 13.6 Files changed

- `.gitattributes` — new; `eol=lf` on every catalog-hashed file.
- `.github/workflows/p0-ci.yml` — PyYAML install step in
  `windows-compat` (browser upload by the parent; not API-pushed).
- `tests/test_skill_router.py` — two `.gitattributes` coverage
  checks + `fnmatch` import.
- `docs/runtime/SKILL_ROUTING_RUNTIME.md` — checkout-contract
  paragraph in "The catalog".
- `docs/implementation/CF-WO-P1-002-corrections.md` — this §13.
- `CHANGELOG.md` — R1-R1 entry under [Unreleased].
- `AGENTS.md` — one-line checkout-contract note in the P1-002
  section.
- Regenerated provenance (manifest, living report, build report)
  in the repo's required order; the manifest and CHECKSUMS values
  live in the delivery report, not here (hash-chain rule §7).

### 13.7 Remaining limitations + unresolved decisions

- The `.gitattributes` contract pins line endings for the hashed
  files only. Any future file the catalog hashes must be added
  here too — the regression test fails loudly if it is not (the
  coverage check names the uncovered file).
- The fingerprint still proves the catalog file is the
  compiler's output, not who ran the compiler; it does not stop
  a malicious same-OS-user process.
- The Windows CI evidence for the two fixes exists only after
  the re-run; Windows success is not claimed before that run.
- Script-to-performance runtime remains P1-003 territory; no
  executor or scheduler for plans was added.

## 14. CF-WO-P1-002-R1-R2 — Reject explicit nulls in non-nullable optional fields (2026-11-26)

Independent schema-parity testing found 22 cases where the JSON
Schema rejects an explicit `null` but `validate_routing_request()`
accepted it as if the field were absent. This section records the
reproduction, the fix and the regression group. Nothing here
redesigns the router, changes intent-mode permission or selection
logic, or changes the P1-001 session runtime. Same branch
(`feat/cf-p1-002-skill-routing-runtime`), same PR #3 (Draft,
unmerged); no merge, no P1-003.

### 14.1 The gap — 22 cases, all reproduced pre-fix

Every case was reproduced on pre-fix code with a probe that built
a valid schema-conforming request, set the optional property to
explicit `None`, and asked both validators: the restricted schema
validator (`scripts/validate-repo.py:validate_instance`) rejected
all 22; the production runtime validator accepted all 22. The
pattern was the same in each place: `request.get(key) or []` /
`or {}` defaults and `if value is not None` guards treated an
explicit `None` exactly like an omitted key.

- **Task A — request level (10):** `additional_layers`,
  `dialogue_lines`, `hints`, `primary_pathway`,
  `production_profile` (in a mode where the profile is otherwise
  optional), `registration_evidence`, `requested_skills`,
  `subjects`, `shots`, `requested_skills[i].scope`.
- **Task B — production profile (5):** `name`,
  `per_shot_overrides`, `per_subject_overrides`, `project_id`,
  `skill_profiles`.
- **Task C — registration evidence (7):** `character_link`,
  `licence_or_permission`, `name`, `owner`, `project_scope`,
  `source`, `unique_id`.

### 14.2 The fix — key-presence checks, no architecture change

All fixes are in `runtime/skill_router.py`, in the two existing
validators, and follow one rule: **presence decides, not
truthiness.** A key that is present with `None` is a type error
naming the field; a key that is absent stays valid wherever the
schema permits omission.

- `validate_routing_request()`: `production_profile` — an
  explicit null now reports "must be an object, got None" in
  every mode, while a missing profile in a production mode still
  reports the existing "is required in {mode} mode" error (the
  two cases are now distinct branches). `hints`,
  `additional_layers`, `requested_skills`, `subjects`, `shots`,
  `dialogue_lines` — the `or []` / `or {}` defaults are replaced
  by a presence check that reports "must be a list/object, got
  None" and then validates the value normally. `primary_pathway`
  — explicit null reports "must be a skill slug, got None".
  `requested_skills[i].scope` — explicit null reports "must be
  an object, got None". `registration_evidence` — the key's
  presence now decides whether the shape validator runs, and
  that validator already reports a non-object (including `None`)
  as "is not an object".
- `_validate_profile_fields()`: `name`, `project_id`,
  `skill_profiles`, `per_shot_overrides`,
  `per_subject_overrides` — explicit nulls are now rejected with
  a field-naming error, mirroring the existing
  `production_profile_id` null check. All existing type, enum,
  pattern, minItems and additionalProperties checks are
  untouched; omission of any of the five stays valid.
- `_validate_registration_evidence()`: the seven string fields
  now reject a present `None` with "must be a non-empty string,
  got None". Boolean approval validation is unchanged: only the
  actual boolean `True` is affirmative evidence; strings,
  integers and other truthy values still fail the type check.
- No change to `_validate_referential_integrity()`: it already
  guards every table read with `isinstance` and treats a null
  table as empty — the null itself is now reported by the
  structural validation that runs first. Both public entry
  points (`resolve_skills`, `build_workflow_plan`) validate
  first, so a null can never reach selection or planning through
  them; the second `primary_pathway` read inside `resolve_skills`
  is downstream of validation and needed no change.

### 14.3 Regression group — CF-P1-002-R1-R2-NULL

A parameterized group in `tests/test_skill_router.py` covers all
22 cases. Each case: (1) starts from a valid schema-conforming
request/profile, (2) adds the optional property with explicit
`None`, (3) verifies the restricted schema validator rejects it,
(4) verifies production `validate_routing_request()` also rejects
it, (5) verifies the runtime error names the field/path, (6)
deletes the property and verifies the request is valid again
(schema AND runtime, wherever omission is permitted). The
declared list is the contract: a summary check asserts
`len(null_cases) == 22` and that the exercised labels equal the
declared labels. Demonstrated failing on purpose: with one case
(`evidence source`) removed from the declared list, the summary
check fails ("declared=21 exercised=21") and the suite reports
1 failure; restored, the suite passes. `tests/test_skill_router.py`
is now **430 checks, 0 failures** (was 341; +89 = 22 cases × 4
checks + 1 summary check). No existing positive fixture or test
was weakened; all R1 groups (SCOPE, SCHEMA, HANDOFF, CATALOG)
still pass unchanged.

### 14.4 Tests executed — exact counts

- `python3 scripts/generate-routing-catalog.py --check` — CHECK OK.
- `python3 tests/test_skill_router.py` — **430 checks, 0 failures**.
- `python3 tests/test_routing.py` — **305/0**.
- `python3 tests/test_local_session_runtime.py` — **67/0** (Linux).
- `python3 tests/test_session_authorization.py` — **47/0**.
- `python3 tests/test_private_voice_security.py` — **158/0**
  (unmodified).
- `bash tests/run-tests.sh` — **PASS, 68 entries / 54 distinct IDs /
  36 distinct commands, 0 failures** (unchanged entry counts —
  no new test file; `tests/last-run.json` byte-identical to the
  R1-R1 run, SHA `a24736d6…`, as the suite records entry-level
  results only).
- `python3 scripts/validate-repo.py` — PASS (8/8).
- `python3 scripts/generate-registries.py --check` — OK.
- `python3 scripts/generate-report.py --check` — OK (after the
  provenance regen below; the check fails right after a suite run
  because the suite rewrites the living report — known behaviour,
  same as R1/R1-R1).
- `python3 tests/test_reports.py` — PASS (0 failures).
- `git diff --check` — clean.
- The 22-case probe was re-run after the fix: schema and runtime
  both reject all 22.

### 14.5 Files changed

- `runtime/skill_router.py` — key-presence null checks in
  `validate_routing_request()`, `_validate_profile_fields()` and
  `_validate_registration_evidence()` (Tasks A–C).
- `tests/test_skill_router.py` — CF-P1-002-R1-R2-NULL regression
  group (22 cases × 4 checks + summary) + test-ID header.
- `docs/runtime/SKILL_ROUTING_RUNTIME.md` — explicit-null
  paragraph in the schema-parity section.
- `docs/implementation/CF-WO-P1-002-corrections.md` — this §14.
- `CHANGELOG.md` — R1-R2 entry under [Unreleased].
- `AGENTS.md` — one-line nullability note in the P1-002 section.
- Regenerated provenance (manifest, living report, build report)
  in the repo's required order; the manifest and CHECKSUMS values
  live in the delivery report, not here (hash-chain rule §7).

### 14.6 Remaining limitations + unresolved decisions

- The fix covers the 22 declared cases — the optional fields
  named in the work order. Other optional fields with the same
  `or []` / `or {}` shape (for example `motion_methods` and
  `subject_types` inside a profile, or `hints.languages`) are
  required fields or already reject `None` through their existing
  checks; they were not in scope and were not changed.
- A receipt is still reported completion state, not proof of
  external work (R1 §12 boundary, unchanged).
- Script-to-performance runtime remains P1-003 territory; no
  executor or scheduler for plans was added.
