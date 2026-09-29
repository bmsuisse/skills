---
name: coding-guidelines-python
plugin: coding
description: >
  Apply and enforce Python-specific coding standards. Use alongside
  coding-guidelines for any Python file — covers typing, Pyright, dataclasses,
  enums, abstract base classes, mutable defaults, and module-level state.
  Trigger on any Python work session, PR review, or when the user asks to
  "follow Python guidelines", "check Python style", or "enforce Python standards".
---

# Python Coding Guidelines

## Linting — ruff

We use ruff with strict rules (config in `prek`); run `uv run ruff check` and fix what it reports.
`ANN401` (`Any`) is only a warning. Don't add `from __future__ import annotations` (unneeded on 3.14).

## Type checking — ty

```bash
uv run ty check
```

## Database Access

Use [pgdevkit and it's skills](https://github.com/bmsuisse/pgdevkit)

## Tests

Write tests according to skill testing-strategy before committing. Run with:

```bash
uv run -m pytest TEST_FILE.py
```

## Dataclasses over raw dicts

`dict[str, Any]` as a data carrier is untyped and opaque. Give every data
shape an explicit type so ty can check it.

- **`@dataclass`** — when you own the object and instantiate it yourself
- **`TypedDict`** — when the data is dict-shaped from an external source
  (JSON, DB row, config) and something downstream expects a plain `dict`
- **`pydantic.BaseModel`** — when you need runtime validation (API request
  bodies, config loading, user input)

```python
# ❌
def process(data: dict[str, Any]) -> dict[str, Any]: ...

# ✅ own object
@dataclass
class Report:
    id: str
    title: str

def process(report: Report) -> Report: ...

# ✅ external dict shape (e.g. parsed JSON)
class ReportPayload(TypedDict):
    id: str
    title: str
```

## Enums for string constants

Use `Literal` for a closed set of values.

```python
from typing import Literal
Format = Literal["pdf", "csv"]

def export(format: Format) -> bytes: ...
```

## No module-level mutable state

Module-level variables that get mutated are hidden global state. They make
testing hard and introduce subtle ordering bugs. Pass state explicitly or
use a class.

```python
# ❌
_cache: dict[str, str] = {}

def get(key: str) -> str:
    return _cache[key]

# ✅
class Cache:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def get(self, key: str) -> str:
        return self._store[key]
```

## References

Authoritative sources for the principles above are in `references/references.md`.
Load it when you need to cite or explain the reasoning behind a guideline.

## Pre-commit checklist (Python)

- [ ] `uv run ruff check` passes
- [ ] `uv run ty check` passes with zero errors
- [ ] `uv run -m pytest YOURFILE.py` passes
- [ ] No `dict[str, Any]` as a data carrier — use a dataclass or TypedDict
- [ ] No raw string constants in conditions — use `Literal`
- [ ] No module-level mutable variables

---

More guidelines and examples can be found in the `references/examples.md` file.
