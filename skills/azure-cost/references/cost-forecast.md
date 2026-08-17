# Cost Forecast

For "what will this cost next month/quarter" projections. Different endpoint from Query — don't try to bolt grouping or historical-only ranges onto it.

`POST {scope}/providers/Microsoft.CostManagement/forecast?api-version=2023-11-01`

## How it differs from Query

| | Query | Forecast |
|---|---|---|
| Time period | Past only | `to` **must** be in the future |
| Grouping | Up to 2 dimensions | **Not supported at all** — if the user wants "forecast Databricks spend specifically", forecast the whole scope and separately query Databricks' historical share to scale it, don't expect the API to group |
| Extra response column | — | `CostStatus`: `Actual` (historical) vs `Forecast` (projected) |
| Response size | Up to 5,000 rows/page | ~40 rows recommended — this is meant for a trend line, not a data dump |

Needs at least 28 days of historical cost in the scope to build a forecast — a subscription younger than that will fail or fall back to actuals only.

## Request

```bash
SUB=$(az account show --query id -o tsv)
az rest --method POST \
  --url "https://management.azure.com/subscriptions/$SUB/providers/Microsoft.CostManagement/forecast?api-version=2023-11-01" \
  --body '{
    "type": "ActualCost",
    "timeframe": "Custom",
    "timePeriod": {"from": "2026-08-01", "to": "2026-09-30"},
    "dataset": {
      "granularity": "Daily",
      "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
      "sorting": [{"direction": "Ascending", "name": "UsageDate"}]
    },
    "includeActualCost": true,
    "includeFreshPartialCost": true
  }'
```

`includeActualCost: true` returns historical actuals alongside the forecast in one response (so you can plot both on one trend without a second call). `includeFreshPartialCost` needs `includeActualCost: true` set alongside it — it fills in partial data for the last few days before the forecast model has fully processed them.

## Errors specific to forecast

| Status | Cause | Fix |
|---|---|---|
| 400 | "Can't forecast on the past" | `to` must be a future date — this is the #1 mistake, easy to copy a Query-style past-only range by accident |
| 400 | Missing `dataset` | It's required even though grouping isn't allowed inside it |
| 403 | Cost Management Reader missing | Same role as Query/Optimization |
| 424 | Insufficient training data | Needs 28+ days of history; falls back to actuals-only if available — tell the user this isn't a forecast failure, just an insufficient-data case |

"Forecast is unavailable for the specified time period" is not a bug to work around — it means the scope genuinely doesn't have enough history yet. Fall back to [cost-query.md](cost-query.md) for whatever historical data does exist rather than retrying the forecast call.
