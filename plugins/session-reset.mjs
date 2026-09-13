import { tool } from "@opencode-ai/plugin";
import { isScopedAgent, buildCompactionContext, summaryPayload, safeFacts } from "../lib/session-reset-core.mjs";

const TOKEN_BUDGET = 1500;
const OV = "http://127.0.0.1:1933";
const agentBySession = new Map();

const ovHeaders = () => ({
  "content-type": "application/json",
  authorization: `Bearer ${process.env.OPENVIKING_API_KEY ?? ""}`,
});

async function findFacts(query) {
  const res = await fetch(`${OV}/api/v1/search/find`, {
    method: "POST",
    headers: ovHeaders(),
    body: JSON.stringify({ query, limit: 6 }),
  });
  if (!res.ok) throw new Error(`find ${res.status}`);
  const data = await res.json();
  const items = data.result?.resources ?? data.result?.memories ?? data.results ?? data.items ?? [];
  return items.map((x) => x.abstract ?? x.overview ?? x.content ?? x.uri).filter(Boolean);
}

export const SessionReset = async ({ client, $ }) => {
  // A continued session in a new process has an empty map, so fall back to the agent recorded on its messages.
  const agentFor = async (sessionID) => {
    if (agentBySession.has(sessionID)) return agentBySession.get(sessionID);
    const msgs = await client.session.messages({ path: { id: sessionID } }).catch(() => null);
    const agent = [...(msgs?.data ?? [])].reverse().find((m) => m.info?.agent)?.info?.agent;
    if (agent) agentBySession.set(sessionID, agent);
    return agent;
  };

  const changeRef = async (sessionID) => {
    const r = await client.session.get({ path: { id: sessionID } }).catch(() => null);
    return r?.data?.title?.match(/\[change:([^\]]+)\]/)?.[1] ?? null;
  };

  const readState = async (ref) => {
    if (!ref) return null;
    const [project, slug] = ref.split("/");
    const home = process.env.HOME;
    const changeState = new URL("../bin/change-state", import.meta.url).pathname;
    try {
      return JSON.parse(await $`${changeState} ${home}/specs/${project} ${slug}`.quiet().text());
    } catch {
      return null;
    }
  };

  return {
    "chat.message": async (input) => {
      if (input.agent) agentBySession.set(input.sessionID, input.agent);
    },

    "experimental.session.compacting": async (input, output) => {
      const agent = await agentFor(input.sessionID);
      if (!isScopedAgent(agent)) return;
      const state = await readState(await changeRef(input.sessionID));
      const { facts } = await safeFacts(() => findFacts(state?.slug ?? ""));
      output.context.push(...buildCompactionContext({ agent, state, facts, tokenBudget: TOKEN_BUDGET }));
    },

    event: async ({ event }) => {
      if (event.type !== "session.compacted") return;
      const sessionID = event.properties?.sessionID;
      const agent = await agentFor(sessionID);
      if (!isScopedAgent(agent)) return;
      const msgs = await client.session.messages({ path: { id: sessionID } }).catch(() => null);
      const last = [...(msgs?.data ?? [])].reverse().find((m) => m.info?.summary);
      const summary = last?.parts?.map((p) => p.text ?? "").join("\n").trim();
      const payload = summaryPayload({ agent, summary });
      if (!payload || !summary) return;
      await fetch(`${OV}/api/v1/content/write`, {
        method: "POST",
        headers: ovHeaders(),
        body: JSON.stringify({ uri: `viking://user/memories/sessions/${sessionID}.md`, content: payload.text, mode: "upsert" }),
      }).catch(() => {});
    },

    tool: {
      phase_reset: tool({
        description: "Compact this orchestrator or architect session at a gate; the change state is restored from files",
        args: {},
        async execute(_args, ctx) {
          if (!isScopedAgent(ctx.agent)) return "phase_reset is only for orchestrator and architect sessions";
          const cfg = await client.config.get().catch(() => null);
          const [providerID, ...rest] = String(cfg?.data?.model ?? "zai-coding-plan/glm-5.3").split("/");
          // Awaiting summarize here deadlocks: it waits for the session to go idle, and the session is busy running this tool.
          client.session
            .summarize({ path: { id: ctx.sessionID }, body: { providerID, modelID: rest.join("/") } })
            .catch(() => {});
          return "compaction scheduled: finish this turn now; the next turn starts from the compacted summary and the change files";
        },
      }),
    },
  };
};
