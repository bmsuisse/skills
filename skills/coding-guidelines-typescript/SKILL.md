---
name: coding-guidelines-typescript
plugin: coding
description: >
  Apply and enforce TypeScript-specific coding standards. Use alongside
  coding-guidelines for any TypeScript file — covers typing, no-any policy,
  interfaces, abstract classes, and pre-commit checks. Trigger on any
  TypeScript work session, PR review, or when the user asks to "follow
  TypeScript guidelines", "check TS style", or "enforce TypeScript standards".
---

# TypeScript Coding Guidelines

## Typing

No `any`. No non-null assertions (`!`) unless the reason is documented in the
code. Prefer explicit return types on all exported functions. Use generics over
`unknown` casts.

```typescript
// ❌
function parse(data: any): any { ... }

// ✅
function parse<T>(data: unknown): T { ... }
```

## Interfaces and abstract classes

Define contracts explicitly. Use `interface` for pure shapes, `abstract class`
when shared behaviour belongs in the base.

```typescript
// ❌ — duck typing, no contract
function run(runner: { execute(): void }) {
    runner.execute();
}

// ✅ — explicit interface
interface Runner {
    execute(): void;
}

function run(runner: Runner): void {
    runner.execute();
}
```

## No type assertions without justification

`as SomeType` silences the type checker. Only use it when you have information
the compiler cannot infer, and document why inline.

```typescript
// ❌
const user = data as User;

// ✅ — only when you know the shape is guaranteed by an external contract
const user = data as User; // API contract guarantees this shape (see api.ts)
```

## Enums and literal types

Prefer `const` enums or union literals over raw strings in conditions.

```typescript
// ❌
function export(format: string) { ... }

// ✅
type Format = "pdf" | "csv";
function export(format: Format) { ... }
```

## Check

Run before every commit:

```bash
npm run check
```

## Pre-commit checklist (TypeScript)

- [ ] No `any` — use `unknown` or a proper generic
- [ ] No undocumented non-null assertions (`!`)
- [ ] Explicit return types on all exported functions
- [ ] Contracts expressed as `interface` or `abstract class`, not duck typing
- [ ] No raw string literals in conditions — use a union type or `const` enum
- [ ] `npm run check` passes
