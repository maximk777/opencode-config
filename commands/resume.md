---
description: Resume a change from its files
agent: orchestrator
---
Run ~/.config/opencode/bin/change-state ~/specs/<project> $ARGUMENTS. Then read the decisions.md it names and run one find with target_uri viking://resources/<project>/specs/openspec/changes/$ARGUMENTS before any other memory call; when synced_commit differs from head, trust the files. Continue the change from that state: with change-execute when tasks.md exists, otherwise with the flow skill for the first missing artifact (change-brainstorm, change-spec or change-plan).
