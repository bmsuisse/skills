# maintenance: incident

`/maintenance incident <package | advisory url | news link>`: a named vulnerability or supply chain attack. Event-driven,
not part of `all`. Rule for the bump: see "never lock" in [SKILL.md](../SKILL.md).

1. **Identify**: ecosystem (PyPI/npm/Maven), package, affected range, fixed version, and whether it is a *vulnerable* release
   (fix arrives as a new version) or a *malicious* one (`MAL-` advisory, hijacked account, typosquat: the new version is
   the problem). Sources: OSV (`https://api.osv.dev/v1/vulns/<id>`), GitHub advisories, vendor write-ups (Socket,
   Aikido, StepSecurity); treat a blog as a lead, confirm in OSV/GHSA before acting.
2. **Relevance**: `bdt deps affected <package> [--version-spec "<x"] --path <repo> ...` over every repo we use. Per project:
   locked version in range? direct or transitive? runtime or dev group? Reachable code path? No match anywhere: say so,
   no PR.
3. **Vulnerable release**: take the exception flow in [audit.md](audit.md#fixes-younger-than-the-cooldown) (it works for
   a named advisory too: `bdt deps advisories` shows the status), one PR per project, link the advisory and the issue.
   Fast path for tests: whatever the repo's `bdt ci plan` allows; default is the full suite for a lock change.
4. **Malicious release**: don't upgrade first, **establish exposure**. Was the bad version locked, installed or executed
   (lockfile history, CI runs, dev machines, build caches and images)? Preserve evidence, then hand containment and
   credential rotation to the security incident process; the skill doesn't invent those steps. Remove/replace the
   package afterwards; never "fix" it with a pin.
5. **Close the loop**: `bdt issue create` for what can't be fixed now (search for duplicates first), and a short note on
   `bmsuisse/devtools#113` if the incident exposed a gap in this skill or in `bdt`.
