import importlib.machinery
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

S = importlib.machinery.SourceFileLoader("specs_commit", "bin/specs-commit").load_module()


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


class SpecsCommit(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.repo = self.root / "proj"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "t@t")
        git(self.repo, "config", "user.name", "t")
        (self.repo / "a.md").write_text("a\n")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_commits_all_changes(self):
        ok, text = S.commit("proj", "docs(proj): add a", self.root)
        self.assertTrue(ok, text)
        self.assertEqual(git(self.repo, "log", "-1", "--format=%s"), "docs(proj): add a")
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")

    def test_rejects_bad_message(self):
        ok, text = S.commit("proj", "Added stuff", self.root)
        self.assertFalse(ok)
        self.assertIn("commit message rejected", text)

    def test_rejects_traversal(self):
        for name in ("..", "../proj", "a/b", ".hidden"):
            ok, _ = S.commit(name, "docs(proj): add a", self.root)
            self.assertFalse(ok, name)

    def test_refuses_nested_directory_of_another_repo(self):
        (self.repo / "inner").mkdir()
        ok, text = S.commit("inner", "docs(proj): add a", self.repo)
        self.assertFalse(ok)
        self.assertIn("not the root", text)

    def test_nothing_to_commit(self):
        S.commit("proj", "docs(proj): add a", self.root)
        ok, text = S.commit("proj", "docs(proj): add b", self.root)
        self.assertTrue(ok)
        self.assertEqual(text, "nothing to commit")

    def test_follows_symlinked_project(self):
        link_root = Path(tempfile.mkdtemp())
        (link_root / "proj").symlink_to(self.repo)
        try:
            ok, text = S.commit("proj", "docs(proj): add a", link_root)
            self.assertTrue(ok, text)
        finally:
            shutil.rmtree(link_root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
