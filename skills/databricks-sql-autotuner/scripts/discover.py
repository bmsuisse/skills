#!/usr/bin/env python3
"""Discover Databricks profiles, clusters, DBR version, and default catalog/schema.

Replaces the Phase 1 bash one-liners in the SQL autotuner workflow. Requires only
the Databricks CLI — no venv or databricks-connect needed.

Usage:
    python3 scripts/discover.py                            # list everything, auto-select where possible
    python3 scripts/discover.py --profile my-profile       # skip profile selection
    python3 scripts/discover.py --profile p --cluster-id 0123-456789-abc  # full detail only
    python3 scripts/discover.py --profile p --cluster-name my-cluster
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

def _run(*args: str) -> dict | list | None:
    """Run a databricks CLI command and return parsed JSON, or None on failure."""
    result = subprocess.run(
        ["databricks", *args, "--output", "json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def _require(*args: str) -> dict | list:
    data = _run(*args)
    if data is None:
        print(f"[error] 'databricks {' '.join(args)}' failed. Is the CLI authenticated?", file=sys.stderr)
        sys.exit(1)
    return data


# ---------------------------------------------------------------------------
# Discovery steps
# ---------------------------------------------------------------------------

def list_profiles() -> list[dict]:
    data = _require("auth", "profiles")
    profiles = data if isinstance(data, list) else data.get("profiles", [])
    return [{"name": p.get("name"), "host": p.get("host", "")} for p in profiles]


def list_clusters(profile: str) -> list[dict]:
    data = _require("clusters", "list", "--profile", profile)
    clusters = data if isinstance(data, list) else data.get("clusters", [])
    return [
        {
            "cluster_id": c.get("cluster_id"),
            "cluster_name": c.get("cluster_name"),
            "state": c.get("state"),
            "spark_version": c.get("spark_version", ""),
            "dbr_version": (c.get("spark_version") or "").split("-")[0],
        }
        for c in clusters
    ]


def get_cluster_detail(profile: str, cluster_id: str) -> dict | None:
    return _run("clusters", "get", cluster_id, "--profile", profile)


def extract_catalog_schema(detail: dict) -> tuple[str, str]:
    cfg = detail.get("spark_conf") or {}
    catalog = cfg.get("spark.databricks.sql.initial.catalog.name", "hive_metastore")
    schema = cfg.get("spark.databricks.sql.initial.catalog.namespace", "default")
    return catalog, schema


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discover Databricks environment for the SQL autotuner.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--profile", help="CLI profile name (skip interactive selection)")
    parser.add_argument("--cluster-id", dest="cluster_id", help="Cluster ID (skip listing)")
    parser.add_argument("--cluster-name", dest="cluster_name", help="Resolve cluster by name")
    args = parser.parse_args()

    # --- Profiles ---
    profiles = list_profiles()

    selected_profile = args.profile
    if not selected_profile:
        if len(profiles) == 1:
            selected_profile = profiles[0]["name"]
            print(f"[profile] Auto-selected (only one): {selected_profile}", file=sys.stderr)
        else:
            print("\nAvailable profiles:", file=sys.stderr)
            for p in profiles:
                print(f"  • {p['name']}  ({p['host']})", file=sys.stderr)
            print(
                "\n[action] Multiple profiles found. Re-run with --profile <name> to continue.",
                file=sys.stderr,
            )
            print(json.dumps({"status": "needs_profile", "profiles": profiles}, indent=2))
            return

    # --- Clusters ---
    all_clusters = list_clusters(selected_profile)
    usable = [c for c in all_clusters if c["state"] in ("RUNNING", "TERMINATED")]
    running = [c for c in usable if c["state"] == "RUNNING"]

    selected_cluster_id = args.cluster_id

    if not selected_cluster_id and args.cluster_name:
        match = next((c for c in usable if c["cluster_name"] == args.cluster_name), None)
        if not match:
            print(f"[error] No cluster named '{args.cluster_name}'", file=sys.stderr)
            sys.exit(1)
        selected_cluster_id = match["cluster_id"]
        print(f"[cluster] Resolved '{args.cluster_name}' → {selected_cluster_id}", file=sys.stderr)

    if not selected_cluster_id:
        if len(running) == 1:
            selected_cluster_id = running[0]["cluster_id"]
            print(
                f"[cluster] Auto-selected running cluster: "
                f"{running[0]['cluster_name']} ({selected_cluster_id})",
                file=sys.stderr,
            )
        else:
            # Present options and let Claude/user decide
            print("\nAvailable clusters:", file=sys.stderr)
            for c in usable:
                marker = "▶ RUNNING" if c["state"] == "RUNNING" else "○ TERMINATED"
                print(
                    f"  {marker}  {c['cluster_name']}  ({c['cluster_id']})  DBR {c['dbr_version']}",
                    file=sys.stderr,
                )
            print(
                "\n[action] Multiple clusters found. Re-run with --cluster-id <id> to continue.",
                file=sys.stderr,
            )
            print(
                json.dumps(
                    {
                        "status": "needs_cluster",
                        "profile": selected_profile,
                        "clusters": usable,
                    },
                    indent=2,
                )
            )
            return

    # --- Full detail ---
    print(f"[detail] Fetching cluster details for {selected_cluster_id}...", file=sys.stderr)
    detail = get_cluster_detail(selected_profile, selected_cluster_id)
    if not detail:
        print(f"[error] Could not fetch details for cluster {selected_cluster_id}", file=sys.stderr)
        sys.exit(1)

    cluster_name = detail.get("cluster_name", selected_cluster_id)
    state = detail.get("state", "UNKNOWN")
    spark_version = detail.get("spark_version", "")
    dbr_version = spark_version.split("-")[0] if spark_version else "unknown"
    catalog, schema = extract_catalog_schema(detail)

    if state == "TERMINATED":
        print(
            f"\n[warn] Cluster '{cluster_name}' is TERMINATED. "
            "Start it before running env_setup.py:",
            file=sys.stderr,
        )
        print(
            f"  databricks clusters start {selected_cluster_id} --profile {selected_profile}",
            file=sys.stderr,
        )

    # --- Human-readable summary ---
    print("\n" + "=" * 56, file=sys.stderr)
    print("  Databricks SQL Autotuner — Environment Summary", file=sys.stderr)
    print("=" * 56, file=sys.stderr)
    print(f"  Profile      : {selected_profile}", file=sys.stderr)
    print(f"  Cluster ID   : {selected_cluster_id}", file=sys.stderr)
    print(f"  Cluster name : {cluster_name}", file=sys.stderr)
    print(f"  State        : {state}", file=sys.stderr)
    print(f"  DBR version  : {dbr_version}", file=sys.stderr)
    print(f"  Catalog      : {catalog}", file=sys.stderr)
    print(f"  Schema       : {schema}", file=sys.stderr)
    print("=" * 56, file=sys.stderr)
    print(file=sys.stderr)
    print("Next — run env_setup.py:", file=sys.stderr)
    print(
        f"  python3 scripts/env_setup.py \\\n"
        f"    --dbr-version {dbr_version} \\\n"
        f"    --profile {selected_profile} \\\n"
        f"    --cluster-id {selected_cluster_id}",
        file=sys.stderr,
    )

    # Machine-readable JSON on stdout for Claude
    print(
        json.dumps(
            {
                "status": "ok",
                "profile": selected_profile,
                "cluster_id": selected_cluster_id,
                "cluster_name": cluster_name,
                "state": state,
                "dbr_version": dbr_version,
                "catalog": catalog,
                "schema": schema,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
