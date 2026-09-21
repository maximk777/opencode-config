"""Rule: key links resolve to existing entities. Also used by the ADR rule."""
from __future__ import annotations

import re
import weakref
from typing import Dict, List, Optional, Tuple

from wslib.common import Finding, md_links, resolve_target
from wslib.model import Workspace
from wslib.profiles import load_profiles

KEY_RE = re.compile(r"^(adr|diagram|mockup|repo|stand|domain|story|stream|task):(.+)$")
ELEMENT_KEY_RE = re.compile(r"^([^:/\s]+):(.+)$")
PAIR_RE = re.compile(r"^([^/]+)/([^/]+)$")
TRIPLE_RE = re.compile(r"^([^/]+)/([^/]+)/([^/]+)$")
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


_ELEMENT_DIRS: "weakref.WeakKeyDictionary" = weakref.WeakKeyDictionary()


def _element_dirs(ctx) -> Dict[str, str]:
    """Map element key prefixes of valid profiles to their directories; cached per context."""
    try:
        return _ELEMENT_DIRS[ctx]
    except (KeyError, TypeError):
        pass
    dirs: Dict[str, str] = {}
    for profile in load_profiles(ctx)[0].values():
        for element in profile["elements"]:
            prefix = element["prefix"]
            # Built-in prefixes keep their own resolution; the first profile wins a duplicate.
            if ELEMENT_KEY_RE.match(prefix + ":x") and not KEY_RE.match(prefix + ":x") and prefix not in dirs:
                dirs[prefix] = element["dir"]
    try:
        _ELEMENT_DIRS[ctx] = dirs
    except TypeError:
        pass
    return dirs


def is_key(ctx, text: str) -> bool:
    """True when text has a built-in key prefix or one declared by a loaded profile."""
    if KEY_RE.match(text):
        return True
    m = ELEMENT_KEY_RE.match(text)
    return bool(m) and m.group(1) in _element_dirs(ctx)


def lookup(ctx, key: str) -> Tuple[bool, Optional[List[str]]]:
    """Return (exists, accepted targets); targets None means the target is not checked."""
    if not isinstance(key, str):
        return False, []
    m = KEY_RE.match(key) or ELEMENT_KEY_RE.match(key)
    if not m:
        return False, []
    kind, rest = m.group(1), m.group(2)
    element_dir = _element_dirs(ctx).get(kind)
    if not KEY_RE.match(key) and element_dir is None:
        return False, []
    if kind == "adr":
        # Numbers are workspace-global, so the file may sit at the root or in any project.
        adr_re = re.compile(r"^(docs|projects/[^/]+)/adr/" + re.escape(rest) + r"-[^/]+\.md$")
        matches = sorted(rel for rel in ctx.files if adr_re.match(rel))
        if len(matches) != 1:
            return False, []
        return True, matches
    if kind == "task":
        target = "tasks/%s/task.md" % rest
        return (True, [target]) if target in ctx.files else (False, [])
    if element_dir is not None or kind in ("domain", "stream", "story"):
        if kind == "domain":
            pair = PAIR_RE.match(rest)
            if not pair:
                return False, []
            base = "projects/%s/domains/%s" % (pair.group(1), pair.group(2))
            exists = any(rel.startswith(base + "/") for rel in ctx.files)
            return exists, [base, base + "/README.md"]
        triple = TRIPLE_RE.match(rest)
        if not triple:
            return False, []
        base = "projects/%s/domains/%s" % (triple.group(1), triple.group(2))
        name = triple.group(3)
        if element_dir is not None:
            target = "%s/%s/%s.md" % (base, element_dir, name)
        elif kind == "stream":
            target = "%s/streams/%s/stream.json" % (base, name)
        else:
            data = ctx.load_json(".agents/index.json")[0] if ".agents/index.json" in ctx.files else None
            target = data.get(key) if isinstance(data, dict) else None
            # The index entry must name this story's own file, not any other existing file.
            story_re = re.compile(
                r"^" + re.escape(base) + r"/streams/[^/]+/stories/" + re.escape(name) + r"/story\.md$")
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
    return False, []


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


def _tracker_files(ws) -> dict:
    """Map each non-empty story/task frontmatter tracker to the files carrying it."""
    carriers: dict = {}
    for task in list(ws.stories.values()) + list(ws.tasks.values()):
        fields = task.fields
        tracker = fields.get("tracker") if isinstance(fields, dict) else None
        if isinstance(tracker, str) and tracker:
            carriers.setdefault(tracker, []).append(task.path)
    return carriers


def check_key_resolve(ctx) -> List[Finding]:
    ws = Workspace(ctx)
    carriers = _tracker_files(ws)
    findings: List[Finding] = []
    for rel in ctx.files:
        if not rel.endswith(".md"):
            continue
        text = ctx.read_text(rel)
        if text is None:
            continue
        for line, label, target in md_links(_without_code(text)):
            if is_key(ctx, label):
                exists, accepted = lookup(ctx, label)
                if not exists:
                    findings.append(Finding(rel, line, "key-resolve", "unknown key %s" % label))
                    continue
            else:
                key = ws.match_tracker(label)
                if key == "ambiguous":
                    names = ", ".join(sorted(t.key for t in ws.trackers if t.pattern.fullmatch(label)))
                    findings.append(Finding(
                        rel, line, "key-resolve",
                        "tracker id %s matches several trackers: %s" % (label, names)))
                    continue
                if key is None:
                    continue
                tracker = next(t for t in ws.trackers if t.key == key)
                accepted = [tracker.url.replace("{id}", label)] if tracker.url is not None else []
                accepted += carriers.get(label, [])
                if not accepted:
                    findings.append(Finding(
                        rel, line, "key-resolve",
                        "tracker id %s has no tracker url and no story or task carries it" % label))
                    continue
            if accepted is not None and not _points_to(rel, target, accepted):
                findings.append(Finding(
                    rel, line, "key-resolve",
                    "link to %s does not point to %s" % (label, " or ".join(accepted))))
    return findings


RULES = [("key-resolve", check_key_resolve)]
