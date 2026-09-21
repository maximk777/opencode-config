"""Rules for work records and ADRs."""
from __future__ import annotations

import re
from typing import List, Optional

from wslib.common import Finding, h2_headings, parse_frontmatter
from wslib.rules_keys import lookup

RECORD_KEYS = ["task", "repos", "merge_requests", "commits"]
RECORD_SECTIONS = ["Changed", "Decisions", "Open questions", "Verification"]
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


def _id_pattern(ctx) -> Optional[re.Pattern]:
    data, error = ctx.load_json("tracker/tracker.json")
    if error is not None or not isinstance(data, dict) or not isinstance(data.get("id_pattern"), str):
        return None
    # A bad pattern is reported by json-shape; it must not crash check (e.g. a{4294967296} overflows).
    try:
        return re.compile(data["id_pattern"])
    except (re.error, OverflowError, RecursionError, ValueError):
        return None


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


def _check_record(ctx, name: str, rel: str, repo_names: set) -> List[Finding]:
    def finding(message, line=1):
        return Finding(rel, line, "work-record", message)

    text = ctx.read_text(rel)
    if text is None:
        return [finding("record.md is not readable UTF-8")]
    data, body, error = parse_frontmatter(text)
    if error is not None:
        return [finding(error, _error_line(error))]
    data = data or {}
    findings = []
    for key in RECORD_KEYS:
        if key not in data:
            findings.append(finding("missing frontmatter key %s" % key))
    if "task" in data and data["task"] != name:
        findings.append(finding("task %s does not match directory %s" % (data["task"], name)))
    for key in RECORD_KEYS[1:]:
        if key in data and not isinstance(data[key], list):
            findings.append(finding("%s must be a list" % key))
    if isinstance(data.get("repos"), list):
        for repo in data["repos"]:
            if repo not in repo_names:
                findings.append(finding("repository %s is not in repos.json" % repo))
    headings = set(h2_headings(_body_outside_fences(body)))
    for section in RECORD_SECTIONS:
        if section not in headings:
            findings.append(finding("missing section ## %s" % section))
    return findings


def check_work_record(ctx) -> List[Finding]:
    # directories are the second segment of ctx.files paths under work/ with at least three segments
    names = []
    for rel in ctx.files:
        parts = rel.split("/")
        if len(parts) >= 3 and parts[0] == "work" and parts[1] not in names:
            names.append(parts[1])
    id_re = _id_pattern(ctx)
    repo_names = _repo_names(ctx)
    findings: List[Finding] = []
    for name in names:
        rel = "work/%s/record.md" % name
        if id_re is not None and not id_re.fullmatch(name):
            findings.append(Finding("work/%s" % name, 1, "work-record", "directory name does not match id_pattern"))
        if rel not in ctx.files:
            findings.append(Finding("work/%s" % name, 1, "work-record", "missing record.md"))
            continue
        findings.extend(_check_record(ctx, name, rel, repo_names))
    return findings


def check_adr(ctx) -> List[Finding]:
    # files directly under docs/adr/ except .gitkeep and README.md
    findings: List[Finding] = []
    seen_numbers = set()
    for rel in ctx.files:
        parts = rel.split("/")
        if len(parts) != 3 or parts[:2] != ["docs", "adr"] or parts[2] in (".gitkeep", "README.md"):
            continue

        def finding(message, line=1, rel=rel):
            return Finding(rel, line, "adr", message)

        m = ADR_NAME.match(parts[2])
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


RULES = [("work-record", check_work_record), ("adr", check_adr)]
