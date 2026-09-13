---
name: extend
description: Use to add an agent, skill, rule, role, domain, stand, environment variable or repository to this workspace by its templates, through a merge request.
---
# Extend the workspace

## Steps
1. Go to the workspace root: the nearest directory, walking up from where you are, where `test -f .agents/kit.json` succeeds. Run every command below from there.
2. Ask the person for the kind and the name, and wait for both answers:
   - kind: one of `agent`, `skill`, `rule`, `role`, `domain`, `stand`, `variable`, `repository`;
   - name: lowercase letters, digits and `-` only (`[a-z0-9-]+`), for example `release-notes`; for `variable` use `[A-Z][A-Z0-9_]*`, for example `TRACKER_TOKEN`.
   - For `repository`, stop here and follow `.agents/skills/repos-add/SKILL.md` instead.
3. Check that the name is free. Run the command of the kind:
   - agent: `test -e .agents/agents/<name>.md`
   - skill: `test -e .agents/skills/<name>`
   - rule: `test -e .agents/rules/<name>.md`
   - role: `test -e .agents/roles/<name>.md`
   - domain: `test -e domains/<name>`
   - stand: `grep -n '"stand:<name>"' environments.json`
   - variable: `grep -n '"<name>"' .agents/env.schema.json`
   When `test` succeeds or `grep` prints a line, the entity already exists: stop, tell the person, and change nothing.
4. Find the default branch: run `git symbolic-ref --short refs/remotes/origin/HEAD` and remove the `origin/` prefix; when the command fails, use `main`. Call it `<default>`. Then run, one by one:
   - `git switch <default>`
   - `git pull --ff-only`
   - `git switch -c extend-<kind>-<name>`
5. Do the steps of the kind in `## Kinds`.
6. If `command -v python3` prints a path, run `python3 tools/generate.py`. Otherwise apply the recipe of the kind in `## Recipes` (kinds without generated files need no recipe).
7. If `command -v python3` prints a path, run `python3 tools/check.py`. Fix every finding in files you changed and run it again until it prints nothing. Otherwise remember the line `check not run: python3 missing`.
8. Commit:
   - Run `git add` with every file you created or changed, including the generated files listed for the kind in `## Kinds`.
   - Run `git commit -m "feat(workspace): add <kind> <name>"`.
9. Run `git pull --rebase origin <default>`. On conflicts follow `## Conflicts`.
10. Push and open the merge request by `.agents/rules/merge-requests.md`, with branch `extend-<kind>-<name>` and title `Add <kind> <name>`.
11. Report to the person:
    - the files you created or changed;
    - the branch `extend-<kind>-<name>`;
    - the merge request link, or the instruction to open it;
    - as the last line, the check result, or `check not run: python3 missing`.

## Kinds
- agent:
  1. Run `mkdir -p .agents/agents && cp .agents/templates/agent.md .agents/agents/<name>.md`.
  2. In `.agents/agents/<name>.md` set `name: <name>`, write a one-sentence `description:` and replace the title and instructions. Never list tools that exist only in one tool, such as the browser automation of one vendor.
  3. Generated files: `.claude/agents/<name>.md`, `.opencode/agents/<name>.md`.
- skill:
  1. Run `mkdir -p .agents/skills/<name> && cp .agents/templates/skill/SKILL.md .agents/skills/<name>/SKILL.md`.
  2. In `.agents/skills/<name>/SKILL.md` set `name: <name>` and a one-sentence `description:`, write numbered steps under `## Steps`, and keep a `## Without Python` section. When the skill changes files, its steps end with `python3 tools/generate.py` and `python3 tools/check.py`, and its `## Without Python` ends with the line `check not run: python3 missing`.
  3. In `AGENTS.md` add one row at the end of the table under `## Skills`, in the same form as the other rows. Example for `release-notes`:
     ```
     | `.agents/skills/release-notes/SKILL.md` | write release notes for a merged merge request |
     ```
  4. Generated files: every file under `.claude/skills/<name>/`.
- rule:
  1. Run `cp .agents/templates/rule.md .agents/rules/<name>.md`.
  2. Replace `<Rule title>` in the first line; the first line stays `# <Rule title>`. Write one rule per bullet below it.
  3. Generated files: `.cursor/rules/<name>.mdc`.
- role:
  1. Run `cp .agents/templates/role.md .agents/roles/<name>.md`.
  2. Replace every `<role>` with `<name>` and fill the sections.
  3. No generated files.
- domain:
  1. Run `mkdir -p domains/<name>/map && cp .agents/templates/domain/README.md domains/<name>/README.md && touch domains/<name>/map/.gitkeep`.
  2. In `domains/<name>/README.md` replace every `<name>` with the domain name and fill `## Purpose`.
  3. No generated files.
- stand:
  1. Ask the person for `purpose`, `access`, and every service with its base URL. Never invent a value.
  2. Write every value as a JSON string: inside it write `"` as `\"` and `\` as `\\`. For example the access `Ask "platform" team, C:\vpn` becomes `"access": "Ask \"platform\" team, C:\\vpn"`.
  3. Write the new entry with two spaces of indentation per level, as `json.dumps(indent=2)` writes it:
     - `{` and the closing `}` of the entry: 4 spaces;
     - the lines `"key"`, `"purpose"`, `"access"`, `"services": {` and the closing `}` of `services`: 6 spaces, in this order;
     - each service line `"<service>": "<base url>"`: 8 spaces;
     - a comma at the end of the `"key"`, `"purpose"` and `"access"` lines;
     - a comma after every service line except the last one;
     - no comma after the closing `}` of `services` and no comma after the closing `}` of the entry.
  4. Open `environments.json` and find the `stands` list:
     - When it is the one line `  "stands": []`, replace that line with the line `  "stands": [`, then the new entry, then the line `  ]`. See example A.
     - Otherwise the list has entries. Add a comma at the end of the line `    }` that closes the previous last entry, directly above the line `  ]`. Insert the new entry between that line and `  ]`. See example B.
     - Change nothing else in the file.

     Example A, empty list. `environments.json` before:
     ```json
     {
       "stands": []
     }
     ```
     After adding stand `demo` with two services:
     ```json
     {
       "stands": [
         {
           "key": "stand:demo",
           "purpose": "Demonstrations for customers",
           "access": "Ask \"platform\" team, C:\\vpn",
           "services": {
             "orders": "https://orders.demo.invalid",
             "billing": "https://billing.demo.invalid"
           }
         }
       ]
     }
     ```
     Example B, a list with one entry. `environments.json` before:
     ```json
     {
       "stands": [
         {
           "key": "stand:demo",
           "purpose": "Demonstrations for customers",
           "access": "VPN, ask the platform team",
           "services": {
             "orders": "https://orders.demo.invalid"
           }
         }
       ]
     }
     ```
     After adding stand `load` with one service:
     ```json
     {
       "stands": [
         {
           "key": "stand:demo",
           "purpose": "Demonstrations for customers",
           "access": "VPN, ask the platform team",
           "services": {
             "orders": "https://orders.demo.invalid"
           }
         },
         {
           "key": "stand:load",
           "purpose": "Load tests",
           "access": "VPN",
           "services": {
             "orders": "https://orders.load.invalid"
           }
         }
       ]
     }
     ```
  5. No generated files. Elsewhere refer to the stand only by its key `stand:<name>`, never by its base URL.
- variable:
  1. Ask the person for `issued_by` (who issues the value) and `how_to_get` (how to request it). Never ask for or write the value itself.
  2. Write every value as a JSON string: inside it write `"` as `\"` and `\` as `\\`. For example `open "Access" in C:\portal` becomes `"how_to_get": "open \"Access\" in C:\\portal"`.
  3. Write the new entry with two spaces of indentation per level, as `json.dumps(indent=2)` writes it:
     - `{` and the closing `}` of the entry: 4 spaces;
     - the lines `"name"`, `"issued_by"`, `"how_to_get"`: 6 spaces, in this order;
     - a comma at the end of the `"name"` and `"issued_by"` lines, none after `"how_to_get"`;
     - no comma after the closing `}` of the entry.
  4. Open `.agents/env.schema.json` and find the `variables` list:
     - When it is the one line `  "variables": []`, replace that line with the line `  "variables": [`, then the new entry, then the line `  ]`. See example A.
     - Otherwise the list has entries. Add a comma at the end of the line `    }` that closes the previous last entry, directly above the line `  ]`. Insert the new entry between that line and `  ]`. See example B.
     - Change nothing else in the file.

     Example A, empty list. `.agents/env.schema.json` before:
     ```json
     {
       "variables": []
     }
     ```
     After adding variable `TRACKER_TOKEN`:
     ```json
     {
       "variables": [
         {
           "name": "TRACKER_TOKEN",
           "issued_by": "the tracker admin",
           "how_to_get": "open \"Access\" in C:\\portal"
         }
       ]
     }
     ```
     Example B, a list with one entry. `.agents/env.schema.json` before:
     ```json
     {
       "variables": [
         {
           "name": "TRACKER_TOKEN",
           "issued_by": "the tracker admin",
           "how_to_get": "request it in the access portal"
         }
       ]
     }
     ```
     After adding variable `FORGE_TOKEN`:
     ```json
     {
       "variables": [
         {
           "name": "TRACKER_TOKEN",
           "issued_by": "the tracker admin",
           "how_to_get": "request it in the access portal"
         },
         {
           "name": "FORGE_TOKEN",
           "issued_by": "the forge admin",
           "how_to_get": "create a personal access token in the forge settings"
         }
       ]
     }
     ```
  5. No generated files. In the report tell people to run the `init` skill again to get the new key in `.local/env`.

## Recipes
Use these only when `python3` is missing. Each recipe gives exactly the bytes `python3 tools/generate.py` writes. Do not change any other generated file.

### Recipe: skill
1. Run `mkdir -p .claude/skills/<name> && cp -R .agents/skills/<name>/. .claude/skills/<name>/`.
2. Run `find .claude/skills/<name> -name .DS_Store -type f -delete`.
3. Run `find .claude/skills/<name> -name __pycache__ -type d -prune -exec rm -rf {} +`.
4. Every file of `.agents/skills/<name>/` except `.DS_Store` files and files inside `__pycache__` directories now has a byte copy at the same path under `.claude/skills/<name>/`, and `.claude/skills/<name>/` has no other files.

Example for skill `release-notes`:

```
mkdir -p .claude/skills/release-notes && cp -R .agents/skills/release-notes/. .claude/skills/release-notes/
find .claude/skills/release-notes -name .DS_Store -type f -delete
find .claude/skills/release-notes -name __pycache__ -type d -prune -exec rm -rf {} +
```

Result: `.agents/skills/release-notes/SKILL.md` and `.claude/skills/release-notes/SKILL.md` are identical; `cmp .agents/skills/release-notes/SKILL.md .claude/skills/release-notes/SKILL.md` prints nothing, and `find .claude/skills/release-notes -name .DS_Store -o -name __pycache__` prints nothing.

### Recipe: agent
1. Run `mkdir -p .claude/agents .opencode/agents && cp .agents/agents/<name>.md .claude/agents/<name>.md`.
2. Write `.opencode/agents/<name>.md` with these lines, in order:
   - the line `---`;
   - the first `description:` line of the source frontmatter, copied exactly (write `description: ` when the source has none);
   - the line `mode: subagent`;
   - the line `---`;
   - every line after the source's closing `---`, unchanged (the whole source when it has no frontmatter).
3. The file ends with a newline, like the source.

Example for agent `reviewer`. Source `.agents/agents/reviewer.md`:

```
---
name: reviewer
description: Reviews a merge request diff against the workspace rules.
---
# Reviewer

Read the diff and list findings as `path:line message`.
```

`.claude/agents/reviewer.md` is the same file. `.opencode/agents/reviewer.md`:

```
---
description: Reviews a merge request diff against the workspace rules.
mode: subagent
---
# Reviewer

Read the diff and list findings as `path:line message`.
```

### Recipe: rule
1. Run `mkdir -p .cursor/rules`.
2. Write `.cursor/rules/<name>.mdc` with these lines, in order:
   - the line `---`;
   - the line `description: <text of the first line of the rule without "# ">`;
   - the line `alwaysApply: true`;
   - the line `---`;
   - the whole rule file `.agents/rules/<name>.md`, unchanged.

Example for rule `sql-style`. Source `.agents/rules/sql-style.md`:

```
# SQL style

- Write SQL keywords in upper case.
```

`.cursor/rules/sql-style.mdc`:

```
---
description: SQL style
alwaysApply: true
---
# SQL style

- Write SQL keywords in upper case.
```

### Other recipes
- Repository: `## Recipe: repository table` in `.agents/skills/repos-add/SKILL.md`.
- ADR: the recipe in `.agents/skills/decide/SKILL.md`.
- Role, domain, stand and variable have no generated files and need no recipe.

## Conflicts
A file is generated when its path starts with `.claude/`, `.opencode/` or `.cursor/`, or when it is exactly `CLAUDE.md`, `.agents/index.json` or `REPOSITORIES.md`. Every other file is not generated.

1. List all conflicted files: `git diff --name-only --diff-filter=U`. Write the list down before you change anything.
2. First check the whole list for any file that is not generated. If there is one:
   - Run `git rebase --abort`. Do not touch any file first, not even the generated ones.
   - For each file that is not generated, show the person both versions with these labels:
     - "default branch": the output of `git show origin/<default>:<file>`;
     - "your branch": the output of `git show extend-<kind>-<name>:<file>`.
     When one of the two commands fails, tell the person that side has no such file.
   - Stop and wait for the person.
3. Only when every file in the list is generated:
   - For each file in the list, run `git checkout --ours -- <file>`. During a rebase `--ours` is the default branch version.
   - Regenerate: if `command -v python3` prints a path, run `python3 tools/generate.py`; otherwise apply the recipe of your kind in `## Recipes` again.
   - For each file in the list, run `git add <file>`. Also `git add` any generated file of your kind that the regeneration changed.
   - Run `GIT_EDITOR=true git rebase --continue`.
   - If `command -v python3` prints a path, run `python3 tools/check.py` again and fix findings as in step 7.

## Without Python
1. In step 6, apply the recipe of the kind in `## Recipes` instead of `python3 tools/generate.py`.
2. Skip `python3 tools/generate.py` and `python3 tools/check.py` everywhere, including `## Conflicts`.
3. End the report with the line:

check not run: python3 missing
