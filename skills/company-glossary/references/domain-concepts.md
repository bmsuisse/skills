# Fabricks DWH — Domain Concepts

## Delkredere
Credit risk provisioning system. Tracks customer open balances and calculates bad debt provisions:
- **Customer Ledger**: GL entries for open AR balances
- **Provision Calculation**: Risk assessment based on aging and customer health
- **Multiplicator Rules**: Risk adjustment factors (managed externally)
- **Snapshot Dates**: Reference dates for provision calculation

## Commission System (c)
Internal sales commission and bonus system with multi-tier targets:
1. Accumulate monthly sales per agent/group
2. Compare sales reach against defined tier targets
3. Calculate bonus using tiered interpolation
4. Integrate IVP (incentive/margin) bonuses
5. Apply manual corrections if needed

## IVP (Incentive/Margin Bonus)
Adjusted margin calculation that layers supplier and article incentives on top of standard margin:
- **Supplier Bonus**: Volume-based incentives from suppliers
- **Article Bonus Factor**: Article-specific bonus multiplier
- **Slow Mover Bonus**: Special bonus factor for slow-moving articles by location
- **Margin IVP**: Standard margin plus all incentive adjustments

## HEP (High Engagement Program)
A product category designation with:
- Dedicated budget (`fact_sales_hep_budget`)
- Separate margin and contribution targets
- `is_hep` flag on article and sales order records

## MDM — Article Deduplication
Multi-step workflow to identify and resolve duplicate articles:
1. Find duplicates (island/graph method)
2. Define default/master article
3. Detect pricing conflicts
4. Detect master data conflicts
5. Build deduplication plan
6. Impact assessment across branches