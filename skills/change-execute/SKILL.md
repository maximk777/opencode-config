---
name: change-execute
description: Use when a change plan is approved and its tasks must be executed wave by wave with review
---
# Execute a change

Run the approved plan in waves: executors implement, task-reviewer checks, the orchestrator accepts by staging.

## Start or resume

On resume run ~/.config/opencode/bin/change-state ~/specs/<project> <slug> and continue from its output.
Set the session title to include [change:<project>/<slug>].
Read waves.md. Skip checked tasks. Run change-state at the start too: a task may have been submitted before this session.
Handle its groups before dispatching anything new: awaiting_review goes to task-reviewer, needs_fix goes back to an executor with the last review notes, ready_to_accept is accepted.

## Todo list

Right after change-state at start and resume, after a wave is dispatched, after every review verdict and after every acceptance, run ~/.config/opencode/bin/change-todos ~/specs/<project> <slug> and pass its output unchanged to todowrite when that tool is available; skip the step otherwise.
When change-todos exits non-zero or todowrite returns an error, skip the step without reporting it and continue.

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
On NOT COMPLIANT or quality issues, send the notes back to the same executor with its task_id. Without a task_id, for example after a reset or for a task submitted earlier, dispatch a new executor with the brief path, the report path and the notes.
After three rejected fix rounds with the same executor, dispatch executor-strong; if that fails, ask the user.

## Session reset

Call phase_reset after the spec is approved, after the plan is approved, and after every wave is accepted.
The compaction keeps the change state from files; after it, run change-state if anything is unclear and continue.
Where phase_reset is not available, as in Claude Code, do not wait for a reset: continue, and after an automatic compaction the SessionStart hook restores the change state.

## Acceptance

Accept a task only when the last Verdict line in its report is Verdict: COMPLIANT; if the report has no verdict, dispatch task-reviewer again.
On acceptance run git add -- <task files> and check the task in tasks.md.
When a wave is accepted, run ~/.config/opencode/bin/ov-sync <project>; it only queues the project and returns at once.
Never commit in the work repository unless the user asks; at the end propose commits using the commit-message skill.
If an executor touched a file outside its list, the reviewer flags it; revert that file only with the user's consent.

## Spec errors

When execution shows the spec is wrong, stop the wave and switch to the change-spec skill.

## Finish

The change is not finished until every step below has run, in this order:
1. After the last wave run the full verification, request a final review of the whole change, then run openspec archive <slug> --yes from ~/specs/<project>.
2. Archive before proposing commits. Then commit the specs repository with `~/.config/opencode/bin/specs-commit <project> 'docs(<slug>): archive change'`; this commit needs no request from the user.
3. Run ~/.config/opencode/bin/ov-sync <project>.
4. Check each proposed message with `printf '%s\n' '<message>' | ~/.config/opencode/bin/check-commit-msg`.
5. Present to the user: what changed, the verification output, and the proposed commits with their files.
