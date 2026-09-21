"""Rule: agents stay neutral across tools."""
from __future__ import annotations

import posixpath
from typing import List

from wslib.common import Finding, parse_frontmatter

AGENTS_DIR = ".agents/agents"
HARNESS_TOOL_PREFIXES = ("mcp__claude-in-chrome__",)


def _tool_names(value) -> List[str]:
    if isinstance(value, list):
        return [item.strip() for item in value]
    if isinstance(value, dict):
        return [key.strip() for key in value]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",")]
    return []


def _problems(text) -> List[str]:
    if text is None:
        return ["file is not readable UTF-8"]
    data, _body, error = parse_frontmatter(text)
    if error is not None:
        return [error]
    if data is None:
        return ["missing frontmatter with name and description"]
    problems = []
    for field in ("name", "description"):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            problems.append("missing %s" % field)
    harness = [name for name in _tool_names(data.get("tools")) if name.startswith(HARNESS_TOOL_PREFIXES)]
    if harness:
        problems.append("harness-specific tools: %s" % ", ".join(harness))
    return problems


def check_neutral_agent(ctx) -> List[Finding]:
    findings = []
    for rel in ctx.files:
        if posixpath.dirname(rel) != AGENTS_DIR or not rel.endswith(".md"):
            continue
        problems = _problems(ctx.read_text(rel))
        if problems:
            findings.append(Finding(rel, 1, "neutral-agent", "; ".join(problems)))
    return findings


RULES = [("neutral-agent", check_neutral_agent)]
