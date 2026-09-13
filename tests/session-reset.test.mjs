import { test } from "node:test";
import assert from "node:assert/strict";
import { isScopedAgent, renderState, buildCompactionContext, summaryPayload, safeFacts, modelFromTier } from "../lib/session-reset-core.mjs";

const state = { slug: "add-ping", tasks_open: ["1.2", "1.3"], awaiting_review: ["1.2"], current_wave: 2 };

test("only orchestrator and architect are scoped", () => {
  assert.equal(isScopedAgent("orchestrator"), true);
  assert.equal(isScopedAgent("architect"), true);
  assert.equal(isScopedAgent("executor"), false);
  assert.equal(isScopedAgent(undefined), false);
});

test("executor compaction gets no context", () => {
  assert.deepEqual(buildCompactionContext({ agent: "executor", state, facts: ["x"], tokenBudget: 500 }), []);
});

test("state names awaiting review and current wave", () => {
  const text = renderState(state);
  assert.match(text, /Change: add-ping/);
  assert.match(text, /Awaiting review: 1\.2/);
  assert.match(text, /Current wave: 2/);
});

test("facts are cut to the token budget", () => {
  const ctx = buildCompactionContext({ agent: "orchestrator", state, facts: ["a".repeat(10000)], tokenBudget: 100 });
  assert.ok(ctx.join("").length <= renderState(state).length + 400 + 50);
});

test("only the summary is sent", () => {
  assert.deepEqual(summaryPayload({ agent: "orchestrator", summary: "S" }), { kind: "session-summary", agent: "orchestrator", text: "S" });
  assert.equal(summaryPayload({ agent: "executor", summary: "S" }), null);
});

test("openviking failure falls back to files", async () => {
  const r = await safeFacts(() => Promise.reject(new Error("ECONNREFUSED")));
  assert.deepEqual(r.facts, []);
  assert.match(r.warning, /ECONNREFUSED/);
  const ctx = buildCompactionContext({ agent: "orchestrator", state, facts: r.facts, tokenBudget: 500 });
  assert.equal(ctx.length, 1);
});

test("missing state keeps facts only", () => {
  const ctx = buildCompactionContext({ agent: "architect", state: null, facts: ["fact one"], tokenBudget: 500 });
  assert.equal(ctx.length, 1);
  assert.match(ctx[0], /fact one/);
});

test("tier file becomes provider and model ids", () => {
  assert.deepEqual(modelFromTier("zai-coding-plan/glm-5.3-flash\n"), { providerID: "zai-coding-plan", modelID: "glm-5.3-flash" });
  assert.deepEqual(modelFromTier("openrouter/vendor/model"), { providerID: "openrouter", modelID: "vendor/model" });
  assert.equal(modelFromTier(""), null);
  assert.equal(modelFromTier("no-slash"), null);
});

test("phase_reset summarizes with the fast tier model", async () => {
  const { readFileSync } = await import("node:fs");
  const { SessionReset } = await import("../plugins/session-reset.mjs");
  const tier = modelFromTier(readFileSync(new URL("../tiers/fast", import.meta.url), "utf8"));
  let body;
  const client = { session: { summarize: async (req) => { body = req.body; } } };
  const hooks = await SessionReset({ client, $: null });
  await hooks.tool.phase_reset.execute({}, { agent: "orchestrator", sessionID: "s1" });
  assert.deepEqual(body, tier);
});
