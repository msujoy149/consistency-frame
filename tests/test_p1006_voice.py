#!/usr/bin/env python3
"""Voice stage tests (CF-WO-P1-006, Phase C).

Covers voice-config validation, line-asset mapping, voice
asset verification against real small WAV fixtures, the
unsupported-control refusal, generation retry through a stub
adapter, and the voice mapping report.

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
from runtime.media_adapters import VoiceStudioAdapter  # noqa: E402
from runtime.media_execution import MediaExecutionError  # noqa: E402
from runtime.production_assets import (  # noqa: E402
    hash_file, new_asset_record, register_asset)
from runtime.production_voice import (  # noqa: E402
    VoiceError, generate_voice_line, validate_voice_config,
    verify_voice_assets, voice_line_assets, voice_mapping_report)

failures = []
_checks = [0]


def check(name, cond, detail=""):
    _checks[0] += 1
    if cond:
        print(f"PASS {name}")
    else:
        print(f"FAIL {name} {detail}")
        failures.append(name)


def expect_error(label, fn, kinds=(VoiceError, MediaExecutionError)):
    try:
        fn()
    except kinds as exc:
        check(label, True)
        return str(exc)
    except Exception as exc:  # noqa: BLE001 - any other error fails
        check(label, False, f"raised {type(exc).__name__}: {exc}")
        return ""
    check(label, False, "operation succeeded instead of refusing")
    return ""


SCRIPT_LINES = [
    {"line_id": "l1", "shot_id": "s1",
     "text": "One character. Every scene."},
    {"line_id": "l2", "shot_id": "s2",
     "text": "Most tools redraw the character in every shot."},
    {"line_id": "l3", "shot_id": "s3",
     "text": "Consistency Frame locks the design first."},
]


def valid_config():
    return {
        "voice_id": "p1006-narrator",
        "language": "en-US",
        "engine": "omnivoice",
        "provider": "provider-voicestudio-omnivoice",
        "commercial_use": "non-commercial-only",
        "seed": 42,
        "instruct": "narrator",
        "speed": 1.0,
        "pause_after_seconds": 0.5,
        "lead_in_seconds": 1.0,
        "tail_out_seconds": 1.5,
        "lines": [
            {"line_id": "l1", "shot_id": "s1",
             "text": "One character. Every scene."},
            {"line_id": "l2", "shot_id": "s2",
             "text": "Most tools redraw the character in every shot."},
            {"line_id": "l3", "shot_id": "s3",
             "text": "Consistency Frame locks the design first."},
        ],
    }


def make_tone_wav(path, seconds=1.0, freq=440.0, rate=48000,
                  amplitude=0.5, channels=1):
    """Real sine WAV fixture (stdlib wave only)."""
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


def make_silent_wav(path, seconds=1.0, rate=48000):
    count = int(round(seconds * rate))
    with wave.open(path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x00" * count)
    return path


def make_empty_wav(path, rate=48000):
    with wave.open(path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"")
    return path


def asset_for(root, tmpdir, line_id, filename, project_id="proj-voice-001"):
    """A registered voice asset record for a real WAV file."""
    rel = filename
    sha, size = hash_file(os.path.join(tmpdir, filename))
    record = new_asset_record(
        asset_id=f"voice-{line_id}", project_id=project_id,
        shot_id="s1", asset_type="audio-voice",
        provider="provider-voicestudio-omnivoice",
        provider_status="EXERCISED", path=rel,
        mime_type="audio/wav", license_class="cc-by-nc",
        license_note="OmniVoice default weights CC-BY-NC — "
                     "non-commercial only",
        privacy_class="internal", transmit_to_provider=False,
        provenance="INFERRED_FOR_PRODUCTION",
        generation={"tool": "voicestudio-omnivoice",
                    "tool_version": "0.5.8", "seed": 42,
                    "instruct": "narrator", "attempts": 1})
    record["size_bytes"] = size
    record["sha256"] = sha
    return record


class StubAdapter:
    """VoiceStudio-shaped stub: records packets, writes real WAVs.

    ``fail_times`` controls how many submit calls fail with a
    provider error before succeeding. ``refuse_controls`` makes
    translate refuse unsupported controls like the real adapter.
    """

    adapter_version = "0.5.8"

    def __init__(self, workspace_root, fail_times=0,
                 refuse_controls=True):
        self.workspace_root = workspace_root
        self.fail_times = fail_times
        self.refuse_controls = refuse_controls
        self.translate_calls = []
        self.submit_calls = 0

    def translate(self, packet, context):
        self.translate_calls.append((packet, context))
        binding = (packet or {}).get("voice_binding") or {}
        if self.refuse_controls:
            for control in ("emotional_delivery", "pitch_range",
                            "pauses", "vocal_characteristics",
                            "pronunciation_preferences"):
                if binding.get(control) not in (None, "", {}):
                    raise MediaExecutionError(
                        f"voice control {control!r} is not supported "
                        "by the bundled OmniVoice engine",
                        code="validation-failed")
        return {"voice_request": {
            "text": binding.get("dialogue_text"),
            "language": binding.get("language"),
            "profile_id": binding.get("voice_profile_id"),
            "seed": binding.get("seed"),
            "dialogue_line_id": binding.get("dialogue_line_id"),
            "instruct": (context or {}).get("instruct"),
            "speed": binding.get("speaking_pace")}}

    def submit(self, request, context):
        self.submit_calls += 1
        if self.submit_calls <= self.fail_times:
            raise MediaExecutionError(
                "simulated provider error",
                code="provider-error")
        execution_id = (context or {}).get("execution_id") or "voice"
        out_rel = os.path.join("outputs", f"{execution_id}.wav")
        out_real = os.path.join(self.workspace_root, out_rel)
        os.makedirs(os.path.dirname(out_real), exist_ok=True)
        make_tone_wav(out_real, seconds=1.0, freq=440.0)
        sha, size = hash_file(out_real)
        return {"provider_job_id": "audio-stub-001",
                "completed": True,
                "output": {"path": out_rel, "sha256": sha,
                           "bytes": size, "format": "wav",
                           "provider_audio_id": "audio-stub-001"},
                "failure": None}


def run_checks():
    if shutil.which("ffmpeg") is None \
            or shutil.which("ffprobe") is None:
        print("FAIL CF-P1-006-VOICE-ffmpeg-required: ffmpeg and "
              "ffprobe are required for the voice tests; a skipped "
              "run is not coverage")
        return 1

    # --- voice config validation ---
    check("CF-P1-006-VOICE-valid-config-passes",
          validate_voice_config(valid_config(), SCRIPT_LINES) == [])
    bad = valid_config()
    bad["lines"][1]["text"] = "Most tools redraw the character."
    errors = validate_voice_config(bad, SCRIPT_LINES)
    check("CF-P1-006-VOICE-text-mismatch-fails",
          any("byte-for-byte" in e for e in errors), str(errors))
    bad = valid_config()
    bad["lines"].append(dict(bad["lines"][0]))
    errors = validate_voice_config(bad, SCRIPT_LINES)
    check("CF-P1-006-VOICE-duplicate-line-fails",
          any("appears twice" in e for e in errors), str(errors))
    bad = valid_config()
    bad["lines"] = bad["lines"][:2]
    errors = validate_voice_config(bad, SCRIPT_LINES)
    check("CF-P1-006-VOICE-missing-line-fails",
          any("missing dialogue" in e for e in errors), str(errors))
    bad = valid_config()
    bad["seed"] = "42"
    errors = validate_voice_config(bad, SCRIPT_LINES)
    check("CF-P1-006-VOICE-bad-seed-fails",
          any("seed" in e for e in errors), str(errors))
    bad = valid_config()
    bad["language"] = "fr-FR"
    errors = validate_voice_config(bad, SCRIPT_LINES)
    check("CF-P1-006-VOICE-bad-language-fails",
          any("language" in e for e in errors), str(errors))
    bad = valid_config()
    bad["speed"] = 2.5
    errors = validate_voice_config(bad, SCRIPT_LINES)
    check("CF-P1-006-VOICE-bad-speed-fails",
          any("speed" in e for e in errors), str(errors))
    for control in ("emotional_delivery", "pitch_range", "pauses"):
        bad = valid_config()
        bad[control] = "warm and slow"
        errors = validate_voice_config(bad, SCRIPT_LINES)
        check(f"CF-P1-006-VOICE-unsupported-control-fails:{control}",
              any(control in e for e in errors), str(errors))

    # --- line-asset mapping ---
    specs = voice_line_assets(valid_config())
    check("CF-P1-006-VOICE-line-assets-order-ids",
          [s["asset_id"] for s in specs]
          == ["voice-l1", "voice-l2", "voice-l3"]
          and [s["line_id"] for s in specs] == ["l1", "l2", "l3"]
          and [s["shot_id"] for s in specs] == ["s1", "s2", "s3"],
          str(specs))
    check("CF-P1-006-VOICE-line-assets-fields",
          all(s["language"] == "en-US" and s["seed"] == 42
              and s["instruct"] == "narrator"
              and s["pause_after_seconds"] == 0.5
              and s["text"] == SCRIPT_LINES[i]["text"]
              for i, s in enumerate(specs)))
    expect_error("CF-P1-006-VOICE-line-assets-no-lines",
                 lambda: voice_line_assets({"lines": []}))

    # --- voice verification with real WAV fixtures ---
    tmpdir = tempfile.mkdtemp(prefix="cf-p1006-voice-")
    lines = voice_line_assets(valid_config())
    for line in lines:
        line["project_id"] = "proj-voice-001"
    make_tone_wav(os.path.join(tmpdir, "voice-l1.wav"), seconds=1.0)
    make_tone_wav(os.path.join(tmpdir, "voice-l2.wav"), seconds=1.5,
                  freq=660.0)
    make_tone_wav(os.path.join(tmpdir, "voice-l3.wav"), seconds=0.5,
                  freq=330.0, channels=2)
    records = [asset_for("root", tmpdir, lid, f"voice-{lid}.wav")
               for lid in ("l1", "l2", "l3")]
    errors, report = verify_voice_assets(lines, records, tmpdir)
    check("CF-P1-006-VOICE-verify-valid-passes", errors == [],
          str(errors))
    check("CF-P1-006-VOICE-verify-report",
          report["lines_checked"] == 3
          and abs(report["total_duration_seconds"] - 3.0) < 0.01
          and [p["line_id"] for p in report["per_line"]]
          == ["l1", "l2", "l3"]
          and abs(report["per_line"][0]["duration_seconds"] - 1.0)
          < 0.01
          and report["per_line"][0]["sample_rate"] == 48000
          and report["per_line"][0]["channels"] == 1
          and report["per_line"][2]["channels"] == 2,
          str(report))
    make_empty_wav(os.path.join(tmpdir, "voice-l1-empty.wav"))
    empty_record = asset_for("root", tmpdir, "l1",
                             "voice-l1-empty.wav")
    errors, _ = verify_voice_assets(
        lines[:1], [empty_record], tmpdir)
    check("CF-P1-006-VOICE-empty-wav-fails",
          any("0 frames" in e for e in errors), str(errors))
    make_silent_wav(os.path.join(tmpdir, "voice-l1-silent.wav"))
    silent_record = asset_for("root", tmpdir, "l1",
                              "voice-l1-silent.wav")
    errors, _ = verify_voice_assets(
        lines[:1], [silent_record], tmpdir)
    check("CF-P1-006-VOICE-all-zero-wav-fails",
          any("silence" in e for e in errors), str(errors))
    missing_record = new_asset_record(
        asset_id="voice-l1", project_id="proj-voice-001",
        shot_id="s1", asset_type="audio-voice",
        provider="provider-voicestudio-omnivoice",
        provider_status="EXERCISED",
        path="voice-l1-does-not-exist.wav",
        mime_type="audio/wav", license_class="cc-by-nc",
        license_note="OmniVoice default weights CC-BY-NC — "
                     "non-commercial only",
        privacy_class="internal", transmit_to_provider=False,
        provenance="INFERRED_FOR_PRODUCTION",
        generation={"tool": "voicestudio-omnivoice",
                    "tool_version": "0.5.8", "seed": 42,
                    "instruct": "narrator", "attempts": 1})
    errors, _ = verify_voice_assets(
        lines[:1], [missing_record], tmpdir)
    check("CF-P1-006-VOICE-missing-file-fails",
          any("does not exist" in e for e in errors), str(errors))
    wrong_hash = copy.deepcopy(records[0])
    wrong_hash["sha256"] = "0" * 64
    errors, _ = verify_voice_assets(lines[:1], [wrong_hash], tmpdir)
    check("CF-P1-006-VOICE-wrong-hash-fails",
          any("SHA-256 mismatch" in e for e in errors), str(errors))
    errors, _ = verify_voice_assets(
        lines, records + [copy.deepcopy(records[0])], tmpdir)
    check("CF-P1-006-VOICE-duplicate-line-asset-fails",
          any("duplicate" in e for e in errors), str(errors))
    errors, _ = verify_voice_assets(lines, records[:2], tmpdir)
    check("CF-P1-006-VOICE-missing-line-fails",
          any("no voice asset" in e for e in errors), str(errors))
    unknown = copy.deepcopy(records[0])
    unknown["asset_id"] = "voice-l9"
    errors, _ = verify_voice_assets(lines, records + [unknown],
                                    tmpdir)
    check("CF-P1-006-VOICE-unknown-line-asset-fails",
          any("no dialogue line" in e for e in errors), str(errors))

    # --- unsupported-control refusal ---
    workspace = tempfile.mkdtemp(prefix="cf-p1006-voice-ws-")
    os.makedirs(os.path.join(workspace, "outputs"), exist_ok=True)
    real_adapter = VoiceStudioAdapter(workspace_root=workspace)
    packet = {"voice_binding": {
        "dialogue_text": "Hello.", "language": "en",
        "voice_profile_id": "p1006-narrator", "seed": 42,
        "dialogue_line_id": "l1",
        "emotional_delivery": "warm"}}
    expect_error(
        "CF-P1-006-VOICE-adapter-refuses-emotional-delivery",
        lambda: real_adapter.translate(packet, {}))
    packet["voice_binding"] = {
        "dialogue_text": "Hello.", "language": "en",
        "voice_profile_id": "p1006-narrator", "seed": 42,
        "dialogue_line_id": "l1", "pauses": [0.5]}
    message = expect_error(
        "CF-P1-006-VOICE-adapter-refuses-pauses",
        lambda: real_adapter.translate(packet, {}))
    check("CF-P1-006-VOICE-refusal-names-control",
          "pauses" in message, message)
    stub = StubAdapter(workspace)
    bad_line = dict(lines[0])
    bad_line["pitch_range"] = "wide"
    message = expect_error(
        "CF-P1-006-VOICE-generate-refuses-pitch-range",
        lambda: generate_voice_line(
            stub, None, bad_line, workspace_root=workspace,
            execution_id="exec-refused"))
    check("CF-P1-006-VOICE-generate-refusal-names-control",
          "pitch_range" in message, message)
    check("CF-P1-006-VOICE-refusal-writes-no-audio",
          not os.path.exists(
              os.path.join(workspace, "outputs",
                           "exec-refused.wav")))

    # --- generation retry through the stub ---
    stub_once = StubAdapter(workspace, fail_times=1)
    record = generate_voice_line(
        stub_once, None, lines[0], workspace_root=workspace,
        execution_id="exec-retry-001")
    check("CF-P1-006-VOICE-retry-once-succeeds",
          record["asset_id"] == "voice-l1"
          and record["status"] == "VERIFIED"
          and record["asset_type"] == "audio-voice"
          and record["source"]["provider"]
          == "provider-voicestudio-omnivoice"
          and record["source"]["provider_status"] == "EXERCISED"
          and record["license"]["class"] == "cc-by-nc"
          and record["duration_seconds"] is not None
          and abs(record["duration_seconds"] - 1.0) < 0.05
          and record["sample_rate"] == 48000,
          str({k: record.get(k) for k in
               ("asset_id", "status", "duration_seconds",
                "sample_rate")}))
    check("CF-P1-006-VOICE-retry-records-attempts",
          record["generation"]["attempts"] == 2
          and len(record["generation"].get("failures") or []) == 1
          and record["generation"]["failures"][0]["attempt"] == 1
          and record["generation"]["seed"] == 42
          and record["generation"]["instruct"] == "narrator"
          and record["generation"]["provider_audio_id"]
          == "audio-stub-001",
          str(record.get("generation")))
    check("CF-P1-006-VOICE-retry-packet-shape",
          stub_once.translate_calls[0][0]["voice_binding"]
          == {"dialogue_text": "One character. Every scene.",
              "language": "en-US",
              "voice_profile_id": "p1006-narrator", "seed": 42,
              "dialogue_line_id": "l1", "speaking_pace": 1.0}
          and stub_once.translate_calls[0][1]["instruct"]
          == "narrator"
          and stub_once.translate_calls[0][1]["execution_id"]
          == "exec-retry-001",
          str(stub_once.translate_calls))
    stub_always = StubAdapter(workspace, fail_times=99)
    message = expect_error(
        "CF-P1-006-VOICE-fail-twice-raises",
        lambda: generate_voice_line(
            stub_always, None, lines[1], workspace_root=workspace,
            execution_id="exec-fail-001"))
    check("CF-P1-006-VOICE-fail-twice-no-fake-audio",
          not os.path.exists(
              os.path.join(workspace, "outputs",
                           "exec-fail-001.wav")))
    check("CF-P1-006-VOICE-fail-twice-names-line",
          "l2" in message, message)
    # Diagnostics ride on the raised error.
    try:
        generate_voice_line(
            StubAdapter(workspace, fail_times=99), None, lines[1],
            workspace_root=workspace, execution_id="exec-fail-002")
        check("CF-P1-006-VOICE-fail-diagnostics", False,
              "no error raised")
    except VoiceError as exc:
        check("CF-P1-006-VOICE-fail-diagnostics",
              exc.diagnostics is not None
              and exc.diagnostics.get("attempts") == 2
              and len(exc.diagnostics.get("failures") or []) == 2,
              str(exc.diagnostics))

    # --- voice mapping report ---
    verified = [generate_voice_line(
        StubAdapter(workspace), None, line,
        workspace_root=workspace,
        execution_id=f"exec-map-{line['line_id']}")
        for line in lines]
    mapping = voice_mapping_report(lines, verified)
    check("CF-P1-006-VOICE-mapping-report",
          mapping["voice_id"] == "p1006-narrator"
          and mapping["language"] == "en-US"
          and mapping["seed"] == 42
          and mapping["instruct"] == "narrator"
          and [m["line_id"] for m in mapping["lines"]]
          == ["l1", "l2", "l3"]
          and all(m["asset_id"] == f"voice-{m['line_id']}"
                  and m["duration_seconds"] is not None
                  and abs(m["duration_seconds"] - 1.0) < 0.05
                  and isinstance(m["sha256"], str)
                  and len(m["sha256"]) == 64
                  and m["text"] == SCRIPT_LINES[i]["text"]
                  for i, m in enumerate(mapping["lines"])),
          str(mapping))
    expect_error("CF-P1-006-VOICE-mapping-missing-asset",
                 lambda: voice_mapping_report(lines, verified[:2]))
    registry = {}
    for record in verified:
        registry = register_asset(registry, record)
    check("CF-P1-006-VOICE-records-register",
          len(registry) == 3)

    print(f"--- CF-P1-006-VOICE: {_checks[0]} checks, "
          f"{len(failures)} failures ---")
    if failures:
        print("FAILURES: " + ", ".join(failures))
        return 1
    return 0


def main():
    return run_checks()


if __name__ == "__main__":
    sys.exit(main())
