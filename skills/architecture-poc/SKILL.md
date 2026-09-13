---
name: architecture-poc
description: Use when an architecture hypothesis such as a data model, replication approach or performance claim must be proven with a measured proof of concept
---
# Proof of concept

Check an idea with code and numbers instead of arguing about it.

## When

Run a PoC only when the hypothesis can be checked with numbers and the user agreed to check it.
Examples: a table layout for a new database against a latency target; a streaming replication tool against a throughput target.

## Steps

1. Write poc/<slug>/README.md with the hypothesis and success criterion before the first run. Use ../architecture-docs/templates/poc-readme.md.
2. Write the PoC code in ~/specs/<project>/architecture/poc/<slug>/: schema, seed data, benchmark, prototype. Keep it small and disposable.
3. Run locally only: docker compose or testcontainers.
4. When work repository code is needed, use a temporary git worktree and remove it afterwards.
5. Never target stage or production without the user's explicit permission in this session.
6. Repeat each measurement at least three times; keep raw numbers, not only averages.
7. Write poc/<slug>/RESULT.md from templates/poc-result.md with raw numbers and a verdict.
8. Link RESULT.md from the ADR that relies on it.
9. Commit the specs repository and run ~/.config/opencode/bin/ov-sync <project>.

## After the verdict

Never copy PoC code into a product repository; write a candidate card instead.
If the result is inconclusive, say which measurement would decide it and ask the user whether to run it.
