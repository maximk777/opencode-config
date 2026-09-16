# tailwind-daisyui cheat sheet

Composition recipes for legacy-parity mockups rendered with the vendored
Tailwind Play script (`vendor/tailwind-daisyui/4.12.24/vendor/tailwind.js`) and
the daisyUI full stylesheet. An artboard starts from `template.dc.html`; the
markup below goes into its `<main class="artboard">`. **This kit imitates the
legacy CRM look, not antd** — use it when a mockup must match the existing
support CRM screens; for new screen language use the antd kit.

The Play script compiles utility classes at runtime from the local file, so
mockups work fully offline once the kit is vendored. daisyUI component classes
(`btn`, `table`, `modal`, `timeline`, …) come precompiled from
`daisyui-full.min.css` with the `light` theme active — no `tailwind.config`
block is needed. Mute labels with the `opacity-60` utility — slash opacity
variants of daisy color tokens are JIT-only, and neither vendored asset can
resolve them, so they silently render at full opacity. Screens are static
renders with 5-10 rows of realistic sample data; cross-screen navigation is a
plain `<a href="Other.dc.html">`.

## FilterForm

Stacked `form-control` fields above the table: a labeled `input input-bordered`
per filter plus a `btn` row. `grid gap-4` with `md:grid-cols-*` keeps it compact
on wide artboards.

```html
<form class="card bg-base-100 p-4 grid gap-4 md:grid-cols-3">
  <label class="form-control">
    <span class="label-text mb-1">Subject</span>
    <input class="input input-bordered w-full" placeholder="subject or id">
  </label>
  <label class="form-control">
    <span class="label-text mb-1">Status</span>
    <select class="select select-bordered w-full">
      <option>open</option><option>closed</option>
    </select>
  </label>
  <div class="form-control justify-end">
    <button class="btn btn-primary">Search</button>
  </div>
</form>
```

## DataTable

`table table-zebra table-sm` inside a `card`; the id column wraps each row id
in a plain link to the details screen. Zebra stripes imitate the legacy grid.

```html
<div class="card bg-base-100">
  <table class="table table-zebra table-sm">
    <thead><tr><th>ID</th><th>Subject</th><th>Status</th><th>Updated</th></tr></thead>
    <tbody>
      <tr>
        <td><a class="link" href="Ticket.dc.html">TCK-101</a></td>
        <td>Login fails on mobile</td>
        <td><span class="badge badge-warning">open</span></td>
        <td>2026-09-14</td>
      </tr>
      <!-- one tr per row, 5-10 rows of realistic sample data -->
    </tbody>
  </table>
</div>
```

## ActionModal

A `dialog.modal` rendered open: `modal-open` (or the `open` attribute) shows it
for the static mockup. `modal-action` hosts the footer buttons; `btn-error`
marks destructive actions. Form fields follow the FilterForm pattern.

```html
<dialog class="modal modal-open">
  <div class="modal-box">
    <h3 class="font-bold text-lg">Close ticket TCK-101</h3>
    <label class="form-control my-4">
      <span class="label-text mb-1">Reason</span>
      <select class="select select-bordered w-full">
        <option>duplicate</option><option>resolved</option>
      </select>
    </label>
    <div class="modal-action">
      <a class="btn" href="Ticket.dc.html">Cancel</a>
      <button class="btn btn-error">Close ticket</button>
    </div>
  </div>
</dialog>
```

## DetailsModal

Read-only entity details: a `card` (inside a `modal-box` when it overlays) with
`grid grid-cols-2` label/value rows — labels muted with `opacity-60`; a plain
link doubles as the "Edit" jump.

```html
<div class="card bg-base-100">
  <div class="card-body">
    <h2 class="card-title">Ticket TCK-101</h2>
    <div class="grid grid-cols-2 gap-y-2 text-sm">
      <span class="opacity-60">ID</span>
      <span><a class="link" href="Ticket.dc.html">TCK-101</a></span>
      <span class="opacity-60">Status</span>
      <span><span class="badge badge-warning">open</span></span>
      <span class="opacity-60">Assignee</span><span>a.ivanov</span>
      <span class="opacity-60">Created</span><span>2026-09-14 10:32</span>
      <!-- one label/value span pair per field -->
    </div>
  </div>
</div>
```

## HistoryModal

Event log as a daisyUI `timeline`: `ul.timeline` with one `li` per event,
timestamp in `timeline-start` muted with `opacity-60`, payload in a
`timeline-box`. Wrap it in `modal-box` when the mockup shows it as a dialog.

```html
<div class="modal-box">
  <h3 class="font-bold text-lg">Ticket TCK-101 — history</h3>
  <ul class="timeline timeline-vertical mt-4">
    <li>
      <div class="timeline-start opacity-60">2026-09-14 11:00</div>
      <div class="timeline-middle">●</div>
      <div class="timeline-end timeline-box">Assigned to a.ivanov</div>
    </li>
    <li>
      <div class="timeline-start opacity-60">2026-09-14 10:45</div>
      <div class="timeline-middle">●</div>
      <div class="timeline-end timeline-box">Status changed new → open</div>
    </li>
  </ul>
</div>
```

## PageLayout

Shell for a screen: daisyUI `drawer` with the menu in `drawer-side`, a
`navbar bg-base-100` on top and `breadcrumbs` under it; content goes into
`drawer-content`.

```html
<div class="drawer">
  <input id="menu" class="drawer-toggle">
  <div class="drawer-content">
    <div class="navbar bg-base-100">
      <label for="menu" class="btn btn-ghost btn-square btn-sm">☰</label><span class="font-bold">Support CRM</span>
    </div>
    <div class="breadcrumbs px-4 pt-2 text-sm">
      <ul><li><a href="Home.dc.html">Support</a></li><li>Tickets</li></ul>
    </div>
  </div>
  <div class="drawer-side">
    <label for="menu" class="drawer-overlay"></label>
    <ul class="menu bg-base-100 w-56"><li><a href="Tickets.dc.html">Tickets</a></li><li><a href="Reports.dc.html">Reports</a></li></ul>
  </div>
</div>
```
