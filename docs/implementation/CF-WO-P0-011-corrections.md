# CF-WO-P0-011 Corrections — Exact Object Identity Verification, Subclass Spoofing Protection & Authorization Regression

**Work order:** CF-WO-P0-011 (independent-review follow-up to P0-010)
**Branch:** `feat/cf-p0-safe-foundations` — PR #1, NOT merged
**Base (P0-010 docs head):** `e35fcb6`
**Remote head at order start (verified live):** `15c82c9643d583ff9c95d069a4403e01ff32d84b`
**Date:** 2026-11-23

---

## 1. What existed (P0-010 state)

- `TrustedAuthorizationContext` (`scripts/asset_policy.py`) was genuinely immutable after issuance (P0-009) and only factory-issued objects were accepted (P0-010).
- The issuance registry was `_ISSUED_AUTHORIZATION_CONTEXTS`, a `weakref.WeakSet` (`scripts/asset_policy.py`). Registration happened only inside `issue_trusted_authorization_context()`, as its last step.
- The verification function `is_factory_issued_trusted_authorization_context(context)` returned True when the argument `isinstance(...)` of the class **and** was a member of the WeakSet.
- The class had explicit identity equality/hash semantics (`__eq__` is `is`, `__hash__` is `object.__hash__`), and the constructor sentinel, `__setstate__` refusal, pickle refusal, and copy-non-registration from P0-009/P0-010 all stood.
- The verifier was used at every authorization boundary: `validate_private_voice_export` (including provider-transmission approval via `to_provider=True`), `revoke_trusted_authorization_context`, and `is_trusted_authorization_revoked`.

## 2. What was contradictory / missing

1. **A `WeakSet` membership test is an equality test (Task B).** Membership in a set is computed by hashing the candidate and comparing it with `==` against stored members. The P0-010 verifier therefore ran untrusted code — the candidate's `__hash__` and `__eq__` — and trusted their answers. A forged subclass of `TrustedAuthorizationContext` that overrides `__eq__` to always return True and `__hash__` to return the genuine object's hash compares equal to a genuine issued context and passes the check, with **zero** factory calls. The class's own identity `__eq__` does not help: the candidate's overridden `__eq__` is the one Python calls during the set lookup.
2. **A hostile `__eq__` was also a denial-of-service vector.** Before the fix, a spoof whose `__eq__` raised `RuntimeError` made the verifier itself raise `RuntimeError('untrusted equality executed')` — verification executed untrusted code and could be crashed from inside the check.
3. **`isinstance` admitted subclasses by definition.** A subclass instance passes `isinstance`, so the type half of the P0-010 check accepted exactly the objects the attack uses. The verifier had no exact-type requirement.
4. **No subclass prohibition existed.** Nothing stopped a subclass of the context from being defined at all.

## 3. What changed

### TASK A — Exact concrete type enforcement

- The verifier now requires `type(context) is TrustedAuthorizationContext` as its first check. Any subclass instance — however it was built, however faithfully it mimics the genuine object — is rejected before any registry lookup.
- `TrustedAuthorizationContext.__init_subclass__` is added: defining a subclass raises `TypeError("TrustedAuthorizationContext cannot be subclassed …")`. This is defence-in-depth only and is **never** the trust anchor: the verifier independently enforces exact type, so a subclass built through unusual or low-level mechanisms (the test fixture builds one via `type()` with the prohibition temporarily neutralized) is still rejected.

### TASK B — Identity verification, no equality anywhere in the registry

- The registry is replaced: `_ISSUED_AUTHORIZATION_CONTEXTS` is now a plain `dict[int, weakref.ref]` keyed by `id()` of the issued object, values are weak references to the issued objects. The weak-reference weakref itself is never consulted for equality: a set of weakrefs would reintroduce the hole, because a `weakref`'s own `__eq__`/`__hash__` delegate to its referent.
- The verifier (`is_factory_issued_trusted_authorization_context`):
  1. `type(context) is not TrustedAuthorizationContext` → False.
  2. `ref = registry.get(id(context))` — a dict keyed by ints, so the lookup itself invokes no candidate method.
  3. `ref is None` → False.
  4. `target = ref()` — if the weak reference is dead, the stale entry is pruned (only if the stored value is still that exact ref object) and the check returns False.
  5. `return target is context` — the only identity test, `is`, never `==`.
- An `id()` lookup alone is never proof: the target weak reference must still point at the exact object. No equality or hash is used as an identity substitute anywhere in the registry path.
- Registration remains factory-only and remains the last step of `issue_trusted_authorization_context()`, via the single registration path `_register_issued_context(context)`. The factory still registers exactly the object it constructed; a failed construction never leaves a partially issued object registered.

**Cleanup / id-reuse design.** Each stored weak reference carries a callback that removes the entry when the object is garbage-collected. The callback removes an entry **only if the stored value is still that exact (now dead) ref object** (`_drop_issued_context(key, ref)` checks `registry.get(key) is ref` before deleting). This matters because Python reuses `id()` values after an object is collected: a newer registration could legitimately reuse the same integer key, and an old dead callback must never delete the new entry. The same guard protects the verifier's prune step. Both behaviours are pinned by tests (k12, k13). Entries vanish when their objects are garbage-collected (no leak — verified by test k11).

### TASK C — The same central verifier at every authorization boundary

- Every consumer calls `is_factory_issued_trusted_authorization_context()` and no authorization-sensitive path performs a bare `isinstance`. The consumers audited and unchanged in their use of the verifier are `validate_private_voice_export` (including provider-transmission approval via `to_provider=True`), `revoke_trusted_authorization_context`, and `is_trusted_authorization_revoked`. `resolve_voice_for_production`, `authorize_action`, and timeline validation do not consume a context and needed no change (see the audit table in §6).
- Forged contexts are rejected with the existing clear error ("was not issued by `issue_trusted_authorization_context()`"), fail closed, and are never silently downgraded.

### TASK D — Hostile subclasses are irrelevant

- Verification never invokes a candidate's `__eq__` or `__hash__`: the exact-type check runs first (a subclass is rejected before the registry is consulted), and the registry lookup is an int-keyed dict lookup followed by an `is` comparison. Always-True `__eq__`, raising `__eq__`, genuine-hash `__hash__`, constant hash, inconsistent eq/hash, and multiple equal subclasses are all rejected with False / a clear error, without granting authorization, mutating or revoking the genuine context, corrupting the registry, or raising an unhandled exception. Pinned by tests k3–k8, k15.
- The base class's `__eq__` (`is`) / `__hash__` (`object.__hash__`) are unchanged.

### TASK E — P0-009 + P0-010 preserved

- Immutability, separate revocation, serialization refusal, and copy non-registration are unchanged and re-pinned (k16, plus all of groups (h)/(i)/(j) still passing).
- Revoking one issued context never revokes another with matching fields: revocation is keyed by the immutable per-issuance `authorization_id`, and the revocation functions themselves enforce exact type + factory issuance, so a forged subclass cannot revoke a genuine context or inspect its revocation status via a stolen `authorization_id` (k9, k15).
- A second genuine context with identical field values remains a separate issued object (k9). Same field values, same `authorization_id`, or a matching hash never substitute for exact object identity (k10, k3–k5).
- Both registries (issuance and revocation) are process-local and reset on restart; no persistence is claimed and no authenticated identity is claimed (§8).

## 4. Negative-control evidence (reproduced, labelled)

Reproduction script: `~/workspace/consistency-frame-p0-delivery/p0-011-repro.py` (outside the repo). It creates a genuine factory context, then a spoof subclass built without the factory (low-level construction via `type()` so the repro exercises the verifier, not just the subclass prohibition), overriding `__eq__` (always True) and `__hash__` (the genuine object's hash), plus a second spoof whose `__eq__` raises `RuntimeError`.

**Before the fix** (`p0-011-repro-before.txt`, regenerated against the pre-fix code with the same script version via `git stash`):

```
genuine factory context: created (factory_calls=1)
plain subclass definition: ALLOWED (no prohibition)
spoof subclass: created without factory (low-level construction)
isinstance(spoof, TrustedAuthorizationContext): True
type(spoof) is TrustedAuthorizationContext: False
spoof == genuine: True
hash(spoof) == hash(genuine): True
is_factory_issued(spoof): True
validate_private_voice_export(spoof): []
validate_private_voice_export(genuine): []
is_factory_issued(raising-eq spoof): RAISED RuntimeError('untrusted equality executed')
  (verification invoked untrusted __eq__)
factory_calls for spoof: 0
RESULT: SUBCLASS SPOOF BYPASS REPRODUCED — forged subclass accepted as factory-issued
```

**After the fix** (`p0-011-repro-after.txt`, same script):

```
genuine factory context: created (factory_calls=1)
plain subclass definition: raises TypeError (TrustedAuthorizationContext cannot be subclassed — only the ...)
spoof subclass: created without factory (low-level construction)
isinstance(spoof, TrustedAuthorizationContext): True
type(spoof) is TrustedAuthorizationContext: False
spoof == genuine: True
hash(spoof) == hash(genuine): True
is_factory_issued(spoof): False
validate_private_voice_export(spoof): ['private voice export blocked: authorization context was not issued by
  issue_trusted_authorization_context() — only the exact context object issued by the local application
  authorization boundary is accepted; a directly constructed, copied, deserialized or otherwise forged context
  never authorizes an export (type, field values and immutability alone prove nothing)']
validate_private_voice_export(genuine): []
is_factory_issued(raising-eq spoof, genuine hash): False (no exception — __eq__ never invoked)
factory_calls for spoof: 0
RESULT: SUBCLASS SPOOF BYPASS FIXED — forged subclass rejected, genuine context still authorizes
```

Note that `isinstance(spoof, TrustedAuthorizationContext)` is still True after the fix — that is expected and harmless: the verifier no longer trusts `isinstance`, and the exact-type check rejects the spoof before any registry lookup.

## 5. Tests executed — exact counts

- Focused: `python3 tests/test_private_voice_security.py` — **158 checks, 0 failures** (was 142 in P0-010; +16 from new group (k)).
- Focused: `test_timeline_manifest.py`, `test_character_registration.py`, `test_private_overlay.py`, `test_modes.py` — all PASS (0 failures).
- Full suite `bash tests/run-tests.sh` — run **twice** at final state: **49 recorded entries / 37 IDs / 30 commands, all PASS both times**.
- `tests/last-run.json` SHA-256: `cdb305693d7a29525181892ca1ff10d5ea65a4ddc607e4bd2658b08d832921e8` (identical after both runs; the file records runner-level per-file results only, so it hashes the same as in P0-008/P0-009/P0-010 — the new checks live inside existing test files, as before).

New group (k), `CF-P0-011-SEC`, in `tests/test_private_voice_security.py` (k1–k16):

- **(A) Exact type:** k1 factory-issued context recognized, exact type; k2 plain subclass definition raises TypeError; k3 always-equal spoof (genuine hash) rejected by verifier + export while genuine stays valid, registry untouched, revocation state unchanged.
- **(B) Equality/hash spoofing:** k4 constant-hash spoof rejected; k5 inconsistent eq/hash spoof rejected; k6 multiple mutually-equal spoofs all rejected, genuine unaffected.
- **(C) Equality never invoked:** k7 hostile raising `__eq__` (genuine hash) — verifier returns False with no exception and a call counter proves `__eq__` never ran; k8 the same hostile object through the real export consumer, no unhandled exception, still no `__eq__` call.
- **(D) Identity/duplicate values:** k9 two identical-field genuine contexts distinct, independently recognized, revoking one does not revoke the other; k10 unissued object with the same field values **and** the same `authorization_id` as a genuine context rejected.
- **(E) GC/weakref cleanup:** k11 deterministic (no sleeps) — dropped reference + `gc.collect()` returns the registry to its previous size, live context unaffected; k12 id-reuse guard — `_drop_issued_context` called with a dead ref under a live context's id never removes the live registration; k13 a stale dead entry met during verification is pruned and the check fails closed.
- **(F) Consumer matrix:** k14 export + provider-transmission accept only the genuine context and reject every spoof, the sentinel-forged object, and the revoked context; k15 a forged subclass cannot revoke a genuine context or inspect its revocation status (both raise TypeError, genuine stays unrevoked).
- **(G) Prior regression pins:** k16 sentinel construction unregistered, `__new__` unregistered, pickle refused, copy unregistered, fields immutable, revocation effective, genuine still authorizes.

Two earlier tests were updated by design (no test removed, no assertion weakened): j3 and j24 touched the registry directly (`reg in _ISSUED...`, `forged not in _ISSUED...`), which was valid for the WeakSet but meaningless for the new id-keyed dict — both now assert the same security property through the verifier (j3: two fresh issuances grow the registry by two and each is independently recognized; j24: no stored reference's target `is` the forged object). The property tested is unchanged; the mechanism assertion was replaced, as in P0-010's h6 update.

## 6. Files changed

- `scripts/asset_policy.py` — registry replaced with `dict[int, weakref.ref]`; `_drop_issued_context` / `_register_issued_context` added; verifier rewritten (exact type → int-keyed lookup → `is` comparison, with stale-entry pruning); `__init_subclass__` prohibition added; factory registration call updated; module/class docstrings and comments updated to describe the design and the id-reuse reasoning.
- `tests/test_private_voice_security.py` — header docstring (group (k) description), `_define_spoof_subclass` fixture, j3/j24 mechanism updates (see §5), group (k) k1–k16; `import weakref` added. 142 → 158 checks.
- `docs/implementation/CF-WO-P0-011-corrections.md` — this record.
- `docs/07-character-registry.md` — authorization-model passage extended with the P0-011 exact-type + identity-registry rule.
- `CHANGELOG.md` — [Unreleased] P0-011 entry.
- `AGENTS.md` — P0-011 section added (and the P0-010 section's WeakSet description updated to the new registry).
- `docs/implementation/BUILD_REPORT_P0.md`, `build-report.json`, `CHECKSUMS.txt`, `release-manifest.json`, living architecture/security reports — regenerated via the repo's own scripts (`scripts/generate-report.py` first, `scripts/generate-build-report.py` last, manifest regenerated after the final suite run — see §7).

### Per-consumer audit table

| Consumer / path | Verifier used | P0-011 change | Result |
|---|---|---|---|
| `validate_private_voice_export` (incl. `to_provider=True`) | `is_factory_issued_trusted_authorization_context` | None needed — verifier itself now enforces exact type + identity | Genuine only; spoof / exact-forged / revoked rejected with a clear error |
| `revoke_trusted_authorization_context` | same | None needed — verifier itself | Forged subclass raises `TypeError`; cannot revoke a genuine context |
| `is_trusted_authorization_revoked` | same | None needed — verifier itself | Forged subclass raises `TypeError`; cannot inspect genuine revocation status |
| `resolve_voice_for_production` | does not consume a context (requester identity + `authorize_action`) | None | No change |
| `authorize_action` | does not consume a context | None | No change |
| Timeline validation (`validate_timeline_cross_references`, `validate_timeline_structural`) | does not consume a context | None | No change |

## 7. Provenance

- **Order lesson (from P0-010 corrections §7):** `scripts/generate-report.py` and `scripts/generate-build-report.py` both write the living report — `generate-report.py` ran FIRST, `generate-build-report.py` LAST, and the manifest was regenerated AFTER the final suite run (the suite rewrites the living report's timestamp), then verified at 0 mismatches.
- `scripts/generate-report.py` — run with `--github-head 15c82c9643d583ff9c95d069a4403e01ff32d84b` (current remote head; no push in this phase).
- `scripts/generate-build-report.py` — run last with `--github-head 15c82c9643d583ff9c95d069a4403e01ff32d84b`.
- Manifest: **157 files, 0 mismatches vs working tree** (verified after regeneration by re-hashing every listed file). `github_branch_head` `15c82c96`, generation-time local head `e35fcb6` (the commit recorded in the manifest is the pre-P0-011-commit head; the parent regenerates after pushing).
- Manifest SHA-256: `1eb20036ae5dcbc3041e4e649ace58e6bc54a90a719b1a4844b35b751ed48acc` (regeneration run before the final docs freeze).
- Build-report SHA-256: `a748573d800b3a4334a36249634ba1a2c51223582bb6285c6b91c43b0ce6b4e8` (same run).
- BUILD_REPORT_P0.md SHA-256: `8e759d57073242a5611fcc7009a14452b0aa4bfe6dc5362f830172d4ff2bfbb8` (same run).
- CHECKSUMS.txt: 3/3 OK.
- Note on generator order: `scripts/generate-report.py` writes the living report, and `scripts/generate-build-report.py` writes it too — the build-report generator must run LAST, otherwise the living report's timestamp changes after the manifest is written and the manifest shows a mismatch. Verified: running the build-report generator last yields 0 mismatches.
- `scripts/validate-repo.py` — PASS.
- `git diff --check` — clean. No shell script was changed this round, so no `bash -n` run was needed. `bash setup.sh --dry-run` (core-only; `--with-components` NOT run, as always) — PASS.

## 8. Remaining limitations + unresolved decisions

- The registries are process-local and reset on restart; they are not a cryptographic secret, not OS isolation, and offer no protection against hostile same-process code — an attacker who can run code inside the same process can call the factory directly. This is the same boundary as P0-009/P0-010.
- Authenticated application-session identity remains P1; the context is a structural (type + identity) boundary, not cryptographic proof of identity.
- The subclass prohibition (`__init_subclass__`) is defence-in-depth only; the verifier's exact-type check is the trust anchor. A subclass built by low-level means is still rejected by the verifier (proven by the fixture-based tests, not just by class-definition failure).
- The verifier's stale-entry prune only fires when a dead weak reference is met during a check; in normal CPython execution the weak-reference callback removes dead entries at collection time, so the prune is a defensive second path.

## 9. P0 vs P1 separation (explicit)

- P0: exact object identity for authorization issuance, subclass spoofing protection, hostile-equality irrelevance, GC cleanup, per-consumer verification, regression protection. No P1 runtime started, no server/API/cloud database/hosted identity involved, no VoiceStudio/OpenMontage change, no private media in the public repo.
- P1 (unchanged): authenticated session identity, persistence of authorization state, routing engine runtime, script-to-performance runtime, adapter conformance tests, count reconciliation (165 vs 109/120).

## 10. ADRs (decisions taken this round)

- **ADR-1: `id()`-keyed dict of weakrefs, not an iterated weakref collection.** Both designs satisfy "verify with `is`, never `==`". The dict was chosen because it is the easiest to audit and prove correct: the lookup is a single int-keyed `dict.get`, the only identity test is one `is`, and the cleanup/id-reuse guard is a single `is`-comparison in `_drop_issued_context`. An iterated collection would need the same guard per element and a linear scan per verification.
- **ADR-2: `__init_subclass__` prohibition is defence-in-depth, never the trust anchor.** The verifier enforces exact type independently, because a prohibition on the normal class-definition path says nothing about low-level construction. Tests prove the verifier rejects a subclass built by deliberate low-level construction.
- **ADR-3: j3/j24 mechanism assertions updated, property assertions kept.** The P0-010 tests asserted a WeakSet membership property directly; the new registry cannot be tested that way (a dict's `in` tests int keys). The tests now assert the same security property through the verifier, following the P0-010 h6 precedent.

## 11. Not addressed / out of scope

- No change to VoiceStudio/OpenMontage. No change to `resolve_voice_for_production`, `authorize_action`, or timeline validation. No persistence, no authenticated identity, no cryptographic proof. P0-010 history is preserved — this record does not rewrite its evidence; the P0-010 WeakSet was the correct step for its threat (forged objects with zero factory calls), and this round closes the residual equality-based hole it left.
