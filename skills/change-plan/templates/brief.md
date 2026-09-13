---
task: <N>
files: <comma-separated paths>
depends: <comma-separated task numbers or empty>
skeleton: <yes|no>
---
# Task <N>: <title>

## Requirement
<requirement name and full text, with its scenarios>

## Do
<numbered steps; include the code skeleton when skeleton: yes>

## Verify
Command: <exact command>
Expected output contains: <markers>

## Constraints
- Touch only the files listed above.
- Do not commit.
- Comment only non-obvious decisions.
- Write the report to <report path> from the report template.
