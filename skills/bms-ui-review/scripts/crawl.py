#!/usr/bin/env python3
"""Crawl a web app's screens: full-page screenshots, automatic UI checks and a style inventory.

Follows same-origin links (<a href>) breadth-first from the start paths, so it finds every screen a user can
reach from the navigation. One run is one variant (light, dark, a language); run it once per variant.

    uv run --with playwright python crawl.py http://localhost:5173 --out shots/light
    uv run --with playwright python crawl.py http://localhost:5173 --out shots/dark --color-scheme dark
    uv run --with playwright python crawl.py http://localhost:5173 --out shots/fr --storage app.lang=fr
    ... --start /admin --start /reports/x   (extra start paths: screens no link reaches)
    ... --exclude '/logout|/print'          (never visit: sign-out, downloads, destructive links)
    ... --storage-state auth.json           (a signed-in session, from Playwright's storage_state)

Writes <out>/<slug>.png and <slug>.txt (the visible text, tagged by role) per screen and dialog, <out>/report.json
(per screen: path, title, file, text, thumb, problems with box and crop, styles, graphics) and <out>/summary.md. Never clicks buttons or submits forms: it only follows links, so it changes nothing.
"""

from __future__ import annotations

import argparse
import base64
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Page, sync_playwright

ID = re.compile(r"^(\d+|[0-9a-f]{8,}|[0-9a-f-]{36})$", re.I)

# Runs in the page: problems a script can find, and the styles in use (for cross-screen consistency).
PROBE = r"""() => {
  const out = [], add = (kind, where, detail, el) => {  // el: an element or a rect, kept as a page box for a crop
    const p = {kind, where, detail}, r = el && (el instanceof Element ? el.getBoundingClientRect() : el);
    if (r && r.width > 0 && r.height > 0) p.box = [r.left + scrollX, r.top + scrollY, r.width, r.height].map(Math.round);
    out.push(p); };
  const vis = (e) => { const r = e.getBoundingClientRect(), s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && +s.opacity > 0; };
  const name = (e) => (e.getAttribute('data-testid') || e.getAttribute('aria-label') || e.innerText || e.tagName)
    .trim().replace(/\s+/g, ' ').slice(0, 60);
  const doc = document.documentElement;
  if (doc.scrollWidth > doc.clientWidth + 1) add('page-overflow', 'page', (doc.scrollWidth - doc.clientWidth) + 'px wider than the window');

  // text: placeholders that leaked, untranslated keys, clipped text without an ellipsis, tiny text
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  while (walker.nextNode()) {
    const t = walker.currentNode.textContent.trim(), el = walker.currentNode.parentElement;
    if (!t || !el || !vis(el) || seen.has(el)) continue;
    seen.add(el);
    if (/\b(undefined|NaN|null|\[object Object\])\b/.test(t)) add('leaked-value', name(el), t.slice(0, 80), el);
    if (/^[a-z][a-zA-Z0-9]*(\.[a-zA-Z0-9_]+){1,}$/.test(t) && !/\.(com|ch|json|md|csv|xlsx|py|ts)$/.test(t)) add('i18n-key', name(el), t, el);
    const s = getComputedStyle(el);
    if (parseFloat(s.fontSize) < 11) add('tiny-text', name(el), s.fontSize, el);
    if (el.clientWidth > 2 && el.scrollWidth > el.clientWidth + 1 && s.overflow.includes('hidden') && s.textOverflow !== 'ellipsis' && !el.title)
      add('clipped-text', name(el), 'cut off, no ellipsis, no title', el);
  }
  // contrast of text against the first opaque background behind it (WCAG AA: 4.5, 3 for large text)
  // any CSS colour (oklch, color(), rgb) to [r, g, b, a 0..255] through a 1x1 canvas
  const cx = Object.assign(document.createElement('canvas'), {width: 1, height: 1}).getContext('2d', {willReadFrequently: true});
  const rgb = (c) => { cx.clearRect(0, 0, 1, 1); cx.fillStyle = '#000'; cx.fillStyle = c; cx.fillRect(0, 0, 1, 1); return [...cx.getImageData(0, 0, 1, 1).data]; };
  const lum = ([r, g, b]) => { const f = (v) => (v /= 255) <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const bg = (e) => { for (; e; e = e.parentElement) { const c = rgb(getComputedStyle(e).backgroundColor);
    if (c[3] > 230) return c; } return [255, 255, 255, 255]; };
  const checked = new Set();
  for (const el of seen) {
    const s = getComputedStyle(el), c = rgb(s.color);
    if (c[3] < 128) continue;
    const key = s.color + '|' + bg(el).join(',');
    if (checked.has(key)) continue; checked.add(key);
    const [a, b] = [lum(c), lum(bg(el))], ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    const large = parseFloat(s.fontSize) >= 24 || (parseFloat(s.fontSize) >= 18.66 && +s.fontWeight >= 700);
    if (ratio < (large ? 3 : 4.5)) add('low-contrast', name(el), ratio.toFixed(2) + ':1 (' + s.color + ')', el);
  }
  // controls without an accessible name, images without alt, duplicate ids
  document.querySelectorAll('button, a[href], [role=button], input, select, textarea').forEach((e) => {
    if (!vis(e)) return;
    const label = e.getAttribute('aria-label') || e.getAttribute('aria-labelledby') || e.title || e.innerText.trim()
      || (e.id && document.querySelector('label[for="' + e.id + '"]')) || e.closest('label') || e.getAttribute('placeholder');
    if (!label) add('no-accessible-name', e.tagName.toLowerCase(), e.outerHTML.slice(0, 100), e);
  });
  // a scrollbar inside the page (cards, tiles, panels): usually content that does not fit its box
  document.querySelectorAll('body *').forEach((e) => {
    if (!vis(e) || e.matches('main, [role=main], nav, aside, table, [role=grid], [role=listbox], [role=dialog] > *')) return;
    const s = getComputedStyle(e);
    const y = /(auto|scroll)/.test(s.overflowY) && e.scrollHeight > e.clientHeight + 2 && e.clientHeight < innerHeight * 0.6;
    const x = /(auto|scroll)/.test(s.overflowX) && e.scrollWidth > e.clientWidth + 2 && !e.querySelector('table, [role=grid]');
    if (x || y) add('inner-scrollbar', name(e), (x ? 'sideways ' : '') + (y ? 'vertical' : '') + ' scrollbar in a ' + Math.round(e.clientWidth) + 'x' + Math.round(e.clientHeight) + ' box', e);
  });
  // a row of controls whose vertical centres differ (items-start with mixed heights): buttons and chips off one line
  document.querySelectorAll('body *').forEach((row) => {
    if (!vis(row)) return;
    const s = getComputedStyle(row);
    if (!s.display.includes('flex') || s.flexDirection !== 'row') return;
    const kids = [...row.children].filter((c) => vis(c) && (c.matches('button, [role=button], input, select, a') || c.querySelector(':scope > button, :scope > [role=button]')));
    const rows = {};  // group by wrapped line (top within 4px), then compare centres on each line
    kids.forEach((c) => { const r = c.getBoundingClientRect(); const k = Object.keys(rows).find((t) => Math.abs(t - r.top) < 4 || Math.abs((rows[t][0].top + rows[t][0].height / 2) - (r.top + r.height / 2)) < r.height / 2); (rows[k ?? r.top] ??= []).push(r); });
    Object.values(rows).forEach((line) => {
      if (line.length < 2) return;
      const centres = line.map((r) => r.top + r.height / 2), spread = Math.max(...centres) - Math.min(...centres);
      if (spread > 3) add('misaligned-row', name(row), 'controls ' + Math.round(spread) + 'px off one centre line (align-items: ' + s.alignItems + ')', row);
    });
  });
  // an open list, menu or dialog that runs past the window: options or buttons the user cannot reach
  document.querySelectorAll('[role=listbox], [role=menu], [role=dialog], [role=alertdialog]').forEach((e) => {
    if (!vis(e)) return;
    const r = e.getBoundingClientRect();
    if (r.bottom > innerHeight + 1 || r.right > innerWidth + 1 || r.top < -1 || r.left < -1)
      add('popup-offscreen', name(e), Math.round(r.left) + ',' + Math.round(r.top) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height) + ' in a ' + innerWidth + 'x' + innerHeight + ' window', e);
  });
  // an option of an open list cut short with no tooltip: the user cannot read what they would pick
  document.querySelectorAll('[role=listbox] [role=option], [role=menu] [role=menuitem]').forEach((o) => {
    if (!vis(o)) return;
    const cut = [o, ...o.querySelectorAll('*')].find((e) => e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflow !== 'visible');
    if (cut && !o.title && !cut.title) add('option-cut', name(o), 'option text cut, no tooltip', o);
  });
  // a disabled control should say why (title, aria-describedby, or a visible hint next to it)
  document.querySelectorAll('button:disabled, [aria-disabled=true]').forEach((e) => {
    if (vis(e) && !e.title && !e.getAttribute('aria-describedby') && !e.closest('[title]')) add('disabled-no-reason', name(e), 'disabled, no title or description', e);
  });
  // overlap: a control drawn over text or another control that is not its parent or child (a reset button over a
  // select's label). Glyph boxes, not element boxes, so a clear button in an input's padding is fine; each box is cut
  // to its scrolling ancestors. Left out: charts, maps, svg, canvas, aria-hidden decorations, count badges, text on
  // text (tight line boxes touch), and a popup over the page.
  const SKIP = 'svg, canvas, [aria-hidden=true], [class*=chart i], [class*=legend i], .leaflet-container, .maplibregl-map, .react-flow';
  const LAYER = '[role=dialog], [role=alertdialog], [role=menu], [role=listbox], [role=tooltip], [popover]';
  const cut = (a, b) => { const l = Math.max(a.left, b.left), t = Math.max(a.top, b.top);
    return new DOMRect(l, t, Math.min(a.right, b.right) - l, Math.min(a.bottom, b.bottom) - t); };
  // per ancestor: the box it clips to (overflow), whether it is transparent, whether it starts a layer of its own (a
  // popup, a sticky or fixed bar: what scrolls under a sticky footer is meant to)
  const anc = new Map(), look = (p) => { if (!anc.has(p)) { const s = getComputedStyle(p);
    anc.set(p, [s.overflow === 'visible' ? null : p.getBoundingClientRect(), s.opacity === '0', /fixed|sticky/.test(s.position) || p.matches(LAYER)]); }
    return anc.get(p); };
  const units = [], place = (el, r, text) => { let layer = null;
    for (let p = el; p && p !== document.body; p = p.parentElement) {
      const [c, gone, top] = look(p);
      if (gone) return;
      if (c) r = cut(r, c);
      if (r.width <= 2 || r.height <= 2) return;  // scrolled out of its box, or a sliver
      if (top && !layer) layer = p;
    }
    units.push({el, r, text, layer}); };
  const rg = document.createRange();
  for (const el of seen) {
    if (el.closest(SKIP) || (getComputedStyle(el).position === 'absolute' && el.innerText.trim().length <= 3)) continue;
    for (const n of el.childNodes) if (n.nodeType === 3 && n.textContent.trim()) { rg.selectNodeContents(n); place(el, rg.getBoundingClientRect(), true); }
  }
  document.querySelectorAll('button, a[href], [role=button], [role=combobox], [role=tab], [role=switch], [role=checkbox], input:not([type=hidden]), select, textarea').forEach((el) => {
    if (!vis(el) || el.closest(SKIP)) return;
    let r = el.getBoundingClientRect();
    if (el.matches('input, select, textarea')) { const s = getComputedStyle(el), pl = parseFloat(s.paddingLeft);
      r = new DOMRect(r.left + pl, r.top, r.width - pl - parseFloat(s.paddingRight), r.height); }
    place(el, r, false);
  });
  const pairs = new Set();
  units.forEach((c, i) => { if (c.text) return;
    units.forEach((u, j) => {
      if (u === c || (!u.text && j < i) || c.el.contains(u.el) || u.el.contains(c.el) || u.el.closest('label')?.control === c.el) return;
      const x = Math.min(c.r.right, u.r.right) - Math.max(c.r.left, u.r.left), y = Math.min(c.r.bottom, u.r.bottom) - Math.max(c.r.top, u.r.top);
      if (x <= 2 || y <= 2 || c.layer !== u.layer) return;
      const key = [name(c.el), name(u.el)].sort().join(' / ');  // one finding per pair, whichever side found it
      if (pairs.has(key)) return;
      pairs.add(key);
      const l = Math.min(c.r.left, u.r.left), t = Math.min(c.r.top, u.r.top);
      add('overlap', key, Math.round(x) + 'x' + Math.round(y) + 'px drawn over each other',
        new DOMRect(l, t, Math.max(c.r.right, u.r.right) - l, Math.max(c.r.bottom, u.r.bottom) - t));
    });
  });
  document.querySelectorAll('img:not([alt])').forEach((e) => vis(e) && add('img-no-alt', 'img', e.src.slice(-60), e));
  const idc = {}; document.querySelectorAll('[id]').forEach((e) => idc[e.id] = (idc[e.id] || 0) + 1);
  Object.entries(idc).filter(([, n]) => n > 1).forEach(([id, n]) => add('duplicate-id', id, n + ' times'));

  // style inventory: what a consistent UI keeps few of
  const inv = {font: {}, radius: {}, buttonHeight: {}, h1: [], color: {}, actions: {}};
  const bump = (m, k) => m[k] = (m[k] || 0) + 1;
  document.querySelectorAll('body *').forEach((e) => {
    if (!vis(e)) return;
    const s = getComputedStyle(e);
    if (e.childNodes.length && [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()))
      { bump(inv.font, s.fontSize + ' ' + s.fontWeight); bump(inv.color, s.color); }
    if (s.borderRadius !== '0px') bump(inv.radius, s.borderRadius.split(' ').map((r) => parseFloat(r) >= 999 ? 'pill' : r).join(' '));
    if (e.matches('button, [role=button]') && e.getBoundingClientRect().height >= 16) bump(inv.buttonHeight, Math.round(e.getBoundingClientRect().height) + 'px');
    if (e.matches('button, [role=button], [role=menuitem], [role=tab], a[href]')) {
      const t = (e.innerText || e.getAttribute('aria-label') || e.title || '').trim().replace(/\s+/g, ' ');
      if (t && t.length <= 40) bump(inv.actions, t);
    }
  });
  document.querySelectorAll('h1').forEach((e) => vis(e) && inv.h1.push(e.innerText.trim().slice(0, 60)));
  const graphics = !!document.querySelector('canvas') || [...document.querySelectorAll('svg')].some((e) => {
    const r = e.getBoundingClientRect(); return r.width > 150 && r.height > 100; });  // a chart, a map or a diagram
  return {problems: out, styles: inv, graphics};
}"""


# Runs in the page: the visible text in reading order, one line per thing, tagged by role, for the text reviewers.
TEXT = r"""(rootSel) => {
  const root = rootSel ? [...document.querySelectorAll(rootSel)].filter((e) => e.getBoundingClientRect().width > 0).pop() : document.body;
  if (!root) return '';
  const lines = [], seen = new Set();
  const clean = (t) => (t || '').replace(/\s+/g, ' ').trim().slice(0, 160);
  const push = (tag, t) => { t = clean(t); const l = tag + ': ' + t; if (t && !seen.has(l)) { seen.add(l); lines.push(l); } };
  const named = (e) => clean(e.getAttribute('aria-label') || e.innerText || e.title || e.getAttribute('placeholder'));
  const walk = (e) => {
    const s = getComputedStyle(e);
    if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0' || e.getAttribute('aria-hidden') === 'true') return;
    const tag = e.tagName.toLowerCase(), role = e.getAttribute('role');
    if (/^h[1-3]$/.test(tag)) return push(tag, e.innerText);
    if (e.matches('[aria-label*=breadcrumb i]')) return push('breadcrumb', e.innerText.split('\n').filter((x) => x.trim()).join(' > '));
    if (e.matches('table, [role=grid], [role=table], [role=treegrid]')) {
      push('table', [...e.querySelectorAll('th, [role=columnheader]')].map(named).join(' | '));
      [...e.querySelectorAll('tr, [role=row]')].filter((r) => r.querySelector('td, [role=gridcell], [role=cell]')).slice(0, 3)
        .forEach((r) => push('row', [...r.querySelectorAll('td, [role=gridcell], [role=cell]')].map(named).join(' | ')));
      return;
    }
    if (e.matches('[role=alert], [role=status], [data-sonner-toast]')) return push('alert', e.innerText);
    if (e.matches('button, [role=button], [role=tab], [role=menuitem], [role=option]'))  // a select shows its value too
      return push(role || 'button', named(e) + (role === 'combobox' && e.getAttribute('aria-label') && e.innerText.trim() ? ' = ' + clean(e.innerText) : ''));
    if (e.matches('a[href]')) return push('link', named(e));
    if (e.matches('label')) return push('label', e.innerText);
    if (e.matches('input, textarea, select, [role=combobox]'))
      return push(tag === 'select' || role === 'combobox' ? 'select' : 'input', [e.getAttribute('aria-label'),
        e.getAttribute('placeholder') && '[' + e.getAttribute('placeholder') + ']', e.value && '= ' + e.value].filter(Boolean).join(' '));
    for (const n of e.childNodes) n.nodeType === 3 ? push('text', n.textContent) : n.nodeType === 1 && walk(n);
  };
  walk(root);
  const out = lines.join('\n');
  return out.length > 4000 ? out.slice(0, 4000) + '\n... (cut at 4 kB)' : out;
}"""


# Words that name the same kind of action; more than one of a set in one app is a lead for the consistency review
# (not always a finding: "Discard" changes and "Cancel" an action can be meant differently).
SYNONYMS = [
    {"cancel", "discard", "close", "dismiss", "abort", "abbrechen", "verwerfen", "schliessen", "schließen", "annuler", "fermer", "abandonner", "annulla", "chiudi", "scarta"},
    {"delete", "remove", "erase", "löschen", "loeschen", "entfernen", "supprimer", "retirer", "elimina", "rimuovi"},
    {"save", "apply", "ok", "confirm", "done", "submit", "speichern", "anwenden", "übernehmen", "enregistrer", "appliquer", "valider", "salva", "applica", "conferma"},
    {"add", "new", "create", "hinzufügen", "neu", "erstellen", "ajouter", "nouveau", "créer", "aggiungi", "nuovo", "crea"},
    {"edit", "modify", "change", "bearbeiten", "ändern", "modifier", "modifica"},
    {"search", "find", "suchen", "rechercher", "cerca"},
    {"undo", "revert", "reset", "rückgängig", "zurücksetzen", "annuler", "réinitialiser", "ripristina"},
]


def pattern(path: str) -> str:
    """ids replaced by *; a query keeps its keys, not its values (?page=1 and ?page=2 are one pattern)."""
    p, _, q = path.partition("?")
    keys = "&".join(sorted(k.split("=")[0] for k in q.split("&") if k))
    return "/".join("*" if ID.match(s) else s for s in p.split("/")) + (f"?{keys}" if keys else "")


def slug(path: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-") or "home"


def settle(page: Page, ms: int) -> None:
    """Wait for the network to go quiet and spinners or skeletons to go away."""
    try:  # an app that polls never goes quiet: a short cap, then the spinner check below decides
        page.wait_for_load_state("networkidle", timeout=min(ms, 3000))
    except Exception:
        pass
    for _ in range(ms // 250):
        if not page.evaluate("""() => !!document.querySelector('[aria-busy=true], .animate-pulse, .animate-spin')"""):
            break
        page.wait_for_timeout(250)
    still(page)
    page.wait_for_timeout(400)


def still(page: Page) -> None:
    """Finite animations and CSS transitions (chart entrances, slide-ins, a theme's colour fade) end; spinners are ignored."""
    page.wait_for_timeout(100)  # a transition starts on the next style pass
    try:
        page.wait_for_function(
            "() => document.getAnimations().every(a => a.playState !== 'running' || a.effect?.getTiming().iterations === Infinity)",
            timeout=5000,
        )
    except Exception:
        pass


THUMB_WIDTH = 1000  # px: a viewport copy a model reads for about a third of a full page's tokens
MAX_CROPS = 12  # per screen


def capture(page: Page, shot: Path, problems: list[dict], thumb: bool, text_root: str | None = "") -> dict:
    """The full-page shot; with thumb also a small JPEG of the viewport and a crop around each finding that has a box
    (its path goes into the finding); the text extract (text_root: a CSS selector, "" the whole page, None no text)."""
    page.screenshot(path=str(shot), full_page=True)
    files = {"file": str(shot)}
    if text_root is not None:
        txt = shot.with_suffix(".txt")
        txt.write_text(page.evaluate(TEXT, text_root))
        files["text"] = str(txt)
    if not thumb:
        return files
    vw, vh = page.viewport_size["width"], page.viewport_size["height"]
    cdp = page.context.new_cdp_session(page)  # Chromium scales the capture itself: no image library needed
    data = cdp.send("Page.captureScreenshot", {"format": "jpeg", "quality": 70,
                                               "clip": {"x": 0, "y": 0, "width": vw, "height": vh, "scale": THUMB_WIDTH / vw}})
    cdp.detach()
    small = shot.with_suffix(".thumb.jpg")
    small.write_bytes(base64.b64decode(data["data"]))
    files["thumb"] = str(small)
    n: Counter[str] = Counter()
    for p in problems:
        if "box" not in p or sum(n.values()) >= MAX_CROPS:
            continue
        n[p["kind"]] += 1
        x, y, w, h = p["box"]
        crop = shot.with_name(f"{shot.stem}--{p['kind']}-{n[p['kind']]}.png")
        try:
            page.screenshot(path=str(crop), full_page=True, clip={"x": max(0, x - 40), "y": max(0, y - 40),
                                                                  "width": min(w + 80, vw), "height": min(h + 80, vh)})
            p["crop"] = str(crop)
        except Exception:
            pass  # a box outside the page (a popup past the edge): no crop
    return files


POPUP = "[role=dialog], [role=alertdialog], [role=menu], [role=listbox]"
CLAIMS: Path | None = None  # set by main from --claims: popups are claimed across parallel crawls too
# any VISIBLE popup: a hidden menu or listbox already in the page must not count
POPUP_OPEN = f"""() => [...document.querySelectorAll('{POPUP}')].some(e => {{
  const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden'; }})"""


UNSAFE = re.compile(r"(?i)delete|remove|löschen|entfernen|supprimer|retirer|elimina|rimuovi|save|speichern|enregistrer|salva|submit|send|publish")


# a VISIBLE list: for a dropdown inside a dialog, the dialog itself must not count as "open"
LIST_OPEN = """() => [...document.querySelectorAll('[role=listbox]')].some(e => {
  const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden'; })"""


def open_popup(page: Page, t, dropdown: bool) -> None:
    """A dropdown opens from the keyboard (focus, ArrowDown: open and highlight, nothing picked; Escape cancels): a click
    can pick the option that lands under the pointer. A dialog trigger is clicked."""
    if dropdown:
        t.focus()
        page.keyboard.press("ArrowDown")
        try:
            page.wait_for_function(LIST_OPEN, timeout=1500)
            return
        except Exception:
            pass
    t.click(timeout=3000)


def open_dialogs(page: Page, path: str, out: Path, limit: int, opened: set[str], errors: list[str], base: list[dict], label_rx: str = "",
                 dropdowns: bool = False, inner_dropdowns: int = 0, scope=None, thumb: bool = False) -> list[dict]:
    """Open what a screen's popup triggers open, one at a time; capture and check it, close it with Escape.
    Reports only what the open popup adds to the screen's own findings (`base`)."""
    known = {(p["kind"], p["where"], p["detail"]) for p in base}
    found: list[dict] = []
    root = scope or page  # scope: an open dialog, to open the dropdowns inside it
    popups = root.locator("[role=combobox], [aria-haspopup=listbox]" if dropdowns
                          else "[aria-haspopup=dialog], [aria-haspopup=menu], [aria-haspopup=true]:not([role=combobox])")
    triggers = []
    if label_rx:  # first: buttons that open a form without declaring it (a "New" that opens a dialog); never a destructive one
        buttons = page.locator("button, [role=button]")
        names = buttons.evaluate_all("els => els.map(e => (e.getAttribute('aria-label') || e.innerText || e.title || '').trim())")
        triggers += [buttons.nth(i) for i, n in enumerate(names) if re.search(label_rx, n) and not UNSAFE.search(n)]
    triggers += [popups.nth(i) for i in range(popups.count())]
    for t in triggers[: limit * 3]:
        if len(found) >= limit:
            break
        try:
            if not t.is_visible() or t.is_disabled():
                continue
            label = " ".join((t.get_attribute("aria-label") or t.inner_text() or t.get_attribute("title") or t.get_attribute("placeholder") or "").split())[:40]
            if dropdowns:
                label = "list " + (label or f"#{len(found) + 1}")
            if not label or label in opened or not claim(CLAIMS, "popup:" + label):
                continue
            opened.add(label)
            errors.clear()
            open_popup(page, t, dropdowns)
            page.wait_for_function(LIST_OPEN if dropdowns else POPUP_OPEN, timeout=3000)
            if dropdowns:  # a list fills in after it opens (options rendered or fetched)
                try:
                    page.wait_for_function("() => document.querySelector('[role=listbox] [role=option], [role=listbox] :is(li, [data-value])')", timeout=3000)
                except Exception:
                    pass
            page.wait_for_timeout(600)  # dialogs slide in
            probe = page.evaluate(PROBE)
            problems = [p for p in probe["problems"] if (p["kind"], p["where"], p["detail"]) not in known]
            if dropdowns and not page.evaluate("() => [...document.querySelectorAll('[role=listbox]')].some(l => l.querySelector('[role=option], li'))"):
                problems.append({"kind": "empty-list", "where": label, "detail": "the list opens with no option and no message"})
            problems += [{"kind": "browser-error", "where": "console", "detail": d} for d in dict.fromkeys(errors)]
            files = capture(page, out / f"{slug(path)}--{slug(label)}.png", problems, thumb, POPUP)
            found.append({"path": f"{path} > {label}", "title": label, **files, "problems": problems, "styles": probe["styles"]})
            if inner_dropdowns and not dropdowns:  # the lists inside the open dialog, each closed before the dialog
                dialog = page.locator("[role=dialog]:visible, [role=alertdialog]:visible").last
                if dialog.count():
                    inner = open_dialogs(page, f"{path} > {label}", out, inner_dropdowns, opened, errors, base, dropdowns=True, scope=dialog, thumb=thumb)
                    found += inner
        except Exception:
            pass  # not a popup after all, or it did not open: move on
        finally:
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
            if scope is None and page.evaluate(POPUP_OPEN):  # a menu inside a dialog: one more Escape
                page.keyboard.press("Escape")
    return found


def claim(claims: Path | None, key: str) -> bool:
    """True when this process is the first to take key: an atomic create, so parallel crawls never repeat a screen."""
    if claims is None:
        return True
    claims.mkdir(parents=True, exist_ok=True)
    try:
        os.close(os.open(claims / hashlib.sha1(key.encode()).hexdigest(), os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        return True
    except FileExistsError:
        return False


def summarize(results: list[dict], out: Path, title: str) -> str:
    """report.json and summary.md: per screen the findings, then the style inventory and the synonyms in use."""
    (out / "report.json").write_text(json.dumps(results, indent=1, ensure_ascii=False))
    total: dict[str, Counter] = {"font": Counter(), "radius": Counter(), "buttonHeight": Counter(), "actions": Counter()}
    lines = [f"# {len(results)} screens ({title})", ""]
    for r in results:
        for k in total:
            total[k].update(r.get("styles", {}).get(k, {}))
        kinds = Counter(x["kind"] for x in r["problems"] + [{**p, "kind": "dark " + p["kind"]} for p in r.get("dark", {}).get("problems", [])])
        lines.append(f"- {r['path']}  {r.get('file', '')}  " + (", ".join(f"{k} x{n}" for k, n in kinds.items()) or "ok"))
    lines += ["", "## Style inventory (all screens)"]
    lines += [f"- {k}: {len(c)} distinct: " + ", ".join(f"{v} ({n})" for v, n in c.most_common(12)) for k, c in total.items() if k != "actions"]
    # action words: which synonyms of one set the app uses, and on which screens (first word of each label)
    where: dict[str, set[str]] = {}
    for r in results:
        for label in r.get("styles", {}).get("actions", {}):
            first = label.split(" ")[0].lower().strip(".:…")
            where.setdefault(first, set()).add(r["path"])
    lines += ["", "## Action words: synonyms in use (leads for the consistency review)"]
    for group in SYNONYMS:
        used = sorted(w for w in group if w in where)
        if len(used) > 1:
            lines.append("- " + " / ".join(f"{w} ({len(where[w])}: {', '.join(sorted(where[w])[:4])})" for w in used))
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    return "\n".join(lines)


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--summarize":  # merge the shards of one variant: report-*.json -> report.json, summary.md
        out = Path(sys.argv[2])
        shards = sorted(out.glob("report-*.json"))
        print(summarize([e for f in shards for e in json.loads(f.read_text())], out, f"merged from {len(shards)} parallel crawls"))
        return 0
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("base", help="the app's URL, e.g. http://localhost:5173")
    ap.add_argument("--out", required=True, help="folder for the screenshots and report.json")
    ap.add_argument("--start", action="append", default=[], help="a start path (repeatable); default /")
    ap.add_argument("--exclude", default=r"^/api/|/logout|/signout|/sign-out|/download|/export|/print|\.(pdf|xlsx|csv|zip|odc)$")
    ap.add_argument("--max-screens", type=int, default=80)
    ap.add_argument("--per-pattern", type=int, default=1, help="screens per route pattern (ids replaced by *)")
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--color-scheme", choices=["light", "dark"], default="light")
    ap.add_argument("--cdp", help="connect to a running Chromium (its DevTools endpoint) instead of launching one")
    ap.add_argument("--claims", type=Path, help="a folder shared by parallel crawls of one variant: each screen, route pattern and popup is claimed once (an atomic file)")
    ap.add_argument("--shard", help="this process's name among parallel crawls: writes report-<shard>.json; merge them with --summarize")
    ap.add_argument("--also-dark", action="store_true",
                    help="also capture each screen in dark in the same pass (no reload; only for an app that follows the browser's colour preference) into <out>/dark/")
    ap.add_argument("--thumb", action="store_true",
                    help="also write a 1000 px JPEG of the viewport (<slug>.thumb.jpg) and a crop per finding with a box (<slug>--<kind>-<n>.png)")
    ap.add_argument("--storage", action="append", default=[], help="localStorage key=value set before each page")
    ap.add_argument("--storage-state", help="Playwright storage_state file of a signed-in session")
    ap.add_argument("--timeout", type=int, default=20000, help="ms to wait for a screen to settle")
    ap.add_argument("--open-label", default="", metavar="REGEX",
                    help="with --open-dialogs: also open buttons whose name matches, e.g. '^(New|Settings|Share)$' (forms that only open; never Delete or Save)")
    ap.add_argument("--open-dropdowns", type=int, default=0, metavar="N",
                    help="per screen, open up to N dropdowns (comboboxes, aria-haspopup=listbox), capture and check the open list, close it with Escape; never pick a value")
    ap.add_argument("--open-dialogs", type=int, default=0, metavar="N",
                    help="per screen, open up to N controls marked aria-haspopup=dialog|menu, capture and check what opens, close it with Escape (never clicks inside)")
    args = ap.parse_args()
    global CLAIMS
    CLAIMS = args.claims

    base = args.base.rstrip("/")
    host = urlparse(base).netloc
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    exclude = re.compile(args.exclude)
    queue = [p if p.startswith("/") else "/" + p for p in (args.start or ["/"])]
    seen_paths: set[str] = set()
    per_pattern: Counter[str] = Counter()
    results: list[dict] = []
    opened: set[str] = set()  # dialog triggers already captured, by label: one capture per dialog
    storage = dict(kv.split("=", 1) for kv in args.storage)

    with sync_playwright() as p:
        # --cdp: a tab in a browser that prepare.py shares between the parallel crawls (one Chromium, less memory)
        browser = p.chromium.connect_over_cdp(args.cdp) if args.cdp else p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": args.width, "height": args.height},
            color_scheme=args.color_scheme,
            storage_state=args.storage_state,
        )
        if storage:
            ctx.add_init_script(f"Object.entries({json.dumps(storage)}).forEach(([k, v]) => localStorage.setItem(k, v))")
        page = ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(f"page error: {e}"[:200]))
        page.on("console", lambda m: errors.append(f"console: {m.text}"[:200]) if m.type == "error" else None)
        page.on("response", lambda r: errors.append(f"HTTP {r.status} {urlparse(r.url).path}") if r.status >= 400 else None)

        screens = 0
        while queue and screens < args.max_screens:
            path = queue.pop(0)
            if path in seen_paths or exclude.search(path):
                continue
            seen_paths.add(path)
            if args.claims:  # shared with the other crawls of this variant: the path, then a slot of its pattern
                if not claim(args.claims, "path:" + path) or not any(claim(args.claims, f"pattern:{pattern(path)}:{k}") for k in range(args.per_pattern)):
                    continue
            elif per_pattern[pattern(path)] >= args.per_pattern:
                continue
            per_pattern[pattern(path)] += 1
            screens += 1
            errors.clear()
            try:
                page.goto(base + path, timeout=args.timeout * 2)
            except Exception as e:  # one broken screen must not end the crawl
                results.append({"path": path, "problems": [{"kind": "navigation-failed", "where": "page", "detail": str(e)[:200]}]})
                continue
            settle(page, args.timeout)
            final = urlparse(page.url)
            probe = page.evaluate(PROBE)
            problems = probe["problems"] + [{"kind": "browser-error", "where": "console", "detail": d} for d in dict.fromkeys(errors)]
            if final.path != urlparse(base + path).path:
                problems.append({"kind": "redirected", "where": "page", "detail": f"to {final.path}"})
            files = capture(page, out / f"{slug(path)}.png", problems, args.thumb)
            results.append({"path": path, "title": page.title(), **files, "problems": problems, "styles": probe["styles"], "graphics": probe["graphics"]})
            if args.also_dark:  # the same screen in dark: switch the preference, capture, switch back; no navigation
                page.emulate_media(color_scheme="dark")
                still(page)  # a colour fade measured mid-way reports light-mode contrast as dark
                (out / "dark").mkdir(exist_ok=True)
                dark_problems = [p for p in page.evaluate(PROBE)["problems"] if p["kind"] in ("low-contrast", "popup-offscreen")]
                results[-1]["dark"] = {**capture(page, out / "dark" / f"{slug(path)}.png", dark_problems, args.thumb, None), "problems": dark_problems}
                page.emulate_media(color_scheme=args.color_scheme)
                still(page)
            if args.open_dialogs:
                results += open_dialogs(page, path, out, args.open_dialogs, opened, errors, problems, args.open_label,
                                        inner_dropdowns=args.open_dropdowns, thumb=args.thumb)
            if args.open_dropdowns:
                results += open_dialogs(page, path, out, args.open_dropdowns, opened, errors, problems, dropdowns=True, thumb=args.thumb)
            for href in page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))"):
                u = urlparse(urljoin(page.url, href))
                target = (u.path or "/") + (f"?{u.query}" if u.query else "")  # a query can pick a page (?page=2)
                if u.netloc == host and u.scheme.startswith("http") and target not in seen_paths:
                    queue.append(target)
        ctx.close()
        if not args.cdp:  # a shared browser belongs to prepare.py
            browser.close()

    if args.shard is not None:  # one of several parallel crawls: prepare.py merges them (crawl.py --summarize)
        (out / f"report-{args.shard}.json").write_text(json.dumps(results, indent=1, ensure_ascii=False))
        print(f"{len(results)} rows: {out / f'report-{args.shard}.json'}")
        return 0
    print(summarize(results, out, f"{args.color_scheme}{', ' + ', '.join(args.storage) if args.storage else ''}"))
    print(f"\nreport: {out / 'report.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
