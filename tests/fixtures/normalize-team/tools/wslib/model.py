"""Read-only workspace lifecycle model: map elements, streams and stories discovered from Context files."""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from wslib import tables
from wslib.common import Finding, parse_frontmatter
from wslib.profiles import PROFILES_DIR, RULE as PROFILE_RULE, load_profiles

LIFECYCLE = "lifecycle"


def _frontmatter(ctx, rel: str) -> Tuple[Optional[str], Optional[dict], Optional[str]]:
    """Return (text, fields, error) of a Markdown file."""
    text = ctx.read_text(rel)
    if text is None:
        return None, None, "missing or unreadable file"
    fields, _, error = parse_frontmatter(text)
    if fields is None and error is None:
        error = "missing frontmatter"
    return text, fields, error


class Element:
    def __init__(self, ctx, prefix: str, kind: str, domain: str, slug: str, rel: str, table_specs: list):
        self.key = "%s:%s/%s" % (prefix, domain, slug)
        self.kind = kind
        self.domain = domain
        self.slug = slug
        self.path = rel
        text, self.fields, self.error = _frontmatter(ctx, rel)
        self.tables: Dict[str, tuple] = {}
        for spec in table_specs:
            heading = spec["heading"]
            # Parsing the whole file keeps row numbers as file lines; frontmatter never holds `## ` lines.
            self.tables[heading] = tables.parse_table(text or "", heading)


class Story:
    def __init__(self, ctx, domain: str, stream: str, slug: str, rel: str):
        self.key = "story:%s/%s" % (domain, slug)
        self.domain = domain
        self.stream = stream
        self.slug = slug
        self.path = rel
        text, self.fields, self.error = _frontmatter(ctx, rel)
        self.sections = tables.sections(text or "")


class Stream:
    def __init__(self, ctx, domain: str, name: str, rel: str, present: bool = True):
        self.key = "stream:%s/%s" % (domain, name)
        self.domain = domain
        self.name = name
        self.path = rel
        self.epic_path = "domains/%s/streams/%s/epic.md" % (domain, name)
        self.stories: Dict[str, Story] = {}
        self.data: Optional[dict] = None
        self.error: Optional[Finding] = None
        if not present:
            self.error = Finding(rel, 1, LIFECYCLE, "missing stream.json")
        else:
            data, error = ctx.load_json(rel)
            if error is not None:
                self.error = Finding(rel, error.line, LIFECYCLE, error.message)
            elif not isinstance(data, dict):
                self.error = Finding(rel, 1, LIFECYCLE, "stream.json must be a JSON object")
            else:
                self.data = data
        profile = self.data.get("profile") if self.data is not None else None
        self.profile_name: Optional[str] = profile if isinstance(profile, str) else None


def _compile_id_pattern(ctx):
    data, error = ctx.load_json("tracker/tracker.json")
    if error is not None or not isinstance(data, dict) or not isinstance(data.get("id_pattern"), str):
        return None
    try:
        return re.compile(data["id_pattern"])
    except (re.error, OverflowError, RecursionError, ValueError):
        return None


class Workspace:
    def __init__(self, ctx):
        self.ctx = ctx
        self.profiles, self.profile_findings = load_profiles(ctx)
        self.elements: Dict[str, Element] = {}
        self.element_list: List[Element] = []
        self.streams: List[Stream] = []
        self.stories: Dict[str, Story] = {}
        self.map_docs: Dict[str, str] = {}
        self.id_pattern = _compile_id_pattern(ctx)

        split = [(rel, rel.split("/")) for rel in ctx.files if rel.startswith("domains/")]
        self._discover_elements(ctx, split)
        self._discover_streams(ctx, split)
        for rel, parts in split:
            if len(parts) == 3 and parts[2] == "MAP.md":
                self.map_docs[parts[1]] = rel

    def _discover_elements(self, ctx, split) -> None:
        owners: Dict[str, Tuple[str, str]] = {}
        for name, profile in self.profiles.items():
            for spec in profile["elements"]:
                owner = owners.get(spec["dir"])
                if owner is not None:
                    # Files of a shared directory stay with the first kind; the later declaration is reported.
                    self.profile_findings.append(
                        Finding(
                            "%s/%s/profile.json" % (PROFILES_DIR, name),
                            1,
                            PROFILE_RULE,
                            "kind %s of profile %s uses dir %s already used by kind %s of profile %s"
                            % (spec["kind"], name, spec["dir"], owner[0], owner[1]),
                        )
                    )
                    continue
                owners[spec["dir"]] = (spec["kind"], name)
                for rel, parts in split:
                    if len(parts) != 4 or parts[2] != spec["dir"] or not parts[3].endswith(".md"):
                        continue
                    element = Element(
                        ctx, spec["prefix"], spec["kind"], parts[1], parts[3][: -len(".md")], rel, spec.get("tables", [])
                    )
                    self.element_list.append(element)
                    self.elements.setdefault(element.key, element)

    def _discover_streams(self, ctx, split) -> None:
        with_json = set()
        story_files = []
        for rel, parts in split:
            if len(parts) == 5 and parts[2] == "streams" and parts[4] == "stream.json":
                with_json.add((parts[1], parts[3]))
            elif len(parts) == 7 and parts[2] == "streams" and parts[4] == "stories" and parts[6] == "story.md":
                story_files.append((rel, parts))
        # A folder with stories but no (or an ignored) stream.json is still a stream, so its stories are not lost.
        folders = with_json | {(parts[1], parts[3]) for _, parts in story_files}
        by_folder: Dict[Tuple[str, str], Stream] = {}
        for domain, name in sorted(folders):
            rel = "domains/%s/streams/%s/stream.json" % (domain, name)
            stream = Stream(ctx, domain, name, rel, present=(domain, name) in with_json)
            self.streams.append(stream)
            by_folder[(domain, name)] = stream
        for rel, parts in story_files:
            stream = by_folder[(parts[1], parts[3])]
            story = Story(ctx, parts[1], parts[3], parts[5], rel)
            stream.stories[story.key] = story
            self.stories.setdefault(story.key, story)
