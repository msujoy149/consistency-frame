#!/usr/bin/env python3
"""Consistency Frame P1 — deterministic runtime skill router and
workflow plan builder (CF-WO-P1-002).

This module promotes the P0 test-only routing helper into the first
production runtime. It resolves skills and builds deterministic
workflow plans from structured requests, using only the compiled
routing catalog (``registry/routing-catalog.json``) as its data source.
It is standard-library only: it never imports YAML, never reads a
private project asset, never contacts a provider, never generates
media, and never persists anything.

Rules enforced here (all grounded in the catalog, never in prose):
- Exactly one primary pathway where one applies; one or more
  compatible style profiles bound to shots and subjects, using only
  the canonical VISUAL_STYLE vocabulary.
- Subject-scoped capabilities: a subject's constraints are never
  applied to another subject.
- Canonical dependencies and graph edges: a dependent is never ready
  before its prerequisites. A dependency that does not apply in the
  selected mode is a blocked diagnostic — never silently dropped,
  never invented.
- Precedence is a routing order and a tie-breaker only, never an
  exclusion.
- resource-management is cross-cutting phase-level instruction, never
  a scheduled step.
- True conflicts (TC-1..TC-10) apply only in their documented scope
  (same subject, same shot, same dialogue line). Cross-shot and
  cross-subject combinations stay allowed. A conflict is returned as
  a structured blocked diagnostic naming the rule, the skills, the
  shot, the subject and the decision required — neither skill is ever
  silently removed.
- Intent modes are enforced from the catalog: a skill that does not
  list the request's mode cannot be selected in that mode.
- Plans are deterministic: no timestamps anywhere in a plan, and the
  plan hash is the SHA-256 of the canonical JSON of the plan without
  the hash field itself.

Session handling: :func:`build_workflow_plan` requires an exact
active :class:`runtime.local_session.LocalSession`, verified with the
P1-001 verifier. Actor identity comes only from that session — never
from caller-provided owner or workspace strings.

R1 (CF-WO-P1-002-R1) hardens the router without redesigning it:
every scope reference must resolve to a request/profile subject or
shot (referential integrity); the request validator enforces the
same relevant constraints as the request and profile schemas, with
exact JSON types and boolean authorisation evidence that must be the
actual boolean ``True`` (a string such as ``"false"`` is never
approval); handoff packets are issued only for a ready step under
explicit, validated completion receipts; and the compiled catalog
carries an integrity fingerprint plus full semantic validation, so
an accidental hand edit is detected at load.
"""

from __future__ import annotations

import hashlib
import json
import os
import re

from . import local_session

CATALOG_VERSION = "2.4"
SCHEMA_VERSION = "2.4"

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_CATALOG_PATH = os.path.join(
    _REPO_ROOT, "registry", "routing-catalog.json")

# Modes that never route production work through this router.
_NON_ROUTING_MODES = frozenset({"UPLOAD_ONLY", "REPORT_UPDATE_ONLY"})
# Modes that need a production profile to route anything.
_PRODUCTION_MODES = frozenset({
    "GENERATE_FROM_SCRIPT", "EDIT_EXISTING_MEDIA", "REMAKE_OR_TRANSFORM",
    "PROJECT_CONSISTENCY", "TEMPORARY_ASSET_USE",
})
_REGISTRATION_MODES = frozenset({
    "REGISTER_CHARACTER", "REGISTER_VOICE_PROFILE", "REGISTER_SOUND_ASSET",
})
# Evidence each registration mode requires (architecture/intent-modes.yaml).
_REGISTRATION_EVIDENCE = {
    "REGISTER_CHARACTER": (
        "explicit_authorisation", "name", "unique_id", "approved_reference"),
    "REGISTER_VOICE_PROFILE": (
        "explicit_authorisation", "rights_consent", "character_link",
        "reference_audio"),
    "REGISTER_SOUND_ASSET": (
        "explicit_instruction", "source", "licence_or_permission", "owner",
        "project_scope"),
}
# Default registration chains (WORKFLOW_GRAPH.yaml sequential_chains).
_REGISTRATION_CHAINS = {
    "REGISTER_CHARACTER": ["character-consistency"],
    "REGISTER_VOICE_PROFILE": ["voice-consistency"],
    "REGISTER_SOUND_ASSET": [],
}
# The 13 intent modes (architecture/intent-modes.yaml) and the canonical
# parallel-group names (architecture/WORKFLOW_GRAPH.yaml). The catalog
# loader enforces these exact sets, so a hand-edited catalog cannot
# silently rename a mode or a group the planner switches on.
_INTENT_MODES = frozenset({
    "UPLOAD_ONLY", "TEMPORARY_ASSET_USE", "PROJECT_CONSISTENCY",
    "REGISTER_CHARACTER", "REGISTER_VOICE_PROFILE", "REGISTER_SOUND_ASSET",
    "GENERATE_FROM_SCRIPT", "EDIT_EXISTING_MEDIA", "REFERENCE_REVIEW",
    "REFERENCE_LEARN_AND_UPDATE", "VIDEO_QC", "REMAKE_OR_TRANSFORM",
    "REPORT_UPDATE_ONLY",
})
_PARALLEL_GROUP_NAMES = frozenset({
    "composable-pathways-different-shots", "foundation-planning",
    "language-and-humanization-prep", "performance-layers-different-scenes",
})
_CONDITIONAL_GROUP_NAMES = frozenset({"existing-character-prep"})
# Integrity fingerprint algorithm for the compiled catalog (Task D).
_INTEGRITY_ALGORITHM = "sha256-canonical-json-v1"
# Registration-evidence field types
# (schemas/skill-routing-request.json). The boolean fields are
# affirmative-approval evidence and must be the actual boolean True
# wherever the policy requires approval; the string fields must be
# non-empty text. A string such as "false" is never boolean evidence.
_EVIDENCE_BOOL_FIELDS = frozenset({
    "explicit_authorisation", "approved_reference", "rights_consent",
    "reference_audio", "explicit_instruction",
})
_EVIDENCE_STRING_FIELDS = frozenset({
    "name", "unique_id", "character_link", "source",
    "licence_or_permission", "owner", "project_scope",
})

_REQUEST_FIELDS = frozenset({
    "schema_version", "task_id", "intent_mode", "production_profile",
    "hints", "primary_pathway", "additional_layers", "requested_skills",
    "subjects", "shots", "dialogue_lines", "repair_authorised",
    "explicit_request", "rights_provenance_checked",
    "dialogue_rewrite_requested", "registration_evidence",
    "explicit_user_instruction",
})
_HINT_FIELDS = frozenset({
    "dialogue", "languages", "recurring_character", "explainer_structure",
    "consent", "existing_character_registered",
})
_PROFILE_FIELDS = frozenset({
    "visual_style", "production_medium", "source_media_type",
    "motion_methods", "subject_types", "interaction_pattern",
    "is_live_action_footage", "per_subject_overrides",
    "per_shot_overrides",
    # Full v2.5 profile fields (schemas/production-profile.json). The
    # router reads the routing dimensions; the record fields are
    # accepted so a validated v2.5 profile embeds unchanged.
    "name", "production_profile_id", "project_id", "schema_version",
    "skill_profiles", "status", "version",
})
_PROFILE_REQUIRED_FIELDS = (
    "schema_version", "production_profile_id", "production_medium",
    "visual_style", "source_media_type", "motion_methods",
    "subject_types", "interaction_pattern", "is_live_action_footage",
    "version", "status",
)
_SUBJECT_OVERRIDE_FIELDS = frozenset({
    "character_id", "subject_kind", "representation", "source_media",
    "rendering_style", "articulation_target", "species", "motion_methods",
    "is_live_action_footage",
})
_SHOT_OVERRIDE_FIELDS = frozenset({
    # v2.5 camera-direction fields.
    "shot_id", "camera_movement", "depth_of_field", "focus_target",
    "lighting", "transition_to_next_shot",
    # Routing extensions the router reads (not in the v2.5 schema):
    # per-shot routing scope.
    "subjects", "visual_style", "source_media", "is_live_action_footage",
})
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{2,63}$")
_SKILL_PROFILE_RE = re.compile(r"^skill-[a-z0-9][a-z0-9\-]*$")
_REQUESTED_SKILL_SOURCES = frozenset({
    "user-request", "profile-dimension", "hint", "canonical-dependency",
    "mode-default", "router-default",
})
_TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# Anatomy map for TC-10: the articulation a subject's own anatomy
# allows. None means the anatomy cannot be established from the
# supplied structured information (fail closed, never guess).
_ANATOMY_ARTICULATION = {
    "human": "human-mouth-lips",
    "digital-human": "human-mouth-lips",
    "real-animal": "animal-muzzle",
    "cgi-animal": "animal-muzzle",
    "fictional-creature": "creature-jaw-mandibles",
    "anthropomorphic": "human-mouth-lips",
}


class RoutingError(ValueError):
    """A routing request is invalid, ambiguous or contradictory.

    Raised by :func:`resolve_skills` for contradictory profiles and
    invalid requests. :func:`build_workflow_plan` converts these into
    structured blocked plans instead of raising, so a caller that
    needs a plan always gets one.
    """


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

def catalog_fingerprint(catalog: dict) -> str:
    """SHA-256 of the canonical JSON of the catalog without its own
    integrity record. The compiler
    (``scripts/generate-routing-catalog.py``) computes the same value
    over the same canonical form when it builds the catalog; the
    loader refuses any catalog whose stored fingerprint differs, so
    an accidental hand edit of the generated file is detected even
    when every semantic check would still pass. This is integrity
    against accidental / unsupported mutation, not cryptographic
    protection against a malicious process with the same OS-user
    access to the repository and the runtime source."""
    body = {k: v for k, v in catalog.items() if k != "integrity"}
    return hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest()


def load_routing_catalog(path=None) -> dict:
    """Load and verify the compiled routing catalog (stdlib JSON only).

    The catalog must be version 2.4, list exactly the 15 skills with
    unique precedence 1..15, name the same skill set as the workflow
    graph nodes, and carry the SHA-256 of every canonical source.
    Its integrity fingerprint must match its contents, and its
    complete runtime-relevant structure is validated (exact TC-1..TC-10
    rule IDs, graph edges against skill dependencies, conflict
    symmetry, mode applicability, parallel and conditional groups).
    A catalog that fails any of these checks is refused here, so a
    hand-edited catalog cannot silently change routing.
    """
    path = path or _DEFAULT_CATALOG_PATH
    try:
        with open(path, encoding="utf-8") as f:
            catalog = json.load(f)
    except OSError as exc:
        raise RoutingError(f"routing catalog not readable: {path}: {exc}")
    except json.JSONDecodeError as exc:
        raise RoutingError(f"routing catalog is not valid JSON: {exc}")
    if not isinstance(catalog, dict):
        raise RoutingError("routing catalog is not a JSON object")
    if catalog.get("catalog_version") != CATALOG_VERSION:
        raise RoutingError(
            "routing catalog version must be "
            f"'{CATALOG_VERSION}', got {catalog.get('catalog_version')!r}")
    integrity = catalog.get("integrity")
    if not isinstance(integrity, dict):
        raise RoutingError("routing catalog has no integrity record")
    if integrity.get("algorithm") != _INTEGRITY_ALGORITHM:
        raise RoutingError(
            "routing catalog integrity algorithm must be "
            f"'{_INTEGRITY_ALGORITHM}', got "
            f"{integrity.get('algorithm')!r}")
    stored = integrity.get("fingerprint")
    if not isinstance(stored, str) or not _SHA256_RE.match(stored):
        raise RoutingError(
            "routing catalog integrity fingerprint is not a SHA-256 digest")
    if catalog_fingerprint(catalog) != stored:
        raise RoutingError(
            "routing catalog integrity fingerprint does not match the "
            "catalog contents (the generated catalog was hand-edited or "
            "is stale; regenerate it with "
            "scripts/generate-routing-catalog.py)")
    skills = catalog.get("skills")
    if not isinstance(skills, list) or len(skills) != 15:
        raise RoutingError("routing catalog must list exactly 15 skills")
    slugs = set()
    precs = set()
    for entry in skills:
        if not isinstance(entry, dict):
            raise RoutingError("routing catalog skill entry is not an object")
        slug = entry.get("skill")
        if not slug or slug in slugs:
            raise RoutingError(f"routing catalog: bad or duplicate skill {slug!r}")
        slugs.add(slug)
        prec = entry.get("precedence")
        if not isinstance(prec, int) or isinstance(prec, bool):
            raise RoutingError(f"routing catalog: skill {slug} has no precedence")
        precs.add(prec)
        path_value = entry.get("path")
        sha = entry.get("sha256")
        if not isinstance(path_value, str) or not path_value:
            raise RoutingError(f"routing catalog: skill {slug} has no path")
        if not isinstance(sha, str) or not _SHA256_RE.match(sha):
            raise RoutingError(
                f"routing catalog: skill {slug} has no SHA-256 fingerprint")
    if precs != set(range(1, 16)):
        raise RoutingError(
            f"routing catalog precedence must be unique 1..15, got {sorted(precs)}")
    nodes = {n.get("id") for n in (catalog.get("graph") or {}).get("nodes") or []}
    if nodes != slugs:
        raise RoutingError(
            "routing catalog graph nodes != matrix skills: "
            f"graph-only={sorted(nodes - slugs)} "
            f"matrix-only={sorted(slugs - nodes)}")
    sources = catalog.get("sources")
    if not isinstance(sources, dict):
        raise RoutingError("routing catalog has no sources record")
    for rel in ("architecture/SKILL_ROUTING_MATRIX.yaml",
                "architecture/WORKFLOW_GRAPH.yaml",
                "architecture/intent-modes.yaml",
                "architecture/COMPANION_CAPABILITY_REGISTRY.yaml",
                "architecture/AGENT_COMPATIBILITY_MATRIX.yaml"):
        info = sources.get(rel)
        if not isinstance(info, dict) \
                or not _SHA256_RE.match(str(info.get("sha256") or "")):
            raise RoutingError(f"routing catalog has no SHA-256 for {rel}")
    vocab = catalog.get("vocabularies")
    if not isinstance(vocab, dict):
        raise RoutingError("routing catalog has no vocabularies")
    for key in ("visual_style", "production_medium", "source_media",
                "motion_method", "subject_kind", "interaction_pattern",
                "articulation_target"):
        if not vocab.get(key):
            raise RoutingError(f"routing catalog vocabulary {key} is empty")
    modes = catalog.get("intent_modes")
    if not isinstance(modes, dict) or len(modes) != 13:
        raise RoutingError("routing catalog must list exactly 13 intent modes")
    _validate_catalog_semantics(catalog)
    return catalog


def _validate_catalog_semantics(catalog: dict) -> None:
    """Semantic validation of the compiled catalog's complete
    runtime-relevant structure, beyond the counts and ID shapes the
    loader checks above. Raises RoutingError on the first defect.

    Enforced here (all grounded in the canonical records, never in
    prose): exact TC-1..TC-10 rule IDs; every matrix dependency is a
    graph edge and every non-router graph edge is a matrix dependency;
    matrix conflict symmetry; every skill lists at least one known
    mode (a skill with no applicable mode could never be selected);
    parallel and conditional groups name exactly the canonical groups
    with known, duplicate-free members and no internal dependency
    inside a parallel group; nodes, chains, cross-cutting records,
    mode records and vocabularies have their canonical shapes. The
    integrity fingerprint (checked by the loader before this runs)
    is the backstop for everything else in the file, including the
    companion and agent records the router never reads.
    """
    skills = catalog["skills"]
    by_slug = {e["skill"]: e for e in skills}
    slugs = set(by_slug)
    prec_by_skill = {e["skill"]: e["precedence"] for e in skills}
    vocab = catalog.get("vocabularies") or {}

    def _str_list(value, what):
        if not isinstance(value, list) \
                or any(not isinstance(x, str) for x in value):
            raise RoutingError(f"routing catalog: {what} is not a list "
                               "of strings")
        return value

    def _non_empty_str(value, what):
        if not isinstance(value, str) or not value.strip():
            raise RoutingError(f"routing catalog: {what} is not a "
                               "non-empty string")
        return value

    # Sources: exactly the five canonical files.
    expected_sources = {
        "architecture/SKILL_ROUTING_MATRIX.yaml",
        "architecture/WORKFLOW_GRAPH.yaml",
        "architecture/intent-modes.yaml",
        "architecture/COMPANION_CAPABILITY_REGISTRY.yaml",
        "architecture/AGENT_COMPATIBILITY_MATRIX.yaml",
    }
    if set((catalog.get("sources") or {}).keys()) != expected_sources:
        raise RoutingError(
            "routing catalog sources must be exactly the five canonical "
            "files, got "
            f"{sorted((catalog.get('sources') or {}).keys())}")

    # Intent modes: exactly the 13 modes, each with its record shape.
    modes = catalog.get("intent_modes") or {}
    if set(modes) != set(_INTENT_MODES):
        raise RoutingError(
            "routing catalog intent modes must be exactly the 13 modes, "
            f"got {sorted(modes)}")
    for name, record in modes.items():
        if not isinstance(record, dict):
            raise RoutingError(
                f"routing catalog: intent mode {name} is not an object")
        _str_list(record.get("allowed"), f"intent mode {name} allowed")
        if not record.get("allowed"):
            raise RoutingError(
                f"routing catalog: intent mode {name} allows nothing")
        if "forbidden" in record:
            _str_list(record.get("forbidden"),
                      f"intent mode {name} forbidden")
        if "requires" in record:
            _str_list(record.get("requires"),
                      f"intent mode {name} requires")
        if "dialogue_mode_default" in record:
            _non_empty_str(record.get("dialogue_mode_default"),
                           f"intent mode {name} dialogue_mode_default")
        if not isinstance(record.get("creates_permanent_record"), bool):
            raise RoutingError(
                f"routing catalog: intent mode {name} "
                "creates_permanent_record is not a boolean")

    # Vocabularies: every dimension is a non-empty list of unique
    # strings; the derived sets stay inside their parent vocabulary.
    dim_keys = ("visual_style", "production_medium", "source_media",
                "motion_method", "subject_kind", "interaction_pattern",
                "articulation_target")
    for key in dim_keys:
        values = _str_list(vocab.get(key), f"vocabulary {key}")
        if not values or len(values) != len(set(values)):
            raise RoutingError(
                f"routing catalog vocabulary {key} is empty or has "
                "duplicate values")
    for key, parent in (("cinematic_styles", "visual_style"),
                        ("animation_styles", "visual_style"),
                        ("generated_media", "production_medium"),
                        ("generated_subjects", "subject_kind")):
        values = _str_list(vocab.get(key), f"vocabulary {key}")
        if not set(values) <= set(vocab.get(parent) or []):
            raise RoutingError(
                f"routing catalog vocabulary {key} names values outside "
                f"{parent}")
    if set(vocab.get("intent_modes") or []) != set(_INTENT_MODES):
        raise RoutingError(
            "routing catalog vocabulary intent_modes must be the 13 modes")

    # Skills: identity, fingerprint, precedence, modes, dependencies,
    # conflicts (and their symmetry), routing dimensions, text fields.
    for entry in skills:
        slug = entry["skill"]
        if entry.get("skill_id") != f"skill-{slug}":
            raise RoutingError(
                f"routing catalog: skill {slug} has skill_id "
                f"{entry.get('skill_id')!r}, expected 'skill-{slug}'")
        if entry.get("path") != f"skills/{slug}/SKILL.md":
            raise RoutingError(
                f"routing catalog: skill {slug} has path "
                f"{entry.get('path')!r}")
        applicable = entry.get("applicable_modes")
        _str_list(applicable, f"skill {slug} applicable_modes")
        if not applicable:
            raise RoutingError(
                f"routing catalog: skill {slug} lists no applicable mode "
                "(it could never be selected)")
        if len(applicable) != len(set(applicable)):
            raise RoutingError(
                f"routing catalog: skill {slug} lists a mode twice")
        for mode in applicable:
            if mode not in _INTENT_MODES:
                raise RoutingError(
                    f"routing catalog: skill {slug} lists unknown mode "
                    f"{mode!r}")
        for field in ("dependencies", "conflicts"):
            values = _str_list(entry.get(field), f"skill {slug} {field}")
            if len(values) != len(set(values)):
                raise RoutingError(
                    f"routing catalog: skill {slug} lists a {field[:-1]} "
                    "twice")
            for other in values:
                if other not in slugs:
                    raise RoutingError(
                        f"routing catalog: skill {slug} names unknown "
                        f"{field[:-1]} {other!r}")
                if other == slug:
                    raise RoutingError(
                        f"routing catalog: skill {slug} lists itself in "
                        f"{field}")
        for dep in entry.get("dependencies") or []:
            if prec_by_skill[dep] >= entry["precedence"]:
                raise RoutingError(
                    f"routing catalog: skill {slug} depends on {dep}, "
                    "which does not run earlier")
        dims = entry.get("routing_dimensions")
        if dims is not None:
            if not isinstance(dims, dict):
                raise RoutingError(
                    f"routing catalog: skill {slug} routing_dimensions "
                    "is not an object")
            for key, values in dims.items():
                if key not in dim_keys:
                    raise RoutingError(
                        f"routing catalog: skill {slug} routing_dimensions "
                        f"names unknown dimension {key!r}")
                _str_list(values,
                          f"skill {slug} routing_dimensions.{key}")
                if not set(values) <= set(vocab.get(key) or []):
                    raise RoutingError(
                        f"routing catalog: skill {slug} "
                        f"routing_dimensions.{key} names values outside "
                        "the vocabulary")
        _non_empty_str(entry.get("quality_gate"),
                       f"skill {slug} quality_gate")
        _non_empty_str(entry.get("activation_trigger"),
                       f"skill {slug} activation_trigger")
        _non_empty_str(entry.get("non_trigger"),
                       f"skill {slug} non_trigger")
        for field in ("approval_conditions", "required_inputs",
                      "expected_outputs"):
            value = entry.get(field)
            if isinstance(value, list):
                for item in value:
                    if not isinstance(item, (str, dict)):
                        raise RoutingError(
                            f"routing catalog: skill {slug} {field} holds "
                            f"a non-text value {item!r}")
            elif not isinstance(value, (str, dict)):
                raise RoutingError(
                    f"routing catalog: skill {slug} {field} is not text")
        if "conflict_scope" in entry:
            _non_empty_str(entry.get("conflict_scope"),
                           f"skill {slug} conflict_scope")
    for entry in skills:
        for other in entry.get("conflicts") or []:
            if entry["skill"] not in (by_slug[other].get("conflicts") or []):
                raise RoutingError(
                    "routing catalog: conflict pair is asymmetric — "
                    f"{entry['skill']} lists {other} but {other} does not "
                    f"list {entry['skill']}")

    # Graph: nodes, edges, groups, true conflicts, chains, cross-cutting.
    graph = catalog.get("graph") or {}
    if not isinstance(graph, dict):
        raise RoutingError("routing catalog graph is not an object")
    nodes = graph.get("nodes") or []
    if not isinstance(nodes, list) or len(nodes) != 15:
        raise RoutingError("routing catalog graph must list 15 nodes")
    for node in nodes:
        if not isinstance(node, dict):
            raise RoutingError("routing catalog graph node is not an object")
        ident = node.get("id")
        if ident not in slugs:
            raise RoutingError(
                f"routing catalog graph node {ident!r} is not a skill")
        if node.get("skill") != ident:
            raise RoutingError(
                f"routing catalog graph node {ident!r} names skill "
                f"{node.get('skill')!r}")
        if node.get("precedence") != prec_by_skill[ident]:
            raise RoutingError(
                f"routing catalog graph node {ident!r} precedence "
                f"{node.get('precedence')} != skill "
                f"{prec_by_skill[ident]}")
        _non_empty_str(node.get("stage"), f"graph node {ident} stage")
    edges = graph.get("edges") or []
    if not isinstance(edges, list):
        raise RoutingError("routing catalog graph edges is not a list")
    edge_pairs: set[tuple] = set()
    for edge in edges:
        if not isinstance(edge, dict):
            raise RoutingError("routing catalog graph edge is not an object")
        src, dst = edge.get("from"), edge.get("to")
        if src not in slugs or dst not in slugs:
            raise RoutingError(
                f"routing catalog graph edge {src!r} -> {dst!r} names an "
                "unknown skill")
        if src == dst:
            raise RoutingError(
                f"routing catalog graph edge {src!r} -> {dst!r} is a "
                "self-edge")
        if (src, dst) in edge_pairs:
            raise RoutingError(
                f"routing catalog graph edge {src!r} -> {dst!r} appears "
                "twice")
        edge_pairs.add((src, dst))
        _non_empty_str(edge.get("reason"),
                       f"graph edge {src} -> {dst} reason")
    matrix_deps = {(d, e["skill"]) for e in skills
                   for d in (e.get("dependencies") or [])}
    missing = sorted(matrix_deps - edge_pairs)
    if missing:
        raise RoutingError(
            "routing catalog: matrix dependencies missing from the "
            f"workflow graph: {missing}")
    non_dep = sorted(edge_pairs - matrix_deps)
    bad = [pair for pair in non_dep if pair[0] != "command-authority"]
    if bad:
        raise RoutingError(
            "routing catalog: non-dependency graph edges must be router "
            f"edges (command-authority -> skill), got: {bad}")
    router_edges = [pair for pair in edge_pairs
                    if pair[0] == "command-authority"]
    if len(router_edges) != len(slugs) - 1 or \
            {dst for _, dst in router_edges} != (slugs - {"command-authority"}):
        raise RoutingError(
            "routing catalog: the router must edge command-authority to "
            "every other skill exactly once")
    groups = graph.get("parallel_groups") or []
    if not isinstance(groups, list):
        raise RoutingError("routing catalog parallel_groups is not a list")
    if {g.get("name") for g in groups} != set(_PARALLEL_GROUP_NAMES):
        raise RoutingError(
            "routing catalog parallel groups must be exactly "
            f"{sorted(_PARALLEL_GROUP_NAMES)}, got "
            f"{sorted(g.get('name') for g in groups if isinstance(g, dict))}")
    for group in groups:
        _validate_parallel_group(group, edge_pairs, "parallel", slugs)
    cond_groups = graph.get("conditional_parallel_groups") or []
    if not isinstance(cond_groups, list):
        raise RoutingError(
            "routing catalog conditional_parallel_groups is not a list")
    if {g.get("name") for g in cond_groups} != set(_CONDITIONAL_GROUP_NAMES):
        raise RoutingError(
            "routing catalog conditional parallel groups must be exactly "
            f"{sorted(_CONDITIONAL_GROUP_NAMES)}")
    for group in cond_groups:
        _validate_parallel_group(group, edge_pairs, "conditional", slugs)
        condition = group.get("condition")
        if not isinstance(condition, str) or len(condition.strip()) < 20:
            raise RoutingError(
                f"routing catalog conditional group {group.get('name')}: "
                "missing condition")
    tc_ids = [tc.get("id") for tc in (graph.get("true_conflicts") or [])]
    if tc_ids != [f"TC-{i}" for i in range(1, 11)]:
        raise RoutingError(
            "routing catalog true_conflicts must be exactly TC-1..TC-10 "
            f"in order, got {tc_ids}")
    for tc in graph.get("true_conflicts") or []:
        if not isinstance(tc, dict):
            raise RoutingError("routing catalog true conflict is not an object")
        members = _str_list(tc.get("skills"),
                            f"true conflict {tc.get('id')} skills")
        if len(members) < 2 or len(members) != len(set(members)):
            raise RoutingError(
                f"routing catalog true conflict {tc.get('id')} must name "
                "at least two distinct skills")
        for skill in members:
            if skill not in slugs:
                raise RoutingError(
                    f"routing catalog true conflict {tc.get('id')} names "
                    f"unknown skill {skill!r}")
        _non_empty_str(tc.get("rule"), f"true conflict {tc.get('id')} rule")
        _non_empty_str(tc.get("scope"),
                       f"true conflict {tc.get('id')} scope")
        _non_empty_str(tc.get("resolution"),
                       f"true conflict {tc.get('id')} resolution")
    chains = graph.get("sequential_chains") or []
    if not isinstance(chains, list):
        raise RoutingError("routing catalog sequential_chains is not a list")
    for chain in chains:
        if not isinstance(chain, dict):
            raise RoutingError("routing catalog sequential chain is not an object")
        _non_empty_str(chain.get("name"), "sequential chain name")
        members = _str_list(chain.get("skills"),
                            f"sequential chain {chain.get('name')} skills")
        if not members or len(members) != len(set(members)):
            raise RoutingError(
                f"routing catalog sequential chain {chain.get('name')} "
                "must name distinct skills")
        for skill in members:
            if skill not in slugs:
                raise RoutingError(
                    f"routing catalog sequential chain {chain.get('name')} "
                    f"names unknown skill {skill!r}")
    cross = graph.get("cross_cutting") or []
    if not isinstance(cross, list) or not cross:
        raise RoutingError("routing catalog cross_cutting is empty")
    for record in cross:
        if not isinstance(record, dict):
            raise RoutingError("routing catalog cross_cutting entry is not "
                               "an object")
        if record.get("skill") not in slugs:
            raise RoutingError(
                "routing catalog cross_cutting names unknown skill "
                f"{record.get('skill')!r}")
        _non_empty_str(record.get("note"), "cross_cutting note")
    # Companion and agent records are not read by the router; their
    # shape is checked lightly and the fingerprint guards the rest.
    for key in ("companions", "agents", "non_hosts"):
        records = catalog.get(key)
        if not isinstance(records, list):
            raise RoutingError(f"routing catalog {key} is not a list")
        for record in records:
            if not isinstance(record, dict) \
                    or not isinstance(record.get("name"), str) \
                    or not record["name"]:
                raise RoutingError(
                    f"routing catalog {key} entry has no name")


def _validate_parallel_group(group, edge_pairs, kind, slugs) -> None:
    """One parallel (or conditional parallel) group: a known name, at
    least two distinct known members, and — for a plain parallel
    group — no internal dependency edge between its members (members
    run together, so a dependency between them would be a
    contradiction). A conditional group may carry the edge it
    relaxes (existing-character-prep relaxes character-consistency
    -> voice-consistency), so the internal-edge rule does not apply
    there."""
    if not isinstance(group, dict):
        raise RoutingError(f"routing catalog {kind} group is not an object")
    name = group.get("name")
    if not isinstance(name, str) or not name:
        raise RoutingError(f"routing catalog {kind} group has no name")
    members = group.get("skills")
    if not isinstance(members, list) \
            or any(not isinstance(x, str) for x in members):
        raise RoutingError(
            f"routing catalog {kind} group {name}: skills is not a list "
            "of skill slugs")
    if len(members) < 2 or len(members) != len(set(members)):
        raise RoutingError(
            f"routing catalog {kind} group {name} must name at least two "
            "distinct skills")
    for skill in members:
        if skill not in slugs:
            raise RoutingError(
                f"routing catalog {kind} group {name} names unknown skill "
                f"{skill!r}")
    if kind == "parallel":
        internal = [(a, b) for a in members for b in members
                    if (a, b) in edge_pairs]
        if internal:
            raise RoutingError(
                f"routing catalog parallel group {name}: internal "
                f"dependency {internal}")


def _skills_by_slug(catalog: dict) -> dict:
    return {e["skill"]: e for e in catalog["skills"]}


def _vocab(catalog: dict, key: str) -> set:
    return set((catalog.get("vocabularies") or {}).get(key) or [])


def _mode_record(catalog: dict, mode: str) -> dict:
    return (catalog.get("intent_modes") or {}).get(mode) or {}


# ---------------------------------------------------------------------------
# Request validation
# ---------------------------------------------------------------------------

def validate_routing_request(request, catalog: dict) -> list:
    """Validate a routing request against the request schema and the
    catalog. Returns a list of error strings; an empty list means the
    request is valid. Never raises for a bad request — callers that
    need an exception use :func:`resolve_skills`.
    """
    errors: list[str] = []
    skills_by_slug = _skills_by_slug(catalog)
    modes = set((catalog.get("intent_modes") or {}).keys())

    if not isinstance(request, dict):
        return ["request is not an object"]
    unknown = sorted(set(request) - _REQUEST_FIELDS)
    if unknown:
        errors.append(f"request has unknown fields: {unknown}")
    if request.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            "schema_version must be "
            f"'{SCHEMA_VERSION}', got {request.get('schema_version')!r}")
    task_id = request.get("task_id")
    if not isinstance(task_id, str) or not _TASK_ID_RE.match(task_id):
        errors.append("task_id must be a non-empty id "
                      "(letters, digits, '.', '_' or '-', max 128 chars)")
    mode = request.get("intent_mode")
    if not isinstance(mode, str) or mode not in modes:
        errors.append(f"intent_mode {mode!r} is not one of the 13 intent modes")
        return errors  # mode-dependent checks cannot run without a mode

    profile = request.get("production_profile")
    if "production_profile" in request and profile is None:
        # R1-R2: an explicit null is not an omitted profile. The
        # schema types production_profile as object, so a null is
        # invalid even in a mode where the profile is optional.
        errors.append("production_profile must be an object, got None")
    elif mode in _PRODUCTION_MODES and profile is None:
        errors.append(
            f"production_profile is required in {mode} mode")
    if profile is not None:
        errors.extend(_validate_profile_fields(profile, catalog))

    hints = request.get("hints")
    if hints is None:
        if "hints" in request:
            # R1-R2: explicit null, not omission — the schema types
            # hints as object.
            errors.append("hints must be an object, got None")
        hints = {}
    if not isinstance(hints, dict):
        errors.append("hints is not an object")
    else:
        unknown_hints = sorted(set(hints) - _HINT_FIELDS)
        if unknown_hints:
            errors.append(f"hints has unknown fields: {unknown_hints}")
        if "dialogue" in hints and not isinstance(hints["dialogue"], bool):
            errors.append("hints.dialogue must be a boolean")
        if "languages" in hints:
            langs = hints["languages"]
            if not isinstance(langs, list) \
                    or any(not isinstance(x, str) or len(x) < 2 for x in langs):
                errors.append("hints.languages must be a list of language codes")
        for flag in ("recurring_character", "explainer_structure", "consent",
                     "existing_character_registered"):
            if flag in hints and not isinstance(hints[flag], bool):
                errors.append(f"hints.{flag} must be a boolean")

    pathway = request.get("primary_pathway")
    if "primary_pathway" in request and pathway is None:
        # R1-R2: explicit null, not omission — the schema types
        # primary_pathway as a string enum.
        errors.append("primary_pathway must be a skill slug, got None")
    if pathway is not None:
        if not isinstance(pathway, str) or pathway not in skills_by_slug:
            errors.append(f"primary_pathway {pathway!r} is not a known skill")
        elif pathway == "resource-management":
            errors.append("resource-management is cross-cutting, never a "
                          "primary pathway")
        elif pathway == "command-authority":
            errors.append("command-authority is the router itself, never a "
                          "primary pathway")
    layers = request.get("additional_layers")
    if layers is None:
        if "additional_layers" in request:
            # R1-R2: explicit null, not omission — the schema types
            # additional_layers as an array.
            errors.append("additional_layers must be a list, got None")
        layers = []
    if not isinstance(layers, list):
        errors.append("additional_layers is not a list")
    else:
        for layer in layers:
            if not isinstance(layer, str) or layer not in skills_by_slug:
                errors.append(f"additional layer {layer!r} is not a known skill")
            elif layer == "resource-management":
                errors.append("resource-management is cross-cutting, never a "
                              "standalone layer")
        if len(set(layers)) != len(layers):
            errors.append("additional_layers lists a skill twice")
        if pathway is not None and pathway in layers:
            errors.append("primary_pathway is also listed in additional_layers")

    requested = request.get("requested_skills")
    if requested is None:
        if "requested_skills" in request:
            # R1-R2: explicit null, not omission — the schema types
            # requested_skills as an array.
            errors.append("requested_skills must be a list, got None")
        requested = []
    if not isinstance(requested, list):
        errors.append("requested_skills is not a list")
    else:
        seen: set[str] = set()
        for i, item in enumerate(requested):
            if not isinstance(item, dict):
                errors.append(f"requested_skills[{i}] is not an object")
                continue
            extra_item = sorted(set(item) - {"skill", "source", "scope"})
            if extra_item:
                errors.append(f"requested_skills[{i}] has unknown fields: "
                              f"{extra_item}")
            skill = item.get("skill")
            if not isinstance(skill, str) or skill not in skills_by_slug:
                errors.append(
                    f"requested_skills[{i}].skill {skill!r} is not a known skill")
            if isinstance(skill, str):
                if skill in seen:
                    errors.append(f"requested skill {skill!r} is listed twice")
                seen.add(skill)
            source = item.get("source")
            if not isinstance(source, str) \
                    or source not in _REQUESTED_SKILL_SOURCES:
                errors.append(
                    f"requested_skills[{i}].source "
                    f"{source!r} is not a known selection source")
            scope = item.get("scope")
            if "scope" in item and scope is None:
                # R1-R2: explicit null, not omission — the schema
                # types scope as an object.
                errors.append(f"requested_skills[{i}].scope must be an "
                              "object, got None")
            elif scope is not None:
                if not isinstance(scope, dict):
                    errors.append(f"requested_skills[{i}].scope is not an object")
                else:
                    extra = sorted(set(scope) - {"shots", "subjects"})
                    if extra:
                        errors.append(
                            f"requested_skills[{i}].scope has unknown fields: {extra}")
                    for key in ("shots", "subjects"):
                        if key in scope and (
                                not isinstance(scope[key], list)
                                or any(not isinstance(x, str) for x in scope[key])):
                            errors.append(
                                f"requested_skills[{i}].scope.{key} must be a "
                                "list of ids")

    _TABLE_FIELDS = {
        "subjects": {"subject_id", "subject_kind", "articulation_target",
                     "shots", "speaking", "species"},
        "shots": {"shot_id", "visual_style", "source_media", "subject_ids",
                  "is_live_action_footage"},
    }
    for table, id_key in (("subjects", "subject_id"), ("shots", "shot_id")):
        items = request.get(table)
        if items is None:
            if table in request:
                # R1-R2: explicit null, not omission — the schema types
                # the table as an array.
                errors.append(f"{table} must be a list, got None")
            items = []
        if not isinstance(items, list):
            errors.append(f"{table} is not a list")
            continue
        seen_ids: set[str] = set()
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(f"{table}[{i}] is not an object")
                continue
            extra_item = sorted(set(item) - _TABLE_FIELDS[table])
            if extra_item:
                errors.append(f"{table}[{i}] has unknown fields: {extra_item}")
            ident = item.get(id_key)
            if not isinstance(ident, str) or not ident:
                errors.append(f"{table}[{i}] has no {id_key}")
            elif ident in seen_ids:
                errors.append(f"{table} lists {id_key} {ident!r} twice")
            else:
                seen_ids.add(ident)
    if isinstance(request.get("subjects"), list):
        for i, sub in enumerate(request["subjects"]):
            if not isinstance(sub, dict):
                continue
            kind = sub.get("subject_kind")
            if kind is not None and (
                    not isinstance(kind, str)
                    or kind not in _vocab(catalog, "subject_kind")):
                errors.append(f"subjects[{i}].subject_kind {kind!r} is not "
                              "in the fixed vocabulary")
            art = sub.get("articulation_target")
            if art is not None and (
                    not isinstance(art, str)
                    or art not in _vocab(catalog, "articulation_target")):
                errors.append(f"subjects[{i}].articulation_target {art!r} is "
                              "not in the fixed vocabulary")
            if "speaking" in sub and not isinstance(sub["speaking"], bool):
                errors.append(f"subjects[{i}].speaking must be a boolean")
            if "species" in sub and not isinstance(sub["species"], str):
                errors.append(f"subjects[{i}].species must be a string")
            for key in ("shots",):
                if key in sub and (
                        not isinstance(sub[key], list)
                        or any(not isinstance(x, str) for x in sub[key])):
                    errors.append(f"subjects[{i}].{key} must be a list of ids")
    if isinstance(request.get("shots"), list):
        for i, shot in enumerate(request["shots"]):
            if not isinstance(shot, dict):
                continue
            style = shot.get("visual_style")
            if style is not None and (
                    not isinstance(style, str)
                    or style not in _vocab(catalog, "visual_style")):
                errors.append(f"shots[{i}].visual_style {style!r} is not in "
                              "the fixed vocabulary")
            media = shot.get("source_media")
            if media is not None and (
                    not isinstance(media, str)
                    or media not in _vocab(catalog, "source_media")):
                errors.append(f"shots[{i}].source_media {media!r} is not in "
                              "the fixed vocabulary")
            if "subject_ids" in shot and (
                    not isinstance(shot["subject_ids"], list)
                    or any(not isinstance(x, str) for x in shot["subject_ids"])):
                errors.append(f"shots[{i}].subject_ids must be a list of ids")
            if "is_live_action_footage" in shot \
                    and not isinstance(shot["is_live_action_footage"], bool):
                errors.append(f"shots[{i}].is_live_action_footage must be a "
                              "boolean")

    lines = request.get("dialogue_lines")
    if lines is None:
        if "dialogue_lines" in request:
            # R1-R2: explicit null, not omission — the schema types
            # dialogue_lines as an array.
            errors.append("dialogue_lines must be a list, got None")
        lines = []
    if not isinstance(lines, list):
        errors.append("dialogue_lines is not a list")
    else:
        for i, line in enumerate(lines):
            if not isinstance(line, dict):
                errors.append(f"dialogue_lines[{i}] is not an object")
                continue
            extra_line = sorted(set(line) - {"line_id", "subject_id",
                                             "shot_id", "articulation_target"})
            if extra_line:
                errors.append(f"dialogue_lines[{i}] has unknown fields: "
                              f"{extra_line}")
            if not isinstance(line.get("line_id"), str) or not line.get("line_id"):
                errors.append(f"dialogue_lines[{i}] has no line_id")
            if not isinstance(line.get("subject_id"), str) \
                    or not line.get("subject_id"):
                errors.append(f"dialogue_lines[{i}] has no subject_id")
            if "shot_id" in line and not isinstance(line["shot_id"], str):
                errors.append(f"dialogue_lines[{i}].shot_id must be a string")
            art = line.get("articulation_target")
            if not isinstance(art, str) \
                    or art not in _vocab(catalog, "articulation_target"):
                errors.append(f"dialogue_lines[{i}].articulation_target "
                              f"{art!r} is not in the fixed vocabulary")

    for flag in ("repair_authorised", "explicit_request",
                 "rights_provenance_checked", "dialogue_rewrite_requested",
                 "explicit_user_instruction"):
        if flag in request and not isinstance(request[flag], bool):
            errors.append(f"{flag} must be a boolean")
    evidence = request.get("registration_evidence")
    if "registration_evidence" in request:
        # R1-R2: the shape validator reports an explicit null as
        # "not an object"; omission (key absent) stays valid.
        errors.extend(_validate_registration_evidence(evidence))
    errors.extend(_validate_referential_integrity(request))
    return errors


def _validate_registration_evidence(evidence) -> list:
    """Shape and type validation of registration evidence
    (schemas/skill-routing-request.json: registration_evidence,
    additionalProperties false).

    This is shape only: whether the evidence satisfies a mode's
    required fields is a policy decision made by
    :func:`build_workflow_plan`, which returns a blocked plan. A
    boolean field carrying anything but an actual bool — the string
    "false" included — is a type error here, so a string can never
    reach the policy check where Python truthiness would treat
    "false" as approval. A well-formed False is a denial, not a
    type error: it passes this check and fails the policy check.
    """
    errors: list[str] = []
    if not isinstance(evidence, dict):
        return ["registration_evidence is not an object"]
    unknown = sorted(set(evidence)
                     - _EVIDENCE_BOOL_FIELDS - _EVIDENCE_STRING_FIELDS)
    if unknown:
        errors.append(
            f"registration_evidence has unknown fields: {unknown}")
    for field in sorted(_EVIDENCE_BOOL_FIELDS):
        if field in evidence and not isinstance(evidence[field], bool):
            errors.append(
                f"registration_evidence.{field} must be a boolean, got "
                f"{evidence[field]!r} — a string such as \"false\" is never "
                "boolean authorisation evidence")
    for field in sorted(_EVIDENCE_STRING_FIELDS):
        value = evidence.get(field)
        if field in evidence and value is None:
            # R1-R2: explicit null, not omission — the schema types
            # the field as a string.
            errors.append(
                f"registration_evidence.{field} must be a non-empty "
                "string, got None")
        elif value is not None \
                and (not isinstance(value, str) or not value):
            errors.append(
                f"registration_evidence.{field} must be a non-empty string")
    return errors


def _validate_referential_integrity(request) -> list:
    """Referential integrity of every scope reference in the request
    (Task A). The canonical request-local reference sets are the
    union of the profile's per-subject override character IDs and
    per-shot override shot IDs with the request's own subject and
    shot tables. Every scope, subject, shot, dialogue-line and
    override reference must resolve into those sets; a reference
    that does not resolve is a validation error, never a silently
    dropped scope — an invalid scope must not produce a ready plan.
    Duplicate IDs inside the profile override tables are ambiguous
    and rejected (the request tables are already duplicate-checked
    by the structural validation above; a profile override and a
    request table entry sharing one ID is the documented merge, not
    a duplicate).
    """
    errors: list[str] = []
    profile = request.get("production_profile")
    if not isinstance(profile, dict):
        profile = {}
    subjects: set[str] = set()
    shots: set[str] = set()
    for i, sub in enumerate(profile.get("per_subject_overrides") or []):
        if not isinstance(sub, dict):
            continue
        ident = sub.get("character_id")
        if not isinstance(ident, str) or not ident:
            continue
        if ident in subjects:
            errors.append(
                "production_profile.per_subject_overrides lists "
                f"character_id {ident!r} twice")
        subjects.add(ident)
    for i, shot in enumerate(profile.get("per_shot_overrides") or []):
        if not isinstance(shot, dict):
            continue
        ident = shot.get("shot_id")
        if not isinstance(ident, str) or not ident:
            continue
        if ident in shots:
            errors.append(
                "production_profile.per_shot_overrides lists shot_id "
                f"{ident!r} twice")
        shots.add(ident)
    for sub in request.get("subjects") or []:
        if isinstance(sub, dict):
            ident = sub.get("subject_id")
            if isinstance(ident, str) and ident:
                subjects.add(ident)
    for shot in request.get("shots") or []:
        if isinstance(shot, dict):
            ident = shot.get("shot_id")
            if isinstance(ident, str) and ident:
                shots.add(ident)

    def _check_subjects(values, where):
        for value in values or []:
            if isinstance(value, str) and value not in subjects:
                errors.append(
                    f"{where} {value!r} does not resolve to a request or "
                    "profile subject")

    def _check_shots(values, where):
        for value in values or []:
            if isinstance(value, str) and value not in shots:
                errors.append(
                    f"{where} {value!r} does not resolve to a request or "
                    "profile shot")

    for i, item in enumerate(request.get("requested_skills") or []):
        if not isinstance(item, dict):
            continue
        scope = item.get("scope")
        if isinstance(scope, dict):
            _check_subjects(scope.get("subjects"),
                            f"requested_skills[{i}].scope.subjects entry")
            _check_shots(scope.get("shots"),
                         f"requested_skills[{i}].scope.shots entry")
    for i, sub in enumerate(request.get("subjects") or []):
        if isinstance(sub, dict):
            _check_shots(sub.get("shots"), f"subjects[{i}].shots entry")
    for i, shot in enumerate(request.get("shots") or []):
        if isinstance(shot, dict):
            _check_subjects(shot.get("subject_ids"),
                            f"shots[{i}].subject_ids entry")
    for i, line in enumerate(request.get("dialogue_lines") or []):
        if not isinstance(line, dict):
            continue
        subject = line.get("subject_id")
        if isinstance(subject, str) and subject \
                and subject not in subjects:
            errors.append(
                f"dialogue_lines[{i}].subject_id {subject!r} does not "
                "resolve to a request or profile subject")
        shot = line.get("shot_id")
        if isinstance(shot, str) and shot and shot not in shots:
            errors.append(
                f"dialogue_lines[{i}].shot_id {shot!r} does not resolve "
                "to a request or profile shot")
    for i, shot in enumerate(profile.get("per_shot_overrides") or []):
        if isinstance(shot, dict):
            _check_subjects(
                shot.get("subjects"),
                f"per_shot_overrides[{i}].subjects entry")
    return errors


def _validate_profile_fields(profile, catalog: dict) -> list:
    """Structural checks on the embedded production profile: it must
    be a validated v2.5 profile (schemas/production-profile.json),
    plus the per-shot routing extensions the router reads."""
    errors: list[str] = []
    if not isinstance(profile, dict):
        return ["production_profile is not an object"]
    unknown = sorted(set(profile) - _PROFILE_FIELDS)
    if unknown:
        errors.append(f"production_profile has unknown fields: {unknown}")
    for field in _PROFILE_REQUIRED_FIELDS:
        if field not in profile:
            errors.append(
                f"production_profile is missing required v2.5 field '{field}'")
    if profile.get("schema_version") != "2.5":
        errors.append(
            "production_profile.schema_version must be '2.5', got "
            f"{profile.get('schema_version')!r}")
    for field in ("production_profile_id", "project_id"):
        value = profile.get(field)
        if value is not None and (
                not isinstance(value, str) or not _ID_RE.match(value)):
            errors.append(
                f"production_profile.{field} {value!r} is not a valid id")
    if "production_profile_id" in profile \
            and profile.get("production_profile_id") is None:
        errors.append(
            "production_profile.production_profile_id must be a valid id, "
            "got None")
    if "project_id" in profile and profile.get("project_id") is None:
        # R1-R2: explicit null, not omission — the schema types
        # project_id as a string.
        errors.append(
            "production_profile.project_id must be a valid id, got None")
    version = profile.get("version")
    if not isinstance(version, int) or isinstance(version, bool) \
            or version < 1:
        errors.append("production_profile.version must be an integer >= 1")
    status = profile.get("status")
    if status not in ("draft", "approved", "deprecated"):
        errors.append(
            f"production_profile.status {status!r} is not draft, approved "
            "or deprecated")
    name = profile.get("name")
    if "name" in profile and name is None:
        # R1-R2: explicit null, not omission — the schema types name
        # as a non-empty string.
        errors.append(
            "production_profile.name must be a non-empty string, got None")
    elif name is not None and (not isinstance(name, str) or not name):
        errors.append("production_profile.name must be a non-empty string")
    skill_profiles = profile.get("skill_profiles")
    if skill_profiles is None:
        if "skill_profiles" in profile:
            # R1-R2: explicit null, not omission — the schema types
            # skill_profiles as an array.
            errors.append("production_profile.skill_profiles must be a "
                          "list, got None")
        skill_profiles = []
    if not isinstance(skill_profiles, list):
        errors.append("production_profile.skill_profiles is not a list")
    else:
        for value in skill_profiles:
            if not isinstance(value, str) or not _SKILL_PROFILE_RE.match(value):
                errors.append(
                    f"production_profile.skill_profiles value {value!r} is "
                    "not a skill slug")
    for key, vocab_key in (
            ("visual_style", "visual_style"),
            ("production_medium", "production_medium"),
            ("source_media_type", "source_media"),
            ("interaction_pattern", "interaction_pattern")):
        if key not in profile:
            continue
        value = profile.get(key)
        if not isinstance(value, str) \
                or value not in _vocab(catalog, vocab_key):
            errors.append(
                f"production_profile.{key} {value!r} is not in the fixed "
                "vocabulary")
    for key, vocab_key in (
            ("motion_methods", "motion_method"),
            ("subject_types", "subject_kind")):
        values = profile.get(key) or []
        if not isinstance(values, list):
            errors.append(f"production_profile.{key} is not a list")
        else:
            if not values:
                errors.append(
                    f"production_profile.{key} must name at least one value")
            for value in values:
                if not isinstance(value, str) \
                        or value not in _vocab(catalog, vocab_key):
                    errors.append(
                        f"production_profile.{key} value {value!r} is not in "
                        "the fixed vocabulary")
    if "is_live_action_footage" in profile \
            and not isinstance(profile["is_live_action_footage"], bool):
        errors.append("production_profile.is_live_action_footage must be a "
                      "boolean")
    overrides = profile.get("per_subject_overrides")
    if overrides is None:
        if "per_subject_overrides" in profile:
            # R1-R2: explicit null, not omission — the schema types
            # per_subject_overrides as an array.
            errors.append("production_profile.per_subject_overrides must "
                          "be a list, got None")
        overrides = []
    if not isinstance(overrides, list):
        errors.append("production_profile.per_subject_overrides is not a list")
    else:
        for i, sub in enumerate(overrides):
            if not isinstance(sub, dict):
                errors.append(f"per_subject_overrides[{i}] is not an object")
                continue
            unknown_sub = sorted(set(sub) - _SUBJECT_OVERRIDE_FIELDS)
            if unknown_sub:
                errors.append(f"per_subject_overrides[{i}] has unknown "
                              f"fields: {unknown_sub}")
            character = sub.get("character_id")
            if not isinstance(character, str) or not _ID_RE.match(character):
                errors.append(f"per_subject_overrides[{i}].character_id "
                              f"{character!r} is not a valid id")
            if "species" in sub and not isinstance(sub["species"], str):
                errors.append(f"per_subject_overrides[{i}].species must be "
                              "a string")
            for key, vocab_key in (
                    ("subject_kind", "subject_kind"),
                    ("representation", "production_medium"),
                    ("source_media", "source_media"),
                    ("rendering_style", "visual_style"),
                    ("articulation_target", "articulation_target")):
                value = sub.get(key)
                if value is not None and (
                        not isinstance(value, str)
                        or value not in _vocab(catalog, vocab_key)):
                    errors.append(f"per_subject_overrides[{i}].{key} "
                                  f"{value!r} is not in the fixed vocabulary")
            motions = sub.get("motion_methods") or []
            if not isinstance(motions, list):
                errors.append(f"per_subject_overrides[{i}].motion_methods "
                              "is not a list")
            else:
                for value in motions:
                    if not isinstance(value, str) \
                            or value not in _vocab(catalog, "motion_method"):
                        errors.append(f"per_subject_overrides[{i}].motion_methods "
                                      f"value {value!r} is not in the fixed "
                                      "vocabulary")
    shot_overrides = profile.get("per_shot_overrides")
    if shot_overrides is None:
        if "per_shot_overrides" in profile:
            # R1-R2: explicit null, not omission — the schema types
            # per_shot_overrides as an array.
            errors.append("production_profile.per_shot_overrides must be "
                          "a list, got None")
        shot_overrides = []
    if not isinstance(shot_overrides, list):
        errors.append("production_profile.per_shot_overrides is not a list")
    else:
        for i, shot in enumerate(shot_overrides):
            if not isinstance(shot, dict):
                errors.append(f"per_shot_overrides[{i}] is not an object")
                continue
            unknown_shot = sorted(set(shot) - _SHOT_OVERRIDE_FIELDS)
            if unknown_shot:
                errors.append(f"per_shot_overrides[{i}] has unknown fields: "
                              f"{unknown_shot}")
            if not isinstance(shot.get("shot_id"), str) or not shot.get("shot_id"):
                errors.append(f"per_shot_overrides[{i}] has no shot_id")
            style = shot.get("visual_style")
            if style is not None and (
                    not isinstance(style, str)
                    or style not in _vocab(catalog, "visual_style")):
                errors.append(f"per_shot_overrides[{i}].visual_style "
                              f"{style!r} is not in the fixed vocabulary")
            media = shot.get("source_media")
            if media is not None and (
                    not isinstance(media, str)
                    or media not in _vocab(catalog, "source_media")):
                errors.append(f"per_shot_overrides[{i}].source_media "
                              f"{media!r} is not in the fixed vocabulary")
            movement = shot.get("camera_movement")
            if movement is not None and movement not in (
                    "static", "pan", "tilt", "tracking", "dolly-in",
                    "dolly-out", "push-in", "pull-back", "follow",
                    "handheld"):
                errors.append(f"per_shot_overrides[{i}].camera_movement "
                              f"{movement!r} is not a v2.5 camera movement")
            depth = shot.get("depth_of_field")
            if depth is not None \
                    and depth not in ("shallow", "deep", "rack-focus"):
                errors.append(f"per_shot_overrides[{i}].depth_of_field "
                              f"{depth!r} is not a v2.5 depth of field")
            if "is_live_action_footage" in shot \
                    and not isinstance(shot["is_live_action_footage"], bool):
                errors.append(f"per_shot_overrides[{i}].is_live_action_footage "
                              "must be a boolean")
            for key in ("focus_target", "lighting",
                        "transition_to_next_shot"):
                if key in shot and not isinstance(shot[key], str):
                    errors.append(f"per_shot_overrides[{i}].{key} must be a "
                                  "string")
            subjects = shot.get("subjects")
            if subjects is not None and (
                    not isinstance(subjects, list)
                    or any(not isinstance(x, str) for x in subjects)):
                errors.append(f"per_shot_overrides[{i}].subjects must be a "
                              "list of ids")
    return errors


# ---------------------------------------------------------------------------
# Profile semantics (the promoted P0 routing helper)
# ---------------------------------------------------------------------------

def _vocab_or_raise(name, value, allowed):
    if value not in allowed:
        raise RoutingError(f"{name} {value!r} is not in the fixed vocabulary")


def _validate_profile_semantics(profile, catalog: dict) -> dict:
    """Semantic profile checks (P0 routing helper, promoted verbatim).

    Raises RoutingError on a contradictory profile instead of silently
    picking a side. Returns the derived facts the selection rules need:
    effective styles, subject kinds, the digital-human predicate and
    the live-action predicate.
    """
    if "animation_type" in profile:
        raise RoutingError("single animation_type enum is withdrawn; "
                           "use the separate dimensions")
    style = profile.get("visual_style")
    if style is None:
        raise RoutingError("visual_style is required: no style is ever "
                           "inferred, and cartoon is never the default")
    _vocab_or_raise("visual_style", style, _vocab(catalog, "visual_style"))
    medium = profile.get("production_medium")
    _vocab_or_raise("production_medium", medium,
                    _vocab(catalog, "production_medium"))
    source = profile.get("source_media_type")
    _vocab_or_raise("source_media_type", source, _vocab(catalog, "source_media"))
    motions = profile.get("motion_methods") or []
    for value in motions:
        _vocab_or_raise("motion_method", value, _vocab(catalog, "motion_method"))
    subjects = set(profile.get("subject_types") or [])
    for value in subjects:
        _vocab_or_raise("subject_kind", value, _vocab(catalog, "subject_kind"))
    _vocab_or_raise("interaction_pattern", profile.get("interaction_pattern"),
                    _vocab(catalog, "interaction_pattern"))
    overrides = profile.get("per_subject_overrides") or []
    for sub in overrides:
        kind = sub.get("subject_kind")
        if kind is not None:
            _vocab_or_raise("subject_kind", kind, _vocab(catalog, "subject_kind"))
            subjects.add(kind)
        if sub.get("representation") is not None:
            _vocab_or_raise("representation", sub["representation"],
                            _vocab(catalog, "production_medium"))
        if sub.get("source_media") is not None:
            _vocab_or_raise("source_media", sub["source_media"],
                            _vocab(catalog, "source_media"))
        art = sub.get("articulation_target")
        if art is not None:
            _vocab_or_raise("articulation_target", art,
                            _vocab(catalog, "articulation_target"))
            species = (sub.get("species") or "").lower()
            if ("bird" in species or "parrot" in species) \
                    and art == "human-mouth-lips":
                raise RoutingError(
                    "a bird never uses human lip movement: "
                    f"{sub.get('character_id')} needs bird-beak articulation")
        if sub.get("rendering_style") is not None:
            _vocab_or_raise("rendering_style", sub["rendering_style"],
                            _vocab(catalog, "visual_style"))
    # Pure captured footage needs no motion-generation method; anything
    # generated must name at least one.
    generated_media = _vocab(catalog, "generated_media")
    generated_subjects = _vocab(catalog, "generated_subjects")
    generated_here = medium in generated_media \
        or bool(subjects & generated_subjects) \
        or medium == "hybrid-live-action-cgi"
    if not motions and generated_here:
        raise RoutingError("motion_methods required for a generated subject")
    # Provenance: a generated subject is NEVER live-action footage.
    is_live = profile.get("is_live_action_footage")
    if is_live and (medium in generated_media
                    or medium == "hybrid-live-action-cgi"
                    or subjects & generated_subjects):
        raise RoutingError("generated subjects are never live-action footage")
    for sub in overrides:
        if sub.get("is_live_action_footage") and (
                sub.get("representation") in generated_media
                or sub.get("subject_kind") in generated_subjects):
            raise RoutingError(
                f"generated subject {sub.get('character_id')} is never "
                "live-action footage")
    # True conflict (TC-9 at production level): one shot cannot be both
    # flat 2D vector and captured live-action footage.
    eff_styles = {style} if style != "mixed" else {
        sub["rendering_style"] for sub in overrides
        if sub.get("rendering_style")}
    if "flat-2d-vector" in eff_styles and is_live:
        raise RoutingError("one shot cannot be both flat 2D vector and "
                           "captured live-action footage")
    digital_human = any(
        sub.get("subject_kind") == "digital-human"
        and sub.get("representation") == "ai-digital-human"
        and sub.get("source_media") == "reference-image"
        for sub in overrides) or (
            medium == "ai-digital-human" and source == "reference-image"
            and style == "photorealistic-digital-human")
    return {
        "visual_style": style,
        "production_medium": medium,
        "source_media_type": source,
        "motion_methods": list(motions),
        "subject_kinds": subjects,
        "interaction_pattern": profile.get("interaction_pattern"),
        "is_live_action_footage": bool(is_live),
        "effective_styles": eff_styles,
        "digital_human": digital_human,
        "overrides": overrides,
    }


def _subject_table(request, profile_facts) -> list:
    """Merge the profile's per-subject overrides with the request's
    per-subject scope table into one subject list. The request table
    wins on a shared subject id; the profile wins for fields the
    request table does not state.
    """
    subjects: dict[str, dict] = {}
    for sub in profile_facts["overrides"]:
        ident = sub.get("character_id")
        if not ident:
            continue
        subjects[ident] = {
            "subject_id": ident,
            "subject_kind": sub.get("subject_kind"),
            "representation": sub.get("representation"),
            "source_media": sub.get("source_media"),
            "rendering_style": sub.get("rendering_style"),
            "articulation_target": sub.get("articulation_target"),
            "species": sub.get("species"),
            "motion_methods": list(sub.get("motion_methods") or []),
            "is_live_action_footage": bool(sub.get("is_live_action_footage")),
            "speaking": None,
            "shots": [],
        }
    for sub in request.get("subjects") or []:
        ident = sub.get("subject_id")
        if not ident:
            continue
        merged = subjects.get(ident, {
            "subject_id": ident,
            "subject_kind": None,
            "representation": None,
            "source_media": None,
            "rendering_style": None,
            "articulation_target": None,
            "species": None,
            "motion_methods": [],
            "is_live_action_footage": False,
            "speaking": None,
            "shots": [],
        })
        for key in ("subject_kind", "articulation_target", "species",
                    "speaking"):
            if sub.get(key) is not None:
                merged[key] = sub[key]
        if sub.get("shots"):
            merged["shots"] = list(sub["shots"])
        subjects[ident] = merged
    return [subjects[key] for key in sorted(subjects)]


def _shot_table(request, profile) -> list:
    """Merge the profile's per-shot overrides with the request's
    per-shot scope table into one shot list."""
    shots: dict[str, dict] = {}
    for shot in (profile or {}).get("per_shot_overrides") or []:
        ident = shot.get("shot_id")
        if not ident:
            continue
        shots[ident] = {
            "shot_id": ident,
            "subject_ids": list(shot.get("subjects") or []),
            "visual_style": shot.get("visual_style"),
            "source_media": shot.get("source_media"),
            "is_live_action_footage": bool(shot.get("is_live_action_footage")),
        }
    for shot in request.get("shots") or []:
        ident = shot.get("shot_id")
        if not ident:
            continue
        merged = shots.get(ident, {
            "shot_id": ident,
            "subject_ids": [],
            "visual_style": None,
            "source_media": None,
            "is_live_action_footage": False,
        })
        for key in ("visual_style", "source_media", "is_live_action_footage"):
            if shot.get(key) is not None:
                merged[key] = shot[key]
        if shot.get("subject_ids"):
            merged["subject_ids"] = list(shot["subject_ids"])
        shots[ident] = merged
    return [shots[key] for key in sorted(shots)]


def _effective_style_for_shot(shot, profile_facts, subjects) -> str | None:
    """The effective visual style of one shot: the shot's own style,
    else the production style, else (for a mixed production) the
    rendering style of the subjects in the shot, if they agree."""
    if shot.get("visual_style"):
        return shot["visual_style"]
    style = profile_facts["visual_style"]
    if style != "mixed":
        return style
    styles = {s.get("rendering_style") for s in subjects
              if s.get("rendering_style")
              and (not shot.get("subject_ids")
                   or s["subject_id"] in shot["subject_ids"])}
    if len(styles) == 1:
        return next(iter(styles))
    return None


def _effective_style_for_subject(subject, profile_facts) -> str | None:
    if subject.get("rendering_style"):
        return subject["rendering_style"]
    style = profile_facts["visual_style"]
    return None if style == "mixed" else style

# ---------------------------------------------------------------------------
# Scope claims: which (subject, shot) pairs a selected skill applies to
# ---------------------------------------------------------------------------
# A claim is a (subject_id, shot_id) pair; None is a wildcard meaning
# "every subject" or "every shot". Two skills conflict in a scope only
# when their claim sets intersect on a pair the TC rule actually
# covers — a production-wide claim intersects everything, a scoped
# claim only its own shots and subjects.

def _claims_for_skill(skill, request, profile_facts, subjects, shots,
                      explicit_scope, style_sets) -> set:
    """Claim set for one selected skill.

    explicit_scope is the scope the request gave for this skill
    (requested_skills scope, or the primary_pathway/additional_layers
    scope, which is production-wide). Profile-derived claims come from
    the skill's own selection predicate; a skill with no predicate
    and no explicit scope claims the whole production.
    """
    if explicit_scope is not None:
        scope_shots = explicit_scope.get("shots") or []
        scope_subjects = explicit_scope.get("subjects") or []
        if not scope_shots and not scope_subjects:
            return {(None, None)}
        pairs = set()
        for subject in scope_subjects or [None]:
            for shot in scope_shots or [None]:
                pairs.add((subject, shot))
        return pairs
    profile = request.get("production_profile") or {}
    medium = profile_facts["production_medium"] if profile_facts else None
    source = profile_facts["source_media_type"] if profile_facts else None
    is_live = profile_facts["is_live_action_footage"] if profile_facts else False
    cinematic_styles = style_sets["cinematic"]
    if skill == "realistic-person":
        pairs = set()
        for sub in subjects:
            if sub.get("subject_kind") == "digital-human" \
                    and sub.get("representation") == "ai-digital-human" \
                    and sub.get("source_media") == "reference-image":
                for shot in sub.get("shots") or [None]:
                    pairs.add((sub["subject_id"], shot))
        if not pairs and profile_facts and profile_facts["digital_human"]:
            kinds = {s.get("subject_kind") for s in subjects}
            if "digital-human" in kinds:
                for sub in subjects:
                    if sub.get("subject_kind") == "digital-human":
                        pairs.add((sub["subject_id"], None))
            else:
                pairs.add((None, None))
        return pairs or {(None, None)}
    if skill == "live-action-vfx":
        pairs = set()
        for sub in subjects:
            if sub.get("is_live_action_footage") \
                    or sub.get("representation") == "live-action-footage":
                for shot in sub.get("shots") or [None]:
                    pairs.add((sub["subject_id"], shot))
        for shot in shots:
            if shot.get("is_live_action_footage"):
                for subject in shot.get("subject_ids") or [None]:
                    pairs.add((subject, shot["shot_id"]))
        if not pairs and (is_live or source == "captured-footage"):
            pairs.add((None, None))
        return pairs or {(None, None)}
    if skill == "explainer-animation":
        pairs = set()
        for shot in shots:
            style = _effective_style_for_shot(shot, profile_facts, subjects)
            if style == "flat-2d-vector":
                for subject in shot.get("subject_ids") or [None]:
                    pairs.add((subject, shot["shot_id"]))
        if not pairs and profile_facts \
                and "flat-2d-vector" in profile_facts["effective_styles"]:
            pairs.add((None, None))
        return pairs or {(None, None)}
    if skill == "cinematic-power":
        pairs = set()
        for sub in subjects:
            if sub.get("subject_kind") in (
                    "cgi-animal", "fictional-creature", "anthropomorphic"):
                for shot in sub.get("shots") or [None]:
                    pairs.add((sub["subject_id"], shot))
        for shot in shots:
            style = _effective_style_for_shot(shot, profile_facts, subjects)
            if style in cinematic_styles:
                for subject in shot.get("subject_ids") or [None]:
                    pairs.add((subject, shot["shot_id"]))
        if not pairs and profile_facts \
                and profile_facts["effective_styles"] & cinematic_styles:
            pairs.add((None, None))
        return pairs or {(None, None)}
    if skill == "kids-family-animation":
        pairs = set()
        kids_styles = style_sets["kids"]
        for sub in subjects:
            style = _effective_style_for_subject(sub, profile_facts)
            if style in kids_styles:
                for shot in sub.get("shots") or [None]:
                    pairs.add((sub["subject_id"], shot))
        return pairs or {(None, None)}
    # Layers and the router apply to the whole production.
    return {(None, None)}


def _scopes_intersect(a: set, b: set) -> list:
    """Intersecting (subject, shot) pairs between two claim sets,
    with None as a wildcard. Returns the intersecting pairs, with a
    wildcard resolved to None where the other side did not name one.
    """
    found = []
    for s1, t1 in sorted(a, key=lambda p: (str(p[0]), str(p[1]))):
        for s2, t2 in sorted(b, key=lambda p: (str(p[0]), str(p[1]))):
            if (s1 is None or s2 is None or s1 == s2) \
                    and (t1 is None or t2 is None or t1 == t2):
                subject = s1 if s1 is not None else s2
                shot = t1 if t1 is not None else t2
                pair = (subject, shot)
                if pair not in found:
                    found.append(pair)
    return found


def _tc_diagnostic(rule_id, skills, pair, required_input, resolution):
    subject, shot = pair
    return {
        "rule_id": rule_id,
        "skills": sorted(skills),
        "shot_id": shot,
        "subject_id": subject,
        "decision": resolution,
        "required_input": required_input,
    }


def _check_true_conflicts(selected, claims, request, profile_facts,
                          subjects, shots, catalog, style_sets,
                          explicit_scopes=None) -> list:
    """Evaluate TC-1..TC-10 over the selected skills' claims. Returns
    structured blocked diagnostics; an empty list means no conflict
    fires. Neither skill in a conflict is ever removed.
    """
    blocked: list[dict] = []
    tc_by_id = {tc["id"]: tc
                for tc in (catalog.get("graph") or {}).get("true_conflicts") or []}
    hints = request.get("hints") or {}
    dialogue = bool(hints.get("dialogue"))

    def fires(rule_id, skills, pairs):
        tc = tc_by_id.get(rule_id) or {}
        for pair in pairs:
            blocked.append(_tc_diagnostic(
                rule_id, skills, pair,
                tc.get("resolution", ""),
                tc.get("resolution", "")))
        return pairs

    # TC-2: live-action footage vs generated digital human, same subject,
    # same shot (matrix blocking pair).
    if {"live-action-vfx", "realistic-person"} <= selected:
        pairs = _scopes_intersect(claims["live-action-vfx"],
                                  claims["realistic-person"])
        if pairs:
            fires("TC-2", ["live-action-vfx", "realistic-person"], pairs)
    # TC-4: flat-2D explainer vs photorealistic digital human, same
    # subject, same shot (matrix blocking pair).
    if {"explainer-animation", "realistic-person"} <= selected:
        pairs = _scopes_intersect(claims["explainer-animation"],
                                  claims["realistic-person"])
        if pairs:
            fires("TC-4", ["explainer-animation", "realistic-person"], pairs)
    # TC-1: a REAL animal directed to speak (anthropomorphic direction)
    # vs real behaviour cut from footage. A CGI creature speaking is
    # cinematic-power creature performance, not this conflict.
    if {"live-action-vfx", "cinematic-power"} <= selected and dialogue:
        pairs = _scopes_intersect(claims["live-action-vfx"],
                                  claims["cinematic-power"])
        speaking_real_animals = []
        for sub in subjects:
            if sub.get("subject_kind") != "real-animal":
                continue
            speaks = sub.get("speaking") is True \
                or any(line.get("subject_id") == sub["subject_id"]
                       for line in (request.get("dialogue_lines") or [])) \
                or sub.get("articulation_target") is not None
            if speaks:
                speaking_real_animals.append(sub["subject_id"])
        for subject, shot in pairs:
            if subject in speaking_real_animals:
                fires("TC-1", ["live-action-vfx", "cinematic-power"],
                      [(subject, shot)])
    # TC-3 / TC-5: two style locks on one NAMED shot. A lock covers a
    # shot when the shot's effective style is the lock's style, or
    # when the skill was explicitly requested for that shot. A
    # production-wide claim never locks a shot on its own: a mixed
    # production holds different styles on different subjects, and
    # without shot scope the router cannot prove they share a shot —
    # a conflict exists only when two rules genuinely cannot both
    # hold for the same subject in the same shot.
    explicit_scopes = explicit_scopes or {}

    def _locks_shot(skill, shot_id, lock_styles):
        shot = next((s for s in shots if s["shot_id"] == shot_id), None)
        if shot is not None:
            style = _effective_style_for_shot(shot, profile_facts, subjects)
            if style in lock_styles:
                return True
        scope = explicit_scopes.get(skill) or {}
        return shot_id in (scope.get("shots") or [])

    if {"explainer-animation", "cinematic-power"} <= selected and shots:
        for shot in shots:
            shot_id = shot["shot_id"]
            if _locks_shot("explainer-animation", shot_id,
                           {"flat-2d-vector"}) \
                    and _locks_shot("cinematic-power", shot_id,
                                    style_sets["cinematic"]):
                fires("TC-3", ["explainer-animation", "cinematic-power"],
                      [(None, shot_id)])
    if {"explainer-animation", "kids-family-animation"} <= selected and shots:
        for shot in shots:
            shot_id = shot["shot_id"]
            if _locks_shot("explainer-animation", shot_id,
                           {"flat-2d-vector"}) \
                    and _locks_shot("kids-family-animation", shot_id,
                                    style_sets["kids"]):
                fires("TC-5", ["explainer-animation", "kids-family-animation"],
                      [(None, shot_id)])
    # TC-6: animated character vs photorealistic digital human, same
    # subject, same shot.
    if {"kids-family-animation", "realistic-person"} <= selected:
        pairs = _scopes_intersect(claims["kids-family-animation"],
                                  claims["realistic-person"])
        if pairs:
            fires("TC-6", ["kids-family-animation", "realistic-person"], pairs)
    # TC-7: 2D/3D-animation styling vs photorealistic digital human,
    # same subject, same shot. The intersecting subject's effective
    # style must be animation styling for the conflict to fire.
    if {"cinematic-power", "realistic-person"} <= selected:
        pairs = _scopes_intersect(claims["cinematic-power"],
                                  claims["realistic-person"])
        subject_style = {s["subject_id"]: _effective_style_for_subject(
            s, profile_facts) for s in subjects}
        for subject, shot in pairs:
            if subject is not None \
                    and subject_style.get(subject) in style_sets["animation"]:
                fires("TC-7", ["cinematic-power", "realistic-person"],
                      [(subject, shot)])
    # TC-8: synthetic spokesperson vs real-person digital human, same
    # subject.
    if {"agency-advertising", "realistic-person"} <= selected:
        pairs = _scopes_intersect(claims["agency-advertising"],
                                  claims["realistic-person"])
        if pairs:
            fires("TC-8", ["agency-advertising", "realistic-person"], pairs)
    # TC-9: flat-2D explainer vs captured live-action footage, same
    # shot (per-shot overrides; the production-level case is already
    # refused by profile validation).
    if {"explainer-animation", "live-action-vfx"} <= selected:
        for shot in shots:
            style = _effective_style_for_shot(shot, profile_facts, subjects)
            if style == "flat-2d-vector" and shot.get("is_live_action_footage"):
                fires("TC-9", ["explainer-animation", "live-action-vfx"],
                      [(None, shot["shot_id"])])
    # TC-10: articulation must match the subject's own anatomy, per
    # subject per dialogue line. Fails closed when the anatomy cannot
    # be established for a speaking subject.
    blocked.extend(_check_articulation(
        request, profile_facts, subjects, tc_by_id.get("TC-10") or {}))
    return blocked


def _expected_articulation(subject) -> str | None:
    """The articulation a subject's anatomy allows, or None when the
    anatomy cannot be established from structured information."""
    kind = subject.get("subject_kind")
    if kind in _ANATOMY_ARTICULATION:
        if kind in ("real-animal", "cgi-animal"):
            species = (subject.get("species") or "").lower()
            if "bird" in species or "parrot" in species:
                return "bird-beak"
        return _ANATOMY_ARTICULATION[kind]
    return None


def _check_articulation(request, profile_facts, subjects, tc10) -> list:
    blocked: list[dict] = []
    hints = request.get("hints") or {}
    dialogue = bool(hints.get("dialogue"))
    lines = request.get("dialogue_lines") or []

    def _fail(subject_id, shot_id, articulation, expected):
        if expected is None:
            required = (
                "the subject's anatomy (subject_kind or species) or an "
                "explicit articulation_target — the anatomy cannot be "
                "established from the supplied information, so the line "
                "cannot be routed")
        else:
            required = (
                f"articulation_target {expected} for this subject "
                f"(its anatomy allows {expected}, not {articulation})")
        blocked.append({
            "rule_id": "TC-10",
            "skills": sorted(tc10.get("skills") or [
                "character-consistency", "voice-consistency",
                "language-authenticity"]),
            "shot_id": shot_id,
            "subject_id": subject_id,
            "decision": tc10.get("resolution", ""),
            "required_input": required,
        })

    by_id = {s["subject_id"]: s for s in subjects}
    speaking_ids = set()
    for sub in subjects:
        if sub.get("speaking") is True:
            speaking_ids.add(sub["subject_id"])
    for line in lines:
        speaking_ids.add(line.get("subject_id"))
    if dialogue:
        for sub in subjects:
            if sub.get("articulation_target") is not None:
                speaking_ids.add(sub["subject_id"])
    # Per-line articulation (the strongest signal).
    for line in lines:
        subject = by_id.get(line.get("subject_id"))
        articulation = line.get("articulation_target")
        if subject is None:
            _fail(line.get("subject_id"), line.get("shot_id"),
                  articulation, None)
            continue
        expected = _expected_articulation(subject)
        if articulation == "other":
            continue
        if expected is None:
            _fail(subject["subject_id"], line.get("shot_id"),
                  articulation, None)
        elif articulation != expected:
            _fail(subject["subject_id"], line.get("shot_id"),
                  articulation, expected)
    # Per-subject articulation from the profile / scope table.
    checked = {line.get("subject_id") for line in lines}
    for sub in subjects:
        if sub["subject_id"] in checked:
            continue
        if sub["subject_id"] not in speaking_ids:
            continue
        articulation = sub.get("articulation_target")
        if articulation is None or articulation == "other":
            continue
        expected = _expected_articulation(sub)
        if expected is None:
            _fail(sub["subject_id"], None, articulation, None)
        elif articulation != expected:
            _fail(sub["subject_id"], None, articulation, expected)
    # Fail closed: a speaking subject whose anatomy cannot be
    # established at all (no kind, no species) and whose articulation
    # is not stated as "other".
    for subject_id in speaking_ids:
        subject = by_id.get(subject_id)
        if subject is None:
            continue
        if subject.get("articulation_target") in (None, "other"):
            if _expected_articulation(subject) is None:
                _fail(subject_id, None, None, None)
    return blocked


# ---------------------------------------------------------------------------
# Skill resolution
# ---------------------------------------------------------------------------

def resolve_skills(request, catalog: dict) -> dict:
    """Resolve skills for one routing request (production promotion of
    the P0 routing helper).

    Returns a dict with ``skills`` (set of slugs), ``styles``
    (effective rendering styles), ``blocked`` (structured TC-1..TC-10
    diagnostics), ``visual_style`` and ``source_media_type`` as
    resolved (never inferred from each other), ``selections`` (each
    skill with its basis and scope) and ``claims`` (per-skill scope
    claims, for the planner).

    Raises RoutingError on an invalid request or a contradictory
    profile. A true conflict does NOT raise: it is returned in
    ``blocked`` so the planner can build a blocked plan that names
    the rule, the skills, the shot, the subject and the decision
    required — neither skill is ever silently removed.
    """
    errors = validate_routing_request(request, catalog)
    if errors:
        raise RoutingError("; ".join(errors))
    skills_by_slug = _skills_by_slug(catalog)
    mode = request["intent_mode"]
    hints = request.get("hints") or {}
    profile = request.get("production_profile")
    profile_facts = None
    if profile is not None:
        profile_facts = _validate_profile_semantics(profile, catalog)

    selections: dict[str, dict] = {}
    style_sets = _catalog_style_sets(catalog)

    def _select(skill, basis, scope=None):
        if skill not in selections:
            selections[skill] = {
                "skill": skill,
                "basis": basis,
                "scope": scope or {"kind": "production"},
            }

    # The router itself is always selected first.
    _select("command-authority", "router-default")
    explicit_scopes: dict[str, dict] = {}
    if profile_facts is not None:
        facts = profile_facts
        eff_styles = facts["effective_styles"]
        subjects_kinds = facts["subject_kinds"]
        # Base layers for any production.
        _select("production-systems", "router-default")
        _select("humanized-production", "router-default")
        if hints.get("dialogue"):
            _select("voice-consistency", "hint")
        if hints.get("recurring_character"):
            _select("character-consistency", "hint")
        if any(lang != "en" for lang in (hints.get("languages") or [])):
            _select("language-authenticity", "hint")
        if hints.get("explainer_structure") and "flat-2d-vector" in eff_styles:
            # The flat 2D explainer is ONE optional profile, not the
            # explainer model: explainer structure at another style
            # does NOT route through explainer-animation.
            _select("explainer-animation", "hint")
        if eff_styles & style_sets["cinematic"]:
            _select("cinematic-power", "profile-dimension")
        if subjects_kinds & {"cgi-animal", "fictional-creature",
                             "anthropomorphic"} and hints.get("dialogue"):
            _select("cinematic-power", "profile-dimension")
        if facts["digital_human"]:
            if hints.get("consent") is not True:
                raise RoutingError("consent record required before animating "
                                   "a real person's photo")
            _select("realistic-person", "profile-dimension")
        if facts["is_live_action_footage"] \
                or facts["source_media_type"] == "captured-footage" \
                or any(sub.get("representation") == "live-action-footage"
                       for sub in facts["overrides"]):
            _select("live-action-vfx", "profile-dimension")
        if facts["source_media_type"] == "reference-video" \
                and "ai-video-to-video" in facts["motion_methods"]:
            _select("video-regeneration", "profile-dimension")
        # Real-animal subjects are handled by live-action-vfx §6 (cut
        # from real behaviour): CGI creature-performance rules are
        # never forced onto an actual animal, so real-animal alone
        # adds no CG skill.
    # Explicit selections: exactly one primary pathway, plus layers.
    pathway = request.get("primary_pathway")
    if pathway is not None:
        _select(pathway, "user-request")
    for layer in request.get("additional_layers") or []:
        _select(layer, "user-request")
    for item in request.get("requested_skills") or []:
        skill = item["skill"]
        scope = item.get("scope")
        if scope:
            scope_obj = {"kind": "shot-subject"}
            if scope.get("shots") and not scope.get("subjects"):
                scope_obj = {"kind": "shot", "shots": list(scope["shots"])}
            elif scope.get("subjects") and not scope.get("shots"):
                scope_obj = {"kind": "subject",
                             "subjects": list(scope["subjects"])}
            else:
                scope_obj = {"kind": "shot-subject",
                             "shots": list(scope.get("shots") or []),
                             "subjects": list(scope.get("subjects") or [])}
            explicit_scopes[skill] = scope
            _select(skill, item["source"], scope_obj)
        else:
            _select(skill, item["source"])
    # Registration modes carry their canonical chain as the default
    # (WORKFLOW_GRAPH.yaml sequential_chains): a registration plan is
    # plan-only and the chain is the plan.
    if mode in _REGISTRATION_MODES:
        for skill in _REGISTRATION_CHAINS[mode]:
            _select(skill, "mode-default")
    # Canonical dependencies are ORDER constraints, not selection
    # rules: a dependent is never ready before a prerequisite that is
    # also selected, but selecting a skill never forces its
    # dependencies into the plan. The P0 scenarios are decisive here:
    # a realistic-person video in English selects realistic-person
    # without language-authenticity, and real-animal footage selects
    # live-action-vfx without cinematic-power — the dependencies
    # constrain the step order in the plan (see build_workflow_plan),
    # they do not expand the selection. A dependency that is not
    # applicable in the selected mode is resolved per the mode's
    # documented scope there, never silently dropped and never
    # invented.
    # resource-management is cross-cutting: it is recorded as
    # phase-level instruction by the planner, never as a selected skill.
    selections.pop("resource-management", None)

    # Mode compatibility: every selected skill must list the mode.
    for skill in sorted(selections):
        applicable = skills_by_slug[skill].get("applicable_modes") or []
        if mode not in applicable:
            suggested = _suggested_mode(skill, skills_by_slug)
            raise RoutingError(
                f"skill {skill} is not applicable in {mode} mode "
                f"(applicable modes: {sorted(applicable)}"
                + (f"; use {suggested} instead" if suggested else "")
                + ")")

    subjects = _subject_table(request, profile_facts) \
        if profile_facts is not None else _subject_table(request, {
            "overrides": []})
    shots = _shot_table(request, profile)
    claims = {}
    for skill in selections:
        claims[skill] = _claims_for_skill(
            skill, request, profile_facts, subjects, shots,
            explicit_scopes.get(skill), style_sets)
    blocked = _check_true_conflicts(
        set(selections), claims, request, profile_facts, subjects, shots,
        catalog, style_sets, explicit_scopes)
    return {
        "skills": set(selections),
        "styles": set(profile_facts["effective_styles"])
                  if profile_facts is not None else set(),
        "blocked": blocked,
        "visual_style": profile_facts["visual_style"]
                        if profile_facts is not None else None,
        "source_media_type": profile_facts["source_media_type"]
                             if profile_facts is not None else None,
        "selections": [selections[s] for s in sorted(
            selections, key=lambda x: skills_by_slug[x]["precedence"])],
        "claims": claims,
        "subjects": subjects,
        "shots": shots,
    }


def _suggested_mode(skill, skills_by_slug) -> str | None:
    """The first applicable production mode for a skill, in the order
    a production would normally use it — used only inside the
    mode-incompatibility diagnostic."""
    preference = ("GENERATE_FROM_SCRIPT", "REMAKE_OR_TRANSFORM",
                  "EDIT_EXISTING_MEDIA", "PROJECT_CONSISTENCY", "VIDEO_QC",
                  "TEMPORARY_ASSET_USE", "REFERENCE_REVIEW",
                  "REFERENCE_LEARN_AND_UPDATE")
    applicable = skills_by_slug[skill].get("applicable_modes") or []
    for mode in preference:
        if mode in applicable:
            return mode
    return None


def _catalog_style_sets(catalog: dict) -> dict:
    """Style sets the conflict checks read from the catalog in use —
    never hard-coded in the router."""
    vocab = catalog.get("vocabularies") or {}
    kids = _skills_by_slug(catalog).get("kids-family-animation") or {}
    dims = (kids.get("routing_dimensions") or {}).get("visual_style") or []
    return {
        "cinematic": set(vocab.get("cinematic_styles") or []),
        "animation": set(vocab.get("animation_styles") or []),
        "kids": {s for s in dims if s != "flat-2d-vector"},
    }

# ---------------------------------------------------------------------------
# Deterministic plan hash
# ---------------------------------------------------------------------------

def _canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def plan_hash(plan: dict) -> str:
    """SHA-256 of the canonical JSON of the plan without its own
    plan_hash field. No timestamps are ever embedded in a plan, so
    the hash is deterministic: the same request, catalog and session
    always produce the same hash."""
    body = {k: v for k, v in plan.items() if k != "plan_hash"}
    return hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest()


def _as_text_list(value) -> list:
    """Normalize a matrix text field to a list of strings.

    The routing matrix stores required_inputs / expected_outputs as
    lists of strings and single-key dicts ({label: detail}), and
    approval_conditions as one string. Plans and handoff packets
    carry them uniformly as string lists (so they validate against
    the plan schema): a dict becomes "label: detail" with its keys
    sorted, a bare string becomes a one-element list.
    """
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return ["; ".join(f"{k}: {v}" for k, v in sorted(value.items()))]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_as_text_list(item))
        return out
    return [str(value)]


def _registration_field_satisfied(field, value) -> bool:
    """Whether one registration-evidence value satisfies the policy:
    a boolean field only when it is the actual boolean True, a
    string field only when it is a non-empty string. Anything else —
    including the string "false", the integer 1, or an empty string —
    does not satisfy it, so no string or number can stand in for
    affirmative approval."""
    if field in _EVIDENCE_BOOL_FIELDS:
        return value is True
    return isinstance(value, str) and bool(value)


def _new_plan_base(task_id, mode, catalog, session) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "plan_id": f"plan-{task_id}",
        "task_id": task_id,
        "intent_mode": mode,
        "catalog_version": catalog.get("catalog_version"),
        "catalog_sources": catalog.get("sources"),
        "session": {"session_id": session.session_id},
        "status": "ready",
        "selected_skills": [],
        "steps": [],
        "execution_batches": [],
        "parallel_groups": [],
        "resource_management": [],
        "conflicts": [],
        "blocked_diagnostics": [],
        "constraints": [],
        "plan_only": False,
        "proposal_only": False,
        "temporary_only": False,
        "analysis_only": False,
    }


def _blocked_plan(task_id, mode, catalog, session, diagnostics,
                  conflicts=None) -> dict:
    """A blocked plan: status blocked, no steps, every reason recorded.
    Nothing is silently dropped — the caller must resolve the
    diagnostics and request a new plan."""
    plan = _new_plan_base(task_id, mode, catalog, session)
    plan["status"] = "blocked"
    plan["blocked_diagnostics"] = diagnostics
    plan["conflicts"] = conflicts or []
    plan["plan_hash"] = plan_hash(plan)
    return plan


def _diagnostic(code, message, **extra) -> dict:
    item = {"code": code, "message": message}
    item.update(extra)
    return item


# ---------------------------------------------------------------------------
# Workflow plan builder
# ---------------------------------------------------------------------------

def build_workflow_plan(session, request, catalog=None) -> dict:
    """Build a deterministic workflow plan for one request under one
    exact active local session.

    Identity comes only from the session, verified with the P1-001
    verifier — never from caller-provided owner or workspace strings.
    A missing, forged, expired, copied or closed session raises
    RoutingError and no plan is built at all.

    Every request-side problem (invalid request, mode incompatibility,
    missing evidence, true conflict) produces a structured blocked
    plan instead of raising, so the caller always gets a plan that
    names what must be decided. The planner never reads a private
    project asset and never bypasses P1-001 authorization: it plans
    only.
    """
    catalog = catalog or load_routing_catalog()
    if not local_session.is_active_session(session):
        reasons = local_session.validate_session(session)
        raise RoutingError(
            "no active session for this plan"
            + (f": {'; '.join(reasons)}" if reasons else ""))
    if not isinstance(request, dict):
        raise RoutingError("request is not an object")
    mode = request.get("intent_mode")
    task_id = request.get("task_id") or "unknown"
    modes = set((catalog.get("intent_modes") or {}).keys())
    if not isinstance(mode, str) or mode not in modes:
        raise RoutingError(f"intent_mode {mode!r} is not one of the 13 "
                           "intent modes")
    if mode in _NON_ROUTING_MODES:
        allowed = ", ".join(
            (_mode_record(catalog, mode).get("allowed") or []))
        return _blocked_plan(task_id, mode, catalog, session, [_diagnostic(
            "mode-does-not-route-production",
            f"{mode} never routes production work through the router "
            f"(allowed actions: {allowed}); no plan is built",
            )])
    errors = validate_routing_request(request, catalog)
    if errors:
        return _blocked_plan(task_id, mode, catalog, session, [
            _diagnostic("invalid-request", error) for error in errors])
    # Mode-specific evidence and behaviour (architecture/intent-modes.yaml).
    if mode in _REGISTRATION_MODES:
        evidence = request.get("registration_evidence") or {}
        missing = [field for field in _REGISTRATION_EVIDENCE[mode]
                   if not _registration_field_satisfied(
                       field, evidence.get(field))]
        if missing:
            return _blocked_plan(task_id, mode, catalog, session, [
                _diagnostic(
                    "missing-registration-evidence",
                    f"{mode} requires {', '.join(missing)}; registration is "
                    "plan-only and needs its own explicit authorisation",
                    )])
    if mode == "REFERENCE_LEARN_AND_UPDATE" \
            and request.get("explicit_user_instruction") is not True:
        return _blocked_plan(task_id, mode, catalog, session, [_diagnostic(
            "missing-explicit-instruction",
            "REFERENCE_LEARN_AND_UPDATE is proposal-only and requires an "
            "explicit user instruction")])
    if mode == "REMAKE_OR_TRANSFORM" \
            and (request.get("explicit_request") is not True
                 or request.get("rights_provenance_checked") is not True):
        return _blocked_plan(task_id, mode, catalog, session, [_diagnostic(
            "missing-remake-evidence",
            "REMAKE_OR_TRANSFORM requires an explicit request and a rights "
            "provenance check")])
    if mode == "GENERATE_FROM_SCRIPT" \
            and request.get("dialogue_rewrite_requested") is True:
        return _blocked_plan(task_id, mode, catalog, session, [_diagnostic(
            "dialogue-rewrite-forbidden",
            "GENERATE_FROM_SCRIPT forbids a silent dialogue rewrite; "
            "dialogue stays verbatim unless a rewrite is authorised "
            "per line")])
    try:
        resolved = resolve_skills(request, catalog)
    except RoutingError as exc:
        return _blocked_plan(task_id, mode, catalog, session, [
            _diagnostic("routing-refused", str(exc))])
    if resolved["blocked"]:
        diagnostics = []
        for item in resolved["blocked"]:
            subject = item.get("subject_id") or "the production"
            shot = item.get("shot_id") or "the production"
            diagnostics.append(_diagnostic(
                f"true-conflict-{item['rule_id']}",
                f"{item['rule_id']}: {', '.join(item['skills'])} conflict "
                f"for {subject} in {shot} — {item['required_input']}",
                rule_id=item["rule_id"],
                shot_id=item.get("shot_id"),
                subject_id=item.get("subject_id")))
        return _blocked_plan(task_id, mode, catalog, session, diagnostics,
                             conflicts=resolved["blocked"])
    if mode == "VIDEO_QC" and "video-regeneration" in resolved["skills"] \
            and request.get("repair_authorised") is not True:
        return _blocked_plan(task_id, mode, catalog, session, [_diagnostic(
            "regeneration-without-repair-authorisation",
            "VIDEO_QC forbids regeneration without repair authorisation; "
            "inspect and report defects only",
            skill="video-regeneration")])

    skills_by_slug = _skills_by_slug(catalog)
    plan = _new_plan_base(task_id, mode, catalog, session)
    mode_record = _mode_record(catalog, mode)
    if mode in _REGISTRATION_MODES:
        plan["plan_only"] = True
    if mode == "REFERENCE_LEARN_AND_UPDATE":
        plan["proposal_only"] = True
    if mode == "TEMPORARY_ASSET_USE":
        plan["temporary_only"] = True
    if mode == "REFERENCE_REVIEW":
        plan["analysis_only"] = True
    if mode == "GENERATE_FROM_SCRIPT":
        plan["constraints"].append("dialogue_mode: VERBATIM_SCRIPT")
    for action in mode_record.get("allowed") or []:
        plan["constraints"].append(f"mode {mode}: allowed {action}")
    for action in mode_record.get("forbidden") or []:
        plan["constraints"].append(f"mode {mode}: forbidden {action}")
    if mode_record.get("creates_permanent_record"):
        plan["constraints"].append(
            f"mode {mode}: creates a permanent record")

    # Selected skills, enriched with the exact skill path and SHA-256
    # fingerprint from the catalog.
    selected = []
    for item in resolved["selections"]:
        record = skills_by_slug[item["skill"]]
        selected.append({
            "skill": item["skill"],
            "skill_id": record["skill_id"],
            "path": record["path"],
            "sha256": record["sha256"],
            "basis": item["basis"],
            "scope": item["scope"],
            "quality_gate": record["quality_gate"],
            "approval_conditions": _as_text_list(
                record["approval_conditions"]),
            "required_inputs": _as_text_list(record["required_inputs"]),
            "expected_outputs": _as_text_list(record["expected_outputs"]),
        })
    plan["selected_skills"] = selected
    selected_skills = [s["skill"] for s in selected]

    # Non-applicable dependencies, resolved per the mode's documented
    # scope: a dependency that is not selected AND does not list this
    # mode is recorded here, never silently dropped. (A dependency
    # that lists the mode but is simply not selected is the normal
    # composable case — the plan's step dependencies already show the
    # restricted set.)
    selected_set = set(selected_skills)
    for skill in sorted(selected_set):
        for dep in (skills_by_slug[skill].get("dependencies") or []):
            if dep in selected_set:
                continue
            dep_applicable = (skills_by_slug[dep].get("applicable_modes")
                              or [])
            if mode not in dep_applicable:
                plan["constraints"].append(
                    f"dependency: {dep} of {skill} is not applicable in "
                    f"{mode} mode and is not selected; the step runs "
                    "without it (resolved per documented mode scope)")

    # Derived articulations: a speaking subject with no explicit
    # articulation gets the one its anatomy allows, recorded here so
    # the plan never guesses silently.
    for sub in resolved["subjects"]:
        if sub.get("articulation_target") is None \
                and _expected_articulation(sub) is not None:
            speaking = sub.get("speaking") is True \
                or any(line.get("subject_id") == sub["subject_id"]
                       for line in (request.get("dialogue_lines") or [])) \
                or (bool((request.get("hints") or {}).get("dialogue"))
                    and sub.get("subject_kind") is not None)
            if speaking:
                plan["constraints"].append(
                    f"articulation: {sub['subject_id']} -> "
                    f"{_expected_articulation(sub)} (derived from anatomy)")

    # Deterministic DAG: topological order over the matrix
    # dependencies restricted to the selected skills, precedence as
    # the tie-breaker. The conditional existing-character-prep group
    # relaxes the character-consistency -> voice-consistency edge
    # only when the character is already registered (the two registry
    # reads are independent then); for a new character the edge
    # applies and registration runs first.
    existing_character = bool(
        (request.get("hints") or {}).get("existing_character_registered"))
    dependencies: dict[str, set] = {}
    for skill in selected_skills:
        deps = {d for d in
                (skills_by_slug[skill].get("dependencies") or [])
                if d in selected_skills}
        if existing_character and skill == "voice-consistency":
            deps.discard("character-consistency")
        dependencies[skill] = deps
    order = _topological_order(selected_skills, dependencies, skills_by_slug)
    graph = catalog.get("graph") or {}
    stages = {n.get("id"): n.get("stage")
              for n in (graph.get("nodes") or [])}
    steps = []
    for skill in order:
        record = skills_by_slug[skill]
        scope = next(item["scope"] for item in resolved["selections"]
                     if item["skill"] == skill)
        steps.append({
            "step_id": skill,
            "skill": skill,
            "precedence": record["precedence"],
            "dependencies": sorted(
                dependencies[skill],
                key=lambda d: skills_by_slug[d]["precedence"]),
            "stage": stages.get(skill, ""),
            "scope": scope,
            "quality_gate": record["quality_gate"],
            "approval_conditions": _as_text_list(
                record["approval_conditions"]),
        })
    plan["steps"] = steps

    # Execution batches: a skill joins the earliest batch where all
    # its dependencies are in earlier batches and it shares a
    # parallel group (whose scope condition holds in this plan) with
    # every skill already in that batch. Anything else gets its own
    # batch — never parallelise merely on different names.
    batches = _execution_batches(
        order, dependencies, resolved["claims"], catalog, existing_character)
    plan["execution_batches"] = batches
    batch_of = {}
    for i, batch in enumerate(batches):
        for step_id in batch:
            batch_of[step_id] = i
    for step in steps:
        group = _batch_parallel_group(
            step["step_id"], batches[batch_of[step["step_id"]]],
            catalog, existing_character)
        if group is not None:
            step["parallel_group"] = group
    plan["parallel_groups"] = _active_parallel_groups(
        selected_skills, resolved["claims"], catalog, existing_character,
        batches)

    # resource-management is cross-cutting: one instruction per phase
    # boundary, never a scheduled step.
    cross = (graph.get("cross_cutting") or [{}])[0]
    note = cross.get("note", "")
    plan["resource_management"] = [
        {"phase": f"before-batch-{i + 1}", "instructions": note}
        for i in range(len(batches))
    ]
    plan["plan_hash"] = plan_hash(plan)
    return plan


def _topological_order(skills, dependencies, skills_by_slug) -> list:
    """Kahn's algorithm with precedence as the tie-breaker. Raises
    RoutingError on a cycle or an unknown node."""
    unknown = [s for s in skills if s not in skills_by_slug]
    if unknown:
        raise RoutingError(f"unknown skills in plan: {sorted(unknown)}")
    remaining = {s: set(dependencies.get(s) or set()) for s in skills}
    order: list[str] = []
    while remaining:
        ready = sorted(
            (s for s, deps in remaining.items() if not deps),
            key=lambda s: skills_by_slug[s]["precedence"])
        if not ready:
            raise RoutingError(
                "dependency cycle among: "
                f"{sorted(remaining)}")
        skill = ready[0]
        order.append(skill)
        del remaining[skill]
        for deps in remaining.values():
            deps.discard(skill)
    return order


def _group_scope_condition(group, claims, existing_character) -> bool:
    """Whether a canonical parallel group's scope condition holds in
    this plan, given the selected skills' claims."""
    name = group.get("name")
    members = group.get("skills") or []
    if name == "existing-character-prep":
        return existing_character
    if name == "performance-layers-different-scenes":
        # Only for DIFFERENT scenes: the two skills must not share a
        # shot. A production-wide claim shares every shot, so the
        # group does not apply without scoped claims.
        if len(members) != 2:
            return False
        a, b = claims.get(members[0], set()), claims.get(members[1], set())
        shots_a = {t for _, t in a if t is not None}
        shots_b = {t for _, t in b if t is not None}
        if (None, None) in a or (None, None) in b:
            return False
        return not (shots_a & shots_b)
    if name == "composable-pathways-different-shots":
        # Only for DIFFERENT shots or subjects: the members' claims
        # must be pairwise disjoint.
        for i, first in enumerate(members):
            for second in members[i + 1:]:
                if _scopes_intersect(claims.get(first, set()),
                                     claims.get(second, set())):
                    return False
        return True
    # foundation-planning and language-and-humanization-prep carry no
    # scope condition: no dependency between the members.
    return True


def _execution_batches(order, dependencies, claims, catalog,
                       existing_character) -> list:
    """Greedy deterministic batching (see build_workflow_plan)."""
    graph = catalog.get("graph") or {}
    groups = list(graph.get("parallel_groups") or []) \
        + list(graph.get("conditional_parallel_groups") or [])
    group_of = {}
    for group in groups:
        members = group.get("skills") or []
        for first in members:
            for second in members:
                if first != second:
                    group_of.setdefault((first, second), []).append(group)
    batches: list[list[str]] = []
    placed: dict[str, int] = {}

    def _compatible(skill, batch):
        for other in batch:
            shared = group_of.get((skill, other), [])
            if not shared:
                return False
            if not any(_group_scope_condition(g, claims, existing_character)
                       for g in shared):
                return False
        return True

    for skill in order:
        earliest = 0
        for dep in dependencies.get(skill) or set():
            earliest = max(earliest, placed[dep] + 1)
        target = None
        for i in range(earliest, len(batches)):
            if _compatible(skill, batches[i]):
                target = i
                break
        if target is None:
            batches.append([skill])
            placed[skill] = len(batches) - 1
        else:
            batches[target].append(skill)
            placed[skill] = target
    return batches


def _batch_parallel_group(step_id, batch, catalog, existing_character):
    """The parallel group a step shares its batch through, if any."""
    if len(batch) < 2:
        return None
    graph = catalog.get("graph") or {}
    groups = list(graph.get("parallel_groups") or []) \
        + list(graph.get("conditional_parallel_groups") or [])
    for group in groups:
        members = set(group.get("skills") or [])
        if step_id in members and members & set(batch) - {step_id}:
            return group.get("name")
    return None


def _active_parallel_groups(selected_skills, claims, catalog,
                            existing_character, batches) -> list:
    """Canonical parallel groups actually parallelised in this plan:
    at least two selected members in the same execution batch, with
    the scope condition holding. A group whose members were split
    across batches by the greedy batching is not listed — the plan
    records what it actually parallelises, not what it could have."""
    graph = catalog.get("graph") or {}
    groups = list(graph.get("parallel_groups") or []) \
        + list(graph.get("conditional_parallel_groups") or [])
    skills_by_slug = _skills_by_slug(catalog)
    batch_of: dict[str, int] = {}
    for i, batch in enumerate(batches):
        for step_id in batch:
            batch_of[step_id] = i
    scope_labels = {
        "foundation-planning": "no-dependency",
        "language-and-humanization-prep": "no-dependency",
        "performance-layers-different-scenes": "different-scenes",
        "composable-pathways-different-shots": "different-shots-or-subjects",
        "existing-character-prep": "existing-character-only",
    }
    active = []
    for group in groups:
        members = [s for s in (group.get("skills") or [])
                   if s in selected_skills]
        if len(members) < 2:
            continue
        if not _group_scope_condition(group, claims, existing_character):
            continue
        together = [s for s in members
                    if batch_of.get(s) == batch_of.get(members[0])]
        if len(together) < 2:
            continue
        active.append({
            "name": group.get("name"),
            "skills": sorted(together,
                             key=lambda s: skills_by_slug[s]["precedence"]),
            "scope": scope_labels.get(group.get("name"), "no-dependency"),
        })
    return sorted(active, key=lambda g: g["name"])


# ---------------------------------------------------------------------------
# Plan validation, ready steps, handoff packets
# ---------------------------------------------------------------------------

def validate_routing_plan(plan, catalog: dict) -> list:
    """Validate a routing plan against the plan schema rules and the
    catalog. Returns a list of error strings; an empty list means the
    plan is valid. This is the tamper check: a plan whose recomputed
    hash differs from plan_hash, whose catalog sources do not match
    the catalog, or whose step order violates a dependency is
    rejected here. (Structural schema conformance is additionally
    checked by the test suite against schemas/skill-routing-plan.json
    with the repo validator.)
    """
    errors: list[str] = []
    if not isinstance(plan, dict):
        return ["plan is not an object"]
    if plan.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            "schema_version must be "
            f"'{SCHEMA_VERSION}', got {plan.get('schema_version')!r}")
    task_id = plan.get("task_id")
    if plan.get("plan_id") != f"plan-{task_id}":
        errors.append(
            f"plan_id {plan.get('plan_id')!r} does not match task_id "
            f"{task_id!r}")
    mode = plan.get("intent_mode")
    if mode not in set((catalog.get("intent_modes") or {}).keys()):
        errors.append(f"intent_mode {mode!r} is not one of the 13 intent modes")
    if plan.get("catalog_version") != CATALOG_VERSION:
        errors.append(
            "catalog_version must be "
            f"'{CATALOG_VERSION}', got {plan.get('catalog_version')!r}")
    if plan.get("catalog_sources") != catalog.get("sources"):
        errors.append("catalog_sources do not match the catalog in use")
    session = plan.get("session")
    if not isinstance(session, dict) \
            or not isinstance(session.get("session_id"), str) \
            or not session["session_id"]:
        errors.append("plan has no session_id")
    status = plan.get("status")
    if status not in ("ready", "blocked"):
        errors.append(f"status {status!r} is not ready or blocked")
    if status == "ready" and plan.get("blocked_diagnostics"):
        errors.append("ready plan carries blocked diagnostics")
    if status == "blocked" and plan.get("steps"):
        errors.append("blocked plan carries steps")
    stored_hash = plan.get("plan_hash")
    if not isinstance(stored_hash, str) or not _SHA256_RE.match(stored_hash):
        errors.append("plan_hash is not a SHA-256 hex digest")
    elif plan_hash(plan) != stored_hash:
        errors.append("plan_hash does not match the plan contents "
                      "(the plan was tampered with)")
    skills_by_slug = _skills_by_slug(catalog)
    selected = plan.get("selected_skills") or []
    step_skills = [s.get("skill") for s in (plan.get("steps") or [])]
    if sorted(s.get("skill") for s in selected) != sorted(step_skills):
        errors.append("selected_skills and steps name different skills")
    seen_steps: list[str] = []
    for i, step in enumerate(plan.get("steps") or []):
        skill = step.get("skill")
        if skill not in skills_by_slug:
            errors.append(f"steps[{i}].skill {skill!r} is not a known skill")
            continue
        record = skills_by_slug[skill]
        if step.get("precedence") != record["precedence"]:
            errors.append(f"step {skill} precedence "
                          f"{step.get('precedence')} != catalog "
                          f"{record['precedence']}")
        if step.get("step_id") != skill:
            errors.append(f"steps[{i}].step_id {step.get('step_id')!r} != "
                          f"skill {skill!r}")
        for dep in step.get("dependencies") or []:
            if dep not in seen_steps:
                errors.append(
                    f"step {skill} depends on {dep}, which is not an "
                    "earlier step")
            if skills_by_slug.get(dep, {}).get("precedence", 99) \
                    >= record["precedence"]:
                errors.append(
                    f"step {skill} depends on {dep}, which does not run "
                    "earlier")
        seen_steps.append(skill)
    flat_batches = [step_id for batch in (plan.get("execution_batches") or [])
                    for step_id in batch]
    if sorted(flat_batches) != sorted(step_skills):
        errors.append("execution_batches do not cover exactly the steps")
    if len(flat_batches) != len(set(flat_batches)):
        errors.append("execution_batches list a step twice")
    for group in plan.get("parallel_groups") or []:
        members = group.get("skills") or []
        if len(members) < 2:
            errors.append(
                f"parallel group {group.get('name')} has fewer than two "
                "members in the plan")
        if not set(members) <= set(step_skills):
            errors.append(
                f"parallel group {group.get('name')} names skills that are "
                "not steps in the plan")
    return errors


def get_ready_steps(plan, completed_step_ids) -> list:
    """Pure function: the steps that are ready to run given the plan
    and the set of completed step ids (receipts). A step is ready when
    every dependency is complete, the step itself is not complete,
    and every step in every earlier execution batch is complete —
    batches run in order, so a step never jumps ahead of its batch.
    No sleeps, no workers, no external scheduler — the caller drives
    execution and reports receipts back. A blocked plan has no ready
    steps. Unknown receipts are ignored.
    """
    if not isinstance(plan, dict) or plan.get("status") != "ready":
        return []
    completed = set(completed_step_ids or [])
    batches = plan.get("execution_batches") or []
    batch_of: dict[str, int] = {}
    for i, batch in enumerate(batches):
        for step_id in batch:
            batch_of[step_id] = i
    ready = []
    for step in plan.get("steps") or []:
        step_id = step.get("step_id")
        if step_id in completed:
            continue
        if not set(step.get("dependencies") or []) <= completed:
            continue
        earlier = {s for b in batches[:batch_of.get(step_id, 0)] for s in b}
        if earlier <= completed:
            ready.append(step_id)
    precedence = {s.get("step_id"): s.get("precedence", 99)
                  for s in plan.get("steps") or []}
    return sorted(ready, key=lambda s: precedence.get(s, 99))


def build_handoff_packet(session, plan, step_id, completed_receipts=None,
                         catalog=None) -> dict:
    """Build the handoff packet for one step: everything the skill
    that runs the step needs, and nothing it must not do.

    The packet carries the exact skill path and SHA-256 fingerprint,
    the selection reason, the inputs, the expected outputs, the
    satisfied dependencies, the quality gate, the approval
    requirements, and the conflicting and prohibited operations.
    When a catalog is supplied, the conflicting operations also name
    the skill's matrix conflicts and the true-conflict rules that
    involve it; without a catalog only the plan's own conflict
    records are used.

    Dependency-safe (Task C): a declared dependency is never labelled
    satisfied merely because the plan lists it. The caller supplies
    explicit completion receipts — one per completed step — and only
    a receipt that validates against this exact plan (matching
    plan_id, a known step ID, explicit ``status == "completed"``)
    counts as completed input. The requested step must be ready
    under :func:`get_ready_steps` for those receipts, or the packet
    is refused. Receipts are reported completion state, not
    cryptographic proof that an external agent actually executed
    the work; there is no execution engine here.

    Validation order: the exact active session first (a missing,
    forged, expired, copied or closed session raises and nothing is
    built), then the plan structure and its deterministic hash, then
    the plan/session binding, then every receipt, then readiness.
    """
    if not local_session.is_active_session(session):
        reasons = local_session.validate_session(session)
        raise RoutingError(
            "no active session for this handoff"
            + (f": {'; '.join(reasons)}" if reasons else ""))
    catalog = catalog or load_routing_catalog()
    if not isinstance(plan, dict):
        raise RoutingError("plan is not an object")
    plan_errors = validate_routing_plan(plan, catalog)
    if plan_errors:
        raise RoutingError(
            "plan does not validate: " + "; ".join(plan_errors))
    if plan.get("status") != "ready":
        raise RoutingError(
            f"plan status is {plan.get('status')!r}, not 'ready': no "
            "handoff is issued for a blocked plan")
    plan_session_id = (plan.get("session") or {}).get("session_id")
    if plan_session_id != session.session_id:
        raise RoutingError(
            "plan belongs to a different session: the handoff session "
            "does not match the plan's session")
    step_ids = [s.get("step_id") for s in (plan.get("steps") or [])]
    receipts = completed_receipts if completed_receipts is not None else []
    if not isinstance(receipts, list):
        raise RoutingError("completed_receipts is not a list")
    completed: set[str] = set()
    for i, receipt in enumerate(receipts):
        if not isinstance(receipt, dict):
            raise RoutingError(
                f"completion receipt [{i}] is not an object")
        extra = sorted(set(receipt) - {"plan_id", "step_id", "status"})
        if extra:
            raise RoutingError(
                f"completion receipt [{i}] has unknown fields: {extra}")
        for field in ("plan_id", "step_id", "status"):
            if field not in receipt:
                raise RoutingError(
                    f"completion receipt [{i}] is missing '{field}'")
        if receipt["plan_id"] != plan.get("plan_id"):
            raise RoutingError(
                f"completion receipt [{i}] names plan "
                f"{receipt['plan_id']!r}, not this plan "
                f"{plan.get('plan_id')!r}")
        if receipt["step_id"] not in step_ids:
            raise RoutingError(
                f"completion receipt [{i}] names unknown step "
                f"{receipt['step_id']!r}")
        if receipt["status"] != "completed":
            raise RoutingError(
                f"completion receipt [{i}] for step "
                f"{receipt['step_id']!r} has status "
                f"{receipt['status']!r}, not 'completed'")
        if receipt["step_id"] in completed:
            raise RoutingError(
                f"completion receipt [{i}] duplicates the receipt for "
                f"step {receipt['step_id']!r}")
        completed.add(receipt["step_id"])
    step = next((s for s in (plan.get("steps") or [])
                 if s.get("step_id") == step_id), None)
    if step is None:
        raise RoutingError(f"step {step_id!r} is not in the plan")
    ready = get_ready_steps(plan, completed)
    if step_id not in ready:
        missing_deps = [d for d in (step.get("dependencies") or [])
                        if d not in completed]
        batches = plan.get("execution_batches") or []
        batch_of: dict[str, int] = {}
        for i, batch in enumerate(batches):
            for member in batch:
                batch_of[member] = i
        earlier_missing = sorted(
            s for s, b in batch_of.items()
            if b < batch_of.get(step_id, 0) and s not in completed)
        detail = ""
        if step_id in completed:
            detail = f"step {step_id!r} is already complete"
        elif missing_deps:
            detail = ("its dependencies are not complete: "
                      f"{missing_deps}")
        elif earlier_missing:
            detail = ("earlier batch steps are not complete: "
                      f"{earlier_missing}")
        else:
            detail = "it is not ready under the supplied receipts"
        raise RoutingError(
            f"step {step_id!r} is not ready for handoff: {detail}")
    skill = step["skill"]
    record = next((s for s in (plan.get("selected_skills") or [])
                   if s.get("skill") == skill), None)
    if record is None:
        raise RoutingError(f"skill {skill} has no selected-skills record")
    satisfied = [d for d in (step.get("dependencies") or [])
                 if d in completed]
    conflicting: list[str] = []
    prohibited: list[str] = []
    for conflict in plan.get("conflicts") or []:
        if skill in (conflict.get("skills") or []):
            conflicting.append(
                f"{conflict.get('rule_id')}: conflicts with "
                f"{', '.join(s for s in conflict['skills'] if s != skill)} "
                f"for subject {conflict.get('subject_id') or 'the production'} "
                f"in shot {conflict.get('shot_id') or 'the production'} — "
                f"{conflict.get('decision', '')}")
    for constraint in plan.get("constraints") or []:
        if ": forbidden " in constraint:
            prohibited.append(constraint)
    skills_by_slug = _skills_by_slug(catalog)
    entry = skills_by_slug.get(skill) or {}
    for other in entry.get("conflicts") or []:
        scope = entry.get("conflict_scope") or "same subject, same shot"
        conflicting.append(
            f"matrix conflict with {other} ({scope}) — the two skills "
            "cannot both apply to one subject in one shot")
    for tc in (catalog.get("graph") or {}).get("true_conflicts") or []:
        if skill in (tc.get("skills") or []):
            conflicting.append(
                f"{tc.get('id')}: {tc.get('rule', '')} "
                f"Resolution: {tc.get('resolution', '')}")
    precedence = {s.get("step_id"): s.get("precedence", 99)
                  for s in plan.get("steps") or []}
    return {
        "plan_id": plan.get("plan_id"),
        "session_id": session.session_id,
        "step_id": step_id,
        "skill": skill,
        "skill_id": record["skill_id"],
        "path": record["path"],
        "sha256": record["sha256"],
        "selection_basis": record["basis"],
        "selection_reason": (
            f"selected as {record['basis']} "
            f"(scope {record['scope'].get('kind')})"),
        "scope": record["scope"],
        "stage": step.get("stage"),
        "precedence": step.get("precedence"),
        "inputs": list(record["required_inputs"]),
        "expected_outputs": list(record["expected_outputs"]),
        "satisfied_dependencies": list(satisfied),
        "dependency_steps": list(step.get("dependencies") or []),
        "completed_step_ids": sorted(
            completed, key=lambda s: precedence.get(s, 99)),
        "quality_gate": step.get("quality_gate"),
        "approval_requirements": list(step.get("approval_conditions") or []),
        "conflicting_operations": sorted(set(conflicting)),
        "prohibited_operations": sorted(set(prohibited)),
    }


__all__ = [
    "RoutingError",
    "catalog_fingerprint",
    "load_routing_catalog",
    "validate_routing_request",
    "resolve_skills",
    "build_workflow_plan",
    "validate_routing_plan",
    "get_ready_steps",
    "build_handoff_packet",
    "plan_hash",
]
