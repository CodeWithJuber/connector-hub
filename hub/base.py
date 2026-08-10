"""Base contract for every connector in the hub."""
import os
import re
import time
import uuid

from pydantic import SecretStr, ValidationError

from .http_client import UpstreamError, shared_http_client
from .logging import log, redact_fields
from .schemas import validate_action
from .schemas.actions import secret_field_names

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
        request_id = str(params.pop("_request_id", "") or uuid.uuid4())
        started = time.monotonic()
        try:
            params = validate_action(self, action, params)
        except ValidationError as exc:
            raise ConnectorError(f"{self.name}.{action}: invalid request: {exc}") from exc
        secrets = secret_field_names(self, action)
        log.info("connector_action_start", request_id=request_id, connector=self.name,
                 action=action, params=redact_fields(params, secrets))
        params = {k: v.get_secret_value() if isinstance(v, SecretStr) else v for k, v in params.items()}
        if self.mock:
            result = {
                "ok": True,
                "mock": True,
                "connector": self.name,
                "action": action,
                "echo": redact_fields(params, secrets),
                "note": f"set {', '.join(self.missing_env)} to go live",
            }
        else:
            result = self._live(action, **params)
        log.info("connector_action_complete", request_id=request_id, connector=self.name,
                 action=action, latency_ms=round((time.monotonic()-started)*1000, 2),
                 upstream_status=result.get("status"))
        result.setdefault("request_id", request_id)
        return result

    def _live(self, action, **params):
        raise NotImplementedError(f"{self.name} has no live implementation")

    # --- HTTP ------------------------------------------------------------
    def http_json(self, method, url, headers=None, payload=None, timeout=30):
        try:
            return shared_http_client.request_json(self.name, method, url, headers=headers,
                                                   payload=payload, cache_safe=True)
        except UpstreamError as exc:
            raise ConnectorError(str(exc)) from exc

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
