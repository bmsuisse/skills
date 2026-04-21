---
title: KendoReact
description: KendoReact component patterns — Grid, Form, theming, licensing, and common pitfalls.
---

# KendoReact

**Skill:** `kendo-ui-react` · **Plugin:** `ui@bmsuisse-skills`

## Installation

```bash
npm i @progress/kendo-react-grid @progress/kendo-theme-default
```

Import the theme **once** in your entry point:

```ts
import '@progress/kendo-theme-default/dist/all.css';
```

## Licensing

```bash
npx kendo react setup   # adds license key to project
```

Without a valid key: banner in dev, blocked in production.

## Data Grid

```tsx
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
            style={{ height: '400px' }}
        >
            <GridColumn field="name" title="Name" />
            <GridColumn field="role" title="Role" />
        </Grid>
    );
}
```

**Always set `style={{ height }}`** — without it the Grid collapses.

**Always pipe through `process(data, dataState)`** from `@progress/kendo-data-query` — sorting/filtering/paging won't work otherwise.

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
                    <Field name="email" component={Input} validator={emailValidator} />
                    <button type="submit" disabled={!allowSubmit}>Submit</button>
                </FormElement>
            )}
        />
    );
}
```

Validators return `''` for valid, error string for invalid.

## Theming

```css
/* Quick override via CSS variables */
:root {
    --kendo-color-primary: #0052cc;
}
```

```scss
/* Full control via SASS */
$kendo-color-primary: #0052cc;
@use '@progress/kendo-theme-default/scss/index.scss';
```

Available themes: `default`, `bootstrap`, `material`, `fluent`.

## Common pitfalls

| Problem | Fix |
|---|---|
| Components render unstyled | Import a theme CSS globally |
| License banner in dev | Run `npx kendo react setup` |
| Grid collapses | Set `style={{ height: '400px' }}` |
| Sorting/filtering not working | Pipe data through `process(data, dataState)` |
| Errors in Next.js | Add `'use client'` to files using KendoReact |
