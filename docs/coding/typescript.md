---
title: TypeScript Guidelines
description: TypeScript coding standards — no any, strict typing, discriminated unions, async patterns.
---

# TypeScript Guidelines

**Skill:** `coding-guidelines-typescript` · **Plugin:** `coding@bmsuisse-skills`

## Core rules

### No `any`

`any` disables type checking for everything it touches — every variable assigned from it, every function that receives it. Once it enters your codebase, type errors become invisible.

```typescript
// ❌
function process(data: any) { ... }

// ✅
function process(data: unknown) {
    if (!isReport(data)) throw new Error("Invalid data");
    // data is now Report
}
```

### No non-null assertions (`!`)

`!` is a lie you tell the compiler. It will eventually be wrong.

```typescript
// ❌ crashes if user is null
const name = getUser()!.name;

// ✅ handle it
const user = getUser();
const name = user?.name ?? "Anonymous";
```

### Explicit return types

Forces you to think about the contract before writing the implementation.

```typescript
// ❌
function getUser(id: string) { ... }

// ✅
function getUser(id: string): Promise<User | null> { ... }
```

### Interfaces over duck typing

```typescript
// ❌ — brittle, can't be reused
function render(obj: { id: string; name: string }) { ... }

// ✅
interface User {
    id: string;
    name: string;
}
function render(user: User) { ... }
```

### `as` only with a runtime guard

```typescript
// ❌ assertion with no verification
const user = JSON.parse(data) as User;

// ✅ guard first
function isUser(x: unknown): x is User {
    return typeof x === "object" && x !== null && "id" in x;
}
const parsed = JSON.parse(data);
if (!isUser(parsed)) throw new Error("Invalid user");
```

### Discriminated unions over flat optional objects

```typescript
// ❌ — status is implicit, fields are all optional
interface QueryResult {
    data?: User[];
    error?: string;
    loading?: boolean;
}

// ✅ — status is explicit, exhaustive switch works
type QueryResult =
    | { status: "loading" }
    | { status: "error"; error: string }
    | { status: "success"; data: User[] };

function render(result: QueryResult) {
    switch (result.status) {
        case "loading": return <Spinner />;
        case "error":   return <Error msg={result.error} />;
        case "success": return <List data={result.data} />;
    }
}
```

### Async/Promise typing

```typescript
// ❌
async function fetchUser(id: string): Promise<any> { ... }

// ✅
async function fetchUser(id: string): Promise<User | null> {
    const res = await fetch(`/api/users/${id}`);
    if (res.status === 404) return null;
    return res.json() as Promise<User>;
}
```

## Pre-commit checklist

- [ ] Zero `any` — use `unknown` + type guards at boundaries
- [ ] Zero `!` — use optional chaining or explicit null checks
- [ ] All functions have explicit return types
- [ ] All data shapes use `interface` or `type`, not inline object literals
- [ ] `as` assertions backed by a runtime guard
- [ ] Union types use discriminated unions for state modelling
- [ ] `Promise<T>` is always typed, never `Promise<any>`
