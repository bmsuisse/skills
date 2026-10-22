# Azure DevOps branch policies

The build policy is what makes a PR build run (Azure Repos ignores YAML `pr:` triggers) and what blocks
the merge when it fails. Needs an authenticated `az` with the `azure-devops` extension.

## Audit first

```bash
az repos show -r <repo> --query defaultBranch -o tsv              # want refs/heads/dev
az repos policy list -r <repo> --branch dev  -o table             # repeat for test and main
az pipelines list --query "[].{id:id,name:name}" -o table         # the definition id to validate with
```

Each of `dev`, `test`, `main` should list a **Build** policy (blocking, enabled) and a **Minimum number
of reviewers** policy. Missing rows are the gaps to close.

## Close the gaps

```bash
REPO_ID=$(az repos show -r <repo> --query id -o tsv)
DEF_ID=<pipeline definition id>

az repos update -r <repo> --default-branch dev

for BRANCH in dev test main; do
  az repos policy build create --repository-id $REPO_ID --branch $BRANCH \
    --build-definition-id $DEF_ID --display-name "Build validation ($BRANCH)" \
    --blocking true --enabled true \
    --manual-queue-only false --queue-on-source-update-only false \
    --valid-duration 0 -o none

  az repos policy approver-count create --repository-id $REPO_ID --branch $BRANCH \
    --minimum-approver-count 1 --creator-vote-counts false --allow-downvotes false \
    --reset-on-source-push true --blocking true --enabled true -o none
done
```

Notes:
- `--valid-duration 0` means a passing build never goes stale by time alone; with
  `--queue-on-source-update-only false` the build is also re-queued when the target branch moves, so the PR
  was validated against the latest `dev`, not an old one.
- Don't add a `--path-filter` unless certain that PRs touching other paths need no build at all; a filtered
  policy lets those PRs merge without any build. If infra-only changes shouldn't trigger the app pipeline,
  point those paths at a separate pipeline with its own policy instead.
- One policy per (branch, pipeline) pair: re-running the loop creates duplicates. Check with
  `az repos policy list` first, and use `az repos policy update`/`delete` to change one.
- Raise the reviewer count on `main` (e.g. 2) if production changes need a stricter bar.
- The tests-skipped behaviour lives in the pipeline (`executeTests`), not in the policy, so all three
  branches use the *same* build definition.
- Merge strategy (`az repos policy merge-strategy create`): squash is fine for feature -> `dev`. Promotions
  (`dev` -> `test` -> `main`) should use a merge commit, not squash, otherwise the branches end up with
  the same content in different commits and every promotion conflicts again. Set it per branch.
