#!/usr/bin/env python3
"""Mine a repo's history for 'what the team corrected' signals. Prints a markdown digest.

usage: mine.py REPO [--ref origin/HEAD] [--since 2025-01-01] [--top 25] [--prs 0]
Git only by default (seconds). --prs N also pulls review comments of the last N completed PRs
via `az` (Azure DevOps only, minutes: opt in when the team really reviews in PR threads).
"""
import argparse, collections, json, re, subprocess, sys, urllib.parse
from concurrent.futures import ThreadPoolExecutor

CODE = re.compile(r"\.(py|ts|tsx|vue|js|jsx|sql|cs|php|yml|yaml|bicep|toml|sh)$")
NOISE = re.compile(r"(lock|\.min\.|/migrations?/|snapshots?/|generated|CHANGELOG|/(i18n|locales?)/|catalogs?/)", re.I)
TRAILER = re.compile(r"^(Co-Authored-By|Claude-Session|Signed-off-by|Related work items|Generated with)", re.I)
RULE_WORDS = re.compile(r"\b(root cause|regress\w*|silently|never|must not|mistake|wrong|instead of|workaround|code review|review found|again|forbid\w*|restore\w*)\b", re.I)
MECHANICAL = re.compile(r"\b(strict|biome|ruff|format\w*|lint\w*|bump|rename)\b", re.I)


def out(s=""):
    print(s, flush=True)


def run(*a):
    r = subprocess.run(a, capture_output=True, text=True)
    return r.stdout, r.stderr


def git(repo, *a):
    return run("git", "-C", repo, *a)[0]


def kind(s, body=""):
    m = re.match(r"(\w+)(\(.*?\))?!?:", s)
    if re.match(r"revert", s, re.I) or "This reverts commit" in body:
        return "revert"
    return m.group(1).lower() if m else "other"


def first_line(body):
    for l in body.splitlines():
        l = l.strip()
        if l and not TRAILER.match(l):
            return l[:220]
    return ""


def commits(repo, ref, since):
    """Unique-by-subject commits, newest first (cherry-picks onto dev/test/main count once)."""
    raw = git(repo, "log", ref, "--no-merges", "--format=%x01%h%x02%as%x02%s%x02%b%x03", "--name-only", *(["--since", since] if since else []))
    res, at = [], {}
    for block in raw.split("\x01")[1:]:
        head, _, files = block.partition("\x03")
        sha, date, subj, body = head.split("\x02", 3)
        fs = [f for f in files.split("\n") if f and CODE.search(f) and not NOISE.search(f)]
        c = (sha, date, subj, body, fs)
        if subj not in at:
            at[subj] = len(res); res.append(c)
        elif len(body) > len(res[at[subj]][3]):  # keep the copy that has the explanation
            res[at[subj]] = c
    return res


def header(repo, ref, cs):
    sha = git(repo, "rev-parse", "--short", ref).strip()
    tree = git(repo, "ls-tree", "-r", "--name-only", ref).splitlines()
    docs = [f for f in tree if re.search(r"(^|/)(AGENTS|CLAUDE)\.md$|(STANDARDS|CONSTITUTION)\.md$", f, re.I)][:8]
    kinds = collections.Counter(kind(c[2], c[3]) for c in cs)
    out(f"# History digest: {repo} @ {ref} ({sha})\n")
    out(f"{len(cs)} unique commits, {cs[-1][1]} .. {cs[0][1]}. Types: {dict(kinds.most_common(8))}")
    out("Agent docs on this ref: " + (", ".join(docs) or "none (bootstrap: nothing to dedupe against)") + "\n")


def reverts(repo, cs, top):
    out("## Reverts (something was wrong enough to undo)")
    n = 0
    for sha, date, subj, body, fs in cs:
        if kind(subj, body) != "revert":
            continue
        why = first_line(body)
        m = re.search(r"This reverts commit (\w+)", body)
        undone = git(repo, "log", "-1", "--format=%s", m.group(1)).strip() if m else ""
        out(f"- {sha} {date} {subj}" + (f"\n    why: {why}" if why and "This reverts" not in why else "") + (f"\n    undoes: {undone}" if undone and undone not in subj else ""))
        n += 1
        if n >= top:
            break
    if not n:
        out("(none: checked subjects and 'This reverts commit' bodies)")
    out()


def refactors(cs, top):
    """Newest-first would only show this month: take up to 3 per month, skip mechanical sweeps."""
    out("## Refactors (spread over the window, mechanical lint/format sweeps skipped)")
    per, n = collections.Counter(), 0
    for sha, date, subj, body, fs in cs:
        if kind(subj, body) != "refactor" or MECHANICAL.search(subj) or len(fs) > 60 or per[date[:7]] >= 3:
            continue
        per[date[:7]] += 1
        why = first_line(body)
        out(f"- {sha} {date} {subj}" + (f"\n    why: {why}" if why else ""))
        n += 1
        if n >= top:
            break
    out()


def rule_words(cs, top):
    out("## Commits whose message states a cause or rule (read these first)")
    n = 0
    for sha, date, subj, body, fs in cs:
        if kind(subj, body) in {"revert", "docs", "test", "chore"}:
            continue
        text = subj + "\n" + body
        hit = RULE_WORDS.search(text)
        if hit and len(first_line(body)) > 30:
            out(f"- {sha} {date} {subj}\n    {first_line(body)}")
            n += 1
            if n >= top:
                break
    out()


def hot_files(cs, top):
    c = collections.Counter(f for _, _, s, b, fs in cs if kind(s, b) in {"fix", "refactor"} for f in fs)
    out("## Files fixed/refactored most often (churn, not proof of a mistake)")
    for f, n in c.most_common(top):
        out(f"- {n}x {f}")
    out()


def reviews(repo, n):
    url = git(repo, "remote", "get-url", "origin").strip()
    m = re.match(r"https://[^/]*@?dev\.azure\.com/([^/]+)/([^/]+)/_git/([^/]+)", url)
    if not m:
        return "origin is not Azure DevOps (dev.azure.com https remote); use `gh api` for GitHub reviews"
    org, proj, name = (urllib.parse.unquote(x) for x in m.groups())
    base = f"https://dev.azure.com/{org}"
    so, se = run("az", "repos", "pr", "list", "--organization", base, "--project", proj, "--repository", name, "--status", "completed", "--top", str(n), "--query", "[].{id:pullRequestId,by:createdBy.id}", "-o", "json")
    try:
        prs = json.loads(so)
    except Exception:
        return f"az failed (not logged in / not installed?): {se.strip()[:200]}"

    def threads(pr):
        o, _ = run("az", "devops", "invoke", "--organization", base, "--area", "git", "--resource", "pullRequestThreads", "--route-parameters", f"project={proj}", f"repositoryId={name}", f"pullRequestId={pr['id']}", "--api-version", "7.1", "-o", "json")
        try:
            return pr, json.loads(o)["value"]
        except Exception:
            return pr, None

    found, failed = [], 0
    with ThreadPoolExecutor(8) as ex:
        for pr, ths in ex.map(threads, prs):
            if ths is None:
                failed += 1
                continue
            for th in ths:
                path = (th.get("threadContext") or {}).get("filePath", "")
                for c in th.get("comments", []):
                    txt = (c.get("content") or "").strip()
                    reviewer = (c.get("author") or {}).get("id") != pr["by"]
                    if c.get("commentType") == "text" and len(txt) > 40 and (path or reviewer):
                        found.append((pr["id"], path, txt.replace("\n", " ")[:300]))
    return found, failed, len(prs)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("repo"); p.add_argument("--ref", default="origin/HEAD"); p.add_argument("--since")
    p.add_argument("--top", type=int, default=25); p.add_argument("--prs", type=int, default=0)
    a = p.parse_args()
    cs = commits(a.repo, a.ref, a.since)
    if not cs:
        sys.exit("no commits found: check --ref/--since")
    header(a.repo, a.ref, cs)
    reverts(a.repo, cs, a.top)
    rule_words(cs, a.top)
    refactors(cs, a.top)
    hot_files(cs, a.top)
    if a.prs:
        r = reviews(a.repo, a.prs)
        out("## PR review comments (file-anchored or by someone other than the PR author)")
        if isinstance(r, str):
            out(f"(unavailable: {r})")
        else:
            found, failed, total = r
            out(f"{len(found)} comments from {total} PRs ({failed} PRs failed to load)")
            for pid, f, t in found[: a.top * 2]:
                out(f"- PR {pid} {f}: {t}")


main()
