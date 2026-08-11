from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = (
    Path(__file__).parents[1] / ".agents/plugins/plugins/connector-hub/scripts/sync_upstreams.py"
)


@unittest.skipUnless(
    os.environ.get("RUN_INTEGRATION") == "1", "set RUN_INTEGRATION=1 to access real GitHub data"
)
class RealSourceIntegrationTest(unittest.TestCase):
    def test_fetches_both_real_repositories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "hub").mkdir()
            (root / ".git").mkdir()
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--root", str(root)],
                check=False,
                capture_output=True,
                text=True,
                timeout=420,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((root / ".vendor/forgekit/.git").is_dir())
            self.assertTrue((root / ".vendor/hikmah-stack/.git").is_dir())
            self.assertTrue((root / "vendor-manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()
