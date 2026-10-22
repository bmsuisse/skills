---
name: bmsapp-native
plugin: coding
description: >
  Use when a web app or FastAPI backend should talk to the BMS iOS app
  (`@bmsuisse/app-native`, `bmsdna-app-native`). Triggers: BMSNative, push to
  the app, widget, Live Activity, approvals, scan barcode, native form, Entra
  token.
---

# bmsapp-native — connecting web apps and backends to the BMS app

Two packages, one standard. Never create your own copies of them in the
project (e.g. a custom `nativeBridge.ts` or `ios_push.py`) — if something is missing, it belongs in the package.

The packages and their guides live in the
[bmsuisse/bmsapp-native](https://github.com/bmsuisse/bmsapp-native) repo. Guides
are linked below as `docs/<name>.md` of that repo (they are not shipped with the packages).

| Side                        | Package                                         | Reference                                      |
| --------------------------- | ----------------------------------------------- | ---------------------------------------------- |
| Web app (browser/WKWebView) | `@bmsuisse/app-native`                          | [references/webapp.md](references/webapp.md)   |
| Backend (FastAPI)           | `bmsdna-app-native`, import `bmsdna.app_native` | [references/backend.md](references/backend.md) |

## Ground rules

1. **The page must also work without the app.** The npm functions have
   browser fallbacks; guard your own logic with `isNativeApp()` / `can(...)`.
2. **The app decides on capabilities.** Each web app has capabilities in the
   app configuration (`camera`, `customChrome`, `dashboardWidgets`, …).
   Without the capability, the app responds `{ ok: false, error: 'capability' }`.
3. **Face ID is UX only.** `biometricConfirm` does not replace an
   authorization check in the backend. The same goes for `user_email` in
   request bodies: take the caller from `auth_dependency` (`context.user`).
4. **Callbacks via `on(...)`**, not via your own `window.onNative…` functions.
5. **Widgets/Live Activities:** the same format via the bridge (npm), feed or
   push (Python). Use the Pydantic models in the backend, otherwise the app
   silently discards invalid widgets.
6. **Never commit APNs keys** (`.p8`); configure via `APNS_*` environment
   variables.
7. **Sign-in is the Entra token of the app**, not a cookie login of your own,
   for web apps with the `identity` capability. The backend checks the token
   (`create_entra_auth_dependency`), answers **401** for an invalid one (never
   a redirect), and takes the user from it. Never forward, store or log the
   token. Guide: [`docs/entra-token-guide.md`](https://github.com/bmsuisse/bmsapp-native/blob/main/docs/entra-token-guide.md).
8. **Reminders and contacts need `deviceApps`**; route and phone call do not.
   Guide: [`docs/device-actions-guide.md`](https://github.com/bmsuisse/bmsapp-native/blob/main/docs/device-actions-guide.md).
9. **Native forms and content** (`showForm`, `showContent`) need `nativeForms` /
   `nativeContent`; camera fields also `camera`. **Keep the web UI as the
   fallback** (`canShowNativeForms()`, `isNativeSurfaceUnsupported()`): browsers,
   old app builds (`unknownAction`, treat like `unavailable`) and web apps
   without the capability. Never rely on a field or block type being known by an
   older app. Use `onSubmit` so the backend can reject with field errors. Guide:
   [`docs/native-surfaces-guide.md`](https://github.com/bmsuisse/bmsapp-native/blob/main/docs/native-surfaces-guide.md).

10. **Push always carries `webapp_id`** (the web app's `id` in the app), plus
    `path` for the deep link. Without it the notification lands as "Unknown app"
    and silent pushes are ignored. Clean up dead tokens with
    `PERMANENTLY_INVALID_TOKEN_REASONS`, but keep the device record: the
    `device_id` survives a reinstall.
11. **Widgets: the feed is the source**, the bridge only updates while the page
    is open. Every delivery (feed, push, `setWidgets`) replaces **all** widgets,
    so send the complete list with stable `id`s. Action buttons run in the
    backend: check what `context.user` may do, the payload is client input.
    Guide: [`docs/dashboard-widgets-guide.md`](https://github.com/bmsuisse/bmsapp-native/blob/main/docs/dashboard-widgets-guide.md).
12. **Live Activities are for a process with a start and an end** (at most 8
    hours, about 4 KB, no images), not for permanent information (that is a
    widget). Keep the *latest* token per activity from `create_live_activity_router`,
    and never make it the only place a status can be seen: browsers and old
    apps answer `unavailable`.
13. **Approvals: the backend decides.** `get_approvals` returns everything still
    open for `context.user` (it replaces the list), `on_decision` checks that this
    user may decide this `approval_id`; `user_email` and `biometric` do not count.
    After a change, `send_approvals_update` (backend) or `refreshApprovals()` (page).
14. **Scanning** needs `camera`. Keep a way to type the value in (no scanner in a
    browser or simulator), handle each result once (the promise and `on(...)`
    both fire), and treat `cancelled` as no error. Guide:
    [`docs/scan-guide.md`](https://github.com/bmsuisse/bmsapp-native/blob/main/docs/scan-guide.md).
15. **Chrome (menu, action buttons, bottom bar)** is set per route with
    `scope: 'route'` and set again on every route change. Everything in it must
    also be reachable on the page itself, because a browser shows none of it.
    Guide: [`docs/webapp-chrome-guide.md`](https://github.com/bmsuisse/bmsapp-native/blob/main/docs/webapp-chrome-guide.md).
16. **Answers, not exceptions.** Calls return `{ ok: false, error }`. Treat
    `unavailable`, `unknownAction` (app too old) and `capability` as "show the
    web UI", `cancelled` as "do nothing", `denied` as "tell the user".

## Workflow

1. Decide which side the feature touches (page, backend, or both) and open the
   matching reference above.
2. Check that the app team has granted the capability to this web app, and
   that the backend paths match the app configuration.
3. Read the guide of the topic before building (table below), then use the
   package API; if something is missing, the package gets extended.
4. Test in a browser (fallbacks), then in the app. `sendTestNotification` shows a
   push without a backend.

## More guides

One guide per topic in the
[`docs/`](https://github.com/bmsuisse/bmsapp-native/tree/main/docs) folder of the
bmsapp-native repo. Read the matching one before building the feature:

| Topic                                   | Guide                                                                                                             |
| --------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| Native menu, action buttons, bottom bar | [webapp-chrome-guide.md](https://github.com/bmsuisse/bmsapp-native/blob/main/docs/webapp-chrome-guide.md)         |
| Dashboard widgets                       | [dashboard-widgets-guide.md](https://github.com/bmsuisse/bmsapp-native/blob/main/docs/dashboard-widgets-guide.md) |
| Live Activities                         | [live-activities-guide.md](https://github.com/bmsuisse/bmsapp-native/blob/main/docs/live-activities-guide.md)     |
| Approvals inbox                         | [approvals-guide.md](https://github.com/bmsuisse/bmsapp-native/blob/main/docs/approvals-guide.md)                 |
| Text and barcode scan                   | [scan-guide.md](https://github.com/bmsuisse/bmsapp-native/blob/main/docs/scan-guide.md)                           |
| Sign-in with the app's Entra token      | [entra-token-guide.md](https://github.com/bmsuisse/bmsapp-native/blob/main/docs/entra-token-guide.md)             |
| Route, reminder, contact, phone call    | [device-actions-guide.md](https://github.com/bmsuisse/bmsapp-native/blob/main/docs/device-actions-guide.md)       |
| Native forms and content                | [native-surfaces-guide.md](https://github.com/bmsuisse/bmsapp-native/blob/main/docs/native-surfaces-guide.md)     |
| Widgets and Live Activities in CarPlay  | [carplay-guide.md](https://github.com/bmsuisse/bmsapp-native/blob/main/docs/carplay-guide.md)                     |
| Links that open directly in the app     | [universal-links.md](https://github.com/bmsuisse/bmsapp-native/blob/main/docs/universal-links.md)                 |
