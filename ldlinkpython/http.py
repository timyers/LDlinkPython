# ldlinkpython/http.py
#
# Shared HTTP request helper used by all ldlinkpython endpoint wrappers.
#
# What it does
# - Provides a single `request()` function that builds and sends LDlink REST requests via `requests`.
# - Serializes every network call behind one global `threading.Lock` so users cannot accidentally
#   run concurrent requests (LDlink can be sensitive to bursts, and this keeps behavior predictable).
# - Ensures the LDlink API token is always supplied as the required query parameter `token=...`,
#   coming from an explicit `token=` argument or the `LDLINK_TOKEN` environment variable.
# - Returns parsed JSON when the response looks like JSON; otherwise returns the raw text body.
# - Raises a clear RuntimeError on HTTP errors (status >= 400) including a short response snippet.
# - If the initial request fails with a connection/TLS style error (requests ConnectionError),
#   retries once with a temporary “force IPv4 only” DNS resolution patch, which can work around
#   occasional IPv6/network handshake issues seen in some environments.
#
# Why it exists
# - Keeps request logic consistent across endpoints (token handling, error messages, parsing).
# - Centralizes reliability workarounds (global serialization and IPv4 retry) in one place.
# - Makes endpoint functions smaller and easier to maintain and test.

# ldlinkpython/http.py
from __future__ import annotations

import json
import socket
import threading
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional, Union
from urllib.parse import urljoin

import requests
import urllib3.util.connection
from requests import Response

from .parsing import is_json_response
from .validators import ensure_token

_REQUEST_LOCK = threading.Lock()


@contextmanager
def _request_lock() -> Iterator[None]:
    """
    Global lock to serialize all HTTP requests.

    Kept as a wrapper so tests can monkeypatch it to verify it is used.
    """
    _REQUEST_LOCK.acquire()
    try:
        yield
    finally:
        _REQUEST_LOCK.release()


@contextmanager
def _force_ipv4_only() -> Iterator[None]:
    """
    Temporarily force urllib3 DNS resolution to return IPv4 only.

    Used as a single retry fallback for connection/TLS handshake style errors.
    """
    original = urllib3.util.connection.allowed_gai_family

    def allowed_gai_family_ipv4() -> int:
        return socket.AF_INET

    urllib3.util.connection.allowed_gai_family = allowed_gai_family_ipv4  # type: ignore[assignment]
    try:
        yield
    finally:
        urllib3.util.connection.allowed_gai_family = original  # type: ignore[assignment]


def _parse_body(resp: Response) -> Union[Dict[str, Any], list, str]:
    text = resp.text if resp.text is not None else ""
    if is_json_response(text):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return text


def _raise_for_status(resp: Response, url: str) -> None:
    if resp.status_code >= 400:
        snippet = (resp.text or "").strip().replace("\r", " ").replace("\n", " ")
        if len(snippet) > 500:
            snippet = snippet[:500] + "..."
        raise RuntimeError(
            f"LDlink request failed: HTTP {resp.status_code} {resp.reason} for {url}. "
            f"Response: {snippet}"
        )


def request(
    endpoint: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    token: Optional[str] = None,
    api_root: str,
    method: str = "GET",
    timeout: float = 60.0,
) -> Union[Dict[str, Any], list, str]:
    """
    Shared HTTP helper for LDlink REST endpoints.

    - Serializes all requests via a single global lock.
    - Adds token as query param token=...
    - Parses JSON if possible; otherwise returns raw text.
    - Retries once forcing IPv4 if the first attempt raises requests.ConnectionError.
    - Supports JSON request bodies and custom headers.

    Raises RuntimeError on HTTP status >= 400 or repeated connection failure.
    """
    tok = ensure_token(token)
    qparams: Dict[str, Any] = dict(params or {})
    qparams["token"] = tok

    base = api_root.rstrip("/") + "/"
    url = urljoin(base, endpoint.lstrip("/"))

    def _do_request() -> Response:
        return requests.request(
            method=method,
            url=url,
            params=qparams,
            json=json_body,
            headers=headers,
            timeout=timeout,
        )

    with _request_lock():
        try:
            resp = _do_request()
        except requests.exceptions.ConnectionError as e:
            with _force_ipv4_only():
                try:
                    resp = _do_request()
                except requests.exceptions.ConnectionError as e2:
                    raise RuntimeError(
                        f"LDlink request failed due to connection error after IPv4 retry for {url}. "
                        f"Original error: {e!r}; Retry error: {e2!r}"
                    ) from e2

    _raise_for_status(resp, url)
    return _parse_body(resp)