---
name: agents-instrumentation
description: Use when creating, auditing or improving a project's agent instrumentation - AGENTS.md, rules, project skills and project agents
---
# Project agent instrumentation

Build and maintain project-specific rules, skills and agents. The global setup is not your scope.

## Layout

Keep AGENTS.md a table of contents of about 100 lines.
Content lives in .agents/rules, .agents/skills and .agents/agents; .opencode/agents and .opencode/skills are symlinks to them.
Run templates/link-opencode.sh to move files out of .opencode and create the symlinks.
Agent frontmatter in .agents/agents contains name, description and OpenCode fields only; never a tools list or a model alias.

## Audit

1. Inventory AGENTS.md, .agents and .opencode.
2. Run ~/.config/opencode/bin/agents-lint <repo> before presenting a diff.
3. Read every rule and skill against this checklist.

Harmful rule checklist:
- AGENTS.md longer than about 100 lines or used as an encyclopedia.
- A rule with no way to check it ("write quality code").
- A rule that contradicts the code or names paths and commands that do not exist.
- Duplicated or conflicting rules between AGENTS.md, rules and skills.
- Statements tied to a date or a past state.
- A skill description that retells the process instead of saying when to use it.
- An agent without description or mode.
- A rule that should be a lint check: hand it to the harness-builder.

## New rules and skills

Propose a new rule or skill only when the same error class appears at least twice, and cite the occurrences.
Sources: reviewer rejections in archived change reports, memory, repeated review comments.

## Skills

Use templates/skill/SKILL.md.
A skill about code must contain templates/ derived from real code of this repository, with source path and commit.
Before creating a code skill, generate a sample from its templates in a temporary git worktree and build or test it; if it fails, do not create the skill.

## Changes

Present a diff and apply it only after the user's approval; never commit.
Write rules and skills in English.
