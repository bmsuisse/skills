---
name: add-skill
description: Use this skill whenever the user wants to add, create, publish, or contribute a new skill to the bmsuisse/skills repository. Triggers on requests like "add a new skill", "create a skill", "publish a skill", "contribute a skill", or "how do I add a skill".
---

# Adding a New Skill to bmsuisse/skills

Follow these steps every time a new skill is contributed to the repo.

## Step 1 — Create a feature branch

```bash
git checkout main && git pull
git checkout -b skill/<skill-name>
```

## Step 2 — Scaffold the skill

Create the canonical directory under `skills/`:

```
skills/
└── <skill-name>/
    ├── SKILL.md          ← required
    ├── scripts/          ← optional: helper scripts (uv / Python)
    ├── references/       ← optional: reference docs the agent may load
    └── assets/           ← optional: templates, examples
```

### SKILL.md frontmatter (required)

```markdown
---
name: <skill-name>
description: What the skill does and when to trigger it. Be specific — this is how the agent decides whether to use the skill.
---
```

## Step 3 — Sync to runtime directories

After writing the skill, copy it into all three runtime locations so agents can use it immediately in this repo:

```bash
# Antigravity
cp -r skills/<skill-name> .agents/skills/<skill-name>
cp -r skills/<skill-name> .agent/skills/<skill-name>

# Claude Code
cp -r skills/<skill-name> .claude/skills/<skill-name>
```

> Runtime dirs (`.agent/`, `.agents/`, `.claude/`) are git-ignored — only `skills/` is tracked.

## Step 4 — Commit, push, and merge

```bash
git add skills/<skill-name> README.md
git commit -m "feat: add <skill-name> skill"
git push -u origin skill/<skill-name>
```

Then merge to `main` (fast-forward preferred):

```bash
git checkout main
git merge skill/<skill-name> --ff-only
git push
```

## Checklist

- [ ] Branch created (`skill/<skill-name>`)
- [ ] `skills/<skill-name>/SKILL.md` written with valid frontmatter
- [ ] Synced to `.agents/skills/`, `.agent/skills/`, `.claude/skills/`
- [ ] Committed and pushed
- [ ] README table auto-updated by CI after merge to `main`
- [ ] Merged to `main` and pushed
