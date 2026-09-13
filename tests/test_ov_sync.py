import contextlib
import importlib.machinery
import io
import subprocess
import unittest

S = importlib.machinery.SourceFileLoader("ov_sync", "bin/ov-sync").load_module()


class OvSync(unittest.TestCase):
    def test_command(self):
        self.assertEqual(S.build_command("demo"), [
            "docker", "exec", "openviking", "ov", "add-resource", "/specs/demo",
            "--to", "viking://resources/demo/specs", "--args", "parse_mode:no_split",
        ])

    def run_sync(self, runner):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = S.sync("demo", run=runner)
        self.stderr = err.getvalue()
        return code, out.getvalue()

    def test_docker_missing_is_skipped(self):
        def boom(*a, **k):
            raise FileNotFoundError("docker")
        code, out = self.run_sync(boom)
        self.assertEqual(code, 0)
        self.assertIn("docker not installed, skipped", out)

    def test_failed_command_surfaces_stderr(self):
        code, out = self.run_sync(lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "Error: No such container: openviking\n"))
        self.assertEqual(code, 1)
        self.assertIn("No such container: openviking", self.stderr)
        self.assertIn("exit 1", self.stderr)
        self.assertNotIn("synced", out)

    def test_timeout_fails(self):
        def slow(*a, **k):
            raise subprocess.TimeoutExpired("docker", 600)
        code, _ = self.run_sync(slow)
        self.assertEqual(code, 1)
        self.assertIn("timed out", self.stderr)

    def test_success(self):
        code, out = self.run_sync(lambda *a, **k: subprocess.CompletedProcess(a, 0, "ok", ""))
        self.assertEqual(code, 0)
        self.assertIn("synced viking://resources/demo/specs", out)


if __name__ == "__main__":
    unittest.main()
