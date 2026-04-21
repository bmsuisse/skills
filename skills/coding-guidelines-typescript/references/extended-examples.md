# Extended Examples — TypeScript Coding Guidelines

This file contains deeper examples for cases where the SKILL.md summary is not
enough. Load this file when a guideline needs more detailed explanation or when
you encounter patterns not directly covered by the main skill.

## Table of Contents

1. [Narrowing unknown without assertions](#1-narrowing-unknown-without-assertions)
2. [Generics vs. overloads](#2-generics-vs-overloads)
3. [Discriminated unions for state machines](#3-discriminated-unions-for-state-machines)
4. [Utility types — when and when not](#4-utility-types--when-and-when-not)
5. [Error handling patterns](#5-error-handling-patterns)
6. [Class vs. interface decisions](#6-class-vs-interface-decisions)

---

## 1. Narrowing `unknown` without assertions

When you receive external data (API responses, `JSON.parse`, user input),
the correct type is `unknown`. Narrow it with a type guard rather than casting.

```typescript
// ❌ — assertion with no guard; crashes if shape differs
const payload = JSON.parse(raw) as { userId: string; role: string };

// ✅ — validate at the boundary, strong types inside
interface AuthPayload {
    userId: string;
    role: "admin" | "user";
}

function isAuthPayload(val: unknown): val is AuthPayload {
    return (
        typeof val === "object" &&
        val !== null &&
        typeof (val as Record<string, unknown>).userId === "string" &&
        ["admin", "user"].includes((val as Record<string, unknown>).role as string)
    );
}

const parsed = JSON.parse(raw);
if (!isAuthPayload(parsed)) throw new Error("Unexpected payload shape");
// parsed is AuthPayload here — compiler-verified
```

**Why**: Type guards run at runtime and give you a clean failure point. A naked
`as` assertion silently corrupts the type environment for every consumer.

---

## 2. Generics vs. overloads

Overloads are hard to read and maintain. Prefer a single generic signature when
the return type mirrors the input type.

```typescript
// ❌ — three overloads that all do the same thing
function wrap(value: string): { value: string };
function wrap(value: number): { value: number };
function wrap(value: boolean): { value: boolean };
function wrap(value: any): any { return { value }; }

// ✅ — one generic, fully type-safe
function wrap<T>(value: T): { value: T } {
    return { value };
}
```

Use overloads only when the relationship between input and output genuinely
differs across forms and cannot be expressed with a single generic.

---

## 3. Discriminated unions for state machines

Any object that can be in one of several exclusive states is a state machine.
Model it as a discriminated union rather than an object with optional fields —
optional fields allow impossible states to be represented at the type level.

```typescript
// ❌ — allows impossible state: { loading: true, error: "..." }
interface FetchState<T> {
    loading: boolean;
    data?: T;
    error?: string;
}

// ✅ — every state is mutually exclusive; narrowing is exhaustive
type FetchState<T> =
    | { status: "idle" }
    | { status: "loading" }
    | { status: "success"; data: T }
    | { status: "error"; error: string };

function render<T>(state: FetchState<T>): string {
    switch (state.status) {
        case "idle":    return "...";
        case "loading": return "Loading...";
        case "success": return JSON.stringify(state.data); // data is T here
        case "error":   return `Error: ${state.error}`;
    }
    // TypeScript exhaustiveness check: if you add a new status, this won't compile
}
```

---

## 4. Utility types — when and when not

TypeScript's built-in utility types (`Partial`, `Pick`, `Omit`, `Readonly`) are
useful for expressing derived shapes without duplication.

```typescript
// ❌ — manually repeating fields; diverges from User when User changes
interface UserUpdatePayload {
    name?: string;
    email?: string;
}

// ✅ — derived from User; automatically stays in sync
type UserUpdatePayload = Partial<Pick<User, "name" | "email">>;
```

**When not to use them:**

- Don't chain more than 2-3 utility types — the resulting type becomes unreadable.
- Don't use `Partial<T>` to bypass required fields for initialisation; use a
  factory function or builder pattern instead.
- Don't use `Record<string, unknown>` as a substitute for an interface; give
  shapes names.

---

## 5. Error handling patterns

TypeScript has no checked exceptions. Make error paths explicit in the type
system rather than relying on callers remembering to catch.

```typescript
// ❌ — throws are invisible in the signature; callers forget to catch
async function getAccount(id: string): Promise<Account> {
    const row = await db.findOne(id);
    if (!row) throw new Error("Not found");
    return row;
}

// ✅ — null signals absence; caller must handle it
async function getAccount(id: string): Promise<Account | null> {
    return db.findOne(id); // returns null if not found
}

// ✅ — discriminated union when you need typed error context
type AccountResult =
    | { ok: true; account: Account }
    | { ok: false; reason: "not_found" | "forbidden" };

async function getAccount(id: string, actor: User): Promise<AccountResult> {
    const row = await db.findOne(id);
    if (!row) return { ok: false, reason: "not_found" };
    if (!canAccess(actor, row)) return { ok: false, reason: "forbidden" };
    return { ok: true, account: row };
}
```

Reserve throwing for truly unexpected programmer errors (e.g., violated
invariants). Use return types for recoverable application errors.

---

## 6. Class vs. interface decisions

| Scenario | Use |
|---|---|
| Pure data shape (no methods, no inheritance) | `interface` or `type` alias |
| Shape from external source (JSON, DB row) | `interface` with a type guard |
| Shared logic in a base, subclasses differ | `abstract class` |
| Service with constructor injection | `class` implementing an `interface` |
| Closed set of string values | `const` enum or union literal |

**Abstract class example:**

```typescript
// Base provides shared parsing logic; subclasses supply format-specific details
abstract class DataParser<T> {
    abstract parse(raw: string): T;

    parseOrNull(raw: string): T | null {
        try {
            return this.parse(raw);
        } catch {
            return null;
        }
    }
}

class JsonParser<T> extends DataParser<T> {
    parse(raw: string): T {
        return JSON.parse(raw) as T; // boundary: raw comes from trusted internal store
    }
}
```
