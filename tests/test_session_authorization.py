#!/usr/bin/env python3
"""CF-WO-P1-001 — session authorization bridge regression suite.

Tests the production code in runtime/authorization.py (the bridge
to the P0 policy in scripts/asset_policy.py and the trusted
private-voice export issuance path) plus the P0 behaviour pins
that prove the existing authorization functions are unchanged.
Every check executes production code against isolated temporary
directories and synthetic IDs/assets; no real character data,
voice data, credentials, or network use.

Test IDs: CF-P1-001-AUTH (bridge), CF-P1-001-EXP (export
issuance), CF-P1-001-P0 (P0 behaviour unchanged),
CF-P1-001-R1-ENUM (R1: context enumeration requires an exact
active session — no unissued object recovers a context).

Run: python3 tests/test_session_authorization.py
Exit 0 = PASS, 1 = FAIL.
"""

import copy
import os
import shutil
import sys
import tempfile
import time
from types import SimpleNamespace

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, ROOT)
import asset_policy  # noqa: E402
from runtime import authorization, local_session  # noqa: E402
from runtime.local_session import (  # noqa: E402
    InstallationProfile, close_session, is_active_session,
    load_or_create_profile, start_session)

failures = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def _voice(owner_id, workspace_id, character_id="char-test-001",
           voice_profile_id="voice-test-001", visibility="private",
           sharing="none"):
    """A minimal synthetic private voice profile with structured
    ownership (no real character or voice data)."""
    return {"character_id": character_id,
            "voice_profile_id": voice_profile_id,
            "ownership": {"owner_id": owner_id,
                          "workspace_id": workspace_id,
                          "visibility": visibility,
                          "sharing": sharing}}


def _approve_yes(action, **kwargs):
    return True


def _approve_no(action, **kwargs):
    return False


def _approve_boom(action, **kwargs):
    raise RuntimeError("approval UI crashed")


def main():
    tmp_roots = []

    def new_root():
        root = tempfile.mkdtemp(prefix="cf-p1-001-auth-")
        tmp_roots.append(root)
        return root

    try:
        profile_a = load_or_create_profile(new_root())
        profile_b = load_or_create_profile(new_root())
        session_a = start_session(profile_a, profile_a.workspace_id)
        session_b = start_session(profile_b, profile_b.workspace_id)
        voice_a = _voice(profile_a.owner_id, profile_a.workspace_id)
        voice_b = _voice(profile_b.owner_id, profile_b.workspace_id)

        # ----------------------------------------------------------
        # Authorization bridge (CF-P1-001-AUTH)
        # ----------------------------------------------------------
        allowed_all = all(
            authorization.authorize(session_a, scope,
                                    voice_a["ownership"]) == []
            for scope in asset_policy.ACTION_SCOPES)
        check("CF-P1-001-AUTH-01: correct owner and workspace can "
              "perform every allowed action", allowed_all)

        check("CF-P1-001-AUTH-02: wrong owner is rejected",
              bool(authorization.authorize(
                  session_b, "use_in_project", voice_a["ownership"])))
        wrong_ws_ownership = {"owner_id": profile_a.owner_id,
                              "workspace_id": "workspace-other01",
                              "visibility": "private", "sharing": "none"}
        check("CF-P1-001-AUTH-03: wrong workspace is rejected",
              bool(authorization.authorize(
                  session_a, "use_in_project", wrong_ws_ownership)))
        check("CF-P1-001-AUTH-04: missing session is rejected",
              bool(authorization.authorize(
                  None, "use_in_project", voice_a["ownership"])))
        check("CF-P1-001-AUTH-05: a dict is not a session",
              bool(authorization.authorize(
                  {"owner_id": profile_a.owner_id,
                   "workspace_id": profile_a.workspace_id},
                  "use_in_project", voice_a["ownership"])))
        forged = SimpleNamespace(
            session_id=session_a.session_id,
            owner_id=session_a.owner_id,
            workspace_id=session_a.workspace_id,
            created_at=session_a.created_at,
            expires_at=session_a.expires_at)
        check("CF-P1-001-AUTH-06: forged session is rejected",
              bool(authorization.authorize(
                  forged, "use_in_project", voice_a["ownership"])))
        closed = start_session(profile_a, profile_a.workspace_id)
        close_session(closed)
        check("CF-P1-001-AUTH-07: closed session is rejected",
              bool(authorization.authorize(
                  closed, "use_in_project", voice_a["ownership"])))
        expired = start_session(profile_a, profile_a.workspace_id,
                                lifetime_seconds=1)
        time.sleep(2.0)
        check("CF-P1-001-AUTH-08: expired session is rejected",
              bool(authorization.authorize(
                  expired, "use_in_project", voice_a["ownership"])))
        try:
            authorization.authorize(
                session_a, "use_in_project", voice_a["ownership"],
                requesting_owner_id=profile_b.owner_id)
            raised = False
        except TypeError:
            raised = True
        check("CF-P1-001-AUTH-09: caller-provided identity fields "
              "cannot override session identity", raised)
        check("CF-P1-001-AUTH-10: unknown action is rejected",
              bool(authorization.authorize(
                  session_a, "dance", voice_a["ownership"])))
        check("CF-P1-001-AUTH-11: malformed ownership is rejected",
              bool(authorization.authorize(
                  session_a, "use_in_project",
                  {"owner_id": profile_a.owner_id})))

        # Shared + workspace asset: another owner in the SAME
        # workspace is admitted by the P0 policy (delegation, not
        # a runtime rule). The session is started from a directly
        # constructed valid profile (profile data, same IDs).
        shared_voice = _voice(profile_a.owner_id,
                              profile_a.workspace_id,
                              visibility="shared", sharing="workspace")
        profile_b_same_ws = InstallationProfile(
            owner_id=profile_b.owner_id,
            workspace_id=profile_a.workspace_id,
            data_root=new_root(),
            profile_path=os.path.join(new_root(), "profile.json"))
        session_b_same_ws = start_session(
            profile_b_same_ws, profile_a.workspace_id)
        check("CF-P1-001-AUTH-12: shared-workspace access follows the "
              "P0 policy (same workspace, other owner)",
              authorization.authorize(
                  session_b_same_ws, "use_in_project",
                  shared_voice["ownership"]) == []
              and bool(authorization.authorize(
                  session_b_same_ws, "use_in_project",
                  voice_a["ownership"])))

        # ----------------------------------------------------------
        # Trusted export issuance (CF-P1-001-EXP)
        # ----------------------------------------------------------
        ctx = authorization.request_voice_export_authorization(
            session_a, voice_a, scope="export voice-test-001 for backup",
            approve_callback=_approve_yes)
        check("CF-P1-001-EXP-01: export issuance with approval succeeds",
              asset_policy.is_factory_issued_trusted_authorization_context(
                  ctx)
              and ctx.character_id == "char-test-001"
              and ctx.voice_profile_id == "voice-test-001"
              and ctx.provider_transmission_approved is False
              and ctx.expires_at is not None)
        check("CF-P1-001-EXP-01b: issued export validates at the P0 "
              "boundary",
              asset_policy.validate_private_voice_export(
                  voice_a, trusted_context=ctx) == [])
        check("CF-P1-001-EXP-02: export without approval is rejected",
              _no_context(session_a, voice_a, _approve_no))
        check("CF-P1-001-EXP-03: export for another Character ID is "
              "rejected",
              bool(asset_policy.validate_private_voice_export(
                  _voice(profile_a.owner_id, profile_a.workspace_id,
                         character_id="char-other-001"),
                  trusted_context=ctx)))
        check("CF-P1-001-EXP-04: export for another Voice Profile ID "
              "is rejected",
              bool(asset_policy.validate_private_voice_export(
                  _voice(profile_a.owner_id, profile_a.workspace_id,
                         voice_profile_id="voice-other-001"),
                  trusted_context=ctx)))
        check("CF-P1-001-EXP-05: provider transmission without separate "
              "approval is rejected",
              bool(asset_policy.validate_private_voice_export(
                  voice_a, trusted_context=ctx, to_provider=True)))
        tx_ctx = authorization.\
            request_provider_transmission_authorization(
                session_a, voice_a,
                scope="send voice-test-001 to provider",
                approve_callback=_approve_yes)
        check("CF-P1-001-EXP-06: transmission with separate approval "
              "validates for provider use",
              tx_ctx.provider_transmission_approved is True
              and asset_policy.validate_private_voice_export(
                  voice_a, trusted_context=tx_ctx,
                  to_provider=True) == [])
        check("CF-P1-001-EXP-07: transmission without its own approval "
              "is rejected",
              _no_context_tx(session_a, voice_a, _approve_no))
        check("CF-P1-001-EXP-08: export approval never sets the "
              "transmission flag",
              ctx.provider_transmission_approved is False)
        check("CF-P1-001-EXP-09: approval callback failure is no "
              "approval",
              _no_context(session_a, voice_a, _approve_boom))
        check("CF-P1-001-EXP-10: non-callable approval is rejected",
              _no_context(session_a, voice_a, "yes"))
        check("CF-P1-001-EXP-11: empty scope is rejected",
              _no_context_scope(session_a, voice_a))
        check("CF-P1-001-EXP-12: export lifetime is short and finite",
              _export_lifetime_ok(ctx)
              and _bad_lifetime_rejected(session_a, voice_a))

        short_ctx = authorization.request_voice_export_authorization(
            session_a, voice_a, scope="short-lived export",
            approve_callback=_approve_yes, lifetime_seconds=1)
        time.sleep(2.0)
        check("CF-P1-001-EXP-13: expired context is rejected",
              bool(asset_policy.validate_private_voice_export(
                  voice_a, trusted_context=short_ctx)))

        check("CF-P1-001-EXP-14: plain dict authorization is rejected",
              bool(asset_policy.validate_private_voice_export(
                  voice_a,
                  authorization={"granted_by": profile_a.owner_id,
                                 "scope": "export",
                                 "explicit_authorisation": True})))
        forged_ctx = copy.copy(ctx)
        check("CF-P1-001-EXP-15: copied (forged) context is rejected",
              bool(asset_policy.validate_private_voice_export(
                  voice_a, trusted_context=forged_ctx)))

        # Shutdown revokes everything the session issued.
        ctx2 = authorization.request_voice_export_authorization(
            session_a, voice_a, scope="second export",
            approve_callback=_approve_yes)
        tracked_before = authorization.issued_contexts_for_session(
            session_a)
        check("CF-P1-001-EXP-16: issued contexts are tracked per session",
              len(tracked_before) == 4
              and set(c.authorization_id for c in tracked_before)
              == {ctx.authorization_id, tx_ctx.authorization_id,
                  short_ctx.authorization_id, ctx2.authorization_id})

        # ----------------------------------------------------------
        # R1: context enumeration requires exact active issuance
        # (CF-P1-001-R1-ENUM)
        # ----------------------------------------------------------
        check("CF-P1-001-R1-ENUM-01: genuine active session enumerates "
              "its own issued contexts",
              len(tracked_before) == 4
              and set(c.authorization_id
                      for c in authorization.issued_contexts_for_session(
                          session_a))
              == {ctx.authorization_id, tx_ctx.authorization_id,
                  short_ctx.authorization_id, ctx2.authorization_id})
        check("CF-P1-001-R1-ENUM-02: copy.copy(session) cannot "
              "enumerate contexts",
              _enum_refused(copy.copy(session_a)))
        check("CF-P1-001-R1-ENUM-03: copy.deepcopy(session) cannot "
              "enumerate contexts",
              _enum_refused(copy.deepcopy(session_a)))
        built_enum = object.__new__(local_session.LocalSession)
        for slot, value in (
                ("session_id", session_a.session_id),
                ("owner_id", session_a.owner_id),
                ("workspace_id", session_a.workspace_id),
                ("created_at", session_a.created_at),
                ("expires_at", session_a.expires_at),
                ("_frozen", True)):
            object.__setattr__(built_enum, slot, value)
        check("CF-P1-001-R1-ENUM-04: a populated "
              "__new__-built object with the genuine session ID "
              "cannot enumerate contexts",
              _enum_refused(built_enum))
        check("CF-P1-001-R1-ENUM-05: a different session cannot "
              "enumerate another session's contexts",
              authorization.issued_contexts_for_session(session_b) == [])
        expired_enum = start_session(profile_a, profile_a.workspace_id,
                                     lifetime_seconds=1)
        time.sleep(2.0)
        check("CF-P1-001-R1-ENUM-06: an expired session cannot "
              "enumerate contexts",
              _enum_refused(expired_enum))
        doomed = start_session(profile_a, profile_a.workspace_id)
        authorization.request_voice_export_authorization(
            doomed, voice_a, scope="doomed export",
            approve_callback=_approve_yes)
        close_session(doomed)
        check("CF-P1-001-R1-ENUM-07: a closed session cannot "
              "enumerate contexts",
              _enum_refused(doomed))
        unissued = [copy.copy(session_a), copy.deepcopy(session_a),
                    built_enum, expired_enum, doomed]
        recovered = []
        for candidate in unissued:
            try:
                recovered.extend(
                    authorization.issued_contexts_for_session(candidate))
            except ValueError:
                continue
        check("CF-P1-001-R1-ENUM-08: a context recovered by any "
              "unissued session is never usable for private export "
              "or provider transmission",
              recovered == []
              and authorization.issued_contexts_for_session(
                  session_b) == [])

        check("CF-P1-001-EXP-17: shutdown prevents further authorization",
              close_session(session_a) is True
              and bool(authorization.authorize(
                  session_a, "use_in_project", voice_a["ownership"])))
        short_errors = asset_policy.validate_private_voice_export(
            voice_a, trusted_context=short_ctx)
        check("CF-P1-001-EXP-18: shutdown revokes the session's contexts",
              all(asset_policy.validate_private_voice_export(
                  voice_a, trusted_context=c)
                  == ["private voice export blocked: the authorization "
                      "has been revoked"]
                  for c in (ctx, tx_ctx, ctx2))
              and "revoked" in " ".join(short_errors)
              # R1: a closed session no longer enumerates at all —
              # enumeration now raises ValueError instead of
              # returning an empty list.
              and _enum_refused(session_a))
        check("CF-P1-001-EXP-19: closed session cannot request issuance",
              _no_context_closed(session_a, voice_a))
        check("CF-P1-001-EXP-20: forged session cannot request issuance",
              _no_context_forged(forged, voice_a))
        check("CF-P1-001-EXP-21: another profile's session cannot "
              "export this voice",
              _no_context(session_b, voice_a, _approve_yes))
        check("CF-P1-001-EXP-22: export is owner-only even for a "
              "shared-workspace voice",
              _no_context(session_b_same_ws, shared_voice, _approve_yes))

        # ----------------------------------------------------------
        # P0 behaviour unchanged (CF-P1-001-P0)
        # ----------------------------------------------------------
        owner_a = {"owner_id": "owner-a", "workspace_id": "workspace-a",
                   "visibility": "private", "sharing": "none"}
        check("CF-P1-001-P0-01: P0 authorize_action still allows the "
              "owner",
              asset_policy.authorize_action(
                  "use_in_project", owner_a, "owner-a",
                  "workspace-a") == [])
        check("CF-P1-001-P0-02: P0 authorize_action still rejects a "
              "wrong owner",
              bool(asset_policy.authorize_action(
                  "use_in_project", owner_a, "owner-b",
                  "workspace-a")))
        p0_ctx = asset_policy.issue_trusted_authorization_context(
            actor_owner_id="owner-a", actor_workspace_id="workspace-a",
            granted_by="owner-a", scope="export voice-nila-001",
            action="export_private_asset",
            character_id="char-nila-001",
            voice_profile_id="voice-nila-001")
        p0_voice = {"character_id": "char-nila-001",
                    "voice_profile_id": "voice-nila-001",
                    "ownership": dict(owner_a)}
        check("CF-P1-001-P0-03: P0 factory context still validates",
              asset_policy.validate_private_voice_export(
                  p0_voice, trusted_context=p0_ctx) == [])
        check("CF-P1-001-P0-04: P0 factory context for another voice "
              "still rejects",
              bool(asset_policy.validate_private_voice_export(
                  {"character_id": "char-aria-001",
                   "voice_profile_id": "voice-aria-001",
                   "ownership": dict(owner_a)},
                  trusted_context=p0_ctx)))
    finally:
        for root in tmp_roots:
            shutil.rmtree(root, ignore_errors=True)

    print()
    if failures:
        print(f"test_session_authorization: FAIL "
              f"({len(failures)} failure(s))")
        for name in failures:
            print(f"  FAIL {name}")
        return 1
    print("test_session_authorization: PASS (0 failure(s))")
    return 0


def _no_context(session, voice, approve_callback):
    """True when issuance raises ValueError (no context issued)."""
    try:
        authorization.request_voice_export_authorization(
            session, voice, scope="export", approve_callback=approve_callback)
    except ValueError:
        return True
    return False


def _enum_refused(session):
    """True when context enumeration refuses ``session`` with the
    fail-closed ValueError (not an active session issued by
    start_session())."""
    try:
        authorization.issued_contexts_for_session(session)
    except ValueError:
        return True
    return False


def _no_context_tx(session, voice, approve_callback):
    try:
        authorization.request_provider_transmission_authorization(
            session, voice, scope="transmit",
            approve_callback=approve_callback)
    except ValueError:
        return True
    return False


def _no_context_scope(session, voice):
    try:
        authorization.request_voice_export_authorization(
            session, voice, scope="   ", approve_callback=_approve_yes)
    except ValueError:
        return True
    return False


def _no_context_closed(session, voice):
    return _no_context(session, voice, _approve_yes)


def _no_context_forged(session, voice):
    return _no_context(session, voice, _approve_yes)


def _export_lifetime_ok(context):
    """The export expiry is finite and within 5 minutes of now."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    expires = datetime.strptime(context.expires_at, "%Y-%m-%dT%H:%M:%SZ")
    expires = expires.replace(tzinfo=timezone.utc)
    delta = (expires - now).total_seconds()
    return 0 < delta <= 300


def _bad_lifetime_rejected(session, voice):
    for bad in (0, -10, 3601, "300", True):
        try:
            authorization.request_voice_export_authorization(
                session, voice, scope="export",
                approve_callback=_approve_yes, lifetime_seconds=bad)
        except ValueError:
            continue
        return False
    return True


if __name__ == "__main__":
    sys.exit(main())
