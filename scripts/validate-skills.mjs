#!/usr/bin/env node
/**
 * Validates all SKILL.md files in the skills/ directory.
 *
 * Checks:
 *  - Every skill folder contains a SKILL.md
 *  - Required frontmatter fields: name, description, plugin
 *  - `name` matches the folder name (lowercase-hyphens)
 *  - `plugin` is a known plugin from marketplace.json
 */

import { readFileSync, readdirSync, statSync } from "fs";
import { join, basename } from "path";
import { fileURLToPath } from "url";

const __dir = fileURLToPath(new URL(".", import.meta.url));
const root = join(__dir, "..");
const skillsDir = join(root, "skills");
const marketplacePath = join(root, ".claude-plugin", "marketplace.json");

// ── helpers ──────────────────────────────────────────────────────────────────

function parseFrontmatter(content) {
  const match = content.match(/^---\n([\s\S]*?)\n---/);
  if (!match) return null;
  const fields = {};
  for (const line of match[1].split("\n")) {
    // Skip continuation lines (YAML block scalars like `>`)
    if (line.startsWith(" ") || line.startsWith("\t")) continue;
    const colon = line.indexOf(":");
    if (colon === -1) continue;
    const key = line.slice(0, colon).trim();
    const value = line.slice(colon + 1).trim().replace(/^["']|["']$/g, "");
    if (key) fields[key] = value;
  }
  return fields;
}

function getSkillFolders() {
  return readdirSync(skillsDir).filter((entry) => {
    const full = join(skillsDir, entry);
    return statSync(full).isDirectory();
  });
}

function loadKnownPlugins() {
  const marketplace = JSON.parse(readFileSync(marketplacePath, "utf8"));
  const pluginMap = {}; // skillName → pluginName
  for (const plugin of marketplace.plugins ?? []) {
    for (const skillPath of plugin.skills ?? []) {
      const skillName = basename(skillPath);
      pluginMap[skillName] = plugin.name;
    }
  }
  return { pluginNames: marketplace.plugins.map((p) => p.name), pluginMap };
}

// ── validation ────────────────────────────────────────────────────────────────

const { pluginNames, pluginMap } = loadKnownPlugins();
const folders = getSkillFolders();

let errors = 0;
let warnings = 0;

for (const folder of folders) {
  const skillPath = join(skillsDir, folder);
  const skillFile = join(skillPath, "SKILL.md");

  let content;
  try {
    content = readFileSync(skillFile, "utf8");
  } catch {
    // No SKILL.md → workspace or non-skill folder, skip silently
    continue;
  }

  const fm = parseFrontmatter(content);
  if (!fm) {
    console.error(`❌  ${folder}: SKILL.md has no frontmatter`);
    errors++;
    continue;
  }

  const issues = [];

  // Required fields
  for (const field of ["name", "description", "plugin"]) {
    if (!fm[field]) issues.push(`missing required field: ${field}`);
  }

  // name must match folder
  if (fm.name && fm.name !== folder) {
    issues.push(`name "${fm.name}" doesn't match folder "${folder}"`);
  }

  // name must be lowercase-hyphens
  if (fm.name && !/^[a-z0-9-]+$/.test(fm.name)) {
    issues.push(`name "${fm.name}" must be lowercase letters, digits, and hyphens only`);
  }

  // plugin must be a known plugin
  if (fm.plugin && !pluginNames.includes(fm.plugin)) {
    issues.push(`plugin "${fm.plugin}" is not in marketplace.json (known: ${pluginNames.join(", ")})`);
  }

  // plugin should match marketplace.json mapping (cross-check)
  const expectedPlugin = pluginMap[folder];
  if (fm.plugin && expectedPlugin && fm.plugin !== expectedPlugin) {
    issues.push(
      `plugin "${fm.plugin}" doesn't match marketplace.json entry "${expectedPlugin}"`,
    );
  }

  // Skill not listed in marketplace.json at all
  if (!expectedPlugin) {
    console.warn(`⚠️   ${folder}: not listed in marketplace.json`);
    warnings++;
  }

  if (issues.length > 0) {
    for (const issue of issues) {
      console.error(`❌  ${folder}: ${issue}`);
    }
    errors++;
  } else {
    console.log(`✅  ${folder} (plugin: ${fm.plugin})`);
  }
}

console.log(
  `\n${folders.length} skills checked — ${errors} error(s), ${warnings} warning(s)`,
);
if (errors > 0) process.exit(1);
