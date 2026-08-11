"""Deployment policy, SSRF-safe networking, and bounded process execution.

The module intentionally uses only the Python standard library.  A deployment
can pass ``config={"security": ...}`` to a connector or set
``HUB_SECURITY_POLICY`` to an equivalent JSON object.
"""

import http.client
import ipaddress
import json
import logging
import os
import re
import socket
import ssl
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit

LOG = logging.getLogger("hub.security")


class SecurityError(ValueError):
    """A request was rejected by deployment security policy."""


_SECRET = re.compile(
    r"(?i)(authorization|cookie|token|secret|password|passwd|api[-_]?key)(\s*[:=]\s*)([^\s,;]+)"
)
_METADATA_HOSTS = {"metadata.google.internal", "metadata.azure.internal"}
_METADATA_IPS = {ipaddress.ip_address("169.254.169.254"), ipaddress.ip_address("169.254.170.2")}


def redact(value, secrets=()):
    """Remove common credential forms and explicitly supplied secret values."""
    text = str(value)
    text = _SECRET.sub(lambda m: m.group(1) + m.group(2) + "***", text)
    for secret in secrets:
        if secret:
            text = text.replace(str(secret), "***")
    return text


@dataclass(frozen=True)
class ValidatedTarget:
    url: str
    scheme: str
    hostname: str
    port: int
    addresses: tuple
    path: str


class SecurityPolicy:
    """Validated deployment policy with safe defaults."""

    def __init__(self, config=None):
        supplied = dict(config or {})
        if not supplied and os.environ.get("HUB_SECURITY_POLICY"):
            try:
                supplied = json.loads(os.environ["HUB_SECURITY_POLICY"])
            except json.JSONDecodeError as exc:
                raise SecurityError("HUB_SECURITY_POLICY must be valid JSON") from exc
        self.config = supplied.get("security", supplied)
        self.schemes = frozenset(self.config.get("allowed_schemes", ["http", "https"]))
        self.ports = frozenset(int(p) for p in self.config.get("allowed_ports", [80, 443]))
        self.max_redirects = int(self.config.get("max_redirects", 5))
        self.max_output = int(self.config.get("max_output_bytes", 1_000_000))
        self.plugins = self.config.get("plugins", {})

    def plugin(self, name):
        value = self.plugins.get(name, {})
        if not isinstance(value, Mapping):
            raise SecurityError(f"security.plugins.{name} must be an object")
        return value

    def require_capability(self, plugin, capability, action=None, approval=None, destructive=False):
        cfg = self.plugin(plugin)
        if capability not in cfg.get("capabilities", []):
            raise SecurityError(f"{plugin}: capability '{capability}' is not enabled")
        if destructive:
            allowed = cfg.get("destructive_actions", [])
            approvals = self.config.get("approvals", [])
            if action not in allowed or not approval or approval not in approvals:
                LOG.warning("security_authorization_denied plugin=%s action=%s", plugin, action)
                raise SecurityError(
                    f"{plugin}: destructive action '{action}' requires explicit policy and approval"
                )
            LOG.info(
                "security_authorization_granted plugin=%s action=%s approval=%s",
                plugin,
                action,
                approval,
            )

    @staticmethod
    def _public_address(raw):
        try:
            address = ipaddress.ip_address(raw.split("%", 1)[0])
        except ValueError as exc:
            raise SecurityError(f"resolver returned invalid IP address: {raw}") from exc
        if address in _METADATA_IPS:
            raise SecurityError("cloud metadata endpoints are blocked")
        if not address.is_global or any(
            (
                address.is_loopback,
                address.is_link_local,
                address.is_private,
                address.is_multicast,
                address.is_reserved,
                address.is_unspecified,
            )
        ):
            raise SecurityError(f"non-public address is blocked: {address}")
        return str(address)

    def resolve_host(self, host, port, socktype=socket.SOCK_STREAM):
        if not isinstance(host, str) or not host or len(host) > 253:
            raise SecurityError("host must be a non-empty DNS name or IP address")
        normalized = host.rstrip(".").lower()
        if normalized in _METADATA_HOSTS or normalized.endswith(".metadata.google.internal"):
            raise SecurityError("cloud metadata endpoints are blocked")
        try:
            infos = socket.getaddrinfo(host, port, type=socktype)
        except socket.gaierror as exc:
            raise SecurityError(f"cannot resolve host '{host}': {exc}") from exc
        addresses = tuple(dict.fromkeys(self._public_address(i[4][0]) for i in infos))
        if not addresses:
            raise SecurityError(f"host '{host}' resolved to no addresses")
        return addresses

    def validate_url(self, url):
        if not isinstance(url, str) or len(url) > 4096:
            raise SecurityError("URL must be a string of at most 4096 characters")
        parsed = urlsplit(url)
        scheme = parsed.scheme.lower()
        if scheme not in self.schemes:
            raise SecurityError(f"URL scheme '{scheme}' is not allowed")
        if not parsed.hostname or parsed.username or parsed.password:
            raise SecurityError("URL must contain a host and no user information")
        try:
            port = parsed.port or (443 if scheme == "https" else 80)
        except ValueError as exc:
            raise SecurityError("URL contains an invalid port") from exc
        if port not in self.ports:
            raise SecurityError(f"port {port} is not allowed")
        addresses = self.resolve_host(parsed.hostname, port)
        path = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
        return ValidatedTarget(url, scheme, parsed.hostname, port, addresses, path)


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, target, timeout):
        super().__init__(target.hostname, target.port, timeout=timeout)
        self._target = target

    def connect(self):
        self.sock = socket.create_connection((self._target.addresses[0], self.port), self.timeout)


class _PinnedHTTPSConnection(_PinnedHTTPConnection):
    def connect(self):
        super().connect()
        self.sock = ssl.create_default_context().wrap_socket(
            self.sock, server_hostname=self._target.hostname
        )


def pinned_urlopen(policy, url, method="GET", headers=None, timeout=30, max_bytes=None):
    """Open a URL while validating each redirect and pinning its resolved IP."""
    current = url
    for redirects in range(policy.max_redirects + 1):
        target = policy.validate_url(current)
        cls = _PinnedHTTPSConnection if target.scheme == "https" else _PinnedHTTPConnection
        conn = cls(target, timeout)
        request_headers = {"Host": target.hostname, "Connection": "close", **(headers or {})}
        conn.request(method, target.path, headers=request_headers)
        response = conn.getresponse()
        if response.status in (301, 302, 303, 307, 308):
            location = response.getheader("Location")
            response.read(min(policy.max_output, 64 * 1024))
            conn.close()
            if not location:
                raise SecurityError("redirect response has no Location header")
            if redirects == policy.max_redirects:
                raise SecurityError("redirect limit exceeded")
            current = urljoin(current, location)
            if response.status == 303:
                method = "GET"
            continue
        limit = policy.max_output if max_bytes is None else min(max_bytes, policy.max_output)
        body = response.read(limit + 1)
        result_headers = dict(response.getheaders())
        status = response.status
        conn.close()
        if len(body) > limit:
            raise SecurityError(f"response exceeds {limit} byte output limit")
        return {"url": current, "status": status, "headers": result_headers, "body": body}
    raise SecurityError("redirect limit exceeded")


def bounded_run(
    argv: Sequence[str],
    timeout: int,
    max_output: int,
    secrets=(),
    env: Mapping[str, str] | None = None,
):
    """Execute an argv (never a shell), enforcing timeout and output bounds."""
    if not isinstance(argv, list | tuple) or not argv or not all(isinstance(x, str) for x in argv):
        raise SecurityError("command must be a non-empty string argument vector")
    try:
        proc = subprocess.run(
            list(argv),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout,
            env=dict(env) if env else None,
        )
    except subprocess.TimeoutExpired as exc:
        raise SecurityError(f"command timed out after {timeout}s") from exc
    stdout = proc.stdout[:max_output].decode("utf-8", "replace")
    remaining = max(0, max_output - len(proc.stdout[:max_output]))
    stderr = proc.stderr[:remaining].decode("utf-8", "replace")
    truncated = len(proc.stdout) + len(proc.stderr) > max_output
    return {
        "returncode": proc.returncode,
        "stdout": redact(stdout, secrets),
        "stderr": redact(stderr, secrets),
        "truncated": truncated,
    }
