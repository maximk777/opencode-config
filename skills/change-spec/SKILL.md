---
name: change-spec
description: Use when a change design is approved and its requirement deltas must be written and validated
---
# Specify a change

Write OpenSpec requirement deltas for the approved design, validate them, and get the user's approval.

## Where

Deltas live in ~/specs/<project>/openspec/changes/<slug>/specs/<capability>/spec.md. Set OPENSPEC_TELEMETRY=0.

## Delta format

```markdown
## ADDED Requirements

### Requirement: Ping returns pong
The service SHALL answer GET /ping with status 200 and body pong.

#### Scenario: ping
- **WHEN** a client sends GET /ping
- **THEN** the response status is 200 and the body is pong
```

- Section headers: `## ADDED Requirements`, `## MODIFIED Requirements`, `## REMOVED Requirements`, `## RENAMED Requirements`.
- Requirement text uses SHALL or MUST.
- Each requirement MUST include at least one #### Scenario: block.
- A MODIFIED requirement repeats the whole requirement, not a diff.
- A REMOVED requirement states the reason and the migration.

## Validation loop

Run openspec validate <slug> --strict --no-interactive from ~/specs/<project> until it prints "is valid".
On errors, read the "Next steps" lines, fix the delta, and run it again. To inspect what was parsed: `openspec show <slug> --json --deltas-only`.

## Gate

Stop and ask the user to approve the spec before planning.
After approval, commit the specs repository with `~/.config/opencode/bin/specs-commit <project> 'docs(<slug>): add spec deltas'`, run ~/.config/opencode/bin/ov-sync <project>; it only queues the project and returns at once, and load the change-plan skill.

## Spec errors during execution

When execution shows the spec is wrong, stop dispatching, amend the delta, validate again, ask the user, then re-plan only the remaining tasks.
Do not let executors work around a wrong requirement.
