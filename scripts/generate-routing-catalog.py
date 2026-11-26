#!/usr/bin/env python3
"""Consistency Frame P1 — generate the deterministic runtime routing catalog.

Compiles the canonical routing records into registry/routing-catalog.json,
the single machine-readable routing source the standard-library-only
runtime reads:
  architecture/SKILL_ROUTING_MATRIX.yaml           (15 skill records, v2.4)
  architecture/WORKFLOW_GRAPH.yaml                 (nodes, edges, parallel
                                                    groups, TC-1..TC-10, v2.4)
  architecture/intent-modes.yaml                   (13 intent modes, v2.3)
  architecture/COMPANION_CAPABILITY_REGISTRY.yaml  (2 companions, v2.4)
  architecture/AGENT_COMPATIBILITY_MATRIX.yaml     (10 agents, v2.4)
plus a SHA-256 fingerprint of each skill's skills/<slug>/SKILL.md file,
so a handoff packet can name the exact skill text it was built from.

Build-time only: this compiler uses PyYAML (already installed in CI and
in this environment). The installed runtime (runtime/skill_router.py)
never imports YAML — it reads the generated JSON with the standard
library only. The generated JSON is never edited by hand; --check fails
CI when it is stale.

The compiler stamps an integrity fingerprint over the catalog
contents (``integrity.fingerprint``, SHA-256 of the canonical JSON
of the catalog without the integrity record itself — the same
canonical form ``runtime.skill_router.catalog_fingerprint`` computes,
so the two must agree exactly). The runtime loader refuses any
catalog whose stored fingerprint differs from a recomputation, so
an accidental hand edit of the generated file is detected at load
even when every semantic check would still pass. The fingerprint is
recomputed deterministically on every build: editing a canonical
source (or the compiler) and re-running this script updates it; a
hand edit of the JSON without re-running the script is caught by
--check (the committed file differs from a fresh build) and by the
runtime loader (the fingerprint no longer matches). This is
integrity against accidental / unsupported mutation, not
cryptographic protection against a malicious process with the same
OS-user access to the repository and the runtime source.

Cross-source consistency is enforced here, never silently reinterpreted:
matrix skills, graph nodes, and skills/ on disk must agree exactly;
every matrix dependency must be a graph edge; precedence must be
unique 1..15; conflicts and modes must name known skills and modes;
the fixed vocabularies must equal the unions of the matrix
routing_dimensions. Any contradiction aborts the build with the exact
mismatch printed.

Usage:
  python3 scripts/generate-routing-catalog.py [--check]
  --check exits 1 if the committed catalog differs from what this
  script would generate (used by CI).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is installed in CI
    print("generate-routing-catalog: PyYAML is required "
          "(pip install pyyaml)")
    sys.exit(1)

ROOT = os.path.join(os.path.dirname(__file__), "..")
REG = os.path.join(ROOT, "registry")
OUT_NAME = "routing-catalog.json"
CHECK = "--check" in sys.argv

CATALOG_VERSION = "2.4"

# Canonical source files (relative to the repo root) and their required
# versions. The catalog records each file's SHA-256 so a stale catalog
# is detectable and a runtime can prove which sources built it.
SOURCES = {
    "architecture/SKILL_ROUTING_MATRIX.yaml": "2.4",
    "architecture/WORKFLOW_GRAPH.yaml": "2.4",
    "architecture/intent-modes.yaml": "2.3",
    "architecture/COMPANION_CAPABILITY_REGISTRY.yaml": "2.4",
    "architecture/AGENT_COMPATIBILITY_MATRIX.yaml": "2.4",
}

# Fixed vocabularies (SKILL_ROUTING_MATRIX.yaml header, P0-006). The
# compiler asserts the derived unions equal these sets, so a matrix edit
# that silently drops a value fails the build instead of shrinking the
# vocabulary the runtime enforces.
EXPECTED_VOCABULARIES = {
    "visual_style": {
        "flat-2d-vector", "hand-drawn-2d", "illustrated-2d", "anime",
        "cartoon-2d", "stylized-3d", "semi-realistic-3d",
        "photorealistic-3d-cgi", "photorealistic-digital-human",
        "photorealistic-digital-animal-creature", "mixed",
        "captured-live-action",
    },
    "production_medium": {
        "2d-drawn-vector", "3d-cgi-rigged", "ai-digital-human",
        "ai-digital-creature", "live-action-footage", "hybrid-live-action-cgi",
    },
    "source_media": {
        "script-only", "reference-image", "reference-video",
        "captured-footage", "generated-image", "generated-video", "mixed",
    },
    "motion_method": {
        "rig-2d-keyframe", "rig-3d-keyframe", "ai-image-to-video",
        "ai-video-to-video", "motion-capture", "performance-transfer",
        "face-animation", "body-animation", "pose-gesture-transfer",
        "lip-sync-phoneme-viseme", "creature-articulation",
        "rotoscoping-compositing", "captured-motion",
    },
    "subject_kind": {
        "human", "digital-human", "real-animal", "cgi-animal",
        "fictional-creature", "anthropomorphic", "mixed", "non-character",
    },
    "interaction_pattern": {
        "single-performance", "two-person-conversation",
        "multi-person-conversation", "human-animal", "human-creature",
        "multiple-animals-creatures", "group-scene", "silent-reaction",
        "physical-contact-object",
    },
    "articulation_target": {
        "human-mouth-lips", "bird-beak", "animal-muzzle",
        "creature-jaw-mandibles", "other",
    },
}

# Routing-model sets from the P0-006 composable model (the same constants
# the P0 routing tests encode). They are recorded here so the runtime
# reads them as data, not as code constants.
GENERATED_MEDIA = [
    "2d-drawn-vector", "3d-cgi-rigged", "ai-digital-human",
    "ai-digital-creature",
]
GENERATED_SUBJECTS = [
    "digital-human", "cgi-animal", "fictional-creature", "anthropomorphic",
]
# Styles whose skill carries a style lock (cinematic-power §1).
CINEMATIC_STYLES = [
    "stylized-3d", "anime", "cartoon-2d", "semi-realistic-3d",
    "photorealistic-3d-cgi",
]
# Animation styling (2D/3D) that cannot share one subject in one shot
# with a photorealistic digital human (TC-7).
ANIMATION_STYLES = [
    "anime", "cartoon-2d", "stylized-3d", "semi-realistic-3d",
    "photorealistic-3d-cgi",
]

EXPECTED_PINS = {
    "VoiceStudio": "2f2f5a9b0e982c6147efc6baaeae62936f29b79b",
    "OpenMontage": "fecb9a1e3cc23ef84de30b272059457a427f16f8",
}


class CatalogError(Exception):
    """A canonical routing-data inconsistency: the build stops here."""


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_yaml(rel: str):
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        raise CatalogError(f"{rel}: missing")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _catalog_fingerprint(catalog: dict) -> str:
    """SHA-256 of the canonical JSON of the catalog without its own
    integrity record. Must compute exactly what
    ``runtime.skill_router.catalog_fingerprint`` computes (same
    canonical form: sorted keys, compact separators, UTF-8) — the
    test suite loads every compiler-generated catalog through the
    runtime loader, so a divergence fails loudly instead of silently
    shipping a fingerprint the runtime rejects."""
    body = {k: v for k, v in catalog.items() if k != "integrity"}
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=False).encode("utf-8")).hexdigest()


def build() -> dict:
    docs = {}
    sources = {}
    for rel, version in SOURCES.items():
        doc = load_yaml(rel)
        docs[rel] = doc
        if str(doc.get("version")) != version:
            raise CatalogError(
                f"{rel}: version must be '{version}', "
                f"got {doc.get('version')!r}")
        sources[rel] = {
            "sha256": sha256_file(os.path.join(ROOT, rel)),
            "version": version,
        }

    matrix = docs["architecture/SKILL_ROUTING_MATRIX.yaml"]
    graph = docs["architecture/WORKFLOW_GRAPH.yaml"]
    modes_doc = docs["architecture/intent-modes.yaml"]
    companions_doc = docs["architecture/COMPANION_CAPABILITY_REGISTRY.yaml"]
    agents_doc = docs["architecture/AGENT_COMPATIBILITY_MATRIX.yaml"]

    # --- Cross-source consistency (never silently reinterpreted) --------
    fs_skills = sorted(
        d for d in os.listdir(os.path.join(ROOT, "skills"))
        if os.path.isdir(os.path.join(ROOT, "skills", d)))
    entries = matrix.get("skills") or []
    matrix_slugs = {e.get("skill") for e in entries}
    node_ids = {n.get("id") for n in (graph.get("nodes") or [])}
    if matrix_slugs != set(fs_skills):
        raise CatalogError(
            "routing matrix skill set != skills/ on disk: "
            f"matrix-only={sorted(matrix_slugs - set(fs_skills))} "
            f"disk-only={sorted(set(fs_skills) - matrix_slugs)}")
    if node_ids != set(fs_skills):
        raise CatalogError(
            "workflow graph node set != skills/ on disk: "
            f"graph-only={sorted(node_ids - set(fs_skills))} "
            f"disk-only={sorted(set(fs_skills) - node_ids)}")
    if len(entries) != 15:
        raise CatalogError(
            f"routing matrix must list exactly 15 skills, got {len(entries)}")

    precs = sorted(e.get("precedence") for e in entries)
    if precs != list(range(1, 16)):
        raise CatalogError(
            f"precedence values must be unique 1..15, got {precs}")
    prec_by_skill = {e["skill"]: e["precedence"] for e in entries}

    mode_names = set((modes_doc.get("modes") or {}).keys())
    if len(mode_names) != 13:
        raise CatalogError(
            f"intent-modes.yaml must list exactly 13 modes, got {len(mode_names)}")

    for e in entries:
        for field in ("skill_id", "skill", "activation_trigger",
                      "non_trigger", "required_inputs", "expected_outputs",
                      "dependencies", "precedence", "conflicts",
                      "applicable_modes", "quality_gate",
                      "approval_conditions"):
            # routing_dimensions is NOT required: the cross-cutting
            # resource-management skill states no routing dimensions
            # (it is consulted at every phase, never routed as a stage),
            # and a missing field means "no dimensions stated", not a
            # contradiction. The vocabulary union below treats it as empty.
            if field not in e:
                raise CatalogError(
                    f"routing entry {e.get('skill_id')}: missing field '{field}'")
        for dep in e.get("dependencies") or []:
            if dep not in matrix_slugs:
                raise CatalogError(
                    f"routing entry {e['skill']}: unknown dependency {dep!r}")
            if prec_by_skill[dep] >= e["precedence"]:
                raise CatalogError(
                    f"routing entry {e['skill']}: dependency {dep} "
                    f"(precedence {prec_by_skill[dep]}) does not run earlier "
                    f"(precedence {e['precedence']})")
        for conf in e.get("conflicts") or []:
            if conf not in matrix_slugs:
                raise CatalogError(
                    f"routing entry {e['skill']}: unknown conflict {conf!r}")
        for mode in e.get("applicable_modes") or []:
            if mode not in mode_names:
                raise CatalogError(
                    f"routing entry {e['skill']}: unknown mode {mode!r}")

    graph_edges = {(e.get("from"), e.get("to"))
                   for e in (graph.get("edges") or [])}
    matrix_deps = {(d, e["skill"]) for e in entries
                   for d in (e.get("dependencies") or [])}
    missing = sorted(matrix_deps - graph_edges)
    if missing:
        raise CatalogError(
            "matrix dependencies missing from the workflow graph: "
            f"{missing}")
    non_dep = sorted(graph_edges - matrix_deps)
    bad_router = [edge for edge in non_dep if edge[0] != "command-authority"]
    if bad_router:
        raise CatalogError(
            "non-dependency graph edges must be router edges "
            "(command-authority -> skill), got: "
            f"{bad_router}")

    # Acyclicity (Kahn's algorithm).
    children: dict[str, set[str]] = {n: set() for n in node_ids}
    indegree = {n: 0 for n in node_ids}
    for src, dst in graph_edges:
        if dst not in children[src]:
            children[src].add(dst)
            indegree[dst] += 1
    queue = [n for n, d in indegree.items() if d == 0]
    visited = 0
    while queue:
        n = queue.pop()
        visited += 1
        for dst in children[n]:
            indegree[dst] -= 1
            if indegree[dst] == 0:
                queue.append(dst)
    if visited != len(node_ids):
        raise CatalogError(
            f"workflow graph has a cycle (visited {visited}/{len(node_ids)})")

    for group in graph.get("parallel_groups") or []:
        members = set(group.get("skills") or [])
        if not members <= node_ids:
            raise CatalogError(
                f"parallel group {group.get('name')}: unknown skills "
                f"{sorted(members - node_ids)}")
        internal = [(a, b) for a in members for b in members
                    if (a, b) in graph_edges]
        if internal:
            raise CatalogError(
                f"parallel group {group.get('name')}: internal dependency "
                f"{internal}")
    for group in graph.get("conditional_parallel_groups") or []:
        members = set(group.get("skills") or [])
        if not members <= node_ids:
            raise CatalogError(
                f"conditional group {group.get('name')}: unknown skills "
                f"{sorted(members - node_ids)}")
        if not isinstance(group.get("condition"), str) \
                or len(group["condition"].strip()) < 20:
            raise CatalogError(
                f"conditional group {group.get('name')}: missing condition")
    tc_ids = [tc.get("id") for tc in (graph.get("true_conflicts") or [])]
    if sorted(tc_ids, key=lambda t: int(str(t)[3:])) != \
            [f"TC-{i}" for i in range(1, 11)]:
        raise CatalogError(
            f"true_conflicts must be exactly TC-1..TC-10, got {sorted(tc_ids)}")
    for tc in graph.get("true_conflicts") or []:
        for skill in tc.get("skills") or []:
            if skill not in node_ids:
                raise CatalogError(
                    f"true conflict {tc.get('id')}: unknown skill {skill!r}")
        if not isinstance(tc.get("scope"), str) or not tc["scope"].strip():
            raise CatalogError(
                f"true conflict {tc.get('id')}: missing scope")
        if not isinstance(tc.get("resolution"), str) \
                or not tc["resolution"].strip():
            raise CatalogError(
                f"true conflict {tc.get('id')}: missing resolution")

    comps = companions_doc.get("companions") or []
    if {c.get("name") for c in comps} != {"VoiceStudio", "OpenMontage"}:
        raise CatalogError(
            "companion registry must list exactly VoiceStudio + OpenMontage")
    for c in comps:
        if c.get("pinned_commit") != EXPECTED_PINS.get(c.get("name")):
            raise CatalogError(
                f"companion {c.get('name')}: pinned_commit "
                f"{c.get('pinned_commit')!r} does not match the setup.sh pin")

    # --- Fixed vocabularies: derived unions must equal the canonical sets
    derived: dict[str, set[str]] = {}
    for e in entries:
        for key, values in (e.get("routing_dimensions") or {}).items():
            derived.setdefault(key, set()).update(values)
    vocabularies: dict[str, list[str]] = {}
    for key, expected in EXPECTED_VOCABULARIES.items():
        got = derived.get(key, set())
        if got != expected:
            raise CatalogError(
                f"vocabulary {key}: derived union {sorted(got)} != "
                f"canonical set {sorted(expected)}")
        vocabularies[key] = sorted(expected)
    vocabularies["generated_media"] = sorted(GENERATED_MEDIA)
    vocabularies["generated_subjects"] = sorted(GENERATED_SUBJECTS)
    vocabularies["cinematic_styles"] = sorted(CINEMATIC_STYLES)
    vocabularies["animation_styles"] = sorted(ANIMATION_STYLES)
    vocabularies["intent_modes"] = sorted(mode_names)

    # --- Skills: matrix records verbatim + live SKILL.md fingerprints ---
    skills = []
    for e in sorted(entries, key=lambda x: x["precedence"]):
        slug = e["skill"]
        rel_path = f"skills/{slug}/SKILL.md"
        record = dict(e)
        record["path"] = rel_path
        record["sha256"] = sha256_file(os.path.join(ROOT, rel_path))
        skills.append(record)

    graph_out = {
        "router": graph.get("router"),
        "nodes": sorted(graph.get("nodes") or [],
                        key=lambda n: n.get("precedence", 99)),
        "edges": sorted(
            (graph.get("edges") or []),
            key=lambda e: (e.get("from", ""), e.get("to", ""))),
        "parallel_groups": sorted(
            (graph.get("parallel_groups") or []),
            key=lambda g: g.get("name", "")),
        "conditional_parallel_groups": sorted(
            (graph.get("conditional_parallel_groups") or []),
            key=lambda g: g.get("name", "")),
        "true_conflicts": sorted(
            (graph.get("true_conflicts") or []),
            key=lambda tc: int(str(tc.get("id", "TC-0"))[3:])),
        "sequential_chains": sorted(
            (graph.get("sequential_chains") or []),
            key=lambda c: c.get("name", "")),
        "cross_cutting": graph.get("cross_cutting") or [],
        "routing_model": graph.get("routing_model") or {},
        "representation": graph.get("representation") or {},
    }

    catalog = {
        "catalog_version": CATALOG_VERSION,
        "note": "Generated by scripts/generate-routing-catalog.py — "
                "never edit by hand.",
        "sources": sources,
        "skills": skills,
        "graph": graph_out,
        "intent_modes": modes_doc.get("modes") or {},
        "companions": sorted(comps, key=lambda c: c.get("name", "")),
        "agents": sorted(agents_doc.get("agents") or [],
                         key=lambda a: a.get("name", "")),
        "non_hosts": sorted(agents_doc.get("non_hosts") or [],
                            key=lambda n: n.get("name", "")),
        "vocabularies": vocabularies,
    }
    catalog["integrity"] = {
        "algorithm": "sha256-canonical-json-v1",
        "fingerprint": _catalog_fingerprint(catalog),
    }
    return catalog


def main() -> int:
    try:
        catalog = build()
    except CatalogError as exc:
        print(f"generate-routing-catalog: INCONSISTENT ROUTING DATA: {exc}")
        return 1
    path = os.path.join(REG, OUT_NAME)
    new = json.dumps(catalog, indent=2, sort_keys=True) + "\n"
    changed = False
    if os.path.exists(path):
        old = open(path, encoding="utf-8").read()
        if old != new:
            changed = True
    else:
        changed = True
    if CHECK:
        if changed:
            print(f"CHECK FAILED: {OUT_NAME} is out of date "
                  "(run scripts/generate-routing-catalog.py)")
            return 1
        print(f"CHECK OK: {OUT_NAME} matches the canonical routing sources")
        return 0
    os.makedirs(REG, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new)
    print(f"catalog_version={catalog['catalog_version']} "
          f"skills={len(catalog['skills'])} "
          f"edges={len(catalog['graph']['edges'])} "
          f"true_conflicts={len(catalog['graph']['true_conflicts'])} "
          f"changed={'yes' if changed else 'no'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
