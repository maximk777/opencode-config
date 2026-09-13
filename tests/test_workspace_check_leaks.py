import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
import tempfile
import unittest

from workspace_helpers import create_workspace, run_check

RULES = ("home-path", "local-link", "secret-file", "stand-string")


def rule_lines(lines):
    """Keep only findings of this task's rules; other rule modules may add their own lines."""
    return [line for line in lines if len(line.split(" ")) > 1 and line.split(" ")[1] in RULES]


class CheckLeaksTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.ws = create_workspace(self.tmp)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text):
        path = self.ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def findings(self):
        _, lines, stderr = run_check(self.ws)
        self.assertNotIn("Traceback", stderr)
        return rule_lines(lines)

    def lines_for(self, lines, path, rule=None):
        return [line for line in lines
                if line.startswith(path + ":") and (rule is None or line.split(" ")[1] == rule)]

    def test_fresh_workspace_has_no_leak_findings(self):
        self.assertEqual(self.findings(), [])

    def test_home_path_in_rule(self):
        self.write(".agents/rules/build.md", "# Build\n\nSteps:\nRun from /Users/alice/work\n")
        lines = self.findings()
        self.assertTrue(any(line.startswith(".agents/rules/build.md:4 home-path ") for line in lines), lines)

    def test_linux_and_windows_home_paths(self):
        self.write("docs/notes.md", "# Notes\n\nsee /home/bob/x\nand C:\\Users\\carol\\x\n")
        lines = self.findings()
        self.assertTrue(any(line.startswith("docs/notes.md:3 home-path ") for line in lines), lines)
        self.assertTrue(any(line.startswith("docs/notes.md:4 home-path ") for line in lines), lines)

    def test_placeholder_home_path_not_reported(self):
        self.write("docs/notes.md", "# Notes\n\nNever write /Users/<name>/ paths.\n")
        self.assertEqual(self.lines_for(self.findings(), "docs/notes.md"), [])

    def test_url_and_api_paths_not_reported_as_home_paths(self):
        self.write("docs/notes.md", "# Notes\n\nhttps://wiki.example/home/page/intro\nGET /api/Users/42/roles\n")
        self.assertEqual(self.lines_for(self.findings(), "docs/notes.md", "home-path"), [])

    def test_home_path_after_separators(self):
        body = ["/Users/alice/x", "`/home/bob/`", "file:///Users/alice/x",
                "cd /Users/alice/x", "\"/home/bob/x\"", "(/Users/alice/x)"]
        self.write("docs/notes.md", "# Notes\n\n" + "\n".join(body) + "\n")
        lines = self.findings()
        for lineno in range(3, 3 + len(body)):
            self.assertTrue(any(line.startswith("docs/notes.md:%d home-path " % lineno) for line in lines),
                            f"{lineno}: {lines}")

    def test_json_escaped_windows_home_path(self):
        self.write("docs/paths.json", json.dumps({"dir": "C:\\Users\\carol\\x"}, indent=2) + "\n")
        lines = self.findings()
        self.assertTrue(any(line.startswith("docs/paths.json:2 home-path ") for line in lines), lines)

    def test_ignored_local_env_is_skipped(self):
        self.write(".local/env", "HOME_DIR=/Users/alice/\n")
        self.assertEqual(self.lines_for(self.findings(), ".local/env"), [])

    def test_local_link(self):
        self.write("docs/notes.md", "# Notes\n\n[draft](../.local/drafts/TASK-1.md)\n")
        lines = self.findings()
        self.assertTrue(any(line.startswith("docs/notes.md:3 local-link ") for line in lines), lines)

    def test_secret_files(self):
        for rel in (".env", "deploy/key.pem", "id_rsa"):
            self.write(rel, "secret\n")
        self.write(".env.example", "TOKEN=\n")
        lines = self.findings()
        for rel in (".env", "deploy/key.pem", "id_rsa"):
            self.assertTrue(self.lines_for(lines, rel, "secret-file"), f"{rel}: {lines}")
        self.assertEqual(self.lines_for(lines, ".env.example"), [])

    def test_local_file_listed_when_not_ignored(self):
        gitignore = self.ws / ".gitignore"
        kept = [line for line in gitignore.read_text(encoding="utf-8").splitlines() if line != ".local/"]
        gitignore.write_text("\n".join(kept) + "\n", encoding="utf-8")
        self.write(".local/env", "TOKEN=\n")
        self.assertTrue(self.lines_for(self.findings(), ".local/env", "secret-file"))

    def test_stand_string(self):
        envs = {"stands": [{"key": "stand:stage", "purpose": "Testing", "access": "VPN",
                            "services": {"svc": "http://svc.stage.example"}}]}
        self.write("environments.json", json.dumps(envs, indent=2, ensure_ascii=False) + "\n")
        record = "".join("line %d\n" % n for n in range(1, 9)) + "Docs at http://svc.stage.example/docs\n"
        self.write("work/TASK-1/record.md", record)
        lines = self.findings()
        self.assertTrue(any(line.startswith("work/TASK-1/record.md:9 stand-string ") for line in lines), lines)
        self.assertEqual(self.lines_for(lines, "environments.json", "stand-string"), [])

    def test_stand_string_host_boundary(self):
        envs = {"stands": [{"key": "stand:stage", "purpose": "Testing", "access": "VPN",
                            "services": {"svc": "http://svc.stage.example"}}]}
        self.write("environments.json", json.dumps(envs, indent=2, ensure_ascii=False) + "\n")
        self.write("docs/notes.md", "# Notes\n\nhttp://svc.stage.example.org/x\nsee http://svc.stage.example\n")
        lines = self.lines_for(self.findings(), "docs/notes.md", "stand-string")
        self.assertEqual([line.split(" ")[0] for line in lines], ["docs/notes.md:4"], lines)


if __name__ == "__main__":
    unittest.main()
