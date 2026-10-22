# Pipeline snippets (Azure Pipelines YAML)

Adapt names (stages, environments, folders) to the repo; the logic is what matters. Read `SKILL.md` first
for why each piece exists.

## Contents
- Triggers and the nightly schedule
- `executeTests`: skip tests on promotion PRs
- `Plan` stage: PR labels -> areas
- Unit and E2E stages run the selected areas
- Guard: what may target `main` / `test`
- Deploy stage conditions

## Triggers and the nightly schedule

```yaml
# Pushes to test/main = a promotion just merged: build + deploy only (tests already ran).
# No CI trigger on dev: every change reached it through a PR build, and the nightly covers the rest.
trigger:
  branches:
    include: [main, test]

# Azure Repos Git ignores `pr:` here -- PR builds come from branch policies (azure-devops-policies.md).
# Keep a `pr:` block only if the repo is also on GitHub.

schedules:
  - cron: "0 5 * * *"          # UTC; pick a quiet hour
    displayName: "Nightly: full tests on dev, then deploy dev to test"
    branches:
      include: [dev]
    always: true               # run without changes: environment/data/dependency drift breaks tests too
```

## `executeTests`: skip tests on promotion PRs

Both ends in the long-lived set means "already tested"; anything else is new code. `Schedule` always runs
everything and deploys to the test environment. PR variables only exist at runtime, hence `$[ ]`.

```yaml
variables:
  ${{ if eq(variables['Build.Reason'], 'Schedule') }}:
    executeTests: true          # nightly: everything
    deployTarget: Test
  ${{ elseif eq(variables['Build.SourceBranchName'], 'main') }}:
    executeTests: false         # push after merge: deploy only
    deployTarget: Production
  ${{ elseif eq(variables['Build.SourceBranchName'], 'test') }}:
    executeTests: false
    deployTarget: Test
  ${{ else }}:                  # PR builds (source branch name is 'merge' here)
    deployTarget: None
    executeTests: $[ not(and(
      in(variables['System.PullRequest.SourceBranch'], 'refs/heads/dev', 'refs/heads/test', 'refs/heads/main'),
      in(variables['System.PullRequest.TargetBranch'], 'refs/heads/dev', 'refs/heads/test', 'refs/heads/main'))) ]
```

Test stages carry `condition: and(succeeded(), eq(variables.executeTests, true))`. Build, lint and
type-check stages stay unconditional so the build policy has something real to verify.

## `Plan` stage: PR labels -> areas

One place decides the areas; the unit and E2E stages both consume the result, so the two tiers can never
disagree. Areas are the union of the folder names under `tests/unit/` and `tests/e2e/`, so adding a folder
needs no pipeline edit.

```yaml
- stage: Plan
  jobs:
    - job: select
      steps:
        - checkout: self
        - script: |
            set -euo pipefail
            mapfile -t areas < <(find tests/unit tests/e2e -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null \
              | grep -v '^__' | sort -u)
            publish() { echo "Areas: $*"; echo "##vso[task.setvariable variable=areas;isOutput=true]$*"; exit 0; }

            [ "$EXECUTE_TESTS" = "True" ] || [ "$EXECUTE_TESTS" = "true" ] || publish ""           # promotion: nothing
            [ -z "${SYSTEM_PULLREQUEST_PULLREQUESTID:-}" ] && publish "${areas[@]}"                 # nightly: everything

            labels=$(curl -sS -f -u ":$SYSTEM_ACCESSTOKEN" \
              "$(System.CollectionUri)$(System.TeamProjectId)/_apis/git/repositories/$(Build.Repository.ID)/pullrequests/$SYSTEM_PULLREQUEST_PULLREQUESTID/labels?api-version=7.1") \
              && echo "$labels" | jq -e '.value' >/dev/null 2>&1 \
              || publish "${areas[@]}"                                  # can't read labels: fail safe to everything

            active() { echo "$labels" | jq -e --arg n "$1" '.value[]? | select(.name == $n and .active == true)' >/dev/null; }

            active test-full && publish "${areas[@]}"

            selected=()
            for a in "${areas[@]}"; do active "test-${a//_/-}" && selected+=("$a"); done

            if [ ${#selected[@]} -eq 0 ]; then
              echo "##vso[task.logissue type=error]PR has no 'test-<area>' label (or 'test-full'). Add one so CI knows which areas to run."
              exit 1
            fi
            publish "${selected[@]}"
          name: pick
          displayName: Select test areas from PR labels
          env:
            SYSTEM_ACCESSTOKEN: $(System.AccessToken)
            EXECUTE_TESTS: $(executeTests)
```

Needs `jq` on the agent; the build identity can read PR labels on its own repo by default. Failing here
(missing label) happens before any expensive stage starts.

## Unit and E2E stages run the selected areas

```yaml
- stage: Test
  dependsOn: Plan
  condition: and(succeeded(), eq(variables.executeTests, true))
  variables:
    areas: $[ stageDependencies.Plan.select.outputs['pick.areas'] ]
  jobs:
    - job: unit
      steps:
        - script: |
            paths=(); for a in $(areas); do [ -d "tests/unit/$a" ] && paths+=("tests/unit/$a"); done
            [ ${#paths[@]} -eq 0 ] && { echo "No unit tests for the selected areas"; exit 0; }
            uv run pytest "${paths[@]}"
          displayName: Unit tests (selected areas)

- stage: TestE2E
  dependsOn: [Plan, Build]
  condition: and(succeeded(), eq(variables.executeTests, true))
  variables:
    areas: $[ stageDependencies.Plan.select.outputs['pick.areas'] ]
  jobs:
    - job: e2e
      steps:
        - script: |
            paths=(); for a in $(areas); do [ -d "tests/e2e/$a" ] && paths+=("tests/e2e/$a"); done
            [ ${#paths[@]} -eq 0 ] && { echo "No e2e tests for the selected areas"; exit 0; }
            uv run pytest "${paths[@]}"
          displayName: E2E tests (selected areas)
```

Use the runner of the stack (`bun test`, `vitest`, ...) the same way. Parallelise across areas (a matrix
over `$(areas)`) when the suite is slow; the nightly then also finishes quickly.

## Guard: what may target `main` / `test`

First step of the build stage (always runs, also on skipped-test PRs). Enforces rule 7 and the
no-skipping rule. Fails the build, which blocks the PR through the policy.

```yaml
- script: |
    [ -z "${SYSTEM_PULLREQUEST_PULLREQUESTID:-}" ] && exit 0
    src="${SYSTEM_PULLREQUEST_SOURCEBRANCH#refs/heads/}"; dst="${SYSTEM_PULLREQUEST_TARGETBRANCH#refs/heads/}"
    case "$dst" in
      main) case "$src" in test|fix/*|hotfix/*) exit 0;; esac
            echo "##vso[task.logissue type=error]PRs into main are only allowed from 'test' (promotion) or fix/*, hotfix/* (fixes). Got '$src'."; exit 1;;
      test) case "$src" in dev|main) exit 0;; esac
            echo "##vso[task.logissue type=error]PRs into test must come from 'dev' (promotion). Got '$src'."; exit 1;;
    esac
  displayName: Guard branch flow
```

`main` as a source into `test` covers a fix on `main` that must reach `test` before the next promotion;
drop it if the `main` -> `dev` back-merge should be the only return path. Match the prefixes to the repo's
branch naming.

## Deploy stage conditions

Deploy when the run is a push to `test`/`main` or a green nightly; never on PR builds.

```yaml
- stage: Deploy
  dependsOn: [Build, Test, TestE2E]          # skipped test stages count as satisfied
  condition: |
    and(not(failed()), not(canceled()),
        ne(variables.deployTarget, 'None'))
```

`not(failed())` instead of `succeeded()` is deliberate: `succeeded()` is false when a dependency was
skipped, and test stages are skipped on `test`/`main` pushes. Production deploys additionally go through an
environment approval, independent of this model.
