---
name: repo-kit-install
description: Use to install the repository kit named in a repos.json entry into your local clone of that repository, on a new branch, without committing.
---
# Install a repository kit

This skill writes into the clone `repos/<name>`, never into the workspace. In the clone it writes only under `.agents/`, the `.agent/` links it repairs in step 13, and the one `AGENTS.md` line of step 17. It never reads `.env` files, `.local/env` or secret values, never prints tokens, and never commits or pushes.

## Words used below
- `<ws>`: the workspace root, an absolute path (the output of `pwd` in step 1).
- `<name>`: the repository name in `repos.json`. `<clone>`: `<ws>/repos/<name>`.
- `<kind>`: `kit.kind` of the entry. `<kitdir>`: `<ws>/.agents/repo-kits/<kind>`. `<version>`: `version` in `<kitdir>/kit.json`. This is the workspace version of the kit; the workspace's own `.agents/kit.json` is a different file.
- `<branch>`: `repo-kit-<kind>-<version>`, for example `repo-kit-example-0.1.0`.
- `<default>`: `default_branch` of the entry.
- `<out>`: a temporary folder for the rendered kit, outside the clone and the workspace.
- `<base>`: the folder the clone's kit files are read from. It is `<clone>/.agent` while `<clone>/.agents` does not exist and `<clone>/.agent` does; otherwise it is `<clone>/.agents`. The kit path `.agents/<p>` is the clone file `<base>/<p>`.
- `<sha256>`: `shasum -a 256` when `command -v shasum` prints a path, otherwise `sha256sum`.
- States of a path: `absent`, `same`, `replaceable`, `edited`, `obsolete`, `removed-edited`, `foreign` (see `## Recipe: status`). Decisions for an `edited` path: `kit`, `local`, `raise`, exactly these words.

## Stops
Every stop prints its message and ends the skill. Before a stop in this table the skill has written nothing into the clone and created no branch. When `<out>` already exists, run `rm -rf <out>` before stopping. Only step 16 can stop after the clone changed; it prints the commands that discard the attempt.

| Stop | Message |
|---|---|
| S1 no digest tool | `Stop: python3, shasum and sha256sum are all missing, so file digests cannot be computed. Nothing was changed.` |
| S2 unknown repository | `Stop: repository <name> is not in repos.json. Nothing was changed.` |
| S3 invalid kit | `Stop: the kit of repository <name> in repos.json is invalid: <reason>. Fix the entry or the kit through a workspace merge request, then run repo-kit-install again. Nothing was changed.` |
| S4 render failed | `Stop: rendering kit <kind> for repository <name> failed: <reason>. Nothing was changed.` |
| S5 clone missing | `Stop: clone repos/<name> is missing. Clone it with the repos-sync skill, then run repo-kit-install again. Nothing was changed.` |
| S6 dirty clone | `Stop: clone repos/<name> has uncommitted changes. Commit or stash them yourself, then run repo-kit-install again. Nothing was changed.` |
| S7 not on the default branch | `Stop: clone repos/<name> is on branch <current>, not <default>. Switch it to <default> yourself, then run repo-kit-install again. Nothing was changed.` |
| S8 both folders | `Stop: repos/<name> has both .agent/ and .agents/. Which one should stay? Merge them by hand in a separate merge request, then run repo-kit-install again. Nothing was changed.` |
| S9 other kind | `Stop: repos/<name>/.agents/kit.json has kind <stamp kind>, but repos.json names kind <kind>. Changing the kind of a repository is the owner's decision. Nothing was changed.` |
| S10 workspace behind | `Stop: repos/<name>/.agents/kit.json has version <stamp version>, newer than version <version> of kit <kind> in this workspace. The workspace is behind: update it from its default branch, then run the skill again. Nothing was changed.` |
| S11 branch exists | `Stop: branch <branch> already exists in repos/<name>. Finish or delete it, then run repo-kit-install again. Nothing was changed.` |
| S12 value the recipe cannot render | `Stop: parameter <NAME> of repository <name> has the value <value>, which the recipe without python3 cannot render. Run repo-kit-install where python3 is available. Nothing was changed.` |
| S13 raise | `Stop: <path> got the decision raise. Change kit <kind> in .agents/repo-kits/<kind>/ through a workspace merge request, then run repo-kit-install again. Nothing was changed.` |

S8 also asks the maintainer the question in its message and waits for the answer; the skill does not merge the folders.

## Steps
1. Go to the workspace root: the nearest directory, walking up from where you are, where `test -f .agents/kit.json` succeeds. Run `pwd`; its output is `<ws>`. Use the workspace default branch after the merge request with the kit and the entry is merged. Start every command below with `cd <ws> && ` or `cd <clone> && ` as shown.
2. Find the tools. When `command -v python3` prints a path, Python is present. Otherwise, when neither `command -v shasum` nor `command -v sha256sum` prints a path, stop with S1. Without Python, follow `## Without Python` in every step that names a recipe.
3. Ask the person for `<name>` when they did not give it. Read `<ws>/repos.json` and find the entry of `repositories` whose `name` is `<name>`. With no such entry, stop with S2.
4. Check the entry's `kit`:
   - When the entry has no `kit`, stop with S3 and the reason `the entry has no kit`.
   - When `test -d <kitdir>` fails, stop with S3 and the reason `kit kind <kind> is not a folder under .agents/repo-kits/`.
   - Read `<kitdir>/kit.json`. `kit.params` of the entry must have exactly the names in `params` of `kit.json`, and every value must match the whole `pattern` of its parameter. Check a pattern with Python as `repos-add` step 2 does: `PATTERN='<pattern>' VALUE='<value>' python3 -c 'import os, re, sys; sys.exit(0 if re.fullmatch(os.environ["PATTERN"], os.environ["VALUE"]) else 1)'`; exit code 0 means it matches. Without Python run `printf '%s\n' '<value>' | grep -Ex -e '<pattern>'`; exit code 0 means the whole value matches. In both commands write each `'` inside the quotes as `'\''`. `grep -E` syntax covers the patterns kits use: character classes, `.`, `*`, `+`, `?`, `{m,n}`, `|` and groups. When a pattern uses syntax `grep -E` does not support, such as `\d`, `\w`, `\s`, `(?` or a lazy `*?`, compare by reading instead. A value with a line break never matches. On a missing name, an extra name or a value that does not match, stop with S3 and name the parameter in the reason.
   - Remember `<version>` from `version` in `<kitdir>/kit.json` and `<default>` from the entry.
5. Render the kit. Run `mktemp -d`; its output is `<out>`.
   - With Python: `cd <ws> && python3 tools/repo_kit.py render <name> <out>`. When it exits 2, stop with S4 and use its error line as the reason.
   - Without Python: apply `## Recipe: render`.
   `<out>/.agents/` now holds every kit file with the placeholders replaced.
6. Check the clone:
   - When `test -d <clone>/.git` fails, stop with S5.
   - When `cd <clone> && git status --porcelain` prints anything, stop with S6.
   - When `cd <clone> && git rev-parse --abbrev-ref HEAD` prints something other than `<default>`, stop with S7 with that output as `<current>`.
   - When both `test -d <clone>/.agent` and `test -d <clone>/.agents` succeed, stop with S8.
7. Check for a stamp. When `test -f <clone>/.agents/kit.json` succeeds, the repository already has a kit:
   - Read `kind` and `version` from it (`grep -m 1 '^  "kind": ' <clone>/.agents/kit.json` and `grep -m 1 '^  "version": ' <clone>/.agents/kit.json`).
   - When `kind` is not `<kind>`, stop with S9.
   - Compare the stamp `version` with `<version>` as three numbers, MAJOR first, then MINOR, then PATCH: `1.10.0` is newer than `1.9.0`. When the stamp version is newer, stop with S10. For example, stamp `1.2.0` and workspace kit `1.1.0` stop here.
   - Otherwise run `rm -rf <out>` and continue with `.agents/skills/repo-kit-update/SKILL.md` for the same `<name>` from its first step. Do not run the rest of this skill.
8. When `cd <clone> && git rev-parse --verify --quiet refs/heads/<branch>` or `cd <clone> && git rev-parse --verify --quiet refs/remotes/origin/<branch>` prints anything, stop with S11.
9. Compare the clone with the kit.
   - With Python: `cd <ws> && python3 tools/repo_kit.py status <name> repos/<name>`. When it exits 2, stop with S4 and use its error line as the reason.
   - Without Python: apply `## Recipe: status`.
   Each output line is `<state> <path>`. Before the folder move the paths still read `.agents/...`; the files behind them are under `<base>`. Without a stamp only `absent`, `same`, `edited` and `foreign` occur.
10. Collect decisions before writing anything. Show the person every `edited` path. For each path `.agents/<p>`, show the difference with `diff <base>/<p> <out>/.agents/<p>`. When `<base>` is `<clone>/.agent`, show it with the old links normalized instead: `LC_ALL=C sed 's#\.agent/#.agents/#g' <base>/<p> | diff - <out>/.agents/<p>`. When that `diff` prints nothing, the file differs only in `.agent/` links, which step 13 repairs: tell the person so and write down `kit` for the path without asking. Otherwise ask for one decision:
    - `kit`: the clone file is replaced by the kit file; the clone text is lost.
    - `local`: the clone text moves to `.agents/local/<p>`, and the kit file takes its place. When `test -e <base>/local/<p>` succeeds, that place is taken: tell the person and ask again for `kit` or `raise`.
    - `raise`: the kit itself must change first.
    Write the decisions down as `<decision> <path>`. When the person gives any other word, ask again. When there is no `edited` path, there is nothing to ask.
11. When any path got `raise`, run `rm -rf <out>` and stop with S13, naming that path. The clone has no new branch and no changed file.
12. Create the branch: `cd <clone> && git switch -c <branch>`. From here on the clone changes.
13. Move the folder and repair links, only when `<base>` is `<clone>/.agent`:
    1. `cd <clone> && git mv .agent .agents`. From now on `<base>` is `<clone>/.agents`.
    2. List the lines that still link to the old folder: `cd <clone> && grep -rnI --exclude-dir=.git --exclude='.env' --exclude='.env.*' '\.agent/' .`. Files named `.env` or `.env.*` are never read.
    3. In every listed line change `.agent/` to `.agents/` and change nothing else in the file. Remember the listed files outside `.agents/` for step 19.
    4. Run the `grep` of sub-step 2 again; it prints nothing.

    This step runs before step 14, so text that step 14 moves to `.agents/local/` under a `local` decision already has its `.agent/` links repaired.
14. Apply the decisions, for each `edited` path `.agents/<p>`:
    - `kit`: `cd <clone> && cp <out>/.agents/<p> .agents/<p>`.
    - `local`: `cd <clone> && mkdir -p "$(dirname .agents/local/<p>)" && mv .agents/<p> .agents/local/<p> && cp <out>/.agents/<p> .agents/<p>`.
15. Copy every `absent` path `.agents/<p>`: `cd <clone> && mkdir -p "$(dirname .agents/<p>)" && cp <out>/.agents/<p> .agents/<p>`. Leave `same` paths as they are and do not touch `foreign` paths.
16. Write the stamp.
    - With Python: `cd <ws> && python3 tools/repo_kit.py stamp <name> repos/<name>`.
    - Without Python: apply `## Recipe: stamp`.
    Then run step 9 again. Every kit path must now be `same`; `foreign` paths stay. When another state is left, stop: run `rm -rf <out>`, tell the person every line whose state is neither `same` nor `foreign`, and print these commands for the person to discard the attempt. Do not run them yourself:
    ```
    cd <clone> && git reset --hard && git clean -fd
    cd <clone> && git switch <default> && git branch -d <branch>
    ```
    The first line removes every uncommitted change of this attempt, staged or untracked, including the folder move. The second returns the clone to `<default>` and deletes `<branch>`. Step 6 made sure the clone had no uncommitted or untracked files before, so nothing else is lost.
17. Check the root `AGENTS.md` of the clone. The clone owns it; the kit never rewrites it.
    - `cd <clone> && grep -n '\.agents/AGENTS\.md' AGENTS.md` and `cd <clone> && grep -n '\.agents/local/' AGENTS.md`. A command that prints a line means that link exists.
    - When both print a line, change nothing.
    - Otherwise propose one line to the person, by what is missing, and add it as the last line of `AGENTS.md` only when the person agrees. When `AGENTS.md` does not exist, propose creating it with only that line.
      ```
      Both missing:            Agent instructions: [.agents/AGENTS.md](.agents/AGENTS.md). Repository-only rules and skills: [.agents/local/](.agents/local/).
      Only .agents/local/:     Repository-only rules and skills: [.agents/local/](.agents/local/).
      Only .agents/AGENTS.md:  Agent instructions: [.agents/AGENTS.md](.agents/AGENTS.md).
      ```
      Write only the text after the label and the spaces.
    - When the line links to `.agents/local/` and `test -d <clone>/.agents/local` fails, run `cd <clone> && mkdir -p .agents/local && touch .agents/local/.gitkeep` so the link resolves.
18. List every `foreign` path from step 9. These files belong to the repository: do not move or change them. For each `.agents/<p>` propose `git mv .agents/<p> .agents/local/<p>` to the person as a later change of their own.
19. Run `rm -rf <out>`. Print these commands for the person and do not run them. The repository's forge is `forge` of the entry, not the forge of this workspace:
    ```
    cd <clone>
    git add -A .agents <files changed in step 13 outside .agents> <AGENTS.md when step 17 changed it>
    git commit -m "chore(agents): install kit <kind> <version>"
    ```
    Then, by `forge`:
    - `gitlab`: `git push -u origin <branch> -o merge_request.create -o merge_request.title="Install kit <kind> <version>"`;
    - `github`: `git push -u origin <branch>`, then `gh pr create --fill`;
    - `git`: `git push -u origin <branch>`, then open the merge request by hand.
    Tell the person to adjust the commit message to the repository's own commit rules when it has them.
20. Report to the person: `<branch>`; the decisions; the files copied; the files with repaired links; the `AGENTS.md` line proposed or added; the `foreign` list; the printed commands. Never commit or push yourself.

## Example
Workspace entry `payments-worker` with kit `example` version `0.1.0` and `"params": {"SERVICE": "payments-worker"}`, forge `gitlab`, default branch `main`. The kit has `files/AGENTS.md`, `files/rules/example.md` and `files/skills/example/SKILL.md`. The clone `repos/payments-worker` is clean on `main` and has no `.agents/`, but has `.agent/AGENTS.md` equal to the rendered file, `.agent/rules/example.md` edited by hand, and `.agent/notes.md`. Its root `AGENTS.md` says `See .agent/AGENTS.md.`

- Step 9 prints:
  ```
  same .agents/AGENTS.md
  foreign .agents/notes.md
  edited .agents/rules/example.md
  absent .agents/skills/example/SKILL.md
  ```
- Step 10: the person decides `local .agents/rules/example.md`.
- Steps 12 to 16: branch `repo-kit-example-0.1.0`; `git mv .agent .agents`; root `AGENTS.md` becomes `See .agents/AGENTS.md.`; `.agents/rules/example.md` moves to `.agents/local/rules/example.md` and the kit file replaces it; `.agents/skills/example/SKILL.md` is copied; the stamp is written as in `## Recipe: stamp`. Step 9 again prints `same` for the three kit paths and `foreign .agents/notes.md`.
- Step 17: `AGENTS.md` links to `.agents/AGENTS.md` but not to `.agents/local/`; the proposed line is `Repository-only rules and skills: [.agents/local/](.agents/local/).` The folder exists after the `local` decision.
- Step 18 proposes `git mv .agents/notes.md .agents/local/notes.md`.
- Step 19 prints `git add -A .agents AGENTS.md`, the commit command and `git push -u origin repo-kit-example-0.1.0 -o merge_request.create -o merge_request.title="Install kit example 0.1.0"`.

## Recipe: render
Gives exactly the files `python3 tools/repo_kit.py render <name> <out>` writes.

1. Values. For every parameter in `params` of `<kitdir>/kit.json`, take its value from `kit.params` of the entry. The recipe replaces placeholders with `sed`, so it works only when no value contains `/`, `&`, `\`, `"`, `'`, `__`, a tab, a line break or another control character. For such a value stop with S12.
2. Placeholders. Run `cd <kitdir>/files && LC_ALL=C grep -rhoaE '__[A-Z][A-Z0-9_]*__' . | LC_ALL=C sort -u`. Every printed line must be `__<NAME>__` for a `<NAME>` in `params`. For any other line find the file with `cd <kitdir>/files && LC_ALL=C grep -rlaF '<line>' .` and stop with S4, reason `kit <kind>: files/<file> uses undeclared placeholder <NAME>`.
3. Files. Kit files are every file under `<kitdir>/files/` except files inside `__pycache__` folders. File names must not contain `"`, `\` or control characters; otherwise stop with S12 naming the file instead of a parameter. Copy each file `files/<p>` to `<out>/.agents/<p>`, with one `sed` expression `-e 's/__<NAME>__/<value>/g'` per parameter, in the order of `params`. `LC_ALL=C` makes `sed` treat the file as bytes, so line endings, a missing last newline and any encoding stay as they are:
   ```
   cd <kitdir>/files && LC_ALL=C find . -type f ! -path '*/__pycache__/*' | LC_ALL=C sort | while IFS= read -r p; do p=${p#./}; mkdir -p "<out>/.agents/$(dirname "$p")" && LC_ALL=C sed -e 's/__<NAME1>__/<value1>/g' -e 's/__<NAME2>__/<value2>/g' "$p" > "<out>/.agents/$p"; done
   ```

Example for kit `example` with the one parameter `SERVICE` = `payments-worker`, `<kitdir>` = `<ws>/.agents/repo-kits/example` and `<out>` = `/tmp/tmp.k3Jd9`:
```
cd <ws>/.agents/repo-kits/example/files && LC_ALL=C grep -rhoaE '__[A-Z][A-Z0-9_]*__' . | LC_ALL=C sort -u
```
prints only `__SERVICE__`, which is declared. Then:
```
cd <ws>/.agents/repo-kits/example/files && LC_ALL=C find . -type f ! -path '*/__pycache__/*' | LC_ALL=C sort | while IFS= read -r p; do p=${p#./}; mkdir -p "/tmp/tmp.k3Jd9/.agents/$(dirname "$p")" && LC_ALL=C sed -e 's/__SERVICE__/payments-worker/g' "$p" > "/tmp/tmp.k3Jd9/.agents/$p"; done
```
Result: `/tmp/tmp.k3Jd9/.agents/AGENTS.md`, `/tmp/tmp.k3Jd9/.agents/rules/example.md` and `/tmp/tmp.k3Jd9/.agents/skills/example/SKILL.md`. The first line of the rendered `AGENTS.md` is `# payments-worker`, and no rendered file contains `__SERVICE__`.

## Recipe: status
Gives exactly the lines `python3 tools/repo_kit.py status <name> repos/<name>` prints. It needs `<out>` from `## Recipe: render`. A digest is the first 64 characters of `<sha256>` run on the file as standard input: `shasum -a 256 < <file> | cut -c 1-64`. The stamp `<clone>/.agents/kit.json` is read as `## Recipe: stamp` writes it: one `files` entry per line, `    "<path>": "<digest>"`. The stamp digest of a path is `grep -F '    "<path>": "' <clone>/.agents/kit.json | head -n 1 | cut -d '"' -f 4`; it is empty when there is no stamp or no such line.

For every rendered path `.agents/<p>`, the clone file `F` is `<base>/<p>`:
- `absent`: `F` does not exist;
- `same`: `cmp -s <out>/.agents/<p> F` succeeds;
- `replaceable`: otherwise, when the stamp digest of the path is not empty and equals the digest of `F`;
- `edited`: otherwise.

For every path `P` in the stamp's `files` that is not rendered (`test -f <out>/P` fails), starts with `.agents/`, has no `..` segment, and whose clone file `<base>/<P without .agents/>` exists:
- `obsolete`: the stamp digest equals the digest of that file;
- `removed-edited`: otherwise.
A stamp path whose clone file is missing prints nothing.

For every file under `<base>`, as the path `.agents/<p>`: `foreign` when it is not rendered, not a key in the stamp's `files`, not `.agents/kit.json` and not under `.agents/local/`.

Sort all lines by path, byte by byte. The commands, with the three values set in the first line:
```
OUT=<out>; CLONE=<clone>; BASE=<base>
STAMP="$CLONE/.agents/kit.json"
{
  cd "$OUT" && LC_ALL=C find .agents -type f | while IFS= read -r P; do
    F="$BASE/${P#.agents/}"
    if [ ! -f "$F" ]; then echo "absent $P"
    elif cmp -s "$P" "$F"; then echo "same $P"
    else
      H=$( [ -f "$STAMP" ] && grep -F "    \"$P\": \"" "$STAMP" | head -n 1 | cut -d '"' -f 4 )
      D=$(shasum -a 256 < "$F" | cut -c 1-64)
      if [ -n "$H" ] && [ "$H" = "$D" ]; then echo "replaceable $P"; else echo "edited $P"; fi
    fi
  done
  [ -f "$STAMP" ] && sed -n '/^  "files": {/,/^  }/p' "$STAMP" | grep '^    "' | while IFS= read -r L; do
    P=$(printf '%s\n' "$L" | cut -d '"' -f 2); H=$(printf '%s\n' "$L" | cut -d '"' -f 4)
    case "$P" in .agents/*) ;; *) continue ;; esac
    case "/$P/" in */../*) continue ;; esac
    [ -f "$OUT/$P" ] && continue
    F="$BASE/${P#.agents/}"
    [ -f "$F" ] || continue
    if [ "$(shasum -a 256 < "$F" | cut -c 1-64)" = "$H" ]; then echo "obsolete $P"; else echo "removed-edited $P"; fi
  done
  [ -d "$BASE" ] && cd "$BASE" && LC_ALL=C find . -type f | while IFS= read -r p; do
    P=".agents/${p#./}"
    case "$P" in .agents/kit.json|.agents/local/*) continue ;; esac
    [ -f "$OUT/$P" ] && continue
    [ -f "$STAMP" ] && grep -qF "    \"$P\": \"" "$STAMP" && continue
    echo "foreign $P"
  done
} | LC_ALL=C sort -k 2
```
Replace both `shasum -a 256` with `sha256sum` when `shasum` is missing. The block runs the same in `sh`, `bash` and `zsh`.

Example: the clone of `## Example` before the move, so `BASE=<ws>/repos/payments-worker/.agent`, no stamp, `<out>` from `## Recipe: render`. `.agent/AGENTS.md` equals the rendered file, `.agent/rules/example.md` differs, `.agent/skills/` does not exist, and `.agent/notes.md` is not a kit file. The lines are:
```
same .agents/AGENTS.md
foreign .agents/notes.md
edited .agents/rules/example.md
absent .agents/skills/example/SKILL.md
```
With a stamp holding the digest of the current `.agent/rules/example.md`, that line would be `replaceable .agents/rules/example.md` instead.

## Recipe: stamp
Gives exactly the bytes of `<clone>/.agents/kit.json` that `python3 tools/repo_kit.py stamp <name> repos/<name>` writes. It needs `<out>` from `## Recipe: render`, and the value rules of that recipe hold here too.

The file has these lines, each ending with a line break, and nothing else:
1. `{`
2. `  "kind": "<kind>",`
3. `  "version": "<version>",`
4. `  "params": {`
5. one line per parameter, in the order of `params` in `<kitdir>/kit.json`: `    "<NAME>": "<value>"`, with a comma after every line except the last;
6. `  },`
7. `  "files": {`
8. one line per rendered file, sorted by path byte by byte: `    ".agents/<p>": "<digest of <out>/.agents/<p>>"`, with a comma after every line except the last;
9. `  }`
10. `}`

A kit without parameters writes the single line `  "params": {},` instead of lines 4 to 6; a kit without files writes `  "files": {}` instead of lines 7 to 9. This is how the tool prints an empty object.

The commands, with one argument per parameter line in the second `printf`. For a kit without parameters that line is `printf '%s\n' '  "params": {},'` instead. The files part needs no change: it prints `  "files": {}` when `<out>` has no `.agents/` files.
```
mkdir -p <clone>/.agents && cd <out> && {
  printf '%s\n' '{' '  "kind": "<kind>",' '  "version": "<version>",'
  printf '%s\n' '  "params": {' '    "<NAME1>": "<value1>",' '    "<NAME2>": "<value2>"' '  },'
  FILES=$( [ -d .agents ] && LC_ALL=C find .agents -type f | LC_ALL=C sort | while IFS= read -r f; do printf '    "%s": "%s",\n' "$f" "$(shasum -a 256 < "$f" | cut -c 1-64)"; done | LC_ALL=C sed '$ s/,$//' )
  if [ -n "$FILES" ]; then printf '%s\n' '  "files": {' "$FILES" '  }'; else printf '%s\n' '  "files": {}'; fi
  printf '%s\n' '}'
} > <clone>/.agents/kit.json
```
Use `sha256sum` instead of `shasum -a 256` when `shasum` is missing.

Example for `## Example`, `<out>` = `/tmp/tmp.k3Jd9`:
```
mkdir -p <ws>/repos/payments-worker/.agents && cd /tmp/tmp.k3Jd9 && {
  printf '%s\n' '{' '  "kind": "example",' '  "version": "0.1.0",'
  printf '%s\n' '  "params": {' '    "SERVICE": "payments-worker"' '  },'
  FILES=$( [ -d .agents ] && LC_ALL=C find .agents -type f | LC_ALL=C sort | while IFS= read -r f; do printf '    "%s": "%s",\n' "$f" "$(shasum -a 256 < "$f" | cut -c 1-64)"; done | LC_ALL=C sed '$ s/,$//' )
  if [ -n "$FILES" ]; then printf '%s\n' '  "files": {' "$FILES" '  }'; else printf '%s\n' '  "files": {}'; fi
  printf '%s\n' '}'
} > <ws>/repos/payments-worker/.agents/kit.json
```
The written `repos/payments-worker/.agents/kit.json`, with a line break after the last `}`:
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

## Without Python
1. Step 2: without `python3`, one of `shasum` or `sha256sum` must exist; with neither, stop with S1.
2. Step 4: check each value against its `pattern` with the `grep -Ex` command of step 4, or by reading when the pattern uses syntax `grep -E` does not support; the whole value must match.
3. Step 5: apply `## Recipe: render` instead of `tools/repo_kit.py render`.
4. Steps 9 and 16: apply `## Recipe: status` instead of `tools/repo_kit.py status`.
5. Step 16: apply `## Recipe: stamp` instead of `tools/repo_kit.py stamp`.
6. The skill changes no workspace file, so there is no workspace check to run.
