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
    "additional_voice_profile_ids", "audio_assets", "ownership",
    "ownership_scope",
    "consent_permissions", "registration_history", "schema_version"}
# CF-WO-P0-007 (B): deterministic test identities for the structured
# ownership object. owner-a/workspace-a own Mina + Nila; owner-b /
# workspace-b are the "other user / other workspace" in the tests.
OWNER_A = {"owner_id": "owner-a", "workspace_id": "workspace-a",
           "visibility": "private", "sharing": "none"}
OWNER_B = {"owner_id": "owner-b", "workspace_id": "workspace-b",
           "visibility": "private", "sharing": "none"}
OWNER_A_WS_B = {"owner_id": "owner-a", "workspace_id": "workspace-b",
                "visibility": "private", "sharing": "none"}
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
    # CF-WO-P0-007 (B): structured ownership is REQUIRED (the schema
    # requires it too). The legacy ownership_scope string is optional
    # and deprecated — it is never a substitute for the object.
    errs.extend(asset_policy.validate_ownership(reg.get("ownership")))
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
    """Fixed voice-profile contract (Addendum C §5, as amended by
    CF-WO-P0-007 Correction C).

    Consent governing rule: consent_status governs; consent.granted
    must agree with it. consent_status "not-required" is legitimate
    only when human_voice_donor is explicitly false. Approval:
    approval_status must EXIST (pending is a legitimate state — a
    generated voice is never approved automatically); whether the
    profile may be used in production is decided by the resolver
    (asset_policy.resolve_voice_for_production), not here. status
    "approved" without approval_status "approved" is invalid.
    Ownership + the full v2.5 minimum-field set are enforced by
    asset_policy.validate_voice_profile (see
    validate_voice_profile_v25 below) — this §5 validator predates
    structured ownership and does not demand it, so the pre-P0-007
    fixtures it checks (voice-profile-user-recording.json /
    voice-profile-ai-generated.json, which carry no ownership
    object) keep their §5 meaning.
    """
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
        if vp.get("approval_status") not in ("pending", "approved",
                                             "rejected"):
            errs.append("ai-generated voice needs approval_status "
                        "(pending, approved or rejected)")
        if not vp.get("provider"):
            errs.append("ai-generated voice needs a provider")
    if vp.get("consent_status") not in ("granted", "pending", "denied",
                                        "not-required"):
        errs.append(f"unknown consent_status "
                    f"{vp.get('consent_status')!r}")
    consent = vp.get("consent") or {}
    if vp.get("consent_status") == "granted" \
            and consent.get("granted") is not True:
        errs.append("consent_status 'granted' but consent.granted is "
                    "not true")
    if vp.get("consent_status") == "not-required" \
            and vp.get("human_voice_donor") is not False:
        errs.append("consent_status 'not-required' is legitimate only "
                    "when human_voice_donor is false (no real person's "
                    "voice was used)")
    if vp.get("human_voice_donor") is True \
            and vp.get("consent_status") != "granted":
        errs.append("a real-person voice donor requires explicit "
                    "permission (consent_status 'granted')")
    if vp.get("status") == "approved" \
            and vp.get("approval_status") != "approved":
        errs.append("status 'approved' without approval_status "
                    "'approved' is invalid (no approval record)")
    return errs


def validate_voice_profile_v25(vp, character=None):
    """Full v2.5 voice-profile verdict: (schema_errors, python_errors).

    Both layers are returned separately so the C tests can pin each
    layer's verdict: the JSON Schema is permissive for v2.5
    conditional fields (the repo validator subset has no if/then),
    so schema-pass + python-fail is an expected, documented
    outcome for conditional cases — never a silent disagreement.
    A record is fully valid v2.5 only when both lists are empty.
    """
    schema = load_schema("voice-profile.json")
    schema_errs = errors_for(schema, vp) if schema is not None else [
        "voice-profile.json schema missing"]
    python_errs = asset_policy.validate_voice_profile(vp, character)
    return schema_errs, python_errs


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
                                voice_profile_id=None,
                                character_registry=None,
                                requesting_owner_id=None,
                                requesting_workspace_id=None):
    """The voice profile bound to a character (optionally: one ID).

    CF-WO-P0-007 (B): when a character_registry is given, the
    resolved voice's ownership must match the character's
    ownership; when a requesting owner/workspace is given, the
    requester must be allowed access by the voice ownership.
    With no registry/requester the legacy binding-only behaviour
    is kept (AC-09).
    """
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
        voice = hit[0]
    else:
        voice = matches[0]
    if character_registry is not None:
        character = character_registry.get(character_id)
        if character is None:
            return None, [f"unknown character_id {character_id!r}"]
        if not asset_policy.ownerships_match(
                voice.get("ownership"), character.get("ownership")):
            return None, ["voice profile ownership does not match the "
                          "character ownership (owner/workspace must "
                          "match)"]
    if requesting_owner_id is not None or \
            requesting_workspace_id is not None:
        if not asset_policy.ownership_allows_access(
                voice.get("ownership"), requesting_owner_id,
                requesting_workspace_id):
            return None, ["voice profile is not accessible to this "
                          "owner/workspace (private by default; no "
                          "cross-user sharing)"]
    return voice, []


def check_voice_binding(voice_registry, character_id, voice_profile_id,
                        character_registry=None):
    """A character/voice binding is valid only when the voice profile's
    own character_id is the character it is bound to (and, when a
    character registry is given, the voice ownership matches the
    character ownership)."""
    vp = voice_registry.get(voice_profile_id)
    if vp is None:
        return [f"unknown voice_profile_id {voice_profile_id!r}"]
    if vp.get("character_id") != character_id:
        return [f"voice_profile_id {voice_profile_id!r} belongs to "
                f"character {vp.get('character_id')!r}, not "
                f"{character_id!r} — cross-character assignment rejected"]
    if character_registry is not None:
        character = character_registry.get(character_id)
        if character is None:
            return [f"unknown character_id {character_id!r}"]
        if not asset_policy.ownerships_match(
                vp.get("ownership"), character.get("ownership")):
            return ["voice profile ownership does not match the "
                    "character ownership (owner/workspace must match)"]
    return []


def resolve_for_user(reg, requesting_user, requesting_workspace=None):
    """Owner/workspace-scoped resolution: another user's assets are
    rejected, never silently served.

    CF-WO-P0-007 (B): a structured ownership object, when present,
    governs — the requester must be its owner_id in its
    workspace_id (see asset_policy.ownership_allows_access). The
    legacy ownership_scope string is consulted ONLY for records
    with no ownership object. requesting_user is an owner_id;
    requesting_workspace is a workspace_id.
    """
    ownership = reg.get("ownership") if isinstance(reg, dict) else None
    if isinstance(ownership, dict):
        if asset_policy.ownership_allows_access(
                ownership, requesting_user, requesting_workspace):
            return []
        return [f"asset owned by {ownership.get('owner_id')!r} in "
                f"workspace {ownership.get('workspace_id')!r} cannot "
                f"be resolved under owner {requesting_user!r} "
                f"(workspace {requesting_workspace!r})"]
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
        required_fields=("character_id", "display_name", "ownership"))
    if reg_schema is not None:
        props = reg_schema["properties"]
        check("SCHEMA-GATE: character-registration requires the "
              "structured ownership object",
              "ownership" in reg_schema.get("required", []),
              f"required={reg_schema.get('required')}")
        check("SCHEMA-GATE: character-registration keeps "
              "ownership_scope as OPTIONAL legacy (deprecated, "
              "superseded by ownership)",
              "ownership_scope" in props
              and "ownership_scope" not in reg_schema.get("required", []),
              f"required={reg_schema.get('required')}")
        check("SCHEMA-GATE: character-registration ownership shape is "
              "owner_id + workspace_id + visibility + sharing",
              set(props.get("ownership", {}).get("properties", {}))
              == {"owner_id", "workspace_id", "visibility", "sharing"}
              and set(props.get("ownership", {}).get("required", []))
              == {"owner_id", "workspace_id", "visibility", "sharing"}
              and props.get("ownership", {}).get("additionalProperties")
              is False)
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
        check("SCHEMA-GATE: voice-profile.json carries the structured "
              "ownership object (same shape as character-registration)",
              set(props.get("ownership", {}).get("properties", {}))
              == {"owner_id", "workspace_id", "visibility", "sharing"}
              and set(props.get("ownership", {}).get("required", []))
              == {"owner_id", "workspace_id", "visibility", "sharing"})
        check("SCHEMA-GATE: voice-profile.json does NOT add v2.5 fields "
              "to the global required array (v2.3 must keep passing)",
              "ownership" not in voice_schema.get("required", [])
              and "voice_profile_id" not in voice_schema.get("required", [])
              and "source" not in voice_schema.get("required", []),
              f"required={voice_schema.get('required')}")
        check("SCHEMA-GATE: voice-profile.json records the human-donor "
              "condition + provider transmission disclosure",
              "human_voice_donor" in props
              and "provider_transmission" in props)

    # The bird registration fixture (character-registration-bird-valid
    # .json, char-002) is owned by another CF-WO-P0-007 worker: its
    # structured ownership object is pending from them. Until it
    # lands, the fixture-vs-schema check is SKIPped (never a pass
    # against nothing) and the registration tests below use an
    # in-memory copy with the ownership object injected — the file
    # itself is not modified here. The check un-skips automatically
    # once the fixture carries ownership.
    _bird_reg = load_fixture("character-registration-bird-valid.json")
    _bird_ownership_pending = "ownership" not in _bird_reg
    if _bird_ownership_pending:
        skip("valid fixture character-registration-bird-valid.json "
             "validates",
             "bird fixture ownership pending from its owning worker")
    else:
        validate_against_schema(
            reg_schema, "character-registration-bird-valid.json",
            "valid fixture character-registration-bird-valid.json "
            "validates")

    # Fixture-vs-schema validation (repo's validate_instance), only
    # where the gate passed.
    validate_against_schema(
        reg_schema, "character-registration-valid.json",
        "valid fixture character-registration-valid.json validates")
    validate_against_schema(
        reg_schema, "character-registration-valid-human.json",
        "valid fixture character-registration-valid-human.json "
        "validates")
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
    if _bird_ownership_pending:
        # In-memory only: the registration logic below is exercised
        # with the ownership object present; the file gains it from
        # its owning worker (see the SKIP above).
        kiki = copy.deepcopy(kiki)
        kiki["ownership"] = copy.deepcopy(OWNER_A)
    mina_voice = load_fixture("voice-profile-user-recording.json")
    kiki_voice = load_fixture("voice-profile-ai-generated.json")
    # Full valid v2.5 records (CF-WO-P0-007 Worker 2 fixtures):
    # Nila (user-recorded voice) + Aria (AI-generated voice), both
    # owned by owner-a / workspace-a, private, sharing none.
    nila = load_fixture("character-registration-valid-human.json")
    nila_voice = load_fixture("voice-profile-valid-user-recorded.json")
    aria_voice = load_fixture("voice-profile-valid-ai-generated.json")
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
    # CF-WO-P0-007 (B): resolution is by structured ownership now
    # (owner-a / workspace-a). The legacy ownership_scope string
    # ("user-a") is no longer an identity once the ownership object
    # exists.
    check("AC-11: owner-A asset resolves under owner-A / workspace-A",
          not resolve_for_user(mina, "owner-a", "workspace-a"))
    check("AC-11: owner-A asset is rejected when resolved under "
          "owner-B",
          bool(resolve_for_user(mina, "owner-b", "workspace-b")))
    check("AC-11: owner-A asset is rejected under owner-A in the "
          "wrong workspace",
          bool(resolve_for_user(mina, "owner-a", "workspace-b")))
    check("AC-11: a voice bound to an owner-A character is rejected "
          "under owner-B (ownership follows the character)",
          bool(resolve_for_user(
              {"ownership": copy.deepcopy(OWNER_A)}, "owner-b",
              "workspace-b")))
    check("AC-11: legacy ownership_scope still governs a record with "
          "no ownership object (migration fallback)",
          not resolve_for_user({"ownership_scope": "user-a"}, "user-a")
          and bool(resolve_for_user({"ownership_scope": "user-a"},
                                       "user-b")))

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

    # --- CF-WO-P0-007 (B): structured private ownership -------------
    # The production resolver is asset_policy.resolve_voice_for_
    # production; these tests verify it (not isolated example
    # conditions). v2.5 voice fixtures: Nila (user-recorded) + Aria
    # (AI-generated), both owner-a / workspace-a.
    v25_voice_registry = {
        nila_voice["voice_profile_id"]: nila_voice,
        aria_voice["voice_profile_id"]: aria_voice}
    nila_registry = {nila["character_id"]: nila}
    aria_character = {"character_id": "char-aria-001",
                      "ownership": copy.deepcopy(OWNER_A)}
    aria_registry = {aria_character["character_id"]: aria_character}
    v25_registries = {**nila_registry, **aria_registry}

    voice, errs = asset_policy.resolve_voice_for_production(
        v25_voice_registry, v25_registries, "char-nila-001",
        "voice-nila-001", "owner-a", "workspace-a")
    check("B: Owner-A character resolved by Owner-A (production "
          "resolver)",
          not errs and voice is not None
          and voice["voice_profile_id"] == "voice-nila-001",
          "; ".join(errs))
    voice, errs = resolve_voice_for_character(
        v25_voice_registry, "char-nila-001", "voice-nila-001",
        character_registry=nila_registry,
        requesting_owner_id="owner-a",
        requesting_workspace_id="workspace-a")
    check("B: Owner-A character voice resolves under Owner-A "
          "(binding resolver)",
          not errs and voice is not None, "; ".join(errs))
    _, errs = asset_policy.resolve_voice_for_production(
        v25_voice_registry, v25_registries, "char-nila-001",
        "voice-nila-001", "owner-b", "workspace-b")
    check("B: Owner-A character rejected by Owner-B",
          bool(errs), "; ".join(errs))
    _, errs = asset_policy.resolve_voice_for_production(
        v25_voice_registry, v25_registries, "char-nila-001",
        "voice-nila-001", "owner-a", "workspace-b")
    check("B: same owner but wrong workspace rejected",
          bool(errs), "; ".join(errs))
    _, errs = asset_policy.resolve_voice_for_production(
        v25_voice_registry, v25_registries, "char-nila-001",
        "voice-nila-001", "owner-b", "workspace-a")
    check("B: no cross-user sharing by default (same workspace, "
          "other owner, sharing none)",
          bool(errs), "; ".join(errs))
    shared_ws = copy.deepcopy(nila_voice)
    shared_ws["ownership"] = {"owner_id": "owner-a",
                              "workspace_id": "workspace-a",
                              "visibility": "shared",
                              "sharing": "workspace"}
    check("B: sharing 'workspace' admits another owner in the same "
          "workspace",
          asset_policy.ownership_allows_access(
              shared_ws["ownership"], "owner-b", "workspace-a"))
    check("B: sharing 'workspace' still rejects another workspace",
          not asset_policy.ownership_allows_access(
              shared_ws["ownership"], "owner-b", "workspace-b"))
    other_owner_voice = copy.deepcopy(nila_voice)
    other_owner_voice["ownership"] = copy.deepcopy(OWNER_B)
    _, errs = asset_policy.resolve_voice_for_production(
        {other_owner_voice["voice_profile_id"]: other_owner_voice},
        v25_registries, "char-nila-001", "voice-nila-001",
        "owner-a", "workspace-a")
    check("B: voice owned by another user rejected (correct "
          "Character ID, mismatched ownership)",
          bool(errs), "; ".join(errs))
    other_ws_voice = copy.deepcopy(nila_voice)
    other_ws_voice["ownership"] = copy.deepcopy(OWNER_A_WS_B)
    _, errs = asset_policy.resolve_voice_for_production(
        {other_ws_voice["voice_profile_id"]: other_ws_voice},
        v25_registries, "char-nila-001", "voice-nila-001",
        "owner-a", "workspace-a")
    check("B: voice owned by another workspace rejected",
          bool(errs), "; ".join(errs))
    check("B: correct Character ID but mismatched ownership rejected "
          "(binding check with registry)",
          bool(check_voice_binding(
              {other_owner_voice["voice_profile_id"]: other_owner_voice},
              "char-nila-001", "voice-nila-001",
              character_registry=nila_registry)))
    _, errs = asset_policy.resolve_voice_for_production(
        v25_voice_registry, v25_registries, "char-nila-001",
        "voice-aria-001", "owner-a", "workspace-a")
    check("B: cross-character voice assignment rejected by the "
          "production resolver",
          bool(errs), "; ".join(errs))
    check("B: private voice export blocked without explicit "
          "authorization",
          bool(asset_policy.validate_private_voice_export(nila_voice)))
    check("B: private voice export blocked with partial "
          "authorization",
          bool(asset_policy.validate_private_voice_export(
              nila_voice, {"granted_by": "user",
                           "scope": "export voice"})))
    check("B: private voice export allowed with full explicit "
          "authorization",
          not asset_policy.validate_private_voice_export(
              nila_voice, {"granted_by": "owner-a",
                           "scope": "export voice-nila-001 for backup",
                           "explicit_authorisation": True}))
    check("B: private media not included in public release manifests "
          "(manifest check)",
          bool(asset_policy.validate_release_manifest_paths(
              ["characters/char-nila-001/voice-reference.mp3",
               "docs/07-character-registry.md"]))
          and not asset_policy.validate_release_manifest_paths(
              ["characters/README.md",
               "docs/07-character-registry.md"]))
    check("B: private data path traversal rejected",
          asset_policy.resolve_private_path(
              "characters", "../outside/secret.jpg")[1] != []
          and asset_policy.resolve_private_path(
              "characters", "/etc/passwd")[1] != []
          and asset_policy.resolve_private_path(
              "characters",
              "char-nila-001/../../etc/passwd")[1] != [])
    check("B: temporary asset use must NOT silently become permanent "
          "registration",
          not asset_policy.may_create_permanent_record(
              "TEMPORARY_ASSET_USE")
          and bool(register({}, load_fixture("temporary-asset-use.json"))))
    check("B: uploading an image never makes a character public "
          "(visibility stays private, sharing none, other owner "
          "still rejected)",
          nila["ownership"]["visibility"] == "private"
          and nila["ownership"]["sharing"] == "none"
          and bool(resolve_for_user(nila, "owner-b", "workspace-b")))
    check("B: visibility 'shared' without a sharing permission is "
          "rejected",
          bool(asset_policy.validate_ownership(
              {"owner_id": "owner-a", "workspace_id": "workspace-a",
               "visibility": "shared", "sharing": "none"})))
    check("B: ownership IDs must be opaque local identifiers (never "
          "a real name/email)",
          bool(asset_policy.validate_ownership(
              {"owner_id": "Owner A", "workspace_id": "workspace-a",
               "visibility": "private", "sharing": "none"}))
          and bool(asset_policy.validate_ownership(
              {"owner_id": "owner-a",
               "workspace_id": "someone@example.com",
               "visibility": "private", "sharing": "none"}))
          and not asset_policy.validate_ownership(
              copy.deepcopy(OWNER_A)))

    # --- CF-WO-P0-007 (C): conditional v2.5 voice-profile ----------
    # validation. Each case pins BOTH layers: the JSON Schema verdict
    # and the Python v2.5 validator verdict. For conditional fields
    # the schema is permissive by design (validator subset has no
    # if/then) — schema-pass + python-fail is the documented gap,
    # asserted explicitly, never silent.
    def check_voice_case(name, record, expect_schema_pass,
                         expect_python_pass, character=None):
        schema_errs, python_errs = validate_voice_profile_v25(
            record, character)
        check(f"C: {name} — schema verdict as expected",
              (not schema_errs) == expect_schema_pass,
              "; ".join(schema_errs))
        check(f"C: {name} — python v2.5 verdict as expected",
              (not python_errs) == expect_python_pass,
              "; ".join(python_errs))

    check_voice_case("valid v2.5 user-recorded (approved + granted "
                     "consent + matching ownership)",
                     copy.deepcopy(nila_voice), True, True,
                     character=nila)
    check_voice_case("valid v2.5 AI-generated (approved, provider+"
                     "model recorded, no-human-donor accurately "
                     "recorded)",
                     copy.deepcopy(aria_voice), True, True,
                     character=aria_character)
    check_voice_case("valid v2.3 legacy voice profile still passes",
                     load_fixture("voice-profile-valid.json"), True, True)
    bad = copy.deepcopy(nila_voice)
    del bad["voice_profile_id"]
    check_voice_case("missing Voice Profile ID", bad, True, False)
    bad = copy.deepcopy(nila_voice)
    del bad["source"]
    check_voice_case("missing source", bad, True, False)
    bad = copy.deepcopy(nila_voice)
    del bad["ownership"]
    check_voice_case("missing owner/workspace (documented subset gap: "
                     "schema cannot express conditional-required, "
                     "Python enforces it)",
                     bad, True, False)
    bad = copy.deepcopy(nila_voice)
    bad["audio_reference_assets"] = []
    check_voice_case("user recording without audio reference", bad,
                     True, False)
    bad = copy.deepcopy(nila_voice)
    bad["consent_status"] = "pending"
    bad["consent"] = {"granted": False, "granted_by": "parent",
                      "scope": "this series only", "source": "user"}
    check_voice_case("user recording without granted consent", bad,
                     True, False)
    bad = copy.deepcopy(aria_voice)
    del bad["provider"]
    check_voice_case("AI-generated voice without provider", bad,
                     True, False)
    bad = copy.deepcopy(aria_voice)
    del bad["approval_status"]
    check_voice_case("AI-generated voice without approval state", bad,
                     True, False)
    bad = copy.deepcopy(aria_voice)
    del bad["model"]
    del bad["model_version"]
    check_voice_case("AI-generated voice without model identification",
                     bad, True, False)
    bad = copy.deepcopy(aria_voice)
    bad["human_voice_donor"] = True
    bad["consent_status"] = "not-required"
    bad["consent"] = {"granted": False, "source": "user"}
    check_voice_case("unauthorized real-person voice sample (donor "
                     "voice claimed not-required, no consent)",
                     bad, True, False)
    bad = copy.deepcopy(aria_voice)
    del bad["human_voice_donor"]
    check_voice_case("consent_status 'not-required' without the "
                     "no-human-donor condition recorded",
                     bad, True, False)
    bad = copy.deepcopy(nila_voice)
    bad["approval_status"] = "pending"
    check_voice_case("status 'approved' without an approval record",
                     bad, True, False)
    bad = copy.deepcopy(nila_voice)
    bad["ownership"] = {"owner_id": "Owner A!",
                        "workspace_id": "workspace-a",
                        "visibility": "private", "sharing": "none"}
    check_voice_case("ownership owner_id is not an opaque local "
                     "identifier (both layers reject)", bad, False, False)
    bad = copy.deepcopy(nila_voice)
    bad["ownership"] = {"owner_id": "owner-a",
                        "workspace_id": "workspace-a",
                        "visibility": "shared", "sharing": "none"}
    check_voice_case("visibility 'shared' with sharing 'none'",
                     bad, True, False)
    bad = copy.deepcopy(nila_voice)
    bad["provider_transmission"] = {"disclosed": False,
                                    "provider": "external-voice-api",
                                    "data_use_scope": "synthesis",
                                    "approved_by": "user"}
    check_voice_case("provider transmission without disclosure",
                     bad, True, False)
    # Pending is a legitimate record state — but never an approved
    # production voice.
    pending = copy.deepcopy(aria_voice)
    pending["approval_status"] = "pending"
    pending["status"] = "draft"
    check_voice_case("pending profile is a valid record (not yet "
                     "approved)", pending, True, True)
    _, errs = asset_policy.resolve_voice_for_production(
        {pending["voice_profile_id"]: pending}, aria_registry,
        "char-aria-001", "voice-aria-001", "owner-a", "workspace-a")
    check("C: pending profile used as approved production voice is "
          "rejected",
          bool(errs), "; ".join(errs))
    _, errs = asset_policy.resolve_voice_for_production(
        v25_voice_registry, v25_registries, "char-aria-001",
        "voice-nila-001", "owner-a", "workspace-a")
    check("C: voice bound to another character rejected by the "
          "production resolver",
          bool(errs), "; ".join(errs))
    wrong_ws = copy.deepcopy(aria_voice)
    wrong_ws["ownership"] = copy.deepcopy(OWNER_A_WS_B)
    _, errs = asset_policy.resolve_voice_for_production(
        {wrong_ws["voice_profile_id"]: wrong_ws}, aria_registry,
        "char-aria-001", "voice-aria-001", "owner-a", "workspace-a")
    check("C: voice bound to another workspace rejected by the "
          "production resolver",
          bool(errs), "; ".join(errs))

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
