#!/usr/bin/env bash
# Sets a work item's System.State via the Azure DevOps REST API. issues.py
# doesn't expose this (only list/get/report/assign/auto-assign), so this
# talks to the same API directly, reusing the same auth as issues.py.
# Usage: set_state.sh <id> <state>
# <state> must be one of THIS project's real state names (e.g. "Done") --
# don't guess a generic-sounding one; run `list.sh` with no filter first if
# unsure what they are.
set -euo pipefail
ID="$1"
STATE="$2"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTH="$("$SCRIPT_DIR/auth_token.sh")"

curl -sf -X PATCH \
  -H "Authorization: $AUTH" \
  -H "Content-Type: application/json-patch+json" \
  -d "[{\"op\":\"add\",\"path\":\"/fields/System.State\",\"value\":\"$STATE\"}]" \
  "https://dev.azure.com/bmeurope/BMS%20-%20Data/_apis/wit/workitems/$ID?api-version=7.0"
