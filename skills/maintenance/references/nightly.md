# maintenance: nightly

Failures of the scheduled build on `dev` (the nightly full-suite run, see `branching-strategy`). It is the safety
net for per-area PR testing, so a red nightly is a real signal: a change that was only tested for its own area
broke something else, or the environment drifted.

```bash
# Azure DevOps
az pipelines runs list --branch dev --reason schedule --top 14 --query-order QueueTimeDesc \
  --query "[].{id:id, result:result, finish:finishTime, commit:sourceVersion}" -o table
az devops invoke --area build --resource timeline --route-parameters project=<project> buildId=<id> \
  --query "records[?result=='failed'].{name:name, type:type, issues:issues[].message}"

# GitHub
gh run list --branch dev --event schedule --limit 14
gh run view <id> --log-failed
```

Look at the last two weeks, not only last night: one red run is an incident, the same job red on 4 of 14 runs is flaky
(see [tests.md](tests.md)). Compare the commit range between the last green and the first red run
(`git log <green>..<red> --oneline`): the culprit is nearly always in there, unless nothing changed, then it is
data, a dependency release or an expired secret/token.

Per distinct failure (same test or step, same cause):

1. **Already known?** `bdt issue search --state all --since-days 0 "<test or step name>"`. Open: comment with the run
   link only if it adds something. No duplicates.
2. **Broken by a commit**: issue naming the commit and its PR, and tag the PR's author. If the fix is obvious, a
   `fix/` PR into `dev` per `/dev-workflow`, with the label of the failing area.
3. **Environment/dependency/secret**: issue with the evidence (log lines, the release or expiry date).
4. **Flaky** (passes on re-run, no relevant commit): issue, then handle it in `tests`. Don't just re-run the build
   and call it green.

Don't mute a nightly failure with `continue-on-error`, `xfail` or by deleting the test to get a green run.
Report: runs checked, green/red count, each failure with cause and issue link.
