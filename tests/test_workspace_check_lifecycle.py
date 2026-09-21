import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
import shutil
import tempfile
import unittest

from workspace_helpers import create_workspace, run_check
from wslib import common, rules_lifecycle

UI_PROFILE = REPO / "kits/workspace/.agents/profiles/ui-migration"
CHECKLIST_PROFILE = REPO / "tests/fixtures/profiles/checklist"
RULES = ("lifecycle", "profile", "stage-gate")
STREAM_JSON = "projects/abs/domains/operations/streams/s/stream.json"

EPIC = "".join(
    "## %s\n\nx\n\n" % s
    for s in ("Goal", "Scope", "Success criteria", "Out of scope", "Open questions", "Target users", "Product")
)
STORY_BODY = (
    "\n## Goal\n\nx\n\n## Scope\n\nx\n\n## Acceptance criteria\n\nx\n\n## Verification\n\nx\n"
    "\n## Out of scope\n\nx\n\n## Open questions\n\n%s\n"
)
MAP_DOC = (
    "# Map of operations\n\n<!-- map:screens:begin -->\n<!-- map:screens:end -->\n\n"
    "## Legacy trace\n\n| Legacy group | Legacy item | Legacy route | Target |\n|---|---|---|---|\n"
    "| g | documents | /docs | screen:abs/operations/documents |\n"
    "| g | report | /report | screen:abs/operations/report |\n"
)


def screen(slug, story=""):
    return (
        "---\nkey: screen:abs/operations/%s\nroute: /%s\nkind: place\nsection: s\nparent:\naccess: a\n"
        "label: L\nwave: 1\nstory:%s\n---\n\n## Transitions\n\n| Action | Target |\n|---|---|\n"
        % (slug, slug, " " + story if story else "")
    )


def ui_story(slug, scope, tracker="", questions="None.", status="waiting"):
    return (
        "---\nkey: story:abs/operations/%s\ntype: story\nstatus: %s\nwave: 1\ntracker:%s\nscope: [%s]\ndepends: []\n"
        "repos: []\ndecisions: []\nmockups: []\n---\n%s"
        % (slug, status, " " + tracker if tracker else "", ", ".join(scope), STORY_BODY % questions)
    )


def approvals(*stages):
    return [{"stage": stage, "by": "owner", "date": "2026-09-01"} for stage in stages]


class LifecycleBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.ws = create_workspace(self.tmp)
        target = self.ws / ".agents/profiles/ui-migration"
        if not (target / "profile.json").is_file():
            shutil.copytree(str(UI_PROFILE), str(target), dirs_exist_ok=True)
        shutil.copytree(str(CHECKLIST_PROFILE), str(self.ws / ".agents/profiles/checklist"))

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text):
        path = self.ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return rel

    def write_stream(self, stage, scope=(), approved=(), profile="ui-migration", domain="operations", name="s",
                     key=None, data=None):
        if data is None:
            data = {
                "key": key or "stream:abs/%s/%s" % (domain, name),
                "profile": profile,
                "stage": stage,
                "scope": list(scope),
                "approvals": approvals(*approved),
            }
        return self.write(
            "projects/abs/domains/%s/streams/%s/stream.json" % (domain, name), json.dumps(data, indent=2) + "\n"
        )

    def ui_map(self):
        self.write("projects/abs/domains/operations/map/documents.md", screen("documents", "story:abs/operations/documents"))
        self.write("projects/abs/domains/operations/map/report.md", screen("report"))
        self.write("projects/abs/domains/operations/MAP.md", MAP_DOC)
        self.write("projects/abs/domains/operations/streams/s/epic.md", EPIC)

    def findings(self):
        code, lines, stderr = run_check(self.ws)
        self.assertNotIn("Traceback", stderr)
        self.assertNotEqual(code, 2, stderr)
        return [line for line in lines if len(line.split(" ")) > 1 and line.split(" ")[1] in RULES]

    def remaining(self):
        return rules_lifecycle.remaining(common.Context(self.ws))

    def assertOnly(self, rel, rule, *fragments):
        lines = self.findings()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(rel + ":"), lines)
        self.assertEqual(lines[0].split(" ")[1], rule, lines)
        for fragment in fragments:
            self.assertIn(fragment, lines[0])


class StreamShapeTest(LifecycleBase):
    def test_valid_stream_at_goal(self):
        self.write("projects/abs/domains/operations/map/documents.md", screen("documents"))
        self.write("projects/abs/domains/operations/streams/migration/epic.md", EPIC)
        self.write_stream("goal", ["screen:abs/operations/documents"], name="migration")
        self.assertEqual(self.findings(), [])

    def test_key_does_not_match_path(self):
        rel = self.write_stream("goal", domain="risks", name="risks-2026", key="stream:abs/risks/other")
        self.write("projects/abs/domains/risks/streams/risks-2026/epic.md", EPIC)
        self.assertOnly(rel, "lifecycle", "stream:abs/risks/other")

    def test_unknown_profile_gives_no_other_checks(self):
        rel = self.write_stream("done", ["screen:abs/operations/ghost"], profile="nonexistent")
        self.assertOnly(rel, "lifecycle", "nonexistent")
        self.assertEqual(self.remaining(), [])

    def test_broken_json(self):
        rel = self.write(STREAM_JSON, "{not json\n")
        self.assertOnly(rel, "lifecycle")

    def test_not_an_object(self):
        rel = self.write(STREAM_JSON, "[]\n")
        self.assertOnly(rel, "lifecycle")

    def test_missing_approvals_and_bad_scope(self):
        self.write("projects/abs/domains/operations/streams/s/epic.md", EPIC)
        rel = self.write_stream("goal", data={
            "key": "stream:abs/operations/s", "profile": "ui-migration", "stage": "goal", "scope": "screen:x"})
        lines = self.findings()
        self.assertEqual(len(lines), 2, lines)
        self.assertTrue(all(line.startswith(rel + ":") and " lifecycle " in line for line in lines), lines)
        self.assertTrue(any("scope" in line for line in lines), lines)
        self.assertTrue(any("approvals" in line for line in lines), lines)

    def test_non_list_scope_reported_once(self):
        self.ui_map()
        rel = self.write_stream("ready", approved=("goal", "map", "decomposition"), data={
            "key": "stream:abs/operations/s", "profile": "ui-migration", "stage": "ready", "scope": "screen:x",
            "approvals": approvals("goal", "map", "decomposition")})
        self.assertOnly(rel, "lifecycle", "scope must be a list of strings")

    def test_stage_outside_list(self):
        rel = self.write_stream("review")
        self.assertOnly(rel, "lifecycle", "review")
        self.assertEqual(self.remaining(), [])

    def test_approval_from_the_future(self):
        self.write("projects/abs/domains/operations/streams/s/epic.md", EPIC)
        rel = self.write_stream("map", approved=("goal", "decomposition"))
        self.assertOnly(rel, "lifecycle", "decomposition")

    def test_scope_key_without_map_element_at_goal(self):
        self.write("projects/abs/domains/operations/map/documents.md", screen("documents"))
        self.write("projects/abs/domains/operations/streams/s/epic.md", EPIC)
        self.write_stream("goal", ["screen:abs/operations/documents", "screen:abs/operations/ghost"])
        self.assertOnly(STREAM_JSON, "lifecycle", STREAM_JSON + ":1 ",
                        "scope key screen:abs/operations/ghost names no map element")

    def test_approval_for_unknown_stage(self):
        self.write("projects/abs/domains/operations/streams/s/epic.md", EPIC)
        rel = self.write_stream("map", approved=("goal", "review"))
        self.assertOnly(rel, "lifecycle", "review")


class ProfileTest(LifecycleBase):
    def test_invalid_profile_reported_and_its_streams_not_checked(self):
        data = json.loads((CHECKLIST_PROFILE / "profile.json").read_text(encoding="utf-8"))
        data["name"] = "broken"
        data["stages"]["map"].append({"gate": "magic_gate"})
        rel = self.write(".agents/profiles/broken/profile.json", json.dumps(data, indent=2) + "\n")
        self.write_stream("done", profile="broken")
        self.assertOnly(rel, "profile", "magic_gate")
        self.assertEqual(self.remaining(), [])

    def test_shared_element_dir_reported_from_model(self):
        data = json.loads((CHECKLIST_PROFILE / "profile.json").read_text(encoding="utf-8"))
        data["name"] = "zz-shared"
        data["elements"][0]["dir"] = "map"
        self.write(".agents/profiles/zz-shared/profile.json", json.dumps(data, indent=2) + "\n")
        lines = self.findings()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(" profile " in lines[0] and "map" in lines[0], lines)


class MissingStreamJsonTest(LifecycleBase):
    def test_stories_without_stream_json(self):
        self.write("projects/abs/domains/operations/streams/bare/stories/documents/story.md",
                   ui_story("documents", ["screen:abs/operations/documents"]))
        self.assertOnly("projects/abs/domains/operations/streams/bare/stream.json", "lifecycle", "missing stream.json")


class StageGateTest(LifecycleBase):
    def test_goal_gates_checked_at_map_and_map_gates_not(self):
        self.write("projects/abs/domains/operations/map/documents.md", screen("documents"))
        self.write_stream("map", ["screen:abs/operations/documents"])
        lines = self.findings()
        self.assertEqual(len(lines), 2, lines)
        self.assertTrue(
            any(l.startswith("projects/abs/domains/operations/streams/s/epic.md:1 stage-gate goal epic_sections:")
                for l in lines),
            lines,
        )
        self.assertTrue(any(l.startswith(STREAM_JSON + ":1 stage-gate goal approval:") for l in lines), lines)

    def test_map_closed_without_approval(self):
        self.ui_map()
        self.write_stream("decomposition", ["screen:abs/operations/documents"], approved=("goal",))
        self.write("projects/abs/domains/operations/streams/s/stories/documents/story.md",
                   ui_story("documents", ["screen:abs/operations/documents"]))
        self.assertOnly(STREAM_JSON, "stage-gate", "map approval:")

    def test_uncovered_screen_at_decomposition_is_not_a_finding(self):
        self.ui_map()
        self.write_stream(
            "decomposition", ["screen:abs/operations/documents", "screen:abs/operations/report"],
            approved=("goal", "map"))
        self.write("projects/abs/domains/operations/streams/s/stories/documents/story.md",
                   ui_story("documents", ["screen:abs/operations/documents"]))
        self.assertEqual(self.findings(), [])

    def test_uncovered_screen_at_ready(self):
        self.ui_map()
        self.write_stream(
            "ready", ["screen:abs/operations/documents", "screen:abs/operations/report"],
            approved=("goal", "map", "decomposition"))
        self.write("projects/abs/domains/operations/streams/s/stories/documents/story.md",
                   ui_story("documents", ["screen:abs/operations/documents"]))
        # The story has no tracker id: that is a ready gate and stays out of the findings.
        self.assertOnly(STREAM_JSON, "stage-gate", "decomposition two_way_coverage:", "screen:abs/operations/report")

    def test_open_question_blocks_ready_at_delivery(self):
        self.ui_map()
        self.write_stream("delivery", ["screen:abs/operations/documents"],
                          approved=("goal", "map", "decomposition"))
        rel = self.write("projects/abs/domains/operations/streams/s/stories/documents/story.md",
                         ui_story("documents", ["screen:abs/operations/documents"], "TASK-1", "- Who signs?"))
        self.assertOnly(rel, "stage-gate", "ready no_open_questions:")

    def test_done_stream_with_closed_stages_passes(self):
        self.ui_map()
        self.write_stream("done", ["screen:abs/operations/documents"], approved=("goal", "map", "decomposition"))
        self.write("projects/abs/domains/operations/streams/s/stories/documents/story.md",
                   ui_story("documents", ["screen:abs/operations/documents"], "TASK-1", status="done"))
        # The story folder has no work.md, but work_records is a gate of done itself.
        self.assertEqual(self.findings(), [])
        lines = self.remaining()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("stream:abs/operations/s done work_records: "), lines)
        self.assertIn("work.md", lines[0])


class ChecklistProfileTest(LifecycleBase):
    def setUp(self):
        super().setUp()
        self.write("projects/abs/domains/ops/rules/a.md", self.rule("a", "rule:abs/ops/b"))
        self.write("projects/abs/domains/ops/rules/b.md", self.rule("b", "rule:abs/ops/a"))
        self.write("projects/abs/domains/ops/streams/c/epic.md", "## Goal\n\nx\n")
        self.write("projects/abs/domains/ops/streams/c/stories/a/story.md",
                   "---\nkey: story:abs/ops/a\ntype: story\nscope: [rule:abs/ops/a, rule:abs/ops/b]\ntracker: TASK-3\n---\n"
                   "\n## Goal\n\nx\n\n## Open questions\n\nNone.\n")
        self.write_stream("ready", ["rule:abs/ops/a", "rule:abs/ops/b"], ("goal", "map", "decomposition"),
                          profile="checklist", domain="ops", name="c")

    @staticmethod
    def rule(slug, target):
        return (
            "---\nkey: rule:abs/ops/%s\nowner: me\nstory: story:abs/ops/a\n---\n\n## Checks\n\n"
            "| Check | Target |\n|---|---|\n| next | %s |\n" % (slug, target)
        )

    def test_passes(self):
        self.assertEqual(self.findings(), [])

    def test_dangling_target_fails_closed_map_stage(self):
        rel = self.write("projects/abs/domains/ops/rules/a.md", self.rule("a", "rule:abs/ops/ghost"))
        lines = self.findings()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(rel + ":11 stage-gate map no_dangling_targets:"), lines)
        self.assertIn("rule:abs/ops/ghost", lines[0])


class RemainingTest(LifecycleBase):
    def test_uncovered_screen_listed(self):
        self.ui_map()
        self.write_stream(
            "decomposition", ["screen:abs/operations/documents", "screen:abs/operations/report"],
            approved=("goal", "map"))
        self.write("projects/abs/domains/operations/streams/s/stories/documents/story.md",
                   ui_story("documents", ["screen:abs/operations/documents"]))
        lines = self.remaining()
        self.assertEqual(len(lines), 2, lines)
        coverage = [l for l in lines if l.startswith("stream:abs/operations/s decomposition two_way_coverage: ")]
        self.assertEqual(len(coverage), 1, lines)
        self.assertIn(STREAM_JSON + ":1 ", coverage[0])
        self.assertIn("screen:abs/operations/report", coverage[0])
        self.assertTrue(any(l.startswith("stream:abs/operations/s decomposition approval: " + STREAM_JSON + ":1 ")
                            for l in lines), lines)

    def test_fresh_workspace_has_nothing_remaining(self):
        self.assertEqual(self.remaining(), [])


if __name__ == "__main__":
    unittest.main()
