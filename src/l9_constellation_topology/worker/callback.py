"""Locally governed, authenticated stage-result callback client."""

from __future__ import annotations

import http.client
import ipaddress
import os
import socket
import ssl
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from l9_constellation_topology.packets.transport import CallbackRef
from l9_constellation_topology.run import canonical_bytes

from .errors import WorkerError


@dataclass(frozen=True)
class ResolvedCallback:
    callback_id: str
    url: str
    token: str | None
    allow_loopback: bool
    allowed_path_prefix: str


def _callback_config(callback: CallbackRef, policy: dict[str, Any]) -> ResolvedCallback:
    callbacks = policy.get("callbacks")
    if not isinstance(callbacks, dict):
        raise WorkerError(
            "callback-policy-invalid",
            "callback policy must define a callbacks mapping",
            blocked=True,
        )
    raw = callbacks.get(callback.callback_id)
    if not isinstance(raw, dict):
        raise WorkerError(
            "callback-id-forbidden",
            f"callback ID is not locally allowlisted: {callback.callback_id}",
            blocked=True,
        )
    url_env = raw.get("url_env")
    if not isinstance(url_env, str) or not url_env:
        raise WorkerError(
            "callback-policy-invalid",
            f"callback {callback.callback_id} does not define url_env",
            blocked=True,
        )
    url = os.environ.get(url_env)
    if not url:
        raise WorkerError(
            "callback-url-missing",
            f"local callback URL environment variable is not set: {url_env}",
            blocked=True,
        )
    credential_env = raw.get("credential_env")
    token = os.environ.get(str(credential_env)) if credential_env else None
    if bool(raw.get("credential_required", True)) and not token:
        raise WorkerError(
            "callback-token-missing",
            f"local callback credential is not set for {callback.callback_id}",
            blocked=True,
        )
    return ResolvedCallback(
        callback_id=callback.callback_id,
        url=url,
        token=token,
        allow_loopback=bool(raw.get("allow_loopback", False)),
        allowed_path_prefix=str(raw.get("allowed_path_prefix", "/")),
    )


def _safe_addresses(hostname: str, port: int, *, allow_loopback: bool) -> tuple[str, ...]:
    try:
        resolved = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise WorkerError(
            "callback-dns-resolution-failed",
            f"cannot resolve callback host {hostname}: {exc}",
            retryable=True,
        ) from exc
    addresses = tuple(sorted({item[4][0] for item in resolved}))
    if not addresses:
        raise WorkerError(
            "callback-dns-resolution-empty",
            f"callback host resolved to no addresses: {hostname}",
            retryable=True,
        )
    for value in addresses:
        address = ipaddress.ip_address(value)
        prohibited = (
            address.is_private
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
            or address.is_loopback
        )
        if prohibited and not (allow_loopback and address.is_loopback):
            raise WorkerError(
                "callback-address-forbidden",
                f"callback host resolves to a prohibited address: {value}",
                blocked=True,
            )
    return addresses


def _validate_endpoint(endpoint: ResolvedCallback) -> tuple[object, tuple[str, ...], int, str]:
    parsed = urlparse(endpoint.url)
    if parsed.username or parsed.password or parsed.fragment:
        raise WorkerError(
            "callback-url-invalid",
            "callback URL may not contain userinfo or fragments",
            blocked=True,
        )
    if not parsed.hostname:
        raise WorkerError("callback-url-invalid", "callback URL lacks a hostname", blocked=True)
    if parsed.scheme not in {"https", "http"}:
        raise WorkerError(
            "callback-url-invalid",
            "callback URL must use HTTPS",
            blocked=True,
        )
    if parsed.scheme == "http" and not endpoint.allow_loopback:
        raise WorkerError(
            "callback-url-insecure",
            "HTTP callbacks are permitted only for the local integration-test callback ID",
            blocked=True,
        )
    path = parsed.path or "/"
    if not path.startswith(endpoint.allowed_path_prefix):
        raise WorkerError(
            "callback-path-forbidden",
            f"callback path is outside the local allowlist: {path}",
            blocked=True,
        )
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    addresses = _safe_addresses(parsed.hostname, port, allow_loopback=endpoint.allow_loopback)
    request_target = path + (f"?{parsed.query}" if parsed.query else "")
    return parsed, addresses, port, request_target


def _post_once(
    endpoint: ResolvedCallback,
    body: bytes,
    headers: dict[str, str],
    *,
    timeout_seconds: int,
) -> int:
    parsed, addresses, port, request_target = _validate_endpoint(endpoint)
    hostname = str(parsed.hostname)
    last_error: OSError | ssl.SSLError | None = None
    for address in addresses:
        connection: http.client.HTTPConnection | http.client.HTTPSConnection | None = None
        try:
            if parsed.scheme == "https":
                raw_socket = socket.create_connection((address, port), timeout=timeout_seconds)
                tls_socket = ssl.create_default_context().wrap_socket(
                    raw_socket,
                    server_hostname=hostname,
                )
                connection = http.client.HTTPSConnection(
                    hostname,
                    port,
                    timeout=timeout_seconds,
                )
                connection.sock = tls_socket
            else:
                connection = http.client.HTTPConnection(
                    hostname,
                    port,
                    timeout=timeout_seconds,
                )
            connection.request("POST", request_target, body=body, headers=headers)
            response = connection.getresponse()
            response.read()
            if 300 <= response.status < 400:
                raise WorkerError(
                    "callback-redirect-forbidden",
                    f"callback redirects are forbidden: HTTP {response.status}",
                    blocked=True,
                )
            return response.status
        except WorkerError:
            raise
        except (OSError, ssl.SSLError) as exc:
            last_error = exc
        finally:
            if connection is not None:
                connection.close()
    raise WorkerError(
        "callback-connection-failed",
        str(last_error or "callback connection failed"),
        retryable=True,
    )


def send_callback(
    callback: CallbackRef,
    payload: object,
    *,
    callback_policy: dict[str, Any],
    attempts: int = 3,
    timeout_seconds: int = 20,
) -> None:
    endpoint = _callback_config(callback, callback_policy)
    body = canonical_bytes(payload)
    headers = {"Content-Type": "application/json", "User-Agent": "l9-topology-worker/2.0.0"}
    if endpoint.token:
        headers["Authorization"] = f"Bearer {endpoint.token}"
    last_error = "callback failed"
    for attempt in range(1, attempts + 1):
        try:
            status = _post_once(endpoint, body, headers, timeout_seconds=timeout_seconds)
            if 200 <= status < 300:
                return
            last_error = f"callback returned HTTP {status}"
        except WorkerError as exc:
            if exc.blocked:
                raise
            last_error = str(exc)
        if attempt < attempts:
            time.sleep(min(2 ** (attempt - 1), 4))
    raise WorkerError("callback-failed", last_error, retryable=True)
