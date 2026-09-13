import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
import os
import subprocess
import tempfile
import unittest

from workspace_helpers import create_workspace, run_check, run_generate

CHECK = REPO / "kits/workspace/tools/check.py"
KIT_MANIFEST = json.loads((REPO / "kits/workspace/kit.json").read_text(encoding="utf-8"))

BROKEN_RULE = '''from wslib import common


def broken(ctx):
    raise RuntimeError("boom")


RULES = [("zz-broken", broken)]
'''


class FreshWorkspace(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.ws = create_workspace(self.tmp)

    def tearDown(self):
        self._tmp.cleanup()

    def test_fresh_workspace_passes(self):
        stamp = json.loads((self.ws / ".agents/kit.json").read_text(encoding="utf-8"))
        self.assertEqual(stamp["version"], KIT_MANIFEST["version"])
        for rel in KIT_MANIFEST["templated"]:
            self.assertNotIn("{{", (self.ws / rel).read_text(encoding="utf-8"), rel)
        code, lines, stderr = run_check(self.ws)
        self.assertEqual((code, lines, stderr), (0, [], ""))

    def test_fresh_workspace_is_generated(self):
        result = run_generate(self.ws)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("generated: 0 files changed", result.stdout)

    def test_broken_json_exits_1(self):
        (self.ws / "repos.json").write_text("{broken", encoding="utf-8")
        code, lines, stderr = run_check(self.ws)
        self.assertEqual(code, 1, (lines, stderr))
        self.assertTrue(
            any(line.startswith("repos.json:") and " json-shape " in line for line in lines), lines
        )
        self.assertNotIn("Traceback", stderr)

    def test_outside_workspace_exits_2(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        result = subprocess.run(
            [sys.executable, str(CHECK)], cwd=empty, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_internal_error_exits_2(self):
        (self.ws / "tools/wslib/rules_zz_broken.py").write_text(BROKEN_RULE, encoding="utf-8")
        code, lines, stderr = run_check(self.ws)
        self.assertEqual(code, 2, (lines, stderr))
        self.assertIn("internal error", stderr)

    def test_committed_workspace_passes(self):
        # Isolate from the developer's global git config (signing, identity).
        env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull}
        git = [
            "git",
            "-c", "commit.gpgsign=false",
            "-c", "user.name=test",
            "-c", "user.email=test@example.com",
        ]
        subprocess.run(git + ["add", "-A"], cwd=self.ws, env=env, check=True, capture_output=True)
        subprocess.run(
            git + ["commit", "-q", "-m", "init"], cwd=self.ws, env=env, check=True, capture_output=True
        )
        code, lines, stderr = run_check(self.ws)
        self.assertEqual((code, lines, stderr), (0, [], ""))


if __name__ == "__main__":
    unittest.main()
