"""Consistency Frame P1 — provider URL security policy
(CF-WO-P1-005-R4, workstream A).

Every outbound request an external provider adapter makes goes
through this policy before any byte is sent or received. The
policy is deliberately small and transport-independent: it
validates the URL structure, the origin against an explicit
per-provider allowlist, and — for the real transport — the DNS
resolution of the destination, and it pins the connection to a
validated resolved address so the hostname cannot resolve to a
different destination between validation and connection.

What it enforces
----------------
- Only ``https`` to an explicitly allow-listed origin, one list
  for provider API calls (``api``) and a separate list for signed
  output/CDN download URLs (``output``). No suffix or wildcard
  matching: the host must equal an allow-listed origin exactly
  after lower-casing.
- No userinfo, no non-443 port, no ``file://`` / ``ftp://`` /
  plain-``http`` downgrade, no empty host, no trailing-dot host,
  no underscore / percent / non-ASCII character in the host, no
  empty or malformed label, no backslash anywhere in the URL.
- No IP-literal host at all, and no alternate numeric address
  representation (``0x7f000001``, ``0177.0.0.1``,
  ``2130706433``, ``127.1``): a hostname that looks numeric is
  refused outright, so an attacker cannot smuggle a loopback or
  private address past the allowlist in a form the resolver
  would interpret differently.
- No encoded path trick: a path segment that percent-decodes to
  ``.`` or ``..`` (or to NUL) is refused.
- Output origins may carry per-host path prefixes
  (``output_path_prefixes``): a host listed there accepts only
  output URLs whose path starts with one of its prefixes, so a
  shared-host origin (for example ``storage.googleapis.com``,
  permitted only under ``/falserverless/`` for the fal-video
  contract) never becomes a blanket allow for every bucket on
  that host. The prefix rule applies to the output purpose
  only, and only on the policy instance built for that
  provider/model contract.
- Every resolved address must be a public address: loopback,
  private (RFC 1918 and carrier-grade NAT), link-local,
  multicast, reserved, unspecified and cloud-metadata
  (``169.254.169.254``) destinations are all refused, for IPv4
  and IPv6, including IPv4-mapped IPv6 addresses. If ANY
  returned address is prohibited, the destination is refused —
  a resolver returning both a public and a private address is
  not a safe destination.
- Redirects are validated hop by hop by the caller (see
  ``HttpProviderAdapter._request``); this module supplies the
  per-hop validation and the pinned single-hop request.

What the pinned transport protects against — and what it does not
------------------------------------------------------------------
``pinned_request`` resolves the hostname once, validates every
returned address, and then connects to one validated address
while keeping TLS server-name indication and certificate
validation against the original hostname. That closes the
time-of-check/time-of-use gap in which a hostname could resolve
to a prohibited destination between validation and connection
(DNS rebinding against this client): the address actually
connected to is one the policy already approved, and the
certificate must still match the hostname.

It does NOT protect against a compromised or malicious resolver
returning a public attacker address that holds a valid
certificate for the hostname, nor against the provider origin
itself being malicious. A trusted resolver (and DNSSEC where
available) remains an infrastructure responsibility; this module
documents the boundary instead of claiming protection it does
not provide. A one-time hostname check alone is never presented
as DNS-rebinding protection anywhere in this codebase.

Failure mode: fail closed. Any validation that cannot be
completed (unresolvable host, empty answer, resolver error,
unparseable address) refuses the request. Error messages never
include a URL query string, userinfo or credential: they carry
only ``scheme://host/path`` (see :func:`safe_url_for_message`).
"""
from __future__ import annotations

import http.client
import ipaddress
import re
import socket
import ssl
import urllib.parse

from .media_execution import MediaExecutionError

#: Maximum redirects the adapter follows for one request.
MAX_REDIRECTS = 5
#: Maximum response body a non-streaming request may return.
MAX_RESPONSE_BYTES = 16 * 1024 * 1024  # 16 MiB
#: Maximum streamed download when the caller sets no lower limit.
MAX_DOWNLOAD_BYTES = 512 * 1024 * 1024  # 512 MiB
_DEFAULT_TIMEOUT_S = 120

# Provider-specific output-origin path rules (CF-WO-P1-006-R2-PREFLIGHT).
#
# The fal.ai Kling Video v3 Pro model page documents its output
# example on Google Cloud Storage, not on the fal CDN:
# https://storage.googleapis.com/falserverless/example_outputs/
# kling-v3/pro-i2v/out.mp4
# (model page https://fal.ai/models/fal-ai/kling-video/v3/pro/
# image-to-video/api). The retention page says generated outputs
# go to the fal CDN, but for THIS endpoint the model-specific
# page wins: outputs land on GCS, so the fal CDN ACL does NOT
# protect a storage.googleapis.com output URL and GCS outputs
# are public-by-link. The GCS rule below is therefore bound to
# this one provider/model contract only (it lives on the
# provider-fal-video adapter's policy instance, built from that
# spec) and permits exactly one bucket path prefix — no broad
# wildcard for Google or fal subdomains, and no global allow of
# storage.googleapis.com for arbitrary downloads.
FAL_VIDEO_GCS_HOST = "storage.googleapis.com"
FAL_VIDEO_GCS_PATH_PREFIX = "/falserverless/"
FAL_VIDEO_GCS_OUTPUT_EXAMPLE = (
    "https://storage.googleapis.com/falserverless/"
    "example_outputs/kling-v3/pro-i2v/out.mp4")
FAL_VIDEO_MODEL = "fal-ai/kling-video/v3/pro/image-to-video"
FAL_VIDEO_PROVIDER_ID = "provider-fal-video"

# Provider job ids, operation names and endpoint segments travel
# inside URLs the adapter constructs. They must be plain path
# tokens — no "..", no leading slash, no query, no whitespace.
_JOB_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/:-]{0,127}$")
_OPERATION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}$")
_ENDPOINT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")
_LABEL_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
_NUMERIC_HOST_RE = re.compile(r"^[0-9.]+$")
_HEX_HOST_RE = re.compile(r"^0[xX][0-9a-fA-F.]+$")

#: Header names that carry provider credentials. They are never
#: forwarded to a redirect target on another origin, or to a
#: signed output/CDN download URL (which carries its own query
#: authorization).
AUTH_HEADER_NAMES = frozenset(
    {"authorization", "x-goog-api-key", "xi-api-key"})


def _fail(message: str) -> None:
    raise MediaExecutionError(message, code="validation-failed")


def safe_url_for_message(url: str) -> str:
    """``scheme://host/path`` only — never a query or userinfo.

    Used in every error message that names a URL, so a signed
    download URL's query authorization (or a smuggled credential)
    can never leak into a log, a report or an exception.
    """
    try:
        split = urllib.parse.urlsplit(url)
    except ValueError:
        return "<unparseable url>"
    host = split.hostname or ""
    port = ""
    try:
        if split.port is not None:
            port = f":{split.port}"
    except ValueError:
        port = ""
    path = split.path or "/"
    return f"{split.scheme or '?'}://{host}{port}{path}"


def redact_result_url(url: str) -> str:
    """A provider result URL with sensitive query parameters removed.

    The same ``scheme://host/path`` form as
    :func:`safe_url_for_message`: the original result URL is
    recorded in this redacted form only, so a signed download
    URL's query authorization is never stored, logged or
    reported.
    """
    return safe_url_for_message(url)


def record_result_url(url: str) -> dict:
    """A safe record of a provider result URL (no query string).

    Returns ``{"url", "host", "path"}`` — the redacted URL plus
    its host and path for audit. The query string (which may
    carry signed-download authorization) is never recorded.
    Raises MediaExecutionError on an unparseable URL.
    """
    if not isinstance(url, str) or not url:
        _fail("provider result URL must be a non-empty string")
    try:
        split = urllib.parse.urlsplit(url)
    except ValueError:
        _fail("provider result URL is unparseable")
    host = (split.hostname or "").lower()
    if not host:
        _fail("provider result URL has no host")
    return {"url": safe_url_for_message(url), "host": host,
            "path": split.path or "/"}


def _is_prohibited_address(address) -> bool:
    """True when an ipaddress object is not a public destination."""
    if address.is_loopback or address.is_private \
            or address.is_link_local or address.is_multicast \
            or address.is_reserved or address.is_unspecified:
        return True
    mapped = getattr(address, "ipv4_mapped", None)
    if mapped is not None:
        return _is_prohibited_address(mapped)
    return False


def validate_resolved_addresses(addresses) -> list:
    """Require every resolved address to be a public address.

    Returns the parsed address objects. Any prohibited address —
    loopback, private, link-local, multicast, reserved,
    unspecified, cloud-metadata, or an IPv4-mapped IPv6 address
    whose mapped address is prohibited — refuses the whole
    destination, even when another returned address is public.
    An empty or unparseable answer fails closed.
    """
    if not isinstance(addresses, (list, tuple)) or not addresses:
        _fail("destination DNS resolution returned no addresses")
    parsed = []
    for raw in addresses:
        try:
            address = ipaddress.ip_address(str(raw))
        except ValueError:
            _fail("destination DNS resolution returned an "
                  "unparseable address")
        if _is_prohibited_address(address):
            _fail("destination resolves to a non-public address "
                  "(loopback, private, link-local, multicast, "
                  "reserved or unspecified)")
        parsed.append(address)
    return parsed


def validate_provider_job_id(job_id) -> str:
    """A provider job id that is safe to embed in a URL path."""
    if not isinstance(job_id, str) or not _JOB_ID_RE.match(job_id):
        _fail("provider job id is not a safe URL path token")
    return job_id


def validate_model_id(model) -> str:
    """A provider model id that is safe to embed in a URL path."""
    if not isinstance(model, str) or not _MODEL_RE.match(model) \
            or ".." in model.split("/"):
        _fail("provider model id is not a safe URL path token")
    return model


def validate_operation_name(name) -> str:
    """A provider operation name (e.g. ``operations/<job-id>``)."""
    if not isinstance(name, str) or not _OPERATION_RE.match(name) \
            or ".." in name.split("/") or name.startswith("/"):
        _fail("provider operation name is not a safe URL path")
    return name


def validate_endpoint_segment(segment) -> str:
    """One provider endpoint segment (e.g. a fal/LTX endpoint)."""
    if not isinstance(segment, str) \
            or not _ENDPOINT_RE.match(segment) \
            or ".." in segment.split("/"):
        _fail("provider endpoint is not a safe URL path segment")
    return segment


def _default_resolver(host: str) -> list:
    """Resolve ``host`` with the system resolver (injectable in tests)."""
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except (socket.gaierror, OSError):
        _fail(f"destination host {host!r} did not resolve")
    seen = []
    for info in infos:
        address = info[4][0]
        if address not in seen:
            seen.append(address)
    return seen


class ProviderURLPolicy:
    """URL security policy for one external provider's origins.

    ``api_origins`` are the permitted origins for provider API
    calls; ``output_origins`` are the permitted origins for signed
    output/CDN download URLs — the two lists are separate on
    purpose, so a download URL can never be mistaken for an API
    call (and its query authorization is never sent an
    Authorization header). ``output_path_prefixes`` is an
    optional mapping of output host to the path prefixes
    permitted on that host (output purpose only): a host listed
    here accepts only URLs whose path starts with one of its
    prefixes, so an origin allowlist can never become a blanket
    allow for every path on a shared host (for example
    ``storage.googleapis.com`` permits only
    ``/falserverless/`` for the fal-video contract — every other
    GCS bucket/path is rejected). ``resolver`` is an injectable
    ``host -> [address, ...]`` callable; the default is the system
    resolver.
    """

    def __init__(self, *, api_origins=(), output_origins=(),
                 output_path_prefixes=None, resolver=None,
                 max_redirects=MAX_REDIRECTS,
                 max_response_bytes=MAX_RESPONSE_BYTES,
                 timeout_s=_DEFAULT_TIMEOUT_S):
        self.api_origins = frozenset(
            str(origin).lower() for origin in (api_origins or ()))
        self.output_origins = frozenset(
            str(origin).lower() for origin in (output_origins or ()))
        self.output_path_prefixes = {
            str(host).lower(): tuple(str(prefix) for prefix in prefixes)
            for host, prefixes in
            (output_path_prefixes or {}).items()}
        self.resolver = resolver or _default_resolver
        self.max_redirects = max_redirects
        self.max_response_bytes = max_response_bytes
        self.timeout_s = timeout_s

    # -- structure -------------------------------------------------
    def validate_url(self, url, purpose: str) -> dict:
        """Validate one URL for ``purpose`` (``"api"`` / ``"output"``).

        Returns ``{"scheme", "host", "port", "path", "query"}``.
        Raises MediaExecutionError (code ``validation-failed``) on
        any violation. Nothing is resolved here: resolution is a
        separate step (:meth:`validate_destination`) so a caller
        can refuse a structurally bad URL before touching DNS.
        """
        if not isinstance(url, str) or not url:
            _fail("provider URL must be a non-empty string")
        if any(ord(char) <= 0x20 or ord(char) == 0x7F
               for char in url):
            _fail("provider URL contains whitespace or control "
                  "characters")
        if "\\" in url:
            _fail("provider URL contains a backslash")
        try:
            split = urllib.parse.urlsplit(url)
        except ValueError:
            _fail("provider URL is unparseable")
        if split.scheme != "https":
            _fail("provider URL must use https "
                  f"(got {split.scheme or 'no scheme'})")
        if split.username is not None or split.password is not None:
            _fail("provider URL must not carry userinfo")
        host = split.hostname
        if not host:
            _fail("provider URL has no host")
        host = host.lower()
        if host.endswith("."):
            _fail("provider URL host has a trailing dot")
        if "%" in host or "_" in host:
            _fail("provider URL host contains an encoded or "
                  "underscore character")
        try:
            host.encode("ascii")
        except UnicodeEncodeError:
            _fail("provider URL host contains non-ASCII characters")
        if len(host) > 253:
            _fail("provider URL host is too long")
        labels = host.split(".")
        for label in labels:
            if not label or not _LABEL_RE.match(label):
                _fail("provider URL host has an empty or malformed "
                      "label")
        # No IP-literal host, and no alternate numeric address
        # representation: a hostname that looks numeric is refused
        # outright, whatever the resolver would make of it.
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            _fail("provider URL host must be a hostname, not an "
                  "IP literal")
        if _NUMERIC_HOST_RE.match(host) or _HEX_HOST_RE.match(host):
            _fail("provider URL host is an alternate numeric "
                  "address representation")
        for label in labels:
            if len(label) > 1 and label[0] == "0" \
                    and label.isdigit():
                _fail("provider URL host uses an octal address "
                      "representation")
        try:
            port = split.port
        except ValueError:
            _fail("provider URL has an invalid port")
        if port is not None and port != 443:
            _fail("provider URL port must be 443")
        path = split.path or ""
        if "\x00" in path:
            _fail("provider URL path contains a NUL byte")
        for segment in urllib.parse.unquote(path).split("/"):
            if segment in (".", "..") or "\x00" in segment:
                _fail("provider URL path contains an encoded "
                      "traversal segment")
        if purpose == "api":
            allowed = self.api_origins
        elif purpose == "output":
            allowed = self.output_origins
        else:
            _fail(f"unknown URL purpose {purpose!r}")
        if host not in allowed:
            _fail(f"provider URL host {host!r} is not an approved "
                  f"origin for {purpose} requests")
        if purpose == "output":
            prefixes = self.output_path_prefixes.get(host)
            if prefixes is not None and not any(
                    path.startswith(prefix) for prefix in prefixes):
                _fail(f"provider URL path {path!r} on host "
                      f"{host!r} is not a permitted output path "
                      "for this provider contract")
        return {"scheme": "https", "host": host,
                "port": port if port is not None else 443,
                "path": path, "query": split.query or ""}

    # -- resolution ------------------------------------------------
    def resolve_host(self, host: str) -> list:
        """Resolve ``host``; returns the unique addresses in order."""
        try:
            addresses = self.resolver(host)
        except MediaExecutionError:
            raise
        except Exception:  # noqa: BLE001 - resolver guard
            _fail(f"destination host {host!r} did not resolve")
        if not isinstance(addresses, (list, tuple)) or not addresses:
            _fail(f"destination host {host!r} did not resolve")
        seen = []
        for address in addresses:
            if address not in seen:
                seen.append(address)
        return seen

    def validate_destination(self, url, purpose: str) -> tuple:
        """Validate a URL and its DNS resolution.

        Returns ``(parsed, pinned_ip)``: the parsed URL plus the
        first validated public address to connect to. Every
        returned address must be public; a resolver that returns
        both a public and a private address is refused.
        """
        parsed = self.validate_url(url, purpose)
        addresses = self.resolve_host(parsed["host"])
        validate_resolved_addresses(addresses)
        return parsed, str(addresses[0])

    # -- pinned transport ------------------------------------------
    def pinned_request(self, method, url, *, purpose, headers=None,
                       body=None, ssl_context=None,
                       raw_response=False) -> tuple:
        """One HTTPS request to a validated, pinned destination.

        Validates the URL and its resolution, connects to the
        pinned address while keeping TLS SNI and certificate
        validation against the original hostname, sends the
        request, and returns ``(status, headers, body)``. The body
        is capped at ``max_response_bytes``. With
        ``raw_response=True`` the body is NOT read at all: the
        third element is the live ``http.client.HTTPResponse`` and
        the caller owns it — it must read (or discard) and close
        it, which closes the socket. That mode exists so a
        redirect loop can decide from the status before any
        download byte is written. ``ssl_context`` exists only so
        tests can present their own test CA; production callers
        never pass one (the default context validates against the
        system trust store).
        """
        parsed, pinned_ip = self.validate_destination(url, purpose)
        target = parsed["path"] or "/"
        if parsed["query"]:
            target += "?" + parsed["query"]
        status, resp_headers, payload = _pinned_https_request(
            parsed["host"], pinned_ip, method, target,
            headers=headers, body=body, timeout_s=self.timeout_s,
            ssl_context=ssl_context, raw_response=raw_response,
            max_response_bytes=self.max_response_bytes)
        if raw_response:
            return status, resp_headers, payload
        if len(payload) > self.max_response_bytes:
            raise MediaExecutionError(
                "provider response exceeds the size limit",
                code="validation-failed")
        return status, resp_headers, payload


def _pinned_https_request(host, pinned_ip, method, target, *,
                          headers=None, body=None,
                          timeout_s=_DEFAULT_TIMEOUT_S,
                          ssl_context=None, raw_response=False,
                          max_response_bytes=MAX_RESPONSE_BYTES,
                          port=443):
    """One HTTPS exchange with an explicit pinned address.

    Connects to ``pinned_ip`` (not to whatever the hostname
    resolves to at connect time) while TLS SNI, certificate
    validation and the Host header all name ``host``. This is the
    unit-testable half of :meth:`ProviderURLPolicy.pinned_request`:
    the policy half validates the destination, this half proves
    the connection actually goes to the pinned address with the
    hostname's certificate. Callers pass a validated pinned
    address; this function performs no allowlist or DNS check of
    its own. ``port`` is 443 in production; tests pass their local
    test server's port.
    """
    context = ssl_context or ssl.create_default_context()
    try:
        raw = socket.create_connection(
            (pinned_ip, port), timeout=timeout_s)
    except OSError as exc:
        raise MediaExecutionError(
            "provider request failed: "
            f"{_redact_socket_error(exc)}",
            code="submission-uncertain")
    conn = None
    returned_response = False
    try:
        raw.settimeout(timeout_s)
        try:
            tls = context.wrap_socket(raw, server_hostname=host)
        except (ssl.SSLError, OSError) as exc:
            raise MediaExecutionError(
                "provider request failed: TLS handshake with "
                f"{host} failed",
                code="submission-uncertain") from exc
        conn = http.client.HTTPSConnection(host, port,
                                          timeout=timeout_s)
        # Pre-set the socket: the connection below goes to the
        # pinned address, while SNI, certificate validation and
        # the Host header all still name the hostname.
        conn.sock = tls
        try:
            conn.request(method, target, body=body,
                         headers=dict(headers or {}))
            response = conn.getresponse()
        except (http.client.HTTPException, OSError) as exc:
            raise MediaExecutionError(
                "provider request failed: "
                f"{_redact_socket_error(exc)}",
                code="submission-uncertain")
        resp_headers = {key.lower(): value for key, value
                        in response.getheaders()}
        if raw_response:
            # Ownership of the socket passes to the caller with
            # the response; the finally-block below must not
            # close the connection out from under it.
            returned_response = True
            return response.status, resp_headers, response
        body_bytes = response.read(max_response_bytes + 1)
        return response.status, resp_headers, body_bytes
    finally:
        if returned_response:
            # The socket belongs to the returned response now;
            # the caller closes it.
            pass
        elif conn is not None:
            try:
                conn.close()
            except Exception:  # noqa: BLE001 - close is best-effort
                pass
        else:
            try:
                raw.close()
            except Exception:  # noqa: BLE001 - close is best-effort
                pass


def _redact_socket_error(exc: BaseException) -> str:
    """Socket error text without any address that could leak a
    resolved destination into a log line."""
    text = str(exc) or type(exc).__name__
    return text[:200]


__all__ = [
    "MAX_REDIRECTS",
    "MAX_RESPONSE_BYTES",
    "MAX_DOWNLOAD_BYTES",
    "AUTH_HEADER_NAMES",
    "FAL_VIDEO_GCS_HOST",
    "FAL_VIDEO_GCS_PATH_PREFIX",
    "FAL_VIDEO_GCS_OUTPUT_EXAMPLE",
    "FAL_VIDEO_MODEL",
    "FAL_VIDEO_PROVIDER_ID",
    "ProviderURLPolicy",
    "safe_url_for_message",
    "redact_result_url",
    "record_result_url",
    "validate_resolved_addresses",
    "validate_provider_job_id",
    "validate_model_id",
    "validate_operation_name",
    "validate_endpoint_segment",
]
