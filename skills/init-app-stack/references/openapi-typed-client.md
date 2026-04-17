# OpenAPI Typed Client Reference

Generate frontend TypeScript types from FastAPI's OpenAPI schema. Zero manual type duplication.

Load this when adding new backend endpoints, refactoring response models, or debugging type mismatches between FE and BE.

---

## The workflow

1. Define a Pydantic response model on a FastAPI endpoint.
2. Start the backend (`uv run dev`).
3. Run `bun run generate-api` in the frontend.
4. `frontend/src/lib/api-types.ts` now has typed `paths`, `components`, `operations`.

```bash
cd frontend && bun run generate-api
# → openapi-typescript http://localhost:8000/openapi.json -o src/lib/api-types.ts
```

Re-run any time a backend response model changes. Commit `api-types.ts`? **No** — it's in `.gitignore` (regenerated from the source of truth). Check it in only if CI doesn't regenerate it.

---

## Using the generated types

```ts
import type { paths, components } from './api-types'

// Pull a response schema by name:
type User = components['schemas']['UserOut']

// Or pull an operation's response type from its path:
type GetUserResponse =
  paths['/users/{user_id}']['get']['responses']['200']['content']['application/json']

// Request bodies:
type CreateUserBody =
  paths['/users']['post']['requestBody']['content']['application/json']
```

### Typed wrapper (optional)

Wrap the generic `api<T>` helper when you want stronger inference per endpoint:

```ts
// lib/queries.ts
import { queryOptions } from '@tanstack/react-query'
import { api } from './api'
import type { components } from './api-types'

type User = components['schemas']['UserOut']

export const userQuery = (id: number) =>
  queryOptions({
    queryKey: ['users', id],
    queryFn: () => api<User>(`/users/${id}`),
  })
```

---

## Power mode: `openapi-fetch`

For full type inference on path, query, body, and response in one call, add [`openapi-fetch`](https://openapi-ts.dev/openapi-fetch/):

```bash
bun add openapi-fetch
```

```ts
// lib/client.ts
import createClient from 'openapi-fetch'
import type { paths } from './api-types'

export const client = createClient<paths>({ baseUrl: import.meta.env.VITE_API_URL })

// Now every call is fully typed:
const { data, error } = await client.GET('/users/{user_id}', {
  params: { path: { user_id: 42 } },
})
```

Recommendation: start with the plain `api<T>` wrapper (already scaffolded). Add `openapi-fetch` when endpoint count grows and manual `<T>` annotations get tedious.

---

## Regeneration discipline

- Run `generate-api` **before** you touch frontend code that depends on a changed backend model — otherwise the type checker will be happily wrong.
- CI should run the backend, run `bun run generate-api`, and fail if `api-types.ts` differs from what was committed (or just regenerate as part of build).
- Breaking backend changes (renaming a field, removing an endpoint) will surface as type errors on the next `generate-api` — embrace this as the contract-testing signal.

---

## When it breaks

- **Empty or malformed `api-types.ts`**: backend not running, or `/openapi.json` returned an error. `curl http://localhost:8000/openapi.json | jq .info` to confirm.
- **Missing schemas**: the endpoint doesn't declare `response_model=` or the Pydantic model isn't imported at module level. FastAPI only includes schemas it can statically resolve.
- **`any` everywhere**: check you're using `components['schemas']['X']`, not `components['schemas'].X` (TS can't narrow the latter through the index signature).
