---
name: azure-cost
description: >
  Query, analyze, and reduce Azure spending via the Cost Management REST API
  and Azure CLI. Covers cost breakdowns by service/resource-group/resource,
  month-over-month spike detection, orphaned-resource hunting, storage
  tiering savings, VM rightsizing, and spend forecasting. Use this whenever
  the user asks about Azure cost, billing, or spend — even if they only say
  "what's driving cost this month" or "why did the bill go up" without
  naming the API. Trigger on: "azure cost", "azure bill", "cost breakdown",
  "how much are we spending", "what's the biggest cost driver", "cost
  spike", "cost increased", "reduce azure spend", "optimize azure costs",
  "save money on azure", "orphaned resources", "unattached disks",
  "rightsize vms", "storage cost", "forecast azure spending", "azure
  budget". DO NOT USE FOR: deploying or provisioning resources, general
  Azure resource configuration, or security/compliance audits unrelated to
  cost — those are separate concerns even if they touch the same resources.
---

# Azure Cost Management

Three things people ask for, three references:

| Intent | Reference |
|---|---|
| "What are we spending / what's driving cost?" | [references/cost-query.md](references/cost-query.md) |
| "How do we spend less?" | [references/cost-optimization.md](references/cost-optimization.md) |
| "What will next month/quarter cost?" | [references/cost-forecast.md](references/cost-forecast.md) |

Request/response schema, dimension availability, and rate limits are shared across all three — see [references/api-reference.md](references/api-reference.md).

Always start with a query (even for an optimization ask) — you can't credibly recommend savings without first showing the actual bill. Present the breakdown, then the recommendations.

## Fast path

```bash
az account show                                    # confirm subscription/tenant
SUB=$(az account show --query id -o tsv)

az rest --method POST \
  --url "https://management.azure.com/subscriptions/$SUB/providers/Microsoft.CostManagement/query?api-version=2023-11-01" \
  --body '{
    "type": "ActualCost",
    "timeframe": "MonthToDate",
    "dataset": {
      "granularity": "None",
      "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
      "grouping": [{"type": "Dimension", "name": "ServiceName"}]
    }
  }'
```

`az rest` against the Cost Management API is more reliable than `az costmanagement query` — the CLI wrapper is thinner and lags the REST surface. Use `az rest` for everything cost-related.

## Hard-won guardrails (learned live, not just from docs)

These bit us running this skill for real against a production subscription — treat them as load-bearing, not optional trivia:

- **The per-scope rate limit (4 requests/minute) is real and tight.** Four sequential `az rest` calls to the same subscription inside a minute triggered a 429. Sleep ~10-15s between sequential Cost Management calls to the same scope — don't just fire-and-retry-on-error. `granularity: Daily` combined with a `grouping` dimension is a heavier query and throttles faster than a plain totals query.
- **Filter field is `operator` (singular), not `operators`.** Getting this wrong returns a 400 with a message that reads like the value is the problem ("'In' operator is the only valid value") when actually the *key name* is wrong. If a filter 400s and the error mentions the operator value being invalid, check the key spelling first.
- **`TheLastMonth` (and similarly `TheLastBillingMonth`) can 400 as "currently not supported"** depending on tenant/agreement type, despite being a documented preset. Don't rely on named relative-month presets for month-over-month comparisons — use `"timeframe": "Custom"` with explicit `from`/`to` dates instead. It's also the only way to do an apples-to-apples partial-month comparison (e.g. "first 17 days of this month vs first 17 days of last month") since `MonthToDate` always starts on the 1st.
- Full error/retry reference: [references/api-reference.md](references/api-reference.md#errors--rate-limits).

## Scope patterns

- Subscription: `/subscriptions/<id>`
- Resource group: `/subscriptions/<id>/resourceGroups/<name>`
- Management group: `/providers/Microsoft.Management/managementGroups/<id>`
- Billing account: `/providers/Microsoft.Billing/billingAccounts/<id>`

Default to subscription scope unless the user names a narrower resource group or a broader management group. `ResourceId` grouping (needed for "which specific resource is driving this") only works at subscription/resource-group scope — see [references/api-reference.md](references/api-reference.md) if you need to go broader and still want per-resource detail.

## Required access

Cost Management Reader (or Contributor) role on the target scope. `az account show` confirms which subscription/tenant is active before you query — don't assume, since the user may be logged into a different subscription than the one they mean.
