import fcntl
import importlib.machinery
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "lib"))

from ovsync import state  # noqa: E402

D = importlib.machinery.SourceFileLoader("ov_syncd", str(REPO / "bin/ov-syncd")).load_module()

SCOPE_TEXT = (REPO / "openviking" / "sync-scope").read_text(encoding="utf-8")
EARLY_MORNING = datetime(2026, 1, 1, 1, 0)  # before NIGHT_HOUR, so nightly never fires by accident


def make_git_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    (path / ".git").mkdir()


def failing_git(argv, **kwargs):
    """A `run` stand-in whose git calls always fail cleanly (head_info returns None)."""
    return subprocess.CompletedProcess(argv, 1, "", "")


class BaseCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        home = root / "home"
        specs = root / "specs"
        repo = root / "repo"
        (repo / "openviking").mkdir(parents=True)
        (repo / "openviking" / "sync-scope").write_text(SCOPE_TEXT, encoding="utf-8")
        specs.mkdir(parents=True)
        self.paths = state.Paths(home, specs, repo)


class LockTest(BaseCase):
    def test_second_instance_exits_without_syncing(self):
        self.paths.lock.parent.mkdir(parents=True, exist_ok=True)
        fd = open(self.paths.lock, "a+")
        self.addCleanup(fd.close)
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with patch.object(D.runner, "sync_project") as sync_mock:
            code = D.main(
                ["--once"], paths=self.paths, run=object(), clock=lambda: 1000.0,
                sleep=lambda s: None, now_local=lambda: EARLY_MORNING,
            )
        self.assertEqual(code, 0)
        self.assertIn("worker already running", self.paths.log.read_text(encoding="utf-8"))
        sync_mock.assert_not_called()


class OnceTest(BaseCase):
    def test_runs_due_projects_in_order_with_scope_rules(self):
        make_git_repo(self.paths.specs / "demo")
        make_git_repo(self.paths.specs / "alpha")
        sleep_calls = []
        run_obj = object()

        def fake_sync(paths, project, run, clock, sleep, rules):
            self.assertIs(run, run_obj)
            return dict(state.EMPTY_STATE)

        with patch.object(D.due, "head_info", return_value=("abc123", 1000.0)), \
             patch.object(D.due, "due_projects", return_value=["demo", "alpha"]), \
             patch.object(D.runner, "sync_project", side_effect=fake_sync) as sync_mock:
            code = D.main(
                ["--once"], paths=self.paths, run=run_obj, clock=lambda: 2000.0,
                sleep=lambda s: sleep_calls.append(s), now_local=lambda: EARLY_MORNING,
            )
        self.assertEqual(code, 0)
        self.assertEqual(sleep_calls, [])
        self.assertEqual(len(sync_mock.call_args_list), 2)
        first, second = sync_mock.call_args_list
        self.assertEqual(first.args[0], self.paths)
        self.assertEqual(first.args[1], "demo")
        self.assertEqual(second.args[1], "alpha")
        rules = first.args[5]
        self.assertEqual(D.scope.select(["openspec/specs/x.md", "random.txt"], rules), ["openspec/specs/x.md"])
        self.assertEqual(second.args[5], rules)


class CleanupTest(BaseCase):
    def test_removes_leftover_tmp_and_old_dirs(self):
        self.paths.stage.mkdir(parents=True)
        tmp_dir = self.paths.stage / "demo.tmp"
        old_dir = self.paths.stage / "demo.old"
        tmp_dir.mkdir()
        old_dir.mkdir()
        code = D.main(
            ["--once"], paths=self.paths, run=object(), clock=lambda: 1000.0,
            sleep=lambda s: None, now_local=lambda: EARLY_MORNING,
        )
        self.assertEqual(code, 0)
        self.assertFalse(tmp_dir.exists())
        self.assertFalse(old_dir.exists())


class FailingProjectTest(BaseCase):
    def test_one_failure_does_not_stop_the_tick(self):
        make_git_repo(self.paths.specs / "demo")
        make_git_repo(self.paths.specs / "alpha")
        calls = []

        def fake_sync(paths, project, run, clock, sleep, rules):
            calls.append(project)
            if project == "demo":
                raise RuntimeError("boom")
            return dict(state.EMPTY_STATE)

        with patch.object(D.due, "due_projects", return_value=["demo", "alpha"]), \
             patch.object(D.runner, "sync_project", side_effect=fake_sync):
            D.tick(self.paths, failing_git, clock=lambda: 1000.0, sleep=lambda s: None, now_local=lambda: EARLY_MORNING)
        self.assertEqual(calls, ["demo", "alpha"])
        log_line = next(
            line for line in self.paths.log.read_text(encoding="utf-8").splitlines() if "demo" in line
        )
        self.assertIn("demo failed", log_line)
        self.assertIn("boom", log_line)


class NightlyTest(BaseCase):
    def test_runs_once_when_due_with_project_list(self):
        make_git_repo(self.paths.specs / "demo")
        with patch.object(D.due, "due_projects", return_value=[]), \
             patch.object(D.nightly, "run_nightly") as nightly_mock:
            D.tick(
                self.paths, failing_git, clock=lambda: 1000.0, sleep=lambda s: None,
                now_local=lambda: datetime(2026, 9, 15, 3, 5),
            )
        nightly_mock.assert_called_once()
        self.assertEqual(nightly_mock.call_args.args[-1], ["demo"])

    def test_not_called_again_same_day(self):
        state.write_nightly(self.paths, {"last_date": "2026-09-15"})
        with patch.object(D.due, "due_projects", return_value=[]), \
             patch.object(D.nightly, "run_nightly") as nightly_mock:
            D.tick(
                self.paths, failing_git, clock=lambda: 1000.0, sleep=lambda s: None,
                now_local=lambda: datetime(2026, 9, 15, 3, 5),
            )
        nightly_mock.assert_not_called()


class MissingScopeTest(BaseCase):
    def test_logs_and_syncs_nothing(self):
        self.paths.scope.unlink()
        with patch.object(D.runner, "sync_project") as sync_mock:
            D.tick(self.paths, object(), clock=lambda: 1000.0, sleep=lambda s: None, now_local=lambda: EARLY_MORNING)
        sync_mock.assert_not_called()
        self.assertIn("sync-scope missing", self.paths.log.read_text(encoding="utf-8"))


class InvalidProjectNameTest(BaseCase):
    def test_invalid_name_never_reaches_state_or_runner(self):
        make_git_repo(self.paths.specs / "demo")
        make_git_repo(self.paths.specs / "a..b")

        def echo_due_projects(projects, heads, states, markers, now):
            # Echo back whatever tick collected, so the assertion below proves due_projects
            # itself was only ever offered "demo", never the invalid "a..b".
            return list(projects)

        real_read_state = state.read_state

        def guarded_read_state(paths, project):
            self.assertNotEqual(project, "a..b")
            return real_read_state(paths, project)

        sync_calls = []

        def fake_sync(paths, project, run, clock, sleep, rules):
            sync_calls.append(project)
            return dict(state.EMPTY_STATE)

        with patch.object(D.due, "due_projects", side_effect=echo_due_projects), \
             patch.object(D.state, "read_state", side_effect=guarded_read_state), \
             patch.object(D.runner, "sync_project", side_effect=fake_sync):
            D.tick(self.paths, failing_git, clock=lambda: 1000.0, sleep=lambda s: None, now_local=lambda: EARLY_MORNING)
        self.assertEqual(sync_calls, ["demo"])


class LoopTest(BaseCase):
    def test_runs_tick_twice_sleeps_between_and_returns_on_interrupt(self):
        tick_calls = []
        sleep_calls = []

        def fake_tick(paths, run, clock, sleep, now_local):
            tick_calls.append(1)

        def fake_sleep(seconds):
            sleep_calls.append(seconds)
            if len(sleep_calls) >= 2:
                raise KeyboardInterrupt()

        with patch.object(D, "tick", side_effect=fake_tick):
            code = D.main(
                [], paths=self.paths, run=object(), clock=lambda: 1000.0,
                sleep=fake_sleep, now_local=lambda: EARLY_MORNING,
            )
        self.assertEqual(code, 0)
        self.assertEqual(len(tick_calls), 2)
        self.assertEqual(sleep_calls, [D.TICK, D.TICK])

    def test_raising_tick_does_not_stop_the_second_tick(self):
        tick_calls = []
        sleep_calls = []

        def fake_tick(paths, run, clock, sleep, now_local):
            tick_calls.append(1)
            if len(tick_calls) == 1:
                raise RuntimeError("tick boom")

        def fake_sleep(seconds):
            sleep_calls.append(seconds)
            if len(sleep_calls) >= 2:
                raise KeyboardInterrupt()

        with patch.object(D, "tick", side_effect=fake_tick):
            code = D.main(
                [], paths=self.paths, run=object(), clock=lambda: 1000.0,
                sleep=fake_sleep, now_local=lambda: EARLY_MORNING,
            )
        self.assertEqual(code, 0)
        self.assertEqual(len(tick_calls), 2)
        log_text = self.paths.log.read_text(encoding="utf-8")
        self.assertIn("tick boom", log_text)


class UsageTest(BaseCase):
    def test_bogus_arg_returns_2(self):
        self.assertEqual(D.main(["--bogus"]), 2)


class PhaseCrashResilienceTest(BaseCase):
    """A crash outside the per-project sync must never end the process (main keeps returning 0)."""

    def test_nightly_exception_does_not_crash_main(self):
        with patch.object(D.nightly, "run_nightly", side_effect=RuntimeError("nightly boom")):
            code = D.main(
                ["--once"], paths=self.paths, run=object(), clock=lambda: 1000.0,
                sleep=lambda s: None, now_local=lambda: datetime(2026, 9, 15, 3, 5),
            )
        self.assertEqual(code, 0)
        log_lines = self.paths.log.read_text(encoding="utf-8").splitlines()
        line = next(line for line in log_lines if "nightly" in line)
        _timestamp, rest = line.split(" ", 1)
        self.assertEqual(rest, "- failed nightly: RuntimeError('nightly boom')")

    def test_markers_exception_does_not_crash_main(self):
        make_git_repo(self.paths.specs / "demo")
        with patch.object(D.state, "markers", side_effect=RuntimeError("markers boom")):
            code = D.main(
                ["--once"], paths=self.paths, run=failing_git, clock=lambda: 1000.0,
                sleep=lambda s: None, now_local=lambda: EARLY_MORNING,
            )
        self.assertEqual(code, 0)
        self.assertIn("markers boom", self.paths.log.read_text(encoding="utf-8"))

    def test_list_projects_exception_does_not_crash_main(self):
        with patch.object(D.due, "list_projects", side_effect=RuntimeError("list boom")):
            code = D.main(
                ["--once"], paths=self.paths, run=object(), clock=lambda: 1000.0,
                sleep=lambda s: None, now_local=lambda: EARLY_MORNING,
            )
        self.assertEqual(code, 0)
        self.assertIn("list boom", self.paths.log.read_text(encoding="utf-8"))


class CleanupCrashResilienceTest(BaseCase):
    def test_cleanup_exception_does_not_stop_the_tick(self):
        tick_calls = []

        def fake_tick(paths, run, clock, sleep, now_local):
            tick_calls.append(1)

        with patch.object(D.mirror, "cleanup_stage", side_effect=OSError("cleanup boom")), \
             patch.object(D, "tick", side_effect=fake_tick):
            code = D.main(
                ["--once"], paths=self.paths, run=object(), clock=lambda: 1000.0,
                sleep=lambda s: None, now_local=lambda: EARLY_MORNING,
            )
        self.assertEqual(code, 0)
        self.assertEqual(tick_calls, [1])
        self.assertIn("cleanup boom", self.paths.log.read_text(encoding="utf-8"))


class CollectionFailureSkipsNightlyTest(BaseCase):
    def test_list_projects_exception_skips_nightly_this_tick(self):
        with patch.object(D.due, "list_projects", side_effect=RuntimeError("list boom")), \
             patch.object(D.nightly, "run_nightly") as nightly_mock:
            D.tick(
                self.paths, object(), clock=lambda: 1000.0, sleep=lambda s: None,
                now_local=lambda: datetime(2026, 9, 15, 3, 5),
            )
        nightly_mock.assert_not_called()
        self.assertIn("collection", self.paths.log.read_text(encoding="utf-8"))

    def test_collection_failure_then_healthy_tick_still_runs_nightly(self):
        make_git_repo(self.paths.specs / "demo")
        real_list_projects = D.due.list_projects
        calls = []

        def flaky_list_projects(specs):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("list boom")
            return real_list_projects(specs)

        with patch.object(D.due, "list_projects", side_effect=flaky_list_projects), \
             patch.object(D.nightly, "run_nightly") as nightly_mock:
            D.tick(
                self.paths, failing_git, clock=lambda: 1000.0, sleep=lambda s: None,
                now_local=lambda: datetime(2026, 9, 15, 3, 5),
            )
            nightly_mock.assert_not_called()
            D.tick(
                self.paths, failing_git, clock=lambda: 1001.0, sleep=lambda s: None,
                now_local=lambda: datetime(2026, 9, 15, 3, 6),
            )
        nightly_mock.assert_called_once()
        self.assertEqual(nightly_mock.call_args.args[-1], ["demo"])


class ScopeProblemDedupTest(BaseCase):
    def test_missing_scope_logged_once_across_ticks(self):
        self.paths.scope.unlink()
        D.tick(self.paths, object(), clock=lambda: 1000.0, sleep=lambda s: None, now_local=lambda: EARLY_MORNING)
        D.tick(self.paths, object(), clock=lambda: 1001.0, sleep=lambda s: None, now_local=lambda: EARLY_MORNING)
        lines = [
            line for line in self.paths.log.read_text(encoding="utf-8").splitlines()
            if "sync-scope missing" in line
        ]
        self.assertEqual(len(lines), 1)

    def test_logs_again_after_recovering(self):
        self.paths.scope.unlink()
        D.tick(self.paths, object(), clock=lambda: 1000.0, sleep=lambda s: None, now_local=lambda: EARLY_MORNING)
        self.paths.scope.write_text(SCOPE_TEXT, encoding="utf-8")
        D.tick(self.paths, object(), clock=lambda: 1001.0, sleep=lambda s: None, now_local=lambda: EARLY_MORNING)
        self.paths.scope.unlink()
        D.tick(self.paths, object(), clock=lambda: 1002.0, sleep=lambda s: None, now_local=lambda: EARLY_MORNING)
        lines = [
            line for line in self.paths.log.read_text(encoding="utf-8").splitlines()
            if "sync-scope missing" in line
        ]
        self.assertEqual(len(lines), 2)


if __name__ == "__main__":
    unittest.main()
