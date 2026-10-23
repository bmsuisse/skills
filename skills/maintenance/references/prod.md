# maintenance: prod

What production says: errors in Application Insights, and whether the open issues already cover them. Read-only
on prod. The output is issues (and PRs for small clear fixes), never a prod change.

Needs `AZURE_RESOURCE_GROUP` and `AZURE_APP_INSIGHTS` (the repo's `.env` / README documents them; check with
`bdt env`, which doesn't print values) and `az login`.

```bash
bdt logs roles --minutes 1440                                   # cloud_RoleName values: backend, worker, ...
bdt logs tail --role <role> --minutes 1440 --level error        # raw errors, newest first
az monitor app-insights query --app "$AZURE_APP_INSIGHTS" -g "$AZURE_RESOURCE_GROUP" --offset 7d \
  --analytics-query "exceptions | summarize n=count(), last=max(timestamp) by cloud_RoleName, type, outerMessage | top 20 by n desc"
```

The `az` query needs `az extension add -n application-insights`. Failed requests and slow endpoints:
`requests | where success == false | summarize count() by name, resultCode | top 20 by count_ desc`,
`requests | summarize p95=percentile(duration, 95), n=count() by name | top 20 by p95 desc`.

## Triage

Group by root cause, not by message: the same bug shows up with different ids, users and timestamps. Per group
note count over the window, first/last seen, role, endpoint or task, and one representative stack trace.

- **Noise** (client disconnects, 401/404 from scanners, retried-and-succeeded transients): not an issue. If it
  floods the logs, lowering its level or filtering it is a small PR.
- **Real**: check the open issues *before* creating one, with synonyms and the exception type, not only the message:
  `bdt issue search --state all --since-days 0 "<exception type>"`, then by endpoint. Closed issues count too: a
  regression gets a comment on the old one or a new issue linking it.
- Already open: add a comment only if you have new facts (frequency, new endpoint). No "+1" comments.
- Not covered: `bdt issue create --title "..."` with count, window, representative trace, suspected cause. One
  issue per root cause.

Also list the open issues that look stale or already fixed (no hits in the logs for the window): don't close them
yourself, name them in the report.

## Fix

Only what is small and clear (a missing null check, an unhandled 404 turned into a 500). Follow `/dev-workflow`
with the issue's number in the PR; everything else stays an issue. Don't paste user data or secrets from the logs
into an issue.
