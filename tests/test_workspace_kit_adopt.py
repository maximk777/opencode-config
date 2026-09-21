import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
import subprocess
import tempfile
import unittest

from workspace_helpers import DEFAULT_PARAMS

KIT = REPO / "kits/workspace"


def kit_meta():
    return json.loads((KIT / "kit.json").read_text(encoding="utf-8"))


def adopt_command(target, params=None):
    params = DEFAULT_PARAMS if params is None else params
    argv = [sys.executable, str(REPO / "bin/workspace-kit"), "adopt", str(target)]
    for key, value in params.items():
        argv += ["--param", f"{key}={value}"]
    return argv


def snapshot(root):
    """Map every file and directory under root to its bytes (None for directories)."""
    return {
        str(path.relative_to(root)): None if path.is_dir() else path.read_bytes()
        for path in sorted(root.rglob("*"))
    }


def conflicts(stdout):
    return [line for line in stdout.splitlines() if line.startswith("conflict: ")]


class AdoptTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.target = self.tmp / "repo"
        self.target.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def git_init(self):
        subprocess.run(["git", "init", "-q"], cwd=self.target, check=True, capture_output=True, text=True)

    def write(self, rel, text):
        path = self.target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def adopt(self, params=None):
        return subprocess.run(adopt_command(self.target, params), capture_output=True, text=True)

    def adopt_ok(self, params=None):
        result = self.adopt(params)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def assert_rejected(self, params=None):
        before = snapshot(self.target)
        result = self.adopt(params)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertTrue(result.stderr.strip())
        self.assertEqual(snapshot(self.target), before)
        return result

    def test_existing_files_kept(self):
        self.git_init()
        readme = self.write("README.md", "# Our repo\n").read_bytes()
        clone = self.write("tools/clone-repos.sh", "#!/bin/sh\necho clone\n").read_bytes()
        result = self.adopt_ok()
        self.assertEqual((self.target / "README.md").read_bytes(), readme)
        self.assertEqual((self.target / "tools/clone-repos.sh").read_bytes(), clone)
        self.assertIn("conflict: README.md", conflicts(result.stdout))
        self.assertTrue((self.target / "tools/check.py").is_file())
        stamp = json.loads((self.target / ".agents/kit.json").read_text(encoding="utf-8"))
        self.assertEqual(stamp, {"name": "workspace", "version": kit_meta()["version"], "params": DEFAULT_PARAMS})

    def test_stamp_present(self):
        self.git_init()
        self.write(".agents/kit.json", "{}\n")
        self.assert_rejected()

    def test_not_a_repository(self):
        self.write("README.md", "# Not a repo\n")
        self.assert_rejected()

    def test_parameters_substituted_in_copied_templated_file(self):
        self.git_init()
        self.adopt_ok()
        trackers = json.loads((self.target / "tracker/trackers.json").read_text(encoding="utf-8"))
        main = next(t for t in trackers["trackers"] if t["key"] == "main")
        self.assertEqual(main["id_pattern"], r"TASK-\d+")
        self.assertEqual(main["url"], DEFAULT_PARAMS["tracker_url"])
        for rel in kit_meta()["templated"]:
            self.assertNotIn("{{", (self.target / rel).read_text(encoding="utf-8"), rel)

    def test_existing_templated_file_untouched(self):
        self.git_init()
        agents = self.write("AGENTS.md", "Own rules for {{workspace_name}}\n").read_bytes()
        result = self.adopt_ok()
        self.assertEqual((self.target / "AGENTS.md").read_bytes(), agents)
        self.assertIn("conflict: AGENTS.md", conflicts(result.stdout))

    def test_identical_existing_file_not_listed(self):
        self.git_init()
        self.write(".gitignore", (KIT / ".gitignore").read_text(encoding="utf-8"))
        result = self.adopt_ok()
        self.assertNotIn("conflict: .gitignore", conflicts(result.stdout))

    def test_kit_meta_not_copied(self):
        self.git_init()
        result = self.adopt_ok()
        self.assertFalse((self.target / "kit.json").exists())
        self.assertNotIn("conflict: kit.json", conflicts(result.stdout))

    def test_invalid_id_pattern(self):
        self.git_init()
        self.write("README.md", "# Our repo\n")
        result = self.assert_rejected(dict(DEFAULT_PARAMS, id_pattern="(DEMO"))
        self.assertIn("id_pattern", result.stderr)

    def test_missing_parameter(self):
        self.git_init()
        params = dict(DEFAULT_PARAMS)
        del params["title"]
        result = self.assert_rejected(params)
        self.assertIn("title", result.stderr)

    def test_language_stored(self):
        self.git_init()
        self.adopt_ok(dict(DEFAULT_PARAMS, language="ru"))
        stamp = json.loads((self.target / ".agents/kit.json").read_text(encoding="utf-8"))
        self.assertEqual(stamp["params"], dict(DEFAULT_PARAMS, language="ru"))

    def test_invalid_language(self):
        self.git_init()
        self.write("README.md", "# Our repo\n")
        result = self.assert_rejected(dict(DEFAULT_PARAMS, language="RU"))
        self.assertIn("language", result.stderr)

    def test_conflicts_sorted(self):
        self.git_init()
        self.write("README.md", "# Our repo\n")
        self.write("tools/check.py", "print('own check')\n")
        self.write("AGENTS.md", "Own rules\n")
        self.write(".gitignore", "node_modules/\n")
        result = self.adopt_ok()
        self.assertEqual(
            conflicts(result.stdout),
            ["conflict: .gitignore", "conflict: AGENTS.md", "conflict: README.md", "conflict: tools/check.py"],
        )


if __name__ == "__main__":
    unittest.main()
