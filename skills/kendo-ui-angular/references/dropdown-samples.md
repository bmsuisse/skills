# Kendo UI for Angular — DropDownList & AutoComplete Samples

Both components come from `@progress/kendo-angular-dropdowns`.

---

## Choosing the Right Component

| Component | Token | Use when |
|---|---|---|
| `kendo-dropdownlist` | `KENDO_DROPDOWNLIST` | User must pick from a predefined list; free-text not allowed |
| `kendo-autocomplete` | `KENDO_AUTOCOMPLETE` | User types freely; list provides search suggestions only |
| `kendo-combobox`     | `KENDO_COMBOBOX`     | Either: pick from list OR enter a custom value |

---

## DropDownList

### 1. Basic — Static List with ngModel

```typescript
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { KENDO_DROPDOWNLIST } from '@progress/kendo-angular-dropdowns';

interface Category { text: string; value: number }

@Component({
  standalone: true,
  selector: 'app-dropdown-basic',
  imports: [KENDO_DROPDOWNLIST, FormsModule],
  template: `
    <kendo-dropdownlist
      [data]="categories"
      textField="text"
      valueField="value"
      [(ngModel)]="selected"
      [defaultItem]="{ text: 'Select a category…', value: null }"
      style="width: 280px"
      (selectionChange)="onSelect($event)"
    />
    <p *ngIf="selected">Selected value: {{ selected.value }}</p>
  `,
})
export class DropDownBasicComponent {
  categories: Category[] = [
    { text: 'Electronics', value: 1 },
    { text: 'Clothing',    value: 2 },
    { text: 'Food',        value: 3 },
    { text: 'Books',       value: 4 },
  ];

  selected: Category | null = null;

  onSelect(item: Category) {
    console.log('Selected:', item);
  }
}
```

---

### 2. Reactive Forms with Typed FormControl

```typescript
import { Component } from '@angular/core';
import { ReactiveFormsModule, FormControl } from '@angular/forms';
import { NgIf } from '@angular/common';
import { KENDO_DROPDOWNLIST } from '@progress/kendo-angular-dropdowns';

interface Country { name: string; code: string }

@Component({
  standalone: true,
  selector: 'app-dropdown-reactive',
  imports: [KENDO_DROPDOWNLIST, ReactiveFormsModule, NgIf],
  template: `
    <form (ngSubmit)="onSubmit()">
      <kendo-dropdownlist
        [formControl]="countryControl"
        [data]="countries"
        textField="name"
        valueField="code"
        [valuePrimitive]="true"
        placeholder="Select country"
        style="width: 280px"
      />
      <p *ngIf="countryControl.value">Selected code: {{ countryControl.value }}</p>
      <button type="submit" [disabled]="countryControl.invalid">Submit</button>
    </form>
  `,
})
export class DropDownReactiveComponent {
  // valuePrimitive:true means the formControl holds the valueField string, not the whole object
  countryControl = new FormControl<string | null>(null);

  countries: Country[] = [
    { name: 'Switzerland', code: 'CH' },
    { name: 'Germany',     code: 'DE' },
    { name: 'Austria',     code: 'AT' },
    { name: 'France',      code: 'FR' },
    { name: 'Italy',       code: 'IT' },
  ];

  onSubmit() {
    console.log('Country code:', this.countryControl.value);
  }
}
```

> **`[valuePrimitive]`**: when `true`, `ngModel` / `formControl` holds the primitive `valueField` value (string/number); when `false` (default), it holds the full object. Set to `true` when you only need the ID for API calls.

---

### 3. Server-Side Filtering

Use when the list has thousands of items. Only load matching items from the API as the user types.

```typescript
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { AsyncPipe, NgIf } from '@angular/common';
import { BehaviorSubject, Observable, switchMap, debounceTime, distinctUntilChanged } from 'rxjs';
import { KENDO_DROPDOWNLIST } from '@progress/kendo-angular-dropdowns';

interface Product { id: number; name: string }

@Component({
  standalone: true,
  selector: 'app-dropdown-server',
  imports: [KENDO_DROPDOWNLIST, FormsModule, AsyncPipe, NgIf],
  template: `
    <kendo-dropdownlist
      [data]="products$ | async"
      textField="name"
      valueField="id"
      [(ngModel)]="selected"
      [filterable]="true"
      [loading]="loading"
      style="width: 300px"
      (filterChange)="onFilterChange($event)"
    />
  `,
})
export class DropDownServerComponent {
  selected: Product | null = null;
  loading = false;

  private filter$ = new BehaviorSubject<string>('');

  products$: Observable<Product[]> = this.filter$.pipe(
    debounceTime(300),
    distinctUntilChanged(),
    switchMap(term => {
      this.loading = true;
      return this.http.get<Product[]>(`/api/products/search?q=${encodeURIComponent(term)}`);
    }),
  );

  constructor(private http: HttpClient) {}

  onFilterChange(term: string) {
    this.loading = true;
    this.filter$.next(term);
  }
}
```

---

## AutoComplete

### 1. Basic — String Array with Suggestions

```typescript
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { KENDO_AUTOCOMPLETE } from '@progress/kendo-angular-dropdowns';

@Component({
  standalone: true,
  selector: 'app-autocomplete-basic',
  imports: [KENDO_AUTOCOMPLETE, FormsModule],
  template: `
    <kendo-autocomplete
      [data]="suggestions"
      [(ngModel)]="value"
      placeholder="Type a country…"
      [suggest]="true"
      style="width: 280px"
      (filterChange)="onFilter($event)"
      (valueChange)="onValueChange($event)"
    />
    <p *ngIf="value">Value: {{ value }}</p>
  `,
})
export class AutoCompleteBasicComponent {
  private all = [
    'Austria', 'Albania', 'Belgium', 'Bulgaria',
    'Croatia', 'Cyprus', 'Denmark', 'Estonia',
    'Finland', 'France', 'Germany', 'Greece',
  ];

  suggestions = [...this.all];
  value = '';

  onFilter(term: string) {
    const q = term.toLowerCase();
    this.suggestions = q.length >= 2
      ? this.all.filter(c => c.toLowerCase().startsWith(q))
      : [...this.all];
  }

  onValueChange(val: string) {
    console.log('Committed value:', val);
  }
}
```

> **`[suggest]="true"`** auto-completes the text input with the first suggestion as the user types. The bound value stays a plain string — the user can commit any value, not just items from the list.

---

### 2. Object Data — Display Name, Bind ID

When suggestions are objects but you want the value to be a string field from the object:

```typescript
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { KENDO_AUTOCOMPLETE } from '@progress/kendo-angular-dropdowns';

interface User { id: number; fullName: string; email: string }

@Component({
  standalone: true,
  selector: 'app-autocomplete-objects',
  imports: [KENDO_AUTOCOMPLETE, FormsModule],
  template: `
    <kendo-autocomplete
      [data]="suggestions"
      valueField="fullName"
      [(ngModel)]="selectedName"
      placeholder="Search by name…"
      style="width: 300px"
      (filterChange)="onFilter($event)"
    />
    <p *ngIf="selectedUser">Email: {{ selectedUser.email }}</p>
  `,
})
export class AutoCompleteObjectsComponent {
  private allUsers: User[] = [
    { id: 1, fullName: 'Alice Johnson',  email: 'alice@example.com'  },
    { id: 2, fullName: 'Alex Brown',     email: 'alex@example.com'   },
    { id: 3, fullName: 'Andrew Davis',   email: 'andrew@example.com' },
    { id: 4, fullName: 'Betty White',    email: 'betty@example.com'  },
  ];

  suggestions: User[] = [...this.allUsers];
  selectedName = '';

  get selectedUser(): User | undefined {
    return this.allUsers.find(u => u.fullName === this.selectedName);
  }

  onFilter(term: string) {
    const q = term.toLowerCase();
    this.suggestions = q
      ? this.allUsers.filter(u => u.fullName.toLowerCase().includes(q))
      : [...this.allUsers];
  }
}
```

---

### 3. Async Remote Search

Debounce filter changes and fetch from an API. Use `[loading]` to show a spinner while the request is in flight.

```typescript
import { Component, ChangeDetectionStrategy, ChangeDetectorRef } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Subject, switchMap, debounceTime, distinctUntilChanged } from 'rxjs';
import { KENDO_AUTOCOMPLETE } from '@progress/kendo-angular-dropdowns';

@Component({
  standalone: true,
  selector: 'app-autocomplete-async',
  imports: [KENDO_AUTOCOMPLETE, FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <kendo-autocomplete
      [data]="results"
      [(ngModel)]="value"
      placeholder="Search products…"
      [loading]="loading"
      [suggest]="false"
      style="width: 300px"
      (filterChange)="onFilter($event)"
    />
  `,
})
export class AutoCompleteAsyncComponent {
  value = '';
  results: string[] = [];
  loading = false;

  private filter$ = new Subject<string>();

  constructor(private http: HttpClient, private cdr: ChangeDetectorRef) {
    this.filter$
      .pipe(
        debounceTime(300),
        distinctUntilChanged(),
        switchMap(term => {
          this.loading = true;
          this.cdr.markForCheck();
          return this.http.get<{ name: string }[]>(
            `/api/products/search?q=${encodeURIComponent(term)}`
          );
        })
      )
      .subscribe(items => {
        this.results  = items.map(i => i.name);
        this.loading  = false;
        this.cdr.markForCheck();
      });
  }

  onFilter(term: string) {
    if (term.length >= 2) {
      this.filter$.next(term);
    } else {
      this.results = [];
    }
  }
}
```

> **Minimum filter length**: guard with `term.length >= 2` (or your preferred threshold) to avoid firing a server request on every single keystroke from an empty field.
