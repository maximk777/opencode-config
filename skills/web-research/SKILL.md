# Skill: web-research

# Research the live web with citations

Use when the question needs information beyond the repository and memory: finding or comparing tools, libraries and APIs, checking versions, licenses and deprecations, or verifying how others solved a problem. Triggers on "research", "find a tool", "what's the best <lib>", "check the latest version".

## Method

1. Restate the question as one sentence and name the decision it serves.
2. Plan 3 to 5 diverse queries. English queries give better technical coverage; add the current year for freshness-sensitive topics.
3. Search, then pick sources by credibility: official docs, source code, changelogs and release pages first; vendor blogs next; SEO farms and content mills never.
4. Fetch the promising pages and skim them; quote at most a few lines, never whole pages.
5. Cross-check every key claim across at least two independent sources; report disagreements instead of resolving them silently.
6. Record the date or version each claim holds for.

## Delegation

- Multi-query research goes to the web-researcher subagent; hand it the question and the decision it serves, and expect the cited format from its prompt.
- A single quick lookup may run in place with websearch and webfetch.

## Output

Answer first. Then findings as one line per claim: `claim — <URL> (date or version)`. Then disagreements and gaps.

## Keeping findings

When the research settles a recurring reference (a tool choice, a version constraint, a link worth re-reading), save it with openviking_remember as one line: the decision, the source URL and the date.
