import { test } from "node:test";
import assert from "node:assert/strict";
import { checkSkill, readSkill } from "./lib/skill.mjs";

checkSkill("change-execute", [
  "Give each executor only the brief path and the report path.",
  "Use the tier from waves.md: executor or executor-strong.",
  "task-reviewer gives the spec verdict first and assesses quality only when compliant.",
  "After three rejected fix rounds with the same executor, dispatch executor-strong; if that fails, ask the user.",
  "On acceptance run git add -- <task files> and check the task in tasks.md.",
  "Never commit in the work repository; at the end propose commits using the commit-message skill.",
  "On resume run ~/.config/opencode/bin/change-state ~/specs/<project> <slug> and continue from its output.",
  "When execution shows the spec is wrong, stop the wave and switch to the change-spec skill.",
  "After the last wave run the full verification, request a final review of the whole change, then run openspec archive <slug> --yes from ~/specs/<project>.",
]);

test("change-execute states the wave dispatch rule", () => {
  const text = readSkill("change-execute");
  assert.ok(text.includes("Dispatch all tasks of a wave in one message.") || text.includes("Dispatch one task per message."));
});
