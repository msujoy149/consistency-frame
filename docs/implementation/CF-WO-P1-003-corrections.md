# CF-WO-P1-003 Corrections — Script-to-Performance Intelligence Runtime (Scene, Shot & Performance Plan Builder)

## 1. What existed (P1-002 state)

P0 defined the Script-to-Performance contracts as schemas and
validation only: `schemas/script-contract.json` (v2.3),
`schemas/script-to-performance.json` (v2.4/2.5),
`schemas/scene-plan.json`, `schemas/shot-plan.json`,
`schemas/performance-plan.json` (v2.4/2.5) and
`schemas/production-profile.json` (v2.5), with the structural and
semantic rules enforced by `scripts/validate-repo.py`
(`validate_instance`, `validate_dialogue_rewrite`,
`validate_non_verbal_lines`) and pinned by `tests/test_schemas.py`
and `tests/test_performance_semantics.py` (CF-P0-PERF-001..005).
The Brain Amendment v2.4 (AGENTS.md) named Script-to-Performance
Intelligence as a P1 runtime — a script analysed at
scene/beat/dialogue-line level into machine-readable Scene, Shot
and Performance Plans — but no runtime component existed that
could build or validate those plans. P1-001 had delivered the
trusted local session (`runtime/local_session.py`,
`runtime/authorization.py`) and P1-002 the deterministic skill
router and workflow plan builder (`runtime/skill_router.py`, 766
router checks after R1-R3; full suite 68/54/36 PASS; CI run #244
SUCCESS on head `b9072f07`), but nothing consumed a routing plan
to produce a production bundle.

## 2. What was missing / the gap

- No production Script-to-Performance runtime: nothing validated
  a ScriptContract + production profile + analysis drafts into
  final Scene, Shot and Performance Plans, and nothing bound them
  to a session and a routing plan.
- No verbatim dialogue guarantee at runtime: the P0 rewrite rules
  existed as validators, but no builder enforced the exact 1:1
  dialogue mapping, the five-condition rewrite authorisation, or
  the byte-for-byte preservation of the user's original lines.
- No cross-plan integrity at runtime: nothing checked that the
  four records (Script-to-Performance, Scene, Shot, Performance)
  form one coherent timeline — root IDs, project agreement,
  scene/beat/shot resolution, character resolution, voice-binding
  and reaction-hold references, or contradictory subject
  dimensions across plans.
- No deterministic bundle: nothing assembled the validated inputs
  into a single hash-fingerprinted, tamper-evident output with a
  self-check before return.
- No nullability parity for the six consumed schemas: the P1-002
  R1-R3 matrix covered only the routing-request schema; the
  script, profile and plan schemas had no equivalent regression
  protection.

## 3. What changed

### 3.1 New production runtime `runtime/script_to_performance.py` (stdlib only)

Public API: `build_script_to_performance_bundle(session,
routing_plan, script, profile, draft, bundle_id,
dialogue_rewrite_authorised=False)`,
`validate_script_contract()`, `validate_production_profile()`,
`validate_scene_plan()`, `validate_shot_plan()`,
`validate_performance_plan()`, `validate_script_plan_drafts()`,
`validate_script_to_performance_bundle()`,
`script_to_performance_hash()`, `ScriptToPerformanceError`.
Exported from `runtime/__init__.py`.

The builder runs in stages and raises `ScriptToPerformanceError`
at the first failing stage — no partial bundle is ever returned:

- **Stage A — session, bundle ID, rewrite flag, routing plan.**
  Exact active `LocalSession` via the P1-001 verifier; bundle ID
  pattern; the rewrite flag must be an actual boolean; the routing
  plan is verified with the existing P1-002
  `validate_routing_plan` against the compiled catalog (a plan so
  malformed the router validator cannot run is rejected with a
  structured error rather than leaking the validator's exception);
  the plan must be `ready`, its `intent_mode` must be
  `GENERATE_FROM_SCRIPT`, and its session ID must match the exact
  active session. The router's selected skills and decisions are
  preserved (the bundle records only the routing plan ID); no
  additional skills are selected or invented.
- **Stage B — deep copies; script + profile validation.** Inputs
  are deep-copied and never modified in place; the script and the
  profile are validated (schema + P0 semantic rules + the P1-002
  profile field rules).
- **Stage C — draft validation.** The three plans, the optional
  audio/editing/binding fields (validated against the
  corresponding subschemas of the canonical Script-to-Performance
  schema), and the cross-references among the drafts, including
  the dialogue mapping against the script.
- **Stage D — binding-record assembly.** The final
  Script-to-Performance record is assembled from the agreed
  cross-plan values (schema version, dialogue mode, project ID)
  and the draft's optional fields, then schema-validated.
- **Stage E — full cross-reference validation with the binding
  record** (root IDs, rewrite authorisation, bindings, holds).
- **Stage F — bundle assembly and self-check.** The bundle
  carries the final binding record, the three final plans, the
  validated script and profile, the routing plan ID, the exact
  active session ID and the SHA-256 bundle hash; it is validated
  with `validate_script_to_performance_bundle()` (including the
  hash recomputation) before it is returned.

### 3.2 Dialogue preservation (critical acceptance requirement)

Default `dialogue_mode = VERBATIM_SCRIPT`. Every source dialogue
line maps to exactly one Performance Plan line, by `line_id`, in
order; the text survives byte-for-byte (code-point-for-code-point).
Missing, extra, duplicate or reordered lines, changed text, and
character-ID mismatches where the source supplies one all fail.
A rewrite is valid only when all five hold: (1) the caller
supplies an actual boolean `True` for
`dialogue_rewrite_authorised`, (2) the plan uses
`SCRIPT_EDIT_REQUESTED`, (3) the exact line has
`rewrite_permitted: true`, (4) the original text stays in
`dialogue.text`, (5) the changed version lives only in
`rewritten_text`. A plan-level request alone never authorises a
rewrite; omission means false.

### 3.3 Cross-plan integrity

Root IDs match the actual plan IDs and the bundle ID; project IDs
agree wherever supplied; schema versions agree across the three
plans; `dialogue_mode` agrees between script and performance
plan. Scene/beat/shot/line IDs are unique; every shot's
`scene_id` and supplied `beat_id` resolve; source shot IDs are
never silently omitted. Character references resolve into the
known set (script dialogue speakers, profile per-subject
overrides, scene-plan cast). Voice bindings reference valid
dialogue line IDs (in either ID namespace — the script's
`line_id` or the performance line's `dialogue_line_id`), valid
shot IDs when present, and the correct character for the line;
singular + plural forms are ambiguous only when two bindings for
one line differ on any field. Reaction holds reference valid
dialogue line IDs. Contradictory subject dimensions across scene,
shot and profile records are detected
(`subject_kind`, `representation`, `rendering_style`,
`source_media`, `articulation_target`, `is_live_action_footage`,
`species`, plus `motion_method` agreement and profile-list
membership). Human mouth/lip articulation is never applied to an
animal or creature (P0 articulation map + bird-species rule);
when the kind cannot be established, the check fails closed in
the cross-reference phase only, after kinds are resolved from all
sources.

### 3.4 Determinism and hashing

Canonical JSON serialisation (sorted keys, compact separators,
Unicode unescaped) + SHA-256, the same pattern as the router's
`plan_hash`. The hash covers the bundle minus `bundle_hash`
itself, lives only on the bundle (no canonical schema provides a
field for it), and is recomputed by the bundle validator, so any
tampering fails validation. No timestamps, no random identifiers,
no silent field removal, no input mutation, no nondeterministic
sorting of dialogue/scenes/beats/shots.

### 3.5 Tests

New suite `tests/test_script_to_performance_runtime.py` (see §5
for counts), registered in `tests/run-tests.sh` as one entry per
group ID (the P1-002 pattern): `CF-P1-003-SESSION-ROUTING`,
`CF-P1-003-SCRIPT`, `CF-P1-003-PLANS`, `CF-P1-003-DIALOGUE`,
`CF-P1-003-XREF`, `CF-P1-003-DETERMINISM`, `CF-P1-003-NULL156`.
A new `windows-compat` CI step runs the suite natively on both
matrix versions (`.github/workflows/p0-ci.yml` — this file cannot
be pushed via the GitHub API; the parent uploads it via the
GitHub website; no CI coverage is claimed until the actual
workflow file and exact run prove it).

## 4. Design decisions and interpretations

Recorded here because they are judgements the work order left
open; each is pinned by a test.

- **Two layers kept separate.** Layer A (AI reasoning/script
  analysis) is not implemented; Layer B (this deterministic
  runtime) validates, binds and assembles. No LLM API, no provider
  client, no heuristics pretending to understand natural language.
- **The bundle carries the validated script and profile.** The
  work order's minimum bundle list did not name them, but they are
  needed so the hash is recomputable from the bundle alone and
  covers the full validated input.
- **Dialogue mapping by `line_id`, order preserved.** Language
  agreement is not enforced (not in the work order's §6 list).
- **Character resolution.** Scene-plan character IDs/subjects are
  definitions that establish context; shot, performance-line and
  binding character references must resolve into the known set
  (script dialogue speakers ∪ profile overrides ∪ scene cast).
- **Voice-binding ID namespaces.** `dialogue_line_id` must be in
  `{line_id} ∪ {dialogue_line_id}` — both namespaces occur in the
  P0 fixtures.
- **Fail-closed articulation, cross-reference phase only.**
  Single-record validators do not fail closed on an
  unestablishable kind, because another record may supply it; the
  cross-reference phase resolves kinds first and then fails
  closed. This mirrors router TC-10's posture.
- **Source shots are never silently omitted.** Every
  `script.shots[].shot_id` must appear in the shot plan.
- **Per-path baseline variants in the nullability matrix.** The
  standard baseline is the full valid record. The dialogue object
  and its text need two baselines: "present" and "null" use the
  standard spoken baseline, "omitted" uses the non-verbal baseline
  (source text `""`, performance `dialogue.text` omitted,
  non-verbal events present). `rewritten_text` uses the
  rewrite-authorised baseline for all three checks.
- **Malformed routing plans fail closed structurally.** A plan so
  malformed that `validate_routing_plan` raises is rejected with a
  structured `ScriptToPerformanceError`, not a leaked
  `AttributeError`. (Observed in testing: a plan whose
  `selected_skills` is a list of strings crashes the P1-002
  validator; the router itself is untouched per scope — the
  builder defends at its own boundary.)

## 5. Schema contradictions and limitations found (documented, not redesigned)

No P0 schema was changed. Two findings are recorded here:

1. **Empty-dialogue scripts have no valid performance plan.**
   The script-contract schema permits empty dialogue (no
   minItems), but the performance-plan schema requires at least
   one line (minItems 1), while the dialogue mapping forbids
   inventing one (an extra line fails). A zero-dialogue script
   therefore cannot produce a bundle: 0 lines fails the schema,
   ≥1 line fails the mapping. The builder fails closed with a
   structured error rather than fabricating a performance line.
   Pinned by `CF-P1-003-SCRIPT` (empty dialogue validates as a
   script; both build attempts fail closed).
2. **Non-verbal performance lines omit `dialogue.text`.**
   The performance-plan schema gives `dialogue.text` minLength 1,
   so an explicit `""` is schema-invalid; the correct
   representation is to omit the text key (the P0 bird-fixture
   pattern). The runtime treats a missing or empty text as
   non-verbal for the semantic checks, and the schema rejects the
   empty string. Pinned by `CF-P1-003-SCRIPT` (non-verbal-only
   script builds) and `CF-P1-003-NULL156`.

Documented limitations (not machine-decidable, not pretended
otherwise): the beat-level non-verbal-event requirement (scene
beats carry no spoken-text marker; P0 PERF-004 binds
performance-plan lines only — a sad beat without non-verbal
events is valid) and whether camera movement is "motivated" by
dramatic intent (only the enum is validated; static is valid; the
runtime invents nothing).

## 6. Verification

All run on the new branch
`feat/cf-p1-003-script-to-performance-runtime`, based on the exact
accepted P1-002 head
`b9072f07910b77621e3f5bdad1fd7546f5fc09c2` (PR #3,
Open/Draft/Unmerged; base verified by the parent).

- `tests/test_script_to_performance_runtime.py` — **606 checks, 0
  failures**: SESSION-ROUTING 22, SCRIPT 18, PLANS 23, DIALOGUE
  23, XREF 35, DETERMINISM 16, NULL156 469 (156 optional paths ×
  3 checks — present valid, omitted valid, explicit null rejected
  — plus 1 coverage assertion comparing the declared matrix
  against the optional paths discovered from the six schemas).
- `tests/test_skill_router.py` — **766 checks, 0 failures**
  (unchanged — P1-002 R1-R3 preserved).
- `tests/test_routing.py` — **305 checks, 0 failures**.
- `tests/test_local_session_runtime.py` — **67 checks, 0
  failures**.
- `tests/test_session_authorization.py` — **47 checks, 0
  failures**.
- `tests/test_private_voice_security.py` — **158 checks, 0
  failures** (unmodified P0 suite).
- `scripts/generate-routing-catalog.py --check` — **CHECK OK**.
- `scripts/validate-repo.py` — **PASS** (all 8 checks).
- `scripts/generate-registries.py --check` — **CHECK OK**.
- `bash tests/run-tests.sh` — **PASS: 75 recorded entries, 61
  distinct test IDs, 37 distinct command strings, 0 failures**
  (was 68/54/36 at P1-002 R1-R3; +7 entries / +7 IDs / +1 command
  — one entry per new group ID, the P1-002 pattern).
- `git diff --check` — **clean**.
- `tests/test_reports.py` — **PASS** (0 failures).
- `scripts/generate-report.py --check --github-head
  b9072f07910b77621e3f5bdad1fd7546f5fc09c2` — **CHECK OK** (living
  report matches canonical records).

## 7. Files changed

New: `runtime/script_to_performance.py`,
`tests/test_script_to_performance_runtime.py`,
`docs/runtime/SCRIPT_TO_PERFORMANCE_RUNTIME.md`,
`docs/implementation/CF-WO-P1-003-corrections.md`. Modified:
`runtime/__init__.py`, `tests/run-tests.sh`,
`.github/workflows/p0-ci.yml`, `AGENTS.md`, `CHANGELOG.md`,
`docs/architecture/living-architecture-report-v2.4-p0.md`,
`docs/implementation/BUILD_REPORT_P0.md`,
`docs/implementation/build-report.json`,
`docs/implementation/CHECKSUMS.txt`, `release-manifest.json`,
`tests/last-run.json`. The full `git diff --stat` against
`b9072f07` is recorded in the delivery report.

## 8. Provenance

Provenance was regenerated after the final suite run, in order:
full suite → `scripts/generate-report.py` →
`scripts/generate-build-report.py` LAST, both with
`--github-head b9072f07910b77621e3f5bdad1fd7546f5fc09c2` (the
accepted P1-002 base head; the parent re-regenerates after the
push).

The manifest generator lists files from `git diff --name-only
<base>...HEAD`, so untracked files cannot appear in it. The
manifest was therefore regenerated AFTER the single P1-003
content commit (`7dccff2`) and folded into the same commit with
`--amend` (provenance-only amend, no code change), giving content
head `3c1d5c6`. The living report was then regenerated AT the
content head `3c1d5c6` — the pre-commit generation had missed the
four new files from its inventory because they were untracked at
that point — and committed as a separate docs commit (the P1-002
pattern: "docs: provenance at GitHub head <content>"). The
manifest's `commit` field consequently names the pre-amend
content head `7dccff2`, the living report names the content head
`3c1d5c6`, and the final head is the docs commit — the same
one-commit lag as the P1-002 round, whose living report names
`e541b0e` while its head is `b9072f07`. `generate-report.py
--check` was verified CHECK OK at the content head `3c1d5c6`
(with the fresh report in the working tree, before the docs
commit); at the docs head it reports the report out of date by
exactly the head/timestamp fields, which is the expected
consequence of the lag pattern, not a defect. The manifest file
count is **182** (178 at P1-002 R1-R3 + 4 new files), verified
entry-by-entry against the live tree: every entry exists, every
SHA-256 matches, no entry missing. CHECKSUMS.txt verified manually
(SHA-256 + byte counts recomputed, `#` comment lines skipped):
**3/3 OK**. The full SHA list (manifest, build-report.json,
BUILD_REPORT_P0.md, this document, CHECKSUMS.txt,
living-architecture report) is recorded in the delivery report,
not here — this document cannot quote the manifest SHA of the
generation that includes this document's own final text (manifest
hash-chain rule).

## 9. Remaining limitations + unresolved decisions

- The runtime builds and validates plans only. There is no
  executor: no step runs a skill, no handoff packet is delivered
  to a skill, and no media is generated — the caller drives
  execution from the bundle.
- The AI reasoning layer (Layer A) is not implemented here; the
  runtime trusts the drafts it is given after validating them.
  A draft that is structurally valid but semantically wrong (a
  wrong emotion, a wrong camera choice) passes — the runtime
  guarantees contract integrity, not creative correctness.
- Character/voice registration stays out of scope: the runtime
  resolves character references against the supplied context only
  and never creates a permanent registration.
- The `windows-compat` CI step is added to the workflow file in
  this commit but cannot be pushed via the GitHub API (403 in past
  rounds) — the parent uploads the workflow file via the GitHub
  website. No Windows CI coverage is claimed until the actual
  workflow file and exact run prove it; the local suite passes on
  Linux.
- P1-004 is not started. PR #4 (targeting
  `feat/cf-p1-002-skill-routing-runtime`) is created by the parent
  after the push; it is Draft and unmerged. PR #2 and PR #3 are
  untouched.
