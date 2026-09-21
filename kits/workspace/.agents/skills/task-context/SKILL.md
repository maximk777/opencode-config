---
name: task-context
description: Use to gather the context of a story key, a task: key or a tracker id - the task with its status, owner and started date, its stream and stage, scope screens with transitions, repositories, decisions, mockups, work record and the sources of its type.
---
# Task context

## Steps
1. Go to the workspace root: the nearest directory, walking up from where you are, where `test -f .agents/kit.json` succeeds. Run every later command in that directory. This skill changes no file. Read `params.language` from `.agents/kit.json`; when it is absent, use `en`. Below it is `<lang>`.
   - A value in `profile.json` is either plain or a language object such as `{"en": "Transitions", "ru": "Переходы"}`. For a language object, take the value of `<lang>`, or the value of `en` when `<lang>` is not in the object.
2. Ask the person for a story key `story:<project>/<domain>/<slug>`, a `task:<slug>` key, or a tracker id, unless they already gave one. Below it is `<input>`.
3. When `<input>` starts with `story:` or `task:`, it is a key; go to step 4. Otherwise it is a tracker id `<ID>`. Check it against `tracker/trackers.json`:
   - Every entry of `trackers` carries `key` and `id_pattern`. JSON doubles every backslash, so `\\d` in the file means `\d`.
   - Rewrite each pattern for `grep -E`: write every `\d` as `[0-9]`, because `grep -E` does not know `\d`.
   - Run `printf '%s\n' '<ID>' | grep -Ex '<rewritten pattern>'` entry by entry until one matches. The `-x` makes the whole id match, not a part of it.
   - When no entry matches, answer `<ID> is not in this workspace` and stop.
4. Read `.agents/index.json`. It is one JSON object that maps keys and tracker ids to paths. Take the value of `<input>`.
   - When there is no value, remember the line `index is stale: <input> is not in .agents/index.json` and go to step 5.
   - When `test -f <value>` fails, remember the line `index is stale: .agents/index.json points <input> to <value>, which does not exist` and go to step 5.
   - For a story or `task:` key, the value is the task file path; go to step 6.
   - For a tracker id, read the frontmatter `tracker` of `<value>` and remove the quotes around it, if any. When it equals `<ID>`, the value is the task file path; go to step 6. Otherwise remember the line `index is stale: .agents/index.json points <input> to <value>, whose tracker is not <input>` and go to step 5.
5. Search the disk, because the index is stale. Add `2>/dev/null` to each command so that a glob with no match prints no error. Empty output, or only an error such as `no matches found` or `No such file or directory`, means nothing was found.
   - For a story key, run `ls projects/<project>/domains/<domain>/streams/*/stories/<slug>/story.md 2>/dev/null`.
   - For a `task:` key, run `test -f tasks/<slug>/task.md`; when it succeeds, the task file is `tasks/<slug>/task.md`, otherwise nothing was found.
   - For a tracker id, run `grep -rlE "^tracker: [\"']?<ID>[\"']?$" projects tasks 2>/dev/null`. Quotes around the value are allowed in frontmatter.
   - When exactly one path is found, that is the task file. Keep the "index is stale" line from step 4 for the report. The fix is `python3 tools/generate.py`; this skill does not run it.
   - When more than one path is found, report all of them, say that the index is stale and the key or id is used by more than one task, and stop.
   - When nothing is found, answer `<input> is not in this workspace` and stop.
6. Read the task file. A story path has the form `projects/<project>/domains/<domain>/streams/<stream>/stories/<slug>/story.md`; take `<project>`, `<domain>`, `<stream>` and `<slug>` from it. A workspace task path is `tasks/<slug>/task.md`. Read its frontmatter: `key`, `type`, `status`, `owner`, `started` and `tracker` for every task; for a story also `wave`, `scope`, `depends`, `repos`, `decisions` and `mockups`. Remove the quotes around `owner`, `started` and `tracker`, if any; use the bare values everywhere below. A list is written either as `key: [a, b]` or as `key:` followed by lines `  - a`; `key: []` and `key:` with nothing after it mean empty. A workspace task has no `wave`, `scope`, `depends`, `repos`, `decisions` or `mockups` unless a person added them; a missing line counts as absent, and the report writes `none` for it.
7. Stream and stage, for a story:
   - Read `projects/<project>/domains/<domain>/streams/<stream>/stream.json`. Take `key`, `profile` and `stage`. When the file is missing, write `stream.json missing` instead of the stage.
   - Find the summary section name: open `.agents/profiles/<profile>/profile.json` and take `story.summary_section`, resolved to `<lang>` as in step 1. When `story.summary_section` is absent, take the first entry of `story.sections`, resolved the same way. This name is `<section>`. For `ui-migration` it is `Goal` in an English workspace and `Цель` in a Russian workspace (`params.language` is `ru`).
   - Read the `## <section>` section of the story and take its first non-empty line. When the section is absent, write `no <section> section`.
   - When `stream.json` is missing or `test -f .agents/profiles/<profile>/profile.json` fails, write `no section name, stream.json missing` or `no section name, unknown profile <profile>` instead of that line.
   For a workspace task there is no stream: write `Stream: none (workspace task)` in the report, and take the goal line from the first non-empty line of its `## Goal` section; when the section is absent, write `no Goal section`.
8. For each key in `scope`, in order; when the task has no `scope` field or an empty one, write `none` under Scope and skip this step:
   - A key has the form `<prefix>:<element project>/<element domain>/<element slug>`.
   - Find the element entry: open `.agents/profiles/<profile>/profile.json` and take the entry of `elements` whose `prefix` equals `<prefix>`. Its `dir` gives the path `projects/<element project>/domains/<element domain>/<dir>/<element slug>.md`, and its `tables` list the tables to copy. Resolve each table's `heading` and `columns` to `<lang>` as in step 1. When the story has no stream (nothing found in step 7), take `<profile>` from no file: treat it as unknown and follow the unknown-entry rule below.
   - When there is no entry, the reason is one of: `stream.json missing` (step 7 found no file), `unknown profile <profile>` (`test -f .agents/profiles/<profile>/profile.json` fails) or `unknown prefix <prefix>` (no entry has that prefix). Then:
     - For `screen:` keys, use the path `projects/<element project>/domains/<element domain>/map/<element slug>.md`. For the table heading and columns, when `.agents/profiles/<profile>/profile.json` exists and has an `elements` entry whose `kind` is `screen`, take that entry's first table's `heading` and `columns`, resolved to `<lang>` as in step 1; otherwise use `Transitions` for the heading and `Action`, `Target` for the columns. For example, in a Russian `ui-migration` workspace this heading is `Переходы`. Mark the key `path by convention: <reason>`.
     - For any other prefix, write `<key>: no path, <reason>` and take the next key. Do not look for its file or its transitions.
   - When `test -f <path>` fails, write `missing: <path>` for this key and take the next key.
   - Read the frontmatter values `kind`, `route` and `label` when present.
   - For each table, for example `Transitions`, find the `## <heading>` section of the file and copy every row of its first table under the resolved `columns`: for `Transitions`, `Action` and `Target` in an English workspace, `Действие` and `Цель` in a Russian workspace. When the section is absent, write `no <heading> section`.
9. For each value in `repos`, remove a leading `repo:`; the rest is `<name>`. Open `repos.json` and find the entry of `repositories` whose `name` equals `<name>`. Take its `status`, `remote` and `default_branch`. A `planned` repository may have no `remote`; write `no remote` then, and `status not set` when `status` is absent. When there is no such entry, write `not in repos.json`. Run `ls -d repos/<name> 2>/dev/null` to say whether a local clone exists; empty output means absent.
10. For each key `adr:<NNNN>` in `decisions`, run `ls docs/adr/<NNNN>-*.md projects/*/adr/<NNNN>-*.md 2>/dev/null`. Read the frontmatter `title` and `status` of each printed file. When more than one file is printed, report every one and say `several ADR files share number <NNNN>`. When nothing is printed, write `missing`.
11. For each key in `mockups`, open `docs/diagrams/external.json` and find the entry of `diagrams` whose `key` equals it. Take its `url`. When there is no such entry, write `not in external.json`.
12. The task folder is the directory holding the task file. Run `test -f <folder>/work.md`. When it succeeds, read its title line and its frontmatter `repos`, `merge_requests`, `commits` and `recorded`. Otherwise write `no work record`.
13. Type sources. Read the `type` of the task and add the sources of its row of this table to the report, one `- ` line each, in the order of the row. Report every source as its path plus `present` or `missing` (`test -f` for a file, `test -d` for a folder), plus the extra detail named below. When a row produces no line at all, write `Type sources: none`.

   | type | sources |
   |---|---|
   | `epic`, `story` | the `epic.md` and the `BREAKDOWN.md` of the task's stream |
   | `task` | `docs/ARCHITECTURE.md` with its `## ` headings; the table of `REPOSITORIES.md` |
   | `bug` | the map file of every `screen:` key named in the task file, resolved as in step 8 |
   | `spike` | `docs/ARCHITECTURE.md` with its `## ` headings; the ADRs of `decisions`, already reported as Decisions |
   | `architecture` | `docs/ARCHITECTURE.md` with its `## ` headings; the `MAP.md` of every touched domain; the affected ADRs |
   | `e2e` | the repository kits of `repos`; the stands; the existing test paths of its repositories |

   - The `epic.md` of a stream is `projects/<project>/domains/<domain>/streams/<stream>/epic.md`; its `BREAKDOWN.md` is `projects/<project>/domains/<domain>/streams/<stream>/BREAKDOWN.md`.
   - The `## ` headings of `docs/ARCHITECTURE.md`: run `grep -E '^## ' docs/ARCHITECTURE.md` and list the heading names on the same line, for example `docs/ARCHITECTURE.md: present (Purpose, Systems, Domains, Decisions, Diagrams)`.
   - Touched domains, for `architecture`: run `grep -oE '[a-z]+:[a-z0-9-]+/[a-z0-9-]+(/[a-z0-9-]+)?' <task file>` and keep every match whose part before the first `:` is `domain`, `stream`, `story`, `mockup` or an element prefix such as `screen`. The touched domain of a key is its first two parts after the colon (`<project>/<domain>`). Deduplicate. Report `projects/<project>/domains/<domain>/MAP.md` for each.
   - Affected ADRs, for `architecture`: the ADRs of `decisions` are already reported as Decisions; add every `adr:` key written in the sections of the task file - run `grep -oE 'adr:[0-9][0-9][0-9][0-9]' <task file>`, deduplicate, and drop the ones already reported - each resolved as in step 10.
   - Repository kits, for `e2e`: for each `repo:<name>` of `repos`, open its entry in `repos.json`. When it has a `kit` entry, report `.agents/repo-kits/<kind>/kit.json` with `present` or `missing`, where `<kind>` is the kit's `kind`. When it has none, write `repo:<name>: no kit`.
   - Stands, for `e2e`: take every `stand:<name>` key written in the task file - run `grep -oE 'stand:[a-z0-9-]+' <task file>` and deduplicate - and report each with `in environments.json` or `not in environments.json`. When the task names none, report every `key` of the `stands` list of `environments.json` instead, or `stands: none` when that list is empty.
   - Existing test paths, for `e2e`: for each `repo:<name>` of `repos` with a local clone `repos/<name>`, run `ls repos/<name>` and keep the entries whose name contains `test` in any case; report each as `repos/<name>/<entry>`. When no entry matches, write `repo:<name>: no test paths at the repository root`; when there is no clone, write `repo:<name>: no clone`.
14. Report in the format below. Name every item by its key and give paths relative to the workspace root. Write only what you read in steps 4 to 13; never guess a value, a path or a stage. Write `none` for an empty or absent list.

## Report format
```
Task: <key> (<task file path>)
Status: <status>; owner: <owner or "none">; started: <started or "none">
Type: <type>; wave: <wave or "none">; depends: <depends joined with ", " or "none">; tracker: <tracker or "no tracker id">
Goal: <first line of the summary section from step 7>
Stream: <stream key> (<stream.json path>), profile <profile>, stage <stage>
Scope:
- <element key> (<element path>): kind <kind>; route <route>; label <label>[; path by convention: <reason>]
  | <column> | <column> | ... |
  |---|---| ... |
  | <cell> | <cell> | ... |
- <element key>: no path, <reason>
Repositories:
- <name>: status <status>, remote <remote or "no remote">, default branch <default_branch>, clone <present or absent>
Decisions:
- <adr key> (<adr path>): <title>, <status>
Mockups:
- <mockup key>: <url>
Work record: <work.md path>, <title>; recorded <recorded>; repos <repos or none>; commits <count>; merge requests <urls or none>
Type sources:
- <one line per source of step 13>
<the "index is stale" line from step 4, when the task was found in step 5>
```

A workspace task reports `Stream: none (workspace task)` instead of the stream line.

Example for `ODARM-145`:
```
Task: story:abs/operations/documents (projects/abs/domains/operations/streams/migration/stories/documents/story.md)
Status: in_progress; owner: maxim; started: 2026-09-14
Type: story; wave: 2; depends: story:abs/operations/login; tracker: ODARM-145
Goal: Operators open and download client documents in the new interface.
Stream: stream:abs/operations/migration (projects/abs/domains/operations/streams/migration/stream.json), profile ui-migration, stage decomposition
Scope:
- screen:abs/operations/documents (projects/abs/domains/operations/map/documents.md): kind place; route /documents; label Documents
  | Action | Target |
  |---|---|
  | Open document | screen:abs/operations/document-view |
  | Back | screen:abs/operations/home |
Repositories:
- docs-bff: status active, remote git@example.org:ops/docs-bff.git, default branch main, clone present
Decisions:
- adr:0007 (docs/adr/0007-document-storage.md): Store documents in object storage, accepted
Mockups:
- mockup:abs/operations/documents: https://design.example.org/file/documents
Work record: no work record
Type sources:
- projects/abs/domains/operations/streams/migration/epic.md: present
- projects/abs/domains/operations/streams/migration/BREAKDOWN.md: present
```

Example for a workspace task of type `architecture`:
```
Task: task:billing-architecture (tasks/billing-architecture/task.md)
Status: waiting; owner: none; started: none
Type: architecture; wave: none; depends: none; tracker: no tracker id
Goal: Split the billing deployment into two services behind one facade.
Stream: none (workspace task)
Scope: none
Repositories: none
Decisions: none
Mockups: none
Work record: no work record
Type sources:
- docs/ARCHITECTURE.md: present (Purpose, Systems, Domains, Decisions, Diagrams)
- projects/billing/domains/payments/MAP.md: present
- adr:0003 (docs/adr/0003-billing-split.md): Split billing into two services, accepted
```

Example for an id nobody uses:
```
ODARM-999 is not in this workspace
```

## Without Python
This skill needs no Python. It only reads files and changes none, so there is nothing to check.
