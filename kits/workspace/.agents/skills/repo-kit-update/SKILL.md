---
name: repo-kit-update
description: Use to update the .agents/ folder of your local clone of a repository to the current version of its repository kit, on a new branch, without committing.
---
# Update a repository kit

This skill writes into the clone `repos/<name>`, never into the workspace. In the clone it writes only under `.agents/`. It never reads `.env` files, `.local/env` or secret values, never prints tokens, and never commits or pushes.

## Words used below
- `<ws>`: the workspace root, an absolute path (the output of `pwd` in step 1).
- `<name>`: the repository name in `repos.json`. `<clone>`: `<ws>/repos/<name>`.
- `<kind>`: `kit.kind` of the entry. `<kitdir>`: `<ws>/.agents/repo-kits/<kind>`. `<version>`: `version` in `<kitdir>/kit.json`. This is the workspace version of the kit; the workspace's own `.agents/kit.json` is a different file.
- `<branch>`: `repo-kit-<kind>-<version>`, for example `repo-kit-example-0.2.0`.
- `<default>`: `default_branch` of the entry.
- `<out>`: a temporary folder for the rendered kit, outside the clone and the workspace: the literal output of `mktemp -d` in step 5, written into every later command.
- `<base>`: the folder the clone's kit files are read from. An update always has `<clone>/.agents`, so `<base>` is `<clone>/.agents`. The kit path `.agents/<p>` is the clone file `<base>/<p>`.
- `<stamp version>`: `version` in `<clone>/.agents/kit.json`.
- States of a path: `absent`, `same`, `replaceable`, `edited`, `obsolete`, `removed-edited`, `foreign` (see `## Recipe: status` in `.agents/skills/repo-kit-install/SKILL.md`). Decisions for an `edited` or `removed-edited` path: `kit`, `local`, `raise`, exactly these words.

## Stops
Every stop prints its message and ends the skill. Every check of this table runs before step 13, so before a stop in this table the skill has written nothing into the clone, created no branch and switched no branch. When `<out>` already exists, run `rm -rf <out>` before stopping. Only step 15 can stop after the clone changed; it prints the commands that discard the attempt.

| Stop | Message |
|---|---|
| U1 no digest tool | `Stop: python3, shasum and sha256sum are all missing, so file digests cannot be computed. Nothing was changed.` |
| U2 unknown repository | `Stop: repository <name> is not in repos.json. Nothing was changed.` |
| U3 invalid kit | `Stop: the kit of repository <name> in repos.json is invalid: <reason>. Fix the entry or the kit through a workspace merge request, then run repo-kit-update again. Nothing was changed.` |
| U4 render failed | `Stop: rendering kit <kind> for repository <name> failed: <reason>. Nothing was changed.` |
| U5 clone missing | `Stop: clone repos/<name> is missing. Clone it with the repos-sync skill, then run repo-kit-update again. Nothing was changed.` |
| U6 dirty clone | `Stop: clone repos/<name> has uncommitted changes. Commit or stash them yourself, then run repo-kit-update again. Nothing was changed.` |
| U7 not on the default branch | `Stop: clone repos/<name> is on branch <current>, not <default>. Switch it to <default> and pull it yourself, then run repo-kit-update again. Nothing was changed.` |
| U8 both folders | `Stop: repos/<name> has both .agent/ and .agents/. Which one should stay? Merge them by hand in a separate merge request, then run repo-kit-update again. Nothing was changed.` |
| U9 invalid stamp | `Stop: repos/<name>/.agents/kit.json is not a stamp with kind, version and params. Ask the maintainer to repair it. Nothing was changed.` |
| U10 other kind | `Stop: repos/<name>/.agents/kit.json has kind <stamp kind>, but repos.json names kind <kind>. Changing the kind of a repository is the owner's decision. Nothing was changed.` |
| U11 workspace behind | `Stop: repos/<name>/.agents/kit.json has version <stamp version>, newer than version <version> of kit <kind> in this workspace. The workspace is behind: update it from its default branch, then run the skill again. Nothing was changed.` |
| U12 branch exists | `Stop: branch <branch> already exists in repos/<name>. Finish or delete it, then run repo-kit-update again. Nothing was changed.` |
| U13 value the recipe cannot render | `Stop: parameter <NAME> of repository <name> has the value <value>, which the recipe without python3 cannot render. Run repo-kit-update where python3 is available. Nothing was changed.` |
| U14 raise | `Stop: <path> got the decision raise. Change kit <kind> in .agents/repo-kits/<kind>/ through a workspace merge request. Raise the kit version in the same merge request, because the update compares versions, then run repo-kit-update again. Nothing was changed.` |

U8 also asks the maintainer the question in its message and waits for the answer; the skill does not merge the folders.

## Steps
1. Go to the workspace root: the nearest directory, walking up from where you are, where `test -f .agents/kit.json` succeeds. Run `pwd`; its output is `<ws>`. Start every command below with `cd <ws> && ` or `cd <clone> && ` as shown.
2. Find the tools. When `command -v python3` prints a path, Python is present. Otherwise, when neither `command -v shasum` nor `command -v sha256sum` prints a path, stop with U1. Without Python, follow `## Without Python` in every step that names a recipe.
3. Ask the person for `<name>` when they did not give it. Read `<ws>/repos.json` and find the entry of `repositories` whose `name` is `<name>`. With no such entry, stop with U2.
4. Check the entry's `kit`:
   - When the entry has no `kit`, stop with U3 and the reason `the entry has no kit`.
   - When `test -d <kitdir>` fails, stop with U3 and the reason `kit kind <kind> is not a folder under .agents/repo-kits/`.
   - Read `<kitdir>/kit.json`. `kit.params` of the entry must have exactly the names in `params` of `kit.json`, and every value must match the whole `pattern` of its parameter. Check a pattern with `PATTERN='<pattern>' VALUE='<value>' python3 -c 'import os, re, sys; sys.exit(0 if re.fullmatch(os.environ["PATTERN"], os.environ["VALUE"]) else 1)'`; exit code 0 means it matches. Without Python run `printf '%s\n' '<value>' | grep -Ex -e '<pattern>'`; exit code 0 means the whole value matches. In both commands write each `'` inside the quotes as `'\''`. `grep -E` syntax covers the patterns kits use: character classes, `.`, `*`, `+`, `?`, `{m,n}`, `|` and groups. When a pattern uses syntax `grep -E` does not support, such as `\d`, `\w`, `\s`, `(?` or a lazy `*?`, compare by reading instead. A value with a line break never matches. On a missing name, an extra name or a value that does not match, stop with U3 and name the parameter in the reason.
   - Remember `<version>` from `version` in `<kitdir>/kit.json` and `<default>` from the entry.
5. Render the kit. Run `mktemp -d`; its output is `<out>`. Write that path itself into every later command; do not keep it in a shell variable, because a later command may run in a new shell.
   - With Python: `cd <ws> && python3 tools/repo_kit.py render <name> <out>`. When it exits 2, stop with U4 and use its error line as the reason.
   - Without Python: apply `## Recipe: render` as `## Without Python` says.
   `<out>/.agents/` now holds every kit file with the placeholders replaced.
6. Check the clone:
   - When `test -d <clone>/.git` fails, stop with U5.
   - When `cd <clone> && git status --porcelain` prints anything, stop with U6.
   - When `cd <clone> && git rev-parse --abbrev-ref HEAD` prints something other than `<default>`, stop with U7 with that output as `<current>`. Do not switch or pull; the person does that.
   - When both `test -d <clone>/.agent` and `test -d <clone>/.agents` succeed, stop with U8.
7. Check the stamp.
   - When `test -f <clone>/.agents/kit.json` fails, there is no stamp: run `rm -rf <out>`, tell the person `repos/<name> has no kit stamp; continuing as repo-kit-install.`, and continue with `.agents/skills/repo-kit-install/SKILL.md` for the same `<name>` from its first step. Do not run the rest of this skill.
   - Read `kind`, `version` and `params` from the stamp with `grep -m 1 '^  "kind": ' <clone>/.agents/kit.json`, `grep -m 1 '^  "version": ' <clone>/.agents/kit.json` and `grep -m 1 '^  "params": ' <clone>/.agents/kit.json`. When one of them prints nothing, stop with U9. The parameter values are the `    "<NAME>": "<value>"` lines that `sed -n '/^  "params": {$/,/^  },$/p' <clone>/.agents/kit.json` prints; the line `  "params": {},` means the stamp has no parameters.
   - When `kind` is not `<kind>`, stop with U10.
   - Compare `<stamp version>` with `<version>` as three numbers, MAJOR first, then MINOR, then PATCH: `1.10.0` is newer than `1.9.0`. When the stamp version is newer, stop with U11. For example, stamp `1.2.0` and workspace kit `1.1.0` stop here, and the clone is unchanged.
   - When `<stamp version>` equals `<version>` and the stamp `params` have the same names with the same values as `kit.params` of the entry (order does not matter), run `rm -rf <out>`, tell the person `repos/<name> is up to date with kit <kind> <version>; nothing to do.` and end the skill.
8. When `cd <clone> && git rev-parse --verify --quiet refs/heads/<branch>` or `cd <clone> && git rev-parse --verify --quiet refs/remotes/origin/<branch>` prints anything, stop with U12.
9. Compare the clone with the kit.
   - With Python: `cd <ws> && python3 tools/repo_kit.py status <name> repos/<name>`. When it exits 2, stop with U4 and use its error line as the reason.
   - Without Python: apply `## Recipe: status` as `## Without Python` says.
   Each output line is `<state> <path>`; for the path `.agents/<p>` the clone file is `<base>/<p>`. Write the list down. The states mean:
   - `same`: the clone file equals the kit file; nothing to do.
   - `absent`: the kit has the file and the clone does not; it will be copied.
   - `replaceable`: the kit changed the file and the clone file is untouched since the stamp; it will be replaced.
   - `obsolete`: the kit no longer has the file and the clone file is untouched; it will be deleted.
   - `edited`: the clone file was changed in the repository and differs from the kit; it needs a decision.
   - `removed-edited`: the kit no longer has the file and the clone file was changed in the repository; it needs a decision.
   - `foreign`: a repository file inside `.agents/` that the kit never had; it is not touched.
10. Collect decisions before writing anything. Show the person every `edited` and `removed-edited` path. For each `.agents/<p>`, one at a time:
    - For `edited`, show the difference with `diff <base>/<p> <out>/.agents/<p>`. For `removed-edited`, tell the person the kit no longer has this file and show it with `cat <base>/<p>`.
    - Ask for one decision:
      - `kit`: for `edited` the kit file replaces the clone file; for `removed-edited` the file is deleted. The clone text is lost.
      - `local`: the clone text moves to `.agents/local/<p>`; for `edited` the kit file then takes its place. When `test -e <base>/local/<p>` succeeds, that place is taken: tell the person and ask again for `kit` or `raise`.
      - `raise`: the kit itself must change first.
    - Write the decisions down as `<decision> <path>`. When the person gives any other word, ask again. When there is no such path, there is nothing to ask.
11. When any path got `raise`, run `rm -rf <out>` and stop with U14, naming that path. The clone has no new branch and no changed file.
12. List every `foreign` path from step 9 for the report. Do not move or change them.
13. Create the branch: `cd <clone> && git switch -c <branch>`. From here on the clone changes.
14. Write the kit files, in this order, for each path `.agents/<p>`:
    1. Each `replaceable` path: `cd <clone> && cp <out>/.agents/<p> .agents/<p>`.
    2. Each `absent` path: `cd <clone> && mkdir -p "$(dirname .agents/<p>)" && cp <out>/.agents/<p> .agents/<p>`.
    3. Each `obsolete` path: `cd <clone> && rm .agents/<p>`.
    4. Each decision:
       - `kit` on `edited`: `cd <clone> && cp <out>/.agents/<p> .agents/<p>`.
       - `kit` on `removed-edited`: `cd <clone> && rm .agents/<p>`.
       - `local` on `edited`: `cd <clone> && mkdir -p "$(dirname .agents/local/<p>)" && mv .agents/<p> .agents/local/<p> && cp <out>/.agents/<p> .agents/<p>`.
       - `local` on `removed-edited`: `cd <clone> && mkdir -p "$(dirname .agents/local/<p>)" && mv .agents/<p> .agents/local/<p>`.
    Leave `same` paths as they are and do not touch `foreign` paths.
15. Write the new stamp.
    - With Python: `cd <ws> && python3 tools/repo_kit.py stamp <name> repos/<name>`.
    - Without Python: apply `## Recipe: stamp` as `## Without Python` says.
    Then run step 9 again. Every kit path must now be `same`; `foreign` paths stay. When another state is left, stop: run `rm -rf <out>`, tell the person every line whose state is neither `same` nor `foreign`, and print these commands for the person to discard the attempt. Do not run them yourself:
    ```
    cd <clone> && git reset --hard && git clean -fd
    cd <clone> && git switch <default> && git branch -d <branch>
    ```
    The first line removes every uncommitted change of this attempt, staged or untracked. The second returns the clone to `<default>` and deletes `<branch>`. Step 6 made sure the clone had no uncommitted or untracked files before, so nothing else is lost.
16. Run `rm -rf <out>`. Print these commands for the person and do not run them. The repository's forge is `forge` of the entry, not the forge of this workspace:
    ```
    cd <clone>
    git add -A .agents
    git commit -m "chore(agents): update kit <kind> to <version>"
    ```
    Then, by `forge`:
    - `gitlab`: `git push -u origin <branch> -o merge_request.create -o merge_request.title="Update kit <kind> to <version>"`;
    - `github`: `git push -u origin <branch>`, then `gh pr create --fill`;
    - `git`: `git push -u origin <branch>`, then open the merge request by hand.
    Tell the person to adjust the commit message to the repository's own commit rules when it has them.
17. Report to the person: `<branch>` and the version change `<stamp version>` to `<version>`; the replaced, copied and deleted paths; the decisions; each `foreign` path with the proposal `git mv .agents/<p> .agents/local/<p>` as a later change of their own; the printed commands. Never commit or push yourself.

## Example
Workspace entry `payments-worker` with forge `gitlab`, default branch `main` and `"kit": {"kind": "example", "params": {"SERVICE": "payments-worker"}}`. The clone `repos/payments-worker` is clean on `main` and has kit `example` version `0.1.0`. The team changed `files/rules/example.md` and `files/skills/example/SKILL.md` and raised the kit to `0.2.0`. In the clone a maintainer had changed step 1 of `.agents/skills/example/SKILL.md`.

Stamp `repos/payments-worker/.agents/kit.json` before:

```json
{
  "kind": "example",
  "version": "0.1.0",
  "params": {
    "SERVICE": "payments-worker"
  },
  "files": {
    ".agents/AGENTS.md": "27ff1ccb6beb7cb7b873f3d9c173ff18e74fbb30572c299987bb09055b1d77b4",
    ".agents/rules/example.md": "e31c19605d14f680052c8bb7550bd2132105a0eacda42e9db2a11809743af543",
    ".agents/skills/example/SKILL.md": "777eb69778449f5ffa502dafaf1fee70914792262e0448e43a312adce57bd70b"
  }
}
```

- Step 5: `mktemp -d` prints `/tmp/tmp.Q7r2m`, so `<out>` is `/tmp/tmp.Q7r2m`.
- Step 7: the stamp version `0.1.0` is older than `0.2.0`, so the update goes on. Step 8 finds no branch `repo-kit-example-0.2.0`.
- Step 9 prints:
  ```
  same .agents/AGENTS.md
  replaceable .agents/rules/example.md
  edited .agents/skills/example/SKILL.md
  ```
  The clone `rules/example.md` still has the stamp digest `e31c1960...`, so it is `replaceable`. The clone `SKILL.md` has digest `6b9e2f06...`, which is neither the stamp digest nor the digest of the kit file, so it is `edited`.
- Step 10: the person decides `local .agents/skills/example/SKILL.md`.
- Steps 13 to 15 run, with `<ws>` the workspace root:
  ```
  cd <ws>/repos/payments-worker && git switch -c repo-kit-example-0.2.0
  cd <ws>/repos/payments-worker && cp /tmp/tmp.Q7r2m/.agents/rules/example.md .agents/rules/example.md
  cd <ws>/repos/payments-worker && mkdir -p "$(dirname .agents/local/skills/example/SKILL.md)" && mv .agents/skills/example/SKILL.md .agents/local/skills/example/SKILL.md && cp /tmp/tmp.Q7r2m/.agents/skills/example/SKILL.md .agents/skills/example/SKILL.md
  cd <ws> && python3 tools/repo_kit.py stamp payments-worker repos/payments-worker
  ```
- Stamp after:
  ```json
  {
    "kind": "example",
    "version": "0.2.0",
    "params": {
      "SERVICE": "payments-worker"
    },
    "files": {
      ".agents/AGENTS.md": "27ff1ccb6beb7cb7b873f3d9c173ff18e74fbb30572c299987bb09055b1d77b4",
      ".agents/rules/example.md": "0e96d5109adecd0063c090858b2b121986c1fde4f2cfa3b2acd1299f35cc181b",
      ".agents/skills/example/SKILL.md": "d863c733393931e28bb36078a2255078b9f500dd3ec4124a060d51d81d64d686"
    }
  }
  ```
- Step 9 again prints `same` for all three paths. The maintainer's text is in `.agents/local/skills/example/SKILL.md`.
- Step 16 runs `rm -rf /tmp/tmp.Q7r2m` and prints `git add -A .agents`, `git commit -m "chore(agents): update kit example to 0.2.0"` and `git push -u origin repo-kit-example-0.2.0 -o merge_request.create -o merge_request.title="Update kit example to 0.2.0"`.

## Without Python
The recipes live in `.agents/skills/repo-kit-install/SKILL.md`; follow them there and do not copy them here. They use the words of that skill, which mean here:
- `<ws>`, `<name>`, `<clone>` = `<ws>/repos/<name>`, `<kind>`, `<kitdir>` = `<ws>/.agents/repo-kits/<kind>` and `<version>`: as in `## Words used below`.
- `<out>`: the literal `mktemp -d` output of step 5.
- `<base>`: `<clone>/.agents`.
- Their stop S4 is U4 here, and their stop S12 is U13 here, with the messages of `## Stops` of this skill.

1. Step 2: without `python3`, one of `shasum` or `sha256sum` must exist; with neither, stop with U1.
2. Step 4: check each value against its `pattern` with the `grep -Ex` command of step 4, or by reading when the pattern uses syntax `grep -E` does not support; the whole value must match, not only a part of it.
3. Step 5: apply `## Recipe: render` instead of `tools/repo_kit.py render`. When a value contains a character that recipe cannot render, stop with U13. When a kit file uses an undeclared placeholder, stop with U4 and the reason `kit <kind>: files/<file> uses undeclared placeholder <NAME>`.
4. Steps 9 and 15: apply `## Recipe: status` instead of `tools/repo_kit.py status`, with digests from `shasum -a 256` or `sha256sum`.
5. Step 15: apply `## Recipe: stamp` instead of `tools/repo_kit.py stamp`.
6. The skill changes no workspace file, so there is no workspace check to run.
