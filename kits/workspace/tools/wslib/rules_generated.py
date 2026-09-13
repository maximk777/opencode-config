"""Rule: generated files equal the generator output."""
from __future__ import annotations

from pathlib import Path
from typing import List

import generate
from wslib import gen_adapters
from wslib.common import Finding

HINT = "run python3 tools/generate.py"


def first_diff_line(actual: bytes, expected: bytes) -> int:
    """Return the 1-based number of the first line where actual and expected differ."""
    actual_lines = actual.split(b"\n")
    expected_lines = expected.split(b"\n")
    for index, (a, e) in enumerate(zip(actual_lines, expected_lines)):
        if a != e:
            return index + 1
    return min(len(actual_lines), len(expected_lines)) + 1


def check_generated(ctx) -> List[Finding]:
    root = Path(ctx.root)
    rendered = generate.render_all(root)
    findings: List[Finding] = []
    for rel, expected in rendered.items():
        try:
            actual = (root / rel).read_bytes()
        except FileNotFoundError:
            findings.append(Finding(rel, 1, "generated-stale", "missing; " + HINT))
            continue
        except OSError:
            findings.append(Finding(rel, 1, "generated-stale", "unreadable; " + HINT))
            continue
        if actual != expected:
            line = first_diff_line(actual, expected)
            findings.append(Finding(rel, line, "generated-stale", "differs from generator output; " + HINT))
    # Only ctx.files is inspected: git-ignored junk (.DS_Store, __pycache__) is never shared, so it is not reported
    # even though generate.py deletes it.
    prefixes = tuple(owned + "/" for owned in gen_adapters.OWNED_DIRS)
    for rel in sorted(set(ctx.files)):
        if rel.startswith(prefixes) and rel not in rendered:
            findings.append(Finding(rel, 1, "generated-stale", "not produced by the generator; " + HINT))
    return findings


RULES = [("generated-stale", check_generated)]
