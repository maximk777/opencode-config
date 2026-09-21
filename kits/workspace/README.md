# {{title}}

Workspace `{{workspace_name}}` is the shared team workplace: one task queue, one set of repositories. Agents read `AGENTS.md`; this file is for people who work without an agent.

## First steps
1. Clone this repository and open it.
2. Follow the steps in `.agents/skills/init/SKILL.md` by hand: create `.local/`, choose which repositories of `repos.json` to clone into `repos/`.
3. Read `STATUS.md` to see the task queue: pick a `waiting` task, read its context (`.agents/skills/task-context/SKILL.md`), and move it to `In progress` with `.agents/skills/task-start/SKILL.md` before you start working on it.
4. Read `docs/ARCHITECTURE.md` and `REPOSITORIES.md`.

## Where things are
- `STATUS.md`: the task queue — what is in progress, waiting and done recently.
- `tasks/<slug>/`: one workspace task per folder; the finished-work record `work.md` sits next to `task.md`.
- `projects/<project>/`: project description, decisions and domains with their streams and stories.
- `repos.json`: the repository manifest; `REPOSITORIES.md` explains the repositories.
- `docs/adr/`: decisions. `docs/diagrams/`: diagrams.
- `environments.json`: stands and their addresses.
- `.local/`: your personal notes and tokens, never committed.

## Changing the workspace
Every change goes through a branch and a merge request, and a person merges it. The skills in `.agents/skills/` list the exact steps, and a person can follow them without an agent. Before taking new work, close or reopen the tasks you already hold; `STATUS.md` and `.agents/skills/status/SKILL.md` show what is yours.

## Optional tools
With Python 3.9 or newer:
```
python3 tools/generate.py
python3 tools/check.py
```
`generate.py` rebuilds generated files; `check.py` reports problems as `path:line rule-id message`.
