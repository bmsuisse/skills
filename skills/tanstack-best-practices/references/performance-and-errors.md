# Performance & Error Handling Deep Dive

Load this when optimizing a large list/table, tuning retry behavior, or
building custom optimistic-update rollback logic beyond the basic invalidate
pattern in the main skill.

---

## Performance

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

## Mutations — optimistic updates

For a toggle/edit that should feel instant, the pattern is: cancel outgoing
refetches → snapshot old data → set optimistic value → return context for
rollback.

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

For simple single-component toggles you can skip cache manipulation entirely
and use `mutation.isPending` to show the optimistic state directly in the UI —
less code and still responsive.

---

## Error handling — retry policy

The default of 3 retries is fine for transient failures, but retrying 4xx
errors wastes time. Inspect the error status:

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
