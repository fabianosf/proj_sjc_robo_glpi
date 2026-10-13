# SincronizarFeedbackGLPI.py
# Importa chamados FECHADOS do GLPI (últimos 6 meses) para Tb_Ticket_Feedback_Temp

import os
import sys

from DbMigracao import ClDbMigracao
from trade import ClTrade
from FeedbackChamados import ClFeedbackChamados


def main():
    meses = int(os.getenv("ML_FEEDBACK_MESES", "6"))

    print("=" * 60)
    print("SINCRONIZAÇÃO DE FEEDBACK GLPI -> Tb_Ticket_Feedback_Temp")
    print("=" * 60)

    print("\n[0] Migração Fase 2...")
    if not ClDbMigracao().aplicar_migracao_ambiente():
        print("[AVISO] Migração incompleta — continuando mesmo assim.")

    try:
        print("\n[1] Conectando ao GLPI (conf/glpi.dat)...")
        trade = ClTrade()
        print(f"[OK] Conexão estabelecida: {trade.base_url}")

        print(f"\n[2] Sincronizando chamados fechados dos últimos {meses} meses...")
        feedback = ClFeedbackChamados(trade=trade)
        total = feedback.sincronizar_glpi(meses=meses)

        print(f"\n[RESULTADO]")
        print(f"  Chamados retornados pelo GLPI : {feedback.ultimo_total_glpi}")
        print(f"  Registros gravados/atualizados : {total}")
        print(f"  Com equipe identificada (Tb_Atrib): {feedback.ultimo_total_com_equipe}")
        print(f"  Registros aptos para treino ML  : {feedback.contar_registros_treino()}")
        print("\n" + "=" * 60)

        if total == 0 and feedback.ultimo_total_glpi == 0:
            sys.exit(1)
    except Exception as e:
        print(f"\n[ERRO] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
