#!/usr/bin/env python3
"""P0 schema tests. Run via tests/run-tests.sh or directly:
  python3 tests/test_schemas.py
Exit 0 = PASS, 1 = FAIL. Test IDs: P0-SCHEMA, CF-P0-ASSET-003 (part),
CF-P0-LEARN-001 (reference-review propose/apply, part).
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


def reference_review_errors(review):
    """Schema validation + the conditional apply rule for a review.

    The restricted subset cannot express conditional-required, so the
    rule is enforced semantically here: apply_skill_patch=true needs
    a full authorization object (granted_by, scope, branch).
    """
    errs = errors_for(load_schema("reference-review.json"), review)
    if review.get("apply_skill_patch") is True:
        auth = review.get("authorization")
        if not isinstance(auth, dict):
            errs.append("apply_skill_patch=true requires an authorization object")
        else:
            for field in ("granted_by", "scope", "branch"):
                if not auth.get(field):
                    errs.append(f"authorization is missing '{field}'")
    return errs


def base_review():
    return {"schema_version": "2.3", "id": "rev-001",
            "reference_id": "ref-001", "mutates_canonical_skills": False}


# --- CF-WO-P0-006 (v2.5, animation-first, style-agnostic) -------------------
# The restricted JSON-Schema subset cannot express cross-field rules
# (articulation must match the subject; a generated digital human is
# never live-action footage; character IDs must be unique across the
# registry), so — like the dialogue-rewrite and non-verbal-line rules
# above — they are enforced semantically here.

ARTICULATION_BY_SUBJECT_KIND = {
    "human": {"human-mouth-lips"},
    "digital-human": {"human-mouth-lips"},
    "real-animal": {"bird-beak", "animal-muzzle", "other"},
    "cgi-animal": {"bird-beak", "animal-muzzle", "other"},
    "fictional-creature": {"creature-jaw-mandibles", "bird-beak",
                           "animal-muzzle", "other"},
    "anthropomorphic": {"human-mouth-lips", "bird-beak", "animal-muzzle",
                        "creature-jaw-mandibles", "other"},
    "mixed": {"human-mouth-lips", "bird-beak", "animal-muzzle",
              "creature-jaw-mandibles", "other"},
    "non-character": {"human-mouth-lips", "bird-beak", "animal-muzzle",
                      "creature-jaw-mandibles", "other"},
}
BIRD_WORDS = ("bird", "parrot", "crow", "owl", "eagle", "sparrow",
              "pigeon", "duck", "chicken", "songbird")
GENERATED_MEDIA = {"ai-digital-human", "ai-digital-creature",
                   "3d-cgi-rigged", "2d-drawn-vector"}
GENERATED_STYLES = {"photorealistic-digital-human",
                    "photorealistic-digital-animal-creature",
                    "photorealistic-3d-cgi", "stylized-3d",
                    "semi-realistic-3d", "flat-2d-vector", "hand-drawn-2d",
                    "illustrated-2d", "anime", "cartoon-2d"}


def articulation_errors(entries):
    """Each entry needs subject_kind/species/articulation_target.

    Human lip movement applies ONLY to human/digital-human subjects.
    A bird (by species or subject kind) never uses human-mouth-lips;
    animals use animal-muzzle (or bird-beak), creatures use
    creature-jaw-mandibles. Returns a list of violations.
    """
    errors = []
    for i, entry in enumerate(entries or []):
        if not isinstance(entry, dict):
            continue
        target = entry.get("articulation_target") or entry.get("articulation")
        if not target:
            continue
        kind = entry.get("subject_kind")
        species = (entry.get("species") or "").lower()
        label = entry.get("character_id") or entry.get("dialogue_line_id") or f"entry {i}"
        if kind in ARTICULATION_BY_SUBJECT_KIND and \
                target not in ARTICULATION_BY_SUBJECT_KIND[kind]:
            errors.append(f"{label}: articulation '{target}' is not valid "
                          f"for subject_kind '{kind}'")
        if target == "human-mouth-lips" and \
                any(w in species for w in BIRD_WORDS):
            errors.append(f"{label}: bird species '{entry.get('species')}' "
                          "must never use human-mouth-lips articulation")
    return errors


def live_action_errors(profile):
    """is_live_action_footage must agree with the production medium/style.

    A generated subject (AI digital human/creature, CGI, drawn) with
    is_live_action_footage=true is invalid — a generated digital human
    is NEVER live-action footage. Conversely a live-action-footage
    production with the flag false is invalid. Checks the profile level
    and every per-subject override. Returns a list of violations.
    """
    errors = []
    if not isinstance(profile, dict):
        return ["production profile is not an object"]
    flag = profile.get("is_live_action_footage")
    medium = profile.get("production_medium")
    style = profile.get("visual_style")
    pid = profile.get("production_profile_id", "?")
    if flag is True and (medium in GENERATED_MEDIA or style in GENERATED_STYLES):
        errors.append(f"{pid}: is_live_action_footage=true but "
                      f"production_medium='{medium}' / visual_style='{style}' "
                      "is generated, not live-action footage")
    if flag is False and medium == "live-action-footage":
        errors.append(f"{pid}: is_live_action_footage=false but "
                      "production_medium='live-action-footage'")
    for i, sub in enumerate(profile.get("per_subject_overrides") or []):
        if not isinstance(sub, dict):
            continue
        if sub.get("is_live_action_footage") is True and \
                sub.get("representation") in GENERATED_MEDIA:
            errors.append(f"{pid} per_subject_overrides[{i}] "
                          f"({sub.get('character_id', '?')}): "
                          "is_live_action_footage=true but representation "
                          f"'{sub.get('representation')}' is generated")
    return errors


def subject_live_action_errors(subjects):
    """Per-subject is_live_action_footage check for scene/shot subjects."""
    errors = []
    for i, sub in enumerate(subjects or []):
        if not isinstance(sub, dict):
            continue
        if sub.get("is_live_action_footage") is True and \
                sub.get("representation") in GENERATED_MEDIA:
            errors.append(f"subjects[{i}] ({sub.get('character_id', '?')}): "
                          "is_live_action_footage=true but representation "
                          f"'{sub.get('representation')}' is generated")
    return errors


def duplicate_character_id_errors(records):
    """character_id must be unique across registration records.

    A second registration reusing an existing character_id is rejected;
    IDs are never silently merged. `records` is a list of registration
    objects. Returns a list of violations.
    """
    errors = []
    seen = {}
    for i, rec in enumerate(records or []):
        if not isinstance(rec, dict):
            continue
        cid = rec.get("character_id")
        if not cid:
            continue
        if cid in seen:
            errors.append(f"duplicate character_id '{cid}' in records[{i}] "
                          f"(first seen in records[{seen[cid]}])")
        else:
            seen[cid] = i
    return errors


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

    # CF-P0-LEARN-001: a review may only propose (proposal_only, default true).
    check("CF-P0-LEARN-001: reference-review without proposal_only is valid "
          "(default true: proposal only)",
          not reference_review_errors(base_review()))
    review = base_review()
    review["proposal_only"] = True
    check("CF-P0-LEARN-001: reference-review with proposal_only=true is valid",
          not reference_review_errors(review))
    review = base_review()
    review["apply_skill_patch"] = True
    check("CF-P0-LEARN-001: apply_skill_patch=true without authorization "
          "is rejected",
          bool(reference_review_errors(review)))
    review = base_review()
    review["apply_skill_patch"] = True
    review["authorization"] = {"granted_by": "user",
                               "scope": "kids-family-animation"}
    check("CF-P0-LEARN-001: apply_skill_patch=true with partial "
          "authorization is rejected",
          bool(reference_review_errors(review)))
    review = base_review()
    review["apply_skill_patch"] = True
    review["authorization"] = {"granted_by": "user",
                               "scope": "kids-family-animation",
                               "branch": "feat/cf-p0-safe-foundations"}
    check("CF-P0-LEARN-001: apply_skill_patch=true with full authorization "
          "is valid",
          not reference_review_errors(review))
    review = base_review()
    review["apply_skill_patch"] = False
    check("CF-P0-LEARN-001: apply_skill_patch=false without authorization "
          "is valid",
          not reference_review_errors(review))

    # Intake: TEMPORARY_ASSET_USE with permanent records is a policy violation.
    job = load_fixture("intake-temporary.json")
    check("CF-P0-ASSET-001: temporary intake has no permanent records",
          job["mode"] == "TEMPORARY_ASSET_USE"
          and job["retention"] == "temporary"
          and job["permanent_records_created"] == []
          and not asset_policy.may_create_permanent_record(job["mode"]))

    # ---- CF-WO-P0-006 (v2.5, animation-first, style-agnostic) ----------
    # Valid v2.5 fixtures pass schema validation. The bird
    # registration fixture (character-registration-valid-bird.json,
    # char-kiki-001) is owned by another CF-WO-P0-007 worker and its
    # structured ownership object is pending from them; its check is
    # SKIPped until the object lands (never a pass against nothing)
    # and un-skips automatically.
    _bird_reg = load_fixture("character-registration-valid-bird.json")
    _bird_ownership_pending = "ownership" not in _bird_reg
    _v25_fixtures = [
            ("production-profile-valid-digital-human.json",
             "production-profile.json"),
            ("routing-profile-s6-real-animal.json",
             "production-profile.json"),
            ("scene-plan-valid-human-bird.json", "scene-plan.json"),
            ("shot-plan-valid-human-bird.json", "shot-plan.json"),
            ("performance-plan-valid-bird.json", "performance-plan.json"),
            ("script-to-performance-valid-bindings.json",
             "script-to-performance.json"),
            ("character-registration-valid-human.json",
             "character-registration.json"),
            ("voice-profile-valid-user-recorded.json", "voice-profile.json"),
            ("voice-profile-valid-ai-generated.json", "voice-profile.json"),
            ("character-valid-v25-animal.json", "character.json"),
            ("visual-style-profile-valid.json", "visual-style-profile.json")]
    if not _bird_ownership_pending:
        _v25_fixtures.append(("character-registration-valid-bird.json",
                              "character-registration.json"))
    for fixture, schema_name in _v25_fixtures:
        errs = errors_for(load_schema(schema_name), load_fixture(fixture))
        check(f"CF-P0-006: valid fixture {fixture} validates",
              not errs, "; ".join(errs))
    if _bird_ownership_pending:
        print("SKIP CF-P0-006: valid fixture "
              "character-registration-valid-bird.json validates — bird "
              "fixture ownership pending from its owning worker")

    # Migration (F5): existing v2.3/v2.4 records stay valid under v2.5.
    for fixture, schema_name in (
            ("character-valid.json", "character.json"),
            ("voice-profile-valid.json", "voice-profile.json"),
            ("scene-plan-valid.json", "scene-plan.json"),
            ("shot-plan-valid.json", "shot-plan.json"),
            ("performance-plan-valid.json", "performance-plan.json"),
            ("script-to-performance-valid.json",
             "script-to-performance.json")):
        errs = errors_for(load_schema(schema_name), load_fixture(fixture))
        check(f"CF-P0-006/F5: v2.3/v2.4 fixture {fixture} still validates",
              not errs, "; ".join(errs))
    check("CF-P0-006/F5: character schema accepts 2.3 and 2.5",
          load_schema("character.json")["properties"]["schema_version"]["enum"]
          == ["2.3", "2.5"])
    check("CF-P0-006/F5: scene-plan schema accepts 2.4 and 2.5",
          load_schema("scene-plan.json")["properties"]["schema_version"]["enum"]
          == ["2.4", "2.5"])

    # No single animation_type enum: a record carrying it is rejected.
    bad = load_fixture("production-profile-valid-digital-human.json")
    bad["animation_type"] = "photorealistic"
    check("CF-P0-006: production profile with animation_type is rejected "
          "(no single animation_type enum; dimensions are separate)",
          bool(errors_for(load_schema("production-profile.json"), bad)))
    errs = errors_for(load_schema("production-profile.json"),
                      load_fixture("production-profile-invalid-animation-type.json"))
    check("CF-P0-006: invalid animation_type fixture is rejected",
          bool(errs))

    # Fixed vocabularies: unknown enum values are rejected.
    bad = load_fixture("production-profile-valid-digital-human.json")
    bad["visual_style"] = "pixar-style"
    check("CF-P0-006: unknown visual_style is rejected",
          bool(errors_for(load_schema("production-profile.json"), bad)))
    bad = load_fixture("production-profile-valid-digital-human.json")
    bad["production_medium"] = "stop-motion"
    check("CF-P0-006: unknown production_medium is rejected",
          bool(errors_for(load_schema("production-profile.json"), bad)))

    # Articulation is subject-specific: a bird never uses human lips.
    bird_plan = load_fixture("performance-plan-invalid-bird-human-lips.json")
    check("CF-P0-006: bird line with human-mouth-lips is rejected",
          bool(articulation_errors(bird_plan["lines"])))
    good_bird = load_fixture("performance-plan-valid-bird.json")
    check("CF-P0-006: bird line with bird-beak articulation is valid",
          articulation_errors(good_bird["lines"]) == []
          and not errors_for(load_schema("performance-plan.json"), good_bird))
    check("CF-P0-006: valid bird line passes the non-verbal-line rule",
          _validate_repo.validate_non_verbal_lines(good_bird) == [])
    scene_bird = load_fixture("scene-plan-valid-human-bird.json")
    check("CF-P0-006: human+bird scene subjects pass articulation check",
          articulation_errors(scene_bird["scenes"][0]["subjects"]) == [])
    shot_bird = load_fixture("shot-plan-valid-human-bird.json")
    check("CF-P0-006: human+bird shot subjects pass articulation check",
          articulation_errors(shot_bird["shots"][0]["subjects"]) == [])
    check("CF-P0-006: human+bird scene subjects pass live-action check",
          subject_live_action_errors(scene_bird["scenes"][0]["subjects"]) == [])
    check("CF-P0-006: human+bird shot subjects pass live-action check",
          subject_live_action_errors(shot_bird["shots"][0]["subjects"]) == [])

    # A generated digital human is NEVER live-action footage.
    good_profile = load_fixture("production-profile-valid-digital-human.json")
    check("CF-P0-006: valid digital-human profile passes live-action check",
          live_action_errors(good_profile) == [])
    bad_profile = load_fixture(
        "production-profile-invalid-digital-human-live-action.json")
    check("CF-P0-006: digital-human profile claiming live-action footage "
          "is schema-valid (boolean) but rejected by the provenance check",
          not errors_for(load_schema("production-profile.json"), bad_profile)
          and bool(live_action_errors(bad_profile)))

    # Character registration: name + unique ID required; no duplicates.
    reg_schema = load_schema("character-registration.json")
    check("CF-P0-006: registration without character_id is rejected",
          bool(errors_for(reg_schema, load_fixture(
              "character-registration-invalid-missing-id.json"))))
    dupes = load_fixture("character-registration-invalid-duplicate-id.json")
    check("CF-P0-006: duplicate character_id across registrations "
          "is rejected",
          bool(duplicate_character_id_errors(dupes)))
    check("CF-P0-006: each duplicate-ID record is valid on its own "
          "(the rejection is the duplication, not the shape; the "
          "pre-ownership records are validated with the ownership "
          "object added, since the schema now requires it)",
          all(not errors_for(reg_schema, {**rec, "ownership": {
              "owner_id": "owner-a", "workspace_id": "workspace-a",
              "visibility": "private", "sharing": "none"}})
              for rec in dupes))
    check("CF-P0-006: distinct registrations pass the duplicate-ID check",
          duplicate_character_id_errors([
              load_fixture("character-registration-valid-human.json"),
              load_fixture("character-registration-valid-bird.json")]) == [])
    reg_bird = load_fixture("character-registration-valid-bird.json")
    check("CF-P0-006: bird registration is temporary, never silently "
          "permanent",
          reg_bird["registration_history"][0]["event"]
          == "registered-temporary")

    # Voice profiles: user-recorded vs AI-generated (Addendum C §5).
    vp_schema = load_schema("voice-profile.json")
    user_vp = load_fixture("voice-profile-valid-user-recorded.json")
    check("CF-P0-006: user-recorded voice profile is valid",
          user_vp["source"] == "user-recording"
          and not errors_for(vp_schema, user_vp))
    ai_vp = load_fixture("voice-profile-valid-ai-generated.json")
    check("CF-P0-006: AI-generated voice profile is valid",
          ai_vp["source"] == "ai-generated"
          and not errors_for(vp_schema, ai_vp))
    bad = load_fixture("voice-profile-valid-user-recorded.json")
    bad["source"] = "cloned-without-consent"
    check("CF-P0-006: unknown voice source is rejected",
          bool(errors_for(vp_schema, bad)))

    # ---- CF-WO-P0-007 (B + C): structured ownership + conditional
    # v2.5 voice-profile validation --------------------------------
    # The repo's JSON-Schema validator subset has no if/then, allOf
    # or dependentRequired, so v2.5 conditional-required fields
    # cannot live in the schema: the schema stays permissive for
    # them and asset_policy.validate_voice_profile enforces them.
    # Every case below pins BOTH layers' verdicts, so the layers
    # never disagree silently. The full negative matrix lives in
    # tests/test_character_registration.py; this section pins the
    # schema shapes and the key agreement cases.
    check("CF-P0-007/B: character-registration requires structured "
          "ownership",
          "ownership" in reg_schema.get("required", []))
    check("CF-P0-007/B: character-registration ownership shape is "
          "exactly owner_id + workspace_id + visibility + sharing",
          set(reg_schema["properties"]["ownership"]["properties"])
          == {"owner_id", "workspace_id", "visibility", "sharing"}
          and set(reg_schema["properties"]["ownership"]["required"])
          == {"owner_id", "workspace_id", "visibility", "sharing"}
          and reg_schema["properties"]["ownership"]
          ["additionalProperties"] is False
          and reg_schema["properties"]["ownership"]["properties"]
          ["visibility"]["enum"] == ["private", "shared"]
          and reg_schema["properties"]["ownership"]["properties"]
          ["sharing"]["enum"] == ["none", "workspace", "explicit"])
    check("CF-P0-007/B: ownership_scope is optional legacy "
          "(deprecated, superseded by ownership)",
          "ownership_scope" in reg_schema["properties"]
          and "ownership_scope" not in reg_schema.get("required", []))
    check("CF-P0-007/B: voice-profile carries the same ownership "
          "shape",
          set(vp_schema["properties"]["ownership"]["properties"])
          == {"owner_id", "workspace_id", "visibility", "sharing"}
          and set(vp_schema["properties"]["ownership"]["required"])
          == {"owner_id", "workspace_id", "visibility", "sharing"})
    check("CF-P0-007/B: voice-profile does NOT add v2.5 fields to "
          "the global required array (v2.3 must keep passing)",
          "ownership" not in vp_schema.get("required", [])
          and "voice_profile_id" not in vp_schema.get("required", []))
    check("CF-P0-007/C: voice-profile records the human-donor "
          "condition + provider transmission disclosure",
          "human_voice_donor" in vp_schema["properties"]
          and "provider_transmission" in vp_schema["properties"])
    reg_no_owner = load_fixture("character-registration-valid.json")
    del reg_no_owner["ownership"]
    check("CF-P0-007/B: registration without structured ownership "
          "is rejected by the schema",
          bool(errors_for(reg_schema, reg_no_owner)))
    reg_no_scope = load_fixture("character-registration-valid.json")
    del reg_no_scope["ownership_scope"]
    check("CF-P0-007/B: registration without the legacy "
          "ownership_scope still validates (legacy is optional)",
          not errors_for(reg_schema, reg_no_scope))

    def voice_agreement(name, record, expect_schema_pass,
                        expect_python_pass, character=None):
        schema_errs = errors_for(vp_schema, record)
        python_errs = asset_policy.validate_voice_profile(
            record, character)
        check(f"CF-P0-007/C: {name} — schema verdict as expected",
              (not schema_errs) == expect_schema_pass,
              "; ".join(schema_errs))
        check(f"CF-P0-007/C: {name} — python v2.5 verdict as expected",
              (not python_errs) == expect_python_pass,
              "; ".join(python_errs))

    _nila = load_fixture("character-registration-valid-human.json")
    voice_agreement("valid v2.5 user-recorded agrees (both pass)",
                    load_fixture("voice-profile-valid-user-recorded.json"),
                    True, True, character=_nila)
    voice_agreement("valid v2.5 AI-generated agrees (both pass)",
                    load_fixture("voice-profile-valid-ai-generated.json"),
                    True, True)
    voice_agreement("valid v2.3 legacy voice profile still passes",
                    load_fixture("voice-profile-valid.json"), True, True)
    _no_owner = load_fixture("voice-profile-valid-user-recorded.json")
    del _no_owner["ownership"]
    voice_agreement("v2.5 voice without ownership: schema permissive, "
                    "python rejects (documented subset gap)",
                    _no_owner, True, False)
    _no_audio = load_fixture("voice-profile-valid-user-recorded.json")
    _no_audio["audio_reference_assets"] = []
    voice_agreement("user recording without audio reference",
                    _no_audio, True, False)
    _no_provider = load_fixture("voice-profile-valid-ai-generated.json")
    del _no_provider["provider"]
    voice_agreement("AI-generated voice without provider",
                    _no_provider, True, False)
    _pending = load_fixture("voice-profile-valid-ai-generated.json")
    _pending["approval_status"] = "pending"
    _pending["status"] = "draft"
    voice_agreement("pending AI-generated voice is a valid record",
                    _pending, True, True)
    _donor = load_fixture("voice-profile-valid-ai-generated.json")
    _donor["human_voice_donor"] = True
    _donor["consent_status"] = "not-required"
    voice_agreement("real-person donor claimed 'not-required'",
                    _donor, True, False)
    _bad_owner = load_fixture("voice-profile-valid-user-recorded.json")
    _bad_owner["ownership"] = {"owner_id": "owner-a",
                               "workspace_id": "workspace-a",
                               "visibility": "public",
                               "sharing": "none"}
    voice_agreement("ownership visibility outside the enum (both "
                    "layers reject)", _bad_owner, False, False)

    # Script-to-performance: one shared audio-visual timeline.
    s2p = load_fixture("script-to-performance-valid-bindings.json")
    bindings = s2p["character_voice_bindings"]
    check("CF-P0-006: character_voice_bindings cover the bird line and "
          "the human line with stable dialogue_line_ids",
          {b["dialogue_line_id"] for b in bindings}
          == {"l-bird-01", "l-bird-02"}
          and articulation_errors(
              [{"subject_kind": "cgi-animal", "species": "African grey parrot",
                "articulation_target": b["articulation"],
                "character_id": b["character_id"]}
               for b in bindings if b["character_id"] == "char-kiki-001"]) == [])
    check("CF-P0-006: singular character_voice_binding object is valid",
          not errors_for(
              load_schema("script-to-performance.json"),
              {**{k: v for k, v in s2p.items()
                  if k != "character_voice_bindings"},
               "character_voice_binding": bindings[0]}))

    # Shot plan: legacy camera_movement 'dolly' stays valid (migration),
    # and the new v2.5 values (push-in, dolly-in) are accepted.
    good_shot = load_fixture("shot-plan-valid.json")
    check("CF-P0-006/F5: legacy camera_movement 'dolly' still validates",
          not errors_for(load_schema("shot-plan.json"), good_shot))
    good_shot["shots"][0]["camera_movement"] = "push-in"
    check("CF-P0-006: camera_movement 'push-in' is accepted",
          not errors_for(load_schema("shot-plan.json"), good_shot))
    good_shot["shots"][0]["camera_movement"] = "whip-pan"
    check("CF-P0-006: unknown camera_movement is rejected",
          bool(errors_for(load_schema("shot-plan.json"), good_shot)))

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
