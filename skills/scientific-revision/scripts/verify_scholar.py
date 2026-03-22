"""Verify bibliography entries against Semantic Scholar, with Google Scholar
(scholarly) as an optional cross-check.

Uses httpx sync client directly against the Semantic Scholar API — avoids the
anyio/Python 3.14 incompatibility in the semanticscholar library.

Optional API key (raises rate limit from ~1 to 10 req/s):
    export SEMANTIC_SCHOLAR_API_KEY=<your-key>
    Free key: https://www.semanticscholar.org/product/api

Usage:
    python scripts/verify_scholar.py [path/to/essay.md]
"""

import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import httpx


SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"
SIMILARITY_THRESHOLD = 0.45
_S2_API_KEY = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")


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
    confidence: str  # "high", "medium", "low"
    confidence_score: float
    source: str = ""
    matched_title: str = ""
    matched_author: str = ""
    matched_year: str = ""
    scholar_url: str = ""
    similarity: float = 0.0
    note: str = ""
    citations: int = -1


def extract_bibliography(text: str) -> list[BibEntry]:
    lines = text.splitlines()
    _bib_headers = re.compile(
        r"^#+\s*(References|Bibliography|Works\s+Cited"
        r"|Literaturverzeichnis|Literatur"
        r"|Bibliographie|R[eé]f[eé]rences"
        r"|Bibliografia|Riferimenti(?:\s+bibliografici)?|Opere\s+citate)",
        re.IGNORECASE,
    )
    bib_start = next(
        (i for i, line in enumerate(lines) if _bib_headers.match(line)), -1
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
            plain = re.match(r"([^.]+)\.", rest)
            title = plain.group(1).strip() if plain else rest[:100]

        m = re.match(r"([A-ZÄÖÜa-zäöüéè\-]+)", authors)
        key = f"{m.group(1) if m else '?'}, {year}"
        entries.append(BibEntry(key=key, authors=authors, year=year, title=title, full_line=line))

    return entries


def word_overlap(a: str, b: str) -> float:
    wa, wb = set(a.lower().split()), set(b.lower().split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(len(wa), len(wb))


def _score_to_confidence(score: float) -> str:
    if score >= 0.80:
        return "high"
    if score >= 0.60:
        return "medium"
    return "low"


def _not_found(entry: BibEntry, note: str, source: str) -> VerificationResult:
    return VerificationResult(
        entry=entry, status="not_found", confidence="low",
        confidence_score=0.1, source=source, note=note,
    )


def _error(entry: BibEntry, msg: str, source: str) -> VerificationResult:
    return VerificationResult(
        entry=entry, status="error", confidence="low",
        confidence_score=0.1, source=source, note=f"Error: {msg}",
    )


def _s2_headers() -> dict[str, str]:
    h = {"User-Agent": "CitationChecker/1.0"}
    if _S2_API_KEY:
        h["x-api-key"] = _S2_API_KEY
    return h


def query_semantic_scholar(entry: BibEntry, client: httpx.Client) -> VerificationResult:
    query = f"{entry.title} {entry.authors.split(',')[0]}"
    params = {
        "query": query,
        "limit": "5",
        "fields": "title,authors,year,citationCount,url",
    }

    for attempt in range(4):
        try:
            resp = client.get(SEMANTIC_SCHOLAR_API, params=params, timeout=15)
        except Exception as e:
            return _error(entry, str(e), source="semantic_scholar")

        if resp.status_code == 429:
            wait = 2 ** attempt * 3  # 3, 6, 12, 24s
            time.sleep(wait)
            continue

        if resp.status_code != 200:
            return _error(entry, f"HTTP {resp.status_code}", source="semantic_scholar")

        papers = resp.json().get("data", [])
        break
    else:
        return _error(entry, "Rate limited after retries (HTTP 429)", source="semantic_scholar")

    if not papers:
        return _not_found(entry, "Not found in Semantic Scholar", source="semantic_scholar")

    best_score = 0.0
    best: dict | None = None

    for paper in papers:
        cr_title = paper.get("title") or ""
        cr_authors = paper.get("authors") or []
        cr_first_author = cr_authors[0].get("name", "") if cr_authors else ""
        cr_year = str(paper.get("year") or "")

        title_sim = word_overlap(entry.title, cr_title)
        first_name = entry.authors.split(",")[0].lower()
        author_match = (
            first_name in cr_first_author.lower()
            or cr_first_author.lower() in first_name
        )
        combined = (
            title_sim * 0.65
            + (0.2 if author_match else 0)
            + (0.15 if cr_year == entry.year else 0)
        )
        if combined > best_score:
            best_score = combined
            best = {
                "title": cr_title,
                "author": cr_first_author,
                "year": cr_year,
                "url": paper.get("url") or "",
                "citations": paper.get("citationCount") if paper.get("citationCount") is not None else -1,
                "title_sim": title_sim,
            }

    if best and best_score >= SIMILARITY_THRESHOLD:
        return VerificationResult(
            entry=entry,
            status="verified",
            confidence=_score_to_confidence(best_score),
            confidence_score=round(best_score, 2),
            source="semantic_scholar",
            matched_title=best["title"],
            matched_author=best["author"],
            matched_year=best["year"],
            scholar_url=best["url"],
            similarity=round(best["title_sim"], 2),
            citations=best["citations"],
        )

    return _not_found(entry, "Title similarity too low", source="semantic_scholar")


def query_scholarly(entry: BibEntry) -> VerificationResult:
    """Query Google Scholar via the scholarly library (optional)."""
    try:
        from scholarly import scholarly as _scholarly  # type: ignore[import-untyped]
    except ImportError:
        return _error(entry, "scholarly not installed — run: uv add scholarly", source="scholar")

    query = f"{entry.title} {entry.authors.split(',')[0]}"
    try:
        results = list(_scholarly.search_pubs(query))
    except Exception as e:
        return _error(entry, f"Google Scholar blocked: {e}", source="scholar")

    if not results:
        return _not_found(entry, "Not found in Google Scholar", source="scholar")

    best_score = 0.0
    best: dict | None = None

    for pub in results[:5]:
        bib = pub.get("bib", {})
        cr_title = bib.get("title") or ""
        cr_authors_raw = bib.get("author") or ""
        cr_first_author = cr_authors_raw.split(" and ")[0].split(",")[0].strip()
        cr_year = str(bib.get("pub_year") or "")

        title_sim = word_overlap(entry.title, cr_title)
        first_name = entry.authors.split(",")[0].lower()
        author_match = (
            first_name in cr_first_author.lower()
            or cr_first_author.lower() in first_name
        )
        combined = (
            title_sim * 0.65
            + (0.2 if author_match else 0)
            + (0.15 if cr_year == entry.year else 0)
        )
        if combined > best_score:
            best_score = combined
            best = {
                "title": cr_title,
                "author": cr_first_author,
                "year": cr_year,
                "url": pub.get("pub_url") or "",
                "citations": pub.get("num_citations", -1),
                "title_sim": title_sim,
            }

    if best and best_score >= SIMILARITY_THRESHOLD:
        return VerificationResult(
            entry=entry,
            status="verified",
            confidence=_score_to_confidence(best_score),
            confidence_score=round(best_score, 2),
            source="scholar",
            matched_title=best["title"],
            matched_author=best["author"],
            matched_year=best["year"],
            scholar_url=best["url"],
            similarity=round(best["title_sim"], 2),
            citations=best["citations"],
        )

    return _not_found(entry, "Title similarity too low", source="scholar")


def verify_entry(entry: BibEntry, client: httpx.Client, use_scholar: bool) -> VerificationResult:
    """Query Semantic Scholar; pick Scholar result if it scores higher."""
    s2 = query_semantic_scholar(entry, client)
    if not use_scholar:
        return s2
    gs = query_scholarly(entry)
    if gs.status == "verified" and gs.confidence_score > s2.confidence_score:
        return gs
    return s2


def _check_scholarly_available() -> bool:
    try:
        import scholarly  # noqa: F401
        return True
    except ImportError:
        return False


def generate_report(results: list[VerificationResult], output_path: Path) -> None:
    by_conf: dict[str, list[VerificationResult]] = {"high": [], "medium": [], "low": [], "none": []}
    for r in results:
        by_conf.setdefault(r.confidence, []).append(r)

    sources_used = {r.source for r in results if r.source}

    lines: list[str] = [
        "# Citation Verification Report (Scholar)",
        "",
        f"**Generated:** {time.strftime('%Y-%m-%d %H:%M')}",
        f"**Sources:** {', '.join(sorted(sources_used)) or 'N/A'}",
        f"**Total entries:** {len(results)}",
        "",
        "| Confidence | Count |",
        "|------------|-------|",
        f"| High | {len(by_conf['high'])} |",
        f"| Medium | {len(by_conf['medium'])} |",
        f"| Low | {len(by_conf['low'])} |",
        "",
        "> Powered by [Semantic Scholar](https://www.semanticscholar.org/).",
        "> Set `SEMANTIC_SCHOLAR_API_KEY` to raise the rate limit (free key at semanticscholar.org/product/api).",
        "",
        "---",
        "",
    ]

    sections: list[tuple[str, list[VerificationResult], bool]] = [
        ("Low Confidence — Manual Check Required", sorted(by_conf["low"] + by_conf["none"], key=lambda x: x.confidence_score), True),
        ("Medium Confidence — Worth Reviewing", sorted(by_conf["medium"], key=lambda x: x.confidence_score), False),
    ]
    for label, section, show_full_ref in sections:
        if not section:
            continue
        lines += [f"## {label}", ""]
        for r in section:
            lines.append(f"### {r.entry.key}")
            lines += [
                f"- **Status:** {r.status}",
                f"- **Score:** {r.confidence_score}",
                f"- **Source:** {r.source}",
            ]
            if r.note:
                lines.append(f"- **Note:** {r.note}")
            lines.append(f"- **Title:** {r.entry.title}")
            if show_full_ref:
                lines.append(f"- **Full ref:** {r.entry.full_line}")
            if r.scholar_url:
                lines.append(f"- **URL:** {r.scholar_url}")
            if r.matched_title:
                lines.append(f"- **Matched:** {r.matched_title} (sim={r.similarity})")
            lines.append("")

    if by_conf["high"]:
        lines += [
            "## High Confidence — Verified", "",
            "| Entry | Score | Source | Citations | URL |",
            "|-------|-------|--------|-----------|-----|",
        ]
        for r in sorted(by_conf["high"], key=lambda x: x.entry.key):
            url_cell = f"[link]({r.scholar_url})" if r.scholar_url else "-"
            cites = str(r.citations) if r.citations >= 0 else "-"
            lines.append(f"| {r.entry.key} | {r.confidence_score} | {r.source} | {cites} | {url_cell} |")
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

    use_scholar = _check_scholarly_available()

    print("=" * 70)
    print("SCHOLAR VERIFICATION")
    print("=" * 70)
    key_status = "with API key" if _S2_API_KEY else "no API key (rate limited to ~1 req/s)"
    print(f"  Semantic Scholar: {key_status}")
    if use_scholar:
        print("  Google Scholar (scholarly): available — used as cross-check")
    print(f"\nChecking {len(entries)} bibliography entries...\n")

    results: list[VerificationResult] = []
    with httpx.Client(headers=_s2_headers()) as client:
        for i, entry in enumerate(entries, 1):
            sys.stdout.write(f"\r  [{i}/{len(entries)}] {entry.key:<40}")
            sys.stdout.flush()
            results.append(verify_entry(entry, client, use_scholar=use_scholar))
            if not _S2_API_KEY:
                time.sleep(1.2)  # stay under the ~1 req/s unauthenticated limit

    print("\r" + " " * 80)

    high = sum(1 for r in results if r.confidence == "high")
    medium = sum(1 for r in results if r.confidence == "medium")
    low = sum(1 for r in results if r.confidence == "low")

    print(f"\n  High confidence:   {high}")
    print(f"  Medium confidence: {medium}")
    print(f"  Low confidence:    {low}")

    report_path = essay_path.parent / "citation_report_scholar.md"
    generate_report(results, report_path)
    print(f"\n  Report saved to: {report_path}")
    print()


if __name__ == "__main__":
    main()
