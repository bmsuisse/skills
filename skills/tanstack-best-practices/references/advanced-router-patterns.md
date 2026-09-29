# Advanced Router Patterns

Load this when a route needs multiple parallel loads, deferred/non-critical
data, code-splitting, or you're wiring up the full SSR test setup — patterns
that come up less often than the CRITICAL/HIGH items in the main skill.

---

## Data Loading — parallel and deferred

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

## Code Splitting

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

## Testing — fresh `QueryClient` per test

```tsx
function renderWithProviders() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createRouter({ routeTree, context: { queryClient } })
  return { ...render(<RouterProvider router={router} />), queryClient }
}
```
