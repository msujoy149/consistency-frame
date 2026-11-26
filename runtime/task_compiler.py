"""Consistency Frame P1 — deterministic provider-neutral task compiler
(CF-WO-P1-004, Task J).

Converts a validated production bundle (P1-003 Script-to-Performance
bundle, plus the AI host's production analysis) into actionable task
packets: one deterministic packet per unit of production work
(character/reference preparation, image generation, video generation,
voice generation, sound generation, editing and finishing, QC review).

The compiler is Layer B work: deterministic validation, binding and
assembly. It never performs creative reasoning (that is the AI host's
Layer A analysis, supplied as input), never calls a provider, never
generates media, never persists anything, and never pretends a packet
executed. A packet is a plan for work, not proof of work.

Provider matching is evidence-based: a provider is matched only when
its capability record (``registry/providers.json``, generated from
``architecture/COMPANION_CAPABILITY_REGISTRY.yaml``) actually evidences
the required operations and capabilities. Conformance status VERIFIED
(a formal test passed) is preferred, EXERCISED (exercised in a
recorded run, no formal test) is accepted, NOT_TESTED and FAILED are
never matched. When no verified provider exists for a task, the
compiler returns a complete provider-neutral handoff packet
(``provider_status: unavailable-no-verified-provider``) and records
the reason — it never invents a provider and never silently changes
a character reference, voice profile or quality constraint.

Commercial voice rule: a job flagged commercial is never matched to a
provider whose ``commercial_use_approved`` is false. The default
OmniVoice weights are CC-BY-NC and are not cleared for commercial or
monetised production; such voice tasks compile as handoffs with the
restriction recorded.

Determinism: packets carry no timestamps. ``packet_hash`` is the
SHA-256 of the canonical JSON of the packet without the packet_hash
field itself (the same pattern as the router's ``plan_hash`` and the
S2P ``bundle_hash``). Inputs are never modified in place; no partial
package is ever returned.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re

from . import local_session

ROOT = os.path.join(os.path.dirname(__file__), "..")
SCHEMAS_DIR = os.path.join(ROOT, "schemas")
PROVIDERS_PATH = os.path.join(ROOT, "registry", "providers.json")

TASK_PACKET_SCHEMA_VERSION = "2.5"
PROVIDER_SCHEMA_VERSION = "2.5"

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")

# Conformance ranks for provider matching. Lower is better; only the
# first two ranks are ever matched.
_CONFORMANCE_RANK = {"VERIFIED": 0, "EXERCISED": 1,
                     "NOT_TESTED": 2, "FAILED": 3}
_MATCHABLE = ("VERIFIED", "EXERCISED")

# Task type -> what a provider must evidence to be matched.
# `types` are provider_type values; `operations` must all be present;
# the boolean flags require the matching capability fields.
TASK_PROVIDER_REQUIREMENTS = {
    "character-design": {
        "types": ("local-tool",),
        "operations": ("design-brief",),
        "needs_reference_image": False,
        "needs_character_reference": False,
        "needs_audio": False,
    },
    "reference-sheet": {
        "types": ("image-generation", "local-tool"),
        "operations": ("generate-image",),
        "needs_reference_image": True,
        "needs_character_reference": True,
        "needs_audio": False,
    },
    "environment-reference": {
        "types": ("image-generation", "local-tool"),
        "operations": ("generate-image",),
        "needs_reference_image": False,
        "needs_character_reference": False,
        "needs_audio": False,
    },
    "prop-reference": {
        "types": ("image-generation", "local-tool"),
        "operations": ("generate-image",),
        "needs_reference_image": False,
        "needs_character_reference": False,
        "needs_audio": False,
    },
    "image-generation": {
        "types": ("image-generation",),
        "operations": ("generate-image",),
        "needs_reference_image": True,
        "needs_character_reference": True,
        "needs_audio": False,
    },
    "video-generation": {
        "types": ("video-generation",),
        "operations": ("generate-video",),
        "needs_reference_image": True,
        "needs_character_reference": True,
        "needs_audio": False,
    },
    "voice-generation": {
        "types": ("voice-tts", "voice-cloning"),
        "operations": ("generate-speech",),
        "needs_reference_image": False,
        "needs_character_reference": False,
        "needs_audio": True,
    },
    "sound-generation": {
        "types": ("sound-effects", "music"),
        "operations": ("generate-sound",),
        "needs_reference_image": False,
        "needs_character_reference": False,
        "needs_audio": True,
    },
    "editing-finishing": {
        "types": ("editing-rendering", "local-tool"),
        "operations": ("assemble-timeline",),
        "needs_reference_image": False,
        "needs_character_reference": False,
        "needs_audio": True,
    },
    "qc-review": {
        "types": ("local-tool",),
        "operations": ("probe-media",),
        "needs_reference_image": False,
        "needs_character_reference": False,
        "needs_audio": False,
    },
    "regeneration": {
        "types": ("image-generation", "video-generation",
                  "voice-tts", "sound-effects"),
        "operations": (),
        "needs_reference_image": False,
        "needs_character_reference": False,
        "needs_audio": False,
    },
}


class TaskCompilerError(ValueError):
    """Fail-closed error for the task compiler.

    Carries a list of human-readable reasons, like
    :class:`runtime.script_to_performance.ScriptToPerformanceError`.
    """

    def __init__(self, errors):
        if isinstance(errors, str):
            errors = [errors]
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


def canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def task_packet_hash(packet: dict) -> str:
    """Deterministic hash of a task packet (excluding packet_hash)."""
    probe = {k: v for k, v in packet.items() if k != "packet_hash"}
    return sha256_hex(canonical_json(probe))


def load_schema(name: str) -> dict:
    path = os.path.join(SCHEMAS_DIR, name)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_instance(schema: dict, value, path: str,
                       errors: list[str]) -> None:
    """Minimal validator for the repo's restricted JSON-Schema subset.

    Handles type, properties, required, additionalProperties, enum,
    pattern, minLength, minItems, minimum, maximum, exclusiveMinimum
    and items. An explicit null fails every type check (no type in
    the subset includes null), which is the required nullability
    behaviour: present-with-null is a type error, omitted is valid
    wherever the schema permits omission.
    """
    t = schema.get("type")
    if t == "object":
        if not isinstance(value, dict):
            errors.append(f"{path}: expected object, "
                          f"got {type(value).__name__}")
            return
        props = schema.get("properties") or {}
        for req in schema.get("required") or []:
            if req not in value:
                errors.append(f"{path}: missing required field '{req}'")
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    errors.append(f"{path}: unexpected field '{key}'")
        for name, sub in props.items():
            if name in value:
                validate_instance(sub, value[name], f"{path}.{name}",
                                   errors)
    elif t == "array":
        if not isinstance(value, list):
            errors.append(f"{path}: expected array, "
                          f"got {type(value).__name__}")
            return
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: array has {len(value)} items, "
                          f"minimum is {schema['minItems']}")
        items = schema.get("items")
        if isinstance(items, dict):
            for i, item in enumerate(value):
                validate_instance(items, item, f"{path}[{i}]", errors)
    elif t == "string":
        if not isinstance(value, str):
            errors.append(f"{path}: expected string, "
                          f"got {type(value).__name__}")
            return
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: string shorter than "
                          f"minLength {schema['minLength']}")
        if "pattern" in schema and not re.search(schema["pattern"],
                                                 value):
            errors.append(f"{path}: string {value!r} does not match "
                          f"pattern {schema['pattern']}")
        if "enum" in schema and value not in schema["enum"]:
            errors.append(f"{path}: {value!r} is not one of "
                          f"{sorted(schema['enum'])}")
    elif t == "integer":
        if type(value) is not int:
            errors.append(f"{path}: expected integer, "
                          f"got {type(value).__name__}")
            return
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value} is below minimum "
                          f"{schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: {value} is above maximum "
                          f"{schema['maximum']}")
        if "exclusiveMinimum" in schema \
                and value <= schema["exclusiveMinimum"]:
            errors.append(f"{path}: {value} is not above "
                          f"exclusiveMinimum {schema['exclusiveMinimum']}")
        if "enum" in schema and value not in schema["enum"]:
            errors.append(f"{path}: {value!r} is not one of "
                          f"{sorted(schema['enum'])}")
    elif t == "number":
        if type(value) not in (int, float) or isinstance(value, bool):
            errors.append(f"{path}: expected number, "
                          f"got {type(value).__name__}")
            return
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value} is below minimum "
                          f"{schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: {value} is above maximum "
                          f"{schema['maximum']}")
        if "exclusiveMinimum" in schema \
                and value <= schema["exclusiveMinimum"]:
            errors.append(f"{path}: {value} is not above "
                          f"exclusiveMinimum {schema['exclusiveMinimum']}")
    elif t == "boolean":
        if type(value) is not bool:
            errors.append(f"{path}: expected boolean, "
                          f"got {type(value).__name__}")
    else:
        errors.append(f"{path}: schema has unsupported type {t!r}")


def schema_errors(schema_name: str, value, label: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{label}: expected an object, "
                f"got {type(value).__name__}"]
    schema = load_schema(f"{schema_name}.json")
    errors: list[str] = []
    validate_instance(schema, value, label, errors)
    return errors


def validate_task_packet(packet) -> list[str]:
    """Schema errors for one task packet (empty list = valid)."""
    errors = schema_errors("task-packet", packet, "task_packet")
    if isinstance(packet, dict):
        if packet.get("schema_version") != TASK_PACKET_SCHEMA_VERSION:
            errors.append("task_packet.schema_version must be "
                          f"'{TASK_PACKET_SCHEMA_VERSION}', got "
                          f"{packet.get('schema_version')!r}")
        stored = packet.get("packet_hash")
        if isinstance(stored, str) and _SHA_RE.match(stored):
            if task_packet_hash(packet) != stored:
                errors.append("task_packet.packet_hash does not match "
                              "the recomputed packet hash")
        if packet.get("task_type") not in TASK_PROVIDER_REQUIREMENTS:
            errors.append("task_packet.task_type "
                          f"{packet.get('task_type')!r} is not a known "
                          "task type")
        translation = packet.get("provider_translation")
        if isinstance(translation, dict) \
                and packet.get("provider_status") \
                == "unavailable-no-verified-provider":
            errors.append("task_packet.provider_translation must be "
                          "absent when provider_status is "
                          "unavailable-no-verified-provider")
    return errors


def validate_provider_record(record) -> list[str]:
    """Schema errors for one provider capability record."""
    errors = schema_errors("provider-capability", record,
                            "provider_record")
    if isinstance(record, dict):
        if record.get("schema_version") != PROVIDER_SCHEMA_VERSION:
            errors.append("provider_record.schema_version must be "
                          f"'{PROVIDER_SCHEMA_VERSION}', got "
                          f"{record.get('schema_version')!r}")
        conformance = record.get("conformance")
        if isinstance(conformance, dict):
            if conformance.get("status") not in _CONFORMANCE_RANK:
                errors.append("provider_record.conformance.status "
                              f"{conformance.get('status')!r} is not a "
                              "known conformance status")
    return errors


def validate_task_package(package) -> list[str]:
    """Structural + per-packet errors for a compiled task package."""
    errors: list[str] = []
    if not isinstance(package, dict):
        return ["task_package: expected an object, "
                f"got {type(package).__name__}"]
    for field in ("package_id", "job_id", "project_id", "package_hash"):
        if not isinstance(package.get(field), str) \
                or not package.get(field):
            errors.append(f"task_package: missing or empty '{field}'")
    if package.get("package_id") \
            and not _ID_RE.match(package["package_id"]):
        errors.append("task_package.package_id "
                      f"{package.get('package_id')!r} is not a valid id")
    packets = package.get("packets")
    if not isinstance(packets, list):
        errors.append("task_package.packets: expected an array")
        return errors
    seen: set[str] = set()
    for packet in packets:
        errors.extend(validate_task_packet(packet))
        if isinstance(packet, dict):
            task_id = packet.get("task_id")
            if task_id in seen:
                errors.append(f"task_package: duplicate task_id "
                              f"{task_id!r}")
            seen.add(task_id)
    stored = package.get("package_hash")
    if isinstance(stored, str) and _SHA_RE.match(stored):
        probe = {k: v for k, v in package.items()
                 if k != "package_hash"}
        if sha256_hex(canonical_json(probe)) != stored:
            errors.append("task_package.package_hash does not match "
                          "the recomputed package hash")
    for entry in package.get("unmatched_tasks") or []:
        if not isinstance(entry, dict) \
                or not entry.get("task_id") or not entry.get("reason"):
            errors.append("task_package.unmatched_tasks: every entry "
                          "needs task_id and reason")
    return errors


def load_provider_registry(providers_path=None) -> list[dict]:
    """Load and validate the compiled provider registry.

    Raises TaskCompilerError when the file is missing, malformed, or
    any record fails its schema. The runtime never invents a
    provider: an empty or unreadable registry means every task
    compiles as a handoff, never as an execution claim.
    """
    path = providers_path or PROVIDERS_PATH
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError as exc:
        raise TaskCompilerError(
            f"provider registry not found at {path}") from exc
    except (OSError, ValueError) as exc:
        raise TaskCompilerError(
            f"provider registry at {path} is unreadable: {exc}") from exc
    records = data.get("records") if isinstance(data, dict) else None
    if not isinstance(records, list):
        raise TaskCompilerError(
            "provider registry has no 'records' array")
    errors: list[str] = []
    for record in records:
        errors.extend(validate_provider_record(record))
    if errors:
        raise TaskCompilerError(errors)
    return copy.deepcopy(records)


def match_provider_for_task(task_type: str, providers,
                            *, commercial_use: bool = False,
                            needs_clone: bool = False):
    """Match one task to the best evidenced provider.

    Returns ``(provider_id or None, reason)``. Matching is
    deterministic: candidates are ranked by conformance (VERIFIED
    before EXERCISED) then provider_id, and the first match wins.
    A task that needs voice cloning additionally requires the
    provider to evidence the ``clone-voice`` operation. Commercial
    jobs exclude every provider whose ``commercial_use_approved`` is
    false. NOT_TESTED and FAILED providers are never matched.
    """
    if task_type not in TASK_PROVIDER_REQUIREMENTS:
        return None, f"unknown task type {task_type!r}"
    req = TASK_PROVIDER_REQUIREMENTS[task_type]
    needed_ops = list(req["operations"])
    if needs_clone and "clone-voice" not in needed_ops:
        needed_ops.append("clone-voice")
    candidates = []
    for provider in providers or []:
        pid = provider.get("provider_id")
        conformance = provider.get("conformance") or {}
        status = conformance.get("status")
        if status not in _MATCHABLE:
            continue
        if provider.get("provider_type") not in req["types"]:
            continue
        operations = provider.get("operations") or []
        if any(op not in operations for op in needed_ops):
            continue
        if req["needs_reference_image"] \
                and not provider.get("reference_image_capability"):
            continue
        if req["needs_character_reference"] \
                and not provider.get("character_reference_capability"):
            continue
        if req["needs_audio"] and not provider.get("audio_capability"):
            continue
        if commercial_use and not provider.get("commercial_use_approved"):
            continue
        candidates.append((_CONFORMANCE_RANK[status], pid))
    if not candidates:
        reason = ("no matched provider: no VERIFIED or EXERCISED "
                  "provider evidences the required capabilities"
                  + (" for a commercial job" if commercial_use else ""))
        return None, reason
    candidates.sort()
    return candidates[0][1], "matched"


__all__ = [
    "TaskCompilerError",
    "TASK_PROVIDER_REQUIREMENTS",
    "canonical_json",
    "sha256_hex",
    "load_schema",
    "schema_errors",
    "validate_instance",
    "task_packet_hash",
    "validate_task_packet",
    "validate_task_package",
    "validate_provider_record",
    "load_provider_registry",
    "match_provider_for_task",
    "compile_task_package",
    "compile_regeneration_packets",
]


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _cue_text(cue) -> str:
    if isinstance(cue, str):
        return cue
    if isinstance(cue, dict):
        return str(cue.get("cue") or cue.get("description")
                   or canonical_json(cue))
    return str(cue)


def _final_dialogue_text(bundle: dict, line: dict) -> str:
    """The text a voice packet must speak: the source script text,
    or the authorised rewritten text when a rewrite was authorised
    for exactly this line."""
    script_lines = (bundle.get("script_contract") or {}).get("dialogue") \
        or []
    source_text = None
    for entry in script_lines:
        if isinstance(entry, dict) \
                and entry.get("line_id") == line.get("line_id"):
            source_text = entry.get("text")
            break
    dialogue = line.get("dialogue") or {}
    s2p = bundle.get("script_to_performance") or {}
    if s2p.get("dialogue_rewrite_authorised") is True \
            and dialogue.get("rewrite_permitted") is True \
            and dialogue.get("rewritten_text"):
        return str(dialogue["rewritten_text"])
    if source_text is not None:
        return str(source_text)
    return str(dialogue.get("text") or "")


def _build_packet(*, packet_id, task_id, job_id, project_id, task_type,
                  scene_id, shot_id, instruction, inputs, requirements,
                  restrictions, expected, qc_conditions, provenance,
                  authorization_action, providers, commercial_use,
                  needs_clone=False, translation_note=None,
                  match_provider=True, match_task_type=None):
    """Assemble one packet, match a provider, hash it, validate it.

    Matching never changes the canonical instruction: a matched
    provider gets a provider_translation only when the match is
    real; an unmatched task keeps its full canonical instruction
    as a handoff and records why no provider matched. Host work
    (``match_provider=False``, for example character design, which
    the reasoning host does) is handed off directly with
    provider_status ``handed-off`` — it is never matched against
    a media provider.
    """
    if match_provider:
        provider_id, reason = match_provider_for_task(
            match_task_type or task_type, providers,
            commercial_use=commercial_use,
            needs_clone=needs_clone)
        provider_status = ("not-executed" if provider_id
                           else "unavailable-no-verified-provider")
    else:
        provider_id, reason = None, None
        provider_status = "handed-off"
    packet = {
        "schema_version": TASK_PACKET_SCHEMA_VERSION,
        "packet_id": packet_id,
        "task_id": task_id,
        "job_id": job_id,
        "project_id": project_id,
        "task_type": task_type,
        "canonical_instruction": instruction,
        "provider_capability_requirements": [
            {"capability": cap, "required": True}
            for cap in requirements
        ],
        "restrictions": list(restrictions),
        "expected_output": expected,
        "qc_conditions": list(qc_conditions),
        "authorization_required": {
            "action": authorization_action,
            "required": True,
        },
        "provenance": provenance,
        "provider_status": provider_status,
        "required_inputs": inputs,
    }
    if scene_id is not None:
        packet["scene_id"] = scene_id
    if shot_id is not None:
        packet["shot_id"] = shot_id
    if provider_id is not None:
        packet["provider_translation"] = {
            "provider_id": provider_id,
            "translated_instruction":
                (translation_note or instruction),
        }
    packet["packet_hash"] = task_packet_hash(packet)
    errors = validate_task_packet(packet)
    if errors:
        raise TaskCompilerError(errors)
    if provider_id is not None or not match_provider:
        return packet, None
    return packet, {"task_id": task_id, "reason": reason}


def compile_task_package(session, job, bundle, analysis=None,
                         proposals=None, providers=None, *,
                         voice_consent=False, voice_kinds=None,
                         providers_path=None) -> dict:
    """Compile a deterministic production task package from a
    validated S2P bundle and the AI host's production analysis.

    ``job`` is the orchestrator job record (it carries job_id,
    project_id, commercial_use and the stills_first flag).
    ``bundle`` is a validated Script-to-Performance bundle. ``analysis``
    is a validated production analysis (may be None for bundles built
    without one). ``proposals`` are validated character-design
    proposal records for every task-local proposal the analysis
    references. ``providers`` is a validated provider list; when
    None, the compiled ``registry/providers.json`` is loaded.

    Voice cloning needs two things: the voice kind must be declared
    ``clone`` for that voice profile, and ``voice_consent`` must be
    the actual boolean True. Anything else fails closed.

    Raises TaskCompilerError on any failure and returns nothing
    partial. Inputs are never modified in place.
    """
    if not local_session.is_active_session(session):
        reasons = local_session.validate_session(session)
        raise TaskCompilerError(
            "no active session for task compilation"
            + (f": {'; '.join(reasons)}" if reasons else ""))
    if type(voice_consent) is not bool:
        raise TaskCompilerError(
            "voice_consent must be an actual boolean, got "
            f"{type(voice_consent).__name__}")
    if not isinstance(job, dict):
        raise TaskCompilerError("job is not an object")
    job_id = job.get("job_id")
    project_id = job.get("project_id")
    if not isinstance(job_id, str) or not _ID_RE.match(job_id):
        raise TaskCompilerError(f"job_id {job_id!r} is not a valid id")
    if not isinstance(project_id, str) or not _ID_RE.match(project_id):
        raise TaskCompilerError(
            f"project_id {project_id!r} is not a valid id")
    if not isinstance(bundle, dict):
        raise TaskCompilerError("bundle is not an object")
    bundle_errors = schema_errors(
        "script-to-performance",
        bundle.get("script_to_performance"), "script_to_performance") \
        if bundle.get("script_to_performance") is not None else \
        ["bundle has no script_to_performance record"]
    if bundle_errors:
        raise TaskCompilerError(bundle_errors)
    commercial_use = job.get("commercial_use") is True
    stills_first = job.get("stills_first") is True
    providers = (copy.deepcopy(providers) if providers is not None
                 else load_provider_registry(providers_path))
    for provider in providers:
        errors = validate_provider_record(provider)
        if errors:
            raise TaskCompilerError(errors)

    job = copy.deepcopy(job)
    bundle = copy.deepcopy(bundle)
    analysis = copy.deepcopy(analysis) if analysis is not None else None
    proposals = {p.get("proposal_id"): p
                 for p in (proposals or []) if isinstance(p, dict)}

    scene_plan = bundle.get("scene_plan") or {}
    shot_plan = bundle.get("shot_plan") or {}
    perf_plan = bundle.get("performance_plan") or {}
    s2p = bundle.get("script_to_performance") or {}
    scenes = _as_list(scene_plan.get("scenes"))
    shots = _as_list(shot_plan.get("shots"))
    lines = _as_list(perf_plan.get("lines"))
    bindings = _as_list(s2p.get("character_voice_bindings"))
    singular_binding = s2p.get("character_voice_binding")
    if isinstance(singular_binding, dict):
        bindings = bindings + [singular_binding]
    voice_by_character = {}
    for binding in bindings:
        if isinstance(binding, dict) and binding.get("character_id"):
            voice_by_character[binding["character_id"]] = binding
    voice_kinds = voice_kinds or {}

    packets: list[dict] = []
    unmatched: list[dict] = []
    seq = [0]

    def next_ids(prefix):
        seq[0] += 1
        n = seq[0]
        return f"pkt-{prefix}-{n:03d}", f"t-{prefix}-{n:03d}"

    def add(packet, miss):
        packets.append(packet)
        if miss is not None:
            unmatched.append(miss)

    # -- 1. Character design + reference-sheet packets (Task C). --
    if analysis is not None:
        for resolution in sorted(
                _as_list(analysis.get("character_resolutions")),
                key=lambda r: r.get("character_ref", "")):
            if not isinstance(resolution, dict):
                continue
            if resolution.get("resolution") != "task-local-proposal":
                continue
            proposal_id = resolution.get("proposal_id")
            proposal = proposals.get(proposal_id)
            if proposal is None:
                raise TaskCompilerError(
                    "analysis references task-local proposal "
                    f"{proposal_id!r} but no proposal record was "
                    "supplied")
            proposal_errors = schema_errors(
                "character-design-proposal", proposal,
                "character_design_proposal")
            if proposal_errors:
                raise TaskCompilerError(proposal_errors)
            if proposal.get("status") == "rejected":
                raise TaskCompilerError(
                    f"proposal {proposal_id!r} is rejected and cannot "
                    "be compiled into tasks")
            packet_id, task_id = next_ids("character-design")
            packet, miss = _build_packet(
                packet_id=packet_id, task_id=task_id, job_id=job_id,
                project_id=project_id, task_type="character-design",
                scene_id=None, shot_id=None,
                instruction=(
                    f"Prepare the task-local character design for "
                    f"{proposal.get('character_ref')!r} "
                    f"(proposal {proposal_id}): "
                    f"{proposal.get('design_brief')}. This design is "
                    "for this job only and must never be registered "
                    "permanently without explicit authorisation."),
                inputs=[{"input_ref": proposal_id, "kind": "plan",
                         "required": True}],
                requirements=["design-brief"],
                restrictions=[
                    "task-local proposal only: never register "
                    "permanently without explicit authorisation",
                    "approved identities always win over proposals",
                ],
                expected={
                    "description": "Approved-for-job character design "
                                   "brief with fixed structure",
                    "format": "json",
                    "acceptance_checks": [
                        "design brief matches the proposal",
                        "no permanent registration was created",
                    ],
                },
                qc_conditions=[
                    "Critical: design must not reuse an approved "
                    "character's identity",
                ],
                provenance={
                    "source": proposal.get(
                        "provenance", "INFERRED_FOR_PRODUCTION"),
                    "note": "task-local proposal from the production "
                            "analysis",
                },
                authorization_action="use_in_production",
                providers=providers, commercial_use=commercial_use,
                match_provider=False)
            add(packet, miss)
            if proposal.get("status") == "approved-for-job":
                packet_id, task_id = next_ids("reference-sheet")
                refs = ", ".join(
                    proposal.get("approved_reference_ids") or []) \
                    or "no approved references yet"
                packet, miss = _build_packet(
                    packet_id=packet_id, task_id=task_id, job_id=job_id,
                    project_id=project_id, task_type="reference-sheet",
                    scene_id=None, shot_id=None,
                    instruction=(
                        "Prepare the reference sheet for "
                        f"{proposal.get('character_ref')!r} "
                        f"(proposal {proposal_id}): front and side "
                        "references, turnaround and expression sheet. "
                        f"Approved references: {refs}."),
                    inputs=[{"input_ref": proposal_id, "kind": "plan",
                             "required": True}],
                    requirements=["generate-image",
                                  "reference-image",
                                  "character-reference"],
                    restrictions=[
                        "face, body proportions and clothing must "
                        "match the approved design brief",
                        "no face drift without a story-driven variation",
                    ],
                    expected={
                        "description": "Reference sheet: front, side, "
                                       "turnaround, expression sheet",
                        "format": "png",
                        "acceptance_checks": [
                            "references match the approved design brief",
                            "turnaround covers front and side",
                        ],
                    },
                    qc_conditions=[
                        "Critical: reference face must match the "
                        "approved design",
                    ],
                    provenance={
                        "source": "INFERRED_FOR_PRODUCTION",
                        "note": "reference preparation for an "
                                "approved-for-job proposal",
                    },
                    authorization_action="use_in_production",
                    providers=providers, commercial_use=commercial_use)
                add(packet, miss)

    # -- 2. Environment reference packets, one per scene. --
    analysis_scenes = {}
    if analysis is not None:
        for entry in _as_list(analysis.get("scenes")):
            if isinstance(entry, dict) and entry.get("scene_id"):
                analysis_scenes[entry["scene_id"]] = entry
    for scene in sorted(scenes, key=lambda s: s.get("scene_id", "")):
        if not isinstance(scene, dict) or not scene.get("scene_id"):
            continue
        scene_id = scene["scene_id"]
        location = (analysis_scenes.get(scene_id) or {}).get(
            "location_brief") or scene.get("location_id") \
            or "location as described in the scene plan"
        packet_id, task_id = next_ids("environment-reference")
        packet, miss = _build_packet(
            packet_id=packet_id, task_id=task_id, job_id=job_id,
            project_id=project_id, task_type="environment-reference",
            scene_id=scene_id, shot_id=None,
            instruction=(
                f"Prepare the environment reference for scene "
                f"{scene_id}: {location}. The background supports the "
                "main story action; it must not be unnecessarily busy."),
            inputs=[{"input_ref": scene_id, "kind": "plan",
                     "required": True}],
            requirements=["generate-image"],
            restrictions=[
                "background supports the action, never overwhelms it",
                "spatial continuity with neighbouring scenes",
            ],
            expected={
                "description": "Environment reference for the scene",
                "format": "png",
                "acceptance_checks": [
                    "environment matches the location brief",
                    "foreground, midground and background read clearly",
                ],
            },
            qc_conditions=[
                "Major: environment must not contradict the location "
                "brief",
            ],
            provenance={
                "source": (analysis_scenes.get(scene_id) or {}).get(
                    "provenance", "INFERRED_FOR_PRODUCTION"),
                "note": "environment intelligence for the scene",
            },
            authorization_action="use_in_production",
            providers=providers, commercial_use=commercial_use)
        add(packet, miss)

    # -- 3. Image packets (stills-first jobs only) + video packets. --
    shot_direction = {}
    if analysis is not None:
        for entry in _as_list(analysis.get("shot_direction")):
            if isinstance(entry, dict) and entry.get("shot_id"):
                shot_direction[entry["shot_id"]] = entry
    image_task_by_shot = {}
    for shot in sorted(shots, key=lambda s: s.get("shot_id", "")):
        if not isinstance(shot, dict) or not shot.get("shot_id"):
            continue
        shot_id = shot["shot_id"]
        scene_id = shot.get("scene_id")
        direction = shot_direction.get(shot_id) or {}
        framing = shot.get("framing") or shot.get("shot_size") or ""
        if stills_first:
            packet_id, task_id = next_ids("image-generation")
            packet, miss = _build_packet(
                packet_id=packet_id, task_id=task_id, job_id=job_id,
                project_id=project_id, task_type="image-generation",
                scene_id=scene_id, shot_id=shot_id,
                instruction=(
                    f"Generate the approved starting still for shot "
                    f"{shot_id} (scene {scene_id}): "
                    f"{shot.get('action') or shot.get('framing') or ''} "
                    f"framing {framing}; "
                    f"lighting {shot.get('lighting') or 'as directed'}; "
                    f"camera {shot.get('camera_angle') or ''} "
                    f"{shot.get('camera_movement') or ''}."),
                inputs=[{"input_ref": shot_id, "kind": "plan",
                         "required": True}],
                requirements=["generate-image", "reference-image",
                              "character-reference"],
                restrictions=[
                    "character identity fixed: face, structure, hands, "
                    "feet must match the approved reference",
                    "no camera or rendering control may be claimed "
                    "unless a provider capability record verifies it",
                ],
                expected={
                    "description": "Approved starting still for the shot",
                    "format": "png",
                    "acceptance_checks": [
                        "characters match their approved references",
                        "composition and lighting match the shot plan",
                    ],
                },
                qc_conditions=[
                    "Critical: face must match the approved reference",
                    "Major: lighting must match the shot plan",
                ],
                provenance={
                    "source": direction.get(
                        "provenance", "INFERRED_FOR_PRODUCTION"),
                    "note": "starting still for the shot",
                },
                authorization_action="use_in_production",
                providers=providers, commercial_use=commercial_use)
            add(packet, miss)
            image_task_by_shot[shot_id] = task_id
        packet_id, task_id = next_ids("video-generation")
        video_inputs = [{"input_ref": shot_id, "kind": "plan",
                         "required": True}]
        if stills_first:
            video_inputs.append({
                "input_ref": image_task_by_shot[shot_id],
                "kind": "prior-output", "required": True})
        else:
            video_inputs.append({
                "input_ref": "approved-starting-reference",
                "kind": "approved-asset", "required": False})
        duration = shot.get("duration_seconds")
        packet, miss = _build_packet(
            packet_id=packet_id, task_id=task_id, job_id=job_id,
            project_id=project_id, task_type="video-generation",
            scene_id=scene_id, shot_id=shot_id,
            instruction=(
                f"Generate the video for shot {shot_id} "
                f"(scene {scene_id}): "
                f"{shot.get('action') or ''} "
                f"framing {framing}; angle "
                f"{shot.get('camera_angle') or ''}; movement "
                f"{shot.get('camera_movement') or ''}; focus "
                f"{shot.get('focus_target') or ''}; depth of field "
                f"{shot.get('depth_of_field') or ''}"
                + (f"; duration {duration} seconds"
                   if isinstance(duration, (int, float)) else "")
                + ". Physical action must be realistic: weight, "
                  "balance, contact and continuity as directed."),
            inputs=video_inputs,
            requirements=["generate-video", "reference-image",
                          "character-reference"],
            restrictions=[
                "character identity fixed: face, structure, hands, "
                "feet must match the approved reference",
                "dialogue, if any, is spoken exactly as scripted",
                "no camera or rendering control may be claimed unless "
                "a provider capability record verifies it",
            ],
            expected={
                "description": "Video for the shot",
                "format": "mp4",
                "acceptance_checks": [
                    "duration and framing match the shot plan",
                    "characters match their approved references",
                    "motion is physically believable",
                ],
            },
            qc_conditions=[
                "Critical: face must match the approved reference",
                "Major: motion must be physically believable",
            ],
            provenance={
                "source": direction.get(
                    "provenance", "INFERRED_FOR_PRODUCTION"),
                "note": "video generation for the shot",
            },
            authorization_action="use_in_production",
            providers=providers, commercial_use=commercial_use)
        add(packet, miss)

    # -- 4. Voice packets, one per speaking line (exact dialogue). --
    for line in sorted(lines, key=lambda ln: ln.get("line_id", "")):
        if not isinstance(line, dict) or not line.get("line_id"):
            continue
        if (line.get("speaking_state") or "speaking") == "listening":
            continue
        if not line.get("dialogue"):
            continue
        line_id = line["line_id"]
        character_id = line.get("character_id")
        binding = voice_by_character.get(character_id) or {}
        voice_profile_id = (line.get("voice_profile_id")
                            or binding.get("voice_profile_id"))
        if not voice_profile_id:
            raise TaskCompilerError(
                f"speaking line {line_id!r} has no voice profile id "
                "(character_voice_bindings must name one)")
        kind = voice_kinds.get(voice_profile_id, "existing-profile")
        if kind not in ("existing-profile", "user-recording",
                        "ai-generated", "clone"):
            raise TaskCompilerError(
                f"voice profile {voice_profile_id!r} has unknown kind "
                f"{kind!r}")
        if kind == "clone" and voice_consent is not True:
            raise TaskCompilerError(
                "voice cloning for profile "
                f"{voice_profile_id!r} needs explicit voice consent "
                "(voice_consent must be the actual boolean True)")
        text = _final_dialogue_text(bundle, line)
        if not text:
            raise TaskCompilerError(
                f"speaking line {line_id!r} has no dialogue text")
        voice = line.get("voice") or {}
        delivery = (line.get("delivery")
                    or binding.get("delivery") or "")
        emotion = (line.get("emotion") or binding.get("emotion") or "")
        language = line.get("language") or "unspecified"
        packet_id, task_id = next_ids("voice-generation")
        packet, miss = _build_packet(
            packet_id=packet_id, task_id=task_id, job_id=job_id,
            project_id=project_id, task_type="voice-generation",
            scene_id=None, shot_id=binding.get("shot_id"),
            instruction=(
                f"Generate the voice for line {line_id} "
                f"(character {character_id}, voice profile "
                f"{voice_profile_id}, language {language}): speak "
                f"exactly: {text!r}. Delivery: {delivery}. Emotion: "
                f"{emotion}. Pace: {voice.get('pace') or ''}. Pauses: "
                f"{voice.get('pauses') or ''}."),
            inputs=[
                {"input_ref": line_id, "kind": "script",
                 "required": True},
                {"input_ref": voice_profile_id, "kind": "profile",
                 "required": True},
            ],
            requirements=["generate-speech"]
            + (["clone-voice"] if kind == "clone" else []),
            restrictions=[
                "dialogue verbatim: speak exactly the scripted text",
                "voice identity fixed: tags, seed and reference audio "
                "must match the approved voice profile",
                "commercial jobs must never use a noncommercial voice "
                "route",
            ],
            expected={
                "description": "Spoken dialogue audio for the line",
                "format": "wav",
                "acceptance_checks": [
                    "spoken text is byte-identical to the scripted text",
                    "voice matches the approved voice profile",
                    "lip-sync timing matches the dialogue",
                ],
            },
            qc_conditions=[
                "Critical: spoken text must match the script exactly",
                "Major: voice must match the approved profile",
            ],
            provenance={
                "source": "EXPLICIT_FROM_USER",
                "note": "dialogue is the user's script, verbatim",
            },
            authorization_action="use_in_production",
            providers=providers, commercial_use=commercial_use,
            needs_clone=(kind == "clone"))
        add(packet, miss)

    # -- 5. Sound packets from the analysis, else the bundle plan. --
    cues = []
    if analysis is not None:
        for cue in _as_list(analysis.get("sound_direction")):
            if isinstance(cue, dict) and cue.get("cue_type"):
                cues.append((cue.get("scene_id"),
                             cue.get("cue_type"),
                             cue.get("intent") or "",
                             cue.get("provenance",
                                     "INFERRED_FOR_PRODUCTION")))
    if not cues:
        audio_plan = s2p.get("audio_plan") or {}
        for kind in ("ambience", "music", "sfx"):
            for item in _as_list(audio_plan.get(kind)):
                if isinstance(item, dict) and item.get("cue"):
                    cues.append((None, kind, _cue_text(item),
                                 "INFERRED_FOR_PRODUCTION"))
    for scene_id, cue_type, intent, provenance in sorted(
            cues, key=lambda c: (c[0] or "", c[1], c[2])):
        if cue_type == "intentional-silence":
            continue
        packet_id, task_id = next_ids("sound-generation")
        packet, miss = _build_packet(
            packet_id=packet_id, task_id=task_id, job_id=job_id,
            project_id=project_id, task_type="sound-generation",
            scene_id=scene_id, shot_id=None,
            instruction=(
                f"Generate the {cue_type} sound cue"
                + (f" for scene {scene_id}" if scene_id else "")
                + f": {intent}. Sync with the visible action; mix "
                  "dialogue-first."),
            inputs=[{"input_ref": job_id, "kind": "plan",
                     "required": True}],
            requirements=["generate-sound"],
            restrictions=[
                "dialogue-first mixing: never drown the dialogue",
                "intentional silence is a creative decision, never a "
                "missing-audio defect",
            ],
            expected={
                "description": f"{cue_type} cue audio",
                "format": "wav",
                "acceptance_checks": [
                    "cue matches its intent",
                    "syncs with the visible action",
                ],
            },
            qc_conditions=[
                "Major: cue must sync with the visible action",
            ],
            provenance={"source": provenance,
                        "note": "sound direction for the scene"},
            authorization_action="use_in_production",
            providers=providers, commercial_use=commercial_use)
        add(packet, miss)

    # -- 6. Editing + finishing packet (one per job). --
    editing = s2p.get("editing_plan") or {}
    packet_id, task_id = next_ids("editing-finishing")
    packet, miss = _build_packet(
        packet_id=packet_id, task_id=task_id, job_id=job_id,
        project_id=project_id, task_type="editing-finishing",
        scene_id=None, shot_id=None,
        instruction=(
            "Assemble the final timeline in shot order with the "
            "editing plan: reaction holds "
            f"{len(_as_list(editing.get('reaction_holds')))}; rhythm "
            f"{editing.get('rhythm') or 'as directed'}. Sync audio to "
            "picture, apply colour finishing, export per the delivery "
            "profile."),
        inputs=[{"input_ref": job_id, "kind": "plan", "required": True}],
        requirements=["assemble-timeline"],
        restrictions=[
            "shot order is the shot plan order",
            "never regenerate an approved neighbouring shot to fix "
            "one defective shot",
        ],
        expected={
            "description": "Finished timeline and export",
            "format": "mp4",
            "acceptance_checks": [
                "shots in shot-plan order",
                "audio synced to picture",
                "export matches the delivery profile",
            ],
        },
        qc_conditions=[
            "Critical: shot order must match the shot plan",
            "Major: audio must be synced to picture",
        ],
        provenance={"source": "FROM_APPROVED_PROJECT_CANON",
                    "note": "editing plan from the validated bundle"},
        authorization_action="use_in_production",
        providers=providers, commercial_use=commercial_use)
    add(packet, miss)

    # -- 7. QC review packet (one per job). --
    packet_id, task_id = next_ids("qc-review")
    packet, miss = _build_packet(
        packet_id=packet_id, task_id=task_id, job_id=job_id,
        project_id=project_id, task_type="qc-review",
        scene_id=None, shot_id=None,
        instruction=(
            "Run QC on the assembled output: file existence, "
            "resolution, duration, frame rate, audio presence, "
            "audio/video sync where measurable, file and export "
            "integrity, plus human review for semantic defects. "
            "Grade defects Critical / Major / Minor / Polish."),
        inputs=[{"input_ref": job_id, "kind": "plan",
                 "required": True}],
        requirements=["probe-media"],
        restrictions=[
            "a model claiming a scene looks good is not sufficient "
            "evidence every frame is correct",
            "deterministic checks first, human review for semantics",
        ],
        expected={
            "description": "QC report with severity-graded defects",
            "format": "json",
            "acceptance_checks": [
                "every deterministic check ran and is recorded",
                "defects carry severity and shot ids",
            ],
        },
        qc_conditions=[
            "Critical: no Critical defect may ship unwaived",
        ],
        provenance={"source": "FROM_APPROVED_PROJECT_CANON",
                    "note": "QC rules from the Addendum-01 systems"},
        authorization_action="use_in_production",
        providers=providers, commercial_use=commercial_use)
    add(packet, miss)

    package = {
        "package_id": f"pkg-{job_id}",
        "job_id": job_id,
        "project_id": project_id,
        "packets": packets,
        "unmatched_tasks": unmatched,
    }
    package["package_hash"] = sha256_hex(canonical_json(package))
    errors = validate_task_package(package)
    if errors:
        raise TaskCompilerError(errors)
    return package


def compile_regeneration_packets(session, job, qc_report, providers=None,
                                 *, providers_path=None) -> dict:
    """Compile correction task packets for a QC report's failed shots.

    Only defects that need repair get packets: Critical and Major
    always; Minor only when the defect carries
    ``repair_authorised: true``; Polish never (it is finishing
    polish, recorded in the skipped list, not a regeneration task).
    Each packet reuses the failed task's original type for provider
    matching, so a failed video shot is re-matched as video work —
    never silently re-typed. Approved neighbouring shots are never
    touched: packets are built only for the shots the report names.

    The job must already carry a compiled task package (see
    :func:`compile_task_package`); the correction round is taken
    from ``job['correction_round']`` so repeated corrections get
    distinct deterministic package ids.

    Raises TaskCompilerError on any failure; returns nothing partial.
    """
    if not local_session.is_active_session(session):
        reasons = local_session.validate_session(session)
        raise TaskCompilerError(
            "no active session for regeneration compilation"
            + (f": {'; '.join(reasons)}" if reasons else ""))
    if not isinstance(job, dict):
        raise TaskCompilerError("job is not an object")
    job_id = job.get("job_id")
    project_id = job.get("project_id")
    if not isinstance(job_id, str) or not _ID_RE.match(job_id):
        raise TaskCompilerError(f"job_id {job_id!r} is not a valid id")
    package = job.get("task_package")
    if not isinstance(package, dict):
        raise TaskCompilerError(
            "job has no compiled task package to correct against")
    package_errors = validate_task_package(package)
    if package_errors:
        raise TaskCompilerError(package_errors)
    if not isinstance(qc_report, dict):
        raise TaskCompilerError("qc_report is not an object")
    if qc_report.get("job_id") != job_id:
        raise TaskCompilerError(
            "qc_report.job_id "
            f"{qc_report.get('job_id')!r} does not match job {job_id!r}")
    defects = qc_report.get("defects")
    if not isinstance(defects, list) or not defects:
        raise TaskCompilerError(
            "qc_report.defects must be a non-empty array")
    providers = (copy.deepcopy(providers) if providers is not None
                 else load_provider_registry(providers_path))
    for provider in providers:
        errors = validate_provider_record(provider)
        if errors:
            raise TaskCompilerError(errors)

    job = copy.deepcopy(job)
    qc_report = copy.deepcopy(qc_report)
    packets_by_id = {}
    packets_by_shot: dict[str, list] = {}
    for packet in package.get("packets") or []:
        if not isinstance(packet, dict):
            continue
        packets_by_id[packet.get("task_id")] = packet
        if packet.get("shot_id"):
            packets_by_shot.setdefault(packet["shot_id"], []).append(
                packet)
    commercial_use = job.get("commercial_use") is True
    round_no = int(job.get("correction_round") or 0) + 1
    packets: list[dict] = []
    unmatched: list[dict] = []
    skipped: list[dict] = []
    seq = [0]

    for defect in defects:
        if not isinstance(defect, dict):
            raise TaskCompilerError("qc_report defect is not an object")
        severity = defect.get("severity")
        if severity not in ("Critical", "Major", "Minor", "Polish"):
            raise TaskCompilerError(
                f"defect {defect.get('defect_id')!r} has unknown "
                f"severity {severity!r}")
        defect_id = defect.get("defect_id") or "defect-unknown"
        if severity == "Polish":
            skipped.append({"defect_id": defect_id,
                            "reason": "Polish defects are finishing "
                                      "polish, not regeneration tasks"})
            continue
        if severity == "Minor" \
                and defect.get("repair_authorised") is not True:
            skipped.append({"defect_id": defect_id,
                            "reason": "Minor defect without repair "
                                      "authorisation"})
            continue
        task_id = defect.get("task_id")
        shot_id = defect.get("shot_id")
        original = packets_by_id.get(task_id) if task_id else None
        if original is None and shot_id:
            candidates = packets_by_shot.get(shot_id) or []
            video = [p for p in candidates
                     if p.get("task_type") == "video-generation"]
            original = (video or candidates or [None])[0]
        if original is None:
            raise TaskCompilerError(
                f"defect {defect_id!r} names no known task or shot "
                f"(task_id={task_id!r}, shot_id={shot_id!r})")
        original_type = original.get("task_type")
        if original_type not in TASK_PROVIDER_REQUIREMENTS:
            raise TaskCompilerError(
                f"defect {defect_id!r} references task type "
                f"{original_type!r}, which cannot be regenerated")
        seq[0] += 1
        n = seq[0]
        packet_id, regen_task_id = (f"pkt-regen-{round_no:02d}-{n:03d}",
                                    f"t-regen-{round_no:02d}-{n:03d}")
        instruction = (
            f"Regenerate the output for defect {defect_id} "
            f"(severity {severity}, shot {shot_id or 'unknown'}): "
            f"{defect.get('description') or ''} Correct the "
            "production instruction that caused it, regenerate only "
            "this shot's output, and revalidate continuity. "
            "Neighbouring approved shots must not change.")
        packet, miss = _build_packet(
            packet_id=packet_id, task_id=regen_task_id, job_id=job_id,
            project_id=project_id, task_type="regeneration",
            scene_id=original.get("scene_id"),
            shot_id=original.get("shot_id"),
            instruction=instruction,
            inputs=[{"input_ref": original.get("task_id"),
                     "kind": "prior-output", "required": True}],
            requirements=list(
                TASK_PROVIDER_REQUIREMENTS[original_type]["operations"]),
            restrictions=list(original.get("restrictions") or []) + [
                "regenerate only the defective shot's output",
                "preserve every approved neighbouring shot",
            ],
            expected={
                "description": "Corrected output for the defective shot",
                "format": original.get("expected_output", {}).get(
                    "format", "mp4"),
                "acceptance_checks": [
                    "the reported defect is fixed",
                    "continuity with neighbouring shots holds",
                ],
            },
            qc_conditions=[
                f"{severity}: the reported defect must be fixed on "
                "re-QC",
            ],
            provenance={
                "source": "FROM_APPROVED_PROJECT_CANON",
                "note": f"QC correction for defect {defect_id}",
            },
            authorization_action="use_in_production",
            providers=providers, commercial_use=commercial_use,
            match_task_type=original_type)
        packets.append(packet)
        if miss is not None:
            unmatched.append(miss)

    package_out = {
        "package_id": f"pkg-{job_id}-regen-{round_no:02d}",
        "job_id": job_id,
        "project_id": project_id,
        "packets": packets,
        "unmatched_tasks": unmatched,
        "skipped_defects": skipped,
    }
    package_out["package_hash"] = sha256_hex(canonical_json(package_out))
    errors = validate_task_package(package_out)
    if errors:
        raise TaskCompilerError(errors)
    return package_out
