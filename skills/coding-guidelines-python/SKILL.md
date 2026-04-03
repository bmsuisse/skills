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

## Typing

Every function has parameter types and a return type. Use `from __future__ import annotations`
at the top of every file. Prefer `X | None` over `Optional[X]`. Use generics
where appropriate (`list[str]`, `dict[str, int]`).

```python
from __future__ import annotations

def transform(items: list[str], limit: int) -> list[str]:
    return items[:limit]
```

## Pyright

Run `pyright` before every commit. Zero errors is the bar — never disable
a check to make a deadline. Fix the root cause.

```bash
uv run pyright
```

## Tests

Write tests before committing. Run with:

```bash
uv run pytest
```

## Abstract base classes

```python
from abc import ABC, abstractmethod

class Processor(ABC):
    @abstractmethod
    def process(self, data: str) -> str: ...
```

## No mutable default arguments

Mutable defaults are shared across all calls — a classic Python trap.

```python
# ❌
def append(item: str, items: list[str] = []) -> list[str]:
    items.append(item)
    return items

# ✅
def append(item: str, items: list[str] | None = None) -> list[str]:
    result = items or []
    result.append(item)
    return result
```

## Dataclasses over raw dicts

`dict[str, Any]` as a data carrier is untyped and opaque. Give every data
shape an explicit type so pyright can check it.

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

Raw string literals in conditions are fragile and invisible to the type checker.
Use `Literal` for a closed set of values, or `Enum` when you need iteration
or methods.

```python
# ❌
def export(format: str) -> bytes:
    if format == "pdf": ...

# ✅
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

## Pre-commit checklist (Python)

- [ ] All function parameters and return types annotated
- [ ] `from __future__ import annotations` at the top of every file
- [ ] `uv run pyright` passes with zero errors
- [ ] `uv run pytest` passes
- [ ] No mutable default arguments
- [ ] No `dict[str, Any]` as a data carrier — use a dataclass or TypedDict
- [ ] No raw string constants in conditions — use `Literal` or `Enum`
- [ ] No module-level mutable variables
