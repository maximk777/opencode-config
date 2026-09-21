"""Rules for work records, task record consistency and ADRs."""
from __future__ import annotations

import datetime
import posixpath
import re
from typing import List, Optional

from wslib.common import Finding, h2_headings, parse_frontmatter
from wslib.model import Workspace
from wslib.rules_keys import lookup

RECORD_KEYS = ["repos", "merge_requests", "commits", "recorded"]
LIST_KEYS = ["repos", "merge_requests", "commits"]
RECORD_SECTIONS = ["Changed", "Decisions", "Open questions", "Verification"]
DONE_QUESTIONS = "None."
RECORD_NAME = "work.md"
TEMPLATE_PREFIX = ".agents/templates/"
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
ADR_NAME = re.compile(r"^(\d{4})-[a-z0-9-]+\.md$")
ADR_STATUSES = {"proposed", "accepted", "superseded"}
FENCE_RE = re.compile(r"^ {0,3}(```|~~~)")
ERROR_LINE_RE = re.compile(r"^frontmatter line (\d+):")


def _error_line(error: str) -> int:
    m = ERROR_LINE_RE.match(error)
    return int(m.group(1)) if m else 1


def _body_outside_fences(body: str) -> str:
    # Records quote command output and examples in fences; a heading there is not a section.
    lines = []
    in_fence = False
    for line in body.split("\n"):
        if FENCE_RE.match(line):
            in_fence = not in_fence
        elif not in_fence:
            lines.append(line)
    return "\n".join(lines)


def _repo_names(ctx) -> set:
    if "repos.json" not in ctx.files:
        return set()
    data, error = ctx.load_json("repos.json")
    if error is not None or not isinstance(data, dict) or not isinstance(data.get("repositories"), list):
        return set()
    return {
        entry["name"] for entry in data["repositories"]
        if isinstance(entry, dict) and isinstance(entry.get("name"), str)
    }


def _is_date(value) -> bool:
    if not isinstance(value, str) or not DATE_RE.fullmatch(value):
        return False
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _check_record(ctx, rel: str, repo_names: set) -> List[Finding]:
    def finding(message, line=1):
        return Finding(rel, line, "work-record", message)

    text = ctx.read_text(rel)
    if text is None:
        return [finding("work.md is not readable UTF-8")]
    data, body, error = parse_frontmatter(text)
    if error is not None:
        return [finding(error, _error_line(error))]
    data = data or {}
    findings = []
    for key in RECORD_KEYS:
        if key not in data:
            findings.append(finding("missing frontmatter key %s" % key))
    for key in LIST_KEYS:
        if key in data and not isinstance(data[key], list):
            findings.append(finding("%s must be a list" % key))
    if isinstance(data.get("repos"), list):
        for repo in data["repos"]:
            if repo not in repo_names:
                findings.append(finding("repository %s is not in repos.json" % repo))
    if "recorded" in data and not _is_date(data["recorded"]):
        findings.append(finding("recorded must be a YYYY-MM-DD date"))
    headings = set(h2_headings(_body_outside_fences(body)))
    for section in RECORD_SECTIONS:
        if section not in headings:
            findings.append(finding("missing section ## %s" % section))
    return findings


def _task_folders(ws) -> dict:
    """Task folder -> task entity of the model; stories and workspace tasks are both tasks here."""
    folders = {}
    for task in list(ws.stories.values()) + list(ws.tasks.values()):
        folders[posixpath.dirname(task.path)] = task
    return folders


def check_work_record(ctx) -> List[Finding]:
    # The model is the single source of task placement; a folder stays a task folder even when its task.md is unreadable.
    folders = _task_folders(Workspace(ctx))
    repo_names = _repo_names(ctx)
    findings: List[Finding] = []
    for rel in ctx.files:
        parts = rel.split("/")
        # A work.md under .agents/templates/ is the kit's record template, not a workspace record.
        if parts[-1] != RECORD_NAME or rel.startswith(TEMPLATE_PREFIX):
            continue
        if "/".join(parts[:-1]) in folders:
            findings.extend(_check_record(ctx, rel, repo_names))
        else:
            findings.append(Finding(rel, 1, "work-record", "work.md outside a task folder"))
    return findings


def _section_text(body: str, heading: str) -> Optional[str]:
    """Trimmed text of an H2 section, or None when the heading is absent."""
    lines: List[str] = []
    active = False
    for line in body.split("\n"):
        if line.startswith("## "):
            if active:
                break
            active = line[3:].strip() == heading
        elif active:
            lines.append(line)
    return "\n".join(lines).strip() if active else None


def check_task_state(ctx) -> List[Finding]:
    """Consistency between a task's done status and the work.md in its folder."""
    findings: List[Finding] = []
    for folder, task in sorted(_task_folders(Workspace(ctx)).items()):
        # Consistency needs parsed fields; unreadable or broken task files are reported by their shape rules.
        fields = task.fields
        if not isinstance(fields, dict):
            continue
        done = fields.get("status") == "done"
        work_rel = folder + "/" + RECORD_NAME
        if work_rel not in ctx.files:
            if done:
                findings.append(Finding(task.path, 1, "task-state", "status is done but the folder has no work.md"))
            continue
        if not done:
            findings.append(Finding(work_rel, 1, "task-state", "work.md in a task folder whose status is not done"))
            continue
        data, body, error = parse_frontmatter(ctx.read_text(work_rel) or "")
        # A broken record is reported by work-record; the done gate reads only well-formed frontmatter.
        merge_requests = data.get("merge_requests") if isinstance(data, dict) else None
        if isinstance(merge_requests, list) and not merge_requests:
            findings.append(
                Finding(work_rel, 1, "task-state", "merge_requests must not be empty when the task is done")
            )
        # A missing section is work-record's finding; the gate fires only when the section says something else.
        questions = None if error is not None else _section_text(body, "Open questions")
        if questions is not None and questions != DONE_QUESTIONS:
            findings.append(
                Finding(work_rel, 1, "task-state", "Open questions must be %s when the task is done" % DONE_QUESTIONS)
            )
    return findings


def check_adr(ctx) -> List[Finding]:
    # ADR files sit directly under docs/adr/ or projects/<key>/adr/; .gitkeep and README.md are placeholders.
    findings: List[Finding] = []
    seen_numbers = set()
    for rel in ctx.files:
        parts = rel.split("/")
        in_adr_dir = (len(parts) == 3 and parts[:2] == ["docs", "adr"]) or (
            len(parts) == 4 and parts[0] == "projects" and parts[2] == "adr"
        )
        if not in_adr_dir or parts[-1] in (".gitkeep", "README.md"):
            continue

        def finding(message, line=1, rel=rel):
            return Finding(rel, line, "adr", message)

        m = ADR_NAME.match(parts[-1])
        if not m:
            findings.append(finding("file name is not NNNN-<slug>.md"))
        elif m.group(1) in seen_numbers:
            findings.append(finding("duplicate ADR number %s" % m.group(1)))
        else:
            seen_numbers.add(m.group(1))

        text = ctx.read_text(rel)
        if text is None:
            findings.append(finding("file is not readable UTF-8"))
            continue
        data, _body, error = parse_frontmatter(text)
        if error is not None:
            findings.append(finding(error, _error_line(error)))
            continue
        data = data or {}
        status = data.get("status")
        if not isinstance(status, str) or status not in ADR_STATUSES:
            findings.append(finding("status %s is not proposed, accepted or superseded" % (status or "(missing)")))
        affects = data.get("affects", [])
        if not isinstance(affects, list):
            findings.append(finding("affects must be a list"))
        else:
            for key in affects:
                if not lookup(ctx, key)[0]:
                    findings.append(finding("affects key %s does not resolve" % key))
        if status == "accepted":
            approved = data.get("approved")
            if not isinstance(approved, dict) or not approved.get("by") or not approved.get("date"):
                findings.append(finding("accepted ADR lacks approved with by and date"))
    return findings


RULES = [("work-record", check_work_record), ("task-state", check_task_state), ("adr", check_adr)]
