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
   - `summary`: ask for one line.
   - `kit` (optional): only when the person names a repository kit kind. The allowed kinds are the folder names printed by `ls .agents/repo-kits/`. When that folder is missing or empty, tell the person that this workspace has no repository kits, and the entry gets no `kit`. When the person names a kind that is not in the list, tell them the allowed kinds and ask again. With a kind, collect its parameters:
     1. Read `.agents/repo-kits/<kind>/kit.json`. Its `params` object lists every parameter, each with `description` and `pattern`.
     2. For every parameter, in the order of `params`, show the person its name, `description` and `pattern`, and ask for the value.
     3. The whole value must match `pattern`, not only a part of it: `ops` matches `[a-z]+`, `ops-1` does not. When `command -v python3` succeeds, check with `PATTERN='<pattern>' VALUE='<value>' python3 -c 'import os, re, sys; sys.exit(0 if re.fullmatch(os.environ["PATTERN"], os.environ["VALUE"]) else 1)'`; exit code 0 means it matches. The pattern and value travel in environment variables so the Python code never contains them. Inside the single-quoted shell values write each `'` as `'\''`; for example the value `it's` becomes `VALUE='it'\''s'`. On a value that does not match, tell the person the pattern and ask for that parameter again.
     4. Do not install the kit into the clone in this skill. Installation is the `repo-kit-install` skill, run after this merge request is merged.
   - Never invent a summary, a kit kind or kit parameter values. If the person gives no summary, ask again. The kit kind is optional: when the person names none, the entry gets no `kit` and you do not ask for one again.
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
7. Edit `repos.json`: append the entry as the last element of `repositories`. Keys go in the order `name`, `remote`, `forge`, `default_branch`, `summary`, and `kit` last when the person named a kit. `kit` is an object with the keys `kind` and `params`, in this order; `params` holds every parameter collected in step 2 in the order of the kit's `params`. Use two-space indentation and put each list item and each object key on its own line, exactly as in the example below. When the list already has entries, add a comma after the closing `}` of the previous last entry. Inside every JSON string value write `"` as `\"` and `\` as `\\`; for example the summary `Reads "raw" C:\data` becomes `"summary": "Reads \"raw\" C:\\data"`.
8. If `command -v python3` succeeds, run `python3 tools/generate.py`. Otherwise apply `## Recipe: repository table`.
9. Unless the person chose to add without cloning, run `git clone <remote> repos/<name>`. Do not add or change any file in the clone, including `.agents/`.
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
    - when the entry has `kit`: the kit kind is recorded but not installed; after the merge request is merged, install it with the `repo-kit-install` skill;
    - as the last line, the check result, or `check not run: python3 missing`.

## Recipe: repository table
In `REPOSITORIES.md`, between `<!-- repos:begin -->` and `<!-- repos:end -->`, add one line directly above `<!-- repos:end -->`:

`| <name> | <forge> | <default_branch> | <kit.kind> | <summary> |`

When the entry has no `kit`, the `<kit.kind>` cell is empty: write the two spaces around it, `| payments-worker | gitlab | main |  | Consumes`. Only `kit.kind` goes into the table; never write kit parameters there.

Change nothing else in the file.

Example. The person adds two repositories, one after the other:
- `payments-worker` with remote `git@gitlab.example.com:team/payments-worker.git`, forge `gitlab`, default branch `main`, summary `Consumes payment events and writes postings`, no kit;
- `abs-operations` with remote `git@gitlab.example.com:team/abs-operations.git`, forge `gitlab`, default branch `master`, summary `Operations micro frontend`, kit `mfe`. The `mfe` kit declares `MFE`, `BFF` and `PREFIX` in this order; the person gives `abs-operations`, `abs-operations-bff` and `ops`.

`repos.json` after adding both:

```json
{
  "repositories": [
    {
      "name": "payments-worker",
      "remote": "git@gitlab.example.com:team/payments-worker.git",
      "forge": "gitlab",
      "default_branch": "main",
      "summary": "Consumes payment events and writes postings"
    },
    {
      "name": "abs-operations",
      "remote": "git@gitlab.example.com:team/abs-operations.git",
      "forge": "gitlab",
      "default_branch": "master",
      "summary": "Operations micro frontend",
      "kit": {
        "kind": "mfe",
        "params": {
          "MFE": "abs-operations",
          "BFF": "abs-operations-bff",
          "PREFIX": "ops"
        }
      }
    }
  ]
}
```

Table block in `REPOSITORIES.md` before:

```
<!-- repos:begin -->
| Name | Forge | Default branch | Kit | Summary |
|---|---|---|---|---|
<!-- repos:end -->
```

Table block in `REPOSITORIES.md` after:

```
<!-- repos:begin -->
| Name | Forge | Default branch | Kit | Summary |
|---|---|---|---|---|
| payments-worker | gitlab | main |  | Consumes payment events and writes postings |
| abs-operations | gitlab | master | mfe | Operations micro frontend |
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
   - Without Python, replace the two header lines below `<!-- repos:begin -->` with `| Name | Forge | Default branch | Kit | Summary |` and `|---|---|---|---|---|`, and delete every row between that separator and `<!-- repos:end -->`. Then, for each entry of `repositories` in `repos.json`, from first to last, add its row directly above `<!-- repos:end -->` by `## Recipe: repository table`, with the `Kit` cell from the entry's `kit.kind` or empty. Keep the two marker lines. The table then has one row per entry in `repos.json` order.
   - Run `git add REPOSITORIES.md`.
   - Run `GIT_EDITOR=true git rebase --continue`.

## Without Python
1. In step 8, apply `## Recipe: repository table` instead of `python3 tools/generate.py`.
2. In step 2, check each kit parameter value against its `pattern` with `printf '%s\n' '<value>' | grep -Ex -e '<pattern>'`; exit code 0 means the whole value matches. Write each `'` inside the quotes as `'\''`. When a pattern uses syntax `grep -E` does not support, such as `\d`, `\w`, `\s`, `(?` or a lazy `*?`, compare by reading instead. A value with a line break never matches.
3. Skip `python3 tools/generate.py` and `python3 tools/check.py` everywhere, including `## Conflicts`.
4. End the report with the line:

check not run: python3 missing
