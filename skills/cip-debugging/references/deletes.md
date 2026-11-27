# CIP deletes — how they happen and how to investigate

Unexpected deletes are the most frequent and most damaging CIP incident: a product disappears from a
shop overnight and nobody touched it. There are several independent code paths that can delete, so
first find out **which path and which job** sent the delete, then why it considered the id gone.

## The delete paths

| Path | Where | When it deletes | Guard rails |
|---|---|---|---|
| Feed upload | `distribution/cip/upload_to_cip.py` (post_run of every feed job, `do_deletes: true`) | Rows of the feed table with `__is_deleted = true` (only those with `__timestamp > latest - 5 days` unless `force_full_deletes`) | `cross_feed_tables` suppression; >80% mass-delete abort; logs `operation=delete` only for ids CIP confirmed (202) |
| Manual delete | `distribution/cip/deletes_to_cip.py` | Exactly the `ids` you pass | None — it's manual |
| Orphan cleanup | `distribution/cip/deletes_cleanup_cip.py` (job `deletes_cleanup_prod`, manual, `dry_run: 'true'` in prod) | Ids whose latest logged op is `insert` but that are no longer live in any healthy current table | Skips empty/missing tables; 80% guard per item; dry_run writes `dry_delete` |
| Promo cleanup | `distribution/cip/pre_promotion_cleanup.py` | Promo ids before a swap | `dry_run` widget |
| cip2 | `distribution/cip2/*` | Same notebooks, separate pipeline | Still test/acc-only and manual (check `_config.cip2.yml`) |

The delete **endpoint** is derived from the upload endpoint (`products/lead-times/batch-upsert` →
`products/lead-times/batch-delete`) since commit 435a94175. Before that, any job without
`api_delete_endpoint` defaulted to `products/batch-delete` — i.e. deleted **whole products**. If you
investigate a delete before 26 Nov 2026, keep that in mind.

## Why a feed marks an id `__is_deleted`

Feed jobs are `mode: update` + `change_data_capture: scd1`: an id that drops out of the query result
gets a tombstone. An id drops out when any filter in the feed SQL stops matching, e.g. for plumbing
(`product_plumbing_base_prod.sql`): Akeneo `enabled`, `is_online_channel`, `cip_logistics_classification`,
not in the promotion feed (`left anti join` on `cip_product_promotion_base_prod`), `packageInformation`
not null, category in the SPT tree, at least one visible characteristic. **Moving a product from one
feed to another (e.g. into a promotion) makes the old feed send a delete** — that is exactly what
`cross_feed_tables` exists to suppress.

## Known incidents (learn from these)

- **Cross-feed deletes (3 Nov, 76e28b336)** — a feed deleted an id another feed of the same brand still
  served. Fix: `cross_feed_tables` on each getaz/richner product job; ids live (`__is_current` and not
  `__is_deleted`) in any listed table are not deleted. When you add a new feed for a brand, **add it to
  the `cross_feed_tables` of every other feed of that brand** (a quick awk over the config shows which
  jobs list which tables).
- **Missing cross-feed table disabled the suppression silently (25 Nov, 0c703936f)** — now raises.
  Same commit: promo jobs in prod have `do_deletes: false` (removals are done on purpose, manually).
- **lead_time upload deleted whole products every night (26 Nov, 136b8831f, b656e725f, 435a94175,
  0699e28a1)** — Getaz lead_time had `do_deletes: true` and no `api_delete_endpoint`; promo articles left
  the base → their lead-time rows became `__is_deleted` → `products/batch-delete`. It was invisible
  because the job had no `log_uri`. Now: lead_time `do_deletes: false`, endpoint derived, and jobs
  without `log_uri` log deletes to `<error_uri dir>/logs`.
- **Mass-delete guard blocked an intended promo swap** — `Delete count 3 is >80% of current rows (3)`.
  For a deliberate swap, rerun `upload_to_cip` for the promo jobs with `force_full_deletes=true` (with
  the user's OK); don't change the config.

## Investigation recipe

1. **Confirm it's gone** — detail page 404 (see `shop-checks.md`) vs. just not searchable.
2. **Who deleted it** — all logged operations for the id across every feed:
   ```sql
   select item, env, operation, min(timestamp) first_ts, max(timestamp) last_ts, count(*) n
   from parquet.`abfss://distribution@bmsstaprdeuwdatastoresnd.dfs.core.windows.net/cip/*/logs/logs`
   where id = '<id>' group by all order by last_ts
   ```
   Also check the side logs of jobs without `log_uri` (lead_time, relations):
   `.../cip/<item>/logs/logs` next to their `error_uri`. A delete that appears nowhere was either sent
   before the delete-logging fix, by a manual notebook, or by CIP itself.
   Manual notebooks never log, so if the logs show no delete, go to step 6.
   Log dirs are named per item **without always carrying the env**. Filter on the `env` column; prod
   rows are `prd` or, in older rows, `prod`. Remember that `insert` rows copy the whole table, tombstones
   included, so they don't prove a send.
3. **Why the feed tombstoned it** — current state of the id in every CIP table:
   ```sql
   show tables in distribution like 'cip_product*_prod'
   ```
   then per table `select __is_current, __is_deleted, __timestamp from ... where productIdentification.id = '<id>'`.
   Base tables have no `__is_current`/`__is_deleted`, so select `*` there. Attributes/classification
   tables have no `productIdentification.id`. Lead-time ids are ints.
   Then walk the feed's SQL filters against `core.dim_akeneo_product` / `core.dim_article` to find
   the one that stopped matching.
4. **Was suppression in place** — is the table that still serves the id listed in the deleting job's
   `cross_feed_tables`?
   ```bash
   awk '/^- job:/{it=""} /^    item:/{it=$2} /cross_feed_tables:/{print it": "$0}' distribution/cip/_config.cip_prod.yml
   ```
5. **Would the orphan cleanup delete it** — run `deletes_cleanup_cip` with `test_id=<id>`; it prints
   `VERDICT: WOULD DELETE … orphaned in …` (or not) and stops without sending.
6. **Manual deletes** — `deletes_to_cip` (and `pre_promotion_cleanup`) don't write the upload log, so
   a manual delete is only visible in the Databricks run history. List submitted runs and filter on
   the notebook and its parameters:
   ```bash
   DATABRICKS_AUTH_TYPE=azure-cli databricks api get "/api/2.1/jobs/runs/list?run_type=SUBMIT_RUN&expand_tasks=true&limit=25&start_time_from=<epoch ms>" -p <profile>
   ```
   - Paginate with `page_token` until `has_more` is false; one page silently misses runs.
   - Times are epoch milliseconds.
   - Keep runs whose `tasks[].notebook_task.notebook_path` ends in `deletes_to_cip` (or `pre_promotion_cleanup`) and whose `base_parameters.ids` contains the id.
   - Ignore the many `fabricks_tools_cli` runs.
   - The run gives who (`creator_user_name`), when, which secret/URL (env and brand) and a run URL.
   - Then check `git log -p -S'<id>' -- distribution/cip/` for the reason, e.g. an allow-list removal.
7. **Restore** — resend with `scripts/resend_products.py` (see SKILL.md) once the cause is fixed;
   otherwise tonight's run deletes it again.

## Safety rules for anything that deletes

- Ask the user before every delete or prod write, per environment. Go tst → acc → prod.
- `deletes_to_cip.py` widget defaults are dangerous: `key_vault_secret` defaults to
  `cip-api-headers-getaz` (no env) and `api_base_url` to tst. Always pass both explicitly, and assert
  that prod calls use a `-prd` secret and `api-prdstv2` URL.
- Read the post_run arguments from `_config.cip*.yml` (`yaml.safe_load`, `invoker_options.post_run[].arguments`)
  instead of retyping them; write one output per target (an overwrite bug once sent 9217 only to Richner).
- Send deletes first, uploads only if all deletes succeeded.
- Run the cleanup in prod as `dry_run` first and review `dry_delete` rows with `search_id_log.py`.
