---
name: commit-message
description: Use when proposing or writing a git commit message
---
# Commit messages

## Format

One English line, no body, no trailers:

```
type(scope): subject
```

- `type` is one of: feat, fix, refactor, test, docs, chore, perf, build, ci.
- `scope` is lowercase kebab-case: the module, service or feature.
- `subject` starts lowercase, uses the imperative mood, at most 72 characters for the whole line.
- No `Co-Authored-By` or other trailers.

## Good

- `feat(clients): add passport expiry check`
- `fix(report-311): handle empty error count`
- `refactor(bff): extract routing table`

## Bad

- `Fixed the bug in reports` — no type or scope, past tense.
- `feat(clients): Add passport check` — capitalized subject.
- `fix(api): handle nil` followed by a paragraph — bodies are not allowed.

## Rules

- Propose commits; do not commit unless the user asks.
- One logical change per commit; list the files each proposed commit contains.
- Check a message with `~/.config/opencode/bin/check-commit-msg <file>` or by piping it to stdin.

## Per-repository hook

Install only into a specific repository and only when the user asks:

```bash
cp ~/.config/opencode/skills/commit-message/templates/commit-msg .git/hooks/commit-msg && chmod +x .git/hooks/commit-msg
```

Never set `core.hooksPath` globally.
