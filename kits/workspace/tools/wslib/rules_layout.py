"""Rules for required workspace files and the shape of workspace JSON files."""
from __future__ import annotations

import json
import re
from typing import Callable, Dict, List

from wslib.common import Context, Finding

REQUIRED = [
    "AGENTS.md",
    "README.md",
    "CLAUDE.md",
    "repos.json",
    "REPOSITORIES.md",
    "environments.json",
    "STATUS.md",
    "tracker/trackers.json",
    ".gitignore",
    ".agents/kit.json",
    ".agents/env.schema.json",
    ".agents/index.json",
    "tools/check.py",
    "tools/generate.py",
]
FORGES = ("gitlab", "github", "git")
STATUSES = ("active", "planned")
KIT_PARAMS = ("workspace_name", "title", "forge", "id_pattern", "tracker_url")
# Used with fullmatch: "$" in match() would accept a trailing newline.
STAND_KEY_RE = re.compile(r"stand:[a-z0-9][a-z0-9-]*")
VARIABLE_RE = re.compile(r"[A-Z][A-Z0-9_]*")


def check_layout(ctx: Context) -> List[Finding]:
    present = set(ctx.files)
    findings = [
        Finding(path, 1, "layout", "required file is missing or ignored by git")
        for path in REQUIRED
        if path not in present
    ]
    # Directory names only appear in ctx.files when the project holds at least one tracked file;
    # a file directly under projects/ is a stray file, not a project directory.
    projects = {
        rel.split("/")[1] for rel in ctx.files if rel.startswith("projects/") and "/" in rel[len("projects/"):]
    }
    findings.extend(
        Finding("projects/%s/PROJECT.md" % name, 1, "layout", "required file is missing or ignored by git")
        for name in sorted(projects)
        if "projects/%s/PROJECT.md" % name not in present
    )
    return findings


def _is_cell(value) -> bool:
    """A non-empty string that can become a Markdown table cell."""
    return isinstance(value, str) and value != "" and not any(c in value for c in "|\r\n")


def _entry_line(text: str, name) -> int:
    if not isinstance(name, str):
        return 1
    needle = '"name": ' + json.dumps(name, ensure_ascii=False)
    for lineno, line in enumerate(text.split("\n"), start=1):
        if needle in line:
            return lineno
    return 1


def _repos(ctx: Context, rel: str, data) -> List[Finding]:
    if not isinstance(data, dict) or not isinstance(data.get("repositories"), list):
        return [Finding(rel, 1, "json-shape", "expected an object with a list repositories")]
    text = ctx.read_text(rel) or ""
    findings = []
    names: Dict[str, int] = {}
    remotes: Dict[str, int] = {}
    for index, entry in enumerate(data["repositories"]):
        if not isinstance(entry, dict):
            findings.append(Finding(rel, 1, "json-shape", "repositories[%d] is not an object" % index))
            continue
        line = _entry_line(text, entry.get("name"))
        label = "repositories[%d]" % index

        def bad(message, line=line, label=label):
            findings.append(Finding(rel, line, "json-shape", "%s %s" % (label, message)))

        status = entry.get("status")
        if "status" in entry and status not in STATUSES:
            bad("status must be one of %s" % ", ".join(STATUSES))
        fields = ["name", "default_branch", "summary"]
        # A planned repository does not exist yet, but a remote it already names must still be valid.
        if status != "planned" or "remote" in entry:
            fields.insert(1, "remote")
        for field in fields:
            if not _is_cell(entry.get(field)):
                bad("%s must be a non-empty string without | or line breaks" % field)
        if entry.get("forge") not in FORGES:
            bad("forge must be one of %s" % ", ".join(FORGES))
        for field, seen in (("name", names), ("remote", remotes)):
            value = entry.get(field)
            if not isinstance(value, str) or value == "":
                continue
            if value in seen:
                bad("duplicate %s %s" % (field, value))
            else:
                seen[value] = index
    return findings


def _environments(ctx: Context, rel: str, data) -> List[Finding]:
    if not isinstance(data, dict) or not isinstance(data.get("stands"), list):
        return [Finding(rel, 1, "json-shape", "expected an object with a list stands")]
    findings = []
    keys = set()
    for index, stand in enumerate(data["stands"]):
        label = "stands[%d]" % index
        if not isinstance(stand, dict):
            findings.append(Finding(rel, 1, "json-shape", "%s is not an object" % label))
            continue
        key = stand.get("key")
        if not isinstance(key, str) or not STAND_KEY_RE.fullmatch(key):
            findings.append(Finding(rel, 1, "json-shape", "%s key must match stand:<name>" % label))
        elif key in keys:
            findings.append(Finding(rel, 1, "json-shape", "%s duplicate key %s" % (label, key)))
        else:
            keys.add(key)
        for field in ("purpose", "access"):
            if not isinstance(stand.get(field), str):
                findings.append(Finding(rel, 1, "json-shape", "%s %s must be a string" % (label, field)))
        services = stand.get("services")
        if not isinstance(services, dict) or not all(
            isinstance(url, str) and url.startswith(("http://", "https://")) for url in services.values()
        ):
            findings.append(
                Finding(rel, 1, "json-shape", "%s services must map names to http(s) URLs" % label)
            )
    return findings


def _env_schema(ctx: Context, rel: str, data) -> List[Finding]:
    if not isinstance(data, dict) or not isinstance(data.get("variables"), list):
        return [Finding(rel, 1, "json-shape", "expected an object with a list variables")]
    findings = []
    for index, variable in enumerate(data["variables"]):
        label = "variables[%d]" % index
        if not isinstance(variable, dict):
            findings.append(Finding(rel, 1, "json-shape", "%s is not an object" % label))
            continue
        name = variable.get("name")
        if not isinstance(name, str) or not VARIABLE_RE.fullmatch(name):
            findings.append(Finding(rel, 1, "json-shape", "%s name must match [A-Z][A-Z0-9_]*" % label))
        for field in ("issued_by", "how_to_get"):
            if not isinstance(variable.get(field), str):
                findings.append(Finding(rel, 1, "json-shape", "%s %s must be a string" % (label, field)))
    return findings


def _trackers(ctx: Context, rel: str, data) -> List[Finding]:
    if not isinstance(data, dict) or not isinstance(data.get("trackers"), list) or not data["trackers"]:
        return [Finding(rel, 1, "json-shape", "expected an object with a non-empty list trackers")]
    findings = []
    keys: Dict[str, int] = {}
    for index, tracker in enumerate(data["trackers"]):
        if not isinstance(tracker, dict):
            findings.append(Finding(rel, 1, "json-shape", "trackers[%d] is not an object" % index))
            continue
        label = "trackers[%d]" % index
        key = tracker.get("key")
        if not isinstance(key, str) or key == "":
            findings.append(Finding(rel, 1, "json-shape", "%s key must be a non-empty string" % label))
        elif key in keys:
            findings.append(Finding(rel, 1, "json-shape", "%s duplicate key %s" % (label, key)))
        else:
            keys[key] = index
        pattern = tracker.get("id_pattern")
        if not isinstance(pattern, str):
            findings.append(Finding(rel, 1, "json-shape", "%s id_pattern must be a string" % label))
        else:
            try:
                re.compile(pattern)
            # Huge repeat counts or deep nesting raise these instead of re.error.
            except (re.error, OverflowError, RecursionError, ValueError) as exc:
                findings.append(Finding(rel, 1, "json-shape", "%s id_pattern does not compile: %s" % (label, exc)))
        url = tracker.get("url")
        if not isinstance(url, str) or "{id}" not in url:
            findings.append(Finding(rel, 1, "json-shape", "%s url must be a string containing {id}" % label))
    return findings


def _kit(ctx: Context, rel: str, data) -> List[Finding]:
    if not isinstance(data, dict):
        return [Finding(rel, 1, "json-shape", "expected an object")]
    findings = []
    for field in ("name", "version"):
        if not isinstance(data.get(field), str):
            findings.append(Finding(rel, 1, "json-shape", "%s must be a string" % field))
    params = data.get("params")
    if not isinstance(params, dict):
        findings.append(Finding(rel, 1, "json-shape", "params must be an object"))
    else:
        for param in KIT_PARAMS:
            if not isinstance(params.get(param), str):
                findings.append(Finding(rel, 1, "json-shape", "params.%s must be a string" % param))
    return findings


SHAPES: Dict[str, Callable[[Context, str, object], List[Finding]]] = {
    "repos.json": _repos,
    "environments.json": _environments,
    ".agents/env.schema.json": _env_schema,
    "tracker/trackers.json": _trackers,
    ".agents/kit.json": _kit,
}


def check_json_shape(ctx: Context) -> List[Finding]:
    present = set(ctx.files)
    findings: List[Finding] = []
    for rel, validate in SHAPES.items():
        if rel not in present:
            continue
        data, error = ctx.load_json(rel)
        if error is not None:
            findings.append(error)
            continue
        findings.extend(validate(ctx, rel, data))
    return findings


RULES = [("layout", check_layout), ("json-shape", check_json_shape)]
