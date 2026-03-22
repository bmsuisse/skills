---
name: coding-guidelines
description: >
  Apply and enforce project coding standards during any code generation, review,
  or refactoring session. Use this skill whenever writing new code, reviewing a
  PR, refactoring existing files, or when the user asks to "follow the coding
  guidelines", "enforce standards", "apply code style", "review code quality",
  or "check before commit". Trigger proactively on any Python or TypeScript work
  session — these rules apply universally across the codebase.
---

# Coding Guidelines

These rules apply to every file touched, regardless of language or context.
When in doubt: would a senior engineer who hates noise approve this?

---

## Universal rules

### No comments in code

Code must be self-explanatory through naming. Remove all comments that restate
what the code does. The only acceptable documentation is a module-level docstring
when a file's purpose is non-obvious, or a one-line docstring on a public API
that cannot speak for itself.

```python
# ❌
# Get user by id
user = repo.get(user_id)

# ✅
user = repo.get(user_id)
```

### Don't repeat yourself

Every piece of logic lives in exactly one place. If two functions share more
than a few lines of logic, extract it. Duplication is a bug waiting to happen.

### Small functions

A function does one thing. If you need to scroll to understand it, split it.
Target: under 20 lines per function body. A long parameter list is a smell —
consider a dataclass or a dedicated type.

### Abstract classes over duck typing

When multiple concrete types share a contract, define it with an `ABC` in Python
or an `interface`/`abstract class` in TypeScript. Never rely on structural
coincidence.

```python
# ❌
def run(runner):
    runner.execute()  # hope it has .execute()

# ✅
class Runner(ABC):
    @abstractmethod
    def execute(self) -> None: ...

def run(runner: Runner) -> None:
    runner.execute()
```

### Minimal error handling

Only catch what you can meaningfully recover from at the call site. Do not wrap
happy paths in `try/except` or `try/catch` for safety theatre. Let exceptions
propagate and fail loudly. One `try` block per actual recovery strategy.

### No `hasattr` or `isinstance` checks

If you need `hasattr` to know whether an attribute exists, the type is wrong.
Fix the type — add the attribute or use a proper interface. If you need
`isinstance` to branch on a concrete type, the abstraction is broken upstream.
Use polymorphism or a typed union instead. Both patterns are training artefacts
that mask type errors rather than fixing them.

```python
# ❌ hasattr guard hiding a missing type contract
def send(target):
    if hasattr(target, 'email'):
        notify(target.email)

# ✅ Type the contract and trust it
def send(target: Notifiable) -> None:
    notify(target.email)

# ❌ isinstance check — broken abstraction
def process(value: str | int) -> str:
    if isinstance(value, int):
        return str(value)
    return value

# ✅ Fix the caller to pass the right type
def process(value: str) -> str:
    return value
```

```python
# ❌
try:
    result = compute()
except Exception:
    return None

# ✅  — only catch if you have a real recovery
result = compute()
```

### Composition over inheritance

Only inherit from `ABC` / `interface`. Never build deep concrete class
hierarchies — inject dependencies instead of extending them. Inheritance for
behaviour sharing is almost always the wrong tool.

```python
# ❌
class AdminService(UserService):
    ...

# ✅
class AdminService:
    def __init__(self, users: UserRepository) -> None:
        self.users = users
```

### Fail fast at the boundary

Validate and guard at the entry point — the API handler, CLI argument parser,
or config loader. After that, trust your types and let them fail loudly if
something is wrong. Do not re-validate the same thing deep inside a helper.

### File size limit

No file exceeds 1000 lines. If a file approaches this, split by responsibility
before adding more code.

---

## Python

### Typing

Every function has parameter types and a return type. Use `from __future__ import annotations`
at the top of every file. Prefer `X | None` over `Optional[X]`. Use generics
where appropriate (`list[str]`, `dict[str, int]`).

```python
from __future__ import annotations

def transform(items: list[str], limit: int) -> list[str]:
    return items[:limit]
```

### Pyright

Run `pyright` before every commit. Zero errors is the bar — never disable
a check to make a deadline. Fix the root cause.

```bash
uv run pyright
```

### Tests

Write tests before committing. Run with:

```bash
uv run pytest
```

### Abstract base classes

```python
from abc import ABC, abstractmethod

class Processor(ABC):
    @abstractmethod
    def process(self, data: str) -> str: ...
```

### No mutable default arguments

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

### Dataclasses over raw dicts

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

### Enums for string constants

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

### No module-level mutable state

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

---

## TypeScript

### Typing

No `any`. No non-null assertions (`!`) unless the reason is documented in the
code. Prefer explicit return types on all exported functions. Use generics over
`unknown` casts.

```typescript
// ❌
function parse(data: any): any { ... }

// ✅
function parse<T>(data: unknown): T { ... }
```

### Interfaces and abstract classes

Define contracts explicitly. Use `interface` for pure shapes, `abstract class`
when shared behaviour belongs in the base.

### Check

Run before every commit:

```bash
npm run check
```

---

## Pre-commit checklist

Before committing, verify all of the following:

- [ ] No comments left in the diff (unless documenting a non-obvious public API)
- [ ] No logic duplicated — each piece of knowledge has one home
- [ ] No function longer than ~20 lines
- [ ] Abstractions are backed by `ABC` / `interface`, not coincidence
- [ ] No defensive `try/except` or `try/catch` around happy paths
- [ ] No `hasattr` checks — fix the type instead
- [ ] No `isinstance` checks — fix the abstraction instead
- [ ] No concrete class extending another concrete class — compose instead
- [ ] Validation only at the boundary — not repeated deep inside helpers
- [ ] No mutable default arguments (Python)
- [ ] No `dict[str, Any]` as a data carrier — use a dataclass or TypedDict
- [ ] No raw string constants in conditions — use `Literal` or `Enum`
- [ ] No module-level mutable variables
- [ ] All Python types present; `pyright` passes with zero errors
- [ ] No TypeScript `any` or undocumented `!`
- [ ] No file exceeds 1000 lines
- [ ] `uv run pytest` passes (Python)
- [ ] `npm run check` passes (TypeScript)
