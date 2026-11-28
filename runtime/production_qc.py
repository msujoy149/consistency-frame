"""Consistency Frame P1 — Phase G technical / visual / audio QC
(CF-WO-P1-006).

Quality control for the reference vertical production. Three
stages, each honest about what it can and cannot check:

- :func:`technical_qc` — container, geometry, codecs, duration,
  decodability, timestamps, black gaps and frozen segments, all
  measured with ffprobe/ffmpeg. A failed check fails the verdict.
- :func:`visual_qc` — one keyframe per shot plus a contact sheet
  and a black-frame report for a human reviewer. It never claims
  an automated visual-quality review: the report always states
  that human review is required and editorial approval starts
  empty.
- :func:`audio_qc` — loudness and true peak (ebur128), peak and
  clipping (volumedetect/astats), silence classification against
  the timeline's recorded intentional silences, dialogue span and
  per-track alignment against the asset records' probed
  durations.
- :func:`qc_decision` — the delivery gate. DELIVERY_READY only
  when the technical verdict passes, the audio report carries no
  critical finding, and a named human reviewer approved. There
  is no override flag and no automated approval.

Standard library plus ffmpeg/ffprobe only. A missing ffmpeg or
ffprobe binary raises :class:`QCError` — a QC stage is never
skipped because its tool is absent.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
from fractions import Fraction

from .production_assets import hash_file
from .timeline_delivery import aspect_ratio_for_dimensions

QC_SCHEMA_VERSION = "2.5"

#: Blackdetect: a picture counts as black when at least this
#: fraction of its pixels is below the pixel threshold.
BLACK_PICTURE_THRESHOLD = 0.98
#: Blackdetect: a black run shorter than this is not a gap.
BLACK_MIN_DURATION_SECONDS = 0.5
#: Freezedetect noise tolerance (mean frame difference).
FREEZE_NOISE_THRESHOLD = 0.001
#: Freezedetect: a frozen run shorter than this is not a segment.
FREEZE_MIN_DURATION_SECONDS = 1.0
#: Silencedetect threshold, in dBFS.
SILENCE_THRESHOLD_DB = -50
#: Silencedetect: a silence shorter than this is not reported.
SILENCE_MIN_DURATION_SECONDS = 0.5
#: An unexpected silence longer than this is a major finding.
UNEXPECTED_SILENCE_MAJOR_SECONDS = 2.0
#: A sample peak at or above this level counts as clipped audio.
CLIP_PEAK_DBFS = -0.1
#: A format start time at or above this is an invalid timestamp.
TIMESTAMP_MAX_START_SECONDS = 1.0
#: Stream durations must agree with the format duration within this.
STREAM_DURATION_TOLERANCE_SECONDS = 0.5
#: Per-track alignment tolerance between placed and asset duration.
TRACK_ALIGNMENT_TOLERANCE_SECONDS = 0.1
#: A track end past the timeline by more than this is a finding.
AUDIO_BEYOND_TIMELINE_TOLERANCE_SECONDS = 0.05
#: Contact-sheet tile size (540x960 per tile, 2 columns).
CONTACT_SHEET_TILE_WIDTH = 540
CONTACT_SHEET_TILE_HEIGHT = 960
CONTACT_SHEET_COLUMNS = 2

_BLACK_RE = re.compile(
    r"black_start:\s*([\d.]+)\s+black_end:\s*([\d.]+)\s+"
    r"black_duration:\s*([\d.]+)")
_FREEZE_START_RE = re.compile(r"freeze_start:\s*([\d.]+)")
_FREEZE_END_RE = re.compile(r"freeze_end:\s*([\d.]+)")
_FREEZE_DURATION_RE = re.compile(r"freeze_duration:\s*([\d.]+)")
_SILENCE_START_RE = re.compile(r"silence_start:\s*([\d.]+)")
_SILENCE_END_RE = re.compile(
    r"silence_end:\s*([\d.]+)\s*\|\s*"
    r"silence_duration:\s*([\d.]+)")
_EBUR_I_RE = re.compile(r"I:\s+(-?[\d.]+)\s+LUFS")
_EBUR_PEAK_RE = re.compile(r"Peak:\s+(-?[\d.]+)\s+dBFS")
_VOLUME_MAX_RE = re.compile(r"max_volume:\s+(-inf|-?[\d.]+)\s+dB")
_ASTATS_PEAK_RE = re.compile(r"Peak level dB:\s+(-?[\d.]+)")


class QCError(ValueError):
    """QC error carrying a list of structured messages."""

    def __init__(self, errors):
        if isinstance(errors, str):
            errors = [errors]
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


def _require_tools(*binaries) -> None:
    """Raise QCError when a required tool binary is absent.

    A missing ffmpeg/ffprobe is never a reason to skip a check.
    """
    for binary in binaries:
        if shutil.which(binary) is None:
            raise QCError(f"required QC tool {binary!r} is not "
                          "available on PATH — QC cannot run "
                          "without it")


def _run(argv, timeout_s):
    """Run a subprocess, returning the completed process.

    A missing binary or a timeout is a QCError, never a silent
    empty result.
    """
    try:
        return subprocess.run(argv, capture_output=True, text=True,
                              timeout=timeout_s)
    except OSError as exc:
        raise QCError(f"could not run {' '.join(argv[:2])}: "
                      f"{exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise QCError(f"QC command timed out after {timeout_s}s: "
                      f"{' '.join(argv[:2])}") from exc


def _check(check_id, status, detail):
    """One technical-QC check entry."""
    return {"check_id": check_id, "status": status, "detail": detail}


def _probe_json(path, *, ffprobe, timeout_s):
    """Full ffprobe JSON for a file, or (None, error string)."""
    proc = _run([ffprobe, "-v", "error", "-show_format",
                 "-show_streams", "-of", "json", path], timeout_s)
    if proc.returncode != 0:
        return None, (proc.stderr or proc.stdout or "").strip()[:500]
    try:
        return json.loads(proc.stdout), ""
    except ValueError:
        return None, "ffprobe returned unparseable output"


def _aspect_label(width, height):
    """Reduced-fraction aspect label (``"9:16"``), never a float."""
    if not isinstance(width, int) or not isinstance(height, int) \
            or width <= 0 or height <= 0:
        return None
    divisor = math.gcd(width, height)
    return f"{width // divisor}:{height // divisor}"


def _rational_for_frame_rate(rate):
    """Exact rational string for a frame rate (``30`` -> ``"30/1"``)."""
    try:
        fraction = Fraction(str(rate)).limit_denominator(10000)
    except (ValueError, ZeroDivisionError):
        return None
    return f"{fraction.numerator}/{fraction.denominator}"


def _intentional_windows(intentional_silences):
    """Normalise intentional silences to [(start, end)] windows.

    Accepts the timeline shape (``timeline_start_seconds`` /
    ``duration_seconds``) and the plain shape (``start`` / ``end``
    or ``start`` / ``duration_seconds``). Unparseable entries are
    ignored — they never silently excuse a segment.
    """
    windows = []
    for entry in intentional_silences or []:
        if not isinstance(entry, dict):
            continue
        start = entry.get("timeline_start_seconds", entry.get("start"))
        duration = entry.get("duration_seconds")
        end = entry.get("end")
        try:
            start = float(start)
            if end is not None:
                end = float(end)
            elif duration is not None:
                end = start + float(duration)
            else:
                continue
        except (TypeError, ValueError):
            continue
        if end >= start:
            windows.append((start, end))
    return windows


def _segment_is_intentional(start, end, windows, *, tolerance=0.25):
    """True when a detected segment is covered by an intentional window."""
    for window_start, window_end in windows:
        if start >= window_start - tolerance \
                and end <= window_end + tolerance:
            return True
    return False


def _parse_blackdetect(stderr):
    """Black segments from blackdetect output: [{start, end, duration}]."""
    segments = []
    for match in _BLACK_RE.finditer(stderr or ""):
        start, end, duration = (float(v) for v in match.groups())
        segments.append({"start": start, "end": end,
                         "duration": duration})
    return segments


def _parse_freezedetect(stderr):
    """Frozen segments from freezedetect output.

    The filter logs start, duration and end on separate lines, in
    order, so the three value lists are zipped together.
    """
    starts = [float(v) for v in _FREEZE_START_RE.findall(stderr or "")]
    ends = [float(v) for v in _FREEZE_END_RE.findall(stderr or "")]
    durations = [float(v) for v in
                 _FREEZE_DURATION_RE.findall(stderr or "")]
    segments = []
    for start, end, duration in zip(starts, ends, durations):
        segments.append({"start": start, "end": end,
                         "duration": duration})
    return segments


def _parse_silencedetect(stderr):
    """Silences from silencedetect output: [{start, end, duration}].

    The filter logs the start on one line and the end plus
    duration on the next (``silence_end: X | silence_duration:
    Y``), so the two value lists are zipped together in order.
    """
    starts = [float(v) for v in
              _SILENCE_START_RE.findall(stderr or "")]
    ends = [(float(end), float(duration)) for end, duration in
            _SILENCE_END_RE.findall(stderr or "")]
    segments = []
    for start, (end, duration) in zip(starts, ends):
        segments.append({"start": start, "end": end,
                         "duration": duration})
    return segments


def _timeline_intentional_silences(timeline):
    """Intentional-silence windows recorded on a timeline."""
    if not isinstance(timeline, dict):
        return []
    return _intentional_windows(timeline.get("intentional_silences"))


def _video_clips(timeline):
    """Video clips from a timeline, in timeline order."""
    if not isinstance(timeline, dict):
        return []
    tracks = timeline.get("video_tracks") or []
    for track in tracks:
        if isinstance(track, dict):
            return list(track.get("clips") or [])
    return []


def _audio_tracks(timeline):
    """Audio tracks from a timeline (list of track dicts)."""
    if not isinstance(timeline, dict):
        return []
    tracks = timeline.get("audio_tracks") or []
    return [t for t in tracks if isinstance(t, dict)]


def _track_span(clips):
    """(start, end) span of clips, or (None, None) when empty."""
    starts = []
    ends = []
    for clip in clips or []:
        if not isinstance(clip, dict):
            continue
        start = clip.get("timeline_start_seconds")
        duration = clip.get("duration_seconds")
        if isinstance(start, (int, float)) \
                and isinstance(duration, (int, float)):
            starts.append(float(start))
            ends.append(float(start) + float(duration))
    if not starts:
        return None, None
    return min(starts), max(ends)


# ------------------------------------------------------------------
# Technical QC
# ------------------------------------------------------------------

def technical_qc(path, profile, *, intentional_silences=None,
                 ffmpeg="ffmpeg", ffprobe="ffprobe", timeout_s=300):
    """Technical QC of a rendered MP4 against its output profile.

    Validates, each as a separate check entry: the file exists
    and is non-zero; the container is MP4; video and audio
    streams exist; resolution, aspect ratio (reduced fraction,
    never a float) and frame rate (exact rational comparison)
    match the profile; duration is inside the profile range;
    video/audio codecs match; the audio decodes; timestamps are
    valid; no black gap outside a recorded intentional silence;
    no frozen segment; and a full decode pass reports no errors.

    Returns a report ``{verdict, checks, measured}``; the verdict
    is ``"fail"`` when any check fails. Raises :class:`QCError`
    when ffmpeg/ffprobe is missing or the profile is incomplete —
    a missing tool never produces a passing report.
    """
    _require_tools(ffmpeg, ffprobe)
    if not isinstance(profile, dict):
        raise QCError("technical QC needs an output profile object")
    missing = [key for key in (
        "width", "height", "aspect_ratio", "frame_rate",
        "video_codec", "audio_codec", "duration_min_seconds",
        "duration_max_seconds") if profile.get(key) is None]
    if missing:
        raise QCError("output profile is missing required fields "
                      f"for technical QC: {', '.join(sorted(missing))}")
    windows = _intentional_windows(intentional_silences)
    measured = {
        "size_bytes": None, "sha256": None, "format_name": None,
        "duration_seconds": None, "width": None, "height": None,
        "aspect_ratio": None, "frame_rate_rational": None,
        "frame_rate": None, "video_codec": None,
        "audio_codec": None, "audio_sample_rate": None,
        "audio_channels": None, "start_time_seconds": None,
        "decode_errors": [],
    }
    checks: list = []

    def _fail_rest(reason):
        for check_id in (
                "mp4-container", "video-stream", "audio-stream",
                "resolution", "aspect-ratio", "frame-rate",
                "duration", "video-codec", "audio-codec",
                "audio-decodable", "timestamps", "black-gaps",
                "frozen-segments", "decode-errors"):
            checks.append(_check(check_id, "fail", reason))

    if not os.path.isfile(path):
        checks.append(_check("file-exists", "fail",
                             f"file {path!r} does not exist"))
        checks.append(_check("file-nonzero", "fail",
                             "file does not exist"))
        _fail_rest("not probed: file does not exist")
        return {"verdict": "fail", "checks": checks,
                "measured": measured}
    checks.append(_check("file-exists", "pass",
                         f"file {path!r} exists"))
    sha, size = hash_file(path)
    measured["size_bytes"] = size
    measured["sha256"] = sha
    if size <= 0:
        checks.append(_check("file-nonzero", "fail",
                             "file is empty (0 bytes)"))
        _fail_rest("not probed: file is empty")
        return {"verdict": "fail", "checks": checks,
                "measured": measured}
    checks.append(_check("file-nonzero", "pass",
                         f"file is {size} bytes"))

    probe, probe_error = _probe_json(path, ffprobe=ffprobe,
                                     timeout_s=timeout_s)
    if probe is None:
        checks.append(_check(
            "mp4-container", "fail",
            f"ffprobe failed: {probe_error or 'unknown error'}"))
        checks.append(_check("video-stream", "fail",
                             "not probed: ffprobe failed"))
        checks.append(_check("audio-stream", "fail",
                             "not probed: ffprobe failed"))
        checks.append(_check("resolution", "fail",
                             "not probed: ffprobe failed"))
        checks.append(_check("aspect-ratio", "fail",
                             "not probed: ffprobe failed"))
        checks.append(_check("frame-rate", "fail",
                             "not probed: ffprobe failed"))
        checks.append(_check("duration", "fail",
                             "not probed: ffprobe failed"))
        checks.append(_check("video-codec", "fail",
                             "not probed: ffprobe failed"))
        checks.append(_check("audio-codec", "fail",
                             "not probed: ffprobe failed"))
        decode = _run([ffmpeg, "-v", "error", "-i", path,
                       "-f", "null", "-"], timeout_s)
        decode_errors = [line for line in
                         (decode.stderr or "").splitlines()
                         if line.strip()]
        measured["decode_errors"] = decode_errors
        checks.append(_check(
            "audio-decodable", "fail" if decode.returncode != 0
            else "pass",
            "ffmpeg decode failed"
            if decode.returncode != 0
            else "audio decoded (ffprobe failed, but the "
                 "decode pass ran)"))
        checks.append(_check("timestamps", "fail",
                             "not probed: ffprobe failed"))
        checks.append(_check("black-gaps", "fail",
                             "not probed: ffprobe failed"))
        checks.append(_check("frozen-segments", "fail",
                             "not probed: ffprobe failed"))
        checks.append(_check(
            "decode-errors",
            "fail" if decode.returncode != 0 or decode_errors
            else "pass",
            f"decode reported {len(decode_errors)} error line(s)"
            if decode_errors else "decode pass clean"
            if decode.returncode == 0 else "decode pass failed"))
        return {"verdict": "fail", "checks": checks,
                "measured": measured}

    fmt = probe.get("format") or {}
    streams = probe.get("streams") or []
    video = next((s for s in streams
                  if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams
                  if s.get("codec_type") == "audio"), None)
    measured["format_name"] = fmt.get("format_name")
    try:
        measured["duration_seconds"] = float(fmt["duration"]) \
            if fmt.get("duration") else None
    except (TypeError, ValueError):
        measured["duration_seconds"] = None
    try:
        measured["start_time_seconds"] = float(fmt["start_time"]) \
            if fmt.get("start_time") is not None else None
    except (TypeError, ValueError):
        measured["start_time_seconds"] = None
    if video is not None:
        measured["width"] = video.get("width")
        measured["height"] = video.get("height")
        measured["video_codec"] = video.get("codec_name")
        measured["frame_rate_rational"] = \
            str(video.get("avg_frame_rate") or "") or None
        rate = measured["frame_rate_rational"]
        if rate and "/" in rate:
            num, den = rate.split("/", 1)
            try:
                measured["frame_rate"] = float(num) / float(den) \
                    if float(den) else None
            except (TypeError, ValueError, ZeroDivisionError):
                measured["frame_rate"] = None
        measured["aspect_ratio"] = _aspect_label(
            measured["width"], measured["height"])
    if audio is not None:
        measured["audio_codec"] = audio.get("codec_name")
        try:
            measured["audio_sample_rate"] = int(
                audio.get("sample_rate"))
        except (TypeError, ValueError):
            measured["audio_sample_rate"] = None
        measured["audio_channels"] = audio.get("channels")

    format_name = measured["format_name"] or ""
    checks.append(_check(
        "mp4-container",
        "pass" if "mp4" in format_name.split(",") else "fail",
        f"container format is {format_name!r}"))
    checks.append(_check(
        "video-stream",
        "pass" if video is not None else "fail",
        "video stream present" if video is not None
        else "no video stream"))
    requires_audio = profile.get("audio_channels", 2) != 0
    checks.append(_check(
        "audio-stream",
        "pass" if audio is not None or not requires_audio else "fail",
        "audio stream present" if audio is not None
        else "no audio stream, but the profile requires audio"
        if requires_audio else "no audio stream (profile needs none)"))
    checks.append(_check(
        "resolution",
        "pass" if measured["width"] == profile["width"]
        and measured["height"] == profile["height"] else "fail",
        f"resolution is {measured['width']}x{measured['height']}, "
        f"expected {profile['width']}x{profile['height']}"))
    checks.append(_check(
        "aspect-ratio",
        "pass" if measured["aspect_ratio"]
        == profile["aspect_ratio"] else "fail",
        f"aspect ratio is {measured['aspect_ratio']!r}, expected "
        f"{profile['aspect_ratio']!r}"))
    expected_rate = _rational_for_frame_rate(profile["frame_rate"])
    checks.append(_check(
        "frame-rate",
        "pass" if measured["frame_rate_rational"] == expected_rate
        else "fail",
        f"frame rate is {measured['frame_rate_rational']!r}, "
        f"expected {expected_rate!r}"))
    duration = measured["duration_seconds"]
    checks.append(_check(
        "duration",
        "pass" if duration is not None
        and float(profile["duration_min_seconds"]) <= duration
        <= float(profile["duration_max_seconds"]) else "fail",
        f"duration is {duration}s, expected "
        f"{profile['duration_min_seconds']}–"
        f"{profile['duration_max_seconds']}s"))
    checks.append(_check(
        "video-codec",
        "pass" if measured["video_codec"] == profile["video_codec"]
        else "fail",
        f"video codec is {measured['video_codec']!r}, expected "
        f"{profile['video_codec']!r}"))
    checks.append(_check(
        "audio-codec",
        "pass" if measured["audio_codec"] == profile["audio_codec"]
        else "fail",
        f"audio codec is {measured['audio_codec']!r}, expected "
        f"{profile['audio_codec']!r}"))

    # One full decode pass serves both the audio-decodable check
    # and the decode-errors check.
    decode = _run([ffmpeg, "-v", "error", "-i", path,
                   "-f", "null", "-"], timeout_s)
    decode_errors = [line for line in
                     (decode.stderr or "").splitlines()
                     if line.strip()]
    measured["decode_errors"] = decode_errors
    checks.append(_check(
        "audio-decodable",
        "pass" if decode.returncode == 0 else "fail",
        "audio decoded cleanly" if decode.returncode == 0
        else f"ffmpeg decode failed (exit {decode.returncode}): "
             f"{(decode.stderr or '').strip()[:300]}"))

    # Timestamps: format start time in [0, 1.0), and every stream
    # duration agrees with the format duration within 0.5s.
    timestamp_problems = []
    start_time = measured["start_time_seconds"]
    if start_time is None:
        timestamp_problems.append("format start_time is missing")
    elif not 0 <= start_time < TIMESTAMP_MAX_START_SECONDS:
        timestamp_problems.append(
            f"format start_time is {start_time}s (must be >= 0 "
            f"and < {TIMESTAMP_MAX_START_SECONDS}s)")
    if duration is not None:
        for stream in streams:
            stream_duration = stream.get("duration")
            if stream_duration is None:
                continue
            try:
                stream_seconds = float(stream_duration)
            except (TypeError, ValueError):
                continue
            if abs(stream_seconds - duration) \
                    > STREAM_DURATION_TOLERANCE_SECONDS:
                timestamp_problems.append(
                    f"{stream.get('codec_type')} stream duration "
                    f"{stream_seconds}s disagrees with format "
                    f"duration {duration}s by more than "
                    f"{STREAM_DURATION_TOLERANCE_SECONDS}s")
    checks.append(_check(
        "timestamps",
        "pass" if not timestamp_problems else "fail",
        "timestamps valid" if not timestamp_problems
        else "; ".join(timestamp_problems)))

    black_proc = _run([ffmpeg, "-v", "info", "-i", path,
                       "-vf", "blackdetect=d="
                       f"{BLACK_MIN_DURATION_SECONDS}:pic_th="
                       f"{BLACK_PICTURE_THRESHOLD}:pix_th=0.10",
                       "-an", "-f", "null", "-"], timeout_s)
    if black_proc.returncode != 0:
        checks.append(_check("black-gaps", "fail",
                             "blackdetect failed: "
                             f"{(black_proc.stderr or '').strip()[:300]}"))
        black_segments = []
    else:
        black_segments = _parse_blackdetect(black_proc.stderr)
        unexpected = [s for s in black_segments
                      if not _segment_is_intentional(
                          s["start"], s["end"], windows)]
        checks.append(_check(
            "black-gaps",
            "pass" if not unexpected else "fail",
            "no unexpected black gaps" if not unexpected
            else "unexpected black segment(s): " + ", ".join(
                f"{s['start']:.2f}–{s['end']:.2f}s"
                for s in unexpected)))

    freeze_proc = _run([ffmpeg, "-v", "info", "-i", path,
                        "-vf", "freezedetect=n="
                        f"{FREEZE_NOISE_THRESHOLD}:d="
                        f"{FREEZE_MIN_DURATION_SECONDS}",
                        "-f", "null", "-"], timeout_s)
    if freeze_proc.returncode != 0:
        checks.append(_check("frozen-segments", "fail",
                             "freezedetect failed: "
                             f"{(freeze_proc.stderr or '').strip()[:300]}"))
    else:
        frozen_segments = _parse_freezedetect(freeze_proc.stderr)
        checks.append(_check(
            "frozen-segments",
            "pass" if not frozen_segments else "fail",
            "no frozen segments" if not frozen_segments
            else "frozen segment(s): " + ", ".join(
                f"{s['start']:.2f}–{s['end']:.2f}s"
                for s in frozen_segments)))

    checks.append(_check(
        "decode-errors",
        "pass" if decode.returncode == 0 and not decode_errors
        else "fail",
        "decode pass clean" if decode.returncode == 0
        and not decode_errors
        else f"decode reported {len(decode_errors)} error line(s)"
        if decode_errors else
        f"decode pass failed (exit {decode.returncode})"))

    verdict = "pass" if all(c["status"] == "pass" for c in checks) \
        else "fail"
    return {"verdict": verdict, "checks": checks,
            "measured": measured}


# ------------------------------------------------------------------
# Visual QC
# ------------------------------------------------------------------

def visual_qc(path, timeline, out_dir, *, ffmpeg="ffmpeg",
              ffprobe="ffprobe", timeout_s=300):
    """Visual QC evidence for a rendered MP4 against a timeline.

    Extracts one keyframe per shot at the shot midpoint, builds
    a contact sheet (tile filter, 2 columns, 540x960 per tile),
    re-runs blackdetect for the black-frame report, and records
    the aspect/crop report from the probe. This pipeline never
    crops: the report records that explicitly.

    Returns ``{contact_sheet, keyframes, shot_summary,
    black_frame_report, aspect_crop_report, findings,
    human_review_required, editorial_approval}``. The report
    never claims an automated visual-quality review: human
    review is always required and editorial approval always
    starts as None. Raises :class:`QCError` when the tools are
    missing, the file cannot be probed, or the timeline has no
    video clips.
    """
    _require_tools(ffmpeg, ffprobe)
    if not os.path.isfile(path):
        raise QCError(f"visual QC input {path!r} does not exist")
    clips = _video_clips(timeline)
    if not clips:
        raise QCError("visual QC needs a timeline with video clips")
    os.makedirs(out_dir, exist_ok=True)
    probe, probe_error = _probe_json(path, ffprobe=ffprobe,
                                     timeout_s=timeout_s)
    if probe is None:
        raise QCError(f"visual QC could not probe {path!r}: "
                      f"{probe_error or 'unknown error'}")
    video = next((s for s in probe.get("streams") or []
                  if s.get("codec_type") == "video"), None)
    width = (video or {}).get("width")
    height = (video or {}).get("height")

    keyframes: list = []
    shot_summary: list = []
    for clip in clips:
        shot_id = clip.get("shot_id")
        start = float(clip.get("timeline_start_seconds") or 0)
        duration = float(clip.get("duration_seconds") or 0)
        midpoint = start + duration / 2
        frame_name = f"keyframe-{shot_id}.png"
        frame_path = os.path.join(out_dir, frame_name)
        proc = _run([ffmpeg, "-y", "-v", "error", "-i", path,
                     "-ss", str(midpoint), "-frames:v", "1",
                     "-q:v", "2", frame_path], timeout_s)
        if proc.returncode != 0 or not os.path.isfile(frame_path):
            raise QCError(
                f"keyframe extraction failed for shot "
                f"{shot_id!r} at {midpoint}s: "
                f"{(proc.stderr or '').strip()[:300]}")
        keyframes.append({"shot_id": shot_id, "path": frame_name,
                          "at_seconds": midpoint})
        shot_summary.append({
            "shot_id": shot_id,
            "timeline_start_seconds": start,
            "duration_seconds": duration,
            "asset_id": clip.get("asset_id")})

    rows = max(1, math.ceil(len(keyframes) / CONTACT_SHEET_COLUMNS))
    inputs: list = []
    filter_parts: list = []
    for index, frame in enumerate(keyframes):
        inputs.extend(["-i", os.path.join(out_dir, frame["path"])])
        filter_parts.append(
            f"[{index}:v]scale={CONTACT_SHEET_TILE_WIDTH}:"
            f"{CONTACT_SHEET_TILE_HEIGHT},"
            f"setpts=N/(30*TB)[v{index}]")
    concat_inputs = "".join(f"[v{i}]" for i in range(len(keyframes)))
    filter_parts.append(
        f"{concat_inputs}concat=n={len(keyframes)}:v=1:a=0,"
        f"tile={CONTACT_SHEET_COLUMNS}x{rows}[sheet]")
    sheet_name = "contact-sheet.png"
    sheet_path = os.path.join(out_dir, sheet_name)
    proc = _run([ffmpeg, "-y", "-v", "error", *inputs,
                 "-filter_complex", ";".join(filter_parts),
                 "-map", "[sheet]", "-frames:v", "1",
                 sheet_path], timeout_s)
    if proc.returncode != 0 or not os.path.isfile(sheet_path):
        raise QCError(
            "contact sheet generation failed: "
            f"{(proc.stderr or '').strip()[:300]}")

    black_proc = _run([ffmpeg, "-v", "info", "-i", path,
                       "-vf", "blackdetect=d="
                       f"{BLACK_MIN_DURATION_SECONDS}:pic_th="
                       f"{BLACK_PICTURE_THRESHOLD}:pix_th=0.10",
                       "-an", "-f", "null", "-"], timeout_s)
    if black_proc.returncode != 0:
        raise QCError("visual QC blackdetect failed: "
                      f"{(black_proc.stderr or '').strip()[:300]}")
    segments = _parse_blackdetect(black_proc.stderr)
    windows = _timeline_intentional_silences(timeline)
    intentional = [s for s in segments
                   if _segment_is_intentional(s["start"], s["end"],
                                              windows)]
    unexpected = [s for s in segments
                  if not _segment_is_intentional(s["start"], s["end"],
                                                 windows)]
    findings: list = []
    for segment in unexpected:
        findings.append({
            "severity": "major", "code": "unexpected-black-segment",
            "message": f"unexpected black segment "
                       f"{segment['start']:.2f}–{segment['end']:.2f}s "
                       f"({segment['duration']:.2f}s) with no "
                       "recorded intentional silence"})
    return {
        "contact_sheet": sheet_name,
        "keyframes": keyframes,
        "shot_summary": shot_summary,
        "black_frame_report": {
            "segments": segments,
            "intentional": intentional,
            "unexpected": unexpected,
        },
        "aspect_crop_report": {
            "width": width,
            "height": height,
            "aspect_ratio": aspect_ratio_for_dimensions(width, height)
            if isinstance(width, int) and isinstance(height, int)
            else None,
            "cropped": False,
            "notes": ("no cropping is applied by this pipeline: "
                      "the rendered frame is used as delivered, "
                      "and the aspect ratio is verified from the "
                      "probe, not assumed"),
        },
        "findings": findings,
        "human_review_required": True,
        "editorial_approval": None,
    }


# ------------------------------------------------------------------
# Audio QC
# ------------------------------------------------------------------

def audio_qc(path, timeline, voice_lines, audio_profile, *,
             ffmpeg="ffmpeg", ffprobe="ffprobe", timeout_s=300,
             assets=None):
    """Audio QC of a rendered MP4 against a timeline and profile.

    Measures integrated loudness and true peak (ebur128 — when
    the filter is unavailable the values are honestly recorded
    as None), sample peak (volumedetect/astats), and silence
    (silencedetect, classified against the timeline's recorded
    intentional silences). Dialogue duration is the voice-track
    span in the timeline; per-track alignment compares the
    placed clip durations with the asset records' probed
    durations (``assets``, when supplied, is a list or dict of
    asset records).

    Findings use the severities ``critical`` / ``major`` /
    ``minor``: clipped audio, missing dialogue, empty audio,
    missing mandatory music/SFX asset (critical); unexpected
    long silence, misaligned track, audio beyond the timeline
    (major). Raises :class:`QCError` when the tools are missing
    or the file cannot be probed.
    """
    _require_tools(ffmpeg, ffprobe)
    if not os.path.isfile(path):
        raise QCError(f"audio QC input {path!r} does not exist")
    probe, probe_error = _probe_json(path, ffprobe=ffprobe,
                                     timeout_s=timeout_s)
    if probe is None:
        raise QCError(f"audio QC could not probe {path!r}: "
                      f"{probe_error or 'unknown error'}")
    audio = next((s for s in probe.get("streams") or []
                  if s.get("codec_type") == "audio"), None)
    timeline_duration = timeline.get("duration_seconds") \
        if isinstance(timeline, dict) else None
    windows = _timeline_intentional_silences(timeline)
    findings: list = []

    integrated_loudness = None
    true_peak = None
    peak_dbfs = None
    clipped = False
    silence_report: list = []

    if audio is None:
        findings.append({
            "severity": "critical", "code": "empty-audio",
            "message": "the rendered file has no audio stream"})
    else:
        ebur_proc = _run([ffmpeg, "-v", "info", "-i", path,
                          "-af", "ebur128=framelog=verbose:peak=true",
                          "-f", "null", "-"], timeout_s)
        ebur_out = ebur_proc.stderr or ""
        if ebur_proc.returncode != 0 \
                and "No such filter" in ebur_out:
            findings.append({
                "severity": "minor", "code": "loudness-unmeasured",
                "message": "ebur128 is unavailable in this ffmpeg "
                           "build: integrated loudness and true "
                           "peak are not measured"})
        elif ebur_proc.returncode != 0:
            findings.append({
                "severity": "minor", "code": "loudness-unmeasured",
                "message": "ebur128 measurement failed: "
                           f"{ebur_out.strip()[:300]}"})
        else:
            loudness_values = _EBUR_I_RE.findall(ebur_out)
            peak_values = _EBUR_PEAK_RE.findall(ebur_out)
            if loudness_values:
                integrated_loudness = float(loudness_values[-1])
            if peak_values:
                true_peak = float(peak_values[-1])
            if integrated_loudness is None:
                findings.append({
                    "severity": "minor",
                    "code": "loudness-unmeasured",
                    "message": "ebur128 ran but reported no "
                               "integrated loudness value"})

        volume_proc = _run([ffmpeg, "-v", "info", "-i", path,
                            "-af", "volumedetect", "-f", "null", "-"],
                           timeout_s)
        volume_match = _VOLUME_MAX_RE.search(volume_proc.stderr or "")
        silent = False
        if volume_match:
            raw = volume_match.group(1)
            if raw == "-inf":
                silent = True
            else:
                peak_dbfs = float(raw)
        astats_peak = None
        astats_proc = _run([ffmpeg, "-v", "info", "-i", path,
                            "-af", "astats=metadata=1", "-f", "null",
                            "-"], timeout_s)
        astats_values = _ASTATS_PEAK_RE.findall(
            astats_proc.stderr or "")
        if astats_values:
            astats_peak = max(float(v) for v in astats_values)
        if peak_dbfs is not None and peak_dbfs >= CLIP_PEAK_DBFS:
            clipped = True
        if astats_peak is not None and astats_peak > 0.0:
            clipped = True
        if clipped:
            findings.append({
                "severity": "critical", "code": "clipped-audio",
                "message": f"audio is clipped (sample peak "
                           f"{peak_dbfs} dBFS"
                           + (f", astats peak {astats_peak} dB"
                              if astats_peak is not None else "")
                           + ")"})
        if silent:
            findings.append({
                "severity": "critical", "code": "empty-audio",
                "message": "the rendered audio is digital silence "
                           "(peak -inf dBFS)"})

        silence_proc = _run([ffmpeg, "-v", "info", "-i", path,
                             "-af", "silencedetect=noise="
                             f"{SILENCE_THRESHOLD_DB}dB:d="
                             f"{SILENCE_MIN_DURATION_SECONDS}",
                             "-f", "null", "-"], timeout_s)
        if silence_proc.returncode == 0:
            for segment in _parse_silencedetect(silence_proc.stderr):
                intentional = _segment_is_intentional(
                    segment["start"], segment["end"], windows)
                silence_report.append({
                    "start": segment["start"],
                    "end": segment["end"],
                    "duration": segment["duration"],
                    "intentional": intentional})
                if not intentional and segment["duration"] \
                        > UNEXPECTED_SILENCE_MAJOR_SECONDS:
                    findings.append({
                        "severity": "major",
                        "code": "unexpected-long-silence",
                        "message": f"unexpected silence "
                                   f"{segment['start']:.2f}–"
                                   f"{segment['end']:.2f}s "
                                   f"({segment['duration']:.2f}s) "
                                   "with no recorded intentional "
                                   "silence"})

    tracks = _audio_tracks(timeline)
    by_kind = {}
    for track in tracks:
        by_kind.setdefault(track.get("kind") or track.get("track_id"),
                           track)
    voice_track = by_kind.get("dialogue") or by_kind.get("voice")
    voice_clips = (voice_track or {}).get("clips") or []
    voice_start, voice_end = _track_span(voice_clips)
    dialogue_duration = 0.0
    if voice_start is not None and voice_end is not None:
        dialogue_duration = voice_end - voice_start
    covered_lines = {c.get("line_id") for c in voice_clips
                     if isinstance(c, dict)}
    missing_lines = [ln.get("line_id") for ln in (voice_lines or [])
                     if isinstance(ln, dict)
                     and ln.get("line_id") not in covered_lines]
    if not voice_clips or dialogue_duration <= 0:
        findings.append({
            "severity": "critical", "code": "missing-dialogue",
            "message": "the timeline carries no dialogue on the "
                       "voice track"})
    elif missing_lines:
        findings.append({
            "severity": "critical", "code": "missing-dialogue",
            "message": "voice lines with no timeline clip: "
                       + ", ".join(sorted(missing_lines))})
    music_track = by_kind.get("music")
    if music_track is None or not (music_track.get("clips") or []):
        findings.append({
            "severity": "critical", "code": "missing-music-asset",
            "message": "the timeline carries no music track: the "
                       "mandatory music bed is missing"})
    sfx_track = by_kind.get("sfx")
    if sfx_track is None or not (sfx_track.get("clips") or []):
        findings.append({
            "severity": "critical", "code": "missing-sfx-asset",
            "message": "the timeline carries no SFX track: the "
                       "mandatory SFX cues are missing"})

    asset_by_id = {}
    if isinstance(assets, dict):
        asset_by_id = assets
    elif isinstance(assets, list):
        asset_by_id = {a.get("asset_id"): a for a in assets
                       if isinstance(a, dict)}
    track_alignment: list = []
    for track in tracks:
        track_id = track.get("track_id")
        clips = track.get("clips") or []
        expected = sum(float(c.get("duration_seconds") or 0)
                       for c in clips if isinstance(c, dict))
        measured_duration = None
        if asset_by_id:
            total = 0.0
            complete = True
            for clip in clips:
                record = asset_by_id.get(clip.get("asset_id")) \
                    if isinstance(clip, dict) else None
                record_duration = (record or {}).get(
                    "duration_seconds") if isinstance(record, dict) \
                    else None
                if record_duration is None:
                    complete = False
                    break
                total += float(record_duration)
            measured_duration = total if complete else None
        else:
            measured_duration = expected
        aligned = measured_duration is not None \
            and abs(expected - measured_duration) \
            <= TRACK_ALIGNMENT_TOLERANCE_SECONDS
        track_alignment.append({
            "track_id": track_id,
            "expected_duration_seconds": expected,
            "measured_duration_seconds": measured_duration,
            "aligned": aligned})
        if not aligned:
            findings.append({
                "severity": "major", "code": "track-misaligned",
                "message": f"audio track {track_id!r}: placed "
                           f"duration {expected}s does not match "
                           f"the asset durations "
                           f"({measured_duration}s)"})
        if timeline_duration is not None:
            _start, track_end = _track_span(clips)
            if track_end is not None and track_end \
                    > float(timeline_duration) \
                    + AUDIO_BEYOND_TIMELINE_TOLERANCE_SECONDS:
                findings.append({
                    "severity": "major",
                    "code": "audio-beyond-timeline",
                    "message": f"audio track {track_id!r} ends at "
                               f"{track_end}s, past the timeline "
                               f"duration {timeline_duration}s"})

    asset_hashes = []
    for asset_id in sorted(asset_by_id):
        record = asset_by_id[asset_id]
        if isinstance(record, dict) and record.get("sha256"):
            asset_hashes.append({"asset_id": asset_id,
                                 "sha256": record["sha256"]})
    return {
        "integrated_loudness_lufs": integrated_loudness,
        "true_peak_dbfs": true_peak,
        "peak_dbfs": peak_dbfs,
        "clipped": clipped,
        "silence_report": silence_report,
        "dialogue_duration_seconds": dialogue_duration,
        "track_alignment": track_alignment,
        "asset_hashes": asset_hashes,
        "findings": findings,
    }


# ------------------------------------------------------------------
# QC decision (the delivery gate)
# ------------------------------------------------------------------

def qc_decision(technical_report, audio_report, *,
                editorial_approval=None):
    """Delivery gate over the technical and audio QC reports.

    Returns ``{"decision": "DELIVERY_READY"|"BLOCKED", "reasons":
    [...]}``. DELIVERY_READY only when the technical verdict is
    ``"pass"`` AND the audio report carries no critical finding
    AND ``editorial_approval`` is a non-empty reviewer name
    string from a human reviewer. The string ``"automated"`` is
    refused as approval, a missing approval blocks, and a failed
    or incomplete QC blocks delivery. There is no override flag.
    """
    reasons: list[str] = []
    tech = technical_report if isinstance(technical_report, dict) \
        else {}
    if tech.get("verdict") != "pass":
        failed = [c.get("check_id") for c in (tech.get("checks") or [])
                  if isinstance(c, dict)
                  and c.get("status") == "fail"]
        if failed:
            reasons.append("technical QC failed: "
                           + ", ".join(failed))
        else:
            reasons.append("technical QC did not pass (no verdict "
                           "or no checks recorded)")
    audio = audio_report if isinstance(audio_report, dict) else {}
    findings = audio.get("findings")
    if not isinstance(findings, list):
        reasons.append("audio QC findings are unavailable: the "
                       "audio report is incomplete")
    else:
        for finding in findings:
            if isinstance(finding, dict) \
                    and finding.get("severity") == "critical":
                reasons.append(
                    "audio QC critical finding: "
                    f"{finding.get('code') or 'unknown'} — "
                    f"{finding.get('message') or ''}".strip())
    if not isinstance(editorial_approval, str) \
            or not editorial_approval.strip():
        reasons.append("editorial approval is missing: a named "
                       "human reviewer must approve before delivery")
    elif editorial_approval.strip().lower() == "automated":
        reasons.append("editorial approval 'automated' is refused: "
                       "approval must come from a named human "
                       "reviewer, never an automated process")
    return {"decision": "DELIVERY_READY" if not reasons else "BLOCKED",
            "reasons": reasons}


__all__ = [
    "QCError",
    "QC_SCHEMA_VERSION",
    "technical_qc",
    "visual_qc",
    "audio_qc",
    "qc_decision",
]
