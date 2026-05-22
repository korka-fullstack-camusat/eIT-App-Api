import random
import time
from typing import Dict, Tuple

_store: Dict[str, Tuple[str, float]] = {}
OTP_TTL = 600  # 10 minutes


def generate_otp(email: str) -> str:
    code = f"{random.randint(0, 999999):06d}"
    _store[email.lower()] = (code, time.time() + OTP_TTL)
    return code


def verify_otp(email: str, code: str) -> bool:
    key = email.lower()
    entry = _store.get(key)
    if not entry:
        return False
    stored_code, expiry = entry
    if time.time() > expiry:
        _store.pop(key, None)
        return False
    if stored_code != code.strip():
        return False
    _store.pop(key, None)
    return True
