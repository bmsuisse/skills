# Checking what CIP actually has (shop side)

Our logs only prove that we *sent* something and CIP answered 202. CIP processes asynchronously, so the
shop is the only way to see what CIP really stored and indexed. Check it as an anonymous visitor (an
isolated browser context in chrome-devtools works well) so that customer-specific assortments don't
hide anything.

| Shop | Base URL | Operating company / feed suffix |
|---|---|---|
| Gétaz-Miauton | https://getaz-miauton.ch | `*_getaz_*`, secret `cip-api-headers-getaz-<env>`, ERP branch 2003 |
| Richner | Richner e-shop (same CIP frontend; URL not verified here — ask the user) | `*_richner_*`, secret `cip-api-headers-richner-<env>`, ERP branch 9214 |

(9217 = central warehouse; the `product_promotion_9217_*` feeds go to both shops.)

## Three separate things to check

A product can be stored in CIP and still be invisible. Check each layer separately; they fail independently.

1. **Product stored** — open the detail page directly. Any slug works, only the id matters:
   `https://getaz-miauton.ch/products/d/x/<id>` — redirects/renders the real page, e.g.
   `/products/d/vanne-de-regulation-de-circulation-kemper-multi-therm-typ-141-og/9314071`.
   Page loads with data → the upsert landed. 404 → CIP never stored it, or it was deleted.
   Read `link[rel=canonical]` to get the real, shareable URL.

2. **Search index** — `https://getaz-miauton.ch/products?searchQuery=<id>`; the page shows `N Résultats`.
   Detail page OK but 0 results → the product is stored but CIP did not index it. That is on CIP's
   side; nothing in our logs will show it.

3. **Catalog (category) tree** — category pages are addressed by the *full path* of catalog ids,
   colon separated, and the URL needs **one path segment per level** (slugs themselves are ignored):
   - level 1: `/products/x?catalog=<l1>`
   - level 3: `/products/a/b/c?catalog=<l1>:<l2>:<l3>`
   - level 6: `/products/a/b/c/d/e/f?catalog=<l1>:...:<l6>`
   Too few segments → 404 even for categories that exist, so don't conclude "missing" from that.
   The page title is the category's French name if CIP knows it, `(inconnu)` / 404 if not.
   **The shop hides categories with 0 products** from navigation, so "not in the menu" ≠ "not in CIP".

   Catalog ids are `__identity` of `distribution.cip_catalog_prod` (= `xxhash64(__key)` of
   `core.dim_akeneo_product_catalog`); products reference them in `catalogs[].id`. Build a path:

   ```sql
   select concat_ws(':', c1.`__identity`, c2.`__identity`, c3.`__identity`, c4.`__identity`) path
   from distribution.cip_catalog_prod c4
   join distribution.cip_catalog_prod c3 on c3.`__identity` = c4.parent_sk
   join distribution.cip_catalog_prod c2 on c2.`__identity` = c3.parent_sk
   join distribution.cip_catalog_prod c1 on c1.`__identity` = c2.parent_sk
   where c4.`__key` = '<category key>'
   ```
   (add/remove joins for the level; `level` is a column, the root of the SPT tree is 2410893796948688121
   and is not part of the path.)

## Quick check with curl (no browser needed)

The shop renders server-side, so curl is enough for detail pages and search:

```bash
id=9314071
curl -sL "https://getaz-miauton.ch/products/d/x/$id" | grep -o -e 'rel="canonical" href="[^"]*"' -e 'N° du produit' | sort -u   # stored? + real URL
curl -sL "https://getaz-miauton.ch/products?searchQuery=$id" | grep -o '[0-9]* Résultats' | head -1                          # indexed?
curl -sL "https://getaz-miauton.ch/products/a/b/c/d/e/f?catalog=<l1>:...:<l6>" | grep -o -e '<title>[^<]*' -e '[0-9]* Résultats' | head -2   # category stored? (title) + count
```

The browser variant below is only needed when curl output looks incomplete.

## Scripted check (chrome-devtools `evaluate_script`)

Open one page on the shop first, then run this in it — it opens each URL in a child window and reads
the result count, which is much faster than navigating one by one:

```js
async () => {
  const test = async (href) => {
    const w = window.open(href);
    for (let i = 0; i < 20; i++) { await new Promise(r => setTimeout(r, 700)); if (/Résultats|404|N° du produit/.test(w.document.body.innerText)) break; }
    await new Promise(r => setTimeout(r, 800));
    const t = w.document.body.innerText;
    const r = w.document.title.split('|')[0].trim() + ' | ' + ((t.match(/\d+\s+Résultats/) || [])[0] || (/404/.test(t) ? '404' : (/N° du produit/.test(t) ? 'detail ok' : '?')));
    w.close(); return r;
  };
  const out = {};
  for (const id of ['9314071', '9311131']) {
    out['search ' + id] = await test('/products?searchQuery=' + id);
    out['detail ' + id] = await test('/products/d/x/' + id);
  }
  return out;
}
```

## Always compare with a control

Before blaming CIP, pick a *similar product that works* (same feed, similar first-upload date — find one
in the upload logs) and run the same checks. If the control is also missing, it's a general
delay/outage; if only yours is missing, diff the two payloads (see SKILL.md, step 5).
