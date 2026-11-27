"""Consistency Frame P1 — character & voice identity resolution
(CF-WO-P1-004-R1-ADDENDUM-IDENTITY, Tasks B–O).

Deterministic, private-data-aware identity selection, resolution
and production binding. A user registers characters and their
approved voices once, selects them later by name or ID, and reuses
their exact identities across short-form and long-form videos.

This module is Layer B work: deterministic validation, resolution
and binding. It never performs creative reasoning (that is the AI
host's Layer A analysis, supplied as input), never calls a
provider, never generates media, never persists anything, and
never pretends a packet executed. It wraps — never duplicates —
the existing systems: ``resolve_character`` in
``runtime/production_orchestrator.py`` for the approved/task-local
binding, ``resolve_voice_for_production`` /
``validate_voice_profile`` / ``authorize_action`` in
``scripts/asset_policy.py`` for every voice authorization,
consent and approval check, and the P1-004 production store
(``runtime/production_store.py``) for persistence — the identity
snapshot rides inside the job dict, so the store carries it
without any second database.

Privacy boundary: this module loads the private character
registry only from the explicitly configured overlay
(``CONSISTENCY_FRAME_CHARACTERS``) or an explicit root. Records
are scoped to the requesting owner/workspace; records from
another workspace are never returned, and errors never leak
private registry contents — an unknown or inaccessible identity
is reported by the selector the caller supplied, never by
revealing what the registry contains. Only asset ids, relative
pointers and hashes travel into task packets and snapshots;
private media bytes never leave authorized private storage.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import re

from . import local_session  # noqa: F401  (session type, kept for callers)
from .task_compiler import (
    canonical_json,
    load_schema,
    schema_errors,
    sha256_hex,
    validate_instance,
)

IDENTITY_SCHEMA_VERSION = "2.5"

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
_LANG_RE = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")
_CONSENT_VALUES = ("granted", "pending", "denied", "not-required")

# The asset-role vocabulary the packet schemas accept. A
# registry record may carry a free-form role; the snapshot
# normalizes anything outside this vocabulary to "other"
# (the record itself is never rewritten).
_ASSET_ROLES = ("front", "profile", "three-quarter", "back",
                "detail", "expression", "pose", "outfit", "other")


def _packet_role(role):
    if isinstance(role, str) and role in _ASSET_ROLES:
        return role
    return "other"
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")

IDENTITY_MODES = (
    "SELECTED_REGISTERED_ONLY",
    "MIXED_REGISTERED_AND_NEW",
    "NEW_ONLY",
    "AUTO_MATCH_APPROVED",
)

CAST_CLASSES = (
    "VISIBLE_CHARACTER",
    "OFF_SCREEN_SPEAKER",
    "NARRATOR_OR_VOICE_OVER",
    "MENTIONED_ONLY",
)

PROVENANCE_VALUES = (
    "EXPLICIT_FROM_USER",
    "FROM_APPROVED_PROJECT_CANON",
    "INFERRED_FOR_PRODUCTION",
    "NEEDS_USER_DECISION",
)

_OVERLAY_ENV_VAR = "CONSISTENCY_FRAME_CHARACTERS"
_REGISTRY_FILENAMES = ("character.json", "character-registration.json")


class IdentityResolutionError(ValueError):
    """An identity resolution, selection or binding failed
    closed. Carries the structured ``errors`` list."""

    def __init__(self, errors):
        if isinstance(errors, str):
            errors = [errors]
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


# ---------------------------------------------------------------------------
# asset-policy loader (by file path, never by mutating sys.path)
# ---------------------------------------------------------------------------

_asset_policy = None


def _load_asset_policy():
    global _asset_policy
    if _asset_policy is None:
        helper_path = os.path.join(
            os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))),
            "scripts", "asset_policy.py")
        spec = importlib.util.spec_from_file_location(
            "consistency_frame_asset_policy", helper_path)
        if spec is None or spec.loader is None:
            raise IdentityResolutionError(
                "cannot load scripts/asset_policy.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _asset_policy = module
    return _asset_policy


def record_hash(record) -> str:
    """SHA-256 of the canonical JSON of one registry record."""
    return hashlib.sha256(
        canonical_json(record).encode("utf-8")).hexdigest()


def _safe_asset_id(path, seen=None) -> str:
    """A stable asset id derived from a relative asset path.
    Used only when a record carries no explicit asset_id: the
    basename (no extension), lowercased, non-alphanumerics
    folded to single hyphens. The path itself is always kept
    alongside, so the id is a pointer, never a replacement."""
    base = os.path.basename(str(path or ""))
    stem = base.rsplit(".", 1)[0] if "." in base else base
    cleaned = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
    if not cleaned:
        cleaned = "ref"
    if seen is not None:
        candidate = cleaned
        suffix = 2
        while candidate in seen:
            candidate = f"{cleaned}-{suffix}"
            suffix += 1
        cleaned = candidate
        seen.add(cleaned)
    return cleaned


def _is_id(value) -> bool:
    return isinstance(value, str) and bool(_ID_RE.match(value))


def _display_name(record):
    """The human-readable name of a character record, from either
    canonical shape (character.json ``name`` or
    character-registration.json ``display_name``)."""
    if not isinstance(record, dict):
        return None
    name = record.get("display_name") or record.get("name")
    return name if isinstance(name, str) and name else None


def _character_id_of(record):
    if not isinstance(record, dict):
        return None
    cid = record.get("character_id") or record.get("id")
    return cid if isinstance(cid, str) and cid else None


def _voice_ids_of_character(record):
    """All voice-profile ids bound to a character record, in
    priority order: the explicit default first, then the bound
    list. Handles both canonical shapes."""
    if not isinstance(record, dict):
        return []
    ordered: list[str] = []
    for key in ("default_voice_profile_id", "voice_profile_id"):
        value = record.get(key)
        if isinstance(value, str) and value and value not in ordered:
            ordered.append(value)
    for key in ("voice_profile_ids", "additional_voice_profile_ids"):
        for value in record.get(key) or []:
            if isinstance(value, str) and value and value not in ordered:
                ordered.append(value)
    return ordered


def _default_voice_id_of_character(record):
    """The character's default voice-profile id, or None. The
    canonical rule (character.json): the default is the first
    entry of voice_profile_ids. A registration's explicit
    default_voice_profile_id wins when present. A registration
    with only additional_voice_profile_ids and no explicit
    default has NO default — the first additional profile is
    not a default, so several eligible profiles without one
    must fail closed (Task I)."""
    if not isinstance(record, dict):
        return None
    explicit = record.get("default_voice_profile_id")
    if isinstance(explicit, str) and explicit:
        return explicit
    ids = record.get("voice_profile_ids") or []
    if ids and isinstance(ids[0], str) and ids[0]:
        return ids[0]
    return None


# ---------------------------------------------------------------------------
# Task B/C — identity-selection policy
# ---------------------------------------------------------------------------

def validate_identity_policy(policy) -> list[str]:
    """Policy-contract errors (empty list = valid).

    Checks the schema plus the semantic rules: selected and
    excluded ids are disjoint; NEW_ONLY selects nothing and
    allows new characters; MIXED requires at least one selected
    registered character and allows new ones;
    SELECTED_REGISTERED_ONLY allows no new characters; a record
    cannot be both the project default and a one-job override.
    """
    errors = schema_errors("identity-selection-policy", policy,
                           "identity_selection_policy")
    if not isinstance(policy, dict):
        return errors
    if policy.get("schema_version") != IDENTITY_SCHEMA_VERSION:
        errors.append("identity_selection_policy.schema_version must "
                      f"be '{IDENTITY_SCHEMA_VERSION}', got "
                      f"{policy.get('schema_version')!r}")
    mode = policy.get("mode")
    selected = policy.get("selected_character_ids") or []
    excluded = policy.get("excluded_character_ids") or []
    allow_new = policy.get("allow_new_task_local_characters")
    if isinstance(selected, list) and isinstance(excluded, list):
        overlap = sorted(set(selected) & set(excluded))
        if overlap:
            errors.append("identity_selection_policy: character(s) "
                          f"{overlap} cannot be both selected and "
                          "excluded")
    if mode == "NEW_ONLY":
        if selected:
            errors.append("identity_selection_policy: NEW_ONLY must "
                          "select no registered characters, got "
                          f"{selected}")
        if allow_new is not True:
            errors.append("identity_selection_policy: NEW_ONLY must "
                          "allow new task-local characters")
    if mode == "MIXED_REGISTERED_AND_NEW":
        if not selected:
            errors.append("identity_selection_policy: "
                          "MIXED_REGISTERED_AND_NEW needs at least "
                          "one selected registered character")
        if allow_new is not True:
            errors.append("identity_selection_policy: "
                          "MIXED_REGISTERED_AND_NEW must allow new "
                          "task-local characters")
    if mode == "SELECTED_REGISTERED_ONLY" and allow_new is True:
        errors.append("identity_selection_policy: "
                      "SELECTED_REGISTERED_ONLY must not allow new "
                      "task-local characters")
    if policy.get("is_project_default") is True \
            and policy.get("per_job_override") is True:
        errors.append("identity_selection_policy: a policy cannot be "
                      "both the project default and a one-job "
                      "override")
    return errors


# ---------------------------------------------------------------------------
# Task D — authorized private-registry loading
# ---------------------------------------------------------------------------

def _contained_path(root, *parts):
    """Join path components under a root and refuse any path
    whose realpath escapes the root (symlink containment)."""
    root_real = os.path.realpath(root)
    path = os.path.join(root, *parts)
    real = os.path.realpath(path)
    if real != root_real and not real.startswith(root_real + os.sep):
        raise IdentityResolutionError(
            "registry path escapes the configured overlay root")
    return path


def _registry_record_files(overlay_root):
    """Character registry record files under the overlay root,
    in deterministic order. Only ``character.json`` /
    ``character-registration.json`` files are read; a
    character.yaml-only entry is not loaded (the runtime is
    standard-library only and cannot parse YAML — the JSON
    record is the canonical machine-readable form)."""
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(overlay_root):
        dirnames.sort()
        for name in sorted(filenames):
            if name in _REGISTRY_FILENAMES:
                found.append(os.path.join(dirpath, name))
    index = os.path.join(overlay_root, "registry.json")
    if os.path.isfile(index):
        found.append(index)
    return sorted(found)


def load_authorized_character_registry(overlay_root=None, *,
                                       owner_id=None,
                                       workspace_id=None) -> dict:
    """Load the authorized private character registry.

    The root is an explicit argument, else the
    ``CONSISTENCY_FRAME_CHARACTERS`` environment variable. Every
    record is schema-validated and must carry an ``ownership``
    object; when an owner/workspace is supplied, records under a
    different owner or workspace are silently excluded (never
    leaked). A duplicate character id across files is an error
    naming only the id. A missing or unreadable root, an
    unreadable file, or an invalid record fails closed with a
    generic message that never reveals registry contents.

    Returns ``{character_id: record}`` (deep copies). The
    registry is data, not authorization: every use still goes
    through the P1-001 session and the P0 authorization
    boundary.
    """
    root = overlay_root or os.environ.get(_OVERLAY_ENV_VAR)
    if not isinstance(root, str) or not root:
        raise IdentityResolutionError(
            "no authorized character registry is configured: pass "
            "an overlay root or set CONSISTENCY_FRAME_CHARACTERS")
    if not os.path.isabs(root):
        raise IdentityResolutionError(
            "character registry root must be an absolute path")
    if os.path.islink(root) or not os.path.isdir(root):
        raise IdentityResolutionError(
            "character registry root is not a readable directory")
    registry: dict = {}
    for path in _registry_record_files(root):
        if os.path.islink(path):
            raise IdentityResolutionError(
                "character registry record is a symlink — refusing "
                "to read a symlinked record")
        _contained_path(root, os.path.relpath(path, root))
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError) as exc:
            raise IdentityResolutionError(
                "character registry record is unreadable: "
                f"{exc}") from exc
        records: list = []
        if isinstance(data, dict) and isinstance(
                data.get("characters"), list):
            records = data["characters"]
        elif isinstance(data, dict):
            records = [data]
        elif isinstance(data, list):
            records = data
        else:
            raise IdentityResolutionError(
                "character registry record is not an object")
        for record in records:
            if not isinstance(record, dict):
                raise IdentityResolutionError(
                    "character registry record is not an object")
            schema_name = ("character-registration"
                           if "character_id" in record
                           and "display_name" in record
                           else "character")
            errors = schema_errors(schema_name, record,
                                   "character_registry_record")
            if errors:
                raise IdentityResolutionError(errors)
            cid = _character_id_of(record)
            if not _is_id(cid):
                raise IdentityResolutionError(
                    "character registry record carries no valid "
                    "character id")
            if cid in registry:
                raise IdentityResolutionError(
                    f"duplicate character id {cid!r} in the "
                    "authorized character registry")
            ownership = record.get("ownership") or {}
            if owner_id is not None and ownership.get("owner_id") \
                    not in (None, owner_id):
                continue
            if workspace_id is not None and ownership.get(
                    "workspace_id") not in (None, workspace_id):
                continue
            registry[cid] = copy.deepcopy(record)
    return registry


def registry_snapshot_hash(registry) -> str:
    """Deterministic hash of the registry content used for a
    snapshot: canonical JSON of ``{character_id: record}``
    sorted by id."""
    ordered = {cid: registry[cid] for cid in sorted(registry)}
    return sha256_hex(canonical_json(ordered))


__all__ = [
    "IdentityResolutionError",
    "IDENTITY_MODES",
    "CAST_CLASSES",
    "IDENTITY_SCHEMA_VERSION",
    "record_hash",
    "validate_identity_policy",
    "load_authorized_character_registry",
    "registry_snapshot_hash",
]

# ---------------------------------------------------------------------------
# Task D — name/ID resolution + script cast extraction
# ---------------------------------------------------------------------------

def resolve_character_reference(*, selector, registry):
    """Resolve one character selector against an authorized
    registry mapping.

    ``selector`` carries ``character_id`` and/or ``name``. The
    unique id is the strongest selector; a unique name resolves
    within the authorized registry scope; duplicate names need
    the unique id; name + id must refer to exactly the same
    record; unknown ids never silently create a different
    identity; no speculative fuzzy matching — exact string
    equality only. Errors name only the selector the caller
    supplied, never registry contents.

    Returns ``{"character_id", "record", "matched_by",
    "resolution"}`` where ``resolution`` is the dict
    ``resolve_character`` in the orchestrator expects (the
    caller passes it there for the final binding).
    """
    if not isinstance(selector, dict):
        raise IdentityResolutionError("character selector is not an "
                                      "object")
    if not isinstance(registry, dict):
        raise IdentityResolutionError("character registry is not an "
                                      "object")
    character_id = selector.get("character_id")
    name = selector.get("name")
    if character_id is not None and not _is_id(character_id):
        raise IdentityResolutionError(
            f"character selector character_id {character_id!r} is "
            "not a valid id")
    if name is not None and (not isinstance(name, str)
                             or not name):
        raise IdentityResolutionError(
            "character selector name must be a non-empty string")
    if character_id is None and name is None:
        raise IdentityResolutionError(
            "character selector names neither a character id nor a "
            "name")
    if character_id is not None:
        record = registry.get(character_id)
        if record is None:
            raise IdentityResolutionError(
                f"unknown character id {character_id!r} in the "
                "authorized character registry")
        if name is not None and _display_name(record) != name:
            raise IdentityResolutionError(
                f"character name {name!r} and character id "
                f"{character_id!r} refer to different records")
        return {
            "character_id": character_id,
            "record": copy.deepcopy(record),
            "matched_by": "id-and-name" if name is not None else "id",
            "resolution": {
                "character_ref": name or character_id,
                "resolution": "approved",
                "registered_character_id": character_id,
                "provenance": "EXPLICIT_FROM_USER",
            },
        }
    matches = [cid for cid, record in registry.items()
               if _display_name(record) == name]
    if not matches:
        raise IdentityResolutionError(
            f"unknown character name {name!r} in the authorized "
            "character registry")
    if len(matches) > 1:
        raise IdentityResolutionError(
            f"character name {name!r} is ambiguous "
            f"({len(matches)} registered characters share it) — "
            "supply the unique character id")
    character_id = matches[0]
    return {
        "character_id": character_id,
        "record": copy.deepcopy(registry[character_id]),
        "matched_by": "name",
        "resolution": {
            "character_ref": name,
            "resolution": "approved",
            "registered_character_id": character_id,
            "provenance": "EXPLICIT_FROM_USER",
        },
    }


def resolve_project_identity_policy(policy, *, registry):
    """Resolve an identity-selection policy against an
    authorized registry.

    Validates the policy (schema + semantics + approval), resolves
    every selected id, enforces every exclusion, and enforces the
    mode: SELECTED_REGISTERED_ONLY resolves exactly the selected
    ids; NEW_ONLY resolves none (registry selection is disabled);
    AUTO_MATCH_APPROVED resolves the selected ids and leaves the
    rest to per-name auto-matching at cast-resolution time.
    Returns the resolved selection (records deep-copied) plus the
    registry snapshot hash the resolution was built from.
    """
    errors = validate_identity_policy(policy)
    if errors:
        raise IdentityResolutionError(errors)
    if not isinstance(registry, dict):
        raise IdentityResolutionError("character registry is not an "
                                      "object")
    if policy.get("approval_status") != "approved":
        raise IdentityResolutionError(
            "identity policy "
            f"{policy.get('policy_id')!r} is not approved "
            f"(approval_status "
            f"{policy.get('approval_status')!r}) — an unapproved "
            "policy must not drive production")
    mode = policy["mode"]
    selected_ids = list(policy.get("selected_character_ids") or [])
    excluded_ids = list(policy.get("excluded_character_ids") or [])
    for excluded_id in excluded_ids:
        if excluded_id not in registry:
            raise IdentityResolutionError(
                f"excluded character id {excluded_id!r} is not in "
                "the authorized character registry")
    resolved: dict = {}
    if mode != "NEW_ONLY":
        for character_id in selected_ids:
            if character_id in excluded_ids:
                raise IdentityResolutionError(
                    f"character {character_id!r} cannot be both "
                    "selected and excluded")
            resolved[character_id] = resolve_character_reference(
                selector={"character_id": character_id},
                registry=registry)
    return {
        "policy_id": policy["policy_id"],
        "project_id": policy["project_id"],
        "mode": mode,
        "selected_character_ids": selected_ids,
        "excluded_character_ids": excluded_ids,
        "allow_new_task_local_characters": bool(
            policy.get("allow_new_task_local_characters")),
        "resolved": resolved,
        "registry_snapshot_version": policy.get(
            "registry_snapshot_version") or "unversioned",
        "registry_snapshot_hash": registry_snapshot_hash(registry),
        "provenance": policy.get("provenance"),
    }


def resolve_script_cast(script_contract, analysis, bundle=None, *,
                        policy_resolution=None):
    """Classify every distinct identity in a script/analysis
    into its cast class.

    Deterministic classification from structured inputs only —
    no natural-language inference. A character is VISIBLE when
    it appears in a scene's character_refs or a shot's
    character_ids; a narrator (role 'narrator' in the analysis
    resolutions) is NARRATOR_OR_VOICE_OVER unless it is also
    visible; a speaking identity that never appears is
    OFF_SCREEN_SPEAKER; an identity that appears nowhere except
    the resolutions is MENTIONED_ONLY. A name mentioned in
    dialogue is not automatically a visible character.

    Returns ``{character_ref: cast_class}`` keyed by script
    reference, plus ``{"by_character_id": {...}}`` for the
    resolved ids when a policy resolution is supplied.
    """
    refs: dict = {}
    if isinstance(script_contract, dict):
        for line in script_contract.get("dialogue") or []:
            if isinstance(line, dict) and line.get("character_id"):
                refs.setdefault(line["character_id"],
                                {"speaking": True})
    if isinstance(analysis, dict):
        for scene in analysis.get("scenes") or []:
            if not isinstance(scene, dict):
                continue
            for ref in scene.get("character_refs") or []:
                entry = refs.setdefault(ref, {})
                entry["visible"] = True
        for resolution in analysis.get("character_resolutions") or []:
            if not isinstance(resolution, dict):
                continue
            ref = resolution.get("character_ref")
            if not ref:
                continue
            entry = refs.setdefault(ref, {})
            role = str(resolution.get("role") or "").lower()
            if "narrator" in role:
                entry["narrator"] = True
            if resolution.get("registered_character_id"):
                entry["character_id"] = resolution[
                    "registered_character_id"]
            if resolution.get("proposal_id"):
                entry["proposal_id"] = resolution["proposal_id"]
    if isinstance(bundle, dict):
        shot_plan = bundle.get("shot_plan") or {}
        for shot in shot_plan.get("shots") or []:
            if not isinstance(shot, dict):
                continue
            for cid in shot.get("character_ids") or []:
                entry = refs.setdefault(cid, {})
                entry["visible"] = True
        perf_plan = bundle.get("performance_plan") or {}
        for line in perf_plan.get("lines") or []:
            if not isinstance(line, dict):
                continue
            cid = line.get("character_id")
            if not cid:
                continue
            entry = refs.setdefault(cid, {})
            if (line.get("speaking_state") or "speaking") \
                    != "listening":
                entry["speaking"] = True
    cast: dict = {}
    by_id: dict = {}
    for ref, info in sorted(refs.items()):
        if info.get("visible"):
            cast_class = "VISIBLE_CHARACTER"
        elif info.get("narrator"):
            cast_class = "NARRATOR_OR_VOICE_OVER"
        elif info.get("speaking"):
            cast_class = "OFF_SCREEN_SPEAKER"
        else:
            cast_class = "MENTIONED_ONLY"
        cast[ref] = cast_class
        cid = info.get("character_id")
        if cid:
            by_id[cid] = cast_class
    if policy_resolution is not None:
        excluded = set(policy_resolution.get(
            "excluded_character_ids") or [])
        for ref in list(cast):
            cid = refs.get(ref, {}).get("character_id")
            if ref in excluded or cid in excluded:
                raise IdentityResolutionError(
                    f"excluded character {ref!r} appears in the "
                    "script cast")
    return {"cast": cast, "by_character_id": by_id}


# ---------------------------------------------------------------------------
# Task I — voice profile resolution (selection only; the P0
# resolver in asset_policy.py performs every authorization,
# consent and approval check)
# ---------------------------------------------------------------------------

def resolve_character_voice(*, character_id, voice_registry,
                            character_registry,
                            requesting_owner_id,
                            requesting_workspace_id,
                            language=None, role=None,
                            preferred_voice_profile_id=None,
                            provider=None, commercial_use=False):
    """Resolve the voice profile for one speaking character.

    Selection: the character's bound profiles, filtered by
    exact language match (language-agnostic legacy profiles
    stay eligible only when no exact-language profile exists)
    and by role (a 'narration' role prefers a narration
    variant). Exactly one eligible profile resolves
    automatically; several eligible profiles resolve to the
    character's default when it is among them; otherwise the
    caller must make one clear selection — never a random
    pick, never another character's voice. A preferred id must
    belong to this character. The chosen profile is then passed
    to ``resolve_voice_for_production`` for the full P0 checks
    (character binding, ownership, requester identity,
    conditional validation, approval). Returns
    ``(voice_record_or_None, errors)``.
    """
    if not _is_id(character_id):
        return None, [f"character_id {character_id!r} is not a "
                      "valid id"]
    if not isinstance(voice_registry, dict):
        return None, ["voice registry is not an object"]
    if not isinstance(character_registry, dict):
        return None, ["character registry is not an object"]
    character = character_registry.get(character_id)
    if character is None:
        return None, [f"unknown character_id {character_id!r}"]
    candidate_ids = _voice_ids_of_character(character)
    if preferred_voice_profile_id is not None:
        if preferred_voice_profile_id not in candidate_ids:
            return None, [
                f"voice profile "
                f"{preferred_voice_profile_id!r} is not bound to "
                f"character {character_id!r} — a voice profile "
                "must never be borrowed from another character"]
        candidate_ids = [preferred_voice_profile_id]
    if not candidate_ids:
        return None, [f"character {character_id!r} has no bound "
                      "voice profile"]
    profiles = {}
    for pid in candidate_ids:
        record = voice_registry.get(pid)
        if record is None:
            return None, [f"unknown voice_profile_id {pid!r}"]
        profiles[pid] = record
    eligible = list(candidate_ids)
    if language is not None:
        exact = [pid for pid in eligible
                 if profiles[pid].get("language") == language]
        if exact:
            eligible = exact
        else:
            # No exact-language profile: language-agnostic
            # legacy profiles stay eligible; a profile in a
            # different language is excluded.
            eligible = [pid for pid in eligible
                        if not profiles[pid].get("language")]
    if role is not None and "narrat" in role.lower():
        narr = [pid for pid in eligible
                if "narrat" in str(
                    profiles[pid].get("use_scope") or "").lower()
                or "narrat" in str(
                    profiles[pid].get("tags") or "").lower()]
        if narr:
            eligible = narr
    if not eligible:
        return None, [f"character {character_id!r} has no eligible "
                      f"voice profile for language {language!r}"
                      + (f" and role {role!r}" if role else "")]
    if len(eligible) == 1:
        selected = eligible[0]
    else:
        default = _default_voice_id_of_character(character)
        if default in eligible:
            selected = default
        else:
            return None, [
                f"character {character_id!r} has "
                f"{len(eligible)} eligible voice profiles and no "
                "default among them — one clear selection is "
                "required"]
    if provider is not None and commercial_use:
        if provider.get("commercial_use_approved") is not True:
            return None, [
                "commercial production cannot use voice profile "
                f"{selected!r}: the intended provider does not "
                "approve commercial use"]
    asset_policy = _load_asset_policy()
    voice, errors = asset_policy.resolve_voice_for_production(
        voice_registry, character_registry, character_id, selected,
        requesting_owner_id, requesting_workspace_id,
        require_approved=True)
    if errors:
        return None, errors
    return voice, []


def voice_selection_for_character(*, character_id, voice_record,
                                  dialogue_line_ids=None,
                                  language=None):
    """The snapshot voice-selection entry for one character,
    from its resolved voice-profile record. The
    reference-audio asset id is derived deterministically
    from the authorized reference-audio path (voice records
    carry no explicit asset id); the path's SHA-256 is copied
    verbatim. The raw audio never leaves private storage."""
    if not isinstance(voice_record, dict):
        raise IdentityResolutionError("voice record is not an "
                                      "object")
    audio = voice_record.get("reference_audio") or {}
    audio_asset_id = audio.get("asset_id") or _safe_asset_id(
        audio.get("path") or voice_record.get("voice_profile_id")
        or character_id)
    language = language or voice_record.get("language")
    consent = voice_record.get("consent_status")
    if consent not in _CONSENT_VALUES:
        consent = None
    return {
        "character_id": character_id,
        "voice_profile_id": voice_record["voice_profile_id"],
        **({"dialogue_line_ids": list(dialogue_line_ids)}
           if dialogue_line_ids else {}),
        **({"language": language}
           if isinstance(language, str)
           and _LANG_RE.match(language) else {}),
        **({"reference_audio_asset_id": audio_asset_id}
           if audio.get("path") else {}),
        **({"reference_audio_sha256": audio["sha256"]}
           if audio.get("sha256") else {}),
        **({"approval_status": voice_record["approval_status"]}
           if voice_record.get("approval_status") else {}),
        **({"consent_status": consent} if consent else {}),
        **({"provider_voice_id": voice_record["provider_voice_id"]}
           if voice_record.get("provider_voice_id") else {}),
    }


# ---------------------------------------------------------------------------
# Task E/N — identity snapshot (build + validate + resume)
# ---------------------------------------------------------------------------

def _fixed_identity_reference(record) -> str:
    """Stable pointer for a character's fixed identity: the
    SHA-256 of the canonical JSON of its fixed identity (plus
    the prompt block when present). The approved reference is
    never silently replaced by a generated interpretation."""
    fixed = record.get("fixed_identity") or {}
    block = record.get("fixed_prompt_block")
    payload = {"fixed_identity": fixed}
    if isinstance(block, str) and block:
        payload["fixed_prompt_block"] = block
    return "fixed-identity:" + sha256_hex(canonical_json(payload))


def build_identity_snapshot(*, snapshot_id, job_id, project_id,
                            policy_resolution, voice_selections=None,
                            task_local_proposals=None,
                            approval_records=None,
                            cast_classes=None,
                            provenance="EXPLICIT_FROM_USER"):
    """Build the resolved identity snapshot for one job.

    ``policy_resolution`` is the return value of
    ``resolve_project_identity_policy``. ``voice_selections``
    is a list of ``{"character_id", "voice_profile_id",
    "dialogue_line_ids", "language", "reference_audio_asset_id",
    "reference_audio_sha256", "approval_status",
    "consent_status", "provider_voice_id"}`` entries (from
    ``resolve_character_voice``). ``cast_classes`` is the
    ``{character_ref: cast_class}`` map from
    ``resolve_script_cast`` (stored on the snapshot so the
    compiler can enforce non-visible cast classes even when
    the analysis omits them). ``task_local_proposals`` maps
    proposal_id to its validated proposal record. The snapshot
    freezes every resolved character's reference ids, hashes,
    model-sheet ref, expression mapping, wardrobe constraints
    and registry record version/hash at build time, and carries
    its own snapshot hash. Raises IdentityResolutionError on
    any invalid input; returns the validated snapshot dict.
    """
    if not _is_id(snapshot_id):
        raise IdentityResolutionError(
            f"snapshot_id {snapshot_id!r} is not a valid id")
    if not _is_id(job_id):
        raise IdentityResolutionError(
            f"job_id {job_id!r} is not a valid id")
    if not _is_id(project_id):
        raise IdentityResolutionError(
            f"project_id {project_id!r} is not a valid id")
    if not isinstance(policy_resolution, dict):
        raise IdentityResolutionError(
            "policy resolution is not an object")
    resolved = policy_resolution.get("resolved") or {}
    proposals = task_local_proposals or {}
    voice_map: dict = {}
    for selection in voice_selections or []:
        if not isinstance(selection, dict):
            raise IdentityResolutionError(
                "voice selection is not an object")
        # One selection per (character, language): a character
        # may speak Bengali in one line and English in another,
        # but the same language twice is a conflict.
        key = (selection.get("character_id"),
               selection.get("language"))
        if key in voice_map:
            raise IdentityResolutionError(
                f"character {key[0]!r} has more than one voice "
                f"selection for language {key[1]!r} in one snapshot")
        voice_map[key] = selection
    resolved_characters: list = []
    for character_id in sorted(resolved):
        entry = resolved[character_id]
        record = entry["record"]
        refs = []
        model_sheet = None
        seen_ids: set = set()
        for asset in record.get("reference_assets") or []:
            if isinstance(asset, dict) and asset.get("path"):
                refs.append({
                    "asset_id": asset.get("asset_id") or
                    _safe_asset_id(asset["path"], seen_ids),
                    "path": asset["path"],
                    **({"sha256": asset["sha256"]}
                       if asset.get("sha256") else {}),
                    **({"role": _packet_role(asset["role"])}
                       if asset.get("role") else {}),
                })
        canonical = record.get("canonical_reference_images") or []
        for asset in canonical:
            if isinstance(asset, dict) and asset.get("path"):
                refs.append({
                    "asset_id": asset.get("asset_id") or
                    _safe_asset_id(asset["path"], seen_ids),
                    "path": asset["path"],
                    **({"sha256": asset["sha256"]}
                       if asset.get("sha256") else {}),
                    **({"role": _packet_role(asset["role"])}
                       if asset.get("role") else {}),
                })
        sheet = record.get("model_sheet")
        if isinstance(sheet, dict) and sheet.get("path"):
            model_sheet = {
                "asset_id": sheet.get("asset_id") or
                _safe_asset_id(sheet["path"], seen_ids),
                "path": sheet["path"],
                **({"sha256": sheet["sha256"]}
                   if sheet.get("sha256") else {}),
            }
        expressions = []
        for asset in record.get("expression_pose_references") or []:
            if isinstance(asset, dict) and asset.get("path"):
                # The expression name comes from the asset path's
                # basename (the character-consistency skill's
                # expression-<name> file convention); the record
                # schema carries no separate expression-name field.
                stem = os.path.basename(
                    asset["path"]).rsplit(".", 1)[0]
                name = stem[len("expression-"):] \
                    if stem.startswith("expression-") else stem
                expressions.append({
                    "expression": name,
                    "asset_id": asset.get("asset_id") or
                    _safe_asset_id(asset["path"], seen_ids),
                    "path": asset["path"],
                    **({"sha256": asset["sha256"]}
                       if asset.get("sha256") else {}),
                })
        primary = None
        for asset in refs:
            if asset.get("role") == "front":
                primary = asset["asset_id"]
                break
        if primary is None and refs:
            primary = refs[0]["asset_id"]
        wardrobe = []
        features = record.get("features") or {}
        if isinstance(features, dict) and features.get("clothing"):
            wardrobe.append(str(features["clothing"]))
        ownership = record.get("ownership") or {}
        resolved_characters.append({
            "character_ref": entry["resolution"].get(
                "character_ref") or character_id,
            "resolution": "approved",
            "character_id": character_id,
            "reference_asset_ids": refs,
            **({"primary_reference_id": primary}
               if primary else {}),
            **({"model_sheet_reference": model_sheet}
               if model_sheet else {}),
            "fixed_identity_reference":
                _fixed_identity_reference(record),
            **({"fixed_prompt_block": record["fixed_prompt_block"]}
               if isinstance(record.get("fixed_prompt_block"), str)
               and record["fixed_prompt_block"] else {}),
            "expression_references": expressions,
            "wardrobe_constraints": wardrobe,
            "ownership_scope": {
                "owner_id": ownership.get("owner_id") or "unknown",
                "workspace_id": ownership.get("workspace_id")
                or "unknown",
            },
            "registry_record_version": int(
                record.get("version") or 1),
            "registry_record_hash": record_hash(record),
        })
    for proposal_id in sorted(proposals):
        proposal = proposals[proposal_id]
        if not isinstance(proposal, dict):
            raise IdentityResolutionError(
                f"task-local proposal {proposal_id!r} is not an "
                "object")
        refs = []
        seen_ref_ids: set = set()
        for asset_id in proposal.get("approved_reference_ids") or []:
            refs.append({"asset_id": _safe_asset_id(asset_id,
                                                    seen_ref_ids),
                         "path": asset_id})
        primary = refs[0]["asset_id"] if refs else None
        resolved_characters.append({
            "character_ref": proposal.get("character_ref")
            or proposal_id,
            "resolution": "task-local-proposal",
            # The proposal id IS the stable job-scoped identity
            # for a task-local character.
            "character_id": proposal_id,
            "proposal_id": proposal_id,
            "reference_asset_ids": refs,
            **({"primary_reference_id": primary}
               if primary else {}),
            "fixed_identity_reference":
                "task-local-proposal:" + proposal_id,
            "expression_references": [],
            "wardrobe_constraints": [],
            "ownership_scope": {
                "owner_id": "job-local",
                "workspace_id": "job-local",
            },
            "registry_record_version": 1,
            "registry_record_hash": record_hash(proposal),
        })
    snapshot = {
        "schema_version": IDENTITY_SCHEMA_VERSION,
        "snapshot_id": snapshot_id,
        "job_id": job_id,
        "project_id": project_id,
        "identity_lock_version": 1,
        "registry_snapshot_version": policy_resolution.get(
            "registry_snapshot_version") or "unversioned",
        "registry_snapshot_hash": policy_resolution.get(
            "registry_snapshot_hash") or "0" * 64,
        "mode": policy_resolution["mode"],
        "selected_character_ids": list(
            policy_resolution.get("selected_character_ids") or []),
        "excluded_character_ids": list(
            policy_resolution.get("excluded_character_ids") or []),
        "resolved_characters": resolved_characters,
        "task_local_proposal_ids": sorted(proposals),
        "voice_selections": [
            {k: selection[k] for k in (
                "character_id", "voice_profile_id",
                "dialogue_line_ids", "language",
                "reference_audio_asset_id",
                "reference_audio_sha256", "approval_status",
                "consent_status", "provider_voice_id")
             if k in selection}
            for selection in (voice_selections or [])],
        "approval_records": list(approval_records or []),
        "provenance": provenance,
    }
    if cast_classes:
        # A list of entries, not a free-form map: the repo's schema
        # style requires every object schema to carry non-empty
        # properties with additionalProperties false. Sorted by
        # character_ref so the snapshot hash is deterministic.
        snapshot["cast_classes"] = [
            {"character_ref": ref, "cast_class": cls}
            for ref, cls in sorted(cast_classes.items())]
    snapshot["snapshot_hash"] = sha256_hex(
        canonical_json({k: v for k, v in snapshot.items()
                        if k != "snapshot_hash"}))
    errors = schema_errors("identity-snapshot", snapshot,
                           "identity_snapshot")
    if errors:
        raise IdentityResolutionError(errors)
    return snapshot


def validate_identity_snapshot(snapshot, *, registry=None,
                               voice_registry=None) -> list[str]:
    """Snapshot errors (empty list = valid).

    Always checks the schema and the snapshot hash. When
    registries are supplied, revalidates every resolved
    character against the current registry record (record hash
    must match; every reference asset path + sha must still
    match) and every voice selection against the current voice
    record (profile must still belong to the character and its
    reference-audio sha must still match). A missing asset or
    a hash mismatch is an error — never a silent rebuild.
    """
    errors = schema_errors("identity-snapshot", snapshot,
                           "identity_snapshot")
    if not isinstance(snapshot, dict):
        return errors
    stored = snapshot.get("snapshot_hash")
    if isinstance(stored, str) and _SHA_RE.match(stored):
        recomputed = sha256_hex(canonical_json(
            {k: v for k, v in snapshot.items()
             if k != "snapshot_hash"}))
        if recomputed != stored:
            errors.append("identity_snapshot.snapshot_hash does "
                          "not match the recomputed snapshot hash")
    if registry is not None:
        if not isinstance(registry, dict):
            errors.append("identity snapshot validation needs a "
                          "character registry object")
            return errors
        for entry in snapshot.get("resolved_characters") or []:
            if not isinstance(entry, dict):
                continue
            if entry.get("resolution") != "approved":
                continue
            cid = entry.get("character_id")
            record = registry.get(cid)
            if record is None:
                errors.append("identity snapshot character "
                              f"{cid!r} is no longer in the "
                              "authorized registry")
                continue
            if record_hash(record) != entry.get(
                    "registry_record_hash"):
                errors.append("identity snapshot character "
                              f"{cid!r} registry record changed "
                              "after the snapshot was approved")
                continue
            by_path = {}
            for asset in record.get("reference_assets") or []:
                if isinstance(asset, dict) and asset.get("path"):
                    by_path[asset["path"]] = asset
            for asset in record.get(
                    "canonical_reference_images") or []:
                if isinstance(asset, dict) and asset.get("path"):
                    by_path[asset["path"]] = asset
            for ref in entry.get("reference_asset_ids") or []:
                current = by_path.get(ref.get("path"))
                if current is None:
                    errors.append("identity snapshot character "
                                  f"{cid!r} reference asset "
                                  f"{ref.get('path')!r} is no "
                                  "longer in the registry")
                elif ref.get("sha256") and current.get("sha256") \
                        and ref["sha256"] != current["sha256"]:
                    errors.append("identity snapshot character "
                                  f"{cid!r} reference asset "
                                  f"{ref.get('path')!r} hash no "
                                  "longer matches the registry")
    if voice_registry is not None:
        if not isinstance(voice_registry, dict):
            errors.append("identity snapshot validation needs a "
                          "voice registry object")
            return errors
        for selection in snapshot.get("voice_selections") or []:
            if not isinstance(selection, dict):
                continue
            pid = selection.get("voice_profile_id")
            record = voice_registry.get(pid)
            if record is None:
                errors.append("identity snapshot voice profile "
                              f"{pid!r} is no longer in the voice "
                              "registry")
                continue
            if record.get("character_id") != selection.get(
                    "character_id"):
                errors.append("identity snapshot voice profile "
                              f"{pid!r} no longer belongs to "
                              f"character "
                              f"{selection.get('character_id')!r}")
            audio = record.get("reference_audio") or {}
            if selection.get("reference_audio_sha256") \
                    and audio.get("sha256") \
                    and selection["reference_audio_sha256"] \
                    != audio["sha256"]:
                errors.append("identity snapshot voice profile "
                              f"{pid!r} reference audio hash no "
                              "longer matches the registry")
    return errors


def validate_resumed_identity(job, *, registry,
                              voice_registry=None) -> list[str]:
    """Revalidate a stored job's identity snapshot on resume.

    No snapshot on the job means no identity state to check.
    A present snapshot is validated against the CURRENT
    registries: a changed record, a missing asset or a hash
    mismatch fails the resume. This is called by the caller
    after ``resume_production_job`` returns the job, under the
    new active session.
    """
    if not isinstance(job, dict):
        return ["job is not an object"]
    snapshot = job.get("identity_snapshot")
    if snapshot is None:
        return []
    return validate_identity_snapshot(
        snapshot, registry=registry, voice_registry=voice_registry)


__all__ += [
    "resolve_character_reference",
    "resolve_project_identity_policy",
    "resolve_script_cast",
    "resolve_character_voice",
    "build_identity_snapshot",
    "validate_identity_snapshot",
    "validate_resumed_identity",
]

# ---------------------------------------------------------------------------
# Tasks F/G/H/J — packet bindings (built by the task compiler
# from a validated snapshot; this module owns the binding shape)
# ---------------------------------------------------------------------------

def _angle_role_for_shot(shot) -> str:
    """The reference angle role a shot needs, from its framing
    and camera angle. Front for close/front shots, profile for
    side shots, three-quarter otherwise."""
    text = " ".join(str(shot.get(key) or "")
                    for key in ("framing", "shot_size", "angle",
                                "camera_angle")).lower()
    if "close" in text or "front" in text:
        return "front"
    if "profile" in text or "side" in text:
        return "profile"
    return "three-quarter"


def _expression_ref_for_character(entry, lines, character_id):
    """The expression reference for a character in one shot,
    from the first speaking line's emotion in that shot. Falls
    back to the neutral expression reference when the emotion
    has no library entry, and to None when the library has
    neither."""
    emotion = None
    for line in lines or []:
        if not isinstance(line, dict):
            continue
        if line.get("character_id") != character_id:
            continue
        emotion = (line.get("emotion")
                   or line.get("primary_emotion")
                   or line.get("facial_expression"))
        if emotion:
            break
    refs = entry.get("expression_references") or []
    if not refs:
        return None
    if emotion:
        for ref in refs:
            if str(ref.get("expression") or "").lower() \
                    == str(emotion).lower():
                return ref
    for ref in refs:
        if str(ref.get("expression") or "").lower() == "neutral":
            return ref
    return None


def identity_binding_for_character(*, character_id, snapshot,
                                   role="three-quarter",
                                   expression=None):
    """One structured identity binding for one character,
    from a validated snapshot. The binding names the canonical
    reference asset ids, the primary identity reference, the
    model sheet, the angle-matched reference for ``role``
    (``front`` / ``three-quarter`` / ``profile``), the
    expression reference when ``expression`` is supplied, the
    fixed-identity pointer, the primary reference SHA-256,
    the approved wardrobe variation and the ownership scope.
    An excluded character, or a character with no resolved
    snapshot entry, fails closed."""
    if not isinstance(snapshot, dict):
        raise IdentityResolutionError("identity snapshot is not an "
                                      "object")
    if character_id in set(snapshot.get(
            "excluded_character_ids") or []):
        raise IdentityResolutionError(
            f"excluded character {character_id!r} cannot receive an "
            "identity binding")
    entry = None
    for candidate in snapshot.get("resolved_characters") or []:
        if not isinstance(candidate, dict):
            continue
        if candidate.get("character_id") == character_id \
                or candidate.get("character_ref") == character_id:
            entry = candidate
            break
    if entry is None:
        raise IdentityResolutionError(
            f"character {character_id!r} has no resolved entry in "
            "the identity snapshot")
    refs = entry.get("reference_asset_ids") or []
    if not refs:
        raise IdentityResolutionError(
            f"character {character_id!r} has no approved reference "
            "assets in the identity snapshot")
    primary = entry.get("primary_reference_id")
    primary_ref = None
    for asset in refs:
        if asset.get("asset_id") == primary:
            primary_ref = asset
            break
    if primary_ref is None:
        primary_ref = refs[0]
    angle_ref = None
    for asset in refs:
        if asset.get("role") == role:
            angle_ref = asset
            break
    if angle_ref is None:
        angle_ref = primary_ref
    return {
        "character_id": entry.get("character_id")
        or entry.get("character_ref"),
        "character_ref": entry.get("character_ref"),
        "reference_asset_ids": copy.deepcopy(refs),
        **({"primary_reference_id": primary} if primary else {}),
        **({"model_sheet_reference": copy.deepcopy(
            entry["model_sheet_reference"])}
           if entry.get("model_sheet_reference") else {}),
        **({"angle_matched_reference": copy.deepcopy(angle_ref)}
           if angle_ref else {}),
        **({"expression_reference": copy.deepcopy(expression)}
           if expression else {}),
        "fixed_identity_reference": entry.get(
            "fixed_identity_reference") or "",
        **({"reference_sha256": primary_ref["sha256"]}
           if primary_ref.get("sha256") else {}),
        **({"wardrobe_variation": "; ".join(
            entry.get("wardrobe_constraints") or [])}
           if entry.get("wardrobe_constraints") else {}),
        **({"ownership_scope": copy.deepcopy(
            entry["ownership_scope"])}
           if entry.get("ownership_scope") else {}),
    }


def identity_bindings_for_shot(*, shot, snapshot, lines=None,
                               analysis=None):
    """Structured identity bindings for one image/video shot.

    One binding per visible registered or task-local character
    in the shot — never a merged reference, never an inferred
    face. A character whose cast class is not VISIBLE_CHARACTER
    (narrator, off-screen speaker, mentioned-only) receives no
    image/video binding. An excluded character in a shot, a
    character outside its declared scene list, or a shot
    character with no resolved snapshot entry all fail closed.

    Returns ``(bindings, missing)``: ``bindings`` is the list of
    binding entries; ``missing`` names shot characters that
    could not be bound (the compiler turns a non-empty missing
    list into a compile error).
    """
    if not isinstance(shot, dict):
        raise IdentityResolutionError("shot is not an object")
    if not isinstance(snapshot, dict):
        raise IdentityResolutionError("identity snapshot is not an "
                                      "object")
    excluded = set(snapshot.get("excluded_character_ids") or [])
    by_id: dict = {}
    by_ref: dict = {}
    for entry in snapshot.get("resolved_characters") or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("character_id"):
            by_id[entry["character_id"]] = entry
        if entry.get("character_ref"):
            by_ref[entry["character_ref"]] = entry
    cast_by_ref: dict = {}
    scene_ids_by_ref: dict = {}
    if isinstance(analysis, dict):
        for resolution in analysis.get("character_resolutions") or []:
            if not isinstance(resolution, dict):
                continue
            ref = resolution.get("character_ref")
            if not ref:
                continue
            if resolution.get("cast_class"):
                cast_by_ref[ref] = resolution["cast_class"]
            if resolution.get("scene_ids"):
                scene_ids_by_ref[ref] = set(
                    resolution["scene_ids"])
    # Fallback cast list from the snapshot (derived at bundle
    # time); the analysis resolutions win when they name one.
    for entry in snapshot.get("cast_classes") or []:
        if not isinstance(entry, dict):
            continue
        ref = entry.get("character_ref")
        cls = entry.get("cast_class")
        if ref and cls:
            cast_by_ref.setdefault(ref, cls)
    role = _angle_role_for_shot(shot)
    scene_id = shot.get("scene_id")
    bindings: list = []
    missing: list = []
    for character_id in shot.get("character_ids") or []:
        if character_id in excluded:
            raise IdentityResolutionError(
                f"excluded character {character_id!r} appears in "
                f"shot {shot.get('shot_id')!r}")
        entry = by_id.get(character_id) or by_ref.get(character_id)
        if entry is None:
            missing.append(character_id)
            continue
        ref = entry.get("character_ref")
        cast_class = cast_by_ref.get(ref)
        if cast_class is not None \
                and cast_class != "VISIBLE_CHARACTER":
            raise IdentityResolutionError(
                f"character {ref!r} is {cast_class} and must not "
                "receive an image/video binding")
        allowed_scenes = scene_ids_by_ref.get(ref)
        if allowed_scenes is not None and scene_id is not None \
                and scene_id not in allowed_scenes:
            raise IdentityResolutionError(
                f"character {ref!r} is not in scene "
                f"{scene_id!r} per its scene list")
        try:
            bindings.append(identity_binding_for_character(
                character_id=character_id, snapshot=snapshot,
                role=role,
                expression=_expression_ref_for_character(
                    entry, lines, character_id)))
        except IdentityResolutionError:
            missing.append(character_id)
    return bindings, missing


def voice_binding_for_line(*, line, snapshot, voice_record=None):
    """The exact voice binding for one speaking dialogue-line
    task, from the job's identity snapshot (and the resolved
    voice-profile record when the caller supplies it). The
    binding names the profile, the authorized reference-audio
    asset id + SHA-256, language, accent, delivery and
    ownership/consent evidence. The raw audio stays in
    authorized private storage; only the asset id and hash
    travel in the packet."""
    if not isinstance(line, dict):
        raise IdentityResolutionError("dialogue line is not an "
                                      "object")
    if not isinstance(snapshot, dict):
        raise IdentityResolutionError("identity snapshot is not an "
                                      "object")
    character_id = line.get("character_id")
    line_id = line.get("line_id")
    # The line may name the character by script ref; resolve to
    # the registered id (or the job-scoped proposal id) first so
    # the binding always carries a valid identity.
    ref_to_id = {}
    for entry in snapshot.get("resolved_characters") or []:
        if isinstance(entry, dict) and entry.get("character_ref") \
                and entry.get("character_id"):
            ref_to_id[entry["character_ref"]] = entry["character_id"]
    canonical_id = ref_to_id.get(character_id, character_id)
    # A character may hold one selection per language: prefer
    # the selection matching this line's language, and fall back
    # to the character's only selection when the line names none.
    line_language = line.get("language")
    selection = None
    first_for_character = None
    for entry in snapshot.get("voice_selections") or []:
        if isinstance(entry, dict) \
                and entry.get("character_id") == canonical_id:
            if first_for_character is None:
                first_for_character = entry
            if line_language is not None \
                    and entry.get("language") == line_language:
                selection = entry
                break
    if selection is None:
        selection = first_for_character
    if selection is None:
        raise IdentityResolutionError(
            f"speaking line {line_id!r} (character "
            f"{character_id!r}) has no resolved voice selection "
            "in the identity snapshot")
    record = voice_record or {}
    voice = line.get("voice") or {}
    language = line.get("language") or selection.get("language")
    if not (isinstance(language, str)
            and _LANG_RE.match(language)):
        language = None
    consent_ref = (
        f"voice-profile:{selection['voice_profile_id']} "
        f"approved={selection.get('approval_status')}")
    if selection.get("consent_status"):
        consent_ref += f" consent={selection['consent_status']}"
    binding = {
        "character_id": canonical_id,
        "voice_profile_id": selection["voice_profile_id"],
        **({"dialogue_line_id": line_id} if line_id else {}),
        **({"language": language} if language else {}),
        **({"accent": record["accent"]}
           if record.get("accent") else {}),
        **({"vocal_characteristics":
            record["vocal_characteristics"]}
           if record.get("vocal_characteristics") else {}),
        **({"pitch_range": record["pitch_range"]}
           if record.get("pitch_range") else {}),
        **({"speaking_pace": record["speaking_pace"]}
           if record.get("speaking_pace") else {}),
        **({"pronunciation_preferences":
            record["pronunciation_preferences"]}
           if record.get("pronunciation_preferences") else {}),
        **({"emotional_delivery": line.get("emotion")
            or line.get("primary_emotion")}
           if line.get("emotion") or line.get("primary_emotion")
           else {}),
        **({"pauses": voice["pauses"]}
           if voice.get("pauses") else {}),
        **({"reference_audio_asset_id":
            selection["reference_audio_asset_id"]}
           if selection.get("reference_audio_asset_id") else {}),
        **({"reference_audio_sha256":
            selection["reference_audio_sha256"]}
           if selection.get("reference_audio_sha256") else {}),
        **({"provider_voice_id":
            selection.get("provider_voice_id")
            or record.get("provider_voice_id")}
           if selection.get("provider_voice_id")
           or record.get("provider_voice_id") else {}),
        **({"model": record["model"]}
           if record.get("model") else {}),
        **({"model_version": record["model_version"]}
           if record.get("model_version") else {}),
        **({"seed": record["seed"]}
           if isinstance(record.get("seed"), int) else {}),
        "ownership_consent_ref": consent_ref,
    }
    packet_schema = load_schema("task-packet.json")
    voice_errors: list[str] = []
    validate_instance(
        packet_schema["properties"]["voice_binding"], binding,
        "voice_binding", voice_errors)
    if voice_errors:
        raise IdentityResolutionError(voice_errors)
    return binding


__all__ += [
    "voice_selection_for_character",
    "identity_binding_for_character",
    "identity_bindings_for_shot",
    "voice_binding_for_line",
]
