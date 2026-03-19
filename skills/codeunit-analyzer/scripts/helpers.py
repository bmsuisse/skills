import sys
from concurrent.futures import ThreadPoolExecutor, as_completed


def run_in_threadpool(func, iterable, max_workers=32, desc=None):
    """Run a function with multiple argument sets in a thread pool.

    Prints a live progress line to stderr while working.

    Args:
        func: Function to execute
        iterable: Iterable of argument tuples
        max_workers: Max number of parallel threads
        desc: Optional label shown in the progress line

    Returns:
        List of results (order not guaranteed)
    """
    results = []
    items = list(iterable)
    total = len(items)
    label = f"{desc}: " if desc else ""

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
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

    # Clear the progress line
    print(f"\r  {label}done ({total} files)        ", file=sys.stderr)
    return results
