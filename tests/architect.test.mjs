import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { checkSkill, readSkill } from "./lib/skill.mjs";

const ROOT = new URL("..", import.meta.url).pathname;

checkSkill("architecture-docs", [
  "Write only under ~/specs/<project>/architecture: adr/, diagrams/, roadmap.md, backlog/, poc/.",
  "Diagrams are Mermaid: C4 component diagrams and sequence diagrams.",
  "Record rejected alternatives in every ADR.",
  "Hand work to execution only as a candidate card in backlog/ from templates/candidate.md.",
  "Copy diagrams into the work repository docs/ only when the user explicitly asks in this session.",
  "Never write change specs or tasks.",
  "Pass ADRs through the humanize skill.",
  "After an accepted document, commit the specs repository with",
  "architecture/sessions/<YYYY-MM-DD>-<topic>.md",
  "append every user answer and decision as soon as it is given and commit it",
  "append `Rederived: <ADR or map path>` to the log",
]);

test("architecture-docs session log no longer sets rederived directly", () => {
  const text = readSkill("architecture-docs");
  assert.ok(!text.includes("Set `rederived`"));
});

const cfg = JSON.parse(readFileSync(`${ROOT}opencode.json`, "utf8"));

test("architect is primary on the smart tier and only calls explorer", () => {
  const a = cfg.agent.architect;
  assert.equal(a.mode, "primary");
  assert.equal(a.model, "{file:./tiers/smart}");
  assert.deepEqual(a.permission.task, { "*": "deny", explorer: "allow", "web-researcher": "allow" });
  assert.deepEqual(a.permission.edit, { "*": "deny", "~/specs/*/architecture/**": "allow" });
});

test("change command reads candidate cards", () => {
  assert.ok(readFileSync(`${ROOT}commands/change.md`, "utf8").includes("architecture/backlog"));
});

test("architect prompt keeps the specs-commit rule", () => {
  const p = readFileSync(`${ROOT}prompts/architect.md`, "utf8");
  assert.ok(p.includes("Commit the specs repository only through ~/.config/opencode/bin/specs-commit"));
  assert.ok(!p.includes("edit files, then run"));
  assert.ok(!p.includes("ov-sync"));
});
