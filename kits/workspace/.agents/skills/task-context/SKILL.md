---
name: task-context
description: Use to gather the context of a story key or a tracker id - its story, stream stage, scope screens, repositories, decisions, mockups and work records.
---
# Task context

## Steps
1. Go to the workspace root: the nearest directory, walking up from where you are, where `test -f .agents/kit.json` succeeds. Run every later command in that directory. This skill changes no file.
2. Ask the person for a story key or a tracker id, unless they already gave one. Below it is `<input>`.
3. When `<input>` starts with `story:`, it is a story key of the form `story:<domain>/<slug>`; go to step 4. Otherwise it is a tracker id `<ID>`. Check it:
   - Read `id_pattern` from `tracker/tracker.json`. JSON doubles every backslash, so `\\d` in the file means `\d`.
   - Rewrite the pattern for `grep -E`: write every `\d` as `[0-9]`, because `grep -E` does not know `\d`.
   - Run `printf '%s\n' '<ID>' | grep -Ex '<rewritten pattern>'`. The `-x` makes the whole id match, not a part of it.
   - If it prints nothing, answer `<ID> is not in this workspace` and stop.
4. Read `.agents/index.json`. It is one JSON object that maps keys and tracker ids to paths. Take the value of `<input>`.
   - When there is no value, remember the line `index is stale: <input> is not in .agents/index.json` and go to step 5.
   - When `test -f <value>` fails, remember the line `index is stale: .agents/index.json points <input> to <value>, which does not exist` and go to step 5.
   - For a story key, the value is the story path; go to step 6.
   - For a tracker id, read the frontmatter `tracker` of `<value>` and remove the quotes around it, if any. When it equals `<ID>`, the value is the story path; go to step 6. Otherwise remember the line `index is stale: .agents/index.json points <input> to <value>, whose tracker is not <input>` and go to step 5.
5. Search the disk, because the index is stale. Add `2>/dev/null` to each command so that a glob with no match prints no error. Empty output, or only an error such as `no matches found` or `No such file or directory`, means nothing was found.
   - For a story key, run `ls domains/<domain>/streams/*/stories/<slug>/story.md 2>/dev/null`.
   - For a tracker id, run `grep -lE "^tracker: [\"']?<ID>[\"']?$" domains/*/streams/*/stories/*/story.md 2>/dev/null`. Quotes around the value are allowed in frontmatter.
   - When exactly one path is printed, that is the story path. Keep the "index is stale" line from step 4 for the report. The fix is `python3 tools/generate.py`; this skill does not run it.
   - When more than one path is printed, report all of them, say that the index is stale and the id is used by more than one story, and stop.
   - When nothing is found, answer `<input> is not in this workspace` and stop.
6. Read the story file. The story path has the form `domains/<domain>/streams/<stream>/stories/<slug>/story.md`; take `<domain>`, `<stream>` and `<slug>` from it. The story key is `story:<domain>/<slug>`. Read its frontmatter: `type`, `wave`, `tracker`, `scope`, `depends`, `repos`, `decisions`, `mockups`. Remove the quotes around `tracker`, if any; use this bare value everywhere below. A list is written either as `key: [a, b]` or as `key:` followed by lines `  - a`; `key: []` and `key:` with nothing after it mean empty. Read the `## Goal` section.
7. Read `domains/<domain>/streams/<stream>/stream.json`. Take `key`, `profile` and `stage`. When the file is missing, write `stream.json missing` instead of the stage.
8. For each key in `scope`, in order:
   - A key has the form `<prefix>:<element domain>/<element slug>`.
   - Find the element entry: open `.agents/profiles/<profile>/profile.json` and take the entry of `elements` whose `prefix` equals `<prefix>`. Its `dir` gives the path `domains/<element domain>/<dir>/<element slug>.md`, and its `tables` list the tables to copy.
   - When there is no entry, the reason is one of: `stream.json missing` (step 7 found no file), `unknown profile <profile>` (`test -f .agents/profiles/<profile>/profile.json` fails) or `unknown prefix <prefix>` (no entry has that prefix). Then:
     - For `screen:` keys, use the path `domains/<element domain>/map/<element slug>.md` and the table `Transitions`, and mark the key `path by convention: <reason>`.
     - For any other prefix, write `<key>: no path, <reason>` and take the next key. Do not look for its file or its transitions.
   - When `test -f <path>` fails, write `missing: <path>` for this key and take the next key.
   - Read the frontmatter values `kind`, `route` and `label` when present.
   - For each table, for example `Transitions`, find the `## <heading>` section of the file and copy every row of its first table: for `Transitions`, `Action` and `Target`. When the section is absent, write `no <heading> section`.
9. For each value in `repos`, remove a leading `repo:`; the rest is `<name>`. Open `repos.json` and find the entry of `repositories` whose `name` equals `<name>`. Take its `status`, `remote` and `default_branch`. A `planned` repository may have no `remote`; write `no remote` then, and `status not set` when `status` is absent. When there is no such entry, write `not in repos.json`. Run `ls -d repos/<name> 2>/dev/null` to say whether a local clone exists; empty output means absent.
10. For each key `adr:<NNNN>` in `decisions`, run `ls docs/adr/<NNNN>-*.md 2>/dev/null`. Read the frontmatter `title` and `status` of each printed file. When more than one file is printed, report every one and say `several ADR files share number <NNNN>`. When nothing is printed, write `missing`.
11. For each key in `mockups`, open `docs/diagrams/external.json` and find the entry of `diagrams` whose `key` equals it. Take its `url`. When there is no such entry, write `not in external.json`.
12. When `tracker` is not empty, run `test -f work/<tracker>/record.md`. When it succeeds, read its title line and its frontmatter `repos`, `merge_requests` and `commits`. Otherwise write `no work record`. When `tracker` is empty, write `no tracker id`.
13. Report in the format below. Name every item by its key and give paths relative to the workspace root. Write only what you read in steps 4 to 12; never guess a value, a path or a stage. Write `none` for an empty list.

## Report format
```
Story: <story key> (<story path>)
Tracker: <tracker without quotes, or "no tracker id">
Type: <type>; wave: <wave>; depends: <depends joined with ", " or "none">
Goal: <first line of the Goal section>
Stream: <stream key> (<stream.json path>), profile <profile>, stage <stage>
Scope:
- <element key> (<element path>): kind <kind>; route <route>; label <label>[; path by convention: <reason>]
  | Action | Target |
  |---|---|
  | <action> | <target> |
- <element key>: no path, <reason>
Repositories:
- <name>: status <status>, remote <remote or "no remote">, default branch <default_branch>, clone <present or absent>
Decisions:
- <adr key> (<adr path>): <title>, <status>
Mockups:
- <mockup key>: <url>
Work record: <record path>, <title>; repos <repos or none>; commits <count>; merge requests <urls or none>
<the "index is stale" line from step 4, when the story was found in step 5>
```

Example for `DEMO-145`:
```
Story: story:operations/documents (domains/operations/streams/migration/stories/documents/story.md)
Tracker: DEMO-145
Type: story; wave: 2; depends: story:operations/login
Goal: Operators open and download client documents in the new interface.
Stream: stream:operations/migration (domains/operations/streams/migration/stream.json), profile ui-migration, stage decomposition
Scope:
- screen:operations/documents (domains/operations/map/documents.md): kind place; route /documents; label Documents
  | Action | Target |
  |---|---|
  | Open document | screen:operations/document-view |
  | Back | screen:operations/home |
Repositories:
- docs-bff: status active, remote git@example.org:ops/docs-bff.git, default branch main, clone present
Decisions:
- adr:0007 (docs/adr/0007-document-storage.md): Store documents in object storage, accepted
Mockups:
- mockup:operations/documents: https://design.example.org/file/documents
Work record: no work record
```

Example for an id nobody uses:
```
DEMO-999 is not in this workspace
```

## Without Python
This skill needs no Python. It only reads files and changes none, so there is nothing to check.
