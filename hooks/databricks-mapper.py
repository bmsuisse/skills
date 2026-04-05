#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""
PreToolUse hook: rewrites common Databricks CLI mistakes to correct forms.

Wrong flags / non-existent subcommands the CLI rejects:

  databricks schemas list --catalog-name X       → databricks schemas list X
  databricks schemas list --catalog X            → databricks schemas list X
  databricks tables list --catalog X --schema Y  → databricks tables list X Y
  databricks tables list --catalog-name X ...    → databricks tables list X Y
  databricks sql-warehouses list                 → databricks warehouses list
  databricks sql execute ...                     → databricks experimental aitools tools query ...
  databricks sql-execute ...                     → databricks experimental aitools tools query ...
  databricks execute-statement ...               → databricks experimental aitools tools query ...
"""

import json
import re
import sys


def _extract_flag(cmd: str, *flags: str) -> tuple[str | None, str]:
    """Pull the first matching flag value out of cmd, return (value, remaining_cmd)."""
    for flag in flags:
        pattern = rf"(?:^|\s){re.escape(flag)}\s+(\S+)"
        m = re.search(pattern, cmd)
        if m:
            val = m.group(1)
            # Remove the flag+value pair from the command
            cmd = re.sub(rf"\s*{re.escape(flag)}\s+{re.escape(val)}", "", cmd).strip()
            return val, cmd
    return None, cmd


def remap(cmd: str) -> str:  # noqa: C901
    if not cmd or not re.match(r"^databricks\b", cmd):
        return cmd

    # ── schemas list ──────────────────────────────────────────────────────────
    # databricks schemas list --catalog-name X  →  databricks schemas list X
    # databricks schemas list --catalog X       →  databricks schemas list X
    if re.match(r"^databricks\s+schemas\s+list\b", cmd):
        if "--catalog" in cmd:
            catalog, cmd = _extract_flag(cmd, "--catalog-name", "--catalog")
            if catalog:
                # strip any leftover positional that was already there
                base = re.sub(r"^(databricks\s+schemas\s+list)\b.*", r"\1", cmd)
                rest = cmd[len(base):].strip()
                # avoid doubling if catalog already appears positionally
                if catalog not in rest.split():
                    return f"{base} {catalog} {rest}".strip()
        return cmd

    # ── tables list ───────────────────────────────────────────────────────────
    # databricks tables list --catalog X --schema Y  →  databricks tables list X Y
    if re.match(r"^databricks\s+tables\s+list\b", cmd):
        if "--catalog" in cmd or "--schema" in cmd:
            catalog, cmd = _extract_flag(cmd, "--catalog-name", "--catalog")
            schema, cmd = _extract_flag(cmd, "--schema-name", "--schema")
            base = re.sub(r"^(databricks\s+tables\s+list)\b.*", r"\1", cmd)
            rest = cmd[len(base):].strip()
            parts = " ".join(filter(None, [catalog, schema, rest]))
            return f"{base} {parts}".strip()
        return cmd

    # ── sql-warehouses list → warehouses list ─────────────────────────────────
    if m := re.match(r"^(databricks)\s+sql-warehouses(\s+.+)?$", cmd):
        return f"{m.group(1)} warehouses{m.group(2) or ''}"

    # ── sql execute / sql-execute / execute-statement → aitools query ─────────
    # Extract quoted or unquoted SQL argument if present
    sql_match = None
    if m := re.match(
        r"^databricks\s+(?:sql\s+execute|sql-execute|execute-statement)\s+(.+)$", cmd
    ):
        sql_match = m.group(1).strip()
    elif re.match(r"^databricks\s+(?:sql\s+execute|sql-execute|execute-statement)$", cmd):
        sql_match = ""

    if sql_match is not None:
        # Pull --profile flag through unchanged
        profile_val, remainder = _extract_flag(sql_match, "--profile", "-p")
        profile_flag = f" --profile {profile_val}" if profile_val else ""
        # Whatever remains is treated as the SQL query string
        sql = remainder.strip().strip("\"'")
        if sql:
            return f'databricks experimental aitools tools query "{sql}"{profile_flag}'
        return f"databricks experimental aitools tools query{profile_flag}"

    return cmd


def main() -> None:
    data = json.load(sys.stdin)
    cmd = data.get("tool_input", {}).get("command", "")

    new_cmd = remap(cmd)

    if new_cmd != cmd:
        data["tool_input"]["command"] = new_cmd
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "updatedInput": data["tool_input"],
            }
        }))


if __name__ == "__main__":
    main()
