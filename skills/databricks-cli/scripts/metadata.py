"""
Databricks Unity Catalog metadata helpers.

Functions
---------
catalogs(profile)               -> list of catalog names
schemas(profile, catalog)       -> list of schema names
tables(profile, catalog, schema)-> list of table dicts
describe(profile, fqn)          -> full table dict (columns, comment, owner, …)
search(profile, keyword, catalog) -> prints matching tables via information_schema
"""

from __future__ import annotations

import json
import subprocess
import sys


def _run(profile: str, *args: str) -> dict | list:
    cmd = ["databricks", *args, "--profile", profile, "--output", "json"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[error] {r.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return json.loads(r.stdout) if r.stdout.strip() else {}


def _unwrap(resp: dict | list, key: str) -> list:
    """Handle both {key: [...]} and bare [...] responses."""
    if isinstance(resp, dict):
        return resp.get(key, []) or []
    return resp or []


def catalogs(profile: str) -> list[str]:
    resp = _run(profile, "catalogs", "list")
    return [c["name"] for c in _unwrap(resp, "catalogs")]


def schemas(profile: str, catalog: str) -> list[str]:
    resp = _run(profile, "schemas", "list", catalog)
    return [s["name"] for s in _unwrap(resp, "schemas")]


def tables(profile: str, catalog: str, schema: str) -> list[dict]:
    resp = _run(profile, "tables", "list", catalog, schema)
    return _unwrap(resp, "tables")


def describe(profile: str, fqn: str) -> dict:
    resp = _run(profile, "tables", "get", fqn)
    return resp if isinstance(resp, dict) else {}


def search(profile: str, keyword: str, catalog: str | None = None) -> None:
    """Search information_schema for tables matching keyword.

    Streams output directly — does not return a value.
    Uses `databricks experimental aitools tools query` (no cluster needed).
    """
    safe_kw = keyword.replace("'", "''")  # basic SQL escaping
    where = f"table_name LIKE '%{safe_kw}%'"
    if catalog:
        safe_cat = catalog.replace("'", "''")
        where += f" AND table_catalog = '{safe_cat}'"

    sql = (
        f"SELECT table_catalog, table_schema, table_name, comment "
        f"FROM system.information_schema.tables "
        f"WHERE {where} "
        f"ORDER BY table_catalog, table_schema, table_name"
    )

    cmd = ["databricks", "experimental", "aitools", "tools", "query", sql, "--profile", profile]
    r = subprocess.run(cmd)
    if r.returncode != 0:
        sys.exit(r.returncode)
