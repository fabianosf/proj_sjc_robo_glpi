# RestaurarModeloML.py — rollback de versão do modelo ML (Fase 3)

import sys

from ModelVersionamento import ClModelVersionamento


def main():
    ver = ClModelVersionamento()
    versoes = ver.listar_versoes()

    if not versoes:
        print("Nenhuma versão arquivada. Treine um modelo primeiro.")
        sys.exit(1)

    print("Versões disponíveis:\n")
    for i, v in enumerate(versoes, 1):
        f1 = v.get("f1_macro")
        f1s = f"{f1:.3f}" if f1 is not None else "N/A"
        print(f"  [{i}] {v['arquivo']}  |  F1: {f1s}  |  {v.get('data', '')}")

    if len(sys.argv) > 1:
        escolha = sys.argv[1]
    else:
        escolha = input("\nNúmero ou nome do arquivo para restaurar (Enter=cancelar): ").strip()

    if not escolha:
        print("Cancelado.")
        return

    if escolha.isdigit():
        idx = int(escolha) - 1
        if idx < 0 or idx >= len(versoes):
            print("Índice inválido.")
            sys.exit(1)
        arquivo = versoes[idx]["arquivo"]
    else:
        arquivo = escolha

    if ver.restaurar(arquivo):
        print(f"Modelo restaurado: {arquivo}")
        print("Reinicie o main.py ou aguarde o recarregamento automático.")
    else:
        print("Falha ao restaurar.")
        sys.exit(1)


if __name__ == "__main__":
    main()
