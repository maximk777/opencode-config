import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import unittest

from wslib import tables


SCREEN = """# Screen

Intro text.

## Transitions

Some prose.

| Action | Target |
|---|---|
| Open | screen:bank/detail |
| Back | screen:bank/list |

Trailing prose.

## Notes

Nothing here.
"""


class SectionText(unittest.TestCase):
    def test_returns_heading_line_and_text_up_to_next_h2(self):
        line, text = tables.section_text(SCREEN, "Transitions")
        self.assertEqual(line, 5)
        self.assertIn("| Open | screen:bank/detail |", text)
        self.assertIn("Trailing prose.", text)
        self.assertNotIn("## Notes", text)
        self.assertNotIn("Nothing here.", text)

    def test_last_section_runs_to_end(self):
        line, text = tables.section_text(SCREEN, "Notes")
        self.assertEqual(line, 16)
        self.assertIn("Nothing here.", text)

    def test_absent_section_is_none(self):
        self.assertIsNone(tables.section_text(SCREEN, "Missing"))

    def test_h3_does_not_end_section(self):
        body = "## A\n### Sub\nkeep\n## B\n"
        line, text = tables.section_text(body, "A")
        self.assertEqual(line, 1)
        self.assertIn("### Sub", text)
        self.assertIn("keep", text)

    def test_heading_inside_fence_ignored(self):
        body = "## A\n```\n## B\n```\nstill a\n## C\n"
        self.assertIsNone(tables.section_text(body, "B"))
        line, text = tables.section_text(body, "A")
        self.assertIn("still a", text)
        self.assertIn("## B", text)

    def test_heading_line_counts_file_lines(self):
        body = "---\nkey: x\n---\n\n## Goal\ntext\n"
        line, _ = tables.section_text(body, "Goal")
        self.assertEqual(line, 5)


class ParseTable(unittest.TestCase):
    def test_section_with_table(self):
        columns, rows, error = tables.parse_table(SCREEN, "Transitions")
        self.assertIsNone(error)
        self.assertEqual(columns, ["Action", "Target"])
        self.assertEqual(rows, [
            (11, ["Open", "screen:bank/detail"]),
            (12, ["Back", "screen:bank/list"]),
        ])

    def test_start_line_offsets_row_lines(self):
        _, rows, _ = tables.parse_table(SCREEN, "Transitions", start_line=4)
        self.assertEqual([r[0] for r in rows], [14, 15])

    def test_section_without_table(self):
        columns, rows, error = tables.parse_table(SCREEN, "Notes")
        self.assertEqual(error, "no table")
        self.assertIsNone(columns)
        self.assertEqual(rows, [])

    def test_absent_section(self):
        columns, rows, error = tables.parse_table(SCREEN, "Missing")
        self.assertIsNone(columns)
        self.assertEqual(rows, [])
        self.assertIsNone(error)

    def test_table_in_other_section_not_taken(self):
        body = "## A\ntext\n## B\n| X | Y |\n|---|---|\n| 1 | 2 |\n"
        columns, rows, error = tables.parse_table(body, "A")
        self.assertEqual(error, "no table")

    def test_row_with_wrong_cell_count_names_line(self):
        body = "## T\n| A | B |\n|---|---|\n| 1 | 2 |\n| 3 |\n| 4 | 5 |\n"
        columns, rows, error = tables.parse_table(body, "T")
        self.assertEqual(columns, ["A", "B"])
        self.assertEqual(error, "row at line 5 has 1 cells, expected 2")
        self.assertIn((4, ["1", "2"]), rows)

    def test_row_error_line_uses_start_line(self):
        body = "## T\n| A | B |\n|---|---|\n| 1 | 2 | 3 |\n"
        _, _, error = tables.parse_table(body, "T", start_line=10)
        self.assertEqual(error, "row at line 13 has 3 cells, expected 2")

    def test_separator_with_alignment(self):
        body = "## T\n| A | B | C |\n|:---:|---:|:--|\n| 1 | 2 | 3 |\n"
        columns, rows, error = tables.parse_table(body, "T")
        self.assertIsNone(error)
        self.assertEqual(columns, ["A", "B", "C"])
        self.assertEqual(rows, [(4, ["1", "2", "3"])])

    def test_missing_separator_is_error(self):
        body = "## T\n| A | B |\n| 1 | 2 |\n"
        columns, rows, error = tables.parse_table(body, "T")
        self.assertIsNotNone(error)
        self.assertIn("2", error)
        self.assertEqual(rows, [])

    def test_separator_cell_count_differs_from_header(self):
        body = "## T\n| A | B |\n|---|\n| 1 | 2 |\n"
        columns, rows, error = tables.parse_table(body, "T")
        self.assertEqual(columns, ["A", "B"])
        self.assertEqual(error, "table at line 2 has no separator line")
        self.assertEqual(rows, [])

    def test_separator_cell_without_dash(self):
        body = "## T\n| A | B |\n|:|---|\n| 1 | 2 |\n"
        _, rows, error = tables.parse_table(body, "T")
        self.assertEqual(error, "table at line 2 has no separator line")
        self.assertEqual(rows, [])

    def test_other_fence_char_inside_fence_does_not_close_it(self):
        body = "## T\n```\n~~~\n| X |\n```\n| A |\n|---|\n| 1 |\n"
        columns, rows, error = tables.parse_table(body, "T")
        self.assertIsNone(error)
        self.assertEqual(columns, ["A"])
        self.assertEqual(rows, [(8, ["1"])])

    def test_header_only_table_at_end_of_text(self):
        columns, rows, error = tables.parse_table("## T\n| A | B |", "T")
        self.assertIsNotNone(error)
        self.assertEqual(rows, [])

    def test_cells_stripped_and_empty_cells_kept(self):
        body = "## T\n|  A  |B|  C |\n|---|---|---|\n|   x |  | z   |\n"
        columns, rows, error = tables.parse_table(body, "T")
        self.assertIsNone(error)
        self.assertEqual(columns, ["A", "B", "C"])
        self.assertEqual(rows, [(4, ["x", "", "z"])])

    def test_table_ends_at_first_non_pipe_line(self):
        body = "## T\n| A |\n|---|\n| 1 |\n\n| 2 |\n"
        _, rows, error = tables.parse_table(body, "T")
        self.assertIsNone(error)
        self.assertEqual(rows, [(4, ["1"])])

    def test_heading_inside_fence_ignored(self):
        body = "```\n## T\n| A |\n|---|\n| 1 |\n```\n"
        self.assertEqual(tables.parse_table(body, "T"), (None, [], None))

    def test_never_raises_on_odd_input(self):
        samples = ["", "\n", "## T", "## T\n|", "## T\n||\n||\n|||\n", "## T\n|\r\n|-|\r\n",
                   "```\n## T\n", "## T\n| a | b\n|---\n| 1 | 2\n", "\x00## T\n"]
        for s in samples:
            tables.parse_table(s, "T")
            tables.section_text(s, "T")
            tables.sections(s)


class Sections(unittest.TestCase):
    def test_every_h2_with_line_and_text(self):
        result = tables.sections(SCREEN)
        self.assertEqual([(line, heading) for line, heading, _ in result],
                         [(5, "Transitions"), (16, "Notes")])
        self.assertIn("Some prose.", result[0][2])
        self.assertIn("Nothing here.", result[1][2])

    def test_fenced_headings_skipped(self):
        body = "## A\n~~~\n## Fake\n~~~\n## B\n"
        self.assertEqual([h for _, h, _ in tables.sections(body)], ["A", "B"])

    def test_tilde_inside_backtick_fence_does_not_close_it(self):
        body = "## A\n```\n~~~\n## Fake\n```\n## B"
        self.assertEqual([h for _, h, _ in tables.sections(body)], ["A", "B"])
        self.assertIsNone(tables.section_text(body, "Fake"))
        self.assertEqual(tables.section_text(body, "B"), (6, ""))

    def test_shorter_fence_does_not_close_longer(self):
        body = "## A\n````\n```\n## Fake\n````\n## B\n"
        self.assertEqual([h for _, h, _ in tables.sections(body)], ["A", "B"])

    def test_fence_with_trailing_text_does_not_close(self):
        body = "## A\n```\n``` x\n## Fake\n```  \n## B\n"
        self.assertEqual([h for _, h, _ in tables.sections(body)], ["A", "B"])

    def test_no_sections(self):
        self.assertEqual(tables.sections("# Title\ntext\n"), [])


if __name__ == "__main__":
    unittest.main()
