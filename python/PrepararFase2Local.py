# PrepararFase2Local.py — preparação local da Fase 2 (migração, sync GLPI, treino ML)

import argparse
import os
import sys

from DbMigracao import ClDbMigracao
from ML import ClML, MODEL_VERSION, MODELO_ATIVO
from trade import ClTrade


def passo_migracao() -> bool:
    print("\n[1/3] Migração Fase 2 (banco local)...")
    mig = ClDbMigracao()
    ok = mig.aplicar_migracoes()
    if ok:
        print("  OK — schema Fase 2/3 aplicado.")
        if mig.ultimo_backfill_equipe:
            print(f"  Backfill Equipe: {mig.ultimo_backfill_equipe} registro(s) atualizado(s).")
    else:
        print("  ERRO — migração falhou. Verifique conf/sgc.dat e logs.")
    return ok


def passo_sync(meses: int) -> bool:
    print(f"\n[2/3] Sincronização GLPI (últimos {meses} meses)...")
    from FeedbackChamados import ClFeedbackChamados

    try:
        trade = ClTrade()
        feedback = ClFeedbackChamados(trade=trade)
        total = feedback.sincronizar_glpi(meses=meses)
        print(f"  GLPI retornou : {feedback.ultimo_total_glpi}")
        print(f"  Gravados      : {total}")
        print(f"  Aptos treino  : {feedback.contar_registros_treino()}")
        return total > 0 or feedback.ultimo_total_glpi > 0
    except Exception as e:
        print(f"  ERRO — sync GLPI falhou: {e}")
        return False


def passo_treino(meses: int, forcar: bool) -> bool:
    print("\n[3/3] Treinamento ML (modelo v3)...")
    try:
        trade = ClTrade()
        clml = ClML()
        ok = clml.geracao_automatica_modelo(
            trade=trade,
            meses_feedback=meses,
            sincronizar_feedback=False,
            forcar_implantacao=forcar,
        )
        if ok:
            modelo = clml.le_modelo_ml()
            versao = modelo[3].get("version") if modelo[3] else None
            f1 = clml.ultimo_f1_macro
            print(f"  OK — modelo implantado (v{versao}, F1-macro: {f1}).")
            print(f"  Arquivo: {MODELO_ATIVO}")
            return versao == MODEL_VERSION
        print("  AVISO — treino não implantou modelo (dados insuficientes ou F1 abaixo do mínimo).")
        return False
    except Exception as e:
        print(f"  ERRO — treino falhou: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Prepara ambiente local para Fase 2 do SGC")
    parser.add_argument(
        "--apenas-migracao",
        action="store_true",
        help="Executa somente migração de banco (sem GLPI)",
    )
    parser.add_argument(
        "--sem-treino",
        action="store_true",
        help="Executa migração e sync, mas não treina o modelo",
    )
    parser.add_argument(
        "--forcar-treino",
        action="store_true",
        help="Implanta modelo mesmo sem melhoria de F1 (primeiro deploy local)",
    )
    args = parser.parse_args()
    meses = int(os.getenv("ML_FEEDBACK_MESES", "6"))

    print("=" * 60)
    print("PREPARAÇÃO LOCAL — FASE 2 SGC")
    print("=" * 60)

    if not passo_migracao():
        sys.exit(1)

    if args.apenas_migracao:
        print("\nConcluído (somente migração).")
        return

    if not passo_sync(meses):
        print("\nAVISO: sync GLPI sem dados — treino pode falhar se a base local estiver vazia.")

    if args.sem_treino:
        print("\nConcluído (migração + sync, sem treino).")
        return

    forcar = args.forcar_treino or os.getenv("ML_FORCAR_IMPLANTACAO", "").lower() in ("1", "true", "yes")
    if not passo_treino(meses, forcar):
        print("\nPróximo passo manual: sgc_python.bat python\\TreinarModeloNovo.py")
        sys.exit(1)

    print("\nFase 2 preparada. Inicie o monitoramento com:")
    print("  python main.py")
    print("  (alternativa: run.bat / ./run.sh)")
    print("=" * 60)


if __name__ == "__main__":
    main()
