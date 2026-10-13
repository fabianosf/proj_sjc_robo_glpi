# DetectarCorrecoesGLPI.py — divergências de equipe SGC vs fechamento GLPI

from CorrecaoFeedback import ClCorrecaoFeedback
from DbMigracao import ClDbMigracao


def main():
    print("=" * 60)
    print("DETECÇÃO DE CORREÇÕES — SGC vs FECHAMENTO GLPI")
    print("=" * 60)

    ClDbMigracao().aplicar_fase3()
    corr = ClCorrecaoFeedback()
    total = corr.detectar_e_gravar()

    print(f"\nDivergências encontradas : {corr.ultimo_total_detectado}")
    print(f"Registros gravados/atual.: {total}")
    print(f"Total na base            : {corr.contar_correcoes()}")
    print("\nDivergências de equipe (SGC ≠ fechamento) entram no treino ML com peso maior.")
    print("Trocas de técnico dentro da mesma equipe não geram correção.")
    print("=" * 60)


if __name__ == "__main__":
    main()
