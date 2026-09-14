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


def key_lines(lines):
    return [line for line in lines if len(line.split(" ")) > 1 and line.split(" ")[1] == RULE]


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

    def notes(self, link):
        self.write("docs/notes.md", "# Notes\n\nSee " + link + ".\n")

    def findings(self):
        _, lines, stderr = run_check(self.ws)
        self.assertNotIn("Traceback", stderr)
        return key_lines(lines)

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
        self.assert_fails("[adr:0009](docs/adr/0009-x.md)")

    def test_existing_adr(self):
        self.write("docs/adr/0009-x.md", "# ADR\n")
        self.assert_passes("[adr:0009](adr/0009-x.md)")
        self.assert_fails("[adr:0009](docs/adr/0010-y.md)")

    def test_tracker_link(self):
        self.assert_passes("[TASK-1](https://tracker.example/i/TASK-1)")
        self.assert_fails("[TASK-1](https://other.example/TASK-1)")

    def test_tracker_work_record(self):
        self.assert_fails("[TASK-1](../work/TASK-1/record.md)")
        self.write("work/TASK-1/record.md", "---\ntask: TASK-1\n---\n")
        self.assert_passes("[TASK-1](../work/TASK-1/record.md)")

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
        self.assert_fails("[domain:ops](../domains/ops/README.md)")
        self.write("domains/ops/README.md", "# Ops\n")
        self.assert_passes("[domain:ops](../domains/ops/README.md)")

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
        self.write_json("tracker/tracker.json", {"id_pattern": "a{4294967296}", "url": "https://t.example/i/{id}"})
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

    STORY = "domains/operations/streams/docs/stories/upload/story.md"

    def story(self, rel=STORY, tracker=""):
        self.write(rel, "---\nkey: story:operations/upload\ntracker: %s\n---\n# Upload\n" % tracker)

    def test_screen_link(self):
        self.write("domains/operations/map/documents.md", "---\nkey: screen:operations/documents\n---\n")
        self.write(self.STORY, "# Upload\n\nSee [screen:operations/documents](../../../../map/documents.md).\n")
        self.assertEqual(self.findings(), [])

    def test_screen_missing_file(self):
        self.assert_fails("[screen:operations/documents](../domains/operations/map/documents.md)")

    def test_screen_wrong_path(self):
        self.write("domains/operations/map/documents.md", "# Documents\n")
        self.assert_fails("[screen:operations/documents](../domains/operations/map/other.md)")

    def test_unknown_mockup(self):
        self.assert_fails("[mockup:risks/matches](https://example.test/x)")

    def test_external_mockup(self):
        self.write_json("docs/diagrams/external.json", {"diagrams": [
            {"key": "mockup:risks/matches", "url": "https://example.test/x"}]})
        self.assert_passes("[mockup:risks/matches](https://example.test/x)")
        self.assert_fails("[mockup:risks/matches](https://example.test/y)")

    def test_stream_link(self):
        self.assert_fails("[stream:operations/docs](../domains/operations/streams/docs/stream.json)")
        self.write_json("domains/operations/streams/docs/stream.json", {"key": "stream:operations/docs"})
        self.assert_passes("[stream:operations/docs](../domains/operations/streams/docs/stream.json)")
        self.assert_fails("[stream:operations/docs](../domains/operations/streams/docs/README.md)")

    def test_story_link_through_index(self):
        self.story()
        link = "[story:operations/upload](../domains/operations/streams/docs/stories/upload/story.md)"
        self.assert_fails(link)
        self.write_json(".agents/index.json", {"story:operations/upload": self.STORY})
        self.assert_passes(link)
        self.assert_fails("[story:operations/upload](../domains/operations/README.md)")

    def test_story_index_entry_to_missing_file(self):
        self.write_json(".agents/index.json", {"story:operations/upload": self.STORY})
        self.assert_fails("[story:operations/upload](../domains/operations/streams/docs/stories/upload/story.md)")

    def test_tracker_link_to_story_with_that_tracker(self):
        self.story(tracker="TASK-1")
        self.assert_passes("[TASK-1](../domains/operations/streams/docs/stories/upload/story.md)")

    def test_tracker_link_to_story_with_other_tracker(self):
        self.story(tracker="TASK-2")
        self.assert_fails("[TASK-1](../domains/operations/streams/docs/stories/upload/story.md)")

    def test_lookup_story_without_index_entry(self):
        from wslib.common import Context
        from wslib.rules_keys import lookup

        self.story()
        self.write_json(".agents/index.json", {"story:operations/other": self.STORY, "story:operations/upload": ["x"]})
        ctx = Context(self.ws)
        self.assertEqual(lookup(ctx, "story:x/y"), (False, []))
        self.assertEqual(lookup(ctx, "story:operations/upload"), (False, []))
        self.assertEqual(lookup(ctx, "story:operations/other"), (False, []))


if __name__ == "__main__":
    unittest.main()
