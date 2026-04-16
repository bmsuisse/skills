# Kendo UI for Angular — Grid Code Samples

All samples use Angular standalone components with TypeScript and `@progress/kendo-angular-grid`.

---

## 1. Client-Side Sort, Filter & Page with `process()`

Use this pattern when all data fits in memory (< ~5,000 rows). The `process()` function from `@progress/kendo-data-query` handles all operations in one call.

```typescript
import { Component, OnInit } from '@angular/core';
import { KENDO_GRID } from '@progress/kendo-angular-grid';
import {
  DataStateChangeEvent,
  GridDataResult,
} from '@progress/kendo-angular-grid';
import { process, State } from '@progress/kendo-data-query';

interface Product {
  id: number;
  name: string;
  category: string;
  price: number;
  inStock: boolean;
}

const RAW_DATA: Product[] = [
  { id: 1, name: 'Chai',          category: 'Beverages',  price: 18.00, inStock: true  },
  { id: 2, name: 'Chang',         category: 'Beverages',  price: 19.00, inStock: false },
  { id: 3, name: 'Aniseed Syrup', category: 'Condiments', price: 10.00, inStock: true  },
  { id: 4, name: 'Chef Anton',    category: 'Condiments', price: 21.35, inStock: true  },
  { id: 5, name: 'Gumbo Mix',     category: 'Condiments', price: 17.00, inStock: false },
];

@Component({
  standalone: true,
  selector: 'app-grid-client',
  imports: [KENDO_GRID],
  template: `
    <kendo-grid
      [data]="gridData"
      [pageSize]="state.take"
      [skip]="state.skip"
      [sort]="state.sort"
      [filter]="state.filter"
      [pageable]="{ buttonCount: 5, info: true, pageSizes: [5, 10, 20] }"
      [sortable]="true"
      [filterable]="true"
      style="height: 400px"
      (dataStateChange)="onDataStateChange($event)"
    >
      <kendo-grid-column field="id"       title="ID"           [width]="70"  [filterable]="false" />
      <kendo-grid-column field="name"     title="Product Name" />
      <kendo-grid-column field="category" title="Category"     />
      <kendo-grid-column field="price"    title="Price"        format="{0:c}" filter="numeric" />
      <kendo-grid-column field="inStock"  title="In Stock"     filter="boolean" [width]="110" />
    </kendo-grid>
  `,
})
export class GridClientComponent implements OnInit {
  state: State = { skip: 0, take: 5, sort: [], filter: undefined };
  gridData!: GridDataResult;

  ngOnInit() {
    this.gridData = process(RAW_DATA, this.state);
  }

  onDataStateChange(state: DataStateChangeEvent) {
    this.state = state;
    this.gridData = process(RAW_DATA, this.state);
  }
}
```

---

## 2. Server-Side Paging, Filtering & Sorting with RxJS

For large datasets. The `switchMap` pattern cancels in-flight requests when state changes quickly (e.g. user types rapidly in a filter).

```typescript
import { Component, OnInit, ChangeDetectionStrategy } from '@angular/core';
import { AsyncPipe } from '@angular/common';
import { HttpClient, HttpParams } from '@angular/common/http';
import { BehaviorSubject, Observable, switchMap, tap } from 'rxjs';
import { KENDO_GRID } from '@progress/kendo-angular-grid';
import {
  DataStateChangeEvent,
  GridDataResult,
} from '@progress/kendo-angular-grid';
import { State } from '@progress/kendo-data-query';

interface Product { id: number; name: string; category: string; price: number }

@Component({
  standalone: true,
  selector: 'app-grid-server',
  imports: [KENDO_GRID, AsyncPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <kendo-grid
      [data]="(gridData$ | async) ?? { data: [], total: 0 }"
      [pageSize]="state.take"
      [skip]="state.skip"
      [sort]="state.sort"
      [filter]="state.filter"
      [loading]="loading"
      [pageable]="{ buttonCount: 5, info: true, pageSizes: [10, 25, 50] }"
      [sortable]="true"
      [filterable]="true"
      style="height: 500px"
      (dataStateChange)="onDataStateChange($event)"
    >
      <kendo-grid-column field="id"       title="ID"       [width]="80" [filterable]="false" />
      <kendo-grid-column field="name"     title="Name"     />
      <kendo-grid-column field="category" title="Category" />
      <kendo-grid-column field="price"    title="Price"    format="{0:c}" filter="numeric" />
    </kendo-grid>
  `,
})
export class GridServerComponent {
  state: State = { skip: 0, take: 10, sort: [], filter: undefined };
  loading = false;

  private state$ = new BehaviorSubject<State>(this.state);

  gridData$: Observable<GridDataResult> = this.state$.pipe(
    tap(() => (this.loading = true)),
    switchMap((state) => this.fetchData(state)),
    tap(() => (this.loading = false))
  );

  constructor(private http: HttpClient) {}

  onDataStateChange(state: DataStateChangeEvent) {
    this.state = state;
    this.state$.next(state);
  }

  private fetchData(state: State): Observable<GridDataResult> {
    const params = new HttpParams()
      .set('skip',   String(state.skip  ?? 0))
      .set('take',   String(state.take  ?? 10))
      .set('sort',   JSON.stringify(state.sort   ?? []))
      .set('filter', JSON.stringify(state.filter ?? null));
    // Server must respond with { data: Product[], total: number }
    return this.http.get<GridDataResult>('/api/products', { params });
  }
}
```

**ASP.NET Core tip**: Use `ToDataSourceResult()` from `Telerik.UI.for.AspNet.Core` — it accepts the Kendo state descriptors directly and returns the correct `{ data, total }` shape.

---

## 3. Inline Row Editing — Add / Edit / Save / Cancel / Delete

The `kendo-grid-command-column` provides built-in edit/save/cancel/remove buttons. The `(add)`, `(edit)`, `(save)`, `(cancel)`, and `(remove)` events on the grid fire at each stage.

```typescript
import { Component } from '@angular/core';
import { KENDO_GRID } from '@progress/kendo-angular-grid';
import { AddEvent, EditEvent, SaveEvent, RemoveEvent, CancelEvent } from '@progress/kendo-angular-grid';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';

interface Product { id: number; name: string; price: number }

@Component({
  standalone: true,
  selector: 'app-grid-edit',
  imports: [KENDO_GRID, ReactiveFormsModule],
  template: `
    <kendo-grid
      [data]="data"
      style="height: 400px"
      (add)="onAdd($event)"
      (edit)="onEdit($event)"
      (save)="onSave($event)"
      (cancel)="onCancel($event)"
      (remove)="onRemove($event)"
    >
      <ng-template kendoGridToolbarTemplate>
        <button kendoGridAddCommand>Add New</button>
      </ng-template>

      <kendo-grid-column field="id"    title="ID"    [width]="70"  [editable]="false" />
      <kendo-grid-column field="name"  title="Name"  />
      <kendo-grid-column field="price" title="Price" format="{0:c}" editor="numeric" />

      <kendo-grid-command-column title="Actions" [width]="180">
        <ng-template kendoGridCellTemplate let-isNew="isNew">
          <button kendoGridEditCommand   [primary]="true">Edit</button>
          <button kendoGridRemoveCommand>Delete</button>
          <button kendoGridSaveCommand   [primary]="true">{{ isNew ? 'Add' : 'Update' }}</button>
          <button kendoGridCancelCommand>Cancel</button>
        </ng-template>
      </kendo-grid-command-column>
    </kendo-grid>
  `,
})
export class GridEditComponent {
  data: Product[] = [
    { id: 1, name: 'Chai',          price: 18.00 },
    { id: 2, name: 'Chang',         price: 19.00 },
    { id: 3, name: 'Aniseed Syrup', price: 10.00 },
  ];

  private editedRowIndex?: number;
  private editedItem?: Product;

  constructor(private fb: FormBuilder) {}

  onAdd({ sender }: AddEvent) {
    this.closeEditor(sender);
    sender.addRow(this.fb.group({
      name:  ['', Validators.required],
      price: [0,  Validators.min(0)],
    }));
  }

  onEdit({ sender, rowIndex, dataItem }: EditEvent) {
    this.closeEditor(sender);
    this.editedRowIndex = rowIndex;
    this.editedItem = { ...dataItem as Product };
    sender.editRow(rowIndex, this.fb.group({
      name:  [dataItem['name'],  Validators.required],
      price: [dataItem['price'], Validators.min(0)],
    }));
  }

  onSave({ sender, rowIndex, formGroup, isNew }: SaveEvent) {
    const product: Product = formGroup.value;
    if (isNew) {
      product.id = Math.max(0, ...this.data.map(d => d.id)) + 1;
      this.data = [product, ...this.data];
      // POST /api/products
    } else {
      Object.assign(this.data[rowIndex], product);
      // PUT /api/products/:id
    }
    sender.closeRow(rowIndex);
    this.editedRowIndex = undefined;
  }

  onCancel({ sender, rowIndex }: CancelEvent) {
    sender.closeRow(rowIndex);
    this.editedRowIndex = undefined;
  }

  onRemove({ dataItem }: RemoveEvent) {
    this.data = this.data.filter(d => d.id !== (dataItem as Product).id);
    // DELETE /api/products/:id
  }

  private closeEditor(grid: any) {
    if (this.editedRowIndex !== undefined) {
      grid.closeRow(this.editedRowIndex);
      this.editedRowIndex = undefined;
    }
  }
}
```

---

## 4. Multi-Row Checkbox Selection

```typescript
import { Component } from '@angular/core';
import { NgIf } from '@angular/common';
import { KENDO_GRID } from '@progress/kendo-angular-grid';
import { SelectableSettings, SelectionChangeEvent } from '@progress/kendo-angular-grid';

interface Employee { id: number; name: string; department: string }

@Component({
  standalone: true,
  selector: 'app-grid-selection',
  imports: [KENDO_GRID, NgIf],
  template: `
    <p>{{ selectedKeys.length }} row(s) selected</p>

    <kendo-grid
      [data]="data"
      [selectable]="selectSettings"
      [selectedKeys]="selectedKeys"
      kendoGridSelectBy="id"
      style="height: 350px"
      (selectionChange)="onSelectionChange($event)"
    >
      <kendo-grid-checkbox-column [showSelectAll]="true" [width]="50" />
      <kendo-grid-column field="name"       title="Name"       />
      <kendo-grid-column field="department" title="Department" />
    </kendo-grid>
  `,
})
export class GridSelectionComponent {
  data: Employee[] = [
    { id: 1, name: 'Alice',   department: 'Engineering' },
    { id: 2, name: 'Bob',     department: 'Design'      },
    { id: 3, name: 'Charlie', department: 'Product'     },
  ];

  selectSettings: SelectableSettings = { checkboxOnly: true, mode: 'multiple' };
  selectedKeys: number[] = [];

  onSelectionChange(e: SelectionChangeEvent) {
    e.selectedRows.forEach(({ dataItem }) => {
      if (!this.selectedKeys.includes((dataItem as Employee).id)) {
        this.selectedKeys = [...this.selectedKeys, (dataItem as Employee).id];
      }
    });
    e.deselectedRows.forEach(({ dataItem }) => {
      this.selectedKeys = this.selectedKeys.filter(k => k !== (dataItem as Employee).id);
    });
  }
}
```

---

## 5. Custom Cell Template (Status Badge)

Use `ng-template kendoGridCellTemplate` on a `<kendo-grid-column>` when a column needs custom rendering — badges, icons, links, progress bars, etc. Always keep `field` set even on custom cells so sorting and filtering still work.

```typescript
import { Component } from '@angular/core';
import { NgStyle } from '@angular/common';
import { KENDO_GRID } from '@progress/kendo-angular-grid';

type Status = 'pending' | 'processing' | 'shipped' | 'delivered' | 'cancelled';

interface Order {
  id: number;
  customer: string;
  amount: number;
  status: Status;
}

const STATUS_COLORS: Record<Status, string> = {
  pending:    '#f59e0b',
  processing: '#3b82f6',
  shipped:    '#8b5cf6',
  delivered:  '#10b981',
  cancelled:  '#ef4444',
};

@Component({
  standalone: true,
  selector: 'app-grid-custom-cell',
  imports: [KENDO_GRID, NgStyle],
  template: `
    <kendo-grid [data]="data" style="height: 400px">
      <kendo-grid-column field="id"       title="Order #"  [width]="100" />
      <kendo-grid-column field="customer" title="Customer" />
      <kendo-grid-column field="amount"   title="Amount"   format="{0:c}" filter="numeric" />

      <!-- Custom status badge cell -->
      <kendo-grid-column field="status" title="Status" [width]="150">
        <ng-template kendoGridCellTemplate let-dataItem>
          <span [ngStyle]="{
            background: statusColor(dataItem.status),
            color: '#fff',
            padding: '2px 10px',
            borderRadius: '12px',
            fontSize: '12px',
            fontWeight: '600',
            textTransform: 'capitalize'
          }">{{ dataItem.status }}</span>
        </ng-template>
      </kendo-grid-column>
    </kendo-grid>
  `,
})
export class GridCustomCellComponent {
  data: Order[] = [
    { id: 1001, customer: 'Acme Corp',     amount: 1250.00, status: 'delivered'  },
    { id: 1002, customer: 'Globex',        amount:  320.50, status: 'processing' },
    { id: 1003, customer: 'Initech',       amount:  899.99, status: 'pending'    },
    { id: 1004, customer: 'Umbrella Corp', amount: 4200.00, status: 'shipped'    },
    { id: 1005, customer: 'Hooli',         amount:   75.00, status: 'cancelled'  },
  ];

  statusColor(status: Status): string {
    return STATUS_COLORS[status];
  }
}
```

---

## 6. Master-Detail (Expandable Rows)

```typescript
import { Component } from '@angular/core';
import { KENDO_GRID } from '@progress/kendo-angular-grid';
import { DetailTemplateDirective } from '@progress/kendo-angular-grid';

interface Order {
  id: number;
  customer: string;
  amount: number;
  notes?: string;
}

@Component({
  standalone: true,
  selector: 'app-grid-detail',
  imports: [KENDO_GRID],
  template: `
    <kendo-grid [data]="data" style="height: 400px">
      <kendo-grid-column field="id"       title="Order #"  [width]="100" />
      <kendo-grid-column field="customer" title="Customer" />
      <kendo-grid-column field="amount"   title="Amount"   format="{0:c}" />

      <ng-template kendoGridDetailTemplate let-dataItem>
        <section style="padding: 12px 24px; background: #f9fafb">
          <strong>Notes:</strong> {{ dataItem.notes || 'None' }}
        </section>
      </ng-template>
    </kendo-grid>
  `,
})
export class GridDetailComponent {
  data: Order[] = [
    { id: 1001, customer: 'Acme',   amount: 1250, notes: 'Rush delivery' },
    { id: 1002, customer: 'Globex', amount:  320 },
    { id: 1003, customer: 'Hooli',  amount:   75, notes: 'Gift wrap'     },
  ];
}
```

---

## 7. Excel Export

Install: `ng add @progress/kendo-angular-excel-export`

```typescript
import { Component, ViewChild } from '@angular/core';
import { KENDO_GRID } from '@progress/kendo-angular-grid';
import { GridComponent } from '@progress/kendo-angular-grid';

interface Product { id: number; name: string; category: string; price: number }

@Component({
  standalone: true,
  selector: 'app-grid-excel',
  imports: [KENDO_GRID],
  template: `
    <kendo-grid #grid [data]="data" [sortable]="true" style="height: 400px">
      <ng-template kendoGridToolbarTemplate>
        <button kendoGridExcelCommand icon="file-excel">Export to Excel</button>
      </ng-template>

      <kendo-grid-column field="id"       title="ID"           [width]="80" />
      <kendo-grid-column field="name"     title="Product Name" />
      <kendo-grid-column field="category" title="Category"     />
      <kendo-grid-column field="price"    title="Price"        format="{0:c}" />

      <kendo-grid-excel fileName="products.xlsx" />
    </kendo-grid>
  `,
})
export class GridExcelComponent {
  data: Product[] = [
    { id: 1, name: 'Chai',          category: 'Beverages',  price: 18.00 },
    { id: 2, name: 'Chang',         category: 'Beverages',  price: 19.00 },
    { id: 3, name: 'Aniseed Syrup', category: 'Condiments', price: 10.00 },
  ];
}
```

**Server-side grids**: the `<kendo-grid-excel>` element supports a `[fetchData]` callback that returns all pages before export:

```typescript
fetchData = (): Observable<GridDataResult> =>
  this.http.get<GridDataResult>('/api/products?take=999999&skip=0');
```

Bind it: `<kendo-grid-excel [fetchData]="fetchData" fileName="products.xlsx" />`

---

## 8. Virtual Scrolling for Large Datasets

Keep DOM size constant by rendering only visible rows. Requires a fixed height and accurate `rowHeight`.

```typescript
import { Component } from '@angular/core';
import { KENDO_GRID } from '@progress/kendo-angular-grid';

@Component({
  standalone: true,
  selector: 'app-grid-virtual',
  imports: [KENDO_GRID],
  template: `
    <!--
      scrollable="virtual" enables row virtualization.
      [rowHeight] must match the actual rendered row height in your theme.
      Measure it in production — the wrong value causes display gaps.
    -->
    <kendo-grid
      [data]="data"
      scrollable="virtual"
      [rowHeight]="36"
      [height]="600"
      [pageSize]="100"
    >
      <kendo-grid-column field="id"       title="ID"       [width]="90" />
      <kendo-grid-column field="name"     title="Name"     />
      <kendo-grid-column field="price"    title="Price"    format="{0:c}" />
      <kendo-grid-column field="category" title="Category" />
    </kendo-grid>
  `,
})
export class GridVirtualComponent {
  data = Array.from({ length: 100_000 }, (_, i) => ({
    id: i + 1,
    name: `Product ${i + 1}`,
    price: parseFloat((Math.random() * 100).toFixed(2)),
    category: ['Beverages', 'Condiments', 'Seafood'][i % 3],
  }));
}
```

**Virtualization checklist:**
- Set `[height]` (px) — virtualization requires a fixed container height
- `[rowHeight]` must match your CSS row height precisely
- Do **not** combine virtual scrolling with grouping
- For large data + filtering/sorting: still use server-side operations; virtualization is about DOM rendering only
