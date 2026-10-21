# Backend: `bmsdna-app-native`

```toml
dependencies = ["bmsdna-app-native"]
```

```python
from bmsdna.app_native import (
    send_push,
    create_ingest_router,
    create_widget_feed_router,
    KpiWidget,
    KpiData,
)
```

Full documentation:
[`python/app-native/README.md`](https://github.com/bmsuisse/bmsapp-native/blob/main/python/app-native/README.md)
in the bmsapp-native repo.

## Building blocks

| Task                            | API                                                                                                                              |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Receive device token + location | `create_ingest_router(on_device_registered=…, on_location_received=…)`                                                           |
| Push with banner                | `send_push(device_token=…, title=…, body=…, data={"path": "/…"})`                                                                |
| Silent push                     | `send_silent_push(...)`                                                                                                          |
| Urgent/critical                 | `send_critical_alert(...)`                                                                                                       |
| Clean up dead tokens            | `PERMANENTLY_INVALID_TOKEN_REASONS`                                                                                              |
| Receive scans, media of forms   | `create_document_router(...)` (callback may return a reference), `resolve_file_refs`, `NativeFileRef`                            |
| Receive push buttons            | `create_notification_action_router(...)`                                                                                         |
| Dashboard widgets               | `create_widget_feed_router`, `create_widget_action_router`, `create_widget_options_router`, `send_widget_update`, `dump_widgets` |
| Native forms and content        | `NativeForm`, `NativeContent` (serve a definition), `create_widget_options_router` (`form_id`, `context`), `dump_native_form`    |
| Live Activities                 | `create_live_activity_router`, `send_live_activity_start/update/end`                                                             |
| Approvals                       | `create_approvals_router`, `send_approvals_update`                                                                               |
| Sign-in with the app's token    | `EntraTokenVerifier`, `create_entra_auth_dependency`, `SignedSessionCookie`, `bearer_token`                                      |

All routers **require** an `auth_dependency`: a FastAPI dependency that
raises 401/403 or returns the user, which arrives as `context.user` in the
callbacks. For the Entra token of the app (web apps with `identity`) use
`create_entra_auth_dependency(EntraTokenVerifier.from_env(), session=SignedSessionCookie(secret=...))`:
the token has priority and gives 401 if invalid, a valid one is exchanged for a
host-only session cookie, `resolve_user` maps the identity to your own user (None
gives 403). Any other check (cookie, API key) works as well. Use
`insecure_no_auth` only locally. Take the identity from `context.user`,
never from the `user_email` in the body, which is client input.
Guide: [`docs/entra-token-guide.md`](https://github.com/bmsuisse/bmsapp-native/blob/main/docs/entra-token-guide.md).

## Configuration

`APNS_KEY` (contents of the `.p8` file, in production from a secret store),
`APNS_KEY_ID`, `APNS_TEAM_ID`,
`APNS_BUNDLE_ID`, `APNS_USE_SANDBOX` as environment variables. For the token
sign-in `ENTRA_TENANT_ID` (directory ID) and `ENTRA_AUDIENCE` (client ID of the iOS
app's registration), plus a random secret for the session cookie. Get the IDs from
the app team; do not hard-wire them. Without them
`send_push` raises `RuntimeError`. Never put the key in the repo, see
"Storing the key in production" in the Python package's README.
