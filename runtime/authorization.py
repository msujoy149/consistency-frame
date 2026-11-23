#!/usr/bin/env python3
"""Consistency Frame P1 — authorization bridge and trusted private-voice
export issuance (CF-WO-P1-001, Tasks C + D).

Every authorization decision in this module takes actor identity
EXCLUSIVELY from a verified :class:`runtime.local_session.LocalSession`
— never from caller-provided strings or authorization dictionaries —
and delegates the decision itself to the existing P0 policy,
``scripts/asset_policy.py::authorize_action``. No ownership or
sharing rule is duplicated here: the P0 policy remains the single
policy source, and this module is only the session-aware front door
to it.

Trusted private-voice export issuance goes through the P0 factory
(``issue_trusted_authorization_context``) and only through it: an
active runtime-issued session, validated against the voice's
structured ownership, plus an explicit owner approval delivered
through a narrow callback (the UI-confirmation seam — see below),
binds the resulting context to the exact Character ID and Voice
Profile ID with a short, finite expiry. Provider transmission is a
separate permission with a distinct approval: an export approval
never sets ``provider_transmission_approved``.

The approval callback is the narrow interface where a future
application UI confirms the action with the owner. Its protocol:
``approve_callback(action, *, character_id, voice_profile_id,
scope) -> bool`` — ``action`` is ``"export_private_asset"`` for an
export request and ``"transmit_to_provider"`` for a provider
transmission request; it must return True only after the owner
explicitly approved exactly that action for exactly those assets.
A callback that returns a falsy value, is not callable, or raises
is treated as NO approval (fail closed — nothing is issued). This
module does NOT pretend a full graphical registration or approval
UI exists.

Session shutdown revokes that session's live contexts: this module
registers a session-close handler with
:func:`runtime.local_session.register_session_close_handler` at
import time, so :func:`runtime.local_session.close_session` revokes
every still-live context the session issued. Closing a session IS
its shutdown. (That revocation only happens if this module has been
imported — the application entry point must import
``runtime.authorization`` before closing sessions that issued
contexts. Contexts also carry a short finite expiry, so a context
can never outlive its expiry even if revocation were missed.)

All decisions fail closed: an invalid session, missing identity,
malformed ownership, unknown action, missing approval, or any
validation failure means no authorization and no issuance.
"""

from __future__ import annotations

import weakref
from datetime import datetime, timedelta, timezone

from . import local_session

import asset_policy  # noqa: E402  (sys.path set up by local_session)

# Export authorizations are short-lived by design: 5 minutes by
# default, at most 1 hour. An authorization that outlives the owner's
# attention is a liability, not a feature.
DEFAULT_EXPORT_LIFETIME_SECONDS = 300
MAX_EXPORT_LIFETIME_SECONDS = 3600


def _utc_iso(moment) -> str:
    """Format a datetime as an ISO-8601 'Z' string (the format the
    P0 factory validates)."""
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Per-session issued-context tracking (Task D)
# ---------------------------------------------------------------------------
# session_id -> list of weak references to the contexts that session
# issued. Weak references only: tracking must never pin a context in
# memory, and a context that died is simply gone (its authority died
# with it — the P0 issuance registry holds weak references too).
_SESSION_CONTEXTS: dict[str, list] = {}


def _track_context(session_id: str, context) -> None:
    _SESSION_CONTEXTS.setdefault(session_id, []).append(
        weakref.ref(context))


def issued_contexts_for_session(session) -> list:
    """Return the still-live contexts issued by ``session``.
    Raises ValueError for anything that is not a session issued by
    ``start_session()``. Revoked contexts are still listed until
    the session closes (revocation is recorded in the P0
    revocation registry, not by removing the tracking entry)."""
    if type(session) is not local_session.LocalSession:
        raise ValueError(
            "only a LocalSession issued by start_session() has "
            "tracked contexts")
    refs = _SESSION_CONTEXTS.get(session.session_id, [])
    live = []
    for ref in list(refs):
        context = ref()
        if context is not None and \
                asset_policy.is_factory_issued_trusted_authorization_context(
                    context):
            live.append(context)
    return live


def _revoke_contexts_for_session(session) -> None:
    """Session-close handler: revoke every still-live context the
    session issued. Dead references are skipped; revocation is
    idempotent (the P0 revocation registry is a set)."""
    refs = _SESSION_CONTEXTS.pop(session.session_id, [])
    for ref in refs:
        context = ref()
        if context is None:
            continue
        if asset_policy.is_factory_issued_trusted_authorization_context(
                context):
            asset_policy.revoke_trusted_authorization_context(context)


# Registered at import time: closing a session revokes its contexts.
local_session.register_session_close_handler(
    _revoke_contexts_for_session)


# ---------------------------------------------------------------------------
# Authorization bridge (Task C)
# ---------------------------------------------------------------------------

def authorize(session, action, ownership) -> list[str]:
    """Authorize one action for the actor bound to ``session``.

    Returns rejection reasons; [] = allowed. The session must be
    an exact, active runtime-issued session (checked by
    :func:`local_session.is_active_session`); ``owner_id`` and
    ``workspace_id`` come ONLY from that session. There is no
    parameter for caller-provided identity — a caller that tries
    to pass ``requesting_owner_id`` / ``requesting_workspace_id``
    gets a TypeError from the signature itself. The decision is
    delegated to ``asset_policy.authorize_action``; this module
    adds no rule of its own.
    """
    if not local_session.is_active_session(session):
        return ["authorization refused: the session is not an "
                "active session issued by start_session() — a "
                "missing, closed, expired, copied, forged or "
                "otherwise unissued session authorizes nothing"]
    return asset_policy.authorize_action(
        action, ownership, session.owner_id, session.workspace_id)


# ---------------------------------------------------------------------------
# Trusted private-voice export issuance (Task D)
# ---------------------------------------------------------------------------

def _issue(session, voice, *, scope, approve_callback,
           lifetime_seconds, provider_transmission: bool,
           approval_action: str):
    """Shared issuance path for export and provider transmission.
    Raises ValueError on every failure (fail closed — no context
    is issued, and no partial authorization exists)."""
    if not local_session.is_active_session(session):
        raise ValueError(
            "export authorization refused: the session is not an "
            "active session issued by start_session()")
    if not isinstance(voice, dict):
        raise ValueError("voice profile must be an object")
    ownership = voice.get("ownership")
    ownership_errors = asset_policy.validate_ownership(ownership)
    if ownership_errors:
        raise ValueError(
            "export authorization refused: the voice profile has "
            "no valid ownership binding — " + "; ".join(
                ownership_errors))
    if session.owner_id != ownership.get("owner_id"):
        raise ValueError(
            "export authorization refused: the session owner is "
            "not the voice owner — private export is owner-only")
    if session.workspace_id != ownership.get("workspace_id"):
        raise ValueError(
            "export authorization refused: the session workspace "
            "is not the voice workspace")
    character_id = voice.get("character_id")
    voice_profile_id = voice.get("voice_profile_id")
    for field, value in (("character_id", character_id),
                         ("voice_profile_id", voice_profile_id)):
        if not isinstance(value, str) or not value:
            raise ValueError(
                f"export authorization refused: the voice profile "
                f"has no {field}")
        if not local_session._is_valid_opaque_id(value):
            raise ValueError(
                "export authorization refused: "
                f"{field} {value!r} is not a valid opaque local "
                "identifier")
    if not isinstance(scope, str) or not scope.strip():
        raise ValueError(
            "export authorization refused: scope must be a "
            "non-empty string")
    if type(lifetime_seconds) is not int or lifetime_seconds < 1 \
            or lifetime_seconds > MAX_EXPORT_LIFETIME_SECONDS:
        raise ValueError(
            "export authorization refused: lifetime_seconds must "
            "be an integer between 1 and "
            f"{MAX_EXPORT_LIFETIME_SECONDS} (short, finite expiry)")
    if not callable(approve_callback):
        raise ValueError(
            "export authorization refused: an explicit owner "
            "approval callback is required")
    try:
        approved = approve_callback(
            approval_action, character_id=character_id,
            voice_profile_id=voice_profile_id, scope=scope)
    except Exception:
        # A failing approval callback is NO approval (fail
        # closed). The exception is not propagated: issuance is
        # refused, and the caller learns only that approval was
        # not obtained.
        raise ValueError(
            "export authorization refused: the owner approval "
            "callback failed — treated as no approval")
    if not approved:
        raise ValueError(
            "export authorization refused: the owner did not "
            "explicitly approve this export")
    expires_at = _utc_iso(datetime.now(timezone.utc)
                          + timedelta(seconds=lifetime_seconds))
    context = asset_policy.issue_trusted_authorization_context(
        actor_owner_id=session.owner_id,
        actor_workspace_id=session.workspace_id,
        granted_by=session.owner_id,
        scope=scope,
        action="export_private_asset",
        character_id=character_id,
        voice_profile_id=voice_profile_id,
        provider_transmission_approved=bool(provider_transmission),
        expires_at=expires_at)
    _track_context(session.session_id, context)
    return context


def request_voice_export_authorization(
        session, voice, *, scope, approve_callback,
        lifetime_seconds=DEFAULT_EXPORT_LIFETIME_SECONDS):
    """Issue a trusted private-voice export authorization.

    Requires an active runtime-issued session whose owner and
    workspace match the voice's structured ownership, and an
    explicit owner approval through ``approve_callback``. The
    issued context is bound to the exact Character ID and Voice
    Profile ID from the voice record, carries a short finite
    expiry, and NEVER permits provider transmission
    (``provider_transmission_approved`` is always False here —
    an export approval must never silently authorize sending
    the voice to an external provider; use
    :func:`request_provider_transmission_authorization` with its
    own distinct approval for that). Raises ValueError on any
    failure; no context is issued.
    """
    return _issue(session, voice, scope=scope,
                  approve_callback=approve_callback,
                  lifetime_seconds=lifetime_seconds,
                  provider_transmission=False,
                  approval_action="export_private_asset")


def request_provider_transmission_authorization(
        session, voice, *, scope, approve_callback,
        lifetime_seconds=DEFAULT_EXPORT_LIFETIME_SECONDS):
    """Issue a trusted authorization that ALSO permits sending
    the voice to an external provider.

    This is a SEPARATE permission from export: it requires its
    own distinct explicit owner approval (the callback is
    invoked with action ``"transmit_to_provider"``), and it is
    the only path that sets ``provider_transmission_approved``.
    All other requirements are identical to
    :func:`request_voice_export_authorization` (active session,
    ownership match, exact Character/Voice binding, short
    finite expiry). Raises ValueError on any failure.
    """
    return _issue(session, voice, scope=scope,
                  approve_callback=approve_callback,
                  lifetime_seconds=lifetime_seconds,
                  provider_transmission=True,
                  approval_action="transmit_to_provider")
