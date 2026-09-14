import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
import shutil
import subprocess
import tempfile
import unittest

from workspace_helpers import create_workspace, run_check, run_generate

CHECKLIST_PROFILE = REPO / "tests/fixtures/profiles/checklist/profile.json"
STREAM = "domains/demo/streams/migration"
STREAM_JSON = STREAM + "/stream.json"
STREAM_KEY = "stream:demo/migration"
LIST_SCREEN = "domains/demo/map/list.md"
CARD_SCREEN = "domains/demo/map/card.md"
TRACKERS = {"list": "TASK-1", "card": "TASK-2", "bff-cleanup": "TASK-3"}


class LifecycleTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = create_workspace(Path(self._tmp.name).resolve())

    def tearDown(self):
        self._tmp.cleanup()

    # --- files a skill would write ---

    def read(self, rel):
        return (self.ws / rel).read_text(encoding="utf-8")

    def write(self, rel, text):
        path = self.ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def template(self, rel, subs):
        text = self.read(rel)
        for placeholder, value in subs.items():
            text = text.replace("<%s>" % placeholder, value)
        return text

    def update_stream(self, stage=None, approve=None, scope=None, rel=STREAM_JSON):
        data = json.loads(self.read(rel))
        if stage is not None:
            data["stage"] = stage
        if approve is not None:
            data["approvals"].append({"stage": approve, "by": "owner", "date": "2026-09-01"})
        if scope is not None:
            data["scope"] = scope
        self.write(rel, json.dumps(data, indent=2) + "\n")

    def replace(self, rel, old, new):
        text = self.read(rel)
        self.assertIn(old, text)
        self.write(rel, text.replace(old, new, 1))

    def line_of(self, rel, fragment):
        for number, line in enumerate(self.read(rel).split("\n"), start=1):
            if fragment in line:
                return number
        self.fail("%s not in %s" % (fragment, rel))

    def screen(self, slug, transitions=()):
        text = self.template(
            ".agents/profiles/ui-migration/screen.md",
            {"domain": "demo", "slug": slug, "route": slug, "section": "demo",
             "spec operation": "get" + slug.title(), "legacy menu label": slug.title()},
        )
        text += "".join("| %s | %s |\n" % row for row in transitions)
        self.write("domains/demo/map/%s.md" % slug, text)

    def story(self, slug, scope_block=None):
        text = self.template(".agents/profiles/ui-migration/story.md", {"domain": "demo", "slug": slug})
        if scope_block is not None:
            text = text.replace("scope:\n  - screen:demo/%s\n" % slug, scope_block)
        self.write("%s/stories/%s/story.md" % (STREAM, slug), text)

    # --- runs ---

    def generate(self):
        result = run_generate(self.ws)
        self.assertEqual(result.returncode, 0, result.stderr)

    def check(self):
        self.generate()
        code, lines, stderr = run_check(self.ws)
        self.assertNotIn("Traceback", stderr)
        return code, lines

    def assertClean(self):
        self.assertEqual(self.check(), (0, []))

    def remaining(self):
        self.generate()
        result = subprocess.run(
            [sys.executable, "tools/check.py", "--remaining"], cwd=self.ws, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.splitlines()

    # --- the walk of domain demo ---

    def at_goal(self):
        self.write("domains/demo/README.md", self.template(".agents/templates/domain/README.md", {"name": "demo"}))
        self.write(STREAM_JSON, self.template(".agents/templates/stream.json", {"domain": "demo", "stream": "migration"}))
        self.write(STREAM + "/epic.md", self.template(".agents/templates/epic.md", {"Epic title": "Demo migration"}))

    def at_map(self):
        self.at_goal()
        self.screen("list", [("Open", "screen:demo/card")])
        self.screen("card")
        text = self.template(".agents/templates/MAP.md", {"domain": "demo"})
        header = "| Legacy group | Legacy item | Legacy route | Target |\n|---|---|---|---|\n"
        self.assertIn(header, text)
        text = text.replace(
            header,
            header + "| Docs | List | /docs | screen:demo/list |\n"
            "| Docs | Archive | /archive | dropped: runs through clerk, owner decision 2026-09-03 |\n",
        )
        self.write("domains/demo/MAP.md", text)
        self.update_stream(stage="map", approve="goal", scope=["screen:demo/list", "screen:demo/card"])

    def at_decomposition(self):
        self.at_map()
        self.story("list")
        self.replace(LIST_SCREEN, "\nstory:\n", "\nstory: story:demo/list\n")
        self.update_stream(stage="decomposition", approve="map")

    def fill_trackers(self):
        for slug, tracker in TRACKERS.items():
            self.replace("%s/stories/%s/story.md" % (STREAM, slug), "\ntracker:\n", "\ntracker: %s\n" % tracker)

    def record(self, tracker, story_key):
        text = self.template(".agents/templates/work-record.md", {"ID": tracker, "one-line summary": "demo work"})
        text = text.replace("\nrepos: []\n", "\nstory: %s\nrepos: []\n" % story_key, 1)
        self.write("work/%s/record.md" % tracker, text)

    # --- tests ---

    def test_fresh_workspace(self):
        self.assertClean()
        self.assertEqual(self.remaining(), [])

    def test_walk_through_stages(self):
        self.at_goal()
        self.assertClean()
        lines = self.remaining()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("%s goal approval: %s:1 " % (STREAM_KEY, STREAM_JSON)), lines)

        self.at_map()
        self.assertClean()

        self.story("list")
        self.replace(LIST_SCREEN, "\nstory:\n", "\nstory: story:demo/list\n")
        self.update_stream(stage="decomposition", approve="map")
        self.assertClean()
        lines = self.remaining()
        self.assertTrue(
            any(line.startswith("%s decomposition two_way_coverage: " % STREAM_KEY) and "screen:demo/card" in line
                for line in lines),
            lines,
        )
        self.assertFalse(any("screen:demo/list" in line for line in lines), lines)

        self.story("card")
        self.replace(CARD_SCREEN, "\nstory:\n", "\nstory: story:demo/card\n")
        self.story("bff-cleanup", "scope: []\nunmapped: bff defects\n")
        self.update_stream(stage="ready", approve="decomposition")
        self.assertClean()

        self.update_stream(stage="delivery")
        code, lines = self.check()
        self.assertEqual(code, 1, lines)
        self.assertEqual(
            sorted(line.split(" ")[0] for line in lines),
            sorted("%s/stories/%s/story.md:%d" % (STREAM, slug, self.line_of(
                "%s/stories/%s/story.md" % (STREAM, slug), "tracker:")) for slug in TRACKERS),
            lines,
        )
        for line in lines:
            self.assertIn(" stage-gate ready tracker_ids: ", line)

        self.fill_trackers()
        self.assertClean()

        self.update_stream(stage="done")
        self.assertClean()

        self.record("TASK-1", "story:demo/list")
        self.assertClean()
        lines = self.remaining()
        self.assertTrue(lines, lines)
        for line in lines:
            self.assertTrue(line.startswith("%s done work_records: " % STREAM_KEY), lines)
        self.assertFalse(any("/stories/list/" in line for line in lines), lines)
        self.assertTrue(any("/stories/card/" in line for line in lines), lines)

    def test_dangling_transition_after_map_closed(self):
        self.at_decomposition()
        self.assertClean()
        self.replace(LIST_SCREEN, "| Open | screen:demo/card |", "| Open | screen:demo/ghost |")
        code, lines = self.check()
        self.assertEqual(code, 1, lines)
        self.assertEqual(len(lines), 1, lines)
        line = self.line_of(LIST_SCREEN, "screen:demo/ghost")
        self.assertTrue(lines[0].startswith("%s:%d stage-gate map no_dangling_targets: " % (LIST_SCREEN, line)), lines)

    def test_approval_from_later_stage(self):
        self.at_map()
        self.assertClean()
        self.update_stream(approve="decomposition")
        code, lines = self.check()
        self.assertEqual(code, 1, lines)
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("%s:1 lifecycle " % STREAM_JSON), lines)

    def test_checklist_profile_stream(self):
        self.at_map()
        target = self.ws / ".agents/profiles/checklist"
        target.mkdir(parents=True)
        shutil.copy(str(CHECKLIST_PROFILE), str(target / "profile.json"))
        rules = "domains/policy/streams/rules"
        rules_json = rules + "/stream.json"
        rule = (
            "---\nkey: rule:policy/%s\nowner: risk\nstory: story:policy/%s\n---\n\n"
            "## Checks\n| Check | Target |\n|---|---|\n%s"
        )
        self.write("domains/policy/rules/limits.md", rule % ("limits", "limits", "| Related | rule:policy/caps |\n"))
        self.write("domains/policy/rules/caps.md", rule % ("caps", "limits", ""))
        self.write(rules + "/epic.md", "# Policy rules\n\n## Goal\nKeep limits checked.\n")
        self.write(
            rules + "/stories/limits/story.md",
            "---\nkey: story:policy/limits\ntype: story\nscope:\n  - rule:policy/limits\n  - rule:policy/caps\n"
            "tracker: TASK-9\n---\n\n## Goal\nCheck limits.\n\n## Open questions\nNone.\n",
        )
        stream = {"key": "stream:policy/rules", "profile": "checklist", "stage": "delivery",
                  "scope": ["rule:policy/limits", "rule:policy/caps"], "approvals": []}
        self.write(rules_json, json.dumps(stream, indent=2) + "\n")
        for stage in ("goal", "map", "decomposition"):
            self.update_stream(approve=stage, rel=rules_json)
        self.assertClean()

        self.replace("domains/policy/rules/limits.md", "| Related | rule:policy/caps |", "| Related | rule:policy/gone |")
        self.replace(rules + "/stories/limits/story.md", "\n  - rule:policy/caps\n", "\n")
        self.replace(rules + "/stories/limits/story.md", "\nNone.\n", "\nWho owns caps?\n")
        code, lines = self.check()
        self.assertEqual(code, 1, lines)
        gates = sorted(" ".join(line.split(" ")[1:4]) for line in lines)
        self.assertEqual(
            gates,
            ["stage-gate decomposition two_way_coverage:", "stage-gate map no_dangling_targets:",
             "stage-gate ready no_open_questions:"],
            lines,
        )
        self.assertTrue(any(line.startswith("domains/policy/rules/limits.md:%d " % self.line_of(
            "domains/policy/rules/limits.md", "rule:policy/gone")) for line in lines), lines)

    def test_planned_repository_in_story_repos(self):
        self.at_decomposition()
        repos = {"repositories": [{
            "name": "demo-bff", "default_branch": "main", "summary": "Future BFF of demo",
            "forge": "git", "roles": ["backend"], "status": "planned",
        }]}
        self.write("repos.json", json.dumps(repos, indent=2) + "\n")
        self.replace("%s/stories/list/story.md" % STREAM, "\nrepos: []\n", "\nrepos:\n  - repo:demo-bff\n")
        self.assertClean()


if __name__ == "__main__":
    unittest.main()
