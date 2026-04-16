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

## 4. Multi-Row Checkbox Selection

Track selection with a `selected` boolean on each item. The grid uses that field to reflect checkbox state; you update it on `@selectionchange` and `@headerselectionchange`.

```vue
<script setup lang="ts">
import { ref, computed } from 'vue';
import { Grid, GridColumn } from '@progress/kendo-vue-grid';
import type {
  GridSelectionChangeEvent,
  GridHeaderSelectionChangeEvent,
} from '@progress/kendo-vue-grid';

interface Row { id: number; name: string; role: string; selected: boolean }

const data = ref<Row[]>([
  { id: 1, name: 'Alice',   role: 'Admin',  selected: false },
  { id: 2, name: 'Bob',     role: 'Editor', selected: false },
  { id: 3, name: 'Charlie', role: 'Viewer', selected: false },
]);

const selectedRows = computed(() => data.value.filter(r => r.selected));

// Are all rows selected? Used to drive the header checkbox tri-state
const allSelected = computed(() => data.value.every(r => r.selected));

// Row-level checkbox changed
function handleSelectionChange(e: GridSelectionChangeEvent) {
  const item = data.value.find(r => r.id === (e.dataItem as Row).id);
  if (item) item.selected = !item.selected;
}

// Header "select all" checkbox
function handleHeaderSelectionChange(e: GridHeaderSelectionChangeEvent) {
  const checked = (e.nativeEvent.target as HTMLInputElement).checked;
  data.value.forEach(r => (r.selected = checked));
}
</script>

<template>
  <div>
    <p>{{ selectedRows.length }} row(s) selected</p>

    <Grid
      :data-items="data"
      :selected-field="'selected'"
      style="height: 350px;"
      @selectionchange="handleSelectionChange"
      @headerselectionchange="handleHeaderSelectionChange"
    >
      <!-- Checkbox column — selectable:true renders the header select-all checkbox -->
      <GridColumn
        :selectable="true"
        :width="'50px'"
        :header-selection-value="allSelected"
      />
      <GridColumn field="name" title="Name" />
      <GridColumn field="role" title="Role" />
    </Grid>
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
