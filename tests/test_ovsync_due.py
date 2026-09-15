import importlib.machinery
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "lib"))

from ovsync import due


class ListProjects(unittest.TestCase):
    def test_lists_git_dirs_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            specs = Path(tmp)
            (specs / "demo" / ".git").mkdir(parents=True)
            (specs / "alpha" / ".git").mkdir(parents=True)
            (specs / ".ov-stage" / ".git").mkdir(parents=True)
            (specs / "plain").mkdir()
            (specs / "opencode-smoke").symlink_to(specs / "demo")
            self.assertEqual(due.list_projects(specs), ["alpha", "demo"])

    def test_nonexistent_specs_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(due.list_projects(Path(tmp) / "does-not-exist"), [])


class HeadInfo(unittest.TestCase):
    def test_parses_sha_and_epoch(self):
        calls = []

        def fake_run(argv, **kwargs):
            calls.append((argv, kwargs))
            return subprocess.CompletedProcess(argv, 0, "abc123 1700000000\n", "")

        repo = Path("/some/repo")
        result = due.head_info(fake_run, repo)
        self.assertEqual(result, ("abc123", 1700000000.0))
        self.assertEqual(calls[0][0], ["git", "log", "-1", "--format=%H %ct"])
        self.assertEqual(calls[0][1].get("cwd"), repo)
        self.assertEqual(calls[0][1].get("timeout"), 30)

    def test_nonzero_exit_returns_none(self):
        def fake_run(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 1, "", "fatal: bad")

        self.assertIsNone(due.head_info(fake_run, Path(".")))

    def test_empty_stdout_returns_none(self):
        def fake_run(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 0, "", "")

        self.assertIsNone(due.head_info(fake_run, Path(".")))

    def test_missing_git_returns_none(self):
        def fake_run(argv, **kwargs):
            raise FileNotFoundError("git")

        self.assertIsNone(due.head_info(fake_run, Path(".")))

    def test_timeout_returns_none(self):
        def fake_run(argv, **kwargs):
            raise subprocess.TimeoutExpired(cmd=argv, timeout=30)

        self.assertIsNone(due.head_info(fake_run, Path(".")))

    def test_missing_space_returns_none(self):
        def fake_run(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 0, "abc123500000000\n", "")

        self.assertIsNone(due.head_info(fake_run, Path(".")))

    def test_non_numeric_time_returns_none(self):
        def fake_run(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 0, "abc123 notatime\n", "")

        self.assertIsNone(due.head_info(fake_run, Path(".")))


class DueProjectsTable(unittest.TestCase):
    """Table-driven cases from the brief, driven through the public due_projects entry point."""

    NOW = 10_000.0

    def check(self, head, st, marker, expect_due):
        heads = {"demo": head}
        states = {"demo": st}
        markers = {"demo": marker} if marker is not None else {}
        result = due.due_projects(["demo"], heads, states, markers, self.NOW)
        self.assertEqual(result, ["demo"] if expect_due else [])

    def test_marker_debounce(self):
        st = {"synced_commit": "abc"}
        head = ("abc", self.NOW - 5)
        self.check(head, st, self.NOW - 89, False)
        self.check(head, st, self.NOW - 91, True)

    def test_commit_settle_gate(self):
        st = {"synced_commit": "a"}
        self.check(("b", self.NOW - 180), st, None, True)
        self.check(("b", self.NOW - 60), st, None, False)

    def test_head_equal_to_synced_commit_not_due(self):
        st = {"synced_commit": "a"}
        self.check(("a", self.NOW - 500), st, None, False)

    def test_no_head_not_due_unless_marker_due(self):
        st = {}
        self.check(None, st, None, False)
        self.check(None, st, self.NOW - 89, False)
        self.check(None, st, self.NOW - 91, True)

    def test_next_attempt_gate(self):
        st = {"next_attempt": self.NOW + 5}
        self.check(None, st, self.NOW - 91, False)

    def test_running_gate(self):
        self.check(None, {"running": True, "started_at": self.NOW - 100}, self.NOW - 91, False)
        self.check(None, {"running": True, "started_at": self.NOW - 2000}, self.NOW - 91, True)
        # missing started_at while running counts as a crashed run: it does not block.
        self.check(None, {"running": True, "started_at": None}, self.NOW - 91, True)

    def test_failing_gate(self):
        head = ("h1", self.NOW - 200)
        st_blocked = {
            "failing": True,
            "failing_head": "h1",
            "failing_marker": 500.0,
            "synced_commit": "h1",
        }
        self.check(head, st_blocked, 500.0, False)

        head_changed = ("h2", self.NOW - 200)
        st_head_changed = {
            "failing": True,
            "failing_head": "h1",
            "failing_marker": 500.0,
            "synced_commit": "h_old",
        }
        self.check(head_changed, st_head_changed, 500.0, True)

        st_marker_advanced = {
            "failing": True,
            "failing_head": "h1",
            "failing_marker": 100.0,
            "synced_commit": "h1",
        }
        self.check(head, st_marker_advanced, 200.0, True)

    def test_order(self):
        projects = ["zeta", "alpha", "two", "one"]
        markers = {"one": 50.0, "two": 100.0}
        heads = {
            "alpha": ("h", self.NOW - 200),
            "zeta": ("h", self.NOW - 200),
        }
        states = {
            "alpha": {"synced_commit": "old"},
            "zeta": {"synced_commit": "old"},
            "one": {},
            "two": {},
        }
        result = due.due_projects(projects, heads, states, markers, self.NOW)
        self.assertEqual(result, ["one", "two", "alpha", "zeta"])


class IsDueFailingWithUnknownHead(unittest.TestCase):
    """A None head (git failed) must not read as "differs" from failing_head/synced_commit."""

    NOW = 10_000.0

    def test_unknown_head_stays_blocked(self):
        st = {"failing": True, "failing_head": "h1", "failing_marker": 500.0}
        self.assertFalse(due.is_due("d", None, st, 500.0, self.NOW))

    def test_unknown_head_unblocked_by_advanced_marker(self):
        st = {"failing": True, "failing_head": "h1", "failing_marker": 500.0}
        self.assertTrue(due.is_due("d", None, st, 600.0, self.NOW))


if __name__ == "__main__":
    unittest.main()
