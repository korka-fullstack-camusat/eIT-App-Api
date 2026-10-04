"""Point d'entrée FastAPI : interface de chat + API."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agent import Agent, store
from .auth import current_user
from .config import get_sources_file
from .datasources import get_registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Assistant IA Camusat", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def index(_: str = Depends(current_user)) -> FileResponse:
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/api/sources")
async def sources(_: str = Depends(current_user)) -> list[dict]:
    reg = get_registry()
    return [
        {"id": s.id, "name": s.name, "configured": reg.get(s.id).configured}
        for s in get_sources_file().sources
    ]


@app.post("/api/chat")
async def chat(req: ChatRequest, user: str = Depends(current_user)) -> StreamingResponse:
    conv = store.get_or_create(req.conversation_id, user)
    if conv.lock.locked():
        raise HTTPException(409, "Une question est déjà en cours dans cette conversation.")

    async def events():
        async with conv.lock:
            yield json.dumps({"type": "conversation", "id": conv.id}) + "\n"
            start_len = len(conv.messages)
            try:
                async for event in Agent(conv, user).run(req.message.strip()):
                    yield json.dumps(event, ensure_ascii=False, default=str) + "\n"
            except Exception:
                logging.getLogger("assistant").exception("Erreur inattendue")
                del conv.messages[start_len:]
                yield json.dumps({"type": "error", "message": "Erreur interne de l'assistant."}) + "\n"
            except BaseException:
                # Client déconnecté en cours de route : on retire un tour resté incomplet.
                last = conv.messages[-1] if conv.messages else None
                complete = last is not None and last["role"] == "assistant" and not any(
                    getattr(b, "type", None) == "tool_use" for b in last["content"]
                )
                if not complete:
                    del conv.messages[start_len:]
                raise

    return StreamingResponse(events(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
