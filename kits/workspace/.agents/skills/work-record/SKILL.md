---
name: work-record
description: Use when you finished work on a tracker task and it must be recorded in the workspace through a merge request.
---
# Record finished work

## Steps
1. Go to the workspace root: the nearest directory, walking up from where you are, where `test -f .agents/kit.json` succeeds. Run every command below from there.
2. Ask the person for the task id. Below the id is `<ID>`. Check it:
   - Read `id_pattern` from `tracker/tracker.json`. JSON doubles every backslash, so `\\d` in the file means `\d`.
   - Rewrite the pattern for `grep -E`: write every `\d` as `[0-9]`, because `grep -E` does not know `\d`.
   - Run `printf '%s\n' '<ID>' | grep -Ex '<rewritten pattern>'`. The `-x` makes the whole id match, not a part of it.
   - If it prints nothing, stop and ask again.
3. Read `.local/drafts/<ID>.md`. If it does not exist, ask the person four questions: what changed, which decisions were taken, what is still open, and what was verified. Wait for the answers before going on.
4. Find the workspace default branch: run `git symbolic-ref --short refs/remotes/origin/HEAD` and remove the `origin/` prefix; when the command fails, use `main`. Call it `<default>`. Then run `git fetch origin`.
5. Read the manifest of the default branch: run `git show origin/<default>:repos.json`. Below, "the manifest" is this output, never the `repos.json` file of the current branch: the record is checked against the default branch, and a repository added only on an unmerged branch would fail the `work-record` check. Collect commits. For each entry in `repositories` of the manifest whose directory `repos/<name>` exists, with `<default_branch>` from the entry:
   - Run `git -C repos/<name> fetch --prune`.
   - Run `git -C repos/<name> for-each-ref --format='%(refname:short)' refs/heads refs/remotes | grep -E '(^|[^A-Za-z0-9])<ID>([^0-9]|$)'`. Each printed line is one `<branch>`, used as printed. The grep keeps only names where `<ID>` is a whole token, so `TASK-1` does not match `feat/TASK-10-y`.
   - For every `<branch>`, run `git -C repos/<name> log --format=%H origin/<default_branch>..<branch>`.
   - Run `git -C repos/<name> log --format=%H -E --grep='<ID>([^0-9]|$)' origin/<default_branch>` to find work that is already merged.
   - Write each sha as `<name>@<sha>`. Keep each value once, in the order found.
   - A repository with at least one sha goes into `repos`.
6. If no repository gave a sha, ask the person which repositories and branches hold the work, and repeat step 5 for them. A repository that is not in the manifest cannot go into `repos`; tell the person it must be merged into `<default>` first.
7. Collect merge requests. For each repository in `repos`, look at its `forge` in the manifest:
   - `gitlab`: if `command -v glab` and `glab auth status` both succeed, run `glab mr list --search "<ID>" --all --output json` inside `repos/<name>` and take every `web_url` value that contains `/-/merge_requests/` (the other `web_url` values are user profiles). Otherwise add `glab` to the `missing` list.
   - `github`: if `command -v gh` and `gh auth status` both succeed, run `gh pr list --search "<ID>" --state all --json url --jq ".[].url"` inside `repos/<name>` and take every printed URL. Otherwise add `gh` to the `missing` list.
   - `git`: there is no merge request data; add nothing.
   - Keep each URL once, in the order found. Keep each name in `missing` once.
8. Run `git status --porcelain --untracked-files=no`. If it prints anything, stop and tell the person: the workspace has uncommitted tracked changes. Commit nothing.
9. If `git rev-parse --verify --quiet work/<ID>` or `git rev-parse --verify --quiet origin/work/<ID>` succeeds, the branch already exists:
   - For each of `work/<ID>` and `origin/work/<ID>` that exists, run `git diff --name-only origin/<default>...<that branch>`.
   - If any printed path does not start with `work/<ID>/`, stop and tell the person which paths they are. Commit nothing.
   - If `origin/work/<ID>` exists, the branch is already pushed. Its commits must never be rewritten. Remember this for steps 14 and 15. Then:
     - When `git rev-parse --verify --quiet work/<ID>` succeeds, run `git switch work/<ID>`, then `git branch --set-upstream-to=origin/work/<ID>`.
     - Otherwise run `git switch --track origin/work/<ID>`.
     - Run `git pull --ff-only`. If it fails, stop and tell the person that the local and pushed `work/<ID>` differ. Commit nothing.
   - If only the local `work/<ID>` exists, run `git switch work/<ID>`.
   - Bring the branch up to date: run `GIT_EDITOR=true git merge --no-edit origin/<default>`. The branch may predate a repository merged into `<default>`; after the merge its `repos.json` equals the manifest from step 5, which step 12 checks the record against. The branch changes only `work/<ID>/`, so the merge is clean. On a conflict, run `git diff --name-only --diff-filter=U` to list the files, then `git merge --abort`, show the two versions as step 14 describes and stop. Commit nothing.
   - Skip step 10.
10. Otherwise run, one by one:
    - `git switch <default>`
    - `git pull --ff-only`
    - `git switch -c work/<ID>`
11. Write `work/<ID>/record.md` from `.agents/templates/work-record.md`:
    - Frontmatter `task: <ID>`.
    - `repos`, `merge_requests` and `commits` as block lists: the line `key:`, then one line `  - value` per value. Write `key: []` when the list is empty.
    - Add `story:` only when the person names a story. Add `contract:` or `consumed_contract:` only when the person gives them, as `key:` then lines `  sub: value`.
    - Replace `<one-line summary>` in the title with one line about the work.
    - Fill `## Changed`, `## Decisions`, `## Open questions` and `## Verification` from the draft or the answers. Write "None." in a section with nothing to say.
    - Write a stand as a link to its key, `[stand:<name>](../../environments.json)`, never as an address.
    - Never link into `.local/`.
12. If `command -v python3` succeeds, check the record:
    - Run `python3 tools/generate.py`, then `python3 tools/check.py`. Each finding is a line `path:line rule message`.
    - If a finding has the path `work/<ID>/record.md`, fix it in that file and run both commands again.
    - Exception: a `work-record` finding "repository X is not in repos.json" for a repository X taken from the manifest in step 5 is never fixed by removing X from `repos`. Stop and tell the person the finding. Commit nothing.
    - Change no other file. When no finding has the path `work/<ID>/record.md`, stop repeating. Remember the findings that are left for the report.
    - Otherwise, when `python3` is missing, remember the line `check not run: python3 missing`.
13. Commit: run `git add work/<ID>/`, then `git commit -m "docs(work): record <ID>"`.
14. Update from the default branch:
    - If step 9 found `origin/work/<ID>`, run `GIT_EDITOR=true git merge --no-edit origin/<default>`. On a conflict, run `git diff --name-only --diff-filter=U` to list the files, then `git merge --abort`.
    - Otherwise run `git pull --rebase origin <default>`. On a conflict, run `git diff --name-only --diff-filter=U` to list the files, then `git rebase --abort`.
    - A conflict means someone else changed `work/<ID>/`. For each listed `<file>`, show the person two versions with their labels: "default branch" is the output of `git show origin/<default>:<file>`, and "your branch" is the output of `git show work/<ID>:<file>`. Then stop.
15. Push and open the merge request by `params.forge` in `.agents/kit.json`:
    - `gitlab`: run `git push -u origin work/<ID> -o merge_request.create -o merge_request.title="Work record <ID>"`.
    - `github`: run `git push -u origin work/<ID>`, then `gh pr create --title "Work record <ID>" --body "work/<ID>/record.md"`. If `gh` is missing or the command fails, print its error and ask the person to open the pull request for branch `work/<ID>`.
    - `git`: run `git push -u origin work/<ID>`, print the branch name `work/<ID>` and ask the person to open the merge request.
    - Never push with `--force` or `--force-with-lease`.
16. If the push is rejected, print the error and these commands to finish by hand, then stop:
    - When step 9 found `origin/work/<ID>`: `git pull --no-rebase --no-edit origin work/<ID>`, then `GIT_EDITOR=true git merge --no-edit origin/<default>`.
    - Otherwise: `git pull --rebase origin <default>`. After fixing a conflict, run `git add <file>`, then `GIT_EDITOR=true git rebase --continue`.
    - Then the push for the forge:
      - `gitlab`: `git push -u origin work/<ID> -o merge_request.create -o merge_request.title="Work record <ID>"`
      - `github`: `git push -u origin work/<ID>`, then `gh pr create --title "Work record <ID>" --body "work/<ID>/record.md"`
      - `git`: `git push -u origin work/<ID>`, then open the merge request for branch `work/<ID>` in the forge web page.
17. Report to the person:
    - the record path `work/<ID>/record.md`;
    - the branch `work/<ID>`;
    - the merge request link, or the instruction to open it;
    - `missing: <names from the missing list, joined with ", ">`, or `missing: none`;
    - the check findings left in other files, if any;
    - as the last line, the check result, or `check not run: python3 missing`.

## Example record
`work/TASK-1/record.md` for work in repository `demo-bff` with one commit and no merge request data:

```markdown
---
task: TASK-1
repos:
  - demo-bff
merge_requests: []
commits:
  - demo-bff@2c0efd7072c42fb1df4dce53f4c284baf338a035
---
# TASK-1: Show the card limit on the payment screen

## Changed
demo-bff: the `/payments/screen` response now has a `card_limit` field read from the limits service.

## Decisions
The limit is cached for 60 seconds per card to keep the screen fast; the limits service allows this staleness.

## Open questions
None.

## Verification
Unit tests pass in demo-bff. The payment screen was opened on [stand:test](../../environments.json) and showed the limit for a test card.
```

## Without Python
1. Skip `python3 tools/generate.py` and `python3 tools/check.py` in step 12.
2. A work record changes no generated file, so no recipe is needed.
3. End the report with the line:

check not run: python3 missing
