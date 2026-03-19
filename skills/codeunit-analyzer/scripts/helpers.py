import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def run_in_threadpool(func, iterable, max_workers=32, desc=None, total=None):
    results = []
    iterable_as_list = list(iterable)
    actual_total = total or len(iterable_as_list)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(func, *args): args for args in iterable_as_list}

        completed_count = 0
        if desc:
            print(f"{desc}: 0/{actual_total}", end="", flush=True)

        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
                completed_count += 1

                if desc:
                    # Print progress update
                    print(f"\r{desc}: {completed_count}/{actual_total}", end="", flush=True)
            except Exception as e:
                print(f"\nError processing {futures[future]}: {e}", file=sys.stderr)

        if desc:
            print()  # Newline after progress complete

    return results


def get_search_root():
    """
    Get the root directory to search for codeunit files.

    Priority:
    1. CODEUNITS_DIR environment variable (if set, use its parent)
    2. Current working directory
    """
    if env_dir := os.environ.get("CODEUNITS_DIR"):
        return Path(env_dir).parent

    return Path.cwd()


def find_codeunit_files(root_dir=None, extensions=None):
    """
    Recursively find all codeunit files (.cs, .c-al) from root directory.

    Args:
        root_dir: Starting directory (defaults to get_search_root())
        extensions: File extensions to search for (defaults to ['.cs', '.c-al'])

    Returns:
        List of Path objects for all matching files, sorted by name
    """
    if root_dir is None:
        root_dir = get_search_root()
    else:
        root_dir = Path(root_dir)

    if extensions is None:
        extensions = ['.cs', '.c-al']

    files = []
    for ext in extensions:
        # Use rglob for recursive globbing
        files.extend(root_dir.rglob(f'*{ext}'))

    # Sort by filename for consistent ordering
    return sorted(files, key=lambda p: p.name)
