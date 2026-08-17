# Cost Optimization

For "how do we spend less" / "find waste" / "orphaned resources" / "rightsize" questions.

Always run [cost-query.md](cost-query.md) first and present the actual bill alongside recommendations — savings estimates without the baseline bill next to them read as speculative even when they're accurate.

## Workflow

1. **Confirm access:** `az account show`, and that the account has Reader + Cost Management Reader on the target scope.
2. **Pull Azure Advisor's cost recommendations** — this is the fastest signal, Microsoft already computed it from your actual usage:
   ```bash
   az advisor recommendation list --category Cost -o table
   ```
   Each recommendation includes an estimated monthly/annual saving and the specific resource ID — use these numbers rather than re-deriving your own estimate.
3. **Find orphaned resources with Resource Graph** (KQL patterns below) — unattached disks, unused public IPs, NICs with no VM, idle load balancers. These are the "delete this and save $X immediately" wins with the least risk.
4. **If `azqr` (Azure Quick Review, github.com/Azure/azqr) is installed**, it's worth running for a broader governance/orphaned-resource sweep — `azqr scan --subscription <id> -o json`. It's optional; Resource Graph queries below cover the same ground for cost purposes without the extra tool.
5. **For rightsizing claims, back them with Azure Monitor metrics** — don't recommend downsizing a VM off a hunch. Pull 14 days of CPU/memory before suggesting a smaller SKU.
6. **Service-specific rules:** storage tiering/lifecycle — see below.
7. **Report:** total bill (from step in cost-query), Advisor findings, orphaned resources with exact resource IDs, prioritized recommendations (immediate/low-risk first), and the commands to act on each — but don't run destructive commands yourself without explicit approval.

## Azure Advisor (primary source of truth)

```bash
az advisor recommendation list --category Cost --query "[].{resource:impactedValue, problem:shortDescription.problem, solution:shortDescription.solution, savings:extendedProperties.annualSavingsAmount}" -o table
```

Advisor needs a few days of usage history to populate recommendations for new resources — don't be surprised if a subscription created last week has nothing here yet.

## Resource Graph queries for orphaned resources

Requires `az extension add --name resource-graph`.

**Unattached managed disks** (billed as storage, doing nothing):
```bash
az graph query -q "Resources | where type =~ 'microsoft.compute/disks' | where isempty(managedBy) | project name, resourceGroup, location, diskSizeGb=properties.diskSizeGB, sku=sku.name" -o table
```

**Unattached public IPs:**
```bash
az graph query -q "Resources | where type =~ 'microsoft.network/publicipaddresses' | where isempty(properties.ipConfiguration) | project name, resourceGroup, location, sku=sku.name" -o table
```

**Orphaned NICs (no VM attached):**
```bash
az graph query -q "Resources | where type =~ 'microsoft.network/networkinterfaces' | where isempty(properties.virtualMachine) | project name, resourceGroup, location" -o table
```

**Idle load balancers (empty backend pool):**
```bash
az graph query -q "Resources | where type =~ 'microsoft.network/loadbalancers' | where array_length(properties.backendAddressPools) == 0 | project name, resourceGroup, location, sku=sku.name" -o table
```

**Tag coverage** (useful when cost can't be attributed to a team/cost-center):
```bash
az graph query -q "Resources | extend hasCostCenter = isnotnull(tags['CostCenter']) | summarize total=count(), tagged=countif(hasCostCenter) by type | extend coverage=round(100.0*tagged/total,1) | order by total desc" -o table
```

Always cross-reference orphaned-resource findings against actual cost data (`ResourceId` grouping from [cost-query.md](cost-query.md)) before recommending deletion — a resource graph hit tells you it's *orphaned*, not that it's *expensive*; prioritize by the intersection of both.

## Storage cost optimization

Storage is consistently one of the top 2-3 cost drivers on most subscriptions, so it's worth checking these even without a specific storage complaint:

| Pattern | Detection | Fix |
|---|---|---|
| Premium in dev/test | `sku.name` contains `Premium` + `tags.environment` in dev/test/staging | Downgrade to Standard |
| GRS/GZRS in dev/test | `sku.name` contains `GRS`/`GZRS` + dev/test tag | Downgrade to LRS — dev/test rarely needs geo-redundancy, ~50% cheaper |
| No lifecycle policy | `az storage account management-policy show` returns empty | Add tiering rules (below) |
| Hot-only with stale data | Blobs unaccessed 30+ days, still in Hot tier | Move to Cool, or enable auto-tiering |
| Excess soft-delete retention | `deleteRetentionPolicy.days > 30` without a compliance reason | Reduce to 7-14 days |

Find candidates:
```bash
az graph query -q "Resources | where type =~ 'microsoft.storage/storageaccounts' | where sku.name contains 'Premium' or sku.name contains 'GRS' | where tags.environment in~ ('dev','test','staging') | project name, resourceGroup, sku=sku.name, tags" -o table
```

**Access tier by last-access age:** <30d → Hot, 30-90d → Cool, 90-180d → Cold, >180d → Archive (Archive has retrieval cost + hours-long rehydration, only for genuinely cold data).

**Baseline lifecycle policy** (move to Cool at 30d, Archive at 180d, clean up old snapshots/versions at 90d):
```json
{
  "rules": [
    {"name": "move-to-cool", "type": "Lifecycle", "definition": {
      "actions": {"baseBlob": {"tierToCool": {"daysAfterLastAccessTimeGreaterThan": 30}}},
      "filters": {"blobTypes": ["blockBlob"]}
    }},
    {"name": "move-to-archive", "type": "Lifecycle", "definition": {
      "actions": {"baseBlob": {"tierToArchive": {"daysAfterLastAccessTimeGreaterThan": 180}}},
      "filters": {"blobTypes": ["blockBlob"]}
    }},
    {"name": "delete-old-snapshots", "type": "Lifecycle", "definition": {
      "actions": {"snapshot": {"delete": {"daysAfterCreationGreaterThan": 90}}},
      "filters": {"blobTypes": ["blockBlob"]}
    }}
  ]
}
```
Apply with `az storage account management-policy create --account-name <name> --resource-group <rg> --policy @policy.json`. `tierToCool`/`tierToArchive` based on last-access time requires last-access tracking enabled first — check with `az storage account blob-service-properties show --account-name <name> --resource-group <rg> --query lastAccessTimeTrackingPolicy`.

## Report structure

```markdown
# Azure Cost Optimization Report — <subscription name>, <date>

## Executive summary
Total monthly cost: €X · Top 3 drivers: <service> (€), <service> (€), <service> (€) · Potential savings: €Y/mo

## Cost breakdown by service
| Service | Cost | % of total |

## Advisor recommendations
(from `az advisor recommendation list --category Cost`, with estimated savings)

## Orphaned resources
(from Resource Graph, with resource IDs and estimated monthly cost from the cost-by-resource query)

## Prioritized recommendations
### Immediate, low-risk (delete/downgrade orphaned or idle resources)
### Medium-risk (rightsizing, tiering — needs utilization data to back it)
### Longer-term (reservations/savings plans, if steady-state usage justifies the commitment)

## Commands
(exact commands to execute each recommendation — do not run destructive ones without explicit approval)
```

Never delete or resize anything without explicit user approval — this workflow is find-and-report, not find-and-fix. Always include a dry-run/verification step before any destructive command in the report.
