import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import datetime
import json
import shutil
import subprocess
import tempfile
import unittest

from workspace_helpers import DEFAULT_PARAMS, create_workspace, kit_command, run_check, run_generate

KIT = REPO / "kits/workspace"


def kit_meta():
    return json.loads((KIT / "kit.json").read_text(encoding="utf-8"))


def run(argv):
    return subprocess.run(argv, capture_output=True, text=True)


class CreateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def copy_kit(self):
        kit = self.tmp / "kit"
        shutil.copytree(KIT, kit, ignore=shutil.ignore_patterns("__pycache__"))
        return kit

    def assert_fresh_workspace(self, ws):
        meta = kit_meta()
        stamp = json.loads((ws / ".agents/kit.json").read_text(encoding="utf-8"))
        self.assertEqual(stamp, {"name": "workspace", "version": meta["version"], "params": DEFAULT_PARAMS})
        trackers = json.loads((ws / "tracker/trackers.json").read_text(encoding="utf-8"))
        self.assertEqual([tracker["key"] for tracker in trackers["trackers"]], ["main"])
        self.assertEqual(trackers["trackers"][0]["id_pattern"], DEFAULT_PARAMS["id_pattern"])
        for rel in meta["templated"]:
            self.assertNotIn("{{", (ws / rel).read_text(encoding="utf-8"), rel)
        self.assertTrue((ws / "CLAUDE.md").is_file())
        self.assertTrue((ws / ".agents/index.json").is_file())
        self.assertFalse((ws / "kit.json").exists())

    def test_create_into_missing_target(self):
        ws = create_workspace(self.tmp)
        self.assert_fresh_workspace(ws)

    def test_create_into_empty_directory(self):
        (self.tmp / "ws").mkdir()
        ws = create_workspace(self.tmp)
        self.assert_fresh_workspace(ws)

    def test_untemplated_file_keeps_braces(self):
        kit = self.copy_kit()
        (kit / "notes.md").write_text("Name: {{workspace_name}}\n", encoding="utf-8")
        ws = create_workspace(self.tmp, kit=kit)
        self.assertEqual((ws / "notes.md").read_text(encoding="utf-8"), "Name: {{workspace_name}}\n")

    def test_non_empty_target(self):
        target = self.tmp / "ws"
        target.mkdir()
        (target / "keep.txt").write_text("keep\n", encoding="utf-8")
        result = run(kit_command(target))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(sorted(p.name for p in target.iterdir()), ["keep.txt"])

    def assert_param_rejected(self, params, name):
        target = self.tmp / "ws"
        result = run(kit_command(target, params))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(name, result.stderr)
        self.assertFalse(target.exists())

    def test_missing_parameter(self):
        params = dict(DEFAULT_PARAMS)
        del params["title"]
        self.assert_param_rejected(params, "title")

    def test_unknown_parameter(self):
        self.assert_param_rejected(dict(DEFAULT_PARAMS, colour="red"), "colour")

    def test_invalid_forge(self):
        self.assert_param_rejected(dict(DEFAULT_PARAMS, forge="bitbucket"), "forge")

    def test_invalid_id_pattern(self):
        self.assert_param_rejected(dict(DEFAULT_PARAMS, id_pattern="(DEMO"), "id_pattern")

    def test_tracker_url_without_id(self):
        self.assert_param_rejected(dict(DEFAULT_PARAMS, tracker_url="https://tracker.example/i/"), "tracker_url")

    def test_language_parameter(self):
        ws = create_workspace(self.tmp, params=dict(DEFAULT_PARAMS, language="ru"))
        stamp = json.loads((ws / ".agents/kit.json").read_text(encoding="utf-8"))
        self.assertEqual(stamp["params"], dict(DEFAULT_PARAMS, language="ru"))

    def test_invalid_language(self):
        self.assert_param_rejected(dict(DEFAULT_PARAMS, language="russian"), "language")

    def test_generator_failure(self):
        kit = self.copy_kit()
        (kit / "tools/generate.py").write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
        parent = self.tmp / "out"
        parent.mkdir()
        target = parent / "ws"
        result = run(kit_command(target, kit=kit))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(target.exists())
        self.assertEqual([p.name for p in parent.iterdir() if p.name.startswith(".workspace-kit-")], [])

    def test_example_repository_kit_is_valid(self):
        ws = create_workspace(self.tmp)
        example = ws / ".agents/repo-kits/example"
        shutil.copytree(ws / ".agents/templates/repo-kit", example)
        _, lines, stderr = run_check(ws)
        self.assertNotIn("Traceback", stderr)
        self.assertNotIn("internal error", stderr)
        self.assertEqual([line for line in lines if " repo-kit " in line], [])


class AcceptanceTest(unittest.TestCase):
    """Change acceptance: two projects and tasks of three types pass check, and a flip moves the STATUS row."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = create_workspace(Path(self._tmp.name).resolve())

    def tearDown(self):
        self._tmp.cleanup()

    def read_template(self, rel):
        return (KIT / rel).read_text(encoding="utf-8")

    def write(self, rel, text):
        path = self.ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def add_project(self, name):
        text = self.read_template(".agents/templates/project.md")
        self.write("projects/%s/PROJECT.md" % name, text.replace("<project>", name).replace("<name>", name))

    def add_task(self, slug, kind):
        text = self.read_template(".agents/templates/task.md")
        text = (
            text.replace("<slug>", slug)
            .replace("type: task", "type: %s" % kind)
            .replace("<one-line summary>", "Accept the %s flow" % slug)
        )
        self.write("tasks/%s/task.md" % slug, text)

    def add_story(self, project, domain, stream, slug):
        data = json.loads(self.read_template(".agents/templates/stream.json"))
        data["key"] = "stream:%s/%s/%s" % (project, domain, stream)
        self.write(
            "projects/%s/domains/%s/streams/%s/stream.json" % (project, domain, stream),
            json.dumps(data, indent=2) + "\n",
        )
        story = self.read_template(".agents/profiles/ui-migration/story.md")
        # The template scope names a screen this acceptance never creates; an empty scope keeps key-resolve quiet.
        story = story.replace("scope:\n  - screen:<project>/<domain>/<slug>\n", "scope: []\n")
        story = (
            story.replace("<project>", project)
            .replace("<domain>", domain)
            .replace("<slug>", slug)
        )
        self.write(
            "projects/%s/domains/%s/streams/%s/stories/%s/story.md" % (project, domain, stream, slug),
            story,
        )

    def add_queue(self):
        self.add_project("abs")
        self.add_project("billing")
        self.add_task("billing-architecture", "architecture")
        self.add_task("e2e-checkout", "e2e")
        self.add_story("billing", "invoices", "checkout", "export-invoices")

    def status_section(self, name):
        text = (self.ws / "STATUS.md").read_text(encoding="utf-8")
        begin, end = "<!-- status:%s:begin -->" % name, "<!-- status:%s:end -->" % name
        return text.split(begin, 1)[1].split(end, 1)[0]

    def generate_and_check(self):
        result = run_generate(self.ws)
        self.assertEqual(result.returncode, 0, result.stderr)
        code, lines, stderr = run_check(self.ws)
        self.assertEqual(code, 0, "\n".join(lines) + stderr)

    def test_two_projects_and_three_task_types_pass_check(self):
        self.add_queue()
        self.generate_and_check()
        waiting = self.status_section("waiting")
        for link in (
            "[task:billing-architecture](tasks/billing-architecture/task.md)",
            "[task:e2e-checkout](tasks/e2e-checkout/task.md)",
            "[story:billing/invoices/export-invoices]"
            "(projects/billing/domains/invoices/streams/checkout/stories/export-invoices/story.md)",
        ):
            self.assertIn(link, waiting)

    def test_flip_moves_the_status_row(self):
        self.add_queue()
        self.generate_and_check()
        path = self.ws / "tasks/e2e-checkout/task.md"
        started = datetime.date.today().isoformat()
        text = path.read_text(encoding="utf-8")
        text = text.replace("status: waiting", "status: in_progress")
        text = text.replace("owner:\n", "owner: maxim\n").replace("started:\n", "started: %s\n" % started)
        path.write_text(text, encoding="utf-8")
        self.generate_and_check()
        in_progress = self.status_section("in-progress")
        self.assertIn("### maxim", in_progress)
        self.assertIn("| [task:e2e-checkout](tasks/e2e-checkout/task.md) | %s |" % started, in_progress)
        self.assertNotIn("[task:e2e-checkout](tasks/e2e-checkout/task.md)", self.status_section("waiting"))


if __name__ == "__main__":
    unittest.main()
