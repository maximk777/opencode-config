# Screen spec (free-form input)

Fill this template when the screen has no MAP row: it gives the `ui-designer` subagent the same
information a MAP row would, plus everything the artboard needs. One template per screen; keep the
label language consistent across fields — a Russian label means Russian interface text.

```markdown
Screen: <name, as it should appear in the manifest entry `screen` field>
Title: <visible page heading and document title>
Pattern: <page layout | filter form | data table | action modal | details modal | history modal>
Access: <who sees the screen, if known>

Fields / columns:
- <name>: <type, format, example value>
- ...

Transitions:
- <button or link caption> -> <target screen or artboard file name, or "none">

Sample data notes:
- <realistic rows the artboard must show; totals must match rows, counts must match lists>
```

Rules the subagent applies anyway, so keep the spec consistent with them:

- The title drives the document title and page heading.
- 5-10 rows of realistic, domain-fitting sample data; no lorem ipsum, no placeholder text in a
  foreign language.
- Transitions become plain links to existing or same-run artboards; never dead links.
