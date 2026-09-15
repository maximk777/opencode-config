import contextlib
import importlib.machinery
import io
import os
import plistlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "lib"))

U = importlib.machinery.SourceFileLoader("ov_up", str(REPO / "bin/ov-up")).load_module()

FIXTURE = REPO / "tests" / "fixtures" / "opencode.ov-studio.installed.plist"


def _plist(label):
    return plistlib.dumps({"Label": label}).decode()


class RenderPlist(unittest.TestCase):
    def test_studio_matches_fixture(self):
        template_text = (REPO / "openviking" / "launchd" / "opencode.ov-studio.plist").read_text()
        rendered = U.render_plist(template_text, "/Users/test")
        self.assertEqual(plistlib.loads(rendered.encode()), plistlib.loads(FIXTURE.read_bytes()))

    def test_templates_render_to_valid_plists(self):
        expectations = {
            "opencode.ov-studio.plist": REPO / "openviking" / "launchd" / "opencode.ov-studio.plist",
            "opencode.ov-syncd.plist": REPO / "openviking" / "launchd" / "opencode.ov-syncd.plist",
        }
        log_paths = {
            "opencode.ov-studio.plist": "/Users/test/.openviking/ov-studio.log",
            "opencode.ov-syncd.plist": "/Users/test/.openviking/ov-sync.log",
        }
        program_args = {
            "opencode.ov-studio.plist": [
                "/usr/bin/env",
                "python3",
                "/Users/test/.config/opencode/bin/ov-studio",
                "--no-open",
            ],
            "opencode.ov-syncd.plist": [
                "/usr/bin/env",
                "python3",
                "/Users/test/.config/opencode/bin/ov-syncd",
            ],
        }
        for name, template_path in expectations.items():
            rendered = U.render_plist(template_path.read_text(), "/Users/test")
            parsed = plistlib.loads(rendered.encode())
            self.assertTrue(parsed["RunAtLoad"])
            self.assertTrue(parsed["KeepAlive"])
            path = parsed["EnvironmentVariables"]["PATH"]
            self.assertIn("/opt/homebrew/bin", path)
            self.assertIn("/usr/local/bin", path)
            self.assertEqual(parsed["StandardOutPath"], log_paths[name])
            self.assertEqual(parsed["StandardErrorPath"], log_paths[name])
            self.assertEqual(parsed["ProgramArguments"], program_args[name])


class FakeRun:
    """Records argv calls and returns (or raises) a scripted result for each command's first two words."""

    def __init__(self, results):
        self.results = results
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        outcome = self.results[tuple(argv[:2])]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class Result:
    def __init__(self, returncode, stderr="", stdout=""):
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = stdout


class InstallAgent(unittest.TestCase):
    def _agents_dir(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        return d

    def test_identical_file_loaded_returns_ok(self):
        agents_dir = self._agents_dir()
        target = agents_dir / "opencode.ov-studio.plist"
        target.write_text("rendered-content")
        mtime_before = target.stat().st_mtime
        run = FakeRun({("launchctl", "print"): Result(0)})
        status = U.install_agent(run, "opencode.ov-studio", "rendered-content", agents_dir, 501)
        self.assertEqual(status, "ok")
        self.assertEqual(run.calls, [["launchctl", "print", "gui/501/opencode.ov-studio"]])
        self.assertEqual(target.stat().st_mtime, mtime_before)

    def test_different_file_loaded_returns_updated_and_reboots(self):
        # Full call list: initial print (loaded), bootout, one poll that already reports
        # unloaded (no sleep needed), then bootstrap.
        agents_dir = self._agents_dir()
        target = agents_dir / "opencode.ov-studio.plist"
        target.write_text("old-content")
        calls = []

        def run(argv, **kwargs):
            calls.append(argv)
            if argv[:2] == ["launchctl", "print"]:
                print_calls = sum(1 for c in calls if c[:2] == ["launchctl", "print"])
                return Result(0) if print_calls == 1 else Result(113)
            if argv[:2] == ["launchctl", "bootout"]:
                return Result(0)
            if argv[:2] == ["launchctl", "bootstrap"]:
                return Result(0)
            raise AssertionError(f"unexpected argv {argv}")

        status = U.install_agent(
            run, "opencode.ov-studio", "rendered-content", agents_dir, 501, sleep=lambda s: None
        )
        self.assertEqual(status, "updated")
        self.assertEqual(target.read_text(), "rendered-content")
        self.assertEqual(
            calls,
            [
                ["launchctl", "print", "gui/501/opencode.ov-studio"],
                ["launchctl", "bootout", "gui/501/opencode.ov-studio"],
                ["launchctl", "print", "gui/501/opencode.ov-studio"],
                ["launchctl", "bootstrap", "gui/501", str(target)],
            ],
        )
        self.assertFalse(any(argv[:2] == ["launchctl", "kickstart"] for argv in calls))

    def test_bootout_waits_for_unload_before_bootstrap(self):
        agents_dir = self._agents_dir()
        target = agents_dir / "opencode.ov-studio.plist"
        target.write_text("old-content")
        calls = []
        sleeps = []

        def run(argv, **kwargs):
            calls.append(argv)
            if argv[:2] == ["launchctl", "print"]:
                print_calls = sum(1 for c in calls if c[:2] == ["launchctl", "print"])
                # initial check (call 1) and the first two polls (calls 2, 3) report loaded;
                # the third poll (call 4) reports unloaded.
                return Result(0) if print_calls < 4 else Result(113)
            if argv[:2] == ["launchctl", "bootout"]:
                return Result(0)
            if argv[:2] == ["launchctl", "bootstrap"]:
                return Result(0)
            raise AssertionError(f"unexpected argv {argv}")

        status = U.install_agent(
            run, "opencode.ov-studio", "rendered-content", agents_dir, 501, sleep=sleeps.append
        )
        self.assertEqual(status, "updated")
        self.assertEqual(sleeps, [0.5, 0.5])

    def test_bootout_never_unloads_still_bootstraps_after_ten_polls(self):
        agents_dir = self._agents_dir()
        target = agents_dir / "opencode.ov-studio.plist"
        target.write_text("old-content")
        calls = []
        sleeps = []

        def run(argv, **kwargs):
            calls.append(argv)
            if argv[:2] == ["launchctl", "print"]:
                return Result(0)  # always reports loaded
            if argv[:2] == ["launchctl", "bootout"]:
                return Result(0)
            if argv[:2] == ["launchctl", "bootstrap"]:
                return Result(0)
            raise AssertionError(f"unexpected argv {argv}")

        status = U.install_agent(
            run, "opencode.ov-studio", "rendered-content", agents_dir, 501, sleep=sleeps.append
        )
        self.assertEqual(status, "updated")
        print_calls = sum(1 for c in calls if c[:2] == ["launchctl", "print"])
        self.assertEqual(print_calls, 11)  # 1 initial check + 10 polls
        self.assertEqual(len(sleeps), 10)
        self.assertTrue(any(c[:2] == ["launchctl", "bootstrap"] for c in calls))

    def test_bootout_failure_returns_error_and_no_bootstrap(self):
        agents_dir = self._agents_dir()
        target = agents_dir / "opencode.ov-studio.plist"
        target.write_text("old-content")
        stderr = "Bootout failed: 5: Input/output error"
        run = FakeRun({
            ("launchctl", "print"): Result(0),
            ("launchctl", "bootout"): Result(5, stderr=stderr),
        })
        status = U.install_agent(run, "opencode.ov-studio", "rendered-content", agents_dir, 501)
        self.assertTrue(status.startswith("error: "))
        self.assertIn(stderr, status)
        self.assertFalse(any(argv[:2] == ["launchctl", "bootstrap"] for argv in run.calls))

    def test_bootout_raises_timeout_returns_error(self):
        agents_dir = self._agents_dir()
        target = agents_dir / "opencode.ov-studio.plist"
        target.write_text("old-content")
        run = FakeRun({
            ("launchctl", "print"): Result(0),
            ("launchctl", "bootout"): subprocess.TimeoutExpired(cmd=["launchctl", "bootout"], timeout=30),
        })
        status = U.install_agent(run, "opencode.ov-studio", "rendered-content", agents_dir, 501)
        self.assertTrue(status.startswith("error: "))
        self.assertNotIn("\n", status)

    def test_different_file_not_loaded_returns_updated_and_bootstraps(self):
        agents_dir = self._agents_dir()
        target = agents_dir / "opencode.ov-studio.plist"
        target.write_text("old-content")
        run = FakeRun({
            ("launchctl", "print"): Result(113),
            ("launchctl", "bootstrap"): Result(0),
        })
        status = U.install_agent(run, "opencode.ov-studio", "rendered-content", agents_dir, 501)
        self.assertEqual(status, "updated")
        self.assertEqual(target.read_text(), "rendered-content")
        self.assertIn(
            ["launchctl", "bootstrap", "gui/501", str(agents_dir / "opencode.ov-studio.plist")],
            run.calls,
        )

    def test_missing_file_returns_installed_and_bootstraps(self):
        agents_dir = self._agents_dir()
        run = FakeRun({
            ("launchctl", "print"): Result(113),
            ("launchctl", "bootstrap"): Result(0),
        })
        status = U.install_agent(run, "opencode.ov-studio", "rendered-content", agents_dir, 501)
        self.assertEqual(status, "installed")
        target = agents_dir / "opencode.ov-studio.plist"
        self.assertEqual(target.read_text(), "rendered-content")
        self.assertIn(
            ["launchctl", "bootstrap", "gui/501", str(target)],
            run.calls,
        )

    def test_missing_file_loaded_returns_installed_and_bootstraps(self):
        # A missing file always bootstraps, even if launchctl still reports the label as loaded.
        agents_dir = self._agents_dir()
        run = FakeRun({
            ("launchctl", "print"): Result(0),
            ("launchctl", "bootstrap"): Result(0),
        })
        status = U.install_agent(run, "opencode.ov-studio", "rendered-content", agents_dir, 501)
        self.assertEqual(status, "installed")
        target = agents_dir / "opencode.ov-studio.plist"
        self.assertEqual(target.read_text(), "rendered-content")
        self.assertIn(["launchctl", "bootstrap", "gui/501", str(target)], run.calls)
        self.assertFalse(any(argv[:2] == ["launchctl", "kickstart"] for argv in run.calls))

    def test_identical_file_not_loaded_returns_loaded_and_bootstraps(self):
        agents_dir = self._agents_dir()
        target = agents_dir / "opencode.ov-studio.plist"
        target.write_text("rendered-content")
        run = FakeRun({
            ("launchctl", "print"): Result(113),
            ("launchctl", "bootstrap"): Result(0),
        })
        status = U.install_agent(run, "opencode.ov-studio", "rendered-content", agents_dir, 501)
        self.assertEqual(status, "loaded")
        self.assertIn(
            ["launchctl", "bootstrap", "gui/501", str(target)],
            run.calls,
        )

    def test_bootstrap_failure_returns_error_with_stderr(self):
        agents_dir = self._agents_dir()
        stderr = "Bootstrap failed: 5: Input/output error"
        run = FakeRun({
            ("launchctl", "print"): Result(113),
            ("launchctl", "bootstrap"): Result(5, stderr=stderr),
        })
        status = U.install_agent(run, "opencode.ov-studio", "rendered-content", agents_dir, 501)
        self.assertTrue(status.startswith("error: "))
        self.assertIn(stderr, status)

    def test_error_status_has_no_newline(self):
        agents_dir = self._agents_dir()
        stderr = "Bootstrap failed: 5:\nInput/output error\n"
        run = FakeRun({
            ("launchctl", "print"): Result(113),
            ("launchctl", "bootstrap"): Result(5, stderr=stderr),
        })
        status = U.install_agent(run, "opencode.ov-studio", "rendered-content", agents_dir, 501)
        self.assertTrue(status.startswith("error: "))
        self.assertNotIn("\n", status)

    def test_print_raises_file_not_found_returns_error(self):
        agents_dir = self._agents_dir()
        run = FakeRun({
            ("launchctl", "print"): FileNotFoundError("[Errno 2] No such file or directory: 'launchctl'"),
        })
        status = U.install_agent(run, "opencode.ov-studio", "rendered-content", agents_dir, 501)
        self.assertTrue(status.startswith("error: "))
        self.assertIn("No such file or directory", status)

    def test_bootstrap_raises_timeout_returns_error(self):
        agents_dir = self._agents_dir()
        run = FakeRun({
            ("launchctl", "print"): Result(113),
            ("launchctl", "bootstrap"): subprocess.TimeoutExpired(cmd=["launchctl", "bootstrap"], timeout=30),
        })
        status = U.install_agent(run, "opencode.ov-studio", "rendered-content", agents_dir, 501)
        self.assertTrue(status.startswith("error: "))
        self.assertNotIn("\n", status)

    def test_agents_dir_creation_failure_returns_error(self):
        # agents_dir exists as a plain file, so mkdir(parents=True, exist_ok=True) raises OSError.
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        agents_dir = tmp / "not-a-directory"
        agents_dir.write_text("blocking file")
        run = FakeRun({("launchctl", "print"): Result(113)})
        status = U.install_agent(run, "opencode.ov-studio", "rendered-content", agents_dir, 501)
        self.assertTrue(status.startswith("error: "))

    def test_read_existing_plist_oserror_returns_error(self):
        agents_dir = self._agents_dir()
        target = agents_dir / "opencode.ov-studio.plist"
        target.write_text("rendered-content")
        os.chmod(target, 0)
        self.addCleanup(os.chmod, target, 0o644)
        run = FakeRun({("launchctl", "print"): Result(0)})
        status = U.install_agent(run, "opencode.ov-studio", "rendered-content", agents_dir, 501)
        self.assertTrue(status.startswith("error: "))


class InstallAgents(unittest.TestCase):
    def _dirs(self):
        templates_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, templates_dir, True)
        agents_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, agents_dir, True)
        return templates_dir, agents_dir

    def test_returns_both_agents_in_order(self):
        templates_dir, agents_dir = self._dirs()
        (templates_dir / "opencode.ov-studio.plist").write_text(_plist("opencode.ov-studio"))
        (templates_dir / "opencode.ov-syncd.plist").write_text(_plist("opencode.ov-syncd"))

        run = FakeRun({
            ("launchctl", "print"): Result(113),
            ("launchctl", "bootstrap"): Result(0),
        })
        results = U.install_agents(run, templates_dir, agents_dir, "/Users/test", 501)
        self.assertEqual(
            results,
            [("ov-studio", "installed"), ("ov-syncd", "installed")],
        )

    def test_label_comes_from_plist_not_filename(self):
        templates_dir, agents_dir = self._dirs()
        (templates_dir / "weird-name.plist").write_text(_plist("opencode.ov-weird"))

        run = FakeRun({
            ("launchctl", "print"): Result(113),
            ("launchctl", "bootstrap"): Result(0),
        })
        results = U.install_agents(run, templates_dir, agents_dir, "/Users/test", 501)
        self.assertEqual(results, [("ov-weird", "installed")])
        self.assertTrue((agents_dir / "opencode.ov-weird.plist").exists())
        self.assertFalse((agents_dir / "weird-name.plist").exists())

    def test_print_file_not_found_for_one_agent_does_not_stop_the_other(self):
        templates_dir, agents_dir = self._dirs()
        (templates_dir / "opencode.ov-studio.plist").write_text(_plist("opencode.ov-studio"))
        (templates_dir / "opencode.ov-syncd.plist").write_text(_plist("opencode.ov-syncd"))

        def run(argv, **kwargs):
            if argv[:2] == ["launchctl", "print"] and "ov-studio" in argv[2]:
                raise FileNotFoundError("[Errno 2] No such file or directory: 'launchctl'")
            if argv[:2] == ["launchctl", "print"]:
                return Result(113)
            if argv[:2] == ["launchctl", "bootstrap"]:
                return Result(0)
            raise AssertionError(f"unexpected argv {argv}")

        results = U.install_agents(run, templates_dir, agents_dir, "/Users/test", 501)
        self.assertEqual(results[0][0], "ov-studio")
        self.assertTrue(results[0][1].startswith("error: "))
        self.assertEqual(results[1], ("ov-syncd", "installed"))

    def test_bootstrap_timeout_for_one_agent_does_not_stop_the_other(self):
        templates_dir, agents_dir = self._dirs()
        (templates_dir / "opencode.ov-studio.plist").write_text(_plist("opencode.ov-studio"))
        (templates_dir / "opencode.ov-syncd.plist").write_text(_plist("opencode.ov-syncd"))

        def run(argv, **kwargs):
            if argv[:2] == ["launchctl", "print"]:
                return Result(113)
            if argv[:2] == ["launchctl", "bootstrap"] and "ov-studio" in argv[3]:
                raise subprocess.TimeoutExpired(cmd=argv, timeout=30)
            if argv[:2] == ["launchctl", "bootstrap"]:
                return Result(0)
            raise AssertionError(f"unexpected argv {argv}")

        results = U.install_agents(run, templates_dir, agents_dir, "/Users/test", 501)
        self.assertEqual(results[0][0], "ov-studio")
        self.assertTrue(results[0][1].startswith("error: "))
        self.assertEqual(results[1], ("ov-syncd", "installed"))


class InstallAgentsErrors(unittest.TestCase):
    def _dirs(self):
        templates_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, templates_dir, True)
        agents_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, agents_dir, True)
        return templates_dir, agents_dir

    def _run_ok(self):
        return FakeRun({
            ("launchctl", "print"): Result(113),
            ("launchctl", "bootstrap"): Result(0),
        })

    def test_template_read_oserror_reports_error_and_continues(self):
        templates_dir, agents_dir = self._dirs()
        bad = templates_dir / "opencode.ov-broken.plist"
        bad.write_text(_plist("opencode.ov-broken"))
        os.chmod(bad, 0)
        self.addCleanup(os.chmod, bad, 0o644)
        (templates_dir / "opencode.ov-studio.plist").write_text(_plist("opencode.ov-studio"))

        results = U.install_agents(self._run_ok(), templates_dir, agents_dir, "/Users/test", 501)
        names = dict(results)
        self.assertTrue(names["ov-broken"].startswith("error: "))
        self.assertEqual(names["ov-studio"], "installed")

    def test_template_substitution_error_reports_error_and_continues(self):
        templates_dir, agents_dir = self._dirs()
        (templates_dir / "opencode.ov-broken.plist").write_text("${MISSING}")
        (templates_dir / "opencode.ov-studio.plist").write_text(_plist("opencode.ov-studio"))

        results = U.install_agents(self._run_ok(), templates_dir, agents_dir, "/Users/test", 501)
        names = dict(results)
        self.assertTrue(names["ov-broken"].startswith("error: "))
        self.assertEqual(names["ov-studio"], "installed")

    def test_plist_parse_error_reports_error_and_continues(self):
        templates_dir, agents_dir = self._dirs()
        (templates_dir / "opencode.ov-broken.plist").write_text("not a plist")
        (templates_dir / "opencode.ov-studio.plist").write_text(_plist("opencode.ov-studio"))

        results = U.install_agents(self._run_ok(), templates_dir, agents_dir, "/Users/test", 501)
        names = dict(results)
        self.assertTrue(names["ov-broken"].startswith("error: "))
        self.assertEqual(names["ov-studio"], "installed")

    def test_missing_label_reports_error_and_continues(self):
        templates_dir, agents_dir = self._dirs()
        (templates_dir / "opencode.ov-broken.plist").write_text(
            plistlib.dumps({"NotLabel": "x"}).decode()
        )
        (templates_dir / "opencode.ov-studio.plist").write_text(_plist("opencode.ov-studio"))

        results = U.install_agents(self._run_ok(), templates_dir, agents_dir, "/Users/test", 501)
        names = dict(results)
        self.assertTrue(names["ov-broken"].startswith("error: "))
        self.assertEqual(names["ov-studio"], "installed")

    def test_truncated_xml_template_reports_error_and_continues(self):
        # plistlib.loads raises xml.parsers.expat.ExpatError on truncated XML, not ValueError.
        templates_dir, agents_dir = self._dirs()
        (templates_dir / "opencode.ov-broken.plist").write_text(
            '<?xml version="1.0"?><plist><dict><key>Label'
        )
        (templates_dir / "opencode.ov-studio.plist").write_text(_plist("opencode.ov-studio"))

        results = U.install_agents(self._run_ok(), templates_dir, agents_dir, "/Users/test", 501)
        names = dict(results)
        self.assertTrue(names["ov-broken"].startswith("error: "))
        self.assertEqual(names["ov-studio"], "installed")

    def test_non_dict_root_reports_error_and_continues(self):
        # A plist whose root is a list raises TypeError on the ["Label"] lookup.
        templates_dir, agents_dir = self._dirs()
        (templates_dir / "opencode.ov-broken.plist").write_text(plistlib.dumps([1, 2, 3]).decode())
        (templates_dir / "opencode.ov-studio.plist").write_text(_plist("opencode.ov-studio"))

        results = U.install_agents(self._run_ok(), templates_dir, agents_dir, "/Users/test", 501)
        names = dict(results)
        self.assertTrue(names["ov-broken"].startswith("error: "))
        self.assertEqual(names["ov-studio"], "installed")

    def test_non_string_label_reports_error_and_continues(self):
        # A non-string Label raises AttributeError on label.startswith(...).
        templates_dir, agents_dir = self._dirs()
        (templates_dir / "opencode.ov-broken.plist").write_text(plistlib.dumps({"Label": 5}).decode())
        (templates_dir / "opencode.ov-studio.plist").write_text(_plist("opencode.ov-studio"))

        results = U.install_agents(self._run_ok(), templates_dir, agents_dir, "/Users/test", 501)
        names = dict(results)
        self.assertTrue(names["ov-broken"].startswith("error: "))
        self.assertEqual(names["ov-studio"], "installed")


class LoginItems(unittest.TestCase):
    LIST_ARGV = [
        "osascript",
        "-e",
        'tell application "System Events" to get the name of every login item',
    ]

    def test_parses_stdout(self):
        run = FakeRun({("osascript", "-e"): Result(0, stdout="Docker, Ollama\n")})
        self.assertEqual(U.login_items(run), ["Docker", "Ollama"])
        self.assertEqual(run.calls, [self.LIST_ARGV])

    def test_empty_stdout_returns_empty_list(self):
        run = FakeRun({("osascript", "-e"): Result(0, stdout="")})
        self.assertEqual(U.login_items(run), [])

    def test_nonzero_exit_returns_none(self):
        run = FakeRun({("osascript", "-e"): Result(1, stderr="boom")})
        self.assertIsNone(U.login_items(run))

    def test_file_not_found_returns_none(self):
        run = FakeRun({("osascript", "-e"): FileNotFoundError("no osascript")})
        self.assertIsNone(U.login_items(run))


class EnsureLoginItems(unittest.TestCase):
    ADD_OLLAMA_ARGV = [
        "osascript",
        "-e",
        'tell application "System Events" to make login item at end with properties '
        '{path:"/Applications/Ollama.app", hidden:true}',
    ]
    PERMISSION_ERROR = "Not authorized to send Apple events to System Events. (-1743)"

    def test_all_present_returns_ok_and_adds_nothing(self):
        calls = []

        def run(argv, **kwargs):
            calls.append(argv)
            return Result(0, stdout="Docker, Ollama\n")

        self.assertEqual(U.ensure_login_items(run), ("login items: ok", True))
        self.assertEqual(len(calls), 1)

    def test_missing_ollama_is_added(self):
        calls = []

        def run(argv, **kwargs):
            calls.append(argv)
            if "get the name of every login item" in argv[2]:
                return Result(0, stdout="Docker\n")
            return Result(0)

        self.assertEqual(U.ensure_login_items(run), ("login items: added Ollama", True))
        self.assertIn(self.ADD_OLLAMA_ARGV, calls)

    def test_add_failure_returns_manual_line(self):
        def run(argv, **kwargs):
            if "get the name of every login item" in argv[2]:
                return Result(0, stdout="Docker\n")
            return Result(1, stderr=self.PERMISSION_ERROR)

        self.assertEqual(
            U.ensure_login_items(run),
            (
                "login items: add Ollama manually in System Settings, General, Login Items "
                f"({self.PERMISSION_ERROR})",
                False,
            ),
        )

    def test_listing_failure_returns_manual_line_for_both(self):
        def run(argv, **kwargs):
            return Result(1, stderr=self.PERMISSION_ERROR)

        self.assertEqual(
            U.ensure_login_items(run),
            (
                f"login items: cannot read ({self.PERMISSION_ERROR}); "
                "add Docker and Ollama manually in System Settings, General, Login Items",
                False,
            ),
        )

    def test_both_missing_and_both_adds_fail(self):
        def run(argv, **kwargs):
            if "get the name of every login item" in argv[2]:
                return Result(0, stdout="")
            return Result(1, stderr=self.PERMISSION_ERROR)

        self.assertEqual(
            U.ensure_login_items(run),
            (
                "login items: add Docker and Ollama manually in System Settings, General, Login Items "
                f"({self.PERMISSION_ERROR})",
                False,
            ),
        )

    def test_docker_add_fails_ollama_add_succeeds(self):
        def run(argv, **kwargs):
            if "get the name of every login item" in argv[2]:
                return Result(0, stdout="")
            if "Docker.app" in argv[2]:
                return Result(1, stderr=self.PERMISSION_ERROR)
            return Result(0)

        self.assertEqual(
            U.ensure_login_items(run),
            (
                "login items: added Ollama; add Docker manually in System Settings, General, "
                f"Login Items ({self.PERMISSION_ERROR})",
                False,
            ),
        )


class Main(unittest.TestCase):
    def _env_text(self):
        template_text = (REPO / "openviking" / "ov.conf.template").read_text()
        placeholders = sorted(set(re.findall(r"\$\{(\w+)\}", template_text)))
        lines = ["OPENVIKING_API_KEY=k"]
        lines += [f"{name}=dummy-{name.lower()}" for name in placeholders]
        return "\n".join(lines) + "\n"

    def _tmp_home(self):
        home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, home, True)
        (home / ".openviking").mkdir()
        (home / ".openviking" / ".env").write_text(self._env_text())
        return home

    def _agents_dir(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        return d

    def _patched(self, agents_dir, statuses):
        return unittest.mock.patch.multiple(
            U, AGENTS_DIR=agents_dir, install_agents=unittest.mock.Mock(return_value=statuses)
        )

    def test_success_prints_status_lines_and_returns_zero(self):
        home = self._tmp_home()
        calls = []

        def fake(argv, **kwargs):
            calls.append(argv)
            if argv[:2] == ["ollama", "pull"]:
                return Result(0)
            if argv[:2] == ["docker", "compose"]:
                return Result(0)
            if argv[:2] == ["osascript", "-e"]:
                return Result(0, stdout="Docker, Ollama\n")
            raise AssertionError(f"unexpected argv {argv}")

        with self._patched(self._agents_dir(), [("ov-studio", "ok"), ("ov-syncd", "installed")]):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                code = U.main(run=fake, home=home)

        self.assertEqual(code, 0)
        self.assertEqual(
            out.getvalue().splitlines(),
            ["OpenViking: started", "ov-studio: ok", "ov-syncd: installed", "login items: ok"],
        )
        key_path = home / ".openviking" / "mcp-key"
        self.assertEqual(key_path.read_text(), "k")
        self.assertEqual(stat.S_IMODE(key_path.stat().st_mode), 0o600)
        self.assertIn(["ollama", "pull", "bge-m3"], calls)
        self.assertIn(
            ["docker", "compose", "-f", str(REPO / "openviking" / "docker-compose.yml"), "up", "-d"],
            calls,
        )

    def test_login_item_add_failure_still_runs_compose_and_returns_one(self):
        home = self._tmp_home()
        calls = []

        def fake(argv, **kwargs):
            calls.append(argv)
            if argv[:2] == ["ollama", "pull"]:
                return Result(0)
            if argv[:2] == ["docker", "compose"]:
                return Result(0)
            if argv[:2] == ["osascript", "-e"]:
                if "get the name of every login item" in argv[2]:
                    return Result(0, stdout="Docker\n")
                return Result(
                    1, stderr="Not authorized to send Apple events to System Events. (-1743)"
                )
            raise AssertionError(f"unexpected argv {argv}")

        with self._patched(self._agents_dir(), [("ov-studio", "ok"), ("ov-syncd", "installed")]):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                code = U.main(run=fake, home=home)

        self.assertEqual(code, 1)
        self.assertTrue(any(c[:2] == ["docker", "compose"] for c in calls))
        self.assertIn(
            "login items: add Ollama manually in System Settings, General, Login Items "
            "(Not authorized to send Apple events to System Events. (-1743))",
            out.getvalue().splitlines(),
        )

    def test_compose_file_not_modified(self):
        home = self._tmp_home()
        compose_path = REPO / "openviking" / "docker-compose.yml"
        before = compose_path.read_bytes()

        def fake(argv, **kwargs):
            if argv[:2] == ["ollama", "pull"]:
                return Result(0)
            if argv[:2] == ["docker", "compose"]:
                return Result(0)
            if argv[:2] == ["osascript", "-e"]:
                return Result(0, stdout="Docker, Ollama\n")
            raise AssertionError(f"unexpected argv {argv}")

        with self._patched(self._agents_dir(), [("ov-studio", "ok"), ("ov-syncd", "installed")]):
            with contextlib.redirect_stdout(io.StringIO()):
                U.main(run=fake, home=home)

        self.assertEqual(compose_path.read_bytes(), before)

    def test_agent_install_error_still_prints_login_items_and_returns_one(self):
        home = self._tmp_home()

        def fake(argv, **kwargs):
            if argv[:2] == ["ollama", "pull"]:
                return Result(0)
            if argv[:2] == ["docker", "compose"]:
                return Result(0)
            if argv[:2] == ["osascript", "-e"]:
                return Result(0, stdout="Docker, Ollama\n")
            raise AssertionError(f"unexpected argv {argv}")

        with self._patched(
            self._agents_dir(), [("ov-studio", "error: boom"), ("ov-syncd", "installed")]
        ):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                code = U.main(run=fake, home=home)

        self.assertEqual(code, 1)
        lines = out.getvalue().splitlines()
        self.assertIn("ov-studio: error: boom", lines)
        self.assertEqual(lines[-1], "login items: ok")

    def test_template_error_still_prints_login_items_and_returns_one(self):
        home = self._tmp_home()
        templates_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, templates_dir, True)
        (templates_dir / "opencode.ov-broken.plist").write_text(
            '<?xml version="1.0"?><plist><dict><key>Label'
        )
        (templates_dir / "opencode.ov-studio.plist").write_text(_plist("opencode.ov-studio"))
        agents_dir = self._agents_dir()

        def fake(argv, **kwargs):
            if argv[:2] == ["ollama", "pull"]:
                return Result(0)
            if argv[:2] == ["docker", "compose"]:
                return Result(0)
            if argv[:2] == ["launchctl", "print"]:
                return Result(113)
            if argv[:2] == ["launchctl", "bootstrap"]:
                return Result(0)
            if argv[:2] == ["osascript", "-e"]:
                return Result(0, stdout="Docker, Ollama\n")
            raise AssertionError(f"unexpected argv {argv}")

        with unittest.mock.patch.object(U, "LAUNCHD", templates_dir), \
                unittest.mock.patch.object(U, "AGENTS_DIR", agents_dir):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                code = U.main(run=fake, home=home)

        self.assertEqual(code, 1)
        lines = out.getvalue().splitlines()
        self.assertTrue(any(line.startswith("ov-broken: error:") for line in lines))
        self.assertEqual(lines[-1], "login items: ok")

    def test_pull_and_compose_do_not_capture_output(self):
        home = self._tmp_home()
        recorded = []

        def fake(argv, **kwargs):
            recorded.append((list(argv), kwargs))
            if argv[:2] == ["ollama", "pull"]:
                return Result(0)
            if argv[:2] == ["docker", "compose"]:
                return Result(0)
            if argv[:2] == ["osascript", "-e"]:
                return Result(0, stdout="Docker, Ollama\n")
            raise AssertionError(f"unexpected argv {argv}")

        with self._patched(self._agents_dir(), [("ov-studio", "ok"), ("ov-syncd", "installed")]):
            with contextlib.redirect_stdout(io.StringIO()):
                U.main(run=fake, home=home)

        pull_kwargs = next(kwargs for argv, kwargs in recorded if argv[:2] == ["ollama", "pull"])
        compose_kwargs = next(kwargs for argv, kwargs in recorded if argv[:2] == ["docker", "compose"])
        self.assertNotIn("capture_output", pull_kwargs)
        self.assertEqual(pull_kwargs.get("stdout"), subprocess.DEVNULL)
        self.assertNotIn("capture_output", compose_kwargs)
        self.assertNotIn("stdout", compose_kwargs)

    def test_ollama_pull_failure_stops_before_compose(self):
        home = self._tmp_home()
        calls = []

        def fake(argv, **kwargs):
            calls.append(argv)
            if argv[:2] == ["ollama", "pull"]:
                return Result(7)
            raise AssertionError(f"unexpected argv {argv}")

        with self._patched(self._agents_dir(), [("ov-studio", "ok"), ("ov-syncd", "installed")]):
            with contextlib.redirect_stderr(io.StringIO()) as err:
                with self.assertRaises(SystemExit) as ctx:
                    U.main(run=fake, home=home)

        self.assertEqual(ctx.exception.code, 7)
        self.assertIn("ov-up: ollama pull failed with exit 7", err.getvalue())
        self.assertFalse(any(c[:2] == ["docker", "compose"] for c in calls))

    def test_docker_compose_failure_stops_main(self):
        home = self._tmp_home()

        def fake(argv, **kwargs):
            if argv[:2] == ["ollama", "pull"]:
                return Result(0)
            if argv[:2] == ["docker", "compose"]:
                return Result(3)
            raise AssertionError(f"unexpected argv {argv}")

        with self._patched(self._agents_dir(), [("ov-studio", "ok"), ("ov-syncd", "installed")]):
            with contextlib.redirect_stderr(io.StringIO()) as err:
                with self.assertRaises(SystemExit) as ctx:
                    U.main(run=fake, home=home)

        self.assertEqual(ctx.exception.code, 3)
        self.assertIn("ov-up: docker compose failed with exit 3", err.getvalue())

    def test_agents_dir_mkdir_failure_is_handled_per_agent_not_by_main(self):
        # agents_dir sits under a regular file, so mkdir(parents=True) raises NotADirectoryError.
        # An unconditional AGENTS_DIR.mkdir() in main (the removed code) would raise this
        # uncaught and crash before the login items line; install_agent's own try/except must
        # instead turn it into a per-agent error status and let main finish.
        home = self._tmp_home()
        base = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, base, True)
        blocking_file = base / "file.txt"
        blocking_file.write_text("not a directory")
        agents_dir = blocking_file / "LaunchAgents"

        def fake(argv, **kwargs):
            if argv[:2] == ["ollama", "pull"]:
                return Result(0)
            if argv[:2] == ["docker", "compose"]:
                return Result(0)
            if argv[:2] == ["launchctl", "print"]:
                return Result(113)
            if argv[:2] == ["osascript", "-e"]:
                return Result(0, stdout="Docker, Ollama\n")
            raise AssertionError(f"unexpected argv {argv}")

        with unittest.mock.patch.object(U, "AGENTS_DIR", agents_dir):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                code = U.main(run=fake, home=home)

        self.assertEqual(code, 1)
        lines = out.getvalue().splitlines()
        self.assertTrue(any(line.startswith("ov-studio: error:") for line in lines))
        self.assertTrue(any(line.startswith("ov-syncd: error:") for line in lines))
        self.assertEqual(lines[-1], "login items: ok")


if __name__ == "__main__":
    unittest.main()
