#!/usr/bin/env node
/**
 * Generates the Codex marketplace (`.agents/plugins/marketplace.json`) from the Claude Code one
 * (`.claude-plugin/marketplace.json`), which stays the single source of truth.
 *
 *   node scripts/sync-codex.mjs          write the Codex marketplace
 *   node scripts/sync-codex.mjs --check  fail if the committed file is out of date (used in CI)
 *
 * What carries over, and what does not:
 *  - Plugins that ship skills keep `name`, `description`, `source` and `skills`; Codex reads the same fields.
 *  - Plugins without skills (Claude Code mods such as `bdt-status`) are left out: Codex cannot use them.
 *  - `hooks` and `agents` are dropped. Codex plugin hooks only run after an interactive trust review,
 *    and its subagents are not Claude Code agent files, so the skills are the shared surface.
 *  - `{ source: "github", repo }` becomes `{ source: "url", url }`, the only form Codex resolves for GitHub repos.
 */

import { existsSync, mkdirSync, readFileSync, writeFileSync } from "fs";
import { dirname, join, relative, resolve } from "path";
import { fileURLToPath } from "url";

const root = resolve(fileURLToPath(new URL(".", import.meta.url)), "..");
const claudePath = join(root, ".claude-plugin", "marketplace.json");
const codexPath = join(root, ".agents", "plugins", "marketplace.json");

function toCodexSource(source) {
  if (source?.source === "github") return { source: "url", url: `https://github.com/${source.repo}.git` };
  return source;
}

/** A plugin is usable from Codex when it ships skills itself or is fetched from another repo. */
function isCodexPlugin(plugin) {
  return typeof plugin.source !== "string" || (plugin.skills?.length ?? 0) > 0;
}

function buildCodexMarketplace(claude) {
  return {
    name: claude.name,
    plugins: claude.plugins.filter(isCodexPlugin).map((plugin) => {
      const entry = { name: plugin.name, description: plugin.description, source: toCodexSource(plugin.source) };
      if (plugin.skills) entry.skills = plugin.skills;
      return entry;
    }),
  };
}

const expected = `${JSON.stringify(buildCodexMarketplace(JSON.parse(readFileSync(claudePath, "utf8"))), null, 2)}\n`;
const show = (path) => relative(root, path);

if (process.argv.includes("--check")) {
  const actual = existsSync(codexPath) ? readFileSync(codexPath, "utf8") : null;
  if (actual === expected) {
    console.log(`✅  ${show(codexPath)} is in sync with ${show(claudePath)}`);
  } else {
    console.error(`❌  ${show(codexPath)} is ${actual === null ? "missing" : `out of sync with ${show(claudePath)}`}.`);
    console.error("    Run `node scripts/sync-codex.mjs` and commit the result.");
    process.exit(1);
  }
} else {
  mkdirSync(dirname(codexPath), { recursive: true });
  writeFileSync(codexPath, expected);
  console.log(`Wrote ${show(codexPath)}`);
}
