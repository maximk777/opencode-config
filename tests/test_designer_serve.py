import contextlib
import importlib.machinery
import io
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parent.parent
SERVE = REPO / "bin" / "designer-serve"
FIXTURE = REPO / "tests" / "fixtures" / "designer" / "project" / "mockups"

S = importlib.machinery.SourceFileLoader("designer_serve", str(SERVE)).load_module()

MARKER = "gallery-index-marker-8f2a"
INDEX = f"<html><body><h1>gallery</h1><p>{MARKER}</p></body></html>\n"


def make_mockups(tmp):
    # temp copy of the fixture mockups with a freshly generated index.html
    dest = Path(tmp) / "mockups"
    dest.mkdir(parents=True)
    if FIXTURE.is_dir():
        shutil.copytree(FIXTURE, dest, dirs_exist_ok=True)
    (dest / "index.html").write_text(INDEX)
    return dest


def start(mockups, pf, extra=(), env=None):
    return subprocess.Popen(
        [sys.executable, str(SERVE), str(mockups), "--port-file", str(pf), *extra],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )


def url_from_file(pf, proc=None, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc is not None and proc.poll() is not None:
            out, err = proc.communicate()
            raise AssertionError(f"designer-serve exited early rc={proc.returncode}: {out}{err}")
        if pf.exists() and pf.read_text().strip():
            return pf.read_text().strip()
        time.sleep(0.05)
    raise AssertionError(f"no URL written to {pf} within {timeout}s")


def get(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, r.read().decode()


def finish(proc, timeout=10):
    # --once runs exit after the request; kill is a safety net against strays
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        raise AssertionError("designer-serve did not exit after the served request")
    return proc.returncode, out, err


class DesignerServe(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_serves_index_200(self):
        mockups = make_mockups(self.tmp)
        pf = Path(self.tmp) / "port"
        proc = start(mockups, pf, ["--no-open", "--once"])
        try:
            url = url_from_file(pf, proc)
            status, body = get(url)
        finally:
            rc, out, err = finish(proc)
        self.assertEqual(status, 200)
        self.assertIn(MARKER, body)
        self.assertIn(url, out)
        self.assertEqual(rc, 0)

    def test_free_port_picked(self):
        mockups = make_mockups(self.tmp)
        pf1, pf2 = Path(self.tmp) / "p1", Path(self.tmp) / "p2"
        p1 = start(mockups, pf1, ["--no-open", "--once"])
        p2 = start(mockups, pf2, ["--no-open", "--once"])
        try:
            u1 = url_from_file(pf1, p1)
            u2 = url_from_file(pf2, p2)
            self.assertNotEqual(urlparse(u1).port, urlparse(u2).port)
            get(u1)
            get(u2)
        finally:
            finish(p1)
            finish(p2)

    def test_no_open_flag_and_headless(self):
        mockups = make_mockups(self.tmp)
        pf = Path(self.tmp) / "port"
        proc = start(mockups, pf, ["--no-open", "--once"], env={"PATH": ""})
        try:
            url = url_from_file(pf, proc)
            status, body = get(url)
        finally:
            rc, out, err = finish(proc)
        self.assertEqual(status, 200)
        self.assertIn(MARKER, body)
        self.assertEqual(rc, 0)
        self.assertIn(url, out)

    def test_prints_url_and_open_best_effort(self):
        # no --no-open and PATH="": browser open is impossible, still exit 0 after printing URL;
        # serve in a background thread of this test process and shut it down
        mockups = make_mockups(self.tmp)
        pf = Path(self.tmp) / "port"
        out = io.StringIO()
        result = {}
        old_path = os.environ.get("PATH")

        def run():
            os.environ["PATH"] = ""
            try:
                with contextlib.redirect_stdout(out):
                    result["rc"] = S.main([str(mockups), "--port-file", str(pf), "--once"])
            finally:
                if old_path is None:
                    os.environ.pop("PATH", None)
                else:
                    os.environ["PATH"] = old_path

        thread = threading.Thread(target=run)
        thread.start()
        try:
            url = url_from_file(pf)
            status, body = get(url)
        finally:
            thread.join(timeout=15)
        self.assertEqual(status, 200)
        self.assertIn(MARKER, body)
        self.assertFalse(thread.is_alive(), "serve thread did not shut down")
        self.assertEqual(result.get("rc"), 0)
        self.assertIn(url, out.getvalue())


if __name__ == "__main__":
    unittest.main()
