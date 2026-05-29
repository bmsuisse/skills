# Schema & Migrations

Procrastinate ships plain `.sql` files — apply them with any PostgreSQL client.

## Initial setup

```bash
# Print the full creation SQL and pipe it to psql
procrastinate schema --print-schema | psql $DATABASE_URL
```

Or capture it for your migration tooling (Flyway, sqitch, Alembic raw SQL, etc.):

```bash
procrastinate schema --print-schema > migrations/V1__procrastinate_schema.sql
```

## Upgrading — migration files

Migration files live inside the installed package:

```bash
procrastinate schema --migrations-path
# → /path/to/venv/lib/python3.x/site-packages/procrastinate/sql/migrations
```

Apply a specific migration:

```bash
cat $(procrastinate schema --migrations-path)/02.00.00_01_pre_some_migration.sql | psql $DATABASE_URL
```

## Migration file naming

```
{xx.yy.zz}_{ab}_{pre|post}_description.sql
```

- `xx.yy.zz` — Procrastinate version the migration targets
- `ab` — serial number within that version
- `pre` — apply **before** deploying new code (safe for blue-green)
- `post` — apply **after** deploying new code

## Upgrade workflow (with service continuity)

For each version bump that includes migrations:

1. Apply all `pre` migrations for the new version
2. Deploy the new code
3. Apply all `post` migrations

```bash
cat $(procrastinate schema --migrations-path)/02.01.00_01_pre_*.sql | psql $DATABASE_URL
# deploy
cat $(procrastinate schema --migrations-path)/02.01.00_01_post_*.sql | psql $DATABASE_URL
```

Check the [Procrastinate changelog](https://procrastinate.readthedocs.io/en/stable/changelog.html) to see which releases include new migrations.
