# Good vs bad comment examples, by language

More paired examples than fit in SKILL.md. Read this when you want more
reference material for a specific language, or when writing eval/test cases
for this skill.

## Python

```python
# Bad -- restates the code
# loop through users and print name
for user in users:
    print(user.name)

# Good -- no comment needed
for user in users:
    print(user.name)
```

```python
# Bad -- vague TODO, no context for the next person
def send_invoice(order):
    # TODO: fix this
    return render(order)

# Good -- names the actual constraint
def send_invoice(order):
    # Renders synchronously for now -- the async renderer drops line-item
    # discounts (see INVOICE-482). Swap back once that's fixed upstream.
    return render(order)
```

```python
# Bad -- docstring for a private helper that only restates the signature
def _clamp(x: int, lo: int, hi: int) -> int:
    """Clamps x between lo and hi."""
    return max(lo, min(x, hi))

# Good -- signature + name already say this; no docstring needed
def _clamp(x: int, lo: int, hi: int) -> int:
    return max(lo, min(x, hi))
```

```python
# Bad -- public API with no contract documented
def schedule(job, at):
    ...

# Good -- documents what a caller can't infer from the signature
def schedule(job, at):
    """Queue `job` to run at `at` (UTC). Silently no-ops if `at` is in
    the past -- callers needing "run now" semantics should call `run` instead."""
    ...
```

## JavaScript / TypeScript

```javascript
// Bad -- narrates a change instead of explaining current behavior
// changed this from a for loop to reduce on 2022-03-01
const total = items.reduce((sum, i) => sum + i.price, 0);

// Good -- git blame is the record of what changed and when; comment (if any)
// only needs to explain the current code
const total = items.reduce((sum, i) => sum + i.price, 0);
```

```typescript
// Bad -- type escape with no explanation
const config = (raw as any).settings;

// Good -- fix the type, or if you truly can't yet, say why
// raw is untyped JSON from a third-party webhook; validated at runtime
// by `assertConfigShape` right below, so the cast is safe here.
const config = raw as unknown as Config;
assertConfigShape(config);
```

```javascript
// Bad -- venting
// this whole module is a disaster, don't touch it
function legacyExport() { ... }

// Good -- same information, professional and useful to the next reader
// Untested and load-bearing for the nightly export job. Changes here
// need a manual run against staging data before merging (see RUNBOOK.md#export).
function legacyExport() { ... }
```

```javascript
// Bad -- explains what a one-liner obviously does
// call the API and get the response
const res = await fetch(url);

// Good -- explains a non-obvious choice
// Retries are handled by the caller (see withRetry); this fetch is
// intentionally bare so failures propagate immediately.
const res = await fetch(url);
```

## React (JSX / TSX)

```tsx
// Bad -- comment restates what JSX already shows
function UserCard({ user }: { user: User }) {
  return (
    <div>
      {/* render the user's name */}
      <span>{user.name}</span>
    </div>
  );
}

// Good -- no comment needed, the JSX is the documentation
function UserCard({ user }: { user: User }) {
  return (
    <div>
      <span>{user.name}</span>
    </div>
  );
}
```

```tsx
// Bad -- no explanation for a surprising dependency array
useEffect(() => {
  syncScrollPosition();
}, [route.key]);

// Good -- explains why this dependency, specifically, and why not others
useEffect(() => {
  // Re-sync on route.key (not pathname) so replacing the route with the
  // same path but a new key -- e.g. a "refresh" navigation -- still re-syncs.
  syncScrollPosition();
}, [route.key]);
```

```tsx
// Bad -- silently swallows the reason for a memo
const rows = useMemo(() => buildRows(data), [data]);

// Good, when the memo exists for a non-obvious reason
// Memoized because buildRows does an O(n^2) group-by; this list can be
// 5-10k rows on the largest customer accounts (see PERF-118).
const rows = useMemo(() => buildRows(data), [data]);
```

```tsx
// Bad -- documents props redundantly above the component
/**
 * name: the user's name
 * age: the user's age
 */
function Profile({ name, age }: { name: string; age: number }) { ... }

// Good -- types already say this; if the component needs docs, document
// the non-obvious contract instead
/** Renders nothing (returns null) until `age` is confirmed >= 13, per COPPA. */
function Profile({ name, age }: { name: string; age: number }) { ... }
```
