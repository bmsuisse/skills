---
name: cip-debugging
description: Debug CIP e-shop data (Gétaz/Richner) in Fabricks.Runtime — articles or categories missing, wrong or deleted in CIP or the shop, failed distribution.cip_* uploads, CIP logs, and resending products. Use whenever CIP, getaz-miauton.ch or a missing shop article comes up.
---

Run commands from the Fabricks.Runtime repo root. `<skill-dir>` means this skill's directory (where
this SKILL.md lives); `scripts/` and `references/` below are relative to it.

# CIP debugging

CIP is BME's product platform behind the Gétaz-Miauton and Richner e-shops. We push data with
`distribution/cip/*` Fabricks jobs. Each feed job builds a table `distribution.cip_<item>`, and its
`upload_to_cip` post_run sends the rows to the CIP API. The API answers **202 and processes the data
later**. So "we sent it" and "it's in the shop" are separate questions, and most debugging means finding
the exact layer where the article stops.

```
Akeneo / OneTrade ─► core.dim_akeneo_product, core.dim_article, core.dim_akeneo_product_catalog
   ─► distribution.cip_product_<feed>_base_<env>        (filters + payload; no upload)
   ─► distribution.cip_product_<feed>_{getaz,richner}_<env>   (post_run upload_to_cip → CIP API)
         + relations_*, catalog_*, product_classification_*, lead_time_*, … (own post_runs)
   ─► CIP stores the product ─► CIP search index / category listing ─► shop
```

- **Environments:**
  - `tst`: `api-tststv2`
  - `acc`: `api-uatstv2`
  - `prd`: `api-prdstv2.bme-internal.com/cip/data-management/v1`
- **Config:** prod jobs live only in `distribution/cip/_config.cip_prod.yml`; tst and acc are in `_config.cip.yml`.
- **Operating companies:** 2003 → Getaz, 9214 → Richner, 9217 (central stock) → both.
- **Feeds** (`<feed>` above): `plumbing`, `tiles`, `wood`, `long_wood`, `dummies`, `promotion_*`, `2003`, `9214`, `tools`, `reco`.
- **Which feed an article goes to:** mostly `cip_logistics_classification` in Akeneo (e.g. `bms_plumbing_product`) plus the promotion lists.
- **Schedules:** prod sends run in the `daily` schedule at roughly 21:00–00:15 UTC. `distribution/cip2/` is a newer pipeline that is still tst/acc-only and manual.

## Tooling (read first, saves an hour)

- **Querying `distribution.*` and the log paths:**
  - The SQL warehouse and OneHub fail on these with *"This Azure storage request is not authorized … Firewalls"*.
  - Local Spark Connect fails when pyspark is installed.
  - OneHub `execute_databricks_sql` is fine for `core.*` and `fabricks.*`.
  - For everything else, use the bundled script, which runs SQL on the general-purpose cluster `0422-142111-ov7kv4xy`:
  ```bash
  python3 <skill-dir>/scripts/cluster_sql.py "select ..."      # or --file q.sql
  ```
  Queries over log globs can take several minutes, so give the command a long timeout (10 min) or run it in the background.
- **Databricks profile:**
  - It picks `premium`, or falls back to `bms` (same workspace `adb-8956277663194228`).
  - Auth is azure-cli via the existing `az login`. Don't ask the user for a browser login.
- **Logs:**
  - Both live under `abfss://distribution@bmsstaprdeuwdatastoresnd.dfs.core.windows.net/cip/<item>/logs/`.
  - **Upload log** `logs/logs`:
    - Columns: `id, item, topic, step, env, operation (insert|delete|dry_delete), timestamp`.
    - The format is mixed: a `parquet.` glob over all items works, but a single item can be Delta (`DELTA_INVALID_FORMAT` → use `delta.`).
    - The full `cip/*/logs/logs` glob takes several minutes. Narrow it when you can, e.g. `cip/product_*_prod/logs/logs` or a single item.
    - **Older `insert` rows don't prove a send.** Until Fabricks.Runtime PR 39836 (end of Nov 2026), `upload_to_cip` logged every row of the feed table as `insert` on every run, including tombstoned and non-current rows. Since that fix, an `insert` row means the id was in that run's upload and CIP accepted it (202). For older rows, confirm with the table state (`__is_current` and not `__is_deleted`) and the error table.
    - Manual notebooks (`deletes_to_cip`, resends) don't write this log. See `references/deletes.md` for finding them.
  - **Error table** `logs/error`: read it with `delta.` (`parquet.` fails). Use one path per item.
    - Columns: `batch, error_msg, timestamp`.
    - Find an article with `batch rlike '<id>'`.
    - An empty `error_msg` means CIP answered with a non-202 status and an empty body. The status code isn't logged.
    - Schema-validation failures carry the validator text instead.
  - `env` is `tst|acc|prd`, but older prod rows say `prod`. Filter prod with `env in ('prd','prod')`.
  - The upload log records **what we sent**, not CIP's verdict. Rejected batches land in the error table.
  - Timestamps are UTC. Say so when reporting; Swiss users think in CET/CEST (UTC+1/+2).
- **Key columns of `core.dim_akeneo_product`:**
  - Filter on `id` (the article number, which is what the CIP feeds use) and `__is_current`.
  - Then read `enabled`, `is_online_channel`, `cip_logistics_classification`, `categories` (array of catalog `__key`s), `created` (Akeneo) and `__metadata.inserted` / `.updated` (arrival in the DWH).
  - Attributes sit in the variant `values`, e.g. ``values:barcode[0].data``.
- **Job history:**
  - `fabricks.logs` holds the start/running/done/failed rows per job and schedule run.
  - `fabricks.last_status` holds the latest status per job.
  - For a failed post_run, use `databricks jobs get-run` and `get-run-output` for the task's trace.
- **One-off notebooks:**
  1. Import them under the workspace repo, next to the notebook they need: `/Users/<me>/Fabricks.Runtime/distribution/cip/scratch_<name>`. That makes `utils.transformers` and `json_schema/` resolve.
  2. Submit with `databricks jobs submit` on the general-purpose cluster.
  3. Read `get-run-output <task run_id>`.
  4. **Delete the scratch notebook afterwards.**

## Triage: "article X is not in CIP / the shop"

For "is X in CIP, and since when?", step 4 (first and last `insert` per env) plus the shop checks in
step 5 are enough. If both look fine, answer and stop; a control article is only needed when something
is missing.

Work through the layers in order and stop at the first one that fails. Run the same checks on a
**similar article that does work** (same feed, similar date) as a control. Without a control you can't
tell "broken for X" from "everything is slow".

1. **Which feed should carry it?** Read `core.dim_akeneo_product` (current row) for:
   - `enabled`, `is_online_channel`, `cip_logistics_classification`
   - `categories`, `created`, `__metadata`

   Map the classification to the feed, e.g. `bms_plumbing(_product)` → `product_plumbing_*`. If the
   data only arrived in core *after* the last nightly run (`__metadata.inserted` vs. the run time in
   `fabricks.logs`), the answer is simply "it goes out tonight".

2. **Does it pass the feed's filters?** Open the feed's `_base_<env>.sql` and test each `where` / join
   condition for the id. Typical drop-outs:
   - disabled, or not on the online channel
   - wrong classification
   - in the promotion feed (anti-join)
   - no `core.dim_article` row
   - `packageInformation` null
   - category not under the SPT catalog root `2410893796948688121`
   - no visible characteristics in `cip_product_attributes_<env>`

3. **Is it in the feed tables?** Check `productIdentification.id` in `cip_product_<feed>_base_<env>` and
   `_getaz_` / `_richner_` (`__is_current`, `__is_deleted`, `__timestamp`).
   - Base tables (`*_base_*`) are rebuilt in full and have no `__is_current`/`__is_deleted`.
   - `cip_lead_time_*` stores the id as an int; the others use a string.
   - If the id was in the feed and dropped out, check `git log -p -S'<id>' -- distribution/cip/` and the
     history of the feed SQL. Allow-lists (promotions, groupIds) are edited by hand, and the commit
     message usually explains the why.

4. **Was it sent, and did it fail?**
   ```sql
   select item, env, operation, min(timestamp) first_ts, max(timestamp) last_ts
   from parquet.`abfss://distribution@bmsstaprdeuwdatastoresnd.dfs.core.windows.net/cip/*/logs/logs`
   where id in ('<id>') group by all order by last_ts
   ```
   Then the error table of each relevant item, filtered with `batch rlike '<id>'`, and
   `fabricks.last_status` / `fabricks.logs` for the job. Also check the **catalog** upload
   (`cip/catalog_prod/logs/error`) when the article sits in a new category.

5. **What does CIP show?** Follow `references/shop-checks.md`. It has three independent checks:
   - **detail page:** was the product stored?
   - **search:** was it indexed?
   - **category path:** was the catalog stored?

   If all our checks pass and only search or the category listing is empty, it's CIP's index. Diff our
   payload against the control:
   ```sql
   select productIdentification.id, to_json(struct(* except(`__key`,`__timestamp`,`__is_current`,`__is_deleted`,`__hash`,`__metadata`))) j
   from distribution.cip_product_<feed>_getaz_prod where `__is_current` and productIdentification.id in ('<bad>','<good>')
   ```
   Look for values unique to the bad article across the whole feed (package units, catalog ids, GTIN,
   status codes). Then escalate to the CIP team with the evidence (see "Reporting").

6. **Deleted / disappeared overnight?** Go to `references/deletes.md`. Deletes have several independent
   causes and a dedicated recipe.

For pattern-matching against earlier cases, see `references/incidents.md` (search index, catalog
upload failure, jobs running before their source, groupId allow-list, promo per location, incremental
window).

## Resending specific products

`upload_to_cip`'s `filter_keys` widget splits on commas, but `__key` values look like
`[9314071, GLN of BMS]`, so it can't target single products. Use the bundled notebook instead. It
reads endpoint, secret, schema and log path from the feed's post_run in `_config.cip*.yml`, validates
against the JSON schema, never deletes, and appends `insert` rows to the upload log:

```bash
ME=$(DATABRICKS_AUTH_TYPE=azure-cli databricks current-user me -p <profile> --output json | python3 -c "import json,sys;print(json.load(sys.stdin)['userName'])")
NB="/Users/$ME/Fabricks.Runtime/distribution/cip/scratch_resend_products"
databricks workspace import "$NB" --file <skill-dir>/scripts/resend_products.py --format SOURCE --language PYTHON --overwrite -p <profile>
# base_parameters: ids="9314071,9314068"  items="product_plumbing_getaz_prod,product_plumbing_richner_prod"  dry_run="true"
databricks jobs submit -p <profile> --json @submit.json   # existing_cluster_id 0422-142111-ov7kv4xy, notebook_task.source WORKSPACE
databricks jobs get-run-output <task run_id> -p <profile> # notebook_output.result = JSON per item: found, missing_in_table, invalid, status
databricks workspace delete "$NB" -p <profile>
```

1. Run it with `dry_run=true` first.
2. Show the user what would be sent.
3. Get an explicit OK for the environment, then rerun with `dry_run=false`.
4. A 202 only means CIP accepted the request. Re-check the shop a few minutes later.

The Databricks repo checkout under `/Repos/...` can lag behind git. If you depend on a code change,
push it and `databricks repos update <repo id> --branch <branch>` first.

## Safety

- Prod writes are outward-facing. Confirm each one: resend, delete, full load or cleanup without `dry_run`.
- Default order is tst → acc → prod.
- Never pass widget defaults blindly. `deletes_to_cip` defaults to a tst URL and an env-less secret.
- Before any prod call, assert that the secret ends in `-prd` and the URL contains `api-prdstv2`.
- Read-only investigation (queries, shop checks, dry runs) needs no confirmation. Just do it.

## Reporting

The user wants the answer, not the journey. Lead with the layer where the article stops and the
evidence for it:
- table/log names and timestamps (UTC)
- the control article
- direct shop links, e.g. `https://getaz-miauton.ch/products/d/<slug>/<id>` (take the slug from `link[rel=canonical]`)

Give run URLs for anything you submitted. If it's CIP's side, offer a ready-to-send message (German
if the user writes German, Swiss spelling with "ss") that covers:
- what is fine on our side
- what is missing in CIP
- control articles that work
- the direct links
- the concrete question for the CIP team
