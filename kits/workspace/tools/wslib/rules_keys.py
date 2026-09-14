"""Rule: key links resolve to existing entities. Also used by the ADR rule."""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from wslib.common import Finding, md_links, parse_frontmatter, resolve_target

KEY_RE = re.compile(r"^(adr|diagram|mockup|repo|stand|domain|screen|story|stream):(.+)$")
PAIR_RE = re.compile(r"^([^/]+)/([^/]+)$")
STORY_RE = re.compile(r"^domains/[^/]+/streams/[^/]+/stories/[^/]+/story\.md$")
# CommonMark: a backtick fence's info string may not contain backticks.
FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}(?!.*`)|~{3,}).*$")
CODE_SPAN_RE = re.compile(r"(`+)(.+?)\1")


def _json_list(ctx, rel: str, field: str) -> list:
    if rel not in ctx.files:
        return []
    data, error = ctx.load_json(rel)
    if error is not None or not isinstance(data, dict) or not isinstance(data.get(field), list):
        return []
    return [entry for entry in data[field] if isinstance(entry, dict)]


def _json_strings(ctx, rel: str, field: str, attr: str) -> set:
    # json-shape reports wrong types; here non-string values simply name nothing.
    values = (entry.get(attr) for entry in _json_list(ctx, rel, field))
    return {value for value in values if isinstance(value, str)}


def lookup(ctx, key: str) -> Tuple[bool, Optional[List[str]]]:
    """Return (exists, accepted targets); targets None means the target is not checked."""
    if not isinstance(key, str):
        return False, []
    m = KEY_RE.match(key)
    if not m:
        return False, []
    kind, rest = m.group(1), m.group(2)
    if kind == "adr":
        adr_re = re.compile(r"^docs/adr/" + re.escape(rest) + r"-[^/]+\.md$")
        matches = [rel for rel in ctx.files if adr_re.match(rel)]
        if len(matches) != 1:
            return False, []
        return True, matches
    if kind in ("screen", "story", "stream"):
        pair = PAIR_RE.match(rest)
        if not pair:
            return False, []
        domain, name = pair.group(1), pair.group(2)
        if kind == "screen":
            target = "domains/%s/map/%s.md" % (domain, name)
        elif kind == "stream":
            target = "domains/%s/streams/%s/stream.json" % (domain, name)
        else:
            data = ctx.load_json(".agents/index.json")[0] if ".agents/index.json" in ctx.files else None
            target = data.get(key) if isinstance(data, dict) else None
            # The index entry must name this story's own file, not any other existing file.
            story_re = re.compile(
                r"^domains/" + re.escape(domain) + r"/streams/[^/]+/stories/" + re.escape(name) + r"/story\.md$")
            if not isinstance(target, str) or not story_re.match(target):
                return False, []
        if target not in ctx.files:
            return False, []
        return True, [target]
    if kind in ("diagram", "mockup"):
        targets = []
        local = "docs/diagrams/%s.md" % rest
        if kind == "diagram" and local in ctx.files:
            targets.append(local)
        for entry in _json_list(ctx, "docs/diagrams/external.json", "diagrams"):
            if isinstance(entry.get("key"), str) and entry["key"] == key and isinstance(entry.get("url"), str):
                targets.append(entry["url"])
        return bool(targets), targets
    if kind == "repo":
        name = rest.split("#", 1)[0].split(":", 1)[0]
        return name in _json_strings(ctx, "repos.json", "repositories", "name"), None
    if kind == "stand":
        return key in _json_strings(ctx, "environments.json", "stands", "key"), ["environments.json"]
    prefix = "domains/%s/" % rest
    exists = any(rel.startswith(prefix) for rel in ctx.files)
    return exists, ["domains/%s" % rest, "domains/%s/README.md" % rest]


def _tracker(ctx) -> Tuple[Optional[re.Pattern], Optional[str]]:
    data, error = ctx.load_json("tracker/tracker.json")
    if error is not None or not isinstance(data, dict):
        return None, None
    pattern, url = data.get("id_pattern"), data.get("url")
    if not isinstance(pattern, str) or not isinstance(url, str):
        return None, None
    # A bad pattern is reported by json-shape; huge repeats or deep nesting raise more than re.error.
    try:
        return re.compile(pattern), url
    except (re.error, OverflowError, RecursionError, ValueError):
        return None, None


def _without_code(text: str) -> str:
    # Skills and templates show example links inside code; blanking code keeps line numbers intact.
    lines = []
    fence = None
    for line in text.split("\n"):
        if fence is None:
            m = FENCE_OPEN_RE.match(line)
            if m:
                fence = m.group(1)
                lines.append("")
            else:
                lines.append(CODE_SPAN_RE.sub(lambda m: _blank_span(line, m), line))
            continue
        # Only the same character, at least as long as the opener, with no info string closes a fence.
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if indent <= 3 and len(stripped) >= len(fence) and set(stripped) == {fence[0]}:
            fence = None
        lines.append("")
    return "\n".join(lines)


def _blank_span(line: str, m: re.Match) -> str:
    # A code span that is the whole link text, as in [`adr:0004`](x.md), keeps its content.
    if line[m.start() - 1:m.start()] == "[" and line[m.end():m.end() + 2] == "](":
        return m.group(2)
    return " " * len(m.group(0))


def _points_to(rel: str, target: str, accepted: List[str]) -> bool:
    for candidate in accepted:
        if "://" in candidate:
            if target == candidate:
                return True
        elif resolve_target(rel, target) == candidate:
            return True
    return False


def _story_trackers(ctx) -> dict:
    """Map each non-empty story frontmatter tracker to the story.md paths carrying it."""
    trackers: dict = {}
    for rel in ctx.files:
        if not STORY_RE.match(rel):
            continue
        text = ctx.read_text(rel)
        data = parse_frontmatter(text)[0] if text is not None else None
        tracker = data.get("tracker") if isinstance(data, dict) else None
        if isinstance(tracker, str) and tracker:
            trackers.setdefault(tracker, []).append(rel)
    return trackers


def check_key_resolve(ctx) -> List[Finding]:
    id_re, url = _tracker(ctx)
    trackers = _story_trackers(ctx) if id_re is not None else {}
    findings: List[Finding] = []
    for rel in ctx.files:
        if not rel.endswith(".md"):
            continue
        text = ctx.read_text(rel)
        if text is None:
            continue
        for line, label, target in md_links(_without_code(text)):
            if KEY_RE.match(label):
                exists, accepted = lookup(ctx, label)
                if not exists:
                    findings.append(Finding(rel, line, "key-resolve", "unknown key %s" % label))
                    continue
            elif id_re is not None and id_re.fullmatch(label):
                accepted = [url.replace("{id}", label)]
                if "work/%s/record.md" % label in ctx.files:
                    accepted += ["work/%s" % label, "work/%s/record.md" % label]
                accepted += trackers.get(label, [])
            else:
                continue
            if accepted is not None and not _points_to(rel, target, accepted):
                findings.append(Finding(
                    rel, line, "key-resolve",
                    "link to %s does not point to %s" % (label, " or ".join(accepted))))
    return findings


RULES = [("key-resolve", check_key_resolve)]
