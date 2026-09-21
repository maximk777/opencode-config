# Status

The work queue of the workspace. `python3 tools/generate.py` rewrites the four sections below from the `status`, `owner`, `started` and `recorded` fields of every story and workspace task; only the text outside the `<!-- status:... -->` markers is hand-written.

## In progress
Who works on what right now, one group per owner.

<!-- status:in-progress:begin -->
<!-- status:in-progress:end -->

## Waiting
Tasks ready to be picked up, grouped by project and stream; `task-start` moves one into progress.

<!-- status:waiting:begin -->
<!-- status:waiting:end -->

## Done recently
Tasks whose work records were written in the last 30 days.

<!-- status:done-recently:begin -->
<!-- status:done-recently:end -->

## Drift
Repository resync candidates; empty until the resync seam is wired.

<!-- status:drift:begin -->
<!-- status:drift:end -->
