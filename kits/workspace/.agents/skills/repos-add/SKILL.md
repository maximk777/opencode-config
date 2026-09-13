---
name: repos-add
description: Use to add a code repository to this workspace's manifest, table and your clones, through a merge request.
---
# Add a repository

## Steps
1. Go to the workspace root: the nearest directory, walking up from where you are, where `test -f .agents/kit.json` succeeds. Run every command below from there.
2. Collect inputs from the person:
   - `remote` (required): the clone URL or path.
   - `name`: default is the last path segment of the remote without `.git` (for `git@gitlab.example.com:team/payments-worker.git` it is `payments-worker`).
   - `roles`: ask for one or more names; the allowed names are the file names without `.md` printed by `ls .agents/roles/`.
   - `summary`: ask for one line.
   - Never invent roles or summary. If the person gives none, ask again.
3. Set `forge`. Use the value the person gave. Otherwise find the remote host:
   - `git@host:path` (for example `git@gitlab.example.com:team/app.git`): the host is the text between `@` and the first `:`, here `gitlab.example.com`;
   - `ssh://git@host/path` or `ssh://host/path`: remove `ssh://`, then the text before the first `/`, without any `user@` before it and any `:port` after it;
   - `https://host/path` or `http://host/path`: remove the scheme, then the text before the first `/`, without any `user@` before it and any `:port` after it.

   Then choose `forge` by the host:
   - host contains `gitlab` → `gitlab`;
   - host is `github.com` → `github`;
   - a local path or a `file://` remote → `git`;
   - any other host → ask the person to choose `gitlab`, `github` or `git`.
4. Read `repos.json`. If any entry has the same `name` or the same `remote`, stop, tell the person which entry matches, and change nothing.
5. Run `git ls-remote --symref <remote> HEAD`. The output line `ref: refs/heads/<branch>	HEAD` gives `default_branch` = `<branch>`.
   - When the command succeeds but prints no line starting with `ref:` (the remote is an empty repository), ask the person for `default_branch`.
   - When the command fails, stop and ask the person whether to add the entry without cloning. With no answer, stop and change nothing.
   - When the person says no, stop and change nothing.
   - When the person says yes, ask the person for `default_branch` and skip step 9.
6. Find the workspace default branch: run `git symbolic-ref --short refs/remotes/origin/HEAD` and remove the `origin/` prefix; when the command fails, use `main`. Call it `<default>`. Then run, one by one:
   - `git switch <default>`
   - `git pull --ff-only`
   - `git switch -c repos-add-<name>`
7. Edit `repos.json`: append the entry as the last element of `repositories`. Keys go in the order `name`, `remote`, `forge`, `default_branch`, `roles`, `summary`. Use two-space indentation and put each list item on its own line, exactly as in the example below. When the list already has entries, add a comma after the closing `}` of the previous last entry. Inside every JSON string value write `"` as `\"` and `\` as `\\`; for example the summary `Reads "raw" C:\data` becomes `"summary": "Reads \"raw\" C:\\data"`.
8. If `command -v python3` succeeds, run `python3 tools/generate.py`. Otherwise apply `## Recipe: repository table`.
9. Unless the person chose to add without cloning, run `git clone <remote> repos/<name>`.
10. Run the check. First run `command -v python3`.
    - When it succeeds (Python is present): run `python3 tools/check.py`. Fix findings only in `repos.json` and `REPOSITORIES.md`, the files this skill changed, and run it again. Stop running it when no finding names either file. If findings in other files remain, do not fix them; list them in the report.
    - When it fails (Python is missing): do not run the check. Remember the line `check not run: python3 missing` for the report.
11. Commit: run `git add repos.json REPOSITORIES.md`, then `git commit -m "chore(repos): add <name>"`.
12. Run `git pull --rebase origin <default>`. On conflicts follow `## Conflicts`. After the conflicts are resolved and the rebase has finished, go back to step 10 and run it again before step 13.
13. Push and open the merge request by `.agents/rules/merge-requests.md`, with title `Add repository <name>` and branch `repos-add-<name>`. Choose how to open it by `params.forge` in `.agents/kit.json`, the forge of this workspace. Do not use the `forge` you set in step 3; that one belongs to the new repository.
14. Report to the person:
    - the branch `repos-add-<name>`;
    - the merge request link, or the instruction to open it;
    - the clone result (`repos/<name>` cloned, or skipped without cloning);
    - as the last line, the check result, or `check not run: python3 missing`.

## Recipe: repository table
In `REPOSITORIES.md`, between `<!-- repos:begin -->` and `<!-- repos:end -->`, add one line directly above `<!-- repos:end -->`:

`| <name> | <forge> | <default_branch> | <roles joined with ", "> | <summary> |`

Change nothing else in the file.

Example. The person adds `payments-worker` with remote `git@gitlab.example.com:team/payments-worker.git`, forge `gitlab`, default branch `main`, roles `backend` and `qa`, summary `Consumes payment events and writes postings`.

`repos.json` after adding:

```json
{
  "repositories": [
    {
      "name": "payments-worker",
      "remote": "git@gitlab.example.com:team/payments-worker.git",
      "forge": "gitlab",
      "default_branch": "main",
      "roles": [
        "backend",
        "qa"
      ],
      "summary": "Consumes payment events and writes postings"
    }
  ]
}
```

Table block in `REPOSITORIES.md` before:

```
<!-- repos:begin -->
| Name | Forge | Default branch | Roles | Summary |
|---|---|---|---|---|
<!-- repos:end -->
```

Table block in `REPOSITORIES.md` after:

```
<!-- repos:begin -->
| Name | Forge | Default branch | Roles | Summary |
|---|---|---|---|---|
| payments-worker | gitlab | main | backend, qa | Consumes payment events and writes postings |
<!-- repos:end -->
```

## Conflicts
1. List conflicted files: `git diff --name-only --diff-filter=U`.
2. First check the list for any file other than `REPOSITORIES.md`, including `repos.json`. If there is one:
   - Run `git rebase --abort`.
   - For each such file, show the person both versions: `git diff <default>...repos-add-<name> -- <file>` and `git show origin/<default>:<file>`.
   - Stop and wait for the person. Do not touch `REPOSITORIES.md`.
3. Only when `REPOSITORIES.md` is the sole conflicted file:
   - Run `git checkout --ours -- REPOSITORIES.md`. During a rebase `--ours` is the default branch version.
   - Regenerate the table: if `command -v python3` succeeds, run `python3 tools/generate.py`; otherwise rebuild the table by hand as below.
   - Without Python, delete every row between the header separator `|---|---|---|---|---|` and `<!-- repos:end -->`. Then, for each entry of `repositories` in `repos.json`, from first to last, add its row directly above `<!-- repos:end -->` by `## Recipe: repository table`. Keep the two marker lines and the two header lines as they are. The table then has one row per entry in `repos.json` order.
   - Run `git add REPOSITORIES.md`.
   - Run `GIT_EDITOR=true git rebase --continue`.

## Without Python
1. In step 8, apply `## Recipe: repository table` instead of `python3 tools/generate.py`.
2. Skip `python3 tools/generate.py` and `python3 tools/check.py` everywhere, including `## Conflicts`.
3. End the report with the line:

check not run: python3 missing
