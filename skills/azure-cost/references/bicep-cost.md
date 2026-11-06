# bicep-cost

For "what will this Bicep deployment cost", "did this PR raise the bill" and "does our estimate match the real bill".
[`bicep-cost`](https://github.com/bmsuisse/bicep-cost) prices a `.bicep` / `.bicepparam` / compiled ARM template
from the public Azure Retail Prices API (no login), and `collect` measures real usage from the deployed resources
so the estimate stops running on defaults. Complements the other references: Query shows what *was* billed,
bicep-cost what the template *will* bill.

Run it with `uvx bicep-cost ...` (PyPI) or `uv tool install bicep-cost`. Needs the Bicep CLI (`bicep` on PATH,
`$BICEP_CLI` or `az bicep install`) for `.bicep` input.

## Estimate

```bash
uvx bicep-cost estimate app/infra/main.bicep -p app/infra/parameters/prod.bicepparam \
  --currency CHF --resource-group <rg> --subscription-id <sub> --detail
uvx bicep-cost estimate main.bicep --format json -o head.json     # also markdown (PR comment), csv
```

Parameters that change the answer, in order of how often they are wrong:

| Flag | Why it matters |
|---|---|
| `-p` / `--set NAME=VALUE` | Without the prod parameters the template's defaults are priced (often dev SKUs). Secure params without a default need `--set x=x`. |
| `--usage FILE` | Storage GB, log GB, replica hours... Without it the built-in defaults are used (10 GB per storage account, 2 GB logs) and the report says how many figures are defaults. Default lookup: `<params stem>.usage.toml` or `bicep-cost.usage.toml` next to the input. |
| `--currency` | Defaults to the usage file's `[meta] cost_currency`, else USD. Use the billing currency of the subscription (read it from a Cost Management query, see [cost-query.md](cost-query.md)); no conversion happens, and the report and `diff` must use the same one. |
| `--resource-group`, `--subscription-id` | Only needed so `resourceGroup()` / `resourceId()` evaluate like the deployed ones; `collect` requires them. |
| `[discounts]` in the usage file | Retail prices are list prices. EA/MCA discounts as percent per resource type, e.g. `"Microsoft.Web/serverfarms" = 30`. Or `--azure-prices` (az login, needs access to the subscription's price sheet) to use negotiated rates; then `[discounts]` is ignored. |
| `--location` | Region for resources without one (default `westeurope`). |
| `--strict` | Exit 2 if any resource could not be priced. Without it, unsupported types are only *listed* ("cost NOT included"): read that section before quoting a total. |

Fixed lines (plan SKU x instances, DB compute, private endpoints) follow from the template; usage-based lines
(`*`) are only as good as the usage file. Say which one a number is when reporting it.

## Measure real values: `collect`

Read-only (GETs, Azure Monitor metrics, Log Analytics `Usage`, Cost Management `query`); needs `az login` with
Reader on the resources, Cost Management Reader and Log Analytics Reader for cost/log data.

```bash
uvx bicep-cost collect app/infra/main.bicep -p app/infra/parameters/prod.bicepparam \
  --resource-group <rg> --days 60          # writes parameters/prod.usage.toml next to the parameters
```

The usage file holds the measured values, the **drift** between template and live (32 GB vs 64 GB, 2 vs 3
instances) and each resource's actual cost of the window as a comment. Windows are scaled to 730 h/month.
Keep the file in the repo (it's what makes the PR estimate honest); put hand-written overrides in a second file
(`--usage a.toml --usage b.toml`, later wins) so a re-`collect` doesn't overwrite them. `--days` of 30 is the
default; use 60-90 for workloads with monthly peaks.

## Compare estimate with the real bill

1. `estimate --format json` with the fresh usage file, per-resource figures.
2. `collect`'s comments (or [cost-query.md](cost-query.md) grouped by `ResourceId`) give the actual cost of the
   same window.
3. A resource where actual differs from estimate by more than ~25 %: wrong parameter file, a usage key that
   is still a default, an unmodelled meter (egress, Premium storage, licences, reservations: see the tool's
   "Not covered" list), or a real overspend. The first three fix the estimate, the last one is a finding.

## PR guard rail

```bash
uvx bicep-cost estimate main.bicep -p prod.bicepparam --format json -o base.json   # on the base branch
uvx bicep-cost estimate main.bicep -p prod.bicepparam --baseline base.json --fail-increase-percent 10 --fail-above <monthly budget>
uvx bicep-cost diff base.json head.json     # per-resource change
```

Exit 3 when a cap is exceeded, 2 with `--strict` and something unpriced. Both reports need the same currency and
usage assumptions, otherwise the diff compares assumptions, not infrastructure.

## Where it stops

Bandwidth/egress, reservations, Premium storage, load balancers, gateways and firewalls are not modelled (the
tool's README lists every supported type and what it leaves out). An estimate below the actual bill by roughly those items is expected, not a bug. A missing resource type
is a PR on the bicep-cost repo (`bicep_cost/estimators/`).
