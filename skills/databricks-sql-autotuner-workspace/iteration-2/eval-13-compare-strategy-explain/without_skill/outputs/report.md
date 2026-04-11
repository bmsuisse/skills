# Comparing `--compare-strategy checksum` vs `--compare-strategy row_hash`

## General Knowledge Answer

These two flags control how a Databricks SQL autotuner detects whether data has changed between runs (or between source and target). They represent two different approaches to change detection, each with distinct trade-offs in speed, granularity, and reliability.

---

## `--compare-strategy checksum`

### How it works
A **checksum** strategy typically computes a single aggregate value (often via `CHECKSUM()`, `SUM()`, `COUNT()`, or a combination) over an entire table or partition. The result is a single scalar — if it matches the previous run, the data is considered unchanged.

### Characteristics
- **Coarse-grained**: operates at the table or partition level, not at the row level
- **Very fast**: only one aggregate query is executed per table/partition
- **Low overhead**: minimal compute and memory usage
- **Collision risk**: two different datasets can theoretically produce the same checksum (hash collision), though rare in practice
- **No row-level insight**: you cannot identify *which* rows changed, only *whether* something changed

### When to use it
- Large tables where row-level comparison would be prohibitively expensive
- Pipelines where you only need to know "did anything change at all?" before triggering a full reload
- Monitoring or alerting use cases where speed matters more than precision
- Situations where false negatives (missing a change) are acceptable and false positives (unnecessary reruns) are the bigger concern

---

## `--compare-strategy row_hash`

### How it works
A **row_hash** strategy computes a hash (e.g., MD5, SHA1, or a built-in Spark hash function like `xxhash64`) for every individual row, typically by hashing all or a subset of columns together. These per-row hashes are then compared between source and target (or between current and previous runs) to identify exactly which rows were inserted, updated, or deleted.

### Characteristics
- **Fine-grained**: operates at the individual row level
- **Slower and more resource-intensive**: requires hashing every row and joining/comparing large hash sets
- **Precise**: identifies exactly which rows changed, not just whether *something* changed
- **Enables incremental updates**: you can apply only the changed rows (upserts/deletes) rather than reloading the full table
- **Still has theoretical collision risk** per row, but with a good hash function this is negligible in practice

### When to use it
- Incremental load patterns (CDC-style) where you need to apply only deltas
- Tables with low-to-medium row counts where per-row comparison is feasible
- Scenarios where you need to audit or log exactly which rows changed
- Pipelines that feed downstream systems requiring precise change sets (e.g., slowly changing dimensions, audit tables)
- When network/storage costs of a full reload outweigh the compute cost of row-level hashing

---

## Side-by-side comparison

| Dimension               | `checksum`                        | `row_hash`                        |
|-------------------------|-----------------------------------|-----------------------------------|
| Granularity             | Table / partition level           | Row level                         |
| Speed                   | Very fast                         | Slower (scales with row count)    |
| Compute cost            | Minimal                           | Higher                            |
| Change identification   | "Something changed" only          | Exactly which rows changed        |
| Incremental apply       | No — triggers full reload         | Yes — enables targeted upserts    |
| Best for                | Large tables, fast gate checks    | Incremental pipelines, CDC        |
| Collision risk          | Low but coarser                   | Low per-row, very precise         |

---

## Decision guide

Use **`checksum`** when:
- The table is very large and row-level hashing would be too slow or expensive
- You only need a binary "changed / not changed" signal to decide whether to run a downstream job
- You plan to do a full table reload anyway if a change is detected

Use **`row_hash`** when:
- You need to apply incremental changes efficiently (insert/update/delete only changed rows)
- The table is small enough that per-row hashing is affordable
- You need traceability — knowing exactly which rows differ between runs
- You are implementing a CDC or SCD (Slowly Changing Dimension) pattern

---

*Note: This explanation is based on general knowledge of data comparison strategies commonly used in ETL/ELT pipelines and Databricks SQL workloads. Specific behavior may vary depending on the exact implementation of the autotuner tool.*
