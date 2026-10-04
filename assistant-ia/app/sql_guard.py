"""Validation des requêtes SQL produites par l'agent avant exécution.

Défense en profondeur : la vraie protection reste le rôle Postgres en lecture
seule avec des GRANT limités (voir scripts/create_readonly_role.sql). Ce module
refuse en amont tout ce qui n'est pas un SELECT simple sur des tables autorisées.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch

import sqlglot
from sqlglot import exp

# Fonctions qui permettent de lire le système de fichiers, d'ouvrir des
# connexions, de bloquer le serveur ou de sérialiser une ligne entière
# (ce qui contournerait le filtrage des colonnes sensibles).
FORBIDDEN_FUNCTIONS = {
    "pg_read_file", "pg_read_binary_file", "pg_ls_dir", "pg_stat_file",
    "lo_import", "lo_export", "lo_get", "dblink", "dblink_exec", "dblink_connect",
    "pg_sleep", "pg_sleep_for", "pg_sleep_until", "set_config",
    "pg_terminate_backend", "pg_cancel_backend", "pg_reload_conf",
    "row_to_json", "to_json", "to_jsonb", "json_agg", "jsonb_agg",
    "hstore", "query_to_xml", "table_to_xml", "cursor_to_xml",
}

FORBIDDEN_SCHEMAS = {"pg_catalog", "information_schema", "pg_toast"}


class SqlRejected(ValueError):
    """Requête refusée ; le message est renvoyé tel quel à l'agent."""


@dataclass
class CheckedQuery:
    sql: str
    tables: list[str] = field(default_factory=list)


def _matches(name: str, patterns: list[str]) -> bool:
    name = name.lower()
    return any(fnmatch(name, p.lower()) for p in patterns)


def check_select(
    sql: str,
    *,
    allowed_schemas: list[str],
    excluded_tables: list[str],
    excluded_columns: list[str],
) -> CheckedQuery:
    sql = sql.strip().rstrip(";").strip()
    if not sql:
        raise SqlRejected("Requête vide.")

    try:
        statements = sqlglot.parse(sql, dialect="postgres")
    except sqlglot.errors.ParseError as e:
        raise SqlRejected(f"SQL invalide : {e}") from e

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise SqlRejected("Une seule requête SELECT à la fois.")
    tree = statements[0]

    if not isinstance(tree, exp.Query):
        raise SqlRejected("Seules les requêtes de lecture (SELECT / WITH … SELECT) sont autorisées.")

    for node in tree.walk():
        if isinstance(node, (exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Create,
                             exp.Drop, exp.Alter, exp.Command, exp.Into, exp.Lock)):
            raise SqlRejected("Seules les requêtes de lecture sont autorisées.")

    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    tables: list[str] = []
    for table in tree.find_all(exp.Table):
        name = table.name.lower()
        if not name:
            continue
        schema = (table.db or "").lower()
        if not schema and name in cte_names:
            continue
        if schema in FORBIDDEN_SCHEMAS or name.startswith("pg_"):
            raise SqlRejected(
                "Les tables système ne sont pas accessibles. Utilisez les outils "
                "list_tables / describe_table pour explorer le schéma."
            )
        if schema and schema not in [s.lower() for s in allowed_schemas]:
            raise SqlRejected(f"Schéma « {schema} » non autorisé pour cette source.")
        if _matches(name, excluded_tables):
            raise SqlRejected(f"La table « {name} » est exclue (données sensibles ou techniques).")
        full = f"{schema}.{name}" if schema else name
        if full not in tables:
            tables.append(full)

    # Noms et alias de tables : « SELECT e FROM employee e » renverrait la ligne
    # entière (colonnes sensibles comprises) sous forme d'un seul champ.
    row_refs = {t.alias_or_name.lower() for t in tree.find_all(exp.Table)} | {
        t.name.lower() for t in tree.find_all(exp.Table)
    }
    for col in tree.find_all(exp.Column):
        if col.name and _matches(col.name, excluded_columns):
            raise SqlRejected(f"La colonne « {col.name} » est exclue (donnée sensible).")
        if not col.table and col.name.lower() in row_refs:
            raise SqlRejected(
                f"« {col.name} » désigne une ligne entière : sélectionnez des colonnes explicites."
            )

    for func in tree.find_all(exp.Func):
        fname = (func.sql_name() if not isinstance(func, exp.Anonymous) else func.name).lower()
        if fname in FORBIDDEN_FUNCTIONS:
            raise SqlRejected(f"La fonction « {fname} » n'est pas autorisée.")

    return CheckedQuery(sql=sql, tables=tables)
