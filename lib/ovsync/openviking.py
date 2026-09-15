"""Commands and output parsing for the OpenViking CLI inside the openviking container."""
from __future__ import annotations

import json
import re
import subprocess
from typing import Callable, List, Optional

PREFIX = ["docker", "exec", "openviking", "ov"]

_TASK_STATUSES = {"pending", "running", "completed", "failed"}


def ov(*args: str) -> List[str]:
    return PREFIX + list(args)


def resource_uri(project: str) -> str:
    return f"viking://resources/{project}/specs"


def import_cmd(project: str) -> List[str]:
    return ov(
        "add-resource",
        f"/specs/.ov-stage/{project}",
        "--to",
        resource_uri(project),
        "--processing-mode",
        "vectors_only",
        "--args",
        "parse_mode:no_split",
    )


def reindex_cmd(project: str, directory: str) -> List[str]:
    return ov(
        "reindex",
        f"{resource_uri(project)}/{directory}",
        "--mode",
        "semantic_and_vectors",
        "--recursive",
        "true",
    )


def classify(output: str) -> str:
    if "lock acquire timed out" in output or "CONFLICT" in output:
        return "locked"
    if (
        "No such container" in output
        or "Cannot connect to the Docker daemon" in output
        or "is not running" in output
    ):
        return "unavailable"
    return "error"


def health(run: Callable) -> bool:
    try:
        result = run(ov("health"), capture_output=True, text=True, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _json(run: Callable, *args: str) -> Optional[object]:
    """Run an ov command with -o json; None on missing docker, timeout, non-zero exit or bad JSON."""
    try:
        result = run(ov(*args, "-o", "json"), capture_output=True, text=True, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict) or not data.get("ok"):
        return None
    return data.get("result")


def tasks(run: Callable) -> Optional[list]:
    result = _json(run, "task", "list")
    if not isinstance(result, list):
        return None
    return result


def find_task(task_list: list, project: str, started_at: float) -> Optional[dict]:
    uri = resource_uri(project)
    candidates = []
    for t in task_list:
        if not isinstance(t, dict):
            continue
        created_at = t.get("created_at")
        if not isinstance(created_at, (int, float)):
            continue
        if (
            t.get("task_type") == "add_resource"
            and t.get("resource_id") == uri
            and created_at >= started_at - 5
        ):
            candidates.append(t)
    if not candidates:
        return None
    return max(candidates, key=lambda t: t["created_at"])


def task_status(task: dict) -> str:
    if not isinstance(task, dict):
        return "running"
    status = task.get("status")
    return status if status in _TASK_STATUSES else "running"


def _table_calls(status_text: str, model_name: str) -> Optional[int]:
    # ov observer output embeds an ASCII table as a "status" string; the
    # Calls column is the third "|"-separated cell after the model name.
    match = re.search(
        rf"\|\s*{re.escape(model_name)}\s*\|\s*\S+\s*\|\s*(\d+)\s*\|", status_text
    )
    return int(match.group(1)) if match else None


def models(run: Callable) -> Optional[dict]:
    result = _json(run, "observer", "models")
    if not isinstance(result, dict):
        return None
    status_text = result.get("status")
    if not isinstance(status_text, str):
        return None
    vlm_calls = _table_calls(status_text, "deepseek-flash")
    embedding_calls = _table_calls(status_text, "bge-m3")
    if vlm_calls is None or embedding_calls is None:
        return None
    return {"vlm_calls": vlm_calls, "embedding_calls": embedding_calls}


def retrieval(run: Callable) -> Optional[int]:
    result = _json(run, "observer", "retrieval")
    if not isinstance(result, dict):
        return None
    status_text = result.get("status")
    if not isinstance(status_text, str):
        return None
    match = re.search(r"\|\s*Total Queries\s*\|\s*(\d+)\s*\|", status_text)
    return int(match.group(1)) if match else None


def add_resource_count(task_list: list) -> int:
    return sum(
        1 for t in task_list if isinstance(t, dict) and t.get("task_type") == "add_resource"
    )
