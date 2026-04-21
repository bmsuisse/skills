---
title: Python Guidelines
description: Python coding standards — typing, ty type checker, dataclasses, enums, and more.
---

# Python Guidelines

**Skill:** `coding-guidelines-python` · **Plugin:** `coding@bmsuisse-skills`

Enforces Python-specific coding standards for all Python files in the project.

## Core rules

### Typing

Every function has parameter types and a return type. Use `from __future__ import annotations` at the top of every file. Prefer `X | None` over `Optional[X]`.

```python
from __future__ import annotations

def transform(items: list[str], limit: int) -> list[str]:
    return items[:limit]
```

### Type checking — ty

Run `ty` before every commit. Zero errors is the bar.

```bash
uv add --dev ty
uv run ty check
```

`ty` is Astral's fast Python type checker (same ecosystem as `uv` and `ruff`).

### No mutable default arguments

```python
# ❌ shared across all calls
def append(item: str, items: list[str] = []) -> list[str]: ...

# ✅
def append(item: str, items: list[str] | None = None) -> list[str]:
    result = items or []
    result.append(item)
    return result
```

### Dataclasses over raw dicts

| Shape | Use |
|---|---|
| Own object, instantiated by you | `@dataclass` |
| Dict-shaped from external source (JSON, DB row) | `TypedDict` |
| Needs runtime validation (API bodies, user input) | `pydantic.BaseModel` |

```python
# ❌
def process(data: dict[str, Any]) -> dict[str, Any]: ...

# ✅
@dataclass
class Report:
    id: str
    title: str

def process(report: Report) -> Report: ...
```

### Enums for string constants

```python
# ❌
def export(format: str) -> bytes:
    if format == "pdf": ...

# ✅
from typing import Literal
Format = Literal["pdf", "csv"]

def export(format: Format) -> bytes: ...
```

### No module-level mutable state

```python
# ❌
_cache: dict[str, str] = {}

# ✅
class Cache:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}
```

## Pre-commit checklist

- [ ] All function parameters and return types annotated
- [ ] `from __future__ import annotations` at top of every file
- [ ] `uv run ty check` passes with zero errors
- [ ] `uv run pytest` passes
- [ ] No mutable default arguments
- [ ] No `dict[str, Any]` as a data carrier
- [ ] No raw string constants in conditions — use `Literal` or `Enum`
- [ ] No module-level mutable variables

## The four principles

The skill also embeds four meta-principles about how LLMs should approach coding tasks:

| Principle | Summary |
|---|---|
| **Think Before Coding** | Surface assumptions, ask clarifying questions before writing code |
| **Simplicity First** | YAGNI — don't add abstractions until they're needed |
| **Surgical Changes** | Only touch what the task requires; match existing style |
| **Goal-Driven Execution** | Write a failing test first, then make it pass |
