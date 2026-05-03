#!/usr/bin/env python3
"""Take a screenshot of a URL and print the file path.

Designed to be called from Bash. The path on stdout is the only
machine-readable output — everything else goes to stderr. The caller
(typically Claude via the Read tool) can then load the PNG directly.

Usage:
    screenshot.py URL [--selector CSS] [--full-page] [--wait-for CSS]
                       [--wait-until {load,domcontentloaded,networkidle}]
                       [--width N] [--height N] [--out PATH]
                       [--browser {chromium,firefox,webkit}]
                       [--storage-state PATH]
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright


def default_output_path(url: str) -> Path:
    tmp = Path(os.environ.get("TMPDIR", "/tmp")) / "playwright-screenshots"
    tmp.mkdir(parents=True, exist_ok=True)
    host = urlparse(url).hostname or "page"
    slug = re.sub(r"[^a-z0-9]+", "-", host.lower()).strip("-") or "page"
    return tmp / f"{slug}-{int(time.time() * 1000)}.png"


async def capture(args: argparse.Namespace) -> Path:
    out = Path(args.out) if args.out else default_output_path(args.url)
    out.parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as pw:
        browser_type = getattr(pw, args.browser)
        browser = await browser_type.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": args.width, "height": args.height},
            storage_state=args.storage_state if args.storage_state else None,
        )
        page = await context.new_page()
        try:
            await page.goto(args.url, wait_until=args.wait_until, timeout=args.timeout)
            if args.wait_for:
                await page.wait_for_selector(args.wait_for, timeout=args.timeout)

            if args.selector:
                element = await page.wait_for_selector(args.selector, timeout=args.timeout)
                await element.screenshot(path=str(out))
            else:
                await page.screenshot(path=str(out), full_page=args.full_page)
        finally:
            await context.close()
            await browser.close()

    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("url", help="URL to screenshot (include scheme: http://, https://, file://)")
    p.add_argument("--selector", help="CSS selector to screenshot a single element instead of the page")
    p.add_argument("--full-page", action="store_true", help="Scroll and capture the full page height")
    p.add_argument("--wait-for", help="CSS selector to wait for before capturing (best for SPAs)")
    p.add_argument(
        "--wait-until",
        choices=["load", "domcontentloaded", "networkidle", "commit"],
        default="load",
        help="Navigation wait strategy (default: load)",
    )
    p.add_argument("--width", type=int, default=1280, help="Viewport width (default: 1280)")
    p.add_argument("--height", type=int, default=800, help="Viewport height (default: 800)")
    p.add_argument("--timeout", type=int, default=30_000, help="Per-step timeout in ms (default: 30000)")
    p.add_argument("--out", help="Output path (default: $TMPDIR/playwright-screenshots/<slug>-<ts>.png)")
    p.add_argument("--browser", choices=["chromium", "firefox", "webkit"], default="chromium")
    p.add_argument("--storage-state", help="Path to a Playwright storage_state.json for authenticated sessions")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    try:
        path = asyncio.run(capture(args))
    except Exception as exc:
        print(f"screenshot failed: {exc}", file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
