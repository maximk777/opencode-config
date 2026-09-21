import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
import subprocess
import tempfile
import unittest

from wslib import gen_tables

REPOS_MD = "# Repos\n\nIntro\n<!-- repos:begin -->\nold\n<!-- repos:end -->\nTail\n"
HEADER = "| Name | Forge | Default branch | Kit | Summary |\n|---|---|---|---|---|\n"


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_out(root: Path, out) -> None:
    for rel, data in out.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def dump(obj) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()


class RepositoryTable(Base):
    def test_two_repos_render_new_header_in_manifest_order(self):
        write(self.root, "repos.json", dump({"repositories": [
            {"name": "b-repo", "remote": "git@x:b.git", "forge": "github",
             "default_branch": "master", "summary": "Second"},
            {"name": "a-repo", "remote": "git@x:a.git", "forge": "gitlab",
             "default_branch": "main", "summary": "First"},
        ]}))
        write(self.root, "REPOSITORIES.md", REPOS_MD)
        out = gen_tables.render(self.root)
        expected = (
            "# Repos\n\nIntro\n<!-- repos:begin -->\n" + HEADER
            + "| b-repo | github | master |  | Second |\n"
            + "| a-repo | gitlab | main |  | First |\n"
            + "<!-- repos:end -->\nTail\n"
        )
        self.assertEqual(out["REPOSITORIES.md"], expected.encode("utf-8"))
        write_out(self.root, out)
        self.assertEqual(gen_tables.render(self.root), out)

    def test_kit_column_holds_kit_kind(self):
        write(self.root, "repos.json", dump({"repositories": [
            {"name": "mfe-abs-operations", "remote": "git@x:mfe.git", "forge": "gitlab",
             "default_branch": "main", "roles": ["frontend"], "summary": "Operations",
             "kit": {"kind": "mfe", "params": {"APP_NAME": "abs-operations"}}},
            {"name": "docs-site", "remote": "git@x:docs.git", "forge": "github",
             "default_branch": "main", "summary": "Docs"},
        ]}))
        write(self.root, "REPOSITORIES.md", REPOS_MD)
        out = gen_tables.render(self.root)
        expected = (
            "# Repos\n\nIntro\n<!-- repos:begin -->\n" + HEADER
            + "| mfe-abs-operations | gitlab | main | mfe | Operations |\n"
            + "| docs-site | github | main |  | Docs |\n"
            + "<!-- repos:end -->\nTail\n"
        )
        self.assertEqual(out["REPOSITORIES.md"], expected.encode("utf-8"))
        write_out(self.root, out)
        self.assertEqual(gen_tables.render(self.root), out)

    def test_empty_repositories_gives_header_only(self):
        write(self.root, "repos.json", dump({"repositories": []}))
        write(self.root, "REPOSITORIES.md", REPOS_MD)
        out = gen_tables.render(self.root)
        expected = "# Repos\n\nIntro\n<!-- repos:begin -->\n" + HEADER + "<!-- repos:end -->\nTail\n"
        self.assertEqual(out["REPOSITORIES.md"], expected.encode("utf-8"))

    def test_without_markers_skips_table(self):
        write(self.root, "repos.json", dump({"repositories": []}))
        write(self.root, "REPOSITORIES.md", "# Repos\n\nNo markers\n")
        self.assertNotIn("REPOSITORIES.md", gen_tables.render(self.root))

    def test_invalid_repos_json_skips_table(self):
        write(self.root, "repos.json", "{not json\n")
        write(self.root, "REPOSITORIES.md", REPOS_MD)
        self.assertNotIn("REPOSITORIES.md", gen_tables.render(self.root))

    def test_wrong_repos_shape_skips_table(self):
        write(self.root, "repos.json", dump({"repositories": ["b-repo"]}))
        write(self.root, "REPOSITORIES.md", REPOS_MD)
        self.assertNotIn("REPOSITORIES.md", gen_tables.render(self.root))

    def test_kit_not_object_skips_table(self):
        write(self.root, "repos.json", dump({"repositories": [{"name": "a", "kit": "mfe"}]}))
        write(self.root, "REPOSITORIES.md", REPOS_MD)
        self.assertNotIn("REPOSITORIES.md", gen_tables.render(self.root))

    def test_kit_kind_not_string_skips_table(self):
        write(self.root, "repos.json", dump({"repositories": [{"name": "a", "kit": {"kind": 5}}]}))
        write(self.root, "REPOSITORIES.md", REPOS_MD)
        self.assertNotIn("REPOSITORIES.md", gen_tables.render(self.root))

    def test_lone_surrogate_skips_table(self):
        write(self.root, "repos.json", '{"repositories": [{"name": "a", "summary": "\\ud800"}]}\n')
        write(self.root, "REPOSITORIES.md", REPOS_MD)
        self.assertNotIn("REPOSITORIES.md", gen_tables.render(self.root))


class AliasIndex(Base):
    def test_adrs_then_diagrams_then_external(self):
        write(self.root, "docs/adr/0002-b.md", "b\n")
        write(self.root, "docs/adr/0001-a.md", "a\n")
        write(self.root, "docs/adr/.gitkeep", "")
        write(self.root, "docs/adr/notes.md", "x\n")
        write(self.root, "docs/diagrams/flow.md", "flow\n")
        write(self.root, "docs/diagrams/external.json", dump(
            {"diagrams": [{"key": "diagram:c4", "url": "https://arch.example/c4"}]}))
        out = gen_tables.render(self.root)
        expected = dump({
            "adr:0001": "docs/adr/0001-a.md",
            "adr:0002": "docs/adr/0002-b.md",
            "diagram:flow": "docs/diagrams/flow.md",
            "diagram:c4": "https://arch.example/c4",
        })
        self.assertEqual(out[".agents/index.json"], expected.encode("utf-8"))
        self.assertEqual(list(json.loads(out[".agents/index.json"])),
                         ["adr:0001", "adr:0002", "diagram:flow", "diagram:c4"])
        write_out(self.root, out)
        self.assertEqual(gen_tables.render(self.root), out)

    def test_empty_index(self):
        self.assertEqual(gen_tables.render(self.root)[".agents/index.json"], b"{}\n")

    def test_unreadable_external_json_contributes_nothing(self):
        write(self.root, "docs/diagrams/external.json", "{broken")
        self.assertEqual(gen_tables.render(self.root)[".agents/index.json"], b"{}\n")

    def test_external_skips_non_diagram_and_empty_keys(self):
        write(self.root, "docs/diagrams/external.json", dump({"diagrams": [
            {"key": "repo:x", "url": "https://a.example"},
            {"key": "work/TASK-1", "url": "https://b.example"},
            {"key": "diagram:", "url": "https://c.example"},
            {"key": "diagram:ok", "url": "https://d.example"},
        ]}))
        self.assertEqual(gen_tables.render(self.root)[".agents/index.json"],
                         dump({"diagram:ok": "https://d.example"}).encode("utf-8"))

    def test_external_lone_surrogate_skips_entry(self):
        write(self.root, "docs/diagrams/external.json",
              '{"diagrams": [{"key": "diagram:a", "url": "\\udc00"},'
              ' {"key": "diagram:\\ud800", "url": "https://x.example"},'
              ' {"key": "diagram:b", "url": "https://b.example"}]}\n')
        self.assertEqual(gen_tables.render(self.root)[".agents/index.json"],
                         dump({"diagram:b": "https://b.example"}).encode("utf-8"))

    def test_markdown_diagram_wins_over_external(self):
        write(self.root, "docs/diagrams/flow.md", "flow\n")
        write(self.root, "docs/diagrams/external.json", dump({"diagrams": [
            {"key": "diagram:flow", "url": "https://arch.example/flow"},
            {"key": "diagram:c4", "url": "https://arch.example/c4"},
        ]}))
        out = gen_tables.render(self.root)
        self.assertEqual(out[".agents/index.json"], dump({
            "diagram:flow": "docs/diagrams/flow.md",
            "diagram:c4": "https://arch.example/c4",
        }).encode("utf-8"))

    def test_adr_name_needs_ascii_digits(self):
        write(self.root, "docs/adr/\u0661\u0662\u0663\u0664-a.md", "x\n")
        write(self.root, "docs/adr/0001-a.md", "a\n")
        self.assertEqual(gen_tables.render(self.root)[".agents/index.json"],
                         dump({"adr:0001": "docs/adr/0001-a.md"}).encode("utf-8"))


STREAM = "projects/%s/domains/%s/streams/%s/stream.json"
STORY = "projects/%s/domains/%s/streams/%s/stories/%s/story.md"

# Minimal valid profile so the screen file is a discovered element in test_screen_file_adds_no_entry.
PROFILE = {
    "name": "ui-migration",
    "elements": [
        {"kind": "screen", "prefix": "screen", "dir": "map",
         "fields": ["key"], "may_be_empty": [], "values": {}, "tables": []}
    ],
    "story": {"fields": ["key", "type", "status", "tracker"], "sections": ["Goal"]},
    "stages": {"goal": [], "map": [], "decomposition": [], "ready": [], "delivery": [], "done": []},
}


def story_text(key: str, tracker: str = "") -> str:
    return "---\nkey: %s\ntype: story\nstatus: waiting\ntracker: %s\n---\n# Story\n" % (key, tracker)


def task_text(key: str, tracker: str = "") -> str:
    return "---\nkey: %s\ntype: e2e\nstatus: waiting\ntracker: %s\n---\n# Task\n" % (key, tracker)


class LifecycleIndex(Base):
    def add_stream(self, project: str, domain: str, stream: str) -> None:
        write(self.root, STREAM % (project, domain, stream),
              dump({"key": "stream:%s/%s/%s" % (project, domain, stream)}))

    def add_story(self, project: str, domain: str, stream: str, slug: str, text: str) -> str:
        rel = STORY % (project, domain, stream, slug)
        write(self.root, rel, text)
        return rel

    def index(self) -> dict:
        return json.loads(gen_tables.render(self.root)[".agents/index.json"])

    def test_mockups_follow_external_file_order_among_diagrams(self):
        write(self.root, "docs/diagrams/flow.md", "flow\n")
        write(self.root, "docs/diagrams/external.json", dump({"diagrams": [
            {"key": "mockup:abs/operations/list", "url": "https://figma.example/list"},
            {"key": "diagram:c4", "url": "https://arch.example/c4"},
            {"key": "mockup:", "url": "https://figma.example/empty"},
            {"key": "mockup:abs/operations/card", "url": "https://figma.example/card"},
        ]}))
        self.assertEqual(list(self.index().items()), [
            ("diagram:flow", "docs/diagrams/flow.md"),
            ("mockup:abs/operations/list", "https://figma.example/list"),
            ("diagram:c4", "https://arch.example/c4"),
            ("mockup:abs/operations/card", "https://figma.example/card"),
        ])

    def test_story_alias(self):
        self.add_stream("abs", "operations", "migration")
        rel = self.add_story("abs", "operations", "migration", "documents",
                             story_text("story:abs/operations/documents", "ODARM-145"))
        self.assertEqual(self.index(), {"story:abs/operations/documents": rel, "ODARM-145": rel})

    def test_task_alias(self):
        rel = "tasks/e2e-checkout/task.md"
        write(self.root, rel, task_text("task:e2e-checkout", "DEMO-3"))
        self.assertEqual(self.index(), {"task:e2e-checkout": rel, "DEMO-3": rel})

    def test_order_adrs_diagrams_stories_tasks_then_trackers(self):
        write(self.root, "docs/adr/0001-a.md", "a\n")
        write(self.root, "docs/diagrams/external.json", dump(
            {"diagrams": [{"key": "mockup:abs/operations/list", "url": "https://figma.example/list"}]}))
        self.add_stream("ops", "core", "b-stream")
        self.add_stream("billing", "payments", "a-stream")
        zeta = self.add_story("ops", "core", "b-stream", "zeta", story_text("story:ops/core/zeta", "OPS-1"))
        alpha = self.add_story("ops", "core", "b-stream", "alpha", story_text("story:ops/core/alpha", "OPS-9"))
        pay = self.add_story("billing", "payments", "a-stream", "pay", story_text("story:billing/payments/pay", "BIL-5"))
        checkout = "tasks/e2e-checkout/task.md"
        write(self.root, checkout, task_text("task:e2e-checkout", "DEMO-3"))
        out = gen_tables.render(self.root)
        self.assertEqual(list(json.loads(out[".agents/index.json"]).items()), [
            ("adr:0001", "docs/adr/0001-a.md"),
            ("mockup:abs/operations/list", "https://figma.example/list"),
            ("story:billing/payments/pay", pay),
            ("story:ops/core/alpha", alpha),
            ("story:ops/core/zeta", zeta),
            ("task:e2e-checkout", checkout),
            ("BIL-5", pay),
            ("DEMO-3", checkout),
            ("OPS-1", zeta),
            ("OPS-9", alpha),
        ])
        write_out(self.root, out)
        self.assertEqual(gen_tables.render(self.root), out)

    def test_empty_tracker_gives_no_alias(self):
        self.add_stream("ops", "core", "s")
        rel = self.add_story("ops", "core", "s", "a", story_text("story:ops/core/a"))
        self.add_story("ops", "core", "s", "b", "---\nkey: story:ops/core/b\ntype: story\n---\n")
        write(self.root, "tasks/plain/task.md", "---\nkey: task:plain\ntype: chore\nstatus: waiting\n---\n")
        self.assertEqual(self.index(), {
            "story:ops/core/a": rel,
            "story:ops/core/b": STORY % ("ops", "core", "s", "b"),
            "task:plain": "tasks/plain/task.md",
        })

    def test_broken_frontmatter_gives_no_entry(self):
        self.add_stream("ops", "core", "s")
        self.add_story("ops", "core", "s", "broken", "---\nkey: story:ops/core/broken\ntracker: OPS-2\n")
        self.add_story("ops", "core", "s", "blank", "---\nkey: story:ops/core/blank\n\ntracker: OPS-3\n---\n")
        write(self.root, "tasks/broken/task.md", "---\nkey: task:broken\ntracker: OPS-4\n")
        self.assertEqual(self.index(), {})

    def test_duplicate_tracker_first_story_key_wins(self):
        self.add_stream("ops", "core", "s")
        first = self.add_story("ops", "core", "s", "a", story_text("story:ops/core/a", "OPS-1"))
        second = self.add_story("ops", "core", "s", "b", story_text("story:ops/core/b", "OPS-1"))
        self.assertEqual(self.index(),
                         {"story:ops/core/a": first, "story:ops/core/b": second, "OPS-1": first})

    def test_screen_file_adds_no_entry(self):
        write(self.root, "docs/adr/0001-a.md", "a\n")
        write(self.root, ".agents/profiles/ui-migration/profile.json", dump(PROFILE))
        before = gen_tables.render(self.root)[".agents/index.json"]
        write(self.root, "projects/abs/domains/operations/map/documents.md",
              "---\nkey: screen:abs/operations/documents\n---\n")
        after = gen_tables.render(self.root)[".agents/index.json"]
        self.assertEqual(before, after)
        self.assertEqual(list(json.loads(after)), ["adr:0001"])

    def test_derivable_keys_stay_out(self):
        write(self.root, "docs/adr/0001-a.md", "a\n")
        write(self.root, "repos.json",
              dump({"repositories": [{"name": "web", "forge": "gitlab", "default_branch": "main"}]}))
        write(self.root, "environments.json", dump({"stands": [{"key": "stand:dev"}]}))
        write(self.root, "projects/abs/domains/operations/MAP.md", "# Map\n")
        self.add_stream("abs", "operations", "main")
        self.add_story("abs", "operations", "main", "documents",
                       story_text("story:abs/operations/documents", "ODARM-145"))
        task_rel = "tasks/e2e-checkout/task.md"
        write(self.root, task_rel, task_text("task:e2e-checkout", "DEMO-3"))
        keys = list(self.index())
        self.assertEqual(keys, ["adr:0001", "story:abs/operations/documents",
                                "task:e2e-checkout", "DEMO-3", "ODARM-145"])
        for prefix in ("repo:", "stand:", "domain:", "screen:", "stream:"):
            self.assertFalse(any(k.startswith(prefix) for k in keys), prefix)

    def test_ignored_story_excluded(self):
        self.add_stream("ops", "pay", "s")
        kept = self.add_story("ops", "pay", "s", "kept", story_text("story:ops/pay/kept", "OPS-1"))
        self.add_story("ops", "pay", "s", "ignored", story_text("story:ops/pay/ignored", "OPS-2"))
        write(self.root, ".gitignore", "projects/ops/domains/pay/streams/s/stories/ignored/\n")
        subprocess.run(["git", "init", "-q"], cwd=str(self.root), check=True)
        self.assertEqual(self.index(), {"story:ops/pay/kept": kept, "OPS-1": kept})


if __name__ == "__main__":
    unittest.main()
