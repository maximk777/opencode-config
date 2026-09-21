import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
import tempfile
import unittest

from workspace_helpers import create_workspace, run_check

RULE = "key-resolve"

TRACKER = {"key": "main", "id_pattern": r"TASK-\d+", "url": "https://tracker.example/i/{id}"}
STORY = "projects/abs/domains/operations/streams/docs/stories/upload/story.md"
TASK = "tasks/e2e-checkout/task.md"


def key_lines(lines):
    return [line for line in lines if len(line.split(" ")) > 1 and line.split(" ")[1] == RULE]


def task_md(tracker=""):
    return (
        "---\nkey: task:e2e-checkout\ntype: e2e\nstatus: waiting\nowner:\nstarted:\ntracker: %s\n---\n"
        "\n# E2E checkout\n\n## Goal\n\nx\n" % tracker
    )


def adr_md(number):
    return "---\nkey: adr:%s\nstatus: proposed\n---\n\n# ADR %s\n" % (number, number)


class CheckKeysTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.ws = create_workspace(self.tmp)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text):
        path = self.ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def write_json(self, rel, obj):
        self.write(rel, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")

    def trackers(self, entries):
        self.write_json("tracker/trackers.json", {"trackers": entries})

    def notes(self, link):
        self.write("docs/notes.md", "# Notes\n\nSee " + link + ".\n")

    def findings(self):
        _, lines, stderr = run_check(self.ws)
        self.assertNotIn("Traceback", stderr)
        return key_lines(lines)

    def rule_lines(self, rule):
        _, lines, stderr = run_check(self.ws)
        self.assertNotIn("Traceback", stderr)
        return [line for line in lines if len(line.split(" ")) > 1 and line.split(" ")[1] == rule]

    def assert_fails(self, link):
        self.notes(link)
        lines = self.findings()
        self.assertTrue(any(line.startswith("docs/notes.md:3 ") for line in lines), f"{link}: {lines}")

    def assert_passes(self, link):
        self.notes(link)
        self.assertEqual(self.findings(), [], link)

    def test_fresh_workspace_has_no_key_findings(self):
        self.assertEqual(self.findings(), [])

    def test_missing_adr(self):
        self.assert_fails("[adr:0009](projects/abs/adr/0009-x.md)")

    def test_existing_adr(self):
        self.write("docs/adr/0009-x.md", "# ADR\n")
        self.assert_passes("[adr:0009](adr/0009-x.md)")
        self.assert_fails("[adr:0009](docs/adr/0010-y.md)")

    def test_project_adr(self):
        self.write("projects/abs/adr/0009-x.md", "# ADR\n")
        self.assert_passes("[adr:0009](../projects/abs/adr/0009-x.md)")
        self.assert_fails("[adr:0009](docs/adr/0009-x.md)")

    def test_adr_numbers_unique_across_places(self):
        self.write("docs/adr/0003-a.md", adr_md("0003"))
        self.write("projects/abs/adr/0003-b.md", adr_md("0003"))
        lines = self.rule_lines("adr")
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("0003", lines[0])

    def test_tracker_link(self):
        self.trackers([TRACKER])
        self.assert_passes("[TASK-1](https://tracker.example/i/TASK-1)")
        self.assert_fails("[TASK-1](https://other.example/TASK-1)")

    def test_tracker_link_to_story_with_that_tracker(self):
        self.trackers([TRACKER])
        self.story(tracker="TASK-1")
        self.assert_passes("[TASK-1](../projects/abs/domains/operations/streams/docs/stories/upload/story.md)")

    def test_tracker_link_to_story_with_other_tracker(self):
        self.trackers([TRACKER])
        self.story(tracker="TASK-2")
        self.assert_fails("[TASK-1](../projects/abs/domains/operations/streams/docs/stories/upload/story.md)")

    def test_tracker_link_to_task_with_that_tracker(self):
        self.trackers([TRACKER])
        self.write(TASK, task_md(tracker="TASK-1"))
        self.assert_passes("[TASK-1](../tasks/e2e-checkout/task.md)")

    def test_tracker_link_to_task_with_other_tracker(self):
        self.trackers([TRACKER])
        self.write(TASK, task_md(tracker="TASK-2"))
        self.assert_fails("[TASK-1](../tasks/e2e-checkout/task.md)")

    def test_ambiguous_tracker_id(self):
        self.trackers([
            {"key": "alpha", "id_pattern": r"\d+", "url": "https://a.example/{id}"},
            {"key": "beta", "id_pattern": "42", "url": "https://b.example/{id}"},
        ])
        self.notes("[42](https://a.example/42)")
        lines = self.findings()
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("alpha", lines[0])
        self.assertIn("beta", lines[0])

    def test_repo(self):
        self.assert_fails("[repo:ghost](x)")
        self.write_json("repos.json", {"repositories": [{
            "name": "ghost", "remote": "git@x:ghost.git", "forge": "gitlab", "default_branch": "main",
            "roles": ["backend"], "summary": "Service"}]})
        self.assert_passes("[repo:ghost:api/openapi.yaml#getItems](anything)")

    def test_stand(self):
        self.write_json("environments.json", {"stands": [{
            "key": "stand:stage", "purpose": "Testing", "access": "VPN",
            "services": {"api": "https://stage.example"}}]})
        self.assert_passes("[stand:stage](../environments.json)")
        self.assert_fails("[stand:stage](../README.md)")

    def test_domain(self):
        self.assert_fails("[domain:abs/ops](../projects/abs/domains/ops/README.md)")
        self.write("projects/abs/domains/ops/README.md", "# Ops\n")
        self.assert_passes("[domain:abs/ops](../projects/abs/domains/ops/README.md)")

    def test_diagram_file(self):
        self.assert_fails("[diagram:flow](diagrams/flow.md)")
        self.write("docs/diagrams/flow.md", "# Flow\n")
        self.assert_passes("[diagram:flow](diagrams/flow.md)")

    def test_external_diagram(self):
        self.write_json("docs/diagrams/external.json", {"diagrams": [
            {"key": "diagram:c4", "url": "https://diagrams.example/c4"}]})
        self.assert_passes("[diagram:c4](https://diagrams.example/c4)")
        self.assert_fails("[diagram:c4](https://diagrams.example/other)")

    def test_plain_link_is_ignored(self):
        self.assert_passes("[readme](../README.md)")

    def test_link_in_fenced_block_is_ignored(self):
        self.write("docs/notes.md", "# Notes\n\n```\n[adr:0009](x.md)\n```\n")
        self.assertEqual(self.findings(), [])

    def test_link_in_inline_code_is_ignored(self):
        self.assert_passes("`[adr:0009](x.md)`")

    def test_inner_fence_lines_do_not_close_block(self):
        self.write("docs/notes.md", "\n".join([
            "# Notes",
            "",
            "```",
            "~~~",
            "[adr:0001](a.md)",
            "```json",
            "[adr:0002](a.md)",
            "```",
            "",
            "See [adr:0009](x.md).",
            "",
        ]))
        lines = self.findings()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("docs/notes.md:10 "), lines)

    def test_key_in_backticks_as_link_text_is_checked(self):
        self.assert_fails("[`adr:0009`](x.md)")

    def test_tracker_pattern_overflowing_compiler_does_not_crash(self):
        self.write_json("tracker/trackers.json", {"trackers": [
            {"key": "t", "id_pattern": "a{4294967296}", "url": "https://t.example/i/{id}"}]})
        code, _, stderr = run_check(self.ws)
        self.assertNotEqual(code, 2, stderr)
        self.assertNotIn("Traceback", stderr)

    def assert_check_does_not_crash(self):
        code, lines, stderr = run_check(self.ws)
        self.assertNotEqual(code, 2, stderr)
        self.assertNotIn("Traceback", stderr)
        return key_lines(lines)

    def test_repo_name_list_does_not_crash(self):
        self.write_json("repos.json", {"repositories": [{"name": ["x"]}]})
        self.notes("[repo:x](a)")
        lines = self.assert_check_does_not_crash()
        self.assertTrue(any(line.startswith("docs/notes.md:3 ") for line in lines), lines)

    def test_stand_key_dict_does_not_crash(self):
        self.write_json("environments.json", {"stands": [{"key": {"k": "stand:stage"}}]})
        self.notes("[stand:stage](../environments.json)")
        lines = self.assert_check_does_not_crash()
        self.assertTrue(any(line.startswith("docs/notes.md:3 ") for line in lines), lines)

    def test_adr_affects_with_unhashable_names_does_not_crash(self):
        self.write_json("repos.json", {"repositories": [{"name": {"a": 1}}]})
        self.write_json("environments.json", {"stands": [{"key": ["stand:stage"]}]})
        self.write("docs/adr/0009-x.md", "---\nstatus: proposed\naffects: [repo:x, stand:stage]\n---\n# ADR\n")
        self.assert_check_does_not_crash()

    def test_lookup_considers_only_string_names_and_keys(self):
        from wslib.common import Context
        from wslib.rules_keys import lookup

        odd = [["x"], {"a": 1}, 1, None, True, 1.5]
        self.write_json("repos.json", {"repositories": [{"name": v} for v in odd] + [{"name": "real"}]})
        self.write_json("environments.json", {"stands": [{"key": v} for v in odd] + [{"key": "stand:real"}]})
        self.write_json("docs/diagrams/external.json", {"diagrams": [
            {"key": v, "url": v} for v in odd] + [{"key": "diagram:c4", "url": ["u"]}]})
        ctx = Context(self.ws)
        self.assertEqual(lookup(ctx, "repo:real"), (True, None))
        self.assertEqual(lookup(ctx, "repo:x"), (False, None))
        self.assertEqual(lookup(ctx, "stand:real"), (True, ["environments.json"]))
        self.assertFalse(lookup(ctx, "stand:x")[0])
        self.assertFalse(lookup(ctx, "diagram:c4")[0])
        for key in odd:
            self.assertFalse(lookup(ctx, key)[0], key)

    def story(self, rel=STORY, tracker=""):
        self.write(rel, "---\nkey: story:abs/operations/upload\ntracker: %s\n---\n# Upload\n" % tracker)

    def test_task_link(self):
        self.write(TASK, task_md())
        self.assert_passes("[task:e2e-checkout](../tasks/e2e-checkout/task.md)")
        self.assert_fails("[task:e2e-checkout](../tasks/e2e-checkout/other.md)")
        self.assert_fails("[task:ghost](../tasks/e2e-checkout/task.md)")

    def test_task_link_from_project_note(self):
        self.write(TASK, task_md())
        self.write(
            "projects/abs/domains/note.md",
            "# Note\n\nSee [task:e2e-checkout](../../../tasks/e2e-checkout/task.md).\n",
        )
        self.assertEqual(self.findings(), [])

    def test_screen_link(self):
        self.write(
            "projects/abs/domains/operations/map/documents.md",
            "---\nkey: screen:abs/operations/documents\n---\n",
        )
        self.write(STORY, "# Upload\n\nSee [screen:abs/operations/documents](../../../../map/documents.md).\n")
        self.assertEqual(self.findings(), [])

    def test_screen_missing_file(self):
        self.assert_fails("[screen:abs/operations/documents](../projects/abs/domains/operations/map/documents.md)")

    def test_screen_wrong_path(self):
        self.write("projects/abs/domains/operations/map/documents.md", "# Documents\n")
        self.assert_fails("[screen:abs/operations/documents](../projects/abs/domains/operations/map/other.md)")

    def rule_profile(self):
        profile = json.loads((self.ws / ".agents/profiles/ui-migration/profile.json").read_text(encoding="utf-8"))
        profile["name"] = "rules"
        profile["elements"] = [{"kind": "rule", "prefix": "rule", "dir": "rules", "fields": ["key"]}]
        self.write_json(".agents/profiles/rules/profile.json", profile)

    def test_workspace_profile_element_missing(self):
        self.rule_profile()
        self.write(
            "docs/notes.md",
            "# Notes\n\nSee [rule:abs/billing/limits](projects/abs/domains/billing/rules/limits.md).\n",
        )
        lines = self.findings()
        self.assertTrue(any(line.startswith("docs/notes.md:3 ") for line in lines), lines)

    def test_workspace_profile_element_exists(self):
        self.rule_profile()
        self.write("projects/abs/domains/billing/rules/limits.md", "---\nkey: rule:abs/billing/limits\n---\n")
        self.assert_passes("[rule:abs/billing/limits](../projects/abs/domains/billing/rules/limits.md)")
        self.assert_fails("[rule:abs/billing/limits](../projects/abs/domains/billing/rules/other.md)")

    def test_screen_resolves_through_kit_profile(self):
        from wslib.common import Context
        from wslib.rules_keys import lookup

        self.write("projects/abs/domains/operations/map/documents.md", "# Documents\n")
        ctx = Context(self.ws)
        self.assertEqual(lookup(ctx, "screen:abs/operations/documents"),
                         (True, ["projects/abs/domains/operations/map/documents.md"]))

    def test_prefix_declared_by_no_profile_is_not_a_key(self):
        from wslib.common import Context
        from wslib.rules_keys import lookup

        self.assert_passes("[rule:abs/billing/limits](nowhere.md)")
        self.assertEqual(lookup(Context(self.ws), "rule:abs/billing/limits"), (False, []))

    def test_unknown_mockup(self):
        self.assert_fails("[mockup:risks/matches](https://example.test/x)")

    def test_external_mockup(self):
        self.write_json("docs/diagrams/external.json", {"diagrams": [
            {"key": "mockup:risks/matches", "url": "https://example.test/x"}]})
        self.assert_passes("[mockup:risks/matches](https://example.test/x)")
        self.assert_fails("[mockup:risks/matches](https://example.test/y)")

    def test_stream_link(self):
        self.assert_fails("[stream:abs/operations/docs](../projects/abs/domains/operations/streams/docs/stream.json)")
        self.write_json(
            "projects/abs/domains/operations/streams/docs/stream.json", {"key": "stream:abs/operations/docs"})
        self.assert_passes(
            "[stream:abs/operations/docs](../projects/abs/domains/operations/streams/docs/stream.json)")
        self.assert_fails("[stream:abs/operations/docs](../projects/abs/domains/operations/streams/docs/README.md)")

    def test_story_link_through_index(self):
        self.story()
        link = "[story:abs/operations/upload](../projects/abs/domains/operations/streams/docs/stories/upload/story.md)"
        self.assert_fails(link)
        self.write_json(".agents/index.json", {"story:abs/operations/upload": STORY})
        self.assert_passes(link)
        self.assert_fails("[story:abs/operations/upload](../projects/abs/domains/operations/README.md)")

    def test_story_index_entry_to_missing_file(self):
        self.write_json(".agents/index.json", {"story:abs/operations/upload": STORY})
        link = "[story:abs/operations/upload](../projects/abs/domains/operations/streams/docs/stories/upload/story.md)"
        self.assert_fails(link)

    def test_tracker_link_to_story_needs_tracker_file(self):
        # Without tracker/trackers.json the id matches no pattern, so the link is not checked at all.
        self.story(tracker="TASK-1")
        self.assert_passes("[TASK-1](../projects/abs/domains/operations/streams/docs/stories/upload/story.md)")

    def test_lookup_story_without_index_entry(self):
        from wslib.common import Context
        from wslib.rules_keys import lookup

        self.story()
        self.write_json(
            ".agents/index.json",
            {"story:abs/operations/other": STORY, "story:abs/operations/upload": ["x"]},
        )
        ctx = Context(self.ws)
        self.assertEqual(lookup(ctx, "story:abs/ghost/upload"), (False, []))
        self.assertEqual(lookup(ctx, "story:abs/operations/upload"), (False, []))
        self.assertEqual(lookup(ctx, "story:abs/operations/other"), (False, []))


if __name__ == "__main__":
    unittest.main()
