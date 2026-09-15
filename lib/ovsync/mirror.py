"""Build the allow-listed copy of a project's HEAD that OpenViking imports."""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Callable, List

from ovsync import scope

# surrogateescape maps an undecodable byte b to U+DC80..U+DCFF; such a path
# cannot round-trip through the cat-file batch protocol below and is skipped
_SURROGATE_LOW, _SURROGATE_HIGH = 0xDC80, 0xDCFF


def committed_paths(run: Callable, repo: Path, head: str) -> List[str]:
    """Paths of committed blobs (files and symlinks) selected by scope; submodules and trees are excluded."""
    r = run(["git", "ls-tree", "-r", "-z", head], cwd=repo, capture_output=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"git ls-tree failed: {r.stderr.decode(errors='replace').strip()}")
    paths: List[str] = []
    for entry in r.stdout.split(b"\0"):
        if not entry:
            continue
        meta, sep, raw_path = entry.partition(b"\t")
        if not sep:
            continue
        fields = meta.split(b" ")
        if len(fields) != 3 or fields[1] != b"blob":
            continue  # skip submodules (gitlinks, type "commit") and any other non-blob entry
        path = os.fsdecode(raw_path)
        if "\n" in path or any(_SURROGATE_LOW <= ord(ch) <= _SURROGATE_HIGH for ch in path):
            continue  # newline breaks the batch request framing; surrogate-escaped chars mean a non-UTF-8 name
        paths.append(path)
    return paths


def read_blobs(run: Callable, repo: Path, head: str, paths: List[str]) -> List[bytes]:
    """One `git cat-file --batch` call; the reply is '<sha> blob <size>\\n<content>\\n' per request line."""
    if not paths:
        return []
    request = "".join(f"{head}:{p}\n" for p in paths).encode()
    r = run(["git", "cat-file", "--batch"], cwd=repo, input=request, capture_output=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"git cat-file failed: {r.stderr.decode(errors='replace').strip()}")
    data = r.stdout
    out: List[bytes] = []
    pos = 0
    for p in paths:
        nl = data.find(b"\n", pos)
        if nl == -1:
            raise RuntimeError(f"truncated git cat-file reply for {p!r}")
        header = data[pos:nl].decode(errors="replace")
        pos = nl + 1
        fields = header.split(" ")
        if fields[-1] == "missing":
            raise RuntimeError(f"missing blob for {p!r} at {head}")
        if len(fields) != 3 or not fields[2].isdigit():
            raise RuntimeError(f"malformed git cat-file header for {p!r}: {header!r}")
        size = int(fields[2])
        content = data[pos:pos + size]
        if len(content) != size:
            raise RuntimeError(f"truncated git cat-file content for {p!r}")
        out.append(content)
        pos += size + 1  # skip the trailing newline git appends after the content
    return out


def build_mirror(run: Callable, repo: Path, head: str, rules, stage: Path, project: str) -> int:
    selected = scope.select(committed_paths(run, repo, head), rules)
    if not selected:
        return 0
    tmp, final, old = stage / f"{project}.tmp", stage / project, stage / f"{project}.old"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    blobs = read_blobs(run, repo, head, selected)
    for path, content in zip(selected, blobs):
        dest = tmp / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
    if old.exists():
        shutil.rmtree(old)
    if final.exists():
        final.rename(old)
    tmp.rename(final)
    if old.exists():
        shutil.rmtree(old)
    return len(selected)


def cleanup_stage(stage: Path) -> None:
    if not stage.exists():
        return
    for pattern in ("*.tmp", "*.old"):
        for p in stage.glob(pattern):
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
