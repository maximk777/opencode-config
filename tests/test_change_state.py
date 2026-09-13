import importlib.machinery
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

S = importlib.machinery.SourceFileLoader("change_state", "bin/change-state").load_module()


class ChangeState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp()) / "proj"
        cls.root.mkdir()
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
        for n, text in reports.items():
            (ch / "reports" / f"{n}.md").write_text(text)
        (ch / "waves.md").write_text("wave 1: 1.1\nwave 2: " + " ".join(open_tasks) + "\n")
        cls.state = S.read_state(cls.root, "add-ping")

    def test_done_and_open(self):
        self.assertEqual(self.state["tasks_done"], ["1.1"])
        self.assertEqual(self.state["tasks_open"], ["1.2", "1.3", "1.4", "1.5", "1.6"])

    def test_awaiting_review_without_verdict_or_after_new_attempt(self):
        self.assertEqual(self.state["awaiting_review"], ["1.2", "1.4"])

    def test_last_verdict_decides(self):
        self.assertEqual(self.state["needs_fix"], ["1.3"])
        self.assertEqual(self.state["ready_to_accept"], ["1.5"])

    def test_current_wave(self):
        self.assertEqual(self.state["current_wave"], 2)

    def test_openspec_status_from_external_root(self):
        self.assertEqual(self.state["openspec_status"]["changeName"], "add-ping")


if __name__ == "__main__":
    unittest.main()
