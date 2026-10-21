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
never from the `user_email` in the body, which is client input. The same goes
for ids in a payload (`approval_id`, `widget_id`, `data` of a push button):
check that `context.user` may act on them.
Guide: [`docs/entra-token-guide.md`](https://github.com/bmsuisse/bmsapp-native/blob/main/docs/entra-token-guide.md).

The examples below use `require_user` for this dependency and mount every router
with `app.include_router(router, prefix="/api")`; the app calls the default
paths (`api/devices`, `api/widgets`, `api/approvals`, …) unless the web app is
configured with others.

## Examples

**Devices and push.** The app registers `push_token` and `user_email`
independently of each other (push before login is normal), so only touch the
fields that were sent. The owner of a device is `context.user`, not the body:

```python
async def on_device_registered(body: DeviceRegistration, context: WidgetRequestContext) -> None:
    device = store.get_or_create(body.device_id)
    if "push_token" in body.model_fields_set:
        device.push_token = body.push_token
    if isinstance(context.user, EntraUser):
        device.user_email = context.user.email  # never body.user_email
    store.save(device)


app.include_router(
    create_ingest_router(on_device_registered=on_device_registered, auth_dependency=require_user),
    prefix="/api",
)

sent, detail = await send_push(
    device_token=device.push_token,
    title="New order",
    body="Order 123 is awaiting confirmation",
    data={"webapp_id": "partner-tool", "path": "/orders/123"},
)
if not sent and detail in PERMANENTLY_INVALID_TOKEN_REASONS:
    device.push_token = None  # keep the device record, its device_id survives a reinstall
```

`data` keys the app evaluates: **`webapp_id`** (the web app's `id` in the app;
send it with every push, otherwise the notification lands as "Unknown app" and
silent pushes are ignored), `path` (opens the web app there on tap), `actions`
(`[{"id": "confirm", "title": "Confirm"}]`: buttons in the app's notifications
tab, not on the lock screen banner). Taps arrive in
`create_notification_action_router(on_action_received=…, auth_dependency=…)` with
`action.action` (the tapped id) and `action.data`. `send_push` returns
`(sent, detail)` and raises `RuntimeError` only when APNs is not configured, so
catch that in loops. `send_silent_push(device_token=…, data={"webapp_id": …})`
reloads the web app in the background (best effort, throttled by iOS).
`send_push(..., interruption_level="time-sensitive")` breaks through Focus;
`send_critical_alert(device_token=…, webapp_id=…, title=…, body=…, acknowledge_label=…)`
is for real emergencies only (full-screen alarm, the acknowledgement comes back as
`action="acknowledge"` in the action router).

**Dashboard widgets.** The feed is the source of truth (the app fetches it on
launch, on foreground and after a silent push); the push only says "reload":

```python
async def get_widgets(context: WidgetRequestContext) -> list[Widget]:
    return [
        KpiWidget(id="open-orders", title="Open orders", data=KpiData(value=await count_open(context.user), unit="pcs"))
    ]


async def on_action(action: WidgetActionReceived, context: WidgetRequestContext) -> WidgetActionResult | None:
    if not await may_act(context.user, action.widget_id):  # action.* is client input
        return WidgetActionResult(ok=False, message="Not allowed", style="error")
    await handle(action.widget_id, action.action_id, action.item_id, action.values)
    return WidgetActionResult(message="Done", widget=await build_widget(context.user, action.widget_id))


app.include_router(create_widget_feed_router(get_widgets=get_widgets, auth_dependency=require_user), prefix="/api")
app.include_router(create_widget_action_router(on_action_received=on_action, auth_dependency=require_user), prefix="/api")

await send_widget_update(device_token=token, webapp_id="partner-tool", widgets=await get_widgets_for(user))
```

A feed or `send_widget_update(widgets=…)` replaces **all** widgets of the web app,
so always send the complete list. `WidgetActionResult` may carry `widget` (replace
one), `widgets` (replace all), `open_path` and `ok=False` (shows `message` as an
error). Use the Pydantic models (`KpiWidget`, `ListWidget`, `ActionWidget`, …) and
snake_case; they validate and serialise to the camelCase the app expects.
`create_widget_options_router` answers search / remote `select` fields of action
widgets and native forms.

**Documents** (scans and the media of native forms):

```python
async def on_document_received(doc: ReceivedDocument, context: WidgetRequestContext) -> str | None:
    if doc.metadata.kind != "form":  # a plain scan
        await blobs.put(owner=context.user.oid, name=doc.filename, data=doc.data)
        return None
    # form media: idempotent per upload_id (the app retries), return a reference
    return await uploads.put(owner=context.user.oid, upload_id=doc.metadata.upload_id, doc=doc)


app.include_router(
    create_document_router(on_document_received=on_document_received, auth_dependency=require_user),
    prefix="/api",
)
# default limit 25 MB (413 above); max_bytes=… changes it
```

The page later sends the references to its own endpoint; turn them back with
`await resolve_file_refs(body.card, lambda ref: uploads.get(owner=user.oid, ref=ref))`
(`NativeFileRef`, 422 for unknown refs). Check the owner when resolving, and
delete uploads no request ever names after a while.

**Live Activities.** The app reports tokens; you store them per activity and
push updates with them. Updates need the *latest* token of an activity:

```python
async def on_token(body: LiveActivityTokenReceived, context: WidgetRequestContext) -> None:
    if body.event == "token":  # per activity, may change while it runs
        await db.save_activity_token(body.device_id, body.activity_id, body.push_token)
    elif body.event == "push_to_start_token":  # one per device, iOS 17.2+
        await db.save_start_token(body.device_id, body.push_token)
    elif body.event == "ended":  # swiped away or ended: drop the token
        await db.delete_activity_token(body.device_id, body.activity_id)


app.include_router(
    create_live_activity_router(on_token_received=on_token, auth_dependency=require_user), prefix="/api"
)

state = LiveActivityState(title="Ready for pickup", steps=["Ordered", "Packed", "Ready"], current_step=2)
await send_live_activity_update(push_token=token, state=state, alert_title="Ready for pickup")  # alert sparingly
await send_live_activity_update(push_token=token, state=state, priority=5)  # unimportant intermediate state
await send_live_activity_end(push_token=token, dismiss_at=datetime.now(UTC) + timedelta(minutes=30))

# start without the app open (iOS 17.2+), then wait for its `token` event before updating
await send_live_activity_start(
    push_to_start_token=start_token,
    attributes=LiveActivityAttributes(webapp_id="partner-tool", activity_id="A-123", webapp_name="Partner-Tool", path="/orders/A-123"),
    state=LiveActivityState(title="Order received"),
)
```

Max 8 hours per activity, about 4 KB per update, text and SF Symbols only. A
failure with a reason in `PERMANENTLY_INVALID_TOKEN_REASONS` means the activity is
over. The same APNs key is used; the toolkit sets the Live Activity topic.

**Approvals.** The app shows what `get_approvals` returns for the signed-in user and
posts the decision back. The backend alone decides who may decide:

```python
async def get_approvals(context: WidgetRequestContext) -> list[Approval]:
    rows = await repo.open_requests_for(context.user.email)
    return [
        Approval(
            id=str(r["id"]),
            title="Vacation request",
            subtitle=f"{r['name']} · {r['period']}",
            amount=f"{r['days']} days",
            due_at=r["due_at"],
            details=[ApprovalDetail(label="Deputy", value=r["deputy"])],
            reject_comment="required",  # none | optional | required
        )
        for r in rows
    ]


async def on_decision(body: ApprovalDecisionReceived, context: WidgetRequestContext) -> ApprovalDecisionResult | None:
    if not await repo.may_decide(body.approval_id, context.user.email):  # NOT body.user_email
        return ApprovalDecisionResult(ok=False, message="Not (or no longer) yours to decide")
    await repo.decide(body.approval_id, body.decision, body.comment, context.user.email)
    return None  # plain ok: the app removes the approval


app.include_router(
    create_approvals_router(get_approvals=get_approvals, on_decision=on_decision, auth_dependency=require_user),
    prefix="/api",
)

await send_approvals_update(device_token=token, webapp_id="partner-tool")  # new request came in
```

The feed replaces all of the web app's approvals (max 100), so return everything
still open. `biometric=True` asks for Face ID, which is UX only. A decision is
not queued offline: the user sees the error. For a visible "New request" also send
a normal `send_push`.

**Native forms and content.** Serve a definition with `NativeForm` / `NativeContent`
(`response_model_by_alias=True`, `response_model_exclude_none=True`) so typos and
limit breaches fail in the backend, not on the device. Field options for `search`
and remote `select` come from `create_widget_options_router` (`req.form_id`,
`req.field_id`, `req.query`), uploads from the document router above. Full example:
[`docs/native-surfaces-guide.md`](https://github.com/bmsuisse/bmsapp-native/blob/main/docs/native-surfaces-guide.md).

## Configuration

`APNS_KEY` (contents of the `.p8` file, in production from a secret store),
`APNS_KEY_ID`, `APNS_TEAM_ID`,
`APNS_BUNDLE_ID`, `APNS_USE_SANDBOX` as environment variables (`true` for Xcode
debug builds, `false` for TestFlight and App Store; a mix-up shows as
`BadDeviceToken`). For the token
sign-in `ENTRA_TENANT_ID` (directory ID) and `ENTRA_AUDIENCE` (client ID of the iOS
app's registration), plus a random secret for the session cookie. Get the IDs from
the app team; do not hard-wire them. Without them
`send_push` raises `RuntimeError`. Never put the key in the repo, see
"Storing the key in production" in the Python package's README.

Credentials from a database or admin UI instead of the environment: pass
`config=ApnsConfig(key=…, key_id=…, team_id=…, bundle_id=…, use_sandbox=…)` to any
`send_*`, or register an async loader once with `set_apns_config_provider(load)`.
Explicit `config` wins over the provider, the provider over `APNS_*`. The key
applies to the whole Apple team and only two can be active: reuse the team's
key, rotate by adding the new one before revoking the old.

## Tests

The callbacks are plain async functions, so test them directly with fake
`WidgetRequestContext`s; no APNs credentials are needed. The `build_*_message`
functions (`build_alert_message`, `build_widget_update_message`,
`build_approvals_update_message`, `build_live_activity_message`, …) return only the
payload, and `dump_widgets` / `dump_native_form` / `dump_native_content` return
the exact JSON the app gets. Patch `send_push` & co. in your own tests rather than
calling APNs.
