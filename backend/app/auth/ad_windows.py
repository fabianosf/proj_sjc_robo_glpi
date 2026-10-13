"""Validação de credenciais no Active Directory via Windows LogonUser."""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("sgc_api")


class AdAuthError(RuntimeError):
    """Falha de configuração ou ambiente AD (não confundir com senha inválida)."""


def validate_ad_credentials(
    username: str,
    password: str,
    domain: str,
) -> bool:
    """
    Valida matrícula/senha contra o AD usando LogonUser (LOGON32_LOGON_NETWORK).

    Retorna True se a autenticação AD for bem-sucedida.
    Retorna False se usuário/senha inválidos.
    Levanta AdAuthError se pywin32 ausente, domínio vazio ou erro de sistema.
    Nunca registra a senha em logs.
    """
    user = (username or "").strip()
    dom = (domain or "").strip()
    if not user:
        return False
    if not dom:
        raise AdAuthError(
            "SGC_AD_DOMAIN não definido. Configure o domínio Windows/AD em backend/.env."
        )
    if password is None or password == "":
        return False

    try:
        import win32security  # type: ignore[import-untyped]
        import win32con  # type: ignore[import-untyped]
        import pywintypes  # type: ignore[import-untyped]
    except ImportError as exc:
        raise AdAuthError(
            "pywin32 não instalado. Execute: "
            "venv\\Scripts\\python.exe -m pip install -r requirements-api.txt"
        ) from exc

    handle: Optional[object] = None
    try:
        handle = win32security.LogonUser(
            user,
            dom,
            password,
            win32con.LOGON32_LOGON_NETWORK,
            win32con.LOGON32_PROVIDER_DEFAULT,
        )
        return True
    except pywintypes.error as exc:
        # 1326 = ERROR_LOGON_FAILURE (usuário/senha)
        # 1330 / 1907 / etc. = política de conta — tratar como falha de credencial
        winerror = getattr(exc, "winerror", None)
        if winerror in (1326, 1330, 1907, 1793, 1909, 1385):
            logger.info(
                "AD_LOGON_FAIL user=%s domain=%s winerror=%s",
                user,
                dom,
                winerror,
            )
            return False
        logger.warning(
            "AD_LOGON_SYSTEM_ERROR user=%s domain=%s winerror=%s",
            user,
            dom,
            winerror,
        )
        raise AdAuthError(
            f"Falha ao validar no Active Directory (código {winerror})."
        ) from exc
    finally:
        if handle is not None:
            try:
                handle.Close()
            except Exception:
                pass
