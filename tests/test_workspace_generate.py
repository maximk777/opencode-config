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

import generate
from wslib import gen_adapters, gen_tables

SCRIPT = REPO / "kits/workspace/tools/generate.py"
AGENT = b"---\nname: reviewer\ndescription: Reviews things\n---\nBody line\n"
SKILL = b"---\nname: demo\ndescription: Demo skill\n---\nUse it.\n"
RULE = b"# Keys and links\n\nText.\n"
REPOS = {
    "repositories": [
        {"name": "b-repo", "remote": "git@x:b.git", "forge": "gitlab", "default_branch": "main",
         "roles": ["backend"], "summary": "B"},
        {"name": "a-repo", "remote": "git@x:a.git", "forge": "gitlab", "default_branch": "master",
         "roles": ["frontend", "qa"], "summary": "A"},
    ]
}
REPOSITORIES = b"# Repositories\n\n<!-- repos:begin -->\nold\n<!-- repos:end -->\n"


def write(root, rel, data):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def snapshot(root):
    result = {}
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            path = Path(dirpath, name)
            result[path.relative_to(root).as_posix()] = path.read_bytes()
    return result


class Generate(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name).resolve()
        write(self.root, ".agents/kit.json", b"{}\n")
        write(self.root, ".agents/agents/reviewer.md", AGENT)
        write(self.root, ".agents/skills/demo/SKILL.md", SKILL)
        write(self.root, ".agents/rules/links.md", RULE)
        write(self.root, "repos.json", (json.dumps(REPOS, indent=2) + "\n").encode("utf-8"))
        write(self.root, "REPOSITORIES.md", REPOSITORIES)

    def tearDown(self):
        self._td.cleanup()

    def run_script(self, cwd=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=str(cwd or self.root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )

    def test_first_run_creates_outputs(self):
        proc = self.run_script()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual((self.root / "CLAUDE.md").read_bytes(), b"@AGENTS.md\n")
        self.assertEqual((self.root / ".claude/agents/reviewer.md").read_bytes(), AGENT)
        self.assertTrue((self.root / ".opencode/agents/reviewer.md").is_file())
        self.assertEqual((self.root / ".claude/skills/demo/SKILL.md").read_bytes(), SKILL)
        self.assertTrue((self.root / ".cursor/rules/links.mdc").is_file())
        self.assertEqual((self.root / ".agents/index.json").read_bytes(), b"{}\n")

    def test_second_run_changes_nothing(self):
        first = self.run_script()
        self.assertEqual(first.returncode, 0, first.stderr)
        before = snapshot(self.root)
        second = self.run_script()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("generated: 0 files changed", second.stdout)
        self.assertEqual(snapshot(self.root), before)

    def test_repository_order_is_kept(self):
        self.assertEqual(self.run_script().returncode, 0)
        text = (self.root / "REPOSITORIES.md").read_text(encoding="utf-8")
        self.assertLess(text.index("| b-repo |"), text.index("| a-repo |"))

    def test_stale_files_and_emptied_dirs_are_removed(self):
        self.assertEqual(self.run_script().returncode, 0)
        write(self.root, ".claude/agents/old.md", b"old\n")
        write(self.root, ".cursor/rules/old.mdc", b"old\n")
        write(self.root, ".claude/skills/gone/nested/x.md", b"old\n")
        proc = self.run_script()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("generated: 3 files changed", proc.stdout)
        self.assertFalse((self.root / ".claude/agents/old.md").exists())
        self.assertFalse((self.root / ".cursor/rules/old.mdc").exists())
        self.assertFalse((self.root / ".claude/skills/gone").exists())
        self.assertEqual((self.root / ".claude/agents/reviewer.md").read_bytes(), AGENT)

    def test_symlinked_output_is_replaced_by_a_copy(self):
        (self.root / ".claude/agents").mkdir(parents=True)
        os.symlink(str(self.root / ".agents/agents/reviewer.md"), str(self.root / ".claude/agents/reviewer.md"))
        os.symlink(str(self.root / ".agents/skills"), str(self.root / ".claude/skills"))
        self.assertEqual(self.run_script().returncode, 0)
        for rel in (".claude/agents/reviewer.md", ".claude/skills", ".claude/skills/demo/SKILL.md"):
            self.assertFalse((self.root / rel).is_symlink(), rel)
        self.assertEqual((self.root / ".claude/skills/demo/SKILL.md").read_bytes(), SKILL)
        self.assertEqual((self.root / ".agents/skills/demo/SKILL.md").read_bytes(), SKILL)

    def test_symlinked_sources_dir_is_left_alone(self):
        with tempfile.TemporaryDirectory() as other:
            sources = Path(other).resolve() / "agents-src"
            os.rename(str(self.root / ".agents"), str(sources))
            os.symlink(str(sources), str(self.root / ".agents"))
            first = self.run_script()
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertTrue((self.root / ".agents").is_symlink())
            self.assertEqual((sources / "agents/reviewer.md").read_bytes(), AGENT)
            self.assertTrue((sources / "index.json").is_file())
            second = self.run_script()
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("generated: 0 files changed", second.stdout)
            self.assertTrue((self.root / ".agents").is_symlink())

    def test_directory_on_rendered_path_is_replaced(self):
        write(self.root, ".agents/skills/demo/ref/x.md", b"nested\n")
        self.assertEqual(self.run_script().returncode, 0)
        self.assertTrue((self.root / ".claude/skills/demo/ref").is_dir())
        (self.root / ".agents/skills/demo/ref/x.md").unlink()
        (self.root / ".agents/skills/demo/ref").rmdir()
        write(self.root, ".agents/skills/demo/ref", b"flat\n")
        first = self.run_script()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual((self.root / ".claude/skills/demo/ref").read_bytes(), b"flat\n")
        second = self.run_script()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("generated: 0 files changed", second.stdout)

    def test_runs_from_nested_subdirectory(self):
        nested = self.root / "docs" / "deep"
        nested.mkdir(parents=True)
        proc = self.run_script(cwd=nested)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((self.root / "CLAUDE.md").is_file())
        self.assertFalse((nested / "CLAUDE.md").exists())

    def test_outside_workspace_exits_2(self):
        with tempfile.TemporaryDirectory() as other:
            proc = self.run_script(cwd=other)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("not inside a workspace", proc.stderr)

    def test_render_all_is_union_of_renderers(self):
        expected = {}
        expected.update(gen_adapters.render(self.root))
        expected.update(gen_tables.render(self.root))
        self.assertEqual(generate.render_all(self.root), expected)


if __name__ == "__main__":
    unittest.main()
