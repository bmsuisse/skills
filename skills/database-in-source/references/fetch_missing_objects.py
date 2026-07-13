#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "sqlglot",
#   "psycopg[binary]",
#   "questionary",
#   "python-dotenv",
#   "shandy-sqlfmt[jinjafmt]",
# ]
# ///
"""
Fetches DDL from PostgreSQL for tables, scalar functions, and table
functions that exist in the database but aren't yet tracked as .sql
files under database/, then writes them to the matching layer folder's
tables/, scalar_functions/, or table_functions/ subfolder (matched by
schema name, ignoring each layer folder's leading sort number).

Adjust _PREFIX below to match the project's env-var naming. Add more
entries to OBJECT_KINDS to cover other object types (views, procedures, ...).

Usage:
    uv run scripts/fetch_missing_objects.py
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

# ── Config — adjust per project ────────────────────────────────────────────────

_PREFIX = os.getenv("PG_ENV_PREFIX", "POSTGRES_")

DB_ROOT = Path(__file__).parent.parent / "database"

_LAYER_PREFIX_RE = re.compile(r"^\d+_?")


def layer_folders() -> dict[str, Path]:
    """Map a schema name to its existing layer directory under database/.

    Discovered from the top-level folders in database/ (skipping migration
    dirs), stripping the leading display-order number (e.g. "1_reference_data"
    -> "reference_data") — that number is a sort aid, not part of the name.
    """
    folders: dict[str, Path] = {}
    if not DB_ROOT.is_dir():
        return folders
    for entry in DB_ROOT.iterdir():
        if not entry.is_dir() or entry.name in ("migrations", "_migration_scripts"):
            continue
        name = _LAYER_PREFIX_RE.sub("", entry.name).lower()
        folders[name] = entry
    return folders


def folder_for(schema: str, subfolder: str) -> Path:
    existing = layer_folders().get(schema.lower())
    base = existing if existing is not None else DB_ROOT / schema
    return base / subfolder


# ── Extract tables already tracked in database/ ───────────────────────────────


def extract_tables_sqlglot(sql: str) -> set[tuple[str, str]]:
    import sqlglot
    import sqlglot.expressions as exp

    tables: set[tuple[str, str]] = set()
    try:
        for stmt in sqlglot.parse(sql, dialect="postgres"):
            if isinstance(stmt, exp.Create) and stmt.kind == "TABLE":
                tbl = stmt.find(exp.Table)
                if tbl:
                    schema = tbl.db or "public"
                    tables.add((schema.lower(), tbl.name.lower()))
    except Exception:
        pass
    return tables


def extract_tables_regex(sql: str) -> set[tuple[str, str]]:
    pattern = re.compile(
        r"CREATE\s+(?:OR\s+REPLACE\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
        r"(?:([a-zA-Z_]\w*)\.)?([a-zA-Z_]\w*)",
        re.IGNORECASE,
    )
    return {(m.group(1).lower() if m.group(1) else "public", m.group(2).lower()) for m in pattern.finditer(sql)}


def extract_tables(sql: str) -> set[tuple[str, str]]:
    result = extract_tables_sqlglot(sql)
    if not result:
        result = extract_tables_regex(sql)
    return result


def tracked_tables() -> set[tuple[str, str]]:
    tables: set[tuple[str, str]] = set()
    for sql_file in DB_ROOT.rglob("*.sql"):
        if "migrations" in sql_file.parts or "_migration_scripts" in sql_file.parts:
            continue
        try:
            sql = sql_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        tables |= extract_tables(sql)
    return tables


def tracked_names(keyword: str) -> set[tuple[str, str]]:
    """(schema, name) pairs already tracked for a `CREATE [OR REPLACE] <keyword> ...` object."""
    pattern = re.compile(
        rf"CREATE\s+(?:OR\s+REPLACE\s+)?{keyword}\s+(?:IF\s+NOT\s+EXISTS\s+)?"
        r"(?:([a-zA-Z_]\w*)\.)?([a-zA-Z_]\w*)",
        re.IGNORECASE,
    )
    names: set[tuple[str, str]] = set()
    for sql_file in DB_ROOT.rglob("*.sql"):
        if "migrations" in sql_file.parts or "_migration_scripts" in sql_file.parts:
            continue
        try:
            sql = sql_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        names |= {(m.group(1).lower() if m.group(1) else "public", m.group(2).lower()) for m in pattern.finditer(sql)}
    return names


# ── PostgreSQL helpers ─────────────────────────────────────────────────────────


def pg_connection():
    import psycopg

    p = _PREFIX
    return psycopg.connect(
        host=os.environ[p + "HOST"],
        port=os.environ[p + "PORT"],
        dbname=os.environ[p + "DB"],
        user=os.environ[p + "USER"],
        password=os.environ[p + "PASSWORD"],
    )


def all_pg_tables(conn) -> list[tuple[str, str]]:
    """Return (schema, table) for all user tables, sorted."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT n.nspname, c.relname
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'r'
              AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
              AND n.nspname NOT LIKE 'pg_temp_%'
            ORDER BY n.nspname, c.relname
        """)
        return [(row[0], row[1]) for row in cur.fetchall()]


def get_create_table_ddl(conn, schema: str, table: str) -> str:
    """Reconstruct CREATE TABLE DDL from pg_catalog."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.oid
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s AND c.relname = %s AND c.relkind = 'r'
        """,
            (schema, table),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Table {schema}.{table} not found in pg_catalog")
        oid = row[0]

        # Columns
        cur.execute(
            """
            SELECT
                a.attname,
                pg_catalog.format_type(a.atttypid, a.atttypmod),
                a.attnotnull,
                a.attidentity,
                a.attgenerated,
                CASE
                    WHEN a.attidentity = 'a' THEN 'GENERATED ALWAYS AS IDENTITY'
                    WHEN a.attidentity = 'd' THEN 'GENERATED BY DEFAULT AS IDENTITY'
                    WHEN a.attgenerated = 's' THEN
                        'GENERATED ALWAYS AS (' || pg_catalog.pg_get_expr(ad.adbin, ad.adrelid) || ') STORED'
                    WHEN ad.adbin IS NOT NULL THEN
                        'DEFAULT ' || pg_catalog.pg_get_expr(ad.adbin, ad.adrelid)
                    ELSE NULL
                END
            FROM pg_catalog.pg_attribute a
            LEFT JOIN pg_catalog.pg_attrdef ad
                ON ad.adrelid = a.attrelid AND ad.adnum = a.attnum
            WHERE a.attrelid = %s AND a.attnum > 0 AND NOT a.attisdropped
            ORDER BY a.attnum
        """,
            (oid,),
        )
        columns = cur.fetchall()

        # Table constraints
        cur.execute(
            """
            SELECT conname, pg_catalog.pg_get_constraintdef(oid, true)
            FROM pg_catalog.pg_constraint
            WHERE conrelid = %s
            ORDER BY contype, conname
        """,
            (oid,),
        )
        constraints = cur.fetchall()

        # Extra indexes (not backing a constraint)
        cur.execute(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = %s AND tablename = %s
              AND indexname NOT IN (
                  SELECT conname FROM pg_catalog.pg_constraint WHERE conrelid = %s
              )
            ORDER BY indexname
        """,
            (schema, table, oid),
        )
        indexes = cur.fetchall()

    # Build column definitions
    col_defs: list[str] = []
    for attname, data_type, not_null, identity, _, extra in columns:
        col_def = f"{attname} {data_type}"
        if not_null and not identity:
            col_def += " NOT NULL"
        if extra:
            col_def += f" {extra}"
        col_defs.append(col_def)

    for conname, condef in constraints:
        col_defs.append(f"CONSTRAINT {conname} {condef}")

    ddl = f"CREATE TABLE IF NOT EXISTS {schema}.{table} (\n"
    ddl += ",\n".join(f"    {c}" for c in col_defs)
    ddl += "\n);\n"

    for _, indexdef in indexes:
        indexdef = re.sub(r"^CREATE INDEX\b", "CREATE INDEX IF NOT EXISTS", indexdef)
        indexdef = re.sub(r"^CREATE UNIQUE INDEX\b", "CREATE UNIQUE INDEX IF NOT EXISTS", indexdef)
        ddl += f"\n{indexdef};\n"

    return ddl


def all_pg_functions(conn, table_returning: bool) -> list[tuple[str, str]]:
    """Return (schema, name) for scalar functions (table_returning=False) or
    table functions — those returning SETOF/TABLE (table_returning=True)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT n.nspname, p.proname
            FROM pg_catalog.pg_proc p
            JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
            WHERE p.prokind = 'f'
              AND p.proretset = %s
              AND n.nspname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY n.nspname, p.proname
        """,
            (table_returning,),
        )
        return [(row[0], row[1]) for row in cur.fetchall()]


def get_function_ddl(conn, schema: str, name: str) -> str:
    """Fetch a function's DDL via pg_get_functiondef.

    If the function is overloaded, this uses the lowest-oid (oldest) match —
    good enough to seed a file; resolve manually if there's more than one.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.oid
            FROM pg_catalog.pg_proc p
            JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = %s AND p.proname = %s AND p.prokind = 'f'
            ORDER BY p.oid
            LIMIT 1
        """,
            (schema, name),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Function {schema}.{name} not found in pg_catalog")

        cur.execute("SELECT pg_catalog.pg_get_functiondef(%s)", (row[0],))
        ddl_row = cur.fetchone()
        if not ddl_row or ddl_row[0] is None:
            raise ValueError(f"Could not reconstruct DDL for function {schema}.{name}")
        return ddl_row[0].rstrip() + ";\n"


# ── Object kinds — add more entries here for other object types ───────────────

OBJECT_KINDS = [
    {
        "label": "table",
        "subfolder": "tables",
        "tracked": tracked_tables,
        "pg_list": lambda conn: all_pg_tables(conn),
        "ddl": get_create_table_ddl,
    },
    {
        "label": "scalar function",
        "subfolder": "scalar_functions",
        "tracked": lambda: tracked_names("FUNCTION"),
        "pg_list": lambda conn: all_pg_functions(conn, table_returning=False),
        "ddl": get_function_ddl,
    },
    {
        "label": "table function",
        "subfolder": "table_functions",
        "tracked": lambda: tracked_names("FUNCTION"),
        "pg_list": lambda conn: all_pg_functions(conn, table_returning=True),
        "ddl": get_function_ddl,
    },
]


# ── sqlfmt formatting ─────────────────────────────────────────────────────────


def sqlfmt_file(path: Path) -> None:
    from sqlfmt.api import Mode, run

    run(files=[path], mode=Mode())


# ── Interactive selection ──────────────────────────────────────────────────────


def pick_objects(missing: list[dict]) -> list[dict]:
    """Let the user choose which objects to fetch via questionary checkboxes."""
    import questionary

    choices = [f"[{m['label']}] {m['schema']}.{m['name']}" for m in missing]
    if not choices:
        return []

    selected = questionary.checkbox(
        "Select objects to fetch (space to toggle, enter to confirm):",
        choices=choices,
    ).ask()

    if not selected:
        return []

    selected_set = set(selected)
    return [m for m, c in zip(missing, choices) if c in selected_set]


# ── Main ───────────────────────────────────────────────────────────────────────


def main() -> None:
    print("Connecting to PostgreSQL…")
    try:
        conn = pg_connection()
    except Exception as e:
        print(f"  Connection failed: {e}", file=sys.stderr)
        sys.exit(1)

    with conn:
        missing: list[dict] = []

        for kind in OBJECT_KINDS:
            print(f"Scanning database/ for tracked {kind['label']}s…")
            tracked = kind["tracked"]()
            pg_objects = kind["pg_list"](conn)
            print(f"  {len(tracked)} tracked, {len(pg_objects)} in the database.")

            for schema, name in pg_objects:
                if (schema.lower(), name.lower()) not in tracked:
                    missing.append({"kind": kind, "label": kind["label"], "schema": schema, "name": name})

        if not missing:
            print("\nNo missing objects — everything is already tracked.")
            return

        missing.sort(key=lambda m: (m["label"], m["schema"], m["name"]))

        print(f"\n{len(missing)} untracked objects:\n")
        for m in missing:
            dest = folder_for(m["schema"], m["kind"]["subfolder"]) / f"{m['name']}.sql"
            print(f"  [{m['label']}] {m['schema']}.{m['name']:40s}  →  {dest.relative_to(DB_ROOT.parent)}")

        print()
        selected = pick_objects(missing)

        if not selected:
            print("Nothing selected, exiting.")
            return

        print()
        written: list[Path] = []
        errors: list[str] = []

        for m in selected:
            schema, name, kind = m["schema"], m["name"], m["kind"]
            try:
                ddl = kind["ddl"](conn, schema, name)
            except Exception as e:
                errors.append(f"[{m['label']}] {schema}.{name}: {e}")
                continue

            dest_dir = folder_for(schema, kind["subfolder"])
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f"{name}.sql"

            if dest.exists():
                print(f"  SKIP  {dest.relative_to(DB_ROOT.parent)} (already exists)")
                continue

            dest.write_text(ddl, encoding="utf-8")
            sqlfmt_file(dest)
            written.append(dest)
            print(f"  WROTE {dest.relative_to(DB_ROOT.parent)}")

        if errors:
            print("\nErrors:")
            for e in errors:
                print(f"  {e}", file=sys.stderr)

        if written:
            print(f"\nDone — wrote {len(written)} file(s).")


if __name__ == "__main__":
    main()
