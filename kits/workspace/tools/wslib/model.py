"""Read-only workspace lifecycle model: map elements, streams, stories and workspace tasks discovered from Context files."""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from wslib import tables
from wslib.common import Finding, parse_frontmatter
from wslib.profiles import PROFILES_DIR, RULE as PROFILE_RULE, load_profiles

LIFECYCLE = "lifecycle"
TRACKERS_REL = "tracker/trackers.json"


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
    def __init__(self, ctx, prefix: str, kind: str, project: str, domain: str, slug: str, rel: str, table_specs: list):
        self.key = "%s:%s/%s/%s" % (prefix, project, domain, slug)
        self.kind = kind
        self.project = project
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
    def __init__(self, ctx, project: str, domain: str, stream: str, slug: str, rel: str):
        self.key = "story:%s/%s/%s" % (project, domain, slug)
        self.project = project
        self.domain = domain
        self.stream = stream
        self.slug = slug
        self.path = rel
        text, self.fields, self.error = _frontmatter(ctx, rel)
        self.sections = tables.sections(text or "")


class Task:
    """Workspace task at tasks/<slug>/task.md; frontmatter shape matches a story."""

    def __init__(self, ctx, slug: str, rel: str):
        self.key = "task:%s" % slug
        self.slug = slug
        self.path = rel
        text, self.fields, self.error = _frontmatter(ctx, rel)
        self.sections = tables.sections(text or "")


class Stream:
    def __init__(self, ctx, project: str, domain: str, name: str, rel: str, present: bool = True):
        self.key = "stream:%s/%s/%s" % (project, domain, name)
        self.project = project
        self.domain = domain
        self.name = name
        self.path = rel
        self.epic_path = "projects/%s/domains/%s/streams/%s/epic.md" % (project, domain, name)
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


class Tracker:
    def __init__(self, key: str, id_pattern: str, url: Optional[str], pattern: "re.Pattern[str]"):
        self.key = key
        self.id_pattern = id_pattern
        self.url = url
        self.pattern = pattern


def _load_trackers(ctx) -> List[Tracker]:
    """Load tracker/trackers.json; invalid entries are skipped, shape reporting stays in check."""
    data, error = ctx.load_json(TRACKERS_REL)
    if error is not None or not isinstance(data, dict) or not isinstance(data.get("trackers"), list):
        return []
    trackers: List[Tracker] = []
    for item in data["trackers"]:
        if not isinstance(item, dict) or not isinstance(item.get("key"), str) or not isinstance(item.get("id_pattern"), str):
            continue
        try:
            pattern = re.compile(item["id_pattern"])
        except (re.error, OverflowError, RecursionError, ValueError):
            continue
        url = item.get("url")
        trackers.append(Tracker(item["key"], item["id_pattern"], url if isinstance(url, str) else None, pattern))
    return trackers


class Workspace:
    def __init__(self, ctx):
        self.ctx = ctx
        self.profiles, self.profile_findings = load_profiles(ctx)
        self.elements: Dict[str, Element] = {}
        self.element_list: List[Element] = []
        self.streams: List[Stream] = []
        self.stories: Dict[str, Story] = {}
        self.tasks: Dict[str, Task] = {}
        self.map_docs: Dict[str, str] = {}
        self.trackers = _load_trackers(ctx)

        split = [(rel, rel.split("/")) for rel in ctx.files if rel.startswith("projects/")]
        self._discover_elements(ctx, split)
        self._discover_streams(ctx, split)
        self._discover_tasks(ctx)
        for rel, parts in split:
            if len(parts) == 5 and parts[2] == "domains" and parts[4] == "MAP.md":
                # Keyed by project/domain: the same domain name may exist in different projects.
                self.map_docs["%s/%s" % (parts[1], parts[3])] = rel

    def match_tracker(self, tracker_id: str) -> Optional[str]:
        """Key of the one tracker whose id_pattern matches, "ambiguous" on several, None on none."""
        matches = [t.key for t in self.trackers if t.pattern.fullmatch(tracker_id)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return "ambiguous"
        return None

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
                    if len(parts) != 6 or parts[2] != "domains" or parts[4] != spec["dir"] or not parts[5].endswith(".md"):
                        continue
                    element = Element(
                        ctx,
                        spec["prefix"],
                        spec["kind"],
                        parts[1],
                        parts[3],
                        parts[5][: -len(".md")],
                        rel,
                        spec.get("tables", []),
                    )
                    self.element_list.append(element)
                    self.elements.setdefault(element.key, element)

    def _discover_streams(self, ctx, split) -> None:
        with_json = set()
        story_files = []
        for rel, parts in split:
            if len(parts) == 7 and parts[2] == "domains" and parts[4] == "streams" and parts[6] == "stream.json":
                with_json.add((parts[1], parts[3], parts[5]))
            elif (
                len(parts) == 9
                and parts[2] == "domains"
                and parts[4] == "streams"
                and parts[6] == "stories"
                and parts[8] == "story.md"
            ):
                story_files.append((rel, parts))
        # A folder with stories but no (or an ignored) stream.json is still a stream, so its stories are not lost.
        folders = with_json | {(parts[1], parts[3], parts[5]) for _, parts in story_files}
        by_folder: Dict[Tuple[str, str, str], Stream] = {}
        for project, domain, name in sorted(folders):
            rel = "projects/%s/domains/%s/streams/%s/stream.json" % (project, domain, name)
            stream = Stream(ctx, project, domain, name, rel, present=(project, domain, name) in with_json)
            self.streams.append(stream)
            by_folder[(project, domain, name)] = stream
        for rel, parts in story_files:
            stream = by_folder[(parts[1], parts[3], parts[5])]
            story = Story(ctx, parts[1], parts[3], parts[5], parts[7], rel)
            stream.stories[story.key] = story
            self.stories.setdefault(story.key, story)

    def _discover_tasks(self, ctx) -> None:
        for rel in ctx.files:
            parts = rel.split("/")
            if len(parts) != 3 or parts[0] != "tasks" or parts[2] != "task.md":
                continue
            task = Task(ctx, parts[1], rel)
            self.tasks.setdefault(task.key, task)
