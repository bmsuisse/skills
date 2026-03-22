"""Writing quality checker — detects AI slop patterns and consistency issues.

Scans a markdown document for:
  - Throat-clearing openers and emphasis crutches
  - AI buzzwords and business jargon
  - Weak transitions and meta-commentary
  - Adverb slop and vague declaratives
  - False agency (inanimate actors doing things)
  - Terminology inconsistencies

Languages: English, German, French, Italian
Patterns sourced from: references/slop_patterns.md (github.com/hardikpandya/stop-slop)

Usage:
    python scripts/check_writing.py [path/to/document.md]
"""

import re
import sys
from collections import Counter
from pathlib import Path


_PATTERNS_FILE = Path(__file__).parent.parent / "references" / "slop_patterns.md"


def _load_patterns(ref_path: Path) -> list[tuple[str, str, str]]:
    """Load slop patterns from references/slop_patterns.md.

    Format: ## Category (LANG) headers, then `- phrase` bullet items.
    Each phrase is compiled into a case-insensitive word-boundary regex.
    """
    patterns: list[tuple[str, str, str]] = []
    current_category = ""
    for line in ref_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("## "):
            current_category = line[3:].strip()
        elif line.startswith("- ") and current_category:
            phrase = line[2:].strip()
            if phrase:
                tail = r"\b" if phrase[-1].isalnum() or phrase[-1] == "_" else ""
                regex = r"\b" + re.escape(phrase) + tail
                patterns.append((current_category, phrase, regex))
    return patterns


_SLOP_PATTERNS = _load_patterns(_PATTERNS_FILE)


def _extract_body(text: str) -> str:
    """Return only the body text, excluding the bibliography section."""
    for i, line in enumerate(text.splitlines()):
        if re.match(
            r"^#+\s*(References|Bibliography|Works\s+Cited|Literaturverzeichnis|Literatur|Bibliographie|R[eé]f[eé]rences)",
            line, re.IGNORECASE,
        ):
            return "\n".join(text.splitlines()[:i])
    return text


def check_slop(body: str) -> list[tuple[str, str, list[int]]]:
    """Return list of (category, phrase, [line_numbers]) for each hit."""
    hits: list[tuple[str, str, list[int]]] = []
    lines = body.splitlines()
    for category, label, pattern in _SLOP_PATTERNS:
        rx = re.compile(pattern, re.IGNORECASE)
        line_nums = [i + 1 for i, line in enumerate(lines) if rx.search(line)]
        if line_nums:
            hits.append((category, label, line_nums))
    return hits


def check_terminology(body: str) -> list[tuple[str, list[str]]]:
    """Find terms used in multiple forms (e.g., 'data set' vs 'dataset').

    Returns list of (normalized_term, [variants_found]).
    """
    variant_groups: list[tuple[str, list[str]]] = [
        ("dataset",         [r"\bdataset\b", r"\bdata set\b", r"\bdata-set\b"]),
        ("machine learning",["r\bmachine learning\b", r"\bML\b"]),
        ("artificial intelligence", [r"\bartificial intelligence\b", r"\bAI\b"]),
        ("deep learning",   [r"\bdeep learning\b", r"\bDL\b"]),
        ("neural network",  [r"\bneural network\b", r"\bNN\b"]),
        ("Datenqualität",   [r"\bDatenqualität\b", r"\bDaten-Qualität\b"]),
        ("Maschinelles Lernen", [r"\bMaschinelles Lernen\b", r"\bML\b"]),
    ]

    inconsistencies: list[tuple[str, list[str]]] = []
    for term, patterns in variant_groups:
        found = [p.strip(r"\b") for p in patterns if re.search(p, body, re.IGNORECASE)]
        if len(found) > 1:
            inconsistencies.append((term, found))
    return inconsistencies


def check_sentence_starters(body: str) -> list[tuple[str, int]]:
    """Find paragraph-opening words used too often (signals formulaic structure)."""
    starters: list[str] = []
    for para in re.split(r"\n{2,}", body):
        sentences = re.split(r"(?<=[.!?])\s+", para.strip())
        if sentences and sentences[0]:
            first_word = re.match(r"\w+", sentences[0])
            if first_word:
                starters.append(first_word.group(0).lower())
    counts = Counter(starters)
    # Flag any starter used 3+ times
    return [(word, count) for word, count in counts.most_common() if count >= 3]


def main() -> None:
    essay_path = Path("docs/essay/essay.md")
    if len(sys.argv) > 1:
        essay_path = Path(sys.argv[1])

    text = essay_path.read_text(encoding="utf-8")
    body = _extract_body(text)

    slop_hits = check_slop(body)
    term_issues = check_terminology(body)
    starter_issues = check_sentence_starters(body)

    print("=" * 70)
    print("WRITING QUALITY REPORT")
    print("=" * 70)

    # Group slop by category
    by_category: dict[str, list[tuple[str, list[int]]]] = {}
    for cat, label, lines in slop_hits:
        by_category.setdefault(cat, []).append((label, lines))

    total_slop = sum(len(v) for v in by_category.values())
    print(f"\nAI slop patterns found: {total_slop}")
    print(f"Terminology variants:   {len(term_issues)}")
    print(f"Repetitive starters:    {len(starter_issues)}")

    if by_category:
        print(f"\n{'─' * 70}")
        print("AI SLOP PATTERNS:")
        print(f"{'─' * 70}")
        for category, entries in sorted(by_category.items()):
            print(f"\n  [{category}]")
            for label, line_nums in entries:
                nums = ", ".join(str(n) for n in line_nums[:5])
                suffix = " ..." if len(line_nums) > 5 else ""
                print(f"  x  \"{label}\"  — line{'s' if len(line_nums) > 1 else ''} {nums}{suffix}")
    else:
        print("\n  No common AI slop patterns detected.")

    if term_issues:
        print(f"\n{'─' * 70}")
        print("TERMINOLOGY INCONSISTENCIES:")
        print(f"{'─' * 70}")
        for term, variants in term_issues:
            print(f"  ? \"{term}\" — used in {len(variants)} forms: {', '.join(variants)}")
            print(f"    Pick one form and use it consistently throughout.")
    else:
        print(f"\n  No terminology inconsistencies detected.")

    if starter_issues:
        print(f"\n{'─' * 70}")
        print("REPETITIVE SENTENCE/PARAGRAPH STARTERS:")
        print(f"{'─' * 70}")
        for word, count in starter_issues:
            print(f"  ? \"{word}\" starts {count} paragraphs/sentences — vary your openings.")

    print()
    sys.exit(1 if slop_hits or term_issues else 0)


if __name__ == "__main__":
    main()
