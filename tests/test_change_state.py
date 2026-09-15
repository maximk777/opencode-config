import importlib.machinery
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

S = importlib.machinery.SourceFileLoader("change_state", "bin/change-state").load_module()

GIT_IDENTITY = ["-c", "user.name=test", "-c", "user.email=test@example.com"]


def _git_commit(root):
    """Initialise a git repository with one commit, identity set once via -c flags."""
    subprocess.run(["git", *GIT_IDENTITY, "init"], cwd=root, check=True, capture_output=True)
    (root / "README.md").write_text("test\n")
    subprocess.run(["git", *GIT_IDENTITY, "add", "README.md"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", *GIT_IDENTITY, "commit", "-m", "init"], cwd=root, check=True, capture_output=True)


class ChangeState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp_root = Path(tempfile.mkdtemp())
        cls.addClassCleanup(shutil.rmtree, tmp_root, True)
        cls.root = tmp_root / "proj"
        cls.root.mkdir()
        cls.home = Path(tempfile.mkdtemp())
        cls.addClassCleanup(shutil.rmtree, cls.home, True)
        env = dict(os.environ, OPENSPEC_TELEMETRY="0")
        subprocess.run(["openspec", "init", "--tools", "none", str(cls.root)], check=True, capture_output=True, env=env)
        ch = cls.root / "openspec" / "changes" / "add-ping"
        (ch / "reports").mkdir(parents=True)
        (ch / "proposal.md").write_text("# Add ping\n\n## Why\nOperators need a liveness check before routing traffic.\n\n## What Changes\n- Add ping.\n")
        open_tasks = ["1.2", "1.3", "1.4", "1.5", "1.6"]
        (ch / "tasks.md").write_text("## 1. Ping\n- [x] 1.1 Add handler\n" + "".join(f"- [ ] {n} Step\n" for n in open_tasks))
        rejected = "## Review round 1\nVerdict: NOT COMPLIANT\nMissing: scenario\n"
        reports = {
            "1.2": "# Report 1.2\nStatus: DONE\nVerdict: DONE\n",
            "1.3": "# Report 1.3\nStatus: DONE\n" + rejected,
            "1.4": "# Report 1.4\nStatus: DONE\n" + rejected + "## Attempt 2\nStatus: DONE\n",
            "1.5": "# Report 1.5\nStatus: DONE\n" + rejected + "## Attempt 2\nStatus: DONE\n## Review round 2\nVerdict: COMPLIANT\n",
        }
        reports["1.7"] = "# Report 1.7\n## Attempt 2\nStatus: DONE\n# Report 1.7\nStatus: DONE\n" + rejected
        open_tasks.append("1.7")
        (ch / "tasks.md").write_text("## 1. Ping\n- [x] 1.1 Add handler\n" + "".join(f"- [ ] {n} Step\n" for n in open_tasks))
        for n, text in reports.items():
            (ch / "reports" / f"{n}.md").write_text(text)
        (ch / "waves.md").write_text("wave 1: 1.1\nwave 2: " + " ".join(open_tasks) + "\n")
        cls.state = S.read_state(cls.root, "add-ping", home=cls.home)

    def test_done_and_open(self):
        self.assertEqual(self.state["tasks_done"], ["1.1"])
        self.assertEqual(self.state["tasks_open"], ["1.2", "1.3", "1.4", "1.5", "1.6", "1.7"])

    def test_awaiting_review_without_verdict_or_after_new_attempt(self):
        self.assertEqual(self.state["awaiting_review"], ["1.2", "1.4", "1.7"])

    def test_last_verdict_decides(self):
        self.assertEqual(self.state["needs_fix"], ["1.3"])
        self.assertEqual(self.state["ready_to_accept"], ["1.5"])

    def test_current_wave(self):
        self.assertEqual(self.state["current_wave"], 2)

    def test_openspec_status_from_external_root(self):
        self.assertEqual(self.state["openspec_status"]["changeName"], "add-ping")


class MemoryFields(unittest.TestCase):
    def _fixture(self, git=False, decisions=False):
        tmp_root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp_root, True)
        root = tmp_root / "proj"
        root.mkdir()
        if git:
            _git_commit(root)
        ch = root / "openspec" / "changes" / "add-ping"
        ch.mkdir(parents=True)
        if decisions:
            (ch / "decisions.md").write_text("# Decisions\n")
        home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, home, True)
        return root, home

    def test_decisions_and_synced_commit_present(self):
        root, home = self._fixture(git=True, decisions=True)
        state_dir = home / ".openviking" / "sync-state"
        state_dir.mkdir(parents=True)
        (state_dir / f"{root.resolve().name}.json").write_text(json.dumps({"synced_commit": "abc123"}))
        state = S.read_state(root, "add-ping", run_openspec=False, home=home)
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True).stdout.strip()
        self.assertEqual(state["decisions"], str((root / "openspec" / "changes" / "add-ping" / "decisions.md").resolve()))
        self.assertEqual(state["synced_commit"], "abc123")
        self.assertEqual(state["head"], head)

    def test_head_none_without_git_repository(self):
        root, home = self._fixture(git=False, decisions=True)
        # GIT_CEILING_DIRECTORIES stops git from finding a repository above root,
        # so the result is independent of where the OS places temp directories.
        with patch.dict(os.environ, {"GIT_CEILING_DIRECTORIES": str(root.parent)}):
            state = S.read_state(root, "add-ping", run_openspec=False, home=home)
        self.assertIsNone(state["head"])

    def test_missing_decisions_and_state_file(self):
        root, home = self._fixture(git=False, decisions=False)
        state = S.read_state(root, "add-ping", run_openspec=False, home=home)
        self.assertIsNone(state["decisions"])
        self.assertIsNone(state["synced_commit"])

    def test_invalid_json_state_file(self):
        root, home = self._fixture(git=False, decisions=False)
        state_dir = home / ".openviking" / "sync-state"
        state_dir.mkdir(parents=True)
        (state_dir / f"{root.resolve().name}.json").write_text("not json")
        state = S.read_state(root, "add-ping", run_openspec=False, home=home)
        self.assertIsNone(state["synced_commit"])

    def test_decisions_is_absolute_for_relative_root(self):
        root, home = self._fixture(git=False, decisions=True)
        cwd = Path.cwd()
        self.addCleanup(os.chdir, cwd)
        os.chdir(root.parent)
        state = S.read_state(Path(root.name), "add-ping", run_openspec=False, home=home)
        self.assertTrue(Path(state["decisions"]).is_absolute())
        self.assertEqual(state["decisions"], str((root / "openspec" / "changes" / "add-ping" / "decisions.md").resolve()))


class ResumeCommand(unittest.TestCase):
    def test_text_names_scoped_find_and_trust_rule(self):
        text = Path("commands/resume.md").read_text()
        self.assertIn("read the decisions.md it names", text)
        self.assertIn(
            "run one find with target_uri viking://resources/<project>/specs/openspec/changes/$ARGUMENTS before any other memory call",
            text,
        )
        self.assertIn("when synced_commit differs from head, trust the files", text)


if __name__ == "__main__":
    unittest.main()
