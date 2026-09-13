import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
import tempfile
import unittest

from workspace_helpers import create_workspace, run_check

RULES = ("work-record", "adr")
SHA = "0123456789abcdef0123456789abcdef01234567"
SECTIONS = "\n## Changed\n\nx\n\n## Decisions\n\nx\n\n## Open questions\n\nx\n\n## Verification\n\nx\n"


def record(task="TASK-1", repos="repos:\n  - demo", body=SECTIONS):
    return (
        "---\ntask: %s\n%s\nmerge_requests: []\ncommits:\n  - demo@%s\n---\n%s" % (task, repos, SHA, body)
    )


def adr(number="0001", status="proposed", affects="[]", extra=""):
    return (
        "---\nkey: adr:%s\ntitle: X\nstatus: %s\ndate: 2026-09-13\naffects: %s\n%s---\n"
        "\n## Context\n\n## Decision\n\n## Alternatives\n\n## Consequences\n" % (number, status, affects, extra)
    )


class CheckRecordsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.ws = create_workspace(self.tmp)
        self.write(
            "repos.json",
            json.dumps({"repositories": [{
                "name": "demo", "remote": "git@x:demo.git", "forge": "gitlab", "default_branch": "main",
                "roles": ["backend"], "summary": "Service"}]}, indent=2) + "\n",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text):
        path = self.ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def findings(self, rule):
        code, lines, stderr = run_check(self.ws)
        self.assertNotIn("Traceback", stderr)
        self.assertNotEqual(code, 2, stderr)
        return [line for line in lines if len(line.split(" ")) > 1 and line.split(" ")[1] == rule]

    def test_fresh_workspace_has_none(self):
        self.assertTrue((self.ws / "work/.gitkeep").is_file())
        self.assertTrue((self.ws / "docs/adr/.gitkeep").is_file())
        for rule in RULES:
            self.assertEqual(self.findings(rule), [], rule)

    def test_valid_record(self):
        self.write("work/TASK-1/record.md", record())
        self.assertEqual(self.findings("work-record"), [])

    def test_unknown_repository(self):
        self.write("work/TASK-1/record.md", record(repos="repos: [ghost]"))
        lines = self.findings("work-record")
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("ghost", lines[0])

    def test_non_string_repository_names_are_ignored(self):
        self.write(
            "repos.json",
            json.dumps({"repositories": [
                {"name": ["x"]}, {"name": {"a": 1}}, {"name": None}, {"name": 5},
                {"name": "demo", "remote": "git@x:demo.git", "forge": "gitlab", "default_branch": "main",
                 "roles": ["backend"], "summary": "Service"}]}, indent=2) + "\n",
        )
        self.write("work/TASK-1/record.md", record())
        self.assertEqual(self.findings("work-record"), [])
        self.write("work/TASK-1/record.md", record(repos="repos: [ghost]"))
        self.assertEqual(len(self.findings("work-record")), 1)

    def test_directory_name_does_not_match(self):
        self.write("work/NOPE/record.md", record(task="NOPE"))
        self.assertNotEqual(self.findings("work-record"), [])

    def test_directory_without_record(self):
        self.write("work/TASK-2/notes.md", "# Notes\n")
        self.assertEqual(len(self.findings("work-record")), 1)

    def test_uncompilable_id_pattern_skips_name_check(self):
        from wslib.common import Context
        from wslib.rules_records import check_work_record

        self.write("tracker/tracker.json", json.dumps({"id_pattern": "a{4294967296}", "url": "x/{id}"}) + "\n")
        self.write("work/NOPE/record.md", record(task="NOPE"))
        self.assertEqual(check_work_record(Context(self.ws)), [])

    def test_task_differs_from_directory(self):
        self.write("work/TASK-2/record.md", record(task="TASK-3"))
        self.assertEqual(len(self.findings("work-record")), 1)

    def test_missing_verification_section(self):
        body = SECTIONS.split("\n## Verification")[0] + "\n"
        self.write("work/TASK-1/record.md", record(body=body))
        lines = self.findings("work-record")
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("Verification", lines[0])

    def test_section_inside_code_fence_does_not_count(self):
        body = SECTIONS.split("\n## Verification")[0] + "\n```\n## Verification\n```\n"
        self.write("work/TASK-1/record.md", record(body=body))
        self.assertEqual(len(self.findings("work-record")), 1)

    def test_missing_key(self):
        text = record().replace("merge_requests: []\n", "")
        self.write("work/TASK-1/record.md", text)
        self.assertEqual(len(self.findings("work-record")), 1)

    def test_repos_not_a_list(self):
        self.write("work/TASK-1/record.md", record(repos="repos: demo"))
        self.assertEqual(len(self.findings("work-record")), 1)

    def test_broken_frontmatter(self):
        self.write("work/TASK-1/record.md", record().replace("merge_requests: []", "merge_requests [oops"))
        lines = self.findings("work-record")
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("frontmatter line", lines[0])
        self.assertTrue(lines[0].startswith("work/TASK-1/record.md:5 "), lines)

    def test_accepted_without_approval(self):
        self.write("docs/adr/0001-x.md", adr(status="accepted"))
        self.assertEqual(len(self.findings("adr")), 1)

    def test_accepted_with_approval(self):
        self.write("docs/adr/0001-x.md", adr(status="accepted", extra="approved: {by: alice, date: 2026-09-13}\n"))
        self.assertEqual(self.findings("adr"), [])

    def test_bad_file_name(self):
        self.write("docs/adr/12-x.md", adr(number="12"))
        self.assertNotEqual(self.findings("adr"), [])

    def test_duplicate_number(self):
        self.write("docs/adr/0002-a.md", adr(number="0002"))
        self.write("docs/adr/0002-b.md", adr(number="0002"))
        lines = self.findings("adr")
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("docs/adr/0002-b.md:1 "), lines)

    def test_unknown_status(self):
        self.write("docs/adr/0001-x.md", adr(status="draft"))
        self.assertEqual(len(self.findings("adr")), 1)

    def test_status_list_is_reported(self):
        self.write("docs/adr/0001-x.md", adr(status="[accepted]"))
        lines = self.findings("adr")
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("status", lines[0])

    def test_status_block_mapping_is_reported(self):
        self.write("docs/adr/0001-x.md", adr(status="\n  a: b"))
        lines = self.findings("adr")
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("status", lines[0])

    def test_unresolved_affects(self):
        self.write("docs/adr/0001-x.md", adr(affects="[domain:ghost]"))
        lines = self.findings("adr")
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("domain:ghost", lines[0])

    def test_affects_existing_adr(self):
        self.write("docs/adr/0001-x.md", adr(affects="[adr:0002]"))
        self.assertEqual(len(self.findings("adr")), 1)
        self.write("docs/adr/0002-y.md", adr(number="0002"))
        self.assertEqual(self.findings("adr"), [])


if __name__ == "__main__":
    unittest.main()
