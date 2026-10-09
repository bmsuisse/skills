# Finding duplicates with `duplicatecode`

[`duplicatecode`](https://github.com/bmsuisse/duplicatecode) (BMS tool) finds
duplicate or similar code in Python, TypeScript/JavaScript, SQL and C#. It is
static and offline by default (tree-sitter, no LLM, no network). Use it as hard
evidence for the explore step: duplicated knowledge across modules is a strong
signal that a seam is missing or in the wrong place.

Run without installing: `uvx duplicatecode ...` (or `uv tool install duplicatecode`).

## Commands worth running

```sh
# Groups of similar units; start here. Skip tests, they duplicate by design.
duplicatecode scan . --skip-tests --exclude '**/generated/**'

# Say what differs between each pair: what to parameterize
duplicatecode scan <hot-spot-dir> --pairs --explain

# Re-implementations that share few tokens (renamed, restructured)
duplicatecode scan . --profile reimpl --skip-tests

# Copied blocks inside different functions
duplicatecode fragments <dir> --min-stmts 4

# Machine-readable, for building the report
duplicatecode scan . --skip-tests --json
```

`duplicatecode diff --repo . < change.diff` checks a diff against the existing
repo, which is the right tool when the question is "did we just re-implement
something that already exists?".

## Reading the results as architecture signals

- **Same logic in several modules** = the decision lives in no single place.
  Candidate: one deep module that owns it (locality).
- **Near-identical wrappers or adapters** = shallow pass-throughs. Run the
  deletion test on them.
- **Pairs differing only in a literal or a call** (`--explain`) = a missing
  parameter, not a missing module. Don't over-engineer: the fix may be one
  function with an argument.
- **Duplicates only across two files, no third** = apply the rule of three;
  list it as `Speculative`, not `Strong`.
- Generated code, tests and migrations are usually noise; exclude them.

## Cautions

- The default run is offline. `--embed openai|cohere` or any hosted
  `--embeddings` endpoint uploads source text to that provider. Don't use them
  on client code without the user's explicit approval. Local presets
  (`--embed` with ollama `embeddinggemma`) stay on the machine.
- A match is a candidate to judge, not a verdict. Read both units before
  putting them in the report.
- `find "<description>" <paths>` needs embeddings, so treat it as opt-in.
