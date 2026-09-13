import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const ROOT = new URL("..", import.meta.url).pathname;
const cfg = JSON.parse(readFileSync(`${ROOT}opencode.json`, "utf8"));
const A = cfg.agent;
const prompt = (n) => readFileSync(`${ROOT}prompts/${n}.md`, "utf8");

test("orchestrator is primary on the smart tier", () => {
  assert.equal(A.orchestrator.mode, "primary");
  assert.equal(A.orchestrator.model, "{file:./tiers/smart}");
});

test("executors and reviewer are hidden subagents with the right tiers", () => {
  for (const n of ["executor", "executor-strong", "task-reviewer"]) {
    assert.equal(A[n].mode, "subagent", n);
    assert.equal(A[n].hidden, true, n);
  }
  assert.equal(A.executor.model, "{file:./tiers/fast}");
  assert.equal(A["executor-strong"].model, "{file:./tiers/smart}");
  assert.equal(A["task-reviewer"].model, "{file:./tiers/smart}");
});

test("nobody in the change flow can commit", () => {
  for (const n of ["orchestrator", "executor", "executor-strong"]) {
    assert.equal(A[n].permission.bash["git commit*"], "deny", n);
  }
});

test("orchestrator edits only specs and dispatches only the flow subagents", () => {
  assert.deepEqual(A.orchestrator.permission.edit, { "*": "deny", "../*specs/*": "allow" });
  assert.deepEqual(A.orchestrator.permission.task, {
    "*": "deny", executor: "allow", "executor-strong": "allow", "task-reviewer": "allow", explorer: "allow",
  });
});

test("reviewer has no memory tools and cannot edit code", () => {
  assert.equal(A["task-reviewer"].permission["openviking_*"], "deny");
  assert.equal(A["task-reviewer"].permission.edit["*"], "deny");
});

test("executors may only find and read in memory", () => {
  for (const n of ["executor", "executor-strong"]) {
    assert.equal(A[n].permission["openviking_*"], "deny", n);
    assert.equal(A[n].permission.openviking_find, "allow", n);
    assert.equal(A[n].permission.openviking_read, "allow", n);
  }
});

test("prompts carry the key rules", () => {
  assert.ok(prompt("executor").includes("Do not commit."));
  assert.ok(prompt("executor").includes("Comment only non-obvious decisions."));
  assert.ok(prompt("executor-strong").includes("Do not commit."));
  assert.ok(prompt("task-reviewer").includes("Do not trust the report; read the diff yourself."));
  assert.ok(prompt("task-reviewer").includes("Append to the report; never rewrite or delete earlier content."));
  assert.ok(prompt("orchestrator").includes("change-brainstorm"));
});
