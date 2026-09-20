import importlib.machinery
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

L = importlib.machinery.SourceFileLoader("claude_link", "bin/claude-link").load_module()
C = importlib.machinery.SourceFileLoader("claude_change_context", "bin/claude-change-context").load_module()
REPO = Path(".").resolve()


class ClaudeLink(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        (self.home / "settings.json").write_text(json.dumps({"enabledPlugins": {"magent@magent": True, "other@x": True}}))

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def test_links_generates_and_is_idempotent(self):
        done, refused = L.apply(REPO, self.home)
        self.assertEqual(refused, [])
        self.assertEqual((self.home / "CLAUDE.md").resolve(), (REPO / "AGENTS.md").resolve())
        self.assertTrue((self.home / "skills" / "change-execute" / "SKILL.md").exists())
        agent = (self.home / "agents" / "task-reviewer.md").read_text()
        self.assertIn("name: task-reviewer", agent)
        self.assertIn("model: sonnet", agent)
        self.assertIn("tools: Read, Grep, Glob, Bash, Edit", agent)
        self.assertIn("You are task-reviewer.", agent)
        self.assertIn("model: sonnet", (self.home / "agents" / "executor.md").read_text())
        self.assertEqual(L.apply(REPO, self.home), ([], []))

    def test_settings_disable_plugins_add_hook_and_deny(self):
        L.apply(REPO, self.home)
        s = json.loads((self.home / "settings.json").read_text())
        self.assertEqual(s["enabledPlugins"], {"magent@magent": False, "other@x": True})
        self.assertEqual(s["hooks"]["SessionStart"][0]["matcher"], "compact")
        self.assertIn("Bash(printenv:*)", s["permissions"]["deny"])

    def test_refuses_foreign_files(self):
        (self.home / "agents").mkdir()
        (self.home / "agents" / "explorer.md").write_text("my own agent")
        (self.home / "CLAUDE.md").write_text("my own rules")
        _, refused = L.apply(REPO, self.home)
        self.assertEqual((self.home / "agents" / "explorer.md").read_text(), "my own agent")
        self.assertEqual(len(refused), 2)

    def test_agent_description_is_valid_yaml_string(self):
        text = L.agent_text("x", {"model": "{file:./tiers/smart}", "description": "Reviews: spec first"}, "body")
        self.assertIn('description: "Reviews: spec first"', text)

    def test_explorer_gets_openviking_read_tools(self):
        agents = L.plan_agents(REPO)
        self.assertIn("tools: Read, Grep, Glob, Bash, mcp__openviking__find, mcp__openviking__search", agents["explorer"])

    def test_agent_without_openviking_permission_gets_no_mcp_tools(self):
        spec = {"model": "{file:./tiers/fast}", "description": "d"}
        text = L.agent_text("explorer", spec, "body")
        self.assertNotIn("mcp__openviking", text)
        self.assertIn("tools: Read, Grep, Glob, Bash", text)

    def test_ask_deny_and_wildcard_permissions_do_not_add_tools(self):
        spec = {
            "model": "{file:./tiers/fast}",
            "description": "d",
            "permission": {"openviking_find": "ask", "openviking_search": "deny", "openviking_*": "deny"},
        }
        text = L.agent_text("explorer", spec, "body")
        self.assertNotIn("mcp__openviking", text)

    def test_later_wildcard_deny_overrides_earlier_exact_allow(self):
        spec = {
            "model": "{file:./tiers/fast}",
            "description": "d",
            "permission": {"openviking_find": "allow", "openviking_*": "deny"},
        }
        text = L.agent_text("explorer", spec, "body")
        self.assertNotIn("mcp__openviking", text)

    def test_later_exact_allow_overrides_earlier_wildcard_deny(self):
        spec = {
            "model": "{file:./tiers/fast}",
            "description": "d",
            "permission": {"openviking_*": "deny", "openviking_find": "allow"},
        }
        text = L.agent_text("explorer", spec, "body")
        self.assertIn("mcp__openviking__find", text)
        self.assertNotIn("mcp__openviking__search", text)

    def test_task_reviewer_still_gets_no_openviking_tools(self):
        agents = L.plan_agents(REPO)
        self.assertNotIn("mcp__openviking", agents["task-reviewer"])


class McpHelper(unittest.TestCase):
    def test_mcp_config_uses_headers_helper_without_key(self):
        cfg = json.loads(L.mcp_json(REPO))
        self.assertEqual(cfg["type"], "http")
        self.assertTrue(cfg["headersHelper"].endswith("bin/ov-mcp-headers"))
        self.assertNotIn("Authorization", json.dumps(cfg))


class ChangeContext(unittest.TestCase):
    def test_prints_active_change_state_for_repo_project(self):
        root = Path(tempfile.mkdtemp())
        specs, work = root / "specs", root / "proj"
        ch = specs / "proj" / "openspec" / "changes" / "add-x"
        (ch / "reports").mkdir(parents=True)
        (specs / "proj" / "openspec" / "changes" / "archive").mkdir()
        (ch / "tasks.md").write_text("## 1\n- [x] 1.1 a\n- [ ] 1.2 b\n")
        (ch / "reports" / "1.2.md").write_text("# Report 1.2\nStatus: DONE\n")
        work.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=work, check=True)
        out = C.context(work, specs)
        self.assertIn("Change proj/add-x: 1/2 tasks done", out)
        self.assertIn("awaiting_review: 1.2", out)
        self.assertEqual(C.context(root, specs), "")
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
