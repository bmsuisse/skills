# Translations (`translations.toml` + `just translate`)

Every BMS app (CCMT2, OneSales, MDMApp's akeneo_editor, and anything scaffolded by this skill) keeps UI text
in one `translations.toml` and generates the per-language JSON from it with
[`bdt translate`](https://github.com/bmsuisse/devtools#bdt-translate) (from `bmsdna-devtools`).

## The shared recipe

All apps expose the **same `just` recipe name**, so humans, agents and hooks never need to know the paths:

```just
# Generate frontend/src/locales/<lng>.json (git-ignored) from translations.toml.
# Add a key with `uv run bdt translate add KEY en=... de=... fr=... it=...`.
translate:
    uv run bdt translate
```

Wire it in as a dependency wherever the JSON is consumed, so it is never stale:

| Recipe               | How                                                              |
| -------------------- | ---------------------------------------------------------------- |
| `install`            | calls `just translate` after `bun install` (fresh clones/worktrees) |
| `frontend` / `dev-frontend`, `agent-preview`, `build` | `recipe: translate` dependency |
| `lint`               | `uv run bdt translate --check` (fails on stale files or `t("KEY")` missing from the toml) |

Where the files go is configuration, not recipe logic — it lives in `pyproject.toml`:

```toml
[tool.bdt.translate]
file = "translations.toml"
languages = ["en", "de", "fr", "it"]
output = ["frontend/src/locales"]   # MDMApp: ["akeneo_editor/frontend/src/locales"] with file = "akeneo_editor/translations.toml"
nested = true                       # "a.b.c" keys become nested JSON objects
scan = ["frontend/src"]             # t("KEY") usages are checked against the toml
```

The generated `frontend/src/locales/*.json` are **build artifacts**: git-ignore them, never hand-edit them.

## Adding a key

```bash
uv run bdt translate add SAVE en=Save de=Speichern fr=Enregistrer it=Salva
```

This writes `translations.toml` and regenerates the JSON in one go. Editing the toml by hand works too —
then run `just translate`.

## Regenerate on edit (Claude Code hook)

`hooks/translate_on_edit.py` is a `PostToolUse` hook (`Edit|Write`) that runs `just translate` whenever the
edited file is named `translations.toml`. If the recipe fails (for example a `t("KEY")` in code that the toml
doesn't define) it exits 2 with the output, so the agent fixes it right away. It does nothing for other files,
or when `just` or a `translate` recipe is missing. It only ever runs the justfile at `$CLAUDE_PROJECT_DIR`, and only for files inside that project.

`scripts/create.py` already copies it to `.claude/hooks/` and registers it in `.claude/settings.json`. For an
existing app, copy the file there and add:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{ "type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/translate_on_edit.py\"" }]
      }
    ]
  }
}
```

If the app already has a `PostToolUse` `Edit|Write` group (OneSales does), add the command to its `hooks`
list instead of a second group.
