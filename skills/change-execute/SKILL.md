---
name: change-execute
description: Use when a change plan is approved and its tasks must be executed wave by wave with review
---
# Execute a change

Run the approved plan in waves: executors implement, task-reviewer checks, the orchestrator accepts by staging.

## Start or resume

On resume run ~/.config/opencode/bin/change-state ~/specs/<project> <slug> and continue from its output.
Set the session title to include [change:<project>/<slug>].
Read waves.md. Skip checked tasks. Review tasks listed as awaiting review before dispatching anything new.

## Per wave

1. Dispatch all tasks of a wave in one message.
2. Give each executor only the brief path and the report path.
3. Use the tier from waves.md: executor or executor-strong.
4. When executors return, handle their status:
   - DONE: review.
   - DONE_WITH_CONCERNS: read the concerns; fix correctness or scope issues before review.
   - NEEDS_CONTEXT: add the missing context to the brief and dispatch again.
   - BLOCKED: provide context, switch to executor-strong, or split the task. Never resend the same brief to the same tier after BLOCKED.

## Review loop

task-reviewer gives the spec verdict first and assesses quality only when compliant.
Pass the reviewer the brief path, the report path and the task's file list. Do not tell the reviewer what not to flag.
On NOT COMPLIANT or quality issues, send the notes back to the same executor with its task_id.
After three rejected fix rounds with the same executor, dispatch executor-strong; if that fails, ask the user.

## Session reset

Call phase_reset after the spec is approved, after the plan is approved, and after every wave is accepted.
The compaction keeps the change state from files; after it, run change-state if anything is unclear and continue.

## Acceptance

Accept a task only when the last Verdict line in its report is Verdict: COMPLIANT; if the report has no verdict, dispatch task-reviewer again.
On acceptance run git add -- <task files> and check the task in tasks.md.
Never commit in the work repository; at the end propose commits using the commit-message skill.
If an executor touched a file outside its list, the reviewer flags it; revert that file only with the user's consent.

## Spec errors

When execution shows the spec is wrong, stop the wave and switch to the change-spec skill.

## Finish

After the last wave run the full verification, request a final review of the whole change, then run openspec archive <slug> --yes from ~/specs/<project>.
Archive before proposing commits. Then commit the specs repository, run ~/.config/opencode/bin/ov-sync <project>, check each proposed message with `printf '%s\n' '<message>' | ~/.config/opencode/bin/check-commit-msg`, and present to the user: what changed, the verification output, and the proposed commits with their files.
