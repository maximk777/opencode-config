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


if __name__ == "__main__":
    unittest.main()
