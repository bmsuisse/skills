# File size and duplication gates

Large files and copy-pasted code both make change expensive: you edit one copy
and forget the other, or scroll 1500 lines to find the part that matters. Both
are cheap to check by machine, so make them gates.

## File size

`scripts/check_file_size.py` (copy into the repo's `scripts/`). Limits per
extension, tests 1.5x (`test_*`, `*_test.py`, `conftest.py`, `*.spec.ts`, files under `tests/`),
generated and lock files skipped, a warning at 75% of the limit so growth is
visible before it blocks. Edit the `LIMITS` table to match the repo.

prek hook (see the `prek` skill for the surrounding file):

```toml
[[repos]]
repo = "local"
hooks = [
    { id = "check-file-size", name = "check file size", language = "system", entry = "python3 scripts/check_file_size.py", pass_filenames = true, types = ["text"] },
]
```

Adopting it in an existing repo: run `python3 scripts/check_file_size.py $(git ls-files)` once.
Files that already exceed a limit fail forever, so either raise that extension's
limit to just above the current maximum and ratchet it down over time, or list
the legacy files in a temporary `SKIP` set with a comment. Markdown has the
lowest limit (500) and long `SKILL.md`/docs files hit it: raise or exempt those
with a comment instead of splitting arbitrarily. Do not split a file
only to satisfy the number: extract a cohesive module (one reason to change) and
move its tests with it.

## Duplication

[`duplicatecode`](https://github.com/bmsuisse/duplicatecode) (static, offline by
default; Python, TS/JS, SQL, C#):

```sh
uvx duplicatecode scan . --skip-tests --exclude '**/generated/**' --fail-on-found   # CI gate
uvx duplicatecode scan <dir> --pairs --explain      # what differs between a pair: what to parameterize
uvx duplicatecode fragments <dir>                   # copied blocks inside different functions
git diff origin/main | uvx duplicatecode diff --repo .   # does this PR re-implement something that exists?
```

Start with the `diff` check on pull requests (only new code can fail it). CI needs
the base branch and enough history for a merge-base:

```sh
git fetch origin main   # or checkout with fetch-depth: 0
git diff origin/main...HEAD | uvx duplicatecode diff --repo .
```

Turn on the repo-wide `scan --fail-on-found` only once the existing groups are
fixed or excluded, otherwise it fails on pre-existing duplicates immediately.

Reading a report:

- Pairs that differ only in a literal or a call: one function with a parameter.
- Near-identical wrappers or adapters: delete one, they are shallow pass-throughs.
- Same business rule in several places: move it to one module that owns it.
- Two copies and no third: leave it (rule of three), unless the copy is a business rule.
- Tests, migrations and generated code duplicate by design: exclude them.

Never use `--embed openai|cohere` on code you may not upload; the defaults stay local.
