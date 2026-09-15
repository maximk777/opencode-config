"""Decide which specs projects the OpenViking sync worker should run now."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

MARKER_DEBOUNCE = 90.0
COMMIT_SETTLE = 120.0
STALE_RUN = 1800.0


def list_projects(specs: Path) -> List[str]:
    if not specs.exists():
        return []
    projects = []
    for entry in specs.iterdir():
        if entry.name.startswith("."):
            continue
        if entry.is_symlink():
            continue
        if not entry.is_dir():
            continue
        if (entry / ".git").exists():
            projects.append(entry.name)
    return sorted(projects)


def head_info(run: Callable, repo: Path) -> Optional[Tuple[str, float]]:
    """Return (commit sha, commit epoch seconds) of HEAD, or None when git cannot tell."""
    try:
        result = run(
            ["git", "log", "-1", "--format=%H %ct"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    stdout = result.stdout.strip()
    if not stdout:
        return None
    parts = stdout.split()
    if len(parts) != 2:
        return None
    sha, epoch = parts
    try:
        return (sha, float(epoch))
    except ValueError:
        return None


def is_due(project: str, head: Optional[Tuple[str, float]], st: dict, marker: Optional[float], now: float) -> bool:
    """The four conditions of conventions "Due rules", with defaults for missing state keys."""
    if st.get("running", False):
        started_at = st.get("started_at")
        # A missing started_at while running cannot be timed, so treat it as
        # an already-stale (crashed) run rather than blocking forever.
        if started_at is not None and (now - started_at) <= STALE_RUN:
            return False

    if now < st.get("next_attempt", 0.0):
        return False

    if st.get("failing", False):
        failing_head = st.get("failing_head")
        failing_marker = st.get("failing_marker")
        # An unknown head (git failed) must never read as "differs" from
        # failing_head: only a confirmed sha change lifts the failing gate.
        head_changed = head is not None and head[0] != failing_head
        marker_advanced = marker is not None and (failing_marker is None or marker > failing_marker)
        if not head_changed and not marker_advanced:
            return False

    marker_due = marker is not None and (now - marker) > MARKER_DEBOUNCE

    commit_due = False
    if head is not None:
        head_sha, head_time = head
        if head_sha != st.get("synced_commit") and (now - head_time) > COMMIT_SETTLE:
            commit_due = True

    return marker_due or commit_due


def due_projects(projects: List[str], heads: Dict[str, Optional[Tuple[str, float]]],
                 states: Dict[str, dict], markers: Dict[str, float], now: float) -> List[str]:
    candidates = [
        p for p in projects
        if is_due(p, heads.get(p), states.get(p, {}), markers.get(p), now)
    ]
    with_marker = sorted((p for p in candidates if p in markers), key=lambda p: markers[p])
    without_marker = sorted(p for p in candidates if p not in markers)
    return with_marker + without_marker
