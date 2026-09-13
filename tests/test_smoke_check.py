import importlib.machinery
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

S = importlib.machinery.SourceFileLoader("smoke_check", "bin/smoke-check").load_module()

BRIEF = "---\ntask: {task}\nfiles: {files}\ndepends:\nskeleton: yes\n---\n# Task {task}\n"


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def make_run(tmp, *, move_head=False, stray=False, checked=4, rejections=1, bad_commit=False, reset=True, specs_commit=True):
    run = Path(tmp)
    work, ch = run / "work", run / "specs" / "openspec" / "changes" / "smoke-change"
    (work / "pkg").mkdir(parents=True)
    (ch / "briefs").mkdir(parents=True)
    (ch / "reports").mkdir()
    (run / "specs" / "openspec" / "changes" / "archive").mkdir()
    (work / "go.mod").write_text("module smokeapp\n\ngo 1.24\n")
    (work / "pkg" / "a.go").write_text("package pkg\n")
    git(work, "init", "-q")
    git(work, "add", "-A")
    git(work, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "chore(smoke): init")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=work, capture_output=True, text=True).stdout.strip()
    (run / "HEAD.before").write_text(head + "\n")
    (ch / "briefs" / "1.1.md").write_text(BRIEF.format(task="1.1", files="pkg/a.go"))
    (work / "pkg" / "a.go").write_text("package pkg\n\nfunc A() int { return 1 }\n")
    git(work, "add", "--", "pkg/a.go")
    if stray:
        (work / "stray.txt").write_text("x")
        git(work, "add", "--", "stray.txt")
    if move_head:
        git(work, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "feat(pkg): add a")
    lines = [f"- [{'x' if i <= checked else ' '}] 1.{i} task" for i in range(1, 5)]
    (ch / "tasks.md").write_text("## 1. Smoke\n" + "\n".join(lines) + "\n")
    for i in range(rejections):
        (ch / "reports" / f"1.{i + 1}.md").write_text("Status: DONE\nVerdict: NOT COMPLIANT\nVerdict: COMPLIANT\n")
    (run / "events.log").write_text('{"tool":"phase_reset"}\n{"tool":"task"}\n' if reset else '{"tool":"task"}\n')
    (run / "specs" / "proposed-commits.txt").write_text("Added stuff\n" if bad_commit else "feat(pkg): add a\n")
    specs = run / "specs"
    git(specs, "init", "-q")
    for msg in ["docs(smoke): approved change", "docs(smoke): archive change"][: 2 if specs_commit else 1]:
        (specs / "log.txt").write_text(msg)
        git(specs, "add", "-A")
        git(specs, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", msg)
    return run


class SmokeCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def check(self, **kw):
        lines = S.run_checks(make_run(self.tmp, **kw), run_go_test=False)
        return "\n".join(lines)

    def test_passing_run(self):
        out = self.check()
        self.assertIn("head unchanged", out)
        self.assertIn("reviewer rejected: 1", out)
        self.assertIn("resumed after reset", out)
        self.assertIn("SMOKE PASS", out)

    def test_head_moved(self):
        self.assertIn("SMOKE FAIL", self.check(move_head=True))

    def test_stray_file_staged(self):
        out = self.check(stray=True)
        self.assertIn("outside briefs: stray.txt", out)
        self.assertIn("SMOKE FAIL", out)

    def test_unchecked_task(self):
        out = self.check(checked=3)
        self.assertIn("tasks checked: 3/4", out)
        self.assertIn("SMOKE FAIL", out)

    def test_no_rejection(self):
        self.assertIn("SMOKE FAIL", self.check(rejections=0))

    def test_specs_not_committed(self):
        out = self.check(specs_commit=False)
        self.assertIn("specs commits: 1", out)
        self.assertIn("SMOKE FAIL", out)

    def test_fix_round_without_reviewer_rejection_fails(self):
        run = make_run(self.tmp, rejections=0)
        with open(run / "events.log", "a") as f:
            f.write('{"description":"Fix task 1.3 trimmed empty"}\n')
        out = "\n".join(S.run_checks(run, run_go_test=False))
        self.assertIn("fix rounds dispatched: 1", out)
        self.assertIn("SMOKE FAIL", out)

    def test_bad_commit_message(self):
        self.assertIn("SMOKE FAIL", self.check(bad_commit=True))

    def test_archived_change_is_found(self):
        run = make_run(self.tmp)
        changes = run / "specs" / "openspec" / "changes"
        (changes / "smoke-change").rename(changes / "archive" / "2026-09-13-smoke-change")
        out = "\n".join(S.run_checks(run, run_go_test=False))
        self.assertIn("tasks checked: 4/4", out)
        self.assertIn("SMOKE PASS", out)

    def test_no_reset(self):
        self.assertIn("SMOKE FAIL", self.check(reset=False))


if __name__ == "__main__":
    unittest.main()
