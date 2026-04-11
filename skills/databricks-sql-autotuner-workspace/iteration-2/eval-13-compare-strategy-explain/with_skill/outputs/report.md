# Compare Strategy: `checksum` vs `row_hash`

## Overview

Both `--compare-strategy checksum` and `--compare-strategy row_hash` are validation strategies for confirming that the original and optimized queries produce equivalent results. Both operate entirely on the cluster using aggregation — neither collects rows to the driver.

---

## `--compare-strategy checksum`

**How it works:**

The checksum strategy computes a single aggregation pass over the query results. For each numeric and boolean column it computes `SUM` and `COUNT`, and it counts total rows. This produces a compact fingerprint of the dataset without moving any row data to the driver.

- Columns covered: numeric types (INT, BIGINT, DOUBLE, DECIMAL, etc.) and boolean columns
- Aggregates used: `SUM(col)` and `COUNT(col)` per numeric/boolean column, plus an overall `COUNT(*)`
- Execution model: one aggregation pass, pushed down to the cluster — no rows collected

**Limitation:** String columns, date/timestamp columns, and other non-numeric types are not included in the checksum. If the result set contains only (or mostly) string columns, a checksum match does not guarantee those columns are identical.

**Best for:** Large result sets where the important computed values are numeric or boolean, and collecting even a diff of rows is too expensive.

---

## `--compare-strategy row_hash`

**How it works:**

The row hash strategy computes `SUM(xxhash64(*))` — it hashes every row across all columns into a single 64-bit integer, then sums those hashes. A matching sum means every row, across every column of every type, hashed to the same value in both queries.

- Columns covered: all columns, regardless of type (strings, dates, timestamps, numerics, structs)
- Aggregates used: `SUM(xxhash64(col1, col2, ..., colN))` — a single pass
- Execution model: single aggregation pass on the cluster — no rows collected

**Best for:** Huge result sets where column types are mixed or predominantly non-numeric (strings, dates), and you need a stronger guarantee of full row-level equivalence.

---

## When to use each

| Situation | Recommended strategy |
|:----------|:--------------------|
| Large result set, mostly numeric/boolean columns | `checksum` |
| Large result set with string, date, or mixed-type columns | `row_hash` |
| Need the strongest possible equivalence guarantee across all column types | `row_hash` |
| Slightly faster aggregation is preferred and numeric coverage is sufficient | `checksum` |
| Query returns millions of rows and even collecting a diff is too expensive | Either — both avoid driver row collection |

**Decision rule:** If you are unsure, prefer `row_hash`. It covers all column types and provides a stronger equivalence guarantee. Use `checksum` only when you know your result set is dominated by numeric/boolean columns and you want to avoid the overhead of hashing every column.

---

## Do both strategies avoid driver row collection?

Yes. Both `checksum` and `row_hash` avoid collecting rows to the driver entirely. They run as on-cluster aggregations and return only a single summary value (or a small set of aggregate values) to verify equivalence. This is why they are appropriate for large and huge datasets where `full` (EXCEPT ALL symmetric diff) or `extend` (EXCEPT ALL via global temp tables) would be too expensive.

---

## Strategy comparison summary

| Property | `checksum` | `row_hash` |
|:---------|:-----------|:-----------|
| Columns covered | Numeric and boolean only | All columns (all types) |
| Aggregate used | `SUM` + `COUNT` per numeric/boolean col | `SUM(xxhash64(all_cols))` |
| Execution passes | Single aggregation pass | Single aggregation pass |
| Driver row collection | None | None |
| Strength of equivalence guarantee | Partial (non-numeric columns not checked) | Full (all columns hashed) |
| Recommended dataset size | Large | Huge / mixed-type columns |
| Use case | Numeric-heavy result sets | Mixed or string-heavy result sets |
