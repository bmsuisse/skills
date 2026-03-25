---
name: codeunit-analyzer
description: >
  Comprehensive C-AL codeunit and table analysis tool for the OneTrade/Navision project.
  Zero-dependency Python script with three sub-commands: analyze (deep dive),
  scan (project-wide bottleneck detection), and optimize (refactoring suggestions).
  Works with Python standard library only - no packages to install! Use when the
  user asks about analyzing codeunits, tables, or pages, finding performance issues, or optimizing
  Navision code. Trigger: "/codeunit-analyzer", "analyze codeunit", "analyze table", "scan bottlenecks".
---

# Codeunit, Table & Page Analyzer

**Zero-dependency** C-AL analysis tool using only Python standard library. Applies seamlessly to both codeunits, tables, and pages.

## ✨ Key Features

- ✅ **No external dependencies** - Pure Python standard library
- ✅ **No virtual environment needed** - Works immediately
- ✅ **Fast & lightweight** - Simple regex-based parsing
- ✅ **Windows compatible** - No Unicode issues
- ✅ **Offline capable** - No API server required

## Sub-Commands

### 1. **list** - Show All Codeunits

List all available .cs and .c-al files in the workspace.

### 2. **analyze** - Deep Codeunit Analysis

Analyze a specific codeunit with bottleneck detection and dependency extraction.

### 3. **scan** - Project-Wide Bottleneck Scan

Scan all codeunits for performance issues and generate ranked report.

### 4. **optimize** - Optimization Recommendations

Get actionable refactoring suggestions with code examples.

### 5. **setloadfields** - SETLOADFIELDS / SELECT-* Audit

Dedicated audit that finds every `FINDSET`, `FINDFIRST`, `FIND`, `FINDLAST`, or `GET` without
`SETLOADFIELDS` and ranks them by **urgency score** — combining:

- **Column-width multiplier** — wider tables (more fields) waste more network bytes per row.
- **Row-count multiplier** — large tables amplify the cost of every unnecessary column.
- **Loop penalty** — reads inside loops are fired N times, so the cost is multiplied.
- **FlowField bonus** — Business Central calculates *all* FlowFields on a `SELECT *`; pinning
  fields with `SETLOADFIELDS` skips those expensive sub-queries entirely.

The table metadata JSON files can optionally include `field_count` (int) and `has_flow_fields`
(bool) to enable precise scoring. If absent, the analyzer falls back to neutral multipliers.

---

## Pre-Flight Setup (Run This First, Every Time)

**Before any command**, resolve two things: the Python executable and the codeunits, tables, or pages directories. Do both in one shot:

```bash
# 1. Find Python
PYTHON=$(command -v python3 || command -v python || echo "uv run python")
$PYTHON --version || { echo "Python not found. Install via: brew install python  OR  uv python install 3.12"; exit 1; }

# 2. Find the SKILL path
SKILL="$(dirname "$(dirname "$(find . -path '*codeunit-analyzer/scripts/analyze.py' | head -1)")")"

# 3. Find the codeunits, tables, or pages directories — check common locations
CODEUNITS_DIR=$(
  for candidate in codeunits data/codeunits src/codeunits .agents/data/codeunits; do
    [ -d "$candidate" ] && { echo "$candidate"; break; }
  done
)

# 4. If not found, search from project root
if [ -z "$CODEUNITS_DIR" ]; then
  CODEUNITS_DIR=$(find . -name "*.c-al" -o -name "*.cs" 2>/dev/null | head -1 | xargs dirname 2>/dev/null)
fi

# 5. Export so the script picks it up automatically
export CODEUNITS_DIR
echo "Python : $PYTHON"
echo "Skill  : $SKILL/scripts/analyze.py"
echo "Codeunits: $CODEUNITS_DIR"
```

> If `CODEUNITS_DIR` is still empty, ask the user where their `.cs`/`.c-al` files are and set it manually:
> `export CODEUNITS_DIR=/path/to/codeunits`

With those three variables set, all commands become:

```bash
$PYTHON $SKILL/scripts/scripts/analyze.py list
$PYTHON $SKILL/scripts/scripts/analyze.py scan
$PYTHON $SKILL/scripts/scripts/analyze.py analyze <file>
```

---

## Quick Start

**No setup required beyond the pre-flight above.**

```bash
# List all available codeunits
$PYTHON $SKILL/scripts/scripts/analyze.py list

# Analyze a specific codeunit
$PYTHON $SKILL/scripts/scripts/analyze.py analyze 1.cs

# Scan all codeunits for bottlenecks
$PYTHON $SKILL/scripts/scripts/analyze.py scan

# Save scan results to file
$PYTHON $SKILL/scripts/scripts/analyze.py scan -o bottlenecks.json

# Get optimization suggestions
$PYTHON $SKILL/scripts/scripts/analyze.py optimize 80.cs

# SETLOADFIELDS audit — project-wide (ranked by urgency)
$PYTHON $SKILL/scripts/analyze.py setloadfields

# SETLOADFIELDS audit — single file
$PYTHON $SKILL/scripts/analyze.py setloadfields 80.cs

# SETLOADFIELDS audit — save JSON, show top 10 tables
$PYTHON $SKILL/scripts/analyze.py setloadfields --top 10 -o slf_report.json
```

---

## Usage Patterns

### Pattern 1: List Files

**User says:**

- "List all codeunits"
- "Show me available files"
- "What codeunits, tables, or pages can I analyze?"

**Action:**

```bash
python .skills/codeunit-analyzer/scripts/scripts/analyze.py list
```

**Output:**
Table showing: File name | Object name | ID

---

### Pattern 2: Analyze Specific Codeunit or Table

**User says:**

- "Analyze codeunit 80"
- "Explain what codeunit 1.cs does"
- "Analyze table 18"
- "Analyze <filename>"

**Action:**

```bash
python .skills/codeunit-analyzer/scripts/scripts/analyze.py analyze <filename>
```

**Steps:**

1. If no filename provided, run `list` first
2. Execute analysis command
3. Display bottlenecks sorted by severity
4. Show dependencies and side effects
5. If critical issues found, suggest running `optimize`

**Output includes:**

- Codeunit overview (ID, name, procedures)
- Performance bottlenecks with severity levels
- Dependencies (tables referenced)
- Side effects (INSERT/MODIFY/DELETE/COMMIT)

---

### Pattern 3: Scan All Codeunits

**User says:**

- "Scan for bottlenecks"
- "Find all performance issues"
- "Which codeunits are slow?"
- "Performance audit"

**Action:**

```bash
python .skills/codeunit-analyzer/scripts/scripts/analyze.py scan
```

**Save to JSON:**

```bash
python .skills/codeunit-analyzer/scripts/scripts/analyze.py scan -o bottlenecks_$(date +%Y%m%d).json
```

**Steps:**

1. Scan all .cs and .c-al files
2. Detect bottlenecks in each
3. Sort by severity and score
4. Group by codeunit
5. Display top 10 offenders
6. Show critical issues first

**Output includes:**

- Total issue count by severity
- Top 10 worst codeunits (by score)
- Critical issues detailed (first 5)
- Optional JSON export for tracking

---

### Pattern 4: Optimize Codeunit

**User says:**

- "Optimize codeunit 80"
- "How can I improve performance?"
- "Fix bottlenecks in <file>"
- "Make it faster"

**Action:**

```bash
python .skills/codeunit-analyzer/scripts/scripts/analyze.py optimize <filename>
```

**Steps:**

1. Analyze the file for bottlenecks
2. Group issues by severity
3. Create phased optimization plan
4. Show code examples for fixes
5. Estimate performance impact

**Output includes:**

- Phase 1: Critical fixes (do first)
- Phase 2: High priority fixes (do next)
- Phase 3: Medium priority backlog
- Recommendations summary
- Estimated performance gains

---

### Pattern 5: SETLOADFIELDS Audit

**User says:**

- "Find all missing SETLOADFIELDS"
- "Which tables are we doing SELECT * on?"
- "We have wide tables — are we loading all columns everywhere?"
- "SETLOADFIELDS performance audit"
- "Where are we fetching all fields without filtering?"

**Action (project-wide):**

```bash
python .skills/codeunit-analyzer/scripts/analyze.py setloadfields
```

**Action (single file):**

```bash
python .skills/codeunit-analyzer/scripts/analyze.py setloadfields <filename>
```

**Flags:**
- `--top N` — show only the N most urgent tables
- `--json` — output raw JSON
- `-o <file>` — save findings to a JSON file

**Output includes:**

- Summary: total missing SETLOADFIELDS, loop occurrences, FlowField tables
- Table ranked by combined urgency score (column-width × row-count × loop penalty)
- Per-read findings with code fix examples

---

## Interactive Flow

**Scenario 1: User invokes with just "list"**

```
User: /codeunit-analyzer list
→ Run: python .skills/codeunit-analyzer/scripts/scripts/analyze.py list
→ Show table of all codeunits
```

**Scenario 2: User wants to analyze but doesn't specify file**

```
User: /codeunit-analyzer analyze
→ Run list first to show options
→ Ask: "Which file would you like to analyze?"
→ User selects file
→ Run: python .skills/codeunit-analyzer/scripts/scripts/analyze.py analyze <selected_file>
```

**Scenario 3: User provides filename directly**

```
User: /codeunit-analyzer analyze 1.cs
→ Run: python .skills/codeunit-analyzer/scripts/scripts/analyze.py analyze 1.cs
→ Display results immediately
```

**Scenario 4: Generic request**

```
User: "Find performance issues"
→ Infer command: scan
→ Run: python .skills/codeunit-analyzer/scripts/scripts/analyze.py scan
```

---

## Detected Bottleneck Patterns

The script detects these performance anti-patterns:

### 1. **N+1 Query** (Critical - 150 points)

Database queries inside loops causing massive slowdown.

**Example:**

```cal
// ❌ Bad: Queries database for each iteration
REPEAT
  Customer.GET(SalesLine."Sell-to Customer No.");
  ...
UNTIL SalesLine.NEXT = 0;

// ✅ Good: Query once, process in memory
Customer.GET(SalesHeader."Sell-to Customer No.");
REPEAT
  ...
UNTIL SalesLine.NEXT = 0;
```

### 2. **Explicit COMMIT** (High - 100 points)

Manual transaction commits that break rollback behavior.

**Example:**

```cal
// ❌ Bad: Breaks automatic rollback
IF Customer.INSERT THEN BEGIN
  COMMIT;  // Don't do this!
  MESSAGE('Customer created');
END;

// ✅ Good: Let NAV handle transactions
IF Customer.INSERT THEN BEGIN
  MESSAGE('Customer created');
END;
```

### 3. **Nested Loops with Writes** (High - 120 points)

Database writes inside nested loops.

**Example:**

```cal
// ❌ Bad: Write operation in nested loop
REPEAT
  ItemEntry.SETRANGE("Item No.", SalesLine."No.");
  IF ItemEntry.FINDSET THEN
    REPEAT
      ItemEntry.Processed := TRUE;
      ItemEntry.MODIFY;  // Slow!
    UNTIL ItemEntry.NEXT = 0;
UNTIL SalesLine.NEXT = 0;

// ✅ Good: Use bulk operations
REPEAT
  ItemEntry.SETRANGE("Item No.", SalesLine."No.");
  ItemEntry.MODIFYALL(Processed, TRUE);  // Fast!
UNTIL SalesLine.NEXT = 0;
```

### 4. **High Write Density** (Medium - 60 points)

Too many individual write operations (>10 per codeunit).

**Recommendation:** Batch operations or use MODIFYALL/DELETEALL.

---

## Output Formatting

### Console Output

```
================================================================================
[1] [CRITICAL] - N Plus One Query
================================================================================
Procedure: PostSalesOrder
Score: 150 points

Issue:
  Database query inside loop - causes N+1 query problem

Recommendation:
  Load all records at once using FINDSET, then process in memory

Code Example:
  // Use FINDSET outside loop
  IF Table.FINDSET THEN
    REPEAT
      // Process here
    UNTIL Table.NEXT = 0;
```

### Severity Levels

- **[CRITICAL]** - Immediate action required (150 points)
- **[HIGH]** - Fix this sprint (100-120 points)
- **[MEDIUM]** - Plan for next sprint (60 points)
- **[LOW]** - Backlog item

### JSON Export Format

```json
[
  {
    "pattern": "n_plus_one_query",
    "severity": "critical",
    "score": 150,
    "procedure": "PostSalesOrder",
    "explanation": "Database query inside loop - causes N+1 query problem",
    "recommendation": "Load all records at once using FINDSET",
    "example": "// Use FINDSET outside loop\nIF Table.FINDSET THEN...",
    "codeunit": {
      "file": "80.cs",
      "object_name": "Sales-Post",
      "object_id": "80"
    }
  }
]
```

---

## Environment Requirements

### Minimal Setup ✨

- **Python:** 3.10+ (standard library only)

### Directory Structure

```
OneTrade/
├── scripts/
│   └── analyze.py          # Standalone script (zero deps)
├── data/
│   └── codeunits/          # Your .cs/.c-al files
└── .skills/
    └── codeunit-analyzer/  # This skill
```

That's it! No `requirements.txt`, no `pip install`, no virtual environment.

---

## Error Handling

### Common Errors

**1. No codeunits found**

```
Error: No codeunits found.
Expected directory: c:\Users\...\data\codeunits
```

**Solution:** Create the data directory and add your .cs or .c-al files.

**2. File not found**

```
Error: FileNotFoundError: '80.cs'
```

**Solution:** Run `python .skills/codeunit-analyzer/scripts/scripts/analyze.py list` to see available files.

**3. No bottlenecks detected**

```
[OK] No bottlenecks detected - this codeunit is already optimized!
```

**Solution:** Great news! No action needed.

---

## AL-Perf Integrated Anti-Patterns

The analyzer incorporates advanced source-correlated checks natively adopted from `al-perf`:
- **Missing SetLoadFields** (Medium): Flags `FINDSET/FINDFIRST` executed without `SETLOADFIELDS()`. Navision defaults to `SELECT *` across the network, bloating the buffer.
- **Unfiltered FindSet** (High): Flags `FINDSET` operations lacking `SETRANGE` or `SETFILTER`, severely impacting SQL Server memory caching by pulling entire tables.
- **Event Subscriber Hotspots** (Critical): Flags `[EventSubscriber]` procedures containing data-loops or heavy read operations. Because Navision Event Subscribers run globally and synchronously, any blocked loop here degrades the entire ERP execution context.

---

## Troubleshooting

### Script won't run

**Check Python version:**

```bash
python --version  # Should be 3.10+
```

**Run from project root:**

```bash
python .skills/codeunit-analyzer/scripts/scripts/analyze.py list
```

### No files listed

**Check data directory:**

```bash
ls data/codeunits/*.cs | wc -l
```

If empty, add your C-AL files to `data/codeunits/`.

### Permission denied (Linux/Mac)

```bash
chmod +x scripts/analyze.py
python .skills/codeunit-analyzer/scripts/scripts/analyze.py list
```

---

## Performance Notes

- **List:** < 1 second for 2000+ files
- **Analyze:** < 2 seconds per file
- **Scan:** Processes all files sequentially (~1-2 sec per file)
- **Optimize:** < 2 seconds per file

**Note:** No caching implemented yet - each run re-parses files. This keeps the code simple and dependency-free.

---

## Examples

### Example 1: Quick list

```bash
python .skills/codeunit-analyzer/scripts/scripts/analyze.py list
```

Output:

```
Found 2414 codeunits:

File                 Object Name                                        ID
==================================================================================
1.cs                 ApplicationManagement                              1
80.cs                Sales-Post                                         80
...
```

### Example 2: Analyze specific file

```bash
python .skills/codeunit-analyzer/scripts/scripts/analyze.py analyze 80.cs
```

Output:

```
================================================================================
CODEUNIT: Sales-Post
================================================================================
ID: 80
Procedures: 15
File: 80.cs

================================================================================
PERFORMANCE BOTTLENECKS (5 issues)
================================================================================

Critical: 2
High: 2
Medium: 1

[Detailed bottleneck information follows...]
```

### Example 3: Full scan

```bash
python .skills/codeunit-analyzer/scripts/scripts/analyze.py scan -o scan_results.json
```

Output:

```
================================================================================
BOTTLENECK SCAN SUMMARY
================================================================================
Total Issues: 147
  Critical: 23
  High: 45
  Medium: 67
  Low: 12

================================================================================
TOP OFFENDERS (by total score)
================================================================================

1. Sales-Post (80.cs)
   Issues: 12 | Critical: 3 | High: 5 | Medium: 4
   Total Score: 850 points

[Top 10 worst codeunits listed...]

Full report saved to: scan_results.json
```

---

## Tips

1. **Start with scan** - Get overview before drilling down
2. **Save scan results** - Track progress over time with dated files
3. **Focus on critical** - [CRITICAL] issues have biggest impact
4. **Test after fixes** - Verify changes don't break business logic
5. **Use JSON export** - Integrate with other tools or CI/CD

---

## Limitations

This is a **simplified parser** using regex. It may not detect:

- Complex nested logic
- Dynamic table references
- Indirect procedure calls
- Some edge case patterns

For production use, consider the full analysis service with Pydantic schemas and comprehensive parsing.

---

## Comparison: Standalone vs Full Service

| Feature         | Standalone Script | Full Service              |
| --------------- | ----------------- | ------------------------- |
| Dependencies    | None              | Pydantic, Cashews, etc.   |
| Setup           | Zero              | Virtual env + pip install |
| Speed           | Fast              | Faster (cached)           |
| Accuracy        | Good (regex)      | Excellent (full parser)   |
| Offline         | ✅ Yes            | ✅ Yes                    |
| Table metadata  | ❌ No             | ✅ Yes                    |
| AI explanations | ❌ No             | ✅ Yes (with Azure)       |
| Best for        | Quick analysis    | Production use            |

**Use standalone for:** Quick scans, CI/CD, no-dependency environments
**Use full service for:** Detailed analysis, AI insights, production workflows

---

## Related Files

- **Main Script:** [analyze.py](./analyze.py)
- **Documentation:** [.skills/README.md](../README.md)
- **Summary:** [.skills/SUMMARY.md](../SUMMARY.md)
- **Project Docs:** [CLAUDE.md](../../CLAUDE.md)

---

**Ready to use!** No installation, no dependencies, just Python. 🚀

### 5. **Page Navigation Trigger Abuse** (High/Critical)
Heavy queries (GET >= 3), nested database writes (MODIFY), or `PAGE.RUN` calls inside `OnAfterGetRecord` and similar UI rendering triggers.

**Recommendation:** Cache records inside Temp tables or run heavy logic exclusively via user-explicit `OnAction` events.
