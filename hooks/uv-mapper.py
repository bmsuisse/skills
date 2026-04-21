#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""
PreToolUse hook: remaps common commands to preferred tooling.

  python -m <mod>       → uv run -m <mod>
  python / python3      → uv run python
  pip install           → uv add
  pip uninstall         → uv remove
  pip <other>           → uv pip <other>   (list, freeze, show, …)
  pytest                → uv run pytest
  ruff                  → uv run ruff
  pyright               → uv run pyright
  basedpyright          → uv run basedpyright
  ty                    → uv run ty
  npx <cmd>             → bunx <cmd>
  npx skills <args>     → bunx skills <args>
"""

import json
import re
import sys

# Tools that map directly to `uv run <tool> [args]`
_UV_RUN_TOOLS = ("pytest", "ruff", "pyright", "basedpyright", "ty")


def remap(cmd: str) -> str:
    if not cmd or cmd.startswith("uv ") or cmd == "uv":
        return cmd

    # python -m <mod> [args] → uv run -m <mod> [args]  (must come before the plain python rule)
    if m := re.match(r"^python3? -m (.+)$", cmd):
        return f"uv run -m {m.group(1)}"

    # python / python3 [args] → uv run python [args]
    if m := re.match(r"^python3?(\s.*)?$", cmd):
        return f"uv run python{m.group(1) or ''}"

    # pip / pip3 install [args] → uv add [args]
    if m := re.match(r"^pip3? install(\s.*)?$", cmd):
        return f"uv add{m.group(1) or ''}"

    # pip / pip3 uninstall [args] → uv remove [args]
    if m := re.match(r"^pip3? uninstall(\s.*)?$", cmd):
        return f"uv remove{m.group(1) or ''}"

    # pip / pip3 <other> → uv pip <other>
    if m := re.match(r"^pip3? (.+)$", cmd):
        return f"uv pip {m.group(1)}"

    # pytest / ruff / pyright / basedpyright / ty [args] → uv run <tool> [args]
    tools_pattern = "|".join(re.escape(t) for t in _UV_RUN_TOOLS)
    if m := re.match(rf"^({tools_pattern})(\s.*)?$", cmd):
        return f"uv run {m.group(1)}{m.group(2) or ''}"

    # npx / pnpx <cmd> → bun x <cmd>
    if m := re.match(r"^(?:npx|pnpx)(\s.*)?$", cmd):
        return f"bun x{m.group(1) or ''}"

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
