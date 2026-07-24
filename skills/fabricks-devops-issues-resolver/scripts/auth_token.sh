#!/usr/bin/env bash
# Prints a bearer token for the Azure DevOps REST API, same auth path as
# issues.py's _get_auth_header(): AZURE_DEVOPS_PAT env var first, else an
# az CLI access token for the DevOps resource ID. No shell=True/list bug
# here since this is a plain bash invocation, not Python subprocess.
set -euo pipefail
if [ -n "${AZURE_DEVOPS_PAT:-}" ]; then
  TOKEN=$(printf ':%s' "$AZURE_DEVOPS_PAT" | base64 | tr -d '\n')
  echo "Basic $TOKEN"
else
  TOKEN=$(az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798 --query accessToken -o tsv)
  echo "Bearer $TOKEN"
fi
