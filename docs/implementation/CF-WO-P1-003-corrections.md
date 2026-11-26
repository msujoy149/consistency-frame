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

## 10. Wrong-base incident on the first push (parent repair, 2026-11-26)

- The first content push (`push_files`, 14 files, message "P1-003:
  deterministic Script-to-Performance runtime...") created the
  remote branch `feat/cf-p1-003-script-to-performance-runtime`
  from the repo DEFAULT branch instead of from the accepted
  P1-002 head: the new commit `f4adad254f970f02879a2d21b83392736acecf32`
  had parent `8fc11feec232102c2a3dfaa90c3452d2186c472e` (main), so
  the branch tree was main + the 14 pushed files only — all of
  P1-001 / P1-002 / R1 / R1-R1 / R1-R2 / R1-R3 was missing
  (18 files, +16,243/−201 vs the local head). The browser task
  uploading the workflow file caught it first: the branch's
  `.github/workflows/p0-ci.yml` was the 38-line P0 version with
  no `windows-compat` job and no router step, so appending the
  new step there would have put it in the Ubuntu `p0-validate`
  job. The parent verified the parent SHA and the tree diff
  with `git fetch` + `git log`/`git diff` (the API's
  `get_file_contents` reads right after branch creation were
  inconsistent — one read briefly reported `skill_router.py`
  missing, a later read reported it present; only the `git`
  fetch gives ground truth) and told the browser to stop
  without editing.
- Repair, in order: (1) the wrong branch was deleted via the
  GitHub website (browser, verified on the Branches page; no
  other branch touched); the deletion was confirmed with
  `git fetch --prune` (no remote p1-003 branch). (2) The branch
  was re-created with the MCP `create_branch` tool from
  `from_branch: feat/cf-p1-002-skill-routing-runtime`, landing
  at exactly `b9072f07910b77621e3f5bdad1fd7546f5fc09c2`.
  (3) The same 14 content files were re-pushed with
  `push_files` (head `749fa62077105066312bacb7e6d7bcb32bd12ee3`,
  parent verified `b9072f07`; remote tree then differed from
  the local head only in the workflow file, +8 lines).
  (4) The workflow file was uploaded via the GitHub website
  (browser, verified the 123-line file with `windows-compat`
  and the router step before editing), head
  `6547893db8a8cb34eb47fa9f47f3e41a7116699f`; the remote tree
  was then verified byte-identical to the local head
  (empty `git diff`, including modes). PR #4 was created only
  after that verification.
- Standing lesson: `push_files` creates a NEW branch from the
  repo default branch — it takes no base. Always `create_branch`
  from the correct base branch FIRST, then `push_files` onto
  the existing branch. Verify the new branch's parent SHA and
  tree diff with `git fetch` before any further step (PR,
  workflow upload, CI claim).
- **Provenance trap found during the post-push regen (same
  round):** `scripts/generate-report.py` takes its base from
  the LOCAL `origin/main` ref (`rev-parse origin/main`) — it
  has no base parameter. In every round so far that ref was
  STALE at the P0 base `e1571db68ed87fb973c45960a4a3e27e09ba0d06`
  (nobody had fetched `main` locally since the PR #1 merge),
  so the manifest covered the cumulative diff vs the P0 base
  (182 files at R1-R3). This round the parent's
  `git fetch origin --prune` (run to confirm the wrong-branch
  deletion) updated the local `origin/main` to the real main
  head `8fc11fee`, and the regen then produced base `8fc11fee`,
  32 changed files and a 30-file manifest — a silent loss of
  152 manifest entries. The parent restored the ref with
  `git update-ref refs/remotes/origin/main e1571db…` and
  re-ran the regen, restoring the 182-file cumulative manifest.
  Standing rule: never refresh the local `origin/main` ref
  before a provenance regen; the generator's base is
  effectively the P0 base commit, and a future round should
  give the generator an explicit `--base` instead of reading
  a ref that any fetch can move.

## 11. R1 — Bundle Shape Integrity, Fail-Closed Validation & Source Metadata Preservation (2026-11-26)

Reviewer work order (relayed by the user, same branch and PR #4,
no merge, no P1-004): harden the P1-003 runtime in three places.
Starting HEAD `082efb595d1b4b6dd5b930e77111b6e648fb65b3` (P1-003
delivery head; local HEAD `1302ee4`, tree clean, merge-base with
P1-002 `b9072f07`). All three defects were reproduced on the
pre-fix code FIRST with a standalone repro script
(`~/workspace/consistency-frame-p1-delivery/evidence/p1003-r1/repro-p1003-r1.py`;
before-run output `repro-p1003-r1-before.txt`, after-run output
`repro-p1003-r1-after.txt`), then fixed, then re-run.

### 11.1 Defect A — bundle shape: required records replaced, hash recomputed, still accepted

Reproduced (pre-fix, 0 errors = accepted): `script_contract`,
`production_profile`, `script_to_performance`, `scene_plan`,
`shot_plan`, `performance_plan` each replaced by `None`;
`scene_plan` replaced by `["not", "an", "object"]`,
`script_to_performance` by `"scalar"`, `shot_plan` by `42`,
`performance_plan` by `3.5`; `session_id=None`,
`routing_plan_id=None`, `bundle_hash=None` — all accepted with
the bundle hash recomputed. Already rejected pre-fix:
`script_contract` as a list (1 error), `bundle_id=None` (1),
`bundle_id` as a list (2), `session_id=42` (1),
`bundle_hash="not-a-hash"` (1). Root cause:
`validate_script_to_performance_bundle()` skipped each record
validator when the field was `None` or not a dict, and skipped
the `session_id` / `routing_plan_id` / `bundle_hash` checks when
the value was `None`.

Fix (Task A, `validate_script_to_performance_bundle()` only):
every required field is now validated for BOTH presence AND
correct type — the `is not None` / `isinstance` guards are gone
and all six record validators run unconditionally (each already
returns a schema type error for a non-dict value);
`bundle_id` / `session_id` / `routing_plan_id` error when not a
valid non-empty string (covers `None`); `bundle_hash` errors
when not a string matching the SHA-256 regex, else it is
recomputed and compared. The cross-reference block stays
guarded by `isinstance(scene/shot/perf, dict)`. After the fix
every Defect A case is rejected (1–2 errors each; `bundle_id`
`None` now 2 — invalid ID plus the s2p record's ID mismatch);
the valid baseline bundle still validates.

### 11.2 Defect B — malformed input leaks raw TypeError

Reproduced (pre-fix, all raw `TypeError: unhashable type:
'list'/'dict'`): `script.dialogue[0].line_id = []` and
`scene_plan.scenes[0].scene_id = {}` in `_unique_id_errors()`;
`build()` with `scene_id=[]`; articulation target as a list;
`production_medium` as a list with `is_live_action_footage=true`.

Fix (Task B): type is now checked before a value is used as a
dictionary or set key, before a string method is called on it,
and before set membership is tested with it — never silently
coerced, never swallowed indiscriminately. Hardened, in
`runtime/script_to_performance.py`: `_articulation_errors()`
(non-string target/kind/species append a field-naming error and
skip that check); `_live_action_errors()` and
`_subject_live_action_errors()` (membership in the generated
media/style sets guarded by a new `_is_hashable()` helper);
`_unique_id_errors()` (non-string identifier appends an error
and is never used as a dict key); `_kind_species_lookup()`
(only `str` values enter the kind/species tables);
`_dimension_agreement_errors()` (unhashable dimension value
appends an error and is skipped from the agreement map);
`_cross_reference_errors()` (project agreement only from `str`
project IDs; schema versions collected as a `list[str]` with a
field-naming error for a non-string; `beat_ids` only from `str`
beat IDs); `_dialogue_mapping_errors()` (source/performance
line-ID sets built from `str` IDs only, non-string IDs append an
error; the same str-only rule for the `source_by_id` /
`perf_by_id` maps); `_binding_errors()` (`shot_ref` checked
`isinstance(str)` before membership); `_agreed_project_id()`
(only `str` project IDs count); `_assemble_s2p_record()`
(versions from `str` schema versions only);
`build_script_to_performance_bundle()` stage A (the routing
plan's `session` record guarded against a non-dict, and the
blocked-diagnostics join guarded against a non-list and
non-dict entries — a list `session` raised `AttributeError`
before this fix). After the fix every Defect B case returns
structured field-specific errors (the two validator cases: 2
errors each; the build cases: `ScriptToPerformanceError`, never
a raw exception).

### 11.3 Defect C — source dialogue metadata dropped or changed

Reproduced (pre-fix, all passed validation when they must fail):
the Performance Plan line's `character_id` removed while the
source line supplies `char-001`; the Performance Plan line's
`language` changed `en` → `bn` while the source line supplies
`en`; the Performance Plan line's `language` removed.

Fix (Task C, `_dialogue_mapping_errors()` only): when the source
dialogue line supplies a non-empty string `character_id`, the
Performance Plan line must contain the SAME value (missing,
wrong type or different string all fail); when the source
supplies a non-empty string `language`, the Performance Plan
line's top-level `language` must equal it (missing, wrong type
or different all fail). No replacement ID is invented and no
language is inferred. A source line that supplies neither
imposes no metadata requirement. The exact dialogue text, line
ID and ordering protections are unchanged. After the fix all
three Defect C cases are rejected; the correct character ID and
language still build.

### 11.4 `--base` generator parameter and provenance clarification (§8)

The P1-003 provenance trap (§10) is fixed at the source: both
generators now take a minimal, backwards-compatible
`--base <sha>` parameter (a `resolve_base()` helper mirroring
`resolve_github_head()`; default = current behaviour, the local
`origin/main` ref). Default behaviour is unchanged —
`python3 tests/test_reports.py` still passes. **Deviation from
the work order's literal regen commands, recorded here:** the
brief names `--base` only for `scripts/generate-report.py`, but
`--base` was added to `scripts/generate-build-report.py` too
(same helper, same default), because build-report is the writer
of `release-manifest.json` — without `--base` there, a fetched
`origin/main` (`8fc11fee`) would silently shrink the manifest
from 182 entries to 30 again, which is exactly the trap §8
wants fixed. No other generator behaviour changed.

No `git update-ref` or remote-tracking-ref manipulation was used
in this round, and the local `origin/main` ref (still held at the
P0 base `e1571db68ed87fb973c45960a4a3e27e09ba0d06` from P1-003)
was not relied on or reproduced. The parent restores
`origin/main` to its true value with a plain
`git fetch origin main` before the regen; the regen uses
`--base e1571db68ed87fb973c45960a4a3e27e09ba0d06` explicitly.

The three SHAs and their roles, made explicit (per §8):

- P1-002 base
  `b9072f07910b77621e3f5bdad1fd7546f5fc09c2` — the base commit
  the P1-003 branch stacks on.
- Workflow commit
  `6547893db8a8cb34eb47fa9f47f3e41a7116699f` — the
  website-uploaded workflow-file commit on the P1-003 branch.
- Final P1-003 PR HEAD
  `082efb595d1b4b6dd5b930e77111b6e648fb65b3` — the P1-003
  delivery head; R1 produces a new final head (content commit +
  docs/provenance commit; the parent pushes and re-runs the
  regen with the actual GitHub head).

The R1 regen runs
`python3 scripts/generate-report.py --base e1571db… --github-head <content SHA>`
then
`python3 scripts/generate-build-report.py --base e1571db… --github-head <content SHA>`
LAST, then
`python3 scripts/generate-report.py --check --base e1571db… --github-head <content SHA>`
with the SAME full `--github-head` (the local content-commit SHA
as the provisional head, exactly as P1-003 did). The manifest
must stay 182 entries with every entry resolving; the
manifest/build-report head is not claimed to equal the final PR
HEAD unless it actually does. The manifest SHA and CHECKSUMS SHA
are recorded in the delivery report, not in this doc (hash-chain
rule: this doc cannot quote the manifest SHA of the generation
that includes the doc's own final text); the post-push regen gets
a brief addendum here recording the regen head only.

### 11.5 Verification

- `tests/test_script_to_performance_runtime.py`: **691 checks, 0
  failures** — baseline 606 intact (SESSION-ROUTING 22, SCRIPT
  18, PLANS 23, DIALOGUE 23, XREF 35, DETERMINISM 16, NULL156
  469) plus 85 new (BUNDLE-SHAPE 35, FAIL-CLOSED 41,
  DIALOGUE-META 9).
- `tests/test_skill_router.py`: 766 checks, 0 failures.
  `tests/test_routing.py`: 305 checks, 0 failures.
  `tests/test_performance_semantics.py`: 32 checks, 0 failures.
- `python3 scripts/validate-repo.py`: PASS.
  `python3 scripts/generate-registries.py --check`: CHECK OK.
  `python3 scripts/generate-routing-catalog.py --check`: CHECK OK.
  `python3 tests/test_reports.py`: PASS (0 failures).
- Full suite `bash tests/run-tests.sh`: **78 entries / 64
  distinct IDs / 37 distinct commands, 0 failures, status PASS**
  (was 75/61/37; the three new group IDs are registered one
  `run_one` line each, following the existing per-group
  pattern).
- `git diff --check`: clean (also the suite's P0-DIFF-CHECK
  entry, PASS).
- Repro evidence: `repro-p1003-r1-before.txt` (all three defects
  reproduced on pre-fix code) vs `repro-p1003-r1-after.txt`
  (every case rejected / structured, baseline bundle still
  validates).

### 11.6 Files changed (R1 content)

- `runtime/script_to_performance.py` — Task A bundle validator,
  Task B hardening of the nine named functions plus the builder
  stage A, Task C dialogue mapping.
- `tests/test_script_to_performance_runtime.py` — three new
  groups: `CF-P1-003-R1-BUNDLE-SHAPE` (35),
  `CF-P1-003-R1-FAIL-CLOSED` (41),
  `CF-P1-003-R1-DIALOGUE-META` (9); no existing test weakened
  or removed.
- `tests/run-tests.sh` — three new `run_one` lines (one per new
  group ID).
- `scripts/generate-report.py`, `scripts/generate-build-report.py`
  — `--base <sha>` parameter (default unchanged).
- `docs/implementation/CF-WO-P1-003-corrections.md` — this §11.
- `docs/runtime/SCRIPT_TO_PERFORMANCE_RUNTIME.md` — dialogue
  preservation (Task C) and validation/error model (Tasks A/B).
- `AGENTS.md` — short R1 note in the P1-003 section.
- `CHANGELOG.md` — R1 entry under [Unreleased].
- `tests/last-run.json` — regenerated by the full suite run.

Protected paths untouched: no P0 schema, canonical YAML, skill,
`local_session` / `authorization` / `skill_router`,
`asset_policy` / `timeline_policy` / `atomic_write`, or
component file changed. The only `scripts/` changes are the two
`--base` additions listed above. No file over 100 MiB, no media
added. The zero-dialogue schema tension stays documented and
fail-closed; no Performance Plan line was invented and no P0
schema was modified.

### 11.7 Provenance regen addendum (docs commit)

Provenance was regenerated locally with the explicit `--base`
mechanism (§11.4), using the R1 content commit as the
provisional head, exactly as P1-003 did; the parent re-ran the
regen with the actual GitHub head after pushing. Manifest: 182
entries, every entry resolves, no hash mismatches, no silent
scope change (the `changed_files` list holds 184 names — the
182 manifest files plus `release-manifest.json` and
`CHECKSUMS.txt`, both excluded from the manifest by design).
`generate-report.py --check` with the same full `--github-head`:
CHECK OK. CHECKSUMS recomputed by hand: all three entries OK.

Post-push regen (parent, 2026-11-26): provenance regenerated
with the explicit `--base` mechanism and the actual GitHub head
after the docs push; no `git update-ref` or ref manipulation
was used at any point in R1 — the local `origin/main` ref was
restored to its true value by a plain `git fetch origin main`
before the regen. Manifest: 182 entries, 0 mismatches against
the tree at regen time; CHECKSUMS 3/3 OK. The manifest head and
manifest commit lag the final PR head by one docs commit, the
established pattern.

No final provenance values are quoted in this section: the
manifest SHA, the manifest head and commit, the CHECKSUMS SHA
and the final GitHub head are recorded in the delivery report
and the PR body, not here (hash-chain rule, §11.4) — so that
regenerating the manifest never requires editing this document.

## 12. R2 — Manifest Integrity & Adversarial Nested JSON Validation (2026-11-26)

Reviewer work order (relayed by the user, same branch and PR #4,
no merge, no P1-004): restore complete release-manifest
integrity and expand adversarial nested JSON validation across
the Script-to-Performance runtime. Starting HEAD
`6bb8e0a51b8e037ba7875f79fc7dbdaed063e527` (R1 delivery head;
local HEAD `235533a`, tree clean, merge-base with P1-002
`b9072f07`). No rebase, no branch-reference manipulation, no
`git update-ref` anywhere in R2.

### 12.1 Task 0 — verified baseline preflight

All seven preflight checks passed before any file was modified:
(1) branch is `feat/cf-p1-003-script-to-performance-runtime`;
(2) remote starting HEAD is the R1 final head above; (3) PR #3
is based on P1-001 HEAD `b2db48828b3e964eebca3fe585bff84bafb00dae`;
(4) PR #3 current HEAD is `b9072f07910b77621e3f5bdad1fd7546f5fc09c2`;
(5) PR #4 base SHA equals the current PR #3 HEAD; (6) PR #2, #3
and #4 are all Open, Draft, Unmerged (verified live via the
GitHub API); (7) the R1 combined ZIP's code matches the remote
source — 215 files, 0 mismatches, 0 missing.

### 12.2 Task A — manifest defect and fix

Known reproducible defect: the R1 manifest held 182 entries and
exactly one was mismatched —
`docs/implementation/CF-WO-P1-003-corrections.md`, recorded
34,017 bytes against an actual 34,742 bytes at the start of R2.
Root cause: the corrections document was edited AFTER the R1
manifest was generated (the §11.7 post-push regen addendum),
so the manifest hashed a version of the document that no longer
existed. The R1 manifest's own SHA and the CHECKSUMS entries
were still internally consistent — only the one listed file had
drifted.

Fix, in two parts. First, finalize-first ordering: the
corrections document is completed BEFORE the final manifest is
generated, and it is not edited afterwards. Second, the
self-referential pattern is removed: §11.7 was rewritten to
quote no generated value at all — no final manifest hash, no
manifest head or commit, no final GitHub head. Final provenance
values live only in the external delivery report and the PR
body, never in this document, so regenerating the manifest can
never again require editing the document that the manifest
hashes. The 182-file manifest scope is preserved (no scope
defect was demonstrated); the intentional exclusions of
`release-manifest.json` and `CHECKSUMS.txt` from the manifest's
own file list are preserved.

Automated verification: `tests/test_reports.py` gains the
`CF-P1-003-R2-MANIFEST` group (17 checks). A pure helper,
`verify_manifest_entries(manifest, root)`, iterates every
manifest entry and checks existence, recomputed SHA-256 and
recomputed byte count; rejects duplicate paths and unsafe
paths (`..`, leading `/`, backslashes, empty path); verifies the
two intentional exclusions and the manifest structure and
provenance fields (head/commit present as 40-char hex, entry
count, `changed_files` accounting: every manifest file plus the
two excluded files). The group also carries negative checks
that tamper in-memory copies of the manifest (byte count, SHA,
duplicate, five unsafe paths, excluded file listed, missing
file, malformed provenance head, dropped entry) — each tampered
copy MUST be rejected. The group fails on the pre-regen tree
(the two files changed in R2 are stale in the old manifest, as
designed) and passes after the final regen. Existing
CF-P0-REPORT-001..005 checks are untouched.

Suite-interaction defect found by the new group (fixed in R2):
`tests/run-tests.sh` used to regenerate the living report
(`python3 scripts/generate-report.py`, defaults) BEFORE the
report tests ran — and the living report is itself a
manifest-listed file, so the regen invalidated the manifest
check on every full-suite run (all six `test_reports.py`
group entries failed, even though the standalone file passed).
The regen also uses the local `origin/main` ref as its base,
which R1 restored to the true main head, so the suite's
regenerated report additionally carried a different base and a
different changed-files list than the committed one. Fix: the
six report-test entries now run BEFORE the living-report regen
step in `run-tests.sh`, so the manifest-integrity group
verifies the committed manifest against the committed tree;
the regen + `--check` pair still runs afterwards and still
verifies the generator. No check was weakened — the group
still fails if any listed file changes without a regen.

### 12.3 Task B — adversarial nested JSON validation

Eight boundaries, table-driven, over schema-valid baseline
fixtures — 1,096 new checks in eight new groups in
`tests/test_script_to_performance_runtime.py`
(`CF-P1-003-R2-SCRIPT` 121, `CF-P1-003-R2-PROFILE` 200,
`CF-P1-003-R2-SCENE` 170, `CF-P1-003-R2-SHOT` 150,
`CF-P1-003-R2-PERFORMANCE` 202, `CF-P1-003-R2-EDITING` 51,
`CF-P1-003-R2-BINDINGS` 131, `CF-P1-003-R2-BUNDLE` 71).
For every applicable required object/array boundary the
malformed types are `null`, boolean, number, string, array
instead of object, object instead of array, and malformed
array elements; for identifiers and reference fields the matrix
adds empty string, object, array, nested arrays and nested
objects. Every bundle case recomputes the hash, so only
structural validation can reject it. Public validators return
structured errors; the builder raises `ScriptToPerformanceError`;
no raw `TypeError`/`AttributeError`/`KeyError`/`IndexError`
escapes. Baseline 691 checks are intact (total S2P 1,787).
Valid baselines still pass; truly optional omitted fields stay
valid where the schema permits omission; explicit null stays
invalid where the schema declares a non-nullable field; no
malformed input produces a partial bundle and no invalid data
is silently discarded. No canonical schema was weakened.

### 12.4 Task C — production-code defects found and fixed

Twenty cases, all reproduced on the pre-fix code FIRST with a
standalone repro script
(`~/workspace/consistency-frame-p1-delivery/evidence/p1003-r2/repro-p1003-r2.py`;
before-run output `repro-p1003-r2-before.txt`, after-run output
`repro-p1003-r2-after.txt`), then fixed, then re-run: 0/20
fixed before, 20/20 fixed after.

- **D1–D14 — raw `TypeError` crash class.** A truthy
  non-iterable scalar (int/float/bool) where an array is
  required was iterated via `x or []` (`'int' object is not
  iterable`). Crash sites: `_unique_id_errors` (script shots),
  `_live_action_errors` (profile per-subject overrides), and the
  cross-reference helpers (`_subject_table`,
  `_known_characters`, `_cross_reference_errors`,
  `resolved_entries`, `_kind_species_lookup`, `_binding_errors`)
  for scene scenes/beats/subjects/character_ids, shot
  shots/subjects/character_ids, performance lines, script
  dialogue, voice bindings and reaction holds — escaping
  `validate_script_contract`, `validate_production_profile`,
  `validate_script_plan_drafts`,
  `validate_script_to_performance_bundle` and the builder (as a
  raw `TypeError`, not `ScriptToPerformanceError`). Fix: a new
  `_as_list()` helper (the list itself, else `[]`; schema
  validation still reports the type error) applied at every
  iteration site.
- **D12 — non-JSON-serialisable bundle hash.** A bundle
  containing a set crashed `validate_script_to_performance_bundle`
  inside the hash recomputation (`TypeError: Object of type set
  is not JSON serializable`). Fix: hash recomputation in the
  bundle validator is wrapped so it appends a structured error
  instead.
- **D15–D18 — empty-string identifiers silently passed.**
  `scene_id`, `shot_id` (script and shot plan), `line_id` and
  shot `scene_id`/`beat_id` have no schema pattern and passed
  with `""`. Fix: `_unique_id_errors` now rejects an empty
  identifier, and `validate_shot_plan` rejects empty
  `scene_id`/`beat_id` references.
- **D19–D20 — dangling per-shot overrides silently built.** A
  profile `per_shot_overrides` entry with `shot_id` `""` or an
  unknown shot built successfully — no cross-check existed.
  Fix: `_cross_reference_errors` now requires every per-shot
  override `shot_id` to reference a valid shot-plan shot (a
  non-string `shot_id` is reported too).

Deliberately NOT changed (schema-permitted, no resolution rule
exists): empty free-text fields (`language`, `focus_target`,
`eyeline_target`, `audio_asset_id`, `purpose`, `rhythm`,
etc.), script `beats` elements, and duplicate per-shot
override `shot_id`s; a per-subject override character not
appearing elsewhere is definitional (the profile is context,
per the existing `_known_characters` design), not dangling.

### 12.5 Verification

- S2P suite: **1,787 checks, 0 failures** — baseline 691
  intact (SESSION-ROUTING 22, SCRIPT 18, PLANS 23, DIALOGUE
  23, XREF 35, DETERMINISM 16, NULL156 469, R1-BUNDLE-SHAPE
  35, R1-FAIL-CLOSED 41, R1-DIALOGUE-META 9) plus the eight
  new R2 groups (1,096). Per-suite, all 0 failures: router
  766, routing 305, S2P 1,787, local session 67, authorization
  47, private voice security 158, performance semantics 32.
- `tests/test_reports.py`: 64 checks (47 pre-existing +
  17 new manifest-integrity checks). On the pre-regen tree 63
  pass and exactly one fails — the manifest entry-by-entry
  check, because the R1 manifest is stale for the two files R2
  changed (this document and `test_reports.py` itself); that
  failure is the defect the group exists to catch, and it is
  cleared by the final regen. All 16 tamper negative checks
  pass (every tampered in-memory copy is rejected).
- Full suite `bash tests/run-tests.sh`: **87 entries / 73
  distinct IDs / 37 distinct commands** (was 78/64/37; nine
  new group entries). Pre-regen: 81 PASS / 6 FAIL — all six
  failures are the six `test_reports.py` group entries, which
  share the one stale-manifest failure above; every other entry
  passes. The post-regen full-suite re-run did NOT come back
  all-PASS at first: it exposed the suite-interaction defect
  documented in §12.2 — the suite's own living-report regen
  step ran before the report tests and rewrote a
  manifest-listed file, and the run also caught the two
  content files edited after the first regen (this document,
  46,398 B vs 45,385 B recorded, and `tests/run-tests.sh`,
  8,652 B vs 8,301 B recorded) plus `tests/last-run.json`
  (whose bytes change on every suite run). The fix is the
  `run-tests.sh` reorder in §12.2 plus a second regen after
  the final all-PASS suite run, so the manifest records the
  final all-PASS `last-run.json` (a later all-PASS run
  reproduces it byte-identically). The final full-suite
  result and the final manifest SHA are recorded in the
  delivery report, not here, because the delivery report is
  where final provenance values live.
- `validate-repo.py`: PASS. `generate-registries.py --check`:
  OK. `generate-routing-catalog.py --check`: OK.
  `git diff --check`: clean.
- `generate-report.py --check` with the explicit `--base` and
  the content head: reported out of date, for the known
  one-commit-lag reason only — the committed living report was
  generated at the content head while the local HEAD had moved
  to the docs commit; the generated files themselves
  (build-report.json, BUILD_REPORT_P0.md, CHECKSUMS.txt,
  release-manifest.json) were byte-identical after a fresh
  regen. The `--check` behaviour is unchanged from R1.
- Manifest: 182 entries; after the final regen every entry
  verifies against the tree (existence + SHA-256 + byte
  count, 0 mismatches) and CHECKSUMS recompute 3/3 OK — the
  final manifest SHA and CHECKSUMS SHA are in the delivery
  report, not here.

### 12.6 Files changed (R2 content)

- `runtime/script_to_performance.py` (`_as_list()` helper,
  empty-identifier rejection, per-shot override cross-check,
  bundle-hash wrap)
- `tests/test_script_to_performance_runtime.py` (eight new
  R2 groups)
- `tests/test_reports.py` (`CF-P1-003-R2-MANIFEST` group)
- `tests/run-tests.sh` (nine new group entries: eight R2 S2P
  groups + the manifest group; the six report-test entries
  moved BEFORE the living-report regen step, so the
  manifest-integrity group checks the committed tree — see
  §12.2)
- `docs/implementation/CF-WO-P1-003-corrections.md` (this §12;
  §11.7 rewritten with no generated values)
- `AGENTS.md`, `CHANGELOG.md`
- Generated (regen only): `docs/architecture/living-architecture-report-v2.4-p0.md`,
  `docs/implementation/BUILD_REPORT_P0.md`,
  `docs/implementation/build-report.json`,
  `docs/implementation/CHECKSUMS.txt`, `release-manifest.json`,
  `tests/last-run.json`
