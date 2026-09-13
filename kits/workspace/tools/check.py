#!/usr/bin/env python3
"""Check a workspace against its rules and print path:line rule-id message."""
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path  # noqa: E402

from wslib import common  # noqa: E402


def load_rules():
    rules = []
    wslib_dir = Path(__file__).resolve().parent / "wslib"
    for path in sorted(wslib_dir.glob("rules_*.py")):
        module = importlib.import_module("wslib." + path.stem)
        rules.extend(module.RULES)
    return rules


def main():
    root = common.find_root(Path.cwd())
    if root is None:
        print("check: not inside a workspace (no .agents/kit.json)", file=sys.stderr)
        return 2
    ctx = common.Context(root)
    findings = []
    for _rule_id, fn in load_rules():
        findings.extend(fn(ctx))
    findings.sort(key=lambda f: (f.path, f.line, f.rule))
    for f in findings:
        print(common.format_finding(f))
    return 1 if findings else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # a broken rule must not look like a clean workspace
        print(f"check: internal error: {exc!r}", file=sys.stderr)
        sys.exit(2)
