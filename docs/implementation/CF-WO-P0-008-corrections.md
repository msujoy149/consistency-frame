# CF-WO-P0-008 — Fail-Closed Private Voice Security: Corrections

Work order CF-WO-P0-008 (received 2026-11-22), branch
`feat/cf-p0-safe-foundations`. Local base `5574589` (P0-007 docs);
local head at the start of the Correction F/G work `6224bba`
(production Corrections A–E already implemented and committed
locally in `f3e0c2b` and `6224bba`; this record covers the whole
order, but the F/G author changed tests and documentation only and
committed nothing — the coordinator integrates and commits). This
order does NOT start P1, does NOT merge, does NOT change the PR
Draft state, and does NOT touch `main`, the Master Prompt, or
VoiceStudio/OpenMontage internals. No server, API backend, cloud
database, or cloud identity service was built or invented.

## Objective

Close the three reproduced privacy failures P0-007 left open: (A)
the production voice resolver resolved a private v2.5 voice with
no requester identity; (B) a caller-created authorization
dictionary — including a forged `granted_by` — authorized a
private voice export; (C) timeline cross-reference validation
lived only in a test file, so no production code enforced the
relationship or ownership rules. Centralize every production
access decision in one choke point (E), remove the duplicate
test-only authorization logic (D), prove the fixes with a
dedicated security regression suite that executes the real
production functions (F), and reconcile the schemas and
documentation with the implemented contracts (G).

## 1. What already existed

- `scripts/asset_policy.py`: structured ownership (`owner_id`,
  `workspace_id`, `visibility`, `sharing` — opaque local IDs,
  private by default), `validate_ownership`,
  `ownership_allows_access`, `validate_voice_profile` (conditional
  v2.5 rules), `resolve_voice_for_production`,
  `validate_private_voice_export(voice, authorization=None)`,
  `resolve_private_path`, and the mode policy.
- `tests/test_character_registration.py`: the binding resolver
  `resolve_voice_for_character`, plus local copies of the
  character/voice binding check and the owner/workspace-scoped
  resolution rule.
- `tests/test_timeline_manifest.py`: the reference implementation
  of `validate_timeline_cross_references()` — the only place the
  timeline relationship rules existed — plus fixtures and the 14
  P0-007 cases.
- `schemas/timeline-manifest.json` v2.5, `schemas/voice-profile.json`,
  `schemas/character-registration.json`, and the P0-007 corrections
  record describing the ownership contract.

## 2. What was contradictory

- **Resolver vs privacy promise.** The docs promised
  owner/workspace-scoped, private-by-default voices, but
  `resolve_voice_for_production` checked requester access only
  inside `if requesting_owner_id is not None or
  requesting_workspace_id is not None:` — a caller that omitted
  both identities still received the voice. Matching owner and
  workspace between two records was treated as proof that the
  requester was permitted, although the function never knew who
  the requester was.
- **Export vs authority.** `validate_private_voice_export`
  accepted any dictionary carrying `granted_by`, `scope`, and
  `explicit_authorisation == True` — a textual identity field was
  treated as proof of authority, so `granted_by: "owner-b"` (or
  `"owner-a"`, claimed by anyone) authorized exporting owner-a's
  private voice. No trusted boundary existed between an untrusted
  authorization request and a validated permission decision.
- **Timeline validator vs production pipeline.** The only
  timeline validator lived in a test file. A test proving a
  test-file helper works is not proof that the production
  planning and handoff pipeline enforces the same rules — and
  production code could not call it at all.
- **Several privacy rules vs one policy.** Binding, resolution,
  export, and timeline checks each carried their own slightly
  different access logic, so a fix in one place could drift from
  the others. Permission for one action (local production use)
  was not distinguished in code from permission for another
  (export, provider transmission).

## 3. What was missing

- A mandatory requester-identity requirement for private v2.5
  voice resolution, failing closed on a missing owner or
  workspace.
- An owner-bound export authorization boundary that a caller
  cannot forge by constructing a dictionary.
- A production timeline validator with strict v2.5 ownership
  enforcement, and tests that import and execute it.
- A centralized authorization decision point with explicit
  action scopes.
- A regression suite that reproduces all three failures and pins
  the fixed behaviour.
- Documentation stating the trusted boundary honestly — what it
  enforces, and what still needs the P1 app/session runtime.

## 4. What was changed (per Correction A–G)

### 4.1 Correction A — Requester identity is mandatory for private v2.5 voice resolution

`scripts/asset_policy.py` — `resolve_voice_for_production`
(unchanged signature: `requesting_owner_id=None`,
`requesting_workspace_id=None`, `require_approved=True`):

- For a `schema_version "2.5"` voice, the requester identity is
  now mandatory. The resolver calls `authorize_action(
  "use_in_production", voice ownership, requesting_owner_id,
  requesting_workspace_id)`, which fails closed on a missing
  owner, a missing workspace, an unknown action, or an invalid
  ownership record. A missing requester is never an authorized
  internal request; there is no silent fallback to the
  character's owner; `None` is never an authorization bypass.
- The full check list before a voice is returned: the voice
  exists; it belongs to the requested Character ID; the
  character exists and the voice ownership matches the character
  ownership; the record passes the v2.5 conditional validation;
  the requester is authorized under the ownership/sharing
  policy; when `require_approved`, `approval_status` and
  `status` are both `"approved"`.
- Sharing rules are unchanged: `private` + `none` admits only
  the owner in the owning workspace; `shared` + `workspace`
  additionally admits another owner in the same workspace;
  `shared` + `explicit` admits only the owner (no explicit grant
  record is modelled here, so no third party is admitted).
- Legacy compatibility is unchanged: a non-2.5 record keeps its
  historical contract (binding + validation + approval; the
  requester is checked only when given). A legacy record that
  lacks reliable ownership does NOT automatically become
  available for private v2.5 production use — it gains v2.5
  protection only by explicit ownership assignment (an ownership
  object matching its character, plus `schema_version "2.5"`).
  Ownership is never inferred from a filename, name, or image.

### 4.2 Correction B — Owner-bound private voice export

`scripts/asset_policy.py` — `TrustedAuthorizationContext`,
`issue_trusted_authorization_context`, and a rewritten
`validate_private_voice_export(voice, authorization=None,
trusted_context=None, to_provider=False)`:

- A private voice export now requires a
  `TrustedAuthorizationContext` issued by
  `issue_trusted_authorization_context` — the local application
  authorization boundary. The `authorization` dict, when given,
  is an untrusted request record only: its `granted_by` / `scope`
  / `explicit_authorisation` fields NEVER confer authority and
  are ignored for the decision.
- The boundary is structural (a type boundary), not
  cryptographic proof of identity. Only the factory, holding a
  module-private sentinel (`_AUTHORIZATION_BOUNDARY`), can
  construct a context; direct construction raises `TypeError`,
  and a plain dict or `SimpleNamespace` is rejected by the
  `isinstance` check. The factory fails closed at issuance
  (`ValueError` on a missing/invalid field, including an empty
  scope). A local pure-Python function cannot prove who the
  human at the keyboard is — the P1 runtime (app UI / session)
  must supply the actor identity at the boundary; until then the
  factory IS the boundary and its caller MUST be the trusted
  local application. Passing someone else's IDs to the factory
  is boundary misuse, not a validator bypass: the validator
  still checks the issued context against the asset.
- The validator checks the context against the voice on every
  point: the trusted actor is the voice owner in the voice
  workspace; the issuer (`granted_by`) is the voice owner (a
  forged `granted_by` is rejected); the action is an explicit
  `"export_private_asset"`; the scope is non-empty; the context
  covers exactly this `character_id` and `voice_profile_id`; the
  context is not expired (`expires_at`, ISO-8601 UTC
  `"YYYY-MM-DDTHH:MM:SSZ"`, or `None` = no expiry) and not
  revoked (`ctx.revoked = True`).
- Export to an external provider (`to_provider=True`)
  additionally requires `provider_transmission_approved` on the
  context — a separate permission from export. Export is
  owner-only even under `shared` + `workspace`: sharing a voice
  for use in a workspace never authorizes another owner to
  export it. Private sharing and exporting remain disabled by
  default: no context, no export.

### 4.3 Correction C — Timeline validation moved into production

New file `scripts/timeline_policy.py` —
`validate_timeline_cross_references(manifest, registry,
requesting_owner_id=None, requesting_workspace_id=None, *,
strict=False)`:

- The implementation moved out of
  `tests/test_timeline_manifest.py` verbatim; the test file now
  imports the production function (`validate_timeline_cross_
  references is timeline_policy.validate_timeline_cross_
  references`) and keeps only fixtures and cases. There is no
  second implementation.
- **Structural mode (default, `strict=False`):** the P0-007
  relationship contract, unchanged — shot/scene/dialogue-line/
  character/voice/audio/clip/track/sync-group existence, timing,
  speaker/listener agreement, no silent character/voice/audio
  switch. A registry section that is ABSENT is skipped (partial
  registries allowed); a section that is PRESENT is
  authoritative. Valid v2.3 timelines still pass.
- **Strict v2.5 production mode (`strict=True`):** the structural
  contract PLUS fail-closed ownership enforcement, for private
  v2.5 production only. Strict applies only to `schema_version
  "2.5"` manifests — a strict call on a v2.3 file is itself an
  error (a v2.3 file is valid only under the legacy structural
  contract, never as an authorized private v2.5 production). In
  strict mode: every kind of asset the manifest references must
  have its registry section present (missing registry data fails
  closed); requester owner + workspace identity is required
  whenever the timeline references a character, voice, or
  dialogue line; every referenced character, voice, and
  dialogue-bound audio asset must carry a valid ownership
  binding and pass `authorize_action("use_in_project", ...)` for
  the requester; every referenced voice must be approved.
  Legitimate non-character tracks — narration, music, ambience,
  SFX, foley — reference none of these and remain valid without
  a requester.
- The timeline registry holds MINIMAL reference records (id,
  `character_id`, `approval_status`, `ownership`) — not full
  voice profiles — so the full production voice resolver (which
  validates the complete v2.5 voice record) is not applicable
  here. The ownership/access decision is centralized in
  `asset_policy.authorize_action`, which the resolver also uses,
  so no second ownership algorithm exists.

### 4.4 Correction D — Duplicate test-only authorization logic removed

- `tests/test_character_registration.py`:
  `resolve_voice_for_character` is now a thin wrapper over the
  production resolver (`asset_policy.resolve_voice_for_
  production`) — no authorization logic of its own lives there.
  `check_voice_binding` IS
  `asset_policy.check_voice_binding` and `resolve_for_user` IS
  `asset_policy.resolve_for_user` (production functions moved to
  `scripts/asset_policy.py`; the test-file names are aliases to
  the production objects, not second implementations).
- `tests/test_timeline_manifest.py`: the reference implementation
  of `validate_timeline_cross_references` is deleted; the file
  imports the production function from
  `scripts/timeline_policy.py` (Correction C).
- Test fixture builders (mini-registries, clip/track/manifest
  builders) stay in the tests — they build inputs, they do not
  decide authorization.
- The bypass regression is pinned by the new suite (§4.6):
  identity assertions (`is`) on the production functions, and a
  spy test proving the character-registration resolver calls the
  production resolver.

### 4.5 Correction E — Centralized authorization decisions

`scripts/asset_policy.py` — `authorize_action(action, ownership,
requesting_owner_id, requesting_workspace_id) -> list[str]`
(the one choke point) and `ACTION_SCOPES`:

```text
"use_in_project", "use_in_production", "export_private_asset",
"transmit_to_provider", "share_with_workspace"
```

- Every production access decision goes through
  `authorize_action` (resolvers, export validation, and timeline
  validation all call it, or `validate_private_voice_export`,
  which builds on the same ownership checks). No second,
  slightly different privacy rule exists elsewhere.
- Fail closed: an unknown action, an invalid ownership record,
  or a missing requester owner/workspace is a rejection.
- Permission for one action never implies permission for
  another: local production use does not imply export, and
  export does not imply provider transmission. The separation
  is pinned by test (`CF-P0-008-SEC(g4)`).
- The ownership vocabulary is unchanged (`owner_id`,
  `workspace_id`, `visibility`, `sharing`); there is no default
  sharing, no automatic provider transmission, no unauthorized
  export.

### 4.6 Correction F — Security regression suite

New file `tests/test_private_voice_security.py` (74 checks,
test IDs `CF-P0-008-SEC`, run as `python3
tests/test_private_voice_security.py`, exit 0 = PASS). Every
check executes the actual production function. `tests/run-tests.sh`
gains one entry, `run_one "CF-P0-008-SEC" python3
tests/test_private_voice_security.py`, directly after the
`CF-P0-007-AC-TIMELINE` line.

- **(a) Resolver (17 checks):** no requester; owner only; workspace
  only; wrong owner; wrong workspace; correct owner / wrong
  workspace (second record); correct workspace / wrong owner
  (private sharing none); voice of another character; voice owned
  by another owner; voice owned by another workspace; pending
  voice with `require_approved`; correct owner + workspace
  approved resolves; `shared` + `workspace` admits another
  owner in the same workspace; `shared` + `workspace` rejects
  another workspace; legacy v2.3 record keeps its historical
  contract (resolves without a requester only when
  `require_approved=False` and no character registry is given —
  pinned, including the two companion pins: it rejects under the
  default `require_approved=True`, and rejects when a character
  registry is given because it has no ownership to match).
- **(b) Export (20 checks):** no context; dict-only (granted_by
  owner-a, full explicit); forged granted_by owner-b; trusted
  context with actor owner-b / granted_by owner-a; actor owner-a
  / granted_by owner-b; owner-a in the wrong workspace; empty
  scope and whitespace-only scope (factory raises `ValueError` —
  pinned); wrong action (`use_in_production` context); context
  for another character; context for another voice; expired
  context (`expires_at "2000-01-01T00:00:00Z"`); revoked context
  (`ctx.revoked = True`); `to_provider=True` without
  provider-transmission approval; `to_provider=True` with it
  approved (allows); correct owner export within scope (allows);
  `shared` + `workspace` does NOT authorize export by owner-b;
  direct `TrustedAuthorizationContext(...)` construction raises
  `TypeError`; a dict fake context is rejected; a
  `SimpleNamespace` fake context is rejected.
- **(c) Timeline, strict mode (23 checks, WO §4 scenarios 1–17):**
  1 owner-a timeline / owner-a character + voice passes; 2
  owner-b requester rejects; 3 owner-a requester, voice from
  workspace-b rejects; 4 character owner-a, voice owner-b
  rejects; 5 voice with no ownership rejects; 6 missing
  requester owner rejects; 7 missing requester workspace
  rejects; 8 correct owner + workspace passes (two-speaker
  timeline); 9 narration without a visible character passes,
  with and without a requester; 10 music without a Character ID
  passes (no requester); 11 ambience + SFX without a Character
  ID passes (no requester); 12 dialogue line with the wrong
  speaker rejects; 13 audio clip with the wrong Voice Profile
  rejects; 14 video clip with an unrelated Character ID rejects;
  15 sync group with a nonexistent clip rejects; 16 valid legacy
  v2.3 fixture passes under the legacy structural contract
  (empty registry) and really is v2.3; 17 strict enforces
  requester + ownership together (wrong requester AND a voice
  without ownership). Plus: strict on a v2.3 manifest returns a
  version error; strict rejects when a referenced kind's registry
  section is absent; strict rejects a dialogue-bound audio asset
  without ownership; a strict music-only timeline with a full
  registry and no requester passes.
- **(d) Bypass regression (4 checks):** the timeline validator in
  the test file IS the production function (same object);
  a spy test wrapping `asset_policy.resolve_voice_for_production`
  with a counting wrapper proves
  `test_character_registration.resolve_voice_for_character`
  calls the production resolver (original restored afterwards);
  `check_voice_binding` and `resolve_for_user` in the test file
  ARE the production functions.
- **(e) Path escape (4 checks):** `resolve_private_path` rejects
  `"../outside/secret.jpg"`, `"/etc/passwd"`, and a symlink
  escape out of the base (built with `tempfile`, as in
  `tests/test_private_overlay.py`); a safe path inside the base
  resolves.
- **(f) Invalid sharing mode (2 checks):** `authorize_action`
  rejects ownership with sharing `"everyone"`;
  `validate_ownership` rejects visibility `"shared"` + sharing
  `"none"`.
- **(g) Centralization (4 checks):** `authorize_action` rejects
  an unknown action; rejects a missing requester; production use
  is allowed for the correct owner — and the same voice is NOT
  automatically exportable (export without a trusted context
  still rejects).

**Before/after record (honest experiment, WO §7).** The
reproduction script
`~/workspace/consistency-frame-p0-delivery/p0-008-repro.py` was
run BEFORE the fix and reproduced all three failures (outputs
in `p0-008-repro-before.txt`): (A) the production resolver
RESOLVED a private v2.5 voice with NO requester identity; (B1)
export of an owner-a voice with a dict claiming granted_by
`'owner-b'` was ALLOWED; (B2) export with a plain caller dict
claiming granted_by `'owner-a'` (no trusted context) was
ALLOWED; (C) a timeline referencing a private voice VALIDATED
with no requester identity in the call. After the fix the same
inputs are REJECTED (`p0-008-repro-after.txt`: "RESULT: ALL
THREE FAILURES FIXED"). The new suite pins the AFTER behaviour
on every one of those inputs. No other historical numbers are
claimed in this record.

### 4.7 Correction G — Schema and documentation reconciliation

No new schema was needed: the P0-008 contract is a policy /
validation contract over the existing v2.5 records, not a new
record type, and no schema was created that falsely suggests
the local app already has an authenticated runtime. Changes:

- `schemas/README.md`: the P0-007 paragraph now points the
  timeline validator at its production home,
  `scripts/timeline_policy.py` (the test file imports it), and a
  short P0-008 paragraph records the mandatory requester
  identity, the trusted export context, the strict timeline
  mode, and the centralized `authorize_action`.
- `docs/07-character-registry.md`: a new section documents the
  fail-closed resolver (requester mandatory for v2.5), the
  owner-bound export contract + trusted context, and that
  private sharing/export remain disabled by default.
- `docs/architecture/ANIMATION_SCOPE_AND_PRODUCTION_MODES.md`:
  the ownership / voice-privacy passage (§C6) gains a pointer
  to the P0-008 contract (resolver + export + strict timeline);
  the document is not restructured.
- `docs/implementation/BUILD_REPORT_P0.md` and
  `docs/implementation/P0_UPDATED_IMPLEMENTATION_PLAN.md`:
  P0-008 is recorded (what changed; what stays P1).
- `CHANGELOG.md`: a `[Unreleased]` P0-008 entry.
- `AGENTS.md`: a "P0-008 Fail-closed private voice security
  (2026-11-22)" section after the P0-007 section, mirroring its
  style.
- This corrections record (new).

## 5. P0 vs P1 separation

P0-008 completes policy / validation / tests / documentation
ONLY. Still P1 (not started, not claimed): the first-run
registration UI; the app/session runtime that supplies the actor
identity at the trusted authorization boundary (until then the
factory IS the boundary and its caller must be the trusted local
application); provider execution; lip-sync / articulation
generation; the complete automated script-to-finished-video
runtime. No P1 item was converted to P0 by writing a contract
or a mock. No server, API backend, cloud database, or cloud
identity service exists or was started; nothing was deployed.
The trusted context is a structural type boundary, not
cryptographic proof of identity, and this record says so
wherever the boundary is described — a local pure-Python
function cannot prevent a malicious process running with the
same local OS user privileges from manipulating files or code,
and no such promise is made.

## 6. Test results

Final local run (Correction F/G work, 2026-11-22, branch
`feat/cf-p0-safe-foundations`; all commands run from the repo
root, uncommitted work):

- `python3 tests/test_private_voice_security.py` → exit 0.
  **74 checks, all PASS, 0 failures** (17 resolver + 20 export
  + 23 timeline + 4 bypass + 4 path + 2 sharing + 4
  centralization).
- `python3 tests/test_timeline_manifest.py`,
  `python3 tests/test_character_registration.py`,
  `python3 tests/test_private_overlay.py`,
  `python3 tests/test_production_direction.py`,
  `python3 tests/test_schemas.py` → all exit 0 (regression
  check after the F/G changes; the F/G work touched no
  production code and no other test file).
- `python3 scripts/validate-repo.py` → PASS.
- `python3 scripts/generate-registries.py --check` → CHECK OK.
- `bash -n tests/run-tests.sh` → OK.
- `git diff --check` → clean.

No test was reported PASS unless executed with the expected
successful result; no skipped test was counted as passed; no
count was invented. The full-suite (`bash tests/run-tests.sh`)
and remote-CI verification are the coordinator's / parent's
steps after integration and push (two-head rule, §7); no GitHub
CI pass is claimed here.

## 7. Validation (integrated run)

- The new suite was run repeatedly during development (74/74
  PASS on the final run) and once more after the `run-tests.sh`
  entry and all documentation edits, together with the six
  neighbouring suites listed in §6 — all green.
- The production code under test was not modified by the F/G
  work: `git diff` for `scripts/asset_policy.py` and
  `scripts/timeline_policy.py` is empty in this change set.
- No test, count, or CI claim in this record is made for a run
  that has not finished. Remote CI is the parent's step, after
  pushing (two-head rule, §8).

## 8. Reports, release manifest and provenance

- No registries were regenerated: `generate-registries.py
  --check` passes, and no canonical Skill / architecture data
  changed (the P0-008 contract is policy code + tests + docs).
- The build report, living report, release manifest, and
  checksums were NOT regenerated in this change set: those
  generators record the live GitHub head and the final test
  evidence, which only exist after integration, push, and CI.
  The coordinator / parent re-runs provenance after pushing.
  No future SHA was recorded; no GitHub CI pass was claimed
  before the relevant run finishes.
- Two-head rule preserved in intent: this record names the
  local base (`5574589`) and the local head at the start of the
  F/G work (`6224bba`); the delivery message must state the
  final local head and the live GitHub branch head separately.

## 9. Remaining limitations + unresolved decisions

1. **Trusted boundary is structural, not cryptographic.**
   `TrustedAuthorizationContext` proves only that the factory
   was called, not who the human at the keyboard is. The P1
   app/session runtime must supply the actor identity at the
   boundary. Until it exists, the factory's caller must be the
   trusted local application.
2. **Explicit sharing grants are not modelled.** `shared` +
   `explicit` admits only the owner; an explicit grant record
   for a named third party does not exist yet (P1).
3. **Timeline registry records are minimal.** Strict timeline
   validation checks ownership/approval on minimal reference
   records, not the full v2.5 voice record — the full production
   resolver is not applicable there. A timeline whose registry
   carries a stale approval state is only as correct as its
   registry.
4. **Local-process threat model.** P0 policy functions cannot
   stop a malicious process with the same OS user privileges
   from manipulating files or code. The contract governs
   well-behaved callers (the Brain, the companions, the app
   boundary), not a hostile local process.
5. **Legacy v2.3 records keep their historical contract.**
   They gain v2.5 protection only by explicit ownership
   assignment; until then they must not be treated as
   authorized for private v2.5 production use.
6. **No P1 runtime was started** (§5). In particular, no
   registration UI, provider execution, or
   script-to-finished-video runtime exists.

## 10. Acceptance checklist (WO §14, honest status)

### Production resolver

- [x] Requester owner identity required for private v2.5 access.
- [x] Requester workspace identity required.
- [x] Missing identities fail closed.
- [x] Wrong owner rejected.
- [x] Wrong workspace rejected.
- [x] Cross-character voice rejected.
- [x] Voice/Character ownership must match.
- [x] Approval status enforced.

### Private export

- [x] Arbitrary caller-created authorization dictionary is not
  treated as trusted authority.
- [x] Trusted local authorization context required.
- [x] Requester identity checked.
- [x] Authorization issuer checked against the asset owner.
- [x] Workspace checked.
- [x] Export scope checked.
- [x] Character and Voice Profile binding checked.
- [x] External provider transmission remains a separate
  permission.

### Timeline

- [x] Timeline cross-reference validator exists in production
  code (`scripts/timeline_policy.py`).
- [x] Tests call production implementation.
- [x] Test-only duplicate implementation removed.
- [x] Character ownership checked (strict mode).
- [x] Voice ownership checked (strict mode).
- [x] Audio Asset ownership checked (strict mode, dialogue-bound
  assets).
- [x] Requester identity checked (strict mode).
- [x] Missing required registries fail closed (strict mode).
- [x] Narration/music/ambience/SFX cases remain valid.
- [x] v2.3 compatibility preserved (structural mode).

### Regression and delivery

- [x] New negative tests reproduce all three failures.
- [x] Positive tests pass.
- [x] Existing installer security tests pass — verified by the
  coordinator's full-suite run (49/49 PASS, see below).
- [x] Complete test suite passes locally — coordinator ran
  `bash tests/run-tests.sh`: 49 recorded entries, 37 distinct
  test IDs, 30 distinct command strings, 49 PASS, 0 FAIL,
  0 skipped; `tests/last-run.json` SHA-256
  `cdb305693d7a29525181892ca1ff10d5ea65a4ddc607e4bd2658b08d832921e8`.
  The remote CI run is the parent's step after push.
- [ ] GitHub push and PR CI pass — not this change set's step
  (no push, no commit by the F/G author).
- [ ] Exact latest artifact inspected — pending push/CI.
- [x] Reports and manifest updated locally — regenerated by the
  coordinator with the passing run (`generate-report.py` +
  `generate-build-report.py`); re-regeneration with the new
  GitHub head after push is the parent's step (§8).
- [ ] Existing PR #1 updated — parent's step.
- [x] No direct push or merge to Main.
- [x] Remaining P1 limitations documented (§5, §9).

## 11. Files changed (Correction F/G change set only)

- `tests/test_private_voice_security.py` (new, 74 checks).
- `tests/run-tests.sh` (one entry: `CF-P0-008-SEC`).
- `docs/implementation/CF-WO-P0-008-corrections.md` (new, this
  record).
- `schemas/README.md` (P0-007 paragraph pointer fix + P0-008
  paragraph).
- `docs/07-character-registry.md` (fail-closed resolver +
  export contract section).
- `docs/architecture/ANIMATION_SCOPE_AND_PRODUCTION_MODES.md`
  (§C6 pointer to the P0-008 contract).
- `docs/implementation/BUILD_REPORT_P0.md` (P0-008 recorded).
- `docs/implementation/P0_UPDATED_IMPLEMENTATION_PLAN.md`
  (P0-008 recorded).
- `CHANGELOG.md` (`[Unreleased]` P0-008 entry).
- `AGENTS.md` (P0-008 section).

Production files (`scripts/asset_policy.py`,
`scripts/timeline_policy.py`), schemas, and every other test
file are unchanged in this change set — Corrections A–E were
implemented and committed locally beforehand (`f3e0c2b`,
`6224bba`).
