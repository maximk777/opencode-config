import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import tempfile
import unittest

from workspace_helpers import create_workspace, run_check

RULE = "neutral-agent"
SKILL_RULE = "skill-structure"


def rule_lines(lines, rule=RULE):
    """Keep only findings of one rule; other rule modules may add their own lines."""
    return [line for line in lines if len(line.split(" ")) > 1 and line.split(" ")[1] == rule]


VALID_SKILL = (
    "---\nname: quick\ndescription: Does a quick thing\n---\n"
    "# Quick\n\n## Steps\n1. Do the thing\n\n## Without Python\nDo it by hand.\n"
)


class CheckAgentsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.ws = create_workspace(self.tmp)

    def tearDown(self):
        self._tmp.cleanup()

    def write_agent(self, name, text):
        path = self.ws / ".agents/agents" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def write_skill(self, name, text):
        path = self.ws / ".agents/skills" / name / "SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def findings(self, rule=RULE):
        _, lines, stderr = run_check(self.ws)
        self.assertNotIn("Traceback", stderr)
        return rule_lines(lines, rule)

    def assert_one_finding(self, name):
        lines = self.findings()
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(".agents/agents/%s:1 %s" % (name, RULE)), lines)

    def test_fresh_workspace_has_none(self):
        self.assertEqual(self.findings(), [])

    def test_agent_with_name_and_description(self):
        self.write_agent("publisher.md", "---\nname: publisher\ndescription: Publishes pages\n---\nBody\n")
        self.assertEqual(self.findings(), [])

    def test_missing_description(self):
        self.write_agent("publisher.md", "---\nname: publisher\n---\nBody\n")
        self.assert_one_finding("publisher.md")

    def test_missing_frontmatter(self):
        self.write_agent("publisher.md", "# Publisher\n\nBody\n")
        self.assert_one_finding("publisher.md")

    def test_harness_tool_in_inline_list(self):
        self.write_agent(
            "publisher.md",
            "---\nname: publisher\ndescription: Publishes pages\n"
            "tools: [read, mcp__claude-in-chrome__navigate]\n---\nBody\n",
        )
        self.assert_one_finding("publisher.md")

    def test_harness_tool_in_block_list(self):
        self.write_agent(
            "publisher.md",
            "---\nname: publisher\ndescription: Publishes pages\n"
            "tools:\n  - read\n  - mcp__claude-in-chrome__navigate\n---\nBody\n",
        )
        self.assert_one_finding("publisher.md")

    def test_harness_tool_in_comma_separated_string(self):
        self.write_agent(
            "publisher.md",
            "---\nname: publisher\ndescription: Publishes pages\n"
            "tools: read, mcp__claude-in-chrome__navigate\n---\nBody\n",
        )
        self.assert_one_finding("publisher.md")

    def test_gitkeep_is_ignored(self):
        self.write_agent(".gitkeep", "")
        self.assertEqual(self.findings(), [])

    def test_valid_skill_passes(self):
        self.write_skill("quick", VALID_SKILL)
        self.assertEqual(self.findings(SKILL_RULE), [])

    def test_skill_without_numbered_steps(self):
        text = (
            "---\nname: quick\ndescription: Does a quick thing\n---\n"
            "# Quick\n\n## Steps\nDo the thing.\n\n## Without Python\nDo it by hand.\n"
        )
        self.write_skill("quick", text)
        lines = self.findings(SKILL_RULE)
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(
            lines[0].startswith(".agents/skills/quick/SKILL.md:1 %s" % SKILL_RULE), lines
        )


if __name__ == "__main__":
    unittest.main()
