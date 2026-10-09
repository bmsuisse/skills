#!/usr/bin/env bash
# Usage: python_audit.sh [path=.] [min-confidence=80]
# Read-only dead-code and dependency audit for a Python project (run from the project root).
# Needs: uv. Everything else runs through uvx / uv run, nothing is installed permanently.
here=$(cd "$(dirname "$0")" && pwd); . "$here/common.sh"
path=${1:-.}; conf=${2:-80}
have uv || { echo "uv not found: https://docs.astral.sh/uv/"; exit 1; }

# Optional whitelist of known false positives (framework entry points, dunder hooks, public API).
wl=(); [ -f vulture_whitelist.py ] && wl=(vulture_whitelist.py)

run "vulture: unused functions/classes/variables (confidence >= $conf, heuristic: review before deleting)" \
  uvx vulture "$path" "${wl[@]}" --min-confidence "$conf" --exclude ".venv,venv,node_modules,build,dist,migrations"

run "ruff: unused imports (F401), unused locals (F841), unused arguments (ARG)" \
  uvx ruff check "$path" --select F401,F841,ARG --no-fix --output-format concise

# deptry maps imports to packages, so it must run inside the project's environment.
run "deptry: unused / missing / transitive dependencies" \
  uv run --with deptry deptry "$path"

run "outdated direct dependencies" uv tree --outdated --depth 1

section "pip-audit: known vulnerabilities"
tmp=$(mktemp)
if uv export --frozen --no-hashes --no-emit-project -o "$tmp" >/dev/null 2>&1; then
  uvx pip-audit -r "$tmp" --no-deps --disable-pip 2>&1 || echo "(findings above, or the tool could not run)"
else
  echo "(skipped: no uv.lock / uv export failed)"
fi
rm -f "$tmp"

section "next step"
echo "Code that tests never execute is the other dead-code signal: uv run coverage run -m pytest && uv run coverage report -m"
