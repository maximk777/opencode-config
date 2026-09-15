---
name: opencode-config-improver
description: Use when auditing or improving the global OpenCode setup in ~/.config/opencode - config drift, upstream sources, flow metrics
---
# Improve the global OpenCode setup

Keep the global setup current and useful without importing surprises.

## Scope

Work only on ~/.config/opencode.
Project-specific rules and skills belong to the instrumentation agent in that project.

## Checks

1. OpenCode drift. Compare the config with the changelog of the installed OpenCode version (opencode --version) and report deprecated keys and new options.
2. Upstream sources. For every row in sources.lock, show the upstream diff since the pinned commit and recommend what to take; never pull automatically.
3. Flow metrics. Measure the flow from session logs: subagents over their steps limit, repeated reviewer rejection reasons, repeated tool failures. Run ~/.config/opencode/bin/ov-usage --days 7 and report the week's VLM calls, agent reads, memory lines and used findings against ADR-005's thresholds: fewer than one used finding per ten sessions means fallback B, no reads means option C.
4. Lint. Run ~/.config/opencode/bin/agents-lint on the repositories the user names, and the config's own tests with `node --test tests/` and `python3 -m unittest discover tests`.

## Changing the setup

- Mark edits to prompts/orchestrator.md or prompts/task-reviewer.md as risky and run bin/smoke-run after applying them.
- Verify model changes with ~/.config/opencode/bin/oc-agent <name>; never run opencode debug config.
- Add a new model provider as a provider block with apiKey {env:VAR}, put the key in an env file with mode 600, and switch a tier by editing tiers/<tier>.
- Present a diff and apply it only after the user's approval.
- Commit accepted changes in the setup repository with a Conventional Commit and update sources.lock when a ported source moves.
