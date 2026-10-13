"""Leitura de matrícula e e-mail no AD (employeeNumber / mail / UPN)."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger("sgc_api")

_SAFE_SAM = re.compile(r"^[A-Za-z0-9._\-]+$")


@dataclass(frozen=True)
class AdIdentity:
    sam: str
    matricula: Optional[str] = None
    mail: Optional[str] = None
    given_name: Optional[str] = None
    sn: Optional[str] = None
    display_name: Optional[str] = None

    @property
    def person_name(self) -> Optional[str]:
        gn = (self.given_name or "").strip()
        family = (self.sn or "").strip()
        if gn and family:
            return f"{gn} {family}"
        disp = (self.display_name or "").strip()
        return disp or None


def get_ad_ldap_root() -> str:
    """
    Root LDAP do domínio (igual ao basedn do AuthLDAP do GLPI).
    Ex.: LDAP://GRBF/dc=grbf,dc=dom
    """
    raw = (os.getenv("SGC_AD_LDAP_ROOT") or "").strip()
    if raw:
        return raw
    domain = (os.getenv("SGC_AD_DOMAIN") or "GRBF").strip() or "GRBF"
    # GRBF → dc=grbf,dc=dom (padrão do ambiente Redentor/UCS)
    return f"LDAP://{domain}/dc={domain.lower()},dc=dom"


def _ad_str(raw: object) -> str:
    if raw is None:
        return ""
    if isinstance(raw, (list, tuple)):
        raw = raw[0] if raw else ""
    s = str(raw).strip()
    if s.lower() in ("none", "null"):
        return ""
    return s


def _ad_field(rs: object, name: str) -> str:
    try:
        return _ad_str(rs.Fields(name).Value)  # type: ignore[union-attr]
    except Exception:
        return ""


def _normalize_mat(raw: object) -> Optional[str]:
    s = _ad_str(raw)
    if not s or s in ("0", "00000"):
        return None
    if len(s) > 10:
        s = s[:10]
    return s


def fetch_ad_identities(sam_accounts: list[str]) -> Dict[str, AdIdentity]:
    """
    Busca employeeNumber/employeeID, mail e userPrincipalName no AD via ADSI/ADODB.

    Requer processo Windows autenticado no domínio (sem senha no .env).
    Inclui contas mesmo sem matrícula, para cruzar e-mail com o Oracle.
    """
    wanted = sorted({(u or "").strip() for u in sam_accounts if (u or "").strip()})
    wanted = [u for u in wanted if _SAFE_SAM.match(u)]
    if not wanted:
        return {}

    try:
        import win32com.client  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("pywin32 ausente — sync AD indisponível")
        return {}

    root = get_ad_ldap_root()
    out: Dict[str, AdIdentity] = {}
    try:
        conn = win32com.client.Dispatch("ADODB.Connection")
        conn.Provider = "ADsDSOObject"
        conn.Open("Active Directory Provider")
        cmd = win32com.client.Dispatch("ADODB.Command")
        cmd.ActiveConnection = conn
        try:
            cmd.Properties("Page Size").Value = 200
        except Exception:
            pass

        batch_size = 40
        attrs = (
            "sAMAccountName,employeeNumber,employeeID,mail,userPrincipalName,"
            "givenName,sn,displayName"
        )
        for i in range(0, len(wanted), batch_size):
            batch = wanted[i : i + batch_size]
            clauses = "".join(f"(sAMAccountName={u})" for u in batch)
            filt = f"(&(objectClass=user)(|{clauses}))"
            cmd.CommandText = f"<{root}>;{filt};{attrs};subtree"
            rs, _ = cmd.Execute()
            while not rs.EOF:
                sam = _ad_field(rs, "sAMAccountName")
                emp = _ad_field(rs, "employeeNumber")
                emp_id = _ad_field(rs, "employeeID")
                mail = _ad_field(rs, "mail") or _ad_field(rs, "userPrincipalName")
                mat = _normalize_mat(emp) or _normalize_mat(emp_id)
                given = _ad_field(rs, "givenName") or None
                sn = _ad_field(rs, "sn") or None
                display = _ad_field(rs, "displayName") or None
                if sam:
                    out[sam] = AdIdentity(
                        sam=sam,
                        matricula=mat,
                        mail=mail or None,
                        given_name=given,
                        sn=sn,
                        display_name=display,
                    )
                rs.MoveNext()
        conn.Close()
    except Exception as exc:
        logger.warning("AD identity lookup falhou: %s", exc)
        return {}

    logger.info(
        "AD identidades: %s / %s (com matrícula=%s com e-mail=%s com nome=%s)",
        len(out),
        len(wanted),
        sum(1 for v in out.values() if v.matricula),
        sum(1 for v in out.values() if v.mail),
        sum(1 for v in out.values() if v.person_name),
    )
    return out


def fetch_employee_numbers(sam_accounts: list[str]) -> Dict[str, str]:
    """
    Busca employeeNumber (e fallback employeeID) no AD via ADSI/ADODB.

    Mesmo mapeamento do GLPI: AuthLDAP.registration_number_field = employeenumber
    → glpi_users.registration_number.
    """
    identities = fetch_ad_identities(sam_accounts)
    return {sam: ident.matricula for sam, ident in identities.items() if ident.matricula}
