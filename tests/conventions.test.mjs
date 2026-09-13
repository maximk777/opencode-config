import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const text = readFileSync(new URL("../AGENTS.md", import.meta.url), "utf8");

const sentences = [
  "Answer the user in Russian.",
  "Never commit unless the user asks.",
  "Commit messages are one English line: type(scope): subject.",
  "Install a commit-msg hook only into a specific repository and only on request; never set core.hooksPath globally.",
  "Comment only non-obvious decisions, or add a one or two line doc comment on a method.",
  "Never run opencode debug config.",
  "Pass long texts through the humanize skill.",
];

for (const s of sentences) {
  test(`AGENTS.md contains: ${s}`, () => assert.ok(text.includes(s)));
}

test("AGENTS.md is short", () => assert.ok(text.split("\n").length <= 80));

test("AGENTS.md is English", () => assert.ok(!/[Ѐ-ӿ]/.test(text)));

for (const h of ["## Language", "## Commits", "## Code comments", "## Secrets", "## Long texts"]) {
  test(`AGENTS.md has section ${h}`, () => assert.ok(text.includes(h)));
}
