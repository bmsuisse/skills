import sys
from concurrent.futures import ThreadPoolExecutor, as_completed


def run_in_threadpool(func, iterable, max_workers=32):
    """Run a function with multiple argument sets in a thread pool.

    Args:
        func: Function to execute
        iterable: Iterable of argument tuples
        max_workers: Max number of parallel threads

    Returns:
        List of results (order not guaranteed)
    """
    results = []
    iterable_as_list = list(iterable)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Convert generator to list if needed
        futures = {executor.submit(func, *args): args for args in iterable_as_list}

        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"Error processing {futures[future]}: {e}", file=sys.stderr)

    return results
