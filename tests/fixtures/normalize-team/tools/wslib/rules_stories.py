"""Rule: stories carry the fields and sections of their stream's profile, and their keys resolve."""
from __future__ import annotations

from typing import List

from wslib.common import Finding
from wslib.model import Workspace
from wslib.rules_keys import lookup

RULE = "story"
LIST_FIELDS = ("scope", "depends", "repos", "decisions", "mockups")


def _field_line(text: str, field: str) -> int:
    lines = text.split("\n")
    for i, line in enumerate(lines[1:], start=2):
        if line == "---":
            break
        if line.startswith(field + ":"):
            return i
    return 1


def _is_empty(value) -> bool:
    return value == "" or value == [] or value == {}


def _resolves(ws, field: str, key: str) -> bool:
    if field == "scope":
        return key in ws.elements
    if field == "depends":
        return key in ws.stories
    if field == "repos":
        # Story repos name repos.json entries; a value already written as a key is accepted as is.
        return lookup(ws.ctx, key if key.startswith("repo:") else "repo:" + key)[0]
    prefix = "adr:" if field == "decisions" else "mockup:"
    return key.startswith(prefix) and lookup(ws.ctx, key)[0]


def _check_story(ws, story, spec: dict) -> List[Finding]:
    text = ws.ctx.read_text(story.path) or ""
    if story.error is not None:
        return [Finding(story.path, 1, RULE, story.error)]
    if story.fields is None:
        return [Finding(story.path, 1, RULE, "missing frontmatter")]
    fields = story.fields
    findings: List[Finding] = []

    def add(field: str, message: str) -> None:
        findings.append(Finding(story.path, _field_line(text, field), RULE, message))

    may_be_empty = set(spec.get("may_be_empty", []))
    for field in spec["fields"]:
        if field not in fields:
            add(field, "missing field %s" % field)
        elif _is_empty(fields[field]) and field not in may_be_empty:
            add(field, "field %s must not be empty" % field)
    for field, allowed in spec.get("values", {}).items():
        value = fields.get(field)
        if field in fields and not _is_empty(value) and value not in allowed:
            add(field, "field %s has value %s, expected one of %s" % (field, value, ", ".join(allowed)))

    if "key" in fields and fields["key"] != story.key:
        add("key", "key %s does not match folder key %s" % (fields["key"], story.key))

    for field in LIST_FIELDS:
        value = fields.get(field)
        if field not in fields or value == "":
            continue
        if not isinstance(value, list):
            add(field, "field %s must be a list" % field)
            continue
        for key in value:
            if not _resolves(ws, field, key):
                add(field, "%s key %s does not resolve" % (field, key))

    headings = {heading for _, heading, _ in story.sections}
    for section in spec["sections"]:
        if section not in headings:
            findings.append(Finding(story.path, 1, RULE, "missing section %s" % section))
    return findings


def check_stories(ctx) -> List[Finding]:
    ws = Workspace(ctx)
    findings: List[Finding] = []
    for stream in ws.streams:
        profile = ws.profiles.get(stream.profile_name) if stream.profile_name is not None else None
        # Unknown profiles are a lifecycle finding; their stories have no shape to check against.
        if profile is None:
            continue
        for story in stream.stories.values():
            findings.extend(_check_story(ws, story, profile["story"]))
    return findings


RULES = [(RULE, check_stories)]
