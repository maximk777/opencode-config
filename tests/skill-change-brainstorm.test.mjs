import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { checkSkill } from "./lib/skill.mjs";

checkSkill("change-brainstorm", [
  "Do not write code or tasks before the user approves the design.",
  "Ask one question per message.",
  "Propose 2-3 approaches and lead with a recommendation.",
  "Write proposal.md and design.md under ~/specs/<project>/openspec/changes/<slug>/.",
  "Never write change artifacts into the work repository.",
  "If ~/specs/<project> does not exist, create it, run git init and openspec init --tools none.",
  "After each approved design section, commit the specs repository",
  "Pass proposal.md and design.md through the humanize skill.",
  "Search OpenViking memory before asking the user.",
  "Set the session title to include [change:<project>/<slug>].",
]);

test("sources.lock pins superpowers brainstorming", () => {
  const lock = readFileSync(new URL("../sources.lock", import.meta.url), "utf8");
  assert.match(lock, /^superpowers-brainstorming\tobra\/superpowers\t[0-9a-f]{7,40}\tskills\/change-brainstorm\/SKILL\.md$/m);
});
