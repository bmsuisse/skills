# Azure DevOps branch policies

The build policy is what makes a PR build run (Azure Repos ignores YAML `pr:` triggers) and what blocks
the merge when it fails. Needs an authenticated `az` with the `azure-devops` extension.

## Audit first

```bash
az repos show -r <repo> --query defaultBranch -o tsv              # want refs/heads/dev
REPO_ID=$(az repos show -r <repo> --query id -o tsv)
az repos policy list --repository-id $REPO_ID --branch dev -o table   # repeat for test and main
az pipelines list --query "[].{id:id,name:name}" -o table         # the definition id to validate with
```

Each of `dev`, `test`, `main` should list a **Build** policy (blocking, enabled) and a **Minimum number
of reviewers** policy. Missing rows are the gaps to close. Also check the two environments (see
"Environment approvals" below) in the web UI: **Pipelines -> Environments**.

## Close the gaps

```bash
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

## Environment approvals (`test` and `main`)

Branch policies gate what may merge; **environment approvals gate what may deploy**. They are separate
mechanisms and `test` and `main` need both. The reviewer policy above is the PR approval; this is a
human saying "yes, deploy it now".

The pipeline's deploy job names an environment (`Test` for `test` and the nightly, `Production` for `main`,
see `pipeline.md`). Configure the approvals on those environments, once, in the portal:

1. **Pipelines -> Environments -> `Test`** (and `Production`) -> **Approvals and checks** -> **+** ->
   **Approvals**.
2. Add the approvers (prefer a group over named people so the list survives people changing teams), set
   "Requester can approve" according to how strict the bar should be, and set a **timeout** (default is
   30 days; a day or less keeps stale deploys from piling up).
3. Optionally add **Branch control** on the environment, allowing only `refs/heads/main` (for
   `Production`) and `refs/heads/test` / `refs/heads/dev` (for `Test`), so no other branch can ever deploy
   there even if someone edits the YAML.

This is deliberately not scripted in the setup commands: environments are shared across pipelines and the
approver groups are a team decision. When adjusting an existing project, read what is there first
(**Environments -> <name> -> Approvals and checks**) and only add what is missing.

Consequence to decide on, not to ignore: the **nightly** also deploys to `Test`, so with approvals on
`Test` it pauses at the deploy job until someone approves (and is rejected when the timeout expires).
That is correct if a human should sign off on every deploy to `test`; if the nightly must run unattended,
give it its own environment (e.g. `Test-Nightly`, pointing at the same resources, without approvals) and
keep `Test` with approvals for the `dev` -> `test` promotions.
