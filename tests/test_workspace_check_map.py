import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
import tempfile
import unittest

from workspace_helpers import create_workspace, run_check, run_generate

RULE = "map"
FIXTURE = Path(__file__).resolve().parent / "fixtures/profiles/checklist/profile.json"
SCREEN_PATH = "projects/abs/domains/operations/map/documents.md"

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

FIELDS = [
    ("key", "screen:abs/operations/documents"),
    ("route", "/documents"),
    ("kind", "place"),
    ("section", "documents"),
    ("parent", ""),
    ("access", "getDocuments"),
    ("label", "Documents"),
    ("wave", "1"),
    ("story", "story:abs/operations/documents"),
]

# With FIELDS unchanged the Transitions heading is file line 14 and its first row line 18.
TRANSITIONS = "## Transitions\n\n| Action | Target |\n|---|---|\n| Open | screen:abs/operations/documents |\n"

STORY = """---
key: story:abs/operations/documents
type: story
wave: 1
tracker:
scope: [screen:abs/operations/documents]
depends: []
repos: []
decisions: []
mockups: []
---
# Documents

## Goal

Show documents.
"""


def screen(fields=None, body=TRANSITIONS, drop=(), override=None):
    override = override or {}
    lines = ["---"]
    for name, value in fields or FIELDS:
        if name in drop:
            continue
        value = override.get(name, value)
        lines.append("%s: %s" % (name, value) if value != "" else "%s:" % name)
    lines += ["---", "# Documents", "", body]
    return "\n".join(lines)


def map_lines(lines):
    return [line for line in lines if len(line.split(" ")) > 1 and line.split(" ")[1] == RULE]


class CheckMapTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.ws = create_workspace(self.tmp)
        self.write_json(".agents/profiles/ui-migration/profile.json", UI_MIGRATION)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text):
        path = self.ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def write_json(self, rel, obj):
        self.write(rel, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")

    def stream(self, stage="goal"):
        self.write_json("projects/abs/domains/operations/streams/docs/stream.json", {
            "key": "stream:abs/operations/docs",
            "profile": "ui-migration",
            "stage": stage,
            "scope": ["screen:abs/operations/documents"],
            "approvals": [],
        })
        self.write("projects/abs/domains/operations/streams/docs/stories/documents/story.md", STORY)

    def findings(self):
        _, lines, stderr = run_check(self.ws)
        self.assertNotIn("Traceback", stderr)
        return map_lines(lines)

    def assert_finding_at(self, prefix):
        lines = self.findings()
        self.assertTrue(any(line.startswith(prefix) for line in lines), lines)
        return lines

    def test_fresh_workspace_has_no_map_findings(self):
        self.assertEqual(self.findings(), [])

    def test_poc_screen_has_no_finding(self):
        self.stream()
        self.write(SCREEN_PATH, screen())
        self.assertEqual(self.findings(), [])

    def test_screen_missing_access(self):
        self.stream()
        self.write(SCREEN_PATH, screen(drop=("access",)))
        lines = self.assert_finding_at(SCREEN_PATH + ":")
        self.assertTrue(any("access" in line for line in lines), lines)

    def test_empty_story_field_on_map_stage_screen(self):
        self.stream(stage="map")
        self.write(SCREEN_PATH, screen(override={"story": ""}))
        self.assertEqual(self.findings(), [])

    def test_empty_story_field_on_decomposition_stage_screen(self):
        self.stream(stage="decomposition")
        self.write(SCREEN_PATH, screen(override={"story": ""}))
        self.assertEqual(self.findings(), [])

    def test_empty_story_field_after_decomposition(self):
        for stage in ("ready", "delivery", "done"):
            with self.subTest(stage=stage):
                self.stream(stage=stage)
                self.write(SCREEN_PATH, screen(override={"story": ""}))
                self.assertEqual(self.findings(), [
                    SCREEN_PATH + ":10 map field story is empty after decomposition of stream:abs/operations/docs"])

    def test_empty_story_field_outside_closed_stream(self):
        self.stream(stage="ready")
        self.write("projects/abs/domains/operations/map/other.md",
                   screen(override={"key": "screen:abs/operations/other", "story": ""}))
        self.write(SCREEN_PATH, screen())
        self.assertEqual(self.findings(), [])

    def test_story_field_must_be_present(self):
        self.stream()
        self.write(SCREEN_PATH, screen(drop=("story",)))
        self.assert_finding_at(SCREEN_PATH + ":")

    def test_story_naming_missing_story(self):
        self.write(SCREEN_PATH, screen())
        lines = self.assert_finding_at(SCREEN_PATH + ":10 map ")
        self.assertTrue(any("story:abs/operations/documents" in line for line in lines), lines)

    def test_wrong_kind_value(self):
        self.stream()
        self.write(SCREEN_PATH, screen(override={"kind": "modal"}))
        self.assert_finding_at(SCREEN_PATH + ":4 map ")

    def test_empty_value_not_allowed(self):
        self.stream()
        self.write(SCREEN_PATH, screen(override={"route": ""}))
        self.assert_finding_at(SCREEN_PATH + ":3 map ")

    def test_pipe_in_label_breaks_map_row(self):
        self.stream()
        self.write(SCREEN_PATH, screen(override={"label": "Documents | Files"}))
        self.assert_finding_at(SCREEN_PATH + ':8 map field label value contains "|"')

    def test_pipe_in_list_item_breaks_map_row(self):
        self.stream()
        self.write(SCREEN_PATH, screen(override={"parent": "[screen:abs/operations/a | b]"}))
        self.assert_finding_at(SCREEN_PATH + ':6 map field parent value contains "|"')

    def test_wrong_transitions_columns_on_heading_line(self):
        self.stream()
        self.write(SCREEN_PATH, screen(body="## Transitions\n\n| Action | Screen |\n|---|---|\n| Open | x |\n"))
        self.assert_finding_at(SCREEN_PATH + ":14 map ")

    def test_missing_transitions_table(self):
        self.stream()
        self.write(SCREEN_PATH, screen(body="## Notes\n\nNone.\n"))
        self.assert_finding_at(SCREEN_PATH + ":")

    def test_transitions_section_without_table(self):
        self.stream()
        self.write(SCREEN_PATH, screen(body="## Transitions\n\nNone.\n"))
        self.assert_finding_at(SCREEN_PATH + ":14 map ")

    def test_broken_table_row_reported_on_its_line(self):
        self.stream()
        self.write(SCREEN_PATH, screen(body=TRANSITIONS.replace("| Open |", "| Open | extra |")))
        self.assert_finding_at(SCREEN_PATH + ":18 map ")

    def test_broken_frontmatter(self):
        self.stream()
        text = screen().replace("access: getDocuments", "access getDocuments")
        self.write(SCREEN_PATH, text)
        self.assert_finding_at(SCREEN_PATH + ":7 map ")

    def test_element_without_frontmatter(self):
        self.write(SCREEN_PATH, "# Documents\n\n" + TRANSITIONS)
        lines = self.assert_finding_at(SCREEN_PATH + ":1 map ")
        self.assertTrue(any("missing frontmatter" in line for line in lines), lines)

    def test_key_path_mismatch(self):
        self.stream()
        self.write(SCREEN_PATH, screen(override={"key": "screen:abs/operations/other"}))
        self.assert_finding_at(SCREEN_PATH + ":2 map ")

    def test_checklist_element_uses_its_own_fields(self):
        self.write("projects/abs/domains/ops/rules/audit.md", "---\nkey: rule:abs/ops/audit\nowner:\nstory:\n---\n\n## Checks\n\n"
                   "| Check | Target |\n|---|---|\n")
        self.write(".agents/profiles/checklist/profile.json", FIXTURE.read_text(encoding="utf-8"))
        self.assert_finding_at("projects/abs/domains/ops/rules/audit.md:3 map ")
        self.write("projects/abs/domains/ops/rules/audit.md", "---\nkey: rule:abs/ops/audit\nowner: team\nstory:\n---\n\n## Checks\n\n"
                   "| Check | Target |\n|---|---|\n")
        self.assertEqual(self.findings(), [])

    # Delta scenario "map without markers": a marker-less domain MAP.md on the projects layout gives `map`.
    # The spec prose writes `projects/abs/risks/MAP.md`; the model discovers `projects/<project>/domains/<domain>/MAP.md`.
    def test_map_without_markers(self):
        self.write("projects/abs/domains/risks/MAP.md", "# Map of domain risks\n\n## Legacy trace\n")
        self.assert_finding_at("projects/abs/domains/risks/MAP.md:1 map ")

    def test_map_with_markers_has_no_finding(self):
        template = (REPO / "kits/workspace/.agents/profiles/ui-migration/MAP.md").read_text(encoding="utf-8")
        self.write("projects/abs/domains/risks/MAP.md", template.replace("<domain>", "risks"))
        self.assertEqual(self.findings(), [])

    def test_indented_marker_gives_finding(self):
        self.write("projects/abs/domains/risks/MAP.md", "# Map\n\n  <!-- map:screens:begin -->\n<!-- map:screens:end -->\n")
        self.assert_finding_at("projects/abs/domains/risks/MAP.md:1 map ")

    def test_marker_with_trailing_space_gives_finding(self):
        self.write("projects/abs/domains/risks/MAP.md", "# Map\n\n<!-- map:screens:begin --> \n<!-- map:screens:end -->\n")
        self.assert_finding_at("projects/abs/domains/risks/MAP.md:1 map ")

    def test_map_with_only_transitions_markers_has_no_finding(self):
        self.write("projects/abs/domains/risks/MAP.md", "# Map\n\n<!-- map:transitions:begin -->\n<!-- map:transitions:end -->\n")
        self.assertEqual(self.findings(), [])

    def test_generate_renders_map_that_check_accepts(self):
        self.stream()
        self.write(SCREEN_PATH, screen())
        template = (REPO / "kits/workspace/.agents/profiles/ui-migration/MAP.md").read_text(encoding="utf-8")
        self.write("projects/abs/domains/operations/MAP.md", template.replace("<domain>", "operations"))
        self.assertEqual([line for line in self.findings() if "MAP.md" in line], [])
        result = run_generate(self.ws)
        self.assertEqual(result.returncode, 0, result.stderr)
        text = (self.ws / "projects/abs/domains/operations/MAP.md").read_text(encoding="utf-8")
        self.assertIn("| screen:abs/operations/documents | /documents | place |", text)
        self.assertIn("| screen:abs/operations/documents | Open | screen:abs/operations/documents |", text)


if __name__ == "__main__":
    unittest.main()
