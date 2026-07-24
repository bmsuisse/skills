#!/usr/bin/env bash
# Runs the open-issues report from issues.py directly — no justfile/just dependency.
# Usage: report.sh <repo_root> [output_path]
set -euo pipefail
REPO_ROOT="$1"
OUTPUT="${2:-}"
cd "$REPO_ROOT"
if [ -n "$OUTPUT" ]; then
  uv run issues.py report --output "$OUTPUT"
else
  uv run issues.py report
fi
