"""Base contract for every connector in the hub.

Zero third-party dependencies. HTTP via urllib. Secrets via env only.
"""
import json
import os
import re
import urllib.request
import urllib.error

_SECRET_PAT = re.compile(r"(KEY|TOKEN|SECRET|PASS|PWD)", re.I)


class ConnectorError(Exception):
    """Raised on real-mode failures (auth, HTTP, bad action)."""


class BaseConnector:
    """Subclass and set `name`, `required_env`, implement `actions()` and `call()`."""

    name = "base"
    required_env: list = []          # env vars needed to leave mock mode
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
                f"{self.name}: unknown action '{action}'. "
                f"Available: {', '.join(self.actions())}"
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
    def http_json(self, method, url, headers=None, payload=None, timeout=30):
        body = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(url, data=body, method=method.upper())
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
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:500]
            raise ConnectorError(f"{self.name} HTTP {e.code} {url}: {detail}")
        except urllib.error.URLError as e:
            raise ConnectorError(f"{self.name} connection failed {url}: {e.reason}")

    # --- misc ------------------------------------------------------------
    def _redact(self, obj):
        if isinstance(obj, dict):
            return {
                k: ("***" if _SECRET_PAT.search(str(k)) else self._redact(v))
                for k, v in obj.items()
            }
        if isinstance(obj, (list, tuple)):
            return [self._redact(x) for x in obj]
        return obj


# --- registry ------------------------------------------------------------
_REGISTRY = {}


def register(cls):
    _REGISTRY[cls.name] = cls
    return cls


def get_connector(name, config=None):
    if name not in _REGISTRY:
        raise ConnectorError(
            f"unknown channel '{name}'. Known: {', '.join(sorted(_REGISTRY))}"
        )
    return _REGISTRY[name](config=config)


def list_connectors():
    return {name: cls.description for name, cls in sorted(_REGISTRY.items())}
