"""Render tool adapters from the neutral .agents sources."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional, Tuple

OWNED_DIRS = [".claude/agents", ".claude/skills", ".opencode/agents", ".cursor/rules"]


def _split_frontmatter(data: bytes) -> Tuple[Optional[bytes], bytes]:
    """Return (description line or None, body).

    The body is the bytes after the closing `---` line, or the whole file when there is no closed frontmatter.
    """
    # Work on bytes split on "\n" only, so any encoding passes through unchanged.
    lines = data.split(b"\n")
    if lines[0] != b"---":
        return None, data
    for idx in range(1, len(lines)):
        if lines[idx] == b"---":
            description = None
            for line in lines[1:idx]:
                if line.startswith(b"description:"):
                    description = line
                    break
            return description, b"\n".join(lines[idx + 1:])
    return None, data


def _rule_description(data: bytes, stem: str) -> bytes:
    for line in data.split(b"\n"):
        if line.startswith(b"# "):
            return line[2:]
    return os.fsencode(stem)


def _is_skill_junk(rel_parts: Tuple[str, ...]) -> bool:
    return rel_parts[-1] == ".DS_Store" or "__pycache__" in rel_parts[:-1]


def render(root) -> Dict[str, bytes]:
    """Return generated adapter files keyed by POSIX path relative to root."""
    root = Path(root)
    out: Dict[str, bytes] = {"CLAUDE.md": b"@AGENTS.md\n"}

    agents_dir = root / ".agents" / "agents"
    if agents_dir.is_dir():
        for src in sorted(p for p in agents_dir.glob("*.md") if p.is_file()):
            data = src.read_bytes()
            out[".claude/agents/" + src.name] = data
            description, body = _split_frontmatter(data)
            if description is None:
                description = b"description: "
            out[".opencode/agents/" + src.name] = b"---\n" + description + b"\nmode: subagent\n---\n" + body

    skills_dir = root / ".agents" / "skills"
    if skills_dir.is_dir():
        skill_dirs = (
            p for p in skills_dir.iterdir()
            if p.is_dir() and p.name != "__pycache__" and not p.name.startswith(".")
        )
        for skill_dir in sorted(skill_dirs):
            for src in sorted(p for p in skill_dir.rglob("*") if p.is_file()):
                if _is_skill_junk(src.relative_to(skill_dir).parts):
                    continue
                rel = src.relative_to(skills_dir).as_posix()
                out[".claude/skills/" + rel] = src.read_bytes()

    rules_dir = root / ".agents" / "rules"
    if rules_dir.is_dir():
        for src in sorted(p for p in rules_dir.glob("*.md") if p.is_file()):
            data = src.read_bytes()
            header = b"---\ndescription: " + _rule_description(data, src.stem) + b"\nalwaysApply: true\n---\n"
            out[".cursor/rules/" + src.stem + ".mdc"] = header + data

    return out
