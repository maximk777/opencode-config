import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
import shutil
import subprocess
import tempfile
import unittest

from workspace_helpers import DEFAULT_PARAMS, create_workspace, kit_command

KIT = REPO / "kits/workspace"


def kit_meta():
    return json.loads((KIT / "kit.json").read_text(encoding="utf-8"))


def run(argv):
    return subprocess.run(argv, capture_output=True, text=True)


class CreateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def copy_kit(self):
        kit = self.tmp / "kit"
        shutil.copytree(KIT, kit, ignore=shutil.ignore_patterns("__pycache__"))
        return kit

    def assert_fresh_workspace(self, ws):
        meta = kit_meta()
        stamp = json.loads((ws / ".agents/kit.json").read_text(encoding="utf-8"))
        self.assertEqual(stamp, {"name": "workspace", "version": meta["version"], "params": DEFAULT_PARAMS})
        tracker = json.loads((ws / "tracker/tracker.json").read_text(encoding="utf-8"))
        self.assertEqual(tracker["id_pattern"], r"TASK-\d+")
        for rel in meta["templated"]:
            self.assertNotIn("{{", (ws / rel).read_text(encoding="utf-8"), rel)
        self.assertTrue((ws / "CLAUDE.md").is_file())
        self.assertTrue((ws / ".agents/index.json").is_file())
        self.assertFalse((ws / "kit.json").exists())

    def test_create_into_missing_target(self):
        ws = create_workspace(self.tmp)
        self.assert_fresh_workspace(ws)

    def test_create_into_empty_directory(self):
        (self.tmp / "ws").mkdir()
        ws = create_workspace(self.tmp)
        self.assert_fresh_workspace(ws)

    def test_untemplated_file_keeps_braces(self):
        kit = self.copy_kit()
        (kit / "notes.md").write_text("Name: {{workspace_name}}\n", encoding="utf-8")
        ws = create_workspace(self.tmp, kit=kit)
        self.assertEqual((ws / "notes.md").read_text(encoding="utf-8"), "Name: {{workspace_name}}\n")

    def test_non_empty_target(self):
        target = self.tmp / "ws"
        target.mkdir()
        (target / "keep.txt").write_text("keep\n", encoding="utf-8")
        result = run(kit_command(target))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(sorted(p.name for p in target.iterdir()), ["keep.txt"])

    def assert_param_rejected(self, params, name):
        target = self.tmp / "ws"
        result = run(kit_command(target, params))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(name, result.stderr)
        self.assertFalse(target.exists())

    def test_missing_parameter(self):
        params = dict(DEFAULT_PARAMS)
        del params["title"]
        self.assert_param_rejected(params, "title")

    def test_unknown_parameter(self):
        self.assert_param_rejected(dict(DEFAULT_PARAMS, colour="red"), "colour")

    def test_invalid_forge(self):
        self.assert_param_rejected(dict(DEFAULT_PARAMS, forge="bitbucket"), "forge")

    def test_invalid_id_pattern(self):
        self.assert_param_rejected(dict(DEFAULT_PARAMS, id_pattern="(DEMO"), "id_pattern")

    def test_tracker_url_without_id(self):
        self.assert_param_rejected(dict(DEFAULT_PARAMS, tracker_url="https://tracker.example/i/"), "tracker_url")

    def test_generator_failure(self):
        kit = self.copy_kit()
        (kit / "tools/generate.py").write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
        parent = self.tmp / "out"
        parent.mkdir()
        target = parent / "ws"
        result = run(kit_command(target, kit=kit))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(target.exists())
        self.assertEqual([p.name for p in parent.iterdir() if p.name.startswith(".workspace-kit-")], [])


if __name__ == "__main__":
    unittest.main()
