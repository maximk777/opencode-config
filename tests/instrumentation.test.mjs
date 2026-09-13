import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { checkSkill } from "./lib/skill.mjs";

const ROOT = new URL("..", import.meta.url).pathname;

checkSkill("agents-instrumentation", [
  "Keep AGENTS.md a table of contents of about 100 lines.",
  "Content lives in .agents/rules, .agents/skills and .agents/agents; .opencode/agents and .opencode/skills are symlinks to them.",
  "Run templates/link-opencode.sh to move files out of .opencode and create the symlinks.",
  "A skill about code must contain templates/ derived from real code of this repository, with source path and commit.",
  "Before creating a code skill, generate a sample from its templates in a temporary git worktree and build or test it; if it fails, do not create the skill.",
  "Run ~/.config/opencode/bin/agents-lint <repo> before presenting a diff.",
  "Propose a new rule or skill only when the same error class appears at least twice, and cite the occurrences.",
  "Harmful rule checklist:",
  "Present a diff and apply it only after the user's approval; never commit.",
  "Write rules and skills in English.",
]);

const tpl = (n) => readFileSync(`${ROOT}skills/agents-instrumentation/templates/${n}`, "utf8");

test("skill template has a templates section", () => assert.ok(tpl("skill/SKILL.md").includes("## Templates")));
test("link script creates symlinks into .agents", () => assert.ok(tpl("link-opencode.sh").includes("ln -s ../.agents/")));

test("instrumentation agent edits only project instrumentation and cannot commit", () => {
  const a = JSON.parse(readFileSync(`${ROOT}opencode.json`, "utf8")).agent.instrumentation;
  assert.equal(a.mode, "primary");
  assert.equal(a.permission.edit["*"], "deny");
  assert.equal(a.permission.edit[".agents/*"], "allow");
  assert.equal(a.permission.bash["git commit*"], "deny");
});
