import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const ROOT = new URL("../..", import.meta.url).pathname;

export function readSkill(name) {
  return readFileSync(`${ROOT}skills/${name}/SKILL.md`, "utf8");
}

export function checkSkill(name, phrases) {
  const text = readSkill(name);
  test(`${name}: frontmatter`, () => {
    assert.match(text, new RegExp(`^---\\nname: ${name}\\n`));
    assert.match(text, /\ndescription: Use when /);
  });
  test(`${name}: size and language`, () => {
    assert.ok(text.split("\n").length <= 500);
    assert.ok(!/[Ѐ-ӿ]/.test(text));
  });
  for (const p of phrases) {
    test(`${name}: contains "${p}"`, () => assert.ok(text.includes(p)));
  }
}
