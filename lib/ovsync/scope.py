"""Select specs paths for the OpenViking index by gitignore-style rules."""
from __future__ import annotations

import re
from typing import Iterable, List, Pattern, Tuple

Rule = Tuple[bool, Pattern[str]]


def translate(pattern: str) -> Pattern[str]:
    """Compile one scope pattern into a regex that must fullmatch a POSIX relative path."""
    if pattern.endswith("/"):
        pattern += "**"
    parts = pattern.split("/")
    out = []
    for i, seg in enumerate(parts):
        last = i == len(parts) - 1
        if seg == "**":
            out.append(".*" if last else "(?:[^/]+/)*")
            continue
        # escape everything except * and ?, then add the separator unless this is the last segment
        buf = []
        for ch in seg:
            if ch == "*":
                buf.append("[^/]*")
            elif ch == "?":
                buf.append("[^/]")
            else:
                buf.append(re.escape(ch))
        out.append("".join(buf))
        if not last:
            out.append("/")
    return re.compile("".join(out))


def parse(text: str) -> List[Rule]:
    rules: List[Rule] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("!"):
            rules.append((False, translate(line[1:])))
        else:
            rules.append((True, translate(line)))
    return rules


def selected(path: str, rules: List[Rule]) -> bool:
    verdict = False
    for include, rx in rules:
        if rx.fullmatch(path):
            verdict = include
    return verdict


def select(paths: Iterable[str], rules: List[Rule]) -> List[str]:
    return sorted(p for p in paths if selected(p, rules))
