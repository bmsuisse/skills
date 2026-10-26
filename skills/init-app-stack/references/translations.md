# Translations (`translations.toml` + `bdt translate`)

Every BMS app (CCMT2, OneSales, MDMApp's akeneo_editor, and anything scaffolded by this skill) keeps UI text
in one `translations.toml` and generates the per-language JSON from it with
[`bdt translate`](https://github.com/bmsuisse/devtools#bdt-translate) (from `bmsdna-devtools`).

## Running it

Call `bdt` directly. There is no `just translate` wrapper to keep in sync across repos:

```bash
uv run bdt translate                 # generate <lng>.json from translations.toml
uv run bdt translate --check         # CI/lint: fail on stale files or t("KEY") missing from the toml
uv run bdt translate add SAVE en=Save de=Speichern fr=Enregistrer it=Salva   # add a key + regenerate
```

Run it wherever the JSON is consumed, so it is never stale: in `just install` (fresh clones/worktrees), before
the frontend dev server / `agent-preview` / build, and as `--check` in lint.

Where the files go is configuration, not command logic — it lives in `pyproject.toml`:

```toml
[tool.bdt.translate]
file = "translations.toml"
languages = ["en", "de", "fr", "it"]
output = ["frontend/src/locales"]   # MDMApp: ["akeneo_editor/frontend/src/locales"] with file = "akeneo_editor/translations.toml"
nested = true                       # "a.b.c" keys become nested JSON objects
scan = ["frontend/src"]             # t("KEY") usages are checked against the toml
```

The generated `frontend/src/locales/*.json` are **build artifacts**: git-ignore them, never hand-edit them.

## Regenerate on edit (Claude Code hook)

`hooks/translate_on_edit.py` is a `PostToolUse` hook (`Edit|Write`) that runs `uv run bdt translate` whenever
the edited file is named `translations.toml`. If it fails (for example a `t("KEY")` in code that the toml
doesn't define) it exits 2 with the output, so the agent fixes it right away. It does nothing for other files,
or when `uv` or `[tool.bdt.translate]` in the project's `pyproject.toml` is missing. It only ever runs in
`$CLAUDE_PROJECT_DIR`, and only for files inside that project.

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
