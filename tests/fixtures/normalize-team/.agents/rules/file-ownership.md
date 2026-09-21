# File ownership

Every file has one owner kind. The kind decides who changes it and how a conflict is resolved.

| Kind | Files | Changed by | On conflict |
|---|---|---|---|
| Task-owned | `work/<ID>/` | the `work/<ID>` branch of that task | cannot conflict |
| Element-owned | `domains/<domain>/map/<slug>.md`, `domains/<domain>/streams/<stream>/stories/<slug>/` | the merge request that changes that element | a person resolves it |
| Generated | `.claude/`, `.opencode/`, `.cursor/`, `CLAUDE.md`, the table in `REPOSITORIES.md`, only the tables between `map:` markers in `domains/<domain>/MAP.md`, `domains/<domain>/streams/<stream>/BREAKDOWN.md`, `.agents/index.json` | `python3 tools/generate.py` or a skill recipe | take the default branch version, then regenerate |
| Shared hand-written | `AGENTS.md`, `README.md`, the text of `REPOSITORIES.md` outside the table, `.agents/rules/`, `.agents/roles/`, `.agents/skills/`, `.agents/agents/`, `.agents/templates/`, `.agents/kit.json`, `.agents/env.schema.json`, `tracker/tracker.json`, `docs/`, `repos.json`, `environments.json`, `stream.json`, `epic.md`, the legacy trace table (the profile's `map_doc` heading in the workspace language: `Legacy trace`, `Трасса legacy` in a Russian workspace) and all other text of `MAP.md` outside the `map:` markers, `MOCKUPS.md` | reviewed merge requests | stop and show both sides to the person |

Never edit a generated file by hand outside a skill recipe. `python3 tools/check.py` reports a mismatch as `generated-stale`.
