"""Rules against environment leaks: home paths, .local links, secrets, raw stand URLs."""
from __future__ import annotations

import posixpath
import re
from typing import Iterator, List, Tuple

from wslib.common import Finding, md_links, resolve_target

# Name classes exclude "<" and "[" so documentation placeholders and these patterns do not match.
# The lookbehind skips URL and API segments such as example.org/home/... or /api/Users/...;
# the Windows form also accepts JSON-escaped double backslashes.
HOME_RES = [
    re.compile(r"(?<![\w.-])/Users/[A-Za-z0-9._-]+/"),
    re.compile(r"(?<![\w.-])/home/[A-Za-z0-9._-]+/"),
    re.compile(r"[A-Za-z]:\\{1,2}Users\\{1,2}[A-Za-z0-9._-]+\\"),
]
# A registered base URL must not continue into a longer host name.
URL_END = r"(?![A-Za-z0-9.-])"
SECRET_NAMES = {".env", "id_rsa", "id_ed25519", "id_ecdsa"}
SECRET_SUFFIXES = (".pem", ".key", ".p12")
ENVIRONMENTS = "environments.json"


def _texts(ctx) -> Iterator[Tuple[str, str]]:
    for rel in ctx.files:
        text = ctx.read_text(rel)
        if text is not None:
            yield rel, text


def check_home_path(ctx) -> List[Finding]:
    findings: List[Finding] = []
    for rel, text in _texts(ctx):
        for lineno, line in enumerate(text.split("\n"), start=1):
            if any(pattern.search(line) for pattern in HOME_RES):
                findings.append(Finding(rel, lineno, "home-path", "absolute home path; use a relative path or a key"))
    return findings


def check_local_link(ctx) -> List[Finding]:
    findings: List[Finding] = []
    for rel, text in _texts(ctx):
        seen = set()
        for lineno, _label, target in md_links(text):
            if lineno in seen or "://" in target or target.startswith("mailto:"):
                continue
            resolved = resolve_target(rel, target)
            if resolved == ".local" or resolved.startswith(".local/"):
                seen.add(lineno)
                findings.append(Finding(rel, lineno, "local-link", "link into .local/ %s; move the content into work/ or docs/" % target))
    return findings


def check_secret_file(ctx) -> List[Finding]:
    findings: List[Finding] = []
    for rel in ctx.files:
        name = posixpath.basename(rel)
        if (
            name in SECRET_NAMES
            or (name.startswith(".env.") and not name.endswith(".example"))
            or rel.endswith(SECRET_SUFFIXES)
            or rel.startswith((".local/", "repos/"))
        ):
            findings.append(Finding(rel, 1, "secret-file", "secret-like file is not ignored by git"))
    return findings


def check_stand_string(ctx) -> List[Finding]:
    data, error = ctx.load_json(ENVIRONMENTS)
    if error is not None or not isinstance(data, dict) or not isinstance(data.get("stands"), list):
        return []
    urls = []
    for stand in data["stands"]:
        services = stand.get("services") if isinstance(stand, dict) else None
        if not isinstance(services, dict):
            continue
        for url in services.values():
            if isinstance(url, str) and url.rstrip("/"):
                urls.append(url.rstrip("/"))
    if not urls:
        return []
    patterns = [(url, re.compile(re.escape(url) + URL_END)) for url in urls]
    findings: List[Finding] = []
    for rel, text in _texts(ctx):
        if rel == ENVIRONMENTS:
            continue
        for lineno, line in enumerate(text.split("\n"), start=1):
            found = next((url for url, pattern in patterns if pattern.search(line)), None)
            if found is not None:
                findings.append(Finding(rel, lineno, "stand-string", "raw stand URL %s; link a stand: key instead" % found))
    return findings


RULES = [
    ("home-path", check_home_path),
    ("local-link", check_local_link),
    ("secret-file", check_secret_file),
    ("stand-string", check_stand_string),
]
