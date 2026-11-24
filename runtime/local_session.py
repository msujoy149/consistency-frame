#!/usr/bin/env python3
"""Consistency Frame P1 — local installation identity and process-bound
sessions (CF-WO-P1-001, Tasks A + B + E).

Two layers:

1. Installation identity. On first use the runtime generates a stable,
   opaque ``owner_id`` and ``workspace_id`` (cryptographically secure
   random identifiers — never a name, email, phone number or other
   personal information) and persists them in a small profile file
   OUTSIDE the repository, under a portable user data root:
   Linux respects ``XDG_DATA_HOME`` (else ``~/.local/share``), macOS
   uses ``~/Library/Application Support``, Windows uses
   ``%LOCALAPPDATA%``; an explicit data-root override is accepted for
   controlled deployments and tests. There is no silent fallback to a
   repository-local directory. A missing profile is initialized; a
   corrupt, invalid or apparently tampered profile FAILS CLOSED — it
   is never silently replaced, so its identity is never lost. The
   profile holds only the minimum identity/configuration data: no
   passwords, API keys, voice files or authorization contexts.

2. Process-bound sessions. :func:`start_session` mints a fresh
   session ID for every application session, binds it to the
   profile's owner ID and an explicitly selected workspace ID, and
   registers the exact object in a process-local issuance registry.
   :func:`is_active_session` is the single verifier and follows the
   P0-009 / P0-010 / P0-011 lessons exactly: exact concrete type
   (``type(session) is LocalSession`` — subclassing is prohibited by
   ``__init_subclass__`` as defence-in-depth only) plus an
   ``id()``-keyed dict of weak references checked with ``is`` — never
   a weak set's equality-based membership, never ``==``, never a hash
   of the candidate. A session ID or owner ID is an identifier, not
   a secret credential. Sessions are never persisted to disk: a
   restart creates a new session while the installation's stable
   IDs survive.

Security boundary (see
``docs/runtime/LOCAL_SESSION_AND_TRUST_BOUNDARY.md``): this is a
local OS-user boundary only. It proves an object was issued by this
process's session factory and that the actor IDs came from the
validated local profile — it does NOT prove the person operating the
application is who the IDs name, and it does NOT protect against
another process or attacker already controlling the same OS account
(such code can read the profile, call this module, or rewrite the
profile file). The profile object itself is data: its trust comes
from being loaded and validated from the local data root by
:func:`load_or_create_profile`, not from its type. In-process
construction of profile data is outside the threat model, exactly
as P0's policy layer assumes the calling process is trusted.
"""

from __future__ import annotations

import copy
import json
import os
import platform
import secrets
import sys
import tempfile
import uuid
import weakref
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# Shared P0 policy module (single module instance — see below).
# ---------------------------------------------------------------------------
# The P0 policy layer keeps process-local issuance/revocation registries
# as module globals (scripts/asset_policy.py). Two separately loaded
# copies of that module would have two separate registries, and a
# context issued through one copy would fail verification through the
# other. This runtime therefore imports the SAME module object every
# other consumer uses: it puts the repo's scripts/ directory on
# sys.path (exactly as tests/test_private_voice_security.py does) and
# then imports normally, so sys.modules caches one instance. The
# scripts/ directory is derived from this file's location, never from
# the current working directory.
_SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import asset_policy  # noqa: E402

APP_DIR_NAME = "consistency-frame"
PROFILE_FILENAME = "profile.json"
PROFILE_SCHEMA_VERSION = 1

# Session lifetime: 12 hours by default, at most 24 hours. A session
# is one application run; a finite lifetime bounds how long a stolen
# in-process reference stays usable, and a restart always mints a
# fresh session anyway.
DEFAULT_SESSION_LIFETIME_SECONDS = 12 * 60 * 60
MAX_SESSION_LIFETIME_SECONDS = 24 * 60 * 60


class ProfileError(ValueError):
    """A local installation profile is missing data, corrupt,
    invalid, or unsafe to use. Fail closed: callers must not
    silently re-initialize or replace the profile."""


class SessionError(ValueError):
    """A session could not be started, validated, or closed."""


# ---------------------------------------------------------------------------
# Opaque identifiers
# ---------------------------------------------------------------------------

def _new_opaque_id() -> str:
    """A fresh opaque local identifier: 32 lowercase hex characters
    from a cryptographically secure random source. It matches the
    P0 ownership ID pattern (``^[a-z0-9][a-z0-9\\-]{2,63}$``) so an
    ID minted here is directly usable as an owner/workspace ID in
    the P0 policy layer."""
    return secrets.token_hex(16)


def _is_valid_opaque_id(value) -> bool:
    """Strict opaque-ID check. ``fullmatch`` (not the P0 layer's
    ``search``) so a trailing newline or other smuggled character
    can never pass: the runtime is deliberately stricter than the
    policy layer at this boundary."""
    return (isinstance(value, str)
            and asset_policy.OWNERSHIP_ID_PATTERN.fullmatch(value)
            is not None)


def _utc_now_iso() -> str:
    """Current UTC time as an ISO-8601 'Z' string (lexicographic
    comparison works for expiry checks — same format as P0)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Data-root resolution (Task A)
# ---------------------------------------------------------------------------

def resolve_data_root(data_root=None) -> str:
    """Resolve the local data root that holds the installation
    profile.

    Precedence: an explicit ``data_root`` override wins (it names
    the data root itself, for controlled deployments and tests);
    otherwise the platform default applies — Linux respects
    ``XDG_DATA_HOME`` (a relative value is invalid per the XDG
    specification and is ignored), else ``~/.local/share``; macOS
    uses ``~/Library/Application Support``; Windows uses
    ``%LOCALAPPDATA%`` (required — a missing value is an error,
    never a silent fallback). The application subdirectory is
    ``consistency-frame`` on every platform. The resolution never
    consults the repository location, so there is no silent
    fallback to a repository-local directory.
    """
    if data_root is not None:
        if not isinstance(data_root, str) or not data_root.strip():
            raise ProfileError(
                "data_root override must be a non-empty string")
        return os.path.abspath(os.path.expanduser(data_root))
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("LOCALAPPDATA")
        if not base:
            raise ProfileError(
                "LOCALAPPDATA is not set — cannot resolve the local "
                "data root on Windows (no repository-local fallback)")
        return os.path.join(base, APP_DIR_NAME)
    home = os.path.expanduser("~")
    if not home or home == "~":
        raise ProfileError(
            "cannot resolve the home directory — cannot resolve the "
            "local data root (no repository-local fallback)")
    if system == "Darwin":
        return os.path.join(home, "Library", "Application Support",
                            APP_DIR_NAME)
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg and os.path.isabs(xdg):
        return os.path.join(xdg, APP_DIR_NAME)
    return os.path.join(home, ".local", "share", APP_DIR_NAME)


# ---------------------------------------------------------------------------
# Installation profile (Tasks A + E)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class InstallationProfile:
    """The validated local installation identity.

    Immutable data: ``owner_id`` / ``workspace_id`` are the stable
    opaque IDs from the profile file, ``data_root`` is the resolved
    data root, ``profile_path`` is the profile file's location.
    Trust in a profile object comes from obtaining it through
    :func:`load_or_create_profile` (which validates the file on
    disk), not from its type — see the module docstring.
    """
    owner_id: str
    workspace_id: str
    data_root: str
    profile_path: str

    def __post_init__(self):
        if not _is_valid_opaque_id(self.owner_id):
            raise ProfileError(
                f"owner_id {self.owner_id!r} is not a valid opaque "
                "local identifier")
        if not _is_valid_opaque_id(self.workspace_id):
            raise ProfileError(
                f"workspace_id {self.workspace_id!r} is not a valid "
                "opaque local identifier")
        if not isinstance(self.data_root, str) or not self.data_root:
            raise ProfileError("data_root must be a non-empty string")
        if not isinstance(self.profile_path, str) \
                or not self.profile_path:
            raise ProfileError(
                "profile_path must be a non-empty string")


def _ensure_private_dir(path: str) -> None:
    """Create ``path`` as a private directory (POSIX mode 0700) or
    verify the existing directory. A symlink at the path is
    refused outright — a symlinked data directory is not a valid
    private directory. Permission tightening is best-effort on
    filesystems that do not support POSIX modes (see the runtime
    doc for the Windows limitation); a failure to chmod never
    silently converts a valid directory into an error, but the
    directory is never created with loose default permissions on
    a POSIX system."""
    if os.path.islink(path):
        raise ProfileError(
            f"data directory {path!r} is a symlink — refusing to "
            "use a symlinked data directory as a private profile "
            "location")
    if not os.path.exists(path):
        os.makedirs(path, mode=0o700)
    elif not os.path.isdir(path):
        raise ProfileError(
            f"data location {path!r} exists and is not a directory")
    if os.name == "posix":
        try:
            os.chmod(path, 0o700)
        except OSError:
            # Filesystems without POSIX permission support (e.g. a
            # mounted FAT volume): the directory is still usable,
            # but the limitation is documented, not hidden.
            pass


def _profile_path(data_root: str) -> str:
    """The profile file path inside ``data_root``, validated with
    the P0 private-path resolver: traversal, absolute paths and
    symlink escapes are rejected. The file itself must not be a
    symlink — :func:`resolve_private_path` resolves existing
    components, so an unexpected symlink at the file is checked
    separately by the caller."""
    path, errors = asset_policy.resolve_private_path(
        data_root, PROFILE_FILENAME)
    if errors:
        raise ProfileError(
            "cannot resolve the installation profile path: "
            + "; ".join(errors))
    return path


def _validate_profile_data(data) -> tuple[str, str]:
    """Strict validation of parsed profile JSON. Returns
    (owner_id, workspace_id). Anything else — wrong type, missing
    or extra fields, wrong schema version, malformed IDs — is a
    ProfileError (fail closed, never silently repaired)."""
    if not isinstance(data, dict):
        raise ProfileError(
            "installation profile is corrupt: the profile file "
            "must contain a JSON object")
    expected = {"schema_version", "owner_id", "workspace_id"}
    keys = set(data)
    if keys != expected:
        missing = sorted(expected - keys)
        extra = sorted(keys - expected)
        detail = []
        if missing:
            detail.append(f"missing field(s): {', '.join(missing)}")
        if extra:
            detail.append(f"unexpected field(s): {', '.join(extra)}")
        raise ProfileError(
            "installation profile is invalid: " + "; ".join(detail))
    version = data["schema_version"]
    if type(version) is not int or version != PROFILE_SCHEMA_VERSION:
        raise ProfileError(
            "installation profile is invalid: schema_version must "
            f"be {PROFILE_SCHEMA_VERSION}, got {version!r}")
    owner_id = data["owner_id"]
    workspace_id = data["workspace_id"]
    if not _is_valid_opaque_id(owner_id):
        raise ProfileError(
            "installation profile is invalid: owner_id is not a "
            "valid opaque local identifier")
    if not _is_valid_opaque_id(workspace_id):
        raise ProfileError(
            "installation profile is invalid: workspace_id is not "
            "a valid opaque local identifier")
    return owner_id, workspace_id


def _read_profile(path: str) -> tuple[str, str]:
    """Read and strictly validate the profile file at ``path``.
    A symlink at the path is refused before any read. The file is
    never modified by a read, so a corrupt profile survives a
    failed load byte-for-byte."""
    if os.path.islink(path):
        raise ProfileError(
            f"installation profile {path!r} is a symlink — refusing "
            "to read a symlinked profile as if it were valid")
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError as exc:
        raise ProfileError(
            f"cannot read the installation profile {path!r}: {exc}")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ProfileError(
            "installation profile is corrupt: not valid JSON "
            f"({exc}) — refusing to replace it")
    return _validate_profile_data(data)


def _publish_profile_atomic(path: str, payload: dict) -> bool:
    """Publish ``payload`` as the profile at ``path`` exactly once
    (CF-WO-P1-001-R1, Task B).

    Atomic create-if-absent publication. The payload is written
    to an unguessable temporary file in the same directory
    (exclusive creation via ``tempfile.mkstemp`` — O_CREAT |
    O_EXCL — mode 0600 on POSIX, flushed + fsynced), then
    published with ``os.link()``: a single atomic filesystem
    operation that FAILS with FileExistsError when ``path``
    already exists, so it can never overwrite another process's
    profile. On Windows the temporary file is not chmodded:
    Windows Python 3.10-3.12 does not expose ``os.fchmod``, so
    the call is capability-checked (``hasattr(os, "fchmod")``)
    and skipped there — the file instead inherits the user data
    directory's Windows security/ACL behaviour. No POSIX
    0600 semantics are claimed on Windows (see the
    trust-boundary doc). Returns True when this call published
    the profile; False when another process published first
    (the temporary file is removed either way, so no artefact
    remains). Any other failure raises OSError, with the
    temporary file removed and ``path`` untouched. A crash
    before the link leaves only a temporary file — never a
    partially written profile at the final path — and the next
    load reads whatever is actually at ``path`` (a valid
    profile, or a fail-closed corrupt one), never a half-written
    one. The P0 ``scripts/atomic_write.py`` helper is
    deliberately NOT used here: its ``os.replace()``
    unconditionally overwrites the target, which is exactly the
    race being closed; the helper itself is unchanged.
    """
    parent = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=parent, prefix=".profile-",
                               suffix=".tmp")
    try:
        # POSIX only, capability-checked: tighten the temporary
        # file to 0600. Windows Python 3.10-3.12 has no
        # os.fchmod — the check (not a broad AttributeError
        # swallow) skips the call there, and the file inherits
        # the user data directory's Windows ACL instead. A
        # missing fchmod is the only tolerated absence; any
        # other failure still raises.
        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        try:
            f = os.fdopen(fd, "wb")
        except BaseException:
            os.close(fd)
            raise
        blob = (json.dumps(payload, indent=2, sort_keys=True)
                + "\n").encode("utf-8")
        with f:
            f.write(blob)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.link(tmp, path)
        except FileExistsError:
            return False
        return True
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def load_or_create_profile(data_root=None) -> InstallationProfile:
    """Load the validated installation profile, creating it on
    first use.

    First use: fresh opaque IDs are generated and published with
    an atomic create-if-absent operation into a private
    directory (0700 directory and 0600 file on POSIX; on
    Windows the file inherits the user data directory's ACL —
    see :func:`_publish_profile_atomic`); the profile on disk
    is re-read and validated before it is returned — whether
    this process published it or another concurrent first run
    won (the winner's profile is loaded, the loser's candidate
    is discarded, nothing is overwritten). Later use: the existing profile is read and
    strictly validated — a corrupt, invalid or tampered profile
    raises ProfileError and is left untouched on disk. No
    repository-local fallback exists at any point in this
    function.
    """
    root = resolve_data_root(data_root)
    _ensure_private_dir(root)
    path = _profile_path(root)
    if os.path.lexists(path):
        if os.path.islink(path):
            raise ProfileError(
                f"installation profile {path!r} is a symlink — "
                "refusing to read or overwrite a symlinked profile")
        owner_id, workspace_id = _read_profile(path)
        return InstallationProfile(owner_id=owner_id,
                                   workspace_id=workspace_id,
                                   data_root=root, profile_path=path)
    # First use: generate a candidate identity, then publish it
    # atomically. A concurrent first run that published first
    # wins — the link fails with FileExistsError and the winner's
    # profile is loaded instead of being overwritten. No
    # check-then-write window exists: the link IS the atomic
    # decision point.
    owner_id = _new_opaque_id()
    workspace_id = _new_opaque_id()
    payload = {"schema_version": PROFILE_SCHEMA_VERSION,
               "owner_id": owner_id, "workspace_id": workspace_id}
    try:
        _publish_profile_atomic(path, payload)
    except OSError as exc:
        raise ProfileError(
            "cannot write the installation profile "
            f"{path!r}: {exc} — the previous profile (if any) is "
            "untouched")
    # Prove the profile on disk is valid before trusting it —
    # whether this process published it or another process won.
    # A corrupt winner fails closed here and stays untouched.
    owner_id, workspace_id = _read_profile(path)
    return InstallationProfile(owner_id=owner_id,
                               workspace_id=workspace_id,
                               data_root=root, profile_path=path)


# ---------------------------------------------------------------------------
# Process-bound sessions (Task B)
# ---------------------------------------------------------------------------
# Issuance registry — the P0-011 pattern, applied to sessions.
# A plain dict keyed by id() holding weak references; verification
# compares the stored reference's target with `is`, never with `==`
# and never through a hash of the candidate. See asset_policy.py
# (TrustedAuthorizationContext) for the full reasoning; the same
# attacks apply here (a forged subclass overriding __eq__/__hash__
# must never compare equal to a genuine session).

_ISSUED_SESSIONS: dict[int, "weakref.ref"] = {}

# Session IDs whose close has been processed. Keyed by the session
# ID string (a fresh uuid4 per session), never by id() — an id()
# could be reused by a later object after the session dies, but a
# session ID is never minted twice.
_CLOSED_SESSION_IDS: set = set()

# Handlers run when a session closes (e.g. the authorization
# module's revocation of that session's issued contexts). A handler
# receives the session object; the session is marked closed BEFORE
# any handler runs, so a failing handler can never leave the
# session active.
_SESSION_CLOSE_HANDLERS: list = []

_SESSION_BOUNDARY = object()


def _drop_issued_session(key, ref):
    """Weak-reference callback: remove the entry under `key` ONLY
    if it still holds this exact (now dead) reference — a newer
    registration that reused the id must survive."""
    if _ISSUED_SESSIONS.get(key) is ref:
        del _ISSUED_SESSIONS[key]


def _register_issued_session(session):
    """Register an issued session (factory only — the single
    registration path, called as start_session's last step after
    all validation and successful construction)."""
    key = id(session)
    _ISSUED_SESSIONS[key] = weakref.ref(
        session,
        lambda dead_ref, _key=key: _drop_issued_session(_key,
                                                        dead_ref))


def register_session_close_handler(handler) -> None:
    """Register a callable invoked with the session object when a
    session closes. Used by runtime.authorization to revoke the
    contexts a session issued. Handlers are process-local and run
    in registration order; the session is already closed when
    they run."""
    if not callable(handler):
        raise SessionError("session close handler must be callable")
    _SESSION_CLOSE_HANDLERS.append(handler)


class LocalSession:
    """A process-bound application session, issued by
    :func:`start_session` only.

    Fields: ``session_id`` (fresh uuid4 hex per session — an
    identifier, not a secret), ``owner_id`` / ``workspace_id``
    (bound from the validated installation profile),
    ``created_at`` / ``expires_at`` (ISO-8601 UTC strings; the
    session is inactive at or after ``expires_at``).

    The trust rules are the P0-009 / P0-010 / P0-011 rules,
    applied to sessions: the instance is genuinely immutable
    after issuance (frozen flag enforced by ``__setattr__`` /
    ``__delattr__``; no ``__dict__``); equality and hashing are
    identity-based (``__eq__`` is ``is``); serialization is
    refused outright (``__reduce__`` / ``__reduce_ex__`` /
    ``__getstate__`` / ``__setstate__`` raise TypeError); copies
    are frozen but UNREGISTERED clones with no authority; and —
    crucially — only the exact object registered by
    :func:`start_session` is ever accepted, verified by
    :func:`is_active_session` through the ``id()``-keyed weak
    reference registry with an ``is`` comparison. A directly
    constructed, ``__new__``-built, copied, deserialized or
    subclass object is never in the registry and is always
    rejected, however genuine its fields look.
    """
    __slots__ = ("session_id", "owner_id", "workspace_id",
                 "created_at", "expires_at", "_frozen", "__weakref__")

    _DATA_SLOTS = ("session_id", "owner_id", "workspace_id",
                   "created_at", "expires_at", "_frozen")

    def __init_subclass__(cls, **kwargs):
        # Defence-in-depth only (same pattern as P0-011): the
        # verifier independently requires the exact concrete
        # type, so even a subclass instance built through an
        # unusual or low-level mechanism is still rejected.
        raise TypeError(
            "LocalSession cannot be subclassed — only the exact "
            "object issued by start_session() is trusted")

    def __eq__(self, other):
        # Identity equality ONLY: two sessions with identical
        # fields are still distinct objects.
        return self is other

    def __ne__(self, other):
        return not self.__eq__(other)

    __hash__ = object.__hash__

    def __init__(self, *, _boundary, session_id, owner_id,
                 workspace_id, created_at, expires_at):
        if _boundary is not _SESSION_BOUNDARY:
            raise TypeError(
                "LocalSession must be issued by start_session() — "
                "the local application session factory — never "
                "constructed directly")
        object.__setattr__(self, "session_id", session_id)
        object.__setattr__(self, "owner_id", owner_id)
        object.__setattr__(self, "workspace_id", workspace_id)
        object.__setattr__(self, "created_at", created_at)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(self, "_frozen", True)

    def __setattr__(self, name, value):
        if getattr(self, "_frozen", False):
            raise AttributeError(
                "LocalSession is immutable after issuance — cannot "
                f"reassign {name!r} (start a new session instead)")
        object.__setattr__(self, name, value)

    def __delattr__(self, name):
        if getattr(self, "_frozen", False):
            raise AttributeError(
                "LocalSession is immutable after issuance — cannot "
                f"delete {name!r}")
        object.__delattr__(self, name)

    def _frozen_copy(self, deep=False, memo=None):
        """A frozen copy with the same field values (internal
        only). Deliberately NOT registered: a copy looks like the
        original but has no authority and is rejected by every
        session consumer, because only the exact issued instance
        is trusted."""
        clone = object.__new__(type(self))
        for slot in self._DATA_SLOTS:
            value = getattr(self, slot)
            if deep:
                value = copy.deepcopy(value, memo)
            object.__setattr__(clone, slot, value)
        object.__setattr__(clone, "_frozen", True)
        return clone

    def __copy__(self):
        return self._frozen_copy()

    def __deepcopy__(self, memo):
        return self._frozen_copy(deep=True, memo=memo)

    def __getstate__(self):
        raise TypeError(
            "LocalSession cannot be serialized — a session is "
            "process-local issuance state, not transferable data "
            "(start a new session instead)")

    def __setstate__(self, state):
        raise TypeError(
            "LocalSession cannot be restored from serialized state "
            "— only start_session() may create a session")

    def __reduce__(self):
        raise TypeError(
            "LocalSession cannot be pickled — a session is "
            "process-local issuance state, not transferable data "
            "(start a new session instead)")

    def __reduce_ex__(self, protocol):
        raise TypeError(
            "LocalSession cannot be pickled — a session is "
            "process-local issuance state, not transferable data "
            "(start a new session instead)")


def start_session(profile, workspace_id, *,
                  lifetime_seconds=DEFAULT_SESSION_LIFETIME_SECONDS):
    """Start a fresh process-bound session from a validated
    installation profile.

    ``profile`` must be an :class:`InstallationProfile` (normally
    obtained from :func:`load_or_create_profile`); ``workspace_id``
    must be passed explicitly and must equal the profile's
    workspace — this installation holds exactly one workspace in
    this work order, and a session for a workspace the
    installation does not hold is rejected rather than invented.
    ``lifetime_seconds`` is the finite session lifetime (default
    12 hours, at most 24 hours). The session ID is minted fresh
    on every call; the session is registered as the factory's
    last step and returned. Sessions are never written to disk.
    """
    if not isinstance(profile, InstallationProfile):
        raise SessionError(
            "start_session requires an InstallationProfile from "
            "load_or_create_profile()")
    if not _is_valid_opaque_id(workspace_id):
        raise SessionError(
            f"workspace_id {workspace_id!r} is not a valid opaque "
            "local identifier")
    if workspace_id != profile.workspace_id:
        raise SessionError(
            "workspace_id does not match the installation profile's "
            "workspace — this installation holds exactly one "
            "workspace; a session for another workspace is refused")
    if type(lifetime_seconds) is not int or lifetime_seconds < 1 \
            or lifetime_seconds > MAX_SESSION_LIFETIME_SECONDS:
        raise SessionError(
            "lifetime_seconds must be an integer between 1 and "
            f"{MAX_SESSION_LIFETIME_SECONDS}")
    now = datetime.now(timezone.utc)
    created_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    expires_at = (now + timedelta(seconds=lifetime_seconds)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    session = LocalSession(
        _boundary=_SESSION_BOUNDARY,
        session_id=uuid.uuid4().hex,
        owner_id=profile.owner_id,
        workspace_id=workspace_id,
        created_at=created_at,
        expires_at=expires_at)
    _register_issued_session(session)
    return session


def is_active_session(session) -> bool:
    """True ONLY for the exact object issued by
    :func:`start_session`, that has not been closed and has not
    expired. The single session verifier — the same contract as
    P0-011's context verifier: exact concrete type, then the
    ``id()``-keyed weak-reference registry checked with ``is``.
    No untrusted method runs during verification: ``type()``,
    ``id()`` and the int-keyed dict lookup never invoke the
    candidate's ``__eq__`` or ``__hash__``. A dead registry entry
    met during lookup is pruned (only if it is still that exact
    ref) and the check fails closed. A forged object is never
    reported as active, and a non-session is never reported as
    active."""
    if type(session) is not LocalSession:
        return False
    ref = _ISSUED_SESSIONS.get(id(session))
    if ref is None:
        return False
    target = ref()
    if target is None:
        if _ISSUED_SESSIONS.get(id(session)) is ref:
            del _ISSUED_SESSIONS[id(session)]
        return False
    if target is not session:
        return False
    if session.session_id in _CLOSED_SESSION_IDS:
        return False
    if session.expires_at <= _utc_now_iso():
        return False
    return True


def validate_session(session) -> list[str]:
    """Return rejection reasons for ``session``; empty list means
    the session is active and usable. Fails closed and never
    raises for hostile input: field values are read only after
    the issuance check has proved the object genuine."""
    if type(session) is not LocalSession:
        return ["not a LocalSession issued by start_session()"]
    ref = _ISSUED_SESSIONS.get(id(session))
    if ref is None or ref() is not session:
        return ["session was not issued by start_session()"]
    if session.session_id in _CLOSED_SESSION_IDS:
        return ["session is closed"]
    if session.expires_at <= _utc_now_iso():
        return [f"session expired at {session.expires_at}"]
    return []


def close_session(session) -> bool:
    """Close (shut down) a session issued by :func:`start_session`.

    Returns True when this call closed the session, False when it
    was already closed. Raises SessionError for anything that is
    not an issued session — a forged object can never be
    "closed". The session is marked closed BEFORE any registered
    close handler runs, so a failing handler can never leave the
    session active; the first handler exception (if any) is
    re-raised after all handlers have run. Closing is permanent:
    a closed session is never active again, and a restart must
    start a new session. Sessions are process-local, so closing
    here does not affect any other process.
    """
    if type(session) is not LocalSession:
        raise SessionError(
            "only a LocalSession issued by start_session() can be "
            "closed")
    ref = _ISSUED_SESSIONS.get(id(session))
    if ref is None or ref() is not session:
        raise SessionError(
            "only a LocalSession issued by start_session() can be "
            "closed")
    if session.session_id in _CLOSED_SESSION_IDS:
        return False
    _CLOSED_SESSION_IDS.add(session.session_id)
    first_error = None
    for handler in list(_SESSION_CLOSE_HANDLERS):
        try:
            handler(session)
        except Exception as exc:  # noqa: BLE001 - close must finish
            if first_error is None:
                first_error = exc
    if first_error is not None:
        raise first_error
    return True
