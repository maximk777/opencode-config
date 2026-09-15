"""Sync one specs project: mirror HEAD, import in vectors_only, wait for the task, record state."""
from __future__ import annotations

import subprocess
from typing import Callable

from ovsync import due, mirror, nightly, policy, state
from ovsync import openviking as ov

POLL = 5.0
TASK_TIMEOUT = 900.0
TASK_APPEAR = 60.0

_ACTIVE_STATUSES = ("pending", "running")


def _changed(run: Callable, repo, since: str, head: str) -> list:
    try:
        result = run(
            ["git", "diff", "--name-only", f"{since}..{head}"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"git diff failed: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"git diff failed: {detail}" if detail else "git diff failed")
    return [line for line in result.stdout.splitlines() if line]


def _wait(run, clock, sleep, project, started):
    """Return ('completed'|'failed'|'timeout'|'missing'|'unavailable', task or None)."""
    seen = None
    while True:
        task_list = ov.tasks(run)
        task = ov.find_task(task_list, project, started) if task_list is not None else None
        if task is not None:
            seen = task
            status = ov.task_status(task)
            if status == "completed":
                return "completed", task
            if status == "failed":
                return "failed", task
        if seen is not None:
            # Once the task has been observed, a later poll failure must not end the wait: only
            # the 15-minute timeout does, reported against the last confirmed sighting.
            if clock() - started > TASK_TIMEOUT:
                return "timeout", seen
        elif clock() - started > TASK_APPEAR:
            return ("unavailable", None) if task_list is None else ("missing", None)
        sleep(POLL)


def sync_project(paths: state.Paths, project: str, run: Callable, clock: Callable,
                 sleep: Callable, rules) -> dict:
    repo = paths.specs / project
    st = state.read_state(paths, project)

    pending = st.get("pending_task")
    if pending:
        task_list = ov.tasks(run)
        if task_list is None:
            new_st = policy.apply(st, "unavailable", clock(), error="OpenViking unavailable")
            state.write_state(paths, project, new_st)
            state.append_log(paths, project, "unavailable", new_st.get("error") or "")
            return new_st
        match = next(
            (t for t in task_list if isinstance(t, dict) and t.get("task_id") == pending.get("task_id")),
            None,
        )
        if match is not None and ov.task_status(match) in _ACTIVE_STATUSES:
            new_st = dict(st)
            new_st["next_attempt"] = clock() + policy.RETRY_AFTER_FAILURE
            state.write_state(paths, project, new_st)
            state.append_log(paths, project, "timeout", f"blocked by pending task {pending['task_id']}")
            return new_st
        st = dict(st)
        st["pending_task"] = None

    head = due.head_info(run, repo)
    if head is None:
        new_st = policy.apply(st, "skipped", clock(), error="git: HEAD unavailable", git_error=True)
        state.write_state(paths, project, new_st)
        state.append_log(paths, project, "skipped", new_st.get("error") or "")
        return new_st
    head_sha, _head_time = head

    started_at = clock()
    st["running"] = True
    st["started_at"] = started_at
    state.write_state(paths, project, st)

    try:
        count = mirror.build_mirror(run, repo, head_sha, rules, paths.stage, project)
    except RuntimeError as exc:
        reason = f"git: {exc}"
    except (OSError, subprocess.TimeoutExpired) as exc:
        reason = f"mirror: {exc}"
    else:
        reason = None
    if reason is not None:
        new_st = policy.apply(st, "skipped", clock(), error=reason, git_error=True)
        state.write_state(paths, project, new_st)
        state.append_log(paths, project, "skipped", reason)
        return new_st

    if count == 0:
        new_st = policy.apply(st, "skipped", clock(), error="empty selection")
        new_st["synced_commit"] = head_sha
        state.remove_marker_if_not_newer(paths, project, started_at)
        state.write_state(paths, project, new_st)
        state.append_log(paths, project, "skipped", "empty selection")
        return new_st

    if not ov.health(run):
        new_st = policy.apply(st, "unavailable", clock(), error="OpenViking unavailable")
        state.write_state(paths, project, new_st)
        state.append_log(paths, project, "unavailable", new_st.get("error") or "")
        return new_st

    import_failed_text = None
    try:
        result = run(ov.import_cmd(project), capture_output=True, text=True, timeout=120)
    except FileNotFoundError:
        new_st = policy.apply(st, "unavailable", clock(), error="OpenViking unavailable")
        state.write_state(paths, project, new_st)
        state.append_log(paths, project, "unavailable", new_st.get("error") or "")
        return new_st
    except subprocess.TimeoutExpired:
        import_failed_text = "add-resource timed out client-side"
    else:
        if result.returncode != 0:
            output = ((result.stdout or "") + (result.stderr or "")).strip()
            cls = ov.classify(output)
            if cls == "locked":
                new_st = policy.apply(st, "locked", clock(), error=output or "lock acquire timed out")
                state.write_state(paths, project, new_st)
                state.append_log(paths, project, "locked", new_st.get("error") or "")
                return new_st
            if cls == "unavailable":
                new_st = policy.apply(st, "unavailable", clock(), error="OpenViking unavailable")
                state.write_state(paths, project, new_st)
                state.append_log(paths, project, "unavailable", new_st.get("error") or "")
                return new_st
            import_failed_text = output

    wait_status, task = _wait(run, clock, sleep, project, started_at)

    if wait_status == "completed":
        reindex_pending = list(st.get("reindex_pending", []))
        reindexed_commit = st.get("reindexed_commit")
        previous = st.get("synced_commit")
        if previous is None:
            # First sync: the vectors_only import covers HEAD and there is no range to diff.
            if reindexed_commit is None:
                reindexed_commit = head_sha
        else:
            # The range starts at the previous synced_commit, so each synced range is added once;
            # reindexed_commit only records that the nightly emptied the list.
            try:
                changed = _changed(run, repo, previous, head_sha)
            except RuntimeError as exc:
                state.append_log(paths, project, "ok", str(exc))
            else:
                reindex_pending = nightly.merge_pending(reindex_pending, nightly.pending_dirs(changed, rules))
        new_st = policy.apply(st, "ok", clock())
        new_st["synced_commit"] = head_sha
        new_st["synced_at"] = clock()
        new_st["files"] = count
        new_st["duration"] = clock() - started_at
        new_st["reindexed_commit"] = reindexed_commit
        new_st["reindex_pending"] = reindex_pending
        state.remove_marker_if_not_newer(paths, project, started_at)
        state.write_state(paths, project, new_st)
        state.append_log(paths, project, "ok", f"files={count}")
        return new_st

    if wait_status == "timeout":
        minimal_task = {"task_id": task["task_id"], "created_at": task["created_at"]}
        new_st = policy.apply(
            st, "timeout", clock(), task=minimal_task, error=f"task {task['task_id']} timed out",
        )
        state.write_state(paths, project, new_st)
        state.append_log(paths, project, "timeout", new_st.get("error") or "")
        return new_st

    if wait_status == "unavailable":
        new_st = policy.apply(st, "unavailable", clock(), error="OpenViking unavailable")
        state.write_state(paths, project, new_st)
        state.append_log(paths, project, "unavailable", new_st.get("error") or "")
        return new_st

    if wait_status == "failed":
        error = f"task {task['task_id']} failed"
    else:
        error = import_failed_text or "no add_resource task appeared"
    marker = state.marker_mtime(paths, project)
    new_st = policy.apply(st, "failed", clock(), head=head_sha, marker=marker, error=error)
    state.write_state(paths, project, new_st)
    state.append_log(paths, project, "failed", error)
    return new_st
