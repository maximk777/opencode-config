---
description: Start or continue a change with the orchestrator
agent: orchestrator
---
Start the change flow for: $ARGUMENTS

If ~/specs/<project>/architecture/backlog/$ARGUMENTS.md exists, read it and every file it links before the first question.
Load the change-brainstorm skill first.
If $ARGUMENTS names an existing change under ~/specs/<project>/openspec/changes, load change-execute and resume instead.
