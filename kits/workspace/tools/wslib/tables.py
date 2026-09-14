"""Parse H2 sections and the first pipe table of a section in Markdown text."""
from __future__ import annotations

from typing import List, Optional, Tuple

Fence = Tuple[str, int]


def _fence_open(line: str) -> Optional[Fence]:
    """Return (char, length) when the line opens a CommonMark code fence."""
    stripped = line.lstrip()
    for char in ("`", "~"):
        length = len(stripped) - len(stripped.lstrip(char))
        if length >= 3:
            # A backtick fence's info string may not contain backticks (CommonMark).
            if char == "`" and "`" in stripped[length:]:
                return None
            return char, length
    return None


def _fence_closes(line: str, fence: Fence) -> bool:
    char, length = fence
    stripped = line.lstrip()
    run = len(stripped) - len(stripped.lstrip(char))
    return run >= length and stripped[run:].strip(" ") == ""


def _step_fence(line: str, fence: Optional[Fence]) -> Tuple[bool, Optional[Fence]]:
    """Return (line is a fence line, fence state after the line)."""
    if fence is None:
        opened = _fence_open(line)
        return opened is not None, opened
    if _fence_closes(line, fence):
        return True, None
    return False, fence


def _h2_positions(lines: List[str]) -> List[Tuple[int, str]]:
    """Return (0-based index, stripped heading) of every H2 line outside fenced code."""
    result: List[Tuple[int, str]] = []
    fence: Optional[Fence] = None
    for idx, line in enumerate(lines):
        was_open = fence is not None
        is_fence_line, fence = _step_fence(line, fence)
        if is_fence_line or was_open:
            continue
        if line.startswith("## "):
            result.append((idx, line[3:].strip()))
    return result


def _find_section(lines: List[str], heading: str) -> Optional[Tuple[int, int]]:
    """Return (heading index, end index exclusive) of the first `## heading` section."""
    positions = _h2_positions(lines)
    for n, (idx, text) in enumerate(positions):
        if text == heading:
            end = positions[n + 1][0] if n + 1 < len(positions) else len(lines)
            return idx, end
    return None


def _split_lines(text: str) -> List[str]:
    return [line.rstrip("\r") for line in text.split("\n")]


def _cells(line: str) -> List[str]:
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return [cell.strip() for cell in inner.split("|")]


def _is_separator(cells: List[str], width: int) -> bool:
    return len(cells) == width and all("-" in cell and set(cell) <= {"-", ":"} for cell in cells)


def section_text(body: str, heading: str) -> Optional[Tuple[int, str]]:
    lines = _split_lines(body)
    found = _find_section(lines, heading)
    if found is None:
        return None
    idx, end = found
    return idx + 1, "\n".join(lines[idx + 1:end])


def sections(body: str) -> List[Tuple[int, str, str]]:
    lines = _split_lines(body)
    positions = _h2_positions(lines)
    result: List[Tuple[int, str, str]] = []
    for n, (idx, heading) in enumerate(positions):
        end = positions[n + 1][0] if n + 1 < len(positions) else len(lines)
        result.append((idx + 1, heading, "\n".join(lines[idx + 1:end])))
    return result


def parse_table(
    text: str, heading: str, start_line: int = 1
) -> Tuple[Optional[List[str]], List[Tuple[int, List[str]]], Optional[str]]:
    lines = _split_lines(text)
    found = _find_section(lines, heading)
    if found is None:
        return None, [], None
    idx, end = found

    table: List[int] = []
    fence: Optional[Fence] = None
    for i in range(idx + 1, end):
        line = lines[i]
        was_open = fence is not None
        is_fence_line, fence = _step_fence(line, fence)
        if is_fence_line:
            if table:
                break
            continue
        if was_open:
            continue
        if line.startswith("|"):
            table.append(i)
        elif table:
            break
    if not table:
        return None, [], "no table"

    def file_line(i: int) -> int:
        return start_line + i

    columns = _cells(lines[table[0]])
    if len(table) < 2 or not _is_separator(_cells(lines[table[1]]), len(columns)):
        return columns, [], "table at line %d has no separator line" % file_line(table[0])

    rows: List[Tuple[int, List[str]]] = []
    error: Optional[str] = None
    for i in table[2:]:
        cells = _cells(lines[i])
        if len(cells) != len(columns):
            # Keep only well-formed rows so callers can index cells safely; report the first bad one.
            if error is None:
                error = "row at line %d has %d cells, expected %d" % (file_line(i), len(cells), len(columns))
            continue
        rows.append((file_line(i), cells))
    return columns, rows, error
