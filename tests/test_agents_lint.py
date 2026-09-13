import importlib.machinery
import os
import shutil
import tempfile
import unittest
from pathlib import Path

FIX = Path("tests/fixtures/agents-lint")
L = importlib.machinery.SourceFileLoader("agents_lint", "bin/agents-lint").load_module()


def prepared(name):
    tmp = Path(tempfile.mkdtemp()) / name
    shutil.copytree(FIX / name, tmp)
    (tmp / ".opencode").mkdir(exist_ok=True)
    if name != "bad-symlink":
        for kind in ("agents", "skills"):
            if (tmp / ".agents" / kind).exists():
                os.symlink(f"../.agents/{kind}", tmp / ".opencode" / kind)
    return tmp


class AgentsLint(unittest.TestCase):
    def reasons(self, name):
        return " | ".join(L.lint(prepared(name)))

    def test_good_repo_passes(self):
        self.assertEqual(L.lint(prepared("good")), [])

    def test_bad_name(self):
        self.assertIn("skill name", self.reasons("bad-name"))

    def test_bad_description(self):
        self.assertIn("description", self.reasons("bad-description"))

    def test_bad_size(self):
        self.assertIn("500 lines", self.reasons("bad-size"))

    def test_bad_depth(self):
        self.assertIn("deeper than one level", self.reasons("bad-depth"))

    def test_bad_templates(self):
        self.assertIn("templates/", self.reasons("bad-templates"))

    def test_bad_rule_path(self):
        self.assertIn("make integration", self.reasons("bad-rule-path"))

    def test_bad_frontmatter(self):
        self.assertIn("tools", self.reasons("bad-frontmatter"))

    def test_bad_symlink(self):
        self.assertIn("symlink", self.reasons("bad-symlink"))


def repo_with(files):
    tmp = Path(tempfile.mkdtemp())
    for rel, text in files.items():
        (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp / rel).write_text(text)
    (tmp / ".opencode").mkdir()
    for kind in ("agents", "skills"):
        if (tmp / ".agents" / kind).exists():
            os.symlink(f"../.agents/{kind}", tmp / ".opencode" / kind)
    return tmp


class FalsePositives(unittest.TestCase):
    def test_quoted_frontmatter(self):
        repo = repo_with({
            ".agents/skills/fine/SKILL.md": '---\nname: "fine"\ndescription: \'Use when testing quotes\'\n---\nText.\n',
            ".agents/agents/helper.md": '---\nname: helper\nmodel: "zai-coding-plan/glm-5.3"\n---\nBody.\n',
        })
        self.assertEqual(L.lint(repo), [])

    def test_code_inside_other_words_is_not_a_code_skill(self):
        repo = repo_with({".agents/skills/jwt/SKILL.md": "---\nname: jwt\ndescription: Use when you decode JWT claims\n---\nText.\n"})
        self.assertEqual(L.lint(repo), [])

    def test_model_with_nested_slash_and_tag(self):
        repo = repo_with({
            ".agents/agents/a.md": "---\nname: a\nmodel: openrouter/vendor/model-1.5\n---\n",
            ".agents/agents/b.md": "---\nname: b\nmodel: ollama/qwen3:8b\n---\n",
        })
        self.assertEqual(L.lint(repo), [])
        bad = repo_with({".agents/agents/c.md": "---\nname: c\nmodel: gpt-5\n---\n"})
        self.assertIn("provider/model", " ".join(L.lint(bad)))

    def test_rule_paths_that_are_not_repository_paths(self):
        repo = repo_with({
            "cmd/app/main.go": "package main\n",
            ".agents/rules/style.md": "Handlers live in `internal/**/*.go` and `<pkg>/handler.go`, see `cmd/app/main.go:12`,\n"
                                      "memory is at `viking://resources/x` and binaries in `/usr/local/bin`.\n",
        })
        self.assertEqual(L.lint(repo), [])
        missing = repo_with({".agents/rules/style.md": "See `cmd/app/gone.go:12`.\n"})
        self.assertIn("cmd/app/gone.go does not exist", " ".join(L.lint(missing)))

    def test_make_targets_declared_together(self):
        repo = repo_with({
            "Makefile": ".PHONY: build test\nGO := go\nbuild test: deps\n\t$(GO) test ./...\n",
            ".agents/rules/testing.md": "Run `make test` and `make build`.\n",
        })
        self.assertEqual(L.lint(repo), [])
        self.assertIn("make GO", " ".join(L.lint(repo_with({"Makefile": "GO := go\n", ".agents/rules/r.md": "`make GO`\n"}))))


if __name__ == "__main__":
    unittest.main()
