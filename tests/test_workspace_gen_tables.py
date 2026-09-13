import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
import tempfile
import unittest

from wslib import gen_tables

REPOS_MD = "# Repos\n\nIntro\n<!-- repos:begin -->\nold\n<!-- repos:end -->\nTail\n"
HEADER = "| Name | Forge | Default branch | Roles | Summary |\n|---|---|---|---|---|\n"


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
    def test_keeps_manifest_order(self):
        write(self.root, "repos.json", dump({"repositories": [
            {"name": "b-repo", "remote": "git@x:b.git", "forge": "github",
             "default_branch": "master", "roles": [], "summary": "Second"},
            {"name": "a-repo", "remote": "git@x:a.git", "forge": "gitlab",
             "default_branch": "main", "roles": ["backend", "qa"], "summary": "First"},
        ]}))
        write(self.root, "REPOSITORIES.md", REPOS_MD)
        out = gen_tables.render(self.root)
        expected = (
            "# Repos\n\nIntro\n<!-- repos:begin -->\n" + HEADER
            + "| b-repo | github | master |  | Second |\n"
            + "| a-repo | gitlab | main | backend, qa | First |\n"
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

    def test_work_record_does_not_change_index(self):
        write(self.root, "docs/adr/0001-a.md", "a\n")
        write(self.root, "repos.json", dump({"repositories": []}))
        write(self.root, "environments.json", dump({"stands": [{"key": "stand:dev"}]}))
        write(self.root, "domains/pay/README.md", "pay\n")
        before = gen_tables.render(self.root)[".agents/index.json"]
        write(self.root, "work/TASK-1/record.md", "---\ntask: TASK-1\n---\n")
        write_out(self.root, gen_tables.render(self.root))
        after = gen_tables.render(self.root)[".agents/index.json"]
        self.assertEqual(before, after)
        keys = list(json.loads(after))
        self.assertEqual(keys, ["adr:0001"])


if __name__ == "__main__":
    unittest.main()
