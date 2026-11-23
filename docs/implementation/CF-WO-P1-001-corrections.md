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
  half-written profile results.
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
