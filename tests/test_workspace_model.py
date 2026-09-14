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
from wslib.model import Element, Story, Stream, Workspace

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
        "fields": ["key", "type", "wave", "tracker", "scope", "depends", "repos", "decisions", "mockups"],
        "may_be_empty": ["tracker", "scope", "depends", "repos", "decisions", "mockups"],
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
key: screen:operations/list
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
| Open | screen:operations/card |
| Back | screen:clients/home |
"""

SCREEN_CARD = """---
key: screen:operations/card
route: /operations/:id
kind: place
section: Operations
parent: screen:operations/list
access: getOperation
label: Operation
wave: 1
story: story:operations/card
---
# Operation card

## Notes

No table here.
"""

STORY = """---
key: story:operations/card
type: story
wave: 1
tracker: TASK-1
scope: [screen:operations/card]
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


def stream_json(domain, stream, profile="ui-migration", **extra):
    data = {
        "key": "stream:%s/%s" % (domain, stream),
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
        self.write("domains/ops/rules/r1.md", "---\nkey: rule:ops/r1\nowner: me\nstory:\n---\n")
        ws = self.workspace()
        self.assertEqual(sorted(ws.profiles), ["ui-migration"])
        self.assertTrue(ws.profile_findings)
        self.assertEqual({f.rule for f in ws.profile_findings}, {"profile"})
        self.assertEqual(ws.elements, {})
        self.assertEqual(ws.element_list, [])


class ElementsTest(ModelTestCase):
    def test_elements_per_kind_and_domain(self):
        self.write("domains/operations/map/list.md", SCREEN_LIST)
        self.write("domains/operations/map/card.md", SCREEN_CARD)
        self.write("domains/clients/map/home.md", "---\nkey: screen:clients/home\n---\n# Home\n")
        self.write("domains/ops/rules/r1.md", "---\nkey: rule:ops/r1\nowner: me\nstory:\n---\n# R1\n")
        ws = self.workspace()
        self.assertEqual(
            sorted(ws.elements),
            ["rule:ops/r1", "screen:clients/home", "screen:operations/card", "screen:operations/list"],
        )
        self.assertEqual(len(ws.element_list), 4)

        card = ws.elements["screen:operations/card"]
        self.assertIsInstance(card, Element)
        self.assertEqual(
            (card.key, card.kind, card.domain, card.slug, card.path, card.error),
            ("screen:operations/card", "screen", "operations", "card", "domains/operations/map/card.md", None),
        )
        self.assertEqual(card.fields["parent"], "screen:operations/list")
        self.assertEqual(card.fields["story"], "story:operations/card")
        self.assertEqual(card.tables["Transitions"], (None, [], None))

        rule = ws.elements["rule:ops/r1"]
        self.assertEqual((rule.kind, rule.domain, rule.slug), ("rule", "ops", "r1"))
        self.assertEqual(rule.fields, {"key": "rule:ops/r1", "owner": "me", "story": ""})
        self.assertEqual(rule.tables, {"Checks": (None, [], None)})

    def test_tables_parsed_with_file_lines(self):
        self.write("domains/operations/map/list.md", SCREEN_LIST)
        ws = self.workspace()
        columns, rows, error = ws.elements["screen:operations/list"].tables["Transitions"]
        self.assertEqual(columns, ["Action", "Target"])
        self.assertIsNone(error)
        lines = SCREEN_LIST.split("\n")
        self.assertEqual(lines[rows[0][0] - 1], "| Open | screen:operations/card |")
        self.assertEqual(
            rows,
            [
                (rows[0][0], ["Open", "screen:operations/card"]),
                (rows[0][0] + 1, ["Back", "screen:clients/home"]),
            ],
        )

    def test_key_from_path_not_frontmatter(self):
        self.write("domains/operations/map/list.md", SCREEN_LIST.replace("screen:operations/list", "screen:x/y", 1))
        ws = self.workspace()
        element = ws.elements["screen:operations/list"]
        self.assertEqual(element.fields["key"], "screen:x/y")
        self.assertNotIn("screen:x/y", ws.elements)

    def test_frontmatter_error_kept(self):
        self.write("domains/operations/map/bad.md", "---\nkey: screen:operations/bad\n\nroute: /bad\n---\n")
        ws = self.workspace()
        bad = ws.elements["screen:operations/bad"]
        self.assertIsNone(bad.fields)
        self.assertIn("blank line", bad.error)

    def test_missing_frontmatter_is_error(self):
        self.write("domains/operations/map/plain.md", "# Plain\n")
        self.write("domains/operations/map/empty.md", "")
        ws = self.workspace()
        for key in ("screen:operations/plain", "screen:operations/empty"):
            element = ws.elements[key]
            self.assertIsNone(element.fields, key)
            self.assertEqual(element.error, "missing frontmatter", key)

    def test_shared_dir_first_kind_wins_and_is_reported(self):
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        data["elements"][0]["dir"] = "map"
        self.write(".agents/profiles/checklist/profile.json", json.dumps(data) + "\n")
        self.write("domains/operations/map/list.md", SCREEN_LIST)
        ws = self.workspace()
        self.assertEqual(sorted(ws.profiles), ["checklist", "ui-migration"])
        self.assertEqual(list(ws.elements), ["rule:operations/list"])
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
        self.write("domains/operations/map/list.md", SCREEN_LIST)
        ws = self.workspace()
        self.assertEqual(list(ws.elements), ["screen:operations/list"])
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
        self.write("domains/operations/map/list.md", SCREEN_LIST)
        self.write("domains/operations/views/list.md", "---\nkey: screen:operations/list\n---\n")
        ws = self.workspace()
        self.assertEqual(ws.elements["screen:operations/list"].path, "domains/operations/map/list.md")
        self.assertEqual(
            [e.path for e in ws.element_list],
            ["domains/operations/map/list.md", "domains/operations/views/list.md"],
        )

    def test_only_direct_md_files_of_element_dir(self):
        self.write("domains/operations/map/list.md", SCREEN_LIST)
        self.write("domains/operations/map/notes.txt", "x\n")
        self.write("domains/operations/map/deep/inner.md", "---\nkey: screen:operations/inner\n---\n")
        self.write("domains/operations/MAP.md", "# Map\n")
        self.write("map/top.md", "---\nkey: screen:top\n---\n")
        ws = self.workspace()
        self.assertEqual(list(ws.elements), ["screen:operations/list"])


class StreamsTest(ModelTestCase):
    def test_stream_with_stories(self):
        base = "domains/operations/streams/arm"
        self.write(base + "/stream.json", stream_json("operations", "arm", scope=["screen:operations/card"]))
        self.write(base + "/epic.md", "# Epic\n")
        self.write(base + "/stories/card/story.md", STORY)
        self.write(base + "/stories/list/story.md", "---\nkey: story:operations/list\nscope: [\n---\n")
        self.write(base + "/stories/card/notes.md", "# Notes\n")
        self.write(base + "/stories/stray.md", "# Stray\n")
        ws = self.workspace()
        self.assertEqual(len(ws.streams), 1)
        stream = ws.streams[0]
        self.assertIsInstance(stream, Stream)
        self.assertEqual(
            (stream.key, stream.domain, stream.name, stream.path, stream.error, stream.profile_name, stream.epic_path),
            (
                "stream:operations/arm",
                "operations",
                "arm",
                base + "/stream.json",
                None,
                "ui-migration",
                base + "/epic.md",
            ),
        )
        self.assertEqual(stream.data["scope"], ["screen:operations/card"])
        self.assertEqual(sorted(stream.stories), ["story:operations/card", "story:operations/list"])

        card = stream.stories["story:operations/card"]
        self.assertIsInstance(card, Story)
        self.assertEqual(
            (card.key, card.domain, card.stream, card.slug, card.path, card.error),
            ("story:operations/card", "operations", "arm", "card", base + "/stories/card/story.md", None),
        )
        self.assertEqual(card.fields["tracker"], "TASK-1")
        self.assertEqual([heading for _, heading, _ in card.sections], ["Goal", "Open questions"])
        line, _, text = card.sections[1]
        self.assertEqual(STORY.split("\n")[line - 1], "## Open questions")
        self.assertEqual(text.strip(), "None.")

        broken = stream.stories["story:operations/list"]
        self.assertIsNone(broken.fields)
        self.assertIn("unclosed [", broken.error)

    def test_epic_path_given_when_absent(self):
        self.write("domains/ops/streams/s1/stream.json", stream_json("ops", "s1", profile="checklist"))
        ws = self.workspace()
        self.assertEqual(ws.streams[0].epic_path, "domains/ops/streams/s1/epic.md")
        self.assertEqual(ws.streams[0].stories, {})

    def test_invalid_json_kept_as_lifecycle_error(self):
        rel = "domains/ops/streams/s1/stream.json"
        self.write(rel, '{"key": "stream:ops/s1",\n"profile": \n')
        self.write("domains/ops/streams/s1/stories/a/story.md", "---\nkey: story:ops/a\n---\n")
        ws = self.workspace()
        stream = ws.streams[0]
        self.assertIsNone(stream.data)
        self.assertIsNone(stream.profile_name)
        self.assertEqual((stream.error.path, stream.error.rule), (rel, "lifecycle"))
        self.assertIsInstance(stream.error.line, int)
        self.assertEqual(list(stream.stories), ["story:ops/a"])

    def test_non_object_json_kept_as_lifecycle_error(self):
        rel = "domains/ops/streams/s1/stream.json"
        self.write(rel, "[]\n")
        stream = self.workspace().streams[0]
        self.assertIsNone(stream.data)
        self.assertEqual((stream.error.path, stream.error.line, stream.error.rule), (rel, 1, "lifecycle"))

    def test_non_string_profile_gives_no_profile_name(self):
        self.write("domains/ops/streams/s1/stream.json", stream_json("ops", "s1", profile=["checklist"]))
        stream = self.workspace().streams[0]
        self.assertIsNone(stream.error)
        self.assertIsNone(stream.profile_name)

    def test_stories_across_streams_first_wins(self):
        self.write("domains/ops/streams/a/stream.json", stream_json("ops", "a"))
        self.write("domains/ops/streams/b/stream.json", stream_json("ops", "b"))
        self.write("domains/risks/streams/c/stream.json", stream_json("risks", "c"))
        self.write("domains/ops/streams/a/stories/one/story.md", STORY)
        self.write("domains/ops/streams/b/stories/one/story.md", STORY)
        self.write("domains/ops/streams/b/stories/two/story.md", STORY)
        self.write("domains/risks/streams/c/stories/one/story.md", STORY)
        ws = self.workspace()
        self.assertEqual([s.key for s in ws.streams], ["stream:ops/a", "stream:ops/b", "stream:risks/c"])
        self.assertEqual(sorted(ws.stories), ["story:ops/one", "story:ops/two", "story:risks/one"])
        self.assertEqual(ws.stories["story:ops/one"].stream, "a")
        self.assertEqual(ws.stories["story:risks/one"].domain, "risks")

    def assert_missing_stream_json(self, stream, domain, name):
        rel = "domains/%s/streams/%s/stream.json" % (domain, name)
        self.assertEqual((stream.key, stream.path, stream.data, stream.profile_name), ("stream:%s/%s" % (domain, name), rel, None, None))
        self.assertEqual(tuple(stream.error), (rel, 1, "lifecycle", "missing stream.json"))

    def test_stories_without_stream_json_discovered(self):
        self.write("domains/ops/streams/a/stories/one/story.md", STORY)
        self.write("domains/ops/streams/b/stream.json", stream_json("ops", "b"))
        self.write("domains/ops/streams/c/epic.md", "# Epic\n")
        ws = self.workspace()
        self.assertEqual([s.key for s in ws.streams], ["stream:ops/a", "stream:ops/b"])
        orphan = ws.streams[0]
        self.assert_missing_stream_json(orphan, "ops", "a")
        self.assertEqual(list(orphan.stories), ["story:ops/one"])
        self.assertIs(ws.stories["story:ops/one"], orphan.stories["story:ops/one"])
        self.assertEqual(ws.stories["story:ops/one"].stream, "a")

    def test_stories_with_ignored_stream_json_discovered(self):
        subprocess.run(["git", "init", "-q"], cwd=str(self.root), check=True)
        self.write(".gitignore", "domains/ops/streams/a/stream.json\n")
        self.write("domains/ops/streams/a/stream.json", stream_json("ops", "a"))
        self.write("domains/ops/streams/a/stories/one/story.md", STORY)
        ws = self.workspace()
        self.assertEqual(len(ws.streams), 1)
        self.assert_missing_stream_json(ws.streams[0], "ops", "a")
        self.assertEqual(list(ws.stories), ["story:ops/one"])

    def test_missing_frontmatter_story_is_error(self):
        self.write("domains/ops/streams/a/stream.json", stream_json("ops", "a"))
        self.write("domains/ops/streams/a/stories/one/story.md", "# One\n\n## Goal\n")
        story = self.workspace().stories["story:ops/one"]
        self.assertIsNone(story.fields)
        self.assertEqual(story.error, "missing frontmatter")

    def test_deeply_nested_stream_json_is_lifecycle_error(self):
        rel = "domains/ops/streams/s1/stream.json"
        self.write(rel, "[" * 200000 + "]" * 200000 + "\n")
        self.write("tracker/tracker.json", "{\"id_pattern\": " + "[" * 200000 + "\n")
        ws = self.workspace()
        stream = ws.streams[0]
        self.assertIsNone(stream.data)
        self.assertEqual((stream.error.path, stream.error.line, stream.error.rule), (rel, 1, "lifecycle"))
        self.assertIsNone(ws.id_pattern)


class WorkspaceFilesTest(ModelTestCase):
    def test_map_docs(self):
        self.write("domains/operations/MAP.md", "# Map\n")
        self.write("domains/clients/README.md", "# Clients\n")
        self.write("domains/clients/map/home.md", "---\nkey: screen:clients/home\n---\n")
        ws = self.workspace()
        self.assertEqual(ws.map_docs, {"operations": "domains/operations/MAP.md"})

    def test_id_pattern_compiled(self):
        self.write("tracker/tracker.json", json.dumps({"id_pattern": r"TASK-\d+", "url": "https://t/{id}"}) + "\n")
        ws = self.workspace()
        self.assertIsInstance(ws.id_pattern, re.Pattern)
        self.assertTrue(ws.id_pattern.fullmatch("TASK-12"))

    def test_id_pattern_uncompilable_is_none(self):
        for pattern in ("a{4294967296}", "(", 7):
            self.write("tracker/tracker.json", json.dumps({"id_pattern": pattern, "url": "u"}) + "\n")
            self.assertIsNone(self.workspace().id_pattern, pattern)

    def test_id_pattern_missing_or_invalid_file_is_none(self):
        self.assertIsNone(self.workspace().id_pattern)
        self.write("tracker/tracker.json", "{\n")
        self.assertIsNone(self.workspace().id_pattern)

    def test_ignored_files_not_discovered(self):
        subprocess.run(["git", "init", "-q"], cwd=str(self.root), check=True)
        self.write(
            ".gitignore",
            "domains/operations/map/secret.md\ndomains/operations/streams/hidden/\n"
            "domains/operations/streams/arm/stories/draft/\ndomains/clients/MAP.md\n",
        )
        self.write("domains/operations/map/list.md", SCREEN_LIST)
        self.write("domains/operations/map/secret.md", "---\nkey: screen:operations/secret\n---\n")
        self.write("domains/operations/streams/arm/stream.json", stream_json("operations", "arm"))
        self.write("domains/operations/streams/arm/stories/card/story.md", STORY)
        self.write("domains/operations/streams/arm/stories/draft/story.md", STORY)
        self.write("domains/operations/streams/hidden/stream.json", stream_json("operations", "hidden"))
        self.write("domains/operations/MAP.md", "# Map\n")
        self.write("domains/clients/MAP.md", "# Map\n")
        ws = self.workspace()
        self.assertEqual(list(ws.elements), ["screen:operations/list"])
        self.assertEqual([s.key for s in ws.streams], ["stream:operations/arm"])
        self.assertEqual(list(ws.stories), ["story:operations/card"])
        self.assertEqual(ws.map_docs, {"operations": "domains/operations/MAP.md"})


if __name__ == "__main__":
    unittest.main()
