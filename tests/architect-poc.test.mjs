import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { checkSkill } from "./lib/skill.mjs";

const ROOT = new URL("..", import.meta.url).pathname;

checkSkill("architecture-poc", [
  "Run a PoC only when the hypothesis can be checked with numbers and the user agreed to check it.",
  "Write poc/<slug>/README.md with the hypothesis and success criterion before the first run.",
  "Run locally only: docker compose or testcontainers.",
  "When work repository code is needed, use a temporary git worktree and remove it afterwards.",
  "Never target stage or production without the user's explicit permission in this session.",
  "Write poc/<slug>/RESULT.md from templates/poc-result.md with raw numbers and a verdict.",
  "Link RESULT.md from the ADR that relies on it.",
  "Never copy PoC code into a product repository; write a candidate card instead.",
  "After the user accepts the result, commit the specs repository and run ~/.config/opencode/bin/ov-sync <project>; it only queues the project and returns at once.",
]);

const tpl = (n) => readFileSync(`${ROOT}skills/architecture-docs/templates/${n}`, "utf8");

test("PoC templates carry criterion and verdict", () => {
  assert.ok(tpl("poc-readme.md").includes("Success criterion:"));
  assert.ok(tpl("poc-result.md").includes("Verdict:"));
});

test("architect can run PoCs locally", () => {
  const bash = JSON.parse(readFileSync(`${ROOT}opencode.json`, "utf8")).agent.architect.permission.bash;
  assert.equal(bash["git worktree add*"], "allow");
  assert.equal(bash["docker compose *"], "allow");
});

test("architect prompt loads the PoC skill", () => {
  assert.ok(readFileSync(`${ROOT}prompts/architect.md`, "utf8").includes("architecture-poc"));
});
