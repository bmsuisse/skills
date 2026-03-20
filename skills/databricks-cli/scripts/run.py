"""
databricks-cli run helper
Execute Python or SQL on a Databricks cluster via the execution context API.

Usage
-----
# Inline code
uv run scripts/run.py --profile premium --cluster-id <ID> --lang python \
    --code "print(spark.version)"

# From a local file (language inferred from extension)
uv run scripts/run.py --profile premium --cluster-id <ID> --file script.py

# SQL
uv run scripts/run.py --profile premium --cluster-id <ID> --lang sql \
    --code "SELECT * FROM catalog.schema.table LIMIT 10"

Cluster IDs
-----------
  general-purpose      : look up with `databricks clusters list --profile <PROFILE>`
  machine-learning (gpu): 0303-075313-aono4t6a
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path




def _cli(profile: str, method: str, path: str, body: dict) -> dict:
    cmd = ["databricks", "api", method, path, "--profile", profile, "--json", json.dumps(body)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[error] CLI call failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)


def create_context(profile: str, cluster_id: str, language: str) -> str:
    resp = _cli(profile, "post", "/api/1.2/contexts/create", {"clusterId": cluster_id, "language": language})
    ctx_id: str = resp["id"]
    return ctx_id


def execute(profile: str, cluster_id: str, context_id: str, language: str, command: str) -> str:
    resp = _cli(
        profile,
        "post",
        "/api/1.2/commands/execute",
        {"clusterId": cluster_id, "contextId": context_id, "language": language, "command": command},
    )
    cmd_id: str = resp["id"]
    return cmd_id


def poll(profile: str, cluster_id: str, context_id: str, command_id: str, interval: float = 2.0) -> dict:
    while True:
        resp = _cli(
            profile,
            "get",
            "/api/1.2/commands/status",
            {"clusterId": cluster_id, "contextId": context_id, "commandId": command_id},
        )
        status = resp.get("status", "")
        if status == "Finished":
            return resp
        if status == "Error":
            print(f"[error] Command entered Error state:\n{resp}", file=sys.stderr)
            sys.exit(1)
        print(f"  … {status}", file=sys.stderr)
        time.sleep(interval)


def destroy_context(profile: str, cluster_id: str, context_id: str) -> None:
    _cli(profile, "post", "/api/1.2/contexts/destroy", {"clusterId": cluster_id, "contextId": context_id})


_EXT_TO_LANG = {".py": "python", ".sql": "sql", ".r": "r", ".scala": "scala"}


def detect_language(file: Path | None, explicit: str | None) -> str:
    if explicit:
        return explicit.lower()
    if file:
        return _EXT_TO_LANG.get(file.suffix.lower(), "python")
    return "python"



def print_result(resp: dict) -> int:
    results = resp.get("results", {})
    result_type = results.get("resultType", "")

    if result_type == "error":
        cause = results.get("cause", "")
        summary = results.get("summary", "")
        print("\n[FAILED]", file=sys.stderr)
        if cause:
            print(cause, file=sys.stderr)
        if summary:
            print("\nTraceback:", file=sys.stderr)
            print(summary, file=sys.stderr)
        return 1

    data = results.get("data", "")
    if data:
        print(data)
    else:
        schema = results.get("schema")
        rows = results.get("data")
        if schema and rows is not None:
            cols = [c["name"] for c in schema] if isinstance(schema, list) else []
            if cols:
                print("\t".join(cols))
                print("-" * (sum(len(c) for c in cols) + len(cols) * 3))
            for row in rows:
                print("\t".join(str(v) for v in row))
        else:
            print("[no output]")

    return 0



def main() -> None:
    parser = argparse.ArgumentParser(
        description="Execute Python or SQL on a Databricks cluster (execution context API).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--profile", required=True, help="Databricks CLI profile (e.g. premium)")
    parser.add_argument("--cluster-id", required=True, dest="cluster_id", help="Cluster ID to run on")
    parser.add_argument("--lang", dest="lang", help="Language: python | sql | r | scala (default: inferred from file)")

    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--code", help="Inline code string to execute")
    src.add_argument("--file", type=Path, help="Local script file to upload and execute")

    parser.add_argument("--args", help="JSON dict injected as ARGS variable before exec (Python only)", default=None)
    parser.add_argument("--no-destroy", action="store_true", help="Keep the execution context open after running")
    parser.add_argument("--poll-interval", type=float, default=2.0, metavar="SEC", help="Polling interval in seconds")

    args = parser.parse_args()

    if args.file:
        code = args.file.read_text(encoding="utf-8")
    else:
        code = args.code

    language = detect_language(args.file, args.lang)

    if args.args and language == "python":
        try:
            json.loads(args.args)  # validate JSON before injecting
        except json.JSONDecodeError as e:
            print(f"[error] --args must be valid JSON: {e}", file=sys.stderr)
            sys.exit(1)
        code = f"ARGS = {args.args}\n{code}"

    print(f"[run] profile={args.profile} cluster={args.cluster_id} lang={language}", file=sys.stderr)
    print("[run] opening execution context …", file=sys.stderr)
    ctx_id = create_context(args.profile, args.cluster_id, language)
    print(f"[run] context {ctx_id}", file=sys.stderr)

    try:
        print("[run] submitting command …", file=sys.stderr)
        cmd_id = execute(args.profile, args.cluster_id, ctx_id, language, code)
        resp = poll(args.profile, args.cluster_id, ctx_id, cmd_id, interval=args.poll_interval)
    finally:
        if not args.no_destroy:
            destroy_context(args.profile, args.cluster_id, ctx_id)

    exit_code = print_result(resp)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
