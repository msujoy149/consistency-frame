#!/usr/bin/env python3
"""Consistency Frame P1 — deterministic Script-to-Performance runtime
(CF-WO-P1-003).

This module is the third P1 runtime component: it receives a structured
source ScriptContract, an approved production context and the structured
analysis drafts prepared by the AI reasoning layer, and it validates,
binds and assembles them into final schema-valid Scene, Shot and
Performance Plans plus the Script-to-Performance binding record. It is
standard-library only: it never reads a private project asset, never
contacts a provider, never generates media, never persists anything,
and never runs an LLM.

Two layers, kept separate (see
``docs/runtime/SCRIPT_TO_PERFORMANCE_RUNTIME.md``):

- Layer A — AI reasoning / script analysis: the active AI agent
  analyses the supplied script with the canonical Consistency Frame
  skills and prepares structured draft data (scenes, beats, shots,
  dialogue-level performance). That creative analysis is NOT done
  here and is never faked with deterministic heuristics.
- Layer B — this deterministic runtime: it validates the drafts
  against the canonical schemas and the P0 semantic rules, checks
  every cross-reference between the four records, enforces verbatim
  dialogue preservation (with strictly authorised per-line rewrites
  only), and assembles the final bundle with a deterministic SHA-256
  fingerprint.

Rules enforced here (all grounded in the canonical schemas and the
P0 semantic checks, never in prose):

- Session and routing: an exact active P1-001 ``LocalSession`` and
  a valid, ready P1-002 routing plan with
  ``intent_mode == GENERATE_FROM_SCRIPT`` whose session ID matches
  the exact active session. A missing, forged, copied, expired or
  closed session fails closed; a blocked or invalid routing plan is
  refused. The router's selected skills and decisions are preserved
  — this module never selects or invents a skill.
- Dialogue preservation: ``dialogue_mode = VERBATIM_SCRIPT`` by
  default; the user's original dialogue is preserved exactly,
  character for character. Every source dialogue line maps to
  exactly one Performance Plan line, in the same order. A rewrite
  is valid only when the caller explicitly supplies
  ``dialogue_rewrite_authorised: True`` (an actual boolean), the
  plan uses ``SCRIPT_EDIT_REQUESTED``, the exact line has
  ``rewrite_permitted: true``, the original text stays in
  ``dialogue.text`` and any changed version lives separately in
  ``rewritten_text``. A plan-level rewrite request alone never
  authorises a rewrite.
- Cross-plan integrity: the four final records form one coherent
  production timeline — root IDs match the actual plan IDs,
  project IDs agree wherever supplied, scene/shot/beat IDs resolve,
  performance line IDs match source dialogue line IDs exactly,
  character references resolve from the supplied project/script
  context, voice bindings and reaction holds reference valid line
  and shot IDs, and repeated subject IDs never carry contradictory
  identity or production-medium information. The production
  dimensions (representation, rendering style, source media, motion
  method, subject kind, articulation target, live-action provenance)
  stay independent — they are never collapsed into one
  animation-type field. Human mouth/lip articulation is never
  applied to an animal or creature; when a speaking subject's
  anatomy cannot be established, the runtime fails closed rather
  than guessing.
- P0 semantics: CF-P0-PERF-001 (emotion-intensity bounds),
  CF-P0-PERF-002 (strictly positive durations), CF-P0-PERF-003
  (canonical emotion taxonomy), CF-P0-PERF-004 (non-verbal event
  requirements) and CF-P0-PERF-005 (line-level dialogue rewrite
  permission) are all preserved.
- Nullability parity (P1-002-R1-R3 approach): an optional field
  omitted from a record is not equivalent to a present field
  containing ``null`` when the schema disallows null — explicit
  nulls are rejected with an error naming the field.
- Determinism: no random identifiers, no generated timestamps,
  no silent field removal, no input mutation, no nondeterministic
  sorting. The bundle hash is the SHA-256 of the canonical JSON of
  the bundle without the hash field itself.

Session handling: the builder requires an exact active
:class:`runtime.local_session.LocalSession`, verified with the
P1-001 verifier. Actor identity comes only from that session —
never from caller-provided owner or workspace strings.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re

from . import local_session
from . import skill_router

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{2,63}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCHEMA_DIR = os.path.join(_REPO_ROOT, "schemas")

# Canonical schemas consumed by this runtime (P0 contracts, v2.3–v2.5).
# They are read, never modified; a schema contradiction is reported,
# never silently redesigned.
_SCRIPT_CONTRACT_SCHEMA = "script-contract.json"
_SCRIPT_TO_PERFORMANCE_SCHEMA = "script-to-performance.json"
_SCENE_PLAN_SCHEMA = "scene-plan.json"
_SHOT_PLAN_SCHEMA = "shot-plan.json"
_PERFORMANCE_PLAN_SCHEMA = "performance-plan.json"
_PRODUCTION_PROFILE_SCHEMA = "production-profile.json"

# Draft keys the builder accepts. scene_plan, shot_plan and
# performance_plan are required; the rest are optional.
_DRAFT_REQUIRED_KEYS = ("scene_plan", "shot_plan", "performance_plan")
_DRAFT_OPTIONAL_KEYS = ("audio_plan", "editing_plan",
                       "character_voice_binding",
                       "character_voice_bindings")
_DRAFT_KEYS = frozenset(_DRAFT_REQUIRED_KEYS + _DRAFT_OPTIONAL_KEYS)

# Production dimensions that must agree for one subject wherever they
# are supplied (scene subjects, shot subjects, profile overrides).
_SUBJECT_DIMENSION_FIELDS = (
    "subject_kind", "representation", "rendering_style", "source_media",
    "articulation_target", "is_live_action_footage", "species",
)

# Articulation allowed per subject kind (P0, tests/test_schemas.py
# ARTICULATION_BY_SUBJECT_KIND). Human lip movement applies only to
# human / digital-human subjects (anthropomorphic and mixed entries
# carry their own vocabulary in the canonical table).
_ARTICULATION_BY_SUBJECT_KIND = {
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
_BIRD_WORDS = ("bird", "parrot", "crow", "owl", "eagle", "sparrow",
               "pigeon", "duck", "chicken", "songbird")
# Generated media (P0, tests/test_schemas.py): a generated subject is
# NEVER live-action footage.
_GENERATED_MEDIA = {"ai-digital-human", "ai-digital-creature",
                    "3d-cgi-rigged", "2d-drawn-vector"}
_GENERATED_STYLES = {"photorealistic-digital-human",
                     "photorealistic-digital-animal-creature",
                     "photorealistic-3d-cgi", "stylized-3d",
                     "semi-realistic-3d", "flat-2d-vector",
                     "hand-drawn-2d", "illustrated-2d", "anime",
                     "cartoon-2d"}

# Bundle format version (the in-memory bundle itself has no canonical
# schema; this names the assembly format, not a plan schema version).
BUNDLE_SCHEMA_VERSION = "2.5"


class ScriptToPerformanceError(ValueError):
    """Raised when a Script-to-Performance input or bundle fails
    validation. Carries the structured ``errors`` list; the caller
    never receives a partially valid production bundle as a success.
    """

    def __init__(self, errors):
        if isinstance(errors, str):
            errors = [errors]
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


# ---------------------------------------------------------------------------
# Canonical JSON + hashing
# ---------------------------------------------------------------------------

def _canonical_json(value) -> str:
    """Canonical JSON serialisation: sorted keys, tight separators,
    unicode preserved. The same value always serialises the same way,
    so hashes are deterministic across runs and platforms."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def script_to_performance_hash(bundle: dict) -> str:
    """Deterministic SHA-256 bundle fingerprint: the canonical JSON of
    the bundle without the ``bundle_hash`` field itself. The hash
    covers the validated script, profile, routing-plan reference,
    session context and all four final records, so any change to the
    validated inputs changes the hash."""
    if not isinstance(bundle, dict):
        raise ScriptToPerformanceError("bundle is not an object")
    payload = {key: value for key, value in bundle.items()
               if key != "bundle_hash"}
    return _sha256_hex(_canonical_json(payload))


# ---------------------------------------------------------------------------
# Restricted JSON-Schema-subset validation (mirrors
# scripts/validate-repo.py::validate_instance semantics exactly, so the
# runtime and the repo validator agree on every record)
# ---------------------------------------------------------------------------

_SCHEMA_CACHE: dict[str, dict] = {}


def _load_schema(name: str) -> dict:
    """Load a canonical schema from schemas/. The file is read, never
    modified; a missing or unreadable schema fails closed."""
    if name not in _SCHEMA_CACHE:
        path = os.path.join(_SCHEMA_DIR, name)
        try:
            with open(path, encoding="utf-8") as handle:
                _SCHEMA_CACHE[name] = json.load(handle)
        except (OSError, ValueError) as exc:
            raise ScriptToPerformanceError(
                f"canonical schema {name} cannot be loaded: {exc}")
    return _SCHEMA_CACHE[name]


def _validate_instance(schema: dict, value, path: str,
                       errors: list[str]) -> None:
    """Minimal instance validation against the supported subset:
    type (with bool excluded from integer/number), enum, pattern
    (re.search), minLength, minimum/maximum/exclusiveMinimum,
    required, additionalProperties==False, minItems, items. An
    explicit null fails the type check wherever the schema type does
    not include null — an omitted optional field is never equivalent
    to a present null."""
    schema_type = schema.get("type")
    type_ok = {
        "object": isinstance(value, dict),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float))
        and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "array": isinstance(value, list),
    }
    if schema_type and not type_ok.get(schema_type, True):
        errors.append(
            f"{path}: expected {schema_type}, got {type(value).__name__}")
        return
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in enum {schema['enum']}")
        return
    if schema_type == "object":
        for required in schema.get("required", []):
            if required not in value:
                errors.append(
                    f"{path}: missing required field '{required}'")
        for name, sub in schema.get("properties", {}).items():
            if name in value:
                _validate_instance(sub, value[name], f"{path}.{name}",
                                   errors)
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in schema.get("properties", {}):
                    errors.append(f"{path}: unexpected field '{key}'")
    if schema_type == "string":
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(
                f"{path}: '{value}' does not match pattern "
                f"{schema['pattern']}")
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(
                f"{path}: shorter than minLength {schema['minLength']}")
    if schema_type in ("integer", "number"):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(
                f"{path}: {value} < minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(
                f"{path}: {value} > maximum {schema['maximum']}")
        if "exclusiveMinimum" in schema \
                and value <= schema["exclusiveMinimum"]:
            errors.append(
                f"{path}: {value} <= exclusiveMinimum "
                f"{schema['exclusiveMinimum']}")
    if schema_type == "array":
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(
                f"{path}: fewer than minItems {schema['minItems']}")
        items = schema.get("items")
        if isinstance(items, dict):
            for i, item in enumerate(value):
                _validate_instance(items, item, f"{path}[{i}]", errors)


def _schema_errors(schema_name: str, value, label: str) -> list[str]:
    """Validate ``value`` against a canonical schema; returns the
    error list (empty means valid)."""
    schema = _load_schema(schema_name)
    errors: list[str] = []
    _validate_instance(schema, value, label, errors)
    return errors


# ---------------------------------------------------------------------------
# P0 semantic checks (CF-P0-PERF-001..005), mirrored from
# scripts/validate-repo.py + tests/test_schemas.py so the runtime and
# the P0 tests agree. Schema validation already enforces PERF-001
# (intensity 0..10), PERF-002 (exclusiveMinimum 0 durations) and
# PERF-003 (emotion enums); the cross-field rules below are the ones
# the restricted schema subset cannot express.
# ---------------------------------------------------------------------------

def _dialogue_rewrite_errors(plan: dict) -> list[str]:
    """CF-P0-PERF-005: a line's ``dialogue.rewritten_text`` may be
    present only when that line's ``dialogue.rewrite_permitted`` is
    explicitly true. The plan-level ``dialogue_mode`` (even
    SCRIPT_EDIT_REQUESTED) never permits a rewrite by itself."""
    errors = []
    if not isinstance(plan, dict):
        return ["performance plan is not an object"]
    for i, line in enumerate(plan.get("lines") or []):
        if not isinstance(line, dict):
            continue
        dialogue = line.get("dialogue")
        if not isinstance(dialogue, dict):
            continue
        if "rewritten_text" in dialogue \
                and dialogue.get("rewrite_permitted") is not True:
            errors.append(
                f"lines[{i}] ({line.get('line_id', '?')}): rewritten_text "
                "present but rewrite_permitted is not true for this line "
                "(plan-level dialogue_mode alone never permits a rewrite)")
    return errors


def _non_verbal_line_errors(plan: dict) -> list[str]:
    """CF-P0-PERF-004: a performance-plan line must speak or perform
    non-verbally. A line with no spoken dialogue text (dialogue
    absent, or text missing/empty) must carry at least one
    ``non_verbal_events`` entry."""
    errors = []
    if not isinstance(plan, dict):
        return ["performance plan is not an object"]
    for i, line in enumerate(plan.get("lines") or []):
        if not isinstance(line, dict):
            continue
        dialogue = line.get("dialogue")
        text = dialogue.get("text") if isinstance(dialogue, dict) else None
        events = line.get("non_verbal_events") or []
        if not text and not events:
            errors.append(
                f"lines[{i}] ({line.get('line_id', '?')}): no spoken "
                "dialogue text and no non_verbal_events — a line must "
                "speak or perform non-verbally")
    return errors


def _articulation_errors(entries, label: str,
                         fail_closed_unknown: bool = False) -> list[str]:
    """Articulation must match the subject's anatomy. Each entry is a
    dict carrying ``articulation_target`` (or ``articulation``) plus
    ``subject_kind`` / ``species`` / ``character_id`` where known.
    Human lip movement applies only to human / digital-human
    subjects; a bird species never uses human-mouth-lips. When
    ``fail_closed_unknown`` is set and the articulation is
    human-mouth-lips but the subject kind cannot be established from
    the supplied context, the check fails closed — anatomy is never
    guessed. (Single-record validators leave it unset: they cannot
    see the kind another record supplies; the cross-reference phase
    resolves kinds first and then fails closed.)"""
    errors = []
    for i, entry in enumerate(entries or []):
        if not isinstance(entry, dict):
            continue
        target = entry.get("articulation_target") or entry.get("articulation")
        if not target:
            continue
        kind = entry.get("subject_kind")
        species = (entry.get("species") or "").lower()
        who = entry.get("character_id") or entry.get("dialogue_line_id") \
            or f"{label}[{i}]"
        if kind in _ARTICULATION_BY_SUBJECT_KIND and \
                target not in _ARTICULATION_BY_SUBJECT_KIND[kind]:
            errors.append(
                f"{who}: articulation '{target}' is not valid for "
                f"subject_kind '{kind}'")
        if target == "human-mouth-lips" and \
                any(word in species for word in _BIRD_WORDS):
            errors.append(
                f"{who}: bird species '{entry.get('species')}' must never "
                "use human-mouth-lips articulation")
        if target == "human-mouth-lips" and kind is None \
                and not species and fail_closed_unknown:
            errors.append(
                f"{who}: human-mouth-lips articulation but the subject "
                "kind / species cannot be established from the supplied "
                "context — anatomy is never guessed")
    return errors


def _live_action_errors(profile: dict) -> list[str]:
    """is_live_action_footage must agree with the production medium /
    style. A generated subject (AI digital human/creature, CGI,
    drawn) with is_live_action_footage=true is invalid; conversely a
    live-action-footage production with the flag false is invalid.
    Checks the profile level and every per-subject override."""
    errors = []
    if not isinstance(profile, dict):
        return ["production profile is not an object"]
    flag = profile.get("is_live_action_footage")
    medium = profile.get("production_medium")
    style = profile.get("visual_style")
    pid = profile.get("production_profile_id", "?")
    if flag is True and (medium in _GENERATED_MEDIA
                         or style in _GENERATED_STYLES):
        errors.append(
            f"{pid}: is_live_action_footage=true but "
            f"production_medium='{medium}' / visual_style='{style}' is "
            "generated, not live-action footage")
    if flag is False and medium == "live-action-footage":
        errors.append(
            f"{pid}: is_live_action_footage=false but "
            "production_medium='live-action-footage'")
    for i, sub in enumerate(profile.get("per_subject_overrides") or []):
        if not isinstance(sub, dict):
            continue
        if sub.get("is_live_action_footage") is True and \
                sub.get("representation") in _GENERATED_MEDIA:
            errors.append(
                f"{pid} per_subject_overrides[{i}] "
                f"({sub.get('character_id', '?')}): "
                "is_live_action_footage=true but representation "
                f"'{sub.get('representation')}' is generated")
    return errors


def _subject_live_action_errors(subjects, label: str) -> list[str]:
    """Per-subject is_live_action_footage check for scene/shot
    subjects: a generated representation is never live-action
    footage."""
    errors = []
    for i, sub in enumerate(subjects or []):
        if not isinstance(sub, dict):
            continue
        if sub.get("is_live_action_footage") is True and \
                sub.get("representation") in _GENERATED_MEDIA:
            errors.append(
                f"{label}[{i}] ({sub.get('character_id', '?')}): "
                "is_live_action_footage=true but representation "
                f"'{sub.get('representation')}' is generated")
    return errors


def _unique_id_errors(values, key: str, label: str) -> list[str]:
    """Duplicate identifier check for a list of records."""
    errors = []
    seen: dict[str, int] = {}
    for i, item in enumerate(values or []):
        if not isinstance(item, dict):
            continue
        ident = item.get(key)
        if ident is None:
            continue
        if ident in seen:
            errors.append(
                f"{label}: duplicate {key} {ident!r} (first at index "
                f"{seen[ident]}, again at index {i})")
        else:
            seen[ident] = i
    return errors


# ---------------------------------------------------------------------------
# Record validators (schema + P0 semantics)
# ---------------------------------------------------------------------------

def validate_script_contract(script) -> list[str]:
    """Validate a source ScriptContract against
    schemas/script-contract.json plus the structural rules the schema
    cannot express: dialogue line IDs and source shot IDs must be
    unique, and every dialogue line ID must be a non-empty string.
    An empty dialogue list is valid (a non-verbal-only script)."""
    errors = _schema_errors(_SCRIPT_CONTRACT_SCHEMA, script, "script")
    if not isinstance(script, dict):
        return errors
    dialogue = script.get("dialogue")
    if isinstance(dialogue, list):
        for i, line in enumerate(dialogue):
            if not isinstance(line, dict):
                continue
            line_id = line.get("line_id")
            if isinstance(line_id, str) and not line_id:
                errors.append(
                    f"script.dialogue[{i}]: line_id must not be empty")
        errors.extend(_unique_id_errors(
            dialogue, "line_id", "script.dialogue"))
    errors.extend(_unique_id_errors(
        script.get("shots"), "shot_id", "script.shots"))
    return errors


def validate_production_profile(profile) -> list[str]:
    """Validate a production profile against
    schemas/production-profile.json plus the live-action provenance
    rule (a generated subject is never live-action footage)."""
    errors = _schema_errors(_PRODUCTION_PROFILE_SCHEMA, profile,
                            "production_profile")
    if isinstance(profile, dict):
        errors.extend(_live_action_errors(profile))
    return errors


def validate_scene_plan(plan) -> list[str]:
    """Validate a Scene Plan against schemas/scene-plan.json plus
    scene/beat ID uniqueness, per-scene subject character uniqueness,
    articulation and live-action provenance."""
    errors = _schema_errors(_SCENE_PLAN_SCHEMA, plan, "scene_plan")
    if not isinstance(plan, dict):
        return errors
    scenes = plan.get("scenes")
    if not isinstance(scenes, list):
        return errors
    errors.extend(_unique_id_errors(scenes, "scene_id", "scene_plan.scenes"))
    for si, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            continue
        label = f"scene_plan.scenes[{si}]"
        beats = scene.get("beats")
        if isinstance(beats, list):
            errors.extend(_unique_id_errors(
                beats, "beat_id", f"{label}.beats"))
        subjects = scene.get("subjects")
        if isinstance(subjects, list):
            errors.extend(_unique_id_errors(
                subjects, "character_id", f"{label}.subjects"))
            errors.extend(_subject_live_action_errors(
                subjects, f"{label}.subjects"))
            errors.extend(_articulation_errors(subjects, label))
    return errors


def validate_shot_plan(plan) -> list[str]:
    """Validate a Shot Plan against schemas/shot-plan.json plus shot
    ID uniqueness, per-shot subject character uniqueness,
    articulation and live-action provenance. Shot durations are
    strictly positive by schema (CF-P0-PERF-002)."""
    errors = _schema_errors(_SHOT_PLAN_SCHEMA, plan, "shot_plan")
    if not isinstance(plan, dict):
        return errors
    shots = plan.get("shots")
    if not isinstance(shots, list):
        return errors
    errors.extend(_unique_id_errors(shots, "shot_id", "shot_plan.shots"))
    for si, shot in enumerate(shots):
        if not isinstance(shot, dict):
            continue
        label = f"shot_plan.shots[{si}]"
        subjects = shot.get("subjects")
        if isinstance(subjects, list):
            errors.extend(_unique_id_errors(
                subjects, "character_id", f"{label}.subjects"))
            errors.extend(_subject_live_action_errors(
                subjects, f"{label}.subjects"))
            errors.extend(_articulation_errors(subjects, label))
    return errors


def validate_performance_plan(plan) -> list[str]:
    """Validate a Performance Plan against
    schemas/performance-plan.json plus CF-P0-PERF-004 (a line must
    speak or perform non-verbally), CF-P0-PERF-005 (per-line dialogue
    rewrite permission only), line/dialogue-line ID uniqueness and
    articulation."""
    errors = _schema_errors(_PERFORMANCE_PLAN_SCHEMA, plan,
                            "performance_plan")
    if not isinstance(plan, dict):
        return errors
    lines = plan.get("lines")
    if not isinstance(lines, list):
        return errors
    errors.extend(_unique_id_errors(lines, "line_id",
                                    "performance_plan.lines"))
    errors.extend(_unique_id_errors(lines, "dialogue_line_id",
                                    "performance_plan.lines"))
    errors.extend(_non_verbal_line_errors(plan))
    errors.extend(_dialogue_rewrite_errors(plan))
    errors.extend(_articulation_errors(lines, "performance_plan.lines"))
    return errors


# ---------------------------------------------------------------------------
# Subject context: the supplied project/script context that character
# references must resolve against, and the per-subject dimension table
# used for contradiction detection.
# ---------------------------------------------------------------------------

def _subject_table(scene, shot, profile):
    """character_id -> [(source, subject record)] from scene subjects,
    shot subjects and profile per-subject overrides. Used for the
    dimension-agreement check and for resolving a subject's kind /
    species when a single record does not carry it."""
    table: dict[str, list] = {}

    def add(source, records):
        for rec in records or []:
            if isinstance(rec, dict) \
                    and isinstance(rec.get("character_id"), str):
                table.setdefault(rec["character_id"], []).append(
                    (source, rec))

    if isinstance(scene, dict):
        for item in scene.get("scenes") or []:
            if isinstance(item, dict):
                add("scene_plan", item.get("subjects"))
    if isinstance(shot, dict):
        for item in shot.get("shots") or []:
            if isinstance(item, dict):
                add("shot_plan", item.get("subjects"))
    if isinstance(profile, dict):
        add("production_profile", profile.get("per_subject_overrides"))
    return table


def _kind_species_lookup(table, perf_lines):
    """character_id -> (subject_kind, species) resolved from every
    supplied record; the first known value wins (contradictions are
    reported separately by the dimension-agreement check)."""
    kind: dict[str, str] = {}
    species: dict[str, str] = {}
    for cid, records in table.items():
        for _, rec in records:
            if kind.get(cid) is None and rec.get("subject_kind"):
                kind[cid] = rec["subject_kind"]
            if species.get(cid) is None and rec.get("species"):
                species[cid] = rec["species"]
    for line in perf_lines or []:
        if not isinstance(line, dict):
            continue
        cid = line.get("character_id")
        if not isinstance(cid, str):
            continue
        if kind.get(cid) is None and line.get("subject_kind"):
            kind[cid] = line["subject_kind"]
        if species.get(cid) is None and line.get("species"):
            species[cid] = line["species"]
    return kind, species


def _dimension_agreement_errors(table) -> list[str]:
    """For repeated subject IDs, detect contradictory identity or
    production-medium information. A dimension supplied in two places
    must agree; a scene/shot motion_method must be one of the profile
    motion_methods for that subject (when the profile lists them)."""
    errors = []
    for cid in sorted(table):
        records = table[cid]
        for field in _SUBJECT_DIMENSION_FIELDS:
            seen: dict[object, list] = {}
            for source, rec in records:
                if field in rec:
                    seen.setdefault(rec[field], []).append(source)
            if len(seen) > 1:
                parts = ", ".join(
                    f"{value!r} ({', '.join(sources)})"
                    for value, sources in seen.items())
                errors.append(
                    f"subject {cid}: contradictory {field}: {parts}")
        methods: dict[str, list] = {}
        for source, rec in records:
            if source == "production_profile":
                continue
            method = rec.get("motion_method")
            if isinstance(method, str):
                methods.setdefault(method, []).append(source)
        if len(methods) > 1:
            parts = ", ".join(
                f"{value!r} ({', '.join(sources)})"
                for value, sources in methods.items())
            errors.append(
                f"subject {cid}: contradictory motion_method: {parts}")
        for source, rec in records:
            if source != "production_profile":
                continue
            allowed = rec.get("motion_methods")
            if not isinstance(allowed, list):
                continue
            for other_source, other in records:
                if other_source == "production_profile":
                    continue
                method = other.get("motion_method")
                if isinstance(method, str) and method not in allowed:
                    errors.append(
                        f"subject {cid}: motion_method {method!r} "
                        f"({other_source}) is not among the profile "
                        f"motion_methods {allowed} for this subject")
    return errors


def _known_characters(script, profile, scene) -> set:
    """Character IDs the supplied project/script context defines:
    script dialogue speakers, profile per-subject overrides, and the
    scene plan's own cast (character_ids + subjects — the scene plan
    is part of the supplied context, so it defines characters rather
    than referencing them). Shot, performance and binding references
    must resolve into this set."""
    known: set[str] = set()
    if isinstance(script, dict):
        for line in script.get("dialogue") or []:
            if isinstance(line, dict) \
                    and isinstance(line.get("character_id"), str):
                known.add(line["character_id"])
    if isinstance(profile, dict):
        for sub in profile.get("per_subject_overrides") or []:
            if isinstance(sub, dict) \
                    and isinstance(sub.get("character_id"), str):
                known.add(sub["character_id"])
    if isinstance(scene, dict):
        for item in scene.get("scenes") or []:
            if not isinstance(item, dict):
                continue
            for cid in item.get("character_ids") or []:
                if isinstance(cid, str):
                    known.add(cid)
            for sub in item.get("subjects") or []:
                if isinstance(sub, dict) \
                        and isinstance(sub.get("character_id"), str):
                    known.add(sub["character_id"])
    return known


# ---------------------------------------------------------------------------
# Cross-reference validation — the four records as one timeline
# ---------------------------------------------------------------------------

def _cross_reference_errors(script, profile, scene, shot, perf,
                            s2p) -> list[str]:
    """Explicit cross-reference validation across the validated
    records. ``s2p`` may be None (draft validation, before the
    binding record is assembled); the S2P-specific checks are then
    skipped. Every error names the field/path it concerns."""
    errors: list[str] = []
    if not isinstance(scene, dict) or not isinstance(shot, dict) \
            or not isinstance(perf, dict):
        return ["scene, shot and performance plans must be objects"]
    scenes = scene.get("scenes") or []
    shots = shot.get("shots") or []
    lines = perf.get("lines") or []

    # -- Project IDs agree wherever supplied.
    projects: dict[object, list] = {}
    for label, record in (("script", script), ("production_profile", profile),
                          ("scene_plan", scene), ("shot_plan", shot),
                          ("performance_plan", perf)):
        if isinstance(record, dict) and "project_id" in record:
            projects.setdefault(record["project_id"], []).append(label)
    if s2p is not None and isinstance(s2p, dict) \
            and "project_id" in s2p:
        projects.setdefault(s2p["project_id"], []).append(
            "script_to_performance")
    if len(projects) > 1:
        parts = ", ".join(
            f"{value!r} ({', '.join(labels)})"
            for value, labels in projects.items())
        errors.append(f"project_id disagreement: {parts}")

    # -- Schema versions agree across the three plans (the S2P record
    # carries the agreed version).
    versions = {plan.get("schema_version")
                for plan in (scene, shot, perf)}
    if len(versions) > 1:
        errors.append(
            "schema_version disagreement across scene/shot/performance "
            f"plans: {sorted(str(v) for v in versions)}")

    # -- Dialogue modes agree (script vs performance plan).
    script_mode = script.get("dialogue_mode") \
        if isinstance(script, dict) else None
    perf_mode = perf.get("dialogue_mode")
    if script_mode is not None and perf_mode is not None \
            and script_mode != perf_mode:
        errors.append(
            "dialogue_mode disagreement: script uses "
            f"{script_mode!r}, performance plan uses {perf_mode!r}")

    # -- Scene / beat resolution.
    scene_ids: dict[str, dict] = {}
    for item in scenes:
        if isinstance(item, dict) \
                and isinstance(item.get("scene_id"), str):
            scene_ids[item["scene_id"]] = item
    if isinstance(shot, dict) and "scene_plan_id" in shot \
            and shot["scene_plan_id"] != scene.get("id"):
        errors.append(
            "shot_plan.scene_plan_id "
            f"{shot['scene_plan_id']!r} does not match scene_plan.id "
            f"{scene.get('id')!r}")
    shot_ids: set[str] = set()
    for i, item in enumerate(shots):
        if not isinstance(item, dict):
            continue
        shot_id = item.get("shot_id")
        if isinstance(shot_id, str):
            shot_ids.add(shot_id)
        scene_id = item.get("scene_id")
        if isinstance(scene_id, str) and scene_id not in scene_ids:
            errors.append(
                f"shot_plan.shots[{i}] ({shot_id or '?'}): scene_id "
                f"{scene_id!r} does not resolve to a scene plan scene")
            continue
        beat_id = item.get("beat_id")
        if isinstance(beat_id, str) and isinstance(scene_id, str):
            beats = scene_ids[scene_id].get("beats") or []
            beat_ids = {b.get("beat_id") for b in beats
                        if isinstance(b, dict)}
            if beat_id not in beat_ids:
                errors.append(
                    f"shot_plan.shots[{i}] ({shot_id or '?'}): beat_id "
                    f"{beat_id!r} does not resolve inside scene "
                    f"{scene_id!r}")

    # -- Source shot IDs are never silently omitted.
    if isinstance(script, dict):
        for item in script.get("shots") or []:
            if isinstance(item, dict) \
                    and isinstance(item.get("shot_id"), str) \
                    and item["shot_id"] not in shot_ids:
                errors.append(
                    "script.shots shot_id "
                    f"{item['shot_id']!r} is not present in the shot plan "
                    "(source shots are never silently omitted)")

    # -- Subject dimension agreement + articulation with resolved kinds.
    table = _subject_table(scene, shot, profile)
    errors.extend(_dimension_agreement_errors(table))
    kind_by_id, species_by_id = _kind_species_lookup(table, lines)

    def resolved_entries(records, label):
        """Entries with kind/species resolved from the subject table
        so the articulation check sees the full context."""
        out = []
        for rec in records or []:
            if not isinstance(rec, dict):
                continue
            merged = dict(rec)
            cid = rec.get("character_id")
            if isinstance(cid, str):
                if "subject_kind" not in merged \
                        and kind_by_id.get(cid):
                    merged["subject_kind"] = kind_by_id[cid]
                if "species" not in merged and species_by_id.get(cid):
                    merged["species"] = species_by_id[cid]
            out.append(merged)
        return out

    for item in scenes:
        if isinstance(item, dict):
            errors.extend(_articulation_errors(
                resolved_entries(item.get("subjects"), "scene subjects"),
                "scene_plan", fail_closed_unknown=True))
    for item in shots:
        if isinstance(item, dict):
            errors.extend(_articulation_errors(
                resolved_entries(item.get("subjects"), "shot subjects"),
                "shot_plan", fail_closed_unknown=True))
    errors.extend(_articulation_errors(
        resolved_entries(lines, "performance lines"),
        "performance_plan", fail_closed_unknown=True))

    # -- Character references resolve.
    known = _known_characters(script, profile, scene)
    for i, item in enumerate(shots):
        if not isinstance(item, dict):
            continue
        for cid in item.get("character_ids") or []:
            if isinstance(cid, str) and cid not in known:
                errors.append(
                    f"shot_plan.shots[{i}] ({item.get('shot_id', '?')}): "
                    f"character_id {cid!r} does not resolve from the "
                    "supplied project/script context")
        for sub in item.get("subjects") or []:
            if isinstance(sub, dict) \
                    and isinstance(sub.get("character_id"), str) \
                    and sub["character_id"] not in known:
                errors.append(
                    f"shot_plan.shots[{i}] subjects: character_id "
                    f"{sub['character_id']!r} does not resolve from the "
                    "supplied project/script context")
    for i, line in enumerate(lines):
        if not isinstance(line, dict):
            continue
        cid = line.get("character_id")
        if isinstance(cid, str) and cid not in known:
            errors.append(
                f"performance_plan.lines[{i}] ({line.get('line_id', '?')}): "
                f"character_id {cid!r} does not resolve from the "
                "supplied project/script context")

    # -- Dialogue mapping (needs the script).
    dialogue_errors = _dialogue_mapping_errors(script, perf)
    errors.extend(dialogue_errors)

    # -- Voice bindings, reaction holds, binding-form ambiguity.
    if s2p is not None and isinstance(s2p, dict):
        errors.extend(_binding_errors(s2p, lines, shot_ids, known,
                                      kind_by_id, species_by_id))

    return errors


def _dialogue_mapping_errors(script, perf) -> list[str]:
    """Every source dialogue line maps to exactly one Performance
    Plan line, in the same order, with the text preserved exactly.
    A spoken source line must carry its text in the performance
    line; a non-verbal source line (empty text) must be performed
    non-verbally."""
    errors: list[str] = []
    if not isinstance(script, dict) or not isinstance(perf, dict):
        return errors
    source = script.get("dialogue")
    lines = perf.get("lines")
    if not isinstance(source, list) or not isinstance(lines, list):
        return errors
    source_ids = [ln.get("line_id") for ln in source
                  if isinstance(ln, dict)]
    perf_ids = [ln.get("line_id") for ln in lines
                if isinstance(ln, dict)]
    source_set = set(source_ids)
    perf_set = set(perf_ids)
    for missing in source_ids:
        if missing not in perf_set:
            errors.append(
                f"performance plan is missing source dialogue line "
                f"{missing!r}")
    for extra in perf_ids:
        if extra not in source_set:
            errors.append(
                f"performance plan has extra line {extra!r} with no "
                "source dialogue line")
    if source_set == perf_set and source_ids != perf_ids:
        errors.append(
            "performance plan lines are reordered relative to the "
            f"source dialogue (source order {source_ids}, plan order "
            f"{perf_ids})")
    source_by_id = {ln.get("line_id"): ln for ln in source
                    if isinstance(ln, dict)}
    perf_by_id = {ln.get("line_id"): ln for ln in lines
                  if isinstance(ln, dict)}
    for line_id in source_ids:
        src = source_by_id.get(line_id)
        dst = perf_by_id.get(line_id)
        if src is None or dst is None:
            continue
        src_text = src.get("text")
        dialogue = dst.get("dialogue")
        dst_text = dialogue.get("text") \
            if isinstance(dialogue, dict) else None
        if isinstance(src_text, str) and src_text:
            if not isinstance(dst_text, str):
                errors.append(
                    f"performance line {line_id!r} omits the spoken "
                    "dialogue text of its source line")
            elif dst_text != src_text:
                errors.append(
                    f"performance line {line_id!r} dialogue text differs "
                    "from the source dialogue (verbatim preservation "
                    "required)")
        else:
            if isinstance(dst_text, str) and dst_text:
                errors.append(
                    f"performance line {line_id!r} carries spoken text "
                    "for a non-verbal source line")
        src_char = src.get("character_id")
        dst_char = dst.get("character_id")
        if isinstance(src_char, str) and isinstance(dst_char, str) \
                and src_char != dst_char:
            errors.append(
                f"performance line {line_id!r} character_id "
                f"{dst_char!r} does not match the source dialogue "
                f"character_id {src_char!r}")
    return errors


def _rewrite_authorisation_errors(perf, dialogue_mode,
                                  authorised: bool) -> list[str]:
    """A rewrite is valid only when ALL of these hold: the caller
    explicitly supplied dialogue_rewrite_authorised True, the plan
    uses SCRIPT_EDIT_REQUESTED, the exact line has
    rewrite_permitted true, and the original text stays preserved in
    dialogue.text. (The per-line permission itself is CF-P0-PERF-005,
    enforced by the performance-plan validator.)"""
    errors = []
    if not isinstance(perf, dict):
        return errors
    for i, line in enumerate(perf.get("lines") or []):
        if not isinstance(line, dict):
            continue
        dialogue = line.get("dialogue")
        if not isinstance(dialogue, dict):
            continue
        if "rewritten_text" not in dialogue:
            continue
        who = f"lines[{i}] ({line.get('line_id', '?')})"
        if authorised is not True:
            errors.append(
                f"performance plan {who}: rewritten_text present but "
                "dialogue_rewrite_authorised is not true — a plan-level "
                "rewrite request alone never authorises a rewrite")
        if dialogue_mode != "SCRIPT_EDIT_REQUESTED":
            errors.append(
                f"performance plan {who}: rewritten_text present but "
                f"dialogue_mode is {dialogue_mode!r}, not "
                "'SCRIPT_EDIT_REQUESTED'")
        if dialogue.get("rewrite_permitted") is not True:
            errors.append(
                f"performance plan {who}: rewritten_text present but "
                "rewrite_permitted is not true for this line")
        if "text" not in dialogue:
            errors.append(
                f"performance plan {who}: rewritten_text present but the "
                "original dialogue.text is not preserved")
    return errors


def _binding_errors(s2p, lines, shot_ids, known, kind_by_id,
                    species_by_id) -> list[str]:
    """Voice bindings reference valid dialogue line IDs and (when a
    shot ID is present) valid shot IDs; their characters resolve;
    their articulation matches the subject; and the single and
    multiple binding forms are never used ambiguously together (two
    bindings for one line must agree on every field). Editing
    reaction holds reference valid dialogue line IDs."""
    errors: list[str] = []
    valid_line_ids: set[str] = set()
    line_by_ref: dict[str, dict] = {}
    for line in lines:
        if not isinstance(line, dict):
            continue
        for key in ("line_id", "dialogue_line_id"):
            ident = line.get(key)
            if isinstance(ident, str):
                valid_line_ids.add(ident)
                line_by_ref.setdefault(ident, line)
    bindings: list[tuple[str, dict]] = []
    single = s2p.get("character_voice_binding")
    if isinstance(single, dict):
        bindings.append(("character_voice_binding", single))
    for i, entry in enumerate(s2p.get("character_voice_bindings") or []):
        if isinstance(entry, dict):
            bindings.append((f"character_voice_bindings[{i}]", entry))
    by_line: dict[str, list] = {}
    for label, binding in bindings:
        line_ref = binding.get("dialogue_line_id")
        if not isinstance(line_ref, str) \
                or line_ref not in valid_line_ids:
            errors.append(
                f"{label}: dialogue_line_id {line_ref!r} does not "
                "reference a valid dialogue line")
            continue
        by_line.setdefault(line_ref, []).append((label, binding))
        shot_ref = binding.get("shot_id")
        if shot_ref is not None and shot_ref not in shot_ids:
            errors.append(
                f"{label}: shot_id {shot_ref!r} does not reference a "
                "valid shot")
        char_ref = binding.get("character_id")
        if isinstance(char_ref, str) and char_ref not in known:
            errors.append(
                f"{label}: character_id {char_ref!r} does not resolve "
                "from the supplied project/script context")
        perf_line = line_by_ref.get(line_ref)
        if isinstance(perf_line, dict) \
                and isinstance(perf_line.get("character_id"), str) \
                and isinstance(char_ref, str) \
                and perf_line["character_id"] != char_ref:
            errors.append(
                f"{label}: character_id {char_ref!r} does not match the "
                "performance line's character_id "
                f"{perf_line['character_id']!r} for dialogue line "
                f"{line_ref!r}")
        merged = dict(binding)
        if isinstance(char_ref, str):
            if "subject_kind" not in merged and kind_by_id.get(char_ref):
                merged["subject_kind"] = kind_by_id[char_ref]
            if "species" not in merged and species_by_id.get(char_ref):
                merged["species"] = species_by_id[char_ref]
        errors.extend(_articulation_errors([merged], label,
                                           fail_closed_unknown=True))
    for line_ref, group in sorted(by_line.items()):
        if len(group) < 2:
            continue
        first = group[0][1]
        for label, binding in group[1:]:
            for field in ("character_id", "voice_profile_id",
                          "articulation", "speaking_state", "shot_id",
                          "delivery", "emotion", "audio_asset_id",
                          "reference_asset_ids"):
                if binding.get(field) != first.get(field):
                    errors.append(
                        "ambiguous character-voice bindings for dialogue "
                        f"line {line_ref!r}: {label} and "
                        f"{group[0][0]} disagree on {field} "
                        f"({binding.get(field)!r} vs "
                        f"{first.get(field)!r})")
    editing = s2p.get("editing_plan")
    if isinstance(editing, dict):
        for i, hold in enumerate(editing.get("reaction_holds") or []):
            if not isinstance(hold, dict):
                continue
            after = hold.get("after_line_id")
            if not isinstance(after, str) \
                    or after not in valid_line_ids:
                errors.append(
                    f"editing_plan.reaction_holds[{i}]: after_line_id "
                    f"{after!r} does not reference a valid dialogue line")
    return errors


# ---------------------------------------------------------------------------
# Draft validation
# ---------------------------------------------------------------------------

def _draft_field_errors(draft: dict) -> list[str]:
    """Validate the draft's optional audio/editing/binding fields
    against the corresponding subschemas of the canonical
    Script-to-Performance schema."""
    errors = []
    s2p_schema = _load_schema(_SCRIPT_TO_PERFORMANCE_SCHEMA)
    props = s2p_schema.get("properties", {})
    for key in ("audio_plan", "editing_plan", "character_voice_binding",
                "character_voice_bindings"):
        if key in draft and key in props:
            sub_errors: list[str] = []
            _validate_instance(props[key], draft[key],
                               f"draft.{key}", sub_errors)
            errors.extend(sub_errors)
    return errors


def validate_script_plan_drafts(draft, script=None) -> list[str]:
    """Validate a structured analysis draft: the three required
    plans (each against its canonical schema plus the P0 semantic
    rules), the optional audio/editing/binding fields, and the
    cross-references among the drafts. When ``script`` is supplied
    it is validated too and the dialogue mapping plus source-shot
    coverage are checked; without it those two checks are skipped
    (the builder always supplies the script)."""
    errors: list[str] = []
    if not isinstance(draft, dict):
        return ["draft is not an object"]
    for key in draft:
        if key not in _DRAFT_KEYS:
            errors.append(f"draft: unexpected field '{key}'")
    for key in _DRAFT_REQUIRED_KEYS:
        if key not in draft:
            errors.append(f"draft: missing required field '{key}'")
        elif not isinstance(draft[key], dict):
            errors.append(f"draft.{key} is not an object")
    errors.extend(_draft_field_errors(draft))
    scene = draft.get("scene_plan")
    shot = draft.get("shot_plan")
    perf = draft.get("performance_plan")
    if isinstance(scene, dict):
        errors.extend(validate_scene_plan(scene))
    if isinstance(shot, dict):
        errors.extend(validate_shot_plan(shot))
    if isinstance(perf, dict):
        errors.extend(validate_performance_plan(perf))
    if script is not None:
        errors.extend(validate_script_contract(script))
    if isinstance(scene, dict) and isinstance(shot, dict) \
            and isinstance(perf, dict):
        errors.extend(_cross_reference_errors(script, None, scene, shot,
                                              perf, None))
    return errors


# ---------------------------------------------------------------------------
# Script-to-Performance record assembly
# ---------------------------------------------------------------------------

def _agreed_project_id(records) -> object:
    """The single project ID all supplied records agree on, or None
    when no record supplies one. Disagreement is reported by the
    cross-reference check, not resolved here."""
    values = {rec["project_id"] for rec in records
              if isinstance(rec, dict) and "project_id" in rec}
    return values.pop() if len(values) == 1 else None


def _assemble_s2p_record(bundle_id: str, dialogue_mode: str,
                         authorised: bool, scene, shot, perf,
                         draft: dict) -> dict:
    """Assemble the final Script-to-Performance binding record from
    the validated plans and draft. Nothing is invented: every field
    comes from the caller, the validated drafts or the agreed
    cross-plan values (project ID, schema version, dialogue mode)."""
    versions = {plan.get("schema_version")
                for plan in (scene, shot, perf)}
    record = {
        "schema_version": versions.pop() if len(versions) == 1 else "2.5",
        "id": bundle_id,
        "dialogue_mode": dialogue_mode,
        "dialogue_rewrite_authorised": authorised,
        "scene_plan_id": scene.get("id"),
        "shot_plan_id": shot.get("id"),
        "performance_plan_id": perf.get("id"),
    }
    project_id = _agreed_project_id(
        (scene, shot, perf))
    if project_id is not None:
        record["project_id"] = project_id
    for key in ("audio_plan", "editing_plan", "character_voice_binding",
                "character_voice_bindings"):
        if key in draft:
            record[key] = copy.deepcopy(draft[key])
    return record


# ---------------------------------------------------------------------------
# Bundle validation
# ---------------------------------------------------------------------------

_BUNDLE_REQUIRED_KEYS = (
    "bundle_id", "schema_version", "session_id", "routing_plan_id",
    "script_contract", "production_profile", "script_to_performance",
    "scene_plan", "shot_plan", "performance_plan", "bundle_hash",
)


def validate_script_to_performance_bundle(bundle) -> list[str]:
    """Validate an assembled bundle: structure, every embedded
    record against its canonical schema plus the P0 semantic rules,
    the full cross-reference validation, and the bundle-hash
    recomputation. An empty list means the bundle is coherent and
    untampered."""
    errors: list[str] = []
    if not isinstance(bundle, dict):
        return ["bundle is not an object"]
    for key in _BUNDLE_REQUIRED_KEYS:
        if key not in bundle:
            errors.append(f"bundle: missing required field '{key}'")
    bundle_id = bundle.get("bundle_id")
    if bundle_id is not None and (
            not isinstance(bundle_id, str)
            or not _ID_RE.match(bundle_id)):
        errors.append(
            f"bundle.bundle_id {bundle_id!r} is not a valid bundle ID")
    if bundle.get("schema_version") != BUNDLE_SCHEMA_VERSION:
        errors.append(
            "bundle.schema_version must be "
            f"'{BUNDLE_SCHEMA_VERSION}', got "
            f"{bundle.get('schema_version')!r}")
    session_id = bundle.get("session_id")
    if session_id is not None and (
            not isinstance(session_id, str) or not session_id):
        errors.append("bundle.session_id must be a non-empty string")
    routing_plan_id = bundle.get("routing_plan_id")
    if routing_plan_id is not None and (
            not isinstance(routing_plan_id, str) or not routing_plan_id):
        errors.append("bundle.routing_plan_id must be a non-empty string")
    stored_hash = bundle.get("bundle_hash")
    if stored_hash is not None:
        if not isinstance(stored_hash, str) \
                or not _SHA256_RE.match(stored_hash):
            errors.append("bundle.bundle_hash is not a SHA-256 hex digest")
        elif script_to_performance_hash(bundle) != stored_hash:
            errors.append(
                "bundle.bundle_hash does not match the bundle contents "
                "(the bundle was tampered with)")
    script = bundle.get("script_contract")
    profile = bundle.get("production_profile")
    s2p = bundle.get("script_to_performance")
    scene = bundle.get("scene_plan")
    shot = bundle.get("shot_plan")
    perf = bundle.get("performance_plan")
    if script is not None:
        errors.extend(validate_script_contract(script))
    if profile is not None:
        errors.extend(validate_production_profile(profile))
    if isinstance(s2p, dict):
        errors.extend(_schema_errors(_SCRIPT_TO_PERFORMANCE_SCHEMA, s2p,
                                     "script_to_performance"))
    if isinstance(scene, dict):
        errors.extend(validate_scene_plan(scene))
    if isinstance(shot, dict):
        errors.extend(validate_shot_plan(shot))
    if isinstance(perf, dict):
        errors.extend(validate_performance_plan(perf))
    if isinstance(scene, dict) and isinstance(shot, dict) \
            and isinstance(perf, dict):
        errors.extend(_cross_reference_errors(
            script, profile, scene, shot, perf, s2p))
        if isinstance(s2p, dict):
            if s2p.get("scene_plan_id") != scene.get("id"):
                errors.append(
                    "script_to_performance.scene_plan_id "
                    f"{s2p.get('scene_plan_id')!r} does not match "
                    f"scene_plan.id {scene.get('id')!r}")
            if s2p.get("shot_plan_id") != shot.get("id"):
                errors.append(
                    "script_to_performance.shot_plan_id "
                    f"{s2p.get('shot_plan_id')!r} does not match "
                    f"shot_plan.id {shot.get('id')!r}")
            if s2p.get("performance_plan_id") != perf.get("id"):
                errors.append(
                    "script_to_performance.performance_plan_id "
                    f"{s2p.get('performance_plan_id')!r} does not match "
                    f"performance_plan.id {perf.get('id')!r}")
            if s2p.get("id") != bundle_id:
                errors.append(
                    "script_to_performance.id "
                    f"{s2p.get('id')!r} does not match bundle_id "
                    f"{bundle_id!r}")
            authorised = s2p.get("dialogue_rewrite_authorised")
            if type(authorised) is not bool:
                errors.append(
                    "script_to_performance.dialogue_rewrite_authorised "
                    f"must be a boolean, got {type(authorised).__name__}")
            else:
                errors.extend(_rewrite_authorisation_errors(
                    perf, s2p.get("dialogue_mode"), authorised))
    return errors


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def build_script_to_performance_bundle(
        session, routing_plan, script, profile, draft, bundle_id,
        dialogue_rewrite_authorised=False) -> dict:
    """Build a deterministic Script-to-Performance bundle from a
    structured script, a valid production profile and the AI layer's
    analysis drafts, under one exact active local session and one
    valid, ready P1-002 routing plan.

    Raises :class:`ScriptToPerformanceError` on any failure and
    returns nothing partial: no bundle is ever returned when any
    input fails validation. Input objects are never modified in
    place — the builder works on deep copies throughout.

    The returned bundle carries the final Script-to-Performance
    record, the final Scene / Shot / Performance Plans, the
    validated script and profile (for traceability and hash
    verification), the routing plan ID, the exact active session ID
    and the deterministic SHA-256 bundle hash.
    """
    # -- Stage A: session, bundle ID, rewrite flag, routing plan.
    if not local_session.is_active_session(session):
        reasons = local_session.validate_session(session)
        raise ScriptToPerformanceError(
            "no active session for this bundle"
            + (f": {'; '.join(reasons)}" if reasons else ""))
    if not isinstance(bundle_id, str) or not _ID_RE.match(bundle_id):
        raise ScriptToPerformanceError(
            f"bundle_id {bundle_id!r} is not a valid bundle ID "
            "(lowercase letters, digits and hyphens, 3-64 chars)")
    if type(dialogue_rewrite_authorised) is not bool:
        raise ScriptToPerformanceError(
            "dialogue_rewrite_authorised must be an actual boolean, "
            f"got {type(dialogue_rewrite_authorised).__name__} "
            "(only an actual boolean True is affirmative approval)")
    catalog = skill_router.load_routing_catalog()
    if not isinstance(routing_plan, dict):
        raise ScriptToPerformanceError("routing plan is not an object")
    try:
        plan_errors = skill_router.validate_routing_plan(routing_plan,
                                                         catalog)
    except (AttributeError, KeyError, TypeError, IndexError) as exc:
        # A plan so malformed the router validator cannot even run
        # is still an invalid plan: fail closed with a structured
        # error rather than leaking the validator's crash.
        raise ScriptToPerformanceError(
            "invalid routing plan: the plan is malformed "
            f"({type(exc).__name__}: {exc})") from exc
    if plan_errors:
        raise ScriptToPerformanceError(
            ["invalid routing plan: " + err for err in plan_errors])
    if routing_plan.get("status") != "ready":
        raise ScriptToPerformanceError(
            "routing plan is not ready: "
            + "; ".join(
                d.get("message", str(d))
                for d in routing_plan.get("blocked_diagnostics") or []
            ) or f"status is {routing_plan.get('status')!r}")
    if routing_plan.get("intent_mode") != "GENERATE_FROM_SCRIPT":
        raise ScriptToPerformanceError(
            "routing plan intent_mode must be GENERATE_FROM_SCRIPT, got "
            f"{routing_plan.get('intent_mode')!r}")
    plan_session_id = (routing_plan.get("session") or {}).get("session_id")
    if plan_session_id != session.session_id:
        raise ScriptToPerformanceError(
            "routing plan session does not match the exact active "
            "session (plan session "
            f"{plan_session_id!r} != active session "
            f"{session.session_id!r})")

    # -- Stage B: work on deep copies; validate script + profile.
    script = copy.deepcopy(script)
    profile = copy.deepcopy(profile)
    draft = copy.deepcopy(draft)
    errors = validate_script_contract(script)
    errors.extend(validate_production_profile(profile))
    if errors:
        raise ScriptToPerformanceError(errors)

    # -- Stage C: validate the drafts (plans + cross-references,
    # including dialogue mapping against the script).
    errors = validate_script_plan_drafts(draft, script)
    if errors:
        raise ScriptToPerformanceError(errors)
    scene = draft["scene_plan"]
    shot = draft["shot_plan"]
    perf = draft["performance_plan"]

    # -- Stage D: assemble + schema-validate the binding record.
    dialogue_mode = perf.get("dialogue_mode")
    s2p = _assemble_s2p_record(bundle_id, dialogue_mode,
                               dialogue_rewrite_authorised,
                               scene, shot, perf, draft)
    errors = _schema_errors(_SCRIPT_TO_PERFORMANCE_SCHEMA, s2p,
                            "script_to_performance")
    if errors:
        raise ScriptToPerformanceError(errors)

    # -- Stage E: full cross-reference validation with the binding
    # record (root IDs, rewrite authorisation, bindings, holds).
    errors = _cross_reference_errors(script, profile, scene, shot, perf,
                                     s2p)
    if isinstance(s2p, dict):
        if s2p.get("scene_plan_id") != scene.get("id"):
            errors.append(
                "script_to_performance.scene_plan_id "
                f"{s2p.get('scene_plan_id')!r} does not match "
                f"scene_plan.id {scene.get('id')!r}")
        if s2p.get("shot_plan_id") != shot.get("id"):
            errors.append(
                "script_to_performance.shot_plan_id "
                f"{s2p.get('shot_plan_id')!r} does not match "
                f"shot_plan.id {shot.get('id')!r}")
        if s2p.get("performance_plan_id") != perf.get("id"):
            errors.append(
                "script_to_performance.performance_plan_id "
                f"{s2p.get('performance_plan_id')!r} does not match "
                f"performance_plan.id {perf.get('id')!r}")
    errors.extend(_rewrite_authorisation_errors(
        perf, dialogue_mode, dialogue_rewrite_authorised))
    if errors:
        raise ScriptToPerformanceError(errors)

    # -- Stage F: assemble the bundle and self-check it (including
    # the hash). A bundle that fails its own validation is never
    # returned.
    bundle = {
        "bundle_id": bundle_id,
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "session_id": session.session_id,
        "routing_plan_id": routing_plan.get("plan_id"),
        "script_contract": script,
        "production_profile": profile,
        "script_to_performance": s2p,
        "scene_plan": scene,
        "shot_plan": shot,
        "performance_plan": perf,
    }
    bundle["bundle_hash"] = script_to_performance_hash(bundle)
    errors = validate_script_to_performance_bundle(bundle)
    if errors:
        raise ScriptToPerformanceError(errors)
    return bundle


__all__ = [
    "ScriptToPerformanceError",
    "validate_script_contract",
    "validate_production_profile",
    "validate_scene_plan",
    "validate_shot_plan",
    "validate_performance_plan",
    "validate_script_plan_drafts",
    "validate_script_to_performance_bundle",
    "build_script_to_performance_bundle",
    "script_to_performance_hash",
]
