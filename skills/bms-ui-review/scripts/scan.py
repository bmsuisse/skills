#!/usr/bin/env python3
"""Static UI checks over a frontend's source files: no browser, no running app.

    python scan.py frontend/src [more folders] [--locales 'frontend/**/locales/*.ts']

Reports, per file and line:
- shared-package: an @bmsuisse/* package behind the latest on npm (declared and installed versions);
- homonym: one word for two meanings in a translation (fr 'annuler' for both Cancel and Discard);
- mixed-form: one message in two forms ('Add member' and 'Add a filter'; 'Saved.' and 'Saved');
- vocabulary: one action named with two words of a synonym set across the locale files (Cancel / Discard,
  Delete / Remove, ...); the crawl does the same on screen, this sees every string, dialogs included;
- raw-colour: a hex/rgb/hsl colour or a Tailwind palette class (bg-blue-500) instead of a token;
- icon-set: an icon import from another set than Heroicons;
- native-control: a native element where @bmsuisse/ui or @bmsuisse/datagrid has a component;
- inline-size: a font size in px written inline;
- button-navigates: a click handler that navigates, where a link belongs.
Findings are leads: open the line before reporting it. What holds for the app belongs in its CI as a lint or test.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import sys
import urllib.parse
import urllib.request

# Same sets as crawl.py: words that name one kind of action.
SYNONYMS = [
    {"cancel", "discard", "close", "dismiss", "abort", "abbrechen", "verwerfen", "schliessen", "schließen", "annuler", "fermer", "abandonner", "annulla", "chiudi", "scarta"},
    {"delete", "remove", "erase", "löschen", "entfernen", "supprimer", "retirer", "elimina", "rimuovi"},
    {"save", "apply", "confirm", "submit", "speichern", "anwenden", "übernehmen", "enregistrer", "appliquer", "valider", "salva", "applica", "conferma"},
    {"add", "create", "hinzufügen", "erstellen", "ajouter", "créer", "aggiungi", "crea"},
    {"edit", "modify", "bearbeiten", "ändern", "modifier", "modifica"},
    {"undo", "revert", "reset", "rückgängig", "zurücksetzen", "réinitialiser", "ripristina"},
]
CODE = {".ts", ".tsx", ".js", ".jsx", ".vue", ".css"}
RULES = [
    ("raw-colour", re.compile(r"#[0-9a-fA-F]{3,8}\b|\b(rgb|rgba|hsl|hsla)\(|\b(bg|text|border|ring|fill|stroke)-(red|blue|green|yellow|orange|purple|pink|gray|grey|slate|zinc|neutral|stone|amber|lime|emerald|teal|cyan|sky|indigo|violet|fuchsia|rose)-\d{2,3}\b")),
    ("icon-set", re.compile(r"from ['\"](lucide-react|react-icons[^'\"]*|@mui/icons-material[^'\"]*|@fortawesome/[^'\"]*|@tabler/icons-react|react-feather|@phosphor-icons/[^'\"]*)['\"]")),
    ("native-control", re.compile(r"<input[^>]*type=[\"'](date|datetime-local|month|number)[\"']|<table[\s>]|<dialog[\s>]|\bwindow\.(confirm|alert|prompt)\(|<select[\s>]")),
    ("inline-size", re.compile(r"fontSize:\s*['\"]?\d+(px)?|font-size:\s*\d+px")),
    # below the readable minimum, in CSS, Tailwind, chart options and canvas fonts
    ("tiny-font", re.compile(r"(?:font-size:\s*|fontSize:\s*['\"]?|text-\[|font\s*=\s*['\"\x60][^'\"\x60]*?)(?:[5-9]|10)(?:\.\d+)?px|fontSize:\s*(?:[5-9]|10)\b")),
    # shown on hover only: a keyboard or touch user never finds it
    ("hover-only", re.compile(r"opacity-0(?![^\"'\x60]*(?:focus|aria-expanded|data-\[state))[^\"'\x60]*group-hover:opacity-100|group-hover:opacity-100(?![^\"'\x60]*focus)[^\"'\x60]*opacity-0")),
    # a coloured dot with no text: colour is the only signal
    ("status-dot", re.compile(r"size-(?:1\.5|2|2\.5)\b[^\"'\x60]*rounded-full[^\"'\x60]*\bbg-|rounded-full[^\"'\x60]*size-(?:1\.5|2|2\.5)\b[^\"'\x60]*\bbg-")),
]
FIX = {
    "raw-colour": "a design token (bg-primary, text-muted-foreground, var(--...))",
    "icon-set": "@heroicons/react/24/outline",
    "native-control": "the @bmsuisse/ui or @bmsuisse/datagrid component (DateInput, NumberInput, DataGrid, ConfirmDialog, FormModal, Select)",
    "inline-size": "the type scale (a text-* class or token)",
    "tiny-font": "11px at least (the type scale's smallest step), also in charts and canvas",
    "hover-only": "keep it visible, or show it on focus-within / focus-visible too",
    "status-dot": "an aria-label or title on the dot, or a word next to it",
    "untranslated": "translate it, or allow-list the term (product names, Chat, JSON, SQL)",
    "missing-key": "add the key to the language, or the UI falls back to another language",
    "register": "one form of address per language (de: Sie or du, fr: vous or tu)",
    "plural": "a plural form (ICU {n, plural, ...} or _one/_other keys)",
    "spelling-mix": "one spelling (British or American) for the language",
    "absence": "one wording for 'no value' across the app",
    "dev-jargon": "user-facing text without repository paths, file names or tool names",
    "grid-language": "pass the app's language / labels to the shared component",
    "disabled-no-reason": "a title or tooltip that says why, or validate on submit",
    "third-party-dark": "theme the widget for dark mode (its CSS classes under .dark), or hide its chrome",
    "token-contrast": "adjust the token pair to 4.5:1 for text (3:1 for large text and UI parts)",
    "shared-package": "update it before reviewing: what it fixed is not the app's bug (OneSales: built-in translations from @bmsuisse/ui 0.30)",
    "button-navigates": "a link (<Link>, <a href>), so it opens in a new tab and reads as navigation",
}
# one locale entry per line: "key": "value" (TS/JS objects and JSON)
ENTRY = re.compile(r"""^\s*["']?([\w.\-]+)["']?\s*:\s*(["'\x60])(.*)\2,?\s*$""")
# toast-like keys: a short confirmation whose final period should be the same everywhere
DONE = re.compile(r"(saved|created|deleted|added|removed|copied|updated|sent)$", re.I)
# a quoted string (', " or a backtick) after a key, an assignment, a comma or a bracket
# over the whole file (a handler spans lines): an on<Event> handler whose body navigates within ~150 characters
NAVIGATES = re.compile(r"\bon[A-Z]\w*=\{\s*(\([^)]*\)|\w+)\s*=>\s*\{?\s*(void\s+)?(navigate|router\.(push|navigate|replace))\(|window\.location(\.href)?\s*=")
STRING = re.compile(r"(?:^|[:=,(\[]\s*)([\"'\x60])((?:(?!\1).){2,80})\1")


def files(roots: list[str], exts: set[str]) -> list[Path]:
    out: list[Path] = []
    for r in roots:
        p = Path(r)
        if p.is_file():
            out.append(p)
            continue
        out += [
            f for f in p.rglob("*")
            if f.suffix in exts and "node_modules" not in f.parts and "dist" not in f.parts
            and "generated" not in f.parts and ".gen." not in f.name
        ]
    return out


def version(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def shared_packages(roots: list[str]) -> list[tuple[str, str, str]]:
    """@bmsuisse/* packages behind the latest on npm: a fix the shared package already has is not the app's bug."""
    out: list[tuple[str, str, str]] = []
    manifests: set[Path] = set()
    for r in roots:  # the package.json at or above each source folder
        for d in [Path(r).resolve(), *Path(r).resolve().parents]:
            if (d / "package.json").is_file():
                manifests.add(d / "package.json")
                break
    for m in sorted(manifests):
        data = json.loads(m.read_text())
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        for name, wanted in sorted(deps.items()):
            if not name.startswith("@bmsuisse/") or wanted.startswith(("workspace:", "file:", "link:")):
                continue
            installed = m.parent / "node_modules" / name / "package.json"
            have = json.loads(installed.read_text())["version"] if installed.is_file() else wanted
            source = "installed" if installed.is_file() else "declared, not installed"
            try:
                url = f"https://registry.npmjs.org/{urllib.parse.quote(name, safe='@')}/latest"
                with urllib.request.urlopen(url, timeout=10) as r:
                    latest = json.load(r)["version"]
            except Exception as e:  # offline or not on the public registry: say so instead of guessing
                out.append(("shared-package", f"{m}: {name} {have}", f"latest unknown ({type(e).__name__})"))
                continue
            if version(have) < version(latest):
                major = version(have)[:1] != version(latest)[:1] or (version(have)[0] == 0 and version(have)[:2] != version(latest)[:2])
                out.append(("shared-package", f"{m}: {name} {have} -> {latest}",
                            f"{source}; declared {wanted}; {'breaking range (0.x minor or major): read the changelog' if major else 'within range: update'}"))
    return out


DISABLED = re.compile(r"<(Button|IconButton|button)\b(?:(?!>)[\s\S]){0,400}?\bdisabled(?:=\{(?![^}]*\b(?:true|false)\b\s*\})[^}]+\})?(?:(?!>)[\s\S]){0,400}?>")
GRID = re.compile(r"<(DataGrid|TreeDataGrid)\b((?:(?!>)[\s\S]){0,800})>")
JARGON = re.compile(r"(?:\b(?:docs|samples|content|scripts|backend|frontend)/[\w./-]+|\b[\w-]+\.(?:md|py|json|tsx?)\b|\bthe skill\b|\bjust [a-z-]+\b|\bPR\b)")


def jsx_checks(f: Path, text: str) -> list[tuple[str, str, str]]:
    """Checks that need a whole element, which spans lines in JSX."""
    out: list[tuple[str, str, str]] = []
    if f.suffix not in {".tsx", ".jsx", ".vue"}:
        return out
    line = lambda i: text.count("\n", 0, i) + 1  # noqa: E731
    if re.search(r"(?i)help|guide|docs?\b|onboard", str(f)):  # user-facing help written in code
        for i, ln in enumerate(text.splitlines(), 1):
            if ln.lstrip().startswith(("import", "//", "*")):
                continue
            if JARGON.search(ln) and re.search(r"[\"'\x60>]", ln):
                out.append(("dev-jargon", f"{f}:{i}", ln.strip()[:110]))
            if re.search(r"[äöüß]|\b(und|der|die|das|nicht|ist)\b", ln) and REGISTER["de"][0].search(ln):
                out.append(("register", f"{f}:{i}", "German informal: " + ln.strip()[:100]))
    for m in DISABLED.finditer(text):
        el = m.group(0)
        cond = re.search(r"\bdisabled=\{([^}]*)\}", el)
        # only a condition about validity needs a reason; "nothing changed" or "busy" explains itself
        if cond and re.search(r"(?i)valid|can(Save|Create|Submit)|required|error|missing|complete|ready|\bok\b|!\s*\w+\.trim\(\)", cond.group(1)) \
                and not re.search(r"\b(title|aria-describedby|tooltip|Tooltip|hint)\b", el):
            out.append(("disabled-no-reason", f"{f}:{line(m.start())}", " ".join(el.split())[:110]))
    for m in GRID.finditer(text):
        if not re.search(r"\b(labels|locale|lang|language|translations|i18n)\s*=", m.group(2)):
            out.append(("grid-language", f"{f}:{line(m.start())}", f"<{m.group(1)}> without labels/locale"))
    return out


# German and French forms of address; the informal set is what users read as "du" / "tu"
REGISTER = {
    "de": (re.compile(r"\b(du|dich|dir|dein\w*|deine\w*)\b", re.I), re.compile(r"\b(Sie|Ihnen|Ihr\w*)\b")),
    "fr": (re.compile(r"\b(tu|toi|ton|ta|tes)\b", re.I), re.compile(r"\b(vous|votre|vos)\b", re.I)),
}
SPELLING = [("colour", "color"), ("analyse", "analyze"), ("organise", "organize"), ("behaviour", "behavior"),
            ("centre", "center"), ("cancelled", "canceled"), ("favourite", "favorite"), ("customise", "customize"),
            ("licence", "license"), ("summarise", "summarize"), ("optimise", "optimize")]
ABSENT = re.compile(r"^\s*(–|-|—|n/a|none|keine?|aucun\w*|nessun\w*|not set|nicht gesetzt|no data|keine daten|pas de données|nessun dato|\(blank\)|\(leer\)|\(vide\)|empty)\s*\.?\s*$", re.I)
PLURAL_STOP = {"of", "von", "sur", "di", "de", "du", "des", "more", "weitere", "mehr", "plus", "altri", "altre", "in", "en", "and",
               "und", "et", "e", "x", "×", "selected", "ausgewählt", "sélectionné", "selezionati", "broken", "fehlerhaft"}
ALLOW_SAME = re.compile(r"^(ok|json|sql|chat|csv|pdf|excel|power bi|dax|id|url|api|email|e-mail|admin|status|name|info|version|\W*|\{[^}]+\}|[\d\s.,:%/-]+)$", re.I)


def locale_checks(locales: list[Path], base_lang: str) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    files = {f.stem: (f, entries(f)) for f in locales}
    if not files:
        return out
    base = files.get(base_lang, files.get("en", next(iter(files.values()))))
    bf, bv = base
    for lang, (f, tr) in files.items():
        if f == bf:
            continue
        missing = [k for k in bv if k not in tr]
        if missing:
            out.append(("missing-key", f"{f}: {len(missing)} keys", ", ".join(missing[:8])))
        bare = lambda s: re.sub(r"\{[^}]*\}|[^\w\s]", " ", s).strip()  # noqa: E731
        same = [k for k, v in tr.items() if k in bv and v == bv[k] and re.search(r"[a-z]{3}", bare(v))
                and not ALLOW_SAME.match(bare(v)) and not ALLOW_SAME.match(v.strip())]
        same.sort(key=lambda k: -len(bare(tr[k]).split()))  # several words first: the likeliest untranslated
        if same:
            out.append(("untranslated", f"{f}: {len(same)} values equal to {bf.stem}", "; ".join(f"{k}: {tr[k]}" for k in same[:8])))
        if lang in REGISTER:
            informal, formal = REGISTER[lang]
            inf = [k for k, v in tr.items() if informal.search(v)]
            fo = [k for k, v in tr.items() if formal.search(v)]
            if inf and fo:
                few, many, fw = (inf, fo, "informal") if len(inf) <= len(fo) else (fo, inf, "formal")
                out.append(("register", f"{f}: {len(inf)} informal, {len(fo)} formal", f"the {fw} ones: " + "; ".join(f"{k}: {tr[k][:50]}" for k in few[:6])))
    for lang, (f, tr) in files.items():
        plural = [k for k, v in tr.items() if (m := re.search(r"\{(n|count|\w*[cC]ount|num\w*)\}\s+(\w+)", v))
                  and m.group(2).lower() not in PLURAL_STOP and "plural" not in v
                  and not re.search(r"_(one|other|few|many|zero)$", k) and not any(k2.startswith(k + "_") for k2 in (k + "_one", k + "_other") if k2 in tr)]
        if plural:
            out.append(("plural", f"{f}: {len(plural)} counts without a plural form", "; ".join(f"{k}: {tr[k][:50]}" for k in plural[:6])))
        absent = sorted({v.strip().lower().rstrip(".") for v in tr.values() if ABSENT.match(v)})
        if len(absent) > 1:
            out.append(("absence", f"{f}: {len(absent)} wordings for no value", " | ".join(absent)))
        jargon = [k for k, v in tr.items() if JARGON.search(v)]
        if jargon:
            out.append(("dev-jargon", f"{f}: {len(jargon)} values", "; ".join(f"{k}: {tr[k][:60]}" for k in jargon[:5])))
        if lang == "en" or f == bf and lang.startswith("en"):
            text = " ".join(tr.values()).lower()
            uk = [b for b, _ in SPELLING if re.search(rf"\b{b}", text)]
            us = [a for _, a in SPELLING if re.search(rf"\b{a}", text)]
            if uk and us:  # both spellings in one language
                out.append(("spelling-mix", f"{f}: British ({', '.join(uk)}) and American ({', '.join(us)})", "pick one"))
    return out


def oklch_to_rgb(lightness: float, c: float, h: float) -> tuple[float, float, float]:
    import math
    a, b = c * math.cos(math.radians(h)), c * math.sin(math.radians(h))
    l_ = lightness + 0.3963377774 * a + 0.2158037573 * b
    m_ = lightness - 0.1055613458 * a - 0.0638541728 * b
    s_ = lightness - 0.0894841775 * a - 1.2914855480 * b
    lm, mm, sm = l_ ** 3, m_ ** 3, s_ ** 3
    r = 4.0767416621 * lm - 3.3077115913 * mm + 0.2309699292 * sm
    g = -1.2684380046 * lm + 2.6097574011 * mm - 0.3413193965 * sm
    bl = -0.0041960863 * lm - 0.7034186147 * mm + 1.7076147010 * sm
    return tuple(min(1.0, max(0.0, x)) for x in (r, g, bl))  # linear sRGB


def colour(v: str):
    v = v.strip()
    if m := re.match(r"oklch\(\s*([\d.]+)(%?)\s+([\d.]+)\s+([\d.]+)", v):
        lightness = float(m.group(1)) / (100 if m.group(2) else 1)
        return oklch_to_rgb(lightness, float(m.group(3)), float(m.group(4)))
    if m := re.match(r"#([0-9a-f]{6})\b", v, re.I):
        srgb = [int(m.group(1)[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in srgb)
    return None


def css_tokens(src: list[Path]) -> list[tuple[str, str, str]]:
    """Contrast of the token pairs a design system pairs (x / x-foreground), in light (:root) and dark (.dark)."""
    out: list[tuple[str, str, str]] = []
    for f in [p for p in src if p.suffix == ".css"]:
        text = f.read_text(errors="ignore")
        for scope, sel in (("light", r":root"), ("dark", r"\.dark")):
            block = "".join(m.group(1) for m in re.finditer(sel + r"\s*\{([^}]*)\}", text))
            tokens = dict(re.findall(r"--([\w-]+)\s*:\s*([^;]+);", block))
            for name in tokens:
                pairs = []
                if name.endswith("-foreground"):
                    pairs.append((name, name[: -len("-foreground")]))
                if name == "foreground":
                    pairs.append((name, "background"))
                if name == "muted-foreground":
                    pairs += [(name, "background"), (name, "card")]
                for fg, bg in pairs:
                    a, b = colour(tokens.get(fg, "")), colour(tokens.get(bg, ""))
                    if not a or not b:
                        continue
                    lum = lambda c: 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]  # noqa: E731
                    hi, lo = max(lum(a), lum(b)), min(lum(a), lum(b))
                    ratio = (hi + 0.05) / (lo + 0.05)
                    if ratio < 4.5:
                        out.append(("token-contrast", f"{f}: {scope} --{fg} on --{bg}", f"{ratio:.2f}:1"))
    return out


THIRD_PARTY = {"reactflow": "react-flow", "@xyflow/react": "react-flow", "leaflet": "leaflet", "react-leaflet": "leaflet",
               "maplibre-gl": "maplibregl", "mapbox-gl": "mapboxgl", "@codemirror": "cm-", "monaco-editor": "monaco"}


def third_party_dark(src: list[Path]) -> list[tuple[str, str, str]]:
    """A third-party widget that draws its own chrome, with no dark-mode override for its CSS classes."""
    out: list[tuple[str, str, str]] = []
    text = {f: f.read_text(errors="ignore") for f in src}
    css = "\n".join(t for f, t in text.items() if f.suffix == ".css")
    if not re.search(r"\.dark\b", css) and not any("dark:" in t for t in text.values()):
        return out  # no dark mode at all
    for pkg, prefix in THIRD_PARTY.items():
        users = [f for f, t in text.items() if re.search(rf"from ['\"]{re.escape(pkg)}", t)]
        own = "\n".join(text[f] for f in users)
        if users and not re.search(rf"\.dark[^{{]*\.{re.escape(prefix)}|\[data-theme=dark\][^{{]*{re.escape(prefix)}", css) \
                and not re.search(r"colorMode=|\bdark\b.*\bcontrols|className=\{[^}]*dark", own):
            out.append(("third-party-dark", f"{pkg} in {users[0]}" + (f" (+{len(users) - 1})" if len(users) > 1 else ""), f"no .dark override for .{prefix}* found"))
    return out


def entries(f: Path) -> dict[str, str]:
    return {m.group(1): m.group(3) for line in f.read_text(errors="ignore").splitlines() if (m := ENTRY.match(line))}


def first(v: str) -> str:
    """The first real word: placeholders ({label}) skipped, since some languages put the verb after them."""
    words = [w for w in v.strip().split() if not w.startswith("{")]
    return words[0].lower().strip(".:…!") if words else ""


def forms(locales: list[Path], base_lang: str) -> list[tuple[str, str, str]]:
    """Checks that need the keys: one word for two meanings across languages, and mixed forms of one message."""
    out: list[tuple[str, str, str]] = []
    files = {f.stem: entries(f) for f in locales}
    if base_lang not in files and files:  # no file of that language: compare with one that exists, and say so
        fallback = "en" if "en" in files else sorted(files)[0]
        out.append(("homonym", f"base language '{base_lang}' has no locale file: compared with '{fallback}'",
                    f"files: {', '.join(sorted(files))}; pass --base-lang to choose"))
        base_lang = fallback
    base = files.get(base_lang)
    if not base:
        return out
    # one word, two meanings: the base language uses two words of a set (Cancel / Discard) where a translation uses one
    for group in SYNONYMS:
        keys_by_word: dict[str, list[str]] = defaultdict(list)
        for k, v in base.items():
            if first(v) in group:
                keys_by_word[first(v)].append(k)
        if len(keys_by_word) < 2:
            continue
        for lang, tr in files.items():
            if lang == base_lang:
                continue
            words: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))  # translated word -> base word -> keys
            for bw, keys in keys_by_word.items():
                for k in keys:
                    if k in tr and first(tr[k]):
                        words[first(tr[k])][bw].append(k)
            for tw, bws in words.items():
                if len(bws) > 1:
                    out.append(("homonym", f"{lang}: '{tw}' for {' and '.join(sorted(bws))}",
                                "; ".join(f"{bw}: {', '.join(ks[:3])}" for bw, ks in bws.items())))
    # mixed forms in the base language: "Add member" next to "Add a filter"; "Saved." next to "Saved"
    adds = [(k, v) for k, v in base.items() if re.match(r"(?i)add\s+\w", v) and len(v.split()) <= 4]
    with_article = [(k, v) for k, v in adds if re.match(r"(?i)add\s+(a|an|the)\s", v)]
    without = [(k, v) for k, v in adds if (k, v) not in with_article and not re.match(r"(?i)add\s+(to|all|new)\b", v)]
    if with_article and without:
        out.append(("mixed-form", f"{base_lang}: 'Add a X' ({len(with_article)}) and 'Add X' ({len(without)})",
                    "; ".join(f"{k}: {v}" for k, v in (with_article[:2] + without[:3]))))
    done = [(k, v) for k, v in base.items() if DONE.search(k) and len(v.split()) <= 5]
    dot = [(k, v) for k, v in done if v.rstrip().endswith(".")]
    if dot and len(dot) < len(done):
        out.append(("mixed-form", f"{base_lang}: confirmations with a final period ({len(dot)}) and without ({len(done) - len(dot)})",
                    "; ".join(f"{k}: {v}" for k, v in (dot[:3] + [x for x in done if x not in dot][:2]))))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("roots", nargs="+", help="source folders (e.g. frontend/src)")
    ap.add_argument("--ignore", action="append", default=[], metavar="GLOB",
                    help="files where raw values are deliberate (print CSS, chart palettes, illustrations); repeatable")
    ap.add_argument("--base-lang", default="en", help="the locale file the others translate (by file name stem)")
    ap.add_argument("--locales", action="append", default=[], help="glob of locale files; default: files under a locales/, i18n/ or lang/ folder")
    args = ap.parse_args()

    findings: list[tuple[str, str, str]] = []
    src = files(args.roots, CODE)
    for f in src:
        if re.search(r"\.(test|spec|stories)\.", f.name) or any(f.match(g) for g in args.ignore):
            continue
        for n, line in enumerate(f.read_text(errors="ignore").splitlines(), 1):
            if line.lstrip().startswith(("//", "*", "/*")):
                continue
            for kind, rx in RULES:
                if kind == "raw-colour" and f.suffix == ".css" and "--" in line:
                    continue  # a token definition is where raw colours belong
                if rx.search(line):
                    findings.append((kind, f"{f}:{n}", line.strip()[:110]))
        text = f.read_text(errors="ignore")
        findings += jsx_checks(f, text)
        for m in NAVIGATES.finditer(text):
            n = text.count("\n", 0, m.start()) + 1
            findings.append(("button-navigates", f"{f}:{n}", " ".join(m.group(0).split())[:110]))

    locales = [Path(p) for g in args.locales for p in Path(".").glob(g)] or [
        f for f in files(args.roots, {".ts", ".json", ".js"}) if re.search(r"/(locales?|i18n|lang)/", str(f))
    ]
    for f in locales:  # one language per file: compare words within a file, never across languages
        used: dict[int, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))  # synonym set -> word -> lines
        for n, line in enumerate(f.read_text(errors="ignore").splitlines(), 1):
            for m in STRING.finditer(line):
                first = m.group(2).strip().split(" ")[0].lower().strip(".:…!")
                for i, group in enumerate(SYNONYMS):
                    if first in group:
                        used[i][first].append(str(n))
        for words in used.values():
            if len(words) > 1:
                findings.append((
                    "vocabulary",
                    f"{f}: " + " / ".join(f"{w} ({len(p)})" for w, p in words.items()),
                    "; ".join(f"{w}: lines {', '.join(p[:5])}" for w, p in words.items()),
                ))

    findings += forms(locales, args.base_lang)
    findings += locale_checks(locales, args.base_lang)
    findings += css_tokens(src)
    findings += third_party_dark(src)
    findings += shared_packages(args.roots)

    by_kind: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for k, where, what in findings:
        by_kind[k].append((where, what))
    print(f"# Static UI scan: {len(src)} source files, {len(locales)} locale files\n")
    for k, items in by_kind.items():
        print(f"## {k} ({len(items)})" + (f"  -> {FIX[k]}" if k in FIX else ""))
        for where, what in items[:60]:
            print(f"- {where}  {what}")
        if len(items) > 60:
            print(f"- ... {len(items) - 60} more")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
