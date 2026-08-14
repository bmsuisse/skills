# UI Components Reference

Primary source: **[`@bmsuisse/ui`](https://github.com/bmsuisse/bmsui/tree/main/packages/ui)**
(base primitives + composed patterns) and
**[`@bmsuisse/datagrid`](https://github.com/bmsuisse/bmsui/tree/main/packages/datagrid)**
(`<DataGrid>`, `<TreeDataGrid>`) — real npm dependencies published publicly
from the [bmsuisse/bmsui](https://github.com/bmsuisse/bmsui) monorepo, built
from the same shadcn/ui + Radix foundation this scaffold used to generate
locally. Fallback: the **shadcn CLI**, kept wired up (`components.json`,
theme CSS, the shadcn runtime deps) for anything `@bmsuisse/ui` doesn't cover.

Load this when adding UI components, wiring a data table, theming, dark mode,
or debugging class merge / unstyled-component issues.

---

## Mental model

- `@bmsuisse/ui` and `@bmsuisse/datagrid` are ordinary public npm dependencies
  (see `frontend/package.json`), not copy-pasted source — you don't own this
  code, you consume it like any other library. They're published from
  [bmsuisse/bmsui](https://github.com/bmsuisse/bmsui) to the public npm
  registry, so `bun add @bmsuisse/ui @bmsuisse/datagrid` just works — no
  registry scoping, feed credentials, or `.npmrc` setup needed.
- `components.json` still exists and the shadcn CLI still works — it's the
  fallback for anything `@bmsuisse/ui` doesn't ship (see "What's covered" below).
  Anything you pull down that way *is* copy-pasted source you own, same as
  before — it lands in `src/components/ui/` and you edit it freely.
- Both packages are styled via the same Tailwind v4 semantic tokens
  (`bg-background`, `text-foreground`, …) the scaffold's `src/index.css`
  already defines — same OKLCH theme vars, same `new-york`/neutral shadcn
  base. You don't need to reconcile two token systems.

---

## What's covered by `@bmsuisse/ui` / `@bmsuisse/datagrid`

`@bmsuisse/ui`'s full public surface (`import { ... } from '@bmsuisse/ui'`):

- **Primitives**: `Button`, `Input`, `Label`, `Textarea`, `Card` (+
  `CardHeader`/`CardTitle`/`CardDescription`/`CardContent`/`CardFooter`),
  `Badge`, `Dialog`, `Popover`, `Select`, `Skeleton`, `Checkbox`, `Switch`,
  `Tabs`, `Separator`, `ScrollArea`/`ScrollBar`, `Table` (+ `TableHeader`/
  `TableBody`/`TableRow`/`TableHead`/`TableCell`/`TableCaption`/`TableFooter`),
  `DropdownMenu`, `Sheet`, `Tooltip`
- **Patterns** (composed on top of the primitives): `Modal`, `ConfirmDialog`,
  `FormModal`, `FormField` (label + input + error/description wrapper),
  `Combobox` (searchable single-select), `AlertBox` (error/warning/info/
  success banner), `StatusBadge` (status string → color badge),
  `LoadingSpinner` / `LoadingOverlay`
- **Utility**: `cn` (also available locally from `@/lib/utils` — see below)

`@bmsuisse/datagrid`'s `<DataGrid>` (TanStack Table v9 under the hood, client
and server modes, per-column-type default filter widgets, `<ColumnSelector>`,
row/header action menus) and `<TreeDataGrid>` (lazy-loading hierarchies)
cover tables end to end — **use `<DataGrid>` instead of hand-rolling
`useReactTable`** for any list/table UI; see
[`tanstack-best-practices`](../../tanstack-best-practices/) and
[bmsui's `AGENTS.md`](https://github.com/bmsuisse/bmsui/blob/main/AGENTS.md)
(linked from that package's README) for the full `ColumnDef`/`GridState`
contract.

**Not covered — use the shadcn CLI fallback for these**: RadioGroup,
Accordion, Avatar, Progress, Calendar/date-picker (standalone — `<DataGrid>`
has one internally for its date-range filter, but it isn't exported),
Command, Toast/Sonner. Check `@bmsuisse/ui`'s actual export list (its
[`src/index.ts`](https://github.com/bmsuisse/bmsui/blob/main/packages/ui/src/index.ts),
or just try the import) before assuming something is missing — the list
above reflects `@bmsuisse/ui@0.4.6` and will grow.

---

## Adding a component that's already in `@bmsuisse/ui`

```tsx
import { Button, Card, CardContent, Input, Label } from '@bmsuisse/ui'

export function Save() {
  return (
    <Card>
      <CardContent className="flex flex-col gap-2">
        <Label htmlFor="name">Name</Label>
        <Input id="name" />
        <Button>Save</Button>
      </CardContent>
    </Card>
  )
}
```

No `add` step, no generated file — it's just an import, like any other
dependency.

## Adding a component that's NOT in `@bmsuisse/ui` (shadcn CLI fallback)

```bash
cd frontend
bunx --bun shadcn@latest add tabs
bunx --bun shadcn@latest add tooltip switch
```

Files land under `src/components/ui/` — same as the old default flow. Import
with the `@/` alias:

```tsx
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
```

**Do not** re-add something `@bmsuisse/ui` already exports via the shadcn CLI
(e.g. `bunx shadcn add button`) — that creates a second, divergent copy of a
component that already exists as a shared dependency. Check the "What's
covered" list above first.

---

## Theme tokens (always prefer these)

| Token                        | Use for                              |
| ----------------------------- | ------------------------------------ |
| `bg-background`              | App/page background                  |
| `text-foreground`            | Primary text                         |
| `text-muted-foreground`      | Secondary text, captions, hints      |
| `bg-card text-card-foreground` | Card surfaces                      |
| `bg-primary text-primary-foreground` | Primary actions (buttons, links) |
| `bg-secondary text-secondary-foreground` | Secondary actions           |
| `bg-muted`                   | Subtle surfaces (input bg, inactive tabs) |
| `bg-accent text-accent-foreground` | Hover states                   |
| `bg-destructive`             | Destructive buttons, error banners   |
| `border-border`              | Borders, dividers                    |
| `ring-ring`                  | Focus rings                          |

**Do not use** raw palette classes like `bg-neutral-800`, `text-gray-500`,
`bg-zinc-50` — they break theming and dark mode. `@bmsuisse/ui`'s components
already follow this; match it in your own code.

---

## Dark mode

Scaffold already defines `.dark` variants in `src/index.css` and registers
`@custom-variant dark (&:is(.dark *))`. Activate by toggling
`className="dark"` on `<html>`. `@bmsuisse/ui`/`@bmsuisse/datagrid` components
respond to the same `.dark` class — no separate dark-mode wiring needed for
them.

Minimal theme toggle:

```tsx
// src/components/theme-toggle.tsx
import { Moon, Sun } from 'lucide-react'
import { Button } from '@bmsuisse/ui'

export function ThemeToggle() {
  const toggle = () => document.documentElement.classList.toggle('dark')
  return (
    <Button variant="ghost" size="icon" onClick={toggle}>
      <Sun className="h-4 w-4 dark:hidden" />
      <Moon className="hidden h-4 w-4 dark:block" />
    </Button>
  )
}
```

Persist across reloads by reading/writing `localStorage` in a `useEffect` on
the root route.

---

## The `cn()` helper

`@bmsuisse/ui` exports its own `cn`, and the scaffold still writes a local
`@/lib/utils` with an identical implementation:

```ts
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

Both exist because the shadcn CLI fallback generates files that
unconditionally import `cn` from `@/lib/utils` (that's what `components.json`
tells it to do) — keeping the local copy means fallback components work
without extra wiring. Use either in your own code; they're functionally
identical. Don't remove `@/lib/utils`'s `cn` even if you never touch the
shadcn CLI — it's load-bearing for `components.json`'s `"utils"` alias.

```tsx
<div className={cn(
  'rounded-lg border p-4',
  isActive && 'border-primary bg-primary/5',
  className,   // prop override — goes last so it wins
)} />
```

---

## Icons — two libraries, two purposes

- **`lucide-react`** — internal to `@bmsuisse/ui`/`@bmsuisse/datagrid`'s components
  and to anything the shadcn CLI generates. It's a byproduct of the
  shadcn/Radix foundation, not a choice you make per app. Don't reach for it
  in your own components.
- **`@heroicons/react`** (`24/outline`) — the icon library for everything you
  place yourself: nav items, page/business icons, empty states. Import by
  name:

  ```tsx
  import { HomeIcon, UsersIcon } from '@heroicons/react/24/outline'

  <HomeIcon className="h-[18px] w-[18px]" />
  ```

For a BMS app's nav and common concepts (dashboard, customers, contracts,
approvals, settings, ...), use the curated concept-to-icon mapping in the
`bms-frontend-design` skill's [`references/icons.md`](../../bms-frontend-design/references/icons.md)
instead of picking a lookalike icon per app.

---

## Building your own components

Follow the same pattern `@bmsuisse/ui`'s own components use:

```tsx
// src/components/empty-state.tsx
import { cn } from '@/lib/utils'
import type { ReactNode } from 'react'

interface EmptyStateProps {
  title: string
  description?: string
  action?: ReactNode
  className?: string
}

export function EmptyState({ title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed p-12 text-center', className)}>
      <h3 className="text-lg font-medium">{title}</h3>
      {description && <p className="text-sm text-muted-foreground">{description}</p>}
      {action}
    </div>
  )
}
```

Rules:
- Accept `className`, pass through `cn(base, className)` with the prop
  **last** so overrides win.
- Use semantic tokens, never raw palette colors.
- Don't install a competing component library (MUI, Chakra, Mantine, Ant,
  HeroUI). If neither `@bmsuisse/ui` nor the shadcn CLI covers what you need,
  build it with the primitives (`@radix-ui/react-*` — both are built on
  these; you can add more directly).
- If what you're building is a genuinely reusable BMS-wide pattern (not
  specific to this app), consider contributing it to `@bmsuisse/ui` instead of
  duplicating it per project — that's the whole reason the package exists.
  See [bmsui's `AGENTS.md`](https://github.com/bmsuisse/bmsui/blob/main/AGENTS.md)
  for the survey that produced the current pattern set and the reasoning
  behind each one.

---

## When it breaks

- **Components render with no styling at all (correct DOM structure, no
  Tailwind classes applied)**: `frontend/src/index.css` is missing the
  `@source` lines for `@bmsuisse/ui`/`@bmsuisse/datagrid`. Tailwind v4 does not
  scan `node_modules` by default — `@bmsuisse/ui` and `@bmsuisse/datagrid` ship
  compiled JS with Tailwind class names baked into JSX, so without an
  explicit `@source "../node_modules/@bmsuisse/ui/dist/**/*.js";` (and the same
  for `@bmsuisse/datagrid`) those classes never make it into the generated CSS.
  The scaffold writes both lines by default — check they weren't deleted.
- **Install fails / package not found**: `@bmsuisse/ui` and `@bmsuisse/datagrid`
  are public npm packages — no `.npmrc` scoping or feed auth needed. A failed
  install usually means a typo'd name/version or a stale bun lockfile; try
  `bun add @bmsuisse/ui@latest @bmsuisse/datagrid@latest`.
- **`Cannot find module '@/components/ui/...'`**: path alias not wired
  (only relevant to shadcn-CLI-added fallback components). Check
  `vite.config.ts` has `resolve.alias['@']`, `tsconfig.json` and
  `tsconfig.app.json` both have `"paths": { "@/*": ["./src/*"] }`.
- **Dark mode classes not applying**: missing
  `@custom-variant dark (&:is(.dark *));` in `index.css`, or `.dark` class
  not on `<html>`.
- **`twMerge` not resolving correctly**: you're using arbitrary values that
  conflict (e.g. `p-[13px] p-4`). Use standard scale classes when possible.
- **`tw-animate-css` errors on install**: confirm you're on Tailwind v4 —
  `tw-animate-css` is the v4 replacement for the old `tailwindcss-animate`
  PostCSS plugin and requires v4.
