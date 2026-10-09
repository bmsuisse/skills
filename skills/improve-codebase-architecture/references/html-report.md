# HTML Report Format

Render the review as a single self-contained HTML file in `$TMPDIR`
(`<tmpdir>/architecture-review-<timestamp>.html`). Diagrams carry the weight;
prose is sparse. If a diagram needs a paragraph to be understood, redraw it.

Tailwind and Mermaid come from CDNs. Use Mermaid for graph-shaped relations
(call graphs, dependencies, sequences) and hand-built divs or inline SVG for
the editorial visuals (mass diagrams, cross-sections). Mix them; Mermaid alone
looks generic.

## Scaffold

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Architecture review for {{repo name}}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script type="module">
      import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
      mermaid.initialize({ startOnLoad: true, theme: "neutral" });
    </script>
    <style>
      .seam { stroke-dasharray: 4 4; }
      .leak { stroke: #dc2626; }
      .deep { background: linear-gradient(135deg, #0f172a, #1e293b); }
    </style>
  </head>
  <body class="bg-stone-50 text-slate-900 font-sans">
    <main class="max-w-5xl mx-auto px-6 py-12 space-y-12">
      <header>...</header>
      <section id="candidates" class="space-y-10">...</section>
      <section id="top-recommendation">...</section>
    </main>
  </body>
</html>
```

## Header

Repo name, date, and a compact legend: solid box = module, dashed line = seam,
red arrow = leakage, thick dark box = deep module. No intro paragraph.

## Candidate card

One `<article>` per candidate:

- **Title**: names the deepening, e.g. "Collapse the order intake pipeline".
- **Badges**: recommendation strength (`Strong` emerald, `Worth exploring`
  amber, `Speculative` slate) and dependency category (`in-process`,
  `local-substitutable`, `ports & adapters`, `mock`).
- **Files**: monospaced list.
- **Before / After diagram**: two columns side by side, the centrepiece.
- **Problem**: one sentence. **Solution**: one sentence.
- **Wins**: bullets of at most six words, e.g. "Tests hit one interface",
  "Delete 4 shallow wrappers".
- **ADR callout** (if relevant): one line in an amber box.

## Diagram patterns

Pick what fits each candidate and vary them:

- **Collapse**: many small boxes with arrows between them on the left, one
  thick dark box with a single entry arrow on the right.
- **Leak**: two modules with a red arrow crossing a dashed seam line; after,
  the arrow is gone and the logic lives inside one module.
- **Mass diagram**: boxes sized by interface vs implementation, showing the
  interface shrinking while implementation stays.
- **Call graph / sequence** (Mermaid): who calls whom before, and after.

Keep text inside diagrams short; label with the project's domain terms.

## Top recommendation

Which candidate to tackle first and why, in two or three sentences.
