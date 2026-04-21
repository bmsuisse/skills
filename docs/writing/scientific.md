---
title: Scientific Revision
description: Verify, revise, and improve scientific essays and academic papers.
---

# Scientific Revision

**Skill:** `scientific-revision` · **Plugin:** `writing@bmsuisse-skills`

Revises scientific writing for clarity, precision, and correctness — without changing the author's voice or argument structure.

## Invoke

```
/scientific-revision
```

Then paste the text to revise.

## What it checks

- **Claim accuracy** — flags unsupported assertions, vague quantifiers ("many studies show"), and overclaiming
- **Precision** — tightens imprecise language ("significant improvement" → specific number)
- **Structure** — ensures each paragraph has one clear claim, evidence, and interpretation
- **Transitions** — logical flow between sections and paragraphs
- **Passive voice** — converts to active where it improves clarity
- **Hedging** — appropriate epistemic caution ("may suggest" vs. "proves")
- **Citation gaps** — flags claims that need a citation

## Output

Returns the revised text with tracked changes and a brief rationale for each edit.
