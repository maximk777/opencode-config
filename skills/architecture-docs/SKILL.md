---
name: architecture-docs
description: Use when designing a system or project as a whole - ADRs, component and sequence diagrams, versions, roadmap and change candidates
---
# Architecture documents

System-level work for the architect. Changes to code go through the orchestrator; this skill produces the thinking and the hand-off.

## Where

Write only under ~/specs/<project>/architecture: adr/, diagrams/, roadmap.md, backlog/, poc/.
If the folder does not exist, create it inside the specs repository (run git init there if the repository is missing).
Never write change specs or tasks.

## ADRs

- Use templates/adr.md, numbered `adr/NNN-<slug>.md`.
- Record rejected alternatives in every ADR.
- Link evidence: diagrams, PoC results, measurements.
- Pass ADRs through the humanize skill.

## Diagrams

Diagrams are Mermaid: C4 component diagrams and sequence diagrams.
Keep one diagram per file in diagrams/ (`<name>.md` with a mermaid code block) so diffs stay readable.

## Roadmap and versions

roadmap.md lists versions with their goals, the decisions they depend on (ADR links) and open questions.

## Hand-off to execution

Hand work to execution only as a candidate card in backlog/ from templates/candidate.md.
The user starts it with `/change <slug>`; the orchestrator reads the card and its links.

## Project docs

Copy diagrams into the work repository docs/ only when the user explicitly asks in this session.

## Work style

- Read code through the explorer subagent; do not guess how things are built.
- Discuss one question at a time; propose alternatives with a recommendation.
- After an accepted document, commit the specs repository with `~/.config/opencode/bin/specs-commit <project> '<message>'` and run ~/.config/opencode/bin/ov-sync <project>.
