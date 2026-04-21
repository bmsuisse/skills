#!/usr/bin/env python3
"""
Check that the local databricks-connect version matches the cluster's DBR.
If mismatched, create .venv_spark_<major>_<minor>/ with the correct version.

Usage:
    python check_spark_env.py

Reads DATABRICKS_PROFILE and DATABRICKS_CLUSTER_ID from .env or environment.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


def load_dotenv(path: str = ".env") -> None:
    env_file = Path(path)
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_cluster_dbr(profile: str, cluster_id: str) -> str:
    result = subprocess.run(
        ["databricks", "clusters", "get", "--cluster-id", cluster_id, "--profile", profile],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(result.stdout)
    spark_version: str = data["spark_version"]  # e.g. "17.4.x-scala2.12"
    match = re.match(r"(\d+\.\d+)", spark_version)
    if not match:
        raise ValueError(f"Cannot parse DBR version from: {spark_version!r}")
    return match.group(1)


def get_installed_connect_version(python_bin: Path | None = None) -> str | None:
    exe = str(python_bin) if python_bin else sys.executable
    result = subprocess.run(
        [exe, "-m", "pip", "show", "databricks-connect"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if line.startswith("Version:"):
            return line.split(":", 1)[1].strip()
    return None


def major_minor(version: str) -> str:
    m = re.match(r"(\d+\.\d+)", version)
    return m.group(1) if m else version


def python_in_venv(venv: Path) -> Path:
    if sys.platform == "win32":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def setup_venv(dbr: str, venv_path: Path) -> None:
    print(f"\nCreating {venv_path} with databricks-connect=={dbr}.*")
    subprocess.run(["uv", "venv", str(venv_path)], check=True)
    subprocess.run(
        ["uv", "pip", "install", f"databricks-connect=={dbr}.*",
         "--python", str(python_in_venv(venv_path))],
        check=True,
    )
    _print_activate(venv_path)


def _print_activate(venv_path: Path) -> None:
    print("\nActivate with:")
    if sys.platform == "win32":
        print(f"  {venv_path}\\Scripts\\activate")
    else:
        print(f"  source {venv_path}/bin/activate")


def main() -> None:
    load_dotenv()

    profile = os.getenv("DATABRICKS_PROFILE")
    cluster_id = os.getenv("DATABRICKS_CLUSTER_ID")

    if not profile or not cluster_id:
        sys.exit("Missing DATABRICKS_PROFILE or DATABRICKS_CLUSTER_ID — set in .env or environment.")

    print(f"Profile  : {profile}")
    print(f"Cluster  : {cluster_id}")

    print("\nFetching cluster version...")
    dbr = get_cluster_dbr(profile, cluster_id)
    print(f"Cluster DBR : {dbr}")

    # Check current environment first
    installed = get_installed_connect_version()
    if installed:
        mm = major_minor(installed)
        print(f"Installed   : databricks-connect {installed} ({mm})")
        if mm == dbr:
            print(f"\n✓ Aligned ({dbr}) — no action needed.")
            return
        print(f"\n✗ Mismatch: cluster={dbr}, installed={mm}")
    else:
        print("databricks-connect not installed in current environment.")

    # Versioned venv name, e.g. .venv_spark_17_4
    venv_name = f".venv_spark_{dbr.replace('.', '_')}"
    venv_path = Path(venv_name)

    if venv_path.exists():
        existing = get_installed_connect_version(python_in_venv(venv_path))
        if existing and major_minor(existing) == dbr:
            print(f"\n✓ {venv_path} already has matching version ({existing}).")
            _print_activate(venv_path)
            return
        print(f"{venv_path} exists but version wrong ({existing}) — recreating.")

    setup_venv(dbr, venv_path)


if __name__ == "__main__":
    main()
