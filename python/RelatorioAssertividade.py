# RelatorioAssertividade.py — relatório PDF diário de assertividade do SGC

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from AssertividadeMetricas import ClAssertividadeMetricas
from DAL import DAL
from logger import ClLog
from paths import RELATORIOS_DIR

RELATORIO_DIR = RELATORIOS_DIR
DIAS_ATRASO_PADRAO = 2


class ClRelatorioAssertividade:
    logger = ClLog()

    def __init__(self, dal: DAL = None, dias_atraso_atribuicao: int = DIAS_ATRASO_PADRAO):
        self.dal = dal or DAL(app_name="Relatorio", nome_arquivo_config="sgc.dat")
        self.dias_atraso_atribuicao = dias_atraso_atribuicao
        self.metricas = ClAssertividadeMetricas(dal=self.dal)
        self._ultimo_arquivo = ""

    @property
    def ultimo_arquivo(self):
        return self._ultimo_arquivo

    @staticmethod
    def _texto_resumo_executivo(resumo) -> str:
        """Parágrafo inicial em linguagem direta para o gestor."""
        if resumo.total_comparados == 0:
            pendentes = resumo.total_pendentes_fechamento
            if pendentes > 0:
                return (
                    f"Em <b>{resumo.data_referencia}</b>, o SGC atribuiu chamados, mas "
                    f"<b>nenhum deles já estava fechado no GLPI</b> na data deste relatório. "
                    f"Há <b>{pendentes}</b> chamado(s) daquela data aguardando fechamento — "
                    "a assertividade será calculada quando forem encerrados."
                )
            return (
                f"Não foram encontrados chamados atribuídos pelo SGC em "
                f"<b>{resumo.data_referencia}</b> que já tenham sido fechados no GLPI."
            )

        taxa = resumo.taxa_assertividade
        comparados = resumo.total_comparados
        acertos = resumo.total_acertos
        erros = resumo.total_erros

        if taxa >= 80:
            avaliacao = "O desempenho está <b>bom</b>."
        elif taxa >= 60:
            avaliacao = "O desempenho está <b>razoável</b>; vale revisar os erros listados abaixo."
        else:
            avaliacao = "O desempenho está <b>abaixo do esperado</b>; analise as divergências com atenção."

        texto = (
            f"Referência: chamados que o SGC classificou em <b>{resumo.data_referencia}</b> "
            f"e que <b>já foram fechados</b> no GLPI. "
            f"Foram analisados <b>{comparados}</b> chamado(s): "
            f"<b>{acertos}</b> tiveram a equipe correta e "
            f"<b>{erros}</b> foram fechados por outra equipe "
            f"(<b>{taxa:.1f}%</b> de assertividade). {avaliacao}"
        )
        if resumo.total_reatribuicoes_mesma_equipe > 0:
            texto += (
                f" <b>{resumo.total_reatribuicoes_mesma_equipe}</b> chamado(s) foram fechados "
                "por outro técnico da <b>mesma equipe</b> — isso <b>não</b> conta como erro."
            )
        if resumo.total_pendentes_fechamento > 0:
            texto += (
                f" Além disso, <b>{resumo.total_pendentes_fechamento}</b> chamado(s) "
                "da mesma data ainda estão abertos e não entram nesta conta."
            )
        return texto

    def gerar_relatorio_pdf(self) -> str:
        RELATORIO_DIR.mkdir(parents=True, exist_ok=True)
        data_str = datetime.now().strftime("%Y%m%d")
        caminho = RELATORIO_DIR / f"Assertividade_SGC_{data_str}.pdf"

        resumo = self.metricas.calcular(dias_atraso_atribuicao=self.dias_atraso_atribuicao)
        doc = SimpleDocTemplate(
            str(caminho),
            pagesize=A4,
            rightMargin=1.5 * cm,
            leftMargin=1.5 * cm,
            topMargin=1.5 * cm,
            bottomMargin=1.5 * cm,
        )

        styles = getSampleStyleSheet()
        titulo_style = ParagraphStyle(
            "TituloSGC",
            parent=styles["Heading1"],
            fontSize=16,
            spaceAfter=8,
        )
        subtitulo_style = ParagraphStyle(
            "SubtituloSGC",
            parent=styles["Heading2"],
            fontSize=12,
            spaceBefore=12,
            spaceAfter=6,
            textColor=colors.HexColor("#1a365d"),
        )
        corpo_style = ParagraphStyle(
            "CorpoSGC",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            spaceAfter=6,
        )
        destaque_style = ParagraphStyle(
            "DestaqueSGC",
            parent=corpo_style,
            backColor=colors.HexColor("#ebf8ff"),
            borderPadding=8,
            spaceBefore=6,
            spaceAfter=10,
        )
        nota_style = ParagraphStyle(
            "NotaSGC",
            parent=corpo_style,
            fontSize=9,
            textColor=colors.HexColor("#4a5568"),
            leftIndent=12,
        )

        elementos = []

        elementos.append(Paragraph("Relatório de assertividade do SGC", titulo_style))
        elementos.append(
            Paragraph(
                f"Emitido em {datetime.now().strftime('%d/%m/%Y às %H:%M')}",
                nota_style,
            )
        )
        elementos.append(Spacer(1, 0.3 * cm))

        elementos.append(Paragraph(self._texto_resumo_executivo(resumo), destaque_style))

        elementos.append(
            Paragraph(
                "<b>O que este relatório mede:</b> comparamos a <b>equipe classificada pelo SGC</b> "
                "(campo Equipe registrado na atribuição) com a <b>equipe do técnico que encerrou</b> "
                "o chamado no GLPI. Se forem iguais, é acerto. Se o chamado foi repassado para "
                "outro membro da <b>mesma equipe</b> antes do fechamento, <b>não</b> é considerado erro. "
                "Só conta erro quando o fechamento foi feito por técnico de <b>outra equipe</b>.",
                corpo_style,
            )
        )
        elementos.append(
            Paragraph(
                f"<b>Data analisada:</b> atribuições feitas pelo SGC em "
                f"<b>{resumo.data_referencia}</b> "
                f"({self.dias_atraso_atribuicao} dias antes da geração deste relatório, "
                "para dar tempo de o chamado ser fechado).",
                nota_style,
            )
        )
        elementos.append(Spacer(1, 0.3 * cm))

        elementos.append(Paragraph("Números do dia analisado", subtitulo_style))
        tabela_resumo = [
            ["O que significa", "Quantidade"],
            ["Chamados comparados (atribuídos na data e já fechados)", str(resumo.total_comparados)],
            ["Atribuições corretas (equipe SGC = equipe no fechamento)", str(resumo.total_acertos)],
            ["Atribuições incorretas (fechamento em outra equipe)", str(resumo.total_erros)],
            ["Reatribuições na mesma equipe (não são erro)", str(resumo.total_reatribuicoes_mesma_equipe)],
            ["Percentual de acerto (assertividade)", f"{resumo.taxa_assertividade:.1f}%"],
            ["Chamados da data que ainda não foram fechados no GLPI", str(resumo.total_pendentes_fechamento)],
        ]
        elementos.append(self._criar_tabela(tabela_resumo, [10 * cm, 5 * cm]))
        elementos.append(Spacer(1, 0.4 * cm))

        elementos.append(Paragraph("Desempenho por equipe atribuída pelo SGC", subtitulo_style))
        elementos.append(
            Paragraph(
                "Mostra, para cada equipe que o SGC escolheu, quantos chamados acertou e quantos errou.",
                nota_style,
            )
        )
        if resumo.por_equipe.empty:
            elementos.append(
                Paragraph(
                    "Não há dados de equipe para a data analisada.",
                    corpo_style,
                )
            )
        else:
            dados_eq = [["Equipe atribuída pelo SGC", "Total de chamados", "Acertos", "Taxa de acerto"]]
            for _, row in resumo.por_equipe.iterrows():
                dados_eq.append([
                    str(row["equipe_sgc"]),
                    str(int(row["total"])),
                    str(int(row["acertos"])),
                    f"{row['taxa_pct']:.1f}%",
                ])
            elementos.append(self._criar_tabela(dados_eq, [4.5 * cm, 3.5 * cm, 3 * cm, 4 * cm]))

        elementos.append(Spacer(1, 0.4 * cm))
        elementos.append(Paragraph("Erros mais frequentes", subtitulo_style))
        elementos.append(
            Paragraph(
                "Combinações em que o SGC classificou uma equipe, mas o chamado foi fechado "
                "por técnico de outra equipe.",
                nota_style,
            )
        )
        if resumo.principais_erros.empty:
            elementos.append(
                Paragraph(
                    "Nenhum erro registrado — todas as atribuições coincidiram com o fechamento.",
                    corpo_style,
                )
            )
        else:
            dados_erro = [["Equipe que o SGC escolheu", "Equipe no fechamento", "Quantidade de vezes"]]
            for _, row in resumo.principais_erros.iterrows():
                dados_erro.append([
                    str(row["equipe_sgc"]),
                    str(row["equipe_fechamento"]),
                    str(int(row["quantidade"])),
                ])
            elementos.append(self._criar_tabela(dados_erro, [5 * cm, 5 * cm, 4 * cm]))

        elementos.append(Spacer(1, 0.4 * cm))
        elementos.append(Paragraph("Base de aprendizado do modelo (informação complementar)", subtitulo_style))
        cov = resumo.cobertura_feedback
        pct_equipe = (
            round(100.0 * cov.get("com_equipe", 0) / cov.get("total_feedback", 1), 1)
            if cov.get("total_feedback", 0) > 0
            else 0.0
        )
        elementos.append(
            Paragraph(
                "Estes números referem-se ao histórico de chamados <b>fechados</b> usado para "
                "treinar o modelo de machine learning — não à data analisada acima.",
                nota_style,
            )
        )
        tabela_cov = [
            ["Informação", "Valor"],
            ["Total de chamados fechados armazenados", str(cov.get("total_feedback", 0))],
            ["Com equipe identificada pelo cadastro de técnicos", str(cov.get("com_equipe", 0))],
            ["Percentual com equipe identificada", f"{pct_equipe:.1f}%"],
            ["Quantidade de equipes distintas no histórico", str(cov.get("equipes_distintas", 0))],
        ]
        elementos.append(self._criar_tabela(tabela_cov, [10 * cm, 5 * cm]))

        if not resumo.detalhes.empty:
            erros_det = resumo.detalhes[~resumo.detalhes["acerto"]].head(15)
            if not erros_det.empty:
                elementos.append(Spacer(1, 0.4 * cm))
                elementos.append(Paragraph("Exemplos de chamados com atribuição incorreta", subtitulo_style))
                elementos.append(
                    Paragraph(
                        "Amostra dos últimos casos em que a equipe do SGC não bateu com a equipe no fechamento.",
                        nota_style,
                    )
                )
                dados_det = [["Nº chamado", "Título (resumo)", "Equipe SGC", "Equipe no fechamento", "Técnico que fechou"]]
                for _, row in erros_det.iterrows():
                    titulo = str(row["titulo"])[:45]
                    dados_det.append([
                        str(row["id_glpi"]),
                        titulo,
                        str(row["equipe_sgc"]),
                        str(row["equipe_fechamento"]),
                        str(row["tecnico_fechamento"]),
                    ])
                elementos.append(self._criar_tabela(
                    dados_det, [2 * cm, 5.5 * cm, 2 * cm, 2.5 * cm, 3 * cm]
                ))

        doc.build(elementos)
        self._ultimo_arquivo = str(caminho)
        self.logger.registrarActionLog(
            "RELATORIO",
            "ATIVIDADE",
            f"PDF ASSERTIVIDADE GERADO: {caminho} | TAXA: {resumo.taxa_assertividade:.1f}%",
        )
        return str(caminho)

    @staticmethod
    def _criar_tabela(dados, larguras):
        tabela = Table(dados, colWidths=larguras, repeatRows=1)
        tabela.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c5282")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7fafc")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ])
        )
        return tabela
