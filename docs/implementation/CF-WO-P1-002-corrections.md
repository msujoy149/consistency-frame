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
