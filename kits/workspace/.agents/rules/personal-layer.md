# Personal layer

- `.local/` holds personal state and is ignored by the workspace `.gitignore`: `drafts/`, `handoffs/`, `env`, `repos.json`.
- Search tools and IDE indexing may skip ignored files, so open `.local/` paths directly.
- `.local/env` has mode 600. Never print its values, copy them into another file or commit them.
- When another person needs something from `.local/`, move it into `work/<ID>/` or `docs/` through a merge request.
- Shared files never link into `.local/`; `python3 tools/check.py` reports such links as `local-link`.
- To keep history of your personal layer, make `.local` a symlink to a repository of your own.
