import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))

import hashlib
import json
import tempfile
import unittest

from wslib import repo_kits

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


def write_kit(root, kind="mfe", kit=None, files=None):
    """Create .agents/repo-kits/<kind>/ with kit.json and files/ from a {relpath: bytes|str} map."""
    base = Path(root) / ".agents" / "repo-kits" / kind
    base.mkdir(parents=True, exist_ok=True)
    if kit is not None:
        text = kit if isinstance(kit, str) else json.dumps(kit, indent=2)
        (base / "kit.json").write_text(text, encoding="utf-8")
    for rel, content in (files or {}).items():
        path = base / "files" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, str):
            content = content.encode("utf-8")
        path.write_bytes(content)
    return base


def write_repos(root, entries):
    (Path(root) / "repos.json").write_text(json.dumps({"repositories": entries}, indent=2), encoding="utf-8")


def mfe_workspace(td, files=None, entries=None):
    root = Path(td)
    write_kit(root, kit=MFE_KIT, files=files if files is not None else {"AGENTS.md": "Service __MFE__\n"})
    write_repos(root, entries if entries is not None else [MFE_ENTRY])
    return root


class LoadKit(unittest.TestCase):
    def test_valid_kit_has_no_problems(self):
        with tempfile.TemporaryDirectory() as td:
            root = mfe_workspace(td)
            kit, problems = repo_kits.load_kit(root, "mfe")
            self.assertEqual(problems, [])
            self.assertEqual(kit, MFE_KIT)
            self.assertEqual(repo_kits.undeclared_placeholders(root, "mfe"), [])

    def test_missing_kit_json(self):
        with tempfile.TemporaryDirectory() as td:
            write_kit(td, files={"AGENTS.md": "x\n"})
            kit, problems = repo_kits.load_kit(td, "mfe")
            self.assertIsNone(kit)
            self.assertEqual(len(problems), 1)
            self.assertIn("kit.json", problems[0])

    def test_bad_json(self):
        with tempfile.TemporaryDirectory() as td:
            write_kit(td, kit="{not json")
            kit, problems = repo_kits.load_kit(td, "mfe")
            self.assertIsNone(kit)
            self.assertEqual(len(problems), 1)
            self.assertIn("not valid JSON", problems[0])

    def test_unreadable_kit_json_is_not_called_invalid_json(self):
        with tempfile.TemporaryDirectory() as td:
            base = write_kit(td)
            (base / "kit.json").mkdir()
            kit, problems = repo_kits.load_kit(td, "mfe")
            self.assertIsNone(kit)
            self.assertEqual(len(problems), 1)
            self.assertIn("cannot be read", problems[0])
            self.assertNotIn("JSON", problems[0])
            self.assertIn(".agents/repo-kits/mfe/kit.json cannot be read", problems[0])
            self.assertNotIn(str(td), problems[0])

    def test_non_utf8_kit_json_cannot_be_read(self):
        with tempfile.TemporaryDirectory() as td:
            base = write_kit(td)
            (base / "kit.json").write_bytes(b'{"name": "\xff"}')
            kit, problems = repo_kits.load_kit(td, "mfe")
            self.assertIsNone(kit)
            self.assertEqual(len(problems), 1)
            self.assertIn("cannot be read", problems[0])
            self.assertNotIn("JSON", problems[0])

    def test_each_bad_field_is_reported(self):
        bad = {
            "name": "other",
            "version": "1.0",
            "target": ".agent",
            "params": {
                "lower": {"description": "d", "pattern": "x"},
                "EMPTY": {"description": "", "pattern": "x"},
                "NOPAT": {"description": "d"},
                "BROKEN": {"description": "d", "pattern": "("},
            },
        }
        with tempfile.TemporaryDirectory() as td:
            write_kit(td, kit=bad)
            _, problems = repo_kits.load_kit(td, "mfe")
            text = "\n".join(problems)
            self.assertEqual(len(problems), 7, text)
            for needle in ("name", "version", "target", "lower", "EMPTY", "NOPAT", "BROKEN"):
                self.assertIn(needle, text)

    def test_params_must_be_object(self):
        with tempfile.TemporaryDirectory() as td:
            write_kit(td, kit=dict(MFE_KIT, params=[]))
            _, problems = repo_kits.load_kit(td, "mfe")
            self.assertEqual(len(problems), 1)
            self.assertIn("params", problems[0])


class KitFiles(unittest.TestCase):
    def test_sorted_relative_paths_without_pycache(self):
        with tempfile.TemporaryDirectory() as td:
            write_kit(
                td,
                kit=MFE_KIT,
                files={
                    "b.md": "b",
                    "agents/screen.md": "s",
                    "AGENTS.md": "a",
                    "tools/__pycache__/x.pyc": b"\0",
                },
            )
            self.assertEqual(repo_kits.kit_files(td, "mfe"), ["AGENTS.md", "agents/screen.md", "b.md"])

    def test_no_files_folder(self):
        with tempfile.TemporaryDirectory() as td:
            write_kit(td, kit=MFE_KIT)
            self.assertEqual(repo_kits.kit_files(td, "mfe"), [])


class UndeclaredPlaceholders(unittest.TestCase):
    def test_undeclared_placeholder_names_file_and_name(self):
        with tempfile.TemporaryDirectory() as td:
            root = mfe_workspace(td, files={"AGENTS.md": "__MFE__\n", "agents/screen.md": "__PREFIX__ and __MFE__\n"})
            self.assertEqual(repo_kits.undeclared_placeholders(root, "mfe"), [("agents/screen.md", "PREFIX")])


class LoadEntry(unittest.TestCase):
    def test_finds_entry_by_name(self):
        with tempfile.TemporaryDirectory() as td:
            root = mfe_workspace(td, entries=[{"name": "other"}, MFE_ENTRY])
            self.assertEqual(repo_kits.load_entry(root, "abs-operations"), MFE_ENTRY)
            self.assertIsNone(repo_kits.load_entry(root, "missing"))

    def test_missing_repos_json(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(repo_kits.load_entry(td, "abs-operations"))


class EntryProblems(unittest.TestCase):
    def entry(self, kit):
        return {"name": "abs-operations", "kit": kit}

    def test_valid_entry(self):
        with tempfile.TemporaryDirectory() as td:
            root = mfe_workspace(td)
            self.assertEqual(repo_kits.entry_problems(root, MFE_ENTRY), [])

    def test_entry_without_kit(self):
        with tempfile.TemporaryDirectory() as td:
            root = mfe_workspace(td)
            self.assertEqual(repo_kits.entry_problems(root, {"name": "abs-operations"}), [])

    def test_missing_parameter(self):
        with tempfile.TemporaryDirectory() as td:
            root = mfe_workspace(td)
            problems = repo_kits.entry_problems(root, self.entry({"kind": "mfe", "params": {"MFE": "mfe-abs-operations"}}))
            self.assertEqual(len(problems), 1)
            self.assertIn("abs-operations", problems[0])
            self.assertIn("BFF", problems[0])

    def test_unknown_kind(self):
        with tempfile.TemporaryDirectory() as td:
            root = mfe_workspace(td)
            problems = repo_kits.entry_problems(root, self.entry({"kind": "gateway", "params": {}}))
            self.assertEqual(len(problems), 1)
            self.assertIn("abs-operations", problems[0])
            self.assertIn("gateway", problems[0])

    def test_kind_outside_repo_kits_is_unknown(self):
        with tempfile.TemporaryDirectory() as td:
            root = mfe_workspace(td)
            problems = repo_kits.entry_problems(root, self.entry({"kind": "../repo-kits/mfe", "params": {}}))
            self.assertEqual(len(problems), 1)

    def test_extra_parameter(self):
        with tempfile.TemporaryDirectory() as td:
            root = mfe_workspace(td)
            params = dict(MFE_ENTRY["kit"]["params"], PREFIX="x")
            problems = repo_kits.entry_problems(root, self.entry({"kind": "mfe", "params": params}))
            self.assertEqual(len(problems), 1)
            self.assertIn("PREFIX", problems[0])

    def test_value_not_string_or_not_matching(self):
        with tempfile.TemporaryDirectory() as td:
            root = mfe_workspace(td)
            # "bff-abs-operations " matches with re.search/match but not with re.fullmatch.
            params = {"MFE": 5, "BFF": "bff-abs-operations "}
            problems = repo_kits.entry_problems(root, self.entry({"kind": "mfe", "params": params}))
            text = "\n".join(problems)
            self.assertEqual(len(problems), 2, text)
            self.assertIn("MFE", text)
            self.assertIn("BFF", text)

    def test_broken_kit_json_names_the_kit(self):
        with tempfile.TemporaryDirectory() as td:
            root = mfe_workspace(td)
            write_kit(root, kit="{not json")
            problems = repo_kits.entry_problems(root, MFE_ENTRY)
            self.assertEqual(len(problems), 1, problems)
            self.assertIn("kit mfe is invalid", problems[0])
            self.assertNotIn("has no parameter", problems[0])

    def test_missing_kit_json_names_the_kit(self):
        with tempfile.TemporaryDirectory() as td:
            root = mfe_workspace(td)
            (root / ".agents/repo-kits/mfe/kit.json").unlink()
            problems = repo_kits.entry_problems(root, MFE_ENTRY)
            self.assertEqual(len(problems), 1, problems)
            self.assertIn("kit mfe is invalid", problems[0])
            self.assertIn("kit.json is missing", problems[0])

    def test_malformed_kit_object(self):
        with tempfile.TemporaryDirectory() as td:
            root = mfe_workspace(td)
            self.assertNotEqual(repo_kits.entry_problems(root, self.entry("mfe")), [])
            self.assertNotEqual(repo_kits.entry_problems(root, self.entry({"kind": "mfe", "params": []})), [])


class Render(unittest.TestCase):
    def test_substitution(self):
        with tempfile.TemporaryDirectory() as td:
            root = mfe_workspace(td, files={"AGENTS.md": "__MFE__ / __BFF__\n", "agents/screen.md": "Service __MFE__\n"})
            out = repo_kits.render(root, "abs-operations")
            self.assertEqual(list(out), [".agents/AGENTS.md", ".agents/agents/screen.md"])
            self.assertEqual(out[".agents/agents/screen.md"], b"Service mfe-abs-operations\n")
            self.assertNotIn(b"__MFE__", out[".agents/agents/screen.md"])
            self.assertEqual(out[".agents/AGENTS.md"], b"mfe-abs-operations / bff-abs-operations\n")

    def test_entry_without_kit_raises(self):
        with tempfile.TemporaryDirectory() as td:
            root = mfe_workspace(td, entries=[{"name": "abs-operations"}])
            with self.assertRaises(repo_kits.RepoKitError):
                repo_kits.render(root, "abs-operations")

    def test_unknown_repository_raises(self):
        with tempfile.TemporaryDirectory() as td:
            root = mfe_workspace(td)
            with self.assertRaises(repo_kits.RepoKitError):
                repo_kits.render(root, "missing")

    def test_invalid_entry_raises(self):
        with tempfile.TemporaryDirectory() as td:
            entry = {"name": "abs-operations", "kit": {"kind": "mfe", "params": {"MFE": "mfe-abs-operations"}}}
            root = mfe_workspace(td, entries=[entry])
            with self.assertRaisesRegex(repo_kits.RepoKitError, "BFF"):
                repo_kits.render(root, "abs-operations")

    def test_invalid_kit_raises(self):
        with tempfile.TemporaryDirectory() as td:
            root = mfe_workspace(td)
            write_kit(root, kit=dict(MFE_KIT, target="docs"))
            with self.assertRaises(repo_kits.RepoKitError):
                repo_kits.render(root, "abs-operations")

    def test_broken_kit_json_raises_naming_the_kit(self):
        with tempfile.TemporaryDirectory() as td:
            root = mfe_workspace(td)
            write_kit(root, kit="{not json")
            with self.assertRaises(repo_kits.RepoKitError) as ctx:
                repo_kits.render(root, "abs-operations")
            self.assertIn("kit mfe is invalid", str(ctx.exception))
            self.assertNotIn("has no parameter", str(ctx.exception))

    def test_adjacent_placeholders_read_as_one_name(self):
        # The spec regex __[A-Z][A-Z0-9_]*__ is greedy, so __MFE____BFF__ is the single name MFE____BFF.
        with tempfile.TemporaryDirectory() as td:
            root = mfe_workspace(td, files={"AGENTS.md": "__MFE____BFF__\n"})
            with self.assertRaisesRegex(repo_kits.RepoKitError, "MFE____BFF"):
                repo_kits.render(root, "abs-operations")

    def test_undeclared_placeholder_raises(self):
        with tempfile.TemporaryDirectory() as td:
            root = mfe_workspace(td, files={"AGENTS.md": "__MFE__ __PREFIX__\n"})
            with self.assertRaisesRegex(repo_kits.RepoKitError, "PREFIX"):
                repo_kits.render(root, "abs-operations")

    def test_two_renders_are_equal(self):
        with tempfile.TemporaryDirectory() as td:
            root = mfe_workspace(td, files={"z.md": "__BFF__", "a/b.md": "__MFE__", "AGENTS.md": "x"})
            first = repo_kits.render(root, "abs-operations")
            second = repo_kits.render(root, "abs-operations")
            self.assertEqual(list(first.items()), list(second.items()))

    def test_line_endings_are_kept(self):
        with tempfile.TemporaryDirectory() as td:
            root = mfe_workspace(td, files={"AGENTS.md": b"one __MFE__\r\ntwo\r\nthree\n"})
            out = repo_kits.render(root, "abs-operations")
            self.assertEqual(out[".agents/AGENTS.md"], b"one mfe-abs-operations\r\ntwo\r\nthree\n")


def sha(content):
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def write_clone(clone, files):
    """Create clone files from a {relpath: bytes|str} map."""
    for rel, content in files.items():
        path = Path(clone) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, str):
            content = content.encode("utf-8")
        path.write_bytes(content)


def write_stamp_file(clone, files, kind="mfe", version="1.0.0"):
    stamp = {"kind": kind, "version": version, "params": MFE_ENTRY["kit"]["params"], "files": files}
    write_clone(clone, {".agents/kit.json": json.dumps(stamp, indent=2) + "\n"})


class Status(unittest.TestCase):
    KIT_FILES = {"rules/api-client.md": "Client for __BFF__\n", "skills/add-table/SKILL.md": "Table in __MFE__ v2\n"}
    RENDERED_API = "Client for bff-abs-operations\n"
    RENDERED_SKILL = "Table in mfe-abs-operations v2\n"

    def run_status(self, clone_files, stamp=None):
        with tempfile.TemporaryDirectory() as td:
            root = mfe_workspace(Path(td) / "ws", files=self.KIT_FILES)
            clone = Path(td) / "clone"
            clone.mkdir()
            write_clone(clone, clone_files)
            if stamp is not None:
                write_stamp_file(clone, stamp)
            return repo_kits.status(root, "abs-operations", clone)

    def test_absent(self):
        result = self.run_status({".agents/rules/api-client.md": self.RENDERED_API})
        self.assertEqual(result, [("same", ".agents/rules/api-client.md"), ("absent", ".agents/skills/add-table/SKILL.md")])

    def test_same(self):
        result = self.run_status(
            {".agents/rules/api-client.md": self.RENDERED_API, ".agents/skills/add-table/SKILL.md": self.RENDERED_SKILL}
        )
        self.assertEqual(result, [("same", ".agents/rules/api-client.md"), ("same", ".agents/skills/add-table/SKILL.md")])

    def test_replaceable(self):
        old = "Table in mfe-abs-operations v1\n"
        result = self.run_status(
            {".agents/rules/api-client.md": self.RENDERED_API, ".agents/skills/add-table/SKILL.md": old},
            stamp={".agents/rules/api-client.md": sha(self.RENDERED_API), ".agents/skills/add-table/SKILL.md": sha(old)},
        )
        self.assertIn(("replaceable", ".agents/skills/add-table/SKILL.md"), result)

    def test_edited_against_stamp(self):
        result = self.run_status(
            {".agents/rules/api-client.md": "Client for bff-abs-operations, with team notes\n"},
            stamp={".agents/rules/api-client.md": sha(self.RENDERED_API)},
        )
        self.assertIn(("edited", ".agents/rules/api-client.md"), result)

    def test_edited_without_stamp(self):
        result = self.run_status({".agents/rules/api-client.md": "handwritten\n"})
        self.assertIn(("edited", ".agents/rules/api-client.md"), result)

    def test_edited_when_stamp_has_no_entry(self):
        result = self.run_status({".agents/rules/api-client.md": "handwritten\n"}, stamp={})
        self.assertIn(("edited", ".agents/rules/api-client.md"), result)

    def test_obsolete(self):
        result = self.run_status({".agents/rules/old.md": "old\n"}, stamp={".agents/rules/old.md": sha("old\n")})
        self.assertIn(("obsolete", ".agents/rules/old.md"), result)

    def test_removed_edited(self):
        result = self.run_status({".agents/rules/old.md": "old, edited\n"}, stamp={".agents/rules/old.md": sha("old\n")})
        self.assertIn(("removed-edited", ".agents/rules/old.md"), result)

    def test_stamp_path_with_missing_file_prints_nothing(self):
        result = self.run_status({}, stamp={".agents/rules/old.md": sha("old\n")})
        self.assertEqual([path for _, path in result], [".agents/rules/api-client.md", ".agents/skills/add-table/SKILL.md"])

    def test_foreign(self):
        result = self.run_status(
            {
                ".agents/rules/team-notes.md": "notes\n",
                ".agents/local/rules/api-client.md": "old text\n",
                "docs/readme.md": "outside the kit folder\n",
            },
            stamp={},
        )
        self.assertEqual(
            result,
            [
                ("absent", ".agents/rules/api-client.md"),
                ("foreign", ".agents/rules/team-notes.md"),
                ("absent", ".agents/skills/add-table/SKILL.md"),
            ],
        )

    def test_status_before_the_folder_move(self):
        with tempfile.TemporaryDirectory() as td:
            root = mfe_workspace(Path(td) / "ws", files={"agents/arm-bff-implementer.md": "Implementer for __BFF__\n"})
            clone = Path(td) / "clone"
            write_clone(
                clone,
                {".agent/agents/arm-bff-implementer.md": "Our own implementer\n", ".agent/rules/team-notes.md": "notes\n"},
            )
            result = repo_kits.status(root, "abs-operations", clone)
            self.assertEqual(
                result,
                [("edited", ".agents/agents/arm-bff-implementer.md"), ("foreign", ".agents/rules/team-notes.md")],
            )
            self.assertFalse((clone / ".agents").exists())

    def test_sorted_by_path(self):
        result = self.run_status(
            {".agents/zz.md": "z\n", ".agents/a.md": "a\n", ".agents/rules/old.md": "old\n"},
            stamp={".agents/rules/old.md": sha("old\n")},
        )
        paths = [path for _, path in result]
        self.assertEqual(paths, sorted(paths))
        self.assertEqual(len(paths), 5)


class Stamp(unittest.TestCase):
    def workspace(self, td):
        # Entry params in the opposite order of the kit's params, to check the stamp follows the kit.
        entry = {"name": "abs-operations", "kit": {"kind": "mfe", "params": {"BFF": "bff-abs-operations", "MFE": "mfe-abs-operations"}}}
        root = Path(td) / "ws"
        write_kit(root, kit=MFE_KIT, files={"z.md": "__BFF__\n", "AGENTS.md": "__MFE__\n", "agents/screen.md": "screen\n"})
        write_repos(root, [entry])
        return root

    def test_stamp_text(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.workspace(td)
            text = repo_kits.stamp_text(root, "abs-operations")
            self.assertTrue(text.endswith("}\n"))
            data = json.loads(text, object_pairs_hook=lambda pairs: pairs)
            self.assertEqual([key for key, _ in data], ["kind", "version", "params", "files"])
            stamp = json.loads(text)
            self.assertEqual(stamp["kind"], "mfe")
            self.assertEqual(stamp["version"], "1.0.0")
            self.assertEqual(list(stamp["params"].items()), [("MFE", "mfe-abs-operations"), ("BFF", "bff-abs-operations")])
            self.assertEqual(
                list(stamp["files"].items()),
                [
                    (".agents/AGENTS.md", sha("mfe-abs-operations\n")),
                    (".agents/agents/screen.md", sha("screen\n")),
                    (".agents/z.md", sha("bff-abs-operations\n")),
                ],
            )
            self.assertEqual(text, json.dumps(stamp, indent=2, ensure_ascii=False) + "\n")

    def test_write_and_read_stamp(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.workspace(td)
            clone = Path(td) / "clone"
            clone.mkdir()
            self.assertIsNone(repo_kits.read_stamp(clone))
            repo_kits.write_stamp(root, "abs-operations", clone)
            path = clone / ".agents" / "kit.json"
            self.assertEqual(path.read_bytes(), repo_kits.stamp_text(root, "abs-operations").encode("utf-8"))
            self.assertEqual(repo_kits.read_stamp(clone), json.loads(path.read_text(encoding="utf-8")))

    def test_read_stamp_invalid(self):
        with tempfile.TemporaryDirectory() as td:
            write_clone(td, {".agents/kit.json": "{not json"})
            self.assertIsNone(repo_kits.read_stamp(td))

    def test_stamp_after_status_is_all_same(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.workspace(td)
            clone = Path(td) / "clone"
            write_clone(clone, dict(repo_kits.render(root, "abs-operations")))
            repo_kits.write_stamp(root, "abs-operations", clone)
            self.assertEqual({state for state, _ in repo_kits.status(root, "abs-operations", clone)}, {"same"})


if __name__ == "__main__":
    unittest.main()
