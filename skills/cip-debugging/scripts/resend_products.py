# Databricks notebook source
# MAGIC %md
# MAGIC # Resend specific products to CIP
# MAGIC Upserts the current rows of the given product ids from one or more CIP feed tables, using the
# MAGIC same endpoint, key vault secret, JSON schema and log path as the feed's `upload_to_cip` post_run
# MAGIC in `_config.cip*.yml`. Never sends deletes. `dry_run=true` (default) only builds and validates.
# MAGIC
# MAGIC Must live next to `upload_to_cip` in the workspace repo (`.../Fabricks.Runtime/distribution/cip/`)
# MAGIC so `utils.transformers` and `json_schema/` resolve.

# COMMAND ----------

# MAGIC %pip install orjson jsonschema-rs polars pyyaml

# COMMAND ----------

dbutils.widgets.text("ids", "")  # type: ignore # noqa: F821
dbutils.widgets.text("items", "")  # type: ignore # noqa: F821
dbutils.widgets.text("dry_run", "true")  # type: ignore # noqa: F821

# COMMAND ----------

import re
from datetime import datetime, timezone
from pathlib import Path

import jsonschema_rs
import orjson
import polars as pl
import requests
import yaml
from databricks.sdk.runtime import dbutils, spark
from pyspark.sql import functions as F
from utils.transformers import remove_none_and_empty, transformer  # type: ignore

ids = [i for i in re.split(r"[,\s]+", dbutils.widgets.get("ids").strip()) if i]
items = [i for i in re.split(r"[,\s]+", dbutils.widgets.get("items").strip()) if i]
dry_run = dbutils.widgets.get("dry_run").strip().lower() != "false"
assert ids and items, "set the ids and items widgets (comma separated), e.g. items=product_plumbing_getaz_prod"

# COMMAND ----------


def upload_targets(item: str) -> list[dict]:
    targets = []
    for cfg in Path(".").glob("_config.cip*.yml"):
        for entry in yaml.safe_load(cfg.read_text()) or []:
            job = entry.get("job", {})
            if job.get("item") != item:
                continue
            for post in (job.get("invoker_options") or {}).get("post_run") or []:
                if post.get("notebook", "").endswith("upload_to_cip"):
                    targets.append(post["arguments"])
    assert targets, f"no upload_to_cip post_run found for {item} in _config.cip*.yml"
    return targets


results = []
for item in items:
    df = (
        spark.table(f"distribution.cip_{item}")
        .where("__is_current")
        .where(F.col("productIdentification.id").isin(ids))
    )
    df = df.select(*[c for c in df.columns if not c.startswith("_")])
    for args in upload_targets(item):
        records = transformer(pl.DataFrame(df.toArrow()), args.get("transformer_name") or "no transformer")
        records = [remove_none_and_empty(r) for r in records]
        with Path(args["schema_path"]).open() as f:
            validator = jsonschema_rs.validator_for(orjson.loads(f.read()))
        invalid = {
            r["productIdentification"]["id"]: "; ".join(str(e) for e in validator.iter_errors([r]))
            for r in records
            if not validator.is_valid([r])
        }
        sent = sorted(r["productIdentification"]["id"] for r in records)
        result = {
            "item": item,
            "env": args["env"],
            "secret": args["key_vault_secret"],
            "found": sent,
            "missing_in_table": sorted(set(ids) - set(sent)),
            "invalid": invalid,
        }
        if not dry_run and records and not invalid:
            headers = orjson.loads(dbutils.secrets.get("bmskv", args["key_vault_secret"]))
            url = f"{args['api_base_url']}/{args['api_endpoint']}"
            resp = requests.post(url, json=records, headers=headers)
            result.update({"status": resp.status_code, "body": resp.text[:500]})
            if resp.status_code == 202 and args.get("log_uri"):
                (
                    spark.createDataFrame([(i,) for i in sent], "id string")
                    .withColumn("item", F.lit(item))
                    .withColumn("topic", F.lit("cip"))
                    .withColumn("step", F.lit("distribution"))
                    .withColumn("env", F.lit(args["env"]))
                    .withColumn("timestamp", F.lit(datetime.now(timezone.utc)))
                    .withColumn("operation", F.lit("insert"))
                    .write.mode("append")
                    .save(args["log_uri"])
                )
        results.append(result)

dbutils.notebook.exit(orjson.dumps({"dry_run": dry_run, "results": results}).decode())
