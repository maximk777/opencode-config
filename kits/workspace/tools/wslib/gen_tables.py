"""Render the repository table and the alias index."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from wslib.common import Context
from wslib.model import Workspace

BEGIN = "<!-- repos:begin -->"
EXTERNAL_PREFIXES = ("diagram:", "mockup:")
END = "<!-- repos:end -->"
ADR_RE = re.compile(r"([0-9]{4})-[a-z0-9-]+\.md")
TABLE_HEADER = ["| Name | Forge | Default branch | Kit | Summary |", "|---|---|---|---|---|"]


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _encodable(text: str) -> bool:
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _load_json(path: Path) -> object:
    text = _read_text(path)
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _table_rows(manifest: object) -> Optional[List[str]]:
    if not isinstance(manifest, dict) or not isinstance(manifest.get("repositories"), list):
        return None
    rows = []
    for entry in manifest["repositories"]:
        if not isinstance(entry, dict):
            return None
        cells = [entry.get(f, "") for f in ("name", "forge", "default_branch")]
        summary = entry.get("summary", "")
        kit = entry.get("kit", {})
        if not isinstance(kit, dict):
            return None
        kind = kit.get("kind", "")
        texts = cells + [kind, summary]
        if not all(isinstance(c, str) for c in texts):
            return None
        # Lone surrogates (valid JSON escapes, not UTF-8) make the manifest unusable instead of raising.
        if not all(_encodable(c) for c in texts):
            return None
        rows.append("| %s |" % " | ".join(cells + [kind, summary]))
    return rows


def _render_table(root: Path) -> Optional[bytes]:
    text = _read_text(root / "REPOSITORIES.md")
    rows = _table_rows(_load_json(root / "repos.json"))
    if text is None or rows is None:
        return None
    lines = text.split("\n")
    try:
        begin = lines.index(BEGIN)
        end = lines.index(END, begin + 1)
    except ValueError:
        return None
    new_lines = lines[: begin + 1] + TABLE_HEADER + rows + lines[end:]
    return "\n".join(new_lines).encode("utf-8")


def _sorted_files(directory: Path) -> List[Path]:
    if not directory.is_dir():
        return []
    return sorted((p for p in directory.iterdir() if p.is_file()), key=lambda p: p.name)


def _render_index(root: Path) -> bytes:
    index: Dict[str, str] = {}
    for path in _sorted_files(root / "docs" / "adr"):
        m = ADR_RE.fullmatch(path.name)
        if m:
            index["adr:" + m.group(1)] = "docs/adr/" + path.name
    for path in _sorted_files(root / "docs" / "diagrams"):
        if path.suffix == ".md" and _encodable(path.name):
            index["diagram:" + path.stem] = "docs/diagrams/" + path.name
    external = _load_json(root / "docs" / "diagrams" / "external.json")
    entries = external.get("diagrams") if isinstance(external, dict) else None
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            key, url = entry.get("key"), entry.get("url")
            # Only diagram and mockup keys are non-derivable; anything else would leak derivable keys into the index.
            if not (isinstance(key, str) and any(key.startswith(p) and len(key) > len(p) for p in EXTERNAL_PREFIXES)):
                continue
            # Lone surrogates skip the entry; an existing key (a docs/diagrams/*.md file) wins over external.json.
            if not isinstance(url, str) or not _encodable(key) or not _encodable(url) or key in index:
                continue
            index[key] = url
    # Stories and tasks are the lifecycle items; their keys sort ascending,
    # which also places every story: before every task:.
    ws = Workspace(Context(root))
    items = [s for s in ws.stories.values() if s.fields is not None and s.error is None]
    items += [t for t in ws.tasks.values() if t.fields is not None and t.error is None]
    items.sort(key=lambda item: item.key)
    for item in items:
        index.setdefault(item.key, item.path)
    aliases = [(item.fields.get("tracker"), item.path) for item in items]
    # Stable sort keeps the smaller item key first when two items share a tracker id.
    for tracker, path in sorted((a for a in aliases if isinstance(a[0], str) and a[0]), key=lambda a: a[0]):
        index.setdefault(tracker, path)
    return (json.dumps(index, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def render(root) -> Dict[str, bytes]:
    """Return REPOSITORIES.md and .agents/index.json keyed by POSIX path."""
    root = Path(root)
    out: Dict[str, bytes] = {}
    table = _render_table(root)
    if table is not None:
        out["REPOSITORIES.md"] = table
    out[".agents/index.json"] = _render_index(root)
    return out
