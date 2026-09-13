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
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = S.sync("demo", run=runner)
        return code, out.getvalue()

    def test_docker_missing_is_skipped(self):
        def boom(*a, **k):
            raise FileNotFoundError("docker")
        code, out = self.run_sync(boom)
        self.assertEqual(code, 0)
        self.assertIn("openviking unavailable, skipped", out)

    def test_failed_command_is_skipped(self):
        code, out = self.run_sync(lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "no container"))
        self.assertEqual(code, 0)
        self.assertIn("skipped", out)

    def test_success(self):
        code, out = self.run_sync(lambda *a, **k: subprocess.CompletedProcess(a, 0, "ok", ""))
        self.assertEqual(code, 0)
        self.assertIn("synced viking://resources/demo/specs", out)


if __name__ == "__main__":
    unittest.main()
