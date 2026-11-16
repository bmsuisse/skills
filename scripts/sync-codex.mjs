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
 *  - `hooks` carry over in the shape Codex wants (`{ hooks: { <event>: [...] } }`). Matcher groups for tools that only
 *    exist in Claude Code (EnterWorktree) are dropped, and the file-edit tools (Edit, Write, ...) also match Codex's
 *    `apply_patch`. The hook scripts themselves handle both agents. Codex runs plugin hooks only after the user has
 *    reviewed them (`/hooks`), or with `--dangerously-bypass-hook-trust`.
 *  - `agents` are dropped from the manifest: Codex cannot select agent files. Each agents/*.md instead becomes a
 *    dispatch card under skills/dev-workflow/references/codex-agents/ (see codex-agents.mjs), shipped with the skill.
 *  - `{ source: "github", repo }` becomes `{ source: "url", url }`, the only form Codex resolves for GitHub repos.
 */

import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "fs";
import { dirname, join, relative, resolve } from "path";
import { fileURLToPath } from "url";
import { buildCodexAgentCards } from "./codex-agents.mjs";

const root = resolve(fileURLToPath(new URL(".", import.meta.url)), "..");
const claudePath = join(root, ".claude-plugin", "marketplace.json");
const codexPath = join(root, ".agents", "plugins", "marketplace.json");
const cardsDir = join(root, "skills", "dev-workflow", "references", "codex-agents");

function toCodexSource(source) {
  if (source?.source === "github") return { source: "url", url: `https://github.com/${source.repo}.git` };
  return source;
}

const CLAUDE_ONLY_TOOLS = new Set(["EnterWorktree", "NotebookEdit", "MultiEdit"]);
const EDIT_TOOLS = new Set(["Edit", "Write"]);

/** Codex matcher for a Claude Code one: Claude-only tools are removed, edit tools gain `apply_patch`. */
function toCodexMatcher(matcher) {
  if (!matcher) return matcher;
  const tools = matcher.split("|");
  const kept = tools.filter((tool) => !CLAUDE_ONLY_TOOLS.has(tool));
  if (kept.some((tool) => EDIT_TOOLS.has(tool))) kept.unshift("apply_patch");
  return kept.join("|");
}

function toCodexHooks(hooks) {
  const events = {};
  for (const [event, groups] of Object.entries(hooks ?? {})) {
    const kept = groups
      .map((group) => ({ ...group, matcher: toCodexMatcher(group.matcher) }))
      .filter((group) => group.matcher !== "");
    if (kept.length > 0) events[event] = kept;
  }
  return Object.keys(events).length > 0 ? { hooks: events } : undefined;
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
      const hooks = toCodexHooks(plugin.hooks);
      if (hooks) entry.hooks = hooks;
      return entry;
    }),
  };
}

const expected = `${JSON.stringify(buildCodexMarketplace(JSON.parse(readFileSync(claudePath, "utf8"))), null, 2)}\n`;
const expectedCards = buildCodexAgentCards(join(root, "agents"));
const show = (path) => relative(root, path);

/** Paths (relative to the repo) of generated files that are missing, stale or no longer wanted. */
function outOfSync() {
  const bad = [];
  if (!existsSync(codexPath) || readFileSync(codexPath, "utf8") !== expected) bad.push(show(codexPath));
  for (const [name, content] of Object.entries(expectedCards)) {
    const path = join(cardsDir, name);
    if (!existsSync(path) || readFileSync(path, "utf8") !== content) bad.push(show(path));
  }
  for (const name of existsSync(cardsDir) ? readdirSync(cardsDir) : []) {
    if (!(name in expectedCards)) bad.push(show(join(cardsDir, name)));
  }
  return bad;
}

if (process.argv.includes("--check")) {
  const bad = outOfSync();
  if (bad.length === 0) {
    console.log(`✅  ${show(codexPath)} and ${show(cardsDir)} are in sync with ${show(claudePath)} and agents/`);
  } else {
    console.error(`❌  Out of sync with ${show(claudePath)} / agents/:\n${bad.map((path) => `    ${path}`).join("\n")}`);
    console.error("    Run `node scripts/sync-codex.mjs` and commit the result.");
    process.exit(1);
  }
} else {
  mkdirSync(dirname(codexPath), { recursive: true });
  writeFileSync(codexPath, expected);
  rmSync(cardsDir, { recursive: true, force: true });
  mkdirSync(cardsDir, { recursive: true });
  for (const [name, content] of Object.entries(expectedCards)) writeFileSync(join(cardsDir, name), content);
  console.log(`Wrote ${show(codexPath)} and ${Object.keys(expectedCards).length} cards in ${show(cardsDir)}`);
}
