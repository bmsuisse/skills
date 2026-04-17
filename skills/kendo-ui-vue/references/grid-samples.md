# Kendo UI Vue — Grid Code Samples

All samples use Vue 3 `<script setup lang="ts">` and the Native Grid from `@progress/kendo-vue-grid`.

---

## 1. Client-Side Sort, Filter & Page with `process()`

Use this pattern when all data fits in memory (< ~5,000 rows). The `process()` function from `@progress/kendo-data-query` handles all operations in one call.

```vue
<script setup lang="ts">
import { ref, computed } from 'vue';
import { Grid } from '@progress/kendo-vue-grid';
import { process } from '@progress/kendo-data-query';
import type { DataResult, State } from '@progress/kendo-data-query';
import type { GridDataStateChangeEvent } from '@progress/kendo-vue-grid';

interface Product { id: number; name: string; category: string; price: number; inStock: boolean }

const rawData: Product[] = [
  { id: 1, name: 'Chai',         category: 'Beverages', price: 18.00, inStock: true },
  { id: 2, name: 'Chang',        category: 'Beverages', price: 19.00, inStock: false },
  { id: 3, name: 'Aniseed Syrup',category: 'Condiments',price: 10.00, inStock: true },
  { id: 4, name: 'Chef Anton',   category: 'Condiments',price: 21.35, inStock: true },
  { id: 5, name: 'Gumbo Mix',    category: 'Condiments',price: 17.00, inStock: false },
];

const dataState = ref<State>({ skip: 0, take: 5, sort: [], filter: undefined });
const dataResult = computed<DataResult>(() => process(rawData, dataState.value));

const columns = [
  { field: 'id',       title: 'ID',       width: '70px', filterable: false },
  { field: 'name',     title: 'Product Name' },
  { field: 'category', title: 'Category' },
  { field: 'price',    title: 'Price',    format: '{0:c}', filter: 'numeric' },
  { field: 'inStock',  title: 'In Stock', filter: 'boolean', width: '100px' },
];

const handleDataStateChange = (e: GridDataStateChangeEvent) => {
  dataState.value = e.dataState;
};
</script>

<template>
  <Grid
    :data-items="dataResult.data"
    :total="dataResult.total"
    :columns="columns"
    :pageable="{ buttonCount: 5, info: true, pageSizes: [5, 10, 20] }"
    :sortable="true"
    :filterable="true"
    :skip="dataState.skip"
    :take="dataState.take"
    :sort="(dataState.sort as any)"
    :filter="(dataState.filter as any)"
    style="height: 400px;"
    @datastatechange="handleDataStateChange"
  />
</template>
```

---

## 2. Server-Side Paging, Filtering & Sorting

For large datasets, send the grid state to your API and bind only the current page. Your server response must include `{ data: T[], total: number }` — the `total` is the unfiltered count so the pager renders correctly.

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { Grid } from '@progress/kendo-vue-grid';
import type { GridDataStateChangeEvent } from '@progress/kendo-vue-grid';
import type { State } from '@progress/kendo-data-query';

interface Product { id: number; name: string; category: string; price: number }

const dataItems = ref<Product[]>([]);
const total = ref(0);
const loading = ref(false);
const dataState = ref<State>({
  skip: 0,
  take: 10,
  sort: [],
  filter: undefined,
});

const columns = [
  { field: 'id',       title: 'ID',       width: '80px', filterable: false },
  { field: 'name',     title: 'Name' },
  { field: 'category', title: 'Category' },
  { field: 'price',    title: 'Price',    format: '{0:c}', filter: 'numeric' },
];

async function fetchData() {
  loading.value = true;
  try {
    // Serialize state into query params — adapt to your API's conventions
    const params = new URLSearchParams({
      skip:   String(dataState.value.skip  ?? 0),
      take:   String(dataState.value.take  ?? 10),
      sort:   JSON.stringify(dataState.value.sort   ?? []),
      filter: JSON.stringify(dataState.value.filter ?? null),
    });
    const res = await fetch(`/api/products?${params}`);
    const json = await res.json(); // must be { data: Product[], total: number }
    dataItems.value = json.data;
    total.value     = json.total;
  } finally {
    loading.value = false;
  }
}

const handleDataStateChange = (e: GridDataStateChangeEvent) => {
  dataState.value = e.dataState;
  fetchData();
};

onMounted(fetchData);
</script>

<template>
  <Grid
    :data-items="dataItems"
    :total="total"
    :columns="columns"
    :loading="loading"
    :pageable="{ buttonCount: 5, info: true, pageSizes: [10, 25, 50] }"
    :sortable="true"
    :filterable="true"
    :skip="dataState.skip"
    :take="dataState.take"
    :sort="(dataState.sort as any)"
    :filter="(dataState.filter as any)"
    style="height: 500px;"
    @datastatechange="handleDataStateChange"
  />
</template>
```

**Server-side tip**: If using ASP.NET Core, the `ToDataSourceResult()` extension from `Telerik.UI.for.AspNet.Core` handles all Kendo state descriptors automatically and returns the correct `{ data, total }` shape.

---

## 3. Inline Row Editing — Add / Edit / Save / Cancel / Delete

This is the most common CRUD pattern. Each data item carries an optional `inEdit` flag; the Grid uses `edit-field="inEdit"` to know which row is being edited. The `@itemchange` event fires when any editable cell changes.

**Key points:**
- Clone items when entering edit mode so Cancel can restore the original values
- Use `<GridColumn>` with `#cell` slot for the command column (gives access to parent scope)
- Remove the `inEdit` flag (and the backup clone) on save or cancel

```vue
<script setup lang="ts">
import { ref } from 'vue';
import { Grid, GridToolbar, GridColumn } from '@progress/kendo-vue-grid';
import type { GridItemChangeEvent } from '@progress/kendo-vue-grid';

interface Product {
  id: number;
  name: string;
  price: number;
  inEdit?: boolean;
  // used internally to roll back on Cancel:
  _original?: Omit<Product, 'inEdit' | '_original'>;
}

let nextId = 10;
const data = ref<Product[]>([
  { id: 1, name: 'Chai',         price: 18.00 },
  { id: 2, name: 'Chang',        price: 19.00 },
  { id: 3, name: 'Aniseed Syrup',price: 10.00 },
]);

// Enter edit mode: clone the original so we can roll back on Cancel
function editItem(item: Product) {
  item._original = { id: item.id, name: item.name, price: item.price };
  item.inEdit = true;
}

function saveItem(item: Product) {
  // Persist to server here, then clean up
  delete item.inEdit;
  delete item._original;
}

function cancelItem(item: Product) {
  if (item._original) {
    Object.assign(item, item._original);
    delete item._original;
  }
  // New (unsaved) items have no _original → remove them
  if (!item.id) {
    data.value = data.value.filter(d => d !== item);
  } else {
    delete item.inEdit;
  }
}

function removeItem(item: Product) {
  data.value = data.value.filter(d => d.id !== item.id);
  // Call DELETE /api/products/:id here
}

function addNew() {
  const newItem: Product = { id: 0, name: '', price: 0, inEdit: true };
  data.value = [newItem, ...data.value];
}

// Fires when the user types in an editable cell
function handleItemChange(e: GridItemChangeEvent) {
  const match = data.value.find(d => d.id === (e.dataItem as Product).id);
  if (match) {
    (match as any)[e.field!] = e.value;
  }
}
</script>

<template>
  <Grid
    :data-items="data"
    :edit-field="'inEdit'"
    style="height: 400px;"
    @itemchange="handleItemChange"
  >
    <GridToolbar>
      <button
        class="k-button k-button-md k-rounded-md k-button-solid k-button-solid-primary"
        @click="addNew"
      >
        Add New
      </button>
    </GridToolbar>

    <GridColumn field="id"    title="ID"    width="70px"  :editable="false" />
    <GridColumn field="name"  title="Name"  />
    <GridColumn field="price" title="Price" format="{0:c}" editor="numeric" />

    <!-- Command column — uses slot to access parent-scope handlers -->
    <GridColumn title="Actions" :width="'180px'">
      <template #cell="{ dataItem }">
        <td>
          <template v-if="(dataItem as Product).inEdit">
            <button
              class="k-button k-button-sm k-rounded-md k-button-solid k-button-solid-primary"
              @click="saveItem(dataItem as Product)"
            >Update</button>
            <button
              class="k-button k-button-sm k-rounded-md k-button-solid k-button-solid-base"
              style="margin-left:4px"
              @click="cancelItem(dataItem as Product)"
            >Cancel</button>
          </template>
          <template v-else>
            <button
              class="k-button k-button-sm k-rounded-md k-button-solid k-button-solid-primary"
              @click="editItem(dataItem as Product)"
            >Edit</button>
            <button
              class="k-button k-button-sm k-rounded-md k-button-solid k-button-solid-error"
              style="margin-left:4px"
              @click="removeItem(dataItem as Product)"
            >Delete</button>
          </template>
        </td>
      </template>
    </GridColumn>
  </Grid>
</template>
```

---

## 4. Row Selection — Four Patterns

The Vue Native Grid uses a **key-based selection model**: a `select` ref holds `{ [key]: true }` for each selected row. The key field is declared via `data-item-key`. Both `@selectionchange` and `@headerselectionchange` return the complete new selection state in `event.select` — just assign it.

```
Selection API quick reference
────────────────────────────────────────────────
data-item-key        string              Key field for selection (required)
:selectable          GridSelectableSettings  { enabled, mode, drag, cell }
:select              SelectDescriptor    Controlled state: { [key]: true }
:default-select      SelectDescriptor    Uncontrolled initial state (no handler needed)
{ columnType: 'checkbox' }  in :columns  Renders per-row checkboxes + select-all header
@selectionchange     event.select        Assign to your select ref
@headerselectionchange event.select      Assign to your select ref

// Read selected items:
const selectedItems = computed(() => data.value.filter(e => select.value[e.id]));
```

---

### 4a. Single-Row Click-to-Select

No checkbox column needed — clicking a row selects it. Set `mode: 'single'` and no `{ columnType: 'checkbox' }` column.

```vue
<script setup lang="ts">
import { ref, computed } from 'vue';
import { Grid } from '@progress/kendo-vue-grid';
import type { GridSelectionChangeEvent } from '@progress/kendo-vue-grid';

interface Employee { id: number; name: string; department: string }

const data = ref<Employee[]>([
  { id: 1, name: 'Alice',   department: 'Engineering' },
  { id: 2, name: 'Bob',     department: 'Design'      },
  { id: 3, name: 'Charlie', department: 'Product'     },
  { id: 4, name: 'Diana',   department: 'Engineering' },
]);

// { [id]: true } for the selected row — single mode keeps at most one entry
const select = ref<Record<number, boolean>>({});

const selectedEmployee = computed(() =>
  data.value.find(e => select.value[e.id]) ?? null
);

const columns = [
  { field: 'name',       title: 'Name'       },
  { field: 'department', title: 'Department' },
];

const onSelectionChange = (e: GridSelectionChangeEvent) => {
  select.value = e.select as Record<number, boolean>;
};
</script>

<template>
  <div>
    <p>Selected: <strong>{{ selectedEmployee?.name ?? 'none' }}</strong></p>

    <Grid
      :data-items="data"
      data-item-key="id"
      :selectable="{ enabled: true, mode: 'single' }"
      :select="select"
      :columns="columns"
      :style="{ height: '300px' }"
      @selectionchange="onSelectionChange"
    />
  </div>
</template>
```

---

### 4b. Multi-Row Checkbox Selection with Bulk Actions

Add `{ columnType: 'checkbox' }` as the first entry in `:columns` to render per-row checkboxes and a header select-all checkbox. Both events return `event.select` — the complete new state to assign.

```vue
<script setup lang="ts">
import { ref, computed } from 'vue';
import { Grid } from '@progress/kendo-vue-grid';
import type {
  GridSelectionChangeEvent,
  GridHeaderSelectionChangeEvent,
} from '@progress/kendo-vue-grid';

interface Employee { id: number; name: string; department: string }

const data = ref<Employee[]>([
  { id: 1, name: 'Alice',   department: 'Engineering' },
  { id: 2, name: 'Bob',     department: 'Design'      },
  { id: 3, name: 'Charlie', department: 'Product'     },
  { id: 4, name: 'Diana',   department: 'Engineering' },
  { id: 5, name: 'Eve',     department: 'Design'      },
]);

const select = ref<Record<number, boolean>>({});

const selectedItems = computed(() => data.value.filter(e => select.value[e.id]));

const columns = [
  { columnType: 'checkbox' },           // renders checkboxes + select-all in header
  { field: 'name',       title: 'Name'       },
  { field: 'department', title: 'Department' },
];

// Both events return the complete new selection state — just assign it
const onSelectionChange = (e: GridSelectionChangeEvent) => {
  select.value = e.select as Record<number, boolean>;
};
const onHeaderSelectionChange = (e: GridHeaderSelectionChangeEvent) => {
  select.value = e.select as Record<number, boolean>;
};

function deleteSelected() {
  data.value = data.value.filter(e => !select.value[e.id]);
  select.value = {};
}
</script>

<template>
  <div>
    <div style="margin-bottom: 8px; display: flex; align-items: center; gap: 12px;">
      <span>{{ selectedItems.length }} of {{ data.length }} selected</span>
      <button
        v-if="selectedItems.length > 0"
        class="k-button k-button-md k-rounded-md k-button-solid k-button-solid-error"
        @click="deleteSelected"
      >
        Delete Selected ({{ selectedItems.length }})
      </button>
    </div>

    <Grid
      :data-items="data"
      data-item-key="id"
      :selectable="{ enabled: true, mode: 'multiple' }"
      :select="select"
      :columns="columns"
      :style="{ height: '350px' }"
      @selectionchange="onSelectionChange"
      @headerselectionchange="onHeaderSelectionChange"
    />
  </div>
</template>
```

---

### 4c. Programmatic Selection

`select` is a plain ref — reassign it to select rows from outside the grid without any grid API call.

```vue
<script setup lang="ts">
import { ref, computed } from 'vue';
import { Grid } from '@progress/kendo-vue-grid';
import type {
  GridSelectionChangeEvent,
  GridHeaderSelectionChangeEvent,
} from '@progress/kendo-vue-grid';

interface Employee { id: number; name: string; department: string }

const data = ref<Employee[]>([
  { id: 1, name: 'Alice',   department: 'Engineering' },
  { id: 2, name: 'Bob',     department: 'Design'      },
  { id: 3, name: 'Charlie', department: 'Product'     },
  { id: 4, name: 'Diana',   department: 'Engineering' },
  { id: 5, name: 'Eve',     department: 'Design'      },
]);

const select = ref<Record<number, boolean>>({});

const selectedItems = computed(() => data.value.filter(e => select.value[e.id]));

const columns = [
  { columnType: 'checkbox' },
  { field: 'name',       title: 'Name'       },
  { field: 'department', title: 'Department' },
];

const onSelectionChange = (e: GridSelectionChangeEvent) => {
  select.value = e.select as Record<number, boolean>;
};
const onHeaderSelectionChange = (e: GridHeaderSelectionChangeEvent) => {
  select.value = e.select as Record<number, boolean>;
};

// Programmatic helpers — reassign the ref, grid reacts automatically
function selectAll() {
  select.value = Object.fromEntries(data.value.map(e => [e.id, true]));
}
function clearSelection() { select.value = {}; }
function invertSelection() {
  select.value = Object.fromEntries(
    data.value.filter(e => !select.value[e.id]).map(e => [e.id, true])
  );
}
function selectByDept(dept: string) {
  select.value = Object.fromEntries(
    data.value.filter(e => e.department === dept).map(e => [e.id, true])
  );
}
</script>

<template>
  <div>
    <div style="margin-bottom: 8px; display: flex; gap: 8px; flex-wrap: wrap;">
      <button class="k-button k-button-sm k-rounded-md k-button-solid k-button-solid-primary" @click="selectAll">Select All</button>
      <button class="k-button k-button-sm k-rounded-md k-button-solid k-button-solid-base"    @click="clearSelection">Clear</button>
      <button class="k-button k-button-sm k-rounded-md k-button-solid k-button-solid-base"    @click="invertSelection">Invert</button>
      <button class="k-button k-button-sm k-rounded-md k-button-solid k-button-solid-base"    @click="selectByDept('Engineering')">Engineering only</button>
    </div>
    <p>{{ selectedItems.length }} row(s) selected</p>

    <Grid
      :data-items="data"
      data-item-key="id"
      :selectable="{ enabled: true, mode: 'multiple' }"
      :select="select"
      :columns="columns"
      :style="{ height: '350px' }"
      @selectionchange="onSelectionChange"
      @headerselectionchange="onHeaderSelectionChange"
    />
  </div>
</template>
```

---

### 4d. Persisting Selection Across Pages

Because `select` is key-based (not tied to current page items), it persists across page changes automatically — no extra bookkeeping needed. This is the main advantage over field-based selection.

```vue
<script setup lang="ts">
import { ref, computed } from 'vue';
import { Grid } from '@progress/kendo-vue-grid';
import { process } from '@progress/kendo-data-query';
import type { State, DataResult } from '@progress/kendo-data-query';
import type {
  GridDataStateChangeEvent,
  GridSelectionChangeEvent,
  GridHeaderSelectionChangeEvent,
} from '@progress/kendo-vue-grid';

interface Employee { id: number; name: string; department: string }

const rawData: Employee[] = Array.from({ length: 25 }, (_, i) => ({
  id: i + 1,
  name: `Employee ${i + 1}`,
  department: ['Engineering', 'Design', 'Product', 'Sales'][i % 4],
}));

const dataState = ref<State>({ skip: 0, take: 5 });
const dataResult = computed<DataResult>(() => process(rawData, dataState.value));

// Keys persist across page changes — no re-stamping needed
const select = ref<Record<number, boolean>>({});

const totalSelected = computed(() => Object.keys(select.value).length);

const columns = [
  { columnType: 'checkbox' },
  { field: 'name',       title: 'Name'       },
  { field: 'department', title: 'Department' },
];

const onDataStateChange = (e: GridDataStateChangeEvent) => {
  dataState.value = e.dataState;
  // select stays unchanged — selection is preserved automatically
};

const onSelectionChange = (e: GridSelectionChangeEvent) => {
  select.value = e.select as Record<number, boolean>;
};
const onHeaderSelectionChange = (e: GridHeaderSelectionChangeEvent) => {
  select.value = e.select as Record<number, boolean>;
};
</script>

<template>
  <div>
    <p>{{ totalSelected }} of {{ rawData.length }} total rows selected (across all pages)</p>

    <Grid
      :data-items="dataResult.data"
      :total="dataResult.total"
      data-item-key="id"
      :selectable="{ enabled: true, mode: 'multiple' }"
      :select="select"
      :pageable="{ buttonCount: 5, info: true }"
      :skip="dataState.skip"
      :take="dataState.take"
      :columns="columns"
      :style="{ height: '400px' }"
      @datastatechange="onDataStateChange"
      @selectionchange="onSelectionChange"
      @headerselectionchange="onHeaderSelectionChange"
    />
  </div>
</template>
```

---

## 5. Custom Cell Template (Status Badge Example)

Use the `#cell` slot on `<GridColumn>` when a column needs custom rendering — icons, badges, links, progress bars, etc. Always keep the `field` set even on custom cells so sorting and filtering still work.

```vue
<script setup lang="ts">
import { ref } from 'vue';
import { Grid, GridColumn } from '@progress/kendo-vue-grid';

interface Order {
  id: number;
  customer: string;
  amount: number;
  status: 'pending' | 'processing' | 'shipped' | 'delivered' | 'cancelled';
}

const data = ref<Order[]>([
  { id: 1001, customer: 'Acme Corp',     amount: 1250.00, status: 'delivered'  },
  { id: 1002, customer: 'Globex',        amount: 320.50,  status: 'processing' },
  { id: 1003, customer: 'Initech',       amount: 899.99,  status: 'pending'    },
  { id: 1004, customer: 'Umbrella Corp', amount: 4200.00, status: 'shipped'    },
  { id: 1005, customer: 'Hooli',         amount: 75.00,   status: 'cancelled'  },
]);

const statusColors: Record<Order['status'], string> = {
  pending:    '#f59e0b',
  processing: '#3b82f6',
  shipped:    '#8b5cf6',
  delivered:  '#10b981',
  cancelled:  '#ef4444',
};
</script>

<template>
  <Grid :data-items="data" style="height: 400px;">
    <GridColumn field="id"       title="Order #"  width="100px" />
    <GridColumn field="customer" title="Customer" />
    <GridColumn field="amount"   title="Amount"   format="{0:c}" filter="numeric" />

    <!-- Custom status badge cell -->
    <GridColumn field="status" title="Status" width="140px">
      <template #cell="{ dataItem }">
        <td>
          <span
            :style="{
              background: statusColors[(dataItem as Order).status],
              color: '#fff',
              padding: '2px 10px',
              borderRadius: '12px',
              fontSize: '12px',
              fontWeight: 600,
              textTransform: 'capitalize',
            }"
          >
            {{ (dataItem as Order).status }}
          </span>
        </td>
      </template>
    </GridColumn>
  </Grid>
</template>
```

---

## 6. Master-Detail (Expandable Rows)

Pass a component to the `:detail` prop to render extra content below each row when expanded. The component receives `{ dataItem }` as a prop. Track expand state with a boolean field (e.g. `expanded`) and update it in `@expandchange`.

```vue
<!-- OrderDetail.vue — child component rendered in the detail row -->
<script setup lang="ts">
defineProps<{ dataItem: any }>();
</script>

<template>
  <section style="padding: 12px 24px; background: #f9fafb;">
    <strong>Order Notes:</strong> {{ dataItem.notes || 'None' }}<br />
    <strong>Internal ID:</strong> {{ dataItem.internalId }}
  </section>
</template>
```

```vue
<!-- ParentGrid.vue -->
<script setup lang="ts">
import { ref } from 'vue';
import { Grid } from '@progress/kendo-vue-grid';
import type { GridExpandChangeEvent } from '@progress/kendo-vue-grid';
import OrderDetail from './OrderDetail.vue';

interface Order {
  id: number; customer: string; amount: number;
  notes?: string; internalId?: string;
  expanded: boolean;
}

const data = ref<Order[]>([
  { id: 1001, customer: 'Acme',   amount: 1250, notes: 'Rush delivery', internalId: 'ORD-A1', expanded: false },
  { id: 1002, customer: 'Globex', amount: 320,  notes: '',              internalId: 'ORD-B2', expanded: false },
  { id: 1003, customer: 'Hooli',  amount: 75,   notes: 'Gift wrap',     internalId: 'ORD-C3', expanded: false },
]);

const columns = [
  { field: 'id',       title: 'Order #', width: '100px' },
  { field: 'customer', title: 'Customer' },
  { field: 'amount',   title: 'Amount',  format: '{0:c}' },
];

function handleExpandChange(e: GridExpandChangeEvent) {
  const item = data.value.find(r => r.id === (e.dataItem as Order).id);
  if (item) item.expanded = !item.expanded;
}
</script>

<template>
  <Grid
    :data-items="data"
    :columns="columns"
    :detail="OrderDetail"
    :expand-field="'expanded'"
    style="height: 400px;"
    @expandchange="handleExpandChange"
  />
</template>
```

---

## 7. Excel Export

Install the export package: `npm install @progress/kendo-vue-excel-export`

Use `saveExcel()` to trigger a client-side download. Pass the same column definitions you use for display, or filter them to control what gets exported.

```vue
<script setup lang="ts">
import { ref } from 'vue';
import { Grid, GridToolbar } from '@progress/kendo-vue-grid';
import { saveExcel } from '@progress/kendo-vue-excel-export';

interface Product { id: number; name: string; category: string; price: number }

const data = ref<Product[]>([
  { id: 1, name: 'Chai',         category: 'Beverages',  price: 18.00 },
  { id: 2, name: 'Chang',        category: 'Beverages',  price: 19.00 },
  { id: 3, name: 'Aniseed Syrup',category: 'Condiments', price: 10.00 },
]);

const columns = [
  { field: 'id',       title: 'ID',       width: '80px' },
  { field: 'name',     title: 'Product Name' },
  { field: 'category', title: 'Category' },
  { field: 'price',    title: 'Price',    format: '{0:c}' },
];

// For server-side grids, pass the *full* dataset (not just the current page) to saveExcel
function exportToExcel() {
  saveExcel({
    data: data.value,
    fileName: 'products',
    columns: columns.map(c => ({ field: c.field, title: c.title, width: c.width })),
  });
}
</script>

<template>
  <Grid
    :data-items="data"
    :columns="columns"
    :sortable="true"
    style="height: 400px;"
  >
    <GridToolbar>
      <button
        class="k-button k-button-md k-rounded-md k-button-solid k-button-solid-primary"
        @click="exportToExcel"
      >
        Export to Excel
      </button>
    </GridToolbar>
  </Grid>
</template>
```

**Server-side export**: When the grid is server-paged, `data.value` contains only the current page. Fetch the full dataset first:

```typescript
async function exportToExcel() {
  const res = await fetch('/api/products?take=999999&skip=0');
  const { data: allData } = await res.json();
  saveExcel({ data: allData, fileName: 'products', columns: /* ... */ });
}
```

---

## 8. Row Virtualization for Large Datasets

Row virtualization keeps a constant DOM size by rendering only visible rows. Use it for 10,000+ rows in scrollable (non-paged) grids. Column virtualization (`columnVirtualization`) is for grids with 50+ columns.

```vue
<script setup lang="ts">
import { ref } from 'vue';
import { Grid } from '@progress/kendo-vue-grid';

// Generate a large dataset
const data = ref(
  Array.from({ length: 100_000 }, (_, i) => ({
    id: i + 1,
    name: `Product ${i + 1}`,
    price: parseFloat((Math.random() * 100).toFixed(2)),
    category: ['Beverages', 'Condiments', 'Seafood'][i % 3],
  }))
);

const columns = [
  { field: 'id',       title: 'ID',       width: '90px' },
  { field: 'name',     title: 'Name' },
  { field: 'price',    title: 'Price',    format: '{0:c}' },
  { field: 'category', title: 'Category' },
];
</script>

<template>
  <!--
    scrollable="virtual" + :row-height="N" enables row virtualization.
    row-height must match the actual rendered row height — measure it in
    production with the same theme and font size you're using.
    A fixed height on the grid is required.
  -->
  <Grid
    :data-items="data"
    :columns="columns"
    scrollable="virtual"
    :row-height="36"
    style="height: 600px;"
  />
</template>
```

**Virtualization checklist:**
- Set an explicit `style="height: Npx"` — virtualization requires a fixed height
- `:row-height` must be accurate — use a value that matches your CSS row height
- Do **not** combine virtual scrolling with grouping (not supported)
- For combined large-data + filtering/sorting: still do server-side ops; virtualization is about DOM rendering, not data fetching
