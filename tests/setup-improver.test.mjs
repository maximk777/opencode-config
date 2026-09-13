import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { checkSkill } from "./lib/skill.mjs";

const ROOT = new URL("..", import.meta.url).pathname;

checkSkill("opencode-config-improver", [
  "Work only on ~/.config/opencode.",
  "Compare the config with the changelog of the installed OpenCode version (opencode --version) and report deprecated keys and new options.",
  "For every row in sources.lock, show the upstream diff since the pinned commit and recommend what to take; never pull automatically.",
  "Measure the flow from session logs: subagents over their steps limit, repeated reviewer rejection reasons, repeated tool failures.",
  "Mark edits to prompts/orchestrator.md or prompts/task-reviewer.md as risky and run bin/smoke-run after applying them.",
  "Verify model changes with ~/.config/opencode/bin/oc-agent <name>; never run opencode debug config.",
  "Project-specific rules and skills belong to the instrumentation agent in that project.",
  "Present a diff and apply it only after the user's approval.",
]);

test("sources.lock pins at least five sources", () => {
  const rows = readFileSync(`${ROOT}sources.lock`, "utf8").split("\n").filter((l) => l.trim());
  assert.ok(rows.length >= 5);
});

test("setup-improver is primary on smart", () => {
  const a = JSON.parse(readFileSync(`${ROOT}opencode.json`, "utf8")).agent["setup-improver"];
  assert.equal(a.mode, "primary");
  assert.equal(a.model, "{file:./tiers/smart}");
  assert.deepEqual(a.permission.task, { "*": "deny", explorer: "allow" });
});
