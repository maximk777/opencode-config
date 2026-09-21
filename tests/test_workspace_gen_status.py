import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import datetime
import tempfile
import unittest

from workspace_helpers import create_workspace, run_generate
from wslib import gen_status

STATUS_MD = """# Status

Queue of the workspace; hand text stays.

<!-- status:in-progress:begin -->
stale
<!-- status:in-progress:end -->

## Waiting

<!-- status:waiting:begin -->
stale
<!-- status:waiting:end -->

## Done recently

<!-- status:done-recently:begin -->
stale
<!-- status:done-recently:end -->

<!-- status:drift:begin -->
stale
<!-- status:drift:end -->

Tail text.
"""

STORY_REL = "projects/abs/domains/operations/streams/main/stories/%s/story.md"


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def story(slug: str, status: str = "waiting", owner: str = "", started: str = "") -> str:
    fields = ["key: story:abs/operations/%s" % slug, "type: story", "status: %s" % status]
    if owner:
        fields.append("owner: %s" % owner)
    if started:
        fields.append("started: %s" % started)
    return "---\n%s\n---\n# %s\n\n## Goal\n\nx\n" % ("\n".join(fields), slug)


def task(slug: str, status: str = "waiting", owner: str = "", started: str = "") -> str:
    fields = ["key: task:%s" % slug, "type: e2e", "status: %s" % status]
    if owner:
        fields.append("owner: %s" % owner)
    if started:
        fields.append("started: %s" % started)
    return "---\n%s\n---\n# %s\n\n## Goal\n\nx\n" % ("\n".join(fields), slug)


def work(recorded: str) -> str:
    return (
        "---\nrepos: []\nmerge_requests: [MR-1]\ncommits: []\nrecorded: %s\n---\n"
        "## Changed\n\nx\n\n## Decisions\n\nx\n\n## Open questions\n\nNone.\n\n## Verification\n\nx\n" % recorded
    )


def section(text: str, name: str) -> str:
    begin, end = gen_status.marker(name)
    lines = text.split("\n")
    return "\n".join(lines[lines.index(begin) + 1 : lines.index(end)])


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def render(self) -> str:
        return gen_status.render(self.root)["STATUS.md"].decode("utf-8")


class MarkersTest(Base):
    def test_outside_text_stays_and_sections_are_replaced(self):
        write(self.root, STORY_REL % "card", story("card", "in_progress", "anna", "2026-09-01"))
        write(self.root, "STATUS.md", STATUS_MD)
        text = self.render()
        self.assertTrue(text.startswith("# Status\n\nQueue of the workspace; hand text stays.\n"), text)
        self.assertIn("Tail text.", text)
        self.assertIn("## Waiting", text)
        self.assertNotIn("stale", text)
        self.assertEqual(section(text, "in-progress"), "\n".join([
            "### anna",
            "",
            "| Task | Started |",
            "|---|---|",
            "| [story:abs/operations/card](%s) | 2026-09-01 |" % (STORY_REL % "card"),
        ]))
        self.assertEqual(section(text, "drift"), "")

    def test_missing_status_file_is_skipped(self):
        self.assertEqual(gen_status.render(self.root), {})

    def test_status_without_markers_is_skipped(self):
        write(self.root, "STATUS.md", "# Status\n\nNo markers.\n")
        self.assertEqual(gen_status.render(self.root), {})
        self.assertFalse(gen_status.has_markers("# Status\n"))
        self.assertTrue(gen_status.has_all_markers(STATUS_MD))
        self.assertFalse(gen_status.has_all_markers(STATUS_MD.replace("<!-- status:drift:begin -->\n", "")))
        self.assertFalse(gen_status.has_all_markers(STATUS_MD.replace("<!-- status:drift:end -->\n", "")))

    def test_hand_text_between_unpaired_markers_is_kept(self):
        text = STATUS_MD.replace("<!-- status:drift:end -->\n", "")
        write(self.root, "STATUS.md", text)
        rendered = gen_status.render(self.root)["STATUS.md"].decode("utf-8")
        # Only the unpaired drift section keeps its hand text; every paired section was regenerated.
        self.assertEqual(rendered.count("stale"), 1)
        self.assertGreater(rendered.index("stale"), rendered.index("<!-- status:drift:begin -->"))


class InProgressTest(Base):
    def test_grouped_by_owner_then_started_ascending(self):
        write(self.root, STORY_REL % "late", story("late", "in_progress", "anna", "2026-09-10"))
        write(self.root, STORY_REL % "early", story("early", "in_progress", "anna", "2026-09-01"))
        write(self.root, "tasks/e2e-checkout/task.md", task("e2e-checkout", "in_progress", "bob", "2026-08-31"))
        write(self.root, "STATUS.md", STATUS_MD)
        text = self.render()
        anna = text.index("### anna")
        early = text.index("[story:abs/operations/early]")
        late = text.index("[story:abs/operations/late]")
        bob = text.index("### bob")
        checkout = text.index("[task:e2e-checkout]")
        self.assertTrue(anna < early < late < bob < checkout, text)

    def test_waiting_and_done_tasks_are_not_in_progress(self):
        write(self.root, STORY_REL % "card", story("card", "waiting"))
        write(self.root, "tasks/done-1/task.md", task("done-1", "done"))
        write(self.root, "STATUS.md", STATUS_MD)
        self.assertEqual(section(self.render(), "in-progress"), "")


class WaitingTest(Base):
    def test_grouped_by_project_and_stream_then_workspace(self):
        write(self.root, STORY_REL % "reports", story("reports"))
        write(self.root, "projects/abs/domains/operations/streams/arm/stories/card/story.md", story("card"))
        write(self.root, "tasks/e2e-checkout/task.md", task("e2e-checkout"))
        write(self.root, "STATUS.md", STATUS_MD)
        text = self.render()
        arm = text.index("### abs/operations/arm")
        card = text.index("[story:abs/operations/card]")
        main = text.index("### abs/operations/main")
        reports = text.index("[story:abs/operations/reports]")
        workspace = text.index("### workspace")
        checkout = text.index("[task:e2e-checkout]")
        self.assertTrue(arm < card < main < reports < workspace < checkout, text)

    def test_other_statuses_are_not_waiting(self):
        write(self.root, STORY_REL % "card", story("card", "in_progress", "anna", "2026-09-01"))
        write(self.root, "STATUS.md", STATUS_MD)
        self.assertEqual(section(self.render(), "waiting"), "")


class DoneRecentlyTest(Base):
    def test_thirty_day_window_in_descending_order(self):
        # Dates are fixed relative to today so the window test does not depend on the calendar.
        today = datetime.date.today()
        write(self.root, "tasks/fresh/task.md", task("fresh", "done"))
        write(self.root, "tasks/fresh/work.md", work(today.isoformat()))
        write(self.root, "tasks/edge/task.md", task("edge", "done"))
        write(self.root, "tasks/edge/work.md", work((today - datetime.timedelta(days=30)).isoformat()))
        write(self.root, "tasks/old/task.md", task("old", "done"))
        write(self.root, "tasks/old/work.md", work((today - datetime.timedelta(days=31)).isoformat()))
        write(self.root, "STATUS.md", STATUS_MD)
        text = self.render()
        fresh = text.index("[task:fresh]")
        edge = text.index("[task:edge]")
        self.assertIn("| [task:fresh](tasks/fresh/task.md) | %s |" % today.isoformat(), text)
        self.assertTrue(fresh < edge, text)
        self.assertNotIn("task:old", text)

    def test_undated_record_is_not_listed(self):
        write(self.root, "tasks/broken/task.md", task("broken", "done"))
        write(self.root, "tasks/broken/work.md", work("not-a-date"))
        write(self.root, "STATUS.md", STATUS_MD)
        self.assertEqual(section(self.render(), "done-recently"), "")

    def test_task_without_record_is_not_listed(self):
        write(self.root, "tasks/ghost/task.md", task("ghost", "done"))
        write(self.root, "STATUS.md", STATUS_MD)
        self.assertEqual(section(self.render(), "done-recently"), "")


class IdempotencyTest(Base):
    def test_second_render_is_byte_identical(self):
        write(self.root, STORY_REL % "card", story("card", "in_progress", "anna", "2026-09-01"))
        write(self.root, STORY_REL % "reports", story("reports"))
        write(self.root, "tasks/fresh/task.md", task("fresh", "done"))
        write(self.root, "tasks/fresh/work.md", work(datetime.date.today().isoformat()))
        write(self.root, "STATUS.md", STATUS_MD)
        first = gen_status.render(self.root)
        write(self.root, "STATUS.md", first["STATUS.md"].decode("utf-8"))
        self.assertEqual(gen_status.render(self.root), first)


class GenerateStatusTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.ws = create_workspace(self.tmp)
        write(self.ws, STORY_REL % "card", story("card", "in_progress", "anna", "2026-09-01"))
        write(self.ws, STORY_REL % "reports", story("reports"))
        write(self.ws, "tasks/fresh/task.md", task("fresh", "done"))
        write(self.ws, "tasks/fresh/work.md", work(datetime.date.today().isoformat()))
        write(self.ws, "STATUS.md", STATUS_MD)

    def tearDown(self):
        self._tmp.cleanup()

    def test_generate_writes_sections_and_second_run_changes_no_file(self):
        first = run_generate(self.ws)
        self.assertEqual(first.returncode, 0, first.stderr)
        text = (self.ws / "STATUS.md").read_text(encoding="utf-8")
        self.assertIn("### anna", section(text, "in-progress"))
        self.assertIn("[task:fresh]", section(text, "done-recently"))
        self.assertEqual(section(text, "drift"), "")
        before = (self.ws / "STATUS.md").read_bytes()

        second = run_generate(self.ws)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("generated: 0 files changed", second.stdout)
        self.assertEqual((self.ws / "STATUS.md").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
