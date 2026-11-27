#!/usr/bin/env python3
"""Provider URL security tests (CF-WO-P1-005-R4, workstream A).

Covers the provider URL security policy
(``runtime/provider_url_policy.py``) and its use by
``HttpProviderAdapter``: explicit API/output origin allowlists,
scheme/host/port/userinfo validation, IP-literal and alternate
numeric address rejection, encoded path/hostname tricks,
trailing-dot hosts, DNS resolution that must return only public
addresses, validated redirect hops with no credential forwarding
across origins, template-constructed poll/cancel URLs, malicious
status/cancel/output URLs refused before any request, response
and download size limits, and the pinned TLS transport (local
test CA + TLS server: the connection goes to the pinned address
while SNI, certificate validation and the Host header name the
hostname).

No live provider call is made anywhere in this suite: every
external provider is exercised through an injected mock
transport, credentials are fake test values in the process
environment only, and the pinned-transport test talks to a TLS
server on loopback created for the test.

Conventions follow tests/test_media_adapters.py: check(name,
cond, detail="") prints PASS/FAIL lines, failures are collected,
and the process exits 0 only when every check passes. No test
here weakens any P0 or P1 check.
"""

import base64
import http.server
import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading

ROOT = os.path.join(os.path.dirname(__file__), "..")
ROOT_ABS = os.path.abspath(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
from runtime.media_adapters import (  # noqa: E402
    PROVIDER_SPECS, HttpProviderAdapter)
from runtime.media_execution import MediaExecutionError  # noqa: E402
from runtime.provider_url_policy import (  # noqa: E402
    ProviderURLPolicy, _pinned_https_request,
    validate_endpoint_segment, validate_model_id,
    validate_operation_name, validate_provider_job_id,
    validate_resolved_addresses)

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


def make_policy(api=("api.openai.com", "queue.fal.run",
                     "generativelanguage.googleapis.com",
                     "api-singapore.klingai.com", "api.ltx.io",
                     "api.elevenlabs.io"),
                output=("fal.media",), **extra):
    return ProviderURLPolicy(api_origins=api, output_origins=output,
                             **extra)


def resolver_for(mapping):
    """Injectable resolver: hostname -> [addresses]."""
    def resolve(host):
        if host not in mapping:
            raise socket.gaierror(f"no such host {host}")
        return list(mapping[host])
    return resolve


# A minimal 1x1 transparent PNG (also used as download bytes).
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")


def structure_group():
    """CF-P1-005-R4-SEC: URL structure + origin allowlist."""
    policy = make_policy()
    # Legitimate URLs pass, for both purposes.
    check("CF-P1-005-R4-SEC-api-url-ok",
          policy.validate_url(
              "https://api.openai.com/v1/images/generations",
              "api")["host"] == "api.openai.com")
    check("CF-P1-005-R4-SEC-api-url-explicit-443",
          policy.validate_url("https://api.openai.com:443/v1",
                              "api")["port"] == 443)
    check("CF-P1-005-R4-SEC-api-url-case-insensitive",
          policy.validate_url(
              "HTTPS://API.OPENAI.COM/v1", "api")["host"]
          == "api.openai.com")
    check("CF-P1-005-R4-SEC-output-url-ok",
          policy.validate_url(
              "https://fal.media/files/abc123?sig=deadbeef",
              "output")["host"] == "fal.media")
    # Purpose separation: an output origin is not an API origin.
    expect_error("CF-P1-005-R4-SEC-output-origin-not-api",
                 lambda: policy.validate_url(
                     "https://fal.media/files/abc", "api"))
    expect_error("CF-P1-005-R4-SEC-api-origin-not-output",
                 lambda: policy.validate_url(
                     "https://api.openai.com/v1", "output"))
    # Every hostile shape is refused.
    hostile = [
        "http://api.openai.com/v1",  # downgrade
        "https://api.openai.com:80/v1",  # unapproved port
        "https://api.openai.com:8443/v1",
        "https://api.openai.com:99999/v1",  # invalid port
        "https://api.openai.com:abc/v1",  # invalid port
        "file:///etc/passwd",
        "ftp://api.openai.com/file",
        "https://127.0.0.1/",
        "https://127.0.0.1:443/",
        "https://localhost/",
        "https://localhost:443/",
        "https://[::1]/",
        "https://[::ffff:127.0.0.1]/",  # IPv4-mapped IPv6 literal
        "https://10.0.0.5/",
        "https://172.16.0.9/",
        "https://192.168.1.1/",
        "https://169.254.169.254/latest/meta-data/",
        "https://[fe80::1]/",
        "https://[fc00::1]/",
        "https://0x7f000001/",  # hex address
        "https://0x7f.0.0.1/",  # hex label
        "https://2130706433/",  # decimal address
        "https://0177.0.0.1/",  # octal address
        "https://127.1/",  # short-form address
        "https://user:pass@api.openai.com/",  # userinfo
        "https://api.openai.com@127.0.0.1/",  # userinfo smuggle
        "https://api.openai.com:443@evil.example.com/",  # userinfo
        "https://evil.example.com/",  # unapproved origin
        "https://api.openai.com.evil.example.com/",  # suffix
        "https://evilapi.openai.com/",  # near-miss origin
        "https://api.openai.com./v1",  # trailing dot
        "https://api.openai.com%2e/v1",  # encoded dot in host
        "https://api.openai.com%00/v1",  # NUL in host
        "https://api_openai.com/v1",  # underscore in host
        "https://api.openai.com\\@127.0.0.1/",  # backslash
        "https://api.openai.com/%2e%2e/admin",  # encoded traversal
        "https://api.openai.com/%2E%2E/admin",  # encoded traversal
        "https://api.openai.com/%00",  # encoded NUL in path
        "https://evil.com#@api.openai.com/",  # fragment smuggle
        "https://",  # empty host
        "https:///path",  # empty host
        " https://api.openai.com/",  # leading whitespace
        "https://api.openai.com/\n",  # control character
        "",
    ]
    for url in hostile:
        expect_error("CF-P1-005-R4-SEC-hostile-url: " + (url or "<empty>"),
                     lambda u=url: policy.validate_url(u, "api"))
    for bad in (None, 42, b"https://api.openai.com/"):
        expect_error("CF-P1-005-R4-SEC-non-string-url",
                     lambda b=bad: policy.validate_url(b, "api"))
    expect_error("CF-P1-005-R4-SEC-unknown-purpose",
                 lambda: policy.validate_url(
                     "https://api.openai.com/", "other"))
    # A refused URL's error never carries its query string.
    try:
        policy.validate_url(
            "https://fal.media/files/x?sig=TOPSECRET123", "api")
        check("CF-P1-005-R4-SEC-query-never-in-error", False,
              "refused URL was accepted")
    except MediaExecutionError as exc:
        check("CF-P1-005-R4-SEC-query-never-in-error",
              "TOPSECRET123" not in "; ".join(exc.errors))


def resolution_group():
    """CF-P1-005-R4-SEC: DNS resolution must return public only."""
    # A public-only answer validates and pins the first address.
    policy = make_policy(resolver=resolver_for(
        {"api.openai.com": ["93.184.216.34", "93.184.216.35"]}))
    parsed, pinned = policy.validate_destination(
        "https://api.openai.com/v1", "api")
    check("CF-P1-005-R4-SEC-resolve-public-ok",
          pinned == "93.184.216.34" and parsed["host"] == "api.openai.com")
    # A resolver returning BOTH a public and a private address is
    # refused: one prohibited address poisons the destination.
    for label, addresses in [
            ("mixed-public-private", ["93.184.216.34", "10.0.0.1"]),
            ("loopback", ["127.0.0.1"]),
            ("localhost-v6", ["::1"]),
            ("metadata", ["169.254.169.254"]),
            ("private-10", ["10.1.2.3"]),
            ("private-172", ["172.16.5.4"]),
            ("private-192", ["192.168.0.7"]),
            ("link-local-v6", ["fe80::1"]),
            ("unique-local-v6", ["fc00::1"]),
            ("multicast", ["224.0.0.1"]),
            ("unspecified", ["0.0.0.0"]),
            ("mapped-loopback", ["::ffff:127.0.0.1"]),
            ("mapped-private", ["::ffff:10.0.0.1"]),
            ("test-net", ["192.0.2.1"]),
            ("unparseable", ["not-an-ip"]),
    ]:
        bad_policy = make_policy(resolver=resolver_for(
            {"api.openai.com": addresses}))
        expect_error("CF-P1-005-R4-SEC-resolve-refused: " + label,
                     lambda p=bad_policy: p.validate_destination(
                         "https://api.openai.com/v1", "api"))
    # Resolution failure fails closed: unknown host, empty answer,
    # resolver raising.
    expect_error("CF-P1-005-R4-SEC-resolve-unknown-host",
                 lambda: make_policy(resolver=resolver_for({}))
                 .validate_destination(
                     "https://api.openai.com/v1", "api"))
    expect_error("CF-P1-005-R4-SEC-resolve-empty",
                 lambda: make_policy(resolver=resolver_for(
                     {"api.openai.com": []})).validate_destination(
                     "https://api.openai.com/v1", "api"))
    expect_error("CF-P1-005-R4-SEC-resolve-empty-list",
                 lambda: validate_resolved_addresses([]))
    expect_error("CF-P1-005-R4-SEC-resolve-none",
                 lambda: validate_resolved_addresses(None))
    # URL path tokens: job ids, operation names, endpoints, models.
    check("CF-P1-005-R4-SEC-job-id-ok",
          validate_provider_job_id("veo-job-001") == "veo-job-001")
    check("CF-P1-005-R4-SEC-operation-ok",
          validate_operation_name("operations/veo-job-001")
          == "operations/veo-job-001")
    check("CF-P1-005-R4-SEC-endpoint-ok",
          validate_endpoint_segment("text-to-video") == "text-to-video"
          and validate_endpoint_segment("fal-ai/flux/dev")
          == "fal-ai/flux/dev")
    check("CF-P1-005-R4-SEC-model-ok",
          validate_model_id("fal-ai/nano-banana-2")
          == "fal-ai/nano-banana-2")
    for label, fn in [
            ("job-id-traversal",
             lambda: validate_provider_job_id("../evil")),
            ("job-id-leading-slash",
             lambda: validate_provider_job_id("/evil")),
            ("job-id-space",
             lambda: validate_provider_job_id("a b")),
            ("job-id-empty",
             lambda: validate_provider_job_id("")),
            ("job-id-too-long",
             lambda: validate_provider_job_id("x" * 129)),
            ("operation-traversal",
             lambda: validate_operation_name("operations/../../x")),
            ("operation-leading-slash",
             lambda: validate_operation_name("/operations/x")),
            ("endpoint-traversal",
             lambda: validate_endpoint_segment("../../x")),
            ("endpoint-query",
             lambda: validate_endpoint_segment("text-to-video?x=1")),
            ("model-traversal",
             lambda: validate_model_id("a/../../b")),
            ("model-empty",
             lambda: validate_model_id("")),
    ]:
        expect_error("CF-P1-005-R4-SEC-token-refused: " + label, fn)


def recording_transport(responder):
    """A mock transport that records every call it receives.

    ``responder(method, url, headers, body)`` returns
    ``(status, headers, body)``. Returns ``(transport, calls)``.
    """
    calls = []

    def transport(method, url, *, headers=None, body=None):
        calls.append((method, url, dict(headers or {}),
                      body))
        return responder(method, url, dict(headers or {}), body)

    return transport, calls


def redirect_group(tmpdir):
    """CF-P1-005-R4-SEC: every redirect hop is validated."""
    workspace = os.path.join(tmpdir, "sec-redirect")
    os.makedirs(workspace)
    old = set_env("FAL_KEY", "test-fal-key")
    try:
        fal_spec = dict(PROVIDER_SPECS["provider-fal-image"])
        fal_spec["provider_id"] = "provider-fal-image"
        packet = {"task_id": "task-sec-001",
                  "task_type": "image-generation",
                  "canonical_instruction": "a red boat"}

        # Redirect to localhost: refused, and the transport is
        # called exactly once — the forbidden hop is never made.
        def to_localhost(method, url, headers, body):
            return (302, {"location": "http://127.0.0.1/steal"},
                    b"")
        transport, calls = recording_transport(to_localhost)
        adapter = HttpProviderAdapter(
            fal_spec, workspace_root=workspace, transport=transport)
        expect_error("CF-P1-005-R4-SEC-redirect-localhost",
                     lambda: adapter.submit(
                         adapter.prepare(packet, {
                             "endpoint": "fal-ai/flux/dev"}),
                         {"endpoint": "fal-ai/flux/dev"}))
        check("CF-P1-005-R4-SEC-redirect-localhost-one-call",
              len(calls) == 1, str(len(calls)))

        # Redirect from an approved host to an unapproved host:
        # refused before the second hop.
        def to_unapproved(method, url, headers, body):
            return (302, {"location": "https://evil.example.com/x"},
                    b"")
        transport, calls = recording_transport(to_unapproved)
        adapter = HttpProviderAdapter(
            fal_spec, workspace_root=workspace, transport=transport)
        expect_error("CF-P1-005-R4-SEC-redirect-unapproved",
                     lambda: adapter.submit(
                         adapter.prepare(packet, {
                             "endpoint": "fal-ai/flux/dev"}),
                         {"endpoint": "fal-ai/flux/dev"}))
        check("CF-P1-005-R4-SEC-redirect-unapproved-one-call",
              len(calls) == 1, str(len(calls)))

        # Redirect to a loopback HTTPS URL: refused the same way.
        def to_loopback_https(method, url, headers, body):
            return (302, {"location": "https://127.0.0.1/x"}, b"")
        transport, calls = recording_transport(to_loopback_https)
        adapter = HttpProviderAdapter(
            fal_spec, workspace_root=workspace, transport=transport)
        expect_error("CF-P1-005-R4-SEC-redirect-loopback-https",
                     lambda: adapter.submit(
                         adapter.prepare(packet, {
                             "endpoint": "fal-ai/flux/dev"}),
                         {"endpoint": "fal-ai/flux/dev"}))
        check("CF-P1-005-R4-SEC-redirect-loopback-one-call",
              len(calls) == 1, str(len(calls)))

        # Same-origin redirect keeps working, auth kept.
        def same_origin(method, url, headers, body):
            if "/other" not in url:
                return (302, {"location": "/other"}, b"")
            return (200, {},
                    json.dumps(
                        {"request_id": "fal-job-001",
                         "status_url": "https://queue.fal.run/"
                                       "fal-ai/flux/dev/requests/"
                                       "fal-job-001/status",
                         "response_url": "https://queue.fal.run/"
                                         "fal-ai/flux/dev/requests/"
                                         "fal-job-001",
                         "cancel_url": "https://queue.fal.run/"
                                       "fal-ai/flux/dev/requests/"
                                       "fal-job-001/cancel"})
                    .encode("utf-8"))
        transport, calls = recording_transport(same_origin)
        adapter = HttpProviderAdapter(
            fal_spec, workspace_root=workspace, transport=transport)
        result = adapter.submit(
            adapter.prepare(packet, {"endpoint": "fal-ai/flux/dev"}),
            {"endpoint": "fal-ai/flux/dev"})
        check("CF-P1-005-R4-SEC-redirect-same-origin-ok",
              result.get("provider_job_id") == "fal-job-001")
        check("CF-P1-005-R4-SEC-redirect-same-origin-auth",
              len(calls) == 2
              and calls[0][2].get("Authorization") == "Key test-fal-key"
              and calls[1][2].get("Authorization") == "Key test-fal-key",
              str([c[2] for c in calls]))

        # Cross-origin redirect between two allow-listed API
        # origins: followed, but the credential is stripped on the
        # second hop. (A synthetic two-origin policy: no live
        # provider allow-lists two API origins today, so this pins
        # the stripping rule itself.)
        two_origin = ProviderURLPolicy(
            api_origins=("api-a.example.test", "api-b.example.test"),
            output_origins=())
        spec = {"provider_id": "provider-test-two-origin",
                "adapter_id": "adapter-test-two-origin",
                "api_version": "test",
                "models": ["test-model"],
                "submit": {"method": "POST",
                           "url": "https://api-a.example.test/submit"},
                "auth": {"env_var": "FAL_KEY", "header": "Authorization",
                         "scheme": "Key"},
                "async": False, "cancel": None,
                "retrieval": "response-body",
                "api_origins": ["api-a.example.test",
                                "api-b.example.test"],
                "output_origins": []}
        PROVIDER_SPECS["provider-test-two-origin"] = spec
        try:
            def cross_origin(method, url, headers, body):
                if "api-a.example.test" in url:
                    return (302, {"location":
                                  "https://api-b.example.test/other"},
                            b"")
                return (200, {}, b"cross-origin-ok")
            transport, calls = recording_transport(cross_origin)
            adapter = HttpProviderAdapter(
                spec, workspace_root=workspace, transport=transport,
                url_policy=two_origin)
            out = adapter._request(
                "POST", "https://api-a.example.test/submit",
                headers={"Authorization": "Key test-fal-key"},
                body=b"{}", purpose="api")
            check("CF-P1-005-R4-SEC-redirect-cross-origin-ok",
                  out[0] == 200 and out[2] == b"cross-origin-ok")
            check("CF-P1-005-R4-SEC-redirect-auth-stripped",
                  len(calls) == 2
                  and calls[0][2].get("Authorization")
                  == "Key test-fal-key"
                  and "Authorization" not in calls[1][2],
                  str([c[2] for c in calls]))
        finally:
            del PROVIDER_SPECS["provider-test-two-origin"]

        # A 303 turns the follow-up into a GET with no body.
        def see_other(method, url, headers, body):
            if method == "POST":
                return (303, {"location": "/result"}, b"")
            return (200, {}, b"see-other-ok")
        transport, calls = recording_transport(see_other)
        adapter = HttpProviderAdapter(
            fal_spec, workspace_root=workspace, transport=transport)
        out = adapter._request(
            "POST", "https://queue.fal.run/submit",
            headers={"Authorization": "Key test-fal-key"},
            body=b"{}", purpose="api")
        check("CF-P1-005-R4-SEC-redirect-303-get",
              out[0] == 200 and out[2] == b"see-other-ok"
              and len(calls) == 2 and calls[1][0] == "GET"
              and calls[1][3] is None,
              str([(c[0], c[3]) for c in calls]))

        # Redirect loop limit: a policy with max_redirects=2 is
        # refused after exactly three transport calls.
        limited = ProviderURLPolicy(
            api_origins=("queue.fal.run",), output_origins=(),
            max_redirects=2)
        def loop(method, url, headers, body):
            return (302, {"location": "/again"}, b"")
        transport, calls = recording_transport(loop)
        adapter = HttpProviderAdapter(
            fal_spec, workspace_root=workspace, transport=transport,
            url_policy=limited)
        expect_error("CF-P1-005-R4-SEC-redirect-limit",
                     lambda: adapter._request(
                         "GET", "https://queue.fal.run/x",
                         headers={}, purpose="api"))
        check("CF-P1-005-R4-SEC-redirect-limit-calls",
              len(calls) == 3, str(len(calls)))

        # Response size limit: a body over the cap is refused.
        def huge(method, url, headers, body):
            return (200, {}, b"x" * 200)
        transport, calls = recording_transport(huge)
        adapter = HttpProviderAdapter(
            fal_spec, workspace_root=workspace, transport=transport,
            max_response_bytes=100)
        expect_error("CF-P1-005-R4-SEC-response-size-limit",
                     lambda: adapter._request(
                         "GET", "https://queue.fal.run/x",
                         headers={}, purpose="api"))
    finally:
        restore_env("FAL_KEY", old)


def async_url_group(tmpdir):
    """CF-P1-005-R4-SEC: poll/cancel URLs are built or validated."""
    workspace = os.path.join(tmpdir, "sec-async")
    os.makedirs(workspace)

    # fal.ai has no poll/cancel template: a malicious status_url
    # or cancel_url is refused BEFORE the transport is called.
    old = set_env("FAL_KEY", "test-fal-key")
    try:
        fal_spec = dict(PROVIDER_SPECS["provider-fal-image"])
        fal_spec["provider_id"] = "provider-fal-image"
        for label, url in [
                ("localhost", "http://127.0.0.1/status"),
                ("loopback-https", "https://127.0.0.1/status"),
                ("metadata", "http://169.254.169.254/status"),
                ("unapproved", "https://evil.example.com/status"),
                ("userinfo", "https://queue.fal.run@evil.example.com/"),
                ("http-downgrade", "http://queue.fal.run/status")]:
            transport, calls = recording_transport(
                lambda m, u, h, b: (200, {}, b'{"status": "COMPLETED"}'))
            adapter = HttpProviderAdapter(
                fal_spec, workspace_root=workspace, transport=transport)
            expect_error("CF-P1-005-R4-SEC-malicious-status-url: " + label,
                         lambda u=url: adapter.poll(
                             "fal-job-001", {"status_url": u}))
            check("CF-P1-005-R4-SEC-malicious-status-no-call: " + label,
                  len(calls) == 0, str(len(calls)))
            transport, calls = recording_transport(
                lambda m, u, h, b: (200, {}, b""))
            adapter = HttpProviderAdapter(
                fal_spec, workspace_root=workspace, transport=transport)
            expect_error("CF-P1-005-R4-SEC-malicious-cancel-url: " + label,
                         lambda u=url: adapter.cancel(
                             "fal-job-001", {"cancel_url": u}))
            check("CF-P1-005-R4-SEC-malicious-cancel-no-call: " + label,
                  len(calls) == 0, str(len(calls)))

        # A legitimate fal status/cancel URL works, auth attached.
        def fal_ok(method, url, headers, body):
            if method == "PUT":
                return (200, {}, b"{}")
            return (200, {}, json.dumps(
                {"status": "IN_PROGRESS"}).encode("utf-8"))
        transport, calls = recording_transport(fal_ok)
        adapter = HttpProviderAdapter(
            fal_spec, workspace_root=workspace, transport=transport)
        polled = adapter.poll("fal-job-001", {
            "status_url": "https://queue.fal.run/fal-ai/flux/dev/"
                          "requests/fal-job-001/status"})
        check("CF-P1-005-R4-SEC-fal-status-url-ok",
              polled.get("completed") is False
              and calls[0][1] == "https://queue.fal.run/fal-ai/flux/dev/"
              "requests/fal-job-001/status"
              and calls[0][2].get("Authorization") == "Key test-fal-key")
        cancelled = adapter.cancel("fal-job-001", {
            "cancel_url": "https://queue.fal.run/fal-ai/flux/dev/"
                          "requests/fal-job-001/cancel"})
        check("CF-P1-005-R4-SEC-fal-cancel-url-ok",
              cancelled is True and calls[1][0] == "PUT")
    finally:
        restore_env("FAL_KEY", old)

    # Template-constructed poll URLs: Veo, Kling, LTX.
    old = set_env("VERTEX_ACCESS_TOKEN", "test-vertex-token")
    try:
        veo_spec = dict(PROVIDER_SPECS["provider-veo-video"])
        veo_spec["provider_id"] = "provider-veo-video"
        veo_operation = ("projects/test-project-1/locations/"
                         "us-central1/publishers/google/models/"
                         "veo-3.1-generate-001/operations/veo-job-001")
        transport, calls = recording_transport(
            lambda m, u, h, b: (200, {}, b'{"done": false}'))
        adapter = HttpProviderAdapter(
            veo_spec, workspace_root=workspace, transport=transport)
        adapter.poll(veo_operation, {})
        check("CF-P1-005-R4-SEC-veo-poll-template",
              calls[0][0] == "POST"
              and calls[0][1] == "https://us-central1-"
              "aiplatform.googleapis.com/v1/projects/test-project-1/"
              "locations/us-central1/publishers/google/models/"
              "veo-3.1-generate-001:fetchPredictOperation"
              and json.loads(calls[0][3].decode("utf-8"))
              == {"operationName": veo_operation},
              str(calls[0][1]))
        # A hostile job id never reaches the transport.
        transport, calls = recording_transport(
            lambda m, u, h, b: (200, {}, b'{"done": false}'))
        adapter = HttpProviderAdapter(
            veo_spec, workspace_root=workspace, transport=transport)
        expect_error("CF-P1-005-R4-SEC-veo-poll-bad-job-id",
                     lambda: adapter.poll("../evil", {}))
        check("CF-P1-005-R4-SEC-veo-poll-bad-job-no-call",
              len(calls) == 0, str(len(calls)))
    finally:
        restore_env("VERTEX_ACCESS_TOKEN", old)

    old = set_env("KLING_API_KEY", "test-kling-key")
    try:
        kling_spec = dict(PROVIDER_SPECS["provider-kling-video"])
        kling_spec["provider_id"] = "provider-kling-video"
        transport, calls = recording_transport(
            lambda m, u, h, b: (200, {}, json.dumps(
                {"code": 0,
                 "data": {"task_id": "kling-job-001",
                          "task_status": "processing"}}).encode(
                              "utf-8")))
        adapter = HttpProviderAdapter(
            kling_spec, workspace_root=workspace, transport=transport)
        adapter.poll("kling-job-001", {})
        check("CF-P1-005-R4-SEC-kling-poll-template",
              calls[0][1] == "https://api-singapore.klingai.com/"
              "v1/videos/text2video/kling-job-001",
              str(calls[0][1]))
    finally:
        restore_env("KLING_API_KEY", old)

    old = set_env("LTX_API_KEY", "test-ltx-key")
    try:
        ltx_spec = dict(PROVIDER_SPECS["provider-ltx-video"])
        ltx_spec["provider_id"] = "provider-ltx-video"
        transport, calls = recording_transport(
            lambda m, u, h, b: (200, {}, json.dumps(
                {"id": "ltx-job-001",
                 "status": "processing"}).encode("utf-8")))
        adapter = HttpProviderAdapter(
            ltx_spec, workspace_root=workspace, transport=transport)
        adapter.poll("ltx-job-001", {"endpoint": "text-to-video"})
        check("CF-P1-005-R4-SEC-ltx-poll-template",
              calls[0][1] == "https://api.ltx.io/v2/text-to-video/"
              "ltx-job-001",
              str(calls[0][1]))
        transport, calls = recording_transport(
            lambda m, u, h, b: (200, {}, json.dumps(
                {"id": "ltx-job-001",
                 "status": "processing"}).encode("utf-8")))
        adapter = HttpProviderAdapter(
            ltx_spec, workspace_root=workspace, transport=transport)
        expect_error("CF-P1-005-R4-SEC-ltx-poll-bad-endpoint",
                     lambda: adapter.poll(
                         "ltx-job-001", {"endpoint": "../../x"}))
        check("CF-P1-005-R4-SEC-ltx-poll-bad-endpoint-no-call",
              len(calls) == 0, str(len(calls)))
    finally:
        restore_env("LTX_API_KEY", old)


def retrieve_group(tmpdir):
    """CF-P1-005-R4-SEC: output downloads go through the policy."""
    workspace = os.path.join(tmpdir, "sec-retrieve")
    os.makedirs(workspace)
    old = set_env("FAL_KEY", "test-fal-key")
    try:
        fal_spec = dict(PROVIDER_SPECS["provider-fal-image"])
        fal_spec["provider_id"] = "provider-fal-image"

        # A malicious output URL is refused before any request and
        # creates no file.
        for label, url in [
                ("localhost", "http://127.0.0.1/x.png"),
                ("loopback-https", "https://127.0.0.1/x.png"),
                ("metadata", "http://169.254.169.254/x.png"),
                ("unapproved", "https://evil.example.com/x.png"),
                ("api-origin-as-output",
                 "https://queue.fal.run/x.png"),
                ("userinfo", "https://fal.media@evil.example.com/x"),
        ]:
            transport, calls = recording_transport(
                lambda m, u, h, b: (200, {}, PNG_1X1))
            adapter = HttpProviderAdapter(
                fal_spec, workspace_root=workspace, transport=transport)
            expect_error("CF-P1-005-R4-SEC-malicious-output-url: " + label,
                         lambda u=url: adapter.retrieve(
                             "fal-job-001", u, {"execution_id": "exec-sec"}))
            check("CF-P1-005-R4-SEC-malicious-output-no-call: " + label,
                  len(calls) == 0, str(len(calls)))
            check("CF-P1-005-R4-SEC-malicious-output-no-file: " + label,
                  not os.path.exists(
                      os.path.join(workspace, "outputs", "exec-sec")))

        # A legitimate signed CDN URL downloads, with no
        # Authorization header and no query in any header.
        def cdn_ok(method, url, headers, body):
            return (200, {}, PNG_1X1)
        transport, calls = recording_transport(cdn_ok)
        adapter = HttpProviderAdapter(
            fal_spec, workspace_root=workspace, transport=transport)
        out = adapter.retrieve(
            "fal-job-001",
            "https://fal.media/files/abc123?sig=TOPSECRET123",
            {"execution_id": "exec-cdn-ok"})
        check("CF-P1-005-R4-SEC-cdn-download-ok",
              out == os.path.join("outputs", "exec-cdn-ok")
              and open(os.path.join(workspace, out), "rb").read()
              == PNG_1X1)
        check("CF-P1-005-R4-SEC-cdn-download-no-auth",
              len(calls) == 1
              and "Authorization" not in calls[0][2]
              and "TOPSECRET123" not in json.dumps(calls[0][2]),
              str(calls[0][2]))

        # A redirect hop's body is never download content: only
        # the final hop's bytes land in the file.
        def cdn_redirect(method, url, headers, body):
            if url.endswith("/first"):
                return (302, {"location":
                              "https://fal.media/files/second"},
                        b"REDIRECT-BODY-MUST-NOT-LAND")
            return (200, {}, PNG_1X1)
        transport, calls = recording_transport(cdn_redirect)
        adapter = HttpProviderAdapter(
            fal_spec, workspace_root=workspace, transport=transport)
        out = adapter.retrieve(
            "fal-job-001", "https://fal.media/files/first",
            {"execution_id": "exec-cdn-redirect"})
        check("CF-P1-005-R4-SEC-cdn-redirect-body-discarded",
              open(os.path.join(workspace, out), "rb").read() == PNG_1X1)

        # Download size limit: over-limit leaves no partial file.
        def big(method, url, headers, body):
            return (200, {}, b"x" * 100)
        transport, calls = recording_transport(big)
        adapter = HttpProviderAdapter(
            fal_spec, workspace_root=workspace, transport=transport,
            max_download_bytes=10)
        expect_error("CF-P1-005-R4-SEC-download-size-limit",
                     lambda: adapter.retrieve(
                         "fal-job-001", "https://fal.media/files/big",
                         {"execution_id": "exec-too-big"}))
        check("CF-P1-005-R4-SEC-download-size-no-file",
              not os.path.exists(
                  os.path.join(workspace, "outputs", "exec-too-big")))

        # An HTTP error on download leaves no file either.
        def missing(method, url, headers, body):
            return (404, {}, b"not found")
        transport, calls = recording_transport(missing)
        adapter = HttpProviderAdapter(
            fal_spec, workspace_root=workspace, transport=transport)
        expect_error("CF-P1-005-R4-SEC-download-404",
                     lambda: adapter.retrieve(
                         "fal-job-001", "https://fal.media/files/nope",
                         {"execution_id": "exec-404"}))
        check("CF-P1-005-R4-SEC-download-404-no-file",
              not os.path.exists(
                  os.path.join(workspace, "outputs", "exec-404")))
    finally:
        restore_env("FAL_KEY", old)


def legitimate_group(tmpdir):
    """CF-P1-005-R4-SEC: legitimate provider calls still work."""
    workspace = os.path.join(tmpdir, "sec-legit")
    os.makedirs(workspace)
    # OpenAI sync image through the policy + mock transport.
    old = set_env("OPENAI_API_KEY", "test-openai-key")
    try:
        openai_spec = dict(PROVIDER_SPECS["provider-openai-image"])
        openai_spec["provider_id"] = "provider-openai-image"
        calls = []

        def image_transport(method, url, *, headers=None, body=None):
            calls.append((method, url, headers or {}))
            payload = {"data": [{"b64_json": base64.b64encode(
                PNG_1X1).decode("ascii")}]}
            return (200, {"content-type": "application/json"},
                    json.dumps(payload).encode("utf-8"))
        adapter = HttpProviderAdapter(
            openai_spec, workspace_root=workspace,
            transport=image_transport)
        packet = {"task_id": "task-img-001",
                  "task_type": "image-generation",
                  "canonical_instruction": "a red boat on a river"}
        result = adapter.submit(
            adapter.prepare(packet, {"execution_id": "exec-img-001"}),
            {"execution_id": "exec-img-001"})
        check("CF-P1-005-R4-SEC-legit-openai-submit",
              result.get("completed") is True
              and result.get("output") is not None
              and calls[0][1]
              == "https://api.openai.com/v1/images/generations"
              and calls[0][2].get("Authorization")
              == "Bearer test-openai-key")
    finally:
        restore_env("OPENAI_API_KEY", old)

    # A spec whose submit URL is outside its own allowlist is
    # refused before the transport is called (fail closed on a
    # misconfigured spec).
    old = set_env("OPENAI_API_KEY", "test-openai-key")
    try:
        bad_spec = dict(PROVIDER_SPECS["provider-openai-image"])
        bad_spec["provider_id"] = "provider-openai-image"
        bad_spec["api_origins"] = []
        transport, calls = recording_transport(
            lambda m, u, h, b: (200, {}, b"{}"))
        adapter = HttpProviderAdapter(
            bad_spec, workspace_root=workspace, transport=transport)
        packet = {"task_id": "task-img-001",
                  "task_type": "image-generation",
                  "canonical_instruction": "a red boat"}
        expect_error("CF-P1-005-R4-SEC-empty-allowlist-refused",
                     lambda: adapter.submit(
                         adapter.prepare(packet, {}), {}))
        check("CF-P1-005-R4-SEC-empty-allowlist-no-call",
              len(calls) == 0, str(len(calls)))
    finally:
        restore_env("OPENAI_API_KEY", old)


def _make_test_ca(tmpdir, common_name):
    """A throwaway CA + server cert (openssl) for one hostname."""
    openssl = shutil.which("openssl")
    if openssl is None:
        raise RuntimeError("openssl is required for the TLS test")
    ca_key = os.path.join(tmpdir, "ca.key")
    ca_crt = os.path.join(tmpdir, "ca.crt")
    srv_key = os.path.join(tmpdir, "srv.key")
    srv_csr = os.path.join(tmpdir, "srv.csr")
    srv_crt = os.path.join(tmpdir, "srv.crt")
    ext = os.path.join(tmpdir, "ext.cnf")
    with open(ext, "w", encoding="utf-8") as handle:
        handle.write(f"subjectAltName=DNS:{common_name}\n")
    subprocess.run([openssl, "req", "-x509", "-newkey", "rsa:2048",
                    "-keyout", ca_key, "-out", ca_crt, "-days", "2",
                    "-nodes", "-subj", "/CN=CF Test CA"],
                   check=True, capture_output=True, timeout=60)
    subprocess.run([openssl, "req", "-newkey", "rsa:2048",
                    "-keyout", srv_key, "-out", srv_csr, "-nodes",
                    "-subj", f"/CN={common_name}"],
                   check=True, capture_output=True, timeout=60)
    subprocess.run([openssl, "x509", "-req", "-in", srv_csr,
                    "-CA", ca_crt, "-CAkey", ca_key,
                    "-CAcreateserial", "-out", srv_crt, "-days", "2",
                    "-extfile", ext],
                   check=True, capture_output=True, timeout=60)
    return ca_crt, srv_key, srv_crt


class _FixedHandler(http.server.BaseHTTPRequestHandler):
    seen_hosts = []

    def do_GET(self):  # noqa: N802 - http.server naming
        _FixedHandler.seen_hosts.append(self.headers.get("Host"))
        body = b"pinned-ok"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # noqa: D102 - silence the server
        pass


def pinned_tls_group(tmpdir):
    """CF-P1-005-R4-SEC: the pinned transport (local test CA)."""
    workdir = os.path.join(tmpdir, "sec-tls")
    os.makedirs(workdir)
    try:
        ca_crt, srv_key, srv_crt = _make_test_ca(workdir, "provider.test")
    except RuntimeError as exc:
        check("CF-P1-005-R4-SEC-tls-openssl-present", False, str(exc))
        return
    server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_ctx.load_cert_chain(srv_crt, srv_key)
    httpd = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), _FixedHandler)
    httpd.socket = server_ctx.wrap_socket(httpd.socket, server_side=True)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    client_ctx = ssl.create_default_context(cafile=ca_crt)
    try:
        _FixedHandler.seen_hosts = []
        # The pinned address is loopback (the test server), while
        # SNI, certificate validation and the Host header name
        # "provider.test": the exchange goes to the pinned address
        # and still validates the hostname's certificate.
        status, headers, body = _pinned_https_request(
            "provider.test", "127.0.0.1", "GET", "/hello",
            ssl_context=client_ctx, port=port)
        check("CF-P1-005-R4-SEC-pinned-tls-ok",
              status == 200 and body == b"pinned-ok",
              f"{status} {body!r}")
        check("CF-P1-005-R4-SEC-pinned-tls-host-header",
              _FixedHandler.seen_hosts == [f"provider.test:{port}"],
              str(_FixedHandler.seen_hosts))
        # A certificate for another hostname is refused: SNI +
        # certificate validation really run against the hostname.
        _FixedHandler.seen_hosts = []
        try:
            _pinned_https_request(
                "other.test", "127.0.0.1", "GET", "/hello",
                ssl_context=client_ctx, port=port)
            check("CF-P1-005-R4-SEC-pinned-tls-wrong-host", False,
                  "wrong-host certificate was accepted")
        except MediaExecutionError as exc:
            check("CF-P1-005-R4-SEC-pinned-tls-wrong-host",
                  exc.code == "submission-uncertain")
        # An untrusted server certificate is refused too.
        try:
            _pinned_https_request(
                "provider.test", "127.0.0.1", "GET", "/hello",
                ssl_context=ssl.create_default_context(), port=port)
            check("CF-P1-005-R4-SEC-pinned-tls-untrusted", False,
                  "untrusted certificate was accepted")
        except MediaExecutionError as exc:
            check("CF-P1-005-R4-SEC-pinned-tls-untrusted",
                  exc.code == "submission-uncertain")
    finally:
        httpd.shutdown()
        httpd.server_close()


def main():
    tmpdir = tempfile.mkdtemp(prefix="cf-p1-005-r4-sec-")
    structure_group()
    resolution_group()
    redirect_group(tmpdir)
    async_url_group(tmpdir)
    retrieve_group(tmpdir)
    legitimate_group(tmpdir)
    pinned_tls_group(tmpdir)
    print(f"--- CF-P1-005-R4-SEC: {_checks[0]} checks, "
          f"{len(failures)} failures ---")
    if failures:
        print("FAILURES: " + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
