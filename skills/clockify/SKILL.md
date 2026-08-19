---
name: clockify
description: >
  Query and log time entries in Clockify via its REST API — check a timesheet,
  look up the workspace/user/project, create or update time entries, and
  ALWAYS tag the description with a Jira issue key (`[JIRA-KEY]: Summary`) —
  never leave a Clockify entry without one. Use
  whenever the user asks about their Clockify timesheet, wants to log/add/
  edit tracked time, or asks "what did I work on", "log N hours on X", "add
  a time entry", "see my timesheet". Trigger on: "clockify", "log time",
  "time entry", "add hours", "my timesheet", "track time". DO NOT USE FOR:
  Jira issue tracking itself, or general project management — only the
  Clockify side of time tracking.
---

# Clockify

## Setup

`CLOCKIFY_API_KEY` in `.env` (get it from Clockify → profile icon → Preferences
→ API — a personal key, not a per-workspace one). Every request:

```bash
source .env
curl -s -H "X-Api-Key: $CLOCKIFY_API_KEY" https://api.clockify.me/api/v1/...
```

## Who am I / which workspace

```bash
curl -s -H "X-Api-Key: $CLOCKIFY_API_KEY" https://api.clockify.me/api/v1/user
```

Returns `activeWorkspace` (the workspace id used in every other endpoint) and
`settings.timeZone` (e.g. `Europe/Zurich`) — use that offset, not UTC, when
the user gives a local time like "this morning" or "9-5".

## Find a project

```bash
curl -s -H "X-Api-Key: $CLOCKIFY_API_KEY" \
  "https://api.clockify.me/api/v1/workspaces/$WS/projects?name=<query>&page-size=50"
```

The `name` filter is a loose substring match — if nothing comes back, drop
the filter (`page-size=200`, no `name`) and scan the full list yourself.
Clockify project names don't reliably mirror Jira project/epic names (a
Jira epic called "OneSales" existed with no matching Clockify project at
all) — don't assume a 1:1 match, ask the user which project to use if it's
ambiguous or missing.

## Create a time entry

```bash
curl -s -X POST -H "X-Api-Key: $CLOCKIFY_API_KEY" -H "Content-Type: application/json" \
  -d '{"start":"2026-08-19T06:00:00Z","end":"2026-08-19T10:00:00Z","projectId":"<id>","description":"[BMSBIDWH-703]: OneSales"}' \
  "https://api.clockify.me/api/v1/workspaces/$WS/time-entries"
```

`start`/`end` are always UTC on the wire (`Z` suffix) regardless of the
workspace's local `timeZone` — convert the user's local time yourself before
sending, or entries land on the wrong hour/day.

## Update a time entry

```bash
curl -s -X PUT -H "X-Api-Key: $CLOCKIFY_API_KEY" -H "Content-Type: application/json" \
  -d '{"start":"...","end":"...","projectId":"<id>","description":"...","billable":false}' \
  "https://api.clockify.me/api/v1/workspaces/$WS/time-entries/<entryId>"
```

`PUT` replaces the whole entry — always resend `start`/`end`/`projectId`,
not just the field you're changing.

## Description convention — always reference Jira

Every entry in this workspace follows `[JIRA-KEY]: Summary`, e.g.
`[BMSBIDWH-680]: CIP`. This is mandatory, not optional — never create or
update a Clockify time entry with a bare description. Always resolve a Jira
key first:

```bash
curl -s -u "$JIRA_EMAIL:$JIRA_API_TOKEN" "$JIRA_SITE/rest/api/3/issue/{key}"          # exact key known
curl -s -u "$JIRA_EMAIL:$JIRA_API_TOKEN" "$JIRA_SITE/rest/api/3/project/search?query=<name>"  # find it by name
```

then use `[KEY]: Title` as the description. If no matching Jira issue exists,
ask the user for the key rather than inventing one or leaving it off.

## Gotchas

- **Creating a project can 403 `Access Denied`** for a non-admin API key.
  Don't assume you can create one on demand; if no matching project exists,
  ask the user which existing project to file the entry under instead of
  guessing or silently picking one.
- Times are UTC on the wire — always convert from the workspace's local
  `timeZone`, both when reading a timesheet back and when creating entries.
