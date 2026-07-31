---
name: testing-strategy
plugin: coding
description: >
  Decide what kind of test to write and in what order for a backend feature:
  HTTP-level first, then Playwright e2e for the same flow. Use whenever
  adding or reviewing tests for an API endpoint or a user-facing flow, when
  the user asks "how should I test this", "add tests for X", "write an e2e
  test", or when a PR is missing test coverage. Not a Postgres setup guide —
  see the pgdevkit skill for that.
---

# Testing strategy

For any new backend feature, test it twice, in this order:

1. **HTTP-level test first** — real app, real DB, no browser. In Python:
   `httpx.AsyncClient(transport=ASGITransport(app=app))` against a live route.
   Cheapest way to lock down request/response shape, status codes, and
   permission checks.
2. **Playwright e2e for the same flow** — drives the actual UI against a live
   backend (see [playwright-python](../playwright-python/SKILL.md)), so it
   also catches wiring bugs the HTTP test can't see (wrong field name in the
   frontend, a button that never fires the request).

Both tiers earn their place — the HTTP test is fast and pinpoints backend
regressions precisely; the e2e test is the only one that proves the feature
actually works end to end. Don't write only one.

**Unit tests / `.spec.ts` files are optional and not part of this pyramid.**
Use them freely as scratch scaffolding while you (the agent) work out a
tricky piece of logic, but they don't run in CI and don't need to be
committed — delete them once the HTTP and e2e tests above cover the feature.

## Keep files small

One file per endpoint or per UI flow, not one giant `test_api.py` /
`test_app.spec.ts` covering everything. Split as soon as a file drifts
toward covering more than one feature — small files are what makes "check
one flow in isolation" cheap for both humans and agents.

## Test data

Use pgdevkit's `.test_data.json` sidecar convention for seeding rows —
`skillup add bmsuisse/pgdevkit --skill pgdevkit` for the full skill; don't
reinvent fixture loading per project.

## Mock only when unavoidable

Prefer a full simulation of the third-party system over mocking calls to it,
especially for anything with a read/write round trip (write a row, then read
it back) — a mock that always returns the same canned response can't catch
that kind of bug, a real fake server can. A stdlib-only fake HTTP server
standing in for the real service (own process, real request parsing, keeps
state across calls) is usually worth the extra setup. Reach for
`page.route()`-style request mocking only for the narrow cases a full fake
isn't worth building for, e.g. a genuinely external service outside the
team's control, or a frontend-only test that has no interest in backend
behavior at all.
