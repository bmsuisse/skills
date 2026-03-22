"""Citation checker — cross-checks in-text citations vs bibliography.

Handles citation styles:
  - Parenthetical: (Author & Author, Year), (Author et al., Year)
  - Multi-citation: (Author, Year; Author & Author, Year)
  - Narrative two-author: Author and/und/et/e Author (Year)
  - Narrative et al.: Author et al. (Year)
  - Narrative single: Author (Year)
  - Organization/acronym: (DAMA International, 2017), (HLEG, 2019)

Languages: English, German, French, Italian
"""

import re
import sys
from pathlib import Path


_STOPWORDS = {
    # German
    "kapitel", "abbildung", "tabelle", "stufe", "schritt", "phase", "seit",
    "januar", "februar", "märz", "april", "mai", "juni", "juli", "august",
    "september", "oktober", "november", "dezember", "lag", "version", "stand",
    "regulation", "abschnitt", "abs", "quartal", "monat", "woche", "tag",
    "jahr", "kurzfristig", "mittelfristig", "langfristig",
    # English
    "figure", "table", "chapter", "section", "appendix", "equation", "exhibit",
    "january", "february", "march", "april", "june", "july",
    "september", "october", "november", "december", "version", "phase", "step",
    # French
    "janvier", "février", "mars", "avril", "juin", "juillet", "août",
    "chapitre", "tableau", "figure", "annexe", "paragraphe", "partie",
    "résumé", "étude", "introduction", "conclusion",
    # Italian
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "ottobre", "dicembre",
    "capitolo", "tabella", "sezione", "appendice", "paragrafo", "parte",
    "studio", "introduzione", "conclusione",
}


def _normalize_key(author_raw: str, year: str) -> str | None:
    """Normalize an author string + year into a comparable key."""
    author_raw = author_raw.strip()
    if not author_raw or author_raw[0].islower():
        return None

    if "et al" in author_raw:
        m = re.match(r"([A-ZÄÖÜÀÂÇÉÈÊËÎÏÔÛÙÜÌÒÚa-zäöüéèàâçêëîïôûùüìòú]+)", author_raw)
        return f"{m.group(1).lower()} et al., {year}" if m else None

    if "&" in author_raw:
        parts = [p.strip() for p in author_raw.split("&")]
        surnames = []
        for p in parts:
            words = [w for w in p.split() if w[0:1].isupper()]
            if words:
                surnames.append(words[-1].lower())
        if len(surnames) == 2:
            return f"{surnames[0]} & {surnames[1]}, {year}"
        if len(surnames) == 1:
            return f"{surnames[0]}, {year}"
        return None

    return f"{author_raw.lower()}, {year}"


def _fuzzy_match(key: str, candidates: set[str]) -> bool:
    """Check if key approximately matches any candidate by surname+year.

    Bidirectional: "dama international" matches "international" and vice versa,
    so multi-word org names extracted in different forms still link correctly.
    """
    parts = key.split(",")
    surname = parts[0].split("&")[0].split("et al")[0].strip()
    year = parts[-1].strip()
    for c in candidates:
        if year != c.split(",")[-1].strip():
            continue
        c_surname = c.split(",")[0].split("&")[0].split("et al")[0].strip()
        if surname in c_surname or c_surname in surname:
            return True
    return False


def extract_inline_citations(body: str) -> set[str]:
    """Extract all citation keys from body text. Returns normalized keys like 'author, year'."""
    citations: set[str] = set()

    for m in re.compile(r"\(([^)]+,\s*\d{4}(?:\s*;\s*[^)]+,\s*\d{4})*)\)").finditer(body):
        for part in re.split(r"\s*;\s*", m.group(1)):
            part = re.sub(
                r"^(?:vgl\.|siehe|e\.g\.,?|z\.B\.,?|cf\.|voir|ibid\.|op\.\s*cit\.|cfr\.)\s+",
                "", part.strip(), flags=re.IGNORECASE,
            )
            year_match = re.search(r",\s*(\d{4})$", part)
            if year_match:
                key = _normalize_key(part[: year_match.start()].strip(), year_match.group(1))
                if key:
                    citations.add(key)

    # Character class covering EN/DE/FR/IT surnames (accented letters in body of name)
    _CAP = r"[A-ZÄÖÜÀÂÇÉÈÊËÎÏÔÛÙÜŸŒÆÌÒÚ]"
    _LOW = r"[a-zäöüéèàâçêëîïôûùüÿœæìòú\-]"
    _SUR = rf"(?:Mc|Mac)?{_CAP}{_LOW}+"

    # Narrative two-author: EN "and", DE "und", FR "et" (≠ "et al."), IT "e"
    for m in re.compile(
        rf"({_SUR})\s+(?:und|and|et(?!\s+al\.?\b)|e(?=\s+{_CAP}))\s+({_SUR})\s+\((\d{{4}})\)"
    ).finditer(body):
        citations.add(f"{m.group(1).lower()} & {m.group(2).lower()}, {m.group(3)}")

    # Narrative et al.: "Author et al. (Year)"
    for m in re.compile(rf"({_SUR})\s+et\s+al\.\s+\((\d{{4}})\)").finditer(body):
        citations.add(f"{m.group(1).lower()} et al., {m.group(2)}")

    # Narrative with preposition — German, French, Italian
    _PREP = r"(?:nach|von|laut|bei|selon|d'apr[eè]s|par|secondo|stando\s+a)"
    for m in re.compile(
        rf"{_PREP}\s+({_SUR}(?:\s+et\s+al\.)?)\s+\((\d{{4}})\)"
    ).finditer(body):
        author_raw, year = m.group(1).strip(), m.group(2)
        if "et al." in author_raw:
            citations.add(f"{author_raw.split()[0].lower()} et al., {year}")
        else:
            citations.add(f"{author_raw.lower()}, {year}")

    # Simple narrative: "Author (Year)"
    # Skip second-author words already captured by the two-author pattern above.
    for m in re.compile(rf"(?<![(\w])({_SUR})\s+\((\d{{4}})\)").finditer(body):
        author = m.group(1)
        if author.lower() in _STOPWORDS:
            continue
        preceding = body[max(0, m.start(1) - 6): m.start(1)].rstrip()
        if preceding.endswith(("&", "und", "and", "et", " e")):
            continue
        citations.add(f"{author.lower()}, {m.group(2)}")

    return citations


def extract_bibliography(bib_text: str) -> dict[str, str]:
    """Extract bibliography entries. Returns {normalized_key: full_line}."""
    entries: dict[str, str] = {}

    for line in bib_text.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "-", ">")):
            continue

        year_match = re.search(r"\((\d{4})\)", line)
        if not year_match:
            continue

        year = year_match.group(1)
        author_part = line[: year_match.start()].strip().rstrip(",").rstrip(".")

        _BIB_CAP = r"[A-ZÄÖÜÀÂÇÉÈÊËÎÏÔÛÙÜÌÒÚ]"
        _BIB_LOW = r"[a-zäöüéèàâçêëîïôûùüìòú\-]"
        authors: list[str] = []
        for part in re.split(r"\s*&\s*", author_part):
            surname_matches = re.findall(
                rf"((?:Mc|Mac)?{_BIB_CAP}{_BIB_LOW}+),\s*{_BIB_CAP}", part
            )
            if surname_matches:
                authors.extend(surname_matches)
            else:
                m = re.match(
                    rf"((?:Mc|Mac)?{_BIB_CAP}[{_BIB_CAP[1:-1]}a-zäöüéèàâçêëîïôûùüìòú\- ]+)",
                    part.strip(),
                )
                if m:
                    authors.append(m.group(1).strip())

        if not authors:
            continue

        first = authors[0]
        if len(authors) >= 3:
            key = f"{first.lower()} et al., {year}"
        elif len(authors) == 2:
            key = f"{first.lower()} & {authors[1].lower()}, {year}"
        else:
            key = f"{first.lower()}, {year}"

        entries[key] = line

    return entries


_BIB_HEADERS = re.compile(
    r"^#+\s*(References|Bibliography|Works\s+Cited"
    r"|Literaturverzeichnis|Literatur"
    r"|Bibliographie|R[eé]f[eé]rences"
    r"|Bibliografia|Riferimenti(?:\s+bibliografici)?|Opere\s+citate)",
    re.IGNORECASE,
)


def find_bib_start(text: str) -> int:
    """Find the line index where the bibliography section starts."""
    for i, line in enumerate(text.splitlines()):
        if _BIB_HEADERS.match(line):
            return i
    return -1


def _suggest_alternatives(
    missing_key: str, bibliography: dict[str, str], n: int = 3
) -> list[tuple[str, str]]:
    """Return up to n bibliography entries that might match a missing citation.

    Ranks by: same year (score +2) + overlapping surname token (score +1).
    """
    parts = missing_key.split(",")
    surname = parts[0].split("&")[0].split("et al")[0].strip()
    year = parts[-1].strip()

    scored: list[tuple[int, str, str]] = []
    for bk, full_line in bibliography.items():
        bk_year = bk.split(",")[-1].strip()
        bk_surname = bk.split(",")[0].split("&")[0].split("et al")[0].strip()
        score = (2 if bk_year == year else 0) + (1 if surname and (surname in bk_surname or bk_surname in surname) else 0)
        if score > 0:
            scored.append((score, bk, full_line))

    scored.sort(reverse=True)
    return [(bk, fl[:80] + "..." if len(fl) > 80 else fl) for _, bk, fl in scored[:n]]


def main() -> None:
    essay_path = Path("docs/essay/essay.md")
    if len(sys.argv) > 1:
        essay_path = Path(sys.argv[1])

    text = essay_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    bib_start = find_bib_start(text)
    if bib_start < 0:
        print("ERROR: Could not find bibliography section.")
        sys.exit(1)

    body = "\n".join(lines[:bib_start])
    bib_text = "\n".join(lines[bib_start:])

    inline = extract_inline_citations(body)
    bibliography = extract_bibliography(bib_text)
    bib_keys = set(bibliography.keys())

    missing_from_bib = [c for c in sorted(inline) if c not in bib_keys and not _fuzzy_match(c, bib_keys)]
    never_cited = [k for k in sorted(bib_keys) if k not in inline and not _fuzzy_match(k, inline)]

    print("=" * 70)
    print("CITATION CHECK REPORT")
    print("=" * 70)
    print(f"\nIn-text citations found: {len(inline)}")
    print(f"Bibliography entries:    {len(bibliography)}")

    print(f"\n{'─' * 70}")
    print(f"CITED IN TEXT BUT NOT IN BIBLIOGRAPHY ({len(missing_from_bib)}):")
    print(f"{'─' * 70}")
    if missing_from_bib:
        for c in missing_from_bib:
            print(f"  x {c}")
            suggestions = _suggest_alternatives(c, bibliography)
            if suggestions:
                print(f"    Did you mean:")
                for bk, short in suggestions:
                    print(f"      - {bk}  [{short}]")
    else:
        print("  All in-text citations have matching bibliography entries.")

    print(f"\n{'─' * 70}")
    print(f"IN BIBLIOGRAPHY BUT NEVER CITED ({len(never_cited)}):")
    print(f"{'─' * 70}")
    for key in never_cited:
        full_line = bibliography[key]
        short = full_line[:80] + "..." if len(full_line) > 80 else full_line
        print(f"  ? {key}")
        print(f"    - {short}")
    if not never_cited:
        print("  All bibliography entries are cited in the text.")

    print(f"\n{'─' * 70}")
    print(f"ALL INLINE CITATIONS ({len(inline)}):")
    print(f"{'─' * 70}")
    for c in sorted(inline):
        status = "ok" if c in bib_keys or _fuzzy_match(c, bib_keys) else "x"
        print(f"  {status} {c}")

    print()
    sys.exit(1 if missing_from_bib else 0)


if __name__ == "__main__":
    main()
