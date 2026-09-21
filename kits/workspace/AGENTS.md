# {{title}}

Workspace `{{workspace_name}}` is the shared team workplace: one task queue for everyone, in any tool or without one.

## Start here
1. If the directory `.local/` does not exist, run the `init` skill: follow `.agents/skills/init/SKILL.md`. Never guess paths or repositories.
2. Read `STATUS.md`: pick a `waiting` task, run the `task-context` skill for it, then `task-start` to take it. The queue is the only source of work; do not invent tasks.
3. Keep personal notes in `.local/`, never in shared files.

## Folder map
| Path | Holds | Changed by |
|---|---|---|
| `AGENTS.md`, `README.md` | this map, and the same for people without an agent | reviewed merge requests |
| `STATUS.md` | the task queue; the sections between `status:` markers are generated | people, generator |
| `repos.json` | the repository manifest | `repos-add` |
| `REPOSITORIES.md` | repository context; its table is generated | people, generator |
| `environments.json` | stands by `stand:` key | `extend` |
| `tracker/trackers.json` | trackers: `key`, `id_pattern`, `url` | reviewed merge requests |
| `docs/ARCHITECTURE.md` | system overview | reviewed merge requests |
| `docs/adr/` | workspace decisions, `adr:NNNN` | `decide` |
| `docs/diagrams/` | diagrams, `diagram:<name>` | people |
| `projects/<project>/` | `PROJECT.md`, the project's `adr/` and `domains/` | `extend` |
| `projects/<project>/domains/<domain>/` | domain description and `map/` | `extend` |
| `projects/<project>/domains/<domain>/map/` | map elements, one `screen:` file each; element-owned | the merge request of that element, `extend` |
| `projects/<project>/domains/<domain>/MAP.md` | the domain map; only the tables between `map:` markers are generated | people, generator |
| `projects/<project>/domains/<domain>/streams/<stream>/` | `stream.json`, `epic.md`, `stories/<slug>/story.md`, generated `BREAKDOWN.md` | `extend`, `task-new`, `task-decompose` |
| `tasks/<slug>/` | one workspace task per folder: `task.md`, and `work.md` once it is finished | `task-new`, `task-start`, `work-record` |
| `.agents/` | skills, rules, agents, templates, kit stamp; `index.json` is generated | reviewed merge requests, `extend`; `index.json` by the generator only |
| `.agents/profiles/` | stream profiles: element kinds, story shape, stage gates | kit updates, reviewed merge requests |
| `.agents/repo-kits/<kind>/` | repository kits: `kit.json` and `files/` for the `.agents/` folder of repositories of that kind | reviewed merge requests |
| `.claude/`, `.opencode/`, `.cursor/`, `CLAUDE.md` | tool adapters | generator only |
| `tools/` | `check.py`, `generate.py`, `repo_kit.py` | kit updates |
| `.local/` | your personal layer, ignored by git | you |
| `repos/` | clones of code repositories, ignored by git | `init`, `repos-sync` |

## Personal layer
`.local/` is ignored by git, so search tools may skip it. Open these paths directly:
- `.local/drafts/<ID>.md`: notes while you work on a task;
- `.local/handoffs/`: notes for your next session;
- `.local/env`: your tokens, mode 600; never print, copy or commit its values;
- `.local/repos.json`: your repository selection and deviations.
Anything another person needs moves to a task folder or `docs/`. Shared files never link into `.local/`. Details: `.agents/rules/personal-layer.md`.

## Keys and links
Refer to things by key, written as `[key](relative path)`: `adr:NNNN`, `diagram:<name>`, `repo:<name>` or `repo:<name>:<path>#<operation>`, `stand:<name>`, `domain:<project>/<name>`, `screen:<project>/<domain>/<slug>`, `story:<project>/<domain>/<slug>`, `stream:<project>/<domain>/<stream>`, `mockup:<project>/<domain>/<slug>`, `task:<slug>`, and tracker ids that match exactly one `id_pattern` in `tracker/trackers.json`. Never write absolute home paths or stand addresses as plain text. Details: `.agents/rules/keys-and-links.md`.

## Skills
Follow the steps of a skill file exactly, in order.
| Skill | Use it to |
|---|---|
| `.agents/skills/init/SKILL.md` | set up `.local/`, choose your repositories and clone them |
| `.agents/skills/repos-sync/SKILL.md` | update your clones and see their state |
| `.agents/skills/repos-add/SKILL.md` | add a repository to the manifest |
| `.agents/skills/status/SKILL.md` | read the queue: in progress, waiting, done recently |
| `.agents/skills/task-context/SKILL.md` | gather the context of a story key, `task:` key or tracker id |
| `.agents/skills/task-start/SKILL.md` | take a `waiting` task, or reopen a `done` one |
| `.agents/skills/work-record/SKILL.md` | finish a task: write `work.md` and set the status to done |
| `.agents/skills/task-new/SKILL.md` | create a story in a stream or a workspace task in `tasks/` |
| `.agents/skills/task-decompose/SKILL.md` | split a stream's scope into stories |
| `.agents/skills/decide/SKILL.md` | write an architecture decision record |
| `.agents/skills/extend/SKILL.md` | add an agent, skill, rule, project, domain, stream, map element, stand or variable |
| `.agents/skills/repo-kit-install/SKILL.md` | install a repository kit into a clone |
| `.agents/skills/repo-kit-update/SKILL.md` | update a clone to a newer repository kit version |

## Changes
- Every change to shared files goes through a branch and a merge request, and a person merges it. Details: `.agents/rules/merge-requests.md`.
- Queue hygiene: before taking new work, close or reopen the tasks you already hold; one person works on a task at a time, and a `done` task comes back only through `task-start` with the reason in the merge request description.
- A stream's stage moves one step at a time through a reviewed merge request that adds the approval mark of the stage it closes (moving from `goal` to `map` adds `{"stage": "goal", ...}`); `python3 tools/check.py --remaining` shows the open work of the current stage.
- Generated files change only through `python3 tools/generate.py` or a skill recipe. Details: `.agents/rules/file-ownership.md`.
- When `python3` is available, run `python3 tools/generate.py` and then `python3 tools/check.py` before pushing. Without Python, report "check not run: python3 missing".

## More
- Rules: `.agents/rules/`
- Templates: `.agents/templates/`
