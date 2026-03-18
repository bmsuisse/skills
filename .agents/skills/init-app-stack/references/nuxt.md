# Nuxt Reference

> Source: https://github.com/antfu/skills — skill by Anthony Fu
> Install: `npx skills add https://github.com/antfu/skills --skill nuxt`
> Based on Nuxt 3.x (generated 2026-01-28)

Nuxt is a full-stack Vue framework: SSR, file-based routing, auto-imports, Nitro server engine.

## Key topic areas

| Topic | Description |
|-------|-------------|
| Directory Structure | Project folders, conventions, file organization |
| Configuration | `nuxt.config.ts`, `app.config.ts`, runtime config, env vars |
| CLI Commands | `nuxi dev`, `nuxi build`, `nuxi generate`, `nuxi preview` |
| Routing | File-based routing, dynamic routes, navigation, middleware, layouts |
| Data Fetching | `useFetch`, `useAsyncData`, `$fetch`, caching, refresh |
| Modules | Creating/using Nuxt modules, Nuxt Kit utilities |
| Deployment | Nitro universal deployment: Vercel, Netlify, Cloudflare, Node |
| State Management | `useState`, SSR-friendly state, Pinia integration |
| Server Routes | API routes in `server/api/`, Nitro server middleware |
| Rendering Modes | Universal (SSR), SPA, hybrid, route rules |

## Essential patterns

```ts
// nuxt.config.ts — common baseline
export default defineNuxtConfig({
  modules: ['@nuxt/ui', '@pinia/nuxt'],
  runtimeConfig: {
    apiSecret: '',          // server-only
    public: {
      apiBase: '/api',      // exposed to client
    },
  },
})
```

```ts
// Data fetching
const { data, refresh, status } = await useFetch('/api/items')

// Server route: server/api/items.get.ts
export default defineEventHandler(async (event) => {
  return { items: [] }
})
```

```ts
// SSR-safe state
const count = useState('count', () => 0)

// Pinia store (auto-imported)
export const useUserStore = defineStore('user', () => {
  const user = ref(null)
  return { user }
})
```

For the full antfu/skills nuxt reference files (routing, data fetching, SSR hazards, etc.), install the skill:
```bash
npx skills add https://github.com/antfu/skills --skill nuxt
```
