"""Tests d'intégration sur une vraie base PostgreSQL.

Lancés seulement si TEST_DB_URL pointe vers une base de test contenant les tables
hr_employees_employee (avec une colonne iban) et users_customuser, par ex. :
  TEST_DB_URL=postgresql://assistant_ro:...@localhost:5432/rh_test pytest
"""
import asyncio
import os

import pytest

from app.config import SourceConfig
from app.datasources import DataSource
from app.sql_guard import SqlRejected

DSN = os.environ.get("TEST_DB_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="TEST_DB_URL non défini")


def make_source() -> DataSource:
    os.environ["ASSISTANT_TEST_DSN"] = DSN or ""
    cfg = SourceConfig(id="rh", name="RH", dsn_env="ASSISTANT_TEST_DSN",
                       exclude_tables=["users_*"], exclude_columns=["iban", "numero_*"])
    return DataSource(cfg, global_tables=["django_*"], global_columns=["*password*"])


def test_schema_hides_sensitive():
    schema = asyncio.run(make_source().schema())
    assert "hr_employees_employee" in schema
    assert "users_customuser" not in schema
    cols = [c for c, _ in schema["hr_employees_employee"]["columns"]]
    assert "nom" in cols and "iban" not in cols and "numero_securite_sociale" not in cols


def test_star_select_drops_sensitive_columns():
    res = asyncio.run(make_source().run_select("SELECT * FROM hr_employees_employee"))
    assert "iban" in res.hidden_columns
    assert all("iban" not in r for r in res.rows)
    assert "nom" in res.columns


def test_rejected_before_execution():
    with pytest.raises(SqlRejected):
        asyncio.run(make_source().run_select("SELECT username FROM users_customuser"))


def test_session_is_read_only():
    # Une écriture déguisée dans une fonction volatile doit échouer côté serveur.
    import psycopg
    with pytest.raises(psycopg.errors.Error):
        asyncio.run(make_source().run_select("SELECT nextval('hr_employees_employee_id_seq')"))
