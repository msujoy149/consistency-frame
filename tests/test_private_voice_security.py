#!/usr/bin/env python3
"""CF-WO-P0-008 Correction F — fail-closed private voice security
regression suite.

Tests the actual production functions in scripts/asset_policy.py
(resolver, export authorization, centralized authorize_action,
path safety) and scripts/timeline_policy.py (strict v2.5 timeline
validation). Every check executes production code; no check passes
through a test-only wrapper that mimics the rule.

Honest before/after experiment (CF-WO-P0-008 §7): the reproduction
script ~/workspace/consistency-frame-p0-delivery/p0-008-repro.py was
run BEFORE the fix and reproduced all three failures — (A) the
production resolver RESOLVED a private v2.5 voice with NO requester
identity; (B1) export of an owner-a voice with a dict claiming
granted_by 'owner-b' was ALLOWED; (B2) export with a plain caller
dict claiming granted_by 'owner-a' (no trusted context) was ALLOWED;
(C) a timeline referencing a private voice VALIDATED with no
requester identity in the call. Outputs:
p0-008-repro-before.txt ("RESULT: ALL THREE FAILURES REPRODUCED").
After the fix the same inputs are REJECTED (p0-008-repro-after.txt:
"RESULT: ALL THREE FAILURES FIXED"). This suite pins the AFTER
behaviour on every one of those inputs. No other historical numbers
are claimed here.

Test identities (deterministic, shared with
tests/test_character_registration.py): owner-a / workspace-a own
Mina + Nila (char-nila-001, voice-nila-001) and Aria
(char-aria-001, voice-aria-001); owner-b / workspace-b is the other
user / workspace.

Run: python3 tests/test_private_voice_security.py
Exit 0 = PASS, 1 = FAIL. Test IDs: CF-P0-008-SEC.
"""
import copy
import dataclasses
import importlib.util
import json
import os
import pickle
import sys
import tempfile
from types import SimpleNamespace

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import asset_policy  # noqa: E402
import timeline_policy  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "test_timeline_manifest",
    os.path.join(ROOT, "tests", "test_timeline_manifest.py"))
test_timeline_manifest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(test_timeline_manifest)
validate_timeline_cross_references = (
    timeline_policy.validate_timeline_cross_references)

_spec = importlib.util.spec_from_file_location(
    "test_character_registration",
    os.path.join(ROOT, "tests", "test_character_registration.py"))
test_character_registration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(test_character_registration)

failures = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def load_fixture(name):
    with open(os.path.join(ROOT, "tests", "fixtures", name),
              encoding="utf-8") as f:
        return json.load(f)


OWNER_A = {"owner_id": "owner-a", "workspace_id": "workspace-a",
           "visibility": "private", "sharing": "none"}
OWNER_B = {"owner_id": "owner-b", "workspace_id": "workspace-b",
           "visibility": "private", "sharing": "none"}
OWNER_A_WS_B = {"owner_id": "owner-a", "workspace_id": "workspace-b",
                "visibility": "private", "sharing": "none"}
SHARED_WS = {"owner_id": "owner-a", "workspace_id": "workspace-a",
             "visibility": "shared", "sharing": "workspace"}


def owned_registry():
    """mini_registry() with owner-a ownership injected on every
    character, voice profile and audio asset, so a strict v2.5
    timeline under requester owner-a / workspace-a passes."""
    reg = test_timeline_manifest.mini_registry()
    for rec in reg["characters"].values():
        rec["ownership"] = copy.deepcopy(OWNER_A)
    for rec in reg["voice_profiles"].values():
        rec["ownership"] = copy.deepcopy(OWNER_A)
    audio_chars = {"aud-ana-01": "char-ana-001",
                   "aud-ben-01": "char-ben-002",
                   "aud-kiki-01": "char-kiki-003"}
    for aid, rec in reg["audio_assets"].items():
        rec["ownership"] = copy.deepcopy(OWNER_A)
        if aid in audio_chars:
            rec["character_id"] = audio_chars[aid]
    return reg


def dialogue_timeline():
    """One human speaker, synchronized dialogue + video (the §4
    scenario 1 shape)."""
    m = test_timeline_manifest.manifest
    track = test_timeline_manifest.track
    video_clip = test_timeline_manifest.video_clip
    dialogue_audio = test_timeline_manifest.dialogue_audio
    sync_group = test_timeline_manifest.sync_group
    return m([
        track("v1", "video", [video_clip(
            "clip-v-01", "shot-a-01", "sc-01", ["char-ana-001"],
            timeline_start_seconds=0, timeline_end_seconds=4,
            duration_seconds=4)]),
        track("a1", "audio", [dialogue_audio(
            "clip-a-01", "l-ana-01", "char-ana-001", "vp-ana-001",
            "aud-ana-01", ["shot-a-01"])]),
    ], synchronization_groups=[sync_group(
        "sync-01", ["clip-v-01"], ["clip-a-01"], ["l-ana-01"],
        ["shot-a-01"])])


def two_speaker_timeline():
    """Two characters with separate voice profiles (§4 scenario 8)."""
    m = test_timeline_manifest.manifest
    track = test_timeline_manifest.track
    video_clip = test_timeline_manifest.video_clip
    dialogue_audio = test_timeline_manifest.dialogue_audio
    return m([
        track("v1", "video", [video_clip(
            "clip-v-02", "shot-a-02", "sc-01",
            ["char-ana-001", "char-ben-002"],
            timeline_start_seconds=0, timeline_end_seconds=8,
            duration_seconds=8)]),
        track("a1", "audio", [
            dialogue_audio("clip-a-02a", "l-ana-01", "char-ana-001",
                           "vp-ana-001", "aud-ana-01", ["shot-a-02"]),
            dialogue_audio("clip-a-02b", "l-ben-01", "char-ben-002",
                           "vp-ben-001", "aud-ben-01", ["shot-a-02"],
                           timeline_start_seconds=4,
                           timeline_end_seconds=8),
        ]),
    ])


def export_ctx(actor_owner="owner-a", actor_workspace="workspace-a",
               granted_by="owner-a", scope="export voice-nila-001 "
               "for backup", action="export_private_asset",
               character_id="char-nila-001",
               voice_profile_id="voice-nila-001",
               provider_transmission_approved=False,
               expires_at=None):
    return asset_policy.issue_trusted_authorization_context(
        actor_owner_id=actor_owner, actor_workspace_id=actor_workspace,
        granted_by=granted_by, scope=scope, action=action,
        character_id=character_id, voice_profile_id=voice_profile_id,
        provider_transmission_approved=provider_transmission_approved,
        expires_at=expires_at)


def main():
    nila = load_fixture("character-registration-valid-human.json")
    nila_voice = load_fixture("voice-profile-valid-user-recorded.json")
    aria_voice = load_fixture("voice-profile-valid-ai-generated.json")
    aria_character = {"character_id": "char-aria-001",
                      "ownership": copy.deepcopy(OWNER_A)}
    v25_voice_registry = {
        nila_voice["voice_profile_id"]: nila_voice,
        aria_voice["voice_profile_id"]: aria_voice}
    v25_registries = {nila["character_id"]: nila,
                      aria_character["character_id"]: aria_character}

    # ------------------------------------------------------------------
    # (a) Resolver reproduced failure (CF-WO-P0-008 §2 / §7)
    # ------------------------------------------------------------------
    voice, errs = asset_policy.resolve_voice_for_production(
        v25_voice_registry, v25_registries, "char-nila-001",
        "voice-nila-001")
    check("CF-P0-008-SEC(a1): resolver with NO requester rejects a "
          "private v2.5 voice",
          voice is None and bool(errs), "; ".join(errs))
    voice, errs = asset_policy.resolve_voice_for_production(
        v25_voice_registry, v25_registries, "char-nila-001",
        "voice-nila-001", None, "workspace-a")
    check("CF-P0-008-SEC(a2): resolver with owner only (no workspace) "
          "rejects",
          voice is None and bool(errs), "; ".join(errs))
    voice, errs = asset_policy.resolve_voice_for_production(
        v25_voice_registry, v25_registries, "char-nila-001",
        "voice-nila-001", "owner-a", None)
    check("CF-P0-008-SEC(a3): resolver with workspace only (no owner) "
          "rejects",
          voice is None and bool(errs), "; ".join(errs))
    voice, errs = asset_policy.resolve_voice_for_production(
        v25_voice_registry, v25_registries, "char-nila-001",
        "voice-nila-001", "owner-b", "workspace-b")
    check("CF-P0-008-SEC(a4): resolver rejects the wrong owner",
          voice is None and bool(errs), "; ".join(errs))
    voice, errs = asset_policy.resolve_voice_for_production(
        v25_voice_registry, v25_registries, "char-nila-001",
        "voice-nila-001", "owner-a", "workspace-b")
    check("CF-P0-008-SEC(a5): resolver rejects the wrong workspace",
          voice is None and bool(errs), "; ".join(errs))
    voice, errs = asset_policy.resolve_voice_for_production(
        v25_voice_registry, v25_registries, "char-aria-001",
        "voice-aria-001", "owner-a", "workspace-b")
    check("CF-P0-008-SEC(a6): correct owner in the wrong workspace "
          "rejects (second record)",
          voice is None and bool(errs), "; ".join(errs))
    voice, errs = asset_policy.resolve_voice_for_production(
        v25_voice_registry, v25_registries, "char-aria-001",
        "voice-aria-001", "owner-b", "workspace-a")
    check("CF-P0-008-SEC(a7): correct workspace with the wrong owner "
          "rejects (private sharing none)",
          voice is None and bool(errs), "; ".join(errs))
    voice, errs = asset_policy.resolve_voice_for_production(
        v25_voice_registry, v25_registries, "char-nila-001",
        "voice-aria-001", "owner-a", "workspace-a")
    check("CF-P0-008-SEC(a8): voice of another character rejects",
          voice is None and bool(errs), "; ".join(errs))
    other_owner_voice = copy.deepcopy(nila_voice)
    other_owner_voice["ownership"] = copy.deepcopy(OWNER_B)
    voice, errs = asset_policy.resolve_voice_for_production(
        {other_owner_voice["voice_profile_id"]: other_owner_voice},
        v25_registries, "char-nila-001", "voice-nila-001",
        "owner-a", "workspace-a")
    check("CF-P0-008-SEC(a9): voice owned by another owner rejects",
          voice is None and bool(errs), "; ".join(errs))
    other_ws_voice = copy.deepcopy(nila_voice)
    other_ws_voice["ownership"] = copy.deepcopy(OWNER_A_WS_B)
    voice, errs = asset_policy.resolve_voice_for_production(
        {other_ws_voice["voice_profile_id"]: other_ws_voice},
        v25_registries, "char-nila-001", "voice-nila-001",
        "owner-a", "workspace-a")
    check("CF-P0-008-SEC(a10): voice owned by another workspace "
          "rejects",
          voice is None and bool(errs), "; ".join(errs))
    pending_voice = copy.deepcopy(nila_voice)
    pending_voice["approval_status"] = "pending"
    pending_voice["status"] = "pending"
    voice, errs = asset_policy.resolve_voice_for_production(
        {pending_voice["voice_profile_id"]: pending_voice},
        v25_registries, "char-nila-001", "voice-nila-001",
        "owner-a", "workspace-a", require_approved=True)
    check("CF-P0-008-SEC(a11): pending voice rejects when approval "
          "is required",
          voice is None and bool(errs), "; ".join(errs))
    voice, errs = asset_policy.resolve_voice_for_production(
        v25_voice_registry, v25_registries, "char-nila-001",
        "voice-nila-001", "owner-a", "workspace-a")
    check("CF-P0-008-SEC(a12): correct owner + workspace, approved "
          "voice resolves",
          voice is not None and not errs
          and voice["voice_profile_id"] == "voice-nila-001",
          "; ".join(errs))
    shared_voice = copy.deepcopy(nila_voice)
    shared_voice["ownership"] = copy.deepcopy(SHARED_WS)
    voice, errs = asset_policy.resolve_voice_for_production(
        {shared_voice["voice_profile_id"]: shared_voice},
        v25_registries, "char-nila-001", "voice-nila-001",
        "owner-b", "workspace-a")
    check("CF-P0-008-SEC(a13): shared + workspace admits another "
          "owner in the same workspace",
          voice is not None and not errs, "; ".join(errs))
    voice, errs = asset_policy.resolve_voice_for_production(
        {shared_voice["voice_profile_id"]: shared_voice},
        v25_registries, "char-nila-001", "voice-nila-001",
        "owner-b", "workspace-b")
    check("CF-P0-008-SEC(a14): shared + workspace rejects another "
          "workspace",
          voice is None and bool(errs), "; ".join(errs))
    # Legacy v2.3 contract (pinned, not invented): the v2.3 fixture
    # carries no voice_profile_id / ownership / approval_status, so
    # it resolves without a requester ONLY with require_approved
    # False and no character registry given.
    legacy_voice = load_fixture("voice-profile-valid.json")
    legacy_registry = {legacy_voice["id"]: legacy_voice}
    voice, errs = asset_policy.resolve_voice_for_production(
        legacy_registry, None, "char-nila-001", "voice-nila-001",
        require_approved=False)
    check("CF-P0-008-SEC(a15): legacy v2.3 record keeps its "
          "historical contract (resolves without requester when "
          "require_approved=False, no character registry)",
          voice is not None and not errs, "; ".join(errs))
    voice, errs = asset_policy.resolve_voice_for_production(
        legacy_registry, None, "char-nila-001", "voice-nila-001")
    check("CF-P0-008-SEC(a16): legacy v2.3 record still rejects "
          "under the default require_approved=True (no approval "
          "record)",
          voice is None and bool(errs), "; ".join(errs))
    voice, errs = asset_policy.resolve_voice_for_production(
        legacy_registry, v25_registries, "char-nila-001",
        "voice-nila-001", "owner-a", "workspace-a",
        require_approved=False)
    check("CF-P0-008-SEC(a17): legacy v2.3 record with a character "
          "registry rejects (no ownership to match the character)",
          voice is None and bool(errs), "; ".join(errs))

    # ------------------------------------------------------------------
    # (b) Export reproduced failure (CF-WO-P0-008 §3 / §7)
    # ------------------------------------------------------------------
    check("CF-P0-008-SEC(b1): export without any authorization "
          "context rejects",
          bool(asset_policy.validate_private_voice_export(nila_voice)))
    check("CF-P0-008-SEC(b2): export with a dict-only authorization "
          "(granted_by owner-a, full explicit) rejects — a dict is "
          "never authority",
          bool(asset_policy.validate_private_voice_export(
              nila_voice, {"granted_by": "owner-a",
                           "scope": "export voice-nila-001 for backup",
                           "explicit_authorisation": True})))
    check("CF-P0-008-SEC(b3): export with a forged granted_by "
          "(owner-b) rejects",
          bool(asset_policy.validate_private_voice_export(
              nila_voice, {"granted_by": "owner-b",
                           "scope": "export voice-nila-001 for backup",
                           "explicit_authorisation": True})))
    check("CF-P0-008-SEC(b4): trusted context whose actor is owner-b "
          "with granted_by owner-a rejects",
          bool(asset_policy.validate_private_voice_export(
              nila_voice, trusted_context=export_ctx(
                  actor_owner="owner-b", actor_workspace="workspace-b",
                  granted_by="owner-a"))))
    check("CF-P0-008-SEC(b5): trusted context with actor owner-a but "
          "granted_by owner-b rejects",
          bool(asset_policy.validate_private_voice_export(
              nila_voice, trusted_context=export_ctx(
                  actor_owner="owner-a", granted_by="owner-b"))))
    check("CF-P0-008-SEC(b6): owner-a in the wrong workspace rejects",
          bool(asset_policy.validate_private_voice_export(
              nila_voice, trusted_context=export_ctx(
                  actor_owner="owner-a",
                  actor_workspace="workspace-b"))))
    try:
        export_ctx(scope="")
        scope_raised = False
    except ValueError:
        scope_raised = True
    check("CF-P0-008-SEC(b7): the factory raises ValueError on an "
          "empty scope (fail closed at issuance)",
          scope_raised)
    try:
        export_ctx(scope="   ")
        ws_scope_raised = False
    except ValueError:
        ws_scope_raised = True
    check("CF-P0-008-SEC(b8): the factory raises ValueError on a "
          "whitespace-only scope",
          ws_scope_raised)
    check("CF-P0-008-SEC(b9): a context for the wrong action "
          "(use_in_production) rejects export",
          bool(asset_policy.validate_private_voice_export(
              nila_voice, trusted_context=export_ctx(
                  action="use_in_production"))))
    check("CF-P0-008-SEC(b10): a context for another character "
          "rejects",
          bool(asset_policy.validate_private_voice_export(
              nila_voice, trusted_context=export_ctx(
                  character_id="char-aria-001"))))
    check("CF-P0-008-SEC(b11): a context for another voice rejects",
          bool(asset_policy.validate_private_voice_export(
              nila_voice, trusted_context=export_ctx(
                  voice_profile_id="voice-aria-001"))))
    check("CF-P0-008-SEC(b12): an expired context rejects",
          bool(asset_policy.validate_private_voice_export(
              nila_voice, trusted_context=export_ctx(
                  expires_at="2000-01-01T00:00:00Z"))))
    # CF-WO-P0-009 (A): revocation is registry state, NOT a mutated
    # field — the context is immutable, so `revoked_ctx.revoked =
    # True` (the P0-008 test) must no longer be the revocation
    # path. Revoking goes through
    # asset_policy.revoke_trusted_authorization_context, the
    # issued context itself is unchanged, and export rejects.
    revoked_ctx = export_ctx()
    revoked_before = (revoked_ctx.authorization_id,
                      revoked_ctx.actor_owner_id,
                      revoked_ctx.scope, revoked_ctx.revoked)
    asset_policy.revoke_trusted_authorization_context(revoked_ctx)
    check("CF-P0-008-SEC(b13): a revoked context rejects",
          bool(asset_policy.validate_private_voice_export(
              nila_voice, trusted_context=revoked_ctx)))
    check("CF-P0-008-SEC(b13b): revoking does not mutate the issued "
          "context (revoked field still False, all fields unchanged)",
          (revoked_ctx.authorization_id, revoked_ctx.actor_owner_id,
           revoked_ctx.scope, revoked_ctx.revoked) == revoked_before
          and revoked_ctx.revoked is False)
    check("CF-P0-008-SEC(b14): to_provider=True without "
          "provider-transmission approval rejects",
          bool(asset_policy.validate_private_voice_export(
              nila_voice, trusted_context=export_ctx(),
              to_provider=True)))
    check("CF-P0-008-SEC(b15): to_provider=True with "
          "provider-transmission approval allows",
          not asset_policy.validate_private_voice_export(
              nila_voice, trusted_context=export_ctx(
                  provider_transmission_approved=True),
              to_provider=True))
    check("CF-P0-008-SEC(b16): correct owner export within scope "
          "allows",
          not asset_policy.validate_private_voice_export(
              nila_voice, trusted_context=export_ctx()))
    shared_voice_export = copy.deepcopy(nila_voice)
    shared_voice_export["ownership"] = copy.deepcopy(SHARED_WS)
    check("CF-P0-008-SEC(b17): shared + workspace does NOT authorize "
          "export by owner-b (export is owner-only)",
          bool(asset_policy.validate_private_voice_export(
              shared_voice_export, trusted_context=export_ctx(
                  actor_owner="owner-b",
                  actor_workspace="workspace-a",
                  granted_by="owner-a"))))
    try:
        asset_policy.TrustedAuthorizationContext(
            actor_owner_id="owner-a", actor_workspace_id="workspace-a",
            granted_by="owner-a", scope="export voice-nila-001",
            action="export_private_asset",
            character_id="char-nila-001",
            voice_profile_id="voice-nila-001")
        direct_raised = False
    except TypeError:
        direct_raised = True
    check("CF-P0-008-SEC(b18): direct TrustedAuthorizationContext "
          "construction raises TypeError (factory-only boundary)",
          direct_raised)
    check("CF-P0-008-SEC(b19): a dict fake context is rejected (not "
          "a trusted context instance)",
          bool(asset_policy.validate_private_voice_export(
              nila_voice, trusted_context={
                  "actor_owner_id": "owner-a",
                  "actor_workspace_id": "workspace-a",
                  "granted_by": "owner-a",
                  "scope": "export voice-nila-001 for backup",
                  "action": "export_private_asset",
                  "character_id": "char-nila-001",
                  "voice_profile_id": "voice-nila-001"})))
    check("CF-P0-008-SEC(b20): a SimpleNamespace fake context is "
          "rejected (not a trusted context instance)",
          bool(asset_policy.validate_private_voice_export(
              nila_voice, trusted_context=SimpleNamespace(
                  actor_owner_id="owner-a",
                  actor_workspace_id="workspace-a",
                  granted_by="owner-a",
                  scope="export voice-nila-001 for backup",
                  action="export_private_asset",
                  character_id="char-nila-001",
                  voice_profile_id="voice-nila-001",
                  provider_transmission_approved=False,
                  expires_at=None, revoked=False))))

    # ------------------------------------------------------------------
    # (c) Timeline reproduced failure + WO §4 scenarios 1–17 (strict)
    # ------------------------------------------------------------------
    strict = validate_timeline_cross_references
    reg = owned_registry()
    errs = strict(dialogue_timeline(), reg, "owner-a", "workspace-a",
                  strict=True)
    check("CF-P0-008-SEC(c1): §4 scenario 1 — owner-a timeline, "
          "owner-a character + voice passes (strict)",
          not errs, "; ".join(errs))
    errs = strict(dialogue_timeline(), reg, "owner-b", "workspace-b",
                  strict=True)
    check("CF-P0-008-SEC(c2): §4 scenario 2 — owner-b requester "
          "rejects (strict)",
          bool(errs), "; ".join(errs))
    reg_ws_b_voice = owned_registry()
    reg_ws_b_voice["voice_profiles"]["vp-ana-001"]["ownership"] = \
        copy.deepcopy(OWNER_A_WS_B)
    errs = strict(dialogue_timeline(), reg_ws_b_voice, "owner-a",
                  "workspace-a", strict=True)
    check("CF-P0-008-SEC(c3): §4 scenario 3 — owner-a requester, "
          "voice from workspace-b rejects (strict)",
          bool(errs), "; ".join(errs))
    reg_b_voice = owned_registry()
    reg_b_voice["voice_profiles"]["vp-ana-001"]["ownership"] = \
        copy.deepcopy(OWNER_B)
    errs = strict(dialogue_timeline(), reg_b_voice, "owner-a",
                  "workspace-a", strict=True)
    check("CF-P0-008-SEC(c4): §4 scenario 4 — character owner-a, "
          "voice owner-b rejects (strict)",
          bool(errs), "; ".join(errs))
    reg_no_voice_owner = owned_registry()
    del reg_no_voice_owner["voice_profiles"]["vp-ana-001"]["ownership"]
    errs = strict(dialogue_timeline(), reg_no_voice_owner, "owner-a",
                  "workspace-a", strict=True)
    check("CF-P0-008-SEC(c5): §4 scenario 5 — voice with no "
          "ownership rejects (strict)",
          bool(errs), "; ".join(errs))
    errs = strict(dialogue_timeline(), reg, None, "workspace-a",
                  strict=True)
    check("CF-P0-008-SEC(c6): §4 scenario 6 — missing requester "
          "owner rejects (strict)",
          bool(errs), "; ".join(errs))
    errs = strict(dialogue_timeline(), reg, "owner-a", None,
                  strict=True)
    check("CF-P0-008-SEC(c7): §4 scenario 7 — missing requester "
          "workspace rejects (strict)",
          bool(errs), "; ".join(errs))
    errs = strict(two_speaker_timeline(), reg, "owner-a",
                  "workspace-a", strict=True)
    check("CF-P0-008-SEC(c8): §4 scenario 8 — correct owner + "
          "workspace with the correct voices passes (strict)",
          not errs, "; ".join(errs))
    narration = test_timeline_manifest.manifest([
        test_timeline_manifest.track("v1", "video", [
            test_timeline_manifest.video_clip(
                "clip-v-04", "shot-n-01", "sc-03", [],
                timeline_start_seconds=0, timeline_end_seconds=4,
                duration_seconds=4)]),
        test_timeline_manifest.track("a1", "audio", [
            test_timeline_manifest.audio_clip(
                "clip-a-04", "narration", language="en",
                role="narrator", timeline_start_seconds=0,
                timeline_end_seconds=4, duration_seconds=4)]),
    ])
    errs = strict(narration, reg, "owner-a", "workspace-a",
                  strict=True)
    check("CF-P0-008-SEC(c9a): §4 scenario 9 — narration without a "
          "visible character passes (strict, with requester)",
          not errs, "; ".join(errs))
    errs = strict(narration, reg, strict=True)
    check("CF-P0-008-SEC(c9b): §4 scenario 9 — narration without a "
          "visible character passes (strict, no requester at all)",
          not errs, "; ".join(errs))
    music = test_timeline_manifest.manifest([
        test_timeline_manifest.track("a1", "audio", [
            test_timeline_manifest.audio_clip(
                "clip-a-m", "music", audio_asset_id="aud-music-01",
                timeline_start_seconds=0, timeline_end_seconds=4,
                duration_seconds=4)]),
    ])
    errs = strict(music, reg, strict=True)
    check("CF-P0-008-SEC(c10): §4 scenario 10 — music without a "
          "Character ID passes (strict, no requester)",
          not errs, "; ".join(errs))
    ambience_sfx = test_timeline_manifest.manifest([
        test_timeline_manifest.track("a1", "audio", [
            test_timeline_manifest.audio_clip(
                "clip-a-b", "ambience", audio_asset_id="aud-amb-01",
                timeline_start_seconds=0, timeline_end_seconds=4,
                duration_seconds=4),
            test_timeline_manifest.audio_clip(
                "clip-a-s", "sound-effect",
                timeline_start_seconds=0, timeline_end_seconds=4,
                duration_seconds=4)]),
    ])
    errs = strict(ambience_sfx, reg, strict=True)
    check("CF-P0-008-SEC(c11): §4 scenario 11 — ambience + SFX "
          "without a Character ID passes (strict, no requester)",
          not errs, "; ".join(errs))
    wrong_speaker = test_timeline_manifest.manifest([
        test_timeline_manifest.track("a1", "audio", [
            test_timeline_manifest.dialogue_audio(
                "clip-a-12", "l-ana-01", "char-ben-002", "vp-ana-001",
                "aud-ana-01", ["shot-a-01"])]),
    ])
    errs = strict(wrong_speaker, reg, "owner-a", "workspace-a",
                  strict=True)
    check("CF-P0-008-SEC(c12): §4 scenario 12 — dialogue line with "
          "the wrong speaker rejects (strict)",
          bool(errs), "; ".join(errs))
    wrong_voice = test_timeline_manifest.manifest([
        test_timeline_manifest.track("a1", "audio", [
            test_timeline_manifest.dialogue_audio(
                "clip-a-13", "l-ana-01", "char-ana-001", "vp-ben-001",
                "aud-ana-01", ["shot-a-01"])]),
    ])
    errs = strict(wrong_voice, reg, "owner-a", "workspace-a",
                  strict=True)
    check("CF-P0-008-SEC(c13): §4 scenario 13 — audio clip with the "
          "wrong Voice Profile rejects (strict)",
          bool(errs), "; ".join(errs))
    unrelated_char = test_timeline_manifest.manifest([
        test_timeline_manifest.track("v1", "video", [
            test_timeline_manifest.video_clip(
                "clip-v-14", "shot-a-01", "sc-01",
                ["char-ana-001", "char-ben-002"])]),
    ])
    errs = strict(unrelated_char, reg, "owner-a", "workspace-a",
                  strict=True)
    check("CF-P0-008-SEC(c14): §4 scenario 14 — video clip with an "
          "unrelated Character ID rejects (strict)",
          bool(errs), "; ".join(errs))
    bad_sync = test_timeline_manifest.manifest([
        test_timeline_manifest.track("v1", "video", [
            test_timeline_manifest.video_clip(
                "clip-v-15", "shot-a-01", "sc-01",
                ["char-ana-001"])]),
        test_timeline_manifest.track("a1", "audio", [
            test_timeline_manifest.dialogue_audio(
                "clip-a-15", "l-ana-01", "char-ana-001", "vp-ana-001",
                "aud-ana-01", ["shot-a-01"])]),
    ], synchronization_groups=[test_timeline_manifest.sync_group(
        "sync-15", ["clip-nope"], ["clip-a-15"], ["l-ana-01"],
        ["shot-a-01"])])
    errs = strict(bad_sync, reg, "owner-a", "workspace-a", strict=True)
    check("CF-P0-008-SEC(c15): §4 scenario 15 — sync group with a "
          "nonexistent clip rejects (strict)",
          bool(errs), "; ".join(errs))
    legacy = load_fixture("timeline-valid-v23.json")
    errs = validate_timeline_cross_references(legacy, {})
    check("CF-P0-008-SEC(c16a): §4 scenario 16 — valid legacy v2.3 "
          "timeline passes under the legacy structural contract "
          "(empty registry)",
          not errs, "; ".join(errs))
    check("CF-P0-008-SEC(c16b): §4 scenario 16 — the legacy fixture "
          "really is v2.3",
          legacy["schema_version"] == "2.3")
    reg_combined = owned_registry()
    del reg_combined["voice_profiles"]["vp-ana-001"]["ownership"]
    errs = strict(dialogue_timeline(), reg_combined, "owner-b",
                  "workspace-b", strict=True)
    check("CF-P0-008-SEC(c17): §4 scenario 17 — strict enforces "
          "requester + ownership together (wrong requester AND a "
          "voice without ownership reject)",
          bool(errs), "; ".join(errs))
    errs = strict(test_timeline_manifest.manifest(
        [test_timeline_manifest.track("a1", "audio", [
            test_timeline_manifest.dialogue_audio(
                "clip-a-v", "l-ana-01", "char-ana-001", "vp-ana-001",
                "aud-ana-01", ["shot-a-01"])])], version="2.3"),
        reg, "owner-a", "workspace-a", strict=True)
    check("CF-P0-008-SEC(c18): strict validation on a v2.3 manifest "
          "returns a version error",
          bool(errs) and "2.3" in "; ".join(errs),
          "; ".join(errs))
    reg_missing_chars = owned_registry()
    del reg_missing_chars["characters"]
    errs = strict(dialogue_timeline(), reg_missing_chars, "owner-a",
                  "workspace-a", strict=True)
    check("CF-P0-008-SEC(c19): strict rejects when a referenced "
          "kind's registry section is absent (missing registry "
          "data fails closed)",
          bool(errs), "; ".join(errs))
    reg_no_audio_owner = owned_registry()
    del reg_no_audio_owner["audio_assets"]["aud-ana-01"]["ownership"]
    errs = strict(dialogue_timeline(), reg_no_audio_owner, "owner-a",
                  "workspace-a", strict=True)
    check("CF-P0-008-SEC(c20): strict rejects a dialogue-bound "
          "audio asset without ownership",
          bool(errs), "; ".join(errs))
    errs = strict(music, reg, strict=True)
    check("CF-P0-008-SEC(c21): strict music-only timeline with a "
          "full registry and no requester passes",
          not errs, "; ".join(errs))

    # ------------------------------------------------------------------
    # (d) Bypass regression (CF-WO-P0-008 §5 / Correction D)
    # ------------------------------------------------------------------
    check("CF-P0-008-SEC(d1): timeline validation in the test file "
          "IS the production function (same object — no second "
          "implementation)",
          timeline_policy.validate_timeline_cross_references
          is test_timeline_manifest.validate_timeline_cross_references)
    mina_voice = load_fixture("voice-profile-user-recording.json")
    mina_registry = {mina_voice["voice_profile_id"]: mina_voice}
    # CF-WO-P0-009 (B): Mina's voice is v2.5, so the wrapper must
    # be given the Character Registry — a v2.5 voice is never
    # resolvable without it.
    mina_character = load_fixture("character-registration-valid.json")
    mina_character_registry = {mina_character["character_id"]:
                               mina_character}
    original_resolver = asset_policy.resolve_voice_for_production
    calls = {"n": 0}

    def counting_resolver(*args, **kwargs):
        calls["n"] += 1
        return original_resolver(*args, **kwargs)

    asset_policy.resolve_voice_for_production = counting_resolver
    try:
        resolved, spy_errs = \
            test_character_registration.resolve_voice_for_character(
                mina_registry, "char-001",
                character_registry=mina_character_registry,
                requesting_owner_id="owner-a",
                requesting_workspace_id="workspace-a")
    finally:
        asset_policy.resolve_voice_for_production = original_resolver
    check("CF-P0-008-SEC(d2): the character-registration resolver "
          "calls the production resolver (spy: production resolver "
          "invoked, voice resolved)",
          calls["n"] >= 1 and resolved is not None and not spy_errs,
          f"calls={calls['n']} errs={'; '.join(spy_errs)}")
    check("CF-P0-008-SEC(d3): check_voice_binding in the test file "
          "IS asset_policy.check_voice_binding",
          asset_policy.check_voice_binding
          is test_character_registration.check_voice_binding)
    check("CF-P0-008-SEC(d4): resolve_for_user in the test file IS "
          "asset_policy.resolve_for_user",
          asset_policy.resolve_for_user
          is test_character_registration.resolve_for_user)
    # CF-WO-P0-009 (cross-cutting): the wrapper has no fallback of
    # its own — if the production resolver is unavailable, the
    # wrapper must surface the failure, never resolve on its own.
    def _unavailable_resolver(*args, **kwargs):
        raise RuntimeError("production resolver unavailable")

    asset_policy.resolve_voice_for_production = _unavailable_resolver
    try:
        try:
            test_character_registration.resolve_voice_for_character(
                mina_registry, "char-001",
                character_registry=mina_character_registry,
                requesting_owner_id="owner-a",
                requesting_workspace_id="workspace-a")
            unavailable_propagated = False
        except RuntimeError:
            unavailable_propagated = True
    finally:
        asset_policy.resolve_voice_for_production = original_resolver
    check("CF-P0-008-SEC(d5): the character-registration wrapper "
          "has no fallback — an unavailable production resolver "
          "propagates instead of resolving on its own",
          unavailable_propagated)

    # ------------------------------------------------------------------
    # (e) Path escape (regression pin)
    # ------------------------------------------------------------------
    _, errs = asset_policy.resolve_private_path(
        "characters", "../outside/secret.jpg")
    check("CF-P0-008-SEC(e1): private path traversal "
          "'../outside/secret.jpg' rejects",
          bool(errs), "; ".join(errs))
    _, errs = asset_policy.resolve_private_path(
        "characters", "/etc/passwd")
    check("CF-P0-008-SEC(e2): absolute private path '/etc/passwd' "
          "rejects",
          bool(errs), "; ".join(errs))
    with tempfile.TemporaryDirectory() as tmp:
        base = os.path.join(tmp, "characters")
        outside = os.path.join(tmp, "outside")
        os.makedirs(os.path.join(base, "char-nila-001"))
        os.makedirs(outside)
        with open(os.path.join(outside, "secret.jpg"), "w") as f:
            f.write("not yours")
        os.symlink(outside, os.path.join(base, "escape"))
        _, errs = asset_policy.resolve_private_path(
            base, "escape/secret.jpg")
        check("CF-P0-008-SEC(e3): symlink escape out of the private "
              "base rejects",
              bool(errs), "; ".join(errs))
        resolved, errs = asset_policy.resolve_private_path(
            base, "char-nila-001/voice-reference.mp3")
        check("CF-P0-008-SEC(e4): a safe path inside the base "
              "resolves",
              not errs and resolved is not None
              and resolved.startswith(os.path.realpath(base)),
              "; ".join(errs))

    # ------------------------------------------------------------------
    # (f) Invalid sharing mode
    # ------------------------------------------------------------------
    check("CF-P0-008-SEC(f1): authorize_action rejects ownership "
          "with sharing 'everyone'",
          bool(asset_policy.authorize_action(
              "use_in_production",
              {"owner_id": "owner-a", "workspace_id": "workspace-a",
               "visibility": "private", "sharing": "everyone"},
              "owner-a", "workspace-a")))
    check("CF-P0-008-SEC(f2): validate_ownership rejects visibility "
          "'shared' + sharing 'none'",
          bool(asset_policy.validate_ownership(
              {"owner_id": "owner-a", "workspace_id": "workspace-a",
               "visibility": "shared", "sharing": "none"})))

    # ------------------------------------------------------------------
    # (g) Centralization (CF-WO-P0-008 §6 / Correction E)
    # ------------------------------------------------------------------
    check("CF-P0-008-SEC(g1): authorize_action rejects an unknown "
          "action",
          bool(asset_policy.authorize_action(
              "delete_everything", copy.deepcopy(OWNER_A), "owner-a",
              "workspace-a")))
    check("CF-P0-008-SEC(g2): authorize_action rejects a missing "
          "requester",
          bool(asset_policy.authorize_action(
              "use_in_production", copy.deepcopy(OWNER_A), None,
              None)))
    voice, errs = asset_policy.resolve_voice_for_production(
        v25_voice_registry, v25_registries, "char-nila-001",
        "voice-nila-001", "owner-a", "workspace-a")
    check("CF-P0-008-SEC(g3): production use is allowed for the "
          "correct owner (setup for the separation pin)",
          voice is not None and not errs, "; ".join(errs))
    check("CF-P0-008-SEC(g4): a voice allowed for use_in_production "
          "is NOT automatically exportable (export without a "
          "trusted context still rejects)",
          bool(asset_policy.validate_private_voice_export(voice)))

    # ------------------------------------------------------------------
    # (h) CF-WO-P0-009 (A) — the trusted context is genuinely
    # immutable after issuance; revocation is separate registry
    # state, never a mutated field.
    # ------------------------------------------------------------------
    fresh = export_ctx()
    check("CF-P0-009-SEC(h1): a newly issued context carries the "
          "expected identity / scope / action / approval",
          fresh.actor_owner_id == "owner-a"
          and fresh.actor_workspace_id == "workspace-a"
          and fresh.granted_by == "owner-a"
          and fresh.scope == "export voice-nila-001 for backup"
          and fresh.action == "export_private_asset"
          and fresh.character_id == "char-nila-001"
          and fresh.voice_profile_id == "voice-nila-001"
          and fresh.provider_transmission_approved is False
          and fresh.expires_at is None
          and fresh.revoked is False
          and isinstance(fresh.authorization_id, str)
          and bool(fresh.authorization_id))
    forged_values = {
        "authorization_id": "forged-authorization-id",
        "actor_owner_id": "owner-b",
        "actor_workspace_id": "workspace-b",
        "granted_by": "owner-b",
        "scope": "forged scope",
        "action": "use_in_production",
        "character_id": "char-aria-001",
        "voice_profile_id": "voice-aria-001",
        "provider_transmission_approved": True,
        "expires_at": "2000-01-01T00:00:00Z",
        "revoked": True}
    for field, forged in forged_values.items():
        before_value = getattr(fresh, field)
        try:
            setattr(fresh, field, forged)
            reassignment_raised = False
        except AttributeError:
            reassignment_raised = True
        check(f"CF-P0-009-SEC(h2): reassigning {field} raises "
              "AttributeError and leaves the issued value unchanged",
              reassignment_raised
              and getattr(fresh, field) == before_value)
    try:
        fresh.forged_field = "forged"
        new_attr_raised = False
    except AttributeError:
        new_attr_raised = True
    check("CF-P0-009-SEC(h3): adding a NEW attribute to an issued "
          "context raises AttributeError",
          new_attr_raised and not hasattr(fresh, "forged_field"))
    try:
        del fresh.scope
        delete_raised = False
    except AttributeError:
        delete_raised = True
    check("CF-P0-009-SEC(h4): deleting a field of an issued context "
          "raises AttributeError",
          delete_raised and fresh.scope
          == "export voice-nila-001 for backup")
    check("CF-P0-009-SEC(h5): an issued context has no __dict__ "
          "escape (vars() raises TypeError)",
          not hasattr(fresh, "__dict__"))
    try:
        vars(fresh)
        vars_raised = False
    except TypeError:
        vars_raised = True
    check("CF-P0-009-SEC(h5b): vars() on an issued context raises "
          "TypeError",
          vars_raised)
    copied = copy.copy(fresh)
    deep_copied = copy.deepcopy(fresh)
    unpickled = pickle.loads(pickle.dumps(fresh))
    for label, clone in (("copy", copied), ("deepcopy", deep_copied),
                         ("pickle round-trip", unpickled)):
        try:
            clone.scope = "forged scope"
            clone_raised = False
        except AttributeError:
            clone_raised = True
        check(f"CF-P0-009-SEC(h6): a {label} of an issued context "
              "is frozen too (reassignment raises) and keeps the "
              "issued values",
              clone_raised and clone.scope
              == "export voice-nila-001 for backup"
              and clone.authorization_id == fresh.authorization_id)
    try:
        dataclasses.replace(fresh, scope="forged scope")
        replace_raised = False
    except TypeError:
        replace_raised = True
    check("CF-P0-009-SEC(h7): dataclasses.replace on an issued "
          "context raises TypeError (no replace backdoor)",
          replace_raised
          and fresh.scope == "export voice-nila-001 for backup")
    ctx_a = export_ctx()
    ctx_b = export_ctx()
    check("CF-P0-009-SEC(h8): two issued contexts have distinct "
          "authorization_ids",
          ctx_a.authorization_id != ctx_b.authorization_id)
    snapshot_a = (ctx_a.authorization_id, ctx_a.actor_owner_id,
                  ctx_a.actor_workspace_id, ctx_a.granted_by,
                  ctx_a.scope, ctx_a.action, ctx_a.character_id,
                  ctx_a.voice_profile_id,
                  ctx_a.provider_transmission_approved,
                  ctx_a.expires_at, ctx_a.revoked)
    check("CF-P0-009-SEC(h9): a fresh context is not revoked",
          not asset_policy.is_trusted_authorization_revoked(ctx_a))
    asset_policy.revoke_trusted_authorization_context(ctx_a)
    check("CF-P0-009-SEC(h10): revocation does not mutate the "
          "original context (every field, including revoked, keeps "
          "its issued value)",
          (ctx_a.authorization_id, ctx_a.actor_owner_id,
           ctx_a.actor_workspace_id, ctx_a.granted_by, ctx_a.scope,
           ctx_a.action, ctx_a.character_id, ctx_a.voice_profile_id,
           ctx_a.provider_transmission_approved, ctx_a.expires_at,
           ctx_a.revoked) == snapshot_a
          and ctx_a.revoked is False)
    check("CF-P0-009-SEC(h11): a revoked context is rejected by "
          "the export authorization path",
          bool(asset_policy.validate_private_voice_export(
              nila_voice, trusted_context=ctx_a)))
    check("CF-P0-009-SEC(h12): revoking one context does not revoke "
          "another — the unrevoked context still authorizes export",
          not asset_policy.validate_private_voice_export(
              nila_voice, trusted_context=ctx_b))
    try:
        asset_policy.revoke_trusted_authorization_context(
            {"authorization_id": ctx_b.authorization_id})
        revoke_fake_raised = False
    except TypeError:
        revoke_fake_raised = True
    check("CF-P0-009-SEC(h13): revoking a dict fake raises "
          "TypeError and leaves the real context unrevoked",
          revoke_fake_raised
          and not asset_policy.is_trusted_authorization_revoked(ctx_b))
    try:
        asset_policy.is_trusted_authorization_revoked(
            SimpleNamespace(authorization_id=ctx_b.authorization_id))
        check_fake_raised = False
    except TypeError:
        check_fake_raised = True
    check("CF-P0-009-SEC(h14): checking revocation of a fake "
          "context raises TypeError (fail closed)",
          check_fake_raised)
    forged_ctx = export_ctx(voice_profile_id="voice-aria-001")
    try:
        forged_ctx.voice_profile_id = "voice-nila-001"
        retarget_raised = False
    except AttributeError:
        retarget_raised = True
    check("CF-P0-009-SEC(h15): a context issued for another voice "
          "cannot be retargeted by reassignment, and export for "
          "the other voice still rejects",
          retarget_raised
          and forged_ctx.voice_profile_id == "voice-aria-001"
          and bool(asset_policy.validate_private_voice_export(
              nila_voice, trusted_context=forged_ctx)))
    check("CF-P0-009-SEC(h16): existing valid authorization use "
          "cases still work (fresh context allows export, and "
          "allows provider transmission when approved)",
          not asset_policy.validate_private_voice_export(
              nila_voice, trusted_context=export_ctx())
          and not asset_policy.validate_private_voice_export(
              nila_voice, trusted_context=export_ctx(
                  provider_transmission_approved=True),
              to_provider=True))

    # ------------------------------------------------------------------
    # (i) CF-WO-P0-009 (B) — v2.5 resolution fails closed without
    # a Character Registry; legacy v2.3 keeps its contract.
    # ------------------------------------------------------------------
    voice, errs = asset_policy.resolve_voice_for_production(
        v25_voice_registry, None, "char-nila-001",
        "voice-nila-001", "owner-a", "workspace-a")
    check("CF-P0-009-SEC(i1): v2.5 resolution WITHOUT a Character "
          "Registry fails (voice unresolved, explicit registry "
          "reason)",
          voice is None and bool(errs)
          and "v2.5 private voice resolution requires a valid "
          "Character Registry" in "; ".join(errs), "; ".join(errs))
    voice, errs = asset_policy.resolve_voice_for_production(
        v25_voice_registry, None, "char-nila-001",
        "voice-nila-001", "owner-a", "workspace-a",
        require_approved=False)
    check("CF-P0-009-SEC(i2): v2.5 resolution without a registry "
          "fails even when approval is not required (no silent "
          "fallback)",
          voice is None and bool(errs), "; ".join(errs))
    voice, errs = asset_policy.resolve_voice_for_production(
        v25_voice_registry, None, "char-nila-001",
        "voice-nila-001")
    check("CF-P0-009-SEC(i3): v2.5 resolution without a registry "
          "fails even with no requester either (registry is "
          "checked first, fail closed)",
          voice is None and bool(errs)
          and "Character Registry" in "; ".join(errs),
          "; ".join(errs))
    voice, errs = asset_policy.resolve_voice_for_production(
        v25_voice_registry, ["not-a-registry"], "char-nila-001",
        "voice-nila-001", "owner-a", "workspace-a")
    check("CF-P0-009-SEC(i4): v2.5 resolution with a non-dict "
          "Character Registry fails closed",
          voice is None and bool(errs)
          and "Character Registry" in "; ".join(errs),
          "; ".join(errs))
    voice, errs = asset_policy.resolve_voice_for_production(
        v25_voice_registry, {}, "char-nila-001",
        "voice-nila-001", "owner-a", "workspace-a")
    check("CF-P0-009-SEC(i5): v2.5 resolution with a registry "
          "missing the Character fails",
          voice is None and bool(errs)
          and "unknown character_id 'char-nila-001'" in "; ".join(errs),
          "; ".join(errs))
    mismatched_character = {"character_id": "char-nila-001",
                            "ownership": copy.deepcopy(OWNER_B)}
    voice, errs = asset_policy.resolve_voice_for_production(
        v25_voice_registry,
        {"char-nila-001": mismatched_character}, "char-nila-001",
        "voice-nila-001", "owner-a", "workspace-a")
    check("CF-P0-009-SEC(i6): v2.5 resolution with mismatched "
          "Character/Voice ownership fails",
          voice is None and bool(errs), "; ".join(errs))
    voice, errs = asset_policy.resolve_voice_for_production(
        v25_voice_registry, v25_registries, "char-aria-001",
        "voice-aria-001", "owner-a", "workspace-a")
    check("CF-P0-009-SEC(i7): v2.5 resolution with matching "
          "ownership + valid permissions succeeds (second record)",
          voice is not None and not errs
          and voice["voice_profile_id"] == "voice-aria-001",
          "; ".join(errs))
    voice, errs = asset_policy.resolve_voice_for_production(
        v25_voice_registry, v25_registries, "char-nila-001",
        "voice-nila-001", "owner-b", "workspace-b")
    check("CF-P0-009-SEC(i8): requester authorization is still "
          "enforced with a registry present (wrong owner rejects)",
          voice is None and bool(errs), "; ".join(errs))
    voice, errs = asset_policy.resolve_voice_for_production(
        legacy_registry, None, "char-nila-001", "voice-nila-001",
        require_approved=False)
    check("CF-P0-009-SEC(i9): legacy v2.3 keeps its historical "
          "contract — the same no-registry call shape that fails "
          "for v2.5 still resolves for v2.3 (version-aware, never "
          "a silent v2.5 fallback)",
          voice is not None and not errs, "; ".join(errs))

    print(f"test_private_voice_security: "
          f"{'PASS' if not failures else 'FAIL'} "
          f"({len(failures)} failure(s))")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
