"""Base contract for every connector in the hub.

Zero third-party dependencies. HTTP via urllib. Secrets via env only.
"""

import json
import os
import random
import re
import time
import urllib.error
import urllib.request

_SECRET_PAT = re.compile(r"(KEY|TOKEN|SECRET|PASS|PWD)", re.I)


class ConnectorError(Exception):
    """Raised on real-mode failures (auth, HTTP, bad action)."""

    def __init__(self, message, *, code="connector_error", retryable=False, status=None):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.status = status

    def as_dict(self):
        """Return a stable, secret-safe error envelope for callers and logs."""
        return {
            "ok": False,
            "error": {
                "code": self.code,
                "message": str(self),
                "retryable": self.retryable,
                "status": self.status,
            },
        }


class BaseConnector:
    """Subclass and set `name`, `required_env`, implement `actions()` and `call()`."""

    name = "base"
    required_env: list = []  # env vars needed to leave mock mode
    description = ""

    def __init__(self, config=None):
        self.config = config or {}
        missing = [v for v in self.required_env if not os.environ.get(v)]
        self.mock = bool(missing)
        self.missing_env = missing

    # --- helpers ---------------------------------------------------------
    def env(self, var, default=None):
        return os.environ.get(var, default)

    def status(self):
        return {
            "name": self.name,
            "mode": "mock" if self.mock else "live",
            "missing_env": self.missing_env,
            "actions": self.actions(),
            "description": self.description,
        }

    def actions(self):
        raise NotImplementedError

    def require(self, action):
        if action not in self.actions():
            raise ConnectorError(
                f"{self.name}: unknown action '{action}'. Available: {', '.join(self.actions())}"
            )

    def call(self, action, **params):
        self.require(action)
        if self.mock:
            return {
                "ok": True,
                "mock": True,
                "connector": self.name,
                "action": action,
                "echo": self._redact(params),
                "note": f"set {', '.join(self.missing_env)} to go live",
            }
        return self._live(action, **params)

    def _live(self, action, **params):
        raise NotImplementedError(f"{self.name} has no live implementation")

    # --- HTTP ------------------------------------------------------------
    def http_json(
        self, method, url, headers=None, payload=None, timeout=20, max_attempts=3, base_delay=0.25
    ):
        """Send JSON with bounded exponential backoff and rate-limit awareness.

        Only idempotent requests and explicit rate-limit responses are retried.
        Jitter prevents synchronized clients from retrying simultaneously.
        """
        body = json.dumps(payload).encode() if payload is not None else None
        method = method.upper()
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        for attempt in range(max_attempts):
            req = urllib.request.Request(url, data=body, method=method)
            req.add_header("Accept", "application/json")
            if body is not None:
                req.add_header("Content-Type", "application/json")
            for k, v in (headers or {}).items():
                req.add_header(k, v)
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    raw = resp.read().decode() or "{}"
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        data = {"raw": raw}
                    return {"ok": True, "status": resp.status, "data": data}
            except urllib.error.HTTPError as exc:
                retryable = exc.code == 429 or exc.code >= 500
                can_retry = retryable and (method in {"GET", "HEAD"} or exc.code == 429)
                if can_retry and attempt + 1 < max_attempts:
                    retry_after = exc.headers.get("Retry-After") if exc.headers else None
                    try:
                        delay = min(float(retry_after), 30.0) if retry_after else 0.0
                    except ValueError:
                        delay = 0.0
                    time.sleep(
                        max(delay, base_delay * (2**attempt) + random.uniform(0, base_delay))
                    )
                    continue
                detail = exc.read().decode(errors="replace")[:500]
                raise ConnectorError(
                    f"{self.name} HTTP {exc.code} {url}: {detail}",
                    code="rate_limited" if exc.code == 429 else "http_error",
                    retryable=retryable,
                    status=exc.code,
                ) from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                if method in {"GET", "HEAD"} and attempt + 1 < max_attempts:
                    time.sleep(base_delay * (2**attempt) + random.uniform(0, base_delay))
                    continue
                reason = getattr(exc, "reason", exc)
                raise ConnectorError(
                    f"{self.name} connection failed {url}: {reason}",
                    code="connection_error",
                    retryable=True,
                ) from exc

    # --- misc ------------------------------------------------------------
    def _redact(self, obj):
        if isinstance(obj, dict):
            return {
                k: ("***" if _SECRET_PAT.search(str(k)) else self._redact(v))
                for k, v in obj.items()
            }
        if isinstance(obj, list | tuple):
            return [self._redact(x) for x in obj]
        return obj


# --- registry ------------------------------------------------------------
_REGISTRY = {}


def register(cls):
    _REGISTRY[cls.name] = cls
    return cls


def get_connector(name, config=None):
    if name not in _REGISTRY:
        raise ConnectorError(f"unknown channel '{name}'. Known: {', '.join(sorted(_REGISTRY))}")
    return _REGISTRY[name](config=config)


def list_connectors():
    return {name: cls.description for name, cls in sorted(_REGISTRY.items())}
