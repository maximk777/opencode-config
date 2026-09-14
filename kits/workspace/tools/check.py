#!/usr/bin/env python3
"""Check a workspace against its rules and print path:line rule-id message."""
import argparse
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


def print_remaining(root):
    """Print the current stage's gate failures; always exit 0, reporting an internal error on stderr."""
    try:
        from wslib import rules_lifecycle

        for line in rules_lifecycle.remaining(common.Context(root)):
            print(line)
    except Exception as exc:
        print(f"check: internal error: {exc!r}", file=sys.stderr)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="check.py", description=__doc__)
    parser.add_argument(
        "--remaining", action="store_true", help="print the current stage's gate failures and exit 0"
    )
    args = parser.parse_args(argv)
    root = common.find_root(Path.cwd())
    if root is None:
        print("check: not inside a workspace (no .agents/kit.json)", file=sys.stderr)
        return 2
    if args.remaining:
        return print_remaining(root)
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
