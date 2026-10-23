# Pipeline snippets (Azure Pipelines YAML)

Adapt names (stages, environments, folders) to the repo; the logic is what matters. Read `SKILL.md` first
for why each piece exists.

## Contents
- Triggers and the nightly schedule
- `executeTests`: skip tests on promotion PRs
- `Plan` stage: PR labels -> areas
- Unit and E2E stages run the selected areas
- Guard: what may target `main` / `test`
- Deploy stage

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
  - cron: "0 3 * * *"          # UTC (03:00 UTC = 05:00 in UTC+2); pick a quiet hour, done before the workday starts
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
  # Nightly = the schedule, or a manual run on dev (so the whole nightly path can be tried on demand).
  # Compare full refs: Build.SourceBranchName is only the last path segment ('feature/main' -> 'main').
  ${{ if or(eq(variables['Build.Reason'], 'Schedule'), and(eq(variables['Build.Reason'], 'Manual'), eq(variables['Build.SourceBranch'], 'refs/heads/dev'))) }}:
    executeTests: true          # nightly: everything
    shouldDeploy: true
    environment: Test
  ${{ elseif and(eq(variables['Build.Reason'], 'IndividualCI'), eq(variables['Build.SourceBranch'], 'refs/heads/main')) }}:
    executeTests: false         # push after merge: deploy only
    shouldDeploy: true
    environment: Production
  ${{ elseif and(eq(variables['Build.Reason'], 'IndividualCI'), eq(variables['Build.SourceBranch'], 'refs/heads/test')) }}:
    executeTests: false
    shouldDeploy: true
    environment: Test
  ${{ else }}:                  # PR builds and manual runs elsewhere: never deploy
    shouldDeploy: false
    environment: Test           # unused, but must name a real environment
    executeTests: $[ not(and(
      in(variables['System.PullRequest.SourceBranch'], 'refs/heads/dev', 'refs/heads/test', 'refs/heads/main'),
      in(variables['System.PullRequest.TargetBranch'], 'refs/heads/dev', 'refs/heads/test', 'refs/heads/main'))) ]
```

A manual run on any other branch (no PR variables) falls into the last case and runs the tests, which is
what you want from a "does my branch pass" run.

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
            [ ${#areas[@]} -gt 0 ] || { echo "##vso[task.logissue type=error]No test areas found under tests/unit or tests/e2e"; exit 1; }
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
            uv run pytest --durations=20 --durations-min=1.0 "${paths[@]}"
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
            uv run pytest --durations=20 --durations-min=1.0 "${paths[@]}"
          displayName: E2E tests (selected areas)
```

`--durations=20 --durations-min=1.0` makes pytest print the 20 slowest tests (setup, call and teardown) at the
end of every run, leaving out anything under one second so the list stays short on a fast suite. Slow tests
show up in the build log and the nightly without anyone profiling. Keep it in the pipeline command
rather than in `addopts`, so local runs stay quiet. Use the runner of the stack (`bun test`, `vitest`, ...) the
same way. Parallelise across areas (a matrix over `$(areas)`) when the suite is slow; the nightly then also
finishes quickly.

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
      test) case "$src" in dev) exit 0;; esac
            echo "##vso[task.logissue type=error]PRs into test must come from 'dev' (promotion). Got '$src'."; exit 1;;
    esac
  displayName: Guard branch flow
```

Nothing else may target `test`, including `main`: a fix reaches `test` via the `main` -> `dev` back-merge
and the next `dev` -> `test` promotion. Fix branches are cut from `main` (see rule 7). Match the prefixes to
the repo's branch naming.

## Deploy stage

Deploy on a push to `test`/`main` or a green nightly; never on PR builds. Use a `deployment` job that names
an **environment**: that is what lets Azure DevOps attach approvals to it (next section's note; configured
in the environment, not in this YAML).

```yaml
- stage: Deploy
  dependsOn: [Build, Test, TestE2E]          # skipped test stages count as satisfied
  condition: and(not(failed()), not(canceled()), eq(variables.shouldDeploy, true))
  jobs:
    - deployment: DeployApp
      environment: ${{ variables.environment }}     # Test or Production; approvals live on these
      strategy:
        runOnce:
          deploy:
            steps:
              - script: echo deploy here
```

`not(failed())` instead of `succeeded()` is deliberate: `succeeded()` is false when a dependency was
skipped, and test stages are skipped on `test`/`main` pushes.

Approvals on `Test` and `Production` are set up once in the environment settings — see "Environment
approvals" in `azure-devops-policies.md`. They gate the deploy job only; they don't change anything above.
