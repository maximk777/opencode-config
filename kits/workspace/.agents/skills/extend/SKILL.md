---
name: extend
description: Use to add an agent, skill, rule, role, domain, stream, map element, stand, environment variable or repository to this workspace by its templates, through a merge request.
---
# Extend the workspace

## Steps
1. Go to the workspace root: the nearest directory, walking up from where you are, where `test -f .agents/kit.json` succeeds. Run every command below from there. Then find the workspace language:
   - Run `grep -o '"language": *"[a-z]*"' .agents/kit.json`. When it prints a line such as `"language": "ru"`, the language is the code in the last quotes, here `ru`. When it prints nothing, the language is `en`. Call it `<language>`.
   - A profile template `<name>` of profile `<profile>` is `.agents/profiles/<profile>/<name>.<language>.md` when `<language>` is not `en` and `test -f .agents/profiles/<profile>/<name>.<language>.md` succeeds; otherwise it is `.agents/profiles/<profile>/<name>.md`. Example with language `ru`: the `epic` template of `ui-migration` is `.agents/profiles/ui-migration/epic.ru.md`.
   - In `profile.json` a heading, a column list, a key list, and the `title`, `note` and `columns` of `breakdown` may be a language object such as `{"en": "Transitions", "ru": "Переходы"}`. Take its value under `<language>`, or under `en` when that key is absent. A plain value is used as it is.
2. Ask the person for the kind and the name, and wait for both answers:
   - kind: one of `agent`, `skill`, `rule`, `role`, `domain`, `stream`, `map-element`, `stand`, `variable`, `repository`;
   - name: lowercase letters, digits and `-` only (`[a-z0-9-]+`), for example `release-notes`; for `variable` use `[A-Z][A-Z0-9_]*`, for example `TRACKER_TOKEN`. For `stream` the name is the stream name, for `map-element` it is the element slug.
   - For `repository`, stop here and follow `.agents/skills/repos-add/SKILL.md` instead.
   - For `domain`, also ask which profile the domain's map follows. Show the profiles with `ls .agents/profiles` and let the person pick one of them.
   - For `stream`, also ask the domain and the profile. Show the profiles with `ls .agents/profiles` and let the person pick one of them.
   - For `map-element`, also ask the domain and whether to add the element to the scope of a stream, and if so which stream. The profile is then the `"profile"` value of `domains/<domain>/streams/<stream>/stream.json`; without a stream, show `ls .agents/profiles` and let the person pick one. Then read the `elements` list in `.agents/profiles/<profile>/profile.json`; when it has more than one object, ask the person which `kind` to add. From the chosen object take `kind`, `prefix`, `dir`, `fields` and `tables`. The template is the profile template `<kind>` from step 1 and the element key is `<prefix>:<domain>/<name>`. Run `test -f .agents/profiles/<profile>/<kind>.md`; when it fails, stop, tell the person the profile has no template for that kind, and change nothing. Example: with the `ui-migration` profile the kind is `screen`, the prefix is `screen`, the directory is `map`, the template is `.agents/profiles/ui-migration/screen.md` (`.agents/profiles/ui-migration/screen.ru.md` with language `ru`) and the key is `screen:<domain>/<name>`.
   - For `stream` and `map-element`, run `test -d domains/<domain>`. When it fails, the domain does not exist: stop, tell the person to add the domain first, and change nothing. For `map-element` with a stream, also run `test -f domains/<domain>/streams/<stream>/stream.json`; when it fails, stop the same way.
3. Check that the name is free. Run the command of the kind:
   - agent: `test -e .agents/agents/<name>.md`
   - skill: `test -e .agents/skills/<name>`
   - rule: `test -e .agents/rules/<name>.md`
   - role: `test -e .agents/roles/<name>.md`
   - domain: `test -e domains/<name>`
   - stream: `test -e domains/<domain>/streams/<name>`
   - map-element: `test -e domains/<domain>/<dir>/<name>.md`
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
  1. Run `mkdir -p domains/<name>/map && cp .agents/templates/domain/README.md domains/<name>/README.md && cp <map template> domains/<name>/MAP.md && touch domains/<name>/map/.gitkeep`, where `<map template>` is the profile template `MAP` from step 1: `.agents/profiles/<profile>/MAP.md`, or `.agents/profiles/<profile>/MAP.<language>.md` when that file exists. For `ui-migration` with language `en`: `cp .agents/profiles/ui-migration/MAP.md domains/<name>/MAP.md`; with language `ru`: `cp .agents/profiles/ui-migration/MAP.ru.md domains/<name>/MAP.md`.
  2. In `domains/<name>/README.md` replace every `<name>` with the domain name and fill `## Purpose`.
  3. In `domains/<name>/MAP.md` replace every `<domain>` with the domain name. Change nothing else.
  4. Generated files: the tables between the `map:` markers in `domains/<name>/MAP.md`.
- stream:
  1. Run `mkdir -p domains/<domain>/streams/<name> && cp .agents/templates/stream.json domains/<domain>/streams/<name>/stream.json && cp <epic template> domains/<domain>/streams/<name>/epic.md`, where `<epic template>` is the profile template `epic` from step 1: `.agents/profiles/<profile>/epic.md`, or `.agents/profiles/<profile>/epic.<language>.md` when that file exists. For `ui-migration` with language `ru`: `cp .agents/profiles/ui-migration/epic.ru.md domains/<domain>/streams/<name>/epic.md`.
  2. In `domains/<domain>/streams/<name>/stream.json` change only two values: in `"key"` replace `<domain>/<stream>` with `<domain>/<name>`, and set `"profile"` to the chosen profile. Keep `"stage": "goal"`, `"scope": []` and `"approvals": []`. Example for stream `legacy-ops-risks` in domain `risks` with profile `ui-migration`:
     ```json
     {
       "key": "stream:risks/legacy-ops-risks",
       "profile": "ui-migration",
       "stage": "goal",
       "scope": [],
       "approvals": []
     }
     ```
  3. In `domains/<domain>/streams/<name>/epic.md` replace the placeholder in the first line with the title the person gives: `<Epic title>` in `epic.md`, `<Название эпика>` in `ui-migration/epic.ru.md`. Keep every section; the person fills them during the `goal` stage.
  4. Generated files: `domains/<domain>/streams/<name>/BREAKDOWN.md`.
- map-element:
  1. Run `mkdir -p domains/<domain>/<dir> && cp <element template> domains/<domain>/<dir>/<name>.md`, with `<dir>` from step 2 and `<element template>` the profile template `<kind>` from step 1: `.agents/profiles/<profile>/<kind>.md`, or `.agents/profiles/<profile>/<kind>.<language>.md` when that file exists. For `ui-migration`: `mkdir -p domains/<domain>/map && cp .agents/profiles/ui-migration/screen.md domains/<domain>/map/<name>.md`; with language `ru` copy `.agents/profiles/ui-migration/screen.ru.md` instead.
  2. In `domains/<domain>/<dir>/<name>.md` set `key: <prefix>:<domain>/<name>`. Ask the person for every other field in `fields` of the element; fields in `may_be_empty` may stay empty; a field with a `values` list takes one of those values. Write each value after `<field>: ` on its own line. Never invent a value. For `ui-migration`: set `key: screen:<domain>/<name>`, ask for `route`, `section`, `access`, `label` and `wave`, and for `parent` (a `screen:` key) and `story` (a `story:` key), which may stay empty; keep `kind: place`.
  3. For each object in `tables` of the element, take `heading`, `columns` and `keys` in the workspace language as step 1 says. Under `## <heading>` add one row per row the person names, in the person's order, with one cell per column of `columns`, in that order; a cell of a column listed in `keys` is an element key. With no rows keep only the header and separator lines. For `ui-migration`: under `## Transitions` (`## Переходы` with language `ru`, columns `Действие`, `Цель`) add one row `| <action> | <target> |` per transition; every target is a `screen:` key.
  4. Only when the person chose a stream, edit `domains/<domain>/streams/<stream>/stream.json`, keeping two spaces of indentation per level, as `json.dumps(indent=2)` writes it:
     - Scope: when `scope` is the one line `  "scope": [],`, replace it with the three lines `  "scope": [`, `    "<prefix>:<domain>/<name>"`, `  ],`. Otherwise add a comma at the end of the last string line of `scope` and insert the line `    "<prefix>:<domain>/<name>"` directly above `  ],`.
     - Stage: the stage order is `goal`, `map`, `decomposition`, `ready`, `delivery`, `done`. When `stage` is `goal` or `map`, change nothing else. When `stage` is `decomposition`, `ready`, `delivery` or `done`:
       - set `"stage": "map"`;
       - remove every approval object whose `"stage"` is `map`, `decomposition`, `ready`, `delivery` or `done`, and keep the others in their order; every kept object except the last one ends with `    },`, the last one with `    }`; when no object is left, write the one line `  "approvals": []`;
       - tell the person: "The scope of stream:<domain>/<stream> grew after its map was approved, so the stream is back at stage `map` and the approvals of `map` and every later stage are removed. The map and the later stages must be approved again."

     Example: stream `legacy-ops-risks` at stage `ready`, adding `screen:risks/limits`. Before:
     ```json
     {
       "key": "stream:risks/legacy-ops-risks",
       "profile": "ui-migration",
       "stage": "ready",
       "scope": [
         "screen:risks/overview"
       ],
       "approvals": [
         {
           "stage": "goal",
           "by": "anna",
           "date": "2026-09-01"
         },
         {
           "stage": "map",
           "by": "anna",
           "date": "2026-09-05"
         },
         {
           "stage": "decomposition",
           "by": "oleg",
           "date": "2026-09-08"
         }
       ]
     }
     ```
     After:
     ```json
     {
       "key": "stream:risks/legacy-ops-risks",
       "profile": "ui-migration",
       "stage": "map",
       "scope": [
         "screen:risks/overview",
         "screen:risks/limits"
       ],
       "approvals": [
         {
           "stage": "goal",
           "by": "anna",
           "date": "2026-09-01"
         }
       ]
     }
     ```
  5. Generated files: the tables between the `map:` markers in `domains/<domain>/MAP.md`.
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

### Recipe: map element
Use it for kind `map-element`, and for kind `domain`, whose new `MAP.md` has no elements yet. In `domains/<domain>/MAP.md` change only the lines strictly between a `<!-- map:<block>:begin -->` line and its `<!-- map:<block>:end -->` line; every other line stays as it is. When `MAP.md` lacks the marker lines of a block, skip that block.

1. Blocks come from `elements` in `.agents/profiles/*/profile.json`: one block `map:<kind>s` per element kind, and one block per table of the kind, named `map:` + the table heading in lower case with spaces written as `-`. Take every table `heading` and `columns` in the workspace language as step 1 says. For `ui-migration` these are `map:screens` (fields `key`, `route`, `kind`, `section`, `parent`, `access`, `label`, `wave`, `story`) and `map:transitions` (table `Transitions`, columns `Action`, `Target`); with language `ru` the second block is `map:переходы` (table `Переходы`, columns `Действие`, `Цель`).
2. The `map:screens` block holds, in this order:
   - the header `| key | route | kind | section | parent | access | label | wave | story |`: `| `, the field names joined with ` | `, then ` |`;
   - the separator `|---|---|---|---|---|---|---|---|---|`: `|`, then `---|` once per field;
   - one row per element file `domains/<domain>/<dir>/*.md`, with `<dir>` from the element in `profile.json` (`map` for `ui-migration`): `| `, its frontmatter values in field order joined with ` | `, then ` |`. Copy every value verbatim without surrounding quotes; join a list (`[a, b]` or lines starting with `  - `) with `, `; write a missing or empty value as the empty string, which gives two spaces between bars (`|  |`).
3. The block of a table, `map:transitions` for `ui-migration`, holds, in this order:
   - the header `| From | Action | Target |`: `| `, the first column name, ` | `, the table columns joined with ` | `, then ` |`. Take the first column name from `map_doc.from_column` in the `profile.json` that declares the element kind, in the workspace language as step 1 says; when it is absent, use `From`. For `ui-migration` with language `ru` the header is `| Откуда | Действие | Цель |`;
   - the separator `|---|---|---|`: `|`, then `---|` once per column plus one;
   - for each element file, one row per row of its `## <heading>` table (`## Transitions`, or `## Переходы` with language `ru`), in the order of that file: `| <element key> | ` followed by its cells in the order of the profile columns, joined with ` | `, then ` |`, each cell with surrounding spaces removed. An element whose table has no rows adds nothing.
4. Order: elements go in ascending order of file name (`<slug>.md`), compared character by character by character code; for example `limit-card.md` comes before `limit.md`, because `-` sorts before `.`. In `map:transitions` the rows of one element stay together and follow the same element order.
5. To add one element:
   - When a block is empty, that is its begin line is directly followed by its end line, first write its header and separator lines between them.
   - In `map:screens` insert the new row directly above the first row whose file name sorts after the new file name, or directly above the end line when there is none.
   - In each table block insert the new element's rows, in file order, directly above the rows of the first element whose file name sorts after the new one, or directly above the end line when there is none.
6. For a new domain there are no elements: each block gets only its header and separator lines.

Examples A and B use language `en`. With language `ru` the second block of a new domain is:

```
## Переходы
<!-- map:переходы:begin -->
| Откуда | Действие | Цель |
|---|---|---|
<!-- map:переходы:end -->
```

Example A, new domain `risks`. The blocks of `domains/risks/MAP.md` after the recipe:

```
## Screens
<!-- map:screens:begin -->
| key | route | kind | section | parent | access | label | wave | story |
|---|---|---|---|---|---|---|---|---|
<!-- map:screens:end -->

## Transitions
<!-- map:transitions:begin -->
| From | Action | Target |
|---|---|---|
<!-- map:transitions:end -->
```

Example B, domain `risks` with `map/alerts.md` and `map/overview.md`, adding `map/limits.md`. The blocks before:

```
## Screens
<!-- map:screens:begin -->
| key | route | kind | section | parent | access | label | wave | story |
|---|---|---|---|---|---|---|---|---|
| screen:risks/alerts | /risks/alerts | place | Risks |  | risks.alerts.read | Alerts | 1 |  |
| screen:risks/overview | /risks | place | Risks |  | risks.read | Overview | 1 | story:risks/overview |
<!-- map:screens:end -->

## Transitions
<!-- map:transitions:begin -->
| From | Action | Target |
|---|---|---|
| screen:risks/overview | Open alerts | screen:risks/alerts |
<!-- map:transitions:end -->
```

The new file `domains/risks/map/limits.md`:

```
---
key: screen:risks/limits
route: /risks/limits
kind: place
section: Risks
parent: screen:risks/overview
access: risks.limits.read
label: Limits
wave: 2
story:
---

## Transitions
| Action | Target |
|---|---|
| Back | screen:risks/overview |
| Show alerts | screen:risks/alerts |
```

The blocks after. `limits.md` sorts after `alerts.md` and before `overview.md`:

```
## Screens
<!-- map:screens:begin -->
| key | route | kind | section | parent | access | label | wave | story |
|---|---|---|---|---|---|---|---|---|
| screen:risks/alerts | /risks/alerts | place | Risks |  | risks.alerts.read | Alerts | 1 |  |
| screen:risks/limits | /risks/limits | place | Risks | screen:risks/overview | risks.limits.read | Limits | 2 |  |
| screen:risks/overview | /risks | place | Risks |  | risks.read | Overview | 1 | story:risks/overview |
<!-- map:screens:end -->

## Transitions
<!-- map:transitions:begin -->
| From | Action | Target |
|---|---|---|
| screen:risks/limits | Back | screen:risks/overview |
| screen:risks/limits | Show alerts | screen:risks/alerts |
| screen:risks/overview | Open alerts | screen:risks/alerts |
<!-- map:transitions:end -->
```

### Recipe: empty BREAKDOWN.md
Use it for kind `stream`.

1. Open `.agents/profiles/<profile>/profile.json` of the stream's profile and find its `breakdown` block. Take `<title>`, `<note>` and `<columns>` from its `title`, `note` and `columns`, each in the workspace language as step 1 says. When the block or one of these keys is absent, use the default:
   - title `Breakdown of`;
   - note `Generated by tools/generate.py from stories/*/story.md. Do not edit.`;
   - columns `Story`, `Wave`, `Scope`, `Unmapped`, `Tracker`, `Depends`.
2. Write `domains/<domain>/streams/<name>/BREAKDOWN.md` with exactly these lines and end the file with a newline after the last line:
   - `# <title> stream:<domain>/<name>`;
   - an empty line;
   - `<note>`;
   - an empty line;
   - the header: `| `, the columns joined with ` | `, then ` |`;
   - the separator `|---|---|---|---|---|---|`.

With the defaults the file is:

```
# Breakdown of stream:<domain>/<name>

Generated by tools/generate.py from stories/*/story.md. Do not edit.

| Story | Wave | Scope | Unmapped | Tracker | Depends |
|---|---|---|---|---|---|
```

With profile `ui-migration` and language `ru` the first line is `# Разбивка stream:<domain>/<name>`, the note is `Сгенерировано tools/generate.py из stories/*/story.md. Не редактировать.` and the header is `| Стори | Волна | Экраны | Без экрана | Трекер | Зависит от |`.

Example for stream `legacy-ops-risks` in domain `risks` with language `en`, file `domains/risks/streams/legacy-ops-risks/BREAKDOWN.md`:

```
# Breakdown of stream:risks/legacy-ops-risks

Generated by tools/generate.py from stories/*/story.md. Do not edit.

| Story | Wave | Scope | Unmapped | Tracker | Depends |
|---|---|---|---|---|---|
```

### Other recipes
- Repository: `## Recipe: repository table` in `.agents/skills/repos-add/SKILL.md`.
- ADR: the recipe in `.agents/skills/decide/SKILL.md`.
- Domain and map element: `### Recipe: map element`. Stream: `### Recipe: empty BREAKDOWN.md`.
- Role, stand and variable have no generated files and need no recipe.

## Conflicts
A file is generated when its path starts with `.claude/`, `.opencode/` or `.cursor/`, when it is exactly `CLAUDE.md`, `.agents/index.json` or `REPOSITORIES.md`, or when it matches `domains/<domain>/streams/<stream>/BREAKDOWN.md`. Every other file is not generated, with one exception: `domains/<domain>/MAP.md`.

`domains/<domain>/MAP.md` mixes generated tables with hand-written text. Only the lines strictly between a `<!-- map:<block>:begin -->` line and its `<!-- map:<block>:end -->` line are generated. Run `grep -n '^<<<<<<<\|^>>>>>>>\|<!-- map:' domains/<domain>/MAP.md`. Treat the file as generated for this conflict only when every `<<<<<<<` line and its following `>>>>>>>` line lie between one begin line and its end line; otherwise treat it as not generated. Never run `git checkout --ours` on `MAP.md`: it would drop the lines your branch changed outside the blocks that git merged cleanly. Resolve a generated `MAP.md` by editing it instead: in each conflicted hunk keep the lines of one side, either will do, and delete the `<<<<<<<`, `=======` and `>>>>>>>` lines; leave every line outside the hunks as it is. Regeneration then rewrites the blocks: without Python re-apply `### Recipe: map element`, adding every element file in `domains/<domain>/<dir>/` (for each `dir` of the profile's `elements`) that is missing from the blocks, so rows added on the default branch are kept too.

1. List all conflicted files: `git diff --name-only --diff-filter=U`. Write the list down before you change anything.
2. First check the whole list for any file that is not generated, including a `MAP.md` with a conflict outside its marker blocks. If there is one:
   - Run `git rebase --abort`. Do not touch any file first, not even the generated ones.
   - For each file that is not generated, show the person both versions with these labels:
     - "default branch": the output of `git show origin/<default>:<file>`;
     - "your branch": the output of `git show extend-<kind>-<name>:<file>`.
     When one of the two commands fails, tell the person that side has no such file.
   - Stop and wait for the person.
3. Only when every file in the list is generated:
   - For each file in the list except `domains/<domain>/MAP.md`, run `git checkout --ours -- <file>`. During a rebase `--ours` is the default branch version.
   - For each `domains/<domain>/MAP.md` in the list, edit its conflicted hunks as described above; do not run `git checkout` on it.
   - Regenerate: if `command -v python3` prints a path, run `python3 tools/generate.py`; otherwise apply the recipe of your kind in `## Recipes` again.
   - For each file in the list, run `git add <file>`. Also `git add` any generated file of your kind that the regeneration changed.
   - Run `GIT_EDITOR=true git rebase --continue`.
   - If `command -v python3` prints a path, run `python3 tools/check.py` again and fix findings as in step 7.

## Without Python
1. In step 6, apply the recipe of the kind in `## Recipes` instead of `python3 tools/generate.py`.
2. Skip `python3 tools/generate.py` and `python3 tools/check.py` everywhere, including `## Conflicts`.
3. End the report with the line:

check not run: python3 missing
