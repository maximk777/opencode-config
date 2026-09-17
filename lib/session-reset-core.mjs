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
    `Needs fix: ${list(state.needs_fix)}`,
    `Ready to accept: ${list(state.ready_to_accept)}`,
    `Current wave: ${state.current_wave ?? "none"}`,
    `OpenSpec status: ${openspecSummary(state.openspec_status)}`,
  ].join("\n");
}

const firstLine = (s) => String(s ?? "").split("\n")[0].slice(0, 200);

// The full openspec JSON carries absolute paths and instructions; the compacted context only needs completion and artifact states.
export function openspecSummary(status) {
  if (!status) return "unknown";
  if (status.error) return `error: ${firstLine(status.error)}`;
  const problem = Array.isArray(status.status) && status.status.find((s) => s.severity === "error");
  if (problem) return `error: ${firstLine(problem.message)}`;
  const artifacts = (status.artifacts ?? []).map((a) => `${a.id}=${a.status}`).join(", ") || "none";
  return `complete=${status.isComplete ?? "unknown"}; artifacts: ${artifacts}`;
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

// The summarizer must hand the next action to the post-compaction turn, not just the state.
const NEXT_DIRECTIVE = "End the summary with a 'Next' section naming the exact next action of the in-flight work.";

export function buildCompactionContext({ agent, state, facts, tokenBudget }) {
  if (!isScopedAgent(agent)) return [];
  const out = [];
  if (state) out.push(renderState(state));
  const block = factsBlock(facts, tokenBudget);
  if (block) out.push(block);
  out.push(NEXT_DIRECTIVE);
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

// Compact only at or above 60% of the serving model's context window.
export const COMPACT_SHARE = 0.6;

const count = (n) => (Number.isFinite(n) ? n : 0);

export function sumTokens(tokens) {
  if (!tokens) return 0;
  return count(tokens.input) + count(tokens.output) + count(tokens.reasoning) + count(tokens.cache?.read) + count(tokens.cache?.write);
}

export function compactionDecision(tokens, limit) {
  if (tokens >= COMPACT_SHARE * limit) return { compact: true };
  const share = Math.round(COMPACT_SHARE * 100);
  return { compact: false, message: `phase_reset skipped: ${tokens} tokens below ${share}% of ${limit}` };
}

// A compaction is not a gate: a scoped session that idles soon after it is pushed to continue.
export const CONTINUE_TTL_MS = 180_000;
export const CONTINUE_COOLDOWN_MS = 120_000;

export function continueDecision({ markedAt, now, lastContinue }) {
  if (markedAt == null) return { send: false, reason: "unmarked" };
  if (now - markedAt > CONTINUE_TTL_MS) return { send: false, reason: "stale" };
  if (lastContinue != null && now - lastContinue < CONTINUE_COOLDOWN_MS) return { send: false, reason: "cooldown" };
  return { send: true };
}

export function continueMessage(ref) {
  const tail =
    " Do not report status and do not wait for the user; stop only when a real user decision is needed.";
  if (!ref) return "Compaction finished; it is not a gate. Continue your current work from the files." + tail;
  const [project, slug] = ref.split("/");
  return (
    `Compaction finished; it is not a gate. Continue change ${ref} now: run ` +
    `~/.config/opencode/bin/change-state ~/specs/${project} ${slug} and continue the flow from its output.` + tail
  );
}
