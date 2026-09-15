import contextlib
import errno
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
TOOL = REPO / "kits/workspace/tools/repo_kit.py"
sys.path.insert(0, str(REPO / "kits/workspace/tools"))

from wslib import repo_kits  # noqa: E402

MFE_KIT = {
    "name": "mfe",
    "version": "1.0.0",
    "target": ".agents",
    "params": {
        "MFE": {"description": "Micro-frontend service name", "pattern": "mfe-[a-z0-9-]+"},
        "BFF": {"description": "Backend-for-frontend service name", "pattern": "bff-[a-z0-9-]+"},
    },
}
MFE_ENTRY = {
    "name": "abs-operations",
    "kit": {"kind": "mfe", "params": {"MFE": "mfe-abs-operations", "BFF": "bff-abs-operations"}},
}


def sha(content):
    return hashlib.sha256(content).hexdigest()


def write_files(base, files):
    for rel, content in files.items():
        path = Path(base) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)


def make_workspace(td, files, entries=None):
    """Create a workspace root under td with the mfe kit and repos.json; return its path."""
    root = Path(td) / "ws"
    base = root / ".agents" / "repo-kits" / "mfe"
    base.mkdir(parents=True)
    (base / "kit.json").write_text(json.dumps(MFE_KIT, indent=2), encoding="utf-8")
    write_files(base / "files", files)
    entries = [MFE_ENTRY] if entries is None else entries
    (root / "repos.json").write_text(json.dumps({"repositories": entries}), encoding="utf-8")
    return root


def run_tool(root, *args):
    return subprocess.run([sys.executable, str(TOOL), *args], cwd=root, capture_output=True, text=True)


def tree(path):
    path = Path(path)
    return sorted(p.relative_to(path).as_posix() for p in path.rglob("*") if p.is_file())


class Render(unittest.TestCase):
    def test_substitution(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_workspace(td, {"agents/screen.md": "Service __MFE__\n", "AGENTS.md": "BFF __BFF__\r\n"})
            out = Path(td) / "out"
            result = run_tool(root, "render", "abs-operations", str(out))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(tree(out), [".agents/AGENTS.md", ".agents/agents/screen.md"])
            screen = (out / ".agents/agents/screen.md").read_text(encoding="utf-8")
            self.assertIn("Service mfe-abs-operations", screen)
            self.assertNotIn("__MFE__", screen)
            self.assertEqual((out / ".agents/AGENTS.md").read_bytes(), b"BFF bff-abs-operations\r\n")

    def test_two_runs_are_identical(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_workspace(td, {"agents/screen.md": "Service __MFE__\n", "rules/a.md": "__BFF__"})
            first, second = Path(td) / "one", Path(td) / "two"
            self.assertEqual(run_tool(root, "render", "abs-operations", str(first)).returncode, 0)
            self.assertEqual(run_tool(root, "render", "abs-operations", str(second)).returncode, 0)
            self.assertEqual(tree(first), tree(second))
            for rel in tree(first):
                self.assertEqual((first / rel).read_bytes(), (second / rel).read_bytes())

    def assert_rejected(self, root, out, *names):
        result = run_tool(root, "render", "abs-operations", str(out))
        self.assertEqual(result.returncode, 2)
        self.assertFalse(out.exists())
        self.assertEqual(len(result.stderr.strip().splitlines()), 1, result.stderr)
        for name in names:
            self.assertIn(name, result.stderr)

    def test_entry_without_kit(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_workspace(td, {"AGENTS.md": "x\n"}, entries=[{"name": "abs-operations"}])
            self.assert_rejected(root, Path(td) / "out", "abs-operations")

    def test_invalid_kit_param(self):
        with tempfile.TemporaryDirectory() as td:
            entry = {"name": "abs-operations", "kit": {"kind": "mfe", "params": {"MFE": "bad", "BFF": "bff-x"}}}
            root = make_workspace(td, {"AGENTS.md": "x\n"}, entries=[entry])
            self.assert_rejected(root, Path(td) / "out", "MFE")

    def test_unknown_repository(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_workspace(td, {"AGENTS.md": "x\n"}, entries=[])
            self.assert_rejected(root, Path(td) / "out", "abs-operations")

    def test_undeclared_placeholder(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_workspace(td, {"AGENTS.md": "__MFE__\n", "z.md": "__OTHER__\n"})
            self.assert_rejected(root, Path(td) / "out", "OTHER")

    def test_out_is_a_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_workspace(td, {"AGENTS.md": "__MFE__\n"})
            out = Path(td) / "out"
            out.write_text("taken\n", encoding="utf-8")
            result = run_tool(root, "render", "abs-operations", str(out))
            self.assertEqual(result.returncode, 2)
            self.assertEqual(out.read_text(encoding="utf-8"), "taken\n")
            self.assertEqual(len(result.stderr.strip().splitlines()), 1, result.stderr)
            self.assertIn(str(out), result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_os_error_without_filename(self):
        spec = importlib.util.spec_from_file_location("repo_kit_cli", TOOL)
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        with tempfile.TemporaryDirectory() as td:
            root = make_workspace(td, {"AGENTS.md": "__MFE__\n"})
            error = OSError(errno.ENOSPC, "No space left on device")
            stderr = io.StringIO()
            cwd = os.getcwd()
            os.chdir(root)
            try:
                with mock.patch.object(tool.repo_kits, "render", side_effect=error), \
                        contextlib.redirect_stderr(stderr):
                    code = tool.main(["render", "abs-operations", str(Path(td) / "out")])
            finally:
                os.chdir(cwd)
            self.assertEqual(code, 2)
            self.assertEqual(stderr.getvalue(), "repo_kit: No space left on device\n")


class Status(unittest.TestCase):
    FILES = {
        "rules/api-client.md": "client __MFE__\n",
        "skills/add-table/SKILL.md": "add table v2 __BFF__\n",
        "agents/screen.md": "Service __MFE__\n",
        "agents/new.md": "new\n",
    }

    def test_states(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_workspace(td, self.FILES)
            clone = Path(td) / "clone"
            installed_client = b"client mfe-abs-operations\n"
            old_skill = b"add table v1 bff-abs-operations\n"
            old_rule = b"old rule\n"
            old_edited = b"old edited\n"
            write_files(clone / ".agents", {
                "rules/api-client.md": b"client mfe-abs-operations\nteam change\n",
                "skills/add-table/SKILL.md": old_skill,
                "agents/screen.md": "Service mfe-abs-operations\n",
                "rules/old.md": old_rule,
                "rules/old-edited.md": old_edited + b"more\n",
                "rules/team-notes.md": "notes\n",
                "local/rules/mine.md": "mine\n",
            })
            stamp = {
                "kind": "mfe",
                "version": "0.9.0",
                "params": MFE_ENTRY["kit"]["params"],
                "files": {
                    ".agents/rules/api-client.md": sha(installed_client),
                    ".agents/skills/add-table/SKILL.md": sha(old_skill),
                    ".agents/rules/old.md": sha(old_rule),
                    ".agents/rules/old-edited.md": sha(old_edited),
                    ".agents/rules/gone.md": sha(b"gone\n"),
                },
            }
            (clone / ".agents/kit.json").write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
            result = run_tool(root, "status", "abs-operations", str(clone))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(), [
                "absent .agents/agents/new.md",
                "same .agents/agents/screen.md",
                "edited .agents/rules/api-client.md",
                "removed-edited .agents/rules/old-edited.md",
                "obsolete .agents/rules/old.md",
                "foreign .agents/rules/team-notes.md",
                "replaceable .agents/skills/add-table/SKILL.md",
            ])

    def test_before_folder_move(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_workspace(td, {"agents/arm-bff-implementer.md": "implement __BFF__\n"})
            clone = Path(td) / "clone"
            write_files(clone / ".agent", {"agents/arm-bff-implementer.md": "team version\n"})
            result = run_tool(root, "status", "abs-operations", str(clone))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(), ["edited .agents/agents/arm-bff-implementer.md"])

    def test_missing_clone(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_workspace(td, {"AGENTS.md": "x\n"})
            result = run_tool(root, "status", "abs-operations", str(Path(td) / "nope"))
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertEqual(len(result.stderr.strip().splitlines()), 1, result.stderr)

    def test_invalid_entry(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_workspace(td, {"AGENTS.md": "x\n"}, entries=[{"name": "abs-operations"}])
            clone = Path(td) / "clone"
            clone.mkdir()
            result = run_tool(root, "status", "abs-operations", str(clone))
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertEqual(len(result.stderr.strip().splitlines()), 1, result.stderr)

    @unittest.skipIf(os.name != "posix" or os.geteuid() == 0, "needs a non-root POSIX user")
    def test_unreadable_clone_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_workspace(td, {"AGENTS.md": "x\n"})
            clone = Path(td) / "clone"
            write_files(clone / ".agents", {"AGENTS.md": "y\n"})
            locked = clone / ".agents/AGENTS.md"
            locked.chmod(0)
            try:
                result = run_tool(root, "status", "abs-operations", str(clone))
            finally:
                locked.chmod(0o644)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertEqual(len(result.stderr.strip().splitlines()), 1, result.stderr)
            self.assertIn(str(locked), result.stderr)
            self.assertNotIn("Traceback", result.stderr)


class Stamp(unittest.TestCase):
    def test_stamp_content(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_workspace(td, {"agents/screen.md": "Service __MFE__\n", "AGENTS.md": "__BFF__\n"})
            clone = Path(td) / "clone"
            clone.mkdir()
            result = run_tool(root, "stamp", "abs-operations", str(clone))
            self.assertEqual(result.returncode, 0, result.stderr)
            text = (clone / ".agents/kit.json").read_text(encoding="utf-8")
            self.assertEqual(text, repo_kits.stamp_text(root, "abs-operations"))
            data = json.loads(text)
            self.assertEqual(data["kind"], "mfe")
            self.assertEqual(data["version"], "1.0.0")
            self.assertEqual(data["params"], MFE_ENTRY["kit"]["params"])
            self.assertEqual(data["files"], {
                ".agents/AGENTS.md": sha(b"bff-abs-operations\n"),
                ".agents/agents/screen.md": sha(b"Service mfe-abs-operations\n"),
            })

    def test_missing_clone(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_workspace(td, {"AGENTS.md": "x\n"})
            clone = Path(td) / "nope"
            result = run_tool(root, "stamp", "abs-operations", str(clone))
            self.assertEqual(result.returncode, 2)
            self.assertFalse(clone.exists())
            self.assertEqual(len(result.stderr.strip().splitlines()), 1, result.stderr)

    def test_invalid_entry_writes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_workspace(td, {"AGENTS.md": "__NOPE__\n"})
            clone = Path(td) / "clone"
            clone.mkdir()
            result = run_tool(root, "stamp", "abs-operations", str(clone))
            self.assertEqual(result.returncode, 2)
            self.assertEqual(tree(clone), [])

    def test_write_error_reports_the_path(self):
        with tempfile.TemporaryDirectory() as td:
            root = make_workspace(td, {"AGENTS.md": "__MFE__\n"})
            clone = Path(td) / "clone"
            kit_json = clone / ".agents" / "kit.json"
            kit_json.mkdir(parents=True)
            result = run_tool(root, "stamp", "abs-operations", str(clone))
            self.assertEqual(result.returncode, 2)
            self.assertEqual(len(result.stderr.strip().splitlines()), 1, result.stderr)
            self.assertIn(str(kit_json), result.stderr)
            self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
