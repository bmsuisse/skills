import os
import sys
from collections.abc import Callable, Iterable
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Any


def run_in_processpool(
    func: Callable[..., Any],
    iterable: Iterable[tuple[Any, ...]],
    max_workers: int | None = None,
    desc: str | None = None,
) -> list[Any]:
    results: list[Any] = []
    items = list(iterable)
    total = len(items)
    label = f"{desc}: " if desc else ""

    if max_workers is None:
        max_workers = os.cpu_count() or 4

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(func, *args): args for args in items}

        for completed, future in enumerate(as_completed(futures), start=1):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"Error processing {futures[future]}: {e}", file=sys.stderr)

            pct = completed * 100 // total
            bar = "#" * (pct // 5) + "-" * (20 - pct // 5)
            print(f"\r  {label}[{bar}] {completed}/{total} ({pct}%)", end="", file=sys.stderr, flush=True)

    print(f"\r  {label}done ({total} files)        ", file=sys.stderr)
    return results
