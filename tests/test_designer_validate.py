import contextlib
import importlib.machinery
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

FIX = Path("tests/fixtures/designer/project")
L = importlib.machinery.SourceFileLoader("designer_validate", "bin/designer-validate").load_module()


def prepared():
    tmp = Path(tempfile.mkdtemp()) / "project"
    shutil.copytree(FIX, tmp)
    return tmp


def run_validate(mockups_dir, map_path):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = L.main([str(mockups_dir), "--map", str(map_path)])
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    return code, out.getvalue(), err.getvalue()


class DesignerValidate(unittest.TestCase):
    def test_extended_schema_accepted(self):
        proj = prepared()
        code, _, err = run_validate(proj / "mockups", proj / "MAP.md")
        self.assertEqual(code, 0, err)
        self.assertNotIn("mockups.json:", err)
        self.assertNotIn("canvas.json:", err)

    def test_arm_only_entry_accepted(self):
        proj = prepared()
        code, _, err = run_validate(proj / "mockups", proj / "MAP.md")
        self.assertEqual(code, 0, err)
        self.assertNotIn("mockup:clients/legacy", err)

    def test_bad_manifest_rejected(self):
        proj = prepared()
        manifest = proj / "mockups" / "mockups.json"
        manifest.write_text(json.dumps({"none": []}))
        code, _, err = run_validate(proj / "mockups", proj / "MAP.md")
        self.assertNotEqual(code, 0)
        self.assertIn("mockups", err)

        manifest.write_text(json.dumps({
            "mockups": {"mockup:clients/broken": {"screen": "screen:clients/clients"}},
            "none": [],
        }))
        code, _, err = run_validate(proj / "mockups", proj / "MAP.md")
        self.assertNotEqual(code, 0)
        self.assertIn("mockup:clients/broken", err)

    def test_artboard_artifacts_rejected(self):
        proj = prepared()
        board = proj / "mockups" / "Clients.dc.html"
        board.write_text(board.read_text().replace("<body>", "<body><x-dc></x-dc>"))
        code, _, err = run_validate(proj / "mockups", proj / "MAP.md")
        self.assertNotEqual(code, 0)
        self.assertIn("Clients.dc.html", err)

        board.write_text(board.read_text().replace("app.css", "support.js"))
        code, _, err = run_validate(proj / "mockups", proj / "MAP.md")
        self.assertNotEqual(code, 0)
        self.assertIn("Clients.dc.html", err)

    def test_uncovered_screen(self):
        proj = prepared()
        manifest = proj / "mockups" / "mockups.json"
        data = json.loads(manifest.read_text())
        del data["mockups"]["mockup:clients/legacy"]
        manifest.write_text(json.dumps(data))
        code, _, err = run_validate(proj / "mockups", proj / "MAP.md")
        self.assertNotEqual(code, 0)
        self.assertIn("screen:clients/other", err)

    def test_none_marker_covers(self):
        proj = prepared()
        manifest = proj / "mockups" / "mockups.json"
        data = json.loads(manifest.read_text())
        del data["mockups"]["mockup:clients/legacy"]
        data["none"] = ["screen:clients/other"]
        manifest.write_text(json.dumps(data))
        code, _, err = run_validate(proj / "mockups", proj / "MAP.md")
        self.assertEqual(code, 0, err)

    def test_malformed_map_row(self):
        proj = prepared()
        map_file = proj / "MAP.md"
        lines = map_file.read_text().splitlines()
        lineno = next(i for i, line in enumerate(lines, 1) if "screen:clients/other" in line)
        lines[lineno - 1] = "| screen:clients/other | /clients/other |"
        map_file.write_text("\n".join(lines) + "\n")
        code, _, err = run_validate(proj / "mockups", proj / "MAP.md")
        self.assertNotEqual(code, 0)
        self.assertIn(f"MAP.md:{lineno}:", err)

    def test_manifest_artboard_missing(self):
        proj = prepared()
        (proj / "mockups" / "Clients.dc.html").unlink()
        code, _, err = run_validate(proj / "mockups", proj / "MAP.md")
        self.assertNotEqual(code, 0)
        self.assertIn("mockup:clients/clients", err)
        self.assertIn("Clients.dc.html", err)

    def test_dangling_vendor_ref(self):
        proj = prepared()
        board = proj / "mockups" / "Clients.dc.html"
        board.write_text(board.read_text().replace("app.css", "missing.js"))
        code, _, err = run_validate(proj / "mockups", proj / "MAP.md")
        self.assertNotEqual(code, 0)
        self.assertIn("Clients.dc.html", err)
        self.assertIn("vendor/fake/1.0.0/missing.js", err)

    def test_external_url_rejected(self):
        proj = prepared()
        board = proj / "mockups" / "Clients.dc.html"
        board.write_text(board.read_text().replace(
            "</head>", '<script src="https://cdn.example.com/x.js"></script></head>'))
        code, _, err = run_validate(proj / "mockups", proj / "MAP.md")
        self.assertNotEqual(code, 0)
        self.assertIn("Clients.dc.html", err)
        self.assertIn("https://cdn.example.com/x.js", err)

    def test_kit_version_mismatch(self):
        proj = prepared()
        manifest = proj / "mockups" / "mockups.json"
        data = json.loads(manifest.read_text())
        data["mockups"]["mockup:clients/clients"]["kit_version"] = "2.0.0"
        manifest.write_text(json.dumps(data))
        code, _, err = run_validate(proj / "mockups", proj / "MAP.md")
        self.assertNotEqual(code, 0)
        self.assertIn("mockup:clients/clients", err)
        self.assertIn("2.0.0", err)

    def test_kit_version_match_accepted(self):
        proj = prepared()
        code, _, err = run_validate(proj / "mockups", proj / "MAP.md")
        self.assertEqual(code, 0, err)
        self.assertNotIn("kit_version", err)

    def test_orphan_artboard_warns(self):
        proj = prepared()
        (proj / "mockups" / "Orphan.dc.html").write_text(
            "<!doctype html>\n<html><body><main>orphan</main></body></html>\n")
        code, _, err = run_validate(proj / "mockups", proj / "MAP.md")
        self.assertEqual(code, 0, err)
        self.assertIn("warning:", err)
        self.assertIn("Orphan.dc.html", err)


if __name__ == "__main__":
    unittest.main()
