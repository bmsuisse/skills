---
name: bmsui
plugin: coding
description: >
  Pick the right shared component from `@bmsuisse/ui` / `@bmsuisse/datagrid`
  before writing a local one: dialogs, forms, dates, search/filters, tables,
  toasts, empty/error/loading states. Use for any React UI work in a BMS app.
---

# bmsui: use the shared components first

`@bmsuisse/ui` (primitives + composed patterns + hooks) and `@bmsuisse/datagrid`
(`DataGrid`, `TreeDataGrid`) are the shared libraries for BMS React apps. Check
them before building a local component. For colors, icons, sidebar and layout
see `bms-frontend-design`.

## 1. Read the catalog

`CATALOG.md` lists every export with when to use it. Get it from:

- the project: `node_modules/@bmsuisse/ui/CATALOG.md`
- no `node_modules` (e.g. you're running in OneHub): `https://cdn.jsdelivr.net/npm/@bmsuisse/ui/CATALOG.md`
- the source of truth: `packages/ui/CATALOG.md` in https://github.com/bmsuisse/bmsui

Find your need there, then import from `@bmsuisse/ui`. Exact props: the
published `api-report.md` (same repo, `packages/ui/api-report.md`), or the
Storybook at https://bmsuisse.github.io/bmsui/storybook/ once deployed.

## 2. Defaults that save rework

- Fetched data: `AsyncBoundary` (+ `ErrorState`, `LoadingState`); pass `hasData` so refetches keep content.
- Forms: `FormField` around every control; `FormModal` / `ConfirmDialog` / `ResponsivePanel` instead of raw `Dialog`.
- Dates and numbers: `DateInput` / `DatePicker` / `DateRangePicker` / `NumberInput`, never `<input type="date">`.
- Notices: `toast(...)` plus one `<Toaster />`. Empty states: `EmptyState` / `FilteredEmptyState`.
- Search UIs: `SearchBar` (with its `actions` slot), `FacetFilter` for sidebar facets, `FilterSheet` on phones, `ResultList` + `ResultCard` for hits, `ScoreBadge` for match scores.
- Tables with sort/filter/paging/grouping/editing/trees: `@bmsuisse/datagrid`, not `Table`.

## 3. Rules

- Strings: components take English defaults and a `labels` prop. Pass the app's translations; never fork a component to translate it.
- If the app has a local copy of a catalog component, migrate call sites when you touch them and delete the copy once unused.
- Nothing fits and it's generic? Build it locally and say it's a candidate for bmsui. Don't copy a library component into the app to change it; open an issue or PR in bmsui.
