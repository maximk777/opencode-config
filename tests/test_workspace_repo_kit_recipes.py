"""Repository kit recipes from repo-kit-install, run as the skill text says, must equal tools/repo_kit.py output."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TOOL = REPO / "kits/workspace/tools/repo_kit.py"
SKILL = REPO / "kits/workspace/.agents/skills/repo-kit-install/SKILL.md"

KIT = {
    "name": "mfe",
    "version": "1.2.3",
    "target": ".agents",
    "params": {
        "MFE": {"description": "Micro-frontend service name", "pattern": "mfe-[a-z0-9-]+"},
        "BFF": {"description": "Backend-for-frontend service name", "pattern": "bff-[a-z0-9-]+"},
    },
}
ENTRY = {
    "name": "abs-operations",
    "forge": "gitlab",
    "default_branch": "main",
    "kit": {"kind": "mfe", "params": {"MFE": "mfe-abs-operations", "BFF": "bff-abs-operations"}},
}
# Byte-level edge cases the recipe promises to keep: CRLF, no final newline, non-ASCII text.
FILES = {
    "AGENTS.md": "# __MFE__\n\nBackend: __BFF__.\r\nСервис __MFE__ и __BFF__\n".encode("utf-8"),
    "rules/api.md": b"Call __BFF__ from __MFE__ only",
    "skills/screen/SKILL.md": b"---\nname: screen\n---\nScreens of __MFE__ talk to __BFF__.\n",
}
PARAM_TOKENS = {"<NAME1>": "MFE", "<value1>": "mfe-abs-operations",
                "<NAME2>": "BFF", "<value2>": "bff-abs-operations"}
NO_PARAMS_LINE = re.compile(r"For a kit without parameters that line is `([^`]+)`")


def digest_tool():
    if shutil.which("shasum"):
        return "shasum -a 256"
    if shutil.which("sha256sum"):
        return "sha256sum"
    return None


def section(title):
    text = SKILL.read_text(encoding="utf-8")
    start = text.index("\n## %s\n" % title)
    end = text.find("\n## ", start + 1)
    return text[start:] if end == -1 else text[start:end]


def first_block(title):
    """Return the first fenced code block of a skill section, dedented: the generic command template."""
    match = re.search(r"^([ ]*)```[a-z]*\n(.*?)^\1```", section(title), re.S | re.M)
    return textwrap.dedent(match.group(2))


def fill(case, template, values):
    tool = digest_tool()
    for key, value in {**PARAM_TOKENS, **values}.items():
        template = template.replace(key, value)
    if tool != "shasum -a 256":
        template = template.replace("shasum -a 256", tool)
    left = re.findall(r"<(?:NAME\d|value\d|kitdir|out|clone|base|kind|version|ws)>", template)
    case.assertEqual(left, [], "unfilled placeholders in:\n%s" % template)
    return template


def sh(case, command, cwd=None):
    result = subprocess.run(["/bin/sh", "-c", command], cwd=cwd, capture_output=True)
    case.assertEqual(result.returncode, 0, "command failed:\n%s\nstderr:\n%s" % (command, result.stderr.decode()))
    return result.stdout


def make_workspace(td, kit=KIT, entry=ENTRY, files=FILES):
    ws = Path(td) / "ws"
    kitdir = ws / ".agents/repo-kits/mfe"
    (kitdir / "files").mkdir(parents=True)
    for rel, content in files.items():
        path = kitdir / "files" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    (kitdir / "kit.json").write_text(json.dumps(kit, indent=2) + "\n", encoding="utf-8")
    (ws / "repos.json").write_text(json.dumps({"repositories": [entry]}, indent=2) + "\n", encoding="utf-8")
    return ws, kitdir


def run_tool(case, ws, *args):
    result = subprocess.run([sys.executable, str(TOOL), *args], cwd=ws, capture_output=True)
    case.assertEqual(result.returncode, 0, result.stderr.decode())
    return result.stdout


def tree_bytes(root):
    root = Path(root)
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def recipe_render(case, kitdir, out):
    step = next(line for line in section("Recipe: render").splitlines() if line.startswith("2. Placeholders."))
    check = fill(case, re.search(r"`([^`]+)`", step).group(1), {"<kitdir>": str(kitdir)})
    case.assertEqual(sh(case, check).decode().split(), ["__BFF__", "__MFE__"])
    sh(case, fill(case, first_block("Recipe: render"), {"<kitdir>": str(kitdir), "<out>": str(out)}))


def stamp_template(params):
    """Return the stamp recipe block, with the parameter line swapped as the skill says for a kit without parameters."""
    block = first_block("Recipe: stamp")
    if params:
        return block
    lines = block.splitlines(keepends=True)
    index = next(i for i, line in enumerate(lines) if '"params": {\'' in line)
    indent = lines[index][:len(lines[index]) - len(lines[index].lstrip())]
    lines[index] = indent + NO_PARAMS_LINE.search(section("Recipe: stamp")).group(1) + "\n"
    return "".join(lines)


def assert_stamp_equals_tool(case, td, ws, out, params=True):
    recipe_clone, tool_clone = Path(td) / "recipe-clone", Path(td) / "tool-clone"
    recipe_clone.mkdir()
    tool_clone.mkdir()
    sh(case, fill(case, stamp_template(params), {"<clone>": str(recipe_clone), "<out>": str(out),
                                                 "<kind>": "mfe", "<version>": "1.2.3"}))
    run_tool(case, ws, "stamp", "abs-operations", str(tool_clone))
    recipe = (recipe_clone / ".agents/kit.json").read_bytes()
    case.assertEqual(recipe, (tool_clone / ".agents/kit.json").read_bytes())
    return json.loads(recipe.decode("utf-8"))


@unittest.skipIf(digest_tool() is None, "neither shasum nor sha256sum is installed, the recipes cannot compute digests")
class RepoKitRecipes(unittest.TestCase):
    def test_render_and_stamp_equal_tool(self):
        with tempfile.TemporaryDirectory() as td:
            ws, kitdir = make_workspace(td)
            recipe_out, tool_out = Path(td) / "recipe-out", Path(td) / "tool-out"
            recipe_out.mkdir()
            recipe_render(self, kitdir, recipe_out)
            run_tool(self, ws, "render", "abs-operations", str(tool_out))
            rendered = tree_bytes(tool_out)
            self.assertEqual(sorted(rendered), [".agents/AGENTS.md", ".agents/rules/api.md",
                                                ".agents/skills/screen/SKILL.md"])
            self.assertEqual(tree_bytes(recipe_out), rendered)
            assert_stamp_equals_tool(self, td, ws, recipe_out)

    def test_stamp_without_params_equals_tool(self):
        with tempfile.TemporaryDirectory() as td:
            kit = {**KIT, "params": {}}
            entry = {**ENTRY, "kit": {"kind": "mfe", "params": {}}}
            ws, _ = make_workspace(td, kit=kit, entry=entry, files={"AGENTS.md": b"# plain\n"})
            out = Path(td) / "out"
            run_tool(self, ws, "render", "abs-operations", str(out))
            stamp = assert_stamp_equals_tool(self, td, ws, out, params=False)
            self.assertEqual(stamp["params"], {})
            self.assertEqual(list(stamp["files"]), [".agents/AGENTS.md"])

    def test_stamp_without_files_equals_tool(self):
        with tempfile.TemporaryDirectory() as td:
            ws, _ = make_workspace(td, files={})
            out = Path(td) / "out"
            out.mkdir()
            run_tool(self, ws, "render", "abs-operations", str(out))
            self.assertEqual(tree_bytes(out), {})
            stamp = assert_stamp_equals_tool(self, td, ws, out)
            self.assertEqual(stamp["files"], {})

    def test_status_states_equal_tool(self):
        with tempfile.TemporaryDirectory() as td:
            # rules/old.md and rules/gone.md leave the kit after stamping: obsolete and removed-edited.
            files = {**FILES, "rules/old.md": b"Old rule of __MFE__\n", "rules/gone.md": b"Gone rule\n"}
            ws, kitdir = make_workspace(td, files=files)
            clone = Path(td) / "clone"
            run_tool(self, ws, "render", "abs-operations", str(clone))
            run_tool(self, ws, "stamp", "abs-operations", str(clone))
            (kitdir / "files/rules/old.md").unlink()
            (kitdir / "files/rules/gone.md").unlink()
            with (clone / ".agents/rules/api.md").open("ab") as handle:
                handle.write(b"\nLocal note.\n")
            with (clone / ".agents/rules/gone.md").open("ab") as handle:
                handle.write(b"Local change.\n")
            (clone / ".agents/notes.md").write_bytes(b"Repository notes\n")
            (clone / ".agents/local").mkdir()
            (clone / ".agents/local/own.md").write_bytes(b"Repository-only rule\n")
            out = Path(td) / "out"
            out.mkdir()
            recipe_render(self, kitdir, out)

            recipe = sh(self, fill(self, first_block("Recipe: status"), {"<out>": str(out), "<clone>": str(clone),
                                                                        "<base>": str(clone / ".agents")}))
            tool = run_tool(self, ws, "status", "abs-operations", str(clone))
            self.assertEqual(tool.decode().splitlines(), [
                "same .agents/AGENTS.md",
                "foreign .agents/notes.md",
                "edited .agents/rules/api.md",
                "removed-edited .agents/rules/gone.md",
                "obsolete .agents/rules/old.md",
                "same .agents/skills/screen/SKILL.md",
            ])
            self.assertEqual(recipe, tool)


if __name__ == "__main__":
    unittest.main()
