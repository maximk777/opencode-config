import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readlinkSync, symlinkSync, writeFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { checkSkill } from "./lib/skill.mjs";

const ROOT = new URL("..", import.meta.url).pathname;

checkSkill("agents-instrumentation", [
  "Keep AGENTS.md a table of contents of about 100 lines.",
  "Content lives in .agents/rules, .agents/skills and .agents/agents; .opencode/agents and .opencode/skills are symlinks to them.",
  "Run ~/.config/opencode/skills/agents-instrumentation/templates/link-opencode.sh to move files out of .opencode and create the symlinks.",
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
test("link script creates symlinks into .agents", () => assert.ok(tpl("link-opencode.sh").includes('ln -s "../.agents/')));

const linkScript = `${ROOT}skills/agents-instrumentation/templates/link-opencode.sh`;
const runLink = (cwd) => spawnSync("bash", [linkScript], { cwd, encoding: "utf8" });
const scratch = () => mkdtempSync(join(tmpdir(), "link-opencode-"));

test("link script moves .opencode contents and is idempotent", () => {
  const dir = scratch();
  mkdirSync(join(dir, ".opencode/agents"), { recursive: true });
  writeFileSync(join(dir, ".opencode/agents/helper.md"), "helper");
  assert.equal(runLink(dir).status, 0);
  assert.equal(readlinkSync(join(dir, ".opencode/agents")), "../.agents/agents");
  assert.equal(readlinkSync(join(dir, ".opencode/skills")), "../.agents/skills");
  assert.equal(readFileSync(join(dir, ".agents/agents/helper.md"), "utf8"), "helper");
  assert.equal(runLink(dir).status, 0);
});

test("link script refuses to overwrite an existing .agents file", () => {
  const dir = scratch();
  mkdirSync(join(dir, ".opencode/agents"), { recursive: true });
  mkdirSync(join(dir, ".agents/agents"), { recursive: true });
  writeFileSync(join(dir, ".opencode/agents/helper.md"), "old");
  writeFileSync(join(dir, ".agents/agents/helper.md"), "kept");
  const r = runLink(dir);
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /refusing/);
  assert.equal(readFileSync(join(dir, ".agents/agents/helper.md"), "utf8"), "kept");
  assert.equal(readFileSync(join(dir, ".opencode/agents/helper.md"), "utf8"), "old");
  assert.equal(existsSync(join(dir, ".opencode/skills")), false);
});

test("link script refuses a foreign symlink or a file in place of the link", () => {
  const linked = scratch();
  mkdirSync(join(linked, ".opencode"), { recursive: true });
  symlinkSync("/tmp", join(linked, ".opencode/skills"));
  const r1 = runLink(linked);
  assert.notEqual(r1.status, 0);
  assert.equal(readlinkSync(join(linked, ".opencode/skills")), "/tmp");
  const file = scratch();
  mkdirSync(join(file, ".opencode"), { recursive: true });
  writeFileSync(join(file, ".opencode/agents"), "not a dir");
  const r2 = runLink(file);
  assert.notEqual(r2.status, 0);
  assert.equal(readFileSync(join(file, ".opencode/agents"), "utf8"), "not a dir");
});

test("instrumentation agent edits only project instrumentation and cannot commit", () => {
  const a = JSON.parse(readFileSync(`${ROOT}opencode.json`, "utf8")).agent.instrumentation;
  assert.equal(a.mode, "primary");
  assert.equal(a.permission.edit["*"], "deny");
  assert.equal(a.permission.edit[".agents/*"], "allow");
  assert.equal(a.permission.bash["git commit*"], "deny");
});
