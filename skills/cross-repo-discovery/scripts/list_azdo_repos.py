#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""List Azure DevOps repos in an org alongside local clone status.

Requires: az cli with the devops extension, logged in (`az login`).

The org is resolved in this order:
    1. --org flag
    2. AZDO_ORG or BMS_ORG env var (or in a local .env file)
If neither is set, the script exits with an error.

Usage:
    uv run list_azdo_repos.py [--org myorg]
    python list_azdo_repos.py [--org myorg]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

DESC_LINE_RE = re.compile(r"^\s*([\w.\-– ]+)\s*:\s*(.+?)\s*$")
AZ_CMD = shutil.which("az")
if AZ_CMD is None:
    sys.exit("Could not find 'az' on PATH. Install the Azure CLI and/or run `az login`.")


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def work_dir() -> Path:
    env = os.environ.get("AZDO_WORK_DIR") or os.environ.get("BMS_WORK_DIR")
    if env:
        return Path(env).expanduser()
    if os.name == "nt":
        return Path("C:/Projects")
    return Path("~/projects").expanduser()


def resolve_org(cli_org: str | None) -> str:
    if cli_org:
        return cli_org
    env = os.environ.get("AZDO_ORG") or os.environ.get("BMS_ORG")
    if env:
        return env
    sys.exit("An Azure DevOps org is required: pass --org <org>, or set AZDO_ORG/BMS_ORG.")


def az(*args: str) -> str:
    result = subprocess.run(
        [AZ_CMD, *args, "-o", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"az {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def list_projects(org: str) -> list[dict]:
    out = az("devops", "project", "list", "--org", f"https://dev.azure.com/{org}")
    return json.loads(out)["value"]


def project_description(org: str, project_id: str) -> str:
    out = subprocess.run(
        [
            AZ_CMD,
            "devops",
            "invoke",
            "--org",
            f"https://dev.azure.com/{org}",
            "--area",
            "core",
            "--resource",
            "projects",
            "--route-parameters",
            f"projectId={project_id}",
            "-o",
            "json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        return ""
    data = json.loads(out.stdout)
    return data.get("description", "") or ""


def parse_repo_descriptions(description: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in description.splitlines():
        m = DESC_LINE_RE.match(line)
        if m:
            result[m.group(1)] = m.group(2)
    return result


REPOS_HEADER_RE = re.compile(r"^\s*repos\s*:\s*$", re.IGNORECASE)


def split_description(description: str) -> tuple[str, str]:
    """Split into (preserved text before the 'Repos:' header, text after it).

    If no 'Repos:' header line is found, the whole description is preserved
    and there's nothing to scan for repo entries.
    """
    lines = description.splitlines()
    for i, line in enumerate(lines):
        if REPOS_HEADER_RE.match(line):
            return "\n".join(lines[:i]).strip(), "\n".join(lines[i + 1 :])
    return description.strip(), ""


def parse_selection(raw: str, count: int, has_desc: list[bool] | None = None) -> set[int]:
    """Parse '1,3,5-7' / 'all' / 'none'/'' / 'with_desc' (optionally mixed, e.g. '5,with_desc')."""
    raw = raw.strip().lower()
    if raw in ("", "none", "n"):
        return set()
    if raw in ("all", "a"):
        return set(range(count))
    indices: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if has_desc is not None and part in ("with_desc", "with-desc", "withdesc"):
            indices.update(i for i, d in enumerate(has_desc) if d)
        elif "-" in part:
            start, end = part.split("-", 1)
            indices.update(range(int(start) - 1, int(end)))
        else:
            indices.add(int(part) - 1)
    return {i for i in indices if 0 <= i < count}


def select_items(items: list[str], prompt: str, has_desc: list[bool] | None = None) -> set[int]:
    labels = items
    if has_desc is not None:
        labels = [f"{item} (has desc)" if d else item for item, d in zip(items, has_desc)]
    for i, item in enumerate(labels, 1):
        print(f"  [{i}] {item}")
    extra = ", 'with_desc' for all with descriptions" if has_desc is not None else ""
    raw = input(f"{prompt} (numbers/ranges, 'all'{extra}, or empty for none): ")
    return parse_selection(raw, len(items), has_desc)


def list_repos(org: str, project_name: str) -> list[dict]:
    out = az(
        "repos",
        "list",
        "--org",
        f"https://dev.azure.com/{org}",
        "--project",
        project_name,
    )
    return json.loads(out)


SKIP_DIR_NAMES = {"node_modules", ".venv"}


def find_git_repos(base: Path) -> list[Path]:
    """Walk base looking for .git dirs, without descending into node_modules/.venv
    or below a directory that is already a repo root."""
    repos: list[Path] = []
    if not base.exists():
        return repos
    for root, dirs, files in os.walk(base):
        root_path = Path(root)
        if (root_path / ".git").exists():
            repos.append(root_path)
            dirs.clear()
            continue
        dirs[:] = [d for d in dirs if d not in SKIP_DIR_NAMES and not d.startswith(".")]
    return repos


def find_local_clones(base: Path) -> dict[str, list[Path]]:
    """Map normalized remote origin URL -> list of local paths."""
    clones: dict[str, list[Path]] = {}
    for repo_path in find_git_repos(base):
        result = subprocess.run(
            ["git", "-C", str(repo_path), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            continue
        url = normalize_url(result.stdout.strip())
        clones.setdefault(url, []).append(repo_path)
    return clones


def normalize_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if url.endswith(".git"):
        url = url[: -len(".git")]
    return url.lower()


FAILED_UPDATES_PATH = Path("failed_project_updates.json")


def load_failed_updates() -> dict[str, dict]:
    if not FAILED_UPDATES_PATH.is_file():
        return {}
    entries = json.loads(FAILED_UPDATES_PATH.read_text(encoding="utf-8"))
    return {e["project_id"]: e for e in entries}


def write_failed_updates(entries: dict[str, dict]) -> None:
    if not entries:
        if FAILED_UPDATES_PATH.is_file():
            FAILED_UPDATES_PATH.unlink()
        return
    FAILED_UPDATES_PATH.write_text(json.dumps(list(entries.values()), indent=2), encoding="utf-8")


def save_failed_update(org: str, project_id: str, project_name: str, new_description: str, error: str) -> None:
    entries = load_failed_updates()
    entries[project_id] = {
        "org": org,
        "project_id": project_id,
        "project_name": project_name,
        "description": new_description,
        "error": error,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    write_failed_updates(entries)
    print(f"  [update] saved failed update to {FAILED_UPDATES_PATH}", file=sys.stderr)


def remove_failed_update(project_id: str) -> None:
    entries = load_failed_updates()
    if project_id in entries:
        del entries[project_id]
        write_failed_updates(entries)


def update_project_description(org: str, project_id: str, project_name: str, new_description: str) -> bool:
    body = json.dumps({"description": new_description})
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(body)
        body_path = f.name
    try:
        result = subprocess.run(
            [
                AZ_CMD,
                "devops",
                "invoke",
                "--org",
                f"https://dev.azure.com/{org}",
                "--area",
                "core",
                "--resource",
                "projects",
                "--route-parameters",
                f"projectId={project_id}",
                "--http-method",
                "PATCH",
                "--in-file",
                body_path,
                "--api-version",
                "7.1",
                "-o",
                "json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        os.unlink(body_path)
    if result.returncode != 0:
        error = result.stderr.strip()
        print(f"  [update] failed: {error}", file=sys.stderr)
        save_failed_update(org, project_id, project_name, new_description, error)
        return False
    return True


def read_all_repos_md(path: Path) -> list[tuple[str, str, str, str, str]]:
    """Parse the '| Project | Repo | Remote URL | Local Clone(s) | Description |' table."""
    rows: list[tuple[str, str, str, str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) != 5 or cols[0] == "Project":
            continue
        rows.append(tuple(cols))
    return rows


def write_all_repos_md(path: Path, org: str, base: Path, rows: list[tuple[str, str, str, str, str]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        f.write("# Azure DevOps Repos\n\n")
        f.write(f"Org: {org}  \n")
        f.write(f"Local work dir: {base}\n\n")
        f.write("| Project | Repo | Remote URL | Local Clone(s) | Description |\n")
        f.write("|---|---|---|---|---|\n")
        for project_name, repo_name, remote_url, local_str, desc in rows:
            f.write(f"| {project_name} | {repo_name} | {remote_url} | {local_str} | {desc} |\n")


def sync_descriptions_from_md(org: str, md_path: Path) -> None:
    """Read ALL_REPOS.md, let the user set/edit each repo's description, push to DevOps."""
    if not md_path.is_file():
        sys.exit(f"{md_path} not found. Run without --sync-descriptions first to generate it.")
    rows = read_all_repos_md(md_path)
    if not rows:
        print(f"No repo rows found in {md_path}.")
        return

    by_project: dict[str, list[tuple[str, str]]] = {}
    for project, repo, _url, _local, desc in rows:
        by_project.setdefault(project, []).append((repo, desc))

    projects = {p["name"]: p["id"] for p in list_projects(org)}
    final_descs: dict[tuple[str, str], str] = {(p, r): d for p, r, _u, _l, d in rows}

    for project_name, repo_list in by_project.items():
        project_id = projects.get(project_name)
        if not project_id:
            print(f"  [skip] project '{project_name}' not found in org '{org}'")
            continue

        description_text = project_description(org, project_id)
        other_text, repo_section = split_description(description_text)
        repo_descriptions = parse_repo_descriptions(repo_section)

        print(f"\nProject: {project_name}")
        changed = False
        for repo_name, md_desc in repo_list:
            current = repo_descriptions.get(repo_name, "")
            default = md_desc if md_desc.strip() and md_desc != "-" else current
            new_val = input(f"  {repo_name} [{default or 'blank'}]: ").strip() or default
            if new_val and new_val != current:
                repo_descriptions[repo_name] = new_val
                changed = True
            if new_val:
                final_descs[(project_name, repo_name)] = new_val

        if changed:
            repo_lines = "\n".join(f"{name}: {d}" for name, d in repo_descriptions.items())
            repos_block = f"Repos:\n{repo_lines}"
            new_description = f"{other_text}\n\n{repos_block}" if other_text else repos_block
            if update_project_description(org, project_id, project_name, new_description):
                print(f"  Updated project description for {project_name}")

    new_rows = [
        (p, r, u, l, final_descs.get((p, r), d))
        for p, r, u, l, d in rows
    ]
    write_all_repos_md(md_path, org, work_dir(), new_rows)
    print(f"\nWrote {md_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org", default=None, help="Azure DevOps org name; prompted for if omitted")
    parser.add_argument("--all", action="store_true", help="skip interactive selection, include every project/repo")
    parser.add_argument(
        "--sync-descriptions",
        action="store_true",
        help="read ALL_REPOS.md, let you set/edit descriptions, and push them to DevOps (skips the listing flow)",
    )
    args = parser.parse_args()

    load_dotenv()

    base = work_dir()
    org = resolve_org(args.org)

    if args.sync_descriptions:
        sync_descriptions_from_md(org, base / "ALL_REPOS.md")
        return

    print(f"Local work dir: {base}")
    print(f"Azure DevOps org: {org}")

    print("Scanning local clones...")
    local_clones = find_local_clones(base)

    print("Fetching projects...")
    projects = list_projects(org)

    print(f"\nFound {len(projects)} project(s) in '{org}':")
    project_names = [p["name"] for p in projects]
    selected_project_idx = set(range(len(project_names))) if args.all else select_items(project_names, "Select relevant projects")
    selected_projects = [projects[i] for i in sorted(selected_project_idx)]

    if not selected_projects:
        print("No projects selected, nothing to do.")
        return

    rows: list[tuple[str, str, str, str, str]] = []  # project, repo, remote_url, local_paths, description
    pending_updates = load_failed_updates()

    for project in selected_projects:
        project_name = project["name"]
        project_id = project["id"]
        print(f"\nProject: {project_name}")

        pending = pending_updates.get(project_id)
        if pending:
            print(f"  Found saved update from a previous failed run, retrying instead of re-asking...")
            if update_project_description(org, project_id, project_name, pending["description"]):
                print(f"  Updated project description for {project_name}")
                remove_failed_update(project_id)
            description_text = pending["description"]
        else:
            description_text = project_description(org, project_id)
        other_text, repo_section = split_description(description_text)
        repo_descriptions = parse_repo_descriptions(repo_section)

        all_repos = [r for r in list_repos(org, project_name) if not r.get("isDisabled")]
        if not all_repos:
            print("  No active repos.")
            continue

        repo_names = [r["name"] for r in all_repos]
        repo_has_desc = [bool(repo_descriptions.get(name, "").strip()) for name in repo_names]
        selected_repo_idx = (
            set(range(len(repo_names)))
            if args.all
            else select_items(repo_names, f"  Select relevant repos in '{project_name}'", has_desc=repo_has_desc)
        )
        repos = [all_repos[i] for i in sorted(selected_repo_idx)]
        if not repos:
            print("  No repos selected, skipping project.")
            continue

        updated_description_lines: dict[str, str] = dict(repo_descriptions)
        description_changed = False

        for repo in repos:
            repo_name = repo["name"]
            remote_url = repo["remoteUrl"]
            norm_url = normalize_url(remote_url)
            local_paths = local_clones.get(norm_url, [])
            local_str = "; ".join(str(p) for p in local_paths) if local_paths else "-"

            desc = repo_descriptions.get(repo_name, "")
            if not desc:
                manual = input(
                    f"No description for '{project_name}/{repo_name}'. Enter one "
                    f"(blank to skip): "
                ).strip()
                if manual:
                    answer = input(
                        f"Set this in Azure DevOps project description? [y/N] "
                    ).strip().lower()
                    if answer == "y":
                        updated_description_lines[repo_name] = manual
                        description_changed = True
                    desc = manual

            rows.append((project_name, repo_name, remote_url, local_str, desc or "-"))

        if description_changed:
            repo_lines = "\n".join(f"{name}: {d}" for name, d in updated_description_lines.items())
            repos_block = f"Repos:\n{repo_lines}"
            new_description = f"{other_text}\n\n{repos_block}" if other_text else repos_block
            if update_project_description(org, project_id, project_name, new_description):
                print(f"  Updated project description for {project_name}")

    out_path = base / "ALL_REPOS.md"
    write_all_repos_md(out_path, org, base, rows)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
