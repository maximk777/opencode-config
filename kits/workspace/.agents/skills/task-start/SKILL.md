---
name: task-start
description: Use to start a waiting task - resolve it from the STATUS.md queue or by key, show its context through task-context, flip it to in_progress with the person's owner key and today's date on a new branch and open a merge request. Reopens a done task and stops for one already in progress.
---
# Start a task

## Steps
1. Go to the workspace root: the nearest directory, walking up from where you are, where `test -f .agents/kit.json` succeeds. Run every command below from there.
2. Resolve what to start. Ask the person, unless they already said it. The answer is a key, a tracker id, or a request to see the queue:
   - a key: `task:<slug>` for a workspace task in `tasks/<slug>/task.md`, or `story:<project>/<domain>/<slug>` for a story;
   - a tracker id, for example `DEMO-145`;
   - to see the queue: read `STATUS.md`, show the person the rows between `<!-- status:waiting:begin -->` and `<!-- status:waiting:end -->`, and ask them to name the key of one row or to give a key or a tracker id. When that section holds no rows, report that the queue is empty and stop.
   Below, `<input>` is the key or the tracker id.
3. Find the task file:
   - Read `.agents/index.json` and take the value of `<input>`. When there is a value and `test -f <value>` succeeds, that value is the task file; go to step 4.
   - Otherwise the index may be stale. Search the disk, with `2>/dev/null` on every command so an empty search prints nothing:
     - for `task:<slug>`, use `tasks/<slug>/task.md` when `test -f` succeeds on it;
     - for `story:<project>/<domain>/<slug>`, run `ls projects/<project>/domains/<domain>/streams/*/stories/<slug>/story.md 2>/dev/null`;
     - for a tracker id, run `grep -rlE "^tracker: [\"']?<input>[\"']?$" projects tasks 2>/dev/null`.
   - Exactly one file: that is the task file, and remember the line `index is stale: <input> is not in .agents/index.json` for the report. Several files: report every path, tell the person the key or id is used by more than one task, and stop. Nothing: answer `<input> is not in this workspace` and stop.
4. Read the `status:` line of the frontmatter of the task file (between its first two `---` lines) and remove the quotes around the value, if any:
   - `waiting`: go to step 5.
   - `done`: this is a reopen. Ask the person whether to reopen this task and wait for the answer; on a no, stop and change nothing. On a yes, ask for the reopen reason and wait; never invent one. Keep the reason as `<reason>`; step 14 puts it into the merge request description. Go to step 5.
   - `in_progress`: stop, tell the person the task is already in progress and read its `owner:` line to them, and change nothing.
   - An empty value, a missing line, or anything else: stop, tell the person the task file has no valid `status` field, and change nothing.
5. Show the context: follow `.agents/skills/task-context/SKILL.md` for `<input>` and give its report to the person. When that skill answers `<input> is not in this workspace` or stops, stop too and change nothing.
6. Collect the values to write:
   - Ask the person for their short owner key - one lowercase word of letters, digits and `-`, the name their git commits carry, for example `maxim` - unless they already gave it. Check it with `printf '%s\n' '<owner>' | grep -Ex '[a-z0-9-]+'`; when it prints nothing, ask again.
   - Run `date +%Y-%m-%d` and take its output as `<date>`.
7. Find the default branch: run `git symbolic-ref --short refs/remotes/origin/HEAD` and remove the `origin/` prefix; when the command fails, use `main`. Call it `<default>`. Then run, one by one:
   - `git switch <default>`
   - `GIT_TERMINAL_PROMPT=0 git pull --ff-only`
8. Take `<name>`: the text after the last `/` of the key (`e2e-checkout` for `task:e2e-checkout`, `documents` for `story:abs/operations/documents`), or `<input>` itself when step 2 got a tracker id. Run `git switch -c task-<name>`. When the branch already exists, the command fails: stop, tell the person, and change nothing.
9. Flip the frontmatter of the task file. Change exactly these three lines and keep every other line and its order:
   - `status: in_progress`
   - `owner: <owner>`
   - `started: <date>`
   For a reopen this is the whole change to the file: the previous `owner` and `started` values are replaced, never kept or appended. Change nothing else.
10. Update the generated files: run `python3 tools/generate.py`. It rewrites the sections of `STATUS.md` from the `status`, `owner` and `started` fields.
11. Run `python3 tools/check.py`, at most three times in total. After each run look only at findings that name the task file or `STATUS.md`:
    - Fix such a finding only when the fix needs no new value, for example a wrong line format or a stale generated file (run `python3 tools/generate.py` again). Then run the check again.
    - A finding that needs a value only the person has, or one that stays after the third run: stop, do not commit, list the findings, and wait.
    - Findings in other files: do not fix them; list them in the report.
12. Commit: run `git add <task file> STATUS.md`, then `git commit -m "docs(task): start <name>"`, or `docs(story): start <name>` when the task file is a story.
13. Run `GIT_TERMINAL_PROMPT=0 git pull --rebase origin <default>`. On a conflict run `git rebase --abort`, show the person both versions of every conflicted file - "default branch": the output of `git show origin/<default>:<file>`, "your branch": the output of `git show task-<name>:<file>` - and stop. After a clean rebase run step 11 again; when it made you fix a file, run `git add <file>` for each fixed file, then `git commit --amend --no-edit`.
14. Push and open the merge request by `.agents/rules/merge-requests.md`, with branch `task-<name>` and title `Start <input>`, or `Reopen <input>` for a reopen. For a reopen the merge request description must start with the line `Reopen: <reason>`: with `gitlab`, add `-o merge_request.description="Reopen: <reason>"` to the push; with `github`, run `gh pr create --title "Reopen <input>" --body "Reopen: <reason>"`; with `git`, tell the person to open the request with that first line. Use `GIT_TERMINAL_PROMPT=0` before `git push`.
15. Report to the person:
    - the task file, and the three values written there (`status: in_progress`, `owner`, `started`);
    - for a reopen, the reason, and that it must stay in the merge request description;
    - the branch `task-<name>` and the merge request link, or the instruction to open it;
    - the `index is stale` line from step 3, when there is one - the fix is `python3 tools/generate.py`, run by a person;
    - the check findings left in other files, when there are any;
    - as the last line, the check result, or `check not run: python3 missing`.

## Without Python
1. Make the flip of step 9, then apply `## Recipe: STATUS.md start flip` to `STATUS.md`: it moves the task's row from the `## Waiting` section to the `## In progress` section, with the result `python3 tools/generate.py` would write. Then continue with step 12.
2. Skip `python3 tools/generate.py` and `python3 tools/check.py` everywhere else they appear.
3. End the report with the line:

check not run: python3 missing

## Recipe: STATUS.md start flip
Use this only when `python3` is missing. The result equals what `python3 tools/generate.py` writes. Only the text between the `<!-- status:... -->` markers changes. Take `<task key>` from the `key` line of the task file, `<task file>` as its path from the workspace root, and `<owner>` and `<started>` from the values step 6 collected. A story waits under the heading of its stream group `<project>/<domain>/<stream>`; a task in `tasks/` waits under the heading `workspace`.

1. `## Waiting`: delete the row `| [<task key>](<task file>) |`. When no row is left in its group, delete the whole group: the `### <group>` line, the blank line below it, its two table lines `| Task |` and `|---|`, and one neighbouring blank line when there is one, so no two blank lines stay together.
2. `## In progress`: write the row `| [<task key>](<task file>) | <started> |`:
   - When the section holds no rows between its markers, insert directly below the begin marker:

     ```
     ### <owner>

     | Task | Started |
     |---|---|
     | [<task key>](<task file>) | <started> |
     ```

   - When a `### <owner>` group is already there, insert the row above the first of its rows whose started date is later than `<started>`, or whose date equals `<started>` and whose key comes after `<task key>`; below the last row of the group when there is no such row.
   - Otherwise insert the same four lines as a new group between the groups whose owners sort around `<owner>`: above the `### ` line of the first group whose owner comes after `<owner>`, with a blank line below the new row, or below the last row of the last group when every owner comes before, with a blank line above the new `### <owner>` line. Owners and keys sort character by character from the left; the first different character decides in this order: `-`, then `.`, `/`, digits `0` to `9`, `:`, upper-case letters `A` to `Z`, `_`, lower-case letters `a` to `z`. When one name is the start of the other, the shorter one comes first.
3. Change nothing else in the file.

### Example
`maxim` starts `story:demo/operations/documents` on 2026-09-21. It is the only waiting row of its stream, and nobody is in progress yet. `## Waiting` before step 1:

```
### demo/operations/migration

| Task |
|---|
| [story:demo/operations/documents](projects/demo/domains/operations/streams/migration/stories/documents/story.md) |
```

Step 1 deletes the row, and with it the whole now-empty group. Step 2 finds no rows between the `## In progress` markers and inserts directly below the begin marker:

```
### maxim

| Task | Started |
|---|---|
| [story:demo/operations/documents](projects/demo/domains/operations/streams/migration/stories/documents/story.md) | 2026-09-21 |
```
