import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
import re
import shutil
import subprocess
import tempfile
import unittest

from workspace_helpers import DEFAULT_PARAMS, run_check, run_generate

FIXTURE = REPO / "tests/fixtures/workspace-normalize"
LEGACY = FIXTURE / "legacy"
OVERLAY = FIXTURE / "overlay"
REMOVE = "REMOVE.txt"
PARAMS = dict(DEFAULT_PARAMS, forge="gitlab", language="ru")
GIT = ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false"]


class NormalizeFixtureTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name).resolve() / "ws"
        shutil.copytree(str(LEGACY), str(self.ws))
        for args in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "legacy"]):
            subprocess.run(GIT + args, cwd=self.ws, check=True, capture_output=True, text=True)

    def tearDown(self):
        self._tmp.cleanup()

    def adopt(self):
        argv = [sys.executable, str(REPO / "bin/workspace-kit"), "adopt", str(self.ws)]
        for key, value in PARAMS.items():
            argv += ["--param", "%s=%s" % (key, value)]
        result = subprocess.run(argv, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def apply_recipes(self):
        shutil.copytree(str(OVERLAY), str(self.ws), dirs_exist_ok=True, ignore=shutil.ignore_patterns(REMOVE))
        for rel in (OVERLAY / REMOVE).read_text(encoding="utf-8").split():
            path = self.ws / rel
            self.assertTrue(path.is_file(), rel)
            path.unlink()
            parent = path.parent
            while parent != self.ws and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent

    def test_adopt_keeps_existing_files(self):
        result = self.adopt()
        for rel in ("README.md", "tools/clone-repos.sh"):
            self.assertEqual((self.ws / rel).read_bytes(), (LEGACY / rel).read_bytes(), rel)
        self.assertIn("conflict: README.md", result.stdout.splitlines())

    def test_normalized_workspace_passes_check(self):
        self.adopt()
        self.apply_recipes()
        self.assertFalse((self.ws / "legacy").exists())
        generated = run_generate(self.ws)
        self.assertEqual(generated.returncode, 0, generated.stderr)
        code, lines, stderr = run_check(self.ws)
        self.assertEqual((code, lines), (0, []), stderr)
        remaining = subprocess.run(
            [sys.executable, "tools/check.py", "--remaining"], cwd=self.ws, capture_output=True, text=True
        )
        self.assertEqual(remaining.returncode, 0, remaining.stderr)
        # The 0.5.0 model discovers streams only under projects/, so the 0.4-shaped overlay domain
        # produces no gate lines; gate coverage on the new layout lives in NormalizeTeamMigrationTest.
        self.assertEqual(remaining.stdout.splitlines(), [])

    def test_generate_leaves_overlay_files_unchanged(self):
        self.adopt()
        self.apply_recipes()
        # The first generate rewrites the overlay's stale generated table, so it runs before the commit;
        # REPOSITORIES.md is generator-owned and exempt from the byte comparison.
        generated = run_generate(self.ws)
        self.assertEqual(generated.returncode, 0, generated.stderr)
        for args in (["add", "-A"], ["commit", "-qm", "overlay"]):
            subprocess.run(GIT + args, cwd=self.ws, check=True, capture_output=True, text=True)
        generated = run_generate(self.ws)
        self.assertEqual(generated.returncode, 0, generated.stderr)
        status = subprocess.run(GIT + ["status", "--porcelain"], cwd=self.ws, check=True, capture_output=True, text=True)
        modified = [line for line in status.stdout.splitlines() if not line.startswith("??")]
        self.assertEqual(modified, [])
        for path in sorted(OVERLAY.rglob("*")):
            rel = path.relative_to(OVERLAY).as_posix()
            if path.is_file() and rel not in (REMOVE, "REPOSITORIES.md"):
                self.assertEqual((self.ws / rel).read_bytes(), path.read_bytes(), rel)


class NormalizeTeamMigrationTest(unittest.TestCase):
    """The 0.4.1 fixture migrates to the team workplace layout by applying the plan actions mechanically."""

    KIT = REPO / "kits/workspace"
    TEAM_FIXTURE = REPO / "tests/fixtures/normalize-team"
    TEAM_PARAMS = dict(DEFAULT_PARAMS, forge="gitlab")
    PROJECT = "demo"  # the project key defaults to the workspace name
    RECORDED = "2026-09-15"  # the fixed merge date stands in for the record's last commit date
    LEGACY_KEY = re.compile(r"(?<![\w/-])((?:story|stream|domain|screen|mockup):)(?!demo/)")

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name).resolve() / "ws"
        shutil.copytree(str(self.TEAM_FIXTURE), str(self.ws))
        for args in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "legacy"]):
            subprocess.run(GIT + args, cwd=self.ws, check=True, capture_output=True, text=True)
        self.plan = []
        self._local_before = self.local_snapshot()
        self.assertTrue(self._local_before, "the fixture must carry a personal layer")

    def tearDown(self):
        self._tmp.cleanup()

    # --- helpers ---

    def write(self, rel, text):
        path = self.ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def read(self, rel):
        return (self.ws / rel).read_text(encoding="utf-8")

    def plan_action(self, action, source, target):
        self.plan.append((action, source, target))

    def local_snapshot(self):
        root = self.ws / ".local"
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    def template(self, rel, subs):
        text = self.read(rel)
        for placeholder, value in subs.items():
            text = text.replace("<%s>" % placeholder, value)
        return text

    def substitute(self, rel, data):
        # The kit binary substitutes templated files the same way; JSON values stay JSON-encoded.
        text = data.decode("utf-8")
        for key, value in self.TEAM_PARAMS.items():
            text = text.replace("{{" + key + "}}", json.dumps(value)[1:-1] if rel.endswith(".json") else value)
        return text.encode("utf-8")

    def frontmatter_field(self, rel, field):
        lines = self.read(rel).split("\n")
        end = lines[1:].index("---") + 1 if lines[0] == "---" else 1
        m = re.search(r"^%s: (.+)$" % field, "\n".join(lines[1:end]), re.M)
        return m.group(1) if m else None

    def stories(self):
        return sorted((self.ws / "projects").rglob("story.md"))

    # --- the migration actions, in the order the skill applies them ---

    def adopt_kit(self):
        meta = json.loads((self.KIT / "kit.json").read_text(encoding="utf-8"))
        templated = set(meta.get("templated", []))
        for path in sorted(self.KIT.rglob("*")):
            rel = path.relative_to(self.KIT).as_posix()
            if path.is_dir() or "__pycache__" in path.parts or rel == "kit.json":
                continue
            # tracker/trackers.json is written by the trackers convert action, like a hand merge row.
            # repos.json is the workspace's own manifest: an adopt conflict, merged by the roles off action.
            if rel in ("tracker/trackers.json", "repos.json"):
                continue
            data = path.read_bytes()
            if rel in templated:
                data = self.substitute(rel, data)
            dst = self.ws / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
            shutil.copymode(str(path), str(dst))
        # Files the 0.5.0 kit dropped and no other action moves.
        for rel in ("work/.gitkeep", ".agents/templates/work-record.md"):
            path = self.ws / rel
            if path.is_file():
                path.unlink()
        stamp = {"name": meta["name"], "version": meta["version"], "params": self.TEAM_PARAMS}
        self.write(".agents/kit.json", json.dumps(stamp, indent=2, ensure_ascii=False) + "\n")
        self.plan_action("adopt", "kit workspace 0.5.0", ".agents/kit.json")

    def projectize(self):
        project = self.ws / "projects" / self.PROJECT
        project.mkdir(parents=True, exist_ok=True)
        shutil.move(str(self.ws / "domains"), str(project / "domains"))
        self.write(
            "projects/%s/PROJECT.md" % self.PROJECT,
            self.template(".agents/templates/project.md", {"name": self.PROJECT, "project": self.PROJECT}),
        )
        self.plan_action("projectize", "domains/", "projects/%s/domains/" % self.PROJECT)

    def retarget(self):
        # Old keys carry no project segment; already-prefixed keys are skipped by the lookahead.
        for path in sorted((self.ws / "projects" / self.PROJECT).rglob("*")):
            if not path.is_file() or path.suffix not in (".md", ".json"):
                continue
            text = path.read_text(encoding="utf-8")
            new = self.LEGACY_KEY.sub(r"\1%s/" % self.PROJECT, text)
            if new != text:
                path.write_text(new, encoding="utf-8")
        self.plan_action("retarget", "projects/%s/" % self.PROJECT, "project-prefixed keys")

    def carrier_of(self, task_id):
        """The story or workspace task whose frontmatter tracker is task_id, or None."""
        candidates = self.stories() + sorted((self.ws / "tasks").rglob("task.md"))
        for path in candidates:
            if self.frontmatter_field(path.relative_to(self.ws).as_posix(), "tracker") == task_id:
                return path
        return None

    def stamp_status(self, path, status):
        rel = path.relative_to(self.ws).as_posix()
        if self.frontmatter_field(rel, "status") is not None:
            return rel, False
        text = path.read_text(encoding="utf-8")
        # The 0.4.1 story frontmatter has no status line; the queue state lands right after type.
        self.assertIn("type: story\n", text, rel)
        stamped = text.replace(
            "type: story\n",
            "type: story\nstatus: %s\nowner:\nstarted:\n" % status,
            1,
        )
        path.write_text(stamped, encoding="utf-8")
        return rel, True

    def work_merge(self):
        for record in sorted((self.ws / "work").glob("*/record.md")):
            task_id = self.frontmatter_field(record.relative_to(self.ws).as_posix(), "task")
            self.assertTrue(task_id, record)
            carrier = self.carrier_of(task_id)
            if carrier is None:
                # The keep row belongs to the owner; the migration never deletes the record.
                self.plan_action("keep", record.relative_to(self.ws).as_posix(), "-")
                continue
            folder = carrier.parent
            text = record.read_text(encoding="utf-8")
            self.write(folder / "work.md", text.replace("task: %s\n" % task_id, "recorded: %s\n" % self.RECORDED, 1))
            record.unlink()
            record.parent.rmdir()
            rel = folder.relative_to(self.ws).as_posix()
            self.plan_action("work merge", record.relative_to(self.ws).as_posix(), rel + "/work.md")
            story_rel, stamped = self.stamp_status(carrier, "done")
            if stamped:
                self.plan_action("status stamp", story_rel, "status: done")

    def status_stamp(self):
        for story in self.stories():
            story_rel, stamped = self.stamp_status(story, "waiting")
            if stamped:
                self.plan_action("status stamp", story_rel, "status: waiting")

    def roles_off(self):
        shutil.rmtree(self.ws / ".agents/roles")
        data = json.loads(self.read("repos.json"))
        for entry in data["repositories"]:
            entry.pop("roles", None)
        self.write("repos.json", json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        self.plan_action("roles off", ".agents/roles/, repos.json", "-")

    def trackers_convert(self):
        old = json.loads(self.read("tracker/tracker.json"))
        self.write("tracker/trackers.json", json.dumps({"trackers": [{
            "key": "main",
            "id_pattern": old["id_pattern"],
            "url": old["url"],
        }]}, indent=2, ensure_ascii=False) + "\n")
        (self.ws / "tracker/tracker.json").unlink()
        self.plan_action("trackers convert", "tracker/tracker.json", "tracker/trackers.json")

    # --- the test ---

    def test_migration_to_team_workplace(self):
        ws = self.ws
        self.adopt_kit()
        self.projectize()
        self.retarget()
        self.work_merge()
        self.status_stamp()
        self.roles_off()
        self.trackers_convert()

        # work/TASK-1/record.md landed in its story folder as work.md.
        merged = Path("projects/%s/domains/billing/streams/invoices/stories/list" % self.PROJECT)
        self.assertTrue((ws / merged / "work.md").is_file())
        text = (ws / merged / "work.md").read_text(encoding="utf-8")
        self.assertIn("recorded: %s\n" % self.RECORDED, text)
        self.assertNotIn("task: TASK-1", text)
        self.assertFalse((ws / "work/TASK-1").exists())

        # The record that resolves to no task stays in place as the plan's keep row.
        self.assertTrue((ws / "work/TASK-9/record.md").is_file())
        self.assertIn(("keep", "work/TASK-9/record.md", "-"), self.plan)

        # Stories are stamped: the merged story is done, the others wait with an empty queue state.
        statuses = {path.relative_to(ws).as_posix(): self.frontmatter_field(
            path.relative_to(ws).as_posix(), "status") for path in self.stories()}
        self.assertEqual(statuses, {
            "projects/%s/domains/billing/streams/invoices/stories/list/story.md" % self.PROJECT: "done",
            "projects/%s/domains/billing/streams/invoices/stories/export/story.md" % self.PROJECT: "waiting",
            "projects/%s/domains/catalog/streams/import/stories/items/story.md" % self.PROJECT: "waiting",
        })
        for rel in statuses:
            if statuses[rel] == "waiting":
                front = self.read(rel).split("---")[1]
                self.assertIn("owner:\n", front, rel)
                self.assertIn("started:\n", front, rel)

        # Roles left the manifest and the tree; the tracker became a list with the owner-named key.
        self.assertFalse((ws / ".agents/roles").exists())
        for entry in json.loads(self.read("repos.json"))["repositories"]:
            self.assertNotIn("roles", entry)
        self.assertFalse((ws / "tracker/tracker.json").exists())
        trackers = json.loads(self.read("tracker/trackers.json"))["trackers"]
        self.assertEqual(len(trackers), 1)
        self.assertEqual(trackers[0]["key"], "main")
        self.assertEqual(trackers[0]["id_pattern"], r"TASK-\d+")

        stamp = json.loads(self.read(".agents/kit.json"))
        self.assertEqual(stamp["version"], "0.5.0")

        # The owner resolves the keep row: nothing carries TASK-9, so the record leaves git and work/ goes away.
        (ws / "work/TASK-9/record.md").unlink()
        (ws / "work/TASK-9").rmdir()
        (ws / "work").rmdir()

        self.assertEqual(run_generate(ws).returncode, 0)
        code, lines, stderr = run_check(ws)
        self.assertEqual((code, lines), (0, []), stderr)
        self.assertFalse((ws / "work").exists())
        self.assertEqual(self.local_snapshot(), self._local_before)


if __name__ == "__main__":
    unittest.main()
