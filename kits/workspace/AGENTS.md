# {{title}}

Workspace `{{workspace_name}}` is the shared entry point for everyone working on this project, in any tool or without one.

## Start here
1. If the directory `.local/` does not exist, run the `init` skill: follow `.agents/skills/init/SKILL.md`. Never guess paths or roles.
2. Read `.agents/roles/<your role>.md` to see what to read first.
3. Keep personal notes in `.local/`, never in shared files.

## Folder map
| Path | Holds | Changed by |
|---|---|---|
| `AGENTS.md`, `README.md` | this map, and the same for people without an agent | reviewed merge requests |
| `repos.json` | the repository manifest | `repos-add` |
| `REPOSITORIES.md` | repository context; its table is generated | people, generator |
| `environments.json` | stands by `stand:` key | `extend` |
| `tracker/tracker.json` | tracker id pattern and issue URL | reviewed merge requests |
| `docs/ARCHITECTURE.md` | system overview | reviewed merge requests |
| `docs/adr/` | decisions, `adr:NNNN` | `decide` |
| `docs/diagrams/` | diagrams, `diagram:<name>` | people |
| `domains/<domain>/` | domain description and map | `extend` |
| `work/<ID>/` | one work record per tracker task | `work-record` |
| `.agents/` | skills, rules, roles, agents, templates, kit stamp; `index.json` is generated | reviewed merge requests, `extend`; `index.json` by the generator only |
| `.claude/`, `.opencode/`, `.cursor/`, `CLAUDE.md` | tool adapters | generator only |
| `tools/` | `check.py`, `generate.py` | kit updates |
| `.local/` | your personal layer, ignored by git | you |
| `repos/` | clones of code repositories, ignored by git | `init`, `repos-sync` |

## Personal layer
`.local/` is ignored by git, so search tools may skip it. Open these paths directly:
- `.local/drafts/<ID>.md`: notes while you work on a task;
- `.local/handoffs/`: notes for your next session;
- `.local/env`: your tokens, mode 600; never print, copy or commit its values;
- `.local/repos.json`: your role and repository deviations.
Anything another person needs moves to `work/<ID>/` or `docs/`. Shared files never link into `.local/`. Details: `.agents/rules/personal-layer.md`.

## Keys and links
Refer to things by key, written as `[key](relative path)`: `adr:NNNN`, `diagram:<name>`, `repo:<name>` or `repo:<name>:<path>#<operation>`, `stand:<name>`, `domain:<name>`, and tracker ids that match `id_pattern` in `tracker/tracker.json`. Never write absolute home paths or stand addresses as plain text. Details: `.agents/rules/keys-and-links.md`.

## Skills
Follow the steps of a skill file exactly, in order.
| Skill | Use it to |
|---|---|
| `.agents/skills/init/SKILL.md` | set up `.local/` and clone your repositories |
| `.agents/skills/repos-sync/SKILL.md` | update your clones and see their state |
| `.agents/skills/repos-add/SKILL.md` | add a repository to the manifest |
| `.agents/skills/work-record/SKILL.md` | record finished work on a tracker task |
| `.agents/skills/decide/SKILL.md` | write an architecture decision record |
| `.agents/skills/extend/SKILL.md` | add an agent, skill, rule, role, domain, stand or variable |

## Changes
- Every change to shared files goes through a branch and a merge request, and a person merges it. Details: `.agents/rules/merge-requests.md`.
- Generated files change only through `python3 tools/generate.py` or a skill recipe. Details: `.agents/rules/file-ownership.md`.
- When `python3` is available, run `python3 tools/generate.py` and then `python3 tools/check.py` before pushing. Without Python, report "check not run: python3 missing".

## More
- Rules: `.agents/rules/`
- Roles: `.agents/roles/`
- Templates: `.agents/templates/`
