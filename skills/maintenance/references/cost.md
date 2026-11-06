# maintenance: cost

Did Azure spend spike, and is it a real change or a mistake. Read-only: the data comes from the Cost Management
API, Resource Graph and the Activity Log, not from guesses. The output is issues (and PRs for small clear fixes,
e.g. a SKU in a Bicep file); never change, scale or delete anything in Azure from this mode.

Uses the [`azure-cost`](../../azure-cost/SKILL.md) skill for the queries and its guardrails (4 requests/minute per
scope: space calls, don't retry blind). Needs `az login` and Cost Management Reader on the scope; step 2 also needs Reader on the resources (Resource Graph, Activity Log) and step 3 Reader on the subscription (scheduled actions, budgets). A 403 is a missing role, not "no evidence" or "no alert": report it as that. Scope = the repo's
`AZURE_RESOURCE_GROUP` (`bdt env`, as in [prod.md](prod.md)) first; if the repo has none, the subscription from
`az account show`.

## 1. Find the spike

```bash
python ../../azure-cost/scripts/cost_spike.py --resource-group "$AZURE_RESOURCE_GROUP"   # by service, last 31 days
```

Last 3 complete days vs the median of the 28 before, today excluded (cost data lags and is partial). Nothing flagged:
say so with the numbers (total per day, window) and stop; don't lower the thresholds until something shows up.
Slow creep doesn't show up in it (3 days vs a median): also compare the same window against last month with a
`Custom` timeframe, per [cost-query.md](../../azure-cost/references/cost-query.md#workflow) step 3, once a quarter or
when the bill feels off.

## 2. Name the cause

For each flagged service, one at a time (rate limit):

```bash
python ../../azure-cost/scripts/cost_spike.py --resource-group "$AZURE_RESOURCE_GROUP" --group-by ResourceId --service "<ServiceName>"
```

Then what changed on that resource, from Azure, in the window of the spike's first day:

```bash
az extension add --name resource-graph          # once
az graph query -q "resourcechanges | where properties.targetResourceId =~ '<resource id>' | where todatetime(properties.changeAttributes.timestamp) > ago(14d) | project ts=properties.changeAttributes.timestamp, type=properties.changeType, by=properties.changeAttributes.changedBy, changes=properties.changes"
az graph query -q "resourcechanges | where properties.changeType == 'Create' and todatetime(properties.changeAttributes.timestamp) > ago(14d) | project ts=properties.changeAttributes.timestamp, id=properties.targetResourceId, by=properties.changeAttributes.changedBy"
az monitor activity-log list -g "$AZURE_RESOURCE_GROUP" --offset 14d --status Succeeded \
  --query "[?contains(operationName.value,'write') || contains(operationName.value,'delete')].{ts:eventTimestamp, op:operationName.value, res:resourceId, by:caller}" -o table
```

The second query lists everything created in the window (a new resource appears in the cost as `new`).
The Activity Log keeps 90 days.

Then match to the likely type of cause:

| Signal | Usual cause | Check |
|---|---|---|
| New resource, `new` in the spike | a deployment, a forgotten test resource | creator and deployment in the Activity Log; is it in the repo's Bicep? |
| Same resource, step up on one day | SKU / instance / replica change, autoscale at max, retention or tier change | `resourcechanges` diff; app/code deploy of that day (`git log --since`) |
| Log Analytics / App Insights / Storage transactions | a new noisy log line, debug level left on, a retry loop | ingestion per table (`Usage | summarize sum(Quantity) by DataType` via `az monitor log-analytics query`), see [prod.md](prod.md) |
| Databricks / compute | a job without a timeout or cluster that never terminates | the job runs; `databricks-cli` skill |
| Data transfer, Storage egress | a new consumer, a public endpoint | `MeterCategory`/`MeterSubCategory` grouping |

Don't stop at "service X is up 3x": the finding is the resource, the day and what changed that day. Not found in
the changes: say "cause unknown", with what was checked.

## 3. Is there a safety net

```bash
az consumption budget list -g "$AZURE_RESOURCE_GROUP" -o table          # no -g for the subscription's budgets
az rest --method GET --url "https://management.azure.com/subscriptions/$SUB/providers/Microsoft.CostManagement/scheduledActions?api-version=2023-11-01" \
  --query "value[?kind=='InsightAlert'].{name:name, status:properties.status, to:properties.notification.to}"
```

No budget with notifications (`Microsoft.Consumption/budgets`), or no `InsightAlert` (the anomaly alert, a
`scheduledActions` resource; it watches the subscription's daily total, so a spike in one resource group can stay
below its radar): that's an issue, "add budget/anomaly alert", with the monthly figure for the budget taken from the last
full month, not a guess. Alerts are created in the portal or Bicep (`Microsoft.Consumption/budgets`); not from this mode.

## 4. Estimate vs bill, parameters (only if the repo has Bicep)

Find the templates (`**/*.bicep`, `*.bicepparam`) and follow [bicep-cost.md](../../azure-cost/references/bicep-cost.md):

```bash
uvx bicep-cost collect <main.bicep> -p <prod.bicepparam> --resource-group "$AZURE_RESOURCE_GROUP" --days 60
uvx bicep-cost estimate <main.bicep> -p <prod.bicepparam> --currency <billing currency> --detail
```

Three things come out of it:

- **Drift** between template and live (instances, storage size): first rule out intended drift (PostgreSQL
  storage auto-grow, autoscale); otherwise the template is wrong or someone changed prod by
  hand. A small, clear case is a PR fixing the template; otherwise an issue.
- **Stale usage file**: commit the refreshed `*.usage.toml` when measured values moved by more than ~25 %, in
  a separate commit; the PR estimate guard (`--fail-increase-percent`) is only as good as it. Keep hand-written
  overrides in their own file.
- **Estimate far from actual** on a resource: see the list in bicep-cost.md; an unmodelled meter is a PR or issue on
  the `bicep-cost` repo, not a reason to ignore the figure.

## Report

Per scope: window and currency, total per day, flagged groups (baseline → recent per day, delta, first day), the
named cause with its evidence (resource id, Activity Log entry or `resourcechanges` row, deploy), budgets/anomaly
alert present or missing, bicep-cost drift. Issues: `bdt issue search --state all --since-days 0 "<resource or
service>"` first (see SKILL.md), one per root cause, with the figures and the commands that produced them. Don't
paste caller emails of non-colleagues or secrets from resource properties.
