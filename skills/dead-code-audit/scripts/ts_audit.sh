#!/usr/bin/env bash
# Usage: ts_audit.sh [path=.]
# Read-only dead-code and dependency audit for a TypeScript/JS/Vue/React project (run from the project root).
here=$(cd "$(dirname "$0")" && pwd); . "$here/common.sh"
path=${1:-.}; cd "$path" || exit 1
[ -f package.json ] || { echo "no package.json in $path"; exit 1; }

# bun if the project uses it, else npm. x = one-off package runner.
if [ -f bun.lock ] || [ -f bun.lockb ]; then x=(bunx); pm=bun; else x=(npx --yes); pm=npm; fi
src=src; [ -d src ] || src=.

run "knip: unused files, exports, types, dependencies (supports Vue; review before deleting)" "${x[@]}" knip

tsc=tsc; grep -q '"vue"' package.json && tsc="vue-tsc"
run "$tsc: unused locals and parameters" "${x[@]}" "$tsc" --noEmit --noUnusedLocals --noUnusedParameters

# madge cannot parse .vue and ignores path aliases unless given the tsconfig; knip above is the reliable source.
ts=(); [ -f tsconfig.json ] && ts=(--ts-config tsconfig.json)
run "madge: circular dependencies (ts/js only)" "${x[@]}" madge --circular --extensions ts,tsx,js,jsx "${ts[@]}" "$src"
run "madge: orphan modules, advisory only: aliased/Vue imports can look orphaned, cross-check with knip" "${x[@]}" madge --orphans --extensions ts,tsx,js,jsx "${ts[@]}" "$src"

run "outdated dependencies" $pm outdated

section "known vulnerabilities"
if have osv-scanner; then osv-scanner scan source -r . 2>&1; else $pm audit 2>&1; fi
echo "(exit $?: 0 = none found; otherwise findings above, or the tool/subcommand is unavailable, e.g. old bun without 'bun audit')"
