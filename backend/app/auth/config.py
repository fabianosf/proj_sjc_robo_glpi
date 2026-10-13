"""Configuração de autenticação — segredos somente via ambiente."""

from __future__ import annotations

import os
from functools import lru_cache


class AuthConfigError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def get_jwt_secret() -> str:
    secret = (os.getenv("SGC_JWT_SECRET") or "").strip()
    if not secret:
        raise AuthConfigError(
            "SGC_JWT_SECRET não definido. Configure a variável de ambiente "
            "antes de iniciar a API (nunca use segredo hardcoded)."
        )
    if len(secret) < 32:
        raise AuthConfigError(
            "SGC_JWT_SECRET deve ter pelo menos 32 caracteres."
        )
    return secret


def get_jwt_algorithm() -> str:
    return (os.getenv("SGC_JWT_ALGORITHM") or "HS256").strip() or "HS256"


def get_jwt_expire_minutes() -> int:
    # Default 120 min (mais curto que 480) — logout também revoga jti em memória
    raw = os.getenv("SGC_JWT_EXPIRE_MINUTES", "120")
    try:
        value = int(raw)
    except ValueError:
        return 120
    return max(5, min(value, 60 * 24 * 7))  # 5 min … 7 dias


PROFILES = ("ADMIN", "GESTOR", "OPERADOR", "CONSULTA")

# Hierarquia: ADMIN inclui tudo; demais listados por recurso
PROFILE_RANK = {
    "CONSULTA": 1,
    "OPERADOR": 2,
    "GESTOR": 3,
    "ADMIN": 4,
}

# Placeholder em Tb_Usuario_Painel — senha real nunca é armazenada (auth = AD)
AD_PASSWORD_PLACEHOLDER = "!AD_AUTH_NO_LOCAL_PASSWORD!"


def get_ad_domain() -> str:
    return (os.getenv("SGC_AD_DOMAIN") or "").strip()


def get_admin_matriculas() -> frozenset[str]:
    raw = os.getenv("SGC_AUTH_ADMIN_MATRICULAS", "59817")
    items = {p.strip().upper() for p in raw.split(",") if p.strip()}
    return frozenset(items) if items else frozenset({"59817"})


def get_admin_equipes() -> frozenset[str]:
    raw = os.getenv("SGC_AUTH_ADMIN_EQUIPES", "N3")
    items = {p.strip().upper() for p in raw.split(",") if p.strip()}
    return frozenset(items) if items else frozenset({"N3"})


def get_ad_user_map() -> dict[str, str]:
    """
    Mapa matrícula → sAMAccountName AD.
    Formato: SGC_AUTH_AD_USER_MAP=59817:fabiano.freitas,12345:outro.user
    Necessário quando a matrícula não é o login Windows.
    """
    raw = (os.getenv("SGC_AUTH_AD_USER_MAP") or "").strip()
    out: dict[str, str] = {}
    if not raw:
        return out
    for part in raw.split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        mat, ad_user = part.split(":", 1)
        mat_n = mat.strip().upper()
        ad_n = ad_user.strip()
        if mat_n and ad_n:
            out[mat_n] = ad_n
    return out


def get_admin_ad_users() -> frozenset[str]:
    """
    Logins Windows (sAMAccountName) com acesso ADMIN explícito.
    Formato: SGC_AUTH_ADMIN_AD_USERS=juan.damasceno,andrew.silva
    """
    raw = (os.getenv("SGC_AUTH_ADMIN_AD_USERS") or "").strip()
    items = {p.strip().lower() for p in raw.split(",") if p.strip()}
    return frozenset(items)
