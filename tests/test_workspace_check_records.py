import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
import tempfile
import unittest

from workspace_helpers import create_workspace, run_check

RULES = ("work-record", "task-state", "adr")
SHA = "0123456789abcdef0123456789abcdef01234567"
STORY_DIR = "projects/abs/domains/ops/streams/a/stories/card"
STORY_REL = STORY_DIR + "/story.md"
TASK_DIR = "tasks/e2e-checkout"
TASK_REL = TASK_DIR + "/task.md"
SECTIONS = "\n## Changed\n\nx\n\n## Decisions\n\nx\n\n## Open questions\n\nNone.\n\n## Verification\n\nx\n"
QUESTIONS_BODY = SECTIONS.replace("None.", "Who signs?")


def work_md(
    repos="repos: [demo]",
    merge_requests="merge_requests: [demo!42]",
    commits="commits:\n  - demo@%s" % SHA,
    recorded="recorded: 2026-09-13",
    body=SECTIONS,
):
    keys = "\n".join(part for part in (repos, merge_requests, commits, recorded) if part)
    return "---\n%s\n---\n%s" % (keys, body)


def story(status="waiting", owner="", started=""):
    return (
        "---\nkey: story:abs/ops/card\ntype: story\nstatus: %s\nowner: %s\nstarted: %s\ntracker: TASK-1\n---\n"
        "\n# Card\n\n## Goal\n\nx\n\n## Open questions\n\nNone.\n" % (status, owner, started)
    )


def task(status="waiting"):
    return (
        "---\nkey: task:e2e-checkout\ntype: e2e\nstatus: %s\nowner:\nstarted:\ntracker:\n---\n"
        "\n# E2E checkout\n\n## Goal\n\nx\n" % status
    )


def adr(number="0001", status="proposed", affects="[]", extra=""):
    return (
        "---\nkey: adr:%s\ntitle: X\nstatus: %s\ndate: 2026-09-13\naffects: %s\n%s---\n"
        "\n## Context\n\n## Decision\n\n## Alternatives\n\n## Consequences\n" % (number, status, affects, extra)
    )


class RecordsBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.ws = create_workspace(self.tmp)
        self.write("repos.json", json.dumps({"repositories": [{"name": "demo"}]}, indent=2) + "\n")

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


class WorkRecordTest(RecordsBase):
    def test_fresh_workspace_has_none(self):
        self.assertEqual(self.findings("work-record"), [])
        self.assertEqual(self.findings("task-state"), [])

    def test_valid_record_in_done_task_folder(self):
        self.write(TASK_REL, task("done"))
        self.write(TASK_DIR + "/work.md", work_md())
        self.assertEqual(self.findings("work-record"), [])
        self.assertEqual(self.findings("task-state"), [])

    def test_valid_record_in_done_story_folder(self):
        self.write(STORY_REL, story("done"))
        self.write(STORY_DIR + "/work.md", work_md())
        self.assertEqual(self.findings("work-record"), [])
        self.assertEqual(self.findings("task-state"), [])

    def test_unknown_repository(self):
        self.write(TASK_REL, task("done"))
        self.write(TASK_DIR + "/work.md", work_md(repos="repos: [ghost]"))
        lines = self.findings("work-record")
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(TASK_DIR + "/work.md:1 "), lines)
        self.assertIn("ghost", lines[0])

    def test_non_string_repository_names_are_ignored(self):
        self.write(
            "repos.json",
            json.dumps({"repositories": [
                {"name": ["x"]}, {"name": {"a": 1}}, {"name": None}, {"name": 5}, {"name": "demo"},
            ]}, indent=2) + "\n",
        )
        self.write(TASK_REL, task("done"))
        self.write(TASK_DIR + "/work.md", work_md())
        self.assertEqual(self.findings("work-record"), [])
        self.write(TASK_DIR + "/work.md", work_md(repos="repos: [ghost]"))
        self.assertEqual(len(self.findings("work-record")), 1)

    def test_missing_keys(self):
        self.write(TASK_REL, task("done"))
        for key in ("repos", "merge_requests", "commits", "recorded"):
            self.write(TASK_DIR + "/work.md", work_md(**{key: ""}))
            lines = self.findings("work-record")
            self.assertEqual(len(lines), 1, (key, lines))
            self.assertIn(key, lines[0])

    def test_missing_sections(self):
        self.write(STORY_REL, story("done"))
        for section in ("Changed", "Decisions", "Open questions", "Verification"):
            self.write(STORY_DIR + "/work.md", work_md(body=SECTIONS.replace("## %s" % section, "## Dropped", 1)))
            lines = self.findings("work-record")
            self.assertEqual(len(lines), 1, (section, lines))
            self.assertIn(section, lines[0])

    def test_section_inside_code_fence_does_not_count(self):
        self.write(STORY_REL, story("done"))
        body = SECTIONS.split("\n## Verification")[0] + "\n```\n## Verification\n```\n"
        self.write(STORY_DIR + "/work.md", work_md(body=body))
        self.assertEqual(len(self.findings("work-record")), 1)

    def test_recorded_not_a_date(self):
        self.write(TASK_REL, task("done"))
        self.write(TASK_DIR + "/work.md", work_md(recorded="recorded: 13.09.2026"))
        lines = self.findings("work-record")
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("recorded", lines[0])

    def test_recorded_impossible_date(self):
        self.write(TASK_REL, task("done"))
        self.write(TASK_DIR + "/work.md", work_md(recorded="recorded: 2026-02-30"))
        self.assertEqual(len(self.findings("work-record")), 1)

    def test_repos_not_a_list(self):
        self.write(TASK_REL, task("done"))
        self.write(TASK_DIR + "/work.md", work_md(repos="repos: demo"))
        self.assertEqual(len(self.findings("work-record")), 1)

    def test_broken_frontmatter(self):
        self.write(TASK_REL, task("done"))
        self.write(TASK_DIR + "/work.md", work_md(merge_requests="merge_requests [oops"))
        lines = self.findings("work-record")
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("frontmatter line 3", lines[0])
        self.assertTrue(lines[0].startswith(TASK_DIR + "/work.md:3 "), lines)

    def test_work_md_outside_task_folder(self):
        rels = ("work/TASK-1/work.md", "tasks/e2e-checkout/extra/work.md", "tasks/lonely/work.md")
        for rel in rels:
            self.write(rel, work_md())
        lines = self.findings("work-record")
        self.assertEqual(sorted(line.split(":")[0] for line in lines), sorted(rels), lines)
        self.assertTrue(all("outside a task folder" in line for line in lines), lines)

    def test_kit_template_work_md_is_not_a_record(self):
        # .agents/templates/ is kit infrastructure: its work.md is the record template, not a record.
        self.write(".agents/templates/work.md", work_md())
        self.assertEqual(self.findings("work-record"), [])


class TaskStateTest(RecordsBase):
    def test_done_story_without_record(self):
        self.write(STORY_REL, story("done"))
        lines = self.findings("task-state")
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(STORY_REL + ":1 "), lines)

    def test_done_task_without_record(self):
        self.write(TASK_REL, task("done"))
        lines = self.findings("task-state")
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(TASK_REL + ":1 "), lines)

    def test_waiting_story_without_record_passes(self):
        self.write(STORY_REL, story("waiting"))
        self.assertEqual(self.findings("task-state"), [])
        self.assertEqual(self.findings("work-record"), [])

    def test_record_with_in_progress_status_is_orphan(self):
        # owner and started are filled: the in_progress coupling belongs to the task-state rule of rules_tasks.
        self.write(STORY_REL, story("in_progress", owner="anna", started="2026-09-01"))
        self.write(STORY_DIR + "/work.md", work_md())
        lines = self.findings("task-state")
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(STORY_DIR + "/work.md:1 "), lines)
        self.assertEqual(self.findings("work-record"), [])

    def test_done_with_empty_merge_requests(self):
        self.write(TASK_REL, task("done"))
        self.write(TASK_DIR + "/work.md", work_md(merge_requests="merge_requests: []"))
        lines = self.findings("task-state")
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("merge_requests", lines[0])
        self.assertEqual(self.findings("work-record"), [])

    def test_done_with_open_questions(self):
        self.write(STORY_REL, story("done"))
        self.write(STORY_DIR + "/work.md", work_md(body=QUESTIONS_BODY))
        lines = self.findings("task-state")
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("Open questions", lines[0])
        self.assertEqual(self.findings("work-record"), [])

    def test_unreadable_task_file_is_no_orphan_cascade(self):
        # Path-based discovery keeps the folder a task folder, so the record is validated as a record;
        # the status is unknowable, so it must not cascade into an orphan finding for the valid work.md.
        path = self.ws / STORY_DIR / "story.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\xff\xfe not utf-8")
        self.write(STORY_DIR + "/work.md", work_md())
        self.assertEqual(self.findings("task-state"), [])
        self.assertEqual(self.findings("work-record"), [])


class AdrTest(RecordsBase):
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
