#!/usr/bin/env python3
"""Prepare a whole-app UI review in one awaited run: discover, scan, crawl every variant at once, batch the screens.

    uv run python prepare.py http://localhost:5173 --repo . --out scratch/ui-review
        [--frontend frontend/src] [--variants light dark de] [--routes /r/sales] [--max-screens 80] [crawl.py options]

Finds the frontend source, its routes (TanStack createFileRoute, React Router path), the localStorage theme and
language keys and the UI languages; opens the app once to find ids for $param routes in its links and to check that
dark mode and the language key really apply; then runs scan.py and one crawl.py per variant at the same time
(all with --thumb) and waits for them. Options it does not know go to every crawl (--storage-state, --exclude...).

<out>/manifest.json
    app, repo, frontend: str
    router: {"kind": "tanstack" | "react-router" | null, "files": [str]}
    theme: {"setting": "key=value" | null, "candidates": [str], "dark_via": "preference" | "storage" | null}
    language: {"key": str | null, "candidates": [str], "languages": [str], "longest": str | null}
    catalog: str                    @bmsuisse/ui CATALOG.md, a local path or the jsdelivr URL
    scan: {"file": str, "roots": [str], "exit": int}
    variants: {name: {"dir": str, "exit": int | null, "screens": int}}   dark by preference lives in <light>/dark
    routes: {"covered": [{"route", "path"}], "not_covered": [{"route", "why"}]}
    images: {"every_screen": Size, "visual_batches": Size, "crops": Size, "text_batches": Size}
        Size: {"files": int, "bytes": int, "tokens": int}   tokens: an estimate (images w*h/750 after the API's
        resize to 1568 px and 1.15 MP; text bytes/4)
    seconds: {"discover", "probe", "scan", "crawl-<variant>", "batches", "wall": float}

<out>/batches.json
    {"scan": str, "summaries": {variant: summary.md}, "shared": [Finding + {"variant", "screens": int, "example"}],
     "text": [Batch], "visual": [Batch]}
    Batch: {"name": str, "areas": [str], "screens": [Screen]}
    Screen (text):   {"path", "route", "texts": {variant: .txt}, "findings": {variant: [Finding]},
                      "dialogs": [{"variant", "path", "text", "findings"}]}
    Screen (visual): {"path", "route", "why": [str], "thumbs": {variant: .jpg}, "findings": {variant: [Finding]},
                      "dialogs": [{"variant", "path", "thumb", "findings"}]}
    Finding: {"kind", "where", "detail", "crop"?}. Text batches get the findings no picture is needed for, visual
    batches the layout ones. A finding on many screens (the shell's) is listed once, under "shared".
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from crawl import pattern, settle  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

SKIP_DIRS = {"node_modules", "dist", "build", "coverage", "out"}
CODE = {".ts", ".tsx", ".js", ".jsx", ".vue"}
TANSTACK = re.compile(r"""create(?:Lazy)?FileRoute\(\s*["'\x60]([^"'\x60]*)["'\x60]""")
REACT_ROUTER = re.compile(r"""(?:\bpath:\s*|<Route\b[^>]*\bpath=)["'\x60]([^"'\x60]*)["'\x60]""")
# a storage key: "app.theme", "vite-ui-theme", "oneview.lang", "i18nextLng"; never an i18n key passed to t()
STORE_KEY = re.compile(r"""(?<![=\w])(?<!\bt\()["'\x60]((?:[\w-]+[.:_-])?(?:theme|color-scheme|colorScheme|lang|language|locale)|i18nextLng)["'\x60]""")
LANG = re.compile(r"^[a-z]{2}(?:[-_][A-Z]{2})?$")
LOCALE_DIRS = {"locales", "locale", "i18n", "lang", "translations"}
OPEN_LABEL = r"^(New|Settings|Share)\b"
VISUAL = {"overlap", "low-contrast", "inner-scrollbar", "misaligned-row", "popup-offscreen", "option-cut", "clipped-text", "page-overflow"}
IMAGES_PER_BATCH, TEXTS_PER_BATCH = 30, 80
LOOK = """() => { let e = document.elementFromPoint(innerWidth / 2, innerHeight / 2);
  for (; e && /rgba\\(.*, 0\\)|transparent/.test(getComputedStyle(e).backgroundColor); e = e.parentElement);
  return {dark: document.documentElement.classList.contains('dark'), bg: e ? getComputedStyle(e).backgroundColor : '',
          lang: document.documentElement.lang, text: document.body.innerText.slice(0, 3000)}; }"""


def walk(root: Path, exts: set[str]):
    for d, dirs, names in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not x.startswith(".")]
        yield from (Path(d, n) for n in names if Path(n).suffix in exts and ".gen." not in n and not n.endswith(".d.ts"))


def is_param(seg: str) -> bool:
    return seg[:1] != "" and seg[0] in "$:*"


def norm(route: str) -> str:
    """Pathless layouts (_auth), groups ((admin)) and optional params ({-$x}) dropped; no trailing slash."""
    segs = [s for s in route.split("/") if s and s[0] not in "_({"]
    return "/" + "/".join(segs)


def route_rx(route: str) -> re.Pattern:
    parts = ["[^/]+" if is_param(s) and s not in ("$", "*") else ".*" if is_param(s) else re.escape(s) for s in route.split("/") if s]
    return re.compile("^/" + "/".join(parts) + "/?$")


def find_ids(routes: list[str], paths: list[str]) -> dict[str, str]:
    """A real value per param name, from the first link whose path matches the route up to that param."""
    ids: dict[str, str] = {}
    for r in routes:
        segs = [s for s in r.split("/") if s]
        for i, s in enumerate(segs):
            name = s.lstrip("$:")
            if not is_param(s) or not name or name in ids:
                continue
            # ponytail: keyed by param name, so two routes with an "$id" share one value; key by prefix if that bites
            rx = re.compile("^/" + "".join(("[^/]+" if is_param(x) else re.escape(x)) + "/" for x in segs[:i]) + r"([^/?#]+)")
            if hit := next((m.group(1) for p in paths if (m := rx.match(p))), None):
                ids[name] = hit
    return ids


def fill(route: str, ids: dict[str, str]) -> tuple[str | None, str | None]:
    out = []
    for s in [s for s in route.split("/") if s]:
        if is_param(s) and not ids.get(s.lstrip("$:")):
            return None, s
        out.append(ids[s.lstrip("$:")] if is_param(s) else s)
    return "/" + "/".join(out), None


def discover(repo: Path, frontend: Path | None) -> dict:
    src = frontend or next((repo / d for d in ("frontend/src", "web/src", "client/src", "app/src", "ui/src", "src") if (repo / d).is_dir()), None)
    if not src:
        sys.exit("no frontend source found: pass --frontend <the src folder>")
    tanstack, react, files, keys = set(), set(), set(), Counter()
    for f in walk(src, CODE):
        text = f.read_text(errors="ignore")
        if found := TANSTACK.findall(text):
            tanstack.update(found)
            files.add(str(f))
        elif "react-router" in text and (found := REACT_ROUTER.findall(text)):
            react.update(found)  # ponytail: a nested relative path loses its parent's prefix; pass --routes for those
            files.add(str(f))
        for line in text.splitlines():  # a namespaced key, or a plain one on a line that uses the storage
            keys.update(k for k in STORE_KEY.findall(line) if re.search(r"[.:_-]", k) or "Storage" in line or k == "i18nextLng")
    kind = "tanstack" if tanstack else "react-router" if react else None
    routes = sorted({norm(r) for r in (tanstack or {"/" + r.lstrip("/") for r in react})})
    sizes: Counter[str] = Counter()  # characters of the strings per language
    words: dict[str, list[int]] = {}
    scan_roots = {src}  # and the package that holds the locale files, when it is not the app's src
    for f in walk(src.parent if src.name == "src" else src, {".ts", ".js", ".json"}):
        code = f.stem if LANG.match(f.stem) else f.parent.name if LANG.match(f.parent.name) else None
        if code and LOCALE_DIRS & set(f.parts):
            values = [m[1] for m in re.findall(r"""^\s*["']?[\w.\-]+["']?\s*:\s*(["'\x60])(.*)\1""", f.read_text(errors="ignore"), re.M)]
            sizes[code] += sum(map(len, values))
            words.setdefault(code, []).extend(len(w) for v in values for w in re.findall(r"[^\W\d_]+", v))
            if src not in f.parents:
                scan_roots.add(next((p for p in f.parents if p.name == "src"), f.parent))
    others = [lang for lang in sizes if lang != "en"]
    # within 5% of the longest, the longer words win: a compound cannot wrap (de "Zeilenebene" vs fr "niveau des lignes")
    longest = max(others, key=lambda g: (sizes[g] >= 0.95 * max(sizes[o] for o in others), sum(words[g]) / len(words[g]))) if others else None
    catalog = next((str(f) for d in [src, *src.parents] if (f := d / "node_modules/@bmsuisse/ui/CATALOG.md").exists()),
                   "https://cdn.jsdelivr.net/npm/@bmsuisse/ui/CATALOG.md")
    # candidates, the likeliest first (app.theme before a test id): the probe keeps the first one that works
    pick = lambda *words: sorted((k for k in keys if any(w in k.lower() for w in words)), key=lambda k: (not re.search("[.:]", k), -keys[k]))[:3]  # noqa: E731
    return {"frontend": str(src), "scan_roots": sorted(map(str, scan_roots)), "router": {"kind": kind, "files": sorted(files)}, "routes": routes,
            "theme_keys": pick("theme", "scheme"), "lang_keys": pick("lang", "locale"),
            "languages": sorted(sizes), "longest": longest, "catalog": catalog}


def probe(app: str, routes: list[str], given: list[str], theme_keys: list[str], lang_keys: list[str], lang: str | None) -> dict:
    """One browser: links on / and on the parents of $param routes (for ids); does dark follow the browser's
    preference or a stored setting (which key); which language key changes <html lang>."""
    concrete = {r for r in routes if not any(is_param(s) for s in r.split("/"))}
    parents = {"/" + "/".join(r.split("/")[1:i]) for r in routes for i, s in enumerate(r.split("/")) if is_param(s)}
    with sync_playwright() as p:
        browser = p.chromium.launch()

        def visit(path: str, scheme: str = "light", storage: dict | None = None):
            ctx = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme=scheme)
            if storage:
                ctx.add_init_script(f"Object.entries({json.dumps(storage)}).forEach(([k, v]) => localStorage.setItem(k, v))")
            page = ctx.new_page()
            try:
                page.goto(app + path, timeout=30000)
            except Exception:
                return page, None
            settle(page, 8000)
            return page, page.evaluate(LOOK)

        hrefs = list(given)
        for path in ["/", *sorted(parents & concrete)]:
            page, _ = visit(path)
            hrefs += page.eval_on_selector_all("a[href]", "els => els.map(e => new URL(e.href).pathname)")
            page.context.close()
        _, light = visit("/")
        differs = lambda seen: bool(seen and light and (seen["dark"] or seen["bg"] != light["bg"]))  # noqa: E731
        by_preference = differs(visit("/", "dark")[1])
        theme = None if by_preference else next(
            (f"{k}={v}" for k in theme_keys for v in ("dark", '"dark"') if differs(visit("/", storage={k: v})[1])), None)
        dark_via = "preference" if by_preference else "storage" if theme else None
        lang_key = next((k for k in lang_keys if lang and light and not light["lang"].startswith(lang)
                         and (seen := visit("/", storage={k: lang})[1]) and seen["lang"].startswith(lang)), None)
        browser.close()
    return {"ids": find_ids(routes, hrefs), "dark_via": dark_via, "theme": theme, "lang_key": lang_key}


def timed(cmd: list[str], log: Path) -> tuple[int, float]:
    t = time.monotonic()
    with log.open("w") as f:
        code = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT).returncode
    return code, round(time.monotonic() - t, 1)


def area(path: str) -> str:
    return path.split("?")[0].strip("/").split("/")[0] or "home"


def pack(screens: list[dict], weight, per_batch: int, most: int) -> list[dict]:
    """Screens grouped by area, an area too big for one batch split in path order, then the pieces spread
    largest first over the lightest batch."""
    total = sum(map(weight, screens))
    if not total:
        return []
    k = max(1, min(most, math.ceil(total / per_batch), len(screens)))
    cap = math.ceil(total / k)
    pieces: list[list[dict]] = []
    for a in dict.fromkeys(s["area"] for s in screens):
        piece: list[dict] = []
        for s in [s for s in screens if s["area"] == a]:
            if piece and sum(map(weight, piece)) + weight(s) > cap:
                pieces.append(piece)
                piece = []
            piece.append(s)
        pieces.append(piece)
    bins: list[list[dict]] = [[] for _ in range(k)]
    for piece in sorted(pieces, key=lambda pc: -sum(map(weight, pc))):
        min(bins, key=lambda b: sum(map(weight, b))).extend(piece)
    return [{"name": "+".join(dict.fromkeys(s["area"] for s in b)), "areas": list(dict.fromkeys(s["area"] for s in b)),
             "screens": [{key: v for key, v in s.items() if key != "area"} for s in b]} for b in bins if b]


def batches(reports: dict[str, Path], routes: list[str]) -> dict:
    """reports: variant -> report.json. Light (or the first variant) is the reference the others are compared to."""
    rxs = sorted(((route_rx(r), r) for r in routes), key=lambda x: -len(x[1]))
    route_of = lambda path: next((r for rx, r in rxs if rx.match(path.split("?")[0])), pattern(path))  # noqa: E731
    screens: dict[str, dict] = {}
    for v, rep in reports.items():
        for e in json.loads(rep.read_text()):
            key = e["path"].split(" > ")[0]
            s = screens.setdefault(key, {"path": key, "area": area(key), "route": route_of(key), "v": {}, "dialogs": []})
            if " > " in e["path"]:
                s["dialogs"].append({"variant": v, **e})
                continue
            s["v"][v] = e
            if "dark" in e:
                s["v"]["dark"] = e["dark"]
    variants = list(dict.fromkeys(v for s in screens.values() for v in s["v"]))
    ref = "light" if "light" in variants else variants[0]
    clean = lambda ps: [{k: v for k, v in p.items() if k != "box"} for p in ps]  # noqa: E731
    shared, common = [], set()
    for v in variants:  # the shell's findings: on 3+ screens and a quarter of them, listed once
        seen = Counter((p["kind"], p["where"]) for s in screens.values() if v in s["v"] for p in {(q["kind"], q["where"]): q for q in s["v"][v].get("problems", [])}.values())
        n = sum(v in s["v"] for s in screens.values())
        for (kind, where), c in seen.items():
            if c >= 3 and c >= n / 4:
                common.add((v, kind, where))
                ex = next((s["path"], p) for s in screens.values() if v in s["v"] for p in s["v"][v].get("problems", []) if (p["kind"], p["where"]) == (kind, where))
                shared.append({**clean([ex[1]])[0], "variant": v, "screens": c, "example": ex[0]})
    own = lambda v, ps, vis: [p for p in clean(ps) if (p["kind"] in VISUAL) == vis and (v, p["kind"], p["where"]) not in common]  # noqa: E731
    text, visual, first = [], [], set()
    for s in sorted(screens.values(), key=lambda s: s["path"]):
        base = {"path": s["path"], "area": s["area"], "route": s["route"]}
        text.append({**base, "texts": {v: e["text"] for v, e in s["v"].items() if e.get("text")},
                     "findings": {v: f for v, e in s["v"].items() if (f := own(v, e.get("problems", []), False))},
                     "dialogs": [{"variant": d["variant"], "path": d["path"], "text": d.get("text"), "findings": own(d["variant"], d["problems"], False)} for d in s["dialogs"]]})
        found = {v: own(v, e.get("problems", []), True) for v, e in s["v"].items()}
        ref_kinds = Counter(p["kind"] for p in found.get(ref, []))
        why = [w for w, hit in (("finding", bool(found.get(ref))), ("graphics", s["v"].get(ref, {}).get("graphics")),
                                ("first of its route", s["route"] not in first)) if hit]
        first.add(s["route"])
        # the other variants only where their layout findings differ from the reference's
        thumbs = {v: e["thumb"] for v, e in s["v"].items() if e.get("thumb") and
                  ((v == ref and why) or (v != ref and Counter(p["kind"] for p in found[v]) - ref_kinds))}
        dialogs = []  # one per kind of popup on a route ("Filter User", "Filter Role": one), lists only with a finding
        for d in s["dialogs"]:
            label = d["path"].split(" > ")[-1]
            kind = (d["variant"], s["route"], label.split(" ")[0])
            if d.get("thumb") and ((f := own(d["variant"], d["problems"], True)) or (not label.startswith("list ") and kind not in first)):
                dialogs.append({"variant": d["variant"], "path": d["path"], "thumb": d["thumb"], "findings": f})
            first.add(kind)
        if thumbs or dialogs:
            visual.append({**base, "why": why, "thumbs": thumbs, "findings": {v: f for v, f in found.items() if f}, "dialogs": dialogs})
    return {"shared": shared,
            "text": pack(text, lambda s: len(s["texts"]) + len(s["dialogs"]), TEXTS_PER_BATCH, 3),
            "visual": pack(visual, lambda s: len(s["thumbs"]) + len(s["dialogs"]), IMAGES_PER_BATCH, 4)}


def tokens(f: Path) -> int:
    """Estimated tokens for a model reading the file: an image by its pixels, text by its bytes."""
    b = f.read_bytes()
    if f.suffix == ".txt":
        return len(b) // 4
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", b[16:24])
    else:  # JPEG: the size is in the first start-of-frame segment
        i = 2
        while b[i + 1] not in (0xC0, 0xC1, 0xC2):
            i += 2 + struct.unpack(">H", b[i + 2:i + 4])[0]
        h, w = struct.unpack(">HH", b[i + 5:i + 9])
    s = min(1, 1568 / max(w, h), math.sqrt(1_150_000 / (w * h)))
    return round(w * h * s * s / 750)


def size(paths) -> dict:
    files = [Path(p) for p in dict.fromkeys(paths) if p and Path(p).exists()]
    return {"files": len(files), "bytes": sum(f.stat().st_size for f in files), "tokens": sum(map(tokens, files))}


def shared_browser(profile: Path) -> tuple[subprocess.Popen, str]:
    """One headless Chromium for all the crawls (each connects over CDP and opens its own context): its DevTools URL."""
    with sync_playwright() as p:
        exe = Path(p.chromium.executable_path)
    if not exe.exists():  # only the headless shell installed (playwright install --only-shell)
        exe = next(Path.home().glob(".cache/ms-playwright/chromium_headless_shell-*/*/chrome-headless-shell"), exe)
    profile.mkdir(parents=True, exist_ok=True)
    log = profile / "chromium.log"
    proc = subprocess.Popen([str(exe), "--headless=new", "--remote-debugging-port=0", f"--user-data-dir={profile}",
                             "--no-first-run", "--no-default-browser-check", "about:blank"], stdout=subprocess.DEVNULL, stderr=log.open("w"))
    for _ in range(100):  # Chromium prints its endpoint once it listens
        if m := re.search(r"DevTools listening on (ws://\S+)", log.read_text(errors="ignore")):
            return proc, m.group(1)
        time.sleep(0.1)
    proc.kill()
    sys.exit(f"the shared Chromium did not start ({exe}); see {log}, or pass --browsers separate")


def auto_workers() -> int:
    """Browsers to run at once: half the CPUs, and about one per 700 MB of free memory, between 2 and 6."""
    cpus = (os.cpu_count() or 2) // 2
    try:
        free_kb = next(int(x.split()[1]) for x in open("/proc/meminfo") if x.startswith("MemAvailable"))
        mem = free_kb // 700_000
    except (OSError, StopIteration):  # macOS: no /proc; the CPU count decides
        mem = cpus
    return max(2, min(6, cpus, mem))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("app", help="the running app's URL")
    ap.add_argument("--repo", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--frontend", type=Path, help="the frontend's src folder; default: frontend/src, web/src, src...")
    ap.add_argument("--variants", nargs="+", help="light, dark and language codes; default: light dark <the longest language>")
    ap.add_argument("--routes", nargs="+", default=[], help="real paths (/r/sales): start paths, and ids for the $param routes")
    ap.add_argument("--max-screens", type=int, default=80, help="per variant")
    ap.add_argument("--browsers", choices=["shared", "separate"], default="shared",
                    help="shared: one Chromium, each crawl a tab in it (less memory, same speed); separate: one Chromium per crawl")
    ap.add_argument("--workers", type=int, help="browsers in parallel across all crawls (default: from CPUs and free memory)")
    ap.add_argument("--open-label", default=OPEN_LABEL, help="buttons the light crawl opens (crawl.py --open-label)")
    ap.add_argument("--theme-key", help="localStorage key of the theme, when the one found is wrong")
    ap.add_argument("--lang-key", help="localStorage key of the language, when the one found is wrong")
    args, crawl_extra = ap.parse_known_args()
    wall = time.monotonic()
    app, out = args.app.rstrip("/"), args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    seconds: dict[str, float] = {}

    t = time.monotonic()
    d = discover(args.repo.resolve(), args.frontend.resolve() if args.frontend else None)
    theme_keys, lang_keys = [args.theme_key] if args.theme_key else d["theme_keys"], [args.lang_key] if args.lang_key else d["lang_keys"]
    variants = args.variants or ["light", "dark", *([d["longest"]] if d["longest"] else [])]
    lang = next((v for v in variants if v not in ("light", "dark")), None)
    seconds["discover"] = round(time.monotonic() - t, 1)

    t = time.monotonic()
    pr = probe(app, d["routes"], args.routes, theme_keys, lang_keys, lang)
    seconds["probe"] = round(time.monotonic() - t, 1)
    starts, skipped = list(args.routes), []
    for r in d["routes"]:
        path, missing = fill(r, pr["ids"])
        if path:
            starts.append(path)
        else:
            skipped.append({"route": r, "why": f"no id for {missing} in the app's links: pass a real path with --routes"})
    starts = sorted(dict.fromkeys(starts), key=lambda p: (p != "/", p))

    crawl = [sys.executable, str(HERE / "crawl.py"), app, "--thumb", *crawl_extra]  # starts and caps are added per shard
    jobs = {"scan": ([sys.executable, str(HERE / "scan.py"), *d["scan_roots"]], out / "scan.md")}
    dirs: dict[str, Path] = {}
    if "light" in variants:
        dirs["light"] = out / "light"
        jobs["crawl-light"] = (crawl + ["--out", str(dirs["light"]), "--open-dialogs", "5", "--open-label", args.open_label,
                                        "--open-dropdowns", "5"] + (["--also-dark"] if pr["dark_via"] == "preference" else []), out / "light.log")
    if "dark" in variants and not pr["dark_via"]:
        skipped.append({"route": "dark", "why": f"neither the browser preference nor {theme_keys} turned the page dark: pass --theme-key"})
    if "dark" in variants and pr["dark_via"] and not ("light" in variants and pr["dark_via"] == "preference"):
        dirs["dark"] = out / "dark"
        mode = ["--color-scheme", "dark"] if pr["dark_via"] == "preference" else ["--storage", pr["theme"]]
        jobs["crawl-dark"] = (crawl + ["--out", str(dirs["dark"]), *mode], out / "dark.log")
    for v in variants:
        if v not in ("light", "dark"):
            if not pr["lang_key"]:
                skipped.append({"route": f"language {v}", "why": f"no key of {lang_keys} set <html lang> to {v}: pass --lang-key"})
                continue
            dirs[v] = out / v
            jobs[f"crawl-{v}"] = (crawl + ["--out", str(dirs[v]), "--storage", f"{pr['lang_key']}={v}"], out / f"{v}.log")
    # each variant's crawl split into shards: browsers share a claims folder so no screen or popup is done twice
    crawls = [n for n in jobs if n.startswith("crawl-")]
    workers = max(len(crawls), args.workers or auto_workers())
    shards = {n: max(1, workers // len(crawls) + (1 if i < workers % len(crawls) else 0)) for i, n in enumerate(crawls)}
    run: dict[str, tuple[list[str], Path]] = {"scan": jobs["scan"]}
    for n in crawls:
        cmd, log = jobs[n]
        vdir = Path(cmd[cmd.index("--out") + 1])
        k = shards[n]
        for i in range(k):  # the routes dealt round-robin; links found on the way are shared through the claims
            mine = starts[i::k]
            run[f"{n}#{i}"] = (cmd + ["--claims", str(vdir / ".claims"), "--shard", str(i), "--max-screens", str(math.ceil(args.max_screens / k)),
                                      *[a for s in mine for a in ("--start", s)]], log.with_name(f"{log.stem}-{i}.log"))
    shared = shared_browser(out / ".chromium") if args.browsers == "shared" else None
    if shared:
        run = {n: (cmd + ["--cdp", shared[1]] if n.startswith("crawl-") else cmd, log) for n, (cmd, log) in run.items()}
    try:
        with ThreadPoolExecutor(len(run)) as pool:
            done = {name: pool.submit(timed, cmd, log) for name, (cmd, log) in run.items()}
            results = {name: f.result() for name, f in done.items()}
    finally:
        if shared:
            shared[0].terminate()
            shared[0].wait(timeout=10)
            shutil.rmtree(out / ".chromium", ignore_errors=True)
    seconds["scan"] = results["scan"][1]
    for n in crawls:  # a variant takes as long as its slowest shard; then its shards are merged into report.json
        seconds[n] = max(s for name, (_, s) in results.items() if name.split("#")[0] == n)
        vdir = Path(jobs[n][0][jobs[n][0].index("--out") + 1])
        subprocess.run([sys.executable, str(HERE / "crawl.py"), "--summarize", str(vdir)], stdout=subprocess.DEVNULL, check=False)
    seconds["workers"] = workers

    t = time.monotonic()
    reports = {v: p / "report.json" for v, p in dirs.items() if (p / "report.json").exists()}
    b = batches(reports, d["routes"]) if reports else {"shared": [], "text": [], "visual": []}
    b = {"scan": str(out / "scan.md"), "summaries": {v: str(p / "summary.md") for v, p in dirs.items()}, **b}
    (out / "batches.json").write_text(json.dumps(b, indent=1, ensure_ascii=False))
    seconds["batches"] = round(time.monotonic() - t, 1)

    entries = {v: json.loads(p.read_text()) for v, p in reports.items()}
    paths = {e["path"].split("?")[0] for es in entries.values() for e in es if " > " not in e["path"]}
    covered, not_covered, why = [], [], {x["route"]: x["why"] for x in skipped}
    for r in d["routes"]:  # a route with no id can still be reached through a link during the crawl
        hit = next((p for p in sorted(paths) if route_rx(r).match(p)), None)
        (covered.append({"route": r, "path": hit}) if hit else
         not_covered.append({"route": r, "why": why.get(r, "not crawled: the screen cap (--max-screens) or the crawl's --exclude")}))
    every = [x for es in entries.values() for e in es for x in (e.get("file"), e.get("dark", {}).get("file"))]
    shown = [x for bt in b["visual"] for s in bt["screens"] for x in [*s["thumbs"].values(), *(dl["thumb"] for dl in s["dialogs"])]]
    crops = [p.get("crop") for es in entries.values() for e in es for p in e.get("problems", []) + e.get("dark", {}).get("problems", [])]
    texts = [x for bt in b["text"] for s in bt["screens"] for x in [*s["texts"].values(), *(dl["text"] for dl in s["dialogs"])]]
    seconds["wall"] = round(time.monotonic() - wall, 1)
    manifest = {
        "app": app, "repo": str(args.repo.resolve()), "frontend": d["frontend"], "router": d["router"],
        "theme": {"setting": pr["theme"], "candidates": theme_keys, "dark_via": pr["dark_via"]},
        "language": {"key": pr["lang_key"], "candidates": lang_keys, "languages": d["languages"], "longest": d["longest"]},
        "catalog": d["catalog"], "scan": {"file": str(out / "scan.md"), "roots": d["scan_roots"], "exit": results["scan"][0]},
        "variants": {v: {"dir": str(p), "exit": max((r[0] or 0) for name, r in results.items() if name.split("#")[0] == f"crawl-{v}"), "screens": len(entries.get(v, []))} for v, p in dirs.items()}
        | ({"dark": {"dir": str(dirs["light"] / "dark"), "exit": None, "screens": sum("dark" in e for e in entries.get("light", []))}}
           if pr["dark_via"] == "preference" and "light" in dirs and "dark" in variants else {}),
        "routes": {"covered": covered, "not_covered": not_covered + [x for x in skipped if not x["route"].startswith("/")]},
        "images": {"every_screen": size(every), "visual_batches": size(shown), "crops": size(crops), "text_batches": size(texts)},
        "seconds": seconds,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False))
    print(json.dumps({k: manifest[k] for k in ("theme", "language", "images", "seconds")}, indent=1))
    print(f"routes: {len(covered)} covered, {len(manifest['routes']['not_covered'])} not; batches: "
          f"{len(b['text'])} text, {len(b['visual'])} visual\nmanifest: {out / 'manifest.json'}\nbatches: {out / 'batches.json'}")
    return 1 if any(code for code, _ in results.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
