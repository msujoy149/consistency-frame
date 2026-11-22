#!/usr/bin/env python3
"""P0 schema tests. Run via tests/run-tests.sh or directly:
  python3 tests/test_schemas.py
Exit 0 = PASS, 1 = FAIL. Test IDs: P0-SCHEMA, CF-P0-ASSET-003 (part).
"""
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "validate_repo", os.path.join(ROOT, "scripts", "validate-repo.py"))
_validate_repo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_validate_repo)
validate_instance = _validate_repo.validate_instance
import asset_policy  # noqa: E402

failures = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def load_schema(name):
    with open(os.path.join(ROOT, "schemas", name), encoding="utf-8") as f:
        return json.load(f)


def load_fixture(name):
    with open(os.path.join(ROOT, "tests", "fixtures", name), encoding="utf-8") as f:
        return json.load(f)


def errors_for(schema, value):
    errs = []
    validate_instance(schema, value, "$", errs)
    return errs


def main():
    # Valid fixtures pass.
    for fixture, schema_name in (
            ("character-valid.json", "character.json"),
            ("voice-profile-valid.json", "voice-profile.json"),
            ("sound-asset-valid.json", "sound-asset.json"),
            ("intake-temporary.json", "intake-job.json")):
        errs = errors_for(load_schema(schema_name), load_fixture(fixture))
        check(f"valid fixture {fixture} validates", not errs, "; ".join(errs))

    # Character missing required name fails.
    bad = load_fixture("character-valid.json")
    del bad["name"]
    check("character without name is rejected",
          bool(errors_for(load_schema("character.json"), bad)))

    # Character with an embedded voice field is rejected (separation).
    bad = load_fixture("character-valid.json")
    bad["voice_tags"] = "child, female, high pitch"
    errs = errors_for(load_schema("character.json"), bad)
    check("character with embedded voice_tags is rejected (additionalProperties)",
          bool(errs))
    check("CF-P0-ASSET-003: separation policy flags embedded voice data",
          bool(asset_policy.check_character_record_separation(bad)))

    # Voice profile without consent is rejected by policy.
    bad_voice = load_fixture("voice-profile-valid.json")
    bad_voice["consent"] = {"granted": False, "source": "user"}
    check("CF-P0-ASSET-002/003: voice profile without consent is rejected",
          bool(asset_policy.validate_voice_registration(bad_voice)))

    # Sound asset without licence is rejected by policy.
    bad_sound = load_fixture("sound-asset-valid.json")
    del bad_sound["licence"]
    check("sound asset without licence is rejected",
          bool(asset_policy.validate_sound_registration(bad_sound)))

    # Wrong enum value is rejected.
    bad = load_fixture("sound-asset-valid.json")
    bad["kind"] = "voice_profile"
    check("sound_asset kind=voice_profile is rejected (voice != sound)",
          bool(errors_for(load_schema("sound-asset.json"), bad)))

    # REFERENCE_REVIEW must never mutate skills.
    errs = errors_for(load_schema("reference-review.json"),
                      {"schema_version": "2.3", "id": "rev-001",
                       "reference_id": "ref-001", "mutates_canonical_skills": True})
    check("reference-review with mutates_canonical_skills=true is rejected",
          bool(errs))

    # Intake: TEMPORARY_ASSET_USE with permanent records is a policy violation.
    job = load_fixture("intake-temporary.json")
    check("CF-P0-ASSET-001: temporary intake has no permanent records",
          job["mode"] == "TEMPORARY_ASSET_USE"
          and job["retention"] == "temporary"
          and job["permanent_records_created"] == []
          and not asset_policy.may_create_permanent_record(job["mode"]))

    # Path traversal in a private pointer is rejected.
    bad = load_fixture("character-valid.json")
    bad["reference_assets"] = [{"path": "../outside/secret.jpg"}]
    check("private pointer with '..' is rejected",
          bool(errors_for(load_schema("character.json"), bad)))

    print(f"test_schemas: {'PASS' if not failures else 'FAIL'} "
          f"({len(failures)} failure(s))")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
