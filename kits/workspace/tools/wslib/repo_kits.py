"""Load, validate and render repository kits under .agents/repo-kits/<kind>/."""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

KITS_DIR = Path(".agents") / "repo-kits"
TARGET = ".agents"
LEGACY_TARGET = ".agent"
STAMP = Path(TARGET) / "kit.json"
PARAM_RE = re.compile(r"[A-Z][A-Z0-9_]*")
PLACEHOLDER_RE = re.compile(rb"__([A-Z][A-Z0-9_]*)__")
VERSION_RE = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
# A kind is one folder name; this rejects separators and dot segments so it cannot point outside repo-kits.
KIND_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


class RepoKitError(Exception):
    """Raised when a repository kit cannot be rendered."""


def _kit_dir(root, kind: str) -> Path:
    return Path(root) / KITS_DIR / kind


def _compile(pattern: str):
    try:
        return re.compile(pattern), None
    # Huge repeat counts or deep nesting raise these instead of re.error.
    except (re.error, OverflowError, RecursionError, ValueError) as exc:
        return None, str(exc)


def load_kit(root, kind: str) -> Tuple[Optional[dict], List[str]]:
    """Return the parsed kit.json of kind (None when unreadable) and its problems."""
    rel = (KITS_DIR / kind / "kit.json").as_posix()
    path = Path(root) / rel
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, ["kit %s: %s is missing" % (kind, rel)]
    # UnicodeDecodeError is a ValueError; it is a read failure, not a JSON one.
    except UnicodeDecodeError as exc:
        return None, ["kit %s: %s cannot be read: %s" % (kind, rel, exc)]
    except ValueError as exc:
        return None, ["kit %s: %s is not valid JSON: %s" % (kind, rel, exc)]
    except OSError as exc:
        # str(exc) would include the absolute path; name only the kit-relative one.
        reason = exc.strerror or type(exc).__name__
        return None, ["kit %s: %s cannot be read: %s" % (kind, rel, reason)]
    if not isinstance(data, dict):
        return data, ["kit %s: %s must be an object" % (kind, rel)]
    problems = []
    if data.get("name") != kind:
        problems.append("kit %s: name must be %s" % (kind, kind))
    version = data.get("version")
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
        problems.append("kit %s: version must be MAJOR.MINOR.PATCH" % kind)
    if data.get("target") != TARGET:
        problems.append("kit %s: target must be %s" % (kind, TARGET))
    params = data.get("params")
    if not isinstance(params, dict):
        problems.append("kit %s: params must be an object" % kind)
        return data, problems
    for name, spec in params.items():
        if not PARAM_RE.fullmatch(name):
            problems.append("kit %s: parameter name %s must match ^[A-Z][A-Z0-9_]*$" % (kind, name))
        if not isinstance(spec, dict):
            problems.append("kit %s: parameter %s must be an object" % (kind, name))
            continue
        description = spec.get("description")
        if not isinstance(description, str) or not description.strip():
            problems.append("kit %s: parameter %s needs a non-empty description" % (kind, name))
        pattern = spec.get("pattern")
        if not isinstance(pattern, str):
            problems.append("kit %s: parameter %s needs a pattern" % (kind, name))
        else:
            _, error = _compile(pattern)
            if error is not None:
                problems.append("kit %s: parameter %s pattern does not compile: %s" % (kind, name, error))
    return data, problems


def kit_files(root, kind: str) -> List[str]:
    """Return the paths under files/ relative to files/, sorted, without __pycache__."""
    base = _kit_dir(root, kind) / "files"
    result = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            result.append(Path(dirpath, name).relative_to(base).as_posix())
    return sorted(result)


def _declared(kit) -> Dict[str, dict]:
    params = kit.get("params") if isinstance(kit, dict) else None
    return params if isinstance(params, dict) else {}


def undeclared_placeholders(root, kind: str) -> List[Tuple[str, str]]:
    """Return sorted unique (file, NAME) pairs for placeholders whose NAME is not a kit parameter."""
    kit, _ = load_kit(root, kind)
    declared = _declared(kit)
    base = _kit_dir(root, kind) / "files"
    pairs = set()
    for rel in kit_files(root, kind):
        for match in PLACEHOLDER_RE.finditer((base / rel).read_bytes()):
            name = match.group(1).decode("ascii")
            if name not in declared:
                pairs.add((rel, name))
    return sorted(pairs)


def load_entry(root, repository: str) -> Optional[dict]:
    """Return the repos.json entry named repository, or None."""
    try:
        data = json.loads((Path(root) / "repos.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    entries = data.get("repositories") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if isinstance(entry, dict) and entry.get("name") == repository:
            return entry
    return None


def entry_problems(root, entry: dict) -> List[str]:
    """Return problems of the entry's kit field; an entry without kit has none."""
    if "kit" not in entry:
        return []
    repo = entry.get("name")
    kit_ref = entry["kit"]
    if not isinstance(kit_ref, dict):
        return ["repository %s: kit must be an object" % repo]
    kind = kit_ref.get("kind")
    if not isinstance(kind, str) or not KIND_RE.fullmatch(kind) or not _kit_dir(root, kind).is_dir():
        return ["repository %s: kit kind %s is not a folder under %s" % (repo, kind, KITS_DIR.as_posix())]
    values = kit_ref.get("params")
    if not isinstance(values, dict):
        return ["repository %s: kit params must be an object" % repo]
    kit, kit_problems = load_kit(root, kind)
    # Without a parameter list the comparison would call every entry parameter extra.
    if not isinstance(kit, dict) or not isinstance(kit.get("params"), dict):
        return ["repository %s: kit %s is invalid: %s" % (repo, kind, "; ".join(kit_problems))]
    declared = _declared(kit)
    problems = []
    for name in declared:
        if name not in values:
            problems.append("repository %s: kit %s parameter %s is missing" % (repo, kind, name))
    for name, value in values.items():
        if name not in declared:
            problems.append("repository %s: kit %s has no parameter %s" % (repo, kind, name))
            continue
        if not isinstance(value, str):
            problems.append("repository %s: kit %s parameter %s must be a string" % (repo, kind, name))
            continue
        spec = declared[name]
        pattern = spec.get("pattern") if isinstance(spec, dict) else None
        # An invalid pattern is a kit problem reported by load_kit, not an entry problem.
        compiled = _compile(pattern)[0] if isinstance(pattern, str) else None
        if compiled is not None and not compiled.fullmatch(value):
            problems.append(
                "repository %s: kit %s parameter %s value %r does not match %s" % (repo, kind, name, value, pattern)
            )
    return problems


def render(root, repository: str) -> "OrderedDict[str, bytes]":
    """Return {".agents/<path>": bytes} for the repository's kit with placeholders replaced."""
    entry = load_entry(root, repository)
    if entry is None:
        raise RepoKitError("repository %s is not in repos.json" % repository)
    if "kit" not in entry:
        raise RepoKitError("repository %s has no kit" % repository)
    problems = entry_problems(root, entry)
    if problems:
        raise RepoKitError("; ".join(problems))
    kind = entry["kit"]["kind"]
    kit, problems = load_kit(root, kind)
    if problems:
        raise RepoKitError("; ".join(problems))
    values = {name: value.encode("utf-8") for name, value in entry["kit"]["params"].items()}
    base = _kit_dir(root, kind) / "files"
    out: "OrderedDict[str, bytes]" = OrderedDict()
    for rel in kit_files(root, kind):
        missing = []

        def substitute(match):
            name = match.group(1).decode("ascii")
            if name not in values:
                missing.append(name)
                return match.group(0)
            return values[name]

        # Bytes in, bytes out: line endings and encoding of the kit file are kept as they are.
        content = PLACEHOLDER_RE.sub(substitute, (base / rel).read_bytes())
        if missing:
            raise RepoKitError(
                "kit %s: files/%s uses undeclared placeholder %s" % (kind, rel, ", ".join(sorted(set(missing))))
            )
        out["%s/%s" % (kit["target"], rel)] = content
    return out


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def read_stamp(clone) -> Optional[dict]:
    """Return the parsed <clone>/.agents/kit.json, or None when it is missing or not a JSON object."""
    try:
        data = json.loads((Path(clone) / STAMP).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _clone_base(clone) -> Path:
    clone = Path(clone)
    if not (clone / TARGET).is_dir() and (clone / LEGACY_TARGET).is_dir():
        return clone / LEGACY_TARGET
    return clone / TARGET


def _read_clone_file(base: Path, path: str) -> Optional[bytes]:
    file = base / path[len(TARGET) + 1:]
    return file.read_bytes() if file.is_file() else None


def status(root, repository: str, clone) -> List[Tuple[str, str]]:
    """Return sorted (state, path) pairs comparing the rendered kit with the clone and its stamp."""
    rendered = render(root, repository)
    stamp = read_stamp(clone)
    stamped = stamp.get("files") if stamp is not None else None
    if not isinstance(stamped, dict):
        stamped = {}
    base = _clone_base(clone)
    prefix = TARGET + "/"
    result = []
    for path, content in rendered.items():
        current = _read_clone_file(base, path)
        if current is None:
            result.append(("absent", path))
        elif current == content:
            result.append(("same", path))
        elif stamped.get(path) == _sha256(current):
            result.append(("replaceable", path))
        else:
            result.append(("edited", path))
    for path, digest in stamped.items():
        # Only paths inside the kit folder count; anything else in a hand-edited stamp is ignored.
        if path in rendered or not path.startswith(prefix) or ".." in path.split("/"):
            continue
        current = _read_clone_file(base, path)
        if current is not None:
            result.append(("obsolete" if digest == _sha256(current) else "removed-edited", path))
    for dirpath, _, filenames in os.walk(base):
        for name in filenames:
            path = prefix + Path(dirpath, name).relative_to(base).as_posix()
            if path in rendered or path in stamped or path == STAMP.as_posix() or path.startswith(prefix + "local/"):
                continue
            result.append(("foreign", path))
    return sorted(result, key=lambda item: item[1])


def stamp_text(root, repository: str) -> str:
    """Return the stamp JSON for the repository's rendered kit."""
    rendered = render(root, repository)
    entry = load_entry(root, repository)
    kit, _ = load_kit(root, entry["kit"]["kind"])
    values = entry["kit"]["params"]
    stamp = OrderedDict()
    stamp["kind"] = entry["kit"]["kind"]
    stamp["version"] = kit["version"]
    stamp["params"] = OrderedDict((name, values[name]) for name in kit["params"])
    stamp["files"] = OrderedDict((path, _sha256(rendered[path])) for path in sorted(rendered))
    return json.dumps(stamp, indent=2, ensure_ascii=False) + "\n"


def write_stamp(root, repository: str, clone) -> None:
    """Write the stamp to <clone>/.agents/kit.json."""
    text = stamp_text(root, repository)
    path = Path(clone) / STAMP
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
