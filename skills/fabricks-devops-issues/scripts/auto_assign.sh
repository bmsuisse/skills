#!/usr/bin/env bash
# Runs issues.py auto-assign directly — no justfile/just dependency.
# Usage: auto_assign.sh <repo_root> [--dry-run] [--id N]
set -euo pipefail
REPO_ROOT="$1"
shift
cd "$REPO_ROOT"
uv run issues.py auto-assign "$@"
