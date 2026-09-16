import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;
const lock = readFileSync(`${ROOT}sources.lock`, "utf8");

// designer lines: sources.lock rows whose target lives under assets/designer/
const designerLines = lock
  .split("\n")
  .filter((l) => l && l.split("\t")[3]?.startsWith("assets/designer/"))
  .map((l) => l.split("\t"));

test("sources.lock pins exactly the three designer kits", () =>
  assert.deepEqual(
    designerLines.map((f) => f[0]).sort(),
    ["antd-kit", "plain-tokens", "tailwind-daisyui-kit"]
  ));

for (const [lockName, , lockVersion, target] of designerLines) {
  const kitDir = join(ROOT, target);
  test(`${lockName} target exists in the cache`, () => assert.ok(existsSync(kitDir), kitDir));
  const kit = JSON.parse(readFileSync(join(kitDir, "kit.json"), "utf8"));
  test(`${lockName} pin equals kit.json version`, () => assert.equal(kit.version, lockVersion));
  test(`${lockName} kit name matches its directory`, () => assert.equal(kit.name, dirname(target.trim()).split("/").pop()));
  test(`${lockName} has template.dc.html and CHEATSHEET.md`, () => {
    assert.ok(existsSync(join(kitDir, "template.dc.html")), `${kitDir}/template.dc.html`);
    assert.ok(existsSync(join(kitDir, "CHEATSHEET.md")), `${kitDir}/CHEATSHEET.md`);
  });
  // templates are served locally; relative vendor references only
  test(`${lockName} template.dc.html has no absolute urls`, () =>
    assert.doesNotMatch(readFileSync(join(kitDir, "template.dc.html"), "utf8"), /https?:\/\//));
}
