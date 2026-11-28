"""Consistency Frame P1 — Phase H delivery package and manifest
(CF-WO-P1-006).

Builds the delivery package for a QC-passed vertical production:
the final MP4 (copied, never moved), every project source file,
the QC reports, a delivery manifest, and a SHA256SUMS file —
then verifies the package independently.

Refusals (fail-closed, no override):

- the QC decision is not DELIVERY_READY — unless this is a
  review package (``review_package=True``) and the decision is
  BLOCKED only because editorial approval is still missing
  (technical QC passed and audio QC carries no critical
  finding). A review package is the artifact a human reviewer
  watches before approving; its manifest records the true
  decision (``BLOCKED``) and the blocking reasons, and never
  claims DELIVERY_READY. A failed or incomplete technical/audio
  QC still blocks a review package;
- any commercial-delivery blocker on any source asset, when the
  project delivery is commercial;
- any listed source file is missing;
- the render timestamp or voice source is missing, invalid, or
  not one of the known values;
- the copied MP4 does not re-probe identically to the source;
- the probed MP4 does not match the delivery contract (MP4
  container, h264/aac, 9:16, 30/1).

All paths inside the package are relative. The manifest lists
every file in the package except itself (a manifest cannot carry
its own hash); SHA256SUMS covers every file including the
manifest. Standard library plus ffmpeg/ffprobe only.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone

from .production_assets import (
    check_commercial_delivery, hash_file, probe_media_file)
from .media_execution import is_safe_relative_path
from .timeline_delivery import aspect_ratio_for_dimensions

DELIVERY_SCHEMA_VERSION = "2.5"
DELIVERY_CONTAINER = "mp4"
DELIVERY_ASPECT_RATIO = "9:16"
DELIVERY_FRAME_RATE_RATIONAL = "30/1"
DELIVERY_FRAME_RATE = 30
DELIVERY_VIDEO_CODEC = "h264"
DELIVERY_AUDIO_CODEC = "aac"
DELIVERY_RENDER_PATH = "ffmpeg"
DELIVERY_QC_STATUS = "DELIVERY_READY"
VOICE_SOURCES = ("voicestudio-omnivoice", "synthesized-tone")
PROBE_DURATION_TOLERANCE_SECONDS = 0.05
VERIFY_DURATION_TOLERANCE_SECONDS = 0.05


class DeliveryError(ValueError):
    """Delivery error carrying a list of structured messages."""

    def __init__(self, errors):
        if isinstance(errors, str):
            errors = [errors]
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


def _is_commercial(project):
    """True when the project delivery is commercial."""
    if not isinstance(project, dict):
        return False
    if project.get("commercial_delivery") is True:
        return True
    delivery = project.get("delivery")
    if isinstance(delivery, dict):
        if delivery.get("commercial") is True:
            return True
        if delivery.get("type") == "commercial":
            return True
    return False


def _validate_render_timestamp(value):
    """ISO-8601 UTC timestamp string, or a refusal message."""
    if not isinstance(value, str) or not value:
        return "render_timestamp is missing: the render time must " \
               "be passed in, it is never invented"
    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00"))
    except ValueError:
        return f"render_timestamp {value!r} is not an ISO-8601 " \
               "timestamp"
    if parsed.tzinfo is None:
        return f"render_timestamp {value!r} carries no timezone: " \
               "an ISO-8601 UTC timestamp is required"
    if parsed.utcoffset() != timezone.utc.utcoffset(None):
        return f"render_timestamp {value!r} is not UTC"
    return None


def _qc_decision_value(qc_reports):
    """The QC decision string inside a qc_reports dict, or None.

    Accepts ``{"decision": "DELIVERY_READY"}`` and
    ``{"decision": {"decision": "DELIVERY_READY", ...}}`` (the
    shape :func:`runtime.production_qc.qc_decision` returns).
    """
    if not isinstance(qc_reports, dict):
        return None
    decision = qc_reports.get("decision")
    if isinstance(decision, dict):
        return decision.get("decision")
    return decision


def _assets_list(assets):
    """Asset records as a list, from a list or a registry dict."""
    if isinstance(assets, dict):
        return list(assets.values())
    if isinstance(assets, list):
        return list(assets)
    raise DeliveryError("assets must be a list of asset records or "
                        "a registry dict")


def _probe_matches(source_probe, copy_probe):
    """Why a dist MP4 probe differs from its source probe, or None."""
    for field in ("width", "height", "frame_rate_rational",
                  "video_codec", "audio_codec", "format_name"):
        if source_probe.get(field) != copy_probe.get(field):
            return (f"dist MP4 {field} "
                    f"{copy_probe.get(field)!r} does not match the "
                    f"source probe {source_probe.get(field)!r}")
    source_duration = source_probe.get("duration_seconds")
    copy_duration = copy_probe.get("duration_seconds")
    if source_duration is not None and copy_duration is not None \
            and abs(float(source_duration) - float(copy_duration)) \
            > PROBE_DURATION_TOLERANCE_SECONDS:
        return (f"dist MP4 duration {copy_duration}s does not match "
                f"the source probe {source_duration}s")
    return None


def _write_json(path, payload):
    """Write a JSON file deterministically (sorted keys, indent 2)."""
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _collect_files(dist_dir):
    """[{path, sha256, size_bytes}] for every file under dist_dir.

    Paths are relative to dist_dir, POSIX-style, sorted. Used for
    the manifest file list (the manifest itself is excluded by
    the caller, before it is written) and for SHA256SUMS.
    """
    entries = []
    for root, _dirs, names in os.walk(dist_dir):
        for name in names:
            real = os.path.join(root, name)
            rel = os.path.relpath(real, dist_dir).replace(os.sep, "/")
            sha, size = hash_file(real)
            entries.append({"path": rel, "sha256": sha,
                            "size_bytes": size})
    entries.sort(key=lambda entry: entry["path"])
    return entries


def write_checksums(dist_dir) -> str:
    """Write SHA256SUMS for every file in a delivery directory.

    One line per file — ``"<sha256>  <relative path>"``, sorted
    by relative path — covering every file present except
    SHA256SUMS itself. The delivery manifest IS included, so
    callers write the manifest first and SHA256SUMS last.
    Returns the SHA256SUMS path.
    """
    if not os.path.isdir(dist_dir):
        raise DeliveryError(
            f"delivery directory {dist_dir!r} is not a directory")
    sums_path = os.path.join(dist_dir, "SHA256SUMS")
    entries = [e for e in _collect_files(dist_dir)
               if e["path"] != "SHA256SUMS"]
    lines = [f"{entry['sha256']}  {entry['path']}\n"
             for entry in entries]
    with open(sums_path, "w", encoding="utf-8") as handle:
        handle.writelines(lines)
    return sums_path


def _decision_reasons(qc_reports):
    """The QC decision's reasons list, or [] when absent."""
    if not isinstance(qc_reports, dict):
        return []
    decision = qc_reports.get("decision")
    if isinstance(decision, dict):
        reasons = decision.get("reasons")
        return list(reasons) if isinstance(reasons, list) else []
    return []


def _editorial_only_block(qc_reports) -> bool:
    """True when the ONLY QC block is a missing human approval.

    The decision must be BLOCKED with at least one reason, and
    every reason must be about editorial approval (the wording
    :func:`runtime.production_qc.qc_decision` uses). A technical
    failure or an audio critical finding is never editorial-only.
    """
    decision = _qc_decision_value(qc_reports)
    if decision != "BLOCKED":
        return False
    reasons = _decision_reasons(qc_reports)
    return bool(reasons) and all(
        isinstance(reason, str)
        and reason.startswith("editorial approval")
        for reason in reasons)


def build_delivery_package(*, project, timeline, assets,
                           voice_mapping, sound_plan,
                           execution_summary, qc_reports, source_files,
                           dist_dir, final_mp4_path,
                           render_timestamp=None, voice_source=None,
                           review_package=False,
                           ffmpeg="ffmpeg", ffprobe="ffprobe"):
    """Build the delivery package for a QC-passed production.

    ``project`` / ``timeline`` are the validated project and
    timeline records; ``assets`` the asset records (list or
    registry); ``voice_mapping``, ``sound_plan`` and
    ``execution_summary`` the records written as JSON;
    ``qc_reports`` a dict carrying the QC decision (see
    :func:`runtime.production_qc.qc_decision`) plus the
    ``technical`` / ``visual`` / ``audio`` report dicts to write;
    ``source_files`` a dict of ``{relative name: absolute path}``
    for the project source files to copy; ``final_mp4_path`` the
    rendered MP4 (copied, never moved); ``render_timestamp`` the
    ISO-8601 UTC render time (passed in, never invented);
    ``voice_source`` one of ``"voicestudio-omnivoice"`` or
    ``"synthesized-tone"``; ``review_package`` builds a review
    package (see the module docstring) instead of a final
    delivery — the manifest then records the true BLOCKED
    decision and the blocking reasons, and never DELIVERY_READY.

    Creates ``dist_dir``; copies the MP4 and every listed
    artifact; verifies the MP4 copy by re-probing it and
    refusing on any mismatch with the source probe; writes the
    delivery manifest and SHA256SUMS; returns the manifest dict.

    Refuses when the QC decision is not DELIVERY_READY, when
    any source file is missing, when a commercial delivery is
    blocked by an asset license, when the timestamp or voice
    source is missing or invalid, or when the MP4 does not match
    the delivery contract.
    """
    if not isinstance(project, dict):
        raise DeliveryError("project must be an object")
    if not isinstance(timeline, dict):
        raise DeliveryError("timeline must be an object")
    project_id = project.get("project_id")
    if not isinstance(project_id, str) or not project_id:
        raise DeliveryError("project.project_id is missing or not "
                            "a string")
    timeline_id = timeline.get("id")
    if not isinstance(timeline_id, str) or not timeline_id:
        raise DeliveryError("timeline.id is missing or not a string")
    if timeline.get("project_id") is not None \
            and timeline["project_id"] != project_id:
        raise DeliveryError(
            f"timeline project_id {timeline['project_id']!r} does "
            f"not match project_id {project_id!r}")
    decision = _qc_decision_value(qc_reports)
    if decision != DELIVERY_QC_STATUS:
        if review_package and _editorial_only_block(qc_reports):
            # Review package: technical QC passed, audio QC has no
            # critical finding, and the only block is the missing
            # human editorial approval. The manifest records the
            # true BLOCKED decision (below) — it never claims
            # DELIVERY_READY.
            pass
        else:
            raise DeliveryError(
                "delivery refused: the QC decision is not "
                f"DELIVERY_READY (got {decision!r}) — a failed or "
                "incomplete QC blocks delivery and there is no "
                "override")
    timestamp_error = _validate_render_timestamp(render_timestamp)
    if timestamp_error is not None:
        raise DeliveryError(timestamp_error)
    if voice_source not in VOICE_SOURCES:
        raise DeliveryError(
            f"voice_source {voice_source!r} is not a known voice "
            f"source (expected one of {', '.join(VOICE_SOURCES)})")
    if not isinstance(final_mp4_path, str) \
            or not os.path.isfile(final_mp4_path):
        raise DeliveryError(
            f"final MP4 {final_mp4_path!r} does not exist")
    filename = os.path.basename(final_mp4_path)
    if not filename or filename in (".", "..") \
            or not is_safe_relative_path(filename):
        raise DeliveryError(
            f"final MP4 filename {filename!r} is not a safe "
            "relative path")
    if not isinstance(source_files, dict):
        raise DeliveryError("source_files must be an object mapping "
                            "relative names to absolute paths")
    for name, source_path in source_files.items():
        if not is_safe_relative_path(name):
            raise DeliveryError(
                f"source file name {name!r} is not a safe relative "
                "path — all paths inside the package are relative")
        if not isinstance(source_path, str) \
                or not os.path.isfile(source_path):
            raise DeliveryError(
                f"source file {name!r} is missing: "
                f"{source_path!r} does not exist")
    asset_records = _assets_list(assets)
    source_assets = []
    for record in asset_records:
        if not isinstance(record, dict):
            raise DeliveryError("assets must be asset record objects")
        asset_id = record.get("asset_id")
        asset_path = record.get("path")
        sha = record.get("sha256")
        size = record.get("size_bytes")
        if not isinstance(asset_id, str) or not asset_id:
            raise DeliveryError("an asset record is missing asset_id")
        if not isinstance(asset_path, str) \
                or not is_safe_relative_path(asset_path):
            raise DeliveryError(
                f"asset {asset_id!r} path {asset_path!r} is not a "
                "safe relative path")
        if not isinstance(sha, str) or len(sha) != 64:
            raise DeliveryError(
                f"asset {asset_id!r} has no recorded SHA-256: an "
                "unverified asset cannot enter a delivery package")
        if not isinstance(size, int) or isinstance(size, bool) \
                or size < 0:
            raise DeliveryError(
                f"asset {asset_id!r} has no recorded byte size")
        source_assets.append({"asset_id": asset_id,
                              "path": asset_path, "sha256": sha,
                              "size_bytes": size})
    if _is_commercial(project):
        blockers = []
        for record in asset_records:
            blockers.extend(check_commercial_delivery(record))
        if blockers:
            raise DeliveryError(
                ["commercial delivery is blocked:"] + blockers)

    try:
        source_probe = probe_media_file(final_mp4_path,
                                        ffprobe=ffprobe)
    except Exception as exc:  # noqa: BLE001 - probe failure refuses
        raise DeliveryError(
            f"final MP4 could not be probed: {exc}") from exc
    contract_errors = []
    if "mp4" not in (source_probe.get("format_name") or "").split(","):
        contract_errors.append(
            "final MP4 container is "
            f"{source_probe.get('format_name')!r}, not mp4")
    if source_probe.get("video_codec") != DELIVERY_VIDEO_CODEC:
        contract_errors.append(
            "final MP4 video codec is "
            f"{source_probe.get('video_codec')!r}, not "
            f"{DELIVERY_VIDEO_CODEC}")
    if source_probe.get("audio_codec") != DELIVERY_AUDIO_CODEC:
        contract_errors.append(
            "final MP4 audio codec is "
            f"{source_probe.get('audio_codec')!r}, not "
            f"{DELIVERY_AUDIO_CODEC}")
    aspect = aspect_ratio_for_dimensions(source_probe.get("width"),
                                         source_probe.get("height"))
    if aspect != DELIVERY_ASPECT_RATIO:
        contract_errors.append(
            f"final MP4 aspect ratio is {aspect!r}, not "
            f"{DELIVERY_ASPECT_RATIO!r}")
    if source_probe.get("frame_rate_rational") \
            != DELIVERY_FRAME_RATE_RATIONAL:
        contract_errors.append(
            "final MP4 frame rate is "
            f"{source_probe.get('frame_rate_rational')!r}, not "
            f"{DELIVERY_FRAME_RATE_RATIONAL!r}")
    if contract_errors:
        raise DeliveryError(contract_errors)

    os.makedirs(dist_dir, exist_ok=True)
    dist_mp4 = os.path.join(dist_dir, filename)
    shutil.copyfile(final_mp4_path, dist_mp4)
    try:
        copy_probe = probe_media_file(dist_mp4, ffprobe=ffprobe)
    except Exception as exc:  # noqa: BLE001 - probe failure refuses
        raise DeliveryError(
            f"dist MP4 could not be re-probed: {exc}") from exc
    mismatch = _probe_matches(source_probe, copy_probe)
    if mismatch:
        raise DeliveryError(
            "dist MP4 verification failed: " + mismatch)
    mp4_sha, mp4_size = hash_file(dist_mp4)

    for name, source_path in sorted(source_files.items()):
        destination = os.path.join(dist_dir, name)
        parent = os.path.dirname(destination)
        if parent:
            os.makedirs(parent, exist_ok=True)
        shutil.copyfile(source_path, destination)

    _write_json(os.path.join(dist_dir, "project.json"), project)
    _write_json(os.path.join(dist_dir, "timeline-manifest.json"),
                timeline)
    _write_json(os.path.join(dist_dir, "asset-manifest.json"),
                {"schema_version": DELIVERY_SCHEMA_VERSION,
                 "project_id": project_id,
                 "assets": asset_records})
    _write_json(os.path.join(dist_dir, "voice-mapping.json"),
                voice_mapping)
    _write_json(os.path.join(dist_dir, "sound-plan.json"), sound_plan)
    _write_json(os.path.join(dist_dir, "execution-summary.json"),
                execution_summary)
    qc_report_names = []
    if isinstance(qc_reports, dict):
        for key in ("technical", "visual", "audio"):
            report = qc_reports.get(key)
            if report is not None:
                name = f"{key}-qc-report.json"
                _write_json(os.path.join(dist_dir, name), report)
                qc_report_names.append(name)
    qc_report_names.sort()

    files = [entry for entry in _collect_files(dist_dir)
             if entry["path"] not in ("delivery-manifest.json",
                                      "SHA256SUMS")]
    # The manifest and SHA256SUMS are written after this list is
    # collected, so they are never in it: a manifest cannot carry
    # its own hash, and a stale manifest or SHA256SUMS left by an
    # earlier build in the same directory must never be listed
    # with a stale hash (a re-run failed verification on exactly
    # that). SHA256SUMS still covers every file including the
    # manifest — it is written last.
    manifest = {
        "manifest_id": f"delivery-{project_id}-{mp4_sha[:12]}",
        "schema_version": DELIVERY_SCHEMA_VERSION,
        "project_id": project_id,
        "timeline_id": timeline_id,
        "filename": filename,
        "size_bytes": mp4_size,
        "sha256": mp4_sha,
        "container": DELIVERY_CONTAINER,
        "video_codec": source_probe["video_codec"],
        "audio_codec": source_probe["audio_codec"],
        "width": source_probe["width"],
        "height": source_probe["height"],
        "aspect_ratio": DELIVERY_ASPECT_RATIO,
        "frame_rate": DELIVERY_FRAME_RATE,
        "frame_rate_rational": DELIVERY_FRAME_RATE_RATIONAL,
        "duration_seconds": source_probe["duration_seconds"],
        "render_timestamp": render_timestamp,
        "render_path": DELIVERY_RENDER_PATH,
        "voice_source": voice_source,
        "source_assets": sorted(source_assets,
                                key=lambda a: a["asset_id"]),
        "qc_status": decision,
        "qc_blocked_reasons": _decision_reasons(qc_reports),
        "package_purpose": "review" if review_package else "delivery",
        "qc_reports": qc_report_names,
        # Every file in the package except this manifest itself:
        # a manifest cannot carry its own hash. SHA256SUMS covers
        # the manifest as well.
        "files": files,
    }
    _write_json(os.path.join(dist_dir, "delivery-manifest.json"),
                manifest)
    write_checksums(dist_dir)
    return manifest


def verify_delivery_package(dist_dir, *, ffmpeg="ffmpeg",
                             ffprobe="ffprobe") -> list:
    """Independent verification of a delivery package.

    Re-reads ``delivery-manifest.json``; re-hashes every listed
    file and compares size and SHA-256; re-probes the MP4 and
    compares width, height, frame rate, duration and codecs
    against the manifest; checks every listed file exists; and
    verifies SHA256SUMS (when present) against every file in
    the package, including the manifest itself. Returns a list
    of errors — an empty list means the package is valid.
    """
    errors: list[str] = []
    if not os.path.isdir(dist_dir):
        return [f"delivery directory {dist_dir!r} is not a directory"]
    manifest_path = os.path.join(dist_dir, "delivery-manifest.json")
    if not os.path.isfile(manifest_path):
        return ["delivery-manifest.json is missing"]
    try:
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, ValueError) as exc:
        return [f"delivery-manifest.json is unparseable: {exc}"]
    if not isinstance(manifest, dict):
        return ["delivery-manifest.json is not an object"]
    if manifest.get("schema_version") != DELIVERY_SCHEMA_VERSION:
        errors.append(
            "delivery manifest schema_version is "
            f"{manifest.get('schema_version')!r}, expected "
            f"{DELIVERY_SCHEMA_VERSION!r}")
    listed = manifest.get("files")
    if not isinstance(listed, list):
        errors.append("delivery manifest has no files list")
        listed = []
    listed_paths = set()
    for entry in listed:
        if not isinstance(entry, dict):
            errors.append("delivery manifest files entry is not an "
                          "object")
            continue
        rel = entry.get("path")
        if not isinstance(rel, str) or not is_safe_relative_path(rel):
            errors.append(f"delivery manifest file path {rel!r} is "
                          "not a safe relative path")
            continue
        listed_paths.add(rel)
        real = os.path.join(dist_dir, rel)
        if not os.path.isfile(real):
            errors.append(f"delivery file {rel!r} is listed in the "
                          "manifest but does not exist")
            continue
        sha, size = hash_file(real)
        if sha != entry.get("sha256"):
            errors.append(f"delivery file {rel!r} SHA-256 mismatch: "
                          f"manifest {entry.get('sha256')}, actual "
                          f"{sha}")
        if size != entry.get("size_bytes"):
            errors.append(f"delivery file {rel!r} size mismatch: "
                          f"manifest {entry.get('size_bytes')}, "
                          f"actual {size}")
    filename = manifest.get("filename")
    if not isinstance(filename, str) or not filename:
        errors.append("delivery manifest has no filename")
    else:
        mp4_path = os.path.join(dist_dir, filename)
        if not os.path.isfile(mp4_path):
            errors.append(f"delivery MP4 {filename!r} does not exist")
        else:
            sha, size = hash_file(mp4_path)
            if sha != manifest.get("sha256"):
                errors.append(
                    "delivery MP4 SHA-256 mismatch: manifest "
                    f"{manifest.get('sha256')}, actual {sha}")
            if size != manifest.get("size_bytes"):
                errors.append(
                    "delivery MP4 size mismatch: manifest "
                    f"{manifest.get('size_bytes')}, actual {size}")
            try:
                probe = probe_media_file(mp4_path, ffprobe=ffprobe)
            except Exception as exc:  # noqa: BLE001 - probe is evidence
                errors.append(f"delivery MP4 could not be probed: "
                              f"{exc}")
                probe = None
            if probe is not None:
                if probe.get("width") != manifest.get("width"):
                    errors.append(
                        "delivery MP4 width "
                        f"{probe.get('width')} does not match the "
                        f"manifest {manifest.get('width')}")
                if probe.get("height") != manifest.get("height"):
                    errors.append(
                        "delivery MP4 height "
                        f"{probe.get('height')} does not match the "
                        f"manifest {manifest.get('height')}")
                if probe.get("frame_rate_rational") != \
                        manifest.get("frame_rate_rational"):
                    errors.append(
                        "delivery MP4 frame rate "
                        f"{probe.get('frame_rate_rational')!r} does "
                        "not match the manifest "
                        f"{manifest.get('frame_rate_rational')!r}")
                if manifest.get("frame_rate") is not None \
                        and probe.get("frame_rate") is not None \
                        and abs(float(probe["frame_rate"])
                               - float(manifest["frame_rate"])) > 0.01:
                    errors.append(
                        "delivery MP4 frame rate "
                        f"{probe.get('frame_rate')} does not match "
                        f"the manifest {manifest.get('frame_rate')}")
                manifest_duration = manifest.get("duration_seconds")
                probe_duration = probe.get("duration_seconds")
                if manifest_duration is not None \
                        and probe_duration is not None \
                        and abs(float(probe_duration)
                               - float(manifest_duration)) \
                        > VERIFY_DURATION_TOLERANCE_SECONDS:
                    errors.append(
                        "delivery MP4 duration "
                        f"{probe_duration}s does not match the "
                        f"manifest {manifest_duration}s")
                if probe.get("video_codec") != \
                        manifest.get("video_codec"):
                    errors.append(
                        "delivery MP4 video codec "
                        f"{probe.get('video_codec')!r} does not "
                        "match the manifest "
                        f"{manifest.get('video_codec')!r}")
                if probe.get("audio_codec") != \
                        manifest.get("audio_codec"):
                    errors.append(
                        "delivery MP4 audio codec "
                        f"{probe.get('audio_codec')!r} does not "
                        "match the manifest "
                        f"{manifest.get('audio_codec')!r}")
    sums_path = os.path.join(dist_dir, "SHA256SUMS")
    if os.path.isfile(sums_path):
        try:
            with open(sums_path, encoding="utf-8") as handle:
                lines = handle.read().splitlines()
        except OSError as exc:
            errors.append(f"SHA256SUMS could not be read: {exc}")
            lines = []
        sums_entries = {}
        for line in lines:
            if not line.strip():
                continue
            parts = line.split(None, 1)
            if len(parts) != 2:
                errors.append(f"SHA256SUMS line is malformed: {line!r}")
                continue
            digest, rel = parts[0], parts[1].strip()
            if rel.startswith("*"):
                rel = rel[1:]
            sums_entries[rel] = digest
        for rel, digest in sorted(sums_entries.items()):
            real = os.path.join(dist_dir, rel)
            if not os.path.isfile(real):
                errors.append(f"SHA256SUMS lists {rel!r}, which "
                              "does not exist")
                continue
            actual, _size = hash_file(real)
            if actual != digest:
                errors.append(f"SHA256SUMS mismatch for {rel!r}: "
                              f"listed {digest}, actual {actual}")
        for entry in _collect_files(dist_dir):
            rel = entry["path"]
            if rel in ("SHA256SUMS", "delivery-manifest.json"):
                continue
            if rel not in sums_entries and rel not in listed_paths:
                errors.append(f"delivery file {rel!r} is present "
                              "but listed in neither the manifest "
                              "nor SHA256SUMS")
            elif rel not in sums_entries:
                errors.append(f"delivery file {rel!r} is missing "
                              "from SHA256SUMS")
    for entry in _collect_files(dist_dir):
        rel = entry["path"]
        if rel in ("SHA256SUMS", "delivery-manifest.json"):
            continue
        if rel not in listed_paths:
            errors.append(f"delivery file {rel!r} is present but "
                          "not listed in the delivery manifest")
    return errors


__all__ = [
    "DeliveryError",
    "DELIVERY_SCHEMA_VERSION",
    "build_delivery_package",
    "write_checksums",
    "verify_delivery_package",
]
