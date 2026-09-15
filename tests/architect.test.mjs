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
  "run ~/.config/opencode/bin/ov-sync <project>; it only queues the project and returns at once",
  "architecture/sessions/<YYYY-MM-DD>-<topic>.md",
  "append every user answer and decision as soon as it is given and commit it",
  'Memory: query="<query>" hits=<N> used=yes|no rederived=<ADR or map path|none>',
  "write rederived=none and never edit the Memory line",
  "append `Rederived: <ADR or map path>` to the log",
]);

test("architecture-docs session log no longer sets rederived directly", () => {
  const text = readSkill("architecture-docs");
  assert.ok(!text.includes("Set `rederived`"));
});

test("architecture-docs session log puts a failed memory read on a Memory error line", () => {
  const text = readSkill("architecture-docs");
  const at = text.indexOf("## Session log");
  assert.notEqual(at, -1, "architecture-docs has no ## Session log heading");
  const next = text.indexOf("\n## ", at + 1);
  const section = next === -1 ? text.slice(at) : text.slice(at, next);
  assert.ok(section.includes("`Memory error: <text>`"));
});

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

test("architect prompt syncs only at gates and starts sessions with memory", () => {
  const p = readFileSync(`${ROOT}prompts/architect.md`, "utf8");
  assert.ok(p.includes("run ~/.config/opencode/bin/ov-sync <project> only at gates: an accepted document or an accepted PoC result"));
  assert.ok(!p.includes("edit files, then run"));
  assert.ok(p.includes("Start each session with find or search on its question"));
  assert.ok(p.includes('Memory: query="<query>" hits=<N> used=yes|no rederived=<ADR or map path|none>'));
  assert.ok(p.includes("architecture/sessions/"));
});
