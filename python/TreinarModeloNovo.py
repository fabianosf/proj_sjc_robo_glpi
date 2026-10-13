import os

from DbMigracao import ClDbMigracao
from trade import ClTrade
from ML import ClML


def main():
    meses = int(os.getenv("ML_FEEDBACK_MESES", "6"))
    forcar = os.getenv("ML_FORCAR_IMPLANTACAO", "").lower() in ("1", "true", "yes")

    try:
        print("Aplicando migração Fase 2...")
        if not ClDbMigracao().aplicar_migracao_ambiente():
            print("AVISO: migração incompleta.")

        print("Conectando ao GLPI (conf/glpi.dat)...")
        trade = ClTrade()

        clml = ClML()
        print(f"Pipeline: GLPI fechados ({meses} meses) -> Tb_Atrib (equipe) -> treino ML")

        if clml.geracao_automatica_modelo(
            trade=trade,
            meses_feedback=meses,
            sincronizar_feedback=True,
            forcar_implantacao=forcar,
        ):
            print("Modelo treinado e implantado com sucesso!")
            print(f"F1-macro (hold-out): {clml.ultimo_f1_macro if clml.ultimo_f1_macro is not None else 'N/A'}")
            print(f"Chamados fechados importados nesta execução: {clml.ultimos_feedback_sync}")
            print(f"Registros usados no treino: {clml.ultimos_feedback_treino}")
        else:
            print("Treinamento concluído sem implantar novo modelo.")
            print("Verifique se há chamados fechados no GLPI com técnico cadastrado em Tb_Atrib.")
    except Exception as e:
        print(f"Um erro ocorreu durante o processo: {e}")


if __name__ == "__main__":
    main()
