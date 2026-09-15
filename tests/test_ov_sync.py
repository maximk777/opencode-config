import contextlib
import importlib.machinery
import io
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "lib"))

from ovsync import state  # noqa: E402

S = importlib.machinery.SourceFileLoader("ov_sync", str(REPO / "bin/ov-sync")).load_module()


class OvSyncEnqueue(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        home = Path(self.tmp.name) / "home"
        specs = Path(self.tmp.name) / "specs"
        self.paths = state.Paths(home, specs, REPO)
        self.empty_path_dir = Path(self.tmp.name) / "empty-path"
        self.empty_path_dir.mkdir()

    def run_main(self, argv, now=None):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = S.main(argv, paths=self.paths, now=now)
        return code, out.getvalue(), err.getvalue()

    def test_enqueue_creates_marker_without_running_anything(self):
        with patch("subprocess.run", side_effect=AssertionError("subprocess.run called")), \
             patch("subprocess.Popen", side_effect=AssertionError("subprocess.Popen called")), \
             patch("os.system", side_effect=AssertionError("os.system called")), \
             patch.dict(os.environ, {"PATH": str(self.empty_path_dir)}):
            code, out, err = self.run_main(["demo"], now=1000.0)
        self.assertEqual(code, 0)
        marker = self.paths.queue / "demo"
        self.assertTrue(marker.exists())
        self.assertEqual(marker.stat().st_mtime, 1000)
        self.assertIn("ov-sync: queued demo", out)

    def test_enqueue_is_fast(self):
        start = time.perf_counter()
        code, _, _ = self.run_main(["demo"], now=1000.0)
        elapsed = time.perf_counter() - start
        self.assertEqual(code, 0)
        self.assertLess(elapsed, 0.1)

    def test_invalid_project_name_rejected(self):
        code, out, err = self.run_main(["../etc"], now=1000.0)
        self.assertEqual(code, 2)
        self.assertTrue(err.startswith("usage: ov-sync"))
        self.assertFalse(self.paths.queue.exists() and any(self.paths.queue.iterdir()))

    def test_no_args_rejected(self):
        code, out, err = self.run_main([], now=1000.0)
        self.assertEqual(code, 2)
        self.assertTrue(err.startswith("usage: ov-sync"))
        self.assertFalse(self.paths.queue.exists() and any(self.paths.queue.iterdir()))

    def test_too_many_args_rejected(self):
        code, out, err = self.run_main(["a", "b"], now=1000.0)
        self.assertEqual(code, 2)
        self.assertTrue(err.startswith("usage: ov-sync"))
        self.assertFalse(self.paths.queue.exists() and any(self.paths.queue.iterdir()))


class OvSyncStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        home = Path(self.tmp.name) / "home"
        specs = Path(self.tmp.name) / "specs"
        self.paths = state.Paths(home, specs, REPO)

    def run_main(self, argv, now=None):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = S.main(argv, paths=self.paths, now=now)
        return code, out.getvalue(), err.getvalue()

    def test_queued_and_failing_projects(self):
        state.touch_marker(self.paths, "demo", now=1000.0)
        failing_state = dict(state.EMPTY_STATE)
        failing_state.update({
            "failures": 3, "failing": True, "result": "failed", "error": "boom",
            "synced_commit": "0123456789abcdef", "synced_at": 900.0,
        })
        state.write_state(self.paths, "alpha", failing_state)
        code, out, err = self.run_main(["--status"], now=2000.0)
        self.assertEqual(code, 0)
        lines = out.splitlines()
        demo_line = next(l for l in lines if l.startswith("demo: queued"))
        alpha_line = next(l for l in lines if l.startswith("alpha: failing"))
        self.assertIn("error=boom", alpha_line)
        self.assertIn("commit=0123456", alpha_line)

    def test_running_state_prints_running(self):
        running_state = dict(state.EMPTY_STATE)
        running_state.update({"running": True, "started_at": 1000.0})
        state.write_state(self.paths, "beta", running_state)
        code, out, err = self.run_main(["--status"], now=2000.0)
        self.assertEqual(code, 0)
        self.assertTrue(any(l.startswith("beta: running") for l in out.splitlines()))

    def test_idle_state_with_result_ok(self):
        ok_state = dict(state.EMPTY_STATE)
        ok_state.update({"result": "ok"})
        state.write_state(self.paths, "gamma", ok_state)
        code, out, err = self.run_main(["--status"], now=2000.0)
        self.assertEqual(code, 0)
        self.assertTrue(any(l.startswith("gamma: idle last=ok") for l in out.splitlines()))

    def test_unavailable_since_shown(self):
        unavailable_state = dict(state.EMPTY_STATE)
        unavailable_state.update({"unavailable_since": 500.0})
        state.write_state(self.paths, "delta", unavailable_state)
        code, out, err = self.run_main(["--status"], now=2000.0)
        self.assertEqual(code, 0)
        iso = datetime.fromtimestamp(500.0).isoformat(timespec="seconds")
        line = next(l for l in out.splitlines() if l.startswith("delta:"))
        self.assertIn("unavailable since " + iso, line)

    def test_missing_values_use_dash_placeholder(self):
        marker_only_state = dict(state.EMPTY_STATE)
        state.write_state(self.paths, "epsilon", marker_only_state)
        code, out, err = self.run_main(["--status"], now=2000.0)
        self.assertEqual(code, 0)
        line = next(l for l in out.splitlines() if l.startswith("epsilon:"))
        self.assertIn("last=-", line)
        self.assertIn("commit=-", line)
        self.assertNotIn("at=", line)

    def test_synced_at_shown_as_synced(self):
        ok_state = dict(state.EMPTY_STATE)
        ok_state.update({"result": "ok", "synced_at": 900.0})
        state.write_state(self.paths, "zeta", ok_state)
        code, out, err = self.run_main(["--status"], now=2000.0)
        self.assertEqual(code, 0)
        iso = datetime.fromtimestamp(900.0).isoformat(timespec="seconds")
        line = next(l for l in out.splitlines() if l.startswith("zeta:"))
        self.assertIn("synced=" + iso, line)
        self.assertNotIn("at=", line)

    def test_unavailable_default_error_not_duplicated(self):
        unavailable_state = dict(state.EMPTY_STATE)
        unavailable_state.update({
            "result": "unavailable", "error": "OpenViking unavailable", "unavailable_since": 500.0,
        })
        state.write_state(self.paths, "eta", unavailable_state)
        code, out, err = self.run_main(["--status"], now=2000.0)
        self.assertEqual(code, 0)
        iso = datetime.fromtimestamp(500.0).isoformat(timespec="seconds")
        line = next(l for l in out.splitlines() if l.startswith("eta:"))
        self.assertIn("last=unavailable", line)
        self.assertIn("unavailable since " + iso, line)
        self.assertNotIn("unavailable unavailable", line)
        self.assertNotIn("error=", line)

    def test_unavailable_distinct_error_still_shown(self):
        unavailable_state = dict(state.EMPTY_STATE)
        unavailable_state.update({
            "result": "unavailable", "error": "custom failure", "unavailable_since": 500.0,
        })
        state.write_state(self.paths, "theta", unavailable_state)
        code, out, err = self.run_main(["--status"], now=2000.0)
        self.assertEqual(code, 0)
        line = next(l for l in out.splitlines() if l.startswith("theta:"))
        self.assertIn("error=custom failure", line)

    def test_nothing_queued_or_synced(self):
        code, out, err = self.run_main(["--status"], now=2000.0)
        self.assertEqual(code, 0)
        self.assertIn("ov-sync: nothing queued or synced", out)


if __name__ == "__main__":
    unittest.main()
