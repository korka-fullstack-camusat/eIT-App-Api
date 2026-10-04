"""Authentification HTTP Basic (comptes définis dans ASSISTANT_USERS)."""
from __future__ import annotations

from functools import lru_cache

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from .config import get_settings

security = HTTPBasic(realm="Assistant IA Camusat")

# Hash factice pour garder un temps de réponse constant quand l'utilisateur n'existe pas.
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password", bcrypt.gensalt())


@lru_cache
def _users() -> dict[str, bytes]:
    users: dict[str, bytes] = {}
    for entry in get_settings().assistant_users.split(","):
        entry = entry.strip()
        if not entry:
            continue
        name, _, hashed = entry.partition(":")
        if name and hashed:
            users[name.strip()] = hashed.strip().encode()
    return users


def current_user(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    users = _users()
    if not users:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Aucun compte configuré (variable ASSISTANT_USERS).",
        )
    hashed = users.get(credentials.username, _DUMMY_HASH)
    ok = bcrypt.checkpw(credentials.password.encode(), hashed)
    if not ok or credentials.username not in users:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Identifiants invalides.",
            headers={"WWW-Authenticate": 'Basic realm="Assistant IA Camusat"'},
        )
    return credentials.username
