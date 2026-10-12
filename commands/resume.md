---
description: Resume a change from its files
agent: orchestrator
---
Run ~/.config/opencode/bin/change-state ~/specs/<project> $ARGUMENTS. Right after change-state, run ~/.config/opencode/bin/change-todos ~/specs/<project> $ARGUMENTS and pass its output unchanged to todowrite when that tool is available; skip the step otherwise. When change-todos exits non-zero or todowrite returns an error, skip the step without reporting it and continue. Then read the decisions.md it names; when the file head differs from what the session remembers, trust the files. Continue the change from that state: with change-execute when tasks.md exists, otherwise with the flow skill for the first missing artifact (change-brainstorm, change-spec or change-plan).
