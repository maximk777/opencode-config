"""Render the status queue sections of STATUS.md between status markers."""
from __future__ import annotations

import datetime
import posixpath
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from wslib.common import Context, parse_frontmatter
from wslib.model import Workspace

RECORD_NAME = "work.md"
RECENT_DAYS = 30
SECTIONS = ("in-progress", "waiting", "done-recently", "drift")
# Workspace tasks sit outside every project and stream; they share one waiting group.
WORKSPACE_GROUP = "workspace"
STATUS_REL = "STATUS.md"


def marker(name: str) -> Tuple[str, str]:
    """Return the (begin, end) marker lines of a status section."""
    return "<!-- status:%s:begin -->" % name, "<!-- status:%s:end -->" % name


def has_markers(text: str) -> bool:
    """True when some line of text equals the begin marker of a status section."""
    lines = text.split("\n")
    return any(marker(name)[0] in lines for name in SECTIONS)


def has_all_markers(text: str) -> bool:
    """True when every status section has both of its markers on their own lines."""
    lines = text.split("\n")
    return all(begin in lines and end in lines for begin, end in map(marker, SECTIONS))


def _usable(item) -> bool:
    return item.error is None and item.fields is not None


def _usable_stories_tasks(ws: Workspace) -> Tuple[List, List]:
    stories = [s for s in ws.stories.values() if _usable(s)]
    tasks = [t for t in ws.tasks.values() if _usable(t)]
    return stories, tasks


def _field(item, name: str) -> str:
    value = item.fields.get(name)
    return value if isinstance(value, str) else ""


def _link(item) -> str:
    return "[%s](%s)" % (item.key, item.path)


def _in_progress_rows(stories, tasks) -> List[str]:
    active = [t for t in stories + tasks if t.fields.get("status") == "in_progress"]
    active.sort(key=lambda t: (_field(t, "owner"), _field(t, "started"), t.key))
    lines: List[str] = []
    owner = None
    for item in active:
        name = _field(item, "owner") or "(unowned)"
        if name != owner:
            if lines:
                lines.append("")
            owner = name
            lines += ["### %s" % name, "", "| Task | Started |", "|---|---|"]
        lines.append("| %s | %s |" % (_link(item), _field(item, "started")))
    return lines


def _waiting_group(item) -> str:
    if not hasattr(item, "stream"):
        return WORKSPACE_GROUP
    return "%s/%s/%s" % (item.project, item.domain, item.stream)


def _waiting_rows(stories, tasks) -> List[str]:
    entries = [
        (_waiting_group(item), item)
        for item in stories + tasks
        if item.fields.get("status") == "waiting"
    ]
    lines: List[str] = []
    for group in sorted({name for name, _ in entries}):
        if lines:
            lines.append("")
        lines += ["### %s" % group, "", "| Task |", "|---|"]
        ordered = sorted(entries, key=lambda entry: entry[1].key)
        lines += ["| %s |" % _link(item) for name, item in ordered if name == group]
    return lines


def _recorded(ctx: Context, item) -> Optional[datetime.date]:
    rel = posixpath.dirname(item.path) + "/" + RECORD_NAME
    if rel not in ctx.files:
        return None
    data, _body, _error = parse_frontmatter(ctx.read_text(rel) or "")
    value = data.get("recorded") if isinstance(data, dict) else None
    if not isinstance(value, str):
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        return None


def _done_recently_rows(ctx: Context, stories, tasks, today: datetime.date) -> List[str]:
    # The window counts today as day zero, so a record dated today - RECENT_DAYS still counts.
    cutoff = today - datetime.timedelta(days=RECENT_DAYS)
    rows = []
    for item in stories + tasks:
        if item.fields.get("status") != "done":
            continue
        recorded = _recorded(ctx, item)
        # A future record date is bad data; the work-record rule owns reporting it.
        if recorded is None or recorded > today or recorded < cutoff:
            continue
        rows.append((recorded, item))
    rows.sort(key=lambda pair: pair[1].key)
    # Stable second pass: recorded descending, key ascending within one day.
    rows.sort(key=lambda pair: pair[0], reverse=True)
    if not rows:
        return []
    return ["| Task | Recorded |", "|---|---|"] + [
        "| %s | %s |" % (_link(item), recorded.isoformat()) for recorded, item in rows
    ]


def _replace(lines: List[str], name: str, content: List[str]) -> List[str]:
    begin, end = marker(name)
    try:
        start = lines.index(begin)
        stop = lines.index(end, start + 1)
    except ValueError:
        # A section without its marker pair is hand territory; has_markers gated the file already.
        return lines
    return lines[: start + 1] + content + lines[stop:]


def render(root) -> Dict[str, bytes]:
    """Return STATUS.md with regenerated sections keyed by POSIX path; skip files without markers."""
    root = Path(root)
    try:
        text = (root / STATUS_REL).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    if not has_markers(text):
        return {}
    ctx = Context(root)
    ws = Workspace(ctx)
    stories, tasks = _usable_stories_tasks(ws)
    lines = text.split("\n")
    for name, content in (
        ("in-progress", _in_progress_rows(stories, tasks)),
        ("waiting", _waiting_rows(stories, tasks)),
        ("done-recently", _done_recently_rows(ctx, stories, tasks, datetime.date.today())),
        ("drift", []),  # Empty by design: the seam reserved for the repository resync candidate.
    ):
        lines = _replace(lines, name, content)
    return {STATUS_REL: "\n".join(lines).encode("utf-8")}
