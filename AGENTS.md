This repo is for skills of BMS.

To create one, use /skill-creator skill, to query complex pages use /playwright-cli

Save skills in ./skills folder in this repo.

To check that your skill contains correct typescript / vue code, use `cd skill-check && bun run check.ts <skill-name>`

The Codex marketplace `.agents/plugins/marketplace.json` is generated from `.claude-plugin/marketplace.json`: after editing the latter run `node scripts/sync-codex.mjs` and commit the result (CI runs it with `--check`).

Skills shall have SHORT descriptions
