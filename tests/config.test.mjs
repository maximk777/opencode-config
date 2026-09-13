import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;
const cfg = () => JSON.parse(readFileSync(join(ROOT, "opencode.json"), "utf8"));

test("every agent model references a tier file", () => {
  for (const [name, a] of Object.entries(cfg().agent ?? {})) {
    assert.match(a.model ?? "", /^\{file:\.\/tiers\/[a-z]+\}$/, `agent ${name}`);
  }
});

test("tier files hold one provider/model line", () => {
  for (const t of ["smart", "fast"]) {
    const v = readFileSync(join(ROOT, "tiers", t), "utf8").trim();
    assert.match(v, /^[a-z0-9-]+\/[a-z0-9.\-]+$/, t);
  }
});

test("provider keys come from the environment", () => {
  for (const [id, p] of Object.entries(cfg().provider ?? {})) {
    const key = p.options?.apiKey;
    if (key !== undefined) assert.match(key, /^\{env:[A-Z0-9_]+\}$/, id);
  }
});

function walk(dir, out = []) {
  for (const n of readdirSync(dir)) {
    if ([".git", "node_modules", "tests"].includes(n)) continue;
    const p = join(dir, n);
    statSync(p).isDirectory() ? walk(p, out) : out.push(p);
  }
  return out;
}

test("no file invokes opencode debug config", () => {
  for (const f of walk(ROOT)) {
    const text = readFileSync(f, "utf8");
    assert.ok(!/^\s*(\$ )?opencode debug config/m.test(text), f);
  }
});
