# db/connection.py — pool factory
#
# Adjust _PREFIX to match the project env-var prefix
# (e.g. "APP_POSTGRES_", "MDM_POSTGRES_").
# _pool is intentional module-level mutable state.

from __future__ import annotations

import os
from psycopg_pool import AsyncConnectionPool

_PREFIX = os.getenv("PG_ENV_PREFIX", "POSTGRES_")

def _dsn() -> str:
    p = _PREFIX
    return (
        f"host={os.environ[p + 'HOST']} "
        f"port={os.environ[p + 'PORT']} "
        f"dbname={os.environ[p + 'DB']} "
        f"user={os.environ[p + 'USER']} "
        f"password={os.environ[p + 'PASSWORD']}"
    )

_pool: AsyncConnectionPool | None = None

async def open_pool() -> None:
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(conninfo=_dsn, open=False, max_size=40, check=AsyncConnectionPool.check_connection)
    if not _pool._opened:
        await _pool.open()

def get_pg_connection():
    """Return an async connection context manager from the pool."""
    assert _pool is not None, "Call open_pool() first (e.g. in app startup)."
    return _pool.connection()
