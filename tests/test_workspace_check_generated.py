import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
import tempfile
import unittest

from workspace_helpers import create_workspace, run_check, run_generate

RULE = "generated-stale"


def stale_lines(lines):
    """Keep only generated-stale findings; other rule modules may add their own lines."""
    return [line for line in lines if len(line.split(" ")) > 1 and line.split(" ")[1] == RULE]


class CheckGeneratedTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.ws = create_workspace(self.tmp)

    def tearDown(self):
        self._tmp.cleanup()

    def findings(self):
        _, lines, stderr = run_check(self.ws)
        self.assertNotIn("Traceback", stderr)
        return stale_lines(lines)

    def assert_fixed_by_generate(self):
        result = run_generate(self.ws)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.findings(), [])

    def test_fresh_workspace_has_none(self):
        self.assertEqual(self.findings(), [])

    def test_appended_repository_makes_table_stale(self):
        manifest = self.ws / "repos.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["repositories"].append({
            "name": "billing", "remote": "git@example.com:billing.git", "forge": "gitlab",
            "default_branch": "main", "roles": ["backend"], "summary": "Billing service",
        })
        manifest.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        table_lines = (self.ws / "REPOSITORIES.md").read_text(encoding="utf-8").split("\n")
        # The new row takes the place of the end marker, so that is the first differing line.
        expected_line = table_lines.index("<!-- repos:end -->") + 1

        lines = self.findings()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("REPOSITORIES.md:%d generated-stale " % expected_line), lines)
        self.assertIn("differs from generator output; run python3 tools/generate.py", lines[0])
        self.assert_fixed_by_generate()

    def test_changed_claude_md(self):
        (self.ws / "CLAUDE.md").write_text("hand edit\n", encoding="utf-8")
        lines = self.findings()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("CLAUDE.md:1 generated-stale "), lines)
        self.assert_fixed_by_generate()

    def test_deleted_index(self):
        (self.ws / ".agents/index.json").unlink()
        lines = self.findings()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(".agents/index.json:1 generated-stale "), lines)
        self.assertIn("missing; run python3 tools/generate.py", lines[0])
        self.assert_fixed_by_generate()

    def test_extra_file_in_owned_dir(self):
        ghost = self.ws / ".claude/agents/ghost.md"
        ghost.parent.mkdir(parents=True, exist_ok=True)
        ghost.write_text("# ghost\n", encoding="utf-8")
        lines = self.findings()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(".claude/agents/ghost.md:1 generated-stale "), lines)
        self.assertIn("not produced by the generator; run python3 tools/generate.py", lines[0])
        self.assert_fixed_by_generate()

    def test_ignored_junk_in_owned_dirs(self):
        exclude = self.ws / ".git/info/exclude"
        exclude.parent.mkdir(parents=True, exist_ok=True)
        with exclude.open("a", encoding="utf-8") as fh:
            fh.write("\n.DS_Store\n")
        (self.ws / ".claude/agents").mkdir(parents=True, exist_ok=True)
        (self.ws / ".claude/agents/.DS_Store").write_bytes(b"\0junk")
        skill = sorted(p for p in (self.ws / ".claude/skills").iterdir() if p.is_dir())[0]
        # __pycache__/ is ignored by the workspace .gitignore.
        (skill / "__pycache__").mkdir()
        (skill / "__pycache__/x.pyc").write_bytes(b"\0pyc")
        self.assertEqual(self.findings(), [])
        ghost = self.ws / ".claude/agents/ghost.md"
        ghost.write_text("# ghost\n", encoding="utf-8")
        lines = self.findings()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(".claude/agents/ghost.md:1 generated-stale "), lines)

    def test_rendered_path_replaced_by_directory(self):
        claude = self.ws / "CLAUDE.md"
        claude.unlink()
        claude.mkdir()
        lines = self.findings()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("CLAUDE.md:1 generated-stale "), lines)
        self.assertIn("unreadable; run python3 tools/generate.py", lines[0])


class FirstDiffLineTest(unittest.TestCase):
    def test_lines(self):
        from wslib.rules_generated import first_diff_line
        self.assertEqual(first_diff_line(b"a\nb\n", b"a\nc\n"), 2)
        self.assertEqual(first_diff_line(b"a\nb\n", b"a\nb\nc\n"), 3)
        self.assertEqual(first_diff_line(b"", b"a\n"), 1)


if __name__ == "__main__":
    unittest.main()
