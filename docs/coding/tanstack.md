---
title: TanStack Best Practices
description: TanStack Query, Router, and Table patterns for React — query keys, loaders, search params, SSR.
---

# TanStack Best Practices

**Skill:** `tanstack-best-practices` · **Plugin:** `coding@bmsuisse-skills`

## TanStack Query

### Query key factories

Use spread-array hierarchy so you can invalidate at any level:

```typescript
const userKeys = {
    all:    ()             => ["users"]                    as const,
    lists:  ()             => [...userKeys.all(), "list"]  as const,
    list:   (f: Filter)    => [...userKeys.lists(), f]     as const,
    detail: (id: string)   => [...userKeys.all(), id]      as const,
};

// Invalidate everything for a user
queryClient.invalidateQueries({ queryKey: userKeys.detail(id) });
// Invalidate all lists
queryClient.invalidateQueries({ queryKey: userKeys.lists() });
```

### `queryOptions()` pattern

Colocate query key + fetcher so both `useQuery` and `router.ensureQueryData` use the same definition:

```typescript
const userQuery = (id: string) => queryOptions({
    queryKey: userKeys.detail(id),
    queryFn:  () => fetchUser(id),
    staleTime: 5 * 60 * 1000,
});

// In component
const { data } = useQuery(userQuery(id));

// In router loader
loader: ({ params }) => queryClient.ensureQueryData(userQuery(params.id))
```

### `staleTime` guidance

| Data type | Recommended `staleTime` |
|---|---|
| User profile, settings | `5–30 min` |
| List data, search results | `1–5 min` |
| Real-time / frequently updated | `0` (default) |
| Static reference data | `Infinity` |

### Mutations with invalidation

```typescript
const updateUser = useMutation({
    mutationFn: (data: UpdateUser) => api.patch(`/users/${data.id}`, data),
    onSuccess: (_, vars) => {
        queryClient.invalidateQueries({ queryKey: userKeys.detail(vars.id) });
        queryClient.invalidateQueries({ queryKey: userKeys.lists() });
    },
});
```

## TanStack Router

### Type registration (required)

```typescript
// src/routeTree.gen.ts (auto-generated)
declare module "@tanstack/react-router" {
    interface Register {
        router: typeof router;
    }
}
```

### Search params with Zod validation

Always add `.catch()` so invalid URLs don't break the route:

```typescript
const searchSchema = z.object({
    page:   z.number().int().min(1).catch(1),
    sort:   z.enum(["asc", "desc"]).catch("asc"),
    filter: z.string().optional(),
});

export const Route = createFileRoute("/users/")({
    validateSearch: searchSchema,
    loaderDeps: ({ search }) => ({ page: search.page, sort: search.sort }),
    loader: ({ deps }) => queryClient.ensureQueryData(usersQuery(deps)),
});
```

### `ensureQueryData` vs `prefetchQuery`

| Method | Use when |
|---|---|
| `ensureQueryData` | Route requires the data — blocks navigation until loaded |
| `prefetchQuery` | Preloading on hover/intent — doesn't block |

### Router + Query SSR integration

```typescript
// root.tsx
export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
    component: RootComponent,
});

// router.ts
const router = createRouter({
    routeTree,
    context: { queryClient },
});
setupRouterSsrQueryIntegration(router, queryClient);
```

## Common pitfalls

| Pitfall | Fix |
|---|---|
| Query key as plain string `"users"` | Use array: `["users"]` |
| No `.catch()` on search param schema | Add `.catch(defaultValue)` to every field |
| `useQuery` in loader | Use `ensureQueryData` in loader, `useSuspenseQuery` in component |
| Invalidating too broadly | Use key hierarchy to invalidate only what changed |
| Forgetting `loaderDeps` | Declare all search params that affect the loader in `loaderDeps` |
