import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
import tempfile
import unittest

from wslib.common import Context
from wslib.model import Workspace
from wslib.predicates import PREDICATES, Issue
from wslib.profiles import KNOWN_GATES

UI_MIGRATION = REPO / "kits/workspace/.agents/profiles/ui-migration/profile.json"
CHECKLIST = Path(__file__).resolve().parent / "fixtures/profiles/checklist/profile.json"

PROJECT = "abs"
OPS = "projects/abs/domains/operations/streams/arm"
RULES = "projects/abs/domains/ops/streams/audit"


def screen(key, transitions=(), story=""):
    rows = "".join("| Go | %s |\n" % target for target in transitions)
    return (
        "---\nkey: %s\nroute: /x\nkind: place\nsection: S\nparent:\naccess: a\nlabel: L\nwave: 1\nstory: %s\n---\n"
        "# Screen\n\n## Transitions\n\n| Action | Target |\n|---|---|\n%s" % (key, story, rows)
    )


def rule(key, checks=()):
    rows = "".join("| Check | %s |\n" % target for target in checks)
    return "---\nkey: %s\nowner: me\nstory:\n---\n# Rule\n\n## Checks\n\n| Check | Target |\n|---|---|\n%s" % (key, rows)


def story(key, scope="[]", tracker="", extra="", questions="None.", status="waiting"):
    return (
        "---\nkey: %s\ntype: story\nstatus: %s\ntracker: %s\nscope: %s\n%s---\n# Story\n\n## Goal\n\nDo it.\n\n"
        "## Open questions\n\n%s\n" % (key, status, tracker, scope, extra, questions)
    )


def trackers(*entries):
    return json.dumps({"trackers": [
        {"key": entry[0], "id_pattern": entry[1], "url": "https://t/{id}"} for entry in entries
    ]}, indent=2) + "\n"


class PredicateTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self.write(".agents/kit.json", json.dumps({"name": "workspace", "version": "0.1.0", "params": {}}) + "\n")
        self.write(".agents/profiles/ui-migration/profile.json", UI_MIGRATION.read_text(encoding="utf-8"))
        self.write(".agents/profiles/checklist/profile.json", CHECKLIST.read_text(encoding="utf-8"))
        self.write("tracker/trackers.json", trackers(("tasks", r"TASK-\d+")))

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def stream(self, base, profile="ui-migration", **extra):
        parts = base.split("/")
        data = {"key": "stream:%s/%s/%s" % (parts[1], parts[3], parts[5]), "profile": profile, "stage": "map",
                "scope": [], "approvals": []}
        data.update(extra)
        self.write(base + "/stream.json", json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    def run_gate(self, gate, base, params=None):
        ws = Workspace(Context(self.root))
        stream = next(s for s in ws.streams if s.path == base + "/stream.json")
        profile = ws.profiles.get(stream.profile_name)
        return PREDICATES[gate](ws, stream, profile, {} if params is None else params)

    def line_of(self, rel, prefix):
        lines = (self.root / rel).read_text(encoding="utf-8").split("\n")
        return next(i + 1 for i, line in enumerate(lines) if line.startswith(prefix))


class RegistryTest(unittest.TestCase):
    def test_keys_are_known_gates(self):
        self.assertEqual(set(PREDICATES), set(KNOWN_GATES))
        self.assertEqual(Issue._fields, ("path", "line", "detail"))


class TwoWayCoverageTest(PredicateTestCase):
    def setUp(self):
        super().setUp()
        self.write("projects/abs/domains/operations/map/documents.md", screen("screen:abs/operations/documents"))
        self.write("projects/abs/domains/risks/map/matches.md", screen("screen:abs/risks/matches"))
        self.stream(OPS, stage="decomposition", scope=["screen:abs/operations/documents"])
        self.write(OPS + "/stories/documents/story.md",
                   story("story:abs/operations/documents", "[screen:abs/operations/documents]"))

    def test_unmapped_cleanup_story_passes(self):
        self.write(OPS + "/stories/bff-cleanup/story.md",
                   story("story:abs/operations/bff-cleanup", "[]", extra="unmapped: bff defects\n"))
        self.assertEqual(self.run_gate("two_way_coverage", OPS), [])

    def test_empty_scope_without_unmapped_fails_on_story(self):
        rel = OPS + "/stories/init/story.md"
        self.write(rel, story("story:abs/operations/init", "[]"))
        issues = self.run_gate("two_way_coverage", OPS)
        self.assertEqual([(i.path, i.line) for i in issues], [(rel, self.line_of(rel, "scope:"))])

    def test_empty_unmapped_reason_fails(self):
        rel = OPS + "/stories/init/story.md"
        self.write(rel, story("story:abs/operations/init", "[]", extra="unmapped:  \n"))
        self.assertEqual([i.path for i in self.run_gate("two_way_coverage", OPS)], [rel])

    def test_story_scope_outside_stream_scope_fails_on_story(self):
        rel = OPS + "/stories/matches/story.md"
        self.write(rel, story("story:abs/operations/matches", "[screen:abs/risks/matches]"))
        issues = self.run_gate("two_way_coverage", OPS)
        self.assertEqual(len(issues), 1)
        self.assertEqual((issues[0].path, issues[0].line), (rel, self.line_of(rel, "scope:")))
        self.assertIn("screen:abs/risks/matches", issues[0].detail)

    def test_story_scope_key_missing_fails(self):
        self.stream(OPS, scope=["screen:abs/operations/documents", "screen:abs/operations/ghost"])
        rel = OPS + "/stories/ghost/story.md"
        self.write(rel, story("story:abs/operations/ghost", "[screen:abs/operations/ghost]"))
        issues = self.run_gate("two_way_coverage", OPS)
        self.assertEqual([i.path for i in issues], [rel])
        self.assertIn("screen:abs/operations/ghost", issues[0].detail)

    def test_uncovered_stream_scope_key_fails_on_stream(self):
        self.write("projects/abs/domains/operations/map/report.md", screen("screen:abs/operations/report"))
        self.stream(OPS, scope=["screen:abs/operations/documents", "screen:abs/operations/report"])
        issues = self.run_gate("two_way_coverage", OPS)
        self.assertEqual([(i.path, i.line) for i in issues], [(OPS + "/stream.json", 1)])
        self.assertIn("screen:abs/operations/report", issues[0].detail)

    def test_broken_story_and_bad_types_do_not_raise(self):
        self.write(OPS + "/stories/bad/story.md", "---\nkey: story:abs/operations/bad\nscope: [\n---\n")
        self.write(OPS + "/stories/odd/story.md", "---\nkey: story:abs/operations/odd\nscope: {a: b}\n---\n")
        issues = self.run_gate("two_way_coverage", OPS)
        self.assertEqual(sorted(i.path for i in issues),
                         [OPS + "/stories/bad/story.md", OPS + "/stories/odd/story.md"])
        self.stream(OPS, scope="screen:abs/operations/documents")
        issues = self.run_gate("two_way_coverage", OPS)
        self.assertEqual(sorted((i.path, i.detail) for i in issues), [
            (OPS + "/stories/bad/story.md", "story frontmatter does not parse: frontmatter line 3: unclosed ["),
            (OPS + "/stories/documents/story.md", "scope key screen:abs/operations/documents is not in the stream scope"),
            (OPS + "/stories/odd/story.md", "scope must be a list of keys"),
            (OPS + "/stream.json", "scope must be a list of strings"),
        ])

    def test_checklist_profile(self):
        self.write("projects/abs/domains/ops/rules/r1.md", rule("rule:abs/ops/r1"))
        self.write("projects/abs/domains/ops/rules/r2.md", rule("rule:abs/ops/r2"))
        self.stream(RULES, profile="checklist", scope=["rule:abs/ops/r1", "rule:abs/ops/r2"])
        self.write(RULES + "/stories/one/story.md", story("story:abs/ops/one", "[rule:abs/ops/r1, rule:abs/ops/r2]"))
        self.assertEqual(self.run_gate("two_way_coverage", RULES), [])
        self.write(RULES + "/stories/one/story.md", story("story:abs/ops/one", "[rule:abs/ops/r1]"))
        issues = self.run_gate("two_way_coverage", RULES)
        self.assertEqual([i.path for i in issues], [RULES + "/stream.json"])
        self.assertIn("rule:abs/ops/r2", issues[0].detail)


class UniqueKeysTest(PredicateTestCase):
    def setUp(self):
        super().setUp()
        self.stream(OPS)
        self.write("projects/abs/domains/operations/map/list.md", screen("screen:abs/operations/list"))
        self.write("projects/abs/domains/operations/map/card.md", screen("screen:abs/operations/card"))

    def test_matching_keys_pass(self):
        self.assertEqual(self.run_gate("unique_keys", OPS), [])

    def test_key_not_matching_path_fails_on_key_line(self):
        rel = "projects/abs/domains/operations/map/card.md"
        self.write(rel, screen("screen:abs/operations/other"))
        issues = self.run_gate("unique_keys", OPS)
        self.assertEqual([(i.path, i.line) for i in issues], [(rel, 2)])

    def test_missing_key_fails(self):
        rel = "projects/abs/domains/operations/map/card.md"
        self.write(rel, "---\nroute: /x\n---\n# Card\n")
        self.assertEqual([(i.path, i.line) for i in self.run_gate("unique_keys", OPS)], [(rel, 1)])

    def test_shared_key_fails(self):
        rel = "projects/abs/domains/operations/map/zlist.md"
        self.write(rel, screen("screen:abs/operations/list"))
        issues = self.run_gate("unique_keys", OPS)
        self.assertEqual({i.path for i in issues}, {rel})
        self.assertTrue(any("projects/abs/domains/operations/map/list.md" in i.detail for i in issues))

    def test_other_domain_not_checked(self):
        self.write("projects/abs/domains/risks/map/bad.md", screen("screen:abs/risks/other"))
        self.assertEqual(self.run_gate("unique_keys", OPS), [])

    def test_other_project_with_same_domain_not_checked(self):
        rel = "projects/web/domains/operations/map/bad.md"
        self.write(rel, screen("screen:web/operations/other"))
        self.assertEqual(self.run_gate("unique_keys", OPS), [])

    def test_checklist_profile(self):
        self.stream(RULES, profile="checklist")
        self.write("projects/abs/domains/ops/rules/r1.md", rule("rule:abs/ops/r1"))
        self.assertEqual(self.run_gate("unique_keys", RULES), [])
        self.write("projects/abs/domains/ops/rules/r1.md", rule("rule:abs/ops/r9"))
        self.assertEqual([(i.path, i.line) for i in self.run_gate("unique_keys", RULES)],
                         [("projects/abs/domains/ops/rules/r1.md", 2)])


class NoDanglingTargetsTest(PredicateTestCase):
    def test_dangling_transition_fails_on_row_line(self):
        self.stream(OPS)
        rel = "projects/abs/domains/operations/map/rejects.md"
        self.write(rel, screen("screen:abs/operations/rejects", ["screen:abs/clients/card"]))
        issues = self.run_gate("no_dangling_targets", OPS)
        self.assertEqual([(i.path, i.line) for i in issues], [(rel, self.line_of(rel, "| Go | screen:abs/clients/card"))])
        self.assertIn("screen:abs/clients/card", issues[0].detail)

    def test_cross_domain_transition_passes(self):
        self.stream(OPS)
        self.write("projects/abs/domains/operations/map/rejects.md",
                   screen("screen:abs/operations/rejects", ["screen:abs/clients/card"]))
        self.write("projects/abs/domains/clients/map/card.md", screen("screen:abs/clients/card"))
        self.assertEqual(self.run_gate("no_dangling_targets", OPS), [])

    def test_checklist_profile(self):
        self.stream(RULES, profile="checklist")
        rel = "projects/abs/domains/ops/rules/r1.md"
        self.write("projects/abs/domains/ops/rules/r2.md", rule("rule:abs/ops/r2"))
        self.write(rel, rule("rule:abs/ops/r1", ["rule:abs/ops/r2"]))
        self.assertEqual(self.run_gate("no_dangling_targets", RULES), [])
        self.write(rel, rule("rule:abs/ops/r1", ["rule:abs/ops/r2", "rule:abs/ops/missing"]))
        issues = self.run_gate("no_dangling_targets", RULES)
        self.assertEqual([(i.path, i.line) for i in issues], [(rel, self.line_of(rel, "| Check | rule:abs/ops/missing"))])


LEGACY = "# Operations\n\n## Legacy trace\n\n| Legacy group | Legacy item | Legacy route | Target |\n|---|---|---|---|\n"


class LegacyTracedTest(PredicateTestCase):
    MAP = "projects/abs/domains/operations/MAP.md"
    PARAMS = {"table": "Legacy trace"}

    def setUp(self):
        super().setUp()
        self.stream(OPS, scope=["screen:abs/operations/list"])
        self.write("projects/abs/domains/operations/map/list.md", screen("screen:abs/operations/list"))

    def gate(self):
        return self.run_gate("legacy_traced", OPS, self.PARAMS)

    def test_existing_screen_and_dropped_row_pass(self):
        self.write(self.MAP, LEGACY + "| Ops | List | /ops | screen:abs/operations/list |\n"
                   "| Ops | Clerk | /clerk | dropped: runs through clerk, owner decision 2026-09-03 |\n")
        self.assertEqual(self.gate(), [])

    def test_missing_screen_fails_on_row_line(self):
        self.write(self.MAP, LEGACY + "| Ops | List | /ops | screen:abs/operations/list |\n"
                   "| Ops | Gone | /gone | screen:abs/operations/gone |\n")
        issues = self.gate()
        self.assertEqual([(i.path, i.line) for i in issues], [(self.MAP, self.line_of(self.MAP, "| Ops | Gone"))])

    def test_dropped_without_reason_fails(self):
        self.write(self.MAP, LEGACY + "| Ops | Clerk | /clerk | dropped:   |\n")
        self.assertEqual([i.path for i in self.gate()], [self.MAP])

    def test_no_table_section_fails(self):
        self.write(self.MAP, "# Operations\n\n## Screens\n")
        self.assertEqual([(i.path, i.line) for i in self.gate()], [(self.MAP, 1)])

    def test_section_without_table_fails_on_heading(self):
        self.write(self.MAP, "# Operations\n\n## Legacy trace\n\nTo do.\n")
        self.assertEqual([(i.path, i.line) for i in self.gate()], [(self.MAP, 3)])

    def test_missing_map_doc_fails(self):
        self.assertEqual([i.path for i in self.gate()], [self.MAP])

    def test_broken_row_reported_even_when_other_rows_are_fine(self):
        self.write(self.MAP, LEGACY + "| Ops | List | /ops | screen:abs/operations/list |\n"
                   "| Ops | Bad | screen:abs/operations/list |\n")
        issues = self.gate()
        self.assertEqual([(i.path, i.line) for i in issues], [(self.MAP, self.line_of(self.MAP, "| Ops | Bad"))])

    def test_uses_map_doc_of_stream_domain(self):
        self.write("projects/abs/domains/clients/MAP.md", "# Clients\n")
        self.write(self.MAP, LEGACY + "| Ops | List | /ops | screen:abs/operations/list |\n")
        self.assertEqual(self.gate(), [])
        self.write("projects/abs/domains/clients/MAP.md",
                   LEGACY + "| Ops | List | /ops | screen:abs/operations/list |\n")
        self.write(self.MAP, "# Operations\n")
        self.assertEqual([i.path for i in self.gate()], [self.MAP])

    def test_map_doc_of_other_project_with_same_domain_is_not_used(self):
        self.write("projects/web/domains/operations/MAP.md",
                   LEGACY + "| Ops | List | /ops | screen:abs/operations/list |\n")
        self.assertEqual([i.path for i in self.gate()], [self.MAP])

    def test_checklist_profile(self):
        self.stream(RULES, profile="checklist")
        self.write("projects/abs/domains/ops/rules/r1.md", rule("rule:abs/ops/r1"))
        self.write("projects/abs/domains/ops/MAP.md", LEGACY + "| G | I | /r | rule:abs/ops/r1 |\n")
        self.assertEqual(self.run_gate("legacy_traced", RULES, self.PARAMS), [])
        self.write("projects/abs/domains/ops/MAP.md", LEGACY + "| G | I | /r | rule:abs/ops/r7 |\n")
        self.assertEqual([i.path for i in self.run_gate("legacy_traced", RULES, self.PARAMS)],
                         ["projects/abs/domains/ops/MAP.md"])


class ApprovalTest(PredicateTestCase):
    def test_mark_passes(self):
        self.stream(OPS, approvals=[{"stage": "goal", "by": "Ann", "date": "2026-09-01"}])
        self.assertEqual(self.run_gate("approval", OPS, {"stage": "goal"}), [])

    def test_bad_marks_fail_on_stream_line_1(self):
        cases = [
            [],
            [{"stage": "map", "by": "Ann", "date": "2026-09-01"}],
            [{"stage": "goal", "by": "", "date": "2026-09-01"}],
            [{"stage": "goal", "by": "Ann", "date": "2026-9-1"}],
            [{"stage": "goal", "by": "Ann", "date": "2026-02-30"}],
            [{"stage": "goal", "by": "Ann"}],
            ["goal"],
            "goal",
        ]
        for approvals in cases:
            self.stream(OPS, approvals=approvals)
            issues = self.run_gate("approval", OPS, {"stage": "goal"})
            self.assertEqual([(i.path, i.line) for i in issues], [(OPS + "/stream.json", 1)], approvals)

    def test_checklist_profile(self):
        self.stream(RULES, profile="checklist", approvals=[{"stage": "map", "by": "Bo", "date": "2026-09-02"}])
        self.assertEqual(self.run_gate("approval", RULES, {"stage": "map"}), [])
        self.assertEqual(len(self.run_gate("approval", RULES, {"stage": "decomposition"})), 1)


class TrackerIdsTest(PredicateTestCase):
    def setUp(self):
        super().setUp()
        self.stream(OPS)
        self.write(OPS + "/stories/a/story.md", story("story:abs/operations/a", tracker="TASK-7"))

    def test_matching_tracker_passes(self):
        self.assertEqual(self.run_gate("tracker_ids", OPS), [])

    def test_partial_or_empty_tracker_fails_on_tracker_line(self):
        rel_b, rel_c = OPS + "/stories/b/story.md", OPS + "/stories/c/story.md"
        self.write(rel_b, story("story:abs/operations/b", tracker="TASK-7x"))
        self.write(rel_c, story("story:abs/operations/c", tracker=""))
        issues = self.run_gate("tracker_ids", OPS)
        self.assertEqual(sorted((i.path, i.line) for i in issues),
                         [(rel_b, self.line_of(rel_b, "tracker:")), (rel_c, self.line_of(rel_c, "tracker:"))])

    def test_non_string_tracker_is_shown_as_repr(self):
        rel = OPS + "/stories/b/story.md"
        self.write(rel, story("story:abs/operations/b", tracker="[TASK-8]"))
        issues = self.run_gate("tracker_ids", OPS)
        self.assertEqual([(i.path, i.detail) for i in issues],
                         [(rel, "tracker ['TASK-8']: matches no id_pattern of tracker/trackers.json")])

    def test_tracker_of_second_pattern_passes(self):
        self.write("tracker/trackers.json", trackers(("tasks", r"TASK-\d+"), ("bugs", r"BUG-\d+")))
        self.write(OPS + "/stories/b/story.md", story("story:abs/operations/b", tracker="BUG-3"))
        self.assertEqual(self.run_gate("tracker_ids", OPS), [])

    def test_tracker_matching_several_patterns_fails(self):
        # TASK ids match both patterns and fail; BUG-3 matches exactly one and passes.
        self.write("tracker/trackers.json", trackers(("tasks", r"TASK-\d+"), ("any", r"\w+-\d+")))
        rel_b, rel_c = OPS + "/stories/b/story.md", OPS + "/stories/c/story.md"
        self.write(rel_b, story("story:abs/operations/b", tracker="TASK-8"))
        self.write(rel_c, story("story:abs/operations/c", tracker="BUG-3"))
        issues = self.run_gate("tracker_ids", OPS)
        self.assertEqual(sorted(i.path for i in issues),
                         [OPS + "/stories/a/story.md", rel_b])
        self.assertTrue(all("several" in i.detail for i in issues), issues)

    def test_unusable_trackers_report_each_story(self):
        self.write(OPS + "/stories/b/story.md", story("story:abs/operations/b", tracker="TASK-8"))
        self.write("tracker/trackers.json", json.dumps({"trackers": [
            {"key": "broken", "id_pattern": "(", "url": "u"}]}) + "\n")
        issues = self.run_gate("tracker_ids", OPS)
        self.assertEqual(sorted(i.path for i in issues), [OPS + "/stories/a/story.md", OPS + "/stories/b/story.md"])

    def test_checklist_profile(self):
        self.stream(RULES, profile="checklist")
        rel = RULES + "/stories/one/story.md"
        self.write(rel, story("story:abs/ops/one", tracker="TASK-1"))
        self.assertEqual(self.run_gate("tracker_ids", RULES), [])
        self.write(rel, story("story:abs/ops/one", tracker="BUG-1"))
        self.assertEqual([i.path for i in self.run_gate("tracker_ids", RULES)], [rel])


class NoOpenQuestionsTest(PredicateTestCase):
    PARAMS = {"section": "Open questions"}

    def setUp(self):
        super().setUp()
        self.stream(OPS)

    def test_none_or_empty_passes(self):
        self.write(OPS + "/stories/a/story.md", story("story:abs/operations/a"))
        self.write(OPS + "/stories/b/story.md", story("story:abs/operations/b", questions=""))
        self.assertEqual(self.run_gate("no_open_questions", OPS, self.PARAMS), [])

    def test_question_fails_on_heading_line(self):
        rel = OPS + "/stories/a/story.md"
        self.write(rel, story("story:abs/operations/a", questions="- Who signs the document?"))
        issues = self.run_gate("no_open_questions", OPS, self.PARAMS)
        self.assertEqual([(i.path, i.line) for i in issues], [(rel, self.line_of(rel, "## Open questions"))])

    def test_checklist_profile(self):
        self.stream(RULES, profile="checklist")
        rel = RULES + "/stories/one/story.md"
        self.write(rel, story("story:abs/ops/one"))
        self.assertEqual(self.run_gate("no_open_questions", RULES, self.PARAMS), [])
        self.write(rel, story("story:abs/ops/one", questions="None. But maybe later."))
        self.assertEqual([i.path for i in self.run_gate("no_open_questions", RULES, self.PARAMS)], [rel])


class WorkRecordsTest(PredicateTestCase):
    STORY = OPS + "/stories/documents/story.md"

    def setUp(self):
        super().setUp()
        self.stream(OPS, stage="done")
        self.write(self.STORY, story("story:abs/operations/documents", tracker="TASK-7", status="done"))

    def test_done_story_with_work_md_passes(self):
        self.write(OPS + "/stories/documents/work.md", "---\nrepos: []\n---\n# Work\n")
        self.assertEqual(self.run_gate("work_records", OPS), [])

    def test_waiting_story_fails_on_status_line(self):
        self.write(self.STORY, story("story:abs/operations/documents", tracker="TASK-7"))
        issues = self.run_gate("work_records", OPS)
        self.assertEqual([(i.path, i.line) for i in issues], [(self.STORY, self.line_of(self.STORY, "status:"))])
        self.assertIn("waiting", issues[0].detail)

    def test_done_story_without_work_md_fails(self):
        issues = self.run_gate("work_records", OPS)
        self.assertEqual([i.path for i in issues], [self.STORY])
        self.assertIn("work.md", issues[0].detail)

    def test_missing_status_fails(self):
        self.write(self.STORY, "---\nkey: story:abs/operations/documents\ntype: story\ntracker: TASK-7\n---\n"
                               "# Story\n\n## Goal\n\nDo it.\n\n## Open questions\n\nNone.\n")
        self.assertEqual([i.path for i in self.run_gate("work_records", OPS)], [self.STORY])

    def test_work_md_elsewhere_does_not_help(self):
        self.write("work/TASK-7/work.md", "---\nrepos: []\n---\n# Work\n")
        self.assertEqual([i.path for i in self.run_gate("work_records", OPS)], [self.STORY])

    def test_checklist_profile(self):
        self.stream(RULES, profile="checklist", stage="done")
        rel = RULES + "/stories/one/story.md"
        self.write(rel, story("story:abs/ops/one", tracker="TASK-7", status="done"))
        self.write(RULES + "/stories/one/work.md", "---\nrepos: []\n---\n# Work\n")
        self.assertEqual(self.run_gate("work_records", RULES), [])
        self.write(rel, story("story:abs/ops/one", tracker="TASK-8", status="waiting"))
        self.assertEqual([i.path for i in self.run_gate("work_records", RULES)], [rel])


UI_EPIC = "# Epic\n\n## Goal\n\n## Scope\n\n## Success criteria\n\n## Out of scope\n\n## Open questions\n\n" \
          "## Target users\n\n## Product\n"


class EpicSectionsTest(PredicateTestCase):
    EPIC = OPS + "/epic.md"

    def setUp(self):
        super().setUp()
        self.stream(OPS, stage="goal")

    def test_all_sections_pass(self):
        self.write(self.EPIC, UI_EPIC)
        self.assertEqual(self.run_gate("epic_sections", OPS), [])

    def test_missing_section_fails(self):
        self.write(self.EPIC, UI_EPIC.replace("## Product\n", "```\n## Product\n```\n"))
        issues = self.run_gate("epic_sections", OPS)
        self.assertEqual([(i.path, i.line) for i in issues], [(self.EPIC, 1)])
        self.assertIn("Product", issues[0].detail)

    def test_missing_epic_fails(self):
        self.assertEqual([i.path for i in self.run_gate("epic_sections", OPS)], [self.EPIC])

    def test_checklist_profile(self):
        self.stream(RULES, profile="checklist")
        self.write(RULES + "/epic.md", "# Epic\n\n## Goal\n")
        self.assertEqual(self.run_gate("epic_sections", RULES), [])
        self.write(RULES + "/epic.md", "# Epic\n\n## Scope\n")
        self.assertEqual([i.path for i in self.run_gate("epic_sections", RULES)], [RULES + "/epic.md"])


class StreamWithoutDataTest(PredicateTestCase):
    def test_stream_without_data_is_skipped(self):
        self.write(OPS + "/stream.json", "[]\n")
        for name in PREDICATES:
            self.assertEqual(self.run_gate(name, OPS, {"stage": "goal"}), [], name)


BAD_PROFILE = {
    "elements": [
        {"kind": "screen", "prefix": "map", "tables": [{"heading": ["Transitions"], "keys": [["Target"], 3]}, "x"]},
        {"kind": ["rule"], "tables": [{"heading": {"a": 1}}]},
    ],
    "epic": {"sections": [["Goal"], {"a": 1}]},
    "map_doc": {"tables": [{"heading": ["Legacy trace"], "target": ["Target"]}, {"heading": "Legacy trace", "target": 3}]},
}


class UnexpectedTypesTest(PredicateTestCase):
    def test_predicates_never_raise(self):
        self.stream(OPS, scope=3, approvals={"stage": "goal"})
        self.write(OPS + "/stories/a/story.md", "no frontmatter\n")
        self.write(OPS + "/stories/b/story.md", "---\nkey: story:abs/operations/b\nscope: [\n---\n")
        self.write(OPS + "/stories/c/story.md",
                   "---\ntracker: [a]\nstatus: {a: b}\nscope: [screen:abs/operations/x]\nunmapped: {a: b}\n---\n")
        self.write(OPS + "/stories/a/work.md", "---\nrepos: [\n---\n")
        self.write(OPS + "/epic.md", "# Epic\n")
        self.write("projects/abs/domains/operations/MAP.md", LEGACY + "| a | b |\n")
        self.write("projects/abs/domains/operations/map/x.md", "---\nkey: [a, b]\n---\n## Transitions\n\n| Action |\n|---|\n| x |\n")
        self.write("projects/abs/domains/operations/map/y.md", "no frontmatter\n")
        ws = Workspace(Context(self.root))
        stream = next(s for s in ws.streams if s.data is not None)
        for name, predicate in PREDICATES.items():
            for profile in (None, {}, {"elements": "x", "epic": [], "map_doc": 3}, BAD_PROFILE,
                            ws.profiles["ui-migration"]):
                for params in (None, {}, {"stage": 3, "table": [], "section": None},
                               {"stage": (1, 2), "table": {"a": 1}, "section": ["Open questions"]}):
                    result = predicate(ws, stream, profile, params)
                    self.assertIsInstance(result, list, name)
                    self.assertTrue(all(isinstance(i, Issue) for i in result), name)


if __name__ == "__main__":
    unittest.main()
