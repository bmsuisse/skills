"""
SQL Dependency Analyzer for Fabricks.Runtime

Uses sqlglot + networkx to build a dependency DAG from all .sql files.
Node weight = COUNT(*) fetched from Databricks (views are skipped).
Finds the top-N most depended-upon tables and analyzes them for
performance improvements, optionally fetching EXPLAIN COST plans.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import networkx as nx
import sqlglot
import sqlglot.expressions as exp
from tqdm import tqdm

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

ROOT = Path(__file__).parent.parent.parent.parent

# ---------------------------------------------------------------------------
# 1. Collect SQL files
# ---------------------------------------------------------------------------

SKIP_PATTERNS = {".post_run.", ".pre_run."}


def collect_sql_files() -> list[Path]:
    all_sql = sorted(ROOT.rglob("*.sql"))
    files: list[Path] = []
    for path in tqdm(all_sql, desc="Scanning SQL files", unit="file", ncols=80):
        name = path.name
        if any(p in name for p in SKIP_PATTERNS):
            continue
        if "udfs" in path.parts:
            continue
        files.append(path)
    return files


# ---------------------------------------------------------------------------
# 2. Map file path -> output table name (Fabricks convention)
#    gold/{step}/{topic}/{item}.sql  ->  {step}.{topic}_{item}
# ---------------------------------------------------------------------------


def file_to_table(path: Path) -> str | None:
    try:
        rel = path.relative_to(ROOT / "gold")
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) < 3:
        return None
    step, topic, item = parts[0], parts[1], parts[2].replace(".sql", "")
    return f"{step}.{topic}_{item}"


# ---------------------------------------------------------------------------
# 3. Extract table references via sqlglot
# ---------------------------------------------------------------------------


def extract_tables(sql: str) -> set[str]:
    tables: set[str] = set()
    try:
        for stmt in sqlglot.parse(sql, dialect="spark"):
            if stmt is None:
                continue
            for table in stmt.find_all(exp.Table):
                db = table.args.get("db")
                tbl = table.args.get("this")
                if db and tbl:
                    db_name = db.name if hasattr(db, "name") else str(db)
                    tbl_name = tbl.name if hasattr(tbl, "name") else str(tbl)
                    tables.add(f"{db_name}.{tbl_name}")
    except Exception:
        for m in re.finditer(r"\b([a-zA-Z_]\w*)\.([a-zA-Z_]\w*)\b", sql):
            schema = m.group(1)
            if schema.lower() not in {"udf", "spark", "dbfs"}:
                tables.add(f"{schema}.{m.group(2)}")
    return tables


# ---------------------------------------------------------------------------
# 4. Build NetworkX dependency DiGraph
# ---------------------------------------------------------------------------


def build_graph(sql_files: list[Path]) -> tuple[nx.DiGraph, dict[Path, str | None]]:
    G: nx.DiGraph = nx.DiGraph()
    file_table_map: dict[Path, str | None] = {}

    for path in tqdm(sql_files, desc="Parsing & building graph", unit="file", ncols=80):
        sql = path.read_text(encoding="utf-8", errors="ignore")
        deps = extract_tables(sql)
        output = file_to_table(path)
        file_table_map[path] = output

        src = output if output else str(path.relative_to(ROOT))
        G.add_node(src, kind="table" if output else "file", path=str(path.relative_to(ROOT)))

        for dep in deps:
            if dep == src:
                continue
            G.add_node(dep, kind="table")
            G.add_edge(src, dep)

    return G, file_table_map


# ---------------------------------------------------------------------------
# 5. Top-N most depended-upon tables (highest in-degree)
# ---------------------------------------------------------------------------


def top_depended(G: nx.DiGraph, n: int | None = 10) -> list[tuple[str, int]]:
    in_deg = [(node, G.in_degree(node)) for node in G.nodes()]
    ranked = sorted(in_deg, key=lambda x: -x[1])
    return ranked[:n] if n else ranked


# ---------------------------------------------------------------------------
# 6. Databricks helpers
# ---------------------------------------------------------------------------


def _get_workspace_client(profile: str):  # type: ignore[no-untyped-def]
    from databricks.sdk import WorkspaceClient

    return WorkspaceClient(profile=profile)


def fetch_row_counts(
    tables: list[str],
    profile: str = "premium",
    skip_views: bool = True,
) -> dict[str, int | None]:
    """
    For each table name (schema.table) fetch COUNT(*) via a SQL warehouse.
    Views are skipped (row_count = None) because materialised counts are
    meaningless for views and they can be expensive to execute.
    Returns {table: count_or_None}
    """
    result: dict[str, int | None] = {}

    try:
        from databricks.sdk.service.sql import StatementState

        w = _get_workspace_client(profile)
        warehouses = [
            wh
            for wh in w.warehouses.list()
            if wh.state and wh.state.name in ("RUNNING", "STARTING")
        ]
        if not warehouses:
            print("  [row-count] No running SQL warehouse found -- skipping row counts")
            return {t: None for t in tables}

        warehouse_id = warehouses[0].id
        tqdm.write(f"  Using warehouse: {warehouses[0].name} ({warehouse_id})")

        for table in tqdm(tables, desc="Fetching row counts", unit="table", ncols=80):
            if skip_views:
                try:
                    chk = w.statement_execution.execute_statement(
                        warehouse_id=warehouse_id,
                        statement=f"SHOW CREATE TABLE {table}",
                        wait_timeout="15s",
                    )
                    if chk.result and chk.result.data_array:
                        ddl = " ".join(str(r) for r in chk.result.data_array).upper()
                        if "CREATE VIEW" in ddl or "CREATE OR REPLACE VIEW" in ddl:
                            tqdm.write(f"  [skip] {table} is a view")
                            result[table] = None
                            continue
                except Exception:
                    pass

            try:
                resp = w.statement_execution.execute_statement(
                    warehouse_id=warehouse_id,
                    statement=f"SELECT COUNT(*) FROM {table}",
                    wait_timeout="30s",
                )
                if resp.status and resp.status.state == StatementState.SUCCEEDED:
                    if resp.result and resp.result.data_array:
                        count = int(resp.result.data_array[0][0])
                        result[table] = count
                        tqdm.write(f"  {table}: {count:,} rows")
                    else:
                        result[table] = None
                else:
                    err = resp.status.error if resp.status else "unknown"
                    tqdm.write(f"  {table}: ERROR ({err})")
                    result[table] = None
            except Exception as e:
                tqdm.write(f"  {table}: ERROR ({e})")
                result[table] = None

    except Exception as e:
        print(f"  [row-count] Could not connect to Databricks: {e}")
        return {t: None for t in tables}

    return result


def get_execution_plan(sql: str, profile: str = "premium") -> str | None:
    try:
        from databricks.sdk.service.sql import StatementState

        w = _get_workspace_client(profile)
        warehouses = [
            wh
            for wh in w.warehouses.list()
            if wh.state and wh.state.name in ("RUNNING", "STARTING")
        ]
        if not warehouses:
            return "No running SQL warehouse found -- start one first"

        warehouse_id = warehouses[0].id
        resp = w.statement_execution.execute_statement(
            warehouse_id=warehouse_id,
            statement=f"EXPLAIN COST\n{sql}",
            wait_timeout="30s",
        )
        if resp.status and resp.status.state == StatementState.SUCCEEDED:
            if resp.result and resp.result.data_array:
                return "\n".join(str(row) for row in resp.result.data_array[:80])
        elif resp.status:
            return f"Statement failed: {resp.status.error}"
        return "No plan returned"
    except Exception as e:
        return f"Error: {e}"


# ---------------------------------------------------------------------------
# 7. Performance heuristics
# ---------------------------------------------------------------------------

# Each entry: (name, compiled_regex, description)
PERF_CHECKS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "SELECT *",
        re.compile(r"\bselect\s+\*", re.IGNORECASE),
        "Avoid SELECT * — select only needed columns to reduce shuffle/IO",
    ),
    (
        "CROSS JOIN",
        re.compile(r"\bcross\s+join\b", re.IGNORECASE),
        "CROSS JOIN detected — ensure intentional, can cause exponential row explosion",
    ),
    (
        "Implicit cross join",
        re.compile(r"\bfrom\s+\w+\s*,\s*\w+", re.IGNORECASE),
        "Comma-separated FROM clause creates an implicit CROSS JOIN — use explicit JOIN syntax",
    ),
    (
        "Subquery in SELECT",
        re.compile(r"select\s+.*?\(\s*select\b", re.IGNORECASE | re.DOTALL),
        "Correlated subquery in SELECT — rewrite as a CTE + LEFT JOIN for better performance",
    ),
    (
        "OR in JOIN condition",
        re.compile(r"\bjoin\b.{0,200}\bor\b", re.IGNORECASE | re.DOTALL),
        "OR in JOIN prevents efficient hash join — split into UNION ALL or use CASE",
    ),
    (
        "NOT IN subquery",
        re.compile(r"\bnot\s+in\s*\(\s*select\b", re.IGNORECASE | re.DOTALL),
        "NOT IN with subquery — rewrite as LEFT ANTI JOIN for better performance",
    ),
    (
        "IN subquery",
        re.compile(r"\bwhere\b.{0,200}\bin\s*\(\s*select\b", re.IGNORECASE | re.DOTALL),
        "WHERE x IN (SELECT …) — prefer EXISTS or LEFT SEMI JOIN for Spark optimization",
    ),
    (
        "UDF in WHERE/JOIN",
        re.compile(r"(?:where|on)\s+[^;]*?\budf_\w+\s*\(", re.IGNORECASE | re.DOTALL),
        "UDF in WHERE/JOIN predicate — may prevent predicate pushdown",
    ),
    (
        "LIKE %val%",
        re.compile(r"\blike\s+'%[^']+%'", re.IGNORECASE),
        "LIKE with leading wildcard forces full string scan — use exact matches or bloom filters",
    ),
    (
        "ILIKE",
        re.compile(r"\bilike\b", re.IGNORECASE),
        "ILIKE does case-insensitive full string scan — use LOWER(col) LIKE where possible",
    ),
    (
        "EXPLODE",
        re.compile(r"\bexplode\s*\(", re.IGNORECASE),
        "EXPLODE multiplies rows — filter upstream before exploding when possible",
    ),
    (
        "SELECT DISTINCT",
        re.compile(r"\bselect\s+distinct\b", re.IGNORECASE),
        "SELECT DISTINCT can be expensive — GROUP BY ALL is usually more explicit/optimizable",
    ),
    (
        "Unbounded window frame",
        re.compile(
            r"\b(rows|range)\s+between\s+unbounded\s+preceding\s+and\s+unbounded\s+following\b",
            re.IGNORECASE,
        ),
        "Unbounded window frame buffers entire partition — reconsider if a narrower frame suffices",
    ),
    (
        "CAST on JOIN key",
        re.compile(r"\bon\s+[^;]{0,300}cast\s*\(", re.IGNORECASE | re.DOTALL),
        "CAST inside JOIN ON clause may prevent partition pruning and disable statistics — cast upstream in a CTE",
    ),
    (
        "array_contains in JOIN",
        re.compile(r"\bon\s+[^;]{0,300}array_contains\s*\(", re.IGNORECASE | re.DOTALL),
        "array_contains in JOIN condition disables sort-merge join and forces nested-loop execution",
    ),
]

# Severity weights used for impact_score computation
SEVERITY_WEIGHTS: dict[str, int] = {
    "CROSS JOIN": 10,
    "Implicit cross join": 10,
    "NOT IN subquery": 8,
    "OR in JOIN condition": 8,
    "Subquery in SELECT": 6,
    "CAST on JOIN key": 6,
    "IN subquery": 5,
    "Unbounded window frame": 5,
    "SELECT *": 5,
    "Repeated scan": 4,
    "EXPLODE": 4,
    "UDF in WHERE/JOIN": 3,
    "array_contains in JOIN": 3,
    "SELECT DISTINCT": 2,
    "LIKE %val%": 2,
    "ILIKE": 2,
}


def analyze_sql(sql: str) -> list[tuple[str, str]]:
    """Return list of (warning_name, warning_message) for all detected issues."""
    warnings: list[tuple[str, str]] = []
    for name, pattern, msg in PERF_CHECKS:
        if pattern.search(sql):
            warnings.append((name, f"[{name}] {msg}"))

    # Repeated source scan (≥2×)
    sources = re.findall(r"\bfrom\s+(\w+\.\w+)", sql, re.IGNORECASE)
    sources += re.findall(r"\bjoin\s+(\w+\.\w+)", sql, re.IGNORECASE)
    counts: dict[str, int] = defaultdict(int)
    for s in sources:
        counts[s.lower()] += 1
    for tbl, cnt in counts.items():
        if cnt >= 2:
            warnings.append(
                (
                    "Repeated scan",
                    f"[Repeated scan] '{tbl}' referenced {cnt}× — consider materializing as a CTE",
                )
            )

    return warnings


def compute_impact_score(dep_count: int, row_count: int | None, warning_names: list[str]) -> float:
    severity_sum = sum(SEVERITY_WEIGHTS.get(name, 1) for name in warning_names)
    rc_millions = (row_count or 0) / 1_000_000
    return (dep_count * 10) + (rc_millions * 5) + severity_sum


# ---------------------------------------------------------------------------
# 8. Graph stats
# ---------------------------------------------------------------------------


def graph_stats(G: nx.DiGraph) -> dict[str, int]:
    try:
        cycles = len(list(nx.simple_cycles(G)))
    except Exception:
        cycles = -1
    return {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "weakly_connected_components": nx.number_weakly_connected_components(G),
        "cycles": cycles,
    }


# ---------------------------------------------------------------------------
# 9. Graph visualisation (NetworkX + Plotly — interactive HTML)
# ---------------------------------------------------------------------------


def render_graph(
    G: nx.DiGraph,
    top_tables: list[tuple[str, int]],
    row_counts: dict[str, int | None] | None = None,
    output_path: str | None = None,
    depth: int = 1,
) -> None:
    """
    Render an interactive Plotly network graph centred on the top-N tables.

    Layout  : Kamada-Kawai (falls back to spring layout on error)
    Node size : proportional to in-degree (dependency count)
    Node colour:
        - #e05252 red    → top-tercile in-degree (hottest)
        - #f0a830 orange → mid-tercile
        - #4a90d9 blue   → low in-degree
    Hover tooltip : full table name, in-degree, row count (if available)
    Output  : written as a self-contained HTML file to *output_path*;
              if omitted, opens in the default browser via plotly.io.show().
    Requires: plotly  (`uv add plotly`)
    """
    import importlib.util

    if importlib.util.find_spec("plotly") is None:
        print("[graph] plotly is not installed. Run `uv add plotly` and retry.")
        return

    import plotly.graph_objects as go

    top_nodes = [t for t, _ in top_tables]

    # --- build subgraph --------------------------------------------------
    visible: set[str] = set(top_nodes)
    for node in top_nodes:
        for _ in range(depth):
            visible.update(G.predecessors(node))
            visible.update(G.successors(node))
    sub = G.subgraph(visible).copy()

    # --- layout ----------------------------------------------------------
    try:
        pos = nx.kamada_kawai_layout(sub)
    except Exception:
        pos = nx.spring_layout(sub, seed=42, k=2.5 / (len(sub.nodes()) ** 0.5 + 1))

    # --- node attributes -------------------------------------------------
    in_degrees = dict(sub.in_degree())
    max_deg = max(in_degrees.values(), default=1) or 1

    sorted_degs = sorted(in_degrees.values())
    n = len(sorted_degs)
    tier_hi  = sorted_degs[int(n * 0.66)] if n >= 3 else sorted_degs[-1]
    tier_mid = sorted_degs[int(n * 0.33)] if n >= 3 else 0

    COLOR_HOT  = "#e05252"
    COLOR_WARM = "#f0a830"
    COLOR_COOL = "#4a90d9"

    node_list = list(sub.nodes())
    node_x = [pos[nd][0] for nd in node_list]
    node_y = [pos[nd][1] for nd in node_list]
    node_colors: list[str] = []
    node_sizes: list[float] = []
    node_text: list[str] = []      # hover
    node_labels: list[str] = []    # short label on the node

    for nd in node_list:
        deg = in_degrees.get(nd, 0)
        rc = (row_counts or {}).get(nd)
        rc_str = f"{rc:,}" if rc is not None else "n/a"

        if deg >= tier_hi:
            node_colors.append(COLOR_HOT)
        elif deg >= tier_mid:
            node_colors.append(COLOR_WARM)
        else:
            node_colors.append(COLOR_COOL)

        # size: 18–60 px, linear in in-degree
        node_sizes.append(18 + 42 * deg / max_deg)

        node_text.append(
            f"<b>{nd}</b><br>"
            f"In-degree (dependents): {deg}<br>"
            f"Row count: {rc_str}"
        )
        node_labels.append(".".join(nd.split(".")[-2:]) if "." in nd else nd)

    # --- edge traces (one per edge so we can draw arrows) ----------------
    edge_traces: list[go.Scatter] = []
    annotations: list[dict] = []

    for src, dst in sub.edges():
        x0, y0 = pos[src]
        x1, y1 = pos[dst]
        # thin line
        edge_traces.append(
            go.Scatter(
                x=[x0, x1, None],
                y=[y0, y1, None],
                mode="lines",
                line={"width": 0.8, "color": "#8888aa"},
                hoverinfo="none",
                showlegend=False,
            )
        )
        # arrowhead annotation
        annotations.append(
            dict(
                ax=x0, ay=y0,
                x=x1,  y=y1,
                xref="x", yref="y",
                axref="x", ayref="y",
                showarrow=True,
                arrowhead=3,
                arrowsize=1.2,
                arrowwidth=1.0,
                arrowcolor="#8888aa",
                opacity=0.6,
            )
        )

    # --- node trace -------------------------------------------------------
    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        hoverinfo="text",
        hovertext=node_text,
        text=node_labels,
        textposition="top center",
        textfont={"size": 9, "color": "#ffffff"},
        marker=dict(
            color=node_colors,
            size=node_sizes,
            line={"width": 1, "color": "#ffffff44"},
            opacity=0.92,
        ),
        showlegend=False,
    )

    # --- legend as dummy scatter traces -----------------------------------
    legend_traces = [
        go.Scatter(
            x=[None], y=[None], mode="markers",
            marker={"color": COLOR_HOT,  "size": 12},
            name="High in-degree (hot)",
        ),
        go.Scatter(
            x=[None], y=[None], mode="markers",
            marker={"color": COLOR_WARM, "size": 12},
            name="Medium in-degree",
        ),
        go.Scatter(
            x=[None], y=[None], mode="markers",
            marker={"color": COLOR_COOL, "size": 12},
            name="Low in-degree",
        ),
    ]

    # --- assemble figure --------------------------------------------------
    fig = go.Figure(
        data=[*edge_traces, node_trace, *legend_traces],
        layout=go.Layout(
            title=dict(
                text=(
                    f"Fabricks SQL Dependency Graph — "
                    f"Top {len(top_nodes)} tables + {depth}-hop neighbours"
                ),
                font={"size": 16, "color": "#e0e0ff"},
            ),
            paper_bgcolor="#1a1a2e",
            plot_bgcolor="#1a1a2e",
            font={"color": "#ccccee"},
            showlegend=True,
            legend=dict(
                bgcolor="#22224a",
                bordercolor="#444466",
                borderwidth=1,
                font={"size": 11},
            ),
            hovermode="closest",
            xaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
            yaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
            annotations=annotations,
            margin={"l": 20, "r": 20, "t": 50, "b": 20},
        ),
    )

    if output_path:
        fig.write_html(output_path, include_plotlyjs="cdn")
        print(f"\n[graph] Saved → {output_path}")
    else:
        fig.show()


def find_source_file(table: str, file_table_map: dict[Path, str | None]) -> Path | None:
    for path, tbl in file_table_map.items():
        if tbl and tbl.lower() == table.lower():
            return path
    return None


# ---------------------------------------------------------------------------
# 9. Main
# ---------------------------------------------------------------------------

SEP = "-" * 70
SEP2 = "=" * 70


def main() -> None:
    parser = argparse.ArgumentParser(description="Fabricks SQL dependency & performance analyzer")
    parser.add_argument("--top", type=int, default=10, help="Number of top depended tables to analyze")
    parser.add_argument(
        "--all-files",
        action="store_true",
        help="Analyze every SQL file, not just the top-N most depended-upon",
    )
    parser.add_argument(
        "--score-threshold",
        type=float,
        default=0.0,
        help="Skip tables with impact_score below this value",
    )
    parser.add_argument(
        "--row-counts",
        action="store_true",
        help="Fetch COUNT(*) from Databricks to use as node weights (skips views)",
    )
    parser.add_argument("--explain", action="store_true", help="Fetch EXPLAIN COST from Databricks")
    parser.add_argument("--profile", default="premium", help="Databricks CLI profile (default: premium)")
    parser.add_argument("--json", dest="output_json", metavar="FILE", help="Write results to JSON file")
    parser.add_argument(
        "--ancestors",
        metavar="TABLE",
        help="Print all transitive dependencies of a given table and exit",
    )
    # Graph visualisation
    parser.add_argument(
        "--graph",
        action="store_true",
        help="Render a NetworkX dependency subgraph for the top-N tables",
    )
    parser.add_argument(
        "--graph-output",
        metavar="FILE",
        default=None,
        help="Save the graph to FILE (PNG/SVG/PDF). If omitted the graph is shown interactively.",
    )
    parser.add_argument(
        "--graph-depth",
        type=int,
        default=1,
        help="Number of hops beyond the top-N nodes to include in the graph (default: 1)",
    )
    args = parser.parse_args()

    print(SEP2)
    print("FABRICKS SQL DEPENDENCY ANALYZER")
    print(SEP2)

    sql_files = collect_sql_files()
    print(f"\nFound {len(sql_files)} SQL files")

    G, file_table_map = build_graph(sql_files)

    stats = graph_stats(G)
    print(
        f"Graph: {stats['nodes']} nodes, {stats['edges']} edges, "
        f"{stats['weakly_connected_components']} components, {stats['cycles']} cycles"
    )

    if args.ancestors:
        node = args.ancestors
        if node not in G:
            print(f"\nNode '{node}' not found in graph.")
        else:
            ancestors = nx.ancestors(G, node)
            print(f"\nTransitive dependencies of '{node}' ({len(ancestors)} nodes):")
            for a in sorted(ancestors):
                print(f"  {a}")
        return

    top_all: list[tuple[str, int]] = top_depended(G, n=None)
    print(f"\n{'TABLE':<55} {'DEPENDENTS':>10}")
    print(SEP)
    for tbl, cnt in top_all[:30]:
        print(f"  {tbl:<53} {cnt:>10}")
    if len(top_all) > 30:
        print(f"  ... and {len(top_all) - 30} more")

    if args.all_files:
        candidate_tables: list[tuple[str, int]] = top_all
    else:
        candidate_tables = top_all[: args.top]

    row_counts: dict[str, int | None] = {}
    if args.row_counts:
        print(f"\nFetching row counts for {len(candidate_tables)} tables ...")
        table_names = [t for t, _ in candidate_tables]
        row_counts = fetch_row_counts(table_names, profile=args.profile, skip_views=True)
        for tbl, cnt in row_counts.items():
            if tbl in G:
                G.nodes[tbl]["row_count"] = cnt

    results: list[dict] = []

    print(f"\n{SEP2}")
    print(f"ANALYZING {len(candidate_tables)} TABLES — PERFORMANCE REPORT")
    print(SEP2)

    for rank, (table, dep_count) in enumerate(
        tqdm(candidate_tables, desc="Analyzing tables", unit="table", ncols=80, leave=False), 1
    ):
        print(f"\n{SEP}")
        rc = row_counts.get(table)
        rc_str = f"  rows={rc:,}" if rc is not None else ""
        print(f"#{rank}  {table}  ({dep_count} dependents{rc_str})")
        print(SEP)

        direct_deps = sorted(G.predecessors(table))
        print(f"  Direct dependents ({len(direct_deps)}):")
        for d in direct_deps[:10]:
            print(f"    + {d}")
        if len(direct_deps) > 10:
            print(f"    ... and {len(direct_deps) - 10} more")

        try:
            transitive = nx.ancestors(G, table)
        except Exception:
            transitive = set()

        source_file = find_source_file(table, file_table_map)
        warning_pairs: list[tuple[str, str]] = []
        plan: str | None = None

        if source_file:
            rel = source_file.relative_to(ROOT)
            print(f"\n  Source SQL: {rel}")
            sql_text = source_file.read_text(encoding="utf-8", errors="ignore")
            warning_pairs = analyze_sql(sql_text)

            if warning_pairs:
                print("\n  Performance warnings:")
                for _name, msg in warning_pairs:
                    print(f"    ! {msg}")
            else:
                print("\n  No performance warnings detected.")

            if args.explain:
                print("\n  Fetching EXPLAIN COST from Databricks ...")
                plan = get_execution_plan(sql_text, profile=args.profile)
                if plan:
                    print("\n  Execution plan (first 80 lines):")
                    for line in plan.splitlines()[:80]:
                        print(f"    {line}")
        else:
            print("\n  (No gold SQL source — may be staging/raw/external table)")

        warning_names = [name for name, _ in warning_pairs]
        warning_messages = [msg for _, msg in warning_pairs]
        impact = compute_impact_score(dep_count, rc, warning_names)
        print(f"\n  Impact score: {impact:.1f}")

        if impact < args.score_threshold:
            print(f"  (Below score threshold {args.score_threshold} — skipping)")
            continue

        results.append(
            {
                "rank": rank,
                "table": table,
                "dependent_count": dep_count,
                "row_count": row_counts.get(table),
                "direct_dependents": direct_deps,
                "transitive_dependent_count": len(transitive),
                "source_file": str(source_file.relative_to(ROOT)) if source_file else None,
                "performance_warnings": warning_messages,
                "warning_names": warning_names,
                "impact_score": impact,
                "execution_plan": plan,
            }
        )

    # Sort results by impact_score descending
    results.sort(key=lambda x: -x["impact_score"])

    if args.output_json:
        out = Path(args.output_json)
        out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nResults written to {out}")

    if args.graph:
        print(f"\n[graph] Rendering subgraph for top {len(candidate_tables)} tables ...")
        render_graph(
            G,
            top_tables=candidate_tables,
            row_counts=row_counts if args.row_counts else None,
            output_path=args.graph_output,
            depth=args.graph_depth,
        )

    print(f"\n{SEP2}")
    print("Done.")


if __name__ == "__main__":
    main()
