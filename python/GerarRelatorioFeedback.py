# GerarRelatorioFeedback.py — relatório de cobertura do feedback ML

from RelatorioFeedback import ClRelatorioFeedback


def main():
    rel = ClRelatorioFeedback()
    caminho = rel.gerar_txt()
    print(f"Relatório gerado: {caminho}")


if __name__ == "__main__":
    main()
