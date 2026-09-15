import contextlib
import importlib.machinery
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock
from datetime import date, datetime
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "lib"))

U = importlib.machinery.SourceFileLoader("ov_usage", str(REPO / "bin/ov-usage")).load_module()

_ORIGINAL_TZNAME = time.tzname


def tearDownModule():
    # guards every UtcTestCase-derived test: the process timezone must be back to what it
    # was before this module ran, regardless of which of those tests ran last.
    if time.tzname != _ORIGINAL_TZNAME:
        raise AssertionError(f"process timezone not restored: expected {_ORIGINAL_TZNAME}, got {time.tzname}")


def git(repo, *args, env=None):
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", *args],
        cwd=repo, check=True, capture_output=True, env=env,
    )


class DayListTests(unittest.TestCase):
    def test_last_n_days_ascending(self):
        self.assertEqual(
            U.day_list(date(2026, 9, 16), 3),
            ["2026-09-14", "2026-09-15", "2026-09-16"],
        )


class LoadUsageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_missing_file_returns_none(self):
        self.assertIsNone(U.load_usage(self.tmp / "usage.jsonl"))

    def test_malformed_lines_are_skipped(self):
        path = self.tmp / "usage.jsonl"
        path.write_text('{"date": "2026-09-15", "vlm_calls": 1}\nnot json\n\n')
        self.assertEqual(U.load_usage(path), [{"date": "2026-09-15", "vlm_calls": 1}])

    def test_non_utf8_content_is_unreadable(self):
        path = self.tmp / "usage.jsonl"
        path.write_bytes(b"\xff\xfe")
        self.assertIsNone(U.load_usage(path))


class UsageByDayTests(unittest.TestCase):
    def test_delta_with_reindex_shown_not_added(self):
        lines = [
            {"date": "2026-09-15", "vlm_calls": 2210, "embedding_calls": 2500, "add_resource_tasks": 50},
            {"date": "2026-09-16", "vlm_calls": 2260, "embedding_calls": 2600, "add_resource_tasks": 52},
            {"date": "2026-09-15", "reindex_vlm": 7},
        ]
        days = ["2026-09-15", "2026-09-16"]
        result = U.usage_by_day(lines, days)
        self.assertEqual(result, {"2026-09-15": {"vlm": 50, "reindex": 7, "embed": 100, "imports": 2}})
        self.assertNotIn("2026-09-16", result)

    def test_reindex_cost_is_not_counted_twice(self):
        lines = [
            {"date": "2026-09-15", "vlm_calls": 2210, "embedding_calls": 2500, "add_resource_tasks": 50},
            {"date": "2026-09-15", "reindex_vlm": 12},
            {"date": "2026-09-16", "vlm_calls": 2260, "embedding_calls": 2600, "add_resource_tasks": 52},
        ]
        result = U.usage_by_day(lines, ["2026-09-15", "2026-09-16"])
        self.assertEqual(result["2026-09-15"]["vlm"], 50)
        self.assertEqual(result["2026-09-15"]["reindex"], 12)

    def test_reindex_is_zero_when_no_reindex_line_but_snapshot_numbers_exist(self):
        lines = [
            {"date": "2026-09-15", "vlm_calls": 2210, "embedding_calls": 2500, "add_resource_tasks": 50},
            {"date": "2026-09-16", "vlm_calls": 2260, "embedding_calls": 2600, "add_resource_tasks": 52},
        ]
        result = U.usage_by_day(lines, ["2026-09-15", "2026-09-16"])
        self.assertEqual(result["2026-09-15"], {"vlm": 50, "reindex": 0, "embed": 100, "imports": 2})

    def test_unavailable_line_breaks_the_pair(self):
        lines = [
            {"date": "2026-09-15", "vlm_calls": 2210, "embedding_calls": 2500, "add_resource_tasks": 50},
            {"date": "2026-09-16", "unavailable": True},
        ]
        result = U.usage_by_day(lines, ["2026-09-15", "2026-09-16"])
        self.assertNotIn("2026-09-15", result)
        self.assertNotIn("2026-09-16", result)

    def test_counter_decrease_gives_no_numbers(self):
        lines = [
            {"date": "2026-09-15", "vlm_calls": 2210, "embedding_calls": 2500, "add_resource_tasks": 50},
            {"date": "2026-09-16", "vlm_calls": 100, "embedding_calls": 2600, "add_resource_tasks": 52},
        ]
        result = U.usage_by_day(lines, ["2026-09-15", "2026-09-16"])
        self.assertNotIn("2026-09-15", result)

    def test_non_dict_line_is_skipped(self):
        lines = [
            5,
            "not an object",
            {"date": "2026-09-15", "vlm_calls": 1, "embedding_calls": 1, "add_resource_tasks": 1},
        ]
        # nothing to crash on and no pair to compute a delta from
        self.assertEqual(U.usage_by_day(lines, ["2026-09-15"]), {})

    def test_reindex_line_without_date_is_skipped(self):
        lines = [
            {"reindex_vlm": 5},
            {"date": "2026-09-15", "vlm_calls": 1, "embedding_calls": 1, "add_resource_tasks": 1},
            {"date": "2026-09-16", "vlm_calls": 2, "embedding_calls": 2, "add_resource_tasks": 2},
        ]
        result = U.usage_by_day(lines, ["2026-09-15", "2026-09-16"])
        self.assertEqual(result["2026-09-15"]["reindex"], 0)

    def test_incomplete_snapshot_is_treated_as_absent(self):
        lines = [
            {"date": "2026-09-15", "vlm_calls": 1, "embedding_calls": 1, "add_resource_tasks": 1},
            {"date": "2026-09-16", "vlm_calls": 2},  # missing embedding_calls and add_resource_tasks
            {"date": "2026-09-17", "vlm_calls": 3, "embedding_calls": 3, "add_resource_tasks": 3},
        ]
        result = U.usage_by_day(lines, ["2026-09-15", "2026-09-16", "2026-09-17"])
        self.assertEqual(result, {})

    def test_reindex_vlm_non_int_value_is_ignored(self):
        lines = [
            {"date": "2026-09-15", "vlm_calls": 1, "embedding_calls": 1, "add_resource_tasks": 1},
            {"date": "2026-09-15", "reindex_vlm": None},
            {"date": "2026-09-16", "vlm_calls": 2, "embedding_calls": 2, "add_resource_tasks": 2},
        ]
        result = U.usage_by_day(lines, ["2026-09-15", "2026-09-16"])
        self.assertEqual(result["2026-09-15"], {"vlm": 1, "reindex": 0, "embed": 1, "imports": 1})

    def test_string_vlm_calls_treated_as_missing_snapshot(self):
        lines = [
            {"date": "2026-09-15", "vlm_calls": "2210", "embedding_calls": 1, "add_resource_tasks": 1},
            {"date": "2026-09-16", "vlm_calls": 2, "embedding_calls": 2, "add_resource_tasks": 2},
        ]
        self.assertEqual(U.usage_by_day(lines, ["2026-09-15", "2026-09-16"]), {})

    def test_bool_vlm_calls_treated_as_missing_snapshot(self):
        lines = [
            {"date": "2026-09-15", "vlm_calls": True, "embedding_calls": 1, "add_resource_tasks": 1},
            {"date": "2026-09-16", "vlm_calls": 2, "embedding_calls": 2, "add_resource_tasks": 2},
        ]
        self.assertEqual(U.usage_by_day(lines, ["2026-09-15", "2026-09-16"]), {})

    def test_non_string_date_is_skipped(self):
        lines = [
            {"date": ["x"], "reindex_vlm": 1},
            {"date": "2026-09-15", "vlm_calls": 1, "embedding_calls": 1, "add_resource_tasks": 1},
            {"date": "2026-09-16", "vlm_calls": 2, "embedding_calls": 2, "add_resource_tasks": 2},
        ]
        result = U.usage_by_day(lines, ["2026-09-15", "2026-09-16"])
        # a non-string "date" must be treated as absent, same as a missing "date" key
        self.assertEqual(result["2026-09-15"]["reindex"], 0)


class MemoryByDayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.specs = self.tmp / "specs"
        self.specs.mkdir()

    def make_commit_repo(self):
        repo = self.specs / "demo"
        repo.mkdir()
        git(repo, "init")
        return repo

    def commit(self, repo, rel, content, when):
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        existing = p.read_text() if p.exists() else ""
        p.write_text(existing + content)
        env = dict(os.environ, GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
        git(repo, "add", "-A", env=env)
        git(repo, "commit", "-m", "memory", env=env)

    def test_counts_used_and_rederived_and_ignores_removed_lines(self):
        repo = self.make_commit_repo()
        self.commit(
            repo, "log.md",
            'Memory: query="x" hits=3 used=yes rederived=architecture/adr/005-memory-as-derived-index.md\n',
            "2026-09-15T12:00:00",
        )
        self.commit(
            repo, "log.md",
            'Memory: query="y" hits=0 used=no rederived=none\nsome unrelated line\n',
            "2026-09-15T12:00:00",
        )
        # a later commit removes the first line; it must not be counted again
        text = (repo / "log.md").read_text()
        (repo / "log.md").write_text(text.replace('Memory: query="x" hits=3 used=yes rederived=architecture/adr/005-memory-as-derived-index.md\n', ""))
        env = dict(os.environ, GIT_AUTHOR_DATE="2026-09-16T09:00:00", GIT_COMMITTER_DATE="2026-09-16T09:00:00")
        git(repo, "add", "-A", env=env)
        git(repo, "commit", "-m", "remove x", env=env)

        result = U.memory_by_day(self.specs, subprocess.run, "2026-09-01")
        self.assertEqual(result["2026-09-15"], {"memory": 2, "used": 1, "rederived": 1})
        self.assertNotIn("2026-09-16", result)

    def test_ignores_hidden_and_symlink_and_non_git_directories(self):
        repo = self.make_commit_repo()
        self.commit(repo, "log.md", 'Memory: query="counted" hits=1 used=yes rederived=none\n', "2026-09-15T12:00:00")

        hidden = self.specs / ".hidden"
        hidden.mkdir()
        git(hidden, "init")
        self.commit(hidden, "log.md", 'Memory: query="hidden" hits=1 used=yes rederived=none\n', "2026-09-15T12:00:00")

        (self.specs / "no-git").mkdir()

        outside = self.tmp / "outside"
        outside.mkdir()
        git(outside, "init")
        self.commit(outside, "log.md", 'Memory: query="outside" hits=1 used=yes rederived=none\n', "2026-09-15T12:00:00")
        try:
            (self.specs / "link").symlink_to(outside)
        except OSError:
            self.skipTest("symlinks are not available on this platform")

        result = U.memory_by_day(self.specs, subprocess.run, "2026-09-01")
        # only the "demo" repo's commit counts; the hidden repo, the non-git dir and the
        # symlinked repo outside specs must all be ignored
        self.assertEqual(result, {"2026-09-15": {"memory": 1, "used": 1, "rederived": 0}})

    def test_missing_specs_dir_returns_none(self):
        self.assertIsNone(U.memory_by_day(self.tmp / "does-not-exist", subprocess.run, "2026-09-01"))

    def test_rederived_line_counts_separately_from_the_memory_line(self):
        repo = self.make_commit_repo()
        self.commit(repo, "log.md", 'Memory: query="x" hits=2 used=no rederived=none\n', "2026-09-15T09:00:00")
        self.commit(repo, "log.md", 'Rederived: architecture/adr/005-memory-as-derived-index.md\n', "2026-09-15T15:00:00")
        result = U.memory_by_day(self.specs, subprocess.run, "2026-09-01")
        self.assertEqual(result["2026-09-15"], {"memory": 1, "used": 0, "rederived": 1})

    def test_memory_error_line_is_neither_memory_nor_rederived(self):
        repo = self.make_commit_repo()
        self.commit(
            repo, "log.md",
            'Memory: query="x" hits=0 used=no rederived=none\nMemory error: boom\n',
            "2026-09-15T09:00:00",
        )
        result = U.memory_by_day(self.specs, subprocess.run, "2026-09-01")
        self.assertEqual(result["2026-09-15"], {"memory": 1, "used": 0, "rederived": 0})

    def test_since_uses_local_midnight_so_early_commits_on_first_day_are_kept(self):
        repo = self.make_commit_repo()
        self.commit(
            repo, "log.md",
            'Memory: query="early" hits=1 used=yes rederived=none\n',
            "2026-09-14T00:30:00",
        )
        result = U.memory_by_day(self.specs, subprocess.run, "2026-09-14")
        self.assertEqual(result["2026-09-14"]["memory"], 1)

    def test_os_error_from_run_is_skipped(self):
        self.make_commit_repo()

        def bad_run(*a, **k):
            raise OSError("boom")

        self.assertEqual(U.memory_by_day(self.specs, bad_run, "2026-09-01"), {})


class UtcTestCase(unittest.TestCase):
    """Pins the process timezone to UTC so local-day conversions are deterministic."""

    def setUp(self):
        super().setUp()
        patcher = unittest.mock.patch.dict(os.environ, {"TZ": "UTC"})
        patcher.start()
        # cleanups run LIFO: register time.tzset() first so it runs *after* patcher.stop()
        # restores TZ, re-syncing the C library timezone with the restored environment.
        self.addCleanup(time.tzset)
        self.addCleanup(patcher.stop)
        time.tzset()


class ReadsClaudeTests(UtcTestCase):
    def setUp(self):
        super().setUp()
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def make_line(self, timestamp, tool_names, with_content=True):
        if not with_content:
            return json.dumps({"timestamp": timestamp})
        content = [
            {"type": "tool_use", "id": f"id{i}", "name": name, "input": {}}
            for i, name in enumerate(tool_names)
        ]
        return json.dumps({"timestamp": timestamp, "message": {"content": content}})

    def test_counts_read_tools_by_local_day(self):
        session_dir = self.tmp / "projects" / "p1"
        session_dir.mkdir(parents=True)
        lines = [
            self.make_line("2026-09-15T10:00:00.000Z", ["mcp__openviking__find"]),
            self.make_line("2026-09-15T11:00:00.000Z", ["mcp__openviking__write"]),
            self.make_line("2026-09-16T09:00:00.000Z", ["mcp__openviking__search"]),
            "not json",
            self.make_line("2026-09-15T12:00:00.000Z", [], with_content=False),
        ]
        (session_dir / "s1.jsonl").write_text("\n".join(lines) + "\n")
        result = U.reads_claude(self.tmp / "projects", ["2026-09-15", "2026-09-16"])
        self.assertEqual(result, {"2026-09-15": 1, "2026-09-16": 1})

    def test_missing_directory_returns_none(self):
        self.assertIsNone(U.reads_claude(self.tmp / "does-not-exist", ["2026-09-15"]))

    def test_reads_outside_requested_days_are_not_counted(self):
        session_dir = self.tmp / "projects" / "p1"
        session_dir.mkdir(parents=True)
        lines = [
            self.make_line("2026-09-14T10:00:00.000Z", ["mcp__openviking__find"]),
            self.make_line("2026-09-15T10:00:00.000Z", ["mcp__openviking__find"]),
        ]
        (session_dir / "s1.jsonl").write_text("\n".join(lines) + "\n")
        result = U.reads_claude(self.tmp / "projects", ["2026-09-15"])
        self.assertEqual(result, {"2026-09-15": 1})

    def test_two_read_tool_uses_in_one_line_count_two(self):
        session_dir = self.tmp / "projects" / "p1"
        session_dir.mkdir(parents=True)
        line = self.make_line("2026-09-15T10:00:00.000Z", ["mcp__openviking__find", "mcp__openviking__search"])
        (session_dir / "s1.jsonl").write_text(line + "\n")
        result = U.reads_claude(self.tmp / "projects", ["2026-09-15"])
        self.assertEqual(result, {"2026-09-15": 2})

    def test_invalid_byte_in_one_line_skips_only_that_line(self):
        session_dir = self.tmp / "projects" / "p1"
        session_dir.mkdir(parents=True)
        good = self.make_line("2026-09-15T10:00:00.000Z", ["mcp__openviking__find"]).encode("utf-8")
        bad = (
            b'{"timestamp": "2026-09-15T11:00:00.000Z", "message": {"content": '
            b'[{"type": "tool_use", "name": "mcp__openviking__search", "input": {}}]}}\xff'
        )
        (session_dir / "s1.jsonl").write_bytes(good + b"\n" + bad + b"\n")
        result = U.reads_claude(self.tmp / "projects", ["2026-09-15"])
        self.assertEqual(result, {"2026-09-15": 1})


class ReadsOpencodeTests(UtcTestCase):
    def setUp(self):
        super().setUp()
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def make_db(self, rows, db_path=None):
        db_path = db_path or self.tmp / "opencode.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.execute("create table part (id text primary key, time_created integer not null, data text not null)")
        for i, (tool, ms) in enumerate(rows):
            data = json.dumps({"type": "tool", "tool": tool})
            # time_created is inlined as a SQL literal (not bound) because sqlite3's binder
            # raises OverflowError for out-of-int64-range values before SQLite ever sees them
            conn.execute(f"insert into part (id, time_created, data) values (?, {ms}, ?)", (f"id{i}", data))
        conn.commit()
        conn.close()
        return db_path

    def test_counts_openviking_read_tool_parts_by_local_day(self):
        ms = int(datetime(2026, 9, 15, 12, 0, 0).timestamp() * 1000)
        db_path = self.make_db([
            ("openviking_find", ms),
            ("openviking_read", ms),
            ("openviking_write", ms),
            ("read", ms),
        ])
        result = U.reads_opencode(db_path, ["2026-09-15", "2026-09-16"])
        self.assertEqual(result, {"2026-09-15": 2, "2026-09-16": 0})

    def test_missing_file_returns_none(self):
        self.assertIsNone(U.reads_opencode(self.tmp / "does-not-exist.db", ["2026-09-15"]))

    def test_database_without_part_table_returns_none(self):
        db_path = self.tmp / "empty.db"
        conn = sqlite3.connect(db_path)
        conn.execute("create table other (id text)")
        conn.commit()
        conn.close()
        self.assertIsNone(U.reads_opencode(db_path, ["2026-09-15"]))

    def test_reads_outside_requested_days_are_not_counted(self):
        ms_14 = int(datetime(2026, 9, 14, 12, 0, 0).timestamp() * 1000)
        ms_15 = int(datetime(2026, 9, 15, 12, 0, 0).timestamp() * 1000)
        db_path = self.make_db([("openviking_find", ms_14), ("openviking_find", ms_15)])
        result = U.reads_opencode(db_path, ["2026-09-15"])
        self.assertEqual(result, {"2026-09-15": 1})

    def test_abnormal_time_created_is_skipped(self):
        db_path = self.make_db([("openviking_find", 10**20)])
        result = U.reads_opencode(db_path, ["2026-09-15"])
        self.assertEqual(result, {"2026-09-15": 0})

    def test_db_path_with_space_in_directory_works(self):
        ms = int(datetime(2026, 9, 15, 12, 0, 0).timestamp() * 1000)
        db_path = self.make_db([("openviking_find", ms)], db_path=self.tmp / "has space" / "opencode.db")
        result = U.reads_opencode(db_path, ["2026-09-15"])
        self.assertEqual(result, {"2026-09-15": 1})


class RenderTests(unittest.TestCase):
    def capture(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            U.render(*args)
        return out.getvalue()

    def test_header_and_rows(self):
        days = ["2026-09-15", "2026-09-16"]
        usage = {"2026-09-15": {"vlm": 50, "reindex": 7, "embed": 100, "imports": 2}}
        memory = {"2026-09-15": {"memory": 2, "used": 1, "rederived": 1}}
        out = self.capture(days, usage, memory, None, None)
        lines = out.splitlines()
        self.assertEqual(lines[0], "date  vlm  reindex  embed  imports  reads_claude  reads_opencode  memory  used  rederived")
        self.assertEqual(lines[1], "2026-09-15  50  7  100  2  n/a  n/a  2  1  1")
        self.assertEqual(lines[2], "2026-09-16  n/a  n/a  n/a  n/a  n/a  n/a  0  0  0")

    def test_missing_sources_show_na(self):
        out = self.capture(["2026-09-15"], None, None, None, None)
        self.assertEqual(out.splitlines()[1], "2026-09-15  n/a  n/a  n/a  n/a  n/a  n/a  n/a  n/a  n/a")


class MainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.specs = self.tmp / "specs"
        self.specs.mkdir()

    def test_no_usage_file_exits_zero_and_prints_na(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = U.main(
                ["--days", "2"], home=self.tmp, specs=self.specs,
                today=date(2026, 9, 16), run=subprocess.run,
            )
        self.assertEqual(code, 0)
        rows = out.getvalue().splitlines()
        self.assertIn("2026-09-16  n/a  n/a  n/a  n/a", rows[-1])

    def test_bad_days_argument_returns_two(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = U.main(["--days", "x"])
        self.assertEqual(code, 2)

    def test_zero_days_returns_two_not_indexerror(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = U.main(["--days", "0"])
        self.assertEqual(code, 2)

    def test_negative_days_returns_two_not_indexerror(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = U.main(["--days", "-1"])
        self.assertEqual(code, 2)

    def write_usage(self, *lines):
        ov_dir = self.tmp / ".openviking"
        ov_dir.mkdir(parents=True, exist_ok=True)
        (ov_dir / "usage.jsonl").write_text("\n".join(json.dumps(line) for line in lines) + "\n")

    def run_main(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = U.main(
                ["--days", "1"], home=self.tmp, specs=self.specs,
                today=date(2026, 9, 15), run=subprocess.run,
            )
        return code, out.getvalue()

    def row_cells(self, out, day):
        for line in out.splitlines():
            if line.startswith(day):
                return line.split("  ")
        raise AssertionError(f"no row for {day} in output:\n{out}")

    def assert_usage_columns_na(self, out, day="2026-09-15"):
        # cells 1-4 are vlm, reindex, embed, imports (see COLUMNS)
        self.assertEqual(self.row_cells(out, day)[1:5], ["n/a", "n/a", "n/a", "n/a"])

    def test_non_object_usage_line_does_not_crash(self):
        self.write_usage(5, {"date": "2026-09-15", "vlm_calls": 1, "embedding_calls": 1, "add_resource_tasks": 1})
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assert_usage_columns_na(out)

    def test_reindex_line_without_date_does_not_crash(self):
        self.write_usage({"reindex_vlm": 5}, {"date": "2026-09-15", "vlm_calls": 1, "embedding_calls": 1, "add_resource_tasks": 1})
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assert_usage_columns_na(out)

    def test_incomplete_snapshot_line_does_not_crash(self):
        self.write_usage({"date": "2026-09-15", "vlm_calls": 1})
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assert_usage_columns_na(out)

    def test_non_utf8_usage_file_exits_zero_and_prints_na(self):
        ov_dir = self.tmp / ".openviking"
        ov_dir.mkdir(parents=True, exist_ok=True)
        (ov_dir / "usage.jsonl").write_bytes(b"\xff\xfe")
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assert_usage_columns_na(out)

    def test_reindex_vlm_null_does_not_crash(self):
        self.write_usage(
            {"date": "2026-09-15", "reindex_vlm": None},
            {"date": "2026-09-15", "vlm_calls": 1, "embedding_calls": 1, "add_resource_tasks": 1},
            {"date": "2026-09-16", "vlm_calls": 3, "embedding_calls": 5, "add_resource_tasks": 2},
        )
        code, out = self.run_main()
        self.assertEqual(code, 0)
        cells = self.row_cells(out, "2026-09-15")
        self.assertEqual(cells[1], "2")
        self.assertEqual(cells[2], "0")

    def test_non_string_date_line_does_not_crash(self):
        self.write_usage(
            {"date": ["x"], "reindex_vlm": 1},
            {"date": "2026-09-15", "vlm_calls": 1, "embedding_calls": 1, "add_resource_tasks": 1},
        )
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assert_usage_columns_na(out)

    def test_string_vlm_calls_does_not_crash(self):
        self.write_usage({"date": "2026-09-15", "vlm_calls": "2210", "embedding_calls": 1, "add_resource_tasks": 1})
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assert_usage_columns_na(out)

    def test_bool_vlm_calls_does_not_crash(self):
        self.write_usage({"date": "2026-09-15", "vlm_calls": True, "embedding_calls": 1, "add_resource_tasks": 1})
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assert_usage_columns_na(out)


class MainReadsTests(UtcTestCase):
    def setUp(self):
        super().setUp()
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.specs = self.tmp / "specs"
        self.specs.mkdir()

    def write_usage(self, *lines):
        ov_dir = self.tmp / ".openviking"
        ov_dir.mkdir(parents=True, exist_ok=True)
        (ov_dir / "usage.jsonl").write_text("\n".join(json.dumps(line) for line in lines) + "\n")

    def write_transcript(self, extra_content=None):
        session_dir = self.tmp / ".claude" / "projects" / "p1"
        session_dir.mkdir(parents=True)
        content = [{"type": "tool_use", "id": "1", "name": "mcp__openviking__find", "input": {}}]
        if extra_content is not None:
            content.append(extra_content)
        line = json.dumps({"timestamp": "2026-09-15T10:00:00.000Z", "message": {"content": content}})
        (session_dir / "s1.jsonl").write_text(line + "\n")

    def run_main(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = U.main(
                ["--days", "1"], home=self.tmp, specs=self.specs,
                today=date(2026, 9, 15), run=subprocess.run,
            )
        return code, out.getvalue()

    def test_reads_claude_numbers_reads_opencode_na_no_db(self):
        self.write_usage({"date": "2026-09-15", "vlm_calls": 1, "embedding_calls": 1, "add_resource_tasks": 1})
        self.write_transcript()
        code, out = self.run_main()
        self.assertEqual(code, 0)
        row = [line for line in out.splitlines() if line.startswith("2026-09-15")][0]
        cells = row.split("  ")
        self.assertEqual(cells[5], "1")
        self.assertEqual(cells[6], "n/a")

    def test_no_transcript_message_text_leaks_to_stdout(self):
        self.write_usage({"date": "2026-09-15", "vlm_calls": 1, "embedding_calls": 1, "add_resource_tasks": 1})
        self.write_transcript(extra_content={"type": "text", "text": "SECRET-TEXT"})
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertNotIn("SECRET-TEXT", out)


if __name__ == "__main__":
    unittest.main()
