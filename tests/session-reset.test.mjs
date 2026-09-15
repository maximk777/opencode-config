import { test } from "node:test";
import assert from "node:assert/strict";
import { isScopedAgent, renderState, buildCompactionContext, summaryPayload, safeFacts, modelFromTier, openspecSummary, COMPACT_SHARE, sumTokens, compactionDecision } from "../lib/session-reset-core.mjs";

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
  assert.match(text, /OpenSpec status: unknown/);
});

test("openspec status is shortened to completion and artifact states", () => {
  const status = {
    changeName: "add-ping",
    changeRoot: "/Users/x/specs/p/openspec/changes/add-ping",
    isComplete: false,
    artifacts: [{ id: "proposal", status: "done" }, { id: "tasks", status: "blocked", missingDeps: ["specs"] }],
  };
  assert.equal(openspecSummary(status), "complete=false; artifacts: proposal=done, tasks=blocked");
  assert.match(renderState({ ...state, openspec_status: status }), /OpenSpec status: complete=false; artifacts: proposal=done, tasks=blocked/);
  assert.equal(openspecSummary({ error: "openspec: command not found\ntrace" }), "error: openspec: command not found");
  assert.equal(
    openspecSummary({ status: [{ severity: "error", code: "change_error", message: "Change 'x' not found.\n  y" }] }),
    "error: Change 'x' not found.",
  );
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

test("sumTokens adds all token fields and tolerates missing data", () => {
  assert.equal(COMPACT_SHARE, 0.6);
  assert.equal(sumTokens({ input: 100, output: 10, reasoning: 5, cache: { read: 50, write: 20 } }), 185);
  assert.equal(sumTokens(null), 0);
  assert.equal(sumTokens({ input: 100, output: 10 }), 110);
});

test("compactionDecision gates at 60% of the context window", () => {
  assert.deepEqual(compactionDecision(400000, 1000000), { compact: false, message: "phase_reset skipped: 400000 tokens below 60% of 1000000" });
  assert.deepEqual(compactionDecision(600000, 1000000), { compact: true });
  assert.deepEqual(compactionDecision(700000, 1000000), { compact: true });
});

test("phase_reset summarizes with the fast tier model", async () => {
  const { readFileSync } = await import("node:fs");
  const { SessionReset } = await import("../plugins/session-reset.mjs");
  const tier = modelFromTier(readFileSync(new URL("../tiers/fast", import.meta.url), "utf8"));
  let body;
  const client = {
    session: {
      summarize: async (req) => { body = req.body; },
      messages: async () => ({ data: [] }),
    },
    config: { providers: async () => ({ data: { providers: [] } }) },
  };
  const hooks = await SessionReset({ client, $: null });
  await hooks.tool.phase_reset.execute({}, { agent: "orchestrator", sessionID: "s1" });
  assert.deepEqual(body, tier);
});

const shareClient = (input) => {
  const calls = [];
  const client = {
    session: {
      summarize: async (req) => calls.push(req.body),
      messages: async () => ({
        data: [{ role: "assistant", providerID: "zai-coding-plan", modelID: "glm-5.3", tokens: { input, output: 0, reasoning: 0, cache: { read: 0, write: 0 } } }],
      }),
    },
    config: {
      providers: async () => ({ data: { providers: [{ id: "zai-coding-plan", models: { "glm-5.3": { limit: { context: 1000000, output: 131072 } } } }] } }),
    },
  };
  return { client, calls };
};

test("phase_reset skips summarize below the compaction share", async () => {
  const { SessionReset } = await import("../plugins/session-reset.mjs");
  const { client, calls } = shareClient(400000);
  const hooks = await SessionReset({ client, $: null });
  const out = await hooks.tool.phase_reset.execute({}, { agent: "orchestrator", sessionID: "s1" });
  assert.equal(out, "phase_reset skipped: 400000 tokens below 60% of 1000000");
  assert.deepEqual(calls, []);
});

test("phase_reset schedules summarize at the compaction share", async () => {
  const { readFileSync } = await import("node:fs");
  const { SessionReset } = await import("../plugins/session-reset.mjs");
  const tier = modelFromTier(readFileSync(new URL("../tiers/fast", import.meta.url), "utf8"));
  const { client, calls } = shareClient(600000);
  const hooks = await SessionReset({ client, $: null });
  const out = await hooks.tool.phase_reset.execute({}, { agent: "orchestrator", sessionID: "s1" });
  assert.match(out, /compaction scheduled/);
  assert.equal(calls.length, 1);
  assert.deepEqual(calls[0], tier);
});

test("unreadable tokens or limit fail safe to compaction", async () => {
  const { SessionReset } = await import("../plugins/session-reset.mjs");
  const calls = [];
  const client = {
    session: {
      summarize: async (req) => calls.push(req.body),
      messages: async () => ({ data: [] }),
    },
    config: { providers: () => Promise.reject(new Error("offline")) },
  };
  const hooks = await SessionReset({ client, $: null });
  const out = await hooks.tool.phase_reset.execute({}, { agent: "orchestrator", sessionID: "s1" });
  assert.match(out, /compaction scheduled/);
  assert.equal(calls.length, 1);
});

test("change-state failure is logged as a warning without stderr", async () => {
  const { SessionReset } = await import("../plugins/session-reset.mjs");
  const logs = [];
  const client = {
    app: { log: async (req) => logs.push(req.body) },
    session: {
      get: async () => ({ data: { title: "work [change:proj/add-ping]" } }),
      messages: async () => ({ data: [] }),
    },
  };
  const $ = () => ({
    quiet: () => ({ text: async () => { throw Object.assign(new Error("secret=abc"), { exitCode: 2, stderr: "secret=abc" }); } }),
  });
  const realFetch = globalThis.fetch;
  globalThis.fetch = async () => { throw new Error("offline"); };
  try {
    const hooks = await SessionReset({ client, $ });
    await hooks["chat.message"]({ agent: "orchestrator", sessionID: "s2" });
    const output = { context: [] };
    await hooks["experimental.session.compacting"]({ sessionID: "s2" }, output);
    assert.deepEqual(output.context, []);
  } finally {
    globalThis.fetch = realFetch;
  }
  assert.deepEqual(logs, [{ service: "session-reset", level: "warn", message: "change-state failed for proj/add-ping: exit 2" }]);
});

test("compaction state lists tasks to fix and to accept", () => {
  const text = renderState({ slug: "x", tasks_done: [], tasks_open: ["1.1", "1.2"], awaiting_review: [], needs_fix: ["1.1"], ready_to_accept: ["1.2"], current_wave: 1 });
  assert.ok(text.includes("Needs fix: 1.1"));
  assert.ok(text.includes("Ready to accept: 1.2"));
});
