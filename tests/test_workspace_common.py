import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import json
import subprocess
import tempfile
import unittest
from unittest import mock

from wslib import common


class FindRoot(unittest.TestCase):
    def test_finds_root_from_nested_subdirectory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "proj"
            (root / ".agents").mkdir(parents=True)
            (root / ".agents" / "kit.json").write_text("{}\n")
            nested = root / "a" / "b"
            nested.mkdir(parents=True)
            self.assertEqual(common.find_root(nested), root.resolve())

    def test_none_without_kit_json(self):
        with tempfile.TemporaryDirectory() as td:
            nested = Path(td) / "other" / "sub"
            nested.mkdir(parents=True)
            self.assertIsNone(common.find_root(nested))


class ListFiles(unittest.TestCase):
    def test_git_repo_respects_gitignore(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(["git", "init", "-q"], cwd=str(root), check=True)
            (root / ".gitignore").write_text(".local/\n")
            (root / "a.md").write_text("hi\n")
            (root / ".local").mkdir()
            (root / ".local" / "env").write_text("HOME=%s\n" % str(Path.home()))
            files = common.list_files(root)
            self.assertEqual(files, [".gitignore", "a.md"])
            self.assertNotIn(".local/env", files)

    def test_plain_directory_skips_reserved_dirs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.md").write_text("hi\n")
            sub = root / "sub"
            sub.mkdir()
            (sub / "b.md").write_text("hi\n")
            (root / ".local").mkdir()
            (root / ".local" / "x").write_text("x\n")
            (root / "repos").mkdir()
            (root / "repos" / "x").write_text("x\n")
            (root / ".git").mkdir()
            (root / ".git" / "x").write_text("x\n")
            files = common.list_files(root)
            self.assertEqual(files, ["a.md", "sub/b.md"])

    def test_git_output_with_non_utf8_name_is_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.md").write_text("hi\n")
            proc = subprocess.CompletedProcess([], 0, stdout=b"a.md\0bad\xff.md\0", stderr=b"")
            with mock.patch.object(common.subprocess, "run", return_value=proc):
                self.assertEqual(common.list_files(root), ["a.md"])

    def test_walk_with_non_utf8_name_is_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            walk = [(td, [], ["a.md", "bad\udcff.md"])]
            with mock.patch.object(common.subprocess, "run", side_effect=OSError), \
                    mock.patch.object(common.os, "walk", return_value=walk):
                self.assertEqual(common.list_files(root), ["a.md"])


class ParseFrontmatter(unittest.TestCase):
    def test_scalar_with_quotes(self):
        text = '---\nkey: "hello world"\n---\nbody\n'
        data, body, error = common.parse_frontmatter(text)
        self.assertIsNone(error)
        self.assertEqual(data, {"key": "hello world"})
        self.assertEqual(body, "body\n")

        text2 = "---\nkey: 'hello'\n---\nbody\n"
        data2, _, error2 = common.parse_frontmatter(text2)
        self.assertIsNone(error2)
        self.assertEqual(data2, {"key": "hello"})

    def test_inline_list(self):
        text = "---\nkey: [a, b]\n---\nbody\n"
        data, _, error = common.parse_frontmatter(text)
        self.assertIsNone(error)
        self.assertEqual(data, {"key": ["a", "b"]})

    def test_empty_list(self):
        text = "---\nkey: []\n---\nbody\n"
        data, _, error = common.parse_frontmatter(text)
        self.assertIsNone(error)
        self.assertEqual(data, {"key": []})

    def test_inline_map(self):
        text = "---\nkey: {a: b, c: d}\n---\nbody\n"
        data, _, error = common.parse_frontmatter(text)
        self.assertIsNone(error)
        self.assertEqual(data, {"key": {"a": "b", "c": "d"}})

    def test_block_list(self):
        text = "---\nkey:\n  - a\n  - b\n---\nbody\n"
        data, _, error = common.parse_frontmatter(text)
        self.assertIsNone(error)
        self.assertEqual(data, {"key": ["a", "b"]})

    def test_block_map(self):
        text = "---\nkey:\n  sub: value\n---\nbody\n"
        data, _, error = common.parse_frontmatter(text)
        self.assertIsNone(error)
        self.assertEqual(data, {"key": {"sub": "value"}})

    def test_empty_value(self):
        text = "---\nkey:\n---\nbody\n"
        data, _, error = common.parse_frontmatter(text)
        self.assertIsNone(error)
        self.assertEqual(data, {"key": ""})

    def test_no_frontmatter(self):
        text = "no marker here\nsecond line\n"
        data, body, error = common.parse_frontmatter(text)
        self.assertIsNone(data)
        self.assertIsNone(error)
        self.assertEqual(body, text)

    def test_missing_closing_marker(self):
        text = "---\nkey: value\n"
        data, body, error = common.parse_frontmatter(text)
        self.assertIsNone(data)
        self.assertEqual(body, text)
        self.assertIsNotNone(error)
        self.assertIn("frontmatter line", error)

    def assertFrontmatterError(self, text, line):
        data, body, error = common.parse_frontmatter(text)
        self.assertIsNone(data)
        self.assertEqual(body, text)
        self.assertIsNotNone(error)
        self.assertIn("frontmatter line %d:" % line, error)

    def test_inline_map_part_without_colon(self):
        self.assertFrontmatterError("---\nkey: {a}\n---\nbody\n", 2)

    def test_inline_map_trailing_comma(self):
        self.assertFrontmatterError("---\nkey: {a: b,}\n---\nbody\n", 2)

    def test_empty_line_inside_block(self):
        self.assertFrontmatterError("---\na: b\n\nc: d\n---\nbody\n", 3)

    def test_block_line_indented_more_than_two_spaces(self):
        self.assertFrontmatterError("---\nkey:\n    sub: v\n---\nbody\n", 3)

    def test_block_map_line_without_sub_value_shape(self):
        self.assertFrontmatterError("---\nkey:\n  justtext\n---\nbody\n", 3)
        self.assertFrontmatterError("---\nkey:\n  : v\n---\nbody\n", 3)
        self.assertFrontmatterError("---\nkey:\n  sub: v\n  other\n---\nbody\n", 4)

    def test_keys_with_hyphens_and_digits(self):
        text = '---\nallowed-tools: [Read, Grep]\nargument-hint: "<id>"\nv2:\n  sub-key: x\n---\nbody\n'
        data, _, error = common.parse_frontmatter(text)
        self.assertIsNone(error)
        self.assertEqual(
            data,
            {"allowed-tools": ["Read", "Grep"], "argument-hint": "<id>", "v2": {"sub-key": "x"}},
        )

    def test_inline_list_empty_item(self):
        self.assertFrontmatterError("---\nkey: [a, ]\n---\nbody\n", 2)
        self.assertFrontmatterError("---\nkey: [, a]\n---\nbody\n", 2)

    def test_unclosed_inline_list_or_map(self):
        self.assertFrontmatterError("---\nkey: [a, b\n---\nbody\n", 2)
        self.assertFrontmatterError("---\nkey: {a: b\n---\nbody\n", 2)

    def test_duplicate_key(self):
        self.assertFrontmatterError("---\na: 1\nb: 2\na: 3\n---\nbody\n", 4)
        self.assertFrontmatterError("---\nkey:\n  a: 1\n  a: 2\n---\nbody\n", 4)
        self.assertFrontmatterError("---\nkey: {a: 1, a: 2}\n---\nbody\n", 2)

    def test_quotes_stripped_in_lists_and_maps(self):
        text = (
            "---\n"
            "il: [\"a\", 'b', c]\n"
            "im: {x: \"1\", y: '2'}\n"
            "bl:\n  - \"p\"\n  - 'q'\n"
            "bm:\n  s: \"v\"\n  t: 'w'\n"
            "---\nbody\n"
        )
        data, _, error = common.parse_frontmatter(text)
        self.assertIsNone(error)
        self.assertEqual(
            data,
            {
                "il": ["a", "b", "c"],
                "im": {"x": "1", "y": "2"},
                "bl": ["p", "q"],
                "bm": {"s": "v", "t": "w"},
            },
        )

    def test_whitespace_only_block_line(self):
        text = "---\nkey:\n  a: b\n  \n---\nbody\n"
        self.assertFrontmatterError(text, 4)
        self.assertIn("blank line", common.parse_frontmatter(text)[2])


class MdLinks(unittest.TestCase):
    def test_link_on_line_two(self):
        text = "line one\n[adr:0001](docs/adr/0001-x.md)\n"
        links = common.md_links(text)
        self.assertIn((2, "adr:0001", "docs/adr/0001-x.md"), links)


class ResolveTarget(unittest.TestCase):
    def test_relative_up_and_fragment(self):
        self.assertEqual(
            common.resolve_target("work/TASK-1/record.md", "../../environments.json#stand"),
            "environments.json",
        )

    def test_relative_directory_trailing_slash(self):
        self.assertEqual(common.resolve_target("AGENTS.md", "domains/ops/"), "domains/ops")

    def test_repeated_slashes_are_normalized(self):
        self.assertEqual(common.resolve_target("AGENTS.md", "a//b/"), "a/b")
        self.assertEqual(common.resolve_target("docs/x.md", "./a/./b//"), "docs/a/b")
        self.assertEqual(common.resolve_target("AGENTS.md", "//a/"), "/a")
        self.assertEqual(common.resolve_target("AGENTS.md", "//"), "/")


class H2Headings(unittest.TestCase):
    def test_only_level_two_with_space(self):
        body = "# Title\n## One \n### Three\n##NoSpace\ntext ## not\n## Two\n"
        self.assertEqual(common.h2_headings(body), ["One", "Two"])


class ContextTests(unittest.TestCase):
    def test_load_json_invalid_returns_finding(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.json").write_text("{not valid json\n")
            ctx = common.Context(root)
            data, finding = ctx.load_json("a.json")
            self.assertIsNone(data)
            self.assertIsNotNone(finding)
            self.assertEqual(finding.rule, "json-shape")

    def test_load_json_line_from_decode_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.json").write_text('{\n  "a": 1,\n  oops\n}\n')
            data, finding = common.Context(root).load_json("a.json")
            self.assertIsNone(data)
            self.assertEqual(finding.path, "a.json")
            self.assertEqual(finding.line, 3)
            self.assertEqual(finding.rule, "json-shape")

    def test_load_json_missing_file(self):
        with tempfile.TemporaryDirectory() as td:
            data, finding = common.Context(td).load_json("missing.json")
            self.assertIsNone(data)
            self.assertEqual((finding.path, finding.line, finding.rule), ("missing.json", 1, "json-shape"))

    def test_load_json_valid(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "a.json").write_text('{"a": [1]}\n')
            self.assertEqual(common.Context(td).load_json("a.json"), ({"a": [1]}, None))

    def test_read_text(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "ok.md").write_text("hi\n", encoding="utf-8")
            (root / "bin.md").write_bytes(b"\xff\xfe\x00bad")
            ctx = common.Context(root)
            self.assertEqual(ctx.read_text("ok.md"), "hi\n")
            self.assertIsNone(ctx.read_text("missing.md"))
            self.assertIsNone(ctx.read_text("bin.md"))

    def test_kit_params(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.assertEqual(common.Context(root).kit_params(), {})
            (root / ".agents").mkdir()
            kit = root / ".agents" / "kit.json"
            kit.write_text(json.dumps({"name": "workspace", "params": {"title": "T"}}))
            self.assertEqual(common.Context(root).kit_params(), {"title": "T"})
            kit.write_text("{broken")
            self.assertEqual(common.Context(root).kit_params(), {})


class FormatFinding(unittest.TestCase):
    def test_format(self):
        f = common.Finding("a.json", 3, "json-shape", "msg")
        self.assertEqual(common.format_finding(f), "a.json:3 json-shape msg")


if __name__ == "__main__":
    unittest.main()
