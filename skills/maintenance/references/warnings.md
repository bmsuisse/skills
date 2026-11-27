# maintenance: warnings

Build warnings nobody reads until they become errors: deprecations, ineffective dynamic imports, pytest warnings.
A build with warnings ends `partiallySucceeded` (Azure DevOps), which still passes branch policies and `succeeded()`
conditions, so nothing forces anyone to look. Needs `bdt` >= 1.10.0.

```bash
bdt pr status                          # a build/run with warnings shows "N Warnings (see with bdt pr warnings --build-id ID)"
bdt pr warnings --build-id <id>        # the warnings by step (also [BUILD_ID] [--pr-id N] [--run-id N] [--json])
```

Look at the latest builds of `dev` (and the nightly, see [nightly.md](nightly.md)), not only one. Per distinct warning:

1. **Fix it** at the source: update the call, import or dependency the tool complains about.
2. **Suppress it consciously** only when it is noise you can't fix (third-party, known upstream issue): a narrow
   filter (`filterwarnings` with the message, the tool's own ignore option), with a comment and an issue link
   (`bdt issue search --state all --since-days 0 "<keywords>"` first, no duplicates). Never a blanket ignore.
3. **Wrap the step if it is invisible**: a tool that only prints its warnings (vite/rolldown, pytest's warnings
   summary) never reaches `bdt pr warnings`. Run it as `bdt ci warnings -- <command>` in the pipeline: output and
   exit code pass through, the warnings are reported afterwards.
   `"$HOME/.local/bin/uv" run --only-group dev bdt ci warnings -- bun run build`

Report: builds checked, warnings per step, fixed / suppressed (why) / issue, steps wrapped.
