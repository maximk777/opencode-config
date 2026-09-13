import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import tempfile
import unittest

from wslib import gen_adapters

AGENT = b"---\nname: reviewer\ndescription: Reviews things\n---\nBody line\n"
SKILL = b"---\nname: demo\ndescription: Demo skill\n---\nUse it.\n"
EXAMPLE = b"example\n"
LINKS = b"# Keys and links\n\nText.\n"
PLAIN = b"No heading here.\n"


def write(root, rel, data):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


class Render(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)
        write(self.root, ".agents/kit.json", b"{}\n")

    def tearDown(self):
        self._td.cleanup()

    def fill(self):
        write(self.root, ".agents/agents/reviewer.md", AGENT)
        write(self.root, ".agents/skills/demo/SKILL.md", SKILL)
        write(self.root, ".agents/skills/demo/examples/a.txt", EXAMPLE)
        write(self.root, ".agents/rules/links.md", LINKS)
        write(self.root, ".agents/rules/plain.md", PLAIN)

    def test_full_fixture(self):
        self.fill()
        expected = {
            "CLAUDE.md": b"@AGENTS.md\n",
            ".claude/agents/reviewer.md": AGENT,
            ".opencode/agents/reviewer.md": b"---\ndescription: Reviews things\nmode: subagent\n---\nBody line\n",
            ".claude/skills/demo/SKILL.md": SKILL,
            ".claude/skills/demo/examples/a.txt": EXAMPLE,
            ".cursor/rules/links.mdc": b"---\ndescription: Keys and links\nalwaysApply: true\n---\n" + LINKS,
            ".cursor/rules/plain.mdc": b"---\ndescription: plain\nalwaysApply: true\n---\n" + PLAIN,
        }
        self.assertEqual(gen_adapters.render(self.root), expected)

    def test_without_sources_only_claude_md(self):
        self.assertEqual(gen_adapters.render(self.root), {"CLAUDE.md": b"@AGENTS.md\n"})

    def test_agent_without_frontmatter_uses_fallback_description(self):
        write(self.root, ".agents/agents/bare.md", b"Just body\n")
        out = gen_adapters.render(self.root)
        self.assertEqual(out[".opencode/agents/bare.md"], b"---\ndescription: \nmode: subagent\n---\nJust body\n")

    def test_agent_without_description_line_uses_fallback_description(self):
        write(self.root, ".agents/agents/nodesc.md", b"---\nname: nodesc\n---\nBody\n")
        out = gen_adapters.render(self.root)
        self.assertEqual(out[".opencode/agents/nodesc.md"], b"---\ndescription: \nmode: subagent\n---\nBody\n")

    def test_agent_frontmatter_without_closing_marker_is_whole_body(self):
        source = b"---\nname: open\ndescription: Open\nBody\n"
        write(self.root, ".agents/agents/open.md", source)
        out = gen_adapters.render(self.root)
        self.assertEqual(out[".opencode/agents/open.md"], b"---\ndescription: \nmode: subagent\n---\n" + source)

    def test_non_utf8_agent_is_rendered_byte_exact(self):
        source = b"---\ndescription: caf\xe9\n---\nBody \xff\n"
        write(self.root, ".agents/agents/latin.md", source)
        out = gen_adapters.render(self.root)
        self.assertEqual(out[".claude/agents/latin.md"], source)
        self.assertEqual(out[".opencode/agents/latin.md"], b"---\ndescription: caf\xe9\nmode: subagent\n---\nBody \xff\n")

    def test_non_utf8_rule_is_rendered_byte_exact(self):
        source = b"\xff intro\n# Caf\xe9\n"
        write(self.root, ".agents/rules/latin.md", source)
        out = gen_adapters.render(self.root)
        self.assertEqual(out[".cursor/rules/latin.mdc"], b"---\ndescription: Caf\xe9\nalwaysApply: true\n---\n" + source)

    def test_skill_junk_files_are_skipped(self):
        write(self.root, ".agents/skills/demo/SKILL.md", SKILL)
        write(self.root, ".agents/skills/demo/.DS_Store", b"junk")
        write(self.root, ".agents/skills/demo/examples/.DS_Store", b"junk")
        write(self.root, ".agents/skills/demo/__pycache__/x.pyc", b"junk")
        out = gen_adapters.render(self.root)
        self.assertEqual(out, {"CLAUDE.md": b"@AGENTS.md\n", ".claude/skills/demo/SKILL.md": SKILL})

    def test_skills_root_junk_entries_are_not_skills(self):
        write(self.root, ".agents/skills/demo/SKILL.md", SKILL)
        write(self.root, ".agents/skills/__pycache__/x.pyc", b"junk")
        write(self.root, ".agents/skills/.DS_Store", b"junk")
        write(self.root, ".agents/skills/.hidden/SKILL.md", b"junk")
        out = gen_adapters.render(self.root)
        self.assertEqual(out, {"CLAUDE.md": b"@AGENTS.md\n", ".claude/skills/demo/SKILL.md": SKILL})

    def test_two_calls_equal(self):
        self.fill()
        self.assertEqual(gen_adapters.render(self.root), gen_adapters.render(self.root))


if __name__ == "__main__":
    unittest.main()
