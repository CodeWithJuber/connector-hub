"""Static, policy-gated plugin manifest discovery.

The loader registers metadata only. It deliberately never imports, downloads, or
executes plugin content; an application must provide reviewed adapters separately.
"""

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_API_VERSIONS = frozenset({"connector-hub.plugin/v1"})
_FIELDS = frozenset(
    {
        "api_version",
        "plugin_id",
        "version",
        "capabilities",
        "required_secrets",
        "allowed_network_hosts",
        "supports_destructive_actions",
    }
)
_ID = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_VERSION = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
_CAPABILITY = re.compile(r"^[a-z][a-z0-9]*(?:[._:-][a-z0-9]+)*$")
_SECRET = re.compile(r"^[A-Z][A-Z0-9_]*$")
_HOST = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(?:\.(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?))*$"
)


class PluginValidationError(ValueError):
    """A plugin cannot be safely registered; the message explains why."""


@dataclass(frozen=True)
class PluginManifest:
    api_version: str
    plugin_id: str
    version: str
    capabilities: tuple[str, ...]
    required_secrets: tuple[str, ...]
    allowed_network_hosts: tuple[str, ...]
    supports_destructive_actions: bool


@dataclass(frozen=True)
class PluginRegistration:
    manifest: PluginManifest
    directory: Path


def _string_array(data: Mapping[str, object], field: str, pattern: re.Pattern) -> tuple[str, ...]:
    value = data.get(field)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise PluginValidationError(f"{field} must be an array of strings")
    if len(value) != len(set(value)):
        raise PluginValidationError(f"{field} must not contain duplicates")
    invalid = [item for item in value if not pattern.fullmatch(item)]
    if invalid:
        raise PluginValidationError(f"{field} contains invalid value(s): {', '.join(invalid)}")
    return tuple(value)


def validate_manifest(data: object, enabled_capabilities: Iterable[str]) -> PluginManifest:
    """Validate untrusted decoded JSON against the closed v1 manifest contract."""
    if not isinstance(data, dict):
        raise PluginValidationError("manifest root must be a JSON object")
    unknown = set(data) - _FIELDS
    missing = _FIELDS - set(data)
    if unknown:
        raise PluginValidationError(f"unknown manifest field(s): {', '.join(sorted(unknown))}")
    if missing:
        raise PluginValidationError(f"missing manifest field(s): {', '.join(sorted(missing))}")
    api_version = data["api_version"]
    if api_version not in SUPPORTED_API_VERSIONS:
        raise PluginValidationError(f"unsupported plugin API version: {api_version!r}")
    plugin_id = data["plugin_id"]
    if not isinstance(plugin_id, str) or len(plugin_id) > 128 or not _ID.fullmatch(plugin_id):
        raise PluginValidationError("plugin_id is not a valid lowercase plugin identifier")
    version = data["version"]
    if not isinstance(version, str) or not _VERSION.fullmatch(version):
        raise PluginValidationError("version must be a semantic version")
    capabilities = _string_array(data, "capabilities", _CAPABILITY)
    disallowed = set(capabilities) - set(enabled_capabilities)
    if disallowed:
        raise PluginValidationError(
            f"capabilities disabled by policy: {', '.join(sorted(disallowed))}"
        )
    secrets = _string_array(data, "required_secrets", _SECRET)
    hosts = _string_array(data, "allowed_network_hosts", _HOST)
    destructive = data["supports_destructive_actions"]
    if type(destructive) is not bool:
        raise PluginValidationError("supports_destructive_actions must be a boolean")
    if destructive and "actions.destructive" not in capabilities:
        raise PluginValidationError("destructive plugins must request actions.destructive")
    return PluginManifest(
        api_version, plugin_id, version, capabilities, secrets, hosts, destructive
    )


class PluginLoader:
    """Register local plugin directories contained beneath a fixed trusted root."""

    def __init__(self, root: Path, enabled_capabilities: Iterable[str]):
        self.root = root.resolve(strict=True)
        self.enabled_capabilities: frozenset[str] = frozenset(enabled_capabilities)
        self._registrations = {}

    @property
    def registrations(self):
        return dict(self._registrations)

    def register(self, relative_directory: str) -> PluginRegistration:
        requested = Path(relative_directory)
        if requested.is_absolute() or ".." in requested.parts:
            raise PluginValidationError("plugin path must be relative and must not contain '..'")
        directory = (self.root / requested).resolve(strict=True)
        try:
            directory.relative_to(self.root)
        except ValueError as exc:
            raise PluginValidationError("plugin path escapes the configured root") from exc
        if not directory.is_dir():
            raise PluginValidationError(f"plugin path is not a directory: {relative_directory}")
        manifest_path = directory / "plugin-manifest.json"
        if manifest_path.is_symlink() or not manifest_path.is_file():
            raise PluginValidationError(
                f"plugin manifest is missing or is a symlink: {manifest_path}"
            )
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise PluginValidationError(
                f"cannot read plugin manifest {manifest_path}: {exc}"
            ) from exc
        manifest = validate_manifest(data, self.enabled_capabilities)
        if manifest.plugin_id in self._registrations:
            raise PluginValidationError(f"duplicate plugin ID: {manifest.plugin_id}")
        registration = PluginRegistration(manifest, directory)
        self._registrations[manifest.plugin_id] = registration
        return registration
