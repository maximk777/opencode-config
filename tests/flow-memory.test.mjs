import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;
const TEMPLATE = 'Memory: query="<query>" hits=<N> used=yes|no rederived=<ADR or map path|none>';
const ALLOWED = new Set([
  "skills/change-spec/SKILL.md", "skills/change-plan/SKILL.md", "skills/change-execute/SKILL.md",
  "skills/architecture-docs/SKILL.md", "skills/architecture-poc/SKILL.md", "skills/harness-assessment/SKILL.md",
  "prompts/orchestrator.md", "prompts/architect.md",
]);
const FORBIDDEN = [/after (each|every) commit/i, /edit files, then run/i, /Commit the specs repository and run/];
// Catches both the full binary path and a bare mention of the command, so a
// gate reference cannot slip past the scan by dropping the "bin/" prefix.
const OV_SYNC_MENTION = /bin\/ov-sync|ov-sync <project>/;
const NUMBERED_LIST_LINE = /^\s*\d+\.\s/;
const GATE_PHRASES = [
  "After approval",
  "After an accepted",
  "When a wave is accepted",
  "After the user accepts",
  "only at gates",
];
// "Run ~/.config/opencode/bin/ov-sync <project>." is only a gate marker inside
// change-execute's numbered Finish list; elsewhere it would be an unqualified sync.
const FINISH_LIST_MARKER = "Run ~/.config/opencode/bin/ov-sync <project>.";

function isGateLine(line) {
  if (GATE_PHRASES.some((phrase) => line.includes(phrase))) return true;
  return NUMBERED_LIST_LINE.test(line) && line.includes(FINISH_LIST_MARKER);
}

function flowFiles() {
  // skills/*/SKILL.md, prompts/*.md and commands/*.md as repository-relative paths
  const files = [];
  for (const name of readdirSync(join(ROOT, "skills"))) {
    const rel = join("skills", name, "SKILL.md");
    if (existsSync(join(ROOT, rel))) files.push(rel);
  }
  for (const name of readdirSync(join(ROOT, "prompts"))) {
    if (name.endsWith(".md")) files.push(join("prompts", name));
  }
  const commandsDir = join(ROOT, "commands");
  if (existsSync(commandsDir)) {
    for (const name of readdirSync(commandsDir)) {
      if (name.endsWith(".md")) files.push(join("commands", name));
    }
  }
  return files;
}

function readRel(rel) {
  return readFileSync(join(ROOT, rel), "utf8");
}

test("ov-sync is mentioned only in gate files", () => {
  for (const rel of flowFiles()) {
    const lines = readRel(rel).split("\n");
    lines.forEach((line, i) => {
      if (!OV_SYNC_MENTION.test(line)) return;
      assert.ok(ALLOWED.has(rel), `${rel}:${i + 1} mentions ov-sync but is not an allowed gate file: ${line}`);
    });
  }
});

test("no sync after a commit or an edit", () => {
  for (const rel of flowFiles()) {
    const lines = readRel(rel).split("\n");
    lines.forEach((line, i) => {
      for (const re of FORBIDDEN) {
        assert.ok(!re.test(line), `${rel}:${i + 1} matches forbidden pattern ${re}: ${line}`);
      }
    });
  }
});

test("every ov-sync line is a gate line", () => {
  for (const rel of flowFiles()) {
    const lines = readRel(rel).split("\n");
    lines.forEach((line, i) => {
      if (!OV_SYNC_MENTION.test(line)) return;
      assert.ok(isGateLine(line), `${rel}:${i + 1} ov-sync line missing a gate phrase: ${line}`);
    });
  }
});

test("change-execute syncs at the end of each wave", () => {
  const text = readRel("skills/change-execute/SKILL.md");
  assert.ok(
    text.includes("When a wave is accepted, run ~/.config/opencode/bin/ov-sync <project>"),
    "change-execute/SKILL.md is missing the end-of-wave sync step",
  );
});

test("gate wording is required, not merely allowed", () => {
  for (const rel of ["prompts/orchestrator.md", "prompts/architect.md"]) {
    assert.ok(
      readRel(rel).includes("bin/ov-sync <project> only at gates"),
      `${rel} is missing the required "bin/ov-sync <project> only at gates" wording`,
    );
  }

  const changeExecute = readRel("skills/change-execute/SKILL.md");
  assert.ok(
    changeExecute.includes("When a wave is accepted, run ~/.config/opencode/bin/ov-sync <project>"),
    "skills/change-execute/SKILL.md is missing the wave gate step",
  );

  const lines = changeExecute.split("\n");
  const archiveIdx = lines.findIndex((line) => line.includes("docs(<slug>): archive change"));
  assert.ok(archiveIdx !== -1, "skills/change-execute/SKILL.md is missing the archive commit step in Finish");
  const syncAfterArchiveIdx = lines.findIndex(
    (line, i) => i > archiveIdx && NUMBERED_LIST_LINE.test(line) && line.includes(FINISH_LIST_MARKER),
  );
  assert.ok(
    syncAfterArchiveIdx !== -1,
    `skills/change-execute/SKILL.md:${archiveIdx + 1} archive commit step is not followed by a Finish-list "${FINISH_LIST_MARKER}" step`,
  );

  for (const rel of ["skills/change-spec/SKILL.md", "skills/change-plan/SKILL.md"]) {
    assert.ok(
      readRel(rel).includes("bin/ov-sync <project>"),
      `${rel} is missing a gate line with "bin/ov-sync <project>"`,
    );
  }
});

test("sessions start with a memory read and commit their log", () => {
  const brainstorm = readRel("skills/change-brainstorm/SKILL.md");
  const archDocs = readRel("skills/architecture-docs/SKILL.md");

  const FIND_OR_SEARCH = /`?find`? or `?search`?/;
  for (const [rel, text] of [
    ["skills/architecture-docs/SKILL.md", archDocs],
    ["skills/change-brainstorm/SKILL.md", brainstorm],
  ]) {
    assert.ok(FIND_OR_SEARCH.test(text), `${rel} is missing "find or search" (with or without backticks)`);
  }

  assert.ok(
    archDocs.includes("docs(architecture): record <topic> decisions"),
    'skills/architecture-docs/SKILL.md is missing "docs(architecture): record <topic> decisions"',
  );
  assert.ok(
    archDocs.includes("architecture/sessions/<YYYY-MM-DD>-<topic>.md"),
    'skills/architecture-docs/SKILL.md is missing "architecture/sessions/<YYYY-MM-DD>-<topic>.md"',
  );

  assert.ok(
    brainstorm.includes("decisions.md as soon as it is given"),
    'skills/change-brainstorm/SKILL.md is missing "decisions.md as soon as it is given"',
  );
  assert.ok(
    brainstorm.includes("commit it at once"),
    'skills/change-brainstorm/SKILL.md is missing "commit it at once"',
  );

  for (const [rel, text] of [
    ["skills/change-brainstorm/SKILL.md", brainstorm],
    ["skills/architecture-docs/SKILL.md", archDocs],
  ]) {
    assert.ok(text.includes("Rederived: <ADR or map path>"), `${rel} is missing "Rederived: <ADR or map path>"`);
    assert.ok(text.includes("never edit the Memory line"), `${rel} is missing "never edit the Memory line"`);
  }
});

test("memory template is shared", () => {
  for (const rel of ["skills/change-brainstorm/SKILL.md", "skills/architecture-docs/SKILL.md", "prompts/architect.md"]) {
    assert.ok(readRel(rel).includes(TEMPLATE), `${rel} is missing the shared memory template`);
  }

  const explorer = readRel("prompts/explorer.md");
  assert.ok(
    explorer.includes('Memory: query="<query>" hits=<N> used=yes|no rederived=none'),
    "prompts/explorer.md is missing its memory line",
  );

  const outputIdx = explorer.indexOf("Output format:");
  assert.ok(outputIdx !== -1, 'prompts/explorer.md is missing an "Output format:" section');
  const section = explorer.slice(outputIdx);
  const zeroMatch = section.match(/^0\.\s*Memory:/m);
  const oneMatch = section.match(/^1\.\s/m);
  assert.ok(zeroMatch, 'prompts/explorer.md "Output format:" list is missing item 0 with the Memory line');
  assert.ok(oneMatch, 'prompts/explorer.md "Output format:" list is missing item 1');
  assert.ok(
    zeroMatch.index < oneMatch.index,
    'prompts/explorer.md: "Output format:" item 0 (Memory) must come before item 1',
  );
});
