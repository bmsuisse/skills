# maintenance: cost

Did Azure spend spike, and why. Read-only: the data comes from the Cost Management API, Resource Graph and the
Activity Log. The output is issues (PRs only for small clear fixes, e.g. a SKU in Bicep); never change, scale or
delete anything in Azure.

Uses the [`azure-cost`](../../azure-cost/SKILL.md) skill and its rate limit (4 requests/minute per scope). Needs
`az login`, Cost Management Reader on the scope, and Reader on the resources and subscription for steps 2-3; a 403 is a
missing role, report it as that, not as "no evidence". Scope: the repo's `AZURE_RESOURCE_GROUP` (`bdt env`, see
[prod.md](prod.md)), else the subscription from `az account show`.

## 1. Find the spike

```bash
uvx bicep-cost@latest spikes --resource-group "$AZURE_RESOURCE_GROUP"
```

Last 3 complete days vs the median of the 28 before. The newest days can lag up to ~72 h: if they look suspiciously
low, say so. Nothing flagged: report the numbers, skip step 2, continue with 3-4. Slow creep isn't caught: when the bill feels off, compare
against last month ([cost-query.md](../../azure-cost/references/cost-query.md#workflow) step 3).

## 2. Name the cause

Per flagged service, one at a time:

```bash
SUB=$(az account show --query id -o tsv)
uvx bicep-cost spikes --resource-group "$AZURE_RESOURCE_GROUP" --group-by ResourceId --service "<ServiceName>"
az extension add --name resource-graph          # once
az graph query --subscriptions "$SUB" -q "resourcechanges | where properties.targetResourceId =~ '<resource id>' | where todatetime(properties.changeAttributes.timestamp) > ago(14d) | project ts=properties.changeAttributes.timestamp, type=properties.changeType, by=properties.changeAttributes.changedBy, changes=properties.changes"
az graph query --subscriptions "$SUB" --first 1000 -q "resourcechanges | where resourceGroup =~ '$AZURE_RESOURCE_GROUP' | where properties.changeType == 'Create' and todatetime(properties.changeAttributes.timestamp) > ago(14d) | project ts=properties.changeAttributes.timestamp, id=properties.targetResourceId, by=properties.changeAttributes.changedBy"
az monitor activity-log list --resource-id '<resource id>' --offset 14d --max-events 1000 --status Succeeded \
  --query "[?contains(operationName.value,'write') || contains(operationName.value,'delete')].{ts:eventTimestamp, op:operationName.value, res:resourceId, by:caller}" -o table
```

| Signal | Usual cause | Check |
|---|---|---|
| `new` group | a deployment, a forgotten test resource | creator in the Activity Log; is it in the repo's Bicep? |
| Step up on one day | SKU/instance change, autoscale at max, retention or tier change | `resourcechanges` diff; `git log --since` for that day's deploy |
| Log Analytics / App Insights / Storage transactions | noisy log line, debug level left on, retry loop | ingestion per table (`az monitor log-analytics query`), see [prod.md](prod.md) |
| Databricks / compute | job without timeout, cluster that never terminates | the job runs (`databricks-cli` skill) |
| Data transfer / egress | new consumer, public endpoint | group by `MeterCategory` |

The finding is the resource, the day and what changed. Nothing found: "cause unknown", with what was checked.

## 3. Safety net

```bash
az consumption budget list -g "$AZURE_RESOURCE_GROUP" -o table          # without -g: the subscription's budgets
az rest --method GET --url "https://management.azure.com/subscriptions/$SUB/providers/Microsoft.CostManagement/scheduledActions?api-version=2023-11-01" \
  --query "value[?kind=='InsightAlert'].{name:name, status:properties.status, to:properties.notification.to}"
```

No budget with notifications, or no `InsightAlert` anomaly alert (it watches the subscription's daily total, so a
single resource group's spike can stay below it): issue "add budget/anomaly alert", budget sized from the last full
month. Not created from this mode.

## 4. Estimate vs bill

```bash
uvx bicep-cost@latest scan --actuals --resource-group "$AZURE_RESOURCE_GROUP" --format markdown   # >= 0.5, no template needed
uvx bicep-cost scan --measure --days 30 --resource-group "$AZURE_RESOURCE_GROUP" --save-usage prod.usage.toml   # + Azure Monitor usage
```

Read the coverage table: *modelled / actual* far from 100 % (usage defaults: `--measure`; discounts: `--azure-prices`
or `[discounts]`; or a modelling gap: issue on the `bicep-cost` repo), and cost of ids no longer in the inventory.

If the repo has Bicep, run `collect` and `estimate` per [bicep-cost.md](../../azure-cost/references/bicep-cost.md):

- **Drift** template vs live: rule out intended drift first (PostgreSQL auto-grow, autoscale). Small clear case: PR on
  the template; otherwise an issue.
- **Stale usage file**: commit the refreshed `*.usage.toml` (own commit) when values moved by more than ~25 %.

## Report

Per scope: window and currency, flagged groups (baseline → recent per day, first day), the cause with its evidence
(resource id, Activity Log or `resourcechanges` row), budget/anomaly alert present or missing, coverage gaps, drift.
`bdt issue search --state all --since-days 0 "<resource or service>"` first, one issue per root cause. No secrets or
caller emails in issues.
