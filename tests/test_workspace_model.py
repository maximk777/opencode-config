import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
import re
import subprocess
import tempfile
import unittest

from wslib.common import Context
from wslib.model import Element, Story, Stream, Task, Workspace

FIXTURE = Path(__file__).resolve().parent / "fixtures/profiles/checklist/profile.json"

UI_MIGRATION = {
    "name": "ui-migration",
    "elements": [
        {
            "kind": "screen",
            "prefix": "screen",
            "dir": "map",
            "fields": ["key", "route", "kind", "section", "parent", "access", "label", "wave", "story"],
            "may_be_empty": ["parent", "story"],
            "values": {"kind": ["place"]},
            "tables": [{"heading": "Transitions", "columns": ["Action", "Target"], "keys": ["Target"]}],
        }
    ],
    "story": {
        "fields": ["key", "type", "status", "owner", "started", "wave", "tracker", "scope", "depends", "repos", "decisions", "mockups"],
        "may_be_empty": ["status", "owner", "started", "tracker", "scope", "depends", "repos", "decisions", "mockups"],
        "values": {"type": ["story"]},
        "sections": ["Goal", "Scope", "Acceptance criteria", "Verification", "Out of scope", "Open questions"],
    },
    "epic": {
        "sections": ["Goal", "Scope", "Success criteria", "Out of scope", "Open questions", "Target users", "Product"]
    },
    "map_doc": {
        "tables": [
            {
                "heading": "Legacy trace",
                "columns": ["Legacy group", "Legacy item", "Legacy route", "Target"],
                "target": "Target",
            }
        ]
    },
    "stages": {
        "goal": [{"gate": "epic_sections"}, {"gate": "approval"}],
        "map": [
            {"gate": "unique_keys"},
            {"gate": "no_dangling_targets"},
            {"gate": "legacy_traced", "table": "Legacy trace"},
            {"gate": "approval"},
        ],
        "decomposition": [{"gate": "two_way_coverage"}, {"gate": "approval"}],
        "ready": [{"gate": "tracker_ids"}, {"gate": "no_open_questions", "section": "Open questions"}],
        "delivery": [],
        "done": [{"gate": "work_records"}],
    },
}

SCREEN_LIST = """---
key: screen:abs/operations/list
route: /operations
kind: place
section: Operations
parent:
access: listOperations
label: Operations
wave: 1
story:
---
# Operations list

## Transitions

| Action | Target |
|---|---|
| Open | screen:abs/operations/card |
| Back | screen:abs/clients/home |
"""

SCREEN_CARD = """---
key: screen:abs/operations/card
route: /operations/:id
kind: place
section: Operations
parent: screen:abs/operations/list
access: getOperation
label: Operation
wave: 1
story: story:abs/operations/card
---
# Operation card

## Notes

No table here.
"""

STORY = """---
key: story:abs/operations/card
type: story
status: waiting
owner:
started:
wave: 1
tracker: TASK-1
scope: [screen:abs/operations/card]
depends: []
repos: []
decisions: []
mockups: []
---
# Card

## Goal

Show a card.

## Open questions

None.
"""

TASK = """---
key: task:e2e-checkout
type: e2e
status: waiting
owner:
started:
tracker:
---
# E2E checkout

## Goal

Check the checkout flow.
"""

TRACKERS = {
    "trackers": [
        {"key": "jira", "id_pattern": r"TASK-\d+", "url": "https://jira/{id}"},
        {"key": "youtrack", "id_pattern": r"YT-\d+", "url": "https://yt/{id}"},
    ]
}


def stream_json(project, domain, stream, profile="ui-migration", **extra):
    data = {
        "key": "stream:%s/%s/%s" % (project, domain, stream),
        "profile": profile,
        "stage": "goal",
        "scope": [],
        "approvals": [],
    }
    data.update(extra)
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


class ModelTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self.write(".agents/kit.json", json.dumps({"name": "workspace", "version": "0.1.0", "params": {}}) + "\n")
        self.write(".agents/profiles/checklist/profile.json", FIXTURE.read_text(encoding="utf-8"))
        self.write(
            ".agents/profiles/ui-migration/profile.json",
            json.dumps(UI_MIGRATION, indent=2, ensure_ascii=False) + "\n",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def workspace(self):
        return Workspace(Context(self.root))


class ProfilesTest(ModelTestCase):
    def test_valid_profiles_loaded(self):
        ws = self.workspace()
        self.assertEqual(sorted(ws.profiles), ["checklist", "ui-migration"])
        self.assertEqual(ws.profile_findings, [])

    def test_invalid_profile_is_reported_and_its_elements_not_discovered(self):
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        data["stages"]["map"].append({"gate": "magic_gate"})
        self.write(".agents/profiles/checklist/profile.json", json.dumps(data) + "\n")
        self.write("projects/abs/domains/ops/rules/r1.md", "---\nkey: rule:abs/ops/r1\nowner: me\nstory:\n---\n")
        ws = self.workspace()
        self.assertEqual(sorted(ws.profiles), ["ui-migration"])
        self.assertTrue(ws.profile_findings)
        self.assertEqual({f.rule for f in ws.profile_findings}, {"profile"})
        self.assertEqual(ws.elements, {})
        self.assertEqual(ws.element_list, [])


class ElementsTest(ModelTestCase):
    def test_elements_per_project_kind_and_domain(self):
        self.write("projects/abs/domains/operations/map/list.md", SCREEN_LIST)
        self.write("projects/abs/domains/operations/map/card.md", SCREEN_CARD)
        self.write("projects/abs/domains/clients/map/home.md", "---\nkey: screen:abs/clients/home\n---\n# Home\n")
        self.write("projects/abs/domains/ops/rules/r1.md", "---\nkey: rule:abs/ops/r1\nowner: me\nstory:\n---\n# R1\n")
        ws = self.workspace()
        self.assertEqual(
            sorted(ws.elements),
            [
                "rule:abs/ops/r1",
                "screen:abs/clients/home",
                "screen:abs/operations/card",
                "screen:abs/operations/list",
            ],
        )
        self.assertEqual(len(ws.element_list), 4)

        card = ws.elements["screen:abs/operations/card"]
        self.assertIsInstance(card, Element)
        self.assertEqual(
            (card.key, card.kind, card.project, card.domain, card.slug, card.path, card.error),
            (
                "screen:abs/operations/card",
                "screen",
                "abs",
                "operations",
                "card",
                "projects/abs/domains/operations/map/card.md",
                None,
            ),
        )
        self.assertEqual(card.fields["parent"], "screen:abs/operations/list")
        self.assertEqual(card.fields["story"], "story:abs/operations/card")
        self.assertEqual(card.tables["Transitions"], (None, [], None))

        rule = ws.elements["rule:abs/ops/r1"]
        self.assertEqual((rule.kind, rule.project, rule.domain, rule.slug), ("rule", "abs", "ops", "r1"))
        self.assertEqual(rule.fields, {"key": "rule:abs/ops/r1", "owner": "me", "story": ""})
        self.assertEqual(rule.tables, {"Checks": (None, [], None)})

    def test_tables_parsed_with_file_lines(self):
        self.write("projects/abs/domains/operations/map/list.md", SCREEN_LIST)
        ws = self.workspace()
        columns, rows, error = ws.elements["screen:abs/operations/list"].tables["Transitions"]
        self.assertEqual(columns, ["Action", "Target"])
        self.assertIsNone(error)
        lines = SCREEN_LIST.split("\n")
        self.assertEqual(lines[rows[0][0] - 1], "| Open | screen:abs/operations/card |")
        self.assertEqual(
            rows,
            [
                (rows[0][0], ["Open", "screen:abs/operations/card"]),
                (rows[0][0] + 1, ["Back", "screen:abs/clients/home"]),
            ],
        )

    def test_key_from_path_not_frontmatter(self):
        self.write(
            "projects/abs/domains/operations/map/list.md",
            SCREEN_LIST.replace("screen:abs/operations/list", "screen:x/y", 1),
        )
        ws = self.workspace()
        element = ws.elements["screen:abs/operations/list"]
        self.assertEqual(element.fields["key"], "screen:x/y")
        self.assertNotIn("screen:x/y", ws.elements)

    def test_frontmatter_error_kept(self):
        self.write(
            "projects/abs/domains/operations/map/bad.md",
            "---\nkey: screen:abs/operations/bad\n\nroute: /bad\n---\n",
        )
        ws = self.workspace()
        bad = ws.elements["screen:abs/operations/bad"]
        self.assertIsNone(bad.fields)
        self.assertIn("blank line", bad.error)

    def test_missing_frontmatter_is_error(self):
        self.write("projects/abs/domains/operations/map/plain.md", "# Plain\n")
        self.write("projects/abs/domains/operations/map/empty.md", "")
        ws = self.workspace()
        for key in ("screen:abs/operations/plain", "screen:abs/operations/empty"):
            element = ws.elements[key]
            self.assertIsNone(element.fields, key)
            self.assertEqual(element.error, "missing frontmatter", key)

    def test_shared_dir_first_kind_wins_and_is_reported(self):
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        data["elements"][0]["dir"] = "map"
        self.write(".agents/profiles/checklist/profile.json", json.dumps(data) + "\n")
        self.write("projects/abs/domains/operations/map/list.md", SCREEN_LIST)
        ws = self.workspace()
        self.assertEqual(sorted(ws.profiles), ["checklist", "ui-migration"])
        self.assertEqual(list(ws.elements), ["rule:abs/operations/list"])
        self.assertEqual([e.kind for e in ws.element_list], ["rule"])
        self.assertEqual(len(ws.profile_findings), 1)
        finding = ws.profile_findings[0]
        self.assertEqual(
            (finding.path, finding.line, finding.rule),
            (".agents/profiles/ui-migration/profile.json", 1, "profile"),
        )
        for word in ("map", "rule", "screen"):
            self.assertIn(word, finding.message)

    def test_shared_dir_in_one_profile_is_reported(self):
        dup = dict(UI_MIGRATION["elements"][0], kind="view", prefix="view")
        profile = dict(UI_MIGRATION, elements=UI_MIGRATION["elements"] + [dup])
        self.write(".agents/profiles/ui-migration/profile.json", json.dumps(profile) + "\n")
        self.write("projects/abs/domains/operations/map/list.md", SCREEN_LIST)
        ws = self.workspace()
        self.assertEqual(list(ws.elements), ["screen:abs/operations/list"])
        self.assertEqual(len(ws.element_list), 1)
        self.assertEqual(len(ws.profile_findings), 1)
        finding = ws.profile_findings[0]
        self.assertEqual(
            (finding.path, finding.line, finding.rule),
            (".agents/profiles/ui-migration/profile.json", 1, "profile"),
        )
        for word in ("map", "screen", "view"):
            self.assertIn(word, finding.message)

    def test_shared_dir_with_same_kind_names_both_profiles(self):
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        data["elements"][0].update(kind="screen", dir="map")
        self.write(".agents/profiles/checklist/profile.json", json.dumps(data) + "\n")
        ws = self.workspace()
        self.assertEqual(
            [f.message for f in ws.profile_findings],
            ["kind screen of profile ui-migration uses dir map already used by kind screen of profile checklist"],
        )

    def test_duplicate_key_first_file_wins(self):
        dup = dict(UI_MIGRATION["elements"][0], kind="view", dir="views")
        profile = dict(UI_MIGRATION, elements=UI_MIGRATION["elements"] + [dup])
        self.write(".agents/profiles/ui-migration/profile.json", json.dumps(profile) + "\n")
        self.write("projects/abs/domains/operations/map/list.md", SCREEN_LIST)
        self.write("projects/abs/domains/operations/views/list.md", "---\nkey: screen:abs/operations/list\n---\n")
        ws = self.workspace()
        self.assertEqual(ws.elements["screen:abs/operations/list"].path, "projects/abs/domains/operations/map/list.md")
        self.assertEqual(
            [e.path for e in ws.element_list],
            [
                "projects/abs/domains/operations/map/list.md",
                "projects/abs/domains/operations/views/list.md",
            ],
        )

    def test_only_direct_md_files_of_element_dir(self):
        self.write("projects/abs/domains/operations/map/list.md", SCREEN_LIST)
        self.write("projects/abs/domains/operations/map/notes.txt", "x\n")
        self.write(
            "projects/abs/domains/operations/map/deep/inner.md",
            "---\nkey: screen:abs/operations/inner\n---\n",
        )
        self.write("projects/abs/domains/operations/MAP.md", "# Map\n")
        self.write("map/top.md", "---\nkey: screen:top\n---\n")
        ws = self.workspace()
        self.assertEqual(list(ws.elements), ["screen:abs/operations/list"])


class StreamsTest(ModelTestCase):
    def test_stream_with_stories(self):
        base = "projects/abs/domains/operations/streams/arm"
        self.write(base + "/stream.json", stream_json("abs", "operations", "arm", scope=["screen:abs/operations/card"]))
        self.write(base + "/epic.md", "# Epic\n")
        self.write(base + "/stories/card/story.md", STORY)
        self.write(
            base + "/stories/list/story.md",
            "---\nkey: story:abs/operations/list\nscope: [\n---\n",
        )
        self.write(base + "/stories/card/notes.md", "# Notes\n")
        self.write(base + "/stories/stray.md", "# Stray\n")
        ws = self.workspace()
        self.assertEqual(len(ws.streams), 1)
        stream = ws.streams[0]
        self.assertIsInstance(stream, Stream)
        self.assertEqual(
            (
                stream.key,
                stream.project,
                stream.domain,
                stream.name,
                stream.path,
                stream.error,
                stream.profile_name,
                stream.epic_path,
            ),
            (
                "stream:abs/operations/arm",
                "abs",
                "operations",
                "arm",
                base + "/stream.json",
                None,
                "ui-migration",
                base + "/epic.md",
            ),
        )
        self.assertEqual(stream.data["scope"], ["screen:abs/operations/card"])
        self.assertEqual(
            sorted(stream.stories),
            ["story:abs/operations/card", "story:abs/operations/list"],
        )

        card = stream.stories["story:abs/operations/card"]
        self.assertIsInstance(card, Story)
        self.assertEqual(
            (card.key, card.project, card.domain, card.stream, card.slug, card.path, card.error),
            (
                "story:abs/operations/card",
                "abs",
                "operations",
                "arm",
                "card",
                base + "/stories/card/story.md",
                None,
            ),
        )
        self.assertEqual(card.fields["tracker"], "TASK-1")
        self.assertEqual([heading for _, heading, _ in card.sections], ["Goal", "Open questions"])
        line, _, text = card.sections[1]
        self.assertEqual(STORY.split("\n")[line - 1], "## Open questions")
        self.assertEqual(text.strip(), "None.")

        broken = stream.stories["story:abs/operations/list"]
        self.assertIsNone(broken.fields)
        self.assertIn("unclosed [", broken.error)

    def test_epic_path_given_when_absent(self):
        self.write("projects/abs/domains/ops/streams/s1/stream.json", stream_json("abs", "ops", "s1", profile="checklist"))
        ws = self.workspace()
        self.assertEqual(ws.streams[0].epic_path, "projects/abs/domains/ops/streams/s1/epic.md")
        self.assertEqual(ws.streams[0].stories, {})

    def test_invalid_json_kept_as_lifecycle_error(self):
        rel = "projects/abs/domains/ops/streams/s1/stream.json"
        self.write(rel, '{"key": "stream:abs/ops/s1",\n"profile": \n')
        self.write("projects/abs/domains/ops/streams/s1/stories/a/story.md", "---\nkey: story:abs/ops/a\n---\n")
        ws = self.workspace()
        stream = ws.streams[0]
        self.assertIsNone(stream.data)
        self.assertIsNone(stream.profile_name)
        self.assertEqual((stream.error.path, stream.error.rule), (rel, "lifecycle"))
        self.assertIsInstance(stream.error.line, int)
        self.assertEqual(list(stream.stories), ["story:abs/ops/a"])

    def test_non_object_json_kept_as_lifecycle_error(self):
        rel = "projects/abs/domains/ops/streams/s1/stream.json"
        self.write(rel, "[]\n")
        stream = self.workspace().streams[0]
        self.assertIsNone(stream.data)
        self.assertEqual((stream.error.path, stream.error.line, stream.error.rule), (rel, 1, "lifecycle"))

    def test_non_string_profile_gives_no_profile_name(self):
        self.write("projects/abs/domains/ops/streams/s1/stream.json", stream_json("abs", "ops", "s1", profile=["checklist"]))
        stream = self.workspace().streams[0]
        self.assertIsNone(stream.error)
        self.assertIsNone(stream.profile_name)

    def test_stories_across_streams_first_wins(self):
        self.write("projects/abs/domains/ops/streams/a/stream.json", stream_json("abs", "ops", "a"))
        self.write("projects/abs/domains/ops/streams/b/stream.json", stream_json("abs", "ops", "b"))
        self.write("projects/abs/domains/risks/streams/c/stream.json", stream_json("abs", "risks", "c"))
        self.write("projects/abs/domains/ops/streams/a/stories/one/story.md", STORY)
        self.write("projects/abs/domains/ops/streams/b/stories/one/story.md", STORY)
        self.write("projects/abs/domains/ops/streams/b/stories/two/story.md", STORY)
        self.write("projects/abs/domains/risks/streams/c/stories/one/story.md", STORY)
        ws = self.workspace()
        self.assertEqual(
            [s.key for s in ws.streams],
            ["stream:abs/ops/a", "stream:abs/ops/b", "stream:abs/risks/c"],
        )
        self.assertEqual(
            sorted(ws.stories),
            ["story:abs/ops/one", "story:abs/ops/two", "story:abs/risks/one"],
        )
        self.assertEqual(ws.stories["story:abs/ops/one"].stream, "a")
        self.assertEqual(ws.stories["story:abs/risks/one"].domain, "risks")

    def test_same_domain_in_two_projects_keeps_distinct_keys(self):
        self.write("projects/abs/domains/ops/streams/s/stream.json", stream_json("abs", "ops", "s"))
        self.write("projects/web/domains/ops/streams/s/stream.json", stream_json("web", "ops", "s"))
        self.write("projects/abs/domains/ops/streams/s/stories/one/story.md", STORY)
        self.write("projects/web/domains/ops/streams/s/stories/one/story.md", STORY)
        ws = self.workspace()
        self.assertEqual([s.key for s in ws.streams], ["stream:abs/ops/s", "stream:web/ops/s"])
        self.assertEqual(sorted(ws.stories), ["story:abs/ops/one", "story:web/ops/one"])
        self.assertEqual(ws.stories["story:web/ops/one"].project, "web")

    def assert_missing_stream_json(self, stream, project, domain, name):
        rel = "projects/%s/domains/%s/streams/%s/stream.json" % (project, domain, name)
        self.assertEqual(
            (stream.key, stream.path, stream.data, stream.profile_name),
            ("stream:%s/%s/%s" % (project, domain, name), rel, None, None),
        )
        self.assertEqual(tuple(stream.error), (rel, 1, "lifecycle", "missing stream.json"))

    def test_stories_without_stream_json_discovered(self):
        self.write("projects/abs/domains/ops/streams/a/stories/one/story.md", STORY)
        self.write("projects/abs/domains/ops/streams/b/stream.json", stream_json("abs", "ops", "b"))
        self.write("projects/abs/domains/ops/streams/c/epic.md", "# Epic\n")
        ws = self.workspace()
        self.assertEqual([s.key for s in ws.streams], ["stream:abs/ops/a", "stream:abs/ops/b"])
        orphan = ws.streams[0]
        self.assert_missing_stream_json(orphan, "abs", "ops", "a")
        self.assertEqual(list(orphan.stories), ["story:abs/ops/one"])
        self.assertIs(ws.stories["story:abs/ops/one"], orphan.stories["story:abs/ops/one"])
        self.assertEqual(ws.stories["story:abs/ops/one"].stream, "a")

    def test_stories_with_ignored_stream_json_discovered(self):
        subprocess.run(["git", "init", "-q"], cwd=str(self.root), check=True)
        self.write(".gitignore", "projects/abs/domains/ops/streams/a/stream.json\n")
        self.write("projects/abs/domains/ops/streams/a/stream.json", stream_json("abs", "ops", "a"))
        self.write("projects/abs/domains/ops/streams/a/stories/one/story.md", STORY)
        ws = self.workspace()
        self.assertEqual(len(ws.streams), 1)
        self.assert_missing_stream_json(ws.streams[0], "abs", "ops", "a")
        self.assertEqual(list(ws.stories), ["story:abs/ops/one"])

    def test_missing_frontmatter_story_is_error(self):
        self.write("projects/abs/domains/ops/streams/a/stream.json", stream_json("abs", "ops", "a"))
        self.write("projects/abs/domains/ops/streams/a/stories/one/story.md", "# One\n\n## Goal\n")
        story = self.workspace().stories["story:abs/ops/one"]
        self.assertIsNone(story.fields)
        self.assertEqual(story.error, "missing frontmatter")

    def test_deeply_nested_stream_json_is_lifecycle_error(self):
        rel = "projects/abs/domains/ops/streams/s1/stream.json"
        self.write(rel, "[" * 200000 + "]" * 200000 + "\n")
        self.write("tracker/trackers.json", "{\"trackers\": " + "[" * 200000 + "\n")
        ws = self.workspace()
        stream = ws.streams[0]
        self.assertIsNone(stream.data)
        self.assertEqual((stream.error.path, stream.error.line, stream.error.rule), (rel, 1, "lifecycle"))
        self.assertEqual(ws.trackers, [])


class TasksTest(ModelTestCase):
    def test_workspace_task_discovered(self):
        self.write("tasks/e2e-checkout/task.md", TASK)
        ws = self.workspace()
        self.assertEqual(list(ws.tasks), ["task:e2e-checkout"])
        task = ws.tasks["task:e2e-checkout"]
        self.assertIsInstance(task, Task)
        self.assertEqual(
            (task.key, task.slug, task.path, task.error),
            ("task:e2e-checkout", "e2e-checkout", "tasks/e2e-checkout/task.md", None),
        )
        self.assertEqual(task.fields["type"], "e2e")
        self.assertEqual(task.fields["status"], "waiting")
        self.assertEqual([heading for _, heading, _ in task.sections], ["Goal"])

    def test_task_missing_frontmatter_is_error(self):
        self.write("tasks/plain/task.md", "# Plain\n")
        task = self.workspace().tasks["task:plain"]
        self.assertIsNone(task.fields)
        self.assertEqual(task.error, "missing frontmatter")

    def test_only_direct_task_md_discovered(self):
        self.write("tasks/real/task.md", TASK)
        self.write("tasks/real/notes.md", "# Notes\n")
        self.write("tasks/real/work.md", "# Work\n")
        self.write("tasks/real/sub/task.md", TASK)
        self.write("tasks/loose.md", TASK)
        ws = self.workspace()
        self.assertEqual(list(ws.tasks), ["task:real"])


class TrackersTest(ModelTestCase):
    def test_trackers_loaded_and_match_tracker(self):
        self.write("tracker/trackers.json", json.dumps(TRACKERS) + "\n")
        ws = self.workspace()
        self.assertEqual([t.key for t in ws.trackers], ["jira", "youtrack"])
        self.assertEqual([t.id_pattern for t in ws.trackers], [r"TASK-\d+", r"YT-\d+"])
        self.assertEqual([t.url for t in ws.trackers], ["https://jira/{id}", "https://yt/{id}"])
        for tracker in ws.trackers:
            self.assertIsInstance(tracker.pattern, re.Pattern)
        self.assertEqual(ws.match_tracker("TASK-12"), "jira")
        self.assertEqual(ws.match_tracker("YT-9"), "youtrack")
        self.assertIsNone(ws.match_tracker("OTHER-1"))

    def test_ambiguous_id_reported_by_match_tracker(self):
        data = {"trackers": TRACKERS["trackers"] + [{"key": "legacy", "id_pattern": r"TASK-1\d+", "url": "u"}]}
        self.write("tracker/trackers.json", json.dumps(data) + "\n")
        ws = self.workspace()
        self.assertEqual(ws.match_tracker("TASK-12"), "ambiguous")
        self.assertEqual(ws.match_tracker("TASK-5"), "jira")

    def test_invalid_entries_skipped(self):
        data = {
            "trackers": [
                7,
                {"key": "no-pattern"},
                {"key": "bad", "id_pattern": "(", "url": "u"},
                {"id_pattern": r"X-\d+", "url": "u"},
                {"key": "jira", "id_pattern": r"TASK-\d+", "url": "https://jira/{id}"},
            ]
        }
        self.write("tracker/trackers.json", json.dumps(data) + "\n")
        ws = self.workspace()
        self.assertEqual([t.key for t in ws.trackers], ["jira"])
        self.assertEqual(ws.match_tracker("TASK-1"), "jira")

    def test_missing_or_invalid_file_gives_no_trackers(self):
        self.assertEqual(self.workspace().trackers, [])
        self.assertIsNone(self.workspace().match_tracker("TASK-1"))
        self.write("tracker/trackers.json", "{\n")
        ws = self.workspace()
        self.assertEqual(ws.trackers, [])
        self.assertIsNone(ws.match_tracker("TASK-1"))


class WorkspaceFilesTest(ModelTestCase):
    def test_map_docs(self):
        self.write("projects/abs/domains/operations/MAP.md", "# Map\n")
        self.write("projects/web/domains/operations/MAP.md", "# Web map\n")
        self.write("projects/abs/domains/clients/README.md", "# Clients\n")
        self.write("projects/abs/domains/clients/map/home.md", "---\nkey: screen:abs/clients/home\n---\n")
        ws = self.workspace()
        self.assertEqual(
            ws.map_docs,
            {
                "abs/operations": "projects/abs/domains/operations/MAP.md",
                "web/operations": "projects/web/domains/operations/MAP.md",
            },
        )

    def test_ignored_files_not_discovered(self):
        subprocess.run(["git", "init", "-q"], cwd=str(self.root), check=True)
        self.write(
            ".gitignore",
            "projects/abs/domains/operations/map/secret.md\nprojects/abs/domains/operations/streams/hidden/\n"
            "projects/abs/domains/operations/streams/arm/stories/draft/\nprojects/abs/domains/clients/MAP.md\n"
            "tasks/draft/\n",
        )
        self.write("projects/abs/domains/operations/map/list.md", SCREEN_LIST)
        self.write("projects/abs/domains/operations/map/secret.md", "---\nkey: screen:abs/operations/secret\n---\n")
        self.write(
            "projects/abs/domains/operations/streams/arm/stream.json",
            stream_json("abs", "operations", "arm"),
        )
        self.write("projects/abs/domains/operations/streams/arm/stories/card/story.md", STORY)
        self.write("projects/abs/domains/operations/streams/arm/stories/draft/story.md", STORY)
        self.write("projects/abs/domains/operations/streams/hidden/stream.json", stream_json("abs", "operations", "hidden"))
        self.write("projects/abs/domains/operations/MAP.md", "# Map\n")
        self.write("projects/abs/domains/clients/MAP.md", "# Map\n")
        self.write("tasks/e2e-checkout/task.md", TASK)
        self.write("tasks/draft/x/task.md", TASK)
        ws = self.workspace()
        self.assertEqual(list(ws.elements), ["screen:abs/operations/list"])
        self.assertEqual([s.key for s in ws.streams], ["stream:abs/operations/arm"])
        self.assertEqual(list(ws.stories), ["story:abs/operations/card"])
        self.assertEqual(list(ws.tasks), ["task:e2e-checkout"])
        self.assertEqual(ws.map_docs, {"abs/operations": "projects/abs/domains/operations/MAP.md"})


if __name__ == "__main__":
    unittest.main()
