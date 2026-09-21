"""Rule: task state fields are consistent, workspace tasks hold no epics, and a task folder keeps one work.md."""
from __future__ import annotations

import datetime
import posixpath
from typing import List

from wslib.common import Finding
from wslib.model import Workspace

RULE = "task-state"
STATUSES = ("waiting", "in_progress", "done")
TYPES = ("epic", "story", "task", "bug", "spike", "architecture", "e2e")
STATE_FIELDS = ("owner", "started")
RECORD_NAME = "work.md"


def _field_line(text: str, field: str) -> int:
    lines = text.split("\n")
    for i, line in enumerate(lines[1:], start=2):
        if line == "---":
            break
        if line.startswith(field + ":"):
            return i
    return 1


def _is_empty(value) -> bool:
    # A missing frontmatter field (None) counts as empty, like an explicit empty value.
    return value is None or value == "" or value == [] or value == {}


def _records_in(ctx, folder: str) -> List[str]:
    prefix = folder + "/"
    return [
        rel for rel in ctx.files
        if rel.startswith(prefix) and posixpath.basename(rel) == RECORD_NAME
    ]


def _check_task(ws, task, in_stream: bool) -> List[Finding]:
    # A broken or missing frontmatter is reported by the story rule; state checks need parsed fields.
    if task.error is not None or task.fields is None:
        return []
    text = ws.ctx.read_text(task.path) or ""
    fields = task.fields
    findings: List[Finding] = []

    def add(field: str, message: str) -> None:
        findings.append(Finding(task.path, _field_line(text, field), RULE, message))

    status = fields.get("status")
    if status not in STATUSES:
        add("status", "field status is %r, expected one of %s" % (status, ", ".join(STATUSES)))
    for field in STATE_FIELDS:
        empty = _is_empty(fields.get(field))
        if status == "in_progress" and empty:
            add(field, "field %s must not be empty while status is in_progress" % field)
        if status != "in_progress" and not empty:
            add(field, "field %s must be empty while status is not in_progress" % field)
    started = fields.get("started")
    if isinstance(started, str) and started:
        try:
            if datetime.date.fromisoformat(started) > datetime.date.today():
                add("started", "started date %s is in the future" % started)
        except ValueError:
            # A started value that is not a date is left to the rules owning frontmatter shapes.
            pass
    kind = fields.get("type")
    if kind not in TYPES:
        add("type", "field type is %r, expected one of %s" % (kind, ", ".join(TYPES)))
    elif kind == "epic" and not in_stream:
        add("type", "type epic is only allowed inside a stream")
    records = _records_in(ws.ctx, posixpath.dirname(task.path))
    if len(records) > 1:
        findings.append(
            Finding(task.path, 1, RULE, "task folder holds %d %s files (%s)" % (len(records), RECORD_NAME, ", ".join(records)))
        )
    return findings


def check_tasks(ctx) -> List[Finding]:
    ws = Workspace(ctx)
    findings: List[Finding] = []
    for story in ws.stories.values():
        findings.extend(_check_task(ws, story, in_stream=True))
    for task in ws.tasks.values():
        findings.extend(_check_task(ws, task, in_stream=False))
    return findings


RULES = [(RULE, check_tasks)]
