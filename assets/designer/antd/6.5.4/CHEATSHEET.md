# antd cheat sheet

Composition recipes for mockups rendered by the antd UMD bundle
(`vendor/antd/6.5.4/`). An artboard starts from `template.dc.html`; the samples
below go into its `App()` component. `const h = React.createElement;` at the top
of the script keeps the samples short — that is the constructor language the mfe
projects use (ADR-005), so a mockup translates to real screen code almost
line-for-line.

**Screens are static renders with 5-10 rows of realistic sample data** — no
fetching, no state beyond what a recipe needs to look alive. Cross-screen
navigation is a plain `<a href="Other.dc.html">` wrapped around a button or a
table cell (real links, not router calls).

## PageLayout

Shell for a screen: `Layout.Sider` navigation + `Header`/`Content`. antd has no
`PageHeader`; a `Card` with `title`/`extra` is the equivalent page head.

```js
h(antd.Layout, { style: { minHeight: "100vh" } },
  h(antd.Layout.Sider, { width: 200 },
    h(antd.Menu, { mode: "inline", defaultSelectedKeys: ["tickets"], items: [
      { key: "tickets", label: h("a", { href: "Tickets.dc.html" }, "Tickets") },
      { key: "reports", label: h("a", { href: "Reports.dc.html" }, "Reports") },
    ] })),
  h(antd.Layout, null,
    h(antd.Layout.Header, null,
      h(antd.Breadcrumb, { items: [
        { title: h("a", { href: "Home.dc.html" }, "Support") },
        { title: "Tickets" },
      ] })),
    h(antd.Layout.Content, { style: { padding: 24 } },
      h(antd.Card, { title: "Tickets", extra: h(antd.Button, { type: "primary" }, "New ticket") },
        // compose FilterForm / DataTable per sections below
        null))));
```

## FilterForm

`Form` + `Row`/`Col` grid of `Input`/`Select`/`DatePicker` and a search
`Button`. `layout="inline"` keeps it compact above the table.

```js
h(antd.Form, { layout: "inline", onFinish: () => {} },
  h(antd.Form.Item, { name: "query", label: "Subject" },
    h(antd.Input, { placeholder: "subject or id", allowClear: true })),
  h(antd.Form.Item, { name: "status", label: "Status", initialValue: "open" },
    h(antd.Select, { style: { width: 140 }, options: [
      { value: "open", label: "open" },
      { value: "closed", label: "closed" },
    ] })),
  h(antd.Form.Item, { name: "created", label: "Created" },
    h(antd.DatePicker, null)),
  h(antd.Form.Item, null,
    h(antd.Button, { type: "primary", htmlType: "submit" }, "Search")));
```

## DataTable

`Table` with `columns` (`title`/`dataIndex`/`render`) and `dataSource`; use its
built-in `pagination` (sample pages of 5) instead of a separate Pagination bar.
`render` wraps the row id in a plain link to the details screen.

```js
const tickets = [
  { id: "TCK-101", subject: "Login fails on mobile", status: "open", updated: "2026-09-14" },
  { id: "TCK-102", subject: "Export times out", status: "closed", updated: "2026-09-12" },
  // 5-10 rows of realistic sample data
];
h(antd.Table, {
  rowKey: "id",
  dataSource: tickets,
  pagination: { pageSize: 5 },
  columns: [
    { title: "ID", dataIndex: "id",
      render: (id) => h("a", { href: "Ticket.dc.html" }, id) },
    { title: "Subject", dataIndex: "subject" },
    { title: "Status", dataIndex: "status",
      render: (s) => h(antd.Tag, { color: s === "open" ? "gold" : "green" }, s) },
    { title: "Updated", dataIndex: "updated" },
  ] });
```

## ActionModal

`Modal` + `Form` with confirm semantics: `okText` names the action, `onOk`
validates the form, `okButtonProps: { danger: true }` marks destructive ones.
Render it open for the static mockup.

```js
const [form] = antd.Form.useForm();
h(antd.Modal, {
  open: true, title: "Close ticket TCK-101", okText: "Close ticket",
  onOk: () => form.validateFields().then(() => {}), okButtonProps: { danger: true },
}, [
  h(antd.Form, { form: form, layout: "vertical" }, [
    h(antd.Form.Item, { name: "reason", label: "Reason", initialValue: "resolved" },
      h(antd.Select, { options: [
        { value: "duplicate", label: "duplicate" },
        { value: "resolved", label: "resolved" },
      ] })),
    h(antd.Form.Item, { name: "note", label: "Note" },
      h(antd.Input.TextArea, { rows: 3, placeholder: "what happened" })),
  ])]);
```

## DetailsModal

Read-only entity details: `Modal` + `Descriptions` (one `Item` per field), a
plain link in the footer row if the mockup needs an "Edit" jump.

```js
h(antd.Modal, {
  open: true, title: "Ticket TCK-101", okText: "Edit", onOk: () => {},
}, [
  h(antd.Descriptions, { bordered: true, column: 1, size: "small" }, [
    h(antd.Descriptions.Item, { label: "ID" },
      h("a", { href: "Ticket.dc.html" }, "TCK-101")),
    h(antd.Descriptions.Item, { label: "Subject" }, "Login fails on mobile"),
    h(antd.Descriptions.Item, { label: "Status" }, h(antd.Tag, { color: "gold" }, "open")),
    h(antd.Descriptions.Item, { label: "Priority" }, h(antd.Tag, { color: "red" }, "high")),
    h(antd.Descriptions.Item, { label: "Assignee" }, "a.ivanov"),
    h(antd.Descriptions.Item, { label: "Created" }, "2026-09-14 10:32"),
    h(antd.Descriptions.Item, { label: "Updated" }, "2026-09-14 11:00"),
  ])]);
```

## HistoryModal

Event log in a modal: `Modal` + `Timeline` (preferred) or a two-column `Table`
when timestamps must align in a grid.

```js
h(antd.Modal, {
  open: true, title: "Ticket TCK-101 — history", footer: null, width: 560,
}, [
  h(antd.Timeline, { items: [
    { color: "blue", children: [
      "Assigned to a.ivanov ", h(antd.Typography.Text, { type: "secondary" }, "2026-09-14 11:00"),
    ] },
    { color: "green", children: [
      "Status changed new → open ", h(antd.Typography.Text, { type: "secondary" }, "2026-09-14 10:45"),
    ] },
    { children: [
      "Ticket created ", h(antd.Typography.Text, { type: "secondary" }, "2026-09-14 10:32"),
    ] },
  ] })]);
```
