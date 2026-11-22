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
"""
from __future__ import annotations

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


if __name__ == "__main__":
    for mode in MODES:
        print(mode, intake_result(mode))
