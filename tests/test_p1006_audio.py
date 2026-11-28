#!/usr/bin/env python3
"""Audio stage tests (CF-WO-P1-006, Phase D).

Covers mix-input validation, deterministic synthesis, voice
track building, mixing with music ducked under voice,
measurement, and QC findings.

FFmpeg/ffprobe are REQUIRED: when they are absent the suite
fails (exit 1) instead of skipping. All generated media lives
in tempfile dirs.
"""

import copy
import math
import os
import shutil
import struct
import sys
import tempfile
import wave

ROOT = os.path.join(os.path.dirname(__file__), "..")
ROOT_ABS = os.path.abspath(ROOT)
sys.path.insert(0, ROOT)
from runtime.production_assets import (  # noqa: E402
    AssetError, new_asset_record, probe_media_file)
from runtime.production_audio import (  # noqa: E402
    audio_qc_findings, build_voice_track, measure_audio, mix_audio,
    synthesize_music_bed, synthesize_room_tone, synthesize_whoosh,
    validate_mix_inputs)

failures = []
_checks = [0]


def check(name, cond, detail=""):
    _checks[0] += 1
    if cond:
        print(f"PASS {name}")
    else:
        print(f"FAIL {name} {detail}")
        failures.append(name)


def expect_error(label, fn):
    try:
        fn()
    except AssetError:
        check(label, True)
        return
    except Exception as exc:  # noqa: BLE001 - any other error fails
        check(label, False, f"raised {type(exc).__name__}: {exc}")
        return
    check(label, False, "operation succeeded instead of refusing")


AUDIO_PROFILE = {
    "id": "test-audio-profile",
    "target_loudness_lufs": -16.0,
    "target_true_peak_dbfs": -1.0,
    "voice_priority": True,
    "music_duck_db": -12.0,
    "fade_in_seconds": 0.5,
    "fade_out_seconds": 1.0,
}


def make_record(asset_id, asset_type, project_id="proj-audio-001"):
    return new_asset_record(
        asset_id=asset_id, project_id=project_id, shot_id="s1",
        asset_type=asset_type,
        provider="ffmpeg-local", provider_status="EXERCISED",
        path=f"{asset_id}.wav", mime_type="audio/wav",
        license_class="original", privacy_class="internal",
        transmit_to_provider=False,
        provenance="INFERRED_FOR_PRODUCTION")


def make_timeline(duration=6.0, voice_lines=("l1", "l2", "l3"),
                  music=True, sfx=True, room_tone=True,
                  silence_reason=True):
    """Canonical test timeline: 3 video clips, dialogue + beds."""
    voice_clips = []
    for index, line_id in enumerate(voice_lines):
        voice_clips.append({
            "clip_id": f"voice-{line_id}", "asset_id": f"voice-{line_id}",
            "line_id": line_id, "shot_id": f"s{index + 1}",
            "timeline_start_seconds": float(index * 2),
            "duration_seconds": 1.5})
    audio_tracks = [{"track_id": "voice", "kind": "dialogue",
                     "clips": voice_clips}]
    if music:
        audio_tracks.append({
            "track_id": "music", "kind": "music",
            "clips": [{"clip_id": "music-bed",
                       "asset_id": "music-bed",
                       "timeline_start_seconds": 0.0,
                       "duration_seconds": duration}]})
    if room_tone:
        audio_tracks.append({
            "track_id": "room-tone", "kind": "room-tone",
            "clips": [{"clip_id": "room-tone",
                       "asset_id": "room-tone",
                       "timeline_start_seconds": 0.0,
                       "duration_seconds": duration}]})
    if sfx:
        audio_tracks.append({
            "track_id": "sfx", "kind": "sfx",
            "clips": [{"clip_id": "sfx-whoosh-s2",
                       "asset_id": "sfx-whoosh",
                       "cue_id": "sfx-whoosh-s2", "shot_id": "s2",
                       "timeline_start_seconds": 2.0,
                       "duration_seconds": 0.8}]})
    silences = [{
        "silence_id": "tail-out", "timeline_start_seconds": 4.5,
        "duration_seconds": 1.5,
        "reason": "Music tail-out under the end card; not a defect."
        if silence_reason else ""}]
    return {
        "schema_version": "2.5", "id": "timeline-test-001",
        "project_id": "proj-audio-001",
        "format": "editor_neutral_v1",
        "output_profile": {},
        "duration_seconds": duration,
        "video_tracks": [{"track_id": "v1", "clips": [
            {"clip_id": f"v{i}", "asset_id": f"shot-s{i}",
             "shot_id": f"s{i}", "source_start_seconds": 0.0,
             "source_end_seconds": 2.0,
             "timeline_start_seconds": float((i - 1) * 2),
             "duration_seconds": 2.0, "operations": []}
            for i in (1, 2, 3)]}],
        "audio_tracks": audio_tracks,
        "transitions": [],
        "intentional_silences": silences,
        "provenance": {},
    }


def make_registry():
    return {
        "voice-l1": make_record("voice-l1", "audio-voice"),
        "voice-l2": make_record("voice-l2", "audio-voice"),
        "voice-l3": make_record("voice-l3", "audio-voice"),
        "music-bed": make_record("music-bed", "audio-music"),
        "room-tone": make_record("room-tone", "audio-room-tone"),
        "sfx-whoosh": make_record("sfx-whoosh", "audio-sfx"),
    }


def make_tone_wav(path, seconds=1.0, freq=440.0, rate=48000,
                  amplitude=0.5, channels=1):
    count = int(round(seconds * rate))
    frames = bytearray()
    for n in range(count):
        value = int(round(
            amplitude * 32767
            * math.sin(2 * math.pi * freq * n / rate)))
        for _ in range(channels):
            frames += struct.pack("<h", value)
    with wave.open(path, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(bytes(frames))
    return path


def make_clipped_wav(path, seconds=1.0, rate=48000):
    count = int(round(seconds * rate))
    frames = bytearray()
    for n in range(count):
        value = 1.5 * math.sin(2 * math.pi * 440 * n / rate)
        clipped = max(-1.0, min(1.0, value))
        frames += struct.pack("<h", int(round(clipped * 32767)))
    with wave.open(path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(bytes(frames))
    return path


def make_silence_gap_wav(path, rate=48000):
    """1 s tone, 3 s silence, 1 s tone."""
    frames = bytearray()
    for n in range(5 * rate):
        second = n // rate
        if second in (0, 4):
            value = int(round(0.5 * 32767
                              * math.sin(2 * math.pi * 440 * n / rate)))
        else:
            value = 0
        frames += struct.pack("<h", value)
    with wave.open(path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(bytes(frames))
    return path


def read_samples(path):
    """(rate, channels, [float samples, interleaved])."""
    with wave.open(path, "rb") as wav:
        rate = wav.getframerate()
        channels = wav.getnchannels()
        frames = wav.getnframes()
        raw = wav.readframes(frames)
    count = len(raw) // 2
    values = struct.unpack(f"<{count}h", raw)
    return rate, channels, [v / 32768.0 for v in values]


def rms_in_window(path, start, end):
    rate, channels, samples = read_samples(path)
    mono = samples[0::channels]
    lo = int(start * rate)
    hi = int(end * rate)
    window = mono[lo:hi]
    if not window:
        return 0.0
    return math.sqrt(sum(v * v for v in window) / len(window))


def goertzel_magnitude(path, start, end, freq):
    """Normalized magnitude of one frequency in a window."""
    rate, channels, samples = read_samples(path)
    mono = samples[0::channels]
    lo = int(start * rate)
    hi = int(end * rate)
    window = mono[lo:hi]
    if not window:
        return 0.0
    coeff = 2 * math.cos(2 * math.pi * freq / rate)
    s1 = s2 = 0.0
    for value in window:
        s0 = value + coeff * s1 - s2
        s2, s1 = s1, s0
    power = s1 * s1 + s2 * s2 - coeff * s1 * s2
    return math.sqrt(max(power, 0.0)) / len(window)


def wav_peak(path):
    _rate, _channels, samples = read_samples(path)
    return max((abs(v) for v in samples), default=0.0)


def run_checks():
    if shutil.which("ffmpeg") is None \
            or shutil.which("ffprobe") is None:
        print("FAIL CF-P1-006-AUDIO-ffmpeg-required: ffmpeg and "
              "ffprobe are required for the audio tests; a skipped "
              "run is not coverage")
        return 1
    tmpdir = tempfile.mkdtemp(prefix="cf-p1006-audio-")

    # --- mix-input validation ---
    timeline = make_timeline()
    registry = make_registry()
    check("CF-P1-006-AUDIO-mix-inputs-valid",
          validate_mix_inputs(timeline, registry, AUDIO_PROFILE)
          == [],
          str(validate_mix_inputs(timeline, registry, AUDIO_PROFILE)))
    bad = make_timeline(voice_lines=("l1", "l2"))
    errors = validate_mix_inputs(bad, registry, AUDIO_PROFILE)
    check("CF-P1-006-AUDIO-missing-dialogue-fails",
          any("do not cover" in e for e in errors), str(errors))
    bad = make_timeline(voice_lines=("l1", "l1", "l3"))
    errors = validate_mix_inputs(bad, registry, AUDIO_PROFILE)
    check("CF-P1-006-AUDIO-duplicate-dialogue-fails",
          any("more than one dialogue clip" in e for e in errors),
          str(errors))
    bad = make_timeline()
    bad_registry = {k: v for k, v in registry.items()
                    if k != "music-bed"}
    errors = validate_mix_inputs(bad, bad_registry, AUDIO_PROFILE)
    check("CF-P1-006-AUDIO-missing-music-asset-fails",
          any("music-bed" in e for e in errors), str(errors))
    bad_registry = {k: v for k, v in registry.items()
                    if k != "sfx-whoosh"}
    errors = validate_mix_inputs(bad, bad_registry, AUDIO_PROFILE)
    check("CF-P1-006-AUDIO-cue-without-asset-fails",
          any("sfx-whoosh" in e for e in errors), str(errors))
    bad = make_timeline(silence_reason=False)
    errors = validate_mix_inputs(bad, registry, AUDIO_PROFILE)
    check("CF-P1-006-AUDIO-unrecorded-silence-fails",
          any("not recorded with a reason" in e for e in errors),
          str(errors))
    bad_registry = dict(registry)
    bad_registry["voice-l2"] = make_record("voice-l2", "audio-music")
    errors = validate_mix_inputs(timeline, bad_registry, AUDIO_PROFILE)
    check("CF-P1-006-AUDIO-wrong-asset-type-fails",
          any("audio-voice" in e for e in errors), str(errors))
    bad_profile = dict(AUDIO_PROFILE)
    bad_profile["voice_priority"] = False
    errors = validate_mix_inputs(timeline, registry, bad_profile)
    check("CF-P1-006-AUDIO-bad-audio-profile-fails",
          any("voice_priority" in e for e in errors), str(errors))
    bad = make_timeline(music=False)
    errors = validate_mix_inputs(bad, registry, AUDIO_PROFILE)
    check("CF-P1-006-AUDIO-missing-music-track-fails",
          any("music bed is missing" in e for e in errors),
          str(errors))
    bad = make_timeline(sfx=False)
    errors = validate_mix_inputs(bad, registry, AUDIO_PROFILE)
    check("CF-P1-006-AUDIO-missing-sfx-track-fails",
          any("SFX are missing" in e for e in errors), str(errors))

    # --- synthesis ---
    music_path = os.path.join(tmpdir, "music-bed.wav")
    path, duration = synthesize_music_bed(2.0, music_path)
    probe = probe_media_file(path)
    check("CF-P1-006-AUDIO-music-bed-real-wav",
          path == music_path and abs(duration - 2.0) < 0.1
          and probe["sample_rate"] == 48000
          and probe["duration_seconds"] is not None
          and abs(probe["duration_seconds"] - 2.0) < 0.1
          and wav_peak(path) > 0.05,
          str(probe))
    check("CF-P1-006-AUDIO-music-bed-not-clipped",
          not measure_audio(path)["clipped"])
    music_path2 = os.path.join(tmpdir, "music-bed-2.wav")
    synthesize_music_bed(2.0, music_path2)
    with open(music_path, "rb") as handle:
        first = handle.read()
    with open(music_path2, "rb") as handle:
        second = handle.read()
    check("CF-P1-006-AUDIO-music-bed-deterministic",
          first == second)
    tone_path = os.path.join(tmpdir, "room-tone.wav")
    path, duration = synthesize_room_tone(1.5, tone_path)
    probe = probe_media_file(path)
    check("CF-P1-006-AUDIO-room-tone-real-wav",
          abs(duration - 1.5) < 0.1
          and probe["sample_rate"] == 48000
          and 0 < wav_peak(path) < 0.2,
          str(probe))
    tone_path2 = os.path.join(tmpdir, "room-tone-2.wav")
    synthesize_room_tone(1.5, tone_path2)
    with open(tone_path, "rb") as handle:
        first = handle.read()
    with open(tone_path2, "rb") as handle:
        second = handle.read()
    check("CF-P1-006-AUDIO-room-tone-deterministic",
          first == second)
    whoosh_path = os.path.join(tmpdir, "whoosh.wav")
    path, duration = synthesize_whoosh(0.8, whoosh_path)
    probe = probe_media_file(path)
    check("CF-P1-006-AUDIO-whoosh-real-wav",
          abs(duration - 0.8) < 0.1
          and probe["sample_rate"] == 48000
          and wav_peak(path) > 0.05,
          str(probe))
    expect_error("CF-P1-006-AUDIO-synthesis-bad-duration",
                 lambda: synthesize_music_bed(
                     0, os.path.join(tmpdir, "bad.wav")))

    # --- voice track build ---
    line1 = os.path.join(tmpdir, "line1.wav")
    line2 = os.path.join(tmpdir, "line2.wav")
    make_tone_wav(line1, seconds=1.0, freq=440.0)
    make_tone_wav(line2, seconds=1.5, freq=660.0)
    voice_path = os.path.join(tmpdir, "voice-track.wav")
    out = build_voice_track(
        [line1, line2], pause_after_seconds=0.25,
        lead_in_seconds=0.5, out_path=voice_path)
    probe = probe_media_file(out)
    check("CF-P1-006-AUDIO-voice-track-duration",
          out == voice_path
          and probe["duration_seconds"] is not None
          and abs(probe["duration_seconds"] - 3.5) < 0.15
          and probe["sample_rate"] == 48000
          and probe["channels"] == 2,
          str(probe))
    check("CF-P1-006-AUDIO-voice-track-lead-in-silent",
          rms_in_window(out, 0.1, 0.4) < 0.01,
          str(rms_in_window(out, 0.1, 0.4)))
    check("CF-P1-006-AUDIO-voice-track-tone1-position",
          rms_in_window(out, 0.6, 0.9) > 0.1,
          str(rms_in_window(out, 0.6, 0.9)))
    check("CF-P1-006-AUDIO-voice-track-pause-silent",
          rms_in_window(out, 1.6, 1.7) < 0.01,
          str(rms_in_window(out, 1.6, 1.7)))
    check("CF-P1-006-AUDIO-voice-track-tone2-position",
          rms_in_window(out, 2.0, 2.4) > 0.1,
          str(rms_in_window(out, 2.0, 2.4)))
    expect_error("CF-P1-006-AUDIO-voice-track-missing-input",
                 lambda: build_voice_track(
                     [os.path.join(tmpdir, "nope.wav")],
                     pause_after_seconds=0.25, lead_in_seconds=0.5,
                     out_path=os.path.join(tmpdir, "bad-track.wav")))

    # --- mix: voice + music + room tone + one SFX ---
    mix_voice = os.path.join(tmpdir, "mix-voice.wav")
    make_tone_wav(line1, seconds=1.0, freq=440.0)
    make_tone_wav(line2, seconds=1.0, freq=660.0)
    build_voice_track([line1, line2], pause_after_seconds=0.25,
                      lead_in_seconds=1.0, out_path=mix_voice)
    mix_music = os.path.join(tmpdir, "mix-music.wav")
    synthesize_music_bed(6.0, mix_music)
    mix_room = os.path.join(tmpdir, "mix-room.wav")
    synthesize_room_tone(6.0, mix_room)
    mix_sfx = os.path.join(tmpdir, "mix-sfx.wav")
    synthesize_whoosh(0.8, mix_sfx)
    mix_timeline = {
        "schema_version": "2.5", "id": "timeline-mix-001",
        "project_id": "proj-audio-001",
        "format": "editor_neutral_v1",
        "output_profile": {}, "duration_seconds": 6.0,
        "video_tracks": [{"track_id": "v1", "clips": [
            {"clip_id": f"v{i}", "asset_id": f"shot-s{i}",
             "shot_id": f"s{i}", "source_start_seconds": 0.0,
             "source_end_seconds": 2.0,
             "timeline_start_seconds": float((i - 1) * 2),
             "duration_seconds": 2.0, "operations": []}
            for i in (1, 2, 3)]}],
        "audio_tracks": [
            {"track_id": "voice", "kind": "dialogue", "clips": [
                {"clip_id": "voice-track", "asset_id": "voice-track",
                 "line_id": "l1", "shot_id": "s1",
                 "timeline_start_seconds": 0.0,
                 "duration_seconds": 3.5}]},
            {"track_id": "music", "kind": "music", "clips": [
                {"clip_id": "music-bed", "asset_id": "music-bed",
                 "timeline_start_seconds": 0.0,
                 "duration_seconds": 6.0}]},
            {"track_id": "room-tone", "kind": "room-tone", "clips": [
                {"clip_id": "room-tone", "asset_id": "room-tone",
                 "timeline_start_seconds": 0.0,
                 "duration_seconds": 6.0}]},
            {"track_id": "sfx", "kind": "sfx", "clips": [
                {"clip_id": "sfx-whoosh-s2", "asset_id": "sfx-whoosh",
                 "cue_id": "sfx-whoosh-s2", "shot_id": "s2",
                 "timeline_start_seconds": 2.0,
                 "duration_seconds": 0.8}]}],
        "transitions": [],
        "intentional_silences": [{
            "silence_id": "tail-out",
            "timeline_start_seconds": 4.5, "duration_seconds": 1.5,
            "reason": "Music tail-out under the end card."}],
        "provenance": {},
    }
    asset_paths = {"voice-track": mix_voice, "music-bed": mix_music,
                   "room-tone": mix_room, "sfx-whoosh": mix_sfx}
    mix_out = os.path.join(tmpdir, "mix.wav")
    record = mix_audio(mix_timeline, asset_paths, AUDIO_PROFILE,
                       mix_out)
    check("CF-P1-006-AUDIO-mix-duration",
          record["duration_seconds"] is not None
          and abs(record["duration_seconds"] - 6.0) < 0.15,
          str(record.get("duration_seconds")))
    check("CF-P1-006-AUDIO-mix-peak-below-zero",
          record["peak_dbfs"] is not None
          and record["peak_dbfs"] < 0.0,
          str(record.get("peak_dbfs")))
    check("CF-P1-006-AUDIO-mix-not-clipped",
          record["clipped"] is False)
    check("CF-P1-006-AUDIO-mix-operations-recorded",
          any("sidechaincompress" in op for op in record["operations"])
          and any("voice" in op for op in record["operations"])
          and any("fade" in op.lower()
                  for op in record["operations"]),
          str(record["operations"]))
    # Music ducking: the 165 Hz music component is louder in the
    # music-only lead-in than under the voice line.
    unducked = goertzel_magnitude(mix_out, 0.6, 1.0, 164.81)
    ducked = goertzel_magnitude(mix_out, 1.1, 1.9, 164.81)
    check("CF-P1-006-AUDIO-music-ducked-under-voice",
          unducked > 0 and ducked < 0.7 * unducked,
          f"unducked={unducked:.4f} ducked={ducked:.4f}")
    # Voice is audible in the mix where the line plays.
    check("CF-P1-006-AUDIO-mix-voice-audible",
          rms_in_window(mix_out, 1.2, 1.8) > 0.05,
          str(rms_in_window(mix_out, 1.2, 1.8)))

    # One measured volume correction when the peak exceeds target.
    strict_profile = dict(AUDIO_PROFILE)
    strict_profile["target_true_peak_dbfs"] = -20.0
    mix_out2 = os.path.join(tmpdir, "mix-corrected.wav")
    record2 = mix_audio(mix_timeline, asset_paths, strict_profile,
                        mix_out2)
    check("CF-P1-006-AUDIO-mix-one-correction",
          any("volume correction" in op
              for op in record2["operations"])
          and record2["peak_dbfs"] is not None
          and record2["peak_dbfs"] <= -19.0,
          str(record2))
    expect_error("CF-P1-006-AUDIO-mix-missing-file",
                 lambda: mix_audio(
                     mix_timeline,
                     {**asset_paths, "music-bed": os.path.join(
                         tmpdir, "nope.wav")},
                     AUDIO_PROFILE,
                     os.path.join(tmpdir, "bad-mix.wav")))

    # --- measure_audio ---
    clipped_path = os.path.join(tmpdir, "clipped.wav")
    make_clipped_wav(clipped_path)
    measured = measure_audio(clipped_path)
    check("CF-P1-006-AUDIO-measure-clipped",
          measured["clipped"] is True
          and measured["peak_dbfs"] is not None
          and measured["peak_dbfs"] > -0.5,
          str(measured))
    gap_path = os.path.join(tmpdir, "gap.wav")
    make_silence_gap_wav(gap_path)
    measured = measure_audio(gap_path)
    check("CF-P1-006-AUDIO-measure-silence",
          any(abs(s["duration"] - 3.0) < 0.15
              for s in measured["silences"]),
          str(measured["silences"]))
    check("CF-P1-006-AUDIO-measure-loudness",
          measured["loudness_lufs"] is not None
          and -70.0 < measured["loudness_lufs"] < 0.0
          and measured["true_peak_dbfs"] is not None,
          str({k: measured.get(k) for k in
               ("loudness_lufs", "true_peak_dbfs")}))
    check("CF-P1-006-AUDIO-measure-duration-rate",
          abs(measured["duration_seconds"] - 5.0) < 0.1
          and measured["sample_rate"] == 48000
          and measured["channels"] == 1,
          str(measured))
    expect_error("CF-P1-006-AUDIO-measure-missing-file",
                 lambda: measure_audio(
                     os.path.join(tmpdir, "nope.wav")))

    # --- audio_qc_findings ---
    clean_measured = {"duration_seconds": 6.0, "sample_rate": 48000,
                      "channels": 2, "peak_dbfs": -6.0,
                      "loudness_lufs": -16.0,
                      "true_peak_dbfs": -1.5, "clipped": False,
                      "silences": []}
    voice_lines = [{"line_id": "l1"}, {"line_id": "l2"},
                   {"line_id": "l3"}]
    intentional = make_timeline()["intentional_silences"]
    findings = audio_qc_findings(clean_measured, make_timeline(),
                                 voice_lines, AUDIO_PROFILE,
                                 intentional)
    check("CF-P1-006-AUDIO-qc-clean", findings == [], str(findings))
    clipped_measured = dict(clean_measured, clipped=True)
    findings = audio_qc_findings(clipped_measured, make_timeline(),
                                 voice_lines, AUDIO_PROFILE,
                                 intentional)
    check("CF-P1-006-AUDIO-qc-clipped",
          any(f["check"] == "clipped-audio"
              and f["severity"] == "critical" for f in findings),
          str(findings))
    findings = audio_qc_findings(
        clean_measured, make_timeline(voice_lines=("l1", "l2")),
        voice_lines, AUDIO_PROFILE, intentional)
    check("CF-P1-006-AUDIO-qc-missing-dialogue",
          any(f["check"] == "missing-dialogue"
              and f["severity"] == "critical" for f in findings),
          str(findings))
    findings = audio_qc_findings(
        dict(clean_measured, duration_seconds=0.0),
        make_timeline(), voice_lines, AUDIO_PROFILE, intentional)
    check("CF-P1-006-AUDIO-qc-empty-audio",
          any(f["check"] == "empty-audio" for f in findings),
          str(findings))
    gap_measured = dict(
        clean_measured,
        silences=[{"start": 1.0, "end": 4.0, "duration": 3.0}])
    findings = audio_qc_findings(gap_measured, make_timeline(),
                                 voice_lines, AUDIO_PROFILE, [])
    check("CF-P1-006-AUDIO-qc-unexpected-silence",
          any(f["check"] == "unexpected-silence"
              and f["severity"] == "major" for f in findings),
          str(findings))
    findings = audio_qc_findings(
        gap_measured, make_timeline(), voice_lines, AUDIO_PROFILE,
        [{"timeline_start_seconds": 1.0, "duration_seconds": 3.0,
          "reason": "Intentional pause."}])
    check("CF-P1-006-AUDIO-qc-intentional-silence-not-flagged",
          not any(f["check"] == "unexpected-silence"
                  for f in findings),
          str(findings))
    findings = audio_qc_findings(
        dict(clean_measured, duration_seconds=4.0),
        make_timeline(), voice_lines, AUDIO_PROFILE, intentional)
    check("CF-P1-006-AUDIO-qc-misaligned-voice",
          any(f["check"] == "voice-alignment" for f in findings),
          str(findings))
    findings = audio_qc_findings(
        clean_measured, make_timeline(music=False), voice_lines,
        AUDIO_PROFILE, intentional)
    check("CF-P1-006-AUDIO-qc-missing-music",
          any(f["check"] == "missing-music" for f in findings),
          str(findings))
    findings = audio_qc_findings(
        clean_measured, make_timeline(sfx=False), voice_lines,
        AUDIO_PROFILE, intentional)
    check("CF-P1-006-AUDIO-qc-missing-sfx",
          any(f["check"] == "missing-sfx" for f in findings),
          str(findings))
    findings = audio_qc_findings(
        dict(clean_measured, duration_seconds=6.5),
        make_timeline(), voice_lines, AUDIO_PROFILE, intentional)
    check("CF-P1-006-AUDIO-qc-overrun",
          any(f["check"] == "audio-overrun" for f in findings),
          str(findings))
    # Integration: a measured 3 s intentional silence is not flagged.
    measured_gap = measure_audio(gap_path)
    findings = audio_qc_findings(
        measured_gap,
        {"duration_seconds": 5.0, "audio_tracks": [
            {"track_id": "voice", "kind": "dialogue", "clips": []},
            {"track_id": "music", "kind": "music", "clips": [
                {"clip_id": "m", "asset_id": "music-bed",
                 "timeline_start_seconds": 0.0,
                 "duration_seconds": 5.0}]},
            {"track_id": "sfx", "kind": "sfx", "clips": [
                {"clip_id": "s", "asset_id": "sfx-whoosh",
                 "timeline_start_seconds": 0.0,
                 "duration_seconds": 0.8}]}],
         "video_tracks": []},
        [], AUDIO_PROFILE,
        [{"timeline_start_seconds": 1.0, "duration_seconds": 3.0,
          "reason": "Intentional pause between lines."}])
    check("CF-P1-006-AUDIO-qc-measured-intentional-silence",
          not any(f["check"] == "unexpected-silence"
                  for f in findings),
          str(findings))

    print(f"--- CF-P1-006-AUDIO: {_checks[0]} checks, "
          f"{len(failures)} failures ---")
    if failures:
        print("FAILURES: " + ", ".join(failures))
        return 1
    return 0


def main():
    return run_checks()


if __name__ == "__main__":
    sys.exit(main())
