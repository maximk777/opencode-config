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

// The summarizer must hand the next action to the post-compaction turn, not just the state.
const NEXT_DIRECTIVE = "End the summary with a 'Next' section naming the exact next action of the in-flight work.";

export function buildCompactionContext({ agent, state }) {
  if (!isScopedAgent(agent)) return [];
  const out = [];
  if (state) out.push(renderState(state));
  out.push(NEXT_DIRECTIVE);
  return out;
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
