"""Hash de senha (bcrypt) e JWT."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
import jwt
from jwt.exceptions import InvalidTokenError

from .config import get_jwt_algorithm, get_jwt_expire_minutes, get_jwt_secret
from .token_revoke import is_revoked


def hash_password(plain: str) -> str:
    if not plain or len(plain) < 8:
        raise ValueError("Senha deve ter pelo menos 8 caracteres.")
    hashed = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12))
    return hashed.decode("utf-8")


def verify_password(plain: str, password_hash: str) -> bool:
    if not plain or not password_hash:
        return False
    try:
        return bcrypt.checkpw(
            plain.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def create_access_token(
    *,
    subject: str,
    user_id: int,
    perfil: str,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=get_jwt_expire_minutes())
    payload: Dict[str, Any] = {
        "sub": subject,
        "uid": user_id,
        "perfil": perfil,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": str(uuid.uuid4()),
        "typ": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, get_jwt_secret(), algorithm=get_jwt_algorithm())


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            get_jwt_secret(),
            algorithms=[get_jwt_algorithm()],
        )
    except InvalidTokenError as exc:
        raise ValueError("Token inválido ou expirado.") from exc
    jti = str(payload.get("jti") or "")
    if jti and is_revoked(jti):
        raise ValueError("Token revogado.")
    return payload
