# setup-opencode

An [OpenCode](https://opencode.ai) configuration: a change-flow orchestrator, skills, plugins, bin scripts and a workspace kit for keeping agent setups reproducible.

## What is inside

- **Change flow** — skills and agents that drive a change from brainstorm through spec, plan and waves of executor tasks to review.
- **Skills** — specialized instructions the agents load on demand.
- **Plugins** — session hooks that keep state tidy between sessions.
- **bin scripts** — small utilities for syncing, linting and checking the setup.
- **Workspace kit** — templates and generators for spinning up team workspaces from a shared kit.

## Installation

Bootstrap a fresh macOS laptop in one command — installs missing deps (Homebrew, node, python, opencode; plus Docker Desktop and Ollama when memory is on), optionally creates a private OpenViking with its own keys, asks for the account name and provider tokens, installs the launch agents:

```sh
bin/bootstrap
```

Memory is optional: `bin/bootstrap --no-memory` (or `OV_MEMORY=no`) skips OpenViking entirely — no Docker Desktop, no Ollama, no launch agents, opencode just runs without memory. It also removes the `mcp.openviking` entry from `opencode.json` (a local git modification) and skips the Claude Code MCP registration, so nothing looks for OpenViking at startup; a rerun with memory restores the entry. On a fresh machine an interactive run also asks. A later plain rerun of `bin/bootstrap` adds the memory stack on top; `--no-memory` on a machine where memory was installed before acts as a repair — it unloads and deletes the `opencode.ov-studio`/`opencode.ov-syncd` launch agents and unregisters the Claude Code MCP, while the `~/.openviking` data is kept.

The OpenViking LLM token (DeepSeek) is optional: an empty answer runs OpenViking in lite mode — local embeddings only, no external LLM calls, no memory extraction and no nightly semantic summaries. Find, spec sync and writes keep working. A later key added to `~/.openviking/.env` plus a rerun of `bin/ov-up` restores full mode.

The pieces it runs, also usable on their own:

Link the skills, agents and rules into [Claude Code](https://claude.com/claude-code):

```sh
bin/claude-link
```

Install the launch agents that keep background syncs running:

```sh
bin/ov-up
```

## Running the tests

JavaScript (node) suite:

```sh
node --test tests/*.test.mjs
```

Python suite:

```sh
python3 -m unittest discover tests
```

## Publishing

Run `bin/check-public` before publishing anything: it scans every commit on every ref for marker words and secret patterns and must pass before publishing.

See docs/ARCHITECTURE.md for how the pieces fit together.

## License

[MIT](LICENSE)
