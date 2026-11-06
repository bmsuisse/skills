#!/usr/bin/env python3
"""Find Azure cost spikes from the Cost Management Query API (read-only, stdlib + `az`).

One daily query (grouped by one dimension) over the last `--days` days, then per group:
mean daily cost of the most recent `--recent` complete days vs the median of the days before.
Today is excluded (cost data lags by hours and is always partial).

    python cost_spike.py                                    # current subscription, by ServiceName
    python cost_spike.py --resource-group rg-prod           # narrow the scope
    python cost_spike.py --group-by ResourceId --service Storage   # drill into one service
    python cost_spike.py --json
"""

import argparse
import json
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from datetime import date, timedelta

API = "2023-11-01"
MAX_DAILY_DAYS = 31  # Daily granularity ceiling of the Query API
RETRY_WAITS = (15, 30, 60)  # 4 req/min per scope: space the retries, max 3


def az_rest(url: str, body: dict | None = None) -> dict:
    cmd = ["az", "rest", "--method", "POST" if body else "GET", "--url", url, "-o", "json"]
    if body:
        cmd += ["--body", json.dumps(body)]
    for wait in (*RETRY_WAITS, None):
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if proc.returncode == 0:
            return json.loads(proc.stdout)
        throttled = "429" in proc.stderr or "Too Many Requests" in proc.stderr
        if not throttled or wait is None:
            sys.exit(f"az rest failed: {proc.stderr.strip()}")
        print(f"429 from Cost Management, waiting {wait}s", file=sys.stderr)
        time.sleep(wait)
    raise AssertionError("unreachable")


def current_subscription() -> str:
    proc = subprocess.run(
        ["az", "account", "show", "--query", "id", "-o", "tsv"], check=False, capture_output=True, text=True
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        sys.exit("no active subscription: run `az login` (or pass --scope)")
    return proc.stdout.strip()


def build_scope(args: argparse.Namespace) -> str:
    if args.scope:
        return args.scope.rstrip("/")
    scope = f"/subscriptions/{args.subscription or current_subscription()}"
    return f"{scope}/resourceGroups/{args.resource_group}" if args.resource_group else scope


def query_daily(
    scope: str, start: date, end: date, group_by: str, service: str | None, cost_type: str
) -> tuple[list[dict], str]:
    dataset: dict = {
        "granularity": "Daily",
        "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
        "grouping": [{"type": "Dimension", "name": group_by}],
    }
    if service:
        dataset["filter"] = {"dimensions": {"name": "ServiceName", "operator": "In", "values": [service]}}
    body = {
        "type": cost_type,
        "timeframe": "Custom",
        "timePeriod": {"from": start.isoformat(), "to": end.isoformat()},
        "dataset": dataset,
    }
    url: str | None = f"https://management.azure.com{scope}/providers/Microsoft.CostManagement/query?api-version={API}"
    records: list[dict] = []
    currency = ""
    while url:
        page = az_rest(url, body)
        props = page["properties"]
        names = [c["name"] for c in props["columns"]]
        for row in props["rows"]:
            rec = dict(zip(names, row))
            currency = rec.get("Currency", currency)
            records.append(rec)
        url = props.get("nextLink")
        body = body if url else None
        if url:
            time.sleep(5)
    return records, currency


def analyse(
    records: list[dict], group_by: str, start: date, last_day: date, recent: int, min_delta: float, ratio: float
) -> list[dict]:
    per_group: dict[str, dict[date, float]] = defaultdict(lambda: defaultdict(float))
    for rec in records:
        day = date.fromisoformat(_fmt(rec["UsageDate"]))
        if day <= last_day:
            per_group[rec[group_by] or "(none)"][day] += rec["Cost"]

    days = [start + timedelta(n) for n in range((last_day - start).days + 1)]
    recent_days, base_days = days[-recent:], days[:-recent]
    findings = []
    for name, costs in per_group.items():
        base = [costs.get(d, 0.0) for d in base_days]
        now = [costs.get(d, 0.0) for d in recent_days]
        base_med, now_mean = statistics.median(base), statistics.fmean(now)
        delta = now_mean - base_med
        is_new = base_med == 0 and sum(base) == 0
        if delta >= min_delta and (is_new or now_mean >= ratio * base_med):
            peak_day = max(recent_days, key=lambda d: costs.get(d, 0.0))
            findings.append(
                {
                    group_by: name,
                    "baseline_per_day": round(base_med, 2),
                    "recent_per_day": round(now_mean, 2),
                    "delta_per_day": round(delta, 2),
                    "ratio": None if is_new else round(now_mean / base_med, 1),
                    "new": is_new,
                    "peak_day": peak_day.isoformat(),
                    "daily": {d.isoformat(): round(costs.get(d, 0.0), 2) for d in days[-(recent + 7) :]},
                }
            )
    return sorted(findings, key=lambda f: f["delta_per_day"], reverse=True)


def _fmt(usage_date: int | str) -> str:
    s = str(usage_date)
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 and s.isdigit() else s[:10]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--scope", help="full scope path, e.g. /subscriptions/<id>/resourceGroups/<rg>")
    p.add_argument("--subscription", help="subscription id (default: az account show)")
    p.add_argument("--resource-group", help="narrow to one resource group (the repo's AZURE_RESOURCE_GROUP)")
    p.add_argument(
        "--group-by",
        default="ServiceName",
        help="ServiceName | ResourceGroupName | ResourceId | MeterCategory ... (default ServiceName; ResourceId needs subscription/RG scope)",
    )
    p.add_argument("--service", help="only this ServiceName (use with --group-by ResourceId)")
    p.add_argument("--days", type=int, default=31, help=f"window incl. baseline, max {MAX_DAILY_DAYS} (default 31)")
    p.add_argument("--recent", type=int, default=3, help="complete days compared against the baseline (default 3)")
    p.add_argument(
        "--min-delta", type=float, default=5.0, help="minimum increase per day in billing currency (default 5)"
    )
    p.add_argument(
        "--ratio", type=float, default=1.5, help="recent must be at least this multiple of baseline (default 1.5)"
    )
    p.add_argument("--cost-type", default="ActualCost", choices=["ActualCost", "AmortizedCost"])
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    if not 2 <= args.days <= MAX_DAILY_DAYS or not 1 <= args.recent < args.days:
        sys.exit(f"--days must be 2..{MAX_DAILY_DAYS} and --recent smaller than --days")
    last_day = date.today() - timedelta(days=1)
    start = last_day - timedelta(days=args.days - 1)
    scope = build_scope(args)

    records, currency = query_daily(scope, start, date.today(), args.group_by, args.service, args.cost_type)
    findings = analyse(records, args.group_by, start, last_day, args.recent, args.min_delta, args.ratio)
    total = defaultdict(float)
    for rec in records:
        total[_fmt(rec["UsageDate"])] += rec["Cost"]

    if args.json:
        json.dump(
            {
                "scope": scope,
                "currency": currency,
                "from": start.isoformat(),
                "to": last_day.isoformat(),
                "recent_days": args.recent,
                "spikes": findings,
                "total_per_day": {k: round(v, 2) for k, v in sorted(total.items())},
            },
            sys.stdout,
            indent=2,
        )
        print()
        return

    print(
        f"scope {scope}  {start} .. {last_day} ({args.cost_type}, {currency}), last {args.recent} days vs median of the rest"
    )
    if not findings:
        print("no spikes above thresholds")
        return
    print(f"{'group':60} {'baseline/d':>11} {'recent/d':>10} {'delta/d':>9} {'x':>6}  peak")
    for f in findings:
        mult = "new" if f["new"] else f"{f['ratio']}x"
        print(
            f"{str(f[args.group_by])[:60]:60} {f['baseline_per_day']:>11} {f['recent_per_day']:>10} {f['delta_per_day']:>9} {mult:>6}  {f['peak_day']}"
        )


if __name__ == "__main__":
    main()
