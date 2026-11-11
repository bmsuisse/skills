# Pipeline snippets (Azure Pipelines YAML)

Adapt names (stages, environments, folders) to the repo; the logic is what matters. Read `SKILL.md` first
for why each piece exists.

## Contents
- Triggers and the nightly schedule
- `UV_NO_BUILD`: install wheels only
- Environment and deploy variables
- Plan stage: `bdt ci plan`
- Test stages consume the outputs
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

## `UV_NO_BUILD`: install wheels only

A top-level pipeline variable (it reaches every `uv` call, as an environment variable), so no command needs
its own `--no-build`.

```yaml
variables:
  # CI installs wheels only: a dependency without one for the pinned Python fails the build instead of compiling for minutes.
  - name: UV_NO_BUILD
    value: "1"
```

If the pipeline already has a `variables:` block, add the entry to it (the block in the next section is
written in mapping form; convert the block to list form, or put the variable in a variable template, when
mixing the two).

## Environment and deploy variables

Only the environment and deploy decisions stay compile-time; which tests run is `bdt ci plan`'s job (next
section). The nightly is the schedule, or a manual run on `dev` (so the whole nightly path can be tried on
demand). Compare full refs: `Build.SourceBranchName` is only the last path segment (`feature/main` -> `main`).

```yaml
variables:
  ${{ if or(eq(variables['Build.Reason'], 'Schedule'), and(eq(variables['Build.Reason'], 'Manual'), eq(variables['Build.SourceBranch'], 'refs/heads/dev'))) }}:
    shouldDeploy: true
    environment: Test
  ${{ elseif and(eq(variables['Build.Reason'], 'IndividualCI'), eq(variables['Build.SourceBranch'], 'refs/heads/main')) }}:
    shouldDeploy: true          # push after merge: deploy only
    environment: Production
  ${{ elseif and(eq(variables['Build.Reason'], 'IndividualCI'), eq(variables['Build.SourceBranch'], 'refs/heads/test')) }}:
    shouldDeploy: true
    environment: Test
  ${{ else }}:                  # PR builds and manual runs elsewhere: never deploy
    shouldDeploy: false
    environment: Test           # unused, but must name a real environment
```

Test stages are gated by the plan outputs, not by these variables. Build, lint and type-check stages stay unconditional so the build policy has something real to verify.

## Plan stage: `bdt ci plan`

One step decides the tests (labels, inference from changed files, promotion skip, nightly = everything) and the
branch flow (what may target `main` / `test`, and that a fix branch was cut from `main`; a violation fails the
step, which blocks the PR through the policy). Every tier consumes the same result, so unit and E2E can never
disagree. Behaviour and config: "Test selection with `bdt ci plan`" in `SKILL.md`.

```yaml
- stage: Plan
  jobs:
    - job: plan
      steps:
        - checkout: self
          fetchDepth: 0                  # the fix-branch base check needs history (skipped with a warning when shallow)
        # ... install uv / sync as in the other stages
        - script: uv run bdt ci plan
          name: plan                     # required: the outputs are read as plan.<variable>
          displayName: Plan tests
          env:
            SYSTEM_ACCESSTOKEN: $(System.AccessToken)   # reads the PR labels
```

Outputs (`isOutput=true`): `runTests`, and per tier (`unit`, `e2e`, ...) `<tier>Run`, `<tier>Areas`, `<tier>Paths`
(a shell-quoted argument list for the runner). The repo pins `bmsdna-devtools>=0.50.0` as a **dev** dependency.

## Test stages consume the outputs

Gate on `<tier>Run` (`runTests` for a tier you don't split by area, e.g. flat unit tests) and pass `<tier>Paths`
to the runner. Never call the runner with empty paths: it would run everything.

```yaml
- stage: Test
  dependsOn: Plan
  condition: and(succeeded(), eq(dependencies.Plan.outputs['plan.plan.unitRun'], 'true'))
  variables:
    unitPaths: $[ stageDependencies.Plan.plan.outputs['plan.unitPaths'] ]
  jobs:
    - job: unit
      steps:
        - script: uv run pytest --maxfail=3 --durations=20 --durations-min=1.0 $(unitPaths)
          displayName: Unit tests (selected areas)

- stage: TestE2E
  dependsOn: [Plan, Build]
  condition: and(succeeded(), eq(dependencies.Plan.outputs['plan.plan.e2eRun'], 'true'))
  variables:
    e2ePaths: $[ stageDependencies.Plan.plan.outputs['plan.e2ePaths'] ]
  jobs:
    - job: e2e
      steps:
        - script: uv run pytest --maxfail=3 --durations=20 --durations-min=1.0 $(e2ePaths)
          displayName: E2E tests (selected areas)
```

`--maxfail=3` stops the run after the third failure, so a broken build doesn't burn agent time on the rest of the
suite. `--durations=20 --durations-min=1.0` prints the 20 slowest tests at the end of every run, leaving out
anything under one second, so slow tests show up in the build log and the nightly without anyone profiling. Keep
the flags in the pipeline command rather than in `addopts`, so local runs stay quiet and complete. Use the runner
of the stack (`bun test`, `vitest`, ...) the same way. Parallelise across areas (a matrix over `<tier>Areas`) when
the suite is slow; the nightly then also finishes quickly.

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
