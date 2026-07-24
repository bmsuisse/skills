#!/usr/bin/env bash
# Lists issues from issues.py directly — no justfile/just dependency.
# Usage: list.sh <repo_root> [--state STATE] [--assigned-to PERSON]
set -euo pipefail
REPO_ROOT="$1"
shift
cd "$REPO_ROOT"
uv run issues.py list "$@"
