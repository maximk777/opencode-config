import importlib.machinery
import os
import shutil
import subprocess
import tempfile
import unittest
import unittest.mock
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
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


class NoOpenViking(unittest.TestCase):
    def test_commits_without_docker_on_path(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        # PATH exposes only git, via a symlink, so any docker/ov-sync call would raise FileNotFoundError.
        path_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, path_dir, True)
        (path_dir / "git").symlink_to(shutil.which("git"))
        repo = root / "demo"
        repo.mkdir()
        git(repo, "init", "-q")
        git(repo, "config", "user.name", "test")
        git(repo, "config", "user.email", "test@example.com")
        # Local override: the global gpgsign=ssh config needs ssh-keygen, which the
        # restricted PATH below deliberately omits.
        git(repo, "config", "commit.gpgsign", "false")
        (repo / "note.md").write_text("note\n")

        recorded = []
        real_run = subprocess.run

        def recording_run(argv, **kwargs):
            recorded.append(argv)
            return real_run(argv, **kwargs)

        with unittest.mock.patch.dict(os.environ, {"PATH": str(path_dir)}):
            with unittest.mock.patch("subprocess.run", recording_run):
                ok, text = S.commit("demo", "docs(demo): add note", root=root)

        self.assertTrue(ok, text)
        self.assertTrue(recorded)
        self.assertTrue(any(argv[:2] == ["git", "commit"] for argv in recorded))
        self.assertEqual(git(repo, "log", "-1", "--format=%s"), "docs(demo): add note")
        for argv in recorded:
            name = Path(argv[0]).name
            self.assertNotEqual(name, "docker")
            self.assertFalse(name.endswith("ov-sync"))

    def test_source_has_no_openviking_call(self):
        text = (REPO / "bin/specs-commit").read_text()
        for word in ("docker", "ov-sync", "openviking", "add-resource"):
            self.assertNotIn(word, text)


if __name__ == "__main__":
    unittest.main()
