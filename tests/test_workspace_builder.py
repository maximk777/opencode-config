import importlib.machinery
import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOME = str(Path.home())
CLAUDE_LINK = REPO / "bin" / "claude-link"


# bin/claude-link may be absent on a clean checkout, so load it only in the tests that need it.
def load_claude_link():
    return importlib.machinery.SourceFileLoader("claude_link", str(CLAUDE_LINK)).load_module()


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

    def test_entry_is_primary_fast_with_prompt(self):
        self.assertEqual(self.agent["mode"], "primary")
        self.assertEqual(self.agent["model"], "{file:./tiers/fast}")
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
        self.assertIn("workspace-normalize", prompt)
        self.assertIn("normalize", prompt)
        self.assertIn(".agents/kit.json", prompt)

    def test_prompt_routes_domain_phase_to_normalize(self):
        prompt = (REPO / "prompts" / "workspace-builder.md").read_text()
        routing = next((line for line in prompt.splitlines() if "domain phase" in line), "")
        self.assertIn("docs/normalize/plan.md", routing)
        self.assertIn(".agents/kit.json", routing)
        self.assertIn("todo", routing)
        self.assertIn("domain phase", routing)
        self.assertIn("workspace-normalize", routing)

    def test_prompt_create_mode_is_empty_directory_only(self):
        prompt = (REPO / "prompts" / "workspace-builder.md").read_text()
        routing = next((line for line in prompt.splitlines() if "workspace-create" in line), "")
        self.assertIn("empty directory", routing)
        self.assertNotIn("repository", routing)

    def test_prompt_names_workspace_language_rule(self):
        prompt = (REPO / "prompts" / "workspace-builder.md").read_text()
        rule = next((line for line in prompt.splitlines() if "params.language" in line), "")
        self.assertIn("unless the user asks otherwise", rule)
        self.assertIn("<name>.md", rule)
        self.assertIn("docs/normalize/plan.md", prompt)

    def test_normalize_skill_exists(self):
        skill = REPO / "skills" / "workspace-normalize" / "SKILL.md"
        self.assertTrue(skill.exists(), f"{skill} is missing")
        frontmatter = skill.read_text().split("---")[1]
        self.assertIn("name: workspace-normalize", frontmatter)

    @unittest.skipUnless(CLAUDE_LINK.exists(), "bin/claude-link is not present in this checkout")
    def test_claude_link_plans_agent_with_prompt_body(self):
        plan = load_claude_link().plan_agents(REPO)
        self.assertIn("workspace-builder", plan)
        body = (REPO / "prompts" / "workspace-builder.md").read_text().rstrip("\n")
        self.assertIn("name: workspace-builder", plan["workspace-builder"])
        self.assertIn(body, plan["workspace-builder"])


class WorkspaceCreateSkill(unittest.TestCase):
    def setUp(self):
        self.skill = (REPO / "skills" / "workspace-create" / "SKILL.md").read_text()

    def section(self, heading):
        start = self.skill.index(heading)
        end = self.skill.find("\n## ", start + 1)
        return self.skill[start:] if end == -1 else self.skill[start:end]

    def test_skill_has_no_roles_wording(self):
        self.assertNotIn("role", self.skill.lower())

    def test_collect_asks_for_trackers_after_the_seed_tracker(self):
        collect = self.section("## Collect")
        self.assertIn("{key, id_pattern, url}", collect)
        self.assertIn("seed tracker", collect)

    def test_describe_fills_trackers_json(self):
        self.assertIn("tracker/trackers.json", self.section("## Describe"))

    def test_first_project_runs_through_the_extend_skill(self):
        self.assertIn("first project", self.skill)
        self.assertIn("extend/SKILL.md", self.skill)
        self.assertIn("projects/<key>/PROJECT.md", self.skill)

    def test_verify_runs_generator_and_check(self):
        verify = self.section("## Verify")
        self.assertIn("tools/generate.py", verify)
        self.assertIn("tools/check.py", verify)

    def test_handoff_reports_trackers_and_project(self):
        handoff = self.section("## Hand-off")
        self.assertIn("trackers", handoff)
        self.assertIn("project", handoff)


if __name__ == "__main__":
    unittest.main()
