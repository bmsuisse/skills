---
name: kendo-ui-react
plugin: ui
description: >
  KendoReact component library patterns and best practices for React developers.
  Trigger whenever the user works with KendoReact components, imports from
  @progress/kendo-react-*, asks how to set up Grid, Form, DateInputs, Charts,
  or any KendoReact component, asks about theming or licensing, or asks to
  "use Kendo", "add a Kendo grid", "set up KendoReact", or similar.
---

# KendoReact

KendoReact is a modular commercial React component library by Progress Telerik.
Components are split into focused npm packages — install only what you need.

## Installation

### New project (recommended)

```sh
npm i -g @progress/kendo-cli
npx kendo react create vite MyApp   # or nextjs / astro
cd MyApp && npm i && npm run dev
```

### Existing project

Install the component package + a theme:

```sh
npm i @progress/kendo-react-grid @progress/kendo-react-data-tools \
      @progress/kendo-theme-default
```

Import the theme CSS **once** in your app entry point:

```ts
import '@progress/kendo-theme-default/dist/all.css';
```

Available themes: `default`, `bootstrap`, `material`, `fluent`.

## Licensing

KendoReact requires a license key for both development and production.

```sh
npx kendo react setup   # interactive wizard — adds license to project
```

Without a valid key, a banner appears in development and components are
blocked in production. Free tier includes 50+ components; Premium unlocks 120+.

## Package Structure

Each functional area is its own package:

| Package | Components |
|---|---|
| `@progress/kendo-react-grid` | Grid (Data Grid) |
| `@progress/kendo-react-form` | Form, Field, FormElement |
| `@progress/kendo-react-dateinputs` | DatePicker, DateRangePicker, TimePicker |
| `@progress/kendo-react-charts` | Chart, Sparkline, StockChart |
| `@progress/kendo-react-inputs` | Input, TextArea, NumericTextBox, Slider |
| `@progress/kendo-react-dropdowns` | DropDownList, ComboBox, MultiSelect |
| `@progress/kendo-react-buttons` | Button, ButtonGroup, ToolBar |
| `@progress/kendo-react-dialogs` | Dialog, Window |
| `@progress/kendo-react-upload` | Upload |

## Data Grid

The Grid is the most-used component. Columns are declarative children.

```tsx
import { Grid, GridColumn } from '@progress/kendo-react-grid';

const data = [
  { id: 1, name: 'Alice', role: 'Admin' },
  { id: 2, name: 'Bob',   role: 'User'  },
];

export function UserGrid() {
  return (
    <Grid data={data} style={{ height: '400px' }}>
      <GridColumn field="id"   title="ID"   width="60px" />
      <GridColumn field="name" title="Name" />
      <GridColumn field="role" title="Role" />
    </Grid>
  );
}
```

### Sorting, filtering, paging

Use controlled state + `onDataStateChange`:

```tsx
import { useState } from 'react';
import { Grid, GridColumn } from '@progress/kendo-react-grid';
import { process, State } from '@progress/kendo-data-query';

export function UserGrid({ data }: { data: User[] }) {
  const [dataState, setDataState] = useState<State>({
    take: 10, skip: 0,
    sort: [{ field: 'name', dir: 'asc' }],
  });

  return (
    <Grid
      data={process(data, dataState)}
      {...dataState}
      sortable filterable pageable
      onDataStateChange={e => setDataState(e.dataState)}
    >
      <GridColumn field="name" title="Name" />
      <GridColumn field="role" title="Role" />
    </Grid>
  );
}
```

### Row virtualization (large datasets)

```tsx
<Grid data={data} rowHeight={36} style={{ height: '600px' }}>
```

### RSC / Next.js

For React Server Components, use the RSC-compatible package variant and
keep interactive Grid features client-side (`'use client'`).

## Forms

```tsx
import { Form, Field, FormElement } from '@progress/kendo-react-form';
import { Input } from '@progress/kendo-react-inputs';

const emailValidator = (v: string) =>
  /\S+@\S+\.\S+/.test(v) ? '' : 'Invalid email';

export function ContactForm() {
  return (
    <Form
      onSubmit={values => console.log(values)}
      render={({ allowSubmit }) => (
        <FormElement>
          <Field name="email" label="Email" component={Input} validator={emailValidator} />
          <button type="submit" disabled={!allowSubmit}>Submit</button>
        </FormElement>
      )}
    />
  );
}
```

Validators return `''` for valid, or an error string for invalid.
`allowSubmit` from `formRenderProps` gates the submit button.

## Theming & Customization

### CSS variables (quick overrides)

```css
:root {
  --kendo-color-primary: #0052cc;
  --kendo-border-radius-md: 4px;
}
```

### SASS (full control)

```sh
npm i @progress/kendo-theme-default   # includes SCSS source
```

```scss
$kendo-color-primary: #0052cc;
@use '@progress/kendo-theme-default/scss/index.scss';
```

### Theme switching at runtime

Swap the CSS import dynamically or use `data-kendo-theme` attribute on `<html>`.

## Common Pitfalls

**Missing theme import** — Components render unstyled. Always import one theme CSS globally.

**License banner in dev** — Run `npx kendo react setup` or set `KENDO_LICENSE_KEY` env var.

**Grid height required** — Without an explicit `style={{ height }}`, the Grid collapses. Always set a height.

**`process()` required for features** — Sorting/filtering/paging only works when you pipe data through `process(data, dataState)` from `@progress/kendo-data-query`.

**Peer deps** — All packages require React 18+. Check peer dep warnings on install.

**SSR / Next.js** — Most components are client-side only. Add `'use client'` at the top of any file using KendoReact components.

## References

- Getting started: https://www.telerik.com/kendo-react-ui/components/getting-started
- Component docs: https://www.telerik.com/kendo-react-ui/components/
- Theming: https://www.telerik.com/kendo-react-ui/components/styling/
- Data query: https://www.telerik.com/kendo-react-ui/components/dataquery/
- Licensing: https://www.telerik.com/kendo-react-ui/components/my-license/

Load `references/references.md` for a full list of official KendoReact doc links (Grid, Form, theming, licensing, getting started, and more) when you need deeper API detail or want to point the user to the right page.
