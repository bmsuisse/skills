# Web app: `@bmsuisse/app-native`

```bash
bun add @bmsuisse/app-native
```

Package README with all functions:
[`packages/app-native/README.md`](https://github.com/bmsuisse/bmsapp-native/blob/main/packages/app-native/README.md)
in the bmsapp-native repo.

## Basics

**Detection.** `isNativeApp()` (inside the app?), `can('camera')` (capability
granted to this web app?), `nativeInfo()` (`appVersion`, `webAppId`,
`capabilities`, `null` outside the app). `can` only saves calls; the app checks
on its own.

**Results.** Calls with an answer return `{ ok: true, … }` or
`{ ok: false, error }`; they do not throw. Outside the app they resolve
`unavailable` right away.

| `error`                        | Meaning / what to do                                                              |
| ------------------------------ | --------------------------------------------------------------------------------- |
| `unavailable`                  | Browser, very old app, or no scanner / Live Activities on the device → web UI     |
| `unknownAction`                | App build predates the call → treat exactly like `unavailable`                    |
| `capability`                   | The app has not granted the capability to this web app → web UI, tell the team    |
| `cancelled`                    | The user closed the sheet or scanner → do nothing, no error message               |
| `denied`                       | Camera / Reminders / Contacts switched off in iOS → show `message` to the user    |
| `invalid`, `notConfigured`, …  | Developer error (wrong payload, missing app config): fix it, do not retry blindly |

`call`, `send`, `post` are the raw layer for an action the package does not
wrap yet. Do not use them for anything that has a function; if an action is
missing, it belongs in the package.

**Events** (`on` returns an unsubscribe function, call it on unmount):
`menuSelect`, `actionButtonTap`, `bottomBarTap` (ids of the chrome entries),
`barcodeScanned`, `barcodesScanned`, `textScanned`, `surfaceAction`.

| Capability                                        | Needed for                                    |
| ------------------------------------------------- | --------------------------------------------- |
| `customChrome` / `customBottomBar`                | menu, action buttons / bottom bar             |
| `camera`                                          | scan calls; camera, scan, barcode form fields |
| `dashboardWidgets`, `liveActivities`, `approvals` | the feature of the same name                  |
| `identity`                                        | Entra token for your backend                  |
| `deviceApps`                                      | `addReminder`, `saveContact`                  |
| `nativeForms`, `nativeContent`                    | `showForm`, `showContent`                     |
| `notifications`                                   | `sendTestNotification`                        |

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

`actionButtons`: at most 2 (`customChrome`). `bottomBar`: at most 5 entries
(`customBottomBar`), `bottomBarStyle: 'prominent'` raises one entry
(`centerProminentEntry(entries, id)` puts it in the middle). Icons are SF Symbol
names. Taps arrive as events, not as URLs: keep your normal navigation as the
only source of truth. Without the app nothing is shown, so every action in the
menu needs a normal button or link on the page too.

**Feedback and system** (all are no-ops outside the app except `share`,
`openExternal`, `biometricConfirm`):

```ts
toast('Saved', 'success') // 'info' | 'success' | 'warning' | 'error'
haptic('success') // light | medium | heavy | soft | rigid | selection | success | warning | error
setBadge(openCount) // number on this web app's tile, 0 removes it
await share({ title: 'Order 123', url: location.href }) // 'shared' | 'copied' | 'cancelled' | 'unavailable'
openExternal(url) // deliberately leaves the app (Safari); new tab in a browser
```

A native toast does not replace your page's own error display: outside the app
`toast` shows nothing.

**Critical action:**

```ts
const confirm = await biometricConfirm('Approve order?')
if (!confirm.ok) return
await api.approve(id) // the backend checks authorization on its own
```

**Scan** (`camera`). The promise carries the result; the `on(...)` events fire
too, so handle each result once. Always keep a way to type the value in:
there is no scanner on a simulator or in a browser.

```ts
const sn = await scanText({ pattern: '[A-Z]{2}-\\d{4,}' }) // pick one line of a label
if (sn.ok) form.serial = sn.text

const res = await scanBarcodes({ formats: ['ean13', 'qr'], max: 20 }) // goods receipt
if (res.ok) addLines(res.values)
else if (res.error !== 'cancelled') showManualInput(res.message)
```

`scanText` takes an ICU regex that must match the **whole line**
(case-insensitive); for a line like `S/N: AB-1234` use `.*AB-\\d{4}.*`.
`scanBarcode({ formats })` returns one `value`, plain `scanBarcode()` returns
`{ ok: true }` and delivers via `on('barcodeScanned')`. `scanDocument()` opens
the document scanner; the app uploads the result itself to the web app's
`documentUploadPath` (backend `create_document_router`). Old apps ignore
`formats`/`max` and give one code with `oldApp: true`. Guide:
[`docs/scan-guide.md`](https://github.com/bmsuisse/bmsapp-native/blob/main/docs/scan-guide.md).

**Widgets live from the page** (`dashboardWidgets`). The feed
(`create_widget_feed_router`) is the real source, the bridge only updates while
the page is open:

```ts
const res = await setWidgets(widgets) // replaces ALL widgets of this web app
if (res.ok && res.rejected > 0) console.warn('invalid widgets', res.rejected)
await updateWidget(widget) // replaces one widget by id, or appends it
await removeWidgets(['open-orders']) // no ids = all of this web app's widgets
await refreshWidgets() // app re-fetches the feed now (after your own change)
```

Kinds: `kpi`, `stats`, `list`, `chart`, `progress`, `text`, `action` (buttons and
small forms that call the backend), `news`. `id` stays stable (the app remembers
order and visibility); sizes `small` … `xlarge`; content that does not fit is
cut off. Buttons can have `confirm` and `biometric`. Never build the widget list
by hand against the guide: use the `Widget` type.

**Live Activities** (`liveActivities`, Lock Screen and Dynamic Island) for a
process with a start and an end, at most 8 hours:

```ts
const steps = ['Ordered', 'Packed', 'Ready']
await startLiveActivity({
  id: 'A-123', // your id, e.g. the order number; existing id = update
  path: '/orders/A-123',
  state: { title: 'Order is being packed', steps, currentStep: 1 },
})
await updateLiveActivity({
  id: 'A-123',
  state: { title: 'Ready for pickup', steps, currentStep: 2 },
  alert: { title: 'Ready for pickup', body: 'Counter 3' }, // sound + expands; use rarely
})
await endLiveActivity({ id: 'A-123', state: { title: 'Picked up' }, dismiss: 'immediate' })
const res = await getLiveActivities() // res.ok → res.ids: ids of the running ones
```

Only `title` is required in `state`; text, numbers, SF Symbols only, about 4 KB.
Errors: `disabled` (user switched it off), `invalid`, `notFound`, `failed`. From
the browser it is `unavailable`, so a Live Activity can never be the only way to
see a status. The backend continues it with a token (see backend.md).

**Approvals** (`approvals`): the inbox is fed by the backend, not by the page.
After the page itself changed an approval, `await refreshApprovals()` makes the
app reload the feed.

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

Content screens work the same way: `showContent(def, { onAction })` resolves once
with the tapped action's `id` or `"dismiss"`. With `onAction` the surface stays
open until your handler settles (return nothing = close, throw or
`{ ok: false, message }` = stay open, `then: [...]` = follow-up steps, at most 6).
`canShowNativeContent()` is the guard. A chained surface (`then: [{ showForm }]`)
has its own round trip: register it with `onSurfaceAction(id, handler)` and call
the returned function when done. `closeSurface()` and `surfaceResult()` are the
low-level calls the helpers use; you rarely need them. `formLimitWarnings` and
`contentLimitWarnings` list definitions that exceed the app's limits (the
helpers already warn in development builds).

Photos, scans and signatures arrive as references (`NativeFileRef`) that the
app uploaded to the document router before; send them to your own backend.

**Token for a WebSocket** (your own `fetch`/XHR calls get the token from the app
automatically; a browser cannot set a header on a WebSocket):

```ts
const session = await getAccessToken()
if (session.ok) socket.send(JSON.stringify({ token: session.token })) // not in the URL
```

**Trying it without a backend:** `sendTestNotification({ title, body, delay, actions })`
(`notifications`) schedules a local notification that looks like a push.

Types (`Widget`, `LiveActivityState`, `Approval`, `Chrome`, `NavigatePayload`,
`NativeFormDef`, `NativeContentDef`, …) are exported as well.

## Tests

In vitest/jsdom, set up `window.BMSNative` with `vi.fn()` for `postMessage`
and `call`; without it the package behaves as in the browser.
