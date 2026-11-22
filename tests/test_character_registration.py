#!/usr/bin/env python3
"""P0-006 acceptance tests — character registration (Addendum C §14).

Run directly: python3 tests/test_character_registration.py
Exit 0 = PASS, 1 = FAIL.
Acceptance cases covered: AC-01..AC-12, plus QC-01 (character-identity
QC, Addendum C §12).

Method: the acceptance logic is tested by small in-test contract
validators built on the FIXED SCHEMA CONTRACTS (CF-WO-P0-006) and on
the repo's own validator (scripts/validate-repo.py validate_instance)
wherever a schema exists. The SCHEMA DEPENDENCY GATES in main() check
that the real P0-006 schemas (v2.5, Agent C) exist and carry exactly
the contract fields and vocabularies; fixture-vs-schema validation
runs only when the gate for that schema passes, and is reported SKIP
(blocked by the gate) otherwise — never a pass against nothing.
"""
import copy
import importlib.util
import json
import os
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import asset_policy  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "validate_repo", os.path.join(ROOT, "scripts", "validate-repo.py"))
_validate_repo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_validate_repo)
validate_instance = _validate_repo.validate_instance
check_schema = _validate_repo.check_schema

try:
    import yaml
except ImportError:
    yaml = None

failures = []
skipped = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name
          + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def skip(name, reason):
    print(f"SKIP {name} — {reason}")
    skipped.append(name)


def load_json(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


def load_schema(name):
    path = os.path.join(ROOT, "schemas", name)
    if not os.path.exists(path):
        return None
    return load_json(os.path.join("schemas", name))


def load_fixture(name):
    return load_json(os.path.join("tests", "fixtures", name))


def errors_for(schema, value):
    errs = []
    validate_instance(schema, value, "$", errs)
    return errs


# --- Fixed vocabularies (CF-WO-P0-006; never a single animation_type) ---
VISUAL_STYLE = {"flat-2d-vector", "hand-drawn-2d", "illustrated-2d",
                "anime", "cartoon-2d", "stylized-3d", "semi-realistic-3d",
                "photorealistic-3d-cgi", "photorealistic-digital-human",
                "photorealistic-digital-animal-creature", "mixed",
                "captured-live-action"}
ARTICULATION_TARGET = {"human-mouth-lips", "bird-beak", "animal-muzzle",
                       "creature-jaw-mandibles", "other"}
SUBJECT_KIND = {"human", "digital-human", "real-animal", "cgi-animal",
                "fictional-creature", "anthropomorphic", "mixed",
                "non-character"}
VOICE_SOURCE = {"user-recording", "ai-generated"}
REGISTRATION_FIELDS = {
    "character_id", "display_name", "character_type", "species",
    "visual_style_profile", "canonical_reference_images",
    "additional_reference_images", "features",
    "expression_pose_references", "default_voice_profile_id",
    "additional_voice_profile_ids", "audio_assets", "ownership_scope",
    "consent_permissions", "registration_history", "schema_version"}
CHARACTER_EXT_FIELDS = {
    "subject_kind", "species", "anatomy_profile", "articulation_target",
    "identity_origin", "reference_media_provenance",
    "visual_style_profile", "voice_profile_ids"}
VOICE_EXT_FIELDS = {
    "voice_profile_id", "character_id", "source",
    "audio_reference_assets", "language", "accent",
    "vocal_characteristics", "pitch_range", "speaking_pace",
    "pronunciation_preferences", "emotional_delivery_range",
    "provider", "model", "approval_status", "consent_status"}
ALLOWED_SCHEMA_VERSIONS = (["2.3"], ["2.4"], ["2.5"],
                           ["2.3", "2.5"], ["2.4", "2.5"])
INVITATION_STATES = {"invited", "accepted", "skipped", "dismissed"}
REGISTRATION_EVENTS = {"registered-temporary", "registered-permanent",
                       "updated", "voice-profile-added",
                       "voice-profile-removed", "deprecated"}


def schema_gate(name, contract_fields, required_fields=()):
    """One check per schema: exists, well-formed (repo's check_schema),
    carries the contract fields, sane schema_version. Returns the
    schema dict, or None when the gate fails (callers then SKIP the
    fixture-vs-schema checks that depend on it)."""
    schema = load_schema(name)
    check(f"SCHEMA-GATE: schemas/{name} exists", schema is not None,
          "schema file missing — Agent C dependency unmet")
    if schema is None:
        return None
    errs = []
    check_schema(schema, f"schemas/{name}", errs)
    check(f"SCHEMA-GATE: schemas/{name} is well-formed (repo subset)",
          not errs, "; ".join(errs))
    props = schema.get("properties", {})
    check(f"SCHEMA-GATE: schemas/{name} carries the contract fields",
          set(contract_fields) <= set(props),
          f"missing={sorted(set(contract_fields) - set(props))}")
    check(f"SCHEMA-GATE: schemas/{name} schema_version is 2.3/2.4/2.5",
          props.get("schema_version", {}).get("enum")
          in ALLOWED_SCHEMA_VERSIONS,
          f"enum={props.get('schema_version', {}).get('enum')}")
    if required_fields:
        check(f"SCHEMA-GATE: schemas/{name} requires "
              f"{sorted(required_fields)}",
              set(required_fields) <= set(schema.get("required", [])),
              f"required={schema.get('required')}")
    return schema


def validate_against_schema(schema, fixture_name, label):
    """validate_instance for one fixture; call only after its gate."""
    if schema is None:
        skip(label, "schema gate failed")
        return
    errs = errors_for(schema, load_fixture(fixture_name))
    check(label, not errs, "; ".join(errs))


# --- In-test contract validators (rules the JSON-Schema subset cannot
# express, or cross-record rules). A rule with no validator support yet
# lives here, in the test, by design — see the module docstring. ---
def validate_registration(reg):
    """Fixed character-registration contract. Returns error strings."""
    errs = []
    if not isinstance(reg, dict):
        return ["registration is not an object"]
    if not reg.get("character_id"):
        errs.append("missing character_id (Unique Character ID required)")
    if not reg.get("display_name"):
        errs.append("missing display_name (Character Name required)")
    refs = reg.get("canonical_reference_images")
    if not isinstance(refs, list) or not refs:
        errs.append("canonical_reference_images must be a non-empty list")
    else:
        seen = set()
        for i, ref in enumerate(refs):
            if not isinstance(ref, dict) or not ref.get("asset_id"):
                errs.append(f"canonical_reference_images[{i}] "
                            "needs asset_id")
            elif ref["asset_id"] in seen:
                errs.append(f"duplicate reference asset_id "
                            f"{ref['asset_id']!r}")
            else:
                seen.add(ref["asset_id"])
            if not ref.get("role"):
                errs.append(f"canonical_reference_images[{i}] needs role")
    consent = reg.get("consent_permissions") or {}
    if consent.get("granted") is not True:
        errs.append("consent_permissions.granted must be true")
    if not reg.get("ownership_scope"):
        errs.append("missing ownership_scope")
    history = reg.get("registration_history")
    if not isinstance(history, list) or not history:
        errs.append("registration_history must be a non-empty list")
    else:
        for ev in history:
            if (ev.get("event") not in REGISTRATION_EVENTS):
                errs.append(f"unknown registration event "
                            f"{ev.get('event')!r}")
    errs.extend(asset_policy.check_character_record_separation(reg))
    return errs


def validate_voice_profile(vp):
    """Fixed voice-profile contract (Addendum C §5)."""
    errs = []
    if not isinstance(vp, dict):
        return ["voice profile is not an object"]
    if not vp.get("voice_profile_id"):
        errs.append("missing voice_profile_id")
    if not vp.get("character_id"):
        errs.append("missing character_id link")
    source = vp.get("source")
    if source not in VOICE_SOURCE:
        errs.append(f"source {source!r} not in {sorted(VOICE_SOURCE)}")
    if source == "user-recording":
        if not vp.get("audio_reference_assets"):
            errs.append("user-recording needs audio_reference_assets")
        if vp.get("consent_status") != "granted":
            errs.append("user-recording needs consent_status 'granted'")
    if source == "ai-generated":
        if vp.get("approval_status") != "approved":
            errs.append("ai-generated voice needs approval_status "
                        "'approved'")
        if not vp.get("provider"):
            errs.append("ai-generated voice needs a provider")
    if vp.get("consent_status") not in ("granted", "pending", "denied",
                                        "not-required"):
        errs.append(f"unknown consent_status "
                    f"{vp.get('consent_status')!r}")
    return errs


def validate_invitation(inv):
    """First-run invitation contract: an explicit state, and skipping
    must never block production."""
    errs = []
    if inv.get("state") not in INVITATION_STATES:
        errs.append(f"unknown invitation state {inv.get('state')!r}")
    if inv.get("state") == "skipped" and inv.get("blocks_production"):
        errs.append("a skipped invitation must not block production")
    if inv.get("state") == "invited" and inv.get("blocks_production"):
        errs.append("merely being invited must not block production")
    return errs


def register(registry, reg):
    """Register or reject: a second registration reusing an existing
    character_id is rejected, never silently merged."""
    errs = validate_registration(reg)
    if reg.get("character_id") in registry:
        errs.append(f"duplicate character_id "
                    f"{reg.get('character_id')!r}: already registered as "
                    f"{registry[reg['character_id']].get('display_name')!r}")
    if errs:
        return errs
    registry[reg["character_id"]] = copy.deepcopy(reg)
    return []


def resolve_references(registry, character_id):
    """All reference asset_ids bound to one Character ID, or an error."""
    reg = registry.get(character_id)
    if reg is None:
        return None, [f"unknown character_id {character_id!r}"]
    refs = [r["asset_id"] for r in reg.get("canonical_reference_images", [])]
    refs += [r["asset_id"]
             for r in reg.get("additional_reference_images", [])]
    return refs, []


def resolve_voice_for_character(voice_registry, character_id,
                                voice_profile_id=None):
    """The voice profile bound to a character (optionally: one ID)."""
    matches = [v for v in voice_registry.values()
               if v.get("character_id") == character_id]
    if not matches:
        return None, [f"no voice profile for character {character_id!r}"]
    if voice_profile_id is not None:
        hit = [v for v in matches
               if v.get("voice_profile_id") == voice_profile_id]
        if not hit:
            return None, [f"voice_profile_id {voice_profile_id!r} is not "
                          f"bound to character {character_id!r}"]
        return hit[0], []
    return matches[0], []


def check_voice_binding(voice_registry, character_id, voice_profile_id):
    """A character/voice binding is valid only when the voice profile's
    own character_id is the character it is bound to."""
    vp = voice_registry.get(voice_profile_id)
    if vp is None:
        return [f"unknown voice_profile_id {voice_profile_id!r}"]
    if vp.get("character_id") != character_id:
        return [f"voice_profile_id {voice_profile_id!r} belongs to "
                f"character {vp.get('character_id')!r}, not "
                f"{character_id!r} — cross-character assignment rejected"]
    return []


def resolve_for_user(reg, requesting_user):
    """Owner/workspace-scoped resolution: another user's assets are
    rejected, never silently served."""
    if reg.get("ownership_scope") != requesting_user:
        return [f"asset owned by {reg.get('ownership_scope')!r} cannot "
                f"be resolved under user {requesting_user!r}"]
    return []


def is_releasable(path):
    """A path may appear in a public release package only if it is not
    private character/voice media (validate-repo.py private-overlay
    rules: characters/ holds only .gitkeep + README.md; media files
    are never tracked)."""
    if path in ("characters/.gitkeep", "characters/README.md"):
        return True
    if path.startswith("characters/") or path.startswith("private-data/"):
        return False
    if path.lower().endswith((".mp3", ".mp4", ".wav", ".webm", ".mov",
                              ".png", ".jpg", ".jpeg")):
        return False
    return True


def main():
    # --- SCHEMA DEPENDENCY GATES --------------------------------------
    reg_schema = schema_gate(
        "character-registration.json", REGISTRATION_FIELDS,
        required_fields=("character_id", "display_name"))
    if reg_schema is not None:
        props = reg_schema["properties"]
        check("SCHEMA-GATE: character-registration visual_style "
              "uses the fixed VISUAL_STYLE vocabulary",
              set(props.get("visual_style_profile", {}).get(
                  "properties", {}).get("visual_style", {}).get(
                      "enum", [])) == VISUAL_STYLE,
              f"enum={props.get('visual_style_profile', {}).get('properties', {}).get('visual_style', {}).get('enum')}")
        check("SCHEMA-GATE: character-registration reference items "
              "require asset_id + role",
              set(props.get("canonical_reference_images", {}).get(
                  "items", {}).get("required", []))
              >= {"asset_id", "role"})
    char_schema = schema_gate("character.json", CHARACTER_EXT_FIELDS)
    if char_schema is not None:
        props = char_schema["properties"]
        check("SCHEMA-GATE: character.json subject_kind uses the fixed "
              "SUBJECT_KIND vocabulary",
              set(props.get("subject_kind", {}).get("enum", []))
              == SUBJECT_KIND)
        check("SCHEMA-GATE: character.json articulation_target uses "
              "the fixed ARTICULATION_TARGET vocabulary",
              set(props.get("articulation_target", {}).get("enum", []))
              == ARTICULATION_TARGET)
    voice_schema = schema_gate("voice-profile.json", VOICE_EXT_FIELDS)
    if voice_schema is not None:
        props = voice_schema["properties"]
        check("SCHEMA-GATE: voice-profile.json source enum is exactly "
              "user-recording / ai-generated",
              set(props.get("source", {}).get("enum", [])) == VOICE_SOURCE)
        check("SCHEMA-GATE: voice-profile.json carries approval_status "
              "+ consent_status",
              "approval_status" in props and "consent_status" in props)

    # Fixture-vs-schema validation (repo's validate_instance), only
    # where the gate passed.
    validate_against_schema(
        reg_schema, "character-registration-valid.json",
        "valid fixture character-registration-valid.json validates")
    validate_against_schema(
        reg_schema, "character-registration-bird-valid.json",
        "valid fixture character-registration-bird-valid.json validates")
    validate_against_schema(
        char_schema, "character-extended-valid.json",
        "valid fixture character-extended-valid.json validates")
    validate_against_schema(
        voice_schema, "voice-profile-user-recording.json",
        "valid fixture voice-profile-user-recording.json validates")
    validate_against_schema(
        voice_schema, "voice-profile-ai-generated.json",
        "valid fixture voice-profile-ai-generated.json validates")
    # Regression: the pre-P0-006 fixtures still validate against the
    # additively extended schemas.
    validate_against_schema(
        char_schema, "character-valid.json",
        "regression: character-valid.json still validates")
    validate_against_schema(
        voice_schema, "voice-profile-valid.json",
        "regression: voice-profile-valid.json still validates")

    # No single animation_type enum anywhere in the new fixtures.
    for name in ("character-registration-valid.json",
                 "character-registration-bird-valid.json",
                 "voice-profile-user-recording.json",
                 "voice-profile-ai-generated.json",
                 "character-extended-valid.json"):
        text = json.dumps(load_fixture(name))
        check(f"no animation_type in fixture {name}",
              "animation_type" not in text)

    mina = load_fixture("character-registration-valid.json")
    kiki = load_fixture("character-registration-bird-valid.json")
    mina_voice = load_fixture("voice-profile-user-recording.json")
    kiki_voice = load_fixture("voice-profile-ai-generated.json")
    registry = {}
    voice_registry = {mina_voice["voice_profile_id"]: mina_voice,
                      kiki_voice["voice_profile_id"]: kiki_voice}

    # --- AC-01: first-run invitation + skip path -----------------------
    invited = load_fixture("registration-invitation.json")
    invited["state"] = "invited"
    check("AC-01: first-run invitation (invited state) validates and "
          "does not block production",
          not validate_invitation(invited)
          and invited.get("blocks_production") is False)
    skipped_inv = load_fixture("registration-invitation.json")
    check("AC-01: skipped invitation validates, needs no character_id, "
          "and does not block production",
          skipped_inv.get("state") == "skipped"
          and not validate_invitation(skipped_inv)
          and skipped_inv.get("character_id") is None
          and skipped_inv.get("blocks_production") is False)

    # --- AC-02: permanent registration, unique name + Character ID ----
    errs = validate_registration(mina)
    check("AC-02: permanent registration validates (contract)",
          not errs, "; ".join(errs))
    mapped = {"explicit_authorisation":
              mina["consent_permissions"]["granted"],
              "name": mina["display_name"], "id": mina["character_id"],
              "references": [r["asset_id"] for r in
                             mina["canonical_reference_images"]]}
    check("AC-02: permanent registration also passes the repo's "
          "asset_policy registration gate",
          asset_policy.validate_character_registration(mapped) == [])
    check("AC-02: Character ID is visible on the registration",
          mina["character_id"] == "char-001"
          and mina["display_name"] == "Mina")
    check("AC-02: registration is permanent (history records "
          "registered-permanent)",
          any(e.get("event") == "registered-permanent"
              for e in mina["registration_history"]))

    # --- AC-03: duplicate Character IDs rejected -----------------------
    check("AC-03: first registration of char-001 succeeds",
          register(registry, mina) == [])
    dup = copy.deepcopy(mina)
    dup["display_name"] = "Mina Again"
    dup_errs = register(registry, dup)
    check("AC-03: second registration with the same Character ID is "
          "rejected",
          bool(dup_errs) and any("duplicate character_id" in e
                                 for e in dup_errs),
          "; ".join(dup_errs))
    check("AC-03: the registry still holds the original registration",
          registry["char-001"]["display_name"] == "Mina")

    # --- AC-04: temporary use without permanent registration ----------
    tmp = load_fixture("temporary-asset-use.json")
    check("AC-04: temporary-use asset validates without a character_id",
          "character_id" not in tmp
          and tmp.get("temporary_only") is True
          and tmp.get("retention") == "temporary"
          and tmp.get("permanent_records_created") == [])
    check("AC-04: TEMPORARY_ASSET_USE creates no permanent record "
          "(repo asset policy)",
          not asset_policy.may_create_permanent_record(
              "TEMPORARY_ASSET_USE"))
    check("AC-04: temporary use does not create a registry entry",
          "tmp-asset-001" not in registry)

    # --- AC-05: several reference images against one Character ID -----
    check("AC-05: registration with canonical + additional references "
          "validates",
          not validate_registration(mina))
    refs, ref_errs = resolve_references(registry, "char-001")
    check("AC-05: all references resolve under the same Character ID",
          not ref_errs and refs == ["ref-mina-front", "ref-mina-side",
                                    "ref-mina-smile"],
          f"refs={refs} errs={ref_errs}")

    # --- AC-06: a later project resolves the correct character --------
    check("AC-06: second character registers under its own ID",
          register(registry, kiki) == [])
    mina_refs, _ = resolve_references(registry, "char-001")
    kiki_refs, _ = resolve_references(registry, "char-002")
    check("AC-06: project referencing char-001 resolves exactly Mina's "
          "references",
          mina_refs == ["ref-mina-front", "ref-mina-side",
                        "ref-mina-smile"])
    check("AC-06: project referencing char-002 resolves exactly Kiki's "
          "references (no mixing)",
          kiki_refs == ["ref-kiki-front", "ref-kiki-side",
                        "ref-kiki-wing"])
    check("AC-06: the two characters' reference sets are disjoint",
          not set(mina_refs) & set(kiki_refs))

    # --- AC-07: user-recorded voice for a registered character --------
    errs = validate_voice_profile(mina_voice)
    check("AC-07: user-recorded voice profile validates", not errs,
          "; ".join(errs))
    check("AC-07: user-recorded voice links to its character",
          mina_voice["character_id"] == "char-001"
          and mina_voice["voice_profile_id"]
          == mina["default_voice_profile_id"]
          and mina_voice["audio_reference_assets"])

    # --- AC-08: approved AI-generated voice, compatible provider ------
    if yaml is None:
        check("AC-08: companion registry readable (PyYAML available)",
              False, "PyYAML not installed")
        omni_exercised = False
    else:
        with open(os.path.join(
                ROOT, "architecture",
                "COMPANION_CAPABILITY_REGISTRY.yaml"),
                encoding="utf-8") as f:
            companions = yaml.safe_load(f)
        vs = [c for c in companions.get("companions", [])
              if c.get("name") == "VoiceStudio"]
        omni_exercised = any(
            "OmniVoice" in (cap.get("capability") or "")
            and cap.get("evidence_level") == "exercised_recorded_run"
            for c in vs for cap in c.get("capabilities", []))
        check("AC-08: a compatible provider exists (VoiceStudio "
              "OmniVoice TTS is exercised_recorded_run)",
              omni_exercised)
    errs = validate_voice_profile(kiki_voice)
    check("AC-08: AI-generated voice profile validates when approved "
          "and a compatible provider exists",
          not errs and omni_exercised, "; ".join(errs))
    check("AC-08: AI-generated voice links to its character",
          kiki_voice["character_id"] == "char-002"
          and kiki_voice["voice_profile_id"]
          == kiki["default_voice_profile_id"])

    # --- AC-09: Voice Profile stays linked across projects ------------
    proj_a = {"project_id": "proj-a", "character_id": "char-001"}
    proj_b = {"project_id": "proj-b", "character_id": "char-001"}
    voice_a, err_a = resolve_voice_for_character(
        voice_registry, proj_a["character_id"])
    voice_b, err_b = resolve_voice_for_character(
        voice_registry, proj_b["character_id"])
    check("AC-09: two productions referencing char-001 resolve the "
          "same voice_profile_id",
          not err_a and not err_b
          and voice_a["voice_profile_id"] == "voice-mina-001"
          and voice_b["voice_profile_id"] == "voice-mina-001")

    # --- AC-10: one character's voice is never assigned to another ----
    check("AC-10: binding Mina's voice to Kiki is rejected",
          bool(check_voice_binding(voice_registry, "char-002",
                                   "voice-mina-001")))
    check("AC-10: binding Kiki's voice to Mina is rejected",
          bool(check_voice_binding(voice_registry, "char-001",
                                   "voice-kiki-001")))
    check("AC-10: each character's own binding is accepted",
          not check_voice_binding(voice_registry, "char-001",
                                  "voice-mina-001")
          and not check_voice_binding(voice_registry, "char-002",
                                      "voice-kiki-001"))

    # --- AC-11: private assets are not exposed to another user --------
    check("AC-11: user-A asset resolves under user-A",
          not resolve_for_user(mina, "user-a"))
    check("AC-11: user-A asset is rejected when resolved under user-B",
          bool(resolve_for_user(mina, "user-b")))
    check("AC-11: a voice bound to a user-A character is rejected "
          "under user-B (ownership follows the character)",
          bool(resolve_for_user(
              {"ownership_scope":
               mina["ownership_scope"]}, "user-b")))

    # --- AC-12: private media excluded from public releases -----------
    manifest = load_json("release-manifest.json")
    manifest_schema = load_schema("release-manifest.json")
    if manifest_schema is None:
        check("AC-12: release-manifest schema exists", False,
              "schemas/release-manifest.json missing")
    else:
        errs = errors_for(manifest_schema, manifest)
        check("AC-12: the actual release-manifest.json validates",
              not errs, "; ".join(errs))
    listed = [f["path"] for f in manifest.get("files", [])]
    check("AC-12: no file under characters/ (except README.md) is in "
          "the release manifest file list",
          all(p == "characters/README.md"
              or not p.startswith("characters/") for p in listed),
          f"offenders={[p for p in listed if p.startswith('characters/') and p != 'characters/README.md']}")
    check("AC-12: no private-overlay path is in the release manifest",
          not any(p.startswith("private-data/") for p in listed))
    check("AC-12: no media file is in the release manifest",
          not any(p.lower().endswith(
              (".mp3", ".mp4", ".wav", ".webm", ".mov", ".png", ".jpg",
               ".jpeg")) for p in listed))
    check("AC-12: a fixture private asset does not validate as "
          "releasable",
          not is_releasable("characters/char-001/reference-front.jpg")
          and not is_releasable("characters/char-001/voice-reference.mp3"))
    check("AC-12: public files do validate as releasable",
          is_releasable("characters/README.md")
          and is_releasable("docs/07-character-registry.md"))
    gi = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    check("AC-12: .gitignore covers characters/* (private-overlay rule)",
          "characters/*" in gi)
    try:
        tracked = subprocess.run(
            ["git", "-C", ROOT, "ls-files"], capture_output=True,
            text=True, check=True).stdout.splitlines()
        char_tracked = sorted(p for p in tracked
                              if p.startswith("characters/"))
        check("AC-12: only .gitkeep + README.md are tracked under "
              "characters/",
              char_tracked == ["characters/.gitkeep",
                               "characters/README.md"],
              f"tracked={char_tracked}")
    except Exception as e:  # pragma: no cover - git always present here
        check("AC-12: git ls-files readable", False, str(e))

    # --- QC-01: character-identity QC (Addendum C §12) -----------------
    refs, errs = resolve_references(registry, "char-999")
    check("QC-01: a binding to a wrong (unregistered) Character ID is "
          "rejected",
          refs is None and bool(errs))
    check("QC-01: Mina's reference claimed under Kiki's ID is rejected "
          "(mixed characters)",
          "ref-mina-front" not in resolve_references(
              registry, "char-002")[0])
    bad = copy.deepcopy(mina)
    bad["canonical_reference_images"] = [
        {"asset_id": "ref-kiki-front", "role": "front",
         "path": "characters/char-002/reference-front.jpg"}]
    bad_refs, _ = resolve_references({"char-001": bad}, "char-001")
    check("QC-01: a registration whose canonical references belong to "
          "another character does not resolve to the expected set",
          bad_refs != ["ref-mina-front", "ref-mina-side",
                       "ref-mina-smile"],
          f"resolved={bad_refs}")

    print(f"test_character_registration: "
          f"{'PASS' if not failures else 'FAIL'} "
          f"({len(failures)} failure(s), {len(skipped)} skipped)")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
