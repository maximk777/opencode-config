import { execFile } from "node:child_process";
import { Plugin } from "@opencode/plugin";
import { isScopedAgent, buildCompactionContext, sumTokens, compactionDecision } from "../../lib/session-reset-core.mjs";

// V2 port of the session-reset plugin, memory-free: the change state comes from
// files at compaction time, and V2 continues a compacted session on its own,
// so there is no continuation logic and no event subscription here.
export default Plugin.define({
  id: "session-reset",
  async setup(ctx) {
    const log = (message) => {
      // Only the error class is logged: stderr is not guaranteed to be free of secrets.
      try {
        const r = ctx.app?.log?.({ body: { service: "session-reset", level: "warn", message } });
        r?.catch?.(() => {});
      } catch {
        console.error(`session-reset: ${message}`);
      }
    };

    // Inject the file-derived change state into checkpoint summaries of scoped agents.
    await ctx.session.hook("compaction", async (event) => {
      if (!isScopedAgent(event.agent)) return;
      const state = await readState(await changeRef(ctx, event.sessionID), log);
      for (const text of buildCompactionContext({ agent: event.agent, state })) {
        event.system.push({ type: "text", text });
      }
    });

    // Compact orchestrator or architect sessions at a gate; V2 resumes the session
    // at the next step boundary on its own, so no continuation prompt is needed.
    await ctx.tool.transform((editor) => {
      editor.add({
        name: "phase_reset",
        description: "Compact this orchestrator or architect session at a gate; the change state is restored from files",
        input: { type: "object", properties: {}, additionalProperties: false },
        async execute(_input, context) {
          const sessionID = context?.sessionID;
          if (!sessionID || !isScopedAgent(context?.agent)) {
            return { content: "phase_reset is only for orchestrator and architect sessions" };
          }
          const msgs = await ctx.session.context({ sessionID }).catch(() => null);
          const last = [...(msgs ?? [])].reverse().find((m) => (m?.info ?? m)?.role === "assistant");
          const info = last?.info ?? last;
          const tokens = sumTokens(info?.tokens);
          if (info?.providerID && info?.modelID) {
            const model = await ctx.model.get(info.providerID, info.modelID).catch(() => null);
            const limit = model?.limit?.context;
            if (Number.isFinite(limit) && limit > 0) {
              const d = compactionDecision(tokens, limit);
              if (!d.compact) return { content: d.message };
            }
          }
          await ctx.session.compact({ sessionID }).catch(() => log(`compact failed for ${sessionID}`));
          return { content: "compaction scheduled: finish this turn now; the session continues after compaction" };
        },
      });
    });
  },
});

// The session title carries an optional [change:project/slug] marker set by the flow.
const changeRef = async (ctx, sessionID) => {
  const r = await ctx.session.get({ sessionID }).catch(() => null);
  return r?.title?.match(/\[change:([^\]]+)\]/)?.[1] ?? null;
};

// Only the exit code or error class surfaces here: change-state stderr is not
// guaranteed to be free of secrets.
const readState = (ref, log) => {
  if (!ref) return Promise.resolve(null);
  const [project, slug] = ref.split("/");
  const script = new URL("../../bin/change-state", import.meta.url).pathname;
  const home = process.env.HOME;
  return new Promise((resolve) => {
    execFile(script, [`${home}/specs/${project}`, slug], { timeout: 15000 }, (err, stdout) => {
      if (err) {
        const reason = err?.code != null ? `code ${err.code}` : (err?.name ?? "error");
        log(`change-state failed for ${ref}: ${reason}`);
        resolve(null);
        return;
      }
      try {
        resolve(JSON.parse(stdout));
      } catch {
        resolve(null);
      }
    });
  });
};
