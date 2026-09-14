---
name: repos-sync
description: Use to update clones of your repositories under repos/ and see their branch, lag and uncommitted changes.
---
# Repository sync

## Steps
1. Go to the workspace root: the nearest directory, walking up from where you are, where `test -f .agents/kit.json` succeeds. Run every later command in that directory.
2. If `.local/repos.json` does not exist, stop and run the `init` skill first: follow `.agents/skills/init/SKILL.md`. When `init` finishes, continue with step 3.
3. Build the repository list. Open `repos.json`. When the person asked for the option `all`, take every entry of `repositories`. Otherwise open `.local/repos.json` and read its `role`; take every entry of `repositories` whose `roles` list contains that role. Then, still in `.local/repos.json`, for every name in `add`, take the entry of `repos.json` with that `name`; when there is none, put the name in the list anyway and mark it "not in repos.json". Remove every entry whose `name` is in `skip`. When a `name` appears more than once, for example a name in `add` that the role already includes, keep it once. Use each entry's `name`, `remote`, `default_branch` and `status`. An entry whose `status` is `planned` does not exist yet and may have no `remote`, so it is never cloned or fetched.
4. An error line below is the first output line that starts with `fatal:` or `error:`. Lines such as `Cloning into` are not the error. When no line starts with `fatal:` or `error:`, the error line is the last non-empty output line.
5. For each repository in the list, one at a time, do these sub-steps in order. Collect each row for the final table in step 6; do not print rows yet. When a sub-step says "next repository", record the row for the table and start sub-step a for the next repository.
   - a. When the name is marked "not in repos.json", the action is `not in repos.json`, write `-` for branch, behind default and dirty, run no git command, and go to the next repository. When the entry's `status` is `planned`, the action is `planned`, write `-` for branch, behind default and dirty, run no git command, and go to the next repository. Otherwise run `ls -d repos/<name>`. When it exists, go to sub-step c.
   - b. Run `GIT_TERMINAL_PROMPT=0 git clone <remote> repos/<name>`. `GIT_TERMINAL_PROMPT=0` makes a clone that needs a password fail instead of waiting for input. When it succeeds, the action is `cloned`; go to sub-step d. When it fails, the action is `clone failed: <error line>`, write `-` for branch, behind default and dirty, and go to the next repository.
   - c. Run `GIT_TERMINAL_PROMPT=0 git -C repos/<name> fetch --prune`. When it fails, remember `fetch failed: <error line>` and continue with sub-step d.
   - d. Run `git -C repos/<name> rev-parse --abbrev-ref HEAD`; its output is the branch. Run `git -C repos/<name> status --porcelain`; any output means dirty `yes`, no output means dirty `no`.
   - e. When sub-step c failed, the action is `fetch failed: <error line>`, write `-` for behind default, and go to the next repository. The branch and dirty values from sub-step d stay in the row.
   - f. Run `git -C repos/<name> rev-parse --verify --quiet origin/<default_branch>`. When it prints nothing, the action is `no origin/<default_branch>`, write `-` for behind default, and go to the next repository. Do not merge.
   - g. Run `git -C repos/<name> rev-list --count HEAD..origin/<default_branch>`. The number is behind default. Remember it before any merge.
   - h. When the action is `cloned`, keep it and go to the next repository.
   - i. When the branch is not `default_branch`, the action is `skipped: on branch <branch>`; go to the next repository. When dirty is `yes`, the action is `skipped: uncommitted changes`; go to the next repository.
   - j. When behind default is `0`, the action is `up to date`; go to the next repository.
   - k. Run `git -C repos/<name> merge --ff-only origin/<default_branch>`. When it succeeds, the action is `fast-forwarded` and behind default becomes `0`. When it fails, the action is `diverged, not changed` and behind default keeps the number from sub-step g.
6. Report a table with one row per repository, in list order:
    ```
    | Repository | Branch | Behind default | Dirty | Action |
    |---|---|---|---|---|
    | <name> | <branch> | <count> | <yes or no> | <action> |
    ```

## Never
- `git checkout`
- `git switch`
- `git stash`
- `git reset`
- `git clean`
- `git pull`, with merge or with rebase
- deleting files in `repos/`

## Without Python
This skill needs no Python. It changes only clones under `repos/`, which git ignores, so there is nothing to check.
