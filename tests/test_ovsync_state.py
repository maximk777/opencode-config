import importlib.machinery
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "lib"))

from ovsync import state


class ValidProject(unittest.TestCase):
    def test_accepts(self):
        for name in ["demo", "legacy-backoffice", "a.b_c"]:
            self.assertTrue(state.valid_project(name), name)

    def test_rejects(self):
        for name in ["../etc", ".hidden", "a..b", "a/b", ""]:
            self.assertFalse(state.valid_project(name), name)


class StateTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.tmp = Path(self.tmpdir.name)
        self.paths = state.Paths(home=self.tmp, specs=self.tmp / "specs", repo=REPO)

    def all_files(self):
        return [str(p) for p in self.tmp.rglob("*") if p.is_file()]


class Markers(StateTestCase):
    def test_touch_and_read(self):
        state.touch_marker(self.paths, "demo", now=1000.0)
        marker = self.paths.queue / "demo"
        self.assertTrue(marker.exists())
        self.assertEqual(marker.stat().st_mtime, 1000.0)
        self.assertEqual(state.marker_mtime(self.paths, "demo"), 1000.0)
        self.assertIsNone(state.marker_mtime(self.paths, "missing"))

    def test_markers_skips_invalid_names(self):
        state.touch_marker(self.paths, "demo", now=1000.0)
        (self.paths.queue / ".hidden").touch()
        self.assertEqual(state.markers(self.paths), {"demo": 1000.0})

    def test_remove_marker_if_not_newer(self):
        state.touch_marker(self.paths, "demo", now=1000.0)
        self.assertTrue(state.remove_marker_if_not_newer(self.paths, "demo", started_at=1000.0))
        self.assertFalse((self.paths.queue / "demo").exists())

    def test_remove_marker_kept_when_newer(self):
        state.touch_marker(self.paths, "demo", now=1001.0)
        self.assertFalse(state.remove_marker_if_not_newer(self.paths, "demo", started_at=1000.0))
        self.assertTrue((self.paths.queue / "demo").exists())

    def test_remove_marker_missing(self):
        self.assertFalse(state.remove_marker_if_not_newer(self.paths, "missing", started_at=1000.0))

    def test_remove_marker_vanishing_between_stat_and_unlink(self):
        state.touch_marker(self.paths, "demo", now=1000.0)
        with mock.patch.object(Path, "unlink", side_effect=FileNotFoundError()):
            result = state.remove_marker_if_not_newer(self.paths, "demo", started_at=1000.0)
        self.assertFalse(result)

    def test_touch_marker_rejects_invalid_name(self):
        with self.assertRaises(ValueError):
            state.touch_marker(self.paths, "../etc")
        self.assertEqual(self.all_files(), [])

    def test_marker_mtime_rejects_invalid_name(self):
        with self.assertRaises(ValueError):
            state.marker_mtime(self.paths, "../etc")

    def test_remove_marker_rejects_invalid_name(self):
        with self.assertRaises(ValueError):
            state.remove_marker_if_not_newer(self.paths, "../etc", started_at=0.0)

    def test_markers_on_fresh_home(self):
        self.assertEqual(state.markers(self.paths), {})

    def test_touch_marker_creates_dirs(self):
        state.touch_marker(self.paths, "demo", now=1000.0)
        self.assertTrue(self.paths.queue.is_dir())


class ProjectState(StateTestCase):
    def test_read_state_missing_returns_defaults_copy(self):
        data = state.read_state(self.paths, "demo")
        self.assertEqual(data, state.EMPTY_STATE)
        self.assertIsNot(data, state.EMPTY_STATE)

    def test_read_state_merges_defaults(self):
        self.paths.state.mkdir(parents=True, exist_ok=True)
        (self.paths.state / "demo.json").write_text(json.dumps({"synced_commit": "abc"}))
        data = state.read_state(self.paths, "demo")
        expected = dict(state.EMPTY_STATE, synced_commit="abc")
        self.assertEqual(data, expected)

    def test_write_state_round_trips(self):
        payload = dict(state.EMPTY_STATE, synced_commit="deadbeef", files=3)
        state.write_state(self.paths, "demo", payload)
        self.assertEqual(state.read_state(self.paths, "demo"), payload)
        names = [p.name for p in self.paths.state.iterdir()]
        self.assertFalse(any(n.endswith(".tmp") for n in names))
        text = (self.paths.state / "demo.json").read_text()
        self.assertTrue(text.endswith("\n"))
        self.assertIn('\n  "synced_commit"', text)

    def test_list_states_skips_nightly(self):
        state.write_state(self.paths, "demo", dict(state.EMPTY_STATE))
        state.write_nightly(self.paths, {"last_date": "2026-09-14"})
        result = state.list_states(self.paths)
        self.assertEqual(set(result), {"demo"})
        self.assertEqual(result["demo"], state.EMPTY_STATE)

    def test_read_state_invalid_json_returns_defaults(self):
        self.paths.state.mkdir(parents=True, exist_ok=True)
        (self.paths.state / "demo.json").write_text("{not json")
        data = state.read_state(self.paths, "demo")
        self.assertEqual(data, state.EMPTY_STATE)
        self.assertIsNot(data, state.EMPTY_STATE)

    def test_read_state_non_object_json_returns_defaults(self):
        self.paths.state.mkdir(parents=True, exist_ok=True)
        (self.paths.state / "demo.json").write_text(json.dumps([1, 2, 3]))
        data = state.read_state(self.paths, "demo")
        self.assertEqual(data, state.EMPTY_STATE)

    def test_list_states_survives_corrupted_project_and_returns_others(self):
        state.write_state(self.paths, "good", dict(state.EMPTY_STATE, synced_commit="abc"))
        (self.paths.state / "bad.json").write_text("{not json")
        result = state.list_states(self.paths)
        self.assertEqual(result["good"], dict(state.EMPTY_STATE, synced_commit="abc"))
        self.assertEqual(result["bad"], state.EMPTY_STATE)

    def test_list_states_skips_invalid_stems(self):
        self.paths.state.mkdir(parents=True, exist_ok=True)
        (self.paths.state / ".bad.json").write_text(json.dumps(state.EMPTY_STATE))
        state.write_state(self.paths, "demo", dict(state.EMPTY_STATE))
        result = state.list_states(self.paths)
        self.assertEqual(set(result), {"demo"})

    def test_list_states_on_fresh_home(self):
        self.assertEqual(state.list_states(self.paths), {})

    def test_write_state_creates_dirs(self):
        state.write_state(self.paths, "demo", dict(state.EMPTY_STATE))
        self.assertTrue(self.paths.state.is_dir())

    def test_read_state_rejects_invalid_name(self):
        with self.assertRaises(ValueError):
            state.read_state(self.paths, "../etc")

    def test_write_state_rejects_invalid_name(self):
        with self.assertRaises(ValueError):
            state.write_state(self.paths, "../x", {})
        self.assertEqual(self.all_files(), [])


class Nightly(StateTestCase):
    def test_round_trip(self):
        self.assertEqual(state.read_nightly(self.paths), {"last_date": None})
        state.write_nightly(self.paths, {"last_date": "2026-09-14"})
        self.assertEqual(state.read_nightly(self.paths), {"last_date": "2026-09-14"})

    def test_read_nightly_on_fresh_home(self):
        self.assertEqual(state.read_nightly(self.paths), {"last_date": None})

    def test_read_nightly_merges_defaults(self):
        self.paths.state.mkdir(parents=True, exist_ok=True)
        (self.paths.state / "_nightly.json").write_text(json.dumps({"extra": "x"}))
        self.assertEqual(state.read_nightly(self.paths), {"last_date": None, "extra": "x"})

    def test_read_nightly_invalid_json_returns_defaults(self):
        self.paths.state.mkdir(parents=True, exist_ok=True)
        (self.paths.state / "_nightly.json").write_text("{not json")
        self.assertEqual(state.read_nightly(self.paths), {"last_date": None})


class LogAndUsage(StateTestCase):
    def test_append_log(self):
        state.append_log(self.paths, "demo", "ok", "files=3", now=0.0)
        lines = self.paths.log.read_text().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].endswith("demo ok files=3"))

    def test_append_usage(self):
        state.append_usage(self.paths, {"date": "2026-09-15", "reindex_vlm": 4})
        lines = self.paths.usage.read_text().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0]), {"date": "2026-09-15", "reindex_vlm": 4})

    def test_append_log_creates_dirs(self):
        state.append_log(self.paths, "demo", "ok", "x", now=0.0)
        self.assertTrue(self.paths.log.exists())

    def test_append_usage_creates_dirs(self):
        state.append_usage(self.paths, {"date": "2026-09-15"})
        self.assertTrue(self.paths.usage.exists())


if __name__ == "__main__":
    unittest.main()
