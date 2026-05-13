# db/postgres.py — Generic CRUD helpers
#
# Copy this file into the project and strip any project-specific bits.
# Use these helpers for simple CRUD. For anything that needs a custom WHERE
# clause, a join, aggregation, or ordering — write a dedicated .sql file and
# a repository method.

from __future__ import annotations

from typing import Any, Sequence, TypeVar, Type, Optional, Callable, Mapping
from psycopg.connection_async import AsyncConnection
from psycopg.sql import SQL, Identifier, Placeholder
from psycopg.rows import dict_row
from db.pg_base import PostgresTableModel

T = TypeVar("T", bound=PostgresTableModel)


async def pg_retrieve(con: AsyncConnection, data_type: Type[T], pks: dict) -> T | None:
    """Fetch a single row by primary key(s)."""
    async with con.cursor(row_factory=dict_row) as cur:
        schema, table = data_type.get_table_name()
        where = " AND ".join(f"{pk} = %({pk})s" for pk in pks)
        await cur.execute(f"select * from {schema}.{table} where {where}", pks)  # type: ignore[arg-type]
        row = await cur.fetchone()
    return data_type(**row) if row else None


async def pg_retrieve_many(
    con: AsyncConnection,
    data_type: Type[T],
    filters: dict,
    *,
    from_dict: Optional[Callable[[Mapping], T]] = None,
) -> Sequence[T]:
    """Fetch multiple rows matching all filter key=value pairs."""
    async with con.cursor(row_factory=dict_row) as cur:
        schema, table = data_type.get_table_name()
        if filters:
            where = " AND ".join(f"{k} = %({k})s" for k in filters)
            sql = f"select * from {schema}.{table} where {where}"  # type: ignore[assignment]
        else:
            sql = f"select * from {schema}.{table}"  # type: ignore[assignment]
        await cur.execute(sql, filters)
        rows = await cur.fetchall()
    fn = from_dict or (lambda d: data_type(**d))
    return [fn(r) for r in rows]


async def pg_insert(con: AsyncConnection, table_name: tuple[str, str], data: dict) -> dict[str, Any]:
    """Insert one row and return the full row (RETURNING *)."""
    query = SQL("INSERT INTO {tbl} ({cols}) VALUES ({vals}) RETURNING *").format(
        tbl=Identifier(*table_name),
        cols=SQL(", ").join(Identifier(k) for k in data),
        vals=SQL(", ").join(Placeholder(k) for k in data),
    )
    async with con.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, data)
        row = await cur.fetchone()
    assert row is not None
    return row


async def pg_update_dict(
    con: AsyncConnection,
    table_name: tuple[str, str],
    data: dict,
    primary_keys: Sequence[str],
) -> Any | None:
    """Update a row identified by primary_keys. Returns the raw row tuple."""
    set_parts = [
        SQL("{col} = {val}").format(col=Identifier(k), val=Placeholder(k))
        for k in data if k not in primary_keys
    ]
    where_parts = [
        SQL("{col} = {val}").format(col=Identifier(pk), val=Placeholder(pk))
        for pk in primary_keys
    ]
    query = SQL("UPDATE {tbl} SET {sets} WHERE {where} RETURNING *").format(
        tbl=Identifier(*table_name),
        sets=SQL(", ").join(set_parts),
        where=SQL(" AND ").join(where_parts),
    )
    async with con.cursor() as cur:
        await cur.execute(query, data)
        return await cur.fetchone()


async def pg_update(con: AsyncConnection, data: T, data_type: type[T]) -> Any | None:
    """Update a typed model instance."""
    return await pg_update_dict(con, data_type.get_table_name(), data.model_dump(), data_type.get_primary_key())


async def pg_upsert_dict(
    con: AsyncConnection,
    table_name: tuple[str, str],
    data: dict,
    primary_keys: Sequence[str],
) -> dict:
    """INSERT … ON CONFLICT … DO UPDATE, returns the row as a dict."""
    fields = list(data)
    updates = [SQL("{col} = EXCLUDED.{col}").format(col=Identifier(k)) for k in fields]
    query = SQL(
        "INSERT INTO {tbl} ({cols}) VALUES ({vals}) ON CONFLICT ({pks}) DO UPDATE SET {updates} RETURNING *"
    ).format(
        tbl=Identifier(*table_name),
        cols=SQL(", ").join(Identifier(k) for k in fields),
        vals=SQL(", ").join(Placeholder(k) for k in fields),
        pks=SQL(", ").join(Identifier(pk) for pk in primary_keys),
        updates=SQL(", ").join(updates),
    )
    async with con.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, data)
        row = await cur.fetchone()
    assert row is not None
    return row


async def pg_upsert(con: AsyncConnection, data: T, data_type: type[T]):
    """Upsert a typed model instance."""
    return await pg_upsert_dict(con, data_type.get_table_name(), data.model_dump(), data_type.get_primary_key())


async def pg_upsert_many_dict(
    con: AsyncConnection,
    table_name: tuple[str, str],
    data: Sequence[dict],
    primary_keys: Sequence[str],
) -> None:
    """Batch upsert — one round-trip via executemany."""
    if not data:
        return
    fields = list(data[0])
    updates = [SQL("{col} = EXCLUDED.{col}").format(col=Identifier(k)) for k in fields if k not in primary_keys]
    query = SQL(
        "INSERT INTO {tbl} ({cols}) VALUES ({vals}) ON CONFLICT ({pks}) DO UPDATE SET {updates}"
    ).format(
        tbl=Identifier(*table_name),
        cols=SQL(", ").join(Identifier(k) for k in fields),
        vals=SQL(", ").join(Placeholder(k) for k in fields),
        pks=SQL(", ").join(Identifier(pk) for pk in primary_keys),
        updates=SQL(", ").join(updates),
    )
    async with con.cursor() as cur:
        await cur.executemany(query, data)


async def pg_upsert_many(con: AsyncConnection, data: Sequence[T], data_type: type[T]) -> None:
    await pg_upsert_many_dict(con, data_type.get_table_name(), [d.model_dump() for d in data], data_type.get_primary_key())


async def pg_insert_many(
    con: AsyncConnection,
    table_name: tuple[str, str],
    data: Sequence[dict],
) -> None:
    """Batch insert — no RETURNING, one round-trip via executemany."""
    if not data:
        return
    fields = list(data[0])
    query = SQL("INSERT INTO {tbl} ({cols}) VALUES ({vals})").format(
        tbl=Identifier(*table_name),
        cols=SQL(", ").join(Identifier(k) for k in fields),
        vals=SQL(", ").join(Placeholder(k) for k in fields),
    )
    async with con.cursor() as cur:
        await cur.executemany(query, data)


async def pg_delete_dict(con: AsyncConnection, table_name: tuple[str, str], data: dict) -> dict | None:
    """Delete by arbitrary key dict, returns the deleted row."""
    where_parts = [SQL("{col} = {val}").format(col=Identifier(k), val=Placeholder(k)) for k in data]
    query = SQL("DELETE FROM {tbl} WHERE {where} RETURNING *").format(
        tbl=Identifier(*table_name),
        where=SQL(" AND ").join(where_parts),
    )
    async with con.cursor() as cur:
        await cur.execute(query, data)
        row = await cur.fetchone()
        if row is None:
            return None
        assert cur.description is not None
        return dict(zip([c[0] for c in cur.description], row))


async def pg_delete(con: AsyncConnection, data: T, data_type: type[T]) -> T | None:
    """Delete a typed model instance by its primary key(s)."""
    pk_dict = {pk: getattr(data, pk) for pk in data_type.get_primary_key()}
    row = await pg_delete_dict(con, data_type.get_table_name(), pk_dict)
    return data_type.model_validate(row) if row else None
