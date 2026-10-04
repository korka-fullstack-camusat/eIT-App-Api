"""Agent conversationnel : Claude + outils de lecture sur les bases des plateformes."""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, AsyncIterator

import anthropic

from .audit import audit
from .config import get_settings, get_sources_file
from .datasources import get_registry
from .sql_guard import SqlRejected

log = logging.getLogger("assistant.agent")

TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_tables",
        "description": (
            "Liste les tables accessibles d'une source (plateforme), avec le nombre de lignes "
            "estimé et le nombre de colonnes. À utiliser pour découvrir où se trouve une information."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source_id": {"type": "string", "description": "Identifiant de la source."},
                "name_filter": {
                    "type": "string",
                    "description": "Filtre optionnel (sous-chaîne) sur le nom des tables.",
                },
            },
            "required": ["source_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "describe_table",
        "description": (
            "Donne les colonnes (nom et type) d'une ou plusieurs tables d'une source. "
            "Toujours vérifier les colonnes avant d'écrire une requête."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source_id": {"type": "string"},
                "tables": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 10},
            },
            "required": ["source_id", "tables"],
            "additionalProperties": False,
        },
    },
    {
        "name": "run_sql",
        "description": (
            "Exécute UNE requête SELECT PostgreSQL en lecture seule sur une source et renvoie "
            "les lignes (maximum 200). Chaque appel reçoit une référence de source (ex. S3) "
            "à citer dans la réponse. Préférez les agrégats (COUNT, SUM, GROUP BY) et un LIMIT "
            "plutôt que de ramener beaucoup de lignes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source_id": {"type": "string"},
                "sql": {"type": "string", "description": "Requête SELECT PostgreSQL."},
                "purpose": {
                    "type": "string",
                    "description": "Ce que cette requête cherche, en une phrase (affiché à l'utilisateur).",
                },
            },
            "required": ["source_id", "sql", "purpose"],
            "additionalProperties": False,
        },
    },
]


def build_system_prompt() -> str:
    sf = get_sources_file()
    reg = get_registry()
    lines = []
    for s in sf.sources:
        status = "" if reg.get(s.id).configured else " (NON CONFIGURÉE : indisponible)"
        lines.append(f"### Source `{s.id}` — {s.name}{status}\n{s.description.strip()}")
        if s.hints.strip():
            lines.append(f"Repères utiles :\n{s.hints.strip()}")
    sources_block = "\n\n".join(lines)

    return f"""Tu es l'assistant de données interne de Camusat. Tu réponds aux questions des \
collaborateurs en interrogeant directement les bases de données de production des plateformes \
de l'entreprise, en lecture seule.

Date du jour : {date.today().isoformat()}.

## Sources disponibles
{sources_block}

## Méthode
- Identifie la ou les sources pertinentes. Une question peut nécessiter plusieurs sources : \
interroge-les toutes et croise les résultats.
- Explore le schéma (list_tables, describe_table) avant d'écrire une requête si tu ne connais \
pas encore les tables et colonnes exactes. Ne devine pas les noms de colonnes.
- Écris des requêtes ciblées : agrégats, filtres, LIMIT. Si une requête échoue, lis l'erreur, \
corrige et réessaie.
- Les valeurs textuelles (noms, statuts, sites) peuvent varier en casse ou en accents : utilise \
ILIKE ou vérifie les valeurs distinctes avant de conclure qu'il n'y a pas de résultat.

## Réponse
- Réponds uniquement à partir des données obtenues avec les outils. N'invente jamais un chiffre, \
un nom ou une date. Si les données ne permettent pas de répondre, dis-le clairement et précise \
ce qui manque.
- Cite systématiquement tes sources : après chaque fait ou tableau, indique la référence entre \
crochets renvoyée par run_sql, par exemple [S2]. Plusieurs références : [S1][S3].
- Termine par une courte ligne « Sources : » qui nomme la plateforme et les tables utilisées.
- Réponds dans la langue de la question (français par défaut), de façon concise. Utilise des \
tableaux Markdown pour les listes de plus de trois éléments.
- Si un résultat est tronqué (plus de 200 lignes), signale-le et propose un filtre ou un agrégat.
- Tu ne peux rien modifier dans les bases. Si on te demande une modification, explique que tu \
es en lecture seule et indique la plateforme où la faire.
- Certaines tables et colonnes sensibles (mots de passe, jetons, coordonnées bancaires, \
données personnelles) sont volontairement masquées. Ne cherche pas à les contourner.
"""


@dataclass
class Citation:
    ref: str
    source_id: str
    source_name: str
    tables: list[str]
    sql: str
    purpose: str
    row_count: int
    truncated: bool
    executed_at: str


@dataclass
class Conversation:
    id: str
    owner: str
    messages: list[Any] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    updated: float = field(default_factory=time.monotonic)


class ConversationStore:
    TTL = 4 * 3600
    MAX = 500

    def __init__(self) -> None:
        self._items: dict[str, Conversation] = {}

    def get_or_create(self, conv_id: str | None, owner: str) -> Conversation:
        self._gc()
        conv = self._items.get(conv_id or "")
        if conv is None or conv.owner != owner:
            conv = Conversation(id=uuid.uuid4().hex, owner=owner)
            self._items[conv.id] = conv
        conv.updated = time.monotonic()
        return conv

    def _gc(self) -> None:
        now = time.monotonic()
        for k in [k for k, c in self._items.items() if now - c.updated > self.TTL]:
            del self._items[k]
        if len(self._items) > self.MAX:
            for k in sorted(self._items, key=lambda k: self._items[k].updated)[: len(self._items) - self.MAX]:
                del self._items[k]


store = ConversationStore()
_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        key = get_settings().anthropic_api_key
        _client = anthropic.AsyncAnthropic(api_key=key) if key else anthropic.AsyncAnthropic()
    return _client


def _to_json(data: Any, max_chars: int) -> str:
    text = json.dumps(data, ensure_ascii=False, default=str)
    if len(text) <= max_chars:
        return text
    # Résultat trop volumineux : on retire des lignes jusqu'à tenir dans la limite.
    if isinstance(data, dict) and isinstance(data.get("rows"), list):
        rows = data["rows"]
        while rows and len(text) > max_chars:
            rows = rows[: max(1, len(rows) * 3 // 4)] if len(rows) > 1 else []
            data = {**data, "rows": rows, "truncated": True,
                    "note": "Résultat raccourci (trop volumineux) : affinez avec un agrégat ou un filtre."}
            text = json.dumps(data, ensure_ascii=False, default=str)
    return text[:max_chars]


class Agent:
    def __init__(self, conv: Conversation, user: str):
        self.conv = conv
        self.user = user
        self.settings = get_settings()
        self.registry = get_registry()

    async def _tool(self, name: str, args: dict[str, Any]) -> tuple[str, bool, dict | None]:
        """Exécute un outil -> (contenu, is_error, événement à afficher)."""
        try:
            source_id = args.get("source_id", "")
            src = self.registry.get(source_id)
            if name == "list_tables":
                schema = await src.schema()
                flt = (args.get("name_filter") or "").lower()
                tables = [
                    {"table": t, "rows_estimate": v["rows_estimate"], "columns": len(v["columns"]),
                     **({"comment": v["comment"]} if v["comment"] else {})}
                    for t, v in sorted(schema.items()) if flt in t.lower()
                ]
                return _to_json({"source": source_id, "tables": tables}, self.settings.tool_result_max_chars), False, None

            if name == "describe_table":
                schema = await src.schema()
                out = {}
                for t in args.get("tables", []):
                    entry = schema.get(t) or schema.get(t.lower())
                    out[t] = (
                        {"columns": [f"{c} ({ty})" for c, ty in entry["columns"]],
                         "rows_estimate": entry["rows_estimate"]}
                        if entry else "Table introuvable ou non autorisée."
                    )
                return _to_json({"source": source_id, "tables": out}, self.settings.tool_result_max_chars), False, None

            if name == "run_sql":
                sql, purpose = args.get("sql", ""), args.get("purpose", "")
                try:
                    res = await src.run_select(sql)
                except SqlRejected as e:
                    audit("sql_rejected", user=self.user, conversation=self.conv.id,
                          source=source_id, sql=sql, reason=str(e))
                    return f"Requête refusée : {e}", True, None
                except psycopg_errors() as e:
                    audit("sql_error", user=self.user, conversation=self.conv.id,
                          source=source_id, sql=sql, error=str(e))
                    return f"Erreur PostgreSQL : {str(e).strip()}", True, None

                ref = f"S{len(self.conv.citations) + 1}"
                cit = Citation(
                    ref=ref, source_id=source_id, source_name=src.cfg.name, tables=res.tables,
                    sql=sql.strip(), purpose=purpose, row_count=len(res.rows),
                    truncated=res.truncated,
                    executed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                )
                self.conv.citations.append(cit)
                audit("sql_executed", user=self.user, conversation=self.conv.id, ref=ref,
                      source=source_id, sql=sql, rows=len(res.rows), duration_ms=res.duration_ms)
                payload = {
                    "ref": ref, "source": src.cfg.name, "tables": res.tables,
                    "row_count": len(res.rows), "truncated": res.truncated,
                    "columns": res.columns, "rows": res.rows,
                }
                if res.hidden_columns:
                    payload["hidden_columns"] = res.hidden_columns
                return _to_json(payload, self.settings.tool_result_max_chars), False, {"citation": cit.__dict__}

            return f"Outil inconnu : {name}", True, None
        except KeyError as e:
            return str(e.args[0] if e.args else e), True, None
        except Exception as e:  # connexion impossible, timeout…
            log.exception("Erreur outil %s", name)
            return f"Erreur lors de l'accès à la source : {type(e).__name__}: {e}", True, None

    async def run(self, question: str) -> AsyncIterator[dict[str, Any]]:
        conv = self.conv
        start_len = len(conv.messages)
        conv.messages.append({"role": "user", "content": question})
        audit("question", user=self.user, conversation=conv.id, question=question)
        first_ref = len(conv.citations)
        system = build_system_prompt()
        client = get_client()

        for _ in range(self.settings.max_agent_steps):
            try:
                response = await client.beta.messages.create(
                    model=self.settings.claude_model,
                    max_tokens=16000,
                    system=system,
                    tools=TOOLS,
                    messages=conv.messages,
                    output_config={"effort": self.settings.claude_effort},
                    cache_control={"type": "ephemeral"},
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default",
                )
            except anthropic.RateLimitError:
                del conv.messages[start_len:]  # la question pourra être reposée
                yield {"type": "error", "message": "Le service IA est saturé, réessayez dans une minute."}
                return
            except anthropic.APIStatusError as e:
                log.error("Erreur API Claude %s: %s", e.status_code, e.message)
                del conv.messages[start_len:]  # la question pourra être reposée
                yield {"type": "error", "message": f"Erreur du service IA ({e.status_code})."}
                return
            except anthropic.APIConnectionError:
                del conv.messages[start_len:]  # la question pourra être reposée
                yield {"type": "error", "message": "Impossible de joindre le service IA."}
                return

            # Historique en ajout seul : on renvoie le contenu de l'assistant tel quel.
            conv.messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "refusal":
                yield {"type": "answer", "text": "Je ne peux pas répondre à cette demande.",
                       "citations": []}
                return

            if response.stop_reason != "tool_use":
                text = "".join(b.text for b in response.content if b.type == "text").strip()
                if response.stop_reason == "max_tokens":
                    text += "\n\n_(Réponse tronquée : la réponse était trop longue.)_"
                cits = [c.__dict__ for c in conv.citations[first_ref:]]
                audit("answer", user=self.user, conversation=conv.id,
                      refs=[c["ref"] for c in cits], chars=len(text))
                yield {"type": "answer", "text": text or "(Pas de réponse.)", "citations": cits}
                return

            calls = [b for b in response.content if b.type == "tool_use"]
            for b in calls:
                yield {"type": "step", "tool": b.name, "source": b.input.get("source_id"),
                       "text": _step_label(b.name, b.input)}
            results = await asyncio.gather(*(self._tool(b.name, b.input) for b in calls))
            tool_results = []
            for b, (content, is_error, event) in zip(calls, results):
                tool_results.append({"type": "tool_result", "tool_use_id": b.id,
                                     "content": content, "is_error": is_error})
                if event:
                    yield {"type": "source", **event}
            conv.messages.append({"role": "user", "content": tool_results})

        # Trop d'étapes : on demande une synthèse avec ce qui a été trouvé.
        conv.messages[-1]["content"].append({"type": "text", "text": (
            "Limite d'étapes atteinte. Réponds maintenant avec les informations déjà obtenues, "
            "en citant les sources, et indique ce qui reste incertain.")})
        try:
            response = await client.beta.messages.create(
                model=self.settings.claude_model, max_tokens=16000, system=system, tools=TOOLS,
                tool_choice={"type": "none"},
                messages=conv.messages, output_config={"effort": self.settings.claude_effort},
                cache_control={"type": "ephemeral"},
                betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            )
        except anthropic.APIError as e:
            log.error("Erreur API Claude (synthèse finale): %s", e)
            del conv.messages[start_len:]
            yield {"type": "error", "message": "Erreur du service IA."}
            return
        conv.messages.append({"role": "assistant", "content": response.content})
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        yield {"type": "answer", "text": text or "(Pas de réponse.)",
               "citations": [c.__dict__ for c in conv.citations[first_ref:]]}


def psycopg_errors() -> tuple[type[BaseException], ...]:
    import psycopg
    return (psycopg.errors.Error,)


def _step_label(name: str, args: dict[str, Any]) -> str:
    src = args.get("source_id", "?")
    if name == "list_tables":
        return f"Exploration des tables de « {src} »"
    if name == "describe_table":
        return f"Lecture de la structure de {', '.join(args.get('tables', []))} ({src})"
    if name == "run_sql":
        return f"{src} : {args.get('purpose') or 'requête'}"
    return name
