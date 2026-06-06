# React + TanStack Reference

Frontend stack: **Vite + React + TanStack Router + TanStack Query + TanStack Form + TanStack Table + TanStack Virtual + Zustand**.

Load this when working on routing, data fetching, forms, mutations, URL state, or client state.

---

## Mental model

- **Server state** (anything from FastAPI): TanStack Query. Never `useEffect + fetch`.
- **URL state** (filters, pagination, sort, current view): TanStack Router search params.
- **Client state** (theme, sidebar, modals, auth user): `useState` + Context. Zustand only when syncing across distant components.

If you reach for Zustand for something that belongs in Query or the URL, back out.

---

## TanStack Router — file-based routing

Routes live in `src/routes/`. The `@tanstack/router-plugin` Vite plugin auto-generates `src/routeTree.gen.ts` — do not edit that file.

```
src/routes/
  __root.tsx         # layout wrapper (Outlet + devtools)
  index.tsx          # /
  users.tsx          # /users (can use as parent)
  users/
    index.tsx        # /users
    $userId.tsx      # /users/:userId  ($ = param)
```

### Typed routes

```tsx
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'

export const Route = createFileRoute('/users/$userId')({
  component: UserPage,
})

function UserPage() {
  const { userId } = Route.useParams()          // typed: string
  const navigate = useNavigate()

  return (
    <>
      <Link to="/users/$userId" params={{ userId: '42' }}>View 42</Link>
      <button onClick={() => navigate({ to: '/' })}>Home</button>
    </>
  )
}
```

Typos in `to="..."` or `params` are compile errors. That's the whole selling point.

### Search params (URL state) with Zod validation

```tsx
import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

const searchSchema = z.object({
  page: z.number().int().min(1).default(1),
  q: z.string().default(''),
})

export const Route = createFileRoute('/users/')({
  validateSearch: searchSchema,
  component: UsersList,
})

function UsersList() {
  const { page, q } = Route.useSearch()          // typed + validated
  const navigate = Route.useNavigate()

  return (
    <input
      value={q}
      onChange={(e) => navigate({ search: (s) => ({ ...s, q: e.target.value, page: 1 }) })}
    />
  )
}
```

**Use this for every filter/paginate/sort UI.** Shareable URLs, back-button works, no Zustand needed.

### Loaders + Query integration

```tsx
import { createFileRoute } from '@tanstack/react-router'
import { queryOptions, useSuspenseQuery } from '@tanstack/react-query'
import { api } from '../lib/api'

const userQuery = (id: string) =>
  queryOptions({
    queryKey: ['users', id],
    queryFn: () => api<User>(`/users/${id}`),
  })

export const Route = createFileRoute('/users/$userId')({
  loader: ({ context, params }) =>
    context.queryClient.ensureQueryData(userQuery(params.userId)),
  component: UserPage,
})

function UserPage() {
  const { userId } = Route.useParams()
  const { data } = useSuspenseQuery(userQuery(userId))
  return <h1>{data.name}</h1>
}
```

The loader warms the Query cache during route transition — component renders with data immediately.

---

## TanStack Query patterns

### queryOptions (always prefer over inline)

```ts
// lib/queries.ts
import { queryOptions } from '@tanstack/react-query'
import { api } from './api'

export const usersQuery = queryOptions({
  queryKey: ['users'],
  queryFn: () => api<User[]>('/users'),
})
```

Reuse the same options in loaders, components, and prefetching — one source of truth.

### Mutations + cache invalidation

```tsx
import { useMutation, useQueryClient } from '@tanstack/react-query'

function CreateUser() {
  const qc = useQueryClient()
  const mutation = useMutation({
    mutationFn: (body: NewUser) =>
      api<User>('/users', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })

  return <button onClick={() => mutation.mutate({ name: 'Alice' })}>Create</button>
}
```

### Optimistic updates

```ts
useMutation({
  mutationFn: updateUser,
  onMutate: async (next) => {
    await qc.cancelQueries({ queryKey: ['users', next.id] })
    const prev = qc.getQueryData(['users', next.id])
    qc.setQueryData(['users', next.id], next)
    return { prev }
  },
  onError: (_err, next, ctx) => qc.setQueryData(['users', next.id], ctx?.prev),
  onSettled: (_d, _e, next) => qc.invalidateQueries({ queryKey: ['users', next.id] }),
})
```

### staleTime defaults

Set in `lib/queryClient.ts`. Default `staleTime: 30_000` avoids re-fetching on every mount. Raise to `5 * 60_000` for data that rarely changes (e.g. current user).

---

## Zustand — only when needed

```ts
// src/stores/ui.ts
import { create } from 'zustand'

interface UiStore {
  sidebarOpen: boolean
  toggleSidebar: () => void
}

export const useUiStore = create<UiStore>((set) => ({
  sidebarOpen: false,
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
}))
```

Use via selectors to avoid re-renders:

```tsx
const sidebarOpen = useUiStore((s) => s.sidebarOpen)
const toggleSidebar = useUiStore((s) => s.toggleSidebar)
```

**Do not** put server data, form state, or URL state in Zustand.

---

## TanStack Form

```tsx
import { useForm } from '@tanstack/react-form'
import { useMutation, useQueryClient } from '@tanstack/react-query'

function CreateUserForm() {
  const qc = useQueryClient()
  const mutation = useMutation({
    mutationFn: (body: { name: string }) => api<User>('/users', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })

  const form = useForm({
    defaultValues: { name: '' },
    onSubmit: ({ value }) => mutation.mutate(value),
  })

  return (
    <form onSubmit={(e) => { e.preventDefault(); form.handleSubmit() }}>
      <form.Field
        name="name"
        validators={{ onChange: ({ value }) => !value ? 'Required' : undefined }}
        children={(field) => (
          <>
            <input
              value={field.state.value}
              onChange={(e) => field.handleChange(e.target.value)}
              onBlur={field.handleBlur}
            />
            {field.state.meta.errors[0] && (
              <span className="text-destructive text-sm">{field.state.meta.errors[0]}</span>
            )}
          </>
        )}
      />
      <button type="submit" disabled={mutation.isPending}>Submit</button>
    </form>
  )
}
```

Use shadcn `input`, `label`, `button` primitives for UI — do **not** install react-hook-form.

---

## TanStack Table

```tsx
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  type ColumnDef,
} from '@tanstack/react-table'

const columns: ColumnDef<User>[] = [
  { accessorKey: 'name', header: 'Name' },
  { accessorKey: 'email', header: 'Email' },
]

function UsersTable({ data }: { data: User[] }) {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  return (
    <table>
      <thead>
        {table.getHeaderGroups().map(hg => (
          <tr key={hg.id}>
            {hg.headers.map(h => (
              <th key={h.id} onClick={h.column.getToggleSortingHandler()} className="cursor-pointer">
                {flexRender(h.column.columnDef.header, h.getContext())}
              </th>
            ))}
          </tr>
        ))}
      </thead>
      <tbody>
        {table.getRowModel().rows.map(row => (
          <tr key={row.id}>
            {row.getVisibleCells().map(cell => (
              <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}
```

Table is headless — you own all markup. Style with Tailwind and shadcn tokens.

---

## TanStack Virtual

Use when rendering 100+ rows to avoid DOM bloat:

```tsx
import { useVirtualizer } from '@tanstack/react-virtual'
import { useRef } from 'react'

function VirtualList({ items }: { items: string[] }) {
  const parentRef = useRef<HTMLDivElement>(null)

  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 40,
  })

  return (
    <div ref={parentRef} className="h-96 overflow-auto">
      <div style={{ height: `${virtualizer.getTotalSize()}px`, position: 'relative' }}>
        {virtualizer.getVirtualItems().map(vItem => (
          <div
            key={vItem.key}
            style={{ position: 'absolute', top: 0, transform: `translateY(${vItem.start}px)`, width: '100%' }}
          >
            {items[vItem.index]}
          </div>
        ))}
      </div>
    </div>
  )
}
```

Combine with TanStack Table by passing `table.getRowModel().rows` as items.

---

## Auth (when you add it)

Cookie-based flow: FastAPI sets `Set-Cookie` with `httpOnly + SameSite=Lax`, frontend uses `credentials: 'include'` (already wired in `lib/api.ts`). Store current user in a Query with `queryKey: ['me']`, not in Zustand.

---

## Do / don't quick list

| Do                                               | Don't                                         |
| ------------------------------------------------ | --------------------------------------------- |
| File-based routing (`src/routes/`)               | Manual route registration                     |
| `queryOptions` for every query                    | Inline `useQuery` with duplicated query keys  |
| Zod-validated search params for filters          | Filter state in Zustand or `useState`         |
| `credentials: 'include'` via `lib/api.ts`         | Re-creating fetch wrappers in components      |
| Invalidate queries after mutations                | Manually `setQueryData` without invalidation  |
| `useSuspenseQuery` inside route loaders          | `useQuery` with `enabled` gating              |
| TanStack Form (`useForm` + `form.Field`)         | react-hook-form or uncontrolled forms         |
| TanStack Table (`useReactTable`)                 | Hand-rolled sort/filter/pagination state      |
| TanStack Virtual for 100+ row lists              | Rendering all rows into the DOM               |
