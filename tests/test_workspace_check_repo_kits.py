import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO / "kits/workspace/tools"))

import json
import shutil
import tempfile
import unittest
from unittest import mock

from workspace_helpers import create_workspace, run_check
from wslib import common, rules_repo_kits

KITS = ".agents/repo-kits"


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def mfe_params():
    return {
        "MFE": {"description": "Micro-frontend repository name", "pattern": "mfe-[a-z0-9-]+"},
        "BFF": {"description": "Backend-for-frontend repository name", "pattern": "bff-[a-z0-9-]+"},
    }


def repo_entry(name, kit=None):
    entry = {"name": name, "remote": "git@x:%s.git" % name, "forge": "gitlab", "default_branch": "main",
             "roles": ["frontend"], "summary": "Service"}
    if kit is not None:
        entry["kit"] = kit
    return entry


class CheckRepoKitsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.ws = create_workspace(self.tmp)

    def tearDown(self):
        self._tmp.cleanup()

    def write_kit(self, kind, params=None, files=None, **fields):
        data = {"name": kind, "version": "1.0.0", "target": ".agents",
                "params": mfe_params() if params is None else params}
        data.update(fields)
        write_json(self.ws / KITS / kind / "kit.json", data)
        for rel, content in (files or {"AGENTS.md": "# __MFE__\n"}).items():
            path = self.ws / KITS / kind / "files" / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def write_repos(self, *entries):
        write_json(self.ws / "repos.json", {"repositories": list(entries)})

    def findings(self, rule="repo-kit"):
        _, lines, stderr = run_check(self.ws)
        self.assertNotIn("Traceback", stderr)
        self.assertNotIn("internal error", stderr)
        return [line for line in lines if len(line.split(" ")) > 1 and line.split(" ")[1] == rule]

    def test_valid_kit_and_entry_give_no_finding(self):
        self.write_kit("mfe")
        self.write_repos(repo_entry("mfe-abs-operations", {
            "kind": "mfe", "params": {"MFE": "mfe-abs-operations", "BFF": "bff-abs-operations"}}))
        self.assertEqual(self.findings(), [])

    def test_entry_with_kit_gives_no_json_shape_finding(self):
        self.write_kit("mfe")
        self.write_repos(repo_entry("mfe-abs-operations", {
            "kind": "mfe", "params": {"MFE": "mfe-abs-operations", "BFF": "bff-abs-operations"}}))
        self.assertEqual([line for line in self.findings("json-shape") if line.startswith("repos.json:")], [])

    def test_invalid_pattern(self):
        params = mfe_params()
        params["PREFIX"] = {"description": "Route prefix", "pattern": "["}
        self.write_kit("mfe", params=params)
        lines = self.findings()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(KITS + "/mfe/kit.json:"), lines)
        self.assertIn("mfe", lines[0].split(" ", 2)[2])
        self.assertIn("PREFIX", lines[0])

    def test_empty_repo_kits_folder_gives_no_finding(self):
        shutil.rmtree(self.ws / KITS, ignore_errors=True)
        (self.ws / KITS).mkdir(parents=True)
        self.write_repos(repo_entry("api"))
        self.assertEqual(self.findings(), [])

    def test_no_repo_kits_folder_gives_no_finding(self):
        shutil.rmtree(self.ws / KITS, ignore_errors=True)
        self.write_repos(repo_entry("api"))
        self.assertEqual(self.findings(), [])

    def test_undeclared_placeholder(self):
        self.write_kit("mfe", files={"rules/routes.md": "# Routes\n\nPrefix: __PREFIX__\n"})
        lines = self.findings()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(KITS + "/mfe/files/rules/routes.md:3 repo-kit "), lines)
        self.assertIn("rules/routes.md", lines[0].split(" ", 2)[2])
        self.assertIn("PREFIX", lines[0])

    def test_missing_kit_json(self):
        path = self.ws / KITS / "mfe" / "files" / "AGENTS.md"
        path.parent.mkdir(parents=True)
        path.write_text("# __MFE__\n", encoding="utf-8")
        lines = self.findings()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(KITS + "/mfe/kit.json:0 repo-kit "), lines)

    def test_kit_json_breaking_format(self):
        self.write_kit("mfe", name="other", version="1.0", target="repo")
        lines = self.findings()
        self.assertEqual(len(lines), 3, lines)
        self.assertTrue(all(line.startswith(KITS + "/mfe/kit.json:0 repo-kit ") for line in lines), lines)
        text = "\n".join(lines)
        for phrase in ("name must be mfe", "version must be MAJOR.MINOR.PATCH", "target must be .agents"):
            self.assertIn(phrase, text)

    def test_params_not_object_skips_placeholder_findings(self):
        self.write_kit("mfe", params="MFE", files={"AGENTS.md": "# __MFE__ __BFF__\n"})
        lines = self.findings()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(KITS + "/mfe/kit.json:0 repo-kit "), lines)
        self.assertIn("params must be an object", lines[0])

    def test_broken_symlink_in_files(self):
        self.write_kit("mfe", files={"AGENTS.md": "# __MFE__\n", "rules/extra.md": "__PREFIX__\n"})
        (self.ws / KITS / "mfe" / "files" / "link.md").symlink_to(self.tmp / "missing.md")
        lines = self.findings()
        self.assertEqual(len(lines), 2, lines)
        self.assertTrue(lines[0].startswith(KITS + "/mfe/files/link.md:0 repo-kit "), lines)
        self.assertIn("files/link.md cannot be read: No such file or directory", lines[0].split(" ", 2)[2])
        self.assertNotIn(str(self.tmp), lines[0])
        # Other files are still scanned after the unreadable one.
        self.assertTrue(lines[1].startswith(KITS + "/mfe/files/rules/extra.md:1 repo-kit "), lines)
        self.assertIn("PREFIX", lines[1])

    def test_read_error_without_strerror_falls_back_to_class_name(self):
        # An OSError built from a single message argument (not (errno, strerror)) leaves strerror
        # None; a real filesystem failure cannot produce this, so the read is mocked in-process.
        self.write_kit("mfe", files={"AGENTS.md": "# __MFE__\n"})
        self.write_repos(repo_entry("mfe-abs-operations", {
            "kind": "mfe", "params": {"MFE": "mfe-abs-operations", "BFF": "bff-abs-operations"}}))
        ctx = common.Context(self.ws)
        target = self.ws / KITS / "mfe" / "files" / "AGENTS.md"
        original_read_bytes = Path.read_bytes

        def fake_read_bytes(path):
            if path == target:
                raise OSError("boom")
            return original_read_bytes(path)

        with mock.patch.object(Path, "read_bytes", fake_read_bytes):
            findings = rules_repo_kits.check_repo_kits(ctx)
        messages = [f.message for f in findings if f.rule == "repo-kit"]
        self.assertEqual(messages, ["kit mfe: files/AGENTS.md cannot be read: OSError"])

    def test_entry_with_broken_kit_json(self):
        self.write_kit("mfe")
        (self.ws / KITS / "mfe" / "kit.json").write_text("{broken", encoding="utf-8")
        self.write_repos(repo_entry("mfe-abs-operations", {
            "kind": "mfe", "params": {"MFE": "mfe-abs-operations", "BFF": "bff-abs-operations"}}))
        lines = self.findings()
        self.assertEqual(len(lines), 2, lines)
        kit_lines = [line for line in lines if line.startswith(KITS + "/mfe/kit.json:0 repo-kit ")]
        repo_lines = [line for line in lines if line.startswith("repos.json:")]
        self.assertEqual(len(kit_lines), 1, lines)
        self.assertEqual(len(repo_lines), 1, lines)
        self.assertIn("not valid JSON", kit_lines[0])
        self.assertIn("mfe-abs-operations", repo_lines[0])
        self.assertIn("kit mfe", repo_lines[0])

    def test_missing_parameter(self):
        self.write_kit("mfe")
        self.write_repos(repo_entry("mfe-abs-operations", {"kind": "mfe", "params": {"MFE": "mfe-abs-operations"}}))
        lines = self.findings()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("repos.json:"), lines)
        self.assertIn("mfe-abs-operations", lines[0])
        self.assertIn("BFF", lines[0])

    def test_unknown_kind(self):
        self.write_kit("mfe")
        self.write_repos(repo_entry("gw", {"kind": "gateway", "params": {}}))
        lines = self.findings()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("repos.json:"), lines)
        self.assertIn("gw", lines[0].split(" ", 2)[2])
        self.assertIn("gateway", lines[0])

    def test_value_not_matching_pattern(self):
        self.write_kit("mfe")
        self.write_repos(repo_entry("mfe-abs-operations", {
            "kind": "mfe", "params": {"MFE": "mfe-abs-operations", "BFF": "gateway"}}))
        lines = self.findings()
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("BFF", lines[0])


if __name__ == "__main__":
    unittest.main()
