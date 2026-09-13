import importlib.machinery
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

C = importlib.machinery.SourceFileLoader("console_server", "console/server.py").load_module()

MODELS_OUTPUT = """zai-coding-plan/glm-5.3
zai-coding-plan/glm-5.3-flash
deepseek/deepseek-flash
deepseek/deepseek-v4-pro
"""


class Console(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        (self.repo / "tiers").mkdir()
        (self.repo / "tiers" / "fast").write_text("zai-coding-plan/glm-5.3-flash\n")
        (self.repo / "tiers" / "smart").write_text("zai-coding-plan/glm-5.3\n")
        self.git_calls = []

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def git(self, *args):
        self.git_calls.append(list(args))

    def test_list_models(self):
        self.assertEqual(C.list_models(lambda: MODELS_OUTPUT)[2], "deepseek/deepseek-flash")

    def test_read_tiers(self):
        self.assertEqual(C.read_tiers(self.repo), {"fast": "zai-coding-plan/glm-5.3-flash", "smart": "zai-coding-plan/glm-5.3"})

    def test_write_tier_changes_only_that_tier_and_commits(self):
        models = C.list_models(lambda: MODELS_OUTPUT)
        C.write_tier(self.repo, "fast", "deepseek/deepseek-v4-pro", models, self.git)
        self.assertEqual((self.repo / "tiers" / "fast").read_text(), "deepseek/deepseek-v4-pro\n")
        self.assertEqual((self.repo / "tiers" / "smart").read_text(), "zai-coding-plan/glm-5.3\n")
        self.assertEqual(self.git_calls, [["add", "tiers/fast"], ["commit", "-m", "chore(tiers): set fast to deepseek-v4-pro", "--", "tiers/fast"]])

    def test_commit_leaves_unrelated_staged_changes(self):
        def git(*args):
            subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                           check=True, capture_output=True)
        git("init", "-q")
        git("add", "tiers")
        git("commit", "-q", "-m", "init")
        (self.repo / "other.txt").write_text("staged\n")
        git("add", "other.txt")
        C.write_tier(self.repo, "fast", "deepseek/deepseek-flash", C.list_models(lambda: MODELS_OUTPUT), git)
        show = subprocess.run(["git", "-C", str(self.repo), "show", "--name-only", "--format=", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.split()
        self.assertEqual(show, ["tiers/fast"])
        staged = subprocess.run(["git", "-C", str(self.repo), "diff", "--cached", "--name-only"],
                                capture_output=True, text=True, check=True).stdout.split()
        self.assertEqual(staged, ["other.txt"])

    def test_unknown_model_rejected(self):
        with self.assertRaises(ValueError):
            C.write_tier(self.repo, "fast", "nope/model", C.list_models(lambda: MODELS_OUTPUT), self.git)

    def test_unknown_tier_rejected(self):
        with self.assertRaises(ValueError):
            C.write_tier(self.repo, "deep", "deepseek/deepseek-flash", C.list_models(lambda: MODELS_OUTPUT), self.git)
        self.assertEqual(self.git_calls, [])


if __name__ == "__main__":
    unittest.main()
