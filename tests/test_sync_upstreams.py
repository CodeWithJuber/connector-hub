from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = (
    Path(__file__).parents[1] / ".agents/plugins/plugins/connector-hub/scripts/sync_upstreams.py"
)
SPEC = importlib.util.spec_from_file_location("sync_upstreams", SCRIPT)
assert SPEC and SPEC.loader
sync_upstreams = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync_upstreams)


class SourceValidationTests(unittest.TestCase):
    def test_approved_sources_are_accepted(self) -> None:
        for name, url in sync_upstreams.SOURCES.items():
            sync_upstreams.validate_source(name, url)

    def test_unapproved_host_is_rejected(self) -> None:
        with self.assertRaisesRegex(sync_upstreams.SyncError, "Unapproved source"):
            sync_upstreams.validate_source("forgekit", "https://example.com/forgekit.git")

    def test_embedded_credentials_are_rejected(self) -> None:
        malicious = "https://user:secret@github.com/CodeWithJuber/forgekit.git"
        with mock.patch.dict(sync_upstreams.SOURCES, {"forgekit": malicious}, clear=False):
            with self.assertRaisesRegex(sync_upstreams.SyncError, "must not embed credentials"):
                sync_upstreams.validate_source("forgekit", malicious)

    def test_repository_root_requires_expected_layout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "a/b/c/d/script.py"
            script.parent.mkdir(parents=True)
            with self.assertRaises(sync_upstreams.SyncError):
                sync_upstreams.repository_root(script)


if __name__ == "__main__":
    unittest.main()
