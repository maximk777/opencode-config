"""Walk the repo-kit-install and repo-kit-update skill order over fixture repositories with tools/repo_kit.py."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from workspace_helpers import create_workspace  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "workspace-repo-kits"
REPOSITORY = "orders"
KIND = "svc"
ENTRY = {"name": REPOSITORY, "kit": {"kind": KIND, "params": {"SERVICE": "orders"}}}
# Isolate from the developer's global git config (signing, identity).
GIT_ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull}
GIT = ["git", "-c", "commit.gpgsign=false", "-c", "user.name=test", "-c", "user.email=test@example.com"]


def git(repo, *args):
    result = subprocess.run(GIT + list(args), cwd=repo, env=GIT_ENV, capture_output=True, text=True)
    if result.returncode != 0:
        raise AssertionError("git %s failed:\n%s" % (" ".join(args), result.stderr))
    return result.stdout


def make_clone(td, fixture):
    """Copy a fixture repository into td, commit it on main and return its path."""
    clone = Path(td) / fixture
    shutil.copytree(FIXTURES / fixture, clone)
    git(clone, "init", "-q", "-b", "main")
    git(clone, "add", "-A")
    git(clone, "commit", "-q", "-m", "init")
    return clone


def use_kit(ws, fixture):
    """Put the fixture kit folder at .agents/repo-kits/svc of the workspace."""
    target = ws / ".agents" / "repo-kits" / KIND
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(FIXTURES / fixture, target)


def make_workspace(td, entries=None):
    ws = create_workspace(td)
    use_kit(ws, "kit")
    entries = [ENTRY] if entries is None else entries
    (ws / "repos.json").write_text(json.dumps({"repositories": entries}, indent=2) + "\n", encoding="utf-8")
    return ws


def tool(ws, *args):
    return subprocess.run(
        [sys.executable, "tools/repo_kit.py", *args], cwd=ws, capture_output=True, text=True
    )


def status(ws, clone):
    result = tool(ws, "status", REPOSITORY, str(clone))
    if result.returncode != 0:
        raise AssertionError("status exited %d: %s" % (result.returncode, result.stderr))
    return [tuple(line.split(" ", 1)) for line in result.stdout.splitlines()]


def render(ws, td):
    out = Path(td) / ("render-%d" % len(list(Path(td).glob("render-*"))))
    result = tool(ws, "render", REPOSITORY, str(out))
    if result.returncode != 0:
        raise AssertionError("render exited %d: %s" % (result.returncode, result.stderr))
    return out


def stamp(ws, clone):
    result = tool(ws, "stamp", REPOSITORY, str(clone))
    if result.returncode != 0:
        raise AssertionError("stamp exited %d: %s" % (result.returncode, result.stderr))


def copy_rendered(out, clone, path):
    target = clone / path
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(out / path, target)


def version_tuple(text):
    return tuple(int(part) for part in text.split("."))


def only(states, state):
    return all(item[0] == state for item in states)


def install_clean(test, td, ws):
    """Install kit 1.0.0 into the clean fixture on its branch, commit it as a merge would, return the clone."""
    clone = make_clone(td, "clean-repo")
    git(clone, "switch", "-q", "-c", "repo-kit-%s-1.0.0" % KIND)
    states = status(ws, clone)
    test.assertEqual(states, [
        ("absent", ".agents/AGENTS.md"),
        ("absent", ".agents/agents/implementer.md"),
        ("absent", ".agents/rules/go.md"),
        ("absent", ".agents/rules/old.md"),
    ])
    out = render(ws, td)
    for _, path in states:
        copy_rendered(out, clone, path)
    stamp(ws, clone)
    return clone


class Install(unittest.TestCase):
    def test_clean_repository(self):
        with tempfile.TemporaryDirectory() as td:
            ws = make_workspace(td)
            clone = install_clean(self, td, ws)
            states = status(ws, clone)
            self.assertTrue(states and only(states, "same"), states)
            data = json.loads((clone / ".agents/kit.json").read_text(encoding="utf-8"))
            self.assertEqual((data["kind"], data["version"], data["params"]), (KIND, "1.0.0", {"SERVICE": "orders"}))
            self.assertEqual(git(clone, "branch", "--show-current").strip(), "repo-kit-svc-1.0.0")

    def test_instrumented_repository(self):
        with tempfile.TemporaryDirectory() as td:
            ws = make_workspace(td)
            clone = make_clone(td, "instrumented-repo")
            hand_edited = (clone / ".agent/agents/implementer.md").read_bytes()
            git(clone, "switch", "-q", "-c", "repo-kit-%s-1.0.0" % KIND)
            self.assertTrue((clone / ".agent").is_dir() and not (clone / ".agents").exists())

            # The skill collects decisions from the status taken before the folder move.
            before = status(ws, clone)
            self.assertEqual(before, [
                ("absent", ".agents/AGENTS.md"),
                ("edited", ".agents/agents/implementer.md"),
                ("same", ".agents/rules/go.md"),
                ("absent", ".agents/rules/old.md"),
            ])
            decisions = {".agents/agents/implementer.md": "local"}

            git(clone, "mv", ".agent", ".agents")
            self.assertFalse((clone / ".agent").exists())
            out = render(ws, td)
            for state, path in before:
                if state == "edited" and decisions[path] == "local":
                    local = clone / ".agents/local" / path[len(".agents/"):]
                    local.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(clone / path), str(local))
                    copy_rendered(out, clone, path)
                elif state == "absent":
                    copy_rendered(out, clone, path)
            stamp(ws, clone)

            after = status(ws, clone)
            self.assertTrue(after and only(after, "same"), after)
            self.assertEqual((clone / ".agents/local/agents/implementer.md").read_bytes(), hand_edited)
            self.assertEqual(
                (clone / ".agents/agents/implementer.md").read_bytes(),
                (out / ".agents/agents/implementer.md").read_bytes(),
            )
            self.assertTrue((clone / ".agents/kit.json").is_file())
            self.assertFalse((clone / ".agent").exists())


class Update(unittest.TestCase):
    def test_update_to_1_1_0(self):
        with tempfile.TemporaryDirectory() as td:
            ws = make_workspace(td)
            clone = install_clean(self, td, ws)
            git(clone, "add", "-A")
            git(clone, "commit", "-q", "-m", "install kit")
            git(clone, "switch", "-q", "main")
            git(clone, "merge", "-q", "--ff-only", "repo-kit-svc-1.0.0")
            with (clone / ".agents/rules/go.md").open("a", encoding="utf-8") as fh:
                fh.write("- Team rule: vet before commit.\n")
            git(clone, "commit", "-q", "-am", "edit go rule")

            use_kit(ws, "kit-1.1.0")
            stamped = json.loads((clone / ".agents/kit.json").read_text(encoding="utf-8"))
            kit = json.loads((ws / ".agents/repo-kits/svc/kit.json").read_text(encoding="utf-8"))
            self.assertNotEqual((stamped["kind"], stamped["version"]), (kit["name"], kit["version"]))
            git(clone, "switch", "-q", "-c", "repo-kit-%s-%s" % (KIND, kit["version"]))

            states = status(ws, clone)
            self.assertEqual(states, [
                ("same", ".agents/AGENTS.md"),
                ("replaceable", ".agents/agents/implementer.md"),
                ("edited", ".agents/rules/go.md"),
                ("obsolete", ".agents/rules/old.md"),
                ("absent", ".agents/skills/verify/SKILL.md"),
            ])
            decisions = {".agents/rules/go.md": "kit"}
            out = render(ws, td)
            for state, path in states:
                if state in ("replaceable", "absent") or (state == "edited" and decisions[path] == "kit"):
                    copy_rendered(out, clone, path)
                elif state == "obsolete":
                    (clone / path).unlink()
            stamp(ws, clone)

            new_stamp = json.loads((clone / ".agents/kit.json").read_text(encoding="utf-8"))
            self.assertEqual(new_stamp["version"], "1.1.0")
            after = status(ws, clone)
            self.assertTrue(after and only(after, "same"), after)
            self.assertNotIn(".agents/rules/old.md", [path for _, path in after])


class Stops(unittest.TestCase):
    def test_both_folders_detectable(self):
        with tempfile.TemporaryDirectory() as td:
            clone = Path(td) / "clone"
            shutil.copytree(FIXTURES / "instrumented-repo", clone)
            (clone / ".agents").mkdir()
            self.assertTrue((clone / ".agent").is_dir() and (clone / ".agents").is_dir())

    def test_stamp_newer_than_kit_detectable(self):
        with tempfile.TemporaryDirectory() as td:
            ws = make_workspace(td)
            use_kit(ws, "kit-1.1.0")
            clone = Path(td) / "clone"
            clone.mkdir()
            stamp(ws, clone)
            use_kit(ws, "kit")
            stamped = json.loads((clone / ".agents/kit.json").read_text(encoding="utf-8"))
            kit = json.loads((ws / ".agents/repo-kits/svc/kit.json").read_text(encoding="utf-8"))
            self.assertGreater(version_tuple(stamped["version"]), version_tuple(kit["version"]))

    def test_render_without_kit_exits_2(self):
        with tempfile.TemporaryDirectory() as td:
            ws = make_workspace(td, entries=[{"name": REPOSITORY}])
            out = Path(td) / "out"
            result = tool(ws, "render", REPOSITORY, str(out))
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
