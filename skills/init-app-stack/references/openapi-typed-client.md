# OpenAPI Typed Client Reference

Generate a typed frontend SDK, TanStack Query hooks, and Zod runtime
validators from FastAPI's OpenAPI schema via [`@hey-api/openapi-ts`](https://openapi-ts.dev).
Zero manual type duplication, zero hand-written fetch wrappers.

Load this when adding new backend endpoints, refactoring response models, or
debugging type mismatches between FE and BE.

---

## The workflow

1. Define a Pydantic response model on a FastAPI endpoint. Give it a clean
   `operation_id=` (e.g. `@app.get("/users/{user_id}", operation_id="get_user")`)
   — otherwise hey-api derives a function name from the path
   (`getUserUsersUserIdGet`), which works but reads worse.
2. Run `just generate-api`.
3. `frontend/src/lib/generated/` now has a typed SDK (`sdk.gen.ts`), types
   (`types.gen.ts`), TanStack Query options (`@tanstack/react-query.gen.ts`),
   and Zod schemas (`zod.gen.ts`).

```bash
just generate-api
# → uv run python -m backend.dump_openapi   (writes frontend/openapi.json — no running server needed)
# → cd frontend && bun run generate-api     (openapi-ts, reads frontend/openapi.json, writes src/lib/generated/)
```

Re-run any time a backend route or response model changes. **Commit the
output** — `frontend/openapi.json` and `frontend/src/lib/generated/` are
checked in, not gitignored. They're the reviewable record of the
frontend/backend contract: a PR that changes a response shape shows the
generated diff, same as a schema migration shows a SQL diff.

---

## Using the generated SDK + Query hooks

Don't hand-write `fetch()` calls or `queryKey` arrays — use the generated
per-operation query options directly:

```ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getUserOptions, updateUserMutation } from '@/lib/generated/@tanstack/react-query.gen'

function UserPanel({ userId }: { userId: number }) {
  const { data, isLoading } = useQuery(getUserOptions({ path: { user_id: userId } }))

  const queryClient = useQueryClient()
  const { mutate } = useMutation({
    ...updateUserMutation(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: getUserOptions({ path: { user_id: userId } }).queryKey }),
  })

  // ...
}
```

For one-off calls outside a component (e.g. a loader), call the SDK function directly:

```ts
import { getUser } from '@/lib/generated/sdk.gen'

const { data } = await getUser({ path: { user_id: 42 }, throwOnError: true })
```

Pull a bare type when you need one without a request:

```ts
import type { UserOut } from '@/lib/generated/types.gen'
```

### Configuring the client

`src/lib/api.ts` configures the generated client's `baseUrl` and
`credentials` once, imported for its side effect in `main.tsx` before the
router renders:

```ts
import { client } from './generated/client.gen'

client.setConfig({
  baseUrl: import.meta.env.VITE_API_URL,
  credentials: 'include',
})
```

Add request/response interceptors (auth headers, 401 re-auth handling) via
`client.interceptors.request.use(...)` / `client.interceptors.response.use(...)`
in the same file — don't scatter auth logic across call sites.

### Runtime validation (Zod)

`openapi-ts.config.ts` sets `validator: { request: "zod" }` on the `@hey-api/sdk`
plugin, so request payloads are validated against the generated Zod schemas
before the request is sent — a malformed request body throws client-side
instead of round-tripping to a 422. Response validation is opt-in (`validator:
{ response: "zod" }`) if you want to guard against a backend/frontend drift
that OpenAPI regeneration hasn't caught yet (e.g. stale deploy).

---

## Regeneration discipline

- Run `just generate-api` **before** you touch frontend code that depends on
  a changed backend model — otherwise the type checker is happily wrong.
- It does **not** require the backend server (or Postgres) running:
  `backend/dump_openapi.py` imports the FastAPI `app` object directly and
  calls `app.openapi()`, which never executes the lifespan (no DB connection
  needed) — this is faster and more CI-friendly than curling a live
  `/openapi.json`.
- CI should run `just generate-api` and fail the build if `frontend/openapi.json`
  or `frontend/src/lib/generated/` differ from what's committed — that diff is
  the contract-testing signal for breaking backend changes (renamed field,
  removed endpoint, changed status code).

---

## When it breaks

- **`ModuleNotFoundError: backend` from `dump_openapi.py`**: run it as
  `uv run python -m backend.dump_openapi` from the project root, not as a
  bare script — `backend` needs to be importable as a package.
- **Empty or malformed `openapi.json`**: an import error in `backend/main.py`
  (or anything it imports) will surface here since `dump_openapi.py` imports
  the app directly. Run `uv run python -c "from backend.main import app"` to
  isolate it.
- **Missing schemas**: the endpoint doesn't declare `response_model=` or the
  Pydantic model isn't imported at module level. FastAPI only includes
  schemas it can statically resolve.
- **Ugly generated names** (`getUserUsersUserIdGet` instead of `getUser`): add
  `operation_id=` to the FastAPI route decorator and regenerate.
- **Stale hooks after a rename**: if `bun run generate-api` succeeds but a
  component still imports an old export name, the type checker will catch it
  — that's expected; update the import.
