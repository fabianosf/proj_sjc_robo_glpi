"""Denylist em memória de JWT (jti) até expiração — mitiga logout sem revogação."""

from __future__ import annotations

import threading
import time
from typing import Dict, Optional

_lock = threading.Lock()
# jti -> unix exp
_revoked: Dict[str, int] = {}


def _purge_unlocked(now: Optional[int] = None) -> None:
    ts = int(now if now is not None else time.time())
    dead = [k for k, exp in _revoked.items() if exp <= ts]
    for k in dead:
        del _revoked[k]


def revoke_jti(jti: str, exp: int) -> None:
    if not jti:
        return
    with _lock:
        _purge_unlocked()
        _revoked[str(jti)] = int(exp)


def is_revoked(jti: str) -> bool:
    if not jti:
        return False
    with _lock:
        _purge_unlocked()
        exp = _revoked.get(str(jti))
        if exp is None:
            return False
        if exp <= int(time.time()):
            del _revoked[str(jti)]
            return False
        return True
