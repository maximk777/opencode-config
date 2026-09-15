import importlib.machinery
import sys
import unittest
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "lib"))

import copy
import json
import re
import subprocess
import tempfile
from datetime import datetime, timedelta
from unittest import mock

from ovsync import nightly, scope, state

FIXTURE_MODELS = json.loads((REPO / "tests/fixtures/ov_observer_models.json").read_text())
FIXTURE_RETRIEVAL_TEXT = (REPO / "tests/fixtures/ov_observer_retrieval.json").read_text()
TASK_LIST_EMPTY = json.dumps({"ok": True, "result": []})


def models_stdout(vlm_calls: int) -> str:
    """Fixture 'observer models' JSON with the deepseek-flash Calls column rewritten."""
    data = copy.deepcopy(FIXTURE_MODELS)
    status = data["result"]["status"]
    status = re.sub(
        r"(\|\s*deepseek-flash\s*\|\s*\S+\s*\|\s*)\d+(\s*\|)",
        rf"\g<1>{vlm_calls}\g<2>",
        status,
    )
    data["result"]["status"] = status
    return json.dumps(data)


def ok(stdout: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess([], 0, stdout, "")


class FakeRun:
    """Dispatches on argv; a 'reindex' call is always recorded as attempted, even on a raise or exit 1."""

    def __init__(self, start_vlm: int = 100, step: int = 5):
        self.vlm = start_vlm
        self.step = step
        self.attempted: list = []
        self.reindex_exit = {}
        self.reindex_raises = {}
        self.reindex_delta = {}

    def __call__(self, argv, **kwargs):
        cmd = argv[4:]
        if cmd[:2] == ["observer", "models"]:
            return ok(models_stdout(self.vlm))
        if cmd[:2] == ["observer", "retrieval"]:
            return ok(FIXTURE_RETRIEVAL_TEXT)
        if cmd[:2] == ["task", "list"]:
            return ok(TASK_LIST_EMPTY)
        if cmd[0] == "reindex":
            directory = cmd[1].split("/specs/", 1)[1]
            self.attempted.append(directory)
            self.vlm += self.reindex_delta.get(directory, self.step)
            if directory in self.reindex_raises:
                raise self.reindex_raises[directory]
            return subprocess.CompletedProcess(argv, self.reindex_exit.get(directory, 0), "", "")
        raise AssertionError(f"unexpected argv {argv}")


def unavailable_run(argv, **kwargs):
    if argv[4:6] == ["observer", "models"]:
        return subprocess.CompletedProcess(argv, 1, "", "boom")
    raise AssertionError(f"unexpected argv {argv}")


def retrieval_none_run(argv, **kwargs):
    cmd = argv[4:]
    if cmd[:2] == ["observer", "models"]:
        return ok(models_stdout(100))
    if cmd[:2] == ["observer", "retrieval"]:
        return subprocess.CompletedProcess(argv, 1, "", "boom")
    if cmd[:2] == ["task", "list"]:
        return ok(TASK_LIST_EMPTY)
    raise AssertionError(f"unexpected argv {argv}")


def tasks_none_run(argv, **kwargs):
    cmd = argv[4:]
    if cmd[:2] == ["observer", "models"]:
        return ok(models_stdout(100))
    if cmd[:2] == ["observer", "retrieval"]:
        return ok(FIXTURE_RETRIEVAL_TEXT)
    if cmd[:2] == ["task", "list"]:
        return subprocess.CompletedProcess(argv, 1, "", "boom")
    raise AssertionError(f"unexpected argv {argv}")


class BusyThenIdleRun:
    """Simulates a queue occupied by other work, then freed for a retried second run."""

    def __init__(self, start_vlm: int = 100, step: int = 5):
        self.busy = True
        self.vlm = start_vlm
        self.step = step
        self.attempted: list = []

    def __call__(self, argv, **kwargs):
        cmd = argv[4:]
        if cmd[:2] == ["observer", "models"]:
            return ok(models_stdout(self.vlm))
        if cmd[:2] == ["observer", "retrieval"]:
            return ok(FIXTURE_RETRIEVAL_TEXT)
        if cmd[:2] == ["task", "list"]:
            if self.busy:
                busy_list = json.dumps({"ok": True, "result": [{"task_id": "t", "status": "running"}]})
                return ok(busy_list)
            return ok(TASK_LIST_EMPTY)
        if cmd[0] == "reindex":
            directory = cmd[1].split("/specs/", 1)[1]
            self.attempted.append(directory)
            self.vlm += self.step
            return subprocess.CompletedProcess(argv, 0, "", "")
        raise AssertionError(f"unexpected argv {argv}")


class RisingDuringWaitRun:
    """The initial queue-idle wait takes one retry cycle; other work bumps the counter meanwhile."""

    def __init__(self):
        self.vlm = 100
        self.polls = 0
        self.attempted: list = []

    def __call__(self, argv, **kwargs):
        cmd = argv[4:]
        if cmd[:2] == ["observer", "models"]:
            return ok(models_stdout(self.vlm))
        if cmd[:2] == ["observer", "retrieval"]:
            return ok(FIXTURE_RETRIEVAL_TEXT)
        if cmd[:2] == ["task", "list"]:
            self.polls += 1
            if self.polls == 2:  # the initial wait's first poll: other work is still running
                self.vlm += 20
                busy = json.dumps({"ok": True, "result": [{"task_id": "t", "status": "running"}]})
                return ok(busy)
            return ok(TASK_LIST_EMPTY)
        if cmd[0] == "reindex":
            directory = cmd[1].split("/specs/", 1)[1]
            self.attempted.append(directory)
            self.vlm += 5
            return subprocess.CompletedProcess(argv, 0, "", "")
        raise AssertionError(f"unexpected argv {argv}")


class BusyAfterFirstReindexRun:
    """Idle for the initial gate, then permanently busy so the post-attempt wait_idle times out."""

    def __init__(self, start_vlm: int = 100, step: int = 5):
        self.vlm = start_vlm
        self.step = step
        self.attempted: list = []
        self.reindex_started = False

    def __call__(self, argv, **kwargs):
        cmd = argv[4:]
        if cmd[:2] == ["observer", "models"]:
            return ok(models_stdout(self.vlm))
        if cmd[:2] == ["observer", "retrieval"]:
            return ok(FIXTURE_RETRIEVAL_TEXT)
        if cmd[:2] == ["task", "list"]:
            if self.reindex_started:
                busy = json.dumps({"ok": True, "result": [{"task_id": "t", "status": "running"}]})
                return ok(busy)
            return ok(TASK_LIST_EMPTY)
        if cmd[0] == "reindex":
            directory = cmd[1].split("/specs/", 1)[1]
            self.attempted.append(directory)
            self.vlm += self.step
            self.reindex_started = True
            return subprocess.CompletedProcess(argv, 0, "", "")
        raise AssertionError(f"unexpected argv {argv}")


class DeferredCostRun(FakeRun):
    """Reindexing `slow` leaves the queue busy and its VLM cost unspent until `finish()`."""

    def __init__(self, slow: str, start_vlm: int = 100, step: int = 30):
        super().__init__(start_vlm=start_vlm, step=step)
        self.slow = slow
        self.busy = False
        self.unfinished = 0

    def __call__(self, argv, **kwargs):
        cmd = argv[4:]
        if cmd[:2] == ["task", "list"] and self.busy:
            return ok(json.dumps({"ok": True, "result": [{"task_id": "t", "status": "running"}]}))
        if cmd and cmd[0] == "reindex" and cmd[1].split("/specs/", 1)[1] == self.slow:
            self.attempted.append(self.slow)
            self.busy = True
            self.unfinished += self.step
            return subprocess.CompletedProcess(argv, 0, "", "")
        return super().__call__(argv, **kwargs)

    def finish(self):
        self.vlm += self.unfinished
        self.unfinished = 0
        self.busy = False


class PendingDirsTests(unittest.TestCase):
    def setUp(self):
        self.rules = scope.parse((REPO / "openviking/sync-scope").read_text())

    def test_architecture_and_decisions_directories(self):
        changed = [
            "architecture/adr/005.md",
            "openspec/changes/x/decisions.md",
            "openspec/changes/x/design.md",
            "harness/gates.md",
        ]
        self.assertEqual(
            nightly.pending_dirs(changed, self.rules),
            ["architecture/adr", "openspec/changes/x"],
        )

    def test_unscoped_path_ignored_even_if_named_decisions(self):
        changed = ["mockups/decisions.md"]
        self.assertEqual(nightly.pending_dirs(changed, self.rules), [])


class MergePendingTests(unittest.TestCase):
    def test_dedupes_and_sorts(self):
        self.assertEqual(nightly.merge_pending(["b", "a"], ["a", "c"]), ["a", "b", "c"])


class IsDueTests(unittest.TestCase):
    def test_before_3am_not_due(self):
        self.assertFalse(nightly.is_due({"last_date": None}, datetime(2026, 9, 15, 2, 59)))

    def test_at_3am_due(self):
        self.assertTrue(nightly.is_due({"last_date": None}, datetime(2026, 9, 15, 3, 0)))

    def test_already_ran_today_not_due(self):
        self.assertFalse(nightly.is_due({"last_date": "2026-09-15"}, datetime(2026, 9, 15, 23, 0)))

    def test_new_day_due(self):
        self.assertTrue(nightly.is_due({"last_date": "2026-09-15"}, datetime(2026, 9, 16, 9, 0)))

    def test_retry_after_blocks_until_elapsed(self):
        retry_at = datetime(2026, 9, 15, 3, 30).timestamp()
        nightly_state = {"last_date": None, "retry_after": retry_at}
        self.assertFalse(nightly.is_due(nightly_state, datetime(2026, 9, 15, 3, 10)))
        self.assertTrue(nightly.is_due(nightly_state, datetime(2026, 9, 15, 3, 31)))

    def test_non_numeric_retry_after_is_treated_as_none(self):
        nightly_state = {"last_date": None, "retry_after": "not-a-number"}
        self.assertTrue(nightly.is_due(nightly_state, datetime(2026, 9, 15, 3, 0)))


class CountFilesTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.root = Path(self.tmpdir.name)

    def test_counts_recursively(self):
        target = self.root / "demo" / "architecture" / "adr"
        target.mkdir(parents=True)
        (target / "a.md").write_text("a")
        (target / "sub").mkdir()
        (target / "sub" / "b.md").write_text("b")
        self.assertEqual(nightly.count_files(self.root / "demo", "architecture/adr"), 2)

    def test_missing_directory_counts_zero(self):
        self.assertEqual(nightly.count_files(self.root / "demo", "architecture/adr"), 0)


class PlanTests(unittest.TestCase):
    def test_boundary_exact_cap(self):
        chosen, rest = nightly.plan(
            ["architecture", "architecture/adr", "architecture/backlog/x"],
            {"architecture": 2, "architecture/adr": 8, "architecture/backlog/x": 12},
            cap=60,
        )
        self.assertEqual(chosen, ["architecture/backlog/x", "architecture/adr"])
        self.assertEqual(rest, ["architecture"])

    def test_big_directory_skipped_smaller_one_still_chosen(self):
        chosen, rest = nightly.plan(
            ["x/big", "x/small"],
            {"x/big": 30, "x/small": 5},
            cap=60,
        )
        self.assertEqual(chosen, ["x/small"])
        self.assertEqual(rest, ["x/big"])


class WaitIdleTests(unittest.TestCase):
    def test_true_when_queue_already_empty(self):
        run = mock.Mock(return_value=ok(TASK_LIST_EMPTY))
        clock = mock.Mock(return_value=0.0)
        sleep = mock.Mock()
        self.assertTrue(nightly.wait_idle(run, clock, sleep, timeout=100.0))
        sleep.assert_not_called()

    def test_false_on_timeout_when_task_stays_running(self):
        busy = json.dumps({"ok": True, "result": [{"task_id": "t", "status": "running"}]})
        run = mock.Mock(return_value=ok(busy))
        clocks = [0.0, 5.0, 200.0]
        clock = mock.Mock(side_effect=clocks)
        sleep = mock.Mock()
        self.assertFalse(nightly.wait_idle(run, clock, sleep, timeout=100.0))


class SnapshotTests(unittest.TestCase):
    def test_normal_snapshot(self):
        run = FakeRun(start_vlm=100)
        snap = nightly.snapshot(run, "2026-09-15")
        self.assertEqual(snap["date"], "2026-09-15")
        self.assertEqual(snap["vlm_calls"], 100)
        self.assertEqual(snap["embedding_calls"], 3804)
        self.assertEqual(snap["retrieval_queries"], 123)
        self.assertEqual(snap["add_resource_tasks"], 0)

    def test_models_none_gives_unavailable(self):
        snap = nightly.snapshot(unavailable_run, "2026-09-15")
        self.assertEqual(snap, {"date": "2026-09-15", "unavailable": True})

    def test_retrieval_none_gives_unavailable(self):
        snap = nightly.snapshot(retrieval_none_run, "2026-09-15")
        self.assertEqual(snap, {"date": "2026-09-15", "unavailable": True})

    def test_tasks_none_gives_unavailable(self):
        snap = nightly.snapshot(tasks_none_run, "2026-09-15")
        self.assertEqual(snap, {"date": "2026-09-15", "unavailable": True})


class RunNightlyTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.tmp = Path(self.tmpdir.name)
        self.paths = state.Paths(home=self.tmp, specs=self.tmp / "specs", repo=REPO)
        self.now = datetime(2026, 9, 15, 3, 0)

    def usage_lines(self):
        return [json.loads(line) for line in self.paths.usage.read_text().splitlines()]

    def snapshot_lines(self):
        return [line for line in self.usage_lines() if "vlm_calls" in line]

    def write_project_state(self, project, **overrides):
        data = copy.deepcopy(state.EMPTY_STATE)
        data.update(overrides)
        state.write_state(self.paths, project, data)
        return data

    def make_mirror_files(self, project, directory, count):
        target = self.paths.stage / project / directory
        target.mkdir(parents=True, exist_ok=True)
        for i in range(count):
            (target / f"f{i}.md").write_text("x")

    def test_both_directories_reindexed_and_commit_advances(self):
        self.write_project_state(
            "demo",
            reindex_pending=["architecture/adr", "architecture/backlog"],
            synced_commit="s2",
            reindexed_commit="s1",
        )
        self.make_mirror_files("demo", "architecture/adr", 2)
        self.make_mirror_files("demo", "architecture/backlog", 2)
        run = FakeRun(start_vlm=100, step=5)

        summary = nightly.run_nightly(
            self.paths, run, clock=lambda: 0.0, sleep=lambda s: None,
            now_local=lambda: self.now, projects=["demo"],
        )

        self.assertFalse(summary["unavailable"])
        self.assertEqual(sorted(run.attempted), ["architecture/adr", "architecture/backlog"])
        st = state.read_state(self.paths, "demo")
        self.assertEqual(st["reindex_pending"], [])
        self.assertEqual(st["reindexed_commit"], "s2")
        lines = self.usage_lines()
        self.assertEqual(lines[0]["vlm_calls"], 100)
        self.assertEqual(lines[-1], {"date": "2026-09-15", "reindex_vlm": 10})
        nightly_state = state.read_nightly(self.paths)
        self.assertEqual(nightly_state["last_date"], "2026-09-15")

    def test_actual_cost_stop_leaves_remainder_pending(self):
        self.write_project_state(
            "demo",
            reindex_pending=["a", "b", "c"],
            synced_commit="s2",
            reindexed_commit=None,
        )
        for d in ("a", "b", "c"):
            self.make_mirror_files("demo", d, 1)
        run = FakeRun(start_vlm=100, step=50)

        nightly.run_nightly(
            self.paths, run, clock=lambda: 0.0, sleep=lambda s: None,
            now_local=lambda: self.now, projects=["demo"],
        )

        self.assertEqual(run.attempted, ["a", "b"])
        st = state.read_state(self.paths, "demo")
        self.assertEqual(st["reindex_pending"], ["c"])
        self.assertIsNone(st["reindexed_commit"])
        lines = self.usage_lines()
        self.assertEqual(lines[-1], {"date": "2026-09-15", "reindex_vlm": 100})

    def test_failed_attempts_still_count_toward_the_actual_stop(self):
        # "a" times out client-side but the server still burns VLM calls; "b" succeeds and
        # crosses the 80 threshold; "c" is never attempted.
        self.write_project_state(
            "demo",
            reindex_pending=["a", "b", "c"],
            synced_commit="s2",
            reindexed_commit=None,
        )
        for d in ("a", "b", "c"):
            self.make_mirror_files("demo", d, 1)
        run = FakeRun(start_vlm=100)
        run.reindex_raises["a"] = subprocess.TimeoutExpired(cmd="ov reindex", timeout=120)
        run.reindex_delta = {"a": 50, "b": 40, "c": 999}

        nightly.run_nightly(
            self.paths, run, clock=lambda: 0.0, sleep=lambda s: None,
            now_local=lambda: self.now, projects=["demo"],
        )

        self.assertEqual(run.attempted, ["a", "b"])
        st = state.read_state(self.paths, "demo")
        self.assertEqual(st["reindex_pending"], ["a", "c"])
        self.assertIsNone(st["reindexed_commit"])
        lines = self.usage_lines()
        self.assertEqual(lines[-1], {"date": "2026-09-15", "reindex_vlm": 90})

    def test_nonzero_exit_keeps_pending_but_still_counts_delta(self):
        self.write_project_state(
            "demo",
            reindex_pending=["architecture/adr"],
            synced_commit="s2",
            reindexed_commit=None,
        )
        self.make_mirror_files("demo", "architecture/adr", 1)
        run = FakeRun(start_vlm=100, step=7)
        run.reindex_exit["architecture/adr"] = 1

        nightly.run_nightly(
            self.paths, run, clock=lambda: 0.0, sleep=lambda s: None,
            now_local=lambda: self.now, projects=["demo"],
        )

        self.assertEqual(run.attempted, ["architecture/adr"])
        st = state.read_state(self.paths, "demo")
        self.assertEqual(st["reindex_pending"], ["architecture/adr"])
        self.assertIsNone(st["reindexed_commit"])
        lines = self.usage_lines()
        self.assertEqual(lines[-1], {"date": "2026-09-15", "reindex_vlm": 7})

    def test_timeout_keeps_directory_pending(self):
        self.write_project_state(
            "demo",
            reindex_pending=["architecture/adr"],
            synced_commit="s2",
            reindexed_commit=None,
        )
        self.make_mirror_files("demo", "architecture/adr", 1)
        run = FakeRun(start_vlm=100, step=5)
        run.reindex_raises["architecture/adr"] = subprocess.TimeoutExpired(cmd="ov reindex", timeout=120)

        nightly.run_nightly(
            self.paths, run, clock=lambda: 0.0, sleep=lambda s: None,
            now_local=lambda: self.now, projects=["demo"],
        )

        st = state.read_state(self.paths, "demo")
        self.assertEqual(st["reindex_pending"], ["architecture/adr"])
        self.assertIsNone(st["reindexed_commit"])

    def test_vlm_counter_unavailable_after_attempt_stops_the_night(self):
        self.write_project_state(
            "demo",
            reindex_pending=["a", "b"],
            synced_commit="s2",
            reindexed_commit=None,
        )
        for d in ("a", "b"):
            self.make_mirror_files("demo", d, 1)
        run = FakeRun(start_vlm=100, step=5)
        real_call = run.__call__

        calls = {"n": 0}

        def flaky(argv, **kwargs):
            cmd = argv[4:]
            if cmd[:2] == ["observer", "models"]:
                calls["n"] += 1
                # call 1: snapshot; call 2: baseline right after the initial wait_idle;
                # call 3: the read right after the first reindex attempt.
                if calls["n"] == 3:
                    return subprocess.CompletedProcess(argv, 1, "", "boom")
            return real_call(argv, **kwargs)

        nightly.run_nightly(
            self.paths, flaky, clock=lambda: 0.0, sleep=lambda s: None,
            now_local=lambda: self.now, projects=["demo"],
        )

        st = state.read_state(self.paths, "demo")
        self.assertEqual(st["reindex_pending"], ["a", "b"])
        self.assertIsNone(st["reindexed_commit"])
        log_text = self.paths.log.read_text()
        self.assertIn("demo failed vlm counter unavailable, reindex stopped", log_text)
        lines = self.usage_lines()
        self.assertEqual(lines[-1], {"date": "2026-09-15", "reindex_vlm": 0, "partial": True})

    def test_unavailable_skips_reindex_but_records_snapshot_and_date(self):
        self.write_project_state(
            "demo",
            reindex_pending=["architecture/adr"],
            synced_commit="s2",
            reindexed_commit=None,
        )
        self.make_mirror_files("demo", "architecture/adr", 1)

        summary = nightly.run_nightly(
            self.paths, unavailable_run, clock=lambda: 0.0, sleep=lambda s: None,
            now_local=lambda: self.now, projects=["demo"],
        )

        self.assertTrue(summary["unavailable"])
        lines = self.usage_lines()
        self.assertEqual(lines, [{"date": "2026-09-15", "unavailable": True}])
        st = state.read_state(self.paths, "demo")
        self.assertEqual(st["reindex_pending"], ["architecture/adr"])
        nightly_state = state.read_nightly(self.paths)
        self.assertEqual(nightly_state["last_date"], "2026-09-15")

    def test_estimate_cap_is_shared_across_projects_in_name_order(self):
        self.write_project_state("p1", reindex_pending=["big"], synced_commit="s1", reindexed_commit=None)
        self.write_project_state("p2", reindex_pending=["small"], synced_commit="s1", reindexed_commit=None)
        self.make_mirror_files("p1", "big", 15)   # estimate 45
        self.make_mirror_files("p2", "small", 10)  # estimate 30, leaves only 15 of cap for p2
        run = FakeRun(start_vlm=100, step=1)

        nightly.run_nightly(
            self.paths, run, clock=lambda: 0.0, sleep=lambda s: None,
            now_local=lambda: self.now, projects=["p2", "p1"],
        )

        self.assertEqual(run.attempted, ["big"])
        p1 = state.read_state(self.paths, "p1")
        p2 = state.read_state(self.paths, "p2")
        self.assertEqual(p1["reindex_pending"], [])
        self.assertEqual(p2["reindex_pending"], ["small"])

    def test_baseline_is_read_after_the_initial_wait_not_from_the_snapshot(self):
        self.write_project_state(
            "demo",
            reindex_pending=["architecture/adr"],
            synced_commit="s2",
            reindexed_commit=None,
        )
        self.make_mirror_files("demo", "architecture/adr", 1)
        run = RisingDuringWaitRun()

        nightly.run_nightly(
            self.paths, run, clock=lambda: 0.0, sleep=lambda s: None,
            now_local=lambda: self.now, projects=["demo"],
        )

        lines = self.usage_lines()
        self.assertEqual(lines[0]["vlm_calls"], 100)  # the snapshot still reflects the pre-wait reading
        # baseline is 120 (100 + the 20 that ran during the wait), so the reindex's own +5 delta
        # is reported, not 25 (which would double-charge the wait's unrelated work).
        self.assertEqual(lines[-1], {"date": "2026-09-15", "reindex_vlm": 5})

    def test_wait_idle_timeout_after_reindex_stops_the_night(self):
        self.write_project_state(
            "demo",
            reindex_pending=["a", "b"],
            synced_commit="s2",
            reindexed_commit=None,
        )
        for d in ("a", "b"):
            self.make_mirror_files("demo", d, 1)
        run = BusyAfterFirstReindexRun(start_vlm=100, step=5)
        clocks = iter([0.0, 0.0, 1000.0])

        summary = nightly.run_nightly(
            self.paths, run, clock=lambda: next(clocks), sleep=lambda s: None,
            now_local=lambda: self.now, projects=["demo"],
        )

        self.assertTrue(summary["partial"])
        self.assertEqual(len(run.attempted), 1)
        st = state.read_state(self.paths, "demo")
        self.assertEqual(st["reindex_pending"], ["a", "b"])
        self.assertIsNone(st["reindexed_commit"])
        nightly_state = state.read_nightly(self.paths)
        self.assertIsNone(nightly_state["last_date"])
        self.assertEqual(nightly_state["retry_after"], self.now.timestamp() + 1800)
        lines = self.usage_lines()
        # The counter is re-read after the attempt even though the queue never drained.
        self.assertEqual(lines[-1], {"date": "2026-09-15", "reindex_vlm": 5, "partial": True})
        self.assertEqual(nightly_state["estimate_used"], 3)
        self.assertEqual(nightly_state["actual_used"], 5)
        self.assertEqual(nightly_state["last_counter"], 105)
        log_text = self.paths.log.read_text()
        self.assertIn(
            "_nightly skipped queue still busy after reindex, nightly reindex retried later",
            log_text,
        )

    def test_retry_same_day_shares_the_day_budget_and_charges_the_unfinished_tail(self):
        self.write_project_state("demo", reindex_pending=["a", "b", "c"], synced_commit="s2", reindexed_commit=None)
        for d in ("a", "b", "c"):
            self.make_mirror_files("demo", d, 10)  # estimate 30 each
        run = DeferredCostRun(slow="b", start_vlm=100, step=30)
        tick = [0.0]

        def clock():
            tick[0] += 1000.0
            return tick[0]

        summary1 = nightly.run_nightly(
            self.paths, run, clock=clock, sleep=lambda s: None,
            now_local=lambda: self.now, projects=["demo"],
        )

        self.assertTrue(summary1["partial"])
        self.assertEqual(run.attempted, ["a", "b"])
        self.assertEqual(state.read_state(self.paths, "demo")["reindex_pending"], ["b", "c"])
        n1 = state.read_nightly(self.paths)
        self.assertIsNone(n1["last_date"])
        self.assertEqual(n1["retry_after"], self.now.timestamp() + 1800)
        self.assertEqual((n1["budget_date"], n1["estimate_used"], n1["actual_used"], n1["last_counter"]),
                         ("2026-09-15", 60, 30, 130))

        run.finish()  # the unfinished attempt spends its 30 calls after the stop
        later = self.now + timedelta(minutes=31)
        self.assertTrue(nightly.is_due(n1, later))
        nightly.run_nightly(
            self.paths, run, clock=clock, sleep=lambda s: None,
            now_local=lambda: later, projects=["demo"],
        )

        self.assertEqual(run.attempted, ["a", "b"])
        self.assertEqual(state.read_state(self.paths, "demo")["reindex_pending"], ["b", "c"])
        n2 = state.read_nightly(self.paths)
        self.assertEqual(n2["last_date"], "2026-09-15")
        self.assertEqual((n2["estimate_used"], n2["actual_used"]), (60, 60))
        reindex_lines = [line for line in self.usage_lines() if "reindex_vlm" in line]
        self.assertEqual(reindex_lines[-1], {"date": "2026-09-15", "reindex_vlm": 30})
        self.assertEqual(sum(line["reindex_vlm"] for line in reindex_lines), run.vlm - 100)
        self.assertEqual(run.vlm - 100, 60)

    def test_new_day_resets_the_budget(self):
        state.write_nightly(self.paths, {
            "last_date": "2026-09-14", "snapshot_date": "2026-09-14", "retry_after": None,
            "budget_date": "2026-09-14", "estimate_used": 60, "actual_used": 90, "last_counter": 50,
        })
        self.write_project_state("demo", reindex_pending=["a"], synced_commit="s2", reindexed_commit=None)
        self.make_mirror_files("demo", "a", 10)
        run = FakeRun(start_vlm=100, step=30)

        nightly.run_nightly(
            self.paths, run, clock=lambda: 0.0, sleep=lambda s: None,
            now_local=lambda: self.now, projects=["demo"],
        )

        self.assertEqual(run.attempted, ["a"])
        self.assertEqual(self.usage_lines()[-1], {"date": "2026-09-15", "reindex_vlm": 30})
        n = state.read_nightly(self.paths)
        self.assertEqual((n["budget_date"], n["estimate_used"], n["actual_used"], n["last_counter"]),
                         ("2026-09-15", 30, 30, 130))

    def test_day_totals_are_stored_after_each_attempt(self):
        self.write_project_state("demo", reindex_pending=["a", "b"], synced_commit="s2", reindexed_commit=None)
        for d in ("a", "b"):
            self.make_mirror_files("demo", d, 1)
        run = FakeRun(start_vlm=100, step=5)
        run.reindex_raises["b"] = RuntimeError("worker crashed")

        with self.assertRaises(RuntimeError):
            nightly.run_nightly(
                self.paths, run, clock=lambda: 0.0, sleep=lambda s: None,
                now_local=lambda: self.now, projects=["demo"],
            )

        self.assertEqual(run.attempted, ["a", "b"])
        n = state.read_nightly(self.paths)
        self.assertEqual((n["budget_date"], n["estimate_used"], n["actual_used"], n["last_counter"]),
                         ("2026-09-15", 3, 5, 105))
        self.assertIsNone(n["last_date"])

    def test_directories_gone_from_the_mirror_leave_pending_without_reindex(self):
        self.write_project_state(
            "demo",
            reindex_pending=["architecture/adr", "architecture/backlog", "openspec/changes/x"],
            synced_commit="s2",
            reindexed_commit="s1",
        )
        (self.paths.stage / "demo" / "architecture/adr/empty").mkdir(parents=True)
        self.make_mirror_files("demo", "architecture/backlog", 1)
        run = FakeRun(start_vlm=100, step=5)

        with mock.patch.object(nightly.state, "write_state", wraps=state.write_state) as write_state:
            nightly.run_nightly(
                self.paths, run, clock=lambda: 0.0, sleep=lambda s: None,
                now_local=lambda: self.now, projects=["demo"],
            )

        self.assertEqual([c.args[1] for c in write_state.call_args_list], ["demo"])
        self.assertEqual(run.attempted, ["architecture/backlog"])
        st = state.read_state(self.paths, "demo")
        self.assertEqual(st["reindex_pending"], [])
        self.assertEqual(st["reindexed_commit"], "s2")
        self.assertEqual(state.read_nightly(self.paths)["estimate_used"], 3)

    def test_only_dropped_directories_still_advance_reindexed_commit(self):
        self.write_project_state(
            "demo", reindex_pending=["openspec/changes/x"], synced_commit="s2", reindexed_commit="s1",
        )
        run = FakeRun(start_vlm=100, step=5)

        nightly.run_nightly(
            self.paths, run, clock=lambda: 0.0, sleep=lambda s: None,
            now_local=lambda: self.now, projects=["demo"],
        )

        self.assertEqual(run.attempted, [])
        st = state.read_state(self.paths, "demo")
        self.assertEqual(st["reindex_pending"], [])
        self.assertEqual(st["reindexed_commit"], "s2")
        self.assertEqual(state.read_nightly(self.paths)["estimate_used"], 0)

    def test_directory_over_the_cap_is_reindexed_alone_as_the_first_of_the_day(self):
        self.write_project_state(
            "demo",
            reindex_pending=["architecture", "architecture/adr/big"],
            synced_commit="s2",
            reindexed_commit="s1",
        )
        self.write_project_state("other", reindex_pending=["small"], synced_commit="o2", reindexed_commit="o1")
        self.make_mirror_files("demo", "architecture/adr/big", 25)  # estimate 75
        self.make_mirror_files("demo", "architecture", 1)
        self.make_mirror_files("other", "small", 1)
        run = FakeRun(start_vlm=100, step=5)

        nightly.run_nightly(
            self.paths, run, clock=lambda: 0.0, sleep=lambda s: None,
            now_local=lambda: self.now, projects=["demo", "other"],
        )

        self.assertEqual(run.attempted, ["architecture/adr/big"])
        st = state.read_state(self.paths, "demo")
        self.assertEqual(st["reindex_pending"], ["architecture"])
        self.assertEqual(st["reindexed_commit"], "s1")
        self.assertEqual(state.read_state(self.paths, "other")["reindex_pending"], ["small"])
        self.assertEqual(state.read_nightly(self.paths)["estimate_used"], 75)

    def test_oversize_parent_is_not_starved_by_a_deeper_small_directory(self):
        self.write_project_state(
            "demo", reindex_pending=["architecture", "architecture/adr"], synced_commit="s2", reindexed_commit="s1",
        )
        self.make_mirror_files("demo", "architecture/adr", 4)
        for i in range(21):  # with adr's 4 files, architecture counts 25 recursively: estimate 75
            (self.paths.stage / "demo" / "architecture" / f"top{i}.md").write_text("x")
        run = FakeRun(start_vlm=100, step=5)

        nightly.run_nightly(
            self.paths, run, clock=lambda: 0.0, sleep=lambda s: None,
            now_local=lambda: self.now, projects=["demo"],
        )

        self.assertEqual(run.attempted, ["architecture"])
        self.assertEqual(state.read_state(self.paths, "demo")["reindex_pending"], ["architecture/adr"])
        self.assertEqual(state.read_nightly(self.paths)["estimate_used"], 75)

        next_night = self.now + timedelta(days=1)
        nightly.run_nightly(
            self.paths, run, clock=lambda: 0.0, sleep=lambda s: None,
            now_local=lambda: next_night, projects=["demo"],
        )

        self.assertEqual(run.attempted, ["architecture", "architecture/adr"])
        st = state.read_state(self.paths, "demo")
        self.assertEqual(st["reindex_pending"], [])
        self.assertEqual(st["reindexed_commit"], "s2")
        self.assertEqual(state.read_nightly(self.paths)["estimate_used"], 12)

    def add_pending(self, project, directory, files):
        st = state.read_state(self.paths, project)
        st["reindex_pending"] = sorted(set(st["reindex_pending"]) | {directory})
        state.write_state(self.paths, project, st)
        self.make_mirror_files(project, directory, files)

    def test_oversize_directory_of_a_later_project_is_not_starved_by_daily_small_changes(self):
        self.write_project_state("alpha", reindex_pending=[], synced_commit="a2", reindexed_commit="a1")
        self.write_project_state("beta", reindex_pending=[], synced_commit="b2", reindexed_commit="b1")
        self.add_pending("alpha", "openspec/changes/a1", 2)
        self.add_pending("beta", "architecture", 25)  # estimate 75
        run = FakeRun(start_vlm=100, step=5)

        def night(day):
            nightly.run_nightly(
                self.paths, run, clock=lambda: 0.0, sleep=lambda s: None,
                now_local=lambda: self.now + timedelta(days=day), projects=["alpha", "beta"],
            )

        night(0)
        self.assertEqual(run.attempted, ["architecture"])
        self.assertEqual(state.read_state(self.paths, "alpha")["reindex_pending"], ["openspec/changes/a1"])
        self.assertEqual(state.read_state(self.paths, "beta")["reindex_pending"], [])

        self.add_pending("alpha", "openspec/changes/a2", 2)
        night(1)
        self.assertEqual(run.attempted[1:], ["openspec/changes/a1", "openspec/changes/a2"])
        self.assertEqual(state.read_state(self.paths, "alpha")["reindex_pending"], [])

        self.add_pending("alpha", "openspec/changes/a3", 2)
        self.add_pending("beta", "architecture", 25)
        night(2)
        self.assertEqual(run.attempted[3:], ["architecture"])
        self.assertEqual(state.read_state(self.paths, "alpha")["reindex_pending"], ["openspec/changes/a3"])
        self.assertEqual(state.read_state(self.paths, "beta")["reindex_pending"], [])

    def test_crash_mid_project_keeps_directories_already_reindexed_out_of_pending(self):
        self.write_project_state("demo", reindex_pending=["a", "b"], synced_commit="s2", reindexed_commit="s1")
        for d in ("a", "b"):
            self.make_mirror_files("demo", d, 1)
        run = FakeRun(start_vlm=100, step=5)
        run.reindex_raises["b"] = RuntimeError("worker crashed")

        with self.assertRaises(RuntimeError):
            nightly.run_nightly(
                self.paths, run, clock=lambda: 0.0, sleep=lambda s: None,
                now_local=lambda: self.now, projects=["demo"],
            )

        st = state.read_state(self.paths, "demo")
        self.assertEqual(st["reindex_pending"], ["b"])
        self.assertEqual(st["reindexed_commit"], "s1")

    def test_oversize_directory_changed_every_day_alternates_with_small_directories(self):
        self.write_project_state("alpha", reindex_pending=[], synced_commit="a2", reindexed_commit="a1")
        self.write_project_state("beta", reindex_pending=[], synced_commit="b2", reindexed_commit="b1")
        self.add_pending("alpha", "openspec/changes/x", 2)
        run = FakeRun(start_vlm=100, step=5)

        def night(day):
            self.add_pending("beta", "architecture/adr", 21)  # every sync re-adds adr, estimate 63
            start = len(run.attempted)
            nightly.run_nightly(
                self.paths, run, clock=lambda: 0.0, sleep=lambda s: None,
                now_local=lambda: self.now + timedelta(days=day), projects=["alpha", "beta"],
            )
            return run.attempted[start:]

        self.assertEqual(night(0), ["architecture/adr"])
        self.assertEqual(state.read_nightly(self.paths)["oversize_night"], "2026-09-15")
        self.assertEqual(night(1), ["openspec/changes/x"])
        self.assertEqual(state.read_state(self.paths, "beta")["reindex_pending"], ["architecture/adr"])
        self.add_pending("alpha", "openspec/changes/y", 2)
        self.assertEqual(night(2), ["architecture/adr"])
        self.assertEqual(state.read_state(self.paths, "alpha")["reindex_pending"], ["openspec/changes/y"])
        self.assertEqual(night(3), ["openspec/changes/y"])

    def test_lone_oversize_directory_runs_on_consecutive_nights(self):
        self.write_project_state("beta", reindex_pending=[], synced_commit="b2", reindexed_commit="b1")
        run = FakeRun(start_vlm=100, step=5)

        for day in range(3):
            self.add_pending("beta", "architecture/adr", 21)
            nightly.run_nightly(
                self.paths, run, clock=lambda: 0.0, sleep=lambda s: None,
                now_local=lambda: self.now + timedelta(days=day), projects=["beta"],
            )

        self.assertEqual(run.attempted, ["architecture/adr"] * 3)
        self.assertEqual(state.read_nightly(self.paths)["oversize_night"], "2026-09-17")

    def test_non_string_oversize_night_means_no_previous_oversize_night(self):
        state.write_nightly(self.paths, {"last_date": 20260914, "oversize_night": 20260914})
        self.write_project_state("alpha", reindex_pending=[], synced_commit="a2", reindexed_commit="a1")
        self.write_project_state("beta", reindex_pending=[], synced_commit="b2", reindexed_commit="b1")
        self.add_pending("alpha", "openspec/changes/x", 2)
        self.add_pending("beta", "architecture/adr", 21)
        run = FakeRun(start_vlm=100, step=5)

        nightly.run_nightly(
            self.paths, run, clock=lambda: 0.0, sleep=lambda s: None,
            now_local=lambda: self.now, projects=["alpha", "beta"],
        )

        self.assertEqual(run.attempted, ["architecture/adr"])

    def test_directory_over_the_cap_waits_when_the_day_already_has_an_estimate(self):
        state.write_nightly(self.paths, {"budget_date": "2026-09-15", "estimate_used": 3, "actual_used": 0})
        self.write_project_state(
            "demo", reindex_pending=["architecture/adr/big"], synced_commit="s2", reindexed_commit="s1",
        )
        self.make_mirror_files("demo", "architecture/adr/big", 25)
        run = FakeRun(start_vlm=100, step=5)

        nightly.run_nightly(
            self.paths, run, clock=lambda: 0.0, sleep=lambda s: None,
            now_local=lambda: self.now, projects=["demo"],
        )

        self.assertEqual(run.attempted, [])
        st = state.read_state(self.paths, "demo")
        self.assertEqual(st["reindex_pending"], ["architecture/adr/big"])
        self.assertEqual(st["reindexed_commit"], "s1")
        self.assertEqual(state.read_nightly(self.paths)["estimate_used"], 3)

    def test_busy_queue_with_pending_project_reindexes_on_retry(self):
        self.write_project_state(
            "demo",
            reindex_pending=["architecture/adr"],
            synced_commit="s2",
            reindexed_commit=None,
        )
        self.make_mirror_files("demo", "architecture/adr", 1)
        run = BusyThenIdleRun()
        clock_values = iter([0.0, 1000.0])

        nightly.run_nightly(
            self.paths, run, clock=lambda: next(clock_values), sleep=lambda s: None,
            now_local=lambda: self.now, projects=["demo"],
        )

        self.assertEqual(run.attempted, [])
        st = state.read_state(self.paths, "demo")
        self.assertEqual(st["reindex_pending"], ["architecture/adr"])
        nightly_state = state.read_nightly(self.paths)
        self.assertIsNone(nightly_state["last_date"])

        run.busy = False
        later = self.now + timedelta(minutes=31)
        nightly.run_nightly(
            self.paths, run, clock=lambda: 0.0, sleep=lambda s: None,
            now_local=lambda: later, projects=["demo"],
        )

        st2 = state.read_state(self.paths, "demo")
        self.assertEqual(st2["reindex_pending"], [])
        self.assertEqual(st2["reindexed_commit"], "s2")
        nightly_state2 = state.read_nightly(self.paths)
        self.assertEqual(nightly_state2["last_date"], later.strftime("%Y-%m-%d"))

    def test_busy_queue_defers_without_consuming_the_tick(self):
        run = BusyThenIdleRun()
        clock_values = iter([0.0, 1000.0])

        summary1 = nightly.run_nightly(
            self.paths, run, clock=lambda: next(clock_values), sleep=lambda s: None,
            now_local=lambda: self.now, projects=[],
        )

        self.assertFalse(summary1["unavailable"])
        nightly_state = state.read_nightly(self.paths)
        self.assertIsNone(nightly_state["last_date"])
        self.assertEqual(nightly_state["retry_after"], self.now.timestamp() + 1800)
        self.assertEqual(len(self.snapshot_lines()), 1)
        log_text = self.paths.log.read_text()
        self.assertIn("_nightly skipped queue busy, nightly reindex retried later", log_text)
        self.assertEqual(self.usage_lines()[-1], {"date": "2026-09-15", "reindex_vlm": 0, "partial": True})

        self.assertFalse(nightly.is_due(nightly_state, self.now + timedelta(minutes=10)))
        self.assertTrue(nightly.is_due(nightly_state, self.now + timedelta(minutes=31)))

        run.busy = False
        later = self.now + timedelta(minutes=31)
        nightly.run_nightly(
            self.paths, run, clock=lambda: 0.0, sleep=lambda s: None,
            now_local=lambda: later, projects=[],
        )

        nightly_state2 = state.read_nightly(self.paths)
        self.assertEqual(nightly_state2["last_date"], later.strftime("%Y-%m-%d"))
        self.assertEqual(len(self.snapshot_lines()), 1)


if __name__ == "__main__":
    unittest.main()
