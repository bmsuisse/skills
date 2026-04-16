---
name: kendo-ui-vue
description: Use this skill whenever the user is working with Kendo UI for Vue — including the Data Grid, DropDownList, ComboBox, AutoComplete, or any @progress/kendo-vue-* package. Covers server-side paging/filtering/sorting, inline CRUD editing, row selection, custom cell templates, master-detail rows, grouping, Excel export, and virtualization for large datasets. Trigger on any mention of kendo grid, telerik vue, @progress/kendo-vue-grid, or when the user is building a sortable/filterable/pageable data table in Vue. Also trigger when a user asks about adding editing, export, or selection to an existing Kendo grid.
---

# Kendo UI for Vue — Development Guidelines

## Architecture Decisions

### Native Grid vs. Wrapper Grid
There are two Grid packages — use the **Native Grid** for all new work:

| Package | Import | When to use |
|---|---|---|
| `@progress/kendo-vue-grid` | `import { Grid } from '@progress/kendo-vue-grid'` | **New code** — Vue 3 Composition API, full TypeScript, all modern features |
| `@progress/kendo-vue-grid` (wrapper) | `import { Grid } from '@progress/kendo-vue-grid/dist/esm/main'` | Legacy wrapper — avoid |

The wrapper API uses `<kendo-grid>` and DataSource; the **Native Grid** uses `:data-items` and event-driven state. All samples below use the Native Grid.

### Client-Side vs. Server-Side Operations

- **Client-side** (< ~5,000 rows): use the `process()` function from `@progress/kendo-data-query`. Pass your raw array + the current `DataState` and bind the result directly.
- **Server-side** (large datasets or slow data): handle `@datastatechange`, send the state to your API, and bind the returned `{ data: T[], total: number }` to the grid. Set `:total` to the server-reported count so the pager is accurate.

## General Principles

- **Production builds only**: dev builds add heavy diagnostics that dramatically slow rendering. Always test grid performance against a `vite build` / `vue-cli-service build --mode production` output.
- **Server ops for large data**: push sort, filter, page, and group operations to the server. Never send 50k rows to the client and filter client-side.
- **Manage `loading` state**: set `:loading="true"` while any async call is in-flight so users see the built-in overlay.
- **Always set `field` on columns**: even when using a custom cell template. Sorting, filtering, and export depend on it.
- **Normalize data before binding**: if you need to display `firstName + lastName` in one column, compute a `fullName` field before binding — don't use a template that concatenates fields, as it breaks sorting/filtering.
- **Z-index for modals**: if you wrap a Grid in a modal, ensure the modal's z-index doesn't clip Grid popups (filter menus, dropdowns). Set `overflow: visible` on the modal and give grid popups higher z-index.

## Key Props & Events Reference

```
Grid Props (most commonly used)
─────────────────────────────────────────────────
:data-items          T[]                     Bound data (page-slice for server-side)
:total               number                  Total record count (server-side only)
:columns             ColumnDefinition[]      Prop-based column defs (or use <GridColumn>)
:pageable            true | PagerSettings    Enable paging
:sortable            true | SortSettings     Enable sorting
:filterable          true | FilterSettings   Enable filter row/menu
:groupable           true | GroupSettings    Enable grouping header
:loading             boolean                 Show loading overlay
:skip                number                  Current page offset
:take                number                  Page size
:sort                SortDescriptor[]        Current sort state
:filter              CompositeFilterDescriptor  Current filter state
:group               GroupDescriptor[]       Current group state
:edit-field          string                  Property name that tracks edit mode ('inEdit')
:selectable          true | SelectSettings   Enable row selection
:selected-field      string                  Property that tracks selection state
:detail              Component               Component rendered in expand detail row
:expand-field        string                  Property name for expand state ('expanded')
:row-height          number                  Required for virtual scrolling

Grid Events
─────────────────────────────────────────────────
@datastatechange     Combined: sort+filter+page+group changed
@sortchange          Sort changed (use when not using @datastatechange)
@filterchange        Filter changed
@pagechange          Page changed
@groupchange         Grouping changed
@itemchange          A cell value changed during inline editing
@selectionchange     Row selection changed
@headerselectionchange  Header checkbox toggled
@expandchange        Master-detail row expanded/collapsed

Sub-components (import from '@progress/kendo-vue-grid')
─────────────────────────────────────────────────
GridToolbar          Toolbar rendered inside the grid header
GridNoRecords        Custom empty-state content
GridColumn           Template-based column with #cell, #headerCell slots
```

## Code Samples

See `references/grid-samples.md` for the full set of Grid samples:
1. Client-side sort/filter/page with `process()`
2. **Server-side paging, filtering & sorting** (`@datastatechange` + fetch)
3. **Inline row editing** — Add / Edit / Save / Cancel / Delete
4. **Multi-row checkbox selection**
5. **Custom cell template** (status badge, linked text, etc.)
6. **Master-detail expandable rows**
7. **Excel export** with GridToolbar button
8. **Row virtualization** for very large datasets

Quick samples for dropdowns are below.

---

## Dropdown & Autocomplete Components

Choose based on user intent:

| Component | Package | Use when |
|---|---|---|
| `DropDownList` | `@progress/kendo-vue-dropdowns` | User must pick from a fixed list — no custom input |
| `ComboBox` | `@progress/kendo-vue-dropdowns` | User may pick from list **or** type a custom value |
| `AutoComplete` | `@progress/kendo-vue-dropdowns` | User types freely; list provides suggestions only |

**Shared best practices:**
- Enable `:filterable="true"` + `@filterchange` for large lists; never push 10k items to the client
- Set `minLength` (or check filter length manually) to avoid triggering a server call on empty input
- Avoid complex `itemRender`/`valueRender` templates — they run on every keystroke

### DropDownList

```vue
<script setup lang="ts">
import { ref } from 'vue';
import { DropDownList } from '@progress/kendo-vue-dropdowns';

interface Category { text: string; value: number }
const categories = ref<Category[]>([
  { text: 'Electronics', value: 1 },
  { text: 'Clothing', value: 2 },
  { text: 'Food', value: 3 },
]);
const selected = ref<Category | null>(null);
</script>

<template>
  <DropDownList
    :data-items="categories"
    text-field="text"
    data-item-key="value"
    v-model="selected"
    :default-item="{ text: 'Select a category…', value: null }"
    style="width: 280px;"
  />
</template>
```

### ComboBox (free-text or pick)

```vue
<script setup lang="ts">
import { ref } from 'vue';
import { ComboBox } from '@progress/kendo-vue-dropdowns';

const source = ['Apple', 'Banana', 'Cherry', 'Date', 'Elderberry'];
const items = ref([...source]);
const value = ref('');

const handleFilter = (e: any) => {
  const q = e.filter.value.toLowerCase();
  items.value = source.filter(i => i.toLowerCase().includes(q));
};
</script>

<template>
  <ComboBox
    :data-items="items"
    v-model="value"
    :filterable="true"
    placeholder="Choose or type a fruit…"
    @filterchange="handleFilter"
    style="width: 280px;"
  />
</template>
```

### AutoComplete (suggestions only, bound value stays a string)

```vue
<script setup lang="ts">
import { ref } from 'vue';
import { AutoComplete } from '@progress/kendo-vue-dropdowns';

const all = ['Austria', 'Albania', 'Belgium', 'Bulgaria', 'Croatia', 'Cyprus'];
const suggestions = ref([...all]);
const text = ref('');

const handleFilter = (e: any) => {
  const q = e.filter.value.toLowerCase();
  suggestions.value = q.length >= 2
    ? all.filter(c => c.toLowerCase().startsWith(q))
    : all;
};
</script>

<template>
  <AutoComplete
    :data-items="suggestions"
    v-model="text"
    :filterable="true"
    placeholder="Type a country…"
    @filterchange="handleFilter"
    style="width: 280px;"
  />
</template>
```
