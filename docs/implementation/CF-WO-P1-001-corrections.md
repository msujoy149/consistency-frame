# CF-WO-P1-001 Corrections — Trusted Local Application Session & Authorization Runtime

## 1. What existed (P0 state)

P0 provided the policy but no runtime to supply the actor:

- Structured private ownership (`owner_id`, `workspace_id`,
  `visibility`, `sharing`) on characters and voice profiles
  (P0-007).
- One authorization choke point,
  `scripts/asset_policy.py::authorize_action`, with explicit
  action scopes (`use_in_project`, `use_in_production`,
  `export_private_asset`, `transmit_to_provider`,
  `share_with_workspace`) (P0-008).
- A factory-issued, genuinely immutable
  `TrustedAuthorizationContext`, verified by exact concrete type
  plus an `id()`-keyed weak-reference registry checked with `is`
  (P0-009/010/011), with separate revocation and serialization
  refusal.
- `resolve_private_path` (traversal / symlink-escape rejection)
  and `atomic_write.py` (unguessable-tempfile atomic writes)
  (P0-003/008).

What P0 did NOT provide: any local identity, any application
session, or any code that turns "the owner, operating the
application" into the `requesting_owner_id` /
`requesting_workspace_id` arguments those functions take. Any
in-process caller could pass any owner/workspace strings, and
`issue_trusted_authorization_context` trusted its arguments at
face value. The P0 docstrings said so explicitly ("the P1
app/session runtime must supply the actor identity at the
boundary"). There was also no first-run initialization, no local
storage story, and no session lifecycle at all.

## 2. What was missing / the gap

1. No stable local owner/workspace identity, and no defined
   place to keep it (the repo itself must never hold it).
2. No process-bound session: nothing distinguished "the
   application, running now, for this owner" from any caller
   with a string.
3. No bridge from a verified session to `authorize_action` —
   the identity arguments were caller-supplied everywhere.
4. No trusted issuance path for private-voice export: the P0
   factory existed, but nothing in the repo called it on behalf
   of a verified session after an explicit owner approval, bound
   it to a session, or revoked it when that session ended.
5. No storage-security rules for local runtime state (atomic
   writes, restrictive permissions, symlink/corruption handling
   for a profile file).

## 3. What changed

### 3.1 New package `runtime/` (stdlib only, no new dependencies)

**`runtime/__init__.py`** — package docstring only; no eager
imports.

**`runtime/local_session.py`** (Tasks A, B, E):

- `resolve_data_root(data_root=None)` — explicit override wins
  (it names the data root itself); otherwise Linux respects
  `XDG_DATA_HOME` (a relative value is invalid per the XDG spec
  and is ignored) else `~/.local/share`; macOS uses
  `~/Library/Application Support`; Windows requires
  `%LOCALAPPDATA%`. The application subdirectory is
  `consistency-frame` on every platform. There is no
  repository-local fallback anywhere in the resolution.
- `load_or_create_profile(data_root=None)` — first use generates
  two fresh opaque IDs (`secrets.token_hex(16)` — 32 lowercase
  hex chars, matching the P0 ownership ID pattern) and writes
  `{"schema_version": 1, "owner_id", "workspace_id"}` atomically
  (mode 0600) into a 0700 directory, re-reading and validating
  the written profile before returning it. Later use strictly
  validates the existing file: wrong type, missing or extra
  fields, wrong `schema_version` (including the boolean-`True`
  `== 1` trap — the check is `type(version) is int`), or a
  malformed ID raises `ProfileError` and the file is left
  untouched. A profile appearing between the existence check and
  the write (a concurrent first run) is loaded and returned
  instead of overwritten.
- `InstallationProfile` — a frozen, slotted dataclass
  (`owner_id`, `workspace_id`, `data_root`, `profile_path`) with
  `__post_init__` validation. It is data: its trust comes from
  being loaded and validated from the data root, not from its
  type (documented in the module docstring — in-process
  construction of profile data is outside the threat model,
  exactly as P0 assumes the calling process is trusted).
- `LocalSession` — the P0-009/010/011 rules applied to sessions:
  `__init_subclass__` raises `TypeError` (defence-in-depth);
  exact-type + `id()`-keyed weak-reference registry checked with
  `is`; `__eq__` is `is`; genuinely immutable after issuance
  (frozen flag, `__setattr__`/`__delattr__` raise, no `__dict__`);
  `__copy__`/`__deepcopy__` return frozen UNREGISTERED clones;
  `__reduce__`/`__reduce_ex__`/`__getstate__`/`__setstate__`
  raise `TypeError`.
- `start_session(profile, workspace_id, *,
  lifetime_seconds=43200)` — validates the profile object, the
  workspace ID (valid opaque ID AND equal to the profile's
  workspace — this installation holds exactly one workspace),
  and the lifetime (integer, 1..86400 seconds); mints a fresh
  `uuid.uuid4().hex` session ID; registers the session as the
  factory's last step. Sessions are never written to disk.
- `is_active_session(session)` — the single verifier: exact
  type, registry `is` check (with the P0-011 guarded dead-entry
  prune), not in the closed-session set, not expired. No
  candidate `__eq__`/`__hash__` is ever invoked.
- `validate_session(session)` — rejection reasons, never raises
  for hostile input; fields are read only after issuance is
  proved.
- `close_session(session)` — marks the session closed (keyed by
  the session ID string — a fresh uuid4 per session — never by
  `id()`, so no id-reuse hazard), then runs registered close
  handlers; the first handler exception is re-raised only after
  all handlers ran, and the session stays closed regardless.
  Closing is permanent; returns True on the call that closed it,
  False if already closed; raises `SessionError` for anything
  that is not an issued session.
- `register_session_close_handler(handler)` — the hook the
  authorization module uses for revocation on close.
- Storage safety reuses the P0 utilities: `atomic_write_json`
  for the profile write, `asset_policy.resolve_private_path`
  for the profile path. A symlinked data directory or profile
  file is refused outright; POSIX permission tightening is
  best-effort on filesystems without POSIX modes (documented).
- One deliberate import detail: the module puts the repo's
  `scripts/` directory on `sys.path` (derived from the file's
  own location, never the working directory) and then imports
  `asset_policy` normally — exactly as the P0 tests do — so the
  runtime shares the ONE module instance (and therefore the ONE
  issuance/revocation registry) with every other consumer. Two
  separately loaded copies of `asset_policy` would have two
  registries, and a context issued through one would fail
  verification through the other.

**`runtime/authorization.py`** (Tasks C, D):

- `authorize(session, action, ownership)` — returns rejection
  reasons (`[]` = allowed). The session must be active
  (`is_active_session`); owner/workspace come ONLY from it; the
  decision is delegated to
  `asset_policy.authorize_action`. There is deliberately no
  parameter for caller-provided identity.
- `request_voice_export_authorization(session, voice, *, scope,
  approve_callback, lifetime_seconds=300)` — validates the
  active session, the voice's structured ownership (owner-only:
  session owner AND workspace must equal the voice's), the exact
  Character/Voice binding, a non-empty scope, and a short finite
  lifetime (integer, 1..3600 seconds, default 300); requires an
  explicit owner approval through the callback; then calls the
  P0 factory with `provider_transmission_approved=False`
  (always — an export approval never sets it) and tracks the
  context against the issuing session (weak references only).
  Raises `ValueError` on every failure.
- `request_provider_transmission_authorization(...)` — the
  separate permission: identical requirements, its own distinct
  approval (the callback is invoked with action
  `"transmit_to_provider"`), and the only path that sets
  `provider_transmission_approved=True`.
- The approval callback protocol —
  `approve_callback(action, *, character_id, voice_profile_id,
  scope) -> bool` — is the narrow UI-confirmation seam. A
  falsy return, a non-callable, or a raising callback is treated
  as NO approval (fail closed). No full graphical UI is built
  or claimed.
- `_revoke_contexts_for_session`, registered as a session-close
  handler at import time: closing a session revokes every
  still-live context it issued (dead references skipped,
  revocation idempotent). `issued_contexts_for_session(session)`
  lists the still-live tracked contexts. Closing a session IS
  its shutdown. The handler only exists if this module has been
  imported — the application entry point must import
  `runtime.authorization` before closing sessions that issued
  contexts (documented in the module docstring and the runtime
  doc).

### 3.2 Tests (registered in `tests/run-tests.sh`)

- `tests/test_local_session_runtime.py` — 56 checks:
  CF-P1-001-PROF-01..19 (+01b, 04b, 12b), CF-P1-001-SESS-01..26,
  CF-P1-001-FS-01..07 (+04b).
- `tests/test_session_authorization.py` — 39 checks:
  CF-P1-001-AUTH-01..12, CF-P1-001-EXP-01..22 (+01b),
  CF-P1-001-P0-01..04.
- Registered as `CF-P1-001-SESSION` and `CF-P1-001-AUTHZ`.
  Isolated temp directories, synthetic IDs/assets only.

### 3.3 Documentation

- `docs/runtime/LOCAL_SESSION_AND_TRUST_BOUNDARY.md` — the
  guarantees (§ "What the boundary guarantees") and the honest
  non-guarantees (local OS-user boundary only; IDs are
  identifiers, not secrets; process-local revocation; no UI;
  one workspace; first-run race; Windows permission limits;
  platform coverage), data-root table, profile format, session
  lifecycle, module map, tests.
- `AGENTS.md` — P1-001 section (session runtime, trust
  boundary, what is still not built).
- `docs/07-character-registry.md` — a "Local application
  session (P1-001)" section after the P0-008 fail-closed
  section, pointing at the runtime doc.
- `CHANGELOG.md` — `[Unreleased]` P1-001 entry.

### 3.4 What did NOT change

- No `scripts/asset_policy.py`, `scripts/atomic_write.py`, or
  any P0 policy code was modified. No skill, schema, registry,
  or companion-internal file was modified.
- `tests/test_private_voice_security.py` is unmodified and
  still passes (158 checks) — the P0 behaviour pins in the new
  authz suite are additional, not replacements.
- No server, API backend, cloud database, cloud identity
  service, password manager, credential vault, or new
  dependency (stdlib only).

## 4. Negative-control evidence (reproduced, labelled)

The new suites are the negative control: they fail on the
pre-change code and pass after.

- **Before** (implementation moved aside, tests unchanged —
  evidence `p1-001-test-before-runtime.txt`,
  `p1-001-test-before-authz.txt` in the delivery folder):
  both test files exit 1 with
  `ModuleNotFoundError: No module named 'runtime'`.
- **After** (implementation restored): both files exit 0 —
  `test_local_session_runtime.py` 56 PASS / 0 FAIL,
  `test_session_authorization.py` 39 PASS / 0 FAIL.
- The suites also pin the fixed behaviour on the forged inputs
  directly (no separate repro script was needed — the checks
  themselves are the reproduction): a forged session object
  carrying a genuine session's field values is rejected
  (SESS-12, AUTH-06, EXP-20); a subclass spoof is rejected
  (SESS-11); copies and pickle are rejected (SESS-14..17);
  a caller-supplied identity override is a `TypeError`
  (AUTH-09); an export without approval issues nothing
  (EXP-02); a closed session's contexts validate as revoked
  (EXP-18).

## 5. Tests executed — exact counts

- `python3 tests/test_local_session_runtime.py` — exit 0,
  **56 PASS / 0 FAIL** (PROF 22, SESS 26, FS 8).
- `python3 tests/test_session_authorization.py` — exit 0,
  **39 PASS / 0 FAIL** (AUTH 12, EXP 23, P0 4).
- Full suite `bash tests/run-tests.sh` — **twice, exit 0 both
  times: 56 recorded entries / 43 distinct test IDs / 34
  distinct commands, 56 PASS, 0 FAIL, 0 SKIP** (was 54/41/32 —
  the two new entries add two IDs and two commands).
- Per-file PASS lines (recalculated, all 0 FAIL): 14 Python
  files total **1,399** (was 1,304 — the two new files add
  56 + 39 = 95; `test_private_voice_security.py` still 158,
  P0-011 protections intact; `test_reports.py` 47);
  `test_installer_status.sh` 61; `test_installer.sh` 40;
  `test_installer_security.sh` 15;
  `test_installer_manifest_security.sh` 24;
  `test_installer_metadata_failure.sh` 13.
- `tests/last-run.json` SHA-256
  `ddd94ee1502d77d22105ab6a6a5cc3a752bbdfe3e5c4d65eec7ff1c8b4e559c5`
  (changed from P0-015's `5f5db583…` because the entry set
  changed — expected). Both suite runs' `last-run.json` were
  byte-identical.
- `bash -n setup.sh` — exit 0. `python3
  scripts/validate-repo.py` — PASS. `python3
  scripts/generate-registries.py --check` — CHECK OK.
  `python3 scripts/generate-report.py --check` — CHECK OK (same
  `--github-head 8fc11fee` as generation). `python3
  tests/test_reports.py` — PASS (0 failures). `git diff
  --check` — clean. `bash setup.sh --dry-run` — exit 0
  (core-only).
- `bash setup.sh --with-components` — **NOT RUN** (unchanged
  standing limitation from P0; this round does not touch the
  installer).

## 6. Files changed

| File | Change |
|---|---|
| `runtime/__init__.py` | New. Package docstring; no eager imports. |
| `runtime/local_session.py` | New. Profile + data root + process-bound sessions (Tasks A, B, E). |
| `runtime/authorization.py` | New. Session bridge + trusted export issuance (Tasks C, D). |
| `tests/test_local_session_runtime.py` | New. 56 checks (PROF/SESS/FS). |
| `tests/test_session_authorization.py` | New. 39 checks (AUTH/EXP/P0). |
| `tests/run-tests.sh` | Two new entries (`CF-P1-001-SESSION`, `CF-P1-001-AUTHZ`). |
| `docs/runtime/LOCAL_SESSION_AND_TRUST_BOUNDARY.md` | New. Guarantees, non-guarantees, data roots, profile format, lifecycle. |
| `docs/implementation/CF-WO-P1-001-corrections.md` | New. This record. |
| `AGENTS.md` | P1-001 section added. |
| `docs/07-character-registry.md` | "Local application session (P1-001)" section added. |
| `CHANGELOG.md` | `[Unreleased]` P1-001 entry. |
| `docs/implementation/BUILD_REPORT_P0.md`, `build-report.json`, `CHECKSUMS.txt`, `release-manifest.json`, `docs/architecture/living-architecture-report-v2.4-p0.md` | Provenance regenerated (see §7). |
| `tests/last-run.json` | Suite record (56 entries; two new entries). |

Diff vs `c36bfaa` (P0-015 docs head): **17 files, +2,821/−54**.
Diff vs base `8fc11fee` (main): identical (17 files, +2,821/−54),
since the branch started at `c36bfaa` whose tree is main's tree
(verified byte-identical, 162/162 files, before work began).

## 7. Provenance

- Base: main `8fc11fee` ("Merge pull request #1 …", PR #1 merged
  2026-11-23). Branch `feat/cf-p1-001-trusted-session`, started at
  `c36bfaa`, whose tree was verified byte-identical to main's tree
  (162/162 files SHA-matched) before work began.
- Generator order (P0-010 lesson): `generate-report.py` first,
  `generate-build-report.py` last, both with
  `--github-head 8fc11fee` (current main head; nothing pushed
  yet); manifest regenerated AFTER the final suite run (the
  suite rewrites the living report); no suite run after that
  before commit.
- Pre-push manifest/build-report/checksums (generated after the
  final suite run, `--github-head 8fc11fee`): manifest SHA-256
  `24a948f7768bb307a7230f7d723bf67ee0e5e3af9b051db110d9dc15eb8d5c1e`
  (162 files, 0 mismatches; commit `c36bfaa`,
  github_branch_head `8fc11fee` — the new files enter the
  manifest in the post-push regeneration, once they are tracked);
  build-report SHA-256
  `824651501f73694027c727b274efed980626a6977d807b50886c97ac5e32bd10`;
  BUILD_REPORT_P0.md SHA-256
  `de587d8d2c65b40208d2dace97140daac9ef149221e35273f207e54afdc7b858`;
  CHECKSUMS.txt 3/3 OK.

## 8. Remaining limitations + unresolved decisions

- **This runtime is a local OS-user boundary only** (see the
  runtime doc § "What the boundary does NOT guarantee"). It does
  not stop another process running as the same OS user from
  reading the profile, importing this module, or rewriting the
  profile file. That is the documented design, not an oversight.
- **Revocation is process-local.** A restart clears the P0
  revocation registry; contexts must be re-issued. Persistent
  revocation across restarts is future work.
- **No approval UI exists.** Approval is a callback; nothing
  here renders a dialog or a registration screen. A callback
  that always returns True is a caller bug the runtime cannot
  detect — the runtime can only require that an approval was
  obtained through the seam, not that a human really saw a UI.
- **One workspace per installation.** Multi-workspace
  installations are not modelled; `start_session` refuses any
  workspace that is not the profile's.
- **First-run race.** Two processes initializing at the same
  instant can each generate an identity; the second write wins.
  Documented in the runtime doc; writes are atomic, so no
  half-written profile results. — CLOSED by R1, see §12: first-run
  publication is now an atomic create-if-absent operation and
  concurrent processes agree on one identity.
- **Windows permissions.** POSIX 0700/0600 bits have no
  equivalent enforcement on Windows; documented honestly.
- **Platform coverage.** Tests run on this Linux VM only.
  macOS/Windows data-root branches are exercised only with a
  patched platform probe, never on real macOS/Windows machines.
- **Session/owner IDs are identifiers, not secrets.** They must
  never be treated as credentials; the runtime never does.
- `setup.sh --with-components` remains NOT RUN (P0 standing
  limitation; untouched by this round).

## 9. P0 vs P1 separation (explicit)

- P1-001 builds the first runtime component (local session +
  authorization bridge). It does NOT build a graphical UI,
  character registration UI, voice/video generation, provider
  calls, the skill routing engine, script-to-performance
  generation, or the script-to-finished-video pipeline. None of
  those is marked implemented.
- P0 authorization behaviour is unchanged (the P0 security
  suite passes unmodified, plus four P0 pins in the new authz
  suite). The runtime adds a caller, not a second policy.
- No companion internals, cloud services, server infrastructure,
  or credential vaults are introduced.

## 10. ADRs (decisions taken this round)

1. **Session workspace must equal the profile's workspace.**
   The work order says the session binds to "the profile's
   owner ID and an explicitly selected valid workspace ID",
   while Task A generates exactly one workspace per
   installation. A session for a workspace the installation
   does not hold would let a caller invent workspace bindings,
   so `start_session` requires the explicitly passed workspace
   to equal the profile's. Multi-workspace support is a later
   decision, not a silent extension here.
2. **Close is shutdown; revocation is a close handler.** Rather
   than a second shutdown API, `close_session` is the single
   shutdown operation and the authorization module registers a
   close handler that revokes the session's contexts. This makes
   "shutdown revokes" hold no matter which module the caller
   uses — but it only holds if `runtime.authorization` has been
   imported (documented; the application entry point must import
   it). Contexts also expire on a short schedule, bounding the
   window if revocation were missed.
3. **Closed sessions are tracked by session ID string, not by
   `id()`.** The P0 revocation registry keys by
   `authorization_id` (a uuid) for the same reason: an `id()`
   can be reused after the object dies, but a session ID is
   never minted twice.
4. **Issuance raises; authorization decisions return error
   lists.** `authorize()` follows the P0 `authorize_action`
   convention (error list, `[]` = allowed) because a decision
   is a verdict. Issuance functions raise `ValueError` on any
   failure, mirroring the P0 factory — issuance either happens
   completely or not at all.
5. **The runtime imports the single shared `asset_policy`
   module instance** (sys.path insert derived from the file's
   location + normal import, the P0 tests' own pattern) because
   the P0 issuance/revocation registries are module globals. A
   second loaded copy would silently split the registries.
6. **Stricter ID validation at the runtime boundary.**
   `_is_valid_opaque_id` uses `fullmatch`, not the P0 layer's
   `search`, so a trailing newline or smuggled character can
   never pass at profile/session creation, even though the P0
   pattern's `$` anchor would accept it.
7. **Export lifetime capped at 1 hour (default 5 minutes),
   session lifetime capped at 24 hours (default 12).** "Short,
   finite expiry" is enforced, not just documented.
8. **A failing approval callback is NO approval** (the
   exception is not propagated). Issuance is refused and the
   caller learns only that approval was not obtained.

## 11. Not addressed / out of scope

- Full graphical application UI; character registration UI.
- Voice generation, speech synthesis, sound processing.
- Video generation, editing, rendering.
- Provider API calls or paid model calls.
- Full workflow/skill routing engine; script-to-performance
  generation; full script-to-finished-video pipeline.
- Multi-device or cloud identity synchronization.
- Changes to VoiceStudio or OpenMontage internals.
- Persistent (cross-restart) revocation.
- `setup.sh --with-components` end-to-end run.

## 12. R1 addendum (2026-11-23) — CF-WO-P1-001-R1

Two independently reproduced defects in the P1-001 code above,
fixed without redesigning the runtime and without changing any P0
policy code. Everything in §§1–11 stands as written; this section
only adds the R1 findings, fixes, tests and verification.

### 12.1 Finding R1-A — forged-session context enumeration

`runtime/authorization.py::issued_contexts_for_session()` checked
only `type(session) is local_session.LocalSession`. It did not
verify exact factory issuance or active-session status. A copied
`LocalSession` fails `is_active_session()` but could still
retrieve the original session's genuine authorization contexts
through this function — and the returned context passed P0's
private-voice export validator (`validate_private_voice_export`
returned `[]`).

Reproduced before the fix
(`~/workspace/consistency-frame-p1-delivery/p1-001-r1-repro-enum-before.txt`,
exit 1): `copy.copy(session)`, `copy.deepcopy(session)` and a
populated `object.__new__(LocalSession)` carrying the genuine
session ID each retrieved 1 context, usable for private export
(1/1). A different genuine session retrieved 0 (correct — it has
no contexts of its own).

### 12.2 Fix R1-A

`issued_contexts_for_session()` now requires
`local_session.is_active_session(session)` — the same exact-type
+ `id()`-keyed weak-reference registry check with `is` that the
bridge (`authorize`) and the issuance path (`_issue`) already
used — before reading `_SESSION_CONTEXTS`. Anything else raises
`ValueError`, the fail-closed error this function already used
for non-sessions. Missing, forged, copied, deep-copied,
`__new__`-built, expired and closed sessions are all refused;
the genuine active session that issued the contexts still
enumerates them. No P0 factory-issued context check was weakened
or replaced: the returned contexts are still filtered through
`is_factory_issued_trusted_authorization_context`, and the
session-close revocation handler is untouched.

One existing assertion changed by design: EXP-18 previously
expected `issued_contexts_for_session(closed_session) == []`
after shutdown; a closed session now raises `ValueError`
instead, so the check now expects the refusal (the
closed-session case is also pinned directly by ENUM-07). No test
was removed and no other assertion was weakened.

### 12.3 Finding R1-B — first-run profile race

`load_or_create_profile()` checked whether the profile exists
and then called `atomic_write_json()`, whose `os.replace()`
unconditionally overwrites the target. Two concurrent first-run
processes could each generate an identity and return different
owner/workspace IDs while only one identity persisted on disk.

Reproduced before the fix
(`~/workspace/consistency-frame-p1-delivery/p1-001-r1-repro-first-run-before.txt`,
exit 1): 4 processes released simultaneously by a barrier
against the same absent data root diverged in 11 of 12 rounds
(2–3 distinct identities per round; the persisted profile
matched one of the returned IDs, the others were lost).

### 12.4 Fix R1-B

First-run publication is now an atomic create-if-absent
operation, implemented in `runtime/local_session.py` as
`_publish_profile_atomic(path, payload)`:

- The candidate payload is written to an unguessable temporary
  file in the same directory (exclusive creation via
  `tempfile.mkstemp` — O_CREAT | O_EXCL — mode 0600, flushed +
  fsynced).
- It is published with `os.link()` — one atomic filesystem
  operation that FAILS with `FileExistsError` when the profile
  already exists, so it can never overwrite another process's
  profile. The temporary file is removed in a `finally` either
  way, so no artefact remains after a successful initialization.
- When the link fails with `FileExistsError`, the losing
  process discards its candidate and loads the winner's profile
  (re-read + strictly validated before it is returned). A
  corrupt winner fails closed and stays untouched; a symlinked
  profile is refused as before.
- A crash before the link leaves only a temporary file — never
  a partially written profile at the final path — so no process
  can read a half-written profile. The old check-then-write
  window (existence re-check before `atomic_write_json`) is
  gone: the link IS the atomic decision point.
- The P0 `scripts/atomic_write.py` helper was NOT modified and
  is no longer used for the profile at all: its `os.replace()`
  is exactly the overwrite this fix removes. The helper's own
  guarantees (and its tests) are unchanged. `local_session.py`
  no longer imports `atomic_write_json`.
- Failure behaviour: any other `OSError` during publication
  raises `ProfileError` with the previous profile (if any)
  untouched; a failed first-use write leaves no profile and no
  temporary file.

Portability note: `os.link()` (hard links) is available on
POSIX and on Windows NTFS. On a filesystem without hard-link
support the link raises `OSError` and first-run initialization
fails closed with `ProfileError` rather than silently falling
back to an overwriting write.

### 12.5 Regression tests

`tests/test_session_authorization.py` — new group
CF-P1-001-R1-ENUM (8 checks), placed between EXP-16 and EXP-17
so the genuine session is still active:

- ENUM-01: the genuine active session enumerates its own 4
  issued contexts.
- ENUM-02: `copy.copy(session)` cannot enumerate (ValueError).
- ENUM-03: `copy.deepcopy(session)` cannot enumerate (ValueError).
- ENUM-04: a populated `object.__new__(LocalSession)` with the
  genuine session ID cannot enumerate (ValueError).
- ENUM-05: a different genuine session enumerates only its own
  contexts — `[]`, none of the first session's.
- ENUM-06: an expired session cannot enumerate (ValueError).
- ENUM-07: a closed session cannot enumerate (ValueError) — the
  session first issues a context, so the refusal is about the
  closed state, not about having nothing to list.
- ENUM-08: no unissued session recovers any context at all, so
  nothing it holds can validate for private export or provider
  transmission; the other genuine session likewise recovers none
  of the first session's contexts.

`tests/test_local_session_runtime.py` — new group
CF-P1-001-R1-FIRST (7 checks), using a process pool (fork
context) with a barrier release so the workers hit first-run
initialization at the same instant; every wait and result
carries a 30-second timeout, no unbounded sleep race:

- FIRST-01: 5 rounds x 4 concurrent processes against a fresh
  absent data root — all return one shared identity.
- FIRST-02: the persisted profile holds exactly the returned
  identity.
- FIRST-03: no temporary file or lock artefact remains after
  successful initialization (directory listing is exactly
  `["profile.json"]`).
- FIRST-04/05: collision with an already existing valid profile
  — all processes return its identity and its bytes are
  unchanged.
- FIRST-06/07: collision with a corrupt profile — all processes
  fail closed with `ProfileError` and the corrupt bytes are
  untouched.

One existing test changed by design: FS-07 (first-use write
failure leaves no profile) now injects its failure at
`_publish_profile_atomic` instead of `atomic_write_json`, and
additionally asserts no artefact remains. The observable
behaviour it pins (ProfileError, no profile) is unchanged.

### 12.6 After-fix evidence

- `p1-001-r1-repro-enum-after.txt` (exit 0): copy, deepcopy and
  `__new__`-built objects refused with ValueError; the different
  genuine session retrieved 0; the genuine session still
  enumerates its context.
- `p1-001-r1-repro-first-run-after.txt` (exit 0): all 12 rounds
  agreed on one identity, persisted profile matched, no
  leftovers.
- `tests/test_session_authorization.py`: 39 → 47 PASS lines
  (exit 0). `tests/test_local_session_runtime.py`: 56 → 63 PASS
  lines (exit 0). `tests/test_private_voice_security.py`:
  158 checks, unmodified, PASS (exit 0).
- Full suite counts recalculated from the final
  `tests/last-run.json` — see §12.7.

### 12.7 Verification (R1 final state)

- `python3 tests/test_local_session_runtime.py` — exit 0, 63 PASS.
- `python3 tests/test_session_authorization.py` — exit 0, 47 PASS.
- `python3 tests/test_private_voice_security.py` — exit 0, 158 PASS.
- `bash tests/run-tests.sh` — twice, exit 0 both times:
  56 recorded entries / 43 distinct test IDs / 34 distinct
  commands, 56 PASS, 0 FAIL, 0 SKIP. (Entry counts unchanged
  from P1-001 — the 15 new checks live inside the same two
  test files.) Per-file PASS lines, one run each, all 0 FAIL:
  14 Python files total **1,414** (was 1,399; +7 runtime, +8
  authorization — `test_private_voice_security.py` 158
  unchanged, `test_reports.py` 47); `test_installer_status.sh`
  61; `test_installer.sh` 40; `test_installer_security.sh` 15;
  `test_installer_manifest_security.sh` 24;
  `test_installer_metadata_failure.sh` 13. First suite run had
  one failure before the fix was complete: `P0-DIFF-CHECK`
  (`git diff --check` exit 2) flagged a trailing blank line at
  the end of this record, added by the R1 edit — the blank line
  was removed, `git diff --check` is clean, and both recorded
  runs after that are exit 0.
- `tests/last-run.json` SHA-256
  `ddd94ee1502d77d22105ab6a6a5cc3a752bbdfe3e5c4d65eec7ff1c8b4e559c5`
  — identical to P1-001's, because the recorded entries (IDs,
  commands, results) are unchanged; only the per-file check
  counts inside the two R1 test files grew.
- `python3 scripts/validate-repo.py` — PASS.
- `python3 scripts/generate-registries.py --check` — CHECK OK.
- `python3 scripts/generate-report.py --check` — CHECK OK (same
  `--github-head` as generation).
- `git diff --check` — clean. `bash -n setup.sh` — exit 0.
- `bash setup.sh --dry-run` — exit 0 (core-only).
- `bash setup.sh --with-components` — NOT RUN (standing
  limitation, untouched by this round).
- P0 files untouched: `scripts/asset_policy.py`,
  `scripts/atomic_write.py`, `scripts/timeline_policy.py` —
  zero diff lines. No new dependencies (stdlib only). No server,
  API, database, cloud identity, graphical UI, or companion
  changes.

### 12.8 ADRs added by R1

- **R1-1 — enumeration is an authorization decision, not a
  lookup.** `issued_contexts_for_session` applies the same
  `is_active_session` gate as `authorize` and `_issue`. A
  session ID string is never enough to name a session's
  contexts; only the exact live object enumerates.
- **R1-2 — first-run publication is create-if-absent via
  `os.link()`.** Chosen over a cross-process lock file (no lock
  artefact to leak, no lock-holder crash to recover from) and
  over O_CREAT|O_EXCL direct write (a crash mid-write would
  leave a partial profile at the final path that fails closed
  forever). The link publishes a complete, fsynced file in one
  atomic step; the loser loads the winner. The P0 atomic-write
  helper stays untouched because its replace semantics are the
  bug, not the fix.

### 12.9 Limitations removed / still standing

- REMOVED: the accepted first-run identity race (§8) — closed
  and verified by FIRST-01..07; the trust-boundary doc no
  longer lists it as an accepted limitation.
- REMOVED (as a gap): unissued-session context enumeration —
  closed and verified by ENUM-01..08.
- STILL STANDING: local OS-user boundary only; no graphical UI;
  one workspace per installation; process-local revocation;
  Windows permission limits; macOS/Windows first-run branches
  tested only on Linux (the concurrency tests run on this Linux
  VM; the link primitive is documented as POSIX + Windows
  NTFS).

## 13. R2 addendum (2026-11-23) — CF-WO-P1-001-R2

Independent review of R1 found a Windows compatibility issue in
the same profile-publication path and two platform assumptions in
its regression tests. R2 fixes those without changing the runtime
architecture, weakening security, or modifying P0 policy.

### 13.1 Findings

- **R2-A — `os.fchmod` does not exist on Windows.**
  `runtime/local_session.py::_publish_profile_atomic()` called
  `os.fchmod(fd, 0o600)` unconditionally. Windows Python
  3.10–3.12 does not expose `os.fchmod`, so first-run profile
  initialization fails with `AttributeError` on Windows.
- **R2-B — the race test is POSIX-only.** The R1 race test
  hardcoded `multiprocessing.get_context("fork")` (there is no
  fork start method on Windows), and the profile-permission
  check asserted POSIX `0700`/`0600` mode bits unconditionally.
- **R2-C — no native Windows verification.** The CI workflow
  ran only the Linux full suite; nothing exercised the runtime
  on a real Windows machine.

### 13.2 Reproduced before the fix

- **R2-A** (`evidence/r2/p1-001-r2-repro-fchmod-before.txt`,
  exit 1): a child process that deletes `os.fchmod` from the
  `os` module before importing the runtime — the Windows
  Python 3.10–3.12 simulation — fails in
  `load_or_create_profile()` with `AttributeError: module 'os'
  has no attribute 'fchmod'` at the unconditional call
  (`runtime/local_session.py`, pre-fix line 358).
- **R2-B** (`evidence/r2/p1-001-r2-repro-fork-before.txt`):
  the pre-fix test file hardcodes `get_context("fork")`
  (line 626) and asserts POSIX mode bits unconditionally
  (`CF-P1-001-PROF-19`, line 310). "fork" is not a start
  method on Windows, so the race test cannot run there at all.

### 13.3 Fix R2-A — capability-checked fchmod

`_publish_profile_atomic()` now tightens the temporary file
with a narrow capability check — `if hasattr(os, "fchmod"):
os.fchmod(fd, 0o600)` — instead of an unconditional call.
On Windows the call is skipped and the file inherits the user
data directory's Windows security/ACL behaviour. This is a
check-then-use on the single capability, not a broad
`try/except AttributeError` around unrelated code: a missing
`fchmod` is the only tolerated absence, and any other failure
still raises. POSIX behaviour is unchanged (0700 directory,
0600 temp/profile file). The R1 `os.link()` create-if-absent
publication, symlink refusal, corrupt-profile fail-closed
behaviour, exclusive temp-file creation, cleanup and atomic
visibility are all untouched. `scripts/atomic_write.py` is not
modified. The docstrings of `_publish_profile_atomic()` and
`load_or_create_profile()` now state the platform distinction
explicitly, and the trust-boundary doc records it (see §13.7).

### 13.4 Fix R2-B — spawn race test, POSIX-gated assertions

- The race test uses `multiprocessing.get_context("spawn")`
  on every platform, pinned as the module constant
  `_RACE_CONTEXT_NAME = "spawn"` in
  `tests/test_local_session_runtime.py`. Worker functions
  (`_load_profile_worker`, `_init_first_run_worker`) are
  module-level and picklable, the barrier initializer runs in
  each spawned worker, and the test entry point is spawn-safe
  (importing the module never runs `main()` — guarded by
  `__main__`). Bounded waits/timeouts are preserved (30 s on
  every barrier wait and future result; no unbounded sleeps,
  no hanging children); child exit codes are checked via the
  futures, and every child process and temporary artefact is
  cleaned up by the pool context manager and the `finally`
  block, including on failure.
- `CF-P1-001-PROF-19` now asserts `0700`/`0600` only when
  `os.name == "posix"`; on other platforms it asserts the
  profile file exists under the data root, with no POSIX
  mode-bit equivalence claimed.
- The race test is not weakened: it still runs 5 rounds x 4
  independent processes against the same initially absent
  data root, plus the existing-valid and corrupt-profile
  collisions — now under spawn, which is the only start
  method on Windows.

### 13.5 Fix R2-C — native Windows CI job

New job `windows-compat` in `.github/workflows/p0-ci.yml`
(the existing Linux job `p0-validate` is untouched in
behaviour; workflow triggers are unchanged —
`pull_request` plus `push` on `[main,
feat/cf-p0-safe-foundations]`; the P1 branch is deliberately
NOT added to the push list, so the PR run is the CI evidence,
as in P1-001/R1):

- Job id: `windows-compat`. `runs-on: windows-latest`.
  Matrix: Python `3.10` and `3.12`.
- Steps: Check out (`actions/checkout`, same pinned SHA as
  the Linux job, v4.2.2); Set up Python
  (`actions/setup-python` pinned by full commit SHA
  `a26af69be951a213d495a4c3e4e4022e16d87065` — v5.6.0,
  the `v5` tag — verified with `git ls-remote` against the
  upstream repo, since the unauthenticated GitHub REST API
  was rate-limited); Show versions (`python --version`,
  start method, platform); Run runtime regression suites
  (`python tests/test_local_session_runtime.py`,
  `python tests/test_session_authorization.py`,
  `python tests/test_private_voice_security.py`).
- The steps run under `shell: bash` (Git Bash on the Windows
  runner) so a non-zero exit from any suite fails the step
  immediately, the same as on Linux.
- The race test (FIRST-01..07) runs for real in this job
  under spawn; its PASS lines must appear in the log — no
  test is skipped for the platform. The Windows job produces
  no `last-run.json` artefact (the three suites do not write
  one); its evidence is the job log.
- No PyYAML install on Windows: the three suites need only
  the stdlib plus the repo's own modules.

### 13.6 Tests executed — exact counts

- `tests/test_local_session_runtime.py` — exit 0, **67 PASS /
  0 FAIL** (was 63; +2 new CF-P1-001-R2 checks, +2
  CF-P1-001-R2-CANON checks added in the §13.11 follow-up).
  FIRST-01..07 all pass under spawn; R2-SPAWN-01 pins the spawn
  start method; R2-NOFCHMOD-01 runs profile creation + reload in
  a child process with `os.fchmod` hidden (30 s timeout, killed
  and reported on timeout); R2-CANON-01/02 prove the canonical-path
  mechanism on Linux (symlinked parent).
- `tests/test_session_authorization.py` — exit 0, **47 PASS /
  0 FAIL** (unchanged; R1 ENUM-01..08 still pass — copied,
  deep-copied, forged, expired, closed and wrong sessions
  cannot enumerate genuine contexts; the genuine active
  session still enumerates its own; no invalid session
  recovers a context usable for private export or provider
  transmission).
- `tests/test_private_voice_security.py` — exit 0, **158 PASS /
  0 FAIL** (unmodified).
- After (fixed code):
  `evidence/r2/p1-001-r2-repro-fchmod-after.txt` (exit 0 —
  profile created and reloaded without `os.fchmod`).
- Full suite `bash tests/run-tests.sh` — **twice**, exit 0
  both times: **56 recorded entries / 43 distinct test IDs /
  34 distinct commands, 56 PASS, 0 FAIL, 0 SKIP** (entry
  counts unchanged from R1 — the 2 new checks live inside
  the same test file). Per-file PASS lines, one run each,
  14 Python files total **1,418** (was 1,414; +2 runtime from
  the original R2 checks and +2 from the §13.11 CANON checks;
  verified by direct counting, not arithmetic).
  `test_installer_status.sh` 61; `test_installer.sh` 40;
  `test_installer_security.sh` 15;
  `test_installer_manifest_security.sh` 24;
  `test_installer_metadata_failure.sh` 13. Run outputs saved:
  `evidence/r2/p1-001-r2-suite-run1.txt` and
  `evidence/r2/p1-001-r2-suite-run2.txt` (original R2 runs),
  plus `evidence/r2/p1-001-r2f-suite-run1.txt` and
  `evidence/r2/p1-001-r2f-suite-run2.txt` (follow-up runs
  after the §13.11 fix — both exit 0).
- `tests/last-run.json` SHA-256
  `ddd94ee1502d77d22105ab6a6a5cc3a752bbdfe3e5c4d65eec7ff1c8b4e559c5`
  — identical to P1-001/R1, because the recorded entries
  (IDs, commands, results) are unchanged; only the per-file
  check count inside `test_local_session_runtime.py` grew.
- `python3 scripts/validate-repo.py` — PASS.
- `python3 scripts/generate-registries.py --check` — CHECK OK.
- `python3 scripts/generate-report.py --check` — CHECK OK
  (same `--github-head` as generation).
- `git diff --check` — clean. `bash -n setup.sh` — exit 0.
- `bash setup.sh --dry-run` — exit 0 (core-only).
- `bash setup.sh --with-components` — NOT RUN (standing
  limitation, untouched by this round).
- P0 files untouched: `scripts/asset_policy.py`,
  `scripts/atomic_write.py`, `scripts/timeline_policy.py` —
  zero diff lines. No new dependencies (stdlib only). No
  server, API, database, cloud identity, graphical UI, or
  companion changes.

### 13.7 Native Windows CI results — FILLED from live PR run #223 (HISTORICAL)

**F1 correction (2026-11-23, §13.12):** this section records PR run
#223 faithfully — it ran against head
`f970d5177797e667debbb1591bf5ae0d9739231f`, NOT the current PR HEAD
`2f66bd21001c8d0d0dce7b571539555bf658c475`. Run #223 is therefore
HISTORICAL evidence (the recovery run after the #216 failure), not
the exact-current-HEAD verification. The exact-current-HEAD
verification is PR run #225, recorded in §13.12. Nothing in this
section is rewritten: the #223 facts below stand as the record of
that run, and this note corrects only how the run is labelled.

The native Windows run is PR run #223 (run ID 45253011530,
event pull_request, head f970d5177797e667debbb1591bf5ae0d9739231f,
https://github.com/msujoy149/consistency-frame/actions/runs/45253011530),
overall conclusion Success, total duration 1m 5s. All three jobs
succeeded; no push run exists for this branch (expected — the
workflow triggers on push only for main and
feat/cf-p0-safe-foundations). The PASS lines below were verified
from the downloaded raw log archives (grepped locally), not only
from the page view.

- Python 3.10 run: Success, 1m 2s. "Show versions" prints
  Python 3.10.11, start method spawn, win32. Runtime suite:
  PASS (0 failure(s)), 65 PASS lines, 0 FAIL lines. FIRST-01..07
  all PASS (concurrent first runs return one shared identity,
  5 rounds x 4 processes, and the rest of the FIRST group),
  R2-SPAWN-01 PASS, R2-NOFCHMOD-01 PASS, FS-03 / FS-04 / FS-04b
  (symlink) PASS. Authorization suite PASS (0 failure(s)),
  47 PASS lines. P0 security suite PASS (0 failure(s)),
  158 PASS lines.
- Python 3.12 run: Success, 27s. "Show versions" prints
  Python 3.12.10, start method spawn, win32. Runtime suite:
  PASS (0 failure(s)), 65 PASS lines, 0 FAIL lines, with the
  same FIRST-01..07, SPAWN-01, NOFCHMOD-01 and FS-03/FS-04/FS-04b
  PASS lines. Authorization suite PASS (0 failure(s)), 47 PASS
  lines. P0 security suite PASS (0 failure(s)), 158 PASS lines.
- No test skipped for the platform: a search for "skip" across
  all Windows step logs returns no matches.
- Runtime-suite count correction: the Windows total is 65 PASS,
  not 67. The two R2-CANON checks are Linux-only by design
  (`os.name == "posix"` gate in the test); they prove the
  canonical-path mechanism on Linux, and on Windows the same
  realpath comparison is exercised by PROF-01b/12b and SESS-18
  themselves. CANON-01/02 PASS in the Linux p0-validate log of
  this same run.
- Linux p0-validate in the same run: Success, 59s. Artifact
  `p0-test-results`, 906 bytes, artifact ID 14855723149,
  digest sha256:62d226b4156b62e748af4d68f4f793045addc54042e9017c33ab98f2ea10c2cf;
  the `last-run.json` inside is byte-identical to the committed
  file (SHA ddd94ee1502d77d22105ab6a6a5cc3a752bbdfe3e5c4d65eec7ff1c8b4e559c5).

Windows support is now verified by the native run above: the
race test runs for real under spawn on Windows, profile
creation works without `os.fchmod`, and no relevant test is
skipped for the platform. (At the time this section was filled,
run #223 was the latest successful run. The exact-current-HEAD
verification is run #225 — see §13.12 — which re-verified the
same results against the current PR HEAD `2f66bd21`.)

### 13.8 Files changed (R2)

- `runtime/local_session.py` — capability-checked `fchmod`
  in `_publish_profile_atomic()` + platform-distinction
  docstrings.
- `tests/test_local_session_runtime.py` — spawn race test,
  POSIX-gated PROF-19, new R2 group (2 checks).
- `.github/workflows/p0-ci.yml` — new `windows-compat` job
  (matrix Python 3.10/3.12); `p0-validate` untouched.
- `docs/runtime/LOCAL_SESSION_AND_TRUST_BOUNDARY.md` —
  platform distinction in §7, Windows permission limits,
  platform coverage, test counts (65 checks).
- `CHANGELOG.md` — `[Unreleased]` R2 bullet.
- Provenance files (living report, BUILD_REPORT_P0.md,
  build-report.json, CHECKSUMS.txt, release-manifest.json) —
  regenerated after the final suite run.

### 13.9 ADRs added by R2

- **R2-1 — capability check, not a broad except.** The
  missing-`fchmod` case is handled with `hasattr(os,
  "fchmod")` at the single call site. A broad
  `try/except AttributeError` would also swallow unrelated
  failures inside the same block (a real bug hiding behind
  the platform difference); the narrow check keeps every
  other failure loud.
- **R2-2 — spawn is the one start method for the race test.**
  "fork" is POSIX-only; "spawn" exists on Windows, Linux and
  macOS, and the test's workers were already module-level
  and picklable, so spawn costs nothing and buys every
  platform. The constant is pinned so a future edit back to
  "fork" fails loudly in R2-SPAWN-01.
- **R2-3 — setup-python pinned by SHA, verified without the
  REST API.** The unauthenticated GitHub REST API was
  rate-limited, so the `v5` tag's commit was resolved with
  `git ls-remote` against the upstream repo
  (`a26af69be951a213d495a4c3e4e4022e16d87065`, v5.6.0) — a
  verifiable, reproducible pin, recorded here rather than
  silently falling back to a floating tag.

### 13.10 Limitations removed / still standing

- REMOVED: profile initialization failing on Windows
  (`os.fchmod` AttributeError) — fixed and verified by the
  no-fchmod simulation (R2-NOFCHMOD-01); native Windows
  verification is the `windows-compat` CI job (§13.7).
- REMOVED: fork-only race test and unconditional POSIX
  permission assertions — the race test now runs under spawn
  on Linux (FIRST-01..07 pass) and the permission assertions
  are POSIX-gated.
- STILL STANDING: local OS-user boundary only; no graphical
  UI; one workspace per installation; process-local
  revocation; macOS untested on real hardware (resolution
  function only, patched platform probe); Windows permission
  limits (ACL inheritance, no POSIX mode-bit equivalence);
  native Windows CI results are now recorded in §13.12 (PR run
  #225, the exact-current-HEAD run, all three jobs Success;
  §13.7 keeps the earlier run #223 as historical evidence).

### 13.11 R2 follow-up (2026-11-23) — PR run #216 failed on Windows; test-side fix

The first PR run of the R2 head failed on Windows. This
section records that failure honestly, its root causes, and
the fix. Production behaviour is unchanged by this follow-up.

**PR run #216** (run ID 45242077218), head
`ac7d5b08d6279577f86e520db2b5431efcae02f0` (the R2 head):

- Linux job `p0-validate`: **SUCCESS** (51s).
- `windows-compat` Python 3.12: **FAILURE** —
  `tests/test_local_session_runtime.py` FAIL (6 failure(s)).
- `windows-compat` Python 3.10: **CANCELLED** by matrix
  fail-fast — never ran any test.
- Linux artifact `p0-test-results` verified byte-identical
  (digest
  `sha256:3b842d0cc28015343022742bfe8f2641320f386aabaff837d236aa65456faa8a`).
- No push run exists (expected — push triggers unchanged).

**The 6 failing checks (first log read — trusted).** The
names were verified against
`tests/test_local_session_runtime.py` at head `ac7d5b08` by
grep (lines 178, 297, 307, 312, 328, 508):

1. `CF-P1-001-PROF-01b`: profile file lives under the data root
2. `CF-P1-001-PROF-12b`: profile lands under the override
3. `CF-P1-001-PROF-13`: XDG_DATA_HOME is respected
4. `CF-P1-001-PROF-14`: default is ~/.local/share
5. `CF-P1-001-PROF-16`: macOS uses Application Support
6. `CF-P1-001-SESS-18`: sessions are never persisted to disk

**A second browser read of the same failed job log was
discarded as unreliable.** It returned 6 FAIL names that DO
NOT EXIST in `tests/test_local_session_runtime.py` at this
head (e.g. "local profile file is read-only for the owner",
"relaunch returns the same session"). The first read stands;
the second read's names are used nowhere.

**Root causes (parent-established, by experiment on Linux)
— all six are TEST-side defects, not production defects:**

1. PROF-01b, PROF-12b, SESS-18 compared path STRINGS.
   Production `_profile_path()` canonicalizes via
   `asset_policy.resolve_private_path` (realpath). On
   Windows the temp dir is spelled with an 8.3 short-name
   component (RUNNER~1) that realpath expands to the long
   form, so the strings differ while the files are
   identical. Linux proof: with a root spelled through a
   symlinked parent component, `profile_path` is the
   realpath'd form, the naive join differs, and realpath
   comparison is True. Production canonicalization is a
   security feature and stays.
2. PROF-13, PROF-14 asserted the Linux resolution branches
   without mocking the platform. On Windows
   `resolve_data_root()` takes the Windows (LOCALAPPDATA)
   branch first and never reads XDG — by design (docs: Linux
   respects XDG, Windows uses LOCALAPPDATA).
3. PROF-16 mocked `platform.system` to "Darwin" but set
   only HOME. `ntpath.expanduser('~')` IGNORES HOME
   entirely — it consults only USERPROFILE (HOME-only
   returns `'~'`; USERPROFILE set returns it). Verified by
   experiment with the `ntpath` module. On Windows, the
   Darwin branch therefore resolved against the runner's
   real USERPROFILE-based home, not the test's HOME-based
   one.

**Fix (test-side only, in
`tests/test_local_session_runtime.py`):**

1. PROF-01b, PROF-12b, SESS-18 compare canonical paths —
   `os.path.realpath(...)` on both sides.
2. PROF-13, PROF-14 mock `platform.system` to return
   "Linux" (the same pattern PROF-16/17 already use).
   USERPROFILE is set to the temp home as well: with only
   the platform mock, PROF-14 would still fail on Windows,
   because `ntpath.expanduser` ignores HOME (verified by
   experiment with `ntpath`: HOME-only returns `'~'`;
   USERPROFILE wins even when HOME is also set). Harmless on
   POSIX — `posixpath.expanduser` ignores USERPROFILE. (This
   USERPROFILE addition for PROF-13/14 is the coordinator's
   own finding, extending the parent's stated fix.)
3. PROF-16 sets BOTH HOME and USERPROFILE to the temp home
   when mocking Darwin (same `ntpath` reason as above).
4. New Linux-only regression checks CF-P1-001-R2-CANON-01/02:
   a root spelled through a symlinked parent component —
   `profile_path` equals the realpath'd join, and the
   SESS-18-style file listing matches after realpath. No
   existing check weakened.

**Workflow fixes (`.github/workflows/p0-ci.yml`,
`windows-compat` only; `p0-validate` untouched; triggers
unchanged — the P1 branch is still NOT in the push list):**

- `fail-fast: false` in the matrix strategy — the default
  fail-fast cancelled the 3.10 job when 3.12 failed, so 3.10
  never ran any test. Each version's result now stands on its
  own.
- The single "Run runtime regression suites" step is split
  into three separate steps (one per suite), so a failure in
  one suite cannot hide the other two.
- Matrix `["3.10", "3.12"]` unchanged; shell `bash` unchanged.

**Verification after the fix (Linux):**
`tests/test_local_session_runtime.py` 67 PASS / 0 FAIL;
`tests/test_session_authorization.py` 47 PASS / 0 FAIL;
`tests/test_private_voice_security.py` 158 PASS / 0 FAIL
(unmodified); full suite twice, exit 0 both: 56 entries /
43 IDs / 34 commands, 56 PASS, 0 FAIL, 0 SKIP;
`tests/last-run.json` SHA
`ddd94ee1502d77d22105ab6a6a5cc3a752bbdfe3e5c4d65eec7ff1c8b4e559c5`
unchanged; per-file total 1,418 (verified by direct
counting). Run outputs:
`evidence/r2/p1-001-r2f-suite-run1.txt` and
`evidence/r2/p1-001-r2f-suite-run2.txt`. Evidence note:
`evidence/r2/p1-001-r2-windows-ci-216-failure-note.txt`.

**§13.7 is now filled from the re-run (#223).** Windows support
is verified by that run; the #216 failure is recorded here
precisely so that no earlier claim is left standing.

**F1 correction (2026-11-23, §13.12):** run #223 ran against head
`f970d517`, not the current PR HEAD `2f66bd21`. It is kept as the
historical recovery run; the exact-current-HEAD verification is
run #225 (§13.12).

### 13.12 R2-F1 (2026-11-23) — final CI evidence & provenance reconciliation

Documentation/evidence correction only. No runtime code,
authorization code, test, P0 policy file, or companion internal
changed in this round.

**The correction.** The R2 report and this record treated PR run
#223 as the final verification for the current PR HEAD
`2f66bd21001c8d0d0dce7b571539555bf658c475`. That is inaccurate:
run #223 (run ID 45253011530) ran against head
`f970d5177797e667debbb1591bf5ae0d9739231f` (the follow-up docs
push head), not the current PR HEAD. Run #223 is therefore
relabeled HISTORICAL evidence — the recovery run after the #216
failure — and is NOT described anywhere as the
exact-current-HEAD run. Its facts (recorded in §13.7) stand
unchanged; only the label is corrected, with an explicit note
added in §13.7, §13.10 and §13.11 rather than a silent rewrite.

**PR run #225 — the exact-current-HEAD verification.** Run
#225 (run ID 45257996093, event pull_request, head
`2f66bd21001c8d0d0dce7b571539555bf658c475` — the exact current
PR HEAD,
https://github.com/msujoy149/consistency-frame/actions/runs/45257996093),
overall conclusion Success, total duration 1m 8s, started
2026-11-23 12:18 PM PST. All three jobs succeeded; no push run
exists for this head (expected — the workflow triggers on push
only for main and feat/cf-p0-safe-foundations). The PASS lines
below were verified from the downloaded raw log archives
(grepped locally), not only from the page view.

- Python 3.10 run: Success, 1m 4s. "Show versions" prints
  Python 3.10.11, start method spawn, win32. Runtime suite:
  PASS (0 failure(s)), 65 PASS lines, 0 FAIL lines. FIRST-01..07
  all PASS, R2-SPAWN-01 PASS, R2-NOFCHMOD-01 PASS, FS-03 / FS-04
  / FS-04b (symlink) PASS. Authorization suite PASS (0
  failure(s)), 47 PASS lines. P0 security suite PASS (0
  failure(s)), 158 PASS lines.
- Python 3.12 run: Success, 22s. "Show versions" prints
  Python 3.12.10, start method spawn, win32. Runtime suite:
  PASS (0 failure(s)), 65 PASS lines, 0 FAIL lines, with the
  same FIRST-01..07, SPAWN-01, NOFCHMOD-01 and FS-03/FS-04/FS-04b
  PASS lines. Authorization suite PASS (0 failure(s)), 47 PASS
  lines. P0 security suite PASS (0 failure(s)), 158 PASS lines.
- No test skipped for the platform: a search for "skip" across
  all Windows step logs returns no matches.
- Runtime-suite count correction (as in §13.7): the Windows
  total is 65 PASS, not 67. The two R2-CANON checks are
  Linux-only by design (`os.name == "posix"` gate in the test);
  they PASS in the Linux p0-validate log of this same run and are
  correctly absent on Windows.
- Linux p0-validate in the same run: Success, 53s. Artifact
  `p0-test-results`, 906 bytes, artifact ID 14859467946,
  digest sha256:588ff296e74c409d0bae87e9bb960c3de7ffce9196cf30a973280458830673ae;
  the `last-run.json` inside is byte-identical to the committed
  file (SHA ddd94ee1502d77d22105ab6a6a5cc3a752bbdfe3e5c4d65eec7ff1c8b4e559c5).

Windows support is verified by the native run above against the
exact current PR HEAD: the race test runs for real under spawn on
Windows, profile creation works without `os.fchmod`, and no
relevant test is skipped for the platform.

**Evidence staged for delivery.** Run #225 Linux artifact
(`ci-evidence-p1-001-r2-f1/p0-test-results-run225.zip`, digest
sha256:588ff296e74c409d0bae87e9bb960c3de7ffce9196cf30a973280458830673ae)
and the native Windows per-job logs
(`evidence/r2-f1/windows-compat-3.10-run225.log`,
SHA-256 8e61bb0e799df8701ce8bb3c4cc2419b9c5ee17b3444044c44eb1d7e12b5e20e;
`evidence/r2-f1/windows-compat-3.12-run225.log`,
SHA-256 d45a67547bb84aba0d0e965853deb95f581e82c2bd3e6d5fb8b8da0beb0a0c78;
each 273 "PASS " lines = 270 checks + 3 suite summaries, 0 "skip"
matches). The F1 README
(`ci-evidence-p1-001-r2-f1/README.txt`) lists run #223
(historical) and run #225 with exact run IDs, head SHAs, job
results, artifact IDs and digests. No artifact from run #223 is
presented as belonging to run #225, and vice versa. The final
post-F1-push PR run does not exist yet and is not invented here;
it will be added after the push.

**Provenance explanation (the `213759c6` snapshot).** The
pre-F1 manifest recorded
`github_branch_head=213759c69d06f471c5b69c687b93fffa9747ee89`
— that value is the SOURCE SNAPSHOT used for the final
provenance generation of the R2 round, NOT the current PR HEAD.
The comparison from that snapshot to the current HEAD
`2f66bd21` shows exactly ONE commit (`1dcd001`, "P1-001-R2
docs: provenance at GitHub head 213759c6"), which affects only
generated report files (the living report, BUILD_REPORT_P0.md,
build-report.json, CHECKSUMS.txt, release-manifest.json) and
changes no code, test, workflow, or policy file. `213759c6` is
therefore never described as the current PR HEAD.

The same snapshot-explanation pattern applies to the new
manifest generated in this F1 round: its
`github_branch_head` is the current GitHub head `2f66bd21`
(the exact current PR HEAD at F1 generation time); the
subsequent docs commit after the F1 push will be
provenance/reporting only, and the parent re-regenerates
provenance after that push. The 169-file hash verification
result and the detached checksum verification result are kept
(see §13.6 and the F1 provenance record below).

**F1 provenance (generated with `--github-head 2f66bd21`,
current GitHub head; full suite run once first, then
`generate-report.py`, then `generate-build-report.py` last):
full suite 56 entries / 43 IDs / 34 commands, 56 PASS, 0 FAIL,
0 SKIP; `tests/last-run.json` SHA
`ddd94ee1502d77d22105ab6a6a5cc3a752bbdfe3e5c4d65eec7ff1c8b4e559c5`
unchanged. Manifest: 169 files, generated from the live tree,
`github_branch_head=2f66bd21`, manifest commit `1dcd001` (the
local head at generation time — the parent re-regenerates after
the F1 push). Manifest SHA-256
`95c4124d833fe22b57998d768b491eff14b9a8dc6bfab0cb11ab125ae230650d`
(32,169 bytes); build-report SHA-256
`b47ba98612da3dfce4a23ea1ace5ba94c0cf182f3303bacc72ac1280f5558901`
(19,073 bytes); BUILD_REPORT_P0.md SHA-256
`1c141aa80ba11f828d1e5a3fbcde5c2ed510b1d68b84872953448a2980caa541`
(47,114 bytes); CHECKSUMS.txt 3/3 OK (detached SHA-256 + byte
counts verified against the three generated files). The
corrections document's own SHA-256 is recorded in the delivery
report, not here (a file cannot record its own hash).**
