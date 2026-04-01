"""
ComplexHelper — psycopg adapter for PostgreSQL composite types, enums, and JSONB.

Use this when your project has custom PostgreSQL types (composite types, enums)
that need to be registered with psycopg before inserting test data. Plain columns
and JSONB are handled automatically by start_postgres.py; you only need this class
for USER-DEFINED types.

Usage in start_postgres.py — extend insert_test_data like this:

    from app.backend_utils.postgres_complex_helper import ComplexHelper

    async def insert_test_data(json_file, table, force_reset_db, con):
        ...
        helper = ComplexHelper(con)
        complex_types = await helper.load_all_complex_types(
            (schema_name, table_name)
        )
        for row in json_data:
            for col, info in complex_types.items():
                if col in row:
                    row[col] = await helper.recursive_convert(row[col], info, con)
        # then proceed with the normal INSERT
"""

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from typing import Any
from psycopg.sql import Identifier
from psycopg.types.composite import CompositeInfo, register_composite
from psycopg.types.json import Jsonb
from psycopg.types.enum import EnumInfo, register_enum


class ComplexHelper:
    complex_types: dict[tuple[str, str], CompositeInfo | EnumInfo] = {}

    def __init__(self, con: AsyncConnection):
        self.con = con
        self.system_complex_type_dict = None

        self.registered: set[CompositeInfo | EnumInfo] = set()

    async def load_complex_type_dict(self):
        async with self.con.cursor(row_factory=dict_row) as cur:
            await cur.execute("""
        SELECT t.oid,
                pg_catalog.format_type ( t.oid, NULL ) AS obj_name,
				t.typtype
            FROM pg_catalog.pg_type t
            JOIN pg_catalog.pg_namespace n
                ON n.oid = t.typnamespace
            WHERE ( t.typrelid = 0
                    OR ( SELECT c.relkind = 'c'
                            FROM pg_catalog.pg_class c
                            WHERE c.oid = t.typrelid ) )
                AND n.nspname <> 'pg_catalog'
                AND n.nspname <> 'information_schema'
                AND n.nspname !~ '^pg_toast'""")
            system_complex_types = await cur.fetchall()
            self.system_complex_type_dict = {
                r["oid"]: (r["obj_name"], r["typtype"]) for r in system_complex_types
            }

    async def _load_complex_type_from_colinfos(
        self, res: dict[str, Any] | None
    ) -> CompositeInfo | EnumInfo | type[Jsonb] | None:
        if not res:
            return None
        if res["data_type"].lower() == "jsonb":
            return Jsonb
        if res["data_type"].upper() == "ARRAY" and res["udt_name"] == "_jsonb":
            return Jsonb
        if (
            not res["is_enum"]
            and not res["is_user_defined"]
            and not (res["data_type"] == "ARRAY" and res["udt_schema"] != "pg_catalog")
        ):
            return None
        udt_schema: str = res["udt_schema"]
        udt_name: str = res["udt_name"]
        c = await self._get_complex_type(
            f"{udt_schema}.{udt_name}", res["is_enum"], self.con
        )
        await self._recurse_register(c, self.con)
        return c

    async def load_all_complex_types(
        self, table_name: tuple[str, str], include_generated: bool = False
    ) -> dict[str, CompositeInfo | type[Jsonb] | EnumInfo | None]:
        if self.system_complex_type_dict is None:
            await self.load_complex_type_dict()
        colquery = """
        with enum_types as (
                            select n.nspname  as enum_schema, t.typname as enum_name from pg_type t
                                inner join pg_namespace n on n.oid=t.typnamespace
                                where typtype='e'
                        )
        select column_name, data_type,
            data_type='USER-DEFINED' as is_user_defined,
            udt_schema, udt_name,
            e.enum_name is not null as is_enum
              from information_schema.columns c
                 left join enum_types e on e.enum_schema=c.udt_schema and e.enum_name=c.udt_name
              where table_schema=%(schema)s and table_name = %(tbl)s and (is_generated <> 'ALWAYS' or %(include_generated)s)"""
        async with self.con.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                colquery,
                {
                    "schema": table_name[0],
                    "tbl": table_name[1],
                    "include_generated": include_generated,
                },
            )
            res = await cur.fetchall()
            return {
                r["column_name"]: await self._load_complex_type_from_colinfos(r)
                for r in res
            }

    async def load_complex_type(
        self, table_name: tuple[str, str], col_name: str
    ) -> CompositeInfo | type[Jsonb] | EnumInfo | None:
        if self.system_complex_type_dict is None:
            await self.load_complex_type_dict()
        colquery = """
        with enum_types as (
                            select n.nspname  as enum_schema, t.typname as enum_name from pg_type t
                                inner join pg_namespace n on n.oid=t.typnamespace
                                where typtype='e'
                        )
        select column_name, data_type,
            data_type='USER-DEFINED' as is_user_defined,
            udt_schema, udt_name,
            e.enum_name is not null as is_enum
              from information_schema.columns c
            left join enum_types e on e.enum_schema=c.udt_schema and e.enum_name=c.udt_name
              where table_schema=%(schema)s and table_name = %(tbl)s
                and column_name = %(col)s"""
        async with self.con.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                colquery,
                {"schema": table_name[0], "tbl": table_name[1], "col": col_name},
            )
            res = await cur.fetchone()

            return await self._load_complex_type_from_colinfos(res)

    async def _get_complex_type(
        self, name: str, is_enum: bool, con: AsyncConnection
    ) -> CompositeInfo | EnumInfo:
        if name.endswith("[]"):
            name = name[:-2]
        schema, type_name = name.split(".")
        if type_name.startswith(
            "_"
        ):  # the array type in PostgreSQL starts with an underscore
            type_name = type_name[1:]
        if is_enum:
            ci = await EnumInfo.fetch(con, Identifier(schema, type_name))
            assert ci is not None, f"Enum type {name} not found in database"
            self.complex_types[(schema, type_name)] = ci
        if (schema, type_name) not in self.complex_types:
            ci = await CompositeInfo.fetch(con, Identifier(schema, type_name))
            assert ci is not None, f"Complex type {name} not found in database"
            self.complex_types[(schema, type_name)] = ci
        return self.complex_types[(schema, type_name)]

    async def _recurse_register(
        self, info: CompositeInfo | EnumInfo, con: AsyncConnection
    ):
        assert self.system_complex_type_dict is not None, (
            "System complex type dictionary not loaded"
        )
        if info not in self.registered:
            if isinstance(info, EnumInfo):
                register_enum(info, con)
            else:
                register_composite(info, con)
            self.registered.add(info)
        if isinstance(info, EnumInfo):
            return
        for t in info.field_types:
            if t in self.system_complex_type_dict:
                name, typtype = self.system_complex_type_dict[t]
                ci = await self._get_complex_type(name, typtype == "e", con)
                await self._recurse_register(ci, con)

    async def recursive_convert(
        self,
        value: Any,
        info: CompositeInfo | EnumInfo | type[Jsonb] | None,
        con: AsyncConnection,
    ) -> Any:
        if info is None:
            return value
        if value is None:
            return None
        if self.system_complex_type_dict is None:
            await self.load_complex_type_dict()
        if isinstance(value, list):
            return [await self.recursive_convert(item, info, con) for item in value]
        prms = {}
        if info == Jsonb:
            return Jsonb(value)
        if isinstance(value, str):
            assert isinstance(info, EnumInfo), f"Expected EnumInfo, got {type(info)}"
            return getattr(info.enum, value)  # Enum
        assert isinstance(info, CompositeInfo), (
            f"Expected CompositeInfo, got {type(info)}"
        )
        assert self.system_complex_type_dict is not None, (
            "System complex type dictionary not loaded"
        )
        for k, v in value.items():
            if v is None:
                prms[k] = None
                continue
            fi = info.field_names.index(k)
            type_oid = info.field_types[fi]
            if type_oid in self.system_complex_type_dict:
                name, typtype = self.system_complex_type_dict[type_oid]
                ci = await self._get_complex_type(name, typtype == "e", con)
                if name.endswith("[]"):
                    prms[k] = [
                        await self.recursive_convert(item, ci, con) for item in v
                    ]
                else:
                    prms[k] = await self.recursive_convert(v, ci, con)
            else:
                prms[k] = v
        assert info.python_type is not None, (
            f"Python type for {info.name} is null, maybe an array?"
        )
        return info.python_type(**prms) if prms else None
