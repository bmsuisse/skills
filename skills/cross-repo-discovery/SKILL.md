---
name: cross-repo-discovery
plugin: coding
description: >
  Find where a repo lives — locally or in the Azure DevOps org — before
  assuming a piece of functionality doesn't exist yet. Use this whenever the
  user asks about "other repos", "which repo has X", cross-repo/cross-service
  work, wants to find or clone a repo they don't have locally yet, or when
  you're stuck looking for code that isn't in the current repo and it might
  live elsewhere in the org. Trigger on things like "is there already a repo
  for this", "check across our other repos", "where's the shared X library",
  or "I don't think this exists yet, can you check devops".
compatibility: Requires `bdt` (bmsuisse-devtools), via `uvx --from bmsdna-devtools bdt` or a local `uv tool install`.
---

# Cross-repo discovery

Don't guess from one repo's contents whether something exists elsewhere in
the org. Look it up:

```bash
uvx --from bmsdna-devtools bdt find-repo <name>
```

This searches locally first (under `$AZDO_WORK_DIR`/`$BMS_WORK_DIR`, falling
back to `~/projects` or `C:/Projects`), then falls back to the Azure DevOps
org (`$AZDO_ORG`/`$BMS_ORG`) if there's no local match — offering to clone
it. Useful flags: `--yes` to clone a remote-only match without an interactive
prompt, `--org`/`--root` to override the env vars, `--pat` for an Azure
DevOps PAT if `az login` isn't set up.

If `bdt` is already installed locally (`uv tool list` includes
`bmsdna-devtools`), just run `bdt find-repo <name>` directly instead of the
`uvx --from` form.

Once you have the repo's path — existing or freshly cloned — read/search
there directly instead of reimplementing something that already exists
elsewhere in the org.
