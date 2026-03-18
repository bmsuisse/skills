---
description: Add a new company skill to the skills repo
---

# Add a New Skill

Adds a new skill to all three required locations so it works with `npx skills add`, Antigravity, and Claude Code.

Replace `<skill-name>` with the actual skill name (lowercase, hyphenated).

1. Create the feature branch
```bash
git checkout -b skill/<skill-name>
```

2. Create the canonical skill directory (this is what `npx skills add` reads)
```bash
mkdir -p skills/<skill-name>
```

3. Create `skills/<skill-name>/SKILL.md` with YAML frontmatter and instructions.

// turbo
4. Sync to the Antigravity runtime directory
```bash
cp -r skills/<skill-name>/. .agents/skills/<skill-name>/
```

// turbo
5. Sync to the Claude Code runtime directory
```bash
cp -r skills/<skill-name>/. .claude/skills/<skill-name>/
```

6. Commit and push
```bash
git add skills/<skill-name> .agents/skills/<skill-name> .claude/skills/<skill-name>
git commit -m "feat(skills): add <skill-name> skill"
git push -u origin skill/<skill-name>
```

7. Open a PR and request review.

> **Tip:** After creating the SKILL.md draft, use the `skill-creator` skill to test and iterate before committing.
