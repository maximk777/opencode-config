#!/usr/bin/env python3
"""Render a repository kit, compare it with a clone, or write the clone's kit stamp."""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path  # noqa: E402

from wslib import repo_kits  # noqa: E402


class UsageError(Exception):
    """Raised for invalid command input that is not a kit problem."""


def _clone(path: str) -> Path:
    clone = Path(path)
    if not clone.is_dir():
        raise UsageError("clone %s is not a directory" % path)
    return clone


def cmd_render(root: Path, args) -> None:
    # Render fully in memory first so an invalid kit leaves <out> untouched.
    rendered = repo_kits.render(root, args.repository)
    out = Path(args.out)
    for path, content in rendered.items():
        target = out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def cmd_status(root: Path, args) -> None:
    for pair in repo_kits.status(root, args.repository, _clone(args.clone)):
        print("%s %s" % pair)


def cmd_stamp(root: Path, args) -> None:
    repo_kits.write_stamp(root, args.repository, _clone(args.clone))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="repo_kit.py", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    render = commands.add_parser("render", help="write the rendered kit under <out>")
    render.add_argument("repository")
    render.add_argument("out")
    render.set_defaults(func=cmd_render)
    for name, func, help_text in (
        ("status", cmd_status, "print <state> <path> for every kit path of the clone"),
        ("stamp", cmd_stamp, "write <clone>/.agents/kit.json"),
    ):
        sub = commands.add_parser(name, help=help_text)
        sub.add_argument("repository")
        sub.add_argument("clone")
        sub.set_defaults(func=func)
    args = parser.parse_args(argv)
    try:
        args.func(Path.cwd(), args)
    except (repo_kits.RepoKitError, UsageError) as exc:
        print("repo_kit: %s" % exc, file=sys.stderr)
        return 2
    except OSError as exc:
        reason = exc.strerror or exc
        if exc.filename is None:
            print("repo_kit: %s" % reason, file=sys.stderr)
        else:
            print("repo_kit: cannot access %s: %s" % (exc.filename, reason), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
