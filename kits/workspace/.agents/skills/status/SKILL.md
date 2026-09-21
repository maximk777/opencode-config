---
name: status
description: Use to see the work queue - what is in progress with owners, what waits by project and stream, what finished recently - and to check your own open work before taking a new task.
---
# Show the status queue

## Steps
1. Go to the workspace root: the nearest directory, walking up from where you are, where `test -f .agents/kit.json` succeeds. Run every command below from there.
2. Ask the person for their short owner key - the value `task-start` writes into `owner` - unless they already gave it. When the person gives none, go on without the hygiene of step 5 and say so in the report.
3. When `command -v python3` prints a path, run `python3 tools/generate.py`. The generator only prints `generated: N files changed`, so detect a refreshed `STATUS.md` afterwards:
   - When `git rev-parse --is-inside-work-tree` prints `true`, run `git diff --name-only -- STATUS.md`. When it prints `STATUS.md`, the file differs from the last commit - usually the generator has just refreshed a stale file: say so in the report, and that the change is uncommitted.
   - When the command fails or prints anything else, the workspace is not a git repository yet and has no baseline: say that staleness was not checked.
   Then read `STATUS.md` and take the three queue sections: the rows between `<!-- status:in-progress:begin -->` and `<!-- status:in-progress:end -->`, the rows between the `waiting` markers, and the rows between the `done-recently` markers.
4. Report the queue. Copy each section's tables as they are; write `empty` for a section with no rows:
   - `In progress`: one group per owner, each task with its started date.
   - `Waiting`: one group per project and stream - a heading `<project>/<domain>/<stream>` is the queue of that stream, the heading `workspace` holds the workspace tasks from `tasks/<slug>/task.md`.
   - `Done recently`: each task with its recorded date.
5. Hygiene, when step 2 has a key:
   - Take the person's own tasks: the rows of their group in the in-progress section, or, when the queue came from the `## Without Python` recipe, the paths whose `owner:` line names their key.
   - For each such task, run `test -f <folder>/work.md` on its folder. When it succeeds, name the task in the report and add: `work.md exists but the task is not done - finish the record first: run work-record to close it, or reopen the task; take no new work before that`.
   - End the report with the instruction: close or reopen your own in-progress tasks before taking new work.
6. This skill writes nothing itself. Say what step 3 refreshed, answer questions about the rows, and point the person to `task-start` for taking a waiting task.

## Without Python
1. Run no `python3 tools/generate.py`. When `STATUS.md` is missing, or the person says it is stale, read the queue from the task files instead of its sections:
   - In progress: `grep -rl "status: in_progress" projects tasks`; for every printed path, read the frontmatter `owner:` and `started:` lines, and group the tasks by owner as step 4 does.
   - Waiting: `grep -rl "status: waiting" projects tasks`; group the paths by their stream folder `projects/<project>/domains/<domain>/streams/<stream>`, and under `workspace` for `tasks/<slug>/task.md`.
   - Done recently: `grep -rl "status: done" projects tasks`; for every printed path, read `recorded:` from the `work.md` in the same folder, and list the task with that date.
2. The person's own tasks for the hygiene of step 5 are then the printed paths whose `owner:` line names their key.
3. When the person asks to refresh a stale `STATUS.md` by hand, point them to the flip recipes: `## Recipe: STATUS.md start flip` in `.agents/skills/task-start/SKILL.md` for every task that moved to `in_progress`, `## Recipe: STATUS.md done flip` in `.agents/skills/work-record/SKILL.md` for every task that moved to `done`. Each application equals what `python3 tools/generate.py` writes for that flip.
4. End the report with the line:

check not run: python3 missing
