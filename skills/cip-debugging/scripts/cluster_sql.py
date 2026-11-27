"""Run one SQL statement on the general-purpose cluster and print the result rows.

Why: the SQL warehouse (and OneHub) cannot read `distribution.*` tables or the CIP log paths on
`bmsstaprdeuwdatastoresnd` (storage firewall), and local Spark Connect breaks when pyspark is also
installed. The cluster command API has neither problem.

Usage:
    python3 <skill-dir>/scripts/cluster_sql.py "select 1"
    python3 <skill-dir>/scripts/cluster_sql.py --file query.sql
    python3 <skill-dir>/scripts/cluster_sql.py --profile premium --file query.sql

Needs the `databricks` CLI and an `az login` session (auth falls back to azure-cli).
"""

import argparse
import json
import os
import subprocess
import sys
import time

CLUSTER_ID = "0422-142111-ov7kv4xy"


def databricks_api(profile: str, method: str, path: str, body: dict | None = None) -> dict:
    cmd = ["databricks", "api", method, path, "-p", profile]
    if body is not None:
        cmd += ["--json", json.dumps(body)]
    env = {**os.environ}
    env.setdefault("DATABRICKS_AUTH_TYPE", "azure-cli")
    out = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if out.returncode != 0:
        sys.exit(f"databricks api {method} {path} failed:\n{out.stderr or out.stdout}")
    return json.loads(out.stdout)


def default_profile() -> str:
    if os.environ.get("DATABRICKS_PROFILE"):
        return os.environ["DATABRICKS_PROFILE"]
    cfg = os.path.expanduser("~/.databrickscfg")
    text = open(cfg).read() if os.path.exists(cfg) else ""
    for name in ("premium", "bms"):
        if f"[{name}]" in text:
            return name
    return "premium"


def run(sql: str, profile: str, cluster_id: str, max_rows: int) -> None:
    ctx = databricks_api(profile, "post", "/api/1.2/contexts/create", {"clusterId": cluster_id, "language": "sql"})["id"]
    try:
        cmd = databricks_api(
            profile,
            "post",
            "/api/1.2/commands/execute",
            {"clusterId": cluster_id, "contextId": ctx, "language": "sql", "command": sql},
        )["id"]
        while True:
            status = databricks_api(
                profile, "get", f"/api/1.2/commands/status?clusterId={cluster_id}&contextId={ctx}&commandId={cmd}"
            )
            if status["status"] in ("Finished", "Error", "Cancelled"):
                break
            time.sleep(3)
    finally:
        databricks_api(profile, "post", "/api/1.2/contexts/destroy", {"clusterId": cluster_id, "contextId": ctx})

    results = status.get("results") or {}
    if results.get("resultType") != "table":
        summary = results.get("summary") or results.get("data") or results
        sys.exit(f"Query failed: {str(summary)[:2000]}")
    print("\t".join(c["name"] for c in results["schema"]))
    for row in results["data"][:max_rows]:
        print("\t".join("" if v is None else str(v) for v in row))
    if len(results["data"]) > max_rows:
        print(f"... {len(results['data']) - max_rows} more rows")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sql", nargs="?", help="SQL statement (or use --file)")
    parser.add_argument("--file", help="read the SQL from this file")
    parser.add_argument("--profile", default=default_profile(), help="~/.databrickscfg profile of the premium workspace")
    parser.add_argument("--cluster-id", default=CLUSTER_ID)
    parser.add_argument("--max-rows", type=int, default=200)
    args = parser.parse_args()
    sql = open(args.file).read() if args.file else args.sql
    if not sql:
        parser.error("give a SQL statement or --file")
    run(sql, args.profile, args.cluster_id, args.max_rows)


if __name__ == "__main__":
    main()
