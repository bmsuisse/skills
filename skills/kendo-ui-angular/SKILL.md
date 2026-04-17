---
name: kendo-ui-angular
description: Use this skill whenever the user is working with Kendo UI for Angular — including the Data Grid, TreeList, TreeView, DropDownList, AutoComplete, or any @progress/kendo-angular-* package. Covers server-side paging/filtering/sorting, inline CRUD editing, row selection, custom cell templates, master-detail rows, grouping, Excel export, and virtualization for large datasets. Trigger on any mention of kendo grid, kendo treelist, kendo treeview, telerik angular, @progress/kendo-angular-grid, or when the user is building a sortable/filterable/pageable data table in Angular. Also trigger when a user asks about adding editing, export, tree navigation, or dropdown filtering to an existing Kendo Angular component.
---

# Kendo UI for Angular — Development Guidelines

## Setup & Installation

All packages are installed via the Angular schematics command, which handles dependencies and theme registration automatically:

```bash
ng add @progress/kendo-angular-grid
ng add @progress/kendo-angular-treelist
ng add @progress/kendo-angular-treeview
ng add @progress/kendo-angular-dropdowns
```

### Standalone vs. NgModule

Modern Angular (15+) uses standalone components. All Kendo packages expose a barrel token (e.g. `KENDO_GRID`) that replaces the module import:

| Approach | Import |
|---|---|
| **Standalone (preferred)** | `imports: [KENDO_GRID]` in `@Component` |
| NgModule | `GridModule` in `@NgModule` |

---

## Architecture Decisions

### Client-Side vs. Server-Side Operations

- **Client-side** (< ~5,000 rows): use the `process()` function from `@progress/kendo-data-query`. Pass your raw array + the current state and bind the result as `GridDataResult`.
- **Server-side** (large datasets): handle `(dataStateChange)`, send the state to your API, and bind the returned `{ data: T[], total: number }`. RxJS `switchMap` is the cleanest pattern to avoid race conditions.

### Change Detection

Kendo components work with both `Default` and `OnPush` change detection. With `OnPush`:
- Pass data as `Observable` (use `async` pipe) — preferred
- Or manually call `cdr.markForCheck()` after mutating bound data

### Forms Integration

All input/dropdown components support both template-driven (`ngModel`) and reactive (`formControl`) forms natively — no wrapper needed.

---

## Component Overview

| Component | Package | Use when |
|---|---|---|
| `kendo-grid` | `@progress/kendo-angular-grid` | Flat tabular data with sort/filter/page/edit |
| `kendo-treelist` | `@progress/kendo-angular-treelist` | Hierarchical data in a table layout (org charts, file trees with columns) |
| `kendo-treeview` | `@progress/kendo-angular-treeview` | Navigation tree / sidebar menu / selection tree |
| `kendo-dropdownlist` | `@progress/kendo-angular-dropdowns` | Pick from a fixed list — no free-text entry |
| `kendo-autocomplete` | `@progress/kendo-angular-dropdowns` | Free-text input with suggestion list |

---

## Grid — Key API

```
kendo-grid Inputs (most commonly used)
────────────────────────────────────────────────────────
[data]               T[] | GridDataResult      Bound data (page-slice for server-side)
[pageSize]           number                    Page size
[skip]               number                    Current page offset (0-based)
[pageable]           boolean | PagerSettings   Enable pager
[sortable]           boolean | SortSettings    Enable sorting
[filterable]         boolean | FilterSettings  Enable filter row or menu
[groupable]          boolean | GroupSettings   Enable grouping drag-and-drop
[selectable]         boolean | SelectSettings  Enable row selection
[loading]            boolean                   Show loading overlay
[sort]               SortDescriptor[]          Current sort state (bind for controlled sort)
[filter]             CompositeFilterDescriptor Current filter state
[group]              GroupDescriptor[]         Current group state
[rowHeight]          number                    Required for virtual scrolling
[height]             number                    Container height in px (virtual scrolling)
[rowClass]           (row) => string           Dynamic CSS class per row

kendo-grid Outputs
────────────────────────────────────────────────────────
(dataStateChange)    Combined: sort+filter+page+group changed — use for server-side
(pageChange)         Page changed (use instead of dataStateChange for paging-only)
(sortChange)         Sort changed
(filterChange)       Filter changed
(groupChange)        Group changed
(selectionChange)    Row selection changed
(add)                Add new row triggered
(edit)               Row enters edit mode
(save)               Row saved
(cancel)             Edit canceled
(remove)             Row removed
(detailExpand)       Detail row expanded
(detailCollapse)     Detail row collapsed
(excelExport)        Excel export triggered

Column directives
────────────────────────────────────────────────────────
kendo-grid-column          Standard column (field, title, width, format, filter, editable, etc.)
kendo-grid-checkbox-column Checkbox selection column
kendo-grid-command-column  Buttons: edit/save/cancel/remove via built-in commands
kendo-grid-toolbar         Toolbar slot (add buttons, search)
```

See `references/grid-samples.md` for complete code samples:
1. Client-side sort/filter/page with `process()`
2. Server-side paging, filtering & sorting with RxJS
3. Inline row editing (Add / Edit / Save / Cancel / Delete)
4. Row selection — single-click, multi-checkbox + bulk actions, programmatic, cross-page persistence, drag-to-select
5. Custom cell template (status badge)
6. Master-detail expandable rows
7. Excel export
8. Virtual scrolling for large datasets

---

## TreeList — Key API

TreeList renders hierarchical data as an expandable table — each row can have child rows, shown with an expand arrow. Unlike TreeView, it supports the full column / sort / filter / edit feature set.

```
kendo-treelist Inputs
────────────────────────────────────────────────────────
[kendoTreeListFlatBinding]      directive   Flat array data binding (use idField + parentIdField)
[kendoTreeListHierarchyBinding] directive   Nested object data binding (use childrenField)
[idField]            string                 Unique id field (flat binding)
[parentIdField]      string                 Parent reference field (flat binding)
[childrenField]      string                 Child array field (hierarchy binding)
[fetchChildren]      (node) => Observable   Load children on demand (async tree)
[hasChildren]        (node) => boolean      Whether a node is expandable
[isExpanded]         (node) => boolean      Whether a node is expanded by default
[pageSize]           number                 Page size
[pageable]           boolean | PagerSettings
[sortable]           boolean | SortSettings
[filterable]         boolean | FilterSettings
[selectable]         boolean | SelectSettings
[loading]            boolean

kendo-treelist Outputs
────────────────────────────────────────────────────────
(expand)             Node expanded
(collapse)           Node collapsed
(dataStateChange)    State changed (sort/filter/page)
(selectionChange)    Selection changed
(add) (edit) (save) (cancel) (remove)   CRUD events (same pattern as Grid)
```

See `references/treelist-treeview-samples.md` for:
1. Flat-data binding with idField / parentIdField
2. Hierarchical (nested) data binding
3. On-demand async children loading
4. Inline editing in TreeList

---

## TreeView — Key API

TreeView is a navigation component — a collapsible tree with optional checkboxes. It does not have columns, sorting, or pagination.

```
kendo-treeview Inputs
────────────────────────────────────────────────────────
[kendoTreeViewHierarchyBinding] directive   Nested data (use textField + childrenField)
[kendoTreeViewFlatDataBinding]  directive   Flat data (use idField + parentIdField)
[nodes]              any[]                  Root-level items (used without a binding directive)
[textField]          string | string[]      Field(s) to display as node text
[children]           (item) => Observable   Function returning child nodes
[hasChildren]        (item) => boolean      Whether a node has children
[isExpanded]         (item, index) => bool  Control expansion state
[isSelected]         (item, index) => bool  Control selection state
[isChecked]          (item, index) => CheckedState   Checkbox state
[loadOnDemand]       boolean                Load children only when parent expands
[filterable]         boolean                Show a filter input
[filter]             string                 Current filter value (controlled)
[navigable]          boolean                Enable keyboard navigation
[animate]            boolean                Expand/collapse animation (default: true)

kendo-treeview Outputs
────────────────────────────────────────────────────────
(nodeClick)          Node clicked
(expand)             Node expanded — use to update your isExpanded state
(collapse)           Node collapsed
(selectionChange)    Selection changed
(checkedChange)      Checkbox state changed
(filterChange)       Filter text changed
```

See `references/treelist-treeview-samples.md` for:
1. Hierarchical binding with expand/collapse state
2. Flat data binding
3. Load-on-demand (async children via Observable)
4. Checkboxes with tri-state parent nodes
5. Filterable tree

---

## DropDownList & AutoComplete — Quick Reference

Choose based on whether the user can enter free text:

| Component | Package token | Use when |
|---|---|---|
| `kendo-dropdownlist` | `KENDO_DROPDOWNLIST` | Must pick from a list; free-text not allowed |
| `kendo-autocomplete` | `KENDO_AUTOCOMPLETE` | Free text with suggestions; bound value stays a string |
| `kendo-combobox` | `KENDO_COMBOBOX` | Either: pick from list OR enter custom text |

**Shared best practices:**
- Enable `[filterable]="true"` + `(filterChange)` for large lists — never push 10k items to the client
- Set a minimum filter length guard (`if (filter.length < 2) return`) to avoid server calls on every keystroke
- Use `[loading]="isLoading"` while async calls are in flight

See `references/dropdown-samples.md` for complete samples covering DropDownList and AutoComplete.

---

## General Principles

- **Always set `field` on grid columns** even when using a custom cell template — sorting, filtering, and export depend on it.
- **Normalize data before binding**: compute derived fields (e.g. `fullName`) before binding to the grid instead of combining fields in a template, which breaks sort/filter.
- **Manage `[loading]`**: always set it `true` while async calls are in-flight to prevent users from interacting with stale data.
- **Z-index for dialogs**: if you wrap a Kendo component inside a modal/overlay, ensure `overflow: visible` on the modal and set a higher z-index for Kendo popups so filter menus and dropdowns are not clipped.
- **Production builds**: Kendo dev builds add diagnostics that slow rendering — always benchmark against a `ng build --configuration production` output.
