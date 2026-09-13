---
name: change-plan
description: Use when a change spec is approved and it must be split into executor tasks, briefs and waves
---
# Plan a change

Turn approved spec deltas into tasks an executor can do without seeing anything else.

## Output

In ~/specs/<project>/openspec/changes/<slug>/:
- Write tasks.md in OpenSpec checkbox format and one brief per task from templates/brief.md.
- `briefs/<N>.md` for every task.
- `waves.md` produced by the waves script.

tasks.md format:

```markdown
## 1. <group>
- [ ] 1.1 <task title>
- [ ] 1.2 <task title>
```

## Writing tasks

- Each task is 2-10 minutes of work: write the failing test, make it pass, run the check.
- Map files first: which files are created or changed and what each is responsible for.
- The brief repeats the full requirement text and scenarios it covers; the executor sees nothing else.
- Set skeleton: yes only when the brief contains the code skeleton.
- A brief without a skeleton that touches more than two files goes to executor-strong; the waves script decides this from `files` and `skeleton`.
- `Verify` names the exact command and the markers it prints verbatim.
- No placeholders: no TBD, TODO, "add error handling", "similar to task N".
- Every requirement in the spec is covered by at least one task.

## Waves

Run ~/.config/opencode/bin/waves <change-dir> and save its output to waves.md.
Tasks in one wave never share a file or a Go package. Default concurrency is 3; pass `--concurrency N` to change it.
If the script reports a cycle or missing dependency, fix the briefs' `depends` and run it again.

## Gate

Stop and ask the user to approve the plan before execution.
Show the waves and the tier of each task. After approval, commit the specs repository (`docs(<slug>): add plan`), run ~/.config/opencode/bin/ov-sync <project>, and load the change-execute skill.
