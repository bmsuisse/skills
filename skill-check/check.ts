import { Glob, $ } from "bun";
import { mkdir, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";

// Define directories
const rootDir = join(import.meta.dir, "..");
const tmpDir = join(import.meta.dir, ".tmp-check");

// Clean and recreate temp output directory
await rm(tmpDir, { recursive: true, force: true });
await mkdir(tmpDir, { recursive: true });

const args = process.argv.slice(2);
const fileFilter = args.length > 0 ? args[0].replace(/\\/g, '/') : null;

// We want to scan the "skills" folder for Markdown files
const mdGlob = new Glob("**/*.md");

let fileMappings = new Map<string, string>();
let count = 0;

for await (const file of mdGlob.scan({ cwd: join(rootDir, "skills"), absolute: false })) {
  if (file.includes("-workspace")) {
    continue;
  }

  if (fileFilter && !file.replace(/\\/g, '/').includes(fileFilter)) {
    continue;
  }

  const fullPath = join(rootDir, "skills", file);
  const content = await Bun.file(fullPath).text();
  const lines = content.split('\n');

  let inBlock = false;
  let blockType = '';
  let blockStartLine = 0;
  let blockLines: string[] = [];
  let blockCounter = 0;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    // Match start of code blocks for vue, ts, typescript
    const startMatch = line.match(/^```(vue|ts|typescript)\b/i);
    const endMatch = line.match(/^```\s*$/);

    if (!inBlock && startMatch) {
      inBlock = true;
      blockType = startMatch[1].toLowerCase();
      // Normalize typescript to ts
      if (blockType === 'typescript') blockType = 'ts';
      // Record the actual line number the code begins at (to pad correctly)
      blockStartLine = i + 1;
      blockLines = [];
    } else if (inBlock && endMatch) {
      inBlock = false;
      blockCounter++;
      
      // Pad empty lines before code so error reporting matches the exact lines in the Markdown file!
      const padding = '\n'.repeat(blockStartLine);
      const outContent = padding + blockLines.join('\n');
      
      // Flatten the path structure to easily output files into .tmp-check folder
      const flatName = `skills_${file.replace(/[\/\\]/g, '_')}_block${blockCounter}.${blockType}`;
      const outPath = join(tmpDir, flatName);
      
      await writeFile(outPath, outContent);
      fileMappings.set(flatName, join("skills", file));
      count++;
    } else if (inBlock) {
      blockLines.push(line);
    }
  }
}

if (count === 0) {
  console.log("No Vue or TypeScript blocks found in any Markdown file.");
  process.exit(0);
}

// Generate the tsconfig for checking
const tsconfig = {
  compilerOptions: {
    target: "ESNext",
    module: "ESNext",
    moduleResolution: "bundler",
    strict: true,
    jsx: "preserve",
    allowJs: true,
    esModuleInterop: true,
    skipLibCheck: true,
    forceConsistentCasingInFileNames: true
  },
  include: ["**/*.ts", "**/*.vue"]
};

await writeFile(join(tmpDir, "tsconfig.json"), JSON.stringify(tsconfig, null, 2));

console.log(`🔍 Extracted ${count} Vue/TS blocks. Running vue-tsc...`);

// Run vue-tsc gracefully
const run = await $`bunx vue-tsc --noEmit -p tsconfig.json`.cwd(tmpDir).nothrow().quiet();

let output = run.stdout.toString() + run.stderr.toString();

// Replace the temporary file names in output with the original Markdown paths
for (const [flatName, originalName] of fileMappings) {
  // Regex to exactly match filename in the tsc output
  const regex = new RegExp(flatName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g');
  output = output.replace(regex, originalName);
}

if (output.trim()) {
  console.log(output);
}

if (run.exitCode !== 0) {
  console.error("❌ Type checking failed! Please fix the errors in your Markdown files listed above.");
  process.exit(1);
} else {
  console.log("✅ All Markdown code blocks are beautifully typed.");
}
