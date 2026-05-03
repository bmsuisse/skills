#!/usr/bin/env python3
"""Dump a page's accessibility tree (or visible text) as YAML/text.

Cheaper than a screenshot when you only need to verify content,
find selectors, or check that an element exists. The accessibility
tree is what screen readers see — roles, names, values — which is
also a great target for writing stable Playwright locators.

Usage:
    snapshot.py URL [--text] [--selector CSS] [--wait-for CSS]
                     [--wait-until {load,domcontentloaded,networkidle}]
                     [--out PATH]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright


def default_output_path(url: str, ext: str) -> Path:
    tmp = Path(os.environ.get("TMPDIR", "/tmp")) / "playwright-snapshots"
    tmp.mkdir(parents=True, exist_ok=True)
    host = urlparse(url).hostname or "page"
    return tmp / f"{host}-{int(time.time() * 1000)}.{ext}"


async def capture(args: argparse.Namespace) -> tuple[Path, str]:
    ext = "txt" if args.text else "json"
    out = Path(args.out) if args.out else default_output_path(args.url, ext)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        try:
            await page.goto(args.url, wait_until=args.wait_until, timeout=args.timeout)
            if args.wait_for:
                await page.wait_for_selector(args.wait_for, timeout=args.timeout)

            if args.text:
                if args.selector:
                    el = await page.wait_for_selector(args.selector, timeout=args.timeout)
                    content = (await el.inner_text()).strip()
                else:
                    content = (await page.inner_text("body")).strip()
            else:
                root = await page.locator(args.selector).element_handle() if args.selector else None
                tree = await page.accessibility.snapshot(root=root, interesting_only=True)
                content = json.dumps(tree, indent=2, ensure_ascii=False)
        finally:
            await context.close()
            await browser.close()

    out.write_text(content, encoding="utf-8")
    return out, content


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("url", help="URL to inspect")
    p.add_argument("--text", action="store_true", help="Dump visible text instead of the accessibility tree")
    p.add_argument("--selector", help="Limit snapshot to a CSS selector")
    p.add_argument("--wait-for", help="CSS selector to wait for before capturing")
    p.add_argument(
        "--wait-until",
        choices=["load", "domcontentloaded", "networkidle", "commit"],
        default="load",
    )
    p.add_argument("--timeout", type=int, default=30_000)
    p.add_argument("--out", help="Output path (default: $TMPDIR/playwright-snapshots/...)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    try:
        path, _ = asyncio.run(capture(args))
    except Exception as exc:
        print(f"snapshot failed: {exc}", file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
