#!/usr/bin/env python3
"""Provider adapter tests (CF-WO-P1-005, WO §4 + §5 + §6).

Covers: the VoiceStudio safe wrapper against a mock HTTP backend
(preflight commercial/consent/language/voice-profile checks,
health, multipart submit saving a real WAV, WAV verification);
the OpenMontage thin adapter (checkout verification against the
real bundled component, fail-closed submit); OpenTimelineIO probe
(not installed, never mandatory); the HTTP provider adapter over
mock transports (sync base64 image, async video submit + poll,
cancellation, credential handling, secret redaction, uncertain
submission); and the adapter factory (Sora refused — shut down).

No live provider call is made anywhere in this suite: every
external provider is exercised through an injected mock transport,
and credentials are fake test values in the process environment
only, restored afterwards.

Conventions follow tests/test_production_store.py: check(name, cond,
detail="") prints PASS/FAIL lines, failures are collected, and the
process exits 0 only when every check passes. No test here weakens
any P0 or P1 check.
"""

import base64
import hashlib
import io
import json
import os
import struct
import sys
import tempfile
import wave

ROOT = os.path.join(os.path.dirname(__file__), "..")
ROOT_ABS = os.path.abspath(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
from runtime.media_adapters import (  # noqa: E402
    PROVIDER_SECRET_ENV, PROVIDER_SPECS, HttpProviderAdapter,
    OpenMontageAdapter, VoiceStudioAdapter, _redact, get_adapter,
    probe_opentimelineio, resolve_provider_secret)
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


def expect_error(label, fn):
    try:
        fn()
    except MediaExecutionError:
        check(label, True)
        return
    except Exception as exc:  # noqa: BLE001 - any other error is a fail
        check(label, False, f"raised {type(exc).__name__}: {exc}")
        return
    check(label, False, "operation succeeded instead of refusing")


def make_wav_bytes(seconds=1, rate=8000):
    """One second of silence as a valid 16-bit mono WAV."""
    frames = b"\x00\x00" * (rate * seconds)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(frames)
    return buf.getvalue()


# A minimal 1x1 transparent PNG.
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")


def set_env(name, value):
    old = os.environ.get(name)
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value
    return old


def restore_env(name, old):
    if old is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = old


def voice_packet():
    return {
        "task_id": "task-voice-001",
        "task_type": "voice-generation",
        "canonical_instruction": "Say hello.",
        "voice_binding": {
            "voice_profile_id": "vp-test-001",
            "dialogue_line_id": "l-01",
            "dialogue_text": "Hello.",
            "language": "bn",
            "character_id": "char-001",
        },
    }


def voice_context(**extra):
    context = {"voice_consent": True,
               "voice_profile_id": "vp-test-001",
               "execution_id": "exec-voice-test"}
    context.update(extra)
    return context


def mock_voicestudio(status=200, audio_id="audio-test-001",
                     health_status="ok", health_engine="omnivoice",
                     capture=None):
    wav = make_wav_bytes()

    def client(method, url, *, data=None, headers=None, files=None):
        if capture is not None:
            capture.append((method, url, data))
        if url.endswith("/health"):
            if health_status == "starting":
                return (503, {}, b"starting")
            return (200, {},
                    json.dumps({"status": "ok", "device": "cpu",
                                "engine": health_engine,
                                "version": "0.5.8"}).encode("utf-8"))
        if url.endswith("/generate"):
            return (status, {"x-audio-id": audio_id}, wav)
        return (404, {}, b"not found")
    return client


def voicestudio_group(tmpdir):
    """CF-P1-005-ADAPTERS: VoiceStudio safe wrapper (mock backend)."""
    workspace = os.path.join(tmpdir, "voice-workspace")
    os.makedirs(workspace)
    adapter = VoiceStudioAdapter(
        workspace_root=workspace,
        http_client=mock_voicestudio())
    check("CF-P1-005-ADAPTERS-vs-health",
          adapter.health().get("engine") == "omnivoice")
    check("CF-P1-005-ADAPTERS-vs-preflight-ok",
          adapter.preflight(voice_packet(),
                            voice_context()) == [])
    check("CF-P1-005-ADAPTERS-vs-preflight-commercial",
          len(adapter.preflight(
              voice_packet(),
              voice_context(commercial_use=True))) > 0)
    check("CF-P1-005-ADAPTERS-vs-preflight-no-consent",
          len(adapter.preflight(
              voice_packet(),
              voice_context(voice_consent=False))) > 0)
    bad_lang = voice_packet()
    bad_lang["voice_binding"] = dict(bad_lang["voice_binding"])
    bad_lang["voice_binding"]["language"] = "fr"
    check("CF-P1-005-ADAPTERS-vs-preflight-bad-language",
          len(adapter.preflight(bad_lang, voice_context())) > 0)
    no_line = voice_packet()
    no_line["voice_binding"] = dict(no_line["voice_binding"])
    del no_line["voice_binding"]["dialogue_line_id"]
    check("CF-P1-005-ADAPTERS-vs-preflight-no-line",
          len(adapter.preflight(no_line, voice_context())) > 0)
    check("CF-P1-005-ADAPTERS-vs-preflight-wrong-profile",
          len(adapter.preflight(
              voice_packet(),
              voice_context(voice_profile_id="vp-other-001"))) > 0)
    # A cold backend reports no engine; the adapter pins omnivoice
    # on submit, so that is not a preflight failure — but a
    # different named engine is.
    cold = VoiceStudioAdapter(
        workspace_root=workspace,
        http_client=mock_voicestudio(health_engine=None))
    check("CF-P1-005-ADAPTERS-vs-preflight-cold-engine",
          cold.preflight(voice_packet(), voice_context()) == [])
    other_engine = VoiceStudioAdapter(
        workspace_root=workspace,
        http_client=mock_voicestudio(health_engine="other-engine"))
    check("CF-P1-005-ADAPTERS-vs-preflight-other-engine",
          len(other_engine.preflight(voice_packet(),
                                     voice_context())) > 0)

    starting = VoiceStudioAdapter(
        workspace_root=workspace,
        http_client=mock_voicestudio(health_status="starting"))
    check("CF-P1-005-ADAPTERS-vs-preflight-starting",
          len(starting.preflight(voice_packet(),
                                 voice_context())) > 0)
    expect_error("CF-P1-005-ADAPTERS-vs-health-503",
                 lambda: starting.health())

    down = VoiceStudioAdapter(
        workspace_root=workspace,
        http_client=lambda *a, **k: (_ for _ in ()).throw(
            MediaExecutionError("down", code="service-unavailable")))
    check("CF-P1-005-ADAPTERS-vs-preflight-down",
          len(down.preflight(voice_packet(), voice_context())) > 0)

    # Submit: a real WAV is saved under outputs/ and verified.
    captured = []
    capturing = VoiceStudioAdapter(
        workspace_root=workspace,
        http_client=mock_voicestudio(capture=captured))
    request = capturing.prepare(voice_packet(), voice_context())
    result = capturing.submit(request, voice_context())
    check("CF-P1-005-ADAPTERS-vs-submit-pins-engine",
          any(b"engine" in (data or b"")
              and b"omnivoice" in (data or b"")
              for _m, _u, data in captured))
    check("CF-P1-005-ADAPTERS-vs-submit-completed",
          result.get("completed") is True
          and result.get("output") is not None)
    artifact = result["output"]
    wav_path = os.path.join(workspace, artifact["path"])
    check("CF-P1-005-ADAPTERS-vs-submit-file",
          os.path.isfile(wav_path)
          and artifact["path"] == os.path.join(
              "outputs", "exec-voice-test.wav"))
    with open(wav_path, "rb") as handle:
        saved = handle.read()
    check("CF-P1-005-ADAPTERS-vs-submit-hash",
          artifact["sha256"] == hashlib.sha256(saved).hexdigest())
    check("CF-P1-005-ADAPTERS-vs-submit-model",
          artifact.get("provider_model") == "omnivoice"
          and artifact.get("provider_audio_id") == "audio-test-001")
    check("CF-P1-005-ADAPTERS-vs-submit-duration",
          artifact.get("duration_seconds") is not None
          and abs(artifact["duration_seconds"] - 1.0) < 0.05)
    verified = adapter.verify_output(artifact["path"], None, {})
    check("CF-P1-005-ADAPTERS-vs-verify-wav",
          verified.get("duration_seconds") is not None
          and len(verified.get("audio_streams") or []) == 1)

    expect_error("CF-P1-005-ADAPTERS-vs-submit-no-text",
                 lambda: adapter.submit({"voice_request": {"text": ""}},
                                        voice_context()))
    # Loopback-only: a non-loopback base URL is refused outright.
    remote = VoiceStudioAdapter(workspace_root=workspace,
                                base_url="http://example.com:3900")
    expect_error("CF-P1-005-ADAPTERS-vs-nonloopback-refused",
                 lambda: remote.health())


def openmontage_group(tmpdir):
    """CF-P1-005-ADAPTERS: OpenMontage thin adapter (real checkout)."""
    component_root = os.path.join(ROOT_ABS, "components", "openmontage")
    workspace = os.path.join(tmpdir, "om-workspace")
    os.makedirs(workspace)
    if not os.path.isdir(component_root):
        print("SKIP CF-P1-005-ADAPTERS-om: component not present")
        return
    adapter = OpenMontageAdapter(component_root=component_root,
                                 workspace_root=workspace)
    try:
        verified = adapter.verify_checkout()
    except MediaExecutionError as exc:
        check("CF-P1-005-ADAPTERS-om-checkout",
              False, "; ".join(exc.errors))
        return
    check("CF-P1-005-ADAPTERS-om-checkout",
          verified.get("head") == "fecb9a1e3cc23ef84de30b272059457a427f16f8"
          and "OpenMontageInc/OpenMontage" in verified.get("origin", ""))
    packet = {"task_id": "task-om-001", "task_type": "media-technical"}
    check("CF-P1-005-ADAPTERS-om-preflight-ok",
          adapter.preflight(packet, {}) == [])
    request = adapter.translate(packet, {
        "composition": "demo-001",
        "clips": ["media/a.mp4", "media/b.mp4"],
        "output": "outputs/demo-001.mp4"})
    check("CF-P1-005-ADAPTERS-om-translate",
          request.get("pipeline", {}).get("composition") == "demo-001"
          and len(request["pipeline"]["clips"]) == 2)
    # Production submit without a verified entry fails closed.
    expect_error("CF-P1-005-ADAPTERS-om-submit-no-composition",
                 lambda: adapter.submit({"pipeline": {}}, {}))
    expect_error("CF-P1-005-ADAPTERS-om-submit-empty-composition",
                 lambda: adapter.submit(
                     {"pipeline": {"composition": ""}}, {}))
    missing = OpenMontageAdapter(
        component_root=os.path.join(tmpdir, "no-such-component"),
        workspace_root=workspace)
    check("CF-P1-005-ADAPTERS-om-preflight-missing",
          len(missing.preflight(packet, {})) > 0)


def otio_group():
    """CF-P1-005-ADAPTERS: OpenTimelineIO is optional, never mandatory."""
    probe = probe_opentimelineio()
    check("CF-P1-005-ADAPTERS-otio-unavailable",
          probe.get("installed") is False)
    check("CF-P1-005-ADAPTERS-otio-reason",
          isinstance(probe.get("reason"), str)
          and len(probe["reason"]) > 0)


def credentials_group():
    """CF-P1-005-ADAPTERS: secrets only from allow-listed env vars."""
    old = set_env("ELEVENLABS_API_KEY", "test-key-abc-123")
    try:
        check("CF-P1-005-ADAPTERS-secret-from-env",
              resolve_provider_secret("provider-elevenlabs-voice")
              == "test-key-abc-123")
        check("CF-P1-005-ADAPTERS-secret-redacted",
              "test-key-abc-123" not in _redact(
                  "failed with test-key-abc-123 in it",
                  secrets=("test-key-abc-123",)))
    finally:
        restore_env("ELEVENLABS_API_KEY", old)
    old = set_env("ELEVENLABS_API_KEY", None)
    try:
        expect_error("CF-P1-005-ADAPTERS-secret-missing",
                     lambda: resolve_provider_secret(
                         "provider-elevenlabs-voice"))
    finally:
        restore_env("ELEVENLABS_API_KEY", old)
    expect_error("CF-P1-005-ADAPTERS-secret-no-var",
                 lambda: resolve_provider_secret("provider-ffmpeg"))


def http_provider_group(tmpdir):
    """CF-P1-005-ADAPTERS: HTTP provider adapter over mock transports."""
    workspace = os.path.join(tmpdir, "http-workspace")
    os.makedirs(workspace)

    # Sync image provider (OpenAI Images API, official docs):
    # base64 output in the response body.
    openai_spec = dict(PROVIDER_SPECS["provider-openai-image"])
    openai_spec["provider_id"] = "provider-openai-image"
    calls = []

    def image_transport(method, url, *, headers=None, body=None):
        calls.append((method, url, headers or {}))
        payload = {"data": [{"b64_json": base64.b64encode(
            PNG_1X1).decode("ascii")}]}
        return (200, {"content-type": "application/json"},
                json.dumps(payload).encode("utf-8"))

    old = set_env("OPENAI_API_KEY", "test-openai-key")
    try:
        adapter = HttpProviderAdapter(
            openai_spec, workspace_root=workspace,
            transport=image_transport)
        packet = {"task_id": "task-img-001",
                  "task_type": "image-generation",
                  "canonical_instruction": "a red boat on a river"}
        check("CF-P1-005-ADAPTERS-http-preflight-ok",
              adapter.preflight(packet, {}) == [])
        request = adapter.prepare(packet, {"execution_id": "exec-img-001"})
        result = adapter.submit(request, {"execution_id": "exec-img-001"})
        check("CF-P1-005-ADAPTERS-http-sync-completed",
              result.get("completed") is True
              and result.get("output") is not None)
        artifact = result["output"]
        with open(os.path.join(workspace, artifact["path"]),
                  "rb") as handle:
            saved = handle.read()
        check("CF-P1-005-ADAPTERS-http-sync-bytes",
              saved == PNG_1X1
              and artifact["sha256"]
              == hashlib.sha256(PNG_1X1).hexdigest())
        check("CF-P1-005-ADAPTERS-http-auth-header",
              calls and calls[0][2].get("Authorization")
              == "Bearer test-openai-key")
        check("CF-P1-005-ADAPTERS-http-key-not-in-artifact",
              "test-openai-key" not in json.dumps(artifact))
        # A 401 is a provider error, not a silent failure.
        def auth_transport(method, url, *, headers=None, body=None):
            return (401, {}, b"invalid api key")
        bad = HttpProviderAdapter(
            openai_spec, workspace_root=workspace,
            transport=auth_transport)
        expect_error("CF-P1-005-ADAPTERS-http-401-provider-error",
                     lambda: bad.submit(
                         bad.prepare(packet, {}), {}))
        # A transport failure after send is submission-uncertain.
        def cut_transport(method, url, *, headers=None, body=None):
            raise ConnectionError("connection reset by peer")
        cut = HttpProviderAdapter(
            openai_spec, workspace_root=workspace,
            transport=cut_transport)
        try:
            cut.submit(cut.prepare(packet, {}), {})
            check("CF-P1-005-ADAPTERS-http-cut-uncertain", False,
                  "transport failure did not raise")
        except MediaExecutionError as exc:
            check("CF-P1-005-ADAPTERS-http-cut-uncertain",
                  exc.code == "submission-uncertain")
        # A synchronous provider has no poll.
        expect_error("CF-P1-005-ADAPTERS-http-sync-no-poll",
                     lambda: adapter.poll("job-1", {}))
    finally:
        restore_env("OPENAI_API_KEY", old)

    # Missing credential fails closed in preflight.
    old = set_env("OPENAI_API_KEY", None)
    try:
        adapter = HttpProviderAdapter(
            openai_spec, workspace_root=workspace,
            transport=image_transport)
        check("CF-P1-005-ADAPTERS-http-preflight-no-credential",
              len(adapter.preflight(
                  {"task_id": "task-img-001",
                   "task_type": "image-generation"}, {})) > 0)
    finally:
        restore_env("OPENAI_API_KEY", old)

    # Async video provider (Veo): submit returns an operation id,
    # poll reports running, then failed, then cancelled.
    veo_spec = dict(PROVIDER_SPECS["provider-veo-video"])
    veo_spec["provider_id"] = "provider-veo-video"
    old = set_env("VERTEX_ACCESS_TOKEN", "test-vertex-token")
    try:
        veo_project = "test-project-1"
        veo_operation = ("projects/" + veo_project
                         + "/locations/us-central1/publishers/google/"
                         "models/veo-3.1-generate-001/operations/"
                         "veo-job-001")
        veo_context = {"execution_id": "exec-veo-adapter-001",
                       "vertex_project_id": veo_project}

        def veo_transport(method, url, *, headers=None, body=None):
            if method == "POST":
                return (200, {},
                        json.dumps(
                            {"name": veo_operation}
                        ).encode("utf-8"))
            return (200, {}, json.dumps(
                {"done": False}).encode("utf-8"))

        adapter = HttpProviderAdapter(
            veo_spec, workspace_root=workspace,
            transport=veo_transport)
        packet = {"task_id": "task-vid-001",
                  "task_type": "video-generation",
                  "canonical_instruction": "a boat crosses the river"}
        request = adapter.prepare(packet, veo_context)
        result = adapter.submit(request, veo_context)
        check("CF-P1-005-ADAPTERS-http-async-accepted",
              result.get("completed") is False
              and result.get("provider_job_id") == veo_operation)
        # R4 follow-up: the job id IS the full Vertex operation
        # name from the submit response; poll POSTs it to the
        # documented :fetchPredictOperation endpoint — no caller
        # supplied status_url is accepted anymore (the old test
        # passed an unapproved example.invalid URL, which the URL
        # security policy now refuses before any request).
        seen_polls = []

        def veo_poll_transport(method, url, *, headers=None, body=None):
            seen_polls.append((method, url, body))
            return (200, {}, json.dumps(
                {"done": False}).encode("utf-8"))
        adapter.transport = veo_poll_transport
        polled = adapter.poll(veo_operation, veo_context)
        check("CF-P1-005-ADAPTERS-http-async-still-running",
              polled.get("completed") is False)
        check("CF-P1-005-ADAPTERS-http-poll-template-url",
              len(seen_polls) == 1
              and seen_polls[0][0] == "POST"
              and seen_polls[0][1] == "https://us-central1-"
              "aiplatform.googleapis.com/v1/projects/"
              + veo_project + "/locations/us-central1/publishers/"
              "google/models/veo-3.1-generate-001:"
              "fetchPredictOperation"
              and json.loads(seen_polls[0][2].decode("utf-8"))
              == {"operationName": veo_operation},
              str(seen_polls))
        # A provider with no poll template and no status_url in
        # the context still fails closed (fal.ai has no template:
        # its status_url comes from the submit response).
        fal_spec = dict(PROVIDER_SPECS["provider-fal-image"])
        fal_spec["provider_id"] = "provider-fal-image"
        old_fal = set_env("FAL_KEY", "test-fal-key")
        try:
            fal_adapter = HttpProviderAdapter(
                fal_spec, workspace_root=workspace,
                transport=veo_poll_transport)
            expect_error("CF-P1-005-ADAPTERS-http-poll-no-url",
                         lambda: fal_adapter.poll("fal-job-001", {}))
        finally:
            restore_env("FAL_KEY", old_fal)

        def failed_transport(method, url, *, headers=None, body=None):
            return (200, {}, json.dumps(
                {"done": True,
                 "error": {"status": "FAILED",
                           "message": "generation failed"}}
            ).encode("utf-8"))
        adapter.transport = failed_transport
        polled = adapter.poll(veo_operation, veo_context)
        check("CF-P1-005-ADAPTERS-http-async-failed",
              polled.get("completed") is True
              and polled["failure"]["code"] == "provider-error")

        def cancelled_transport(method, url, *, headers=None,
                                body=None):
            return (200, {}, json.dumps(
                {"done": True,
                 "error": {"status": "CANCELLED", "code": 499,
                           "message": "operation cancelled"}}
            ).encode("utf-8"))
        adapter.transport = cancelled_transport
        polled = adapter.poll(veo_operation, veo_context)
        check("CF-P1-005-ADAPTERS-http-async-cancelled",
              polled.get("completed") is True
              and polled["failure"]["code"] == "cancelled-by-provider")

        # A provider with no documented cancellation refuses it.
        expect_error("CF-P1-005-ADAPTERS-http-cancel-unsupported",
                     lambda: adapter.cancel(
                         veo_operation,
                         {"cancel_url": "https://example.invalid/x"}))
    finally:
        restore_env("VERTEX_ACCESS_TOKEN", old)


def factory_group(tmpdir):
    """CF-P1-005-ADAPTERS: the adapter factory."""
    workspace = os.path.join(tmpdir, "factory-workspace")
    os.makedirs(workspace)
    expect_error("CF-P1-005-ADAPTERS-factory-sora-refused",
                 lambda: get_adapter("provider-sora-video",
                                     workspace_root=workspace))
    expect_error("CF-P1-005-ADAPTERS-factory-unknown-refused",
                 lambda: get_adapter("provider-no-such",
                                     workspace_root=workspace))
    ffmpeg = get_adapter("provider-ffmpeg", workspace_root=workspace)
    check("CF-P1-005-ADAPTERS-factory-ffmpeg",
          ffmpeg.adapter_id == "adapter-ffmpeg")
    voice = get_adapter("provider-voicestudio-omnivoice",
                        workspace_root=workspace)
    check("CF-P1-005-ADAPTERS-factory-voicestudio",
          voice.adapter_id == "adapter-voicestudio")
    image = get_adapter("provider-openai-image",
                        workspace_root=workspace)
    check("CF-P1-005-ADAPTERS-factory-openai",
          image.adapter_id == "adapter-openai-image")
    # Every live spec carries the fields the WO §5 audit requires,
    # plus the R4-A origin allowlists (api + output, separate).
    required = ("documentation_url", "documentation_status",
                "api_version", "async_behaviour",
                "cancellation_support", "output_retrieval",
                "charge_behaviour", "character_reference_limits",
                "api_origins", "output_origins")
    missing = {pid: [f for f in required if f not in spec]
               for pid, spec in PROVIDER_SPECS.items()}
    check("CF-P1-005-ADAPTERS-specs-complete",
          all(not fields for fields in missing.values()),
          json.dumps(missing))
    check("CF-P1-005-ADAPTERS-specs-nine-live",
          len(PROVIDER_SPECS) == 9, str(len(PROVIDER_SPECS)))
    check("CF-P1-005-ADAPTERS-no-sora-spec",
          "provider-sora-video" not in PROVIDER_SPECS)


def main():
    tmpdir = tempfile.mkdtemp(prefix="cf-p1-005-adapters-")
    voicestudio_group(tmpdir)
    openmontage_group(tmpdir)
    otio_group()
    credentials_group()
    http_provider_group(tmpdir)
    factory_group(tmpdir)
    print(f"--- CF-P1-005-ADAPTERS: {_checks[0]} checks, "
          f"{len(failures)} failures ---")
    if failures:
        print("FAILURES: " + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
