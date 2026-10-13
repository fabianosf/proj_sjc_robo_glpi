# CriarTabelasFase3.py — cria SOMENTE Tb_ML_Log e Tb_Correcao_Feedback na base principal

import sys

from DbMigracao import ClDbMigracao
from DAL import DAL


def main():
    print("=" * 60)
    print("DEPLOY FASE 3 — APENAS TABELAS NOVAS")
    print("Tb_ML_Log + Tb_Correcao_Feedback")
    print("(Não altera Tb_Ticket_new, Tb_Ticket_Feedback_Temp nem demais tabelas)")
    print("=" * 60)

    dal = DAL(app_name="DeployFase3", nome_arquivo_config="sgc.dat")
    mig = ClDbMigracao(dal=dal)

    if not mig.aplicar_fase3():
        print("\n[ERRO] Falha ao criar tabelas. Verifique conf/sgc.dat e permissões.")
        sys.exit(1)

    for tabela in ("Tb_ML_Log", "Tb_Correcao_Feedback"):
        df = dal.read("SHOW TABLES LIKE %s", (tabela,))
        if df is not None and not df.empty:
            print(f"  [OK] {tabela}")
        else:
            print(f"  [ERRO] {tabela} não encontrada após deploy")
            sys.exit(1)

    print("\nDeploy concluído na base configurada em conf/sgc.dat")
    print("=" * 60)


if __name__ == "__main__":
    main()
