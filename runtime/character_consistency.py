"""Consistency Frame P1 — character consistency evaluation (CF-WO-P1-006-R1).

Validates a project-local character bible, binds every scene to
it, verifies the reference assets against the real files, checks
that the project-local identity never leaks into the global
character registry, and evaluates scene-by-scene consistency
against the bible.

Honesty rules enforced here:

- No numeric consistency score is ever invented. The evaluation
  takes structured per-scene findings (human visual inspection
  plus asset metadata) and reports per-attribute pass / fail /
  needs-review, an explicit list of unexplained changes, and an
  overall verdict that is one of ``consistent``,
  ``drift-found`` or ``needs-human-review``. An embedding
  similarity score may be attached as supporting evidence only
  when its model and methodology are documented; it never
  decides the verdict.
- Automated tooling never claims human visual approval. The
  evaluation records who inspected what; editorial approval
  stays a separate, empty-until-human gate (see
  ``runtime.production_qc.qc_decision``).
- The demonstration character is project-local by construction:
  ``check_project_local_isolation`` verifies the character id
  is absent from the authorized global character registry.
  Nothing here registers anything anywhere.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess

from . import production_assets as assets_mod

BIBLE_SCHEMA_VERSION = "2.5"

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{2,63}$")
_HEX_RE = re.compile(r"^[0-9A-Fa-f]{6}$")

# Bible fields that must be present and non-empty.
_REQUIRED_BIBLE_FIELDS = (
    "character_id",
    "name",
    "age_range",
    "face",
    "hair",
    "body_proportions",
    "skin",
    "outfit",
    "signature_color",
    "accessories",
    "visual_constraints",
    "negative_constraints",
    "asset_provenance",
    "approval_state",
)

# Reference views the bible must inventory (asset ids + files).
_REQUIRED_REFERENCE_VIEWS = (
    "front",
    "three_quarter",
    "side",
    "full_body",
    "expressions",
)

# Consistency attributes evaluated for every scene.
CONSISTENCY_ATTRIBUTES = (
    "face_identity",
    "hair",
    "eyes",
    "outfit",
    "body_proportions",
    "signature_color",
    "accessories",
)

_FINDINGS = ("pass", "fail", "review")
_VERDICTS = ("consistent", "drift-found", "needs-human-review")


class CharacterConsistencyError(ValueError):
    """Character consistency error carrying structured messages."""

    def __init__(self, errors):
        if isinstance(errors, str):
            errors = [errors]
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


def _is_id(value) -> bool:
    return isinstance(value, str) and bool(_ID_RE.match(value))


def validate_character_bible(bible) -> list:
    """Bible errors (empty list = valid).

    Every required design field must be present; the signature
    color must be defined exactly once (one hex value); the
    reference inventory must list all five views with asset ids
    and files; CONFIRMED design details must be distinguishable
    from production inferences (the bible carries either a
    ``provenance`` of ``CONFIRMED`` on the design or an explicit
    ``inferences`` list — an inferred detail with no record is
    an error, never silently canon).
    """
    errors: list[str] = []
    if not isinstance(bible, dict):
        return ["character bible: expected an object"]
    if bible.get("schema_version") != BIBLE_SCHEMA_VERSION:
        errors.append(
            "character bible schema_version must be "
            f"'{BIBLE_SCHEMA_VERSION}', got "
            f"{bible.get('schema_version')!r}")
    character_id = bible.get("character_id")
    if not _is_id(character_id):
        errors.append(
            f"character bible character_id {character_id!r} is not "
            "a valid id")
    if bible.get("is_canonical_user_character") is not False:
        errors.append(
            "character bible must state "
            "is_canonical_user_character: false — a demonstration "
            "identity is never an existing canonical character")
    if bible.get("is_registered_in_global_registry") is not False:
        errors.append(
            "character bible must state "
            "is_registered_in_global_registry: false — a "
            "project-local identity is never registered globally")
    for field in _REQUIRED_BIBLE_FIELDS:
        value = bible.get(field)
        if value is None or value == "" or value == [] or value == {}:
            errors.append(
                f"character bible field {field!r} is missing or "
                "empty")
    age = bible.get("age_range") or {}
    if isinstance(age, dict):
        low = age.get("min_years")
        high = age.get("max_years")
        if not isinstance(low, (int, float)) \
                or not isinstance(high, (int, float)) \
                or float(low) <= 0 or float(high) < float(low):
            errors.append(
                "character bible age_range must carry a valid "
                f"min/max year range, got {low!r}/{high!r}")
        if isinstance(low, (int, float)) and float(low) < 18:
            errors.append(
                "character bible age_range starts below 18: a "
                "demonstration character for this round must be an "
                "adult (18+)")
    color = bible.get("signature_color") or {}
    if isinstance(color, dict):
        if color.get("defined_once") is not True:
            errors.append(
                "character bible signature_color must be defined "
                "once (defined_once: true)")
        hex_value = color.get("hex")
        if not isinstance(hex_value, str) \
                or not _HEX_RE.match(hex_value):
            errors.append(
                "character bible signature_color.hex must be one "
                f"6-digit hex value, got {hex_value!r}")
    references = bible.get("references") or {}
    if not isinstance(references, dict):
        errors.append("character bible references: expected an object")
    else:
        for view in _REQUIRED_REFERENCE_VIEWS:
            entry = references.get(view)
            if not isinstance(entry, dict):
                errors.append(
                    f"character bible references.{view} is missing")
                continue
            if not entry.get("asset_id"):
                errors.append(
                    f"character bible references.{view}.asset_id is "
                    "missing")
            if not entry.get("file"):
                errors.append(
                    f"character bible references.{view}.file is "
                    "missing")
    provenance = bible.get("provenance") or {}
    if isinstance(provenance, dict):
        if provenance.get("design") not in ("CONFIRMED", "INFERRED"):
            errors.append(
                "character bible provenance.design must be "
                "CONFIRMED or INFERRED")
        if provenance.get("design") == "INFERRED" \
                and not provenance.get("inferences"):
            errors.append(
                "character bible design is INFERRED but no "
                "inferences are recorded — an inferred detail may "
                "never silently become approved canon")
    return errors


def validate_scene_binding(bible, shot) -> list:
    """Scene-to-bible binding errors (empty list = valid).

    The shot's character id must be the bible's character id;
    its reference ids must resolve to bible references; its
    expression (when given) must resolve to a bible expression;
    its motion must be a known still motion; environment and
    prop ids must be non-empty strings.
    """
    errors: list[str] = []
    if not isinstance(bible, dict) or not isinstance(shot, dict):
        return ["scene binding: bible and shot must both be objects"]
    character_id = bible.get("character_id")
    if shot.get("character_id") != character_id:
        errors.append(
            f"shot {shot.get('shot_id')!r} character_id "
            f"{shot.get('character_id')!r} does not match the bible "
            f"character {character_id!r}")
    references = bible.get("references") or {}
    known_refs = {str((entry or {}).get("asset_id"))
                  for entry in references.values()
                  if isinstance(entry, dict)}
    for ref_id in shot.get("reference_ids") or []:
        if ref_id not in known_refs:
            errors.append(
                f"shot {shot.get('shot_id')!r} reference id "
                f"{ref_id!r} does not resolve to a bible reference")
    expression = shot.get("expression")
    if expression:
        expressions = bible.get("expressions") or {}
        wanted = str(expression).split(",")[0].strip().lower()
        known = {str(key).lower()
                 for key in expressions.keys()
                 if isinstance(key, str)}
        if wanted not in known:
            errors.append(
                f"shot {shot.get('shot_id')!r} expression "
                f"{expression!r} does not resolve to a bible "
                "expression")
    motion = (shot.get("visual") or {}).get("motion")
    if motion is not None and motion not in assets_mod.STILL_MOTIONS:
        errors.append(
            f"shot {shot.get('shot_id')!r} motion {motion!r} is not "
            "a known still motion")
    if not isinstance(shot.get("environment_id"), str) \
            or not shot.get("environment_id"):
        errors.append(
            f"shot {shot.get('shot_id')!r} environment_id is "
            "missing or empty")
    for prop_id in shot.get("prop_ids") or []:
        if not isinstance(prop_id, str) or not prop_id:
            errors.append(
                f"shot {shot.get('shot_id')!r} carries an invalid "
                f"prop id {prop_id!r}")
    return errors


def verify_reference_assets(bible, delivery_root, *,
                            ffprobe="ffprobe") -> dict:
    """Verify every bible reference against the real file.

    ``delivery_root`` is the delivery folder root; bible
    ``file`` entries are relative to it (for example
    ``work/references/mara-front-ref.png``). Returns
    ``{"references": [...], "errors": [...]}``. Each reference
    entry carries asset id, view, file, byte size, SHA-256,
    probed width/height and status VERIFIED. A missing file, an
    unreadable image, or a path escaping the delivery root is
    an error, never a substitution.
    """
    report: dict = {"references": [], "errors": []}
    references = (bible or {}).get("references") or {}
    root = os.path.realpath(delivery_root)
    for view in _REQUIRED_REFERENCE_VIEWS:
        entry = references.get(view) or {}
        asset_id = entry.get("asset_id") or f"ref-{view}"
        rel = entry.get("file") or ""
        real = os.path.realpath(os.path.join(root, rel))
        if not real.startswith(root + os.sep) and real != root:
            report["errors"].append(
                f"reference {asset_id!r} path {rel!r} escapes the "
                "references root")
            continue
        if not os.path.isfile(real):
            report["errors"].append(
                f"reference {asset_id!r} file {rel!r} does not exist")
            continue
        with open(real, "rb") as handle:
            raw = handle.read()
        probe = assets_mod.probe_media_file(real, ffprobe=ffprobe)
        if probe["width"] is None or probe["height"] is None:
            report["errors"].append(
                f"reference {asset_id!r} is not a readable image")
            continue
        report["references"].append({
            "asset_id": asset_id,
            "view": view,
            "file": rel,
            "size_bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "width": probe["width"],
            "height": probe["height"],
            "status": "VERIFIED",
        })
    return report


def check_project_local_isolation(character_id, *,
                                 overlay_root=None) -> list:
    """Isolation errors (empty list = isolated).

    The project-local character id must be absent from the
    authorized global character registry. When no overlay root
    is configured in this environment the global registry is
    empty and isolation holds by construction — that is recorded
    by the caller, not hidden. This function never registers
    anything.
    """
    errors: list[str] = []
    if not _is_id(character_id):
        return [f"character id {character_id!r} is not a valid id"]
    try:
        from .identity_resolution import (
            load_authorized_character_registry)
        registry = load_authorized_character_registry(
            overlay_root) if overlay_root else {}
    except Exception:  # noqa: BLE001 - no registry means isolated
        registry = {}
    records = registry if isinstance(registry, dict) else {}
    for key, record in records.items():
        record_id = key
        if isinstance(record, dict):
            record_id = record.get("character_id") or key
        if record_id == character_id:
            errors.append(
                f"character id {character_id!r} is present in the "
                "authorized global character registry — a "
                "project-local identity must never collide with a "
                "registered character")
    return errors


def evaluate_consistency(bible, scene_evaluations) -> dict:
    """Evaluate scene-by-scene consistency against the bible.

    ``scene_evaluations`` is a list of per-scene findings, each
    ``{"scene_id", "shot_id", "inspector", "checks": {attribute:
    "pass" | "fail" | "review", ...}, "notes": "...",
    "allowed_variations": [...], "unexplained_changes": [...]}``.
    The verdict is rule-based, never a score: any ``fail`` (or
    any unexplained change) gives ``drift-found``; otherwise any
    ``review`` gives ``needs-human-review``; otherwise
    ``consistent``. Missing attributes are ``review``, never
    silently ``pass``.
    """
    errors: list[str] = []
    if not isinstance(scene_evaluations, list) \
            or not scene_evaluations:
        raise CharacterConsistencyError(
            "consistency evaluation needs a non-empty list of "
            "scene evaluations")
    character_id = (bible or {}).get("character_id")
    scenes = []
    overall = "consistent"
    for index, evaluation in enumerate(scene_evaluations):
        where = f"scene_evaluations[{index}]"
        if not isinstance(evaluation, dict):
            errors.append(f"{where}: expected an object")
            continue
        scene_id = evaluation.get("scene_id")
        checks = evaluation.get("checks") or {}
        if not isinstance(checks, dict):
            errors.append(f"{where}.checks: expected an object")
            continue
        scene_result = {"scene_id": scene_id,
                        "shot_id": evaluation.get("shot_id"),
                        "inspector": evaluation.get("inspector"),
                        "checks": {},
                        "allowed_variations":
                            list(evaluation.get("allowed_variations")
                                 or []),
                        "unexplained_changes":
                            list(evaluation.get("unexplained_changes")
                                 or []),
                        "notes": evaluation.get("notes") or ""}
        for attribute in CONSISTENCY_ATTRIBUTES:
            finding = checks.get(attribute, "review")
            if finding not in _FINDINGS:
                errors.append(
                    f"{where}.checks.{attribute} finding "
                    f"{finding!r} is not one of "
                    f"{', '.join(_FINDINGS)}")
                finding = "review"
            scene_result["checks"][attribute] = finding
        if scene_result["unexplained_changes"]:
            scene_result["verdict"] = "drift-found"
        elif "fail" in scene_result["checks"].values():
            scene_result["verdict"] = "drift-found"
        elif "review" in scene_result["checks"].values():
            scene_result["verdict"] = "needs-human-review"
        else:
            scene_result["verdict"] = "consistent"
        if scene_result["verdict"] == "drift-found":
            overall = "drift-found"
        elif scene_result["verdict"] == "needs-human-review" \
                and overall == "consistent":
            overall = "needs-human-review"
        scenes.append(scene_result)
    if errors:
        raise CharacterConsistencyError(errors)
    attribute_summary = {}
    for attribute in CONSISTENCY_ATTRIBUTES:
        counts = {"pass": 0, "fail": 0, "review": 0}
        for scene in scenes:
            counts[scene["checks"][attribute]] += 1
        attribute_summary[attribute] = counts
    return {
        "character_id": character_id,
        "scenes": scenes,
        "attribute_summary": attribute_summary,
        "overall_verdict": overall,
        "human_approval": None,
        "note": "Automated evaluation only. Editorial approval "
                "stays empty until a named human reviewer approves "
                "the visual evidence.",
    }


def build_reference_sheet(reference_paths, output_path, *,
                          ffmpeg="ffmpeg", timeout_s=300) -> dict:
    """Tile reference images into one reference sheet (FFmpeg).

    ``reference_paths`` is an ordered list of image files
    (front, three-quarter, side, full-body). Each is scaled to
    the same height and stacked horizontally. Returns the sheet
    path, size and SHA-256. Raises
    :class:`CharacterConsistencyError` on failure.
    """
    if len(reference_paths) < 2:
        raise CharacterConsistencyError(
            "reference sheet needs at least two reference images")
    for path in reference_paths:
        if not os.path.isfile(path):
            raise CharacterConsistencyError(
                f"reference sheet input {path!r} does not exist")
    tile_height = 1400
    inputs: list[str] = []
    filters: list[str] = []
    for index, path in enumerate(reference_paths):
        inputs += ["-i", path]
        filters.append(
            f"[{index}:v]scale=-2:{tile_height}[r{index}]")
    filters.append(
        "".join(f"[r{i}]" for i in range(len(reference_paths)))
        + f"hstack=inputs={len(reference_paths)}[out]")
    argv = [ffmpeg, "-y", "-v", "error"] + inputs + [
        "-filter_complex", ";".join(filters),
        "-map", "[out]", "-frames:v", "1", output_path]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True,
                              timeout=timeout_s)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CharacterConsistencyError(
            f"reference sheet build failed: {exc}") from exc
    if proc.returncode != 0 or not os.path.isfile(output_path):
        raise CharacterConsistencyError(
            "reference sheet build failed: "
            f"{(proc.stderr or '').strip()[:500]}")
    raw = open(output_path, "rb").read()
    return {"path": output_path, "size_bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def build_identity_comparison_sheet(front_reference, keyframe_paths,
                                    output_path, *, ffmpeg="ffmpeg",
                                    timeout_s=300) -> dict:
    """Tile the front reference beside every scene keyframe.

    One row: front reference first, then one keyframe per scene
    in order. Returns the sheet path, size and SHA-256. Raises
    :class:`CharacterConsistencyError` on failure.
    """
    paths = [front_reference] + list(keyframe_paths or [])
    if len(paths) < 2:
        raise CharacterConsistencyError(
            "identity comparison sheet needs the front reference "
            "and at least one keyframe")
    return build_reference_sheet(paths, output_path, ffmpeg=ffmpeg,
                                 timeout_s=timeout_s)
