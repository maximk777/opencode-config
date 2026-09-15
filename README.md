# setup-opencode

An [OpenCode](https://opencode.ai) configuration: a change-flow orchestrator, skills, plugins, bin scripts and a workspace kit for keeping agent setups reproducible.

## What is inside

- **Change flow** — skills and agents that drive a change from brainstorm through spec, plan and waves of executor tasks to review.
- **Skills** — specialized instructions the agents load on demand.
- **Plugins** — session hooks that keep state tidy between sessions.
- **bin scripts** — small utilities for syncing, linting and checking the setup.
- **Workspace kit** — templates and generators for spinning up team workspaces from a shared kit.

## Installation

Bootstrap a fresh macOS laptop in one command — installs missing deps (Homebrew, node, python, Docker Desktop, Ollama, opencode), creates a private OpenViking with its own keys, asks for the account name and provider tokens, installs the launch agents:

```sh
bin/bootstrap
```

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
