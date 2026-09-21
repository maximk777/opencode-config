import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
import os
import shutil
import subprocess
import tempfile
import unittest

from workspace_helpers import create_workspace, run_check, run_generate

CHECK = REPO / "kits/workspace/tools/check.py"
KIT_MANIFEST = json.loads((REPO / "kits/workspace/kit.json").read_text(encoding="utf-8"))
UI_PROFILE = REPO / "kits/workspace/.agents/profiles/ui-migration"

EPIC = "".join(
    "## %s\n\nx\n\n" % s
    for s in ("Goal", "Scope", "Success criteria", "Out of scope", "Open questions", "Target users", "Product")
)
STORY_BODY = (
    "\n## Goal\n\nx\n\n## Scope\n\nx\n\n## Acceptance criteria\n\nx\n\n## Verification\n\nx\n"
    "\n## Out of scope\n\nx\n\n## Open questions\n\nNone.\n"
)
MAP_DOC = (
    "# Map of operations\n\n<!-- map:screens:begin -->\n<!-- map:screens:end -->\n\n"
    "## Legacy trace\n\n| Legacy group | Legacy item | Legacy route | Target |\n|---|---|---|---|\n"
    "| g | documents | /docs | screen:operations/operations/documents |\n"
    "| g | report | /report | screen:operations/operations/report |\n"
)

RAISING_REMAINING = '''

def remaining(ctx):
    raise RuntimeError("boom")
'''


def screen(slug, story=""):
    return (
        "---\nkey: screen:operations/operations/%s\nroute: /%s\nkind: place\nsection: s\nparent:\naccess: a\n"
        "label: L\nwave: 1\nstory:%s\n---\n\n## Transitions\n\n| Action | Target |\n|---|---|\n"
        % (slug, slug, " " + story if story else "")
    )


def ui_story(slug, scope):
    return (
        "---\nkey: story:operations/operations/%s\ntype: story\nwave: 1\ntracker:\nscope: [%s]\ndepends: []\n"
        "repos: []\ndecisions: []\nmockups: []\n---\n%s" % (slug, ", ".join(scope), STORY_BODY)
    )


def approvals(*stages):
    return [{"stage": stage, "by": "owner", "date": "2026-09-01"} for stage in stages]

BROKEN_RULE = '''from wslib import common


def broken(ctx):
    raise RuntimeError("boom")


RULES = [("zz-broken", broken)]
'''


class FreshWorkspace(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.ws = create_workspace(self.tmp)

    def tearDown(self):
        self._tmp.cleanup()

    def test_fresh_workspace_passes(self):
        stamp = json.loads((self.ws / ".agents/kit.json").read_text(encoding="utf-8"))
        self.assertEqual(stamp["version"], KIT_MANIFEST["version"])
        for rel in KIT_MANIFEST["templated"]:
            self.assertNotIn("{{", (self.ws / rel).read_text(encoding="utf-8"), rel)
        code, lines, stderr = run_check(self.ws)
        self.assertEqual((code, lines, stderr), (0, [], ""))

    def test_fresh_workspace_is_generated(self):
        result = run_generate(self.ws)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("generated: 0 files changed", result.stdout)

    def test_broken_json_exits_1(self):
        (self.ws / "repos.json").write_text("{broken", encoding="utf-8")
        code, lines, stderr = run_check(self.ws)
        self.assertEqual(code, 1, (lines, stderr))
        self.assertTrue(
            any(line.startswith("repos.json:") and " json-shape " in line for line in lines), lines
        )
        self.assertNotIn("Traceback", stderr)

    def test_outside_workspace_exits_2(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        result = subprocess.run(
            [sys.executable, str(CHECK)], cwd=empty, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_internal_error_exits_2(self):
        (self.ws / "tools/wslib/rules_zz_broken.py").write_text(BROKEN_RULE, encoding="utf-8")
        code, lines, stderr = run_check(self.ws)
        self.assertEqual(code, 2, (lines, stderr))
        self.assertIn("internal error", stderr)

    def test_committed_workspace_passes(self):
        # Isolate from the developer's global git config (signing, identity).
        env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull}
        git = [
            "git",
            "-c", "commit.gpgsign=false",
            "-c", "user.name=test",
            "-c", "user.email=test@example.com",
        ]
        subprocess.run(git + ["add", "-A"], cwd=self.ws, env=env, check=True, capture_output=True)
        subprocess.run(
            git + ["commit", "-q", "-m", "init"], cwd=self.ws, env=env, check=True, capture_output=True
        )
        code, lines, stderr = run_check(self.ws)
        self.assertEqual((code, lines, stderr), (0, [], ""))


def run_check_args(cwd, *args):
    result = subprocess.run(
        [sys.executable, str(CHECK), *args], cwd=cwd, capture_output=True, text=True
    )
    return result.returncode, result.stdout.splitlines(), result.stderr


class RemainingOption(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.ws = create_workspace(self.tmp)
        target = self.ws / ".agents/profiles/ui-migration"
        if not (target / "profile.json").is_file():
            shutil.copytree(str(UI_PROFILE), str(target), dirs_exist_ok=True)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text):
        path = self.ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_fresh_workspace_prints_nothing(self):
        self.assertEqual(run_check_args(self.ws, "--remaining"), (0, [], ""))

    def test_remaining_never_fails(self):
        (self.ws / "repos.json").write_text("{broken", encoding="utf-8")
        self.assertEqual(run_check_args(self.ws)[0], 1)
        code, lines, stderr = run_check_args(self.ws, "--remaining")
        self.assertEqual(code, 0, (lines, stderr))
        self.assertFalse(any(" json-shape " in line for line in lines), lines)

    def test_uncovered_screen_listed(self):
        # Domain operations of project operations, at stage decomposition: the report screen is in the
        # stream scope but in no story's scope.
        domain = "projects/operations/domains/operations"
        self.write(domain + "/map/documents.md", screen("documents", "story:operations/operations/documents"))
        self.write(domain + "/map/report.md", screen("report"))
        self.write(domain + "/MAP.md", MAP_DOC)
        self.write(domain + "/streams/s/epic.md", EPIC)
        self.write(domain + "/streams/s/stream.json", json.dumps({
            "key": "stream:operations/operations/s",
            "profile": "ui-migration",
            "stage": "decomposition",
            "scope": ["screen:operations/operations/documents", "screen:operations/operations/report"],
            "approvals": approvals("goal", "map"),
        }) + "\n")
        self.write(domain + "/streams/s/stories/documents/story.md",
                   ui_story("documents", ["screen:operations/operations/documents"]))
        code, lines, stderr = run_check_args(self.ws, "--remaining")
        self.assertEqual(code, 0, (lines, stderr))
        coverage = [l for l in lines
                    if l.startswith("stream:operations/operations/s decomposition two_way_coverage: ")]
        self.assertEqual(len(coverage), 1, lines)
        self.assertIn("screen:operations/operations/report", coverage[0])

    def test_outside_workspace_exits_2(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        code, _lines, stderr = run_check_args(empty, "--remaining")
        self.assertEqual(code, 2, stderr)

    def test_internal_error_exits_0(self):
        with (self.ws / "tools/wslib/rules_lifecycle.py").open("a", encoding="utf-8") as fh:
            fh.write(RAISING_REMAINING)
        # The workspace copy of check.py imports the patched wslib; the kit copy would not.
        result = subprocess.run(
            [sys.executable, "tools/check.py", "--remaining"], cwd=self.ws, capture_output=True, text=True
        )
        code, lines, stderr = result.returncode, result.stdout.splitlines(), result.stderr
        self.assertEqual((code, lines), (0, []), stderr)
        self.assertIn("check: internal error:", stderr)

    def test_unknown_argument_exits_2_with_usage(self):
        code, _lines, stderr = run_check_args(self.ws, "--bogus")
        self.assertEqual(code, 2, stderr)
        self.assertIn("usage", stderr)


if __name__ == "__main__":
    unittest.main()
