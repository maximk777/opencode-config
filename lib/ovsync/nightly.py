"""Nightly usage snapshot and capped summary reindex of changed directories."""
from __future__ import annotations

import posixpath
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Tuple

from ovsync import openviking as ov
from ovsync import scope, state

NIGHT_HOUR = 3
VLM_PER_FILE = 3
ESTIMATE_CAP = 60
ACTUAL_STOP = 80
QUEUE_WAIT = 900.0
POLL = 10.0

_ACTIVE_STATUSES = ("pending", "running")


def pending_dirs(changed: Iterable[str], rules) -> List[str]:
    """Directories under architecture/ or holding a decisions.md among the scope-selected changed paths."""
    result = set()
    for path in changed:
        if not scope.selected(path, rules):
            continue
        directory = posixpath.dirname(path)
        under_architecture = directory == "architecture" or directory.startswith("architecture/")
        holds_decisions = posixpath.basename(path) == "decisions.md"
        if under_architecture or holds_decisions:
            result.add(directory)
    return sorted(result)


def merge_pending(existing: Iterable[str], new: Iterable[str]) -> List[str]:
    return sorted(set(existing) | set(new))


def is_due(nightly_state: dict, now: datetime) -> bool:
    if now.hour < NIGHT_HOUR:
        return False
    if nightly_state.get("last_date") == now.strftime("%Y-%m-%d"):
        return False
    retry_after = nightly_state.get("retry_after")
    if not isinstance(retry_after, (int, float)):
        # A missing or corrupt retry_after must not block the night; treat it as "no retry pending".
        return True
    return now.timestamp() >= retry_after


def count_files(root: Path, directory: str) -> int:
    target = root / directory
    if not target.is_dir():
        return 0
    return sum(1 for p in target.rglob("*") if p.is_file())


def plan(pending: List[str], counts: Dict[str, int], cap: int = ESTIMATE_CAP) -> Tuple[List[str], List[str]]:
    """Greedily fill the cap deepest-first; a directory too big for the remaining budget is skipped, not stopped on."""
    ordered = sorted(pending, key=lambda d: (-d.count("/"), d))
    chosen: List[str] = []
    rest: List[str] = []
    total = 0
    for directory in ordered:
        estimate = counts.get(directory, 0) * VLM_PER_FILE
        if total + estimate <= cap:
            chosen.append(directory)
            total += estimate
        else:
            rest.append(directory)
    return chosen, rest


def snapshot(run: Callable, today: str) -> dict:
    """A snapshot line never fabricates a counter: any missing reading marks the whole line unavailable."""
    models_result = ov.models(run)
    if models_result is None:
        return {"date": today, "unavailable": True}
    retrieval_queries = ov.retrieval(run)
    task_list = ov.tasks(run)
    if retrieval_queries is None or task_list is None:
        return {"date": today, "unavailable": True}
    return {
        "date": today,
        "vlm_calls": models_result["vlm_calls"],
        "embedding_calls": models_result["embedding_calls"],
        "retrieval_queries": retrieval_queries,
        "add_resource_tasks": ov.add_resource_count(task_list),
    }


def wait_idle(run: Callable, clock: Callable, sleep: Callable, timeout: float = QUEUE_WAIT) -> bool:
    """True when `ov task list` shows no pending or running task before the timeout."""
    deadline = clock() + timeout
    while True:
        task_list = ov.tasks(run)
        if task_list is not None and not any(
            isinstance(t, dict) and t.get("status") in _ACTIVE_STATUSES for t in task_list
        ):
            return True
        if clock() >= deadline:
            return False
        sleep(POLL)


def _live_pending(paths: state.Paths, project: str):
    """Project state, pending directories that still hold files in the mirror, and file counts."""
    st = state.read_state(paths, project)
    counts = {d: count_files(paths.stage / project, d) for d in st.get("reindex_pending", [])}
    return st, [d for d, n in counts.items() if n > 0], counts


def _store_pending(paths: state.Paths, project: str, st: dict, pending: Iterable[str]) -> None:
    st["reindex_pending"] = sorted(set(pending))
    if not st["reindex_pending"]:
        st["reindexed_commit"] = st.get("synced_commit")
    state.write_state(paths, project, st)


def _number(value, default):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else default


def run_nightly(paths: state.Paths, run: Callable, clock: Callable, sleep: Callable,
                now_local: Callable[[], datetime], projects: List[str]) -> dict:
    """Snapshot, then reindex pending directories across projects under one daily estimate and actual cap."""
    now = now_local()
    today = now.strftime("%Y-%m-%d")
    nightly_state = state.read_nightly(paths)

    snap = snapshot(run, today)
    if nightly_state.get("snapshot_date") != today:
        state.append_usage(paths, snap)
        nightly_state["snapshot_date"] = today
        state.write_nightly(paths, nightly_state)

    summary = {"date": today, "unavailable": bool(snap.get("unavailable")), "reindexed": {}}
    if snap.get("unavailable"):
        # OpenViking itself is down; retry on the next day's tick rather than a timed retry.
        nightly_state["last_date"] = today
        state.write_nightly(paths, nightly_state)
        return summary

    # The caps are per day and a retried run continues the same day's budget.
    if nightly_state.get("budget_date") != today:
        nightly_state.update(budget_date=today, estimate_used=0, actual_used=0, last_counter=None)
    nightly_state["estimate_used"] = _number(nightly_state.get("estimate_used"), 0)
    nightly_state["actual_used"] = _number(nightly_state.get("actual_used"), 0)
    nightly_state["last_counter"] = _number(nightly_state.get("last_counter"), None)

    if not wait_idle(run, clock, sleep):
        # Other work is using the queue; defer reindexing without consuming today's tick.
        nightly_state["retry_after"] = now.timestamp() + 1800
        state.write_nightly(paths, nightly_state)
        state.append_log(paths, "_nightly", "skipped", "queue busy, nightly reindex retried later")
        state.append_usage(paths, {"date": today, "reindex_vlm": 0, "partial": True})
        summary["retry_after"] = nightly_state["retry_after"]
        summary["vlm_delta"] = 0
        summary["partial"] = True
        return summary
    nightly_state["retry_after"] = None

    # Read the baseline only now, not from the snapshot: other work may run during the wait
    # above, and charging it to tonight's reindex would inflate the actual-cost delta.
    baseline_result = ov.models(run)
    baseline_vlm = baseline_result["vlm_calls"] if baseline_result is not None else snap["vlm_calls"]
    run_delta = 0
    if nightly_state["last_counter"] is not None:
        # An attempt still running at the previous stop finished its work since then; charge
        # that tail now. Unrelated calls in the gap are over-counted, which errs on the safe side.
        tail = max(0, baseline_vlm - nightly_state["last_counter"])
        run_delta += tail
        nightly_state["actual_used"] += tail
    nightly_state["last_counter"] = baseline_vlm
    state.write_nightly(paths, nightly_state)

    stop_all = False
    partial = False

    # Directories with no files in the mirror are gone from the project: they leave the list
    # without a reindex and without charging the estimate.
    live = {project: _live_pending(paths, project) for project in sorted(projects)}
    pick = None
    if nightly_state["estimate_used"] == 0:
        oversize = []
        small = False
        for project, (_, dirs, counts) in live.items():
            for d in dirs:
                if counts[d] * VLM_PER_FILE > ESTIMATE_CAP:
                    oversize.append((-d.count("/"), project, d))
                else:
                    small = True
        oversize_night = nightly_state.get("oversize_night")
        # One oversize directory takes a whole night, alternating with small directories so that
        # neither an oversize directory nor daily small changes elsewhere starve the other.
        after_oversize = isinstance(oversize_night, str) and oversize_night == nightly_state.get("last_date")
        if oversize and not (after_oversize and small):
            _, pick_project, pick_dir = min(oversize)
            pick = (pick_project, pick_dir)

    for project, (st, pending, counts) in live.items():
        if stop_all:
            break
        if not st.get("reindex_pending"):
            continue
        unsaved = len(pending) != len(st["reindex_pending"])
        if pick is None:
            chosen, rest = plan(pending, counts, cap=ESTIMATE_CAP - nightly_state["estimate_used"])
        elif pick[0] == project:
            chosen, rest = [pick[1]], [d for d in pending if d != pick[1]]
        else:
            chosen, rest = [], pending
        left = list(rest)
        reindexed_now = []
        for idx, directory in enumerate(chosen):
            if stop_all or nightly_state["actual_used"] >= ACTUAL_STOP:
                stop_all = True
                left.extend(chosen[idx:])
                break
            if pick == (project, directory):
                nightly_state["oversize_night"] = today
            try:
                result = run(ov.reindex_cmd(project, directory), capture_output=True, text=True, timeout=120)
                exit_ok = result.returncode == 0
            except (subprocess.TimeoutExpired, FileNotFoundError):
                # The client-side call failed, but the server may have started real work;
                # still settle the queue and read the counter so that work counts toward the cap.
                exit_ok = False
            idle = wait_idle(run, clock, sleep)
            after = ov.models(run)
            nightly_state["estimate_used"] += counts.get(directory, 0) * VLM_PER_FILE
            if after is not None:
                delta = max(0, after["vlm_calls"] - baseline_vlm)
                run_delta += delta
                nightly_state["actual_used"] += delta
                baseline_vlm = after["vlm_calls"]
                nightly_state["last_counter"] = baseline_vlm
            # Persist the day's totals at once so a crash or a later stop cannot reset them.
            state.write_nightly(paths, nightly_state)
            if not idle:
                # The queue never settled after this attempt: its remaining cost is charged as the
                # tail on the next run, so stop the whole night rather than start more work.
                left.append(directory)
                left.extend(chosen[idx + 1:])
                _store_pending(paths, project, st, left)
                if reindexed_now:
                    summary["reindexed"][project] = reindexed_now
                state.append_log(
                    paths, "_nightly", "skipped",
                    "queue still busy after reindex, nightly reindex retried later",
                )
                state.append_usage(paths, {"date": today, "reindex_vlm": run_delta, "partial": True})
                nightly_state["retry_after"] = now.timestamp() + 1800
                state.write_nightly(paths, nightly_state)
                summary["vlm_delta"] = run_delta
                summary["partial"] = True
                return summary
            if after is None:
                state.append_log(paths, project, "failed", "vlm counter unavailable, reindex stopped")
                left.append(directory)
                stop_all = True
                partial = True
                continue
            if exit_ok:
                reindexed_now.append(directory)
                _store_pending(paths, project, st, [d for d in pending if d not in reindexed_now])
                unsaved = False
            else:
                left.append(directory)
        if unsaved:
            _store_pending(paths, project, st, left)
        if reindexed_now:
            summary["reindexed"][project] = reindexed_now

    usage_line = {"date": today, "reindex_vlm": run_delta}
    if partial:
        usage_line["partial"] = True
    state.append_usage(paths, usage_line)
    summary["vlm_delta"] = run_delta
    if partial:
        summary["partial"] = True
    nightly_state["last_date"] = today
    state.write_nightly(paths, nightly_state)
    return summary
