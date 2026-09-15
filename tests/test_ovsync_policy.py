import copy
import importlib.machinery
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "lib"))

from ovsync import policy

EMPTY = {
    "synced_commit": None, "synced_at": None, "files": 0, "duration": 0.0,
    "result": None, "error": None, "running": False, "started_at": None,
    "failures": 0, "failing": False, "failing_head": None, "failing_marker": None,
    "next_attempt": 0.0, "backoff": 0.0, "unavailable_since": None,
    "pending_task": None, "reindexed_commit": None, "reindex_pending": [],
}


class Apply(unittest.TestCase):
    def test_does_not_mutate_input(self):
        state = dict(EMPTY)
        before = dict(state)
        policy.apply(state, "ok", 1000.0)
        self.assertEqual(state, before)

    def test_does_not_mutate_nested_input(self):
        state = dict(EMPTY)
        state["pending_task"] = {"task_id": "t1", "created_at": 5.0}
        state["reindex_pending"] = ["a", "b"]
        before = copy.deepcopy(state)

        result = policy.apply(state, "timeout", 1000.0, task={"task_id": "t2", "created_at": 6.0})
        self.assertEqual(state, before)
        self.assertIsNot(result["reindex_pending"], state["reindex_pending"])

        result2 = policy.apply(state, "failed", 1000.0, head="abc", marker=900.0)
        self.assertEqual(state, before)
        self.assertIsNot(result2["pending_task"], state["pending_task"])
        self.assertIsNot(result2["reindex_pending"], state["reindex_pending"])

    def test_result_and_running_always_set(self):
        for outcome in ("ok", "skipped", "failed", "timeout", "unavailable", "locked"):
            state = dict(EMPTY)
            result = policy.apply(state, outcome, 1000.0)
            self.assertFalse(result["running"])
            self.assertEqual(result["result"], outcome)

    def test_unavailable_first_time(self):
        state = dict(EMPTY)
        result = policy.apply(state, "unavailable", 1000.0)
        self.assertEqual(result["backoff"], 60.0)
        self.assertEqual(result["next_attempt"], 1060.0)
        self.assertEqual(result["unavailable_since"], 1000.0)

    def test_unavailable_doubles_and_keeps_since(self):
        state = dict(EMPTY)
        result = policy.apply(state, "unavailable", 1000.0)
        result = policy.apply(result, "unavailable", 1060.0)
        self.assertEqual(result["backoff"], 120.0)
        self.assertEqual(result["next_attempt"], 1180.0)
        self.assertEqual(result["unavailable_since"], 1000.0)

    def test_unavailable_caps_backoff(self):
        state = dict(EMPTY)
        now = 1000.0
        result = state
        for _ in range(20):
            result = policy.apply(result, "unavailable", now)
            now = result["next_attempt"]
        self.assertEqual(result["backoff"], 1800.0)

    def test_locked_first_time(self):
        state = dict(EMPTY)
        result = policy.apply(state, "locked", 1000.0)
        self.assertEqual(result["backoff"], 30.0)
        self.assertEqual(result["next_attempt"], 1030.0)

    def test_locked_doubles(self):
        state = dict(EMPTY)
        result = policy.apply(state, "locked", 1000.0)
        result = policy.apply(result, "locked", 1030.0)
        self.assertEqual(result["backoff"], 60.0)

    def test_locked_caps_backoff(self):
        state = dict(EMPTY)
        now = 1000.0
        result = state
        for _ in range(20):
            result = policy.apply(result, "locked", now)
            now = result["next_attempt"]
        self.assertEqual(result["backoff"], 300.0)

    def test_locked_after_unavailable_starts_again(self):
        state = dict(EMPTY)
        result = policy.apply(state, "unavailable", 1000.0)
        result = policy.apply(result, "locked", 1060.0)
        self.assertEqual(result["backoff"], 30.0)
        self.assertEqual(result["next_attempt"], 1090.0)
        self.assertIsNone(result["unavailable_since"])

    def test_unavailable_backoff_continues_across_skipped(self):
        state = dict(EMPTY)
        result = policy.apply(state, "unavailable", 1000.0)
        result = policy.apply(result, "skipped", 1100.0, git_error=True)
        result = policy.apply(result, "unavailable", 1200.0)
        self.assertEqual(result["unavailable_since"], 1000.0)
        self.assertEqual(result["backoff"], 120.0)

    def test_unavailable_backoff_restarts_after_failed(self):
        state = dict(EMPTY)
        result = policy.apply(state, "unavailable", 1000.0)
        result = policy.apply(result, "failed", 1100.0, head="abc", marker=900.0)
        self.assertIsNone(result["unavailable_since"])
        result = policy.apply(result, "unavailable", 1200.0)
        self.assertEqual(result["unavailable_since"], 1200.0)
        self.assertEqual(result["backoff"], 60.0)

    def test_ok_clears_unavailable_since(self):
        state = dict(EMPTY)
        state["unavailable_since"] = 100.0
        result = policy.apply(state, "ok", 1000.0)
        self.assertIsNone(result["unavailable_since"])

    def test_failed_clears_unavailable_since(self):
        state = dict(EMPTY)
        state["unavailable_since"] = 100.0
        result = policy.apply(state, "failed", 1000.0, head="abc", marker=900.0)
        self.assertIsNone(result["unavailable_since"])

    def test_locked_clears_unavailable_since(self):
        state = dict(EMPTY)
        state["unavailable_since"] = 100.0
        result = policy.apply(state, "locked", 1000.0)
        self.assertIsNone(result["unavailable_since"])

    def test_timeout_clears_unavailable_since(self):
        state = dict(EMPTY)
        state["unavailable_since"] = 100.0
        result = policy.apply(state, "timeout", 1000.0, task={"task_id": "t1", "created_at": 5.0})
        self.assertIsNone(result["unavailable_since"])

    def test_skipped_does_not_touch_unavailable_since(self):
        state = dict(EMPTY)
        state["unavailable_since"] = 100.0
        result = policy.apply(state, "skipped", 1000.0)
        self.assertEqual(result["unavailable_since"], 100.0)

    def test_unavailable_starts_over_when_backoff_is_zero(self):
        state = dict(EMPTY)
        state["result"] = "unavailable"
        state["unavailable_since"] = 500.0
        state["backoff"] = 0.0
        result = policy.apply(state, "unavailable", 1000.0)
        self.assertEqual(result["backoff"], 60.0)
        self.assertEqual(result["next_attempt"], 1060.0)
        self.assertEqual(result["unavailable_since"], 500.0)

    def test_unavailable_starts_over_when_backoff_missing(self):
        state = dict(EMPTY)
        state["result"] = "unavailable"
        state["unavailable_since"] = 500.0
        del state["backoff"]
        result = policy.apply(state, "unavailable", 1000.0)
        self.assertEqual(result["backoff"], 60.0)

    def test_locked_starts_over_when_backoff_is_zero(self):
        state = dict(EMPTY)
        state["result"] = "locked"
        state["backoff"] = 0.0
        result = policy.apply(state, "locked", 1000.0)
        self.assertEqual(result["backoff"], 30.0)
        self.assertEqual(result["next_attempt"], 1030.0)

    def test_locked_starts_over_when_backoff_missing(self):
        state = dict(EMPTY)
        state["result"] = "locked"
        del state["backoff"]
        result = policy.apply(state, "locked", 1000.0)
        self.assertEqual(result["backoff"], 30.0)

    def test_skipped_without_error_keeps_previous_error(self):
        state = dict(EMPTY)
        state["error"] = "previous boom"
        result = policy.apply(state, "skipped", 1000.0)
        self.assertEqual(result["error"], "previous boom")

    def test_failed_three_times(self):
        state = dict(EMPTY)
        result = policy.apply(state, "failed", 1000.0, head="abc", marker=900.0, error="e1")
        self.assertFalse(result["failing"])
        self.assertEqual(result["failures"], 1)
        self.assertEqual(result["next_attempt"], 1060.0)
        self.assertEqual(result["error"], "e1")

        result = policy.apply(result, "failed", 1100.0, head="abc", marker=900.0, error="e2")
        self.assertFalse(result["failing"])
        self.assertEqual(result["failures"], 2)
        self.assertEqual(result["next_attempt"], 1160.0)
        self.assertEqual(result["error"], "e2")

        result = policy.apply(result, "failed", 1200.0, head="abc", marker=900.0, error="e3")
        self.assertTrue(result["failing"])
        self.assertEqual(result["failures"], 3)
        self.assertEqual(result["failing_head"], "abc")
        self.assertEqual(result["failing_marker"], 900.0)
        self.assertEqual(result["next_attempt"], 1260.0)
        self.assertEqual(result["error"], "e3")

    def test_timeout(self):
        state = dict(EMPTY)
        task = {"task_id": "t1", "created_at": 5.0}
        result = policy.apply(state, "timeout", 1000.0, task=task)
        self.assertEqual(result["pending_task"], task)
        self.assertEqual(result["next_attempt"], 1060.0)

    def test_skipped_git_error(self):
        state = dict(EMPTY)
        result = policy.apply(state, "skipped", 1000.0, git_error=True)
        self.assertEqual(result["next_attempt"], 1300.0)
        self.assertEqual(result["failures"], 0)

    def test_skipped_without_git_error(self):
        state = dict(EMPTY)
        state["next_attempt"] = 42.0
        result = policy.apply(state, "skipped", 1000.0)
        self.assertEqual(result["next_attempt"], 42.0)
        self.assertEqual(result["failures"], 0)

    def test_ok_resets_after_failures(self):
        state = dict(EMPTY)
        state.update({
            "failures": 3, "failing": True, "backoff": 1800.0,
            "next_attempt": 5000.0, "unavailable_since": 100.0, "error": "boom",
            "pending_task": {"task_id": "t1", "created_at": 1.0},
        })
        result = policy.apply(state, "ok", 1000.0)
        self.assertEqual(result["failures"], 0)
        self.assertFalse(result["failing"])
        self.assertEqual(result["backoff"], 0.0)
        self.assertEqual(result["next_attempt"], 0.0)
        self.assertIsNone(result["unavailable_since"])
        self.assertIsNone(result["error"])
        self.assertIsNone(result["pending_task"])

    def test_unknown_outcome_raises(self):
        state = dict(EMPTY)
        with self.assertRaises(ValueError):
            policy.apply(state, "bogus", 1000.0)


if __name__ == "__main__":
    unittest.main()
