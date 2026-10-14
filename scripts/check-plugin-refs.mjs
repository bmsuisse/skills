#!/usr/bin/env node
/**
 * Checks that everything `.claude-plugin/marketplace.json` references really exists.
 *
 * For every plugin with a local `source` (a path in this repo), relative to that plugin's root:
 *  - the source directory exists
 *  - every entry of `skills` is a directory containing a SKILL.md
 *  - every entry of `agents` / `commands` exists
 *  - every `${CLAUDE_PLUGIN_ROOT}/<path>` used by a hook command exists
 * Plugins fetched from elsewhere (github, git-subdir, ...) are skipped.
 */

import { existsSync, readFileSync, statSync } from "fs";
import { join, relative, resolve } from "path";
import { fileURLToPath } from "url";

const root = resolve(fileURLToPath(new URL(".", import.meta.url)), "..");
const marketplacePath = join(root, ".claude-plugin", "marketplace.json");

const PLUGIN_ROOT_VAR = /\$\{CLAUDE_PLUGIN_ROOT\}\/([^\s"'\\]+)/g;

function isDir(path) {
  return existsSync(path) && statSync(path).isDirectory();
}

/** Yield every hook `command` string anywhere inside a `hooks` object. */
function* hookCommands(node) {
  if (Array.isArray(node)) {
    for (const item of node) yield* hookCommands(item);
  } else if (node && typeof node === "object") {
    if (typeof node.command === "string") yield node.command;
    for (const value of Object.values(node)) yield* hookCommands(value);
  }
}

function checkPlugin(plugin) {
  const errors = [];
  if (typeof plugin.source !== "string") return errors; // remote source, not ours to check

  const pluginRoot = resolve(root, plugin.source);
  if (!isDir(pluginRoot)) {
    errors.push(`source "${plugin.source}" is not a directory`);
    return errors;
  }
  const show = (path) => relative(root, path) || ".";

  for (const skill of plugin.skills ?? []) {
    const dir = resolve(pluginRoot, skill);
    if (!isDir(dir)) errors.push(`skill "${skill}": ${show(dir)} is not a directory`);
    else if (!existsSync(join(dir, "SKILL.md"))) errors.push(`skill "${skill}": ${show(dir)}/SKILL.md is missing`);
  }

  for (const key of ["agents", "commands"]) {
    const entries = plugin[key] ?? [];
    for (const entry of Array.isArray(entries) ? entries : [entries]) {
      const path = resolve(pluginRoot, entry);
      if (!existsSync(path)) errors.push(`${key.slice(0, -1)} "${entry}": ${show(path)} does not exist`);
    }
  }

  for (const command of hookCommands(plugin.hooks)) {
    for (const [, rel] of command.matchAll(PLUGIN_ROOT_VAR)) {
      const path = resolve(pluginRoot, rel);
      if (!existsSync(path)) errors.push(`hook command: ${show(path)} does not exist`);
    }
  }
  return errors;
}

const marketplace = JSON.parse(readFileSync(marketplacePath, "utf8"));
let failed = 0;

for (const plugin of marketplace.plugins ?? []) {
  const errors = checkPlugin(plugin);
  if (errors.length === 0) {
    console.log(`✅  ${plugin.name}`);
    continue;
  }
  failed++;
  for (const error of errors) console.error(`❌  ${plugin.name}: ${error}`);
}

console.log(`\n${marketplace.plugins.length} plugins checked — ${failed} with broken references`);
if (failed > 0) process.exit(1);
