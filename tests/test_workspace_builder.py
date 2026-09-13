import importlib.machinery
import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOME = str(Path.home())
L = importlib.machinery.SourceFileLoader("claude_link", str(REPO / "bin" / "claude-link")).load_module()


# Mirrors match, expand and decide in tests/permissions.test.mjs: the last matching rule wins.
def match(value, pattern):
    escaped = re.sub(r"[.+^${}()|\[\]\\]", lambda m: "\\" + m.group(0), pattern)
    escaped = escaped.replace("*", ".*").replace("?", ".")
    if escaped.endswith(" .*"):
        escaped = escaped[:-3] + "( .*)?"
    return re.fullmatch(escaped, value, re.S) is not None


def expand(pattern):
    if pattern.startswith("~/"):
        return HOME + pattern[1:]
    if pattern.startswith("$HOME"):
        return HOME + pattern[5:]
    return pattern


def rules(permission):
    for key, value in (permission or {}).items():
        if isinstance(value, str):
            yield key, "*", value
        else:
            for pattern, action in value.items():
                yield key, expand(pattern), action


def decide(cfg, agent, permission, value):
    all_rules = [*rules(cfg.get("permission")), *rules(cfg["agent"][agent].get("permission"))]
    action = "ask"
    for key, pattern, rule_action in all_rules:
        if match(permission, key) and match(value, pattern):
            action = rule_action
    return action


class WorkspaceBuilderAgent(unittest.TestCase):
    def setUp(self):
        self.cfg = json.loads((REPO / "opencode.json").read_text())
        self.agent = self.cfg["agent"].get("workspace-builder")
        self.assertIsNotNone(self.agent, "opencode.json has no workspace-builder agent")

    def expect(self, permission, action, values):
        for value in values:
            self.assertEqual(decide(self.cfg, "workspace-builder", permission, value), action, f"{permission}: {value}")

    def test_entry_is_primary_smart_with_prompt(self):
        self.assertEqual(self.agent["mode"], "primary")
        self.assertEqual(self.agent["model"], "{file:./tiers/smart}")
        self.assertEqual(self.agent["prompt"], "{file:./prompts/workspace-builder.md}")

    def test_task_allows_only_explorer(self):
        task = self.agent["permission"]["task"]
        self.assertEqual({k for k, v in task.items() if v == "allow"}, {"explorer"})
        self.assertEqual(task["*"], "deny")

    def test_bash_denies_commit_and_push(self):
        self.expect("bash", "deny", ["git commit -m x", "git push", "git -C /w commit -m x", "git -C /w push"])

    def test_bash_allows_workspace_commands(self):
        self.expect("bash", "allow", [
            "git init",
            "python3 tools/check.py",
            "python3 tools/generate.py",
            "~/.config/opencode/bin/workspace-kit list",
        ])

    def test_edit_allows_workspace_files(self):
        self.expect("edit", "allow", ["AGENTS.md", ".agents/roles/qa.md", "/w/team/docs/adr/0001.md", ".env.example"])

    def test_edit_denies_env_files(self):
        self.expect("edit", "deny", [
            ".env", ".env.local", ".env.production", "/w/.env", "/w/app/.env", "/w/.env.local", "local.env",
        ])

    def test_edit_denies_opencode_setup(self):
        self.expect("edit", "deny", [
            f"{HOME}/.config/opencode/opencode.json",
            f"{HOME}/.config/opencode/kits/workspace/AGENTS.md",
            "~/.config/opencode/prompts/workspace-builder.md",
            "../../.config/opencode/opencode.json",
        ])

    def test_prompt_names_skills(self):
        prompt = (REPO / "prompts" / "workspace-builder.md").read_text()
        self.assertIn("workspace-create", prompt)
        self.assertIn("workspace-extend", prompt)

    def test_claude_link_plans_agent_with_prompt_body(self):
        plan = L.plan_agents(REPO)
        self.assertIn("workspace-builder", plan)
        body = (REPO / "prompts" / "workspace-builder.md").read_text().rstrip("\n")
        self.assertIn("name: workspace-builder", plan["workspace-builder"])
        self.assertIn(body, plan["workspace-builder"])


if __name__ == "__main__":
    unittest.main()
