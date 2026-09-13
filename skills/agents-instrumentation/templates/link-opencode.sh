#!/usr/bin/env bash
# Keeps project instrumentation in .agents/ and exposes it to OpenCode through .opencode symlinks.
set -euo pipefail
mkdir -p .agents/agents .agents/skills .agents/rules .opencode
for kind in agents skills; do
  if [[ -e .opencode/$kind && ! -L .opencode/$kind ]]; then
    cp -R .opencode/$kind/. .agents/$kind/ && rm -rf .opencode/$kind
  fi
  [[ -L .opencode/$kind ]] || ln -s ../.agents/$kind .opencode/$kind
done
echo "linked .opencode/agents and .opencode/skills to .agents"
