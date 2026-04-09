#!/usr/bin/env bash
# find_python.sh — resolves the Python 3 executable and exports it as $PYTHON.
# Source this file before running any Python scripts:
#
#   source scripts/find_python.sh
#   $PYTHON some_script.py
#
# Or call it directly to print the resolved path:
#
#   bash scripts/find_python.sh          → prints resolved path
#   PYTHON=$(bash scripts/find_python.sh) → captures it in a variable

_find_python() {
  for candidate in python3 python python3.12 python3.11 python3.10; do
    if command -v "$candidate" &>/dev/null; then
      local ver
      ver=$("$candidate" -c "import sys; print(sys.version_info.major)" 2>/dev/null)
      if [[ "$ver" == "3" ]]; then
        echo "$candidate"
        return 0
      fi
    fi
  done
  echo "Error: no Python 3 interpreter found. Install Python 3 and retry." >&2
  return 1
}

# When sourced, export $PYTHON. When run directly, print the path.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  _find_python
else
  PYTHON=$(_find_python) && export PYTHON
fi
