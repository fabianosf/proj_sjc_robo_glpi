#!/usr/bin/env python3
"""
AVISO: o login do painel SGC usa Active Directory + allowlist (matrícula / equipe N3).
Senhas locais em Tb_Usuario_Painel NÃO são mais usadas no login.

Este script permanece apenas para manutenção excepcional do registro local
(auditoria/JWT id) — não libera acesso ao painel por si só.

Preferência operacional:
  - Liberar acesso: SGC_AUTH_ADMIN_MATRICULAS ou técnico ativo N3 em Tb_Atrib
  - Senha: a do Windows / Active Directory
  - Domínio: SGC_AD_DOMAIN em backend/.env
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
PYTHON = ROOT / "python"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(PYTHON))

try:
    from dotenv import load_dotenv

    load_dotenv(BACKEND / ".env", override=False)
    load_dotenv(ROOT / ".env", override=False)
except ImportError:
    pass


def main() -> int:
    print(
        "[AVISO] Auth do painel = Active Directory + allowlist (59817 / N3).\n"
        "        Senha local NÃO autentica mais. Use matrícula + senha Windows.\n"
        "        Configure SGC_AD_DOMAIN em backend\\.env\n",
        file=sys.stderr,
    )
    parser = argparse.ArgumentParser(
        description="(Obsoleto para login) Mantém registro local — auth real é AD"
    )
    parser.add_argument("--username", required=True, help="Matrícula (único)")
    parser.add_argument(
        "--password",
        default=None,
        help="Ignorado no login AD; se informado, só grava placeholder local",
    )
    parser.add_argument("--nome", default=None, help="Nome de exibição")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignorado (compatibilidade).",
    )
    args = parser.parse_args()

    username = args.username.strip()
    if not username:
        print("[ERRO] Username vazio.", file=sys.stderr)
        return 1

    from app.auth.config import AD_PASSWORD_PLACEHOLDER
    from app.auth.service import create_user, ensure_auth_tables, get_user_by_username
    from app.bootstrap import ensure_legacy_path
    from app.deps import get_dal

    ensure_legacy_path()
    get_dal.cache_clear()
    dal = get_dal()

    if not ensure_auth_tables(dal):
        print(
            "[ERRO] Tabelas ausentes. Execute no MariaDB:\n"
            "  sql/criar_Tb_Auth_Painel.sql",
            file=sys.stderr,
        )
        return 1

    existing = get_user_by_username(dal, username)
    if existing:
        print(
            f"[ERRO] Usuário '{username}' já existe (id={existing.get('id_usuario')}). "
            "Não é permitido sobrescrever por este script.",
            file=sys.stderr,
        )
        return 1

    try:
        user_id = create_user(
            dal,
            username=username,
            password_hash=AD_PASSWORD_PLACEHOLDER,
            perfil="ADMIN",
            nome=args.nome,
        )
    except Exception as exc:
        print(f"[ERRO] Falha ao criar registro local: {exc}", file=sys.stderr)
        return 1

    print(
        f"[OK] Registro local criado: username={username} id={user_id} perfil=ADMIN\n"
        "     Login do painel exige: allowlist (59817 ou N3 ativo) + senha AD."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
