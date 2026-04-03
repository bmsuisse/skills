---
name: scientific-revision
plugin: writing
description: Use this skill whenever the user wants to verify, revise, or improve a scientific essay, academic paper, or any written document. It checks citation consistency, verifies bibliography entries via CrossRef and Google Scholar/Semantic Scholar, and detects AI-generated writing patterns (slop). Trigger this skill whenever the user mentions 'check citations', 'verify references', 'scientific revision', 'revise essay', 'clean up writing', 'check for AI slop', 'improve writing quality', 'check google scholar', or 'review my paper', especially in academic or professional writing contexts.
---

# Scientific Revision Skill

This skill provides four tools for document review:

1. **Citation Checker** — cross-checks in-text citations against the bibliography
2. **CrossRef Verifier** — checks whether bibliography entries are real publications
3. **Scholar Verifier** — checks entries against Google Scholar (via `scholarly`) with Semantic Scholar as fallback
4. **Writing Quality Checker** — detects AI slop patterns, vague language, and terminology inconsistencies

Works with any document that has a bibliography/references section. Supports APA, MLA, Chicago, and language-native citation styles in **English, German, French, and Italian** — parenthetical and narrative styles.

## Scripts

All scripts live in `.agents/skills/scientific-revision/scripts/`. Pass the document path as the first argument; all scripts default to `docs/essay/essay.md` if omitted.

### 1. Citation Checker
```bash
python .agents/skills/scientific-revision/scripts/check_citations.py [path/to/document.md]
```
- Finds citations in text missing from bibliography — and **suggests alternatives** from the bibliography that might be the intended reference.
- Finds bibliography entries never cited in the text.

### 2. Bibliography Verification (CrossRef)
```bash
python .agents/skills/scientific-revision/scripts/verify_crossref.py [path/to/document.md]
```
- Queries the CrossRef API to verify each bibliography entry is a real publication.
- Generates a `citation_report.md` in the same directory as the input file.
- Books and software get medium confidence by default (not indexed in CrossRef).

### 3. Bibliography Verification (Google Scholar / Semantic Scholar)
```bash
python .agents/skills/scientific-revision/scripts/verify_scholar.py [path/to/document.md]
```
- Uses the Semantic Scholar API via `httpx` (no library dependency issues).
- Optionally cross-checks with Google Scholar via `scholarly` (install with `uv add scholarly`).
- Also reports **citation counts**, useful to gauge publication impact.
- Generates a `citation_report_scholar.md` in the same directory as the input file.
- Complement CrossRef: use both to catch entries that appear in one index but not the other.
- Set `SEMANTIC_SCHOLAR_API_KEY` env var for a free key that raises the rate limit.

### 4. Writing Quality Checker
```bash
python .agents/skills/scientific-revision/scripts/check_writing.py [path/to/document.md]
```
- Flags AI slop phrases (e.g., "delve into", "it is worth noting", "seamlessly", "leverage").
- Detects terminology inconsistencies (e.g., mixing "dataset" and "data set").
- Flags repetitive sentence/paragraph starters.
- Reports line numbers so issues are easy to locate.

## Supported Section Headers

The scripts auto-detect bibliography sections with any of these headings:
`References`, `Bibliography`, `Works Cited` (EN) · `Literaturverzeichnis`, `Literatur` (DE) · `Bibliographie`, `Références` (FR) · `Bibliografia`, `Riferimenti bibliografici`, `Opere citate` (IT)

## Workflow

When the user asks you to revise or verify their document, follow this sequence unless instructed otherwise:

1. **Check Citations**: Run `check_citations.py`. For each missing citation, review the suggested alternatives and ask the user if one of them is the intended reference. Report uncited bibliography entries too.

2. **Verify References (CrossRef)**: Run `verify_crossref.py`. Share the generated `citation_report.md` with the user, highlighting any low-confidence entries that may be hallucinated or incorrect.

3. **Verify References (Scholar)**: Run `verify_scholar.py`. Cross-reference the `citation_report_scholar.md` with the CrossRef results.
   - An entry flagged low by CrossRef but verified by Scholar (or vice-versa) warrants closer manual review.
   - Highlight citation counts for entries with zero citations — these may be obscure or fabricated.

4. **Check Writing Quality**: Run `check_writing.py`. For each flagged phrase or inconsistency, propose a concrete rewrite. Don't just list problems — offer the user improved versions of the flagged sentences.

After all four checks, give the user a concise summary of:
- Citation issues found and resolved
- Bibliography entries that could not be verified by either CrossRef or Scholar
- Any discrepancies between CrossRef and Scholar results
- Writing quality issues and suggested improvements
