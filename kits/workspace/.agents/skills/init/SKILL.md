---
name: init
description: Use when .local/ is missing in this workspace, or to re-check your repository selection and environment.
---
# Init

Running `init` again is safe: it keeps existing values and only adds what is missing.

## Steps
1. Go to the workspace root: the nearest directory, walking up from where you are, where `test -f .agents/kit.json` succeeds. Run every later command in that directory. When you reach `/` and no directory on the way had `.agents/kit.json`, stop, tell the person "This is not a workspace: no .agents/kit.json found in this directory or above", and do nothing else.
2. Choose the repositories to clone.
   - When `.local/repos.json` exists, keep it as it is, tell the person "Using your saved selection from .local/repos.json", and go to step 3.
   - Otherwise open `repos.json` and show the person every entry of `repositories`: its `name` and `summary`, or `planned` instead of the summary when the entry's `status` is `planned`.
   - Ask the person which of them to clone. Any subset is valid, `all` means every entry, and an empty answer means none. Never pick repositories yourself.
   - Check every name the person gives against the list. When a name is not in it, show the list again and ask again. Wait for a valid answer before you change anything.
3. Run `mkdir -p .local/drafts .local/handoffs`. When step 2 chose the repositories, also run `cp .agents/templates/local/repos.json .local/repos.json` and put the chosen names, in the order the person gave them, into the `repositories` list of `.local/repos.json`. Leave `add` and `skip` empty.
4. Open `.agents/env.schema.json`. Every entry of `variables` has `name`, `issued_by` and `how_to_get`.
   - Never open `.local/env` with a file editor, a read tool or a write tool. Reading it puts token values into your transcript, and a write tool can replace the whole file and lose values the person already filled in. Change `.local/env` only with the `printf` commands below, and find names in it only with the `grep ... | cut -d= -f1` command below, which prints names and never values.
   - Apostrophe rule: before you put `<issued_by>` or `<how_to_get>` into a `printf` command, replace every `'` inside them with `'\''`. For example `the team's admin` becomes `the team'\''s admin`.
   - To add the variable block for one variable, run `printf '%s\n' '# <name>: issued by <issued_by>; <how_to_get>' '<name>=' >> .local/env`. Use `>>`, never `>`, so existing lines stay.
   - If `.local/env` does not exist (`test -f .local/env` fails), run `printf '%s\n' '# Personal tokens for this workspace. Never commit, copy or print this file.' > .local/env` to create it with the header line. Then add the variable block for every variable, in schema order.
   - If `.local/env` exists, first run `test -z "$(tail -c1 .local/env)" || printf '\n' >> .local/env`. It prints nothing and adds a final newline when the file lacks one, so an append does not glue a new line onto the last value. Then run `grep -E '^[A-Za-z_][A-Za-z0-9_]*=' .local/env | cut -d= -f1` to list the names it already has. For every schema variable whose `name` is not in that output, add its variable block. Do not change any other line.
5. Set the `.local/env` permissions:
   - If step 4 just created `.local/env`, run `chmod 600 .local/env` and remember "created with 600". Skip the rest of this step.
   - Otherwise run `ls -l .local/env` and look at the first 10 characters. If they are not `-rw-------`, run `chmod 600 .local/env` and remember "permissions fixed (were <first 10 characters>)". If they are `-rw-------`, remember "already 600".
6. Build the repository list. Open `.local/repos.json` and take every name in its `repositories`. Open `repos.json` and take the entry with that `name` for each of them. Then, still in `.local/repos.json`, for every name in `add`, take the entry of `repos.json` with that `name`; when there is none, mark the name `failed` with "not in repos.json", do not clone it in step 7, and keep it for the step 9 report. Remove every entry whose `name` is in `skip`. When a `name` appears more than once, for example a name in `add` that `repositories` already includes, keep it once. Use each entry's `name`, `remote` and `status`. Mark every entry whose `status` is `planned` as `planned`: a planned repository does not exist yet and may have no `remote`, so it is never cloned.
7. For each repository in the list, one at a time:
   - When it is marked `planned`, run no command and go to the next repository.
   - Run `ls -d repos/<name>`. When it exists, mark it `present` and go to the next repository.
   - Otherwise run `GIT_TERMINAL_PROMPT=0 git clone <remote> repos/<name>`. `GIT_TERMINAL_PROMPT=0` makes a clone that needs a password fail instead of waiting for input.
   - When the command succeeds, mark it `cloned`. When it fails, mark it `failed` with the first output line that starts with `fatal:` or `error:` (the `Cloning into` line is not the error). When no line starts with `fatal:` or `error:`, use the last non-empty output line instead. Then continue with the next repository.
8. Collect the environment, one command each:
   - `git --version`.
   - `command -v glab`: output means `installed`, no output means `missing`.
   - `command -v gh`: output means `installed`, no output means `missing`.
   - `command -v python3`: output means `installed`, no output means `missing`.
   - `grep -E '^[A-Za-z_][A-Za-z0-9_]*=$' .local/env | cut -d= -f1`: the names of empty variables. This command prints only names. Never run `cat .local/env` and never print a value.
9. Report to the person, in this order: each repository from step 7 with `cloned`, `present`, `planned` or `failed` and its error, and each `add` name from step 6 that is not in `repos.json` as `<name>: failed: not in repos.json`; git version; glab, gh and python3 as `installed` or `missing`; empty variables by name, or `none`; the `.local/env` permissions note from step 5.
10. Do not create a branch and do not commit. `init` changes only `.local/` and `repos/`, which git ignores.

## Example
Schema `.agents/env.schema.json`:

```json
{
  "variables": [
    {"name": "TRACKER_TOKEN", "issued_by": "the tracker admin", "how_to_get": "request it in the access portal"}
  ]
}
```

The person chooses `payments` and `ledger`. New `.local/repos.json`:

```json
{
  "repositories": ["payments", "ledger"],
  "add": [],
  "skip": []
}
```

New `.local/env`:

```
# Personal tokens for this workspace. Never commit, copy or print this file.
# TRACKER_TOKEN: issued by the tracker admin; request it in the access portal
TRACKER_TOKEN=
```

Report:

```
Repositories:
- payments: cloned
- ledger: present
- billing-legacy: failed: fatal: could not read Username for 'https://git.example.com': terminal prompts disabled
git: git version 2.43.0
glab: installed
gh: missing
python3: installed
Empty variables: TRACKER_TOKEN
.local/env: created with 600
```

## Without Python
This skill needs no Python: every step uses shell commands and git. When `command -v python3` prints nothing, the report lists `python3: missing`.
