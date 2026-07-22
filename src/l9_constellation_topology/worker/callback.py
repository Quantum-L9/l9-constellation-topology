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

_ENCODED_PATH_SEPARATORS = ("%2f", "%5c")


@dataclass(frozen=True)
class ResolvedCallback:
    callback_id: str
    url: str
    token: str | None
    allow_loopback: bool
    allowed_path_prefix: str
    expected_hosts: tuple[str, ...]
    expected_port: int | None


def _normalize_hostname(value: str) -> str:
    candidate = value.strip().rstrip(".").lower()
    try:
        return ipaddress.ip_address(candidate).compressed
    except ValueError:
        return candidate


def _contains_ambiguous_separator(value: str) -> bool:
    lowered = value.lower()
    return "\\" in value or any(token in lowered for token in _ENCODED_PATH_SEPARATORS)


def path_is_allowed(path: str, prefix: str) -> bool:
    """Return whether a raw URL path is within a normalized segment boundary."""

    normalized_path = path or "/"
    normalized_prefix = prefix.rstrip("/") or "/"
    if not normalized_path.startswith("/") or not normalized_prefix.startswith("/"):
        return False
    if _contains_ambiguous_separator(normalized_path) or _contains_ambiguous_separator(
        normalized_prefix
    ):
        return False
    if normalized_prefix == "/":
        return True
    return normalized_path == normalized_prefix or normalized_path.startswith(
        normalized_prefix + "/"
    )


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
    if not bool(raw.get("enabled", True)):
        raise WorkerError(
            "callback-id-disabled",
            f"callback ID is disabled by local policy: {callback.callback_id}",
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

    raw_hosts = raw.get("expected_hosts", ())
    if not isinstance(raw_hosts, (list, tuple)) or not all(
        isinstance(item, str) and item.strip() for item in raw_hosts
    ):
        raise WorkerError(
            "callback-policy-invalid",
            f"callback {callback.callback_id} expected_hosts must be a list of hostnames",
            blocked=True,
        )
    expected_hosts = tuple(sorted({_normalize_hostname(item) for item in raw_hosts}))
    allow_loopback = bool(raw.get("allow_loopback", False))
    if not allow_loopback and not expected_hosts:
        raise WorkerError(
            "callback-policy-hosts-required",
            f"callback {callback.callback_id} requires at least one expected host",
            blocked=True,
        )

    raw_port = raw.get("expected_port")
    expected_port: int | None
    if raw_port is None:
        expected_port = None
    elif isinstance(raw_port, int) and 1 <= raw_port <= 65535:
        expected_port = raw_port
    else:
        raise WorkerError(
            "callback-policy-invalid",
            f"callback {callback.callback_id} expected_port must be an integer from 1 to 65535",
            blocked=True,
        )

    allowed_path_prefix = str(raw.get("allowed_path_prefix", "/"))
    if not path_is_allowed(allowed_path_prefix, allowed_path_prefix):
        raise WorkerError(
            "callback-policy-invalid",
            f"callback {callback.callback_id} has an invalid allowed_path_prefix",
            blocked=True,
        )

    return ResolvedCallback(
        callback_id=callback.callback_id,
        url=url,
        token=token,
        allow_loopback=allow_loopback,
        allowed_path_prefix=allowed_path_prefix.rstrip("/") or "/",
        expected_hosts=expected_hosts,
        expected_port=expected_port,
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
            "HTTP callbacks are permitted only for a loopback-enabled callback ID",
            blocked=True,
        )

    hostname = _normalize_hostname(parsed.hostname)
    if endpoint.expected_hosts and hostname not in endpoint.expected_hosts:
        raise WorkerError(
            "callback-host-forbidden",
            f"callback host is outside the local allowlist: {hostname}",
            blocked=True,
        )

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if endpoint.expected_port is not None and port != endpoint.expected_port:
        raise WorkerError(
            "callback-port-forbidden",
            f"callback port is outside the local allowlist: {port}",
            blocked=True,
        )

    path = parsed.path or "/"
    if not path_is_allowed(path, endpoint.allowed_path_prefix):
        raise WorkerError(
            "callback-path-forbidden",
            f"callback path is outside the local allowlist: {path}",
            blocked=True,
        )

    addresses = _safe_addresses(hostname, port, allow_loopback=endpoint.allow_loopback)
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
