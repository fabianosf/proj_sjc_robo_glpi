# GerarRelatorioAssertividade.py — geração manual do PDF de assertividade

import os

from DbMigracao import ClDbMigracao
from RelatorioAssertividade import ClRelatorioAssertividade


def main():
    dias_atraso = int(os.getenv("RELATORIO_DIAS_ATRASO", "2"))
    ClDbMigracao().aplicar_fase3()
    rel = ClRelatorioAssertividade(dias_atraso_atribuicao=dias_atraso)
    caminho = rel.gerar_relatorio_pdf()
    print(f"Relatório gerado: {caminho}")
    print(f"Data de referência: atribuições de {dias_atraso} dia(s) atrás (já fechadas no GLPI)")


if __name__ == "__main__":
    main()
