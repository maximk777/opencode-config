"""State transitions of one sync attempt: backoff, failing and timeout bookkeeping."""
from __future__ import annotations

import copy
from typing import Optional

UNAVAILABLE_START, UNAVAILABLE_MAX = 60.0, 1800.0
LOCKED_START, LOCKED_MAX = 30.0, 300.0
FAILING_AFTER = 3
RETRY_AFTER_FAILURE = 60.0
RETRY_AFTER_GIT_ERROR = 300.0
OUTCOMES = ("ok", "skipped", "failed", "timeout", "unavailable", "locked")


def apply(state: dict, outcome: str, now: float, head: Optional[str] = None,
          marker: Optional[float] = None, task: Optional[dict] = None,
          error: Optional[str] = None, git_error: bool = False) -> dict:
    """Return a new state dict after one attempt; the caller writes it."""
    if outcome not in OUTCOMES:
        raise ValueError(outcome)
    st = copy.deepcopy(state)
    previous = st.get("result")
    had_unavailable_since = st.get("unavailable_since") is not None
    previous_backoff = st.get("backoff", 0.0) or 0.0

    if outcome != "ok" and error is None:
        # Keep whatever error the previous attempt left; only a fresh error replaces it.
        error = st.get("error")

    if outcome == "ok":
        st["failures"] = 0
        st["failing"] = False
        st["backoff"] = 0.0
        st["next_attempt"] = 0.0
        st["unavailable_since"] = None
        st["error"] = None
        st["pending_task"] = None
    elif outcome == "unavailable":
        # A streak of "unavailable" doubles the backoff even across an
        # intervening "skipped" (which never touches unavailable_since);
        # any other result in between clears unavailable_since and restarts it.
        if had_unavailable_since and previous_backoff:
            st["backoff"] = min(previous_backoff * 2, UNAVAILABLE_MAX)
        else:
            st["backoff"] = UNAVAILABLE_START
        if not had_unavailable_since:
            st["unavailable_since"] = now
        st["next_attempt"] = now + st["backoff"]
        st["error"] = error
    elif outcome == "locked":
        if previous == "locked" and previous_backoff:
            st["backoff"] = min(previous_backoff * 2, LOCKED_MAX)
        else:
            st["backoff"] = LOCKED_START
        st["next_attempt"] = now + st["backoff"]
        st["unavailable_since"] = None
        st["error"] = error
    elif outcome == "failed":
        st["failures"] = st.get("failures", 0) + 1
        st["error"] = error
        if st["failures"] >= FAILING_AFTER:
            st["failing"] = True
            st["failing_head"] = head
            st["failing_marker"] = marker
        st["next_attempt"] = now + RETRY_AFTER_FAILURE
        st["unavailable_since"] = None
    elif outcome == "timeout":
        st["pending_task"] = copy.deepcopy(task)
        st["next_attempt"] = now + RETRY_AFTER_FAILURE
        st["unavailable_since"] = None
        st["error"] = error
    elif outcome == "skipped":
        st["error"] = error
        if git_error:
            st["next_attempt"] = now + RETRY_AFTER_GIT_ERROR
        # unavailable_since is left untouched: a git error says nothing about the server.

    st["result"] = outcome
    st["running"] = False
    return st
