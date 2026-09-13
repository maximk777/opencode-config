const SCOPED = new Set(["orchestrator", "architect"]);

export function isScopedAgent(agent) {
  return SCOPED.has(agent);
}

export function renderState(state) {
  const list = (xs) => (xs && xs.length ? xs.join(", ") : "none");
  return [
    `Change: ${state.slug}`,
    `Open tasks: ${list(state.tasks_open)}`,
    `Awaiting review: ${list(state.awaiting_review)}`,
    `Current wave: ${state.current_wave ?? "none"}`,
  ].join("\n");
}

// Rough 4 characters per token keeps the injected facts inside the budget without a tokenizer.
function factsBlock(facts, tokenBudget) {
  if (!facts || facts.length === 0) return null;
  const limit = tokenBudget * 4;
  let text = "Relevant memory:\n";
  for (const f of facts) {
    const line = `- ${f}\n`;
    if (text.length + line.length > limit) {
      text += line.slice(0, Math.max(0, limit - text.length));
      break;
    }
    text += line;
  }
  return text.trimEnd();
}

export function buildCompactionContext({ agent, state, facts, tokenBudget }) {
  if (!isScopedAgent(agent)) return [];
  const out = [];
  if (state) out.push(renderState(state));
  const block = factsBlock(facts, tokenBudget);
  if (block) out.push(block);
  return out;
}

export function summaryPayload({ agent, summary }) {
  if (!isScopedAgent(agent)) return null;
  return { kind: "session-summary", agent, text: summary };
}

export function modelFromTier(text) {
  const [providerID, ...rest] = String(text ?? "").trim().split("/");
  const modelID = rest.join("/");
  return providerID && modelID ? { providerID, modelID } : null;
}

export async function safeFacts(fetchFacts) {
  try {
    return { facts: await fetchFacts(), warning: null };
  } catch (err) {
    return { facts: [], warning: `openviking unavailable: ${err?.message ?? err}` };
  }
}
