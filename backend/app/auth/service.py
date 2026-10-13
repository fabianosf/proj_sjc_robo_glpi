"""Serviço de autenticação do painel: allowlist + Active Directory."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from ..db_meta import cell_to_python, safe_read, table_exists
from .ad_windows import AdAuthError, validate_ad_credentials
from .config import (
    AD_PASSWORD_PLACEHOLDER,
    PROFILES,
    get_ad_domain,
    get_ad_user_map,
    get_admin_ad_users,
    get_admin_equipes,
    get_admin_matriculas,
)
from .schemas import UserPublic

logger = logging.getLogger("sgc_api")

EVENT_LOGIN_OK = "LOGIN_OK"
EVENT_LOGIN_FAIL = "LOGIN_FAIL"
EVENT_LOGOUT = "LOGOUT"


@dataclass
class AuthResult:
    """Resultado de authenticate_user (AD + allowlist)."""

    ok: bool
    row: Optional[dict] = None
    detail: str = ""
    # Motivo estruturado para HTTP/audit
    reason: str = ""  # ok | fora_allowlist | credencial_ad_invalida | ad_config | tabelas


def ensure_auth_tables(dal: Any) -> bool:
    if table_exists(dal, "Tb_Usuario_Painel") and table_exists(dal, "Tb_Auth_Audit"):
        return True
    logger.warning(
        "Tabelas de autenticação ausentes. Execute sql/criar_Tb_Auth_Painel.sql"
    )
    return False


def _row_to_user(row: dict) -> UserPublic:
    return UserPublic(
        id=int(row["id_usuario"]),
        username=str(row["username"]),
        nome=row.get("nome"),
        perfil=str(row["perfil"]),  # type: ignore[arg-type]
        ativo=bool(int(row.get("ativo") or 0)),
    )


def get_user_by_username(dal: Any, username: str) -> Optional[dict]:
    if not ensure_auth_tables(dal):
        return None
    df = safe_read(
        dal,
        """
        SELECT id_usuario, username, password_hash, perfil, nome, ativo,
               criado_em, atualizado_em, ultimo_login_em
        FROM Tb_Usuario_Painel
        WHERE username = %s
        LIMIT 1
        """,
        (username.strip(),),
    )
    if df.empty:
        return None
    return {str(k): cell_to_python(v) for k, v in df.iloc[0].items()}


def get_user_by_id(dal: Any, user_id: int) -> Optional[dict]:
    if not ensure_auth_tables(dal):
        return None
    df = safe_read(
        dal,
        """
        SELECT id_usuario, username, password_hash, perfil, nome, ativo,
               criado_em, atualizado_em, ultimo_login_em
        FROM Tb_Usuario_Painel
        WHERE id_usuario = %s
        LIMIT 1
        """,
        (int(user_id),),
    )
    if df.empty:
        return None
    return {str(k): cell_to_python(v) for k, v in df.iloc[0].items()}


def user_public_from_row(row: dict) -> UserPublic:
    return _row_to_user(row)


def record_audit(
    dal: Any,
    *,
    username: Optional[str],
    evento: str,
    sucesso: bool,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    detalhe: Optional[str] = None,
) -> None:
    if not table_exists(dal, "Tb_Auth_Audit"):
        logger.warning("Tb_Auth_Audit ausente — auditoria não gravada (%s)", evento)
        return
    try:
        dal.create(
            """
            INSERT INTO Tb_Auth_Audit
                (username, evento, sucesso, ip, user_agent, detalhe, criado_em)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                (username or "")[:80] or None,
                evento[:40],
                1 if sucesso else 0,
                (ip or "")[:64] or None,
                (user_agent or "")[:255] or None,
                (detalhe or "")[:255] or None,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
    except Exception as exc:
        logger.warning("Falha ao gravar auditoria auth: %s", exc)


def mark_last_login(dal: Any, user_id: int) -> None:
    try:
        dal.update(
            "UPDATE Tb_Usuario_Painel SET ultimo_login_em = %s WHERE id_usuario = %s",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), int(user_id)),
        )
    except Exception as exc:
        logger.warning("Falha ao atualizar ultimo_login_em: %s", exc)


def _normalize_matricula(value: str) -> str:
    """Normaliza matrícula para comparação (trim, upper; remove zeros à esquerda se numérica)."""
    raw = (value or "").strip().upper()
    if not raw:
        return ""
    if raw.isdigit():
        stripped = raw.lstrip("0")
        return stripped or "0"
    return raw


def _normalize_ad_user(value: str) -> str:
    """Login Windows/AD (sAMAccountName); remove domínio se vier DOMAIN\\user."""
    raw = (value or "").strip()
    if not raw:
        return ""
    if "\\" in raw:
        raw = raw.split("\\")[-1]
    if "@" in raw:
        raw = raw.split("@", 1)[0]
    return raw.strip()


def _link_empty_atrib_matricula(dal: Any, usuario: str, matricula: str) -> None:
    """Grava matrícula em Tb_Atrib só se Usuario existir e o campo estiver vazio."""
    from ..db_meta import columns_of, resolve_column

    user = _normalize_ad_user(usuario)
    mat = _normalize_matricula(matricula)
    if not user or not mat or not mat.isdigit() or mat in ("0", "00000"):
        return
    if not table_exists(dal, "Tb_Atrib"):
        return
    cols = columns_of(dal, "Tb_Atrib")
    col_user = resolve_column(cols, "Usuario")
    col_mat = resolve_column(cols, "Matricula", "matricula", "MATRICULA")
    if not col_user or not col_mat:
        return
    dal.update(
        f"""
        UPDATE Tb_Atrib
        SET `{col_mat}` = %s
        WHERE UPPER(TRIM(`{col_user}`)) = %s
          AND TRIM(COALESCE(`{col_mat}`, '')) IN ('', '0', '00000')
        """,
        (mat[:10], user.upper()),
    )


def resolve_ad_logon(dal: Any, login_field: str) -> tuple[str, str]:
    """
    Resolve (matricula_canon, ad_logon) a partir do campo do formulário.

    - Se digitar matrícula (ex. 59817): AD via SGC_AUTH_AD_USER_MAP ou Tb_Atrib.Usuario.
    - Se digitar login AD (ex. fabiano.freitas): matrícula via mapa reverso ou Tb_Atrib.Matricula.
    """
    raw = (login_field or "").strip()
    if not raw:
        return "", ""

    ad_direct = _normalize_ad_user(raw)
    mat_as_num = _normalize_matricula(raw)
    user_map = get_ad_user_map()
    # chaves do mapa já em upper; valores = sAMAccountName
    reverse_map = {v.strip().lower(): k for k, v in user_map.items() if v.strip()}

    # Entrada parece login AD (tem letra / ponto), não só dígitos
    looks_like_ad = bool(ad_direct) and not raw.isdigit()

    if looks_like_ad:
        mat = reverse_map.get(ad_direct.lower(), "")
        if not mat and table_exists(dal, "Tb_Atrib"):
            df = safe_read(
                dal,
                """
                SELECT TRIM(Matricula) AS Matricula
                FROM Tb_Atrib
                WHERE UPPER(TRIM(Usuario)) = %s
                  AND TRIM(COALESCE(Matricula, '')) <> ''
                  AND TRIM(COALESCE(Matricula, '')) NOT IN ('0', '00000')
                LIMIT 1
                """,
                (ad_direct.upper(),),
            )
            if not df.empty:
                mat = _normalize_matricula(str(df.iloc[0]["Matricula"]))
        # Técnico ativo: login AD mesmo sem matrícula válida
        if not mat and is_active_technician(dal, ad_direct):
            return ad_direct.upper(), ad_direct
        return mat or ad_direct.upper(), ad_direct

    # Entrada numérica = matrícula
    mat = mat_as_num
    ad_user = user_map.get(mat, "")
    if not ad_user and table_exists(dal, "Tb_Atrib"):
        df = safe_read(
            dal,
            """
            SELECT TRIM(Usuario) AS Usuario
            FROM Tb_Atrib
            WHERE (Sit = 1 OR Sit = '1')
              AND TRIM(COALESCE(Matricula, '')) <> ''
              AND TRIM(COALESCE(Matricula, '')) NOT IN ('0', '00000')
              AND (
                UPPER(TRIM(Matricula)) = %s
                OR TRIM(LEADING '0' FROM TRIM(Matricula)) = %s
              )
            LIMIT 1
            """,
            (mat, mat),
        )
        if not df.empty:
            ad_user = _normalize_ad_user(str(df.iloc[0]["Usuario"] or ""))
        # Também aceita matrícula em linhas inativas se houver Usuario
        if not ad_user:
            df2 = safe_read(
                dal,
                """
                SELECT TRIM(Usuario) AS Usuario
                FROM Tb_Atrib
                WHERE TRIM(COALESCE(Matricula, '')) <> ''
                  AND TRIM(COALESCE(Matricula, '')) NOT IN ('0', '00000')
                  AND (
                    UPPER(TRIM(Matricula)) = %s
                    OR TRIM(LEADING '0' FROM TRIM(Matricula)) = %s
                  )
                LIMIT 1
                """,
                (mat, mat),
            )
            if not df2.empty:
                ad_user = _normalize_ad_user(str(df2.iloc[0]["Usuario"] or ""))
    if not ad_user:
        ad_user = mat
    return mat, ad_user


def is_allowed(dal: Any, matricula: str) -> bool:
    """
    True somente para:
      - matrículas em SGC_AUTH_ADMIN_MATRICULAS (ex.: 59817), ou
      - técnico ativo (Sit=1) da equipe N3 (SGC_AUTH_ADMIN_EQUIPES)
        com Tb_Atrib.Matricula igual ao login.

    Ninguém mais entra. Login é sempre pela matrícula (não por Usuario AD/nome).
    Ignora Matricula vazia / placeholder 00000.
    """
    mat = _normalize_matricula(matricula)
    if not mat or mat in ("0", "00000"):
        return False
    admin_mats = {_normalize_matricula(x) for x in get_admin_matriculas()}
    if mat in admin_mats:
        return True
    if not table_exists(dal, "Tb_Atrib"):
        logger.warning("Tb_Atrib ausente — allowlist por equipe indisponível")
        return False
    equipes = get_admin_equipes()
    if not equipes:
        return False
    placeholders = ", ".join(["%s"] * len(equipes))
    df = safe_read(
        dal,
        f"""
        SELECT 1 AS ok
        FROM Tb_Atrib
        WHERE (Sit = 1 OR Sit = '1')
          AND UPPER(TRIM(Equipe)) IN ({placeholders})
          AND TRIM(COALESCE(Matricula, '')) <> ''
          AND TRIM(COALESCE(Matricula, '')) NOT IN ('0', '00000')
          AND (
            UPPER(TRIM(Matricula)) = %s
            OR TRIM(LEADING '0' FROM TRIM(Matricula)) = %s
          )
        LIMIT 1
        """,
        (*sorted(equipes), mat, mat),
    )
    return not df.empty


def is_admin_ad_user(ad_logon: str) -> bool:
    """True se o sAMAccountName está em SGC_AUTH_ADMIN_AD_USERS."""
    user = _normalize_ad_user(ad_logon).lower()
    if not user:
        return False
    return user in get_admin_ad_users()


def is_active_technician(dal: Any, ad_logon: str) -> bool:
    """True se Usuario existe em Tb_Atrib com Sit=1 (qualquer equipe)."""
    user = _normalize_ad_user(ad_logon)
    if not user or not table_exists(dal, "Tb_Atrib"):
        return False
    df = safe_read(
        dal,
        """
        SELECT 1 AS ok
        FROM Tb_Atrib
        WHERE UPPER(TRIM(Usuario)) = %s
          AND (Sit = 1 OR Sit = '1')
        LIMIT 1
        """,
        (user.upper(),),
    )
    return not df.empty


def upsert_painel_user(
    dal: Any,
    *,
    username: str,
    nome: Optional[str] = None,
    perfil: str = "CONSULTA",
) -> dict:
    """Garante linha local em Tb_Usuario_Painel para JWT; não armazena senha AD."""
    if perfil not in PROFILES:
        perfil = "CONSULTA"
    existing = get_user_by_username(dal, username)
    if existing:
        try:
            dal.update(
                """
                UPDATE Tb_Usuario_Painel
                SET perfil = %s,
                    ativo = 1,
                    password_hash = %s,
                    nome = COALESCE(%s, nome)
                WHERE id_usuario = %s
                """,
                (
                    perfil,
                    AD_PASSWORD_PLACEHOLDER,
                    (nome or "").strip() or None,
                    int(existing["id_usuario"]),
                ),
            )
        except Exception as exc:
            logger.warning("Falha ao atualizar usuário painel: %s", exc)
        row = get_user_by_username(dal, username)
        if not row:
            raise RuntimeError("Usuário painel sumiu após update.")
        return row

    ok = dal.create(
        """
        INSERT INTO Tb_Usuario_Painel
            (username, password_hash, perfil, nome, ativo)
        VALUES (%s, %s, %s, %s, 1)
        """,
        (
            username.strip(),
            AD_PASSWORD_PLACEHOLDER,
            perfil,
            (nome or "").strip() or None,
        ),
    )
    if not ok:
        raise RuntimeError("Falha ao inserir usuário painel.")
    row = get_user_by_username(dal, username)
    if not row:
        raise RuntimeError("Usuário painel não encontrado após insert.")
    return row


def upsert_ad_admin(
    dal: Any,
    *,
    username: str,
    nome: Optional[str] = None,
) -> dict:
    """Compat: grava ADMIN. Preferir upsert_painel_user com perfil explícito."""
    return upsert_painel_user(dal, username=username, nome=nome, perfil="ADMIN")


def authenticate_user(dal: Any, username: str, password: str) -> AuthResult:
    """
    Fluxo: resolve login → allowlist (mapa / N3 / AD admin / técnico Sit=1)
    → LogonUser AD → upsert painel.
    ADMIN de escrita: só SGC_AUTH_ADMIN_MATRICULAS ou SGC_AUTH_ADMIN_AD_USERS.
    N3 / demais Sit=1: entram como CONSULTA (podem logar; sem redirect/PATCH).
    Campo: matrícula ou usuário Windows. Matrícula opcional se Sit=1.
    """
    if not ensure_auth_tables(dal):
        return AuthResult(ok=False, reason="tabelas", detail="tabelas_auth_ausentes")

    login_field = (username or "").strip()
    if not login_field:
        return AuthResult(ok=False, reason="fora_allowlist", detail="matricula_vazia")

    matricula, ad_logon = resolve_ad_logon(dal, login_field)
    if not ad_logon:
        return AuthResult(ok=False, reason="fora_allowlist", detail="matricula_vazia")

    allowed_mat = is_allowed(dal, matricula) if matricula else False
    allowed_ad = is_admin_ad_user(ad_logon)
    allowed_tech = is_active_technician(dal, ad_logon)
    if not allowed_mat and not allowed_ad and not allowed_tech:
        return AuthResult(
            ok=False,
            reason="fora_allowlist",
            detail="fora_allowlist",
        )

    domain = get_ad_domain()
    try:
        ad_ok = validate_ad_credentials(ad_logon, password, domain)
    except AdAuthError as exc:
        logger.error("AD_CONFIG: %s", exc)
        return AuthResult(ok=False, reason="ad_config", detail=str(exc)[:200])

    if not ad_ok:
        logger.info(
            "AD_AUTH_DENIED matricula=%s ad_user=%s domain=%s",
            matricula,
            ad_logon,
            domain,
        )
        return AuthResult(
            ok=False,
            reason="credencial_ad_invalida",
            detail="credencial_ad_invalida",
        )

    # Identidade local: matrícula numérica válida se allowlist por mat; senão login AD
    mat_n = _normalize_matricula(matricula) if matricula else ""
    if mat_n and mat_n.isdigit() and mat_n not in ("0", "00000"):
        try:
            _link_empty_atrib_matricula(dal, ad_logon, mat_n)
        except Exception as exc:
            logger.warning("Login: não gravou matrícula em Tb_Atrib: %s", exc)
    if allowed_mat and mat_n and mat_n not in ("0", "00000") and mat_n.isdigit():
        local_user = mat_n
    else:
        local_user = ad_logon
    # ADMIN só por matrícula explícita na allowlist ou AD admin — N3 ≠ ADMIN
    admin_mats = {_normalize_matricula(x) for x in get_admin_matriculas()}
    is_write_admin = bool(allowed_ad) or (
        bool(mat_n) and mat_n not in ("0", "00000") and mat_n in admin_mats
    )
    perfil = "ADMIN" if is_write_admin else "CONSULTA"
    try:
        row = upsert_painel_user(
            dal, username=local_user, nome=ad_logon, perfil=perfil
        )
    except Exception as exc:
        logger.error("Falha upsert usuário após AD ok: %s", exc)
        return AuthResult(ok=False, reason="ad_config", detail="falha_persistir_usuario")

    if str(row.get("perfil") or "") not in PROFILES:
        return AuthResult(ok=False, reason="ad_config", detail="perfil_invalido")

    return AuthResult(ok=True, row=row, reason="ok", detail="ok")


def create_user(
    dal: Any,
    *,
    username: str,
    password_hash: str,
    perfil: str,
    nome: Optional[str] = None,
) -> int:
    """Mantido para compatibilidade CLI — login do painel não usa senha local."""
    if perfil not in PROFILES:
        raise ValueError(f"Perfil inválido: {perfil}")
    ok = dal.create(
        """
        INSERT INTO Tb_Usuario_Painel
            (username, password_hash, perfil, nome, ativo)
        VALUES (%s, %s, %s, %s, 1)
        """,
        (username.strip(), password_hash, perfil, (nome or "").strip() or None),
    )
    if not ok:
        raise RuntimeError("Falha ao inserir usuário.")
    row = get_user_by_username(dal, username)
    if not row:
        raise RuntimeError("Usuário não encontrado após insert.")
    return int(row["id_usuario"])
