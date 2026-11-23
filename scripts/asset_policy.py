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
"""
from __future__ import annotations

import os
import re

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
    character (cross-character assignment rejected); (2) the
    character exists and the voice ownership matches the
    character ownership; (3) the requester (when given) is
    allowed access by the voice ownership (no cross-user /
    cross-workspace use by default); (4) the record passes the
    v2.5 conditional validation; (5) when require_approved,
    approval_status and status are both "approved" — a pending
    profile is a valid record but never an approved production
    voice, and sample-generation success is not user approval.
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
    character = None
    if character_registry is not None:
        character = character_registry.get(character_id)
        if character is None:
            return None, [f"unknown character_id {character_id!r}"]
        if not ownerships_match(vp.get("ownership"),
                                character.get("ownership")):
            return None, ["voice profile ownership does not match the "
                          "character ownership (owner/workspace must "
                          "match)"]
    errors.extend(validate_voice_profile(vp, character))
    if requesting_owner_id is not None or \
            requesting_workspace_id is not None:
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


def validate_private_voice_export(voice, authorization=None) -> list[str]:
    """A private voice export is blocked without explicit
    authorisation. `authorization` needs granted_by + scope +
    explicit_authorisation True (same shape as the skill-patch
    apply authorisation). Returns rejection reasons; [] = allowed.
    """
    errors = []
    if not isinstance(voice, dict):
        return ["voice profile is not an object"]
    if validate_ownership(voice.get("ownership")):
        errors.append("voice profile has no valid ownership binding — "
                      "private export blocked")
    auth_errors = []
    if not isinstance(authorization, dict):
        auth_errors.append("missing export authorisation")
    else:
        if not authorization.get("granted_by") or \
                not isinstance(authorization.get("granted_by"), str):
            auth_errors.append("missing granted_by")
        if not authorization.get("scope") or \
                not isinstance(authorization.get("scope"), str):
            auth_errors.append("missing scope")
        if authorization.get("explicit_authorisation") is not True:
            auth_errors.append("missing explicit authorisation to export")
    if auth_errors:
        errors.append("private voice export blocked without explicit "
                      f"authorisation ({'; '.join(auth_errors)})")
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
