# Kendo UI for Angular — TreeList & TreeView Code Samples

---

## TreeList

TreeList renders hierarchical data as an expandable **table** — rows can have children revealed by an expand arrow. It has the full column / sort / filter / edit feature set of the Grid but with built-in parent-child relationships.

---

### 1. Flat-Data Binding (idField / parentIdField)

Use when your data is a flat array where each item references its parent by ID (e.g. a SQL query result).

```typescript
import { Component } from '@angular/core';
import { KENDO_TREELIST } from '@progress/kendo-angular-treelist';

interface Employee {
  id: number;
  managerId: number | null;
  name: string;
  title: string;
  department: string;
}

@Component({
  standalone: true,
  selector: 'app-treelist-flat',
  imports: [KENDO_TREELIST],
  template: `
    <kendo-treelist
      kendoTreeListFlatBinding
      [data]="employees"
      idField="id"
      parentIdField="managerId"
      [sortable]="true"
      [filterable]="true"
      style="height: 450px"
    >
      <kendo-treelist-column field="name"       title="Name"       [expandable]="true" />
      <kendo-treelist-column field="title"      title="Title"      />
      <kendo-treelist-column field="department" title="Department" />
    </kendo-treelist>
  `,
})
export class TreeListFlatComponent {
  employees: Employee[] = [
    { id: 1, managerId: null, name: 'Daryl Sweeney', title: 'CEO',         department: 'Executive' },
    { id: 2, managerId: 1,   name: 'Guy Wooten',    title: 'CTO',         department: 'Technology' },
    { id: 3, managerId: 1,   name: 'Priya Ramirez', title: 'CFO',         department: 'Finance'    },
    { id: 4, managerId: 2,   name: 'Ana Suarez',    title: 'Lead Dev',    department: 'Technology' },
    { id: 5, managerId: 2,   name: 'Liam Chen',     title: 'Dev Ops',     department: 'Technology' },
    { id: 6, managerId: 3,   name: 'Felix Wagner',  title: 'Controller',  department: 'Finance'    },
  ];
}
```

> **Note**: Add `[expandable]="true"` on the first column to show the expand/collapse toggle arrow on that column.

---

### 2. Hierarchical Data Binding (nested objects)

Use when your data is already nested (e.g. a JSON API that returns children as an array property).

```typescript
import { Component } from '@angular/core';
import { KENDO_TREELIST } from '@progress/kendo-angular-treelist';

interface FileNode {
  name: string;
  type: 'folder' | 'file';
  size?: number;
  contents?: FileNode[];
}

@Component({
  standalone: true,
  selector: 'app-treelist-hierarchy',
  imports: [KENDO_TREELIST],
  template: `
    <kendo-treelist
      kendoTreeListHierarchyBinding
      [data]="fileTree"
      childrenField="contents"
      style="height: 400px"
    >
      <kendo-treelist-column field="name" title="Name" [expandable]="true" />
      <kendo-treelist-column field="type" title="Type" [width]="100" />
      <kendo-treelist-column field="size" title="Size (KB)" [width]="130" />
    </kendo-treelist>
  `,
})
export class TreeListHierarchyComponent {
  fileTree: FileNode[] = [
    {
      name: 'src', type: 'folder',
      contents: [
        { name: 'app', type: 'folder', contents: [
            { name: 'app.component.ts', type: 'file', size: 4  },
            { name: 'app.module.ts',    type: 'file', size: 2  },
        ]},
        { name: 'main.ts', type: 'file', size: 1 },
        { name: 'styles.scss', type: 'file', size: 8 },
      ],
    },
    {
      name: 'package.json', type: 'file', size: 3
    },
  ];
}
```

---

### 3. On-Demand Async Children Loading

Use when children are too numerous to load upfront or come from a lazy API endpoint. Provide `[hasChildren]` so the tree shows the toggle before fetching, and `[fetchChildren]` which returns an `Observable`.

```typescript
import { Component } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { KENDO_TREELIST } from '@progress/kendo-angular-treelist';

interface Category { id: number; parentId: number | null; name: string; hasChildren: boolean }

@Component({
  standalone: true,
  selector: 'app-treelist-async',
  imports: [KENDO_TREELIST],
  template: `
    <kendo-treelist
      [data]="rootItems"
      [fetchChildren]="fetchChildren"
      [hasChildren]="hasChildren"
      style="height: 450px"
    >
      <kendo-treelist-column field="name" title="Category" [expandable]="true" />
    </kendo-treelist>
  `,
})
export class TreeListAsyncComponent {
  rootItems: Category[] = [];

  constructor(private http: HttpClient) {}

  ngOnInit() {
    this.http.get<Category[]>('/api/categories?parentId=null').subscribe(
      items => (this.rootItems = items)
    );
  }

  hasChildren = (item: Category) => item.hasChildren;

  fetchChildren = (item: Category): Observable<Category[]> =>
    this.http.get<Category[]>(`/api/categories?parentId=${item.id}`);
}
```

---

### 4. Inline Editing in TreeList

Inline editing in TreeList follows the same reactive-forms pattern as the Grid — use `(add)`, `(edit)`, `(save)`, `(cancel)`, `(remove)` events.

```typescript
import { Component } from '@angular/core';
import { KENDO_TREELIST } from '@progress/kendo-angular-treelist';
import {
  AddEvent, EditEvent, SaveEvent, CancelEvent, RemoveEvent,
} from '@progress/kendo-angular-treelist';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';

interface Employee { id: number; managerId: number | null; name: string; title: string }

@Component({
  standalone: true,
  selector: 'app-treelist-edit',
  imports: [KENDO_TREELIST, ReactiveFormsModule],
  template: `
    <kendo-treelist
      kendoTreeListFlatBinding
      [data]="employees"
      idField="id"
      parentIdField="managerId"
      style="height: 450px"
      (add)="onAdd($event)"
      (edit)="onEdit($event)"
      (save)="onSave($event)"
      (cancel)="onCancel($event)"
      (remove)="onRemove($event)"
    >
      <ng-template kendoTreeListToolbarTemplate>
        <button kendoTreeListAddCommand>Add New</button>
      </ng-template>

      <kendo-treelist-column field="name"  title="Name"  [expandable]="true" />
      <kendo-treelist-column field="title" title="Title" />

      <kendo-treelist-command-column title="Actions" [width]="190">
        <ng-template kendoTreeListCellTemplate let-isNew="isNew">
          <button kendoTreeListEditCommand   [primary]="true">Edit</button>
          <button kendoTreeListRemoveCommand>Delete</button>
          <button kendoTreeListSaveCommand   [primary]="true">{{ isNew ? 'Add' : 'Update' }}</button>
          <button kendoTreeListCancelCommand>Cancel</button>
        </ng-template>
      </kendo-treelist-command-column>
    </kendo-treelist>
  `,
})
export class TreeListEditComponent {
  employees: Employee[] = [
    { id: 1, managerId: null, name: 'Daryl Sweeney', title: 'CEO'      },
    { id: 2, managerId: 1,   name: 'Guy Wooten',    title: 'CTO'      },
    { id: 3, managerId: 2,   name: 'Ana Suarez',    title: 'Lead Dev' },
  ];
  private editedRowIndex?: number;

  constructor(private fb: FormBuilder) {}

  onAdd({ sender }: AddEvent) {
    this.closeEditor(sender);
    sender.addRow(this.fb.group({ name: ['', Validators.required], title: [''] }));
  }

  onEdit({ sender, rowIndex, dataItem }: EditEvent) {
    this.closeEditor(sender);
    this.editedRowIndex = rowIndex;
    sender.editRow(rowIndex, this.fb.group({
      name:  [dataItem['name'],  Validators.required],
      title: [dataItem['title']],
    }));
  }

  onSave({ sender, rowIndex, formGroup, isNew }: SaveEvent) {
    const values = formGroup.value as Pick<Employee, 'name' | 'title'>;
    if (isNew) {
      this.employees = [
        { id: Math.max(0, ...this.employees.map(e => e.id)) + 1, managerId: null, ...values },
        ...this.employees,
      ];
    } else {
      Object.assign(this.employees[rowIndex], values);
    }
    sender.closeRow(rowIndex);
    this.editedRowIndex = undefined;
  }

  onCancel({ sender, rowIndex }: CancelEvent) {
    sender.closeRow(rowIndex);
    this.editedRowIndex = undefined;
  }

  onRemove({ dataItem }: RemoveEvent) {
    this.employees = this.employees.filter(e => e.id !== (dataItem as Employee).id);
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

## TreeView

TreeView is a navigation tree — a collapsible/expandable sidebar menu or selection tree. It has no columns, sorting, or pagination. Use it for navigation structures, folder trees, category selectors.

---

### 1. Hierarchical Binding with Expand/Collapse State

```typescript
import { Component } from '@angular/core';
import { KENDO_TREEVIEW } from '@progress/kendo-angular-treeview';

interface NavNode { text: string; id: number; children?: NavNode[] }

@Component({
  standalone: true,
  selector: 'app-treeview-hierarchy',
  imports: [KENDO_TREEVIEW],
  template: `
    <kendo-treeview
      kendoTreeViewHierarchyBinding
      [nodes]="nodes"
      textField="text"
      childrenField="children"
      kendoTreeViewExpandable
      [isExpanded]="isExpanded"
      (expand)="onExpand($event)"
      (collapse)="onCollapse($event)"
      (nodeClick)="onNodeClick($event)"
    />
  `,
})
export class TreeViewHierarchyComponent {
  nodes: NavNode[] = [
    {
      text: 'Products', id: 1, children: [
        { text: 'Grid',         id: 2 },
        { text: 'TreeList',     id: 3 },
        { text: 'Chart',        id: 4 },
      ],
    },
    {
      text: 'Framework', id: 5, children: [
        { text: 'Data Query',   id: 6 },
        { text: 'Localization', id: 7 },
      ],
    },
  ];

  private expanded = new Set<number>([1]); // expand first node by default

  isExpanded = (node: NavNode) => this.expanded.has(node.id);
  onExpand   = ({ dataItem }: any) => this.expanded.add((dataItem as NavNode).id);
  onCollapse = ({ dataItem }: any) => this.expanded.delete((dataItem as NavNode).id);
  onNodeClick = ({ item }: any) => console.log('Clicked:', item.dataItem);
}
```

---

### 2. Flat Data Binding

```typescript
import { Component } from '@angular/core';
import { KENDO_TREEVIEW } from '@progress/kendo-angular-treeview';

interface Category { id: number; parentId: number | null; text: string }

@Component({
  standalone: true,
  selector: 'app-treeview-flat',
  imports: [KENDO_TREEVIEW],
  template: `
    <kendo-treeview
      kendoTreeViewFlatDataBinding
      [nodes]="categories"
      textField="text"
      idField="id"
      parentIdField="parentId"
      kendoTreeViewExpandable
    />
  `,
})
export class TreeViewFlatComponent {
  categories: Category[] = [
    { id: 1, parentId: null, text: 'Furniture' },
    { id: 2, parentId: 1,   text: 'Tables' },
    { id: 3, parentId: 1,   text: 'Chairs' },
    { id: 4, parentId: 2,   text: 'Dining Tables' },
    { id: 5, parentId: 2,   text: 'Coffee Tables' },
    { id: 6, parentId: null, text: 'Electronics' },
    { id: 7, parentId: 6,   text: 'Laptops' },
  ];
}
```

---

### 3. Load on Demand (Async Children via Observable)

Use when your tree can be very deep or has many nodes — load children only when the user expands a parent.

```typescript
import { Component } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { KENDO_TREEVIEW } from '@progress/kendo-angular-treeview';

interface TreeNode { id: number; text: string; hasChildren: boolean }

@Component({
  standalone: true,
  selector: 'app-treeview-async',
  imports: [KENDO_TREEVIEW],
  template: `
    <kendo-treeview
      [nodes]="rootNodes"
      textField="text"
      [children]="fetchChildren"
      [hasChildren]="hasChildren"
      [loadOnDemand]="true"
      kendoTreeViewExpandable
    />
  `,
})
export class TreeViewAsyncComponent {
  rootNodes: TreeNode[] = [];

  constructor(private http: HttpClient) {}

  ngOnInit() {
    this.http.get<TreeNode[]>('/api/tree?parentId=null').subscribe(
      nodes => (this.rootNodes = nodes)
    );
  }

  hasChildren = (node: TreeNode) => node.hasChildren;

  fetchChildren = (node: TreeNode): Observable<TreeNode[]> =>
    this.http.get<TreeNode[]>(`/api/tree?parentId=${node.id}`);
}
```

---

### 4. Checkboxes with Tri-State Parent Nodes

```typescript
import { Component } from '@angular/core';
import { KENDO_TREEVIEW } from '@progress/kendo-angular-treeview';
import { CheckableSettings, CheckedState } from '@progress/kendo-angular-treeview';

interface TreeNode { id: number; text: string; children?: TreeNode[] }

@Component({
  standalone: true,
  selector: 'app-treeview-checkboxes',
  imports: [KENDO_TREEVIEW],
  template: `
    <kendo-treeview
      kendoTreeViewHierarchyBinding
      [nodes]="nodes"
      textField="text"
      childrenField="children"
      kendoTreeViewExpandable
      kendoTreeViewCheckable
      [checkable]="checkSettings"
      [checkedKeys]="checkedKeys"
      (checkedChange)="onCheckedChange($event)"
    />
    <p>Checked IDs: {{ checkedKeys.join(', ') }}</p>
  `,
})
export class TreeViewCheckboxComponent {
  nodes: TreeNode[] = [
    {
      text: 'Fruits', id: 1, children: [
        { text: 'Apples',  id: 2 },
        { text: 'Bananas', id: 3 },
        { text: 'Cherries',id: 4 },
      ]
    },
    {
      text: 'Vegetables', id: 5, children: [
        { text: 'Carrots', id: 6 },
        { text: 'Peas',    id: 7 },
      ]
    },
  ];

  checkSettings: CheckableSettings = {
    checkChildren: true,
    checkParents:  true,
    mode: 'multiple',
    checkOnClick: true,
  };

  checkedKeys: number[] = [];

  onCheckedChange({ item, checked }: any) {
    // checkedKeys is updated automatically when checkChildren/checkParents are true
    // This event fires for custom side effects only (e.g. API calls)
    console.log(`Node ${item.dataItem.text} is now ${checked ? 'checked' : 'unchecked'}`);
  }
}
```

---

### 5. Filterable Tree

```typescript
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { KENDO_TREEVIEW } from '@progress/kendo-angular-treeview';

interface TreeNode { id: number; text: string; children?: TreeNode[] }

@Component({
  standalone: true,
  selector: 'app-treeview-filter',
  imports: [KENDO_TREEVIEW, FormsModule],
  template: `
    <kendo-treeview
      kendoTreeViewHierarchyBinding
      [nodes]="nodes"
      textField="text"
      childrenField="children"
      kendoTreeViewExpandable
      [filterable]="true"
      [(filter)]="filterValue"
    />
  `,
})
export class TreeViewFilterComponent {
  filterValue = '';

  nodes: TreeNode[] = [
    {
      text: 'Electronics', id: 1, children: [
        { text: 'Laptops',  id: 2, children: [
          { text: 'Gaming Laptops',    id: 5 },
          { text: 'Business Laptops',  id: 6 },
        ]},
        { text: 'Phones',   id: 3 },
        { text: 'Tablets',  id: 4 },
      ]
    },
    {
      text: 'Furniture', id: 7, children: [
        { text: 'Tables', id: 8 },
        { text: 'Chairs', id: 9 },
      ]
    },
  ];
}
```

> The built-in `[filterable]="true"` renders a filter input above the tree. Nodes that don't match (or have no matching descendants) are hidden. For server-side filtering, bind `[filter]` and listen to `(filterChange)` to call your API.
