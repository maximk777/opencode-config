import importlib.machinery
import sys
import unittest
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "lib"))

from ovsync import scope


class TranslateTests(unittest.TestCase):
    def test_double_star_matches_any_depth(self):
        rx = scope.translate("architecture/**")
        self.assertIsNotNone(rx.fullmatch("architecture/a.md"))
        self.assertIsNotNone(rx.fullmatch("architecture/adr/b.md"))
        self.assertIsNone(rx.fullmatch("architecture.md"))

    def test_double_star_in_middle_matches_zero_or_more_segments(self):
        rx = scope.translate("a/**/b.md")
        self.assertIsNotNone(rx.fullmatch("a/b.md"))
        self.assertIsNotNone(rx.fullmatch("a/x/y/b.md"))

    def test_single_star_matches_within_segment(self):
        rx = scope.translate("a/*.md")
        self.assertIsNotNone(rx.fullmatch("a/x.md"))
        self.assertIsNone(rx.fullmatch("a/x/y.md"))

    def test_question_mark_matches_one_char(self):
        rx = scope.translate("a/?.md")
        self.assertIsNotNone(rx.fullmatch("a/x.md"))
        self.assertIsNone(rx.fullmatch("a/xy.md"))

    def test_trailing_slash_matches_everything_under(self):
        rx = scope.translate("docs/")
        self.assertIsNotNone(rx.fullmatch("docs/a/b.md"))

    def test_literal_dot_is_not_a_wildcard(self):
        rx = scope.translate("a.b/c")
        self.assertIsNotNone(rx.fullmatch("a.b/c"))
        self.assertIsNone(rx.fullmatch("aXb/c"))


class ParseTests(unittest.TestCase):
    def test_skips_blank_lines_and_comments(self):
        rules = scope.parse("\n# comment\narchitecture/**\n\n")
        self.assertEqual(len(rules), 1)

    def test_marks_bang_lines_as_excludes(self):
        rules = scope.parse("architecture/**\n!architecture/poc/*/**\n")
        self.assertEqual(rules[0][0], True)
        self.assertEqual(rules[1][0], False)
        # the pattern itself must be translated (stripped of "!"), not compiled with it
        self.assertIsNotNone(rules[1][1].fullmatch("architecture/poc/x/data.json"))


class SelectedTests(unittest.TestCase):
    def test_last_matching_line_wins(self):
        rules = scope.parse("a/**\n!a/x/**\na/x/keep.md\n")
        self.assertTrue(scope.selected("a/y.md", rules))
        self.assertTrue(scope.selected("a/x/keep.md", rules))
        self.assertFalse(scope.selected("a/x/drop.md", rules))

    def test_unmatched_path_is_excluded(self):
        rules = scope.parse("a/**\n")
        self.assertFalse(scope.selected("b/y.md", rules))


class RealScopeFileTests(unittest.TestCase):
    def setUp(self):
        self.rules = scope.parse((REPO / "openviking/sync-scope").read_text())

    def test_change_artifacts_scenario(self):
        paths = [
            "openspec/changes/ov-sync-queue/proposal.md",
            "openspec/changes/ov-sync-queue/design.md",
            "openspec/changes/ov-sync-queue/decisions.md",
            "openspec/changes/ov-sync-queue/tasks.md",
            "openspec/changes/ov-sync-queue/briefs/1.1.md",
            "openspec/changes/ov-sync-queue/reports/1.1.md",
        ]
        self.assertEqual(
            scope.select(paths, self.rules),
            sorted([
                "openspec/changes/ov-sync-queue/proposal.md",
                "openspec/changes/ov-sync-queue/design.md",
                "openspec/changes/ov-sync-queue/decisions.md",
            ]),
        )

    def test_poc_folder_scenario(self):
        paths = [
            "architecture/poc/ov-incremental-sync/README.md",
            "architecture/poc/ov-incremental-sync/RESULT.md",
            "architecture/poc/ov-incremental-sync/poc.py",
            "architecture/poc/ov-incremental-sync/raw.jsonl",
            "architecture/poc/ov-incremental-sync/data/notes/a.md",
        ]
        self.assertEqual(
            scope.select(paths, self.rules),
            sorted([
                "architecture/poc/ov-incremental-sync/README.md",
                "architecture/poc/ov-incremental-sync/RESULT.md",
            ]),
        )

    def test_architecture_documents_scenario(self):
        paths = [
            "architecture/adr/005-memory-as-derived-index.md",
            "architecture/backlog/ov-sync-queue.md",
        ]
        self.assertEqual(scope.select(paths, self.rules), sorted(paths))

    def test_unknown_directory_stays_out(self):
        self.assertFalse(scope.selected("mockups/screen.html", self.rules))

    def test_archived_change_design_is_selected(self):
        self.assertTrue(
            scope.selected(
                "openspec/changes/archive/2026-09-13-x/design.md", self.rules
            )
        )

    def test_diagram_markdown_selected_other_extensions_not(self):
        self.assertTrue(scope.selected("architecture/diagrams/c4.md", self.rules))
        self.assertFalse(scope.selected("architecture/diagrams/c4.puml", self.rules))

    def test_select_returns_sorted_list(self):
        paths = [
            "architecture/b.md",
            "architecture/a.md",
        ]
        self.assertEqual(scope.select(paths, self.rules), ["architecture/a.md", "architecture/b.md"])


if __name__ == "__main__":
    unittest.main()
