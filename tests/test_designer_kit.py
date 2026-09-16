import hashlib
import importlib.machinery
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
KIT = importlib.machinery.SourceFileLoader("designer_kit", str(REPO / "bin/designer-kit")).load_module()
FIXTURES = REPO / "tests/fixtures/designer/cache"
FAKE = FIXTURES / "fake-kit" / "1.0.0"


def run(*args):
    return subprocess.run([sys.executable, str(REPO / "bin/designer-kit"), *args], capture_output=True, text=True)


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def temp_dir():
    return Path(tempfile.mkdtemp(prefix="designer-kit-test-"))


class DesignerKitList(unittest.TestCase):
    def test_list_shows_fake_kit(self):
        r = run("list", "--cache", str(FIXTURES))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("fake-kit 1.0.0", r.stdout)


class DesignerKitEnsure(unittest.TestCase):
    def setUp(self):
        self.mockups = temp_dir()
        self.addCleanup(shutil.rmtree, self.mockups, True)

    def test_ensure_copies_vendor(self):
        r = run("ensure", str(self.mockups), "fake-kit", "1.0.0", "--cache", str(FIXTURES))
        self.assertEqual(r.returncode, 0, r.stderr)
        copied = self.mockups / "vendor/fake-kit/1.0.0/vendor/app.css"
        self.assertTrue(copied.is_file(), f"missing {copied}")
        self.assertEqual(copied.read_text(), (FAKE / "vendor-src/app.css").read_text())
        self.assertTrue((self.mockups / "vendor/fake-kit/1.0.0/template.dc.html").is_file())

    def test_ensure_atomic(self):
        # broken kit: the vendor asset the manifest promises is absent from the cache
        cache = temp_dir()
        self.addCleanup(shutil.rmtree, cache, True)
        broken = cache / "fake-kit" / "1.0.0"
        shutil.copytree(FAKE, broken)
        (broken / "vendor/app.css").unlink()
        r = run("ensure", str(self.mockups), "fake-kit", "1.0.0", "--cache", str(cache))
        self.assertNotEqual(r.returncode, 0)
        leftovers = [p.name for p in self.mockups.rglob("*") if ".tmp" in p.name]
        self.assertEqual(leftovers, [])
        self.assertFalse((self.mockups / "vendor/fake-kit/1.0.0").exists())
        r = run("ensure", str(self.mockups), "fake-kit", "1.0.0", "--cache", str(FIXTURES))
        self.assertEqual(r.returncode, 0, r.stderr)
        leftovers = [p.name for p in self.mockups.rglob("*") if ".tmp" in p.name]
        self.assertEqual(leftovers, [])
        self.assertTrue((self.mockups / "vendor/fake-kit/1.0.0/vendor/app.css").is_file())

    def test_missing_cache_entry_hard_error(self):
        r = run("ensure", str(self.mockups), "antd", "9.9.9", "--cache", str(FIXTURES))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("bin/designer-kit install antd 9.9.9", r.stderr)
        self.assertFalse((self.mockups / "vendor").exists())


class DesignerKitSync(unittest.TestCase):
    def mockups_with(self, pin_version, vendor_versions):
        mockups = temp_dir()
        self.addCleanup(shutil.rmtree, mockups, True)
        for v in vendor_versions:
            shutil.copytree(FAKE, mockups / "vendor/fake-kit" / v)
        entry = {"artboard": "X", "kit": "fake-kit", "kit_version": pin_version}
        (mockups / "mockups.json").write_text(json.dumps({"mockups": {"mockup:x/x": entry}}))
        return mockups

    def test_sync_aligns_version(self):
        mockups = self.mockups_with("1.0.0", ["2.0.0"])
        r = run("sync", str(mockups), "--cache", str(FIXTURES))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((mockups / "vendor/fake-kit/1.0.0/vendor/app.css").is_file())
        self.assertFalse((mockups / "vendor/fake-kit/2.0.0").exists())

    def test_sync_missing_pin_in_cache(self):
        mockups = self.mockups_with("2.0.0", ["1.0.0"])
        r = run("sync", str(mockups), "--cache", str(FIXTURES))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("bin/designer-kit install fake-kit 2.0.0", r.stderr)
        self.assertTrue((mockups / "vendor/fake-kit/1.0.0/vendor/app.css").is_file())

    def test_sync_no_manifest(self):
        mockups = temp_dir()
        self.addCleanup(shutil.rmtree, mockups, True)
        r = run("sync", str(mockups), "--cache", str(FIXTURES))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("mockups.json", r.stderr)


class DesignerKitInstall(unittest.TestCase):
    def source_dir(self, cache, sha):
        # resolve the __FIXTURE__ placeholder so the url is a real local file:// path
        manifest = json.loads((FAKE / "kit.json").read_text())
        manifest["vendor"][0]["url"] = manifest["vendor"][0]["url"].replace("__FIXTURE__", str(FIXTURES))
        manifest["vendor"][0]["sha256"] = sha
        src = cache / "source"
        (src / "vendor-src").mkdir(parents=True)
        (src / "kit.json").write_text(json.dumps(manifest))
        shutil.copy2(FAKE / "vendor-src/app.css", src / "vendor-src/app.css")
        return src

    def test_install_downloads_into_cache(self):
        cache = temp_dir()
        self.addCleanup(shutil.rmtree, cache, True)
        src = self.source_dir(cache, sha256_of(FAKE / "vendor-src/app.css"))
        target = cache / "dl"
        r = run("install", "fake-kit", "1.0.0", "--source", str(src), "--cache", str(target))
        self.assertEqual(r.returncode, 0, r.stderr)
        got = target / "fake-kit/1.0.0/vendor/app.css"
        self.assertTrue(got.is_file(), f"missing {got}")
        self.assertEqual(sha256_of(got), sha256_of(FAKE / "vendor-src/app.css"))

    def test_install_wrong_sha256_leaves_nothing(self):
        cache = temp_dir()
        self.addCleanup(shutil.rmtree, cache, True)
        src = self.source_dir(cache, "0" * 64)
        target = cache / "dl"
        r = run("install", "fake-kit", "1.0.0", "--source", str(src), "--cache", str(target))
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((target / "fake-kit/1.0.0/vendor/app.css").exists())
        leftovers = [p.name for p in target.rglob("*") if ".tmp" in p.name]
        self.assertEqual(leftovers, [])

    def test_install_skips_local_authored(self):
        # authored kits (url not http/file) are committed in the cache already;
        # install must succeed and neither download nor copy the entry
        cache = temp_dir()
        self.addCleanup(shutil.rmtree, cache, True)
        manifest = json.loads((FAKE / "kit.json").read_text())
        manifest["vendor"][0]["url"] = "local:authored"
        src = cache / "source"
        src.mkdir(parents=True)
        (src / "kit.json").write_text(json.dumps(manifest))
        target = cache / "dl"
        r = run("install", "fake-kit", "1.0.0", "--source", str(src), "--cache", str(target))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")
        self.assertFalse((target / "fake-kit/1.0.0/vendor/app.css").exists())


if __name__ == "__main__":
    unittest.main()
