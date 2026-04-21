---
name: coding-guidelines-typescript
plugin: coding
description: >
  Apply and enforce TypeScript-specific coding standards. Use alongside
  coding-guidelines for any TypeScript file — covers typing, no-any policy,
  interfaces, abstract classes, async typing, discriminated unions, and
  pre-commit checks. Trigger on any TypeScript work session, PR review, code
  generation task, or refactoring. Also trigger when writing TypeScript even
  if the user doesn't explicitly ask for guidelines — if the user asks you to
  write a function, add a feature, fix a bug, or review code in a .ts or .tsx
  file, apply these standards automatically without being asked.
---

# TypeScript Coding Guidelines

The goal of these guidelines is to make TypeScript's type system do real work:
catching bugs before runtime, making contracts explicit, and eliminating the
"it works if you pass the right thing" class of errors. Follow them automatically
whenever working in TypeScript — don't wait for the user to ask.

## No `any`

`any` disables the type checker for that value and everything that touches it.
Use `unknown` when you don't know the type yet — it forces you to narrow before
using the value, which is the point.

```typescript
// ❌ — silences the type checker; errors hide until runtime
function parse(data: any): any {
    return data.value; // no error even if data has no .value
}

// ✅ — forces the caller to handle the unknown shape
function parse<T>(data: unknown): T {
    if (!isValidShape<T>(data)) throw new Error("Unexpected shape");
    return data;
}
```

Generics over `unknown` casts: if the shape is known at call time, express it
as a generic parameter so the compiler can verify it end-to-end.

## No non-null assertions without a comment

`!` is a lie you tell the compiler. It suppresses null checks and shifts errors
to runtime. Only use it when you have information the compiler cannot infer, and
always document *why* on the same line.

```typescript
// ❌ — silently crashes if getElementById returns null
const el = document.getElementById("root")!;

// ✅ — explicit contract documented at the assertion point
const el = document.getElementById("root")!; // guaranteed by index.html template
```

When you find yourself reaching for `!`, first ask whether an earlier narrowing
or a default value would express the intent more clearly.

## Explicit return types on exported functions

Return types are part of the public contract. Omitting them means callers
discover the type by reading the implementation — which defeats the purpose of
having an interface. Infer private helpers freely; annotate exports always.

```typescript
// ❌ — callers must read the body to know what they get
export function getUser(id: string) {
    return db.query(`SELECT * FROM users WHERE id = $1`, [id]);
}

// ✅ — contract is visible without reading the body
export async function getUser(id: string): Promise<User | null> {
    return db.query(`SELECT * FROM users WHERE id = $1`, [id]);
}
```

## Interfaces and abstract classes — no duck typing

Duck typing (`{ execute(): void }`) makes contracts invisible. Define a named
`interface` for every shape that crosses a boundary (function parameter, return
value, API response). Use `abstract class` when shared behaviour belongs in the
base — not for shapes that are purely structural.

```typescript
// ❌ — contract lives only inside this function; cannot be reused or tested
function run(runner: { execute(): void; name: string }) {
    console.log(runner.name);
    runner.execute();
}

// ✅ — contract is named, reusable, and mockable in tests
interface Runner {
    name: string;
    execute(): void;
}

function run(runner: Runner): void {
    console.log(runner.name);
    runner.execute();
}
```

## No type assertions without justification

`as SomeType` tells the compiler "trust me", bypassing all checks. It is
appropriate only when you genuinely have information the compiler cannot infer
(e.g., you know the shape of an API response by contract). Document the reason
inline — if you can't explain it, that's a signal to use a runtime guard instead.

```typescript
// ❌ — if the API changes shape, this crashes silently at runtime
const user = response.data as User;

// ✅ — assertion is justified and documented
const user = response.data as User; // /users endpoint always returns User per OpenAPI spec

// Even better — use a runtime guard for untrusted data
function isUser(val: unknown): val is User {
    return typeof val === "object" && val !== null && "id" in val;
}
const user = isUser(response.data) ? response.data : null;
```

## Union types and discriminated unions over string flags

Raw `string` parameters in conditions are fragile — a typo compiles fine and
fails silently at runtime. Use a union literal or `const` enum to close the set
of valid values at the type level. For objects that can be one of several shapes,
use a discriminated union with a literal `kind` or `type` field so TypeScript
can narrow exhaustively.

```typescript
// ❌ — "pdff" typo compiles without error
function exportData(format: string) {
    if (format === "pdf") { ... }
}

// ✅ — invalid values are caught at call sites
type ExportFormat = "pdf" | "csv" | "xlsx";
function exportData(format: ExportFormat): Buffer { ... }

// ✅ discriminated union — exhaustive narrowing, no string comparisons
type Result<T> =
    | { kind: "ok"; value: T }
    | { kind: "err"; error: string };

function handle<T>(result: Result<T>): T {
    if (result.kind === "ok") return result.value;
    throw new Error(result.error); // TS knows result is err here
}
```

## Async functions return typed Promises

Async functions that can fail should make the failure type explicit. Avoid
returning `Promise<any>` — it infects callers and makes error handling
invisible. Prefer a discriminated union result type over throwing for
recoverable errors.

```typescript
// ❌ — callers don't know what this returns or how it fails
async function fetchUser(id: string): Promise<any> {
    const res = await fetch(`/api/users/${id}`);
    return res.json();
}

// ✅ — contract is complete: success type, error cases, and never surprises
async function fetchUser(id: string): Promise<User | null> {
    const res = await fetch(`/api/users/${id}`);
    if (!res.ok) return null;
    return res.json() as User; // validated against OpenAPI spec
}
```

## Pre-commit checklist (TypeScript)

Run `npm run check` before every commit. Then verify:

- [ ] No `any` — use `unknown`, a generic, or a proper type guard
- [ ] No undocumented non-null assertions (`!`)
- [ ] Explicit return types on all exported functions and methods
- [ ] Contracts expressed as `interface` or `abstract class`, not inline duck typing
- [ ] No raw `string` in conditions — use a union type or `const` enum
- [ ] No unexplained `as SomeType` assertions
- [ ] Async functions have typed `Promise<T>` return types (not `Promise<any>`)
- [ ] `npm run check` passes

## References

For extended examples and the reasoning behind each rule, see
`references/extended-examples.md`. Load it when you need to explain a guideline
in depth or handle a case not covered above.
