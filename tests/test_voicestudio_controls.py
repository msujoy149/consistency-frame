#!/usr/bin/env python3
"""VoiceStudio capability honesty tests (CF-WO-P1-005-R4, workstream D).

The bundled VoiceStudio backend + OmniVoice engine genuinely
forward only: instruct (fixed English tags, from the execution
context), a numeric speaking pace (as the backend's speed), and
seed. The voice binding's emotional_delivery, pitch_range,
pauses, vocal_characteristics and pronunciation_preferences
have no backend field on this engine: the adapter refuses them
with a precise capability error in preflight and in translate,
instead of silently dropping them. The provider capability
registry advertises exactly the supported controls.

The backend is a mock HTTP transport; no VoiceStudio process is
started and no VoiceStudio internals are touched. No test here
weakens any P0, P1 or R4 check.
"""

import io
import json
import os
import sys
import tempfile
import wave

ROOT = os.path.join(os.path.dirname(__file__), "..")
ROOT_ABS = os.path.abspath(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
from runtime.media_adapters import (  # noqa: E402
    VOICESTUDIO_SUPPORTED_VOICE_CONTROLS,
    VOICESTUDIO_UNSUPPORTED_VOICE_CONTROLS,
    VoiceStudioAdapter)
from runtime.media_execution import MediaExecutionError  # noqa: E402

failures = []
_checks = [0]


def check(name, cond, detail=""):
    _checks[0] += 1
    if cond:
        print(f"PASS {name}")
    else:
        print(f"FAIL {name} {detail}")
        failures.append(name)


def expect_error(label, fn, code=None):
    try:
        fn()
    except MediaExecutionError as exc:
        if code is not None and exc.code != code:
            check(label, False, f"code {exc.code!r}, expected {code!r}")
            return
        check(label, True)
        return
    except Exception as exc:  # noqa: BLE001 - any other error is a fail
        check(label, False, f"raised {type(exc).__name__}: {exc}")
        return
    check(label, False, "operation succeeded instead of refusing")


def make_wav_bytes(seconds=1, rate=8000):
    frames = b"\x00\x00" * (rate * seconds)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(frames)
    return buf.getvalue()


def mock_voicestudio(capture=None):
    wav = make_wav_bytes()

    def client(method, url, *, data=None, headers=None, files=None):
        if capture is not None:
            capture.append((method, url, data))
        if url.endswith("/health"):
            return (200, {},
                    json.dumps({"status": "ok", "device": "cpu",
                                "engine": "omnivoice",
                                "version": "0.5.8"}).encode("utf-8"))
        if url.endswith("/generate"):
            return (200, {"x-audio-id": "audio-test-001"}, wav)
        return (404, {}, b"not found")
    return client


def voice_packet(**binding_extra):
    binding = {
        "voice_profile_id": "vp-test-001",
        "dialogue_line_id": "l-01",
        "dialogue_text": "Hello.",
        "language": "bn",
        "character_id": "char-001",
    }
    binding.update(binding_extra)
    return {
        "task_id": "task-voice-001",
        "task_type": "voice-generation",
        "canonical_instruction": "Say hello.",
        "voice_binding": binding,
    }


def voice_context(**extra):
    context = {"voice_consent": True,
               "voice_profile_id": "vp-test-001",
               "execution_id": "exec-voice-test"}
    context.update(extra)
    return context


UNSUPPORTED = ("emotional_delivery", "pitch_range", "pauses",
               "vocal_characteristics", "pronunciation_preferences")
SAMPLE_VALUES = {
    "emotional_delivery": "happy",
    "pitch_range": "high",
    "pauses": "after 'hello': 0.5s",
    "vocal_characteristics": {"timbre": "warm"},
    "pronunciation_preferences": "roll the r",
}


def run_checks():
    tmpdir = tempfile.mkdtemp(prefix="cf-p1-005-r4-voice-")
    workspace = os.path.join(tmpdir, "voice-workspace")
    os.makedirs(workspace)
    adapter = VoiceStudioAdapter(
        workspace_root=workspace,
        http_client=mock_voicestudio())

    # The capability map itself: five refused, three forwarded.
    check("CF-P1-005-R4-VOICE-map-unsupported",
          set(VOICESTUDIO_UNSUPPORTED_VOICE_CONTROLS)
          == set(UNSUPPORTED))
    check("CF-P1-005-R4-VOICE-map-supported",
          set(VOICESTUDIO_SUPPORTED_VOICE_CONTROLS)
          == {"instruct", "speed", "seed"})

    # Preflight refuses every unsupported control, naming it.
    for field in UNSUPPORTED:
        packet = voice_packet(**{field: SAMPLE_VALUES[field]})
        errors = adapter.preflight(packet, voice_context())
        check(f"CF-P1-005-R4-VOICE-preflight-refuses-{field}",
              any(field in error for error in errors),
              str(errors))
    # Preflight refuses a descriptive pace (no numeric mapping
    # exists) and accepts a numeric one, string or number.
    for bad_pace in ("natural", "slow", "fast", "0", "-1", "1.5x",
                     True):
        packet = voice_packet(speaking_pace=bad_pace)
        errors = adapter.preflight(packet, voice_context())
        check("CF-P1-005-R4-VOICE-preflight-refuses-pace: "
              f"{bad_pace!r}",
              any("speaking_pace" in error for error in errors),
              str(errors))
    for good_pace in ("1.25", "0.9", 1.0, 2):
        packet = voice_packet(speaking_pace=good_pace)
        check("CF-P1-005-R4-VOICE-preflight-accepts-pace: "
              f"{good_pace!r}",
              adapter.preflight(packet, voice_context()) == [])
    # A non-string instruct is refused; a string is accepted.
    check("CF-P1-005-R4-VOICE-preflight-refuses-bad-instruct",
          len(adapter.preflight(
              voice_packet(),
              voice_context(instruct=123))) > 0)
    check("CF-P1-005-R4-VOICE-preflight-accepts-instruct",
          adapter.preflight(
              voice_packet(),
              voice_context(instruct="[laughter]")) == [])
    # Empty / absent controls are not controls at all.
    check("CF-P1-005-R4-VOICE-preflight-empty-absent",
          adapter.preflight(
              voice_packet(emotional_delivery="",
                           speaking_pace="",
                           vocal_characteristics={}),
              voice_context()) == [])

    # Translate raises (validation-failed) for the same controls.
    for field in UNSUPPORTED:
        packet = voice_packet(**{field: SAMPLE_VALUES[field]})
        expect_error(
            "CF-P1-005-R4-VOICE-translate-refuses-" + field,
            lambda packet=packet: adapter.translate(
                packet, voice_context()),
            code="validation-failed")
    expect_error(
        "CF-P1-005-R4-VOICE-translate-refuses-pace",
        lambda: adapter.translate(
            voice_packet(speaking_pace="natural"), voice_context()),
        code="validation-failed")
    expect_error(
        "CF-P1-005-R4-VOICE-translate-refuses-bad-instruct",
        lambda: adapter.translate(
            voice_packet(), voice_context(instruct=["laughter"])),
        code="validation-failed")
    # ... and prepare() refuses the same way (preflight + translate).
    expect_error(
        "CF-P1-005-R4-VOICE-prepare-refuses-emotion",
        lambda: adapter.prepare(
            voice_packet(emotional_delivery="sad"),
            voice_context()),
        code=None)

    # Translate forwards the supported controls exactly.
    request = adapter.translate(
        voice_packet(speaking_pace="1.25"),
        voice_context(instruct="[laughter]"))
    voice = request["voice_request"]
    check("CF-P1-005-R4-VOICE-translate-forwards-instruct",
          voice.get("instruct") == "[laughter]", str(voice))
    check("CF-P1-005-R4-VOICE-translate-forwards-speed",
          voice.get("speed") == 1.25, str(voice))
    request = adapter.translate(
        voice_packet(speaking_pace=0.9), voice_context())
    check("CF-P1-005-R4-VOICE-translate-numeric-pace",
          request["voice_request"].get("speed") == 0.9)
    request = adapter.translate(voice_packet(), voice_context())
    check("CF-P1-005-R4-VOICE-translate-no-controls",
          "instruct" not in request["voice_request"]
          and "speed" not in request["voice_request"])

    # Submit sends instruct + speed to /generate, and never sends
    # an unsupported control even when hand-built into a request.
    captured = []
    capturing = VoiceStudioAdapter(
        workspace_root=workspace,
        http_client=mock_voicestudio(capture=captured))
    request = capturing.prepare(
        voice_packet(speaking_pace="1.25"),
        voice_context(instruct="[laughter]"))
    result = capturing.submit(request, voice_context())
    body = b"".join(data or b"" for _m, _u, data in captured
                    if _u.endswith("/generate"))
    check("CF-P1-005-R4-VOICE-submit-sends-instruct",
          b'name="instruct"' in body
          and b"[laughter]" in body)
    check("CF-P1-005-R4-VOICE-submit-sends-speed",
          b'name="speed"' in body and b"1.25" in body)
    check("CF-P1-005-R4-VOICE-submit-completed",
          result.get("completed") is True)
    captured.clear()
    hand_built = {"voice_request": {
        "text": "Hello.", "language": "bn",
        "profile_id": "vp-test-001", "seed": None,
        "emotional_delivery": "happy", "pitch_range": "high",
        "pauses": "0.5s", "vocal_characteristics": "warm",
        "pronunciation_preferences": "roll the r"}}
    capturing.submit(hand_built, voice_context())
    body = b"".join(data or b"" for _m, _u, data in captured
                    if _u.endswith("/generate"))
    check("CF-P1-005-R4-VOICE-submit-never-sends-unsupported",
          all(name not in body for name in
              (b"emotional_delivery", b"pitch_range", b"pauses",
               b"vocal_characteristics",
               b"pronunciation_preferences")),
          repr(body[:400]))

    # The registry advertises exactly the supported controls.
    with open(os.path.join(ROOT_ABS, "registry",
                           "providers.json"),
              encoding="utf-8") as handle:
        registry = json.load(handle)
    records = {r["provider_id"]: r
               for r in registry.get("records") or []}
    record = records.get("provider-voicestudio-omnivoice") or {}
    controls = record.get("voice_controls") or {}
    check("CF-P1-005-R4-VOICE-registry-supported",
          controls.get("supported") == ["instruct", "speed", "seed"],
          str(controls))
    check("CF-P1-005-R4-VOICE-registry-unsupported",
          set(controls.get("unsupported") or {}) == set(UNSUPPORTED),
          str(controls))
    check("CF-P1-005-R4-VOICE-registry-commercial-blocked",
          record.get("commercial_use_approved") is False)
    # The record still validates against the capability schema.
    try:
        import jsonschema
        with open(os.path.join(ROOT_ABS, "schemas",
                               "provider-capability.json"),
                  encoding="utf-8") as handle:
            schema = json.load(handle)
        jsonschema.validate(record, schema)
        check("CF-P1-005-R4-VOICE-registry-schema-valid", True)
    except ImportError:
        print("SKIP CF-P1-005-R4-VOICE-registry-schema-valid: "
              "jsonschema not installed")
    except Exception as exc:  # noqa: BLE001 - validation failure
        check("CF-P1-005-R4-VOICE-registry-schema-valid", False,
              str(exc))

    print(f"--- CF-P1-005-R4-VOICE: {_checks[0]} checks, "
          f"{len(failures)} failures ---")
    if failures:
        print("FAILURES: " + ", ".join(failures))
        return 1
    return 0


def main():
    return run_checks()


if __name__ == "__main__":
    sys.exit(main())
