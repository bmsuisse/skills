#!/usr/bin/env bash
# Adds a comment to a work item via the Azure DevOps REST API. issues.py
# doesn't expose this either -- same rationale as set_state.sh.
# Usage: add_comment.sh <id> <comment text>
set -euo pipefail
ID="$1"
TEXT="$2"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTH="$("$SCRIPT_DIR/auth_token.sh")"

PAYLOAD=$(python3 -c 'import json,sys; print(json.dumps({"text": sys.argv[1]}))' "$TEXT")

curl -sf -X POST \
  -H "Authorization: $AUTH" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  "https://dev.azure.com/bmeurope/BMS%20-%20Data/_apis/wit/workItems/$ID/comments?api-version=7.0-preview.3"
