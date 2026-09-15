import { test } from "node:test";
import assert from "node:assert/strict";
import { checkSkill, readSkill } from "./lib/skill.mjs";

checkSkill("change-execute", [
  "Give each executor only the brief path and the report path.",
  "Use the tier from waves.md: executor or executor-strong.",
  "task-reviewer gives the spec verdict first and assesses quality only when compliant.",
  "After three rejected fix rounds with the same executor, dispatch executor-strong; if that fails, ask the user.",
  "On acceptance run git add -- <task files> and check the task in tasks.md.",
  "Accept a task only when the last Verdict line in its report is Verdict: COMPLIANT; if the report has no verdict, dispatch task-reviewer again.",
  "Archive before proposing commits.",
  "Never commit in the work repository unless the user asks; at the end propose commits using the commit-message skill.",
  "On resume run ~/.config/opencode/bin/change-state ~/specs/<project> <slug> and continue from its output.",
  "When execution shows the spec is wrong, stop the wave and switch to the change-spec skill.",
  "After the last wave run the full verification, request a final review of the whole change, then run openspec archive <slug> --yes from ~/specs/<project>.",
  "When a wave is accepted, run ~/.config/opencode/bin/ov-sync <project>; it only queues the project and returns at once.",
  "Right after change-state at start and resume, after a wave is dispatched, after every review verdict and after every acceptance, run ~/.config/opencode/bin/change-todos ~/specs/<project> <slug> and pass its output unchanged to todowrite when that tool is available; skip the step otherwise.",
  "When change-todos exits non-zero or todowrite returns an error, skip the step without reporting it and continue.",
]);

test("change-execute places the todo list after start and before the waves", () => {
  const text = readSkill("change-execute");
  const todo = text.indexOf("## Todo list");
  const start = text.indexOf("## Start or resume");
  const perWave = text.indexOf("## Per wave");
  assert.ok(todo >= 0);
  assert.ok(start >= 0);
  assert.ok(perWave >= 0);
  assert.ok(todo > start);
  assert.ok(todo < perWave);
});

test("change-execute syncs after the archive commit", () => {
  const text = readSkill("change-execute");
  const finish = text.slice(text.indexOf("## Finish"));
  const archive = finish.indexOf("'docs(<slug>): archive change'");
  const sync = finish.indexOf("Run ~/.config/opencode/bin/ov-sync <project>.");
  assert.ok(archive >= 0);
  assert.ok(sync > archive);
  assert.match(finish, /\n\d+\. Run ~\/\.config\/opencode\/bin\/ov-sync <project>\.\n/);
});

test("change-execute states the wave dispatch rule", () => {
  const text = readSkill("change-execute");
  assert.ok(text.includes("Dispatch all tasks of a wave in one message.") || text.includes("Dispatch one task per message."));
});
