# RelatorioOpsPdf.py — PDF executivo do relatório operacional (tela Relatórios)

from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing

from logger import ClLog
from paths import RELATORIOS_DIR

AZUL = colors.HexColor("#1a365d")
AZUL_FAIXA = colors.HexColor("#2c5282")
VERDE = "#276749"
VERMELHO = "#c53030"
CINZA_LINHA = colors.HexColor("#edf2f7")
CINZA_TEXTO = colors.HexColor("#4a5568")


def _br_date(iso: str) -> str:
    try:
        y, m, d = (iso or "").split("-")
        return f"{d}/{m}/{y}"
    except ValueError:
        return iso or "—"


def _fmt_int(n: Optional[int]) -> str:
    if n is None:
        return "—"
    return f"{int(n):,}".replace(",", ".")


def _fmt_hours(h: Optional[float]) -> str:
    if h is None:
        return "—"
    return f"{float(h):.2f} h"


def _indice(fechados: int, atribuidos: int) -> str:
    if atribuidos <= 0:
        return "—"
    return f"{100.0 * fechados / atribuidos:.1f}%"


def _pct(parte: int, total: int) -> str:
    if total <= 0:
        return "—"
    return f"{100.0 * parte / total:.1f}%"


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    return getattr(obj, name, default)


def _delta_int_plain(cur: int, prev: int) -> str:
    d = int(cur) - int(prev)
    if d > 0:
        return f"+{_fmt_int(d)}"
    if d < 0:
        return f"-{_fmt_int(abs(d))}"
    return "0"


def _delta_hours_plain(cur: Optional[float], prev: Optional[float]) -> str:
    if cur is None or prev is None:
        return "—"
    d = round(float(cur) - float(prev), 2)
    if d > 0:
        return f"+{d:.2f} h"
    if d < 0:
        return f"{d:.2f} h"
    return "0.00 h"


class ClRelatorioOpsPdf:
    """Duas a três páginas A4: resumo executivo, KPIs, comparação, ranking e demanda."""

    logger = ClLog()

    def gerar(self, atual: Any, anterior: Any = None) -> Path:
        RELATORIOS_DIR.mkdir(parents=True, exist_ok=True)
        start = _attr(atual, "period_start") or "periodo"
        end = _attr(atual, "period_end") or "periodo"
        caminho = RELATORIOS_DIR / f"Ops_SGC_{start}_{end}.pdf"

        styles = getSampleStyleSheet()
        titulo_branco = ParagraphStyle(
            "OpsTituloBranco",
            parent=styles["Heading1"],
            fontSize=13,
            textColor=colors.whitesmoke,
            leading=16,
            spaceAfter=0,
        )
        meta_branco = ParagraphStyle(
            "OpsMetaBranco",
            parent=styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#e2e8f0"),
            leading=11,
            alignment=TA_RIGHT,
            spaceAfter=0,
        )
        subtitulo_style = ParagraphStyle(
            "OpsSub",
            parent=styles["Heading2"],
            fontSize=10,
            textColor=AZUL_FAIXA,
            spaceBefore=8,
            spaceAfter=4,
        )
        corpo_style = ParagraphStyle(
            "OpsCorpo",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            spaceAfter=3,
        )
        nota_style = ParagraphStyle(
            "OpsNota",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=CINZA_TEXTO,
            spaceAfter=4,
        )
        delta_style = ParagraphStyle(
            "OpsDelta",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            alignment=TA_RIGHT,
        )

        totais = _attr(atual, "totals")
        atrib = int(_attr(totais, "atribuidos", 0) or 0)
        fech = int(_attr(totais, "fechados", 0) or 0)
        tempo = _attr(totais, "tempo_medio_horas")
        backlog = int(_attr(totais, "backlog_ativo", 0) or 0)

        cmp_ = _attr(atual, "comparacao") or anterior
        if cmp_ is not None and _attr(cmp_, "totals") is not None:
            atrib_ant = int(_attr(_attr(cmp_, "totals"), "atribuidos", 0) or 0)
            fech_ant = int(_attr(_attr(cmp_, "totals"), "fechados", 0) or 0)
            tempo_ant = _attr(_attr(cmp_, "totals"), "tempo_medio_horas")
            prev_label = _attr(cmp_, "label") or (
                f"{_attr(cmp_, 'period_start')} a {_attr(cmp_, 'period_end')}"
            )
        elif cmp_ is not None:
            atrib_ant = int(_attr(cmp_, "atribuidos", 0) or 0)
            fech_ant = int(_attr(cmp_, "fechados", 0) or 0)
            tempo_ant = _attr(cmp_, "tempo_medio_horas")
            prev_label = _attr(cmp_, "label") or (
                f"{_br_date(str(_attr(cmp_, 'period_start') or ''))} a "
                f"{_br_date(str(_attr(cmp_, 'period_end') or ''))}"
            )
        else:
            atrib_ant = 0
            fech_ant = 0
            tempo_ant = None
            prev_label = "—"

        equipes = _attr(atual, "focus_teams") or []
        equipes_txt = ", ".join(str(e) for e in equipes) if equipes else "padrão"
        tecnico = _attr(atual, "filtro_tecnico") or "Todos"
        label = _attr(atual, "label") or f"{start} a {end}"
        gerado = datetime.now().strftime("%d/%m/%Y %H:%M")

        faixa = Table(
            [
                [
                    Paragraph("SGC — Relatório operacional", titulo_branco),
                    Paragraph(
                        f"{escape(str(label))}<br/>Gerado em {gerado}",
                        meta_branco,
                    ),
                ]
            ],
            colWidths=[11.2 * cm, 5.3 * cm],
        )
        faixa.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), AZUL),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )

        elementos: List[Any] = [
            faixa,
            Spacer(1, 0.25 * cm),
            Paragraph(
                f"<b>Período:</b> {_br_date(str(start))} a {_br_date(str(end))} "
                f"· <b>Equipes:</b> {escape(equipes_txt)} "
                f"· <b>Técnico:</b> {escape(str(tecnico))}",
                nota_style,
            ),
            Paragraph("Resumo", subtitulo_style),
            Paragraph(
                self._texto_executivo(
                    atrib=atrib,
                    fech=fech,
                    tempo=tempo,
                    backlog=backlog,
                    atrib_ant=atrib_ant,
                    fech_ant=fech_ant,
                    tempo_ant=tempo_ant,
                    prev_label=str(prev_label),
                    atual=atual,
                ),
                corpo_style,
            ),
            Paragraph("Indicadores do período", subtitulo_style),
            self._criar_tabela(
                [
                    ["Atribuídos (SGC)", "Fechados (GLPI)", "Tempo médio", "Backlog agora"],
                    [
                        _fmt_int(atrib),
                        _fmt_int(fech),
                        _fmt_hours(tempo),
                        _fmt_int(backlog),
                    ],
                ],
                [4.0 * cm, 4.0 * cm, 3.8 * cm, 4.7 * cm],
                header_align="CENTER",
            ),
            Spacer(1, 0.2 * cm),
            Paragraph(
                f"<b>Índice operacional</b> (fechados / atribuídos): "
                f"<b>{_indice(fech, atrib)}</b>",
                corpo_style,
            ),
            Paragraph(
                "Índice com fontes diferentes: atribuídos vêm do SGC; fechados vêm do GLPI. "
                "Não é percentual de resolução da semana nem relatório de assertividade.",
                nota_style,
            ),
            Paragraph("Comparação com o período anterior", subtitulo_style),
            Paragraph(
                f"Mesmo tamanho de intervalo imediatamente anterior: "
                f"<b>{escape(str(prev_label))}</b>.",
                nota_style,
            ),
            self._tabela_comparacao(
                atrib,
                atrib_ant,
                fech,
                fech_ant,
                tempo,
                tempo_ant,
                delta_style,
            ),
        ]

        chart_s = self._grafico_serie(atual)
        if chart_s is not None:
            elementos.append(Paragraph("Volume por dia", subtitulo_style))
            elementos.append(
                Paragraph("Atribuídos (SGC) e fechados (GLPI) em cada dia do intervalo.", nota_style)
            )
            elementos.append(chart_s)
        chart_p = self._grafico_pizza(atual)
        if chart_p is not None:
            elementos.append(Paragraph("Fechados por equipe", subtitulo_style))
            elementos.append(chart_p)

        elementos.append(Paragraph("Quem mais fechou", subtitulo_style))
        rank = list(_attr(atual, "rank_fechou_mais") or [])[:5]
        if rank:
            dados_r = [["#", "Técnico", "Equipe", "Fechados"]]
            for i, r in enumerate(rank, 1):
                dados_r.append(
                    [
                        str(i),
                        str(_attr(r, "tecnico") or "—"),
                        str(_attr(r, "equipe") or "—"),
                        _fmt_int(int(_attr(r, "fechados", 0) or 0)),
                    ]
                )
            elementos.append(
                self._criar_tabela(dados_r, [1.2 * cm, 7.0 * cm, 4.5 * cm, 3.8 * cm])
            )
        else:
            elementos.append(
                Paragraph("Nenhum técnico com fechamentos no período.", corpo_style)
            )

        elementos.append(Paragraph("Demanda no período", subtitulo_style))
        elementos.append(
            Paragraph(
                "Solicitantes = atribuídos SGC. Localizações = fechamentos GLPI.",
                nota_style,
            )
        )
        elementos.append(self._tabela_demanda(atual))

        elementos.append(Paragraph("Por equipe", subtitulo_style))
        elementos.append(
            Paragraph(
                "Percentual = participação nos fechamentos do período. "
                "Backlog não entra nesta tabela (é snapshot do momento da consulta).",
                nota_style,
            )
        )
        elementos.append(self._tabela_equipes(atual))
        elementos.append(Spacer(1, 0.25 * cm))
        elementos.append(
            Paragraph(
                "Backlog ativo = chamados locais com Sit=1 agora, independente do intervalo.",
                nota_style,
            )
        )

        doc = SimpleDocTemplate(
            str(caminho),
            pagesize=A4,
            leftMargin=1.5 * cm,
            rightMargin=1.5 * cm,
            topMargin=1.3 * cm,
            bottomMargin=1.7 * cm,
            title=f"Relatório operacional SGC {start} a {end}",
            author="SGC",
        )
        doc.build(elementos, onFirstPage=self._rodape, onLaterPages=self._rodape)
        self.logger.info(f"PDF OPS GERADO: {caminho}")
        self._ultimo_arquivo = str(caminho)
        return caminho

    @staticmethod
    def _rodape(canvas, doc) -> None:
        canvas.saveState()
        width, _height = A4
        canvas.setStrokeColor(AZUL_FAIXA)
        canvas.setLineWidth(0.5)
        canvas.line(1.5 * cm, 1.2 * cm, width - 1.5 * cm, 1.2 * cm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(CINZA_TEXTO)
        canvas.drawString(1.5 * cm, 0.75 * cm, "SGC — Relatório operacional · Uso interno")
        canvas.drawRightString(
            width - 1.5 * cm, 0.75 * cm, f"Página {canvas.getPageNumber()}"
        )
        canvas.restoreState()

    def _grafico_serie(self, atual: Any) -> Optional[Drawing]:
        serie = list(_attr(atual, "serie_diaria") or [])
        if not serie:
            return None
        atrib = [float(int(_attr(s, "atribuidos", 0) or 0)) for s in serie]
        fech = [float(int(_attr(s, "fechados", 0) or 0)) for s in serie]
        if not any(atrib) and not any(fech):
            return None
        n = len(serie)
        step = max(1, n // 8)
        names = []
        for i, s in enumerate(serie):
            iso = str(_attr(s, "data") or "")
            label = _br_date(iso)
            short = label[:5] if len(label) >= 5 else label
            if i == 0 or i == n - 1 or i % step == 0:
                names.append(short)
            else:
                names.append("")
        drawing = Drawing(460, 195)
        chart = HorizontalLineChart()
        chart.x = 40
        chart.y = 40
        chart.height = 125
        chart.width = 400
        chart.data = [atrib, fech]
        chart.categoryAxis.categoryNames = names
        chart.categoryAxis.labels.fontSize = 7
        chart.categoryAxis.labels.fillColor = CINZA_TEXTO
        chart.valueAxis.valueMin = 0
        chart.valueAxis.labels.fontSize = 7
        chart.lines[0].strokeColor = colors.HexColor("#0d7377")
        chart.lines[0].strokeWidth = 1.8
        chart.lines[1].strokeColor = colors.HexColor("#0384c7")
        chart.lines[1].strokeWidth = 1.8
        drawing.add(chart)
        return drawing

    def _grafico_pizza(self, atual: Any) -> Optional[Drawing]:
        rows = []
        for t in _attr(atual, "teams") or []:
            nome = str(_attr(t, "equipe") or "").strip()
            if not nome or nome.upper() == "TOTAL":
                continue
            fech = int(_attr(t, "fechados", 0) or 0)
            if fech > 0:
                rows.append((nome, fech))
        rows.sort(key=lambda x: -x[1])
        rows = rows[:8]
        if not rows:
            return None
        drawing = Drawing(460, 205)
        pie = Pie()
        pie.x = 50
        pie.y = 30
        pie.width = 145
        pie.height = 145
        pie.data = [r[1] for r in rows]
        pie.labels = [r[0] for r in rows]
        pie.simpleLabels = 1
        pie.slices.strokeWidth = 0.4
        pie.slices.fontSize = 7
        palette = [
            colors.HexColor("#0d7377"),
            colors.HexColor("#0384c7"),
            colors.HexColor("#d69e2e"),
            colors.HexColor("#9b2c2c"),
            colors.HexColor("#6b46c1"),
            colors.HexColor("#2b6cb0"),
            colors.HexColor("#38a169"),
            colors.HexColor("#dd6b20"),
        ]
        for i in range(len(rows)):
            pie.slices[i].fillColor = palette[i % len(palette)]
        drawing.add(pie)
        return drawing

    @staticmethod
    def _texto_executivo(
        *,
        atrib: int,
        fech: int,
        tempo: Optional[float],
        backlog: int,
        atrib_ant: int,
        fech_ant: int,
        tempo_ant: Optional[float],
        prev_label: str,
        atual: Any,
    ) -> str:
        idx = _indice(fech, atrib)
        d_atrib = _delta_int_plain(atrib, atrib_ant)
        d_fech = _delta_int_plain(fech, fech_ant)
        d_tempo = _delta_hours_plain(tempo, tempo_ant)
        top_eq = ClRelatorioOpsPdf._equipe_mais_fechados(atual)
        top_tec = ClRelatorioOpsPdf._tecnico_mais_fechou(atual)
        eq_txt = (
            f"A equipe <b>{escape(top_eq[0])}</b> concentrou {_fmt_int(top_eq[1])} fechamento(s)."
            if top_eq
            else "Nenhuma equipe concentrou fechamentos neste recorte."
        )
        tec_txt = (
            f"Quem mais fechou: <b>{escape(top_tec[0])}</b> "
            f"({escape(top_tec[1] or '—')}) com {_fmt_int(top_tec[3])} chamado(s)."
            if top_tec
            else "Não há técnico com fechamentos neste recorte."
        )
        return (
            f"No período o SGC atribuiu <b>{_fmt_int(atrib)}</b> chamado(s) e o GLPI registrou "
            f"<b>{_fmt_int(fech)}</b> fechamento(s) (índice operacional <b>{idx}</b>). "
            f"Tempo médio de abertura até fechamento: <b>{_fmt_hours(tempo)}</b>. "
            f"Backlog ativo agora: <b>{_fmt_int(backlog)}</b> (snapshot, não do intervalo). "
            f"Em relação a {escape(prev_label)}: atribuídos {d_atrib}, fechados {d_fech}, "
            f"tempo médio {d_tempo}. {eq_txt} {tec_txt}"
        )

    @staticmethod
    def _equipe_mais_fechados(atual: Any) -> Optional[tuple]:
        best = None
        for t in _attr(atual, "teams") or []:
            nome = str(_attr(t, "equipe") or "").strip()
            if not nome or nome.upper() == "TOTAL":
                continue
            fech = int(_attr(t, "fechados", 0) or 0)
            atrib = int(_attr(t, "atribuidos", 0) or 0)
            if best is None or (fech, atrib) > (best[1], best[2]):
                best = (nome, fech, atrib)
        if best is None or best[1] <= 0:
            return None
        return (best[0], best[1])

    @staticmethod
    def _tecnico_mais_fechou(atual: Any) -> Optional[tuple]:
        rank = list(_attr(atual, "rank_fechou_mais") or [])
        if rank:
            r = rank[0]
            return (
                str(_attr(r, "tecnico") or ""),
                str(_attr(r, "equipe") or ""),
                str(_attr(r, "matricula") or "") or None,
                int(_attr(r, "fechados", 0) or 0),
            )
        filtro = _attr(atual, "filtro_tecnico")
        if not filtro:
            return None
        fech = int(_attr(_attr(atual, "totals"), "fechados", 0) or 0)
        if fech <= 0:
            return None
        eq = ""
        for t in _attr(atual, "teams") or []:
            if int(_attr(t, "fechados", 0) or 0) > 0:
                eq = str(_attr(t, "equipe") or "")
                break
        return (str(filtro), eq, None, fech)

    def _delta_cell(self, texto: str, cor: Optional[str], style: ParagraphStyle) -> Paragraph:
        if cor:
            return Paragraph(f'<font color="{cor}">{escape(texto)}</font>', style)
        return Paragraph(escape(texto), style)

    def _tabela_comparacao(
        self,
        atrib: int,
        atrib_ant: int,
        fech: int,
        fech_ant: int,
        tempo: Optional[float],
        tempo_ant: Optional[float],
        delta_style: ParagraphStyle,
    ) -> Table:
        def cor_volume(cur: int, prev: int) -> Optional[str]:
            if cur > prev:
                return VERDE
            if cur < prev:
                return VERMELHO
            return None

        def cor_tempo(cur: Optional[float], prev: Optional[float]) -> Optional[str]:
            if cur is None or prev is None:
                return None
            if cur < prev:
                return VERDE
            if cur > prev:
                return VERMELHO
            return None

        dados = [
            ["Indicador", "Período atual", "Período anterior", "Variação"],
            [
                "Atribuídos",
                _fmt_int(atrib),
                _fmt_int(atrib_ant),
                self._delta_cell(
                    _delta_int_plain(atrib, atrib_ant),
                    cor_volume(atrib, atrib_ant),
                    delta_style,
                ),
            ],
            [
                "Fechados",
                _fmt_int(fech),
                _fmt_int(fech_ant),
                self._delta_cell(
                    _delta_int_plain(fech, fech_ant),
                    cor_volume(fech, fech_ant),
                    delta_style,
                ),
            ],
            [
                "Tempo médio",
                _fmt_hours(tempo),
                _fmt_hours(tempo_ant),
                self._delta_cell(
                    _delta_hours_plain(tempo, tempo_ant),
                    cor_tempo(tempo, tempo_ant),
                    delta_style,
                ),
            ],
        ]
        return self._criar_tabela(dados, [4.0 * cm, 3.8 * cm, 4.2 * cm, 4.5 * cm])

    def _tabela_demanda(self, atual: Any) -> Table:
        sols = list(_attr(atual, "top_solicitantes") or [])[:5]
        locs = list(_attr(atual, "top_localizacoes") or [])[:5]
        n = max(len(sols), len(locs), 1)
        dados = [["#", "Quem mais pede", "Qtd", "Onde mais abre", "Qtd"]]
        for i in range(n):
            sol = sols[i] if i < len(sols) else None
            loc = locs[i] if i < len(locs) else None
            dados.append(
                [
                    str(i + 1),
                    str(_attr(sol, "nome") or "—") if sol else "—",
                    _fmt_int(int(_attr(sol, "qtd", 0) or 0)) if sol else "—",
                    str(_attr(loc, "nome") or "—") if loc else "—",
                    _fmt_int(int(_attr(loc, "qtd", 0) or 0)) if loc else "—",
                ]
            )
        return self._criar_tabela(
            dados, [1.0 * cm, 5.6 * cm, 1.6 * cm, 6.4 * cm, 1.9 * cm]
        )

    def _tabela_equipes(self, atual: Any) -> Table:
        totais = _attr(atual, "totals")
        total_fech = int(_attr(totais, "fechados", 0) or 0)
        dados = [["Equipe", "Atribuídos", "Fechados", "% fechados", "Tempo médio"]]
        linhas = []
        for t in _attr(atual, "teams") or []:
            nome = str(_attr(t, "equipe") or "").strip()
            if not nome or nome.upper() == "TOTAL":
                continue
            fech = int(_attr(t, "fechados", 0) or 0)
            linhas.append(
                [
                    nome,
                    _fmt_int(int(_attr(t, "atribuidos", 0) or 0)),
                    _fmt_int(fech),
                    _pct(fech, total_fech),
                    _fmt_hours(_attr(t, "tempo_medio_horas")),
                ]
            )
        linhas.append(
            [
                "TOTAL",
                _fmt_int(int(_attr(totais, "atribuidos", 0) or 0)),
                _fmt_int(total_fech),
                "100%" if total_fech > 0 else "—",
                _fmt_hours(_attr(totais, "tempo_medio_horas")),
            ]
        )
        if len(linhas) == 1:
            dados.append(["—", "0", "0", "—", "—"])
        dados.extend(linhas)
        tabela = self._criar_tabela(
            dados, [4.2 * cm, 2.8 * cm, 2.8 * cm, 2.8 * cm, 3.9 * cm]
        )
        tabela.setStyle(TableStyle([("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")]))
        return tabela

    @staticmethod
    def _criar_tabela(dados, larguras, header_align="LEFT"):
        tabela = Table(dados, colWidths=larguras, repeatRows=1)
        tabela.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), AZUL_FAIXA),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ALIGN", (0, 0), (-1, 0), header_align),
                    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                    ("ALIGN", (0, 1), (0, -1), "LEFT"),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e0")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, CINZA_LINHA],
                    ),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        return tabela


def gerar_relatorio_ops_pdf(atual: Any, anterior: Any = None) -> Path:
    return ClRelatorioOpsPdf().gerar(atual, anterior)
