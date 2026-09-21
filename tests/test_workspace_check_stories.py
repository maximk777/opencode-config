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

PROFILE_DIR = REPO / "kits/workspace/.agents/profiles/ui-migration"
STREAM = "projects/abs/domains/operations/streams/s"
BODY = (
    "\n## Goal\n\nx\n\n## Scope\n\nx\n\n## Acceptance criteria\n\nx\n\n## Verification\n\nx\n"
    "\n## Out of scope\n\nx\n\n## Open questions\n\nNone.\n"
)
DEFAULT_FIELDS = [
    ("key", "story:abs/operations/documents"),
    ("type", "story"),
    ("wave", "1"),
    ("tracker", ""),
    ("scope", "[screen:abs/operations/documents]"),
    ("depends", "[]"),
    ("repos", "[]"),
    ("decisions", "[]"),
    ("mockups", "[]"),
]


def story(overrides=None, drop=(), extra="", body=BODY):
    overrides = overrides or {}
    lines = []
    for name, value in DEFAULT_FIELDS:
        if name in drop:
            continue
        value = overrides.get(name, value)
        lines.append("%s: %s" % (name, value) if value != "" else "%s:" % name)
    return "---\n%s\n%s---\n%s" % ("\n".join(lines), extra, body)


def screen(slug):
    return (
        "---\nkey: screen:abs/operations/%s\nroute: /%s\nkind: place\nsection: s\nparent:\naccess: a\n"
        "label: L\nwave: 1\nstory:\n---\n\n## Transitions\n\n| Action | Target |\n|---|---|\n" % (slug, slug)
    )


class CheckStoriesTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.ws = create_workspace(self.tmp)
        profile = self.ws / ".agents/profiles/ui-migration"
        if not (profile / "profile.json").is_file():
            shutil.copytree(str(PROFILE_DIR), str(profile), dirs_exist_ok=True)
        self.write("projects/abs/domains/operations/map/documents.md", screen("documents"))
        self.write("projects/abs/domains/operations/map/report.md", screen("report"))
        self.write_stream("s", "ui-migration")

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text):
        path = self.ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def write_stream(self, name, profile):
        self.write(
            "projects/abs/domains/operations/streams/%s/stream.json" % name,
            json.dumps({
                "key": "stream:abs/operations/%s" % name, "profile": profile, "stage": "goal",
                "scope": ["screen:abs/operations/documents"], "approvals": []}, indent=2) + "\n",
        )

    def write_story(self, text, slug="documents", stream="s"):
        rel = "projects/abs/domains/operations/streams/%s/stories/%s/story.md" % (stream, slug)
        self.write(rel, text)
        return rel

    def findings(self):
        code, lines, stderr = run_check(self.ws)
        self.assertNotIn("Traceback", stderr)
        self.assertNotEqual(code, 2, stderr)
        return [line for line in lines if len(line.split(" ")) > 1 and line.split(" ")[1] == "story"]

    def assertOneOn(self, rel, fragment):
        lines = self.findings()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(rel + ":"), lines)
        self.assertIn(fragment, lines[0])

    def test_valid_story(self):
        self.write_story(story())
        self.assertEqual(self.findings(), [])

    def test_story_in_wrong_folder(self):
        rel = self.write_story(story({"key": "story:abs/operations/document"}))
        self.assertOneOn(rel, "story:abs/operations/document")

    def test_missing_field(self):
        rel = self.write_story(story(drop=("wave",)))
        self.assertOneOn(rel, "wave")

    def test_empty_field_not_allowed_empty(self):
        rel = self.write_story(story({"wave": ""}))
        self.assertOneOn(rel, "wave")

    def test_missing_section(self):
        rel = self.write_story(story(body=BODY.replace("## Verification", "## Checks")))
        self.assertOneOn(rel, "Verification")

    def test_section_inside_fence_does_not_count(self):
        body = BODY.replace("## Verification\n\nx\n", "```\n## Verification\n```\n")
        rel = self.write_story(story(body=body))
        self.assertOneOn(rel, "Verification")

    def test_wrong_type(self):
        rel = self.write_story(story({"type": "task"}))
        self.assertOneOn(rel, "task")

    def test_frontmatter_error(self):
        rel = self.write_story("---\nkey: story:abs/operations/documents\n\ntype: story\n---\n" + BODY)
        lines = self.findings()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(rel + ":"), lines)
        self.assertIn("frontmatter", lines[0])

    def test_missing_frontmatter(self):
        rel = self.write_story(BODY)
        self.assertOneOn(rel, "frontmatter")

    def test_stories_of_folder_without_stream_json_not_checked(self):
        self.write_story(story({"key": "story:abs/operations/wrong"}, drop=("wave",)), stream="bare")
        self.assertEqual(self.findings(), [])

    def test_scope_key_missing_from_map(self):
        rel = self.write_story(story({"scope": "[screen:abs/operations/documents, screen:abs/operations/ghost]"}))
        self.assertOneOn(rel, "screen:abs/operations/ghost")

    def test_unresolved_depends(self):
        rel = self.write_story(story({"depends": "[story:abs/operations/ghost]"}))
        self.assertOneOn(rel, "story:abs/operations/ghost")

    def test_resolved_depends(self):
        self.write_story(story({"key": "story:abs/operations/report", "scope": "[screen:abs/operations/report]"}), "report")
        self.write_story(story({"depends": "[story:abs/operations/report]"}))
        self.assertEqual(self.findings(), [])

    def test_unresolved_repos(self):
        rel = self.write_story(story({"repos": "[ghost]"}))
        self.assertOneOn(rel, "ghost")

    def test_planned_repo_resolves(self):
        self.write("repos.json", json.dumps({"repositories": [{"name": "front", "planned": True}]}, indent=2) + "\n")
        self.write_story(story({"repos": "[front]"}))
        self.assertEqual(self.findings(), [])

    def test_unresolved_decisions(self):
        rel = self.write_story(story({"decisions": "[adr:0042]"}))
        self.assertOneOn(rel, "adr:0042")

    def test_resolved_decisions(self):
        self.write("docs/adr/0001-choice.md", "---\nkey: adr:0001\n---\n")
        self.write_story(story({"decisions": "[adr:0001]"}))
        self.assertEqual(self.findings(), [])

    def test_unresolved_mockups(self):
        rel = self.write_story(story({"mockups": "[mockup:abs/operations/documents]"}))
        self.assertOneOn(rel, "mockup:abs/operations/documents")

    def test_resolved_mockups(self):
        self.write(
            "docs/diagrams/external.json",
            json.dumps({"diagrams": [{"key": "mockup:abs/operations/documents", "url": "https://x.test/m"}]}) + "\n",
        )
        self.write_story(story({"mockups": "[mockup:abs/operations/documents]"}))
        self.assertEqual(self.findings(), [])

    def test_empty_scope_with_unmapped_is_not_a_story_finding(self):
        self.write_story(story({"scope": "[]"}, extra="unmapped: bff defects\n"))
        self.assertEqual(self.findings(), [])

    def test_stream_with_unknown_profile_not_checked(self):
        self.write_stream("other", "ghost-profile")
        self.write_story(story({"key": "story:abs/operations/wrong", "type": "task"}, drop=("wave",)), stream="other")
        self.assertEqual(self.findings(), [])


if __name__ == "__main__":
    unittest.main()
