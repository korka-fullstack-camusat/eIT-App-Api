"""Journal d'audit JSONL : qui a demandé quoi, et quelles requêtes ont été exécutées."""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import get_settings

_lock = threading.Lock()
log = logging.getLogger("assistant.audit")


def audit(event: str, **fields: Any) -> None:
    record = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "event": event, **fields}
    line = json.dumps(record, ensure_ascii=False, default=str)
    try:
        path = Path(get_settings().audit_log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        with _lock, path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        log.warning("Impossible d'écrire le journal d'audit ; événement : %s", line)
