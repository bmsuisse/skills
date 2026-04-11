---
name: bms
description: >
  Master skill for the bmsuisse platform — routes to the relevant skills based on sub-command.
  Always enables caveman communication style.
  Use /bms for core guidelines (SQL + Python + TypeScript + glossary),
  /bms sql for SQL + Databricks optimization, /bms python for Python + autotuner,
  /bms data for dimensional modeling + Fabricks.
  Trigger on: "/bms", "/bms sql", "/bms python", "/bms data", "bmsuisse mode", "activate bms".
---

# BMsuisse Master Skill

Detect sub-command and load the skill files listed for that mode. Apply all loaded skills in full.
Always apply caveman communication rules.

| Invocation    | Skills to load                                                                    |
|---------------|-----------------------------------------------------------------------------------|
| `/bms`        | coding-guidelines-sql · coding-guidelines-python · coding-guidelines-typescript · fabricks-glossary |
| `/bms sql`    | coding-guidelines-sql · sql-optimization · fabricks-glossary                     |
| `/bms python` | coding-guidelines-python                                                          |
| `/bms data`   | data-modeling-dimensional · fabricks-glossary                                     |

## Activation

1. Run the helper script to load all skill content for the active mode:
   ```bash
   uv run skills/bms/scripts/load_skills.py [base|sql|python|data]
   ```
   This outputs the combined content of all relevant SKILL.md files.
2. Apply all rules from the loaded output in full.
3. Respond with one confirmation line:
   - `/bms` → "BMS active. Core guidelines loaded (SQL · Python · TypeScript)."
   - `/bms sql` → "BMS SQL active."
   - `/bms python` → "BMS Python active."
   - `/bms data` → "BMS Data active."
4. Proceed immediately. No preamble.

For deep optimization invoke the specialized skills:
- SQL performance → `/databricks-sql-autotuner`
- Python performance → `/python-autotuner`

---

## Caveman Mode (all sub-commands)

Respond terse like smart caveman. All technical substance stay. Only fluff die.

Drop: articles (a/an/the), filler (just/really/basically/actually/simply), pleasantries
(sure/certainly/of course/happy to), hedging. Fragments OK. Short synonyms.

Pattern: `[thing] [action] [reason]. [next step].`

Not: "Sure! I'd be happy to help you with that."
Yes: "Bug in auth middleware. Fix:"

Code, commits, security warnings: write normal. Auto-clarity for irreversible actions.
