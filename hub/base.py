"""Base contract for every connector in the hub.

Zero third-party dependencies. HTTP via urllib. Secrets via env only.
"""
import json
import os
import urllib.request
import urllib.error


class ConnectorError(Exception):
    """A connector failure with a stable, caller-visible error type."""

    def __init__(self, message, error_type="upstream_failure"):
        super().__init__(message)
        self.error_type = error_type


class BaseConnector:
    """Subclass and set `name`, `required_env`, implement `actions()` and `call()`."""

    name = "base"
    required_env: list = []          # env vars needed to leave mock mode
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
