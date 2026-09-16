# plain-tokens cheat sheet

Composition recipes for mockups styled by `vendor/tokens.css`. All classes are
defined in the kit; an artboard starts from `template.dc.html` and the markup
below is composed inside `<section class="dd-content">` unless the recipe says
otherwise.

## PageLayout

Shell for a screen: sider navigation, breadcrumb, stacked content cards.
The base template already contains this skeleton — fill `data-screen`,
the sider links and the breadcrumb.

```html
<main class="artboard dd-page" data-screen="tickets-list">
  <aside class="dd-sider">
    <nav><a href="#">Tickets</a><a href="#">Reports</a></nav>
  </aside>
  <section class="dd-content">
    <nav class="dd-breadcrumb"><a href="#">Support</a> / Tickets</nav>
    <header class="dd-header"><h1>Tickets</h1><button class="dd-btn dd-btn--primary">New</button></header>
    <!-- compose cards per cheat-sheet sections below -->
  </section>
</main>
```

## FilterForm

`form.dd-card.dd-form` with `.dd-form-row` (label + field) rows; submit row is
`.dd-form-actions` with a primary submit button.

```html
<form class="dd-card dd-form">
  <div class="dd-form-row">
    <label for="f-status">Status</label>
    <select id="f-status" class="dd-select">
      <option>open</option><option>closed</option>
    </select>
  </div>
  <div class="dd-form-row">
    <label for="f-query">Search</label>
    <input id="f-query" class="dd-input" type="text" placeholder="subject or id">
  </div>
  <div class="dd-form-actions">
    <button type="reset" class="dd-btn">Reset</button>
    <button type="submit" class="dd-btn dd-btn--primary">Filter</button>
  </div>
</form>
```

## DataTable

`table.dd-table` with a semantic `thead`/`tbody`; rows highlight on hover
automatically. Wrap it in a `.dd-card` to give it a frame and title.

```html
<div class="dd-card">
  <h2>Tickets</h2>
  <table class="dd-table">
    <thead><tr><th>ID</th><th>Subject</th><th>Status</th><th>Updated</th></tr></thead>
    <tbody>
      <tr><td>TCK-101</td><td>Login fails on mobile</td><td>open</td><td>2026-09-14</td></tr>
      <tr><td>TCK-102</td><td>Export times out</td><td>closed</td><td>2026-09-12</td></tr>
    </tbody>
  </table>
</div>
```

## ActionModal

`.dd-modal` is the fixed overlay; `.dd-modal__panel` centers inside it. Put an
interactive form in the body and confirm/cancel buttons in the footer. Use the
danger modifier for destructive confirmations.

```html
<div class="dd-modal">
  <div class="dd-modal__panel">
    <header class="dd-modal__header">Close ticket <button class="dd-modal__close" aria-label="Close">×</button></header>
    <form class="dd-modal__body dd-form">
      <div class="dd-form-row">
        <label for="m-reason">Reason</label>
        <select id="m-reason" class="dd-select"><option>duplicate</option><option>resolved</option></select>
      </div>
      <div class="dd-form-row">
        <label for="m-note">Note</label>
        <textarea id="m-note" class="dd-textarea dd-input"></textarea>
      </div>
    </form>
    <footer class="dd-modal__footer">
      <button class="dd-btn">Cancel</button>
      <button class="dd-btn dd-btn--primary">Close ticket</button>
    </footer>
  </div>
</div>
```

## DetailsModal

Read-only entity details in the same modal chrome; body is a
`dl.dd-descriptions` key/value grid instead of a form.

```html
<div class="dd-modal">
  <div class="dd-modal__panel">
    <header class="dd-modal__header">Ticket TCK-101 <button class="dd-modal__close" aria-label="Close">×</button></header>
    <div class="dd-modal__body">
      <dl class="dd-descriptions">
        <dt>Subject</dt><dd>Login fails on mobile</dd>
        <dt>Status</dt><dd>open</dd>
        <dt>Assignee</dt><dd>a.ivanov</dd>
        <dt>Created</dt><dd>2026-09-14 10:32</dd>
      </dl>
    </div>
    <footer class="dd-modal__footer">
      <button class="dd-btn">Cancel</button>
      <button class="dd-btn dd-btn--primary">Edit</button>
    </footer>
  </div>
</div>
```

## HistoryModal

Read-only event log; body is a `ul.dd-timeline` where each `li` is one event
and `.dd-timeline__time` carries its timestamp.

```html
<div class="dd-modal">
  <div class="dd-modal__panel">
    <header class="dd-modal__header">Ticket TCK-101 — history <button class="dd-modal__close" aria-label="Close">×</button></header>
    <div class="dd-modal__body">
      <ul class="dd-timeline">
        <li>Assigned to a.ivanov <span class="dd-timeline__time">2026-09-14 11:00</span></li>
        <li>Status changed new → open <span class="dd-timeline__time">2026-09-14 10:45</span></li>
        <li>Ticket created <span class="dd-timeline__time">2026-09-14 10:32</span></li>
      </ul>
    </div>
    <footer class="dd-modal__footer">
      <button class="dd-btn dd-btn--danger">Delete</button>
      <button class="dd-btn">Close</button>
    </footer>
  </div>
</div>
```
