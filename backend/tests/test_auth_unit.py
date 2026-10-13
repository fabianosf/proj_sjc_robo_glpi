"""Testes unitários de allowlist, rate limit e revogação JWT (sem AD real)."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "python"))

os.environ.setdefault("SGC_JWT_SECRET", "x" * 48)
os.environ.setdefault("SGC_AUTH_ADMIN_MATRICULAS", "59817")
os.environ.setdefault("SGC_AUTH_ADMIN_EQUIPES", "N3")


def test_normalize_and_admin_allowlist():
    from app.auth.service import _normalize_matricula, is_allowed

    assert _normalize_matricula("059817") == "59817"
    dal = MagicMock()
    # admin list — não consulta DB
    assert is_allowed(dal, "59817") is True
    assert is_allowed(dal, "admin") is False


def test_n3_matricula_query():
    from app.auth.service import is_allowed
    from app.db_meta import table_exists

    # força caminho Tb_Atrib via mock de table_exists + safe_read
    import app.auth.service as svc

    dal = MagicMock()
    original_te = svc.table_exists
    original_sr = svc.safe_read

    def te(_dal, name):
        return name == "Tb_Atrib"

    def sr(_dal, sql, params=None):
        mat = params[1] if params and len(params) > 1 else ""
        if mat == "12345":
            return pd.DataFrame([{"ok": 1}])
        return pd.DataFrame()

    svc.table_exists = te
    svc.safe_read = sr
    try:
        assert is_allowed(dal, "12345") is True
        assert is_allowed(dal, "99999") is False
        assert is_allowed(dal, "00000") is False
    finally:
        svc.table_exists = original_te
        svc.safe_read = original_sr


def test_rate_limit():
    from app.auth.rate_limit import LoginRateLimiter

    lim = LoginRateLimiter(max_attempts=3, window_seconds=60)
    assert lim.allow("ip1")
    assert lim.allow("ip1")
    assert lim.allow("ip1")
    assert lim.allow("ip1") is False
    assert lim.allow("ip2") is True


def test_jwt_revoke():
    from app.auth.security import create_access_token, decode_access_token
    from app.auth.token_revoke import revoke_jti
    import jwt
    from app.auth.config import get_jwt_secret, get_jwt_algorithm

    token = create_access_token(subject="59817", user_id=1, perfil="ADMIN")
    payload = decode_access_token(token)
    assert payload["sub"] == "59817"
    jti = payload["jti"]
    revoke_jti(jti, int(payload["exp"]))
    try:
        decode_access_token(token)
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_chamado_existe_fail_closed():
    sys.path.insert(0, str(ROOT / "python"))
    # importa só a lógica via mock mínimo
    from MetodosGenericos import ClMetodosGenericos

    class Fake:
        def read(self, *a, **k):
            raise RuntimeError("db down")

    met = object.__new__(ClMetodosGenericos)
    met.dal_sgc = Fake()
    assert met.chamadoExiste(1) is True


def test_painel_perfil_admin_vs_consulta():
    from app.auth.service import upsert_painel_user

    dal = MagicMock()
    dal.update.return_value = True
    existing = {
        "id_usuario": 9,
        "username": "ryan.braz",
        "perfil": "ADMIN",
        "ativo": 1,
        "nome": "ryan.braz",
    }
    rows = [existing, {**existing, "perfil": "CONSULTA"}]
    from app.auth import service as svc

    original = svc.get_user_by_username
    svc.get_user_by_username = MagicMock(side_effect=rows)
    try:
        out = upsert_painel_user(
            dal, username="ryan.braz", nome="ryan.braz", perfil="CONSULTA"
        )
        assert dal.update.called
        sql = dal.update.call_args[0][0]
        assert "perfil = %s" in sql
        assert dal.update.call_args[0][1][0] == "CONSULTA"
        assert out["perfil"] == "CONSULTA"
    finally:
        svc.get_user_by_username = original


if __name__ == "__main__":
    test_normalize_and_admin_allowlist()
    test_n3_matricula_query()
    test_rate_limit()
    test_jwt_revoke()
    test_chamado_existe_fail_closed()
    test_painel_perfil_admin_vs_consulta()
    print("ALL_UNIT_OK")
