---
name: work-record
description: Use when the work on a task or story is finished - resolve the task, write work.md into its task folder, set the task status to done and open a merge request.
---
# Close a finished task with a work record

## Steps
1. Go to the workspace root: the nearest directory, walking up from where you are, where `test -f .agents/kit.json` succeeds. Run every command below from there.
2. Ask the person for the task: a tracker id, a `task:<slug>` key, or a story key `story:<project>/<domain>/<slug>`. Resolve it to exactly one task file `<task file>`; the task folder `<folder>` is the directory holding that file, and the task key is the frontmatter `key` of `<task file>`. When resolution finds nothing, stop: it is not in this workspace. When it finds several tasks, stop and list them. Change nothing.
   - `task:<slug>`: run `test -f tasks/<slug>/task.md`. When it fails, the task is not in this workspace.
   - `story:<project>/<domain>/<slug>`: take the value of the key from `.agents/index.json`. When the index has no value, or `test -f <value>` fails, run `ls projects/<project>/domains/<domain>/streams/*/stories/<slug>/story.md 2>/dev/null` instead; exactly one printed path is `<task file>` (also remember for the report that the index is stale; the fix is `python3 tools/generate.py`). Empty output means the story is not in this workspace.
   - A tracker id `<raw>`: validate it first (step 3). Then take the value of `<raw>` from `.agents/index.json`. When the index has no value, run `grep -rlE "^tracker: [\"']?<raw>[\"']?$" projects tasks 2>/dev/null`: exactly one printed path is `<task file>` (remember the stale-index line for the report), empty output means the id is not in this workspace, and several paths mean the id is used by more than one task - stop and list them.
3. Validate a tracker id (only for a tracker-id input): read `tracker/trackers.json`. Every entry of `trackers` carries `key` and `id_pattern`; JSON doubles every backslash, so `\\d` in the file means `\d`. Rewrite each pattern for `grep -E` (write every `\d` as `[0-9]`) and run `printf '%s\n' '<raw>' | grep -Ex '<rewritten pattern>'` entry by entry until one matches. The `-x` makes the whole id match, not a part of it. When no entry matches, stop: the id is not in this workspace.
4. Read the frontmatter of `<task file>`: `status`, `tracker`. When `status` is not `in_progress`, stop and change nothing: a `waiting` task must be started first and a `done` task must be reopened - tell the person to run the `task-start` skill in both cases.
5. Set `<ID>`: the task's `tracker` value when it is not empty, otherwise the task's slug (the `<slug>` of `task:<slug>`, or the story slug). The branch below is `work/<ID>` and the draft is `.local/drafts/<ID>.md`.
6. Read `.local/drafts/<ID>.md`. If it does not exist, ask the person four questions: what changed, which decisions were taken, what is still open, and what was verified. Wait for the answers before going on.
7. Find the workspace default branch: run `git symbolic-ref --short refs/remotes/origin/HEAD` and remove the `origin/` prefix; when the command fails, use `main`. Call it `<default>`. Then run, one by one:
   - `git status --porcelain --untracked-files=no`. When it prints anything, stop and tell the person: the workspace has uncommitted tracked changes. Commit nothing.
   - `git switch <default>`
   - `GIT_TERMINAL_PROMPT=0 git pull --ff-only`
8. Collect commits. Read `repos.json`: the pull has just made it the manifest of `<default>`, and the record is checked against it - a repository that is not in the manifest cannot go into `repos`. For each entry of `repositories` whose directory `repos/<name>` exists, with `<default_branch>` from the entry:
   - Run `git -C repos/<name> fetch --prune`.
   - Run `git -C repos/<name> for-each-ref --format='%(refname:short)' refs/heads refs/remotes | grep -E '(^|[^A-Za-z0-9])<ID>([^0-9]|$)'`. Each printed line is one `<branch>`, used as printed. The grep keeps only names where `<ID>` is a whole token, so `TASK-1` does not match `feat/TASK-10-y`.
   - For every `<branch>`, run `git -C repos/<name> log --format=%H origin/<default_branch>..<branch>`.
   - Run `git -C repos/<name> log --format=%H -E --grep='<ID>([^0-9]|$)' origin/<default_branch>` to find work that is already merged.
   - Write each sha as `<name>@<sha>`. Keep each value once, in the order found.
   - A repository with at least one sha goes into `repos`.
9. If no repository gave a sha, ask the person which repositories and branches hold the work, and repeat step 8 for them. A repository that is not in the manifest cannot go into `repos`; tell the person it must be merged into `<default>` first.
10. Collect merge requests. For each repository in `repos`, look at its `forge` in the manifest:
    - `gitlab`: if `command -v glab` and `glab auth status` both succeed, run `glab mr list --search "<ID>" --all --output json` inside `repos/<name>` and take every `web_url` value that contains `/-/merge_requests/` (the other `web_url` values are user profiles). Otherwise add `glab` to the `missing` list.
    - `github`: if `command -v gh` and `gh auth status` both succeed, run `gh pr list --search "<ID>" --state all --json url --jq ".[].url"` inside `repos/<name>` and take every printed URL. Otherwise add `gh` to the `missing` list.
    - `git`: there is no merge request data; add nothing.
    - Keep each URL once, in the order found. Keep each name in `missing` once.
11. Bring the branch `work/<ID>` up:
    - If `git rev-parse --verify --quiet work/<ID>` or `git rev-parse --verify --quiet origin/work/<ID>` succeeds, the branch already exists:
      - For each of `work/<ID>` and `origin/work/<ID>` that exists, run `git diff --name-only origin/<default>...<that branch>`. A generated file in the list (the list of step 15) is expected on the branch - step 15 commits those files itself, for example `STATUS.md` - and never stops the skill. If any other printed path does not start with `<folder>/`, stop and tell the person which paths they are: the branch may touch the task folder and generated files only. Commit nothing.
      - If `origin/work/<ID>` exists, the branch is already pushed. Its commits must never be rewritten. Then:
        - When `git rev-parse --verify --quiet work/<ID>` succeeds, run `git switch work/<ID>`, then `git branch --set-upstream-to=origin/work/<ID>`.
        - Otherwise run `git switch --track origin/work/<ID>`.
        - Run `git pull --ff-only`. If it fails, stop and tell the person that the local and pushed `work/<ID>` differ. Commit nothing.
      - If only the local `work/<ID>` exists, run `git switch work/<ID>`.
      - Bring the branch up to date: run `GIT_EDITOR=true git merge --no-edit origin/<default>`. The branch may predate a repository merged into `<default>`; after the merge its `repos.json` equals the manifest of step 8, which the check tests the record against. The branch changes only `<folder>/` and generated files, so the merge is clean. On a conflict, follow `## Conflicts`.
      - Skip the rest of this step.
    - Otherwise run `git switch -c work/<ID>`.
12. Write `<folder>/work.md` from `.agents/templates/work.md`:
    - Run `date +%F` and put its output into the frontmatter line `recorded:`.
    - `repos`, `merge_requests` and `commits` as block lists: the line `key:`, then one line `  - value` per value. Write `key: []` when the list is empty.
    - Replace `<task key>` in the title line with the task key and `<one-line summary>` with one line about the work.
    - Fill `## Changed`, `## Decisions` and `## Verification` from the draft or the answers. Write "None." in a section with nothing to say.
    - `## Open questions` gets exactly `None.`: a done task keeps no open questions. When the draft names an open question, ask the person to resolve it first; when they cannot, stop and leave the task `in_progress`.
    - Write a stand as a link to its key, `[stand:<name>](<relative path from <folder> to environments.json>)`, never as an address. The path takes one `..` per folder level of `<folder>`: from `tasks/<slug>/` (two levels) it is `../../environments.json`, from a story folder `projects/<p>/domains/<d>/streams/<s>/stories/<slug>/` (eight levels) it is `../../../../../../../../environments.json`.
    - Never link into `.local/`.
13. Flip the task status in `<task file>`: change the `status:` line to `status: done` and empty the `owner:` and `started:` lines (the check requires them empty once the status is not `in_progress`; the history keeps who worked when). Change no other line.
14. Update the generated files and run the check. First run `command -v python3`.
    - When it prints a path: run `python3 tools/generate.py` (the record moves the task from the `## In progress` section of `STATUS.md` to `## Done recently`), then `python3 tools/check.py`, at most three runs in total. After each run, look only at findings that name a file this skill changed: `<folder>/work.md`, `<task file>` and `STATUS.md`.
      - Fix such a finding when the fix needs no new value, for example a wrong list form or a missing section. Then run both commands again.
      - One finding is expected and is not yours to fix: `task-state` "merge_requests must not be empty when the task is done", when step 10 found no merge request. Do not stop for it; keep it for the report.
      - When another finding on these files needs a value only the person has, or survives the third run: stop, do not commit, list the findings, and wait.
      - Findings in other files: do not fix them; list them in the report.
    - When it prints nothing: apply `## Recipe: STATUS.md done flip` to `STATUS.md` and remember the line `check not run: python3 missing` for the report.
15. Commit: run `git status --short --untracked-files=all`. Stage `<folder>/` - the record and the task file. Then stage every other listed path that is a generated file: its path starts with `.claude/`, `.opencode/` or `.cursor/`, or it is exactly `CLAUDE.md`, `.agents/index.json`, `REPOSITORIES.md` or `STATUS.md`, or it matches `projects/*/domains/*/streams/*/BREAKDOWN.md`. Normally that is `STATUS.md` alone. Do not stage any other path; mention it in the report instead. Run `git commit -m "docs(work): record <ID>"`.
16. Update from the default branch:
    - When step 11 found `origin/work/<ID>`: run `GIT_EDITOR=true git merge --no-edit origin/<default>`.
    - Otherwise: run `GIT_TERMINAL_PROMPT=0 git pull --rebase origin <default>`.
    - On conflicts follow `## Conflicts`.
17. Push and open the merge request by `params.forge` in `.agents/kit.json`:
    - `gitlab`: run `GIT_TERMINAL_PROMPT=0 git push -u origin work/<ID> -o merge_request.create -o merge_request.title="Work record <ID>"`.
    - `github`: run `GIT_TERMINAL_PROMPT=0 git push -u origin work/<ID>`, then `gh pr create --title "Work record <ID>" --body "<folder>/work.md"`. If `gh` is missing or the command fails, print its error and ask the person to open the pull request for branch `work/<ID>`.
    - `git`: run `GIT_TERMINAL_PROMPT=0 git push -u origin work/<ID>`, print the branch name `work/<ID>` and ask the person to open the merge request.
    - Never push with `--force` or `--force-with-lease`.
18. If the push is rejected, print the error and these commands to finish by hand, then stop:
    - When step 11 found `origin/work/<ID>`: `git pull --no-rebase --no-edit origin work/<ID>`, then `GIT_EDITOR=true git merge --no-edit origin/<default>`.
    - Otherwise: `git pull --rebase origin <default>`. After fixing a conflict, run `git add <file>`, then `GIT_EDITOR=true git rebase --continue`.
    - Then the push for the forge:
      - `gitlab`: `git push -u origin work/<ID> -o merge_request.create -o merge_request.title="Work record <ID>"`
      - `github`: `git push -u origin work/<ID>`, then `gh pr create --title "Work record <ID>" --body "<folder>/work.md"`
      - `git`: `git push -u origin work/<ID>`, then open the merge request for branch `work/<ID>` in the forge web page.
19. Report to the person:
    - the record path `<folder>/work.md`;
    - the task file `<task file>` and that its `status` is now `done`;
    - the branch `work/<ID>`;
    - the merge request link, or the instruction to open it;
    - `missing: <names from the missing list, joined with ", ">`, or `missing: none`; when the list names `glab` or `gh`, name the CLI and say that `merge_requests` stays empty until a person installs it and adds the merge request URLs to `<folder>/work.md`;
    - the expected `merge_requests must not be empty when the task is done` finding, when step 10 found no merge request;
    - the check findings left in other files, if any;
    - as the last line, the check result, or `check not run: python3 missing`.

## Conflicts
The branch touches the task folder and the generated files of step 15, so a conflict almost always lands in a generated file.

1. List all conflicted files: `git diff --name-only --diff-filter=U`.
2. A file is generated when its path starts with `.claude/`, `.opencode/` or `.cursor/`, or it is exactly `CLAUDE.md`, `.agents/index.json`, `REPOSITORIES.md` or `STATUS.md`, or it matches `projects/*/domains/*/streams/*/BREAKDOWN.md`.
3. When every conflicted file is generated: take the default-branch version of each - `git checkout --theirs -- <file>` during a merge, `git checkout --ours -- <file>` during a rebase (there `--ours` is the default branch) - then regenerate with `python3 tools/generate.py`, or apply `## Recipe: STATUS.md done flip` without Python. Run `git add <file>` for each file, then continue with `GIT_EDITOR=true git rebase --continue` or `git commit --no-edit`.
4. When some conflicted file is not generated: run `git merge --abort` or `git rebase --abort` (the command of the running step). For each file that is not generated, show the person both versions with their labels: "default branch" is the output of `git show origin/<default>:<file>`, and "your branch" is the output of `git show work/<ID>:<file>`. Then stop and wait.

## Example record
`projects/demo/domains/operations/streams/migration/stories/documents/work.md` for the story `story:demo/operations/documents` with tracker `TASK-1`, work in repository `demo-bff`:

```markdown
---
repos:
  - demo-bff
merge_requests:
  - https://gitlab.example/ops/demo-bff/-/merge_requests/42
commits:
  - demo-bff@2c0efd7072c42fb1df4dce53f4c284baf338a035
recorded: 2026-09-20
---
# story:demo/operations/documents: Show client documents in the new interface

## Changed
demo-bff: the `/documents` endpoint now streams files straight from object storage.

## Decisions
Files are fetched on demand; the nightly copy job stays for the audit export only.

## Open questions
None.

## Verification
Unit tests pass in demo-bff. The screen was opened on [stand:test](../../../../../../../../environments.json) and downloaded a test document.
```

## Without Python
1. Skip `python3 tools/generate.py` and `python3 tools/check.py` everywhere in the steps.
2. Update `STATUS.md` by `## Recipe: STATUS.md done flip`. A task that was started without Python carries a row written by `## Recipe: STATUS.md start flip` in `.agents/skills/task-start/SKILL.md`; that row is what step 1 of the recipe below deletes.
3. End the report with the line:

check not run: python3 missing

## Recipe: STATUS.md done flip
Use this only when `python3` is missing. The result equals what `python3 tools/generate.py` writes. Only the text between the `<!-- status:... -->` markers changes; the `drift` section stays empty.

1. `## In progress`: delete the row `| [<task key>](<task file>) | <started> |`, where `<started>` is the `started` value of the task file. When no row is left in that owner group, delete the whole group: the `### <owner>` line, the blank line, its two table lines `| Task | Started |` and `|---|---|`, and one neighbouring blank line when there is one, so no two blank lines stay together.
2. `## Done recently`: `<recorded>` is today, the newest date the section keeps. When the section holds no rows between its markers, insert directly below the begin marker:
   ```
   | Task | Recorded |
   |---|---|
   | [<task key>](<task file>) | <recorded> |
   ```
   Otherwise insert the row `| [<task key>](<task file>) | <recorded> |` directly below the `|---|---|` line; when rows dated `<recorded>` already exist, insert it above the first of them whose key comes after the task key, or below the last of them when none does. Keys compare character by character from the left; the first different character decides in this order: `-`, then `.`, `/`, digits `0` to `9`, `:`, upper-case letters `A` to `Z`, `_`, lower-case letters `a` to `z`. When one key is the start of the other, the shorter one comes first.
3. Change nothing else in the file.

### Example
`maxim` records `story:demo/operations/documents` on 2026-09-20, and the section already holds a row of the same day for `story:demo/operations/documents-export`, whose key comes after. Step 2 inserts the new row above it:

```
| Task | Recorded |
|---|---|
| [story:demo/operations/documents](projects/demo/domains/operations/streams/migration/stories/documents/story.md) | 2026-09-20 |
| [story:demo/operations/documents-export](projects/demo/domains/operations/streams/migration/stories/documents-export/story.md) | 2026-09-20 |
```
