#!/usr/bin/env python3
"""Consistency Frame P0 — asset-mode policy (pure logic, no I/O).

Implements the mode contract from PRODUCT_MODES_AND_ASSET_LIFECYCLE_BN.md
and the P0 Start-Now prompt §4. A mode is never inferred from an upload
alone; the caller must pass the mode the user actually chose.

Rules encoded here (and tested in tests/test_modes.py):
- UPLOAD_ONLY / TEMPORARY_ASSET_USE create NO permanent record.
- REGISTER_CHARACTER requires explicit authorisation + name + unique ID
  + at least one approved reference. Anything missing -> rejection.
- REGISTER_VOICE_PROFILE requires explicit authorisation + consent.
- REGISTER_SOUND_ASSET requires explicit instruction + licence.
- Voice profiles and sound assets are separate types; neither may be
  merged into a character record.
- REFERENCE_REVIEW never mutates canonical skills; only
  REFERENCE_LEARN_AND_UPDATE (with explicit user instruction) may
  propose a learning candidate, and even then only as a reviewable
  patch — never a direct permanent write.

Propose vs apply (independent-review correction, CF-WO-P0-002 §5):
proposing a skill patch and applying one are two different
permissions. `may_propose_skill_patch` allows writing a reviewable
patch file under `.consistency-frame/proposals/` — a proposal never
touches a canonical skill. `may_apply_skill_patch` allows applying
such a patch to a canonical skill, and only with a full, explicit
authorisation (granted_by + scope + branch + explicit_authorisation),
validated by `validate_skill_patch_application`. Intake alone never
carries an apply authorisation, so `intake_result` always reports
`may_apply_skill_patch: False`. `may_mutate_canonical_skills` is the
legacy combined gate: it returns True only when BOTH the propose
permission and a full apply authorisation are present.

Structured private ownership + conditional v2.5 voice-profile
validation (CF-WO-P0-007, Worker 2 — Corrections B + C):
- Ownership is the structured object in schemas/character-
  registration.json and schemas/voice-profile.json (owner_id +
  workspace_id + visibility + sharing). The IDs are stable,
  opaque, randomly generated local identifiers — never a real
  name, email or account detail. Visibility is private by
  default; sharing is none by default and requires an explicit
  future sharing permission. No cross-user sharing by default.
- The repo's JSON-Schema validator (scripts/validate-repo.py)
  supports only a restricted subset: it has NO if/then, allOf
  or dependentRequired, so a v2.5-conditional required field
  (e.g. ownership on a voice profile, which must stay optional
  for v2.3) CANNOT be expressed in the JSON Schema. The JSON
  Schema is therefore deliberately permissive for v2.5
  conditional fields, and `validate_voice_profile` here is the
  authoritative layer that enforces them. A record is fully
  valid v2.5 only when BOTH layers pass; the tests pin both
  layers' verdicts on every case so the layers never disagree
  silently.
- Consent governing rule (v2.5): consent_status governs;
  consent.granted must agree with it. For a user-recording,
  consent_status must be "granted" and consent.granted must be
  true. consent_status "not-required" is legitimate ONLY when
  human_voice_donor is explicitly false (no real person's
  voice was used) — never a bypass for real permission.
- Approval governing rule (v2.5): approval_status must exist.
  status "approved" requires approval_status "approved" and
  vice versa; a generated voice is never approved
  automatically — approval_status is "pending" until the user
  explicitly approves. Only an approved, correctly owned
  profile may be selected for production
  (`resolve_voice_for_production`).
- Provider transmission: voice data sent to a provider must be
  disclosed, user-approved, and recorded with provider +
  data-use scope (see `provider_transmission` in the voice
  schema). Nothing here ever promises data never leaves the
  device.
- Path safety: `resolve_private_path` rejects traversal and
  symlink escapes against a base directory; privateness is
  decided by ownership, never by a folder being named
  "private".

Fail-closed private voice security (CF-WO-P0-008):
- `resolve_voice_for_production` REQUIRES requester identity
  (owner + workspace) for private v2.5 voices. A missing
  requester is never an authorized internal request and `None`
  is never an authorization bypass. Legacy v2.3 records keep
  their historical contract (binding + approval only) and gain
  v2.5 protection only by explicit ownership assignment —
  ownership is never inferred from a filename, name or image.
- Private voice export requires a `TrustedAuthorizationContext`
  issued by `issue_trusted_authorization_context` — the local
  application authorization boundary. A caller-created dict
  (granted_by / scope / explicit_authorisation) is an untrusted
  request, never authority, and a forged granted_by is rejected.
  The context is a structural (type) boundary, not
  cryptographic proof of identity: the P1 runtime (app UI /
  session) must supply the actor identity at the boundary.
- All production access decisions go through one choke point,
  `authorize_action` (Correction E), with explicit action
  scopes: use_in_project, use_in_production,
  export_private_asset, transmit_to_provider,
  share_with_workspace. Permission to use a voice locally never
  implies permission to export it, and export never implies
  provider transmission.

Fail-closed private voice security, hardening (CF-WO-P0-009,
Tasks A + B):
- `TrustedAuthorizationContext` is genuinely immutable after
  issuance (a frozen flag enforced by `__setattr__` /
  `__delattr__`, with `__copy__` / `__deepcopy__` /
  `__setstate__` all returning frozen objects — `__slots__`
  alone never made it immutable). Reassigning any field raises
  AttributeError. Revocation lives OUTSIDE the context, in a
  separate module-level revocation registry keyed by the
  context's immutable `authorization_id`
  (`revoke_trusted_authorization_context` /
  `is_trusted_authorization_revoked`); revoking never mutates
  the issued context. `validate_private_voice_export` rejects a
  context whose id is in the registry.
- `resolve_voice_for_production` requires a valid Character
  Registry for a v2.5 voice profile: a missing (or non-dict)
  registry, a missing Character, or mismatched Character/Voice
  ownership all fail closed with the voice unresolved. Legacy
  v2.3 records keep their historical contract — v2.5 never
  silently falls back to it.

Factory-issued authorization contexts (CF-WO-P0-010):
- P0-009 made the context immutable, but immutability alone
  never proved issuance: the constructor sentinel could be
  imported, `__setstate__` could initialize a `__new__` object,
  and pickle/copy produced further objects that all passed the
  `isinstance` check in `validate_private_voice_export` — with
  zero factory calls. The consumer now verifies ISSUANCE, not
  type: a process-local, identity-based issuance registry
  (`_ISSUED_AUTHORIZATION_CONTEXTS`, a `weakref.WeakSet`) holds
  the exact objects the factory issued, and
  `is_factory_issued_trusted_authorization_context` is the single
  check every authorization boundary uses. A directly constructed,
  `__new__`/`__setstate__`-built, copied or deserialized object
  is never in the registry and is always rejected, however
  genuine its fields look. Serialization of a context is
  rejected outright (`__reduce__` / `__reduce_ex__` /
  `__getstate__` / `__setstate__` all raise TypeError); copying
  returns a frozen but UNREGISTERED clone with no authority.
  This is a process-level integrity contract, NOT cryptographic
  proof of identity and NOT protection against malicious code
  running in the same process — authenticated application-session
  identity remains P1.
"""
from __future__ import annotations

import copy
import os
import re
import uuid
import weakref
from datetime import datetime, timezone

MODES = [
    "UPLOAD_ONLY", "TEMPORARY_ASSET_USE", "PROJECT_CONSISTENCY",
    "REGISTER_CHARACTER", "REGISTER_VOICE_PROFILE", "REGISTER_SOUND_ASSET",
    "GENERATE_FROM_SCRIPT", "EDIT_EXISTING_MEDIA", "REFERENCE_REVIEW",
    "REFERENCE_LEARN_AND_UPDATE", "VIDEO_QC", "REMAKE_OR_TRANSFORM",
    "REPORT_UPDATE_ONLY",
]

# Modes that may never create a permanent record, whatever else is set.
NO_PERMANENT_RECORD_MODES = {"UPLOAD_ONLY", "TEMPORARY_ASSET_USE"}

# Modes that may propose a skill change (only as a reviewable patch).
CAN_PROPOSE_SKILL_CHANGE = {"REFERENCE_LEARN_AND_UPDATE"}

# Where proposed skill patches live: reviewable patch files only.
# Canonical skills are never touched by a proposal.
PROPOSALS_DIR = ".consistency-frame/proposals"


def may_create_permanent_record(mode: str) -> bool:
    """True only for modes whose purpose is permanent registration."""
    if mode not in MODES:
        raise ValueError(f"unknown mode: {mode}")
    return mode in {"REGISTER_CHARACTER", "REGISTER_VOICE_PROFILE",
                    "REGISTER_SOUND_ASSET"}


def validate_character_registration(record: dict) -> list[str]:
    """Return a list of rejection reasons; empty list means allowed.

    `record` keys: explicit_authorisation (bool), name (str),
    id (str), references (list of non-empty strings).
    """
    errors = []
    if not record.get("explicit_authorisation"):
        errors.append("missing explicit authorisation")
    if not record.get("name"):
        errors.append("missing name")
    if not record.get("id"):
        errors.append("missing unique id")
    refs = record.get("references") or []
    if not refs or not all(isinstance(r, str) and r for r in refs):
        errors.append("missing approved reference(s)")
    return errors


def validate_voice_registration(record: dict) -> list[str]:
    errors = []
    if not record.get("explicit_authorisation"):
        errors.append("missing explicit authorisation")
    if not record.get("character_id"):
        errors.append("missing character_id link")
    consent = record.get("consent") or {}
    if not consent.get("granted"):
        errors.append("missing rights/consent")
    if not record.get("reference_audio"):
        errors.append("missing reference audio pointer")
    return errors


def validate_sound_registration(record: dict) -> list[str]:
    errors = []
    if not record.get("explicit_instruction"):
        errors.append("missing explicit instruction to retain/reuse")
    if not record.get("licence"):
        errors.append("missing licence/permission")
    if not record.get("kind"):
        errors.append("missing sound kind")
    return errors


def check_character_record_separation(character: dict) -> list[str]:
    """A character record must not embed voice or sound data.

    Voice/sound live in their own records, linked by ID only.
    """
    errors = []
    for field in ("voice_tags", "voice_seed", "reference_audio",
                  "sound_file", "theme_music", "sound_assets"):
        if field in character:
            errors.append(f"character record must not contain '{field}' "
                          "(use a separate voice-profile / sound-asset record)")
    return errors


def may_propose_skill_patch(mode: str, explicit_user_instruction: bool) -> bool:
    """True only for REFERENCE_LEARN_AND_UPDATE with explicit instruction.

    A proposal is a reviewable patch file under PROPOSALS_DIR — it
    never writes a canonical skill. Proposing is not applying.
    """
    if mode not in MODES:
        raise ValueError(f"unknown mode: {mode}")
    return mode in CAN_PROPOSE_SKILL_CHANGE and bool(explicit_user_instruction)


def validate_skill_patch_application(authorization) -> list[str]:
    """Return a list of rejection reasons; empty list means allowed.

    `authorization` keys: granted_by (non-empty string), scope
    (non-empty string), branch (non-empty string),
    explicit_authorisation (bool, must be True). Anything missing or
    empty -> rejection. Mirrors validate_character_registration style.
    """
    errors = []
    if not isinstance(authorization, dict):
        return ["missing skill-patch authorisation"]
    if not authorization.get("granted_by") or \
            not isinstance(authorization.get("granted_by"), str):
        errors.append("missing granted_by")
    if not authorization.get("scope") or \
            not isinstance(authorization.get("scope"), str):
        errors.append("missing scope")
    if not authorization.get("branch") or \
            not isinstance(authorization.get("branch"), str):
        errors.append("missing branch")
    if authorization.get("explicit_authorisation") is not True:
        errors.append("missing explicit authorisation to apply the patch")
    return errors


def may_apply_skill_patch(authorization) -> bool:
    """True only with a full, explicit apply authorisation.

    Propose permission alone never applies a patch; intake alone
    never carries an authorisation.
    """
    return validate_skill_patch_application(authorization) == []


def may_mutate_canonical_skills(mode: str, explicit_user_instruction: bool,
                                authorization=None) -> bool:
    """Legacy combined gate: True only when BOTH halves are present.

    Propose permission (REFERENCE_LEARN_AND_UPDATE + explicit user
    instruction) AND a full apply authorisation
    (validate_skill_patch_application == []). A proposal alone never
    mutates a canonical skill.
    """
    if mode not in MODES:
        raise ValueError(f"unknown mode: {mode}")
    return (may_propose_skill_patch(mode, explicit_user_instruction)
            and may_apply_skill_patch(authorization))


def intake_result(mode: str, explicit_user_instruction: bool = False) -> dict:
    """What an intake in this mode is allowed to do (for reports/tests).

    Propose permission needs the explicit instruction passed in;
    without it, no proposal is reported. Apply is always False from
    intake alone — intake never carries the apply authorisation.
    """
    if mode not in MODES:
        raise ValueError(f"unknown mode: {mode}")
    return {
        "mode": mode,
        "creates_permanent_record": may_create_permanent_record(mode),
        "may_propose_skill_change": mode in CAN_PROPOSE_SKILL_CHANGE,
        "may_propose_skill_patch": may_propose_skill_patch(
            mode, explicit_user_instruction),
        # Intake never carries an apply authorisation: always False.
        "may_apply_skill_patch": False,
        "retention": ("temporary" if mode in NO_PERMANENT_RECORD_MODES
                      else "project_or_registered"),
    }


# --- Structured private ownership (CF-WO-P0-007, Correction B) -----
# Exact shape from schemas/character-registration.json and
# schemas/voice-profile.json. IDs are opaque local identifiers.
OWNERSHIP_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9\-]{2,63}$")
OWNERSHIP_VISIBILITY = ("private", "shared")
OWNERSHIP_SHARING = ("none", "workspace", "explicit")


def validate_ownership(ownership) -> list[str]:
    """Validate a structured ownership object. Empty list = valid.

    Requires owner_id + workspace_id (opaque local IDs, never a
    real name/email/account detail) + visibility + sharing, no
    extra keys. Visibility/sharing must agree: private implies
    sharing "none"; shared requires sharing "workspace" or
    "explicit" (an explicit future sharing permission).
    """
    errors = []
    if not isinstance(ownership, dict):
        return ["missing ownership (structured owner + workspace binding)"]
    for field in ("owner_id", "workspace_id", "visibility", "sharing"):
        if field not in ownership:
            errors.append(f"ownership is missing '{field}'")
    for field in ("owner_id", "workspace_id"):
        value = ownership.get(field)
        if value is not None and (
                not isinstance(value, str)
                or not OWNERSHIP_ID_PATTERN.search(value)):
            errors.append(f"ownership.{field} {value!r} is not a valid "
                          "opaque local identifier")
    visibility = ownership.get("visibility")
    if visibility is not None and visibility not in OWNERSHIP_VISIBILITY:
        errors.append(f"ownership.visibility {visibility!r} not in "
                      f"{list(OWNERSHIP_VISIBILITY)}")
    sharing = ownership.get("sharing")
    if sharing is not None and sharing not in OWNERSHIP_SHARING:
        errors.append(f"ownership.sharing {sharing!r} not in "
                      f"{list(OWNERSHIP_SHARING)}")
    if visibility == "private" and sharing not in (None, "none"):
        errors.append("ownership.visibility 'private' requires "
                      "sharing 'none'")
    if visibility == "shared" and sharing == "none":
        errors.append("ownership.visibility 'shared' requires an "
                      "explicit sharing permission (sharing 'workspace' "
                      "or 'explicit'), not 'none'")
    for key in ownership:
        if key not in ("owner_id", "workspace_id", "visibility",
                       "sharing"):
            errors.append(f"ownership has unexpected field '{key}'")
    return errors


def ownerships_match(a, b) -> bool:
    """True only when two ownership objects name the same owner in
    the same workspace. Either side missing/invalid -> False."""
    if not isinstance(a, dict) or not isinstance(b, dict):
        return False
    return (a.get("owner_id") and a.get("owner_id") == b.get("owner_id")
            and a.get("workspace_id")
            and a.get("workspace_id") == b.get("workspace_id"))


def ownership_allows_access(ownership, requesting_owner_id,
                            requesting_workspace_id=None) -> bool:
    """True when the requester may access an asset with this
    ownership. Private by default: only the owning owner_id in
    the owning workspace. sharing "workspace" additionally
    admits any owner in the same workspace. sharing "explicit"
    admits only the owner (an explicit grant record is not
    modelled here, so no third party is admitted). Privateness
    is decided by this ownership object, never by a folder
    being named "private".
    """
    if not isinstance(ownership, dict):
        return False
    if validate_ownership(ownership):
        return False
    if requesting_workspace_id is not None and \
            requesting_workspace_id != ownership.get("workspace_id"):
        return False
    if requesting_owner_id == ownership.get("owner_id"):
        return True
    if ownership.get("visibility") == "shared" and \
            ownership.get("sharing") == "workspace" and \
            requesting_workspace_id == ownership.get("workspace_id"):
        return True
    return False


# --- Centralized authorization (CF-WO-P0-008, Correction E) -----------
# One choke point for every production access decision. Do not create
# a second, slightly different privacy rule elsewhere: resolvers,
# export validation and timeline validation all call authorize_action
# (or authorize_export, which builds on it). Permission for one
# action never implies permission for another: local production use
# does not imply export, export does not imply provider transmission.
ACTION_SCOPES = ("use_in_project", "use_in_production",
                 "export_private_asset", "transmit_to_provider",
                 "share_with_workspace")


def authorize_action(action, ownership, requesting_owner_id,
                     requesting_workspace_id) -> list[str]:
    """Authorize one action for one requester against one ownership
    record. Returns rejection reasons; [] = allowed.

    Fail closed: an unknown action, an invalid ownership record, or
    a missing requester owner/workspace is a rejection. `None` is
    never an authorized internal request — a caller that cannot name
    its owner and workspace cannot be authorized. Sharing follows
    ownership_allows_access (private + none: owner only in the
    owning workspace; shared + workspace: any owner in the same
    workspace; shared + explicit: owner only, an explicit grant
    record is not modelled here).
    """
    errors = []
    if action not in ACTION_SCOPES:
        errors.append(f"unknown action {action!r} (must be one of "
                      f"{list(ACTION_SCOPES)})")
    if validate_ownership(ownership):
        errors.append("asset has no valid ownership binding — access "
                      "blocked")
    if not requesting_owner_id or not isinstance(requesting_owner_id, str):
        errors.append("requesting owner identity is required — a "
                      "missing requester identity is never an "
                      "authorized internal request")
    if not requesting_workspace_id or \
            not isinstance(requesting_workspace_id, str):
        errors.append("requesting workspace identity is required — a "
                      "missing requester identity is never an "
                      "authorized internal request")
    if errors:
        return errors
    if not ownership_allows_access(ownership, requesting_owner_id,
                                   requesting_workspace_id):
        errors.append("requester is not allowed access to this asset "
                      "(private by default; no cross-user / "
                      "cross-workspace use without an explicit sharing "
                      "permission)")
    return errors


def check_voice_binding(voice_registry, character_id, voice_profile_id,
                        character_registry=None) -> list[str]:
    """Production character/voice binding check (Correction D: moved
    out of tests/test_character_registration.py, which duplicated
    this rule).

    The voice must exist, belong to the requested character, and —
    when a character registry is given — its ownership must match
    the character's ownership. This is a BINDING check, not a
    production-use authorization: it does not check requester
    identity or approval. Production selection must use
    resolve_voice_for_production, which enforces those too.
    """
    if not isinstance(voice_registry, dict):
        return ["voice registry is not an object"]
    vp = voice_registry.get(voice_profile_id)
    if vp is None:
        return [f"unknown voice_profile_id {voice_profile_id!r}"]
    if vp.get("character_id") != character_id:
        return [f"voice_profile_id {voice_profile_id!r} belongs to "
                f"character {vp.get('character_id')!r}, not "
                f"{character_id!r} — cross-character assignment "
                "rejected"]
    if character_registry is not None:
        character = character_registry.get(character_id)
        if character is None:
            return [f"unknown character_id {character_id!r}"]
        if not ownerships_match(vp.get("ownership"),
                                character.get("ownership")):
            return ["voice profile ownership does not match the "
                    "character ownership (owner/workspace must match)"]
    return []


def resolve_for_user(record, requesting_owner_id,
                     requesting_workspace_id=None) -> list[str]:
    """Owner/workspace-scoped resolution of one record (Correction D:
    moved out of tests/test_character_registration.py, which
    duplicated this rule).

    A structured ownership object, when present, governs — the
    requester must be its owner_id in its workspace_id (see
    ownership_allows_access). The legacy ownership_scope string is
    consulted ONLY for records with no ownership object (migration
    fallback). Returns rejection reasons; [] = the record resolves
    for this requester.
    """
    if not isinstance(record, dict):
        return ["record is not an object"]
    ownership = record.get("ownership")
    if isinstance(ownership, dict):
        if ownership_allows_access(ownership, requesting_owner_id,
                                   requesting_workspace_id):
            return []
        return [f"asset owned by {ownership.get('owner_id')!r} in "
                f"workspace {ownership.get('workspace_id')!r} cannot "
                f"be resolved under owner {requesting_owner_id!r} "
                f"(workspace {requesting_workspace_id!r})"]
    if record.get("ownership_scope") != requesting_owner_id:
        return [f"asset owned by {record.get('ownership_scope')!r} "
                f"cannot be resolved under user "
                f"{requesting_owner_id!r}"]
    return []


# --- Conditional v2.5 voice-profile validation (Correction C) --------
# The JSON Schema cannot express these (validator subset has no
# if/then/allOf/dependentRequired), so this function is the
# authoritative layer for every rule below. v2.3 records are
# exempt: the v2.5 rules apply only when schema_version == "2.5".
# A record with no schema_version gets only the base (legacy)
# rules — its version is unknown, and the JSON Schema (which
# requires schema_version) is what rejects the missing version.
VOICE_SOURCES = ("user-recording", "ai-generated")


def validate_voice_profile(record: dict, character: dict | None = None) -> list[str]:
    """Conditional v2.5 voice-profile validation. Empty = valid.

    Base rules (every version): a character_id link, a
    reference_audio pointer, and consent.granted true.
    v2.5-only rules (schema_version == "2.5"): voice_profile_id,
    source, ownership (explicit owner/workspace binding),
    approval_status and consent_status must all be present;
    source-conditional rules (below); status/approval_status
    must agree; a "not-required" consent is legitimate only
    when human_voice_donor is explicitly false; provider
    transmission, when recorded, must be disclosed + approved
    with provider + data-use scope. When `character` is given,
    the voice's character_id and ownership must match it, and
    the voice must not be usable for another character.
    """
    errors = []
    if not isinstance(record, dict):
        return ["voice profile is not an object"]
    if not record.get("character_id"):
        errors.append("missing character_id link")
    if not record.get("reference_audio"):
        errors.append("missing reference audio pointer")
    consent = record.get("consent")
    if not isinstance(consent, dict) or consent.get("granted") is not True:
        errors.append("missing rights/consent (consent.granted must be true)")
    if character is not None:
        if not isinstance(character, dict):
            errors.append("character record is not an object")
        else:
            if record.get("character_id") != character.get("character_id"):
                errors.append(
                    f"voice profile belongs to character "
                    f"{record.get('character_id')!r}, not "
                    f"{character.get('character_id')!r} — cross-character "
                    "assignment rejected")
            if not ownerships_match(record.get("ownership"),
                                    character.get("ownership")):
                errors.append("voice profile ownership does not match "
                              "the character ownership (owner/workspace "
                              "must match)")
    if record.get("schema_version") != "2.5":
        return errors
    # --- v2.5 minimum fields -----------------------------------------
    if not record.get("voice_profile_id"):
        errors.append("v2.5: missing voice_profile_id")
    source = record.get("source")
    if source not in VOICE_SOURCES:
        errors.append(f"v2.5: source {source!r} not in "
                      f"{sorted(VOICE_SOURCES)}")
    errors.extend(validate_ownership(record.get("ownership")))
    approval = record.get("approval_status")
    if approval not in ("pending", "approved", "rejected"):
        errors.append(f"v2.5: approval_status {approval!r} must exist "
                      "(pending, approved or rejected)")
    consent_status = record.get("consent_status")
    if consent_status not in ("granted", "pending", "denied",
                              "not-required"):
        errors.append(f"v2.5: consent_status {consent_status!r} must "
                      "exist (granted, pending, denied or not-required)")
    # Status / approval agreement: status "approved" without an
    # approval record is invalid, and vice versa. A generated
    # voice is never approved automatically — approval_status
    # stays "pending" until the user explicitly approves.
    status = record.get("status")
    if status == "approved" and approval != "approved":
        errors.append("v2.5: status 'approved' without approval_status "
                      "'approved' is invalid (no approval record)")
    if approval == "approved" and status != "approved":
        errors.append("v2.5: approval_status 'approved' but status is "
                      f"{status!r} (must be 'approved')")
    # Consent governing rule: consent_status governs;
    # consent.granted must agree with it.
    if consent_status == "granted" and consent.get("granted") is not True:
        errors.append("v2.5: consent_status 'granted' but "
                      "consent.granted is not true")
    if consent_status == "denied" and consent.get("granted") is True:
        errors.append("v2.5: consent_status 'denied' but "
                      "consent.granted is true")
    # Human-donor rule: "not-required" is legitimate ONLY when
    # no real person's voice was used, accurately recorded as
    # human_voice_donor false. A donor voice always needs
    # explicit permission + granted consent.
    donor = record.get("human_voice_donor")
    if donor is not None and not isinstance(donor, bool):
        errors.append("v2.5: human_voice_donor must be a boolean")
    if consent_status == "not-required" and donor is not False:
        errors.append("v2.5: consent_status 'not-required' is legitimate "
                      "only when human_voice_donor is false (no real "
                      "person's voice was used); donor status is "
                      "unrecorded or true — never use 'not-required' to "
                      "bypass actual permission requirements")
    if donor is True and consent_status != "granted":
        errors.append("v2.5: a real-person voice donor requires explicit "
                      "permission (consent_status 'granted')")
    # --- Source-conditional rules -------------------------------------
    if source == "user-recording":
        assets = record.get("audio_reference_assets")
        if not isinstance(assets, list) or not assets or not any(
                isinstance(a, dict) and a.get("path")
                and a.get("role") in ("voice-reference", "voice-sample")
                for a in assets):
            errors.append("v2.5: user-recording needs at least one "
                          "approved audio reference asset "
                          "(audio_reference_assets with path + "
                          "voice-reference/voice-sample role)")
        if donor is False:
            errors.append("v2.5: user-recording is a recording of a real "
                          "person's voice, so human_voice_donor cannot "
                          "be false")
        if consent_status != "granted":
            errors.append("v2.5: user-recording needs consent explicitly "
                          "granted (consent_status 'granted')")
    if source == "ai-generated":
        if not record.get("provider"):
            errors.append("v2.5: ai-generated voice needs a provider "
                          "(provider identification governs)")
        if not record.get("model") and not record.get("model_version"):
            errors.append("v2.5: ai-generated voice needs model "
                          "identification (model and/or model_version)")
    # --- Provider transmission disclosure ------------------------------
    transmission = record.get("provider_transmission")
    if transmission is not None:
        if not isinstance(transmission, dict):
            errors.append("v2.5: provider_transmission must be an object")
        else:
            if transmission.get("disclosed") is not True:
                errors.append("v2.5: provider transmission must be "
                              "disclosed to the user (disclosed must be "
                              "true) — never send voice data to a "
                              "provider without disclosing it")
            if not transmission.get("provider"):
                errors.append("v2.5: provider_transmission must record "
                              "the provider")
            if not transmission.get("data_use_scope"):
                errors.append("v2.5: provider_transmission must record "
                              "the data-use scope")
            if not transmission.get("approved_by"):
                errors.append("v2.5: provider_transmission must record "
                              "who approved it (approved_by)")
    return errors


def resolve_voice_for_production(voice_registry, character_registry,
                                 character_id, voice_profile_id,
                                 requesting_owner_id=None,
                                 requesting_workspace_id=None,
                                 require_approved=True):
    """Production voice resolver. Returns (voice_or_None, errors).

    A voice may be selected for production only when ALL hold:
    (1) the voice exists and its character_id is the requested
    character (cross-character assignment rejected); (2) for a
    v2.5 voice the Character Registry is REQUIRED — a missing
    (or non-dict) registry, a missing Character, or mismatched
    Character/Voice ownership all fail closed and the voice is
    never resolved (CF-WO-P0-009 B; there is no legacy fallback
    for v2.5). A non-2.5 (legacy) record keeps its historical
    contract: the registry is consulted only when given, and the
    Character existence / ownership checks run only then; (3)
    CF-WO-P0-008 (A): for a private v2.5 voice the REQUESTER
    identity is mandatory — both requesting_owner_id and
    requesting_workspace_id must be provided and authorized
    (authorize_action, action "use_in_production"). A missing
    requester is never an authorized internal request, there is
    no silent fallback to the character's owner, and None is
    never an authorization bypass; (4) the record passes the
    v2.5 conditional validation; (5) when require_approved,
    approval_status and status are both "approved" — a pending
    profile is a valid record but never an approved production
    voice, and sample-generation success is not user approval.

    Legacy compatibility: a record that is NOT v2.5 keeps its
    historical contract (binding + validation + approval; the
    requester is checked only when given, as before). A legacy
    record that lacks reliable ownership information does NOT
    automatically become available for private v2.5 production
    use: it gains v2.5 protection only by explicit ownership
    assignment (an ownership object matching its character, plus
    schema_version "2.5"). Ownership is never inferred from a
    filename, directory name, character name or uploaded image,
    and a missing owner is never silently assigned.
    """
    errors = []
    if not isinstance(voice_registry, dict):
        return None, ["voice registry is not an object"]
    vp = voice_registry.get(voice_profile_id)
    if vp is None:
        return None, [f"unknown voice_profile_id {voice_profile_id!r}"]
    if vp.get("character_id") != character_id:
        return None, [f"voice_profile_id {voice_profile_id!r} belongs "
                      f"to character {vp.get('character_id')!r}, not "
                      f"{character_id!r} — cross-character assignment "
                      "rejected"]
    is_v25 = vp.get("schema_version") == "2.5"
    character = None
    if is_v25:
        # CF-WO-P0-009 (B): a v2.5 private voice is NEVER
        # resolvable without its Character Registry. A missing
        # registry previously skipped the Character existence and
        # Character/Voice ownership checks entirely (character
        # stayed None and validation ran against no character) —
        # that silent skip is closed here: fail closed, voice
        # unresolved, with an explicit reason.
        if not isinstance(character_registry, dict):
            return None, ["v2.5 private voice resolution requires a "
                          "valid Character Registry — no Character "
                          "Registry was provided, so the voice "
                          "cannot be resolved (fail closed: a v2.5 "
                          "private voice is never resolvable without "
                          "its Character Registry)"]
        character = character_registry.get(character_id)
        if character is None:
            return None, [f"unknown character_id {character_id!r}"]
        if not isinstance(character, dict):
            return None, [f"character record for {character_id!r} "
                          "is not an object — v2.5 private voice "
                          "resolution fails closed"]
        if not ownerships_match(vp.get("ownership"),
                                character.get("ownership")):
            return None, ["voice profile ownership does not match the "
                          "character ownership (owner/workspace must "
                          "match)"]
    elif character_registry is not None:
        character = character_registry.get(character_id)
        if character is None:
            return None, [f"unknown character_id {character_id!r}"]
        if not ownerships_match(vp.get("ownership"),
                                character.get("ownership")):
            return None, ["voice profile ownership does not match the "
                          "character ownership (owner/workspace must "
                          "match)"]
    errors.extend(validate_voice_profile(vp, character))
    if vp.get("schema_version") == "2.5":
        # Private v2.5 production selection: requester identity is
        # mandatory (CF-WO-P0-008 A). authorize_action fails closed
        # on a missing owner/workspace and on unauthorized access.
        errors.extend(authorize_action(
            "use_in_production", vp.get("ownership"),
            requesting_owner_id, requesting_workspace_id))
    elif requesting_owner_id is not None or \
            requesting_workspace_id is not None:
        # Legacy (non-2.5) contract, unchanged: the requester is
        # checked only when given.
        if not ownership_allows_access(
                vp.get("ownership"), requesting_owner_id,
                requesting_workspace_id):
            errors.append("voice profile is not accessible to this "
                          "owner/workspace (private by default; no "
                          "cross-user sharing)")
    if require_approved:
        if vp.get("approval_status") != "approved" or \
                vp.get("status") != "approved":
            errors.append("only an approved voice profile may be "
                          "selected for production (approval_status and "
                          "status must both be 'approved'; a pending "
                          "profile is not an approved production voice)")
    if errors:
        return None, errors
    return vp, []


# --- Trusted authorization context (CF-WO-P0-008, Correction B) -----
# A private voice export must be authorized by the OWNER through the
# local application's trusted authorization boundary — never by a
# caller-created JSON dictionary. The boundary is structural (a
# dedicated class only the factory below can construct), NOT
# cryptographic proof of identity: a local pure-Python function
# cannot prove who the human at the keyboard is. The P1 runtime
# (first-run registration UI / app session) must supply the actor
# identity at the boundary; until then the factory IS the boundary
# and its caller MUST be the trusted local application. Passing
# someone else's IDs to the factory is boundary misuse, not a
# validator bypass — the validator still checks the issued context
# against the asset owner, workspace, character and voice, so a
# context issued for another asset authorizes nothing here.
#
# CF-WO-P0-010 — the sentinel alone is NOT the trust anchor. The
# sentinel is a module-level object and can be imported, so direct
# construction with it, `__new__` + `__setstate__`, pickle and copy
# all used to produce objects that passed the old `isinstance`
# check with zero factory calls. The trust anchor is the
# process-local issuance registry below: only the exact objects
# the factory registered are accepted, and every authorization
# boundary verifies issuance with
# `is_factory_issued_trusted_authorization_context` — never a bare
# `isinstance`. The registry is identity-based (a WeakSet over
# objects with identity equality/hash), so two contexts with
# identical fields are distinct entries, and an entry vanishes
# when its object is garbage-collected (no leak).
_AUTHORIZATION_BOUNDARY = object()

_ISSUED_AUTHORIZATION_CONTEXTS: "weakref.WeakSet" = weakref.WeakSet()


def _utc_now_iso() -> str:
    """Current UTC time as an ISO-8601 'Z' string (lexicographic
    comparison works for expiry checks)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class TrustedAuthorizationContext:
    """An authorization context issued by the local application
    authorization boundary (see issue_trusted_authorization_context).

    Fields: authorization_id (an immutable per-issuance identifier
    minted by the factory — the revocation registry keys on it),
    actor_owner_id / actor_workspace_id (the actor the boundary
    authenticated), granted_by (who granted the authorization —
    must be the asset owner), scope (non-empty description of the
    authorized export), action (one of ACTION_SCOPES — export
    requires "export_private_asset"), character_id /
    voice_profile_id (the exact asset this authorization covers —
    an authorization for one character or voice never covers
    another), provider_transmission_approved (whether this
    authorization also permits sending the voice to an external
    provider — a separate permission from export), expires_at
    (ISO-8601 UTC string or None = no expiry), revoked (the
    issuance-time revocation flag — always False for a
    factory-issued context; revocation after issuance NEVER
    mutates this field, it is recorded in the separate
    revocation registry, see revoke_trusted_authorization_context).

    Instances are genuinely immutable after issuance
    (CF-WO-P0-009 A). `__slots__` alone did NOT make them so —
    it only prevented adding NEW attributes, while every listed
    field could still be reassigned (`ctx.revoked = True`
    succeeded). Immutability is therefore enforced, not assumed:
    `__init__` writes every field with `object.__setattr__` and
    then sets the `_frozen` flag; `__setattr__` and
    `__delattr__` raise AttributeError on a frozen instance for
    ANY attribute (existing or new); the class has no `__dict__`
    slot, so there is no `__dict__` escape; and `__copy__` /
    `__deepcopy__` produce frozen objects, so copying a context
    cannot manufacture a mutable one. There is no public
    `replace` / setter backdoor: `dataclasses.replace` does not
    apply (this is not a dataclass) and direct construction
    raises TypeError — only the factory, holding the boundary
    sentinel, may create one. A plain dict is never an instance
    of this class, so no caller-created JSON can pass the
    isinstance check in validate_private_voice_export.

    Immutability is NOT issuance (CF-WO-P0-010). An immutable
    object is still untrusted unless the factory registered this
    exact instance: equality and hashing are IDENTITY-based
    (`__eq__` is `is`, `__hash__` is `object.__hash__`), so the
    issuance registry (`_ISSUED_AUTHORIZATION_CONTEXTS`) tracks
    exact objects, never field values. Serialization is refused
    outright — `__reduce__`, `__reduce_ex__`, `__getstate__`
    and `__setstate__` all raise TypeError — so no serialized
    representation can ever restore a trusted context, and no
    serialized representation can transfer authority to another
    object or process. `__copy__` / `__deepcopy__` return a
    frozen clone with the same field values (including the same
    `authorization_id`, so copying can never reset revocation
    state) that is deliberately NOT registered: the clone looks
    like the original but has no authority and is rejected by
    every authorization consumer.
    """
    __slots__ = ("authorization_id", "actor_owner_id",
                 "actor_workspace_id", "granted_by", "scope",
                 "action", "character_id", "voice_profile_id",
                 "provider_transmission_approved", "expires_at",
                 "revoked", "_frozen", "__weakref__")

    # Data slots only (excludes "__weakref__", which is a
    # weak-reference slot, not a field, and cannot be assigned).
    _DATA_SLOTS = ("authorization_id", "actor_owner_id",
                   "actor_workspace_id", "granted_by", "scope",
                   "action", "character_id", "voice_profile_id",
                   "provider_transmission_approved", "expires_at",
                   "revoked", "_frozen")

    def __eq__(self, other):
        # Identity equality ONLY: two contexts with identical
        # fields are still distinct objects. A value-equality
        # implementation would let a forged object compare equal
        # to a genuine one and could confuse the issuance
        # registry (a WeakSet) into treating them as the same.
        return self is other

    def __ne__(self, other):
        return not self.__eq__(other)

    __hash__ = object.__hash__

    def __init__(self, *, _boundary, actor_owner_id,
                 actor_workspace_id, granted_by, scope, action,
                 character_id, voice_profile_id,
                 provider_transmission_approved=False, expires_at=None,
                 revoked=False, authorization_id=None):
        if _boundary is not _AUTHORIZATION_BOUNDARY:
            raise TypeError(
                "TrustedAuthorizationContext must be issued by "
                "issue_trusted_authorization_context() — the local "
                "application authorization boundary — never "
                "constructed directly")
        # Write through object.__setattr__: __setattr__ below
        # refuses every write on a frozen instance, and the
        # instance is frozen by the last write here.
        object.__setattr__(
            self, "authorization_id",
            authorization_id if isinstance(authorization_id, str)
            and authorization_id else uuid.uuid4().hex)
        object.__setattr__(self, "actor_owner_id", actor_owner_id)
        object.__setattr__(self, "actor_workspace_id",
                           actor_workspace_id)
        object.__setattr__(self, "granted_by", granted_by)
        object.__setattr__(self, "scope", scope)
        object.__setattr__(self, "action", action)
        object.__setattr__(self, "character_id", character_id)
        object.__setattr__(self, "voice_profile_id", voice_profile_id)
        object.__setattr__(self, "provider_transmission_approved",
                           provider_transmission_approved)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(self, "revoked", revoked)
        object.__setattr__(self, "_frozen", True)

    def __setattr__(self, name, value):
        if getattr(self, "_frozen", False):
            raise AttributeError(
                "TrustedAuthorizationContext is immutable after "
                f"issuance — cannot reassign {name!r} (issue a new "
                "context at the authorization boundary instead)")
        object.__setattr__(self, name, value)

    def __delattr__(self, name):
        if getattr(self, "_frozen", False):
            raise AttributeError(
                "TrustedAuthorizationContext is immutable after "
                f"issuance — cannot delete {name!r}")
        object.__delattr__(self, name)

    def _frozen_copy(self, deep=False, memo=None):
        """A frozen copy with the same field values (internal
        only — the copy path cannot manufacture a mutable
        context: the copy is frozen before it is returned).

        CF-WO-P0-010: the copy is deliberately NOT registered in
        the issuance registry. It is a value-identical but
        authority-less representation: it keeps the same
        `authorization_id` (so a copy of a revoked context
        still carries the revoked id and can never reset
        revocation state), but no authorization consumer accepts
        it, because only the exact factory-issued instance is
        trusted. Copying is a safe, non-crashing operation; it
        never creates an independently valid authorization."""
        clone = object.__new__(type(self))
        for slot in self._DATA_SLOTS:
            value = getattr(self, slot)
            if deep:
                value = copy.deepcopy(value, memo)
            object.__setattr__(clone, slot, value)
        # Freeze explicitly: the clone is frozen even if the
        # source was somehow unfrozen when copied.
        object.__setattr__(clone, "_frozen", True)
        return clone

    def __copy__(self):
        return self._frozen_copy()

    def __deepcopy__(self, memo):
        return self._frozen_copy(deep=True, memo=memo)

    def __getstate__(self):
        # CF-WO-P0-010: a trusted authorization context has no
        # serializable representation. Refusing state extraction
        # is part of refusing serialization outright (see
        # __reduce_ex__): no serialized form of an authorization
        # may exist to be restored, replayed or transferred to
        # another object or process.
        raise TypeError(
            "TrustedAuthorizationContext cannot be serialized — "
            "an authorization context is process-local issuance "
            "state, not transferable data (issue a new context at "
            "the authorization boundary instead)")

    def __setstate__(self, state):
        # CF-WO-P0-010: state restoration is refused outright.
        # The P0-009 __setstate__ populated slots and froze the
        # object, which let `object.__new__` + `__setstate__`
        # manufacture a context that passed the old isinstance
        # check with zero factory calls. A restored object is
        # never trusted, and silently accepting state would hide
        # that; failing loudly is the safe behaviour.
        raise TypeError(
            "TrustedAuthorizationContext cannot be restored from "
            "serialized state — only "
            "issue_trusted_authorization_context() may create a "
            "trusted authorization context")

    def __reduce__(self):
        raise TypeError(
            "TrustedAuthorizationContext cannot be pickled — an "
            "authorization context is process-local issuance "
            "state, not transferable data (issue a new context at "
            "the authorization boundary instead)")

    def __reduce_ex__(self, protocol):
        raise TypeError(
            "TrustedAuthorizationContext cannot be pickled — an "
            "authorization context is process-local issuance "
            "state, not transferable data (issue a new context at "
            "the authorization boundary instead)")


# --- Revocation registry (CF-WO-P0-009 A) ---------------------------
# Revocation state is deliberately SEPARATE from the immutable
# authorization data: revoking a context must never mutate the
# issued context (not even its `revoked` field). The registry is
# a module-level set of authorization_ids, keyed by the
# immutable per-issuance id minted by the factory. It is
# process-local, in-memory state for the P0 policy layer — the
# P1 runtime (app UI / session) owns persistence of revocations
# across restarts; until then a restart clears the registry and
# contexts must be re-issued. Only the two functions below may
# touch the set; there is no public path that removes an id.
_REVOKED_AUTHORIZATION_IDS: set = set()


def is_factory_issued_trusted_authorization_context(context) -> bool:
    """True ONLY for the exact object issued by
    issue_trusted_authorization_context().

    This is the single issuance check every authorization
    boundary must use (CF-WO-P0-010). It is identity-based,
    not type- or field-based: `isinstance` alone is NOT proof
    (a directly constructed, `__new__`-built, copied or
    deserialized object is an instance of the class too), a
    matching field structure is NOT proof, a valid-looking
    owner/workspace is NOT proof, a matching private sentinel
    is NOT proof, and a frozen object is NOT proof. Only
    membership of this exact object in the process-local
    issuance registry counts. A forged object is never
    reported as issued, and a non-context is never reported
    as issued.
    """
    if not isinstance(context, TrustedAuthorizationContext):
        return False
    return context in _ISSUED_AUTHORIZATION_CONTEXTS


def revoke_trusted_authorization_context(trusted_context):
    """Revoke an issued context WITHOUT mutating it.

    Records the context's immutable authorization_id in the
    revocation registry; the context object itself is unchanged
    (every field, including `revoked`, keeps its issued value).
    Raises TypeError for anything that is not a factory-issued
    TrustedAuthorizationContext — a dict, a forged object, or
    a copy/deserialized object can never revoke (or un-revoke)
    anything. (CF-WO-P0-010: issuance is verified here so a
    forged object carrying a stolen authorization_id cannot
    revoke a genuine context.) Returns True.
    """
    if not is_factory_issued_trusted_authorization_context(
            trusted_context):
        raise TypeError(
            "only a TrustedAuthorizationContext issued by "
            "issue_trusted_authorization_context() can be revoked")
    _REVOKED_AUTHORIZATION_IDS.add(trusted_context.authorization_id)
    return True


def is_trusted_authorization_revoked(trusted_context) -> bool:
    """True when the context's authorization_id is in the
    revocation registry. Raises TypeError for anything that is
    not a factory-issued TrustedAuthorizationContext (fail
    closed — a forged object is never reported as 'not
    revoked')."""
    if not is_factory_issued_trusted_authorization_context(
            trusted_context):
        raise TypeError(
            "only a TrustedAuthorizationContext issued by "
            "issue_trusted_authorization_context() can be checked "
            "for revocation")
    return trusted_context.authorization_id in _REVOKED_AUTHORIZATION_IDS


def _is_authorization_revoked(trusted_context) -> bool:
    """Registry check used by validate_private_voice_export:
    False for anything without a registered id (including a
    non-context, which the caller rejects separately). Only
    ever called on a factory-issued context (the caller
    verifies issuance first); this helper itself confers no
    authority."""
    authorization_id = getattr(trusted_context, "authorization_id",
                               None)
    return authorization_id in _REVOKED_AUTHORIZATION_IDS


def issue_trusted_authorization_context(*, actor_owner_id,
                                        actor_workspace_id,
                                        granted_by, scope, action,
                                        character_id,
                                        voice_profile_id,
                                        provider_transmission_approved=False,
                                        expires_at=None):
    """Issue a trusted authorization context at the local application
    authorization boundary.

    CALLER MUST BE the trusted local application (P1: the app UI /
    session that just saw the owner approve this action). The
    arguments are the actor the boundary authenticated — NOT
    caller-supplied claims to be believed at face value. Raises
    ValueError on any missing/invalid field (fail closed at
    issuance); the returned context still authorizes nothing until
    validate_private_voice_export checks it against the asset.
    """
    for field, value in (
            ("actor_owner_id", actor_owner_id),
            ("actor_workspace_id", actor_workspace_id),
            ("granted_by", granted_by),
            ("character_id", character_id),
            ("voice_profile_id", voice_profile_id)):
        if not isinstance(value, str) or not value:
            raise ValueError(f"{field} must be a non-empty string")
        if not OWNERSHIP_ID_PATTERN.search(value):
            raise ValueError(f"{field} {value!r} is not a valid opaque "
                             "local identifier")
    if not isinstance(scope, str) or not scope.strip():
        raise ValueError("scope must be a non-empty string")
    if action not in ACTION_SCOPES:
        raise ValueError(f"action {action!r} must be one of "
                         f"{list(ACTION_SCOPES)}")
    if expires_at is not None and (
            not isinstance(expires_at, str) or len(expires_at) != 20
            or not expires_at.endswith("Z")):
        raise ValueError("expires_at must be an ISO-8601 UTC string "
                         "('YYYY-MM-DDTHH:MM:SSZ') or None")
    context = TrustedAuthorizationContext(
        _boundary=_AUTHORIZATION_BOUNDARY,
        actor_owner_id=actor_owner_id,
        actor_workspace_id=actor_workspace_id, granted_by=granted_by,
        scope=scope, action=action, character_id=character_id,
        voice_profile_id=voice_profile_id,
        provider_transmission_approved=bool(
            provider_transmission_approved),
        expires_at=expires_at,
        authorization_id=uuid.uuid4().hex)
    # CF-WO-P0-010: registration is the LAST step, after the
    # constructor has returned successfully and every field has
    # been validated. A failed construction therefore never
    # leaves a partially issued or trusted object in the
    # registry — only this exact object, built by this factory
    # call, is registered, and only it will ever be accepted by
    # the authorization consumers.
    _ISSUED_AUTHORIZATION_CONTEXTS.add(context)
    return context


def validate_private_voice_export(voice, authorization=None,
                                  trusted_context=None,
                                  to_provider=False) -> list[str]:
    """A private voice export is allowed only under a trusted,
    owner-bound authorization. Returns rejection reasons; [] = allowed.

    `trusted_context` must be the EXACT object issued by
    issue_trusted_authorization_context (the local application
    authorization boundary) — issuance is verified against the
    process-local registry by
    is_factory_issued_trusted_authorization_context, not by a
    bare isinstance check (CF-WO-P0-010): a directly constructed,
    `__new__`-built, copied or deserialized object is rejected
    even when its type and fields look genuine. The
    `authorization` dict — when given —
    is an UNTRUSTED request record only: its granted_by / scope /
    explicit_authorisation fields NEVER confer authority and are
    ignored for the decision. A dict claiming granted_by == the
    owner, or granted_by == anyone else, authorizes nothing on its
    own. The context is checked against the voice on every point:
    trusted actor is the voice owner in the voice workspace; the
    issuer (granted_by) is the voice owner; the action is an
    explicit "export_private_asset"; the scope is non-empty; the
    context covers exactly this character_id and voice_profile_id;
    the context is not expired or revoked. Export to an external
    provider (to_provider=True) additionally requires
    provider_transmission_approved on the context — a separate
    permission from export. Private sharing and exporting remain
    disabled by default: no context, no export.
    """
    errors = []
    if not isinstance(voice, dict):
        return ["voice profile is not an object"]
    ownership = voice.get("ownership")
    if validate_ownership(ownership):
        errors.append("voice profile has no valid ownership binding — "
                      "private export blocked")
    if trusted_context is None:
        errors.append("private voice export blocked: no trusted "
                      "authorization context — a caller-created "
                      "authorization dictionary (granted_by / scope / "
                      "explicit_authorisation) is an untrusted request, "
                      "never authority")
        return errors
    if not is_factory_issued_trusted_authorization_context(
            trusted_context):
        errors.append("private voice export blocked: authorization "
                      "context was not issued by "
                      "issue_trusted_authorization_context() — only "
                      "the exact context object issued by the local "
                      "application authorization boundary is "
                      "accepted; a directly constructed, copied, "
                      "deserialized or otherwise forged context "
                      "never authorizes an export (type, field "
                      "values and immutability alone prove "
                      "nothing)")
        return errors
    ctx = trusted_context
    # Revocation is registry state, not a mutated field: the
    # context itself is immutable, so a revoked context is
    # recognised by its authorization_id being in the revocation
    # registry (revoke_trusted_authorization_context). The
    # issuance-time `revoked` field is kept as a defence-in-depth
    # check alongside it.
    if ctx.revoked or _is_authorization_revoked(ctx):
        errors.append("private voice export blocked: the authorization "
                      "has been revoked")
    if ctx.expires_at is not None and ctx.expires_at <= _utc_now_iso():
        errors.append("private voice export blocked: the authorization "
                      f"expired at {ctx.expires_at}")
    if isinstance(ownership, dict):
        if ctx.actor_owner_id != ownership.get("owner_id"):
            errors.append("private voice export blocked: trusted actor "
                          f"{ctx.actor_owner_id!r} is not the voice "
                          f"owner {ownership.get('owner_id')!r}")
        if ctx.actor_workspace_id != ownership.get("workspace_id"):
            errors.append("private voice export blocked: trusted actor "
                          "workspace "
                          f"{ctx.actor_workspace_id!r} is not the "
                          "voice workspace "
                          f"{ownership.get('workspace_id')!r}")
        if ctx.granted_by != ownership.get("owner_id"):
            errors.append("private voice export blocked: authorization "
                          f"issuer (granted_by) {ctx.granted_by!r} is "
                          "not the voice owner "
                          f"{ownership.get('owner_id')!r} — a forged "
                          "granted_by is rejected")
    if ctx.action != "export_private_asset":
        errors.append("private voice export blocked: authorization "
                      f"action {ctx.action!r} is not an explicit "
                      "export action ('export_private_asset')")
    if not isinstance(ctx.scope, str) or not ctx.scope.strip():
        errors.append("private voice export blocked: export scope is "
                      "empty or missing")
    if ctx.character_id != voice.get("character_id"):
        errors.append("private voice export blocked: authorization is "
                      f"for character {ctx.character_id!r}, not "
                      f"{voice.get('character_id')!r} — an "
                      "authorization for one character never covers "
                      "another")
    if ctx.voice_profile_id != voice.get("voice_profile_id"):
        errors.append("private voice export blocked: authorization is "
                      f"for voice profile {ctx.voice_profile_id!r}, "
                      f"not {voice.get('voice_profile_id')!r} — an "
                      "authorization for one voice profile never "
                      "covers another")
    if to_provider and not ctx.provider_transmission_approved:
        errors.append("private voice export blocked: sending this voice "
                      "to an external provider requires provider-"
                      "transmission approval — a separate permission "
                      "from export, not granted by this authorization")
    return errors


def validate_release_manifest_paths(paths) -> list[str]:
    """A public release manifest must list no private media.

    Rejects any path under characters/ (except .gitkeep +
    README.md) or private-data/, and any media file. A folder
    being named "private" does not by itself make a path
    private — the rule is location + media type, and access is
    decided by ownership, not by a folder name.
    """
    errors = []
    for path in paths or []:
        if path in ("characters/.gitkeep", "characters/README.md"):
            continue
        if path.startswith("characters/") or \
                path.startswith("private-data/"):
            errors.append(f"private path must not be in a public "
                          f"release manifest: {path}")
        elif path.lower().endswith(
                (".mp3", ".mp4", ".wav", ".webm", ".mov", ".png",
                 ".jpg", ".jpeg")):
            errors.append(f"media file must not be in a public release "
                          f"manifest: {path}")
    return errors


def resolve_private_path(base_dir, rel_path):
    """Resolve a private-overlay pointer inside base_dir.

    Returns (resolved_path_or_None, errors). Rejects absolute
    paths, ".." segments and NUL bytes, and any path whose
    real (symlink-resolved) location escapes base_dir. The
    file need not exist; symlinks in existing components are
    still resolved.
    """
    if not isinstance(rel_path, str) or not rel_path:
        return None, ["private path must be a non-empty string"]
    if "\x00" in rel_path or rel_path.startswith("/") or \
            "\\" in rel_path:
        return None, [f"private path {rel_path!r} is not a safe "
                      "relative path"]
    parts = rel_path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return None, [f"private path {rel_path!r} contains an empty, "
                      "'.' or '..' segment (traversal rejected)"]
    base_real = os.path.realpath(base_dir)
    resolved = os.path.realpath(os.path.join(base_real, rel_path))
    if os.path.commonpath([base_real, resolved]) != base_real:
        return None, [f"private path {rel_path!r} escapes its base "
                      "directory (symlink/path escape rejected)"]
    return resolved, []


if __name__ == "__main__":
    for mode in MODES:
        print(mode, intake_result(mode))
