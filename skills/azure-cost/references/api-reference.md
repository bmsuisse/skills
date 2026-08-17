# Cost Management API Reference

Shared schema, dimension availability, and error handling for the Query, Optimization, and Forecast workflows.

## Request body shape (Query API)

`POST {scope}/providers/Microsoft.CostManagement/query?api-version=2023-11-01`

```json
{
  "type": "ActualCost",
  "timeframe": "Custom",
  "timePeriod": { "from": "2026-08-01", "to": "2026-08-17" },
  "dataset": {
    "granularity": "None",
    "aggregation": { "totalCost": { "name": "Cost", "function": "Sum" } },
    "grouping": [{ "type": "Dimension", "name": "ServiceName" }],
    "filter": { "dimensions": { "name": "ResourceGroupName", "operator": "In", "values": ["rg-prod"] } },
    "sorting": [{ "direction": "Descending", "name": "Cost" }]
  }
}
```

| Field | Notes |
|---|---|
| `type` | `ActualCost` (default), `AmortizedCost` (spreads reservation/savings-plan purchases across the term — use for reservation ROI questions), or `Usage`. |
| `timeframe` | Preset (`MonthToDate`, `WeekToDate`, `YearToDate`, `TheLastWeek`, `TheLast7Days`, `TheLast3Months`, …) or `Custom`. **Prefer `Custom` with explicit dates** — some presets (`TheLastMonth`, `TheLastBillingMonth`) 400 on certain tenants/agreement types, and `Custom` is the only way to do a partial-month apples-to-apples comparison. |
| `timePeriod` | Required when `timeframe: Custom`. ISO 8601 dates, `to` inclusive. |
| `dataset.granularity` | `None` (single total, max 12mo range), `Daily` (max 31 days), `Monthly` (max 12mo). |
| `dataset.aggregation` | `Sum` is the only supported function. Source column is usually `Cost`; `PreTaxCost` or `UsageQuantity` also valid. |
| `dataset.grouping` | Up to **2** entries, `{"type": "Dimension"|"TagKey", "name": "..."}`. No duplicate columns. |
| `dataset.filter` | See below — logical (`and`/`or`/`not`) wrapping comparison filters on `dimensions` or `tags`. |
| `dataset.sorting` | `{"direction": "Ascending"|"Descending", "name": "Cost"|<grouped column>}`. |

### Filters

```json
{ "dimensions": { "name": "ServiceName", "operator": "In", "values": ["Storage"] } }
```

**The key is `operator` (singular).** Comparison operators: `In`, `Equal`, `Contains`, `LessThan`, `GreaterThan`, `NotEqual`. Wrap multiple conditions in `and`/`or` (need 2+ children each) or `not` (exactly 1 child) — a single condition should NOT be wrapped in a logical operator, just pass the `dimensions`/`tags` object directly.

### Response shape

```json
{
  "properties": {
    "columns": [{"name": "Cost", "type": "Number"}, {"name": "ServiceName", "type": "String"}, {"name": "Currency", "type": "String"}],
    "rows": [[2875.46, "Azure Databricks", "EUR"]],
    "nextLink": null
  }
}
```

Row values are positional, matching `columns` order — grouping columns shift the index of everything after `Cost`, so read `columns` before indexing into `rows`, don't assume a fixed position. `UsageDate` (present with `Daily`/`Monthly` granularity) comes back as an integer `YYYYMMDD`, not a string. Max 5,000 rows/page (default 1,000); follow `nextLink` if present.

## Dimensions

Commonly useful ones: `ServiceName`, `ServiceFamily`, `ResourceGroupName`, `ResourceId`, `ResourceLocation`, `MeterCategory`, `MeterSubCategory`, `ChargeType`, `PricingModel` (OnDemand/Reservation/SavingsPlan/Spot), `SubscriptionName`, `BenefitName` (reservation/savings-plan name), `TagKey`.

- **`ResourceId` grouping only works at subscription or resource-group scope.** At management group / billing account scope it errors — use `ServiceName` or `SubscriptionName` there, or narrow the scope first if per-resource detail is what's needed.
- EA-only dimensions: `DepartmentName`, `EnrollmentAccountName`, `BillingPeriod`. MCA-only: `InvoiceSectionName`. Using an agreement-type-mismatched dimension 400s.
- EA + management-group scope: filtering by `SubscriptionName` alone errors — pair it with a `SubscriptionId` filter in an `and` block.

## Errors & rate limits

| Status | Cause | Fix |
|---|---|---|
| 400 | Bad schema, unsupported dimension for scope/agreement, date range over the limit, malformed filter (see the `operator` singular note above), or an unsupported timeframe preset for this tenant. | Fix the request; don't retry as-is. |
| 401 | Expired/missing auth. | `az login`. |
| 403 | Missing Cost Management Reader role on the scope. | Get the role assigned; wrong role is a much more common cause of 403 than a wrong scope URL. |
| 404 | Scope doesn't exist / wrong subscription ID. | Verify with `az account show` / `az account list`. |
| 429 | Rate limited — 4 req/min per scope is the tightest limit (also 20/min per user, and tenant-wide caps). | Space sequential calls to the same scope by 10-15s; if you still get 429, check `x-ms-ratelimit-microsoft.costmanagement-*-retry-after` headers and wait the longest one. Max 3 retries. |
| 503 | Service outage. | Check status.azure.com, don't retry blind. |

Only 429 is worth retrying — every other status means the request itself needs fixing.

### Time-period guardrails

- No `timePeriod` given → defaults to current-month-start through today.
- `Daily` granularity: max 31-day range. `Monthly`/`None`: max 12 months. Absolute API ceiling: 37 months regardless of granularity — over-range requests get silently truncated at the front (or 400 past 37mo), so if you need a specific historical window, keep it inside these limits rather than trusting truncation to do the right thing.
- Both `from`/`to` in the future → the whole period silently shifts to the same period *last year*. Only `to` in the future → `to` gets pulled back to today. Watch for a suspiciously-labeled response if you accidentally pass future dates in a forecast-vs-query mixup.
