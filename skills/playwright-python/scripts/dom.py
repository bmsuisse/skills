#!/usr/bin/env python3
"""Dump a page's fully-rendered DOM (post-JS HTML) to a file.

Use this when you need the *structure* — classes, data-attrs, raw
markup — beyond what the accessibility tree exposes. This is the
right tool when you want to grep for an element, find a stable
selector, or diff two states of a page.

Cost ladder (cheapest → richest):
    snapshot.py --text   → just visible text
    snapshot.py          → accessibility tree (roles + names)
    dom.py               → rendered HTML
    screenshot.py        → pixels

Usage:
    dom.py URL [--selector CSS] [--wait-for CSS]
                [--wait-until {load,domcontentloaded,networkidle}]
                [--pretty] [--out PATH]
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright


def default_output_path(url: str) -> Path:
    tmp = Path(os.environ.get("TMPDIR", "/tmp")) / "playwright-dom"
    tmp.mkdir(parents=True, exist_ok=True)
    host = urlparse(url).hostname or "page"
    return tmp / f"{host}-{int(time.time() * 1000)}.html"


def pretty_print_html(html: str) -> str:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return html
    return BeautifulSoup(html, "html.parser").prettify()


async def capture(args: argparse.Namespace) -> Path:
    out = Path(args.out) if args.out else default_output_path(args.url)
    out.parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        try:
            await page.goto(args.url, wait_until=args.wait_until, timeout=args.timeout)
            if args.wait_for:
                await page.wait_for_selector(args.wait_for, timeout=args.timeout)

            if args.selector:
                el = await page.wait_for_selector(args.selector, timeout=args.timeout)
                html = await el.evaluate("el => el.outerHTML")
            else:
                html = await page.content()
        finally:
            await context.close()
            await browser.close()

    if args.pretty:
        html = pretty_print_html(html)
    out.write_text(html, encoding="utf-8")
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("url", help="URL to capture")
    p.add_argument("--selector", help="Limit DOM dump to a CSS selector (recommended for big pages)")
    p.add_argument("--wait-for", help="CSS selector to wait for before capturing (best for SPAs)")
    p.add_argument(
        "--wait-until",
        choices=["load", "domcontentloaded", "networkidle", "commit"],
        default="load",
    )
    p.add_argument("--pretty", action="store_true", help="Pretty-print with BeautifulSoup if available")
    p.add_argument("--timeout", type=int, default=30_000)
    p.add_argument("--out", help="Output path (default: $TMPDIR/playwright-dom/...)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    try:
        path = asyncio.run(capture(args))
    except Exception as exc:
        print(f"dom capture failed: {exc}", file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
