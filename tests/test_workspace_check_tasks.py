import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import datetime
import json
import tempfile
import unittest

from workspace_helpers import create_workspace, run_check

STREAM_REL = "projects/abs/domains/operations/streams/arm"
STORY_REL = STREAM_REL + "/stories/card/story.md"
TASK_REL = "tasks/e2e-checkout/task.md"
TODAY = datetime.date.today().isoformat()
TOMORROW = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()

STORY_BODY = (
    "\n## Goal\n\nx\n\n## Scope\n\nx\n\n## Acceptance criteria\n\nx\n"
    "\n## Verification\n\nx\n\n## Out of scope\n\nx\n\n## Open questions\n\nNone.\n"
)
TASK_BODY = "\n## Goal\n\nx\n\n## Open questions\n\nNone.\n"
STORY_FIELDS = [
    ("key", "story:abs/operations/card"),
    ("type", "story"),
    ("status", "waiting"),
    ("owner", ""),
    ("started", ""),
    ("wave", "1"),
    ("tracker", ""),
    ("scope", "[]"),
    ("depends", "[]"),
    ("repos", "[]"),
    ("decisions", "[]"),
    ("mockups", "[]"),
]
TASK_FIELDS = [
    ("key", "task:e2e-checkout"),
    ("type", "e2e"),
    ("status", "waiting"),
    ("owner", ""),
    ("started", ""),
    ("tracker", ""),
]
WORK_RECORD = """---
repos: []
merge_requests: [MR-1]
commits: []
recorded: %s
---
## Changed

x

## Decisions

x

## Open questions

None.

## Verification

x
""" % TODAY


def frontmatter(fields, overrides=None, drop=()):
    overrides = overrides or {}
    lines = []
    for name, value in fields:
        if name in drop:
            continue
        value = overrides.get(name, value)
        lines.append("%s: %s" % (name, value) if value != "" else "%s:" % name)
    return "---\n%s\n---\n" % "\n".join(lines)


class CheckTasksTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.ws = create_workspace(self.tmp)
        self.write(
            STREAM_REL + "/stream.json",
            json.dumps({
                "key": "stream:abs/operations/arm", "profile": "ui-migration", "stage": "goal",
                "scope": [], "approvals": []}, indent=2) + "\n",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text):
        path = self.ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def story(self, overrides=None, drop=(), slug="card"):
        rel = "%s/stories/%s/story.md" % (STREAM_REL, slug)
        fields = list(STORY_FIELDS)
        if slug != "card":
            fields = [(n, "story:abs/operations/%s" % slug if n == "key" else v) for n, v in fields]
        self.write(rel, frontmatter(fields, overrides, drop) + STORY_BODY)
        return rel

    def task(self, overrides=None, drop=(), slug="e2e-checkout"):
        rel = "tasks/%s/task.md" % slug
        fields = list(TASK_FIELDS)
        if slug != "e2e-checkout":
            fields = [(n, "task:%s" % slug if n == "key" else v) for n, v in fields]
        self.write(rel, frontmatter(fields, overrides, drop) + TASK_BODY)
        return rel

    def findings(self):
        code, lines, stderr = run_check(self.ws)
        self.assertNotIn("Traceback", stderr)
        self.assertNotEqual(code, 2, stderr)
        return [line for line in lines if len(line.split(" ")) > 1 and line.split(" ")[1] == "task-state"]

    def on_task_file(self, rel):
        return [line for line in self.findings() if line.startswith(rel + ":")]

    def assertOneOn(self, rel, fragment):
        lines = self.findings()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(rel + ":"), lines)
        self.assertIn(fragment, lines[0])

    def test_valid_story(self):
        self.story()
        self.assertEqual(self.findings(), [])

    def test_valid_workspace_task(self):
        self.task()
        self.assertEqual(self.findings(), [])

    def test_in_progress_with_owner_and_started(self):
        self.story({"status": "in_progress", "owner": "anna", "started": TODAY})
        self.assertEqual(self.findings(), [])

    def test_epic_story_inside_stream(self):
        self.story({"type": "epic"})
        self.assertEqual(self.findings(), [])

    def test_bad_status(self):
        rel = self.story({"status": "finished"})
        self.assertOneOn(rel, "finished")

    def test_missing_status(self):
        rel = self.story(drop=("status",))
        self.assertOneOn(rel, "status")

    def test_in_progress_without_owner(self):
        rel = self.task({"status": "in_progress", "started": TODAY})
        self.assertOneOn(rel, "owner")

    def test_in_progress_without_started(self):
        rel = self.task({"status": "in_progress", "owner": "anna"})
        self.assertOneOn(rel, "started")

    def test_in_progress_with_absent_owner(self):
        rel = self.task({"status": "in_progress", "started": TODAY}, drop=("owner",))
        self.assertOneOn(rel, "owner must not be empty")

    def test_in_progress_with_absent_started(self):
        rel = self.task({"status": "in_progress", "owner": "anna"}, drop=("started",))
        self.assertOneOn(rel, "started must not be empty")

    def test_waiting_with_owner(self):
        rel = self.story({"owner": "anna"})
        self.assertOneOn(rel, "owner")

    def test_waiting_with_started(self):
        rel = self.story({"started": TODAY})
        self.assertOneOn(rel, "started")

    def test_waiting_with_absent_owner_and_started(self):
        # A missing field counts as empty: waiting with no owner/started at all is valid.
        self.story(drop=("owner", "started"))
        self.assertEqual(self.findings(), [])

    def test_done_with_owner(self):
        rel = self.story({"status": "done", "owner": "anna"})
        # A done story without work.md also draws the record-consistency finding; assert only the owner one.
        lines = [line for line in self.findings() if line.startswith(rel + ":") and "owner" in line]
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("must be empty", lines[0])

    def test_future_started(self):
        rel = self.task({"status": "in_progress", "owner": "anna", "started": TOMORROW})
        self.assertOneOn(rel, TOMORROW)

    def test_unknown_type(self):
        rel = self.story({"type": "feature"})
        self.assertOneOn(rel, "feature")

    def test_epic_workspace_task(self):
        rel = self.task({"type": "epic"}, slug="big-move")
        self.assertOneOn(rel, "epic")

    def test_two_work_records_in_task_folder(self):
        rel = self.task({"status": "done"})
        self.write("tasks/e2e-checkout/work.md", WORK_RECORD)
        self.write("tasks/e2e-checkout/archive/work.md", WORK_RECORD)
        # Records of a done task are judged by the work-record rule; this rule only counts them.
        lines = self.on_task_file(rel)
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("work.md", lines[0])


if __name__ == "__main__":
    unittest.main()
