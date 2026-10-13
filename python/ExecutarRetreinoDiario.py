# ExecutarRetreinoDiario.py — execução única de re-treino (alternativa ao AgendadorSGC / cron Linux)

import sys

from TarefasML import executar_retreino_diario, garantir_tabelas_fase3


def main():
    print("=" * 60)
    print("RE-TREINO DIÁRIO — SGC")
    print("=" * 60)

    if not garantir_tabelas_fase3():
        print("[AVISO] Tabelas Fase 3 não verificadas.")

    ok = executar_retreino_diario()
    if ok:
        print("\nConcluído. O main.py recarrega Modelo/ModeloML.pkl automaticamente.")
        print("=" * 60)
    else:
        print("\nTreino não implantou novo modelo.")
        sys.exit(1)


if __name__ == "__main__":
    main()
