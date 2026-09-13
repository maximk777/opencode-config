import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;
const doc = readFileSync(`${ROOT}docs/ARCHITECTURE.md`, "utf8");

const SECRETS = [
  /eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/,
  /sk-[A-Za-z0-9]{20,}/,
  /ghp_[A-Za-z0-9]{20,}/,
  /glpat-[A-Za-z0-9_-]{20,}/,
];

function walk(dir, out = []) {
  for (const n of readdirSync(dir)) {
    if ([".git", "node_modules", "export", "static", "tests", "__pycache__"].includes(n)) continue;
    const p = join(dir, n);
    statSync(p).isDirectory() ? walk(p, out) : out.push(p);
  }
  return out;
}

test("architecture document exists and explains extension", () => {
  assert.ok(doc.includes("oc-agent"));
  assert.ok(doc.includes("tiers/"));
});

test("no line invokes opencode debug config", () => {
  assert.ok(!/^\s*(\$ )?opencode debug config/m.test(doc));
});

test("repository contains no secrets", () => {
  for (const f of walk(ROOT)) {
    const text = readFileSync(f, "utf8");
    for (const re of SECRETS) assert.ok(!re.test(text), `${f} matches ${re}`);
  }
});
