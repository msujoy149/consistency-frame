#!/usr/bin/env python3
"""P0 asset-mode policy tests. Run via tests/run-tests.sh or directly:
  python3 tests/test_modes.py
Exit 0 = PASS, 1 = FAIL.
Test IDs: CF-P0-ASSET-001, CF-P0-ASSET-002, CF-P0-ASSET-003,
CF-P0-LEARN-001 (propose/apply split for skill learning).
"""
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import asset_policy  # noqa: E402

failures = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def main():
    # CF-P0-ASSET-001: temporary modes create no permanent record.
    for mode in ("UPLOAD_ONLY", "TEMPORARY_ASSET_USE"):
        check(f"CF-P0-ASSET-001: {mode} creates no permanent record",
              not asset_policy.may_create_permanent_record(mode))
        check(f"CF-P0-ASSET-001: {mode} intake retention is temporary",
              asset_policy.intake_result(mode)["retention"] == "temporary")

    # PROJECT_CONSISTENCY loads existing records; it creates nothing new
    # by itself — creation needs a REGISTER_* mode.
    check("PROJECT_CONSISTENCY creates no permanent record by itself",
          not asset_policy.may_create_permanent_record("PROJECT_CONSISTENCY"))

    # CF-P0-ASSET-002: character registration gates.
    complete = {"explicit_authorisation": True, "name": "Nila",
                "id": "char-nila-001", "references": ["reference-front.jpg"]}
    check("CF-P0-ASSET-002: complete registration is allowed",
          asset_policy.validate_character_registration(complete) == [])
    for missing, field in (
            ({"explicit_authorisation": False, "name": "Nila", "id": "char-nila-001",
              "references": ["reference-front.jpg"]}, "authorisation"),
            ({"explicit_authorisation": True, "name": "", "id": "char-nila-001",
              "references": ["reference-front.jpg"]}, "name"),
            ({"explicit_authorisation": True, "name": "Nila", "id": "",
              "references": ["reference-front.jpg"]}, "id"),
            ({"explicit_authorisation": True, "name": "Nila", "id": "char-nila-001",
              "references": []}, "reference"),
            ({"explicit_authorisation": True, "name": "Nila", "id": "char-nila-001"},
             "reference")):
        check(f"CF-P0-ASSET-002: registration without {field} is rejected",
              bool(asset_policy.validate_character_registration(missing)))

    # Uploading a file alone never registers it.
    check("upload alone (no authorisation) never registers",
          bool(asset_policy.validate_character_registration(
              {"name": "Nila", "id": "char-nila-001",
               "references": ["reference-front.jpg"]})))

    # CF-P0-ASSET-003: voice and sound are separate types.
    check("CF-P0-ASSET-003: voice profile without consent is rejected",
          bool(asset_policy.validate_voice_registration(
              {"explicit_authorisation": True, "character_id": "char-nila-001",
               "reference_audio": "voice-reference.mp3",
               "consent": {"granted": False, "source": "user"}})))
    check("CF-P0-ASSET-003: sound asset without licence is rejected",
          bool(asset_policy.validate_sound_registration(
              {"explicit_instruction": True, "kind": "theme_music"})))
    check("CF-P0-ASSET-003: character record cannot embed voice/sound fields",
          bool(asset_policy.check_character_record_separation(
              {"id": "char-nila-001", "voice_tags": "child, female, high pitch"})))

    # Reference review never mutates; learning needs explicit instruction.
    check("REFERENCE_REVIEW never mutates canonical skills",
          not asset_policy.may_mutate_canonical_skills("REFERENCE_REVIEW", True))
    check("REFERENCE_LEARN_AND_UPDATE without explicit instruction cannot mutate",
          not asset_policy.may_mutate_canonical_skills("REFERENCE_LEARN_AND_UPDATE", False))

    # CF-P0-LEARN-001: propose vs apply are separate permissions.
    full_auth = {"granted_by": "user", "scope": "kids-family-animation",
                 "branch": "feat/cf-p0-safe-foundations",
                 "explicit_authorisation": True}
    check("CF-P0-LEARN-001: propose allowed with explicit instruction",
          asset_policy.may_propose_skill_patch("REFERENCE_LEARN_AND_UPDATE", True))
    check("CF-P0-LEARN-001: propose rejected without explicit instruction",
          not asset_policy.may_propose_skill_patch("REFERENCE_LEARN_AND_UPDATE", False))
    check("CF-P0-LEARN-001: propose rejected in other modes",
          not asset_policy.may_propose_skill_patch("REFERENCE_REVIEW", True))
    check("CF-P0-LEARN-001: apply rejected without authorisation",
          not asset_policy.may_apply_skill_patch(None))
    check("CF-P0-LEARN-001: apply rejected with partial authorisation",
          not asset_policy.may_apply_skill_patch(
              {"granted_by": "user", "scope": "kids-family-animation"}))
    check("CF-P0-LEARN-001: apply rejected when explicit_authorisation is False",
          not asset_policy.may_apply_skill_patch(
              {**full_auth, "explicit_authorisation": False}))
    check("CF-P0-LEARN-001: apply allowed only with full authorisation",
          asset_policy.may_apply_skill_patch(full_auth))
    check("CF-P0-LEARN-001: validate_skill_patch_application lists "
          "every missing field",
          asset_policy.validate_skill_patch_application({}) == [
              "missing granted_by", "missing scope", "missing branch",
              "missing explicit authorisation to apply the patch"])
    # The legacy combined gate needs BOTH halves.
    check("CF-P0-LEARN-001: propose alone does not mutate canonical skills",
          not asset_policy.may_mutate_canonical_skills(
              "REFERENCE_LEARN_AND_UPDATE", True))
    check("CF-P0-LEARN-001: propose + full authorisation may mutate",
          asset_policy.may_mutate_canonical_skills(
              "REFERENCE_LEARN_AND_UPDATE", True, full_auth))
    check("CF-P0-LEARN-001: propose + partial authorisation cannot mutate",
          not asset_policy.may_mutate_canonical_skills(
              "REFERENCE_LEARN_AND_UPDATE", True,
              {"granted_by": "user", "scope": "kids-family-animation"}))
    # Intake never reports apply True, with or without instruction.
    check("CF-P0-LEARN-001: intake never reports apply True",
          not asset_policy.intake_result("REFERENCE_LEARN_AND_UPDATE", True)[
              "may_apply_skill_patch"])
    check("CF-P0-LEARN-001: intake reports propose True with instruction",
          asset_policy.intake_result("REFERENCE_LEARN_AND_UPDATE", True)[
              "may_propose_skill_patch"])
    check("CF-P0-LEARN-001: intake reports propose False without instruction",
          not asset_policy.intake_result("REFERENCE_LEARN_AND_UPDATE")[
              "may_propose_skill_patch"])

    # Unknown mode is an error, never silently allowed.
    try:
        asset_policy.may_create_permanent_record("DO_ANYTHING")
        check("unknown mode raises", False)
    except ValueError:
        check("unknown mode raises", True)

    print(f"test_modes: {'PASS' if not failures else 'FAIL'} "
          f"({len(failures)} failure(s))")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
