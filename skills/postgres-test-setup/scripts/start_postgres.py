"""
Generic test-postgres setup script.

Environment variables (all prefixed with TEST_):
  TEST_POSTGRES_PASSWORD  - default: testpwd
  TEST_POSTGRES_DB        - default: app_test
  TEST_POSTGRES_USER      - default: postgres
  TEST_POSTGRES_PORT      - default: 54324
  TEST_POSTGRES_HOST      - default: localhost

Set SKIP_START_POSTGRES=1 to skip container startup (e.g. CI with a service container).

Usage:
  python test_server/start_postgres.py [--force-reset-db]
"""

import json
import os
import re
from pathlib import Path
from time import sleep
from typing import TYPE_CHECKING, cast, Any
import logging

import psycopg
from psycopg.rows import dict_row
from psycopg.sql import SQL, Identifier, Placeholder
import sqlglot
import sqlglot.expressions as exp

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logging.getLogger("sqlglot").setLevel(logging.ERROR)

ENV_PREFIX = "TEST_"
DOCKER_IMAGE = "pgvector/pgvector:pg18-trixie"  # change to e.g. postgres:17 if pgvector not needed
DATABASE_DIR = "database"  # directory containing .sql files, relative to cwd

postgres_test_env = {
    f"{ENV_PREFIX}POSTGRES_PASSWORD": "testpwd",
    f"{ENV_PREFIX}POSTGRES_DB": "app_test",
    f"{ENV_PREFIX}POSTGRES_USER": "postgres",
    f"{ENV_PREFIX}POSTGRES_PORT": "54324",
    f"{ENV_PREFIX}POSTGRES_HOST": "localhost",
}

# ---------------------------------------------------------------------------
# Container management
# ---------------------------------------------------------------------------

def start_postgres(wait=True):
    if os.getenv("SKIP_START_POSTGRES") == "1":
        logger.info("Skipping start_postgres since SKIP_START_POSTGRES=1")
        return None
    import docker
    import docker.errors
    from docker.models.containers import Container

    container_name = f"{ENV_PREFIX.lower()}postgres4test"
    client = docker.from_env()
    pg_server = None
    try:
        m = cast(Container, client.containers.get(container_name))
        if m.status == "running":
            return m
        pg_server = m
    except docker.errors.NotFound:
        pass

    if pg_server is None:
        env_without_prefix = {k[len(ENV_PREFIX):]: v for k, v in postgres_test_env.items()}
        pg_server = client.containers.run(
            DOCKER_IMAGE,
            detach=True,
            name=container_name,
            ports={"5432/tcp": int(postgres_test_env[f"{ENV_PREFIX}POSTGRES_PORT"])},
            environment=env_without_prefix,
        )
    assert pg_server is not None
    pg_server.start()
    if wait:
        sleep(20)
        print("Successfully started postgres container.")
    return pg_server


# ---------------------------------------------------------------------------
# SQL dependency resolution
# ---------------------------------------------------------------------------

_type_order = {
    "schema": 1,
    "types": 2,
    "tables": 3,
    "scalar_functions": 4,
    "functions": 5,
    "views": 6,
    "table_functions": 7,
    "procedures": 8,
    "permissions": 100,
    "indexes": 101,
}


def _get_type_order(x: Path):
    filename = re.sub(r"^\d+(\.\d+)?", "", x.name).removeprefix("_").removesuffix(".sql")
    if filename in _type_order:
        return _type_order[filename]
    if x.parent.name in _type_order:
        return _type_order[x.parent.name]
    raise ValueError("Unknown SQL type", f"{x.name} in {x.parent.name}. Known: {list(_type_order.keys())}")


def get_sql_deps(sql: str) -> tuple[set[str], set[str]]:
    exprs = sqlglot.parse(sql, dialect="postgres")
    deps: set[str] = set()
    declares: set[str] = set()
    for e in exprs:
        if e is not None:
            for t in e.find_all(exp.Create):
                if t.args.get("this") is not None and t.args.get("db") is not None:
                    declares.add(str(t))
            for t in e.find_all(exp.Table):
                if t.args.get("this") is not None and t.args.get("db") is not None:
                    deps.add(str(t))
    return declares, deps


def get_sqls():
    """Yield (Path, sql_content) pairs in dependency-safe execution order."""
    files: list[Path] = []
    for root, _, dbfiles in os.walk(DATABASE_DIR):
        if "_migration_scripts" in root or "migrations" in root:
            continue
        for file in dbfiles:
            if file == "all.sql" or file == "100_permissions.sql":
                continue
            if file.endswith(".sql") and ".prod" not in file:
                files.append(Path(root) / file)

    delivered_tables: set[str] = set()
    delayed_files: list[tuple[str | None, Path, str]] = []
    all_declared: set[str] = set()

    for file in sorted(files, key=lambda x: (_get_type_order(x), str(x.name))):
        content = file.read_text(encoding="utf-8")
        declares, deps = get_sql_deps(content)
        if file.parent.parent.name == "tables":
            schema = file.parent.name
            full_tbl_name = f"{schema}.{file.stem}"
            declares.add(full_tbl_name)
            all_declared.update(declares)
            if not deps or all(d in delivered_tables for d in deps):
                delivered_tables.add(full_tbl_name)
                yield file, content
            else:
                delayed_files.append((full_tbl_name, file, content))
                continue
        elif not deps or all(d in delivered_tables for d in deps):
            yield file, content
        else:
            delayed_files.append((None, file, content))
            continue
        yield file, content

    while delayed_files:
        progress = False
        for i in range(len(delayed_files) - 1, -1, -1):
            tbl_name, file, content = delayed_files[i]
            _, deps = get_sql_deps(content)
            if all(d in delivered_tables or d not in all_declared for d in deps):
                if tbl_name:
                    delivered_tables.add(tbl_name)
                yield file, content
                delayed_files.pop(i)
                progress = True
        if not progress:
            raise ValueError("Circular or missing SQL dependencies", [f[1] for f in delayed_files])


# ---------------------------------------------------------------------------
# Test data insertion
# ---------------------------------------------------------------------------

async def insert_test_data(json_file: Path, table: str, force_reset_db: bool, con: "psycopg.AsyncConnection"):
    """Insert rows from a .test_data.json file into the given schema.table."""
    if not json_file.exists():
        logger.warning("No test data file: %s", json_file)
        return
    json_data: list[dict] = json.loads(json_file.read_text(encoding="utf-8"))
    if not json_data:
        return

    schema, table_name = table.split(".")
    async with con.cursor(row_factory=dict_row) as cur:
        if not force_reset_db:
            await cur.execute(
                SQL("SELECT count(*) AS cnt FROM {t}").format(t=Identifier(schema, table_name))
            )
            row = await cur.fetchone()
            if row and row["cnt"] == len(json_data):
                logger.info("Skip %s — already populated", table)
                return

        logger.info("Inserting %d rows into %s", len(json_data), table)
        col_names = list(json_data[0].keys())

        # Serialize any nested dicts/lists as JSON strings
        for row in json_data:
            for col in col_names:
                if isinstance(row[col], (dict, list)):
                    row[col] = json.dumps(row[col])

        await cur.execute(SQL("DELETE FROM {t}").format(t=Identifier(schema, table_name)))
        sql = SQL("INSERT INTO {t} ({cols}) VALUES ({vals})").format(
            t=Identifier(schema, table_name),
            cols=SQL(", ").join([Identifier(c) for c in col_names]),
            vals=SQL(", ").join([Placeholder(c) for c in col_names]),
        )
        try:
            await cur.executemany(sql, json_data)
            await cur.execute("COMMIT")
        except Exception as e:
            await cur.execute("ROLLBACK")
            raise RuntimeError(f"Error inserting into {table}: {e}") from e


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

async def create_test_db_postgres(con: "psycopg.AsyncConnection", force_reset_db: bool = False):
    assert os.getenv(f"{ENV_PREFIX}POSTGRES_HOST") == "localhost", (
        f"Refusing to run setup_database: {ENV_PREFIX}POSTGRES_HOST is not localhost"
    )
    await con.set_autocommit(True)
    failures: list[tuple[Path, str]] = []

    for file, sql in get_sqls():
        logger.info(file)
        try:
            await con.execute(cast(Any, sql))
            json_file = file.with_suffix(".test_data.json")
            if json_file.exists():
                await con.execute("COMMIT")
                schema_name = file.parent.parent.name
                if re.match(r"^\d+_", schema_name):
                    schema_name = schema_name.split("_", 1)[1]
                await insert_test_data(
                    json_file, f"{schema_name}.{file.stem}", force_reset_db=force_reset_db, con=con
                )
        except Exception as e:
            logger.warning("Error executing %s (will retry): %s", file, e)
            failures.append((file, sql))

    for file, sql in failures:
        logger.info("Retrying %s", file)
        await con.execute(cast(Any, sql))


async def setup_database(force_reset_db: bool = False):
    user = postgres_test_env[f"{ENV_PREFIX}POSTGRES_USER"]
    pwd = postgres_test_env[f"{ENV_PREFIX}POSTGRES_PASSWORD"]
    host = postgres_test_env[f"{ENV_PREFIX}POSTGRES_HOST"]
    port = postgres_test_env[f"{ENV_PREFIX}POSTGRES_PORT"]
    db = postgres_test_env[f"{ENV_PREFIX}POSTGRES_DB"]

    conn_str = f"postgresql://{user}:{pwd}@{host}:{port}/{db}?connect_timeout=10"

    if force_reset_db:
        admin = f"postgresql://{user}:{pwd}@{host}:{port}/postgres?connect_timeout=10"
        async with await psycopg.AsyncConnection.connect(conninfo=admin, autocommit=True) as c:
            await c.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %(db)s",
                {"db": db},
            )
            await c.execute(f'DROP DATABASE IF EXISTS "{db}"')
            await c.execute(f'CREATE DATABASE "{db}"')
            print(f"Database '{db}' reset.")

    async with await psycopg.AsyncConnection.connect(conninfo=conn_str, autocommit=True) as con:
        await con.execute("CREATE EXTENSION IF NOT EXISTS vector")
        await create_test_db_postgres(con, force_reset_db=force_reset_db)
        print(f"Test DB ready: {conn_str}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Start test Postgres and initialize schema")
    parser.add_argument("--force-reset-db", action="store_true", help="Drop and recreate the DB")
    args = parser.parse_args()

    for k, v in postgres_test_env.items():
        os.environ[k] = v

    start_postgres()
    await setup_database(force_reset_db=args.force_reset_db)


if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
