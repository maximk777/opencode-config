"""Core stage-gate predicates: function(ws, stream, profile, params) -> List[Issue]."""
from __future__ import annotations

import datetime
import re
from collections import namedtuple
from typing import Dict, List, Optional

from wslib import tables
from wslib.common import parse_frontmatter

Issue = namedtuple("Issue", "path line detail")

DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
ERROR_LINE_RE = re.compile(r"line (\d+)")


def _dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value) -> list:
    return value if isinstance(value, list) else []


def _str_param(params, name: str, default: str) -> str:
    value = _dict(params).get(name)
    return value if isinstance(value, str) else default


def _element_specs(profile) -> Dict[str, dict]:
    return {
        spec["kind"]: spec
        for spec in _list(_dict(profile).get("elements"))
        if isinstance(spec, dict) and isinstance(spec.get("kind"), str)
    }


def _domain_elements(ws, stream, profile) -> list:
    kinds = _element_specs(profile)
    return [e for e in ws.element_list if e.domain == stream.domain and e.kind in kinds]


def _field_line(ws, rel: str, field: str) -> int:
    """Line of `field:` inside the frontmatter of rel, or 1."""
    text = ws.ctx.read_text(rel) or ""
    lines = text.split("\n")
    if not lines or lines[0] != "---":
        return 1
    for i in range(1, len(lines)):
        if lines[i] == "---":
            break
        if lines[i].startswith(field + ":"):
            return i + 1
    return 1


def _scope_list(value) -> Optional[List[str]]:
    # `scope:` with no value parses as "" and counts as an empty scope.
    if value == "":
        return []
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    return None


def _broken_story(story) -> Optional[Issue]:
    if isinstance(story.fields, dict):
        return None
    return Issue(story.path, 1, "story frontmatter does not parse: %s" % (story.error or "no frontmatter"))


def _skip(stream) -> bool:
    return not isinstance(getattr(stream, "data", None), dict)


def approval(ws, stream, profile, params) -> List[Issue]:
    if _skip(stream):
        return []
    stage = _dict(params).get("stage")
    for mark in _list(stream.data.get("approvals")):
        if not isinstance(mark, dict) or mark.get("stage") != stage:
            continue
        by, date = mark.get("by"), mark.get("date")
        if not isinstance(by, str) or not by.strip() or not isinstance(date, str) or not DATE_RE.fullmatch(date):
            continue
        try:
            datetime.date(int(date[:4]), int(date[5:7]), int(date[8:]))
        except ValueError:
            continue
        return []
    return [Issue(stream.path, 1, "no approval mark for stage %s with by and a YYYY-MM-DD date" % (stage,))]


def epic_sections(ws, stream, profile, params) -> List[Issue]:
    if _skip(stream):
        return []
    required = [s for s in _list(_dict(_dict(profile).get("epic")).get("sections")) if isinstance(s, str)]
    if not required:
        return []
    text = ws.ctx.read_text(stream.epic_path) if stream.epic_path in ws.ctx.files else None
    if text is None:
        return [Issue(stream.epic_path, 1, "epic.md is missing")]
    headings = {heading for _, heading, _ in tables.sections(text)}
    return [Issue(stream.epic_path, 1, "missing section ## %s" % s) for s in required if s not in headings]


def unique_keys(ws, stream, profile, params) -> List[Issue]:
    if _skip(stream):
        return []
    issues: List[Issue] = []
    first: Dict[str, str] = {}
    for element in _domain_elements(ws, stream, profile):
        key = _dict(element.fields).get("key")
        line = _field_line(ws, element.path, "key")
        if key != element.key:
            shown = key if isinstance(key, str) else "(missing)"
            issues.append(Issue(element.path, line, "key %s does not match path key %s" % (shown, element.key)))
        if not isinstance(key, str):
            continue
        if key in first:
            issues.append(Issue(element.path, line, "key %s is also used by %s" % (key, first[key])))
        else:
            first[key] = element.path
    return issues


def no_dangling_targets(ws, stream, profile, params) -> List[Issue]:
    if _skip(stream):
        return []
    specs = _element_specs(profile)
    issues: List[Issue] = []
    for element in _domain_elements(ws, stream, profile):
        for table in _list(specs[element.kind].get("tables")):
            if not isinstance(table, dict):
                continue
            heading = table.get("heading")
            # Profile values may be unhashable; only string headings can name a parsed table.
            if not isinstance(heading, str):
                continue
            parsed = _dict(element.tables).get(heading)
            columns = parsed[0] if isinstance(parsed, tuple) and len(parsed) == 3 else None
            if not isinstance(columns, list):
                continue
            # Broken tables are reported by the map rule; here only well-formed rows are checked.
            for column in _list(table.get("keys")):
                if column not in columns:
                    continue
                index = columns.index(column)
                for line, cells in parsed[1]:
                    if cells[index] not in ws.elements:
                        issues.append(Issue(element.path, line, "%s %s is not an existing map element" % (
                            column, cells[index] or "(empty)")))
    return issues


def legacy_traced(ws, stream, profile, params) -> List[Issue]:
    if _skip(stream):
        return []
    heading = _str_param(params, "table", "Legacy trace")
    target = "Target"
    map_doc = _dict(_dict(profile).get("map_doc"))
    for table in _list(map_doc.get("tables")):
        if isinstance(table, dict) and table.get("heading") == heading and isinstance(table.get("target"), str):
            target = table["target"]
    # A stream's legacy trace lives in the MAP.md of the stream's own domain.
    rel = ws.map_docs.get(stream.domain, "domains/%s/MAP.md" % stream.domain)
    text = ws.ctx.read_text(rel) if rel in ws.ctx.files else None
    if text is None:
        return [Issue(rel, 1, "MAP.md is missing")]
    columns, rows, error = tables.parse_table(text, heading)
    found = tables.section_text(text, heading)
    if found is None:
        return [Issue(rel, 1, "no %s table" % heading)]
    issues: List[Issue] = []
    if error is not None:
        m = ERROR_LINE_RE.search(error)
        issues.append(Issue(rel, int(m.group(1)) if m else found[0], "%s table: %s" % (heading, error)))
    if not isinstance(columns, list):
        return issues
    if target not in columns:
        return issues + [Issue(rel, found[0], "%s table has no %s column" % (heading, target))]
    elements = {e.key for e in ws.element_list if e.kind in _element_specs(profile)}
    index = columns.index(target)
    for line, cells in rows:
        value = cells[index]
        if value in elements:
            continue
        if value.startswith("dropped:") and value[len("dropped:"):].strip():
            continue
        issues.append(Issue(rel, line, "%s %s is neither an existing element key nor dropped: with a reason" % (
            target, value or "(empty)")))
    return issues


def two_way_coverage(ws, stream, profile, params) -> List[Issue]:
    if _skip(stream):
        return []
    issues: List[Issue] = []
    stream_scope = _scope_list(stream.data.get("scope"))
    if stream_scope is None:
        issues.append(Issue(stream.path, 1, "scope must be a list of strings"))
        stream_scope = []
    covered = set()
    for story in stream.stories.values():
        broken = _broken_story(story)
        if broken is not None:
            issues.append(broken)
            continue
        line = _field_line(ws, story.path, "scope")
        scope = _scope_list(story.fields.get("scope"))
        if scope is None:
            issues.append(Issue(story.path, line, "scope must be a list of keys"))
            continue
        if not scope:
            unmapped = story.fields.get("unmapped")
            if not isinstance(unmapped, str) or not unmapped.strip():
                issues.append(Issue(story.path, line, "empty scope without an unmapped reason"))
            continue
        for key in scope:
            covered.add(key)
            if key not in stream_scope:
                issues.append(Issue(story.path, line, "scope key %s is not in the stream scope" % key))
            if key not in ws.elements:
                issues.append(Issue(story.path, line, "scope key %s does not exist" % key))
    for key in stream_scope:
        if key not in covered:
            issues.append(Issue(stream.path, 1, "scope key %s is in no story's scope" % key))
    return issues


def tracker_ids(ws, stream, profile, params) -> List[Issue]:
    if _skip(stream):
        return []
    issues: List[Issue] = []
    for story in stream.stories.values():
        broken = _broken_story(story)
        if broken is not None:
            issues.append(broken)
            continue
        tracker = story.fields.get("tracker")
        if ws.id_pattern is not None and isinstance(tracker, str) and ws.id_pattern.fullmatch(tracker):
            continue
        reason = "id_pattern is missing or invalid" if ws.id_pattern is None else "does not match id_pattern"
        if isinstance(tracker, str):
            shown = tracker or "(empty)"
        else:
            shown = "(empty)" if tracker is None else repr(tracker)
        issues.append(Issue(story.path, _field_line(ws, story.path, "tracker"), "tracker %s: %s" % (shown, reason)))
    return issues


def no_open_questions(ws, stream, profile, params) -> List[Issue]:
    if _skip(stream):
        return []
    section = _str_param(params, "section", "Open questions")
    issues: List[Issue] = []
    for story in stream.stories.values():
        for line, heading, text in _list(story.sections):
            if heading == section and text.strip() not in ("", "None."):
                issues.append(Issue(story.path, line, "%s has text other than None." % section))
    return issues


def work_records(ws, stream, profile, params) -> List[Issue]:
    if _skip(stream):
        return []
    issues: List[Issue] = []
    for story in stream.stories.values():
        broken = _broken_story(story)
        if broken is not None:
            issues.append(broken)
            continue
        tracker = story.fields.get("tracker")
        line = _field_line(ws, story.path, "tracker")
        if not isinstance(tracker, str) or not tracker:
            issues.append(Issue(story.path, line, "story has no tracker id for a work record"))
            continue
        rel = "work/%s/record.md" % tracker
        text = ws.ctx.read_text(rel) if rel in ws.ctx.files else None
        if text is None:
            issues.append(Issue(story.path, line, "%s is missing" % rel))
            continue
        recorded = _dict(parse_frontmatter(text)[0]).get("story")
        if recorded != story.key:
            shown = recorded if isinstance(recorded, str) else "(missing)"
            issues.append(Issue(story.path, line, "%s has story %s, expected %s" % (rel, shown, story.key)))
    return issues


PREDICATES = {
    "approval": approval,
    "epic_sections": epic_sections,
    "unique_keys": unique_keys,
    "no_dangling_targets": no_dangling_targets,
    "legacy_traced": legacy_traced,
    "two_way_coverage": two_way_coverage,
    "tracker_ids": tracker_ids,
    "no_open_questions": no_open_questions,
    "work_records": work_records,
}
