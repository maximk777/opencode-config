import importlib.machinery
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "lib"))

from ovsync import mirror, scope


def git(repo, *args):
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", *args],
        cwd=repo, check=True, capture_output=True,
    )


def head_of(repo):
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True)
    return r.stdout.strip()


class BuildMirrorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        git(self.repo, "init")
        self.stage = self.tmp / "stage"
        self.rules = scope.parse("architecture/**\n!architecture/poc/*/**\n")

    def _write(self, rel, content):
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content)
        return p

    def test_committed_content_only_then_replace_on_second_build(self):
        self._write("architecture/adr/001.md", "v1\n")
        self._write("architecture/poc/x/data.json", "{}")
        self._write("notes/todo.md", "todo\n")
        self._write("architecture/img.png", b"\x89PNG\x00\xff")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "v1")

        # uncommitted edit and an untracked file must not enter the mirror
        self._write("architecture/adr/001.md", "v2\n")
        self._write("architecture/draft.md", "draft\n")

        head = head_of(self.repo)
        count = mirror.build_mirror(subprocess.run, self.repo, head, self.rules, self.stage, "demo")

        self.assertEqual(count, 2)
        self.assertEqual((self.stage / "demo/architecture/adr/001.md").read_text(), "v1\n")
        self.assertEqual((self.stage / "demo/architecture/img.png").read_bytes(), b"\x89PNG\x00\xff")
        self.assertFalse((self.stage / "demo/architecture/draft.md").exists())
        self.assertFalse((self.stage / "demo/architecture/poc").exists())
        self.assertFalse((self.stage / "demo/notes").exists())
        self.assertFalse((self.stage / "demo.tmp").exists())

        (self.repo / "architecture/adr/001.md").unlink()
        (self.repo / "architecture/draft.md").unlink()  # still untracked; drop it so -A below doesn't commit it
        self._write("architecture/adr/002.md", "v2\n")
        self._write("architecture/a b.md", "space\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "v2")

        head2 = head_of(self.repo)
        count2 = mirror.build_mirror(subprocess.run, self.repo, head2, self.rules, self.stage, "demo")

        self.assertEqual(count2, 3)
        self.assertFalse((self.stage / "demo/architecture/adr/001.md").exists())
        self.assertEqual((self.stage / "demo/architecture/adr/002.md").read_text(), "v2\n")
        self.assertEqual((self.stage / "demo/architecture/a b.md").read_text(), "space\n")
        self.assertFalse((self.stage / "demo.old").exists())
        self.assertFalse((self.stage / "demo.tmp").exists())

    def test_empty_selection_returns_zero_and_leaves_existing_mirror(self):
        self._write("architecture/adr/001.md", "v1\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "v1")
        head = head_of(self.repo)

        count = mirror.build_mirror(subprocess.run, self.repo, head, self.rules, self.stage, "demo")
        self.assertEqual(count, 1)
        marker = self.stage / "demo/architecture/adr/001.md"
        self.assertTrue(marker.exists())

        no_match_rules = scope.parse("nomatch/**\n")
        count2 = mirror.build_mirror(subprocess.run, self.repo, head, no_match_rules, self.stage, "demo")

        self.assertEqual(count2, 0)
        self.assertTrue(marker.exists())
        self.assertFalse((self.stage / "demo.tmp").exists())

    def test_gitlink_submodule_is_skipped(self):
        self._write("architecture/adr/001.md", "v1\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "v1")
        subprocess.run(
            ["git", "update-index", "--add", "--cacheinfo", "160000," + "a" * 40 + ",architecture/sub"],
            cwd=self.repo, check=True, capture_output=True,
        )
        git(self.repo, "commit", "-m", "add submodule")

        head = head_of(self.repo)
        count = mirror.build_mirror(subprocess.run, self.repo, head, self.rules, self.stage, "demo")

        self.assertEqual(count, 1)
        self.assertFalse((self.stage / "demo/architecture/sub").exists())


class FakeResult:
    def __init__(self, returncode=0, stdout=b"", stderr=b""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def ls_tree_entries(entries):
    """entries: iterable of (mode, type, sha, path_bytes) -> raw `git ls-tree -r -z` output."""
    out = b""
    for mode, type_, sha, path in entries:
        out += f"{mode} {type_} {sha}\t".encode() + path + b"\0"
    return out


class FakeBatchTests(unittest.TestCase):
    """Exercises committed_paths/read_blobs error paths through a scripted fake `run`, without git."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.rules = scope.parse("architecture/**\n")

    def test_ls_tree_failure_raises_runtime_error(self):
        def fake_run(argv, **kwargs):
            self.assertEqual(argv[1], "ls-tree")
            return FakeResult(returncode=128, stderr=b"fatal: bad object HEAD")

        with self.assertRaises(RuntimeError):
            mirror.build_mirror(fake_run, Path("/unused"), "HEAD", self.rules, self.tmp / "stage", "demo")

    def test_missing_blob_raises_runtime_error(self):
        head = "deadbeef" * 5
        ls_tree_out = ls_tree_entries([("100644", "blob", "a" * 40, b"architecture/a.md")])

        def fake_run(argv, **kwargs):
            if argv[1] == "ls-tree":
                return FakeResult(stdout=ls_tree_out)
            if argv[1] == "cat-file":
                return FakeResult(stdout=f"{head}:architecture/a.md missing\n".encode())
            raise AssertionError(f"unexpected argv {argv}")

        with self.assertRaises(RuntimeError):
            mirror.build_mirror(fake_run, Path("/unused"), head, self.rules, self.tmp / "stage", "demo")

    def test_truncated_cat_file_reply_raises_runtime_error(self):
        head = "head"
        ls_tree_out = ls_tree_entries([("100644", "blob", "a" * 40, b"architecture/big.md")])

        def fake_run(argv, **kwargs):
            if argv[1] == "ls-tree":
                return FakeResult(stdout=ls_tree_out)
            if argv[1] == "cat-file":
                # header promises 10 bytes but the reply is cut off mid-blob
                return FakeResult(stdout=(f"{'a' * 40} blob 10\n" + "abc").encode())
            raise AssertionError(f"unexpected argv {argv}")

        with self.assertRaises(RuntimeError):
            mirror.build_mirror(fake_run, Path("/unused"), head, self.rules, self.tmp / "stage", "demo")

    def test_path_with_newline_is_skipped(self):
        head = "head"
        ls_tree_out = ls_tree_entries([
            ("100644", "blob", "a" * 40, b"architecture/bad\nname.md"),
            ("100644", "blob", "b" * 40, b"architecture/ok.md"),
        ])

        def fake_run(argv, **kwargs):
            if argv[1] == "ls-tree":
                return FakeResult(stdout=ls_tree_out)
            if argv[1] == "cat-file":
                self.assertNotIn(b"bad\nname", kwargs.get("input", b""))
                return FakeResult(stdout=f"{'b' * 40} blob 2\nOK\n".encode())
            raise AssertionError(f"unexpected argv {argv}")

        stage = self.tmp / "stage"
        count = mirror.build_mirror(fake_run, Path("/unused"), head, self.rules, stage, "demo")

        self.assertEqual(count, 1)
        self.assertEqual((stage / "demo/architecture/ok.md").read_text(), "OK")
        self.assertFalse((stage / "demo/architecture/bad\nname.md").exists())

    def test_non_utf8_path_is_skipped_without_crash(self):
        head = "head"
        ls_tree_out = ls_tree_entries([
            ("100644", "blob", "a" * 40, b"architecture/\xff.md"),
            ("100644", "blob", "b" * 40, b"architecture/ok.md"),
        ])

        def fake_run(argv, **kwargs):
            if argv[1] == "ls-tree":
                return FakeResult(stdout=ls_tree_out)
            if argv[1] == "cat-file":
                return FakeResult(stdout=f"{'b' * 40} blob 2\nOK\n".encode())
            raise AssertionError(f"unexpected argv {argv}")

        stage = self.tmp / "stage"
        count = mirror.build_mirror(fake_run, Path("/unused"), head, self.rules, stage, "demo")

        self.assertEqual(count, 1)
        self.assertEqual((stage / "demo/architecture/ok.md").read_text(), "OK")


class CleanupStageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_removes_tmp_and_old_keeps_final(self):
        stage = self.tmp / "stage"
        (stage / "demo").mkdir(parents=True)
        (stage / "demo" / "keep.txt").write_text("x")
        (stage / "demo.tmp").mkdir(parents=True)
        (stage / "demo.old").mkdir(parents=True)

        mirror.cleanup_stage(stage)

        self.assertTrue((stage / "demo" / "keep.txt").exists())
        self.assertFalse((stage / "demo.tmp").exists())
        self.assertFalse((stage / "demo.old").exists())

    def test_missing_stage_is_fine(self):
        mirror.cleanup_stage(self.tmp / "does-not-exist")


if __name__ == "__main__":
    unittest.main()
