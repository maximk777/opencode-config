import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const cmd = (n) => readFileSync(new URL(`../commands/${n}.md`, import.meta.url), "utf8");

test("change and resume run in the orchestrator", () => {
  for (const n of ["change", "resume"]) assert.match(cmd(n), /^---\n(.*\n)*agent: orchestrator\n/m, n);
});

test("change starts with brainstorming", () => assert.ok(cmd("change").includes("change-brainstorm")));

test("resume reads state from files", () => assert.ok(cmd("resume").includes("bin/change-state")));
