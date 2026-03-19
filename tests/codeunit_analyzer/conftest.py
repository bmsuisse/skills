"""pytest configuration for codeunit-analyzer tests.

Adds the skill's own directory to sys.path so `from scripts.x import ...`
works the same way as when running `analyze.py` directly from within the
skill directory.
"""

import sys
from pathlib import Path

# Make `scripts.*` importable without installing anything
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "skills" / "codeunit-analyzer"))
