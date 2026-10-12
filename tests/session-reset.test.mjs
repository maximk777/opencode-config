import { test } from "node:test";
import assert from "node:assert/strict";
import { isScopedAgent, renderState, buildCompactionContext, openspecSummary, COMPACT_SHARE, sumTokens, compactionDecision } from "../lib/session-reset-core.mjs";

const state = { slug: "add-ping", tasks_open: ["1.2", "1.3"], awaiting_review: ["1.2"], current_wave: 2 };

test("only orchestrator and architect are scoped", () => {
  assert.equal(isScopedAgent("orchestrator"), true);
  assert.equal(isScopedAgent("architect"), true);
  assert.equal(isScopedAgent("executor"), false);
  assert.equal(isScopedAgent(undefined), false);
});

test("executor compaction gets no context", () => {
  assert.deepEqual(buildCompactionContext({ agent: "executor", state }), []);
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

test("scoped compaction context carries state and the next directive", () => {
  const ctx = buildCompactionContext({ agent: "orchestrator", state });
  assert.equal(ctx.length, 2);
  assert.match(ctx[0], /Change: add-ping/);
  assert.match(ctx.at(-1), /'Next' section/);
});

test("missing state keeps only the next directive", () => {
  const ctx = buildCompactionContext({ agent: "architect", state: null });
  assert.equal(ctx.length, 1);
  assert.match(ctx.at(-1), /'Next' section/);
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

test("compaction state lists tasks to fix and to accept", () => {
  const text = renderState({ slug: "x", tasks_done: [], tasks_open: ["1.1", "1.2"], awaiting_review: [], needs_fix: ["1.1"], ready_to_accept: ["1.2"], current_wave: 1 });
  assert.ok(text.includes("Needs fix: 1.1"));
  assert.ok(text.includes("Ready to accept: 1.2"));
});

// The plugin registers a compaction hook and the phase_reset tool through the V2
// context. @opencode/plugin resolves only inside the OpenCode runtime, so tests
// drive the setup callback with a fake ctx instead of importing the real SDK.
const setupPlugin = async (overrides = {}) => {
  const registered = { compaction: [] };
  const tools = [];
  const calls = { compacts: [], logs: [] };
  const ctx = {
    session: {
      hook: async (name, cb) => {
        if (name === "compaction") registered.compaction.push(cb);
      },
      get: overrides.sessionGet ?? (async () => ({ title: "" })),
      context: overrides.sessionContext ?? (async () => []),
      compact: async (input) => {
        calls.compacts.push(input);
      },
    },
    tool: {
      transform: async (cb) =>
        cb({
          add: (t) => tools.push(t),
        }),
    },
    model: { get: overrides.modelGet ?? (async () => null) },
    app: { log: async (req) => calls.logs.push(req.body) },
  };
  const mod = await import("../plugins/session-reset/index.mjs");
  await mod.default.setup(ctx);
  return { registered, tools, calls };
};

test("plugin registers the compaction hook and the phase_reset tool", async () => {
  const { registered, tools } = await setupPlugin();
  assert.equal(registered.compaction.length, 1);
  assert.equal(tools.length, 1);
  assert.equal(tools[0].name, "phase_reset");
  assert.equal(tools[0].input.type, "object");
});

test("compaction hook skips non-scoped agents without touching the system", async () => {
  const { registered } = await setupPlugin();
  const event = { agent: "build", sessionID: "s2", system: [] };
  await registered.compaction[0](event);
  assert.deepEqual(event.system, []);
});

test("scoped compaction with an unavailable change state keeps the next directive and logs", async () => {
  // proj/add-ping does not exist, so bin/change-state fails; the state part is
  // dropped but the summarizer still gets the next-action directive.
  const { registered, calls } = await setupPlugin({
    sessionGet: async () => ({ title: "work [change:proj/add-ping]" }),
  });
  const event = { agent: "orchestrator", sessionID: "s1", system: [] };
  await registered.compaction[0](event);
  assert.equal(event.system.length, 1);
  assert.match(event.system[0].text, /'Next' section/);
  assert.equal(calls.logs.length, 1);
  assert.equal(calls.logs[0].service, "session-reset");
  assert.match(calls.logs[0].message, /change-state failed for proj\/add-ping: /);
  assert.doesNotMatch(calls.logs[0].message, /secret/);
});

test("phase_reset is refused outside scoped sessions", async () => {
  const { tools } = await setupPlugin();
  const out = await tools[0].execute({}, { agent: "build", sessionID: "s1" });
  assert.match(out.content, /only for orchestrator and architect/);
});

test("phase_reset skips compaction below the share and schedules at or above it", async () => {
  const message = (tokens) => ({
    sessionContext: async () => [
      { info: { role: "assistant", providerID: "p", modelID: "m", tokens: { input: tokens, output: 0, reasoning: 0, cache: { read: 0, write: 0 } } } },
    ],
    modelGet: async () => ({ limit: { context: 1000000 } }),
  });
  const skipped = await setupPlugin(message(400000));
  const out = await skipped.tools[0].execute({}, { agent: "orchestrator", sessionID: "s1" });
  assert.equal(out.content, "phase_reset skipped: 400000 tokens below 60% of 1000000");
  assert.deepEqual(skipped.calls.compacts, []);

  const scheduled = await setupPlugin(message(600000));
  const out2 = await scheduled.tools[0].execute({}, { agent: "architect", sessionID: "s2" });
  assert.match(out2.content, /compaction scheduled/);
  assert.deepEqual(scheduled.calls.compacts, [{ sessionID: "s2" }]);
});

test("phase_reset fails safe to compaction when the model limit is unreadable", async () => {
  const { tools, calls } = await setupPlugin({
    sessionContext: async () => [],
    modelGet: async () => {
      throw new Error("offline");
    },
  });
  const out = await tools[0].execute({}, { agent: "orchestrator", sessionID: "s3" });
  assert.match(out.content, /compaction scheduled/);
  assert.deepEqual(calls.compacts, [{ sessionID: "s3" }]);
});
