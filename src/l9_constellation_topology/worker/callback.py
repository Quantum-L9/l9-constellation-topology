"""Authenticated stage-result callback client."""

from __future__ import annotations

import os
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

from l9_constellation_topology.packets.transport import CallbackRef
from l9_constellation_topology.run import canonical_bytes

from .errors import WorkerError


def _callback_token(token_ref: str | None) -> str | None:
    if token_ref is None:
        return None
    if not token_ref.startswith("env:"):
        raise WorkerError(
            "callback-token-ref-invalid",
            "callback token_ref must use env:VARIABLE indirection",
            blocked=True,
        )
    name = token_ref.removeprefix("env:")
    value = os.environ.get(name)
    if not value:
        raise WorkerError(
            "callback-token-missing",
            f"callback token environment variable is not set: {name}",
            blocked=True,
        )
    return value


def send_callback(
    callback: CallbackRef,
    payload: object,
    *,
    attempts: int = 3,
    timeout_seconds: int = 20,
) -> None:
    parsed = urlparse(callback.url)
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise WorkerError(
            "callback-url-insecure",
            "callbacks require HTTPS except for local integration tests",
            blocked=True,
        )
    token = _callback_token(callback.token_ref)
    body = canonical_bytes(payload)
    headers = {"Content-Type": "application/json", "User-Agent": "l9-topology-worker/2.0.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    last_error = "callback failed"
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(callback.url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                if 200 <= response.status < 300:
                    return
                last_error = f"callback returned HTTP {response.status}"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
        if attempt < attempts:
            time.sleep(min(2 ** (attempt - 1), 4))
    raise WorkerError("callback-failed", last_error, retryable=True)
