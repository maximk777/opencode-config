"""Recipes for generated files, applied by hand, must equal tools/generate.py output."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/workspace/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from workspace_helpers import create_workspace, run_generate  # noqa: E402


def tree_bytes(root):
    # __pycache__ holds interpreter bytecode whose header embeds source mtimes, so it differs between any two workspaces.
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in sorted(root.rglob("*"))
            if p.is_file() and not {".git", "__pycache__"} & set(p.relative_to(root).parts)}


def write(ws, rel, text):
    path = ws / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def add_repository_source(ws, entry):
    manifest = json.loads((ws / "repos.json").read_text(encoding="utf-8"))
    manifest["repositories"].append(entry)
    write(ws, "repos.json", json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


def recipe_repository(ws, entry):
    text = (ws / "REPOSITORIES.md").read_text(encoding="utf-8")
    row = "| %s | %s | %s | %s | %s |" % (
        entry["name"], entry["forge"], entry["default_branch"], ", ".join(entry["roles"]), entry["summary"])
    end = "<!-- repos:end -->"
    assert text.count(end) == 1
    write(ws, "REPOSITORIES.md", text.replace(end, row + "\n" + end))


def recipe_adr(ws, number, slug):
    rel = ".agents/index.json"
    text = (ws / rel).read_text(encoding="utf-8")
    entry = '  "adr:%s": "docs/adr/%s-%s.md"' % (number, number, slug)
    if text == "{}\n":
        write(ws, rel, "{\n" + entry + "\n}\n")
        return
    lines = text.split("\n")
    adr_lines = [i for i, line in enumerate(lines) if line.startswith('  "adr:')]
    pos = adr_lines[-1] + 1 if adr_lines else lines.index("{") + 1
    before, after = lines[pos - 1], lines[pos]
    if before.startswith("  ") and not before.endswith(","):
        lines[pos - 1] = before + ","
    if after.startswith("  "):
        entry += ","
    lines.insert(pos, entry)
    write(ws, rel, "\n".join(lines))


def recipe_skill(ws, name):
    # The literal commands from the skill recipe in .agents/skills/extend/SKILL.md.
    commands = [
        "mkdir -p .claude/skills/{n} && cp -R .agents/skills/{n}/. .claude/skills/{n}/",
        "find .claude/skills/{n} -name .DS_Store -type f -delete",
        "find .claude/skills/{n} -name __pycache__ -type d -prune -exec rm -rf {{}} +",
    ]
    for command in commands:
        subprocess.run(command.format(n=name), shell=True, cwd=ws, check=True)


def recipe_agent(ws, name):
    source = (ws / ".agents/agents" / (name + ".md")).read_text(encoding="utf-8")
    write(ws, ".claude/agents/%s.md" % name, source)
    lines = source.split("\n")
    close = lines.index("---", 1)
    description = next(line for line in lines[1:close] if line.startswith("description:"))
    body = "\n".join(lines[close + 1:])
    write(ws, ".opencode/agents/%s.md" % name, "---\n" + description + "\nmode: subagent\n---\n" + body)


def recipe_rule(ws, name):
    source = (ws / ".agents/rules" / (name + ".md")).read_text(encoding="utf-8")
    first = source.split("\n", 1)[0]
    header = "---\ndescription: " + first[len("# "):] + "\nalwaysApply: true\n---\n"
    write(ws, ".cursor/rules/%s.mdc" % name, header + source)


SCREEN_FIELDS = ["key", "route", "kind", "section", "parent", "access", "label", "wave", "story"]


def unquote(value):
    return value[1:-1] if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'" else value


def frontmatter_values(text):
    """Frontmatter values as cell strings: verbatim scalars without surrounding quotes, lists joined with ", ", empty as ""."""
    lines = text.split("\n")
    close = lines.index("---", 1)
    values, last = {}, None
    for line in lines[1:close]:
        if line.startswith("  - "):
            values[last] = (values[last] + ", " if values[last] else "") + unquote(line[len("  - "):].strip())
            continue
        name, _, value = line.partition(":")
        value = value.strip()
        values[name] = "" if value == "[]" else ", ".join(unquote(v.strip()) for v in value[1:-1].split(",")) \
            if value.startswith("[") else unquote(value)
        last = name
    return values


def add_domain(ws, domain):
    template = (ws / ".agents/templates/MAP.md").read_text(encoding="utf-8")
    write(ws, "domains/%s/MAP.md" % domain, template.replace("<domain>", domain))
    write(ws, "domains/%s/map/.gitkeep" % domain, "")


def add_screen(ws, domain, slug, route, parent, wave, transitions):
    rows = "".join("| %s | %s |\n" % t for t in transitions)
    write(ws, "domains/%s/map/%s.md" % (domain, slug),
          "---\nkey: screen:%s/%s\nroute: %s\nkind: place\nsection: Risks\nparent: %s\naccess: %s.read\n"
          "label: %s\nwave: %s\nstory:\n---\n\n## Transitions\n| Action | Target |\n|---|---|\n%s"
          % (domain, slug, route, parent, slug, slug.title(), wave, rows))


def add_stream(ws, domain, stream, stage="goal"):
    text = (ws / ".agents/templates/stream.json").read_text(encoding="utf-8")
    text = text.replace("<domain>/<stream>", "%s/%s" % (domain, stream)).replace('"goal"', '"%s"' % stage)
    write(ws, "domains/%s/streams/%s/stream.json" % (domain, stream), text)


def add_story(ws, domain, stream, slug, wave, scope=(), unmapped=None, depends=(), tracker=""):
    def block(field, keys):
        return field + ":\n" + "".join("  - %s\n" % k for k in keys) if keys else field + ": []\n"

    template = (ws / ".agents/profiles/ui-migration/story.md").read_text(encoding="utf-8")
    body = template[template.index("\n---\n", 4) + len("\n---\n"):]
    head = ("---\nkey: story:%s/%s\ntype: story\nwave: %s\ntracker:%s\n" % (domain, slug, wave, " " + tracker if tracker else "")
            + block("scope", scope) + ("unmapped: %s\n" % unmapped if unmapped else "")
            + block("depends", depends) + "repos: []\ndecisions: []\nmockups: []\n---\n")
    write(ws, "domains/%s/streams/%s/stories/%s/story.md" % (domain, stream, slug), head + body)


def set_screen_story(ws, domain, slug, story_key):
    rel = "domains/%s/map/%s.md" % (domain, slug)
    text = (ws / rel).read_text(encoding="utf-8")
    assert text.count("\nstory:\n") == 1
    write(ws, rel, text.replace("\nstory:\n", "\nstory: %s\n" % story_key))


def _block_bounds(lines, name):
    return lines.index("<!-- map:%s:begin -->" % name), lines.index("<!-- map:%s:end -->" % name)


def _row_file_name(row):
    # A row's element file name comes from its first cell, the key `screen:<domain>/<slug>`.
    return row.split(" | ", 1)[0][len("| "):].split("/", 1)[1] + ".md"


def recipe_map_element(ws, domain, slug):
    """### Recipe: map element in .agents/skills/extend/SKILL.md, step 5."""
    rel = "domains/%s/MAP.md" % domain
    source = (ws / ("domains/%s/map/%s.md" % (domain, slug))).read_text(encoding="utf-8")
    values = frontmatter_values(source)
    new_name = slug + ".md"
    screen_row = "| " + " | ".join(values.get(f, "") for f in SCREEN_FIELDS) + " |"
    table = source.split("## Transitions\n", 1)[1].split("\n")[2:]
    transition_rows = ["| %s | %s |" % (values["key"], " | ".join(c.strip() for c in line.strip("|").split("|")))
                       for line in table if line.startswith("|")]
    headers = {
        "screens": ["| " + " | ".join(SCREEN_FIELDS) + " |", "|" + "---|" * len(SCREEN_FIELDS)],
        "transitions": ["| From | Action | Target |", "|---|---|---|"],
    }
    lines = (ws / rel).read_text(encoding="utf-8").split("\n")
    for name, new_rows in (("screens", [screen_row]), ("transitions", transition_rows)):
        begin, end = _block_bounds(lines, name)
        if end == begin + 1:
            lines[end:end] = headers[name]
            end += 2
        pos = next((i for i in range(begin + 3, end) if _row_file_name(lines[i]) > new_name), end)
        lines[pos:pos] = new_rows
    write(ws, rel, "\n".join(lines))


def recipe_story_cell(ws, domain, element_key, story_key):
    """The MAP.md story cell change of step 14 in .agents/skills/task-new/SKILL.md."""
    rel = "domains/%s/MAP.md" % domain
    lines = (ws / rel).read_text(encoding="utf-8").split("\n")
    begin, end = _block_bounds(lines, "screens")
    column = [c.strip() for c in lines[begin + 1].strip("|").split("|")].index("story")
    row = next(i for i in range(begin + 3, end) if lines[i].startswith("| %s |" % element_key))
    cells = lines[row].split("|")
    assert cells[column + 1] == "  "
    cells[column + 1] = " %s " % story_key
    lines[row] = "|".join(cells)
    write(ws, rel, "\n".join(lines))


def recipe_breakdown_row(ws, domain, stream, slug):
    """## Recipe: BREAKDOWN.md row in .agents/skills/task-new/SKILL.md."""
    values = frontmatter_values(
        (ws / ("domains/%s/streams/%s/stories/%s/story.md" % (domain, stream, slug))).read_text(encoding="utf-8"))
    row = "| story:%s/%s | %s |" % (domain, slug, " | ".join(
        values.get(f, "") for f in ("wave", "scope", "unmapped", "tracker", "depends")))
    rel = "domains/%s/streams/%s/BREAKDOWN.md" % (domain, stream)
    path = ws / rel
    if not path.exists():
        write(ws, rel, "# Breakdown of stream:%s/%s\n\nGenerated by tools/generate.py from stories/*/story.md. "
                       "Do not edit.\n\n| Story | Wave | Scope | Unmapped | Tracker | Depends |\n"
                       "|---|---|---|---|---|---|\n" % (domain, stream))
    lines = path.read_text(encoding="utf-8").split("\n")
    separator = lines.index("|---|---|---|---|---|---|")
    # The skill's order (`-`, digits, letters) equals code point order for slug characters.
    pos = next((i for i in range(separator + 1, len(lines))
                if lines[i].startswith("| story:") and lines[i].split(" | ", 1)[0].split("/", 1)[1] > slug), None)
    if pos is None:
        lines[-1:] = [row, ""]
    else:
        lines.insert(pos, row)
    write(ws, rel, "\n".join(lines))


def _insert_index_line(lines, pos, entry):
    before = lines[pos - 1]
    if before.startswith("  ") and not before.endswith(","):
        lines[pos - 1] = before + ","
    lines.insert(pos, entry + ("," if lines[pos] != "}" else ""))


def recipe_story_index(ws, domain, stream, slug):
    """## Recipe: index entry in .agents/skills/task-new/SKILL.md."""
    rel = ".agents/index.json"
    path = "domains/%s/streams/%s/stories/%s/story.md" % (domain, stream, slug)
    tracker = frontmatter_values((ws / path).read_text(encoding="utf-8")).get("tracker", "")
    key = "story:%s/%s" % (domain, slug)
    line = '  "%s": "%s"' % (key, path)
    text = (ws / rel).read_text(encoding="utf-8")
    if text == "{}\n":
        lines = ["{", line, "}", ""]
    else:
        lines = text.split("\n")
        stories = [i for i, l in enumerate(lines) if l.startswith('  "story:')]
        others = [i for i, l in enumerate(lines) if l.startswith(('  "adr:', '  "diagram:', '  "mockup:'))]
        if stories:
            pos = next((i for i in stories if lines[i][len('  "'):].split('"', 1)[0] > key), stories[-1] + 1)
        elif others:
            pos = others[-1] + 1
        else:
            pos = lines.index("{") + 1
        _insert_index_line(lines, pos, line)
    if tracker:
        escaped = tracker.replace("\\", "\\\\").replace('"', '\\"')
        last_story = max(i for i, l in enumerate(lines) if l.startswith('  "story:'))
        close = lines.index("}")
        trackers = range(last_story + 1, close)
        assert not any(lines[i].startswith('  "%s":' % escaped) for i in trackers)
        pos = next((i for i in trackers if lines[i][len('  "'):].split('"', 1)[0] > escaped), close)
        _insert_index_line(lines, pos, '  "%s": "%s"' % (escaped, path))
    write(ws, rel, "\n".join(lines))


class Recipes(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.recipe = create_workspace(self._tmp.name, "recipe")
        self.generated = create_workspace(self._tmp.name, "generated")
        self.both = (self.recipe, self.generated)

    def generate(self, ws):
        result = run_generate(ws)
        self.assertEqual(result.returncode, 0, result.stderr)

    def assertSameTrees(self):
        self.generate(self.generated)
        left, right = tree_bytes(self.recipe), tree_bytes(self.generated)
        differing = sorted(p for p in set(left) | set(right) if left.get(p) != right.get(p))
        self.assertEqual(differing, [], "paths differ between recipe and generated: %s" % differing)

    def test_repository(self):
        first = {"name": "orders-api", "remote": "git@example.com:t/orders-api.git", "forge": "gitlab",
                 "default_branch": "main", "roles": ["backend"], "summary": "Serves orders"}
        second = {"name": "payments-worker", "remote": "git@example.com:t/payments-worker.git",
                  "forge": "github", "default_branch": "develop", "roles": ["backend", "qa"],
                  "summary": "Consumes payment events and writes postings"}
        for entry in (first, second):
            for ws in self.both:
                add_repository_source(ws, entry)
            recipe_repository(self.recipe, entry)
        self.assertSameTrees()

    def test_adr_into_empty_index(self):
        for ws in self.both:
            write(ws, "docs/adr/0001-use-kafka.md", "# ADR-0001: Use Kafka\n")
        recipe_adr(self.recipe, "0001", "use-kafka")
        self.assertEqual((self.recipe / ".agents/index.json").read_text(encoding="utf-8"),
                         '{\n  "adr:0001": "docs/adr/0001-use-kafka.md"\n}\n')
        self.assertSameTrees()

    def test_adr_after_existing_adr_and_diagram(self):
        for ws in self.both:
            write(ws, "docs/adr/0001-a.md", "# ADR-0001: A\n")
            write(ws, "docs/diagrams/flow.md", "# Flow\n")
            self.generate(ws)
            write(ws, "docs/adr/0002-b.md", "# ADR-0002: B\n")
        recipe_adr(self.recipe, "0002", "b")
        self.assertSameTrees()

    def test_skill(self):
        for ws in self.both:
            write(ws, ".agents/skills/release-notes/SKILL.md",
                  "---\nname: release-notes\ndescription: Writes release notes.\n---\n# Release notes\n")
            write(ws, ".agents/skills/release-notes/examples/a.txt", "example\n")
            (ws / ".agents/skills/release-notes/.DS_Store").write_bytes(b"\x00\x00\x00\x01Bud1")
        recipe_skill(self.recipe, "release-notes")
        self.assertFalse((self.recipe / ".claude/skills/release-notes/.DS_Store").exists())
        self.assertSameTrees()

    def test_agent(self):
        source = ("---\nname: reviewer\ndescription: Reviews diffs: flags risky changes\n---\n"
                  "# Reviewer\nList findings as `path:line message`.\n")
        for ws in self.both:
            write(ws, ".agents/agents/reviewer.md", source)
        recipe_agent(self.recipe, "reviewer")
        self.assertSameTrees()

    def test_rule(self):
        for ws in self.both:
            write(ws, ".agents/rules/sql-style.md", "# SQL style\n\n- Write SQL keywords in upper case.\n")
        recipe_rule(self.recipe, "sql-style")
        self.assertSameTrees()

    def test_map_element_into_empty_map(self):
        for ws in self.both:
            add_domain(ws, "risks")
            add_screen(ws, "risks", "overview", "/risks", "", 1, [("Open alerts", "screen:risks/alerts")])
        recipe_map_element(self.recipe, "risks", "overview")
        self.assertSameTrees()

    def test_map_element_before_existing_with_two_transitions(self):
        for ws in self.both:
            add_domain(ws, "risks")
            add_screen(ws, "risks", "limit", "/risks/limit", "", 1, [("Open card", "screen:risks/limit-card")])
            self.generate(ws)
            # limit-card.md sorts before limit.md ("-" < "."), although its key sorts after.
            add_screen(ws, "risks", "limit-card", "/risks/limit/card", "screen:risks/limit", 2,
                       [("Back", "screen:risks/limit"), ("Show alerts", "screen:risks/alerts")])
        recipe_map_element(self.recipe, "risks", "limit-card")
        self.assertSameTrees()

    def test_story_into_empty_breakdown(self):
        for ws in self.both:
            add_stream(ws, "operations", "migration")
            self.generate(ws)
            add_story(ws, "operations", "migration", "bff-defects", 3, unmapped="BFF returns wrong totals")
        recipe_breakdown_row(self.recipe, "operations", "migration", "bff-defects")
        recipe_story_index(self.recipe, "operations", "migration", "bff-defects")
        self.assertSameTrees()

    def test_story_into_non_empty_breakdown(self):
        for ws in self.both:
            add_stream(ws, "operations", "migration")
            add_story(ws, "operations", "migration", "login", 1, scope=["screen:operations/login"])
            add_story(ws, "operations", "migration", "users", 2,
                      scope=["screen:operations/users", "screen:operations/user-view"],
                      depends=["story:operations/login"])
            self.generate(ws)
            add_story(ws, "operations", "migration", "reports", 2, scope=["screen:operations/reports"],
                      depends=["story:operations/login"])
        recipe_breakdown_row(self.recipe, "operations", "migration", "reports")
        recipe_story_index(self.recipe, "operations", "migration", "reports")
        self.assertSameTrees()

    def test_story_creates_missing_breakdown(self):
        for ws in self.both:
            add_stream(ws, "operations", "migration")
            add_story(ws, "operations", "migration", "login", 1, scope=["screen:operations/login"])
        self.assertFalse((self.recipe / "domains/operations/streams/migration/BREAKDOWN.md").exists())
        recipe_breakdown_row(self.recipe, "operations", "migration", "login")
        recipe_story_index(self.recipe, "operations", "migration", "login")
        self.assertSameTrees()

    def test_story_with_quoted_values(self):
        for ws in self.both:
            add_stream(ws, "operations", "migration")
            self.generate(ws)
            add_story(ws, "operations", "migration", "reports", 2, scope=["screen:operations/reports"],
                      tracker="TASK-12")
            rel = "domains/operations/streams/migration/stories/reports/story.md"
            text = (ws / rel).read_text(encoding="utf-8")
            text = text.replace("wave: 2\n", 'wave: "2"\n').replace("tracker: TASK-12\n", "tracker: 'TASK-12'\n")
            write(ws, rel, text.replace("  - screen:operations/reports\n", '  - "screen:operations/reports"\n'))
        recipe_breakdown_row(self.recipe, "operations", "migration", "reports")
        recipe_story_index(self.recipe, "operations", "migration", "reports")
        self.assertSameTrees()

    def _index_with_adr_and_mockup(self, ws):
        write(ws, "docs/adr/0001-use-kafka.md", "# ADR-0001: Use Kafka\n")
        write(ws, "docs/diagrams/external.json", json.dumps(
            {"diagrams": [{"key": "mockup:operations/login", "url": "https://design.example.org/file/login"}]},
            indent=2) + "\n")

    def test_story_index_entry_without_tracker(self):
        for ws in self.both:
            self._index_with_adr_and_mockup(ws)
            add_stream(ws, "operations", "migration")
            self.generate(ws)
            add_story(ws, "operations", "migration", "reports", 2, scope=["screen:operations/reports"])
        recipe_breakdown_row(self.recipe, "operations", "migration", "reports")
        recipe_story_index(self.recipe, "operations", "migration", "reports")
        self.assertSameTrees()

    def test_story_index_entry_with_tracker(self):
        for ws in self.both:
            self._index_with_adr_and_mockup(ws)
            add_stream(ws, "operations", "migration", stage="delivery")
            add_story(ws, "operations", "migration", "users", 1, scope=["screen:operations/users"], tracker="TASK-9")
            self.generate(ws)
            # TASK-12 sorts before TASK-9 by characters, so both new lines go above the existing ones.
            add_story(ws, "operations", "migration", "reports", 2, scope=["screen:operations/reports"],
                      tracker="TASK-12")
        recipe_breakdown_row(self.recipe, "operations", "migration", "reports")
        recipe_story_index(self.recipe, "operations", "migration", "reports")
        self.assertIn('  "TASK-12": "domains/operations/streams/migration/stories/reports/story.md",\n',
                      (self.recipe / ".agents/index.json").read_text(encoding="utf-8"))
        self.assertSameTrees()

    def test_story_cell_in_map(self):
        for ws in self.both:
            add_domain(ws, "operations")
            add_screen(ws, "operations", "reports", "/reports", "", 2, [])
            add_screen(ws, "operations", "users", "/users", "", 1, [])
            add_stream(ws, "operations", "migration")
            self.generate(ws)
            add_story(ws, "operations", "migration", "reports", 2, scope=["screen:operations/reports"])
            set_screen_story(ws, "operations", "reports", "story:operations/reports")
        recipe_breakdown_row(self.recipe, "operations", "migration", "reports")
        recipe_story_index(self.recipe, "operations", "migration", "reports")
        recipe_story_cell(self.recipe, "operations", "screen:operations/reports", "story:operations/reports")
        self.assertSameTrees()


if __name__ == "__main__":
    unittest.main()
