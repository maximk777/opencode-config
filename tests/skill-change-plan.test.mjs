import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { checkSkill } from "./lib/skill.mjs";

checkSkill("change-plan", [
  "Write tasks.md in OpenSpec checkbox format and one brief per task from templates/brief.md.",
  "Each task is 2-10 minutes of work",
  "Set skeleton: yes only when the brief contains the code skeleton.",
  "Run ~/.config/opencode/bin/waves <change-dir> and save its output to waves.md.",
  "Tasks in one wave never share a file or a Go package.",
  "Stop and ask the user to approve the plan before execution.",
  "After approval, commit the specs repository with",
  "run ~/.config/opencode/bin/ov-sync <project>; it only queues the project and returns at once",
]);

const tpl = (n) => readFileSync(new URL(`../skills/change-plan/templates/${n}`, import.meta.url), "utf8");

test("brief template carries wave metadata and constraints", () => {
  const brief = tpl("brief.md");
  assert.ok(brief.includes("skeleton:"));
  assert.ok(brief.includes("Do not commit."));
});

test("report template has a status line", () => assert.ok(tpl("report.md").includes("Status:")));
