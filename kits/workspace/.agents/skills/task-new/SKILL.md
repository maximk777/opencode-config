---
name: task-new
description: Use to create one story in a stream of a project from the stream profile's story template - link it from its scope screens, update the generated files and open a merge request - or one projectless workspace task in tasks/.
---
# Create a story or a workspace task

## Steps
1. Go to the workspace root: the nearest directory, walking up from where you are, where `test -f .agents/kit.json` succeeds. Run every command below from there.
2. Ask the person which kind to create, unless they already said it:
   - a story in a stream of a project: go to step 3;
   - a projectless workspace task in `tasks/`: go to step 21.
   The types `epic` and `story` belong to a stream: create them only through the story flow. The task flow offers `task`, `bug`, `spike`, `architecture` and `e2e` only.

## Story flow
3. Collect these values:
   - `project`: the project folder name in `projects/`, for example `abs`.
   - `domain`: the domain folder name in `projects/<project>/domains/`, for example `operations`.
   - `stream`: the stream folder name in `projects/<project>/domains/<domain>/streams/`, for example `migration`.
   - `slug`: the story name, lowercase letters, digits and `-` only (`[a-z0-9-]+`), for example `reports`.
   - scope keys: one or more element keys of the form `<prefix>:<project>/<domain>/<slug>`, for example `screen:abs/operations/reports`. Or, when the story covers no element (for example BFF defects), no keys and a one-line unmapped reason. The reason must not contain `|` and must not start with `[`, `{`, `"` or `'`.
   - `wave`: a number, for example `2`.
   - depends: story keys this story waits for, for example `story:abs/operations/login`, or none.
   - repos: repository keys, for example `repo:reports-bff`, or none.
   - `title`: the story title for the `# ` title line of the story template, for example `Reports`. Only needed when the template has such a line (step 6 chooses the template), for example `# [СО] <Название стори>` in `story.ru.md`.

   Use every value the person gave. Derive the others from the files by the rules below, and do not ask the person to confirm a derived value: the person corrects derived values in the merge request review. Ask the person only for a value that is neither given nor derivable, and wait for the answer. Never invent a value.
   - Stream. When the person named the project, the domain and the stream, use them. Otherwise run `ls projects/*/domains/*/streams/*/stream.json`; each printed path `projects/<project>/domains/<domain>/streams/<stream>/stream.json` is one stream. Keep the streams whose project folder, domain folder, stream folder or `key` in `stream.json` the request names. When the request names no stream, keep instead the streams that have an uncovered scope key (see Scope). When exactly one stream is left, take its `<project>`, `<domain>` and `<stream>`. When several or none are left, ask the person for the project, the domain and the stream.
   - Scope. When the person named element keys, use them. When the request asks for the element or elements that have no story yet, read the `scope` list of `projects/<project>/domains/<domain>/streams/<stream>/stream.json` and, for each key in it, run `grep -lxF -e '  - <key>' projects/<project>/domains/<domain>/streams/<stream>/stories/*/story.md 2>/dev/null`. The key is uncovered when the command prints no path. The scope keys are the uncovered keys, in the order of the `scope` list. When no key is uncovered, stop, tell the person every scope key of the stream has a story, and change nothing. When the request asks for a story that covers no element, ask the person for the unmapped reason.
   - `wave`. For each scope key, open its element file (step 9 gives the path) and read its `wave:` line. Take the lowest number. Without scope keys, ask the person.
   - `slug`. When the scope has exactly one key, take the text after the last `/` in that key, for example `card` for `screen:abs/demo/card`; step 8 checks that it is free. Otherwise ask the person.
   - depends and repos: none, unless the person named them.
   - `title`. When the person gave a title, use it. Otherwise, when the scope has exactly one key, take the `label:` value of its element file (step 9 gives the path). Otherwise (several keys, no keys, or an empty `label:`) ask the person for the title. Never invent a title.
   - `type`, `tracker`, `decisions` and `mockups` are not asked: step 13 keeps `type`, `decisions` and `mockups` from the template, keeps `status`, `owner` and `started` as the template has them, and `tracker` stays empty unless step 6 needs one.
4. Check the slug: run `printf '%s\n' '<slug>' | grep -Ex '[a-z0-9-]+'`. When it prints nothing, ask the person for another slug.
5. Find the workspace default branch: run `git symbolic-ref --short refs/remotes/origin/HEAD` and remove the `origin/` prefix; when the command fails, use `main`. Call it `<default>`. Then run, one by one:
   - `git switch <default>`
   - `GIT_TERMINAL_PROMPT=0 git pull --ff-only`
   The checks in steps 6 to 10 run after the pull, so they see the fresh default branch.
6. Run `test -f projects/<project>/domains/<domain>/streams/<stream>/stream.json`. When it fails, stop, tell the person the stream does not exist, and change nothing. Otherwise read the file and take `profile`, `stage` and the `scope` list.
   - Find the workspace language `<language>`: open `.agents/kit.json` and read `params.language`. When the file, `params` or `language` is missing, `<language>` is `en`.
   - Find the story template `<template>`: when `<language>` is not `en` and `test -f .agents/profiles/<profile>/story.<language>.md` succeeds, it is `.agents/profiles/<profile>/story.<language>.md`; otherwise `.agents/profiles/<profile>/story.md`. For language `ru` in profile `ui-migration` it is `story.ru.md`.
   - Values in `.agents/profiles/<profile>/profile.json` may be language objects such as `{"en": "Open questions", "ru": "Открытые вопросы"}`. Wherever this skill reads a value from `profile.json`, take the `<language>` value of such an object, or its `en` value when it has no `<language>` key.
   - Find the open questions section `<open questions>`: the `section` of the gate `"gate": "no_open_questions"` in `stages` of `profile.json`, for example `Open questions` (en) or `Открытые вопросы` (ru). When no such gate exists, there is no open questions section.
   - When `stage` is `goal`, `map`, `decomposition` or `ready`: the story gets no tracker id. Go to step 7.
   - When `stage` is `delivery` or `done`: the `ready` stage is closed, so its `tracker_ids` gate requires a tracker id for the new story too. Ask the person for the tracker id `<tracker>` and wait for the answer. When the person gives none, stop, tell them a stream at stage `<stage>` needs a tracker id for every story, and change nothing. Do not create any file or branch.
   - Check `<tracker>`: read `tracker/trackers.json`. Every entry of `trackers` carries `key` and `id_pattern`; JSON doubles every backslash, so `\\d` in the file means `\d`. Rewrite each pattern for `grep -E` (write every `\d` as `[0-9]`) and run `printf '%s\n' '<tracker>' | grep -Ex '<rewritten pattern>'` entry by entry until one matches. When no entry matches, ask the person for another id. When `tracker/trackers.json` has no `trackers` list, or no entry has an `id_pattern`, stop, tell the person, and change nothing.
   - When `<tracker>` contains a `"` or a `\` character, ask the person for another id: `.agents/index.json` stores such ids escaped, so the next check cannot find them.
   - Run `grep -F '  "<tracker>":' .agents/index.json 2>/dev/null`. When it prints a line, the id belongs to another task: ask the person for another id.
7. For each scope key from step 3, check that it is one of the strings in the `scope` list of `stream.json`, exactly. When a key is not in that list, stop, tell the person which key is outside the stream scope, and change nothing. Do not create any file or branch.
   - When step 3 found the scope keys as uncovered keys, run its `grep` again for each of them. When it now prints a path, that story covers the key since the pull: stop, tell the person the path, and change nothing.
8. Run `ls -d projects/<project>/domains/<domain>/streams/*/stories/<slug>`. When it prints a path, the slug already exists: stop, tell the person the path, and change nothing. When step 3 derived the slug, ask the person for another slug and continue from step 4 with the answer.
9. For each scope key, find its element file:
   - The key has the form `<prefix>:<element project>/<element domain>/<element slug>`. Open `.agents/profiles/<profile>/profile.json` and find the entry of `elements` whose `prefix` equals `<prefix>`. Its `dir` gives the path `projects/<element project>/domains/<element domain>/<dir>/<element slug>.md`. For `screen:abs/operations/reports` in profile `ui-migration` it is `projects/abs/domains/operations/map/reports.md`.
   - Run `test -f <path>`. When it fails, stop, tell the person the element file is missing, and change nothing.
10. Check depends and repos:
    - For each depends key `story:<d>/<dd>/<s>`, run `ls projects/<d>/domains/<dd>/streams/*/stories/<s>/story.md 2>/dev/null`. It must print exactly one path.
    - For each repos key `repo:<name>`, run `grep -F '"name": "<name>"' repos.json`. It must print a line.
    - Correct or drop, together with the person, every key that fails. Never keep a key that does not exist.
11. Run `git switch -c story-<domain>-<slug>`.
12. Run `mkdir -p projects/<project>/domains/<domain>/streams/<stream>/stories/<slug> && cp <template> projects/<project>/domains/<domain>/streams/<stream>/stories/<slug>/story.md`.
13. Edit the frontmatter of the new `story.md`. Keep every line of the template in its order and change only these lines:
    - `key: story:<project>/<domain>/<slug>`;
    - keep `status: waiting` and the empty `owner:` and `started:` lines exactly as the template has them: a new story waits, unowned and not started - `task-start` writes those three lines later;
    - `wave: <wave>`;
    - `scope`: with keys, the line `scope:` followed by one line `  - <key>` per key (two spaces, `-`, space), in the order of step 3; without keys, the line `scope: []` and directly below it the line `unmapped: <reason>`. The `unmapped:` line is the only line the template does not have; write it only when the scope is empty;
    - `depends` and `repos`: the same form, `<field>:` followed by `  - <key>` lines, or `<field>: []` when empty;
    - `tracker`: when step 6 gave a `<tracker>`, `tracker: <tracker>`; otherwise leave `tracker:` empty;
    - leave `type`, `decisions` and `mockups` as the template has them.
    Keep every `## ` heading of the template and replace the placeholder text under each of them. The sections are those of `<template>`, in their order; their names are the `story.sections` list of `profile.json`. When the template has a `# ` title line, replace its placeholder in angle brackets with `<title>` from step 3 and keep the rest of the line: `# [СО] <Название стори>` becomes `# [СО] Отчёты` for title `Отчёты`. Where the person gave you the words for a section, write those words. Otherwise write:
    - the summary section: the section named by `story.summary_section` of `profile.json` (in `<language>` as step 6 says), or the first item of `story.sections` when `summary_section` is absent. It gets the goal. With scope keys, one line `Deliver <key> (<label>, <route>).`, listing every scope key as `<key> (<label>, <route>)` joined with `, `; without keys, the line `<reason>.`;
    - the section whose template text names the covered screens (it mentions `screen:` keys or the `scope` field): with scope keys, one line `<key>: <label>, <route>` per key; without keys, the line `Unmapped: <reason>`;
    - `## <open questions>`: `None.`;
    - every other section: the one line `Written in the merge request review.`.
    Take `<label>` and `<route>` from the `label:` and `route:` lines of the element file from step 9. When the element file has no such line or it is empty, leave that part out, for example `<key>` alone. For `screen:abs/demo/card` with label `Card` and route `/card`, the screens section gets `screen:abs/demo/card: Card, /card`. When `stage` is `delivery` or `done`, the text under `## <open questions>` must be `None.` or nothing: keep `None.` and write no questions there, and tell the person in the report to resolve open questions before merging.

    Sections without text from the person, for scope `screen:abs/demo/card` with label `Card` and route `/card`:

    | English (`story.md`) | Russian (`story.ru.md`) | Text |
    |---|---|---|
    | no title line | `# [СО] <Название стори>` | the title: `# [СО] Card` |
    | `## Goal` (summary section) | `## Цель` (summary section) | `Deliver screen:abs/demo/card (Card, /card).` |
    | `## Scope` | `## Функциональные требования` | `screen:abs/demo/card: Card, /card` |
    | `## Acceptance criteria`, `## Verification`, `## Out of scope` | `## Заинтересованные стороны`, `## Описание бизнес-потребности`, `## Нефункциональные требования`, `## Задачи внутри стори`, `## Этапы` | `Written in the merge request review.` |
    | `## Open questions` | `## Открытые вопросы` | `None.` |

    Example with a scope:
    ```
    ---
    key: story:abs/operations/reports
    type: story
    status: waiting
    owner:
    started:
    wave: 2
    tracker:
    scope:
      - screen:abs/operations/reports
    depends:
      - story:abs/operations/login
    repos: []
    decisions: []
    mockups: []
    ---
    ```
    Example without a scope:
    ```
    ---
    key: story:abs/operations/bff-defects
    type: story
    status: waiting
    owner:
    started:
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
14. Link the scope elements. For each element file from step 9, find its frontmatter line `story:`.
    - When the line is exactly `story:` (empty), change it to `story: story:<project>/<domain>/<slug>`.
    - When the line already names a story, leave it unchanged and tell the person in the report.
    - Change nothing else in the element file.
    Remember the element files you changed.
15. Update the generated files. If `command -v python3` prints a path, run `python3 tools/generate.py`. It rewrites the stream's `BREAKDOWN.md`, the story cells of the domain `MAP.md` files, `.agents/index.json` and `STATUS.md`. Otherwise do all three:
    - apply `## Recipe: BREAKDOWN.md row`;
    - apply `## Recipe: index entry`;
    - for each element file you changed in step 14, change one cell in `projects/<element project>/domains/<element domain>/MAP.md`. Find the begin marker of the element kind (`<!-- map:screens:begin -->` for `screen`) and its end marker. When `MAP.md` or the marker pair is absent, skip this element. Between the markers, the first line is the header, for example `| key | route | kind | section | parent | access | label | wave | story |`; count which column is `story`. Find the row that starts with `| <element key> |`. In that row, replace only the text of the `story` cell: the empty cell `|  |` (two spaces between the bars) becomes `| story:<project>/<domain>/<slug> |`. Change nothing else. When there is no such row, do not add one; tell the person the table is stale and needs `python3 tools/generate.py`.

      Row before, in `projects/abs/domains/operations/MAP.md`:
      ```
      | screen:abs/operations/reports | /reports | place | Reports |  | reports.read | Reports | 2 |  |
      ```
      Row after creating `story:abs/operations/reports`:
      ```
      | screen:abs/operations/reports | /reports | place | Reports |  | reports.read | Reports | 2 | story:abs/operations/reports |
      ```
16. Run the check. First run `command -v python3`.
    - When it prints a path (Python is present): run `python3 tools/check.py` at most three times in total. After each run, look only at findings that name a file this skill changed: the new `story.md`, the element files from step 14, `projects/<element project>/domains/<element domain>/MAP.md`, `projects/<project>/domains/<domain>/streams/<stream>/BREAKDOWN.md`, `.agents/index.json` and `STATUS.md`.
      - Fix such a finding only when the fix needs no new value, for example a wrong line format, order or comma, or a stale generated file (run `python3 tools/generate.py`). Then run the check again.
      - When such a finding needs a value only the person has (for example a tracker id, a scope key, or answers to open questions), do not fix it and do not invent the value. Stop: do not commit, list these findings for the person, and wait.
      - When no finding names these files, go on to step 17.
      - When the third run still has findings in these files, stop: do not commit, list the findings for the person, and wait.
      - Findings in other files: do not fix them; list them in the report.
    - When it prints nothing (Python is missing): do not run the check. Remember the line `check not run: python3 missing` for the report.
17. Commit: run `git status --short --untracked-files=all` in the workspace.
    - Stage every path whose status is not `??`: run `git add` for each of them.
    - Stage every `??` path this skill created: the new story folder `projects/<project>/domains/<domain>/streams/<stream>/stories/<slug>/`, and `projects/<project>/domains/<domain>/streams/<stream>/BREAKDOWN.md` when `## Recipe: BREAKDOWN.md row` created it because it did not exist yet.
    - Stage every other `??` path that is a generated file: its path starts with `.claude/`, `.opencode/` or `.cursor/`, or it is exactly `CLAUDE.md`, `.agents/index.json`, `REPOSITORIES.md` or `STATUS.md`, or it matches `projects/*/domains/*/streams/*/BREAKDOWN.md`.
    - Do not stage any other `??` path; mention it in the report to the person.
    - Run `git commit -m "docs(story): add <project>/<domain>/<slug>"`.
18. Run `GIT_TERMINAL_PROMPT=0 git pull --rebase origin <default>`. On conflicts follow `## Conflicts`. After the rebase has finished, run step 16 again. When step 16 stops, do not amend and do not push; wait for the person. When it made you fix a file, run `git add <file>` for each fixed file, then `git commit --amend --no-edit`.
19. Push and open the merge request by `.agents/rules/merge-requests.md`, with branch `story-<domain>-<slug>` and title `Add story <project>/<domain>/<slug>`. Use `GIT_TERMINAL_PROMPT=0` before `git push`.
20. Report to the person:
    - the story file `projects/<project>/domains/<domain>/streams/<stream>/stories/<slug>/story.md`, and its tracker id when step 6 gave one;
    - the values step 3 derived, and that the person corrects them and writes the section text in the merge request review;
    - the element files whose `story` you set, and the ones you left because they already named a story;
    - the branch `story-<domain>-<slug>`;
    - the merge request link, or the instruction to open it;
    - the remaining check findings in other files, when there are any;
    - as the last line, the check result, or `check not run: python3 missing`.

## Workspace task flow
21. Collect these values:
    - `slug`: the task name, lowercase letters, digits and `-` only (`[a-z0-9-]+`), for example `billing-architecture`. It is the last part of the key `task:<slug>`.
    - `type`: ask the person to choose one of `task`, `bug`, `spike`, `architecture`, `e2e`. When they name `epic` or `story`, tell them these types live in a stream and offer the story flow (step 3) instead.
    - `tracker`: optional. When the person gives none, the `tracker:` line stays empty. When they give one, check it the way step 6 does: pattern entry by entry, then the `"` and `\` rule, then the duplicate check in `.agents/index.json`. Every failed check asks the person for another id or for none.
    - a one-line summary for the title, for example `Split billing into two services`.
22. Check the slug: `printf '%s\n' '<slug>' | grep -Ex '[a-z0-9-]+'` must print the slug, and `test -e tasks/<slug>` must fail. When the folder already exists, stop, tell the person `tasks/<slug>/` already exists, and change nothing. When the slug has another form, ask for another slug.
23. Find the workspace default branch as step 5 does, then run `git switch <default>` and `GIT_TERMINAL_PROMPT=0 git pull --ff-only`.
24. Run `git switch -c task-<slug>`.
25. Run `mkdir -p tasks/<slug> && cp .agents/templates/task.md tasks/<slug>/task.md`.
26. Edit the new `task.md`. Keep every line of the template in its order and change only these lines:
    - `key: task:<slug>`;
    - `type: <type>` from step 21;
    - keep `status: waiting` and the empty `owner:` and `started:` lines exactly as the template has them: a new task waits, unowned and not started - `task-start` writes those three lines later;
    - `tracker: <tracker>` when step 21 gave one; otherwise leave `tracker:` empty.
    Replace the title line `# <slug>: <one-line summary>` with the slug and the summary of step 21. Keep every `## ` heading. Where the person gave you the words for a section, write those words under it; otherwise keep the template text under that heading and say in the report that the person fills the sections before starting the task.
27. Update the generated files. If `command -v python3` prints a path, run `python3 tools/generate.py`. It rewrites `.agents/index.json` (the `task:<slug>` entry, and the tracker alias when one was set) and `STATUS.md` (the row in the `workspace` group of the waiting section). Otherwise apply `## Recipe: index entry` for `task:<slug>`.
28. Run the check as step 16 does, at most three times in total, looking only at findings that name `tasks/<slug>/task.md`, `.agents/index.json` or `STATUS.md`, with the same fix, stop and report rules.
29. Commit as step 17 does, with these differences: the created folder is `tasks/<slug>/`; no `BREAKDOWN.md` is created; the commit message is `git commit -m "docs(task): add <slug>"`.
30. Run `GIT_TERMINAL_PROMPT=0 git pull --rebase origin <default>`. On conflicts follow `## Conflicts`. After the rebase has finished, run step 28 again. When step 28 stops, do not amend and do not push; wait for the person. When it made you fix a file, run `git add <file>` for each fixed file, then `git commit --amend --no-edit`.
31. Push and open the merge request by `.agents/rules/merge-requests.md`, with branch `task-<slug>` and title `Add task <slug>`. Use `GIT_TERMINAL_PROMPT=0` before `git push`.
32. Report to the person:
    - the task file `tasks/<slug>/task.md`, and its tracker id when step 21 gave one;
    - that the person fills the sections that still carry the template text before starting the task;
    - the branch `task-<slug>`;
    - the merge request link, or the instruction to open it;
    - the remaining check findings in other files, when there are any;
    - as the last line, the check result, or `check not run: python3 missing`.

## Recipe: BREAKDOWN.md row
Use this only when `python3` is missing. The result equals what `python3 tools/generate.py` writes.

1. Build the row from the frontmatter of the new `story.md`, copying values verbatim (without surrounding quotes):

   `| story:<project>/<domain>/<slug> | <wave> | <scope joined with ", "> | <unmapped> | <tracker> | <depends joined with ", "> |`

   An empty value leaves an empty cell with two spaces between the bars: `|  |`. For example scope `[]` with unmapped `BFF defects` and no tracker and no depends gives `| story:abs/operations/bff-defects | 3 |  | BFF defects |  |  |`.
2. Open `projects/<project>/domains/<domain>/streams/<stream>/BREAKDOWN.md`. When it does not exist, create it with exactly these six lines, each ending with a newline:
   ```
   # <title> stream:<project>/<domain>/<stream>

   <note>

   | <column 1> | <column 2> | <column 3> | <column 4> | <column 5> | <column 6> |
   |---|---|---|---|---|---|
   ```
   Take `<title>`, `<note>` and the six columns from the `breakdown` block of `.agents/profiles/<profile>/profile.json` (`title`, `note` and `columns` in their order), in `<language>` as step 6 says. When `profile.json` has no `breakdown` block, use title `Breakdown of`, note `Generated by tools/generate.py from stories/*/story.md. Do not edit.` and columns `Story`, `Wave`, `Scope`, `Unmapped`, `Tracker`, `Depends`. The row cells keep the order of step 1 whatever the column names are.

   English (`en`, and every profile without a `breakdown` block):
   ```
   # Breakdown of stream:demo/operations/migration

   Generated by tools/generate.py from stories/*/story.md. Do not edit.

   | Story | Wave | Scope | Unmapped | Tracker | Depends |
   |---|---|---|---|---|---|
   ```
   Russian (`ru`, profile `ui-migration`):
   ```
   # Разбивка stream:demo/operations/migration

   Сгенерировано tools/generate.py из stories/*/story.md. Не редактировать.

   | Стори | Волна | Экраны | Без экрана | Трекер | Зависит от |
   |---|---|---|---|---|---|
   ```

   (The blank lines count: the file starts with the title line, a blank line, the note line, a blank line, the header line and the separator line.)
3. Rows follow the separator line in ascending slug order. Compare your slug with the slug of each row (the text after the last `/` in its first cell) character by character from the left; the first different character decides in this order: `-`, then digits `0` to `9`, then letters `a` to `z`. When one slug is the start of the other, the shorter one comes first. So `login` < `reports` < `reports-v2` < `reports2`.
4. Insert your row directly above the first row whose slug comes after yours. When no row comes after yours, add it as the last line of the file. Change nothing else. The file ends with a newline.

Example. `BREAKDOWN.md` before:
```
# Breakdown of stream:demo/operations/migration

Generated by tools/generate.py from stories/*/story.md. Do not edit.

| Story | Wave | Scope | Unmapped | Tracker | Depends |
|---|---|---|---|---|---|
| story:demo/operations/login | 1 | screen:demo/operations/login |  | DEMO-101 |  |
| story:demo/operations/users | 2 | screen:demo/operations/users, screen:demo/operations/user-view |  |  | story:demo/operations/login |
```
After creating `story:demo/operations/reports` with wave `2`, scope `screen:demo/operations/reports`, depends `story:demo/operations/login`:
```
# Breakdown of stream:demo/operations/migration

Generated by tools/generate.py from stories/*/story.md. Do not edit.

| Story | Wave | Scope | Unmapped | Tracker | Depends |
|---|---|---|---|---|---|
| story:demo/operations/login | 1 | screen:demo/operations/login |  | DEMO-101 |  |
| story:demo/operations/reports | 2 | screen:demo/operations/reports |  |  | story:demo/operations/login |
| story:demo/operations/users | 2 | screen:demo/operations/users, screen:demo/operations/user-view |  |  | story:demo/operations/login |
```

## Recipe: index entry
Use this only when `python3` is missing. The result equals what `python3 tools/generate.py` writes.

`.agents/index.json` is one JSON object with one entry per line, two spaces of indentation, in this order: `adr:` entries, then `diagram:` and `mockup:` entries, then the `story:` and `task:` entries ascending by key - every `story:` entry comes before every `task:` entry -, then tracker ids ascending by id. A tracker id entry maps the task's `tracker` value to the same task file path.

Ascending means: compare two keys character by character from the left; the first different character decides in this order: `-`, `.`, `/`, digits `0` to `9`, `:`, upper-case letters `A` to `Z`, `_`, lower-case letters `a` to `z`. When one key is the start of the other, the shorter one comes first. So `story:demo/operations/login` < `story:demo/operations/reports`, `story:demo-new/a` < `story:demo/a`, and `DEMO-145` < `DEMO-99` (not number order).

1. Build your entry line. A story: `  "story:<project>/<domain>/<slug>": "projects/<project>/domains/<domain>/streams/<stream>/stories/<slug>/story.md"`. A workspace task: `  "task:<slug>": "tasks/<slug>/task.md"`.
2. Find its position among the lines starting with `  "story:` or `  "task:`:
   - When the file has such lines, insert your line directly above the first of them whose key comes after yours. When none comes after yours, insert it directly after the last of them.
   - When there is no `  "story:` or `  "task:` line, insert it directly after the last line starting with `  "adr:`, `  "diagram:` or `  "mockup:`.
   - When there is none of those either, insert it as the first entry, directly after the line `{`.
   - When the whole file is the single line `{}`, replace that line with three lines: `{`, your line, `}`.
3. Only when the task's `tracker` is not empty (step 6 sets it for a stream at stage `delivery` or `done`, step 21 whenever the person gives one): build the line `  "<tracker>": "<task file path>"` with the same path as your entry line, writing `"` as `\"` and `\` as `\\` inside the id. Tracker lines are the entry lines after the last `  "story:` or `  "task:` line. When a line with the same id already exists, add nothing and tell the person the id is used by another task. Otherwise insert your line directly above the first tracker line whose id comes after yours; when none comes after yours, insert it as the last entry, directly above the line `}`.
4. Commas: every entry line ends with `,` except the last entry, directly above `}`. After inserting, add the missing `,` to the line above your line, and end your line with `,` unless it is the last entry.
5. Keep no trailing spaces. The file ends with `}` and a newline. Change nothing else.

Example 1. The index is `{}`. After creating `story:demo/operations/reports` in stream `migration`:
```
{
  "story:demo/operations/reports": "projects/demo/domains/operations/streams/migration/stories/reports/story.md"
}
```

Example 2. Before:
```
{
  "adr:0001": "docs/adr/0001-use-kafka.md",
  "mockup:demo/operations/login": "https://design.example.org/file/login",
  "story:demo/operations/login": "projects/demo/domains/operations/streams/migration/stories/login/story.md",
  "story:demo/operations/users": "projects/demo/domains/operations/streams/migration/stories/users/story.md",
  "task:billing-architecture": "tasks/billing-architecture/task.md",
  "DEMO-101": "projects/demo/domains/operations/streams/migration/stories/login/story.md"
}
```
After creating `story:demo/operations/reports` in stream `migration`:
```
{
  "adr:0001": "docs/adr/0001-use-kafka.md",
  "mockup:demo/operations/login": "https://design.example.org/file/login",
  "story:demo/operations/login": "projects/demo/domains/operations/streams/migration/stories/login/story.md",
  "story:demo/operations/reports": "projects/demo/domains/operations/streams/migration/stories/reports/story.md",
  "story:demo/operations/users": "projects/demo/domains/operations/streams/migration/stories/users/story.md",
  "task:billing-architecture": "tasks/billing-architecture/task.md",
  "DEMO-101": "projects/demo/domains/operations/streams/migration/stories/login/story.md"
}
```

## Conflicts
For this skill a conflicted file counts as generated when it is `.agents/index.json`, `STATUS.md`, a stream `BREAKDOWN.md`, or a `MAP.md` whose conflicts all lie between `map:` markers (see step 2). Every other file, including `story.md`, `task.md`, element files and `stream.json`, is not generated.

1. List all conflicted files: `git diff --name-only --diff-filter=U`. Write the list down before you change anything.
2. For each `MAP.md` in the list, run `grep -n -e '^<<<<<<<' -e '^>>>>>>>' -e '<!-- map:' <file>`. The file counts as generated only when every `<<<<<<<` line and the `>>>>>>>` line after it both lie between one `:begin -->` line and the next `:end -->` line. Otherwise it is not generated.
3. First check the whole list for any file that is not generated. If there is one:
   - Run `git rebase --abort`. Do not touch any file first, not even the generated ones.
   - For each file that is not generated, show the person both versions with these labels:
     - "default branch": the output of `git show origin/<default>:<file>`;
     - "your branch": the output of `git show <branch>:<file>`, where `<branch>` is `story-<domain>-<slug>` in the story flow and `task-<slug>` in the task flow.
     When one of the two commands fails, tell the person that side has no such file.
   - Stop and wait for the person.
4. Only when every file in the list is generated:
   - For each file in the list, run `git checkout --ours -- <file>`. During a rebase `--ours` is the default branch version, so your own change in that file is gone.
   - Regenerate: if `command -v python3` prints a path, run `python3 tools/generate.py`. Otherwise apply again, to the files in the list, what step 15 does for a story (`## Recipe: BREAKDOWN.md row`, `## Recipe: index entry`, the `story` cell change in `MAP.md`) and step 27 for a task (`## Recipe: index entry`).
   - For each file in the list, run `git add <file>`. Also `git add` any other generated file the regeneration changed.
   - Run `GIT_EDITOR=true git rebase --continue`. When it stops on conflicts again, go back to step 1.

## Without Python
1. Skip `python3 tools/generate.py` and `python3 tools/check.py` everywhere, including `## Conflicts`. Instead apply, at step 15 for a story and at step 27 for a task, the recipes named there.
2. `STATUS.md` is generated, and this kit version ships no hand recipe for adding a waiting row yet. After step 15 or step 27, do not commit and do not push: tell the person to run `python3 tools/generate.py`, and continue from step 17 or step 29 after they have.
3. End the report with the line:

check not run: python3 missing
