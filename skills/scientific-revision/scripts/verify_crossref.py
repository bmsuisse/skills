"""Verify bibliography entries against CrossRef API and generate a markdown report.

For each entry in the bibliography, queries CrossRef to check if it
corresponds to a real publication. Generates a report sorted by confidence
so low-confidence entries can be manually checked.

Usage:
    python scripts/verify_crossref.py [path/to/essay.md]
"""

import concurrent.futures
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


CROSSREF_API = "https://api.crossref.org/works"
USER_AGENT = "AIActionPlan-CitationChecker/1.0 (mailto:citation-checker@example.com)"
SIMILARITY_THRESHOLD = 0.5


@dataclass
class BibEntry:
    key: str
    authors: str
    year: str
    title: str
    full_line: str


@dataclass
class VerificationResult:
    entry: BibEntry
    status: str  # "verified", "not_found", "error"
    confidence: str  # "high", "medium", "low", "none"
    confidence_score: float
    doi: str = ""
    crossref_title: str = ""
    crossref_author: str = ""
    crossref_year: str = ""
    similarity: float = 0.0
    note: str = ""


def extract_bibliography(text: str) -> list[BibEntry]:
    """Extract bibliography entries from essay text."""
    lines = text.splitlines()
    _bib_headers = re.compile(
        r"^#+\s*(References|Bibliography|Works\s+Cited"
        r"|Literaturverzeichnis|Literatur"
        r"|Bibliographie|R[eé]f[eé]rences"
        r"|Bibliografia|Riferimenti(?:\s+bibliografici)?|Opere\s+citate)",
        re.IGNORECASE,
    )
    bib_start = next(
        (i for i, line in enumerate(lines) if _bib_headers.match(line)),
        -1,
    )
    if bib_start < 0:
        return []

    entries: list[BibEntry] = []
    for line in lines[bib_start:]:
        line = line.strip()
        if not line or line.startswith(("#", "-", ">")):
            continue

        year_match = re.search(r"\((\d{4})\)", line)
        if not year_match:
            continue

        year = year_match.group(1)
        authors = line[: year_match.start()].strip().rstrip(",").rstrip(".")
        rest = line[year_match.end():].strip().lstrip(".").strip()

        title_match = re.match(r"\*([^*]+)\*", rest)
        if title_match:
            title = title_match.group(1).strip().rstrip(".")
        else:
            title_match = re.match(r"([^.]+)\.", rest)
            title = title_match.group(1).strip() if title_match else rest[:100]

        m = re.match(r"([A-ZÄÖÜa-zäöüéè\-]+)", authors)
        key = f"{m.group(1) if m else '?'}, {year}"

        entries.append(BibEntry(key=key, authors=authors, year=year, title=title, full_line=line))

    return entries


def similarity(a: str, b: str) -> float:
    """Word-overlap similarity between two strings."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / max(len(words_a), len(words_b))


def is_book(entry: BibEntry) -> bool:
    after_year = entry.full_line[entry.full_line.find(entry.year):]
    return "*" in after_year and any(
        p in entry.full_line
        for p in ["Press", "Media", "Publications", "Springer", "Wiley", "Business", "SIAM", "Leanpub", "Crown", "Digital Press"]
    )


def is_software(entry: BibEntry) -> bool:
    return any(kw in entry.full_line.lower() for kw in ["github.com", "google.com/", "software", "or-tools", "langchain"])


def _fallback_result(entry: BibEntry, *, api_error: str = "") -> VerificationResult:
    """Return a medium or low confidence result for entries not verified via CrossRef."""
    if is_book(entry):
        note, conf, score = "Book — likely exists but not indexed in CrossRef", "medium", 0.6
    elif is_software(entry):
        note, conf, score = "Software/tool — not a traditional publication", "medium", 0.6
    else:
        note, conf, score = "Not found in CrossRef", "low", 0.1

    if api_error:
        return VerificationResult(
            entry=entry, status="error", confidence="low", confidence_score=0.2,
            note=f"API error: {api_error}. {note}",
        )
    return VerificationResult(entry=entry, status="not_found", confidence=conf, confidence_score=score, note=note)


def query_crossref(entry: BibEntry) -> VerificationResult:
    """Query CrossRef API for a bibliography entry."""
    query = f"{entry.authors.split(',')[0]} {entry.title}"
    params = urllib.parse.urlencode({
        "query.bibliographic": query,
        "rows": "3",
        "select": "title,author,published-print,published-online,DOI,type",
    })
    req = urllib.request.Request(f"{CROSSREF_API}?{params}", headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return _fallback_result(entry, api_error=str(e))

    items = data.get("message", {}).get("items", [])
    if not items:
        return _fallback_result(entry)

    best_sim = 0.0
    best_item: dict | None = None

    for item in items:
        cr_titles = item.get("title", [])
        cr_title = cr_titles[0] if cr_titles else ""
        cr_authors = item.get("author", [])
        cr_first_author = cr_authors[0].get("family", "") if cr_authors else ""

        cr_year = ""
        for date_field in ("published-print", "published-online"):
            date_parts = item.get(date_field, {}).get("date-parts", [[]])
            if date_parts and date_parts[0]:
                cr_year = str(date_parts[0][0])
                break

        title_sim = similarity(entry.title, cr_title)
        author_match = (
            entry.authors.split(",")[0].lower() in cr_first_author.lower()
            or cr_first_author.lower() in entry.authors.split(",")[0].lower()
        )
        combined = title_sim * 0.6 + (0.2 if author_match else 0) + (0.2 if cr_year == entry.year else 0)

        if combined > best_sim:
            best_sim = combined
            best_item = {
                "title": cr_title,
                "author": cr_first_author,
                "year": cr_year,
                "doi": item.get("DOI", ""),
                "title_sim": title_sim,
            }

    if best_item and best_sim >= SIMILARITY_THRESHOLD:
        conf = "high" if best_sim >= 0.85 else "medium" if best_sim >= 0.65 else "low"
        return VerificationResult(
            entry=entry,
            status="verified",
            confidence=conf,
            confidence_score=round(best_sim, 2),
            doi=best_item["doi"],
            crossref_title=best_item["title"],
            crossref_author=best_item["author"],
            crossref_year=best_item["year"],
            similarity=round(best_item["title_sim"], 2),
        )

    return _fallback_result(entry)


def generate_report(results: list[VerificationResult], output_path: Path) -> None:
    """Generate a markdown report sorted by confidence."""
    by_conf: dict[str, list[VerificationResult]] = {"high": [], "medium": [], "low": [], "none": []}
    for r in results:
        by_conf.setdefault(r.confidence, []).append(r)

    lines: list[str] = [
        "# Citation Verification Report",
        "",
        f"**Generated:** {time.strftime('%Y-%m-%d %H:%M')}",
        "**Source:** CrossRef API",
        f"**Total entries:** {len(results)}",
        "",
        "| Confidence | Count |",
        "|------------|-------|",
        f"| High | {len(by_conf['high'])} |",
        f"| Medium | {len(by_conf['medium'])} |",
        f"| Low | {len(by_conf['low'])} |",
        "",
        "---",
        "",
    ]

    sections = [
        ("Low Confidence — Manual Check Required", sorted(by_conf["low"] + by_conf["none"], key=lambda x: x.confidence_score), True),
        ("Medium Confidence — Worth Reviewing", sorted(by_conf["medium"], key=lambda x: x.confidence_score), False),
    ]
    for label, section, show_full_ref in sections:
        if not section:
            continue
        lines += [f"## {label}", ""]
        for r in section:
            lines.append(f"### {r.entry.key}")
            lines += [f"- **Status:** {r.status}", f"- **Score:** {r.confidence_score}"]
            if r.note:
                lines.append(f"- **Note:** {r.note}")
            lines.append(f"- **Title:** {r.entry.title}")
            if show_full_ref:
                lines.append(f"- **Full ref:** {r.entry.full_line}")
            if r.doi:
                lines.append(f"- **DOI:** https://doi.org/{r.doi}")
            if r.crossref_title:
                lines.append(f"- **CrossRef match:** {r.crossref_title} (sim={r.similarity})")
            lines.append("")

    if by_conf["high"]:
        lines += ["## High Confidence — Verified", "", "| Entry | Score | DOI |", "|-------|-------|-----|"]
        for r in sorted(by_conf["high"], key=lambda x: x.entry.key):
            doi_link = f"[{r.doi}](https://doi.org/{r.doi})" if r.doi else "-"
            lines.append(f"| {r.entry.key} | {r.confidence_score} | {doi_link} |")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    essay_path = Path("docs/essay/essay.md")
    if len(sys.argv) > 1:
        essay_path = Path(sys.argv[1])

    text = essay_path.read_text(encoding="utf-8")
    entries = extract_bibliography(text)

    if not entries:
        print("ERROR: No bibliography entries found.")
        sys.exit(1)

    print("=" * 70)
    print("CROSSREF VERIFICATION")
    print("=" * 70)
    print(f"\nChecking {len(entries)} bibliography entries against CrossRef...")
    print("(Running in parallel with up to 5 workers)\n")

    results: list[VerificationResult] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(query_crossref, e): e for e in entries}
        for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
            entry = futures[future]
            results.append(future.result())
            sys.stdout.write(f"\r  [{i}/{len(entries)}] {entry.key:<40}")
            sys.stdout.flush()

    print("\r" + " " * 80)

    high = sum(1 for r in results if r.confidence == "high")
    medium = sum(1 for r in results if r.confidence == "medium")
    low = sum(1 for r in results if r.confidence == "low")

    print(f"\n  High confidence:   {high}")
    print(f"  Medium confidence: {medium}")
    print(f"  Low confidence:    {low}")

    report_path = essay_path.parent / "citation_report.md"
    generate_report(results, report_path)
    print(f"\n  Report saved to: {report_path}")
    print()


if __name__ == "__main__":
    main()
