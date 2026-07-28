#!/usr/bin/env python3
"""Flag a few of this skill's checklist items mechanically instead of by eye:
hex colors close to the known AI-default accents, how many distinct pill/
badge shapes a file uses, and numeric-looking columns with no tabular-figure
treatment. Heuristic, regex-based — a starting point for the review, not a
replacement for reading the file.

Usage: audit_ui_file.py <file> [<file> ...]
"""
import re
import sys
import colorsys

# Known AI-default accents (see SKILL.md #3). Flag anything within this hue
# distance (out of 360) and reasonably close in saturation/lightness.
KNOWN_TELLS = {
    "terracotta/clay (#D97757 family)": "#D97757",
    "acid green": "#39FF14",
    "vermilion": "#E34234",
}
HUE_THRESHOLD_DEG = 18


def hex_to_hsl(hex_color):
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (0, 2, 4))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h * 360, s, l


def find_hex_colors(text):
    return set(m.group(0) for m in re.finditer(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b", text))


def check_accent_tells(text):
    findings = []
    for hex_color in find_hex_colors(text):
        try:
            h, s, l = hex_to_hsl(hex_color)
        except ValueError:
            continue
        if s < 0.35 or l < 0.15 or l > 0.85:
            continue  # too desaturated/dark/light to read as "the accent"
        for name, tell_hex in KNOWN_TELLS.items():
            th, ts, tl = hex_to_hsl(tell_hex)
            hue_dist = min(abs(h - th), 360 - abs(h - th))
            if hue_dist <= HUE_THRESHOLD_DEG:
                findings.append(f"{hex_color} is close to the {name} tell (hue distance {hue_dist:.0f}°)")
    return findings


PILL_PATTERNS = [
    r"rounded-full",
    r"border-radius:\s*9999px",
    r"border-radius:\s*999px",
    r"\bpill\b",
    r"\bbadge\b",
]


def count_pill_shapes(text):
    # Distinct className/style value combos that look like a pill container,
    # not just the count of the word "rounded-full" (one component reused
    # many times for the same semantic thing is fine; the tell is *distinct*
    # shapes/colors applied to *different* semantic things).
    lines_with_pills = [ln for ln in text.splitlines() if any(re.search(p, ln) for p in PILL_PATTERNS)]
    color_hints = set()
    for ln in lines_with_pills:
        color_hints.update(re.findall(r"(?:bg|text|border)-(\w+)-\d{2,3}", ln))
        color_hints.update(find_hex_colors(ln))
    return len(lines_with_pills), color_hints


NUMERIC_COLUMN_HINT = re.compile(
    r"\b(amount|price|revenue|total|count|duration|balance|qty|quantity|percent|rate|value)\b", re.IGNORECASE
)
TABULAR_HINT = re.compile(r"tabular-nums|font-feature-settings.*tnum|font-variant-numeric.*tabular", re.IGNORECASE)


def check_tabular_figures(text):
    has_numeric_hint = bool(NUMERIC_COLUMN_HINT.search(text))
    has_tabular = bool(TABULAR_HINT.search(text))
    if has_numeric_hint and not has_tabular:
        return ["File has numeric-looking column names but no tabular-nums/font-feature-settings anywhere."]
    return []


def audit(path):
    text = open(path, encoding="utf-8").read()
    print(f"\n=== {path} ===")

    accent = check_accent_tells(text)
    if accent:
        print("Accent color tells:")
        for f in accent:
            print(f"  - {f}")
    else:
        print("Accent color: no known AI-default tells found in hex literals.")

    pill_lines, colors = count_pill_shapes(text)
    print(f"Pill/badge-shaped lines: {pill_lines}, distinct color hints used: {len(colors)} {sorted(colors) if colors else ''}")
    if len(colors) > 3:
        print("  -> more than 3 distinct pill colors/shapes; check they map to genuinely different semantic categories (see SKILL.md #2), not decoration.")

    tabular = check_tabular_figures(text)
    for f in tabular:
        print(f"Tabular figures: {f}")
    if not tabular:
        print("Tabular figures: no obvious gap detected (or no numeric-looking columns found).")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    for path in sys.argv[1:]:
        audit(path)


if __name__ == "__main__":
    main()
