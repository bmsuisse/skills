# Secret detection with prek

Projects set up with this skill run two secret hooks, locally on commit and in CI on pull requests: `detect-secrets` (Yelp,
with a reviewed `.secrets.baseline`) and `detect-private-key`. This file holds the details the `prek` skill's Step 6 points to.

## Hooks (already in the Step 3 `prek.toml`)

- `detect-private-key` — prek `builtin`, no baseline support. If it fails on a committed key the app genuinely needs,
  exclude only that exact path in the hook (`exclude = "^path/to/key\\.pem$"`) with a `# TODO: move to a secret store and
  rotate` comment, and flag it. Never exclude a directory or a pattern.
- `detect-secrets` — `args = ["--baseline", ".secrets.baseline"]`. Always exclude lock files and generated data:
  `uv\.lock|bun\.lock|package-lock\.json|pnpm-lock\.yaml|yarn\.lock|\.lock\.json$|\.test_data\.json$|^\.secrets\.baseline$`
  (in a TOML basic string every backslash is doubled). Keep prek.toml line endings: several repos use CRLF.

## Baseline

detect-secrets has no extension filter: it entropy-scans every tracked text file, so one huge single-line JSON/CSV makes the
scan run 15+ minutes. Before scanning, list tracked files over ~800 KB and exclude generated or vendored data (big exports,
notebook outputs, `vendor/`, bundles, submodule dirs) in **both** the hook's `exclude` and the scan:

```bash
uvx detect-secrets scan --exclude-files '<same regex>' > .secrets.baseline     # run in the background, minutes on big repos
git add .secrets.baseline prek.toml                                             # the hook refuses an unstaged baseline
prek run --all-files detect-secrets && prek run --all-files detect-private-key
```

- Stage the baseline **before** `prek run`: with an unstaged baseline the hook errors and looks like it passed in 1 s.
- `git ls-files` quotes paths with umlauts/emoji (`"Bericht \303\274ber.json"`), and such files are silently skipped by a
  raw scan; verify with `prek run --all-files` and scan the stragglers separately.
- Prune excluded files out of the baseline JSON and add the pattern to its `filters_used` → `should_exclude_file`.
- Do not `pkill -f 'detect-secrets scan'`: it matches your own shell's command line.

### Triage (never print secret values)

Classify every finding by `file:line` and type. Harmless (mark `is_secret: false`): lock hashes, SRI integrity hashes, test
fixtures and placeholders, the public Azurite dev key, `pwd == "managed_identity"` comparisons, local-dev compose passwords,
Key Vault secret *names*. **Real-looking** (literal passwords or connection strings, API keys, tokens, committed private
keys): leave baselined as **unaudited** so they stay visible, list them (file:line + type, no values) in the PR under
"Needs a human decision", and recommend rotation. Never baseline a real secret as reviewed, and rotate anything that was
ever committed: history keeps it.

## justfile recipes

```just
# Re-scans for secrets and updates .secrets.baseline (the prek hook / CI flag anything not in it).
update-secrets-baseline:
    uvx detect-secrets scan --baseline .secrets.baseline

# Same check CI runs: detect-secrets + private-key detection over every tracked file.
check-secrets:
    uvx prek run --all-files detect-secrets
    uvx prek run --all-files detect-private-key
```

## CI step (Azure DevOps)

PR builds scan only the files the PR changed (a whole-repo scan takes minutes), the nightly/manual build scans everything,
push builds skip it (the code was scanned when it entered the integration branch, see `branching-strategy`). Put it in the
job that runs on PRs, after `uv` is installed (or install it: `curl -LsSf https://astral.sh/uv/install.sh | sh`):

```yaml
# Secret detection: files changed by the PR on PR builds, every tracked file in the nightly/manual run, nothing on push builds.
- script: |
    set -e
    case "$(Build.Reason)" in
      PullRequest)
        git -c http.extraheader="AUTHORIZATION: bearer $(System.AccessToken)" fetch --no-write-fetch-head origin "+refs/heads/$(System.PullRequest.TargetBranchName):refs/secret-scan/base"
        scope="--from-ref refs/secret-scan/base --to-ref HEAD" ;;
      Schedule|Manual) scope="--all-files" ;;
      *) echo "Not a PR or nightly/manual build: nothing to scan"; exit 0 ;;
    esac
    uvx prek run $scope detect-secrets
    uvx prek run $scope detect-private-key
  displayName: "Secret detection (prek)"
```

Rules learned the hard way:

- **Private ref + `--no-write-fetch-head`.** Other steps rely on `FETCH_HEAD` (database diff base, ruff/sqlfmt diffs); a plain
  `git fetch` would overwrite it. Do not use `--depth=N` where the checkout has full history (it makes the repo shallow and
  breaks the merge base); in a depth-1 checkout of the PR merge commit it is fine.
- **Force the ref (`+refs/heads/...:refs/secret-scan/base`).** Self-hosted agents keep their workspace between builds, so the
  ref from the previous build still exists; without the `+` the next fetch is rejected as non-fast-forward (always in a
  shallow checkout, where git cannot prove the new tip descends from the old one) and the step fails after a few seconds.
- **No nightly `schedules:` entry** (or the PR job is skipped on pushes): the all-files case never runs. Add
  `IndividualCI` to the all-files case (small repos) or a scheduled job, and say so in the PR.
- **A PR build only exists if the target branch has a Build validation policy** (`bdt pr status` says "No build policy is
  configured ..."). Without it the step runs only after merge, and a finding blocks the deploy stage that depends on it.
- The agent needs outbound access to github.com (the `detect-secrets` hook repo is cloned) and astral.sh.
- Edit the YAML by exact anchor, never "the first `if [ \"$(Build.Reason)\"`": an existing step may already contain it. After
  editing, `git diff origin/<base> -- <pipeline>` must show only your added step.
- Existing prek steps that pin an old `prek==x.y` also run the new hooks on changed files; check they pass.

## CI step (GitHub Actions)

```yaml
- uses: actions/checkout@v4
  with: { fetch-depth: 0 }
- run: |
    if [ "${{ github.event_name }}" = "pull_request" ]; then scope="--from-ref origin/${{ github.base_ref }} --to-ref HEAD"; else scope="--all-files"; fi
    uvx prek run $scope detect-secrets
    uvx prek run $scope detect-private-key
```
