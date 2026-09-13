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
  const changeRef = async (sessionID) => {
    const r = await client.session.get({ path: { id: sessionID } }).catch(() => null);
    return r?.data?.title?.match(/\[change:([^\]]+)\]/)?.[1] ?? null;
  };

  const readState = async (ref) => {
    if (!ref) return null;
    const [project, slug] = ref.split("/");
    const home = process.env.HOME;
    try {
      return JSON.parse(await $`${home}/.config/opencode/bin/change-state ${home}/specs/${project} ${slug}`.quiet().text());
    } catch {
      return null;
    }
  };

  return {
    "chat.message": async (input) => {
      if (input.agent) agentBySession.set(input.sessionID, input.agent);
    },

    "experimental.session.compacting": async (input, output) => {
      const agent = agentBySession.get(input.sessionID);
      if (!isScopedAgent(agent)) return;
      const state = await readState(await changeRef(input.sessionID));
      const { facts } = await safeFacts(() => findFacts(state?.slug ?? ""));
      output.context.push(...buildCompactionContext({ agent, state, facts, tokenBudget: TOKEN_BUDGET }));
    },

    event: async ({ event }) => {
      if (event.type !== "session.compacted") return;
      const sessionID = event.properties?.sessionID;
      const agent = agentBySession.get(sessionID);
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
          await client.session.summarize({ path: { id: ctx.sessionID }, body: { providerID, modelID: rest.join("/") } });
          return "session compacted";
        },
      }),
    },
  };
};
