import json
import os
import random
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from hub.plugins import PluginLoader, PluginValidationError, validate_manifest

BASE = {
    "api_version": "connector-hub.plugin/v1",
    "plugin_id": "example.safe",
    "version": "1.2.3",
    "capabilities": ["project.files.read"],
    "required_secrets": [],
    "allowed_network_hosts": [],
    "supports_destructive_actions": False,
}


class ManifestTests(unittest.TestCase):
    def test_valid_manifest(self):
        manifest = validate_manifest(BASE, {"project.files.read"})
        self.assertEqual(manifest.plugin_id, "example.safe")

    def test_unknown_field_is_rejected(self):
        data = {**BASE, "surprise": True}
        with self.assertRaisesRegex(PluginValidationError, "unknown manifest field"):
            validate_manifest(data, {"project.files.read"})

    def test_unsupported_api_is_rejected(self):
        data = {**BASE, "api_version": "connector-hub.plugin/v2"}
        with self.assertRaisesRegex(PluginValidationError, "unsupported plugin API"):
            validate_manifest(data, {"project.files.read"})

    def test_policy_rejects_capability(self):
        with self.assertRaisesRegex(PluginValidationError, "disabled by policy"):
            validate_manifest(BASE, set())

    def test_destructive_flag_requires_capability(self):
        data = {**BASE, "supports_destructive_actions": True}
        with self.assertRaisesRegex(PluginValidationError, "actions.destructive"):
            validate_manifest(data, {"project.files.read"})


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.plugin = self.root / "safe"
        self.plugin.mkdir()
        (self.plugin / "plugin-manifest.json").write_text(json.dumps(BASE), encoding="utf-8")
        self.loader = PluginLoader(self.root, {"project.files.read"})

    def tearDown(self):
        self.temp.cleanup()

    def test_register_and_duplicate_rejection(self):
        self.loader.register("safe")
        with self.assertRaisesRegex(PluginValidationError, "duplicate plugin ID"):
            self.loader.register("safe")

    def test_parent_traversal_is_rejected(self):
        with self.assertRaisesRegex(PluginValidationError, "must not contain"):
            self.loader.register("../outside")

    def test_symlink_escape_is_rejected(self):
        outside = self.root.parent / "outside-plugin-test"
        outside.mkdir(exist_ok=True)
        try:
            (self.root / "escape").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(PluginValidationError, "escapes"):
                self.loader.register("escape")
        finally:
            (self.root / "escape").unlink(missing_ok=True)
            outside.rmdir()


@unittest.skipUnless(
    os.environ.get("RUN_INTEGRATION") == "1", "set RUN_INTEGRATION=1 for GitHub verification"
)
class UpstreamIntegrationTests(unittest.TestCase):
    def test_hikmah_pinned_commit_exists(self):
        url = "https://api.github.com/repos/hikmahlabs/plugins/commits/f028fb87ecb64de0e284b3b233150da41d938ebf"
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "connector-hub-tests"},
        )
        payload = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=10) as response:
                    payload = json.load(response)
                break
            except (urllib.error.URLError, TimeoutError):
                if attempt == 2:
                    raise
                time.sleep((0.25 * (2**attempt)) + random.uniform(0, 0.1))
        self.assertIsInstance(payload, dict)
        self.assertEqual(payload.get("sha"), "f028fb87ecb64de0e284b3b233150da41d938ebf")


if __name__ == "__main__":
    unittest.main()
