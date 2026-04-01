"""Databricks CLI — run code and explore Unity Catalog metadata.

Subcommands: run | tables | describe | search
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import metadata as _meta
import run as _run


def cmd_run(args: argparse.Namespace) -> int:
    code = args.file.read_text(encoding="utf-8") if args.file else args.code
    language = _run.detect_language(args.file, args.lang)

    if args.args and language == "python":
        try:
            json.loads(args.args)
        except json.JSONDecodeError as e:
            print(f"[error] --args must be valid JSON: {e}", file=sys.stderr)
            return 1
        code = f"ARGS = {args.args}\n{code}"

    if language == "sql" and args.output_format == "markdown":
        code = _run.wrap_sql_as_json(code)
        language = "python"

    print(f"[run] profile={args.profile} cluster={args.cluster_id} lang={language}", file=sys.stderr)
    print("[run] opening execution context …", file=sys.stderr)
    ctx_id = _run.create_context(args.profile, args.cluster_id, language)
    print(f"[run] context {ctx_id}", file=sys.stderr)

    try:
        print("[run] submitting command …", file=sys.stderr)
        cmd_id = _run.execute(args.profile, args.cluster_id, ctx_id, language, code)
        resp = _run.poll(args.profile, args.cluster_id, ctx_id, cmd_id, interval=args.poll_interval)
    finally:
        if not args.no_destroy:
            _run.destroy_context(args.profile, args.cluster_id, ctx_id)

    return _run.print_result(resp, output_format=args.output_format)


def cmd_tables(args: argparse.Namespace) -> int:
    tbls = _meta.tables(args.profile, args.catalog, args.schema)
    if not tbls:
        print(f"No tables found in {args.catalog}.{args.schema}")
        return 0

    rows = [
        [
            f"{t.get('catalog_name','')}.{t.get('schema_name','')}.{t.get('name','')}",
            t.get("table_type", ""),
            (t.get("comment") or "").replace("\n", " ")[:100],
        ]
        for t in tbls
    ]
    print(_run.format_markdown_table(["Table", "Type", "Description"], rows))
    print(f"\n{len(tbls)} table(s) in {args.catalog}.{args.schema}")
    return 0


def cmd_describe(args: argparse.Namespace) -> int:
    t = _meta.describe(args.profile, args.fqn)
    if not t:
        print(f"[error] Table not found: {args.fqn}", file=sys.stderr)
        return 1

    full_name = t.get("full_name") or args.fqn
    print(f"## {full_name}")
    print(f"Type: {t.get('table_type', 'UNKNOWN')}  |  Owner: {t.get('owner', '?')}")

    if t.get("comment"):
        print(f"\n{t['comment']}")

    cols = t.get("columns", [])
    if cols:
        print()
        rows = [
            [
                c.get("name", ""),
                c.get("type_text") or c.get("type_name", ""),
                "YES" if c.get("nullable", True) else "NO",
                (c.get("comment") or ""),
            ]
            for c in cols
        ]
        print(_run.format_markdown_table(["Column", "Type", "Nullable", "Description"], rows))

    return 0


def cmd_search(args: argparse.Namespace) -> int:
    _meta.search(args.profile, args.keyword, catalog=args.catalog)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="Databricks CLI — run code and explore Unity Catalog metadata.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Execute Python/SQL on a cluster")
    p_run.add_argument("--profile", required=True, help="Databricks CLI profile")
    p_run.add_argument("--cluster-id", required=True, dest="cluster_id", help="Cluster ID to run on")
    p_run.add_argument("--lang", help="Language: python | sql | r | scala (default: inferred from file)")

    src = p_run.add_mutually_exclusive_group(required=True)
    src.add_argument("--code", help="Inline code string")
    src.add_argument("--file", type=Path, help="Local script file")

    p_run.add_argument("--args", help="JSON dict injected as ARGS variable (Python only)")
    p_run.add_argument("--format", dest="output_format", choices=["text", "markdown"], default="text")
    p_run.add_argument("--no-destroy", action="store_true", help="Keep execution context open after run")
    p_run.add_argument("--poll-interval", type=float, default=2.0, metavar="SEC")

    p_tables = sub.add_parser("tables", help="List tables in a catalog.schema")
    p_tables.add_argument("--profile", required=True, help="Databricks CLI profile")
    p_tables.add_argument("--catalog", required=True, help="Catalog name")
    p_tables.add_argument("--schema", required=True, help="Schema name")

    p_desc = sub.add_parser("describe", help="Full metadata for a single table")
    p_desc.add_argument("--profile", required=True, help="Databricks CLI profile")
    p_desc.add_argument("fqn", metavar="CATALOG.SCHEMA.TABLE", help="Fully qualified table name")

    p_search = sub.add_parser("search", help="Find tables by keyword (no cluster needed)")
    p_search.add_argument("--profile", required=True, help="Databricks CLI profile")
    p_search.add_argument("keyword", metavar="KEYWORD", help="Keyword to search for in table names")
    p_search.add_argument("--catalog", help="Restrict search to a specific catalog")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    handlers = {
        "run": cmd_run,
        "tables": cmd_tables,
        "describe": cmd_describe,
        "search": cmd_search,
    }
    sys.exit(handlers[args.command](args))


if __name__ == "__main__":
    main()
