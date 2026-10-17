#!/usr/bin/env python3
"""Smoke check: python3 test_mine.py  (builds a throwaway repo, asserts the digest sees the signals)."""
import pathlib, subprocess, sys, tempfile

d = pathlib.Path(tempfile.mkdtemp())
g = lambda *a: subprocess.run(["git", "-C", str(d), "-c", "user.name=t", "-c", "user.email=t@t", *a], check=True, capture_output=True, text=True).stdout
g("init", "-q", "-b", "main")
for i, (msg, body) in enumerate([
    ("feat: add cache", ""),
    ("fix: stale cache\n\nRoot cause: cache keyed on layout, never invalidated after prompt fixes.", ""),
    ("Revert \"feat: add cache\"\n\nThis reverts commit X.", ""),
    ("refactor(db): one pool helper", ""),
    ("fix: stale cache", ""),  # cherry-pick duplicate: must count once
]):
    (d / f"f{i}.py").write_text(str(i))
    g("add", "."); g("commit", "-q", "-m", msg)
g("update-ref", "refs/remotes/origin/HEAD", "HEAD")
res = subprocess.run([sys.executable, str(pathlib.Path(__file__).parent / "mine.py"), str(d), "--ref", "HEAD"], capture_output=True, text=True)
o = res.stdout
assert res.returncode == 0, res.stderr
assert "4 unique commits" in o, o  # duplicate subject collapsed
assert "Revert \"feat: add cache\"" in o and "## Reverts" in o, o
assert "Root cause: cache keyed on layout" in o, o  # rule-word section shows the body line
assert "Agent docs on this ref: none" in o, o
print("ok")
