#!/usr/bin/env bash
# Keeps project instrumentation in .agents/ and exposes it to OpenCode through .opencode symlinks.
set -euo pipefail
mkdir -p .agents/agents .agents/skills .agents/rules .opencode
# Every conflict is checked before anything moves, so a refusal leaves the repository untouched.
for kind in agents skills; do
  dest=.opencode/$kind
  if [[ -L $dest ]]; then
    target=$(readlink "$dest")
    if [[ $target != "../.agents/$kind" ]]; then
      echo "refusing: $dest is a symlink to $target, expected ../.agents/$kind" >&2
      exit 1
    fi
  elif [[ -d $dest ]]; then
    while IFS= read -r -d '' f; do
      if [[ -e .agents/$kind/${f#"$dest"/} || -L .agents/$kind/${f#"$dest"/} ]]; then
        echo "refusing: $f would overwrite .agents/$kind/${f#"$dest"/}" >&2
        exit 1
      fi
    done < <(find "$dest" -mindepth 1 ! -type d -print0)
  elif [[ -e $dest ]]; then
    echo "refusing: $dest exists and is not a directory or the expected symlink" >&2
    exit 1
  fi
done
for kind in agents skills; do
  dest=.opencode/$kind
  [[ -L $dest ]] && continue
  if [[ -d $dest ]]; then
    cp -R "$dest/." ".agents/$kind/" && rm -rf "$dest"
  fi
  ln -s "../.agents/$kind" "$dest"
done
echo "linked .opencode/agents and .opencode/skills to .agents"
