#!/usr/bin/env python3
"""Extract comments with surrounding code context from Python, JS, TS, JSX, and TSX files.

Usage:
    python3 extract_comments.py <file> [<file> ...] [--context N]

Output: JSON array to stdout, one entry per comment:
    {"file": "...", "line": 12, "kind": "line|block|docstring",
     "text": "...", "context": "<code around the comment>"}

This is a lightweight heuristic scanner, not a real parser. It is meant to give
an LLM enough surrounding code to judge whether a comment earns its place --
not to be a compiler frontend. JS/TS block-comment detection does a simple
best-effort skip of string/template literals; it can be fooled by comment-like
text inside strings on rare inputs. Good enough for review purposes.
"""
import argparse
import io
import json
import sys
import tokenize
from pathlib import Path

JS_EXTS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
PY_EXTS = {".py"}


def context_window(lines, line_no, before=2, after=5):
    start = max(0, line_no - 1 - before)
    end = min(len(lines), line_no + after)
    return "\n".join(lines[start:end])


def extract_python(source, lines):
    """Use tokenize so comments inside strings are never mistaken for real comments."""
    results = []
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return results

    prev_significant = None
    for tok in tokens:
        if tok.type == tokenize.COMMENT:
            results.append({
                "line": tok.start[0],
                "kind": "line",
                "text": tok.string.lstrip("#").strip(),
            })
        elif tok.type == tokenize.STRING and prev_significant and prev_significant[1] in (":",):
            # crude docstring heuristic: a bare string statement right after a
            # `def ...:` / `class ...:` line, on its own line
            if tok.string.startswith(('"""', "'''")):
                line_text = lines[tok.start[0] - 1].strip()
                if line_text.startswith(('"""', "'''", 'r"""', "r'''")):
                    results.append({
                        "line": tok.start[0],
                        "kind": "docstring",
                        "text": tok.string.strip("\"'").strip(),
                    })
        if tok.type not in (tokenize.NL, tokenize.NEWLINE, tokenize.INDENT,
                            tokenize.DEDENT, tokenize.COMMENT, tokenize.ENCODING):
            prev_significant = (tok.type, tok.string)
    return results


def extract_js(source):
    """Best-effort scan for // and /* */ comments, skipping over string/template literals."""
    results = []
    i = 0
    n = len(source)
    line_no = 1
    in_string = None  # holds the quote char / "`" currently open, or None
    while i < n:
        ch = source[i]
        if ch == "\n":
            line_no += 1
            i += 1
            continue
        if in_string:
            if ch == "\\":
                i += 2
                continue
            if ch == in_string:
                in_string = None
            i += 1
            continue
        if ch in ("'", '"', "`"):
            in_string = ch
            i += 1
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "/":
            end = source.find("\n", i)
            end = end if end != -1 else n
            results.append({
                "line": line_no,
                "kind": "line",
                "text": source[i + 2:end].strip(),
            })
            i = end
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "*":
            end = source.find("*/", i + 2)
            end = end if end != -1 else n
            comment_text = source[i + 2:end]
            kind = "docstring" if source[i:i + 3] == "/**" else "block"
            results.append({
                "line": line_no,
                "kind": kind,
                "text": comment_text.strip(),
            })
            line_no += comment_text.count("\n")
            i = end + 2
            continue
        i += 1
    return results


def process_file(path, before, after):
    ext = Path(path).suffix.lower()
    source = Path(path).read_text(encoding="utf-8", errors="replace")
    lines = source.splitlines()

    if ext in PY_EXTS:
        raw = extract_python(source, lines)
    elif ext in JS_EXTS:
        raw = extract_js(source)
    else:
        raise ValueError(f"Unsupported extension: {ext} (supported: {sorted(PY_EXTS | JS_EXTS)})")

    for item in raw:
        item["file"] = str(path)
        item["context"] = context_window(lines, item["line"], before, after)
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+")
    parser.add_argument("--before", type=int, default=2, help="lines of context before the comment")
    parser.add_argument("--after", type=int, default=5, help="lines of context after the comment")
    args = parser.parse_args()

    all_results = []
    for f in args.files:
        try:
            all_results.extend(process_file(f, args.before, args.after))
        except ValueError as e:
            print(f"Skipping {f}: {e}", file=sys.stderr)

    json.dump(all_results, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
