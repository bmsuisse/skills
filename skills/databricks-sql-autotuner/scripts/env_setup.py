#!/usr/bin/env python3
"""Set up the SQL autotuner venv with uv and verify the Databricks connection.

Requires uv (https://docs.astral.sh/uv/).

Usage:
    python3 scripts/env_setup.py \
        --dbr-version 17.3 \
        --profile <PROFILE> \
        --cluster-id <CLUSTER_ID>

Creates .venv_autotuner/ in the current directory using uv, installs the
correct databricks-connect version, and verifies the connection with SELECT 1.
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path

VENV_NAME = ".venv_autotuner"


def venv_python(venv: Path) -> Path:
    is_windows = platform.system() == "Windows"
    name = "python.exe" if is_windows else "python"
    return venv / ("Scripts" if is_windows else "bin") / name


def check_uv() -> None:
    result = subprocess.run(["uv", "--version"], capture_output=True, text=True)
    if result.returncode != 0:
        print("[error] uv is not installed or not on PATH.", file=sys.stderr)
        print("Install: curl -LsSf https://astral.sh/uv/install.sh | sh", file=sys.stderr)
        sys.exit(1)
    print(f"[setup] {result.stdout.strip()}")


def ensure_venv(venv: Path) -> None:
    if venv.exists():
        print(f"[setup] Using existing {VENV_NAME}/")
        return
    print(f"[setup] Creating {VENV_NAME} with uv...")
    subprocess.run(["uv", "venv", str(venv)], check=True)

    gitignore = Path(".gitignore")
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    if VENV_NAME not in existing:
        with gitignore.open("a", encoding="utf-8") as f:
            f.write(f"\n{VENV_NAME}/\n")
        print(f"[setup] Added {VENV_NAME}/ to .gitignore")


def install_package(venv: Path, dbr_version: str) -> None:
    pkg = f"databricks-connect=={dbr_version}.*"
    print(f"[setup] Installing {pkg}...")
    subprocess.run(
        ["uv", "pip", "install", "--python", str(venv_python(venv)), pkg],
        check=True,
    )
    print(f"[setup] {pkg} installed.")


def verify_connection(venv: Path, profile: str, cluster_id: str) -> None:
    print(f"[verify] Testing connection (profile={profile}, cluster={cluster_id})...")
    code = (
        "from databricks.connect import DatabricksSession\n"
        f"spark = DatabricksSession.builder.profile({json.dumps(profile)}).clusterId({json.dumps(cluster_id)}).getOrCreate()\n"
        "result = spark.sql('SELECT 1 AS ok').collect()\n"
        "assert result[0]['ok'] == 1, 'Unexpected result from SELECT 1'\n"
        "print(f'[verify] OK \u2014 Spark {spark.version}')\n"
    )
    # Call the venv Python directly — uv run dropped -c support in v0.10+
    proc = subprocess.run(
        [str(venv_python(venv)), "-c", code],
        capture_output=True,
        text=True,
    )
    print(proc.stdout, end="")
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        print("\n[error] Connection failed. Check profile, cluster ID, and auth.", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Set up the SQL autotuner venv.")
    parser.add_argument("--dbr-version", required=True, metavar="VER",
                        help="Databricks Runtime version, e.g. 17.3")
    parser.add_argument("--profile", required=True,
                        help="Databricks CLI profile name")
    parser.add_argument("--cluster-id", required=True, dest="cluster_id",
                        help="Target cluster ID")
    args = parser.parse_args()

    check_uv()
    venv = Path(VENV_NAME)
    ensure_venv(venv)
    install_package(venv, args.dbr_version)
    verify_connection(venv, args.profile, args.cluster_id)

    python_path = venv_python(venv)
    print(f"\n[setup] Done. Run tune.py with:")
    print(f"  {python_path} scripts/tune.py "
          f"--profile {args.profile} --cluster-id {args.cluster_id} ...")


if __name__ == "__main__":
    main()
