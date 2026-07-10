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
Fetches CREATE TABLE DDL from PostgreSQL for tables that exist in the
database but aren't yet tracked as .sql files under database/, then
writes them to the right schema folder.

Adjust _PREFIX and SCHEMA_FOLDER below to match the project.

Usage:
    uv run scripts/fetch_missing_tables.py
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

# Maps a Postgres schema name to the folder it's tracked under.
# The layer-number prefix on folders (0_, 1_, 2_...) is purely for human
# sorting/grouping in file listings — it plays no role here or in apply
# order, so map to whatever folder the layer actually lives in.
SCHEMA_FOLDER: dict[str, Path] = {
    "public": DB_ROOT / "public",
    "dim": DB_ROOT / "dim" / "tables",
    "fact": DB_ROOT / "fact" / "tables",
    "app": DB_ROOT / "app" / "tables",
}


def folder_for(schema: str) -> Path:
    if schema in SCHEMA_FOLDER:
        return SCHEMA_FOLDER[schema]
    # Unknown schema: create a sensible default
    return DB_ROOT / schema / "tables"


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


# ── sqlfmt formatting ─────────────────────────────────────────────────────────


def sqlfmt_file(path: Path) -> None:
    from sqlfmt.api import Mode, run

    run(files=[path], mode=Mode())


# ── Interactive selection ──────────────────────────────────────────────────────


def pick_tables(missing: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Let the user choose which tables to fetch via questionary checkboxes."""
    import questionary

    choices = [f"{schema}.{table}" for schema, table in missing]
    if not choices:
        return []

    selected = questionary.checkbox(
        "Select tables to fetch (space to toggle, enter to confirm):",
        choices=choices,
    ).ask()

    if not selected:
        return []

    selected_set = set(selected)
    return [(s, t) for s, t in missing if f"{s}.{t}" in selected_set]


# ── Main ───────────────────────────────────────────────────────────────────────


def main() -> None:
    print("Scanning database/ for tracked tables…")
    tracked = tracked_tables()
    print(f"  Found {len(tracked)} tables already tracked.\n")

    print("Connecting to PostgreSQL…")
    try:
        conn = pg_connection()
    except Exception as e:
        print(f"  Connection failed: {e}", file=sys.stderr)
        sys.exit(1)

    with conn:
        pg_tables = all_pg_tables(conn)
        print(f"  Found {len(pg_tables)} tables in the database.\n")

        missing = sorted((s, t) for s, t in pg_tables if (s.lower(), t.lower()) not in tracked)

        if not missing:
            print("No missing tables — everything is already tracked.")
            return

        print(f"{len(missing)} untracked tables:\n")
        for schema, table in missing:
            dest = folder_for(schema) / f"{table}.sql"
            print(f"  {schema}.{table:40s}  →  {dest.relative_to(DB_ROOT.parent)}")

        print()
        selected = pick_tables(missing)

        if not selected:
            print("Nothing selected, exiting.")
            return

        print()
        written: list[Path] = []
        errors: list[str] = []

        for schema, table in selected:
            try:
                ddl = get_create_table_ddl(conn, schema, table)
            except Exception as e:
                errors.append(f"{schema}.{table}: {e}")
                continue

            dest_dir = folder_for(schema)
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f"{table}.sql"

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
