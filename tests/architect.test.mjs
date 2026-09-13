import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { checkSkill } from "./lib/skill.mjs";

const ROOT = new URL("..", import.meta.url).pathname;

checkSkill("architecture-docs", [
  "Write only under ~/specs/<project>/architecture: adr/, diagrams/, roadmap.md, backlog/, poc/.",
  "Diagrams are Mermaid: C4 component diagrams and sequence diagrams.",
  "Record rejected alternatives in every ADR.",
  "Hand work to execution only as a candidate card in backlog/ from templates/candidate.md.",
  "Copy diagrams into the work repository docs/ only when the user explicitly asks in this session.",
  "Never write change specs or tasks.",
  "Pass ADRs through the humanize skill.",
]);

const cfg = JSON.parse(readFileSync(`${ROOT}opencode.json`, "utf8"));

test("architect is primary on the smart tier and only calls explorer", () => {
  const a = cfg.agent.architect;
  assert.equal(a.mode, "primary");
  assert.equal(a.model, "{file:./tiers/smart}");
  assert.deepEqual(a.permission.task, { "*": "deny", explorer: "allow" });
  assert.deepEqual(a.permission.edit, { "*": "deny", "../*specs/*/architecture/*": "allow" });
});

test("change command reads candidate cards", () => {
  assert.ok(readFileSync(`${ROOT}commands/change.md`, "utf8").includes("architecture/backlog"));
});
