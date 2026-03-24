import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed


def run_in_processpool(func, iterable, max_workers=None, desc=None):
    results = []
    items = list(iterable)
    total = len(items)
    label = f"{desc}: " if desc else ""

    if max_workers is None:
        max_workers = os.cpu_count() or 4

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(func, *args): args for args in items}

        completed = 0
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"Error processing {futures[future]}: {e}", file=sys.stderr)

            completed += 1
            pct = completed * 100 // total
            bar = "#" * (pct // 5) + "-" * (20 - pct // 5)
            print(f"\r  {label}[{bar}] {completed}/{total} ({pct}%)", end="", file=sys.stderr, flush=True)

    print(f"\r  {label}done ({total} files)        ", file=sys.stderr)
    return results
