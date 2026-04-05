#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""
PreToolUse hook: remaps common Node package manager commands to bun equivalents.

  npm install / npm i          → bun install
  npm install <pkg>            → bun add <pkg>
  npm install -D <pkg>         → bun add -d <pkg>
  npm uninstall <pkg>          → bun remove <pkg>
  npm run <script>             → bun run <script>
  npm test / npm t             → bun test
  npm exec / npx               → bunx
  npm publish                  → bun publish
  npm <other>                  → bun <other>

  pnpm install                 → bun install
  pnpm add <pkg>               → bun add <pkg>
  pnpm add -D <pkg>            → bun add -d <pkg>
  pnpm remove <pkg>            → bun remove <pkg>
  pnpm run <script>            → bun run <script>
  pnpm test                    → bun test
  pnpm exec / pnpx             → bunx
  pnpm <other>                 → bun <other>

  yarn install                 → bun install
  yarn add <pkg>               → bun add <pkg>
  yarn add -D <pkg>            → bun add -d <pkg>
  yarn remove <pkg>            → bun remove <pkg>
  yarn run <script>            → bun run <script>
  yarn test                    → bun test
  yarn <other>                 → bun <other>
"""

import json
import re
import sys


def _remap_install_flags(args: str) -> str:
    """Convert -D / --save-dev to bun's -d flag."""
    return re.sub(r"(?:^|\s)(--save-dev|-D)(?=\s|$)", " -d", args).strip()


def remap(cmd: str) -> str:  # noqa: C901
    if not cmd or cmd.startswith("bun ") or cmd == "bun":
        return cmd

    # ── npx / pnpx ────────────────────────────────────────────────────────────
    if m := re.match(r"^(?:npx|pnpx)([\s].+)?$", cmd):
        return f"bunx{m.group(1) or ''}"

    # ── npm ───────────────────────────────────────────────────────────────────
    if m := re.match(r"^npm\s+(.*)?$", cmd):
        rest = (m.group(1) or "").strip()

        # npm install (bare) / npm i (bare)
        if re.match(r"^(?:install|i)$", rest):
            return "bun install"

        # npm install <pkg(s)> [flags]
        if m2 := re.match(r"^(?:install|i)\s+(.+)$", rest):
            args = _remap_install_flags(m2.group(1))
            return f"bun add {args}"

        # npm uninstall
        if m2 := re.match(r"^(?:uninstall|un|remove|rm|r)\s+(.+)$", rest):
            return f"bun remove {m2.group(1)}"

        # npm run <script>
        if m2 := re.match(r"^run\s+(.+)$", rest):
            return f"bun run {m2.group(1)}"

        # npm test / npm t
        if re.match(r"^(?:test|t)$", rest):
            return "bun test"

        # npm exec
        if m2 := re.match(r"^exec\s+(.+)$", rest):
            return f"bunx {m2.group(1)}"

        # npm publish / npm <other>
        return f"bun {rest}" if rest else "bun"

    # ── pnpm ──────────────────────────────────────────────────────────────────
    if m := re.match(r"^pnpm\s+(.*)?$", cmd):
        rest = (m.group(1) or "").strip()

        if re.match(r"^install$", rest):
            return "bun install"

        if m2 := re.match(r"^add\s+(.+)$", rest):
            args = _remap_install_flags(m2.group(1))
            return f"bun add {args}"

        if m2 := re.match(r"^(?:remove|rm|uninstall|un)\s+(.+)$", rest):
            return f"bun remove {m2.group(1)}"

        if m2 := re.match(r"^run\s+(.+)$", rest):
            return f"bun run {m2.group(1)}"

        if re.match(r"^test$", rest):
            return "bun test"

        if m2 := re.match(r"^exec\s+(.+)$", rest):
            return f"bunx {m2.group(1)}"

        return f"bun {rest}" if rest else "bun"

    # ── yarn ──────────────────────────────────────────────────────────────────
    if m := re.match(r"^yarn(?:\s+(.*)?)?$", cmd):
        rest = (m.group(1) or "").strip()

        if not rest or re.match(r"^install$", rest):
            return "bun install"

        if m2 := re.match(r"^add\s+(.+)$", rest):
            args = _remap_install_flags(m2.group(1))
            return f"bun add {args}"

        if m2 := re.match(r"^(?:remove|uninstall)\s+(.+)$", rest):
            return f"bun remove {m2.group(1)}"

        if m2 := re.match(r"^run\s+(.+)$", rest):
            return f"bun run {m2.group(1)}"

        if re.match(r"^test$", rest):
            return "bun test"

        return f"bun {rest}"

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
