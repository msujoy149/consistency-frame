#!/usr/bin/env python3
"""P0 asset-mode policy tests. Run via tests/run-tests.sh or directly:
  python3 tests/test_modes.py
Exit 0 = PASS, 1 = FAIL.
Test IDs: CF-P0-ASSET-001, CF-P0-ASSET-002, CF-P0-ASSET-003.
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
    check("REFERENCE_LEARN_AND_UPDATE with explicit instruction may propose (patch only)",
          asset_policy.may_mutate_canonical_skills("REFERENCE_LEARN_AND_UPDATE", True))

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
