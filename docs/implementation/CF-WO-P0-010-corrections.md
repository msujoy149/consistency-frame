# CF-WO-P0-010 Corrections — Factory-Issuance Integrity for Trusted Authorization Contexts

**Work order:** CF-WO-P0-010 (independent-review follow-up to P0-009)
**Branch:** `feat/cf-p0-safe-foundations` — PR #1, NOT merged
**Base (P0-009 docs head):** `fb7ab55`
**Code head (this round):** `191abf6` (1 commit: code + tests)
**Remote head at order start (verified live):** `5e3e3c38b91d6529bfe11ac7e1156a46f29ae203`
**Date:** 2026-11-23

---

## 1. What existed (P0-009 state)

- `TrustedAuthorizationContext` (`scripts/asset_policy.py`) was genuinely immutable after issuance (`_frozen` flag, `__setattr__`/`__delattr__` raising `AttributeError`, no `__dict__`, copy/deepcopy/pickle returning frozen objects). Revocation was separate registry state (`_REVOKED_AUTHORIZATION_IDS`, keyed by the immutable per-issuance `authorization_id`).
- `validate_private_voice_export()` accepted a context on the basis of `isinstance(trusted_context, TrustedAuthorizationContext)` — the only issuance evidence was the constructor's private sentinel `_AUTHORIZATION_BOUNDARY`, a module-level object.
- `__setstate__()` populated slots from a supplied state tuple and froze the object — it was the unpickling path, and it could be called directly on an object made with `object.__new__()`.
- `__getstate__()` returned the slot values, so `pickle.dumps()` / `pickle.loads()` round-tripped a context. `__copy__` / `__deepcopy__` returned frozen clones that passed the same `isinstance` check as the original.
- `revoke_trusted_authorization_context()` / `is_trusted_authorization_revoked()` also used a bare `isinstance` check.
- `resolve_voice_for_production()` and the timeline validators do not consume a trusted context (they use requester identity + `authorize_action`); provider transmission is approved through `validate_private_voice_export(..., to_provider=True)` + the `provider_transmission_approved` field — there is no separate provider-transmission consumer function.

## 2. What was contradictory / missing

1. **Immutability is not issuance (Task A).** P0-009 proved the object cannot be *changed* after issuance, but nothing proved it *was issued*. The reviewer reproduced, with zero factory calls: a forged object passing the type check and the export authorization (`factory_calls=0`, `forged_is_trusted_context=True`, `forged_is_frozen=True`, `authorization_result=[]`).
2. **The sentinel is importable (Task A).** `_AUTHORIZATION_BOUNDARY` is a module-level object; `from asset_policy import _AUTHORIZATION_BOUNDARY` and passing it to the constructor yields a fully-formed, frozen, apparently legitimate context.
3. **`__setstate__` is a construction path (Task B).** `object.__new__(TrustedAuthorizationContext)` + `__setstate__((None, {...genuine-looking fields...}))` initializes an object without the factory. The same path is what unpickling uses, so a serialized representation could restore a trusted object.
4. **Pickle transfers authority (Task B).** `pickle.dumps()` on a context succeeded and `pickle.loads()` recreated an object that passed the `isinstance` check — trusted authority could move to another object (and, in principle, another process).
5. **Copy creates a second valid authority (Task B).** `copy.copy()` / `copy.deepcopy()` returned clones that passed the `isinstance` check and were accepted by export — an independently valid authorization the factory never issued.
6. **Only one consumer was protected — and weakly (Task C).** The export validator's `isinstance` check was the only gate, and the revocation functions shared the same weakness: a forged object carrying a stolen `authorization_id` (readable from any genuine context) could *revoke* a genuine context.
7. **No identity semantics (Task A, requirement 10).** The class relied on default object equality, which is identity-based, but nothing pinned that — a future value-equality implementation could have made a forged object compare equal to a genuine one and confused any identity registry.

## 3. What changed

### TASK A — Factory-issued instance verification

- New process-local, identity-based issuance registry: `_ISSUED_AUTHORIZATION_CONTEXTS`, a `weakref.WeakSet` (`scripts/asset_policy.py`). Registration happens **only** inside `issue_trusted_authorization_context()`, as the **last** step, after all field validation and after the constructor has returned successfully — a failed construction can never leave a partially issued or trusted object in the registry.
- New single verification function, used at every authorization boundary: `is_factory_issued_trusted_authorization_context(context)` — True only when the argument is an instance of the class **and** this exact object is a member of the issuance registry. It is the only check consumers use; no consumer performs a bare `isinstance` anymore.
- The class now has **explicit identity equality/hash semantics**: `__eq__` is `self is other`, `__ne__` is its negation, `__hash__` is `object.__hash__`. Two contexts issued with identical field values are distinct registry entries, never interchangeable, and a forged object with identical field values does not equal the genuine one.
- `__slots__` gained `"__weakref__"` so instances are weak-referenceable (a slotted class without it cannot enter a `WeakSet`). A `_DATA_SLOTS` tuple lists the data slots only, so copy/getstate logic never touches the weak-reference slot (which cannot be assigned).
- The constructor sentinel remains as a construction guard (direct construction without it still raises `TypeError`), but the module comment and docstrings now state plainly that the sentinel is **not** the trust anchor — the registry is. Direct construction *with* the imported sentinel still succeeds as object creation, but the object is unregistered and is rejected by every consumer.

### TASK B — Serialization and state-restoration bypasses removed

- `__setstate__()` now **raises `TypeError` unconditionally** — it can never create, initialize, authorize, or register a trusted context, on a fresh `__new__` object or on a genuine one. A failed `__setstate__()` on a genuine context leaves that context issued and working.
- `__getstate__()`, `__reduce__()` and `__reduce_ex__()` all **raise `TypeError`** — a trusted context has no serializable representation. `pickle.dumps()` fails; there is nothing to unpickle, replay, or transfer to another object or process. No serialization path calls the issuance factory automatically (and none may).
- `__copy__` / `__deepcopy__` keep their non-crashing behaviour but with a reviewed, safe design: the clone is frozen and value-identical (including the same `authorization_id`, so a copy of a revoked context still carries the revoked id and can never reset revocation state) **and deliberately NOT registered** — it has no authority and is rejected by every consumer. Copying is safe; it never creates an independently valid authorization.
- Registry cleanup is by garbage collection: entries are weak references, so an entry vanishes when its object is collected. Verified by test (j6): issuing a context, dropping the only reference, and collecting leaves the registry size unchanged — no leak.

### TASK C — Issuance verification at every authorization boundary

Consumer audit (all consumers of a `TrustedAuthorizationContext` in the repo):

| Consumer | Location | Before | After |
|---|---|---|---|
| `validate_private_voice_export()` (export, incl. `to_provider=True` provider-transmission approval) | `scripts/asset_policy.py` | bare `isinstance` | `is_factory_issued_trusted_authorization_context()`; a non-issued context is rejected with an explicit "was not issued by `issue_trusted_authorization_context()`" error |
| `revoke_trusted_authorization_context()` | `scripts/asset_policy.py` | bare `isinstance` | issuance verified; a forged/copy/deserialized object raises `TypeError` and can never revoke (or un-revoke) anything — a stolen `authorization_id` alone cannot revoke a genuine context |
| `is_trusted_authorization_revoked()` | `scripts/asset_policy.py` | bare `isinstance` | issuance verified; a non-issued object raises `TypeError` (fail closed — never reported as "not revoked") |
| `_is_authorization_revoked()` (internal helper) | `scripts/asset_policy.py` | id-membership read | unchanged in behaviour; only ever called on a factory-issued context (the caller verifies issuance first); it confers no authority by itself |
| `resolve_voice_for_production()` | `scripts/asset_policy.py` | — | does NOT consume a context (requester identity + `authorize_action`); no change needed, recorded here so the audit is complete |
| `authorize_action()` / timeline validation (`scripts/timeline_policy.py`) | `scripts/asset_policy.py`, `scripts/timeline_policy.py` | — | do NOT consume a context; no change needed, recorded here so the audit is complete |
| `scripts/generate-build-report.py:668` | — | — | mentions the class only in report text; not a consumer |

A forged context is rejected with a clear, actionable authorization error, never silently treated as valid. No check was replaced with a weaker `isinstance` condition.

### TASK D — Immutability and revocation preserved (P0-009)

- All P0-009 immutability behaviour is preserved: every security-sensitive field (`voice_profile_id`, `character_id`, `actor_owner_id`, `actor_workspace_id`, `action`, `provider_transmission_approved`, `scope`, `granted_by`, `expires_at`, `revoked`, `authorization_id`) is unassignable after issuance; new attributes cannot be added; fields cannot be deleted; there is no `__dict__` escape; `dataclasses.replace` still raises `TypeError`.
- Revocation remains separate from the immutable context: revoking never mutates the issued context (not even its `revoked` field); a revoked context is rejected by the export authorization; an unrevoked factory-issued context continues to work for its authorized scope; a revoked context cannot be restored as valid through copying (the copy shares the revoked `authorization_id`) or serialization (serialization is refused outright); a forged context cannot be made valid by setting a `revoked` attribute (the object is frozen — reassignment raises — and it is unregistered in any case).
- One P0-009 test assertion changed by design, not by weakening: group (h) check h6 previously asserted that a *pickle round-trip* of an issued context returns a frozen clone. Pickle is now refused outright, so h6 now covers copy/deepcopy only; the pickle refusal is pinned by group (j) checks j17–j19, which assert the `TypeError` and prove nothing was registered by the failed attempts. No test was removed; no other existing assertion was weakened.

## 4. Negative-control evidence (reproduced, labelled)

Reproduction script: `~/workspace/consistency-frame-p0-delivery/p0-010-repro.py` (saved outside the repo). It builds five forged contexts with **zero factory calls** and submits each to the real production `validate_private_voice_export`, plus a genuine factory-issued control.

**Before the fix** (`p0-010-repro-before.txt`):

```text
factory_calls=0
1. direct constructor + sentinel: is_trusted_context=True authorization_result=[]
2. __new__ + __setstate__: is_trusted_context=True authorization_result=[]
3. __new__ + object.__setattr__: is_trusted_context=True authorization_result=[]
4. pickle round-trip of forged context: is_trusted_context=True authorization_result=[]
5a. copy.copy of forged context: is_trusted_context=True authorization_result=[]
5b. copy.deepcopy of forged context: is_trusted_context=True authorization_result=[]
6. genuine factory-issued context (control): is_trusted_context=True authorization_result=[]
```

Every forged path was accepted (`[]` = export allowed) with `factory_calls=0` — the vulnerability exactly as independently reproduced.

**After the fix** (`p0-010-repro-after.txt`):

```text
factory_calls=0
1. direct constructor + sentinel: is_trusted_context=True authorization_result=['private voice export blocked: authorization context was not issued by issue_trusted_authorization_context() — only the exact context object issued by the local application authorization boundary is accepted; ...']
2. __setstate__ raised TypeError: TrustedAuthorizationContext cannot be restored from serialized state — only issue_trusted_authorization_context() may create a trusted authorization context
3. __new__ + object.__setattr__: is_trusted_context=True authorization_result=['private voice export blocked: ... was not issued by issue_trusted_authorization_context() ...']
4. pickle round-trip raised TypeError: TrustedAuthorizationContext cannot be pickled — an authorization context is process-local issuance state, not transferable data (issue a new context at the authorization boundary instead)
5a. copy.copy of forged context: is_trusted_context=True authorization_result=['private voice export blocked: ... was not issued ...']
5b. copy.deepcopy of forged context: is_trusted_context=True authorization_result=['private voice export blocked: ... was not issued ...']
6. genuine factory-issued context (control): is_trusted_context=True authorization_result=[]
```

All five forged paths are rejected (the forged object still *is* an instance of the class — `is_trusted_context=True` — which is precisely why type alone was never proof); the genuine factory-issued control still authorizes (`[]`). Additional identity checks run during verification: two contexts with identical fields are distinct objects (`a is not b`, `a != b`, `hash(a) != hash(b)`); the registry holds 2 entries while both live and 0 after both are dropped and collected (no leak).

## 5. Tests executed — exact counts

New regression group **(j)** in `tests/test_private_voice_security.py`, IDs `CF-P0-010-SEC(j1)`–`(j29)`:

- **(j) A — genuine issuance:** j1 factory context recognized as issued; j2 two identical-field contexts independently recognized, distinct objects, unequal, different hashes, distinct ids; j3 registry grows by exactly two for two fresh issuances (identical fields not merged); j4 genuine context still authorizes export; j5 legitimate provider-transmission authorization still works; j6 registry cleanup — no leak after drop + GC.
- **(j) B — direct constructor:** j7 sentinel construction creates an object but not a factory-issued context; j8 export rejects it with a clear not-issued error; j9 it cannot revoke and its revocation state cannot be read (both raise `TypeError`); j10 constructing with the sentinel registers nothing (registry size unchanged); j11 rejected by every other relevant consumer (provider-transmission export, revocation functions).
- **(j) C — `__new__` / `__setstate__`:** j12 `__new__` alone is not issued and export rejects; j13 `__setstate__` with genuine-looking fields raises `TypeError` and registers nothing; j14 `__setstate__` on a genuine context raises `TypeError` and the genuine context stays issued and still authorizes; j15 a `__new__` instance populated slot-by-slot (frozen, genuine-looking) remains untrusted; j16 every malformed `__setstate__` call (`None`, `("only-one",)`, `{}`, `(None, None)`, `(None, {"scope": "forged"})`) raises `TypeError`.
- **(j) D — pickle and copy:** j17 `pickle.dumps` of a genuine context raises `TypeError`; j18 same for a forged context; j19 `__getstate__` and `__reduce_ex__` raise `TypeError`, the genuine context still authorizes, nothing new was registered; j20 `copy.copy` returns a frozen value-identical but unregistered clone that export rejects; j21 same for `copy.deepcopy`; j22 copying cannot reset revocation (copy shares the revoked id; original and copy both rejected); j23 a forged context cannot be made valid by setting `revoked` (frozen — reassignment raises — and export still rejects).
- **(j) E — immutability/identity:** j24 identity equality pinned (forged object with identical fields does not equal the genuine one, is not in the registry, hashes differently); j25 revocation never mutates any object (revoking the original leaves the copy's fields, including `revoked=False`, untouched while the original is reported revoked).
- **(j) F — consumer matrices:** j26 export matrix (genuine / forged-sentinel / `__new__`-only / populated-`__new__` / copy / deepcopy / revoked — only genuine accepted); j27 revocation matrix (revoke accepts only a factory-issued context); j28 revocation-check matrix (answers only for a factory-issued context, `False` when unrevoked, `TypeError` otherwise).
- **(j) G — regression pins:** j29 v2.5 resolution without a Character Registry still fails closed and the strict timeline default still rejects a no-requester private dialogue timeline.

Full suite (`bash tests/run-tests.sh`, run **twice** at final state, exit 0 both times): **49 recorded entries, ALL PASS; 37 distinct test IDs; 30 distinct command strings; 0 failures, 0 skipped.** `tests/last-run.json` SHA-256 `cdb305693d7a29525181892ca1ff10d5ea65a4ddc607e4bd2658b08d832921e8` — byte-identical to the P0-008/P0-009 file, which is expected: the runner records per-file/per-command PASS/FAIL, not per-check counts (stated explicitly in the P0-009 corrections record §5 and the final report §11, so it is not mistaken for a stale file).

Per-file PASS counts (verified by running each file): `validate-repo.py` PASS; `generate-registries.py --check` OK (15/165/13/12); `test_schemas.py` 91; `test_routing.py` 305; `test_registries.py` 261; `test_performance_semantics.py` 32; `test_character_registration.py` 142 (0 skipped); `test_production_direction.py` 132; `test_private_overlay.py` 28; `test_timeline_manifest.py` 58; `test_private_voice_security.py` **142** (was 114; +28 net — 29 new (j) checks minus the 1 pickle branch removed from h6); `test_modes.py` 32; `test_reports.py` 37. Per-file PASS lines total: **1,260** (was 1,232).

Other checks: `bash -n` on `scripts/sync-skills.sh`, `setup.sh`, `tests/run-tests.sh` — OK; `git diff --check` clean; `setup.sh --dry-run` exit 0 (core-only; `--with-components` NOT run, as always).

## 6. Files changed

| File | Purpose |
|---|---|
| `scripts/asset_policy.py` | TASK A–D: issuance registry (`_ISSUED_AUTHORIZATION_CONTEXTS`, `weakref.WeakSet`); `is_factory_issued_trusted_authorization_context()` single verification function; identity `__eq__`/`__hash__`; `"__weakref__"` slot + `_DATA_SLOTS`; `__getstate__`/`__setstate__`/`__reduce__`/`__reduce_ex__` raise `TypeError`; copies return frozen unregistered clones; factory registers as its last step; issuance verified in export, revoke, and revocation-check consumers |
| `tests/test_private_voice_security.py` | New group (j), CF-P0-010-SEC j1–j29; h6 updated (pickle branch removed — pickle is now refused, pinned by j17–j19); module docstring records the (j) group and the reproduction script |
| `docs/implementation/CF-WO-P0-010-corrections.md` | This record |
| `CHANGELOG.md` | `[Unreleased]` entry for P0-010 |
| `AGENTS.md` | P0-010 section (repo agent instructions) |
| `docs/07-character-registry.md` | Owner-bound export now described as issuance-verified, not type-checked |
| `docs/architecture/ANIMATION_SCOPE_AND_PRODUCTION_MODES.md` | P0-010 issuance note added to the ownership/export passage |
| `docs/implementation/BUILD_REPORT_P0.md`, `build-report.json`, `CHECKSUMS.txt`, `release-manifest.json`, `docs/architecture/living-architecture-report-v2.4-p0.md` | Regenerated provenance (see §7) |

## 7. Provenance

Regenerated with `scripts/generate-build-report.py --github-head 5e3e3c38b91d6529bfe11ac7e1156a46f29ae203` (the remote head at order start — no push happens in this phase; the parent regenerates after pushing) and `scripts/generate-report.py`, after the last full-suite run. The figures quoted here are from the regeneration run before the final docs freeze; the final figures are in `BUILD_REPORT_P0.md` §12 (see below).

- Manifest: commit `191abf6` (code head), github_branch_head `5e3e3c38`, **156 files, 0 mismatches vs working tree** (verified after regeneration).
- Manifest SHA-256: `0f233a54ee90e4a58570a1e54ae8dab361388ccd7fa0dcfc31682ab78e39d0dd` (regeneration run before the final docs freeze).
- Build-report SHA-256: `eb83871e37f55395424db9ada0afa51117458e32dbbbb46d7622966a7797793c` (same run).
- BUILD_REPORT_P0.md SHA-256: `fa70109fa4672b111daffd707c20fc78f94745630cd7d0ba5e48f3c15d9f6842` (same run).
- CHECKSUMS.txt: 3/3 OK.
- Note on generator order: `scripts/generate-report.py` writes the living report, and `scripts/generate-build-report.py` writes it too — the build-report generator must run LAST, otherwise the living report's timestamp changes after the manifest is written and the manifest shows a mismatch. Verified: running the build-report generator last yields 0 mismatches.

## 8. Remaining limitations + unresolved decisions

- **Factory issuance is not authenticated identity.** This round proves an object was issued by the factory *in this process*; it does not prove the owner/workspace identifiers supplied to the factory belong to the real person operating the application. Actual trusted application-session identity establishment remains P1.
- **The issuance registry is process-local and in-memory.** A restart clears it (and the revocation registry); contexts must be re-issued. Persistence of revocations is P1.
- **No cryptographic proof, no OS isolation, no same-process protection.** Module-private variables and naming conventions are not cryptographic secrets and are not described as such. The P0 contract does not stop malicious code running with the same Python process privileges (or the same local OS user privileges) from manipulating files, code, or process memory — including the registry itself.
- **No new schema added** (a schema would falsely suggest an authenticated runtime exists).
- Count reconciliation (109/120 vs 165) remains deferred to P1, as before.

## 9. P0 vs P1 separation (explicit)

P0-010 is a policy / validation / tests / documentation round. It does not build an authenticated end-user app session, first-run registration UI, provider execution, or any P1 runtime. It does not add a server, API backend, cloud database, cloud identity service, or deployment. VoiceStudio / OpenMontage code was not modified.

## 10. ADRs (decisions taken this round)

1. **Identity registry, not a stronger constructor guard.** A private sentinel can always be imported from a Python module, so no constructor-side secret can prove issuance. The registry of exact issued objects is the only mechanism that survives `__new__`, `__setstate__`, pickle, and copy — because none of those paths can add an entry.
2. **WeakSet, not a strong set.** A strong set of issued contexts would pin every issued context in memory forever (a leak in a long-running process). A `WeakSet` drops entries when their objects are collected; test j6 proves it. This required the `"__weakref__"` slot and explicit identity equality/hash.
3. **Refuse serialization outright.** There is no architectural requirement for a serialized trusted context, so `pickle`/`__getstate__`/`__setstate__` raise instead of producing a "safe" serialized form that something might later trust. Loud failure beats a plausible-looking bypass.
4. **Copies are frozen but unregistered, not exceptions.** Copying is a common defensive operation; raising on copy would break callers that copy defensively, while an unregistered clone is harmless — it looks identical but has no authority. The revocation id is preserved in the clone so copying can never reset revocation state.
5. **Revocation functions verify issuance too.** A forged object carrying a stolen `authorization_id` could otherwise revoke a genuine context. Revoke / revocation-check now raise `TypeError` for anything not factory-issued.
6. **One existing assertion updated, none removed.** h6's pickle branch moved to group (j) as a refusal assertion (j17–j19). The security property — "copying cannot manufacture authority" — is now tested directly, not through an implementation detail.

## 11. Not addressed / out of scope

- Authenticated application-session identity (P1).
- Revocation persistence across restarts (P1).
- First-run registration UI, image upload / reference retrieval, voice recording / AI-voice creation-approval interfaces, reusable per-character voice generation (P1).
- Real image/video provider execution, image-to-video / video-to-video, lip-sync / beak-muzzle articulation generation, facial/body animation, camera-motion/focus generation, VoiceStudio / OpenMontage execution handoffs, full script-to-finished-video runtime (P1).
- No server, API backend, cloud database, cloud identity service, or deployment was added.
