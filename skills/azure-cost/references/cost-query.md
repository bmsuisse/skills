# Cost Query

For "what are we spending" / "what's driving cost" / "why did the bill go up" questions. Full schema and error handling: [api-reference.md](api-reference.md).

## Workflow

1. **Resolve scope.** Default to the current subscription (`az account show --query id -o tsv`) unless the user names a resource group or wants a management-group rollup.
2. **Get the total breakdown first.** Group by `ServiceName` for month-to-date — this is the number the user actually wants, and everything else supports it.
3. **If they're asking "what changed" or "why did it go up", get a same-period comparison.** Don't compare `MonthToDate` (partial month) against a full prior month — that overstates the prior month by definition. Query the *same number of days* in the prior month with `Custom` timeframe (e.g. if today is the 17th, compare Aug 1-17 against Jul 1-17).
4. **Drill into the top 2-3 services by resource** (`ResourceId` grouping, filtered by `ServiceName`) to name the specific resource, not just the service category — "Storage is $2,275" is less actionable than "storage account `stprodlogs` is $1,900 of that $2,275."
5. **Pace your requests.** 4 req/min per scope is the real ceiling — see the guardrails in [SKILL.md](../SKILL.md#hard-won-guardrails-learned-live-not-just-from-docs). Sleep between calls rather than firing them back to back.

## Examples

**Cost by service, month to date:**

```bash
SUB=$(az account show --query id -o tsv)
az rest --method POST \
  --url "https://management.azure.com/subscriptions/$SUB/providers/Microsoft.CostManagement/query?api-version=2023-11-01" \
  --body '{
    "type": "ActualCost",
    "timeframe": "MonthToDate",
    "dataset": {
      "granularity": "None",
      "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
      "grouping": [{"type": "Dimension", "name": "ServiceName"}],
      "sorting": [{"direction": "Descending", "name": "Cost"}]
    }
  }'
```

**Same-period comparison for spike detection** (replace dates with "1st of month" through "same day-of-month last month"):

```bash
az rest --method POST \
  --url "https://management.azure.com/subscriptions/$SUB/providers/Microsoft.CostManagement/query?api-version=2023-11-01" \
  --body '{
    "type": "ActualCost",
    "timeframe": "Custom",
    "timePeriod": {"from": "2026-07-01", "to": "2026-07-17"},
    "dataset": {
      "granularity": "None",
      "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
      "grouping": [{"type": "Dimension", "name": "ServiceName"}]
    }
  }'
```

Diff the two rowsets client-side (by `ServiceName`) — the API doesn't do the delta for you. Sort by absolute delta, not by percentage: a service going from €40 to €770 (+1800%) is a bigger story than one growing from €10,000 to €11,000 (+10%) even though the percentage is smaller.

**Which resource within a service is driving cost** (filter + ResourceId grouping, subscription/RG scope only):

```bash
az rest --method POST \
  --url "https://management.azure.com/subscriptions/$SUB/providers/Microsoft.CostManagement/query?api-version=2023-11-01" \
  --body '{
    "type": "ActualCost",
    "timeframe": "MonthToDate",
    "dataset": {
      "granularity": "None",
      "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
      "filter": {"dimensions": {"name": "ServiceName", "operator": "In", "values": ["Storage"]}},
      "grouping": [{"type": "Dimension", "name": "ResourceId"}]
    }
  }'
```

**Daily trend** (max 31 days, drop the `grouping` if you also need it — grouped+daily is the heaviest query shape and throttles fastest):

```bash
az rest --method POST \
  --url "https://management.azure.com/subscriptions/$SUB/providers/Microsoft.CostManagement/query?api-version=2023-11-01" \
  --body '{
    "type": "ActualCost",
    "timeframe": "MonthToDate",
    "dataset": {
      "granularity": "Daily",
      "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}}
    }
  }'
```

**Reservation/savings-plan effective cost** (use `AmortizedCost`, group by `BenefitName`):

```bash
az rest --method POST \
  --url "https://management.azure.com/subscriptions/$SUB/providers/Microsoft.CostManagement/query?api-version=2023-11-01" \
  --body '{
    "type": "AmortizedCost",
    "timeframe": "Custom",
    "timePeriod": {"from": "2026-07-01", "to": "2026-07-31"},
    "dataset": {
      "granularity": "None",
      "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
      "grouping": [{"type": "Dimension", "name": "BenefitName"}]
    }
  }'
```

## Presenting results

Parse `properties.rows` with `python3 -c "import json,sys; ..."` piped from the `az rest` output rather than eyeballing raw JSON — sort descending by cost, compute % of total, and for comparisons compute both absolute and percentage delta per service. Currency comes back per-row (`Currency` column) — don't assume EUR/USD, read it from the response.
