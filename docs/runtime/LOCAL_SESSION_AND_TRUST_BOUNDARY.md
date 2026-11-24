# Local Session and Trust Boundary (P1-001)

The first real runtime component of Consistency Frame
(CF-WO-P1-001): a trusted **local** application session and
authorization boundary. It answers one question the P0 policy
layer could not answer on its own: *who is the actor* making a
private-asset authorization decision?

P0 already decided, for a named owner/workspace, whether an action
was allowed (`scripts/asset_policy.py::authorize_action`), and it
already required a factory-issued `TrustedAuthorizationContext`
for private voice export. What P0 did not supply was the actor
identity itself: a caller could pass any owner/workspace strings.
This runtime supplies that identity from a validated local
installation profile, through a process-bound session, and hands
it to the P0 policy — which remains the single policy source.

## What the boundary guarantees

1. **Stable local identity.** The first run generates a stable,
   opaque `owner_id` and `workspace_id` (cryptographically secure
   random identifiers — never a name, email, phone number or other
   personal information) and persists them in
   `<data-root>/profile.json`. Later runs load the same IDs; a
   restart never changes them.
2. **Identity comes from the validated profile, never from the
   caller.** Every authorization decision takes `owner_id` and
   `workspace_id` from an active session that was itself started
   from the validated profile. The authorization bridge
   (`runtime/authorization.py::authorize`) has no parameter for
   caller-provided identity — a caller that tries to pass
   `requesting_owner_id` / `requesting_workspace_id` gets a
   `TypeError` from the signature itself.
3. **Sessions are process-bound and freshly issued.** Every
   `start_session()` call mints a fresh session ID. A session is
   accepted only when it is the exact object the factory issued
   in this process (`type(session) is LocalSession` plus an
   `id()`-keyed weak-reference registry checked with `is` — the
   P0-011 pattern). Direct construction, subclass spoofing,
   `__new__`-built objects, shallow/deep copies, and
   serialization/deserialization can never manufacture an
   accepted session. Sessions are never written to disk.
   Enumerating a session's issued contexts
   (`issued_contexts_for_session`) requires the same proof: only
   an exact, ACTIVE issued session enumerates — a copied,
   forged, `__new__`-built, expired or closed object gets a
   fail-closed `ValueError` and never sees a context (R1).
4. **Closed or expired means refused.** Closing a session is
   permanent and immediate: further authorization through it
   fails, and every still-live private-voice export context it
   issued is revoked at close. Sessions also carry a finite
   lifetime (12 hours by default, at most 24 hours); export
   contexts carry a short finite expiry (5 minutes by default,
   at most 1 hour).
5. **Export and provider transmission stay separate.** An export
   approval never sets `provider_transmission_approved`. Sending
   a voice to an external provider needs its own distinct
   explicit approval through
   `request_provider_transmission_authorization()`.
6. **The P0 policy is the only policy.** Ownership, sharing,
   binding, expiry and revocation rules are not duplicated in
   the runtime; they live in `scripts/asset_policy.py` and the
   runtime delegates to them. The P0 private-voice security
   suite (`tests/test_private_voice_security.py`) still passes
   unmodified.
7. **Local state is stored safely.** The profile is published
   atomically and exactly once: the candidate is written to an
   unguessable temporary file in the same directory (mode 0600
   on POSIX, flushed + fsynced) and then published with `os.link()` — a
   single atomic create-if-absent operation that fails when the
   profile already exists, so a concurrent first run can never
   overwrite the winner's profile (R1; the P0
   `scripts/atomic_write.py` helper is not used for the profile
   because its `os.replace()` unconditionally overwrites the
   target). The 0600 tightening is capability-checked
   (`hasattr(os, "fchmod")`): Windows Python 3.10–3.12 does not
   expose `os.fchmod`, so the call is skipped there and the file
   inherits the user data directory's Windows security/ACL
   behaviour instead (R2). The profile lives in a 0700 directory as a 0600
   file on POSIX systems. Traversal, absolute paths and symlink
   escapes are rejected (`resolve_private_path`); a symlinked
   profile is refused rather than followed; a corrupt, invalid
   or tampered profile fails closed and is left byte-for-byte
   untouched — it is never silently replaced. A failed write
   never destroys the previous valid profile, and no temporary
   file or lock artefact remains after a successful
   initialization.

## What the boundary does NOT guarantee

This is the honest limit, and it is load-bearing — do not present
this runtime as stronger than it is:

- **It is a local OS-user boundary only.** It proves an object
  was issued by this process's session factory and that the
  actor IDs came from the validated local profile. It does NOT
  prove the person operating the application is who the IDs
  name, and it does NOT protect against another process or
  attacker already controlling the same OS account: such code
  can read the profile file, import this module, or rewrite the
  profile. There is no password, no cryptographic identity
  proof, no server, no cloud account, and no credential vault
  anywhere in this runtime — by design (see §2 of the work
  order).
- **A session ID or owner ID is an identifier, not a secret.**
  Knowing one confers nothing on its own; authority comes only
  from holding the exact issued session object in this process.
  Do not treat these IDs as passwords or tokens, and do not log
  them as if they were secrets either — they are not, but there
  is no reason to spray them through logs.
- **Revocation is process-local.** The P0 revocation registry
  is in-memory; a restart clears it, and contexts must be
  re-issued. Persistent revocation across restarts is future
  work, not this work order. Contexts also expire on their own
  short schedule, which bounds the window.
- **No graphical UI exists yet.** Owner approval is delivered
  through a narrow callback
  (`approve_callback(action, *, character_id, voice_profile_id,
  scope) -> bool`). The callback is the seam where a future
  application UI confirms the action with the owner; this work
  order does not build that UI, and nothing here claims it does.
- **One workspace per installation.** This work order's profile
  holds exactly one workspace, and `start_session()` refuses a
  workspace ID that does not match it. Multi-workspace
  installations are not modelled here.
- **Concurrent first runs agree on one identity.** First-run
  initialization is an atomic create-if-absent publication
  (`os.link()`): when two processes start at the same instant,
  one publishes and the other loads the winner's profile — the
  loser discards its candidate, nothing is overwritten, and no
  process ever reads a partially written profile (R1; this
  replaces the earlier accepted race, which is now closed).
- **Windows permission limits.** POSIX 0700/0600 modes are
  enforced where the platform supports them. On Windows,
  `os.chmod` does not provide equivalent semantics, so the
  profile directory and file do not get the same restrictive
  bits there; Windows Python 3.10–3.12 also has no `os.fchmod`,
  so the temporary/profile file is not chmodded at creation on
  Windows — it inherits the `%LOCALAPPDATA%` directory's
  Windows security/ACL behaviour instead (R2). The profile is
  still stored under `%LOCALAPPDATA%` (a per-user location)
  and is still written atomically. Do not claim Windows file
  permissions equal the POSIX ones.
- **Platform coverage.** The data-root resolution covers Linux
  (`XDG_DATA_HOME` else `~/.local/share`), macOS (`~/Library/
  Application Support`) and Windows (`%LOCALAPPDATA%`). The
  tests run on Linux; the runtime suites additionally run
  natively on Windows in CI (`windows-compat` job:
  `windows-latest`, Python 3.10 and 3.12 — the recorded
  results live in the corrections record). The macOS branches
  are exercised only through the resolution function with a
  patched platform probe, not on a real macOS machine; the
  Windows data-root branch is likewise exercised through the
  resolution function, while the Windows profile-publication
  and race behaviour is exercised by the native Windows CI job.

## Data-root resolution

| Platform | Data root |
|---|---|
| Linux | `$XDG_DATA_HOME/consistency-frame` if `XDG_DATA_HOME` is set and absolute, else `~/.local/share/consistency-frame` |
| macOS | `~/Library/Application Support/consistency-frame` |
| Windows | `%LOCALAPPDATA%\consistency-frame` (required — a missing value is an error) |
| Any (override) | the explicit `data_root` argument, used verbatim (for controlled deployments and tests) |

There is no fallback to a repository-local directory anywhere in
the resolution. A relative `XDG_DATA_HOME` is invalid per the XDG
specification and is ignored.

## Profile format

`profile.json` — the only file the runtime writes — holds exactly:

```json
{
  "schema_version": 1,
  "owner_id": "<32 lowercase hex chars>",
  "workspace_id": "<32 lowercase hex chars>"
}
```

No passwords, API keys, voice files, authorization contexts, or
personal data are stored in it. Any deviation (wrong type,
missing or extra fields, wrong `schema_version`, malformed IDs)
fails closed with `ProfileError` and leaves the file untouched.

## Session lifecycle

1. `load_or_create_profile(data_root=None)` — load and strictly
   validate the profile, or create it on first use (atomic
   create-if-absent publication, re-read and validated before
   it is returned — whether this process published it or a
   concurrent first run won).
2. `start_session(profile, workspace_id, *, lifetime_seconds=43200)`
   — mint a fresh session bound to the profile's owner and the
   explicitly passed workspace (which must equal the profile's
   workspace). Register it as the factory's last step.
3. `is_active_session(session)` — the single verifier: exact type
   + registry identity + not closed + not expired.
4. `authorize(session, action, ownership)` — bridge to the P0
   policy with session identity.
5. `request_voice_export_authorization(...)` /
   `request_provider_transmission_authorization(...)` — trusted
   issuance through the P0 factory, each with explicit owner
   approval, exact Character/Voice binding, and a short finite
   expiry.
6. `close_session(session)` — shutdown: the session is marked
   closed first, then registered close handlers run (the
   authorization module's handler revokes that session's live
   contexts). Closing is permanent; a restart starts a new
   session with the same stable IDs.

Context revocation on close requires `runtime.authorization` to
have been imported (it registers the revocation handler at import
time). The application entry point must import it before closing
sessions that issued contexts.

## Module map

- `runtime/__init__.py` — package docstring only; no eager imports.
- `runtime/local_session.py` — profile + data root + sessions
  (Tasks A, B, E). Imports the P0 policy module through the same
  single-instance import the tests use (see the comment at the
  top of the file): two separately loaded copies of
  `asset_policy` would have two separate issuance registries.
- `runtime/authorization.py` — bridge + trusted issuance
  (Tasks C, D). Delegates every decision to
  `scripts/asset_policy.py`; duplicates no rule.

## Tests

- `tests/test_local_session_runtime.py` — CF-P1-001-PROF (profile
  lifecycle), CF-P1-001-SESS (session integrity), CF-P1-001-FS
  (filesystem security), CF-P1-001-R1-FIRST (atomic first-run
  identity across concurrent processes), CF-P1-001-R2 (race test
  under the "spawn" start method on every platform, POSIX-gated
  permission assertions, profile creation without `os.fchmod`,
  canonical-path (realpath) comparisons, Linux-branch data-root
  checks under a mocked platform): 67 checks.
- `tests/test_session_authorization.py` — CF-P1-001-AUTH
  (bridge), CF-P1-001-EXP (export issuance), CF-P1-001-P0 (P0
  behaviour unchanged), CF-P1-001-R1-ENUM (context enumeration
  requires exact active issuance): 47 checks.

Both are registered in `tests/run-tests.sh` as `CF-P1-001-SESSION`
and `CF-P1-001-AUTHZ`. Full record:
`docs/implementation/CF-WO-P1-001-corrections.md`.
