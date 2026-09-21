"""Rule: map elements match their profile kind, and domain MAP.md files carry their table markers."""
from __future__ import annotations

import re
from typing import List, Optional

from wslib import gen_maps, tables
from wslib.common import Finding
from wslib.model import Workspace
from wslib.profiles import STAGES

RULE = "map"
LINE_RE = re.compile(r"\bline (\d+)")


def _line_in(message: str, default: int) -> int:
    m = LINE_RE.search(message)
    return int(m.group(1)) if m else default


def _field_line(text: str, field: str) -> int:
    """Return the frontmatter line of `field:`, or 1 when it is absent."""
    lines = text.split("\n")
    for i in range(1, len(lines)):
        if lines[i] == "---":
            break
        if lines[i].startswith(field + ":"):
            return i + 1
    return 1


def _is_empty(value) -> bool:
    return value in ("", [], {})


def _row_breakers(name: str, value) -> List[str]:
    """Messages for a value that would break its MAP.md row when copied verbatim."""
    texts = [v for v in (value if isinstance(value, list) else [value]) if isinstance(v, str)]
    messages = []
    if any("|" in v for v in texts):
        messages.append('field %s value contains "|"' % name)
    if any("\n" in v or "\r" in v for v in texts):
        messages.append("field %s value contains a newline" % name)
    return messages


def _closed_decomposition_streams(ws: Workspace, key: str) -> List[str]:
    """Keys of streams past the decomposition stage whose scope lists `key`."""
    after = STAGES[STAGES.index("decomposition") + 1:]
    result = []
    for stream in ws.streams:
        data = stream.data or {}
        scope = data.get("scope")
        if data.get("stage") in after and isinstance(scope, list) and key in scope:
            result.append(stream.key)
    return result


def _check_fields(ws: Workspace, element, spec: dict, text: str) -> List[Finding]:
    findings: List[Finding] = []
    fields = element.fields
    may_be_empty = set(spec.get("may_be_empty", []))
    values = spec.get("values", {})
    for name in spec["fields"]:
        if name not in fields:
            findings.append(Finding(element.path, 1, RULE, "missing field %s" % name))
            continue
        value = fields[name]
        line = _field_line(text, name)
        findings.extend(Finding(element.path, line, RULE, message) for message in _row_breakers(name, value))
        if _is_empty(value):
            if name not in may_be_empty:
                findings.append(Finding(element.path, line, RULE, "empty field %s" % name))
            elif name == "story":
                findings.extend(
                    Finding(element.path, line, RULE, "field story is empty after decomposition of %s" % stream)
                    for stream in _closed_decomposition_streams(ws, element.key))
            continue
        if name in values and value not in values[name]:
            findings.append(Finding(
                element.path, line, RULE,
                "field %s value %s is not one of %s" % (name, value, ", ".join(values[name]))))
    key = fields.get("key")
    if "key" in fields and key != element.key:
        findings.append(Finding(
            element.path, _field_line(text, "key"), RULE, "key %s does not match path, expected %s" % (key, element.key)))
    story = fields.get("story")
    if isinstance(story, str) and story and story not in ws.stories:
        findings.append(Finding(element.path, _field_line(text, "story"), RULE, "story %s does not exist" % story))
    return findings


def _check_tables(element, spec: dict, text: str) -> List[Finding]:
    findings: List[Finding] = []
    for table in spec.get("tables", []):
        heading = table["heading"]
        columns, _, error = element.tables.get(heading, (None, [], None))
        section = tables.section_text(text, heading)
        heading_line = section[0] if section is not None else 1
        if section is None:
            findings.append(Finding(element.path, 1, RULE, "missing table %s" % heading))
            continue
        if columns is not None and columns != table["columns"]:
            findings.append(Finding(
                element.path, heading_line, RULE,
                "table %s has columns %s, expected %s" % (heading, " | ".join(columns), " | ".join(table["columns"]))))
        if error is not None:
            # A broken table is reported even when its header is right; its rows cannot be trusted.
            findings.append(Finding(
                element.path, _line_in(error, heading_line), RULE, "table %s: %s" % (heading, error)))
    return findings


def _check_element(ws: Workspace, element, spec: Optional[dict]) -> List[Finding]:
    if spec is None:
        return []
    if element.error is not None:
        return [Finding(element.path, _line_in(element.error, 1), RULE, element.error)]
    if element.fields is None:
        return [Finding(element.path, 1, RULE, "missing frontmatter")]
    text = ws.ctx.read_text(element.path) or ""
    return _check_fields(ws, element, spec, text) + _check_tables(element, spec, text)


def check_map(ctx) -> List[Finding]:
    ws = Workspace(ctx)
    # Specs, marker names and the marker test come from gen_maps so check and generate cannot drift.
    spec_list = gen_maps.kind_specs(ws)
    specs = {spec["kind"]: spec for spec in spec_list}
    findings: List[Finding] = []
    for element in ws.element_list:
        findings.extend(_check_element(ws, element, specs.get(element.kind)))
    names = [name for spec in spec_list for name in gen_maps.marker_names(spec)]
    for rel in ws.map_docs.values():
        if not names:
            break
        text = gen_maps.read_map(ctx, rel) or ""
        if not gen_maps.has_begin_marker(text, names):
            example = sorted(gen_maps.marker(name)[0] for name in names)[0]
            findings.append(Finding(rel, 1, RULE, "no map table markers such as %s" % example))
    return findings


RULES = [("map", check_map)]
