import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const REPO = fileURLToPath(new URL("..", import.meta.url));
const KIT = path.join(REPO, "kits/workspace");
const SKILLS = path.join(KIT, ".agents/skills");
const FILE_CHANGING = ["repos-add", "work-record", "decide", "extend"];
const CHECK_LINE = "check not run: python3 missing";

function git(args) {
  try {
    return execFileSync("git", args, { cwd: REPO, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
  } catch {
    return null;
  }
}

function semverGreater(a, b) {
  const pa = a.split(".").map(Number);
  const pb = b.split(".").map(Number);
  for (let i = 0; i < 3; i++) {
    if (pa[i] !== pb[i]) return pa[i] > pb[i];
  }
  return false;
}

function readSkill(name) {
  return readFileSync(path.join(SKILLS, name, "SKILL.md"), "utf8");
}

function skillNames() {
  return readdirSync(SKILLS, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => d.name);
}

// Returns the body of "## Without Python" up to the next level-2 heading or end of file.
function withoutPythonSection(text) {
  const lines = text.split("\n");
  const start = lines.indexOf("## Without Python");
  if (start === -1) return null;
  const rest = lines.slice(start + 1);
  const end = rest.findIndex((l) => l.startsWith("## "));
  return end === -1 ? rest : rest.slice(0, end);
}

function walk(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((d) => {
    const p = path.join(dir, d.name);
    return d.isDirectory() ? [p, ...walk(p)] : [p];
  });
}

test("kit.json has name, semver version and existing templated files", () => {
  const kit = JSON.parse(readFileSync(path.join(KIT, "kit.json"), "utf8"));
  assert.equal(typeof kit.name, "string");
  assert.ok(kit.name.trim().length > 0, "name is empty");
  assert.match(kit.version, /^\d+\.\d+\.\d+$/);
  assert.ok(Array.isArray(kit.templated), "templated is not a list");
  for (const entry of kit.templated) {
    assert.ok(existsSync(path.join(KIT, entry)), `templated entry missing: ${entry}`);
  }
});

test("every kit skill has frontmatter, numbered steps and Without Python", () => {
  const names = skillNames();
  assert.ok(names.length > 0, "no kit skills found");
  for (const name of names) {
    const text = readSkill(name);
    assert.ok(text.startsWith("---\n"), `${name}: no frontmatter`);
    const close = text.indexOf("\n---\n", 3);
    assert.ok(close !== -1, `${name}: frontmatter not closed`);
    const block = text.slice(4, close);
    assert.match(block, /^name: \S.*$/m, `${name}: frontmatter lacks name`);
    assert.match(block, /^description: \S.*$/m, `${name}: frontmatter lacks description`);
    assert.match(text, /^1\. /m, `${name}: no numbered steps`);
    assert.ok(text.split("\n").includes("## Without Python"), `${name}: no Without Python section`);
  }
});

test("file-changing skills end without Python with the check line", () => {
  for (const name of FILE_CHANGING) {
    const section = withoutPythonSection(readSkill(name));
    assert.ok(section, `${name}: no Without Python section`);
    const lines = section.map((l) => l.trim()).filter(Boolean);
    assert.equal(lines.at(-1), CHECK_LINE, `${name}: Without Python does not end with the check line`);
  }
});

test("AGENTS.md has at most 120 lines", () => {
  const lines = readFileSync(path.join(KIT, "AGENTS.md"), "utf8").replace(/\n$/, "").split("\n");
  assert.ok(lines.length <= 120, `AGENTS.md has ${lines.length} lines`);
});

test("kit has no CI configuration", () => {
  const ci = walk(KIT)
    .map((p) => path.relative(KIT, p).split(path.sep).join("/"))
    .filter((p) => p === ".gitlab-ci.yml" || p.endsWith("/.gitlab-ci.yml") || /(^|\/)\.github\/workflows\/./.test(p));
  assert.deepEqual(ci, []);
});

test("kit changes raise the kit version", () => {
  const headKit = git(["show", "HEAD:kits/workspace/kit.json"]);
  // Before the kit is first committed there is no baseline to compare against.
  if (headKit === null) return;
  const status = git(["status", "--porcelain", "--", "kits/workspace"]);
  if (!status) return;
  const current = JSON.parse(readFileSync(path.join(KIT, "kit.json"), "utf8")).version;
  const head = JSON.parse(headKit).version;
  assert.ok(semverGreater(current, head), `kit changed but version ${current} is not above HEAD ${head}`);
});
