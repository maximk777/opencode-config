"""Helpers that create and inspect workspaces for tests."""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_PARAMS = {
    "workspace_name": "demo",
    "title": "Demo workspace",
    "forge": "git",
    "id_pattern": r"TASK-\d+",
    "tracker_url": "https://tracker.example/i/{id}",
}


def kit_command(target, params=None, kit=None):
    """Build the argv for bin/workspace-kit create."""
    params = DEFAULT_PARAMS if params is None else params
    argv = [sys.executable, str(REPO / "bin/workspace-kit"), "create", str(target)]
    for key, value in params.items():
        argv += ["--param", f"{key}={value}"]
    if kit is not None:
        argv += ["--kit", str(kit)]
    return argv


def create_workspace(parent, name="ws", params=None, kit=None) -> Path:
    """Create a workspace under parent, run git init -q in it, return its path; fail the test on non-zero exit."""
    target = Path(parent) / name
    result = subprocess.run(kit_command(target, params, kit), capture_output=True, text=True)
    if result.returncode != 0:
        raise AssertionError(
            f"workspace-kit create exited {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    subprocess.run(["git", "init", "-q"], cwd=target, check=True, capture_output=True, text=True)
    return target


def run_check(ws):
    """Run tools/check.py in ws; return (exit code, stdout lines, stderr)."""
    result = subprocess.run(
        [sys.executable, "tools/check.py"], cwd=ws, capture_output=True, text=True
    )
    return result.returncode, result.stdout.splitlines(), result.stderr


def run_generate(ws):
    """Run tools/generate.py in ws; return the CompletedProcess."""
    return subprocess.run(
        [sys.executable, "tools/generate.py"], cwd=ws, capture_output=True, text=True
    )
