# Web app: `@bmsuisse/app-native`

```bash
bun add @bmsuisse/app-native
```

Package README with all functions:
[`packages/app-native/README.md`](https://github.com/bmsuisse/bmsapp-native/blob/main/packages/app-native/README.md)
in the bmsapp-native repo.

## Common patterns

**Native chrome per route (React/TanStack Router):**

```tsx
import { can, on, setChrome } from '@bmsuisse/app-native'

useEffect(() => {
  if (!can('customChrome')) return
  setChrome({
    scope: 'route', // the app clears it on every route change → set it again here
    menu: [{ items: [{ id: 'new', label: 'New', icon: 'plus' }] }],
  })
}, [pathname])

useEffect(() => on('menuSelect', (id) => handleMenu(id)), [])
```

**Critical action:**

```ts
const confirm = await biometricConfirm('Approve order?')
if (!confirm.ok) return
await api.approve(id) // the backend checks authorization on its own
```

**Widgets live from the page:**

```ts
const res = await setWidgets(widgets) // replaces ALL widgets of this web app
if (res.ok && res.rejected > 0) console.warn('invalid widgets', res.rejected)
```

**Other apps on the iPhone** (`navigate` and `callPhone` need no capability,
`addReminder` and `saveContact` need `deviceApps`):

```ts
await navigate({ destination: { name: 'Müller AG', address: 'Industriestrasse 5, 4600 Olten' } })
const res = await addReminder({ title: 'Call back', due: toIsoWithOffset(date) })
if (res.error === 'denied') toast(res.message, 'warning')
```

**Native form or content** (needs `nativeForms` / `nativeContent`; keep the web
form as the fallback):

```ts
if (canShowNativeForms()) {
  const res = await showForm(customerForm, {
    onSubmit: async (values) => {
      const r = await fetch('/api/customers', { method: 'POST', body: JSON.stringify(values) })
      if (r.status === 422) return { fieldErrors: (await r.json()).fieldErrors } // marks fields
      if (!r.ok) throw new Error('Could not save') // form stays open
    },
  })
  if (res.ok || !isNativeSurfaceUnsupported(res)) return // done, or cancelled
}
openWebCustomerForm() // browser, old app, no capability
```

Photos, scans and signatures arrive as references (`NativeFileRef`) that the
app uploaded to the document router before; send them to your own backend.

**Token for a WebSocket** (your own `fetch`/XHR calls get the token from the app
automatically; a browser cannot set a header on a WebSocket):

```ts
const session = await getAccessToken()
if (session.ok) socket.send(JSON.stringify({ token: session.token })) // not in the URL
```

Types (`Widget`, `LiveActivityState`, `Chrome`, `NavigatePayload`, `NativeFormDef`,
`NativeContentDef`, …) are exported as well.

## Tests

In vitest/jsdom, set up `window.BMSNative` with `vi.fn()` for `postMessage`
and `call`; without it the package behaves as in the browser.
