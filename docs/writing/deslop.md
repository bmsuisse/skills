---
title: Remove AI Slop
description: Detect and fix AI writing patterns in code and PRs — unnecessary verbosity, filler phrases, over-engineering.
---

# Remove AI Slop

**Skill:** `deslop` · **Plugin:** `writing@bmsuisse-skills`

Cleans up AI-generated code and text — removes unnecessary verbosity, filler phrases, over-engineering, and pattern-matching without understanding.

## Invoke

```
/deslop
```

Then paste the code, PR description, or text to clean.

## What it targets

**In code:**

- Docstrings that just restate the function name
- Comments explaining what the code does (not why)
- Abstractions introduced before they're needed
- Error handling for scenarios that can't happen
- Feature flags, backwards-compat shims, and defensive code for hypothetical future requirements
- `# This was added to handle X` — belongs in the commit message, not the code

**In text / PRs:**

- Opening filler: "Certainly!", "Great question!", "I'd be happy to..."
- Hedging: "It's worth noting that", "It's important to mention"
- Padding: "In order to", "Due to the fact that", "At this point in time"
- AI tells: "leveraging", "utilize", "ensure", "robust", "seamlessly"

## Examples

```python
# ❌ AI slop
def calculate_discount(amount: float, percent: float) -> float:
    """
    Calculates the discount amount based on the provided amount and percentage.
    
    Args:
        amount: The original amount
        percent: The discount percentage (0-100)
    
    Returns:
        The calculated discount amount
    """
    # Calculate the discount by multiplying amount by percent divided by 100
    discount = amount * (percent / 100)
    return discount

# ✅ After deslop
def calculate_discount(amount: float, percent: float) -> float:
    return amount * (percent / 100)
```
