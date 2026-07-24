#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = ["PyYAML"]
# ///
"""Resolve an issue's title (STEP.TOPIC_ITEM) to the repo file it describes.

Mirrors the resolution issues.py's `auto-assign` uses internally, exposed here
as its own script because issues.py doesn't offer this as a standalone CLI
command — `diagnose` needs it too. Folder layout does not reliably mirror
step/topic names, so this matches `job.step`/`job.topic`/`job.item` fields
inside `_config.*.yml` files rather than guessing a path.

Usage: resolve_job_file.py <repo_root> <title>
Prints the resolved file path (a sibling `{item}.sql` if one exists,
otherwise the `_config.*.yml` itself) or exits non-zero if no match is found.
"""
import sys
from pathlib import Path

import yaml

_SKIP_DIRS = {".venv", "node_modules", ".git", "__queuestorage__"}


def parse_title(title: str) -> tuple[str, str] | None:
    if "." not in title:
        return None
    step, topic_item = title.split(".", 1)
    return step, topic_item


def find_job_config(title: str, repo_root: Path):
    parsed = parse_title(title)
    if not parsed:
        return None
    step, topic_item = parsed

    for cfg_path in repo_root.rglob("_config.*.yml"):
        if _SKIP_DIRS & set(cfg_path.parts):
            continue
        try:
            entries = yaml.safe_load(cfg_path.read_text()) or []
        except yaml.YAMLError:
            continue
        for entry in entries:
            job = entry.get("job", {}) if isinstance(entry, dict) else {}
            if job.get("step") == step and f"{job.get('topic')}_{job.get('item')}" == topic_item:
                return cfg_path, job
    return None


def resolve_job_file(title: str, repo_root: Path) -> Path | None:
    found = find_job_config(title, repo_root)
    if not found:
        return None
    cfg_path, job = found
    sql_path = cfg_path.parent / f"{job['item']}.sql"
    return sql_path if sql_path.exists() else cfg_path


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: resolve_job_file.py <repo_root> <title>", file=sys.stderr)
        sys.exit(2)
    repo_root = Path(sys.argv[1]).resolve()
    title = sys.argv[2]
    resolved = resolve_job_file(title, repo_root)
    if resolved is None:
        print(f"no matching job config found for title '{title}'", file=sys.stderr)
        sys.exit(1)
    print(resolved)


if __name__ == "__main__":
    main()
