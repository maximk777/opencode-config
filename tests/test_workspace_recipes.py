"""Recipes for generated files, applied by hand, must equal tools/generate.py output."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from workspace_helpers import create_workspace, run_generate  # noqa: E402


def tree_bytes(root):
    # __pycache__ holds interpreter bytecode whose header embeds source mtimes, so it differs between any two workspaces.
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in sorted(root.rglob("*"))
            if p.is_file() and not {".git", "__pycache__"} & set(p.relative_to(root).parts)}


def write(ws, rel, text):
    path = ws / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def add_repository_source(ws, entry):
    manifest = json.loads((ws / "repos.json").read_text(encoding="utf-8"))
    manifest["repositories"].append(entry)
    write(ws, "repos.json", json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


def recipe_repository(ws, entry):
    text = (ws / "REPOSITORIES.md").read_text(encoding="utf-8")
    row = "| %s | %s | %s | %s | %s |" % (
        entry["name"], entry["forge"], entry["default_branch"], ", ".join(entry["roles"]), entry["summary"])
    end = "<!-- repos:end -->"
    assert text.count(end) == 1
    write(ws, "REPOSITORIES.md", text.replace(end, row + "\n" + end))


def recipe_adr(ws, number, slug):
    rel = ".agents/index.json"
    text = (ws / rel).read_text(encoding="utf-8")
    entry = '  "adr:%s": "docs/adr/%s-%s.md"' % (number, number, slug)
    if text == "{}\n":
        write(ws, rel, "{\n" + entry + "\n}\n")
        return
    lines = text.split("\n")
    adr_lines = [i for i, line in enumerate(lines) if line.startswith('  "adr:')]
    pos = adr_lines[-1] + 1 if adr_lines else lines.index("{") + 1
    before, after = lines[pos - 1], lines[pos]
    if before.startswith("  ") and not before.endswith(","):
        lines[pos - 1] = before + ","
    if after.startswith("  "):
        entry += ","
    lines.insert(pos, entry)
    write(ws, rel, "\n".join(lines))


def recipe_skill(ws, name):
    # The literal commands from the skill recipe in .agents/skills/extend/SKILL.md.
    commands = [
        "mkdir -p .claude/skills/{n} && cp -R .agents/skills/{n}/. .claude/skills/{n}/",
        "find .claude/skills/{n} -name .DS_Store -type f -delete",
        "find .claude/skills/{n} -name __pycache__ -type d -prune -exec rm -rf {{}} +",
    ]
    for command in commands:
        subprocess.run(command.format(n=name), shell=True, cwd=ws, check=True)


def recipe_agent(ws, name):
    source = (ws / ".agents/agents" / (name + ".md")).read_text(encoding="utf-8")
    write(ws, ".claude/agents/%s.md" % name, source)
    lines = source.split("\n")
    close = lines.index("---", 1)
    description = next(line for line in lines[1:close] if line.startswith("description:"))
    body = "\n".join(lines[close + 1:])
    write(ws, ".opencode/agents/%s.md" % name, "---\n" + description + "\nmode: subagent\n---\n" + body)


def recipe_rule(ws, name):
    source = (ws / ".agents/rules" / (name + ".md")).read_text(encoding="utf-8")
    first = source.split("\n", 1)[0]
    header = "---\ndescription: " + first[len("# "):] + "\nalwaysApply: true\n---\n"
    write(ws, ".cursor/rules/%s.mdc" % name, header + source)


class Recipes(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.recipe = create_workspace(self._tmp.name, "recipe")
        self.generated = create_workspace(self._tmp.name, "generated")
        self.both = (self.recipe, self.generated)

    def generate(self, ws):
        result = run_generate(ws)
        self.assertEqual(result.returncode, 0, result.stderr)

    def assertSameTrees(self):
        self.generate(self.generated)
        left, right = tree_bytes(self.recipe), tree_bytes(self.generated)
        differing = sorted(p for p in set(left) | set(right) if left.get(p) != right.get(p))
        self.assertEqual(differing, [], "paths differ between recipe and generated: %s" % differing)

    def test_repository(self):
        first = {"name": "orders-api", "remote": "git@example.com:t/orders-api.git", "forge": "gitlab",
                 "default_branch": "main", "roles": ["backend"], "summary": "Serves orders"}
        second = {"name": "payments-worker", "remote": "git@example.com:t/payments-worker.git",
                  "forge": "github", "default_branch": "develop", "roles": ["backend", "qa"],
                  "summary": "Consumes payment events and writes postings"}
        for entry in (first, second):
            for ws in self.both:
                add_repository_source(ws, entry)
            recipe_repository(self.recipe, entry)
        self.assertSameTrees()

    def test_adr_into_empty_index(self):
        for ws in self.both:
            write(ws, "docs/adr/0001-use-kafka.md", "# ADR-0001: Use Kafka\n")
        recipe_adr(self.recipe, "0001", "use-kafka")
        self.assertEqual((self.recipe / ".agents/index.json").read_text(encoding="utf-8"),
                         '{\n  "adr:0001": "docs/adr/0001-use-kafka.md"\n}\n')
        self.assertSameTrees()

    def test_adr_after_existing_adr_and_diagram(self):
        for ws in self.both:
            write(ws, "docs/adr/0001-a.md", "# ADR-0001: A\n")
            write(ws, "docs/diagrams/flow.md", "# Flow\n")
            self.generate(ws)
            write(ws, "docs/adr/0002-b.md", "# ADR-0002: B\n")
        recipe_adr(self.recipe, "0002", "b")
        self.assertSameTrees()

    def test_skill(self):
        for ws in self.both:
            write(ws, ".agents/skills/release-notes/SKILL.md",
                  "---\nname: release-notes\ndescription: Writes release notes.\n---\n# Release notes\n")
            write(ws, ".agents/skills/release-notes/examples/a.txt", "example\n")
            (ws / ".agents/skills/release-notes/.DS_Store").write_bytes(b"\x00\x00\x00\x01Bud1")
        recipe_skill(self.recipe, "release-notes")
        self.assertFalse((self.recipe / ".claude/skills/release-notes/.DS_Store").exists())
        self.assertSameTrees()

    def test_agent(self):
        source = ("---\nname: reviewer\ndescription: Reviews diffs: flags risky changes\n---\n"
                  "# Reviewer\nList findings as `path:line message`.\n")
        for ws in self.both:
            write(ws, ".agents/agents/reviewer.md", source)
        recipe_agent(self.recipe, "reviewer")
        self.assertSameTrees()

    def test_rule(self):
        for ws in self.both:
            write(ws, ".agents/rules/sql-style.md", "# SQL style\n\n- Write SQL keywords in upper case.\n")
        recipe_rule(self.recipe, "sql-style")
        self.assertSameTrees()


if __name__ == "__main__":
    unittest.main()
