---
name: memory-migration
description: Use when triaging exported Magent and ~/memory facts before importing them into OpenViking
---
# Memory migration triage

Move only useful facts into OpenViking. The export is noisy: session notes, stale code facts, duplicates and secrets.

## Input

`~/.config/opencode/migration/export/triage.md`, produced by `bin/memory-export`, with columns `| # | Source | Title | Proposed | Reason |`. Rows with a detected secret already say `drop` and `contains secret`.

## Rules

Fill Proposed with keep, rewrite or drop and a reason for every row.

- Keep: the user's preferences and feedback with their reason, verified project constraints, pointers to external resources.
- Rewrite: a useful fact that is too long, merged from duplicates, or tied to a session; write the new text in the Reason column.
- Drop session-scoped facts, duplicates, dead projects and anything with a secret.
- A fact that names a file, function, flag or number is checked against the source; if it no longer matches, drop or rewrite it. Use grep in the repository it names.
- Never copy a secret into Reason.

## Approval and import

Show the table to the user. Import only rows the user approved.
Write each approved fact to `~/.openviking/import/<name>.md` and add the directory with
`docker exec openviking ov add-resource /app/.openviking/import --to viking://user/memories/imported --args parse_mode:no_split`.
