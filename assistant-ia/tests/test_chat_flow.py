"""Parcours complet /api/chat avec un faux client Claude (aucun appel réseau).

Nécessite TEST_DB_URL (voir test_datasources.py) : la requête SQL est réellement exécutée.
"""
import json
import os
from types import SimpleNamespace as NS

import bcrypt
import pytest

DSN = os.environ.get("TEST_DB_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="TEST_DB_URL non défini")


class FakeMessages:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.script.pop(0)


@pytest.fixture
def client(monkeypatch, tmp_path):
    hashed = bcrypt.hashpw(b"motdepasse-test", bcrypt.gensalt()).decode()
    monkeypatch.setenv("ASSISTANT_USERS", f"alice:{hashed}")
    monkeypatch.setenv("RH_DB_URL", DSN)
    monkeypatch.setenv("AUDIT_LOG_FILE", str(tmp_path / "audit.jsonl"))

    from app import agent, auth, config, datasources
    config.get_settings.cache_clear()
    config.get_sources_file.cache_clear()
    auth._users.cache_clear()
    datasources._registry = None

    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app), agent, tmp_path


def test_chat_with_sources(client):
    tc, agent, tmp_path = client
    sql = "SELECT service, count(*) AS n FROM hr_employees_employee WHERE status = 'ACTIVE' GROUP BY service ORDER BY service"
    fake = FakeMessages([
        NS(stop_reason="tool_use", content=[
            NS(type="tool_use", id="t1", name="run_sql",
               input={"source_id": "rh", "sql": sql, "purpose": "Effectifs actifs par service"}),
        ]),
        NS(stop_reason="end_turn", content=[
            NS(type="text", text="Il y a 3 employés actifs [S1].\n\nSources : RH › hr_employees_employee"),
        ]),
    ])
    agent._client = NS(beta=NS(messages=fake))

    assert tc.get("/").status_code == 401
    r = tc.post("/api/chat", json={"message": "Combien d'employés actifs ?"}, auth=("alice", "motdepasse-test"))
    assert r.status_code == 200
    events = [json.loads(line) for line in r.text.splitlines() if line]
    types = [e["type"] for e in events]
    assert types == ["conversation", "step", "source", "answer"]

    answer = events[-1]
    assert "[S1]" in answer["text"]
    cit = answer["citations"][0]
    assert cit["ref"] == "S1" and cit["source_id"] == "rh" and cit["row_count"] == 3
    assert cit["tables"] == ["hr_employees_employee"]

    # Le résultat SQL renvoyé à Claude contient les lignes et la référence.
    # (la liste de messages est partagée : le dernier élément est la réponse finale)
    tool_result = fake.calls[1]["messages"][-2]["content"][0]
    payload = json.loads(tool_result["content"])
    assert payload["ref"] == "S1" and {"service": "IT", "n": 1} in payload["rows"]
    assert fake.calls[0]["model"] == "claude-opus-5-5"

    audit = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    assert '"event": "sql_executed"' in audit and '"user": "alice"' in audit

    # Deuxième question, même conversation : une colonne sensible est refusée.
    fake.script = [
        NS(stop_reason="tool_use", content=[
            NS(type="tool_use", id="t2", name="run_sql",
               input={"source_id": "rh", "sql": "SELECT nom, iban FROM hr_employees_employee", "purpose": "x"}),
        ]),
        NS(stop_reason="end_turn", content=[NS(type="text", text="Donnée non accessible.")]),
    ]
    r = tc.post("/api/chat", json={"message": "IBAN ?", "conversation_id": events[0]["id"]},
                auth=("alice", "motdepasse-test"))
    events2 = [json.loads(line) for line in r.text.splitlines() if line]
    assert events2[0]["id"] == events[0]["id"]
    refused = fake.calls[-1]["messages"][-2]["content"][0]
    assert refused["is_error"] and "iban" in refused["content"]
