import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { checkSkill } from "./lib/skill.mjs";

const ROOT = new URL("..", import.meta.url).pathname;

checkSkill("harness-assessment", [
  "Every gate row names its error class, evidence, CI cost, command and fix hint.",
  "Do not propose a gate without evidence.",
  "Propose load tests and multi-instance tests only for high-load or concurrency-critical services.",
  "Micro-frontends and low-load services get contract, integration, type and custom lint gates.",
  "Money, personal data or 115-FZ services also get secrets and personal-data-in-logs lint and audit tests.",
  "Run probes in a temporary git worktree, locally, and remove the worktree afterwards.",
  "Never target stage or production without the user's explicit permission in this session.",
  "Write only ~/specs/<project>/harness and change candidates; gate code goes through the orchestrator.",
  "Hand agent-facing rules about gates to the instrumentation agent.",
  "Reassess after several archived changes and mark gates that caught nothing as removal candidates.",
  "## Profile matrix",
]);

test("gates template header is exact", () => {
  const t = readFileSync(`${ROOT}skills/harness-assessment/templates/gates.md`, "utf8");
  assert.ok(t.includes("| Gate | Error class | Evidence | CI cost | Command | Fix hint | Status |"));
  assert.ok(t.includes("## Reassessment"));
});

test("harness-builder is primary on smart and cannot commit", () => {
  const a = JSON.parse(readFileSync(`${ROOT}opencode.json`, "utf8")).agent["harness-builder"];
  assert.equal(a.mode, "primary");
  assert.equal(a.model, "{file:./tiers/smart}");
  assert.equal(a.permission.bash["git commit*"], "deny");
  assert.deepEqual(a.permission.task, { "*": "deny", explorer: "allow" });
});
