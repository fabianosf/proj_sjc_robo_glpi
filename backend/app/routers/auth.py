"""Rotas de autenticação: login AD + allowlist, logout, /me."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, status

from ..auth.config import AuthConfigError, get_jwt_expire_minutes, get_jwt_secret
from ..auth.deps import CurrentUser, _client_meta
from ..auth.rate_limit import login_rate_limiter
from ..auth.schemas import LoginRequest, MessageResponse, TokenResponse, UserPublic
from ..auth.security import create_access_token
from ..auth.service import (
    EVENT_LOGIN_FAIL,
    EVENT_LOGIN_OK,
    EVENT_LOGOUT,
    authenticate_user,
    ensure_auth_tables,
    mark_last_login,
    record_audit,
    user_public_from_row,
)
from ..auth.token_revoke import revoke_jti
from ..deps import get_dal

logger = logging.getLogger("sgc_api")
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request) -> TokenResponse:
    try:
        get_jwt_secret()
    except AuthConfigError as exc:
        logger.error("%s", exc)
        raise HTTPException(
            status_code=503,
            detail="Autenticação não configurada no servidor.",
        ) from exc

    ip, ua = _client_meta(request)
    rate_key = ip or "unknown"
    if not login_rate_limiter.allow(rate_key):
        record_audit(
            get_dal(),
            username=(body.username or "").strip()[:80],
            evento=EVENT_LOGIN_FAIL,
            sucesso=False,
            ip=ip,
            user_agent=ua,
            detalhe="rate_limit",
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas tentativas de login. Aguarde um minuto.",
        )

    dal = get_dal()
    if not ensure_auth_tables(dal):
        raise HTTPException(
            status_code=503,
            detail="Tabelas de autenticação ausentes. Execute sql/criar_Tb_Auth_Painel.sql",
        )

    username = body.username.strip()

    result = authenticate_user(dal, username, body.password)
    if not result.ok or not result.row:
        detail_msg = "Usuário ou senha inválidos."
        if result.reason == "fora_allowlist":
            detail_msg = "Sem permissão de acesso ao painel."
        elif result.reason == "ad_config":
            detail_msg = "Autenticação AD indisponível. Contate o administrador."
            record_audit(
                dal,
                username=username,
                evento=EVENT_LOGIN_FAIL,
                sucesso=False,
                ip=ip,
                user_agent=ua,
                detalhe=(result.detail or result.reason)[:255],
            )
            raise HTTPException(status_code=503, detail=detail_msg)

        record_audit(
            dal,
            username=username,
            evento=EVENT_LOGIN_FAIL,
            sucesso=False,
            ip=ip,
            user_agent=ua,
            detalhe=(result.detail or result.reason or "falha")[:255],
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail_msg,
        )

    user = user_public_from_row(result.row)
    token = create_access_token(
        subject=user.username,
        user_id=user.id,
        perfil=user.perfil,
    )
    mark_last_login(dal, user.id)
    record_audit(
        dal,
        username=user.username,
        evento=EVENT_LOGIN_OK,
        sucesso=True,
        ip=ip,
        user_agent=ua,
        detalhe=f"perfil={user.perfil};auth=AD",
    )
    logger.info("LOGIN_OK user=%s perfil=%s auth=AD", user.username, user.perfil)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_minutes=get_jwt_expire_minutes(),
        user=user,
    )


@router.post("/logout", response_model=MessageResponse)
def logout(request: Request, user: CurrentUser) -> MessageResponse:
    dal = get_dal()
    ip, ua = _client_meta(request)
    jti = getattr(request.state, "auth_jti", "") or ""
    exp = int(getattr(request.state, "auth_exp", 0) or 0)
    if jti and exp:
        revoke_jti(jti, exp)
    record_audit(
        dal,
        username=user.username,
        evento=EVENT_LOGOUT,
        sucesso=True,
        ip=ip,
        user_agent=ua,
        detalhe="revoked" if jti else None,
    )
    return MessageResponse(message="Logout registrado.")


@router.get("/me", response_model=UserPublic)
def me(user: CurrentUser) -> UserPublic:
    return user
