import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";

const ROOT = new URL("..", import.meta.url).pathname;
const cfg = JSON.parse(readFileSync(`${ROOT}opencode.json`, "utf8"));
const A = cfg.agent;
const prompt = (n) => readFileSync(`${ROOT}prompts/${n}.md`, "utf8");

test("orchestrator is primary on the smart tier", () => {
  assert.equal(A.orchestrator.mode, "primary");
  assert.equal(A.orchestrator.model, "{file:./tiers/smart}");
});

test("executors and reviewer are hidden subagents with the right tiers", () => {
  for (const n of ["executor", "executor-strong", "task-reviewer"]) {
    assert.equal(A[n].mode, "subagent", n);
    assert.equal(A[n].hidden, true, n);
  }
  assert.equal(A.executor.model, "{file:./tiers/fast}");
  assert.equal(A["executor-strong"].model, "{file:./tiers/smart}");
  assert.equal(A["task-reviewer"].model, "{file:./tiers/smart}");
});

test("executors cannot commit and the orchestrator commits only on approval", () => {
  assert.equal(A.orchestrator.permission.bash["git commit*"], "ask");
  for (const n of ["executor", "executor-strong"]) {
    assert.equal(A[n].permission.bash["git commit*"], "deny", n);
  }
  const orchestratorPrompt = prompt("orchestrator");
  assert.ok(orchestratorPrompt.includes("Never commit in the work repository unless the user asks; git commit and git push ask for approval."));
  assert.ok(!orchestratorPrompt.includes("Never commit in the work repository. Commit only"));
});

test("orchestrator edits only specs and dispatches only the flow subagents", () => {
  assert.deepEqual(A.orchestrator.permission.edit, { "*": "deny", "../*specs/*": "allow" });
  assert.deepEqual(A.orchestrator.permission.task, {
    "*": "deny", executor: "allow", "executor-strong": "allow", "task-reviewer": "allow", explorer: "allow", "web-researcher": "allow",
  });
});

test("web-researcher is a visible fast subagent with web tools only", () => {
  assert.equal(A["web-researcher"].mode, "subagent");
  assert.notEqual(A["web-researcher"].hidden, true);
  assert.equal(A["web-researcher"].model, "{file:./tiers/fast}");
  assert.equal(A["web-researcher"].steps, 40);
  assert.equal(A["web-researcher"].permission.edit, "deny");
  assert.equal(A["web-researcher"].permission.task, "deny");
  assert.deepEqual(A["web-researcher"].permission.bash, { "*": "deny" });
  assert.equal(A["web-researcher"].permission.webfetch, "allow");
  assert.equal(A["web-researcher"].permission.websearch, "allow");
  assert.ok(prompt("web-researcher").includes("Cross-check every key claim across at least two independent sources"));
});

test("reviewer has no memory tools and cannot edit code", () => {
  assert.equal(A["task-reviewer"].permission["openviking_*"], "deny");
  assert.equal(A["task-reviewer"].permission.edit["*"], "deny");
});

test("executors may only find and read in memory", () => {
  for (const n of ["executor", "executor-strong"]) {
    assert.equal(A[n].permission["openviking_*"], "deny", n);
    assert.equal(A[n].permission.openviking_find, "allow", n);
    assert.equal(A[n].permission.openviking_read, "allow", n);
  }
});

test("prompts carry the key rules", () => {
  assert.ok(prompt("executor").includes("Do not commit."));
  assert.ok(prompt("executor").includes("Comment only non-obvious decisions."));
  assert.ok(prompt("executor-strong").includes("Do not commit."));
  assert.ok(prompt("task-reviewer").includes("Do not trust the report; read the diff yourself."));
  assert.ok(prompt("task-reviewer").includes("Append to the report; never rewrite or delete earlier content."));
  assert.ok(prompt("orchestrator").includes("change-brainstorm"));
});

const ORCH_GATES = "run ~/.config/opencode/bin/ov-sync <project> only at gates: an accepted document, an approved spec, an approved plan, an accepted wave and the archive";
const ARCH_GATES = "run ~/.config/opencode/bin/ov-sync <project> only at gates: an accepted document or an accepted PoC result";
const MEMORY = 'Memory: query="<query>" hits=<N> used=yes|no rederived=<ADR or map path|none>';
const EXPLORER_MEMORY = '0. Memory: the line `Memory: query="<query>" hits=<N> used=yes|no rederived=none` for one find or search you ran on the question first; when openviking tools are unavailable, write hits=0 used=no rederived=none and the reason on the next line as `Memory error: <text>`.';

test("orchestrator syncs only at gates and copies explorer Memory lines", () => {
  const p = prompt("orchestrator");
  assert.ok(p.includes(ORCH_GATES));
  assert.ok(!p.includes("edit files, then run"));
  assert.ok(p.includes("copy the Memory line from each explorer report into decisions.md"));
  const at = p.indexOf("## Resume");
  assert.notEqual(at, -1, "orchestrator prompt has no ## Resume heading");
  const resume = p.slice(at);
  assert.ok(resume.includes("read the decisions.md it names"));
  assert.ok(resume.includes("one find scoped to the change"));
  assert.ok(resume.includes("when synced_commit differs from HEAD, trust the files"));
});

test("resume restores the todo list right after change-state", () => {
  const p = prompt("orchestrator");
  const resume = p.slice(p.indexOf("## Resume"));
  assert.ok(resume.includes(
    "Right after change-state, run ~/.config/opencode/bin/change-todos ~/specs/<project> <slug> and pass its output unchanged to todowrite when that tool is available; skip the step otherwise."
  ));
  assert.ok(resume.includes(
    "When change-todos exits non-zero or todowrite returns an error, skip the step without reporting it and continue."
  ));
  const cmd = readFileSync(`${ROOT}commands/resume.md`, "utf8");
  const line =
    "Right after change-state, run ~/.config/opencode/bin/change-todos ~/specs/<project> $ARGUMENTS and pass its output unchanged to todowrite when that tool is available; skip the step otherwise.";
  assert.ok(cmd.includes(line));
  assert.ok(cmd.includes(
    "When change-todos exits non-zero or todowrite returns an error, skip the step without reporting it and continue."
  ));
  assert.ok(cmd.indexOf("change-todos") > cmd.indexOf("bin/change-state"));
  assert.ok(cmd.indexOf("change-todos") < cmd.indexOf("read the decisions.md it names"));
});

test("explorer output format starts with the Memory line", () => {
  const p = prompt("explorer");
  const at = p.indexOf("Output format:\n");
  assert.notEqual(at, -1, "explorer prompt has no Output format: heading");
  const format = p.slice(at + "Output format:\n".length);
  assert.ok(format.startsWith(EXPLORER_MEMORY + "\n1. Answer:"));
  const item0 = format.split("\n")[0];
  assert.ok(item0.includes("`Memory error: <text>`"));
  assert.ok(item0.includes("on the next line"));
});

test("generated Claude agents carry the gate sync and Memory line wording", () => {
  // Uses the same generator as tests/test_claude_link.py, in memory, without writing ~/.claude.
  const script = [
    "import importlib.machinery, json, sys",
    "from pathlib import Path",
    "L = importlib.machinery.SourceFileLoader('claude_link', sys.argv[1] + 'bin/claude-link').load_module()",
    "print(json.dumps(L.plan_agents(Path(sys.argv[1]))))",
  ].join("\n");
  const agents = JSON.parse(execFileSync("python3", ["-c", script, ROOT], { encoding: "utf8" }));
  assert.ok(agents.orchestrator.includes(ORCH_GATES));
  assert.ok(agents.orchestrator.includes("copy the Memory line from each explorer report into decisions.md"));
  assert.ok(agents.architect.includes(ARCH_GATES));
  assert.ok(agents.architect.includes(MEMORY));
  assert.ok(agents.explorer.includes(EXPLORER_MEMORY));
});
