---
name: workspace-extend
description: Use when the workspace-builder agent must add something to an existing team workspace
---
# Extend a workspace

Add an agent, skill, rule, domain, stand, variable or repository to an existing team workspace by the workspace's own skills, so the result matches what a team member would get.

## Open

1. Ask the owner for the workspace path. Call it `<path>`.
2. Run `test -f <path>/.agents/kit.json`. When it fails, stop: `<path>` is not a workspace built from the kit. Change nothing.
3. Read `<path>/.agents/kit.json` and report its `name` and `version`.
4. Read `~/.config/opencode/kits/workspace/kit.json` and report its `version`.
5. When the kit version is higher than the workspace version, tell the owner the workspace is behind the kit. Updating a workspace to a newer kit is not part of this skill; continue with the workspace as it is.

## Add

1. Ask the owner what to add: the kind and the name.
2. Read `<path>/.agents/skills/extend/SKILL.md` and follow its steps in order, running every command in `<path>`. For a repository, follow `<path>/.agents/skills/repos-add/SKILL.md` instead.
3. The one exception, in both skills: stop before the commit step. Never run its commit, rebase, push or merge request steps, even when the owner asks; your permissions deny `git commit` and `git push`. They become commands for the owner in `## Hand-off`.
4. Leave the changes uncommitted on the branch and go to `## Verify`.

Follow the workspace skill even where it differs from what this setup would do. The workspace skill is the contract; a difference worth fixing is a kit finding.

## Verify

1. In `<path>` run `python3 tools/generate.py`, then `python3 tools/check.py`.
2. Fix every finding and run both again until `check.py` prints nothing.
3. Show the owner the final output of both commands.

## Kit findings

A kit finding is something that applies to every workspace, not only this one: a missing template section, a missing rule, a check that should exist, a step in a workspace skill that is wrong or unclear.

For each finding, write a proposal for the owner with:
- the files under `~/.config/opencode/kits/workspace/` to change;
- the change itself, as the exact text to add or replace;
- the new `version` in `kits/workspace/kit.json`: a patch bump for wording, a minor bump for a new file or rule.

Do not edit the setup. The owner decides whether the proposal goes into the kit.

## Hand-off

Run `git status` and `git diff` in `<path>` and show both outputs to the owner.

Report to the owner:
- what was added: the kind and the name;
- the files created or changed;
- the branch;
- the final `check.py` output;
- the kit proposals, or `no kit findings`.

Then print the commands the owner runs in `<path>`, taken from the commit, rebase, push and merge request steps of the workspace skill with every placeholder filled in:
- `git add` with every file created or changed, then `git commit -m "<message from the workspace skill>"`;
- `git pull --rebase origin <default>`, with a pointer to the skill's `## Conflicts` section;
- the push and merge request command for `params.forge` in `<path>/.agents/kit.json`, as `.agents/rules/merge-requests.md` gives it.

Never run these commands yourself.
