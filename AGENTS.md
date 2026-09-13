# Global agent rules

## Language

Answer the user in Russian. Write prompts, skills, rules and code comments in English.

## Commits

Never commit unless the user asks.
Commit messages are one English line: type(scope): subject.
Types: feat, fix, refactor, test, docs, chore, perf, build, ci. No body, no trailers. Use the commit-message skill.
Install a commit-msg hook only into a specific repository and only on request; never set core.hooksPath globally.

## Code comments

Comment only non-obvious decisions, or add a one or two line doc comment on a method.
Do not restate what the code does and do not describe previous versions. Write extensive documentation only when asked.

## Secrets

Never print API keys, tokens or env files. To check model assignment use ~/.config/opencode/bin/oc-agent <agent>.
Never run opencode debug config. It prints resolved secrets.

## Long texts

Pass long texts through the humanize skill. This covers ADRs, proposals, designs, change summaries, story and task descriptions.

## Shell

Read files with the read, grep and glob tools. In bash, primary agents need the user's approval for redirections, sed, awk, xargs, find -exec and git -C.
Use `cd <dir> && git <command>` instead of git -C.

## Verification

Do not claim work is done without running the check that proves it and reading its output.
