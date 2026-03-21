"""
Databricks execution context helpers — importable library.

Use cli.py as the entrypoint. This module exposes:
  create_context, execute, poll, destroy_context,
  detect_language, wrap_sql_as_json, format_markdown_table, print_result
"""

from __future__ import annotations

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


def wrap_sql_as_json(sql: str) -> str:
    """Wrap a SQL query in Python that returns columns + rows as JSON."""
    escaped = sql.replace("\\", "\\\\").replace('"', '\\"')
    return (
        "import json as _json\n"
        f'_df = spark.sql("{escaped}")\n'
        "_cols = _df.columns\n"
        "_rows = [[str(v) if v is not None else '' for v in row] for row in _df.collect()]\n"
        'print("__MD_TABLE_JSON__" + _json.dumps({"columns": _cols, "rows": _rows}))\n'
    )


def format_markdown_table(columns: list[str], rows: list[list[str]]) -> str:
    widths = [len(c) for c in columns]
    for row in rows:
        for i, val in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(val))
    header = "| " + " | ".join(c.ljust(w) for c, w in zip(columns, widths)) + " |"
    separator = "|" + "|".join("-" * (w + 2) for w in widths) + "|"
    lines = [header, separator]
    for row in rows:
        line = "| " + " | ".join(
            (row[i] if i < len(row) else "").ljust(w)
            for i, w in enumerate(widths)
        ) + " |"
        lines.append(line)
    return "\n".join(lines)



def print_result(resp: dict, output_format: str = "text") -> int:
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
    if data and output_format == "markdown" and "__MD_TABLE_JSON__" in data:
        marker = "__MD_TABLE_JSON__"
        idx = data.index(marker)
        prefix = data[:idx].strip()
        if prefix:
            print(prefix)
        payload = json.loads(data[idx + len(marker) :])
        print(format_markdown_table(payload["columns"], payload["rows"]))
    elif data:
        print(data)
    else:
        print("[no output]")

    return 0
