"""Paths, markers and per-project state files of the OpenViking sync worker."""
from __future__ import annotations

import copy
import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Dict, Optional

PROJECT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
EMPTY_STATE = {
    "synced_commit": None, "synced_at": None, "files": 0, "duration": 0.0,
    "result": None, "error": None, "running": False, "started_at": None,
    "failures": 0, "failing": False, "failing_head": None, "failing_marker": None,
    "next_attempt": 0.0, "backoff": 0.0, "unavailable_since": None,
    "pending_task": None, "reindexed_commit": None, "reindex_pending": [],
}


class Paths:
    def __init__(self, home: Path, specs: Path, repo: Path):
        self.ov = home / ".openviking"
        self.queue = self.ov / "sync-queue"      # markers, one empty file per project
        self.state = self.ov / "sync-state"      # <project>.json and _nightly.json
        self.log = self.ov / "ov-sync.log"
        self.usage = self.ov / "usage.jsonl"
        self.lock = self.ov / "ov-syncd.lock"
        self.specs = specs                        # ~/specs, or $SPECS_ROOT
        self.stage = specs / ".ov-stage"
        self.scope = repo / "openviking" / "sync-scope"

    @classmethod
    def default(cls, repo: Path) -> "Paths":
        specs = Path(os.environ.get("SPECS_ROOT") or Path.home() / "specs")
        return cls(Path.home(), specs, repo)


def valid_project(name: str) -> bool:
    return bool(name) and bool(PROJECT_RE.match(name)) and ".." not in name


def _check_project(project: str) -> None:
    # Guards every project-keyed path so a caller can never escape sync-queue/sync-state.
    if not valid_project(project):
        raise ValueError(f"invalid project name: {project!r}")


def touch_marker(paths: Paths, project: str, now: Optional[float] = None) -> None:
    _check_project(project)
    paths.queue.mkdir(parents=True, exist_ok=True)
    marker = paths.queue / project
    marker.touch(exist_ok=True)
    if now is not None:
        os.utime(marker, (now, now))


def marker_mtime(paths: Paths, project: str) -> Optional[float]:
    _check_project(project)
    try:
        return (paths.queue / project).stat().st_mtime
    except FileNotFoundError:
        return None


def markers(paths: Paths) -> Dict[str, float]:
    result: Dict[str, float] = {}
    if not paths.queue.is_dir():
        return result
    for entry in paths.queue.iterdir():
        if entry.is_file() and valid_project(entry.name):
            result[entry.name] = entry.stat().st_mtime
    return result


def remove_marker_if_not_newer(paths: Paths, project: str, started_at: float) -> bool:
    _check_project(project)
    marker = paths.queue / project
    try:
        mtime = marker.stat().st_mtime
    except FileNotFoundError:
        return False
    if mtime > started_at:
        return False
    try:
        marker.unlink()
    except FileNotFoundError:
        return False
    return True


def _load_json_object(path: Path, defaults: dict) -> dict:
    # A corrupted or malformed file must not take down the worker for every project.
    data = copy.deepcopy(defaults)
    try:
        with path.open("r", encoding="utf-8") as f:
            loaded = json.load(f)
    except FileNotFoundError:
        return data
    except json.JSONDecodeError:
        return data
    if isinstance(loaded, dict):
        data.update(loaded)
    return data


def read_state(paths: Paths, project: str) -> dict:
    _check_project(project)
    return _load_json_object(paths.state / f"{project}.json", EMPTY_STATE)


def _write_json(path: Path, data: dict) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def write_state(paths: Paths, project: str, data: dict) -> None:
    """Write through a temp file in the same directory and os.replace, so readers never see a partial file."""
    _check_project(project)
    _write_json(paths.state / f"{project}.json", data)


def list_states(paths: Paths) -> Dict[str, dict]:
    result: Dict[str, dict] = {}
    if not paths.state.is_dir():
        return result
    for entry in paths.state.iterdir():
        if entry.suffix == ".json" and valid_project(entry.stem):
            project = entry.stem
            result[project] = read_state(paths, project)
    return result


def read_nightly(paths: Paths) -> dict:
    return _load_json_object(paths.state / "_nightly.json", {"last_date": None})


def write_nightly(paths: Paths, data: dict) -> None:
    _write_json(paths.state / "_nightly.json", data)


def append_log(paths: Paths, project: str, result: str, detail: str, now: Optional[float] = None) -> None:
    """Line format: '<ISO local time> <project> <result> <detail>'."""
    ts = time.time() if now is None else now
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts))
    paths.log.parent.mkdir(parents=True, exist_ok=True)
    with paths.log.open("a", encoding="utf-8") as f:
        f.write(f"{stamp} {project} {result} {detail}\n")


def append_usage(paths: Paths, obj: dict) -> None:
    paths.usage.parent.mkdir(parents=True, exist_ok=True)
    with paths.usage.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
