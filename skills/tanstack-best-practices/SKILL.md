---
name: tanstack-best-practices
description: >
  Comprehensive best practices for TanStack libraries in React applications — covering TanStack Query (React Query) data fetching, caching, and mutations; TanStack Router type-safe routing and search params; TanStack Query + Router integration patterns; TypeScript usage; and common pitfalls to avoid.

  Use this skill whenever someone is: building data fetching logic or server state management with TanStack Query / React Query; setting up or refactoring routing with TanStack Router; integrating Query with Router in loaders; asking about staleTime, cache invalidation, query key factories, optimistic updates, search params, suspense patterns, SSR hydration, or prefetching. Also trigger when the user writes useQuery, useMutation, useNavigate, createFileRoute, createRootRouteWithContext, queryOptions, or ensureQueryData.
---

# TanStack Best Practices for React

Comprehensive patterns for TanStack Query, TanStack Router, and their integration. Each section is organized by priority so you can focus on what matters most first.

---

## TanStack Query

### Query Keys (CRITICAL)

**Always use arrays, include all dependencies.**

```tsx
// Bad: string key, missing dependency
useQuery({ queryKey: 'todos', queryFn: fetchTodos })
useQuery({ queryKey: ['todos'], queryFn: () => fetchTodo(id) }) // id missing!

// Good
useQuery({ queryKey: ['todos', { status: 'active' }], queryFn: () => fetchTodos({ status: 'active' }) })
useQuery({ queryKey: ['todo', id], queryFn: () => fetchTodo(id) })
```

**Use query key factories for applications with many query types.** Centralizing key definitions prevents typos, enables autocomplete, and makes invalidation predictable.

```tsx
// lib/query-keys.ts
export const todoKeys = {
  all: ['todos'] as const,
  lists: () => [...todoKeys.all, 'list'] as const,
  list: (filters: TodoFilters) => [...todoKeys.lists(), filters] as const,
  details: () => [...todoKeys.all, 'detail'] as const,
  detail: (id: number) => [...todoKeys.details(), id] as const,
  comments: (id: number) => [...todoKeys.detail(id), 'comments'] as const,
}

// Invalidation becomes safe and predictable:
queryClient.invalidateQueries({ queryKey: todoKeys.all })         // everything
queryClient.invalidateQueries({ queryKey: todoKeys.detail(5) })   // one todo + its comments
```

**Combine with `queryOptions` for full type safety and reuse across loaders + components:**

```tsx
import { queryOptions } from '@tanstack/react-query'

export const todoQueries = {
  list: (filters: TodoFilters) => queryOptions({
    queryKey: todoKeys.list(filters),
    queryFn: () => fetchTodos(filters),
    staleTime: 2 * 60 * 1000,
  }),
  detail: (id: number) => queryOptions({
    queryKey: todoKeys.detail(id),
    queryFn: () => fetchTodo(id),
    staleTime: 5 * 60 * 1000,
  }),
}

// Same options object used in component and in router loader:
const { data } = useQuery(todoQueries.detail(5))
await queryClient.ensureQueryData(todoQueries.detail(5))
```

---

### Caching (CRITICAL)

**Set `staleTime` based on how often your data actually changes.** The default of 0ms means every component mount triggers a background refetch — usually too aggressive.

| Data type | staleTime |
|-----------|-----------|
| Real-time (live feeds, stock prices) | 0 |
| Frequently changing (notifications) | 30s – 1min |
| User-generated content | 1 – 5min |
| Reference / config data | 10 – 30min |
| Static content | `Infinity` |

```tsx
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60 * 1000, // 1 minute default; override per-query as needed
    },
  },
})
```

**Pitfall — `staleTime: Infinity` without manual invalidation.** If you set Infinity you must call `invalidateQueries` after mutations, otherwise the UI never refreshes.

**Use targeted invalidation, not broad patterns:**

```tsx
// Bad: invalidates everything, causes unnecessary refetches
queryClient.invalidateQueries()

// Good: only what changed
queryClient.invalidateQueries({ queryKey: todoKeys.list() })
```

**Understand `placeholderData` vs `initialData`:**
- `initialData` is treated as fresh cache data — it populates the cache and respects `staleTime`.
- `placeholderData` is never cached; it only provides a temporary value while loading. Use `placeholderData: keepPreviousData` for smooth pagination.

---

### Mutations (HIGH)

**Always invalidate related queries after a successful mutation:**

```tsx
const mutation = useMutation({
  mutationFn: createTodo,
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: todoKeys.lists() })
  },
})
```

**Implement optimistic updates for instant UI feedback.** The pattern: cancel outgoing refetches → snapshot old data → set optimistic value → return context for rollback.

```tsx
const mutation = useMutation({
  mutationFn: toggleTodoComplete,
  onMutate: async (todoId) => {
    await queryClient.cancelQueries({ queryKey: todoKeys.lists() })
    const previousTodos = queryClient.getQueryData(todoKeys.list({}))

    queryClient.setQueryData(todoKeys.list({}), (old: Todo[]) =>
      old.map(t => t.id === todoId ? { ...t, completed: !t.completed } : t)
    )
    return { previousTodos }
  },
  onError: (_err, _id, context) => {
    queryClient.setQueryData(todoKeys.list({}), context?.previousTodos)
  },
  onSettled: () => {
    queryClient.invalidateQueries({ queryKey: todoKeys.lists() })
  },
})
```

For simple single-component toggles you can skip cache manipulation and use `mutation.isPending` to show the optimistic state directly in the UI — less code and still responsive.

**Use `isPending` (not deprecated `isLoading`) for mutation loading states.** Use `useMutationState` to observe mutation state across components without prop drilling.

---

### Error Handling (HIGH)

**Pair `useSuspenseQuery` with error boundaries + `useQueryErrorResetBoundary`.** Without resetting the query, the "Try again" button has no effect.

```tsx
import { useQueryErrorResetBoundary } from '@tanstack/react-query'
import { ErrorBoundary } from 'react-error-boundary'

function QueryErrorBoundary({ children }: { children: React.ReactNode }) {
  const { reset } = useQueryErrorResetBoundary()
  return (
    <ErrorBoundary
      onReset={reset}
      fallbackRender={({ error, resetErrorBoundary }) => (
        <div>
          <p>Something went wrong: {error.message}</p>
          <button onClick={resetErrorBoundary}>Try again</button>
        </div>
      )}
    >
      {children}
    </ErrorBoundary>
  )
}

// Usage
<QueryErrorBoundary>
  <Suspense fallback={<Skeleton />}>
    <PostList />
  </Suspense>
</QueryErrorBoundary>
```

Place boundaries granularly so one failing section does not break the entire page.

**Configure `retry` appropriately.** The default of 3 retries is fine for transient failures, but retrying 4xx errors wastes time. Inspect the error status:

```tsx
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        if (error.status === 404 || error.status === 403) return false
        return failureCount < 3
      },
    },
  },
})
```

---

### Performance (LOW – HIGH value for large lists)

**Use `select` to transform/filter data outside the component.** The selector is memoized and only re-runs when the underlying data changes, preventing unnecessary renders.

```tsx
// Bad: filtering inside component runs on every render
const { data: todos } = useQuery({ queryKey: todoKeys.lists(), queryFn: fetchTodos })
const completed = todos?.filter(t => t.completed) ?? []

// Good: runs only when todos data changes
const { data: completed } = useQuery({
  queryKey: todoKeys.lists(),
  queryFn: fetchTodos,
  select: (todos) => todos.filter(t => t.completed),
})
```

When the selector depends on a prop or state, stabilize it with `useCallback` to avoid breaking memoization.

**Use `useQueries` for dynamic parallel queries** instead of calling `useQuery` in a loop.

**Use `placeholderData: keepPreviousData`** during pagination to avoid flickering while the next page loads.

---

## TanStack Router

### Type Safety (CRITICAL)

**Register the router globally** so all hooks (`useParams`, `useSearch`, `useNavigate`) are fully typed:

```tsx
// router.tsx
declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
```

**Use `Route.useParams()` and `Route.useSearch()` instead of the generic hooks** when you know which route you're on. They give narrower, more accurate types.

**Define route params with type constraints in `createFileRoute`:**

```tsx
export const Route = createFileRoute('/users/$userId')({
  parseParams: (params) => ({ userId: Number(params.userId) }),
  stringifyParams: ({ userId }) => ({ userId: String(userId) }),
  component: UserPage,
})
```

---

### Route Organization (CRITICAL)

**Use file-based routing** (`createFileRoute`) — TanStack Router's code generator produces a typed route tree (`routeTree.gen.ts`) that makes the whole router type-safe end-to-end.

File name conventions:
- `routes/index.tsx` → `/`
- `routes/posts.tsx` → `/posts`
- `routes/posts/$postId.tsx` → `/posts/$postId`
- `routes/posts/$postId.lazy.tsx` → lazy-loaded detail page
- `routes/_layout.tsx` → layout route (underscore prefix = pathless layout)

**Keep route files thin** — move business logic to custom hooks or query option factories. Route files should mainly declare the route, loader, and component.

---

### Data Loading (HIGH)

**Use `queryClient.ensureQueryData()` in loaders, not `prefetchQuery` or direct fetch calls.**

- `prefetchQuery` never throws and swallows errors — your error boundary won't fire.
- Direct fetch calls bypass the cache entirely.
- `ensureQueryData` returns fresh cached data if available, fetches otherwise, and throws on error.

```tsx
export const Route = createFileRoute('/posts')({
  loader: async ({ context: { queryClient } }) => {
    await queryClient.ensureQueryData(postQueries.list())
  },
  component: PostsPage,
})

function PostsPage() {
  // Data is guaranteed to be in cache; Suspense not needed here
  const { data } = useSuspenseQuery(postQueries.list())
  return <PostList posts={data} />
}
```

**For parallel independent loads:**

```tsx
loader: async ({ context: { queryClient } }) => {
  await Promise.all([
    queryClient.ensureQueryData(postQueries.list()),
    queryClient.ensureQueryData(userQueries.current()),
  ])
}
```

**Use `defer()` for non-critical data** that should not block the route transition:

```tsx
import { defer } from '@tanstack/react-router'

loader: async ({ context: { queryClient } }) => {
  const criticalData = await queryClient.ensureQueryData(postQueries.list())
  return {
    posts: criticalData,
    comments: defer(queryClient.ensureQueryData(commentQueries.recent())),
  }
}
```

---

### Search Params (HIGH)

**Always validate search params** — they come from the URL and are user-controlled input. Use `validateSearch` to parse, validate, and set defaults.

```tsx
import { z } from 'zod'

const searchSchema = z.object({
  page: z.number().min(1).catch(1),
  limit: z.number().min(1).max(100).catch(20),
  sort: z.enum(['name', 'price', 'date']).catch('name'),
  order: z.enum(['asc', 'desc']).catch('asc'),
  category: z.string().optional(),
})

export const Route = createFileRoute('/products')({
  validateSearch: (search) => searchSchema.parse(search),
  component: ProductsPage,
})

function ProductsPage() {
  const { page, sort, category } = Route.useSearch()
  // fully typed; .catch() in schema provides defaults for bad URLs
}
```

**Update search params without losing others** by using the updater function form:

```tsx
const navigate = useNavigate()
navigate({
  to: '.',
  search: (prev) => ({ ...prev, page: 1, category: newCategory }),
})
```

**Validate before using in loaders** — the loader runs after `validateSearch`, so params are already clean:

```tsx
export const Route = createFileRoute('/products')({
  validateSearch: searchSchema.parse,
  loader: async ({ context: { queryClient }, deps: { page, sort } }) =>
    queryClient.ensureQueryData(productQueries.list({ page, sort })),
  loaderDeps: ({ search: { page, sort } }) => ({ page, sort }),
  component: ProductsPage,
})
```

---

### Navigation (MEDIUM)

**Prefer `<Link>` over `useNavigate` for navigation the user triggers.** `useNavigate` is for programmatic navigation (e.g., redirecting after a form submission).

```tsx
// Good: declarative link
<Link to="/posts/$postId" params={{ postId: post.id }}>
  {post.title}
</Link>

// Good: programmatic redirect after mutation
const navigate = useNavigate()
const mutation = useMutation({
  mutationFn: createPost,
  onSuccess: (newPost) => navigate({ to: '/posts/$postId', params: { postId: newPost.id } }),
})
```

**Enable intent-based preloading** at the router level to preload routes on hover/focus:

```tsx
const router = createRouter({
  routeTree,
  defaultPreload: 'intent',
  defaultPreloadStaleTime: 0, // let TanStack Query manage freshness
  context: { queryClient },
})
```

---

### Code Splitting (MEDIUM)

**Use `.lazy.tsx` files for route components that are not needed on the initial load.** The route file keeps the loader (so data fetches immediately), while the component code loads in parallel.

```tsx
// routes/posts/$postId.tsx — keeps loader, exports lazy component ref
export const Route = createFileRoute('/posts/$postId')({
  loader: ({ context: { queryClient }, params }) =>
    queryClient.ensureQueryData(postQueries.detail(params.postId)),
})

// routes/posts/$postId.lazy.tsx — actual component, code-split
import { createLazyFileRoute } from '@tanstack/react-router'
export const Route = createLazyFileRoute('/posts/$postId')({
  component: PostDetail,
})
```

---

## Router + Query Integration

### Setup (CRITICAL)

**Pass `QueryClient` through router context** rather than using a global singleton. This enables SSR with per-request clients and clean testing.

```tsx
// router.tsx
import { setupRouterSsrQueryIntegration } from '@tanstack/react-router-ssr-query'

export function getRouter() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 2 * 60 * 1000,
        refetchOnWindowFocus: false,
      },
    },
  })

  const router = createRouter({
    routeTree,
    context: { queryClient },
    defaultPreload: 'intent',
    defaultPreloadStaleTime: 0,
    scrollRestoration: true,
  })

  // Handles SSR dehydration/hydration automatically:
  setupRouterSsrQueryIntegration({ router, queryClient })

  return router
}

declare module '@tanstack/react-router' {
  interface Register {
    router: ReturnType<typeof getRouter>
  }
}

// routes/__root.tsx
interface RouterContext {
  queryClient: QueryClient
}
export const Route = createRootRouteWithContext<RouterContext>()({ component: Root })
```

**For testing, inject a fresh `QueryClient` per test:**

```tsx
function renderWithProviders() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createRouter({ routeTree, context: { queryClient } })
  return { ...render(<RouterProvider router={router} />), queryClient }
}
```

---

### Data Flow (HIGH)

**The recommended pattern is: loader prefetches → component reads with `useSuspenseQuery`.**

- The loader ensures data is in cache before the component renders.
- `useSuspenseQuery` in the component reads from cache — it may suspend briefly if not yet cached, but usually resolves immediately.
- This is better than `useQuery` + checking `isLoading` in every component.

**Coordinate cache invalidation between mutations and router navigation:**

```tsx
const mutation = useMutation({
  mutationFn: updatePost,
  onSuccess: async (updatedPost) => {
    // Invalidate so any cached list/detail is refreshed
    await queryClient.invalidateQueries({ queryKey: postKeys.all })
    navigate({ to: '/posts/$postId', params: { postId: updatedPost.id } })
  },
})
```

**SSR: use `setupRouterSsrQueryIntegration`** (from `@tanstack/react-router-ssr-query`) instead of manually wiring dehydrate/hydrate. It handles per-request `QueryClient` creation and streaming automatically.

---

## Common Pitfalls

| Pitfall | Fix |
|---------|-----|
| Query key mismatches across files | Use query key factories |
| `staleTime: 0` causing excessive refetches | Set appropriate `staleTime` per data type |
| `prefetchQuery` in loaders (swallows errors) | Use `ensureQueryData` instead |
| Forgetting to cancel queries before optimistic update | Call `cancelQueries` in `onMutate` |
| No rollback on mutation error | Return snapshot from `onMutate`, restore in `onError` |
| `invalidateQueries()` with no key (invalidates everything) | Always pass a specific key |
| Raw `URLSearchParams` for search state | Use `validateSearch` on the route |
| Global `QueryClient` singleton in SSR | Per-request client via router context |
| Error boundary without `useQueryErrorResetBoundary` | Pair them — retry won't work otherwise |
| `select` with an unstable function reference | Wrap selector in `useCallback` |
| Transforming query data in component body | Move transformation into `select` |
| Calling `useQuery` in a loop | Use `useQueries` for dynamic parallel queries |

---

## TypeScript Tips

- Use `queryOptions()` helper to infer return types automatically — avoids manual generic annotations.
- Declare `interface Register { router: typeof router }` once; every hook in the app becomes typed.
- Use `Route.useSearch()` and `Route.useParams()` over the generic alternatives for narrower types.
- Search param schemas with `.catch()` / `fallback()` provide defaults without throwing — prefer this over try/catch in validateSearch.
- Define `RouterContext` interface and use `createRootRouteWithContext<RouterContext>()` so loaders get typed context.
- When using Zod for search params, `z.infer<typeof schema>` gives you a clean type to export and use elsewhere.
