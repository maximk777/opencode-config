import re
import subprocess
import tempfile
import unittest
from pathlib import Path

GUARD = "bin/check-public"
# Built from fragments so this test never carries a literal marker.
MARKER = "wb" + "bank"
# Same shape as an npm integrity hash: a long mixed-case run with digits.
INTEGRITY = '"integrity": "sha512-oGMAgGoQdBXbZqNG0Ze56CHjDZ1IDYOwGYxYjO5KLSlz5HiNQ9udIXsPZ61VWaHGZ5XW/jyjmr6t2xz2jGVwbQ=="'


def make_repo(files):
    root = tempfile.mkdtemp()
    def git(*args):
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
    git("init", "-q")
    git("config", "user.name", "tester")
    git("config", "user.email", "tester@example.com")
    for name, text in files.items():
        path = Path(root) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        git("add", name)
    git("commit", "-q", "-m", "fixture")
    return root


def run_guard(repo):
    return subprocess.run([GUARD, repo], capture_output=True, text=True)


class CheckPublic(unittest.TestCase):
    def test_planted_marker_fails_and_names_commit_and_file(self):
        leak = "notes/leak.md"
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo({leak: "touches " + MARKER + " internally\n"})
            result = run_guard(repo)
        self.assertNotEqual(result.returncode, 0)
        output = result.stdout + result.stderr
        self.assertIn(leak, output)
        self.assertRegex(output, r"commit [0-9a-f]{7,} " + re.escape(leak))

    def test_clean_repository_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo({"README.md": "a clean fixture file\n"})
            result = run_guard(repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_package_lock_integrity_hash_is_not_a_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo({"package-lock.json": INTEGRITY + "\n"})
            result = run_guard(repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # The skip is scoped to the lock file: elsewhere the same content trips.
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo({"notes.md": INTEGRITY + "\n"})
            result = run_guard(repo)
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
