"""Dependências FastAPI de autenticação e autorização."""

from __future__ import annotations

import logging
from typing import Annotated, Callable, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..deps import get_dal
from .config import PROFILE_RANK, AuthConfigError, get_jwt_secret
from .schemas import UserPublic
from .security import decode_access_token
from .service import ensure_auth_tables, get_user_by_id, user_public_from_row

logger = logging.getLogger("sgc_api")

_bearer = HTTPBearer(auto_error=False)


def _client_meta(request: Request) -> tuple[Optional[str], Optional[str]]:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    return ip, ua


def get_current_user(
    request: Request,
    creds: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer)] = None,
) -> UserPublic:
    try:
        get_jwt_secret()
    except AuthConfigError as exc:
        logger.error("%s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Autenticação não configurada no servidor.",
        ) from exc

    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação necessária.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(creds.credentials)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    if payload.get("typ") != "access":
        raise HTTPException(status_code=401, detail="Token inválido.")

    uid = payload.get("uid")
    if uid is None:
        raise HTTPException(status_code=401, detail="Token inválido.")

    dal = get_dal()
    if not ensure_auth_tables(dal):
        raise HTTPException(
            status_code=503,
            detail="Tabelas de autenticação ausentes. Execute a migration SQL.",
        )

    row = get_user_by_id(dal, int(uid))
    if not row or not int(row.get("ativo") or 0):
        raise HTTPException(status_code=401, detail="Usuário inativo ou inexistente.")

    user = user_public_from_row(row)
    request.state.auth_username = user.username
    request.state.auth_jti = str(payload.get("jti") or "")
    request.state.auth_exp = int(payload.get("exp") or 0)
    return user


def require_profiles(*allowed: str) -> Callable:
    """Exige um dos perfis; ADMIN sempre autorizado."""

    allowed_set = set(allowed)

    def _dep(user: Annotated[UserPublic, Depends(get_current_user)]) -> UserPublic:
        if user.perfil == "ADMIN":
            return user
        if user.perfil not in allowed_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissão insuficiente para este recurso.",
            )
        return user

    return _dep


def require_min_rank(min_perfil: str) -> Callable:
    """Exige perfil com rank >= ao informado (CONSULTA < OPERADOR < GESTOR < ADMIN)."""

    min_rank = PROFILE_RANK.get(min_perfil, 99)

    def _dep(user: Annotated[UserPublic, Depends(get_current_user)]) -> UserPublic:
        rank = PROFILE_RANK.get(user.perfil, 0)
        if rank < min_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissão insuficiente para este recurso.",
            )
        return user

    return _dep


CurrentUser = Annotated[UserPublic, Depends(get_current_user)]
