import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
import tempfile
import unittest

from workspace_helpers import create_workspace, run_check, run_generate

RULE = "generated-stale"


def stale_lines(lines):
    """Keep only generated-stale findings; other rule modules may add their own lines."""
    return [line for line in lines if len(line.split(" ")) > 1 and line.split(" ")[1] == RULE]


class CheckGeneratedTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.ws = create_workspace(self.tmp)

    def tearDown(self):
        self._tmp.cleanup()

    def findings(self):
        _, lines, stderr = run_check(self.ws)
        self.assertNotIn("Traceback", stderr)
        return stale_lines(lines)

    def assert_fixed_by_generate(self):
        result = run_generate(self.ws)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.findings(), [])

    def test_fresh_workspace_has_none(self):
        self.assertEqual(self.findings(), [])

    def test_appended_repository_makes_table_stale(self):
        manifest = self.ws / "repos.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["repositories"].append({
            "name": "billing", "remote": "git@example.com:billing.git", "forge": "gitlab",
            "default_branch": "main", "roles": ["backend"], "summary": "Billing service",
        })
        manifest.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        table_lines = (self.ws / "REPOSITORIES.md").read_text(encoding="utf-8").split("\n")
        # The new row takes the place of the end marker, so that is the first differing line.
        expected_line = table_lines.index("<!-- repos:end -->") + 1

        lines = self.findings()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("REPOSITORIES.md:%d generated-stale " % expected_line), lines)
        self.assertIn("differs from generator output; run python3 tools/generate.py", lines[0])
        self.assert_fixed_by_generate()

    def test_changed_claude_md(self):
        (self.ws / "CLAUDE.md").write_text("hand edit\n", encoding="utf-8")
        lines = self.findings()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("CLAUDE.md:1 generated-stale "), lines)
        self.assert_fixed_by_generate()

    def test_deleted_index(self):
        (self.ws / ".agents/index.json").unlink()
        lines = self.findings()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(".agents/index.json:1 generated-stale "), lines)
        self.assertIn("missing; run python3 tools/generate.py", lines[0])
        self.assert_fixed_by_generate()

    def test_extra_file_in_owned_dir(self):
        ghost = self.ws / ".claude/agents/ghost.md"
        ghost.parent.mkdir(parents=True, exist_ok=True)
        ghost.write_text("# ghost\n", encoding="utf-8")
        lines = self.findings()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(".claude/agents/ghost.md:1 generated-stale "), lines)
        self.assertIn("not produced by the generator; run python3 tools/generate.py", lines[0])
        self.assert_fixed_by_generate()

    def test_ignored_junk_in_owned_dirs(self):
        exclude = self.ws / ".git/info/exclude"
        exclude.parent.mkdir(parents=True, exist_ok=True)
        with exclude.open("a", encoding="utf-8") as fh:
            fh.write("\n.DS_Store\n")
        (self.ws / ".claude/agents").mkdir(parents=True, exist_ok=True)
        (self.ws / ".claude/agents/.DS_Store").write_bytes(b"\0junk")
        skill = sorted(p for p in (self.ws / ".claude/skills").iterdir() if p.is_dir())[0]
        # __pycache__/ is ignored by the workspace .gitignore.
        (skill / "__pycache__").mkdir()
        (skill / "__pycache__/x.pyc").write_bytes(b"\0pyc")
        self.assertEqual(self.findings(), [])
        ghost = self.ws / ".claude/agents/ghost.md"
        ghost.write_text("# ghost\n", encoding="utf-8")
        lines = self.findings()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(".claude/agents/ghost.md:1 generated-stale "), lines)

    def test_rendered_path_replaced_by_directory(self):
        claude = self.ws / "CLAUDE.md"
        claude.unlink()
        claude.mkdir()
        lines = self.findings()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("CLAUDE.md:1 generated-stale "), lines)
        self.assertIn("unreadable; run python3 tools/generate.py", lines[0])


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

MAP_MD = "domains/operations/MAP.md"
BREAKDOWN_MD = "domains/operations/streams/main/BREAKDOWN.md"


def screen(slug, route, wave):
    return (
        "---\nkey: screen:operations/%s\nroute: %s\nkind: place\nsection: Operations\nparent:\n"
        "access: op\nlabel: %s\nwave: %d\nstory:\n---\n# %s\n\n## Transitions\n\n"
        "| Action | Target |\n|---|---|\n| Back | screen:operations/list |\n"
    ) % (slug, route, slug, wave, slug)


def story(slug, wave):
    return (
        "---\nkey: story:operations/%s\ntype: story\nwave: %d\ntracker:\nscope: [screen:operations/list]\n"
        "depends: []\nrepos: []\ndecisions: []\nmockups: []\n---\n# %s\n\n## Goal\n\n%s.\n"
    ) % (slug, wave, slug, slug)


class CheckGeneratedMapsTest(unittest.TestCase):
    def setUp(self):
        CheckGeneratedTest.setUp(self)
        self.write(".agents/profiles/ui-migration/profile.json", json.dumps(UI_MIGRATION, indent=2) + "\n")
        template = (self.ws / ".agents/templates/MAP.md").read_text(encoding="utf-8")
        self.write(MAP_MD, template.replace("<domain>", "operations"))
        self.write("domains/operations/map/list.md", screen("list", "/operations", 1))
        stream = {
            "key": "stream:operations/main", "profile": "ui-migration", "stage": "goal",
            "scope": [], "approvals": [],
        }
        self.write("domains/operations/streams/main/stream.json", json.dumps(stream, indent=2) + "\n")
        self.write("domains/operations/streams/main/stories/documents/story.md", story("documents", 1))
        result = run_generate(self.ws)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.findings(), [])

    tearDown = CheckGeneratedTest.tearDown
    findings = CheckGeneratedTest.findings
    assert_fixed_by_generate = CheckGeneratedTest.assert_fixed_by_generate

    def write(self, rel, text):
        path = self.ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_added_screen_makes_map_stale(self):
        map_lines = (self.ws / MAP_MD).read_text(encoding="utf-8").split("\n")
        # card sorts before list, so its row takes the line of the list row.
        list_row = next(
            (i for i, line in enumerate(map_lines) if line.startswith("| screen:operations/list | /")), None)
        self.assertIsNotNone(list_row, map_lines)
        expected_line = list_row + 1
        self.write("domains/operations/map/card.md", screen("card", "/operations/:id", 1))
        lines = self.findings()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("%s:%d generated-stale " % (MAP_MD, expected_line)), lines)
        self.assertIn("differs from generator output; run python3 tools/generate.py", lines[0])
        self.assert_fixed_by_generate()

    def test_added_story_makes_breakdown_stale(self):
        # The new row replaces the empty string after the final newline, so it is the line past the last row.
        expected_line = len((self.ws / BREAKDOWN_MD).read_text(encoding="utf-8").split("\n"))
        self.write("domains/operations/streams/main/stories/reports/story.md", story("reports", 2))
        lines = self.findings()
        # A new story key is also an alias, so the index goes stale together with the breakdown.
        self.assertEqual(len(lines), 2, lines)
        self.assertTrue(lines[0].startswith(".agents/index.json:"), lines)
        self.assertTrue(lines[1].startswith("%s:%d generated-stale " % (BREAKDOWN_MD, expected_line)), lines)
        self.assert_fixed_by_generate()

    def test_generate_clears_stale_map_and_breakdown(self):
        self.write("domains/operations/map/card.md", screen("card", "/operations/:id", 1))
        self.write("domains/operations/streams/main/stories/reports/story.md", story("reports", 2))
        paths = sorted(line.split(":", 1)[0] for line in self.findings())
        self.assertEqual(paths, [".agents/index.json", MAP_MD, BREAKDOWN_MD])
        self.assert_fixed_by_generate()


class FirstDiffLineTest(unittest.TestCase):
    def test_lines(self):
        from wslib.rules_generated import first_diff_line
        self.assertEqual(first_diff_line(b"a\nb\n", b"a\nc\n"), 2)
        self.assertEqual(first_diff_line(b"a\nb\n", b"a\nb\nc\n"), 3)
        self.assertEqual(first_diff_line(b"", b"a\n"), 1)


if __name__ == "__main__":
    unittest.main()
