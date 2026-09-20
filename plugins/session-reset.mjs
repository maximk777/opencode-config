import { readFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";
import { tool } from "@opencode-ai/plugin";
import { isScopedAgent, buildCompactionContext, summaryPayload, safeFacts, modelFromTier, sumTokens, compactionDecision, continueDecision, continueMessage, artifactPayload, artifactDecision, fingerprint } from "../lib/session-reset-core.mjs";

const TOKEN_BUDGET = 1500;
const OV = "http://127.0.0.1:1933";
const agentBySession = new Map();
const pendingContinue = new Map();
const lastContinueAt = new Map();
const artifactAt = new Map();
const artifactHash = new Map();

// The key file works when OpenCode is started outside an interactive shell, where the env variable is missing.
const ovHeaders = async () => {
  const key = process.env.OPENVIKING_API_KEY || (await readFile(join(homedir(), ".openviking", "mcp-key"), "utf8").catch(() => "")).trim();
  return { "content-type": "application/json", authorization: `Bearer ${key}` };
};

// Memory URIs are per user; the server names the user that owns the key.
const ovUser = async (headers) => {
  const res = await fetch(`${OV}/api/v1/system/status`, { headers }).catch(() => null);
  return res?.ok ? (await res.json()).result?.user : undefined;
};

async function findFacts(query) {
  const res = await fetch(`${OV}/api/v1/search/find`, {
    method: "POST",
    headers: await ovHeaders(),
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
    } catch (err) {
      // Only the exit code or error class is logged: change-state stderr is not guaranteed to be free of secrets.
      const reason = err?.exitCode != null ? `exit ${err.exitCode}` : (err?.name ?? "error");
      await client.app
        ?.log?.({ body: { service: "session-reset", level: "warn", message: `change-state failed for ${ref}: ${reason}` } })
        ?.catch?.(() => {});
      return null;
    }
  };

  // A compaction is not a gate: when a scoped session goes idle right after compacting, send the
  // continuation ourselves. Idle means no loop is running, so the prompt cannot race the session.
  const continueAfterCompaction = async (sessionID) => {
    if (!sessionID || !pendingContinue.has(sessionID)) return;
    const markedAt = pendingContinue.get(sessionID);
    pendingContinue.delete(sessionID);
    const agent = await agentFor(sessionID);
    if (!isScopedAgent(agent)) return;
    const now = Date.now();
    if (!continueDecision({ markedAt, now, lastContinue: lastContinueAt.get(sessionID) }).send) return;
    lastContinueAt.set(sessionID, now);
    const ref = await changeRef(sessionID);
    const ok = await client.session
      .promptAsync({ path: { id: sessionID }, body: { agent, parts: [{ type: "text", text: continueMessage(ref) }] } })
      .then(
        () => true,
        () => false,
      );
    if (!ok) {
      await client.app
        ?.log?.({ body: { service: "session-reset", level: "warn", message: `auto-continue failed for ${sessionID}` } })
        ?.catch?.(() => {});
    }
  };

  // Non-scoped sessions (build, executor, ...) leave a plain vectors-only artifact after a turn;
  // scoped agents keep their compaction-time summary instead.
  const saveIdleArtifact = async (sessionID) => {
    if (!sessionID) return;
    const agent = await agentFor(sessionID);
    if (!agent || isScopedAgent(agent)) return;
    const info = await client.session.get({ path: { id: sessionID } }).catch(() => null);
    const msgs = await client.session.messages({ path: { id: sessionID } }).catch(() => null);
    const payload = artifactPayload({ agent, title: info?.data?.title, messages: msgs?.data ?? [] });
    if (!payload) return;
    const hash = fingerprint(payload.text);
    const d = artifactDecision({ now: Date.now(), lastWriteAt: artifactAt.get(sessionID), changed: artifactHash.get(sessionID) !== hash });
    if (!d.write) return;
    const headers = await ovHeaders();
    const user = await ovUser(headers);
    const res = user
      ? await fetch(`${OV}/api/v1/content/write`, {
          method: "POST",
          headers,
          body: JSON.stringify({ uri: `viking://user/${user}/memories/sessions/${sessionID}.md`, content: payload.text, mode: "replace", processing_mode: "vectors_only" }),
        }).catch(() => null)
      : null;
    if (!res?.ok) {
      await client.app?.log?.({ body: { service: "session-reset", level: "warn", message: `session artifact not saved: ${user ? `write ${res?.status ?? "failed"}` : "OpenViking user unknown"}` } }).catch?.(() => {});
      return;
    }
    artifactHash.set(sessionID, hash);
    artifactAt.set(sessionID, Date.now());
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
      if (event.type === "session.idle") {
        await continueAfterCompaction(event.properties?.sessionID);
        return saveIdleArtifact(event.properties?.sessionID);
      }
      if (event.type !== "session.compacted") return;
      const sessionID = event.properties?.sessionID;
      const agent = await agentFor(sessionID);
      if (!isScopedAgent(agent)) return;
      // Mark before the summary save: a missing summary must not drop the continuation.
      pendingContinue.set(sessionID, Date.now());
      const msgs = await client.session.messages({ path: { id: sessionID } }).catch(() => null);
      const last = [...(msgs?.data ?? [])].reverse().find((m) => m.info?.summary);
      const summary = last?.parts?.map((p) => p.text ?? "").join("\n").trim();
      const payload = summaryPayload({ agent, summary });
      if (!payload || !summary) return;
      const headers = await ovHeaders();
      const user = await ovUser(headers);
      const res = user
        ? await fetch(`${OV}/api/v1/content/write`, {
            method: "POST",
            headers,
            body: JSON.stringify({ uri: `viking://user/${user}/memories/sessions/${sessionID}.md`, content: payload.text, mode: "replace", processing_mode: "vectors_only" }),
          }).catch(() => null)
        : null;
      if (!res?.ok) {
        await client.app?.log?.({ body: { service: "session-reset", level: "warn", message: `session summary not saved: ${user ? `write ${res?.status ?? "failed"}` : "OpenViking user unknown"}` } }).catch(() => {});
      }
    },

    tool: {
      phase_reset: tool({
        description: "Compact this orchestrator or architect session at a gate; the change state is restored from files",
        args: {},
        async execute(_args, ctx) {
          if (!isScopedAgent(ctx.agent)) return "phase_reset is only for orchestrator and architect sessions";
          const msgs = await client.session.messages({ path: { id: ctx.sessionID } }).catch(() => null);
          const last = [...(msgs?.data ?? [])].reverse().find((m) => m.role === "assistant");
          const tokens = last ? sumTokens(last.tokens) : 0;
          const providers = await client.config.providers().catch(() => null);
          const limit = providers?.data?.providers?.find((p) => p.id === last?.providerID)?.models?.[last?.modelID]?.limit?.context;
          if (last && Number.isFinite(limit) && limit > 0) {
            const d = compactionDecision(tokens, limit);
            if (!d.compact) return d.message;
          }
          const tier = new URL("../tiers/fast", import.meta.url);
          const model = modelFromTier(await readFile(tier, "utf8").catch(() => ""));
          if (!model) return `phase_reset: ${tier.pathname} does not name a provider/model`;
          // Awaiting summarize here deadlocks: it waits for the session to go idle, and the session is busy running this tool.
          client.session.summarize({ path: { id: ctx.sessionID }, body: model }).catch(() => {});
          return "compaction scheduled: finish this turn now; after compaction the session continues automatically";
        },
      }),
    },
  };
};
