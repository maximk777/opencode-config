---
name: sd-scheduler
description: Use when the user asks to fill, extend, edit or check the Service Desk duty schedule (sd.wb.ru scheduler / Планировщик) — e.g. "проставь расписание", "заполни график до конца месяца", "проставь смены 10-10". Automates shifts through the sd.wb.ru gateway API from the open browser page.
---

# Service Desk scheduler automation

Manage duty shifts in the SD scheduler (https://sd.wb.ru) through its internal gateway API, executed from the already-authenticated browser page via the `chrome-devtools` MCP tools. Do not call the API from the shell — auth lives in browser session cookies.

## Prerequisites

1. The scheduler page must be open in Chrome: `https://sd.wb.ru/admin/ns/<NS>/scheduler/main` (e.g. NS = `BANK`). Find it with `list_pages`; if missing, open it with `new_page`.
2. All API calls run inside `evaluate_script` with `credentials: "include"` on that page.
3. Never print cookies or tokens captured from network requests.

## Discover the scheduler id

`namespaceId` is a UUID, not the namespace code. Get it from the page network log: find any request matching `/api/gateway/scheduler/<uuid>` in `list_network_requests` (reload the page first if the log is empty). For the BANK namespace it is currently `4b8265f5-8f07-4c6d-94ad-9cde0dd49991`, but always discover it dynamically.

## API endpoints

All relative to `https://sd.wb.ru`, `content-type: application/json;charset=utf-8`.

- **Shift types**: `GET /api/gateway/scheduler/{namespaceId}/shift`
  → `{data: [{id, name, interval: {from, to}, type: "active"|"inactive", color}]}`.
  Pick the type by its `name` (e.g. `"10:00 - 09:59"`), not by hard-coded id.
- **Load schedule**: `POST /api/gateway/scheduler/{namespaceId}`
  body: `{"active":false,"interval":{"from":"YYYY-MM-DD","to":"YYYY-MM-DD"},"search":"","sortDir":"asc","team":[]}`
  → `{data: [{user: {id, login, lastName, firstName}, workShift: [{day: "YYYY-MM-DD", shift: {...}}]}]}`.
  Returns the whole namespace (~300 users) regardless of UI filters — filter by `login` client-side.
- **Create shifts**: `POST /api/gateway/scheduler/{namespaceId}/work-shift`
  body is an **array**: `[{"day":"YYYY-MM-DD","shiftId":"<uuid>","userId":"<uuid>"}]` — batchable.
- **Delete shifts**: `DELETE /api/gateway/scheduler/{namespaceId}/work-shift`, same array body.

## Execution rules

1. **One shot**: do the whole read → compute → write → verify cycle in a single `evaluate_script` call. The SPA can reload and destroy the execution context between calls.
2. **Idempotent**: read current `workShift` first and create only missing days. Never blind-POST; re-running must not duplicate shifts.
3. **Verify**: after writing, re-load the schedule and check every day in the requested range has the expected coverage. Report gaps or overlaps explicitly.
4. Reload the page and take a screenshot at the end so the user sees the result.

## Rotation pattern

When asked to "continue" a schedule, infer the pattern from existing shifts instead of asking:

1. Take the specialists that already have shifts in the month.
2. Order them by the day of their first shift — that is the rotation order.
3. Continue round-robin (period = number of specialists) with the same shift type to the end of the range.
4. If existing shifts are contradictory or ambiguous, ask the user one concrete question.

## Template

```js
async () => {
  const NS = "<namespaceId>";
  const load = async () => (await (await fetch(`/api/gateway/scheduler/${NS}`, {
    method: "POST", credentials: "include",
    headers: { "content-type": "application/json;charset=utf-8" },
    body: JSON.stringify({ active: false, interval: { from: FROM, to: TO }, search: "", sortDir: "asc", team: [] })
  })).json()).data || [];

  const types = (await (await fetch(`/api/gateway/scheduler/${NS}/shift`, { credentials: "include" })).json()).data;
  const shiftId = types.find(t => t.name === "10:00 - 09:59").id;

  const data = await load();
  const byLogin = Object.fromEntries(LOGINS.map(login => {
    const u = data.find(x => x.user.login === login);
    return [login, { id: u.user.id, days: new Set(u.workShift.map(w => w.day)) }];
  }));

  const toAdd = [];
  for (let d = 1; d <= DAYS_IN_MONTH; d++) {
    const login = LOGINS[(d - 1) % LOGINS.length];
    const day = `2026-11-${String(d).padStart(2, "0")}`;
    if (!byLogin[login].days.has(day)) toAdd.push({ day, shiftId, userId: byLogin[login].id });
  }
  if (toAdd.length) {
    const r = await fetch(`/api/gateway/scheduler/${NS}/work-shift`, {
      method: "POST", credentials: "include",
      headers: { "content-type": "application/json;charset=utf-8" },
      body: JSON.stringify(toAdd)
    });
    if (!r.ok) return { error: r.status, body: (await r.text()).slice(0, 300) };
  }

  const after = await load();
  // verify: every day in range covered exactly once by the rotation logins
  const count = {};
  for (const login of LOGINS) {
    for (const w of after.find(x => x.user.login === login).workShift) count[w.day] = (count[w.day] || 0) + 1;
  }
  const gaps = [];
  for (let d = 1; d <= DAYS_IN_MONTH; d++) {
    const day = `2026-11-${String(d).padStart(2, "0")}`;
    if (count[day] !== 1) gaps.push(`${day}: ${count[day] || 0}`);
  }
  return { added: toAdd.length, gaps };
}
```
