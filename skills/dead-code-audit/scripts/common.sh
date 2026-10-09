# Shared helpers, sourced by the audit scripts. Read-only: nothing is modified or deleted.

section() { printf '\n## %s\n' "$1"; }

# run <label> <cmd...>: print output, never abort the audit if one tool fails or is missing.
run() {
  local label=$1; shift
  section "$label"
  "$@" 2>&1
  local rc=$?
  # Most of these tools exit non-zero when they find something; that is a result, not a failure.
  [ $rc -eq 0 ] && echo "(clean)" || echo "(exit $rc: findings above, or the tool could not run)"
}

have() { command -v "$1" >/dev/null 2>&1; }
