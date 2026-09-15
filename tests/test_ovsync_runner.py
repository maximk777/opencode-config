import importlib.machinery
import sys
import unittest
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "lib"))

import copy
import json
import os
import subprocess
import tempfile
from unittest.mock import patch

from ovsync import openviking as ov
from ovsync import runner, scope, state


def ok(stdout="", returncode=0, stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


def task_list_json(tasks):
    return json.dumps({"ok": True, "result": tasks})


def make_task(task_id, status, created_at, resource_id="viking://resources/demo/specs"):
    return {
        "task_id": task_id,
        "task_type": "add_resource",
        "status": status,
        "created_at": created_at,
        "updated_at": created_at,
        "resource_id": resource_id,
    }


class FakeClock:
    """Advances only when the fake sleep is called, matching the injected-clock contract."""

    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class FakeRun:
    """Dispatches on argv; records every argv and marker touches so tests can inspect mid-run state."""

    def __init__(self, paths=None, project=None):
        self.paths = paths
        self.project = project
        self.argv_log = []
        self.health_exit = 0
        self.add_resource_result = ok()
        self.add_resource_raises = None
        self.task_lists = []  # list of lists of task dicts, one per `ov task list` call, last repeats
        self.git_diff_stdout = ""
        self.git_diff_returncode = 0
        self.touch_marker_at = None  # (call_index_of_task_list, new_mtime)
        self._task_list_calls = 0
        self.inspect_add_resource = None  # callable(state_dict) run during add-resource
        self.task_list_fail = lambda idx: False  # predicate: this `ov task list` call fails
        self.git_diff_stderr = ""
        self.calls = []  # (argv, kwargs) for every invocation, so tests can inspect cwd etc.
        self.git_diff_by_range = None  # {"a..b": stdout}; any other range fails like git would

    def __call__(self, argv, **kwargs):
        self.argv_log.append(argv)
        self.calls.append((argv, kwargs))
        if argv[:4] == ["docker", "exec", "openviking", "ov"]:
            cmd = argv[4:]
            if cmd[:1] == ["health"]:
                return ok(returncode=self.health_exit)
            if cmd[:1] == ["add-resource"]:
                if self.inspect_add_resource is not None and self.paths is not None:
                    self.inspect_add_resource(state.read_state(self.paths, self.project))
                if self.add_resource_raises is not None:
                    raise self.add_resource_raises
                return self.add_resource_result
            if cmd[:2] == ["task", "list"]:
                idx = self._task_list_calls
                self._task_list_calls += 1
                if self.touch_marker_at is not None and self.touch_marker_at[0] == idx:
                    marker = self.paths.queue / self.project
                    marker.touch()
                    os.utime(marker, (self.touch_marker_at[1], self.touch_marker_at[1]))
                if self.task_list_fail(idx):
                    return ok(returncode=1, stderr="boom")
                tasks = self.task_lists[idx] if idx < len(self.task_lists) else (
                    self.task_lists[-1] if self.task_lists else []
                )
                return ok(task_list_json(tasks))
            raise AssertionError(f"unexpected ov argv {argv}")
        if argv[:2] == ["git", "diff"]:
            if self.git_diff_by_range is not None:
                if argv[-1] not in self.git_diff_by_range:
                    return ok(returncode=128, stderr=f"fatal: bad revision '{argv[-1]}'")
                return ok(self.git_diff_by_range[argv[-1]])
            return ok(self.git_diff_stdout, self.git_diff_returncode, self.git_diff_stderr)
        raise AssertionError(f"unexpected argv {argv}")


class RunnerTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.tmp = Path(self.tmpdir.name)
        self.paths = state.Paths(home=self.tmp, specs=self.tmp / "specs", repo=REPO)
        (self.paths.specs / "demo").mkdir(parents=True)
        self.rules = scope.parse((REPO / "openviking/sync-scope").read_text())
        self.clock = FakeClock(start=1000.0)
        self.head_patch = patch.object(runner.due, "head_info", return_value=("h2", 1000.0))
        self.head_patch.start()
        self.addCleanup(self.head_patch.stop)
        self.mirror_patch = patch.object(runner.mirror, "build_mirror", return_value=3)
        self.mirror_count = self.mirror_patch.start()
        self.addCleanup(self.mirror_patch.stop)

    def make_run(self):
        run = FakeRun(paths=self.paths, project="demo")
        return run

    def write_state(self, **overrides):
        data = copy.deepcopy(state.EMPTY_STATE)
        data.update(overrides)
        state.write_state(self.paths, "demo", data)
        return data

    def sync(self, run):
        return runner.sync_project(self.paths, "demo", run, self.clock, self.clock.sleep, self.rules)

    def test_success_records_ok_state_and_exact_import_command(self):
        self.write_state(synced_commit="h1", reindexed_commit="h1")
        run = self.make_run()
        run.task_lists = [
            [make_task("t1", "running", 999.0)],
            [make_task("t1", "completed", 999.0)],
        ]
        result = self.sync(run)

        self.assertEqual(result["result"], "ok")
        self.assertEqual(result["synced_commit"], "h2")
        self.assertEqual(result["files"], 3)
        self.assertFalse(result["running"])

        add_resource_argvs = [a for a in run.argv_log if "add-resource" in a]
        self.assertEqual(add_resource_argvs, [ov.import_cmd("demo")])
        self.assertFalse(any("rm" in a for a in run.argv_log))

        diff_calls = [c for c in run.calls if c[0][:2] == ["git", "diff"]]
        self.assertEqual(len(diff_calls), 1)
        diff_argv, diff_kwargs = diff_calls[0]
        self.assertEqual(diff_argv, ["git", "diff", "--name-only", "h1..h2"])
        self.assertEqual(diff_kwargs.get("cwd"), self.paths.specs / "demo")

    def test_cli_cut_off_still_completes(self):
        self.write_state(synced_commit="h1", reindexed_commit="h1")
        run = self.make_run()
        run.add_resource_result = ok(returncode=1, stderr="context deadline exceeded")
        run.task_lists = [
            [make_task("t1", "running", 999.0)],
            [make_task("t1", "completed", 999.0)],
        ]
        result = self.sync(run)
        self.assertEqual(result["result"], "ok")

    def test_add_resource_timeout_expired_then_completed(self):
        self.write_state(synced_commit="h1", reindexed_commit="h1")
        run = self.make_run()
        run.add_resource_raises = subprocess.TimeoutExpired(cmd="ov add-resource", timeout=120)
        run.task_lists = [
            [make_task("t1", "running", 999.0)],
            [make_task("t1", "completed", 999.0)],
        ]
        result = self.sync(run)
        self.assertEqual(result["result"], "ok")

    def test_pending_dirs_merged_with_existing(self):
        self.write_state(synced_commit="h1", reindexed_commit="h1", reindex_pending=["existing/dir"])
        run = self.make_run()
        run.task_lists = [[make_task("t1", "completed", 999.0)]]
        run.git_diff_stdout = "architecture/adr/005.md\nopenspec/changes/x/decisions.md\n"
        result = self.sync(run)
        self.assertEqual(result["result"], "ok")
        self.assertEqual(
            result["reindex_pending"],
            ["architecture/adr", "existing/dir", "openspec/changes/x"],
        )

    def test_first_run_keeps_reindex_pending_empty_and_sets_reindexed_commit(self):
        self.write_state(synced_commit=None, reindexed_commit=None)
        run = self.make_run()
        run.task_lists = [[make_task("t1", "completed", 999.0)]]
        result = self.sync(run)
        self.assertEqual(result["reindex_pending"], [])
        self.assertEqual(result["reindexed_commit"], "h2")
        self.assertFalse(any(a[:2] == ["git", "diff"] for a in run.argv_log))

    def test_diff_range_starts_at_synced_commit_not_reindexed_commit(self):
        self.write_state(synced_commit="h1", reindexed_commit="h0")
        run = self.make_run()
        run.task_lists = [[make_task("t1", "completed", 999.0)]]
        run.git_diff_by_range = {"h1..h2": "architecture/adr/005.md\n"}
        result = self.sync(run)

        diff_calls = [c for c in run.calls if c[0][:2] == ["git", "diff"]]
        self.assertEqual([c[0] for c in diff_calls], [["git", "diff", "--name-only", "h1..h2"]])
        self.assertEqual(diff_calls[0][1].get("cwd"), self.paths.specs / "demo")
        self.assertEqual(result["reindex_pending"], ["architecture/adr"])
        self.assertEqual(result["reindexed_commit"], "h0")

    def test_reindexed_directory_is_not_added_again_by_the_next_range(self):
        self.write_state(synced_commit="h1", reindexed_commit="h0")
        run = self.make_run()
        run.task_lists = [[make_task("t1", "completed", 999.0)]]
        run.git_diff_by_range = {
            "h1..h2": "architecture/adr/005.md\n",
            "h2..h3": "architecture/backlog/y.md\n",
        }
        self.assertEqual(self.sync(run)["reindex_pending"], ["architecture/adr"])

        # The nightly reindexed architecture/adr, emptied the list and advanced reindexed_commit.
        st = state.read_state(self.paths, "demo")
        st["reindex_pending"] = []
        st["reindexed_commit"] = st["synced_commit"]
        state.write_state(self.paths, "demo", st)

        run2 = self.make_run()
        run2.task_lists = [[make_task("t2", "completed", 999.0)]]
        run2.git_diff_by_range = run.git_diff_by_range
        with patch.object(runner.due, "head_info", return_value=("h3", 1000.0)):
            result = self.sync(run2)

        self.assertEqual(result["result"], "ok")
        self.assertEqual(result["synced_commit"], "h3")
        self.assertEqual(result["reindex_pending"], ["architecture/backlog"])
        self.assertEqual(
            [c[0] for c in run2.calls if c[0][:2] == ["git", "diff"]],
            [["git", "diff", "--name-only", "h2..h3"]],
        )

    def test_marker_at_run_start_is_removed(self):
        self.write_state(synced_commit="h1", reindexed_commit="h1")
        state.touch_marker(self.paths, "demo", now=self.clock.now)
        run = self.make_run()
        run.task_lists = [[make_task("t1", "completed", 999.0)]]
        self.sync(run)
        self.assertIsNone(state.marker_mtime(self.paths, "demo"))

    def test_marker_touched_during_poll_survives(self):
        self.write_state(synced_commit="h1", reindexed_commit="h1")
        state.touch_marker(self.paths, "demo", now=self.clock.now)
        run = self.make_run()
        run.task_lists = [
            [make_task("t1", "running", 999.0)],
            [make_task("t1", "completed", 999.0)],
        ]
        run.touch_marker_at = (1, self.clock.now + 500.0)
        self.sync(run)
        self.assertIsNotNone(state.marker_mtime(self.paths, "demo"))

    def test_empty_mirror_is_skipped(self):
        self.mirror_count.return_value = 0
        self.write_state(synced_commit="h1", reindexed_commit="h1")
        state.touch_marker(self.paths, "demo", now=self.clock.now - 100.0)
        run = self.make_run()
        result = self.sync(run)
        self.assertEqual(result["result"], "skipped")
        self.assertEqual(result["error"], "empty selection")
        self.assertEqual(result["synced_commit"], "h2")
        self.assertFalse(any("add-resource" in a for a in run.argv_log))
        self.assertIsNone(state.marker_mtime(self.paths, "demo"))

    def test_git_error_skips_with_reason(self):
        self.head_patch.stop()
        self.head_patch = patch.object(runner.due, "head_info", return_value=None)
        self.head_patch.start()
        run = self.make_run()
        result = self.sync(run)
        self.assertEqual(result["result"], "skipped")
        self.assertTrue(result["error"].startswith("git"))
        self.assertEqual(result["next_attempt"], self.clock.now + 300)
        self.assertFalse(any(a[:4] == ["docker", "exec", "openviking", "ov"] for a in run.argv_log))

    def test_health_failure_marks_unavailable(self):
        self.write_state(synced_commit="h1", reindexed_commit="h1")
        state.touch_marker(self.paths, "demo", now=self.clock.now)
        run = self.make_run()
        run.health_exit = 1
        result = self.sync(run)
        self.assertEqual(result["result"], "unavailable")
        self.assertEqual(result["unavailable_since"], self.clock.now)
        self.assertEqual(result["next_attempt"], self.clock.now + 60)
        self.assertIsNotNone(state.marker_mtime(self.paths, "demo"))
        self.assertFalse(any("add-resource" in a for a in run.argv_log))

    def test_add_resource_file_not_found_is_unavailable(self):
        self.write_state(synced_commit="h1", reindexed_commit="h1")
        run = self.make_run()
        run.add_resource_raises = FileNotFoundError()
        result = self.sync(run)
        self.assertEqual(result["result"], "unavailable")

    def test_add_resource_conflict_is_locked(self):
        self.write_state(synced_commit="h1", reindexed_commit="h1")
        state.touch_marker(self.paths, "demo", now=self.clock.now)
        run = self.make_run()
        run.add_resource_result = ok(returncode=1, stderr="[CONFLICT] lock acquire timed out")
        result = self.sync(run)
        self.assertEqual(result["result"], "locked")
        self.assertEqual(result["next_attempt"], self.clock.now + 30)
        self.assertIsNotNone(state.marker_mtime(self.paths, "demo"))
        self.assertFalse(any(a[4:6] == ["task", "list"] for a in run.argv_log))

    def test_three_failed_tasks_marks_failing(self):
        for i in range(3):
            run = self.make_run()
            run.task_lists = [[make_task(f"t{i}", "failed", 999.0)]]
            result = self.sync(run)
            self.assertEqual(result["result"], "failed")
        self.assertTrue(result["failing"])
        self.assertEqual(result["failures"], 3)

    def test_no_task_appears_records_failed_with_cli_text(self):
        self.write_state(synced_commit="h1", reindexed_commit="h1")
        run = self.make_run()
        run.add_resource_result = ok(returncode=1, stderr="Local path does not exist")
        run.task_lists = [[]]
        result = self.sync(run)
        self.assertEqual(result["result"], "failed")
        self.assertIn("Local path does not exist", result["error"])

    def test_task_timeout_then_blocks_then_resolves(self):
        self.write_state(synced_commit="h1", reindexed_commit="h1")
        run = self.make_run()
        run.task_lists = [[make_task("t1", "running", 999.0)]]

        def jump_past_timeout(seconds):
            # Only one poll happens before the timeout fires, so a single big jump suffices.
            self.clock.now += runner.TASK_TIMEOUT + 1

        result = runner.sync_project(self.paths, "demo", run, self.clock, jump_past_timeout, self.rules)
        self.assertEqual(result["result"], "timeout")
        self.assertEqual(result["pending_task"], {"task_id": "t1", "created_at": 999.0})

        blocked_now = self.clock.now
        run2 = self.make_run()
        run2.task_lists = [[make_task("t1", "running", 999.0)]]
        result2 = runner.sync_project(self.paths, "demo", run2, self.clock, self.clock.sleep, self.rules)
        self.assertFalse(any("add-resource" in a for a in run2.argv_log))
        self.assertEqual(result2["result"], "timeout")
        self.assertEqual(result2["pending_task"], {"task_id": "t1", "created_at": 999.0})
        self.assertEqual(result2["next_attempt"], blocked_now + 60)
        self.assertIn("blocked by pending task t1", self.paths.log.read_text())

        run3 = self.make_run()
        run3.task_lists = [
            [make_task("t1", "completed", 999.0)],
            [make_task("t2", "completed", 10 ** 9)],
        ]
        result3 = runner.sync_project(self.paths, "demo", run3, self.clock, self.clock.sleep, self.rules)
        self.assertTrue(any("add-resource" in a for a in run3.argv_log))
        self.assertIsNone(result3["pending_task"])
        self.assertEqual(result3["result"], "ok")

    def test_running_state_visible_during_the_run(self):
        self.write_state(synced_commit="h1", reindexed_commit="h1")
        run = self.make_run()
        run.task_lists = [[make_task("t1", "completed", 999.0)]]
        seen = {}

        def inspect(st):
            seen["running"] = st["running"]
            seen["started_at"] = st["started_at"]

        run.inspect_add_resource = inspect
        self.sync(run)
        self.assertTrue(seen["running"])
        self.assertEqual(seen["started_at"], 1000.0)

    def test_log_gets_one_line_per_run(self):
        self.write_state(synced_commit="h1", reindexed_commit="h1")
        run = self.make_run()
        run.task_lists = [[make_task("t1", "completed", 999.0)]]
        self.sync(run)
        log_text = self.paths.log.read_text()
        self.assertIn("demo", log_text)
        self.assertIn("ok", log_text)
        self.assertEqual(len(log_text.splitlines()), 1)

    def test_one_failed_poll_after_the_task_was_seen_does_not_end_the_wait(self):
        self.write_state(synced_commit="h1", reindexed_commit="h1")
        run = self.make_run()
        run.task_lists = [[make_task("t1", "running", 999.0)], [make_task("t1", "completed", 999.0)]]
        run.task_list_fail = lambda idx: idx == 1  # the poll right after the task was seen fails once
        result = self.sync(run)
        self.assertEqual(result["result"], "ok")

    def test_polls_failing_after_the_task_was_seen_time_out_using_the_last_sighting(self):
        self.write_state(synced_commit="h1", reindexed_commit="h1")
        run = self.make_run()
        run.task_lists = [[make_task("t1", "running", 999.0)]]
        run.task_list_fail = lambda idx: idx >= 1  # every poll after the first (successful) one fails

        def jump_past_timeout(seconds):
            self.clock.now += runner.TASK_TIMEOUT + 1

        result = runner.sync_project(self.paths, "demo", run, self.clock, jump_past_timeout, self.rules)
        self.assertEqual(result["result"], "timeout")
        self.assertEqual(result["pending_task"], {"task_id": "t1", "created_at": 999.0})

    def test_pending_task_check_reports_unavailable_when_task_list_fails(self):
        self.write_state(pending_task={"task_id": "t1", "created_at": 999.0}, result="timeout")
        run = self.make_run()
        run.task_list_fail = lambda idx: True
        result = self.sync(run)
        self.assertEqual(result["result"], "unavailable")
        self.assertEqual(result["pending_task"], {"task_id": "t1", "created_at": 999.0})
        self.assertFalse(any("add-resource" in a for a in run.argv_log))

    def test_mirror_runtime_error_is_a_git_skip_and_clears_running(self):
        self.write_state(synced_commit="h1", reindexed_commit="h1")
        run = self.make_run()
        with patch.object(runner.mirror, "build_mirror", side_effect=RuntimeError("git ls-tree failed: boom")):
            result = self.sync(run)
        self.assertEqual(result["result"], "skipped")
        self.assertTrue(result["error"].startswith("git:"))
        self.assertFalse(result["running"])

    def test_mirror_os_error_is_a_mirror_skip_and_clears_running(self):
        self.write_state(synced_commit="h1", reindexed_commit="h1")
        run = self.make_run()
        with patch.object(runner.mirror, "build_mirror", side_effect=OSError("disk full")):
            result = self.sync(run)
        self.assertEqual(result["result"], "skipped")
        self.assertTrue(result["error"].startswith("mirror:"))
        self.assertFalse(result["running"])

    def test_git_diff_failure_keeps_ok_but_leaves_reindex_state_untouched(self):
        self.write_state(synced_commit="h1", reindexed_commit="h1", reindex_pending=["existing/dir"])
        run = self.make_run()
        run.task_lists = [[make_task("t1", "completed", 999.0)]]
        run.git_diff_returncode = 1
        run.git_diff_stderr = "fatal: bad revision 'h1..h2'"
        result = self.sync(run)
        self.assertEqual(result["result"], "ok")
        self.assertEqual(result["reindexed_commit"], "h1")
        self.assertEqual(result["reindex_pending"], ["existing/dir"])
        self.assertIn("git diff failed", self.paths.log.read_text())


if __name__ == "__main__":
    unittest.main()
