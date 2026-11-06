# bicep-cost

[`bicep-cost`](https://github.com/bmsuisse/bicep-cost) prices Bicep/ARM templates (or a deployed subscription) from the
Azure Retail Prices API, and reads real usage and cost from Azure. Run `uvx bicep-cost@latest <cmd>`; `.bicep` input
needs the Bicep CLI. Versions: `estimate`/`collect` 0.2, `spikes` 0.3, `--existing` 0.4, `scan` 0.5.

## Estimate

```bash
uvx bicep-cost estimate main.bicep -p parameters/prod.bicepparam --currency CHF --resource-group <rg> --detail
```

| Flag | Why it matters |
|---|---|
| `-p` / `--set NAME=VALUE` | Without prod parameters the template defaults are priced (often dev SKUs). |
| `--usage FILE` | Storage GB, log GB, replica hours. Without it built-in defaults apply (10 GB per storage account, 2 GB logs); the report counts them. Auto-found: `<params stem>.usage.toml`, `bicep-cost.usage.toml`. |
| `--currency` | Default: usage file's `[meta] cost_currency`, else USD. Use the subscription's billing currency; no conversion. |
| `[discounts]` / `--azure-prices` | Prices are list prices. EA/MCA discounts per resource type in the usage file, or negotiated rates (az login, needs price sheet access). |
| `--existing FILE.json` | `resource x '...' existing` deploys nothing, so it estimates ~0. List the referenced resources (`type`, `name`, `sku`, `properties`) to price them. |
| `--strict` | Exit 2 if something couldn't be priced. Otherwise read the "not covered" section before quoting a total. |

Fixed lines follow from the template; usage-based lines (`*`) are only as good as the usage file. Say which a number is.

## Real values (read-only, `az login`)

```bash
uvx bicep-cost collect main.bicep -p prod.bicepparam --resource-group <rg> --days 60   # writes prod.usage.toml
uvx bicep-cost scan --actuals [--resource-group <rg>]     # no template: price what is deployed, reconcile with the bill
uvx bicep-cost spikes [--resource-group <rg>]             # cost jumps, see cost-query.md#spike-check
```

`collect` measures usage (storage, logs, replicas, executions), prints template-vs-live **drift** and each resource's
actual monthly cost as a comment. Keep the file in the repo; hand-written overrides go in a second `--usage` file so
a re-`collect` doesn't overwrite them. 60-90 days for workloads with monthly peaks.

`scan --actuals` ends with a per-type coverage table (modelled vs actual, types priced from the bill, cost of ids no
longer deployed); `--measure` adds Azure Monitor usage.

## Estimate vs bill

Compare per resource: `scan --actuals`, or `estimate --format json` against `collect`'s comments (monthly). A
[cost-query.md](cost-query.md) total is for its whole window: scale to a month (÷ days × 30.4) first. Off by more than
~25 %: wrong parameters, a usage key still at default, an unmodelled meter (egress, Premium storage, licences,
reservations), or a real overspend. A real overspend is a cost finding, a modelling gap an issue on the bicep-cost repo.

## PR guard

```bash
uvx bicep-cost estimate main.bicep -p prod.bicepparam --format json -o base.json      # on the base branch
uvx bicep-cost estimate main.bicep -p prod.bicepparam --baseline base.json --fail-increase-percent 10 --fail-above <budget> --format json -o head.json
uvx bicep-cost diff base.json head.json
```

Exit 3 above a cap, 2 with `--strict` and something unpriced. Same currency and usage assumptions on both sides.
Egress, reservations, Premium storage, gateways and firewalls aren't modelled; a missing type is a PR on the
bicep-cost repo (`bicep_cost/estimators/`).
