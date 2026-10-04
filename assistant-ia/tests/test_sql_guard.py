import pytest

from app.sql_guard import SqlRejected, check_select

OPTS = dict(
    allowed_schemas=["public"],
    excluded_tables=["django_*", "hr_employees_disciplinary*", "users_customuser"],
    excluded_columns=["*password*", "iban", "numero_*"],
)


@pytest.mark.parametrize("sql", [
    "SELECT matricule, nom FROM hr_employees_employee WHERE status = 'ACTIVE' LIMIT 10",
    "select count(*) from inventory_item;",
    "WITH s AS (SELECT warehouse_id, count(*) n FROM wh_outbounds_warehouseoutbound GROUP BY 1) SELECT * FROM s",
    "SELECT e.nom, d.name FROM hr_employees_employee e JOIN hr_employees_department d ON d.id = e.department_id",
    "SELECT * FROM public.materiels",
    "SELECT status, count(*) FROM a UNION ALL SELECT status, count(*) FROM b",
])
def test_accepts_reads(sql):
    assert check_select(sql, **OPTS).sql


@pytest.mark.parametrize("sql, fragment", [
    ("DELETE FROM inventory_item", "lecture"),
    ("UPDATE hr_employees_employee SET nom = 'x'", "lecture"),
    ("DROP TABLE materiels", "lecture"),
    ("INSERT INTO materiels(id) VALUES (1)", "lecture"),
    ("SELECT 1; DELETE FROM materiels", "Une seule"),
    ("SELECT * INTO copie FROM materiels", "lecture"),
    ("WITH d AS (DELETE FROM materiels RETURNING *) SELECT * FROM d", "lecture"),
    ("SELECT * FROM django_session", "exclue"),
    ("SELECT motif FROM hr_employees_disciplinaryrecord", "exclue"),
    ("SELECT username, password FROM users_customuser", "exclue"),
    ("SELECT nom, iban FROM hr_employees_employee", "iban"),
    ("SELECT nom FROM hr_employees_employee WHERE numero_securite_sociale = '1'", "numero_securite_sociale"),
    ("SELECT e FROM hr_employees_employee e", "ligne entière"),
    ("SELECT to_jsonb(e.*) FROM hr_employees_employee e", "to_jsonb"),
    ("SELECT pg_read_file('/etc/passwd')", "pg_read_file"),
    ("SELECT pg_sleep(100)", "pg_sleep"),
    ("SELECT * FROM pg_catalog.pg_authid", "système"),
    ("SELECT * FROM information_schema.columns", "système"),
    ("SELECT * FROM autre.materiels", "Schéma"),
    ("COPY materiels TO '/tmp/x'", ""),
    ("", "vide"),
])
def test_rejects(sql, fragment):
    with pytest.raises(SqlRejected) as e:
        check_select(sql, **OPTS)
    assert fragment in str(e.value)
