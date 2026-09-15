---
name: change-brainstorm
description: Use when starting a change with the orchestrator, before any spec, task or code exists
---
# Brainstorm a change

Turn an idea or an architect's candidate card into an approved design, in dialogue, stored as files.
Adapted from obra/superpowers brainstorming (commit pinned in sources.lock).

## Hard gate

Do not write code or tasks before the user approves the design.
This applies to every change, including ones that look too small to need a design. The design may be three sentences, but it is presented and approved.

## Order

1. Resolve the project and change slug. Set the session title to include [change:<project>/<slug>].
2. If ~/specs/<project> does not exist, create it, run git init and openspec init --tools none.
3. Before asking the user, run find or search on the change's question in OpenViking memory. The first entry of decisions.md is the Memory line: `Memory: query="<query>" hits=<N> used=yes|no rederived=<ADR or map path|none>`. If openviking tools fail, say once that memory is unavailable, write the Memory line with hits=0 used=no rederived=none, and put the error on the next line as `Memory error: <text>`, then continue from files. Either way, commit decisions.md before the first question.
4. Read the work repository's AGENTS.md and .agents/ for constraints. If the input is a candidate card from architecture/backlog, read it and every file it links.
5. Explore the code with the explorer subagent when the design depends on how things are built today.
6. Scope check: if the idea is several independent subsystems, say so and split before refining details.
7. Ask one question per message. Prefer multiple choice. You are after purpose, constraints and what counts as done.
8. Propose 2-3 approaches and lead with a recommendation. Say why the others lose.
9. Present the design in sections sized to their complexity: architecture, units and boundaries, data flow, failure handling, testing. Ask after each section whether it holds.

## Decision log

Append every user answer and decision to ~/specs/<project>/openspec/changes/<slug>/decisions.md as soon as it is given, numbered, and commit it at once with `~/.config/opencode/bin/specs-commit <project> 'docs(<slug>): record <topic>'`.
Copy the Memory line from each explorer report into the log.
The Memory line is written once with `rederived=none`; never edit the Memory line afterward. When a decision reached in the session already sits in an ADR or a map, append `Rederived: <ADR or map path>` to decisions.md and commit it.
design.md records approved sections, decisions.md records the answers they rest on.

## Writing artifacts

Write proposal.md and design.md under ~/specs/<project>/openspec/changes/<slug>/. decisions.md lives in the same change directory.
Never write change artifacts into the work repository.
After each approved design section, commit the specs repository with `~/.config/opencode/bin/specs-commit <project> 'docs(<slug>): add data flow section'`.
Pass proposal.md and design.md through the humanize skill.

proposal.md follows OpenSpec: `# <title>`, `## Why` (at least two sentences on the problem), `## What Changes` (bullets).
design.md records the chosen approach, the rejected approaches with reasons, and the approved sections.

## Self-review before hand-off

- Placeholders: no TBD, TODO or vague requirement.
- Consistency: sections do not contradict each other.
- Scope: one change, not several under one name.
- Ambiguity: a requirement cannot be read two ways.

## Hand-off

Tell the user the design is recorded and ask for approval. On approval, load the change-spec skill. Do not start any other skill first.
