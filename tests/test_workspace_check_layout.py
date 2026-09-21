import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
import subprocess
import tempfile
import unittest

from workspace_helpers import create_workspace, run_check

CHECK = REPO / "kits/workspace/tools/check.py"
RULES = ("layout", "json-shape")


def rule_lines(lines):
    """Keep only findings of this task's rules; other rule modules may add their own lines."""
    return [line for line in lines if len(line.split(" ")) > 1 and line.split(" ")[1] in RULES]


def write_json(ws, rel, obj):
    (ws / rel).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def repo_entry(name, remote, forge="gitlab"):
    return {"name": name, "remote": remote, "forge": forge, "default_branch": "main",
            "roles": ["backend"], "summary": "Service"}


def tracker_entry(key="task", pattern=r"TASK-\d+", url="https://tracker.example/i/{id}"):
    return {"key": key, "id_pattern": pattern, "url": url}


def write_trackers(ws, *entries):
    write_json(ws, "tracker/trackers.json", {"trackers": list(entries)})


class CheckLayoutTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.ws = create_workspace(self.tmp)
        # The kit templates still ship the old single-tracker file; the check rules already
        # require the new layout, so tests bridge the gap until the kit update lands.
        (self.ws / "STATUS.md").write_text("# STATUS\n", encoding="utf-8")
        write_trackers(self.ws, tracker_entry())

    def tearDown(self):
        self._tmp.cleanup()

    def findings(self):
        code, lines, stderr = run_check(self.ws)
        self.assertNotIn("Traceback", stderr)
        return code, rule_lines(lines)

    def assert_finding(self, lines, path, rule):
        matching = [line for line in lines if line.startswith(path + ":") and line.split(" ")[1] == rule]
        self.assertTrue(matching, f"no {rule} finding for {path} in {lines}")

    def test_fresh_workspace_has_no_layout_or_shape_findings(self):
        _, lines = self.findings()
        self.assertEqual(lines, [])

    def test_missing_agents_md(self):
        (self.ws / "AGENTS.md").unlink()
        code, lines = self.findings()
        self.assertEqual(code, 1)
        self.assertTrue(any(line.startswith("AGENTS.md:1 layout ") for line in lines), lines)

    def test_missing_status_md(self):
        (self.ws / "STATUS.md").unlink()
        code, lines = self.findings()
        self.assertEqual(code, 1)
        self.assert_finding(lines, "STATUS.md", "layout")

    def test_missing_trackers_json(self):
        (self.ws / "tracker/trackers.json").unlink()
        code, lines = self.findings()
        self.assertEqual(code, 1)
        self.assert_finding(lines, "tracker/trackers.json", "layout")

    def test_stray_file_under_projects_is_not_a_project(self):
        # The kit ships projects/.gitkeep, so projects/ already exists.
        (self.ws / "projects").mkdir(exist_ok=True)
        (self.ws / "projects/notes.md").write_text("notes\n", encoding="utf-8")
        _, lines = self.findings()
        self.assertEqual([line for line in lines if line.startswith("projects/")], [])

    def test_claude_md_ignored_by_git(self):
        # The kit's .gitignore re-includes CLAUDE.md with !CLAUDE.md, which outranks .git/info/exclude.
        gitignore = self.ws / ".gitignore"
        kept = [line for line in gitignore.read_text(encoding="utf-8").splitlines() if line != "!CLAUDE.md"]
        gitignore.write_text("\n".join(kept) + "\n", encoding="utf-8")
        with open(self.ws / ".git/info/exclude", "a", encoding="utf-8") as fh:
            fh.write("CLAUDE.md\n")
        _, lines = self.findings()
        self.assert_finding(lines, "CLAUDE.md", "layout")

    def test_broken_repos_json(self):
        (self.ws / "repos.json").write_text("{broken", encoding="utf-8")
        code, lines = self.findings()
        self.assertEqual(code, 1)
        self.assert_finding(lines, "repos.json", "json-shape")

    def test_invalid_forge(self):
        write_json(self.ws, "repos.json", {"repositories": [repo_entry("api", "git@x:api.git", "bitbucket")]})
        _, lines = self.findings()
        self.assert_finding(lines, "repos.json", "json-shape")

    def test_duplicate_repository_name(self):
        write_json(self.ws, "repos.json", {"repositories": [
            repo_entry("api", "git@x:api.git"), repo_entry("api", "git@x:api2.git")]})
        _, lines = self.findings()
        self.assert_finding(lines, "repos.json", "json-shape")

    def test_valid_repositories_have_no_findings(self):
        write_json(self.ws, "repos.json", {"repositories": [
            repo_entry("api", "git@x:api.git"), repo_entry("web", "git@x:web.git", "github")]})
        _, lines = self.findings()
        self.assertEqual([line for line in lines if line.startswith("repos.json:")], [])

    def repos_json_lines(self, entries):
        write_json(self.ws, "repos.json", {"repositories": entries})
        _, lines = self.findings()
        return [line for line in lines if line.startswith("repos.json:")]

    def test_planned_repository_without_remote(self):
        entry = repo_entry("mfe-abs-risks", "unused")
        del entry["remote"]
        entry["status"] = "planned"
        self.assertEqual(self.repos_json_lines([entry]), [])

    def test_active_repository_without_remote(self):
        entry = repo_entry("api", "unused")
        del entry["remote"]
        lines = self.repos_json_lines([entry])
        self.assertTrue(any(line.split(" ")[1] == "json-shape" and "remote" in line for line in lines), lines)

    def test_explicit_active_repository_without_remote(self):
        entry = repo_entry("api", "unused")
        del entry["remote"]
        entry["status"] = "active"
        self.assertTrue(self.repos_json_lines([entry]))

    def test_archived_status_is_reported(self):
        entry = repo_entry("api", "git@x:api.git")
        entry["status"] = "archived"
        lines = self.repos_json_lines([entry])
        self.assertTrue(any(line.split(" ")[1] == "json-shape" and "status" in line for line in lines), lines)

    def test_planned_repository_with_remote(self):
        entry = repo_entry("mfe-abs-risks", "git@x:risks.git")
        entry["status"] = "planned"
        self.assertEqual(self.repos_json_lines([entry, repo_entry("api", "git@x:api.git")]), [])

    def test_planned_repositories_without_remote_are_not_duplicates(self):
        first, second = repo_entry("a", "unused"), repo_entry("b", "unused")
        for entry in (first, second):
            del entry["remote"]
            entry["status"] = "planned"
        self.assertEqual(self.repos_json_lines([first, second]), [])

    def test_duplicate_remote_still_reported(self):
        planned = repo_entry("b", "git@x:api.git")
        planned["status"] = "planned"
        lines = self.repos_json_lines([repo_entry("a", "git@x:api.git"), planned])
        self.assertTrue(any("duplicate remote" in line for line in lines), lines)

    def test_tracker_url_without_id(self):
        write_trackers(self.ws, tracker_entry(url="https://t.example/i/"))
        _, lines = self.findings()
        self.assert_finding(lines, "tracker/trackers.json", "json-shape")

    def test_tracker_pattern_does_not_compile(self):
        write_trackers(self.ws, tracker_entry(pattern="(DEMO"))
        _, lines = self.findings()
        self.assert_finding(lines, "tracker/trackers.json", "json-shape")

    def test_tracker_pattern_overflows_compiler(self):
        # re.compile raises OverflowError here, not re.error.
        write_trackers(self.ws, tracker_entry(pattern="a{4294967296}"))
        code, lines = self.findings()
        self.assertEqual(code, 1)
        self.assert_finding(lines, "tracker/trackers.json", "json-shape")

    def test_empty_trackers_list(self):
        write_trackers(self.ws)
        _, lines = self.findings()
        self.assert_finding(lines, "tracker/trackers.json", "json-shape")

    def test_duplicate_tracker_key(self):
        write_trackers(self.ws, tracker_entry(), tracker_entry("task", r"BUG-\d+", "https://bugs.example/i/{id}"))
        _, lines = self.findings()
        self.assert_finding(lines, "tracker/trackers.json", "json-shape")

    def test_valid_trackers_list_passes(self):
        write_trackers(self.ws, tracker_entry(), tracker_entry("bug", r"BUG-\d+", "https://bugs.example/i/{id}"))
        _, lines = self.findings()
        self.assertEqual([line for line in lines if line.startswith("tracker/trackers.json:")], [])

    def test_project_without_project_md(self):
        (self.ws / "projects/billing").mkdir(parents=True)
        (self.ws / "projects/billing/README.md").write_text("Billing project\n", encoding="utf-8")
        code, lines = self.findings()
        self.assertEqual(code, 1)
        self.assert_finding(lines, "projects/billing/PROJECT.md", "layout")

    def test_project_md_present(self):
        (self.ws / "projects/billing").mkdir(parents=True)
        (self.ws / "projects/billing/PROJECT.md").write_text("Billing project\n", encoding="utf-8")
        _, lines = self.findings()
        self.assertEqual([line for line in lines if line.startswith("projects/")], [])

    def test_table_cell_characters_in_repository_fields(self):
        for field in ("name", "remote", "default_branch", "summary"):
            for bad in ("a|b", "a\nb"):
                with self.subTest(field=field, value=bad):
                    entry = repo_entry("api", "git@x:api.git")
                    entry[field] = bad
                    write_json(self.ws, "repos.json", {"repositories": [entry]})
                    _, lines = self.findings()
                    self.assert_finding(lines, "repos.json", "json-shape")

    def test_entry_without_roles_is_valid(self):
        entry = repo_entry("api", "git@x:api.git")
        del entry["roles"]
        self.assertEqual(self.repos_json_lines([entry]), [])

    def test_stand_key_without_prefix(self):
        write_json(self.ws, "environments.json", {"stands": [
            {"key": "stage", "purpose": "Testing", "access": "VPN", "services": {"api": "https://stage.example"}}]})
        _, lines = self.findings()
        self.assert_finding(lines, "environments.json", "json-shape")

    def test_stand_key_with_trailing_newline(self):
        write_json(self.ws, "environments.json", {"stands": [
            {"key": "stand:x\n", "purpose": "Testing", "access": "VPN", "services": {"api": "https://x.example"}}]})
        _, lines = self.findings()
        self.assert_finding(lines, "environments.json", "json-shape")

    def test_variable_name_with_trailing_newline(self):
        write_json(self.ws, ".agents/env.schema.json", {"variables": [
            {"name": "FOO\n", "issued_by": "Ops", "how_to_get": "Ask"}]})
        _, lines = self.findings()
        self.assert_finding(lines, ".agents/env.schema.json", "json-shape")

    def test_outside_workspace_exits_2(self):
        with tempfile.TemporaryDirectory() as empty:
            result = subprocess.run([sys.executable, str(CHECK)], cwd=empty, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)


if __name__ == "__main__":
    unittest.main()
