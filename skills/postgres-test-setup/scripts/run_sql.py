"""
Execute a SQL file or inline SQL against the local test database.

The env-var prefix (e.g. TEST_ or MDM_) is auto-detected from [tool.pytest_env]
in pyproject.toml by looking for a key ending in POSTGRES_HOST. Falls back to TEST_.

Safety: refuses to run if <PREFIX>POSTGRES_HOST != "localhost".

Usage:
  # run a file
  uv run test_server/run_sql.py database/1_dim/tables/user.sql

  # run inline SQL
  uv run test_server/run_sql.py --sql "SELECT * FROM dim.user LIMIT 5"

  # run a file and print results as a table
  uv run test_server/run_sql.py --sql "SELECT * FROM dim.user" --results
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


def _detect_env_prefix() -> str:
    """Detect env-var prefix from [tool.pytest_env] in pyproject.toml.

    Searches upward from cwd for the first pyproject.toml, then looks for a key
    ending in POSTGRES_HOST inside [tool.pytest_env]. Falls back to 'TEST_'.
    """
    try:
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore[no-redef]
        for directory in [Path.cwd(), *Path.cwd().parents]:
            candidate = directory / "pyproject.toml"
            if candidate.exists():
                data = tomllib.loads(candidate.read_text(encoding="utf-8"))
                for key in data.get("tool", {}).get("pytest_env", {}):
                    if key.endswith("POSTGRES_HOST"):
                        return key[: -len("POSTGRES_HOST")]
                break  # found pyproject.toml but no matching key — stop searching
    except Exception:
        pass
    return "TEST_"


ENV_PREFIX = _detect_env_prefix()

# Default env — same as postgres_test_env in start_postgres.py
_defaults = {
    f"{ENV_PREFIX}POSTGRES_HOST":     "localhost",
    f"{ENV_PREFIX}POSTGRES_PORT":     "54324",
    f"{ENV_PREFIX}POSTGRES_DB":       "app_test",
    f"{ENV_PREFIX}POSTGRES_USER":     "postgres",
    f"{ENV_PREFIX}POSTGRES_PASSWORD": "testpwd",
}


def _conn_str() -> str:
    def g(key):
        return os.environ.get(key, _defaults[key])

    host = g(f"{ENV_PREFIX}POSTGRES_HOST")
    assert host == "localhost", (
        f"Safety check: {ENV_PREFIX}POSTGRES_HOST must be 'localhost', got '{host}'. "
        "This script only runs against the local test database."
    )
    port = g(f"{ENV_PREFIX}POSTGRES_PORT")
    db   = g(f"{ENV_PREFIX}POSTGRES_DB")
    user = g(f"{ENV_PREFIX}POSTGRES_USER")
    pwd  = g(f"{ENV_PREFIX}POSTGRES_PASSWORD")
    return f"postgresql://{user}:{pwd}@{host}:{port}/{db}?connect_timeout=10"


def _print_results(rows: list[dict]) -> None:
    if not rows:
        print("(no rows)")
        return
    cols = list(rows[0].keys())
    widths = {c: max(len(str(c)), max(len(str(r.get(c, ""))) for r in rows)) for c in cols}
    sep = "+-" + "-+-".join("-" * widths[c] for c in cols) + "-+"
    header = "| " + " | ".join(str(c).ljust(widths[c]) for c in cols) + " |"
    print(sep)
    print(header)
    print(sep)
    for row in rows:
        print("| " + " | ".join(str(row.get(c, "")).ljust(widths[c]) for c in cols) + " |")
    print(sep)
    print(f"({len(rows)} row{'s' if len(rows) != 1 else ''})")


async def run(sql: str, show_results: bool) -> None:
    conn_str = _conn_str()
    async with await psycopg.AsyncConnection.connect(conninfo=conn_str, autocommit=True) as con:
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        for i, stmt in enumerate(statements):
            is_last = i == len(statements) - 1
            async with con.cursor(row_factory=dict_row) as cur:
                await cur.execute(stmt)
                if show_results and is_last and cur.description:
                    rows = await cur.fetchall()
                    _print_results(rows)
                elif cur.description and cur.rowcount == -1:
                    rows = await cur.fetchall()
                    _print_results(rows)
                else:
                    affected = cur.rowcount
                    if affected >= 0:
                        print(f"OK — {affected} row(s) affected")
                    else:
                        print("OK")


def main():
    parser = argparse.ArgumentParser(description="Run SQL against the local test Postgres database")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("file", nargs="?", help="Path to a .sql file")
    group.add_argument("--sql", help="Inline SQL string")
    parser.add_argument("--results", action="store_true", help="Print query results as a table")
    args = parser.parse_args()

    if args.file:
        path = Path(args.file)
        if not path.exists():
            print(f"Error: file not found: {path}", file=sys.stderr)
            sys.exit(1)
        sql = path.read_text(encoding="utf-8")
    else:
        sql = args.sql

    asyncio.run(run(sql, show_results=args.results))


if __name__ == "__main__":
    main()
