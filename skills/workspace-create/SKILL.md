---
name: workspace-create
description: Use when the workspace-builder agent must create a new team workspace from the kit
---
# Create a workspace

Create a new team workspace from the kit, describe it with the owner, fill its roles, repositories and domains by the workspace's own skills, and leave every file uncommitted.

## Collect

Ask one question per message and wait for the answer before the next one.

1. The absolute target path, for example `/Users/owner/work/abs-operations`. It must be missing or an empty directory; when `ls -A <target>` prints anything, ask for another path. Call it `<target>`.
2. `workspace_name`: lowercase name of the workspace, for example `abs-operations`.
3. `title`: human title, for example `ABS operations workspace`.
4. `forge`: take it from the host of the future workspace remote. A host containing `gitlab` gives `gitlab`, `github.com` gives `github`, a local path or no forge gives `git`. Ask the owner for the remote when it is not known yet.
5. `id_pattern`: Python regular expression for tracker task ids, used with fullmatch, for example `(DEMO|SPPP)-\d+`.
6. A real task id from the tracker. Check it against the pattern with `python3 -c 'import re, sys; print(bool(re.fullmatch(sys.argv[1], sys.argv[2])))' '<id_pattern>' '<id>'`. When it prints `False`, fix `id_pattern` with the owner and check again.
7. `tracker_url`: task link with `{id}` in place of the id, for example `https://tracker.example/i/{id}`. It must contain `{id}`; `workspace-kit` rejects it otherwise.

## Create

1. Run, with each value in single quotes:
   `~/.config/opencode/bin/workspace-kit create <target> --param workspace_name=... --param title=... --param forge=... --param id_pattern=... --param tracker_url=...`
2. On exit 2, show the owner the message, fix the value together and rerun.
3. Run `cd <target> && git init`.

Run every command below in `<target>`.

## Describe

1. Fill `README.md` with the owner. Keep the kit sections and add the team's specifics to them.
2. Fill every section of `docs/ARCHITECTURE.md` with the owner.
3. When the owner points to existing documents or code, send the `explorer` subagent to read them and bring back findings.
4. Refer to repositories, domains, stands and decisions by keys (`repo:<name>`, `domain:<name>`, `stand:<name>`, `adr:NNNN`). Never write home paths or stand URLs.
5. Pass the prose through the humanize skill before writing it.

## Roles

1. Show the owner the list from `ls .agents/roles/`.
2. For each role the team does not have, ask the owner to confirm, then delete its file.
3. For each missing role, follow the `role` kind of `.agents/skills/extend/SKILL.md`: steps 1 to 3, the `role` steps in `## Kinds`, then steps 6 and 7. Skip its branch, commit, rebase and push steps.

## Repositories and domains

1. For each starting repository, apply steps 2 to 9 of `.agents/skills/repos-add/SKILL.md`, except step 6: no branch.
2. For each domain, follow the `domain` kind of `.agents/skills/extend/SKILL.md`: steps 1 to 3, the `domain` steps in `## Kinds`, then steps 6 and 7. Skip its branch and commit steps.

## Verify

1. Run `python3 tools/generate.py`, then `python3 tools/check.py`.
2. Fix every finding and run both again until `check.py` prints nothing.
3. Show the owner the final output of both commands.

## Hand-off

Report to the owner:
- the path `<target>`;
- the kit `name` and `version` from `.agents/kit.json`;
- the parameters;
- the roles, repositories and domains;
- the final `check.py` output.

Say that every file is uncommitted and the repository has no commits. Run `git status` and show its output. Then print the commands the owner runs.

1. The first commit, always:
   - `git add -A && git commit -m "chore(workspace): create from kit <version>"`
2. When the owner gave a remote, tell them to create it as an empty repository first, because a push does not create it:
   - `gitlab`: create an empty project in the GitLab UI, or run `glab repo create <group>/<name> --private` when `glab` is available;
   - `github`: `gh repo create <owner>/<name> --private`.
3. When the owner gave a remote, print the commands to add it and push:
   - `git remote add origin <remote>`
   - `git push -u origin HEAD`

For `forge=git` with no remote, print only the first commit commands.

Never run any of these commands yourself, even when the owner asks; your permissions deny `git commit` and `git push`.
