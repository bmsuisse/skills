---
name: playwright-python
description: Browser automation and visual verification with Playwright in Python. Use this whenever the user wants to drive a browser from Python — taking screenshots of a running dev server or deployed page, scraping rendered content, automating clicks/forms, mocking network requests, or writing pytest browser tests. Also use this when the user wants Claude to "see" what a UI looks like (the bundled screenshot helper drops a PNG in $TMPDIR which Claude can read directly), when they mention pytest-playwright, when they say things like "verify my dashboard renders" / "screenshot localhost" / "test the signup flow in a browser", or any time a task needs a real rendered page rather than raw HTML. Async API is the default; sync and pytest patterns are documented inline.
---

# Playwright in Python

Playwright drives a real browser (Chromium/Firefox/WebKit) from Python. Use it for three things in this repo:

1. **Visual verification** — screenshot a running app so Claude can `Read` the PNG and see what the user sees. This closes the loop when iterating on a UI: edit code → screenshot → look → edit again.
2. **Scraping rendered pages** — anything that needs JavaScript to run (SPAs, dashboards, lazy-loaded data).
3. **End-to-end testing with pytest** — `pytest-playwright` ships fixtures so each test gets a fresh `page`.

The async API is the default. Use sync only when calling from a script that can't run an event loop (rare) or from a notebook that already has one running (also rare; prefer async there too).

## When NOT to use this

- The page is plain HTML with no JS — `httpx` or `requests` + `selectolax`/`beautifulsoup4` is faster and lighter.
- You need a headless API client — Playwright is for *browsers*. Use `httpx` for raw HTTP.
- The reference skill `microsoft/playwright-cli` is a stateful Node CLI; this skill is the Python alternative. Don't conflate them.

## Install (handle this first if missing)

Playwright has two install steps that are easy to forget:

```bash
# 1. Python package
pip install playwright            # or: uv add playwright

# 2. Browser binaries (downloads ~200MB; required on first use)
playwright install chromium       # add firefox / webkit as needed
```

If you're writing pytest tests, also install the pytest plugin:

```bash
pip install pytest-playwright
```

**Detect what's missing**:

```bash
python -c "import playwright" 2>/dev/null && echo "package: ok" || echo "package: missing"
python -c "from playwright.sync_api import sync_playwright; \
  p=sync_playwright().start(); \
  p.chromium.launch(headless=True).close(); p.stop()" 2>&1 | grep -q "Executable doesn't exist" \
  && echo "browsers: missing — run 'playwright install chromium'" \
  || echo "browsers: ok"
```

If a Playwright call fails with `Executable doesn't exist at /…/chromium-XXXX/`, that's the browser-binary step — run `playwright install chromium` and retry.

## Bundled helpers

Three scripts live in `scripts/` next to this file. Reach for them before writing a one-off Playwright snippet — they handle waits, viewport, and `$TMPDIR` output correctly so you don't reinvent that each time. Each answers a different question about the page:

| Helper | Question it answers | Output | When to use |
|---|---|---|---|
| `screenshot.py` | What does the page **look** like? | PNG in `$TMPDIR/playwright-screenshots/` | Layout, styling, visual bugs, "does this render right?" |
| `dom.py` | What's the **structure**? | HTML in `$TMPDIR/playwright-dom/` | Find selectors, inspect classes/data-attrs, diff page states |
| `snapshot.py` | What's **on** the page? | JSON or text in `$TMPDIR/playwright-snapshots/` | Verify text, discover `role`+`name` for stable locators |

Pick the cheapest one that answers your question — text < accessibility tree < HTML < pixels in token cost.

### `scripts/screenshot.py` — visual feedback loop

```bash
# Basic: full viewport screenshot, prints PNG path to stdout
python scripts/screenshot.py http://localhost:3000

# SPA that loads data after navigation — wait for a specific element
python scripts/screenshot.py http://localhost:5173 --wait-for '[data-testid="chart"]'

# Just one element
python scripts/screenshot.py http://localhost:3000 --selector 'header nav'

# Full page (scrolls and stitches)
python scripts/screenshot.py https://example.com --full-page

# Authenticated session — pass a Playwright storage_state.json
python scripts/screenshot.py http://localhost:3000/admin --storage-state ./auth.json
```

The path on stdout is the only machine-readable line — capture it and `Read` the PNG:

```bash
SHOT=$(python scripts/screenshot.py http://localhost:3000)
# then: Read tool on $SHOT — the image renders in context
```

**The pattern that matters** (this is the whole reason for the helper): when iterating on a UI, run the user's dev server, screenshot the page, `Read` the file, observe what's broken, edit code, screenshot again. The image is the source of truth — don't infer from CSS what the page looks like.

### `scripts/dom.py` — rendered HTML

When you need the *structure* — classes, data-attributes, raw markup that the accessibility tree drops:

```bash
# Whole page (post-JS render — what `requests` can't give you)
python scripts/dom.py https://example-spa.local

# Scoped to a region (recommended — full pages are huge)
python scripts/dom.py https://example-spa.local --selector 'main'

# Wait for an SPA to settle
python scripts/dom.py http://localhost:5173 --wait-for '[data-testid="ready"]'

# Pretty-print (uses BeautifulSoup if installed; otherwise raw)
python scripts/dom.py https://example.com --selector 'form' --pretty
```

Reach for this when:
- You need a stable selector (find a `data-testid`, `id`, or distinctive class).
- The accessibility tree omits something you need (icon-only buttons, custom elements, hidden inputs).
- You want to diff the rendered HTML before/after an interaction.

### `scripts/snapshot.py` — accessibility tree / text dump

When you only need to know what's on the page (text or roles), no markup:

```bash
# Accessibility tree as JSON — roles, names, values
python scripts/snapshot.py http://localhost:3000

# Visible text only
python scripts/snapshot.py http://localhost:3000 --text

# Scope to a region
python scripts/snapshot.py http://localhost:3000 --text --selector 'main'
```

Use this to:
- Check that expected text is on the page without paying for a PNG or full HTML.
- Find stable locators — the accessibility tree shows the `role` + `name` you'd pass to `get_by_role()`.

## Writing scripts directly (async-first)

When a task is more involved than "screenshot this URL", write Python with `async_playwright`. Skeleton:

```python
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()

        await page.goto("http://localhost:3000", wait_until="load")
        await page.get_by_role("button", name="Sign in").click()
        await page.get_by_label("Email").fill("user@example.com")
        await page.get_by_label("Password").fill("hunter2")
        await page.get_by_role("button", name="Submit").click()
        await page.wait_for_url("**/dashboard")

        await page.screenshot(path="/tmp/after-login.png", full_page=True)
        await context.close()
        await browser.close()

asyncio.run(main())
```

### Sync API (only if you must)

Same surface, different package — drop the `await`s and use `with sync_playwright()`. Useful in REPLs, simple scripts, or when bridging into sync code that can't host an event loop:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://example.com")
    page.screenshot(path="/tmp/example.png")
    browser.close()
```

Don't mix `sync_api` and `asyncio` in the same process — the sync API is implemented on top of a private greenlet and will deadlock if there's already an event loop running.

## Locators — choose them well

Locator quality determines whether your script breaks the moment a designer renames a class. Order of preference:

1. **Role + name** — what users (and screen readers) see. Stable across visual redesigns.
   `page.get_by_role("button", name="Submit")`
2. **Test IDs** — explicit hooks added for automation.
   `page.get_by_test_id("submit-button")`
3. **Label / placeholder / text** — readable, decent stability.
   `page.get_by_label("Email")`, `page.get_by_text("Welcome back")`
4. **CSS / XPath** — last resort. Brittle to refactors.
   `page.locator("#main > button.submit-btn")`

The accessibility-tree snapshot (`scripts/snapshot.py`) is the easiest way to discover the `role`+`name` pairs that already exist on a page.

### Anti-patterns — selectors that look fine and aren't

These all *seem* specific but are dead the moment the framework, build, or vendor ships an update:

- **Hashed / atomic CSS classes** — `.btn-primary-x9Yq`, `.css-1a2b3c`, `._btn__hash`. Generated by Tailwind JIT, CSS-in-JS, CSS modules. Change every build.
- **Auto-generated IDs** — `#:r17:` (React 18 `useId`), `#mui-42` (MUI), `#headlessui-button-7`, `#radix-:r3:`. Re-rendered means re-numbered.
- **XPath positional selectors** — `//div[3]/button[1]`, `(//button)[2]`. Break the moment any sibling is reordered, added, or wrapped.
- **`nth=` indexing** as a primary strategy — `page.locator("button").nth(2)`. Same problem as positional XPath; fine as a *tiebreaker* on a stable parent locator, terrible on its own.
- **Bare `text=` matches** without a role — `page.locator("text=Continue")` matches `<p>Click Continue to proceed</p>` too. Prefer `get_by_role("button", name="Continue")`, which constrains to actual buttons.

If you must use a CSS selector, anchor it to something the vendor or your own code controls intentionally — `data-testid`, a stable `id` (one that doesn't look auto-generated), or a vendor-namespaced attribute (`data-stripe-element`, `aria-label`). Never anchor to classes you didn't write yourself.

## Waits — pick the right one, not all of them

Most flaky Playwright code is bad waiting. Defaults:

- `page.goto(url, wait_until="load")` — solid default for traditional pages.
- `page.goto(url, wait_until="domcontentloaded")` — the page exists but JS may still be running. Almost never what you want for SPAs.
- `page.goto(url, wait_until="networkidle")` — waits for 500ms with zero in-flight requests. **Avoid for apps that poll** (websockets, analytics) — it'll hang.
- `await page.wait_for_selector("…")` / `expect(locator).to_be_visible()` — wait for *the thing you actually need*. This is the most reliable strategy.

Locators auto-wait by default: `await page.get_by_role("button").click()` already retries until the element is visible and stable. You usually don't need explicit waits before actions — only before assertions or before reading content.

## Authenticated sessions — `storage_state`

Don't log in inside every test or script. Log in once, save the cookies + localStorage, reuse:

```python
# one-time login script
async with async_playwright() as pw:
    browser = await pw.chromium.launch(headless=False)  # headed so user can solve CAPTCHA / 2FA if needed
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto("http://localhost:3000/login")
    # ...do the login...
    await context.storage_state(path="auth.json")
```

Then load it in subsequent runs: `new_context(storage_state="auth.json")`. The screenshot helper takes `--storage-state auth.json` for this.

## Network mocking

Stub external calls so tests don't depend on real APIs:

```python
async def fake_users(route):
    await route.fulfill(json={"users": [{"id": 1, "name": "Alice"}]})

await context.route("**/api/users", fake_users)
```

Block whole resource categories to speed up tests:

```python
await context.route("**/*.{png,jpg,svg,woff2}", lambda r: r.abort())
```

## Tracing — gold for debugging flaky tests

If a test fails and you can't tell why, turn on tracing:

```python
await context.tracing.start(screenshots=True, snapshots=True, sources=True)
try:
    # ...steps...
finally:
    await context.tracing.stop(path="trace.zip")
```

Open the result with `playwright show-trace trace.zip` — you get a frame-by-frame timeline with DOM snapshots and network calls. Worth its weight in gold for "it passes locally but fails in CI".

## Pytest with `pytest-playwright`

The plugin gives you a `page` fixture per test (fresh browser context, isolated storage). Tests are sync by default — the plugin runs them in a thread that hosts the sync API.

```python
# tests/test_signup.py
from playwright.sync_api import Page, expect

def test_signup_flow(page: Page):
    page.goto("http://localhost:3000/signup")
    page.get_by_label("Email").fill("new@example.com")
    page.get_by_label("Password").fill("hunter2-pls")
    page.get_by_role("button", name="Create account").click()
    expect(page).to_have_url("**/welcome")
    expect(page.get_by_text("Welcome, new@example.com")).to_be_visible()
```

Useful CLI flags:

```bash
pytest --headed                      # see what's happening
pytest --slowmo 500                  # add 500ms between actions, debug-friendly
pytest --browser firefox             # cross-browser
pytest --browser chromium --browser firefox --browser webkit  # all three
pytest --video on --screenshot on    # artifacts on failure
pytest --tracing retain-on-failure   # tracing for failed tests only
```

`expect(...)` is the Playwright assertion helper — it auto-retries until the condition holds (or timeout). Don't replace it with raw `assert` on `page.is_visible()`; the latter snapshots the state once and gives you the flaky test you were trying to avoid.

### Screenshot-on-failure for any test

Add to `conftest.py`:

```python
import pytest

@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.when == "call" and rep.failed:
        page = item.funcargs.get("page")
        if page:
            path = f"/tmp/pytest-failures/{item.name}.png"
            page.screenshot(path=path, full_page=True)
            print(f"\nfailure screenshot: {path}")
```

## Cheat sheet

| Task | Code |
|---|---|
| Open page | `await page.goto(url, wait_until="load")` |
| Click | `await page.get_by_role("button", name="X").click()` |
| Fill | `await page.get_by_label("Email").fill("…")` |
| Press key | `await page.keyboard.press("Enter")` |
| Wait for content | `await page.wait_for_selector("[data-loaded]")` |
| Wait for URL | `await page.wait_for_url("**/done")` |
| Read text | `await page.get_by_role("heading").inner_text()` |
| Read rendered HTML | `await page.content()` (full page) or `await locator.evaluate("el => el.outerHTML")` |
| Eval JS | `await page.evaluate("() => document.title")` |
| Screenshot | `await page.screenshot(path="…", full_page=True)` |
| New tab | `page2 = await context.new_page()` |
| Save auth | `await context.storage_state(path="auth.json")` |
| Mock API | `await context.route("**/api/x", handler)` |
| Block resources | `await context.route("**/*.png", lambda r: r.abort())` |

## Common pitfalls

- **"It works headed but fails headless"** — usually a timing or viewport issue. Add `--wait-for` for the element you depend on, and set an explicit viewport in the context (the headless default is small).
- **Tests pass locally, fail in CI** — fonts/animations differ. For visual diffs, set `animations="disabled"` on `page.screenshot()`. For element-presence flakiness, lean on `expect(...)` rather than `is_visible()`.
- **`Executable doesn't exist`** — browser binaries not installed. Run `playwright install chromium`.
- **`Event loop is already running`** — you tried to use `sync_playwright` from inside an async context (e.g., a Jupyter cell). Use `async_playwright` and `await` instead.
- **Hanging on `networkidle`** — the app polls or has a long-lived connection. Switch to `wait_until="load"` plus an explicit `wait_for_selector` on the element you actually need.
