"""Consistency Frame P1 — sound design, mixing and audio
measurement (CF-WO-P1-006, Phase D).

Validates mix inputs against the canonical timeline, synthesizes
the reference project's music bed, room tone and whoosh SFX
locally and deterministically, builds the single voice track
from the per-line WAVs, mixes the timeline's audio tracks with
voice priority and music ducked beneath speech, measures the
result, and reports QC findings.

Synthesis is deterministic: the music bed is three sine
oscillators through FFmpeg lavfi filters, and the noise sources
are generated in-process with a fixed seed — the FFmpeg
``anoisesrc`` source has no seed option and produces different
bytes on every run, so it is never used as a source. All
filtering, envelopes and fades are FFmpeg lavfi. No network is
used anywhere.

Mixing normalizes nothing silently: gains, fades and ducking
are recorded in the mix record's ``operations``, and when the
measured peak exceeds the audio profile's true-peak target
exactly one measured volume correction is applied and recorded,
then the mix is re-measured. A failed tool run raises
:class:`production_assets.AssetError` with diagnostics instead
of producing a silent wrong mix.

Loudness and true peak come from the ``ebur128`` filter when
the installed FFmpeg provides it; when it does not, both are
reported as ``None`` honestly — never invented.
"""

from __future__ import annotations

import math
import os
import random
import re
import subprocess
import wave

from .production_assets import AssetError, probe_media_file
from .vertical_production import validate_audio_profile

# Reference sound-plan track gains (dB), in mix order. The mix
# function takes no sound plan: these are the gains the
# reference project records, stated here so the mix is
# reproducible from the timeline alone. Voice leads at 0 dB.
TRACK_GAINS_DB = {
    "dialogue": 0.0,
    "music": -18.0,
    "room-tone": -38.0,
    "sfx": -12.0,
}

# Asset type each timeline audio-track kind must resolve to.
TRACK_ASSET_TYPES = {
    "dialogue": ("audio-voice",),
    "music": ("audio-music",),
    "room-tone": ("audio-room-tone", "audio-ambience"),
    "sfx": ("audio-sfx",),
}

# Sidechain ducking for the music bed under voice. The threshold
# is -20 dB expressed in the linear scale the sidechaincompress
# filter takes (10^(-20/20) = 0.1); ratio 8:1 ducks a full-level
# voice line by roughly 12 dB (the audio profile's
# music_duck_db).
DUCK_THRESHOLD_DB = -20.0
DUCK_THRESHOLD_LINEAR = 10 ** (DUCK_THRESHOLD_DB / 20.0)
DUCK_RATIO = 8.0
DUCK_ATTACK_MS = 5
DUCK_RELEASE_MS = 250

_SILENCE_THRESHOLD_DB = -50.0
_SILENCE_MIN_SECONDS = 0.5
_LONG_SILENCE_SECONDS = 2.0


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _run_ffmpeg(argv, label, timeout_s=300) -> str:
    """Run one FFmpeg argument array; stderr on failure.

    Raises :class:`AssetError` with diagnostics on a spawn
    failure, a timeout, or a non-zero exit — never a silent
    partial output.
    """
    try:
        proc = subprocess.run(argv, capture_output=True, text=True,
                              timeout=timeout_s)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AssetError(f"{label} failed: {exc}") from exc
    if proc.returncode != 0:
        raise AssetError(
            f"{label} failed: "
            f"{(proc.stderr or proc.stdout or '').strip()[:500]}")
    return proc.stderr or ""


def _registry_by_id(assets) -> dict:
    """Normalize an asset registry (dict) or record list to a dict."""
    if isinstance(assets, dict):
        return assets
    if isinstance(assets, list):
        registry = {}
        for record in assets:
            if isinstance(record, dict) and record.get("asset_id"):
                registry[record["asset_id"]] = record
        return registry
    return {}


def _audio_tracks(timeline) -> list:
    if not isinstance(timeline, dict):
        return []
    tracks = timeline.get("audio_tracks")
    return tracks if isinstance(tracks, list) else []


def _clips_of_kind(timeline, kind) -> list:
    clips = []
    for track in _audio_tracks(timeline):
        if isinstance(track, dict) and track.get("kind") == kind:
            for clip in track.get("clips") or []:
                if isinstance(clip, dict):
                    clips.append(clip)
    return clips


def _video_clip_count(timeline) -> int:
    count = 0
    if not isinstance(timeline, dict):
        return 0
    for track in timeline.get("video_tracks") or []:
        if isinstance(track, dict):
            count += len(track.get("clips") or [])
    return count


# ------------------------------------------------------------------
# Mix-input validation
# ------------------------------------------------------------------

def validate_mix_inputs(timeline, assets, audio_profile) -> list:
    """Mix-input errors (empty list = valid).

    Validates the audio profile (sane loudness / peak / duck /
    fade values, voice priority), then the timeline's audio
    tracks against the asset registry: every audio clip must
    resolve to a registered asset of the right type; dialogue
    clips must cover every voice line exactly once (in this
    production model each shot carries exactly one dialogue
    line, so dialogue coverage is checked against the video
    track's shot count, and a repeated line id is an error);
    the mandatory music bed and SFX assets must exist (a cue
    without a registered asset is an error); every intentional
    silence must be recorded with a reason — an unrecorded
    silence is an error, never silently accepted; and no clip
    may extend past the timeline duration.
    """
    errors: list[str] = []
    errors.extend(validate_audio_profile(audio_profile))
    if not isinstance(timeline, dict):
        return errors + ["timeline: expected an object, got "
                         f"{type(timeline).__name__}"]
    registry = _registry_by_id(assets)
    duration = timeline.get("duration_seconds")
    if not _is_number(duration) or float(duration) <= 0:
        errors.append("timeline.duration_seconds must be a "
                      f"positive number, got {duration!r}")
        duration = None
    tracks = timeline.get("audio_tracks")
    if not isinstance(tracks, list) or not tracks:
        errors.append("timeline.audio_tracks must be a non-empty "
                      "list")
        return errors
    seen_line_ids: set[str] = set()
    dialogue_count = 0
    for track in tracks:
        if not isinstance(track, dict):
            errors.append("timeline audio track: expected an object")
            continue
        kind = track.get("kind")
        if kind not in TRACK_ASSET_TYPES:
            errors.append(f"audio track {track.get('track_id')!r} "
                          f"has unknown kind {kind!r}")
            continue
        for clip in track.get("clips") or []:
            if not isinstance(clip, dict):
                errors.append("audio clip: expected an object")
                continue
            clip_id = clip.get("clip_id") or clip.get("asset_id")
            asset_id = clip.get("asset_id")
            if not isinstance(asset_id, str) or not asset_id:
                errors.append(f"audio clip {clip_id!r} carries no "
                              "asset_id")
                continue
            record = registry.get(asset_id)
            if record is None:
                errors.append(
                    f"audio clip {clip_id!r} references "
                    f"unregistered asset {asset_id!r}: a missing "
                    "asset is an error, never a substitution")
                continue
            expected = TRACK_ASSET_TYPES[kind]
            if record.get("asset_type") not in expected:
                errors.append(
                    f"audio clip {clip_id!r}: asset {asset_id!r} "
                    f"has type {record.get('asset_type')!r}, "
                    f"expected {' or '.join(expected)} for a "
                    f"{kind} clip")
            start = clip.get("timeline_start_seconds")
            clip_duration = clip.get("duration_seconds")
            if not _is_number(start) or float(start) < 0:
                errors.append(f"audio clip {clip_id!r}: "
                              "timeline_start_seconds must be a "
                              f"non-negative number, got {start!r}")
            if not _is_number(clip_duration) \
                    or float(clip_duration) <= 0:
                errors.append(f"audio clip {clip_id!r}: "
                              "duration_seconds must be a positive "
                              f"number, got {clip_duration!r}")
            elif duration is not None and _is_number(start) \
                    and float(start) + float(clip_duration) \
                    > float(duration) + 0.1:
                errors.append(
                    f"audio clip {clip_id!r} ends at "
                    f"{float(start) + float(clip_duration):.2f}s, "
                    f"past the timeline duration {duration}s")
            if kind == "dialogue":
                dialogue_count += 1
                line_id = clip.get("line_id")
                if not isinstance(line_id, str) or not line_id:
                    errors.append(f"dialogue clip {clip_id!r} "
                                  "carries no line_id")
                elif line_id in seen_line_ids:
                    errors.append(
                        f"dialogue line {line_id!r} is covered by "
                        "more than one dialogue clip: each voice "
                        "line is mixed exactly once")
                else:
                    seen_line_ids.add(line_id)
    if dialogue_count == 0:
        errors.append("timeline has no dialogue clips: the "
                      "narrator leads the mix")
    else:
        shot_count = _video_clip_count(timeline)
        if shot_count and dialogue_count != shot_count:
            errors.append(
                f"dialogue clips ({dialogue_count}) do not cover "
                f"every voice line: the timeline has {shot_count} "
                "video clips (one dialogue line per shot) but "
                f"{dialogue_count} dialogue clip(s)")
    if not _clips_of_kind(timeline, "music"):
        errors.append("mandatory music bed is missing: the timeline "
                      "has no music clip")
    if not _clips_of_kind(timeline, "sfx"):
        errors.append("mandatory SFX are missing: the timeline has "
                      "no SFX clip")
    for silence in timeline.get("intentional_silences") or []:
        if not isinstance(silence, dict):
            errors.append("intentional silence: expected an object")
            continue
        silence_id = silence.get("silence_id") or "?"
        if not isinstance(silence.get("reason"), str) \
                or not silence["reason"]:
            errors.append(
                f"intentional silence {silence_id!r} is not "
                "recorded with a reason: an unrecorded silence is "
                "a defect, never silently accepted")
        if not _is_number(silence.get("duration_seconds")) \
                or float(silence.get("duration_seconds") or 0) <= 0:
            errors.append(f"intentional silence {silence_id!r} "
                          "needs a positive duration_seconds")
    return errors


# ------------------------------------------------------------------
# Deterministic synthesis (FFmpeg lavfi + fixed-seed noise)
# ------------------------------------------------------------------

def _write_pcm16_wav(path, samples, sample_rate) -> None:
    """Write mono float samples as a stereo 16-bit WAV."""
    import struct

    frames = b"".join(
        struct.pack("<hh",
                    max(-32768, min(32767, int(round(s * 32767)))),
                    max(-32768, min(32767, int(round(s * 32767)))))
        for s in samples)
    with wave.open(path, "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(frames)


def _normalize_peak(samples, peak=1.0) -> list:
    top = max((abs(s) for s in samples), default=0.0)
    if top <= 0:
        return samples
    return [s * peak / top for s in samples]


def _brown_noise_samples(count, seed=42) -> list:
    """Deterministic brown noise (leaky integrator, fixed seed)."""
    rng = random.Random(seed)
    samples = []
    last = 0.0
    for _ in range(count):
        white = rng.uniform(-1.0, 1.0)
        last = (last + 0.02 * white) / 1.02
        samples.append(last * 3.5)
    return _normalize_peak(samples, 1.0)


def _pink_noise_samples(count, seed=42) -> list:
    """Deterministic pink noise (Paul Kellet filter, fixed seed)."""
    rng = random.Random(seed)
    b = [0.0] * 7
    samples = []
    for _ in range(count):
        white = rng.uniform(-1.0, 1.0)
        b[0] = 0.99886 * b[0] + white * 0.0555179
        b[1] = 0.99332 * b[1] + white * 0.0750759
        b[2] = 0.96900 * b[2] + white * 0.1538520
        b[3] = 0.86650 * b[3] + white * 0.3104856
        b[4] = 0.55000 * b[4] + white * 0.5329522
        b[5] = -0.7616 * b[5] - white * 0.0168980
        pink = (b[0] + b[1] + b[2] + b[3] + b[4] + b[5] + b[6]
                + white * 0.5362)
        b[6] = white * 0.115926
        samples.append(pink)
    return _normalize_peak(samples, 0.9)


def _check_synthesized(path, duration_seconds, label,
                       ffprobe="ffprobe") -> float:
    """Probe a synthesized file; fail closed on a wrong result."""
    probe = probe_media_file(path, ffprobe=ffprobe)
    if not probe["audio_streams"]:
        raise AssetError(f"{label}: synthesized file has no audio "
                         "stream")
    if probe["sample_rate"] != 48000:
        raise AssetError(f"{label}: synthesized file is "
                         f"{probe['sample_rate']} Hz, expected "
                         "48000 Hz")
    measured = probe["duration_seconds"]
    if measured is None or abs(measured - float(duration_seconds)) \
            > 0.1:
        raise AssetError(f"{label}: synthesized duration "
                         f"{measured}, expected {duration_seconds}")
    return measured


def synthesize_music_bed(duration_seconds, output_path, *,
                         sample_rate=48000, ffmpeg="ffmpeg",
                         ffprobe="ffprobe") -> tuple:
    """Synthesize a soft chord-pad music bed (C3/E3/G3).

    Three sine oscillators mixed, lowpassed, with a slow
    amplitude swell and fades in/out — FFmpeg lavfi only, no
    randomness, no network. Returns ``(path, duration_seconds)``.
    The file is a 48 kHz stereo WAV verifiable by
    :func:`production_assets.probe_media_file`; the caller
    registers it with source ``"synthesized"``.
    """
    if not _is_number(duration_seconds) \
            or float(duration_seconds) <= 0:
        raise AssetError("music bed duration must be a positive "
                         f"number, got {duration_seconds!r}")
    duration = float(duration_seconds)
    fade_in = min(1.0, duration / 4.0)
    fade_out = min(1.5, duration / 4.0)
    sources = []
    for freq in (130.81, 164.81, 196.00):
        sources += ["-f", "lavfi", "-i",
                    f"sine=frequency={freq}:duration={duration}:"
                    f"sample_rate={sample_rate}"]
    filters = (
        "amix=inputs=3:normalize=1,lowpass=f=1200,"
        f"volume='0.65+0.35*sin(2*PI*t/{duration})':eval=frame,"
        f"afade=t=in:st=0:d={fade_in},"
        f"afade=t=out:st={duration - fade_out}:d={fade_out}")
    argv = [ffmpeg, "-y", "-v", "error", *sources,
            "-filter_complex", filters,
            "-ar", str(sample_rate), "-ac", "2",
            "-c:a", "pcm_s16le", "-t", str(duration), output_path]
    _run_ffmpeg(argv, "music bed synthesis")
    measured = _check_synthesized(output_path, duration,
                                  "music bed", ffprobe=ffprobe)
    return output_path, measured


def synthesize_room_tone(duration_seconds, output_path, *,
                         sample_rate=48000, ffmpeg="ffmpeg",
                         ffprobe="ffprobe") -> tuple:
    """Synthesize low-level brown-noise room tone.

    The noise samples are generated deterministically in-process
    (fixed seed 42) because the FFmpeg noise source has no seed
    and varies run to run; the level and fades are FFmpeg lavfi.
    Returns ``(path, duration_seconds)``; 48 kHz stereo WAV,
    source ``"synthesized"``.
    """
    if not _is_number(duration_seconds) \
            or float(duration_seconds) <= 0:
        raise AssetError("room tone duration must be a positive "
                         f"number, got {duration_seconds!r}")
    duration = float(duration_seconds)
    count = int(round(duration * sample_rate))
    source_path = output_path + ".noise-src.wav"
    try:
        _write_pcm16_wav(source_path,
                         _brown_noise_samples(count), sample_rate)
        fade = min(0.1, duration / 4.0)
        argv = [ffmpeg, "-y", "-v", "error", "-i", source_path,
                "-af",
                f"volume=0.05,afade=t=in:st=0:d={fade},"
                f"afade=t=out:st={duration - fade}:d={fade}",
                "-ar", str(sample_rate), "-ac", "2",
                "-c:a", "pcm_s16le", "-t", str(duration), output_path]
        _run_ffmpeg(argv, "room tone synthesis")
    finally:
        if os.path.exists(source_path):
            os.remove(source_path)
    measured = _check_synthesized(output_path, duration,
                                  "room tone", ffprobe=ffprobe)
    return output_path, measured


def synthesize_whoosh(duration_seconds, output_path, *,
                      sample_rate=48000, ffmpeg="ffmpeg",
                      ffprobe="ffprobe") -> tuple:
    """Synthesize a whoosh SFX: bandpassed pink noise, rise-fall.

    Deterministic fixed-seed pink noise through an FFmpeg lavfi
    bandpass and a rise-then-fall volume envelope. Returns
    ``(path, duration_seconds)``; 48 kHz stereo WAV, source
    ``"synthesized"``.
    """
    if not _is_number(duration_seconds) \
            or float(duration_seconds) <= 0:
        raise AssetError("whoosh duration must be a positive "
                         f"number, got {duration_seconds!r}")
    duration = float(duration_seconds)
    count = int(round(duration * sample_rate))
    source_path = output_path + ".noise-src.wav"
    try:
        _write_pcm16_wav(source_path,
                         _pink_noise_samples(count), sample_rate)
        argv = [ffmpeg, "-y", "-v", "error", "-i", source_path,
                "-af",
                "bandpass=f=900:width_type=q:width=1.5,"
                f"volume='0.9*sin(PI*t/{duration})':eval=frame",
                "-ar", str(sample_rate), "-ac", "2",
                "-c:a", "pcm_s16le", "-t", str(duration), output_path]
        _run_ffmpeg(argv, "whoosh synthesis")
    finally:
        if os.path.exists(source_path):
            os.remove(source_path)
    measured = _check_synthesized(output_path, duration,
                                  "whoosh", ffprobe=ffprobe)
    return output_path, measured


# ------------------------------------------------------------------
# Voice track
# ------------------------------------------------------------------

def build_voice_track(line_paths, *, pause_after_seconds,
                      lead_in_seconds, sample_rate=48000,
                      ffmpeg="ffmpeg", out_path) -> str:
    """Concatenate line WAVs into one voice track.

    Layout is ``[lead-in silence, line1, pause, line2, pause,
    ...]`` — one pause after every line, including the last.
    Every input is resampled to ``sample_rate`` and converted to
    stereo before the concat filter, so mixed-rate/mono line
    files concatenate cleanly. Returns ``out_path`` (a 48 kHz
    stereo WAV). Raises :class:`AssetError` when an input is
    missing or FFmpeg fails, or when the output duration does
    not match the expected total.
    """
    if not _is_number(pause_after_seconds) \
            or float(pause_after_seconds) < 0:
        raise AssetError("pause_after_seconds must be a "
                         "non-negative number, "
                         f"got {pause_after_seconds!r}")
    if not _is_number(lead_in_seconds) or float(lead_in_seconds) < 0:
        raise AssetError("lead_in_seconds must be a non-negative "
                         f"number, got {lead_in_seconds!r}")
    if not isinstance(line_paths, list):
        raise AssetError("line_paths must be a list")
    for path in line_paths:
        if not os.path.isfile(path):
            raise AssetError(f"voice line file {path!r} does not "
                             "exist")
    inputs: list[str] = []
    filters: list[str] = []
    n_inputs = [0]

    def _add_silence(seconds):
        index = n_inputs[0]
        n_inputs[0] += 1
        inputs.extend(["-f", "lavfi", "-i",
                       f"anullsrc=r={sample_rate}:cl=stereo:"
                       f"d={seconds}"])
        filters.append(f"[{index}:a]aformat=channel_layouts=stereo,"
                       f"asetpts=PTS-STARTPTS[a{index}]")
        return seconds

    def _add_file(path):
        index = n_inputs[0]
        n_inputs[0] += 1
        inputs.extend(["-i", path])
        filters.append(
            f"[{index}:a]aresample={sample_rate},"
            "aformat=channel_layouts=stereo,"
            f"asetpts=PTS-STARTPTS[a{index}]")
        return None

    expected = 0.0
    if float(lead_in_seconds) > 0:
        expected += _add_silence(float(lead_in_seconds))
    for path in line_paths:
        _add_file(path)
        if float(pause_after_seconds) > 0:
            expected += _add_silence(float(pause_after_seconds))
    if not filters:
        # No lines and no lead-in: a zero-length track is a
        # defect, not a voice track.
        raise AssetError("voice track needs at least one line or a "
                         "lead-in")
    # Expected duration: lead-in + pauses + line durations.
    for path in line_paths:
        with wave.open(path, "rb") as wav:
            frames = wav.getnframes()
            rate = wav.getframerate()
            expected += frames / rate if rate else 0.0
    concat = "".join(f"[a{i}]" for i in range(len(filters)))
    filters.append(f"{concat}concat=n={len(filters)}:v=0:a=1[out]")
    argv = [ffmpeg, "-y", "-v", "error", *inputs,
            "-filter_complex", ",".join(filters),
            "-map", "[out]", "-c:a", "pcm_s16le",
            "-ar", str(sample_rate), "-ac", "2", out_path]
    _run_ffmpeg(argv, "voice track build")
    probe = probe_media_file(out_path)
    if probe["duration_seconds"] is None \
            or abs(probe["duration_seconds"] - expected) > 0.15:
        raise AssetError(
            f"voice track duration {probe['duration_seconds']}, "
            f"expected {expected:.2f}")
    return out_path


# ------------------------------------------------------------------
# Measurement
# ------------------------------------------------------------------

def _parse_float(text, pattern, default=None):
    match = re.search(pattern, text or "")
    if not match:
        return default
    try:
        return float(match.group(1))
    except (TypeError, ValueError):
        return default


def measure_audio(path, *, ffmpeg="ffmpeg",
                  ffprobe="ffprobe") -> dict:
    """Measure one audio file.

    Returns ``{duration_seconds, sample_rate, channels,
    peak_dbfs, loudness_lufs, true_peak_dbfs, clipped,
    silences}`` where ``peak_dbfs`` is the volumedetect
    maximum, loudness/true-peak come from the ``ebur128``
    filter's Summary section (``None`` when that filter is
    unavailable — recorded honestly, never invented),
    ``clipped`` is true when a sustained run of samples sits
    at full scale (this FFmpeg's astats reports no "Clip
    count" field, so clipping is detected from its Peak count
    — samples at the peak level — at a 0 dB peak: a sustained
    rail is clipping, an isolated peak sample is not), and
    ``silences`` are ``[{start, end, duration}]`` from
    silencedetect at -50 dB with a 0.5 s minimum. Raises
    :class:`AssetError` on tool failure with diagnostics.
    """
    probe = probe_media_file(path, ffprobe=ffprobe)
    if not probe["audio_streams"]:
        raise AssetError(f"measure_audio: {path!r} has no audio "
                         "stream")
    duration = probe["duration_seconds"]
    if duration is None:
        raise AssetError(f"measure_audio: {path!r} has no known "
                         "duration")

    def _run(args, label):
        try:
            proc = subprocess.run(
                args, capture_output=True, text=True, timeout=300)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AssetError(f"{label} failed for {path!r}: "
                             f"{exc}") from exc
        if proc.returncode != 0:
            raise AssetError(
                f"{label} failed for {path!r}: "
                f"{(proc.stderr or proc.stdout or '').strip()[:500]}")
        return proc.stderr or ""

    peak_text = _run([ffmpeg, "-v", "info", "-i", path,
                      "-af", "volumedetect", "-vn", "-sn", "-dn",
                      "-f", "null", "-"],
                     "volumedetect")
    peak = _parse_float(peak_text, r"max_volume:\s*(-?[0-9.]+)\s*dB")
    ebur_text = None
    loudness = None
    true_peak = None
    try:
        ebur_text = _run([ffmpeg, "-v", "info", "-i", path,
                          "-af", "ebur128=peak=true",
                          "-f", "null", "-"], "ebur128")
    except AssetError as exc:
        if "No such filter" not in "; ".join(exc.errors):
            raise
        # ebur128 unavailable: loudness and true peak stay None,
        # recorded honestly.
    if ebur_text is not None:
        # Parse the Summary section only: the per-frame lines
        # report gated warm-up values (e.g. I: -70 LUFS early
        # on), not the integrated result.
        summary = ebur_text.rsplit("Summary:", 1)[-1]
        loudness = _parse_float(
            summary, r"I:\s*(-?[0-9.]+)\s*LUFS")
        true_peak = _parse_float(
            summary, r"Peak:\s*(-?[0-9.]+)\s*dB(?:TP|FS)")
    astats_text = _run([ffmpeg, "-v", "info", "-i", path,
                        "-af", "astats", "-f", "null", "-"],
                       "astats")
    # This FFmpeg's astats prints no "Clip count" field. The
    # Overall section's Peak count is the number of samples at
    # the peak level: a sustained rail at a 0 dB peak is
    # clipping; the isolated peak samples of a clean signal are
    # a fraction of a percent and are not.
    peak_counts = [float(n) for n in re.findall(
        r"Peak count:\s*([0-9.]+)", astats_text)]
    sample_counts = [float(n) for n in re.findall(
        r"Number of samples:\s*([0-9.]+)", astats_text)]
    peak_level = _parse_float(astats_text,
                              r"Peak level dB:\s*(-?[0-9.]+)")
    clipped = False
    if peak_counts and sample_counts and peak_level is not None:
        ratio = peak_counts[-1] / sample_counts[-1] \
            if sample_counts[-1] else 0.0
        clipped = peak_level >= -0.05 and ratio > 0.005
    silence_text = _run(
        [ffmpeg, "-v", "info", "-i", path, "-af",
         f"silencedetect=noise={_SILENCE_THRESHOLD_DB}dB:"
         f"d={_SILENCE_MIN_SECONDS}", "-f", "null", "-"],
        "silencedetect")
    silences: list[dict] = []
    pending_start = None
    for line in silence_text.splitlines():
        start = _parse_float(line, r"silence_start:\s*([0-9.]+)")
        if start is not None:
            pending_start = start
            continue
        end = _parse_float(line, r"silence_end:\s*([0-9.]+)")
        if end is not None and pending_start is not None:
            silences.append({
                "start": pending_start,
                "end": end,
                "duration": round(end - pending_start, 3)})
            pending_start = None
    if pending_start is not None:
        silences.append({
            "start": pending_start,
            "end": duration,
            "duration": round(duration - pending_start, 3)})
    return {
        "duration_seconds": duration,
        "sample_rate": probe["sample_rate"],
        "channels": probe["channels"],
        "peak_dbfs": peak,
        "loudness_lufs": loudness,
        "true_peak_dbfs": true_peak,
        "clipped": clipped,
        "silences": silences,
    }


# ------------------------------------------------------------------
# Mixing
# ------------------------------------------------------------------

def _bus_filters(clips, asset_paths, gain_db, start_index, prefix,
                 sample_rate=48000):
    """Filter labels for one bus: (inputs, filters, bus label).

    Each clip is gained, converted to 48 kHz stereo, delayed to
    its timeline position and time-based; the bus is the clip
    itself, or an amix of several clips. ``start_index`` is the
    global input number of the first clip and ``prefix`` makes
    the filter labels unique across buses.
    """
    inputs: list[str] = []
    filters: list[str] = []
    labels: list[str] = []
    for index, clip in enumerate(clips):
        asset_id = clip["asset_id"]
        path = asset_paths.get(asset_id)
        if path is None:
            raise AssetError(
                f"mix: no file path for asset {asset_id!r} "
                f"(clip {clip.get('clip_id')!r})")
        if not os.path.isfile(path):
            raise AssetError(
                f"mix: asset file {path!r} for asset "
                f"{asset_id!r} does not exist")
        inputs += ["-i", path]
        delay_ms = int(round(
            float(clip.get("timeline_start_seconds") or 0) * 1000))
        label = f"{prefix}{index}"
        filters.append(
            f"[{start_index + index}:a]aresample={sample_rate},"
            "aformat=channel_layouts=stereo,"
            f"volume={gain_db}dB,"
            f"adelay={delay_ms}|{delay_ms},"
            f"asetpts=PTS-STARTPTS[{label}]")
        labels.append(label)
    return inputs, filters, labels


def _mix_argv(timeline, asset_paths, audio_profile, output_path,
              *, ffmpeg, correction_db=None):
    """FFmpeg argument array for one mix pass (pure builder)."""
    duration = float(timeline["duration_seconds"])
    fade_in = float(audio_profile.get("fade_in_seconds") or 0)
    fade_out = float(audio_profile.get("fade_out_seconds") or 0)
    inputs: list[str] = []
    filters: list[str] = []
    buses: list[str] = []
    operations: list[str] = []
    voice_clips = _clips_of_kind(timeline, "dialogue")
    music_clips = _clips_of_kind(timeline, "music")
    room_clips = _clips_of_kind(timeline, "room-tone")
    sfx_clips = _clips_of_kind(timeline, "sfx")

    def _bus(clips, kind, tag):
        nonlocal inputs, filters
        if not clips:
            return None
        start_index = len(inputs) // 2
        kind_inputs, kind_filters, labels = _bus_filters(
            clips, asset_paths, TRACK_GAINS_DB[kind], start_index,
            tag)
        inputs += kind_inputs
        filters += kind_filters
        if len(labels) == 1:
            return labels[0]
        bus_label = f"{tag}bus"
        filters.append(
            "".join(f"[{label}]" for label in labels)
            + f"amix=inputs={len(labels)}:normalize=0[{bus_label}]")
        return bus_label

    voice_bus = _bus(voice_clips, "dialogue", "voice")
    music_bus = _bus(music_clips, "music", "music")
    room_bus = _bus(room_clips, "room-tone", "room")
    sfx_bus = _bus(sfx_clips, "sfx", "sfx")
    if voice_bus:
        operations.append(
            f"voice: gain {TRACK_GAINS_DB['dialogue']:.1f} dB "
            f"(priority), {len(voice_clips)} clip(s)")
    if music_bus:
        duck_db = audio_profile.get("music_duck_db")
        if voice_bus:
            filters.append(
                f"[{music_bus}][{voice_bus}]sidechaincompress="
                f"threshold={DUCK_THRESHOLD_LINEAR}:ratio={DUCK_RATIO}:"
                f"attack={DUCK_ATTACK_MS}:release={DUCK_RELEASE_MS}:"
                "makeup=1:mix=1[musicducked]")
            music_bus = "musicducked"
            operations.append(
                f"music: gain {TRACK_GAINS_DB['music']:.1f} dB, "
                "ducked under voice (sidechaincompress threshold "
                f"{DUCK_THRESHOLD_DB:.0f} dB, ratio {DUCK_RATIO:.0f}:1, "
                f"target duck {duck_db} dB)")
        else:
            operations.append(
                f"music: gain {TRACK_GAINS_DB['music']:.1f} dB "
                "(no voice bus, so no ducking applied)")
    if room_bus:
        operations.append(
            f"room-tone: gain {TRACK_GAINS_DB['room-tone']:.1f} dB, "
            f"{len(room_clips)} clip(s)")
    if sfx_bus:
        operations.append(
            f"sfx: gain {TRACK_GAINS_DB['sfx']:.1f} dB, "
            f"{len(sfx_clips)} cue(s) at timeline positions")
    final_inputs = [b for b in (voice_bus, music_bus, room_bus,
                                sfx_bus) if b]
    if not final_inputs:
        raise AssetError("mix: the timeline has no audio clips to "
                         "mix")
    if len(final_inputs) == 1:
        mixed = final_inputs[0]
    else:
        mixed = "mixed"
        filters.append(
            "".join(f"[{label}]" for label in final_inputs)
            + f"amix=inputs={len(final_inputs)}:normalize=0[{mixed}]")
    chain = [mixed]
    if correction_db is not None:
        filters.append(
            f"[{mixed}]volume={correction_db:.2f}dB[corrected]")
        chain = ["corrected"]
    if fade_in > 0:
        filters.append(
            f"[{chain[-1]}]afade=t=in:st=0:d={fade_in}[faded]")
        chain = ["faded"]
    if fade_out > 0 and fade_out < duration:
        filters.append(
            f"[{chain[-1]}]afade=t=out:st={duration - fade_out}:"
            f"d={fade_out}[fadedout]")
        chain = ["fadedout"]
    filters.append(
        f"[{chain[-1]}]atrim=0:{duration},"
        f"asetpts=PTS-STARTPTS[out]")
    operations.append(
        f"fades: in {fade_in}s, out {fade_out}s; output 48 kHz "
        f"stereo WAV, timeline duration {duration}s")
    argv = [ffmpeg, "-y", "-v", "error", *inputs,
            "-filter_complex", ",".join(filters),
            "-map", "[out]", "-c:a", "pcm_s16le",
            "-ar", "48000", "-ac", "2", "-t", str(duration),
            output_path]
    return argv, operations


def mix_audio(timeline, asset_paths, audio_profile, output_path, *,
              ffmpeg="ffmpeg", ffprobe="ffprobe") -> dict:
    """Mix the timeline's audio tracks into one WAV.

    Voice (gain 0 dB, priority) + music bed ducked beneath
    speech (sidechain compression keyed on the voice bus) +
    room tone + SFX clips at their timeline positions, with the
    audio profile's fades in/out. Returns a mix record
    ``{path, duration_seconds, peak_dbfs, loudness_lufs,
    true_peak_dbfs, clipped, operations}`` with every gain,
    fade and ducking step recorded in ``operations``.

    Nothing is normalized silently: when the measured peak
    exceeds the profile's ``target_true_peak_dbfs``, exactly
    one measured volume correction is applied (recorded in
    ``operations``) and the mix is re-measured. Raises
    :class:`AssetError` when a clip's file is missing or a tool
    run fails.
    """
    profile_errors = validate_audio_profile(audio_profile)
    if profile_errors:
        raise AssetError(["mix audio_profile:"] + profile_errors)
    if not isinstance(timeline, dict) \
            or not _is_number(timeline.get("duration_seconds")):
        raise AssetError("mix: timeline needs a duration_seconds")
    if not isinstance(asset_paths, dict):
        raise AssetError("mix: asset_paths must be an "
                         "{asset_id: path} mapping")
    argv, operations = _mix_argv(timeline, asset_paths,
                                 audio_profile, output_path,
                                 ffmpeg=ffmpeg)
    _run_ffmpeg(argv, "audio mix")
    measured = measure_audio(output_path, ffmpeg=ffmpeg,
                             ffprobe=ffprobe)
    target = audio_profile.get("target_true_peak_dbfs")
    peak = measured.get("peak_dbfs")
    if _is_number(target) and peak is not None \
            and peak > float(target):
        correction_db = float(target) - float(peak)
        operations.append(
            f"volume correction {correction_db:.2f} dB: measured "
            f"peak {peak:.2f} dBFS exceeded the target true peak "
            f"{float(target):.2f} dBFS; one measured correction "
            "applied, then re-measured")
        argv, _retry_ops = _mix_argv(
            timeline, asset_paths, audio_profile, output_path,
            ffmpeg=ffmpeg, correction_db=correction_db)
        _run_ffmpeg(argv, "audio mix (corrected)")
        measured = measure_audio(output_path, ffmpeg=ffmpeg,
                                 ffprobe=ffprobe)
    return {
        "path": output_path,
        "duration_seconds": measured["duration_seconds"],
        "peak_dbfs": measured["peak_dbfs"],
        "loudness_lufs": measured["loudness_lufs"],
        "true_peak_dbfs": measured["true_peak_dbfs"],
        "clipped": measured["clipped"],
        "operations": operations,
    }


# ------------------------------------------------------------------
# QC findings
# ------------------------------------------------------------------

def _intentional_window(entry) -> tuple | None:
    """(start, end) for an intentional-silence entry, or None."""
    if not isinstance(entry, dict):
        return None
    start = entry.get("timeline_start_seconds", entry.get("start"))
    duration = entry.get("duration_seconds", entry.get("duration"))
    end = entry.get("timeline_end_seconds", entry.get("end"))
    if _is_number(start) and _is_number(duration):
        return (float(start), float(start) + float(duration))
    if _is_number(start) and _is_number(end):
        return (float(start), float(end))
    return None


def _silence_is_intentional(silence, intentional_silences) -> bool:
    """True when at least half of a measured silence is covered."""
    start = silence.get("start")
    end = silence.get("end")
    if not _is_number(start) or not _is_number(end):
        return False
    span = float(end) - float(start)
    if span <= 0:
        return False
    for entry in intentional_silences or []:
        window = _intentional_window(entry)
        if window is None:
            continue
        overlap = max(0.0, min(float(end), window[1])
                      - max(float(start), window[0]))
        if overlap >= 0.5 * span:
            return True
    return False


def audio_qc_findings(measured, timeline, voice_lines, audio_profile,
                      intentional_silences) -> list:
    """QC findings for a measured mix.

    Returns finding dicts ``{severity, check, detail}`` with
    severity ``critical`` / ``major`` / ``minor``. Checks:
    clipped audio; missing dialogue (a voice line with no
    dialogue clip, or a voice track shorter than the dialogue
    span); empty audio file; unexpected long silence (over
    2.0 s, not covered by ``intentional_silences``); misaligned
    voice clips (the last dialogue end past the measured
    duration); missing mandatory music / SFX (a track with no
    clips, or a clip flagged as missing its asset file); audio
    extending beyond the timeline duration. Intentional
    silences produce no finding.
    """
    findings: list[dict] = []

    def _add(severity, check, detail):
        findings.append({"severity": severity, "check": check,
                         "detail": detail})

    if not isinstance(measured, dict):
        _add("critical", "empty-audio",
             "no audio measurement is available: the mix produced "
             "no measurable audio")
        return findings
    duration = measured.get("duration_seconds")
    if duration is None or float(duration) <= 0:
        _add("critical", "empty-audio",
             "measured audio duration is "
             f"{duration!r}: the mix is empty")
        return findings
    if measured.get("clipped"):
        _add("critical", "clipped-audio",
             "the mix contains clipped samples (a sustained run "
             "of samples at full scale): reduce a gain or re-mix "
             "with a volume correction")
    timeline = timeline if isinstance(timeline, dict) else {}
    timeline_duration = timeline.get("duration_seconds")
    dialogue_clips = _clips_of_kind(timeline, "dialogue")
    line_ids = set()
    if isinstance(voice_lines, list):
        for entry in voice_lines:
            if isinstance(entry, dict) and entry.get("line_id"):
                line_ids.add(entry["line_id"])
            elif isinstance(entry, str) and entry:
                line_ids.add(entry)
    covered = {c.get("line_id") for c in dialogue_clips
               if isinstance(c.get("line_id"), str)}
    for line_id in sorted(line_ids):
        if line_id not in covered:
            _add("critical", "missing-dialogue",
                 f"voice line {line_id!r} has no dialogue clip in "
                 "the timeline: required dialogue is missing")
    last_dialogue_end = None
    for clip in dialogue_clips:
        start = clip.get("timeline_start_seconds")
        clip_duration = clip.get("duration_seconds")
        if _is_number(start) and _is_number(clip_duration):
            end = float(start) + float(clip_duration)
            last_dialogue_end = end if last_dialogue_end is None \
                else max(last_dialogue_end, end)
    if last_dialogue_end is not None \
            and last_dialogue_end > float(duration) + 0.05:
        _add("major", "voice-alignment",
             f"the voice track ({float(duration):.2f}s) is shorter "
             f"than the dialogue span (last dialogue ends at "
             f"{last_dialogue_end:.2f}s): a voice clip is "
             "misaligned or truncated")
    for silence in measured.get("silences") or []:
        silence_duration = silence.get("duration")
        if _is_number(silence_duration) \
                and float(silence_duration) > _LONG_SILENCE_SECONDS \
                and not _silence_is_intentional(
                    silence, intentional_silences):
            _add("major", "unexpected-silence",
                 f"unexpected silence of "
                 f"{float(silence_duration):.2f}s at "
                 f"{silence.get('start')}s: longer than "
                 f"{_LONG_SILENCE_SECONDS:.1f}s and not recorded "
                 "as intentional")
    for kind, check in (("music", "missing-music"),
                        ("sfx", "missing-sfx")):
        clips = _clips_of_kind(timeline, kind)
        if not clips:
            _add("major", check,
                 f"the timeline has no {kind} clip: mandatory "
                 f"{kind} is missing")
            continue
        for clip in clips:
            if clip.get("asset_missing"):
                _add("major", check,
                     f"{kind} clip {clip.get('clip_id')!r} "
                     f"(asset {clip.get('asset_id')!r}) has no "
                     "asset file: mandatory asset is missing")
    if _is_number(timeline_duration) \
            and float(duration) > float(timeline_duration) + 0.1:
        _add("major", "audio-overrun",
             f"measured audio ({float(duration):.2f}s) extends "
             f"beyond the timeline duration "
             f"({float(timeline_duration):.2f}s)")
    return findings


__all__ = [
    "TRACK_GAINS_DB",
    "validate_mix_inputs",
    "synthesize_music_bed",
    "synthesize_room_tone",
    "synthesize_whoosh",
    "build_voice_track",
    "measure_audio",
    "mix_audio",
    "audio_qc_findings",
]
