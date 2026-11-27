# Past CIP incidents (non-delete)

Delete incidents are in `deletes.md`. Use these as pattern matches: the same symptom usually has the
same cause.

## Article in all our tables and sent, but not findable in the shop — CIP search index (Nov 2026)

- **Symptom:** Kemper articles 9314068–9314073. Search on getaz-miauton.ch found nothing and the new
  Kemper categories showed "0 Résultats".
- **What we checked:**
  - The articles passed every filter of `product_plumbing_base_prod`.
  - They are current in `cip_product_plumbing_{base,getaz,richner}_prod` and in `cip_relations_plumbing_prod`.
  - Upload logs show them sent on 25 and 26 Nov, plus a manual resend on 27 Nov. Error logs are empty, so every send got a 202.
- **Shop checks:**
  - The detail page `/products/d/x/9314071` loaded with full data, so the product was stored.
  - Every Kemper category existed with its French name, so the catalog was stored.
  - Only the search index was missing the products.
  - Control articles first sent on 15 and 19 Nov were searchable, so this was not a general index delay.
- **Payload diff against a searchable control:** the only thing unique to these 6 products among about 18,000 plumbing products was the package unit `DEM` (½ pallet). Other rare units (GEB, CON, UP1, SA, EI) were searchable, so this stays a hypothesis.
- **Outcome:** escalated to the CIP team. Nothing on our side was wrong.
- **Lesson:** "not in search" ≠ "not in CIP". Check the detail page and category pages before resending or changing code.
- **Side finding:** the `fr_CH` long description contained Italian text. That is an Akeneo data issue.

## Catalog upload failed for the whole tree (26 Nov 2026)

- `distribution.cip_catalog_prod` post_run failed: `assert error_df.count() == 0`, with 8 errors on
  `products/catalogs/batch-upsert`. Each failed record is a whole level-1 tree, because the catalog
  transformer nests the full tree under each root, and `batch_size` is 100000000.
- `error_msg` was empty: CIP returned a non-202 status with an empty body, and the status code is not logged.
- The previous CIP tree stays live, so this only blocks *new or renamed* categories.
- Check `.../cip/catalog_prod/logs/error` before blaming product data when a new category is missing.
  Catalog uploads have no `log_uri`, so success leaves no trace except an empty error table and a `done` status in `fabricks.logs`.

## Akeneo change not in CIP for a day — job ran before its source (c88023ca, article 9126083)

- **How it was diagnosed:**
  - `core.dim_akeneo_product.__metadata.updated` showed the change arrived at 22:42.
  - The upload log showed the last send at 21:55.
  - `fabricks.logs` gave the order within the `daily` schedule_id.
- **Root cause:** `cip_product_wood_base_prod` and `cip_product_long_wood_base_prod` have **0 parents** in
  `fabricks.distribution_dependencies`, so they start right away instead of after the Akeneo core jobs.
  Step order is not a barrier.
- **Likely parse issue:** sqlglot fails on the variant path `ap.\`values\`:barcode[0].data::string`.
- **Also 0 parents:** `article_status_prod`, `catalog_reco_prod`, `deletes_cleanup_prod`,
  `promotion_9214_prod`, `structure_reco_prod`.
- **Workaround:** rerun the base table, then its getaz/richner senders.
- **Tracked in:** Jira BMSCR-1618.
  ```sql
  select concat(j.step,'.',j.topic,'_',j.item) job, count(d.parent_id) n_parents
  from fabricks.distribution_jobs j left join fabricks.distribution_dependencies d on d.job_id = j.job_id
  where j.topic = 'cip' and j.item like '%prod' group by all order by n_parents
  ```

## Wrong `groupId` / classification class (e49d092a, 4c3f7a90c)

- **Symptom:** `bms_tinsmith` received a `_product` suffix in tst.
- **Cause:** the allow-list in `product_attributes_*`, `product_classification_*` and `product_long_wood_base_*` decides
  which `cip_logistics_classification` values are kept as-is and which get `_product` appended.
  Related commits: 52534bf32, 97cca4846, 6584e4400.
- **Gotcha:** find the feed that actually carries the article before rerunning. Tinsmith comes from
  `product_long_wood_base_*`, not `product_base_*` / `product_2003_*`.
  `*_base_*` jobs have no upload post_run, so rerun the getaz/richner child jobs after them.

## Promotion articles missing in some environments (d9123610)

- The promo base query filters on the Akeneo catalog **and stock per location** (2003 / 9214 / 9217).
  An article can therefore be in one env or location and not in another.
- 8149896 was later removed from Getaz 2003 prod because it had hardly any stock in F-CH (44773bf87).

## Products not sent although changed — incremental upload window

- Feeds are `scd1` with `persist_last_timestamp`. `upload_to_cip` sends only rows with
  `__timestamp > latest - 5 days` unless `force_full` is set (config or the schedule variable
  `force_full`).
- A row that didn't change gets no new `__timestamp` and is not resent.
- `filter_cip_env` in schedule variables makes a post_run exit with "Skipped" when it differs from the job's `env`.
