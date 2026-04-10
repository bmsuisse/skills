"""Task runner — cross-platform issues: shell=True, missing encoding, os.path over pathlib."""
import os
import os.path
import subprocess


def run_linter(filepath: str) -> int:
    """Run ruff on a file, return exit code."""
    # shell=True with a list is redundant and platform-fragile
    result = subprocess.run(
        ["ruff", "check", filepath],
        shell=True,
        capture_output=True,
        text=True,
    )
    return result.returncode


def run_tests(test_dir: str, verbose: bool = False) -> dict:
    """Run pytest on a directory."""
    cmd = ["pytest", test_dir]
    if verbose:
        cmd.append("-v")
    # shell=True not needed when passing a list — and breaks on Windows
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def get_python_version() -> str:
    """Get Python version string."""
    result = subprocess.run(
        ["python", "--version"],
        shell=True,          # unnecessary with a list
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or result.stderr.strip()


def read_file(path: str) -> list[str]:
    """Read lines from a file — missing encoding (platform default differs)."""
    with open(path) as f:    # no encoding= → different on Win/Mac/Linux
        return f.readlines()


def write_output(path: str, lines: list[str]) -> None:
    """Write lines to a file — missing encoding and newline control."""
    with open(path, "w") as f:   # no encoding= or newline= → CRLF on Windows
        f.writelines(lines)


def ensure_dir(path: str) -> str:
    """Create a directory if it doesn't exist."""
    # os.path instead of pathlib; makedirs without exist_ok risks race condition
    if not os.path.exists(path):
        os.makedirs(path)
    return path


def stem(filepath: str) -> str:
    """Return filename without extension."""
    return os.path.splitext(os.path.basename(filepath))[0]
