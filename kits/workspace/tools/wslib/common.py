"""Shared helpers for workspace check and generate tools."""
from __future__ import annotations

import json
import os
import posixpath
import re
import subprocess
from collections import namedtuple
from pathlib import Path
from typing import Dict, List, Optional, Tuple

Finding = namedtuple("Finding", "path line rule message")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
SKIP_DIRS = {".git", ".local", "repos", "__pycache__"}

_FRONTMATTER_KEY_RE = re.compile(r"^([A-Za-z0-9_-]+):(.*)$")


def find_root(start) -> Optional[Path]:
    current = Path(start).resolve()
    for candidate in [current] + list(current.parents):
        if (candidate / ".agents" / "kit.json").is_file():
            return candidate
    return None


def list_files(root) -> List[str]:
    root = Path(root)
    try:
        proc = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        names = []
        for raw in proc.stdout.split(b"\0"):
            # Names that are not UTF-8 are skipped: they cannot be printed in findings or linked from Markdown.
            try:
                name = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue
            if name:
                names.append(name)
        return sorted(p for p in names if (root / p).is_file())
    except (subprocess.CalledProcessError, OSError):
        pass
    result: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            rel = Path(dirpath, name).relative_to(root).as_posix()
            try:
                rel.encode("utf-8")
            except UnicodeEncodeError:
                continue
            result.append(rel)
    return sorted(result)


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _split_kv(text: str) -> Optional[Tuple[str, str]]:
    m = _FRONTMATTER_KEY_RE.match(text.strip())
    if not m:
        return None
    return m.group(1), _unquote(m.group(2).strip())


def parse_frontmatter(text: str) -> Tuple[Optional[dict], str, Optional[str]]:
    lines = text.split("\n")
    if not lines or lines[0] != "---":
        return None, text, None

    end = None
    for i in range(1, len(lines)):
        if lines[i] == "---":
            end = i
            break
    if end is None:
        return None, text, "frontmatter line %d: missing closing ---" % len(lines)

    body = "\n".join(lines[end + 1 :])
    data: dict = {}
    i = 1
    while i < end:
        line = lines[i]
        if not line.strip():
            return None, text, "frontmatter line %d: blank line" % (i + 1)
        m = _FRONTMATTER_KEY_RE.match(line)
        if not m:
            return None, text, "frontmatter line %d: invalid syntax" % (i + 1)
        key = m.group(1)
        if key in data:
            return None, text, "frontmatter line %d: duplicate key %s" % (i + 1, key)
        rest = m.group(2).strip()

        if rest == "":
            # Any indented line belongs to the block; each is validated so errors
            # point at the offending line, not at the key.
            j = i + 1
            while j < end and lines[j].startswith(" "):
                j += 1
            if j == i + 1:
                data[key] = ""
                i = j
                continue
            is_list = lines[i + 1].startswith("  - ")
            items: List[str] = []
            sub: Dict[str, str] = {}
            for k in range(i + 1, j):
                bl = lines[k]
                if not bl.strip():
                    return None, text, "frontmatter line %d: blank line" % (k + 1)
                if bl.startswith("   "):
                    return None, text, "frontmatter line %d: indent must be two spaces" % (k + 1)
                if is_list:
                    if not bl.startswith("  - "):
                        return None, text, "frontmatter line %d: expected '- item'" % (k + 1)
                    items.append(_unquote(bl[4:].strip()))
                else:
                    kv = _split_kv(bl)
                    if kv is None:
                        return None, text, "frontmatter line %d: expected 'sub: value'" % (k + 1)
                    if kv[0] in sub:
                        return None, text, "frontmatter line %d: duplicate key %s" % (k + 1, kv[0])
                    sub[kv[0]] = kv[1]
            data[key] = items if is_list else sub
            i = j
            continue

        if rest.startswith("["):
            if not rest.endswith("]"):
                return None, text, "frontmatter line %d: unclosed [" % (i + 1)
            inner = rest[1:-1].strip()
            items = []
            if inner:
                for part in inner.split(","):
                    if not part.strip():
                        return None, text, "frontmatter line %d: empty list item" % (i + 1)
                    items.append(_unquote(part.strip()))
            data[key] = items
        elif rest.startswith("{"):
            if not rest.endswith("}"):
                return None, text, "frontmatter line %d: unclosed {" % (i + 1)
            inner = rest[1:-1].strip()
            sub = {}
            if inner:
                for part in inner.split(","):
                    kv = _split_kv(part)
                    if kv is None:
                        return None, text, "frontmatter line %d: expected '{sub: value, ...}'" % (i + 1)
                    if kv[0] in sub:
                        return None, text, "frontmatter line %d: duplicate key %s" % (i + 1, kv[0])
                    sub[kv[0]] = kv[1]
            data[key] = sub
        else:
            data[key] = _unquote(rest)
        i += 1

    return data, body, None


def format_finding(f: Finding) -> str:
    return "%s:%s %s %s" % (f.path, f.line, f.rule, f.message)


def h2_headings(body: str) -> List[str]:
    return [line[3:].strip() for line in body.split("\n") if line.startswith("## ")]


def md_links(text: str) -> List[Tuple[int, str, str]]:
    result: List[Tuple[int, str, str]] = []
    for lineno, line in enumerate(text.split("\n"), start=1):
        for m in LINK_RE.finditer(line):
            result.append((lineno, m.group(1), m.group(2)))
    return result


def resolve_target(from_rel: str, target: str) -> str:
    target = target.split("#", 1)[0]
    joined = posixpath.normpath(posixpath.join(posixpath.dirname(from_rel), target))
    # normpath already drops trailing slashes but keeps exactly two leading ones (POSIX rule).
    if joined.startswith("//"):
        joined = joined[1:]
    return joined


class Context:
    def __init__(self, root):
        self.root = Path(root)
        self.files = list_files(self.root)

    def read_text(self, rel: str) -> Optional[str]:
        try:
            return (self.root / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

    def load_json(self, rel: str) -> Tuple[object, Optional[Finding]]:
        text = self.read_text(rel)
        if text is None:
            return None, Finding(rel, 1, "json-shape", "missing or unreadable file")
        try:
            return json.loads(text), None
        except json.JSONDecodeError as e:
            return None, Finding(rel, e.lineno, "json-shape", str(e))

    def kit_params(self) -> dict:
        data, _ = self.load_json(".agents/kit.json")
        if isinstance(data, dict):
            params = data.get("params")
            if isinstance(params, dict):
                return params
        return {}
