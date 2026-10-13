#!/usr/bin/env python3
"""
Lista técnicos N3 ativos com Matricula inválida (vazia / 00000)
e gera SQL de UPDATE para preenchimento manual.

Uso (raiz do projeto):
  sgc_python.bat python\\ListarMatriculasN3Pendentes.py
  sgc_python.bat python\\ListarMatriculasN3Pendentes.py --sql-out relatorios\\update_matriculas_n3.sql

Não altera o banco — só reporta. Preencha as matrículas reais antes do login no painel.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from DAL import ClDal  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Matrículas N3 pendentes para o painel")
    parser.add_argument(
        "--sql-out",
        default="",
        help="Caminho opcional para gravar template UPDATE",
    )
    parser.add_argument(
        "--equipe",
        default="N3",
        help="Equipe allowlist (default N3)",
    )
    args = parser.parse_args()

    dal = ClDal("sgc.dat")
    eq = args.equipe.strip().upper()
    df = dal.read(
        """
        SELECT DISTINCT
            TRIM(Usuario) AS Usuario,
            TRIM(COALESCE(Matricula, '')) AS Matricula,
            Sit,
            TRIM(Equipe) AS Equipe
        FROM Tb_Atrib
        WHERE UPPER(TRIM(Equipe)) = %s
          AND (Sit = 1 OR Sit = '1')
        ORDER BY Usuario
        """,
        (eq,),
    )

    if df is None or df.empty:
        print(f"[OK] Nenhum técnico ativo na equipe {eq}.")
        return 0

    pendentes = []
    ok = []
    for _, row in df.iterrows():
        mat = str(row["Matricula"] or "").strip()
        user = str(row["Usuario"] or "").strip()
        if not mat or mat in ("0", "00000"):
            pendentes.append((user, mat))
        else:
            ok.append((user, mat))

    print(f"Equipe {eq} ativos: {len(df)}")
    print(f"  Com Matricula válida: {len(ok)}")
    print(f"  Pendentes (bloqueiam login no painel): {len(pendentes)}")
    print()
    if pendentes:
        print("PENDENTES (Usuario → Matricula atual):")
        for user, mat in pendentes:
            print(f"  - {user!r:30}  Matricula={mat!r}")
        print()
        print("Ação: atualize Tb_Atrib.Matricula com a matrícula AD real, ex.:")
        print(
            "  UPDATE Tb_Atrib SET Matricula = '12345' "
            "WHERE UPPER(TRIM(Usuario)) = 'NOME.SOBRENOME' "
            f"AND UPPER(TRIM(Equipe)) = '{eq}';"
        )

    lines = [
        f"-- Gerado em {datetime.now().isoformat(timespec='seconds')}",
        f"-- Template: preencha MATRICULA_REAL e descomente as linhas",
        f"-- Equipe {eq} — apenas Sit=1 com Matricula inválida",
        "",
    ]
    for user, _mat in pendentes:
        safe = user.replace("'", "''")
        lines.append(
            f"-- UPDATE Tb_Atrib SET Matricula = 'MATRICULA_REAL' "
            f"WHERE UPPER(TRIM(Usuario)) = '{safe.upper()}' "
            f"AND UPPER(TRIM(Equipe)) = '{eq}' AND (Sit = 1 OR Sit = '1');"
        )

    sql_text = "\n".join(lines) + "\n"
    out = (args.sql_out or "").strip()
    if out:
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(sql_text, encoding="utf-8")
        print(f"\n[OK] Template SQL escrito em: {path}")
    else:
        print("\n--- Template SQL (stdout) ---")
        print(sql_text)

    return 0 if not pendentes else 2


if __name__ == "__main__":
    raise SystemExit(main())
