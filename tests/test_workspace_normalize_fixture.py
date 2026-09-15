import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import shutil
import subprocess
import tempfile
import unittest

from workspace_helpers import DEFAULT_PARAMS, run_check, run_generate

FIXTURE = REPO / "tests/fixtures/workspace-normalize"
LEGACY = FIXTURE / "legacy"
OVERLAY = FIXTURE / "overlay"
REMOVE = "REMOVE.txt"
PARAMS = dict(DEFAULT_PARAMS, forge="gitlab", language="ru")
GIT = ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false"]
STREAM_JSON = "domains/demo/streams/main/stream.json"
# Goal and map are approved by status lines in the legacy epic and sitemap; the card screen has no story yet.
EXPECTED_REMAINING = [
    "stream:demo/main decomposition two_way_coverage: %s:1 scope key screen:demo/card is in no story's scope"
    % STREAM_JSON,
    "stream:demo/main decomposition approval: %s:1 no approval mark for stage decomposition with by and a "
    "YYYY-MM-DD date" % STREAM_JSON,
]


class NormalizeFixtureTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name).resolve() / "ws"
        shutil.copytree(str(LEGACY), str(self.ws))
        for args in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "legacy"]):
            subprocess.run(GIT + args, cwd=self.ws, check=True, capture_output=True, text=True)

    def tearDown(self):
        self._tmp.cleanup()

    def adopt(self):
        argv = [sys.executable, str(REPO / "bin/workspace-kit"), "adopt", str(self.ws)]
        for key, value in PARAMS.items():
            argv += ["--param", "%s=%s" % (key, value)]
        result = subprocess.run(argv, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def apply_recipes(self):
        shutil.copytree(str(OVERLAY), str(self.ws), dirs_exist_ok=True, ignore=shutil.ignore_patterns(REMOVE))
        for rel in (OVERLAY / REMOVE).read_text(encoding="utf-8").split():
            path = self.ws / rel
            self.assertTrue(path.is_file(), rel)
            path.unlink()
            parent = path.parent
            while parent != self.ws and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent

    def test_adopt_keeps_existing_files(self):
        result = self.adopt()
        for rel in ("README.md", "tools/clone-repos.sh"):
            self.assertEqual((self.ws / rel).read_bytes(), (LEGACY / rel).read_bytes(), rel)
        self.assertIn("conflict: README.md", result.stdout.splitlines())

    def test_normalized_workspace_passes_check(self):
        self.adopt()
        self.apply_recipes()
        self.assertFalse((self.ws / "legacy").exists())
        generated = run_generate(self.ws)
        self.assertEqual(generated.returncode, 0, generated.stderr)
        code, lines, stderr = run_check(self.ws)
        self.assertEqual((code, lines), (0, []), stderr)
        remaining = subprocess.run(
            [sys.executable, "tools/check.py", "--remaining"], cwd=self.ws, capture_output=True, text=True
        )
        self.assertEqual(remaining.returncode, 0, remaining.stderr)
        stream_lines = [line for line in remaining.stdout.splitlines() if line.startswith("stream:demo/main ")]
        self.assertEqual(stream_lines, EXPECTED_REMAINING)

    def test_generate_leaves_overlay_files_unchanged(self):
        self.adopt()
        self.apply_recipes()
        for args in (["add", "-A"], ["commit", "-qm", "overlay"]):
            subprocess.run(GIT + args, cwd=self.ws, check=True, capture_output=True, text=True)
        generated = run_generate(self.ws)
        self.assertEqual(generated.returncode, 0, generated.stderr)
        status = subprocess.run(GIT + ["status", "--porcelain"], cwd=self.ws, check=True, capture_output=True, text=True)
        modified = [line for line in status.stdout.splitlines() if not line.startswith("??")]
        self.assertEqual(modified, [])
        for path in sorted(OVERLAY.rglob("*")):
            rel = path.relative_to(OVERLAY).as_posix()
            if path.is_file() and rel != REMOVE:
                self.assertEqual((self.ws / rel).read_bytes(), path.read_bytes(), rel)


if __name__ == "__main__":
    unittest.main()
