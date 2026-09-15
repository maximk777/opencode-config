# Demo workspace

Workspace `demo` is the shared entry point into this project for every role. Agents read `AGENTS.md`; this file is for people who work without an agent.

## First steps
1. Clone this repository and open it.
2. Follow the steps in `.agents/skills/init/SKILL.md` by hand: pick your role from `.agents/roles/`, create `.local/`, clone your repositories into `repos/`.
3. Read `.agents/roles/<your role>.md`, then `docs/ARCHITECTURE.md` and `REPOSITORIES.md`.

## Where things are
- `repos.json`: the repository manifest; `REPOSITORIES.md` explains the repositories.
- `docs/adr/`: decisions. `docs/diagrams/`: diagrams.
- `domains/`: one folder per domain.
- `work/<ID>/`: records of finished tracker tasks.
- `environments.json`: stands and their addresses.
- `.local/`: your personal notes and tokens, never committed.

## Назначение
Общая точка входа в перенос раздела «Карточки» из legacy.

## Контакты
- Владелец раздела «Карточки»: Сидорова А.

## Ссылки
- [Клонирование репозиториев](scripts/clone-repos.sh)
- [Решение по карточкам](docs/adr/0001-cards.md)
- [Переходы раздела](docs/diagrams/flow.md)

## Changing the workspace
Every change goes through a branch and a merge request, and a person merges it. The skills in `.agents/skills/` list the exact steps, and a person can follow them without an agent.

## Optional tools
With Python 3.9 or newer:
```
python3 tools/generate.py
python3 tools/check.py
```
`generate.py` rebuilds generated files; `check.py` reports problems as `path:line rule-id message`.
