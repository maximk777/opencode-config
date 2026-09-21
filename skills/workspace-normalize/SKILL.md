---
name: workspace-normalize
description: Use when the workspace-builder agent must bring an existing team workspace without .agents/kit.json, or with a kit stamp older than 0.5.0, under the workspace kit
---
# Normalize a workspace

Bring an existing workspace under the kit in a git worktree: an approved plan first, then the kit base in one merge request, then one merge request per domain. Answer the owner in Russian. Ask one question per message and wait for the answer before the next one. Leave every change uncommitted.

## When

- The owner points to an existing git repository that has a remote `origin` and on its default branch either no `.agents/kit.json`, or a `.agents/kit.json` whose `version` is older than `0.5.0` (base phase), or both `.agents/kit.json` of `0.5.0` or later and `docs/normalize/plan.md` with `todo` rows under a domain (domain phase).
- A repository with a `.agents/kit.json` of `0.5.0` or later and no `docs/normalize/plan.md` is a kit workspace: stop and use the workspace-extend skill instead. A kit stamp older than `0.5.0` is a migration: the base phase adopts the `0.5.0` kit files and then applies the six migration rows of Phase 2 step 2.
- An empty directory or a new workspace: stop and use the workspace-create skill instead.
- A branch or worktree `normalize-base` or `normalize-<domain>` already exists: Phase 0 step 7 stops and asks the owner whether to continue it or recreate it.

## Phase 0: worktree

The owner's checkout is read only. In `<checkout>` you run only `git rev-parse`, `git branch --show-current`, `git remote get-url`, `git status`, `git fetch --prune origin`, `git ls-remote`, `git cat-file`, `git log`, `git worktree list` and `git worktree add`; you never edit, stash, reset, check out, delete a branch or clean anything there.

`<branch>` is `normalize-base` in the base phase and `normalize-<domain>` in a domain phase.

1. Ask the owner for the absolute path of their checkout. Call it `<checkout>`.
2. Run `cd <checkout> && git rev-parse --show-toplevel && git remote get-url origin`. When either fails, stop and show the error.
3. Run `cd <checkout> && git fetch --prune origin`. It updates only remote-tracking refs and drops refs of branches deleted on the remote. When it fails, stop and show the git error.
4. Take the owner's snapshot after the fetch, so remote-tracking changes do not count: `cd <checkout> && git rev-parse HEAD && git branch --show-current && git status --porcelain=v1 --untracked-files=all`. Keep the output; step 10 compares it.
5. Run `cd <checkout> && git ls-remote --symref origin HEAD`. The first line reads `ref: refs/heads/master	HEAD`; the name after `refs/heads/` is `<default>`.
6. Run `cd <checkout> && git cat-file -e origin/<default>:.agents/kit.json`. In the base phase, when it exits 0, read the stamp version: `cd <checkout> && git show origin/<default>:.agents/kit.json`. When the version is `0.5.0` or later, stop: the workspace is already under the current kit, use workspace-extend. When it is older, the base phase is a migration: the plan gets the six migration rows of Phase 2 step 2 directly after the `adopt` row. In a domain phase it must exit 0, and so must `cd <checkout> && git cat-file -e origin/<default>:docs/normalize/plan.md`; when either fails, stop and tell the owner that the base merge request is not merged yet. Then count the `todo` rows under `### <domain>` of that plan; when it prints `0`, stop and tell the owner that the domain is already done or is not in the plan:
   ```
   cd <checkout> && git cat-file -p origin/<default>:docs/normalize/plan.md | python3 -c '
   import sys
   domain, inside, count = sys.argv[1], False, 0
   for line in sys.stdin.read().split("\n"):
       if line.startswith("## ") or line.startswith("### "):
           inside = line.strip() == "### " + domain
       elif inside and line.startswith("|") and "| todo |" in line:
           count += 1
   print(count)
   ' operations
   ```
7. Run `cd <checkout> && git worktree list --porcelain` and `cd <checkout> && git rev-parse --verify --quiet refs/heads/<branch>`. When a worktree entry `branch refs/heads/normalize-base` or `branch refs/heads/normalize-<domain>` exists for `<branch>`, or the branch exists, never reuse it silently.
   - When the `worktree` line of that entry equals the `git rev-parse --show-toplevel` output of step 2, `<branch>` is checked out in the owner's own checkout. Stop and tell the owner so; never continue there and offer no other option.
   - Otherwise stop, show `git log --oneline origin/<default>..<branch>` and `git log --oneline <branch>..origin/<default>`, and ask the owner:
     - continue it: when a worktree entry exists, its `worktree` line is `<wt>`. When only the branch exists, `<wt>` is the path of step 8 (`<checkout>-<branch>`); when `test -e <wt>` succeeds, ask the owner for another path; then, after the owner's word, run `cd <checkout> && git worktree add <wt> <branch>`. Then go to «Resume by plan status» in `## Rules`;
     - or recreate it: when a worktree entry exists, print `cd <checkout> && git worktree remove <wt>` and `cd <checkout> && git branch -D <branch>`; when only the branch exists, print only `cd <checkout> && git branch -D <branch>`. The owner runs them; after the owner confirms, start again from step 7. Never remove the worktree or delete the branch yourself.
8. The worktree path is `<wt>` = `<checkout>-<branch>`, a sibling of the checkout, for example `/Users/owner/work/legacy-backoffice-workspace-normalize-base`. When `test -e <wt>` succeeds, ask the owner for another path.
9. Run `cd <checkout> && git worktree add --no-track -b <branch> <wt> origin/<default>`. `--no-track` keeps the default branch out of the new branch's upstream, so a plain push cannot target it. When the command exits non-zero, stop: show the owner git's error output verbatim and write no file anywhere.
10. Repeat the snapshot command of step 4. Stop and show both outputs only when `HEAD`, the branch name or the status lines differ, since those mean a real change in the owner's tree, index, `HEAD` or branch.
11. Run `cd <wt> && git status --porcelain=v1 --untracked-files=all`. It must print nothing.

A domain phase runs the same steps with `<branch>` = `normalize-<domain>`; step 3 fetches again, so the worktree starts from the current `origin/<default>`.

Run every later command in `<wt>`. Inputs outside the workspace, such as an architect's PoC folder under `~/specs/`, are read only: never write, move or run generators there.

## Phase 1: inventory and plan

### Inventory

1. List the top level: `cd <wt> && git ls-tree --name-only origin/<default>`.
2. List every tracked file: `cd <wt> && git ls-tree -r --name-only origin/<default>`. Count a folder with `git ls-tree -r --name-only origin/<default> -- <dir> | wc -l`. Files that are not tracked on the default branch are not part of normalize.
3. Send the `explorer` subagent to read entry documents (`README.md`, `REPOSITORIES.md`, folder READMEs), repository lists and domain folders, and to bring back findings with paths. Pass it the secrets rule of step 6 in the task text: «Report files that may hold secret values (secret maps, `.env*`, credential or key files, anything under vault folders) by name only; never open them and never quote a value.» Read files in `<wt>`; its tree equals `origin/<default>`.
4. Find design notes with a status line. A status line is a line within the first 20 lines of the note that starts with `Статус:`, optionally in bold (`**Статус:**` or `**Статус**:`). Run `cd <wt> && git grep -n -E '^\*{0,2}Статус\*{0,2}:' origin/<default> -- '<design dir>'` and keep hits whose line number is 20 or less. Each hit reads `origin/<default>:<path>:<line>:<text>`. Take the status word from the text, for example `утверждён` from `Статус: **утверждён** 2026-09-02`.
5. Find personal and session files: folders such as `prompts/` and `handoffs/`, and files with home paths from `cd <wt> && git grep -l -e "/Users/" -e "/home/" origin/<default>`.
6. Find secret handling: list names only, for example `git ls-tree -r --name-only origin/<default> -- tools/vault`. Take variable names from scripts with a match-only search such as `git grep -ohE '\$\{?[A-Z][A-Z0-9_]{2,}' origin/<default> -- 'tools/vault/*.sh'`. Never open files that hold values (secret maps, `.env*`, credential JSON). When names exist only in such files, ask the owner for the list of names.
7. Find open work on paths that will move:
   - `cd <wt> && git branch -r --no-merged origin/<default>`; stale refs were pruned in Phase 0 step 3, and a branch counts only when `git ls-remote --heads origin <name>` still lists it;
   - for each branch, `git diff --name-only origin/<default>...<branch> -- <moved paths>`; a non-empty result is open work on those paths;
   - when `command -v glab` succeeds, run `glab mr list` for open merge requests; when `command -v gh` succeeds, run `gh pr list --state open --json number,title,headRefName`; match each request to its source branch;
   - without a forge CLI, list the branches and write in the plan that merge request numbers were not checked.
8. Find the stories of each domain. List the legacy story folders with `cd <wt> && git ls-tree -d --name-only origin/<default> -- <old>/stories/`. When a PoC for the domain has a `stories/` folder, list it with `ls <poc>/stories/*.md`; its stories are the target set. Write one row per PoC story and one row per legacy story folder under `### <domain>`, by Phase 3 step 7:
   - a legacy folder that the owner maps to a PoC story: `move` to `stories/<poc-slug>/`, with the Note `PoC story: stories/<poc-slug>.md`;
   - a PoC story that no legacy folder maps to: `convert` from `<poc>/stories/<slug>.md` to `stories/<slug>/story.md`;
   - a legacy folder that maps to no PoC story gets one of two owner decisions in its Note. Keep: a `move` row to `stories/<slug>/`, where the slug is the folder name without its numeric prefix, with the Note `no PoC story; owner decision: keep`. Remove: a `remove` row whose Note quotes the owner's reason, for example `no PoC story; owner decision: remove; reason: «…»`. When the owner wants the folder's text in another story, the owner moves it there in the legacy repository before the domain phase; repeat this step and get the plan approved again.
   The mapping and the decisions come only from the owner and are approved with the plan. Never match a folder to a PoC story by its slug, title or text yourself; show both lists to the owner and ask. Without PoC stories, write one `move` row per legacy folder.

### ADR status mapping

A design note becomes an ADR only when it has a status line. The status word maps to the ADR `status`:

| Status word in the note | Action | ADR status |
|---|---|---|
| утверждён, сделано, выполнено | `adr` | `accepted` |
| к исполнению, в работе, частично сделано | `adr` | `proposed` |
| no status line | `move` to `docs/design/` | none |
| template file, such as `_TEMPLATE.md` | not an ADR; `remove` or `keep` by the owner's choice | none |

Any other status word is an open question in the plan; do not pick a status for it. ADR numbers in targets follow the note's date, then its file name; notes without a date come after all dated notes, ordered by file name.

### Plan file

Write `docs/normalize/plan.md` in `<wt>`. It is the only file you write before approval. It has a plan status line, the default branch, the workspace language as a two-letter code with its evidence (for example `ru` when the entry documents are Russian), the sections «Основа», «Домены», «Личное», «Вне change», and «Открытые вопросы». Every row gives the source path, the action, the target path, the status and a note.

Actions:
- `adopt`: `workspace-kit adopt` installs the kit; the source is `kit workspace <version>`, the target `.agents/kit.json`, the note gives the parameters.
- `merge`: a templated kit file (`AGENTS.md`, `README.md`, `REPOSITORIES.md`, `docs/ARCHITECTURE.md`, and `tracker/tracker.json` when the workspace has one) is merged by hand with the existing files named in the source column.
- `move`: the file moves unchanged, with link repair.
- `convert`: the content is rewritten into a kit file.
- `adr`: a design note becomes `docs/adr/NNNN-<slug>.md`; the note gives the ADR status and quotes the status line.
- `personal`: a personal or session file; the note gives the proposal (promote to `docs/`, move to `work/<TASK-ID>/`, or remove from git so the author keeps it in `.local/`).
- `remove`: the file leaves git, with link repair.
- `keep`: the file stays where it is.
- `import`: a file from a read-only input outside the workspace, such as an architect's PoC folder, is copied into the workspace unchanged; the source is written with `~/`, never as an absolute home path.
- `projectize`: a migration row; creates `projects/<key>/` with `PROJECT.md` — the key agreed with the owner, defaulting to the workspace name — and moves every `domains/<domain>/` into it; ADRs stay in `docs/adr/`.
- `retarget`: a migration row; rewrites `story:`, `stream:`, `domain:`, `screen:` and `mockup:` keys to the project-prefixed form and regenerates `.agents/index.json`.
- `work merge`: a migration row; moves a `work/<ID>/record.md` into the folder of the task its id resolves to, as `work.md` with `recorded` from the record's last commit date, and stamps that task `status: done`; a record that resolves to no task becomes a `keep` row instead.
- `status stamp`: a migration row; gives every story without a work record `status: waiting`, empty `owner` and `started`.
- `roles off`: a migration row; deletes `.agents/roles/` and drops `roles` from every `repos.json` entry.
- `trackers convert`: a migration row; turns `tracker/tracker.json` into `tracker/trackers.json` with one entry whose key the owner names.
- `check`: `tools/generate.py`, then `tools/check.py` must exit 0; it closes a phase.

The rows are the plan order, and every phase applies them top to bottom. The base phase takes «Основа», then «Личное». Write the «Основа» rows in the order of the Phase 2 steps:
1. the `adopt` row;
2. one `merge` row per templated file, naming its sources;
3. the `convert` row for `repos.json`, with the mapping from table groups to role names;
4. the `adr` rows;
5. the `move` rows to `docs/design/` and the `remove` rows;
6. the diagram `move` rows;
7. the `move` rows into `tracker/` and `scripts/`.

Write the personal file rows under «Личное», and the base `check` row as its last row.

Write the rows under each `### <domain>` of «Домены» in the order of the Phase 3 steps; «Domain rows» in Phase 3 shows a filled example.

A migration base phase — the stamp was older than `0.5.0` — skips the inventory of a legacy container and the `convert`, `adr`, `move` and `personal` rows of the list above: the workspace tree is already the kit tree of an older kit, so there is no legacy folder, no design notes to convert and no personal files in git. Its «Основа» holds the `adopt` row, the `merge` rows that its conflicts demand, then the six migration rows in the order of Phase 2 step 2 — `projectize`, `retarget`, `work merge`, `status stamp`, `roles off`, `trackers convert`; «Личное» holds only the `check` row, and «Домены» and «Вне change» hold no rows. The migration never touches `.local/`.

Row statuses: `todo`, `done`, `excluded`. A row becomes `done` only after its change is applied and verified against the worktree by the checks in «Resume by plan status», and `excluded` only by the owner's word.

Filled example:

```markdown
# План нормализации

Статус плана: черновик
Ветка по умолчанию: master
Язык workspace: ru (README.md, REPOSITORIES.md и заметки в design/ написаны по-русски)

## Основа

| Source | Action | Target | Status | Note |
|---|---|---|---|---|
| kit workspace 0.3.0 | adopt | .agents/kit.json | todo | workspace_name=legacy-backoffice, forge=gitlab, language=ru |
| README.md, legacy-app/README.md | merge | AGENTS.md | todo | project description and folder rows under the kit sections |
| README.md | merge | README.md | todo | purpose, contacts and links for people |
| REPOSITORIES.md | merge | REPOSITORIES.md | todo | hand-written text only; the table rows go to repos.json |
| legacy-app/ARCHITECTURE.md | merge | docs/ARCHITECTURE.md | todo | kit sections filled from the source |
| REPOSITORIES.md, tools/clone-repos.sh | convert | repos.json | todo | 29 repositories in both lists; roles: Бэкенд → backend, Фронтенд → frontend, Аналитика → analyst |
| legacy-app/design/tracker-proxy.md | adr | docs/adr/0002-tracker-proxy.md | todo | accepted: «Статус: **утверждён** 2026-09-02» |
| legacy-app/design/export-notes.md | move | docs/design/export-notes.md | todo | no status line |
| legacy-app/design/_TEMPLATE.md | remove | - | todo | template, not an ADR; links point to .agents/templates/adr.md |
| legacy-app/diagrams/operations-flow.md | move | docs/diagrams/operations-flow.md | todo | key diagram:operations-flow |
| tools/tracker/mcp-server | move | tracker/mcp-server | todo | tracker tooling |
| tools/vault/ | move | scripts/vault/ | todo | unchanged; variable names go to .agents/env.schema.json |

Открытая работа: none.

## Домены

### operations

| Source | Action | Target | Status | Note |
|---|---|---|---|---|
| legacy-app/operations/stories/03-operation-days/ | move | domains/operations/streams/migration/stories/operation-days/ | todo | PoC story: stories/operation-days.md |
| ~/specs/legacy-backoffice/architecture/poc/operations-map/stories/notices.md | convert | domains/operations/streams/migration/stories/notices/story.md | todo | no legacy folder |
| legacy-app/operations/stories/01-init/ | remove | - | todo | no PoC story (stories/init.md dropped in PoC d76f6bd); owner decision: remove; reason: «There is no `story:operations/init`: the MFE scaffold, host registration and menu are not planned as a story; `scaffold.json` stays as the input. Tracker story DEMO-101 is not used by this map.» (MAP.md line 62 at PoC commit 6994fef, section «No init story») |

Открытая работа:
- origin/feature/operations-stories, merge request !3: changes legacy-app/operations/stories/. normalize-operations waits for its merge or the owner's word.

## Личное

| Source | Action | Target | Status | Note |
|---|---|---|---|---|
| handoffs/2026-08-30-session.md | personal | .local/handoffs/2026-08-30-session.md | todo | contains /Users/ paths; proposal: remove from git, the author keeps it |
| - | check | - | todo | closes the base phase: check.py exits 0, 29 rows in the REPOSITORIES.md table |

## Вне change

| Source | Action | Target | Status | Note |
|---|---|---|---|---|
| templates/bff-agents/ | keep | templates/bff-agents/ | todo | until workspace-repo-kits |

## Открытые вопросы

- legacy-app/design/cache-notes.md: status word «на паузе» has no mapping. Source: line 3.
```

Never put a secret value, token or `.local/env` content into the plan.

### Approval

Steps 1 to 3 are the first approval in a worktree. Step 5 is a re-approval. Choose by the approved copy that step 3 saves: when `cd <wt> && test -f "$(git rev-parse --git-path normalize-plan-approved.md)"` fails, use steps 1 to 3; when it succeeds, use step 5. Rows may already be applied without any row being `done`, for example after `adopt` stopped on a conflict, so never choose by the row statuses.

1. Run `cd <wt> && git status --porcelain=v1 --untracked-files=all`. It must list only `docs/normalize/plan.md`. Show the output and the plan to the owner.
2. Ask the owner to approve the plan, and to answer each open question or exclude its row.
3. Apply nothing until the owner explicitly approves. Then set `Статус плана: утверждён <YYYY-MM-DD>` and save the approved copy: `cd <wt> && cp docs/normalize/plan.md "$(git rev-parse --git-path normalize-plan-approved.md)"`. The copy lives in the worktree's git directory, outside the workspace tree, and is the baseline of step 5.
4. When the owner changes a row, edit the plan and ask for approval again before applying anything. The same holds for every change that needs approval after the plan was approved: a new row, a changed source, action or target, or a new open question. In the same edit, set the status line back to `Статус плана: черновик`. Apply no row until the owner approves again and the line says `утверждён <YYYY-MM-DD>`. A record needs no new approval: a row status, or a note line that changes no source, action or target. Examples are the conflicts of the `adopt` row, or an approver or date the owner named for an `adr` row.
5. Re-approval, when the plan went back to `черновик` and the approved copy exists. The worktree may already hold applied rows, so skip the `git status` check of step 1. Instead:
   - Show the owner the plan diff since the last approval: `cd <wt> && git diff --no-index -- "$(git rev-parse --git-path normalize-plan-approved.md)" docs/normalize/plan.md`. In the base phase the plan is not committed yet, so `git diff -- docs/normalize/plan.md` would print nothing. Exit 1 only means the files differ.
   - Show the rows already done: `cd <wt> && grep -n "| done |" docs/normalize/plan.md`.
   - Ask the owner to approve the changes, and to answer each new open question or exclude its row.
   - Apply nothing until the owner explicitly approves. Then set `Статус плана: утверждён <YYYY-MM-DD>`, save the approved copy again with the `cp` command of step 3, and continue with the first `todo` row.

## Phase 2: base

Run this phase in `<wt>` on `normalize-base`, and only when the plan says `Статус плана: утверждён`. When a step below adds a row or an open question, set the plan back to `Статус плана: черновик` by «Approval» step 4, and apply no further row until the owner approves again by «Approval» step 5. Apply the rows in plan order: «Основа» top to bottom, then «Личное» top to bottom. Phase 1 wrote them in the order of the steps below, and «Resume by plan status» uses the same order. Apply each row by the step for its action. Verify it by its check in «Resume by plan status», then set its status to `done`. Domain folders stay in place on this branch, for example `legacy-app/operations/`. Never move, convert or delete a file inside them. «Link repair» may only fix links in them that point to paths this phase moved or removed.

1. The `adopt` row: adopt the kit.
   - Parameters: `workspace_name`, `title`, `forge`, `id_pattern`, `tracker_url`, `language`. Take `language` from the `Язык workspace:` line of the approved plan. Take `forge` from the host of `cd <wt> && git remote get-url origin` by the rules of `skills/workspace-create/SKILL.md` (Collect, item 4). Check `id_pattern` against a real tracker id found in the workspace with the command from that list (item 6). Ask the owner, one question per message, for every value no source gives.
   - Run, with each value in single quotes: `~/.config/opencode/bin/workspace-kit adopt <wt> --param workspace_name='legacy-backoffice' --param title='Legacy backoffice' --param forge='gitlab' --param id_pattern='(DEMO|SPPP)-\d+' --param tracker_url='https://tracker.example/i/{id}' --param language='ru'`. adopt stores the parameters, `language` included, in `.agents/kit.json`.
   - On exit 2, show the owner the message, fix the value together and rerun. When `<wt>/.agents/kit.json` already exists, adopt ran in an earlier run and refuses to run again. Skip the command and take the conflicts from the row note.
   - When the note has no conflicts record (the run stopped between adopt and the record), rebuild the list. adopt found a conflict in two cases. Either a kit path existed on the default branch with different content, comparing templated files after parameter substitution. Or one of the path's parent paths was a file. This command repeats those rules against `origin/<default>`, with the parameters from `.agents/kit.json`, and prints the same sorted `conflict:` lines as adopt did:
     ```
     cd <wt> && python3 -c '
     import json, os, subprocess, sys
     kit, ref = os.path.expanduser("~/.config/opencode/kits/workspace"), sys.argv[1]
     meta = json.load(open(os.path.join(kit, "kit.json")))
     params = json.load(open(".agents/kit.json"))["params"]
     def git(*args):
         r = subprocess.run(["git"] + list(args), capture_output=True)
         return r.stdout if r.returncode == 0 else None
     conflicts = []
     for root, dirs, names in os.walk(kit):
         dirs[:] = [d for d in dirs if d != "__pycache__"]
         for name in names:
             rel = os.path.relpath(os.path.join(root, name), kit).replace(os.sep, "/")
             if rel == "kit.json":
                 continue
             data = open(os.path.join(kit, rel), "rb").read()
             if rel in meta.get("templated", []):
                 text = data.decode("utf-8")
                 for key, value in params.items():
                     text = text.replace("{{" + key + "}}", json.dumps(value)[1:-1] if rel.endswith(".json") else value)
                 data = text.encode("utf-8")
             parts = rel.split("/")
             blocked = any((git("cat-file", "-t", ref + ":" + "/".join(parts[:i])) or b"").strip() == b"blob" for i in range(1, len(parts)))
             kind = (git("cat-file", "-t", ref + ":" + rel) or b"").strip()
             if blocked or (kind and (kind != b"blob" or git("show", ref + ":" + rel) != data)):
                 conflicts.append(rel)
     for rel in sorted(conflicts):
         print("conflict: " + rel)
     ' origin/<default>
     ```
   - Read the output. Every `conflict: <path>` line is a kit file that already exists with different content; adopt left the existing file alone and did not copy the kit version. Every other kit file was copied, and `.agents/kit.json` was written.
   - A conflict on a templated path (the `templated` list in `~/.config/opencode/kits/workspace/kit.json`: `AGENTS.md`, `README.md`, `REPOSITORIES.md`, `docs/ARCHITECTURE.md`, `tracker/tracker.json`) is handled by its `merge` row in step 3. A templated conflict without a `merge` row is a deviation, as below.
   - Any other conflict stops the run. Show both versions with `diff <wt>/<path> ~/.config/opencode/kits/workspace/<path>` and ask the owner. Write the decision as a new `merge` row directly after the `adopt` row, set the plan back to `черновик`, and get it approved again before you apply the row. For `.gitignore` the usual proposal is to append the kit lines that are missing: when `.claude/` or `CLAUDE.md` stays ignored, `check` reports the generated `CLAUDE.md` as missing.
   - Record the conflicts in the `adopt` row note, for example `workspace_name=legacy-backoffice, forge=gitlab, language=ru; conflicts: .gitignore, README.md, REPOSITORIES.md`. A record needs no new approval («Approval» step 4). Never copy the absolute `<wt>` path into the plan.

   Example output:
   ```
   conflict: .gitignore
   conflict: README.md
   conflict: REPOSITORIES.md
   adopted kit workspace 0.3.0 into /Users/owner/work/legacy-backoffice-workspace-normalize-base
   ```

2. The migration rows: only in a migration base phase, where the stamp on `origin/<default>` is older than `0.5.0`. Six rows, applied in this order after the `adopt` row and its `merge` rows and before the closing `check` row. The tree is already the kit tree of an older kit: there is no legacy container, existing ADRs stay in `docs/adr/`, and `.local/` is never touched.

   The `adopt` row of a migration: the old stamp makes adopt refuse to run, so this row replaces it. Print the old parameters, remove the stamp, and run the adopt command of step 1 with them:
   ```
   cd <wt> && python3 -m json.tool .agents/kit.json
   cd <wt> && git rm -q .agents/kit.json
   ```
   Take `language` from the «Язык workspace» line of the plan when the old stamp has none, and ask the owner, one question per message, for a value no source gives. adopt copies the `0.5.0` kit files over the old ones and prints the conflicts; a templated conflict becomes a `merge` row as in step 1, and on a resume with `.agents/kit.json` already at `0.5.0` the command is skipped by the step 1 rule. Two conflicts never become `merge` rows in a migration: `repos.json` resolves by the `roles off` row (the workspace's own manifest stays), and `tracker/trackers.json` resolves by the `trackers convert` row. The `0.5.0` kit dropped `work/.gitkeep` and `.agents/templates/work-record.md`, and no kit file replaces them; remove both in this row when they exist: `git rm -f work/.gitkeep .agents/templates/work-record.md`. Record the conflicts in the `adopt` row note.

   - `projectize`: ask the owner for the project key `<key>`; the default, and the usual answer, is the workspace name from the stamp. Then move the domains and create the project file:
      ```
      cd <wt> && mkdir -p projects/<key> && git mv domains projects/<key>/domains
      cd <wt> && cp .agents/templates/project.md projects/<key>/PROJECT.md
      ```
      Fill `PROJECT.md`: `<project>` in the frontmatter and `<name>` in the H1 are `<key>`; ask the owner for the purpose when no entry document gives one.
   - `retarget`: rewrite every `story:`, `stream:`, `domain:`, `screen:` and `mockup:` key of the moved tree to the project-prefixed form — `story:operations/documents` becomes `story:<key>/operations/documents`. A key that already carries `<key>/` stays as it is:
      ```
      cd <wt> && python3 -c '
      import pathlib, re, sys
      pattern = re.compile(r"(?<![\w/-])((?:story|stream|domain|screen|mockup):)(?!%s/)" % re.escape(sys.argv[1]))
      for path in sorted(pathlib.Path("projects/" + sys.argv[1]).rglob("*")):
          if not path.is_file() or path.suffix not in (".md", ".json"):
              continue
          text = path.read_text(encoding="utf-8")
          new = pattern.sub(r"\1%s/" % sys.argv[1], text)
          if new != text:
              path.write_text(new, encoding="utf-8")
      ' <key>
      ```
      Then `cd <wt> && python3 tools/generate.py` regenerates `.agents/index.json` with the prefixed keys. Only the moved tree is rewritten: the kit files were merged or replaced at `adopt`, and an old key in another hand-written file is existing content, handled by «Findings in existing content».
   - `work merge`: for every `work/<ID>/record.md`, in sorted order:
      - Read the record's `task:` field and resolve the id: the task is the story or workspace task whose frontmatter carries `tracker: <ID>`, found with `cd <wt> && grep -rl -e "^tracker: <ID>$" --include=story.md --include=task.md projects tasks`.
      - When exactly one task resolves, move the record into that task's folder as `work.md`, take `recorded` from the record's last commit date, and replace the `task:` line with it:
        ```
        cd <wt> && git log -1 --format=%as -- work/<ID>/record.md
        cd <wt> && git mv work/<ID>/record.md <task folder>/work.md && rmdir work/<ID>
        cd <wt> && python3 -c '
        import sys
        path, task, date = sys.argv[1], sys.argv[2], sys.argv[3]
        text = open(path, encoding="utf-8").read()
        open(path, "w", encoding="utf-8").write(text.replace("task: %s\n" % task, "recorded: %s\n" % date, 1))
        ' <task folder>/work.md <ID> <date>
        ```
        Then give that task's frontmatter the stamp of `status stamp` below, with `done` instead of `waiting`.
      - When the record resolves to no task — no `task:` field, or no frontmatter carries the id — write a `keep` row for it, for example `| work/TASK-9/record.md | keep | - | todo | no task carries TASK-9 |`, and change nothing: the file stays in place for the owner. Never delete an unresolved record.
      - When the id matches several tasks, that is an open question and the record stays in place until the owner resolves it.
   - `status stamp`: every story that got no work record keeps its queue place as `waiting`. When the story frontmatter has no `status` line, insert three lines directly after its `type:` line — `status: waiting`, then an empty `owner:`, then an empty `started:`; `task-start` fills the two. A story that already carries a `status` line stays as it is.
   - `roles off`: `cd <wt> && git rm -r -q .agents/roles`, and drop the `roles` key from every `repos.json` entry:
      ```
      cd <wt> && python3 -c '
      import json
      data = json.load(open("repos.json"))
      for entry in data["repositories"]:
          entry.pop("roles", None)
      open("repos.json", "w", encoding="utf-8").write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
      '
      ```
      The generated Roles column of `REPOSITORIES.md` disappears at the next `tools/generate.py` run.
   - `trackers convert`: ask the owner for the tracker key (propose `main`, the kit default), then turn `tracker/tracker.json` into `tracker/trackers.json` and remove the old file:
      ```
      cd <wt> && python3 -c '
      import json, sys
      old = json.load(open("tracker/tracker.json"))
      data = {"trackers": [{"key": sys.argv[1], "id_pattern": old["id_pattern"], "url": old["url"]}]}
      open("tracker/trackers.json", "w", encoding="utf-8").write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
      ' <key>
      cd <wt> && git rm -q tracker/tracker.json
      ```
      This row also resolves the `tracker/trackers.json` conflict of the `adopt` row: the workspace's own `id_pattern` and `url` win over the rendered kit file.

3. The `merge` rows: merge each templated file with the sources in its row. The kit version of `<path>` is `~/.config/opencode/kits/workspace/<path>` with `{{title}}` and `{{workspace_name}}` replaced by the adopt parameters. When `<path>` had no conflict, adopt already copied that version into `<wt>`. Merge only from the sources named in the row; another source is a deviation. Never copy a home path. Write a relative path or a key instead, or ask the owner. A source file of a `convert` row leaves git only when the plan has a `remove` row for it.
   - `AGENTS.md`: keep every kit section, in the kit's order and wording: «Start here», «Folder map», «Personal layer», «Keys and links», «Skills», «Changes», «More». Under the title, add what the workspace is, taken from the entry documents (for example `README.md` and `legacy-app/README.md`). Add a «Folder map» row for each project folder the kit table lacks, for example `| legacy-app/ | domains not yet under the lifecycle | normalize-<domain> merge requests |`. When an existing instruction contradicts a kit rule, do not copy it; list it for the owner.
   - `README.md`: start from the kit version. Keep the project text meant for people from the existing file, such as purpose, contacts and useful links. Put it as extra sections after «Where things are» and before «Changing the workspace», so the kit sections «Changing the workspace» and «Optional tools» stay last.
   - `REPOSITORIES.md`: the text above `<!-- repos:begin -->` is the existing hand-written description: what each repository or group does and how they depend on each other. Between the markers keep only the kit header; step 10 fills in the rows. The rows of the old hand-kept table go into `repos.json` in step 4, not into the text.
   - `docs/ARCHITECTURE.md`: keep the kit sections «Purpose», «Systems», «Domains», «Decisions», «Diagrams» and replace their placeholder lines with text from the source (for example `legacy-app/ARCHITECTURE.md`). A source section that fits none of them goes after «Diagrams» under its own heading. Link with a key only when its target exists on this branch; `domain:` keys do not resolve until the domain phases.
   - `tracker/tracker.json`: keep the kit version with the parameters.

4. The `convert` row for `repos.json`: write it from the repository lists named in the row, one entry per repository. Use the key order and JSON format of step 7 in `.agents/skills/repos-add/SKILL.md`.
   - `name`: the name in the table row.
   - `remote`: the URL in the clone script line for that name.
   - `forge`: from the remote host, by step 3 of `.agents/skills/repos-add/SKILL.md`.
   - `default_branch`: the `-b <branch>` or `--branch <branch>` value of the clone line. Otherwise use the output of `git ls-remote --symref <remote> HEAD`, as in step 5 of repos-add. When that fails, it is an open question.
   - `roles`: role names from `ls .agents/roles/`, mapped from the table group by the mapping in the plan row note. A group without a mapping is an open question.
   - `summary`: the description cell of the table row, on one line and without `|`. A row without a description is an open question.
   - Disagreements between the lists are never resolved by you. Examples: a repository in only one list, one name with two remotes, two names with one remote, a clone-script name that differs from the last segment of the remote. Write each under «Открытые вопросы» with both sources and line numbers, set the plan back to `черновик`, and get it approved again.
   - Count the entries: `python3 -c 'import json; print(len(json.load(open("repos.json"))["repositories"]))'`. The result must equal the number of distinct repositories in the lists, for example `grep -c "git clone" tools/clone-repos.sh`.

   Example. Table row `| legacy-app-bff-operations | Бэкенд | BFF операций АРМ |` and clone line `git clone -b master git@gitlab.example.com:abs/legacy-app-bff-operations.git`, with the plan note mapping `Бэкенд` to `backend`, give:
   ```json
   {
     "name": "legacy-app-bff-operations",
     "remote": "git@gitlab.example.com:abs/legacy-app-bff-operations.git",
     "forge": "gitlab",
     "default_branch": "master",
     "roles": [
       "backend"
     ],
     "summary": "BFF операций АРМ"
   }
   ```

5. The `adr` rows: convert design notes into ADRs, one row at a time.
   - Run `git mv <source> docs/adr/NNNN-<slug>.md` with the target from the plan, so git history follows the note. The slug uses only `a-z`, `0-9` and `-`. The numbers start at `0001`, in the order fixed in Phase 1: by the note's date, then by file name.
   - Rewrite the file into the shape of `.agents/templates/adr.md`. Frontmatter:
     - `key: adr:NNNN`;
     - `title:` the note's H1 text, in its original language;
     - `status:` the value from the plan row, by «ADR status mapping»;
     - `date:` the note's own date: the date in its status line, else its date line, else the date the plan row note gives. When none of them gives a date, ask the owner and record the answer in the row note. Never invent a date and never use today's date;
     - `affects:` only keys that resolve on this branch, such as `repo:` names from `repos.json`; otherwise `[]`.
   - An `accepted` ADR also needs `approved: {by: <name>, date: YYYY-MM-DD}`, or `check` reports it. Take both values only from the note, for example a line «Утвердил: Иванов И.» and the date in the status line. When the note names no approver, ask the owner and write the answer into the row note. Never invent a name.
   - Body: the heading `# ADR-NNNN: <title>`, then `## Context`, `## Decision`, `## Alternatives` and `## Consequences`, filled with the note's own paragraphs under the section they belong to. Keep the wording. Put rejected options into the `| Option | Why not |` table only when the note names them. Write `Нет в исходной заметке.` under a section the note has nothing for. Note text that fits no section stays after `## Consequences` under its original heading. The status line leaves the body; the frontmatter carries it.
   - Apply «Link repair» for the source path.

   Example. The note `legacy-app/design/tracker-proxy.md` starts with `# Прокси трекера` and `Статус: **утверждён** 2026-09-02`, and its row says `docs/adr/0002-tracker-proxy.md`, approved by Иванов И. The ADR starts:
   ```
   ---
   key: adr:0002
   title: Прокси трекера
   status: accepted
   date: 2026-09-02
   affects: []
   approved: {by: Иванов И., date: 2026-09-02}
   ---
   # ADR-0002: Прокси трекера
   ```

6. The `move` rows to `docs/design/` and the `remove` rows.
   - Move: `git mv legacy-app/design/export-notes.md docs/design/export-notes.md`, with the target from the row. The content stays unchanged.
   - Remove: `git rm -r legacy-app/design/_TEMPLATE.md`. Never remove a path that has no `remove` row.
   - Apply «Link repair» for the source path. A link to a removed file points to the replacement named in the row note, for example `.agents/templates/adr.md`. When the note names none, leave the link unchanged and list it for the owner by «Findings in existing content».

7. The diagram `move` rows: move the diagrams to `docs/diagrams/`.
   - Run `git mv <source> docs/diagrams/<name>.<ext>` for each row. `<name>` is the stem of the plan target.
   - A Markdown diagram `docs/diagrams/<name>.md` gets the key `diagram:<name>` from `tools/generate.py`. Link to it as `[diagram:<name>](<relative path>)`.
   - Other files (`.png`, `.svg`, `.drawio`, `.puml`) move unchanged next to the Markdown file that embeds them; they get no key of their own.
   - A diagram kept outside git, such as a Miro or draw.io board URL from the old catalogue, is registered in `docs/diagrams/external.json` under a `diagram:<name>` key. A `.md` file with the same name wins over the URL.
   - A catalogue produced by a project script moves with its row. Change the script's output path only when the plan row says so.
   - Apply «Link repair» for each source path.

   Example `docs/diagrams/external.json`:
   ```json
   {
     "diagrams": [
       {"key": "diagram:operations-context", "url": "https://miro.example.com/app/board/uXjVabc123/"}
     ]
   }
   ```

8. The `move` rows into `tracker/` and `scripts/`: move tracker tooling into `tracker/` and project scripts into `scripts/`; `tools/` belongs to the kit.
   - `tracker/` already holds the kit's `tracker/tracker.json`, so move entries one by one: `git mv tools/tracker/mcp-server tracker/mcp-server`, `git mv tools/tracker/openapi.yaml tracker/openapi.yaml`. When a source entry is named `tracker.json`, stop and ask the owner.
   - Move each project script by its row, for example `git mv tools/clone-repos.sh scripts/clone-repos.sh`. Move `tools/vault/` to `scripts/vault/` unchanged with `git mv tools/vault scripts/vault`, and never open its maps.
   - Declare each variable name found in Phase 1 step 6 in `.agents/env.schema.json` as `{"name": "VAULT_ADDR", "issued_by": "...", "how_to_get": "..."}`. Take `issued_by` and `how_to_get` from script comments or documentation; ask the owner when neither gives them. Names only, never values.
   - Apply «Link repair» for each source path. Scripts often name their own paths, such as `tools/vault/`.
   - After the last of these rows, `cd <wt> && git ls-files --cached --others --exclude-standard tools | grep -v -e '^tools/check.py$' -e '^tools/generate.py$' -e '^tools/wslib/'` must print nothing.

9. The «Личное» rows except the last: apply the owner's decisions on personal files, one row at a time.
   - Promote to `docs/`: `git mv <source> docs/<target>`. A home path left in the text is existing content; step 10 handles it.
   - Move to `work/<TASK-ID>/`: `git mv <source> work/<TASK-ID>/<file>`. The folder name must match `id_pattern`, and `check` requires `work/<TASK-ID>/record.md`. Create it from `.agents/templates/work-record.md` and fill it only from the file's text; ask the owner for fields no text gives.
   - Remove from git: `git rm <source>`. List each such file in the hand-off report. Tell the owner that its author copies it into `.local/<target>` in their own checkout before pulling the merged default branch, because that pull deletes it.
   - Apply «Link repair» for the source path of every moved or removed file.

10. The `check` row, the last row of «Личное»: generate and check.
   - `check` verifies only key links (`key-resolve`), not plain relative links. First run the old-path search of «Link repair» once for the source path of every `done` row of this phase that moved or removed a path. It never searches for the file name, so a link already repaired to the new path, such as `[clone](scripts/clone-repos.sh)`, is not a hit. The gate passes when every printed line is one of two exceptions that «Link repair» left unchanged and listed. One is a link to a removed file without a replacement, listed for the owner (step 6). The other is a line that names a different path which only ends in the old one, such as `docs/other.md:1:see docs/tools/clone-repos.sh`, listed for the hand-off report with that reason («Link repair» step 2). Any other printed line is an unrepaired reference: fix it by «Link repair» and search again.
   - Run `cd <wt> && python3 tools/generate.py`, then `python3 tools/check.py; echo "exit $?"`. Each finding is a line `path:line rule-id message`.
   - Count the generated table rows: `python3 -c 'import re; t = open("REPOSITORIES.md").read(); b = t.split("<!-- repos:begin -->")[1].split("<!-- repos:end -->")[0]; print(len(re.findall(r"^\| ", b, re.M)) - 1)'`. It must print the entry count of step 4, for example `29`.
   - Fix the findings in content this phase wrote: the merged templated files, `repos.json`, `docs/adr/`, `docs/diagrams/external.json`, `.agents/env.schema.json`, new work records and repaired links; in a migration also the prefixed keys, `tracker/trackers.json`, `projects/<key>/PROJECT.md` and the stamped story frontmatter. Run both commands again until no finding names that content. Example: `docs/adr/0002-tracker-proxy.md:1 adr accepted ADR lacks approved with by and date` is yours; step 5 says where the values come from.
   - A finding in a file this phase moved without changing its content, or in any other existing file, is existing content, for example `legacy-app/clients/notes.md:14 home-path absolute home path; use a relative path or a key`. Follow «Findings in existing content» in `## Rules`.
   - The base is complete only when `python3 tools/check.py` prints nothing and `exit 0`. Mark the row `done`, then go to `## Hand-off`.

### Link repair

Every row that moves or removes a path applies this to its source path (`<old>`) before the row is marked `done`.

The path map is the plan: each `done` row of this phase that moved a path maps its source to its target, and the current row maps `<old>` to its target. A path under a moved folder maps the same way; for example `tools/vault/get.sh` maps to `scripts/vault/get.sh`.

1. Run the old-path search. It prints each line that still refers to `<old>`. One kind is a relative link target that resolves to `<old>`, or to a path under it, from the linking file's current place in the worktree: an inline link `[x](path)`, a reference definition `[x]: path`, or an HTML `src="path"` or `href="path"` attribute. The other kind is a literal mention of `<old>` in any tracked or new file, scripts, `.gitignore` and CI files included. It skips `docs/normalize/plan.md`, whose source column records old paths on purpose. It never matches the file name alone, so links already repaired to the new path are not printed. It also prints a line that names a different path which only ends in `<old>`; step 2 says how to handle it.
   ```
   cd <wt> && python3 -c '
   import os, re, subprocess, sys
   old = sys.argv[1].rstrip("/")
   folder = "--folder" in sys.argv[2:]
   mention = re.compile(r"(?<![\w.-])" + re.escape(old) + (r"/[\w.-]" if folder else r"(?![\w.-])"))
   files = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], capture_output=True, text=True).stdout.splitlines()
   for f in files:
       if f == "docs/normalize/plan.md" or not os.path.isfile(f):
           continue
       try:
           lines = open(f, encoding="utf-8").read().split("\n")
       except (UnicodeDecodeError, OSError):
           continue
       for n, line in enumerate(lines, 1):
           targets = re.findall(r"\]\(<?([^)\s>#]+)", line) + re.findall(r"^\s{0,3}\[[^\]]+\]:\s*<?([^\s>#]+)", line) + re.findall(r"(?:src|href)\s*=\s*[\x22\x27]([^\x22\x27#\s]+)", line)
           links = [os.path.normpath(os.path.join(os.path.dirname(f), t)) for t in targets if "://" not in t]
           if mention.search(line) or any(p == old or p.startswith(old + "/") for p in links):
               print("%s:%d:%s" % (f, n, line))
   ' tools/clone-repos.sh
   ```
   After `git mv tools/clone-repos.sh scripts/clone-repos.sh` it prints `docs/setup.md:4:[x](../tools/clone-repos.sh)`, `docs/refs.md:7:[clone]: ../tools/clone-repos.sh` and `run.sh:1:sh "$ROOT/tools/clone-repos.sh"`, but not `README.md:2:See [clone](scripts/clone-repos.sh)`.
   Phase 3 step 11 adds `--folder` after the path, as in `' legacy --folder`. A literal mention then counts only when `<old>/` is followed by a path segment, so `docs/a.md:3:see legacy/demo/SITEMAP.md` is printed and the prose word in `docs/a.md:1:The legacy screens move.` is not. Link targets are matched as without the flag.
2. Fix each hit by the path map. Write the new path relative to the linking file's current place: `python3 -c 'import os, sys; print(os.path.relpath(sys.argv[1], os.path.dirname(sys.argv[2])))' docs/adr/0002-tracker-proxy.md legacy-app/operations/README.md` prints `../../docs/adr/0002-tracker-proxy.md`. Keep the link text; when the text is the old path, replace it with the key, as in `[adr:0002](../../docs/adr/0002-tracker-proxy.md)`. The search also prints a line that names a different path which only ends in `<old>`, such as `docs/other.md:1:see docs/tools/clone-repos.sh`. Leave that line unchanged, and list it with this reason for the hand-off report; step 10 accepts it only when it is listed.
3. When the row moved a Markdown file, recompute its own relative links for its new folder. Resolve each link from the file's previous folder. When the result, or a parent of it, is mapped by the path map, use the mapped path. Otherwise keep the resolved path. An ADR moved in step 5 that links to a diagram not yet moved keeps pointing at the diagram's old place; the diagram's row in step 7 then finds and fixes that link.
4. A link whose target is on neither side of the path map, is absent from the worktree and never existed on the default branch (`git cat-file -e origin/<default>:<resolved path>` fails) stays unchanged; follow «Findings in existing content».

## Phase 3: domain

Run this phase in `<wt>` on `normalize-<domain>`, one domain per branch, and only when the plan says `Статус плана: утверждён`. It ends with a green `python3 tools/check.py` and the `python3 tools/check.py --remaining` output in the owner report. Apply the rows under `### <domain>` top to bottom, each by the step for it below; verify each by its check in «Resume by plan status», then set it to `done`. Changes that need approval follow «Approval» step 4, as in Phase 2. Never write into the PoC folder.

Placeholders used below:
- `<language>`: `cd <wt> && python3 -c 'import json; print(json.load(open(".agents/kit.json"))["params"].get("language", "en"))'`, for example `ru`. The profile template `<name>` is `.agents/profiles/ui-migration/<name>.<language>.md` when `<language>` is not `en` and that file exists, otherwise `.agents/profiles/ui-migration/<name>.md`.
- `<poc>`: the PoC folder named in the row sources, for example `~/specs/legacy-backoffice/architecture/poc/operations-map`.
- `<stream>`: the stream name in the row targets, for example `migration` from `EPIC-migration.md`. The stream profile is always `ui-migration`.
- `<old>`: the domain folder on the default branch, for example `legacy-app/operations`.
- `<container>`: the old folder that holds the domain folders, for example `legacy-app`.

Every open question and every quoted source that this phase writes names a workspace file by its path after this branch's moves, not by its old path, for example `domains/demo/docs/SITEMAP.md:13` for a sitemap that step 8 moves from `legacy/demo/SITEMAP.md`. PoC files keep their `<poc>` path, since they never move.

### Domain rows

Filled example for `operations`, language `ru`, with the map taken from the PoC:

```markdown
### operations

| Source | Action | Target | Status | Note |
|---|---|---|---|---|
| ~/specs/legacy-backoffice/architecture/poc/operations-map/map/ | convert | domains/operations/map/ | todo | all files copied (ls <poc>/map/*.md, 14 at PoC commit 6994fef); ## Transitions → ## Переходы, keys unchanged |
| .agents/profiles/ui-migration/MAP.ru.md, ~/specs/legacy-backoffice/architecture/poc/operations-map/MAP.md | convert | domains/operations/MAP.md | todo | Legacy trace → Трасса legacy; Navigation → Навигация; Decisions → Решения; Open questions → Открытые вопросы |
| legacy-app/operations/EPIC-migration.md | convert | domains/operations/streams/migration/epic.md | todo | Границы направления, Функциональность, Порядок переноса → Объём; Результат → Цель; Критерии успешности → Критерии успеха; Что не переносится → Вне объёма; Расхождения с версией аналитика → Открытые вопросы |
| ~/specs/legacy-backoffice/architecture/poc/operations-map/MAP.md, legacy-app/operations/EPIC-migration.md | convert | domains/operations/streams/migration/stream.json | todo | map: «Map, navigation and mockups approved by the user on 2026-09-13» (MAP.md line 138 at PoC commit 6994fef), approver not named; goal: no source |
| legacy-app/operations/stories/03-operation-days/ | move | domains/operations/streams/migration/stories/operation-days/ | todo | PoC story: stories/operation-days.md; story.md text from the legacy folder, frontmatter from the PoC story |
| ~/specs/legacy-backoffice/architecture/poc/operations-map/stories/notices.md | convert | domains/operations/streams/migration/stories/notices/story.md | todo | no legacy folder; story.md from the PoC story |
| legacy-app/operations/stories/01-init/ | remove | - | todo | no PoC story (stories/init.md dropped in PoC d76f6bd); owner decision: remove; reason: «There is no `story:operations/init`: the MFE scaffold, host registration and menu are not planned as a story; `scaffold.json` stays as the input. Tracker story DEMO-101 is not used by this map.» (MAP.md line 62 at PoC commit 6994fef, section «No init story») |
| legacy-app/operations/stories/README.md | move | domains/operations/docs/stories-README.md | todo | hand-kept story index |
| legacy-app/operations/BREAKDOWN.md | move | domains/operations/docs/BREAKDOWN.md | todo | hand-kept; the stream BREAKDOWN.md is generated |
| legacy-app/operations/_api-inventory.md | move | domains/operations/docs/_api-inventory.md | todo | API inventory |
| ~/specs/legacy-backoffice/architecture/poc/operations-map/mockups.json | convert | docs/diagrams/external.json | todo | 18 mockup: keys with the canvas URL |
| ~/specs/legacy-backoffice/architecture/poc/operations-map/mockups/MOCKUPS.md | import | domains/operations/streams/migration/MOCKUPS.md | todo | mockups as text |
| ~/specs/legacy-backoffice/architecture/poc/operations-map/scaffold.json | import | domains/operations/scaffold.json | todo | project scaffold |
| - | check | - | todo | check exits 0; map files = ls <poc>/map/*.md, story folders = ls <poc>/stories/*.md plus the kept legacy folders (14 and 14 at PoC commit 6994fef, none kept); --remaining goes to the owner report |
```

The example shows a mapped `move`, a `convert` and a `remove` story row; step 7 shows a kept folder. With PoC stories the plan has one row per PoC story and one row per legacy story folder, by Phase 1 inventory step 8: for `operations` at PoC commit 6994fef that is 14 PoC stories and 9 legacy folders on master. A legacy folder that is mapped to a PoC story shares its row with that story. The last domain also has the `remove` row of step 11 directly above its `check` row.

### Steps

1. Preconditions, before the first row.
   - The base is merged: Phase 0 step 6 passed for this domain phase, so `origin/<default>` has `.agents/kit.json` and `docs/normalize/plan.md`, and the worktree holds both.
   - Open work: repeat Phase 1 inventory step 7 for the source paths of this domain's rows. Every branch or merge request from «Открытая работа» under `### <domain>` that the commands still show as open blocks the phase. Stop and ask the owner. Continue only after the merge or on the owner's explicit word, and write that word under «Открытая работа», for example `- origin/feature/operations-stories, merge request !3: владелец разрешил начать 2026-09-15.` That line is a record, not a deviation.
   - Rows: every step below that has a source in this domain needs its row under `### <domain>`. When rows are missing, for example because Phase 1 wrote only the stories row, write them in step order, set the plan back to `черновик`, and get approval by «Approval». The same holds for a legacy story folder or PoC story that has no row, and for a legacy story folder whose Note names neither a PoC story nor an owner decision. A folder without a PoC story has only two decisions: a `move` row with `owner decision: keep`, or a `remove` row whose Note quotes the owner's reason in «»; any other row for it stops the run. A `remove` row of a story folder without a quoted reason also stops the run: ask the owner for the reason, write it into the Note, and get approval by «Approval».
   - When the plan is approved and the rows are complete, save the approved copy with the `cp` command of «Approval» step 3 before applying any row. The worktree is new, so a later re-approval in this phase then has its baseline.

2. The map `convert` row from a PoC folder: copy the elements, then localize their table.
   - Run `cd <wt> && mkdir -p domains/<domain>/map && cp <poc>/map/*.md domains/<domain>/map/`. `ls domains/<domain>/map/*.md | wc -l` must equal `ls <poc>/map/*.md | wc -l`, for example `14`.
   - The files stay unchanged, frontmatter and keys included. The only edit is the table heading and header when `<language>` is `ru`: replace the line `## Transitions` with `## Переходы` and the line `| Action | Target |` with `| Действие | Цель |`. The separator and the rows stay as they are:
     ```
     cd <wt> && python3 -c '
     import pathlib, sys
     swap = {"## Transitions": "## Переходы", "| Action | Target |": "| Действие | Цель |"}
     for path in sorted(pathlib.Path(sys.argv[1]).glob("*.md")):
         lines = path.read_text(encoding="utf-8").split("\n")
         path.write_text("\n".join(swap.get(line, line) for line in lines), encoding="utf-8")
     ' domains/<domain>/map
     ```
     For `operations` the last line reads `' domains/operations/map`. Then `grep -l -e '^## Transitions$' -e '^| Action | Target |$' domains/<domain>/map/*.md` must print nothing.
   - A PoC value that records an open item, such as `access: open question` in `bulk-operations.md`, stays as it is. List it under «Открытые вопросы» of `domains/<domain>/MAP.md` in step 4 with its file and line.

   Example, `domains/operations/map/documents.md` after the step:
   ```
   ---
   key: screen:operations/documents
   route: /documents
   kind: place
   section: documents
   parent: 
   access: getDocuments
   label: Список документов
   wave: 1
   story: story:operations/documents
   ---

   ## Переходы
   | Действие | Цель |
   |---|---|
   | row click | screen:operations/document |
   | after ordering print forms | screen:operations/print-forms |
   ```

3. The map `convert` row from a sitemap: write one element file per sitemap row, instead of step 2.
   - Start each file from the profile template `screen` and write it to `domains/<domain>/map/<slug>.md`. Take the slug and the mapping of the sitemap's kind values from the row note, for example `slugs: /clients → clients, /clients/:clientId → client; Вид: место → place`. The note was approved with the plan; a row without a slug, or a kind value without a mapping, is an open question.
   - Fill the fields one by one, from the sitemap columns and the domain's own files only:
     - `key`: `screen:<domain>/<slug>`;
     - `route`: the «Адрес» cell without backticks;
     - `kind`: the «Вид» cell through the mapping in the note;
     - `section`: the sitemap section the row belongs to. When the row note maps that section, write the mapped value, for example `clients` for the note `Раздел «Клиенты» → clients`. Otherwise write the section name from the sitemap heading verbatim, for example `Карточки` for `## Раздел «Карточки»`; never transliterate it or invent a code;
     - `parent`: the key of the screen named in «Откуда попадают» when it names exactly one row of the same table; empty when it names only an entry point such as `меню`;
     - `access`: the operation that the story's `front.md` section «Права» names for this screen. When the screen has no story or no `front.md`, or «Права» names no operation for it, write `access: open question`, as the PoC does in `map/bulk-operations.md`; `check` accepts that value. List it under «Открытые вопросы» of `domains/<domain>/MAP.md` in step 4 with the sitemap file and line;
     - `label`: the «Экран» cell;
     - `wave`: the wave that the sitemap or the story text states;
     - `story`: `story:<domain>/<slug>` of the story folder named in «Стори», for example `02` → `stories/02-clients/` → `story:clients/clients`; empty for `—`.
   - A missing `section` or `parent` is never guessed. Examples: the row lies outside every sitemap section, or «Откуда попадают» names two screens (`список, алерт склейки`). Write each one under «Открытые вопросы» of the plan with the sitemap file and line, and leave that element unwritten until the owner answers. A range of stories such as `02–09`, or a missing `wave`, is handled the same way.
   - The table «Переходы» gets a row only when a source gives both the action label and the target screen. There are two sources: the label quoted in the `front.md` of the screen's story (button or link text, such as «Открыть карточку»), or a labeled edge between the same two screens in a legacy diagram, including one that the base phase already moved to `docs/diagrams/`, such as `list -->|Открыть карточку| card` in `docs/diagrams/flow.md`; name that diagram's current path in the owner report. An action named only in prose, such as «строка открывает карточку», or not named at all, gives no row: list it under «Открытые вопросы» of `domains/<domain>/MAP.md` with its file and line, and never invent a label. A table without rows keeps only its header and separator.
   - The sitemap file itself follows its own `move` row in step 8.

   Example. Sitemap row `| Список клиентов | `/clients` | место | меню | 02 | работает |` under «Раздел «Клиенты»», with `front.md` of `02-clients` naming `getClients` in «Права» and the sitemap stating wave 1, gives the frontmatter of `domains/clients/map/clients.md`:
   ```
   ---
   key: screen:clients/clients
   route: /clients
   kind: place
   section: clients
   parent:
   access: getClients
   label: Список клиентов
   wave: 1
   story: story:clients/clients
   ---
   ```

4. The `convert` row for `domains/<domain>/MAP.md`: the profile template with the PoC's hand-written text.
   - Copy the profile template `MAP` to `domains/<domain>/MAP.md`, with language `ru`: `cd <wt> && cp .agents/profiles/ui-migration/MAP.ru.md domains/<domain>/MAP.md`. Replace every `<domain>` in it with the domain name.
   - «Открытые вопросы» lists, besides the questions of the PoC or the sitemap, every open question the recipes raised for this domain, each with its file and line: a shortened trace cell, an `access: open question` value (steps 2 and 3), a transition without a label source (step 3). It reads `None.` only when neither the sources nor the recipes give a question.
   - With a PoC `MAP.md`, its hand-written text fills the template:
     - Under the template's intro line, write `Заголовок PoC: «<PoC H1 text>».`, then the PoC lines between its H1 and the first `##` heading. For `operations` that line reads `Заголовок PoC: «Operations map (approved by the user on 2026-09-13; hand-built, the workspace generator will own this file after normalize)».`
     - «Трасса legacy»: replace the empty table with the PoC table «Legacy trace». The header becomes the profile columns in `<language>`, `| Группа legacy | Пункт legacy | Маршрут legacy | Цель |`; the rows are copied unchanged. A «Цель» cell must be a map key or `dropped: <reason>`. When a cell holds a key and more text, such as `screen:operations/bulk-operations (open question)`, keep only the key in the cell and write the rest under «Открытые вопросы» with its source line, for example `- screen:operations/bulk-operations: открытый вопрос в трассе PoC (MAP.md, строка 118).` The line number is the one at the PoC commit in use, here 6994fef.
     - The PoC sections «Navigation», «Decisions» and «Open questions» replace the placeholder text of «Навигация», «Решения» and «Открытые вопросы», the template's `None.` included. When the PoC heading holds more than the section name, the first line under the profile heading keeps it, for example `Раздел PoC: «Navigation (decided 2026-09-13, replaces the hub design)».` Every other PoC section, such as «Approval», «Delivery order» or «Mockup rule», goes after «Открытые вопросы» under its own heading, in the PoC order.
     - The PoC tables «Screens» and «Transitions» are not copied: `tools/generate.py` writes those blocks from `map/`. Other text in those two PoC sections goes at the end of «Решения» under `### Screens` or `### Transitions`, followed by the line `Перенесено из раздела «Screens» PoC.` (or «Transitions»). For `operations` that is the 311-П paragraph of «Screens».
     - Keep the text: run the kept-text check of step 5 with `<poc>/MAP.md` as the source. It may print only these lines, which this step replaces on purpose:
       - the headings `## Screens`, `## Transitions`, `## Legacy trace`, `## Navigation`, `## Decisions` and `## Open questions` whose text is exactly that name;
       - the table lines of the PoC «Screens» and «Transitions» sections;
       - the PoC trace header `| Legacy group | Legacy item | Legacy route | Target |`, when `<language>` is not `en`;
       - each trace row whose «Цель» cell was shortened.
       For `operations` from the PoC at commit 6994fef it prints exactly the lines 6-21 (the «Screens» table), 106, 107, 109, 110 (`## Transitions` and its table), 112, 113 (`## Legacy trace` and its header), 118 (the shortened trace row), 140 (`## Decisions`) and 179 (`## Open questions`); line numbers move when the PoC changes, the categories above do not. Lines 5 (`## Screens`) and 108 are not printed: the target has the heading `### Screens`, and the separator `|---|---|---|` also appears in another kept table. Any other printed line is dropped text: put it back and run the check again.
   - Without a PoC `MAP.md`, the sections come from the sitemap:
     - «Трасса legacy» is filled only when the sitemap has legacy columns, that is columns named like the profile columns («Группа legacy», «Пункт legacy», «Маршрут legacy», or `Legacy group`, `Legacy item`, `Legacy route`). Each sitemap row gives one trace row, and its «Цель» is the key of the element step 3 wrote from that row. A sitemap without legacy columns leaves the profile heading with the empty table; name that in the owner report.
     - «Навигация» and «Решения» take the text of the sitemap sections with the same name (`## Навигация` or `## Navigation`, `## Решения` or `## Decisions`) when they exist. Otherwise «Навигация» reads `Нет в исходной карте.` and «Решения» reads `None.`.
     - «Открытые вопросы» follows the rule above.
     - Sitemap text that no recipe maps, such as its H1, its status and approver lines or a lead line like «Волна 1: …», is not copied into `MAP.md`. It stays in the sitemap's moved copy under `domains/<domain>/docs/` (step 8); name those lines with that path in the owner report.

5. The epic `convert` row: `EPIC-*.md` becomes the stream's `epic.md` with the profile epic sections.
   - Run `cd <wt> && mkdir -p domains/<domain>/streams/<stream> && git mv <old>/EPIC-<name>.md domains/<domain>/streams/<stream>/epic.md`.
   - Rewrite it into the sections of the profile template `epic`, in their order: «Цель», «Объём», «Критерии успеха», «Вне объёма», «Открытые вопросы», «Целевые пользователи», «Продукт». Keep the H1 and the lines between the H1 and the first `##` heading.
   - A source section with the same name moves under that heading unchanged. A source section with another name goes under the section that the row note maps it to, after that section's own text. Its heading is lowered to `###`, its own `###` headings to `####`, and the line `Перенесено из раздела «<source heading>» исходного эпика.` follows the new heading. A source section missing from the note is a deviation: the owner decides where it goes.
   - A profile section that gets no text reads `Нет в исходном эпике.`; «Открытые вопросы» without source text reads `None.`. A status line or an approver line moves into `stream.json` in step 6 and leaves the body.
   - Apply «Link repair» for the source path.
   - Check that no text was dropped, after «Link repair». The kept-text check prints every non-empty source line that the target lacks. It compares lines with the text and target of each link blanked, since «Link repair» rewrites both. A heading line counts as kept only when its whole text without the `#` marks equals the whole text of a target heading of any level, so a lowered heading keeps it, or is quoted whole by a target line `Заголовок PoC: «<text>».` or `Раздел PoC: «<text>».`. The same word elsewhere in the target does not keep it:
     ```
     cd <wt> && python3 -c '
     import re, subprocess, sys
     src, dst = sys.argv[1], sys.argv[2]
     if src.startswith("origin/"):
         old = subprocess.run(["git", "show", src], capture_output=True, text=True, check=True).stdout
     else:
         old = open(src, encoding="utf-8").read()
     text = open(dst, encoding="utf-8").read()
     def norm(line):
         line = re.sub(r"\[[^\]]*\]\(<?[^)\s>]*>?\)", "[]()", line)
         line = re.sub(r"^\s{0,3}\[([^\]]+)\]:\s*\S+", r"[\1]:", line)
         line = re.sub(r"((?:src|href)\s*=\s*)([\x22\x27])[^\x22\x27]*\2", r"\1\2\2", line)
         return line.strip()
     new = set(norm(line) for line in text.split("\n"))
     heads = set()
     for line in text.split("\n"):
         if line.startswith("#"):
             heads.add(line.lstrip("#").strip())
         quoted = re.match(r"(?:Заголовок|Раздел) PoC: «(.*)»\.?$", line.strip())
         if quoted:
             heads.add(quoted.group(1))
     for n, line in enumerate(old.split("\n"), 1):
         if not line.strip():
             continue
         if line.startswith("#"):
             kept = line.lstrip("#").strip() in heads
         else:
             kept = norm(line) in new
         if not kept:
             print("%s:%d:%s" % (src, n, line))
     ' origin/<default>:<old>/EPIC-<name>.md domains/<domain>/streams/<stream>/epic.md
     ```
     For `operations` the last line reads `' origin/master:legacy-app/operations/EPIC-migration.md domains/operations/streams/migration/epic.md`. It may print only the status and approver lines that moved into `stream.json`. The `operations` epic has neither, so it prints nothing. That holds even for line 37 (at master 904a621), whose link target `_api-inventory.md` «Link repair» rewrote to `../../../../legacy-app/operations/_api-inventory.md`. Any other printed line is dropped text: put it back and run the check again.

   Example. `## Границы направления`, mapped to «Объём», lands as:
   ```
   ## Объём
   ### Границы направления
   Перенесено из раздела «Границы направления» исходного эпика.

   К operations относятся общебанковские процессы, реестры и отчётность, которые не
   ```

6. The `convert` row for `stream.json`: key, profile, scope and only proven approvals.
   - Write `domains/<domain>/streams/<stream>/stream.json` as `json.dumps(data, indent=2, ensure_ascii=False)` writes it, with a final newline, and the keys `key`, `profile`, `stage`, `scope`, `approvals` in this order.
   - `key`: `stream:<domain>/<stream>`; `profile`: `ui-migration`.
   - `scope`: every element key of the domain, sorted: `cd <wt> && grep -h '^key: ' domains/<domain>/map/*.md | cut -c6- | sort`.
   - `approvals`: a mark `{"stage": ..., "by": ..., "date": ...}` only when a source quoted in the row note proves that approval. Good sources are an approval section such as the PoC «Approval», or a status line with an approver in the epic or the sitemap. `by` is a person's name taken from the source; «the user» or «владелец» names nobody, so ask the owner and record the answer in the row note. `date` is the date in the source, never today. The goal stage approves the epic, the map stage approves the map.
   - `stage`: the stages run `goal`, `map`, `decomposition`, `ready`, `delivery`, `done`. Take the marks that form an unbroken run from `goal`; the stage is the one after the last of them, and `goal` when there is none. A proven approval after a gap is not written, because `check` rejects a mark for a stage later than the current one. Ask the owner about the missing stage and record the answer in the row note. When the owner names no approver and date, the stage stays at the missing stage.
   - When no source records an approval of the map stage, `stream.json` has no `map` mark and its stage is `goal` or `map`.

   Example. The epic says `Статус: **утверждён** 2026-09-03` and `Утвердил: Сидорова А.`, and the sitemap says `Статус: **утверждён** 2026-09-04` with the same approver:
   ```json
   {
     "key": "stream:demo/main",
     "profile": "ui-migration",
     "stage": "decomposition",
     "scope": [
       "screen:demo/card",
       "screen:demo/list"
     ],
     "approvals": [
       {
         "stage": "goal",
         "by": "Сидорова А.",
         "date": "2026-09-03"
       },
       {
         "stage": "map",
         "by": "Сидорова А.",
         "date": "2026-09-04"
       }
     ]
   }
   ```
   For `operations`, the PoC map approval names «the user» and the epic has no status line. Until the owner names the goal approver and date, and the map approver, the file has `"stage": "goal"` and `"approvals": []`.

7. The story rows: one row at a time, then its frontmatter and sections. With PoC stories, the PoC `stories/` list is the target set, and Phase 1 inventory step 8 wrote one row per PoC story and one per legacy story folder. Which legacy folder goes with which PoC story comes only from the row Note that the owner approved with the plan; never match slugs, titles or text yourself.
   - `move` row, a legacy folder mapped to a PoC story: run `cd <wt> && mkdir -p domains/<domain>/streams/<stream>/stories && git mv <old>/stories/<NN-folder> domains/<domain>/streams/<stream>/stories/<poc-slug>`, where `<poc-slug>` is the PoC file name from the Note without `.md`. For `operations`: `git mv legacy-app/operations/stories/03-operation-days domains/operations/streams/migration/stories/operation-days`. `story.md`, `front.md` and `api.md` keep their names and the legacy text; only the frontmatter comes from the PoC story.
   - `convert` row, a PoC story without a legacy folder: run `cd <wt> && mkdir -p domains/<domain>/streams/<stream>/stories/<slug> && cp <poc>/stories/<slug>.md domains/<domain>/streams/<stream>/stories/<slug>/story.md`. The body stays as in the PoC; the frontmatter is reordered by the rule below. No `front.md` or `api.md` is created.
   - A legacy folder without a PoC story has one of two owner decisions in its Note, made before the domain phase; step 1 stops on anything else.
     - `move` row with `owner decision: keep`: run `cd <wt> && mkdir -p domains/<domain>/streams/<stream>/stories && git mv <old>/stories/<NN-folder> domains/<domain>/streams/<stream>/stories/<slug>`, where the slug is the folder name without its numeric prefix (`^[0-9]+-`). `story.md`, `front.md` and `api.md` keep their names and text; the frontmatter comes from the story text by the rule below. When the owner keeps `08-analytics`, the target is `stories/analytics`.
     - `remove` row: run `cd <wt> && git rm -r <old>/stories/<NN-folder>`, and name the folder with the reason quoted in its Note in the owner report. Its text goes nowhere in this phase: an owner who wants it in another story moves it there in the legacy repository before the domain phase, and the plan is approved again.
   - Without PoC stories, every legacy folder has a `move` row to `stories/<slug>/`, with the slug as for a kept folder.
   - Another file in the old `stories/` folder, such as `README.md`, follows its own row. Apply «Link repair» for the source path of every move and removal.
   - Frontmatter: after a move, add it at the top of `story.md`, above the `# [СО]` title, followed by one empty line; after a `convert`, rewrite the PoC block in place. The fields of `story.fields` in `profile.json` come first, in that order: `key`, `type`, `wave`, `tracker`, `scope`, `depends`, `repos`, `decisions`, `mockups`, in the list format of the profile template `story`.
   - With a PoC story `<poc>/stories/<slug>.md` (a `move` row with a PoC story in its Note, or a `convert` row): take its frontmatter block and drop no field. The fields named in `story.fields` come first, in profile order; every other PoC field, such as `epic: DEMO-83` or `stand: stand:stage-du`, follows in PoC order. Each field keeps its PoC lines unchanged, list items included. Nothing else comes from the PoC story; its body stays in the PoC. Its `key` must be `story:<domain>/<slug>`; a different key is an open question.
   - Without a PoC story (a kept legacy folder, or a domain without PoC stories), take each field from the story's own text, or from the sitemap for `scope` and `wave`:
     - `key`: `story:<domain>/<slug>`; `type`: `story`;
     - `wave`: the wave the text or the sitemap states;
     - `tracker`: a tracker id from the text that matches `id_pattern`, such as `DEMO-112`;
     - `scope`: the `screen:` keys the text names, such as the line «Экраны карты: `screen:operations/documents`», or the elements whose `story` field names this story;
     - `depends`, `decisions`, `mockups`: the `story:`, `adr:` and `mockup:` keys the text names;
     - `repos`: a `repo:<name>` key for each `repos.json` name the text names, for example `repo:cards-front` for `cards-front` in «Задачи внутри стори».
     A field the text does not give stays empty when it is in `may_be_empty` (`tracker`, `scope`, `depends`, `repos`, `decisions`, `mockups`): `tracker:` with no value, a list as `[]`. Any other missing field, here `wave`, is an open question with the file and line.
   - An empty `scope` needs `unmapped:` right after it, by «Nothing invented»: a reason quoted from the story text, else stop and ask the owner.
   - Profile sections: every section of `story.sections` in `<language>` that `story.md` lacks as a `## ` heading is added with an empty body: the heading line, then one empty line before the next heading; at the end of the file the heading is the last line. It goes where the profile order puts it: after the text of the closest earlier profile section that the file has, before the next `## ` heading, or before the first `## ` heading when the file has no earlier profile section. Never write text under an added heading, not even `None.`. List each added heading with its story path in the owner report. For example, the PoC stories at commit 6994fef (after d76f6bd) lack «Открытые вопросы», so every `convert` row adds it at the end of the file.
   - After the last story row, `ls -d domains/<domain>/streams/<stream>/stories/*/ | wc -l` must equal `ls <poc>/stories/*.md | wc -l` plus the number of story `move` rows with `owner decision: keep`, when the domain has PoC stories; otherwise the number of story rows. For `operations` at PoC commit 6994fef, with no kept folder, both print `14`.

   Example, `stories/operation-days/story.md` after the `move` row, with the legacy text of `03-operation-days/story.md` and the frontmatter of the PoC `stories/operation-days.md`, whose `epic` and `stand` fields follow the profile fields. The legacy text has all profile sections, so none is added:
   ```
   ---
   key: story:operations/operation-days
   type: story
   wave: 1
   tracker: DEMO-85
   scope:
     - screen:operations/operation-days
   depends: []
   repos:
     - repo:mfe-abs-operations
     - repo:legacy-app-operations-bff
   decisions: []
   mockups:
     - mockup:operations/operation-days
     - mockup:operations/operation-days-close
   epic: DEMO-83
   stand: stand:stage-du
   ---

   # [СО] Операционные дни

   Родительский эпик: «Реализация ARM ABS Operations на базе платформы BackOffice».
   ```

   Example, the end of `stories/notices/story.md` after the `convert` row: the PoC text ends with «Этапы», and the added heading follows it with an empty body. The owner report gets `domains/operations/streams/migration/stories/notices/story.md: добавлен пустой раздел «Открытые вопросы»`:
   ```
   ## Этапы

   - Согласовать с владельцем `report-311p` смысл колонок «В ожидании» и «Создано, но не отправлено»: подписи legacy расходятся с комментариями модели.
   - Согласовать с платформой маскирование `clientId` в аудите маршрута `/notice-events`.

   ## Открытые вопросы
   ```

8. The `move` rows into `domains/<domain>/docs/`: hand-kept breakdown, API inventory and other domain documents.
   - Run `cd <wt> && mkdir -p domains/<domain>/docs && git mv <old>/BREAKDOWN.md domains/<domain>/docs/BREAKDOWN.md` and `git mv <old>/_api-inventory.md domains/<domain>/docs/_api-inventory.md`, with the targets from the rows. The content stays unchanged.
   - Apply «Link repair» for each source path. A moved breakdown that links to `EPIC-migration.md` then points to the stream's `epic.md`.
   - `domains/<domain>/streams/<stream>/BREAKDOWN.md` is generated in step 12; never copy the hand-kept file there.

9. The mockup rows: keys in `docs/diagrams/external.json`, text next to the stories.
   - Add one entry `{"key": "mockup:<domain>/<slug>", "url": "<url>"}` to the `diagrams` list of `docs/diagrams/external.json` for each key in the PoC `mockups.json`. When the file is absent, create it as `{"diagrams": []}` first. Keep existing entries, add new ones in key order, and never add a key twice. The URL is the one the source gives, here the `canvas` value; never build a URL of your own for an artboard.
   - Without a `mockups.json`, a mockup URL named in a story or map document gets the key given in the row note.
   - Count: `python3 -c 'import json; print(sum(e["key"].startswith("mockup:<domain>/") for e in json.load(open("docs/diagrams/external.json"))["diagrams"]))'` must equal the number of keys in `mockups.json`, for example `18`.
   - The `import` row for `MOCKUPS.md`: `cp <poc>/mockups/MOCKUPS.md domains/<domain>/streams/<stream>/MOCKUPS.md`, then `cmp -s` of both files exits 0. The `*.dc.html` and `index.html` sources stay in the PoC unless the plan has a row for them.

   Example `docs/diagrams/external.json` after the step:
   ```json
   {
     "diagrams": [
       {"key": "diagram:operations-context", "url": "https://miro.example.com/app/board/uXjVabc123/"},
       {"key": "mockup:operations/document", "url": "https://claude.ai/code/artifact/d4704601-55e2-48b6-99c5-b2eab30953d1"},
       {"key": "mockup:operations/documents", "url": "https://claude.ai/code/artifact/d4704601-55e2-48b6-99c5-b2eab30953d1"}
     ]
   }
   ```

10. The `import` row for `scaffold.json`: `cd <wt> && cp <poc>/scaffold.json domains/<domain>/scaffold.json`, then `cmp -s <poc>/scaffold.json domains/<domain>/scaffold.json` exits 0. No kit rule reads it; it stays unchanged.

11. The `remove` row for the old container, only in the last domain: the domain phase that runs when every other `### <domain>` of the plan has all its rows `done`.
   - Run `cd <wt> && git ls-files -- <container>/`. Every file it prints must be covered by this row's note. A file the note does not cover stops the run: ask the owner and write the decision as a deviation.
   - Run `cd <wt> && git rm -r <container>`, then apply «Link repair» for `<container>`, with `--folder` after the path in its old-path search. A container name is often a plain word, such as `legacy`, so only path-shaped mentions (`<container>/` followed by a path segment) and link targets count.
   - Remove the `<container>/` row that the base added to «Folder map» in `AGENTS.md`.

   Example for `legacy-app`: `cd <wt> && git ls-files -- legacy-app/` prints `legacy-app/README.md`, `legacy-app/ARCHITECTURE.md` and `legacy-app/EPIC-backoffice-platform-migration.md`, and the row note reads `README.md, ARCHITECTURE.md: merged in the base; EPIC-backoffice-platform-migration.md: owner decision`. Then `git rm -r legacy-app`, «Link repair» for `legacy-app`, and the Folder map row `| legacy-app/ | ... |` leaves `AGENTS.md`.

12. The closing `check` row: generate, check and report the remaining work.
   - Run the old-path search of «Link repair» for the source path of every `done` row of this phase that moved or removed a path, with `--folder` for the container of step 11; the gate is the one of Phase 2 step 10.
   - Run `cd <wt> && python3 tools/generate.py`, then `python3 tools/check.py; echo "exit $?"`.
   - Fix findings in content this phase wrote: `domains/<domain>/map/`, `MAP.md`, `epic.md`, `stream.json`, story frontmatter, `external.json` and repaired links. A finding that needs a missing fact is never fixed by guessing. Example: `domains/operations/streams/migration/stories/bulk-operations/story.md:10 story repos key repo:arm-backoffice-statements does not resolve`. The repository is missing from `repos.json`; ask the owner to add it with repos-add in its own merge request, or to record an open question. A `missing section` finding on a story is yours: add the heading by step 7. Any other finding in story text, `front.md`, `api.md` or a moved document is existing content, for example a link in `front.md` to a file that never existed; follow «Findings in existing content».
   - Counts: `ls domains/<domain>/map/*.md | wc -l` equals `ls <poc>/map/*.md | wc -l`, or without a PoC the elements step 3 wrote. `ls -d domains/<domain>/streams/<stream>/stories/*/ | wc -l` equals `ls <poc>/stories/*.md | wc -l` plus the kept legacy folders, or without PoC stories the story rows. For `operations` at PoC commit 6994fef with no kept folder, every one of these commands prints `14`.
   - The domain is complete only when `python3 tools/check.py` prints nothing and `exit 0`. Then run `python3 tools/check.py --remaining`. It exits 0 and prints the gate failures of the current stage, one per line, for example `stream:operations/migration goal approval: domains/operations/streams/migration/stream.json:1 no approval mark for stage goal with by and a YYYY-MM-DD date`. Put the full output into the owner report, mark the row `done`, and go to `## Hand-off`.

## Rules

### Nothing invented

- Never invent map elements, story fields, approval marks, reasons, links, repository entries or ADR statuses.
- A disputed fact, such as a disputed sitemap row, a story without a screen or an unknown status word, becomes an open question that names its source file and line.
- Write `unmapped` only with a reason quoted from the story text. When the story names no screen and its text gives no reason, stop and ask the owner.

### Findings in existing content

- When `tools/check.py` reports findings, fix only content that normalize wrote.
- A finding in existing content that cannot be fixed without guessing, such as a link in an old document to a file that never existed, stays unchanged. Leave all changes uncommitted, list each finding with its path and line, and ask the owner to fix the content, record an open question or exclude the plan row.
- Print no hand-off commands while such a finding is unresolved.

### Secrets

- Never read or print secret values, tokens or `.local/env`.
- Scripts and maps that handle secrets move unchanged to `scripts/`, for example `tools/vault/` to `scripts/vault/`.
- Declare the variable names they use in `.agents/env.schema.json`; names only, never values.
- No secret value appears in the plan, the output or the merge request text.

### Deviations

- The approved plan is the source of truth. Any deviation is written into `docs/normalize/plan.md` and approved again before it is applied.
- A new row, a changed source, action or target, and a new open question are deviations. A row status and a record in a row note that changes none of them are not deviations; see «Approval» step 4.
- Writing a deviation sets the plan back to `Статус плана: черновик`. While the plan is `черновик`, apply no row, even in a resumed run.

### Open work

- A domain phase does not start while its «Открытая работа» list names a branch or merge request that is not merged, unless the owner explicitly says to proceed. Write the owner's word into the plan.

### No commits

- In the owner's checkout run only the commands Phase 0 allows; never run `git commit`, `git push`, `git stash`, `git reset`, `git checkout` or `git branch -D` there, and never commit or push in the worktree, even when the owner asks; your permissions deny `git commit` and `git push`.
- Leave the changes uncommitted in `<wt>` and print the commands in `## Hand-off`.

### Resume by plan status

Resume only after the owner chose to continue in Phase 0 step 7.

1. Find the `normalize-base` or `normalize-<domain>` worktree by `git worktree list --porcelain` in `<checkout>` and read `<wt>/docs/normalize/plan.md`.
2. When the plan status line is `черновик`, or anything other than `утверждён <YYYY-MM-DD>`, apply no row. When `cd <wt> && test -f "$(git rev-parse --git-path normalize-plan-approved.md)"` fails, return to «Approval» step 1 in Phase 1; when it succeeds, follow «Approval» step 5.
3. Take the first row whose status is `todo`, in plan order: «Основа», then «Личное» for `normalize-base`; the rows under `### <domain>` in «Домены» for `normalize-<domain>`. An interrupted run may have applied it without marking it, so check it against the worktree before applying anything:
   - `adopt`: `test -e <wt>/.agents/kit.json` succeeds means applied. When the row note has no conflicts record, rebuild it by Phase 2 step 1;
   - `merge`: show the target to the owner and ask whether the merge is complete. When it is not, finish it from the current file; never start over from the kit version;
   - `move` or a `personal` move: target exists and source is gone (`test -e <wt>/<target> && ! test -e <wt>/<source>`) means applied; source exists and target is absent means not applied; both or neither present: stop and ask the owner. For a story folder of Phase 3 step 7, also run `head -1 <wt>/<target>/story.md`; when it does not print `---`, the move is applied but the frontmatter is not, so write only the frontmatter by that step;
   - `import`: `cmp -s <source> <wt>/<target>` exits 0 means applied; an absent target means not applied; a different target: show both to the owner and ask;
   - `convert` or `adr`: an absent target means not applied; an existing target: show it to the owner and ask whether it is complete; never overwrite it;
   - `remove` or a `personal` removal: a source that is gone means applied;
   - `keep`: a source that still exists means applied;
   - a migration row: `projectize` checks like a `move` — `projects/<key>/PROJECT.md` exists and `domains/` is gone; `retarget` is applied when no `story:`, `stream:`, `domain:`, `screen:` or `mockup:` key under `projects/` lacks the `<key>/` prefix; `work merge` checks like a `move` per record — `work.md` in the task folder and the record gone; `status stamp` is applied when every story frontmatter carries a `status` line; `roles off` is applied when `.agents/roles/` is gone and no `repos.json` entry carries `roles`; `trackers convert` checks like a `move` — `tracker/trackers.json` exists and `tracker/tracker.json` is gone;
   - `check`, the row that closes a phase: never applied from an earlier run; run it again.
   A row that moves or removes a path may have stopped before its link repair. The `check` row repeats every link search, so those links are caught there.
4. When the row is already applied, mark it `done` without applying it again. Never run a `move` again blindly.
5. Otherwise apply the row, run the same check, and mark it `done` only when the check shows it applied. For a `merge`, `convert` or `adr` row you have just finished in this run, the finished target is the check.
6. Repeat from step 3 with the next `todo` row.

## Hand-off

Run `cd <wt> && git status` and show its output. Report to the owner the branch, the plan rows done in this run, the final `python3 tools/check.py` output and the open questions. For `normalize-<domain>`, also report the full output of `python3 tools/check.py --remaining` and put it into the merge request description.

Then print the commands the owner runs, with every placeholder filled in:

1. For `normalize-base`, the plan goes in its own commit first:
   - `cd <wt> && git add docs/normalize/plan.md && git commit -m "docs(normalize): add normalize plan"`
   - `git add -A && git commit -m "chore(workspace): normalize base under kit <version>"`
2. For `normalize-<domain>`:
   - `cd <wt> && git add -A && git commit -m "refactor(<domain>): move domain under stream lifecycle"`
3. Push and open the merge request by the forge of the `origin` host:
   - `gitlab`: `git push -u origin <branch> -o merge_request.create -o merge_request.target=<default> -o merge_request.title="<title>"`
   - `github`: `git push -u origin <branch>`, then `gh pr create --base <default> --fill`
   - `git`: `git push -u origin <branch>`, then ask the owner to open the request for `<branch>` into `<default>`.
4. After the merge request is merged: `cd <checkout> && git worktree remove <wt>`.

Never run these commands yourself.
