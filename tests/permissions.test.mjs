import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { homedir } from "node:os";

// Mirrors OpenCode 1.18.30: core/util/wildcard.ts match, permission/index.ts expand, fromConfig and findLast.
// The shell tool checks every command of a pipeline or list on its own, with its redirections.
const cfg = JSON.parse(readFileSync(new URL("../opencode.json", import.meta.url), "utf8"));

function match(str, pattern) {
  let escaped = pattern.replace(/[.+^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*").replace(/\?/g, ".");
  if (escaped.endsWith(" .*")) escaped = escaped.slice(0, -3) + "( .*)?";
  return new RegExp("^" + escaped + "$", "s").test(str);
}

function expand(p) {
  if (p.startsWith("~/")) return homedir() + p.slice(1);
  if (p.startsWith("$HOME")) return homedir() + p.slice(5);
  return p;
}

function fromConfig(permission = {}) {
  return Object.entries(permission).flatMap(([key, value]) =>
    typeof value === "string"
      ? [{ permission: key, pattern: "*", action: value }]
      : Object.entries(value).map(([pattern, action]) => ({ permission: key, pattern: expand(pattern), action })),
  );
}

function decide(agent, permission, input) {
  const rules = [...fromConfig(cfg.permission), ...fromConfig(cfg.agent[agent].permission)];
  const rule = rules.findLast((r) => match(permission, r.permission) && match(input, r.pattern));
  return rule?.action ?? "ask";
}

function expectAll(agent, permission, action, inputs) {
  for (const input of inputs) assert.equal(decide(agent, permission, input), action, `${agent} ${permission}: ${input}`);
}

const PRIMARY = ["orchestrator", "architect", "harness-builder", "instrumentation", "workspace-builder", "setup-improver"];
const HOME = homedir();

test("primary agents read freely", () => {
  for (const a of PRIMARY) {
    expectAll(a, "bash", "allow", [
      "ls -la",
      "cat internal/greet/greet.go",
      "git status --short",
      "git log --oneline -5",
      "git diff -- a.go",
      "rg -n Hello",
      "find . -name '*.go'",
      "IFS= read -r line",
      "go test ./...",
      "ls -la ~/specs/p/openspec/changes/x/reports/ 2>/dev/null",
      "git status --short 2>&1",
    ]);
  }
});

test("primary agents run writing and project commands without asking", () => {
  for (const a of PRIMARY) {
    expectAll(a, "bash", "allow", [
      "echo x > internal/a.go",
      "cat a >> b",
      "printf '%s' x >f",
      "sed -n -i s/a/b/ f",
      "sed -n 'w out' f",
      "awk '{print > \"f\"}' x",
      "xargs rm",
      "find . -delete",
      "find . -name x -exec rm {} ;",
      "sort -o out in",
      "tree -o out",
      "go build -o app ./...",
      "git diff --output=patch",
      "git branch -D main",
      "git -C . reset --hard",
      "git checkout -- a.go",
      "git checkout -b feature/x",
      "rm -rf x/bin/waves y",
      "rg --pre rm x",
      "openspec init .",
      "openspec validate --strict",
      "tee out",
      "make build",
      "curl -s localhost:3939/api/health",
      "docker compose up -d",
      "go mod tidy",
      "cat a > f 2>/dev/null",
      "ls > f 2>&1",
      "ls 2>/dev/null > f",
      "find . -delete 2>/dev/null",
      "rm -rf x 2>/dev/null",
    ]);
  }
});

test("secrets stay out of bash output", () => {
  for (const a of [...PRIMARY, "executor", "executor-strong", "task-reviewer", "explorer"]) {
    expectAll(a, "bash", "deny", ["env", "printenv", "printenv DEEPSEEK_API_KEY", "cat ~/.openviking/.env", "cat .env"]);
  }
  expectAll("orchestrator", "read", "deny", [`${HOME}/.openviking/.env`, "/w/.env.local"]);
  expectAll("orchestrator", "read", "allow", ["/w/.env.example", "/w/main.go"]);
});

test("the orchestrator and setup-improver commit without asking, never through git -C", () => {
  for (const a of ["architect", "harness-builder", "instrumentation", "workspace-builder", "executor", "executor-strong"]) {
    expectAll(a, "bash", "deny", ["git commit -m x", "git -C /w commit -m x", "git -c a=b commit", "git push", "git -C /w push"]);
  }
  expectAll("orchestrator", "bash", "allow", ["git commit -m x", "git -C /w commit -m x", "git -c a=b commit", "git push", "git -C /w push"]);
  expectAll("setup-improver", "bash", "allow", ["git add prompts/x.md", "git commit -m 'fix(x): y'"]);
  expectAll("setup-improver", "bash", "deny", ["git -C /w commit -m x", "git push"]);
});

test("flow scripts run without asking", () => {
  expectAll("orchestrator", "bash", "allow", [
    "~/.config/opencode/bin/waves ~/specs/p/openspec/changes/x",
    `${HOME}/.config/opencode/bin/change-state ~/specs/p x`,
    `${HOME}/.config/opencode/bin/change-todos ~/specs/p x`,
    "~/.config/opencode/bin/change-todos ~/specs/p x 2>&1",
    "~/.config/opencode/bin/change-todos ~/specs/p x 2>/dev/null",
    "~/.config/opencode/bin/check-commit-msg",
    "~/.config/opencode/bin/ov-sync p",
    "~/.config/opencode/bin/specs-commit p 'docs(x): add plan'",
    "~/.config/opencode/bin/specs-commit p 'docs(x): y' > ../w/a.go",
    "git add -- internal/a.go",
  ]);
  for (const a of ["architect", "harness-builder"]) {
    expectAll(a, "bash", "allow", ["~/.config/opencode/bin/specs-commit p 'docs(x): add adr'"]);
  }
  expectAll("setup-improver", "bash", "allow", ["~/.config/opencode/bin/ov-usage --days 7"]);
});

test("only the orchestrator keeps the todo list", () => {
  expectAll("orchestrator", "todowrite", "allow", ["*"]);
  for (const a of ["executor", "executor-strong", "task-reviewer"]) {
    expectAll(a, "todowrite", "deny", ["*"]);
  }
});

test("explorer may find and search in memory", () => {
  expectAll("explorer", "openviking_find", "allow", ["*"]);
  expectAll("explorer", "openviking_search", "allow", ["*"]);
});

test("edits stay in the specs tree outside the work repository", () => {
  expectAll("orchestrator", "edit", "allow", ["../../../specs/p/openspec/changes/x/tasks.md", "../specs/openspec/changes/x/briefs/1.1.md"]);
  expectAll("orchestrator", "edit", "deny", ["internal/specs/x.go", "specs/a.md", "main.go"]);
  expectAll("task-reviewer", "edit", "allow", ["../../specs/p/openspec/changes/x/reports/1.1.md"]);
  expectAll("task-reviewer", "edit", "deny", ["reports/x.md", "internal/reports/x.go", "../../specs/p/openspec/changes/x/tasks.md"]);
  expectAll("architect", "edit", "allow", ["../../specs/p/architecture/adr/0001.md"]);
  expectAll("architect", "edit", "deny", ["architecture/x.md", "docs/specs/p/architecture/x.md"]);
  expectAll("harness-builder", "edit", "deny", ["x.harness-probe-1", "specs/p/harness/x.md"]);
  expectAll("setup-improver", "edit", "allow", ["prompts/orchestrator.md"]);
  expectAll("setup-improver", "edit", "deny", ["../programming/w/main.go"]);
});

test("architect runs proofs of concept in Go, Python, Node, Rust and Zig", () => {
  expectAll("architect", "bash", "allow", [
    "go run ./poc",
    "python3 bench.py",
    "node bench.mjs",
    "cargo run --release",
    "cargo bench",
    "rustc main.rs",
    "zig build run",
    "zig run main.zig",
    "git worktree add poc/x main",
    "git worktree remove poc/x",
    "docker compose up -d",
    "cargo run > out.txt",
  ]);
});

test("default model and memory server do not depend on the shell environment", () => {
  assert.equal(cfg.model, "{file:./tiers/fast}");
  assert.equal(cfg.small_model, "{file:./tiers/fast}");
  assert.equal(cfg.mcp.openviking.oauth, false);
  assert.match(cfg.mcp.openviking.headers.Authorization, /^Bearer \{file:~\/\.openviking\/[a-z-]+\}$/);
});

test("reviewer and explorer run no writing commands", () => {
  expectAll("task-reviewer", "bash", "allow", ["git status --short -- a.go", "git diff -- a.go", "go test ./internal/x/"]);
  expectAll("task-reviewer", "bash", "deny", ["go test ./... > out", "git diff --output=x", "rm a"]);
  expectAll("explorer", "bash", "deny", ["rg --pre rm x", "git log > x"]);
});

test("web-researcher runs no commands and edits nothing", () => {
  expectAll("web-researcher", "bash", "deny", ["ls", "env", "printenv", "curl https://example.com", "git log --oneline -5"]);
  expectAll("web-researcher", "edit", "deny", ["research/notes.md", "internal/a.go"]);
  expectAll("web-researcher", "webfetch", "allow", ["*"]);
  expectAll("web-researcher", "websearch", "allow", ["*"]);
});
