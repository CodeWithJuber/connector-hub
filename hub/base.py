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
"""Base contract for every connector in the hub."""
import os
import urllib.request
import urllib.error
import re
import time
import uuid

from pydantic import SecretStr, ValidationError

from .http_client import UpstreamError, shared_http_client
from .logging import log, redact_fields
from .schemas import validate_action
from .schemas.actions import secret_field_names


class ConnectorError(Exception):
    """A connector failure with a stable, caller-visible error type."""

    def __init__(self, message, error_type="upstream_failure"):
        super().__init__(message)
        self.error_type = error_type

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
    read_only_actions = frozenset()
    mutating_actions = frozenset()
    destructive_actions = frozenset()
    dry_run_actions = frozenset()

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
            "action_policies": self.action_policies(),
            "description": self.description,
        }

    def actions(self):
        raise NotImplementedError

    def require(self, action):
        if action not in self.actions():
            raise ConnectorError(
                f"{self.name}: unknown action '{action}'. Available: {', '.join(self.actions())}"
                f"{self.name}: unknown action '{action}'. "
                f"Available: {', '.join(self.actions())}",
                "invalid_request",
            )

    def action_policies(self):
        """Return explicit safety metadata, failing closed if it is incomplete."""
        actions = set(self.actions())
        classified = (set(self.read_only_actions) | set(self.mutating_actions) |
                      set(self.destructive_actions))
        if classified != actions:
            missing = sorted(actions - classified)
            extra = sorted(classified - actions)
            raise ConnectorError(
                f"{self.name}: invalid action classification; missing={missing}, extra={extra}",
                "configuration_error",
            )
        overlaps = ((set(self.read_only_actions) & set(self.mutating_actions)) |
                    (set(self.read_only_actions) & set(self.destructive_actions)) |
                    (set(self.mutating_actions) & set(self.destructive_actions)))
        if overlaps or not set(self.dry_run_actions) <= actions:
            raise ConnectorError(
                f"{self.name}: overlapping or invalid action policies: {sorted(overlaps)}",
                "configuration_error",
            )
        return {
            action: {
                "classification": (
                    "read_only" if action in self.read_only_actions else
                    "destructive" if action in self.destructive_actions else "mutating"
                ),
                "dry_run_capable": action in self.dry_run_actions,
                "confirmation_required": action in self.destructive_actions,
            }
            for action in self.actions()
        }

    def call(self, action, **params):
        try:
            self.require(action)
            policy = self.action_policies()[action]
        except ConnectorError as exc:
            return self._error(exc.error_type, str(exc), action)

        dry_run = params.pop("dry_run", False)
        if not isinstance(dry_run, bool):
            return self._error("invalid_request", "dry_run must be a boolean", action)
        if self.mock:
            return self._error(
                "configuration_required",
                f"{self.name} requires environment configuration",
                action,
                {"missing_env": list(self.missing_env)},
            )
        if dry_run:
            if not policy["dry_run_capable"]:
                return self._error(
                    "dry_run_not_supported",
                    f"{self.name}.{action} does not support dry_run",
                    action,
                )
            return {
                "ok": False,
                "executed": False,
                "state": "dry_run",
                "connector": self.name,
                "action": action,
                "classification": policy["classification"],
            }
        if policy["confirmation_required"]:
            supplied = params.pop("confirmation_token", None)
            approved = params.pop("policy_approved", False)
            expected = f"CONFIRM:{self.name}:{action}"
            if supplied != expected and approved is not True:
                return self._error(
                    "confirmation_required",
                    f"destructive action requires confirmation_token '{expected}' "
                    "or policy_approved=true",
                    action,
                )
        try:
            result = self._live(action, **params)
        except ConnectorError as exc:
            return self._error(exc.error_type, str(exc), action)
        except Exception as exc:
            return self._error("upstream_failure", str(exc), action)
        if not isinstance(result, dict):
            return self._error("upstream_failure", "connector returned a non-object response", action)
        result.setdefault("executed", True)
        result.setdefault("state", "succeeded" if result.get("ok") is True else "upstream_failure")
        return result

    def _error(self, error_type, message, action, details=None):
        error = {"type": error_type, "message": message}
        if details:
            error["details"] = details
        return {
            "ok": False,
            "executed": False,
            "state": error_type,
            "connector": self.name,
            "action": action,
            "error": error,
        }
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

    def http_json(self, method, url, headers=None, payload=None, timeout=30):
        try:
            return shared_http_client.request_json(self.name, method, url, headers=headers,
                                                   payload=payload, cache_safe=True)
        except UpstreamError as exc:
            raise ConnectorError(str(exc)) from exc

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
