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
        (ch / "tasks.md").write_text("## 1. Ping\n- [x] 1.1 Add handler\n- [ ] 1.2 Add test\n- [ ] 1.3 Add docs\n")
        (ch / "reports" / "1.2.md").write_text("# Report 1.2\nStatus: DONE\n")
        (ch / "reports" / "1.3.md").write_text("# Report 1.3\nStatus: DONE\nVerdict: NOT COMPLIANT\n")
        (ch / "waves.md").write_text("wave 1: 1.1\nwave 2: 1.2 1.3\n")
        cls.state = S.read_state(cls.root, "add-ping")

    def test_done_and_open(self):
        self.assertEqual(self.state["tasks_done"], ["1.1"])
        self.assertEqual(self.state["tasks_open"], ["1.2", "1.3"])

    def test_awaiting_review(self):
        self.assertEqual(self.state["awaiting_review"], ["1.2"])

    def test_current_wave(self):
        self.assertEqual(self.state["current_wave"], 2)

    def test_openspec_status_from_external_root(self):
        self.assertEqual(self.state["openspec_status"]["changeName"], "add-ping")


if __name__ == "__main__":
    unittest.main()
