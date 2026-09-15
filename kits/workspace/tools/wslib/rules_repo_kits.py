"""Rule: repository kits under .agents/repo-kits/ and the kit field of repos.json entries."""
from __future__ import annotations

import json
from typing import List

from wslib import repo_kits
from wslib.common import Context, Finding

RULE = "repo-kit"


def _entry_line(text: str, name) -> int:
    """Return the line of the entry's "name" field in repos.json, or 1 when it is not found."""
    if not isinstance(name, str):
        return 1
    needle = '"name": ' + json.dumps(name, ensure_ascii=False)
    for lineno, line in enumerate(text.split("\n"), start=1):
        if needle in line:
            return lineno
    return 1


def _placeholder_findings(ctx: Context, kind: str, declared: dict) -> List[Finding]:
    # Scanned file by file instead of repo_kits.undeclared_placeholders, which stops at the first
    # unreadable file; here that file becomes a finding and the rest are still checked.
    base = repo_kits.KITS_DIR / kind / "files"
    findings = []
    for rel in repo_kits.kit_files(ctx.root, kind):
        path = (base / rel).as_posix()
        try:
            data = (ctx.root / path).read_bytes()
        except OSError as exc:
            reason = exc.strerror or type(exc).__name__
            findings.append(Finding(path, 0, RULE, "kit %s: files/%s cannot be read: %s" % (kind, rel, reason)))
            continue
        seen = set()
        for match in repo_kits.PLACEHOLDER_RE.finditer(data):
            name = match.group(1).decode("ascii")
            if name in declared or name in seen:
                continue
            seen.add(name)
            findings.append(Finding(
                path, data.count(b"\n", 0, match.start()) + 1, RULE,
                "kit %s: files/%s uses undeclared placeholder %s" % (kind, rel, name)))
    return findings


def _kit_findings(ctx: Context, kind: str) -> List[Finding]:
    rel = (repo_kits.KITS_DIR / kind / "kit.json").as_posix()
    kit, problems = repo_kits.load_kit(ctx.root, kind)
    findings = [Finding(rel, 0, RULE, problem) for problem in problems]
    # Without a params object every placeholder would read as undeclared; the kit.json finding already covers it.
    if not isinstance(kit, dict) or not isinstance(kit.get("params"), dict):
        return findings
    return findings + _placeholder_findings(ctx, kind, kit["params"])


def _entry_findings(ctx: Context) -> List[Finding]:
    rel = "repos.json"
    if rel not in ctx.files:
        return []
    data, error = ctx.load_json(rel)
    # json-shape reports a broken or misshapen repos.json.
    if error is not None or not isinstance(data, dict) or not isinstance(data.get("repositories"), list):
        return []
    text = ctx.read_text(rel) or ""
    findings = []
    for entry in data["repositories"]:
        if not isinstance(entry, dict):
            continue
        line = _entry_line(text, entry.get("name"))
        findings.extend(Finding(rel, line, RULE, problem) for problem in repo_kits.entry_problems(ctx.root, entry))
    return findings


def check_repo_kits(ctx: Context) -> List[Finding]:
    findings: List[Finding] = []
    kits_dir = ctx.root / repo_kits.KITS_DIR
    if kits_dir.is_dir():
        for kind in sorted(p.name for p in kits_dir.iterdir() if p.is_dir()):
            findings.extend(_kit_findings(ctx, kind))
    findings.extend(_entry_findings(ctx))
    return findings


RULES = [(RULE, check_repo_kits)]
