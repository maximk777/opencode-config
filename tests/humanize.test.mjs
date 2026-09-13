import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const ROOT = new URL("..", import.meta.url).pathname;
const skill = readFileSync(`${ROOT}skills/humanize/SKILL.md`, "utf8");
const lock = readFileSync(`${ROOT}sources.lock`, "utf8");

test("humanize skill is short", () => assert.ok(skill.split("\n").length <= 200));
test("humanize skill names its source commit", () => assert.ok(skill.includes("blader/humanizer@9862685")));
test("humanize skill has Russian stock phrases", () => assert.ok(skill.includes("## Russian stock phrases")));
test("humanize skill keeps the strongest pattern", () => assert.ok(skill.includes("Not X but Y")));
test("humanize skill has embedded mode", () => assert.ok(skill.includes("Embedded mode")));
test("sources.lock pins humanizer", () => assert.match(lock, /^humanizer\tblader\/humanizer\t9862685\tskills\/humanize\/SKILL\.md$/m));
