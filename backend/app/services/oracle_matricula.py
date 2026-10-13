"""Matrículas no Oracle Globus (FLP_FUNCIONARIOS) via conf/conf_oracle/erp.dat."""

from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger("sgc_api")

_SAFE_LOGIN = re.compile(r"^[A-Za-z0-9._\-]+$")
_NODOT = re.compile(r"[._\-]+")
_PARTICLES = frozenset({"DE", "DA", "DO", "DOS", "DAS", "E", "DEL", "DI"})

# (chapa, ativo) — None no valor marca conflito (não usar essa chave)
EmailIndex = Dict[str, Optional[Tuple[str, bool]]]
NameRow = Tuple[str, str, bool]  # nome (qualquer caixa), chapa, ativo


def _oracle_conf_dir() -> Path:
    from ..bootstrap import PROJECT_ROOT

    return PROJECT_ROOT / "conf" / "conf_oracle"


def _normalize_chapa(raw: object) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s in ("0", "00000"):
        return None
    if s.isdigit():
        s = s.lstrip("0") or "0"
    if not s or s in ("0", "00000"):
        return None
    return s[:10]


def _email_local(email: object) -> str:
    s = str(email or "").strip().lower()
    if not s:
        return ""
    if "<" in s and ">" in s:
        inner = s[s.find("<") + 1 : s.find(">")].strip()
        if inner:
            s = inner
    if "@" in s:
        s = s.split("@", 1)[0].strip()
    return s


def _nodot(s: str) -> str:
    return _NODOT.sub("", (s or "").lower())


def _fold_ascii(s: str) -> str:
    nfd = unicodedata.normalize("NFD", s or "")
    stripped = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return stripped.upper()


def _significant_tokens(nome: str) -> List[str]:
    folded = _fold_ascii(nome)
    return [t for t in folded.replace(".", " ").split() if t and t not in _PARTICLES]


def _person_first_last(nome: str) -> Tuple[str, str]:
    toks = _significant_tokens(nome)
    if len(toks) < 2:
        return "", ""
    return toks[0], toks[-1]


def _is_active(situacao: object) -> bool:
    s = str(situacao or "").strip().upper()
    return s in ("A", "ATIVO", "1")


def _put_email(index: EmailIndex, key: str, chapa: str, active: bool) -> None:
    if not key:
        return
    prev = index.get(key)
    if prev is None and key not in index:
        index[key] = (chapa, active)
        return
    if prev is None:
        return
    prev_chapa, prev_active = prev
    if prev_chapa == chapa:
        if active and not prev_active:
            index[key] = (chapa, True)
        return
    if active and not prev_active:
        index[key] = (chapa, True)
        return
    if prev_active and not active:
        return
    index[key] = None


def _name_match(first: str, last: str, nome: str) -> bool:
    tokens = _significant_tokens(nome)
    if not tokens:
        return False
    first_u = _fold_ascii(first).split()[0] if first else ""
    last_u = _fold_ascii(last).split()[-1] if last else ""
    if not first_u or not last_u:
        return False
    head = tokens[0]
    first_ok = head == first_u or (len(first_u) >= 2 and head.startswith(first_u))
    return first_ok and last_u in tokens


def _unique_name_chapa(first: str, last: str, name_rows: Sequence[NameRow]) -> Optional[str]:
    def search(only_active: bool) -> Optional[str]:
        hits: List[str] = []
        for nome, chapa, active in name_rows:
            if only_active and not active:
                continue
            if _name_match(first, last, nome):
                hits.append(chapa)
        uniq = sorted(set(hits))
        if len(uniq) == 1:
            return uniq[0]
        return None

    return search(True) or search(False)


def _name_ambiguous(first: str, last: str, name_rows: Sequence[NameRow]) -> bool:
    active_hits = {
        chapa
        for nome, chapa, active in name_rows
        if active and _name_match(first, last, nome)
    }
    all_hits = {chapa for nome, chapa, _a in name_rows if _name_match(first, last, nome)}
    return len(active_hits) > 1 or (not active_hits and len(all_hits) > 1)


def _lookup_email(index: EmailIndex, key: str) -> Optional[str]:
    hit = index.get(key)
    if hit:
        return hit[0]
    return None


def _resolve_key(
    key: str,
    by_email: EmailIndex,
    by_email_nodot: EmailIndex,
    name_rows: Sequence[NameRow],
) -> Tuple[Optional[str], bool]:
    """Retorna (chapa, ambíguo_por_nome)."""
    key = (key or "").strip().lower()
    if not key:
        return None, False
    mat = _lookup_email(by_email, key)
    if mat:
        return mat, False
    nd = _nodot(key)
    if nd:
        mat = _lookup_email(by_email_nodot, nd)
        if mat:
            return mat, False
    parts = [p for p in key.split(".") if p]
    if len(parts) < 2:
        return None, False
    first, last = _fold_ascii(parts[0]), _fold_ascii(parts[-1])
    chapa = _unique_name_chapa(first, last, name_rows)
    if chapa:
        return chapa, False
    return None, _name_ambiguous(first, last, name_rows)


def match_logins_to_chapas(
    funcionarios: Iterable[dict],
    logins: Sequence[str],
    extra_emails: Optional[Dict[str, str]] = None,
    extra_names: Optional[Dict[str, str]] = None,
) -> Tuple[Dict[str, str], List[str]]:
    """
    Casa logins AD com CHAPAFUNC. Só resultado único.

    funcionarios: dicts com CHAPAFUNC/chapa, NOMEFUNC/nome, EMAILFUNC/email,
    SITUACAOFUNC/situacao.
    extra_emails: login → e-mail (AD mail/UPN).
    extra_names: login → nome da pessoa (givenName+sn ou displayName).
    """
    by_email: EmailIndex = {}
    by_email_nodot: EmailIndex = {}
    name_rows: List[NameRow] = []

    for row in funcionarios:
        chapa = _normalize_chapa(
            row.get("CHAPAFUNC") if "CHAPAFUNC" in row else row.get("chapa")
        )
        if not chapa:
            continue
        situacao = row.get("SITUACAOFUNC") if "SITUACAOFUNC" in row else row.get("situacao")
        active = _is_active(situacao)
        local = _email_local(row.get("EMAILFUNC") if "EMAILFUNC" in row else row.get("email"))
        if local:
            _put_email(by_email, local, chapa, active)
            nd = _nodot(local)
            if nd and nd != local:
                _put_email(by_email_nodot, nd, chapa, active)
        nome = str(
            row.get("NOMEFUNC") if "NOMEFUNC" in row else row.get("nome") or ""
        ).strip()
        if nome:
            name_rows.append((nome, chapa, active))

    extra: Dict[str, str] = {}
    for k, v in (extra_emails or {}).items():
        login = (k or "").strip()
        local = _email_local(v)
        if login and local:
            extra[login.lower()] = local

    names: Dict[str, str] = {}
    for k, v in (extra_names or {}).items():
        login = (k or "").strip().lower()
        person = (v or "").strip()
        if login and person:
            names[login] = person

    out: Dict[str, str] = {}
    ambiguous: List[str] = []

    for login in logins:
        raw = (login or "").strip()
        if not raw:
            continue
        mat, amb = _resolve_key(raw.lower(), by_email, by_email_nodot, name_rows)
        if not mat:
            alt = extra.get(raw.lower())
            if alt and alt != raw.lower():
                mat, amb = _resolve_key(alt, by_email, by_email_nodot, name_rows)
        if not mat:
            person = names.get(raw.lower())
            if person:
                first, last = _person_first_last(person)
                if first and last:
                    chapa = _unique_name_chapa(first, last, name_rows)
                    if chapa:
                        mat, amb = chapa, False
                    else:
                        amb = _name_ambiguous(first, last, name_rows)
        if mat:
            out[raw] = mat
        elif amb:
            ambiguous.append(raw)

    return out, ambiguous


def fetch_matriculas_from_oracle(
    logins: List[str],
    extra_emails: Optional[Dict[str, str]] = None,
    extra_names: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Resolve Usuario AD → matrícula (CHAPAFUNC) em GLOBUS.FLP_FUNCIONARIOS.

    1) e-mail cujo local-part = login
    2) local-part e login sem pontos
    3) nome único a partir do login primeiro.ultimo
    4) e-mail AD (extra_emails)
    5) nome da pessoa no AD (extra_names), sem acento / partículas
    """
    wanted = sorted(
        {
            (u or "").strip()
            for u in logins
            if (u or "").strip() and _SAFE_LOGIN.match((u or "").strip())
        }
    )
    if not wanted:
        return {}

    conf_dir = _oracle_conf_dir()
    erp = conf_dir / "erp.dat"
    if not erp.is_file():
        logger.warning("Oracle erp.dat ausente em %s", conf_dir)
        return {}

    try:
        from DAL import DAL  # noqa: WPS433
    except Exception as exc:
        logger.warning("Import DAL para Oracle: %s", exc)
        return {}

    try:
        odal = DAL(
            app_name="SGC_ORACLE_MATRICULA",
            nome_arquivo_config="erp.dat",
            path=str(conf_dir),
        )
        df = odal.read(
            """
            SELECT CHAPAFUNC, NOMEFUNC, EMAILFUNC, SITUACAOFUNC
            FROM GLOBUS.FLP_FUNCIONARIOS
            WHERE CHAPAFUNC IS NOT NULL
            """
        )
    except Exception as exc:
        logger.warning("Consulta Oracle FLP_FUNCIONARIOS falhou: %s", exc)
        return {}

    if df is None or df.empty:
        logger.warning("Oracle FLP_FUNCIONARIOS retornou vazio")
        return {}

    funcionarios = [row.to_dict() for _, row in df.iterrows()]
    out, ambiguous = match_logins_to_chapas(
        funcionarios, wanted, extra_emails, extra_names
    )
    if ambiguous:
        logger.info(
            "Oracle matrícula ambígua (nome) para %s login(s): %s",
            len(ambiguous),
            ", ".join(ambiguous[:12]),
        )
    logger.info(
        "Oracle matrículas resolvidas: %s / %s (funcionarios=%s extra_emails=%s extra_names=%s)",
        len(out),
        len(wanted),
        len(funcionarios),
        len(extra_emails or {}),
        len(extra_names or {}),
    )
    return out
