---
name: task-new
description: Use to create one story in a stream from the stream profile's story template, link it from its scope screens and open a merge request.
---
# Create a story

## Steps
1. Go to the workspace root: the nearest directory, walking up from where you are, where `test -f .agents/kit.json` succeeds. Run every command below from there.
2. Collect these values:
   - `domain`: the domain folder name in `domains/`, for example `operations`.
   - `stream`: the stream folder name in `domains/<domain>/streams/`, for example `migration`.
   - `slug`: the story name, lowercase letters, digits and `-` only (`[a-z0-9-]+`), for example `reports`.
   - scope keys: one or more element keys, for example `screen:operations/reports`. Or, when the story covers no element (for example BFF defects), no keys and a one-line unmapped reason. The reason must not contain `|` and must not start with `[`, `{`, `"` or `'`.
   - `wave`: a number, for example `2`.
   - depends: story keys this story waits for, for example `story:operations/login`, or none.
   - repos: repository keys, for example `repo:reports-bff`, or none.

   Use every value the person gave. Derive the others from the files by the rules below, and do not ask the person to confirm a derived value: the person corrects derived values in the merge request review. Ask the person only for a value that is neither given nor derivable, and wait for the answer. Never invent a value.
   - Stream. When the person named the domain and the stream, use them. Otherwise run `ls domains/*/streams/*/stream.json`; each printed path `domains/<domain>/streams/<stream>/stream.json` is one stream. Keep the streams whose domain folder, stream folder or `key` in `stream.json` the request names. When the request names no stream, keep instead the streams that have an uncovered scope key (see Scope). When exactly one stream is left, take its `<domain>` and `<stream>`. When several or none are left, ask the person for the domain and the stream.
   - Scope. When the person named element keys, use them. When the request asks for the element or elements that have no story yet, read the `scope` list of `domains/<domain>/streams/<stream>/stream.json` and, for each key in it, run `grep -lxF -e '  - <key>' domains/<domain>/streams/<stream>/stories/*/story.md`. The key is uncovered when the command prints no path. The scope keys are the uncovered keys, in the order of the `scope` list. When no key is uncovered, stop, tell the person every scope key of the stream has a story, and change nothing. When the request asks for a story that covers no element, ask the person for the unmapped reason.
   - `wave`. For each scope key, open its element file (step 8 gives the path) and read its `wave:` line. Take the lowest number. Without scope keys, ask the person.
   - `slug`. When the scope has exactly one key, take the text after `/` in that key, for example `card` for `screen:demo/card`; step 7 checks that it is free. Otherwise ask the person.
   - depends and repos: none, unless the person named them.
   - `type`, `tracker`, `decisions` and `mockups` are not asked: step 12 keeps `type`, `decisions` and `mockups` from the template, and `tracker` stays empty unless step 5 needs one.
3. Check the slug: run `printf '%s\n' '<slug>' | grep -Ex '[a-z0-9-]+'`. When it prints nothing, ask the person for another slug.
4. Find the workspace default branch: run `git symbolic-ref --short refs/remotes/origin/HEAD` and remove the `origin/` prefix; when the command fails, use `main`. Call it `<default>`. Then run, one by one:
   - `git switch <default>`
   - `GIT_TERMINAL_PROMPT=0 git pull --ff-only`
   The checks in steps 5 to 9 run after the pull, so they see the fresh default branch.
5. Run `test -f domains/<domain>/streams/<stream>/stream.json`. When it fails, stop, tell the person the stream does not exist, and change nothing. Otherwise read the file and take `profile`, `stage` and the `scope` list.
   - When `stage` is `goal`, `map`, `decomposition` or `ready`: the story gets no tracker id. Go to step 6.
   - When `stage` is `delivery` or `done`: the `ready` stage is closed, so `check` requires a tracker id and an empty `## Open questions` for the new story too. Ask the person for the tracker id `<tracker>` and wait for the answer. When the person gives none, stop, tell them a stream at stage `<stage>` needs a tracker id for every story, and change nothing. Do not create any file or branch.
   - Check `<tracker>`: read `id_pattern` from `tracker/tracker.json` (JSON doubles every backslash, so `\\d` in the file means `\d`), write every `\d` as `[0-9]`, and run `printf '%s\n' '<tracker>' | grep -Ex '<rewritten pattern>'`. When it prints nothing, ask the person for another id. When `tracker/tracker.json` or `id_pattern` is missing, stop, tell the person, and change nothing.
   - When `<tracker>` contains a `"` or a `\` character, ask the person for another id: `.agents/index.json` stores such ids escaped, so the next check cannot find them.
   - Run `grep -F '  "<tracker>":' .agents/index.json`. When it prints a line, the id belongs to another story: ask the person for another id.
6. For each scope key from step 2, check that it is one of the strings in the `scope` list of `stream.json`, exactly. When a key is not in that list, stop, tell the person which key is outside the stream scope, and change nothing. Do not create any file or branch.
   - When step 2 found the scope keys as uncovered keys, run its `grep` again for each of them. When it now prints a path, that story covers the key since the pull: stop, tell the person the path, and change nothing.
7. Run `ls -d domains/<domain>/streams/*/stories/<slug>`. When it prints a path, the slug already exists: stop, tell the person the path, and change nothing. When step 2 derived the slug, ask the person for another slug and continue from step 3 with the answer.
8. For each scope key, find its element file:
   - The key has the form `<prefix>:<element domain>/<element slug>`. Open `.agents/profiles/<profile>/profile.json` and find the entry of `elements` whose `prefix` equals `<prefix>`. Its `dir` gives the path `domains/<element domain>/<dir>/<element slug>.md`. For `screen:operations/reports` in profile `ui-migration` it is `domains/operations/map/reports.md`.
   - Run `test -f <path>`. When it fails, stop, tell the person the element file is missing, and change nothing.
9. Check depends and repos:
   - For each depends key `story:<d>/<s>`, run `ls domains/<d>/streams/*/stories/<s>/story.md`. It must print exactly one path.
   - For each repos key `repo:<name>`, run `grep -F '"name": "<name>"' repos.json`. It must print a line.
   - Correct or drop, together with the person, every key that fails. Never keep a key that does not exist.
10. Run `git switch -c story-<domain>-<slug>`.
11. Run `mkdir -p domains/<domain>/streams/<stream>/stories/<slug> && cp .agents/profiles/<profile>/story.md domains/<domain>/streams/<stream>/stories/<slug>/story.md`.
12. Edit the frontmatter of the new `story.md`. Keep every line of the template in its order and change only these lines:
    - `key: story:<domain>/<slug>`;
    - `wave: <wave>`;
    - `scope`: with keys, the line `scope:` followed by one line `  - <key>` per key (two spaces, `-`, space), in the order of step 2; without keys, the line `scope: []` and directly below it the line `unmapped: <reason>`. Write the `unmapped:` line only when the scope is empty;
    - `depends` and `repos`: the same form, `<field>:` followed by `  - <key>` lines, or `<field>: []` when empty;
    - `tracker`: when step 5 gave a `<tracker>`, `tracker: <tracker>`; otherwise leave `tracker:` empty;
    - leave `type`, `decisions` and `mockups` as the template has them.
    Keep every `## ` heading of the template and replace the placeholder text under each of them. Where the person gave you the words for a section, write those words. Otherwise write:
    - `## Goal`: with scope keys, one line `Deliver <key> (<label>, <route>).`, listing every scope key as `<key> (<label>, <route>)` joined with `, `; without keys, the line `<reason>.`;
    - `## Scope`: with scope keys, one line `<key>: <label>, <route>` per key; without keys, the line `Unmapped: <reason>`;
    - `## Acceptance criteria`, `## Verification` and `## Out of scope`: the one line `Written in the merge request review.`;
    - `## Open questions`: `None.`.
    Take `<label>` and `<route>` from the `label:` and `route:` lines of the element file from step 8. When the element file has no such line or it is empty, leave that part out, for example `<key>` alone. For `screen:demo/card` with label `Card` and route `/card`, `## Scope` gets `screen:demo/card: Card, /card`. When `stage` is `delivery` or `done`, the text under `## Open questions` must be `None.` or nothing: keep `None.` and write no questions there, and tell the person in the report to resolve open questions before merging.

    Example with a scope:
    ```
    ---
    key: story:operations/reports
    type: story
    wave: 2
    tracker:
    scope:
      - screen:operations/reports
    depends:
      - story:operations/login
    repos: []
    decisions: []
    mockups: []
    ---
    ```
    Example without a scope:
    ```
    ---
    key: story:operations/bff-defects
    type: story
    wave: 3
    tracker:
    scope: []
    unmapped: BFF returns wrong totals, no screen changes
    depends: []
    repos:
      - repo:reports-bff
    decisions: []
    mockups: []
    ---
    ```
13. Link the scope elements. For each element file from step 8, find its frontmatter line `story:`.
    - When the line is exactly `story:` (empty), change it to `story: story:<domain>/<slug>`.
    - When the line already names a story, leave it unchanged and tell the person in the report.
    - Change nothing else in the element file.
    Remember the element files you changed.
14. Update the generated files. If `command -v python3` prints a path, run `python3 tools/generate.py`. Otherwise do all three:
    - apply `## Recipe: BREAKDOWN.md row`;
    - apply `## Recipe: index entry`;
    - for each element file you changed in step 13, change one cell in `domains/<element domain>/MAP.md`. Find the begin marker of the element kind (`<!-- map:screens:begin -->` for `screen`) and its end marker. When `MAP.md` or the marker pair is absent, skip this element. Between the markers, the first line is the header, for example `| key | route | kind | section | parent | access | label | wave | story |`; count which column is `story`. Find the row that starts with `| <element key> |`. In that row, replace only the text of the `story` cell: the empty cell `|  |` (two spaces between the bars) becomes `| story:<domain>/<slug> |`. Change nothing else. When there is no such row, do not add one; tell the person the table is stale and needs `python3 tools/generate.py`.

      Row before, in `domains/operations/MAP.md`:
      ```
      | screen:operations/reports | /reports | place | Reports |  | reports.read | Reports | 2 |  |
      ```
      Row after creating `story:operations/reports`:
      ```
      | screen:operations/reports | /reports | place | Reports |  | reports.read | Reports | 2 | story:operations/reports |
      ```
15. Run the check. First run `command -v python3`.
    - When it prints a path (Python is present): run `python3 tools/check.py` at most three times in total. After each run, look only at findings that name a file this skill changed: the new `story.md`, the element files from step 13, `domains/<element domain>/MAP.md`, `domains/<domain>/streams/<stream>/BREAKDOWN.md` and `.agents/index.json`.
      - Fix such a finding only when the fix needs no new value, for example a wrong line format, order or comma, or a stale generated file (run `python3 tools/generate.py`). Then run the check again.
      - When such a finding needs a value only the person has (for example a tracker id, a scope key, or answers to open questions), do not fix it and do not invent the value. Stop: do not commit, list these findings for the person, and wait.
      - When no finding names these files, go on to step 16.
      - When the third run still has findings in these files, stop: do not commit, list the findings for the person, and wait.
      - Findings in other files: do not fix them; list them in the report.
    - When it prints nothing (Python is missing): do not run the check. Remember the line `check not run: python3 missing` for the report.
16. Commit: run `git status --short --untracked-files=all` in the workspace.
    - Stage every path whose status is not `??`: run `git add` for each of them.
    - Stage every `??` path this skill created: the new story folder `domains/<domain>/streams/<stream>/stories/<slug>/`, and `domains/<domain>/streams/<stream>/BREAKDOWN.md` when `## Recipe: BREAKDOWN.md row` created it because it did not exist yet.
    - Stage every other `??` path that is a generated file: its path starts with `.claude/`, `.opencode/` or `.cursor/`, or it is exactly `CLAUDE.md`, `.agents/index.json` or `REPOSITORIES.md`, or it matches `domains/*/streams/*/BREAKDOWN.md`.
    - Do not stage any other `??` path; mention it in the report to the person.
    - Run `git commit -m "docs(story): add <domain>/<slug>"`.
17. Run `GIT_TERMINAL_PROMPT=0 git pull --rebase origin <default>`. On conflicts follow `## Conflicts`. After the rebase has finished, run step 15 again. When step 15 stops, do not amend and do not push; wait for the person. When it made you fix a file, run `git add <file>` for each fixed file, then `git commit --amend --no-edit`.
18. Push and open the merge request by `.agents/rules/merge-requests.md`, with branch `story-<domain>-<slug>` and title `Add story <domain>/<slug>`. Use `GIT_TERMINAL_PROMPT=0` before `git push`.
19. Report to the person:
    - the story file `domains/<domain>/streams/<stream>/stories/<slug>/story.md`, and its tracker id when step 5 gave one;
    - the values step 2 derived, and that the person corrects them and writes the section text in the merge request review;
    - the element files whose `story` you set, and the ones you left because they already named a story;
    - the branch `story-<domain>-<slug>`;
    - the merge request link, or the instruction to open it;
    - the remaining check findings in other files, when there are any;
    - as the last line, the check result, or `check not run: python3 missing`.

## Recipe: BREAKDOWN.md row
Use this only when `python3` is missing. The result equals what `python3 tools/generate.py` writes.

1. Build the row from the frontmatter of the new `story.md`, copying values verbatim (without surrounding quotes):

   `| story:<domain>/<slug> | <wave> | <scope joined with ", "> | <unmapped> | <tracker> | <depends joined with ", "> |`

   An empty value leaves an empty cell with two spaces between the bars: `|  |`. For example scope `[]` with unmapped `BFF defects` and no tracker and no depends gives `| story:operations/bff-defects | 3 |  | BFF defects |  |  |`.
2. Open `domains/<domain>/streams/<stream>/BREAKDOWN.md`. When it does not exist, create it with exactly these six lines, each ending with a newline:
   ```
   # Breakdown of stream:<domain>/<stream>

   Generated by tools/generate.py from stories/*/story.md. Do not edit.

   | Story | Wave | Scope | Unmapped | Tracker | Depends |
   |---|---|---|---|---|---|
   ```
   (The blank lines count: the file starts with the title line, a blank line, the `Generated` line, a blank line, the header line and the separator line.)
3. Rows follow the separator line in ascending slug order. Compare your slug with the slug of each row (the text after `/` in its first cell) character by character from the left; the first different character decides in this order: `-`, then digits `0` to `9`, then letters `a` to `z`. When one slug is the start of the other, the shorter one comes first. So `login` < `reports` < `reports-v2` < `reports2`.
4. Insert your row directly above the first row whose slug comes after yours. When no row comes after yours, add it as the last line of the file. Change nothing else. The file ends with a newline.

Example. `BREAKDOWN.md` before:
```
# Breakdown of stream:operations/migration

Generated by tools/generate.py from stories/*/story.md. Do not edit.

| Story | Wave | Scope | Unmapped | Tracker | Depends |
|---|---|---|---|---|---|
| story:operations/login | 1 | screen:operations/login |  | DEMO-101 |  |
| story:operations/users | 2 | screen:operations/users, screen:operations/user-view |  |  | story:operations/login |
```
After creating `story:operations/reports` with wave `2`, scope `screen:operations/reports`, depends `story:operations/login`:
```
# Breakdown of stream:operations/migration

Generated by tools/generate.py from stories/*/story.md. Do not edit.

| Story | Wave | Scope | Unmapped | Tracker | Depends |
|---|---|---|---|---|---|
| story:operations/login | 1 | screen:operations/login |  | DEMO-101 |  |
| story:operations/reports | 2 | screen:operations/reports |  |  | story:operations/login |
| story:operations/users | 2 | screen:operations/users, screen:operations/user-view |  |  | story:operations/login |
```

## Recipe: index entry
Use this only when `python3` is missing. The result equals what `python3 tools/generate.py` writes.

`.agents/index.json` is one JSON object with one entry per line, two spaces of indentation, in this order: `adr:` entries, then `diagram:` and `mockup:` entries, then `story:` entries ascending by key, then tracker ids ascending by id. A tracker id entry maps the story's `tracker` value to the same `story.md` path.

Ascending means: compare two keys character by character from the left; the first different character decides in this order: `-`, `.`, `/`, digits `0` to `9`, `:`, upper-case letters `A` to `Z`, `_`, lower-case letters `a` to `z`. When one key is the start of the other, the shorter one comes first. So `story:operations/login` < `story:operations/reports`, `story:ops-new/a` < `story:ops/a`, and `DEMO-145` < `DEMO-99` (not number order).

1. Build your story line: `  "story:<domain>/<slug>": "domains/<domain>/streams/<stream>/stories/<slug>/story.md"`.
2. Find its position:
   - When the file has lines starting with `  "story:`, insert your line directly above the first of them whose key comes after yours. When none comes after yours, insert it directly after the last line starting with `  "story:`.
   - When there is no `  "story:` line, insert it directly after the last line starting with `  "adr:`, `  "diagram:` or `  "mockup:`.
   - When there is none of those either, insert it as the first entry, directly after the line `{`.
   - When the whole file is the single line `{}`, replace that line with three lines: `{`, your line, `}`.
3. Only when the story's `tracker` is not empty (step 12 sets it only for a stream at stage `delivery` or `done`): build the line `  "<tracker>": "domains/<domain>/streams/<stream>/stories/<slug>/story.md"`, writing `"` as `\"` and `\` as `\\` inside the id. Tracker lines are the entry lines after the last `  "story:` line. When a line with the same id already exists, add nothing and tell the person the id is used by another story. Otherwise insert your line directly above the first tracker line whose id comes after yours; when none comes after yours, insert it as the last entry, directly above the line `}`.
4. Commas: every entry line ends with `,` except the last entry, directly above `}`. After inserting, add the missing `,` to the line above your line, and end your line with `,` unless it is the last entry.
5. Keep no trailing spaces. The file ends with `}` and a newline. Change nothing else.

Example 1. The index is `{}`. After creating `story:operations/reports` in stream `migration`:
```
{
  "story:operations/reports": "domains/operations/streams/migration/stories/reports/story.md"
}
```

Example 2. Before:
```
{
  "adr:0001": "docs/adr/0001-use-kafka.md",
  "mockup:operations/login": "https://design.example.org/file/login",
  "story:operations/login": "domains/operations/streams/migration/stories/login/story.md",
  "story:operations/users": "domains/operations/streams/migration/stories/users/story.md",
  "DEMO-101": "domains/operations/streams/migration/stories/login/story.md"
}
```
After creating `story:operations/reports` in stream `migration`:
```
{
  "adr:0001": "docs/adr/0001-use-kafka.md",
  "mockup:operations/login": "https://design.example.org/file/login",
  "story:operations/login": "domains/operations/streams/migration/stories/login/story.md",
  "story:operations/reports": "domains/operations/streams/migration/stories/reports/story.md",
  "story:operations/users": "domains/operations/streams/migration/stories/users/story.md",
  "DEMO-101": "domains/operations/streams/migration/stories/login/story.md"
}
```

## Conflicts
For this skill a conflicted file counts as generated when it is `.agents/index.json`, a `BREAKDOWN.md`, or a `MAP.md` whose conflicts all lie between `map:` markers (see step 2). Every other file, including `story.md`, element files and `stream.json`, is not generated.

1. List all conflicted files: `git diff --name-only --diff-filter=U`. Write the list down before you change anything.
2. For each `MAP.md` in the list, run `grep -n -e '^<<<<<<<' -e '^>>>>>>>' -e '<!-- map:' <file>`. The file counts as generated only when every `<<<<<<<` line and the `>>>>>>>` line after it both lie between one `:begin -->` line and the next `:end -->` line. Otherwise it is not generated.
3. First check the whole list for any file that is not generated. If there is one:
   - Run `git rebase --abort`. Do not touch any file first, not even the generated ones.
   - For each file that is not generated, show the person both versions with these labels:
     - "default branch": the output of `git show origin/<default>:<file>`;
     - "your branch": the output of `git show story-<domain>-<slug>:<file>`.
     When one of the two commands fails, tell the person that side has no such file.
   - Stop and wait for the person.
4. Only when every file in the list is generated:
   - For each file in the list, run `git checkout --ours -- <file>`. During a rebase `--ours` is the default branch version, so your own change in that file is gone.
   - Regenerate: if `command -v python3` prints a path, run `python3 tools/generate.py`. Otherwise apply again, to the files in the list, what step 14 does: `## Recipe: BREAKDOWN.md row`, `## Recipe: index entry` and the `story` cell change in `MAP.md`.
   - For each file in the list, run `git add <file>`. Also `git add` any other generated file the regeneration changed.
   - Run `GIT_EDITOR=true git rebase --continue`. When it stops on conflicts again, go back to step 1.

## Without Python
1. In step 14, apply `## Recipe: BREAKDOWN.md row`, `## Recipe: index entry` and the `MAP.md` cell change instead of `python3 tools/generate.py`.
2. Skip `python3 tools/generate.py` and `python3 tools/check.py` everywhere, including `## Conflicts`.
3. End the report with the line:

check not run: python3 missing
