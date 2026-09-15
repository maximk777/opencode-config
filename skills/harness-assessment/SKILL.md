---
name: harness-assessment
description: Use when assessing a service's error background and choosing quality gates such as lint rules, integration, multi-instance or load tests
---
# Harness assessment

Understand a service, measure where it breaks, and propose mostly programmatic gates that reduce that error background.

## Steps

1. Profile the service with templates/profile.md: type, criticality, load and concurrency, integrations, existing gates. Use the explorer subagent for code reading.
2. Measure the error background with templates/error-background.md: run `~/.config/opencode/bin/error-background <repo>`, collect reviewer rejection reasons from archived changes, and read memory.
3. Ask clarifying questions one at a time: SLO and load, what the team counts as green, how many CI minutes are acceptable, which error classes hurt most.
4. Probe suspected weak spots. Run probes in a temporary git worktree, locally, and remove the worktree afterwards.
5. Choose gates with the profile matrix below and write templates/gates.md.
6. Hand off: write change candidates for gate implementation and pass agent-facing rules to the instrumentation agent.

## Rules

- Every gate row names its error class, evidence, CI cost, command and fix hint.
- Do not propose a gate without evidence.
- Propose load tests and multi-instance tests only for high-load or concurrency-critical services.
- Micro-frontends and low-load services get contract, integration, type and custom lint gates.
- Money, personal data or 115-FZ services also get secrets and personal-data-in-logs lint and audit tests.
- Never target stage or production without the user's explicit permission in this session.
- Write only ~/specs/<project>/harness and change candidates; gate code goes through the orchestrator.
- Hand agent-facing rules about gates to the instrumentation agent.
- Reassess after several archived changes and mark gates that caught nothing as removal candidates.
- A lint failure message must say how to fix the problem, because agents read it.

## Profile matrix

| Profile | Gates | Not proposed |
|---|---|---|
| Micro-frontend | typecheck, lint with custom rules (layer boundaries, required api client), contract check against backend OpenAPI, component and visual tests | load tests |
| BFF or low-load service | contract tests from OpenAPI, integration tests on testcontainers (database, queue), custom static lint (layers, error wrapping, no raw SQL in handlers) | load and multi-instance tests |
| High-load or concurrency-critical (SDKs, consumers, payments) | everything above plus multi-instance tests with shared Postgres (leadership, idempotency, at-least-once), load tests with thresholds, race detector | none |
| Money, personal data, 115-FZ (added to any profile) | secrets and personal-data-in-logs lint, audit trail tests | none |

## Output location

~/specs/<project>/harness/profile.md, error-background.md, gates.md. After the user accepts the assessment, commit the specs repository and run ~/.config/opencode/bin/ov-sync <project>; it only queues the project and returns at once.
