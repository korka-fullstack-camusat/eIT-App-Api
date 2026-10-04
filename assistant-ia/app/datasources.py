"""Accès en lecture seule aux bases PostgreSQL des plateformes."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from fnmatch import fnmatch
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .config import SourceConfig, get_settings, get_sources_file
from .sql_guard import CheckedQuery, check_select

SCHEMA_CACHE_TTL = 600  # secondes


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[dict[str, Any]]
    truncated: bool
    hidden_columns: list[str]
    tables: list[str]
    duration_ms: int


class DataSource:
    def __init__(self, cfg: SourceConfig, global_tables: list[str], global_columns: list[str]):
        self.cfg = cfg
        self.excluded_tables = [*global_tables, *cfg.exclude_tables]
        self.excluded_columns = [*global_columns, *cfg.exclude_columns]
        self._schema_cache: tuple[float, dict[str, dict[str, Any]]] | None = None
        self._schema_lock = asyncio.Lock()

    @property
    def id(self) -> str:
        return self.cfg.id

    @property
    def configured(self) -> bool:
        return bool(self.cfg.dsn)

    def _table_allowed(self, name: str) -> bool:
        return not any(fnmatch(name.lower(), p.lower()) for p in self.excluded_tables)

    def _column_allowed(self, name: str) -> bool:
        return not any(fnmatch(name.lower(), p.lower()) for p in self.excluded_columns)

    async def _connect(self) -> psycopg.AsyncConnection:
        if not self.configured:
            raise RuntimeError(
                f"La source « {self.id} » n'est pas configurée (variable {self.cfg.dsn_env} absente)."
            )
        settings = get_settings()
        # Lecture seule imposée au niveau de la session, en plus du rôle Postgres.
        options = (
            f"-c default_transaction_read_only=on "
            f"-c statement_timeout={settings.sql_timeout_ms} "
            f"-c idle_in_transaction_session_timeout=30000"
        )
        return await psycopg.AsyncConnection.connect(
            self.cfg.dsn,
            options=options,
            application_name="assistant-ia",
            connect_timeout=10,
            row_factory=dict_row,
        )

    async def schema(self) -> dict[str, dict[str, Any]]:
        """Tables autorisées -> {columns: [(nom, type)], rows_estimate, comment}."""
        async with self._schema_lock:
            if self._schema_cache and time.monotonic() - self._schema_cache[0] < SCHEMA_CACHE_TTL:
                return self._schema_cache[1]

            async with await self._connect() as conn:
                cols = await (await conn.execute(
                    """
                    SELECT c.table_schema, c.table_name, c.column_name, c.data_type
                    FROM information_schema.columns c
                    JOIN information_schema.tables t
                      ON t.table_schema = c.table_schema AND t.table_name = c.table_name
                    WHERE c.table_schema = ANY(%s) AND t.table_type IN ('BASE TABLE', 'VIEW')
                    ORDER BY c.table_schema, c.table_name, c.ordinal_position
                    """,
                    (self.cfg.schemas,),
                )).fetchall()
                stats = await (await conn.execute(
                    """
                    SELECT n.nspname AS table_schema, c.relname AS table_name,
                           GREATEST(c.reltuples, 0)::bigint AS rows_estimate,
                           obj_description(c.oid) AS comment
                    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = ANY(%s) AND c.relkind IN ('r', 'v', 'm', 'p')
                    """,
                    (self.cfg.schemas,),
                )).fetchall()

            stat_map = {(s["table_schema"], s["table_name"]): s for s in stats}
            tables: dict[str, dict[str, Any]] = {}
            for col in cols:
                tname = col["table_name"]
                if not self._table_allowed(tname):
                    continue
                key = tname if col["table_schema"] == "public" else f'{col["table_schema"]}.{tname}'
                entry = tables.setdefault(key, {"columns": [], "rows_estimate": None, "comment": None})
                if self._column_allowed(col["column_name"]):
                    entry["columns"].append((col["column_name"], col["data_type"]))
                st = stat_map.get((col["table_schema"], tname))
                if st:
                    entry["rows_estimate"] = st["rows_estimate"]
                    entry["comment"] = st["comment"]

            self._schema_cache = (time.monotonic(), tables)
            return tables

    def check(self, sql: str) -> CheckedQuery:
        return check_select(
            sql,
            allowed_schemas=self.cfg.schemas,
            excluded_tables=self.excluded_tables,
            excluded_columns=self.excluded_columns,
        )

    async def run_select(self, sql: str) -> QueryResult:
        checked = self.check(sql)
        settings = get_settings()
        start = time.monotonic()
        async with await self._connect() as conn:
            async with conn.transaction():
                await conn.execute("SET TRANSACTION READ ONLY")
                cur = await conn.execute(checked.sql)
                rows = await cur.fetchmany(settings.sql_max_rows + 1)
                columns = [d.name for d in (cur.description or [])]
        duration_ms = int((time.monotonic() - start) * 1000)

        truncated = len(rows) > settings.sql_max_rows
        rows = rows[: settings.sql_max_rows]
        hidden = [c for c in columns if not self._column_allowed(c)]
        if hidden:
            rows = [{k: v for k, v in r.items() if k not in hidden} for r in rows]
            columns = [c for c in columns if c not in hidden]
        return QueryResult(columns, rows, truncated, hidden, checked.tables, duration_ms)


class Registry:
    def __init__(self) -> None:
        sf = get_sources_file()
        self.sources: dict[str, DataSource] = {
            s.id: DataSource(s, sf.global_exclude_tables, sf.global_exclude_columns)
            for s in sf.sources
        }

    def get(self, source_id: str) -> DataSource:
        try:
            return self.sources[source_id]
        except KeyError:
            raise KeyError(
                f"Source inconnue « {source_id} ». Sources disponibles : {', '.join(self.sources)}"
            ) from None


_registry: Registry | None = None


def get_registry() -> Registry:
    global _registry
    if _registry is None:
        _registry = Registry()
    return _registry
