import importlib.machinery
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
T = importlib.machinery.SourceFileLoader("change_todos", str(REPO / "bin/change-todos")).load_module()


def _tree(root):
    """Snapshot of every path under root and file contents, to prove a run makes no writes."""
    entries = {}
    for p in sorted(Path(root).rglob("*")):
        entries[str(p.relative_to(root))] = p.read_bytes() if p.is_file() else None
    return entries


def _make_change(root, slug, tasks_text, waves_text=None):
    change = Path(root) / "openspec" / "changes" / slug
    change.mkdir(parents=True)
    (change / "tasks.md").write_text(tasks_text)
    if waves_text is not None:
        (change / "waves.md").write_text(waves_text)
    return change


def _report(change, task_id, text):
    reports = change / "reports"
    reports.mkdir(exist_ok=True)
    (reports / f"{task_id}.md").write_text(text)


class Build(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_finished_change_collapses_both_groups(self):
        tasks = (
            "## 1. Core\n"
            "- [x] 1.1 Parse tasks\n"
            "- [x] 1.2 Collapse groups\n"
            "## 2. Flow\n"
            "- [x] 2.1 Read state\n"
            "- [x] 2.2 Build items\n"
            "- [x] 2.3 Print JSON\n"
        )
        _make_change(self.root, "add-ping", tasks)
        items = T.build(self.root, "add-ping")
        self.assertEqual(
            items,
            [
                {"content": "1. Core (2/2)", "status": "completed", "priority": "low"},
                {"content": "2. Flow (3/3)", "status": "completed", "priority": "low"},
            ],
        )

    def test_unfinished_group_without_waves_file(self):
        tasks = "## 1. Core\n- [x] 1.1 Parse tasks\n- [ ] 1.2 Collapse groups\n"
        _make_change(self.root, "add-ping", tasks)
        items = T.build(self.root, "add-ping")
        self.assertEqual(
            items,
            [{"content": "1. Core (1/2)", "status": "pending", "priority": "medium"}],
        )

    def test_ungrouped_tasks_before_first_heading_come_first(self):
        tasks = (
            "- [ ] 0.1 Setup\n"
            "- [x] 0.2 Notes\n"
            "## 1. Core\n"
            "- [ ] 1.1 Parse tasks\n"
        )
        _make_change(self.root, "add-ping", tasks)
        items = T.build(self.root, "add-ping")
        self.assertEqual(
            items[:2],
            [
                {"content": "0.1 Setup", "status": "pending", "priority": "medium"},
                {"content": "0.2 Notes", "status": "completed", "priority": "low"},
            ],
        )

    def test_missing_change_directory_raises(self):
        with self.assertRaises(FileNotFoundError):
            T.build(self.root, "no-such-change")

    def test_missing_tasks_file_raises(self):
        (Path(self.root) / "openspec" / "changes" / "add-ping").mkdir(parents=True)
        with self.assertRaises(FileNotFoundError):
            T.build(self.root, "add-ping")

    def test_tasks_md_as_directory_raises(self):
        change = Path(self.root) / "openspec" / "changes" / "add-ping"
        (change / "tasks.md").mkdir(parents=True)
        with self.assertRaises(FileNotFoundError):
            T.build(self.root, "add-ping")

    def test_current_wave_group_expands_with_every_report_state(self):
        tasks = (
            "## 1. Core\n"
            "- [x] 1.1 A\n"
            "- [ ] 1.2 B\n"
            "- [ ] 1.3 C\n"
            "- [ ] 1.4 D\n"
            "- [ ] 1.5 E\n"
            "- [ ] 1.6 F\n"
        )
        waves = "wave 1: 1.1 1.2 1.3 1.4 1.5\nwave 2: 1.6\ntier 1.1 executor\n"
        change = _make_change(self.root, "add-ping", tasks, waves)
        _report(change, "1.2", "## Attempt 1\n")
        _report(change, "1.3", "## Attempt 1\nVerdict: NOT COMPLIANT\n")
        _report(change, "1.4", "## Attempt 1\nVerdict: COMPLIANT\n")
        items = T.build(self.root, "add-ping")
        self.assertEqual(
            items,
            [
                {"content": "1.1 A", "status": "completed", "priority": "low"},
                {"content": "1.2 B (review)", "status": "in_progress", "priority": "high"},
                {"content": "1.3 C (fix)", "status": "in_progress", "priority": "high"},
                {"content": "1.4 D (accept)", "status": "in_progress", "priority": "high"},
                {"content": "1.5 E", "status": "in_progress", "priority": "high"},
                {"content": "1.6 F", "status": "pending", "priority": "medium"},
            ],
        )

    def test_only_the_group_holding_the_current_wave_expands(self):
        tasks = (
            "## 1. Core\n"
            "- [x] 1.1 A\n"
            "- [x] 1.2 B\n"
            "## 2. Flow\n"
            "- [ ] 2.1 X\n"
            "## 3. Docs\n"
            "- [ ] 3.1 Y\n"
        )
        waves = "wave 1: 2.1\ntier 2.1 executor\n"
        _make_change(self.root, "add-ping", tasks, waves)
        items = T.build(self.root, "add-ping")
        self.assertEqual(
            items,
            [
                {"content": "1. Core (2/2)", "status": "completed", "priority": "low"},
                {"content": "2.1 X", "status": "in_progress", "priority": "high"},
                {"content": "3. Docs (0/1)", "status": "pending", "priority": "medium"},
            ],
        )

    def test_ungrouped_task_outside_current_wave_stays_pending(self):
        tasks = "- [ ] 0.1 Setup\n## 1. Core\n- [ ] 1.1 A\n"
        waves = "wave 1: 1.1\ntier 1.1 executor\n"
        _make_change(self.root, "add-ping", tasks, waves)
        items = T.build(self.root, "add-ping")
        self.assertEqual(
            items[0],
            {"content": "0.1 Setup", "status": "pending", "priority": "medium"},
        )

    def test_ungrouped_task_in_current_wave_gets_fix_suffix(self):
        tasks = "- [ ] 0.1 Setup\n## 1. Core\n- [ ] 1.1 A\n"
        waves = "wave 1: 0.1 1.1\ntier 0.1 executor\n"
        change = _make_change(self.root, "add-ping", tasks, waves)
        _report(change, "0.1", "## Attempt 1\nVerdict: NOT COMPLIANT\n")
        items = T.build(self.root, "add-ping")
        self.assertEqual(
            items[0],
            {"content": "0.1 Setup (fix)", "status": "in_progress", "priority": "high"},
        )

    def test_group_expands_when_a_checked_task_is_in_the_current_wave(self):
        tasks = "## 1. Core\n- [x] 1.1 A\n- [ ] 1.2 B\n## 2. Flow\n- [ ] 2.1 C\n"
        waves = "wave 1: 1.1 2.1\nwave 2: 1.2\n"
        _make_change(self.root, "add-ping", tasks, waves)
        items = T.build(self.root, "add-ping")
        self.assertEqual(
            items,
            [
                {"content": "1.1 A", "status": "completed", "priority": "low"},
                {"content": "1.2 B", "status": "pending", "priority": "medium"},
                {"content": "2.1 C", "status": "in_progress", "priority": "high"},
            ],
        )

    def test_waves_with_no_current_wave_collapses_every_group(self):
        tasks = "## 1. Core\n- [x] 1.1 A\n- [ ] 1.2 B\n"
        waves = "wave 1: 1.1\ntier 1.1 executor\n"
        _make_change(self.root, "add-ping", tasks, waves)
        items = T.build(self.root, "add-ping")
        self.assertEqual(
            items,
            [{"content": "1. Core (1/2)", "status": "pending", "priority": "medium"}],
        )


class Subprocess(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)

    def _run(self, slug):
        return subprocess.run(
            [sys.executable, str(REPO / "bin/change-todos"), str(self.root), slug],
            capture_output=True,
            text=True,
        )

    def test_two_runs_are_byte_identical_and_keys_are_exact(self):
        tasks = (
            "- [ ] 0.1 Setup\n"
            "## 1. Core\n"
            "- [x] 1.1 Parse tasks\n"
            "- [ ] 1.2 Collapse groups\n"
        )
        _make_change(self.root, "add-ping", tasks)
        first = self._run("add-ping")
        second = self._run("add-ping")
        self.assertEqual(first.returncode, 0)
        self.assertEqual(second.returncode, 0)
        self.assertEqual(first.stdout, second.stdout)
        items = json.loads(first.stdout)
        self.assertTrue(items)
        for entry in items:
            self.assertEqual(set(entry.keys()), {"content", "status", "priority"})

    def test_run_leaves_the_change_directory_tree_unchanged(self):
        tasks = (
            "- [ ] 0.1 Setup\n"
            "## 1. Core\n"
            "- [x] 1.1 Parse tasks\n"
            "- [ ] 1.2 Collapse groups\n"
        )
        _make_change(self.root, "add-ping", tasks)
        before = _tree(self.root)
        result = self._run("add-ping")
        after = _tree(self.root)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(before, after)

    def test_run_does_not_write_change_state_bytecode(self):
        _make_change(self.root, "add-ping", "## 1. Core\n- [x] 1.1 Parse tasks\n")
        pycache_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, pycache_dir, True)
        # A fresh PYTHONPYCACHEPREFIX with PYTHONDONTWRITEBYTECODE unset from the
        # parent test process's environment isolates this from bytecode either one
        # already wrote, so the script's own dont_write_bytecode is what is tested.
        env = dict(os.environ, PYTHONPYCACHEPREFIX=str(pycache_dir))
        env.pop("PYTHONDONTWRITEBYTECODE", None)
        result = subprocess.run(
            [sys.executable, str(REPO / "bin/change-todos"), str(self.root), "add-ping"],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0)
        # A fresh PYTHONPYCACHEPREFIX makes the interpreter recompile its own
        # startup imports (encodings, copyreg, ...) into pycache_dir too, so
        # asserting the directory is empty fails regardless of this script;
        # only bin/change-state's own cache entry is under this fix's control.
        change_state_pyc = [p for p in pycache_dir.rglob("*.pyc") if "change-state" in p.name]
        self.assertEqual(change_state_pyc, [])

    def test_no_tasks_file_exits_one_with_empty_stdout_and_one_stderr_line(self):
        (self.root / "openspec" / "changes" / "add-ping").mkdir(parents=True)
        result = self._run("add-ping")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        lines = result.stderr.splitlines()
        self.assertEqual(len(lines), 1)
        self.assertIn("no tasks.md in", lines[0])

    def test_missing_change_directory_exits_one_with_empty_stdout_and_one_stderr_line(self):
        result = self._run("no-such-change")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        lines = result.stderr.splitlines()
        self.assertEqual(len(lines), 1)
        self.assertIn("no change directory", lines[0])


if __name__ == "__main__":
    unittest.main()
