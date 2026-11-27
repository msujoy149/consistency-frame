#!/usr/bin/env python3
"""Provider contract tests (CF-WO-P1-005-R4, workstream B).

Covers the provider-specific request builders + response parsers
in ``runtime/provider_contracts.py`` as wired through
``HttpProviderAdapter``: one exact contract per live provider
(OpenAI image, Gemini image, fal image, Veo video, Kling video,
LTX video, ElevenLabs voice, Lyria music). Each provider group
pins the exact method, endpoint pattern, auth header, required
and optional request fields, invalid/missing inputs, the
successful sync response (where applicable), the accepted async
job response (where applicable), running/success/failure poll
states, cancellation (only where officially supported), malformed
responses, missing output, incorrect content type, output
download failure, size-limit enforcement, and submission
uncertainty without automatic duplicate charge.

A test here MUST fail if the generic ``{model, prompt}`` payload
is accidentally used where the provider's contract differs: the
adapter refuses any submit whose request was not built by a
contract, and several groups assert exact request bodies.

No live provider call is made anywhere in this suite: every
provider is exercised through an injected mock transport,
credentials are fake test values in the process environment only,
and providers stay NOT_TESTED until real evidence exists — mock
tests alone never make a provider EXERCISED or VERIFIED.

Conventions follow tests/test_media_adapters.py: check(name,
cond, detail="") prints PASS/FAIL lines, failures are collected,
and the process exits 0 only when every check passes. No test
here weakens any P0 or P1 check.
"""

import base64
import hashlib
import json
import os
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(__file__), "..")
ROOT_ABS = os.path.abspath(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
from runtime.media_adapters import (  # noqa: E402
    PROVIDER_SPECS, HttpProviderAdapter)
from runtime.media_execution import MediaExecutionError  # noqa: E402
from runtime.provider_contracts import (  # noqa: E402
    CONTRACTS, get_contract)

failures = []
_checks = [0]

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
MP3_BYTES = b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 64
WAV_BYTES = (b"RIFF" + (36).to_bytes(4, "little") + b"WAVEfmt "
             + (16).to_bytes(4, "little") + b"\x01\x00\x01\x00"
             + (8000).to_bytes(4, "little")
             + (16000).to_bytes(4, "little") + b"\x02\x00\x10\x00"
             + b"data" + (0).to_bytes(4, "little"))


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


def expect_code(label, code, fn):
    try:
        fn()
    except MediaExecutionError as exc:
        check(label, exc.code == code,
              f"code={exc.code!r} want {code!r}")
        return
    except Exception as exc:  # noqa: BLE001 - any other error is a fail
        check(label, False, f"raised {type(exc).__name__}: {exc}")
        return
    check(label, False, "operation succeeded instead of refusing")


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


def make_adapter(provider_id, workspace, transport, **kwargs):
    spec = dict(PROVIDER_SPECS[provider_id])
    spec["provider_id"] = provider_id
    return HttpProviderAdapter(spec, workspace_root=workspace,
                               transport=transport, **kwargs)


def recording_transport(responder):
    calls = []

    def transport(method, url, *, headers=None, body=None):
        calls.append((method, url, dict(headers or {}), body))
        return responder(method, url, headers=dict(headers or {}),
                         body=body)

    return transport, calls


def packet(task_type, instruction, model=None):
    data = {"task_id": "task-contracts-001",
            "task_type": task_type,
            "canonical_instruction": instruction}
    if model is not None:
        data["model"] = model
    return data


def json_body(call):
    return json.loads(call[3].decode("utf-8"))


def saved_bytes(workspace, artifact):
    with open(os.path.join(workspace, artifact["path"]),
              "rb") as handle:
        return handle.read()


# ---------------------------------------------------------------------
# OpenAI image (synchronous)
# ---------------------------------------------------------------------

def openai_group(tmpdir):
    """CF-P1-005-R4-CONTRACTS: OpenAI Images API contract."""
    workspace = os.path.join(tmpdir, "openai-workspace")
    os.makedirs(workspace)
    old = set_env("OPENAI_API_KEY", "test-openai-key")
    try:
        calls = []

        def image_transport(method, url, *, headers=None, body=None):
            calls.append((method, url, dict(headers or {}), body))
            payload = {"data": [{"b64_json": base64.b64encode(
                PNG_1X1).decode("ascii")}]}
            return (200, {"content-type": "application/json"},
                    json.dumps(payload).encode("utf-8"))

        adapter = make_adapter("provider-openai-image", workspace,
                               image_transport)
        request = adapter.prepare(
            packet("image-generation", "a red boat on a river"),
            {"execution_id": "exec-oai-001"})
        check("CF-P1-005-R4-CONTRACTS-openai-endpoint",
              calls == [] and request["request"]["model"]
              == "gpt-image-1-mini")
        result = adapter.submit(request, {"execution_id": "exec-oai-001"})
        check("CF-P1-005-R4-CONTRACTS-openai-method-url",
              len(calls) == 1 and calls[0][0] == "POST"
              and calls[0][1] == "https://api.openai.com/v1/images/"
                                 "generations",
              str([c[1] for c in calls]))
        check("CF-P1-005-R4-CONTRACTS-openai-auth",
              calls[0][2].get("Authorization")
              == "Bearer test-openai-key")
        body = json_body(calls[0])
        check("CF-P1-005-R4-CONTRACTS-openai-exact-body",
              body == {"model": "gpt-image-1-mini",
                       "prompt": "a red boat on a river", "n": 1},
              str(body))
        check("CF-P1-005-R4-CONTRACTS-openai-sync-completed",
              result.get("completed") is True
              and result.get("output") is not None)
        artifact = result["output"]
        check("CF-P1-005-R4-CONTRACTS-openai-sync-bytes",
              saved_bytes(workspace, artifact) == PNG_1X1
              and artifact["sha256"]
              == hashlib.sha256(PNG_1X1).hexdigest())
        check("CF-P1-005-R4-CONTRACTS-openai-key-not-in-artifact",
              "test-openai-key" not in json.dumps(artifact))

        # Optional fields travel exactly; an unknown model is refused.
        transport, calls2 = recording_transport(image_transport)
        adapter2 = make_adapter("provider-openai-image", workspace,
                                transport)
        request2 = adapter2.prepare(
            packet("image-generation", "a boat",
                   model="gpt-image-2.5-sunburst"),
            {"execution_id": "exec-oai-002", "size": "1024x1024",
             "quality": "high", "output_format": "png"})
        adapter2.submit(request2, {"execution_id": "exec-oai-002"})
        body2 = json_body(calls2[0])
        check("CF-P1-005-R4-CONTRACTS-openai-optional-fields",
              body2.get("size") == "1024x1024"
              and body2.get("quality") == "high"
              and body2.get("output_format") == "png"
              and body2.get("model") == "gpt-image-2.5-sunburst",
              str(body2))
        expect_error("CF-P1-005-R4-CONTRACTS-openai-retired-model",
                     lambda: adapter.prepare(
                         packet("image-generation", "x",
                                model="gpt-image-1"), {}))
        expect_error("CF-P1-005-R4-CONTRACTS-openai-dalle-retired",
                     lambda: adapter.prepare(
                         packet("image-generation", "x",
                                model="dall-e-3"), {}))
        expect_error("CF-P1-005-R4-CONTRACTS-openai-missing-prompt",
                     lambda: adapter.prepare(
                         packet("image-generation", ""), {}))
        expect_error("CF-P1-005-R4-CONTRACTS-openai-prompt-too-long",
                     lambda: adapter.prepare(
                         packet("image-generation", "x" * 32001), {}))
        expect_error("CF-P1-005-R4-CONTRACTS-openai-bad-quality",
                     lambda: adapter.prepare(
                         packet("image-generation", "x",
                                model="gpt-image-1.5"),
                         {"quality": "xhigh"}))

        # A 401 is authorization-denied, not a silent failure.
        def auth_transport(method, url, *, headers=None, body=None):
            return (401, {}, b"invalid api key")
        bad = make_adapter("provider-openai-image", workspace,
                           auth_transport)
        expect_code("CF-P1-005-R4-CONTRACTS-openai-401",
                    "authorization-denied",
                    lambda: bad.submit(
                        bad.prepare(packet("image-generation", "x"),
                                    {}), {}))

        # Malformed sync response: no data, no base64, bad JSON.
        def no_data(method, url, *, headers=None, body=None):
            return (200, {"content-type": "application/json"},
                    b'{"data": []}')
        nodata = make_adapter("provider-openai-image", workspace,
                              no_data)
        expect_error("CF-P1-005-R4-CONTRACTS-openai-missing-output",
                     lambda: nodata.submit(
                         nodata.prepare(packet("image-generation", "x"),
                                        {}), {}))

        def bad_json(method, url, *, headers=None, body=None):
            return (200, {"content-type": "application/json"},
                    b"not json at all")
        badjson = make_adapter("provider-openai-image", workspace,
                               bad_json)
        expect_error("CF-P1-005-R4-CONTRACTS-openai-malformed",
                     lambda: badjson.submit(
                         badjson.prepare(packet("image-generation", "x"),
                                         {}), {}))

        # Oversize response is refused before it is returned.
        def big(method, url, *, headers=None, body=None):
            return (200, {"content-type": "application/json"},
                    b'{"data": [{"b64_json": "' + b"A" * 100 + b'"}]}')
        small = make_adapter("provider-openai-image", workspace, big,
                             max_response_bytes=10)
        expect_error("CF-P1-005-R4-CONTRACTS-openai-size-limit",
                     lambda: small.submit(
                         small.prepare(packet("image-generation", "x"),
                                       {}), {}))

        # Edits: a reference image goes multipart to /images/edits.
        with open(os.path.join(workspace, "ref.png"),
                  "wb") as handle:
            handle.write(PNG_1X1)
        transport, calls3 = recording_transport(image_transport)
        adapter3 = make_adapter("provider-openai-image", workspace,
                                transport)
        request3 = adapter3.prepare(
            packet("image-generation", "put the boat in a storm"),
            {"execution_id": "exec-oai-003",
             "reference_images": [{"path": "ref.png"}]})
        adapter3.submit(request3, {"execution_id": "exec-oai-003"})
        check("CF-P1-005-R4-CONTRACTS-openai-edits-endpoint",
              calls3[0][1] == "https://api.openai.com/v1/images/edits",
              calls3[0][1])
        check("CF-P1-005-R4-CONTRACTS-openai-edits-multipart",
              calls3[0][2].get("Content-Type", "").startswith(
                  "multipart/form-data")
              and b"reference-1.png" in calls3[0][3]
              and PNG_1X1 in calls3[0][3])
        check("CF-P1-005-R4-CONTRACTS-openai-edits-prompt-field",
              b"put the boat in a storm" in calls3[0][3])
        # A reference outside the workspace is refused.
        expect_error("CF-P1-005-R4-CONTRACTS-openai-ref-escape",
                     lambda: adapter3.prepare(
                         packet("image-generation", "x"),
                         {"reference_images": [
                             {"path": "../outside.png"}]}))
    finally:
        restore_env("OPENAI_API_KEY", old)


# ---------------------------------------------------------------------
# Gemini image (synchronous, Interactions API)
# ---------------------------------------------------------------------

def gemini_group(tmpdir):
    """CF-P1-005-R4-CONTRACTS: Gemini image contract."""
    workspace = os.path.join(tmpdir, "gemini-workspace")
    os.makedirs(workspace)
    old = set_env("GEMINI_API_KEY", "test-gemini-key")
    try:
        def image_response(b64, mime="image/png"):
            return {"steps": [{"content": [
                {"type": "image", "data": b64, "mime_type": mime}]}]}

        def gemini_transport(method, url, *, headers=None, body=None):
            payload = image_response(base64.b64encode(
                PNG_1X1).decode("ascii"))
            return (200, {"content-type": "application/json"},
                    json.dumps(payload).encode("utf-8"))

        transport, calls = recording_transport(gemini_transport)
        adapter = make_adapter("provider-gemini-image", workspace,
                               transport)
        request = adapter.prepare(
            packet("image-generation", "a boat at dawn"),
            {"execution_id": "exec-gem-001", "aspect_ratio": "16:9",
             "image_size": "2K"})
        result = adapter.submit(request, {"execution_id": "exec-gem-001"})
        check("CF-P1-005-R4-CONTRACTS-gemini-method-url",
              len(calls) == 1 and calls[0][0] == "POST"
              and calls[0][1] == "https://generativelanguage."
                                 "googleapis.com/v1beta/interactions",
              str([c[1] for c in calls]))
        check("CF-P1-005-R4-CONTRACTS-gemini-auth-headers",
              calls[0][2].get("x-goog-api-key") == "test-gemini-key"
              and calls[0][2].get("Api-Revision") == "2026-05-20")
        body = json_body(calls[0])
        check("CF-P1-005-R4-CONTRACTS-gemini-exact-body",
              body == {"model": "gemini-nano-banana-2.1",
                       "input": [{"type": "text",
                                  "text": "a boat at dawn"}],
                       "response_format": {"type": "image",
                                           "aspect_ratio": "16:9",
                                           "image_size": "2K"}},
              str(body))
        check("CF-P1-005-R4-CONTRACTS-gemini-sync-bytes",
              result.get("completed") is True
              and saved_bytes(workspace, result["output"]) == PNG_1X1)

        # The deprecated 3.1-flash-image model is still accepted.
        transport, calls2 = recording_transport(gemini_transport)
        adapter2 = make_adapter("provider-gemini-image", workspace,
                                transport)
        request2 = adapter2.prepare(
            packet("image-generation", "x",
                   model="gemini-3.1-flash-image"),
            {"execution_id": "exec-gem-002"})
        adapter2.submit(request2, {"execution_id": "exec-gem-002"})
        check("CF-P1-005-R4-CONTRACTS-gemini-deprecated-model-ok",
              json_body(calls2[0])["model"]
              == "gemini-3.1-flash-image")
        # 15 reference images exceed the 14-image limit.
        refs = [{"mime": "image/png",
                 "base64": base64.b64encode(PNG_1X1).decode("ascii")}
                for _ in range(15)]
        expect_error("CF-P1-005-R4-CONTRACTS-gemini-too-many-refs",
                     lambda: adapter.prepare(
                         packet("image-generation", "x"),
                         {"reference_images": refs}))
        # Unknown model, bad aspect ratio, missing output.
        expect_error("CF-P1-005-R4-CONTRACTS-gemini-bad-model",
                     lambda: adapter.prepare(
                         packet("image-generation", "x",
                                model="gemini-1.0-pro"), {}))
        expect_error("CF-P1-005-R4-CONTRACTS-gemini-bad-aspect",
                     lambda: adapter.prepare(
                         packet("image-generation", "x"),
                         {"aspect_ratio": "7:3"}))
        # A response with no image step carries no output.
        def empty_steps(method, url, *, headers=None, body=None):
            return (200, {"content-type": "application/json"},
                    b'{"steps": []}')
        nodata = make_adapter("provider-gemini-image", workspace,
                              empty_steps)
        expect_error("CF-P1-005-R4-CONTRACTS-gemini-missing-output",
                     lambda: nodata.submit(
                         nodata.prepare(packet("image-generation", "x"),
                                        {}), {}))
    finally:
        restore_env("GEMINI_API_KEY", old)


# ---------------------------------------------------------------------
# fal image (asynchronous queue)
# ---------------------------------------------------------------------

def fal_group(tmpdir):
    """CF-P1-005-R4-CONTRACTS: fal.ai queue contract."""
    workspace = os.path.join(tmpdir, "fal-workspace")
    os.makedirs(workspace)
    old = set_env("FAL_KEY", "test-fal-key")
    try:
        submit_body = {"request_id": "fal-job-001",
                       "status_url": "https://queue.fal.run/"
                                     "fal-ai/nano-banana-2/requests/"
                                     "fal-job-001/status",
                       "response_url": "https://queue.fal.run/"
                                       "fal-ai/nano-banana-2/requests/"
                                       "fal-job-001",
                       "cancel_url": "https://queue.fal.run/"
                                     "fal-ai/nano-banana-2/requests/"
                                     "fal-job-001/cancel"}

        def submit_transport(method, url, *, headers=None, body=None):
            return (200, {"content-type": "application/json"},
                    json.dumps(submit_body).encode("utf-8"))

        transport, calls = recording_transport(submit_transport)
        adapter = make_adapter("provider-fal-image", workspace,
                               transport)
        request = adapter.prepare(
            packet("image-generation", "a boat on a river"),
            {"execution_id": "exec-fal-001"})
        result = adapter.submit(request, {"execution_id": "exec-fal-001"})
        check("CF-P1-005-R4-CONTRACTS-fal-method-url",
              len(calls) == 1 and calls[0][0] == "POST"
              and calls[0][1] == "https://queue.fal.run/"
                                 "fal-ai/nano-banana-2",
              str([c[1] for c in calls]))
        check("CF-P1-005-R4-CONTRACTS-fal-auth",
              calls[0][2].get("Authorization") == "Key test-fal-key")
        check("CF-P1-005-R4-CONTRACTS-fal-exact-body",
              json_body(calls[0]) == {"prompt": "a boat on a river"},
              str(json_body(calls[0])))
        check("CF-P1-005-R4-CONTRACTS-fal-accepted",
              result.get("completed") is False
              and result.get("provider_job_id") == "fal-job-001")

        # Optional fields are validated against the model docs.
        transport, calls2 = recording_transport(submit_transport)
        adapter2 = make_adapter("provider-fal-image", workspace,
                                transport)
        request2 = adapter2.prepare(
            packet("image-generation", "x"),
            {"num_images": 2, "aspect_ratio": "16:9",
             "resolution": "2K", "seed": 7})
        adapter2.submit(request2, {})
        body2 = json_body(calls2[0])
        check("CF-P1-005-R4-CONTRACTS-fal-optional-fields",
              body2.get("num_images") == 2
              and body2.get("aspect_ratio") == "16:9"
              and body2.get("resolution") == "2K"
              and body2.get("seed") == 7, str(body2))
        expect_error("CF-P1-005-R4-CONTRACTS-fal-num-images-range",
                     lambda: adapter.prepare(
                         packet("image-generation", "x"),
                         {"num_images": 5}))
        expect_error("CF-P1-005-R4-CONTRACTS-fal-bad-tolerance",
                     lambda: adapter.prepare(
                         packet("image-generation", "x"),
                         {"safety_tolerance": "7"}))
        expect_error("CF-P1-005-R4-CONTRACTS-fal-refs-refused",
                     lambda: adapter.prepare(
                         packet("image-generation", "x"),
                         {"reference_images": [
                             {"mime": "image/png", "base64": "AAAA"}]}))
        expect_error("CF-P1-005-R4-CONTRACTS-fal-bad-model",
                     lambda: adapter.prepare(
                         packet("image-generation", "x",
                                model="fal-ai/unknown"), {}))

        # A submit response missing its URLs is malformed.
        def short_submit(method, url, *, headers=None, body=None):
            return (200, {"content-type": "application/json"},
                    b'{"request_id": "fal-job-001"}')
        short = make_adapter("provider-fal-image", workspace,
                             short_submit)
        expect_error("CF-P1-005-R4-CONTRACTS-fal-submit-no-urls",
                     lambda: short.submit(
                         short.prepare(packet("image-generation", "x"),
                                       {}), {}))

        # Poll lifecycle: IN_QUEUE / IN_PROGRESS run; COMPLETED
        # fetches the result document, then downloads from fal.media
        # with the credential stripped.
        def poll_transport(method, url, *, headers=None, body=None):
            if url.endswith("/status"):
                return (200, {"content-type": "application/json"},
                        json.dumps(
                            {"status": "COMPLETED",
                             "response_url": submit_body[
                                 "response_url"]}).encode("utf-8"))
            if url == submit_body["response_url"]:
                return (200, {"content-type": "application/json"},
                        json.dumps(
                            {"images": [{"url": "https://fal.media/"
                                               "files/abc.png"}]}
                        ).encode("utf-8"))
            if url.startswith("https://fal.media/"):
                return (200, {"content-type": "image/png"}, PNG_1X1)
            return (404, {}, b"not found")

        transport, calls3 = recording_transport(poll_transport)
        adapter3 = make_adapter("provider-fal-image", workspace,
                                transport)
        polled = adapter3.poll("fal-job-001", {
            "status_url": submit_body["status_url"],
            "execution_id": "exec-fal-002"})
        check("CF-P1-005-R4-CONTRACTS-fal-poll-completed",
              polled.get("completed") is True
              and polled.get("output") is not None)
        check("CF-P1-005-R4-CONTRACTS-fal-download-bytes",
              saved_bytes(workspace, polled["output"]) == PNG_1X1)
        download_calls = [c for c in calls3
                          if c[1].startswith("https://fal.media/")]
        check("CF-P1-005-R4-CONTRACTS-fal-download-no-auth",
              len(download_calls) == 1
              and "Authorization" not in download_calls[0][2],
              str(download_calls))
        check("CF-P1-005-R4-CONTRACTS-fal-poll-urls",
              [c[1] for c in calls3] == [
                  submit_body["status_url"],
                  submit_body["response_url"],
                  "https://fal.media/files/abc.png"],
              str([c[1] for c in calls3]))

        def running_transport(status):
            def responder(method, url, *, headers=None, body=None):
                return (200, {"content-type": "application/json"},
                        json.dumps({"status": status}).encode("utf-8"))
            return responder
        for label, status in (("queue", "IN_QUEUE"),
                              ("progress", "IN_PROGRESS")):
            transport, _ = recording_transport(
                running_transport(status))
            running = make_adapter("provider-fal-image", workspace,
                                   transport)
            polled = running.poll("fal-job-001", {
                "status_url": submit_body["status_url"]})
            check("CF-P1-005-R4-CONTRACTS-fal-poll-running-" + label,
                  polled.get("completed") is False)
        # An undocumented poll status is malformed, never "running".
        transport, _ = recording_transport(
            running_transport("PROCESSING"))
        bad_status = make_adapter("provider-fal-image", workspace,
                                  transport)
        expect_error("CF-P1-005-R4-CONTRACTS-fal-poll-bad-status",
                     lambda: bad_status.poll(
                         "fal-job-001",
                         {"status_url": submit_body["status_url"]}))

        # Cancellation via the submit-returned cancel URL (PUT).
        def cancel_transport(method, url, *, headers=None, body=None):
            if method == "PUT":
                return (200, {}, b"{}")
            return (200, {"content-type": "application/json"},
                    json.dumps({"status": "IN_PROGRESS"})
                    .encode("utf-8"))
        transport, calls4 = recording_transport(cancel_transport)
        canceller = make_adapter("provider-fal-image", workspace,
                                 transport)
        check("CF-P1-005-R4-CONTRACTS-fal-cancel",
              canceller.cancel("fal-job-001", {
                  "cancel_url": submit_body["cancel_url"]}) is True
              and calls4[0][0] == "PUT"
              and calls4[0][1] == submit_body["cancel_url"])

        # A failed result fetch is a provider error, not a download.
        def result_500(method, url, *, headers=None, body=None):
            if url.endswith("/status"):
                return (200, {"content-type": "application/json"},
                        json.dumps(
                            {"status": "COMPLETED",
                             "response_url": submit_body[
                                 "response_url"]}).encode("utf-8"))
            return (500, {}, b"upstream error")
        failing = make_adapter("provider-fal-image", workspace,
                               result_500)
        expect_error("CF-P1-005-R4-CONTRACTS-fal-result-fetch-fails",
                     lambda: failing.poll(
                         "fal-job-001",
                         {"status_url": submit_body["status_url"]}))

        # Submission uncertainty: a cut transport never resubmits.
        def cut_transport(method, url, *, headers=None, body=None):
            raise ConnectionError("connection reset by peer")
        cut = make_adapter("provider-fal-image", workspace,
                           cut_transport)
        expect_code("CF-P1-005-R4-CONTRACTS-fal-uncertain",
                    "submission-uncertain",
                    lambda: cut.submit(
                        cut.prepare(packet("image-generation", "x"),
                                    {}), {}))
    finally:
        restore_env("FAL_KEY", old)


# ---------------------------------------------------------------------
# Veo video (asynchronous long-running operation)
# ---------------------------------------------------------------------

# Veo video (asynchronous long-running operation, Vertex AI)
# ---------------------------------------------------------------------

def veo_group(tmpdir):
    """CF-P1-005-R4-CONTRACTS: Veo video contract (Vertex AI)."""
    workspace = os.path.join(tmpdir, "veo-workspace")
    os.makedirs(workspace)
    old = set_env("VERTEX_ACCESS_TOKEN", "test-vertex-token")
    try:
        project = "test-project-1"
        model = "veo-3.1-generate-001"
        operation = ("projects/" + project + "/locations/us-central1/"
                     "publishers/google/models/" + model
                     + "/operations/veo-job-001")
        submit_url = ("https://us-central1-aiplatform.googleapis.com/"
                      "v1/projects/" + project + "/locations/"
                      "us-central1/publishers/google/models/" + model
                      + ":predictLongRunning")
        poll_url = ("https://us-central1-aiplatform.googleapis.com/"
                    "v1/projects/" + project + "/locations/"
                    "us-central1/publishers/google/models/" + model
                    + ":fetchPredictOperation")

        def ctx(**extra):
            data = {"execution_id": "exec-veo-001",
                    "vertex_project_id": project}
            data.update(extra)
            return data

        def submit_transport(method, url, *, headers=None, body=None):
            return (200, {"content-type": "application/json"},
                    json.dumps({"name": operation}).encode("utf-8"))

        transport, calls = recording_transport(submit_transport)
        adapter = make_adapter("provider-veo-video", workspace,
                               transport)
        request = adapter.prepare(
            packet("video-generation", "a boat crosses the river"),
            ctx())
        result = adapter.submit(request, ctx())
        check("CF-P1-005-R4-CONTRACTS-veo-method-url",
              len(calls) == 1 and calls[0][0] == "POST"
              and calls[0][1] == submit_url,
              str([c[1] for c in calls]))
        check("CF-P1-005-R4-CONTRACTS-veo-auth",
              calls[0][2].get("Authorization")
              == "Bearer test-vertex-token"
              and "x-goog-api-key" not in calls[0][2],
              str(calls[0][2]))
        body = json_body(calls[0])
        check("CF-P1-005-R4-CONTRACTS-veo-exact-body",
              body == {"instances": [
                           {"prompt": "a boat crosses the river"}],
                       "parameters": {"aspectRatio": "16:9",
                                      "resolution": "720p",
                                      "durationSeconds": "8",
                                      "sampleCount": 1}},
              str(body))
        check("CF-P1-005-R4-CONTRACTS-veo-accepted-full-op-name",
              result.get("completed") is False
              and result.get("provider_job_id") == operation)

        # 1080p/4K require 8 seconds; Lite takes no references
        # (UNCONFIRMED); Fast 4K is UNCONFIRMED; the dead Gemini
        # API preview IDs are refused.
        expect_error("CF-P1-005-R4-CONTRACTS-veo-1080p-needs-8s",
                     lambda: adapter.prepare(
                         packet("video-generation", "x"),
                         ctx(resolution="1080p",
                             duration_seconds=6)))
        expect_error("CF-P1-005-R4-CONTRACTS-veo-bad-model",
                     lambda: adapter.prepare(
                         packet("video-generation", "x",
                                model="veo-2.0-generate-001"),
                         ctx()))
        expect_error("CF-P1-005-R4-CONTRACTS-veo-dead-preview-id",
                     lambda: adapter.prepare(
                         packet("video-generation", "x",
                                model="veo-3.1-generate-preview"),
                         ctx()))
        expect_error("CF-P1-005-R4-CONTRACTS-veo-lite-refs",
                     lambda: adapter.prepare(
                         packet("video-generation", "x",
                                model="veo-3.1-lite-generate-001"),
                         ctx(reference_images=[
                             {"mime": "image/png",
                              "base64": "AAAA"}])))
        expect_error("CF-P1-005-R4-CONTRACTS-veo-fast-4k-unconfirmed",
                     lambda: adapter.prepare(
                         packet("video-generation", "x",
                                model="veo-3.1-fast-generate-001"),
                         ctx(resolution="4k",
                             duration_seconds=8)))
        expect_error("CF-P1-005-R4-CONTRACTS-veo-project-id-required",
                     lambda: adapter.prepare(
                         packet("video-generation", "x"),
                         {"execution_id": "exec-veo-001"}))
        expect_error("CF-P1-005-R4-CONTRACTS-veo-bad-project-id",
                     lambda: adapter.prepare(
                         packet("video-generation", "x"),
                         ctx(vertex_project_id="BAD PROJECT!")))

        # A submit response without the documented Vertex
        # operation name (the old Gemini API form is refused).
        def bad_name(method, url, *, headers=None, body=None):
            return (200, {"content-type": "application/json"},
                    b'{"name": "models/veo-3.1-generate-preview/'
                    b'operations/veo-job-001"}')
        badname = make_adapter("provider-veo-video", workspace,
                               bad_name)
        expect_error("CF-P1-005-R4-CONTRACTS-veo-bad-op-name",
                     lambda: badname.submit(
                         badname.prepare(packet("video-generation", "x"),
                                         ctx()), ctx()))

        # Poll: POST to fetchPredictOperation with the full
        # operation name in the body; done with inline video
        # bytes completes without any download.
        def done_transport(method, url, *, headers=None, body=None):
            return (200, {"content-type": "application/json"},
                    json.dumps(
                        {"done": True,
                         "response": {"videos": [
                             {"bytesBase64Encoded":
                              base64.b64encode(
                                  b"FAKEVIDEO").decode("ascii"),
                              "mimeType": "video/mp4"}]}}
                    ).encode("utf-8"))

        transport, calls2 = recording_transport(done_transport)
        done_adapter = make_adapter("provider-veo-video", workspace,
                                    transport)
        polled = done_adapter.poll(operation, {
            "execution_id": "exec-veo-002",
            "vertex_project_id": project})
        check("CF-P1-005-R4-CONTRACTS-veo-poll-method-body",
              len(calls2) >= 1 and calls2[0][0] == "POST"
              and calls2[0][1] == poll_url
              and json.loads(calls2[0][3].decode("utf-8"))
              == {"operationName": operation},
              str([(c[0], c[1]) for c in calls2]))
        check("CF-P1-005-R4-CONTRACTS-veo-poll-completed",
              polled.get("completed") is True
              and polled.get("output") is not None
              and saved_bytes(workspace, polled["output"])
              == b"FAKEVIDEO")

        def running_transport(method, url, *, headers=None, body=None):
            return (200, {"content-type": "application/json"},
                    b'{"done": false}')
        running = make_adapter("provider-veo-video", workspace,
                               running_transport)
        polled = running.poll(operation, ctx())
        check("CF-P1-005-R4-CONTRACTS-veo-poll-running",
              polled.get("completed") is False)

        def failed_transport(method, url, *, headers=None, body=None):
            return (200, {"content-type": "application/json"},
                    json.dumps(
                        {"done": True,
                         "error": {"status": "FAILED",
                                   "message": "generation failed"}}
                    ).encode("utf-8"))
        failing = make_adapter("provider-veo-video", workspace,
                               failed_transport)
        polled = failing.poll(operation, ctx())
        check("CF-P1-005-R4-CONTRACTS-veo-poll-failed",
              polled.get("completed") is True
              and polled["failure"]["code"] == "provider-error"
              and "generation failed" in polled["failure"]["message"])

        def cancelled_transport(method, url, *, headers=None,
                                body=None):
            return (200, {"content-type": "application/json"},
                    json.dumps(
                        {"done": True,
                         "error": {"status": "CANCELLED", "code": 499,
                                   "message": "operation cancelled"}}
                    ).encode("utf-8"))
        cancelled = make_adapter("provider-veo-video", workspace,
                                 cancelled_transport)
        polled = cancelled.poll(operation, ctx())
        check("CF-P1-005-R4-CONTRACTS-veo-poll-cancelled",
              polled.get("completed") is True
              and polled["failure"]["code"] == "cancelled-by-provider")

        # Done without any video is malformed.
        def no_video(method, url, *, headers=None, body=None):
            return (200, {"content-type": "application/json"},
                    json.dumps(
                        {"done": True, "response": {}}
                    ).encode("utf-8"))
        novideo = make_adapter("provider-veo-video", workspace,
                               no_video)
        expect_error("CF-P1-005-R4-CONTRACTS-veo-missing-output",
                     lambda: novideo.poll(operation, ctx()))

        # Done with a GCS URI only is refused: the GCS download
        # origin is UNCONFIRMED, so the output cannot be
        # retrieved.
        def gcs_transport(method, url, *, headers=None, body=None):
            return (200, {"content-type": "application/json"},
                    json.dumps(
                        {"done": True,
                         "response": {"videos": [
                             {"gcsUri": "gs://veo-bucket/veo-job-001.mp4",
                              "mimeType": "video/mp4"}]}}
                    ).encode("utf-8"))
        gcs = make_adapter("provider-veo-video", workspace,
                           gcs_transport)
        expect_code("CF-P1-005-R4-CONTRACTS-veo-gcs-output-refused",
                    "validation-failed",
                    lambda: gcs.poll(operation, ctx()))

        # No documented cancellation.
        expect_error("CF-P1-005-R4-CONTRACTS-veo-cancel-unsupported",
                     lambda: adapter.cancel(operation, ctx()))
    finally:
        restore_env("VERTEX_ACCESS_TOKEN", old)


# Kling video (asynchronous, legacy /v1)
# ---------------------------------------------------------------------

def kling_group(tmpdir):
    """CF-P1-005-R4-CONTRACTS: Kling legacy contract.

    Kling is documented from secondary sources quoting the
    official docs, so ``prepare()`` (preflight) refuses it until
    the official documentation is verified — these tests call
    ``translate()`` directly, which exercises the contract
    without the live-call gate.
    """
    workspace = os.path.join(tmpdir, "kling-workspace")
    os.makedirs(workspace)
    old = set_env("KLING_API_KEY", "test-kling-key")
    try:
        def submit_transport(method, url, *, headers=None, body=None):
            return (200, {"content-type": "application/json"},
                    json.dumps(
                        {"code": 0,
                         "data": {"task_id": "kling-job-001",
                                  "task_status": "submitted"}}
                    ).encode("utf-8"))

        transport, calls = recording_transport(submit_transport)
        adapter = make_adapter("provider-kling-video", workspace,
                               transport)
        request = adapter.translate(
            packet("video-generation", "a boat crosses the river"),
            {"execution_id": "exec-kling-001"})
        result = adapter.submit(request, {"execution_id": "exec-kling-001"})
        check("CF-P1-005-R4-CONTRACTS-kling-method-url",
              len(calls) == 1 and calls[0][0] == "POST"
              and calls[0][1] == "https://api-singapore.klingai.com/"
                                 "v1/videos/text2video",
              str([c[1] for c in calls]))
        check("CF-P1-005-R4-CONTRACTS-kling-auth",
              calls[0][2].get("Authorization")
              == "Bearer test-kling-key")
        check("CF-P1-005-R4-CONTRACTS-kling-exact-body",
              json_body(calls[0]) == {"model_name": "kling-v1",
                                      "prompt": "a boat crosses the "
                                                "river",
                                      "duration": "5"},
              str(json_body(calls[0])))
        check("CF-P1-005-R4-CONTRACTS-kling-accepted",
              result.get("completed") is False
              and result.get("provider_job_id") == "kling-job-001")

        # Image-to-video posts to the other endpoint with raw base64.
        transport, calls2 = recording_transport(submit_transport)
        adapter2 = make_adapter("provider-kling-video", workspace,
                                transport)
        request2 = adapter2.translate(
            packet("video-generation", "animate this boat"),
            {"reference_images": [
                {"mime": "image/png",
                 "base64": base64.b64encode(PNG_1X1).decode("ascii")}]})
        adapter2.submit(request2, {})
        check("CF-P1-005-R4-CONTRACTS-kling-i2v-endpoint",
              calls2[0][1] == "https://api-singapore.klingai.com/"
                              "v1/videos/image2video",
              calls2[0][1])
        body2 = json_body(calls2[0])
        check("CF-P1-005-R4-CONTRACTS-kling-i2v-image-raw-b64",
              body2.get("image")
              == base64.b64encode(PNG_1X1).decode("ascii")
              and not body2["image"].startswith("data:"),
              str(body2)[:120])

        # The new path-based models are NOT implemented.
        expect_error("CF-P1-005-R4-CONTRACTS-kling-new-model-refused",
                     lambda: adapter.translate(
                         packet("video-generation", "x",
                                model="kling-4.0"), {}))
        expect_error("CF-P1-005-R4-CONTRACTS-kling-prompt-too-long",
                     lambda: adapter.translate(
                         packet("video-generation", "x" * 2501), {}))
        # A non-zero submit code is a provider failure.
        def code_fail(method, url, *, headers=None, body=None):
            return (200, {"content-type": "application/json"},
                    json.dumps({"code": 1001,
                                "message": "bad request",
                                "data": {}}).encode("utf-8"))
        failing = make_adapter("provider-kling-video", workspace,
                               code_fail)
        expect_error("CF-P1-005-R4-CONTRACTS-kling-submit-code",
                     lambda: failing.submit(
                         failing.translate(packet("video-generation", "x"),
                                         {}), {}))

        # Poll states.
        def poll_transport(status):
            def responder(method, url, *, headers=None, body=None):
                return (200, {"content-type": "application/json"},
                        json.dumps(
                            {"code": 0,
                             "data": {"task_id": "kling-job-001",
                                      "task_status": status}}
                        ).encode("utf-8"))
            return responder
        for label, status in (("submitted", "submitted"),
                              ("processing", "processing")):
            transport, _ = recording_transport(poll_transport(status))
            running = make_adapter("provider-kling-video", workspace,
                                   transport)
            polled = running.poll("kling-job-001", {})
            check("CF-P1-005-R4-CONTRACTS-kling-poll-running-" + label,
                  polled.get("completed") is False)
        transport, calls3 = recording_transport(poll_transport("failed"))
        failing_poll = make_adapter("provider-kling-video", workspace,
                                    transport)
        polled = failing_poll.poll("kling-job-001", {})
        check("CF-P1-005-R4-CONTRACTS-kling-poll-failed",
              polled.get("completed") is True
              and polled["failure"]["code"] == "provider-error")
        check("CF-P1-005-R4-CONTRACTS-kling-poll-url",
              calls3[0][1] == "https://api-singapore.klingai.com/"
                              "v1/videos/text2video/kling-job-001",
              str([c[1] for c in calls3]))

        # A completed Kling job carries a result URL whose host is
        # UNCONFIRMED — the download fails closed until confirmed.
        def done_transport(method, url, *, headers=None, body=None):
            return (200, {"content-type": "application/json"},
                    json.dumps(
                        {"code": 0,
                         "data": {"task_id": "kling-job-001",
                                  "task_status": "succeed",
                                  "task_result": {
                                      "videos": [{"url":
                                                  "https://cdn.example"
                                                  ".com/v.mp4"}]}}}
                    ).encode("utf-8"))
        done_adapter = make_adapter("provider-kling-video", workspace,
                                    done_transport)
        expect_error("CF-P1-005-R4-CONTRACTS-kling-done-host-unconfirmed",
                     lambda: done_adapter.poll("kling-job-001", {}))

        # No documented cancellation.
        expect_error("CF-P1-005-R4-CONTRACTS-kling-cancel-unsupported",
                     lambda: adapter.cancel("kling-job-001", {}))
    finally:
        restore_env("KLING_API_KEY", old)


# ---------------------------------------------------------------------
# LTX video (asynchronous API v2)
# ---------------------------------------------------------------------

def ltx_group(tmpdir):
    """CF-P1-005-R4-CONTRACTS: LTX API v2 contract.

    LTX is documented from secondary sources quoting the
    official docs, so ``prepare()`` (preflight) refuses it until
    the official documentation is verified — these tests call
    ``translate()`` directly, which exercises the contract
    without the live-call gate.
    """
    workspace = os.path.join(tmpdir, "ltx-workspace")
    os.makedirs(workspace)
    old = set_env("LTX_API_KEY", "test-ltx-key")
    try:
        def submit_transport(method, url, *, headers=None, body=None):
            return (202, {"content-type": "application/json"},
                    json.dumps({"id": "ltx-job-001",
                                "created_at": "2026-11-27T00:00:00Z"}
                               ).encode("utf-8"))

        transport, calls = recording_transport(submit_transport)
        adapter = make_adapter("provider-ltx-video", workspace,
                               transport)
        request = adapter.translate(
            packet("video-generation", "a boat crosses the river"),
            {"execution_id": "exec-ltx-001", "resolution": "1280x720",
             "fps": 24, "duration": 6})
        result = adapter.submit(request, {"execution_id": "exec-ltx-001"})
        check("CF-P1-005-R4-CONTRACTS-ltx-method-url",
              len(calls) == 1 and calls[0][0] == "POST"
              and calls[0][1] == "https://api.ltx.io/v2/text-to-video",
              str([c[1] for c in calls]))
        check("CF-P1-005-R4-CONTRACTS-ltx-auth",
              calls[0][2].get("Authorization")
              == "Bearer test-ltx-key")
        check("CF-P1-005-R4-CONTRACTS-ltx-exact-body",
              json_body(calls[0]) == {"model": "ltx-2-5-fast",
                                      "prompt": "a boat crosses the "
                                                "river",
                                      "resolution": "1280x720",
                                      "fps": 24, "duration": 6},
              str(json_body(calls[0])))
        check("CF-P1-005-R4-CONTRACTS-ltx-accepted",
              result.get("completed") is False
              and result.get("provider_job_id") == "ltx-job-001")

        # Duration and resolution are required and validated.
        expect_error("CF-P1-005-R4-CONTRACTS-ltx-no-duration",
                     lambda: adapter.translate(
                         packet("video-generation", "x"),
                         {"resolution": "1280x720"}))
        expect_error("CF-P1-005-R4-CONTRACTS-ltx-no-resolution",
                     lambda: adapter.translate(
                         packet("video-generation", "x"),
                         {"duration": 6}))
        expect_error("CF-P1-005-R4-CONTRACTS-ltx-bad-duration",
                     lambda: adapter.translate(
                         packet("video-generation", "x"),
                         {"resolution": "1280x720", "duration": 7}))
        expect_error("CF-P1-005-R4-CONTRACTS-ltx-bad-model",
                     lambda: adapter.translate(
                         packet("video-generation", "x",
                                model="ltx-2-4-fast"), {}))

        # Image-to-video needs a first frame and sends a data URI.
        with open(os.path.join(workspace, "frame.png"),
                  "wb") as handle:
            handle.write(PNG_1X1)
        transport, calls2 = recording_transport(submit_transport)
        adapter2 = make_adapter("provider-ltx-video", workspace,
                                transport)
        request2 = adapter2.translate(
            packet("video-generation", "animate this"),
            {"endpoint": "image-to-video", "resolution": "1280x720",
             "fps": 24, "duration": 6,
             "first_frame": {"path": "frame.png"}})
        adapter2.submit(request2, {})
        check("CF-P1-005-R4-CONTRACTS-ltx-i2v-endpoint",
              calls2[0][1] == "https://api.ltx.io/v2/image-to-video",
              calls2[0][1])
        check("CF-P1-005-R4-CONTRACTS-ltx-i2v-data-uri",
              json_body(calls2[0]).get("image_uri", "").startswith(
                  "data:image/png;base64,"))
        expect_error("CF-P1-005-R4-CONTRACTS-ltx-i2v-no-frame",
                     lambda: adapter.translate(
                         packet("video-generation", "x"),
                         {"endpoint": "image-to-video",
                          "resolution": "1280x720", "duration": 6}))

        # Poll states.
        def poll_transport(status, extra=None):
            def responder(method, url, *, headers=None, body=None):
                payload = {"id": "ltx-job-001", "status": status}
                if extra:
                    payload.update(extra)
                return (200, {"content-type": "application/json"},
                        json.dumps(payload).encode("utf-8"))
            return responder
        for label, status in (("pending", "pending"),
                              ("processing", "processing")):
            transport, _ = recording_transport(poll_transport(status))
            running = make_adapter("provider-ltx-video", workspace,
                                   transport)
            polled = running.poll("ltx-job-001",
                                  {"endpoint": "text-to-video"})
            check("CF-P1-005-R4-CONTRACTS-ltx-poll-running-" + label,
                  polled.get("completed") is False)
        transport, calls3 = recording_transport(
            poll_transport("failed",
                           {"error": {"type": "content_filtered",
                                      "message": "blocked"}}))
        failing = make_adapter("provider-ltx-video", workspace,
                               transport)
        polled = failing.poll("ltx-job-001",
                              {"endpoint": "text-to-video"})
        check("CF-P1-005-R4-CONTRACTS-ltx-poll-failed",
              polled.get("completed") is True
              and polled["failure"]["code"] == "provider-error"
              and "blocked" in polled["failure"]["message"])
        check("CF-P1-005-R4-CONTRACTS-ltx-poll-url",
              calls3[0][1] == "https://api.ltx.io/v2/text-to-video/"
                              "ltx-job-001",
              str([c[1] for c in calls3]))
        # A completed LTX job carries a signed video URL whose host
        # is UNCONFIRMED — the download fails closed until confirmed.
        transport, _ = recording_transport(poll_transport(
            "completed",
            {"result": {"video_url": "https://cdn.example.com/v.mp4"}}))
        done_adapter = make_adapter("provider-ltx-video", workspace,
                                    transport)
        expect_error("CF-P1-005-R4-CONTRACTS-ltx-done-host-unconfirmed",
                     lambda: done_adapter.poll(
                         "ltx-job-001", {"endpoint": "text-to-video"}))
        # Unknown poll status is malformed.
        transport, _ = recording_transport(poll_transport("queued"))
        bad_status = make_adapter("provider-ltx-video", workspace,
                                  transport)
        expect_error("CF-P1-005-R4-CONTRACTS-ltx-poll-bad-status",
                     lambda: bad_status.poll(
                         "ltx-job-001", {"endpoint": "text-to-video"}))

        # No cancel endpoint was found in the official docs.
        expect_error("CF-P1-005-R4-CONTRACTS-ltx-cancel-unsupported",
                     lambda: adapter.cancel("ltx-job-001", {}))
    finally:
        restore_env("LTX_API_KEY", old)


# ---------------------------------------------------------------------
# ElevenLabs voice (synchronous text-to-speech)
# ---------------------------------------------------------------------

def elevenlabs_group(tmpdir):
    """CF-P1-005-R4-CONTRACTS: ElevenLabs TTS contract.

    ElevenLabs is documented from secondary sources quoting the
    official docs, so ``prepare()`` (preflight) refuses it until
    the official documentation is verified — these tests call
    ``translate()`` directly, which exercises the contract
    without the live-call gate.
    """
    workspace = os.path.join(tmpdir, "eleven-workspace")
    os.makedirs(workspace)
    old = set_env("ELEVENLABS_API_KEY", "test-eleven-key")
    try:
        def voice_transport(method, url, *, headers=None, body=None):
            return (200, {"content-type": "audio/mpeg"}, MP3_BYTES)

        transport, calls = recording_transport(voice_transport)
        adapter = make_adapter("provider-elevenlabs-voice", workspace,
                               transport)
        request = adapter.translate(
            packet("voice-generation", "Say hello to the river."),
            {"execution_id": "exec-el-001", "voice_id": "voice-001"})
        result = adapter.submit(request, {"execution_id": "exec-el-001"})
        check("CF-P1-005-R4-CONTRACTS-eleven-method-url",
              len(calls) == 1 and calls[0][0] == "POST"
              and calls[0][1] == "https://api.elevenlabs.io/v1/"
                                 "text-to-speech/voice-001"
                                 "?output_format=mp3_44100_128",
              str([c[1] for c in calls]))
        check("CF-P1-005-R4-CONTRACTS-eleven-auth",
              calls[0][2].get("xi-api-key") == "test-eleven-key")
        check("CF-P1-005-R4-CONTRACTS-eleven-exact-body",
              json_body(calls[0]) == {
                  "text": "Say hello to the river.",
                  "model_id": "eleven_v4"},
              str(json_body(calls[0])))
        check("CF-P1-005-R4-CONTRACTS-eleven-sync-bytes",
              result.get("completed") is True
              and saved_bytes(workspace, result["output"]) == MP3_BYTES
              and result["output"]["path"].endswith(".mp3"))

        # Voice settings are validated per model.
        transport, calls2 = recording_transport(voice_transport)
        adapter2 = make_adapter("provider-elevenlabs-voice", workspace,
                                transport)
        request2 = adapter2.translate(
            packet("voice-generation", "x"),
            {"voice_id": "voice-001",
             "voice_settings": {"stability": 0.5,
                                "similarity_boost": 0.8}})
        adapter2.submit(request2, {})
        check("CF-P1-005-R4-CONTRACTS-eleven-voice-settings",
              json_body(calls2[0]).get("voice_settings")
              == {"stability": 0.5, "similarity_boost": 0.8},
              str(json_body(calls2[0])))
        expect_error("CF-P1-005-R4-CONTRACTS-eleven-v4-no-style",
                     lambda: adapter.translate(
                         packet("voice-generation", "x"),
                         {"voice_id": "voice-001",
                          "voice_settings": {"style": 0.5}}))
        expect_error("CF-P1-005-R4-CONTRACTS-eleven-no-voice",
                     lambda: adapter.translate(
                         packet("voice-generation", "x"), {}))
        expect_error("CF-P1-005-R4-CONTRACTS-eleven-v4-char-limit",
                     lambda: adapter.translate(
                         packet("voice-generation", "x" * 100001),
                         {"voice_id": "voice-001"}))
        expect_error("CF-P1-005-R4-CONTRACTS-eleven-bad-model",
                     lambda: adapter.translate(
                         packet("voice-generation", "x",
                                model="eleven_v2"), {}))

        # Wrong content type / empty body are malformed output.
        def html_transport(method, url, *, headers=None, body=None):
            return (200, {"content-type": "text/html"},
                    b"<html>not audio</html>")
        html = make_adapter("provider-elevenlabs-voice", workspace,
                            html_transport)
        expect_error("CF-P1-005-R4-CONTRACTS-eleven-wrong-content-type",
                     lambda: html.submit(
                         html.translate(packet("voice-generation", "x"),
                                      {"voice_id": "voice-001"}), {}))

        def empty_transport(method, url, *, headers=None, body=None):
            return (200, {"content-type": "audio/mpeg"}, b"")
        empty = make_adapter("provider-elevenlabs-voice", workspace,
                             empty_transport)
        expect_error("CF-P1-005-R4-CONTRACTS-eleven-empty-body",
                     lambda: empty.submit(
                         empty.translate(packet("voice-generation", "x"),
                                       {"voice_id": "voice-001"}), {}))

        # A synchronous provider has no poll.
        expect_error("CF-P1-005-R4-CONTRACTS-eleven-no-poll",
                     lambda: adapter.poll("job-1", {}))
    finally:
        restore_env("ELEVENLABS_API_KEY", old)


# ---------------------------------------------------------------------
# Lyria music (synchronous, Interactions API)
# ---------------------------------------------------------------------

def lyria_group(tmpdir):
    """CF-P1-005-R4-CONTRACTS: Lyria music contract."""
    workspace = os.path.join(tmpdir, "lyria-workspace")
    os.makedirs(workspace)
    old = set_env("GEMINI_API_KEY", "test-gemini-key")
    try:
        def music_transport(method, url, *, headers=None, body=None):
            payload = {"steps": [{"content": [
                {"type": "text", "text": "verse one"},
                {"type": "audio",
                 "data": base64.b64encode(MP3_BYTES).decode("ascii"),
                 "mime_type": "audio/mpeg"}]}]}
            return (200, {"content-type": "application/json"},
                    json.dumps(payload).encode("utf-8"))

        transport, calls = recording_transport(music_transport)
        adapter = make_adapter("provider-lyria-music", workspace,
                               transport)
        request = adapter.prepare(
            packet("sound-generation", "a sea shanty in Bengali"),
            {"execution_id": "exec-ly-001"})
        result = adapter.submit(request, {"execution_id": "exec-ly-001"})
        check("CF-P1-005-R4-CONTRACTS-lyria-method-url",
              len(calls) == 1 and calls[0][0] == "POST"
              and calls[0][1] == "https://generativelanguage."
                                 "googleapis.com/v1beta/interactions",
              str([c[1] for c in calls]))
        check("CF-P1-005-R4-CONTRACTS-lyria-auth-headers",
              calls[0][2].get("x-goog-api-key") == "test-gemini-key"
              and calls[0][2].get("Api-Revision") == "2026-05-20")
        check("CF-P1-005-R4-CONTRACTS-lyria-exact-body",
              json_body(calls[0]) == {
                  "model": "lyria-3.5",
                  "input": "a sea shanty in Bengali"},
              str(json_body(calls[0])))
        check("CF-P1-005-R4-CONTRACTS-lyria-sync-bytes",
              result.get("completed") is True
              and saved_bytes(workspace, result["output"]) == MP3_BYTES
              and result["output"]["path"].endswith(".mp3"))

        # The 30-second clip model is accepted.
        transport, calls2 = recording_transport(music_transport)
        adapter2 = make_adapter("provider-lyria-music", workspace,
                                transport)
        request2 = adapter2.prepare(
            packet("sound-generation", "x",
                   model="lyria-3-clip-preview"),
            {"execution_id": "exec-ly-002"})
        adapter2.submit(request2, {"execution_id": "exec-ly-002"})
        check("CF-P1-005-R4-CONTRACTS-lyria-clip-model",
              json_body(calls2[0])["model"] == "lyria-3-clip-preview")

        # WAV output is refused explicitly (fields unconfirmed).
        expect_error("CF-P1-005-R4-CONTRACTS-lyria-wav-refused",
                     lambda: adapter.prepare(
                         packet("sound-generation", "x"),
                         {"output_format": "wav"}))
        # At most 10 inspiration images.
        refs = [{"mime": "image/png",
                 "base64": base64.b64encode(PNG_1X1).decode("ascii")}
                for _ in range(11)]
        expect_error("CF-P1-005-R4-CONTRACTS-lyria-too-many-refs",
                     lambda: adapter.prepare(
                         packet("sound-generation", "x"),
                         {"reference_images": refs}))
        # A response with no audio step carries no output.
        def no_audio(method, url, *, headers=None, body=None):
            return (200, {"content-type": "application/json"},
                    b'{"steps": []}')
        nodata = make_adapter("provider-lyria-music", workspace,
                              no_audio)
        expect_error("CF-P1-005-R4-CONTRACTS-lyria-missing-output",
                     lambda: nodata.submit(
                         nodata.prepare(packet("sound-generation", "x"),
                                        {}), {}))
    finally:
        restore_env("GEMINI_API_KEY", old)


# ---------------------------------------------------------------------
# Cross-cutting: generic-payload refusal + registry consistency
# ---------------------------------------------------------------------

def crosscutting_group(tmpdir):
    """CF-P1-005-R4-CONTRACTS: no generic payload, registry match."""
    workspace = os.path.join(tmpdir, "cross-workspace")
    os.makedirs(workspace)
    old = set_env("OPENAI_API_KEY", "test-openai-key")
    try:
        def image_transport(method, url, *, headers=None, body=None):
            payload = {"data": [{"b64_json": base64.b64encode(
                PNG_1X1).decode("ascii")}]}
            return (200, {"content-type": "application/json"},
                    json.dumps(payload).encode("utf-8"))

        adapter = make_adapter("provider-openai-image", workspace,
                               image_transport)
        # A hand-built generic {model, prompt} request is refused:
        # only a contract-built request may be submitted.
        expect_error("CF-P1-005-R4-CONTRACTS-generic-payload-refused",
                     lambda: adapter.submit(
                         {"provider_request": {
                             "model": "gpt-image-1-mini",
                             "prompt": "a red boat"}},
                         {"execution_id": "exec-x-001"}))
        # A contract-built request whose body was tampered with
        # after translation is refused too.
        request = adapter.prepare(
            packet("image-generation", "a red boat"),
            {"execution_id": "exec-x-002"})
        request["request"]["body"] = dict(request["request"]["body"])
        request["request"]["body"]["prompt"] = "a different boat"
        expect_error("CF-P1-005-R4-CONTRACTS-tampered-body-refused",
                     lambda: adapter.submit(
                         request, {"execution_id": "exec-x-002"}))
        # And a translated request for one provider cannot be
        # submitted to another provider's adapter.
        other = make_adapter("provider-gemini-image", workspace,
                             image_transport)
        request3 = adapter.prepare(
            packet("image-generation", "a red boat"),
            {"execution_id": "exec-x-003"})
        expect_error("CF-P1-005-R4-CONTRACTS-cross-provider-refused",
                     lambda: other.submit(
                         request3, {"execution_id": "exec-x-003"}))
    finally:
        restore_env("OPENAI_API_KEY", old)

    # Registry consistency: one contract per live spec, same
    # async shape, and Sora stays without a contract.
    check("CF-P1-005-R4-CONTRACTS-eight-contracts",
          len(CONTRACTS) == 8, str(sorted(CONTRACTS)))
    for provider_id, contract in sorted(CONTRACTS.items()):
        spec = PROVIDER_SPECS.get(provider_id)
        check("CF-P1-005-R4-CONTRACTS-spec-exists:" + provider_id,
              spec is not None)
        if spec is None:
            continue
        check("CF-P1-005-R4-CONTRACTS-async-match:" + provider_id,
              contract.is_async is spec.get("async"),
              f"contract={contract.is_async} "
              f"spec={spec.get('async')}")
        check("CF-P1-005-R4-CONTRACTS-id-match:" + provider_id,
              contract.provider_id == provider_id)
        check("CF-P1-005-R4-CONTRACTS-cancel-flag:" + provider_id,
              contract.supports_cancel
              == (spec.get("cancel") is not None),
              f"contract={contract.supports_cancel} "
              f"spec-cancel={spec.get('cancel')}")
    check("CF-P1-005-R4-CONTRACTS-no-sora",
          "provider-sora-video" not in CONTRACTS)
    expect_error("CF-P1-005-R4-CONTRACTS-unknown-provider",
                 lambda: get_contract("provider-no-such"))


def main():
    tmpdir = tempfile.mkdtemp(prefix="cf-p1-005-r4-contracts-")
    openai_group(tmpdir)
    gemini_group(tmpdir)
    fal_group(tmpdir)
    veo_group(tmpdir)
    kling_group(tmpdir)
    ltx_group(tmpdir)
    elevenlabs_group(tmpdir)
    lyria_group(tmpdir)
    crosscutting_group(tmpdir)
    print(f"--- CF-P1-005-R4-CONTRACTS: {_checks[0]} checks, "
          f"{len(failures)} failures ---")
    if failures:
        print("FAILURES: " + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
